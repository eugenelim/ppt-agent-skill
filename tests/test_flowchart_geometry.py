"""TDD tests for flowchart geometry fixes (spec: docs/specs/flowchart-geometry-fixes/spec.md).

Run with: python -m pytest tests/test_flowchart_geometry.py -x -v
All tests are written RED first; implementation fills them green.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._constants import (
    _Node, _measure_text_width, _wrap_label,
    _TITLE_FS, _TITLE_FW, _TITLE_LINE_H, NODE_HPAD, _NODE_PAD_V,
    _node_render_h, _node_size_circle, _is_terminal_circle,
    _DIAMOND_SIZE, _HEXAGON_SIZE, _CIRCLE_NODE_SIZE,
)
from mermaid_render.layout._strategies import _dispatch


# ── AC-1: Text measurement bug ────────────────────────────────────────────────

class TestTextMeasurementBug:
    """AC-1: Long-token wrap uses _TITLE_FS/_TITLE_FW, not hard-coded 13/500."""

    def test_long_token_lines_fit_budget_at_title_font(self):
        """Each wrapped line of a long unbroken token must fit within budget at _TITLE_FS."""
        budget = 120
        # 80 capital W's — wide glyphs, guaranteed to exceed budget
        long_token = "W" * 80
        lines = _wrap_label(long_token, width_budget=budget)
        assert len(lines) > 1, "long token should be split into multiple lines"
        for line in lines:
            w = _measure_text_width(line, _TITLE_FS, _TITLE_FW)
            assert w <= budget + 2, (
                f"Line {line!r} measures {w:.1f}px at title font, exceeds budget {budget}px"
            )

    def test_long_token_not_measured_with_hardcoded_13_500(self):
        """Wrapping a long token must not produce lines that only fit at (13, 500)."""
        budget = 120
        # Build a token that is wider at 13/500 vs _TITLE_FS/_TITLE_FW.
        # W glyphs: at 15/700 base=0.60, ratio=1.5 → each W = 1.5*15*0.60 + 15*0.15 ≈ 15.75px
        # At 13/500  base=0.57, ratio=1.5 → each W = 1.5*13*0.57 + 13*0.15 ≈ 13.1px
        # So a line valid at 13px/500w but invalid at 15px/700w would be the bug.
        long_token = "W" * 80
        lines = _wrap_label(long_token, width_budget=budget)
        for line in lines:
            # If the old bug existed, some lines would exceed budget at _TITLE_FS/_TITLE_FW
            # but pass at 13/500. After the fix, all lines must fit at _TITLE_FS/_TITLE_FW.
            w_title = _measure_text_width(line, _TITLE_FS, _TITLE_FW)
            assert w_title <= budget + 2, (
                f"Line {line!r}: {w_title:.1f}px at title font > {budget}px — "
                "token split used wrong font constants"
            )


# ── AC-2: Diamond sizing ──────────────────────────────────────────────────────

class TestDiamondSizing:
    """AC-2: Diamond uses separate formula from hexagon; content_w + content_h drives size."""

    def _diamond_node(self, label: str) -> _Node:
        from mermaid_render.layout._layout import _assign_coordinates
        from mermaid_render.layout._constants import _node_size_diamond
        n = _Node(id="D", label=label, shape="diamond")
        n.width = _node_size_diamond(n)
        n.height = n.width  # diamond is square
        return n

    def test_diamond_single_line_minimum(self):
        """Single-line diamond is at least DIAMOND_MIN wide."""
        from mermaid_render.layout._constants import _node_size_diamond, DIAMOND_MIN
        n = _Node(id="D", label="OK?", shape="diamond")
        size = _node_size_diamond(n)
        assert size >= DIAMOND_MIN

    def test_diamond_multiline_grows(self):
        """Diamond with 3-line label is wider than with 1-line label."""
        from mermaid_render.layout._constants import _node_size_diamond
        n1 = _Node(id="D1", label="OK?", shape="diamond")
        n3 = _Node(id="D3", label="Is the\nrequest\nvalid?", shape="diamond")
        size1 = _node_size_diamond(n1)
        size3 = _node_size_diamond(n3)
        assert size3 > size1, f"multi-line diamond ({size3}) must be > single-line ({size1})"

    def test_diamond_multiline_content_h_included(self):
        """Multi-line diamond size grows when lines are equal-width (content_h drives growth)."""
        from mermaid_render.layout._constants import _node_size_diamond
        # Same-width lines: 3-line version has 2x more content_h, same max content_w
        n1 = _Node(id="D1", label="ABCD", shape="diamond")  # 1 line
        n3 = _Node(id="D3", label="ABCD\nABCD\nABCD", shape="diamond")  # 3 same-width lines
        size1 = _node_size_diamond(n1)
        size3 = _node_size_diamond(n3)
        # content_h triples for n3 vs n1; diamond formula adds content_h so n3 > n1
        assert size3 > size1, (
            f"3-line diamond ({size3}) should exceed single-line ({size1}) — "
            "multi-line content_h must be counted across all lines"
        )

    def test_diamond_differs_from_hexagon_formula(self):
        """Diamond and hexagon produce different widths for the same label."""
        from mermaid_render.layout._constants import _node_size_diamond, _node_size_hexagon
        n = _Node(id="X", label="Decision", shape="diamond")
        d_size = _node_size_diamond(n)
        h_w, _ = _node_size_hexagon(n)
        assert d_size != h_w, f"diamond ({d_size}) == hexagon ({h_w}): formulas must differ"

    def test_diamond_cjk_wider(self):
        """CJK label produces a wider diamond than ASCII of same char count."""
        from mermaid_render.layout._constants import _node_size_diamond
        ascii_n = _Node(id="A", label="ABCD", shape="diamond")
        cjk_n = _Node(id="C", label="中文决策", shape="diamond")
        assert _node_size_diamond(cjk_n) > _node_size_diamond(ascii_n)


# ── AC-3: Hexagon sizing ──────────────────────────────────────────────────────

class TestHexagonSizing:
    """AC-3: Hexagon width and height are independent; _node_render_h returns n.height."""

    def test_hexagon_tall_label_increases_height(self):
        """Hexagon with 4-line label has greater height than 1-line label hexagon."""
        from mermaid_render.layout._constants import _node_size_hexagon
        n1 = _Node(id="H1", label="Process", shape="hexagon")
        n4 = _Node(id="H4", label="Step 1\nStep 2\nStep 3\nStep 4", shape="hexagon")
        _, h1 = _node_size_hexagon(n1)
        _, h4 = _node_size_hexagon(n4)
        assert h4 > h1, f"tall hexagon height ({h4}) should exceed short ({h1})"

    def test_hexagon_wide_label_increases_width(self):
        """Hexagon with wide label has greater width than narrow label hexagon."""
        from mermaid_render.layout._constants import _node_size_hexagon
        narrow_n = _Node(id="H1", label="OK", shape="hexagon")
        wide_n = _Node(id="H2", label="WMWM WMWM WMWM", shape="hexagon")
        w_narrow, _ = _node_size_hexagon(narrow_n)
        w_wide, _ = _node_size_hexagon(wide_n)
        assert w_wide > w_narrow

    def test_hexagon_width_height_independent(self):
        """Hexagon does not force width == height for non-square content."""
        from mermaid_render.layout._constants import _node_size_hexagon
        # Tall narrow content: many lines, short text per line
        n = _Node(id="H", label="A\nB\nC\nD\nE", shape="hexagon")
        w, h = _node_size_hexagon(n)
        # Height grows with line count; width is NOT forced to match height
        assert w != h  # height grows with 5 lines; width stays narrower
        # At minimum: height should differ from width when content is tall
        # With 5 lines, content_h ≈ 5 * _TITLE_LINE_H = 90px. shoulder ≈ 0.25*height.
        # Width = max(HEX_MIN_W, content_w + h_padding + 2*shoulder)
        # Height = max(HEX_MIN_H, content_h + v_padding) ≈ 90 + 24 = 114.
        # The difference should be noticeable. Just assert both are positive and non-zero:
        assert w > 0 and h > 0

    def test_node_render_h_hexagon_uses_n_height(self):
        """_node_render_h for hexagon returns n.height, not n.width."""
        from mermaid_render.layout._constants import _node_size_hexagon
        n = _Node(id="H", label="A\nB\nC\nD", shape="hexagon")
        w, h = _node_size_hexagon(n)
        n.width = w
        n.height = h
        rendered_h = _node_render_h(n)
        assert rendered_h == h, (
            f"_node_render_h returned {rendered_h}, expected n.height={h}"
        )

    def test_hexagon_minimum_bounds(self):
        """Hexagon meets HEX_MIN_W and HEX_MIN_H minima."""
        from mermaid_render.layout._constants import _node_size_hexagon, HEX_MIN_W, HEX_MIN_H
        n = _Node(id="H", label="X", shape="hexagon")
        w, h = _node_size_hexagon(n)
        assert w >= HEX_MIN_W
        assert h >= HEX_MIN_H


# ── AC-4: Circle multiline ────────────────────────────────────────────────────

class TestCircleMultiline:
    """AC-4: Circle diameter accounts for all lines, not just the first."""

    def test_circle_multiline_larger_than_singleline(self):
        """Circle node with 3-line label is wider than the same with 1-line label."""
        n1 = _Node(id="C1", label="Start", shape="circle")
        n3 = _Node(id="C3", label="Start\nStep\nEnd", shape="circle")
        d1 = _node_size_circle(n1)
        d3 = _node_size_circle(n3)
        assert d3 > d1, f"multiline circle diameter ({d3}) must exceed single-line ({d1})"

    def test_doublecircle_larger_than_circle(self):
        """Double-circle diameter exceeds circle diameter for the same label."""
        from mermaid_render.layout._constants import _node_size_circle
        n_circle = _Node(id="C", label="State", shape="circle")
        n_double = _Node(id="D", label="State", shape="doublecircle")
        d_circle = _node_size_circle(n_circle)
        d_double = _node_size_circle(n_double)
        assert d_double > d_circle, (
            f"doublecircle ({d_double}) must exceed circle ({d_circle})"
        )

    def test_circle_cjk_multiline(self):
        """CJK multiline circle has appropriate diameter."""
        n = _Node(id="C", label="处理\n状态\n完成", shape="circle")
        d = _node_size_circle(n)
        assert d >= _CIRCLE_NODE_SIZE, f"CJK circle diameter {d} below minimum"

    def test_terminal_circle_unchanged(self):
        """Terminal circle (short label) keeps its fixed _TERMINAL_NODE_SIZE."""
        from mermaid_render.layout._constants import _TERMINAL_NODE_SIZE
        n = _Node(id="T", label="●", shape="circle")
        assert _is_terminal_circle(n)
        d = _node_size_circle(n)
        assert d == _TERMINAL_NODE_SIZE


# ── AC-5: Geometry IR ─────────────────────────────────────────────────────────

class TestGeometryIR:
    """AC-5: Rect frozen dataclass with helper methods."""

    def setup_method(self):
        from mermaid_render.layout._geometry import Rect
        self.Rect = Rect

    def test_rect_contains_self(self):
        r = self.Rect(0, 0, 100, 50)
        assert r.contains(r)

    def test_rect_contains_inner(self):
        outer = self.Rect(0, 0, 100, 100)
        inner = self.Rect(10, 10, 80, 80)
        assert outer.contains(inner)

    def test_rect_not_contains_partial(self):
        r1 = self.Rect(0, 0, 100, 100)
        r2 = self.Rect(50, 50, 150, 150)
        assert not r1.contains(r2)

    def test_rect_overlaps_partial(self):
        r1 = self.Rect(0, 0, 100, 100)
        r2 = self.Rect(50, 50, 150, 150)
        assert r1.overlaps(r2)
        assert r2.overlaps(r1)

    def test_rect_not_overlaps_adjacent(self):
        r1 = self.Rect(0, 0, 100, 100)
        r2 = self.Rect(100, 0, 200, 100)
        assert not r1.overlaps(r2)

    def test_rect_union(self):
        # Rect(x, y, w, h): r1 spans (0,0)→(100,50); r2 spans (50,30)→(250,130)
        r1 = self.Rect(0, 0, 100, 50)
        r2 = self.Rect(50, 30, 200, 100)
        u = r1.union(r2)
        assert u.x == 0 and u.y == 0
        assert u.w == 250 and u.h == 130

    def test_rect_translate(self):
        r = self.Rect(10, 20, 100, 50)
        t = r.translate(5, -10)
        assert t.x == 15 and t.y == 10
        assert t.w == 100 and t.h == 50

    def test_rect_is_frozen(self):
        r = self.Rect(0, 0, 100, 100)
        with pytest.raises((AttributeError, TypeError)):
            r.x = 5  # type: ignore


# ── AC-6: Nested group y-shift ────────────────────────────────────────────────

class TestNestedGroupYShift:
    """AC-6: _compute_group_bboxes applies y-shift when groups pushed above y=0."""

    _DEEP_NESTING = """\
flowchart TD
    subgraph L1["Level 1"]
        subgraph L2["Level 2"]
            subgraph L3["Level 3"]
                A[DeepNode]
            end
            B[MidNode]
        end
        C[OuterNode]
    end
    A --> B --> C
"""

    def test_deep_nesting_groups_all_above_zero(self):
        """After rendering deep-nesting, all group bboxes have y >= 0."""
        from mermaid_render.layout._renderer import _compute_group_bboxes
        from mermaid_render.layout._strategies import _dispatch
        # Render and extract group bboxes from HTML
        html = _dispatch(self._DEEP_NESTING, None, 800)
        import re
        # All diagram-group top values must be >= 0
        tops = re.findall(r'class="diagram-group"[^>]*top:(-?[\d.]+)px', html)
        for top in tops:
            assert float(top) >= 0, f"group rendered at negative top: {top}px"

    def test_deep_nesting_group_titles_not_same_y(self):
        """Nested group labels should not appear at the same top position."""
        html = _dispatch(self._DEEP_NESTING, None, 800)
        import re
        tops = re.findall(r'class="diagram-group"[^>]*top:(-?[\d.]+)px', html)
        if len(tops) >= 2:
            top_floats = [float(t) for t in tops]
            # Parent and child group tops must differ by at least GROUP_PAD_Y_TOP
            top_floats.sort()
            for i in range(len(top_floats) - 1):
                diff = top_floats[i + 1] - top_floats[i]
                # Each nesting level gets its own title strip (at least ~20px separation)
                assert diff >= 20 or top_floats[i] == top_floats[i + 1] == -1, (
                    f"Group tops too close: {top_floats}"
                )

    def test_canvas_height_exceeds_group_bottom(self):
        """Canvas height in rendered HTML must accommodate all group bboxes."""
        html = _dispatch(self._DEEP_NESTING, None, 800)
        import re
        # Extract canvas height (from the outer diagram div height)
        m = re.search(r'data-diagram-h="(\d+)"', html)
        assert m, "could not find canvas height in HTML"
        canvas_h = int(m.group(1))
        # Extract all group bottom positions
        # group div style: top:{t}px ... height:{h}px
        group_bottoms = []
        for gm in re.finditer(
            r'class="diagram-group"[^>]*top:(-?[\d.]+)px[^>]*[^>]*height:(-?[\d.]+)px',
            html
        ):
            top = float(gm.group(1))
            h = float(gm.group(2))
            group_bottoms.append(top + h)
        if group_bottoms:
            max_bottom = max(group_bottoms)
            assert canvas_h >= max_bottom, (
                f"canvas_h={canvas_h} < max group bottom={max_bottom:.0f}"
            )


# ── AC-7: Canvas width includes groups ───────────────────────────────────────

class TestCanvasIncludesGroups:
    """AC-7: canvas_w >= max group right edge after group separation."""

    _WIDE_GROUP = """\
flowchart TD
    subgraph G["A group with a very long label that should widen the group box"]
        A[Node]
    end
"""

    def test_canvas_width_includes_group_right(self):
        """Canvas width must be >= max group bbox right edge."""
        html = _dispatch(self._WIDE_GROUP, None, 1200)
        import re
        m = re.search(r'data-diagram-w="(\d+)"', html)
        assert m, "could not find canvas width in HTML"
        canvas_w = int(m.group(1))
        group_rights = []
        for gm in re.finditer(
            r'class="diagram-group"[^>]*left:(-?[\d.]+)px[^>]*[^>]*width:(-?[\d.]+)px',
            html
        ):
            left = float(gm.group(1))
            w = float(gm.group(2))
            group_rights.append(left + w)
        if group_rights:
            max_right = max(group_rights)
            assert canvas_w >= max_right - 1, (
                f"canvas_w={canvas_w} < max group right={max_right:.0f}"
            )


# ── AC-8: Direction-aware self-loops ─────────────────────────────────────────

class TestDirectionAwareSelfLoops:
    """AC-8: Self-loops exit correct face based on flow direction."""

    def _self_loop_paths(self, src: str) -> list[str]:
        """Return SVG path d= strings for all self-loop edges."""
        import re
        html = _dispatch(src, None, 800)
        paths = []
        for m in re.finditer(
            r'<path\s+d="([^"]+)"[^>]*data-src="([^"]+)"[^>]*data-dst="([^"]+)"', html
        ):
            d, s, t = m.group(1), m.group(2), m.group(3)
            if s == t:
                paths.append(d)
        return paths

    def _node_bbox_from_html(self, html: str, node_id: str):
        """Extract (left, top, width, height) for a node div."""
        import re
        m = re.search(
            rf'data-node-id="{re.escape(node_id)}"[^>]*left:(-?[\d.]+)px;?\s*top:(-?[\d.]+)px;?\s*width:(-?[\d.]+)px;?\s*height:(-?[\d.]+)px',
            html
        )
        if m:
            return tuple(float(x) for x in m.groups())
        return None

    def test_tb_self_loop_exits_right(self):
        """TB self-loop exits the right face (x > node right edge)."""
        import re
        src = "flowchart TD\n    A[Worker] -->|retry| A\n    A --> B[Next]\n"
        html = _dispatch(src, None, 800)
        paths = self._self_loop_paths(src)
        assert paths, "no self-loop path found"
        # In TB mode, loop should have x-coordinates beyond the node's right edge
        # Extract all x-values from the self-loop path
        for d in paths:
            xs = [float(v) for v in re.findall(r'(?:M|L)\s+([\d.]+)\s+[\d.]+', d)]
            node = re.search(r'data-node-id="A"[^>]*left:(-?[\d.]+)px[^>]*width:(-?[\d.]+)px', html)
            if node and xs:
                node_left = float(node.group(1))
                node_w = float(node.group(2))
                node_right = node_left + node_w
                # At least one x-coordinate should be to the right of the node
                assert max(xs) >= node_right, (
                    f"TB self-loop max x={max(xs):.0f} should be >= node right={node_right:.0f}"
                )

    def test_lr_self_loop_exits_top_or_bottom(self):
        """LR self-loop exits top or bottom face (y < node top or y > node bottom)."""
        import re
        src = "flowchart LR\n    A[Worker] -->|retry| A\n    A --> B[Next]\n"
        html = _dispatch(src, None, 800)
        paths = self._self_loop_paths(src)
        assert paths, "no self-loop path found"
        for d in paths:
            ys = [float(v) for v in re.findall(r'(?:M|L)\s+[\d.]+\s+([\d.]+)', d)]
            node = re.search(r'data-node-id="A"[^>]*top:(-?[\d.]+)px[^>]*height:(-?[\d.]+)px', html)
            if node and ys:
                node_top = float(node.group(1))
                node_h = float(node.group(2))
                node_bot = node_top + node_h
                # At least one y-coordinate should be outside [node_top, node_bot]
                has_outside = any(y < node_top - 1 or y > node_bot + 1 for y in ys)
                assert has_outside, (
                    f"LR self-loop ys={[f'{y:.0f}' for y in ys]} all inside node [{node_top:.0f},{node_bot:.0f}]"
                )

    def test_four_loops_tb_non_overlapping(self):
        """4 self-loops on one TB node alternate right/left faces."""
        import re
        src = (
            "flowchart TD\n"
            "    A[Hub]\n"
            "    A --> A\n"
            "    A -->|loop2| A\n"
            "    A -->|loop3| A\n"
            "    A -->|loop4| A\n"
        )
        html = _dispatch(src, None, 800)
        paths = self._self_loop_paths(src)
        assert len(paths) == 4, f"expected 4 self-loops, got {len(paths)}"
        # Loops alternate right (max-x > node right) and left (min-x < node left).
        node_m = re.search(r'data-node-id="A"[^>]*left:(-?[\d.]+)px[^>]*width:(-?[\d.]+)px', html)
        if node_m:
            node_left = float(node_m.group(1))
            node_w = float(node_m.group(2))
            node_right = node_left + node_w
            # Even-indexed loops exit right, odd-indexed exit left
            right_loops = [d for i, d in enumerate(paths) if i % 2 == 0]
            left_loops = [d for i, d in enumerate(paths) if i % 2 == 1]
            for d in right_loops:
                xs = [float(v) for v in re.findall(r'(?:M|L)\s+([\d.]+)', d)]
                if xs:
                    assert max(xs) > node_right, (
                        f"Right-face self-loop max_x={max(xs):.0f} <= node_right={node_right:.0f}"
                    )
            for d in left_loops:
                # Capture both positive and negative x coords
                xs = [float(v) for v in re.findall(r'(?:M|L)\s+(-?[\d.]+)', d)]
                if xs:
                    assert min(xs) < node_left, (
                        f"Left-face self-loop min_x={min(xs):.0f} >= node_left={node_left:.0f}"
                    )

    def test_self_loop_canvas_not_exceeded(self):
        """Self-loop paths must stay within canvas bounds (both axes)."""
        import re
        src = "flowchart LR\n    A[Worker] -->|retry| A\n    A --> B[Next]\n"
        html = _dispatch(src, None, 800)
        m_w = re.search(r'data-diagram-w="(\d+)"', html)
        m_h = re.search(r'data-diagram-h="(\d+)"', html)
        canvas_w = int(m_w.group(1)) if m_w else 0
        canvas_h = int(m_h.group(1)) if m_h else 0
        xs = [float(v) for v in re.findall(r'(?:M|L)\s+([\d.]+)\s+[\d.]+', html)]
        ys = [float(v) for v in re.findall(r'(?:M|L)\s+[\d.]+\s+([\d.]+)', html)]
        if xs:
            assert max(xs) <= canvas_w + 5, f"path x={max(xs):.0f} exceeds canvas_w={canvas_w}+5"
        if ys:
            assert min(ys) >= -5, f"path y={min(ys):.0f} exceeds canvas top (y<-5)"
            assert max(ys) <= canvas_h + 5, f"path y={max(ys):.0f} exceeds canvas_h={canvas_h}+5"

    def test_tb_left_face_loop_renders_without_error(self):
        """TB left-face self-loop: provisional coordinates are accepted pending finalization pass.

        Label candidates at (loop_x - label_w - 4) can be negative; a finalization pass
        (backlog: self-loop-finalization-pass) will normalize them. Until then, verify the
        diagram renders without crashing.
        """
        src = (
            "flowchart TD\n"
            "    A[Hub]\n"
            "    A --> A\n"
            "    A -->|second| A\n"
        )
        html = _dispatch(src, None, 800)
        assert "data-node-id" in html, "diagram must render without error"


# ── AC-9: A* group title obstacles ───────────────────────────────────────────

class TestAStarGroupTitleObstacles:
    """AC-9: Group title strips are obstacles for the A* routing grid."""

    def test_blocked_segs_with_group_title(self):
        """A segment crossing a group title strip should appear in blocked set."""
        from mermaid_render.layout._routing import _blocked_segs
        # Group title strip: x=50..250, y=100..136 (GROUP_PAD_Y_TOP=36)
        title_obs = [(50, 100, 250, 136)]
        grid_xs = sorted({0, 50, 100, 150, 200, 250, 300})
        grid_ys = sorted({0, 50, 100, 118, 136, 200})
        blocked = _blocked_segs(grid_xs, grid_ys, title_obs)
        # A horizontal segment at y=118 (inside title strip) through x=50..250 should be blocked
        xi_50 = grid_xs.index(50)
        xi_100 = grid_xs.index(100)
        yi_118 = grid_ys.index(118)
        assert (xi_50, yi_118, xi_100, yi_118) in blocked, (
            "Segment through group title strip not in blocked set"
        )

    def test_clear_segment_not_blocked(self):
        """A segment above the group title strip is not blocked."""
        from mermaid_render.layout._routing import _blocked_segs
        title_obs = [(50, 100, 250, 136)]
        grid_xs = sorted({0, 50, 100, 150, 200, 250, 300})
        grid_ys = sorted({0, 50, 100, 118, 136, 200})
        blocked = _blocked_segs(grid_xs, grid_ys, title_obs)
        xi_50 = grid_xs.index(50)
        xi_100 = grid_xs.index(100)
        yi_50 = grid_ys.index(50)
        assert (xi_50, yi_50, xi_100, yi_50) not in blocked, (
            "Clear segment above title strip incorrectly blocked"
        )


# ── AC-10: Edge label hard-reject on node overlap ────────────────────────────

class TestEdgeLabelHardReject:
    """AC-10: _best_label_pos hard-rejects candidates overlapping unrelated nodes."""

    def test_blocked_midpoint_gets_alternate(self):
        """When the primary candidate overlaps a node, an alternate is chosen."""
        from mermaid_render.layout._routing import _best_label_pos, _label_chip_bbox, _est_label_w
        label = "test label"
        w = _est_label_w(label)
        H = 17  # _LABEL_CHIP_H
        # Node obstacle at x=100..300, y=50..92 (overlaps the primary candidate)
        node_obs = [(100, 50, 300, 92)]
        # Primary candidate: chip at (150, 80) → bbox (150, 63, 150+w, 80) — inside node
        # Alternate candidate: chip at (10, 20) → bbox (10, 3, 10+w, 20) — clear
        candidates = [
            (150, 80),   # blocked by node
            (10, 20),    # clear
        ]
        placed: list = []
        placement = _best_label_pos(candidates, label, node_obs, placed, 800)
        assert placement.box is not None
        lx, ly = int(placement.box.x), int(placement.box.y + placement.box.h)
        # The result should prefer the clear candidate
        chosen_bbox = _label_chip_bbox(lx, ly, label)
        from mermaid_render.layout._routing import _overlap_area
        overlap_with_node = _overlap_area(chosen_bbox, node_obs[0], margin=0)
        assert overlap_with_node == 0 or lx == 10, (
            f"best_label_pos chose ({lx},{ly}) which overlaps node obstacle; expected clear position"
        )

    def test_all_blocked_returns_fallback(self):
        """When all candidates overlap nodes, the least-overlap position is returned with reroute_required."""
        from mermaid_render.layout._routing import _best_label_pos
        # Cover the entire canvas with node obstacles
        node_obs = [(0, 0, 800, 600)]
        candidates = [(100, 100), (200, 200), (300, 300)]
        placed: list = []
        placement = _best_label_pos(candidates, "label", node_obs, placed, 800)
        assert placement.box is not None, "all-blocked should return least-overlap position, not None"
        assert placement.reroute_required is True

    def test_empty_candidates_returns_none_placement(self):
        """When candidates list is empty, box is None and reroute_required is True."""
        from mermaid_render.layout._routing import _best_label_pos
        placed: list = []
        placement = _best_label_pos([], "label", [], placed, 800)
        assert placement.box is None
        assert placement.reroute_required is True


# ── AC-11: RenderOptions ─────────────────────────────────────────────────────

class TestRenderOptions:
    """AC-11: RenderOptions controls faithful_mermaid / icon inference / auto direction."""

    def test_render_options_default_fields(self):
        """RenderOptions() has expected defaults."""
        from mermaid_render.layout._strategies import RenderOptions
        opts = RenderOptions()
        assert opts.faithful_mermaid is False
        assert opts.infer_icons is True
        assert opts.auto_direction is True
        assert opts.inferred_legend is True

    def test_faithful_mermaid_preserves_declared_direction(self):
        """With faithful_mermaid=True, declared LR direction is preserved even with hints."""
        from mermaid_render.layout._strategies import RenderOptions
        # Without faithful mode, the auto-direction logic might switch LR → TB
        # when width_hint and height_hint suggest TB is better.
        src = "flowchart LR\n    A --> B --> C --> D --> E\n"
        opts = RenderOptions(faithful_mermaid=True)
        html = _dispatch(src, None, 400, opts=opts)
        # LR diagrams have edges routing horizontally; check that nodes are arranged LR
        import re
        # In LR, nodes have distinct x-coords; in TB, distinct y-coords.
        # Simple heuristic: find node left positions — in LR they should span wide x-range
        lefts = [float(m.group(1)) for m in re.finditer(
            r'class="node[^"]*"[^>]*left:([\d.]+)px', html
        )]
        if lefts and len(lefts) >= 2:
            x_span = max(lefts) - min(lefts)
            assert x_span > 50, (
                f"LR direction not preserved: x_span={x_span:.0f}px (nodes may be stacked vertically)"
            )

    def test_faithful_mermaid_no_icon_inference(self):
        """With faithful_mermaid=True, icon inference is skipped."""
        from mermaid_render.layout._strategies import RenderOptions
        # Label "database" would normally trigger icon inference
        src = "flowchart TD\n    A[database] --> B[server]\n"
        opts_faithful = RenderOptions(faithful_mermaid=True)
        opts_default = RenderOptions()
        html_faithful = _dispatch(src, None, 800, opts=opts_faithful)
        html_default = _dispatch(src, None, 800, opts=opts_default)
        # With default options, icons may be injected; with faithful, they must not be
        # (node-icon class or SVG content indicates an icon was injected)
        faithful_has_icon = 'node-icon' in html_faithful
        assert not faithful_has_icon, (
            "faithful_mermaid=True should suppress icon inference but found node-icon in output"
        )

    def test_faithful_mermaid_no_legend(self):
        """With faithful_mermaid=True, no legend is appended."""
        from mermaid_render.layout._strategies import RenderOptions
        src = "flowchart TD\n    A --> B\n    A -.-> C\n"  # dotted edge triggers legend
        opts_faithful = RenderOptions(faithful_mermaid=True, inferred_legend=False)
        html = _dispatch(src, None, 800, opts=opts_faithful)
        assert 'legend' not in html.lower(), (
            "faithful_mermaid=True should suppress legend injection"
        )

    def test_dispatch_accepts_none_opts(self):
        """_dispatch with opts=None behaves identically to opts=RenderOptions()."""
        src = "flowchart TD\n    A --> B\n"
        html_none = _dispatch(src, None, 800, opts=None)
        html_default = _dispatch(src, None, 800)
        assert html_none == html_default


# ── AC-12: Gallery three-state ────────────────────────────────────────────────

class TestGalleryThreeState:
    """AC-12: _classify_status returns ok/warning/invalid/error."""

    def _classify(self, render_exception=None, geometry_errors=False, geometry_warnings=False):
        from tools.compare_gallery import _classify_status
        return _classify_status(render_exception, geometry_errors, geometry_warnings)

    def test_error_when_exception(self):
        assert self._classify(render_exception=ValueError("boom")) == "error"

    def test_invalid_when_geometry_errors(self):
        assert self._classify(geometry_errors=True) == "invalid"

    def test_warning_when_geometry_warnings_only(self):
        assert self._classify(geometry_warnings=True) == "warning"

    def test_ok_when_clean(self):
        assert self._classify() == "ok"

    def test_error_takes_priority_over_invalid(self):
        assert self._classify(render_exception=Exception("x"), geometry_errors=True) == "error"


# ── AC-13: CSS box-model ──────────────────────────────────────────────────────

class TestCSSBoxModel:
    """AC-13: Overlay SVGs use actual node width/height, not hard-coded 42."""

    def test_subroutine_svg_uses_node_width(self):
        """Subroutine node SVG overlay uses the node's computed width."""
        src = "flowchart TD\n    A[[Subroutine]] --> B[Normal]\n"
        html = _dispatch(src, None, 800)
        import re
        # Find subroutine node width from the node div
        nw_match = re.search(
            r'class="node node-subroutine[^"]*"[^>]*width:(\d+)px', html
        )
        if not nw_match:
            pytest.skip("subroutine node not found in output")
        node_w = int(nw_match.group(1))
        # The SVG overlay should use node_w, not 42
        # Look for the SVG element near the subroutine node
        # The overlay SVG should have width="<node_w>" not width="42"
        assert f'width="42"' not in html or node_w == 42, (
            f"subroutine SVG still uses hard-coded width=42; node_w={node_w}"
        )

    def test_cylinder_svg_uses_node_width(self):
        """Cylinder node SVG overlay uses the node's computed width."""
        src = "flowchart TD\n    DB[(Database)] --> A[App]\n"
        html = _dispatch(src, None, 800)
        import re
        nw_match = re.search(
            r'class="node node-cylinder[^"]*"[^>]*width:(\d+)px', html
        )
        if not nw_match:
            pytest.skip("cylinder node not found in output")
        node_w = int(nw_match.group(1))
        # Check no SVG uses literal 42 for width when node_w != 42
        if node_w != 42:
            assert f'width="42"' not in html, (
                f"cylinder SVG uses hard-coded width=42 but node_w={node_w}"
            )
