"""Oracle cross-checks for the mermaid renderer's parser + emitter.

Our `scripts/mermaid_layout/` is a from-scratch reimplementation of Mermaid (it
does NOT run mermaid.js — see docs/specs/mermaid-source-bridge/spec.md). That can
silently drift from what real Mermaid understands: a dropped node or misread edge
renders a clean-looking-but-wrong diagram, and a pixel snapshot can't catch it.

Since #63 the renderer emits stable identity on its HTML output — `data-node-id`
on entities and `data-src`/`data-dst` on edges — so both oracle modes below read
*our own rendered output* the same way, uniformly across diagram types (no more
per-type internal-parser adapters on our side).

Two modes:

  1. SELF-CONSISTENCY (universal, no external dep) — render our HTML and assert
     every edge endpoint resolves to a declared node (no dangling / misreferenced
     edges). Runs for EVERY diagram type, needs no mermaid.js, and is the only
     viable check for `block-beta` (see below). Catches the dropped/misreferenced
     topology bug class without any ground truth.

  2. DIFFERENTIAL (vs real mermaid.js via `mermaidx`) — for diagram types mermaidx
     renders reliably, assert our topology covers everything mermaid.js drew.
     Strongest, but gated on mermaidx and guarded per-fixture: a mermaidx crash is
     skipped with a reason, never a hard failure.

`block-beta` is deliberately DIFFERENTIAL-excluded: mermaidx (mermaid.js on
QuickJS) crashes with "circular reference" on common block constructs (nested
blocks, width specifiers). It renders trivial blocks but not the rich syntax we
support, so it is not a trustworthy ground truth for block — block relies on the
self-consistency mode instead.

Run:  pytest tests/test_oracle.py
Self-consistency runs everywhere; differential skips cleanly without `mermaidx`.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_layout import _dispatch  # noqa: E402

_ALL_FIXTURES = sorted(FIXTURES_DIR.glob("*.mmd"))
_HAVE_MERMAIDX = importlib.util.find_spec("mermaidx") is not None

# ── our side: uniform output-level extraction (stable data-* identity, #63) ────

_OUR_NODE_RE = re.compile(r'data-node-id="([^"]*)"')
_OUR_EDGE_RE = re.compile(r'data-src="([^"]*)"[^>]*?data-dst="([^"]*)"')
# start/end pseudo-markers our renderer synthesizes for stateDiagram [*]; they are
# real edge endpoints but not user-declared nodes, so self-consistency exempts them.
_PSEUDO_ENDPOINT = re.compile(r'_sm_(start|end)_$')


def _our_topology(src: str) -> tuple[set[str], set[tuple[str, str]]]:
    html = _dispatch(src, None, 800)
    nodes = set(_OUR_NODE_RE.findall(html))
    edges = set(_OUR_EDGE_RE.findall(html))
    return nodes, edges


# ── mode 1: self-consistency (universal, no mermaid.js) ───────────────────────

@pytest.mark.parametrize("fixture", _ALL_FIXTURES, ids=lambda p: p.stem)
def test_no_dangling_edges(fixture: Path):
    """Every edge endpoint our emitter draws must resolve to a node it declared.

    This is the block-safe check: it needs no ground truth, so it covers
    block-beta and every other type, catching edges to phantom/misspelled nodes.
    """
    nodes, edges = _our_topology(fixture.read_text())
    if not edges:
        pytest.skip("no edges in this diagram type")
    endpoints = {e for pair in edges for e in pair}
    dangling = {
        e for e in endpoints
        if e not in nodes and not _PSEUDO_ENDPOINT.search(e)
    }
    assert not dangling, (
        f"{fixture.stem}: edges reference undeclared nodes {sorted(dangling)} "
        f"(declared: {sorted(nodes)})"
    )


# ── mode 2: differential vs real mermaid.js (gated + guarded) ─────────────────

# Per-type mermaid.js SVG identity extractors. Our side is uniform (above); only
# mermaid's side varies, because we don't control its SVG conventions.
_MM_FLOWCHART_NODE = re.compile(r'flowchart-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_SERVICE_NODE = re.compile(r'service-([A-Za-z0-9_.\-]+?)"')
_MM_ENTITY_NODE = re.compile(r'entity-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_LINK_EDGE = re.compile(r'L_([A-Za-z0-9_.\-]+?)_([A-Za-z0-9_.\-]+?)_\d+"')


def _mm_flowchart(svg: str):
    return set(_MM_FLOWCHART_NODE.findall(svg)), set(_MM_LINK_EDGE.findall(svg))


def _mm_architecture(svg: str):
    return set(_MM_SERVICE_NODE.findall(svg)), set(_MM_LINK_EDGE.findall(svg))


def _mm_er(svg: str):
    # ER relationship ids encode the entity pair; nodes are entity-<Name>-<n>.
    return set(_MM_ENTITY_NODE.findall(svg)), set()


# fixture-prefix → mermaid-side extractor. Types absent here use self-consistency
# only (mermaidx renders them but exposes no stable topology ids), and block-beta
# is intentionally omitted (mermaidx circular-reference crash).
_DIFFERENTIAL = {
    "flowchart": _mm_flowchart,
    "architecture": _mm_architecture,
    "er": _mm_er,
}

_DIFF_FIXTURES = [
    f for f in _ALL_FIXTURES if f.stem.split("-")[0] in _DIFFERENTIAL
]


@pytest.mark.skipif(not _HAVE_MERMAIDX, reason="differential mode needs `pip install mermaidx`")
@pytest.mark.parametrize("fixture", _DIFF_FIXTURES, ids=lambda p: p.stem)
def test_topology_covers_mermaid(fixture: Path):
    """Our rendered topology must cover everything real mermaid.js drew."""
    import mermaidx

    src = fixture.read_text()
    try:
        svg = mermaidx.render(src).svg()
    except Exception as exc:  # mermaidx/QuickJS crash → not our bug; skip loudly
        pytest.skip(f"mermaidx failed to render {fixture.stem}: {str(exc)[:60]}")

    extractor = _DIFFERENTIAL[fixture.stem.split("-")[0]]
    mm_nodes, mm_edges = extractor(svg)
    our_nodes, our_edges = _our_topology(src)

    missing_nodes = mm_nodes - our_nodes
    missing_edges = mm_edges - our_edges
    assert not missing_nodes, (
        f"{fixture.stem}: parser dropped nodes mermaid.js drew: "
        f"{sorted(missing_nodes)} (ours: {sorted(our_nodes)})"
    )
    assert not missing_edges, (
        f"{fixture.stem}: parser dropped edges mermaid.js drew: "
        f"{sorted(missing_edges)} (ours: {sorted(our_edges)})"
    )
