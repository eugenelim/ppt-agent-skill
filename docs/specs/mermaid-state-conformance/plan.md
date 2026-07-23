# Implementation Plan — Mermaid State Diagram Conformance

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_strategies.py` or the state compiler module; `scripts/mermaid_render/layout/_geometry.py` (add `StateIndex`); `tests/test_state_conformance.py` (new); shared `tests/geometry_verifier.py` (created by `mermaid-flowchart-conformance`; that item must ship before this one to make the module available).
2. Done when: `pytest tests/test_state_conformance.py` passes for both state fixtures; `StateIndex` covers all composite depths recursively; no whole-diagram fallback triggered by self-loops; geometry verifier reports zero violations.
3. Not changing: flowchart, ER, class, architecture, requirement compilers; the oracle contract, text measurer, shape geometry, or compound layout (upstream dependencies).

**Declined patterns:**
- Tempted to extend the existing flat `by_id` dict rather than building a proper `StateIndex`; declining — the spec requires all six fields; partial implementation re-creates the nesting bug.
- Tempted to use `(src, dst)` as transition identity in tests; declining — the spec prohibits this everywhere; edge IDs are authoritative.
- Tempted to add fixture-specific coordinate patches for nested states; declining — must generalize through recursive traversal.

---

## Tasks

### Task 1: `StateIndex` dataclass and builder
Depends on: none
Verification: TDD

**Tests:**
- `test_state_index_covers_all_depths`: build a `StateIndex` from a three-level composite hierarchy; assert all states at all three levels appear in `by_id`.
- `test_state_index_parent_by_id`: build from a two-level hierarchy; assert `parent_by_id[inner_state_id] == composite_id`.
- `test_state_index_initial_by_scope`: build a diagram with a scoped initial state inside a composite; assert `initial_by_scope[composite_id] == scoped_initial_id`.
- `test_state_index_final_by_scope`: assert scoped final state appears in `final_by_scope` under the correct composite scope.

**Approach:**
- Add `StateIndex(by_id, parent_by_id, scope_by_id, composite_ids, initial_by_scope, final_by_scope)` dataclass to `_geometry.py`.
- Add `build_state_index(states: list[StateNode]) -> StateIndex` using recursive DFS over composite children.
- In the state compiler, call `build_state_index` once before any endpoint rewriting.

---

### Task 2: Unique edge IDs before endpoint rewriting
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_all_transitions_have_unique_edge_ids`: compile `statediagram-complex`; assert all transition `edge_id` values are unique.
- `test_edge_id_assigned_before_rewriting`: spy on the transition builder; assert `edge_id` is set before `routing_source_id` or `routing_target_id` is rewritten.

**Approach:**
- In the state compiler, assign a deterministic `edge_id` (e.g. `f"t{source_position}"` from the parse position, or a hash of `(scope, src, dst, label, ordinal)`) to each transition before any gate-based endpoint rewriting. Do not use `uuid4` — IDs must be stable across repeated runs.
- Update all downstream metadata dicts to use `edge_id` as the key.

---

### Task 3: Composite-to-external transition gates
Depends on: Tasks 1, 2
Verification: TDD

**Tests:**
- `test_composite_exit_gate_created`: compile `statediagram-nested`; find a transition leaving `Processing`; assert a `BoundaryGate(kind=EXIT)` exists at the `Processing` boundary.
- `test_composite_remains_semantic_endpoint`: for the same transition, assert `semantic_source_id == "Processing"`.
- `test_external_route_begins_on_boundary`: for the same transition, assert the first waypoint of the external route lies on `Processing`'s group bounds within 1-pixel tolerance.

**Approach:**
- In the state compiler, for each transition where the source is a composite:
  - Retain `semantic_source_id` = the composite ID.
  - Set `routing_source_id` = the exit-gate proxy ID.
  - Create a `BoundaryGate(kind=EXIT, group_id=composite_id, ...)` at the composite boundary.
  - Begin the visible route from the gate point.

---

### Task 4: External-to-composite transition gates
Depends on: Tasks 1, 2
Verification: TDD

**Tests:**
- `test_composite_entry_gate_created`: compile `statediagram-nested`; find a transition entering `Processing`; assert a `BoundaryGate(kind=ENTRY)` exists.
- `test_declared_semantic_target_preserved`: for the same transition, assert `semantic_target_id` equals the declared target (not the gate proxy).
- `test_internal_transitions_inside_composite`: compile `statediagram-nested`; for all transitions between states both inside `Processing`, assert all waypoints are within `Processing`'s group bounds.

**Approach:**
- For each transition where the target is a composite:
  - Retain `semantic_target_id` = the declared target.
  - Set `routing_target_id` = the entry-gate proxy ID.
  - Create a `BoundaryGate(kind=ENTRY, group_id=composite_id, ...)`.
  - Terminate the visible route at the gate point.

---

### Task 5: Scoped pseudo-state collision-free IDs
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_scoped_initial_ids_distinct`: compile `statediagram-nested`; assert the global initial state and the `Processing`-scoped initial state have distinct IDs.
- `test_scoped_final_ids_distinct`: assert global final and `Processing`-scoped final have distinct IDs.
- `test_pseudo_state_scope_correct`: assert the `Processing`-scoped initial state appears in `StateIndex.initial_by_scope["Processing"]`.

**Approach:**
- In the state compiler, generate scoped pseudo-state IDs as `f"__initial_{scope_id}"` and `f"__final_{scope_id}"`.
- Ensure the global initial/final states use `"__initial_root"` / `"__final_root"` to avoid collisions.
- Register all scoped pseudo-states in `StateIndex.initial_by_scope` / `StateIndex.final_by_scope`.

---

### Task 6: Local cycle routing and self-loop repair
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_local_cycle_not_global_perimeter`: compile `statediagram-complex`; find a local cycle; assert its waypoints are within the SCC bounding box, not at the canvas perimeter.
- `test_self_loop_local_repair_no_fallback`: compile a state diagram with a self-loop; assert `metadata.fallback_reason is None`; assert only the self-loop edge has non-ELK waypoints.

**Approach:**
- Apply the same SCC-based local cycle routing developed for `mermaid-flowchart-conformance`.
- For self-loops: apply a local geometry repair (offset control points) without triggering a whole-diagram fallback.
- Assert non-self-loop edges retain their ELK geometry.

---

### Task 7: Per-fixture conformance tests
Depends on: Tasks 1–6
Verification: TDD

**Tests:**
- `test_statediagram_complex_conformance`: compile `statediagram-complex`; assert all states uniquely identified; assert all edge IDs unique; assert local cycles confined; run geometry verifier; assert zero violations.
- `test_statediagram_nested_conformance`: compile `statediagram-nested`; assert `Processing` contains all internal states; assert internal routes stay inside `Processing`; assert external transitions go through gates; assert global and internal finals distinct; assert nested lookup works at depth ≥ 2.

**Approach:**
- Create `tests/test_state_conformance.py`.
- Reuse the geometry verifier from `mermaid-flowchart-conformance`.
- Assert all structural invariants from the AC list.
