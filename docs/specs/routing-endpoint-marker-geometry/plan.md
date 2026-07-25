# Plan: Routing Endpoint Marker Geometry

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially,
> note why in the changelog at the bottom.

## Approach

Introduce `scripts/mermaid_render/layout/endpoint_geometry.py` with one
`EndpointGeometry` NamedTuple and one public function `compute_endpoint_geometry`.
The module imports only from `port_planner.py`. The riskiest part is the tangent
sign (inward vs. outward) and the zero-length terminal-segment fallback — both
have clear invariants verified by TDD across all four cardinal directions.
Corner rounding is documented but not applied (renderer concern). Tests use
red-green-refactor per task.

## Constraints

- `EndpointGeometry` must be immutable NamedTuple with exactly six fields (AC2, AC3).
- `tangent` is normalized via L1 norm; valid because `RouteCandidate.points`
  is an orthogonal polyline (spec 1 guarantee: each segment is axis-aligned,
  so L1 == L2 for axis-aligned vectors).
- `marker_base = outline − depth × tangent` (inward, AC7). Implementers must
  subtract (not add) `depth × tangent`.
- Zero-length terminal: fallback to negated `port_candidate.outward_normal`,
  `merge_required=True` (AC9, Assumption 5).
- No new pip dependencies.

## Construction tests

**Integration tests:** T3's `test_compute_endpoint_full_pipeline` exercises the
full pipeline: a RouteCandidate + PortReservation → all six fields correct.

**Manual verification:** import smoke (AC1).

## Design (LLD)

### Interfaces & contracts

```python
class EndpointGeometry(NamedTuple):
    outline_intersection: tuple[float, float]
    marker_tip: tuple[float, float]
    marker_base: tuple[float, float]
    line_endpoint: tuple[float, float]
    tangent: tuple[float, float]
    merge_required: bool

def compute_endpoint_geometry(
    route: RouteCandidate,
    reservation: PortReservation,
    marker_depth: float = 0.0,
) -> EndpointGeometry
```

### Behavior & rules

- `outline_intersection = reservation.port_candidate.point`.
- `marker_tip = outline_intersection`.
- Terminal segment: `points[-2]` → `points[-1]`.
- Raw tangent vector: `(points[-1][0] - points[-2][0], points[-1][1] - points[-2][1])`.
- L1 norm: `n = abs(raw_tx) + abs(raw_ty)`.
  - If `n < 1e-9` (zero-length segment): fall back to negated `outward_normal`;
    set `merge_required = True` regardless of depth.
  - Else: `tangent = (raw_tx / n, raw_ty / n)`.
- `terminal_length = n` (already computed; same as L1 for axis-aligned).
- `marker_base = (ox - marker_depth * tx, oy - marker_depth * ty)`.
- `line_endpoint = marker_base if marker_depth > 0 else outline_intersection`.
- `merge_required = terminal_length < marker_depth + 4` (strict; unless already
  set True by zero-length fallback).

## Tasks

### T1: EndpointGeometry data structure (AC1, AC2, AC3) — stub: true

**Depends on:** none

**Tests:**
- `test_import_smoke` (AC1): both names importable.
- `test_endpoint_geometry_immutable` (AC2): `AttributeError` on assignment.
- `test_endpoint_geometry_fields` (AC3): all six field names present.

**Approach:**
- Create `endpoint_geometry.py`; import PortCandidate, PortReservation,
  RouteCandidate from port_planner.
- Define `EndpointGeometry` NamedTuple with six fields.
- Stub `compute_endpoint_geometry` as `raise NotImplementedError # STUB: AC4`.

**Done when:** three structure tests pass.

### T2: tangent, merge_required, marker_base (AC7, AC9, AC10) — stub: true

**Depends on:** T1

**Tests:**
- `test_tangent_horizontal_right` (AC9): terminal going right → `(1.0, 0.0)`.
- `test_tangent_horizontal_left` (AC9): terminal going left → `(-1.0, 0.0)`.
- `test_tangent_vertical_down` (AC9): terminal going down → `(0.0, 1.0)`.
- `test_tangent_vertical_up` (AC9): terminal going up → `(0.0, -1.0)`.
- `test_tangent_zero_length_fallback` (AC9, Assumption 5): terminal length 0 →
  fallback to negated outward_normal; `merge_required=True`.
- `test_merge_required_true` (AC10): `terminal_length=5, depth=8` → 5 < 12 → True.
- `test_merge_required_false_boundary` (AC10): `terminal_length=12, depth=8` →
  12 == 12 → False (boundary is not a merge case).
- `test_merge_required_false_long` (AC10): `terminal_length=20, depth=8` → False.
- `test_marker_base_right_tangent` (AC7): outline=(100,50), depth=8, tangent=(1,0)
  → marker_base=(92.0, 50.0).
- `test_marker_base_down_tangent` (AC7): outline=(0,0), depth=8, tangent=(0,1)
  → marker_base=(0.0, -8.0).
- `test_compute_outline_intersection` (AC5): reservation with known point (42.0, 17.0)
  → result.outline_intersection == (42.0, 17.0) (not an AABB anchor, proving pass-through).
- `test_compute_marker_tip_equals_outline` (AC6): marker_tip == outline_intersection.
- `test_compute_no_marker` (AC8): depth=0 → line_endpoint == outline_intersection.
- `test_compute_with_marker` (AC8): depth=8 → line_endpoint == marker_base.

**Approach:**
- Replace T1 stub; implement the full `compute_endpoint_geometry` function.
  All six fields populated in one pass using the design rules.

**Done when:** ten tangent/merge/base tests pass.

### T3: Integration verification (AC4) — goal-based

**Depends on:** T1, T2

**Tests:**
- `test_compute_endpoint_full_pipeline` (AC4): RouteCandidate with 3 points,
  PortReservation with known coordinates → all six fields non-None, internally
  consistent (marker_base derived from outline + depth, line_endpoint == marker_base).

**Approach:**
- Construct a minimal 3-point route and a PortReservation; verify the returned
  EndpointGeometry is a well-formed, internally consistent result.

**Done when:** integration test passes.

### T4: No-rounding assertion (AC11) — TDD

**Depends on:** T3

**Tests:**
- `test_no_rounding_applied` (AC11): drive with a 3-point route (S-bend near
  the terminal region); assert each returned coordinate equals the exact
  `route.points`-derived value — specifically that `line_endpoint` equals
  `marker_base` (computed from raw points), not a smoothed position.
  The test would fail if any midpoint smoothing were applied.

**Approach:**
- No new code needed; verify the existing implementation satisfies AC11.
- Add a one-line comment to the module documenting the editorial corner condition:
  `# Editorial: renderer may round a corner when both adjacent segments > 2*radius+clearance`.

**Done when:** one test pass; comment present.

### T5: Regression pass (AC12)

**Depends on:** T1-T4

**Tests:**
- `pytest tests/ -x -q` → full suite green.

**Done when:** 0 failures.

## Rollout

No infra or external-system changes. Pure Python, no new dependencies.

## Risks

None significant — self-contained module with no side-effects.

## Changelog

- 2026-07-24: initial plan
- 2026-07-24: post-review — added zero-length fallback (Blocker 2); fixed AC3
  marker_base direction (Blocker 1); added all four cardinal direction tests;
  added merge_required boundary test; added L1-normalization constraint;
  fixed AC5 tautology; reworded AC11; added source-end declined pattern;
  corrected Construction tests cross-reference name.
