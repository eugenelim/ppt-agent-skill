#!/usr/bin/env python3
"""Regression tests for block-beta renderer fixes.

Five bugs fixed in _layout_block (scripts/mermaid_render/layout/_strategies.py):
  1. Multi-word labels: A["Foo Bar"] was split by line.split(), losing spaces.
  2. style directive: "style A fill:#f00" tokenised into spurious block nodes.
  3. classDef/class directives: same as above.
  4. >> arrow shape: B>>"Process" label was lost; shape not rendered as chevron.
  5. space / space:N spacer: did not advance the column cursor.
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

def _render(src: str, width: int = 600) -> str:
    return _dispatch(src, None, width)


def _node_ids(html: str) -> list[str]:
    return re.findall(r'data-node-id="([^"]+)"', html)


# ── Fix 1: multi-word labels ──────────────────────────────────────────────────

class TestMultiWordLabels:
    """A["Foo Bar"] must preserve the space inside the quoted label."""

    _SRC = 'block-beta\n  columns 3\n  A["Foo Bar"] B["Hello World"] C["End"]\n'

    def test_label_with_space_preserved(self):
        html = _render(self._SRC)
        assert "Foo Bar" in html, "Multi-word label 'Foo Bar' lost (split on space)"

    def test_second_label_with_space_preserved(self):
        html = _render(self._SRC)
        assert "Hello World" in html, "Multi-word label 'Hello World' lost (split on space)"

    def test_no_spurious_nodes_from_split_words(self):
        html = _render(self._SRC)
        ids = _node_ids(html)
        # "Bar" and "World" must NOT appear as separate node IDs
        assert "Bar" not in ids, "'Bar' became a spurious node (label was split on space)"
        assert "World" not in ids, "'World' became a spurious node (label was split on space)"

    def test_correct_node_count(self):
        html = _render(self._SRC)
        ids = _node_ids(html)
        assert set(ids) == {"A", "B", "C"}, f"Expected {{A,B,C}} but got {set(ids)}"


# ── Fix 2: style directive ────────────────────────────────────────────────────

class TestStyleDirectiveSkip:
    """style A fill:#f00 must be silently ignored, not turned into nodes."""

    _SRC = 'block-beta\n  columns 2\n  A["A"] B["B"]\n  style A fill:#f00\n'

    def test_no_style_node(self):
        html = _render(self._SRC)
        ids = _node_ids(html)
        assert "style" not in ids, "'style' keyword became a spurious block node"

    def test_no_fill_node(self):
        html = _render(self._SRC)
        ids = _node_ids(html)
        assert "fill" not in ids, "'fill' from style directive became a spurious block node"

    def test_only_declared_nodes_rendered(self):
        html = _render(self._SRC)
        ids = _node_ids(html)
        assert set(ids) == {"A", "B"}, f"Expected only {{A,B}}, got {set(ids)}"


# ── Fix 3: classDef / class directives ───────────────────────────────────────

class TestClassDefDirectiveSkip:
    """classDef and class directives must be silently ignored."""

    _SRC = (
        'block-beta\n'
        '  columns 2\n'
        '  A["A"] B["B"]\n'
        '  classDef myStyle fill:#f00,stroke:#333\n'
        '  class A myStyle\n'
    )

    def test_no_classdef_node(self):
        html = _render(self._SRC)
        ids = _node_ids(html)
        assert "classDef" not in ids
        assert "myStyle" not in ids, "class name became a spurious block node"
        assert "fill" not in ids

    def test_only_declared_nodes(self):
        html = _render(self._SRC)
        ids = _node_ids(html)
        assert set(ids) == {"A", "B"}, f"Expected only {{A,B}}, got {set(ids)}"

    def test_class_directive_line_skipped(self):
        # "class A myStyle" must not add a second A node or a myStyle node
        html = _render(self._SRC)
        ids = _node_ids(html)
        assert ids.count("A") == 1, "Node A duplicated (class directive re-added it)"


# ── Fix 4: >> arrow shape ─────────────────────────────────────────────────────

class TestArrowShape:
    """>> shape: label is extracted and a clip-path chevron is rendered."""

    _SRC = 'block-beta\n  columns 3\n  A["Input"] B>>"Process" C["Output"]\n'

    def test_arrow_label_preserved(self):
        html = _render(self._SRC)
        assert 'Process' in html, '>> arrow label was not extracted from B>>"Process"'

    def test_arrow_shape_css_applied(self):
        html = _render(self._SRC)
        assert "clip-path" in html, ">> arrow shape has no clip-path CSS"

    def test_arrow_node_class(self):
        html = _render(self._SRC)
        assert "node-arrow" in html, ">> arrow node lacks 'node-arrow' CSS class"

    def test_arrow_node_id_present(self):
        html = _render(self._SRC)
        assert 'data-node-id="B"' in html, "Arrow block B missing from output"

    def test_all_three_nodes_present(self):
        html = _render(self._SRC)
        ids = _node_ids(html)
        assert set(ids) == {"A", "B", "C"}, f"Expected {{A,B,C}}, got {set(ids)}"


# ── Fix 5: space / space:N spacer ────────────────────────────────────────────

class TestSpaceSpacer:
    """space and space:N must advance the column cursor without emitting a block."""

    def test_space_no_node_emitted(self):
        src = 'block-beta\n  columns 3\n  A["A"] space B["B"]\n'
        html = _render(src)
        ids = _node_ids(html)
        assert "space" not in ids, "'space' keyword was rendered as a block node"

    def test_space_advances_column(self):
        """With 3 columns and a space in the middle, B must be in column 2."""
        src = 'block-beta\n  columns 3\n  A["A"] space B["B"]\n'
        html = _render(src, width=600)
        # cell_w = (600 - 80 - 48) // 3 = 157; col_gap = 24
        # col 0: left=40, col 1: left=221, col 2: left=402
        lefts = [int(x) for x in re.findall(r'left:(\d+)px', html)]
        assert max(lefts) > 300, (
            f"B was not pushed to col 2 by spacer; max left={max(lefts)} "
            "(expected >300 with 600px canvas and 3 columns)"
        )

    def test_space_colon_two_advances_two_columns(self):
        """space:2 fills two column slots; next block starts in col 3 (new row)."""
        src = 'block-beta\n  columns 3\n  A["A"] space:2\n  B["B"] C["C"] D["D"]\n'
        html = _render(src, width=600)
        # A should be in row 0 (top ~24), B/C/D in row 1 (top ~104)
        tops = [int(x) for x in re.findall(r'top:(\d+)px', html)]
        assert len(set(tops)) >= 2, "space:2 did not push subsequent nodes to a new row"

    def test_only_real_nodes_have_data_node_id(self):
        src = 'block-beta\n  columns 3\n  A["A"] space B["B"]\n'
        html = _render(src)
        ids = _node_ids(html)
        assert set(ids) == {"A", "B"}, f"Expected only {{A,B}}, got {set(ids)}"


# ── Additional shape variants ─────────────────────────────────────────────────

class TestBlockBetaShapes:
    """Standard flowchart shapes inside block-beta."""

    def test_circle_shape(self):
        src = 'block-beta\n  columns 1\n  A(("Circle"))\n'
        html = _render(src)
        assert "node-circle" in html, "Circle shape not rendered with node-circle class"
        assert "Circle" in html, "Circle label not preserved"

    def test_diamond_shape(self):
        src = 'block-beta\n  columns 1\n  A{"Diamond"}\n'
        html = _render(src)
        assert "node-diamond" in html, "Diamond shape not rendered with node-diamond class"
        assert "clip-path" in html, "Diamond missing clip-path CSS"
        assert "Diamond" in html, "Diamond label not preserved"

    def test_hexagon_shape(self):
        src = 'block-beta\n  columns 1\n  A{{"Hexagon"}}\n'
        html = _render(src)
        assert "node-hexagon" in html, "Hexagon shape not rendered with node-hexagon class"
        assert "Hexagon" in html, "Hexagon label not preserved"

    def test_rect_shape_default(self):
        src = 'block-beta\n  columns 2\n  A["Rect"] B\n'
        html = _render(src)
        assert "node-rect" in html, "Default rect shape lost node-rect class"

    def test_all_shapes_render_without_error(self):
        """All supported shape syntaxes must not raise."""
        srcs = [
            'block-beta\n  columns 1\n  A(("Circle"))\n',
            'block-beta\n  columns 1\n  A(["Stadium"])\n',
            'block-beta\n  columns 1\n  A[("Cylinder")]\n',
            'block-beta\n  columns 1\n  A{"Diamond"}\n',
            'block-beta\n  columns 1\n  A{{"Hexagon"}}\n',
            'block-beta\n  columns 1\n  A>>"Arrow"\n',
            'block-beta\n  columns 1\n  A["Rect"]\n',
            'block-beta\n  columns 1\n  A("Round")\n',
        ]
        for src in srcs:
            html = _render(src)
            assert html, f"Empty output for: {src!r}"


# ── Column span ───────────────────────────────────────────────────────────────

class TestColumnSpan:
    """A["label"]:2 must span two cells and be wider than a span-1 block."""

    _SRC = 'block-beta\n  columns 3\n  A["Wide"]:2 B["Narrow"]\n'

    def test_spanning_block_is_wider(self):
        html = _render(self._SRC, width=600)
        widths = {
            nid: int(w)
            for nid, w in re.findall(r'data-node-id="(\w+)"[^>]*width:(\d+)px', html)
        }
        assert widths.get("A", 0) > widths.get("B", 0), (
            f"Spanning block A (span=2) not wider than B (span=1): {widths}"
        )

    def test_span_block_has_correct_node_id(self):
        html = _render(self._SRC)
        assert 'data-node-id="A"' in html
        assert 'data-node-id="B"' in html


# ── Edges still render after fixes ────────────────────────────────────────────

class TestEdgesStillWork:
    """Edges between blocks must still render after the tokeniser rewrite."""

    _SRC = 'block-beta\n  columns 3\n  A["A"] B["B"] C["C"]\n  A --> B --> C\n'

    def test_edge_data_src_present(self):
        html = _render(self._SRC)
        assert 'data-src="A"' in html, "Edge source A missing"
        assert 'data-dst="B"' in html, "Edge dest B missing"

    def test_edge_arrowhead_present(self):
        html = _render(self._SRC)
        assert 'marker-end="url(#arr)"' in html, "Arrowhead marker missing"

    def test_svg_layer_after_node_divs(self):
        html = _render(self._SRC)
        node_positions = [m.start() for m in re.finditer(r'node-rect', html)]
        svg_pos = html.rfind('<svg')
        assert node_positions, "No node-rect divs found"
        assert svg_pos > max(node_positions), (
            "SVG connector layer is before block divs — connectors hidden"
        )
