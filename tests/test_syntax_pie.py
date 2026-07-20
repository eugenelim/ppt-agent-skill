#!/usr/bin/env python3
"""Pytest tests for pie chart syntax coverage.

Covers every documented pie chart syntax variant:
  - Basic pie chart
  - pie showData option
  - Without title
  - Decimal values
  - Many slices
  - Structural output invariants (HTML, SVG, path elements, percentages)
  - data-slice identity attributes
  - Edge cases (single slice, comment lines)

Import note: `to_html` lives on `mermaid_render`, not on the
`mermaid_layout` backward-compat shim (which re-exports only
`mermaid_render.layout` internals).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _slices(html: str) -> list[str]:
    """Return all data-slice attribute values from rendered HTML."""
    return re.findall(r'data-slice="([^"]+)"', html)


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------

class TestPieBasic:
    def test_minimal_pie_renders(self):
        """Two-slice pie with no title returns non-empty HTML containing both labels."""
        src = 'pie\n  "Dogs" : 386\n  "Cats" : 85'
        html = to_html(src)
        assert html
        assert "Dogs" in html
        assert "Cats" in html

    def test_pie_with_title(self):
        """Title keyword value appears in rendered output."""
        src = (
            "pie\n"
            "  title Pet Ownership\n"
            '  "Dogs" : 386\n'
            '  "Cats" : 85\n'
            '  "Rabbits" : 15'
        )
        html = to_html(src)
        assert "Pet Ownership" in html
        assert "Dogs" in html

    def test_pie_show_data(self):
        """pie showData directive is accepted and labels render without error."""
        src = (
            "pie showData\n"
            "  title Pet Ownership\n"
            '  "Dogs" : 386\n'
            '  "Cats" : 85'
        )
        html = to_html(src)
        assert html
        assert "Dogs" in html
        assert "Cats" in html

    def test_pie_without_title(self):
        """Pie chart with no title keyword still renders all slice labels."""
        src = (
            "pie\n"
            '  "Slice A" : 50\n'
            '  "Slice B" : 30\n'
            '  "Slice C" : 20'
        )
        html = to_html(src)
        assert "Slice A" in html
        assert "Slice B" in html
        assert "Slice C" in html

    def test_pie_decimal_values(self):
        """Slice values with decimal fractions are parsed and rendered."""
        src = (
            "pie\n"
            '  "A" : 45.5\n'
            '  "B" : 54.5'
        )
        html = to_html(src)
        assert "A" in html
        assert "B" in html
        # Total is 100 — each label should carry a ~percentage
        assert "%" in html

    def test_pie_many_slices(self):
        """Four-slice chart renders without crashing; all four labels present."""
        src = (
            "pie\n"
            '  "A" : 10\n'
            '  "B" : 20\n'
            '  "C" : 30\n'
            '  "D" : 40'
        )
        html = to_html(src)
        assert html
        for label in ("A", "B", "C", "D"):
            assert label in html

    def test_pie_labels_in_output(self):
        """Every slice label is reachable via data-slice attribute."""
        src = (
            "pie\n"
            '  "Dogs" : 386\n'
            '  "Cats" : 85\n'
            '  "Rabbits" : 15'
        )
        html = to_html(src)
        found = _slices(html)
        assert "Dogs" in found
        assert "Cats" in found
        assert "Rabbits" in found


# ---------------------------------------------------------------------------
# Output structure invariants
# ---------------------------------------------------------------------------

class TestPieStructure:
    def test_pie_html_document(self):
        """Output is a full standalone HTML document."""
        src = 'pie\n  "X" : 60\n  "Y" : 40'
        html = to_html(src)
        assert html.strip().startswith("<!DOCTYPE html")
        assert "<html" in html
        assert "</html>" in html

    def test_pie_contains_svg(self):
        """Sectors are rendered inside an SVG element."""
        src = 'pie\n  "X" : 60\n  "Y" : 40'
        html = to_html(src)
        assert "<svg" in html

    def test_pie_contains_path_elements(self):
        """SVG donut sectors are rendered as <path> elements."""
        src = 'pie\n  "X" : 60\n  "Y" : 40'
        html = to_html(src)
        assert "<path" in html

    def test_pie_percentage_labels(self):
        """Each slice label is followed by a percentage string."""
        src = 'pie\n  "Half" : 50\n  "Other" : 50'
        html = to_html(src)
        assert "50.0%" in html

    def test_pie_data_slice_attrs(self):
        """data-slice attributes match the slice labels exactly."""
        src = (
            "pie\n"
            '  "Alpha" : 30\n'
            '  "Beta"  : 70'
        )
        html = to_html(src)
        found = _slices(html)
        assert set(found) == {"Alpha", "Beta"}

    def test_pie_diagram_wrapper_class(self):
        """Rendered fragment carries the diagram / mermaid-layout CSS class."""
        src = 'pie\n  "P" : 100'
        html = to_html(src)
        assert "mermaid-layout" in html


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestPieEdgeCases:
    def test_pie_single_slice(self):
        """A single slice (full circle) renders without error."""
        src = 'pie\n  "Everything" : 100'
        html = to_html(src)
        assert "Everything" in html
        assert "<path" in html

    def test_pie_two_equal_slices(self):
        """50/50 split renders two distinct sector paths."""
        src = 'pie\n  "Left" : 50\n  "Right" : 50'
        html = to_html(src)
        assert "Left" in html
        assert "Right" in html
        # Two distinct slices → two data-slice attrs
        assert len(_slices(html)) == 2

    def test_pie_comment_lines_ignored(self):
        """Lines starting with %% are treated as comments and do not crash parsing."""
        src = (
            "pie\n"
            "%% this is a comment\n"
            '  "Dogs" : 386\n'
            '  "Cats" : 85'
        )
        html = to_html(src)
        assert "Dogs" in html
        assert "Cats" in html

    def test_pie_show_data_same_labels(self):
        """pie showData produces the same slice labels as plain pie."""
        src_plain = 'pie\n  title Pets\n  "Dogs" : 386\n  "Cats" : 85'
        src_show = 'pie showData\n  title Pets\n  "Dogs" : 386\n  "Cats" : 85'
        plain_slices = _slices(to_html(src_plain))
        show_slices = _slices(to_html(src_show))
        assert set(plain_slices) == set(show_slices)

    def test_pie_large_values(self):
        """Integer values in the thousands render without overflow or crash."""
        src = (
            "pie\n"
            '  "Q1" : 123456\n'
            '  "Q2" : 654321\n'
            '  "Q3" : 99999'
        )
        html = to_html(src)
        for label in ("Q1", "Q2", "Q3"):
            assert label in html
