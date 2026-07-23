"""Tests for Stage 11 — State diagram hierarchical semantics.

Tests the immutable state model types, compile_state_machine(), state_model_to_graph(),
and integration through the existing rendering pipeline for bar/diamond pseudo-states.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.statediagram import (
    AtomicState,
    Choice,
    CompositeState,
    FinalPseudoState,
    Fork,
    History,
    InitialPseudoState,
    Join,
    StateGate,
    StateMachineModel,
    StateNote,
    StateTransition,
    compile_state_machine,
    state_model_to_graph,
)
from mermaid_render import to_html
from mermaid_render.native_svg import dispatch_native


# ── helpers ───────────────────────────────────────────────────────────────────

def _node_labels(html: str) -> list[str]:
    return re.findall(r'class="(?:node|group)-label"[^>]*>([^<]+)', html)


# ── model type: frozen / hashable ─────────────────────────────────────────────

class TestModelTypes:
    """All model types must be frozen (immutable) and hashable."""

    def test_atomic_state_frozen(self):
        s = AtomicState(id="A", label="Alpha")
        with pytest.raises((AttributeError, TypeError)):
            s.id = "B"  # type: ignore[misc]

    def test_atomic_state_hashable(self):
        s = AtomicState(id="A", label="Alpha")
        assert hash(s) is not None
        assert {s}  # membership test

    def test_initial_pseudo_frozen(self):
        s = InitialPseudoState(id="_sm_start_")
        with pytest.raises((AttributeError, TypeError)):
            s.id = "x"  # type: ignore[misc]

    def test_final_pseudo_frozen(self):
        s = FinalPseudoState(id="_sm_end_")
        with pytest.raises((AttributeError, TypeError)):
            s.id = "x"  # type: ignore[misc]

    def test_choice_frozen(self):
        c = Choice(id="C", label="c")
        with pytest.raises((AttributeError, TypeError)):
            c.id = "D"  # type: ignore[misc]

    def test_fork_frozen(self):
        f = Fork(id="F", label="f")
        with pytest.raises((AttributeError, TypeError)):
            f.id = "G"  # type: ignore[misc]

    def test_join_frozen(self):
        j = Join(id="J", label="j")
        with pytest.raises((AttributeError, TypeError)):
            j.id = "K"  # type: ignore[misc]

    def test_history_frozen(self):
        h = History(id="H1", kind="shallow")
        with pytest.raises((AttributeError, TypeError)):
            h.kind = "deep"  # type: ignore[misc]

    def test_history_deep_kind(self):
        h = History(id="H2", kind="deep")
        assert h.kind == "deep"

    def test_state_gate_frozen(self):
        g = StateGate(id="g", kind="entry", composite_id="S")
        with pytest.raises((AttributeError, TypeError)):
            g.kind = "exit"  # type: ignore[misc]

    def test_state_transition_frozen(self):
        t = StateTransition(src_id="A", dst_id="B", label="go")
        with pytest.raises((AttributeError, TypeError)):
            t.label = "stop"  # type: ignore[misc]

    def test_state_note_frozen(self):
        n = StateNote(target_id="A", position="right", text="note")
        with pytest.raises((AttributeError, TypeError)):
            n.text = "other"  # type: ignore[misc]

    def test_composite_state_frozen(self):
        cs = CompositeState(id="S", label="State")
        with pytest.raises((AttributeError, TypeError)):
            cs.label = "Changed"  # type: ignore[misc]

    def test_state_machine_model_frozen(self):
        m = StateMachineModel(states=(), transitions=())
        with pytest.raises((AttributeError, TypeError)):
            m.states = ()  # type: ignore[misc]

    def test_all_types_hashable(self):
        objects = [
            AtomicState(id="A", label="Alpha"),
            InitialPseudoState(id="_sm_start_"),
            FinalPseudoState(id="_sm_end_"),
            Choice(id="C"),
            Fork(id="F"),
            Join(id="J"),
            History(id="H", kind="shallow"),
            StateGate(id="g", kind="entry", composite_id="S"),
            StateTransition(src_id="A", dst_id="B"),
            StateNote(target_id="A"),
            CompositeState(id="S", label="S"),
        ]
        assert len({hash(o) for o in objects}) == len(objects)  # all distinct


# ── compile_state_machine ──────────────────────────────────────────────────────

class TestCompileStateMachine:
    """compile_state_machine() produces correct StateMachineModel from source lines."""

    def test_empty_input(self):
        m = compile_state_machine([])
        assert m.states == ()
        assert m.transitions == ()

    def test_simple_transition(self):
        m = compile_state_machine(["A --> B"])
        assert any(isinstance(s, AtomicState) and s.id == "A" for s in m.states)
        assert any(isinstance(s, AtomicState) and s.id == "B" for s in m.states)
        assert any(t.src_id == "A" and t.dst_id == "B" for t in m.transitions)

    def test_initial_state_from_star(self):
        m = compile_state_machine(["[*] --> Idle"])
        ids = {s.id for s in m.states}
        assert "_sm_start_" in ids
        init = next(s for s in m.states if s.id == "_sm_start_")
        assert isinstance(init, InitialPseudoState)

    def test_final_state_from_star(self):
        m = compile_state_machine(["Done --> [*]"])
        ids = {s.id for s in m.states}
        assert "_sm_end_" in ids
        final = next(s for s in m.states if s.id == "_sm_end_")
        assert isinstance(final, FinalPseudoState)

    def test_fork_pseudo_state(self):
        m = compile_state_machine(["state fork_state <<fork>>"])
        state = next((s for s in m.states if hasattr(s, "id") and s.id == "fork_state"), None)
        assert state is not None
        assert isinstance(state, Fork)

    def test_join_pseudo_state(self):
        m = compile_state_machine(["state join_state <<join>>"])
        state = next((s for s in m.states if hasattr(s, "id") and s.id == "join_state"), None)
        assert state is not None
        assert isinstance(state, Join)

    def test_choice_pseudo_state(self):
        m = compile_state_machine(["state choice_state <<choice>>"])
        state = next((s for s in m.states if hasattr(s, "id") and s.id == "choice_state"), None)
        assert state is not None
        assert isinstance(state, Choice)

    def test_history_shallow(self):
        m = compile_state_machine(["state H1 <<history>>"])
        state = next((s for s in m.states if hasattr(s, "id") and s.id == "H1"), None)
        assert isinstance(state, History)
        assert state.kind == "shallow"

    def test_history_deep(self):
        m = compile_state_machine(["state H2 <<historydeep>>"])
        state = next((s for s in m.states if hasattr(s, "id") and s.id == "H2"), None)
        assert isinstance(state, History)
        assert state.kind == "deep"

    def test_alias(self):
        m = compile_state_machine(['state "Long Label" as short_id'])
        state = next((s for s in m.states if hasattr(s, "id") and s.id == "short_id"), None)
        assert state is not None
        assert isinstance(state, AtomicState)
        assert state.label == "Long Label"

    def test_description_sets_label(self):
        m = compile_state_machine(["idle : Idle State"])
        state = next((s for s in m.states if hasattr(s, "id") and s.id == "idle"), None)
        assert state is not None
        assert state.label == "Idle State"

    def test_transition_label(self):
        m = compile_state_machine(["A --> B : go"])
        t = next((t for t in m.transitions if t.src_id == "A" and t.dst_id == "B"), None)
        assert t is not None
        assert t.label == "go"

    def test_inline_note(self):
        m = compile_state_machine(["A --> B", "note right of A : This is A"])
        assert any(n.target_id == "A" and n.text == "This is A" for n in m.notes)

    def test_multiline_note(self):
        m = compile_state_machine([
            "A --> B",
            "note left of B",
            "Line one",
            "Line two",
            "end note",
        ])
        note = next((n for n in m.notes if n.target_id == "B"), None)
        assert note is not None
        assert "Line one" in note.text
        assert "Line two" in note.text
        assert note.position == "left"

    def test_composite_state_produces_composite(self):
        m = compile_state_machine(["state Active {", "  A --> B", "}"])
        cs = next((s for s in m.states if isinstance(s, CompositeState) and s.id == "Active"), None)
        assert cs is not None

    def test_composite_state_has_gates(self):
        m = compile_state_machine(["state Active {", "  [*] --> A", "}"])
        cs = next(s for s in m.states if isinstance(s, CompositeState) and s.id == "Active")
        assert cs.entry_gate is not None
        assert cs.entry_gate.kind == "entry"
        assert cs.exit_gate is not None
        assert cs.exit_gate.kind == "exit"

    def test_concurrent_separator_ignored(self):
        m = compile_state_machine(["state S {", "  A --> B", "  --", "  C --> D", "}"])
        # Should not raise; -- is ignored; transitions live in cs.transitions (composite scope)
        cs = next(s for s in m.states if isinstance(s, CompositeState) and s.id == "S")
        assert any(t.src_id == "A" for t in cs.transitions)
        assert any(t.src_id == "C" for t in cs.transitions)

    def test_direction_directive_ignored(self):
        m = compile_state_machine(["direction LR", "A --> B"])
        assert any(t.src_id == "A" for t in m.transitions)

    def test_comment_line_skipped(self):
        m = compile_state_machine(["%%comment line", "A --> B"])
        assert any(t.src_id == "A" for t in m.transitions)

    def test_fork_join_full_diagram(self):
        lines = [
            "state fork_state <<fork>>",
            "state join_state <<join>>",
            "[*] --> fork_state",
            "fork_state --> s1",
            "fork_state --> s2",
            "s1 --> join_state",
            "s2 --> join_state",
            "join_state --> [*]",
        ]
        m = compile_state_machine(lines)
        ids = {s.id for s in m.states if hasattr(s, "id")}
        assert "fork_state" in ids
        assert "join_state" in ids
        fork = next(s for s in m.states if hasattr(s, "id") and s.id == "fork_state")
        join = next(s for s in m.states if hasattr(s, "id") and s.id == "join_state")
        assert isinstance(fork, Fork)
        assert isinstance(join, Join)


# ── state_model_to_graph shapes ────────────────────────────────────────────────

class TestStateModelToGraph:
    """state_model_to_graph() produces correct _Node shapes for each pseudo-state type."""

    def _graph_from(self, lines: list[str]):
        m = compile_state_machine(lines)
        return state_model_to_graph(m)

    def test_atomic_state_is_rect(self):
        nodes, _, _ = self._graph_from(["A --> B"])
        assert nodes["A"].shape == "rect"
        assert nodes["B"].shape == "rect"

    def test_initial_pseudo_is_circle(self):
        nodes, _, _ = self._graph_from(["[*] --> Idle"])
        assert nodes["_sm_start_"].shape == "circle"

    def test_final_pseudo_is_doublecircle(self):
        nodes, _, _ = self._graph_from(["Done --> [*]"])
        assert nodes["_sm_end_"].shape == "doublecircle"

    def test_initial_pseudo_label_filled_circle(self):
        nodes, _, _ = self._graph_from(["[*] --> Idle"])
        assert nodes["_sm_start_"].label == "●"

    def test_final_pseudo_label_empty(self):
        nodes, _, _ = self._graph_from(["Done --> [*]"])
        assert nodes["_sm_end_"].label == ""

    def test_fork_is_bar(self):
        nodes, _, _ = self._graph_from(["state F <<fork>>", "[*] --> F"])
        assert nodes["F"].shape == "bar"

    def test_join_is_bar(self):
        nodes, _, _ = self._graph_from(["state J <<join>>", "A --> J"])
        assert nodes["J"].shape == "bar"

    def test_fork_css_class(self):
        nodes, _, _ = self._graph_from(["state F <<fork>>", "[*] --> F"])
        assert nodes["F"].css_class == "state-fork"

    def test_join_css_class(self):
        nodes, _, _ = self._graph_from(["state J <<join>>", "A --> J"])
        assert nodes["J"].css_class == "state-join"

    def test_choice_is_diamond(self):
        nodes, _, _ = self._graph_from(["state C <<choice>>", "[*] --> C"])
        assert nodes["C"].shape == "diamond"

    def test_choice_css_class(self):
        nodes, _, _ = self._graph_from(["state C <<choice>>", "[*] --> C"])
        assert nodes["C"].css_class == "state-choice"

    def test_history_shallow_is_circle(self):
        nodes, _, _ = self._graph_from(["state H <<history>>", "A --> H"])
        assert nodes["H"].shape == "circle"

    def test_history_shallow_label(self):
        nodes, _, _ = self._graph_from(["state H <<history>>", "A --> H"])
        assert nodes["H"].label == "H"

    def test_history_deep_label(self):
        nodes, _, _ = self._graph_from(["state H <<historydeep>>", "A --> H"])
        assert nodes["H"].label == "H*"

    def test_composite_produces_group(self):
        nodes, _, groups = self._graph_from([
            "state Active {",
            "  [*] --> Ready",
            "}",
        ])
        assert any(g.label == "Active" for g in groups.values())

    def test_edges_present(self):
        _, edges, _ = self._graph_from(["A --> B"])
        assert any(e.src == "A" and e.dst == "B" for e in edges)

    def test_transition_label_preserved(self):
        _, edges, _ = self._graph_from(["A --> B : go"])
        edge = next(e for e in edges if e.src == "A" and e.dst == "B")
        assert edge.label == "go"


# ── integration: bar and diamond shapes in rendered HTML ──────────────────────

class TestBarShapeIntegration:
    """Fork/join pseudo-states render as bar-shaped nodes in HTML output."""

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

    def test_renders_without_crash(self):
        html = to_html(self._SRC)
        assert "diagram mermaid-layout" in html

    def test_fork_label_present(self):
        html = to_html(self._SRC)
        assert "fork_state" in _node_labels(html)

    def test_join_label_present(self):
        html = to_html(self._SRC)
        assert "join_state" in _node_labels(html)

    def test_bar_shape_class_present(self):
        """node-bar CSS class is emitted for fork/join nodes."""
        html = to_html(self._SRC)
        assert "node-bar" in html

    def test_no_spurious_state_node(self):
        """Bug fix: 'state' is not created as a spurious atomic node."""
        html = to_html(self._SRC)
        labels = _node_labels(html)
        assert "state" not in labels, f"Spurious 'state' node found: {labels}"

    def test_branches_present(self):
        html = to_html(self._SRC)
        labels = _node_labels(html)
        assert "s1" in labels
        assert "s2" in labels


class TestChoiceShapeIntegration:
    """Choice pseudo-states render as diamond-shaped nodes in HTML output."""

    _SRC = (
        "stateDiagram-v2\n"
        "  state choice_state <<choice>>\n"
        "  [*] --> choice_state\n"
        "  choice_state --> s1 : if x\n"
        "  choice_state --> s2 : if not x\n"
    )

    def test_renders_without_crash(self):
        html = to_html(self._SRC)
        assert "diagram mermaid-layout" in html

    def test_choice_label_present(self):
        html = to_html(self._SRC)
        assert "choice_state" in _node_labels(html)

    def test_diamond_shape_class_present(self):
        """node-diamond CSS class is emitted for choice nodes."""
        html = to_html(self._SRC)
        assert "node-diamond" in html

    def test_no_spurious_state_node(self):
        html = to_html(self._SRC)
        labels = _node_labels(html)
        assert "state" not in labels, f"Spurious 'state' node found: {labels}"


class TestHistoryShapeIntegration:
    """History pseudo-states render as circle nodes with H label."""

    _SRC = (
        "stateDiagram-v2\n"
        "  state Outer {\n"
        "    state H1 <<history>>\n"
        "    [*] --> H1\n"
        "    H1 --> Running\n"
        "  }\n"
    )

    def test_renders_without_crash(self):
        html = to_html(self._SRC)
        assert "diagram mermaid-layout" in html

    def test_no_spurious_state_node(self):
        html = to_html(self._SRC)
        labels = _node_labels(html)
        assert "state" not in labels, f"Spurious 'state' node found: {labels}"


# ── integration: SVG path (dispatch_native) ────────────────────────────────────

_FORK_JOIN_SRC = (
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

_CHOICE_SRC = (
    "stateDiagram-v2\n"
    "  state choice_state <<choice>>\n"
    "  [*] --> choice_state\n"
    "  choice_state --> s1 : if x\n"
    "  choice_state --> s2 : if not x\n"
)


class TestBarShapeSvgPath:
    """Fork/join bar shape renders correctly via dispatch_native() SVG path."""

    def test_fork_join_svg_renders(self):
        """Fork/join diagram produces valid SVG via dispatch_native()."""
        svg = dispatch_native(_FORK_JOIN_SRC)
        assert "<svg" in svg

    def test_fork_join_svg_no_crash(self):
        """Fork/join diagram does not raise during SVG rendering."""
        svg = dispatch_native(_FORK_JOIN_SRC)
        assert svg  # non-empty

    def test_fork_join_bar_class_in_svg(self):
        """node-bar class appears in SVG output for fork/join nodes."""
        svg = dispatch_native(_FORK_JOIN_SRC)
        assert "node-bar" in svg, "bar shape CSS class missing from SVG"

    def test_fork_join_no_spurious_state_in_svg(self):
        """Spurious 'state' node is not created in SVG rendering."""
        svg = dispatch_native(_FORK_JOIN_SRC)
        assert 'data-label="state"' not in svg

    def test_choice_diamond_in_svg(self):
        """Choice pseudo-state renders as diamond (polygon) in SVG."""
        svg = dispatch_native(_CHOICE_SRC)
        assert "<svg" in svg
        assert "node-diamond" in svg, "diamond shape CSS class missing from SVG"


# ── Task 1: compile_state_machine() recursive children ────────────────────────

class TestCompositeChildren:
    """compile_state_machine() must populate CompositeState.children recursively."""

    def test_composite_children_populated(self):
        lines = ["state Processing {", "[*] --> Validating", "Validating --> Executing", "}"]
        m = compile_state_machine(lines)
        cs = next(s for s in m.states if isinstance(s, CompositeState) and s.id == "Processing")
        assert len(cs.children) > 0

    def test_inner_start_in_children(self):
        lines = ["state Processing {", "[*] --> Validating", "}"]
        m = compile_state_machine(lines)
        cs = next(s for s in m.states if isinstance(s, CompositeState))
        ids = {s.id for s in cs.children if hasattr(s, "id")}
        assert "Processing_sm_start_" in ids

    def test_inner_transitions_in_composite(self):
        lines = ["state Processing {", "[*] --> Validating", "Validating --> Executing", "}"]
        m = compile_state_machine(lines)
        cs = next(s for s in m.states if isinstance(s, CompositeState))
        assert any(t.src_id == "Validating" for t in cs.transitions)

    def test_cross_scope_transition_in_top_level(self):
        lines = ["state Processing {", "[*] --> X", "}", "Processing --> Done"]
        m = compile_state_machine(lines)
        assert any(t.src_id == "Processing" and t.dst_id == "Done" for t in m.transitions)

    def test_composite_no_inner_star(self):
        """Composite with no [*] inside: does not crash; children are emitted."""
        lines = ["state Processing {", "A --> B", "}"]
        m = compile_state_machine(lines)
        cs = next(s for s in m.states if isinstance(s, CompositeState))
        child_ids = {s.id for s in cs.children if hasattr(s, "id")}
        assert "A" in child_ids and "B" in child_ids

    def test_two_level_nesting(self):
        """Nested composite (Processing > Inner > X) compiles without crash."""
        lines = [
            "state Processing {",
            "  state Inner {",
            "    [*] --> X",
            "  }",
            "  [*] --> Inner",
            "}",
        ]
        m = compile_state_machine(lines)
        cs = next(s for s in m.states if isinstance(s, CompositeState) and s.id == "Processing")
        inner_ids = {s.id for s in cs.children if hasattr(s, "id")}
        assert "Inner" in inner_ids
        inner = next(s for s in cs.children if isinstance(s, CompositeState) and s.id == "Inner")
        grandchild_ids = {s.id for s in inner.children if hasattr(s, "id")}
        assert "X" in grandchild_ids


# ── Task 2: state_model_to_graph() cross-scope handling ───────────────────────

class TestCrossScopeGraph:
    """state_model_to_graph() routes cross-scope transitions correctly."""

    def test_composite_group_has_children_as_members(self):
        m = compile_state_machine([
            "state Processing {", "[*] --> Validating", "Validating --> Executing",
            "Executing --> [*]", "}",
        ])
        nodes, edges, groups = state_model_to_graph(m)
        g = next(g for g in groups.values() if g.label == "Processing")
        assert "Processing_sm_start_" in g.members
        assert "Validating" in g.members

    def test_cross_scope_exit_edge_has_src_group(self):
        m = compile_state_machine([
            "state Processing {", "[*] --> X", "X --> [*]", "}",
            "Processing --> Done",
        ])
        nodes, edges, groups = state_model_to_graph(m)
        exit_edge = next(e for e in edges if e.dst == "Done")
        assert exit_edge.src_group is not None

    def test_cross_scope_entry_targets_inner_start(self):
        m = compile_state_machine([
            "Idle --> Processing",
            "state Processing {", "[*] --> X", "}",
        ])
        nodes, edges, groups = state_model_to_graph(m)
        entry_edge = next(e for e in edges if e.src == "Idle")
        assert entry_edge.dst == "Processing_sm_start_"

    def test_complex_fixture_no_crash(self):
        """statediagram-complex.mmd renders without crash."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-complex.mmd").read()
        html = to_html(src)
        assert "diagram mermaid-layout" in html

    def test_nested_fixture_no_crash(self):
        """statediagram-nested.mmd renders without crash."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        html = to_html(src)
        assert "diagram mermaid-layout" in html

    def test_nested_fixture_processing_label(self):
        """statediagram-nested.mmd HTML contains the 'Processing' group label."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        html = to_html(src)
        assert "Processing" in html


# ── cross-scope exit waypoint clipping ────────────────────────────────────────

from mermaid_render.layout._strategies import (
    _clip_cross_scope_exit_waypoints,
    _compile_flowchart,
)


class TestCrossScopeExitClip:
    """_clip_cross_scope_exit_waypoints() clips composite-exit routes to the
    source group's bounding-box boundary."""

    BBOX = [100.0, 100.0, 200.0, 200.0]  # [x0, y0, x1, y1]

    def _routed(self, waypoints):
        return [{"edge_id": "e1", "waypoints": list(waypoints)}]

    def test_clips_inside_prefix_to_boundary(self):
        # start inside (150,150); exits through bottom edge (y=200) to (150,250)
        routed = self._routed([(150, 150), (150, 250), (300, 250)])
        _clip_cross_scope_exit_waypoints(routed, {"e1": "g1"}, {"g1": self.BBOX})
        assert routed[0]["waypoints"] == [(150.0, 200.0), (150, 250), (300, 250)]

    def test_drops_multiple_inside_waypoints(self):
        # two waypoints inside the box before the exit crossing
        routed = self._routed([(120, 120), (180, 180), (180, 260), (400, 260)])
        _clip_cross_scope_exit_waypoints(routed, {"e1": "g1"}, {"g1": self.BBOX})
        wps = routed[0]["waypoints"]
        assert wps[0] == (180.0, 200.0)  # crossing of 180,180 -> 180,260 with y=200
        assert wps[1:] == [(180, 260), (400, 260)]

    def test_noop_when_edge_not_tagged(self):
        routed = self._routed([(150, 150), (150, 250)])
        _clip_cross_scope_exit_waypoints(routed, {"other": "g1"}, {"g1": self.BBOX})
        assert routed[0]["waypoints"] == [(150, 150), (150, 250)]

    def test_noop_when_bbox_missing(self):
        routed = self._routed([(150, 150), (150, 250)])
        _clip_cross_scope_exit_waypoints(routed, {"e1": "gX"}, {"g1": self.BBOX})
        assert routed[0]["waypoints"] == [(150, 150), (150, 250)]

    def test_noop_when_first_waypoint_already_outside(self):
        routed = self._routed([(50, 150), (150, 150)])
        _clip_cross_scope_exit_waypoints(routed, {"e1": "g1"}, {"g1": self.BBOX})
        assert routed[0]["waypoints"] == [(50, 150), (150, 150)]

    def test_noop_when_whole_route_inside(self):
        routed = self._routed([(120, 120), (180, 180)])
        _clip_cross_scope_exit_waypoints(routed, {"e1": "g1"}, {"g1": self.BBOX})
        assert routed[0]["waypoints"] == [(120, 120), (180, 180)]

    def test_noop_when_fewer_than_two_waypoints(self):
        routed = self._routed([(150, 150)])
        _clip_cross_scope_exit_waypoints(routed, {"e1": "g1"}, {"g1": self.BBOX})
        assert routed[0]["waypoints"] == [(150, 150)]

    def test_nested_fixture_processing_exit_starts_at_boundary(self):
        """Integration: Processing -> Done route no longer starts inside the
        Processing group box."""
        src = open(REPO_ROOT / "tests" / "fixtures" / "statediagram-nested.mmd").read()
        compiled = _compile_flowchart(src, 0, None)
        layout = compiled.layout
        grp = layout.group_layouts["_g_Processing"]
        b = grp.boundary_bounds
        x0, y0, x1, y1 = b.x, b.y, b.x + b.w, b.y + b.h
        edge = next(
            e for e in layout.routed_edges
            if e.src_node_id == "Processing_sm_end_" and e.dst_node_id == "Done"
        )
        start = edge.waypoints[0]
        strictly_inside = (x0 < start.x < x1) and (y0 < start.y < y1)
        assert not strictly_inside, (
            f"start {start} is inside Processing box [{x0},{y0},{x1},{y1}]"
        )
        # Must lie *on* a box edge (clipped to boundary), not pushed far outside.
        eps = 0.5
        on_edge = (
            (abs(start.x - x0) < eps or abs(start.x - x1) < eps)
            and (y0 - eps) <= start.y <= (y1 + eps)
        ) or (
            (abs(start.y - y0) < eps or abs(start.y - y1) < eps)
            and (x0 - eps) <= start.x <= (x1 + eps)
        )
        assert on_edge, (
            f"start {start} is not on Processing box edge [{x0},{y0},{x1},{y1}]"
        )
