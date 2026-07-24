# Plan: Routing Search and Assignment

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially,
> note why in the changelog at the bottom.

## Approach

Introduce `scripts/mermaid_render/layout/route_search.py` with seven public
functions and one private helper. All consume `PortCandidate`/`RoutingObstacle`
from `port_planner.py` and produce `RouteCandidate` objects. The riskiest part
is `assign_routes`'s rip-up/reroute loop — the `max_iterations` cap and
deterministic ordering keep it bounded. `route_edge` uses `existing_routes` to
compute real `shared_segment_length` for candidate cost, enabling non-conflicting
variants to win on reroute. Local-channel and sparse-A* paths are not implemented.
Tests use red-green-refactor per task.

## Constraints

- All data structures from `port_planner.py` (AC1).
- Cost formula coefficients exact (AC2); `zero_bend_route_count` derived from
  `rc.bend_count == 0`, not a kwarg.
- Conflict threshold `> 8 px` (strict, AC10).
- Shared-segment detection is O(n²) in edge count — acceptable for < 50 edges.
- No new pip dependencies.

## Construction tests

**Integration tests:** T6's `test_assign_routes_conflict_resolved` exercises the
full pipeline: two edges whose initial L-routes share > 8px → rip-up/reroute
produces a non-conflicting Z variant for the higher-cost edge.

**Manual verification:** import smoke (AC1) — one-liner at end of T1.

## Design (LLD)

### Interfaces & contracts

Public surface:

```python
def compute_route_cost(
    rc: RouteCandidate,
    *,
    port_collision_count: int = 0,
    label_overlap_count: int = 0,
    near_obstacle_penalty: float = 0.0,
    nonpreferred_side_count: int = 0,
    aligned_endpoint_count: int = 0,
) -> float
# zero_bend_route_count derived internally: 1 if rc.bend_count == 0 else 0

def try_direct_route(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
) -> RouteCandidate | None

def try_l_route(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
) -> list[RouteCandidate]  # up to 2 candidates (hv and vh variants)

def try_z_route(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
) -> list[RouteCandidate]  # up to 2 candidates (mid-x and mid-y pivot)

def route_edge(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
    obstacles: tuple[RoutingObstacle, ...] = (),
    existing_routes: tuple[RouteCandidate, ...] = (),
) -> RouteCandidate | None

def prioritize_edges(
    edge_ids: list[str],
    fixed_side_ids: set[str],
    cross_scope_ids: set[str],
    high_degree_ids: set[str],
    zero_bend_ids: set[str],
) -> list[str]

def assign_routes(
    requests: list[dict],   # [{"edge_id": str, "src_port": PC, "dst_port": PC}, ...]
    obstacles: tuple[RoutingObstacle, ...] = (),
    max_iterations: int = 10,
) -> dict[str, RouteCandidate]
```

Private helper:

```python
def _is_valid_route(rc: RouteCandidate,
                    obstacles: tuple[RoutingObstacle, ...]) -> bool
```

### Data & schema

- Route points: `tuple[tuple[float, float], ...]` (orthogonal polyline waypoints).
- Segment: consecutive point pair from the polyline.
- Shared-segment: two segments co-linear on the same axis with overlap > 8 px.
- Cost kwargs: all default to 0; `zero_bend_route_count` is always derived from
  `rc.bend_count == 0` (not a kwarg) so the call is deterministic.
- `try_*` cost: passes only the fields computable from geometry (`bend_count`,
  `length`, `crossing_count=0`, `shared_segment_length` against
  `existing_routes`). Penalty kwargs default to 0 inside `try_*`.

### Behavior & rules

- Direct: `abs(sx - dx) < 1e-9` (vertical) or `abs(sy - dy) < 1e-9` (horizontal). Points: `(src.point, dst.point)`.
- L hv: corner at `(dst.point[0], src.point[1])`. Vh: corner at `(src.point[0], dst.point[1])`.
- Z mid-x: mid = `(sx + dx) / 2`; waypoints `(sx,sy) → (mid,sy) → (mid,dy) → (dx,dy)`.
- Z mid-y: mid = `(sy + dy) / 2`; waypoints `(sx,sy) → (sx,mid) → (dx,mid) → (dx,dy)`.
- `_is_valid_route`: uses separating-axis AABB test for each segment vs. each
  obstacle's `bounds`. Permitted gate IDs not checked (stub: always rejects
  intersection).
- `shared_segment_length`: for each candidate in `route_edge`, iterate over
  `existing_routes`, find segments on the same axis, compute overlap length.
  Sum overlaps → `shared_segment_length` field.
- `prioritize_edges`: stable-sort by group index (0=fixed_side, 1=cross_scope,
  2=high_degree, 3=zero_bend, 4=remaining); first-match group determines rank
  for multi-group edges.
- `assign_routes` rip-up: after each full routing pass, find all pairs of
  assigned routes with a shared segment > 8 px; rip up the higher-cost one;
  reroute it by calling `route_edge` with updated `existing_routes`; repeat
  until no conflicts or `max_iterations` reached. Returns best-effort result
  at cap.

## Tasks

### T1: Importable module + cost function (AC1, AC2) — stub: true

**Depends on:** none

**Tests:**
- `test_import_smoke` (AC1): seven public names importable from
  `scripts.mermaid_render.layout.route_search`.
- `test_compute_route_cost_zero_bend_unit_route` (AC2): RouteCandidate with
  length=1.0, bend_count=0, crossing_count=0, shared_segment_length=0.0;
  `compute_route_cost(rc, aligned_endpoint_count=1)` == -219.0.
- `test_compute_route_cost_full_formula` (AC2): verify the eight
  independently-settable coefficients; the derived zero_bend coefficient is
  covered by the zero-bend test.

**Approach:**
- Create `route_search.py`; import PortCandidate, RouteCandidate, RoutingObstacle.
- Implement `compute_route_cost` with exact formula; derive
  `zero_bend_route_count = 1 if rc.bend_count == 0 else 0` internally.
- Stub the remaining six public functions as `raise NotImplementedError`
  (tagged `# STUB: AC<n>`); stub `_is_valid_route` likewise.

**Done when:** import smoke and two cost tests pass.

### T2: Direct route detection (AC3) — stub: true

**Depends on:** T1

**Tests:**
- `test_try_direct_route_vertical` (AC3): src=(50,0), dst=(50,100) → bend_count=0.
- `test_try_direct_route_horizontal` (AC3): src=(0,50), dst=(100,50) → bend_count=0.
- `test_try_direct_route_diagonal` (AC3): offset → None.
- `test_try_direct_route_within_epsilon` (AC3): diff=5e-10 → direct route found.

**Approach:**
- Replace T1 stub; implement `try_direct_route`.
- Check `abs(sx - dx) < 1e-9` (vertical) or `abs(sy - dy) < 1e-9` (horizontal).
- Build RouteCandidate with `crossing_count=0`, `shared_segment_length=0.0`,
  `cost=compute_route_cost(rc_partial)`, `bend_count=0`.

**Done when:** four direct-route tests green.

### T3: L-route and Z-route (AC4, AC5) — stub: true

**Depends on:** T1, T2

**Tests:**
- `test_try_l_route_bend1` (AC4): offset ports → at least one RC with bend_count=1.
- `test_try_l_route_two_variants` (AC4): two variants returned for generic offset.
- `test_try_z_route_bend2` (AC5): offset ports → at least one RC with bend_count=2.
- `test_try_z_route_midpoint_x` (AC5): src=(0,0), dst=(100,100) Z mid-x at x=50.
- `test_try_z_route_midpoint_y` (AC5): src=(0,0), dst=(100,100) Z mid-y at y=50.

**Approach:**
- Replace T1 stubs; implement `try_l_route` and `try_z_route`.
- L hv corner at `(dx, sy)`, vh at `(sx, dy)`.
- Z mid-x and mid-y variants as per design rules.
- Build RouteCandidate for each, computing cost.

**Done when:** five L/Z tests green.

### T4: _is_valid_route + route_edge with existing_routes (AC6, AC7) — stub: true

**Depends on:** T1-T3

**Tests:**
- `test_is_valid_route_no_obstacles`: RC with no obstacles → True.
- `test_is_valid_route_intersecting_obstacle` (AC7): RC whose segment passes
  through obstacle bounds → False.
- `test_route_edge_prefers_direct` (AC6): direct exists → bend_count=0.
- `test_route_edge_falls_back_to_l` (AC6): offset ports → bend_count=1.
- `test_route_edge_all_invalid` (AC7): all candidates intersect obstacle → None.
- `test_route_edge_existing_routes_increase_cost` (AC6): when `existing_routes`
  overlaps an L candidate, a non-overlapping Z candidate wins on cost.

**Approach:**
- Implement `_is_valid_route` with separating-axis AABB test.
- Implement `route_edge`: compute `shared_segment_length` against
  `existing_routes` for each candidate; filter by `_is_valid_route`; return
  min-cost or None.

**Done when:** six tests green.

### T5: prioritize_edges (AC8) — stub: true

**Depends on:** T1

**Tests:**
- `test_prioritize_edges_fixed_first` (AC8): fixed-side edges before others.
- `test_prioritize_edges_full_five_groups` (AC8): all five groups in order.
- `test_prioritize_edges_stable_within_group` (AC8): original order preserved.
- `test_prioritize_edges_multi_group_first_match` (AC8): edge in fixed+high-degree
  → appears in fixed-side group only.

**Approach:**
- Implement using stable-sort by group index; first-match determines group.

**Done when:** four prioritize_edges tests green.

### T6: assign_routes with rip-up/reroute (AC9, AC10, AC12) — stub: true

**Depends on:** T1-T5

**Tests:**
- `test_assign_routes_basic` (AC9): two non-conflicting edges → both in dict.
- `test_assign_routes_conflict_resolved` (AC10): two L-routes sharing > 8px →
  rip-up/reroute resolves; result has no pair sharing > 8px segment.
- `test_assign_routes_max_iterations_cap` (AC10): pathological input confirms
  loop exits after max_iterations; no exception raised.
- `test_assign_routes_unroutable_excluded` (AC9): edge with no valid route absent.
- `test_assign_routes_deterministic` (AC12): two calls with identical input →
  identical dict.

**Approach:**
- Implement `assign_routes`; shared-segment detection is O(n²) per round.
- Rip-up loop: find conflicting pairs, rip the higher-cost, reroute with
  updated existing_routes. Cap at `max_iterations`.

**Done when:** five assign_routes tests green; `pytest tests/ -x -q` passes.

### T7: Regression pass (AC11)

**Depends on:** T1-T6

**Tests:**
- `pytest tests/ -x -q` → full suite green.

**Approach:**
- Run full suite; fix any import collisions or accidental side-effects.

**Done when:** 0 failures in full suite.

## Rollout

No infra or external-system changes. Pure Python, no new dependencies.
Backwards-compatible: no existing file is modified.

## Risks

- Shared-segment detection is O(n²) in edge count — acceptable for < 50 edges;
  noted in `assign_routes` docstring.

## Changelog

- 2026-07-24: initial plan
- 2026-07-24: post-review — added `existing_routes` wiring to route_edge; fixed
  shared-segment threshold to strict > 8px; renamed is_valid_route to
  _is_valid_route; added AC12 determinism; added multi-group membership AC8 test;
  tightened AC3 epsilon; aligned shared_segment_length term naming; dropped
  off-canvas stub reference.
