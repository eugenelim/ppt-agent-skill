# Implementation Plan — Flowchart ELK Routing Regression Pack

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_routing.py`,
   `scripts/mermaid_render/layout/elk_adapter.py`,
   `scripts/mermaid_render/layout/_strategies.py`,
   `scripts/mermaid_render/layout/_geometry.py`,
   `scripts/mermaid_render/layout/_layout.py`,
   `scripts/mermaid_render/layout/_constants.py`,
   `tests/test_regression_fixtures.py`,
   `tests/test_routing_units.py`,
   `tests/test_elk_adapter.py`,
   `tests/test_faithful_mode.py`.
2. Done when: `pytest tests/` passes (all existing tests green); all six
   flowchart fixture geometry tests pass; `pytest tests/test_routing_units.py`
   passes all new unit tests; gallery command exits nonzero for any failing
   fixture.
3. Not changing: sequence, Gantt, pie, packet, journey, XY chart, or C4
   renderers; `_render_graph_fragment()`; public `to_html` / `to_svg` / `to_png`
   signatures; `_to_elk_json()` serialization direction.

**Declined patterns:**
- Pulling in `networkx` for SCC — a 40-line in-file Tarjan's implementation is
  sufficient and keeps the import boundary clean.
- A `LayoutEngine` strategy registry — there are only two paths (ELK, Python);
  the `try elk / except ElkUnavailable → Python` pattern already in
  `_strategies.py` is adequate.
- Post-layout coordinate shuffle for sub-direction — this is the root cause of
  `inner-direction` regressions; the fix is to thread direction into the layout
  passes, not to add another shuffle.
- Canvas-boundary feedback lane — replaced by SCC-local lane; the canvas sentinel
  `right_lane_x` survives only as an absolute fallback when SCC computation
  yields no finite bbox.
- Snapshot-first testing — snapshots drift silently; assertion-based geometry
  tests catch the actual invariants.

---

## Tasks

### Task 1: Fixture baseline regeneration
Depends on: none
Verification: manual + snapshot diff

**Tests:**
- Run `pytest tests/test_regression_fixtures.py -k "arrows_defs or diamond_branch or empty_subgraph or groups_complex or inner_direction or parallel_links"` against current main; record which pass and which fail.
- Capture backend tag (`backend="elkjs"` vs `backend="sugiyama"`) from `FinalizedLayout.metadata` for each fixture when ELK is available.

**Approach:**
- Install elkjs in the test environment (`npm install elkjs` in
  `scripts/mermaid_render/layout/`) and run all six fixtures; log which backend
  actually executed.
- Add or update entries in `tests/test_regression_fixtures.py` with one test
  class per fixture (`TestArrowsDefs`, `TestDiamondBranch`,
  `TestEmptySubgraph`, `TestGroupsComplex`, `TestInnerDirection`,
  `TestParallelLinks`); mark each class with `@pytest.mark.xfail` for the ACs
  that are not yet passing so the suite stays green during implementation.
- Document the baseline failure set in a `# BASELINE` comment block at the top
  of each test class; remove `xfail` marks as tasks close them.

---

### Task 2: ELK edge sections consumed via shared FinalizedLayout path
Depends on: `elk-finalized-layout-roundtrip` spec (external prerequisite); Task 1
Verification: TDD (`@requires_elk`)

**Tests:**
- `tests/test_elk_adapter.py::TestRoundTrip::test_sections_consumed_via_finalized_layout`:
  Build a `LayoutGraph` with two nodes and one edge; synthesize an ELK output
  dict with a two-bend section (`junctionPoints` present); call
  `layout_with_elk()`; assert `RoutedEdge.waypoints` equals the bend sequence
  from the ELK section and the Python A* router is never invoked.
- `tests/test_regression_fixtures.py::TestDiamondBranch::test_elk_waypoints_source`:
  When `@requires_elk`, assert `FinalizedLayout.metadata.backend == "elkjs"` and
  at least one `RoutedEdge` has `len(waypoints) >= 4`.

**Approach:**
- `elk_adapter.py` `_from_elk_result()`: extend section-to-waypoints assembly to
  deduplicate consecutive duplicate points when joining multi-section edges
  (AC10 from `elk-finalized-layout-roundtrip`).
- `_strategies.py` `_compile_flowchart()`: ensure the ELK-path branch does not
  call `route_edges()` after `layout_with_elk()` returns; guard with
  `if metadata.backend == "elkjs": skip_python_routing = True`.
- Stamp `canvas_area` on each `RoutedEdge` at the point where `FinalizedLayout`
  is assembled (needed by Task 10's `max_endpoint_distance`).

---

### Task 3: SCC-scoped feedback lane in Python fallback
Depends on: none
Verification: TDD

**Tests:**
- `tests/test_routing_units.py::TestSCCFeedback::test_tarjan_scc_simple`:
  Three-node cycle returns one SCC of size 3; linear chain returns three SCCs of
  size 1.
- `tests/test_routing_units.py::TestSCCFeedback::test_feedback_lane_local_not_canvas`:
  Build a layout with two nodes Retry (rank 1) and Check (rank 0) sharing an
  SCC; route the Retry → Check back-edge; assert the lane x-coordinate is
  `≤ max(Retry.x + Retry.w, Check.x + Check.w) + 3 × LOOP_LANE_GAP`.
- `tests/test_regression_fixtures.py::TestDiamondBranch::test_retry_check_local_loop`:
  Assert no waypoint of the Retry → Check edge has x-coordinate greater than
  `max(Retry.right, Check.right) + 4 × LOOP_LANE_GAP` (AC1).

**Approach:**
- Add `_tarjan_sccs(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]`
  to `_routing.py` (< 50 lines, iterative Tarjan's using an explicit stack).
- Add `_scc_bbox(scc_members: list[str], nodes: dict) -> Rect` to return the
  bounding box of all nodes in the SCC.
- In the back-edge lane assignment block of `route_edges()` (around line 813):
  compute `_tarjan_sccs` from real edges; for each back-edge, find the smallest
  SCC containing both endpoints; use `scc_bbox.right + lane_stagger` as the
  lane x-coordinate. Fall back to the existing `right_lane_x` sentinel only
  when the SCC contains all nodes (i.e., the global cycle).
- Preserve the existing per-back-edge stagger (`12 * (be_lane + 1)`) within
  the local SCC lane so multiple back-edges in the same SCC do not overlap.

---

### Task 4: Ordered face ports for fan-out/fan-in and parallel edge lane separation
Depends on: none
Verification: TDD

**Tests:**
- `tests/test_routing_units.py::TestFacePorts::test_fan_out_ports_ordered_tb`:
  Fan-out from node S to three destinations A, B, C (in rank order A < B < C
  left-to-right); assert `allocate_face_ports()` assigns port offsets in
  ascending order matching destination x-positions.
- `tests/test_routing_units.py::TestFacePorts::test_fan_in_ports_ordered_tb`:
  Fan-in from A, B, C to node D; assert ports are ordered to match source
  x-positions.
- `tests/test_routing_units.py::TestFacePorts::test_parallel_lanes_distinct`:
  Two edges between nodes P and Q; assert their waypoint sequences share no
  collinear segment.
- `tests/test_regression_fixtures.py::TestParallelLinks::test_balanced_fan_out_fan_in`:
  Assert fan-out source ports are within ±20 px of the barycenter of destination
  x-positions; assert fan-in destination ports are within ±20 px of the
  barycenter of source x-positions (AC5).

**Approach:**
- `_routing.py` `route_edges()`: call `allocate_face_ports()` unconditionally
  before the per-edge routing loop; store `PortAllocation` results in a
  `port_map: dict[str, list[PortAllocation]]` keyed by `f"{node_id}:{face}"`.
  (`allocate_face_ports()` already exists at line 522; it currently returns
  results but they are not threaded through the main routing call.)
- Sort the port assignment by destination rank (TB) or destination y-position
  (LR) so fan-out ports appear in natural reading order.
- For parallel edges: detect `(src_id, dst_id)` duplicates in the edge list;
  assign each duplicate pair an incrementing `lane` offset fed to
  `allocate_face_ports(..., lane_override=i)`.
- Replace the existing hardcoded mid-face port calculation in the forward-edge
  block with a lookup from `port_map`.

---

### Task 5: Expanded obstacle model
Depends on: none
Verification: TDD

**Tests:**
- `tests/test_routing_units.py::TestObstacleModel::test_group_interior_blocked`:
  Build a grid with one group [0,0,200,200] and two nodes outside it; add the
  group interior as an obstacle; assert `_blocked_segs()` marks all segments
  passing through [20,20,180,180] as blocked.
- `tests/test_routing_units.py::TestObstacleModel::test_title_strip_blocked`:
  A group title strip [0,0,200,GROUP_PAD_Y_TOP] is an obstacle; assert routes
  do not enter it.
- `tests/test_routing_units.py::TestObstacleModel::test_placed_label_blocked`:
  An already-placed label rect [50,50,100,20] is added to the obstacle list;
  assert `_blocked_segs()` marks the interior as blocked.
- `tests/test_regression_fixtures.py::TestGroupsComplex::test_no_unrelated_group_traversal`:
  For every edge in `groups-complex`, assert no waypoint lands inside a group
  rect to which neither endpoint belongs (AC3).

**Approach:**
- `_routing.py` `route_edges()`: build `unrelated_group_obstacles` list by
  filtering `groups` to those where neither `real_src` nor `real_dst` is a
  member; add those group interior rects (deflated by `CLEAR`) to the
  `obstacles` list passed to `_build_routing_grid()` and `_blocked_segs()`.
- Add `title_strip_obstacles`: for every group, add a rect
  `(group.x, group.y, group.x + group.w, group.y + GROUP_PAD_Y_TOP)` to
  obstacles unconditionally (even the group's own title strip is an obstacle
  for edges entering/exiting that group through the body).
- Add `placed_label_obstacles`: after each edge label is placed, append its
  `LabelPlacement.box` to a running `placed` list and pass it to subsequent
  `_best_label_pos()` calls (already partially implemented; wire it to
  `_blocked_segs()` as well so routing of later edges avoids placed labels).

---

### Task 6: Local subgraph direction in compound layout
Depends on: none
Verification: TDD

**Tests:**
- `tests/test_routing_units.py::TestCompoundDirection::test_direction_lr_in_group`:
  A group with `direction=LR` containing two nodes A, B with one edge A→B;
  compile the sub-graph; assert `A.x < B.x` (horizontal flow) and
  `abs(A.y - B.y) < NODE_H` (no vertical offset between them).
- `tests/test_routing_units.py::TestCompoundDirection::test_no_post_layout_shuffle`:
  After `_compile_flowchart()`, assert there is no coordinate translation step
  in the call trace by verifying `LayoutGraph.nodes` positions equal
  `FinalizedLayout.node_layouts` positions (no hidden `dx/dy` offset applied).
- `tests/test_regression_fixtures.py::TestInnerDirection::test_no_canvas_edge_route`:
  Assert no waypoint has `x <= CANVAS_PAD` or `x >= canvas_w - CANVAS_PAD`
  unless every A* alternative is blocked (AC2).

**Approach:**
- `_strategies.py` `_compile_flowchart()`: when assembling a sub-`LayoutGraph`
  for a compound group, pass the group's declared `direction` into
  `_assign_ranks()` and `_assign_coordinates()` directly rather than defaulting
  to the top-level direction and applying a post-hoc axis swap.
- `_layout.py`: add `direction` parameter to `_assign_ranks()` and
  `_assign_coordinates()` (currently always TB); when `direction == "LR"`, swap
  the axes used for rank and coordinate assignment so that the layer dimension
  is x and the intra-layer dimension is y.
- Remove the existing `_flip_lr()` / coordinate-translate block in
  `_strategies.py` that compensates for the missing per-group direction
  (introduced as part of `flowchart-pipeline-finish`); replace with the
  direction-threaded approach.

---

### Task 7: Empty subgraph deterministic minimum bounds
Depends on: none
Verification: TDD

**Tests:**
- `tests/test_routing_units.py::TestEmptySubgraph::test_minimum_bounds_labeled`:
  A group with label "Section" and zero children; call the bounds function;
  assert `w >= label_width + 2 × GROUP_PAD_X` and
  `h >= GROUP_PAD_Y_TOP + MIN_EMPTY_GROUP_BODY_H`.
- `tests/test_routing_units.py::TestEmptySubgraph::test_minimum_bounds_unlabeled`:
  A group with an empty label and zero children; assert `w >= MIN_EMPTY_GROUP_W`
  and `h > 0`.
- `tests/test_regression_fixtures.py::TestEmptySubgraph::test_no_group_overlap`:
  For every pair of groups in the rendered `empty-subgraph` layout, assert their
  bounding rects do not intersect (AC4).

**Approach:**
- `_constants.py`: add `MIN_EMPTY_GROUP_W = 120`, `MIN_EMPTY_GROUP_BODY_H = 40`.
- `_strategies.py` `_compile_flowchart()`: after group child-node placement,
  for any `LayoutGroup` with zero children compute its bounds as
  `w = max(_measure_text_width(group.label) + 2 * GROUP_PAD_X, MIN_EMPTY_GROUP_W)`,
  `h = max(GROUP_PAD_Y_TOP + MIN_EMPTY_GROUP_BODY_H, label_h + 2 * GROUP_PAD_Y_TOP)`;
  assign these as the group's `width` / `height` before the global canvas union.
- Ensure these synthetic groups are placed by the Sugiyama layer-assignment as
  if they were nodes with those dimensions (treat empty groups as atomic nodes
  at the rank of their label's lexicographic minimum child — or rank 0 when no
  children and no rank hint).

---

### Task 8: Hierarchy-aware boundary gates for cross-group edges
Depends on: Task 5 (obstacle model expansion needed for group-interior blocking)
Verification: TDD

**Tests:**
- `tests/test_routing_units.py::TestBoundaryGates::test_lca_boundary_port`:
  Two nodes A (in group G1) and B (in group G2); route edge A→B; assert the
  waypoints include a point on the perimeter of G1 (exit gate) and a point on
  the perimeter of G2 (entry gate) before reaching B.
- `tests/test_routing_units.py::TestBoundaryGates::test_no_shortcut_through_wall`:
  Route A→B as above; assert no waypoint interior to G1 lies outside G1's
  bounding rect (edge does not exit through a wall shortcut).
- `tests/test_regression_fixtures.py::TestGroupsComplex::test_routes_use_boundary_gates`:
  For every cross-group edge in `groups-complex`, assert the first waypoint
  after the source is on or outside the source group's boundary rect (AC3
  structural verification).

**Approach:**
- `_routing.py`: add `_lca_group(src_id, dst_id, group_membership) -> str | None`
  returning the ID of the lowest common ancestor group.
- Add `_group_boundary_port(group: LayoutGroup, direction: str, exit: bool) -> tuple[int, int]`
  returning the face-center point on the group perimeter in the layout direction
  (exit=True for source side, exit=False for destination side).
- In `route_edges()`, for each edge where `src_group != dst_group`, prepend the
  LCA exit gate point to the A* source and append the LCA entry gate point to
  the A* destination before calling `_astar_route()`. Store gate points as the
  first and last interior waypoints so they appear in `RoutedEdge.waypoints`.

---

### Task 9: Faithful mode line semantics and legend suppression
Depends on: none
Verification: TDD

**Tests:**
- `tests/test_faithful_mode.py::TestFaithfulLineStyles::test_three_styles_only`:
  Parse `flowchart-arrows-defs` with `faithful=True`; assert the `RoutedEdge`
  list contains exactly one `edge_style="solid"`, one `edge_style="thick"`, and
  one `edge_style="dotted"` (and no other values).
- `tests/test_faithful_mode.py::TestFaithfulLineStyles::test_no_legend_faithful`:
  Call `_layout_graph_topology(src, ..., opts=RenderOptions(faithful_mermaid=True))`;
  assert the returned HTML fragment does not contain `class="diagram-legend"` (AC6).
- `tests/test_faithful_mode.py::TestFaithfulLineStyles::test_no_semantic_inference`:
  Assert that passing `faithful=True` with a `-->` edge does not produce a
  `RoutedEdge.edge_style` of `"async"`, `"optional"`, or any value other than
  `"solid"`.

**Approach:**
- `_strategies.py` `_layout_graph_topology()`: the `_show_legend` guard already
  checks `not _opts.faithful_mermaid`; verify this is the only legend-emission
  site and add an assertion comment.
- `_strategies.py` `_compile_flowchart()` (or the edge-parse block): when
  `opts.faithful_mermaid=True`, map line tokens exactly:
  `"-->" → "solid"`, `"==>" → "thick"`, `"-.->",  "--.->" → "dotted"`.
  Discard any semantic enrichment (color hints, role labels) that the non-faithful
  path may add.
- Add `faithful_mermaid: bool = False` to `RenderOptions` if not already present;
  thread it through `_compile_flowchart()` → edge parsing.

---

### Task 10: Compactness metrics on RoutedEdge
Depends on: Tasks 3, 4, 5, 6, 7, 8 (routing must be stable before metrics are meaningful)
Verification: TDD

**Tests:**
- `tests/test_routing_units.py::TestCompactnessMetrics::test_route_length_l_shape`:
  An L-shaped route with two segments of lengths 100 and 50; assert
  `RoutedEdge.route_length == 150.0`.
- `tests/test_routing_units.py::TestCompactnessMetrics::test_bend_count`:
  The same L-shape has `bend_count == 1`; a straight line has `bend_count == 0`;
  a Z-shape has `bend_count == 2`.
- `tests/test_routing_units.py::TestCompactnessMetrics::test_canvas_area_stamped`:
  After routing, `RoutedEdge.canvas_area == canvas_bounds.w * canvas_bounds.h`.
- `tests/test_routing_units.py::TestCompactnessMetrics::test_max_endpoint_distance_zero_for_direct`:
  An edge whose waypoints go directly from node-A exit to node-B entry has
  `max_endpoint_distance == 0.0` (all segments adjacent to one endpoint).

**Approach:**
- `_geometry.py` `RoutedEdge`: add four fields with defaults:
  `route_length: float = 0.0`, `bend_count: int = 0`,
  `canvas_area: int = 0`, `max_endpoint_distance: float = 0.0`.
  Keep `RoutedEdge` a frozen dataclass; compute metrics at construction time via
  a `_compute_metrics(waypoints, src_bbox, dst_bbox, canvas_area)` module-level
  helper.
- `_routing.py` `route_edges()`: after constructing each `RoutedEdge`, call
  `_compute_metrics()` and pass results into the dataclass constructor.
- `_compute_metrics()` implementation:
  - `route_length`: sum of Euclidean distances between consecutive waypoints.
  - `bend_count`: count index `i` where direction vector changes between
    `(pts[i] - pts[i-1])` and `(pts[i+1] - pts[i])`.
  - `canvas_area`: passed in from `FinalizedLayout.canvas_bounds` at call site.
  - `max_endpoint_distance`: for each segment midpoint, compute distance to
    `src_bbox` and `dst_bbox`; take the max; subtract the node half-diagonal to
    give zero for segments that start/end at the node face.
