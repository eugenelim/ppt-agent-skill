# Spec: Routing Search and Assignment

Mode: full (structural — new module `route_search.py`; multi-feature initiative item)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** ini-004 Shared Orthogonal Routing Foundation (maputo-v1); no ADR/RFC governs this spec
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Introduce `route_search.py` — the routing algorithm layer that turns port
candidates into fully-costed route candidates and assigns one final route to
every edge. It sits above `port_planner.py` (data model, port generation) and
below diagram-type renderers, giving every renderer a shared way to: compute a
deterministic cost for any route candidate, search for routes in a fixed
priority order (direct → L → Z), and run a global assignment pass with bounded
rip-up/reroute when segments conflict. No diagram-type-specific logic changes
in this spec.

## Boundaries

### Always do

- Consume `PortCandidate` and `RoutingObstacle` exclusively from
  `port_planner.py`; produce `RouteCandidate` using the same module.
- Implement the deterministic cost objective exactly as specified (see AC2).
- Keep all new code in `route_search.py`; do not modify existing files.
- Add types and a one-line docstring to every public function.
- Use bare `X | None` syntax throughout; no `Optional` import.

### Ask first

- Any change to `port_planner.py` data structures.
- Any change to `FinalizedLayout` or `_pipeline.py`.
- Adding local-channel or sparse-A* path — deferred; ask first.

### Never do

- Key a structure solely by `(source_id, destination_id)`.
- Add a new pip dependency.
- Touch `_routing.py`, `_pipeline.py`, `_geometry.py`, or any diagram-type
  file in this spec.
- Share a segment between distinct edges unless they have an explicit junction.
- Implement local-channel or sparse-A* path in this spec (deferred to backlog).

## Testing Strategy

- **TDD** — all routing functions (cost formula, direct/L/Z detection,
  priority ordering, assign_routes with rip-up/reroute) use red-green-refactor.
- **Goal-based check** — import smoke: `python -c "from
  scripts.mermaid_render.layout.route_search import compute_route_cost,
  try_direct_route, try_l_route, try_z_route, route_edge,
  prioritize_edges, assign_routes"` exits 0.

## Declined patterns

- Tempted to implement local-channel path — declining: adds significant
  complexity without a concrete caller; `route_edge` returns None past Z-path.
- Tempted to implement sparse A* — declining: A* needs a working obstacle grid
  that requires diagram-pipeline integration, out of scope here.
- Tempted to add a `RoutingGrid` class with full ELK-style grid insertion —
  declining: the grid is implicit in the route-form functions; explicit grid
  objects belong in a future spec integrating with `elk_adapter.py`.
- Tempted to expose `_is_valid_route` as a public function — declining: it is
  an internal helper; `_` prefix signals that to callers.

## Assumptions

1. PortCandidate, RouteCandidate, RoutingObstacle are imported from
   `port_planner.py` (confirmed: spec 1 shipped in #209).
2. Python 3.13 runtime; bare `X | None` syntax throughout.
3. `try_z_route` midpoint is the arithmetic mean of the two port coordinates on
   the unbounded axis — no obstacle avoidance at this level.
4. `_is_valid_route` treats a RoutingObstacle's `bounds` as an axis-aligned
   bounding box and checks each route segment for AABB intersection.
   No permitted-gate-id logic in this spec (always rejects intersection).
5. `assign_routes` rip-up/reroute cap is 10 iterations; deterministic order
   means identical inputs always produce identical output. Post-cap contract:
   returns best-effort assignments with any remaining conflicts left as-is.
6. Shared-segment conflict threshold is `> 8 px` axis-aligned overlap (strict
   greater-than, matching AC10).
7. An edge's group membership for `prioritize_edges` is determined by first
   match in priority order: fixed-side → cross-scope → high-degree → zero-bend
   → remaining. An edge in two groups counts only in the higher-priority group.
8. The `try_*` functions pass only fields derivable from the route geometry
   itself when computing candidate cost (see AC2 for the zero_bend derivation).
   Penalty kwargs (`port_collision_count`, `label_overlap_count`, etc.) default
   to 0 inside `try_*` — callers who know the context may recompute with
   `compute_route_cost`.

## Resolve-vs-surface disposition record

Opened at PLAN. Closed at DECIDE.

| Question | Resolution |
|---|---|
| Should `try_z_route` use midpoint or a smarter pivot? | Arithmetic midpoint — deterministic, no obstacle look-ahead at this level. |
| Should `_is_valid_route` handle permitted gate IDs? | No — gates require pipeline context; stub as always-reject-intersection for now. |
| Should `assign_routes` expose its internal conflict graph? | No — internal detail; the return value (dict[str, RouteCandidate]) is the contract. |
| What happens when conflicts remain after max_iterations? | Best-effort: return assignments as-is with remaining conflicts unresolved. |

## Acceptance Criteria

- [ ] AC1: `compute_route_cost`, `try_direct_route`, `try_l_route`,
  `try_z_route`, `route_edge`, `prioritize_edges`, `assign_routes` are
  importable from `scripts.mermaid_render.layout.route_search`.
- [ ] AC2: The cost formula is:

  ```
  cost = length
       + 80  * bend_count
       + 180 * crossing_count
       + 12  * shared_segment_length        (px)
       + 120 * label_overlap_count          (kwarg, default 0)
       + 100 * port_collision_count         (kwarg, default 0)
       + 60  * near_obstacle_penalty        (kwarg, default 0)
       + 50  * nonpreferred_side_count      (kwarg, default 0)
       - 160 * zero_bend_route_count        (derived: 1 if bend_count == 0, else 0)
       - 60  * aligned_endpoint_count       (kwarg, default 0)
  ```

  Verification: a RouteCandidate with `length=1.0`, `bend_count=0`,
  `crossing_count=0`, `shared_segment_length=0.0`, all other fields zero;
  `compute_route_cost(rc, aligned_endpoint_count=1)` equals
  `1.0 - 160.0 - 60.0 = -219.0`.

- [ ] AC3: `try_direct_route` returns a `RouteCandidate` with `bend_count=0`
  when `src_port.point[0]` and `dst_port.point[0]` agree within 1e-9 (vertical)
  or `src_port.point[1]` and `dst_port.point[1]` agree within 1e-9 (horizontal).
  Returns `None` when neither axis aligns.
- [ ] AC4: `try_l_route` returns at least one `RouteCandidate` with
  `bend_count=1` for any pair of ports whose points are offset on both axes.
- [ ] AC5: `try_z_route` returns at least one `RouteCandidate` with
  `bend_count=2` for any pair of ports whose points are offset on both axes.
- [ ] AC6: `route_edge` tries direct first, then L, then Z, and returns the
  lowest-cost valid candidate among all; returns `None` only when all forms
  produce invalid routes.
- [ ] AC7: `route_edge` returns `None` when every candidate route intersects a
  `RoutingObstacle` (all hard-failure cases rejected by `_is_valid_route`).
- [ ] AC8: `prioritize_edges` returns a list with fixed-side edges first, then
  cross-scope, then high-degree-node, then zero-bend candidates, then remaining
  — maintaining original order within each group; an edge in multiple groups
  appears exactly once under its highest-priority group.
- [ ] AC9: `assign_routes` returns a `dict[str, RouteCandidate]` with one
  entry per routable edge (edges with no valid route are absent from the dict).
- [ ] AC10: When two assigned routes share a segment `> 8 px` in common,
  `assign_routes` rips up the higher-cost route and reroutes it (at most
  `max_iterations` total across all conflicts; remaining conflicts after the cap
  are left as-is in the returned dict).
- [ ] AC11: All existing `pytest tests/ -x -q` tests pass (no regressions).
- [ ] AC12: `assign_routes` called twice on identical inputs returns identical
  `dict[str, RouteCandidate]` (determinism).
