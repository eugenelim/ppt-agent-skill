# Flowchart ELK Routing Regression Pack

Mode: full (structural change, multi-feature, dependent tasks)

- **Status:** Shipped
- **Depends on:** `elk-finalized-layout-roundtrip` (ELK edge sections must be consumed via the shared `FinalizedLayout` path before AC7 can close)

## Objective

Validate and finish ELK and Python-fallback routing for six flowchart fixtures
(`flowchart-arrows-defs`, `flowchart-diamond-branch`, `flowchart-empty-subgraph`,
`flowchart-groups-complex`, `flowchart-inner-direction`, `flowchart-parallel-links`).
Each fixture exposes a distinct routing defect in the current pipeline. The work
closes those defects without introducing a new global layout engine.

Specifically:
- Feedback edges are routed around the smallest containing strongly connected
  component, not the full canvas boundary.
- Fan-out and fan-in nodes receive ordered face ports; parallel edges get
  separate lanes.
- The obstacle model is extended to include unrelated group interiors, group
  title strips, and already-placed edge-label bounds.
- Local subgraph direction inside a compound group is resolved at layout time,
  not through a post-layout coordinate shuffle.
- Empty subgraphs receive deterministic minimum bounds from their label
  dimensions.
- Cross-group edges gate through hierarchy-aware boundary ports.
- Faithful mode maps only the three Mermaid line styles; it does not infer
  semantic meaning and does not add a legend.
- Every `RoutedEdge` exposes four compactness scalars.

## Boundaries

**Always do:**
- Keep all existing tests green throughout.
- Maintain the pure-Python Sugiyama fallback as the mandatory code path when
  Node / elkjs is absent.
- Return `RoutingFailure` objects for unroutable edges; never silently drop an
  edge.
- Gate ELK-path tests with `@requires_elk` so they skip in environments without
  Node.

**Ask first:**
- Any change to the public `to_html` / `to_svg` / `to_png` signatures beyond
  adding `faithful=False` (already agreed in `flowchart-pipeline-finish`).
- Introducing a new runtime dependency for SCC computation (keep in-file
  Tarjan's rather than pulling in networkx).

**Never do:**
- Use the complete canvas boundary as the default feedback-edge lane.
- Add an inferred legend in faithful mode.
- Infer synchronous / asynchronous / optional / critical-path meaning from
  Mermaid line syntax.
- Touch sequence, Gantt, pie, packet, journey, or XY chart renderers.
- Import networkx, numpy, scipy, shapely, or graphviz in any `layout/*.py` file.

**In scope:**
- `scripts/mermaid_render/layout/_routing.py`
- `scripts/mermaid_render/layout/elk_adapter.py` (ELK section consumption,
  blocked on `elk-finalized-layout-roundtrip`)
- `scripts/mermaid_render/layout/_strategies.py`
- `scripts/mermaid_render/layout/_geometry.py`
- `scripts/mermaid_render/layout/_layout.py`
- `tests/test_regression_fixtures.py`
- `tests/test_routing_units.py` (new or extend)

**Not in scope:**
- erDiagram, classDiagram, architecture-beta renderers.
- A new layout engine or strategy registry.
- Full Gansner network-simplex.

## Acceptance Criteria

### Fixture-level

- [ ] **AC1 — diamond-branch local loop:** `flowchart-diamond-branch` renders the
  Retry → Check back-edge in a local loop; no waypoint of that edge exits the
  bounding box of the Retry and Check nodes by more than `2 × LOOP_LANE_GAP`.

- [ ] **AC2 — inner-direction no canvas-edge route:** `flowchart-inner-direction`
  has no edge waypoint at `x = 0` or within `CANVAS_PAD` of the outer canvas
  boundary unless every alternative path is blocked by an obstacle.

- [ ] **AC3 — groups-complex no unrelated group traversal:** In
  `flowchart-groups-complex`, no edge route passes through the interior rect of
  a group to which neither the edge's source nor its destination belongs.

- [ ] **AC4 — empty-subgraph no overlap:** In `flowchart-empty-subgraph`, no two
  group bounding boxes overlap after layout; each empty group has a minimum
  height greater than its label height plus `GROUP_PAD_Y_TOP`.

- [ ] **AC5 — parallel-links balanced fan-out/fan-in:** In
  `flowchart-parallel-links`, the fan-out source ports are evenly spaced across
  the source node's exit face; the fan-in destination ports are evenly spaced
  across the destination node's entry face; no two parallel edges share a
  waypoint segment.

- [ ] **AC6 — arrows-defs three styles, no legend:** `flowchart-arrows-defs`
  renders exactly three distinct edge styles — solid (`-->`), thick (`==>`),
  dotted (`-.->`) — and produces no `<div class="diagram-legend">` element when
  `faithful=True`.

### Structural and behavioral

- [ ] **AC7 — ELK edge sections via FinalizedLayout:** When ELK is available,
  edge waypoints in the rendered output originate from the ELK edge sections
  deserialized into `RoutedEdge.waypoints` by `_from_elk_result()`; the Python
  A* router is not invoked for those edges. (Requires `elk-finalized-layout-roundtrip`.)

- [ ] **AC8 — SCC-scoped feedback lanes:** The Python fallback routes every
  back-edge around the smallest strongly connected component that contains both
  endpoints. The `right_lane_x` / `bottom_lane_y` canvas-edge sentinel is never
  used as the lane coordinate for a back-edge that has a smaller local SCC bbox.

- [ ] **AC9 — ordered face ports for fan-out/fan-in:** `allocate_face_ports()` is
  called on every `route_edges()` invocation. Source ports for fan-out nodes are
  ordered left-to-right (TB) or top-to-bottom (LR) to match destination rank
  order; destination ports for fan-in nodes are ordered correspondingly.

- [ ] **AC10 — parallel edge lane separation:** Edges sharing the same
  (source, destination) node pair are assigned distinct offset lanes so no two
  parallel edges share a collinear waypoint segment.

- [ ] **AC11 — expanded obstacle model:** `_build_routing_grid()` and
  `_blocked_segs()` treat the following as obstacles in addition to node
  interiors: (a) the interior rect of each group to which neither endpoint
  belongs, (b) the title strip rect (top `GROUP_PAD_Y_TOP` px) of every group,
  and (c) the bounding boxes of already-placed edge labels.

- [ ] **AC12 — local direction in compound layout:** A compound group whose
  Mermaid source declares a direction (e.g. `direction LR`) has that direction
  applied to its child sub-graph during the rank-assignment and coordinate-
  assignment passes; no post-layout `dx / dy` translation reversal is performed
  to fake the direction change.

- [ ] **AC13 — empty subgraph deterministic bounds:** An empty subgraph (zero
  child nodes) is assigned a minimum bounding box at layout time: width =
  `max(label_width + 2 × GROUP_PAD_X, MIN_EMPTY_GROUP_W)`, height =
  `max(GROUP_PAD_Y_TOP + MIN_EMPTY_GROUP_BODY_H, label_height + 2 × GROUP_PAD_Y_TOP)`.
  The minimum dimensions are non-zero constants defined in `_constants.py`.

- [ ] **AC14 — hierarchy-aware boundary gates:** An edge crossing a group boundary
  exits/enters through a boundary port allocated on the group's perimeter rect
  at the LCA level; it does not route directly between inner node ports without
  passing through the group wall.

- [ ] **AC15 — faithful mode line semantics only:** With `faithful=True`,
  `_layout_graph_topology()` maps `-->` → `solid`, `==>` → `thick`,
  `-.->` → `dotted` and no other mapping. No legend element is emitted
  regardless of `inferred_legend` setting when `faithful=True`.

- [ ] **AC16 — compactness metrics on RoutedEdge:** `RoutedEdge` gains four
  read-only fields: `route_length: float` (total Euclidean path length),
  `bend_count: int` (number of 90° direction changes), `canvas_area: int`
  (product of `FinalizedLayout.canvas_bounds.w` × `.h`, stamped at routing
  time), and `max_endpoint_distance: float` (maximum over all waypoint segments
  of the segment's distance to the nearest of its two endpoint node AABBs).
  All four default to `0` / `0.0` for edges without waypoints.

## Testing Strategy

**TDD throughout:** each task writes failing tests first, then implements.

- `tests/test_regression_fixtures.py` — extend with one test class per fixture
  (six new classes); each asserts its fixture-level AC plus AC8–AC14 where
  applicable. Tests are parameterized over Python-fallback and
  `@requires_elk`-guarded ELK variants.
- `tests/test_routing_units.py` — unit tests for: SCC detection via Tarjan's
  (`test_tarjan_scc`), `allocate_face_ports()` ordered output
  (`test_face_ports_fan_out`, `test_face_ports_fan_in`), parallel-lane
  deduplication (`test_parallel_lane_separation`), expanded obstacle model
  (`test_group_interior_blocked`, `test_title_strip_blocked`,
  `test_placed_label_blocked`), boundary gate port allocation
  (`test_boundary_gate_lca`), and compactness metric computation
  (`test_compactness_metrics`).
- `tests/test_elk_adapter.py` — add `test_sections_consumed_via_finalized_layout`
  under `@requires_elk` (AC7).
- `tests/test_faithful_mode.py` — assert no legend element and exact three-style
  mapping for `flowchart-arrows-defs` with `faithful=True` (AC15).
- Goal-based: gallery command exits nonzero if any of the six target fixtures
  produces `geometry="fail"`.
