# Spec: Routing Port-Planner Foundation

Mode: full (structural — new module introducing shared data contracts; multi-feature initiative item)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** ini-004 Shared Orthogonal Routing Foundation (maputo-v1); no ADR/RFC governs this spec
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Introduce the shared port-aware routing data model and port-pair planning
module (`port_planner.py`) that all diagram-type renderers in ini-004 will
build on. The module defines four immutable data structures and four planning
functions, giving every subsequent routing spec (search, assignment, validation)
a common vocabulary without requiring them to invent their own port or route
representations.

No diagram-type-specific logic changes in this spec. Existing routing code
(`_routing.py`, `_pipeline.py`) is read-only here.

## Boundaries

### Always do

- Use `NamedTuple` for all four data structures (immutable by construction,
  zero runtime overhead, works with Python 3.8+).
- Use `edge_id` as the primary key everywhere; never key a structure solely
  by `(source_id, destination_id)`.
- Call `ShapeGeometry.boundary_anchor(side, offset, w, h)` for exact boundary
  points when a shape_geometry instance is provided; fall back to AABB
  interpolation otherwise. `boundary_anchor` returns node-local (top-left
  origin) coordinates; add the node's canvas offset to produce the absolute
  `point` in `PortCandidate`.
- Keep all new code in `port_planner.py`; do not modify any existing file
  in this spec.
- Add types and a one-line docstring to every public function.

### Ask first

- Any change to the `ShapeGeometry` protocol or `SHAPE_REGISTRY`.
- Any change to `FinalizedLayout` or `_pipeline.py`.

### Never do

- Key a data structure solely by `(source_id, destination_id)`.
- Mutate a `NamedTuple` after construction (no `_replace` in production
  paths unless building a new immutable value).
- Add a new pip dependency (`requirements.txt` is fixed; any addition
  requires an RFC).
- Touch `_routing.py`, `_pipeline.py`, `_geometry.py`, or any
  diagram-type file in this spec.
- Add another general graph-layout engine.

## Testing Strategy

- **TDD** — all four data structures (immutability, field presence) and all
  four functions (invariants, edge cases) use red-green-refactor.
- **Goal-based check** — import check (`python -c "from scripts.mermaid_render.layout.port_planner import PortCandidate, PortReservation, RouteCandidate, RoutingObstacle, build_edge_lists, generate_port_candidates, plan_straight_corridor, fan_slots"`) exits 0.

## Declined patterns

- Tempted to add constructor helpers / builder methods for `RoutingObstacle`,
  `PortReservation`, `RouteCandidate` — declining: these three structures are
  vocabulary-only in this spec; they are built and consumed by downstream specs
  (routing-search-and-assignment, routing-validation-invariants). Adding helpers
  now would over-specify the construction contract before callers exist.
- Tempted to keep `node_id` and `node_bounds` in `fan_slots` signature — declining:
  the normalized-offset formula `(i+1)/(n+1)` never reads them, and AGENTS.md
  prohibits parameters with no current caller. `side` is retained because
  per-side distribution behaviour is expected to diverge in a follow-on spec.
- Tempted to add an `edges` parameter to `generate_port_candidates` for fan-slot
  offset distribution — declining: the current implementation hardcodes offset 0.5
  for all candidates; per-edge fan distribution is `fan_slots`'s job (spec 1 Task 5).
  AGENTS.md prohibits parameters with no current reader.
- Tempted to make `generate_port_candidates` return `PortReservation` objects —
  declining: reservations require an escape_point that only the routing search
  (spec 2) can compute after graph analysis.

## Assumptions

1. `boundary_anchor(side, offset, w, h)` returns **node-local** (top-left
   origin) coordinates, not canvas coordinates (confirmed from shape_geometry.py
   line 97–109). `generate_port_candidates` adds `node_x, node_y` to produce
   the canvas-absolute `point`.
2. Python 3.13 is the runtime; `NamedTuple` and `frozenset` are both available
   without back-compat shims. Use bare `X | None` syntax throughout (no
   `Optional` import needed).
3. `plan_straight_corridor` assumes the caller has normalized direction
   (`src` is the upstream / earlier-rank node). Reverse corridors are out of scope.
4. Degenerate inputs (zero-size nodes, empty edge lists) are out of scope for
   explicit error handling; functions return empty lists or `None` naturally.
   Zero-size bounds may produce degenerate geometry in AABB calculations — callers
   are responsible for providing valid bounds.

## Resolve-vs-surface disposition record

Opened at PLAN. To be closed at DECIDE.

| Question | Resolution |
|---|---|
| Should `RoutingObstacle.permitted_gate_ids` use `frozenset[str]` or `tuple[str, ...]`? | `frozenset[str]` — gates are semantically unordered; frozenset makes membership O(1) and is hashable. |
| Should `generate_port_candidates` accept target node bounds for straight-through projection? | No — the straight-through case is handled by the caller via `plan_straight_corridor`; keep the function signature lean. |
| NamedTuple vs frozen dataclass for immutability? | NamedTuple — zero overhead, no `@dataclass(frozen=True)` decorator needed, simpler for typing. |

## Acceptance Criteria

- [ ] AC1: `PortCandidate`, `PortReservation`, `RouteCandidate`, `RoutingObstacle`
  are importable from `scripts.mermaid_render.layout.port_planner`.
- [ ] AC2: All four structures are immutable — direct attribute assignment on any
  of `PortCandidate`, `PortReservation`, `RouteCandidate`, `RoutingObstacle`
  raises `AttributeError`.
- [ ] AC3: Every *edge-derived* structure (`PortCandidate`, `PortReservation`,
  `RouteCandidate`) carries an `edge_id` field. `RoutingObstacle` is keyed by
  `obstacle_id` (it represents a region, not an edge).
- [ ] AC4: `generate_port_candidates` with `fixed_side="top"` returns candidates
  exclusively on the `"top"` side (all with `fixed_side=True`,
  `preference_penalty=0.0`).
- [ ] AC5: `generate_port_candidates` with `fixed_side=None` returns at minimum
  one candidate per side in `{"top", "right", "bottom", "left"}` plus one
  `"center"` candidate, covering all five sides.
- [ ] AC6: For non-center candidates computed via `shape_geometry.boundary_anchor`,
  the resulting `point` lies on the shape outline within 0.5 px (verified for
  `RectGeometry` which has an exact AABB boundary). The `"center"` candidate's
  `point` is `(node_x + w/2, node_y + h/2)` and is excluded from the
  on-outline check.
- [ ] AC7: `plan_straight_corridor` returns `("vertical", x)` when `src_bounds`
  and `dst_bounds` share a non-empty horizontal (x-axis) overlap and `src` is
  strictly above `dst` (i.e. `sy + sh < dy`).
- [ ] AC8: `plan_straight_corridor` returns `("horizontal", y)` when `src_bounds`
  and `dst_bounds` share a non-empty vertical (y-axis) overlap and `src` is
  strictly left of `dst` (i.e. `sx + sw < dx`).
- [ ] AC9: `plan_straight_corridor` returns `None` when neither a vertical nor a
  horizontal corridor applies (e.g. diagonal relationship with no overlap).
- [ ] AC13: The vertical and horizontal corridor guards are mutually exclusive:
  `sy+sh < dy` (vertical) implies `sx+sw ≥ dx` makes the horizontal x-overlap
  impossible, and vice versa. A directly-above pair with full x-overlap returns
  `("vertical", …)` and never reaches the horizontal guard.
- [ ] AC10: `fan_slots` for `n` edges returns exactly `n` pairs, all
  `normalized_offset` values distinct, all in `(0.0, 1.0)` exclusive, and no
  two slots at the same offset.
- [ ] AC11: All existing `pytest tests/ -x -q` tests pass (no regressions).
- [ ] AC12: `build_edge_lists` returns a dict mapping each node that appears as a
  source or target to a list containing the `edge_id` of each incident edge; a
  node that appears in multiple edges appears once with all its incident edge
  IDs.
