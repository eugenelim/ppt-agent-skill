#!/usr/bin/env python3
"""Regression tests for stateDiagram renderer fixes.

Covers:
  1. Terminal-circle (start/end state) horizontal centering in TB mode.
  2. Transition arrow labels appear near midpoint.
  3. Composite state group box rendered with label.
  4. Start state renders ● symbol; end state renders ◎ symbol.
  5. direction-directive inside body does not create a spurious node.
  6. All three fixture files render without errors.

Import pattern mirrors tests/test_mermaid_layout.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout import (
    _dispatch,
    _parse_graph_source,
    NODE_W,
    CANVAS_PAD,
)
from mermaid_render.layout._constants import _TERMINAL_NODE_SIZE


# ── helpers ───────────────────────────────────────────────────────────────────

def _dispatch_ok(src: str, width: int = 800) -> str:
    return _dispatch(src, None, width)


def _node_left(html: str, node_id: str) -> int | None:
    """Return CSS left value (px) for a node div, or None if not found."""
    m = re.search(
        rf'data-node-id="{re.escape(node_id)}"[^>]*left:(\d+)px', html
    )
    return int(m.group(1)) if m else None


def _edge_labels(html: str) -> list[str]:
    return re.findall(r'class="edge-label"[^>]*>([^<]+)', html)


# ── TestCircleCenteringTB ─────────────────────────────────────────────────────

class TestCircleCenteringTB:
    """Terminal-circle nodes must be horizontally centred within their column slot (TB).

    _assign_coordinates places every node at the column left edge so that rect
    nodes (NODE_W wide) fill the slot exactly.  Terminal circles are only
    _TERMINAL_NODE_SIZE px wide; without adjustment their visual centre sits
    (NODE_W / 2 - _TERMINAL_NODE_SIZE / 2) px to the LEFT of the rect centre,
    causing a horizontal jog in every transition arrow that connects them.

    After the fix: circle.left == rect.left + (NODE_W - _TERMINAL_NODE_SIZE) // 2,
    i.e. both share the same column centre.
    """

    _BASIC_SRC = (
        "stateDiagram-v2\n"
        "  [*] --> Idle\n"
        "  Idle --> Processing : start\n"
        "  Processing --> Done : complete\n"
        "  Done --> [*]"
    )

    def test_start_circle_centered_relative_to_first_state(self):
        """Start circle left = Idle left + (NODE_W - circle_size) // 2."""
        html = _dispatch_ok(self._BASIC_SRC)
        start_left = _node_left(html, "_sm_start_")
        idle_left = _node_left(html, "Idle")
        assert start_left is not None, "_sm_start_ node not found"
        assert idle_left is not None, "Idle node not found"
        expected_offset = (NODE_W - _TERMINAL_NODE_SIZE) // 2
        assert start_left == idle_left + expected_offset, (
            f"_sm_start_ left={start_left} should be Idle left ({idle_left}) "
            f"+ {expected_offset} = {idle_left + expected_offset}"
        )

    def test_end_circle_centered_relative_to_last_state(self):
        """End circle left = Done left + (NODE_W - circle_size) // 2."""
        html = _dispatch_ok(self._BASIC_SRC)
        end_left = _node_left(html, "_sm_end_")
        done_left = _node_left(html, "Done")
        assert end_left is not None, "_sm_end_ node not found"
        assert done_left is not None, "Done node not found"
        expected_offset = (NODE_W - _TERMINAL_NODE_SIZE) // 2
        assert end_left == done_left + expected_offset, (
            f"_sm_end_ left={end_left} should be Done left ({done_left}) "
            f"+ {expected_offset} = {done_left + expected_offset}"
        )

    def test_start_circle_center_matches_rect_center(self):
        """Circle visual centre (left + half-width) == rect visual centre."""
        html = _dispatch_ok(self._BASIC_SRC)
        start_left = _node_left(html, "_sm_start_")
        idle_left = _node_left(html, "Idle")
        assert start_left is not None and idle_left is not None
        circle_center = start_left + _TERMINAL_NODE_SIZE // 2
        rect_center = idle_left + NODE_W // 2
        assert circle_center == rect_center, (
            f"Circle centre {circle_center} != rect centre {rect_center}"
        )

    def test_arrow_from_start_is_vertical(self):
        """SVG path from start circle to first rect state must be vertical (single x value)."""
        html = _dispatch_ok(self._BASIC_SRC)
        paths = re.findall(r'd="(M[^"]+)"', html)
        assert paths, "No SVG paths found"
        first_path = paths[0]
        # Extract all x coordinates from M/L commands
        coords = re.findall(r'[ML]\s+(\d+\.?\d*)\s+(\d+\.?\d*)', first_path)
        x_vals = [float(x) for x, y in coords]
        # All x values should be within 1px of each other (straight vertical line)
        if len(x_vals) >= 2:
            assert max(x_vals) - min(x_vals) <= 1, (
                f"First path has non-vertical segment: x values={x_vals}, path={first_path}"
            )

    def test_nested_inner_circles_centered(self):
        """Inner start/end circles inside composite state are also centred."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        html = _dispatch_ok(src)
        inner_start = _node_left(html, "_g0_sm_start_")
        validating = _node_left(html, "Validating")
        assert inner_start is not None, "_g0_sm_start_ not found"
        assert validating is not None, "Validating not found"
        expected_offset = (NODE_W - _TERMINAL_NODE_SIZE) // 2
        assert inner_start == validating + expected_offset, (
            f"Inner _g0_sm_start_ left={inner_start} should be Validating left ({validating}) "
            f"+ {expected_offset}"
        )


# ── TestTransitionLabels ──────────────────────────────────────────────────────

class TestTransitionLabels:
    """Transition labels ('State --> Other : label') appear near arrow midpoints."""

    def test_basic_fixture_labels(self):
        """Basic fixture labels 'start' and 'complete' appear in edge-label spans."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-basic.mmd").read()
        html = _dispatch_ok(src)
        labels = _edge_labels(html)
        assert "start" in labels, f"'start' label missing. Got: {labels}"
        assert "complete" in labels, f"'complete' label missing. Got: {labels}"

    def test_complex_fixture_labels(self):
        """Complex fixture labels appear in edge-label spans."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-complex.mmd").read()
        html = _dispatch_ok(src)
        labels = _edge_labels(html)
        for expected in ("login", "success", "failure", "logout"):
            assert expected in labels, (
                f"Label '{expected}' missing from complex fixture. Got: {labels}"
            )

    def test_nested_fixture_labels(self):
        """Nested fixture labels appear in edge-label spans."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        html = _dispatch_ok(src)
        labels = _edge_labels(html)
        for expected in ("start", "valid", "success", "error"):
            assert expected in labels, (
                f"Label '{expected}' missing from nested fixture. Got: {labels}"
            )

    def test_inline_label_no_crash(self):
        """Single-transition diagram with label renders without error."""
        html = _dispatch_ok("stateDiagram-v2\n  A --> B : go")
        assert "go" in _edge_labels(html), (
            f"Label 'go' missing. Got: {_edge_labels(html)}"
        )


# ── TestCompositeStateGroup ───────────────────────────────────────────────────

class TestCompositeStateGroup:
    """Composite state (state X { ... }) renders a group box with label."""

    def test_group_box_present(self):
        """Nested fixture produces at least one diagram-group container."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        html = _dispatch_ok(src)
        groups = re.findall(r'class="diagram-group"', html)
        assert groups, "No diagram-group container found in nested fixture"

    def test_group_label_present(self):
        """Group label 'Processing' appears in the group-label span."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        html = _dispatch_ok(src)
        group_labels = re.findall(r'class="group-label"[^>]*>([^<]+)', html)
        # group-label may use text-transform:uppercase in CSS, but raw content is unchanged
        assert any("Processing" in lbl for lbl in group_labels), (
            f"'Processing' missing from group labels. Got: {group_labels}"
        )

    def test_child_states_inside_group(self):
        """Child states Validating and Executing appear in the output."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        html = _dispatch_ok(src)
        node_labels = re.findall(r'class="node-label"[^>]*>([^<]+)', html)
        assert "Validating" in node_labels, f"'Validating' missing. Got: {node_labels}"
        assert "Executing" in node_labels, f"'Executing' missing. Got: {node_labels}"

    def test_inline_composite_group_present(self):
        """Inline composite state (not from file) produces a diagram-group."""
        html = _dispatch_ok(
            "stateDiagram-v2\n"
            "  [*] --> A\n"
            "  state A {\n"
            "    [*] --> X\n"
            "    X --> [*]\n"
            "  }\n"
            "  A --> [*]"
        )
        groups = re.findall(r'class="diagram-group"', html)
        assert groups, "No diagram-group for inline composite state"


# ── TestStartEndSymbols ───────────────────────────────────────────────────────

class TestStartEndSymbols:
    """Start state renders ● (bullet) and end state renders ◎ (double circle)."""

    def test_start_symbol_in_html(self):
        """[*] as source renders the filled-circle ● start marker."""
        html = _dispatch_ok("stateDiagram-v2\n  [*] --> Idle")
        assert "●" in html, "Start state ● missing"

    def test_end_symbol_in_html(self):
        """[*] as target renders the double-circle ◎ end marker."""
        html = _dispatch_ok("stateDiagram-v2\n  Done --> [*]")
        assert "◎" in html, "End state ◎ missing"

    def test_start_node_is_circle_shape(self):
        """_sm_start_ node has shape circle."""
        nodes, _, _ = _parse_graph_source(["[*] --> Idle"])
        assert "_sm_start_" in nodes
        assert nodes["_sm_start_"].shape == "circle"

    def test_end_node_is_circle_shape(self):
        """_sm_end_ node has shape circle."""
        nodes, _, _ = _parse_graph_source(["Done --> [*]"])
        assert "_sm_end_" in nodes
        assert nodes["_sm_end_"].shape == "circle"

    def test_start_node_bullet_label(self):
        """_sm_start_ node label is the ● character."""
        nodes, _, _ = _parse_graph_source(["[*] --> Idle"])
        assert nodes["_sm_start_"].label == "●"

    def test_end_node_doublecircle_label(self):
        """_sm_end_ node label is the ◎ character."""
        nodes, _, _ = _parse_graph_source(["Done --> [*]"])
        assert nodes["_sm_end_"].label == "◎"

    def test_inner_start_end_circles(self):
        """Inner [*] inside composite state also get ● / ◎ labels."""
        lines = [
            "state Processing {",
            "  [*] --> X",
            "  X --> [*]",
            "}",
        ]
        nodes, _, _ = _parse_graph_source(lines)
        inner_starts = [n for nid, n in nodes.items() if nid.endswith("_sm_start_")]
        inner_ends = [n for nid, n in nodes.items() if nid.endswith("_sm_end_")]
        assert inner_starts, "No inner start node found"
        assert inner_ends, "No inner end node found"
        assert all(n.label == "●" for n in inner_starts)
        assert all(n.label == "◎" for n in inner_ends)


# ── TestDirectionDirective ────────────────────────────────────────────────────

class TestDirectionDirective:
    """direction LR / TB inside stateDiagram-v2 body must not create a spurious node."""

    def test_no_direction_node_lr(self):
        """'direction LR' line does not produce a node named 'direction'."""
        nodes, _, _ = _parse_graph_source([
            "direction LR",
            "[*] --> A",
            "A --> B",
        ])
        assert "direction" not in nodes, (
            f"Spurious 'direction' node created. nodes={list(nodes)}"
        )

    def test_no_direction_node_tb(self):
        """'direction TB' line does not produce a node named 'direction'."""
        nodes, _, _ = _parse_graph_source([
            "direction TB",
            "[*] --> A",
        ])
        assert "direction" not in nodes

    def test_direction_lr_diagram_renders(self):
        """stateDiagram-v2 with 'direction LR' inside body renders without crash."""
        html = _dispatch_ok(
            "stateDiagram-v2\n"
            "  direction LR\n"
            "  [*] --> A\n"
            "  A --> B\n"
            "  B --> [*]"
        )
        assert "diagram mermaid-layout" in html
        assert "A" in html
        assert "B" in html

    def test_states_still_rendered_with_direction(self):
        """Actual state nodes still appear when direction directive is present."""
        nodes, _, _ = _parse_graph_source([
            "direction LR",
            "[*] --> Idle",
            "Idle --> Active",
        ])
        assert "Idle" in nodes, "Idle missing after direction directive"
        assert "Active" in nodes, "Active missing after direction directive"


# ── TestFixtureSmoke ──────────────────────────────────────────────────────────

class TestFixtureSmoke:
    """All three state diagram fixture files render without errors."""

    def test_basic_fixture_renders(self):
        """statediagram-basic.mmd renders to a valid HTML fragment."""
        src = (REPO_ROOT / "tests" / "fixtures" / "statediagram-basic.mmd").read_text()
        html = _dispatch(src, None, 800)
        assert "diagram mermaid-layout" in html

    def test_complex_fixture_renders(self):
        """statediagram-complex.mmd renders to a valid HTML fragment."""
        src = (REPO_ROOT / "tests" / "fixtures" / "statediagram-complex.mmd").read_text()
        html = _dispatch(src, None, 800)
        assert "diagram mermaid-layout" in html

    def test_nested_fixture_renders(self):
        """statediagram-nested.mmd renders to a valid HTML fragment."""
        src = (REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read_text()
        html = _dispatch(src, None, 800)
        assert "diagram mermaid-layout" in html
        assert "Processing" in html

    def test_v1_directive_alias(self):
        """stateDiagram (v1) directive is treated identically to stateDiagram-v2."""
        html = _dispatch_ok("stateDiagram\n  [*] --> Idle\n  Idle --> [*]")
        assert "diagram mermaid-layout" in html
        assert "●" in html
        assert "◎" in html
