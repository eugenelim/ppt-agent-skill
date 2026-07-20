#!/usr/bin/env python3
"""Regression tests for the timeline renderer fix.

Covers every visual failure identified vs mmdc reference output:
- Horizontal spine (SVG line element)
- Period markers (circle dots on spine)
- Period labels (data-node-id, styled chip)
- Alternating above/below placement
- Continuation events (`: TEXT` stacked under current period)
- Section grouping (coloured band rects + section label text)
- Multiple events per period
- Canvas height accommodates below-spine content
- Title rendering
- No empty period created from continuation lines
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import (
    _tl_branch_height,
    _TL_LABEL_GAP,
    _TL_LABEL_H,
    _TL_CARD_H,
    _TL_CARD_GAP,
    _TL_CARD_PAD,
    _TL_MARKER_R,
    _TL_SECTION_COLORS,
)
from mermaid_layout import _dispatch


# ── helpers ───────────────────────────────────────────────────────────────────

def _render(src: str) -> str:
    return _dispatch(src, None, 600)


def _tops(html: str) -> list[int]:
    """Return sorted list of `top:Npx` values from data-node-id divs."""
    return [
        int(m)
        for m in re.findall(r'data-node-id="[^"]*"[^>]*top:(\d+)px', html)
    ]


def _node_ids(html: str) -> list[str]:
    return re.findall(r'data-node-id="([^"]*)"', html)


# ── _tl_branch_height unit tests ─────────────────────────────────────────────

class TestTlBranchHeight:
    def test_zero_events_equals_label_gap_plus_label_h(self):
        assert _tl_branch_height(0) == _TL_LABEL_GAP + _TL_LABEL_H

    def test_one_event(self):
        expected = _TL_LABEL_GAP + _TL_LABEL_H + _TL_CARD_PAD + _TL_CARD_H
        assert _tl_branch_height(1) == expected

    def test_two_events(self):
        expected = (
            _TL_LABEL_GAP + _TL_LABEL_H
            + _TL_CARD_PAD + 2 * _TL_CARD_H + _TL_CARD_GAP
        )
        assert _tl_branch_height(2) == expected

    def test_monotone_increasing(self):
        """Branch height grows strictly with more events."""
        heights = [_tl_branch_height(n) for n in range(6)]
        assert heights == sorted(heights)
        assert len(set(heights)) == len(heights), "heights should be strictly increasing"


# ── Horizontal spine ──────────────────────────────────────────────────────────

class TestSpine:
    def test_spine_line_present(self):
        html = _render("timeline\n  2020 : A\n  2021 : B")
        assert "<line" in html, "SVG spine line must be present"

    def test_spine_stroke_width_2(self):
        html = _render("timeline\n  2020 : A\n  2021 : B")
        assert 'stroke-width="2"' in html, "spine must use stroke-width 2"


# ── Period markers ────────────────────────────────────────────────────────────

class TestPeriodMarkers:
    def test_circles_present(self):
        html = _render("timeline\n  2020 : A\n  2021 : B")
        assert "<circle" in html, "period markers must be SVG circles"

    def test_circle_count_matches_period_count(self):
        html = _render("timeline\n  Q1 : A\n  Q2 : B\n  Q3 : C")
        n_circles = len(re.findall(r"<circle", html))
        assert n_circles == 3, f"expected 3 period dots, got {n_circles}"

    def test_marker_radius_is_correct(self):
        html = _render("timeline\n  2020 : A")
        assert f'r="{_TL_MARKER_R}"' in html

    def test_markers_use_accent_fill(self):
        html = _render("timeline\n  2020 : A")
        # Dot fill uses --accent-1 / --edge-strong token
        assert "edge-strong" in html or "accent-1" in html


# ── Period labels ─────────────────────────────────────────────────────────────

class TestPeriodLabels:
    def test_data_node_id_set_for_each_period(self):
        html = _render("timeline\n  Q1 : Launch\n  Q2 : Scale")
        assert 'data-node-id="Q1"' in html
        assert 'data-node-id="Q2"' in html

    def test_period_label_has_node_class(self):
        html = _render("timeline\n  2020 : A")
        assert "node node-rect" in html

    def test_period_text_visible_in_output(self):
        html = _render("timeline\n  2020 : Event")
        assert "2020" in html


# ── Alternating above/below ───────────────────────────────────────────────────

class TestAlternating:
    """Even-indexed periods (0, 2, …) are above the spine; odd (1, 3, …) below.

    'Above' means smaller top value; 'below' means larger.
    """

    def test_two_periods_on_opposite_sides(self):
        html = _render("timeline\n  A : ev1\n  B : ev2")
        tops = _tops(html)
        assert len(tops) == 2, f"expected 2 period tops, got {tops}"
        assert tops[0] != tops[1], "periods A and B must be on opposite sides"

    def test_even_periods_above_odd_periods(self):
        """Period 0 (above) must have a smaller top than period 1 (below)."""
        html = _render("timeline\n  P0 : x\n  P1 : x\n  P2 : x\n  P3 : x")
        tops = _tops(html)
        assert len(tops) == 4
        above_top = tops[0]   # P0
        below_top = tops[1]   # P1
        assert above_top < below_top, (
            f"above-spine period top ({above_top}) must be less than "
            f"below-spine period top ({below_top})"
        )
        # P2 same side as P0
        assert tops[2] == above_top
        # P3 same side as P1
        assert tops[3] == below_top

    def test_canvas_height_accommodates_below_spine(self):
        """Canvas must be tall enough to contain below-spine event cards."""
        html = _render("timeline\n  A : ev1\n  B : ev2\n  B2 : ev3")
        # The last below-spine period (B) has events stacked downward.
        # Canvas height should be > 150 to contain at least label + event card.
        m = re.search(r'height:(\d+)px', html)
        assert m and int(m.group(1)) > 150, "canvas height too small for below content"


# ── Continuation events ───────────────────────────────────────────────────────

class TestContinuationEvents:
    def test_continuation_stacks_under_period(self):
        """': Google' should add Google as an event under the previous period."""
        src = "timeline\n  2002 : LinkedIn\n       : Google"
        html = _render(src)
        assert "LinkedIn" in html
        assert "Google" in html

    def test_continuation_does_not_create_new_period(self):
        """Continuation lines must not create extra data-node-id entries."""
        src = "timeline\n  2002 : LinkedIn\n       : Google\n  2004 : Facebook"
        html = _render(src)
        ids = _node_ids(html)
        assert "2002" in ids
        assert "2004" in ids
        # Should be exactly 2 periods, not 4 (if ':', 'Google', etc. were mistaken)
        assert len(ids) == 2, f"expected 2 period ids, got {ids}"

    def test_continuation_without_current_period_is_ignored(self):
        """A continuation before any period should not crash."""
        src = "timeline\n  : orphan\n  2020 : real"
        html = _render(src)
        assert "2020" in html

    def test_multiple_continuations(self):
        """Three continuation events all appear in output."""
        src = "timeline\n  2002 : LinkedIn\n       : Google\n       : Amazon"
        html = _render(src)
        assert "LinkedIn" in html
        assert "Google" in html
        assert "Amazon" in html

    def test_canvas_grows_for_many_continuation_events(self):
        """Canvas height must grow when a period accumulates many events."""
        src_few = "timeline\n  2002 : A"
        src_many = "timeline\n  2002 : A\n       : B\n       : C\n       : D\n       : E"
        html_few = _render(src_few)
        html_many = _render(src_many)

        def _canvas_h(html: str) -> int:
            m = re.search(r'height:(\d+)px', html)
            return int(m.group(1)) if m else 0

        assert _canvas_h(html_many) > _canvas_h(html_few), (
            "canvas must grow taller when a period has more continuation events"
        )


# ── Section grouping ──────────────────────────────────────────────────────────

class TestSections:
    def test_section_band_rect_present(self):
        src = "timeline\n  section Phase 1\n  2020 : A\n  2021 : B"
        html = _render(src)
        assert "<rect" in html, "section band must produce a <rect> element"

    def test_section_label_visible(self):
        src = "timeline\n  section Phase 1\n  2020 : A"
        html = _render(src)
        assert "Phase 1" in html

    def test_two_sections_two_bands(self):
        src = (
            "timeline\n"
            "  section Alpha\n    2020 : A\n    2021 : B\n"
            "  section Beta\n    2022 : C\n    2023 : D"
        )
        html = _render(src)
        n_rects = len(re.findall(r"<rect", html))
        # At least 2 rects (one per named section)
        assert n_rects >= 2, f"expected ≥2 section band rects, got {n_rects}"
        assert "Alpha" in html
        assert "Beta" in html

    def test_section_without_periods_produces_no_crash(self):
        """An empty section should not crash the renderer."""
        src = "timeline\n  section Empty\n  2020 : A"
        html = _render(src)
        assert "2020" in html

    def test_periods_without_section_still_render(self):
        """Periods before any section keyword must render normally."""
        src = "timeline\n  2020 : A\n  section S2\n  2021 : B"
        html = _render(src)
        assert "2020" in html
        assert "2021" in html


# ── Multiple events per period ────────────────────────────────────────────────

class TestMultipleEvents:
    def test_all_events_appear_in_html(self):
        src = "timeline\n  2020 : Alpha\n       : Beta\n       : Gamma"
        html = _render(src)
        assert "Alpha" in html
        assert "Beta" in html
        assert "Gamma" in html

    def test_event_cards_grow_canvas_height(self):
        src_one = "timeline\n  A : ev1\n  B : ev2"
        src_three = (
            "timeline\n  A : ev1\n     : ev2\n     : ev3\n  B : ev4\n     : ev5\n     : ev6"
        )

        def _h(html: str) -> int:
            m = re.search(r'height:(\d+)px', html)
            return int(m.group(1)) if m else 0

        assert _h(_render(src_three)) > _h(_render(src_one))


# ── Title ─────────────────────────────────────────────────────────────────────

class TestTitle:
    def test_title_appears_in_output(self):
        html = _render("timeline\n  title My Timeline\n  2020 : A")
        assert "My Timeline" in html

    def test_no_title_no_extra_space(self):
        """Without a title the canvas should be shorter."""
        html_with = _render("timeline\n  title T\n  2020 : A\n  2021 : B")
        html_without = _render("timeline\n  2020 : A\n  2021 : B")

        def _canvas_h(html: str) -> int:
            m = re.search(r'height:(\d+)px', html)
            return int(m.group(1)) if m else 0

        assert _canvas_h(html_with) > _canvas_h(html_without)


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_empty_timeline_raises(self):
        with pytest.raises(ValueError, match="No periods"):
            _dispatch("timeline\n  title Only Title", None, 400)

    def test_single_period_no_crash(self):
        html = _render("timeline\n  2020 : Solo Event")
        assert "2020" in html
        assert "Solo Event" in html


# ── Fixture files ─────────────────────────────────────────────────────────────

class TestFixtureFiles:
    """Smoke-test the fixture files introduced by this fix."""

    FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

    def _load(self, name: str) -> str:
        return (self.FIXTURES_DIR / name).read_text()

    def test_timeline_basic_fixture(self):
        html = _render(self._load("timeline-basic.mmd"))
        assert "Product Timeline" in html
        assert "2020" in html

    def test_timeline_multiperiod_fixture(self):
        html = _render(self._load("timeline-multiperiod.mmd"))
        assert "Product Roadmap" in html

    def test_timeline_sections_fixture(self):
        html = _render(self._load("timeline-sections.mmd"))
        assert "History of Social Media" in html
        assert "2002-2004" in html
        assert "<rect" in html

    def test_timeline_continuation_fixture(self):
        html = _render(self._load("timeline-continuation.mmd"))
        ids = _node_ids(html)
        # Should have exactly 4 period nodes: 2002, 2004, 2005, 2006
        assert len(ids) == 4, f"expected 4 period nodes, got {ids}"
        assert "Google" in html    # continuation of 2002
        assert "Gmail" in html     # continuation of 2004
        assert "MySpace" in html   # continuation of 2005
