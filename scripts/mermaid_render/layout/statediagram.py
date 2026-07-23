"""Stage 11 — State diagram hierarchical semantics.

Provides an immutable state model and compilation functions. This module is the
authoritative state diagram compiler. compile_state_machine() + state_model_to_graph()
replace the _parser.py state path for stateDiagram / stateDiagram-v2.

Painter shapes per pseudo-state type:
  InitialPseudoState → circle (CSS filled disc, not Unicode glyph)
  FinalPseudoState   → doublecircle (outer ring + inner filled disc)
  Choice             → diamond
  Fork / Join        → bar (horizontal bar)
  History            → circle (H / H*)

Composite algorithm: two-pass parse (pass 1: collect composite IDs;
pass 2: accumulate per-scope states/transitions, assemble CompositeState on '}'.
Cross-scope transitions carry src_group so the renderer clips the SVG path
to the group boundary rather than starting from the internal final pseudo-state.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional, Union


# ── Immutable state model types ────────────────────────────────────────────────

@dataclass(frozen=True)
class AtomicState:
    """A plain, non-decomposable state."""
    id: str
    label: str


@dataclass(frozen=True)
class InitialPseudoState:
    """UML initial pseudo-state: small filled circle (CSS disc, no text).

    scope: ID of the enclosing CompositeState, or '' for the top-level machine.
    """
    id: str
    scope: str = ""


@dataclass(frozen=True)
class FinalPseudoState:
    """UML final pseudo-state: double circle (outer ring + inner filled disc).

    scope: ID of the enclosing CompositeState, or '' for the top-level machine.
    """
    id: str
    scope: str = ""


@dataclass(frozen=True)
class Choice:
    """UML choice pseudo-state: diamond shape."""
    id: str
    label: str = ""


@dataclass(frozen=True)
class Fork:
    """UML fork pseudo-state: horizontal bar shape (splits control flow)."""
    id: str
    label: str = ""


@dataclass(frozen=True)
class Join:
    """UML join pseudo-state: horizontal bar shape (merges control flow)."""
    id: str
    label: str = ""


@dataclass(frozen=True)
class History:
    """UML history pseudo-state: circle with H label.

    kind: 'shallow' for H (remembers one level) or 'deep' for H* (all levels).
    scope: ID of the enclosing CompositeState.
    """
    id: str
    kind: Literal["shallow", "deep"] = "shallow"
    scope: str = ""


@dataclass(frozen=True)
class StateGate:
    """Boundary gate on a composite state: the conceptual entry or exit point.

    Gates are not rendered as standalone nodes; they act as anchors for
    transitions crossing a composite boundary. state_model_to_graph() maps
    them to the scoped _sm_start_ / _sm_end_ proxy nodes.
    """
    id: str
    kind: Literal["entry", "exit"]
    composite_id: str


@dataclass(frozen=True)
class StateTransition:
    """A directed transition between two state IDs, optionally labeled/guarded."""
    src_id: str
    dst_id: str
    label: str = ""
    guard: str = ""


@dataclass(frozen=True)
class StateNote:
    """A textual annotation attached to a state node."""
    target_id: str
    position: Literal["right", "left"] = "right"
    text: str = ""


# StateNode is the union of all node types; forward-ref for CompositeState.
StateNode = Union[
    AtomicState,
    "CompositeState",
    InitialPseudoState,
    FinalPseudoState,
    Choice,
    Fork,
    Join,
    History,
    StateGate,
]


@dataclass(frozen=True)
class CompositeState:
    """A composite state enclosing an inner state machine.

    children:        the inner machine's state nodes (populated by compile_state_machine).
    transitions:     transitions within this composite state.
    entry_gate:      StateGate(kind='entry') for incoming transitions from the parent.
    exit_gate:       StateGate(kind='exit') for outgoing transitions to the parent.
    local_direction: direction directive inside the composite body ('LR', 'TB', etc.).
    """
    id: str
    label: str
    children: tuple = ()         # tuple[StateNode, ...]
    transitions: tuple = ()      # tuple[StateTransition, ...]
    entry_gate: Optional[StateGate] = None
    exit_gate: Optional[StateGate] = None
    local_direction: str = ""


@dataclass(frozen=True)
class StateMachineModel:
    """Compiled, immutable IR for a complete state machine diagram."""
    states: tuple        # tuple[StateNode, ...]
    transitions: tuple   # tuple[StateTransition, ...]
    notes: tuple = ()    # tuple[StateNote, ...]
    direction: str = ""  # top-level direction directive ('LR', 'TB', etc.)


# ── Parser: source → StateMachineModel ────────────────────────────────────────

_ALIAS_RE = re.compile(r'^state\s+"([^"]+)"\s+as\s+(\w+)', re.I)
_PSEUDO_RE = re.compile(r'^state\s+(\w+)\s+<<(\w+)>>', re.I)
_COMPOSITE_RE = re.compile(r'^state\s+(\w+)\s*\{')
_DESC_RE = re.compile(r'^([A-Za-z_]\w*)\s*:\s*(\S.*)$')
_NOTE_INLINE_RE = re.compile(r'^note\s+(right|left)\s+of\s+(\w+)\s*:\s*(.+)', re.I)
_NOTE_OPEN_RE = re.compile(r'^note\s+(right|left)\s+of\s+(\w+)\s*$', re.I)
_TRANSITION_RE = re.compile(r'^(.+?)\s*-->\s*(.+)$')
_DIR_RE = re.compile(r'^direction\s+(LR|RL|TB|TD)\s*$', re.I)


def _initial_id(scope: str) -> str:
    return f"{scope}_sm_start_" if scope else "_sm_start_"


def _final_id(scope: str) -> str:
    return f"{scope}_sm_end_" if scope else "_sm_end_"


def _collect_composite_ids(lines: list[str]) -> set[str]:
    """Pass 1: collect all composite state IDs (state X { pattern)."""
    result: set[str] = set()
    for raw in lines:
        m = _COMPOSITE_RE.match(raw.strip())
        if m:
            result.add(m.group(1))
    return result


def compile_state_machine(lines: list[str]) -> StateMachineModel:
    """Compile state diagram source lines into an immutable StateMachineModel.

    Two-pass compilation:
    - Pass 1 identifies composite state IDs so transitions referencing a composite
      before its body is defined don't create spurious AtomicState objects.
    - Pass 2 uses a scope stack (scope_id, local_states, local_transitions) to
      accumulate per-scope nodes and transitions. On '}', the CompositeState is
      assembled with children=tuple(local_states) and appended to the parent scope.

    Cross-scope transitions (e.g. top-level Processing --> Done) remain in the
    top-level transitions tuple; state_model_to_graph() routes them to the correct
    internal anchor nodes.
    """
    _composite_ids: set[str] = _collect_composite_ids(lines)

    # Stack of (scope_id, local_states, local_transitions, local_notes)
    # Index 0 = global scope ("" scope_id)
    _stack: list[tuple[str, list, list, list]] = [("", [], [], [])]
    _known: dict[str, StateNode] = {}   # id → registered node (global registry)
    _labels: dict[str, str] = {}        # id → display label (from alias/desc)
    _directions: dict[str, str] = {}    # scope_id → direction directive
    _note_block: Optional[dict] = None

    def _cur_scope() -> str:
        return _stack[-1][0]

    def _cur_states() -> list:
        return _stack[-1][1]

    def _cur_transitions() -> list:
        return _stack[-1][2]

    def _cur_notes() -> list:
        return _stack[-1][3]

    def _add_to_cur_scope(node: StateNode) -> None:
        nid: str = node.id  # type: ignore[union-attr]
        _known[nid] = node
        _cur_states().append(node)

    def _ensure(sid: str, label: str = "", shape: str = "atomic") -> Optional[StateNode]:
        """Register a state node in the current scope (if not already known).

        Returns None for composite IDs not yet assembled (will be added by '}').
        """
        if sid in _known:
            if label and label != sid:
                _labels[sid] = label
            return _known[sid]

        # Composite IDs are assembled on '}'; skip AtomicState creation for them.
        if sid in _composite_ids and shape == "atomic":
            if label and label != sid:
                _labels[sid] = label
            return None

        shape_l = shape.lower()
        node: StateNode
        sc = _cur_scope()
        if shape_l == "fork":
            node = Fork(id=sid, label=label or sid)
        elif shape_l == "join":
            node = Join(id=sid, label=label or sid)
        elif shape_l == "choice":
            node = Choice(id=sid, label=label or sid)
        elif shape_l in ("history", "historydeep"):
            node = History(id=sid,
                           kind="deep" if shape_l == "historydeep" else "shallow",
                           scope=sc)
        elif sid.endswith("_sm_start_"):
            scope_part = sid[:-len("_sm_start_")].rstrip("_") if sid != "_sm_start_" else ""
            node = InitialPseudoState(id=sid, scope=scope_part)
        elif sid.endswith("_sm_end_"):
            scope_part = sid[:-len("_sm_end_")].rstrip("_") if sid != "_sm_end_" else ""
            node = FinalPseudoState(id=sid, scope=scope_part)
        else:
            node = AtomicState(id=sid, label=label or sid)

        _add_to_cur_scope(node)
        return node

    def _process_transition(src_id: str, dst_id: str, lbl: str) -> None:
        _ensure(src_id)
        _ensure(dst_id)
        _cur_transitions().append(
            StateTransition(src_id=src_id, dst_id=dst_id, label=lbl.strip())
        )

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue

        # Multi-line note block: collect until 'end note'
        if _note_block is not None:
            if line.lower() == "end note":
                _cur_notes().append(StateNote(
                    target_id=_note_block["target"],
                    position=_note_block["pos"],
                    text=" ".join(_note_block["lines"]),
                ))
                _note_block = None
            else:
                _note_block["lines"].append(line)
            continue

        # Closing composite brace
        if line == "}":
            if len(_stack) > 1:
                cs_id, cs_states, cs_transitions, cs_notes = _stack.pop()
                entry = StateGate(id=_initial_id(cs_id), kind="entry",
                                  composite_id=cs_id)
                exit_ = StateGate(id=_final_id(cs_id), kind="exit",
                                  composite_id=cs_id)
                cs = CompositeState(
                    id=cs_id,
                    label=_labels.get(cs_id, cs_id),
                    children=tuple(cs_states),
                    transitions=tuple(cs_transitions),
                    entry_gate=entry,
                    exit_gate=exit_,
                    local_direction=_directions.get(cs_id, ""),
                )
                _known[cs_id] = cs
                _cur_states().append(cs)
                # Bubble composite-scoped notes to the parent scope so they render.
                _cur_notes().extend(cs_notes)
            continue

        # Direction override: store per scope
        m = _DIR_RE.match(line)
        if m:
            sc = _cur_scope()
            if sc:
                _directions[sc] = m.group(1).upper()
            else:
                _directions[""] = m.group(1).upper()
            continue

        # Concurrent region separator (ignored for semantics)
        if line == "--":
            continue

        # Note single-line: note right of X : text
        m = _NOTE_INLINE_RE.match(line)
        if m:
            _cur_notes().append(StateNote(
                target_id=m.group(2),
                position=m.group(1).lower(),
                text=m.group(3).strip(),
            ))
            continue

        # Note block open: note right of X
        m = _NOTE_OPEN_RE.match(line)
        if m:
            _note_block = {"pos": m.group(1).lower(), "target": m.group(2), "lines": []}
            continue

        # State alias: state "Label" as id
        m = _ALIAS_RE.match(line)
        if m:
            lbl, sid = m.group(1), m.group(2)
            _labels[sid] = lbl
            if sid not in _composite_ids:
                _ensure(sid, lbl)
            continue

        # Pseudo-state type annotation: state X <<type>>
        m = _PSEUDO_RE.match(line)
        if m:
            _ensure(m.group(1), m.group(1), m.group(2))
            continue

        # Composite state open: state X {
        m = _COMPOSITE_RE.match(line)
        if m:
            cs_id = m.group(1)
            _stack.append((cs_id, [], [], []))
            continue

        # State description: id : label (no edge operator)
        if "--" not in line and not line.startswith("http"):
            m = _DESC_RE.match(line)
            if m:
                sid, lbl = m.group(1), m.group(2).strip()
                _labels[sid] = lbl
                if sid not in _composite_ids:
                    _ensure(sid, lbl)
                continue

        # [*] substitution before transition parsing
        sc = _cur_scope()
        sm_s = _initial_id(sc)
        sm_e = _final_id(sc)
        proc = re.sub(r'^\[\*\]\s*(?=-->)', sm_s + " ", line).strip()
        proc = re.sub(r'(?<=-->)\s*\[\*\]', f" {sm_e}", proc)

        # Transition: A --> B  or  A --> B : label
        m = _TRANSITION_RE.match(proc)
        if m:
            src_raw = m.group(1).strip()
            rest = m.group(2).strip()
            if " : " in rest:
                dst_raw, lbl = rest.split(" : ", 1)
            elif rest.endswith(":"):
                dst_raw, lbl = rest[:-1].strip(), ""
            else:
                dst_raw, lbl = rest, ""
            _process_transition(src_raw, dst_raw.strip(), lbl.strip())
            continue

        # Standalone node declaration (fallback)
        if re.match(r'^[A-Za-z_]\w*\s*$', proc):
            _ensure(proc.strip())

    # Flatten global scope
    global_states, global_transitions, global_notes = _stack[0][1], _stack[0][2], _stack[0][3]
    top_direction = _directions.get("", "")

    return StateMachineModel(
        states=tuple(global_states),
        transitions=tuple(global_transitions),
        notes=tuple(global_notes),
        direction=top_direction,
    )


# ── Conversion: StateMachineModel → legacy graph format ───────────────────────

def _all_composite_ids(model: StateMachineModel) -> set[str]:
    """Collect all CompositeState IDs in the model (top-level states only)."""
    result: set[str] = set()
    for s in model.states:
        if isinstance(s, CompositeState):
            result.add(s.id)
    return result


def _find_member(cs: CompositeState, prefer_end: bool) -> Optional[str]:
    """Find the first/last non-pseudo member of a composite for entry/exit fallback."""
    candidates = [
        s.id for s in cs.children  # type: ignore[union-attr]
        if hasattr(s, 'id') and not isinstance(s, (StateGate,))
    ]
    if not candidates:
        return None
    return candidates[-1] if prefer_end else candidates[0]


def state_model_to_graph(
    model: StateMachineModel,
) -> "tuple[dict, list, dict]":
    """Convert StateMachineModel to (_Node, _Edge, _Group) for the layout pipeline.

    Cross-scope exit transitions (composite → external) are emitted with:
      edge.src = {composite_id}_sm_end_  (internal final state, for layout routing)
      edge.src_group = _g_{composite_id} (tells renderer to clip to group boundary)

    Cross-scope entry transitions (external → composite) target the internal
    initial pseudo-state directly (the arrow enters through the composite box).

    Painter shapes per pseudo-state kind:
      InitialPseudoState → circle, label '●'  (rendered as CSS disc via src_group nid check)
      FinalPseudoState   → doublecircle, label ''
      Choice             → diamond
      Fork               → bar, css_class 'state-fork'
      Join               → bar, css_class 'state-join'
      History (shallow)  → circle, label 'H', css_class 'state-history'
      History (deep)     → circle, label 'H*', css_class 'state-history'
      CompositeState     → _Group container; children emitted recursively
      AtomicState        → rect
    """
    from ._constants import _Node, _Edge, _Group  # avoid circular at module level

    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    groups: dict[str, _Group] = {}

    _composite_ids: set[str] = _all_composite_ids(model)
    # Map composite_id → group_id for cross-scope transition routing
    _cs_to_group: dict[str, str] = {}

    def _add(sid: str, label: str, shape: str, css_class: str = "",
             group: Optional[str] = None) -> None:
        if sid not in nodes:
            nodes[sid] = _Node(id=sid, label=label, shape=shape, css_class=css_class)
        if group is not None:
            nodes[sid].group = group
            if group in groups and sid not in groups[group].members:
                groups[group].members.append(sid)

    def _emit(state: StateNode, parent_gid: Optional[str] = None) -> None:
        if isinstance(state, AtomicState):
            _add(state.id, state.label, "rect", "", parent_gid)
        elif isinstance(state, InitialPseudoState):
            _add(state.id, "●", "circle", "", parent_gid)
        elif isinstance(state, FinalPseudoState):
            _add(state.id, "", "doublecircle", "", parent_gid)
        elif isinstance(state, Choice):
            _add(state.id, state.label or state.id, "diamond", "state-choice", parent_gid)
        elif isinstance(state, Fork):
            _add(state.id, state.label or state.id, "bar", "state-fork", parent_gid)
        elif isinstance(state, Join):
            _add(state.id, state.label or state.id, "bar", "state-join", parent_gid)
        elif isinstance(state, History):
            hlabel = "H*" if state.kind == "deep" else "H"
            _add(state.id, hlabel, "circle", "state-history", parent_gid)
        elif isinstance(state, StateGate):
            pass  # gates are conceptual; exposed via CompositeState proxy nodes
        elif isinstance(state, CompositeState):
            gid = f"_g_{state.id}"
            _cs_to_group[state.id] = gid
            groups[gid] = _Group(
                id=gid, label=state.label, members=[],
                parent_group=parent_gid,
                direction=state.local_direction,
            )
            # Recursively emit children into the group
            for child in state.children:
                _emit(child, gid)
            # Emit internal transitions as edges within the group.
            # Endpoints should already be nodes from child _emit; create fallback
            # as plain rect if somehow missing (e.g. cross-composite ref).
            for tr in state.transitions:
                src, dst = tr.src_id, tr.dst_id
                if src not in nodes:
                    nodes[src] = _Node(id=src, label=src, shape="rect")
                if dst not in nodes:
                    nodes[dst] = _Node(id=dst, label=dst, shape="rect")
                edges.append(_Edge(src=src, dst=dst, label=tr.label, arrow=True))

    for s in model.states:
        _emit(s, None)

    # Assign stable edge IDs for deduplication (mirrors _parse_graph_source logic)
    _id_counts: dict[str, int] = {}

    def _make_edge(src: str, dst: str, label: str,
                   src_group: Optional[str] = None) -> None:
        # Ensure both endpoints exist as nodes
        if src not in nodes:
            nodes[src] = _Node(id=src, label=src, shape="rect")
        if dst not in nodes:
            nodes[dst] = _Node(id=dst, label=dst, shape="rect")
        _base = f"{src}->{dst}"
        _n = _id_counts.get(_base, 0)
        _id_counts[_base] = _n + 1
        eid = _base if _n == 0 else f"{_base}#{_n}"
        e = _Edge(src=src, dst=dst, label=label, arrow=True, edge_id=eid)
        if src_group is not None:
            e.src_group = src_group  # type: ignore[attr-defined]
        edges.append(e)

    for tr in model.transitions:
        src, dst = tr.src_id, tr.dst_id

        # Determine effective src: composite exit → route via internal final state
        effective_src = src
        sg: Optional[str] = None
        if src in _composite_ids:
            cs_obj = next((s for s in model.states
                          if isinstance(s, CompositeState) and s.id == src), None)
            if cs_obj is not None:
                gid = _cs_to_group.get(src)
                # Prefer the scoped final state; fall back to last child
                exit_id = _final_id(src)
                if exit_id in nodes:
                    effective_src = exit_id
                else:
                    fb = _find_member(cs_obj, prefer_end=True)
                    if fb:
                        effective_src = fb
                if gid:
                    sg = gid

        # Determine effective dst: composite entry → route via internal initial state
        effective_dst = dst
        if dst in _composite_ids:
            entry_id = _initial_id(dst)
            if entry_id in nodes:
                effective_dst = entry_id
            else:
                cs_obj2 = next((s for s in model.states
                               if isinstance(s, CompositeState) and s.id == dst), None)
                if cs_obj2 is not None:
                    fb2 = _find_member(cs_obj2, prefer_end=False)
                    if fb2:
                        effective_dst = fb2

        _make_edge(effective_src, effective_dst, tr.label, src_group=sg)

    # Emit notes as rect nodes with dotted edges (mirrors _parse_graph_source note logic)
    _note_counter = 0
    for note in model.notes:
        _nid = f"_note_{_note_counter}"
        _note_counter += 1
        nodes[_nid] = _Node(id=_nid, label=note.text, shape="rect", css_class="state-note")
        if note.target_id not in nodes:
            nodes[note.target_id] = _Node(id=note.target_id, label=note.target_id, shape="rect")
        edges.append(_Edge(src=note.target_id, dst=_nid, label="", style="dotted", arrow=False))

    # Assign stable edge IDs to internal (composite-transition) edges added by _emit
    for _e in edges:
        if not _e.edge_id:
            _base = f"{_e.src}->{_e.dst}"
            _n = _id_counts.get(_base, 0)
            _id_counts[_base] = _n + 1
            _e.edge_id = _base if _n == 0 else f"{_base}#{_n}"

    return nodes, edges, groups
