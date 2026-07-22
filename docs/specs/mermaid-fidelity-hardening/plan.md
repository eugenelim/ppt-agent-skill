# Implementation Plan — Mermaid Fidelity Harness Hardening

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: tools/mermaid_fidelity/*.py, tools/mermaid_fidelity/compare/*.py, tests/fidelity/*.py, tests/fidelity/adapters/*.py, tests/fidelity/cases.toml, .github/workflows/tests.yml
2. Done when: python3 -m pytest tests/fidelity/ passes; run.py validate returns 0; reports separate active vs planned
3. Not changing: fixture .mmd files, oracle JSON content (shape/semantic data), renderer behavior

**Declined patterns:**
- Tempted to add browser-based geometry extraction in native_svg.py (declining — no browser available without mmdc, and it's repo-adapter territory)
- Tempted to rename existing typed exceptions (declining — add alias UnsupportedDiagramError to bridge, preserve existing API)
- Tempted to make one big "check executor" class that drives comparison (declining — keep separate comparator functions, registry is just metadata)
- Tempted to redesign the entire observation model (declining — evolve in place, preserve JSON serialization compatibility)

**Resolve-vs-surface disposition:**
- "Should I add Playwright dependency to tools/" → resolved with referent (spec says no, keep in tests/fidelity/)
- "Should I recapture oracle with mmdc?" → resolved with referent (spec says only if mmdc available; mark as infrastructure-ready but not executed)
- "How deep should capability registry go?" → resolved with referent (spec says registry is source of truth for names; validation logic stays in comparators)

## Tasks — All Complete

All 13 tasks implemented and verified. test_hardening.py: 36 passed.
Cross-module (test_hardening + test_core_boundary + test_comparators + test_manifest): 117 passed.
Adversarial review: 2 Blockers + 2 Major resolved; remaining Minors deferred (see spec AC14–AC20 deferred anchors).

### Task 1: Fix ValueError → NATIVE_UNSUPPORTED (false-green elimination) — DONE
Depends on: none
Verification: TDD

**Tests:**
- `test_unrelated_value_error_becomes_internal_error`: raise plain ValueError from to_svg() mock → assert status = INTERNAL_ERROR
- `test_unsupported_diagram_type_becomes_native_unsupported`: raise UnsupportedDiagramType → assert status = NATIVE_UNSUPPORTED

**Approach:**
- In `tests/fidelity/adapters/native_svg.py`, change `except ValueError as e:` to `except (UnsupportedDiagramType, NativeRendererUnavailable, UnsupportedDiagramFeature) as e:` → NATIVE_UNSUPPORTED
- Add a new `except ValueError as e:` clause → INTERNAL_ERROR
- Import the typed exceptions from `mermaid_render.errors`

### Task 2: Add lifecycle field to manifest and cases.toml — DONE
Depends on: none
Verification: TDD

**Tests:**
- `test_lifecycle_active_parsed`: case with lifecycle="active" loads correctly
- `test_lifecycle_planned_parsed`: case with lifecycle="planned" loads correctly
- `test_lifecycle_unknown_rejected`: unknown lifecycle value fails validation
- `test_lifecycle_default_active`: missing lifecycle field defaults to "active"

**Approach:**
- Add `lifecycle: str = "active"` to `FidelityCase` in models.py
- In manifest.py, parse `lifecycle` from each case (default "active"), validate against `{"active", "planned"}`
- Add `lifecycle` to all 24 entries in cases.toml (11 flowchart + 2 architecture = "active"; 7 sequence + 4 er = "planned")

### Task 3: Fix CLI hard-fail statuses and unknown --case ID — DONE
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_active_native_unsupported_fails`: active case with NATIVE_UNSUPPORTED → nonzero exit
- `test_planned_native_unsupported_ok`: planned case with NATIVE_UNSUPPORTED → zero exit
- `test_reference_render_failure_fails`: case with REFERENCE_RENDER_FAILURE → nonzero
- `test_unknown_case_id_fails`: --case unknown.id → nonzero with error message

**Approach:**
- In `cli.py` `cmd_run`: add `REFERENCE_RENDER_FAILURE` to `_HARD_FAIL_STATUSES`
- Before running, validate that `args.case_id` (if set) exists in manifest; return 1 if not
- After collecting results, check active cases with NATIVE_UNSUPPORTED → treat as failure regardless

### Task 4: Add check capability registry — DONE
Depends on: none
Verification: TDD

**Tests:**
- `test_all_strict_checks_have_registry_entries`: every known strict check name resolves
- `test_all_scored_checks_have_registry_entries`: every known scored check name resolves
- `test_unknown_check_name_raises`: unknown name → ValueError
- `test_registry_consistent_with_manifest_names`: registry names == manifest's known sets

**Approach:**
- Create `tools/mermaid_fidelity/registry.py` with `CheckCapability` dataclass
- Registry dict mapping all known check names to `CheckCapability` instances
- `get_capability(name: str)` raises `ValueError` for unknown names
- `manifest.py` imports registry for validation (replaces `_KNOWN_STRICT_CHECKS` etc.)

### Task 5: Fix semantic comparison — relation multiplicity — DONE
Depends on: none
Verification: TDD

**Tests:**
- `test_parallel_relations_preserved_count_2`: A→B twice in expected, once in actual → mismatch
- `test_parallel_relations_match`: A→B twice in both → pass

**Approach:**
- In `compare_semantic`, replace set-based relation comparison with Counter-based:
  `_rel_key = (kind, source, target, canonical_label(label), arrow)`
  Use `Counter` to count. Differences → missing/extra.

### Task 6: Fix semantic comparison — shape, group, parse — DONE
Depends on: none
Verification: TDD

**Tests:**
- `test_populated_ref_shape_absent_native_shape_is_mismatch`: exp has shape="diamond", actual has shape=None → changed_entity
- `test_group_existence_checked`: ref has group G1, actual has no groups → missing_group
- `test_group_member_mismatch`: ref G1 has members [A,B], actual G1 has [A] → changed_group
- `test_parse_accepted_vs_rejected_is_mismatch`: ref accepted, native rejected → PARSE_MISMATCH

**Approach:**
- Fix shape check: `if exp_shape is not None and exp_shape != act_shape:` (catches None vs value)
- Fix group check: first check group existence, then membership, then parent
- Add `compare_parse` function that explicitly compares ParseObservation fields
- Call `compare_parse` in runner when "parse" is in strict_fields

### Task 7: Fix containment tuple convention and layout vacuous pass — DONE
Depends on: none
Verification: TDD

**Tests:**
- `test_containment_tuple_child_first`: verify that (child_id, parent_id) ordering is consistent
- `test_vacuous_layout_pass_prevented`: empty entity intersection → not a layout pass

**Approach:**
- In `compare_relative_layout`, fix loop: `for child_id, parent_id in native_obs.containment:`
- When `common_ids` is empty and `"containment"` or any geometry check is in strict_fields AND both observations have entities → return EXTRACTOR_GAP, not passed=True
- In runner, if geometry required for a scored check but geometry is empty/missing → mark EXTRACTOR_GAP

### Task 8: Add source hash and stale oracle detection — DONE
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_source_sha256_computed`: adapter observe() includes source_sha256 in observation
- `test_stale_oracle_detected`: oracle source_sha256 differs from current file → STALE_ORACLE result
- `test_fresh_oracle_passes`: matching hashes → no stale signal

**Approach:**
- Add `source_sha256: str | None = None` to `Observation` model
- In `native_svg.py` adapter, compute `hashlib.sha256(case.source.encode()).hexdigest()` and store
- In `runner.run_case`, compare `native_obs.source_sha256` with oracle `ref_obs.source_sha256`; mismatch → STALE_ORACLE
- In `serialization.py`, include `source_sha256` in to_json/load_json (exclude from fingerprint if desired or include)

### Task 9: Make capture transactional — DONE
Depends on: Task 8
Verification: TDD

**Tests:**
- `test_capture_writes_to_temp_first`: capture uses temp dir, not directly to output
- `test_capture_fails_atomically`: if any active case fails capture, destination not replaced

**Approach:**
- In `cli.py` `cmd_capture_reference`, write to a temp sibling dir first
- After all captures succeed and validation passes, atomic rename to destination
- If any selected active case produces REFERENCE_RENDER_FAILURE → don't replace

### Task 10: Update reports and validate command — DONE
Depends on: Tasks 2, 3
Verification: goal-based check

**Done when:** `run.py validate` shows Active/Planned counts; `run.py run` report.md shows separate sections

**Approach:**
- In `report.py`, split summary into active vs planned counts
- In `cli.py` `cmd_validate`, also validate oracle integrity (source hashes, lifecycle)
- Update `run.py` validate to call extended validation

### Task 11: Fix determinism cases to active-only — DONE
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_determinism_only_uses_active_cases`: sequence/er cases not in determinism subset

**Approach:**
- In `cli.py` `cmd_determinism`, update `_DETERMINISM_CASES` to active-only cases
- Add `RENDER_STABLE` / `UNSUPPORTED_STABLE` / `ERROR_STABLE` / `NONDETERMINISTIC` outcome labels

### Task 12: Update README and CI — DONE
Depends on: Tasks 1-11
Verification: goal-based check

**Done when:** README.md accurately describes Phase 1 scope; tests.yml has browser-free and browser gates

**Approach:**
- Rewrite `tests/fidelity/README.md` per spec requirements
- Update `.github/workflows/tests.yml` to separate browser-free and pinned-browser jobs

### Task 13: Strengthen core boundary tests — DONE
Depends on: Task 4 (registry)
Verification: TDD

**Tests:**
- Test that `tools/mermaid_fidelity` is importable in subprocess with only tools/ on PYTHONPATH
- Test that registry module is importable without scripts/

**Approach:**
- Add subprocess isolation test
- Add registry to the banned-import check
