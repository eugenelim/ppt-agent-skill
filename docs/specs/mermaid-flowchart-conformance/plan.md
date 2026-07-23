# Implementation Plan — Mermaid Flowchart Conformance

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `tests/test_flowchart_conformance.py` (new); `scripts/mermaid_render/layout/_strategies.py` or flowchart compiler (line-style, decision-branch, feedback-edge, fan-out/fan-in fixes); a shared `tests/geometry_verifier.py` utility.
2. Done when: `pytest tests/test_flowchart_conformance.py` passes for all eight fixtures; the geometry verifier reports zero violations; compactness diagnostics are committed as regression baselines.
3. Not changing: the oracle contract, text measurer, shape geometry, or compound layout (all upstream dependencies); sequence, state, ER, architecture, or class compilers.

**Declined patterns:**
- Tempted to add fixture-specific coordinate patches; declining — the spec prohibits this; fixes must generalize through semantic model or layout rules.
- Tempted to skip the Python fallback path; declining — the spec requires both ELK primary and Python fallback where supported.
- Tempted to use screenshot comparison as acceptance; declining — the spec explicitly prohibits using visual artifacts as evidence.

---

## Tasks

### Task 1: Geometry verifier utility
Depends on: none
Verification: TDD

**Tests:**
- `test_verifier_detects_node_overlap`: supply a `FinalizedLayout` with two overlapping nodes; assert verifier reports a violation.
- `test_verifier_detects_containment_failure`: supply a node outside its declared group; assert containment violation.
- `test_verifier_detects_route_through_node`: supply a route that passes through an unrelated node's bounding box; assert route-obstacle violation.
- `test_verifier_passes_on_clean_layout`: supply a synthetically clean `FinalizedLayout`; assert zero violations.

**Approach:**
- Create `tests/geometry_verifier.py` with `verify_layout(layout: FinalizedLayout) -> list[GeometryViolation]`.
- Implement eight checks: node-node non-overlap, node-group containment, sibling-group non-overlap, edge endpoints on visible boundaries, no route through unrelated node, no route through unrelated group interior, no route across group title band, label bounds not overlapping markers or nodes.
- Return a list of `GeometryViolation(kind, description, offending_ids)` objects.

---

### Task 2: Line-style and marker-kind fidelity
Depends on: none
Verification: TDD

**Tests:**
- `test_ordinary_solid_edge_style`: compile `flowchart-arrows-defs`; for each `-->` edge, assert `RoutedEdge.edge_style == "solid"` and `target_marker == MarkerKind.ARROW`.
- `test_thick_edge_style`: for each `==>` edge, assert `edge_style == "thick"`.
- `test_dotted_dashed_edge_style`: for each `-.->` edge, assert `edge_style in {"dashed", "dotted"}` per pinned Mermaid semantics.
- `test_faithful_no_legend`: compile `flowchart-arrows-defs` with `faithful_mermaid=True`; assert no legend node in the layout.

**Approach:**
- Compile `flowchart-arrows-defs` and map each edge's source token to the expected `edge_style` and `target_marker`.
- Assert that `RoutedEdge.edge_style` matches without any editorial coloring pass having run.
- For faithful mode: add a test that inspects the compiled layout for any node whose label is not present in the source Mermaid text.

---

### Task 3: Decision-branch label assignment
Depends on: none
Verification: TDD

**Tests:**
- `test_diamond_branch_labels_by_edge_id`: compile `flowchart-diamond-branch`; for each decision node, assert each outgoing edge carries the correct label by `edge_id`.
- `test_decision_ports_stable`: compile the same fixture twice; assert outgoing port order is identical.
- `test_retry_feedback_local_lane`: compile `flowchart-diamond-branch`; find the retry edge; assert its waypoints stay within the smallest SCC bounding box, not at the canvas perimeter.

**Approach:**
- In the flowchart compiler, when building `LayoutEdge` objects for decision outgoing edges, assign the label to the edge by its `edge_id` before port assignment.
- Ensure port order is derived from a deterministic ordering (e.g. source-text order) and stored in a stable structure.
- For the retry edge, implement SCC detection and route the feedback edge around the SCC bounding box.

---

### Task 4: Fan-out and fan-in port ordering
Depends on: none
Verification: TDD

**Tests:**
- `test_parallel_links_distinct_routes`: compile `flowchart-parallel-links`; assert no two edges share identical waypoints.
- `test_parallel_links_unique_edge_ids`: compile; assert all edge IDs are distinct.
- `test_fan_out_port_order_deterministic`: compile twice; assert the port order for fan-out nodes is identical.

**Approach:**
- In the flowchart compiler, assign stable ordered ports for fan-out nodes (multiple outgoing edges) and fan-in nodes (multiple incoming edges).
- For parallel links between the same pair of nodes: assign distinct port positions that force distinct routes; use existing port-offset mechanism in ELK.
- Reserve label rectangles as obstacles before placing competing edge routes.

---

### Task 5: Compactness diagnostics
Depends on: none
Verification: Goal-based check

**Done when:** `pytest tests/test_flowchart_conformance.py -k "compactness"` passes and prints a table of compactness metrics for each fixture; the metrics are committed as baseline constants.

**Approach:**
- Add `compute_compactness(layout: FinalizedLayout) -> CompactnessReport` to `tests/geometry_verifier.py`.
- Compute: total route length (sum of all edge waypoint distances), total bends (count of direction changes), maximum edge excursion (max distance from any waypoint to its endpoint component bounding box), canvas area, crossing count (pair-wise segment intersection count).
- In `test_flowchart_conformance.py`, call `compute_compactness` for each fixture and assert each metric is ≤ its baseline constant.

---

### Task 6: Per-fixture conformance tests
Depends on: Tasks 1, 2, 3, 4, 5
Verification: TDD

**Tests (one parametrized test class per fixture):**
- `test_all_shapes_shape_geometry`: compile `flowchart-all-shapes`; for each node, assert `ShapeGeometry` class matches the declared Mermaid shape token; run geometry verifier; assert zero violations.
- `test_arrows_defs_style_match`: compile `flowchart-arrows-defs`; assert all edge styles match source tokens; run geometry verifier.
- `test_diamond_branch_labels_and_feedback`: compile `flowchart-diamond-branch`; assert label assignment and feedback lane; run geometry verifier.
- `test_diamond_clipping_endpoint_on_outline`: compile `flowchart-diamond-clipping`; assert all endpoints on diamond outline; run geometry verifier.
- `test_empty_subgraph_bounds`: compile `flowchart-empty-subgraph`; assert all empty groups have positive bounds; assert non-overlap.
- `test_groups_complex_containment`: compile `flowchart-groups-complex`; run geometry verifier; assert zero containment violations.
- `test_inner_direction_recursive`: compile `flowchart-inner-direction`; for each group with a local direction, assert children are arranged along that axis.
- `test_parallel_links_distinct`: compile `flowchart-parallel-links`; assert distinct routes and unique IDs.

**Approach:**
- Create `tests/test_flowchart_conformance.py`.
- Each test function: compile the fixture using the production pipeline; run the geometry verifier; assert fixture-specific semantic checks from Tasks 2–4.
- Gate the full suite with `@pytest.mark.flowchart_conformance` for easy selective execution.
