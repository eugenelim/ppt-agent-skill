# Mermaid Flowchart Conformance

Mode: full (multi-fixture; geometry verifier; faithful-mode assertions)

- **Status:** Draft

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

- [ ] AC1 (flowchart-all-shapes): All declared shapes map to the correct `ShapeGeometry`;
  labels fit within the usable interior; every route endpoint lies on the visible outline.
- [ ] AC2 (flowchart-arrows-defs): All edge styles and marker kinds match source tokens;
  faithful mode adds no legend or semantic interpretation.
- [ ] AC3 (flowchart-diamond-branch): Branch labels belong to the correct edge IDs; the
  retry edge uses a local feedback lane; decision-node ports are stable across runs.
- [ ] AC4 (flowchart-diamond-clipping): Every edge endpoint lies on a diamond segment;
  no rectangular clipping path remains.
- [ ] AC5 (flowchart-empty-subgraph): Empty compounds have measured non-zero bounds;
  sibling groups do not overlap.
- [ ] AC6 (flowchart-groups-complex): All containment is valid; unrelated edges do not
  traverse group interiors.
- [ ] AC7 (flowchart-inner-direction): Local direction is solved recursively; no post-
  layout coordinate rotation is applied.
- [ ] AC8 (flowchart-parallel-links): Parallel relations have unique IDs and distinct
  routes; fan-out and fan-in port order is deterministic.
- [ ] AC9: The geometry verifier asserts all eight invariants and executes at least one
  assertion for each fixture; a fixture with zero assertions fails the verifier.
- [ ] AC10: Compactness diagnostics are recorded for each fixture; thresholds are
  committed as regression baselines.
- [ ] AC11: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

Tests combine the geometry verifier with fixture-specific semantic checks. All tests
compile from source using the production pipeline; no hardcoded coordinates.

- **Geometry verifier:** unit-test each of the eight invariants independently with a
  synthetic `FinalizedLayout`; assert each invariant fails on a known-bad layout.
- **Shape mapping (flowchart-all-shapes):** compile fixture; for each node, assert its
  `ShapeGeometry` class matches the declared Mermaid shape token.
- **Line style (flowchart-arrows-defs):** compile fixture; for each edge, assert
  `RoutedEdge.edge_style` matches the parsed Mermaid line token.
- **Decision branch labels (flowchart-diamond-branch):** compile fixture; for each
  decision node, assert each outgoing edge carries the correct label by edge ID.
- **Diamond endpoint (flowchart-diamond-clipping):** compile fixture; for each edge
  incident to a diamond node, assert the endpoint lies on a diamond segment (not a
  rectangular bounding box) within 0.5-pixel tolerance.
- **Empty subgraph (flowchart-empty-subgraph):** compile fixture; assert each empty
  group's `GroupLayout.bounds` has positive width and height.
- **Containment (flowchart-groups-complex):** compile fixture; run the geometry verifier;
  assert zero containment violations.
- **Inner direction (flowchart-inner-direction):** compile fixture; for each group with a
  declared local direction, assert its child nodes are arranged along that axis.
- **Parallel links (flowchart-parallel-links):** compile fixture; assert no two edges
  share identical waypoints; assert edge IDs are distinct.
- **Faithful mode:** compile `flowchart-arrows-defs` with `faithful_mermaid=True`; assert
  no legend node, no icon node, no semantic-coloring attribute in the output.
