"""Tests for stateDiagram-v2 syntax behaviors.

Covers features NOT already exercised in test_mermaid_layout.py.
Already-covered behaviors (skipped here to avoid duplication):
  - basic smoke dispatch (TestDirectiveStrategies.test_state_diagram, line 642)
  - [*] → start / end node structure (test_statediff_start_node_parsed / _end_, lines 964-978)
  - ': label' edge label parsed (test_statediff_colon_label_parsed, line 950)
  - state description 'id : label' (test_state_description, line 5061)
  - state alias 'state "..." as id' (test_state_alias, line 5066)
  - composite state rendered as group (TestStateDiagramCompositeState, lines 5984-6024)
  - 'direction LR' inside body (test_statediagram_with_direction_override, line 5091)

Import note: `mermaid_layout` is a shim that re-exports mermaid_render.layout;
to_html lives on the top-level mermaid_render package and is not re-exported by
the shim, so we import directly from mermaid_render.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _node_labels(html: str) -> list[str]:
    """Extract node-label text nodes from rendered HTML."""
    return re.findall(r'class="node-label"[^>]*>([^<]+)', html)


def _edge_labels(html: str) -> list[str]:
    """Extract edge-label text nodes from rendered HTML."""
    return re.findall(r'class="edge-label"[^>]*>([^<]+)', html)


# ── TestStateBasic ────────────────────────────────────────────────────────────

class TestStateBasic:
    """HTML-level assertions for basic stateDiagram-v2 syntax.

    Parser-level coverage of transitions and start/end nodes already exists
    in test_mermaid_layout.py; these tests verify the rendered HTML output.
    """

    def test_transition_with_label_appears_in_html(self):
        """A labelled transition 's1 --> s2 : go' must render the label text."""
        html = to_html("stateDiagram-v2\n  s1 --> s2 : go")
        assert "diagram mermaid-layout" in html
        assert "go" in _edge_labels(html), (
            f"Transition label 'go' not found in edge-labels. Got: {_edge_labels(html)}"
        )

    def test_start_state_circle_symbol(self):
        """[*] as source renders the filled-circle ● start marker."""
        html = to_html("stateDiagram-v2\n  [*] --> Idle")
        assert "●" in html, "Start state ● marker missing from HTML"

    def test_end_state_circle_symbol(self):
        """[*] as target renders the double-circle ◎ end marker."""
        html = to_html("stateDiagram-v2\n  Done --> [*]")
        assert "◎" in html, "End state ◎ marker missing from HTML"

    def test_statediagram_v1_directive(self):
        """stateDiagram (without -v2) is treated identically to stateDiagram-v2."""
        html = to_html("stateDiagram\n  [*] --> Idle\n  Idle --> [*]")
        assert "diagram mermaid-layout" in html
        assert "●" in html
        assert "◎" in html
        assert "Idle" in _node_labels(html)


# ── TestStateComposite ────────────────────────────────────────────────────────

class TestStateComposite:
    """Nested composite states (state X { state Y { } })."""

    def test_nested_composite_renders(self):
        """Two levels of composite state render without crash."""
        src = (
            "stateDiagram-v2\n"
            "  state outer {\n"
            "    state inner {\n"
            "      a --> b\n"
            "    }\n"
            "  }\n"
        )
        html = to_html(src)
        assert "diagram mermaid-layout" in html

    def test_nested_composite_outer_label(self):
        """Outer composite state label appears in rendered output."""
        src = (
            "stateDiagram-v2\n"
            "  state outer {\n"
            "    state inner {\n"
            "      a --> b\n"
            "    }\n"
            "  }\n"
        )
        html = to_html(src)
        assert "outer" in _node_labels(html), (
            f"'outer' missing from node labels. Got: {_node_labels(html)}"
        )

    def test_nested_composite_inner_label(self):
        """Inner composite state label appears in rendered output."""
        src = (
            "stateDiagram-v2\n"
            "  state outer {\n"
            "    state inner {\n"
            "      a --> b\n"
            "    }\n"
            "  }\n"
        )
        html = to_html(src)
        assert "inner" in _node_labels(html), (
            f"'inner' missing from node labels. Got: {_node_labels(html)}"
        )

    def test_nested_composite_has_two_groups(self):
        """Two levels of nesting produce two diagram-group containers."""
        src = (
            "stateDiagram-v2\n"
            "  state outer {\n"
            "    state inner {\n"
            "      a --> b\n"
            "    }\n"
            "  }\n"
        )
        html = to_html(src)
        groups = re.findall(r'class="diagram-group"', html)
        assert len(groups) >= 2, (
            f"Expected ≥2 diagram-group containers for 2-level nesting; got {len(groups)}"
        )

    def test_nested_composite_child_states(self):
        """Leaf states inside nested composites appear in rendered output."""
        src = (
            "stateDiagram-v2\n"
            "  state outer {\n"
            "    state inner {\n"
            "      a --> b\n"
            "    }\n"
            "  }\n"
        )
        html = to_html(src)
        labels = _node_labels(html)
        assert "a" in labels, f"Child state 'a' missing. Got: {labels}"
        assert "b" in labels, f"Child state 'b' missing. Got: {labels}"


# ── TestStateForkJoin ─────────────────────────────────────────────────────────

class TestStateForkJoin:
    """Fork and join pseudo-states (<<fork>> / <<join>>).

    The parser does not special-case the <<fork>>/<<join>> markers; it treats
    'state X <<fork>>' as a standalone node declaration and the fork/join
    nodes are registered through the subsequent edge lines.  Tests verify
    the fork/join node labels appear in the rendered output.
    """

    _SRC = (
        "stateDiagram-v2\n"
        "  state fork_state <<fork>>\n"
        "  state join_state <<join>>\n"
        "  [*] --> fork_state\n"
        "  fork_state --> s1\n"
        "  fork_state --> s2\n"
        "  s1 --> join_state\n"
        "  s2 --> join_state\n"
        "  join_state --> [*]\n"
    )

    def test_fork_renders_without_crash(self):
        """Fork/join diagram renders a valid HTML fragment."""
        html = to_html(self._SRC)
        assert "diagram mermaid-layout" in html

    def test_fork_state_label_present(self):
        """fork_state node label appears in rendered output."""
        html = to_html(self._SRC)
        assert "fork_state" in _node_labels(html), (
            f"'fork_state' missing. Got: {_node_labels(html)}"
        )

    def test_join_state_label_present(self):
        """join_state node label appears in rendered output."""
        html = to_html(self._SRC)
        assert "join_state" in _node_labels(html), (
            f"'join_state' missing. Got: {_node_labels(html)}"
        )

    def test_fork_branches_present(self):
        """Both parallel branches (s1, s2) appear in rendered output."""
        html = to_html(self._SRC)
        labels = _node_labels(html)
        assert "s1" in labels, f"'s1' missing. Got: {labels}"
        assert "s2" in labels, f"'s2' missing. Got: {labels}"


# ── TestStateChoice ───────────────────────────────────────────────────────────

class TestStateChoice:
    """Choice pseudo-state (<<choice>>).

    Like fork/join, <<choice>> is not parsed as a special shape; the choice
    node is registered via the edge lines that follow.
    """

    _SRC = (
        "stateDiagram-v2\n"
        "  state choice_state <<choice>>\n"
        "  [*] --> choice_state\n"
        "  choice_state --> s1 : if x\n"
        "  choice_state --> s2 : if not x\n"
    )

    def test_choice_renders_without_crash(self):
        """Choice diagram renders a valid HTML fragment."""
        html = to_html(self._SRC)
        assert "diagram mermaid-layout" in html

    def test_choice_state_label_present(self):
        """choice_state node label appears in rendered output."""
        html = to_html(self._SRC)
        assert "choice_state" in _node_labels(html), (
            f"'choice_state' missing. Got: {_node_labels(html)}"
        )

    def test_choice_branch_labels_present(self):
        """Both branch targets (s1, s2) appear in rendered output."""
        html = to_html(self._SRC)
        labels = _node_labels(html)
        assert "s1" in labels, f"'s1' missing. Got: {labels}"
        assert "s2" in labels, f"'s2' missing. Got: {labels}"


# ── TestStateConcurrency ──────────────────────────────────────────────────────

class TestStateConcurrency:
    """Concurrent regions separated by -- inside a composite state.

    The -- separator is silently ignored by the parser (not a valid edge
    operator with no src token); both concurrent sub-states are registered
    as members of the composite state's group.
    """

    _SRC = (
        "stateDiagram-v2\n"
        "  state Active {\n"
        "    [*] --> Running\n"
        "    --\n"
        "    [*] --> Listening\n"
        "  }\n"
    )

    def test_concurrency_renders_without_crash(self):
        """Concurrency diagram renders a valid HTML fragment."""
        html = to_html(self._SRC)
        assert "diagram mermaid-layout" in html

    def test_concurrency_composite_label_present(self):
        """The composite state wrapping the concurrent regions is present."""
        html = to_html(self._SRC)
        assert "Active" in _node_labels(html), (
            f"'Active' composite label missing. Got: {_node_labels(html)}"
        )

    def test_concurrency_first_region_state_present(self):
        """First concurrent region state (Running) appears in output."""
        html = to_html(self._SRC)
        assert "Running" in _node_labels(html), (
            f"'Running' missing. Got: {_node_labels(html)}"
        )

    def test_concurrency_second_region_state_present(self):
        """Second concurrent region state (Listening) appears in output."""
        html = to_html(self._SRC)
        assert "Listening" in _node_labels(html), (
            f"'Listening' missing. Got: {_node_labels(html)}"
        )

    def test_concurrency_has_group(self):
        """Concurrent region wrapper produces a diagram-group container."""
        html = to_html(self._SRC)
        groups = re.findall(r'class="diagram-group"', html)
        assert groups, "No diagram-group found for composite concurrency state"


# ── TestStateNotes ────────────────────────────────────────────────────────────

class TestStateNotes:
    """Notes (note right of / note left of … end note).

    Notes are not currently parsed as visual annotations; the keywords
    fall through to the general parser.  Tests verify the diagram states
    themselves still render and that no exception is raised.
    """

    def test_inline_note_no_crash(self):
        """Single-line 'note right of s1: text' does not crash the renderer."""
        src = (
            "stateDiagram-v2\n"
            "  s1 --> s2\n"
            "  note right of s1: This is a note\n"
        )
        html = to_html(src)
        assert "diagram mermaid-layout" in html

    def test_inline_note_states_still_render(self):
        """Diagram states still appear in output when inline note is present."""
        src = (
            "stateDiagram-v2\n"
            "  s1 --> s2\n"
            "  note right of s1: This is a note\n"
        )
        html = to_html(src)
        labels = _node_labels(html)
        assert "s1" in labels, f"'s1' missing. Got: {labels}"
        assert "s2" in labels, f"'s2' missing. Got: {labels}"

    def test_multiline_note_no_crash(self):
        """Multi-line 'note left of … end note' block does not crash the renderer."""
        src = (
            "stateDiagram-v2\n"
            "  s1 --> s2\n"
            "  note left of s2\n"
            "    Multiline\n"
            "    note text\n"
            "  end note\n"
        )
        html = to_html(src)
        assert "diagram mermaid-layout" in html

    def test_multiline_note_states_still_render(self):
        """Diagram states still appear in output when multiline note is present."""
        src = (
            "stateDiagram-v2\n"
            "  s1 --> s2\n"
            "  note left of s2\n"
            "    Multiline\n"
            "    note text\n"
            "  end note\n"
        )
        html = to_html(src)
        labels = _node_labels(html)
        assert "s1" in labels, f"'s1' missing. Got: {labels}"
        assert "s2" in labels, f"'s2' missing. Got: {labels}"
