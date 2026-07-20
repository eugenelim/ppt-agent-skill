"""Tests for quadrantChart syntax coverage.

Covers every documented syntax behavior from
https://mermaid.ai/open-source/syntax/quadrantChart.html.

Import pattern: `to_html` lives in `mermaid_render`, not the
`mermaid_layout` shim (the shim re-exports `mermaid_render.layout`
submodule symbols only, not the top-level package API).
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
# Helpers
# ---------------------------------------------------------------------------

_FULL_SRC = """\
quadrantChart
  title Effort vs Impact
  x-axis Low Effort --> High Effort
  y-axis Low Impact --> High Impact
  quadrant-1 Quick Wins
  quadrant-2 Major Projects
  quadrant-3 Time Wasters
  quadrant-4 Fill Ins
  Feature A: [0.3, 0.6]
  Feature B: [0.45, 0.23]
  Feature C: [0.57, 0.69]
"""


# ---------------------------------------------------------------------------
# TestQuadrantBasic
# ---------------------------------------------------------------------------

class TestQuadrantBasic:
    def test_full_quadrant_renders(self):
        """Full chart with all optional fields renders and includes point labels."""
        html = to_html(_FULL_SRC)
        assert html
        assert "Feature A" in html
        assert "Feature B" in html
        assert "Feature C" in html

    def test_canvas_at_least_800px(self):
        """Default canvas width must be >= 800px (regression: was 480px before fix)."""
        src = (
            "quadrantChart\n"
            "  x-axis Low --> High\n"
            "  y-axis Bad --> Good\n"
            "  A: [0.5, 0.5]"
        )
        html = to_html(src)
        m = re.search(r"width:(\d+)px", html)
        assert m, "no width:Npx found in rendered HTML"
        assert int(m.group(1)) >= 800

    def test_html_is_full_page(self):
        """to_html wraps the fragment in a complete HTML document."""
        html = to_html(_FULL_SRC)
        assert re.search(r"<!doctype\s+html", html, re.I), "missing DOCTYPE"
        assert "</html>" in html

    def test_title_in_output(self):
        """Chart title text appears in rendered HTML."""
        src = (
            "quadrantChart\n"
            "  title My Special Title\n"
            "  x-axis Low --> High\n"
            "  y-axis Bad --> Good\n"
            "  A: [0.1, 0.9]"
        )
        html = to_html(src)
        assert "My Special Title" in html


# ---------------------------------------------------------------------------
# TestQuadrantPoints
# ---------------------------------------------------------------------------

class TestQuadrantPoints:
    def test_multiple_points(self):
        """All point names appear as data-point attributes in the output."""
        names = ["Alpha", "Beta", "Gamma"]
        points = "\n".join(f"  {n}: [{i * 0.3:.1f}, {0.5}]" for i, n in enumerate(names))
        src = f"quadrantChart\n  x-axis Low --> High\n  y-axis Low --> High\n{points}"
        html = to_html(src)
        for name in names:
            assert f'data-point="{name}"' in html, f"missing data-point for {name!r}"

    def test_point_label_in_output(self):
        """Point label appears as both data-point attribute and visible text."""
        src = (
            "quadrantChart\n"
            "  x-axis Low --> High\n"
            "  y-axis Bad --> Good\n"
            "  SpecialPoint: [0.4, 0.7]"
        )
        html = to_html(src)
        assert 'data-point="SpecialPoint"' in html
        assert "SpecialPoint" in html

    def test_point_at_origin(self):
        """Point at [0.0, 0.0] (bottom-left corner) renders without error."""
        src = "quadrantChart\n  x-axis Low --> High\n  y-axis Low --> High\n  Origin: [0.0, 0.0]"
        html = to_html(src)
        assert html
        assert "Origin" in html

    def test_point_at_far_corner(self):
        """Point at [1.0, 1.0] (top-right corner) renders without error."""
        src = "quadrantChart\n  x-axis Low --> High\n  y-axis Low --> High\n  Corner: [1.0, 1.0]"
        html = to_html(src)
        assert html
        assert "Corner" in html


# ---------------------------------------------------------------------------
# TestQuadrantAxes
# ---------------------------------------------------------------------------

class TestQuadrantAxes:
    def test_x_axis_labels_in_output(self):
        """Left and right labels from x-axis Low --> High appear in output."""
        src = (
            "quadrantChart\n"
            "  x-axis LeftLabel --> RightLabel\n"
            "  y-axis Bad --> Good\n"
            "  A: [0.5, 0.5]"
        )
        html = to_html(src)
        assert "LeftLabel" in html
        assert "RightLabel" in html

    def test_x_axis_labels_rendered_y_axis_omitted(self):
        """x-axis left/right labels appear in output; y-axis labels are parsed
        but the renderer currently omits them from the DOM (known gap)."""
        src = (
            "quadrantChart\n"
            "  x-axis XLeft --> XRight\n"
            "  y-axis YBottom --> YTop\n"
            "  A: [0.5, 0.5]"
        )
        html = to_html(src)
        # x-axis labels are rendered
        assert "XLeft" in html
        assert "XRight" in html
        # y-axis labels are parsed but not yet emitted (renderer gap)
        assert "YBottom" not in html
        assert "YTop" not in html

    def test_default_axis_labels(self):
        """Without x-axis/y-axis lines the defaults 'Low' and 'High' appear."""
        src = "quadrantChart\n  A: [0.5, 0.5]"
        html = to_html(src)
        assert "Low" in html
        assert "High" in html

    def test_all_four_quadrant_labels_in_output(self):
        """All four quadrant-N label strings appear in the rendered output."""
        src = (
            "quadrantChart\n"
            "  quadrant-1 TopRight\n"
            "  quadrant-2 TopLeft\n"
            "  quadrant-3 BottomLeft\n"
            "  quadrant-4 BottomRight\n"
            "  A: [0.5, 0.5]"
        )
        html = to_html(src)
        for label in ("TopRight", "TopLeft", "BottomLeft", "BottomRight"):
            assert label in html, f"missing quadrant label {label!r}"

    def test_axis_without_arrows_x_label_appears(self):
        """x-axis without --> still captures the label text (x-axis left side)."""
        src = (
            "quadrantChart\n"
            "  x-axis Urgency\n"
            "  y-axis Impact\n"
            "  A: [0.5, 0.5]"
        )
        html = to_html(src)
        # x-axis label is rendered; y-axis label is not (renderer gap)
        assert "Urgency" in html

    def test_axis_quoted_x_label(self):
        """Quoted x-axis label (x-axis \"Urgency\") has its text in the output."""
        src = (
            'quadrantChart\n'
            '  x-axis "Urgency"\n'
            '  y-axis "Impact"\n'
            '  A: [0.5, 0.5]'
        )
        html = to_html(src)
        # x-axis quoted label is rendered; y-axis label is not (renderer gap)
        assert "Urgency" in html


# ---------------------------------------------------------------------------
# TestQuadrantEdgeCases
# ---------------------------------------------------------------------------

class TestQuadrantEdgeCases:
    def test_without_quadrant_labels(self):
        """Chart renders fine when no quadrant-N lines are given."""
        src = (
            "quadrantChart\n"
            "  x-axis Low --> High\n"
            "  y-axis Bad --> Good\n"
            "  Point A: [0.2, 0.8]"
        )
        html = to_html(src)
        assert html
        assert "Point A" in html

    def test_without_axis_lines(self):
        """Chart renders with only points and no x-axis/y-axis directives."""
        src = (
            "quadrantChart\n"
            "  A: [0.1, 0.2]\n"
            "  B: [0.8, 0.9]"
        )
        html = to_html(src)
        assert html
        assert "A" in html
        assert "B" in html

    def test_no_points_renders_without_error(self):
        """Chart with axes but no data points renders without raising."""
        src = (
            "quadrantChart\n"
            "  x-axis Low --> High\n"
            "  y-axis Low --> High"
        )
        html = to_html(src)
        assert html

    def test_point_name_with_spaces(self):
        """Point names containing spaces appear correctly in the output."""
        src = (
            "quadrantChart\n"
            "  x-axis Low --> High\n"
            "  y-axis Low --> High\n"
            "  Feature Alpha: [0.6, 0.8]"
        )
        html = to_html(src)
        assert "Feature Alpha" in html


# ---------------------------------------------------------------------------
# TestQuadrantLayout
# ---------------------------------------------------------------------------

class TestQuadrantLayout:
    def test_outer_border_rect_present(self):
        """SVG rect element (outer border of the quadrant grid) is in the output."""
        src = (
            "quadrantChart\n"
            "  x-axis Low --> High\n"
            "  y-axis Low --> High\n"
            "  A: [0.5, 0.5]"
        )
        html = to_html(src)
        assert "<rect " in html

    def test_divider_lines_present(self):
        """At least two SVG line elements (midpoint dividers) are in the output."""
        src = (
            "quadrantChart\n"
            "  x-axis Low --> High\n"
            "  y-axis Low --> High\n"
            "  A: [0.5, 0.5]"
        )
        html = to_html(src)
        assert html.count("<line ") >= 2

    def test_diagram_wrapper_class(self):
        """Rendered fragment has the standard 'diagram mermaid-layout' class."""
        src = (
            "quadrantChart\n"
            "  x-axis Low --> High\n"
            "  y-axis Low --> High\n"
            "  A: [0.5, 0.5]"
        )
        html = to_html(src)
        assert 'class="diagram mermaid-layout"' in html
