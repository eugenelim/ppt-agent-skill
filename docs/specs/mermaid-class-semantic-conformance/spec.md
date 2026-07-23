# Mermaid Class Semantic Conformance

Mode: full (multi-fixture; edge-ID migration; marker oracle assertions)

- **Status:** Shipped

Dependencies: mermaid-oracle-runtime-unification, mermaid-text-measurement-adoption,
mermaid-shape-boundary-exactness

## Objective

Validate and preserve the already-shipped independent marker model through parsing,
layout, painting, and oracle extraction. The marker model and marker clearance work are
already shipped. This spec focuses on edge identity, metadata preservation, parallel
relations, and executable semantic checks — ensuring the oracle can actually assert marker
kind and marker end, not just node presence.

## Boundaries

**In scope:**
- Every class relation carries: unique `edge_id`, semantic source, semantic target, source
  marker, target marker, line style, label, optional source multiplicity, optional target
  multiplicity.
- Exact marker mappings: inheritance (hollow triangle at general class), composition
  (filled diamond at owner), aggregation (hollow diamond at aggregate), directed
  association (target arrow), dependency (dashed line + target open arrow), realization
  (dashed line + target hollow triangle).
- Rank reversal and route orientation must never change marker ownership.
- Label and marker metadata keyed by `edge_id`.
- Parallel-relation tests with identical `(src, dst)` but different labels, marker kinds,
  and styles — each remains distinct.
- Reference comparison extended to assert: marker kind, marker end, line style, source,
  target, label.
- Invariant-driven route clipping: verify endpoint lies on class-card boundary; implement
  clipping only where the invariant currently fails.
- Invariant-driven label placement: choose longest stable segment; reserve label
  rectangle; implement only through a general route-label utility, not a fixture patch.
- Do not implement clipping or segment placement based solely on old render artifacts;
  implement only when new geometry tests demonstrate a failing invariant.

**Out of scope:**
- Flowchart, state, ER, architecture, requirement compilation.
- Adding new relationship types.
- Visual screenshot comparison.
- Reimplementing the marker model (already shipped in `class-diagram-marker-clearance`).

**Never:**
- Use `(src, dst)` as relation identity when parallel relations exist.
- Allow rank reversal or route orientation to change which class receives a marker.
- Skip a marker semantic assertion.
- Accept a reference comparison that executes zero marker assertions.

## Acceptance Criteria

For `class-relationships-all`, every relation has the correct:
- [x] AC1: Source and target (correct classes, not swapped by rank reversal).
- [x] AC2: Marker kind (hollow triangle, filled diamond, hollow diamond, open arrow,
  none) at the correct end.
- [x] AC3: Solid or dashed line style matching the source token.
- [x] AC4: Label matching the source token.
- [x] AC5: Parallel relations remain distinct — two relations with the same `(src, dst)`
  but different labels produce different `edge_id` values and distinct route records.
- [x] AC6: Class diagrams use a single Python Sugiyama path (no ELK path exists for this
  diagram type). The criterion is **path-stability**: compiling the same source twice
  yields identical `edge_id → (source_marker, target_marker)` mappings. <!-- formerly: "survive both ELK and Python fallback paths" — amended because ELK is not available for class diagrams -->
- [x] AC7: No marker semantic check is skipped in the oracle comparison.
- [x] AC8: The oracle executes at least one marker assertion per edge; a fixture where
  all marker checks are skipped fails the oracle (enforced by `OracleResult(PASS)` requiring
  `len(checks) > 0`).
- [x] AC9: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

All tests compile from class diagram source strings; no hardcoded coordinates.

- **Marker mapping completeness:** parametrize over all six relationship types; compile a
  minimal diagram with one edge of each type; assert the returned `RoutedEdge` has the
  expected `source_marker` and `target_marker` values.
- **Rank reversal invariance:** construct a relation where ELK would reverse the rank
  order; assert the marker end (general class for inheritance, owner for composition)
  does not change after rank reversal.
- **Parallel relations distinct:** compile a class diagram with two edges from class A
  to class B with different labels; assert both have distinct `edge_id` values and appear
  as separate records.
- **Label keyed by edge_id:** compile a diagram with multiple labeled relations; assert
  each label is retrievable by `edge_id` and not by `(src, dst)`.
- **Oracle marker assertions:** run the oracle on `class-relationships-all`; assert
  `len(oracle_result.checks)` is greater than zero; assert `OracleStatus` is not PASS
  when a marker mismatch is introduced.
- **Dashed style:** compile a dependency and a realization relation; assert each
  `RoutedEdge.edge_style == "dashed"`.
- **Solid style:** compile inheritance, composition, aggregation, directed association;
  assert each `RoutedEdge.edge_style == "solid"`.
- **Path stability (AC6):** compile the same class diagram source twice; assert all
  `edge_id → (source_marker, target_marker)` pairs are identical across both runs.
  (Note: class diagrams have no ELK path — the Python Sugiyama path is the only path.)
