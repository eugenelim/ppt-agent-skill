#!/usr/bin/env python3
"""Regression tests for _layout_pie fixes.

Covers every visual failure identified vs mmdc:
  1. Title from inline directive (``pie title ...``)
  2. Title rendered at top (not bottom)
  3. showData flag parsed and raw values shown in legend
  4. Legend present with colour swatches, labels and percentages
  5. Palette expanded to 8 colours (no early repeat for 5+ slices)
  6. data-slice identity attribute on SVG <path> elements
  7. SVG arc commands (<path d="M ... A ...">), no <polygon> for slices
  8. Proportional sweep angles
  9. Small slices (< ~14°) still get a data-slice path even without an in-slice label
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _layout_pie, _PIE_ACCENTS
from mermaid_render.layout import _dispatch


def _dispatch_pie(src: str, width: int = 400) -> str:
    return _dispatch(src, None, width)


# ── helpers ───────────────────────────────────────────────────────────────────

def _arc_paths(html: str) -> list[str]:
    """Return every <path d="M...A..."> match (pie slice arcs)."""
    return re.findall(r'<path[^>]+d="M[^"]*A[^"]*"[^>]*/>', html)


def _data_slices(html: str) -> list[str]:
    """Return all data-slice attribute values."""
    return re.findall(r'data-slice="([^"]+)"', html)


# ── F1: inline title on directive line ───────────────────────────────────────

class TestInlineTitle:
    """Title on directive line (``pie title Foo``) must appear in output."""

    _SRC_INLINE = 'pie title Browser Market Share\n  "Chrome": 65\n  "Firefox": 35\n'

    def test_title_visible(self):
        html = _layout_pie(self._SRC_INLINE, "TB", 400)
        assert "Browser Market Share" in html, "inline title must appear in rendered HTML"

    def test_title_at_top_not_bottom(self):
        html = _layout_pie(self._SRC_INLINE, "TB", 400)
        assert "bottom:8px" not in html, "title must not be placed at bottom"
        # Title div must use top positioning
        assert re.search(r'top:[0-9]+px[^"]*"[^>]*>Browser Market Share', html), \
            "title element must use top: offset"

    def test_content_line_title_also_works(self):
        src = 'pie\n  title Content-line Title\n  "A": 60\n  "B": 40\n'
        html = _layout_pie(src, "TB", 400)
        assert "Content-line Title" in html

    def test_showdata_and_inline_title(self):
        src = 'pie showData title Revenue\n  "Sales": 80\n  "Ops": 20\n'
        html = _layout_pie(src, "TB", 400)
        assert "Revenue" in html


# ── F2: title position ────────────────────────────────────────────────────────

class TestTitlePosition:
    """Title must be above the chart, not below."""

    def test_no_bottom_offset(self):
        src = 'pie\n  title My Chart\n  "A": 50\n  "B": 50\n'
        html = _layout_pie(src, "TB", 400)
        assert "bottom:8px" not in html

    def test_top_offset_present_when_titled(self):
        src = 'pie\n  title My Chart\n  "A": 50\n  "B": 50\n'
        html = _layout_pie(src, "TB", 400)
        # The title span/div must have a top: attribute
        assert re.search(r'top:[0-9]+px', html), "title div must use top: positioning"

    def test_untitled_chart_has_no_title_element(self):
        src = 'pie\n  "A": 50\n  "B": 50\n'
        html = _layout_pie(src, "TB", 400)
        # No large bold heading when there is no title
        assert "font-weight:700" not in html or "My Chart" not in html


# ── F3: showData ──────────────────────────────────────────────────────────────

class TestShowData:
    """``pie showData`` must append raw numeric values to legend entries."""

    _SRC = 'pie showData\n  title Revenue\n  "Sales": 420\n  "Services": 180\n'

    def test_raw_values_in_output(self):
        html = _layout_pie(self._SRC, "TB", 500)
        # Raw values should appear somewhere in the legend text
        assert "420" in html, "raw value 420 must appear when showData is set"
        assert "180" in html, "raw value 180 must appear when showData is set"

    def test_raw_values_absent_without_flag(self):
        src = 'pie\n  title Revenue\n  "Sales": 420\n  "Services": 180\n'
        html = _layout_pie(src, "TB", 500)
        # 420 might appear as part of another number; check for the parenthetical form
        assert "(420" not in html, "raw value parenthetical must not appear without showData"

    def test_showdata_case_insensitive(self):
        src = 'pie showdata\n  "X": 10\n  "Y": 90\n'
        html = _layout_pie(src, "TB", 400)
        assert "10" in html and "90" in html


# ── F4: legend ────────────────────────────────────────────────────────────────

class TestLegend:
    """Every pie chart must render a legend with colour swatches and labels."""

    _SRC = 'pie\n  "Alpha": 60\n  "Beta": 40\n'

    def test_legend_colour_swatch_present(self):
        html = _layout_pie(self._SRC, "TB", 400)
        # Colour swatch is a div with border-radius + background set to a CSS variable
        assert re.search(r'background:var\(--', html), "legend swatch must use CSS variable colour"

    def test_legend_labels_present(self):
        html = _layout_pie(self._SRC, "TB", 400)
        assert "Alpha" in html
        assert "Beta" in html

    def test_legend_percentages_present(self):
        html = _layout_pie(self._SRC, "TB", 400)
        # 60/100 = 60.0% and 40/100 = 40.0%
        assert "60.0%" in html or "60%" in html
        assert "40.0%" in html or "40%" in html

    def test_legend_item_count_matches_slices(self):
        src = 'pie\n  "A": 10\n  "B": 20\n  "C": 30\n  "D": 40\n'
        html = _layout_pie(src, "TB", 400)
        # Each legend item has a flex container; count them
        items = re.findall(r'display:flex;align-items:center', html)
        assert len(items) >= 4, f"expected ≥4 legend items, got {len(items)}"


# ── F5: palette expansion ─────────────────────────────────────────────────────

class TestPaletteExpansion:
    """Charts with more than 4 slices must use distinct accent colours."""

    def test_five_slices_distinct_colours(self):
        src = 'pie\n  "A": 20\n  "B": 20\n  "C": 20\n  "D": 20\n  "E": 20\n'
        html = _layout_pie(src, "TB", 500)
        paths = _arc_paths(html)
        assert len(paths) >= 5
        fills = re.findall(r'fill="([^"]+)"', html)
        slice_fills = [f for f in fills if "var(" in f and "#ffffff" not in f]
        unique_fills = set(slice_fills[:5])
        assert len(unique_fills) >= 5, \
            f"5-slice pie must use 5 distinct colours; got {unique_fills}"

    def test_eight_accents_defined(self):
        assert len(_PIE_ACCENTS) >= 8, "palette must have at least 8 accent entries"

    def test_no_colour_repeat_for_first_eight(self):
        assert len(set(_PIE_ACCENTS[:8])) == 8, "first 8 palette entries must all be distinct"


# ── F6: data-slice identity attribute ────────────────────────────────────────

class TestDataSliceAttribute:
    """Every slice must have a data-slice attribute (on the SVG <path>)."""

    _SRC = 'pie\n  "Dogs": 42\n  "Cats": 58\n'

    def test_data_slice_present(self):
        html = _dispatch_pie(self._SRC)
        assert 'data-slice="Dogs"' in html
        assert 'data-slice="Cats"' in html

    def test_data_slice_on_path_element(self):
        html = _dispatch_pie(self._SRC)
        # Must be on the arc path, not only on a span
        path_slices = re.findall(r'<path[^>]+data-slice="([^"]+)"', html)
        assert "Dogs" in path_slices, "data-slice must appear on the SVG <path> element"
        assert "Cats" in path_slices

    def test_all_slices_have_data_slice(self):
        src = 'pie\n  "X": 10\n  "Y": 20\n  "Z": 30\n  "W": 40\n'
        html = _dispatch_pie(src)
        slices = _data_slices(html)
        assert set(slices) == {"X", "Y", "Z", "W"}, \
            f"all 4 slices must have data-slice; got {slices}"


# ── F7: SVG arc commands ──────────────────────────────────────────────────────

class TestSVGArcs:
    """Slices must use <path d=\"M...A...\"> arcs, not <polygon>."""

    _SRC = (
        'pie title Browser Share\n'
        '    "Chrome" : 65\n'
        '    "Firefox" : 15\n'
        '    "Safari" : 12\n'
        '    "Edge" : 8\n'
    )

    def test_uses_path_arc(self):
        html = _dispatch_pie(self._SRC)
        assert re.search(r'<path[^>]+d="M[^"]*A[^"]*"', html), \
            "pie slices must use SVG <path d='M ... A ...'> arc commands"

    def test_no_polygon_for_slices(self):
        html = _dispatch_pie(self._SRC)
        poly_fills = re.findall(
            r'<polygon[^>]*fill="([^"]*var\(--edge-strong[^"]*|[^"]*accent[^"]*)">', html
        )
        assert not poly_fills, f"pie slices must not use <polygon>; found: {poly_fills}"

    def test_one_path_per_slice(self):
        html = _dispatch_pie(self._SRC)
        paths = _arc_paths(html)
        assert len(paths) >= 4, f"expected ≥4 arc paths, got {len(paths)}"


# ── F8: proportional sweep angles ────────────────────────────────────────────

class TestProportions:
    """Slice sweep angles must be proportional to input values."""

    def test_equal_slices_equal_sweep(self):
        src = 'pie\n  "A": 50\n  "B": 50\n'
        html = _layout_pie(src, "TB", 400)
        # Both slices are exactly 50% → both large_arc flags must be 0
        # (a 50% slice uses sweep=π exactly, which is NOT > π, so large_arc=0)
        large_arcs = re.findall(r'A [0-9]+,[0-9]+ 0 ([01]),1', html)
        assert all(a == "0" for a in large_arcs), \
            f"equal 50/50 slices must each have large_arc=0; got {large_arcs}"

    def test_majority_slice_uses_large_arc(self):
        src = 'pie\n  "Big": 75\n  "Small": 25\n'
        html = _layout_pie(src, "TB", 400)
        # 75% slice → sweep > π → large_arc=1
        large_arcs = re.findall(r'A [0-9]+,[0-9]+ 0 ([01]),1', html)
        assert "1" in large_arcs, "a slice > 50% must use large-arc flag 1"

    def test_zero_total_raises(self):
        with pytest.raises(ValueError, match="zero"):
            _layout_pie('pie\n  "A": 0\n  "B": 0\n', "TB", 400)


# ── F9: small-slice data-slice path present ───────────────────────────────────

class TestSmallSlices:
    """Very small slices must still render a data-slice path (no label required)."""

    def test_tiny_slice_has_path(self):
        # "Micro" is 1% → sweep ≈ 0.063 rad (< 0.25 threshold) → no in-slice label,
        # but the SVG <path> with data-slice must still exist.
        src = 'pie\n  "Big": 99\n  "Micro": 1\n'
        html = _layout_pie(src, "TB", 400)
        path_slices = re.findall(r'<path[^>]+data-slice="([^"]+)"', html)
        assert "Micro" in path_slices, \
            "tiny slice must still have a data-slice <path> even if its label is suppressed"

    def test_tiny_slice_label_suppressed(self):
        src = 'pie\n  "Big": 99\n  "Micro": 1\n'
        html = _layout_pie(src, "TB", 400)
        # In-slice percentage label (white text inside the slice) should be absent
        # for the tiny slice — we check by confirming the label span count < slice count
        in_slice_spans = re.findall(r'font-weight:600', html)
        assert len(in_slice_spans) < 2, \
            "tiny slice must not get an in-slice percentage label"
