"""Regression tests for the kanban renderer fix.

Covers the five visual failure categories identified vs mmdc reference:
  1. Responsive column width — columns fill canvas evenly
  2. Quoted column labels — id["Label"] syntax unwrapped
  3. Metadata badges — ticket / priority / assigned @{...} rendered
  4. Priority colour mapping — Very High→red, High→orange, Low→blue, Very Low→grey
  5. Edge cases — empty column, quoted card labels, bare card labels
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from mermaid_render.layout._strategies import _dispatch


# ── helpers ───────────────────────────────────────────────────────────────────

def _kanban(body: str, width: int = 720) -> str:
    """Wrap body with the kanban directive and dispatch."""
    return _dispatch("kanban\n" + body, None, width)


# ── 1. column layout ──────────────────────────────────────────────────────────

class TestColumnLayout:
    """Columns must be horizontally arranged and fill the canvas width."""

    def test_three_columns_side_by_side(self):
        """Three columns must have three strictly increasing left: positions."""
        html = _kanban("  A\n    t1\n  B\n    t2\n  C\n    t3\n", width=720)
        lefts = [int(v) for v in re.findall(
            r'data-col="[^"]*" style="position:absolute;left:(\d+)px', html
        )]
        assert len(lefts) == 3, f"Expected 3 column headers, got {len(lefts)}"
        assert lefts[0] < lefts[1] < lefts[2], f"Columns not side-by-side: {lefts}"

    def test_columns_fill_canvas_width(self):
        """With 3 columns at width=720, each column must be ≥ 200 px wide."""
        html = _kanban("  A\n    t1\n  B\n  C\n", width=720)
        widths = [int(v) for v in re.findall(
            r'data-col="[^"]*" style="position:absolute;left:\d+px;top:\d+px;width:(\d+)px', html
        )]
        assert len(widths) == 3, f"Expected 3 column headers, got {len(widths)}"
        assert all(w >= 200 for w in widths), f"Columns too narrow at width=720: {widths}"

    def test_single_column_fills_canvas(self):
        """A single column should fill ~100 % of the canvas minus left/right padding."""
        html = _kanban("  Solo\n    task1\n", width=600)
        widths = [int(v) for v in re.findall(
            r'data-col="[^"]*" style="position:absolute;left:\d+px;top:\d+px;width:(\d+)px', html
        )]
        assert len(widths) == 1
        assert widths[0] >= 500, f"Single column too narrow: {widths[0]}px (canvas=600px)"

    def test_two_columns_equal_width(self):
        """Two columns must have identical widths."""
        html = _kanban("  X\n    t1\n  Y\n    t2\n", width=600)
        widths = [int(v) for v in re.findall(
            r'data-col="[^"]*" style="position:absolute;left:\d+px;top:\d+px;width:(\d+)px', html
        )]
        assert len(widths) == 2
        assert widths[0] == widths[1], f"Column widths not equal: {widths}"


# ── 2. column headers ─────────────────────────────────────────────────────────

class TestColumnHeaders:
    """Column header labels must appear correctly as data-col attributes."""

    def test_plain_col_name_in_data_col(self):
        html = _kanban("  Todo\n    t1\n")
        assert 'data-col="Todo"' in html

    def test_quoted_col_label_unwrapped(self):
        """id["Display Name"] → data-col should contain the display name."""
        html = _kanban('  col1["To Do"]\n    t1\n')
        assert 'data-col="To Do"' in html

    def test_quoted_col_label_text_visible(self):
        """Unwrapped display label must appear in the rendered HTML."""
        html = _kanban('  col1["In Progress"]\n    t1\n')
        assert "In Progress" in html

    def test_empty_col_header_renders(self):
        """An empty column (no cards) must still emit a column header div."""
        html = _kanban("  Backlog\n    t1\n  Blocked\n  Done\n    t2\n")
        assert 'data-col="Blocked"' in html

    def test_hyphenated_col_name_preserved(self):
        html = _kanban("  in-progress\n    t1\n")
        assert 'data-col="in-progress"' in html


# ── 3. card rendering ─────────────────────────────────────────────────────────

class TestCardRendering:
    """Cards must emit data-card attributes and visible label text."""

    def test_bare_card_label(self):
        html = _kanban("  Col\n    task1\n")
        assert 'data-card="task1"' in html

    def test_quoted_card_label_unwrapped(self):
        html = _kanban('  Col\n    t1["Write unit tests"]\n')
        assert 'data-card="Write unit tests"' in html

    def test_quoted_card_label_with_slash(self):
        """Labels containing / must be preserved."""
        html = _kanban('  Col\n    t1["Setup CI/CD"]\n')
        assert 'data-card="Setup CI/CD"' in html

    def test_multiple_cards_in_column(self):
        html = _kanban("  Col\n    t1\n    t2\n    t3\n")
        assert 'data-card="t1"' in html
        assert 'data-card="t2"' in html
        assert 'data-card="t3"' in html

    def test_card_label_text_visible_in_span(self):
        html = _kanban('  Col\n    t1["My Task"]\n')
        assert "My Task" in html

    def test_cards_have_node_rect_class(self):
        html = _kanban("  Col\n    task1\n")
        assert 'class="node node-rect"' in html


# ── 4. metadata badges ────────────────────────────────────────────────────────

class TestMetadataBadges:
    """Cards with @{...} metadata must render badge pills."""

    def test_ticket_badge_rendered(self):
        html = _kanban("  Col\n    t1 @{ ticket: MC-101 }\n")
        assert 'data-badge="ticket"' in html
        assert "MC-101" in html

    def test_assigned_badge_rendered(self):
        html = _kanban("  Col\n    t1 @{ assigned: 'Alice' }\n")
        assert 'data-badge="assigned"' in html
        assert "Alice" in html

    def test_priority_badge_rendered(self):
        html = _kanban("  Col\n    t1 @{ priority: 'High' }\n")
        assert 'data-badge="priority"' in html
        assert "High" in html

    def test_all_three_badges_on_same_card(self):
        html = _kanban(
            '  Col\n    t1["Task"] @{ ticket: MC-1, priority: \'High\', assigned: \'Bob\' }\n'
        )
        assert 'data-badge="ticket"' in html
        assert 'data-badge="priority"' in html
        assert 'data-badge="assigned"' in html

    def test_card_without_metadata_has_no_badges(self):
        html = _kanban('  Col\n    t1["Plain task"]\n')
        assert 'data-badge="ticket"' not in html
        assert 'data-badge="priority"' not in html
        assert 'data-badge="assigned"' not in html

    def test_ticket_value_with_hyphen(self):
        """Ticket IDs like MC-2037 must survive the metadata parser."""
        html = _kanban("  Col\n    t1 @{ ticket: MC-2037 }\n")
        assert "MC-2037" in html

    def test_metadata_stripped_from_card_label(self):
        """The @{...} block must not bleed into the card label text."""
        html = _kanban("  Col\n    t1 @{ ticket: MC-1 }\n")
        assert "@{" not in html
        # card should still have data-card="t1"
        assert 'data-card="t1"' in html


# ── 5. priority colours ───────────────────────────────────────────────────────

class TestPriorityColors:
    """Priority badge backgrounds must match the specified colour palette."""

    def _priority_badge_style(self, priority: str) -> str:
        html = _kanban(f"  Col\n    t1 @{{ priority: '{priority}' }}\n")
        m = re.search(r'data-badge="priority" style="([^"]*)"', html)
        assert m, f"No priority badge found for priority={priority!r}"
        return m.group(1)

    def test_very_high_is_red(self):
        assert "#ef4444" in self._priority_badge_style("Very High")

    def test_high_is_orange(self):
        assert "#f97316" in self._priority_badge_style("High")

    def test_low_is_blue(self):
        assert "#60a5fa" in self._priority_badge_style("Low")

    def test_very_low_is_grey(self):
        assert "#9ca3af" in self._priority_badge_style("Very Low")

    def test_unknown_priority_renders_without_error(self):
        """Unknown priority values fall back gracefully without raising."""
        html = _kanban("  Col\n    t1 @{ priority: 'Critical' }\n")
        assert 'data-badge="priority"' in html
        assert "Critical" in html


# ── 6. fixture-based regression tests ────────────────────────────────────────

class TestFixtures:
    """End-to-end tests using checked-in .mmd fixture files."""

    _FIXTURES = Path(__file__).parent / "fixtures"

    def _load(self, name: str) -> str:
        return (self._FIXTURES / name).read_text(encoding="utf-8")

    def test_basic_fixture_all_columns_present(self):
        html = _dispatch(self._load("kanban-basic.mmd"), None, 720)
        assert 'data-col="todo"' in html
        assert 'data-col="doing"' in html
        assert 'data-col="done"' in html

    def test_basic_fixture_cards_present(self):
        html = _dispatch(self._load("kanban-basic.mmd"), None, 720)
        assert 'data-card="Write tests"' in html
        assert 'data-card="Implement feature"' in html
        assert 'data-card="Deploy v1.0"' in html

    def test_quoted_labels_fixture_columns(self):
        html = _dispatch(self._load("kanban-quoted-labels.mmd"), None, 720)
        assert 'data-col="todo"' in html
        assert 'data-col="in-progress"' in html
        assert 'data-col="done"' in html

    def test_quoted_labels_fixture_cards(self):
        html = _dispatch(self._load("kanban-quoted-labels.mmd"), None, 720)
        assert 'data-card="Design mockups"' in html
        assert 'data-card="Setup CI/CD"' in html
        assert 'data-card="Deploy staging"' in html

    def test_metadata_fixture_badges_present(self):
        html = _dispatch(self._load("kanban-metadata.mmd"), None, 720)
        assert 'data-badge="ticket"' in html
        assert 'data-badge="priority"' in html
        assert 'data-badge="assigned"' in html

    def test_metadata_fixture_priority_colors(self):
        html = _dispatch(self._load("kanban-metadata.mmd"), None, 720)
        assert "#ef4444" in html, "Very High (red) priority color missing"
        assert "#f97316" in html, "High (orange) priority color missing"
        assert "#60a5fa" in html, "Low (blue) priority color missing"
        assert "#9ca3af" in html, "Very Low (grey) priority color missing"

    def test_metadata_fixture_quoted_col_labels(self):
        html = _dispatch(self._load("kanban-metadata.mmd"), None, 720)
        assert 'data-col="To Do"' in html
        assert 'data-col="In Progress"' in html
        assert 'data-col="Done"' in html

    def test_empty_col_fixture_blocked_has_header(self):
        html = _dispatch(self._load("kanban-empty-col.mmd"), None, 720)
        assert 'data-col="Blocked"' in html

    def test_empty_col_fixture_other_cols_have_cards(self):
        html = _dispatch(self._load("kanban-empty-col.mmd"), None, 720)
        assert 'data-card="Task A"' in html
        assert 'data-card="Task C"' in html
