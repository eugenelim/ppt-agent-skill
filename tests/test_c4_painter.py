"""Tests for the native C4 scene builder (layout/c4_layout.py)."""
from __future__ import annotations

import re

import pytest

from scripts.mermaid_render.layout.c4_layout import (
    layout_c4_scene, _parse_c4_source,
)
from scripts.mermaid_render.scene import (
    ScenePath, SceneRoundedRect, SceneText, SvgScene,
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
