# Mermaid Oracle Runtime Unification

Mode: full (structural change — new shared module; multi-consumer migration)

- **Status:** Draft

## Objective

The repository currently has two inconsistent comparison models. `tests/test_oracle.py`
has explicit statuses, per-fixture minimums, marker/cardinality extraction, and rejects
passes that execute no checks. `tools/mermaid_fidelity/compare/geometry.py` retains paths
that can treat missing or non-overlapping observations as a passing geometry result.
Semantic comparison omits some marker information because the older reference adapter
cannot extract it. CI reporters and baseline generators each independently redeclare the
same status values.

This spec consolidates all oracle types into a single shared module
(`tools/mermaid_fidelity/oracle_contract.py`) and migrates every consumer to import from
that one location. All status-assignment rules — zero-check refusal, one-sided failure,
extractor-gap detection — are enforced in one place. A fixture-expectation manifest
declares minimum counts per fixture. A stable JSON report schema covers the full
comparison record. Regression tests prove the pathological cases can no longer silently
pass.

This item blocks every other comparison-based acceptance item in boston-v1.

## Boundaries

**In scope:**
- New shared module `tools/mermaid_fidelity/oracle_contract.py` containing
  `OracleStatus`, `OracleCheck`, and `OracleResult`.
- Migration of `tests/test_oracle.py`, `tools/mermaid_fidelity/compare/geometry.py`,
  `tools/mermaid_fidelity/compare/semantic.py`, baseline report generators, and CI
  reporters to import from the shared module.
- Status-rule enforcement: zero-check → never PASS; one-sided observations → FAIL;
  non-overlapping IDs → FAIL; unsupported extraction → UNSUPPORTED_REFERENCE_FEATURE.
- Fixture-expectation manifest covering the 15 in-scope fixtures with minimum counts for
  nodes/entities, groups, relations, edge labels, source/target markers, ER cardinality
  ends, and initial/final pseudo-states.
- Relation comparison model extended to include marker kind, marker end, edge style,
  cardinality, containment, and semantic/routing state endpoints.
- State semantic endpoints compared separately from route proxy endpoints.
- Stable JSON report schema emitted per comparison run.
- Regression tests for: empty observations, one-sided observations, parallel edges,
  marker differences, cardinality differences, containment differences.

**Out of scope:**
- Browser-based geometry capture (see `mmdc-browser-geometry-capture`).
- Implementation of individual diagram-type conformance improvements (items 7–12).
- Changes to the renderer production code paths.
- Pixel comparison scoring.

**Never:**
- Duplicate `OracleStatus` in any consumer — each must import from `oracle_contract.py`.
- Allow `len(checks) == 0` to return PASS anywhere.
- Treat missing reference data as PASS.

## Acceptance Criteria

- [ ] AC1: `OracleStatus`, `OracleCheck`, and `OracleResult` are defined exactly once,
  in `tools/mermaid_fidelity/oracle_contract.py`; all consumers import from there.
- [ ] AC2: Every `OracleResult` with `status == PASS` contains at least one executed
  check; constructing an `OracleResult(status=PASS, checks=())` raises `ValueError`.
- [ ] AC3: No path in `compare/geometry.py` or `compare/semantic.py` returns
  `OracleStatus.PASS` when `len(checks) == 0`.
- [ ] AC4: Native entities present, reference entities absent → `EXTRACTOR_GAP` (not
  PASS); reference entities present, native entities absent → `FAIL`.
- [ ] AC5: Both sides non-empty with no normalized common IDs → `FAIL` (unless an
  explicit identifier-normalization diagnostic accompanies the result).
- [ ] AC6: Unsupported reference extraction → `UNSUPPORTED_REFERENCE_FEATURE`, never
  `PASS`.
- [ ] AC7: A fixture-expectation manifest exists for all 15 in-scope fixtures; each
  entry declares minimum counts for nodes/entities, groups, relations, edge labels,
  source/target markers (where applicable), ER cardinality ends (ER fixtures), and
  initial/final pseudo-states (state fixtures).
- [ ] AC8: Relation comparison includes marker kind, marker end, edge style, and ER
  cardinality for every relation where extractors supply those fields.
- [ ] AC9: State diagram semantic endpoints (declared entity IDs) are compared
  separately from routing proxy pseudo-nodes; proxy nodes are exempt from the
  missing-entity path.
- [ ] AC10: Every comparison run emits a stable JSON report with: fixture, source hash,
  status, checks_executed count, failed_checks count, extractor_gaps list,
  unsupported_fields list, native backend metadata, reference version metadata.
- [ ] AC11: Regression test suite proves that each of the following cannot produce PASS:
  empty observations, one-sided observations (our non-empty / ref empty and vice versa),
  parallel edges with distinct IDs producing duplicate records, marker differences,
  cardinality differences, containment differences.
- [ ] AC12: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

All tests are unit tests; no browser session required.

- **OracleStatus enum:** assert exact vocabulary `{PASS, FAIL, EXTRACTOR_GAP,
  UNSUPPORTED_REFERENCE_FEATURE, UNVALIDATED}` and no others.
- **OracleResult construction guard:** parametrize `status × checks` combinations; assert
  `PASS` with empty checks raises, all other statuses with empty checks succeed.
- **Zero-check paths in geometry.py and semantic.py:** exercise each comparison function
  with empty input on both sides; assert status is not PASS.
- **One-sided observations:** supply (non-empty native, empty reference) and (empty
  native, non-empty reference); assert EXTRACTOR_GAP and FAIL respectively.
- **Non-overlapping IDs:** supply two non-empty sets with zero intersection; assert FAIL.
- **Manifest coverage:** assert all 15 fixture stems have entries; assert missing stem
  raises `ManifestError`.
- **Relation model:** construct two relations identical except for marker kind; assert
  comparison treats them as distinct.
- **ER cardinality:** construct relations with differing cardinality ends; assert FAIL.
- **State proxy exemption:** inject a `_sm_start_` pseudo-node; assert it does not
  trigger FAIL for missing entity.
- **JSON report:** call a comparison, capture the emitted JSON, assert all required keys
  present and types match the schema.
