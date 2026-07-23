# Implementation Plan — State diagram local cycle routing

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_geometry.py` (RoutedEdge + FinalizedLayout), `scripts/mermaid_render/layout/_constants.py` (_Edge), `scripts/mermaid_render/layout/statediagram.py` (state_model_to_graph + gate population), `scripts/mermaid_render/layout/_strategies.py` (_compile_flowchart wiring + boundary enforcement), `scripts/mermaid_render/layout/_routing.py` (scope-aware cycle routing helper), `tests/test_state_model.py`, `tests/test_fix_state.py`, `tests/test_state_cycle_routing.py` (new).
2. Done when: `pytest tests/` passes with zero failures; both `statediagram-complex.mmd` and `statediagram-nested.mmd` produce `RoutedEdge` instances with populated semantic/routing fields and no validation errors; AC5–AC7 proximity assertions pass in `test_fix_state.py`.
3. Not changing: `compile_state_machine()` is the authoritative compiler and must not be replaced; the ELK path is untouched (state diagrams fall back to Python); `_clip_cross_scope_exit_waypoints()` is extended, not replaced.

**Declined patterns:**
- Adding a new separate compiler for state diagrams — `compile_state_machine()` already handles the recursive IR; new fields belong in its output bridge (`state_model_to_graph`), not a parallel code path.
- Storing semantic/routing fields only as `RoutedEdge` metadata strings without typed default values — omitting defaults would break all non-state-diagram callers that construct `RoutedEdge` directly.
- Using `dst_group` on `_Edge` to clip composite-entry endpoints — no consumer today and the entry clipping scope is out of spec; adding it now would dead-code and clutter `_Edge`.
- Global canvas perimeter as fallback for all back-edges — the spec explicitly requires scope-bounded perimeters; the global fallback is only acceptable if no scope information is available.
- Expressing composite gates purely through in-code comments or dynamic `getattr` lookups — they must be an explicit typed field on `FinalizedLayout` so the oracle adapter can read them without internal knowledge.

---

## Tasks

### Task 1: Extend `_Edge` with semantic/routing/scope fields
Depends on: none
Verification: TDD

**Tests (`tests/test_state_model.py`):**
- `_Edge` construction with no new keyword arguments still works (all new fields default to `None`/`""`).
- `_Edge` with explicit `semantic_src="Processing"`, `source_scope="Processing"` round-trips through `dataclass` equality.

**Approach:**
- In `scripts/mermaid_render/layout/_constants.py`, add six optional `str` fields to `_Edge` (after the existing `src_group` field):
  - `semantic_src: Optional[str] = None`
  - `semantic_dst: Optional[str] = None`
  - `routing_src: Optional[str] = None`
  - `routing_dst: Optional[str] = None`
  - `source_scope: str = ""`
  - `target_scope: str = ""`
- `_Edge` is a plain `@dataclass` (not frozen), so append fields with defaults; no existing construction sites break.
- `src_group` already exists; the new fields sit alongside it as state-diagram-only metadata.

---

### Task 2: Populate semantic/routing/scope fields in `state_model_to_graph()`
Depends on: Task 1
Verification: TDD

**Tests (`tests/test_state_model.py`):**
- For `Processing --> Done` (nested fixture): returned `_Edge` has `semantic_src="Processing"`, `routing_src="Processing_sm_end_"`, `semantic_dst="Done"`, `routing_dst="Done"`, `source_scope="Processing"`, `target_scope=""`.
- For `Validating --> Executing` (internal to Processing): `source_scope="Processing"`, `target_scope="Processing"`, `semantic_src="Validating"`, `routing_src="Validating"`.
- Scoped pseudo-state ID collision: constructing two composites whose scoped `_sm_start_` would share an ID raises `ValueError` (synthetic fixture).

**Approach:**
- In `scripts/mermaid_render/layout/statediagram.py`, in `state_model_to_graph()`, after the existing `_Edge` construction for each `StateTransition`:
  - Determine `source_scope` and `target_scope` from the compiled `StateMachineModel` node registry (walk `CompositeState.children` recursively to find each node's parent composite).
  - Set `semantic_src` / `semantic_dst` to the raw transition endpoint IDs (always the semantic names, even when the transition was emitted at composite level).
  - Set `routing_src` / `routing_dst` to the actual graph node IDs used for layout (e.g. `Processing_sm_end_` for a composite-exit edge; the semantic ID itself for all other edges).
  - Add a uniqueness assertion over all scoped pseudo-state IDs before returning.
- Build a `{node_id: parent_composite_id}` index at the start of `state_model_to_graph()` by walking the compiled model recursively; reuse for scope lookups.

---

### Task 3: Extend `RoutedEdge` and wire through `_build_routed_edges_ir()`
Depends on: Task 1
Verification: TDD

**Tests (`tests/test_state_model.py`):**
- `RoutedEdge` construction with no new keyword arguments still works (all new fields default to `""`).
- `_build_routed_edges_ir()` propagates `semantic_source_id` from the route dict's `"edge"` `_Edge` object when present.

**Approach:**
- In `scripts/mermaid_render/layout/_geometry.py`, add six `str` fields to `RoutedEdge` with `""` defaults (after `route_diagnostics`):
  - `semantic_source_id: str = ""`
  - `semantic_target_id: str = ""`
  - `routing_source_id: str = ""`
  - `routing_target_id: str = ""`
  - `source_scope: str = ""`
  - `target_scope: str = ""`
- `RoutedEdge` is `@dataclass(frozen=True)`, so new fields with defaults append cleanly.
- In `scripts/mermaid_render/layout/_strategies.py`, in `_build_routed_edges_ir()`, for each route dict, extract `edge._Edge` and copy the six new fields into the `RoutedEdge` constructor call.

---

### Task 4: Add explicit composite gates to `FinalizedLayout`
Depends on: Task 3
Verification: TDD

**Tests (`tests/test_state_model.py`):**
- `compile_and_finalize("statediagram-nested.mmd content")` returns `FinalizedLayout` with `composite_gates["Processing"] == ("Processing_sm_start_", "Processing_sm_end_")`.
- `FinalizedLayout` constructed without `composite_gates` keyword still works (empty `MappingProxyType` default).

**Approach:**
- In `scripts/mermaid_render/layout/_geometry.py`, add `composite_gates: MappingProxyType = field(default_factory=MappingProxyType)` to `FinalizedLayout`. Wrap in `__post_init__` as with `node_layouts`.
- In `scripts/mermaid_render/layout/_strategies.py`, in `_compile_flowchart()`, after the existing state diagram compiler branch, extract gates from the `StateMachineModel`: walk `_sm_model` to collect `{composite_id: (entry_gate_id, exit_gate_id)}`, then pass to `FinalizedLayout(composite_gates=MappingProxyType(...))`.
- Gate IDs come from `CompositeState.entry_gate.id` / `CompositeState.exit_gate.id` (already populated by `compile_state_machine()`).

---

### Task 5: Scope-aware local cycle routing
Depends on: Task 2
Verification: TDD

**Tests (`tests/test_state_cycle_routing.py` — new file):**
- `_route_local_cycle(src_bbox, dst_bbox, scope_bbox, direction)` returns waypoints that stay within `scope_bbox` expanded by at most `2 * NODE_W`.
- Back-edge between two nodes with no scope constraint falls back to a perimeter around just the src+dst bounding box union.
- Waypoints are ordered correctly (start at src, end at dst) with no degenerate zero-length segments.

**Approach:**
- In `scripts/mermaid_render/layout/_routing.py`, add `_route_local_cycle(src_bbox, dst_bbox, scope_bbox, direction)` that:
  1. Computes the tightest bounding box around `src_bbox ∪ dst_bbox` extended by `NODE_W` margin (the "local perimeter").
  2. Clips to `scope_bbox` if provided and non-empty (so `Failed --> Idle` wraps the outer composite, not the canvas).
  3. Routes the back-edge as a three-segment polyline around the local perimeter (exit from src bottom/left, traverse the perimeter, enter dst top/right).
- In `scripts/mermaid_render/layout/_strategies.py`, in `_compile_flowchart()`, after `_route_edges()` and before `_clip_cross_scope_exit_waypoints()`, post-process edges whose `source_scope == target_scope` and `reversed_ == True` (back-edges) by replacing their waypoints with the output of `_route_local_cycle()`, using the node bboxes from `nodes` and the group bbox from `_grp_bboxes` for the scope constraint.
- For the outer-machine back-edges (e.g. `Failed --> Idle` in `statediagram-nested.mmd`), `scope_bbox` is the canvas bounding box of all top-level nodes (not the full canvas with padding).

---

### Task 6: Prevent internal transitions from crossing their composite boundary
Depends on: Task 5
Verification: TDD

**Tests (`tests/test_state_cycle_routing.py`):**
- Given a routed dict for an internal edge whose waypoints extend beyond the group bbox, `_clip_internal_edge_waypoints(route, group_bbox)` truncates the route to stay inside the box.
- Route already inside the box is returned unchanged.

**Approach:**
- In `scripts/mermaid_render/layout/_strategies.py`, add `_clip_internal_edge_waypoints(routed, internal_edge_ids, grp_bboxes)` (analogous in structure to `_clip_cross_scope_exit_waypoints()`).
- An edge is "internal" when both `_Edge.source_scope` and `_Edge.target_scope` equal the same composite ID and that ID is in `grp_bboxes`.
- Clip any waypoint outside the group bbox back to the nearest boundary point.
- Call immediately after `_clip_cross_scope_exit_waypoints()` in `_compile_flowchart()`.

---

### Task 7: Prevent cross-scope edges from passing through the composite title
Depends on: Task 6
Verification: TDD

**Tests (`tests/test_state_cycle_routing.py`):**
- `_detour_around_title(waypoints, title_rect)` re-routes a polyline that would enter `title_rect` to pass below it.
- Polyline that never enters `title_rect` is returned unchanged.

**Approach:**
- In `scripts/mermaid_render/layout/_strategies.py`, add `_detour_around_title(waypoints, title_rect)` that detects the first segment intersecting `title_rect` and inserts a detour point at `title_rect.bottom + TITLE_PAD`.
- `title_rect` for a group is `Rect(x=grp_x, y=grp_y, w=grp_w, h=TITLE_HEIGHT)` where `TITLE_HEIGHT` is the group label height constant from `_constants.py`.
- Apply to all edges where `_Edge.source_scope != _Edge.target_scope` (cross-scope) and whose source or destination has a corresponding group in `_grp_bboxes`.
- Call in `_compile_flowchart()` after `_clip_internal_edge_waypoints()`.

---

### Task 8: Label attachment to clear route segments
Depends on: Task 5
Verification: TDD

**Tests (`tests/test_state_cycle_routing.py`):**
- `_pick_label_anchor(waypoints, node_bboxes)` returns a point that is not inside any bbox in `node_bboxes`.
- With all segments obstructed, returns the midpoint of the longest segment (best-effort fallback).

**Approach:**
- In `scripts/mermaid_render/layout/_routing.py`, add `_pick_label_anchor(waypoints, node_bboxes)` that iterates segments from longest to shortest and returns the midpoint of the first segment whose midpoint falls outside all `node_bboxes`.
- In `_build_routed_edges_ir()` in `_strategies.py`, for `RoutedEdge` instances where `source_scope != ""` or `target_scope != ""`, replace the default label anchor (segment midpoint) with the output of `_pick_label_anchor()` when a label is present.

---

### Task 9: Validation and oracle adapter exposure
Depends on: Task 3, Task 4
Verification: TDD

**Tests (`tests/test_state_model.py` and `tests/test_fix_state.py`):**
- `validate_finalized_layout()` returns a `ValidationResult` with no errors for both `statediagram-complex.mmd` and `statediagram-nested.mmd`.
- For a synthetic `FinalizedLayout` with a `RoutedEdge` whose `source_scope="Processing"` but `semantic_source_id=""`, `validate_finalized_layout()` returns an error.
- Oracle adapter test: a fixture invoking the mmdc adapter with `statediagram-nested.mmd` content returns a result whose `composite_gates` map contains `"Processing"` and the values match the `FinalizedLayout.composite_gates` field.

**Approach:**
- In `scripts/mermaid_render/layout/_geometry.py`, in `validate_finalized_layout()`, add a check: for each `RoutedEdge` in `finalized.routed_edges`, if `source_scope` or `target_scope` is non-empty, both the semantic and routing endpoint IDs must also be non-empty. Append to `ValidationResult.errors` on violation.
- Expose `FinalizedLayout.composite_gates` in the mmdc oracle adapter response (the adapter already serializes `FinalizedLayout`; add `composite_gates` to the serialization dict, converting `MappingProxyType` to a plain dict for JSON safety).
- Write the oracle adapter test in `tests/test_fix_state.py` asserting the `composite_gates` key is present and correct.
