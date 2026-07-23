# Mermaid Recursive Compound Layout

Mode: full (structural — new abstraction layer; new dataclasses; multi-file)

- **Status:** Draft

Merges: backlog-mermaid-p3-compound-layout, backlog-compound-elk-ac1-ac3

## Objective

The Python fallback still contains leaf-first group repositioning and subsequent group
separation, pushing, and bbox recomputation after an already-laid-out graph. This is a
correction pass over a completed layout rather than a true compound-layout algorithm.
The result is post-layout coordinate shuffling that can violate containment and produce
non-deterministic group overlap when compound structures are deep.

This spec replaces that post-layout correction with a bottom-up recursive compound
layout: a `CompoundNode` tree is built before placement; compounds are processed
innermost-first; each compound's finalized internal geometry is translated into parent
coordinates via proxy expansion; cross-boundary transitions use explicit `BoundaryGate`
objects. ELK receives the full hierarchy where supported; the Python fallback applies the
same bottom-up algorithm without post-placement coordinate rotation.

Depends on: `flowchart-elk-finalized-layout-consumption` (the FinalizedLayout pipeline
must be direct before compound enrichment can work without a second reconstruction).

## Boundaries

**In scope:**
- `CompoundNode` frozen dataclass: `group_id`, `label_layout`, `local_direction`,
  `child_node_ids`, `child_groups`, `padding`, `minimum_size`.
- Build the complete `CompoundNode` tree before placement.
- Edge partitioning by scope: intra-group, child-to-parent, parent-to-child,
  sibling-to-sibling, multi-level cross-hierarchy.
- Bottom-up processing: lay out direct children per group's local direction; reserve
  title and padding; finalize internal routes; compute measured compound bounds; expose
  completed compound as a proxy node to its parent.
- Proxy expansion: translate finalized internal geometry into parent coordinates.
- `BoundaryGate` frozen dataclass: `gate_id`, `group_id`, `side` (PortSide),
  `point` (Point), `semantic_node_id`, `edge_id`, `kind` (ENTRY | EXIT).
- Preserve through gates: semantic endpoint, routing endpoint, gate, scope.
- ELK path: send the complete hierarchy; set local child directions; preserve returned
  group and cross-hierarchy edge geometry.
- Python fallback path: same bottom-up proxy algorithm; no post-layout coordinate
  rotation or shuffle of child coordinates.
- Empty groups: measured proxy node using measured title width, title band, configured
  padding, deterministic minimum content size.
- Group interiors and title bands as routing constraints.
- Delete primary-path calls to group separation, member pushing, and bbox recomputation
  after recursive layout is proven; keep temporary compatibility wrappers only while
  tests migrate.
- Compound layout tests from `backlog-compound-elk-ac1-ac3` run with locked dependency
  install.

**Out of scope:**
- Sequence diagram compound structures.
- Changes to the ELK adapter's external JSON serialization.
- Shape boundary mathematics (see `mermaid-shape-boundary-exactness`).
- Cross-diagram-type sharing of compound logic beyond flowchart/state.

**Never:**
- Apply a coordinate shuffle or rotation after finalized placement.
- Route an internal edge through a parent group's exterior.
- Use a group title band crossing as a valid route path.

## Acceptance Criteria

- [ ] AC1: Empty groups receive deterministic non-zero bounds and placement; identical
  source produces identical bounds across repeated clean runs.
- [ ] AC2: Nested local directions (e.g. inner LR inside outer TB) are solved before
  parent layout; the inner group's axis is independent of the outer group's axis.
- [ ] AC3: Child nodes and child groups are geometrically contained within their parent
  group's finalized bounds (inclusive of padding).
- [ ] AC4: Sibling groups do not overlap after recursive layout.
- [ ] AC5: Cross-boundary edges pass through explicit `BoundaryGate` objects; each gate
  has `gate_id`, `group_id`, `side`, `point`, `semantic_node_id`, `edge_id`, and `kind`.
- [ ] AC6: Internal routes stay inside their compound; no internal route exits the
  compound's bounds.
- [ ] AC7: Group title bands are not crossed by route waypoints.
- [ ] AC8: No primary path applies a coordinate shuffle or rotation after finalized
  placement is returned.
- [ ] AC9: HTML and SVG painters expose the same containment tree and gate geometry.
- [ ] AC10: The compound layout tests from `backlog-compound-elk-ac1-ac3` (ELK inner-
  direction fix, AC1–AC3) continue to pass.
- [ ] AC11: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

All tests are deterministic unit/integration tests. ELK-dependent tests are gated with
`@requires_elk`.

- **CompoundNode tree construction:** assert that a nested group hierarchy produces a
  `CompoundNode` tree with correct parent-child relationships and `local_direction` per
  group.
- **Bottom-up processing order:** assert that a three-level hierarchy processes innermost
  group first; assert that the innermost group's bounds are finalized before the
  intermediate group's proxy is built.
- **Containment invariant:** parametrize over flat/nested/deeply-nested hierarchies;
  assert every child node's bounding box is contained within its parent group's bounds.
- **Sibling non-overlap:** construct two sibling groups; assert their bounds do not
  intersect.
- **BoundaryGate fields:** construct a cross-boundary edge; assert its `BoundaryGate`
  carries all required fields with correct `kind` (ENTRY/EXIT per direction).
- **Internal route confinement:** construct a group with internal edges; assert all
  waypoints are within the group's bounds.
- **Title band routing constraint:** assert no waypoint falls within the group title band
  rectangle.
- **Empty group determinism:** assert identical source produces bit-identical empty group
  bounds on two runs; assert bounds are non-zero.
- **Nested local direction:** construct a TB outer group with LR inner group; assert
  inner nodes are laid out left-to-right independently of the outer layout.
- **No post-layout shuffle (regression):** assert that after `recursive_compound_layout`
  returns, no subsequent repositioning function is called on already-placed nodes.
