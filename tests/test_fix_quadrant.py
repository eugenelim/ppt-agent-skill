#!/usr/bin/env python3
"""Regression tests for _layout_quadrant fixes.

Covers:
- Y-axis labels rendered (previously silently dropped — the primary bug)
- Quadrant background fills rendered
- Data-point dots are <circle> elements (not polygon approximations)
- Center dividers are solid (no stroke-dasharray)
- All pre-existing contract: title, x-axis labels, quadrant labels, data-point
  HTML spans with data-point attribute still present
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _dispatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASIC_SRC = """\
quadrantChart
    title Product Prioritization
    x-axis Low Effort --> High Effort
    y-axis Low Impact --> High Impact
    quadrant-1 Do First
    quadrant-2 Plan
    quadrant-3 Delegate
    quadrant-4 Eliminate
    Feature A: [0.3, 0.8]
    Feature B: [0.7, 0.6]
    Feature C: [0.2, 0.3]
"""

_MINIMAL_SRC = """\
quadrantChart
    x-axis Cheap --> Expensive
    y-axis Low --> High
    Alpha: [0.1, 0.9]
    Beta: [0.9, 0.1]
"""

_NO_LABELS_SRC = """\
quadrantChart
    Gamma: [0.5, 0.5]
"""

_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "quadrant-basic.mmd"


def _html(src: str, width: int = 480) -> str:
    return _dispatch(src, None, width)


# ---------------------------------------------------------------------------
# Y-axis labels (primary bug fix)
# ---------------------------------------------------------------------------

class TestYAxisLabels:
    def test_y_axis_low_label_rendered(self):
        """y-axis low label 'Low Impact' must appear in rendered HTML."""
        html = _html(_BASIC_SRC)
        assert "Low Impact" in html, "y-axis low label not rendered"

    def test_y_axis_high_label_rendered(self):
        """y-axis high label 'High Impact' must appear in rendered HTML."""
        html = _html(_BASIC_SRC)
        assert "High Impact" in html, "y-axis high label not rendered"

    def test_y_axis_labels_from_minimal_src(self):
        """Y-axis labels rendered even without title or quadrant labels."""
        html = _html(_MINIMAL_SRC)
        assert "Low" in html
        assert "High" in html

    def test_y_axis_labels_are_in_svg(self):
        """Y-axis labels are SVG <text> elements inside the SVG block."""
        html = _html(_BASIC_SRC)
        # The SVG text elements must appear before </svg>
        svg_close = html.index("</svg>")
        svg_content = html[:svg_close]
        assert "Low Impact" in svg_content, "y-axis Low label not inside SVG"
        assert "High Impact" in svg_content, "y-axis High label not inside SVG"

    def test_y_axis_labels_rotated(self):
        """Y-axis SVG text must use rotate transform for legibility."""
        html = _html(_BASIC_SRC)
        assert "rotate(-90," in html, "y-axis text must use rotate(-90,...)"

    def test_y_axis_default_labels_when_not_specified(self):
        """Default y-axis labels 'Low' / 'High' used when y-axis not declared."""
        html = _html(_NO_LABELS_SRC)
        # Default labels still appear via the SVG text elements
        svg_close = html.index("</svg>")
        svg_content = html[:svg_close]
        assert "Low" in svg_content
        assert "High" in svg_content

    def test_y_axis_labels_from_fixture_file(self):
        """Fixture file quadrant-basic.mmd: y-axis labels present."""
        src = _FIXTURE_PATH.read_text()
        html = _html(src)
        assert "Low Impact" in html
        assert "High Impact" in html


# ---------------------------------------------------------------------------
# X-axis labels (pre-existing, must still work)
# ---------------------------------------------------------------------------

class TestXAxisLabels:
    def test_x_axis_low_label_rendered(self):
        html = _html(_BASIC_SRC)
        assert "Low Effort" in html

    def test_x_axis_high_label_rendered(self):
        html = _html(_BASIC_SRC)
        assert "High Effort" in html

    def test_x_axis_labels_below_chart(self):
        """X-axis labels must appear in the HTML layer (after </svg>)."""
        html = _html(_BASIC_SRC)
        svg_close_pos = html.index("</svg>")
        after_svg = html[svg_close_pos:]
        assert "Low Effort" in after_svg
        assert "High Effort" in after_svg


# ---------------------------------------------------------------------------
# Quadrant background fills
# ---------------------------------------------------------------------------

class TestQuadrantBackgrounds:
    def test_four_background_rects_present(self):
        """Four filled rects for quadrant backgrounds must appear in SVG."""
        html = _html(_BASIC_SRC)
        # Count filled background rects (stroke="none")
        assert html.count('stroke="none"') >= 4, (
            "Expected at least 4 quadrant background rects with stroke=none"
        )

    def test_background_fills_use_rgba(self):
        """Quadrant backgrounds use rgba() fills (subtle tints)."""
        html = _html(_BASIC_SRC)
        assert "rgba(" in html, "Expected rgba() fills for quadrant backgrounds"

    def test_background_rects_in_svg(self):
        """Background rects are inside the SVG block."""
        html = _html(_BASIC_SRC)
        svg_close = html.index("</svg>")
        svg_content = html[:svg_close]
        assert 'stroke="none"' in svg_content


# ---------------------------------------------------------------------------
# Data-point circles (not polygons)
# ---------------------------------------------------------------------------

class TestDataPointCircles:
    def test_points_rendered_as_circle_elements(self):
        """Data points must use SVG <circle> elements."""
        html = _html(_BASIC_SRC)
        assert "<circle " in html, "Expected <circle> for data points"

    def test_no_polygon_for_points(self):
        """<polygon> elements must not be used for data-point markers."""
        html = _html(_BASIC_SRC)
        # There should be no polygon in the SVG (only circles for points)
        assert "<polygon" not in html, (
            "<polygon> found — data points must use <circle> not polygon"
        )

    def test_circle_has_fill(self):
        """Data-point circles must have a fill colour."""
        html = _html(_BASIC_SRC)
        # Every <circle> should have a fill attribute
        import re
        circles = re.findall(r'<circle[^>]+>', html)
        assert circles, "No <circle> elements found"
        for c in circles:
            assert 'fill=' in c, f"circle missing fill: {c}"

    def test_circle_count_matches_points(self):
        """Number of <circle> elements matches number of data points."""
        import re
        html = _html(_BASIC_SRC)
        circles = re.findall(r'<circle ', html)
        assert len(circles) == 3, f"Expected 3 circles, got {len(circles)}"

    def test_minimal_points_circle_count(self):
        """Two data points in minimal src → two circles."""
        import re
        html = _html(_MINIMAL_SRC)
        circles = re.findall(r'<circle ', html)
        assert len(circles) == 2


# ---------------------------------------------------------------------------
# Center dividers — solid not dashed
# ---------------------------------------------------------------------------

class TestSolidDividers:
    def test_no_stroke_dasharray_on_dividers(self):
        """Center dividers must not use stroke-dasharray (solid lines)."""
        html = _html(_BASIC_SRC)
        assert "stroke-dasharray" not in html, (
            "Center dividers must be solid lines (no stroke-dasharray)"
        )


# ---------------------------------------------------------------------------
# Pre-existing contract: title, quadrant labels, point labels
# ---------------------------------------------------------------------------

class TestPreExistingContract:
    def test_title_rendered(self):
        html = _html(_BASIC_SRC)
        assert "Product Prioritization" in html

    def test_no_title_ok(self):
        html = _html(_MINIMAL_SRC)
        assert html  # must not raise

    def test_quadrant_labels_rendered(self):
        html = _html(_BASIC_SRC)
        assert "Do First" in html
        assert "Plan" in html
        assert "Delegate" in html
        assert "Eliminate" in html

    def test_data_point_span_has_data_point_attr(self):
        """Point label <span> must carry data-point attribute (oracle contract)."""
        html = _html(_BASIC_SRC)
        assert 'data-point="Feature A"' in html
        assert 'data-point="Feature B"' in html
        assert 'data-point="Feature C"' in html

    def test_data_point_attr_minimal(self):
        html = _html(_MINIMAL_SRC)
        assert 'data-point="Alpha"' in html
        assert 'data-point="Beta"' in html

    def test_no_points_no_crash(self):
        src = "quadrantChart\n    x-axis Low --> High\n    y-axis Low --> High\n"
        html = _html(src)
        assert "diagram mermaid-layout" in html

    def test_fixture_full_render(self):
        """Fixture file renders without error and contains all key elements."""
        src = _FIXTURE_PATH.read_text()
        html = _html(src)
        assert "Product Prioritization" in html
        assert "Low Effort" in html
        assert "High Effort" in html
        assert "Low Impact" in html
        assert "High Impact" in html
        assert 'data-point="Feature A"' in html
        assert "<circle " in html
