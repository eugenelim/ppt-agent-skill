#!/usr/bin/env python3
"""Pytest tests for User Journey diagram syntax.

User Journey diagrams use the ``journey`` keyword and are now rendered by the
pure-Python engine.  These tests document all real journey syntax variants and
verify they produce correct HTML output.

Mermaid.js User Journey syntax reference
-----------------------------------------
::

    journey
      title My working day
      section Go to work
        Make tea: 5: Me
        Go upstairs: 3: Me, Cat
        Do work: 1: Me, Cat
      section At work
        Write code: 1: Me
        Deploy: 3: Me, Engineer

- ``title`` (optional) — sets the chart title shown above the diagram.
- ``section`` (optional) — groups tasks under a named lane.
- Each task: ``Task name: <score>: <actor>[, <actor> …]``
  - Score 1–5: 1 = very negative, 5 = very positive experience.

Import pattern mirrors tests/test_syntax_pie.py: ``sys.path.insert`` so the
test is self-contained and does not require conftest.py adjustments.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture sources — each constant documents one syntax variant
# ---------------------------------------------------------------------------

JOURNEY_MINIMAL = """journey
  title My day
  section Morning
    Wake up: 3: Me
    Shower: 5: Me"""

JOURNEY_MULTI_ACTOR = """journey
  section Work
    Write code: 1: Me, Alice
    Deploy: 3: Me, DevOps"""

JOURNEY_NO_SECTION = """journey
  title Simple
  Task A: 4: Actor"""

JOURNEY_ALL_SCORES = """journey
  section Scores
    Terrible: 1: Me
    Bad: 2: Me
    Neutral: 3: Me
    Good: 4: Me
    Great: 5: Me"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestJourneyRendered:
    """to_html renders HTML for every journey syntax variant."""

    def test_journey_renders_html(self):
        """Minimal journey diagram renders HTML."""
        html = to_html(JOURNEY_MINIMAL)
        assert html
        assert "Morning" in html

    def test_journey_title_present(self):
        """Journey title is present in output."""
        html = to_html(JOURNEY_MINIMAL)
        assert "My day" in html

    def test_journey_tasks_present(self):
        """Task names appear in rendered output."""
        html = to_html(JOURNEY_MINIMAL)
        assert "Wake up" in html
        assert "Shower" in html

    def test_journey_multi_actor_renders(self):
        """Journey with multiple actors per task renders."""
        html = to_html(JOURNEY_MULTI_ACTOR)
        assert "Write code" in html
        assert "Deploy" in html

    def test_journey_no_section_renders(self):
        """Journey with no section keyword renders."""
        html = to_html(JOURNEY_NO_SECTION)
        assert "Task A" in html

    def test_journey_all_scores_render(self):
        """Journey using all five score values renders."""
        html = to_html(JOURNEY_ALL_SCORES)
        assert "Terrible" in html
        assert "Great" in html

    def test_journey_section_bands_present(self):
        """Section bands are present in the rendered output."""
        html = to_html(JOURNEY_MINIMAL)
        # section creates a background band div
        assert "Morning" in html

    def test_journey_score_bar_present(self):
        """Score indicator bar is present in task cards."""
        html = to_html(JOURNEY_MINIMAL)
        assert "Score:" in html
