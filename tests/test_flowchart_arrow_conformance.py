"""Flowchart Arrow Style Conformance — item 4 acceptance harness.

Proves that the ``flowchart-arrows-defs`` fixture's edge tokens retain their
exact style and marker semantics through parsing, ELK, the Python fallback,
HTML painting, and SVG painting (spec docs/specs/flowchart-arrow-style-conformance).

The fixture:

    flowchart TB
        A-->B      # normal solid + target arrow
        A==>C      # thick  solid + target arrow
        A-.->D     # dotted        + target arrow
        B-->C      # normal solid + target arrow
        C-->D      # normal solid + target arrow

Style is expressed by the ``edge_style`` string ("solid" | "thick" | "dotted")
plus stroke-width / stroke-dasharray in the painted output; marker ownership is
tracked *independently* by ``has_marker_end`` / ``target_marker`` so a marker
assertion can never be satisfied by a stroke-style assertion (spec AC5).

ELK-lane tests skip cleanly when elkjs / Node are absent.
"""
from __future__ import annotations

import copy
import dataclasses
import re
import sys
from pathlib import Path

import pytest

# ── import surface: put scripts/ on sys.path (matches sibling test modules) ────
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import mermaid_render as mr  # noqa: E402
from mermaid_render.layout._geometry import MarkerKind  # noqa: E402
from mermaid_render.layout._pipeline import (  # noqa: E402
    build_flowchart_layout_graph,
    parse_flowchart_semantics,
)
from mermaid_render.layout._strategies import (  # noqa: E402
    RenderOptions,
    _compile_flowchart,
)
from mermaid_render.layout.elk_adapter import (  # noqa: E402
    _find_elkjs,
    _find_node,
    _from_elk_result,
    _to_elk_json,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
STEM = "flowchart-arrows-defs"


def _src() -> str:
    return (FIXTURE_DIR / f"{STEM}.mmd").read_text()


def _elk_available() -> bool:
    try:
        return _find_elkjs() is not None and _find_node() is not None
    except Exception:  # pragma: no cover - defensive
        return False


requires_elk = pytest.mark.skipif(
    not _elk_available(), reason="elkjs/Node not available"
)

# ── Expected per-edge contract ────────────────────────────────────────────────
# edge_id -> (line_style, has_target_arrow_marker, has_source_marker)
EXPECTED: "dict[str, tuple[str, bool, bool]]" = {
    "A->B": ("solid", True, False),
    "A->C": ("thick", True, False),
    "A->D": ("dotted", True, False),
    "B->C": ("solid", True, False),
    "C->D": ("solid", True, False),
}
# Three distinct edge styles must be exercised (spec AC9 fixture contract).
DISTINCT_STYLES = {"solid", "thick", "dotted"}


# ── Structured oracle record ──────────────────────────────────────────────────

@dataclasses.dataclass
class EdgeStyleOracle:
    """One edge's style + marker facts for a single (lane, renderer) pass.

    ``style`` and marker facts come from *independent* sources so a style check
    and a marker check are never the same assertion (spec AC5). ``assertion_count``
    tallies the style and marker assertions actually executed against this
    record (spec AC6 — a PASS with zero assertions is vacuous).
    """

    edge_id: str
    line_style: str
    has_target_marker: bool
    has_source_marker: bool
    assertion_count: int = 0


def _oracle_from_layout(layout) -> "dict[str, EdgeStyleOracle]":
    """Build per-edge oracle records from a compiled FinalizedLayout.

    Marker ownership is read from ``has_marker_end`` AND ``target_marker`` — the
    two marker signals the pipeline carries — never from ``edge_style``.
    """
    recs: "dict[str, EdgeStyleOracle]" = {}
    for e in layout.routed_edges:
        recs[e.edge_id] = EdgeStyleOracle(
            edge_id=e.edge_id,
            line_style=e.edge_style,
            has_target_marker=(e.has_marker_end and e.target_marker == MarkerKind.ARROW),
            has_source_marker=e.has_marker_start,
        )
    return recs


def _assert_oracle_matches_expected(recs: "dict[str, EdgeStyleOracle]") -> int:
    """Assert every fixture edge matches EXPECTED; return total assertion count.

    Style and marker assertions are counted separately so callers can prove a
    nonzero, non-vacuous assertion count (spec AC6).
    """
    assert set(recs) == set(EXPECTED), (
        f"edge id set mismatch: {sorted(recs)} != {sorted(EXPECTED)}"
    )
    total = 0
    for eid, (style, tgt, src) in EXPECTED.items():
        rec = recs[eid]
        # AC1–AC4: line style per edge.
        assert rec.line_style == style, f"{eid}: style {rec.line_style!r} != {style!r}"
        rec.assertion_count += 1
        total += 1
        # AC5: target-arrow marker asserted independently of stroke style.
        assert rec.has_target_marker is tgt, f"{eid}: target marker {rec.has_target_marker} != {tgt}"
        assert rec.has_source_marker is src, f"{eid}: source marker {rec.has_source_marker} != {src}"
        rec.assertion_count += 2
        total += 2
    return total


def _compile(monkeypatch, *, force_python: bool):
    if force_python:
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
    else:
        monkeypatch.delenv("MERMAID_LAYOUT_ENGINE", raising=False)
    return _compile_flowchart(_src(), None, RenderOptions())


# ═══════════════════════════════════════════════════════════════════════════════
# AC1–AC6 — token normalization to style + independent marker, both lanes
# ═══════════════════════════════════════════════════════════════════════════════

def test_fallback_lane_edge_styles(monkeypatch):
    """AC1–AC5 on the Python-fallback lane; AC6 nonzero assertion count."""
    compiled = _compile(monkeypatch, force_python=True)
    assert compiled.metadata.backend == "python"
    recs = _oracle_from_layout(compiled.layout)
    count = _assert_oracle_matches_expected(recs)
    # AC6: structured records executed a nonzero style/marker assertion count.
    assert count > 0
    assert count == len(EXPECTED) * 3
    assert all(r.assertion_count == 3 for r in recs.values())
    # Fixture contract: three distinct edge styles exercised.
    assert {r.line_style for r in recs.values()} == DISTINCT_STYLES


@requires_elk
def test_elk_lane_edge_styles(monkeypatch):
    """AC1–AC5 on the ELK-required lane; AC6 nonzero assertion count."""
    compiled = _compile(monkeypatch, force_python=False)
    assert compiled.metadata.backend == "elkjs"
    recs = _oracle_from_layout(compiled.layout)
    count = _assert_oracle_matches_expected(recs)
    assert count == len(EXPECTED) * 3
    assert {r.line_style for r in recs.values()} == DISTINCT_STYLES


def test_marker_present_independently_of_stroke_style(monkeypatch):
    """AC5: all five edges own a target arrow marker, confirmed from the marker
    fields alone — asserted here without reading edge_style at all."""
    compiled = _compile(monkeypatch, force_python=True)
    n = 0
    for e in compiled.layout.routed_edges:
        assert e.has_marker_end is True
        assert e.target_marker == MarkerKind.ARROW
        assert e.has_marker_start is False
        n += 1
    assert n == 5


# ═══════════════════════════════════════════════════════════════════════════════
# AC7 — ELK and fallback lanes agree
# ═══════════════════════════════════════════════════════════════════════════════

@requires_elk
def test_elk_and_fallback_agree(monkeypatch):
    """AC7: ELK-required and Python-fallback lanes agree on style + marker."""
    elk = _oracle_from_layout(_compile(monkeypatch, force_python=False).layout)
    fb = _oracle_from_layout(_compile(monkeypatch, force_python=True).layout)
    assert set(elk) == set(fb) == set(EXPECTED)
    for eid in EXPECTED:
        a, b = elk[eid], fb[eid]
        assert a.line_style == b.line_style, f"{eid}: style differs {a.line_style} vs {b.line_style}"
        assert a.has_target_marker == b.has_target_marker, eid
        assert a.has_source_marker == b.has_source_marker, eid


# ═══════════════════════════════════════════════════════════════════════════════
# AC8 — to_html and to_svg agree on style + marker
# ═══════════════════════════════════════════════════════════════════════════════

_PATH_RE = re.compile(r"<path\b[^>]*\bdata-relation-id=\"([^\"]+)\"[^>]*?/?>")


def _rendered_edge_styles(out: str) -> "dict[str, tuple[str, bool]]":
    """Extract normalized (line_style, has_target_marker) per relation-id.

    Style is derived from the painted stroke, not any data-* attribute, so HTML
    and SVG are compared on the same physical signals:
      - dotted  → a stroke-dasharray is present
      - thick   → stroke-width > 1.5 (HTML uses 2, native SVG uses 3)
      - solid   → otherwise
    Marker ownership is the presence of a marker-end reference.
    """
    result: "dict[str, tuple[str, bool]]" = {}
    for m in _PATH_RE.finditer(out):
        tag = m.group(0)
        rid = m.group(1)
        has_marker = 'marker-end="url(#' in tag
        if "stroke-dasharray=" in tag:
            style = "dotted"
        else:
            sw_m = re.search(r'stroke-width="([\d.]+)"', tag)
            sw = float(sw_m.group(1)) if sw_m else 1.5
            style = "thick" if sw > 1.5 else "solid"
        result[rid] = (style, has_marker)
    return result


def _rid_to_edge_id(rid: str) -> str:
    """Relation-id 'A__B__0' → edge_id 'A->B' (first fixture edge per pair)."""
    parts = rid.split("__")
    return f"{parts[0]}->{parts[1]}"


@pytest.mark.parametrize("faithful", [True, False])
def test_html_svg_agree_on_style_and_marker(faithful):
    """AC8: to_html and to_svg agree on style + marker for all five edges,
    and both match the EXPECTED contract."""
    html = _rendered_edge_styles(mr.to_html(_src(), faithful=faithful))
    svg = _rendered_edge_styles(mr.to_svg(_src(), faithful=faithful))
    assert len(html) == 5, f"expected 5 HTML edges, got {sorted(html)}"
    assert len(svg) == 5, f"expected 5 SVG edges, got {sorted(svg)}"
    assert set(html) == set(svg), "relation-id sets differ between HTML and SVG"
    for rid in html:
        assert html[rid] == svg[rid], f"{rid}: HTML {html[rid]} != SVG {svg[rid]}"
        eid = _rid_to_edge_id(rid)
        exp_style, exp_marker, _ = EXPECTED[eid]
        assert html[rid] == (exp_style, exp_marker), f"{rid}: {html[rid]} != expected {(exp_style, exp_marker)}"


# ═══════════════════════════════════════════════════════════════════════════════
# AC9 — faithful mode adds no legend, no semantic labels, no style-derived color
# ═══════════════════════════════════════════════════════════════════════════════

# Colors the editorial palette derives from line style; forbidden on faithful edges.
_SEMANTIC_COLOR_TOKENS = ("accent-1", "accent-4", "edge-strong", "amber", "#60a5fa", "#E8924A")
_SEMANTIC_LABEL_WORDS = ("synchronous", "asynchronous", "optional", "critical")

_EDGE_PATH_RE = re.compile(r"<path\b[^>]*\bdata-relation-id=\"[^\"]+\"[^>]*?/?>")
_ARROW_MARKER_RE = re.compile(r'<marker id="arrow-[^"]*".*?</marker>', re.DOTALL)


@pytest.mark.parametrize("api", ["to_html", "to_svg"])
def test_faithful_mode_no_legend(api):
    """AC9: faithful output carries no legend and no semantic edge labels."""
    out = getattr(mr, api)(_src(), faithful=True)
    assert "legend" not in out.lower(), f"{api}: faithful output contains a legend"
    low = out.lower()
    for word in _SEMANTIC_LABEL_WORDS:
        assert word not in low, f"{api}: faithful output labels an edge {word!r}"


@pytest.mark.parametrize("api", ["to_html", "to_svg"])
def test_faithful_mode_no_semantic_edge_color(api):
    """AC9: no edge stroke or arrowhead marker derives a color from line style."""
    out = getattr(mr, api)(_src(), faithful=True)
    for tag in _EDGE_PATH_RE.findall(out):
        for tok in _SEMANTIC_COLOR_TOKENS:
            assert tok not in tag, f"{api}: edge path carries semantic color {tok!r}: {tag[:120]}"
    for marker in _ARROW_MARKER_RE.findall(out):
        for tok in _SEMANTIC_COLOR_TOKENS:
            assert tok not in marker, f"{api}: arrow marker carries semantic color {tok!r}"


def test_editorial_mode_allows_style_accent():
    """AC9 companion (plan Task 5): editorial mode is strictly less strict —
    the thick and dotted edges DO carry the editorial accent palette, proving
    the faithful guard suppresses a real behavior rather than a no-op."""
    styles = _EDGE_PATH_RE.findall(mr.to_html(_src(), faithful=False))
    joined = "".join(styles)
    assert any(tok in joined for tok in _SEMANTIC_COLOR_TOKENS), (
        "editorial mode should still paint style-derived accents on ==> / -.-> edges"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AC10 — stable edge_id survives ELK serialization + deserialization
# ═══════════════════════════════════════════════════════════════════════════════

def _echo_elk_output(elk_json: dict) -> dict:
    """Simulate an ELK result: echo the serialized graph, adding a minimal route
    section (startPoint/endPoint) to every edge exactly as elkjs would.

    This exercises the pure-Python serialize (_to_elk_json) → deserialize
    (_from_elk_result) round-trip without requiring the Node subprocess.
    """
    out = copy.deepcopy(elk_json)

    def _visit(node: dict) -> None:
        for e in node.get("edges", []):
            e["sections"] = [{
                "startPoint": {"x": 0.0, "y": 0.0},
                "endPoint": {"x": 10.0, "y": 10.0},
            }]
        for child in node.get("children", []):
            _visit(child)

    _visit(out)
    return out


def test_edge_id_survives_elk_roundtrip():
    """AC10: every edge_id persists through ELK JSON serialization and
    deserialization, and style is re-associated by that surviving id."""
    semantics = parse_flowchart_semantics(_src())
    graph = build_flowchart_layout_graph(semantics)
    graph_ids = {e.id for e in graph.edges}
    assert graph_ids == set(EXPECTED)

    elk_json = _to_elk_json(graph)
    finalized = _from_elk_result(_echo_elk_output(elk_json), graph)

    routed_ids = {e.edge_id for e in finalized.routed_edges}
    assert routed_ids == graph_ids, f"edge ids lost in round-trip: {routed_ids} != {graph_ids}"

    # Style survives too, keyed on the surviving id (not the src/dst pair).
    style_by_id = {e.edge_id: e.edge_style for e in finalized.routed_edges}
    for eid, (style, _, _) in EXPECTED.items():
        assert style_by_id[eid] == style, f"{eid}: style {style_by_id[eid]!r} != {style!r} after round-trip"


def test_edge_id_stable_unique_not_src_dst_pair():
    """AC10 / Never: edges are not identified by (source, destination) alone —
    duplicate A-->B relations receive distinct, unique edge_ids."""
    dup_src = "flowchart TB\n    A-->B\n    A-->B\n    A-->C\n"
    semantics = parse_flowchart_semantics(dup_src)
    graph = build_flowchart_layout_graph(semantics)
    ids = [e.id for e in graph.edges]
    assert len(ids) == len(set(ids)) == 3, f"duplicate (src,dst) collapsed edge ids: {ids}"
    # The two A->B relations get distinct ids despite an identical pair.
    ab = [i for i in ids if i.startswith("A->B")]
    assert len(ab) == 2 and len(set(ab)) == 2, f"A->B duplicate not disambiguated: {ab}"
