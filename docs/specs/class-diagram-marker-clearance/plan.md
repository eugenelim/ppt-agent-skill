# Implementation Plan — class-diagram-marker-clearance

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_strategies.py`
   (`_class_rel_markers`), `scripts/mermaid_render/layout/_routing.py`
   (LR waypoint block ~line 1242, TB waypoint block ~line 1350, class-edge
   label call sites at lines 1256 and 1368),
   `tests/test_class_semantic.py` (new clearance + orientation + label tests),
   `tests/test_oracle.py` (`_mm_class` extractor + `_DIFFERENTIAL` registry),
   `scripts/mermaid_render/_renderer.py` (conditionally, if `render_finalized`
   re-derives waypoints rather than consuming `FinalizedLayout.routed_edges`).
2. Done when: `pytest tests/` passes; `class-relationships-all` fixture renders
   without any marker tip inside a card face; all seven label chips are pairwise
   disjoint; `test_oracle.py` self-consistency green for all class fixtures.
3. Not changing: `_geometry.py` `MarkerSpec` / `MarkerKind` definitions (the
   `clearance` field already exists at default 0.0); `LayoutEdge.source_marker`
   / `target_marker` types (stays `MarkerKind`); HTML marker defs in
   `_renderer.py`; label placement logic for non-class edge types.

**Declined patterns:**
- Patching clearance into `MarkerSpec.__post_init__` as a kind-based default —
  clearance is a UML rendering constant, not a property of the marker shape in
  isolation; it belongs in the operator-to-spec mapping (`_class_rel_markers`).
- Inserting route shortening at the marker-id assignment block around line 897
  in `_routing.py` — no `pts` variable is in scope there. Shortening must go in
  the LR (~line 1242) and TB (~line 1350) waypoint blocks where the actual path
  variable (`_pts_lr` or `_pts`) is available, gated on
  `e.style.startswith("cls")`.
- A `_marker_kind_clearance` shim that checks whether the field is a `MarkerKind`
  enum — class-styled (`cls*`) edges are always built via `_class_rel_markers`,
  which always produces `MarkerSpec` objects; `.clearance` is always present on
  these edges. Read it directly. (Non-class edges such as architecture edges may
  have `MarkerKind` values, but they never enter the class-edge gated branch.)
- Putting the 40 px segment floor inside `_label_on_longest` globally — that
  function is shared with flowchart and stateDiagram edges. Apply the floor only
  at the two class-edge label call sites (LR ~line 1256, TB ~line 1368), not
  inside the function itself.
- Storing label shelf position in any module-level dict — shelf is computed
  per-edge at render time from current card geometry.

## Approach

The change has three independent surfaces: clearance constants, route geometry
(shortening + clip + orientation), and label placement / oracle.

**Clearance constants (T1):** one-line change per operator branch in
`_class_rel_markers` — add `clearance=12.0` or `clearance=9.0` to each
`MarkerSpec(...)` call. All existing tests pass unchanged; new TDD tests assert
the constant per kind.

**Route geometry (T2):** inside the LR (`_pts_lr`, ~line 1242) and TB (`_pts`,
~line 1350) waypoint blocks of `_route_edges` in `_routing.py`, after each path
variable is assembled and before label candidates are generated, add a gated
class-edge shortening pass:
  1. Read `src_clearance = e.source_marker.clearance` and
     `tgt_clearance = e.target_marker.clearance`. These are always `float`
     because class-styled edges are always built via `_class_rel_markers`.
  2. For `tgt_clearance > 0`: compute unit tangent from `pts[-2]` → `pts[-1]`;
     if `tgt_clearance >= segment_len`, fall back to the `pts[-3]` → `pts[-2]`
     tangent (orientation-inversion guard); shorten `pts[-1]`; clamp to
     `dst_node` card face.
  3. For `src_clearance > 0`: same logic at `pts[0]` using reversed tangent from
     `pts[1]` → `pts[0]`; clamp to `src_node` card face.
  4. Clip to card `Rect` (clamp if shortened point went past the face).

Note on dummy-split edges: `_layout_class` does not dummy-split edges — it calls
`_route_edges` directly on the original `_Edge` objects assembled from
`_class_rel_markers`. The shortening reads `e.source_marker.clearance` on the
un-split edge, so SOURCE-end clearance is not dropped. (Add a T2 test confirming
source-end shortening for a multi-rank class edge to guard against this if the
layout algorithm changes.)

**Label placement (T3):** at the two class-edge `_label_on_longest` call sites in
`_route_edges` (LR ~line 1256, TB ~line 1368), compute the longest eligible span
before the call. For a collinear path (all-same-x / all-same-y — the dominant
straight-edge case in class diagrams), the eligible span is the full path length.
If the span is ≥ 40 px, call `_label_on_longest` normally. If < 40 px, fall back
to a deterministic shelf: midpoint of `pts`, offset 4 px perpendicular to the
dominant axis, using `_best_label_pos` so `placed_labels` collision avoidance
applies. The `placed_labels` list is already accumulated across edges in
`_route_edges`; class edges must append to it, not reinitialise it.

**Oracle extractor (T4):** add `_mm_class` to `tests/test_oracle.py`. Self-
contained; no upstream code dependency; can proceed in parallel with T1–T3.

Tasks T1, T3, and T4 have no mutual dependencies. T2 depends on T1. T5 wires
clearance into `_compile_classdiagram` and validates end-to-end; it depends on
T1, T2, and T3.

## Constraints

- `LayoutEdge.source_marker`/`target_marker` stays `MarkerKind` (ELK pipeline
  contract from ADR-001 via `class-diagram-marker-semantics` Declined section).
- Clearance constants are fixed at 12 / 9 / 0 px per the product spec; no
  env-var or per-diagram configurability.
- Oracle extractor must not gate any fixture that was not already conditional on
  mmdc — new extractor joins `_DIFF_FIXTURES` filter naturally via the `"class"`
  key prefix.
- `_label_on_longest` must not change behaviour for non-class edges; the 40 px
  floor and shelf are applied only at the two class-edge call sites.

## Construction tests

**Integration:** render `class-relationships-all.mmd` through `_layout_class` and
assert all seven label chips are pairwise disjoint using their `(lx, ly, w, h)`
bounding rectangles.

**Flowchart regression:** run `pytest tests/test_mermaid_layout.py` after T3 to
confirm label placement for flowchart edges is unchanged.

**Manual verification:** none — all acceptance criteria are automatable.

## Design (LLD)

### Design decisions

- Clearance stored on `MarkerSpec` (not on `_Edge` or derived at paint time) so
  any consumer that reads the spec gets the value without special-casing.
  Traces to: AC1.
- Route shortening inserted in the LR and TB waypoint blocks of `_route_edges`
  (where path variable `_pts_lr` / `_pts` is in scope), not at the marker-id
  block at line 897. Traces to: AC2, AC3, AC4.
- Orientation fallback: when `clearance` ≥ last-segment length, use the
  second-to-last segment's tangent rather than producing an inverted direction.
  Traces to: AC3.
- Label floor evaluated before `_label_on_longest`'s collinear early-exit branch
  (i.e., at the call site, not inside the function) to catch all-same-x / all-
  same-y straight edges. Traces to: AC6.
- Label shelf anchored to the card face (not the canvas edge), ensuring stable
  placement on wide canvases. Traces to: AC8.

### Data & schema

`MarkerSpec.clearance` (existing field, `float = 0.0`) receives nonzero values
from `_class_rel_markers`. No schema migration; the field is already serialised
by `dataclasses.asdict`. Traces to: AC1.

### Component / module decomposition

| Module | Change |
|---|---|
| `layout/_strategies.py` | `_class_rel_markers`: add `clearance=12.0` or `9.0` per kind |
| `layout/_routing.py` | LR + TB waypoint blocks: `_shorten_cls_route` for class edges; class-edge label call sites (~lines 1256, 1368): 40 px floor + shelf before `_label_on_longest` |
| `_renderer.py` | Conditional: add `_shorten_cls_route` call in `render_finalized` if it re-derives waypoints (T5 determines this) |
| `tests/test_class_semantic.py` | `TestMarkerClearance`, `TestRouteShortening`, `TestLabelPlacement` classes |
| `tests/test_oracle.py` | `_mm_class` extractor; register under `"class"` key |

### Behavior & rules

- Clearance per kind: `HOLLOW_TRIANGLE` → 12 px; `FILLED_DIAMOND` → 12 px;
  `HOLLOW_DIAMOND` → 12 px; `OPEN_ARROW` → 9 px; `NONE` → 0 px.
- Shortening direction: last segment tangent for target-end markers; first
  segment tangent for source-end markers.
- Orientation fallback: if `clearance` ≥ last-segment length, use the
  second-to-last segment's tangent (or clamp to card face if only one segment).
- Label segment floor: 40 px (Manhattan length), evaluated over the full path
  including the collinear span for all-same-x / all-same-y edges.
- Shelf offset: 4 px from nearest card face; direction perpendicular to the
  dominant path axis.
- Shelf emitted only when the eligible span is < 40 px.

## Tasks

### T1: Assign nonzero clearance constants in `_class_rel_markers`
**Depends on:** none
Verification: TDD
**Touches:** `scripts/mermaid_render/layout/_strategies.py`,
`tests/test_class_semantic.py`

**Tests:**
- `_class_rel_markers("<|--")[0].clearance == 12.0` (hollow triangle, source)
- `_class_rel_markers("<|..")[0].clearance == 12.0` (hollow triangle, dashed)
- `_class_rel_markers("*--")[0].clearance == 12.0` (filled diamond, source)
- `_class_rel_markers("o--")[0].clearance == 12.0` (hollow diamond, source)
- `_class_rel_markers("-->")[1].clearance == 9.0` (open arrow, target)
- `_class_rel_markers("..>")[1].clearance == 9.0` (open arrow, dashed)
- `_class_rel_markers("..|>")[1].clearance == 12.0` (hollow triangle, target)
- `_class_rel_markers("<|--")[1].clearance == 0.0` (NONE target, unchanged default)
- All 12 existing `TestClassRelMarkers` tests still green (no regression).

**Approach:**
- In `_strategies.py`, edit each `return` in `_class_rel_markers`:
  - `_MS(kind=_MK.HOLLOW_TRIANGLE, end=…)` → add `clearance=12.0`
  - `_MS(kind=_MK.FILLED_DIAMOND, end=…)` → add `clearance=12.0`
  - `_MS(kind=_MK.HOLLOW_DIAMOND, end=…)` → add `clearance=12.0`
  - `_MS(kind=_MK.OPEN_ARROW, end=…)` → add `clearance=9.0`
  - `NONE_SRC` / `NONE_TGT` keep `clearance=0.0` (default, no change).
- Add `TestMarkerClearance` class to `tests/test_class_semantic.py` with the
  per-kind assertions above.

**Done when:** `pytest tests/test_class_semantic.py::TestMarkerClearance` passes;
`pytest tests/test_class_semantic.py::TestClassRelMarkers` still green.

---

### T2: Shorten, orient, and clip route endpoints for class edges in `_route_edges`
**Depends on:** T1
Verification: TDD + goal-based check
**Touches:** `scripts/mermaid_render/layout/_routing.py`,
`tests/test_class_semantic.py`

**Tests:**
- Unit (shortening, vertical TB route):
  route `[(100, 50), (100, 150)]`, target-end clearance 12 px → terminal
  waypoint becomes `(100, 138)`.
- Unit (source-end shortening, same route, clearance 12 px):
  first waypoint becomes `(100, 62)`.
- Unit (orientation preserved after shortening):
  route `[(0, 0), (0, 100)]` shortened by 12 at target → `sign(dy)` of
  final segment is `+1`, same as before shortening.
- Unit (orientation fallback — clearance ≥ segment length):
  two-segment route `[(0, 0), (0, 8), (0, 20)]`, tgt clearance 12 (exceeds
  last segment of 12 px) → falls back to first-segment tangent; `sign(dy)`
  of resulting final segment is `+1`.
- Unit (card clip): after shortening, no waypoint satisfies
  `rect.x < wx < rect.x + rect.w and rect.y < wy < rect.y + rect.h`
  for either endpoint's card `Rect`.
- Unit (SOURCE-end clearance on multi-rank class edge):
  construct a class edge whose `_Edge.source_marker.clearance == 12.0`;
  call `_shorten_cls_route` with `src_clearance=12.0`; assert first waypoint
  shifts 12 px toward target. (Guards against dummy-split concern: in
  `_layout_class`, edges are never dummy-split, so this is a unit-level
  insurance test for `_shorten_cls_route` itself.)
- Goal-based: render `Animal <|-- Dog` via `_layout_class`; extract the `<path>`
  `d=` attribute; confirm the final `L x,y` coordinate is ≥ 12 px from the
  `Animal` card's bottom face (`node.y + node_render_h`).
- Regression: `TestRenderedMarkers` still green; `pytest tests/test_mermaid_layout.py`
  green (no change for non-class edges).

**Approach:**
- Locate the LR waypoint block (variable `_pts_lr`, ~line 1242) and the TB
  waypoint block (variable `_pts`, ~line 1350) inside `_route_edges` in
  `_routing.py`. Both already produce a list of `(x, y)` waypoints.
- After each block assembles its path variable, add:
  ```python
  if e.style.startswith("cls"):
      <path_var> = _shorten_cls_route(
          <path_var>, e.source_marker.clearance,
          e.target_marker.clearance, s, d,
      )
  ```
- Implement `_shorten_cls_route(pts, src_cl, tgt_cl, src_node, dst_node)` as a
  module-level helper in `_routing.py`:
  - For `tgt_cl > 0`: compute unit tangent from `pts[-2]` → `pts[-1]`; if
    `tgt_cl >= segment_len`, use tangent of `pts[-3]` → `pts[-2]`; shorten
    `pts[-1]`; clamp to `dst_node` card face.
  - For `src_cl > 0`: same at `pts[0]` using reversed tangent from `pts[1]`
    → `pts[0]`; clamp to `src_node` card face.
  - Return a new `pts` list (do not mutate in place).
- The direct read `e.source_marker.clearance` is safe here because the
  `e.style.startswith("cls")` gate ensures we are on a class-styled edge, which
  is always built via `_class_rel_markers` → `MarkerSpec` objects. Non-class
  edges (architecture etc.) may use `MarkerKind` directly but never enter this
  branch.

**Done when:** all unit and goal-based tests above pass; `pytest tests/` green.

---

### T3: Enforce 40 px segment floor and label shelf at class-edge call sites
**Depends on:** none
Verification: TDD
**Touches:** `scripts/mermaid_render/layout/_routing.py`,
`tests/test_class_semantic.py`

**Tests:**
- Unit (straight edge ≥ 40 px, collinear all-same-x):
  route `[(0,0),(0,60)]` → full span 60 px ≥ 40 px → label placed near
  midpoint; no shelf.
- Unit (straight edge < 40 px, collinear all-same-x):
  route `[(0,0),(0,20)]` → full span 20 px < 40 px → shelf emitted at
  deterministic offset from nearest card face.
- Unit (shelf determinism):
  calling the shelf logic twice with identical geometry returns identical
  `(lx, ly)` coordinates.
- Integration: render all seven relations from `class-relationships-all.mmd`
  together via `_layout_class`; assert pairwise disjoint label chip rects.
- Regression: `pytest tests/test_mermaid_layout.py` green (flowchart label
  placement unchanged — scope change is call-site-only, not in
  `_label_on_longest` itself).

**Approach:**
- Do not modify `_label_on_longest` itself. Instead, wrap both class-edge
  label call sites in `_route_edges`:
  - LR path: ~line 1256 (`lx, ly = _label_on_longest(…)`)
  - TB path: ~line 1368 (`lx, ly = _label_on_longest(…)`)
- For each site, when `e.style.startswith("cls")`:
  1. Compute `eligible_span`: for all-same-x or all-same-y paths, use
     `abs(pts[-1][1] - pts[0][1])` or `abs(pts[-1][0] - pts[0][0])`; for
     multi-segment paths, use the longest individual segment's Manhattan length.
  2. If `eligible_span >= 40`: call `_label_on_longest` normally.
  3. If `eligible_span < 40`: compute shelf candidate — midpoint of `pts`;
     offset 4 px perpendicular to the dominant axis (horizontal route:
     subtract `_LABEL_CHIP_H + 4` from y; vertical route: add 4 to x); call
     `_best_label_pos([shelf_candidate], e.label, obstacles, placed_labels,
     canvas_w)` so collision avoidance still applies.
- Confirm `placed_labels` is not reset between class edges in the outer loop
  (it is shared across all edges in `_route_edges`; no code change needed if
  it already accumulates — just verify).

**Done when:** unit assertions above pass; integration disjoint-chip test passes;
`pytest tests/test_class_semantic.py` and `pytest tests/test_mermaid_layout.py`
green.

---

### T4: Add `_mm_class` extractor to the mmdc oracle
**Depends on:** none
Verification: goal-based check
**Touches:** `tests/test_oracle.py`

**Tests:**
- Registry smoke: `"class" in _DIFFERENTIAL` evaluates to `True` after the change.
- Self-consistency: `pytest tests/test_oracle.py` with mmdc absent — all class
  fixtures self-consistent (no dangling edge endpoints in our rendered HTML).
- Differential (when mmdc present): `class-relationships-all` fixture passes
  symmetric topology check; seven edges and thirteen nodes extracted from mmdc
  SVG match our rendered `data-src`/`data-dst`/`data-edge-label` attributes.

**Approach:**
- In `test_oracle.py`, add `_mm_class(svg: str)` below `_mm_requirement` (~line
  196). Inspect the actual mmdc SVG for `class-relationships-all` to confirm id
  patterns before committing regexes:
  - Nodes: `<g[^>]+class="classGroup[^"]*"[^>]*>\s*<g[^>]+id="([^"]+)"` (or
    the actual stable id pattern mmdc emits — confirm from real output).
  - Edges: `<path[^>]+id="([A-Za-z0-9_]+)_([A-Za-z0-9_]+)"` — adjust if actual
    mmdc class-edge ids differ.
  - Labels: reuse `_MM_EDGE_LABEL` regex.
  - Return `(nodes, edges, labels)`.
  - Add an inline comment noting the confirmed mmdc SVG pattern and version.
- Register: `_DIFFERENTIAL["class"] = _mm_class`.
- Confirm `"class-relationships-all"` fixture stem starts with `"class"` — it
  does; no further change needed to join `_DIFF_FIXTURES`.

**Done when:** `pytest tests/test_oracle.py -k class` passes (self-consistency
always; differential when mmdc available); `"class" in _DIFFERENTIAL` is True.

---

### T5: Wire clearance into `_compile_classdiagram` and validate end-to-end
**Depends on:** T1, T2, T3
Verification: goal-based check
**Touches:** `scripts/mermaid_render/layout/_strategies.py`,
`tests/test_class_semantic.py`,
`scripts/mermaid_render/_renderer.py` (conditionally)

**Tests:**
- End-to-end: `_compile_classdiagram(FIXTURE_SRC)` produces a `FinalizedLayout`
  where the `RoutedEdgeIR` for `Animal → Dog` (inheritance) has a final waypoint
  ≥ 12 px from the `Animal` card's face.
- Two-paths check: if `_renderer.py`'s `render_finalized` path re-derives
  waypoints (does not consume `FinalizedLayout.routed_edges` directly), render
  the same fixture via `render_finalized` and confirm the same clearance applies.
- Regression: `TestCompileClassdiagram` (all 9 existing tests) still green.
- Smoke: `pytest tests/` exits 0 with no new failures.

**Approach:**
- `_compile_classdiagram` calls `_route_edges` at line 1907 and
  `_build_routed_edges_ir` at line 1928; T2's shortening in `_route_edges`
  means the IR already contains shortened waypoints. Confirm this by asserting
  the waypoint coordinate in the end-to-end test.
- Inspect `_renderer.py`'s `render_finalized` (MEMORY note `renderer-two-paths`):
  if it bypasses `_route_edges` and re-derives waypoints from the original edges,
  add `_shorten_cls_route` there too. If it consumes `FinalizedLayout.routed_edges`
  from the already-shortened IR, no code change is needed — just verify with the
  two-paths test.
- Add `test_compile_clearance_applied` to `TestCompileClassdiagram` in
  `tests/test_class_semantic.py`.

**Done when:** all existing and new tests green; `pytest tests/` exits 0.

## Rollout

Pure Python logic change inside the `mermaid_render` package; no infra, no flag,
no migration. Deploys with the next skill release automatically.

The two absorbed backlog slugs (`class-diagram-route-clip` and
`class-diagram-label-segment` in `workspace.toml`) should be removed from the
open list and the prior spec's deferred-AC comment lines (lines 35–37 of
`docs/specs/class-diagram-marker-semantics/spec.md`) updated to point to this
spec, in the same PR that ships this spec.

## Risks

- **Two render paths:** `_renderer.py` has both a main path and `render_finalized`
  path (MEMORY note `renderer-two-paths`); T5 must verify the shortened waypoints
  reach both. Risk: missing one path and shipping asymmetric behaviour.
- **Collinear branch in `_routing.py`:** `_label_on_longest` has an early-exit
  branch for all-same-x / all-same-y paths (lines 367–371) that bypasses the
  segment-search loop. T3 applies the 40 px floor at the call site before
  `_label_on_longest` is invoked, so this is mitigated — but if the call-site
  wrapping is incorrect the collinear check will silently pass through with no
  floor. The unit test for the 20 px collinear route guards this.
- **mmdc SVG id stability:** `_mm_class` regexes in T4 are reverse-engineered from
  mmdc's output; if mmdc changes its id convention the extractor silently returns
  empty sets and the differential check gets `[EXTRACTOR_GAP]`. Acceptable given
  the skip classification contract; mitigated by confirming regexes against actual
  mmdc output before committing.
- **Clearance direction for diagonal routes:** class edges use orthogonal routing,
  so tangents are axis-aligned — shortening is an integer subtract. If a future
  diagonal-routing branch is added the tangent-normalisation logic in T2 needs
  revisiting.

## Changelog

- 2026-07-23: initial plan; absorbed `class-diagram-route-clip` and
  `class-diagram-label-segment` backlog items per product spec; corrected
  insertion point for route shortening to LR/TB waypoint blocks (`_pts_lr` /
  `_pts`), not the marker-id block at line 897; removed `_marker_kind_clearance`
  shim (`.clearance` always present on class-styled edges); moved 40 px floor to
  class-edge call sites (lines 1256, 1368), not inside `_label_on_longest`; added
  `_renderer.py` conditional to file inventory and T5 scope; narrowed shim-removal
  justification to class-styled edges specifically; added orientation tests and
  fallback guard to T2; fixed T3 unit test for collinear routes.
