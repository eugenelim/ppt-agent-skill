# Implementation Plan — class-diagram-marker-clearance

- **Spec:** [`spec.md`](spec.md)
- **Status:** Drafting

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_strategies.py`
   (`_class_rel_markers`), `scripts/mermaid_render/layout/_routing.py`
   (class-edge branch in `route_edges`, `_label_on_longest`),
   `tests/test_class_semantic.py` (new clearance + label-placement tests),
   `tests/test_oracle.py` (`_mm_class` extractor + `_DIFFERENTIAL` registry).
2. Done when: `pytest tests/` passes; `class-relationships-all` fixture
   renders without any marker tip inside a card face; all seven label chips
   are disjoint; `test_oracle.py` self-consistency green for all class
   fixtures.
3. Not changing: `_geometry.py` `MarkerSpec` / `MarkerKind` definitions
   (field already exists at `clearance: float = 0.0`); `LayoutEdge.source_marker`
   / `target_marker` types (stays `MarkerKind`); HTML marker defs in
   `_renderer.py`; any non-class routing paths.

**Declined patterns:**
- Patching clearance into `MarkerSpec.__post_init__` as a kind-based default —
  clearance is a UML rendering constant, not a property of the marker shape in
  isolation; it belongs in the operator-to-spec mapping (`_class_rel_markers`).
- A separate "clip pass" after routing — shortening and clipping must happen
  inside the existing class-edge branch of `route_edges` so the full route
  (including label candidate generation) sees the shortened endpoints.
- Per-render `placed_labels` reset inside the inner edge loop — the list is
  already accumulated across edges in `route_edges`; class edges must append to
  it, not reinitialise it.
- Storing label shelf position in any module-level dict — shelf is computed
  per-edge at render time from current card geometry.

## Approach

The change has three independent surfaces: clearance constants, route
geometry (shortening + clip), and label placement / oracle.

**Clearance constants (T1):** one-line change per operator branch in
`_class_rel_markers` — replace `_MS(kind=…, end=…)` with
`_MS(kind=…, end=…, clearance=12.0)` (or 9.0 for `OPEN_ARROW`). All
existing tests pass unchanged; new TDD tests assert the constant by kind.

**Route geometry (T2):** inside the `e.style.startswith("cls")` branch in
`route_edges` (`_routing.py`), after waypoints are computed and before label
candidates are generated, shorten the terminal waypoint(s) by `clearance` px
along the final/first nonzero tangent and clip to the card bounding rect.
The clip uses the node's `Rect` (already in scope via `s` / `d` nodes).

**Label placement (T3):** extend `_label_on_longest` (or its call site for
class edges) to enforce the 40 px floor — skip segments shorter than 40 px
when looking for the best candidate. When all segments are shorter, fall back
to a deterministic shelf: `card_face_x + 4 px` or `card_face_y - label_h - 4`
depending on the exit side. The `placed_labels` reservation logic is already
present for non-class edges; T3 ensures class edges append their chip bboxes
to the same list.

**Oracle extractor (T4):** add `_mm_class` to `tests/test_oracle.py` that
parses the mmdc SVG's class-diagram edge `<path>` elements (which carry
`marker-start`/`marker-end` URL references) and node `<g class="classGroup">`
elements. Register it under the `"class"` key in `_DIFFERENTIAL`. This is
self-contained and has no upstream code dependency.

Tasks T1, T3, and T4 have no mutual dependencies; T2 depends on T1 so the
clearance constant is available when the routing branch reads
`e.source_marker.clearance` / `e.target_marker.clearance`.

## Constraints

- `LayoutEdge.source_marker`/`target_marker` stays `MarkerKind` (ELK pipeline
  contract from ADR-001 via `class-diagram-marker-semantics` Declined section).
- Clearance constants are fixed at 12 / 9 / 0 px per the product spec; no
  env-var or per-diagram configurability.
- Oracle extractor must not gate any fixture that was not already conditional on
  mmdc — new extractor joins `_DIFF_FIXTURES` filter naturally via the `"class"`
  key prefix.

## Construction tests

**Integration:** render `class-relationships-all.mmd` through `_layout_class` and
assert all seven label chips are pairwise disjoint using their `(lx, ly, w, h)`
bounding rectangles.

**Manual verification:** none — all acceptance criteria are automatable.

## Design (LLD)

### Design decisions

- Clearance stored on `MarkerSpec` (not on `_Edge` or derived at paint time) so
  any consumer that reads the spec gets the value without special-casing.
  Traces to: AC1.
- Route shortening happens in the `e.style.startswith("cls")` routing branch
  rather than a post-pass, keeping geometry coherent for label placement.
  Traces to: AC2, AC3, AC4.
- Label shelf fallback uses the card face as an anchor (not the canvas edge),
  ensuring stable placement even when the canvas is wide.
  Traces to: AC8.

### Data & schema

`MarkerSpec.clearance` (existing field, `float = 0.0`) receives nonzero values
from `_class_rel_markers`. No schema migration needed; the field is already
serialised by `dataclasses.asdict`. Traces to: AC1.

### Component / module decomposition

| Module | Change |
|---|---|
| `layout/_strategies.py` | `_class_rel_markers`: set `clearance=12.0` or `9.0` per kind |
| `layout/_routing.py` | class-edge branch: shorten terminal waypoints by clearance, clip to card rect; `_label_on_longest`: enforce 40 px floor, add shelf fallback |
| `tests/test_class_semantic.py` | clearance unit tests, label placement / disjoint chip tests |
| `tests/test_oracle.py` | `_mm_class` extractor, register under `"class"` key |

### Behavior & rules

- Clearance per kind: `HOLLOW_TRIANGLE` → 12 px; `FILLED_DIAMOND` → 12 px;
  `HOLLOW_DIAMOND` → 12 px; `OPEN_ARROW` → 9 px; `NONE` → 0 px.
- Shortening direction: last segment tangent for target-end markers; first
  segment tangent for source-end markers.
- Label segment floor: 40 px (Manhattan length). Shelf offset: 4 px from
  nearest card face, label chip height above/below depending on exit side.
- Shelf is emitted only when all segments are < 40 px (not merely when the
  longest segment is sub-optimal).

## Tasks

### T1: Assign nonzero clearance constants in `_class_rel_markers`
**Depends on:** none
Verification: TDD
**Touches:** `scripts/mermaid_render/layout/_strategies.py`,
`tests/test_class_semantic.py`

**Tests:**
- `_class_rel_markers("<|--")[0].clearance == 12.0` (hollow triangle, source)
- `_class_rel_markers("*--")[0].clearance == 12.0` (filled diamond, source)
- `_class_rel_markers("o--")[0].clearance == 12.0` (hollow diamond, source)
- `_class_rel_markers("-->")[1].clearance == 9.0` (open arrow, target)
- `_class_rel_markers("..>")[1].clearance == 9.0` (open arrow, dashed)
- `_class_rel_markers("..|>")[1].clearance == 12.0` (hollow triangle, target)
- `MarkerSpec(kind=MarkerKind.NONE, end="TARGET").clearance == 0.0`
  (default unchanged)
- All 12 existing `TestClassRelMarkers` tests still green (no regression).

**Approach:**
- In `_strategies.py`, edit each `return` in `_class_rel_markers`:
  - `_MS(kind=_MK.HOLLOW_TRIANGLE, end=…)` → add `clearance=12.0`
  - `_MS(kind=_MK.FILLED_DIAMOND, end=…)` → add `clearance=12.0`
  - `_MS(kind=_MK.HOLLOW_DIAMOND, end=…)` → add `clearance=12.0`
  - `_MS(kind=_MK.OPEN_ARROW, end=…)` → add `clearance=9.0`
  - `NONE_SRC` / `NONE_TGT` keep `clearance=0.0` (default, no change needed).
- Add a `TestMarkerClearance` class to `tests/test_class_semantic.py` with the
  per-kind assertions above.

**Done when:** `pytest tests/test_class_semantic.py::TestMarkerClearance` passes;
`pytest tests/test_class_semantic.py::TestClassRelMarkers` still green.

---

### T2: Shorten and clip route endpoints in `route_edges` for class edges
**Depends on:** T1
Verification: TDD + goal-based check
**Touches:** `scripts/mermaid_render/layout/_routing.py`,
`tests/test_class_semantic.py`

**Tests:**
- Unit: for a two-point route `[(100, 50), (100, 150)]` (vertical, TB) with a
  target-end clearance of 12, assert the returned terminal waypoint is
  `(100, 138)` (shifted 12 px up the tangent toward source).
- Unit: for a source-end clearance of 12 on the same route, assert the first
  waypoint is `(100, 62)` (shifted 12 px down toward target).
- Unit: after shortening, assert no waypoint is strictly inside the card `Rect`
  of either endpoint node (clip check).
- Goal-based: render `Animal <|-- Dog` with `_layout_class`; extract the `<path>`
  `d=` attribute; confirm the final `L x,y` coordinate is ≥ 12 px from the
  `Animal` card's `y + height` face.
- Regression: `TestRenderedMarkers` still green.

**Approach:**
- In `_routing.py`, inside the `e.style.startswith("cls")` branch (around
  line 897), after `_smooth_orthogonal_path` produces `pts`:
  1. Read `src_clearance = _marker_kind_clearance(e.source_marker)` and
     `tgt_clearance = _marker_kind_clearance(e.target_marker)`, where
     `_marker_kind_clearance` extracts `.clearance` from a `MarkerSpec` or
     returns 0 if the field is a `MarkerKind` enum (backward-compat shim).
  2. If `tgt_clearance > 0`: compute tangent from `pts[-2]` → `pts[-1]`;
     shorten `pts[-1]` by `tgt_clearance` along that tangent.
  3. If `src_clearance > 0`: compute tangent from `pts[1]` → `pts[0]`;
     shorten `pts[0]` by `src_clearance` along that tangent.
  4. Clip each endpoint to the node's card `Rect` (clamp to boundary if the
     shortened point exceeds the face).
- Add helper `_marker_kind_clearance(spec) -> float` — returns `spec.clearance`
  if `spec` is a `MarkerSpec`, else `0.0`.

**Done when:** the unit assertions above pass; rendered `Animal <|-- Dog` path
endpoint is ≥ 12 px from the card face; `pytest tests/` green.

---

### T3: Enforce 40 px segment floor and label shelf in `_label_on_longest`
**Depends on:** none
Verification: TDD
**Touches:** `scripts/mermaid_render/layout/_routing.py`,
`tests/test_class_semantic.py`

**Tests:**
- Unit: route `[(0,0),(0,60)]` (one 60 px segment) — label placed on that
  segment (mid ≈ `(0, 30)`).
- Unit: route `[(0,0),(0,20),(0,40)]` (two 20 px segments) — no segment ≥ 40 px;
  shelf emitted at deterministic offset from nearest card face.
- Unit: shelf offset is stable across two identical calls (determinism check).
- Integration: render all seven relations from `class-relationships-all.mmd`
  together; assert pairwise disjoint label chip rects (no two chips share any
  pixel column + row combination).
- Regression: `TestRenderedMarkers` and `TestMultiplicitySlots` still green.

**Approach:**
- In `_routing.py`, extend `_label_on_longest` (lines 358–398):
  - In the segment-search loop, skip segments with `seg_len < 40`; if all
    segments are < 40, fall through to the shelf path.
  - Shelf fallback: take the midpoint of the full route; offset 4 px
    perpendicular to the dominant direction (horizontal route → place above;
    vertical route → place to the right). Use `_best_label_pos` with the
    shelf candidate so `placed_labels` collision avoidance still applies.
- At the class-edge call sites in `route_edges` (the `e.style.startswith("cls")`
  branch), ensure the `placed_labels` list is passed through (not reset) so
  chips from earlier edges block later ones.

**Done when:** unit assertions above pass; integration disjoint-chip test passes;
`pytest tests/test_class_semantic.py` green.

---

### T4: Add `_mm_class` extractor to the mmdc oracle
**Depends on:** none
Verification: goal-based check
**Touches:** `tests/test_oracle.py`

**Tests:**
- Self-consistency: `pytest tests/test_oracle.py` with mmdc absent — all class
  fixtures self-consistent (no dangling edge endpoints in our rendered HTML).
- Differential (when mmdc present): `class-relationships-all` fixture passes
  symmetric topology check; marker-kind and endpoint extracted from mmdc SVG
  match our rendered `data-src`/`data-dst`/`data-edge-label` attributes.
- Registry smoke: `"class" in _DIFFERENTIAL` evaluates to `True` after the
  change.

**Approach:**
- In `test_oracle.py`, add `_mm_class(svg: str)` below the existing extractors
  (around line 200):
  - Nodes: `<g class="classGroup"[^>]+id="([^"]+)"` (one per class box in
    mmdc's SVG output).
  - Edges: `<path[^>]+id="([A-Za-z0-9_]+)_([A-Za-z0-9_]+)"` for class
    relationship paths (mmdc uses `src_dst` id convention for class edges).
  - Labels: reuse `_MM_EDGE_LABEL` regex (class diagram edge labels use the
    same `<span class="edgeLabel"><p>` structure as flowchart).
  - Return `(nodes, edges, labels)`.
- Register under `_DIFFERENTIAL["class"] = _mm_class`.
- Confirm `"class-relationships-all"` fixture stem starts with `"class"` so it
  joins `_DIFF_FIXTURES` automatically.
- If mmdc SVG id conventions differ from the above, adjust regexes and note
  the actual pattern in a comment.

**Done when:** `pytest tests/test_oracle.py -k class` passes (self-consistency
always; differential when mmdc available); `"class" in _DIFFERENTIAL` is True.

---

### T5: Wire clearance into `_build_routed_edges_ir` and validate end-to-end
**Depends on:** T1, T2, T3
Verification: goal-based check
**Touches:** `scripts/mermaid_render/layout/_strategies.py`,
`tests/test_class_semantic.py`

**Tests:**
- End-to-end: `_compile_classdiagram(FIXTURE_SRC)` produces a `FinalizedLayout`
  where every `RoutedEdgeIR` for a class edge has a final waypoint ≥ its
  `clearance` distance from the respective node's card face.
- Regression: `TestCompileClassdiagram` (all 9 existing tests) still green.
- Smoke: `pytest tests/` exits 0 with no new failures.

**Approach:**
- Confirm `_build_routed_edges_ir` in `_strategies.py` (called at line 1928)
  passes the already-shortened waypoints through — no extra truncation needed
  since T2 shortens in `route_edges` before the IR is built.
- If `_compile_classdiagram` calls a separate rendering path (check for the
  "two paths" MEMORY note — `_renderer.py` has both a main and `render_finalized`
  path), verify the shortened waypoints propagate through `render_finalized` as
  well.
- Add one end-to-end assertion to `TestCompileClassdiagram` that confirms
  waypoint clearance for the `Animal <|-- Dog` edge.

**Done when:** all existing and new tests green; `pytest tests/` exits 0.

## Rollout

Pure Python logic change inside the `mermaid_render` package; no infra, no flag,
no migration. Deploys with the next skill release automatically.

## Risks

- **Two render paths:** the MEMORY note `renderer-two-paths` records that
  `_renderer.py` has both a main path and `render_finalized` path; T5 must verify
  the shortened waypoints reach both. Risk of missing one path and shipping
  asymmetric behaviour.
- **Clearance direction for diagonal routes:** class edges use orthogonal routing,
  so tangents are always axis-aligned — clearance shortening is a simple integer
  subtract. If a future diagonal-routing branch is added, the tangent-normalisation
  logic in T2 will need revisiting.
- **mmdc SVG id stability:** `_mm_class` regexes in T4 are reverse-engineered
  from the mmdc output format; if mmdc changes its id convention the extractor
  silently returns empty sets and the differential check gets `[EXTRACTOR_GAP]`
  rather than a failure. Acceptable given the skip classification contract.

## Changelog

- 2026-07-23: initial plan
