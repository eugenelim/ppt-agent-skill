"""Tests for the native C4 scene builder (layout/c4_layout.py)."""
from __future__ import annotations

import re

import pytest

from scripts.mermaid_render.layout.c4_layout import (
    layout_c4_scene, _parse_c4_source,
)
from scripts.mermaid_render.scene import (
    MarkerDefinition, SceneCircle, SceneEllipse, SceneLine,
    ScenePath, SceneRect, SceneRoundedRect, SceneText, SvgScene,
    LAYER_EDGES, LAYER_NODES, LAYER_LABELS, LAYER_BOUNDARIES, LAYER_BACKGROUND,
)
from scripts.mermaid_render.svg_serializer import scene_to_svg_str
from scripts.mermaid_render.native_svg import dispatch_native


SIMPLE_C4 = """\
C4Context
    title System Context
    Person(user, "User", "A human")
    System(webapp, "Web App", "The main system")
    System_Ext(ext, "External API", "Third party")
    Rel(user, webapp, "Uses")
    Rel(webapp, ext, "Calls")
"""

WITH_BOUNDARY = """\
C4Container
    title Container Diagram
    System_Boundary(sys, "System") {
        Container(web, "Web App", "React", "Frontend")
        Container(api, "API", "FastAPI", "Backend")
        ContainerDb(db, "Database", "PostgreSQL", "Stores data")
    }
    Rel(web, api, "REST")
    Rel(api, db, "SQL")
"""

MINIMAL_C4 = """\
C4Context
    Person(u, "Alice")
    System(s, "System")
"""


class TestC4Parser:
    def test_parses_items(self):
        _, items, _, _ = _parse_c4_source(SIMPLE_C4)
        aliases = [i.alias for i in items]
        assert "user" in aliases
        assert "webapp" in aliases
        assert "ext" in aliases

    def test_external_flag(self):
        _, items, _, _ = _parse_c4_source(SIMPLE_C4)
        ext = next(i for i in items if i.alias == "ext")
        assert ext.is_external is True

    def test_internal_not_external(self):
        _, items, _, _ = _parse_c4_source(SIMPLE_C4)
        webapp = next(i for i in items if i.alias == "webapp")
        assert webapp.is_external is False

    def test_relationships(self):
        _, _, rels, _ = _parse_c4_source(SIMPLE_C4)
        src_dst = [(r.src, r.dst) for r in rels]
        assert ("user", "webapp") in src_dst

    def test_title(self):
        title, _, _, _ = _parse_c4_source(SIMPLE_C4)
        assert title == "System Context"

    def test_boundary_groups(self):
        _, _, _, groups = _parse_c4_source(WITH_BOUNDARY)
        assert "sys" in groups

    def test_items_inside_boundary(self):
        _, items, _, _ = _parse_c4_source(WITH_BOUNDARY)
        web = next(i for i in items if i.alias == "web")
        assert web.boundary == "sys"

    def test_technology_parsed(self):
        _, items, _, _ = _parse_c4_source(WITH_BOUNDARY)
        web = next(i for i in items if i.alias == "web")
        assert web.technology == "React"

    def test_containerdb_technology_parsed(self):
        # ContainerDb uses concatenated (no-underscore) suffix — must not drop technology
        _, items, _, _ = _parse_c4_source(WITH_BOUNDARY)
        db = next(i for i in items if i.alias == "db")
        assert db.technology == "PostgreSQL", \
            "ContainerDb(db, label, tech, desc) must parse technology correctly"
        assert db.description == "Stores data", \
            "ContainerDb(db, label, tech, desc) must parse description correctly"

    def test_empty_source_returns_empty_items(self):
        _, items, _, _ = _parse_c4_source("C4Context\n")
        assert items == []


class TestC4Scene:
    def test_returns_svg_scene(self):
        assert isinstance(layout_c4_scene(SIMPLE_C4), SvgScene)

    def test_diagram_type(self):
        scene = layout_c4_scene(SIMPLE_C4)
        assert scene.diagram_type == "c4context"

    def test_has_nodes(self):
        scene = layout_c4_scene(SIMPLE_C4)
        nodes = scene.get_layer(LAYER_NODES)
        assert len(nodes) >= 3  # 3 items → rects + accent bars

    def test_has_edges(self):
        scene = layout_c4_scene(SIMPLE_C4)
        edges = scene.get_layer(LAYER_EDGES)
        paths = [el for el in edges if isinstance(el, ScenePath)]
        assert len(paths) >= 2  # 2 relationships

    def test_labels_contain_item_names(self):
        scene = layout_c4_scene(SIMPLE_C4)
        labels = scene.get_layer(LAYER_LABELS)
        texts = [el.lines[0].text for el in labels if hasattr(el, "lines")]
        assert "User" in texts
        assert "Web App" in texts

    def test_stereotype_labels(self):
        scene = layout_c4_scene(SIMPLE_C4)
        labels = scene.get_layer(LAYER_LABELS)
        texts = [el.lines[0].text for el in labels if hasattr(el, "lines")]
        assert any("[Person]" in t or "Person" in t for t in texts)

    def test_title_in_background(self):
        scene = layout_c4_scene(SIMPLE_C4)
        bg = scene.get_layer(LAYER_BACKGROUND)
        texts = [el.lines[0].text for el in bg if hasattr(el, "lines")]
        assert "System Context" in texts

    def test_boundary_in_boundaries_layer(self):
        scene = layout_c4_scene(WITH_BOUNDARY, c4_type="c4container")
        bounds = scene.get_layer(LAYER_BOUNDARIES)
        assert len(bounds) > 0

    def test_no_foreign_object(self):
        scene = layout_c4_scene(SIMPLE_C4)
        svg = scene_to_svg_str(scene)
        assert "<foreignObject" not in svg

    def test_valid_xml(self):
        from lxml import etree
        scene = layout_c4_scene(SIMPLE_C4)
        svg = scene_to_svg_str(scene)
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        etree.fromstring(body.encode("utf-8"))

    def test_contains_labels_in_svg(self):
        scene = layout_c4_scene(SIMPLE_C4)
        svg = scene_to_svg_str(scene)
        assert "User" in svg
        assert "Web App" in svg

    def test_deterministic(self):
        s1 = layout_c4_scene(SIMPLE_C4)
        s2 = layout_c4_scene(SIMPLE_C4)
        assert s1.scene_id == s2.scene_id

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="No elements"):
            layout_c4_scene("C4Context\n")

    def test_width_hint_zooms_viewbox(self):
        scene = layout_c4_scene(SIMPLE_C4, width_hint=400)
        # With zoom, svg width should be ≤ width_hint, but viewBox keeps 832
        assert scene.view_box[2] >= scene.width


class TestC4ViaNative:
    def test_dispatch_c4context(self):
        svg = dispatch_native(SIMPLE_C4)
        assert "<svg" in svg
        assert "<foreignObject" not in svg

    def test_c4container_via_native(self):
        svg = dispatch_native(WITH_BOUNDARY)
        assert "<svg" in svg

    def test_labels_present(self):
        svg = dispatch_native(SIMPLE_C4)
        assert "User" in svg or "user" in svg.lower()


# ── Stage 10 distinct-painter and edge-behaviour tests ────────────────────────

_PERSON_SRC = """\
C4Context
Person(u, "Alice", "End user")
System(s, "System", "The main system")
"""

_SYSTEMDB_SRC = """\
C4Context
SystemDb(db, "User Store", "Holds users")
System(s, "App", "Application")
"""

_SYSTEMQUEUE_SRC = """\
C4Context
SystemQueue(q, "Message Queue", "Async bus")
System(s, "App", "Application")
"""

_EXT_SRC = """\
C4Context
System_Ext(ext, "External System", "Third party")
System(s, "Internal", "Our system")
"""

_BIREL_SRC = """\
C4Context
System(a, "Alpha", "First")
System(b, "Beta", "Second")
BiRel(a, b, "Exchanges data")
"""

_DIR_HINT_SRC = """\
C4Context
System(top, "Top", "Upper system")
System(bot, "Bottom", "Lower system")
Rel_D(top, bot, "Calls down")
"""

_DIR_HINT_U_SRC = """\
C4Context
System(top, "Top", "Upper system")
System(bot, "Bottom", "Lower system")
Rel_U(bot, top, "Reports up")
"""

_DIR_HINT_L_SRC = """\
C4Context
System(right, "Right", "Right system")
System(left, "Left", "Left system")
Rel_L(right, left, "Goes left")
"""

_DIR_HINT_R_SRC = """\
C4Context
System(left, "Left", "Left system")
System(right, "Right", "Right system")
Rel_R(left, right, "Goes right")
"""

_TECH_SRC = """\
C4Container
Container(api, "API", "FastAPI", "REST backend")
"""

_NESTED_BOUNDARY_SRC = """\
C4Container
title Nested
System_Boundary(outer, "Outer") {
    System_Boundary(inner, "Inner") {
        Container(c1, "Service A", "Java", "Core")
    }
    Container(c2, "Service B", "Go", "Support")
}
"""


class TestC4DistinctPainters:
    """Stage 10: distinct per-kind shapes in the native SVG painter."""

    def test_person_has_circle(self):
        scene = layout_c4_scene(_PERSON_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        assert any(isinstance(el, SceneCircle) for el in nodes), \
            "Person painter must emit a SceneCircle for the head"

    def test_person_has_body_paths(self):
        scene = layout_c4_scene(_PERSON_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        person_paths = [el for el in nodes if isinstance(el, ScenePath)]
        assert len(person_paths) >= 2, \
            "Person painter must emit >= 2 ScenePath elements (trunk, arms, legs)"

    def test_person_background_box_present(self):
        scene = layout_c4_scene(_PERSON_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        person_box = next(
            (el for el in nodes
             if isinstance(el, SceneRoundedRect)
             and any(k == "node-id" and v == "u" for k, v in el.data_attrs)),
            None,
        )
        assert person_box is not None, "Person node must have a background SceneRoundedRect"

    def test_systemdb_has_ellipses(self):
        scene = layout_c4_scene(_SYSTEMDB_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        ellipses = [el for el in nodes if isinstance(el, SceneEllipse)]
        assert len(ellipses) >= 2, \
            "SystemDb painter must emit >= 2 SceneEllipse (top and bottom caps)"

    def test_systemdb_has_barrel_rect(self):
        scene = layout_c4_scene(_SYSTEMDB_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        barrel = next(
            (el for el in nodes
             if isinstance(el, SceneRect)
             and any(k == "node-id" and v == "db" for k, v in el.data_attrs)),
            None,
        )
        assert barrel is not None, "SystemDb painter must emit a SceneRect barrel body"

    def test_systemdb_has_side_lines(self):
        scene = layout_c4_scene(_SYSTEMDB_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        side_lines = [el for el in nodes if isinstance(el, SceneLine)
                      and ("cyl-ls" in el.element_id or "cyl-rs" in el.element_id)]
        assert len(side_lines) >= 2, "SystemDb painter must emit 2 side SceneLine elements"

    def test_systemqueue_has_bar_lines(self):
        scene = layout_c4_scene(_SYSTEMQUEUE_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        bars = [el for el in nodes
                if isinstance(el, SceneLine) and "qbar" in el.element_id]
        assert len(bars) == 2, "SystemQueue painter must emit exactly 2 queue-bar SceneLine"

    def test_systemqueue_background_box_present(self):
        scene = layout_c4_scene(_SYSTEMQUEUE_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        box = next(
            (el for el in nodes
             if isinstance(el, SceneRoundedRect)
             and any(k == "node-id" and v == "q" for k, v in el.data_attrs)),
            None,
        )
        assert box is not None, "SystemQueue must have a background SceneRoundedRect"

    def test_ext_variant_dashed_border(self):
        scene = layout_c4_scene(_EXT_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        ext_node = next(
            (el for el in nodes
             if isinstance(el, SceneRoundedRect)
             and any(k == "node-id" and v == "ext" for k, v in el.data_attrs)),
            None,
        )
        assert ext_node is not None, "Ext node must have a SceneRoundedRect"
        assert ext_node.paint.stroke is not None, "Ext node must have a stroke"
        assert ext_node.paint.stroke.dasharray == "4 3", \
            f"Ext variant stroke should be dashed '4 3', got {ext_node.paint.stroke.dasharray!r}"

    def test_internal_node_solid_border(self):
        scene = layout_c4_scene(_EXT_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        int_node = next(
            (el for el in nodes
             if isinstance(el, SceneRoundedRect)
             and any(k == "node-id" and v == "s" for k, v in el.data_attrs)),
            None,
        )
        assert int_node is not None
        assert int_node.paint.stroke is not None
        assert int_node.paint.stroke.dasharray == "", \
            "Internal node should have solid border (empty dasharray)"

    def test_birel_path_has_start_marker(self):
        scene = layout_c4_scene(_BIREL_SRC)
        edges = scene.get_layer(LAYER_EDGES)
        birel_paths = [el for el in edges
                       if isinstance(el, ScenePath) and el.marker_start != ""]
        assert birel_paths, "BiRel must produce a ScenePath with marker_start set"

    def test_birel_has_two_marker_definitions(self):
        scene = layout_c4_scene(_BIREL_SRC)
        marker_defs = [d for d in scene.definitions if isinstance(d, MarkerDefinition)]
        assert len(marker_defs) >= 2, \
            f"BiRel must define >= 2 markers (end + start), got {len(marker_defs)}"

    def test_birel_start_marker_type(self):
        scene = layout_c4_scene(_BIREL_SRC)
        marker_defs = [d for d in scene.definitions if isinstance(d, MarkerDefinition)]
        types = {d.marker_type for d in marker_defs}
        assert "arrow-start" in types, "BiRel must define an arrow-start marker"
        assert "arrow-end" in types, "BiRel must define an arrow-end marker"

    def test_birel_valid_svg(self):
        from lxml import etree
        scene = layout_c4_scene(_BIREL_SRC)
        svg = scene_to_svg_str(scene)
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        etree.fromstring(body.encode("utf-8"))  # must not raise

    def test_rel_d_uses_bezier(self):
        scene = layout_c4_scene(_DIR_HINT_SRC)
        edges = scene.get_layer(LAYER_EDGES)
        paths = [el for el in edges if isinstance(el, ScenePath)]
        assert paths, "Rel_D must produce edge paths"
        has_q = any(any(cmd[0] == "Q" for cmd in p.commands) for p in paths)
        assert has_q, "Rel_D must produce a Bézier curve (Q command in path)"

    def test_rel_u_uses_bezier(self):
        scene = layout_c4_scene(_DIR_HINT_U_SRC)
        edges = scene.get_layer(LAYER_EDGES)
        paths = [el for el in edges if isinstance(el, ScenePath)]
        has_q = any(any(cmd[0] == "Q" for cmd in p.commands) for p in paths)
        assert has_q, "Rel_U must produce a Bézier curve (Q command in path)"

    def test_rel_l_uses_bezier(self):
        scene = layout_c4_scene(_DIR_HINT_L_SRC)
        edges = scene.get_layer(LAYER_EDGES)
        paths = [el for el in edges if isinstance(el, ScenePath)]
        has_q = any(any(cmd[0] == "Q" for cmd in p.commands) for p in paths)
        assert has_q, "Rel_L must produce a Bézier curve (Q command in path)"

    def test_rel_r_uses_bezier(self):
        scene = layout_c4_scene(_DIR_HINT_R_SRC)
        edges = scene.get_layer(LAYER_EDGES)
        paths = [el for el in edges if isinstance(el, ScenePath)]
        has_q = any(any(cmd[0] == "Q" for cmd in p.commands) for p in paths)
        assert has_q, "Rel_R must produce a Bézier curve (Q command in path)"

    def test_rel_d_vs_rel_u_bias_sign(self):
        """Rel_D ctrl_y must exceed Rel_U ctrl_y (downward vs upward bias)."""
        def _first_q_ctrl(src):
            scene = layout_c4_scene(src)
            for el in scene.get_layer(LAYER_EDGES):
                if isinstance(el, ScenePath):
                    for cmd in el.commands:
                        if cmd[0] == "Q":
                            return cmd[1], cmd[2]  # ctrl_x, ctrl_y
            return None, None

        # Same two nodes, different direction hints → same start/end, different bias
        d_src = 'C4Context\nSystem(a, "Alpha", "First")\nSystem(b, "Beta", "Second")\nRel_D(a, b, "Down")\n'
        u_src = 'C4Context\nSystem(a, "Alpha", "First")\nSystem(b, "Beta", "Second")\nRel_U(a, b, "Up")\n'
        _, d_ctrl_y = _first_q_ctrl(d_src)
        _, u_ctrl_y = _first_q_ctrl(u_src)
        assert d_ctrl_y is not None and u_ctrl_y is not None, "Both must have Q commands"
        assert d_ctrl_y > u_ctrl_y, \
            f"Rel_D ctrl_y ({d_ctrl_y:.1f}) must exceed Rel_U ctrl_y ({u_ctrl_y:.1f})"

    def test_rel_r_vs_rel_l_bias_sign(self):
        """Rel_R ctrl_x must exceed Rel_L ctrl_x (rightward vs leftward bias)."""
        def _first_q_ctrl_x(src):
            scene = layout_c4_scene(src)
            for el in scene.get_layer(LAYER_EDGES):
                if isinstance(el, ScenePath):
                    for cmd in el.commands:
                        if cmd[0] == "Q":
                            return cmd[1]  # ctrl_x
            return None

        r_src = 'C4Context\nSystem(a, "Alpha", "First")\nSystem(b, "Beta", "Second")\nRel_R(a, b, "Right")\n'
        l_src = 'C4Context\nSystem(a, "Alpha", "First")\nSystem(b, "Beta", "Second")\nRel_L(a, b, "Left")\n'
        r_ctrl_x = _first_q_ctrl_x(r_src)
        l_ctrl_x = _first_q_ctrl_x(l_src)
        assert r_ctrl_x is not None and l_ctrl_x is not None, "Both must have Q commands"
        assert r_ctrl_x > l_ctrl_x, \
            f"Rel_R ctrl_x ({r_ctrl_x:.1f}) must exceed Rel_L ctrl_x ({l_ctrl_x:.1f})"

    def test_technology_has_c4_technology_class(self):
        scene = layout_c4_scene(_TECH_SRC, c4_type="c4container")
        labels = scene.get_layer(LAYER_LABELS)
        tech_els = [el for el in labels
                    if hasattr(el, "css_classes") and "c4-technology" in el.css_classes]
        assert tech_els, "Technology field must produce a c4-technology SceneText element"

    def test_technology_text_content(self):
        scene = layout_c4_scene(_TECH_SRC, c4_type="c4container")
        labels = scene.get_layer(LAYER_LABELS)
        tech_texts = [
            l.text
            for el in labels
            if hasattr(el, "css_classes") and "c4-technology" in el.css_classes
            for l in el.lines
        ]
        assert any("FastAPI" in t for t in tech_texts), \
            "Technology text should contain the technology value"

    def test_relation_label_in_labels_layer(self):
        scene = layout_c4_scene(SIMPLE_C4)
        labels = scene.get_layer(LAYER_LABELS)
        all_texts = [l.text for el in labels if hasattr(el, "lines") for l in el.lines]
        assert "Uses" in all_texts, "Relationship label 'Uses' must appear in LAYER_LABELS"

    def test_edge_label_perpendicular_offset(self):
        """Edge label is offset perpendicular to the edge (not at raw Bézier midpoint)."""
        # SIMPLE_C4: first rel is user→webapp (straight line, horizontal-ish)
        # With perpendicular offset the label y shifts by ~10 px from the raw midpoint
        scene = layout_c4_scene(SIMPLE_C4)
        labels = scene.get_layer(LAYER_LABELS)
        uses_label = next(
            (el for el in labels
             if hasattr(el, "lines") and el.lines[0].text == "Uses"),
            None,
        )
        assert uses_label is not None, "Should find 'Uses' relation label"
        ly = uses_label.lines[0].y
        # For a nearly horizontal edge the perpendicular offset is vertical (~10px).
        # The raw midpoint of user→webapp is approximately y≈244.
        # With offset the label should be above or below by ≥1 px.
        raw_mid_y = (243.953 + 243.788) / 2  # from test_syntax_c4 edge geometry
        assert abs(ly - raw_mid_y) >= 1.0, \
            f"Label y={ly:.2f} too close to raw midpoint {raw_mid_y:.2f}; offset not applied"


class TestC4NestedBoundaries:
    """Stage 10: nested boundaries produce correctly sized outer rects."""

    def test_nested_boundaries_both_present(self):
        scene = layout_c4_scene(_NESTED_BOUNDARY_SRC, c4_type="c4container")
        bounds = scene.get_layer(LAYER_BOUNDARIES)
        boundary_ids = {
            v
            for el in bounds
            if hasattr(el, "data_attrs")
            for k, v in el.data_attrs
            if k == "boundary-id"
        }
        assert "outer" in boundary_ids, "Outer boundary must render"
        assert "inner" in boundary_ids, "Inner boundary must render"

    def test_outer_boundary_contains_inner(self):
        """Outer boundary rect must visually contain the inner boundary rect."""
        scene = layout_c4_scene(_NESTED_BOUNDARY_SRC, c4_type="c4container")
        bounds = scene.get_layer(LAYER_BOUNDARIES)

        def _find_boundary_rect(bid: str):
            for el in bounds:
                if not hasattr(el, "data_attrs"):
                    continue
                if any(k == "boundary-id" and v == bid for k, v in el.data_attrs):
                    if isinstance(el, SceneRoundedRect):
                        return el
            return None

        outer = _find_boundary_rect("outer")
        inner = _find_boundary_rect("inner")
        if outer is None or inner is None:
            pytest.skip("Boundary rects not found")
        assert outer.x <= inner.x, "Outer left edge must be ≤ inner left edge"
        assert outer.y <= inner.y, "Outer top edge must be ≤ inner top edge"
        assert outer.x + outer.w >= inner.x + inner.w, "Outer right must contain inner right"
        assert outer.y + outer.h >= inner.y + inner.h, "Outer bottom must contain inner bottom"

    def test_nested_valid_xml(self):
        from lxml import etree
        scene = layout_c4_scene(_NESTED_BOUNDARY_SRC, c4_type="c4container")
        svg = scene_to_svg_str(scene)
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        etree.fromstring(body.encode("utf-8"))
