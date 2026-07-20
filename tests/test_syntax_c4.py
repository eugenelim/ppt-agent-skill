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
from mermaid_render.layout._c4 import C4Bounds, C4Box  # noqa: E402


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
