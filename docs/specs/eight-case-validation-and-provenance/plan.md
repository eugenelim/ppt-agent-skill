# Implementation Plan — Eight-Case Validation and Provenance

**Status:** Executing

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `tools/mermaid_fidelity/models.py` (extend `Provenance` / add
   `EightCaseProvenance`); `scripts/mermaid_render/layout/_geometry.py` (canvas waypoint
   check in `validate_finalized_layout`; `segment_intersects_rect` helper; compound gate
   validation); `tests/test_eight_case_validation.py` (new canonical runner and contracts).
   `tools/mermaid_fidelity/runner.py` already exists — extend or use it as-is; do NOT
   create a parallel runner package.
2. Done when: `pytest tests/test_eight_case_validation.py -m eight_case` green (validation
   infrastructure tests: regression, gate check, non-vacuous contracts, provenance
   independence); live-render lanes for known-broken fixtures are `xfail` until items 2–6
   land; the historical off-canvas regression test rejects the fabricated geometry.
3. Not changing: rendering logic, layout algorithms, painters, parsers, existing fixture
   `.mmd` files, or `LayoutMetadata.backend` values (never rename "python" to "python-fallback").

**Declined patterns:**
- Tempted to add per-fixture coordinate assertions as the primary oracle; declining — the
  spec explicitly forbids fixture-specific coordinate/route patches.
- Tempted to infer `layout_backend` from `output_format`; declining — spec requires they
  be independent fields populated from actual compiler metadata.
- Tempted to clip negative-coordinate geometry; declining — spec requires translation into
  positive space, not clipping.
- Tempted to rename `LayoutMetadata.backend` from `"python"` to `"python-fallback"`;
  declining — existing tests pin `backend == "python"` and renaming breaks them; derive
  `Provenance.layout_backend` via a normalization mapping instead.
- Tempted to build a second runner in `tools/mermaid_fidelity/`; declining — the package
  already ships `FidelityRunner`; extend it or use `tests/test_eight_case_validation.py`
  standalone with the existing helpers.

---

## Tasks

### Task 1: Canonical eight-fixture runner
Depends on: none
Verification: TDD

**Tests:**
- `test_elk_lane_requires_elkjs_present`: ELK lane is `pytest.mark.skipif(not _elk_available(), ...)`.
  When ELK is available, asserts `provenance.layout_backend == "elkjs"` and
  `provenance.fallback_reason is None`.
- `test_fallback_lane_uses_python_fallback`: monkeypatches `layout_with_elk` to raise
  `ElkUnavailable`; asserts `provenance.layout_backend == "python-fallback"` and
  `provenance.fallback_reason` is a non-empty string.
- `test_sequence_lane_stamps_correct_fields`: calls `compile_sequence` directly; asserts
  stamped `provenance.semantic_compiler == "sequence"` and
  `provenance.layout_backend == "sequence-geometry"`.

**Done when:** `pytest -m eight_case` runs all eight fixtures across the required lanes.

**Approach:**
- Add `tests/test_eight_case_validation.py` with `@pytest.mark.eight_case`.
- Define `Provenance` dataclass (7 fields) locally in the test module or in a helper.
- Define `_layout_backend_from_metadata(metadata)` normalization: `"elkjs"`→`"elkjs"`,
  `"elk-js"`→`"elkjs"`, `"python"`→`"python-fallback"`, fallback to `metadata.backend`.
- Parametrize flowchart/architecture fixtures across output format and faithful modes.
  Gate ELK-required lane with `pytest.mark.skipif(not _elk_available(), ...)`.
  Force fallback lane with monkeypatch on `mermaid_render.layout.elk_adapter.layout_with_elk`.
- Sequence fixtures: call `compile_sequence(src)` directly; stamp provenance at call site.
- Known-broken fixtures (live render expected to fail until items 2–6): mark with
  `pytest.mark.xfail(reason="blocked by item N")` so the test suite stays green.

---

### Task 2: Backend provenance fields
Depends on: none
Verification: TDD

**Tests:**
- `test_provenance_fields_separate`: for a rendered fixture, assert `renderer_api`,
  `output_format`, `semantic_compiler`, `layout_backend`, `fallback_reason` are separate
  keys in the provenance dict (not derived from each other).
- `test_provenance_not_inferred_from_output_format`: render same fixture as both
  `to_html` and `to_svg`; assert `layout_backend` is identical in both (it comes from
  layout, not output format).

**Approach:**
- Add `Provenance` dataclass or dict schema with the five required fields.
- Populate from `LayoutMetadata` returned by the compiler. If `LayoutMetadata` doesn't
  already carry all five fields, extend it (without changing the public API).
- Add `renderer_api` field populated at the `to_html`/`to_svg` call site.

---

### Task 3: Canvas validation with segment coverage
Depends on: none
Verification: TDD

**Tests:**
- `test_canvas_contains_all_waypoints`: fabricate a `FinalizedLayout` where one waypoint
  lies outside the canvas rect; assert `validate_canvas_bounds` raises.
- `test_canvas_contains_all_segments`: fabricate a layout where one route segment crosses
  outside the canvas even though both waypoints are inside; assert validation fails.
- `test_cross_scope_edge_regression`: use the historical `flowchart-cross-scope-edge`
  geometry (h=264, B→C route y=293); assert the validator rejects it.
- `test_negative_coordinates_translated`: a layout with negative coordinates is translated
  into positive space; all waypoints are non-negative after finalization.

**Approach:**
- Extend `FinalizedLayout` validation in `_geometry.py` or a new
  `_layout_validation.py` module.
- Add `_segment_outside_canvas(seg, canvas, tol)` helper using parametric clipping.
- Add canvas-bound computation that runs after nodes, groups, boxes, fragments, routes,
  markers, labels, and gates are all known.
- Add translation step: if any coordinate is negative, compute `(dx, dy)` to shift the
  entire layout into positive space.

---

### Task 4: Segment-vs-rectangle intersection validation
Depends on: Task 3
Verification: TDD

**Tests:**
- `test_segment_crosses_node_interior`: a route segment that passes through an unrelated
  node fails validation.
- `test_segment_endpoint_exclusion`: the first segment's portion that legitimately meets
  its own source node does not trigger a false positive.
- `test_segment_crosses_group_title_band`: a route segment crossing a group title band
  fails validation.
- `test_segment_crosses_label_rect`: a segment crossing an edge-label rectangle fails.

**Approach:**
- Implement `_segment_intersects_rect(p1, p2, rect)` using the separating-axis test or
  parametric intersection.
- For each route segment, test against: unrelated node interiors, unrelated group interiors,
  group title bands, edge-label rectangles, marker-clearance regions.
- Exclude the first/last segment portions using the declared endpoint node/group gate.
- Report `edge_id`, segment index, segment endpoints, obstacle ID, obstacle bounds,
  intersection point in validation diagnostics.

---

### Task 5: Compound gate validation
Depends on: Task 3
Verification: TDD

**Tests:**
- `test_gate_required_for_cross_scope_edge`: a cross-scope edge without a gate record
  fails validation.
- `test_gate_on_group_boundary`: a gate that does not lie on the group boundary fails.
- `test_route_contains_gate_waypoint`: a route that bypasses its declared gate fails.
- `test_single_boundary_crossing`: a route that leaves and re-enters the same group fails.

**Approach:**
- In `_layout_validation.py`, add `validate_compound_gates(layout)`.
- Detect cross-scope edges by comparing `source_scope` and `destination_scope`.
- For each cross-scope edge, retrieve gate records from `BoundaryGate` (or equivalent
  geometry field); verify gate lies on the group boundary within tolerance; verify the
  route contains the gate as a waypoint or segment-boundary intersection; count boundary
  crossings.

---

### Task 6: Non-vacuous case contracts
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_zero_assertion_count_fails`: a comparison result with `assertion_count == 0` and
  status `PASS` raises `NonVacuousViolation`.
- One contract test per fixture verifying minimum assertion counts.

**Approach:**
- Add `FixtureContract` dataclasses for each of the eight fixtures with minimum counts
  (nodes, edges, groups, messages, etc.) per the spec tables.
- After running each fixture, assert the comparison report's assertion count meets the
  contract minimum.
- Integrate into the canonical runner (Task 1) so any zero-assertion PASS fails the run.
