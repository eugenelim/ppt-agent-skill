"""Stage 9: ArchitectureDiagramLayout compiled model tests.

Verifies:
- compile_architecture() returns an ArchitectureDiagramLayout
- Service tiles: measured label (TextLayout), icon_bounds (when icon present), side ports
- Junctions: outer_bounds, arch_to_finalized produces is_dummy=True NodeLayout
- Group boundaries: parent_group_id populated for nested groups, member_ids, child_group_ids
- BiRel (<-->): single ArchEdge with has_marker_start=True, has_marker_end=True
- arch_to_finalized() produces a valid FinalizedLayout
- layout_architecture_scene() pipeline: no regressions + zoom applied correctly
"""
from __future__ import annotations

import pytest

from scripts.mermaid_render.layout.architecture import (
    ArchitectureDiagramLayout,
    ArchEdge,
    ArchGroupBoundary,
    ArchJunction,
    ArchServiceTile,
    arch_to_finalized,
    compile_architecture,
    layout_architecture_scene,
)
from scripts.mermaid_render.layout._geometry import (
    FinalizedLayout,
    NodeLayout,
    PortSide,
    TextLayout,
    Rect,
)
from scripts.mermaid_render.scene import SvgScene, LAYER_NODES, LAYER_EDGES, LAYER_LABELS


# ── Fixtures ───────────────────────────────────────────────────────────────────

SIMPLE = """\
architecture-beta
    service api(server)[API Gateway]
    service db(database)[Database]
    api --> db
"""

WITH_ICON = """\
architecture-beta
    service svc(server)[My Service]
"""

WITH_JUNCTION = """\
architecture-beta
    service a(server)[A]
    junction jct
    service b(database)[B]
    a --> jct
    jct --> b
"""

BIREL = """\
architecture-beta
    service a(server)[A]
    service b(database)[B]
    a <--> b
"""

WITH_GROUPS = """\
architecture-beta
    group outer[Outer]
        group inner[Inner] in outer
            service svc(server)[Service]
"""

BIREL_WITH_LABEL = """\
architecture-beta
    service x(server)[X]
    service y(database)[Y]
    x <--> y : link
"""


# ── ArchitectureDiagramLayout type ────────────────────────────────────────────

class TestCompiledModelType:
    def test_returns_arch_diagram_layout(self):
        arch = compile_architecture(SIMPLE)
        assert isinstance(arch, ArchitectureDiagramLayout)

    def test_services_are_arch_service_tiles(self):
        arch = compile_architecture(SIMPLE)
        assert all(isinstance(s, ArchServiceTile) for s in arch.services)

    def test_junctions_are_arch_junctions(self):
        arch = compile_architecture(WITH_JUNCTION)
        assert all(isinstance(j, ArchJunction) for j in arch.junctions)

    def test_groups_are_arch_group_boundaries(self):
        arch = compile_architecture(WITH_GROUPS)
        assert all(isinstance(g, ArchGroupBoundary) for g in arch.groups)

    def test_edges_are_arch_edges(self):
        arch = compile_architecture(SIMPLE)
        assert all(isinstance(e, ArchEdge) for e in arch.edges)

    def test_canvas_bounds_positive(self):
        arch = compile_architecture(SIMPLE)
        assert arch.canvas_bounds.w > 0
        assert arch.canvas_bounds.h > 0

    def test_direction_is_lr(self):
        arch = compile_architecture(SIMPLE)
        assert arch.direction == "LR"

    def test_zoom_default_one(self):
        arch = compile_architecture(SIMPLE)
        assert arch.zoom == 1.0

    def test_no_services_raises(self):
        with pytest.raises(ValueError, match="No services"):
            compile_architecture("architecture-beta\n")


# ── Service tile semantics ─────────────────────────────────────────────────────

class TestServiceTile:
    def test_service_ids_present(self):
        arch = compile_architecture(SIMPLE)
        ids = {s.node_id for s in arch.services}
        assert "api" in ids
        assert "db" in ids

    def test_label_layout_is_text_layout(self):
        arch = compile_architecture(SIMPLE)
        for svc in arch.services:
            assert isinstance(svc.label_layout, TextLayout)

    def test_label_text_matches_source(self):
        arch = compile_architecture(SIMPLE)
        api = next(s for s in arch.services if s.node_id == "api")
        assert api.label == "API Gateway"
        assert api.label_layout.lines[0].runs[0].text == "API Gateway"

    def test_label_width_positive(self):
        arch = compile_architecture(SIMPLE)
        for svc in arch.services:
            assert svc.label_layout.width > 0

    def test_icon_present_for_server_hint(self):
        arch = compile_architecture(WITH_ICON)
        svc = arch.services[0]
        assert svc.icon_name == "node"        # server → node asset
        assert len(svc.icon_svg) > 0          # SVG loaded

    def test_icon_bounds_when_icon_present(self):
        arch = compile_architecture(WITH_ICON)
        svc = arch.services[0]
        assert svc.icon_bounds is not None
        assert isinstance(svc.icon_bounds, Rect)
        assert svc.icon_bounds.w > 0
        assert svc.icon_bounds.h > 0

    def test_icon_bounds_none_when_no_icon(self):
        # No icon hint → icon_name="" → icon_svg="" → icon_bounds=None
        src = "architecture-beta\nservice plain[Plain Service]\n"
        arch = compile_architecture(src)
        svc = arch.services[0]
        assert svc.icon_bounds is None

    def test_side_ports_count(self):
        arch = compile_architecture(SIMPLE)
        for svc in arch.services:
            assert len(svc.side_ports) == 4

    def test_side_ports_have_correct_sides(self):
        arch = compile_architecture(SIMPLE)
        svc = arch.services[0]
        sides = {p.side for p in svc.side_ports}
        assert PortSide.LEFT in sides
        assert PortSide.RIGHT in sides
        assert PortSide.TOP in sides
        assert PortSide.BOTTOM in sides

    def test_side_port_positions_on_boundary(self):
        arch = compile_architecture(SIMPLE)
        for svc in arch.services:
            b = svc.outer_bounds
            for port in svc.side_ports:
                px, py = port.position.x, port.position.y
                # Port must lie on one of the four faces (within 1px tolerance)
                on_left = abs(px - b.x) < 1.0
                on_right = abs(px - (b.x + b.w)) < 1.0
                on_top = abs(py - b.y) < 1.0
                on_bottom = abs(py - (b.y + b.h)) < 1.0
                assert on_left or on_right or on_top or on_bottom, (
                    f"Port {port.side} at ({px},{py}) not on any face of {b}"
                )

    def test_outer_bounds_positive(self):
        arch = compile_architecture(SIMPLE)
        for svc in arch.services:
            assert svc.outer_bounds.w > 0
            assert svc.outer_bounds.h > 0


# ── Junction semantics ─────────────────────────────────────────────────────────

class TestJunctionGeometry:
    def test_junction_present(self):
        arch = compile_architecture(WITH_JUNCTION)
        assert len(arch.junctions) == 1
        assert arch.junctions[0].node_id == "jct"

    def test_junction_not_in_services(self):
        arch = compile_architecture(WITH_JUNCTION)
        service_ids = {s.node_id for s in arch.services}
        assert "jct" not in service_ids

    def test_junction_has_outer_bounds(self):
        arch = compile_architecture(WITH_JUNCTION)
        jct = arch.junctions[0]
        assert isinstance(jct.outer_bounds, Rect)

    def test_junction_node_layout_is_dummy(self):
        arch = compile_architecture(WITH_JUNCTION)
        finalized = arch_to_finalized(arch)
        jct_layout = finalized.node_layouts["jct"]
        assert jct_layout.is_dummy is True

    def test_junction_node_layout_shape(self):
        arch = compile_architecture(WITH_JUNCTION)
        finalized = arch_to_finalized(arch)
        assert finalized.node_layouts["jct"].semantic_shape == "arch-junction"

    def test_services_still_present_with_junction(self):
        arch = compile_architecture(WITH_JUNCTION)
        service_ids = {s.node_id for s in arch.services}
        assert "a" in service_ids
        assert "b" in service_ids


# ── Group boundary semantics ───────────────────────────────────────────────────

class TestGroupBoundarySemantics:
    def test_group_present(self):
        arch = compile_architecture(WITH_GROUPS)
        group_ids = {g.group_id for g in arch.groups}
        assert "outer" in group_ids
        assert "inner" in group_ids

    def test_inner_group_parent_id(self):
        arch = compile_architecture(WITH_GROUPS)
        inner = next(g for g in arch.groups if g.group_id == "inner")
        assert inner.parent_group_id == "outer"

    def test_outer_group_no_parent(self):
        arch = compile_architecture(WITH_GROUPS)
        outer = next(g for g in arch.groups if g.group_id == "outer")
        assert outer.parent_group_id is None

    def test_outer_has_inner_as_child(self):
        arch = compile_architecture(WITH_GROUPS)
        outer = next(g for g in arch.groups if g.group_id == "outer")
        assert "inner" in outer.child_group_ids

    def test_inner_member_ids(self):
        arch = compile_architecture(WITH_GROUPS)
        inner = next(g for g in arch.groups if g.group_id == "inner")
        assert "svc" in inner.member_ids

    def test_group_label_layout(self):
        arch = compile_architecture(WITH_GROUPS)
        outer = next(g for g in arch.groups if g.group_id == "outer")
        assert outer.label_layout is not None
        assert outer.label_layout.lines[0].runs[0].text == "Outer"

    def test_group_boundary_bounds_positive(self):
        src = "architecture-beta\ngroup g[G]\n    service s(server)[S]\n"
        arch = compile_architecture(src)
        grp = next(g for g in arch.groups if g.group_id == "g")
        assert grp.boundary_bounds.w > 0
        assert grp.boundary_bounds.h > 0

    def test_finalized_group_parent_id_propagated(self):
        arch = compile_architecture(WITH_GROUPS)
        finalized = arch_to_finalized(arch)
        inner_gl = finalized.group_layouts.get("inner")
        assert inner_gl is not None
        assert inner_gl.parent_group_id == "outer"


# ── BiRel semantics: one path with two markers ─────────────────────────────────

class TestBiRelEdge:
    def test_birel_produces_one_arch_edge(self):
        arch = compile_architecture(BIREL)
        assert len(arch.edges) == 1

    def test_birel_has_marker_start(self):
        arch = compile_architecture(BIREL)
        assert arch.edges[0].has_marker_start is True

    def test_birel_has_marker_end(self):
        arch = compile_architecture(BIREL)
        assert arch.edges[0].has_marker_end is True

    def test_birel_edge_ids_match_src_dst(self):
        arch = compile_architecture(BIREL)
        e = arch.edges[0]
        assert e.src_id in ("a", "b")
        assert e.dst_id in ("a", "b")
        assert e.src_id != e.dst_id

    def test_birel_finalized_edge_has_both_markers(self):
        arch = compile_architecture(BIREL)
        finalized = arch_to_finalized(arch)
        assert len(finalized.routed_edges) == 1
        re = finalized.routed_edges[0]
        assert re.has_marker_start is True
        assert re.has_marker_end is True

    def test_birel_with_label(self):
        arch = compile_architecture(BIREL_WITH_LABEL)
        assert len(arch.edges) == 1
        assert arch.edges[0].label == "link"
        assert arch.edges[0].label_layout is not None

    def test_directed_edge_no_marker_start(self):
        arch = compile_architecture(SIMPLE)
        for e in arch.edges:
            assert e.has_marker_start is False

    def test_directed_edge_has_marker_end(self):
        arch = compile_architecture(SIMPLE)
        for e in arch.edges:
            assert e.has_marker_end is True


# ── arch_to_finalized ──────────────────────────────────────────────────────────

class TestArchToFinalized:
    def test_returns_finalized_layout(self):
        arch = compile_architecture(SIMPLE)
        fl = arch_to_finalized(arch)
        assert isinstance(fl, FinalizedLayout)

    def test_node_layouts_present(self):
        arch = compile_architecture(SIMPLE)
        fl = arch_to_finalized(arch)
        assert "api" in fl.node_layouts
        assert "db" in fl.node_layouts

    def test_service_semantic_shape(self):
        arch = compile_architecture(SIMPLE)
        fl = arch_to_finalized(arch)
        assert fl.node_layouts["api"].semantic_shape == "arch-service"

    def test_service_not_dummy(self):
        arch = compile_architecture(SIMPLE)
        fl = arch_to_finalized(arch)
        assert fl.node_layouts["api"].is_dummy is False

    def test_icon_svg_propagated(self):
        arch = compile_architecture(WITH_ICON)
        fl = arch_to_finalized(arch)
        nl = fl.node_layouts["svc"]
        assert len(nl.icon_svg) > 0

    def test_icon_bounds_propagated(self):
        arch = compile_architecture(WITH_ICON)
        fl = arch_to_finalized(arch)
        nl = fl.node_layouts["svc"]
        assert nl.icon_bounds is not None

    def test_side_ports_propagated(self):
        arch = compile_architecture(SIMPLE)
        fl = arch_to_finalized(arch)
        # Service tiles have 4 side ports
        nl = fl.node_layouts["api"]
        assert len(nl.ports) == 4

    def test_group_layouts_with_hierarchy(self):
        arch = compile_architecture(WITH_GROUPS)
        fl = arch_to_finalized(arch)
        assert "outer" in fl.group_layouts
        assert "inner" in fl.group_layouts
        assert fl.group_layouts["inner"].parent_group_id == "outer"

    def test_canvas_bounds_correct(self):
        arch = compile_architecture(SIMPLE)
        fl = arch_to_finalized(arch)
        assert fl.canvas_bounds.w == arch.canvas_bounds.w
        assert fl.canvas_bounds.h == arch.canvas_bounds.h

    def test_routed_edges_present(self):
        arch = compile_architecture(SIMPLE)
        fl = arch_to_finalized(arch)
        assert len(fl.routed_edges) > 0

    def test_routed_edge_waypoints_present(self):
        arch = compile_architecture(SIMPLE)
        fl = arch_to_finalized(arch)
        for re in fl.routed_edges:
            assert len(re.waypoints) >= 2


# ── Scene output: no regressions ──────────────────────────────────────────────

class TestSceneOutput:
    def test_returns_svg_scene(self):
        scene = layout_architecture_scene(SIMPLE)
        assert isinstance(scene, SvgScene)

    def test_diagram_type(self):
        scene = layout_architecture_scene(SIMPLE)
        assert scene.diagram_type == "architecture-beta"

    def test_has_node_elements(self):
        scene = layout_architecture_scene(SIMPLE)
        assert len(scene.get_layer(LAYER_NODES)) > 0

    def test_has_edge_elements(self):
        scene = layout_architecture_scene(SIMPLE)
        assert len(scene.get_layer(LAYER_EDGES)) > 0

    def test_has_label_with_service_text(self):
        scene = layout_architecture_scene(SIMPLE)
        labels = scene.get_layer(LAYER_LABELS)
        texts = [el.lines[0].text for el in labels if hasattr(el, "lines") and el.lines]
        assert any("API Gateway" in t or "Database" in t for t in texts)

    def test_no_foreign_object(self):
        from scripts.mermaid_render.svg_serializer import scene_to_svg_str
        scene = layout_architecture_scene(SIMPLE)
        svg = scene_to_svg_str(scene)
        assert "<foreignObject" not in svg

    def test_valid_xml(self):
        from lxml import etree
        import re
        from scripts.mermaid_render.svg_serializer import scene_to_svg_str
        scene = layout_architecture_scene(SIMPLE)
        svg = scene_to_svg_str(scene)
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        etree.fromstring(body.encode("utf-8"))

    def test_deterministic(self):
        s1 = layout_architecture_scene(SIMPLE)
        s2 = layout_architecture_scene(SIMPLE)
        assert s1.scene_id == s2.scene_id

    def test_width_hint_applies_zoom(self):
        scene = layout_architecture_scene(SIMPLE, width_hint=300)
        assert scene.width <= 301, f"Expected width ≤ 301; got {scene.width}"

    def test_width_hint_viewbox_unchanged(self):
        scene_full = layout_architecture_scene(SIMPLE)
        scene_zoom = layout_architecture_scene(SIMPLE, width_hint=300)
        # viewBox coordinate space is preserved even when width is smaller
        assert scene_zoom.view_box[2] == scene_full.view_box[2]

    def test_birel_produces_two_markers_in_svg(self):
        from scripts.mermaid_render.svg_serializer import scene_to_svg_str
        scene = layout_architecture_scene(BIREL)
        svg = scene_to_svg_str(scene)
        # The single path should carry both marker-start and marker-end
        assert "marker-start" in svg
        assert "marker-end" in svg

    def test_group_boundary_in_scene(self):
        src = "architecture-beta\ngroup g[MyGroup]\n    service s(server)[S]\n"
        scene = layout_architecture_scene(src)
        # boundary layer contains the group element
        from scripts.mermaid_render.scene import LAYER_BOUNDARIES
        boundaries = scene.get_layer(LAYER_BOUNDARIES)
        assert len(boundaries) > 0

    def test_deterministic_svg_bytes(self):
        from scripts.mermaid_render.svg_serializer import scene_to_svg_str
        svg1 = scene_to_svg_str(layout_architecture_scene(SIMPLE))
        svg2 = scene_to_svg_str(layout_architecture_scene(SIMPLE))
        assert svg1 == svg2


# ── Parse edge cases ──────────────────────────────────────────────────────────

class TestParseEdgeCases:
    def test_reverse_edge_swaps_src_dst(self):
        # `a <-- b` should produce an edge from b to a (arrow at a's end)
        src = "architecture-beta\n    service a(server)[A]\n    service b(database)[B]\n    a <-- b\n"
        arch = compile_architecture(src)
        assert len(arch.edges) == 1
        e = arch.edges[0]
        assert e.src_id == "b"
        assert e.dst_id == "a"
        assert e.has_marker_end is True
        assert e.has_marker_start is False

    def test_undirected_edge_no_marker(self):
        src = "architecture-beta\n    service a(server)[A]\n    service b(database)[B]\n    a -- b\n"
        arch = compile_architecture(src)
        assert len(arch.edges) == 1
        assert arch.edges[0].has_marker_end is False
        assert arch.edges[0].has_marker_start is False

    def test_node_cap_exceeded(self):
        from scripts.mermaid_render.layout._constants import NODE_CAP
        lines = ["architecture-beta"]
        for i in range(NODE_CAP + 1):
            lines.append(f"    service s{i}[S{i}]")
        with pytest.raises(ValueError, match="Cap exceeded"):
            compile_architecture("\n".join(lines))

    def test_unknown_icon_hint_stored_verbatim(self):
        # An icon hint not in _ARCH_ICON_MAP is kept as-is (may produce empty icon_svg)
        src = "architecture-beta\n    service x(totally-unknown-icon-xyz)[X]\n"
        arch = compile_architecture(src)
        svc = arch.services[0]
        assert svc.icon_name == "totally-unknown-icon-xyz"
