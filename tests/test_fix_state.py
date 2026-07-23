#!/usr/bin/env python3
"""Regression tests for stateDiagram renderer fixes.

Covers:
  1. Terminal-circle (start/end state) horizontal centering in TB mode.
  2. Transition arrow labels appear near midpoint.
  3. Composite state group box rendered with label.
  4. Start state renders as CSS filled disc (no ● glyph in label span); end state renders ◎.
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
from mermaid_render.layout._strategies import _compile_flowchart


# ── helpers ───────────────────────────────────────────────────────────────────

def _dispatch_ok(src: str, width: int = 800) -> str:
    return _dispatch(src, None, width)


def _node_left(html: str, node_id: str) -> int | None:
    """Return CSS left value (px) for a node div, or None if not found."""
    m = re.search(
        rf'data-node-id="{re.escape(node_id)}"[^>]*left:(\d+)px', html
    )
    return int(m.group(1)) if m else None


def _node_width(html: str, node_id: str) -> int | None:
    """Return CSS width value (px) for a node div, or None if not found."""
    m = re.search(
        rf'data-node-id="{re.escape(node_id)}"[^>]*width:(\d+)px', html
    )
    return int(m.group(1)) if m else None


def _edge_labels(html: str) -> list[str]:
    return re.findall(r'class="edge-label"[^>]*>([^<]+)', html)


# ── TestCircleCenteringTB ─────────────────────────────────────────────────────

class TestCircleCenteringTB:
    """Terminal-circle nodes must be horizontally centred within their column slot (TB).

    _assign_coordinates centers every node within its _layout_nw-wide column slot.
    Terminal circles are _TERMINAL_NODE_SIZE px wide and get an additional
    _circ_shift applied in _strategies.py so their visual centre aligns with
    the column centre shared by all rect-type nodes in the same column.

    Invariant: circle.left + _TERMINAL_NODE_SIZE // 2 == rect.left + rect_width // 2
    """

    _BASIC_SRC = (
        "stateDiagram-v2\n"
        "  [*] --> Idle\n"
        "  Idle --> Processing : start\n"
        "  Processing --> Done : complete\n"
        "  Done --> [*]"
    )

    def test_start_circle_centered_relative_to_first_state(self):
        """Start circle center == Idle center (both centered in column slot)."""
        html = _dispatch_ok(self._BASIC_SRC)
        start_left = _node_left(html, "_sm_start_")
        idle_left = _node_left(html, "Idle")
        idle_width = _node_width(html, "Idle")
        assert start_left is not None, "_sm_start_ node not found"
        assert idle_left is not None, "Idle node not found"
        assert idle_width is not None, "Idle width not found"
        expected_offset = (idle_width - _TERMINAL_NODE_SIZE) // 2
        assert start_left == idle_left + expected_offset, (
            f"_sm_start_ left={start_left} should be Idle left ({idle_left}) "
            f"+ (idle_width {idle_width} - circle {_TERMINAL_NODE_SIZE}) // 2 = "
            f"{idle_left + expected_offset}"
        )

    def test_end_circle_centered_relative_to_last_state(self):
        """End circle center == Done center (both centered in column slot)."""
        html = _dispatch_ok(self._BASIC_SRC)
        end_left = _node_left(html, "_sm_end_")
        done_left = _node_left(html, "Done")
        done_width = _node_width(html, "Done")
        assert end_left is not None, "_sm_end_ node not found"
        assert done_left is not None, "Done node not found"
        assert done_width is not None, "Done width not found"
        expected_offset = (done_width - _TERMINAL_NODE_SIZE) // 2
        assert end_left == done_left + expected_offset, (
            f"_sm_end_ left={end_left} should be Done left ({done_left}) "
            f"+ (done_width {done_width} - circle {_TERMINAL_NODE_SIZE}) // 2 = "
            f"{done_left + expected_offset}"
        )

    def test_start_circle_center_matches_rect_center(self):
        """Circle visual centre (left + half-width) == rect visual centre."""
        html = _dispatch_ok(self._BASIC_SRC)
        start_left = _node_left(html, "_sm_start_")
        idle_left = _node_left(html, "Idle")
        idle_width = _node_width(html, "Idle")
        assert start_left is not None and idle_left is not None and idle_width is not None
        circle_center = start_left + _TERMINAL_NODE_SIZE // 2
        rect_center = idle_left + idle_width // 2
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
        inner_start = _node_left(html, "Processing_sm_start_")
        validating = _node_left(html, "Validating")
        validating_width = _node_width(html, "Validating")
        assert inner_start is not None, "Processing_sm_start_ not found"
        assert validating is not None, "Validating not found"
        assert validating_width is not None, "Validating width not found"
        expected_offset = (validating_width - _TERMINAL_NODE_SIZE) // 2
        assert inner_start == validating + expected_offset, (
            f"Inner Processing_sm_start_ left={inner_start} should be Validating left ({validating}) "
            f"+ (validating_width {validating_width} - circle {_TERMINAL_NODE_SIZE}) // 2 = "
            f"{validating + expected_offset}"
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
    """Start state renders as CSS filled disc; end state renders as doublecircle with filled inner disc."""

    def test_start_symbol_in_html(self):
        """[*] as source sets data-label="●" (CSS disc — no ● text in node-label span)."""
        html = _dispatch_ok("stateDiagram-v2\n  [*] --> Idle")
        assert "●" in html, "Start state data-label ● missing"

    def test_end_node_is_doublecircle_in_html(self):
        """[*] as target renders as node-doublecircle (UML final-state double ring)."""
        html = _dispatch_ok("stateDiagram-v2\n  Done --> [*]")
        assert "node-doublecircle" in html, "End state node-doublecircle class missing"

    def test_start_node_is_circle_shape(self):
        """_sm_start_ node has shape circle."""
        nodes, _, _ = _parse_graph_source(["[*] --> Idle"])
        assert "_sm_start_" in nodes
        assert nodes["_sm_start_"].shape == "circle"

    def test_end_node_is_doublecircle_shape(self):
        """_sm_end_ node has shape doublecircle (UML final-state correct shape)."""
        nodes, _, _ = _parse_graph_source(["Done --> [*]"])
        assert "_sm_end_" in nodes
        assert nodes["_sm_end_"].shape == "doublecircle"

    def test_start_node_bullet_label(self):
        """_sm_start_ node label is the ● character."""
        nodes, _, _ = _parse_graph_source(["[*] --> Idle"])
        assert nodes["_sm_start_"].label == "●"

    def test_end_node_empty_label(self):
        """_sm_end_ node label is empty (shape provides the visual, no text needed)."""
        nodes, _, _ = _parse_graph_source(["Done --> [*]"])
        assert nodes["_sm_end_"].label == ""

    def test_inner_start_end_shapes(self):
        """Inner [*] inside composite state: start gets circle, end gets doublecircle."""
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
        assert all(n.shape == "doublecircle" for n in inner_ends)


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
        assert "node-doublecircle" in html

    def test_initial_disc_not_in_node_label_span(self):
        """AC9: ● character must not appear inside a node-label span (CSS disc renders it)."""
        html = _dispatch_ok("stateDiagram-v2\n  [*] --> Idle")
        node_label_texts = re.findall(r'class="node-label"[^>]*>([^<]*)', html)
        assert not any("●" in t for t in node_label_texts), (
            f"Initial state ● leaked into node-label span: {node_label_texts}"
        )

    def test_final_state_inner_disc_uses_background(self):
        """AC10: doublecircle inner div uses background (filled disc) not border-only ring."""
        html = _dispatch_ok("stateDiagram-v2\n  Done --> [*]")
        # The outer doublecircle div is followed by an inner <div> that must have background
        inner_divs = re.findall(
            r'node-doublecircle.*?(<div style="[^"]*")', html, re.DOTALL
        )
        assert inner_divs, "No doublecircle inner div found"
        assert any("background:" in d for d in inner_divs), (
            f"Final state inner div missing background fill: {inner_divs}"
        )


# ── TestSemanticEndpointFields ────────────────────────────────────────────────

class TestSemanticEndpointFields:
    """Integration: RoutedEdge semantic/routing/scope fields are populated correctly
    for state-diagram cross-scope exit edges (AC2) and composite_gates (AC3)."""

    def test_processing_done_semantic_source_id(self):
        """AC2: Processing --> Done edge has semantic_source_id == "Processing"."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        layout = compiled.layout
        edge = next(
            (e for e in layout.routed_edges
             if e.src_node_id == "Processing_sm_end_" and e.dst_node_id == "Done"),
            None,
        )
        assert edge is not None, "Processing -> Done edge not found"
        assert edge.semantic_source_id == "Processing", (
            f"Expected semantic_source_id='Processing', got {edge.semantic_source_id!r}"
        )

    def test_processing_done_routing_source_id(self):
        """AC2: Processing --> Done edge has routing_source_id == "Processing_sm_end_"."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        layout = compiled.layout
        edge = next(
            (e for e in layout.routed_edges
             if e.src_node_id == "Processing_sm_end_" and e.dst_node_id == "Done"),
            None,
        )
        assert edge is not None, "Processing -> Done edge not found"
        assert edge.routing_source_id == "Processing_sm_end_", (
            f"Expected routing_source_id='Processing_sm_end_', got {edge.routing_source_id!r}"
        )

    def test_processing_done_source_scope(self):
        """AC2: Processing --> Done edge has source_scope == "Processing"."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        layout = compiled.layout
        edge = next(
            (e for e in layout.routed_edges
             if e.src_node_id == "Processing_sm_end_" and e.dst_node_id == "Done"),
            None,
        )
        assert edge is not None, "Processing -> Done edge not found"
        assert edge.source_scope == "Processing", (
            f"Expected source_scope='Processing', got {edge.source_scope!r}"
        )

    def test_complex_authenticating_idle_proximity(self):
        """AC5: Authenticating --> Idle back-edge waypoints satisfy proximity constraint.

        No waypoint lies further than 2*NODE_W from the pair's bounding box right edge.
        """
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-complex.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        layout = compiled.layout
        # Find Authenticating -> Idle edge
        edge = next(
            (e for e in layout.routed_edges
             if e.src_node_id == "Authenticating" and e.dst_node_id == "Idle"),
            None,
        )
        assert edge is not None, "Authenticating -> Idle edge not found"
        # Compute pair bbox right edge
        auth_nl = layout.node_layouts.get("Authenticating")
        idle_nl = layout.node_layouts.get("Idle")
        assert auth_nl and idle_nl
        pair_right = max(
            auth_nl.outer_bounds.x + auth_nl.outer_bounds.w,
            idle_nl.outer_bounds.x + idle_nl.outer_bounds.w,
        )
        # All waypoints must be within 2*NODE_W of pair_right
        for wp in edge.waypoints:
            assert wp.x <= pair_right + 2 * NODE_W, (
                f"Waypoint {wp} exceeds pair_right ({pair_right}) + 2*NODE_W "
                f"in Authenticating -> Idle route"
            )

    def test_composite_gates_non_empty_for_nested_fixture(self):
        """AC3: composite_gates is non-empty for statediagram-nested.mmd."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        layout = compiled.layout
        assert len(layout.composite_gates) > 0, (
            "composite_gates should be non-empty for a diagram with composite states"
        )

    def test_composite_gates_contains_processing(self):
        """AC3: composite_gates contains "Processing" key for nested fixture."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        layout = compiled.layout
        assert "Processing" in layout.composite_gates, (
            f"composite_gates keys: {list(layout.composite_gates.keys())}"
        )

    def test_composite_gates_processing_entry_exit(self):
        """AC3: Processing gates tuple is (entry_gate_id, exit_gate_id)."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        gates = compiled.layout.composite_gates.get("Processing")
        assert gates is not None
        entry_id, exit_id = gates
        assert "sm_start" in entry_id, f"entry gate {entry_id!r} doesn't look like a start pseudo-state"
        assert "sm_end" in exit_id, f"exit gate {exit_id!r} doesn't look like an end pseudo-state"

    def test_validate_finalized_layout_no_errors_nested(self):
        """AC11 + AC13: validate_finalized_layout() returns no errors for nested fixture."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        result = compiled.validation
        assert result.errors == (), (
            f"validate_finalized_layout errors for nested fixture: {result.errors}"
        )

    def test_validate_finalized_layout_no_errors_complex(self):
        """AC11 + AC13: validate_finalized_layout() returns no errors for complex fixture."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-complex.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        result = compiled.validation
        assert result.errors == (), (
            f"validate_finalized_layout errors for complex fixture: {result.errors}"
        )

    def test_composite_gates_empty_for_flat_diagram(self):
        """AC3: composite_gates is empty for a flat (no composites) state diagram."""
        flat_src = "stateDiagram-v2\n  [*] --> Idle\n  Idle --> Active\n  Active --> [*]"
        compiled = _compile_flowchart(flat_src, 0, None)
        assert len(compiled.layout.composite_gates) == 0, (
            "composite_gates should be empty for a flat state diagram"
        )
