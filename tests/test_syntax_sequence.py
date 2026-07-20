#!/usr/bin/env python3
"""Syntax-coverage tests for sequenceDiagram.

Each class maps to one documented syntax area.  Tests assert that
``to_html`` returns non-empty HTML and that key content tokens are
present; they do NOT duplicate unit-level assertions already in
``test_mermaid_layout.py`` (parser internals, block-span geometry,
activation-shorthand phantom-participant regression, etc.).

Import pattern follows the repo convention: add ``scripts/`` to
``sys.path`` so tests run without a package install.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # pure-Python, no Playwright


# ── helpers ───────────────────────────────────────────────────────────────────

def _seq(body: str) -> str:
    """Wrap ``body`` in a minimal sequenceDiagram preamble."""
    return f"sequenceDiagram\n{body}"


# ─────────────────────────────────────────────────────────────────────────────
# Participants
# ─────────────────────────────────────────────────────────────────────────────

class TestSequenceParticipants:
    """Participant declarations and lifecycle keywords."""

    def test_explicit_participant(self):
        """`participant X` declares a named lifeline."""
        html = to_html(_seq("  participant Alice\n  Alice->>Bob: hi"))
        assert "Alice" in html

    def test_actor_keyword(self):
        """`actor X` is a valid participant variant."""
        html = to_html(_seq("  actor User\n  User->>API: request"))
        assert "User" in html

    def test_participant_alias(self):
        """`participant A as Long Name` renders the display label."""
        html = to_html(_seq('  participant A as "Long Name"\n  A->>B: hello'))
        assert "Long Name" in html

    def test_implicit_participant_from_message(self):
        """Participants referenced only in messages are auto-created."""
        html = to_html(_seq("  Client->>Server: connect"))
        assert "Client" in html
        assert "Server" in html

    def test_create_participant_renders(self):
        """`create participant C` followed by a message to C renders C.

        The pure-Python renderer does not draw a creation marker;
        C is added to the participant list via implicit discovery when
        the message ``A->>C`` is parsed.
        """
        html = to_html(_seq(
            "  participant A\n"
            "  create participant C\n"
            "  A->>C: hello\n"
        ))
        assert html
        assert "C" in html

    def test_destroy_participant_renders(self):
        """`destroy P` is accepted without raising."""
        html = to_html(_seq(
            "  participant A\n"
            "  participant B\n"
            "  A->>B: ping\n"
            "  destroy B\n"
        ))
        assert html
        assert "A" in html

    def test_create_then_destroy_roundtrip(self):
        """Full create/use/destroy lifecycle renders without error."""
        html = to_html(_seq(
            "  participant Alice\n"
            "  create participant Token\n"
            "  Alice->>Token: init\n"
            "  Token-->>Alice: ready\n"
            "  destroy Token\n"
        ))
        assert html
        assert "Alice" in html


# ─────────────────────────────────────────────────────────────────────────────
# Message types
# ─────────────────────────────────────────────────────────────────────────────

class TestSequenceMessages:
    """All documented message arrow styles render without error.

    ``->>`` and ``-->>`` are already exercised by many tests in
    ``test_mermaid_layout.py``; they appear here so this file is a
    complete, self-contained syntax reference.
    """

    @pytest.mark.parametrize("arrow,desc", [
        ("->>",  "sync solid arrow"),
        ("-->>", "sync dotted arrow"),
        ("->",   "open non-filled arrow"),
        ("-->",  "open dashed arrow"),
        ("-x",   "sync x terminus (lost message)"),
        ("--x",  "dashed x terminus (lost message)"),
        ("-)",   "async open (half-arrow)"),
        ("--)",  "async dotted open"),
    ])
    def test_message_type_renders(self, arrow: str, desc: str):
        src = _seq(f"  Alice{arrow}Bob: msg")
        html = to_html(src)
        assert html, f"{desc}: to_html returned empty string"
        assert "Alice" in html, f"{desc}: sender 'Alice' not in output"
        assert "Bob" in html, f"{desc}: receiver 'Bob' not in output"

    def test_message_label_in_output(self):
        """Message label text appears in the rendered HTML."""
        html = to_html(_seq("  Alice->>Bob: Hello World"))
        assert "Hello World" in html

    def test_self_message_renders(self):
        """A message from a participant to itself (self-call) renders."""
        html = to_html(_seq("  Alice->>Alice: think"))
        assert html
        assert "Alice" in html

    def test_async_arrow_label(self):
        """``-)`` arrow carries its label through to the HTML."""
        html = to_html(_seq("  Client-)Server: fire and forget"))
        assert "fire and forget" in html

    def test_async_dotted_arrow_label(self):
        """``--)`` arrow carries its label through to the HTML."""
        html = to_html(_seq("  Client--)Server: async reply"))
        assert "async reply" in html

    def test_x_arrow_single_dash_label(self):
        """``-x`` arrow carries its label through to the HTML."""
        html = to_html(_seq("  Alice-xBob: dropped"))
        assert "dropped" in html


# ─────────────────────────────────────────────────────────────────────────────
# Activation
# ─────────────────────────────────────────────────────────────────────────────

class TestSequenceActivation:
    """Explicit and shorthand activation syntax."""

    def test_explicit_activate_deactivate(self):
        """`activate` / `deactivate` blocks render the activation bar."""
        html = to_html(_seq(
            "  A->>B: req\n"
            "  activate B\n"
            "  B->>A: res\n"
            "  deactivate B\n"
        ))
        assert html
        assert "A" in html and "B" in html

    def test_shorthand_plus_activation(self):
        """`->>+B` activates B; `-->>-A` deactivates A."""
        html = to_html(_seq("  A->>+B: activate\n  B-->>-A: done"))
        assert html
        # Phantom participants +B / -A must not appear
        assert "+B" not in html
        assert "-A" not in html


# ─────────────────────────────────────────────────────────────────────────────
# Notes
# ─────────────────────────────────────────────────────────────────────────────

class TestSequenceNotes:
    """Note placement variants render the note text."""

    def test_note_right_of(self):
        html = to_html(_seq("  A->>B: msg\n  Note right of B: right text"))
        assert "right text" in html

    def test_note_left_of(self):
        html = to_html(_seq("  A->>B: msg\n  Note left of A: left text"))
        assert "left text" in html

    def test_note_over_single(self):
        html = to_html(_seq("  A->>B: msg\n  Note over A: over text"))
        assert "over text" in html

    def test_note_over_span(self):
        """``Note over A,B`` spanning multiple participants renders."""
        html = to_html(_seq(
            "  participant A\n  participant B\n"
            "  A->>B: msg\n"
            "  Note over A,B: spanning note"
        ))
        assert "spanning note" in html


# ─────────────────────────────────────────────────────────────────────────────
# Block constructs
# ─────────────────────────────────────────────────────────────────────────────

class TestSequenceBlocks:
    """Every documented block keyword renders without error.

    ``loop``, ``alt/else``, ``opt``, ``par/and`` have detailed assertions
    in ``test_mermaid_layout.py``; they appear here for completeness and
    for the keyword-in-output check.  ``critical``, ``break``, and
    ``rect`` are tested here for the first time.
    """

    def test_loop_renders(self):
        html = to_html(_seq(
            "  loop Every minute\n    Alice->>Bob: ping\n  end"
        ))
        assert "loop" in html.lower()

    def test_alt_else_renders(self):
        html = to_html(_seq(
            "  alt success\n    Alice->>Bob: ok\n"
            "  else failure\n    Alice->>Bob: error\n  end"
        ))
        assert "alt" in html.lower()

    def test_opt_renders(self):
        html = to_html(_seq(
            "  opt optional\n    Alice->>Bob: maybe\n  end"
        ))
        assert "opt" in html.lower()

    def test_par_and_renders(self):
        html = to_html(_seq(
            "  par parallel\n    Alice->>Bob: a\n"
            "  and\n    Alice->>Charlie: b\n  end"
        ))
        assert "par" in html.lower()

    def test_critical_block_renders(self):
        """`critical … option … end` renders without error."""
        html = to_html(_seq(
            "  critical attempt\n"
            "    A->>B: try\n"
            "  option catch\n"
            "    A->>B: handle error\n"
            "  end\n"
        ))
        assert html
        assert "critical" in html.lower()

    def test_critical_keyword_in_output(self):
        """The ``critical`` label is present in the rendered block annotation."""
        html = to_html(_seq(
            "  A->>B: start\n"
            "  critical section\n"
            "    A->>B: atomic\n"
            "  end\n"
        ))
        assert "critical" in html.lower()

    def test_break_block_renders(self):
        """`break … end` renders without error."""
        html = to_html(_seq(
            "  A->>B: request\n"
            "  break on error\n"
            "    A->>B: abort\n"
            "  end\n"
        ))
        assert html
        assert "break" in html.lower()

    def test_break_keyword_in_output(self):
        """The ``break`` label is present in the rendered block annotation."""
        html = to_html(_seq(
            "  A->>B: msg\n"
            "  break abort path\n"
            "    A->>B: stop\n"
            "  end\n"
        ))
        assert "break" in html.lower()

    def test_rect_background_renders(self):
        """`rect rgb(…) … end` renders without error."""
        html = to_html(_seq(
            "  A->>B: before\n"
            "  rect rgb(0, 255, 0)\n"
            "    A->>B: colored\n"
            "  end\n"
            "  A->>B: after\n"
        ))
        assert html
        assert "A" in html and "B" in html

    def test_rect_label_in_output(self):
        """The ``rect`` keyword appears in the rendered output."""
        html = to_html(_seq(
            "  A->>B: msg\n"
            "  rect rgb(200, 200, 200)\n"
            "    A->>B: shaded\n"
            "  end\n"
        ))
        assert "rect" in html.lower()

    def test_nested_blocks_render(self):
        """Loop inside alt renders without error."""
        html = to_html(_seq(
            "  alt retry path\n"
            "    loop 3 times\n"
            "      A->>B: attempt\n"
            "    end\n"
            "  else give up\n"
            "    A->>B: fail\n"
            "  end\n"
        ))
        assert html


# ─────────────────────────────────────────────────────────────────────────────
# Sequencing directives
# ─────────────────────────────────────────────────────────────────────────────

class TestSequenceSequencing:
    """Directives that affect numbering or grouping: autonumber, box."""

    def test_autonumber_renders(self):
        """`autonumber` is silently accepted; diagram still renders."""
        html = to_html(_seq(
            "  autonumber\n"
            "  Alice->>Bob: first\n"
            "  Bob-->>Alice: second\n"
        ))
        assert html
        assert "Alice" in html
        assert "Bob" in html

    def test_autonumber_does_not_create_phantom_participant(self):
        """`autonumber` must not appear as a participant name."""
        html = to_html(_seq(
            "  autonumber\n"
            "  A->>B: msg\n"
        ))
        assert "autonumber" not in html.lower() or html.lower().count("autonumber") == 0 or \
               "data-node-id=\"autonumber\"" not in html

    def test_box_grouping_renders(self):
        """`box Title … end` groups are accepted; participants render."""
        html = to_html(_seq(
            "  box Frontend\n"
            "    participant Browser\n"
            "    participant UI\n"
            "  end\n"
            "  box Backend\n"
            "    participant API\n"
            "  end\n"
            "  Browser->>API: fetch\n"
            "  API-->>Browser: response\n"
        ))
        assert html
        assert "Browser" in html
        assert "API" in html

    def test_box_single_participant(self):
        """`box` with a single participant renders the participant."""
        html = to_html(_seq(
            "  box Services\n"
            "    participant Auth\n"
            "  end\n"
            "  Client->>Auth: login\n"
        ))
        assert "Auth" in html
        assert "Client" in html

    def test_autonumber_with_blocks(self):
        """`autonumber` combined with a loop block renders without error."""
        html = to_html(_seq(
            "  autonumber\n"
            "  A->>B: start\n"
            "  loop retry\n"
            "    A->>B: ping\n"
            "  end\n"
        ))
        assert html
        assert "loop" in html.lower()
