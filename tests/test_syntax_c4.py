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
