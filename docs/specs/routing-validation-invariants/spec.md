# Spec: Routing Validation Invariants

Mode: full (structural — new module `route_validation.py`; multi-feature initiative item)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** ini-004 Shared Orthogonal Routing Foundation (maputo-v1); no ADR/RFC governs this spec
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Introduce `route_validation.py` — a standalone routing-layer validation module
that checks `RouteCandidate` + `PortReservation` objects against hard invariants
from the initiative brief. Returns a list of `ValidationError` typed records;
does not raise on invariant violations. Complements (does not replace) the
existing `validate_finalized_layout` in `_geometry.py`, which operates on
`FinalizedLayout`.

No changes to `_geometry.py`, `_pipeline.py`, or any diagram-type file.

**HTML/SVG-identical invariant** ("HTML and SVG consume identical finalized
points") is explicitly out of scope for this module — it operates on rendered
output strings, not route objects, and belongs in a renderer-layer conformance
check. The brief invariant "repeated runs produce identical normalized geometry"
is covered by AC13 (determinism).

## Boundaries

### Always do

- Import from `port_planner.py` only.
- Keep all new code in `route_validation.py`.
- Return `ValidationError` objects; never raise for invariant violations.
- Use `edge_id` as the key for all per-edge errors.
- Be deterministic: identical inputs → identical output list (same order, same content).
- Guard degenerate routes (< 2 waypoints, or first or last segment with length
  < 1e-9 px) with a `rule="malformed_route"` error rather than propagating an exception.

### Ask first

- Any integration into `_geometry.py`, `_pipeline.py`, or any diagram-type file.
- Any change to `port_planner.py` or `route_search.py`.

### Never do

- Add a new pip dependency (only stdlib `math`).
- Touch `_geometry.py`, `_pipeline.py`, `_routing.py`, or any diagram-type file.
- Raise exceptions for invariant violations (use ValidationError instead).
- Share logic with `validate_finalized_layout` in `_geometry.py`
  (the two modules operate on different types).

## Testing Strategy

- **TDD** — all ACs use red-green-refactor; each invariant has an explicit
  passing case (no violation) and a failing case (violation detected).

## Declined patterns

- Tempted to integrate with `_geometry.py` by delegating from
  `validate_finalized_layout` — declining: that function operates on
  `FinalizedLayout` / `RoutedEdge`, not `RouteCandidate`; wiring deferred.
- Tempted to raise `ValueError` on invariant violation — declining: callers
  need to inspect all violations, not just the first.
- Tempted to add `RoutedEdge`-aware checks — declining: `RoutedEdge` is in
  `_geometry.py`'s layer; this module stays in the routing layer.

## Assumptions

1. `RouteCandidate.points` is a tuple of ≥ 2 `(x, y)` floats. A route is
   malformed when (a) `len(points) < 2`, or (b) the first segment (points[0]→points[1])
   has length < 1e-9, or (c) the last segment (points[-2]→points[-1]) has length < 1e-9.
   The module emits `rule="malformed_route"` and skips that route's remaining checks.
2. Axis-aligned segment: `|Δx| < 1e-9` or `|Δy| < 1e-9` (floating-point
   tolerance; absolute value required).
3. Port-normal consistency:
   - Source: the L2-normalized direction of the first segment must agree with
     `source.outward_normal` within 1e-9 per component. "Agree" means the unit
     vectors are equal (same direction).
   - Target: the L2-normalized direction of the last segment must agree with the
     *negated* `target.outward_normal` (i.e., `(-tnx, -tny)`) within 1e-9 per
     component — because the route approaches the target from outside.
   - When `outward_normal` is (0,0) (center port), the check is skipped for that
     endpoint (both source and target).
   - Zero-length terminal segment is malformed (covered by Assumption 1/AC14).
4. Terminal length — target side: the last segment's Euclidean length must be ≥
   `marker_depths.get(edge_id, 0.0) + 4.0`. When no marker_depth is given,
   the minimum is 4.0 px. `marker_depths` defaults to `None`; the function
   coerces it to `{}` at entry.
5. Terminal length — source side: the first segment's length must be ≥ 4.0 px
   (fixed minimum; no configurable depth). This catches routes where the source
   terminal leaves the node with insufficient clearance.
6. Dogleg threshold: intermediate segments (segment indices 1..n-3, i.e., all
   segments except the first and last, for routes with ≥ 4 waypoints) shorter
   than 4 px are violations. For routes with < 4 waypoints, no intermediate
   segments exist. First and last segments have their own checks (Assumptions 4
   and 5) and are exempt from the dogleg check.
7. Obstacle intersection: a segment `(A, B)` intersects an obstacle AABB when
   the segment's parametric overlap with the AABB interior is positive (Liang-
   Barsky test). A segment collinear with an AABB edge (denominator = 0 in the
   clip test) is treated as non-intersecting (touching the boundary, not passing
   through the interior). `kind = "node"` and `kind = "group"` produce violations;
   other kinds are not checked. `obstacles` defaults to `None`; coerced to `[]`
   at entry. Callers are responsible for excluding source and target nodes from
   the obstacle set when the route's terminal segment would otherwise touch them.
8. Canvas bounds: all `(x, y)` in `route.points` must satisfy
   `cx ≤ x ≤ cx + cw` and `cy ≤ y ≤ cy + ch`. When `canvas_bounds` is None,
   this check is skipped.
9. Shared segment > 8 px: two distinct routes share a segment when they both
   traverse a common axis-aligned interval longer than 8 px (same orientation,
   co-linear within 1e-9, overlapping). Each violating route gets its own
   `ValidationError`.
10. Port-on-reservation: verifies `route.source_port.point == reservation.port_candidate.point`
    (within 1e-6 px per component). This is the routing-layer proxy for the
    broader "port lies on its visible outline" invariant; the outline invariant
    is satisfied transitively because `endpoint_geometry.py` guarantees
    `outline_intersection == port_candidate.point` at marker-geometry time.
    A route without a matching reservation skips this check.
11. Route start/end: `route.points[0]` must equal `route.source_port.point`
    within 1e-6 px; `route.points[-1]` must equal `route.target_port.point`.
12. `marker_depths` is separate from `PortReservation.terminal_clearance` because
    no current producer sets `terminal_clearance`; this module uses a caller-
    supplied dict to avoid depending on a field that is always 0.0 in practice.
13. `obstacles: list | None = None` — coerced to `[]` at entry, matching the
    type annotation and avoiding the mutable-default issue.
14. For routes with exactly 2 waypoints, the single segment is simultaneously
    the first and last; per-terminal checks (axis_aligned, port_normal, terminal_length)
    run independently for both roles and may each emit an error. No deduplication is
    applied — a caller counting errors for a 2-waypoint route may see up to 2 errors
    per per-terminal rule.
15. Python 3.13 runtime.

## Resolve-vs-surface disposition record

Opened at PLAN. Closed at DECIDE.

| Question | Resolution |
|---|---|
| Return errors or raise? | Return list of ValidationError — callers need all violations. |
| Integrate into _geometry.py? | No — different type layers; deferred. |
| Canvas check when None? | Skip silently (Assumption 8). |
| Center port normal check? | Skip when outward_normal == (0,0) (Assumption 3). |
| Obstacle kinds other than node/group? | Not checked (Assumption 7). |
| HTML/SVG identical invariant? | Out of scope (renderer layer); noted in Objective. |
| Port-on-outline vs port-on-reservation? | Transitively correct via endpoint_geometry; noted in Assumption 10. |
| Source terminal length? | 4px minimum, separate from configurable target marker_depth (Assumption 5). |
| Degenerate routes? | rule="malformed_route"; skip remaining checks for that route (Assumption 1). |
| Obstacle set includes connected nodes? | Callers exclude them; documented in Assumption 7. |
| marker_depths default? | None, coerced to {} (Assumption 12, Assumption 13). |

## Acceptance Criteria

- [x] AC1: `ValidationError` and `validate_routes` importable from
  `scripts.mermaid_render.layout.route_validation`.
- [x] AC2: `ValidationError` is a `NamedTuple` with fields
  `edge_id: str`, `rule: str`, `detail: str`.
- [x] AC3: A valid set of routes (all AC4-AC12 invariants satisfied) produces `[]`.
  This test uses a complete fixture placed after T5 when all checks exist.
- [x] AC4: Port-on-reservation violation is detected:
  `route.source_port.point` differs from `reservation.port_candidate.point`
  by > 1e-6 px → `ValidationError` with `rule="port_on_reservation"`.
- [x] AC5: Route start/end violation is detected:
  `route.points[0]` differs from `route.source_port.point` → `rule="route_start"`;
  `route.points[-1]` differs from `route.target_port.point` → `rule="route_end"`.
- [x] AC6: Non-axis-aligned first or last segment is detected →
  `rule="axis_aligned_terminal"`.
- [x] AC7: Port-normal mismatch is detected:
  - First segment direction disagrees with source `outward_normal` →
    `rule="port_normal_source"`.
  - Last segment direction disagrees with the *negated* target `outward_normal`
    (i.e., direction ≠ `(-tnx, -tny)`) → `rule="port_normal_target"`.
  - Center ports (`outward_normal == (0,0)`) are exempt at both source and target.
- [x] AC8: Terminal-too-short violations:
  - Last segment length < `marker_depths.get(edge_id, 0.0) + 4.0` → `rule="terminal_length"`.
  - First segment length < 4.0 px → `rule="terminal_length"`.
- [x] AC9: Dogleg-too-short violation: for a route with ≥ 4 waypoints, an
  intermediate segment (index 1..n-3) shorter than 4 px → `rule="dogleg_too_short"`.
  First and last segments are exempt.
- [x] AC10: Obstacle intersection violation: a route segment passes through a
  node or group obstacle → `rule="obstacle_intersection"`. Collinear-with-boundary
  (touching the AABB edge without passing through its interior) does not trigger.
- [x] AC11: Canvas bounds violation: a route point lies outside canvas_bounds →
  `rule="canvas_bounds"`. Skipped when canvas_bounds is None.
- [x] AC12: Shared-segment violation: two distinct routes share an axis-aligned
  segment > 8 px → each edge gets its own `ValidationError` with
  `rule="shared_segment"`.
- [x] AC13: `validate_routes` is deterministic — calling it twice with identical
  inputs returns the same list (same elements, same order).
- [x] AC14: Malformed routes produce `rule="malformed_route"` and do not raise:
  - a route with < 2 waypoints;
  - a route whose first segment (points[0]→points[1]) has length < 1e-9;
  - a route whose last segment (points[-2]→points[-1]) has length < 1e-9.
- [x] AC15: All existing `pytest tests/ -x -q` tests pass (no regressions).
