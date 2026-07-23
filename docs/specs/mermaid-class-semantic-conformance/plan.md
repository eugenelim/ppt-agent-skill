# Implementation Plan — Mermaid Class Semantic Conformance

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_strategies.py` or class compiler module (edge-ID migration, marker metadata keying); `tools/mermaid_fidelity/compare/semantic.py` (extend comparison to assert markers); `tests/test_class_conformance.py` (new or extended).
2. Done when: `pytest tests/` passes; every class relation has a unique `edge_id`; marker metadata survives both ELK and Python fallback; oracle comparison executes at least one marker assertion per edge; no `(src, dst)` tuple key in the class pipeline.
3. Not changing: the marker model or clearance values (shipped in `class-diagram-marker-clearance`); flowchart, state, ER, architecture, requirement compilers.

**Declined patterns:**
- Tempted to use the existing `(src, dst)` as a lookup key for performance; declining — parallel relations share `(src, dst)` and require `edge_id` for disambiguation.
- Tempted to implement clipping or segment placement based on old visual artifacts; declining — the spec requires new geometry tests to demonstrate a failing invariant before implementing these features.

---

## Tasks

### Task 1: Unique edge IDs for all class relations
Depends on: none
Verification: TDD

**Tests:**
- `test_unique_edge_ids`: compile `class-relationships-all`; assert all relation `edge_id` values are distinct.
- `test_parallel_relations_distinct_ids`: compile a class diagram with two edges between the same classes but different labels; assert both have distinct `edge_id` values.

**Approach:**
- In the class compiler, assign a deterministic `edge_id` (e.g. `f"rel{ordinal}"` based on parse order, or a hash of `(src_class, dst_class, relationship_type, label, ordinal)`) to each relation before any rank reversal or route orientation processing. Do not use `uuid4` — IDs must be stable across repeated runs.
- Ensure the ID is preserved through rank reversal and all subsequent processing steps.

---

### Task 2: Marker metadata keyed by edge_id
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_marker_metadata_by_edge_id`: compile a class diagram with a labeled relation; assert the marker and label are retrievable by `edge_id`.
- `test_no_src_dst_tuple_key_in_class_pipeline`: `grep -n '(src.*dst)' scripts/mermaid_render/layout/` returns zero lookup-dict usages in the class pipeline.

**Approach:**
- Build enrichment dict `{edge_id: ClassEdgeMeta}` where `ClassEdgeMeta` holds `source_marker`, `target_marker`, `edge_style`, `label`, `source_multiplicity`, `target_multiplicity`.
- Remove any `{(src, dst): label}` or `{(src, dst): marker}` dict construction in the class compiler.

---

### Task 3: Marker mapping validation
Depends on: Tasks 1, 2
Verification: TDD

**Tests:**
- `test_inheritance_hollow_triangle_at_general`: compile a class with an inheritance relation; assert `RoutedEdge.target_marker == MarkerKind.HOLLOW_TRIANGLE` at the general class.
- `test_composition_filled_diamond_at_owner`: compile a composition relation; assert `RoutedEdge.source_marker == MarkerKind.FILLED_DIAMOND` at the owner class.
- `test_aggregation_hollow_diamond`: compile an aggregation; assert `MarkerKind.HOLLOW_DIAMOND` at the aggregate.
- `test_directed_association_target_arrow`: compile a directed association; assert `MarkerKind.ARROW` at target, `MarkerKind.NONE` at source.
- `test_dependency_dashed_open_arrow`: compile a dependency; assert `edge_style == "dashed"` and `target_marker == MarkerKind.OPEN_ARROW`.
- `test_realization_dashed_hollow_triangle`: compile a realization; assert `edge_style == "dashed"` and `target_marker == MarkerKind.HOLLOW_TRIANGLE`.

**Approach:**
- Compile a class diagram with one edge of each type.
- Assert the `RoutedEdge` fields match the expected values.
- Introduce a failing assertion on purpose in a test that verifies rank reversal cannot swap marker ends.

---

### Task 4: Rank-reversal marker invariance
Depends on: Task 3
Verification: TDD

**Tests:**
- `test_rank_reversal_does_not_swap_markers`: construct a class relation where ELK would reverse the rank order; assert `source_marker` and `target_marker` are on the same respective class before and after rank reversal.
- `test_route_orientation_does_not_swap_markers`: route an edge in both directions (ELK may flip); assert marker ownership does not change.

**Approach:**
- After ELK layout and rank reversal, check if the edge direction was reversed; if so, swap `src_node_id` and `dst_node_id` in the `RoutedEdge` accordingly but do NOT swap markers.
- Alternatively, always anchor markers to the semantic source/target from `ClassEdgeMeta` (by `edge_id`), not to the route direction.

---

### Task 5: Oracle marker assertions
Depends on: none
Verification: TDD

**Tests:**
- `test_oracle_asserts_markers`: run the oracle on `class-relationships-all`; assert `checks_executed` for marker assertions is > 0.
- `test_oracle_fails_on_marker_mismatch`: introduce a marker mismatch; assert `OracleStatus.FAIL`, not PASS.
- `test_oracle_no_marker_check_skipped`: assert no relation with a non-NONE marker has its marker check skipped.

**Approach:**
- Extend `tools/mermaid_fidelity/compare/semantic.py` to include marker kind and marker end in the relation comparison model (if not already done by `mermaid-oracle-runtime-unification`).
- For each class relation, add an `OracleCheck` that compares `source_marker` and `target_marker` against the reference.
- Ensure the check is not conditional on a "skip marker" flag.

---

### Task 6: Parallel-relation tests
Depends on: Tasks 1, 2
Verification: TDD

**Tests:**
- `test_parallel_relations_both_in_oracle`: compile a class diagram with two parallel relations; run the oracle; assert both relations appear in the comparison result.
- `test_parallel_relations_distinct_routes`: assert the two parallel relations have distinct waypoints.
- `test_parallel_relations_distinct_labels`: assert each label is retrievable by its own `edge_id`.

**Approach:**
- Compile a class diagram with two edges sharing the same `(src, dst)` class pair but with different labels and/or marker kinds.
- Assert both appear in `FinalizedLayout.edges` with distinct `edge_id` values and distinct `waypoints`.

---

### Task 7: Class conformance test suite
Depends on: Tasks 1–6
Verification: TDD

**Tests:**
- `test_class_relationships_all_conformance`: compile `class-relationships-all`; for every relation, assert source, target, marker kind, marker end, style, and label match the source; run the oracle; assert non-vacuous PASS.
- `test_fallback_path_marker_preservation`: trigger the Python fallback; compile the same class diagram; assert marker metadata is identical to the ELK path result.

**Approach:**
- Create or extend `tests/test_class_conformance.py`.
- Compile `class-relationships-all` and assert all relation fields from the spec's AC list.
- Use the oracle from `mermaid-oracle-runtime-unification` to assert the comparison executes nonzero marker assertions.
