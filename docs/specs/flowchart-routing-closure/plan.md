# Plan: flowchart-routing-closure

- **Spec:** [`spec.md`](spec.md)
- **Status:** Shipped

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn.

## Approach

Five tasks in dependency order. T1 is pure data-model additions (no routing changes yet); T2 adds the local-channel algorithm; T3 fixes the fan distribution; T4 wires the flowchart adapter for the three scoped fixtures; T5 adds the test suite. T1 and T3 are independent; T2 also independent (uses only pre-existing `RouteCandidate` — no T1 dependency despite the initial draft); T4 depends on T1, T2, T3; T5 depends on T4. The global flag (`_USE_LEGACY_ROUTE_EDGES = False`) enables the new path for **all** Python-fallback flowcharts — the spec's "three scoped fixtures" means the tests target those three, not that the code is conditionally gated.

The riskiest part is T4 (flowchart adapter), which must produce correct geometry for the compound inner-direction fixture without regressing the other fixtures. The local_channel_route() in T2 is the second riskiest — it must reject candidates outside the inflation bounds.

## Constraints

- Constrained by: `docs/specs/routing-validation-invariants/spec.md` (existing validate_routes contract extended, not replaced).
- Constrained by: `docs/specs/routing-port-planner-foundation/spec.md` (PortCandidate, RoutingObstacle, RouteCandidate shapes pinned).
- Do not change the shape of existing NamedTuples (only add new ones and new fields to validate_routes signature).

## Construction tests

**Integration tests:**
- `tests/test_flowchart_routing_closure.py` covers all three fixtures end-to-end including geometry, fan, and channel assertions.

**Manual verification:** none (all verification is automated).

## Design (LLD)

### Design decisions

- `RoutePermissions` and `GateAperture` go into `port_planner.py` (the shared data-model module, AC1/AC2). Alternative: a new module — rejected (Boundaries: Never do new module).
- `local_channel_route()` goes into `route_search.py` (the existing route-form builder module, AC11). It is a new `try_*`-family function parallel to `try_l_route` and `try_z_route`.
- `flowchart_route_adapter()` goes into `_pipeline.py` (AC6). It is a function called from `layout_flowchart_with_python_fallback()` when the legacy flag is off. Keeps the coupling between semantic model and routing abstractions in one place.
- `fan_slots()` is updated in-place in `port_planner.py` (AC17). The formula change is backward-compatible for N=1 (returns center). The old `_fan_offset()` in `_routing.py` is left unchanged (guarded by the ask-first constraint on MIN_FAN_STEP).

### Data & schema

New types added to `port_planner.py` (AC1–AC3):

```
RoutePermissions(NamedTuple):
    edge_id: str
    source_scope_chain: tuple[str, ...]
    target_scope_chain: tuple[str, ...]
    common_ancestor_ids: tuple[str, ...]
    permitted_gate_ids: tuple[str, ...]

GateAperture(NamedTuple):
    gate_id: str
    edge_id: str
    group_id: str
    side: str          # "top" | "right" | "bottom" | "left"
    center: tuple[float, float]
    half_width: float
```

Extended `RoutingObstacle.kind` (AC3) — new accepted values alongside existing ones:
`"NODE_INTERIOR" | "GROUP_INTERIOR" | "GROUP_BOUNDARY" | "GROUP_TITLE" | "LABEL" | "MARKER_CLEARANCE"`

### Interfaces & contracts

`validate_routes(routes, reservations, obstacles, canvas_bounds, marker_depths, route_permissions)` — new optional `route_permissions` parameter (AC4). Back-compat: defaults to `None` (no change to callers without it).

`local_channel_route(edge_id, src_port, dst_port, local_bounds, existing_routes, lane_index, *, LOCAL_LANE_GAP, LANE_PITCH, MAX_LOCAL_EXCURSION)` — new function in `route_search.py` (AC11). Returns `RouteCandidate | None`.

`fan_slots(edge_ids, side, face_length)` — adds `face_length: float` parameter (AC17). Back-compat: existing callers pass `face_length=0` to get original behavior (degenerate: N==1 path).

`flowchart_route_adapter(semantics)` — new function in `_pipeline.py` (AC6). Returns `(list[PortCandidate], list[RoutingObstacle], list[RoutePermissions], list[GateAperture])`.

### Failure & resilience

When `local_channel_route()` returns `None` (no valid channel), the caller falls back to `route_edge()` which tries direct/L/Z. If all fail, a `RoutingFailure` is recorded (existing behavior). `_route_perimeter` is NOT in the fallback chain for the scoped fixtures.

## Tasks

### T1: Add RoutePermissions, GateAperture, and extended RoutingObstacle kinds

**Depends on:** none
**Touches:** `scripts/mermaid_render/layout/port_planner.py`, `scripts/mermaid_render/layout/route_validation.py`

**Tests:**
- `test_route_permissions_is_namedtuple`: `RoutePermissions("e1", ("A",), ("B",), (), ("g1",))` is immutable and field-accessible (AC1).
- `test_gate_aperture_is_namedtuple`: `GateAperture("g1", "e1", "grp", "bottom", (10.0, 20.0), 5.0)` is immutable (AC2).
- `test_obstacle_kind_new_values_accepted`: construct `RoutingObstacle(…, kind="NODE_INTERIOR", …)` without error (AC3).
- `test_obstacle_kind_old_values_still_accepted`: construct with `kind="node"` and `kind="group"` without error (AC3 back-compat).
- `test_validate_routes_permission_param_defaults_none`: existing callers get identical behavior when `route_permissions` and `gate_apertures` not supplied (AC4 back-compat).
- `test_validate_routes_rejects_wrong_gate`: inject a `RouteCandidate` that crosses a `GROUP_BOUNDARY` obstacle outside its `GateAperture` (both supplied); assert `validate_routes()` returns a `ValidationError` with rule `"gate_violation"` (AC5).
- `test_validate_routes_rejects_title_crossing`: inject a route that crosses a `GROUP_TITLE` obstacle; assert `ValidationError` returned (AC5).
- `test_validate_routes_rejects_reentry`: inject a route that leaves and re-enters a group (by providing permissions + apertures that forbid it); assert `ValidationError` (AC5).
- `test_check_obstacles_filters_new_kinds`: `_check_obstacles` processes `GROUP_BOUNDARY`, `GROUP_INTERIOR`, `GROUP_TITLE` obstacles (not silent-skip as with old filter) (AC5).

**Approach:**
- In `port_planner.py`: add `RoutePermissions` and `GateAperture` NamedTuples after `RoutingObstacle`. Document their field semantics.
- In `port_planner.py`: update the `RoutingObstacle.kind` docstring to list all six values. No runtime change — `kind` is already an unvalidated `str`.
- In `route_validation.py`: add `route_permissions: list[RoutePermissions] | None = None` and `gate_apertures: list[GateAperture] | None = None` parameters to `validate_routes()`. When supplied, run `_check_gate_permissions(route, permissions, apertures)` per edge.
- In `route_validation.py`: update `_check_obstacles()` kind filter from `not in ("node", "group")` to include all six new kind values (old values aliased: `"node"` → `"NODE_INTERIOR"`, `"group"` → `"GROUP_INTERIOR"`, `"title_band"` → `"GROUP_TITLE"`).

**Done when:** `pytest tests/test_flowchart_routing_closure.py::TestDataModel -v` passes (all 8 tests green).

---

### T2: Add local_channel_route() to route_search.py

**Depends on:** none
**Touches:** `scripts/mermaid_render/layout/route_search.py`

**Tests:**
- `test_local_channel_left_channel`: src=(50,100), dst=(50,400), local_bounds=(60,100,80,300) → left channel at x < 60-16; waypoints inside inflate(48) (AC11, AC12).
- `test_local_channel_right_channel`: same but local_bounds forces right channel; verify x ≤ bounds.right + 48 (AC11, AC12).
- `test_local_channel_rejects_out_of_bounds`: when both channels require x > bounds.right+48, returns None (AC12).
- `test_local_channel_returns_route_candidate`: return value is a `RouteCandidate` with correct `edge_id`, `source_port`, `target_port` (AC11).
- `test_local_channel_orthogonal_segments`: all segments in returned `RouteCandidate.points` are axis-aligned (AC11).
- `test_local_channel_deterministic`: same inputs twice → identical `RouteCandidate.points` (AC24 precursor).

**Approach:**
- Add `MAX_LOCAL_EXCURSION = 48.0`, `LOCAL_LANE_GAP = 16.0`, `LANE_PITCH = 14.0` constants at module top.
- Implement `local_channel_route(edge_id, src_port, dst_port, local_bounds, existing_routes, lane_index=0)`:
  1. Compute `left_x = local_bounds[0] - LOCAL_LANE_GAP - lane_index * LANE_PITCH` and `right_x = local_bounds[0] + local_bounds[2] + LOCAL_LANE_GAP + lane_index * LANE_PITCH` (where `local_bounds` is `(x, y, w, h)`).
  2. For each channel side (left, right), build the 5-point route: `(src_x, src_y) → (channel_x, src_y) → (channel_x, dst_y) → (dst_x, dst_y)` (simplified to 4 points for the orthogonal case).
  3. Check all waypoints inside `(local_bounds[0]-MAX_LOCAL_EXCURSION, local_bounds[1]-MAX_LOCAL_EXCURSION, local_bounds[2]+2*MAX_LOCAL_EXCURSION, local_bounds[3]+2*MAX_LOCAL_EXCURSION)`.
  4. Build `RouteCandidate` via `_make_rc()` for each valid candidate; return lowest-cost.
  5. Return `None` when no valid candidate passes the inflation check.

**Done when:** `pytest tests/test_flowchart_routing_closure.py::TestLocalChannel -v` passes (all 6 tests green).

---

### T3: Fix fan_slots() with face-spanning distribution

**Depends on:** none
**Touches:** `scripts/mermaid_render/layout/port_planner.py`

**Tests:**
- `test_fan_slots_n1_returns_center`: N=1, face_length=100 → offset 0.5 (unchanged behavior) (AC17).
- `test_fan_slots_n3_spans_face`: N=3, face_length=100, FAN_EDGE_PADDING=12 → offsets at 12, 50, 88 (not 25, 50, 75) (AC17).
- `test_fan_slots_n3_min_pitch`: N=3, face_length=60 (= 2*12 + 2*24 = minimum valid) → spacing exactly FAN_MIN_PORT_PITCH=24; offsets at 12, 36, 60-12=48 (AC17, AC18).
- `test_fan_slots_constants_defined`: `FAN_EDGE_PADDING`, `FAN_MIN_PORT_PITCH`, `FAN_ESCAPE_LENGTH`, `FAN_CHANNEL_PITCH` all importable from `port_planner` with correct values (AC18).
- `test_fan_slots_n2_no_center_compression`: N=2, face_length=100 → positions 12 and 88 (not 33 and 67) (AC17).
- `test_fan_slots_deterministic`: same edge_ids and face_length → identical output (AC24 precursor).

**Approach:**
- Add module-level constants to `port_planner.py`: `FAN_EDGE_PADDING = 12.0`, `FAN_MIN_PORT_PITCH = 24.0`, `FAN_ESCAPE_LENGTH = 20.0`, `FAN_CHANNEL_PITCH = 14.0`.
- Update `fan_slots(edge_ids, side, face_length=0.0)`:
  - For N=1: return `[(edge_ids[0], 0.5)]` (unchanged).
  - For N≥2 and face_length > 0: compute `required = 2 * FAN_EDGE_PADDING + (N-1) * FAN_MIN_PORT_PITCH`. If `face_length < required`, clamp the usable range so ports are spaced at exactly `FAN_MIN_PORT_PITCH` starting from `FAN_EDGE_PADDING` (the "too narrow" case). Otherwise: distribute evenly: `first = FAN_EDGE_PADDING / face_length`, `last = (face_length - FAN_EDGE_PADDING) / face_length`; `offset_i = first + i * (last - first) / (N-1)`.
  - For face_length=0 (back-compat): use original `(i+1)/(N+1)` formula.

**Done when:** `pytest tests/test_flowchart_routing_closure.py::TestFanSlots -v` passes (all 6 tests green).

---

### T4: Wire flowchart adapter for three scoped fixtures

**Depends on:** T1, T2, T3
**Touches:** `scripts/mermaid_render/layout/_pipeline.py`

**Tests:**
- `test_adapter_returns_port_candidates`: `flowchart_route_adapter(semantics)` returns list of `PortCandidate` objects with valid `edge_id` for a simple 2-node graph (AC6).
- `test_adapter_keyed_by_edge_id`: the adapter's incoming and outgoing edge-id maps each contain the correct `edge_id` keys (not `(src, dst)` pairs); `PortCandidate.edge_id` matches the edge's `edge_id` (AC7).
- `test_new_path_used_for_scoped_fixtures`: monkeypatches `_route_edges` to raise `RuntimeError`; compiles all three scoped fixtures; asserts no exception (AC10).
- `test_perimeter_not_reachable_for_scoped_fixtures`: monkeypatches `_route_perimeter` to raise; compiles all three fixtures; asserts no exception (AC13).
- `test_inner_direction_no_canvas_edge_waypoints` (AC15, AC16): `source→ingest` has no x=0 waypoint; `load→sink` has no y=canvas_height waypoint.
- `test_inner_direction_no_canvas_edge_waypoints` (AC15): `source→ingest` has no waypoint with x≤0 or x≥canvas_w; `load→sink` has no waypoint with y≤0 or y≥canvas_h; both checks in all four bounds.
- `test_inner_direction_single_boundary_crossing` (AC16): both `source→ingest` and `load→sink` each cross the Pipeline boundary exactly once.
- `test_arrows_defs_no_full_height_rectangle` (AC14): `A→D dotted` has no waypoint outside local obstruction inflated by 48.
- `test_parallel_links_fan_pitch` (AC19): pairwise Gateway src port separation ≥ 24; pairwise Aggregator dst port separation ≥ 24.
- `test_parallel_links_escape_distinct` (AC20, AC21): first 20 px of each Gateway outgoing route are distinct; last 20 px of each Aggregator incoming route are distinct.
- `test_endpoint_equals_port` (AC8): for each scoped-fixture edge, `waypoints[0] == reserved_src_port` and `waypoints[-1] == reserved_dst_port`.
- `test_all_fixtures_no_routing_failures`: `layout.routing_failures == []` for all three fixtures (AC22).
- `test_deterministic_routes` (AC24): two compilations of each fixture yield identical normalized waypoints.

**Approach:**
- Add `_USE_LEGACY_ROUTE_EDGES: bool = False` at top of `_pipeline.py` (AC9).
- Implement `flowchart_route_adapter(semantics: FlowchartSemantics) -> tuple[list[PortCandidate], list[RoutingObstacle], list[RoutePermissions], list[GateAperture]]` (AC6):
  - For each node: generate `PortCandidate` via `generate_port_candidates()`.
  - For each group: create `RoutingObstacle(kind="GROUP_INTERIOR", …)` and `RoutingObstacle(kind="GROUP_BOUNDARY", …)` and `RoutingObstacle(kind="GROUP_TITLE", …)` from `group.title`.
  - For each cross-boundary edge: build `RoutePermissions` from source/target group scope chains; build `GateAperture` from the candidate crossing point.
  - For each edge: build incoming/outgoing lists keyed by `edge_id` (AC7).
- In `layout_flowchart_with_python_fallback()`: add branch on `_USE_LEGACY_ROUTE_EDGES`:
  - When False: call `flowchart_route_adapter()`, then `assign_routes()` from `route_search`, then `validate_routes()`, then convert to `RoutedEdge` IR without endpoint patching.
  - When True: existing `_route_edges()` call (unchanged).
- In the new path, when routing a multi-rank edge (src_rank ≠ dst_rank by > 1): try `local_channel_route()` from `route_search` before falling back to `route_edge()`.
- When routing fan nodes (≥ 2 outgoing on same face): use updated `fan_slots()` with `face_length=node_width_or_height`.

**Done when:** `pytest tests/test_flowchart_routing_closure.py::TestAdapter tests/test_flowchart_routing_closure.py::TestFixtureGeometry -v` all pass; existing fixture tests still pass (`pytest tests/test_flowchart_conformance.py tests/test_flowchart_compound_layout.py tests/test_regression_fixtures.py -v -k "not groups_complex"`).

---

### T5: Add full test suite and negative validation tests

**Depends on:** T1-T4
**Touches:** `tests/test_flowchart_routing_closure.py`

**Tests (negative — inject bad routes into validate_routes):**
- `test_rejects_cross_scope_outside_gate` (AC23a): route that crosses GROUP_BOUNDARY outside GateAperture → ValidationError.
- `test_rejects_title_crossing` (AC23b): route that crosses GROUP_TITLE → ValidationError.
- `test_rejects_wrong_gate_used` (AC23c): route using another edge's gate → ValidationError.
- `test_rejects_reentry` (AC23d): route leaving and re-entering same group → ValidationError.
- `test_rejects_perimeter_route` (AC23e): route that traverses the whole canvas perimeter → ValidationError.
- `test_nonzero_assertions_parallel_links` (AC22): at least 1 distance check on Gateway fan ports.
- `test_nonzero_assertions_arrows_defs` (AC22): at least 1 coordinate check on A→D route.
- `test_nonzero_assertions_inner_direction` (AC22): at least 1 boundary-crossing check on source→ingest.

**Approach:**
- Consolidate all tests from T1–T4 into `tests/test_flowchart_routing_closure.py` under named test classes.
- Add negative validation tests by constructing synthetic `RouteCandidate` and `RoutingObstacle` objects and calling `validate_routes()` directly.
- Add `normalize_waypoints(layout)` helper: round all waypoint coordinates to 1 decimal place, sort edges by edge_id, return comparable tuple.

**Done when:** `pytest tests/test_flowchart_routing_closure.py -v` all pass with zero failures; `pytest tests/test_flowchart_conformance.py tests/test_flowchart_compound_layout.py -v` shows no regressions on non-groups-complex fixtures.

## Rollout

Pure Python change; no infra, no migrations, no external services. Ships in one PR. The `_USE_LEGACY_ROUTE_EDGES = False` default is the cutover; setting it `True` is the rollback for the three scoped fixtures.

## Risks

- **T4 compound geometry**: the inner-direction adapter must correctly derive Pipeline boundary gates from the group layout. If the group bboxes are not yet finalized when the adapter runs, gate positions will be wrong. Mitigation: read group bboxes from `layout_graph.group_bboxes` (already computed before routing).
- **T2 channel bounds**: `local_bounds` must cover exactly the obstructing nodes between src and dst ranks, not all nodes. Deriving the local bounds correctly requires iterating over intermediate-rank nodes. If wrong, the channel may be unnecessarily wide or overly restrictive.
- **T3 fan_slots back-compat**: callers that pass `face_length=0` (or omit it) must get the old `(i+1)/(N+1)` formula. Test the explicit degenerate path.

## Changelog

- 2026-07-24: initial plan
