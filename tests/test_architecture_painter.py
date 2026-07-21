"""Tests for the native architecture-beta scene builder (layout/architecture.py)."""
from __future__ import annotations

import re

import pytest

from scripts.mermaid_render.layout.architecture import layout_architecture_scene
from scripts.mermaid_render.scene import (
    ScenePath, SceneRoundedRect, SceneText, SvgScene,
    LAYER_EDGES, LAYER_NODES, LAYER_LABELS,
)
from scripts.mermaid_render.svg_serializer import scene_to_svg_str
from scripts.mermaid_render.native_svg import dispatch_native


SIMPLE_ARCH = """\
architecture-beta
    service API(server)[API Gateway]
    service DB(database)[Database]
    service Cache(server)[Cache]
    API --> DB
    API --> Cache
"""

WITH_GROUPS = """\
architecture-beta
    group backend[Backend]
        service api(server)[API]
        service db(database)[DB]
    api --> db
"""


class TestArchitectureScene:
    def test_returns_svg_scene(self):
        scene = layout_architecture_scene(SIMPLE_ARCH)
        assert isinstance(scene, SvgScene)

    def test_diagram_type(self):
        assert layout_architecture_scene(SIMPLE_ARCH).diagram_type == "architecture-beta"

    def test_has_nodes(self):
        scene = layout_architecture_scene(SIMPLE_ARCH)
        nodes = scene.get_layer(LAYER_NODES)
        assert len(nodes) > 0

    def test_has_edges(self):
        scene = layout_architecture_scene(SIMPLE_ARCH)
        edges = scene.get_layer(LAYER_EDGES)
        assert len(edges) > 0

    def test_contains_service_labels(self):
        scene = layout_architecture_scene(SIMPLE_ARCH)
        labels = scene.get_layer(LAYER_LABELS)
        texts = [el.lines[0].text for el in labels if hasattr(el, "lines")]
        assert any("API" in t or "Database" in t or "Cache" in t for t in texts)

    def test_no_foreign_object(self):
        scene = layout_architecture_scene(SIMPLE_ARCH)
        svg = scene_to_svg_str(scene)
        assert "<foreignObject" not in svg

    def test_valid_xml(self):
        from lxml import etree
        scene = layout_architecture_scene(SIMPLE_ARCH)
        svg = scene_to_svg_str(scene)
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        etree.fromstring(body.encode("utf-8"))

    def test_deterministic(self):
        s1 = layout_architecture_scene(SIMPLE_ARCH)
        s2 = layout_architecture_scene(SIMPLE_ARCH)
        assert s1.scene_id == s2.scene_id

    def test_with_groups(self):
        scene = layout_architecture_scene(WITH_GROUPS)
        assert isinstance(scene, SvgScene)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="No services"):
            layout_architecture_scene("architecture-beta\n")

    def test_width_hint_respected(self):
        scene = layout_architecture_scene(SIMPLE_ARCH, width_hint=600)
        assert scene.width <= 600 + 1  # zoom down to fit


class TestArchitectureViaNative:
    def test_dispatch_native_produces_svg(self):
        svg = dispatch_native(SIMPLE_ARCH)
        assert "<svg" in svg

    def test_no_foreign_object_via_native(self):
        svg = dispatch_native(SIMPLE_ARCH)
        assert "<foreignObject" not in svg

    def test_labels_in_output(self):
        svg = dispatch_native(SIMPLE_ARCH)
        assert "API Gateway" in svg or "API" in svg
