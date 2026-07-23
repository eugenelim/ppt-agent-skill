Mode: light (no risk trigger fired — two bounded bugs in two familiar files)

# Orthogonal Routing Fixes

## Objective

Fix three routing defects in the Python Sugiyama + A\* path that cause diagonal edges,
a global back-edge lane, and misaligned fan-in placement. No ELK changes; Python path only.

## Acceptance Criteria

- `flowchart-arrows-defs`: A→B solid, A→C thick, A→D dotted styles correctly preserved. ✓ (already passing)
- `flowchart-diamond-branch`: all waypoint segments are orthogonal (no Δx≠0 ∧ Δy≠0 pairs);
  back-edge Retry→Check uses lane ≤ max(Retry.right, Check.right) + margin, not global canvas right.
- `flowchart-parallel-links`: E.x ≈ barycenter(B.cx, C.cx, D.cx) − E.w/2 (within ±20 px).
- All 10 `test_graph_fixture_no_overlap` tests still pass with `strict=True`.
- No new regressions across all existing tests.

## Task List

1. **`_routing.py`**: Add `_ensure_orthogonal(pts)` helper; call after A\* endpoint substitution
   (lines 1253-1255). Inserts a bend wherever both x and y change between consecutive waypoints.

2. **`_routing.py`**: Replace global TB back-edge lane (line 999) with local lane:
   `max(s.x + nw_s, d.x + nw_d) + 12 * (be_lane + 1)` so Retry→Check stays within
   the two-column local structure.

3. **`_layout.py`**: Add `_center_isolated_nodes(nodes, edges)`: for each non-dummy node
   that is the sole occupant of its rank and has 2+ real predecessors, reposition it to
   `round(barycenter_x) − nw // 2`.
   Call from `_strategies.py` after `_assign_coordinates` (Python path only, TB only).

## What is NOT changing

- ELK path: not touched (elkjs not installed; Python path handles all three fixtures).
- `_minimize_crossings`: column index assignment unchanged.
- `_renderer.py`: edge style → marker mapping already correct.
- Skip-lane routing for arrows-defs bypass edges: already correct.
- Diamond port face selection: `_ensure_orthogonal` corrects post-substitution diagonals
  without redesigning port selection.
