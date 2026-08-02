# Flowchart Connector Terminal-Geometry Fix

**Mode:** Full (structural change — new attachment contract, multi-file)
**Status:** Shipped

## Objective

Fix flowchart connector attachment so terminal segments leave/enter every supported shape perpendicular to its actual local boundary — not perpendicular to the AABB bounding-box — and routes are built escape-to-escape with the orthogonal trunk between escape points.

## Acceptance Criteria

- [x] AC1: `BoundaryAttachment` NamedTuple in `shape_geometry.py` with `point`, `outward_normal`, `side`, `face_id`, `at_corner` fields.
- [x] AC2: `ShapeGeometry` protocol exposes `attachment(side, offset, w, h, *, preferred_direction=None) -> BoundaryAttachment`.
- [x] AC3: All 13 registered shapes implement `attachment()`.
- [x] AC4: `port_planner.generate_port_candidates()` populates `PortCandidate.outward_normal` from `shape_geometry.attachment().outward_normal` when shape_geometry provided; not from `_SIDE_NORMALS` lookup.
- [x] AC5: `TerminalAttachment` NamedTuple and `build_terminal_attachment()` helper in `port_planner.py`.
- [x] AC6: `route_validation._check_axis_aligned()` replaced by `terminal_normal_source` and `terminal_normal_target` checks using dot-product tolerance ≥ 0.9998.
- [x] AC7: New `orthogonal_trunk` check validates inner segments (between escape points) are axis-aligned.
- [x] AC8: `_check_port_normals()` updated to use dot-product tolerance rather than exact equality.
- [x] AC9 (Python path): `_pipeline._escape_stub_wrap()` inserts escape stubs for all non-zero outward normals (both source and destination) in the main router. CBE rerouter: source stubs apply only for non-cardinal normals (cardinal source stubs deferred — CBE A* grid is label-unaware — (deferred: flowchart-connector-cbe-cardinal-stubs)); destination stubs apply for all non-zero normals. Stubs are capped or disabled when opposing normals have insufficient port separation (< 4 px → disable; 4–20 px → cap). Escape indices recorded in `RouteCandidate.escape_indices`. ELK path deferred: ELK produces AABB-aligned waypoints that lack polygon-boundary geometry; adding shape-aware stubs requires deep ELK adapter changes beyond this spec's scope (deferred: flowchart-connector-elk-attachment).
- [x] AC10: Trunk-only orthogonality achieved via escape-to-escape routing: A* routes from escape point to escape point, `_ensure_orthogonal()` is applied to the trunk, then boundary stubs are wrapped. `_ensure_orthogonal_trunk()` in `_routing.py` is the building-block for callers that already have stubs in the path.
- [x] AC11: Geometry unit tests: rectangle, diamond, hexagon, trapezoid, flag, circle, ellipse, rounded rect, stadium, double circle — point on boundary, normal unit & outward, escape outside shape.
- [x] AC12: Route contract tests with new validation rule names.
- [x] AC13: All existing tests still pass; `pytest tests/ -q --tb=short --ignore=tests/fidelity` exits clean.
- [x] AC14: `tests/test_route_validation.py` updated to check `terminal_normal_source`/`terminal_normal_target` instead of `axis_aligned_terminal`.

## Testing Strategy

- TDD for geometry unit tests (AC11): write stubs first, implement, make green.
- Goal-based for routing change (AC9, AC10): verify no test regressions + visual gallery check.
- Existing route_validation tests updated in lockstep with validation change.

## Task List

1. [x] Read and understand current architecture
2. [x] Add `BoundaryAttachment` to `shape_geometry.py` and `attachment()` method on all shapes (AC1–AC3)
3. [x] Fix `port_planner.py` normal computation + add `TerminalAttachment` (AC4–AC5)
4. [x] Fix `route_validation.py` — replace axis-aligned check, update port_normals (AC6–AC8)
5. [x] Fix `_pipeline.py` — add escape stubs + `_ensure_orthogonal_trunk` (AC9–AC10); implemented in `_pipeline.py` not `_routing.py`
6. [x] Write `tests/test_boundary_attachment.py` (AC11)
7. [x] Write `tests/test_route_contract.py` (AC12)
8. [x] Update `tests/test_route_validation.py` rule names (AC14)
9. [x] Run full test suite (AC13)

## Boundaries

Do NOT touch:
- `_pipeline.py` Fix4 Z-turn gate guard (`_is_tb ... Z-turn` block, PR #242 — line numbers shift as surrounding code grows)
- `_equalize_corridors` gate_coords chain-grow block (PR #242 — do not modify those lines; additions alongside are acceptable)
- Self-loop routing geometry (separate concern)
- Visual debug overlay (deferred — O)

Added alongside (not modifying) gate_coords logic:
- Single-neighbor endpoint protection in Pass B of `_equalize_corridors`: protects index 1 / index n-2 when they share the endpoint's x, preventing diagonal terminal segments on cardinal CBE routes that carry no escape index. A full chain-grow was considered and rejected — it locks gate corridors.

## Declined patterns

- Full `AttachmentCache` class — computed on demand is sufficient
- Rewrite `_astar_route` for float coordinates — stub insertion at float precision is sufficient
- Global `geometry_debug_mode` flag — debug overlay is deferred
- Moving escape-stub logic into port_planner — routing layer owns this since it has node coords
- CBE cardinal source stubs — deferred; shifting the A* start 20 px along a cardinal normal can cause label-crossing regressions because the CBE sparse grid is label-unaware. Fix requires adding label row/column coordinates to `_cbe_build_grid` so A* avoids them. Non-cardinal source stubs are applied; destination stubs apply to all non-zero normals.
