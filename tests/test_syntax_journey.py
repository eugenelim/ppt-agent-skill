#!/usr/bin/env python3
"""Pytest tests for User Journey diagram syntax.

User Journey diagrams use the ``journey`` keyword and are NOT supported by the
pure-Python renderer — ``to_html`` raises ``ValueError`` for this type.  These
tests:

1. Document all real journey syntax variants (as fixture constants and
   docstrings), so the contract is readable without consulting the mermaid.js
   docs.
2. Assert that each variant raises ``ValueError`` rather than silently producing
   broken output or an unrelated exception.
3. Assert the error message is meaningful — it must mention "journey" or
   "unsupported" so callers can diagnose the failure without reading source.

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
- ``section`` (optional) — groups tasks under a named lane; tasks can also
  appear at the top level without a ``section``.
- Each task: ``Task name: <score>: <actor>[, <actor> …]``
  - Score 1–5: 1 = very negative, 5 = very positive experience.
  - Multiple actors are comma-separated.
- No closing keyword; indentation is cosmetic, not structural.

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

# Minimal journey: title + one section + one task.
JOURNEY_MINIMAL = """journey
  title My day
  section Morning
    Wake up: 3: Me
    Shower: 5: Me"""

# Multiple actors on a single task, separated by commas.
JOURNEY_MULTI_ACTOR = """journey
  section Work
    Write code: 1: Me, Alice
    Deploy: 3: Me, DevOps"""

# No ``section`` block — tasks at the top level directly under ``journey``.
JOURNEY_NO_SECTION = """journey
  title Simple
  Task A: 4: Actor"""

# All five legal score values (1 = very negative … 5 = very positive).
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

class TestJourneyUnsupported:
    """to_html raises ValueError for every journey syntax variant.

    journey is in the explicit unsupported-but-recognised set in
    mermaid_render.layout._strategies._dispatch alongside gitgraph and
    requirementdiagram.  The renderer emits a descriptive error so callers
    know to route these diagrams to the mermaid-js CLI instead.
    """

    def test_journey_raises_value_error(self):
        """Minimal journey diagram raises ValueError."""
        with pytest.raises(ValueError):
            to_html(JOURNEY_MINIMAL)

    def test_journey_multi_actor_raises(self):
        """Journey with multiple actors per task raises ValueError."""
        with pytest.raises(ValueError):
            to_html(JOURNEY_MULTI_ACTOR)

    def test_journey_no_section_raises(self):
        """Journey with no section keyword raises ValueError."""
        with pytest.raises(ValueError):
            to_html(JOURNEY_NO_SECTION)

    def test_journey_all_scores_raises(self):
        """Journey using all five score values raises ValueError."""
        with pytest.raises(ValueError):
            to_html(JOURNEY_ALL_SCORES)

    def test_error_message_mentions_journey(self):
        """ValueError message names 'journey' or 'unsupported' for diagnosability."""
        with pytest.raises(ValueError, match="(?i)journey|unsupported"):
            to_html(JOURNEY_MINIMAL)
