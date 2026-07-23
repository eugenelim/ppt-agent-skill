# Implementation Plan — Mermaid Architecture ELK Metadata Preservation

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/architecture.py` (remove `_elk_routes_to_specs` from success path; edge-ID migration; measured labels); `tests/test_architecture_conformance.py` (new or extended).
2. Done when: `pytest tests/` passes; `grep -n "_elk_routes_to_specs" scripts/mermaid_render/layout/architecture.py` returns zero matches in the success path; fixed-side port constraints survive round-trip for `architecture-complex`.
3. Not changing: flowchart, state, ER, class, requirement compilers; the ELK adapter's JSON serialization direction; renderer painters.

**Declined patterns:**
- Tempted to keep `_elk_routes_to_specs` as a utility for the fallback path; declining — the fallback must satisfy the same `FinalizedLayout` contract directly, not via a lossy intermediate.
- Tempted to default to `PortSide.AUTO` when a port side cannot be determined; declining — AUTO is only permitted for non-fixed ports; fixed ports must preserve their declared side.

---

## Tasks

### Task 1: Remove `_elk_routes_to_specs` from success path
Depends on: none
Verification: TDD

**Tests:**
- `test_success_path_does_not_call_elk_routes_to_specs`: mock ELK to return a valid layout; compile `architecture-complex`; assert `_elk_routes_to_specs` is not called.
- `test_success_path_returns_finalized_layout`: compile with mocked ELK; assert return type is `FinalizedLayout`.

**Approach:**
- In `architecture.py`, locate the `if elk_result:` branch.
- Replace the call to `_elk_routes_to_specs(elk_result)` with the enrichment path that returns the `FinalizedLayout` directly.
- The enrichment step retains architecture semantic metadata by `edge_id`.

---

### Task 2: Edge-ID–keyed semantic metadata
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_edge_id_keyed_metadata`: compile an architecture diagram with two edges from the same source service; assert both edges are retrievable by `edge_id`; assert neither is retrievable by `(src, dst)` tuple.
- `test_label_keyed_by_edge_id`: compile a labeled architecture edge; assert `RoutedEdge.label_layout` is set and corresponds to the edge by `edge_id`.

**Approach:**
- In the enrichment step, build a dict `{edge_id: ArchEdgeMeta}` for all architecture-specific metadata (service source/target, declared sides, bidirectionality, label).
- Remove any `{(src, dst): label}` dict construction.

---

### Task 3: Fixed-side port preservation
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_fixed_side_right_preserved`: compile `architecture-complex`; for the `lb:R→L:api` relation, assert `src_port.side == PortSide.RIGHT`.
- `test_fixed_side_left_preserved`: for the same relation, assert `dst_port.side == PortSide.LEFT`.
- `test_fixed_side_bottom_preserved`: for the `api:B→T:cache` relation, assert `src_port.side == PortSide.BOTTOM`.
- `test_no_auto_for_fixed_ports`: compile; assert no `RoutedEdge` with a declared fixed side has `PortSide.AUTO`.

**Approach:**
- In the enrichment step, for each ELK edge, look up the original `LayoutEdge` by `edge_id`; read `src_fixed_side` and `dst_fixed_side`.
- If `src_fixed_side is not None`, set `RoutedEdge.src_port.side = src_fixed_side`.
- Do not override fixed sides with ELK-returned AUTO values.

---

### Task 4: Measured labels for architecture
Depends on: none
Verification: TDD

**Tests:**
- `test_service_label_uses_measurer`: compile an architecture diagram; for each service node, assert the label uses a `TextLayout` from `_MEASURER.layout`, not a character-count estimate.
- `test_group_min_width_from_measurement`: two architecture groups with different label lengths; assert the wider-label group has a greater minimum width.
- `test_edge_label_measured`: compile an architecture diagram with a labeled edge; assert `RoutedEdge.label_layout.width > 0`.

**Approach:**
- In `architecture.py`, replace any character-count width estimation for service labels with `_MEASURER.layout(label, ARCH_SERVICE_LABEL)`.
- Use measured `width` as the service node minimum width.
- For edge labels, create a `TextLayout` from `_MEASURER.layout(edge_label, EDGE_LABEL)`.

---

### Task 5: Fallback contract compliance
Depends on: none
Verification: TDD

**Tests:**
- `test_fallback_backend_metadata`: trigger `ElkUnavailable`; assert `metadata.backend == "python-fallback"` and `metadata.fallback_reason == "elk-unavailable"`.
- `test_fallback_satisfies_finalized_layout_contract`: trigger fallback; assert the result has `nodes`, `groups`, `edges`, `canvas_bounds` — all required `FinalizedLayout` fields.
- `test_incomplete_elk_result_rejected`: supply an ELK result missing required edge sections; assert `ElkInvalidResult` is raised.

**Approach:**
- In the `ElkUnavailable` exception handler, call the existing heuristic layout path and wrap its output in a `FinalizedLayout` with `metadata.backend = "python-fallback"` and `metadata.fallback_reason = "elk-unavailable"`.
- Add a validation step that rejects incomplete ELK results (missing `sections` on an edge) before enrichment.

---

### Task 6: Architecture conformance test suite
Depends on: Tasks 1–5
Verification: TDD

**Tests:**
- `test_architecture_complex_fixed_sides`: all four fixed-side constraints from the spec AC survive compilation.
- `test_architecture_complex_unique_edge_ids`: all relations have distinct `edge_id` values.
- `test_architecture_complex_all_services_contained`: all services are within their declared group bounds.
- `test_architecture_complex_no_rerouting`: mock ELK; assert the ELK result is not rerouted through the Python fallback.
- `test_architecture_complex_measured_labels`: all label widths derive from `TextMeasurer`.

**Approach:**
- Create or extend `tests/test_architecture_conformance.py`.
- Each test compiles `architecture-complex` (or a synthetic equivalent) using the production pipeline.
- Assert the structural and semantic invariants from the spec's AC list.
