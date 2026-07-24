# Spec: Routing Endpoint Marker Geometry

Mode: full (structural — new module `endpoint_geometry.py`; multi-feature initiative item)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** ini-004 Shared Orthogonal Routing Foundation (maputo-v1); no ADR/RFC governs this spec
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Introduce `endpoint_geometry.py` — the module that converts a finalized
orthogonal route into precise per-endpoint geometry: where the visible outline
meets the route, where the marker tip and base sit, where the visible line
starts, and the terminal segment's tangent direction, plus a flag indicating
whether the preceding bend must be merged. This is independent of routing
search (depends only on spec 1's data model), enabling diagram-type renderers
to compute accurate arrowhead placement and terminal-segment trimming without
implementing their own endpoint logic.

No diagram-type-specific changes in this spec. Existing rendering code is
read-only here.

## Boundaries

### Always do

- Consume `PortCandidate`, `PortReservation`, and `RouteCandidate` from
  `port_planner.py`.
- Define a new `EndpointGeometry` NamedTuple (immutable) in this module.
- Implement terminal-segment length check: segment must be `≥ marker_depth + 4 px`
  (the 4 px provides clearance to prevent a marker from being drawn from a
  one-pixel stub and leaves room for the renderer to apply rounding without
  colliding with the boundary). When shorter, set `merge_required=True`.
- Derive marker orientation exclusively from the terminal (last unsmoothed)
  segment direction; fall back to `port_candidate.outward_normal` negated
  when the terminal segment has zero length.
- Keep all new code in `endpoint_geometry.py`; do not modify any existing file.
- Use bare `X | None` syntax; no `Optional` import.

### Ask first

- Any change to `port_planner.py` data structures.
- Any change to `FinalizedLayout` or existing marker painters.

### Never do

- Add a new pip dependency.
- Touch `_routing.py`, `_pipeline.py`, `_geometry.py`, or any diagram-type file.
- Apply corner rounding during endpoint computation (rounding is a renderer
  concern, not a geometry concern).
- Use the AABB bounding box as the outline intersection when a `shape_geometry`
  instance is provided — call `boundary_anchor` for exact intersection.

## Testing Strategy

- **TDD** — all six endpoint components (`outline_intersection`, `marker_tip`,
  `marker_base`, `line_endpoint`, `tangent`, `merge_required`), the
  terminal-segment length check, and the degenerate zero-length segment case
  use red-green-refactor.
- **Goal-based check** — import smoke: `python -c "from scripts.mermaid_render.layout.endpoint_geometry import EndpointGeometry, compute_endpoint_geometry"` exits 0. AC1 is also implied by the tests for AC2/AC3 which must import the module.

## Declined patterns

- Tempted to implement corner rounding in this module — declining: the
  editorial corner condition (`both adjacent segments > 2 * corner_radius +
  terminal_clearance`) is documented for the renderer; no coordinates are
  transformed here.
- Tempted to return a modified points list — declining: the function returns
  `EndpointGeometry` with the six components; polyline modification is the
  caller's responsibility.
- Tempted to merge the preceding bend automatically when `merge_required=True`
  — declining: bend merging changes route topology; this module only signals
  the requirement.
- Tempted to support source-end marker geometry — declining: this spec computes
  only the target-end geometry; source-end markers (double-headed arrows) are
  a follow-on use case. Callers who need source-end geometry should call
  `compute_endpoint_geometry` with the route reversed.

## Assumptions

1. `PortReservation.port_candidate.point` is the canonical port location on
   the visible shape boundary for the target end of the route (confirmed from
   spec 1). Spec 3 computes target-end geometry only.
2. The terminal segment is the last segment of `RouteCandidate.points`:
   `points[-2]` → `points[-1]`. The route must have at least two points.
   `RouteCandidate.points` is an orthogonal polyline (spec 1 guarantee), so
   each segment is axis-aligned, making L1 normalization equivalent to L2.
3. `marker_depth` is a caller-supplied float (px). Typical value: 8 px for
   standard arrowheads; 0 for no-marker edges.
4. `outline_intersection` equals `port_reservation.port_candidate.point` — no
   recomputation. Spec 1's `generate_port_candidates` already called
   `boundary_anchor`; this module trusts the result.
5. When the terminal segment has zero length (`points[-1] == points[-2]` within
   1e-9), the tangent falls back to the negated `port_candidate.outward_normal`
   and `merge_required` is `True` (the segment is by definition too short).
6. The faithful/editorial flags document rendering conditions only; no
   coordinate transformation is applied by this module.
7. Python 3.13 runtime.

## Resolve-vs-surface disposition record

Opened at PLAN. Closed at DECIDE.

| Question | Resolution |
|---|---|
| Should corner rounding coords be computed here or in the renderer? | Renderer — this module flags conditions, doesn't transform points. |
| Should outline_intersection re-call boundary_anchor or trust port_candidate.point? | Trust it — spec 1 already called boundary_anchor (Assumption 4). |
| Should merge_required trigger an automatic bend merge in this module? | No — signals only; caller decides topology change. |
| Source-end marker geometry: in or out of scope? | Out of scope for spec 3; use reversed route as a workaround. |
| Zero-length terminal segment: crash or fallback? | Fallback to negated outward_normal + merge_required=True (Assumption 5). |

## Acceptance Criteria

- [ ] AC1: `EndpointGeometry` and `compute_endpoint_geometry` are importable
  from `scripts.mermaid_render.layout.endpoint_geometry`.
- [ ] AC2: `EndpointGeometry` is immutable (NamedTuple): direct assignment
  raises `AttributeError`.
- [ ] AC3: `EndpointGeometry` has exactly six fields:
  - `outline_intersection: tuple[float, float]` — visible shape boundary point
  - `marker_tip: tuple[float, float]` — where the arrowhead tip meets the boundary
  - `marker_base: tuple[float, float]` — where the line must stop; equals
    `outline_intersection − marker_depth × tangent` (inward offset, opposite to
    terminal segment direction; see AC7 for formula)
  - `line_endpoint: tuple[float, float]` — where the visible line ends
  - `tangent: tuple[float, float]` — unit vector of the terminal segment direction
  - `merge_required: bool` — True when terminal segment < marker_depth + 4 px
- [ ] AC4: `compute_endpoint_geometry` returns an `EndpointGeometry` for the
  target endpoint of a `RouteCandidate` given a `PortReservation` and
  `marker_depth`.
- [ ] AC5: `outline_intersection` equals `port_reservation.port_candidate.point`
  (no recomputation). Verified by constructing a reservation with a known point
  distinct from any AABB anchor.
- [ ] AC6: `marker_tip` equals `outline_intersection` (the marker tip meets the
  visible boundary exactly).
- [ ] AC7: `marker_base` equals `outline_intersection` offset inward by
  `marker_depth`: `(ox − marker_depth × tx, oy − marker_depth × ty)` where
  `(tx, ty)` is the unit tangent. For tangent `(1, 0)` and depth `8`, starting
  at `(100, 50)`: `marker_base == (92.0, 50.0)`.
- [ ] AC8: `line_endpoint` equals `marker_base` when `marker_depth > 0`; equals
  `outline_intersection` when `marker_depth == 0`.
- [ ] AC9: `tangent` is a unit vector in the terminal segment direction (from
  `points[-2]` toward `points[-1]`). For a horizontal right-going segment,
  `tangent == (1.0, 0.0)`; for vertical upward, `tangent == (0.0, -1.0)`.
  When the terminal segment has zero length, falls back to the negated
  `port_candidate.outward_normal` (Assumption 5). When the fallback normal is
  also `(0, 0)` (center port), `tangent == (0.0, 0.0)` and `merge_required`
  is `True`.
- [ ] AC10: `merge_required` is `True` when `terminal_segment_length <
  marker_depth + 4` (strict less-than); `False` when `terminal_segment_length
  == marker_depth + 4` (boundary is not a merge case).
- [ ] AC11: `compute_endpoint_geometry` never applies corner rounding in any
  mode; the returned geometry reflects the unsmoothed orthogonal polyline. The
  editorial corner condition (`both adjacent segments > 2 * corner_radius +
  terminal_clearance`) is a renderer precondition, not computed here.
- [ ] AC12: All existing `pytest tests/ -x -q` tests pass (no regressions).
