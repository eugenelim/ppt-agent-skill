#!/usr/bin/env python3
"""Regression tests for xychart-beta renderer fixes.

Covers three fixes in _layout_xychart:
  1. Y-axis range ignored when label present: y-axis "Revenue" 0 --> 10000
  2. Y-axis label (title) not rendered
  3. Horizontal grid lines missing
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _dispatch


# ── helpers ───────────────────────────────────────────────────────────────────

def _render(src: str, width: int = 800) -> str:
    return _dispatch(src, None, width)


# ── Fix 1: Y-axis range parsed when quoted label precedes it ─────────────────

class TestYAxisRangeWithLabel:
    """y-axis "label" min --> max must parse both the label and the range."""

    SRC_MIXED = (
        "xychart-beta\n"
        '  title "Monthly Revenue vs Target"\n'
        '  x-axis [Jan, Feb, Mar, Apr, May, Jun]\n'
        '  y-axis "Amount ($k)" 0 --> 120\n'
        "  bar [45, 52, 60, 58, 72, 88]\n"
        "  line [50, 55, 60, 65, 70, 75]\n"
    )

    def test_yaxis_max_120_in_tick_labels(self):
        """Tick labels must reach 120 (the explicit max), not default 100."""
        html = _render(self.SRC_MIXED)
        # The max tick label should be 120
        assert ">120<" in html, "Y-axis max tick label 120 missing (range was ignored)"

    def test_yaxis_min_0_present(self):
        html = _render(self.SRC_MIXED)
        assert ">0<" in html, "Y-axis min tick 0 missing"

    def test_bar_heights_scaled_against_120(self):
        """Bar for Jan=45 with range 0-120: height fraction = 45/120 = 0.375.
        Without the fix the range defaults to 0-100, giving fraction 45/100 = 0.45.
        The bars should be shorter when max is 120 vs 100."""
        html_120 = _render(self.SRC_MIXED, width=800)
        # With range 0-100 (wrong) Jan bar height would be larger than with 0-120
        src_100 = self.SRC_MIXED.replace('y-axis "Amount ($k)" 0 --> 120', 'y-axis 0 --> 100')
        html_100 = _render(src_100, width=800)
        # Extract bar heights (height: NNNpx pattern in bar divs)
        heights_120 = [int(m) for m in re.findall(r'data-category="Jan"[^>]+height:(\d+)px', html_120)]
        heights_100 = [int(m) for m in re.findall(r'data-category="Jan"[^>]+height:(\d+)px', html_100)]
        assert heights_120, "Jan bar not found in 0-120 render"
        assert heights_100, "Jan bar not found in 0-100 render"
        # Bar should be shorter when the range is larger (0-120 vs 0-100)
        assert heights_120[0] < heights_100[0], (
            f"Jan bar height {heights_120[0]} should be < {heights_100[0]} "
            "when max is 120 vs 100"
        )

    def test_range_only_syntax_still_works(self):
        """y-axis 0 --> 100 (no label) must still parse correctly."""
        src = (
            "xychart-beta\n"
            "  x-axis [A, B, C]\n"
            "  y-axis 0 --> 50\n"
            "  bar [10, 25, 50]\n"
        )
        html = _render(src)
        assert ">50<" in html, "Max tick 50 missing in range-only syntax"
        assert ">0<" in html, "Min tick 0 missing"

    def test_xychart_mixed_fixture(self):
        """The xychart-mixed.mmd fixture must show range 0-120."""
        fixture = REPO_ROOT / "tests" / "fixtures" / "xychart-mixed.mmd"
        src = fixture.read_text(encoding="utf-8")
        html = _render(src, width=900)
        assert ">120<" in html, (
            "xychart-mixed.mmd: max tick 120 missing — y-axis labeled range was not parsed"
        )

    def test_large_range_with_label(self):
        """y-axis "Revenue ($)" 0 --> 10000 must use max 10000."""
        src = (
            "xychart-beta\n"
            '  y-axis "Revenue ($)" 0 --> 10000\n'
            "  x-axis [Q1, Q2]\n"
            "  bar [2500, 8000]\n"
        )
        html = _render(src)
        assert ">10000<" in html, "Max tick 10000 missing for labeled large range"


# ── Fix 2: Y-axis label (title) rendered ─────────────────────────────────────

class TestYAxisLabel:
    """Y-axis label from y-axis "label" min --> max must appear in HTML."""

    def test_y_label_attr_present(self):
        src = (
            "xychart-beta\n"
            '  y-axis "Amount ($k)" 0 --> 120\n'
            "  x-axis [Jan, Feb]\n"
            "  bar [40, 80]\n"
        )
        html = _render(src)
        assert 'data-y-label="Amount ($k)"' in html, (
            "Y-axis label element with data-y-label attribute missing"
        )

    def test_y_label_text_present(self):
        src = (
            "xychart-beta\n"
            '  y-axis "Revenue" 0 --> 100\n'
            "  x-axis [A, B]\n"
            "  bar [30, 70]\n"
        )
        html = _render(src)
        assert "Revenue" in html, "Y-axis label text 'Revenue' not in output"

    def test_y_label_uses_vertical_writing_mode(self):
        src = (
            "xychart-beta\n"
            '  y-axis "Sales" 0 --> 500\n'
            "  x-axis [Q1]\n"
            "  bar [300]\n"
        )
        html = _render(src)
        assert "writing-mode:vertical" in html, (
            "Y-axis label must use writing-mode:vertical for vertical orientation"
        )

    def test_no_y_label_when_range_only(self):
        """When y-axis has no quoted label, no data-y-label element should appear."""
        src = (
            "xychart-beta\n"
            "  y-axis 0 --> 100\n"
            "  x-axis [A, B]\n"
            "  bar [30, 70]\n"
        )
        html = _render(src)
        assert "data-y-label" not in html, (
            "data-y-label must not appear when y-axis has no quoted label"
        )

    def test_mixed_fixture_y_label(self):
        """xychart-mixed.mmd must have Y-axis label 'Amount ($k)'."""
        fixture = REPO_ROOT / "tests" / "fixtures" / "xychart-mixed.mmd"
        src = fixture.read_text(encoding="utf-8")
        html = _render(src, width=900)
        assert "Amount" in html and "($k)" in html, (
            "xychart-mixed.mmd Y-axis label 'Amount ($k)' missing from output"
        )

    def test_special_chars_in_y_label_escaped(self):
        """HTML special chars in the label must be escaped."""
        src = (
            "xychart-beta\n"
            '  y-axis "Price <USD>" 0 --> 100\n'
            "  x-axis [A]\n"
            "  bar [50]\n"
        )
        html = _render(src)
        # Should be HTML-escaped
        assert "&lt;" in html or "Price" in html, "Special chars in y-label not handled"
        assert "<USD>" not in html, "Unescaped < > in y-label (XSS risk)"


# ── Fix 3: Horizontal grid lines ─────────────────────────────────────────────

class TestXyChartGridLines:
    """Horizontal grid lines must appear at each Y-axis tick level."""

    SRC = (
        "xychart-beta\n"
        "  title Sales\n"
        "  x-axis [Jan, Feb, Mar]\n"
        "  y-axis 0 --> 100\n"
        "  bar [30, 60, 90]\n"
    )

    def test_grid_lines_present(self):
        html = _render(self.SRC)
        assert "stroke-dasharray" in html, "No dashed grid lines found in xychart output"

    def test_grid_line_count(self):
        """With _tick_count=5, there should be 5 grid lines (one per non-zero tick)."""
        html = _render(self.SRC)
        # Count dashed horizontal lines (grid lines have stroke-dasharray)
        grid_lines = re.findall(r'stroke-dasharray="4 3"', html)
        assert len(grid_lines) >= 5, (
            f"Expected ≥5 grid lines (one per non-zero Y tick), got {len(grid_lines)}"
        )

    def test_grid_lines_span_chart_width(self):
        """Grid lines must cross the full plot area (x2 = cx_start + cw)."""
        html = _render(self.SRC, width=800)
        # Capture full <line .../> elements that have the grid dasharray
        full_lines = re.findall(r'<line[^>]+stroke-dasharray="4 3"[^>]*/>', html)
        assert full_lines, "No grid line elements found"
        # At least one must have x2 > 200 (plot area extends well past 200px)
        found_wide = any(
            (m2 := re.search(r'x2="(\d+)"', elem)) and int(m2.group(1)) > 200
            for elem in full_lines
        )
        assert found_wide, "Grid lines do not extend across the chart plot area"

    def test_grid_lines_not_at_bottom_baseline(self):
        """The bottom baseline (y = cy_top + ch) must NOT have a dashed grid line."""
        html = _render(self.SRC, width=800)
        # Bottom baseline y = PAD_V + (20 if title) + ch = 52 + 192 = 244
        # Grid lines must not be at y=244
        baseline_grid = re.findall(
            r'x1="80" y1="244" x2="\d+" y2="244" [^>]*stroke-dasharray', html
        )
        assert not baseline_grid, (
            "Bottom baseline should not be a dashed grid line (it's already a solid axis line)"
        )

    def test_combined_bar_line_still_has_grids(self):
        """Grid lines must be present even when both bar and line series are rendered."""
        src = (
            "xychart-beta\n"
            "  x-axis [A, B, C]\n"
            "  y-axis 0 --> 100\n"
            "  bar [30, 60, 90]\n"
            "  line [20, 50, 80]\n"
        )
        html = _render(src, width=800)
        assert "stroke-dasharray" in html, "Grid lines missing in combined bar+line chart"


# ── Regression: existing behaviour preserved ─────────────────────────────────

class TestXyChartRegressions:
    """Guards: fixes must not break existing xychart behaviour."""

    def test_basic_fixture_still_renders(self):
        fixture = REPO_ROOT / "tests" / "fixtures" / "xychart-basic.mmd"
        src = fixture.read_text(encoding="utf-8")
        html = _render(src, width=700)
        assert "diagram mermaid-layout" in html
        assert "Monthly Revenue" in html

    def test_basic_fixture_max_100(self):
        """xychart-basic has y-axis 0 --> 100; max tick must be 100."""
        fixture = REPO_ROOT / "tests" / "fixtures" / "xychart-basic.mmd"
        src = fixture.read_text(encoding="utf-8")
        html = _render(src, width=700)
        assert ">100<" in html, "Max tick 100 missing for xychart-basic"

    def test_x_axis_labels_still_present(self):
        fixture = REPO_ROOT / "tests" / "fixtures" / "xychart-basic.mmd"
        src = fixture.read_text(encoding="utf-8")
        html = _render(src, width=700)
        for label in ("Jan", "Feb", "Mar", "Apr", "May"):
            assert label in html, f"X-axis label {label!r} missing"

    def test_bar_divs_have_data_category(self):
        src = (
            "xychart-beta\n"
            "  x-axis [Alpha, Beta]\n"
            "  y-axis 0 --> 100\n"
            "  bar [40, 80]\n"
        )
        html = _render(src)
        assert 'data-category="Alpha"' in html
        assert 'data-category="Beta"' in html

    def test_line_series_polygon_present(self):
        src = (
            "xychart-beta\n"
            "  x-axis [A, B, C]\n"
            "  y-axis 0 --> 100\n"
            "  line [30, 60, 90]\n"
        )
        html = _render(src)
        assert "<polygon" in html, "Line series dot markers missing"

    def test_no_nan_in_output(self):
        src = (
            "xychart-beta\n"
            '  y-axis "Revenue" 0 --> 120\n'
            "  x-axis [Jan, Feb]\n"
            "  bar [45, 88]\n"
        )
        html = _render(src)
        assert "NaN" not in html
