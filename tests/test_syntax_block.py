#!/usr/bin/env python3
"""block-beta syntax coverage tests.

Probes whether the ``block-beta`` directive is supported by the pure-Python
renderer and documents its behaviour for all major syntax features.

Result: SUPPORTED — ``block-beta`` dispatches to ``_layout_block``; it does
NOT raise ValueError for well-formed input.

Key implementation behaviours documented here:

1.  Blocks MUST appear on their own non-edge lines to be registered.
    Blocks defined *only* inside edge lines (e.g. ``A["S"] --> B["T"]``
    with no standalone ``A`` or ``B`` line) are NOT registered — the
    diagram raises ValueError("No blocks found in block-beta.").

2.  ``columns N`` sets the grid column count and is consumed without error.

3.  ``space`` and ``space:N`` tokens are silently skipped (not registered as
    block nodes).

4.  ``classDef`` and ``class`` keyword tokens are silently skipped.
    Subsequent tokens on the same line (e.g. the class name) are NOT
    skipped and may appear as block nodes.

5.  ``style`` is NOT in the skip list; the token ``style`` itself is
    treated as a block node ID.  This is a known implementation quirk
    documented here but not fixed by this test suite.

6.  Column-span syntax ``NodeId["label"]:N`` is supported: the block spans
    N columns and its label is extracted correctly.

7.  Edges (``A --> B``) between blocks that appear on standalone lines render
    an SVG arrow with ``data-src`` / ``data-dst`` attributes.

8.  The full canonical mermaid.js docs example renders without raising
    ValueError (quirky block IDs appear from the ``style``/``classDef``/
    ``class`` lines, but the renderer does not crash).

Import note: ``to_html`` lives on ``mermaid_render``, not on the
``mermaid_layout`` backward-compat shim (which re-exports only
``mermaid_render.layout`` internals).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _block(body: str) -> str:
    """Wrap a body snippet in a block-beta preamble and call to_html."""
    return to_html(f"block-beta\n{body}")


# ── TestBlockBetaSupported ────────────────────────────────────────────────────


class TestBlockBetaSupported:
    """Probe: the keyword ``block-beta`` IS recognised by the renderer."""

    def test_basic_block_renders(self):
        """block-beta with two standalone blocks renders without error."""
        html = _block("  columns 2\n  A[\"Alpha\"]\n  B[\"Beta\"]")
        assert html

    def test_returns_string(self):
        """to_html returns a str for block-beta source."""
        html = _block("  columns 2\n  A[\"Alpha\"]\n  B[\"Beta\"]")
        assert isinstance(html, str)

    def test_returns_html_document(self):
        """Output is a full HTML document (DOCTYPE / html tag present)."""
        html = _block("  columns 2\n  A[\"Alpha\"]\n  B[\"Beta\"]")
        assert html.lstrip().startswith("<!DOCTYPE") or "<html" in html

    def test_mermaid_layout_class_present(self):
        """Rendered output contains the ``mermaid-layout`` CSS class."""
        html = _block("  columns 2\n  A[\"Alpha\"]\n  B[\"Beta\"]")
        assert "mermaid-layout" in html

    def test_empty_body_raises_value_error(self):
        """block-beta with no blocks (columns directive only) raises ValueError."""
        with pytest.raises(ValueError, match="No blocks"):
            to_html("block-beta\n  columns 3")

    def test_edge_inline_only_raises_value_error(self):
        """Blocks defined *only* inside edge lines are NOT registered.

        When every block ID appears only in an edge line (``A --> B``) and
        never on a standalone block line, the parser registers no blocks and
        raises ValueError.
        """
        src = 'block-beta\n  A["Start"] --> B["End"]'
        with pytest.raises(ValueError, match="No blocks"):
            to_html(src)


# ── TestBlockBetaGrid ─────────────────────────────────────────────────────────


class TestBlockBetaGrid:
    """Basic grid layout: standalone block lines, labels, node-id attrs."""

    def test_single_block_renders(self):
        """A single standalone block line renders without error.

        Note: labels with spaces are split by the whitespace tokenizer, so
        single-word labels are used here to keep the assertion unambiguous.
        """
        html = _block("  A[\"Alpha\"]")
        assert "Alpha" in html

    def test_single_block_data_node_id(self):
        """Single block carries a data-node-id attribute."""
        html = _block("  A[\"Alpha\"]")
        assert 'data-node-id="A"' in html

    def test_two_blocks_labels_in_output(self):
        """Both block labels appear in the rendered HTML."""
        html = _block("  columns 2\n  A[\"Alpha\"]\n  B[\"Beta\"]")
        assert "Alpha" in html
        assert "Beta" in html

    def test_two_blocks_data_node_ids(self):
        """Both blocks carry data-node-id attributes."""
        html = _block("  columns 2\n  A[\"Alpha\"]\n  B[\"Beta\"]")
        assert 'data-node-id="A"' in html
        assert 'data-node-id="B"' in html

    def test_three_column_grid_all_labels(self):
        """Three blocks in a 3-column grid all appear in output."""
        src = (
            "  columns 3\n"
            "  A[\"Alpha\"]\n"
            "  B[\"Beta\"]\n"
            "  C[\"Gamma\"]\n"
        )
        html = _block(src)
        assert "Alpha" in html
        assert "Beta" in html
        assert "Gamma" in html

    def test_three_column_grid_all_node_ids(self):
        """All three nodes carry data-node-id attrs in a 3-column grid."""
        src = (
            "  columns 3\n"
            "  A[\"Alpha\"]\n"
            "  B[\"Beta\"]\n"
            "  C[\"Gamma\"]\n"
        )
        html = _block(src)
        for nid in ("A", "B", "C"):
            assert f'data-node-id="{nid}"' in html, f"data-node-id={nid!r} missing"

    def test_block_without_quoted_label_uses_id(self):
        """A bare node token without a quoted label uses the ID as its label."""
        html = _block("  MyNode")
        assert "MyNode" in html
        assert 'data-node-id="MyNode"' in html

    def test_six_blocks_two_rows_renders(self):
        """Six blocks in a 3-column grid produce a two-row layout without error."""
        src = (
            "  columns 3\n"
            "  A[\"A\"]  B[\"B\"]  C[\"C\"]\n"
            "  D[\"D\"]  E[\"E\"]  F[\"F\"]\n"
        )
        html = _block(src)
        for label in ("A", "B", "C", "D", "E", "F"):
            assert label in html


# ── TestBlockBetaColumns ──────────────────────────────────────────────────────


class TestBlockBetaColumns:
    """``columns N`` directive sets the grid column count."""

    def test_columns_directive_accepted(self):
        """``columns 3`` is consumed without error."""
        html = _block("  columns 3\n  A[\"A\"]\n  B[\"B\"]\n  C[\"C\"]")
        assert "mermaid-layout" in html

    def test_columns_1_accepted(self):
        """``columns 1`` (single column) renders correctly."""
        html = _block("  columns 1\n  A[\"Only\"]")
        assert "Only" in html

    def test_columns_2_accepted(self):
        """``columns 2`` renders a two-column grid correctly."""
        html = _block("  columns 2\n  A[\"Left\"]\n  B[\"Right\"]")
        assert "Left" in html
        assert "Right" in html

    def test_columns_directive_case_insensitive(self):
        """``Columns N`` (capitalised) is accepted without error."""
        html = _block("  Columns 2\n  A[\"A\"]\n  B[\"B\"]")
        assert "mermaid-layout" in html


# ── TestBlockBetaEdges ────────────────────────────────────────────────────────


class TestBlockBetaEdges:
    """Edges between registered blocks render as SVG arrows."""

    def test_edge_renders_without_error(self):
        """``A --> B`` edge line renders without raising."""
        src = "  columns 2\n  A[\"Source\"]\n  B[\"Target\"]\n  A --> B"
        html = _block(src)
        assert "mermaid-layout" in html

    def test_edge_svg_layer_present(self):
        """An SVG element is present to draw the arrow."""
        src = "  columns 2\n  A[\"Source\"]\n  B[\"Target\"]\n  A --> B"
        html = _block(src)
        assert "<svg" in html

    def test_edge_data_src_attribute(self):
        """The edge SVG line carries a data-src attribute for the source node."""
        src = "  columns 2\n  A[\"Source\"]\n  B[\"Target\"]\n  A --> B"
        html = _block(src)
        assert 'data-src="A"' in html

    def test_edge_data_dst_attribute(self):
        """The edge SVG line carries a data-dst attribute for the target node."""
        src = "  columns 2\n  A[\"Source\"]\n  B[\"Target\"]\n  A --> B"
        html = _block(src)
        assert 'data-dst="B"' in html

    def test_multiple_edges_all_rendered(self):
        """Two separate edge lines both produce SVG arrows."""
        src = (
            "  columns 3\n"
            "  A[\"A\"]\n"
            "  B[\"B\"]\n"
            "  C[\"C\"]\n"
            "  A --> B\n"
            "  B --> C\n"
        )
        html = _block(src)
        assert 'data-src="A"' in html
        assert 'data-src="B"' in html

    def test_edge_between_unknown_ids_silently_ignored(self):
        """An edge referencing an unregistered ID is silently skipped; no error."""
        src = (
            "  columns 1\n"
            "  A[\"A\"]\n"
            "  A --> GHOST\n"  # GHOST was never declared as a standalone block
        )
        html = _block(src)
        assert "mermaid-layout" in html


# ── TestBlockBetaColumnSpan ───────────────────────────────────────────────────


class TestBlockBetaColumnSpan:
    """``NodeId["label"]:N`` syntax spans N grid columns."""

    def test_span_2_renders(self):
        """A block with span 2 renders without error."""
        src = "  columns 3\n  A[\"Normal\"]\n  B[\"Wide\"]:2"
        html = _block(src)
        assert "mermaid-layout" in html

    def test_span_2_label_in_output(self):
        """The label of a span-2 block appears in the output."""
        src = "  columns 3\n  A[\"Normal\"]\n  B[\"Wide\"]:2"
        html = _block(src)
        assert "Wide" in html

    def test_span_2_node_id_attribute(self):
        """A span-2 block carries its data-node-id attribute."""
        src = "  columns 3\n  A[\"Normal\"]\n  B[\"Wide\"]:2"
        html = _block(src)
        assert 'data-node-id="B"' in html

    def test_span_3_renders(self):
        """A block with span 3 (full-row) renders without error.

        Single-word label used because the whitespace tokenizer would split
        a quoted label containing spaces across multiple tokens.
        """
        src = "  columns 3\n  A[\"FullRow\"]:3"
        html = _block(src)
        assert "FullRow" in html


# ── TestBlockBetaSpacer ───────────────────────────────────────────────────────


class TestBlockBetaSpacer:
    """``space`` and ``space:N`` tokens are silently skipped."""

    def test_space_keyword_not_registered_as_node(self):
        """``space`` does not create a node with id 'space'."""
        src = (
            "  columns 3\n"
            "  A[\"A\"]\n"
            "  space\n"
            "  B[\"B\"]\n"
        )
        html = _block(src)
        assert 'data-node-id="space"' not in html

    def test_space_colon_n_not_registered_as_node(self):
        """``space:2`` does not create a node with id 'space'."""
        src = (
            "  columns 3\n"
            "  A[\"A\"]\n"
            "  space:2\n"
            "  B[\"B\"]\n"
        )
        html = _block(src)
        assert 'data-node-id="space"' not in html

    def test_space_keyword_other_nodes_still_render(self):
        """Blocks after a ``space`` line still appear in the output."""
        src = (
            "  columns 3\n"
            "  A[\"Alpha\"]\n"
            "  space\n"
            "  B[\"Beta\"]\n"
        )
        html = _block(src)
        assert "Alpha" in html
        assert "Beta" in html

    def test_space_colon_n_does_not_crash(self):
        """``space:2`` is consumed without raising."""
        src = (
            "  columns 3\n"
            "  A[\"Alpha\"]\n"
            "  space:2\n"
        )
        html = _block(src)
        assert "Alpha" in html


# ── TestBlockBetaStyleDirectives ─────────────────────────────────────────────


class TestBlockBetaStyleDirectives:
    """``classDef``, ``class``, and ``style`` directive lines."""

    def test_classdef_keyword_not_registered_as_node(self):
        """The ``classDef`` token itself is silently skipped."""
        src = (
            "  columns 2\n"
            "  A[\"Alpha\"]\n"
            "  B[\"Beta\"]\n"
            "  classDef blue fill:#00f,color:#fff\n"
        )
        html = _block(src)
        assert 'data-node-id="classDef"' not in html

    def test_classdef_diagram_still_renders(self):
        """A ``classDef`` line does not prevent the diagram from rendering."""
        src = (
            "  columns 2\n"
            "  A[\"Alpha\"]\n"
            "  B[\"Beta\"]\n"
            "  classDef highlight fill:#ff9,stroke:#f90\n"
        )
        html = _block(src)
        assert "mermaid-layout" in html

    def test_class_keyword_not_registered_as_node(self):
        """The ``class`` token itself is silently skipped."""
        src = (
            "  columns 2\n"
            "  A[\"Alpha\"]\n"
            "  B[\"Beta\"]\n"
            "  class A blue\n"
        )
        html = _block(src)
        assert 'data-node-id="class"' not in html

    def test_class_assignment_diagram_still_renders(self):
        """A ``class`` assignment line does not prevent the diagram from rendering."""
        src = (
            "  columns 2\n"
            "  A[\"Alpha\"]\n"
            "  B[\"Beta\"]\n"
            "  classDef blue fill:#00f\n"
            "  class A blue\n"
        )
        html = _block(src)
        assert "mermaid-layout" in html

    def test_style_directive_skipped(self):
        """``style`` lines are now in the skip list and do NOT create a spurious node.

        The block-beta renderer skips entire lines beginning with ``style``,
        ``classDef``, or ``class`` to prevent directive keywords from being
        registered as block node IDs.
        """
        src = (
            "  columns 3\n"
            "  A[\"Alpha\"]\n"
            "  B[\"Beta\"]\n"
            "  C[\"Gamma\"]\n"
            "  style A fill:#f9f,stroke:#333\n"
        )
        html = _block(src)
        assert "mermaid-layout" in html
        # Exactly three real nodes (A, B, C) — no spurious 'style' node.
        assert html.count('data-node-id=') == 3
        assert 'data-node-id="style"' not in html


# ── TestBlockBetaCanonical ────────────────────────────────────────────────────


class TestBlockBetaCanonical:
    """The full canonical mermaid.js docs example renders without ValueError."""

    _CANONICAL = (
        "block-beta\n"
        "  columns 3\n"
        '  A["Start"] --> B{"Decision"}\n'
        "  B --> C([Process])\n"
        "  B --> D[(Database)]\n"
        '  E>>"Block Arrow"] --> F(("Junction"))\n'
        "  space:2\n"
        '  G["Width 2"]:2\n'
        "  style A fill:#f9f,stroke:#333\n"
        "  classDef blue fill:#00f,color:#fff\n"
        "  class D blue\n"
    )

    def test_canonical_does_not_raise(self):
        """The canonical docs example renders without raising any exception."""
        html = to_html(self._CANONICAL)
        assert html

    def test_canonical_has_mermaid_layout(self):
        """The canonical example output contains the ``mermaid-layout`` class."""
        html = to_html(self._CANONICAL)
        assert "mermaid-layout" in html

    def test_canonical_has_some_blocks(self):
        """The canonical example produces at least one ``data-node-id`` attr."""
        html = to_html(self._CANONICAL)
        assert "data-node-id=" in html

    def test_canonical_returns_html_document(self):
        """The canonical example output is a full HTML document."""
        html = to_html(self._CANONICAL)
        assert html.lstrip().startswith("<!DOCTYPE") or "<html" in html
