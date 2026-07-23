# State diagram local cycle routing

Mode: full (structural change, multi-feature)

- **Status:** Draft

## Objective

Complete local cycle routing for state diagrams and preserve state-machine semantics
independently from routing proxies.

The prior shipped specs (`state-compiler-recursive`, `state-diagram-cross-scope-clip`)
established `compile_state_machine()` as the authoritative compiler and added
`_clip_cross_scope_exit_waypoints()` for composite-exit clipping. However, routing
remained semantics-blind: `RoutedEdge` carries only the proxy node IDs used for
geometry (e.g. `Processing_sm_end_`), not the semantic node IDs a reader expects (e.g.
`Processing`). Local back-edges (`Authenticating → Idle`, `Processing → Active`,
`Failed → Idle`) are routed with no knowledge of composite scope, so they can expand
to the full canvas perimeter instead of wrapping tightly around their relevant state
set. Internal composite transitions can bleed through the composite title or group
boundary.

This spec extends the finalized-edge IR with explicit semantic/routing endpoint fields
and scope markers, models entry/exit gates explicitly in `FinalizedLayout`, implements
scope-aware local cycle routing, and exposes composite containment to the mmdc oracle
adapter.

Targets: `statediagram-complex.mmd`, `statediagram-nested.mmd`.

## Boundaries

- **Preserve:** Keep `compile_state_machine()` as the authoritative recursive compiler; do not replace or restructure it.
- **Preserve:** The existing `_clip_cross_scope_exit_waypoints()` step; this spec extends it rather than replacing it.
- **Preserve:** The ELK code path; state diagrams already fall back to the Python Sugiyama path (terminal circles force that), so ELK is unaffected.
- **Preserve:** `state_model_to_graph()` as the bridge between the compiled IR and the layout graph; population of new semantic fields belongs here.
- **Out of scope:** Concurrent region (`--`) semantics.
- **Out of scope:** Deep-history semantics beyond label.
- **Out of scope:** `mermaid_render/native_svg.py` SVG paint path (separate renderer).
- **Out of scope:** Destination-endpoint (composite-entry) waypoint clipping beyond what `_clip_cross_scope_exit_waypoints()` already handles.

## Acceptance Criteria

- [ ] AC1: `RoutedEdge` in `_geometry.py` carries `semantic_source_id`, `semantic_target_id`, `routing_source_id`, `routing_target_id`, `source_scope`, and `target_scope` fields; all are optional strings defaulting to `""` for non-state-diagram edges.
- [ ] AC2: For the `Processing --> Done` edge in `statediagram-nested.mmd`: `semantic_source_id` is `"Processing"`, `routing_source_id` is `"Processing_sm_end_"`, and the first visible waypoint lies on (not strictly inside) the Processing composite boundary.
- [ ] AC3: `FinalizedLayout` carries an explicit `composite_gates` field — a `MappingProxyType` mapping composite ID to a `(entry_gate_id, exit_gate_id)` pair — rather than relying only on dynamic `src_group` attributes or inline comments for gate knowledge.
- [ ] AC4: All scoped pseudo-state IDs produced by `state_model_to_graph()` are collision-free; a uniqueness assertion in `state_model_to_graph()` raises `ValueError` on collision (verified by unit test with a synthetic fixture that would collide without scoping).
- [ ] AC5: `Authenticating --> Idle` route in `statediagram-complex.mmd` uses a perimeter that encircles only the Authenticating + Idle state pair; no waypoint lies further from the pair than `2 * NODE_W` in either axis beyond the pair's bounding box.
- [ ] AC6: `Processing --> Active` back-edge in `statediagram-complex.mmd` uses a perimeter around the Processing + Active pair; same proximity constraint as AC5.
- [ ] AC7: `Failed --> Idle` back-edge in `statediagram-nested.mmd` uses a perimeter around the outer machine's relevant state set (Idle + Failed); it does not use an arbitrary global canvas perimeter lane.
- [ ] AC8: No internal composite transition (transitions whose `source_scope` == `target_scope` == the composite ID) has any waypoint outside the composite group bounding box.
- [ ] AC9: No cross-scope transition waypoint passes through the composite title region (the top `title_height` pixels of the group bounding box).
- [ ] AC10: Edge labels on local back-edge routes are placed on a clear (non-overlapping) segment of the route; the label's anchor point is not inside any node bounding box.
- [ ] AC11: `validate_finalized_layout()` checks that both `semantic_source_id`/`semantic_target_id` and `routing_source_id`/`routing_target_id` are present on every `RoutedEdge` whose `source_scope` or `target_scope` is non-empty; violations appear in `ValidationResult.errors`.
- [ ] AC12: `FinalizedLayout.composite_gates` is accessible from the mmdc oracle adapter so it can verify that a transition's declared scope matches the compiled gate structure; at least one oracle adapter test exercises this path.
- [ ] AC13: All existing tests pass (`pytest tests/`); both `statediagram-complex.mmd` and `statediagram-nested.mmd` compile and render without crash or routing failure.

## Testing Strategy

- **Unit — `tests/test_state_model.py`:**
  - `compile_state_machine()` + `state_model_to_graph()` populate `semantic_source_id`, `routing_source_id`, `source_scope`, and `target_scope` correctly on cross-scope edges.
  - Scoped pseudo-state ID collision detection raises `ValueError` on a synthetic colliding fixture.
  - `composite_gates` map is populated with the correct entry/exit gate IDs.

- **Unit — `tests/test_state_cycle_routing.py` (new):**
  - `_route_local_cycle()` pure-function tests: given a synthetic pair of node bboxes and a scope bbox, the returned waypoints stay within the expected proximity constraint (AC5/AC6/AC7).
  - Boundary-containment check: given an internal-edge route that would cross the group boundary, the post-routing fixup clips the exit back inside the box.
  - Title-avoidance check: given a cross-scope route that would traverse the title row, the fixup detours below it.

- **Integration — `tests/test_fix_state.py`:**
  - `Processing --> Done` edge in `statediagram-nested.mmd`: assert `semantic_source_id == "Processing"`, `routing_source_id == "Processing_sm_end_"`, first waypoint on/outside Processing boundary.
  - `Authenticating --> Idle` in `statediagram-complex.mmd`: assert waypoints satisfy AC5 proximity constraint.
  - `composite_gates` map on `FinalizedLayout` is non-empty and contains `"Processing"` key for nested fixture.
  - `validate_finalized_layout()` returns no errors for both fixtures.
