"""Oracle cross-checks for the mermaid renderer's parser + emitter.

Our `scripts/mermaid_render/` is a from-scratch reimplementation of Mermaid (it
does NOT run mermaid.js — see docs/specs/mermaid-source-bridge/spec.md). That can
silently drift from what real Mermaid understands: a dropped node or misread edge
renders a clean-looking-but-wrong diagram, and a pixel snapshot can't catch it.

Since #63 the renderer emits stable identity on its HTML output — `data-node-id`
on entities and `data-src`/`data-dst` on edges — so both oracle modes below read
*our own rendered output* the same way, uniformly across diagram types.

Two modes:

  1. SELF-CONSISTENCY (universal, no external dep) — render our HTML and assert
     every edge endpoint resolves to a declared node (no dangling / misreferenced
     edges). Runs for EVERY diagram type.

  2. DIFFERENTIAL (vs real mermaid.js via mmdc/Chromium) — for diagram types mmdc
     renders reliably, assert our topology matches what mermaid.js drew.  Uses
     mmdc (which drives Chromium internally, the same engine as mmdc's production
     render path) instead of mermaidx/QuickJS, so the reference is authoritative
     and not QuickJS-specific.

     Comparison is SYMMETRIC: checks what we're missing AND what we've added vs
     the reference.  Adds edge label comparison for types that expose stable labels.

     Every skip is classified with a code so it is visible in the report:
       [REFERENCE_RENDER_FAILURE]  mmdc returned non-zero / produced no SVG
       [EXTRACTOR_GAP]             no topology extractor registered for this type,
                                   or the extractor raised
       [NATIVE_UNSUPPORTED]        our renderer raises ValueError for this type
       [NO_APPLICABLE_RELATIONS]   reference extracted no nodes or edges

Run:  pytest tests/test_oracle.py
Self-consistency runs everywhere; differential skips cleanly when mmdc is absent.
"""
from __future__ import annotations

import html as _html_lib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_layout import _dispatch  # noqa: E402

_ALL_FIXTURES = sorted(FIXTURES_DIR.glob("*.mmd"))
_HAVE_MMDC = shutil.which("mmdc") is not None

# ── our side: uniform output-level extraction (stable data-* identity, #63) ────

_OUR_NODE_RE       = re.compile(r'data-node-id="([^"]*)"')
_OUR_EDGE_RE       = re.compile(r'data-src="([^"]*)"[^>]*?data-dst="([^"]*)"')
_OUR_EDGE_LABEL_RE = re.compile(r'data-edge-label="([^"]*)"')
# start/end pseudo-markers our renderer synthesizes for stateDiagram [*]; they are
# real edge endpoints but not user-declared nodes, so self-consistency exempts them.
_PSEUDO_ENDPOINT   = re.compile(r'_sm_(start|end)_$')


def _our_topology(
    src: str,
) -> tuple[frozenset[str], frozenset[tuple[str, str]], frozenset[str]]:
    """Return (nodes, edges, edge_labels) extracted from our rendered HTML."""
    html   = _dispatch(src, None, 800)
    nodes  = frozenset(_OUR_NODE_RE.findall(html))
    edges  = frozenset(tuple(m) for m in _OUR_EDGE_RE.findall(html))
    labels = frozenset(
        _html_lib.unescape(lbl)
        for lbl in _OUR_EDGE_LABEL_RE.findall(html)
        if lbl
    )
    return nodes, edges, labels


# ── mode 1: self-consistency (universal, no mermaid.js) ───────────────────────

@pytest.mark.parametrize("fixture", _ALL_FIXTURES, ids=lambda p: p.stem)
def test_no_dangling_edges(fixture: Path):
    """Every edge endpoint our emitter draws must resolve to a node it declared.

    This check needs no ground truth: it catches edges to phantom or misspelled
    nodes purely from our own rendered output, covering every diagram type.
    """
    try:
        nodes, edges, _ = _our_topology(fixture.read_text())
    except ValueError as e:
        pytest.skip(f"[NATIVE_UNSUPPORTED] {fixture.stem}: {e}")
    if not edges:
        pytest.skip("[NO_APPLICABLE_RELATIONS] no edges in this diagram type")
    endpoints = {e for pair in edges for e in pair}
    dangling = {
        e for e in endpoints
        if e not in nodes and not _PSEUDO_ENDPOINT.search(e)
    }
    assert not dangling, (
        f"{fixture.stem}: edges reference undeclared nodes {sorted(dangling)} "
        f"(declared: {sorted(nodes)})"
    )


# ── mode 2: differential vs real mermaid.js (mmdc/Chromium) ──────────────────

def _mmdc_render(src: str) -> "str | None":
    """Run mmdc (Chromium) and return the SVG string, or None on failure.

    Returns None on non-zero exit, timeout, or missing output — callers
    classify those as [REFERENCE_RENDER_FAILURE].
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mmd_path = tmp_path / "d.mmd"
        svg_path = tmp_path / "d.svg"
        mmd_path.write_text(src, encoding="utf-8")
        try:
            result = subprocess.run(
                ["mmdc", "-i", str(mmd_path), "-o", str(svg_path), "--quiet"],
                capture_output=True,
                timeout=90,  # Chromium cold-start can be slow
            )
        except subprocess.TimeoutExpired:
            return None
        if result.returncode != 0 or not svg_path.exists():
            return None
        return svg_path.read_text(encoding="utf-8")


def _strip_html_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


# Per-type reference-side extractors for the mmdc SVG.
# Each returns: (nodes: frozenset[str], edges: frozenset[tuple[str,str]],
#                edge_labels: frozenset[str])
_MM_FLOWCHART_NODE = re.compile(r'flowchart-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_SERVICE_NODE   = re.compile(r'service-([A-Za-z0-9_.\-]+?)"')
_MM_ENTITY_NODE    = re.compile(r'entity-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_LINK_EDGE      = re.compile(r'L_([A-Za-z0-9_.\-]+?)_([A-Za-z0-9_.\-]+?)_\d+"')
# Edge labels: <span class="edgeLabel"><p>text</p></span> (non-empty only).
# Unlabeled edges use <span class="edgeLabel"></span> (no <p>) — those don't match.
_MM_EDGE_LABEL     = re.compile(
    r'<span class="edgeLabel"><p[^>]*>(.*?)</p></span>', re.DOTALL
)


def _mm_flowchart(svg: str):
    nodes  = frozenset(_MM_FLOWCHART_NODE.findall(svg))
    edges  = frozenset(tuple(m) for m in _MM_LINK_EDGE.findall(svg))
    labels = frozenset(
        _strip_html_tags(raw) for raw in _MM_EDGE_LABEL.findall(svg)
        if _strip_html_tags(raw)
    )
    return nodes, edges, labels


def _mm_architecture(svg: str):
    nodes = frozenset(_MM_SERVICE_NODE.findall(svg))
    edges = frozenset(tuple(m) for m in _MM_LINK_EDGE.findall(svg))
    return nodes, edges, frozenset()


def _mm_er(svg: str):
    # ER relationship ids encode the entity pair; nodes are entity-<Name>-<n>.
    # No stable edge-id convention in mermaid's ER SVG.
    nodes = frozenset(_MM_ENTITY_NODE.findall(svg))
    return nodes, frozenset(), frozenset()


# fixture-prefix → reference-side extractor.  Types absent here are not in the
# differential suite: either mermaid produces no stable topology ids for them, or
# no extractor has been written yet (add one and it automatically joins the suite).
_DIFFERENTIAL: dict[str, object] = {
    "flowchart":    _mm_flowchart,
    "architecture": _mm_architecture,
    "er":           _mm_er,
}

_DIFF_FIXTURES = [
    f for f in _ALL_FIXTURES if f.stem.split("-")[0] in _DIFFERENTIAL
]


@pytest.mark.skipif(
    not _HAVE_MMDC,
    reason="differential mode needs mmdc (npm i -g @mermaid-js/mermaid-cli)",
)
@pytest.mark.parametrize("fixture", _DIFF_FIXTURES, ids=lambda p: p.stem)
def test_topology_matches_reference(fixture: Path):
    """Symmetric topology check: our output vs the mmdc/Chromium reference.

    Replaces the former mermaidx/QuickJS differential test.  mmdc drives the same
    Chromium + Puppeteer stack as real mermaid CLI, so reference failures are
    authoritative rather than QuickJS-specific crashes.

    Checks BOTH directions:
      - missing_nodes / missing_edges  — things the reference drew that we dropped
      - extra_nodes   / extra_edges    — things we emitted that the reference lacks
    Also checks edge labels for types whose extractors return them.
    """
    src   = fixture.read_text()
    dtype = fixture.stem.split("-")[0]

    svg = _mmdc_render(src)
    if svg is None:
        pytest.skip(
            f"[REFERENCE_RENDER_FAILURE] mmdc failed to render {fixture.stem}"
        )

    extractor = _DIFFERENTIAL.get(dtype)
    if extractor is None:
        pytest.skip(f"[EXTRACTOR_GAP] no differential extractor for type '{dtype}'")

    try:
        ref_nodes, ref_edges, ref_labels = extractor(svg)
    except Exception as exc:
        pytest.skip(
            f"[EXTRACTOR_GAP] extractor raised for {fixture.stem}: {str(exc)[:80]}"
        )

    if not ref_nodes and not ref_edges:
        pytest.skip(
            f"[NO_APPLICABLE_RELATIONS] reference yielded no nodes or edges "
            f"for {fixture.stem}"
        )

    try:
        our_nodes, our_edges, our_labels = _our_topology(src)
    except ValueError as exc:
        pytest.skip(f"[NATIVE_UNSUPPORTED] {fixture.stem}: {exc}")

    errors: list[str] = []

    # Nodes — always compared when the reference provides them.
    missing_nodes = ref_nodes - our_nodes
    extra_nodes   = our_nodes - ref_nodes
    if missing_nodes:
        errors.append(f"missing nodes  {sorted(missing_nodes)}")
    if extra_nodes:
        errors.append(f"extra nodes    {sorted(extra_nodes)}")

    # Edges — only compared when the reference extractor provides them.
    # When the extractor returns frozenset() it means "no stable edge-id
    # convention in this diagram type's SVG" (e.g. ER), not "no edges exist".
    # Self-loops (src == dst) are excluded from differential comparison: mermaid.js
    # renders them but uses element IDs that the current extractor regex doesn't
    # capture, causing false "extra edges" on our side.
    if ref_edges:
        our_non_self  = frozenset(e for e in our_edges  if e[0] != e[1])
        ref_non_self  = frozenset(e for e in ref_edges  if e[0] != e[1])
        missing_edges = ref_non_self - our_non_self
        extra_edges   = our_non_self - ref_non_self
        if missing_edges:
            errors.append(f"missing edges  {sorted(missing_edges)}")
        if extra_edges:
            errors.append(f"extra edges    {sorted(extra_edges)}")

    # Edge labels — only compared when the reference extractor provides them.
    if ref_labels:
        missing_labels = ref_labels - our_labels
        extra_labels   = our_labels - ref_labels
        if missing_labels:
            errors.append(f"missing edge labels  {sorted(missing_labels)}")
        if extra_labels:
            errors.append(f"extra edge labels    {sorted(extra_labels)}")

    assert not errors, (
        f"{fixture.stem}:\n" + "\n".join(f"  {e}" for e in errors)
    )
