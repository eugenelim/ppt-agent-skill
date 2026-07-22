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

This implementation is scoped to what is achievable without live mmdc/browser access.
Items requiring oracle recapture or browser probing (ACs 14, 15, 16, 18, 19, 20) are
infrastructure-ready but deferred to a follow-on mmdc-access pass.

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
- [ ] AC14: Active reference observations contain entity/group/relation geometry (deferred: mmdc-geometry-capture)
- [ ] AC15: Connector paths sampled (deferred: browser-geometry-capture)
- [ ] AC16: Scored metrics use actual measured geometry (deferred: mmdc-geometry-capture)
- [x] AC17: Native clipping/overlap/containment quality checks run on real SVG output
- [ ] AC18: All 13 active cases have fresh oracle observations (deferred: mmdc-oracle-recapture)
- [ ] AC19: All active observations include `source_sha256`; stale oracle detected (deferred: mmdc-oracle-recapture)
- [ ] AC20: Exact Mermaid/mmdc/Node/Playwright/Chromium provenance (deferred: browser-probing)
- [x] AC21: Oracle capture is transactional (temp dir → validate → atomically replace)
- [x] AC22: Active determinism runs use only successfully rendered active cases
- [x] AC23: CI compares native output with committed observations without live recapture
- [x] AC24: Continuous scored metrics do not independently fail Phase 1
- [x] AC25: Reusable core passes isolated import and dependency-boundary tests
- [x] AC26: All existing tests continue to pass
- [x] AC27: Reports do not imply planned sequence/ER cases passed

Deferred AC anchors map to follow-on work items:
- **mmdc-oracle-recapture**: re-run `capture-reference` with mmdc available; commits new oracle JSON with `source_sha256`; enables ACs 18 and 19
- **mmdc-geometry-capture**: extend reference adapter to extract per-entity geometry from real mmdc renders; enables ACs 14 and 16
- **browser-geometry-capture**: extend reference adapter to sample connector paths via Playwright; enables AC 15
- **browser-probing**: query mmdc/Playwright/Chromium version at capture time; enables AC 20

## Testing Strategy

All tests are unit/integration tests (browser-free). Each AC that is in-scope has a
corresponding test or is covered by a modified existing test.

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
