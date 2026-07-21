"""Tests for the native mindmap scene layout (layout/mindmap.py)."""
from __future__ import annotations

import math
import re

import pytest

from scripts.mermaid_render.layout.mindmap import (
    layout_mindmap_scene,
    _parse_mindmap_source,
    _count_leaves,
    _build_tree,
    _radial_positions,
)
from scripts.mermaid_render.scene import (
    SceneCircle, SceneRoundedRect, SceneText, ScenePath, SvgScene,
    LAYER_EDGES, LAYER_NODES, LAYER_LABELS,
)
from scripts.mermaid_render.svg_serializer import scene_to_svg_str


SIMPLE_SRC = """\
mindmap
    root((Central Topic))
        Branch A
            Leaf A1
            Leaf A2
        Branch B
            Leaf B1
"""

RECT_SRC = """\
mindmap
    root[Root]
        Sub1
        Sub2
"""


class TestParser:
    def test_parses_labels(self):
        nodes = _parse_mindmap_source(SIMPLE_SRC)
        labels = [n["label"] for n in nodes]
        assert "Central Topic" in labels
        assert "Branch A" in labels
        assert "Leaf A1" in labels

    def test_root_is_circle_shape(self):
        nodes = _parse_mindmap_source(SIMPLE_SRC)
        assert nodes[0]["shape"] == "circle"

    def test_rect_shape_detected(self):
        nodes = _parse_mindmap_source(RECT_SRC)
        assert nodes[0]["shape"] == "rect"

    def test_depth_increases_for_children(self):
        src = """\
mindmap
    root((Root))
        Child
"""
        nodes = _parse_mindmap_source(src)
        # Child indentation depth should be greater than root's
        assert nodes[1]["depth"] > nodes[0]["depth"]

    def test_strips_markdown_bold(self):
        src = "mindmap\n    **Root**\n        **Child**\n"
        nodes = _parse_mindmap_source(src)
        for n in nodes:
            assert "**" not in n["label"]

    def test_empty_mindmap_returns_empty(self):
        nodes = _parse_mindmap_source("mindmap\n")
        assert nodes == []


class TestTreeBuild:
    def test_root_has_children(self):
        nodes = _parse_mindmap_source(SIMPLE_SRC)
        min_d = min(n["depth"] for n in nodes)
        for n in nodes:
            n["depth"] -= min_d
        children, parent_of, tree_depth = _build_tree(nodes)
        assert len(children[0]) > 0

    def test_leaf_count(self):
        nodes = _parse_mindmap_source(SIMPLE_SRC)
        min_d = min(n["depth"] for n in nodes)
        for n in nodes:
            n["depth"] -= min_d
        children, _, _ = _build_tree(nodes)
        # Root has 3 leaves total (A1, A2, B1)
        assert _count_leaves(0, children) == 3

    def test_tree_depth_root_is_zero(self):
        nodes = _parse_mindmap_source(SIMPLE_SRC)
        min_d = min(n["depth"] for n in nodes)
        for n in nodes:
            n["depth"] -= min_d
        _, _, tree_depth = _build_tree(nodes)
        assert tree_depth[0] == 0

    def test_leaves_have_highest_depth(self):
        nodes = _parse_mindmap_source(SIMPLE_SRC)
        min_d = min(n["depth"] for n in nodes)
        for n in nodes:
            n["depth"] -= min_d
        children, _, tree_depth = _build_tree(nodes)
        max_depth = max(tree_depth)
        # Leaf nodes (no children) should be at max depth
        leaf_depths = [tree_depth[i] for i in range(len(nodes)) if not children[i]]
        assert all(d == max_depth for d in leaf_depths)


class TestRadialLayout:
    def test_root_at_centre(self):
        nodes = _parse_mindmap_source(SIMPLE_SRC)
        min_d = min(n["depth"] for n in nodes)
        for n in nodes:
            n["depth"] -= min_d
        children, _, _ = _build_tree(nodes)
        cx, cy = 300.0, 300.0
        positions = _radial_positions(children, cx, cy)
        assert positions[0] == (cx, cy)

    def test_depth1_nodes_equidistant_from_root(self):
        # Depth-1 nodes are placed at _BASE_R + 1*_STEP_R from root
        src = "mindmap\n    root((Root))\n        A\n        B\n        C\n"
        nodes = _parse_mindmap_source(src)
        min_d = min(n["depth"] for n in nodes)
        for n in nodes:
            n["depth"] -= min_d
        children, parent_of, tree_depth = _build_tree(nodes)
        cx, cy = 300.0, 300.0
        positions = _radial_positions(children, cx, cy)
        from scripts.mermaid_render.layout.mindmap import _BASE_R, _STEP_R
        expected_r = _BASE_R + 1 * _STEP_R  # depth param starts at 1 for root's children
        for i in range(1, len(nodes)):
            if tree_depth[i] == 1:
                px, py = positions[i]
                dist = math.hypot(px - cx, py - cy)
                assert abs(dist - expected_r) < 1.0, f"node {i} at dist {dist}, expected {expected_r}"

    def test_all_nodes_have_positions(self):
        nodes = _parse_mindmap_source(SIMPLE_SRC)
        min_d = min(n["depth"] for n in nodes)
        for n in nodes:
            n["depth"] -= min_d
        children, _, _ = _build_tree(nodes)
        positions = _radial_positions(children, 300.0, 300.0)
        assert len(positions) == len(nodes)


class TestLayoutMindmapScene:
    def test_returns_svg_scene(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        assert isinstance(scene, SvgScene)

    def test_diagram_type_is_mindmap(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        assert scene.diagram_type == "mindmap"

    def test_square_canvas(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        assert scene.width == scene.height

    def test_width_hint_respected(self):
        scene = layout_mindmap_scene(SIMPLE_SRC, width_hint=800)
        assert scene.width >= 800

    def test_has_nodes_layer(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        assert len(nodes) > 0

    def test_has_edges_layer(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        edges = scene.get_layer(LAYER_EDGES)
        assert len(edges) > 0

    def test_has_labels(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        labels = scene.get_layer(LAYER_LABELS)
        assert len(labels) > 0

    def test_labels_contain_root_text(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        labels = scene.get_layer(LAYER_LABELS)
        texts = [el.lines[0].text for el in labels if hasattr(el, "lines")]
        assert "Central Topic" in texts

    def test_labels_contain_branch_text(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        labels = scene.get_layer(LAYER_LABELS)
        texts = [el.lines[0].text for el in labels if hasattr(el, "lines")]
        assert "Branch A" in texts

    def test_root_is_circle(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        circles = [el for el in nodes if isinstance(el, SceneCircle)]
        assert len(circles) >= 1

    def test_edges_are_curved_paths(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        edges = scene.get_layer(LAYER_EDGES)
        for edge in edges:
            assert isinstance(edge, ScenePath)
            cmd_types = {c[0] for c in edge.commands}
            assert "Q" in cmd_types or "C" in cmd_types, "edges should be curved"

    def test_scene_id_is_deterministic(self):
        scene1 = layout_mindmap_scene(SIMPLE_SRC)
        scene2 = layout_mindmap_scene(SIMPLE_SRC)
        assert scene1.scene_id == scene2.scene_id

    def test_empty_mindmap_raises(self):
        with pytest.raises(ValueError, match="No nodes"):
            layout_mindmap_scene("mindmap\n")

    def test_serializes_to_valid_xml(self):
        from lxml import etree
        scene = layout_mindmap_scene(SIMPLE_SRC)
        svg = scene_to_svg_str(scene)
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        etree.fromstring(body.encode("utf-8"))

    def test_no_foreign_object(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        svg = scene_to_svg_str(scene)
        assert "<foreignObject" not in svg

    def test_contains_label_text(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        svg = scene_to_svg_str(scene)
        assert "Central Topic" in svg

    def test_section_colors_used(self):
        scene = layout_mindmap_scene(SIMPLE_SRC)
        svg = scene_to_svg_str(scene)
        # Depth-1 branches should have section fill colors
        assert "rgba(53,148,103" in svg or "rgba(99,102,241" in svg

    def test_rect_shape_produces_rounded_rect(self):
        scene = layout_mindmap_scene(RECT_SRC)
        nodes = scene.get_layer(LAYER_NODES)
        rects = [el for el in nodes if isinstance(el, SceneRoundedRect)]
        assert len(rects) >= 1
