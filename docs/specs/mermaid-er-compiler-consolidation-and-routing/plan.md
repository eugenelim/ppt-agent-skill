# Implementation Plan — ER Compiler Consolidation and Routing

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/er.py` (delete `_compile_er_legacy`; measured cards; ELK routing; edge-ID cardinality); `tests/test_er_conformance.py` (new or extended).
2. Done when: `pytest tests/` passes; `_compile_er_legacy` is not importable; all entity card widths derive from `TextMeasurer`; all relationships have unique `edge_id`; cardinality ends match parsed semantics for all four test patterns.
3. Not changing: flowchart, state, architecture, class, requirement compilers; the oracle contract, text measurer, or shape geometry.

**Declined patterns:**
- Tempted to keep `_compile_er_legacy` as a reference for new tests; declining — the spec requires deletion after test migration; tests must compile against the active path only.
- Tempted to hardcode cardinality glyph angles; declining — glyphs must rotate with the route tangent computed at layout time.

---

## Tasks

### Task 1: Migrate all tests from legacy to active compiler
Depends on: none
Verification: Goal-based check

**Done when:** `grep -rn "_compile_er_legacy" tests/` returns zero matches; `pytest tests/` passes.

**Approach:**
- For each test that calls `_compile_er_legacy` directly or indirectly, replace the call with `compile_er_layout` and verify the test still passes.
- If the test was relying on legacy-specific behavior, update the assertion to match the active compiler's output.

---

### Task 2: Delete `_compile_er_legacy`
Depends on: Task 1
Verification: Goal-based check

**Done when:** `grep -rn "_compile_er_legacy" scripts/` returns zero matches; `pytest tests/` passes.

**Approach:**
- Delete the `_compile_er_legacy` function from `er.py`.
- Remove any import of `_compile_er_legacy` in test or tool files.
- Verify `compile_er` alias still works as a redirect to `compile_er_layout`.

---

### Task 3: Measured entity card sizing
Depends on: none
Verification: TDD

**Tests:**
- `test_er_card_width_from_attribute_name`: two entities with short vs long attribute names; assert wider name produces wider card.
- `test_er_header_has_real_text_layout`: compile an ER entity; assert the header has `TextLayout.width > 0 and TextLayout.height > 0`.
- `test_er_row_height_from_measurement`: assert row heights match the measured line height for the ER cell style.

**Approach:**
- In `compile_er_layout`, for each entity, measure: entity header (ER_ENTITY_HEADER style), key badge (ER_CELL), type string (ER_CELL), attribute name (ER_CELL).
- Compute card width = `max(measured_header_width, max_column_widths + badge_width + padding)`.
- Compute row height = max(key_height, type_height, name_height) + row_padding.
- Create real `TextLayout` objects for headers and each attribute row.

---

### Task 4: Unique edge IDs and explicit ports for relationships
Depends on: none
Verification: TDD

**Tests:**
- `test_unique_edge_ids`: compile a multi-relationship ER diagram; assert all `edge_id` values are distinct.
- `test_explicit_ports_per_relationship`: compile; for each relationship, assert both `src_port` and `dst_port` are not None and have a non-AUTO side.
- `test_adjacent_relationships_distinct_ports`: compile two relationships on the same entity on the same side; assert they use distinct port positions.

**Approach:**
- In `compile_er_layout`, assign a deterministic `edge_id` (e.g. `f"rel{ordinal}"` based on parse order, or a hash of `(src_entity, dst_entity, label, ordinal)`) to each relationship before routing. Do not use `uuid4` — IDs must be stable across repeated runs.
- Assign explicit `src_port` and `dst_port` from the entity's declared connection sides; for adjacent relationships on one entity, use port offsets.

---

### Task 5: CardinalityEnd semantics
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_cardinality_||--||`: parse `||--||`; assert `src_end.minimum == "ONE"`, `src_end.maximum == "ONE"`, `dst_end.minimum == "ONE"`, `dst_end.maximum == "ONE"`.
- `test_cardinality_||--o{`: parse `||--o{`; assert `dst_end.minimum == "ZERO"`, `dst_end.maximum == "MANY"`.
- `test_cardinality_}|--||`: parse `}|--||`; assert `src_end.minimum == "ONE"`, `src_end.maximum == "MANY"`, `dst_end.minimum == "ONE"`, `dst_end.maximum == "ONE"`.
- `test_cardinality_|o--|{`: parse `|o--|{`; assert correct minimum/maximum for both ends.

**Approach:**
- In the ER source parser, map each cardinality glyph character to `CardinalityEnd.minimum` and `CardinalityEnd.maximum` values.
- Store `CardinalityEnd` on each `LayoutEdge` before routing.

---

### Task 6: ELK orthogonal routing
Depends on: Tasks 4, 5
Verification: TDD

**Tests:**
- `test_elk_orthogonal_routing_used`: compile an ER diagram with ELK available; assert `metadata.backend == "elkjs"`.
- `test_fallback_routing_typed`: trigger `ElkUnavailable`; assert `metadata.fallback_reason == "elk-unavailable"`.
- `test_routes_do_not_enter_unrelated_entities`: compile `er-ecommerce`; for each relationship route, assert no waypoint is inside an unrelated entity card's bounding rectangle.

**Approach:**
- Convert the measured ER topology into a `LayoutGraph` with nodes (entity cards), edges (relationships), and ports.
- Call `layout_with_elk(graph)` with orthogonal routing options; on `ElkUnavailable`, use the existing deterministic topology layout as a typed fallback.
- Store waypoints in `RoutedEdge.waypoints` from the ELK sections.

---

### Task 7: Cardinality glyph orientation and label placement
Depends on: Task 6
Verification: TDD

**Tests:**
- `test_cardinality_glyph_follows_tangent`: compile an ER diagram with a horizontal relationship; assert the cardinality glyph angle matches the route tangent angle within 5 degrees.
- `test_label_not_overlapping_glyph`: compile a labeled relationship; assert label `TextLayout.bounds` and cardinality glyph bounds do not intersect.
- `test_label_on_longest_segment`: compile a relationship with multiple route segments; assert the label is placed on the longest clear segment.

**Approach:**
- After routing, for each relationship endpoint: compute the tangent direction from the last/first route segment; rotate the cardinality glyph to align with the tangent.
- Reserve endpoint distance for the cardinality glyph before computing label placement.
- Place the relationship label on the longest segment that doesn't overlap the glyph reservation areas.

---

### Task 8: HTML/SVG identity tests
Depends on: Tasks 3–7
Verification: TDD

**Tests:**
- `test_er_html_svg_same_entity_bounds`: compile an ER diagram; assert HTML and SVG receive the same entity `NodeLayout.bounds`.
- `test_er_html_svg_same_relationship_waypoints`: assert HTML and SVG receive the same `RoutedEdge.waypoints` for each relationship.

**Approach:**
- Add a thin test fixture that intercepts `FinalizedLayout` objects passed to HTML and SVG painters.
- Assert the intercepted layouts are equal.
