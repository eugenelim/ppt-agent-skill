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
from typing import Any

import pytest

from tools.mermaid_fidelity.oracle_contract import (
    OracleStatus,
    OracleCheck,
    OracleResult,
    FixtureMinimums,
    ManifestError,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_layout import _dispatch  # noqa: E402

_ALL_FIXTURES = sorted(FIXTURES_DIR.glob("*.mmd"))
_HAVE_MMDC = shutil.which("mmdc") is not None


# ── T1: Oracle result helper ──────────────────────────────────────────────────

def _make_result(
    stem: str,
    status: OracleStatus,
    checks_run: int,
    notes: list[str] | None = None,
) -> OracleResult:
    notes = notes or []
    checks = tuple(
        OracleCheck(name=f"check_{i}", passed=(status == OracleStatus.PASS))
        for i in range(checks_run)
    )
    return OracleResult(
        status=status,
        checks=checks,
        diagnostics=tuple(notes),
        fixture_stem=stem,
    )


# ── T3: Fixture minimum-count manifest ───────────────────────────────────────

_FIXTURE_MINIMUMS: dict[str, FixtureMinimums] = {
    # architecture
    "architecture-basic":         FixtureMinimums(min_entities=1),
    "architecture-complex":       FixtureMinimums(min_entities=2),
    # er
    "er-basic":                   FixtureMinimums(min_entities=2),
    "er-cardinality-all":         FixtureMinimums(min_entities=2),
    "er-ecommerce":               FixtureMinimums(min_entities=3),
    "er-identifying":             FixtureMinimums(min_entities=2),
    # flowchart
    "flowchart-all-shapes":       FixtureMinimums(min_entities=2),
    "flowchart-arrows-defs":      FixtureMinimums(min_entities=2),
    "flowchart-bidirectional":    FixtureMinimums(min_entities=2),
    "flowchart-br-variants":      FixtureMinimums(min_entities=2),
    "flowchart-cross-scope-edge": FixtureMinimums(min_entities=2),
    "flowchart-deep-nesting":     FixtureMinimums(min_entities=2),
    "flowchart-diamond-branch":   FixtureMinimums(min_entities=2),
    "flowchart-diamond-clipping": FixtureMinimums(min_entities=2),
    "flowchart-empty-subgraph":   FixtureMinimums(min_entities=2),
    "flowchart-groups-complex":   FixtureMinimums(min_entities=2),
    "flowchart-html-entities":    FixtureMinimums(min_entities=2),
    "flowchart-inline-styles":    FixtureMinimums(min_entities=2),
    "flowchart-inner-direction":  FixtureMinimums(min_entities=2),
    "flowchart-label-formatting": FixtureMinimums(min_entities=2),
    "flowchart-linkstyle":        FixtureMinimums(min_entities=2),
    "flowchart-lr-text-metrics":  FixtureMinimums(min_entities=2),
    "flowchart-markdown-labels":  FixtureMinimums(min_entities=2),
    "flowchart-multiline-br":     FixtureMinimums(min_entities=2),
    "flowchart-no-arrows":        FixtureMinimums(min_entities=2),
    "flowchart-parallel-links":   FixtureMinimums(min_entities=2),
    "flowchart-self-loops":       FixtureMinimums(min_entities=2),
    "flowchart-shapes-new":       FixtureMinimums(min_entities=2),
    "flowchart-tb-text-metrics":  FixtureMinimums(min_entities=2),
    # class
    "class-basic":                FixtureMinimums(min_entities=2, min_relations=1),
    "class-methods":              FixtureMinimums(min_entities=2, min_relations=1),
    "class-relationships-all":    FixtureMinimums(min_entities=2, min_relations=7),
    "class-visibility":           FixtureMinimums(min_entities=2, min_relations=2),
    # requirement
    "requirement-basic":          FixtureMinimums(min_entities=2),
}


def _get_fixture_minimums(stem: str) -> FixtureMinimums:
    if stem not in _FIXTURE_MINIMUMS:
        raise ManifestError(
            f"No minimum-count declaration for differential fixture '{stem}'"
        )
    return _FIXTURE_MINIMUMS[stem]


# ── T4: Relation key with arrow type ─────────────────────────────────────────

def _relation_key(
    src: str, dst: str, label: str = "", arrow: "str | None" = None
) -> tuple:
    return (src, dst, label, arrow)


# ── Our-side topology extractors ──────────────────────────────────────────────

_OUR_NODE_RE       = re.compile(r'data-node-id="([^"]*)"')
_OUR_EDGE_RE       = re.compile(r'data-src="([^"]*)"[^>]*?data-dst="([^"]*)"')
_OUR_EDGE_LABEL_RE = re.compile(r'data-edge-label="([^"]*)"')
_PSEUDO_ENDPOINT   = re.compile(r'_sm_(start|end)_$')


def _is_proxy_endpoint(node_id: str) -> bool:
    return bool(_PSEUDO_ENDPOINT.search(node_id))


def _our_topology(
    src: str,
) -> "tuple[frozenset[str], frozenset[tuple[str, str]], frozenset[str]]":
    html   = _dispatch(src, None, 800)
    nodes  = frozenset(_OUR_NODE_RE.findall(html))
    edges  = frozenset(tuple(m) for m in _OUR_EDGE_RE.findall(html))
    labels = frozenset(
        _html_lib.unescape(lbl)
        for lbl in _OUR_EDGE_LABEL_RE.findall(html)
        if lbl
    )
    return nodes, edges, labels


# ── Mode 1: self-consistency ──────────────────────────────────────────────────

@pytest.mark.parametrize("fixture", _ALL_FIXTURES, ids=lambda p: p.stem)
def test_no_dangling_edges(fixture: Path) -> None:
    """Every edge endpoint our emitter draws must resolve to a node it declared."""
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


# ── Mode 2: differential vs real mermaid.js ───────────────────────────────────

def _mmdc_render(src: str) -> "str | None":
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mmd_path = tmp_path / "d.mmd"
        svg_path = tmp_path / "d.svg"
        mmd_path.write_text(src, encoding="utf-8")
        try:
            result = subprocess.run(
                ["mmdc", "-i", str(mmd_path), "-o", str(svg_path), "--quiet"],
                capture_output=True,
                timeout=90,
            )
        except subprocess.TimeoutExpired:
            return None
        if result.returncode != 0 or not svg_path.exists():
            return None
        return svg_path.read_text(encoding="utf-8")


def _strip_html_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


# ── T7: Extended mmdc SVG extractors ─────────────────────────────────────────

_MM_FLOWCHART_NODE = re.compile(r'flowchart-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_SERVICE_NODE   = re.compile(r'service-([A-Za-z0-9_.\-]+?)"')
_MM_ENTITY_NODE    = re.compile(r'entity-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_LINK_EDGE      = re.compile(r'L_([A-Za-z0-9_.\-]+?)_([A-Za-z0-9_.\-]+?)_\d+"')
_MM_EDGE_LABEL     = re.compile(
    r'<span class="edgeLabel"><p[^>]*>(.*?)</p></span>', re.DOTALL
)
_MM_PATH_ATTRS_RE  = re.compile(r'<path\b([^>]*)>')
_MM_ER_REL_CARDS_RE = re.compile(
    r'id="er-([A-Za-z0-9_]+?)-([A-Za-z0-9_]+?)-\d+"'
    r'.*?<text[^>]*class="er cardinality"[^>]*>\s*(\w+)\s*</text>'
    r'.*?<text[^>]*class="er cardinality"[^>]*>\s*(\w+)\s*</text>',
    re.DOTALL,
)


def _mm_flowchart(svg: str) -> tuple:
    nodes  = frozenset(_MM_FLOWCHART_NODE.findall(svg))
    edges  = frozenset(tuple(m) for m in _MM_LINK_EDGE.findall(svg))
    labels = frozenset(
        _strip_html_tags(raw) for raw in _MM_EDGE_LABEL.findall(svg)
        if _strip_html_tags(raw)
    )
    markers: set[tuple[str, str, str]] = set()
    edge_styles: set[tuple[str, str, str]] = set()
    for pm in _MM_PATH_ATTRS_RE.finditer(svg):
        attrs = pm.group(1)
        id_m = re.search(r'\bid="L_([A-Za-z0-9_.\-]+?)_([A-Za-z0-9_.\-]+?)_\d+"', attrs)
        if not id_m:
            continue
        src, dst = id_m.group(1), id_m.group(2)
        marker_m = re.search(r'\bmarker-end="url\(#flowchart-([A-Za-z]+)-[^)]+\)"', attrs)
        if marker_m:
            markers.add((src, dst, marker_m.group(1)))
        style = "dashed" if "stroke-dasharray" in attrs else "solid"
        edge_styles.add((src, dst, style))
    containment: set[tuple[str, str]] = set()
    for sg_m in re.finditer(r'<g\b[^>]*\bid="(subGraph\d+)"', svg):
        sg_id = sg_m.group(1)
        window = svg[sg_m.end(): sg_m.end() + 4000]
        for node_m in _MM_FLOWCHART_NODE.finditer(window):
            containment.add((sg_id, node_m.group(1)))
    extra: dict[str, Any] = {
        "markers":     frozenset(markers),
        "edge_styles": frozenset(edge_styles),
        "containment": frozenset(containment),
    }
    return nodes, edges, labels, extra


def _mm_architecture(svg: str) -> tuple:
    nodes = frozenset(_MM_SERVICE_NODE.findall(svg))
    edges = frozenset(tuple(m) for m in _MM_LINK_EDGE.findall(svg))
    return nodes, edges, frozenset(), {}


def _mm_er(svg: str) -> tuple:
    nodes = frozenset(_MM_ENTITY_NODE.findall(svg))
    cardinalities: set[tuple[str, str, str, str]] = set()
    for m in _MM_ER_REL_CARDS_RE.finditer(svg):
        cardinalities.add((m.group(1), m.group(2), m.group(3), m.group(4)))
    extra: dict[str, Any] = {"cardinalities": frozenset(cardinalities)}
    return nodes, frozenset(), frozenset(), extra


_MM_REQ_EDGE_RE = re.compile(r'\bdata-id="(\w+)-(\w+)-\d+"')


def _mm_requirement(svg: str) -> tuple:
    raw = _MM_REQ_EDGE_RE.findall(svg)
    edges = frozenset((m[0], m[1]) for m in raw)
    node_set = {n for pair in edges for n in pair}
    for g_tag in re.findall(r"<g\b[^>]+>", svg):
        if 'class="node' not in g_tag:
            continue
        id_m = re.search(r'\bid="([^"]*)"', g_tag)
        if id_m:
            nid = id_m.group(1)
            if "-" in nid:
                candidate = nid.rsplit("-", 1)[1]
                if re.match(r"^\w+$", candidate):
                    node_set.add(candidate)
    return frozenset(node_set), edges, frozenset(), {}


_MM_CLASS_GROUP_RE = re.compile(
    r'<g[^>]*class="[^"]*classGroup[^"]*"[^>]*>\s*<g[^>]*id="([^"]+)"')
_MM_CLASS_EDGE_RE  = re.compile(
    r'<(?:path|line)[^>]*id="([A-Za-z0-9_]+)-([A-Za-z0-9_]+)(?:-\d+)?"')


def _mm_class(svg: str) -> tuple:
    """Extract topology from an mmdc-rendered classDiagram SVG.

    Node ids: inner <g id="..."> of each <g class="classGroup ..."> element.
    Edge ids: <path id="SRC-DST[-N]"> elements.
    Labels: shared _MM_EDGE_LABEL pattern.

    Regex patterns unconfirmed (mmdc not run during initial authoring); emit an
    empty tuple on mismatch (triggers [EXTRACTOR_GAP] skip in the differential
    test). Verify by running pytest --run-external-reference tests/test_oracle.py.
    """
    nodes  = frozenset(_MM_CLASS_GROUP_RE.findall(svg))
    raw_edges = _MM_CLASS_EDGE_RE.findall(svg)
    edges = frozenset(
        (src, dst) for src, dst in raw_edges if src != dst
    )
    labels = frozenset(
        _strip_html_tags(raw) for raw in _MM_EDGE_LABEL.findall(svg)
        if _strip_html_tags(raw)
    )
    return nodes, edges, labels

_DIFFERENTIAL: dict[str, Any] = {
    "flowchart":    _mm_flowchart,
    "architecture": _mm_architecture,
    "class":        _mm_class,
    "er":           _mm_er,
    "requirement":  _mm_requirement,
}

_DIFF_FIXTURES = [
    f for f in _ALL_FIXTURES if f.stem.split("-")[0] in _DIFFERENTIAL
]


# ── T2, T5, T6: _compare_topology ─────────────────────────────────────────────

def _compare_topology(
    fixture_stem: str,
    diagram_type: str,
    our_nodes: frozenset,
    our_edges: frozenset,
    our_labels: frozenset,
    ref_nodes: frozenset,
    ref_edges: frozenset,
    ref_labels: frozenset,
    our_extra: "dict[str, Any] | None" = None,
    ref_extra: "dict[str, Any] | None" = None,
    _minimums: "FixtureMinimums | None" = None,
) -> OracleResult:
    our_semantic = frozenset(n for n in our_nodes if not _is_proxy_endpoint(n))
    if _minimums is None:
        mins = _get_fixture_minimums(fixture_stem)
    else:
        mins = _minimums
    if len(ref_nodes) < mins.min_entities:
        return _make_result(
            fixture_stem, OracleStatus.EXTRACTOR_GAP, 0,
            [
                f"ref returned {len(ref_nodes)} entities but manifest "
                f"declares min_entities={mins.min_entities}"
            ],
        )
    if mins.min_relations > 0 and len(ref_edges) < mins.min_relations:
        return _make_result(
            fixture_stem, OracleStatus.EXTRACTOR_GAP, 0,
            [
                f"ref returned {len(ref_edges)} edges but manifest "
                f"declares min_relations={mins.min_relations}"
            ],
        )
    if not ref_nodes and not our_semantic:
        if mins.min_entities > 0:
            return _make_result(
                fixture_stem, OracleStatus.EXTRACTOR_GAP, 0,
                [f"both sides empty but fixture declares min_entities={mins.min_entities}"],
            )
        return _make_result(
            fixture_stem, OracleStatus.UNVALIDATED, 0, ["no entities on either side"]
        )
    # AC4: native present + ref absent → EXTRACTOR_GAP; ref present + native absent → FAIL
    if our_semantic and not ref_nodes:
        return _make_result(
            fixture_stem, OracleStatus.EXTRACTOR_GAP, 0,
            [f"reference side empty (native has {len(our_semantic)} entities)"],
        )
    if ref_nodes and not our_semantic:
        return _make_result(
            fixture_stem, OracleStatus.FAIL, 0,
            [f"native side empty (ref has {len(ref_nodes)} entities)"],
        )
    # AC5: both non-empty with no common IDs → FAIL
    if not (ref_nodes & our_semantic):
        return _make_result(
            fixture_stem, OracleStatus.FAIL, 0,
            [
                f"zero common entities: "
                f"ref={sorted(ref_nodes)[:5]}, ours={sorted(our_semantic)[:5]}"
            ],
        )
    errors: list[str] = []
    checks_run = 0
    missing_nodes = ref_nodes - our_semantic
    extra_nodes   = our_semantic - ref_nodes
    if missing_nodes:
        errors.append(f"missing nodes  {sorted(missing_nodes)}")
    if extra_nodes:
        errors.append(f"extra nodes    {sorted(extra_nodes)}")
    checks_run += len(ref_nodes)
    if ref_edges:
        our_non_self = frozenset(e for e in our_edges if e[0] != e[1])
        ref_non_self = frozenset(e for e in ref_edges if e[0] != e[1])
        def _edge_key(e: tuple) -> tuple:
            label = e[2] if len(e) > 2 else ""
            arrow = e[3] if len(e) > 3 else None
            return _relation_key(e[0], e[1], label, arrow)
        ref_keys = frozenset(_edge_key(e) for e in ref_non_self)
        our_keys = frozenset(_edge_key(e) for e in our_non_self)
        missing_edges = ref_keys - our_keys
        extra_edges   = our_keys - ref_keys
        if missing_edges:
            errors.append(f"missing edges  {sorted(str(k) for k in missing_edges)}")
        if extra_edges:
            errors.append(f"extra edges    {sorted(str(k) for k in extra_edges)}")
        checks_run += len(ref_non_self)
    if ref_labels:
        missing_labels = ref_labels - our_labels
        extra_labels   = our_labels - ref_labels
        if missing_labels:
            errors.append(f"missing edge labels  {sorted(missing_labels)}")
        if extra_labels:
            errors.append(f"extra edge labels    {sorted(extra_labels)}")
        checks_run += len(ref_labels)
    if diagram_type == "er":
        ref_cards = (ref_extra or {}).get("cardinalities", frozenset())
        our_cards = (our_extra or {}).get("cardinalities", frozenset())
        if ref_cards:
            missing_cards = ref_cards - our_cards
            extra_cards   = our_cards - ref_cards
            if missing_cards or extra_cards:
                errors.append(
                    f"cardinality mismatch: "
                    f"missing={sorted(str(c) for c in missing_cards)}, "
                    f"extra={sorted(str(c) for c in extra_cards)}"
                )
            checks_run += len(ref_cards)
    ref_markers = (ref_extra or {}).get("markers", frozenset())
    our_markers = (our_extra or {}).get("markers", frozenset())
    if ref_markers:
        missing_markers = ref_markers - our_markers
        extra_markers   = our_markers - ref_markers
        if missing_markers or extra_markers:
            errors.append(
                f"marker mismatch: "
                f"missing={sorted(str(m) for m in missing_markers)}, "
                f"extra={sorted(str(m) for m in extra_markers)}"
            )
        checks_run += len(ref_markers)
    ref_containment = (ref_extra or {}).get("containment", frozenset())
    our_containment = (our_extra or {}).get("containment", frozenset())
    if ref_containment:
        missing_cont = ref_containment - our_containment
        extra_cont   = our_containment - ref_containment
        if missing_cont or extra_cont:
            errors.append(
                f"containment mismatch: "
                f"missing={sorted(str(c) for c in missing_cont)}, "
                f"extra={sorted(str(c) for c in extra_cont)}"
            )
        checks_run += len(ref_containment)
    if errors:
        return _make_result(fixture_stem, OracleStatus.FAIL, max(checks_run, 1), errors)
    return _make_result(fixture_stem, OracleStatus.PASS, max(checks_run, 1))


# ── T8: CI checks_run regression gate ────────────────────────────────────────

_CHECKS_RUN_BASELINE: dict[str, int] = {}


def _assert_no_checks_run_regression(results: list) -> None:
    for result in results:
        baseline = _CHECKS_RUN_BASELINE.get(result.fixture_stem)
        if baseline is not None and len(result.checks) == 0:
            raise AssertionError(
                f"{result.fixture_stem}: checks_run regressed to 0 "
                f"(baseline had {baseline})"
            )


# ── Main differential test ────────────────────────────────────────────────────

@pytest.mark.external_reference
@pytest.mark.skipif(
    not _HAVE_MMDC,
    reason="differential mode needs mmdc (npm i -g @mermaid-js/mermaid-cli)",
)
@pytest.mark.parametrize("fixture", _DIFF_FIXTURES, ids=lambda p: p.stem)
def test_topology_matches_reference(fixture: Path) -> None:
    """Symmetric topology check: our output vs the mmdc/Chromium reference."""
    src   = fixture.read_text()
    dtype = fixture.stem.split("-")[0]
    stem  = fixture.stem

    svg = _mmdc_render(src)
    if svg is None:
        pytest.skip(f"[REFERENCE_RENDER_FAILURE] mmdc failed to render {stem}")

    extractor = _DIFFERENTIAL.get(dtype)
    if extractor is None:
        pytest.skip(f"[EXTRACTOR_GAP] no differential extractor for type '{dtype}'")

    try:
        ref_result = extractor(svg)
    except Exception as exc:
        pytest.skip(f"[EXTRACTOR_GAP] extractor raised for {stem}: {str(exc)[:80]}")

    ref_nodes, ref_edges, ref_labels = ref_result[:3]
    ref_extra = ref_result[3] if len(ref_result) > 3 else None

    try:
        our_nodes, our_edges, our_labels = _our_topology(src)
    except ValueError as exc:
        pytest.skip(f"[NATIVE_UNSUPPORTED] {stem}: {exc}")

    our_extra = None
    if dtype == "er":
        html = _dispatch(src, None, 800)
        our_cards: set = set()
        for m in re.finditer(
            r'data-src="([^"]*)"[^>]*data-dst="([^"]*)"[^>]*'
            r'data-src-cardinality="([^"]*)"[^>]*data-dst-cardinality="([^"]*)"',
            html,
        ):
            our_cards.add((m.group(1), m.group(2), m.group(3), m.group(4)))
        if our_cards:
            our_extra = {"cardinalities": frozenset(our_cards)}

    result = _compare_topology(
        stem, dtype,
        our_nodes, our_edges, our_labels,
        ref_nodes, ref_edges, ref_labels,
        our_extra=our_extra,
        ref_extra=ref_extra,
    )

    _assert_no_checks_run_regression([result])

    if result.status == OracleStatus.PASS:
        return
    if result.status == OracleStatus.FAIL:
        pytest.fail(f"{stem}:\n" + "\n".join(f"  {n}" for n in result.diagnostics))
    pytest.skip(
        f"[{result.status.value.upper()}] {stem}: "
        + ("; ".join(result.diagnostics) if result.diagnostics else "no detail")
    )


# ═════════════════════════════════════════════════════════════════════════════
# Unit tests
# ═════════════════════════════════════════════════════════════════════════════

# T1

def test_oracle_result_pass_requires_nonzero_checks() -> None:
    with pytest.raises(ValueError, match="PASS requires at least one check"):
        OracleResult(status=OracleStatus.PASS, checks=(), fixture_stem="x")


def test_oracle_result_unvalidated_on_zero_checks() -> None:
    r = _make_result("x", OracleStatus.UNVALIDATED, 0)
    assert len(r.checks) == 0
    assert r.status == OracleStatus.UNVALIDATED


def test_oracle_status_values_exhaustive() -> None:
    assert {s.name for s in OracleStatus} == {
        "PASS", "FAIL", "EXTRACTOR_GAP", "UNSUPPORTED_REFERENCE_FEATURE", "UNVALIDATED"
    }


# T3

def test_manifest_all_differential_fixtures_declared() -> None:
    missing = [f.stem for f in _DIFF_FIXTURES if f.stem not in _FIXTURE_MINIMUMS]
    assert not missing, f"Missing _FIXTURE_MINIMUMS entries for: {missing}"


def test_manifest_missing_entry_raises() -> None:
    with pytest.raises(ManifestError):
        _get_fixture_minimums("nonexistent-fixture-stem")


def test_manifest_minimum_below_actual_yields_extractor_gap() -> None:
    result = _compare_topology(
        "flowchart-diamond-branch", "flowchart",
        frozenset(["A", "B", "C"]), frozenset(), frozenset(),
        frozenset(["A", "B", "C"]), frozenset(), frozenset(),
        _minimums=FixtureMinimums(min_entities=10),
    )
    assert result.status == OracleStatus.EXTRACTOR_GAP


# T4

def test_arrow_type_distinguishes_relations() -> None:
    assert _relation_key("A", "B", "", "arrow") != _relation_key("A", "B", "", "cross")


def test_arrow_none_vs_value_caught() -> None:
    assert _relation_key("A", "B", "", None) != _relation_key("A", "B", "", "arrow")


# T5

def test_er_cardinality_mismatch_yields_fail() -> None:
    result = _compare_topology(
        "er-basic", "er",
        frozenset(["A", "B"]), frozenset(), frozenset(),
        frozenset(["A", "B"]), frozenset(), frozenset(),
        our_extra={"cardinalities": frozenset([("A", "B", "one", "zero_or_one")])},
        ref_extra={"cardinalities": frozenset([("A", "B", "one", "many")])},
    )
    assert result.status == OracleStatus.FAIL


def test_er_cardinality_match_passes() -> None:
    result = _compare_topology(
        "er-basic", "er",
        frozenset(["A", "B"]), frozenset(), frozenset(),
        frozenset(["A", "B"]), frozenset(), frozenset(),
        our_extra={"cardinalities": frozenset([("A", "B", "one", "many")])},
        ref_extra={"cardinalities": frozenset([("A", "B", "one", "many")])},
    )
    assert result.status != OracleStatus.FAIL


# T6

def test_proxy_node_not_missing_entity_error() -> None:
    result = _compare_topology(
        "flowchart-diamond-branch", "flowchart",
        frozenset(["A", "B", "_sm_start_"]), frozenset(), frozenset(),
        frozenset(["A", "B"]), frozenset(), frozenset(),
    )
    assert result.status == OracleStatus.PASS


def test_real_node_still_missing_error() -> None:
    result = _compare_topology(
        "flowchart-diamond-branch", "flowchart",
        frozenset(["A"]), frozenset(), frozenset(),
        frozenset(["A", "B"]), frozenset(), frozenset(),
    )
    assert result.status == OracleStatus.FAIL
    assert any("missing nodes" in n for n in result.diagnostics)


# T2

def test_fail_when_ref_has_entities_our_empty() -> None:
    # AC4: reference has entities, native side empty → FAIL (our renderer failed)
    result = _compare_topology(
        "flowchart-diamond-branch", "flowchart",
        frozenset(), frozenset(), frozenset(),
        frozenset(["A", "B"]), frozenset(), frozenset(),
    )
    assert result.status == OracleStatus.FAIL


def test_extractor_gap_when_our_has_entities_ref_empty() -> None:
    result = _compare_topology(
        "flowchart-diamond-branch", "flowchart",
        frozenset(["A", "B"]), frozenset(), frozenset(),
        frozenset(), frozenset(), frozenset(),
        _minimums=FixtureMinimums(min_entities=0),
    )
    assert result.status == OracleStatus.EXTRACTOR_GAP


def test_extractor_gap_when_both_empty_min_declared() -> None:
    result = _compare_topology(
        "flowchart-diamond-branch", "flowchart",
        frozenset(), frozenset(), frozenset(),
        frozenset(), frozenset(), frozenset(),
        _minimums=FixtureMinimums(min_entities=2),
    )
    assert result.status == OracleStatus.EXTRACTOR_GAP


def test_pass_allowed_when_both_empty_min_zero() -> None:
    result = _compare_topology(
        "flowchart-diamond-branch", "flowchart",
        frozenset(), frozenset(), frozenset(),
        frozenset(), frozenset(), frozenset(),
        _minimums=FixtureMinimums(min_entities=0),
    )
    assert result.status != OracleStatus.EXTRACTOR_GAP


# T7

def test_mm_flowchart_extracts_markers() -> None:
    svg = (
        '<g id="flowchart-A-0"></g>'
        '<g id="flowchart-B-1"></g>'
        '<path id="L_A_B_0" marker-end="url(#flowchart-cross-end-abc)"></path>'
    )
    _, _, _, extra = _mm_flowchart(svg)
    assert ("A", "B", "cross") in extra.get("markers", frozenset())


def test_mm_flowchart_containment() -> None:
    svg = (
        '<g id="subGraph0">'
        '<g id="flowchart-A-0"></g>'
        '<g id="flowchart-B-1"></g>'
        '</g>'
    )
    _, _, _, extra = _mm_flowchart(svg)
    containment = extra.get("containment", frozenset())
    assert ("subGraph0", "A") in containment
    assert ("subGraph0", "B") in containment


def test_mm_er_cardinalities() -> None:
    svg = (
        '<g id="entity-Customer-0"></g>'
        '<g id="entity-Order-1"></g>'
        '<path id="er-Customer-Order-0"></path>'
        '<text class="er cardinality">one</text>'
        '<text class="er cardinality">many</text>'
    )
    _, _, _, extra = _mm_er(svg)
    assert ("Customer", "Order", "one", "many") in extra.get("cardinalities", frozenset())


def test_mm_edge_style_extracted() -> None:
    svg = (
        '<path id="L_A_B_0" stroke-dasharray="3,3" d="M0 0"></path>'
        '<path id="L_C_D_0" d="M0 0"></path>'
    )
    _, _, _, extra = _mm_flowchart(svg)
    edge_styles = extra.get("edge_styles", frozenset())
    assert ("A", "B", "dashed") in edge_styles
    assert ("C", "D", "solid") in edge_styles


# T8

def test_ci_gate_fails_on_zero_regression() -> None:
    original = dict(_CHECKS_RUN_BASELINE)
    _CHECKS_RUN_BASELINE["flowchart-diamond-branch"] = 5
    try:
        result = _make_result("flowchart-diamond-branch", OracleStatus.UNVALIDATED, 0)
        with pytest.raises(AssertionError, match="regressed to 0"):
            _assert_no_checks_run_regression([result])
    finally:
        _CHECKS_RUN_BASELINE.clear()
        _CHECKS_RUN_BASELINE.update(original)


def test_ci_gate_passes_on_nonzero() -> None:
    original = dict(_CHECKS_RUN_BASELINE)
    _CHECKS_RUN_BASELINE["flowchart-diamond-branch"] = 5
    try:
        result = _make_result("flowchart-diamond-branch", OracleStatus.PASS, 3)
        _assert_no_checks_run_regression([result])
    finally:
        _CHECKS_RUN_BASELINE.clear()
        _CHECKS_RUN_BASELINE.update(original)


def test_ci_gate_new_fixture_exempt() -> None:
    result = _make_result("brand-new-fixture", OracleStatus.UNVALIDATED, 0)
    _assert_no_checks_run_regression([result])


# ═════════════════════════════════════════════════════════════════════════════
# Regression tests
# ═════════════════════════════════════════════════════════════════════════════

class TestOracleRegressions:
    """Regression guard: pathological cases that must never silently produce PASS."""

    # oracle_contract type tests

    def test_oracle_status_vocabulary(self) -> None:
        assert {s.name for s in OracleStatus} == {
            "PASS", "FAIL", "EXTRACTOR_GAP", "UNSUPPORTED_REFERENCE_FEATURE", "UNVALIDATED"
        }

    def test_oracle_result_pass_requires_checks(self) -> None:
        with pytest.raises(ValueError):
            OracleResult(status=OracleStatus.PASS, checks=())

    def test_oracle_check_fields(self) -> None:
        c = OracleCheck(name="x", passed=True, expected=1, actual=1)
        assert c.name == "x"
        assert c.passed is True
        assert c.expected == 1
        assert c.actual == 1
        assert c.diagnostic == ""

    # import-shared-status tests

    def test_geometry_compare_imports_shared_status(self) -> None:
        from tools.mermaid_fidelity.compare.geometry import OracleStatus as GeoStatus
        from tools.mermaid_fidelity.oracle_contract import OracleStatus as ContractStatus
        assert GeoStatus is ContractStatus

    def test_semantic_compare_imports_shared_status(self) -> None:
        from tools.mermaid_fidelity.compare.semantic import OracleStatus as SemStatus
        from tools.mermaid_fidelity.oracle_contract import OracleStatus as ContractStatus
        assert SemStatus is ContractStatus

    # zero-check oracle wrapper tests

    def test_geometry_oracle_none_none_unvalidated(self) -> None:
        from tools.mermaid_fidelity.compare.geometry import compare_geometry_oracle
        result = compare_geometry_oracle(None, None)
        assert result.status == OracleStatus.UNVALIDATED

    def test_semantic_oracle_none_none_unvalidated(self) -> None:
        from tools.mermaid_fidelity.compare.semantic import compare_semantic_oracle
        result = compare_semantic_oracle(None, None)
        assert result.status == OracleStatus.UNVALIDATED

    # emit_oracle_report test

    def test_emit_oracle_report_has_required_keys(self) -> None:
        from tools.mermaid_fidelity.report import emit_oracle_report
        result = OracleResult(
            status=OracleStatus.UNVALIDATED,
            fixture_stem="test-fixture",
        )
        provenance = {"source_hash": "abc123"}
        report = emit_oracle_report(result, provenance)
        required_keys = {
            "fixture", "source_hash", "status", "checks_executed", "failed_checks",
            "extractor_gaps", "unsupported_fields", "native_backend_metadata",
            "reference_version_metadata",
        }
        assert required_keys.issubset(set(report.keys()))

    # topology regression tests

    def test_regression_empty_both_sides_no_pass(self) -> None:
        result = _compare_topology(
            "flowchart-diamond-branch", "flowchart",
            frozenset(), frozenset(), frozenset(),
            frozenset(), frozenset(), frozenset(),
            _minimums=FixtureMinimums(min_entities=1),
        )
        assert result.status != OracleStatus.PASS

    def test_regression_one_sided_native_not_pass(self) -> None:
        result = _compare_topology(
            "flowchart-diamond-branch", "flowchart",
            frozenset(["A", "B"]), frozenset(), frozenset(),
            frozenset(), frozenset(), frozenset(),
            _minimums=FixtureMinimums(min_entities=0),
        )
        assert result.status != OracleStatus.PASS

    def test_regression_one_sided_ref_not_pass(self) -> None:
        result = _compare_topology(
            "flowchart-diamond-branch", "flowchart",
            frozenset(), frozenset(), frozenset(),
            frozenset(["A", "B"]), frozenset(), frozenset(),
        )
        assert result.status != OracleStatus.PASS

    def test_regression_parallel_edges_distinct(self) -> None:
        # Parallel edges with distinct labels are treated as separate comparison keys
        result = _compare_topology(
            "flowchart-parallel-links", "flowchart",
            frozenset(["A", "B"]),
            frozenset([("A", "B", "label1"), ("A", "B", "label2")]),
            frozenset(),
            frozenset(["A", "B"]),
            frozenset([("A", "B", "label1"), ("A", "B", "label2")]),
            frozenset(),
        )
        assert result.status == OracleStatus.PASS
        # Missing one parallel edge is caught as FAIL
        result2 = _compare_topology(
            "flowchart-parallel-links", "flowchart",
            frozenset(["A", "B"]),
            frozenset([("A", "B", "label1")]),
            frozenset(),
            frozenset(["A", "B"]),
            frozenset([("A", "B", "label1"), ("A", "B", "label2")]),
            frozenset(),
        )
        assert result2.status == OracleStatus.FAIL

    def test_regression_marker_difference_fails(self) -> None:
        result = _compare_topology(
            "flowchart-diamond-branch", "flowchart",
            frozenset(["A", "B"]), frozenset(), frozenset(),
            frozenset(["A", "B"]), frozenset(), frozenset(),
            our_extra={"markers": frozenset([("A", "B", "circle")])},
            ref_extra={"markers": frozenset([("A", "B", "cross")])},
        )
        assert result.status == OracleStatus.FAIL

    def test_regression_cardinality_difference_fails(self) -> None:
        result = _compare_topology(
            "er-basic", "er",
            frozenset(["A", "B"]), frozenset(), frozenset(),
            frozenset(["A", "B"]), frozenset(), frozenset(),
            our_extra={"cardinalities": frozenset([("A", "B", "one", "many")])},
            ref_extra={"cardinalities": frozenset([("A", "B", "one", "zero_or_more")])},
        )
        assert result.status == OracleStatus.FAIL

    def test_regression_containment_difference_fails(self) -> None:
        result = _compare_topology(
            "flowchart-diamond-branch", "flowchart",
            frozenset(["A", "B"]), frozenset(), frozenset(),
            frozenset(["A", "B"]), frozenset(), frozenset(),
            our_extra={"containment": frozenset()},
            ref_extra={"containment": frozenset([("subGraph0", "A")])},
        )
        assert result.status == OracleStatus.FAIL
