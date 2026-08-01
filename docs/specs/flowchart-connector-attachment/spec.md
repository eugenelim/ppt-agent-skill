# Flowchart Connector Terminal-Geometry Fix

**Mode:** Full (structural change — new attachment contract, multi-file)
**Status:** In Progress

## Objective

Fix flowchart connector attachment so terminal segments leave/enter every supported shape perpendicular to its actual local boundary — not perpendicular to the AABB bounding-box — and routes are built escape-to-escape with the orthogonal trunk between escape points.

## Acceptance Criteria

- [ ] AC1: `BoundaryAttachment` NamedTuple in `shape_geometry.py` with `point`, `outward_normal`, `side`, `face_id`, `at_corner` fields.
- [ ] AC2: `ShapeGeometry` protocol exposes `attachment(side, offset, w, h, *, preferred_direction=None) -> BoundaryAttachment`.
- [ ] AC3: All 13 registered shapes implement `attachment()`.
- [ ] AC4: `port_planner.generate_port_candidates()` populates `PortCandidate.outward_normal` from `shape_geometry.normal_at()` when shape_geometry provided; not from `_SIDE_NORMALS` lookup.
- [ ] AC5: `TerminalAttachment` NamedTuple and `build_terminal_attachment()` helper in `port_planner.py`.
- [ ] AC6: `route_validation._check_axis_aligned()` replaced by `terminal_normal_source` and `terminal_normal_target` checks using dot-product tolerance ≥ 0.9998.
- [ ] AC7: New `orthogonal_trunk` check validates inner segments (between escape points) are axis-aligned.
- [ ] AC8: `_check_port_normals()` updated to use dot-product tolerance rather than exact equality.
- [ ] AC9: `_routing._add_normal_stubs()` inserts boundary→escape stub at source and escape→boundary stub at target for polygon-clipped shapes; cardinal shapes produce collinear stubs (no visible change).
- [ ] AC10: `_routing._ensure_orthogonal_trunk()` replaces `_ensure_orthogonal()` — only orthogonalizes the trunk (between escape points), preserving terminal stubs.
- [ ] AC11: Geometry unit tests: rectangle, diamond, hexagon, trapezoid, flag, circle, ellipse, rounded rect, stadium, double circle — point on boundary, normal unit & outward, escape outside shape.
- [ ] AC12: Route contract tests with new validation rule names.
- [ ] AC13: All existing tests still pass; `pytest tests/ -q --tb=short --ignore=tests/fidelity` exits clean.
- [ ] AC14: `tests/test_route_validation.py` updated to check `terminal_normal_source`/`terminal_normal_target` instead of `axis_aligned_terminal`.

## Testing Strategy

- TDD for geometry unit tests (AC11): write stubs first, implement, make green.
- Goal-based for routing change (AC9, AC10): verify no test regressions + visual gallery check.
- Existing route_validation tests updated in lockstep with validation change.

## Task List

1. [x] Read and understand current architecture
2. [ ] Add `BoundaryAttachment` to `shape_geometry.py` and `attachment()` method on all shapes (AC1–AC3)
3. [ ] Fix `port_planner.py` normal computation + add `TerminalAttachment` (AC4–AC5)
4. [ ] Fix `route_validation.py` — replace axis-aligned check, update port_normals (AC6–AC8)
5. [ ] Fix `_routing.py` — add escape stubs + `_ensure_orthogonal_trunk` (AC9–AC10)
6. [ ] Write `tests/test_boundary_attachment.py` (AC11)
7. [ ] Write `tests/test_route_contract.py` (AC12)
8. [ ] Update `tests/test_route_validation.py` rule names (AC14)
9. [ ] Run full test suite (AC13)

## Boundaries

Do NOT touch:
- `_pipeline.py` lines 3750–3772 (Fix4 Z-turn gate guard, PR #242)
- `_equalize_corridors` gate_coords logic (PR #242)
- Self-loop routing geometry (separate concern)
- Visual debug overlay (deferred — O)

## Declined patterns

- Full `AttachmentCache` class — computed on demand is sufficient
- Rewrite `_astar_route` for float coordinates — stub insertion at float precision is sufficient
- Global `geometry_debug_mode` flag — debug overlay is deferred
- Moving escape-stub logic into port_planner — routing layer owns this since it has node coords
