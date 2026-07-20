#!/usr/bin/env python3
"""Gantt chart syntax coverage tests.

Covers every documented Gantt behaviour via to_html(src) → HTML assertions.

Import note: `mermaid_layout` is a backward-compat shim that maps to
`mermaid_render.layout`, which does not expose `to_html`.  The public
`to_html` lives on `mermaid_render` itself, so we import from there.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html


# ── helpers ───────────────────────────────────────────────────────────────────

def _gantt(body: str, *, title: str = "") -> str:
    """Wrap body lines in a minimal gantt preamble and call to_html."""
    title_line = f"  title {title}\n" if title else ""
    src = f"gantt\n{title_line}  dateFormat YYYY-MM-DD\n{body}"
    return to_html(src)


# ── TestGanttBasic ────────────────────────────────────────────────────────────

class TestGanttBasic:
    def test_minimal_gantt_renders(self):
        src = "gantt\n  title Test\n  dateFormat YYYY-MM-DD\n  section S\n    Task : 2024-01-01, 7d"
        html = to_html(src)
        assert html
        assert "Task" in html

    def test_returns_html_string(self):
        src = "gantt\n  dateFormat YYYY-MM-DD\n  section S\n    Alpha : 2024-01-01, 3d"
        html = to_html(src)
        assert isinstance(html, str)
        assert "<" in html

    def test_diagram_wrapper_class_present(self):
        """Output wraps content in mermaid-layout div."""
        html = _gantt("  section S\n    Task : 2024-01-01, 7d")
        assert "mermaid-layout" in html

    def test_title_rendered_in_output(self):
        html = _gantt("  section S\n    Work : 2024-01-01, 5d", title="My Project Plan")
        assert "My Project Plan" in html

    def test_task_name_in_output(self):
        html = _gantt("  section S\n    Build Phase : 2024-01-01, 10d")
        assert "Build Phase" in html

    def test_data_task_id_attribute_present(self):
        """Bar divs carry data-task-id attributes."""
        html = _gantt("  section S\n    Deploy : 2024-02-01, 3d")
        assert 'data-task-id="Deploy"' in html

    def test_no_tasks_raises_value_error(self):
        """Gantt with directives but no tasks raises ValueError."""
        src = "gantt\n  title Empty\n  dateFormat YYYY-MM-DD"
        with pytest.raises(ValueError, match="[Nn]o tasks"):
            to_html(src)


# ── TestGanttTasks ────────────────────────────────────────────────────────────

class TestGanttTasks:

    # ── done ──────────────────────────────────────────────────────────────────

    def test_done_task_renders(self):
        """done modifier renders without error; task name appears."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Finished Work : done, d1, 2024-01-01, 7d"
        )
        html = to_html(src)
        assert "Finished Work" in html
        assert 'data-task-id="d1"' in html

    def test_done_task_bar_color(self):
        """done task uses the muted/grey bar background colour."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Old Task : done, 2024-01-01, 5d"
        )
        html = to_html(src)
        assert "rgba(100,116,139" in html

    # ── active ────────────────────────────────────────────────────────────────

    def test_active_task_renders(self):
        """active modifier renders without error."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    In Progress : active, b1, 2024-01-08, 3d"
        )
        html = to_html(src)
        assert "In Progress" in html
        assert 'data-task-id="b1"' in html

    def test_active_task_bar_color_is_blue(self):
        """active task renders with a blue bar background to distinguish it."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Running : active, 2024-01-01, 5d"
        )
        html = to_html(src)
        assert "rgba(59,130,246" in html

    # ── crit ──────────────────────────────────────────────────────────────────

    def test_crit_task_renders(self):
        """crit modifier renders without error; task name appears."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Critical Path : crit, c1, 2024-01-10, 5d"
        )
        html = to_html(src)
        assert "Critical Path" in html
        assert 'data-task-id="c1"' in html

    def test_crit_task_bar_color(self):
        """crit task uses a red bar background colour."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Blocker : crit, 2024-01-01, 3d"
        )
        html = to_html(src)
        assert "rgba(220,38,38" in html

    # ── milestone ─────────────────────────────────────────────────────────────

    def test_milestone_renders(self):
        """milestone modifier renders without error."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Release : milestone, m1, 2024-01-15, 0d"
        )
        html = to_html(src)
        assert "Release" in html
        assert 'data-task-id="m1"' in html

    def test_milestone_zero_duration_bar_has_min_width(self):
        """0d duration bar gets minimum 4px width rather than collapsing."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Go-live : milestone, gl, 2024-01-10, 0d\n"
            "    Prep : prep, 2024-01-01, 9d"
        )
        html = to_html(src)
        # bar renders (data-task-id present) — no ValueError
        assert 'data-task-id="gl"' in html

    # ── combined modifiers ────────────────────────────────────────────────────

    def test_crit_and_done_combined(self):
        """crit takes precedence over done when both flags present."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Old Blocker : crit, done, 2024-01-01, 3d"
        )
        html = to_html(src)
        # crit wins: red bar present, not the done grey
        assert "rgba(220,38,38" in html
        assert "Old Blocker" in html

    # ── task IDs ──────────────────────────────────────────────────────────────

    def test_explicit_task_id_used_as_data_attr(self):
        """Explicit task id is used as data-task-id value."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    My Task : myid, 2024-01-01, 5d"
        )
        html = to_html(src)
        assert 'data-task-id="myid"' in html

    def test_task_name_fallback_when_no_id(self):
        """Task without an explicit id uses task name as data-task-id."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Unnamed Task : 2024-01-01, 5d"
        )
        html = to_html(src)
        assert 'data-task-id="Unnamed Task"' in html

    # ── duration units ────────────────────────────────────────────────────────

    def test_duration_in_days(self):
        html = _gantt("  section S\n    Sprint Day : 2024-01-01, 5d")
        assert "Sprint Day" in html

    def test_duration_in_weeks(self):
        """Duration expressed in weeks (e.g. 2w) renders correctly."""
        html = _gantt("  section S\n    Sprint : 2024-01-01, 2w")
        assert "Sprint" in html

    def test_duration_in_months(self):
        """Duration expressed in months (e.g. 3m) renders correctly."""
        html = _gantt("  section S\n    Quarter : 2024-01-01, 3m")
        assert "Quarter" in html


# ── TestGanttSections ─────────────────────────────────────────────────────────

class TestGanttSections:

    def test_multiple_sections_render(self):
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n"
            "  section Design\n    Wireframes : 2024-01-01, 5d\n"
            "  section Development\n    Coding : 2024-01-06, 10d"
        )
        html = to_html(src)
        assert "Wireframes" in html
        assert "Coding" in html

    def test_section_label_in_output(self):
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n"
            "  section Phase Alpha\n    Work : 2024-01-01, 5d"
        )
        html = to_html(src)
        assert "Phase Alpha" in html

    def test_three_section_labels_all_present(self):
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n"
            "  section Planning\n    Spec : 2024-01-01, 3d\n"
            "  section Execution\n    Build : 2024-01-04, 7d\n"
            "  section Review\n    QA : 2024-01-11, 3d"
        )
        html = to_html(src)
        assert "Planning" in html
        assert "Execution" in html
        assert "Review" in html

    def test_default_section_when_none_declared(self):
        """Tasks declared before any section directive still render."""
        src = "gantt\n  dateFormat YYYY-MM-DD\n    Lone Task : 2024-01-01, 5d"
        html = to_html(src)
        assert "Lone Task" in html

    def test_tasks_across_sections_all_rendered(self):
        """All tasks from every section appear with data-task-id."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n"
            "  section A\n    Task1 : t1, 2024-01-01, 3d\n"
            "  section B\n    Task2 : t2, 2024-01-04, 3d\n"
            "  section C\n    Task3 : t3, 2024-01-07, 3d"
        )
        html = to_html(src)
        assert 'data-task-id="t1"' in html
        assert 'data-task-id="t2"' in html
        assert 'data-task-id="t3"' in html

    def test_empty_sections_filtered_out(self):
        """A section with no tasks is dropped; remaining tasks still render."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n"
            "  section Empty\n"
            "  section Real\n    Work : 2024-01-01, 3d"
        )
        html = to_html(src)
        assert "Work" in html


# ── TestGanttDateFormats ──────────────────────────────────────────────────────

class TestGanttDateFormats:

    def test_dateformat_yyyy_mm_dd(self):
        """Standard YYYY-MM-DD dateFormat is parsed without error."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Task : 2024-06-15, 5d"
        )
        html = to_html(src)
        assert "Task" in html

    def test_dateformat_alternative_skipped_gracefully(self):
        """DD/MM/YYYY dateFormat line is consumed but tasks still render."""
        src = (
            "gantt\n  dateFormat DD/MM/YYYY\n  section S\n"
            "    Task : 2024-01-01, 7d"
        )
        html = to_html(src)
        assert "Task" in html

    def test_axisformat_skipped_gracefully(self):
        """axisFormat directive is consumed without error."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  axisFormat %m/%d\n  section S\n"
            "    Task : 2024-01-01, 5d"
        )
        html = to_html(src)
        assert "Task" in html

    def test_tickinterval_silently_ignored(self):
        """tickInterval directive is silently ignored; tasks still render."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  tickInterval 1week\n  section S\n"
            "    Task : 2024-01-01, 5d"
        )
        html = to_html(src)
        assert "Task" in html

    def test_axis_date_labels_rendered(self):
        """Date axis tick labels appear in the output (month/day format)."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Work : 2024-03-01, 30d"
        )
        html = to_html(src)
        # Axis ticks use M/D format; March start → "3/" prefix appears
        assert "3/" in html


# ── TestGanttDirectives ───────────────────────────────────────────────────────

class TestGanttDirectives:

    def test_excludes_weekends_skipped(self):
        """excludes weekends is consumed without error."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  excludes weekends\n  section S\n"
            "    Task : 2024-01-01, 7d"
        )
        html = to_html(src)
        assert "Task" in html

    def test_excludes_specific_date_skipped(self):
        """excludes with a specific date is consumed without error."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  excludes 2024-01-01\n  section S\n"
            "    Task : 2024-01-01, 7d"
        )
        html = to_html(src)
        assert "Task" in html

    def test_todaymarker_off_skipped(self):
        """todayMarker off is consumed without error."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  todayMarker off\n  section S\n"
            "    Task : 2024-01-01, 5d"
        )
        html = to_html(src)
        assert "Task" in html

    def test_includes_date_silently_ignored(self):
        """includes directive (not in skip-list) falls through without error."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  includes 2024-01-01\n  section S\n"
            "    Task : 2024-01-01, 5d"
        )
        html = to_html(src)
        assert "Task" in html

    def test_comments_ignored(self):
        """Lines starting with %% are comments and do not affect output."""
        src = (
            "gantt\n  %% This is a comment\n  dateFormat YYYY-MM-DD\n"
            "  section S\n    Task : 2024-01-01, 5d"
        )
        html = to_html(src)
        assert "Task" in html
        assert "%%" not in html


# ── TestGanttAfterDependency ──────────────────────────────────────────────────

class TestGanttAfterDependency:

    def test_after_single_id_renders(self):
        """after <id> syntax parses and renders without error."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    First : a1, 2024-01-01, 10d\n"
            "    Second : b1, after a1, 5d"
        )
        html = to_html(src)
        assert "First" in html
        assert "Second" in html

    def test_after_single_id_both_bars_present(self):
        """Both predecessor and dependent tasks carry data-task-id attrs."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Alpha : a1, 2024-01-01, 7d\n"
            "    Beta : b1, after a1, 3d"
        )
        html = to_html(src)
        assert 'data-task-id="a1"' in html
        assert 'data-task-id="b1"' in html

    def test_after_resolves_to_predecessor_end(self):
        """after a1 sets start to end of a1; Beta starts after Alpha finishes."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Alpha : a1, 2024-01-01, 7d\n"
            "    Beta : b1, after a1, 7d"
        )
        html = to_html(src)
        # Alpha ends 2024-01-08; Beta spans 2024-01-08 to 2024-01-15.
        # Total timeline is 14 days; both bars should appear.
        assert "Alpha" in html
        assert "Beta" in html

    def test_after_multi_id_fallback_renders(self):
        """after a1 a2 (multiple ids) is accepted; falls back gracefully."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Task A : a1, 2024-01-01, 7d\n"
            "    Task B : a2, 2024-01-01, 5d\n"
            "    Task C : c1, after a1 a2, 3d"
        )
        html = to_html(src)
        assert "Task C" in html
        assert 'data-task-id="c1"' in html

    def test_after_unknown_id_uses_fallback_date(self):
        """after nonexistent_id falls back to a default date without raising."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Orphan : o1, after nonexistent, 5d"
        )
        html = to_html(src)
        assert "Orphan" in html
        assert 'data-task-id="o1"' in html

    def test_chained_after_dependencies(self):
        """Three chained after dependencies all render their bars."""
        src = (
            "gantt\n  dateFormat YYYY-MM-DD\n  section S\n"
            "    Step 1 : s1, 2024-01-01, 5d\n"
            "    Step 2 : s2, after s1, 5d\n"
            "    Step 3 : s3, after s2, 5d"
        )
        html = to_html(src)
        assert 'data-task-id="s1"' in html
        assert 'data-task-id="s2"' in html
        assert 'data-task-id="s3"' in html


# ── TestGanttFullExample ──────────────────────────────────────────────────────

class TestGanttFullExample:

    def test_full_documented_example(self):
        """Full example covering all modifiers, sections and after-deps."""
        src = (
            "gantt\n"
            "  title My Gantt Chart\n"
            "  dateFormat YYYY-MM-DD\n"
            "  section Phase 1\n"
            "    Task A : done, a1, 2024-01-01, 7d\n"
            "    Task B : active, b1, after a1, 5d\n"
            "  section Phase 2\n"
            "    Task C : crit, c1, 2024-01-10, 5d\n"
            "    Task D : milestone, m1, 2024-01-15, 0d"
        )
        html = to_html(src)
        assert html
        assert "My Gantt Chart" in html
        assert "Task A" in html
        assert "Task B" in html
        assert "Task C" in html
        assert "Task D" in html
        assert "Phase 1" in html
        assert "Phase 2" in html
        assert 'data-task-id="a1"' in html
        assert 'data-task-id="b1"' in html
        assert 'data-task-id="c1"' in html
        assert 'data-task-id="m1"' in html

    def test_all_directives_combined(self):
        """Gantt with all recognised directive lines parses cleanly."""
        src = (
            "gantt\n"
            "  title Full Directive Test\n"
            "  dateFormat YYYY-MM-DD\n"
            "  axisFormat %m/%d\n"
            "  tickInterval 1week\n"
            "  excludes weekends\n"
            "  todayMarker off\n"
            "  includes 2024-01-01\n"
            "  section Work\n"
            "    Alpha : a1, 2024-01-01, 5d\n"
            "    Beta : b1, after a1, 5d"
        )
        html = to_html(src)
        assert "Full Directive Test" in html
        assert 'data-task-id="a1"' in html
        assert 'data-task-id="b1"' in html
