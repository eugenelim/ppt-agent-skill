Mode: full (structural change — new compound layout pipeline; touches _pipeline.py core layout path)

# backlog-mermaid-p3-compound-layout

**Status:** Shipped

## Objective

Extend the compound layout pipeline to correctly route edges that cross group boundaries
in flowchart / statediagram subgraphs. Currently, `_recursive_group_layout` repositions
group members in their declared direction but leaves cross-scope edges (edges that enter or
exit a group's boundary) unmodified. This causes edge waypoints to clip through group
boundary boxes instead of routing cleanly through boundary gates.

The four required additions are:

1. **Group tree** — extract the parent→children traversal structure from `_recursive_group_layout`
   into a reusable `_build_group_tree` helper so later passes can share it.
2. **Edge partitioning** — classify each edge as intra-group (both endpoints in the deepest
   shared group), cross-boundary (endpoints in different scopes), or free (neither in any group).
3. **Innermost-first compile** — inject proxy gate nodes (`is_dummy=False`,
   `extra_css="opacity:0;pointer-events:none;"`) for cross-boundary edges before layout runs;
   restore the original edges from merged route-dicts after routing completes.
4. **Proxy-node expansion** — each gate proxy causes the layout engine (ELK or Python Sugiyama)
   to route through it; after routing the two split route-dicts are concatenated into one route-dict
   for the original edge.

## Background

### Current state

`_recursive_group_layout` (lines 507–711 in `_pipeline.py`) runs DFS post-order to
adjust member positions when a group's `direction` differs from the outer layout direction.
It moves node coordinates but does NOT:

- Partition edges by scope.
- Create or update waypoints for edges that cross group boundaries.
- Inject proxy nodes for general flowchart subgraphs.

Result: cross-scope flowchart edges often clip through group boxes when groups are
repositioned by `_recursive_group_layout`.

### Existing related mechanism

`_Edge.src_group` (set by `statediagram.py`) + `_clip_cross_scope_exit_waypoints`
(`_pipeline.py:287`) already clip routes that exit a state-diagram composite state.
The new mechanism is complementary and handles the entry side for flowchart subgraphs
by injecting proxy gate nodes that participate in layout.

### Reference implementation

`statediagram.py` injects `{scope}_sm_start_` and `{scope}_sm_end_` proxy nodes at
`state_model_to_graph()` time, wiring cross-composite transitions through these anchors
before ELK or Sugiyama runs. Those nodes are real (rendered), not hidden. The new
mechanism uses `is_dummy=False` with `extra_css="opacity:0;pointer-events:none;"` so gate
nodes are invisible to users but fully participate in layout and routing (unlike `is_dummy=True`
nodes, which are skipped by both the router and the ELK node builder).

## Acceptance Criteria

- [x] AC-1 **Group tree**: `_build_group_tree(groups)` returns a `(dict[str, list[str]], list[str])`
  tuple: the parent→children map (where a root group maps to `[]`) and the post-order traversal
  list. The existing inline parent→children logic inside `_recursive_group_layout` is replaced
  by a call to `_build_group_tree`.
  Tested: the traversal of a two-level nested subgraph visits the inner group before the outer
  group.

- [x] AC-2 **Edge partitioning**: `_partition_edges(edges, nodes, groups)` returns three lists
  classified in this precedence order:
  - `free`: neither src nor dst is in any group.
  - `intra`: both endpoints share the same deepest group (checked after `free`).
  - `cross`: at least one endpoint is grouped and the endpoints do not share the same deepest
    group.
  Membership is defined as the **deepest** group containing the node (resolves nesting
  ambiguity). The three buckets are mutually exclusive.
  Tested: a 5-node graph with one two-node subgraph correctly classifies all edges into the
  three categories.

- [x] AC-3 **Proxy-node expansion**: `_expand_boundary_gates(nodes, edges, groups)` adds one
  synthetic gate `_Node` per cross-boundary edge: `id=f"_gate_{edge_id}"`, `is_dummy=False`,
  `extra_css="opacity:0;pointer-events:none;"`, `shape="rect"`, `x=0`, `y=0`, `width=0`,
  `height=0`. Gate injection is guarded by `_has_inner_dir_pre` (only runs when at least one
  group has a direction differing from the outer layout) and skips edges whose src/dst IDs start
  with `_sm_` (state-diagram proxy endpoints). For each qualifying edge the original is replaced
  by two edges: `src→gate` and `gate→dst`. The original edge is preserved in a returned mapping
  `{gate_id: original_edge}` for AC-4 restoration.
  Tested: after expansion, no direct cross-boundary edge remains in the edge list; all
  cross-boundary paths go through a gate node.

- [x] AC-4 **Route restoration**: `_restore_gate_edges(route_dicts, gate_to_original, nodes)`
  merges split route-dicts after routing. For each original cross-boundary edge `src→dst` that
  was split via gate `g`:
  1. Find route-dicts for `src→g` and `g→dst`.
  2. Concatenate their `"waypoints"` lists: `[...(src→g waypoints), ...(g→dst waypoints)]`.
  3. Create a new route-dict for `src→dst` using the concatenated waypoints; inherit `label`,
     `style`, `target_marker`, `src`, `dst`, `edge_id` from the original `_Edge`.
  4. Remove the `src→g`, `g→dst` route-dicts and the gate node from `nodes`. Emits
     `warnings.warn` if only one half is found (orphan detection).
  Returns the updated route-dicts list.
  Tested: in a two-level nested subgraph, the merged route for a cross-boundary edge has
  more waypoints than either half alone; `test_cross_scope_fixture_all_edges_rendered` asserts
  all 4 edges present in `routed_edges`.

- [x] AC-5 **No regression**: all flowchart and state-diagram tests that pass on the current
  `main` branch continue to pass. Specifically: every test in `tests/test_unified_pipeline.py`,
  `tests/test_fix_sequence.py`, and `tests/test_fix_state.py` that currently passes must still
  pass. The two tests that are already failing on `main` before this spec —
  `test_graph_fixture_no_overlap[flowchart-diamond-branch]` and
  `test_graph_fixture_no_overlap[flowchart-groups-complex]` (edge-label-vs-node-overlap, unrelated
  to cross-scope routing) — are excluded from this gate. Gate: compare the FAILED set before and
  after; the set must not grow.

- [x] AC-6 **New fixture**: `tests/fixtures/flowchart-cross-scope-edge.mmd` is created with:
  - An outer LR flowchart
  - A TB subgraph containing at least two nodes
  - At least one edge entering the subgraph from outside
  - At least one edge exiting the subgraph to outside
  - Edge labels (if any) must be short and placed to avoid label-node overlap so the
    `geometry == "pass"` assertion is attributable to routing, not label geometry.
  The fixture is added to `_GRAPH_FIXTURES` in `tests/test_unified_pipeline.py` so
  `test_graph_fixture_no_overlap[flowchart-cross-scope-edge]` runs and asserts `== "pass"`.

## Assumptions

- **Parser unchanged**: `_parse_graph_source` already populates `_Group.parent_group`
  and `_Node.group`. Gate-node injection happens after parsing.
- **Gate nodes hidden via opacity**: gate nodes use `is_dummy=False` with
  `extra_css="opacity:0;pointer-events:none;"`. They render as invisible divs, but participate
  fully in ELK layout and Python A* routing. `is_dummy=True` was considered but rejected
  because both the router (`_routing.py`: `if d_node.is_dummy: continue`) and the ELK node
  builder (`_pipeline.py`: `if n.is_dummy: continue`) skip `is_dummy` nodes, causing split
  edges to be silently dropped. Canvas size calculations explicitly exclude gate nodes by ID.
- **Flowchart-only gate injection**: `_expand_boundary_gates` applies only when
  `_has_inner_dir_pre` is true (at least one group has a direction differing from outer layout).
  Within that, edges whose src or dst IDs start with `_sm_` are skipped (state-diagram proxy
  endpoints, already handled by `statediagram.py`).
- **Waypoint restoration at route-dict level**: route dicts are plain Python dicts with a
  `"waypoints"` key (built by `_route_edges`/ELK output, before `RoutedEdge` frozen objects
  are created). Restoration operates on these mutable dicts; no `_Edge.waypoints` field is
  needed and `_constants.py` is untouched. Inherited fields: `label`, `style`, `target_marker`,
  `src`, `dst`, `edge_id` — NOT `reversed_` (reversal is baked into waypoint order before
  route-dicts exist and the key is not read downstream).
- **Gate initial position**: gates are injected at `(x=0, y=0, width=0, height=0)`. Their
  final positions come from the layout engine; the initial position is irrelevant.
- **Scope of change**: only `_pipeline.py`. `_parser.py`, `_constants.py`, `_geometry.py`,
  and all diagram-type modules are untouched.
- **ELK path**: gate nodes participate as regular nodes; ELK assigns their positions. The
  `src→gate` and `gate→dst` edges are routed by ELK. Gate restoration happens after the
  ELK route-dict pass.
- **Python path**: gate nodes participate as regular nodes through `_assign_coordinates`;
  `_route_edges` routes `src→gate` and `gate→dst`. Gate restoration happens after the
  Python route-dict pass.

## Testing Strategy

- Unit tests in `tests/test_compound_layout.py`:
  - `test_build_group_tree_post_order` — AC-1
  - `test_partition_edges_three_categories` — AC-2
  - `test_expand_boundary_gates_no_direct_cross_edges` — AC-3
  - `test_restore_gate_edges_waypoints_merged` — AC-4
  - `test_cross_scope_fixture_all_edges_rendered` — AC-4/AC-6 end-to-end
- Fixture test: `test_graph_fixture_no_overlap[flowchart-cross-scope-edge]` (add entry to
  `_GRAPH_FIXTURES` in `tests/test_unified_pipeline.py`) — AC-6
- Regression sweep: `pytest tests/test_unified_pipeline.py tests/test_fix_state.py tests/test_fix_sequence.py -q`
  — AC-5

## Deferred

- Mixed-direction nested groups beyond depth-2 (handled by post-order but not tested
  beyond depth-2 in this spec).
- Cycle detection in group tree (cyclic group membership is already a parse error).
- Animated layout transitions.
- `_clip_cross_scope_exit_waypoints` integration: the existing state-diagram mechanism
  for source-side clipping is not combined with gate nodes in this spec; deferred.
- Gate injection for same-direction cross-scope edges: the `_has_inner_dir_pre` guard means
  edges crossing group boundaries where both groups share the outer direction do not get gate
  nodes. Deferred.
