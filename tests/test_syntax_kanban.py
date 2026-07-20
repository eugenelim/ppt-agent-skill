#!/usr/bin/env python3
"""Kanban diagram syntax coverage tests.

Covers documented kanban syntax via to_html(src) -> HTML assertions.

The kanban directive IS supported by the pure-Python renderer
(_strategies._layout_kanban, dispatched at _dispatch line ~1891).

Key behaviours probed:
  - Basic board with one or more columns renders without error
  - Column header labels appear in HTML output
  - Card labels appear in HTML output
  - @{ ... } metadata (ticket, assigned, priority) is stripped and does not
    appear in the rendered output; card/column labels are still present
  - Empty column (no cards) does not raise
  - Multiple cards per column all appear in output
  - All documented priority values: High, Very High, Low, Very Low
  - Kanban with no parseable columns raises ValueError

Import note: `to_html` lives on `mermaid_render`, not `mermaid_layout`
(the latter is a backward-compat shim that does not re-export `to_html`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ── TestKanbanBasic ───────────────────────────────────────────────────────────


class TestKanbanBasic:
    def test_minimal_board_renders(self):
        """A minimal kanban with one column and one card renders without error."""
        src = "kanban\n  todo[To Do]\n    task1[Write tests]"
        html = to_html(src)
        assert html
        assert "mermaid-layout" in html

    def test_returns_html_string(self):
        """to_html returns a non-empty HTML string containing '<'."""
        src = "kanban\n  todo[To Do]\n    task1[Write tests]"
        html = to_html(src)
        assert isinstance(html, str)
        assert "<" in html

    def test_column_label_in_output(self):
        """Column label text appears somewhere in the rendered HTML."""
        src = "kanban\n  todo[To Do]\n    task1[Write tests]"
        html = to_html(src)
        assert "To Do" in html

    def test_card_label_in_output(self):
        """Card label text appears somewhere in the rendered HTML."""
        src = "kanban\n  todo[To Do]\n    task1[Write tests]"
        html = to_html(src)
        assert "Write tests" in html

    def test_three_column_board_all_headers_present(self):
        """A three-column board renders all three column header labels."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            "    task1[Write tests]\n"
            "  doing[In Progress]\n"
            "    task3[Review PR]\n"
            "  done[Done]\n"
            "    task4[Deploy]\n"
        )
        html = to_html(src)
        assert "To Do" in html
        assert "In Progress" in html
        assert "Done" in html

    def test_three_column_board_all_cards_present(self):
        """All card labels from a three-column board appear in the output."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            "    task1[Write tests]\n"
            "  doing[In Progress]\n"
            "    task3[Review PR]\n"
            "  done[Done]\n"
            "    task4[Deploy]\n"
        )
        html = to_html(src)
        assert "Write tests" in html
        assert "Review PR" in html
        assert "Deploy" in html

    def test_no_columns_raises_value_error(self):
        """A kanban with only a comment and no columns raises ValueError."""
        src = "kanban\n  %% comment only\n"
        with pytest.raises(ValueError, match="[Nn]o columns"):
            to_html(src)


# ── TestKanbanMetadata ────────────────────────────────────────────────────────


class TestKanbanMetadata:
    def test_ticket_metadata_card_renders(self):
        """Card with @{ ticket: ... } metadata renders the card label."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            '    task1[Write tests] @{ ticket: "PROJ-1", priority: "High" }\n'
        )
        html = to_html(src)
        assert "Write tests" in html

    def test_assigned_metadata_card_renders(self):
        """Card with @{ assigned: ... } metadata renders the card label."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            '    task2[Fix bug] @{ assigned: "alice", priority: "Very High" }\n'
        )
        html = to_html(src)
        assert "Fix bug" in html

    def test_metadata_block_not_in_output(self):
        """The @{ ... } token itself is stripped and does not appear in HTML."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            '    task1[Write tests] @{ ticket: "PROJ-1" }\n'
        )
        html = to_html(src)
        assert "@{" not in html

    def test_priority_high_renders(self):
        """Card with priority: \"High\" metadata renders without error."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            '    task1[Write tests] @{ priority: "High" }\n'
        )
        html = to_html(src)
        assert "Write tests" in html

    def test_priority_very_high_renders(self):
        """Card with priority: \"Very High\" metadata renders without error."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            '    task2[Fix bug] @{ priority: "Very High" }\n'
        )
        html = to_html(src)
        assert "Fix bug" in html

    def test_priority_low_renders(self):
        """Card with priority: \"Low\" metadata renders without error."""
        src = (
            "kanban\n"
            "  doing[In Progress]\n"
            '    task3[Review PR] @{ priority: "Low" }\n'
        )
        html = to_html(src)
        assert "Review PR" in html

    def test_priority_very_low_renders(self):
        """Card with priority: \"Very Low\" metadata renders without error."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            '    task1[Low priority work] @{ priority: "Very Low" }\n'
        )
        html = to_html(src)
        assert "Low priority work" in html

    def test_all_metadata_fields_combined(self):
        """Card with ticket + assigned + priority all combined renders correctly."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            '    task1[Write tests] @{ ticket: "PROJ-1", assigned: "alice", priority: "High" }\n'
        )
        html = to_html(src)
        assert "Write tests" in html
        assert "@{" not in html

    def test_task_without_metadata_renders(self):
        """A task without any @{ } metadata also renders correctly."""
        src = (
            "kanban\n"
            "  done[Done]\n"
            "    task4[Deploy]\n"
        )
        html = to_html(src)
        assert "Deploy" in html


# ── TestKanbanEmptyColumn ─────────────────────────────────────────────────────


class TestKanbanEmptyColumn:
    def test_empty_column_renders_without_error(self):
        """A column with no cards does not raise; its label appears in output."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            "  done[Done]\n"
            "    task4[Deploy]\n"
        )
        html = to_html(src)
        assert "To Do" in html
        assert "Done" in html

    def test_empty_column_label_present_among_populated_columns(self):
        """Empty column label is present alongside a populated column's cards."""
        src = (
            "kanban\n"
            "  backlog[Backlog]\n"
            "  active[Active]\n"
            "    task1[Current work]\n"
        )
        html = to_html(src)
        assert "Backlog" in html
        assert "Current work" in html


# ── TestKanbanMultipleTasksPerColumn ──────────────────────────────────────────


class TestKanbanMultipleTasksPerColumn:
    def test_three_cards_in_column_all_rendered(self):
        """All three cards within a single column appear in the HTML."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            "    task1[Write tests]\n"
            "    task2[Fix bug]\n"
            "    task3[Add docs]\n"
        )
        html = to_html(src)
        assert "Write tests" in html
        assert "Fix bug" in html
        assert "Add docs" in html

    def test_four_cards_in_column_all_rendered(self):
        """Four cards in a single column all produce card divs in the output."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            "    task1[Alpha]\n"
            "    task2[Beta]\n"
            "    task3[Gamma]\n"
            "    task4[Delta]\n"
        )
        html = to_html(src)
        for label in ("Alpha", "Beta", "Gamma", "Delta"):
            assert label in html, f"card label {label!r} missing from output"

    def test_mixed_metadata_and_plain_tasks_all_rendered(self):
        """Tasks with and without metadata in the same column all appear."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            '    task1[Write tests] @{ ticket: "PROJ-1" }\n'
            "    task2[Fix bug]\n"
            '    task3[Add docs] @{ assigned: "bob" }\n'
        )
        html = to_html(src)
        assert "Write tests" in html
        assert "Fix bug" in html
        assert "Add docs" in html


# ── TestKanbanFullExample ─────────────────────────────────────────────────────


class TestKanbanFullExample:
    def test_full_documented_example_renders(self):
        """Full example from the spec with all metadata fields renders correctly."""
        src = (
            "kanban\n"
            "  todo[To Do]\n"
            '    task1[Write tests] @{ ticket: "PROJ-1", priority: "High" }\n'
            '    task2[Fix bug]     @{ assigned: "alice", priority: "Very High" }\n'
            "  doing[In Progress]\n"
            '    task3[Review PR]   @{ ticket: "PROJ-2", assigned: "bob", priority: "Low" }\n'
            "  done[Done]\n"
            '    task4[Deploy]      @{ ticket: "PROJ-3" }\n'
        )
        html = to_html(src)
        assert html
        assert "mermaid-layout" in html
        # All card labels present
        assert "Write tests" in html
        assert "Fix bug" in html
        assert "Review PR" in html
        assert "Deploy" in html
        # Column headers present
        assert "To Do" in html
        assert "In Progress" in html
        assert "Done" in html
        # No raw metadata leakage
        assert "@{" not in html
