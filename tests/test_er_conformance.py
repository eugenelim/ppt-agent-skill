#!/usr/bin/env python3
"""Conformance tests for compile_er_layout — spec mermaid-er-compiler-consolidation-and-routing.

Verifies acceptance criteria AC1–AC9 from
docs/specs/mermaid-er-compiler-consolidation-and-routing/spec.md.

AC5 (cardinality semantics) is fully covered by test_er_cardinality.py and
test_er_finalized_layout.py; it is not repeated here.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.er import (  # noqa: E402
    compile_er,
    compile_er_layout,
    er_to_html,
    layout_er_scene,
    _glyph_reserve,
)
from mermaid_render.layout._constants import CardinalityEnd, Maximum, Minimum  # noqa: E402

_ECOMMERCE_SRC = (REPO_ROOT / "tests/fixtures/er-ecommerce.mmd").read_text()
_MINIMAL = "erDiagram\n    A ||--|| B : rel\n"
_LABELED = "erDiagram\n    A ||--|| B : places\n"
_THREE_ENTITY = """\
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    CUSTOMER }o--o{ ADDRESS : lives_at
"""
_WITH_ATTRS = """\
erDiagram
    PERSON {
        varchar name
        int age
    }
    PERSON ||--|| ADDRESS : lives_at
"""
_TRIANGLE = """\
erDiagram
    A ||--|| B : ab
    B ||--|| C : bc
    A ||--|| C : ac
"""

# Detect ELK availability from diagnostics (no elkjs → warnings contain "elk-unavailable")
_fl_probe = compile_er_layout(_MINIMAL)
_ELK_AVAILABLE = not any("elk-unavailable" in w for w in _fl_probe.diagnostics.warnings)
del _fl_probe

_NEEDS_ELK = pytest.mark.skipif(
    not _ELK_AVAILABLE,
    reason="ELK (elkjs) not installed; run: npm ci --prefix scripts/mermaid_render/layout",
)


# ── Segment-vs-rectangle intersection helper (for AC8) ───────────────────────

def _segment_intersects_rect_interior(p1, p2, b, margin: float = 0.5) -> bool:
    """Return True if segment p1→p2 has any strictly interior overlap with rect *b*.

    *margin* px is shaved from each rect edge so boundary-touching segments
    (which are expected at entity connection points) are not flagged.
    Uses the Liang-Barsky algorithm.
    """
    x0, y0 = p1.x, p1.y
    x1, y1 = p2.x, p2.y
    sx = b.x + margin
    sy = b.y + margin
    sw = b.w - 2 * margin
    sh = b.h - 2 * margin
    if sw <= 0 or sh <= 0:
        return False
    dx = x1 - x0
    dy = y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in [(-dx, x0 - sx), (dx, sx + sw - x0), (-dy, y0 - sy), (dy, sy + sh - y0)]:
        if p == 0:
            if q < 0:
                return False
        elif p < 0:
            r = q / p
            if r > t1:
                return False
            t0 = max(t0, r)
        else:
            r = q / p
            if r < t0:
                return False
            t1 = min(t1, r)
    return t0 < t1  # strictly interior (positive-length intersection)


# ── AC1: One active ER compiler; _compile_er_legacy deleted ──────────────────

class TestAC1LegacyDeleted:
    def test_compile_er_legacy_not_in_module(self):
        """_compile_er_legacy must be absent after consolidation (AC1)."""
        import mermaid_render.layout.er as er_mod
        assert not hasattr(er_mod, "_compile_er_legacy"), (
            "_compile_er_legacy still exists in er module — delete it"
        )

    def test_compile_er_alias_still_works(self):
        """compile_er() compatibility alias must return a valid layout."""
        fl = compile_er(_MINIMAL)
        assert len(fl.node_layouts) == 2

    def test_compile_er_and_compile_er_layout_produce_equal_results(self):
        """compile_er() must delegate to compile_er_layout() (identical output)."""
        fl1 = compile_er(_MINIMAL)
        fl2 = compile_er_layout(_MINIMAL)
        assert fl1.canvas_bounds == fl2.canvas_bounds
        assert set(fl1.node_layouts.keys()) == set(fl2.node_layouts.keys())


# ── AC2: Card widths from TextMeasurer (no character-count coefficient) ───────

class TestAC2MeasuredWidths:
    def test_long_attr_name_wider_than_short(self):
        """Entity with long attribute name must produce strictly wider card (AC2)."""
        short_src = (
            "erDiagram\n    E {\n        int id\n    }\n    E ||--|| B : rel\n"
        )
        long_src = (
            "erDiagram\n    E {\n"
            "        varchar some_very_long_attribute_name_here\n"
            "    }\n    E ||--|| B : rel\n"
        )
        fl_short = compile_er_layout(short_src)
        fl_long = compile_er_layout(long_src)
        w_short = fl_short.node_layouts["E"].outer_bounds.w
        w_long = fl_long.node_layouts["E"].outer_bounds.w
        assert w_long > w_short, (
            f"Long attr name should produce strictly wider card: {w_long} vs {w_short}"
        )


# ── AC3: All visible ER text has real measured TextLayout objects ──────────────

class TestAC3RealTextLayouts:
    def test_header_text_layout_positive_width(self):
        """NodeLayout.title_layout.width must be > 0 for all entities (AC3)."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        for eid, nl in fl.node_layouts.items():
            assert nl.title_layout is not None, f"{eid}: title_layout is None"
            assert nl.title_layout.width > 0, (
                f"{eid}: title_layout.width={nl.title_layout.width}"
            )

    def test_header_text_layout_positive_height(self):
        """NodeLayout.title_layout.height must be > 0 for all entities (AC3)."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        for eid, nl in fl.node_layouts.items():
            assert nl.title_layout is not None
            assert nl.title_layout.height > 0, (
                f"{eid}: title_layout.height={nl.title_layout.height}"
            )

    def test_attribute_member_layouts_count_matches_attrs(self):
        """member_layouts must contain one TextLayout per attribute (AC3)."""
        fl = compile_er_layout(_WITH_ATTRS)
        nl = fl.node_layouts["PERSON"]
        assert len(nl.member_layouts) == 2, (
            f"Expected 2 member_layouts for PERSON, got {len(nl.member_layouts)}"
        )

    def test_attribute_text_layout_positive_dimensions(self):
        """Each attribute TextLayout must have width > 0 and height > 0 (AC3)."""
        fl = compile_er_layout(_WITH_ATTRS)
        nl = fl.node_layouts["PERSON"]
        for i, tl in enumerate(nl.member_layouts):
            assert tl.width > 0, f"PERSON member_layouts[{i}].width={tl.width}"
            assert tl.height > 0, f"PERSON member_layouts[{i}].height={tl.height}"

    def test_entity_without_attrs_has_empty_member_layouts(self):
        """Entities with no declared attributes get empty member_layouts (AC3)."""
        fl = compile_er_layout(_MINIMAL)
        for eid, nl in fl.node_layouts.items():
            assert nl.member_layouts == (), (
                f"{eid}: expected empty member_layouts, got {len(nl.member_layouts)}"
            )

    def test_label_text_layout_positive_dimensions(self):
        """Relationship label TextLayout must have width > 0 and height > 0 (AC3)."""
        fl = compile_er_layout(_LABELED)
        for re in fl.routed_edges:
            if re.label_layout is not None:
                tl = re.label_layout.layout
                assert tl.width > 0, f"{re.edge_id}: label TextLayout.width={tl.width}"
                assert tl.height > 0, f"{re.edge_id}: label TextLayout.height={tl.height}"

    def test_ecommerce_all_entities_have_member_layouts(self):
        """Each ecommerce entity's attribute count matches its member_layouts count (AC3)."""
        from mermaid_render.layout.er import _parse_er_source
        entities, _ = _parse_er_source(_ECOMMERCE_SRC)
        fl = compile_er_layout(_ECOMMERCE_SRC)
        for eid, attrs in entities.items():
            if eid not in fl.node_layouts:
                continue
            nl = fl.node_layouts[eid]
            assert len(nl.member_layouts) == len(attrs), (
                f"{eid}: expected {len(attrs)} member_layouts, got {len(nl.member_layouts)}"
            )

    def test_label_placed_on_longest_segment(self):
        """Label anchor must be on the longest segment of the visible route (AC3 / Task 4).

        Verifies that for a multi-segment route, the anchor is at the midpoint of
        the longest segment, not the first or overall midpoint.
        """
        # With a diagram where ELK produces multiple waypoints, label should be
        # on the longest segment.  Without ELK, there are 2 waypoints (one segment),
        # so the "longest" segment is trivially the only one — still passes.
        fl = compile_er_layout(_THREE_ENTITY)
        for re in fl.routed_edges:
            if re.label_layout is None:
                continue
            wps = re.waypoints
            if len(wps) < 2:
                continue
            # Recompute longest-segment midpoint
            best_i = 0
            best_len = -1.0
            for i in range(len(wps) - 1):
                dx = wps[i + 1].x - wps[i].x
                dy = wps[i + 1].y - wps[i].y
                seg = math.hypot(dx, dy)
                if seg > best_len:
                    best_len = seg
                    best_i = i
            a, b = wps[best_i], wps[best_i + 1]
            expected_x = (a.x + b.x) / 2
            expected_y = (a.y + b.y) / 2
            ap = re.label_layout.anchor_point
            assert abs(ap.x - expected_x) < 0.5 and abs(ap.y - expected_y) < 0.5, (
                f"Edge {re.edge_id}: label anchor ({ap.x:.2f},{ap.y:.2f}) not at "
                f"longest-segment midpoint ({expected_x:.2f},{expected_y:.2f})"
            )


# ── AC4: Every relationship has a stable, unique edge_id ─────────────────────

class TestAC4UniqueEdgeIds:
    def test_single_relationship_has_non_empty_edge_id(self):
        """Every relationship must carry a non-empty edge_id (AC4)."""
        fl = compile_er_layout(_MINIMAL)
        assert len(fl.routed_edges) == 1
        assert fl.routed_edges[0].edge_id != ""

    def test_multi_relationship_edge_ids_all_unique(self):
        """All edge_id values in a diagram must be distinct (AC4)."""
        fl = compile_er_layout(_THREE_ENTITY)
        edge_ids = [re.edge_id for re in fl.routed_edges]
        duplicates = [eid for eid in set(edge_ids) if edge_ids.count(eid) > 1]
        assert not duplicates, f"Duplicate edge IDs: {duplicates}"

    def test_edge_ids_stable_across_repeated_calls(self):
        """edge_id values must be deterministic (same on every call) (AC4)."""
        fl1 = compile_er_layout(_THREE_ENTITY)
        fl2 = compile_er_layout(_THREE_ENTITY)
        ids1 = sorted(re.edge_id for re in fl1.routed_edges)
        ids2 = sorted(re.edge_id for re in fl2.routed_edges)
        assert ids1 == ids2, "Edge IDs differ between calls — not stable"

    def test_ecommerce_all_edges_have_unique_ids(self):
        """Ecommerce fixture: all relationship edge_ids must be distinct (AC4)."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        edge_ids = [re.edge_id for re in fl.routed_edges]
        assert len(edge_ids) == len(set(edge_ids)), (
            f"Duplicate edge IDs in ecommerce: {edge_ids}"
        )

    def test_explicit_ports_per_relationship(self):
        """Every relationship must carry non-None src_port and dst_port with resolved side (AC4).

        PortSide.AUTO is not permitted in a finalized layout.
        """
        from mermaid_render.layout._geometry import PortSide
        fl = compile_er_layout(_ECOMMERCE_SRC)
        for re in fl.routed_edges:
            assert re.src_port is not None, f"Edge {re.edge_id}: src_port is None"
            assert re.dst_port is not None, f"Edge {re.edge_id}: dst_port is None"
            assert re.src_port.side != PortSide.AUTO, (
                f"Edge {re.edge_id}: src_port.side is AUTO (must be resolved)"
            )
            assert re.dst_port.side != PortSide.AUTO, (
                f"Edge {re.edge_id}: dst_port.side is AUTO (must be resolved)"
            )


# ── AC6: Cardinality glyph orientation follows route tangent ─────────────────

class TestAC6GlyphOrientation:
    def test_src_port_direction_is_unit_vector(self):
        """src_port.direction must be a unit vector (magnitude ≈ 1.0) (AC6)."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        for re in fl.routed_edges:
            d = re.src_port.direction
            mag = math.hypot(d.x, d.y)
            assert abs(mag - 1.0) < 0.01, (
                f"Edge {re.edge_id}: src port direction magnitude={mag:.4f}"
            )

    def test_dst_port_direction_is_unit_vector(self):
        """dst_port.direction must be a unit vector (magnitude ≈ 1.0) (AC6)."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        for re in fl.routed_edges:
            d = re.dst_port.direction
            mag = math.hypot(d.x, d.y)
            assert abs(mag - 1.0) < 0.01, (
                f"Edge {re.edge_id}: dst port direction magnitude={mag:.4f}"
            )

    def test_src_port_direction_aligns_with_waypoint_tangent(self):
        """src port direction must align with the outgoing route tangent (AC6).

        The glyph is rendered in the port direction; this verifies that the
        direction matches the route tangent within 25 degrees (cos > 0.9).
        """
        fl = compile_er_layout(_ECOMMERCE_SRC)
        for re in fl.routed_edges:
            wps = re.waypoints
            if len(wps) < 2:
                continue
            dx = wps[1].x - wps[0].x
            dy = wps[1].y - wps[0].y
            mag = math.hypot(dx, dy)
            if mag < 1e-6:
                continue
            tan_x, tan_y = dx / mag, dy / mag
            d = re.src_port.direction
            dot = tan_x * d.x + tan_y * d.y
            assert dot > 0.9, (
                f"Edge {re.edge_id}: src port direction ({d.x:.3f},{d.y:.3f}) "
                f"not aligned with waypoint tangent ({tan_x:.3f},{tan_y:.3f}), dot={dot:.3f}"
            )

    def test_src_dst_port_directions_are_opposing(self):
        """src and dst port directions must point away from each entity (AC6)."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        for re in fl.routed_edges:
            sd = re.src_port.direction
            dd = re.dst_port.direction
            dot = sd.x * dd.x + sd.y * dd.y
            assert dot < 0, (
                f"Edge {re.edge_id}: src and dst port directions are not opposing "
                f"(dot={dot:.3f}). src={sd}, dst={dd}"
            )


# ── AC7: Relationship labels do not overlap cardinality glyph areas ───────────

class TestAC7LabelNotOverlappingGlyph:
    def test_label_anchor_between_trimmed_waypoints(self):
        """Label anchor must lie between the glyph-trimmed line endpoints (AC7)."""
        fl = compile_er_layout(_LABELED)
        for re in fl.routed_edges:
            if re.label_layout is None:
                continue
            ap = re.label_layout.anchor_point
            wps = re.waypoints
            x_lo = min(p.x for p in wps) - 1.0
            x_hi = max(p.x for p in wps) + 1.0
            y_lo = min(p.y for p in wps) - 1.0
            y_hi = max(p.y for p in wps) + 1.0
            assert x_lo <= ap.x <= x_hi, (
                f"Edge {re.edge_id}: label anchor x={ap.x} outside waypoints [{x_lo}, {x_hi}]"
            )
            assert y_lo <= ap.y <= y_hi, (
                f"Edge {re.edge_id}: label anchor y={ap.y} outside waypoints [{y_lo}, {y_hi}]"
            )

    def test_label_anchor_not_at_port_position(self):
        """Label anchor must not coincide with a port (glyph) position (AC7)."""
        fl = compile_er_layout(_LABELED)
        for re in fl.routed_edges:
            if re.label_layout is None:
                continue
            ap = re.label_layout.anchor_point
            for port in (re.src_port, re.dst_port):
                pp = port.position
                dist = math.hypot(ap.x - pp.x, ap.y - pp.y)
                assert dist > 1.0, (
                    f"Edge {re.edge_id}: label anchor ({ap.x:.1f},{ap.y:.1f}) "
                    f"coincides with port at ({pp.x:.1f},{pp.y:.1f})"
                )

    def test_ecommerce_labels_within_canvas(self):
        """All label anchors must lie within the canvas bounds (AC7)."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        cb = fl.canvas_bounds
        for re in fl.routed_edges:
            if re.label_layout is None:
                continue
            ap = re.label_layout.anchor_point
            assert cb.x - 1 <= ap.x <= cb.x + cb.w + 1, (
                f"Edge {re.edge_id}: label x={ap.x} outside canvas [0, {cb.w}]"
            )
            assert cb.y - 1 <= ap.y <= cb.y + cb.h + 1, (
                f"Edge {re.edge_id}: label y={ap.y} outside canvas [0, {cb.h}]"
            )


# ── AC8: Relationships do not enter unrelated entity card interiors ───────────

class TestAC8RouteNonPenetration:
    def test_no_waypoint_strictly_inside_unrelated_entity(self):
        """No route waypoint may lie strictly inside an unrelated entity's bounding
        rectangle (AC8). A 0.5 px margin is used to exclude boundary touches.
        """
        fl = compile_er_layout(_ECOMMERCE_SRC)
        node_bounds = {eid: nl.outer_bounds for eid, nl in fl.node_layouts.items()}

        violations: list[str] = []
        for re in fl.routed_edges:
            src_id = re.src_node_id
            dst_id = re.dst_node_id
            for wp in re.waypoints:
                for eid, b in node_bounds.items():
                    if eid in (src_id, dst_id):
                        continue
                    # Strictly inside (shrink by 0.5 px to exclude boundary contact)
                    if (b.x + 0.5 < wp.x < b.x + b.w - 0.5 and
                            b.y + 0.5 < wp.y < b.y + b.h - 0.5):
                        violations.append(
                            f"Edge {re.edge_id}: waypoint ({wp.x:.1f},{wp.y:.1f}) "
                            f"inside unrelated entity '{eid}' "
                            f"({b.x:.1f},{b.y:.1f},{b.w:.1f}x{b.h:.1f})"
                        )
        assert not violations, "\n".join(violations)

    def test_three_entity_no_waypoint_penetration(self):
        """Three-entity diagram: no waypoint inside an unrelated entity (AC8)."""
        fl = compile_er_layout(_THREE_ENTITY)
        node_bounds = {eid: nl.outer_bounds for eid, nl in fl.node_layouts.items()}
        for re in fl.routed_edges:
            src_id, dst_id = re.src_node_id, re.dst_node_id
            for wp in re.waypoints:
                for eid, b in node_bounds.items():
                    if eid in (src_id, dst_id):
                        continue
                    inside = (b.x + 0.5 < wp.x < b.x + b.w - 0.5 and
                               b.y + 0.5 < wp.y < b.y + b.h - 0.5)
                    assert not inside, (
                        f"Edge {re.edge_id}: waypoint ({wp.x:.1f},{wp.y:.1f}) "
                        f"inside unrelated entity '{eid}'"
                    )

    @_NEEDS_ELK
    def test_triangle_no_segment_penetration_with_elk(self):
        """Triangle topology: no route segment may pass through an unrelated entity (AC8).

        This test requires ELK orthogonal routing, which is the mechanism that
        prevents penetration.  The Sugiyama straight-line fallback does NOT satisfy
        this criterion for triangle topologies (A→C passes through B), so the test
        is skipped when ELK is unavailable.
        """
        fl = compile_er_layout(_TRIANGLE)
        node_bounds = {eid: nl.outer_bounds for eid, nl in fl.node_layouts.items()}
        violations: list[str] = []
        for re in fl.routed_edges:
            src_id, dst_id = re.src_node_id, re.dst_node_id
            wps = re.waypoints
            for i in range(len(wps) - 1):
                p1, p2 = wps[i], wps[i + 1]
                for eid, b in node_bounds.items():
                    if eid in (src_id, dst_id):
                        continue
                    if _segment_intersects_rect_interior(p1, p2, b):
                        violations.append(
                            f"Edge {re.edge_id} segment [{i}→{i+1}] "
                            f"({p1.x:.1f},{p1.y:.1f})→({p2.x:.1f},{p2.y:.1f}) "
                            f"passes through entity '{eid}' interior "
                            f"({b.x:.1f},{b.y:.1f},{b.w:.1f}x{b.h:.1f})"
                        )
        assert not violations, "\n".join(violations)


# ── AC9: HTML and SVG consume identical finalized geometry ────────────────────

class TestAC9HtmlSvgIdentity:
    def test_html_entity_widths_match_finalized_layout(self):
        """HTML card widths must match FinalizedLayout outer_bounds.w (AC9)."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        html = er_to_html(_ECOMMERCE_SRC)
        for eid, nl in fl.node_layouts.items():
            ew = nl.outer_bounds.w
            assert f"width:{ew}" in html, (
                f"{eid}: width:{ew} not found in HTML"
            )

    def test_html_entity_positions_match_finalized_layout(self):
        """HTML card positions (left/top) must match FinalizedLayout bounds (AC9)."""
        fl = compile_er_layout(_MINIMAL)
        html = er_to_html(_MINIMAL)
        for eid, nl in fl.node_layouts.items():
            ex = nl.outer_bounds.x
            ey = nl.outer_bounds.y
            assert f"left:{ex}" in html, f"{eid}: left:{ex} not in HTML"
            assert f"top:{ey}" in html, f"{eid}: top:{ey} not in HTML"

    def test_compile_er_alias_produces_same_geometry(self):
        """compile_er() and compile_er_layout() must produce identical FinalizedLayouts (AC9)."""
        fl1 = compile_er(_ECOMMERCE_SRC)
        fl2 = compile_er_layout(_ECOMMERCE_SRC)
        assert fl1.canvas_bounds == fl2.canvas_bounds, "Canvas bounds differ"
        for eid in fl2.node_layouts:
            b1 = fl1.node_layouts[eid].outer_bounds
            b2 = fl2.node_layouts[eid].outer_bounds
            assert b1 == b2, f"{eid}: bounds differ: {b1} vs {b2}"

    def test_html_canvas_dimensions_match_finalized_layout(self):
        """HTML container width/height must match compile_er_layout canvas bounds (AC9)."""
        fl = compile_er_layout(_ECOMMERCE_SRC, width_hint=600)
        html = er_to_html(_ECOMMERCE_SRC, width_hint=600)
        cw = fl.canvas_bounds.w
        ch = fl.canvas_bounds.h
        assert f"width:{cw}" in html, f"Canvas width {cw} not in HTML"
        assert f"height:{ch}" in html, f"Canvas height {ch} not in HTML"

    def test_svg_scene_canvas_matches_finalized_layout(self):
        """SVG scene (layout_er_scene) canvas must equal FinalizedLayout canvas bounds (AC9).

        Both SVG and HTML paths must consume identical geometry from compile_er_layout.
        """
        fl = compile_er_layout(_ECOMMERCE_SRC)
        scene = layout_er_scene(_ECOMMERCE_SRC)
        assert scene.width == fl.canvas_bounds.w, (
            f"SVG scene width {scene.width} != FinalizedLayout canvas w {fl.canvas_bounds.w}"
        )
        assert scene.height == fl.canvas_bounds.h, (
            f"SVG scene height {scene.height} != FinalizedLayout canvas h {fl.canvas_bounds.h}"
        )

    def test_svg_scene_node_count_matches_finalized_layout(self):
        """SVG scene must record the same entities as compile_er_layout (AC9).

        layout_er_scene() delegates to compile_er_layout(); we verify that it
        emits one SceneRect per entity with semantic_role='entity'.
        """
        from mermaid_render.scene import SceneRect
        fl = compile_er_layout(_THREE_ENTITY)
        scene = layout_er_scene(_THREE_ENTITY)
        # Count SceneRect elements with semantic_role="entity" across all layers
        entity_rects = [
            el
            for _, elements in scene.layers
            for el in elements
            if isinstance(el, SceneRect) and getattr(el, "semantic_role", "") == "entity"
        ]
        fl_count = len(fl.node_layouts)
        assert len(entity_rects) == fl_count, (
            f"SVG scene has {len(entity_rects)} entity SceneRects, "
            f"FinalizedLayout has {fl_count}"
        )


# ── Task 6: ELK routing fallback typed (diagnostics) ─────────────────────────

class TestELKRoutingFallback:
    def test_fallback_routing_typed_when_elk_unavailable(self):
        """When ELK is unavailable, diagnostics.warnings must contain 'elk-unavailable' (Task 6).

        The Sugiyama fallback is a typed fallback — its use is always disclosed in
        diagnostics so callers can detect it.
        """
        if _ELK_AVAILABLE:
            pytest.skip("ELK is available; this test covers the fallback path only")
        fl = compile_er_layout(_ECOMMERCE_SRC)
        elk_warnings = [w for w in fl.diagnostics.warnings if "elk-unavailable" in w]
        assert elk_warnings, (
            "Expected 'elk-unavailable' in diagnostics.warnings when ELK is absent; "
            f"got: {list(fl.diagnostics.warnings)}"
        )

    @_NEEDS_ELK
    def test_elk_routing_produces_no_elk_unavailable_warning(self):
        """When ELK is available, diagnostics.warnings must NOT contain 'elk-unavailable' (Task 6)."""
        fl = compile_er_layout(_ECOMMERCE_SRC)
        elk_warnings = [w for w in fl.diagnostics.warnings if "elk-unavailable" in w]
        assert not elk_warnings, (
            f"Unexpected elk-unavailable warning when ELK should be available: {elk_warnings}"
        )
