Mode: full (multi-feature — 5 interdependent routing sub-systems; structural data-model additions; security: none)

- **Status:** Shipped
- **Shape:** service
- **Brief:** none
- **Discovery:** none
- **Contract:** none

Constrained by: docs/specs/routing-validation-invariants/spec.md, docs/specs/routing-port-planner-foundation/spec.md, docs/specs/routing-search-and-assignment/spec.md

# Spec: flowchart-routing-closure

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The flowchart Python-fallback router produces three confirmed routing defects across the scoped fixtures:

1. **flowchart-parallel-links**: Gateway fan ports are 23 px apart (below the 24 px minimum), compressed around the face centre rather than spanning the usable face.
2. **flowchart-arrows-defs**: The `A-.->D` dotted long edge forms a whole-height rectangle at x=112, spanning y=90→414 (the full diagram height). No local-channel constraint is enforced.
3. **flowchart-inner-direction**: `source→ingest` routes through x=0 (canvas left edge); `load→sink` routes to y=780/870 canvas height — both bypass the Pipeline subgraph boundary instead of crossing it at a legal gate.

This spec adds five building blocks to close all three defects:

1. **Data model**: `RoutePermissions` and `GateAperture` NamedTuples, and six-value `RoutingObstacle.kind`.
2. **Flowchart adapter**: converts `FlowchartSemantics` into port_planner/route_search/route_validation abstractions.
3. **Local channel**: replaces `_route_perimeter` on the Python-fallback path for the three scoped fixtures.
4. **Fan bundles**: `evenly_spaced(FAN_EDGE_PADDING=12, face_length-FAN_EDGE_PADDING, N)` with FAN_MIN_PORT_PITCH=24.
5. **Tests**: 14 common invariants + 7 negative tests in `tests/test_flowchart_routing_closure.py`.

Scope is strictly limited to three fixtures: `flowchart-parallel-links`, `flowchart-arrows-defs`, `flowchart-inner-direction`.

## Boundaries

### Always do
- Target only `flowchart-parallel-links`, `flowchart-arrows-defs`, `flowchart-inner-direction`.
- Keep `_route_edges` callable behind an explicit module-level flag during migration.
- Extend existing data structures in `port_planner.py`; do not create a parallel data-model module.
- Define every new constant once, in the file that owns the algorithm using it.
- Local channel: reject any waypoint outside `local_bounds.inflate(48)`.
- Preserve gate apertures in `FinalizedLayout.boundary_gates` after routing.
- Old `RoutingObstacle.kind` string values remain accepted for back-compat.

### Ask first
- Removing `_route_perimeter` from non-flowchart diagram types (may still be needed by other callers).
- Changing `MIN_FAN_STEP` in `_constants.py` (global symbol used by multiple callers).
- Expanding node minimum size to accommodate fan (touches ELK pre-placement).

### Never do
- Add another graph-layout engine.
- Add fixture-name conditionals in routing code.
- Solve defects through painter-only path changes.
- Make dotted/thick/solid edges use different routing algorithms.
- Globally disable group-title collision checks.
- Retain an unbounded whole-canvas perimeter route as a successful fallback.
- Identify edges only by source+destination IDs (must use `edge_id`).
- Touch files outside `scripts/mermaid_render/layout/` and `tests/`.
- Add a new top-level module boundary or new external dependency.

## Testing Strategy

| Behavior | Mode | Why |
|---|---|---|
| `RoutePermissions` / `GateAperture` NamedTuples | TDD | Pure data — equality invariants |
| New `RoutingObstacle.kind` values | TDD | Exhaustive value-set test |
| `validate_routes()` per-edge permission logic | TDD | Pure function with clear invariants |
| `local_channel_route()` algorithm | TDD | Deterministic geometry — concrete point assertions |
| `fan_slots()` new formula | TDD | Pure arithmetic — evenly-spaced distance invariants |
| `flowchart_route_adapter()` structural mapping | TDD | Output shape — PortCandidate/Obstacle/Permission lists |
| Three fixtures compile via new path, no failures | Goal-based | `compile_flowchart()` returns empty `routing_failures` |
| `_route_perimeter` not reachable on production path | Goal-based | Monkeypatch to raise; confirm no exception |
| Negative validation rejects bad routes | TDD | Inject bad route; assert `validate_routes` returns errors |
| Fixture geometry ACs (AC14–AC16, AC19–AC21): waypoint coordinate constraints per fixture | TDD | Concrete-waypoint assertions on compiled layout; the defect closures are the acceptance criteria |
| Deterministic waypoints across two compilations | Goal-based | Normalized waypoint sequences are byte-equal |

## Acceptance Criteria

### Section 1 — Edge-aware route permissions

- [x] AC1: `RoutePermissions(edge_id, source_scope_chain, target_scope_chain, common_ancestor_ids, permitted_gate_ids)` is an immutable `NamedTuple` in `port_planner.py`.
- [x] AC2: `GateAperture(gate_id, edge_id, group_id, side, center, half_width)` is an immutable `NamedTuple` in `port_planner.py`.
- [x] AC3: `RoutingObstacle.kind` accepts the six string values `"NODE_INTERIOR" | "GROUP_INTERIOR" | "GROUP_BOUNDARY" | "GROUP_TITLE" | "LABEL" | "MARKER_CLEARANCE"`; old values `"node" | "group" | "title_band"` remain accepted for back-compat.
- [x] AC4: `validate_routes()` accepts two new optional parameters: `route_permissions: list[RoutePermissions] | None = None` and `gate_apertures: list[GateAperture] | None = None`; when both are supplied, applies per-edge permission checks; without them, existing obstacle checks are unchanged.
- [x] AC5: `validate_routes()` reports a `ValidationError` for any edge that: crosses a `GROUP_BOUNDARY` obstacle outside its assigned `GateAperture`; leaves and re-enters the same group; crosses a `GROUP_TITLE` obstacle; uses another edge's gate; crosses an unrelated `GROUP_INTERIOR` obstacle. `_check_obstacles()` in `route_validation.py` is updated to filter on the full six-value kind set (with old-value aliasing) so new kinds are not silently skipped.

### Section 2 — Production router consolidation

- [x] AC6: `flowchart_route_adapter(semantics)` in `_pipeline.py` converts `FlowchartSemantics` nodes/groups/edges into `list[PortCandidate]`, `list[RoutingObstacle]`, `list[RoutePermissions]`, `list[GateAperture]`.
- [x] AC7: The adapter builds incoming/outgoing lists keyed exclusively by `edge_id`.
- [x] AC8: For each edge, `RoutedEdge.waypoints[0]` equals the reserved source port coordinate and `RoutedEdge.waypoints[-1]` equals the reserved destination port coordinate (no post-search endpoint substitution).
- [x] AC9: A module-level flag `_USE_LEGACY_ROUTE_EDGES: bool = False` controls which path is taken; setting it `True` restores `_route_edges`.
- [x] AC10: `tests/test_flowchart_routing_closure.py::test_new_path_used_for_scoped_fixtures` monkeypatches `_route_edges` to raise `RuntimeError`; all three scoped fixtures must compile without triggering it.

### Section 3 — Local multi-rank channels

- [x] AC11: `local_channel_route(edge_id, src_port, dst_port, local_bounds, existing_routes, lane_index)` in `route_search.py` returns a `RouteCandidate` or `None`; it tries left and right channels and returns the lower-cost valid one.
- [x] AC12: `local_channel_route()` rejects any candidate containing a waypoint outside `local_bounds.inflate(MAX_LOCAL_EXCURSION=48)` and returns `None` when no valid channel exists.
- [x] AC13: `_route_perimeter` is not a reachable successful return value on the three scoped fixtures' production path (verified by monkeypatching it to raise).
- [x] AC14 (flowchart-arrows-defs): `A→D` dotted edge has no waypoint with x > `local_bounds.right + 48` and no waypoint with y > `local_bounds.bottom + 48`.
- [x] AC15 (flowchart-inner-direction): `source→ingest` has no waypoint with x ≤ 0 or x ≥ canvas_width; `load→sink` has no waypoint with y ≤ 0 or y ≥ canvas_height; `source→ingest` has no waypoint with y ≤ 0 or y ≥ canvas_height; `load→sink` has no waypoint with x ≤ 0 or x ≥ canvas_width.
- [x] AC16 (flowchart-inner-direction): Both `source→ingest` and `load→sink` each cross the Pipeline group boundary exactly once.

### Section 4 — Full-face fan bundles

- [x] AC17: `fan_slots()` in `port_planner.py` uses the face-spanning formula `evenly_spaced(FAN_EDGE_PADDING, face_length - FAN_EDGE_PADDING, N)` when `N >= 2` and `face_length > 0`. When `face_length <= 0`, falls back to the original `(i+1)/(N+1)` formula for back-compat.
- [x] AC18: Constants `FAN_EDGE_PADDING = 12`, `FAN_MIN_PORT_PITCH = 24`, `FAN_ESCAPE_LENGTH = 20`, `FAN_CHANNEL_PITCH = 14` are defined in `port_planner.py`.
- [x] AC19 (flowchart-parallel-links): Pairwise Gateway source port separation ≥ 24 px; pairwise Aggregator destination port separation ≥ 24 px.
- [x] AC20 (flowchart-parallel-links): First 20 px of every Gateway outgoing route are distinct (pairwise shared segment ≤ 0 px in the first 20 px of travel).
- [x] AC21 (flowchart-parallel-links): Last 20 px of every Aggregator incoming route are distinct.

### Section 5 — Validation and regression tests

- [x] AC22: `tests/test_flowchart_routing_closure.py` executes ≥ 1 nonzero routing geometry assertion per fixture (not vacuous: at minimum one distance or coordinate check per fixture).
- [x] AC23: Tests prove `validate_routes()` rejects: (a) cross-scope edge crossing destination group outside gate; (b) cross-scope edge crossing title-label rectangle; (c) cross-scope edge using another edge's gate; (d) route leaving and re-entering the same group; (e) long edge using the whole canvas perimeter.
- [x] AC24: Compiling any scoped fixture twice produces byte-identical normalized waypoint sequences (test: `normalize_waypoints(layout1) == normalize_waypoints(layout2)`).

## Assumptions

- Technical: runtime is Python 3.13.13; test runner is `pytest` (pyproject.toml, probe confirmed).
- Technical: `_fan_offset()` uses `step = max(usable//(total+1), MIN_FAN_STEP=12)` — centre-compressed, not face-spanning (`_routing.py:622`, `_constants.py:162`).
- Technical: `fan_slots()` uses `(i+1)/(n+1)` — same compressed formula (`port_planner.py:209`).
- Technical: `_route_perimeter()` computes bounding box of ALL obstacles and tries 4 whole-canvas bypass paths; reachable as fallback from A* (`_routing.py:417,1553,1702`).
- Technical: `_skip_lane` is absent (already removed in a prior commit).
- Technical: `RoutingObstacle.kind` currently: `"node" | "group" | "title_band"` (`port_planner.py:55`).
- Technical: runtime probe confirmed:
  - `source→ingest` waypoints include x=0 (canvas edge); `load→sink` waypoints reach y=780/870.
  - `A→D dotted` waypoints: `[(92,90),(112,90),(112,414),(74,414)]` — full-height rectangle.
  - Gateway fan ports at x=87, 110, 133 → 23 px spacing (< 24 px minimum required).
- Process: spec status vocabulary `Draft | Approved | Implementing | Shipped | Archived` (CONVENTIONS.md §4); user confirmation 2026-07-24.
