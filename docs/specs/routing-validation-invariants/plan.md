# Plan: Routing Validation Invariants

- **Spec:** [`spec.md`](spec.md)
- **Status:** Shipped

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially,
> note why in the changelog at the bottom.

## Approach

Introduce `scripts/mermaid_render/layout/route_validation.py` with two public
names: `ValidationError` (NamedTuple) and `validate_routes` (the checker).
Each of the 12 invariant families has a dedicated helper; `validate_routes`
calls them in order and collects all errors. All tests use red-green-refactor.
The riskiest parts are (a) the Liang-Barsky AABB–segment intersection test,
(b) the shared-segment detection across all pairs of routes, and (c) the
degenerate-route guard that must emit `rule="malformed_route"` without raising.

## Constraints

- No new pip dependencies (stdlib `math` only).
- Never raise for invariant violations; always return `ValidationError` objects.
- Never touch `_geometry.py`, `_pipeline.py`, or any diagram-type file.
- Deterministic output: same error order across identical calls.
- Degenerate routes: emit `rule="malformed_route"` and skip remaining checks.

## Construction tests

**Integration tests:** T6's `test_valid_routes_all_invariants` exercises all
invariants together on one well-formed route set.

## Design (LLD)

### `ValidationError`

```python
class ValidationError(NamedTuple):
    edge_id: str
    rule: str    # short identifier e.g. "port_on_reservation"
    detail: str  # human-readable description
```

### `validate_routes` interface

```python
def validate_routes(
    routes: list[RouteCandidate],
    reservations: dict[str, PortReservation] | None = None,
    obstacles: list[RoutingObstacle] | None = None,
    canvas_bounds: tuple[float, float, float, float] | None = None,
    marker_depths: dict[str, float] | None = None,
) -> list[ValidationError]:
    reservations = reservations or {}
    obstacles = obstacles or []
    marker_depths = marker_depths or {}
    ...
```

Returns all violations found, one `ValidationError` per (edge_id, rule, detail)
tuple. Order: per-edge checks in route order (malformed_route → port_on_reservation
→ route_start/end → axis_aligned → port_normal → terminal_length → dogleg →
obstacle → canvas), then cross-route shared-segment checks (in route-pair order).

### Invariant implementations

**Degenerate guard** (first, before all other per-edge checks):
Emit `rule="malformed_route"` and skip remaining per-edge checks when:
  - `len(route.points) < 2`, OR
  - first segment length `hypot(Δx01, Δy01) < 1e-9`, OR
  - last segment length `hypot(Δx-2-1, Δy-2-1) < 1e-9`.
(A 2-waypoint route with a zero-length segment satisfies both terminal checks at once.)

**Port-on-reservation** (`_check_port_on_reservation`):
For each route, look up `reservations.get(edge_id)`. If found, compare
`route.source_port.point` with `reservation.port_candidate.point` (each
component, tolerance 1e-6). The reservation covers the source endpoint only
(one reservation per edge_id); no target comparison is performed.
Emit `rule="port_on_reservation"`.

**Route start/end** (`_check_route_endpoints`):
Compare `route.points[0]` with `route.source_port.point` (tolerance 1e-6).
Emit `rule="route_start"` or `rule="route_end"`.

**Axis-aligned terminals** (`_check_axis_aligned`):
First segment: `(points[0], points[1])`. Axis-aligned iff `|Δx| < 1e-9 or |Δy| < 1e-9`.
Same for last segment `(points[-2], points[-1])`. Emit `rule="axis_aligned_terminal"`.

**Port-normal consistency** (`_check_port_normals`):
First segment direction: `(Δx, Δy) = points[1] - points[0]`; L2-normalize
(`mag = sqrt(Δx²+Δy²); unit = (Δx/mag, Δy/mag)`). Zero-length segment is
malformed — already caught by the degenerate guard above; this function may
assume non-zero length.
- Source: if `source.outward_normal == (0,0)`: skip. Otherwise compare unit
  direction component-wise to `outward_normal` within 1e-9. Emit `rule="port_normal_source"`.
- Target: if `target.outward_normal == (0,0)`: skip. Otherwise L2-normalize the
  last segment direction `points[-1] - points[-2]` and compare to
  `(-tnx, -tny)` (negated outward_normal) within 1e-9.
  Emit `rule="port_normal_target"`.
For 2-waypoint routes, both source and target checks run on the same segment;
up to two errors may be emitted (per spec Assumption 14 — no deduplication).

**Terminal length** (`_check_terminal_length`):
Last segment length = `hypot(points[-1][0]-points[-2][0], points[-1][1]-points[-2][1])`.
Minimum target = `marker_depths.get(edge_id, 0.0) + 4.0`. Emit `rule="terminal_length"`.
First segment: same formula; minimum = `4.0` (fixed). Also `rule="terminal_length"`.

**Dogleg too short** (`_check_dogleg`):
For routes with ≥ 4 waypoints, check segment indices 1..n-3 where n = len(points).
Segment i spans `(points[i], points[i+1])`; if length < 4 px → `rule="dogleg_too_short"`.
First (index 0) and last (index n-2) segments are exempt.

**Obstacle intersection** (`_check_obstacles`):
For each route, for each segment `(A, B)`, for each obstacle where
`kind in ("node", "group")`: test using Liang-Barsky parametric clip.
`(ox, oy, ow, oh) = obstacle.bounds`. Clip t ∈ [0, 1] against four half-planes:
  - left: `t_enter = (ox - ax) / (bx - ax)` (if bx ≠ ax), `t_exit = (ox+ow - ax) / (bx - ax)`
  - right, top, bottom: analogously.
  - If denominator = 0 (segment parallel to plane): not intersecting if
    segment is outside the slab; otherwise both t values unchanged.
  - After all clips: `t0 < t1` and `t1 > 0` and `t0 < 1` → INTERSECTS.
  - `t0 ≥ t1` or `t1 ≤ 0` or `t0 ≥ 1` → no intersection.
  - A collinear segment (denominator = 0 for both parallel planes) touches the
    AABB boundary edge but is treated as non-intersecting.
Emit `rule="obstacle_intersection"`.
**Note:** callers must exclude the route's own source and target nodes from the
`obstacles` list; the module does not filter them.

**Canvas bounds** (`_check_canvas`):
When `canvas_bounds = (cx, cy, cw, ch)` is not None: for each `(px, py)` in
`route.points`, check `cx ≤ px ≤ cx+cw` and `cy ≤ py ≤ cy+ch`.
Emit `rule="canvas_bounds"`.

**Shared segment** (`_check_shared_segments`):
For each pair of routes (i, j) with i < j, for each segment in routes[i],
for each segment in routes[j]:
- Horizontal (same y within 1e-9): `overlap = min(x1_i, x1_j) - max(x0_i, x0_j)`
  where x0/x1 are sorted x-endpoints.
- Vertical (same x within 1e-9): same with y.
- Otherwise: not co-linear, skip.
If `overlap > 8.0 px`: emit one `ValidationError` for `routes[i].edge_id` and
one for `routes[j].edge_id`, both `rule="shared_segment"`.

## Tasks

### T1: Module scaffold + ValidationError (AC1, AC2) — stub: true

**Depends on:** none

**Tests:**
- `test_import_smoke` (AC1): `ValidationError` and `validate_routes` importable.
- `test_validation_error_fields` (AC2): `ValidationError(edge_id="e1", rule="r", detail="d")`
  → fields accessible by name.

**Approach:**
- Create `route_validation.py`; define `ValidationError` NamedTuple; stub
  `validate_routes` to return `[]`.

**Done when:** 2 tests pass.

### T2: Malformed-route guard + endpoint invariants (AC4, AC5, AC14) — stub: true

**Depends on:** T1

**Tests:**
- `test_malformed_route_under_2_waypoints` (AC14): route with 1 point →
  `ValidationError(rule="malformed_route")`; no exception raised.
- `test_malformed_route_zero_first_segment` (AC14): 2-waypoint route where
  `points[0] == points[1]` → `rule="malformed_route"`; no exception.
- `test_malformed_route_zero_last_segment` (AC14): 3-waypoint route where
  `points[-2] == points[-1]` → `rule="malformed_route"`; no exception.
- `test_port_on_reservation_violation` (AC4): source port mismatch → `rule="port_on_reservation"`.
- `test_port_on_reservation_no_reservation_ok` (AC4): missing reservation → no error.
- `test_route_start_violation` (AC5): `points[0]` ≠ source_port.point → `rule="route_start"`.
- `test_route_end_violation` (AC5): `points[-1]` ≠ target_port.point → `rule="route_end"`.

**Done when:** 5 tests pass.

### T3: Segment geometry invariants (AC6, AC7, AC8, AC9) — stub: true

**Depends on:** T1

**Tests:**
- `test_axis_aligned_first_segment_violation` (AC6): non-axis-aligned first → `rule="axis_aligned_terminal"`.
- `test_axis_aligned_last_segment_violation` (AC6): non-axis-aligned last → `rule="axis_aligned_terminal"`.
- `test_port_normal_source_violation` (AC7): wrong first-segment direction → `rule="port_normal_source"`.
- `test_port_normal_target_violation` (AC7): wrong last-segment direction → `rule="port_normal_target"`.
- `test_port_normal_center_port_source_exempt` (AC7): source outward_normal=(0,0) → no port_normal_source error.
- `test_port_normal_center_port_target_exempt` (AC7): target outward_normal=(0,0) → no port_normal_target error.
- `test_terminal_length_target_violation` (AC8): last segment < marker_depth+4 → `rule="terminal_length"`.
- `test_terminal_length_source_violation` (AC8): first segment < 4 px → `rule="terminal_length"`.
- `test_dogleg_too_short_violation` (AC9): 4-waypoint route; intermediate segment < 4 px →
  `rule="dogleg_too_short"`.
- `test_dogleg_first_last_exempt` (AC9): 2-waypoint route with short first/last → no dogleg error.
- `test_2waypoint_terminal_length_double_emit` (Assumption 14): a 2-waypoint route whose
  single segment is < 4 px long (with marker_depth=0) must yield exactly 2
  `terminal_length` ValidationErrors — one from the first-segment check, one from
  the last-segment check. This pins the no-deduplication contract.

**Done when:** 9 tests pass.

### T4: Obstacle + canvas invariants (AC10, AC11) — stub: true

**Depends on:** T1

**Tests:**
- `test_obstacle_intersection_violation` (AC10): route segment through node AABB →
  `rule="obstacle_intersection"`.
- `test_obstacle_boundary_touch_ok` (AC10): segment collinear with AABB edge → no error.
- `test_canvas_bounds_violation` (AC11): route point outside canvas → `rule="canvas_bounds"`.
- `test_canvas_none_skip` (AC11): `canvas_bounds=None` → no canvas check.

**Done when:** 4 tests pass.

### T5: Shared segment + determinism (AC12, AC13) — stub: true

**Depends on:** T1

**Tests:**
- `test_shared_segment_violation` (AC12): two routes share > 8 px horizontal segment →
  two ValidationErrors (one per route) with `rule="shared_segment"`.
- `test_shared_segment_short_ok` (AC12): shared overlap ≤ 8 px → no error.
- `test_deterministic` (AC13): two identical calls → same list.

**Done when:** 3 tests pass.

### T6: All-invariants clean test + regression (AC3, AC15)

**Depends on:** T1-T5

**Tests:**
- `test_valid_routes_all_invariants` (AC3): a fixture satisfying all AC4-AC12 invariants
  passes `validate_routes` with result `[]`. (This must be placed after T5 so all checks
  are implemented and the test is non-vacuous.)
- `pytest tests/ -x -q` → full suite green (AC15).

**Done when:** 0 failures.

## Rollout

No infra or external-system changes. Pure Python, no new dependencies.

## Risks

- Liang-Barsky AABB–segment test has degenerate cases (parallel segment, collinear
  with boundary). Parameterised tests cover these explicitly in T4.
- Shared-segment detection is O(routes² × segments²) — acceptable at spec-time scale.
- Clean-route test (AC3/T6) is only meaningful after all checks are implemented;
  placing it in T6 prevents false-pass during T2-T5.

## Changelog

- 2026-07-24: initial plan
- 2026-07-24: post-adversarial-review rewrite: fixed marker_depths/obstacles defaults
  (None not ()), off-by-one dogleg range (1..n-3 not 1..n-2), added malformed-route
  guard (AC14), source terminal length check (AC8), collinear-obstacle clarification,
  noted HTML/SVG invariant out of scope, added port-on-reservation transitivity note,
  moved clean-route test to T6.
- 2026-07-24: second pass: extended malformed-route guard to zero-length first/last
  segments; fixed L1→L2 normalization in port-normal spec/plan; added two AC14 tests.
