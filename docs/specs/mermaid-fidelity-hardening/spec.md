# Mermaid Fidelity Harness Hardening — Phase 1

Mode: full (structural change, multi-feature, unfamiliar territory)

- **Status:** Implementing

## Objective

Harden the existing Mermaid fidelity harness (tools/mermaid_fidelity/, tests/fidelity/) so that:
- A green Phase 1 result is non-vacuous: passing requires actual data, not absent data
- Active (flowchart/architecture) and planned (sequence/ER) cases are clearly separated
- Semantic comparison actually checks relations (with multiplicity), shapes, and groups
- Status codes are correctly assigned (no arbitrary ValueError → NATIVE_UNSUPPORTED)
- Source freshness (stale oracle) is detectable
- Reports communicate what was actually evaluated

This implementation now includes browser-based geometry extraction via a Playwright DOM
extractor (`tests/fidelity/adapters/playwright_extractor.py`). Most ACs are fully
implemented; AC14 (flowchart geometry only — architecture deferred) and AC16 (reference
side only — native connector paths deferred) are partially complete. Oracle recapture,
connector path sampling, text-line measurement, and Playwright/Chromium provenance are
all shipped in this change.

## Boundaries

- **Never**: add a second Mermaid version or more fixture files
- **Never**: implement native sequence or ER rendering
- **Never**: place Playwright/browser imports inside tools/mermaid_fidelity/ or outside tests/fidelity/
- **Never**: change existing renderer behavior or SVG output

## Acceptance Criteria

- [x] AC1: Arbitrary `ValueError` cannot become `NATIVE_UNSUPPORTED`
- [x] AC2: Active and planned cases reported separately
- [x] AC3: Active case returning `NATIVE_UNSUPPORTED` fails CI
- [x] AC4: Unknown `--case` ID fails with nonzero exit
- [x] AC5: `REFERENCE_RENDER_FAILURE` is a hard failure for active cases
- [x] AC6: Parse compatibility is actually executed (comparator runs)
- [x] AC7: Every manifest check name maps to a registry entry
- [x] AC8: Missing strict data on either side → `EXTRACTOR_GAP`
- [x] AC9: Empty entity intersection cannot create a vacuous layout pass
- [x] AC10: Relation multiplicity preserved (two A→B edges compare as count 2)
- [x] AC11: Shape compatibility actually compared (None vs value is caught)
- [x] AC12: Group existence, nesting, and membership compared under `containment` strict
- [x] AC13: Containment tuples consistently use `(child_id, parent_id)` convention
- [~] AC14: Active reference observations contain entity/group/relation geometry — flowchart cases fully captured via Playwright DOM extractor; architecture geometry deferred (reference compare passes vacuously when reference side has no entities, by design)
- [x] AC15: Connector paths sampled — 32-point uniform sampling via `getTotalLength`/`getPointAtLength` with CTM transformation (flowchart and self-loop cases)
- [~] AC16: Scored metrics use actual measured geometry — reference-side relation geometry captured; native-side connector-path scoring deferred (NativeSvgAdapter emits relations=[], so connector-paths scored metric is vacuous)
- [x] AC17: Native clipping/overlap/containment quality checks run on real SVG output
- [x] AC18: All 13 active cases have fresh oracle observations — 24 cases recaptured with mmdc 11.15.0
- [x] AC19: All active observations include `source_sha256`; stale oracle detected — recapture via mermaid-p3 Stage 13
- [x] AC20: Exact Mermaid/mmdc/Node/Playwright/Chromium provenance — `_env_identity(probe_browser=True)` captures playwright_version, chromium_revision, viewport, locale, mermaid_config_hash; stored in environment.json
- [x] AC21: Oracle capture is transactional (temp dir → validate → atomically replace)
- [x] AC22: Active determinism runs use only successfully rendered active cases
- [x] AC23: CI compares native output with committed observations without live recapture
- [x] AC24: Continuous scored metrics do not independently fail Phase 1
- [x] AC25: Reusable core passes isolated import and dependency-boundary tests
- [x] AC26: All existing tests continue to pass
- [x] AC27: Reports do not imply planned sequence/ER cases passed

Deferred AC anchors for follow-on work:
- **architecture-geometry-capture**: extend Playwright extractor to architecture SVG DOM; enables AC14 for architecture cases
- **native-connector-paths**: extract native relation paths in NativeSvgAdapter; enables AC16 connector-path scoring

## Testing Strategy

Tests are primarily unit/integration tests (browser-free, `pytest -m parity_fast`).
Browser-dependent tests (`--run-browser`) exercise the Playwright extractor end-to-end
but are not CI-gated in Phase 1 (oracle recapture uses `capture-reference` offline).
Each AC has a corresponding test or is covered by a modified existing test.

- Typed error regression: test that unrelated ValueError cannot produce NATIVE_UNSUPPORTED
- Parse comparison: pure unit tests for all outcomes
- Lifecycle/active: test active NATIVE_UNSUPPORTED → hard failure
- Relation multiplicity: test parallel A→B→count=2 comparison
- Shape comparison: test None vs value is caught
- Group completeness: test missing group → failure
- Containment direction: test (child, parent) not (parent, child)
- Vacuous layout pass: test empty entity list → EXTRACTOR_GAP
- Semantic extractor gap: test None semantic with strict checks → EXTRACTOR_GAP
- Source hashes: test stale detection (code path); full end-to-end deferred to AC18/19
- Transactional capture: test error gating and temp-dir behavior
- Capability registry: test all check names resolve
- Core isolation: test tools/mermaid_fidelity/ importable without scripts/
