"""Pytest tests covering every documented xychart-beta syntax behavior.

Uses the public mermaid_render.to_html() API (returns a full HTML page,
unlike the internal _dispatch helper which returns only a fragment).

Coverage focus — gaps not already in test_mermaid_layout.py:
  - Full HTML page output (to_html wraps the fragment in a complete document)
  - Horizontal orientation keyword (xychart-beta horizontal)
  - x-axis numeric range form (x-axis 1 --> 5)
  - y-axis label-only form (y-axis "Value")
  - y-axis label+range form (y-axis "Label" lo --> hi)
  - Negative values in bar data
  - 12-bar full-year chart (many bars)

Deviations from the task brief:
  - Import is `from mermaid_render import to_html`, not
    `from mermaid_layout import to_html`, because mermaid_layout is a
    backward-compat shim for mermaid_render.layout (the layout fragment
    helper) and does not export to_html. The public API lives in
    mermaid_render.__init__.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html


# ── TestXYChartBasic ──────────────────────────────────────────────────────────

class TestXYChartBasic:
    """Documented xychart syntax forms, exercised end-to-end via to_html()."""

    def test_bar_chart_renders(self):
        """Full Sales Revenue example from the mermaid xychart spec."""
        src = (
            "xychart-beta\n"
            '  title "Sales Revenue"\n'
            "  x-axis [jan, feb, mar, apr, may]\n"
            '  y-axis "Revenue (in $)" 0 --> 10000\n'
            "  bar [5000, 6000, 7500, 8200, 9100]"
        )
        html = to_html(src)
        assert html
        assert "Sales Revenue" in html

    def test_line_chart_renders(self):
        src = (
            "xychart-beta\n"
            "  x-axis [Q1, Q2, Q3, Q4]\n"
            "  y-axis 0 --> 100\n"
            "  line [10, 20, 40, 80]"
        )
        html = to_html(src)
        assert html
        # line series produces SVG polygon dots or line segments
        assert "<polygon" in html or "<line" in html

    def test_combined_bar_line(self):
        src = (
            "xychart-beta\n"
            "  x-axis [A, B, C]\n"
            "  y-axis 0 --> 100\n"
            "  bar [30, 50, 70]\n"
            "  line [20, 60, 40]"
        )
        html = to_html(src)
        assert "mermaid-layout" in html
        # bars as positioned divs, line as SVG overlay
        assert "position:absolute" in html
        assert "<polygon" in html or "<line" in html

    def test_horizontal_variant(self):
        """xychart-beta horizontal must dispatch and render without crashing."""
        src = (
            "xychart-beta horizontal\n"
            "  x-axis [A, B, C]\n"
            "  y-axis 0 --> 100\n"
            "  bar [30, 50, 70]"
        )
        html = to_html(src)
        assert html
        assert "mermaid-layout" in html

    def test_title_in_output(self):
        src = (
            "xychart-beta\n"
            '  title "Sales Revenue"\n'
            "  x-axis [jan, feb, mar, apr, may]\n"
            "  y-axis 0 --> 10000\n"
            "  bar [5000, 6000, 7500, 8200, 9100]"
        )
        html = to_html(src)
        assert "Sales Revenue" in html

    def test_x_axis_labels_in_output(self):
        src = (
            "xychart-beta\n"
            '  title "Sales Revenue"\n'
            "  x-axis [jan, feb, mar, apr, may]\n"
            "  y-axis 0 --> 10000\n"
            "  bar [5000, 6000, 7500, 8200, 9100]"
        )
        html = to_html(src)
        for label in ("jan", "feb", "mar", "apr", "may"):
            assert label in html, f"x-axis label '{label}' missing from output"


# ── TestXYChartEdgeCases ──────────────────────────────────────────────────────

class TestXYChartEdgeCases:
    """Edge cases: single value, twelve bars, negative data, title quoting."""

    def test_single_bar(self):
        src = (
            "xychart-beta\n"
            "  x-axis [Only]\n"
            "  y-axis 0 --> 100\n"
            "  bar [55]"
        )
        html = to_html(src)
        assert "mermaid-layout" in html
        assert 'data-category="Only"' in html

    def test_many_bars(self):
        """Twelve-bar (full year) chart renders without NaN or crash."""
        months = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 90, 80]
        src = (
            "xychart-beta\n"
            f"  x-axis [{', '.join(months)}]\n"
            "  y-axis 0 --> 100\n"
            f"  bar [{', '.join(str(v) for v in values)}]"
        )
        html = to_html(src)
        assert "mermaid-layout" in html
        assert "NaN" not in html
        # All twelve category labels should appear
        assert 'data-category="Jan"' in html
        assert 'data-category="Dec"' in html

    def test_negative_values(self):
        """Bar data with negative values renders without NaN (clipped to min height)."""
        src = (
            "xychart-beta\n"
            "  x-axis [Q1, Q2, Q3, Q4]\n"
            "  y-axis -50 --> 50\n"
            "  bar [-20, 10, -30, 40]"
        )
        html = to_html(src)
        assert "mermaid-layout" in html
        assert "NaN" not in html

    def test_quoted_title_with_spaces(self):
        """Quoted title text is present without surrounding quote characters."""
        src = (
            "xychart-beta\n"
            '  title "Annual Growth Rate"\n'
            "  x-axis [A, B]\n"
            "  y-axis 0 --> 100\n"
            "  bar [30, 70]"
        )
        html = to_html(src)
        assert "Annual Growth Rate" in html
        # Surrounding quotes must be stripped from the rendered output
        assert '"Annual Growth Rate"' not in html


# ── TestXYChartAxisVariants ───────────────────────────────────────────────────

class TestXYChartAxisVariants:
    """Axis syntax forms documented in the spec."""

    def test_x_axis_numeric_range(self):
        """x-axis 1 --> 5 — numeric range not parsed as categories; falls back to index labels."""
        src = (
            "xychart-beta\n"
            "  x-axis 1 --> 5\n"
            "  y-axis 0 --> 100\n"
            "  bar [20, 40, 60, 80, 100]"
        )
        html = to_html(src)
        assert "mermaid-layout" in html
        assert "NaN" not in html

    def test_y_axis_label_only(self):
        """y-axis \"Value\" — label without range; renderer uses default 0–100."""
        src = (
            "xychart-beta\n"
            "  x-axis [A, B, C]\n"
            '  y-axis "Value"\n'
            "  bar [25, 50, 75]"
        )
        html = to_html(src)
        assert "mermaid-layout" in html
        assert "NaN" not in html

    def test_y_axis_label_with_range(self):
        """y-axis \"Revenue (in $)\" 0 --> 10000 — label+range form from the spec."""
        src = (
            "xychart-beta\n"
            '  title "Sales Revenue"\n'
            "  x-axis [jan, feb, mar, apr, may]\n"
            '  y-axis "Revenue (in $)" 0 --> 10000\n'
            "  bar [5000, 6000, 7500, 8200, 9100]"
        )
        html = to_html(src)
        assert "mermaid-layout" in html
        assert "NaN" not in html

    def test_without_title(self):
        """Chart with no title line renders correctly."""
        src = (
            "xychart-beta\n"
            "  x-axis [A, B]\n"
            "  y-axis 0 --> 10\n"
            "  bar [3, 7]"
        )
        html = to_html(src)
        assert "mermaid-layout" in html


# ── TestXYChartHTMLOutput ─────────────────────────────────────────────────────

class TestXYChartHTMLOutput:
    """Tests specific to the complete HTML document returned by to_html().

    to_html() wraps the layout fragment in a standalone page (<!DOCTYPE html>
    + <body>), unlike the internal _dispatch helper which returns only the
    fragment.  These tests validate that wrapper layer.
    """

    def test_returns_full_html_document(self):
        src = "xychart-beta\n  x-axis [A, B]\n  y-axis 0 --> 100\n  bar [40, 80]"
        html = to_html(src)
        assert "<!DOCTYPE html>" in html
        assert "<body>" in html

    def test_html_is_non_empty_string(self):
        src = "xychart-beta\n  x-axis [X]\n  y-axis 0 --> 100\n  bar [50]"
        html = to_html(src)
        assert isinstance(html, str)
        assert len(html) > 200  # full page is substantially larger than a fragment

    def test_html_contains_css_variables(self):
        """The page wrapper must include CSS custom properties for theming."""
        src = "xychart-beta\n  x-axis [A, B]\n  y-axis 0 --> 100\n  bar [40, 80]"
        html = to_html(src)
        assert "--bg-primary" in html
        assert "--accent-1" in html
