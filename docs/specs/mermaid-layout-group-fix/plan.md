# Plan: mermaid-layout-group-fix

**Status:** Implementing
**Spec:** docs/specs/mermaid-layout-group-fix/spec.md

## Dagre-inspired improvements (expanded scope)

Beyond the 4 original bugs, adding two dagre-inspired improvements:

**A — Variable rank heights in TB mode** (`_assign_coordinates`)  
Dagre uses actual node dimensions for layout. Our LR mode already does variable-pitch Y (by col height). Parity for TB mode: accumulate Y positions by actual max node height per rank. Fixes canvas_h underestimation AND intermediate-rank node overlap in one shot.

**B — Group column compaction** (`_compact_group_columns`, new in `_layout.py`)  
Post-barycenter pass that checks for groups with overlapping column-range × rank-range and shifts the right-er group's col indices to give exclusive column ranges. This is the Python analogue of dagre's cluster-aware ordering.

## Tasks

### T1 — Write RED tests (all 8 cases)
**Depends on:** none
**Verification mode:** TDD
**Done when:** 8 new tests exist, all fail with current code

**Tests:**
- `TestVariableRankHeights.test_tb_variable_rank_heights_tall_last_rank_node` — canvas_h ≥ tallest-rank-node bottom + CANVAS_PAD
- `TestVariableRankHeights.test_tb_variable_rank_heights_intermediate_no_overlap` — intermediate-rank tall node doesn't overlap next rank's top
- `TestVariableRankHeights.test_tb_variable_rank_heights_simple_unchanged_for_uniform_nodes` — for uniform-height nodes, canvas_h = 2*CANVAS_PAD + ... (same as before, within rounding)
- `TestCompactGroupColumns.test_compact_group_columns_separates_overlapping` — two groups with overlapping col×rank range get non-overlapping col ranges after compact
- `TestCompactGroupColumns.test_compact_group_columns_noop_for_nonoverlapping_rank` — groups with same col range but non-overlapping rank range are NOT shifted
- `TestComputeGroupBboxes.test_compute_group_bboxes_no_overlap` — two overlapping padded bboxes → resolved after `_compute_group_bboxes`
- `TestComputeGroupBboxes.test_compute_group_bboxes_clips_to_canvas` — bbox clipped to canvas bounds
- `TestSeparateGroupsTB.test_separate_groups_tb_resolves_x_overlap` — groups with X+Y overlap → separated after `_separate_groups_tb`

---

### T2 — Variable rank heights in `_assign_coordinates` (TB mode)
**Depends on:** T1
**Verification mode:** TDD
**Done when:** All 3 `TestVariableRankHeights` tests GREEN

**Approach:**
In `_layout.py`, replace the fixed-pitch TB coordinate assignment:

```python
# TB path — BEFORE (fixed pitch):
col_pitch = NODE_W + COL_GAP
row_pitch = NODE_H + RANK_GAP
max_col = max(n.col for n in nodes.values())
for n in nodes.values():
    n.x = CANVAS_PAD + n.col * col_pitch
    n.y = CANVAS_PAD + n.rank * row_pitch
canvas_w = CANVAS_PAD * 2 + (max_col + 1) * col_pitch - COL_GAP
canvas_h = CANVAS_PAD * 2 + (max_rank + 1) * row_pitch - RANK_GAP

# TB path — AFTER (variable rank heights, mirrors LR column heights):
col_pitch = NODE_W + COL_GAP
max_col = max(n.col for n in nodes.values())
for n in nodes.values():
    n.x = CANVAS_PAD + n.col * col_pitch

# Group by rank, accumulate Y
rank_to_nodes: dict[int, list] = {}
for n in nodes.values():
    rank_to_nodes.setdefault(n.rank, []).append(n)
y_cursor = CANVAS_PAD
for rank in sorted(rank_to_nodes):
    rank_h = max(_node_render_h(n) for n in rank_to_nodes[rank])
    for n in rank_to_nodes[rank]:
        n.y = y_cursor
    y_cursor += rank_h + RANK_GAP

canvas_w = CANVAS_PAD * 2 + (max_col + 1) * col_pitch - COL_GAP
canvas_h = y_cursor + CANVAS_PAD - RANK_GAP
```

**Invariant preserved**: dummy nodes are in `rank_to_nodes` and get correct Y positions. They have `is_dummy=True` but `_node_render_h` returns `NODE_H` for them (no icon, single line).

---

### T3 — Add `_compact_group_columns` to `_layout.py`
**Depends on:** T1
**Verification mode:** TDD
**Done when:** `TestCompactGroupColumns` tests GREEN

**Approach:**
Add to `_layout.py`. Add `_Group`, `GROUP_CAP` to imports from `._constants`.

```python
def _compact_group_columns(
    nodes: dict[str, _Node],
    groups: dict[str, _Group],
) -> None:
    """Push groups with overlapping col×rank ranges to exclusive column bands.

    Called after _minimize_crossings but before _assign_coordinates.
    Modifies n.col values; does not touch n.x or n.y (not yet assigned).
    """
    if not groups:
        return

    def _ranges(gid):
        mbrs = [nodes[m] for m in groups[gid].members
                if m in nodes and not nodes[m].is_dummy]
        if not mbrs:
            return None
        return (
            min(n.col for n in mbrs), max(n.col for n in mbrs),
            min(n.rank for n in mbrs), max(n.rank for n in mbrs),
        )

    for _pass in range(GROUP_CAP):
        rng = {gid: _ranges(gid) for gid in groups}
        rng = {gid: r for gid, r in rng.items() if r is not None}
        if not rng:
            break
        sorted_gids = sorted(rng, key=lambda g: rng[g][0])  # by col_min
        moved = False
        for i, g1 in enumerate(sorted_gids):
            c1_lo, c1_hi, r1_lo, r1_hi = rng[g1]
            for g2 in sorted_gids[i + 1:]:
                c2_lo, c2_hi, r2_lo, r2_hi = rng[g2]
                col_overlap = c1_lo <= c2_hi and c2_lo <= c1_hi
                rank_overlap = r1_lo <= r2_hi and r2_lo <= r1_hi
                if col_overlap and rank_overlap:
                    shift = c1_hi - c2_lo + 1
                    for nid in groups[g2].members:
                        if nid in nodes:
                            nodes[nid].col += shift
                    # Also shift all non-group nodes at those cols that are
                    # within the rank band — so they don't end up inside g1's zone
                    member_ids = {m for grp in groups.values() for m in grp.members}
                    for nid, n in nodes.items():
                        if nid not in member_ids and not n.is_dummy:
                            if c2_lo <= n.col <= c2_hi and r2_lo <= n.rank <= r2_hi:
                                n.col += shift
                    moved = True
                    break
            if moved:
                break
        if not moved:
            break
```

Also export `_compact_group_columns` from `__init__.py` and expose in test imports.

---

### T4 — Wire `_compact_group_columns` into `_layout_graph_topology`
**Depends on:** T3
**Verification mode:** goal-based (diff + existing tests pass)
**Done when:** `_layout_graph_topology` calls `_compact_group_columns` after `_minimize_crossings`

**Approach:**
In `_strategies.py`, import `_compact_group_columns` from `._layout`.
Insert call in `_layout_graph_topology`:
```python
_minimize_crossings(nodes, edges)
if groups:                          # NEW
    _compact_group_columns(nodes, groups)  # NEW
canvas_w, canvas_h = _assign_coordinates(nodes, direction)
```

---

### T5 — Add `_compute_group_bboxes` to `_renderer.py`
**Depends on:** T1
**Verification mode:** TDD
**Done when:** `TestComputeGroupBboxes` tests GREEN

**Approach:** (See spec plan T3 — unchanged)

---

### T6 — Wire `_compute_group_bboxes` into `_render_graph_fragment`
**Depends on:** T5
**Verification mode:** goal-based (diff)
**Done when:** group div rendering uses `_compute_group_bboxes`

---

### T7 — Add `_separate_groups_tb` to `_renderer.py`
**Depends on:** T1
**Verification mode:** TDD
**Done when:** `TestSeparateGroupsTB.test_separate_groups_tb_resolves_x_overlap` GREEN

**Approach:** (See spec plan T5 — unchanged, mirrors `_separate_groups_lr`)

---

### T8 — Wire `_separate_groups_tb` into `_layout_graph_topology`
**Depends on:** T7
**Verification mode:** goal-based (diff)

---

### T9 — Export new symbols from `__init__.py`
**Depends on:** T3, T5, T7
**Verification mode:** goal-based
**Done when:** All 4 new symbols importable: `_compute_group_bboxes`, `_separate_groups_tb`, `_compact_group_columns`

---

### T10 — Full suite green
**Depends on:** T1–T9
**Verification mode:** TDD + goal-based
**Done when:** `pytest tests/ -x -q` → 120+ tests pass; `python3 scripts/smoke_test.py --phase 2` → 39/39

---

## Implementation order

T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10

## Key notes

- T2 (variable rank heights) is the most impactful single change — it fixes canvas_h AND intermediate-rank overlap AND mirrors how dagre handles variable node sizes.
- T3 (`_compact_group_columns`) is the closest Python equivalent to dagre's cluster-aware ordering. It operates on col indices (not pixels), so it's safe to run before coordinate assignment.
- `_separate_groups_tb` (T7) and `_compute_group_bboxes` (T5) are safety nets for any cases that slipped through T3+T4.
- CANVAS_PAD, COL_GAP, GROUP_PAD_* constants are NOT changed here.
