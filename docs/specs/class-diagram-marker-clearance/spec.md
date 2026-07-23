# Spec: class-diagram-marker-clearance

Mode: full (structural change, multi-feature)

- **Status:** Draft
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** `docs/specs/class-diagram-marker-semantics/spec.md`
  (deferred ACs: route shortening, card-boundary clip, label segment placement)
- **Brief:** none
- **Discovery:** none
- **Contract:** none
- **Shape:** data

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The class-diagram renderer produces correct UML marker geometry for all seven
relationships in `tests/fixtures/class-relationships-all.mmd`. Each marker tip
lands at the card face rather than inside it (route endpoint shortened by the
marker's clearance distance), every marker is oriented from the final nonzero
route-tangent segment, and the mmdc oracle extractor covers the class diagram type
so differential topology checks verify marker kind, endpoint, and label against
the reference renderer.

This spec also absorbs two previously deferred backlog slugs — `class-diagram-route-clip`
and `class-diagram-label-segment` — folding card-boundary clipping and 40 px label
segment placement into the same geometry pass rather than shipping partial clearance
geometry without them. The prior spec (`class-diagram-marker-semantics`) established
the `MarkerSpec` model and operator-to-marker mapping; this spec completes the geometry.

## Boundaries

### Always do

- Set `MarkerSpec.clearance` in `_class_rel_markers` using the per-kind table
  (hollow triangle 12 px, filled diamond 12 px, hollow diamond 12 px, open arrow
  9 px, none 0 px).
- Shorten the route at the marked endpoint and clip to the card `Rect` before
  label candidate generation, so label candidates never straddle the shortened end.
- Preserve marker ownership (which end carries the marker) independently of ELK
  rank direction, using the existing `MarkerSpec.end` field.
- Guard label placement: append each placed chip bbox to `placed_labels` before
  evaluating the next relation's candidates — evaluated before the collinear
  branch in `_label_on_longest` so straight (all-same-x / all-same-y) class edges
  are included.
- Emit a label shelf only when no eligible segment of ≥ 40 px exists (including
  the full collinear path for straight edges); shelf position deterministic
  (canonical offset from the nearest card face).
- Keep `LayoutEdge.source_marker`/`target_marker` typed as `MarkerKind` (ELK
  pipeline contract).

### Ask first

- Any clearance value that differs from the per-kind table above.
- Changing the label chip height (`_LABEL_CHIP_H`) or the 40 px segment floor.
- Adding a new `MarkerKind` value not already in the `MarkerKind` enum.
- Modifying the mmdc oracle extractor in a way that gates an existing non-class
  fixture on mmdc availability.
- Modifying `_label_on_longest` in a way that changes label placement for
  non-class edge types (flowchart, stateDiagram, etc.).

### Never do

- Replace the existing `source_marker`/`target_marker` `MarkerSpec` model with a
  different data structure; the semantics spec's model is the canonical one.
- Add a new top-level Python package or install a new third-party dependency.
- Move label shelf coordinates into any persistent state; shelf is computed
  per-render from current geometry.
- Gate the differential oracle test on any fixture that was not already gated on
  mmdc availability.
- Change `LayoutEdge.source_marker`/`target_marker` to `MarkerSpec` (would break
  the ELK pipeline; out of scope per the semantics spec's `Declined` section).
- Apply the 40 px segment floor or label shelf to non-class edge types; scope the
  change to the class-edge call site only.

## Testing Strategy

**TDD** — for clearance value assignment: every marker kind maps to an exact
clearance constant; these invariants are fully compressible to unit assertions.
Covers AC1.

**TDD** — for route shortening math: the terminal waypoint shifts by exactly
`clearance` px in the tangent direction, and the final path segment direction
(dx, dy) matches the pre-shortening tangent direction. Covers AC2 and AC3.
Includes an edge-case test for clearance ≥ last-segment length (would invert
orientation without a guard).

**TDD** — for card-boundary clip: after shortening, no waypoint lies strictly
inside the node's `Rect`. Stub geometry; assert coordinate bounds. Covers AC4.

**TDD** — for label segment selection and shelf fallback: stub a collinear route
(all-same-x, straight edge — the dominant class-diagram case) and a multi-segment
route; assert floor enforcement and shelf determinism. Covers AC6, AC7, AC8.

**Goal-based check** — for marker placement in rendered HTML: render a
two-class snippet with `_layout_class` and confirm the final `L x,y` waypoint in
the SVG path is ≥ `clearance` px from the card face. Covers AC2 integration.

**Goal-based check** — for mmdc oracle: `pytest tests/test_oracle.py` with mmdc
absent must skip cleanly (self-consistency still runs); with mmdc present the
differential check passes for `class-relationships-all`. Covers AC9.

**Regression** — all existing `tests/test_class_semantic.py` tests (including
`TestFixtureRelationSemantics`, `TestClassRelMarkers`, `TestRenderedMarkers`,
`TestCompileClassdiagram`) must stay green. Covers AC5 and AC10 (both are
already shipped by the prior spec; verified here as non-regression).

## Acceptance Criteria

- [ ] AC1: `_class_rel_markers` sets `MarkerSpec.clearance` to 12.0 for
  `HOLLOW_TRIANGLE`, 12.0 for `FILLED_DIAMOND`, 12.0 for `HOLLOW_DIAMOND`, 9.0
  for `OPEN_ARROW`, and 0.0 for `NONE` — verified by unit test for each kind.

- [ ] AC2: For every class-diagram edge whose marker endpoint has nonzero
  clearance and whose final route segment is longer than `clearance`, the rendered
  SVG path's terminal waypoint is shortened by exactly `clearance` px along the
  final route tangent — verified by asserting the waypoint coordinate difference
  equals the clearance constant. (When the final segment is ≤ `clearance` px, the
  orientation-fallback defined in AC3 applies instead.)

- [ ] AC3: The final path segment direction `(dx, dy)` after shortening matches
  the direction of the pre-shortening last segment — verified by a unit test that
  shortens a known-length segment and asserts `sign(dx)` and `sign(dy)` are
  unchanged. A separate edge-case test confirms that when `clearance` equals or
  exceeds the last segment's length the renderer falls back to the second-to-last
  segment's tangent rather than inverting direction.

- [ ] AC4: After shortening, the path entry/exit point is clipped to the
  class-card bounding rect so no route waypoint falls strictly inside a card's
  `Rect` — verified by asserting no rendered waypoint satisfies
  `rect.x < wx < rect.x + rect.w and rect.y < wy < rect.y + rect.h`.

- [ ] AC5: The five semantic marker-ownership rules hold for all seven fixture
  relations (inheritance at parent; composition at owner; aggregation at
  aggregate; dependency arrow at target; realization triangle at target) —
  verified by `TestFixtureRelationSemantics` (already passing from the prior
  spec; confirmed non-regressed by `pytest tests/test_class_semantic.py`).

- [ ] AC6: Each relation label in `class-relationships-all.mmd` is placed on a
  route segment whose Manhattan length is ≥ 40 px, or — when no such segment
  exists — on a deterministic shelf — verified by asserting that for each
  rendered relation the label `(lx, ly)` either lies within the bounding box of
  a ≥ 40 px segment or the edge has no ≥ 40 px segment (shelf case).

- [ ] AC7: When all seven relations are rendered together, each placed label chip
  bbox is added to `placed_labels` before the next relation's placement runs, so
  no two label chips overlap — verified by asserting pairwise disjoint chip rects.

- [ ] AC8: When no route segment meets the 40 px floor (including the full
  collinear path for straight edges), a label shelf is emitted at a deterministic
  offset from the nearest card face instead of overlapping another chip — verified
  by a synthetic fixture with a very short edge and asserting the shelf
  coordinates are stable across repeated renders.

- [ ] AC9: `tests/test_oracle.py`'s `_DIFFERENTIAL` registry includes a
  `"class"` extractor (`_mm_class`) that identifies each marker type and endpoint
  from the mmdc SVG — verified by `pytest tests/test_oracle.py` passing the
  self-consistency check for all class fixtures and, when mmdc is present, the
  differential check passing for `class-relationships-all`.

- [ ] AC10: `tests/test_class_semantic.py` covers all seven fixture relations
  asserting `source_marker.kind`, `target_marker.kind`, which end is non-NONE,
  `line_style`, `src` node, `dst` node, and `lbl` text — verified by
  `pytest tests/test_class_semantic.py` passing with zero skips. (Tests already
  exist from the prior spec; confirmed non-regressed here.)

## Assumptions

- Technical: `MarkerSpec.clearance` field exists at `float = 0.0` default in
  `_geometry.py` (source: `scripts/mermaid_render/layout/_geometry.py` line 997).
- Technical: `_class_rel_markers` creates `MarkerSpec` instances without nonzero
  clearance — this spec adds the values (source:
  `scripts/mermaid_render/layout/_strategies.py` lines 1725–1745).
- Technical: route shortening is a deferred AC in the semantics spec; card-clip
  and label-segment are separately deferred backlog items — this spec absorbs all
  three (source: `docs/specs/class-diagram-marker-semantics/spec.md` lines
  35–37; `workspace.toml` slugs `class-diagram-route-clip` and
  `class-diagram-label-segment`).
- Technical: `_label_on_longest` in `_routing.py` has an early-exit collinear
  branch (lines 367–371) that bypasses the segment-search loop for straight edges;
  the 40 px floor must be applied before that branch, not inside it (source:
  `scripts/mermaid_render/layout/_routing.py` lines 358–398).
- Technical: `_DIFFERENTIAL` in `tests/test_oracle.py` has no `"class"` entry
  — class diagrams are currently self-consistency-only (source:
  `tests/test_oracle.py` lines 202–207).
- Technical: `LayoutEdge.source_marker`/`target_marker` stays `MarkerKind` — ELK
  pipeline contract unchanged (source: `docs/specs/class-diagram-marker-semantics/
  spec.md` Declined section).
- Technical: waypoint shortening must be inserted in both the LR (`_routing.py`
  ~line 1242) and TB (~line 1350) waypoint blocks, gated on
  `e.style.startswith("cls")`, not at the marker-id assignment block around
  line 897 where no `pts` variable is in scope (source:
  `scripts/mermaid_render/layout/_routing.py`).
- Technical: `_renderer.py` has two separate rendering paths (main +
  `render_finalized`); shape fixes must land in both (source: MEMORY note
  `renderer-two-paths`).
- Product: target fixture is `tests/fixtures/class-relationships-all.mmd` with
  exactly 7 relations (source: user confirmation 2026-07-23).
