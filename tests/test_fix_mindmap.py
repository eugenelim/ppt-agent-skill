#!/usr/bin/env python3
"""Regression tests for the mindmap renderer fix.

Covers: radial spider layout, root circle shape, node shape syntax,
depth colour coding, markdown/annotation stripping, SVG edge presence,
and label visibility.

Import pattern mirrors tests/test_mermaid_layout.py (self-contained
sys.path.insert, no conftest.py dependency).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_layout import _dispatch


# ── helpers ───────────────────────────────────────────────────────────────────

def _render(src: str, width: int = 480) -> str:
    return _dispatch(src, None, width)


def _canvas_size(html: str) -> tuple[int, int]:
    """Return (width, height) of the outer diagram div."""
    m = re.search(r'width:(\d+)px;height:(\d+)px', html)
    assert m, "No canvas size found in HTML"
    return int(m.group(1)), int(m.group(2))


def _root_position(html: str) -> tuple[int, int]:
    """Return (left, top) px of the root node (data-node-id=0)."""
    m = re.search(r'data-node-id="0" style="position:absolute;left:(\d+)px;top:(\d+)px', html)
    assert m, "Root node position not found"
    return int(m.group(1)), int(m.group(2))


def _node_lefts(html: str) -> list[int]:
    """Return left-px values for all nodes, in data-node-id order."""
    pairs = re.findall(r'data-node-id="(\d+)" style="position:absolute;left:(\d+)px', html)
    pairs_sorted = sorted(pairs, key=lambda p: int(p[0]))
    return [int(left) for _, left in pairs_sorted]


# ── Group 1: Radial layout (not vertical tree) ────────────────────────────────

class TestRadialLayout:
    """Root must sit near the canvas centre, branches must spread outward."""

    _SRC = (
        "mindmap\n"
        "  root\n"
        "    Branch A\n"
        "      Leaf 1\n"
        "    Branch B\n"
        "      Leaf 2\n"
        "    Branch C\n"
        "      Leaf 3\n"
    )

    def test_root_near_horizontal_centre(self):
        """Root left + half_width must be close to canvas_w/2."""
        html = _render(self._SRC)
        canvas_w, _ = _canvas_size(html)
        left, _ = _root_position(html)
        # Root circle is 60px wide; centre = left + 30
        root_cx = left + 30
        assert abs(root_cx - canvas_w // 2) <= 5, (
            f"Root horizontal centre {root_cx} is not near canvas centre {canvas_w // 2}"
        )

    def test_root_near_vertical_centre(self):
        """Root top + half_height must be close to canvas_h/2."""
        html = _render(self._SRC)
        _, canvas_h = _canvas_size(html)
        _, top = _root_position(html)
        root_cy = top + 30
        assert abs(root_cy - canvas_h // 2) <= 5, (
            f"Root vertical centre {root_cy} is not near canvas centre {canvas_h // 2}"
        )

    def test_root_not_top_left_corner(self):
        """Old tree layout placed root at left:40, top:24 — must not recur."""
        html = _render(self._SRC)
        left, top = _root_position(html)
        assert left > 100, f"Root left={left} is in the top-left corner (old tree layout)"
        assert top > 100, f"Root top={top} is in the top-left corner (old tree layout)"

    def test_depth1_branches_have_distinct_left_positions(self):
        """Three branches should have three different left values (radial spread)."""
        html = _render(self._SRC)
        lefts_all = _node_lefts(html)
        # node indices 1, 2, 3 are Branch A, B, C (depth-1 siblings)
        branch_lefts = lefts_all[1:4]
        assert len(set(branch_lefts)) == 3, (
            f"Depth-1 branches must have distinct left positions; got {branch_lefts}"
        )

    def test_canvas_square(self):
        """Radial layout should produce a square canvas."""
        html = _render(self._SRC)
        w, h = _canvas_size(html)
        assert w == h, f"Radial canvas must be square; got {w}x{h}"


# ── Group 2: Node shapes ──────────────────────────────────────────────────────

class TestNodeShapes:
    """Mermaid mindmap shape syntax must map to visible CSS differences."""

    def test_root_circle_syntax_gives_border_radius_50(self):
        """root((text)) — root node with circle syntax renders with border-radius:50%."""
        html = _render("mindmap\n  root((Central))\n    A\n    B")
        assert "border-radius:50%" in html, (
            "root ((circle)) node must have border-radius:50%"
        )

    def test_non_root_circle_syntax_gives_border_radius_50(self):
        """id((text)) at depth-1 also gets border-radius:50%."""
        html = _render("mindmap\n  root\n    id((Disc Node))\n    B")
        assert "border-radius:50%" in html, (
            "Non-root ((circle)) node must have border-radius:50%"
        )

    def test_rect_syntax_gives_sharp_corners(self):
        """id[text] renders with a small (4px) border-radius, not a pill."""
        html = _render("mindmap\n  root\n    id[Rect Node]\n    B")
        assert "border-radius:4px" in html, (
            "id[rect] node must have border-radius:4px"
        )

    def test_rect_label_visible(self):
        html = _render("mindmap\n  root\n    id[Box Label]\n    B")
        assert "Box Label" in html

    def test_plain_label_uses_pill(self):
        """Nodes without explicit shape use the pill (large border-radius) style."""
        html = _render("mindmap\n  root\n    Plain Branch\n    B")
        assert "border-radius:var(--node-radius,16px)" in html

    def test_cloud_syntax_label_visible(self):
        """id))text(( cloud syntax: label must appear even though shape is exotic."""
        html = _render("mindmap\n  root\n    id))My Cloud((")
        assert "My Cloud" in html


# ── Group 3: Depth colour coding ─────────────────────────────────────────────

class TestDepthColours:
    """Different depth-1 branches get section colours; leaves get lighter tints."""

    _SRC = (
        "mindmap\n"
        "    root((Platform))\n"
        "        Frontend\n"
        "            React\n"
        "        Backend\n"
        "            API\n"
    )

    def test_section0_branch_colour(self):
        """First branch (section 0) must use the teal-green section colour."""
        html = _render(self._SRC)
        assert "rgba(53,148,103,0.08)" in html, (
            "Section-0 depth-1 branch must have rgba(53,148,103,0.08) background"
        )

    def test_section1_branch_different_colour(self):
        """Second branch (section 1) must use a different section colour."""
        html = _render(self._SRC)
        assert "rgba(99,102,241,0.08)" in html, (
            "Section-1 depth-1 branch must have rgba(99,102,241,0.08) background"
        )

    def test_leaf_lighter_than_branch(self):
        """Leaf nodes (depth>=2) get a lighter tint than their parent branch."""
        html = _render(self._SRC)
        assert "rgba(53,148,103,0.04)" in html, (
            "Section-0 leaves must have rgba(53,148,103,0.04) (lighter than 0.08)"
        )

    def test_leaf_alpha_le_006(self):
        """Leaf tint alpha must satisfy the <=0.06 contract."""
        html = _render(self._SRC)
        tints = re.findall(r'rgba\(53,148,103,([\d.]+)\)', html)
        assert tints, "At least one rgba(53,148,103,...) tint must be present"
        floats = [float(t) for t in tints]
        assert any(t <= 0.06 for t in floats), (
            f"Leaf tint must have alpha <= 0.06; found {floats}"
        )

    def test_root_uses_card_gradient(self):
        """Root node must use the card-bg-from gradient variable."""
        html = _render(self._SRC)
        assert "card-bg-from" in html, "Root node must use card-bg-from gradient"


# ── Group 4: Text and annotation stripping ────────────────────────────────────

class TestTextStripping:
    """Markdown markers and Mermaid annotations must not appear in rendered labels."""

    def test_markdown_bold_asterisks_stripped(self):
        """**bold** — the double-asterisk markers must be stripped from the label."""
        html = _render("mindmap\n  root\n    **Bold Topic**\n    B")
        assert "**" not in html, "Bold asterisks must be stripped from mindmap labels"
        assert "Bold Topic" in html, "Bold text content must appear after stripping"

    def test_markdown_italic_asterisks_stripped(self):
        """*italic* — single-asterisk markers must be stripped from the label."""
        html = _render("mindmap\n  root\n    *Italic Topic*\n    B")
        assert "*Italic Topic*" not in html, "Italic markers must be stripped"
        assert "Italic Topic" in html, "Italic text content must appear after stripping"

    def test_class_annotation_stripped(self):
        """:::classname — class annotation must not appear in the rendered label."""
        html = _render("mindmap\n  root\n    Important Topic:::urgent\n    B")
        assert ":::urgent" not in html, ":::classname annotation must be stripped"
        assert "Important Topic" in html, "Node label must appear after annotation strip"

    def test_icon_annotation_stripped(self):
        """::icon(fa:cloud) — icon annotation must not appear in the rendered label."""
        html = _render("mindmap\n  root\n    Cloud Topic::icon(fa:cloud)\n    B")
        assert "::icon" not in html, "::icon annotation must be stripped"
        assert "Cloud Topic" in html, "Node label must appear after icon annotation strip"


# ── Group 5: SVG edge layer ───────────────────────────────────────────────────

class TestSVGEdges:
    """Edges must be rendered as SVG <path> elements, one per parent-child pair."""

    _SRC = "mindmap\n  root\n    A\n      A1\n    B\n      B1"

    def test_svg_layer_present(self):
        html = _render(self._SRC)
        assert "<svg" in html, "SVG edge layer must be present"

    def test_path_elements_present(self):
        html = _render(self._SRC)
        paths = re.findall(r'<path\b', html)
        # 4 edges: root->A, A->A1, root->B, B->B1
        assert len(paths) >= 4, (
            f"Expected >=4 SVG path edges, got {len(paths)}"
        )

    def test_paths_use_bezier(self):
        """Edges must use quadratic bezier (Q command), not elbow joints."""
        html = _render(self._SRC)
        q_paths = re.findall(r'<path[^>]*d="M[^"]*Q[^"]*"', html)
        assert q_paths, "Edges must use quadratic bezier (Q) curves"

    def test_svg_drawn_before_nodes(self):
        """SVG layer must appear before node divs in the DOM (nodes render on top)."""
        html = _render(self._SRC)
        svg_idx = html.find('<svg')
        first_node_idx = html.find('<div class="node"')
        assert svg_idx < first_node_idx, (
            "SVG edge layer must precede node divs in the HTML"
        )


# ── Group 6: Label visibility ─────────────────────────────────────────────────

class TestLabelVisibility:
    """Every node label from the fixture files must appear in the rendered HTML."""

    def test_basic_fixture_all_labels(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "mindmap-basic.mmd").read_text()
        html = _render(src)
        expected = [
            "Platform", "Frontend", "React", "CSS",
            "Backend", "API", "Database",
            "DevOps", "CI/CD", "Monitoring",
        ]
        missing = [lbl for lbl in expected if lbl not in html]
        assert not missing, f"Labels missing from basic fixture HTML: {missing}"

    def test_deep_fixture_all_labels(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "mindmap-deep.mmd").read_text()
        html = _render(src)
        expected = [
            "Architecture", "Frontend", "React App", "State Mgmt",
            "Backend", "API Gateway", "Services", "Auth", "Data",
            "Infrastructure", "Docker", "Kubernetes",
        ]
        missing = [lbl for lbl in expected if lbl not in html]
        assert not missing, f"Labels missing from deep fixture HTML: {missing}"

    def test_deep_fixture_has_mermaid_layout_class(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "mindmap-deep.mmd").read_text()
        html = _render(src, 800)
        assert "diagram mermaid-layout" in html

    def test_deep_fixture_canvas_expanded_for_depth(self):
        """Deep fixture (depth-3) needs a larger canvas than width_hint alone."""
        src = (REPO_ROOT / "tests" / "fixtures" / "mindmap-deep.mmd").read_text()
        html = _render(src, 480)
        w, _ = _canvas_size(html)
        # depth-3: max_r = 85 + 3*70 = 295; min_side = 2*(295+90) = 770
        assert w >= 770, f"Deep fixture canvas {w} < 770 (needed for depth-3 radial)"
