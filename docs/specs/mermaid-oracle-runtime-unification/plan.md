# Implementation Plan — Mermaid Oracle Runtime Unification

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `tools/mermaid_fidelity/oracle_contract.py` (new); `tools/mermaid_fidelity/compare/geometry.py`; `tools/mermaid_fidelity/compare/semantic.py`; `tests/test_oracle.py`; baseline/report generators in `tools/mermaid_fidelity/report.py` and `tools/mermaid_fidelity/runner.py`; fixture manifest (new constant or sidecar).
2. Done when: `pytest tests/` passes; every oracle consumer imports from `oracle_contract.py`; `grep -r "OracleStatus" tools/ tests/` shows only the shared module definition and import sites; no path returns PASS with zero checks.
3. Not changing: renderer code under `scripts/mermaid_render/`; fixture `.mmd` files; Playwright/browser infrastructure; pixel comparison scoring.

**Declined patterns:**
- Tempted to merge the oracle contract into `tests/test_oracle.py` to avoid a new module; declining — the contract needs to be importable by `tools/mermaid_fidelity/compare/` without a test dependency.
- Tempted to add geometry bounds extraction to the manifest; declining — that requires a live browser and belongs to `mmdc-browser-geometry-capture`.
- Tempted to produce a fixture-level JSON sidecar file per fixture; declining — an inline Python constant dict in a shared manifest module is easier to review and grep.

---

## Tasks

### Task 1: Create `oracle_contract.py` with shared types
Depends on: none
Verification: TDD

**Tests:**
- `test_oracle_status_vocabulary`: assert `OracleStatus` enum has exactly `{PASS, FAIL, EXTRACTOR_GAP, UNSUPPORTED_REFERENCE_FEATURE, UNVALIDATED}`.
- `test_oracle_result_pass_requires_checks`: construct `OracleResult(status=PASS, checks=())` and assert `ValueError` is raised.
- `test_oracle_check_fields`: construct `OracleCheck(name="x", passed=True, expected=1, actual=1)` and assert all fields accessible.

**Approach:**
- Create `tools/mermaid_fidelity/oracle_contract.py`.
- Define `OracleStatus(Enum)` with five values.
- Define frozen `OracleCheck(name, passed, expected, actual, diagnostic="")`.
- Define frozen `OracleResult(status, checks, diagnostics)` with `__post_init__` guard: `status == PASS and len(checks) == 0` raises `ValueError`.

---

### Task 2: Migrate `tests/test_oracle.py` to import from shared module
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_oracle_imports_shared_status`: assert `OracleStatus` in `tests/test_oracle` is the same class as `oracle_contract.OracleStatus`.
- `test_no_local_oracle_status_definition`: `grep -n "class OracleStatus" tests/test_oracle.py` returns empty.

**Approach:**
- Replace any local `OracleStatus` / `OracleResult` / `OracleCheck` definitions in `test_oracle.py` with imports from `oracle_contract`.
- Ensure all usages in `test_oracle.py` reference the shared types.

---

### Task 3: Migrate `compare/geometry.py` and `compare/semantic.py`
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_geometry_compare_imports_shared_status`: assert `compare.geometry.OracleStatus is oracle_contract.OracleStatus`.
- `test_geometry_zero_checks_not_pass`: call the geometry comparison function with two empty observation sets; assert result status is not PASS.
- `test_semantic_zero_checks_not_pass`: call the semantic comparison function with empty input; assert result status is not PASS.

**Approach:**
- Replace any local status definitions in `compare/geometry.py` and `compare/semantic.py` with imports from `oracle_contract`.
- In each comparison function, locate the return path that fires when `len(checks) == 0` and convert it to return `OracleStatus.UNVALIDATED` or `OracleStatus.EXTRACTOR_GAP` as appropriate.

---

### Task 4: Status-rule enforcement (zero-check, one-sided, non-overlapping)
Depends on: Task 3
Verification: TDD

**Tests:**
- `test_extractor_gap_native_non_empty_ref_empty`: native entities non-empty, ref empty → `EXTRACTOR_GAP`.
- `test_fail_ref_non_empty_native_empty`: ref entities non-empty, native empty → `FAIL`.
- `test_fail_non_overlapping_ids`: both sides non-empty, zero common IDs → `FAIL`.
- `test_unsupported_not_pass`: an unsupported extraction result → `UNSUPPORTED_REFERENCE_FEATURE`, not `PASS`.

**Approach:**
- In `compare/geometry.py` and `compare/semantic.py`, add explicit rule checks before the main comparison loop:
  - `if ref_entities and not native_entities: return OracleResult(FAIL, ...)`
  - `if native_entities and not ref_entities: return OracleResult(EXTRACTOR_GAP, ...)`
  - `if ref_entities and native_entities and len(ref_entities & native_entities) == 0: return OracleResult(FAIL, ...)`
- Update unsupported-extraction paths to return `UNSUPPORTED_REFERENCE_FEATURE`.

---

### Task 5: Fixture-expectation manifest
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_manifest_covers_all_15_fixtures`: assert all 15 fixture stems have entries.
- `test_manifest_missing_raises_manifest_error`: call `get_fixture_minimums("nonexistent")` → `ManifestError`.
- `test_manifest_minimum_enforced`: set `min_entities=10` for a fixture; supply 3 entities; assert `EXTRACTOR_GAP`.

**Approach:**
- Create `tools/mermaid_fidelity/manifest.py` (or add to existing if it exists) a `FixtureMinimums` dataclass and `FIXTURE_MINIMUMS` dict keyed by fixture stem.
- Populate minimum counts for all 15 fixtures from the spec's in-scope list.
- Add `ManifestError` as a `ValueError` subclass.
- Call `get_fixture_minimums` in the comparison paths before asserting counts.

---

### Task 6: Extended relation comparison model
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_marker_kind_in_relation_key`: two relations identical except `marker_kind`; assert they produce distinct comparison keys.
- `test_er_cardinality_mismatch_fails`: ER relations differing only in `target_end.maximum`; assert `FAIL`.
- `test_state_proxy_exemption`: `_sm_start_` in our edges, absent from ref; assert not in `FAIL` path for missing entities.

**Approach:**
- Extend the relation comparison model in `compare/semantic.py` to include `marker_kind`, `marker_end`, `edge_style`, `cardinality`, `containment`.
- Add `_is_proxy_endpoint(node_id)` helper; filter proxy nodes from entity comparison.
- Add ER-specific cardinality comparison block that fires when diagram type is ER.
- Update comparison keys to be tuples that include marker/cardinality fields where available.

---

### Task 7: JSON report schema
Depends on: Task 4
Verification: Goal-based check

**Done when:** `python -c "from tools.mermaid_fidelity.report import emit_oracle_report; ..."` emits a JSON string with all required keys.

**Approach:**
- Add `emit_oracle_report(result: OracleResult, provenance: dict) -> dict` to `tools/mermaid_fidelity/report.py`.
- Required keys: `fixture`, `source_hash`, `status`, `checks_executed`, `failed_checks`, `extractor_gaps`, `unsupported_fields`, `native_backend_metadata`, `reference_version_metadata`.
- Wire into the comparison runner to emit the JSON alongside each fixture result.

---

### Task 8: Regression test suite
Depends on: Tasks 4, 5, 6
Verification: TDD

**Tests:**
- `test_regression_empty_both_sides_no_pass`: empty native and reference with non-zero manifest minimum → not PASS.
- `test_regression_one_sided_native_not_pass`: native non-empty, ref empty → not PASS.
- `test_regression_one_sided_ref_not_pass`: ref non-empty, native empty → not PASS.
- `test_regression_parallel_edges_distinct`: two edges with same `(src, dst)` but different `edge_id` → both present in comparison.
- `test_regression_marker_difference_fails`: edges identical except marker kind → `FAIL`.
- `test_regression_cardinality_difference_fails`: ER edges identical except cardinality end → `FAIL`.
- `test_regression_containment_difference_fails`: nodes with different containment → `FAIL`.

**Approach:**
- Add a `TestOracleRegressions` class in `tests/test_oracle.py` (or a new `tests/test_oracle_contract.py`).
- Each test constructs minimal synthetic oracle inputs that exercise the specific pathological case.
- Assert the oracle returns the expected non-PASS status for each case.
