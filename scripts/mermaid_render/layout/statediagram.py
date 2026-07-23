"""Stage 11 — State diagram hierarchical semantics.

Provides an immutable state model and compilation functions. This module is a
semantic IR layer — standalone by design. The production rendering pipeline uses
the pre-existing _parser.py state handling; this module defines the types that
a future compiler can build on. The practical rendering improvements (<<fork>>/
<<join>>/<<choice>>/<<history>> parser fix, bar shape in HTML and SVG) were also
applied to the existing pipeline files.

Pending wiring: compile_state_machine() + state_model_to_graph() should replace
the _parser.py state path as the single authoritative state compiler once the
composite-children recursion is implemented.

Painter shapes per pseudo-state type:
  InitialPseudoState → circle (●)
  FinalPseudoState   → doublecircle (outer ring + inner filled disc)
  Choice             → diamond
  Fork / Join        → bar (horizontal bar)
  History            → circle (H / H*)

Composite algorithm: internal machine compilation via compile_state_machine(),
gate exposure via CompositeState.entry_gate / exit_gate (StateGate objects),
proxy-node expansion via state_model_to_graph() which maps composites to
_Group containers with internal entry/exit proxy nodes.

Deferred: full composite-children recursion in compile_state_machine() —
currently children=() (empty); inner states land in the flat states list.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional, Union


# ── Immutable state model types ────────────────────────────────────────────────

@dataclass(frozen=True)
class AtomicState:
    """A plain, non-decomposable state."""
    id: str
    label: str


@dataclass(frozen=True)
class InitialPseudoState:
    """UML initial pseudo-state: small filled circle (●).

    scope: ID of the enclosing CompositeState, or '' for the top-level machine.
    """
    id: str
    scope: str = ""


@dataclass(frozen=True)
class FinalPseudoState:
    """UML final pseudo-state: double circle (◎).

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

    children:    the inner machine's state nodes (may be empty when the body
                 is not recursively compiled; present when it is).
    transitions: transitions within this composite state.
    entry_gate:  StateGate(kind='entry') for incoming transitions from the parent.
    exit_gate:   StateGate(kind='exit') for outgoing transitions to the parent.
    """
    id: str
    label: str
    children: tuple = ()         # tuple[StateNode, ...]
    transitions: tuple = ()      # tuple[StateTransition, ...]
    entry_gate: Optional[StateGate] = None
    exit_gate: Optional[StateGate] = None


@dataclass(frozen=True)
class StateMachineModel:
    """Compiled, immutable IR for a complete state machine diagram."""
    states: tuple        # tuple[StateNode, ...]
    transitions: tuple   # tuple[StateTransition, ...]
    notes: tuple = ()    # tuple[StateNote, ...]


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


def compile_state_machine(lines: list[str]) -> StateMachineModel:
    """Compile state diagram source lines into an immutable StateMachineModel.

    Handles:
    - Atomic states referenced in transitions
    - Initial/final pseudo-states ([*] markers, scoped per composite)
    - Composite states (state X { ... }) with entry/exit gates
    - Pseudo-state type annotations (state X <<fork|join|choice|history|historydeep>>)
    - State aliases (state "Label" as id)
    - State descriptions (id : label)
    - Transitions (A --> B : label)
    - Notes (single-line and multi-line block)
    - Concurrent region separators (-- ignored)
    - Direction overrides (ignored)
    """
    states: list[StateNode] = []
    transitions: list[StateTransition] = []
    notes: list[StateNote] = []

    _known: dict[str, StateNode] = {}
    _scope_stack: list[str] = []  # stack of composite state IDs
    _note_block: Optional[dict] = None

    def _scope() -> str:
        return _scope_stack[-1] if _scope_stack else ""

    def _register(node: StateNode) -> StateNode:
        nid = node.id  # type: ignore[union-attr]
        if nid not in _known:
            _known[nid] = node
            states.append(node)
        return _known[nid]

    def _ensure(sid: str, label: str = "", shape: str = "atomic") -> StateNode:
        if sid in _known:
            return _known[sid]
        shape_l = shape.lower()
        node: StateNode
        if shape_l == "fork":
            node = Fork(id=sid, label=label or sid)
        elif shape_l == "join":
            node = Join(id=sid, label=label or sid)
        elif shape_l == "choice":
            node = Choice(id=sid, label=label or sid)
        elif shape_l in ("history", "historydeep"):
            node = History(id=sid, kind="deep" if shape_l == "historydeep" else "shallow",
                           scope=_scope())
        elif sid.endswith("_sm_start_"):
            sc = sid[:-len("_sm_start_")].rstrip("_") if sid != "_sm_start_" else ""
            node = InitialPseudoState(id=sid, scope=sc)
        elif sid.endswith("_sm_end_"):
            sc = sid[:-len("_sm_end_")].rstrip("_") if sid != "_sm_end_" else ""
            node = FinalPseudoState(id=sid, scope=sc)
        else:
            node = AtomicState(id=sid, label=label or sid)
        return _register(node)

    def _process_transition(src_id: str, dst_id: str, lbl: str) -> None:
        # [*] substitution has already been applied by the caller's regex subs.
        src = src_id.strip()
        dst = dst_id.strip()
        # Extract colon label from dst if not yet parsed
        if not lbl and " : " in dst:
            dst, lbl = dst.split(" : ", 1)
            dst = dst.strip()
            lbl = lbl.strip()
        _ensure(src)
        _ensure(dst)
        transitions.append(StateTransition(src_id=src, dst_id=dst, label=lbl.strip()))

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue

        # Multi-line note block: collect until 'end note'
        if _note_block is not None:
            if line.lower() == "end note":
                notes.append(StateNote(
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
            if _scope_stack:
                _scope_stack.pop()
            continue

        # Direction override (ignored for semantics)
        if _DIR_RE.match(line):
            continue

        # Concurrent region separator
        if line == "--":
            continue

        # Note single-line: note right of X : text
        m = _NOTE_INLINE_RE.match(line)
        if m:
            notes.append(StateNote(
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
            _ensure(m.group(2), m.group(1))
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
            if cs_id not in _known:
                entry = StateGate(id=_initial_id(cs_id), kind="entry", composite_id=cs_id)
                exit_ = StateGate(id=_final_id(cs_id), kind="exit", composite_id=cs_id)
                node = CompositeState(id=cs_id, label=cs_id,
                                      entry_gate=entry, exit_gate=exit_)
                _register(node)
            _scope_stack.append(cs_id)
            continue

        # State description: id : label (no edge operator, no URL)
        if "--" not in line and not line.startswith("http"):
            m = _DESC_RE.match(line)
            if m:
                _ensure(m.group(1), m.group(2).strip())
                continue

        # [*] substitution before transition parsing
        sc = _scope()
        sm_s = _initial_id(sc)
        sm_e = _final_id(sc)
        proc = re.sub(r'^\[\*\]\s*(?=-->)', sm_s + " ", line).strip()
        proc = re.sub(r'(?<=-->)\s*\[\*\]', f" {sm_e}", proc)

        # Transition: A --> B  or  A --> B : label
        m = _TRANSITION_RE.match(proc)
        if m:
            src_raw = m.group(1).strip()
            rest = m.group(2).strip()
            # Extract label after colon in destination
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

    return StateMachineModel(
        states=tuple(states),
        transitions=tuple(transitions),
        notes=tuple(notes),
    )


# ── Conversion: StateMachineModel → legacy graph format ───────────────────────

def state_model_to_graph(
    model: StateMachineModel,
) -> "tuple[dict, list, dict]":
    """Convert StateMachineModel to (_Node, _Edge, _Group) for the layout pipeline.

    Painter shapes per pseudo-state kind:
      InitialPseudoState → circle, label '●'
      FinalPseudoState   → doublecircle, label ''
      Choice             → diamond
      Fork               → bar, css_class 'state-fork'
      Join               → bar, css_class 'state-join'
      History (shallow)  → circle, label 'H', css_class 'state-history'
      History (deep)     → circle, label 'H*', css_class 'state-history'
      CompositeState     → _Group container (entry/exit gates as circle nodes inside)
      AtomicState        → rect
    """
    from ._constants import _Node, _Edge, _Group  # avoid circular at module level

    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    groups: dict[str, _Group] = {}

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
            pass  # gates are conceptual; rendered via CompositeState proxy nodes
        elif isinstance(state, CompositeState):
            gid = f"_g_{state.id}"
            groups[gid] = _Group(id=gid, label=state.label, members=[], parent_group=parent_gid)
            # Expose entry and exit gates as proxy nodes inside the group
            if state.entry_gate:
                _add(state.entry_gate.id, "●", "circle", "", gid)
            if state.exit_gate:
                _add(state.exit_gate.id, "", "doublecircle", "", gid)
            for child in state.children:
                _emit(child, gid)

    for s in model.states:
        _emit(s, None)

    for tr in model.transitions:
        src, dst = tr.src_id, tr.dst_id
        if src not in nodes:
            nodes[src] = _Node(id=src, label=src, shape="rect")
        if dst not in nodes:
            nodes[dst] = _Node(id=dst, label=dst, shape="rect")
        edges.append(_Edge(src=src, dst=dst, label=tr.label, arrow=True))

    return nodes, edges, groups
