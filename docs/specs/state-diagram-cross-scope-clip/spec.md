# Spec: state-diagram cross-scope exit clipping

Mode: light (no risk trigger fired)

- **Status:** Shipped

## Objective

Implement the deferred waypoint-clipping step for cross-scope exit edges in state
diagrams. PR #132 wired `compile_state_machine()` as the authoritative compiler and
tags each composite-exit transition (e.g. `Processing --> Done`) with
`_Edge.src_group = "_g_<Composite>"`, but the clip step was deferred
(`docs/backlog.md#state-diagram-cross-scope-clip`). Without it, such an edge's SVG
path originates from the composite's internal scoped-final-state node
(`<Composite>_sm_end_`), which sits inside the group box, instead of from the group
boundary.

Add `_clip_cross_scope_exit_waypoints()` and call it in `_compile_flowchart()` after
`_route_edges()` (route_batch built) and before `_build_routed_edges_ir()`, mutating
the routed dicts so each tagged edge's start is clipped to its source group's
bounding-box boundary.

## Acceptance Criteria

- [x] `_clip_cross_scope_exit_waypoints(routed, src_group_map, grp_bboxes)` drops the
  leading run of waypoints inside the source group box and replaces it with the single
  point where the polyline first crosses the box boundary.
- [x] No-op cases are left untouched: edge_id not in `src_group_map`; group bbox
  missing; fewer than 2 waypoints; first waypoint already outside the box; whole route
  inside the box.
- [x] `statediagram-nested.mmd`: the `Processing → Done` edge's first waypoint is not
  strictly inside the Processing group box (it lies on the boundary).
- [x] `statediagram-complex.mmd` renders without crash.
- [x] All existing tests pass (`pytest tests/`).

## Boundaries

Not changing: the routing algorithm (`_route_edges`), `state_model_to_graph`
(`src_group` already written), the ELK code path structure, or SVG `d`-string
generation (`RoutedEdge` regenerates the path from `waypoints`). Destination-endpoint
clipping for composite-*entry* edges is out of scope.

## Testing Strategy

- TDD unit tests for the pure helper (`tests/test_state_model.py`): clip, and each
  no-op branch, on synthetic route dicts + a synthetic bbox.
- Integration check: compile `statediagram-nested.mmd` and assert the
  `Processing_sm_end_ → Done` RoutedEdge's first waypoint is on/outside the
  `_g_Processing` boundary; assert `statediagram-complex.mmd` compiles without raising.
