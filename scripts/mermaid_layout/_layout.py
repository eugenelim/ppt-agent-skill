from __future__ import annotations

from typing import Optional

from ._constants import (
    _Node, _Edge, _Group,
    NODE_W, NODE_H, COL_GAP, RANK_GAP, CANVAS_PAD,
    CROSSING_PASSES, GROUP_CAP,
    _node_render_h,
)

# ── cycle break (DFS back-edge detection) ─────────────────────────────────────

def _break_cycles(nodes: dict[str, _Node], edges: list[_Edge]) -> None:
    """Mark back-edges reversed_=True (DFS from source nodes)."""
    adj: dict[str, list[int]] = {nid: [] for nid in nodes}
    for i, e in enumerate(edges):
        if e.src in adj and e.dst in adj:
            adj[e.src].append(i)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    def dfs(u: str) -> None:
        color[u] = GRAY
        for ei in adj[u]:
            v = edges[ei].dst
            if color.get(v) == GRAY:
                edges[ei].reversed_ = True  # back-edge
            elif color.get(v) == WHITE:
                dfs(v)
        color[u] = BLACK

    for nid in list(nodes.keys()):
        if color[nid] == WHITE:
            dfs(nid)


# ── rank assignment (longest path, then dummy insertion) ──────────────────────

def _assign_ranks(nodes: dict[str, _Node], edges: list[_Edge]) -> None:
    """Longest-path rank assignment; inserts dummy nodes for multi-rank edges."""
    # Build effective successors (skip reversed edges for rank calc)
    succ: dict[str, list[str]] = {nid: [] for nid in nodes}
    pred_count: dict[str, int] = {nid: 0 for nid in nodes}
    for e in edges:
        if e.src in nodes and e.dst in nodes and not e.reversed_:
            succ[e.src].append(e.dst)
            pred_count[e.dst] += 1

    # Topological order (Kahn's algorithm on the forward DAG).
    # Use a scratch copy so pred_count stays intact for the isolation check below.
    from collections import deque
    _pc_kahn: dict[str, int] = dict(pred_count)
    queue: deque[str] = deque(nid for nid in nodes if _pc_kahn[nid] == 0)
    topo: list[str] = []
    while queue:
        u = queue.popleft()
        topo.append(u)
        for v in succ[u]:
            _pc_kahn[v] -= 1
            if _pc_kahn[v] == 0:
                queue.append(v)
    # Any node not yet in topo (cycle residue) gets appended in stable id order
    remaining = [nid for nid in nodes if nid not in set(topo)]
    topo.extend(sorted(remaining))

    # Longest-path ranks
    for nid in nodes:
        nodes[nid].rank = 0
    for u in topo:
        for v in succ[u]:
            nodes[v].rank = max(nodes[v].rank, nodes[u].rank + 1)

    # Isolated-source promotion: grouped nodes with no predecessors whose
    # outgoing edges ALL go to interior nodes (rank ≥ 1). Promote to
    # max(target_rank)+1 so they render RIGHT of their targets in LR layout,
    # with edges routed as back-edges. Ungrouped nodes (e.g. the main CLIENT)
    # are left at rank 0; only group-bounded side-feeder clusters are promoted.
    #
    # Guard: only promote when at least one target has predecessors from OUTSIDE
    # the group. If ALL predecessors of a target are from within the same group,
    # the group is a genuine source cluster (entry points of the flow) and should
    # stay at rank 0 — promoting would make edges run right→left.
    _target_preds: dict[str, set[str]] = {nid: set() for nid in nodes}
    for e in edges:
        if e.dst in _target_preds and not e.reversed_:
            _target_preds[e.dst].add(e.src)
    for nid, n in list(nodes.items()):
        if pred_count.get(nid, 0) != 0 or n.is_dummy or not n.group:
            continue
        out_targets = [v for v in succ.get(nid, []) if v in nodes]
        if not (out_targets and all(nodes[v].rank >= 2 for v in out_targets)):
            continue
        group_members = {nid2 for nid2, n2 in nodes.items() if n2.group == n.group}
        has_external_pred = any(
            (_target_preds[v] - group_members) for v in out_targets
        )
        if has_external_pred:
            n.rank = max(nodes[v].rank for v in out_targets) + 1

    # Insert dummy nodes for edges spanning more than 1 rank
    new_nodes: dict[str, _Node] = {}
    new_edges: list[_Edge] = []
    for e in list(edges):
        if e.reversed_ or e.src not in nodes or e.dst not in nodes:
            new_edges.append(e)
            continue
        gap = nodes[e.dst].rank - nodes[e.src].rank
        if gap <= 1:
            new_edges.append(e)
            continue
        # Insert gap-1 dummy nodes
        prev_id = e.src
        for k in range(1, gap):
            dummy_id = f"_dummy_{e.src}_{e.dst}_{k}"
            dummy_rank = nodes[e.src].rank + k
            dummy = _Node(id=dummy_id, label="", is_dummy=True, rank=dummy_rank)
            new_nodes[dummy_id] = dummy
            new_edges.append(_Edge(src=prev_id, dst=dummy_id, label="" if k > 1 else e.label,
                                   style=e.style, arrow=False))
            prev_id = dummy_id
        new_edges.append(_Edge(src=prev_id, dst=e.dst, style=e.style, arrow=e.arrow))

    nodes.update(new_nodes)
    edges[:] = new_edges


# ── crossing minimisation (8-pass barycenter) ─────────────────────────────────

def _minimize_crossings(nodes: dict[str, _Node], edges: list[_Edge]) -> None:
    """8-pass barycenter crossing minimisation; assigns col index to each node."""
    max_rank = max((n.rank for n in nodes.values()), default=0)
    # Build ranks list (sorted by id for stability)
    ranks: list[list[str]] = [[] for _ in range(max_rank + 1)]
    for nid in sorted(nodes.keys()):
        r = nodes[nid].rank
        if 0 <= r <= max_rank:
            ranks[r].append(nid)

    # Build successor and predecessor adjacency (col-weighted)
    succ_ids: dict[str, list[str]] = {nid: [] for nid in nodes}
    pred_ids: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:
        if e.src in nodes and e.dst in nodes:
            succ_ids[e.src].append(e.dst)
            pred_ids[e.dst].append(e.src)

    def _assign_cols(rank_list: list[str]) -> None:
        for i, nid in enumerate(rank_list):
            nodes[nid].col = i
            nodes[nid].bary = float(i)

    # Initialize columns in declaration order (stable)
    for r_list in ranks:
        _assign_cols(r_list)

    def _forward_pass() -> None:
        for r in range(1, max_rank + 1):
            for nid in ranks[r]:
                ps = pred_ids[nid]
                if ps:
                    nodes[nid].bary = sum(nodes[p].col for p in ps if p in nodes) / len(ps)
            ranks[r].sort(key=lambda nid: (nodes[nid].bary, nid))
            _assign_cols(ranks[r])

    def _backward_pass() -> None:
        for r in range(max_rank - 1, -1, -1):
            for nid in ranks[r]:
                ss = succ_ids[nid]
                if ss:
                    nodes[nid].bary = sum(nodes[s].col for s in ss if s in nodes) / len(ss)
            ranks[r].sort(key=lambda nid: (nodes[nid].bary, nid))
            _assign_cols(ranks[r])

    for _ in range(CROSSING_PASSES // 2):
        _forward_pass()
        _backward_pass()


def _group_coherent_cols(
    nodes: dict[str, _Node],
    groups: dict[str, _Group],
) -> None:
    """Re-assign cols within each rank so nodes in the same group are adjacent.

    Called after _minimize_crossings. Preserves the relative bary-sorted order of
    group clusters (the group with the lowest average bary comes first) but ensures
    all members of a group are consecutive — keeping the group's y-span compact in
    LR mode and reducing nested-group bbox inflation.

    Nodes with no group affiliation are placed in a cluster keyed by "" (empty string)
    and sort after all named groups within their rank, maintaining stable ordering.
    """
    if not groups:
        return
    max_rank = max(n.rank for n in nodes.values())
    for rank in range(max_rank + 1):
        rank_nids = [nid for nid, n in nodes.items() if n.rank == rank and not n.is_dummy]
        if not rank_nids:
            continue
        # Group key → list of (bary, nid); "" for ungrouped
        buckets: dict[str, list[tuple[float, str]]] = {}
        for nid in rank_nids:
            gkey = nodes[nid].group or ""
            buckets.setdefault(gkey, []).append((nodes[nid].bary, nid))
        # Compute each bucket's average bary so buckets sort by their centre
        bucket_order = sorted(
            buckets.items(),
            key=lambda kv: (kv[0] == "", sum(b for b, _ in kv[1]) / len(kv[1]))
        )
        col = 0
        for _gkey, members in bucket_order:
            for _bary, nid in sorted(members):
                nodes[nid].col = col
                col += 1


# ── coordinate assignment (integer pixels) ────────────────────────────────────

def _assign_coordinates(nodes: dict[str, _Node], direction: str = "TB") -> tuple[int, int]:
    """Assign x/y pixel positions; return (canvas_width, canvas_height).

    TB (default): rank→Y (row), col→X (column). Row heights are variable based on
    actual node render heights (mirrors LR's variable column heights — dagre parity).
    LR: rank→X (column), col→Y (row) with variable Y pitch based on node height.
    """
    if not nodes:
        return 2 * CANVAS_PAD, 2 * CANVAS_PAD

    is_lr = direction.upper() in ("LR", "RL")
    max_rank = max(n.rank for n in nodes.values())

    if not is_lr:
        col_pitch = NODE_W + COL_GAP
        max_col = max(n.col for n in nodes.values())
        for n in nodes.values():
            n.x = CANVAS_PAD + n.col * col_pitch

        # Pull dummy nodes (routing waypoints) tightly against their sibling column.
        # Without this, a dummy assigned to col 1 sits ~290px from col-0 nodes,
        # creating very wide horizontal sweeps in the rendered edge paths.
        # Strategy: move each dummy to just right of the rightmost non-dummy at the same rank.
        _DUMMY_MARGIN = 20
        for n in nodes.values():
            if not n.is_dummy:
                continue
            _siblings = [nn for nn in nodes.values() if nn.rank == n.rank and not nn.is_dummy]
            if _siblings:
                _rightmost = max(nn.x + NODE_W for nn in _siblings)
                n.x = _rightmost + _DUMMY_MARGIN

        # Variable rank heights: accumulate Y positions by actual max node height per rank.
        # Nodes shorter than rank_h are centered vertically within the row.
        rank_to_nodes: dict[int, list] = {}
        for n in nodes.values():
            rank_to_nodes.setdefault(n.rank, []).append(n)
        y_cursor = CANVAS_PAD
        for rank in sorted(rank_to_nodes):
            rank_h = max(_node_render_h(n) for n in rank_to_nodes[rank])
            for n in rank_to_nodes[rank]:
                n.y = y_cursor + (rank_h - _node_render_h(n)) // 2
            y_cursor += rank_h + RANK_GAP

        # Recompute canvas_w using actual node x positions (dummies may have shifted)
        max_x_right = max(n.x + NODE_W for n in nodes.values())
        canvas_w = max_x_right + CANVAS_PAD
        canvas_h = y_cursor + CANVAS_PAD - RANK_GAP
        return canvas_w, canvas_h

    # LR: rank→X with fixed pitch; col→Y with variable pitch (multi-line nodes)
    rank_pitch = NODE_W + RANK_GAP
    for n in nodes.values():
        n.x = CANVAS_PAD + n.rank * rank_pitch

    # Group nodes by col, accumulate Y positions top-to-bottom.
    # Nodes shorter than col_h are centered vertically within the band.
    col_to_nodes: dict[int, list] = {}
    for n in nodes.values():
        col_to_nodes.setdefault(n.col, []).append(n)
    y_cursor = CANVAS_PAD
    for col in sorted(col_to_nodes):
        col_h = max(_node_render_h(n) for n in col_to_nodes[col])
        for n in col_to_nodes[col]:
            n.y = y_cursor + (col_h - _node_render_h(n)) // 2
        y_cursor += col_h + COL_GAP

    canvas_w = CANVAS_PAD * 2 + (max_rank + 1) * rank_pitch - RANK_GAP
    canvas_h = y_cursor + CANVAS_PAD - COL_GAP
    return canvas_w, canvas_h


# ── group column compaction (dagre-inspired cluster column separation) ─────────

def _compact_group_columns(
    nodes: dict[str, _Node],
    groups: dict[str, _Group],
) -> None:
    """Push groups with overlapping col×rank ranges to exclusive column bands.

    Called after _minimize_crossings (which assigns n.col) but before
    _assign_coordinates (which converts col to x pixels). Modifies n.col only.

    Two groups "collide" when their column ranges AND rank ranges both overlap.
    The right-er group (higher col_min) is shifted right by the overlap + 1.
    Non-member nodes in the same col×rank band are shifted with the group.

    This is the Python analogue of dagre's cluster-aware ordering step.
    """
    if not groups:
        return

    def _ranges(gid: str) -> Optional[tuple[int, int, int, int]]:
        mbrs = [nodes[m] for m in groups[gid].members
                if m in nodes and not nodes[m].is_dummy]
        if not mbrs:
            return None
        return (
            min(n.col for n in mbrs), max(n.col for n in mbrs),
            min(n.rank for n in mbrs), max(n.rank for n in mbrs),
        )

    def _is_nested(ga: str, gb: str) -> bool:
        """True if ga and gb are in a parent-child relationship (either direction)."""
        cur = groups[gb].parent_group
        while cur:
            if cur == ga:
                return True
            cur = groups[cur].parent_group if cur in groups else None
        cur = groups[ga].parent_group
        while cur:
            if cur == gb:
                return True
            cur = groups[cur].parent_group if cur in groups else None
        return False

    member_ids = {nid for grp in groups.values() for nid in grp.members}

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
                if _is_nested(g1, g2):
                    continue
                c2_lo, c2_hi, r2_lo, r2_hi = rng[g2]
                col_overlap = c1_lo <= c2_hi and c2_lo <= c1_hi
                rank_overlap = r1_lo <= r2_hi and r2_lo <= r1_hi
                if col_overlap and rank_overlap:
                    shift = c1_hi - c2_lo + 1
                    for nid in groups[g2].members:
                        if nid in nodes:
                            nodes[nid].col += shift
                    # Shift non-member nodes in the same col×rank band
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
