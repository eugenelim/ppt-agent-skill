**Mode: full (multi-feature, dependent tasks, unfamiliar algorithm territory)**
**Status: Shipped**

## Objective

Improve the diagram routing engine so parallel routes no longer visually overlap
(tramlines). Three targeted fixes guided by the 10-step routing pipeline document:
(1) raise A* occupied-channel penalty, (2) raise Z-route shared-segment cost,
(3) add post-routing lane assignment to physically separate routes forced into the
same channel.

## Acceptance Criteria

- [x] AC1: A* cross-penalty (CROSS) raised from 60 → 300 so occupied channels cost
        5× more relative to a same-length detour.
- [x] AC2: Z-route `shared_segment_length` multiplier raised from 12 → 80 so
        overlapping Z-candidates are strongly discouraged when alternatives exist.
- [x] AC3: `_assign_lanes()` function added to `_pipeline.py`; detects route pairs
        with shared segment > 8 px and offsets the later route by ±12 px (vertical
        or horizontal, with L→Z stub conversion for endpoint-aligned horizontals).
- [x] AC4: `_assign_lanes()` called immediately before routes are converted to
        waypoint dicts.
- [~] AC5: infra-topology renders with zero tramlines > 20px. component-architecture
        has three CBE tramlines (GI→NP+GI→BD: 131px+48px, EX→NP+GI→NP: 60px)
        at shared boundary gates — accepted as a funnel constraint (multiple routes
        must converge at the same group-boundary gate point; A* vertical soft-cost
        produces worse zigzag routes when applied to the sparse CBE grid).
- [x] AC6: Existing test suite passes (lint + typecheck + tests).

## Boundaries

- Files touched: `_routing.py`, `route_search.py`, `_pipeline.py`
- NOT changing: ELK node placement, port assignment, CBE boundary gate logic,
  SVG rendering, any other feature outside routing.

## Testing Strategy

Visual / manual QA — render both fixtures and verify no tramlines. Unit tests:
existing suite; no new test files added (routing is integration-level tested via
snapshot tests).

## Assumptions

- `RouteCandidate` is a `NamedTuple` (supports `._replace()`).
- `RoutingObstacle.bounds` is `(x, y, w, h)` (x=left, y=top, w=width, h=height).
- Routes forced into the same channel (no obstacle-free alternative) will still
  overlap if both offset directions are blocked; this is accepted — the lane
  assignment degrades gracefully.
