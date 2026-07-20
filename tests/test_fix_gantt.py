"""Regression tests for gantt renderer fixes.

Covers:
- active/milestone flag storage and visual distinction
- crit bar colour (red), done bar colour (grey), active bar colour (blue)
- milestone rendered as diamond (data-milestone + rotate(45deg))
- multi-id ``after a1 a2`` resolved to max(end(a1), end(a2))
- full-height vertical grid lines rendered as SVG
- single-id ``after`` dependency still works
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _layout_gantt

# ── helpers ───────────────────────────────────────────────────────────────────

def _gantt(src: str, width: int = 720) -> str:
    return _layout_gantt(src, "LR", width)


def _bar_bg(html: str, task_id: str) -> str:
    """Return the background style value for data-task-id=<task_id>."""
    m = re.search(
        r'data-task-id="' + re.escape(task_id) + r'"[^>]*background:([^;]+)',
        html,
    )
    assert m, f"task {task_id!r} not found in HTML"
    return m.group(1).strip()


def _bar_x(html: str, task_id: str) -> int:
    """Return left-px for the bar of data-task-id=<task_id>."""
    m = re.search(
        r'data-task-id="' + re.escape(task_id) + r'"[^>]*left:(\d+)px',
        html,
    )
    assert m, f"task {task_id!r} not found or has no left in HTML"
    return int(m.group(1))


# ── fixture source snippets ───────────────────────────────────────────────────

MODIFIERS_SRC = """\
gantt
    title Task Modifiers
    dateFormat YYYY-MM-DD
    section Delivery
        Setup    :done,      t1, 2024-01-01, 3d
        Develop  :active,    t2, 2024-01-04, 5d
        Review   :crit,      t3, 2024-01-09, 3d
        Launch   :milestone, t4, 2024-01-12, 1d
"""

AFTER_MULTI_SRC = """\
gantt
    dateFormat YYYY-MM-DD
    section Track A
        Alpha  :a1, 2024-01-01, 4d
        Beta   :a2, 2024-01-01, 6d
    section Track B
        Merge  :after a1 a2, 3d
"""

AFTER_SINGLE_SRC = """\
gantt
    dateFormat YYYY-MM-DD
    section Work
        Task A  :a1, 2024-01-01, 5d
        Task B  :after a1, 3d
"""


# ── tests: bar colours ────────────────────────────────────────────────────────

class TestBarColours:
    def test_done_is_grey(self):
        html = _gantt(MODIFIERS_SRC)
        bg = _bar_bg(html, "t1")
        # grey uses CSS var OR rgba with low saturation
        assert "100,116,139" in bg or "rgba(100" in bg, f"done bar not grey: {bg}"

    def test_active_is_blue(self):
        html = _gantt(MODIFIERS_SRC)
        bg = _bar_bg(html, "t2")
        assert "59,130,246" in bg, f"active bar not blue: {bg}"

    def test_crit_is_red(self):
        html = _gantt(MODIFIERS_SRC)
        bg = _bar_bg(html, "t3")
        assert "220,38,38" in bg, f"crit bar not red: {bg}"

    def test_default_is_green(self):
        html = _gantt("""\
gantt
    dateFormat YYYY-MM-DD
    section Work
        Normal :n1, 2024-01-01, 5d
""")
        bg = _bar_bg(html, "n1")
        assert "53,148,103" in bg, f"default bar not green: {bg}"


# ── tests: milestone diamond ──────────────────────────────────────────────────

class TestMilestoneDiamond:
    def test_milestone_has_data_attribute(self):
        html = _gantt(MODIFIERS_SRC)
        assert 'data-milestone="1"' in html

    def test_milestone_has_rotate_transform(self):
        html = _gantt(MODIFIERS_SRC)
        m = re.search(r'data-milestone="1"[^>]*transform:rotate\(45deg\)', html)
        assert m, "milestone diamond rotation not found"

    def test_non_milestone_has_no_milestone_attr(self):
        html = _gantt(MODIFIERS_SRC)
        # t1/t2/t3 are not milestones
        for tid in ("t1", "t2", "t3"):
            assert f'data-task-id="{tid}" data-milestone' not in html, \
                f"task {tid} incorrectly has data-milestone"

    def test_milestone_is_square_not_wide_bar(self):
        """Milestone div has equal width and height (square before rotation)."""
        html = _gantt(MODIFIERS_SRC)
        m = re.search(
            r'data-milestone="1"[^>]*width:(\d+)px[^>]*height:(\d+)px',
            html,
        )
        assert m, "milestone width/height not found"
        assert m.group(1) == m.group(2), "milestone is not square"


# ── tests: multi-id after ─────────────────────────────────────────────────────

class TestAfterDependency:
    def test_single_after_respected(self):
        """Task B starts at end of Task A (Jan1+5d = Jan6)."""
        html = _gantt(AFTER_SINGLE_SRC)
        # a1 ends Jan6; total span = Jan1..Jan9 = 8d
        # Task B bar_x = bar_x + int(5/8 * bar_w)
        # bar_x=184, bar_w=496: 184 + int(5/8*496) = 184+310 = 494
        x_b = _bar_x(html, "Task B")
        x_a = _bar_x(html, "a1")
        assert x_b > x_a, "Task B must start after Task A"

    def test_multi_after_resolves_to_max(self):
        """Merge starts at max(a1_end=Jan5, a2_end=Jan7) = Jan7.

        a1: Jan1 + 4d = Jan5
        a2: Jan1 + 6d = Jan7
        Merge: starts Jan7, duration 3d → ends Jan10
        total_days = (Jan10 - Jan1).days = 9
        bar_x for Merge = 184 + int(6/9 * 496) = 184+330 = 514
        """
        html = _gantt(AFTER_MULTI_SRC)
        x_merge = _bar_x(html, "Merge")
        x_alpha = _bar_x(html, "a1")
        x_beta  = _bar_x(html, "a2")
        # Both a1 and a2 start at same date so same x
        assert x_alpha == x_beta == 184, f"alpha/beta should both start at bar_x=184"
        # Merge must start after both
        assert x_merge > 184, "Merge should not start at Jan1 (multi-id resolution failed)"
        # Exact pixel check: should be at Jan7 = offset 6/9 of 496px = 330, so 184+330=514
        assert x_merge == 514, f"Expected Merge at x=514 (Jan7), got {x_merge}"

    def test_multi_after_is_strictly_later_than_single(self):
        """Merge (after a1 a2) starts at Jan7, not Jan5 (which is a1 alone)."""
        html = _gantt(AFTER_MULTI_SRC)
        x_merge = _bar_x(html, "Merge")
        # If only a1 was respected, x would be 184 + int(4/9*496) = 184+220 = 404
        assert x_merge > 404, "Merge should use max of both deps, not just a1"


# ── tests: grid lines ─────────────────────────────────────────────────────────

class TestGridLines:
    def test_grid_svg_present(self):
        html = _gantt(MODIFIERS_SRC)
        assert "<svg" in html, "Grid SVG element missing"

    def test_grid_lines_span_full_height(self):
        html = _gantt(MODIFIERS_SRC)
        # SVG has explicit height attribute
        m = re.search(r'<svg[^>]*height:(\d+)px', html)
        assert m, "SVG height not found"
        grid_h = int(m.group(1))
        assert grid_h > 0, "Grid height must be positive"
        # Lines use the same height
        line_ys = re.findall(r'y2="(\d+)"', html)
        assert any(int(y) == grid_h for y in line_ys), \
            f"No grid line reaches full height {grid_h}; found y2 values: {line_ys}"

    def test_grid_lines_use_dasharray(self):
        html = _gantt(MODIFIERS_SRC)
        assert "stroke-dasharray" in html, "Grid lines missing stroke-dasharray"


# ── tests: fixture-based smoke ────────────────────────────────────────────────

class TestFixtures:
    def test_basic_fixture_renders(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "gantt-basic.mmd").read_text()
        html = _gantt(src)
        assert "mermaid-layout" in html
        assert "data-task-id" in html

    def test_modifiers_fixture_renders(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "gantt-modifiers.mmd").read_text()
        html = _gantt(src)
        assert 'data-milestone="1"' in html
        assert "rgba(220,38,38" in html   # crit red
        assert "rgba(59,130,246" in html  # active blue

    def test_after_multi_fixture_renders(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "gantt-after-multi.mmd").read_text()
        html = _gantt(src)
        x_merge = _bar_x(html, "Merge")
        assert x_merge > 184, "Merge should not be at Jan1"
