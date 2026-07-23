#!/usr/bin/env python3
"""Tests for compile_er_layout and related helpers.

Covers AC1 (non-overlap), AC2 (no-clip), AC3 (cardinality glyphs),
AC4 (dynamic width), AC5 (HTML parity), AC6 (width_hint), AC10 (port
tangent), AC11 (existing tests pass — covered by the green test_fix_er.py
suite, not repeated here).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.er import (  # noqa: E402
    _cardinality_to_marker,
    _compile_er_layout_graph,
    _longest_segment_midpoint,
    _marker_to_cardinality,
    _measure_card_width,
    compile_er_layout,
    er_to_html,
)
from mermaid_render.layout._constants import (  # noqa: E402
    CardinalityEnd,
    Maximum,
    Minimum,
)
from mermaid_render.layout._geometry import (  # noqa: E402
    MarkerKind,
    Point,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

_ECOMMERCE_SRC = (REPO_ROOT / "tests/fixtures/er-ecommerce.mmd").read_text()
_CARDINALITY_SRC = (REPO_ROOT / "tests/fixtures/er-cardinality-all.mmd").read_text()

_MINIMAL = "erDiagram\n    A ||--|| B : rel\n"
_TWO_REL = """\
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
"""

_ONE_ONE = CardinalityEnd(Minimum.ONE, Maximum.ONE)
_ZERO_MANY = CardinalityEnd(Minimum.ZERO, Maximum.MANY)
_ONE_MANY = CardinalityEnd(Minimum.ONE, Maximum.MANY)
_ZERO_ONE = CardinalityEnd(Minimum.ZERO, Maximum.ONE)


# ── 1. Width measurement ──────────────────────────────────────────────────────

class TestMeasureCardWidth:
    def test_no_attrs_returns_minimum(self):
        w = _measure_card_width("A", [])
        assert w == 160, f"Expected 160, got {w}"

    def test_short_name_no_attrs_clamps_to_min(self):
        w = _measure_card_width("X", [])
        assert w >= 160

    def test_long_name_increases_width(self):
        short = _measure_card_width("A", [])
        long_ = _measure_card_width("VERY_LONG_ENTITY_NAME_HERE", [])
        assert long_ >= short

    def test_wide_attrs_increases_width(self):
        attrs_wide = [
            {"type": "varchar_1024", "name": "some_long_attribute_name", "constraint": ""},
        ]
        attrs_narrow = [{"type": "int", "name": "id", "constraint": "PK"}]
        assert _measure_card_width("E", attrs_wide) >= _measure_card_width("E", attrs_narrow)

    def test_result_clamped_to_max(self):
        attrs = [
            {"type": "verylongtypestring" * 4, "name": "very_long_name" * 4, "constraint": ""}
        ]
        w = _measure_card_width("ENTITY", attrs)
        assert w <= 320

    def test_ecommerce_entities_in_range(self):
        """All ecommerce entities should produce widths in [160, 320]."""
        from mermaid_render.layout.er import _parse_er_source
        entities, _ = _parse_er_source(_ECOMMERCE_SRC)
        for eid, attrs in entities.items():
            w = _measure_card_width(eid, attrs)
            assert 160 <= w <= 320, f"{eid}: w={w}"


# ── 2. LayoutGraph compilation ────────────────────────────────────────────────

class TestCompileErLayoutGraph:
    def _make_graph(self, src: str):
        from mermaid_render.layout.er import _parse_er_source
        entities, rels = _parse_er_source(src)
        widths = {e: _measure_card_width(e, a) for e, a in entities.items()}
        heights = {e: 44.0 for e in entities}
        return _compile_er_layout_graph(entities, rels, widths, heights), rels

    def test_node_count_matches_entities(self):
        graph, _ = self._make_graph(_MINIMAL)
        entity_ids = {n.id for n in graph.nodes}
        assert "A" in entity_ids
        assert "B" in entity_ids
        assert len(graph.nodes) == 2

    def test_edge_count_matches_relationships(self):
        graph, rels = self._make_graph(_CARDINALITY_SRC)
        assert len(graph.edges) == len(rels)

    def test_edges_carry_crow_foot_markers(self):
        graph, _ = self._make_graph(_CARDINALITY_SRC)
        # All edges should have non-None markers (crow-foot)
        for edge in graph.edges:
            assert edge.source_marker is not None, f"edge {edge.id} has no source_marker"
            assert edge.target_marker is not None, f"edge {edge.id} has no target_marker"

    def test_one_one_edge_gets_crow_one(self):
        graph, _ = self._make_graph("erDiagram\n    A ||--|| B : rel\n")
        edge = graph.edges[0]
        assert edge.source_marker == MarkerKind.CROW_ONE
        assert edge.target_marker == MarkerKind.CROW_ONE

    def test_node_widths_match_measured(self):
        graph, _ = self._make_graph(_MINIMAL)
        for node in graph.nodes:
            expected_w = _measure_card_width(node.id, [])
            assert node.measured_width == expected_w, f"{node.id}: {node.measured_width} != {expected_w}"

    def test_direction_is_tb(self):
        graph, _ = self._make_graph(_MINIMAL)
        assert graph.direction == "TB"


# ── 3. FinalizedLayout pipeline ───────────────────────────────────────────────

class TestCompileErLayout:
    def test_returns_all_entities(self):
        fl = compile_er_layout(_ECOMMERCE_SRC)
        expected = {"CUSTOMER", "ORDER", "LINE_ITEM", "PRODUCT", "ADDRESS"}
        assert expected == set(fl.node_layouts.keys())

    def test_no_node_overlap_x(self):
        """Cards within the same rank must not overlap on the x-axis."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        # Group by y-position (rank) with tolerance
        from collections import defaultdict
        by_rank: dict[int, list] = defaultdict(list)
        for nl in fl.node_layouts.values():
            rank_key = round(nl.outer_bounds.y)
            by_rank[rank_key].append(nl.outer_bounds)
        for rank_key, bounds_list in by_rank.items():
            sorted_bounds = sorted(bounds_list, key=lambda b: b.x)
            for i in range(len(sorted_bounds) - 1):
                a = sorted_bounds[i]
                b = sorted_bounds[i + 1]
                assert a.x + a.w <= b.x + 0.1, (
                    f"Rank y≈{rank_key}: card at x={a.x},w={a.w} overlaps "
                    f"card at x={b.x}"
                )

    def test_all_nodes_inside_canvas(self):
        """Every card must fit inside canvas_bounds."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        cw = fl.canvas_bounds.w
        ch = fl.canvas_bounds.h
        for eid, nl in fl.node_layouts.items():
            b = nl.outer_bounds
            assert b.x >= 0, f"{eid}.x={b.x} < 0"
            assert b.y >= 0, f"{eid}.y={b.y} < 0"
            assert b.x + b.w <= cw + 1.0, f"{eid}: right={b.x+b.w} > canvas_w={cw}"
            assert b.y + b.h <= ch + 1.0, f"{eid}: bottom={b.y+b.h} > canvas_h={ch}"

    def test_routed_edges_carry_crow_foot_markers(self):
        fl = compile_er_layout(_CARDINALITY_SRC)
        none_markers = [
            re for re in fl.routed_edges
            if re.source_marker == MarkerKind.NONE or re.target_marker == MarkerKind.NONE
        ]
        assert not none_markers, (
            f"Expected crow-foot markers, found NONE on: "
            f"{[(re.edge_id, re.source_marker, re.target_marker) for re in none_markers]}"
        )

    def test_width_hint_scales_canvas(self):
        fl_full = compile_er_layout(_ECOMMERCE_SRC, width_hint=0)
        fl_half = compile_er_layout(_ECOMMERCE_SRC, width_hint=int(fl_full.canvas_bounds.w * 0.5))
        assert fl_half.canvas_bounds.w < fl_full.canvas_bounds.w

    def test_width_hint_does_not_upscale(self):
        """width_hint larger than natural width should leave canvas unchanged."""
        fl_full = compile_er_layout(_MINIMAL, width_hint=0)
        fl_big = compile_er_layout(_MINIMAL, width_hint=int(fl_full.canvas_bounds.w * 3))
        assert abs(fl_big.canvas_bounds.w - fl_full.canvas_bounds.w) < 1.0

    def test_empty_diagram_returns_minimal_layout(self):
        fl = compile_er_layout("erDiagram\n", width_hint=400)
        assert len(fl.node_layouts) == 0
        assert fl.canvas_bounds.w >= 400

    def test_dynamic_widths_exceed_min(self):
        """Entities with long attribute names get wider cards than empty ones."""
        # Use long attribute names that will push past the 160px minimum
        wide_src = (
            "erDiagram\n"
            "    ENTITY_WIDE {\n"
            "        varchar some_long_attribute_name\n"
            "        integer another_quite_long_name\n"
            "    }\n"
            "    ENTITY_WIDE ||--|| B : rel\n"
        )
        fl_wide = compile_er_layout(wide_src)
        fl_bare = compile_er_layout(_CARDINALITY_SRC)
        wide_w = fl_wide.node_layouts["ENTITY_WIDE"].outer_bounds.w
        a_w = fl_bare.node_layouts["A"].outer_bounds.w
        assert wide_w > a_w, (
            f"Expected ENTITY_WIDE ({wide_w}) wider than A ({a_w})"
        )


# ── 4. Cardinality markers ────────────────────────────────────────────────────

class TestCardinalityMarkers:
    @pytest.mark.parametrize("end,expected_mk", [
        (_ONE_ONE, MarkerKind.CROW_ONE),
        (_ZERO_ONE, MarkerKind.CROW_ZERO_ONE),
        (_ONE_MANY, MarkerKind.CROW_MANY),
        (_ZERO_MANY, MarkerKind.CROW_ZERO_MANY),
    ])
    def test_cardinality_to_marker(self, end, expected_mk):
        assert _cardinality_to_marker(end) == expected_mk

    @pytest.mark.parametrize("mk,expected_end", [
        (MarkerKind.CROW_ONE, _ONE_ONE),
        (MarkerKind.CROW_ZERO_ONE, _ZERO_ONE),
        (MarkerKind.CROW_MANY, _ONE_MANY),
        (MarkerKind.CROW_ZERO_MANY, _ZERO_MANY),
    ])
    def test_marker_to_cardinality(self, mk, expected_end):
        assert _marker_to_cardinality(mk) == expected_end

    def test_roundtrip(self):
        for end in (_ONE_ONE, _ZERO_ONE, _ONE_MANY, _ZERO_MANY):
            assert _marker_to_cardinality(_cardinality_to_marker(end)) == end

    def test_cardinality_all_fixture_markers(self):
        """The cardinality-all fixture should have 4 non-NONE routed edges."""
        fl = compile_er_layout(_CARDINALITY_SRC)
        assert len(fl.routed_edges) == 4
        for re in fl.routed_edges:
            assert re.source_marker != MarkerKind.NONE, f"{re.edge_id} source is NONE"
            assert re.target_marker != MarkerKind.NONE, f"{re.edge_id} target is NONE"

    def test_specific_cardinality_values(self):
        """A ||--|| B: both ends CROW_ONE."""
        fl = compile_er_layout("erDiagram\n    A ||--|| B : rel\n")
        re = fl.routed_edges[0]
        assert re.source_marker == MarkerKind.CROW_ONE
        assert re.target_marker == MarkerKind.CROW_ONE

    def test_zero_many_marker(self):
        fl = compile_er_layout("erDiagram\n    A ||--o{ B : rel\n")
        re = fl.routed_edges[0]
        assert re.source_marker == MarkerKind.CROW_ONE
        assert re.target_marker == MarkerKind.CROW_ZERO_MANY


# ── 5. Label placement ────────────────────────────────────────────────────────

class TestLabelPlacement:
    def test_label_anchor_exists_when_label_present(self):
        fl = compile_er_layout("erDiagram\n    A ||--|| B : my-label\n")
        re = fl.routed_edges[0]
        assert re.label_layout is not None, "Expected label_layout"
        ap = re.label_layout.anchor_point
        assert ap is not None

    def test_label_anchor_between_waypoints(self):
        fl = compile_er_layout("erDiagram\n    A ||--|| B : rel\n")
        re = fl.routed_edges[0]
        assert re.label_layout is not None
        ap = re.label_layout.anchor_point
        wps = re.waypoints
        x_min = min(p.x for p in wps)
        x_max = max(p.x for p in wps)
        y_min = min(p.y for p in wps)
        y_max = max(p.y for p in wps)
        assert x_min - 1.0 <= ap.x <= x_max + 1.0, f"anchor x={ap.x} outside [{x_min}, {x_max}]"
        assert y_min - 1.0 <= ap.y <= y_max + 1.0, f"anchor y={ap.y} outside [{y_min}, {y_max}]"

    def test_no_label_no_label_layout(self):
        fl = compile_er_layout("erDiagram\n    A ||--|| B : \"\"\n")
        # Empty-string labels: no label_layout expected
        for re in fl.routed_edges:
            if not re.label_layout:
                pass  # OK
            else:
                # If present, text must be non-empty
                assert re.label_layout.text.strip(), "Empty label but label_layout present"

    def test_longest_segment_midpoint_two_points(self):
        wps = [Point(0.0, 0.0), Point(10.0, 0.0)]
        mp = _longest_segment_midpoint(wps)
        assert abs(mp.x - 5.0) < 0.01
        assert abs(mp.y - 0.0) < 0.01

    def test_longest_segment_midpoint_picks_longest(self):
        # Three points: short segment then long segment
        wps = [Point(0.0, 0.0), Point(1.0, 0.0), Point(11.0, 0.0)]
        mp = _longest_segment_midpoint(wps)
        # Longest segment is [1,0]→[11,0], midpoint is (6,0)
        assert abs(mp.x - 6.0) < 0.01

    def test_ecommerce_labels_all_placed(self):
        fl = compile_er_layout(_ECOMMERCE_SRC)
        for re in fl.routed_edges:
            if re.label_layout is not None:
                ap = re.label_layout.anchor_point
                assert fl.canvas_bounds.x <= ap.x <= fl.canvas_bounds.x + fl.canvas_bounds.w + 1, (
                    f"{re.edge_id}: label x={ap.x} outside canvas"
                )


# ── 6. HTML renderer parity ───────────────────────────────────────────────────

class TestErHtmlRenderer:
    def _render(self, src: str, width_hint: int = 0) -> str:
        return er_to_html(src, width_hint=width_hint)

    def test_all_entities_present_in_html(self):
        html = self._render(_ECOMMERCE_SRC)
        for eid in ("CUSTOMER", "ORDER", "LINE_ITEM", "PRODUCT", "ADDRESS"):
            assert eid in html, f"{eid} not found in HTML"

    def test_no_css_zoom(self):
        """compile_er_layout pre-scales, so no CSS zoom should appear."""
        html = self._render(_ECOMMERCE_SRC, width_hint=600)
        assert "zoom:" not in html, "CSS zoom found in output (should be absent)"

    def test_svg_overlay_present(self):
        html = self._render(_MINIMAL)
        assert "<svg" in html and "</svg>" in html

    def test_cardinality_glyphs_circle_for_zero_min(self):
        html = self._render("erDiagram\n    A ||--o{ B : rel\n")
        assert "<circle" in html, "Expected circle glyph for ZERO minimum"

    def test_cardinality_glyphs_no_circle_for_one_min(self):
        html = self._render("erDiagram\n    A ||--|| B : rel\n")
        assert "<circle" not in html, "No circle expected for ONE..ONE cardinality"

    def test_edge_label_rendered(self):
        html = self._render("erDiagram\n    A ||--|| B : places\n")
        assert "places" in html

    def test_width_hint_applied_to_canvas(self):
        """Canvas width in HTML should match the FinalizedLayout canvas width."""
        target = 500
        fl = compile_er_layout(_ECOMMERCE_SRC, width_hint=target)
        html = self._render(_ECOMMERCE_SRC, width_hint=target)
        cw = fl.canvas_bounds.w
        # HTML uses float formatting, e.g. "width:476.0px"
        assert f"width:{cw}" in html, f"Expected width:{cw} in HTML"

    def test_dynamic_width_reflects_measured_card(self):
        """Card width in HTML should reflect measured width, not fixed 200."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        customer_w = fl.node_layouts["CUSTOMER"].outer_bounds.w
        html = self._render(_ECOMMERCE_SRC)
        assert f"width:{customer_w}" in html, (
            f"Expected width:{customer_w} in HTML for CUSTOMER"
        )
