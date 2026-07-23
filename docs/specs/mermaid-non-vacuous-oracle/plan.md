# Implementation Plan — Mermaid Non-Vacuous Oracle

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `tests/test_oracle.py` (primary); new `tests/oracle_manifest.py`
   or inline fixture sidecar files for minimum-count declarations; no files under
   `tools/mermaid_fidelity/` (the fidelity harness is a separate layer).
2. Done when: `pytest tests/` passes with zero skips on self-consistency and all
   differential fixtures producing an explicit `OracleResult` status; no fixture in
   the differential suite has `checks_run == 0` when mmdc is present.
3. Not changing: renderer code under `scripts/mermaid_layout/`; fidelity harness
   runner/manifest/geometry modules under `tools/mermaid_fidelity/`; existing
   fixture `.mmd` files; pixel comparison scoring.

**Declined patterns:**
- Tempted to lift the oracle into `tools/mermaid_fidelity/` for reuse; declining —
  the oracle is a test-layer concern (it drives `mmdc` as a subprocess) and merging
  it with the capture harness would tangle browser dependencies into the tool package.
- Tempted to add Playwright-based route sampling in this pass; declining — geometry
  extraction requires a live browser session at capture time and is deferred to the
  `mmdc-geometry-capture` track.
- Tempted to use a TOML sidecar file per fixture; declining — an inline constant dict
  in `test_oracle.py` keyed by fixture stem is easier to review and keeps the fixture
  directory free of non-`.mmd` files.

## Tasks

### Task 1: OracleResult dataclass and status enum
Depends on: none
Verification: TDD

**Tests:**
- `test_oracle_result_pass_requires_nonzero_checks`: construct `OracleResult` with
  `status=pass, checks_run=0`; assert `OracleResult.__post_init__` raises
  `ValueError`.
- `test_oracle_result_unvalidated_on_zero_checks`: construct result from a helper
  that auto-assigns status; assert `checks_run=0` yields `status=unvalidated`.
- `test_oracle_status_values_exhaustive`: assert the `OracleStatus` enum contains
  exactly `{pass_, fail, extractor_gap, unsupported_reference_feature, unvalidated}`.

**Approach:**
- Add `OracleStatus` enum (`pass_`, `fail`, `extractor_gap`,
  `unsupported_reference_feature`, `unvalidated`) at the top of `tests/test_oracle.py`.
- Add `OracleResult` dataclass with fields: `fixture_stem: str`,
  `status: OracleStatus`, `checks_run: int`, `notes: list[str]`.
- Add `__post_init__` guard: if `status == pass_` and `checks_run == 0` raise
  `ValueError("pass requires checks_run >= 1")`.
- Introduce `_make_result` helper used by all comparison paths to build an
  `OracleResult` and enforce the invariant.

---

### Task 2: Non-vacuous comparison rules
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_extractor_gap_when_ref_has_entities_our_empty`: zero common entities,
  ref_nodes non-empty, our_nodes empty → `extractor_gap`.
- `test_extractor_gap_when_our_has_entities_ref_empty`: zero common entities,
  our_nodes non-empty, ref_nodes empty → `extractor_gap`.
- `test_extractor_gap_when_both_empty_min_declared`: both sides empty, fixture
  declares `min_entities=2` → `extractor_gap`.
- `test_pass_allowed_when_both_empty_min_zero`: both sides empty, fixture declares
  `min_entities=0` (e.g. a no-node diagram) → not `extractor_gap`.

**Approach:**
- Extract the topology comparison block in `test_topology_matches_reference` into a
  `_compare_topology` function that returns `OracleResult`.
- Before comparing intersection, read the fixture's minimum-count declaration (from
  Task 3's `_FIXTURE_MINIMUMS` dict); if `min_entities > 0` and `len(ref_nodes) == 0
  and len(our_nodes) == 0` return `extractor_gap`.
- If `len(ref_nodes & our_nodes) == 0 and (ref_nodes or our_nodes)` return
  `extractor_gap`.
- Replace the `pytest.skip("[NO_APPLICABLE_RELATIONS]...")` branch with a return of
  `extractor_gap` from `_compare_topology`; the test then calls
  `pytest.skip` only for `REFERENCE_RENDER_FAILURE` and `NATIVE_UNSUPPORTED`.

---

### Task 3: Fixture minimum-count manifest
Depends on: none
Verification: TDD

**Tests:**
- `test_manifest_all_differential_fixtures_declared`: assert every fixture whose
  stem prefix is in `_DIFFERENTIAL` has an entry in `_FIXTURE_MINIMUMS`.
- `test_manifest_missing_entry_raises`: call `_get_fixture_minimums` with a stem
  not in `_FIXTURE_MINIMUMS`; assert `ManifestError` is raised.
- `test_manifest_minimum_below_actual_yields_extractor_gap`: set
  `min_entities=10` for a flowchart fixture that only has 3 reference entities;
  assert `_compare_topology` returns `extractor_gap`.

**Approach:**
- Add a `FixtureMinimums` dataclass: `min_entities: int`, `min_groups: int`,
  `min_relations: int`, `min_labels: int`, `min_markers: int` (all default `0`).
- Add `_FIXTURE_MINIMUMS: dict[str, FixtureMinimums]` constant in `test_oracle.py`,
  populated for every fixture stem currently in `_DIFF_FIXTURES`.
- Add `_get_fixture_minimums(stem: str) -> FixtureMinimums` that raises
  `ManifestError` (a new `ValueError` subclass) when stem is absent.
- Populate minimums by running `_mmdc_render` manually once per fixture and
  inspecting counts; commit the values as constants (not computed at test time).

---

### Task 4: Arrow/marker type in relation multiset comparison
Depends on: none
Verification: TDD

**Tests:**
- `test_arrow_type_distinguishes_relations`: two `(src, dst, label)` identical
  relations with different `arrow` values (`"arrow"` vs `"cross"`) must hash to
  different multiset keys in `_relation_key`.
- `test_arrow_none_vs_value_caught`: `arrow=None` vs `arrow="arrow"` must differ.

**Approach:**
- Add `_relation_key(rel: tuple) -> tuple` helper that returns
  `(src, dst, label, arrow)` — the existing code uses `(src, dst, label)` only.
- Apply `_relation_key` in the multiset counter used inside `_compare_topology`
  for the `ref_edges` / `our_edges` comparison.
- For mmdc-side edges (extracted from SVG) populate `arrow` from the new marker
  extraction in Task 7; for our-side edges read `data-arrow` attribute if present,
  else `None`.

---

### Task 5: ER endpoint cardinalities in semantic comparison
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_er_cardinality_mismatch_yields_fail`: construct two ER topology snapshots
  that agree on entity ids and edge endpoints but differ in cardinality
  (`"one"` vs `"many"`); assert `_compare_topology` returns `fail`.
- `test_er_cardinality_match_passes`: identical cardinality on both sides →
  not `fail` on cardinality check.

**Approach:**
- Extend `_mm_er` extractor (and the our-side ER extraction path) to return a
  fourth value: `cardinalities: frozenset[tuple[str, str, str, str]]` where each
  tuple is `(src, dst, src_card, dst_card)`.
- Add a cardinality comparison block in `_compare_topology` that fires only for
  `er` diagram type; increment `checks_run` by the number of cardinality tuples
  compared.

---

### Task 6: Separate semantic endpoints from routing proxy pseudo-nodes
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_proxy_node_not_missing_entity_error`: construct `our_nodes` with a
  `_sm_start_` pseudo-node and `ref_nodes` without it; assert `_compare_topology`
  does not include `_sm_start_` in `missing_nodes` errors.
- `test_real_node_still_missing_error`: a non-pseudo missing node still yields
  `fail`.

**Approach:**
- Extract `_is_proxy_endpoint(node_id: str) -> bool` from the existing
  `_PSEUDO_ENDPOINT` regex (already defined for self-consistency).
- Before computing `missing_nodes = ref_nodes - our_nodes` and
  `extra_nodes = our_nodes - ref_nodes`, filter proxy endpoints out of both sides:
  `our_semantic = {n for n in our_nodes if not _is_proxy_endpoint(n)}`.
- Document that `_is_proxy_endpoint` matches `_sm_(start|end)_` and any future
  synthetic internal routing nodes added by the renderer.

---

### Task 7: Extend mmdc SVG extractors (non-geometry)
Depends on: none
Verification: TDD

**Tests:**
- `test_mm_flowchart_extracts_markers`: supply a synthetic SVG string with known
  Mermaid marker `<marker id="flowchart-cross-...">` elements; assert `_mm_flowchart`
  returns the expected `{(src, dst): marker_type}` mapping.
- `test_mm_flowchart_containment`: supply SVG with a subgraph cluster `<g
  id="subGraph0">`; assert `_mm_flowchart` returns parent-child pairs.
- `test_mm_er_cardinalities`: supply ER SVG with `<text class="cardinality">one</text>`
  elements near a relationship line; assert `_mm_er` returns expected cardinality tuples.
- `test_mm_edge_style_extracted`: supply SVG with `stroke-dasharray` on a path;
  assert the extractor records edge style as `"dashed"` vs `"solid"`.

**Approach:**
- Add regex/CSS-class patterns for each new attribute:
  - Markers: match `<marker id="flowchart-<type>-...">` to extract arrow head type;
    join to edge via `<path ... marker-end="url(#flowchart-<type>-...)"`.
  - Containment: match `<g id="subGraph<n>"` or `<g class="cluster"` with child
    `flowchart-<node>` ids inside the same `<g>` subtree (use bounded regex, not
    full DOM parse).
  - ER cardinalities: match `<text class="er cardinality">` adjacent to relationship
    path endpoints.
  - Edge style: detect `stroke-dasharray` on relationship `<path>` elements.
- All extractors continue to return the existing
  `(nodes, edges, labels)` tuple for backward compat; new data flows through
  optional additional return values or via the `_compare_topology` closure.
- Note: geometry bounds (x/y/width/height) and connector route path samples are
  NOT extracted here — those require a live DOM/Playwright session
  (deferred: mmdc-geometry-capture).

---

### Task 8: CI checks_run regression gate
Depends on: Task 1, Task 3
Verification: TDD

**Tests:**
- `test_ci_gate_fails_on_zero_regression`: given a committed baseline
  `{fixture_stem: checks_run=5}` and a new result with `checks_run=0` for the same
  fixture, assert `_assert_no_checks_run_regression` raises `AssertionError`.
- `test_ci_gate_passes_on_nonzero`: result `checks_run=3` against baseline
  `checks_run=5` does not raise (degradation in count is allowed; zero is not).
- `test_ci_gate_new_fixture_exempt`: a fixture not yet in the baseline (new addition)
  does not raise even with `checks_run=0`.

**Approach:**
- Add `_CHECKS_RUN_BASELINE: dict[str, int]` constant in `test_oracle.py`, populated
  from the same manual-observation pass as `_FIXTURE_MINIMUMS` (Task 3).
- Add `_assert_no_checks_run_regression(results: list[OracleResult]) -> None` that
  iterates results, looks up each fixture stem in `_CHECKS_RUN_BASELINE`, and asserts
  `result.checks_run > 0` when a baseline entry exists.
- Call this function at the end of `test_topology_matches_reference` (when mmdc is
  present) so it fires in CI environments that have mmdc installed.
- In the `@pytest.mark.skipif(not _HAVE_MMDC, ...)` block, gate the regression
  assertion behind the same mmdc availability check so it doesn't block local runs.
