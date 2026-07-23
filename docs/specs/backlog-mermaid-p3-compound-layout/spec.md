Mode: full (structural change — new compound layout pipeline; touches _pipeline.py core layout path)

# backlog-mermaid-p3-compound-layout

**Status:** Draft

## Objective

Extend the compound layout pipeline to correctly route edges that cross group boundaries
in flowchart / statediagram subgraphs. Currently, `_recursive_group_layout` repositions
group members in their declared direction but leaves cross-scope edges (edges that enter or
exit a group's boundary) unmodified. This causes edge waypoints to clip through group
boundary boxes instead of routing cleanly through boundary gates.

The four required additions are:

1. **Group tree** — a post-order traversal structure over `_Group` objects so later passes
   can process from innermost group outward.
2. **Edge partitioning** — classify each edge as intra-group (both endpoints in the same
   group), cross-boundary (one endpoint in a group, the other outside), or free (neither
   endpoint is in any group).
3. **Innermost-first compile** — re-run layout for each group scope innermost-first,
   treating each group as a sub-graph with virtual boundary nodes.
4. **Proxy-node expansion** — inject a synthetic boundary-gate node on each group's
   boundary for cross-scope edges, so the outer layout treats the group as having defined
   entry/exit anchors.

## Background

### Current state

`_recursive_group_layout` (lines 507–711 in `_pipeline.py`) runs DFS post-order to
adjust member positions when a group's `direction` differs from the outer layout direction.
It moves node coordinates but does NOT:

- Partition edges by scope.
- Create or update waypoints for edges that cross group boundaries.
- Inject proxy nodes (analogous to `_sm_start_`/`_sm_end_` in `statediagram.py`) for
  general flowchart subgraphs.

Result: cross-scope flowchart edges often clip through group boxes when groups are
repositioned by `_recursive_group_layout`.

### Reference implementation

`statediagram.py` injects `{scope}_sm_start_` and `{scope}_sm_end_` proxy nodes at
`state_model_to_graph()` time, wiring cross-composite transitions through these anchors
before ELK or Sugiyama runs. The compound layout spec generalises this to flowchart
subgraphs at layout time rather than at parse time.

## Acceptance Criteria

- [ ] AC-1 **Group tree**: `_build_group_tree(groups)` returns a `GroupTree` (a
  `dict[str, list[str]]` of parent → ordered-children) and a post-order traversal list.
  Tested: the traversal of a two-level nested subgraph visits the inner group before
  the outer group.

- [ ] AC-2 **Edge partitioning**: `_partition_edges(edges, nodes, groups)` returns
  three lists: `intra` (both src and dst are in the same group at any depth),
  `cross` (src and dst belong to different scopes), `free` (neither endpoint in any group).
  Tested: a 5-node graph with one two-node subgraph correctly classifies edges into the
  three categories.

- [ ] AC-3 **Proxy-node expansion**: `_expand_boundary_gates(nodes, edges, groups)` injects
  a synthetic `_gate_{group_id}_in_` / `_gate_{group_id}_out_` `_Node` (type=`gate`,
  not rendered) for each group that has at least one cross-boundary edge. The cross-boundary
  edge is replaced by two edges: src→gate and gate→dst. The gate node's position is at the
  centroid of the group's boundary face nearest the external node.
  Tested: after expansion, no edge in the `cross` list remains; all cross-boundary paths
  go through a gate node.

- [ ] AC-4 **Innermost-first compile**: `_innermost_first_layout(nodes, edges, groups,
  direction)` applies `_recursive_group_layout` in post-order. After layout, gate nodes
  are removed and cross-boundary edges are restored with the gate node's final position
  recorded as an intermediate waypoint.
  Tested: in a two-level nested subgraph, the inner group's members are positioned before
  the outer group's layout runs.

- [ ] AC-5 **No regression**: existing flowchart and state-diagram tests continue to pass.
  Specifically: `tests/test_unified_pipeline.py`, `tests/test_fix_sequence.py`,
  `tests/test_fix_state.py`.

- [ ] AC-6 **New fixture**: `tests/fixtures/flowchart-cross-scope-edge.mmd` with:
  - An outer LR flowchart
  - A TB subgraph containing at least two nodes
  - At least one edge entering the subgraph from outside
  - At least one edge exiting the subgraph to outside
  `structural_geometry` for the fixture reports `render` (no waypoint clipping).

## Assumptions

- **Parser unchanged**: `_parse_graph_source` already populates `_Group.parent_group`
  and `_Node.group`. Proxy-node injection happens after parsing.
- **Gate nodes hidden**: `_Node(type="gate")` gets `data_attrs` flag `data-gate="1"`;
  the HTML renderer skips rendering gate nodes (already handled by checking node type).
- **Waypoint fidelity**: gate nodes become waypoints on the restored edge, not rendered
  nodes. `_Edge.waypoints` already supports intermediate points.
- **Scope of change**: only `_pipeline.py`. `_parser.py`, `_geometry.py`, and all
  diagram-type modules are untouched.
- **ELK path**: proxy injection runs before both ELK and Python Sugiyama paths.
  After ELK, gate positions come from ELK output (same as regular nodes). After Python
  path, gate positions come from `_assign_coordinates`.

## Testing Strategy

- Unit tests in `tests/test_compound_layout.py`:
  - `test_build_group_tree_post_order` — AC-1
  - `test_partition_edges_three_categories` — AC-2
  - `test_expand_boundary_gates_no_direct_cross_edges` — AC-3
  - `test_innermost_first_positions_inner_before_outer` — AC-4
- Fixture test: `test_graph_fixture_no_overlap[flowchart-cross-scope-edge]` (existing
  parametrize table in `test_unified_pipeline.py`) — AC-6
- Regression sweep: `pytest tests/test_unified_pipeline.py tests/test_fix_state.py -q`
  — AC-5

## Deferred

- Mixed-direction nested groups beyond depth-2 (handled by post-order but not tested
  beyond depth-2 in this spec).
- Cycle detection in group tree (cyclic group membership is already a parse error).
- Animated layout transitions.
