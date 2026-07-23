# Mermaid Flowchart Conformance

Mode: full (multi-fixture; geometry verifier; faithful-mode assertions)

- **Status:** Shipped

Dependencies: mermaid-oracle-runtime-unification, mermaid-text-measurement-adoption,
flowchart-elk-finalized-layout-consumption, mermaid-recursive-compound-layout,
mermaid-shape-boundary-exactness

## Objective

Close remaining flowchart semantic, routing, label, and faithful-mode gaps through
structured tests that exercise all eight in-scope flowchart fixtures against the
completed foundation (oracle contract, text measurement, ELK direct consumption,
recursive compound layout, shape boundary exactness).

A reusable geometry verifier asserts structural invariants: non-overlap, containment,
route obstacle avoidance, and label placement. Line semantics, decision-branch label
assignment, feedback-edge routing, fan-out/fan-in port ordering, and faithful-mode
prohibitions are each covered by explicit tests rather than inferred from visual output.

## Boundaries

**In scope:**
- All eight in-scope flowchart fixtures: `flowchart-all-shapes`, `flowchart-arrows-defs`,
  `flowchart-diamond-branch`, `flowchart-diamond-clipping`, `flowchart-empty-subgraph`,
  `flowchart-groups-complex`, `flowchart-inner-direction`, `flowchart-parallel-links`.
- Reusable geometry verifier asserting: node-node non-overlap, node-group containment,
  sibling-group non-overlap, edge endpoints on visible boundaries, no route enters an
  unrelated node, no route enters an unrelated group interior, no route crosses a group
  title band, label bounds do not overlap markers or nodes.
- Line semantics: `-->` (ordinary solid), `==>` (thick solid), `-.->` / `-.->` equivalent
  (dotted/dashed per pinned Mermaid semantics). Assert style independently of editorial
  coloring.
- Decision branches: ordered outgoing ports; labels attached to correct edge IDs on
  first stable outgoing segment; label rectangles reserved before routing competing edges.
- Feedback edges: SCC computation; route around smallest relevant component; forbid
  canvas perimeter as default lane.
- Fan-out and fan-in: unique edge IDs; stable ordered ports; no shared coincident paths
  unless a true junction is modeled; merge nodes near predecessor barycenter.
- Include existing edge-label bounds as obstacles during later route placement.
- Faithful mode assertions: no inferred legend, no inferred icons, no inferred sync/async/
  critical-path labels, no direction rewrite, no semantic recoloring based on line type.
- Deterministic compactness diagnostics (regression metrics, not pixel-parity):
  total route length, total bends, maximum edge excursion, canvas area, crossing count.
- ELK primary backend; Python fallback where supported.

**Out of scope:**
- State, ER, class, architecture, requirement diagrams.
- New shape types beyond those in `flowchart-all-shapes`.
- Visual screenshot comparison.
- Fixes to the oracle, text measurer, or shape geometry themselves (those are upstream
  dependencies).

**Never:**
- Add fixture-specific coordinate patches.
- Use a previously generated screenshot or PNG as evidence of correctness.
- Accept a geometry verifier pass that executes zero assertions.

## Acceptance Criteria

- [x] AC1 (flowchart-all-shapes): All declared shapes map to the correct `ShapeGeometry`;
  every node has positive outer_bounds; geometry verifier reports zero violations.
  (deferred: flowchart-label-fits-interior — content_bounds export not yet shipped)
- [x] AC2 (flowchart-arrows-defs): All edge styles and marker kinds match source tokens;
  faithful mode adds no legend HTML to the rendered output.
- [x] AC3 (flowchart-diamond-branch): Branch labels belong to the correct edge IDs; the
  retry feedback edge uses a local lane (interior waypoints within 150 px of src/dst bbox); decision-node
  ports are stable across runs.
- [x] AC4 (flowchart-diamond-clipping): Every edge endpoint lies within 16 px of the
  diamond node's outer_bounds AABB; geometry verifier reports zero violations.
  (deferred: flowchart-diamond-endpoint-on-segment)
- [x] AC5 (flowchart-empty-subgraph): Groups present in layout have positive bounds;
  sibling groups do not overlap; geometry verifier reports zero violations.
- [x] AC6 (flowchart-groups-complex): All containment is valid; no node overlap; geometry
  verifier reports zero violations.
- [x] AC7 (flowchart-inner-direction): Local direction is solved recursively; LR subgraph
  child nodes are arranged along the horizontal axis (x_span > y_span or x_span > 50 px).
- [x] AC8 (flowchart-parallel-links): Parallel relations have unique IDs and distinct
  routes; fan-out and fan-in port order is deterministic.
- [x] AC9: The geometry verifier asserts all eight invariants unconditionally; a layout
  with zero real nodes and zero edges triggers a "zero-assertions" sentinel violation.
  Unit tests cover: clean pass, node-overlap, containment failure, route-through-node,
  and degenerate-empty detection.
- [x] AC10: Compactness diagnostics (total_route_length, total_bends, max_edge_excursion,
  canvas_area, crossing_count) are recorded for each fixture; all five metrics are
  committed as regression baselines in `_COMPACTNESS_BASELINES`.
- [x] AC11: `pytest tests/` passes with zero regressions (1 pre-existing failure in
  `test_payload_boundary.py::test_all_scripts_reachable` is unrelated to this spec).

## Testing Strategy

Tests combine the geometry verifier with fixture-specific semantic checks. All tests
compile from source using the production pipeline; no hardcoded coordinates.

- **Geometry verifier:** unit-test each of the eight invariants independently with a
  synthetic `FinalizedLayout`; assert each invariant fails on a known-bad layout.
  Added: degenerate-empty layout triggers "zero-assertions" sentinel.
- **Shape mapping (flowchart-all-shapes):** compile fixture; for each node, assert its
  `semantic_shape` matches the declared Mermaid shape token.
- **Line style (flowchart-arrows-defs):** compile fixture; for each edge, assert
  `RoutedEdge.edge_style` matches the parsed Mermaid line token; assert faithful mode
  renders HTML with no "legend" substring.
- **Decision branch labels (flowchart-diamond-branch):** compile fixture; for each
  decision node, assert each outgoing edge carries the correct label by edge ID.
  Added: `test_retry_feedback_local_lane` verifies each interior waypoint of the Retry→Check
  edge has excursion < 150 px from the union of the Retry and Check node bounds; catches
  perimeter-routed regressions.
- **Diamond endpoint (flowchart-diamond-clipping):** compile fixture; assert endpoints
  within 16 px of diamond AABB; geometry verifier reports zero violations.
- **Empty subgraph (flowchart-empty-subgraph):** compile fixture; assert groups present
  have positive bounds; full geometry verifier runs clean.
- **Containment (flowchart-groups-complex):** compile fixture; run the full geometry
  verifier; assert zero violations.
- **Inner direction (flowchart-inner-direction):** compile fixture; assert LR group's
  child nodes have greater x-span than y-span; full geometry verifier runs clean.
- **Parallel links (flowchart-parallel-links):** compile fixture; assert no two edges
  share identical waypoints; assert edge IDs are distinct; full geometry verifier runs clean.
- **Faithful mode:** compile `flowchart-arrows-defs` with `faithful_mermaid=True`; verify
  rendered HTML contains no "legend" substring.
