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
    _tidy_tree_positions,
    _node_hw,
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


class TestTidyTreeLayout:
    """Tests for the tidy-tree layout (layout='tidy-tree')."""

    _SRC = SIMPLE_SRC  # root → Branch A (Leaf A1, Leaf A2) + Branch B (Leaf B1)

    _SRC_4CH = """\
mindmap
    root((Root))
        Alpha
            A1
        Beta
            B1
        Gamma
            G1
        Delta
            D1
"""

    _SRC_DEEP = """\
mindmap
    root((Root))
        Branch A
            Sub A
                Deep A
                    Leaf A
        Branch B
            Sub B
                Deep B
"""

    def _positions(self, src: str = None) -> dict:
        src = src or self._SRC
        flat = _parse_mindmap_source(src)
        min_d = min(n["depth"] for n in flat)
        for n in flat:
            n["depth"] -= min_d
        children, parent_of, tree_depth = _build_tree(flat)
        return _tidy_tree_positions(flat, children, tree_depth), flat, children, tree_depth

    # ── Algorithm correctness ──────────────────────────────────────────────────

    def test_root_at_origin(self):
        pos, flat, _, _ = self._positions()
        assert pos[0] == (0.0, 0.0)

    def test_right_children_have_positive_x(self):
        pos, flat, children, _ = self._positions()
        root_ch = children[0]
        right_idx = root_ch[0]  # even index 0 → right
        assert pos[right_idx][0] > 0.0, "Even-indexed root child should be right of root"

    def test_left_children_have_negative_x(self):
        pos, flat, children, _ = self._positions()
        root_ch = children[0]
        if len(root_ch) < 2:
            pytest.skip("Need at least 2 root children for left-side test")
        left_idx = root_ch[1]  # odd index 1 → left
        assert pos[left_idx][0] < 0.0, "Odd-indexed root child should be left of root"

    @pytest.mark.parametrize("src_attr,label", [
        ("_SRC", "simple"),
        ("_SRC_4CH", "four_children"),
        ("_SRC_DEEP", "deep"),
    ])
    def test_no_bounding_box_overlap(self, src_attr, label):
        pos, flat, _, tree_depth = self._positions(getattr(self, src_attr))
        n = len(flat)
        hw_list = [_node_hw(flat, tree_depth, i)[0] for i in range(n)]
        hh_list = [_node_hw(flat, tree_depth, i)[1] for i in range(n)]
        for i in range(n):
            xi, yi = pos[i]
            for j in range(i + 1, n):
                xj, yj = pos[j]
                x_overlap = min(xi + hw_list[i], xj + hw_list[j]) - max(xi - hw_list[i], xj - hw_list[j])
                y_overlap = min(yi + hh_list[i], yj + hh_list[j]) - max(yi - hh_list[i], yj - hh_list[j])
                if x_overlap > 0 and y_overlap > 0:
                    pytest.fail(
                        f"[{label}] Nodes {i} ({flat[i]['label']!r}) and {j} ({flat[j]['label']!r}) "
                        f"overlap: ({xi:.1f},{yi:.1f}) vs ({xj:.1f},{yj:.1f})"
                    )

    def test_four_children_split_two_two(self):
        pos, flat, children, _ = self._positions(self._SRC_4CH)
        root_ch = children[0]
        assert len(root_ch) == 4, "Expect 4 root children in _SRC_4CH"
        right_idxs = [root_ch[i] for i in range(0, 4, 2)]  # indices 0, 2
        left_idxs = [root_ch[i] for i in range(1, 4, 2)]   # indices 1, 3
        for idx in right_idxs:
            assert pos[idx][0] > 0.0
        for idx in left_idxs:
            assert pos[idx][0] < 0.0

    def test_deterministic_positions(self):
        pos1, _, _, _ = self._positions()
        pos2, _, _, _ = self._positions()
        assert pos1 == pos2

    # ── Scene construction ─────────────────────────────────────────────────────

    def test_returns_svg_scene(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        assert isinstance(scene, SvgScene)

    def test_diagram_type(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        assert scene.diagram_type == "mindmap"

    def test_has_nodes_layer(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        assert len(scene.get_layer(LAYER_NODES)) > 0

    def test_has_edges_layer(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        assert len(scene.get_layer(LAYER_EDGES)) > 0

    def test_labels_contain_root_text(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        texts = [el.lines[0].text for el in scene.get_layer(LAYER_LABELS) if hasattr(el, "lines")]
        assert "Central Topic" in texts

    def test_labels_contain_branch_text(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        texts = [el.lines[0].text for el in scene.get_layer(LAYER_LABELS) if hasattr(el, "lines")]
        assert "Branch A" in texts

    def test_edges_are_cubic_bezier(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        edges = scene.get_layer(LAYER_EDGES)
        for edge in edges:
            assert isinstance(edge, ScenePath)
            cmd_types = {c[0] for c in edge.commands}
            assert "C" in cmd_types, "tidy-tree edges should be cubic bezier (C)"

    def test_canvas_is_rectangle_not_necessarily_square(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        assert scene.width > 0 and scene.height > 0

    def test_deterministic_scene_id(self):
        s1 = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        s2 = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        assert s1.scene_id == s2.scene_id

    def test_scene_id_differs_from_radial(self):
        radial = layout_mindmap_scene(self._SRC)
        tidy = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        assert radial.scene_id != tidy.scene_id

    def test_serializes_to_valid_xml(self):
        from lxml import etree
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        svg = scene_to_svg_str(scene)
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        etree.fromstring(body.encode("utf-8"))

    def test_no_foreign_object(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        svg = scene_to_svg_str(scene)
        assert "<foreignObject" not in svg

    def test_all_labels_in_svg(self):
        scene = layout_mindmap_scene(self._SRC, layout="tidy-tree")
        svg = scene_to_svg_str(scene)
        for label in ("Central Topic", "Branch A", "Branch B", "Leaf A1", "Leaf A2", "Leaf B1"):
            assert label in svg, f"Label {label!r} missing from tidy-tree SVG"

    def test_empty_mindmap_raises(self):
        with pytest.raises(ValueError, match="No nodes"):
            layout_mindmap_scene("mindmap\n", layout="tidy-tree")

    # ── Radial layout not affected ─────────────────────────────────────────────

    def test_radial_unchanged_by_default(self):
        radial = layout_mindmap_scene(self._SRC)
        assert radial.width == radial.height, "Default radial must still produce square canvas"

    def test_radial_scene_id_stable(self):
        s1 = layout_mindmap_scene(self._SRC)
        s2 = layout_mindmap_scene(self._SRC)
        assert s1.scene_id == s2.scene_id

    # ── Frontmatter activation ─────────────────────────────────────────────────

    def test_activated_by_frontmatter_layout_key(self):
        from scripts.mermaid_render.native_svg import dispatch_native
        src_fm = f"---\nlayout: tidy-tree\n---\n{self._SRC}"
        tidy_svg = dispatch_native(src_fm)
        radial_svg = dispatch_native(self._SRC)
        assert "Central Topic" in tidy_svg
        assert tidy_svg != radial_svg, "tidy-tree frontmatter must produce different SVG from radial"

    def test_activated_by_frontmatter_config_key(self):
        # Primary documented activation form: config: { layout: tidy-tree }
        from scripts.mermaid_render.native_svg import dispatch_native
        src_fm = "---\nconfig: { layout: tidy-tree }\n---\n" + self._SRC
        tidy_svg = dispatch_native(src_fm)
        radial_svg = dispatch_native(self._SRC)
        assert "Central Topic" in tidy_svg
        assert tidy_svg != radial_svg, "config: {layout: tidy-tree} frontmatter must produce different SVG from radial"

    def test_activated_by_diagram_config(self):
        from scripts.mermaid_render.native_svg import dispatch_native
        src_dc = f'%%{{init: {{"layout": "tidy-tree"}}}}%%\n{self._SRC}'
        tidy_svg = dispatch_native(src_dc)
        radial_svg = dispatch_native(self._SRC)
        assert "Central Topic" in tidy_svg
        assert tidy_svg != radial_svg, "%%{init} layout tidy-tree must produce different SVG from radial"
