# Mermaid Non-Vacuous Oracle

Mode: full (structural change, multi-feature)

- **Status:** Shipped

## Objective

The differential oracle in `tests/test_oracle.py` currently allows a fixture to
report a topology match even when zero comparisons were executed — for example,
when the reference extractor yields no nodes or edges the test silently skips with
`[NO_APPLICABLE_RELATIONS]` instead of recording a gap. A suite that scores
"15/15 pass" while ten of those cases ran zero checks provides no signal about
renderer correctness.

This spec hardens the oracle in two dimensions. First, the comparison layer gains
a formal `OracleResult` type that records a status value (`pass`, `fail`,
`extractor_gap`, `unsupported_reference_feature`, `unvalidated`) and the count of
assertions actually executed (`checks_run`). Any result with `checks_run == 0` is
classified `unvalidated` — never `pass`. Second, each fixture declares expected
minimum counts (entities, groups, relations, labels, and where applicable markers),
and the oracle treats a result that falls below those minimums as `extractor_gap`
rather than a successful match on empty data.

A third dimension extends the mmdc SVG extractor so that the reference side
captures richer topology: edge source/destination identifiers, parent-child
containment structure, source and destination markers, edge style, and ER endpoint
cardinalities. Geometry extraction (node/entity/group bounding boxes, connector
route path samples) is deferred to the `mmdc-geometry-capture` track because it
requires a live browser session at capture time; the remaining SVG-parseable
attributes are in scope here. Arrow/marker type and ER endpoint cardinalities are
also added to the relation multiset comparison key so that class diagrams and ER
diagrams produce failures on type mismatches, not just missing edges.

## Boundaries

- **In scope:** `tests/test_oracle.py` oracle result typing and non-vacuous gates;
  fixture minimum-count manifest (inline TOML front-matter or sidecar per fixture);
  extend `_DIFFERENTIAL` mmdc SVG extractors for markers, containment, edge style,
  ER cardinalities; add `arrow` field to relation multiset key; separate semantic
  endpoints from routing proxy pseudo-nodes; CI checks_run regression gate.
- **Out of scope:** changes to `tools/mermaid_fidelity/` runner, manifest, or
  geometry modules (the fidelity harness and the oracle are separate layers).
- **Out of scope:** native sequence, ER, or class diagram rendering.
- **Out of scope:** exact pixel comparison scoring changes beyond noting it is a
  scored metric, not a hard gate.
- **Never:** add a second Mermaid version or additional fixture files.
- **Never:** place browser/Playwright imports in `tools/mermaid_fidelity/`.
- **Never:** implement geometry bounds extraction or route path sampling here
  (deferred: mmdc-geometry-capture, browser-geometry-capture).

## Acceptance Criteria

- [x] AC1: `checks_run == 0` on any `OracleResult` → status is `unvalidated`;
  status `pass` requires `checks_run >= 1`.
- [x] AC2: Zero common entities when either side contains entities →
  `extractor_gap`, not a pass.
- [x] AC3: Zero common entities when both sides are empty, but the fixture declares
  a nonzero entity minimum → `extractor_gap`.
- [x] AC4: Each fixture in the differential suite declares expected minimum counts
  for entities/nodes, groups, relations, labels, and (where applicable) markers;
  the oracle raises `ManifestError` when a differential fixture has no declaration.
- [x] AC5: The oracle reports a non-vacuous status for all fixtures in the
  differential suite — either `pass`, `fail`, `extractor_gap`, or
  `unsupported_reference_feature` — with `checks_run` recorded in every case;
  15/15 comparable cases produce an explicit outcome rather than a silent skip.
- [x] AC6: Arrow/marker type field is included in the relation multiset comparison
  key; a fixture where two edges have the same endpoints but different arrow types
  is not reported as a full match.
- [x] AC7: ER endpoint cardinalities (e.g. `one`, `many`, `zero_or_one`) are
  included in the semantic comparison for ER fixtures; a cardinality mismatch
  produces a `fail`, not a pass.
- [x] AC8: Semantic endpoints (declared entity ids) are compared separately from
  internal routing proxy pseudo-nodes (e.g. `_sm_start_` / `_sm_end_`); proxy
  nodes are exempt from the missing-entity error path.
- [x] AC9: The mmdc SVG extractors are extended to capture edge source/destination
  identifiers, parent-child containment structure, source and destination marker
  types, edge style, and ER endpoint cardinalities from SVG text patterns (no
  browser session required); geometry bounds and route path samples remain deferred
  (deferred: mmdc-geometry-capture).
- [x] AC10: Exact pixel comparison is retained as a scored metric only; hard gates
  cover semantic identity, containment, endpoint resolution, markers, and
  non-overlap — not pixel error thresholds.
- [x] AC11: CI fails when a fixture that previously had `checks_run >= 1` regresses
  to `checks_run == 0`; the baseline is stored as a committed fixture sidecar or
  inline in the minimum-count declaration.
- [x] AC12: All existing tests (`pytest tests/`) continue to pass after these
  changes.

## Testing Strategy

All tests are unit/integration tests (browser-free). mmdc-dependent differential
tests are gated with `@pytest.mark.skipif(not _HAVE_MMDC, ...)` as today.

- Status enum and OracleResult: unit tests for each status transition, including
  checks_run=0 → unvalidated, checks_run≥1 with no failures → pass.
- Non-vacuous geometry: parametrize over (our_entities, ref_entities, min_declared)
  tuples and assert the correct status for each empty/non-empty combination.
- Minimum-count manifest: test that a missing declaration raises ManifestError; test
  that a fixture declaring min_entities=3 when the extractor returns 1 yields
  extractor_gap.
- Arrow/marker type: construct two Relation objects that share (source, target, label)
  but differ in arrow; assert multiset comparison treats them as different.
- ER cardinality: construct ER relations with differing cardinality values; assert
  the comparator catches the mismatch.
- Proxy endpoint exemption: inject a pseudo-node endpoint into an edge list; assert
  it does not trigger the missing-entity error.
- mmdc extractor extensions: supply a synthetic SVG string containing known marker
  and containment patterns; assert the extractor returns the expected fields.
- CI regression gate: write a fixture sidecar with checks_run=5, then simulate a
  result with checks_run=0; assert the gate raises.
