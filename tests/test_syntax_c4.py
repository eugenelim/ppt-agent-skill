#!/usr/bin/env python3
"""C4 diagram syntax coverage tests for the mermaid_render layout engine.

Documents real C4 syntax (from mermaid.js docs) and asserts graceful
ValueError failure for empty or unsupported C4 diagrams.

Dispatch behaviour in the renderer:
- C4Context, C4Container, C4Component → ``_layout_c4``; raise ValueError
  when no element content is present ("No elements found in C4 diagram.").
- C4Dynamic, C4Deployment → not in the dispatch table; fall through to
  the unknown-directive handler which raises ValueError
  ("Unsupported or unrecognised Mermaid directive: ...").

All tests in TestC4Unsupported therefore expect ValueError regardless of
which C4 level is used.

Import note: ``to_html`` lives in ``mermaid_render``, not ``mermaid_layout``
(the latter is a shim to ``mermaid_render.layout`` and does not re-export
``to_html``).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402
from mermaid_render.layout._c4 import C4Bounds, C4Box, _mermaid_edge_point  # noqa: E402


# ── C4Bounds packer unit tests (TDD, AC-1) ───────────────────────────────────

class TestC4BoundsPacker:
    """Pixel-exact packing tests matching Mermaid 11.15 Bounds.insert() behaviour."""

    def test_c4_basic_fixture_coordinates(self):
        """c4-basic reference: start_x=100, start_y=66, width_limit=832."""
        boxes = [
            C4Box("user", 216, 134),
            C4Box("webapp", 216, 86),
            C4Box("email", 216, 86),
        ]
        bounds = C4Bounds(start_x=100, start_y=66, width_limit=832)
        for box in boxes:
            bounds.insert(box)
        assert (boxes[0].x, boxes[0].y) == (150, 166), f"user: {boxes[0].x},{boxes[0].y}"
        assert (boxes[1].x, boxes[1].y) == (466, 166), f"webapp: {boxes[1].x},{boxes[1].y}"
        assert (boxes[2].x, boxes[2].y) == (150, 400), f"email: {boxes[2].x},{boxes[2].y}"

    def test_wrap_after_shapes_per_row(self):
        """5 boxes at shapes_per_row=4 wraps: first 4 on row 1, fifth on row 2."""
        boxes = [C4Box(str(i), 100, 50) for i in range(5)]
        bounds = C4Bounds(start_x=0, start_y=0, width_limit=2000, shapes_per_row=4)
        for box in boxes:
            bounds.insert(box)
        row1_ys = {box.y for box in boxes[:4]}
        assert len(row1_ys) == 1, f"First four boxes must be on same row, got ys={row1_ys}"
        assert boxes[4].y > boxes[0].y, "Fifth box must wrap to a lower row"

    def test_single_item_placed(self):
        """A single item is placed at start_x + margin, start_y + 2*margin."""
        box = C4Box("a", 200, 80)
        bounds = C4Bounds(start_x=0, start_y=0, width_limit=1000, shape_margin=50)
        bounds.insert(box)
        assert box.x == 50   # start_x + shape_margin (first_in_row)
        assert box.y == 100  # start_y + 2 * shape_margin

    def test_two_items_same_row(self):
        """Two small items fit on the same row when width allows."""
        b1, b2 = C4Box("a", 100, 50), C4Box("b", 100, 50)
        bounds = C4Bounds(start_x=0, start_y=0, width_limit=1000, shape_margin=50)
        for b in (b1, b2):
            bounds.insert(b)
        assert b1.y == b2.y, "Both boxes must be on the same row"
        assert b2.x > b1.x, "Second box must be to the right of the first"


# ── _mermaid_edge_point geometry unit tests (AC: Mermaid 11.15 intersection) ─

class TestMermaidEdgePoint:
    """Pixel-level tests for the Mermaid 11.15 C4 edge attachment algorithm.

    Expected values are back-calculated from the algorithm formula and cross-
    checked against the mmdc 11.15.0 reference visible in compare_gallery.py.
    """

    def test_right_exit(self):
        """user→webapp: exits right edge of user, enters left edge of webapp."""
        # user: x=150, y=166, cx=258, cy=233, w=216, h=134
        # webapp center: cx=574, cy=209
        sx, sy = _mermaid_edge_point(150, 166, 258, 233, 216, 134, 574, 209)
        assert sx == pytest.approx(366.0, abs=0.01), f"sx={sx}"
        assert sy == pytest.approx(243.953, abs=0.01), f"sy={sy}"

    def test_left_entry(self):
        """webapp→user: exits left edge of webapp (entry point from user)."""
        # webapp: x=466, y=166, cx=574, cy=209, w=216, h=86
        # user center: cx=258, cy=233
        ex, ey = _mermaid_edge_point(466, 166, 574, 209, 216, 86, 258, 233)
        assert ex == pytest.approx(466.0, abs=0.01), f"ex={ex}"
        assert ey == pytest.approx(243.788, abs=0.01), f"ey={ey}"

    def test_bottom_exit(self):
        """webapp→email: exits bottom edge of webapp."""
        # webapp: x=466, y=166, cx=574, cy=209, w=216, h=86
        # email center: cx=258, cy=443
        sx, sy = _mermaid_edge_point(466, 166, 574, 209, 216, 86, 258, 443)
        assert sx == pytest.approx(541.711, abs=0.01), f"sx={sx}"
        assert sy == pytest.approx(252.0, abs=0.01), f"sy={sy}"

    def test_top_entry(self):
        """email→webapp: exits top edge of email (entry point from webapp)."""
        # email: x=150, y=400, cx=258, cy=443, w=216, h=86
        # webapp center: cx=574, cy=209
        ex, ey = _mermaid_edge_point(150, 400, 258, 443, 216, 86, 574, 209)
        assert ex == pytest.approx(353.455, abs=0.01), f"ex={ex}"
        assert ey == pytest.approx(400.0, abs=0.01), f"ey={ey}"

    def test_left_edge_alignment_guard(self):
        """dst_cx == src_x triggers abs(dx)<1e-9 guard → vertical exit from center."""
        # Node top-left=(100, 0), center=(208, 43), w=216, h=86
        # dx = dst_cx - src_x = 100 - 100 = 0 → guard fires
        sx, sy = _mermaid_edge_point(100, 0, 208, 43, 216, 86, 100, 200)
        assert sx == pytest.approx(208.0, abs=0.01)
        assert sy == pytest.approx(86.0, abs=0.01)  # center_y + hh = 43 + 43

    def test_stacked_nodes_off_center_exit(self):
        """Stacked node (dst_cx == src_cx) does NOT hit the dx=0 guard.

        dx = dst_cx - src_x = src_cx - src_x = hw, so the slope is non-zero
        and the exit point is off-center — this documents the known behavior.
        """
        # Node top-left=(100, 0), center=(208, 43), w=216, h=86
        # dst directly below at same cx: dst_cx=208, dst_cy=200
        # dx = 208-100=108, dy=200-0=200, m=200/108≈1.852
        # |dy|*hw = 200*108 = 21600 > |dx|*hh = 108*43 = 4644 → exits bottom
        # x_exit = src_cx + hh/m = 208 + 43/(200/108) = 208 + 43*108/200 = 208+23.22 = 231.22
        # y_exit = src_cy + hh = 43+43 = 86
        sx, sy = _mermaid_edge_point(100, 0, 208, 43, 216, 86, 208, 200)
        assert sx == pytest.approx(231.22, abs=0.1)
        assert sy == pytest.approx(86.0, abs=0.01)

    def test_horizontal_ray(self):
        """Purely horizontal ray (dst_y == src_y) exits via left or right."""
        # dx = 500-100=400, dy = 0-0=0 → abs(dy)<1e-9 guard → right exit
        sx, sy = _mermaid_edge_point(100, 0, 208, 43, 216, 86, 500, 0)
        assert sx == pytest.approx(316.0, abs=0.01)  # center_x + hw = 208 + 108
        assert sy == pytest.approx(43.0, abs=0.01)


# ── TestC4Fragment: integrated parser-to-HTML tests ───────────────────────────

_C4_BASIC_SRC = """
C4Context
    title System Context
    Person(user, "User", "End user")
    System(webapp, "Web App", "Main application")
    System_Ext(email, "Email Service", "Sends emails")
    Rel(user, webapp, "Uses")
    Rel(webapp, email, "Sends via")
"""


class TestC4Fragment:
    """End-to-end tests: parser → layout → HTML fragment via the public API."""

    def test_c4_basic_end_to_end(self):
        """Full parser-to-HTML path for c4-basic produces correct structure."""
        html = to_html(_C4_BASIC_SRC)

        # Wrapper class
        assert 'class="diagram mermaid-layout c4-diagram"' in html

        # Title
        assert "System Context" in html

        # User node: correct position and dimensions
        assert 'data-node-id="user"' in html
        assert "left:150px; top:166px" in html
        assert "width:216px; height:134px" in html

        # Webapp node
        assert 'data-node-id="webapp"' in html
        assert "left:466px; top:166px" in html

        # Email node (external system)
        assert 'data-node-id="email"' in html
        assert "left:150px; top:400px" in html
        assert "background:#999" in html
        assert "border:1px solid #8a8a8a" in html

        # No person-circle or dashed-border styling (those would be regressions)
        assert "node-circle" not in html
        assert "border:1.5px dashed" not in html

    def test_c4_basic_canvas_width(self):
        """Canvas width is pinned to C4_LAYOUT_WIDTH (832 px) not the content bbox."""
        html = to_html(_C4_BASIC_SRC)
        assert "width:832px" in html

    def test_c4_basic_edge_geometry(self):
        """SVG edge paths use Mermaid 11.15 top-left-slope intersection geometry."""
        html = to_html(_C4_BASIC_SRC)
        # First relationship (straight line): user → webapp
        assert "M 366.0 244.0 L 466.0 243.8" in html
        # Second relationship (quadratic Bézier): webapp → email
        assert "M 541.7 252.0 Q 494.6 326.0 353.5 400.0" in html

    def test_c4_basic_width_hint_scales(self):
        """width_hint=416 (half of 832) produces zoom:0.5000 on the C4 wrapper."""
        html = to_html(_C4_BASIC_SRC, width_hint=416)
        assert "zoom:0.5000;" in html


# ── TestC4Unsupported ─────────────────────────────────────────────────────────

class TestC4Unsupported:
    @pytest.mark.parametrize("keyword", [
        "C4Context", "C4Container", "C4Component", "C4Dynamic", "C4Deployment"
    ])
    def test_c4_level_raises(self, keyword):
        """A bare C4 directive with no element content raises ValueError.

        Supported levels (C4Context/Container/Component) raise because no
        elements are parsed ("No elements found in C4 diagram.").
        Unsupported levels (C4Dynamic/C4Deployment) raise because the
        directive is not in the dispatch table.
        """
        with pytest.raises(ValueError):
            to_html(keyword)

    def test_c4_with_person_renders(self):
        """C4Dynamic with Person elements renders via graph-topology fallback.

        C4Dynamic is not in the dispatch table so the renderer falls through
        to the unknown-directive handler, which parses C4 element lines as
        best-effort flowchart nodes and returns HTML.
        """
        src = (
            "C4Dynamic\n"
            '  Person(customer, "Customer", "A bank customer")\n'
            '  Person_Ext(admin, "Admin", "Bank staff")\n'
        )
        html = to_html(src)
        assert html

    def test_c4_with_system_boundary_renders(self):
        """C4Dynamic with System_Boundary renders via graph-topology fallback."""
        src = (
            "C4Dynamic\n"
            '  title System Context for Internet Banking\n'
            '  Person(customer, "Customer", "A bank customer")\n'
            '  System(banking, "Internet Banking", "Allows customers to view accounts")\n'
            '  System_Ext(mail, "E-mail system", "SendGrid")\n'
        )
        html = to_html(src)
        assert html

    def test_c4_with_rel_renders(self):
        """C4Dynamic with Rel lines renders via graph-topology fallback.

        Rel(...) lines are not flowchart edges so no SVG paths are produced,
        but the diagram doesn't crash — the element nodes are still rendered.
        """
        src = (
            "C4Dynamic\n"
            '  Person(customer, "Customer", "A bank customer")\n'
            '  System(banking, "Internet Banking", "Allows customers")\n'
            '  Rel(customer, banking, "Uses")\n'
        )
        html = to_html(src)
        assert html

    def test_c4_with_update_style_renders(self):
        """C4Dynamic with UpdateRelStyle lines renders via graph-topology fallback."""
        src = (
            "C4Dynamic\n"
            '  Person(customer, "Customer", "A bank customer")\n'
            '  System(banking, "Internet Banking", "Allows customers")\n'
            '  UpdateRelStyle(customer, banking, $textColor="blue", $lineColor="red")\n'
        )
        html = to_html(src)
        assert html
