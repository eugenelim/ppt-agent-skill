# Implementation Plan — Flowchart Compound Layout and Boundary Gates

**Status:** Done

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_strategies.py` or the split modules
   (compound layout, fallback); `scripts/mermaid_render/layout/_geometry.py` (`BoundaryGate`
   record); `tests/test_flowchart_compound_layout.py` (new/extended).
2. Done when: all four compound flowchart fixtures pass the canonical runner in both the
   ELK-required and Python-fallback lanes; `BoundaryGate` records exist for every
   cross-scope edge; `flowchart-empty-subgraph` empty-group test fails rather than skips
   when the empty group is absent.
3. Not changing: non-flowchart diagram types; ELK Layered as primary engine; the public
   renderer API.

**Declined patterns:**
- Tempted to add per-fixture coordinate patches for cross-scope routes; declining — spec
  explicitly forbids fixture-specific coordinate or route patches.
- Tempted to keep the unconditional inner-direction fallback as a fallback-of-last-resort;
  declining — spec requires only typed conditions (ElkUnavailable, ElkInvalidResult,
  documented unsupported hierarchy) may select the fallback.
- Tempted to use the prior global placement coordinates as the starting position for local
  group layout in the Python fallback; declining — spec explicitly requires bottom-up
  layout that ignores prior global coordinates.

---

## Tasks

### Task 1: ELK-first routing / engine selection
Depends on: none
Verification: TDD

**As shipped (see spec § Deviations):** non-compound grouped flowcharts attempt
ELK first and consume a successful result directly; inner-direction compound
fixtures stay on the gate-emitting Python compound path, because `BoundaryGate`
records (AC7) and the harness's non-forced `min_gates` contract are currently
Python-path-only. The ELK-first-for-compound + post-ELK gate-derivation path is
deferred (backlog `flowchart-compound-elk-gate-derivation`) pending an
`elkjs`-enabled environment to verify it.

**Tests (`tests/test_flowchart_compound_layout.py`):**
- `test_non_compound_attempts_elk_first`: render `flowchart-groups-complex`; mock
  to verify the ELK entry point is attempted; assert that reaching the Python path
  happens only via the typed `elk-unavailable` reason (not a silent bypass).
- `test_inner_direction_uses_gate_emitting_python_path`: assert the compound
  fixture uses the Python compound path (`backend == "python"`,
  `fallback_reason == "inner-direction"`) and emits boundary gates.
- `test_non_compound_fallback_only_on_typed_condition`: mock ELK to raise
  `ElkUnavailable`; assert `backend == "python"` and a typed `fallback_reason`.

**Approach (as shipped):**
- Keep the `has_inner_dir` → Python compound branch in `_compile_flowchart`; it is
  the branch that emits `BoundaryGate` records.
- Non-compound flowcharts build the `LayoutGraph`, attempt ELK, and consume a
  successful `FinalizedLayout` directly; only `ElkUnavailable` / `ElkInvalidResult`
  select the Python fallback.

---

### Task 2: True Python compound fallback (bottom-up)
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_bottom_up_group_order`: in the fallback path, assert groups are processed
  leaf-first (children before parents) by instrumenting the group-processing loop.
- `test_measured_proxy_size`: after processing a leaf group, assert its proxy size is
  derived from measured title + content (not from prior global placement).
- `test_parent_uses_proxy_sizes`: assert the parent graph packs groups using their
  post-measurement sizes, not zero-size placeholders.

**Approach:**
- Replace the fallback sequence in the Python compound router:
  1. Build the group tree (detect parent/child from subgraph containment).
  2. Partition edges by scope.
  3. Process groups bottom-up (topological sort, leaves first).
  4. For each group: measure title, lay out direct nodes and child-group proxies using
     `local_direction`, reserve title-band and padding, route internal edges, compute
     finalized group size, expose as a measured proxy.
  5. Layout the top-level graph from measured proxies.
  6. Expand child proxies by translating already-finalized internal geometry.
- Remove the old sequence (global layout → move members → separate groups → recompute
  boxes).

---

### Task 3: First-class empty groups
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_empty_group_has_nonzero_bounds`: render `flowchart-empty-subgraph`; assert Empty
  Group has `w > 0` and `h > 0`.
- `test_empty_group_not_at_origin`: Empty Group position is not `(0, 0)`.
- `test_empty_group_no_overlap`: Empty Group bounds do not intersect Group With Node bounds.
- `test_test_fails_not_skips`: in the fixture test, assert the test body raises an error
  rather than being skipped when the empty group is absent.

**Approach:**
- In the bottom-up fallback (Task 2), give empty groups a minimum content size from
  constants (`MIN_EMPTY_GROUP_W`, `MIN_EMPTY_GROUP_H`).
- Compute the group size from: measured title width, measured title height, title padding,
  content padding, minimum content width/height.
- Include empty groups in the parent packing pass; they are proxies of their computed size.

---

### Task 4: Boundary gates as route waypoints
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_boundary_gate_exists_for_cross_scope_edge`: render `flowchart-cross-scope-edge`;
  assert each of B→C and D→E has a `BoundaryGate` record.
- `test_gate_is_route_waypoint`: assert the gate point appears as an exact waypoint (or
  within tolerance) in the routed edge.
- `test_single_boundary_crossing`: assert the B→C route enters Inner TB exactly once
  (no re-entry after exit).
- `test_gate_not_in_title_band`: assert the gate's y coordinate is below the group title
  band bottom edge (for TB groups) or appropriate for other directions.

**Approach:**
- Add `BoundaryGate(gate_id, group_id, side, point, edge_id, role)` to `_geometry.py`
  (`role` is `"entry"` or `"exit"`).
- In the router, for every edge whose source and destination belong to different scopes:
  1. Determine entry/exit sides deterministically from positions, `local_direction`, route
     length, and title-band avoidance.
  2. Create `BoundaryGate` records.
  3. Insert the gate point into the route as a waypoint.
  4. Route the internal portion inside the group; route the external portion avoiding
     unrelated groups.
  5. Merge the routes, preserving the gate waypoint and gate metadata.

---

### Task 5: Group-aware routing obstacles
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_route_avoids_unrelated_group_interior`: in `flowchart-groups-complex`, assert
  no edge segment crosses an unrelated group interior.
- `test_route_avoids_group_title_band`: assert no segment crosses any group title band.
- `test_worker_queue_local_route`: assert Worker→Queue uses a local cross-group route
  (route length is shorter than the canvas perimeter).

**Approach:**
- Collect routing obstacles: unrelated node interiors, unrelated group interiors, group
  title bands, allocated label rectangles, already-allocated compound gates,
  marker-clearance zones.
- Route segments around obstacles using local channels (not defaulting to the canvas edge).
- Store obstacle rectangles alongside the finalized layout for validation.
