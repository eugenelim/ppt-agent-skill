# Implementation Plan — Mermaid Recursive Compound Layout

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_strategies.py` (bottom-up compound algorithm, proxy expansion, delete post-layout correction passes); `scripts/mermaid_render/layout/_geometry.py` (add `CompoundNode`, `BoundaryGate` dataclasses); `scripts/mermaid_render/layout/elk_adapter.py` (pass compound hierarchy to ELK); `tests/test_compound_layout.py` (new compound layout tests).
2. Done when: `pytest tests/` passes including `@requires_elk` tests; the geometry verifier reports no containment violations or title-band crossings on any in-scope compound fixture; no post-layout coordinate shuffle is called in the primary path.
3. Not changing: painter code; sequence diagram layout; shape boundary mathematics. (`FinalizedLayout` gains a `boundary_gates` field in Task 5 — that is in scope.)

**Declined patterns:**
- Tempted to use a mutable `_Group` object for the compound tree; declining — the spec requires frozen `CompoundNode` to guarantee no post-build mutation.
- Tempted to skip the Python fallback path and rely on ELK only; declining — the spec requires the same bottom-up algorithm in the Python fallback.
- Tempted to represent boundary gates as synthetic nodes in the `LayoutGraph`; declining — `BoundaryGate` objects are metadata on the `FinalizedLayout`, not graph nodes; they must not appear as rendered elements.

---

## Tasks

### Task 1: `CompoundNode` and `BoundaryGate` dataclasses
Depends on: none
Verification: TDD

**Tests:**
- `test_compound_node_frozen`: assert modifying a `CompoundNode` field raises `FrozenInstanceError`.
- `test_boundary_gate_fields`: construct a `BoundaryGate`; assert all six required fields are accessible.
- `test_boundary_gate_kind_entry_exit`: assert `BoundaryGateKind.ENTRY` and `BoundaryGateKind.EXIT` are distinct.

**Approach:**
- Add `CompoundNode(group_id, label_layout, local_direction, child_node_ids, child_groups, padding, minimum_size)` frozen dataclass to `_geometry.py`.
- Add `BoundaryGateKind(Enum)` with `ENTRY` and `EXIT`.
- Add `BoundaryGate(gate_id, group_id, side, point, semantic_node_id, edge_id, kind)` frozen dataclass.

---

### Task 2: Compound tree builder
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_tree_covers_all_groups`: build a tree from a graph with three nested groups; assert all three appear in the tree.
- `test_tree_parent_child_relations`: build from a two-level hierarchy; assert the inner `CompoundNode` appears in the outer's `child_groups`.
- `test_tree_leaf_nodes_in_child_node_ids`: build from a group with direct leaf nodes; assert all leaf node IDs appear in `child_node_ids`.

**Approach:**
- Add `build_compound_tree(layout_graph: LayoutGraph) -> list[CompoundNode]` returning root-level compounds.
- Recursively build `CompoundNode` for each group, setting `child_node_ids` and `child_groups` from the graph structure.
- Set `local_direction` from the group's `direction` attribute.
- Set `minimum_size` from measured title width + padding.

---

### Task 3: Edge partitioner
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_intra_group_edges`: an edge where both endpoints are in the same group → classified as intra-group.
- `test_cross_boundary_child_to_parent`: an edge from a child node to its parent group's interior → classified as child-to-parent.
- `test_sibling_to_sibling`: an edge between two nodes in different sibling groups → classified as sibling-to-sibling.
- `test_multi_level_cross_hierarchy`: an edge spanning three group levels → classified as multi-level cross-hierarchy.

**Approach:**
- Add `partition_edges(layout_graph: LayoutGraph, compound_tree) -> EdgePartition` where `EdgePartition` holds five lists (one per scope class).
- For each edge, walk `parent_by_id` of source and target; determine their least-common ancestor group; classify by depth difference.

---

### Task 4: Bottom-up layout algorithm
Depends on: Tasks 2, 3
Verification: TDD

**Tests:**
- `test_bottom_up_processes_innermost_first`: spy on the layout calls; assert the innermost group's layout completes before the outer group's layout starts.
- `test_proxy_exposed_to_parent`: after laying out an inner group, assert a proxy `LayoutNode` representing it appears in the outer graph.
- `test_proxy_bounds_match_compound_bounds`: assert the proxy node's `width` and `height` equal the inner group's measured compound bounds.
- `test_nested_local_direction_independent`: construct a compound with inner LR and outer TB; compile; assert inner group uses LR axis; assert outer group uses TB axis (AC2).
- `test_child_nodes_contained_in_parent`: compile a two-level compound flowchart; for each group, assert all child node bounds lie within the parent group's finalized bounds inclusive of padding; test with `@requires_elk` (AC3).
- `test_sibling_groups_non_overlapping`: compile a compound with two sibling groups each containing nodes; assert the two groups' bounding boxes do not intersect (AC4).

**Approach:**
- Add `recursive_compound_layout(compound_tree, edge_partition, opts) -> FinalizedLayout`.
- Process groups in post-order (innermost first).
- For each group: construct a sub-`LayoutGraph` from its child nodes and intra-group edges; lay out with ELK or Python fallback; finalize internal routes; compute measured bounds (title band + content + padding); create a proxy `LayoutNode` for the parent graph.
- After all groups are proxied, lay out the root graph with proxies in place.
- Expand each proxy by translating finalized internal geometry into parent coordinates.

---

### Task 5: BoundaryGate creation for cross-boundary edges
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_boundary_gate_per_cross_boundary_edge`: compile a compound flowchart with one cross-boundary edge; assert one `BoundaryGate(kind=ENTRY)` and one `BoundaryGate(kind=EXIT)` exist.
- `test_gate_ids_unique_across_diagram`: compile a diagram with three cross-boundary edges; assert all `gate_id` values are distinct.
- `test_gate_point_on_compound_boundary`: assert each gate's `point` lies on the compound group's boundary rectangle within 1-pixel tolerance.
- `test_internal_routes_confined_to_compound`: compile a compound with intra-group edges; for each edge route, assert all waypoints lie within the enclosing group's finalized bounds (AC6).
- `test_title_band_not_crossed_by_routes`: compile a compound with intra-group edges; assert no waypoint's Y coordinate falls within the title-band region `[group.bounds.y, group.bounds.y + TITLE_BAND_HEIGHT]` (AC7).
- `test_html_svg_compound_containment_tree_identical`: compile a compound diagram; assert HTML painter and SVG painter receive a `FinalizedLayout` with identical group nesting counts and gate counts (AC9).

**Approach:**
- In the proxy expansion step, for each edge in `cross_boundary_edges`:
  - Compute the intersection of the edge's external route with the compound's boundary.
  - Create a `BoundaryGate(kind=EXIT)` at the source compound's boundary and `BoundaryGate(kind=ENTRY)` at the target compound's boundary.
  - Store gates in the `FinalizedLayout.boundary_gates` collection (add this field if absent).

---

### Task 6: Empty group handling
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_empty_group_non_zero_bounds`: compile `flowchart-empty-subgraph`; assert every empty group's `GroupLayout.bounds` has positive width and height.
- `test_empty_group_deterministic`: compile the same source twice; assert empty group bounds are byte-identical.

**Approach:**
- In `recursive_compound_layout`, detect groups with zero child nodes and zero child groups.
- For empty groups: set bounds to `Size(width=max(measured_title_width, MIN_GROUP_WIDTH), height=TITLE_BAND_HEIGHT + EMPTY_CONTENT_HEIGHT)`.
- Derive `MIN_GROUP_WIDTH`, `TITLE_BAND_HEIGHT`, `EMPTY_CONTENT_HEIGHT` from the layout config constants.

---

### Task 7: Delete post-layout correction passes
Depends on: Tasks 4, 5, 6
Verification: Goal-based check

**Done when:** `grep -n "group_separation\|member_pushing\|bbox_recomputation" scripts/mermaid_render/layout/_strategies.py` returns zero matches from the primary layout path.

**Approach:**
- After the compound layout algorithm is proven by tests (Tasks 4–6), delete or bypass the primary-path calls to `_group_separation`, `_push_members`, and `_recompute_bboxes`.
- Keep temporary compatibility wrappers only if tests still reference them; add a deprecation comment and delete after test migration.
- Verify `pytest tests/` passes with the correction passes removed.
