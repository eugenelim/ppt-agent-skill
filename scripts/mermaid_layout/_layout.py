from __future__ import annotations

from typing import Optional

from ._constants import (
    _Node, _Edge,
    NODE_W, NODE_H, COL_GAP, RANK_GAP, CANVAS_PAD,
    CROSSING_PASSES,
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

    # Topological order (Kahn's algorithm on the forward DAG)
    from collections import deque
    queue: deque[str] = deque(nid for nid in nodes if pred_count[nid] == 0)
    topo: list[str] = []
    while queue:
        u = queue.popleft()
        topo.append(u)
        for v in succ[u]:
            pred_count[v] -= 1
            if pred_count[v] == 0:
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


# ── coordinate assignment (integer pixels) ────────────────────────────────────

def _assign_coordinates(nodes: dict[str, _Node], direction: str = "TB") -> tuple[int, int]:
    """Assign x/y pixel positions; return (canvas_width, canvas_height).

    TB (default): rank→Y (row), col→X (column).
    LR: rank→X (column), col→Y (row) with variable Y pitch based on node height.
    """
    if not nodes:
        return 2 * CANVAS_PAD, 2 * CANVAS_PAD

    is_lr = direction.upper() in ("LR", "RL")
    max_rank = max(n.rank for n in nodes.values())

    if not is_lr:
        col_pitch = NODE_W + COL_GAP
        row_pitch = NODE_H + RANK_GAP
        max_col = max(n.col for n in nodes.values())
        for n in nodes.values():
            n.x = CANVAS_PAD + n.col * col_pitch
            n.y = CANVAS_PAD + n.rank * row_pitch
        canvas_w = CANVAS_PAD * 2 + (max_col + 1) * col_pitch - COL_GAP
        canvas_h = CANVAS_PAD * 2 + (max_rank + 1) * row_pitch - RANK_GAP
        return canvas_w, canvas_h

    # LR: rank→X with fixed pitch; col→Y with variable pitch (multi-line nodes)
    rank_pitch = NODE_W + RANK_GAP
    for n in nodes.values():
        n.x = CANVAS_PAD + n.rank * rank_pitch

    # Group nodes by col, accumulate Y positions top-to-bottom
    col_to_nodes: dict[int, list] = {}
    for n in nodes.values():
        col_to_nodes.setdefault(n.col, []).append(n)
    y_cursor = CANVAS_PAD
    for col in sorted(col_to_nodes):
        col_h = max(_node_render_h(n) for n in col_to_nodes[col])
        for n in col_to_nodes[col]:
            n.y = y_cursor
        y_cursor += col_h + COL_GAP

    canvas_w = CANVAS_PAD * 2 + (max_rank + 1) * rank_pitch - RANK_GAP
    canvas_h = y_cursor + CANVAS_PAD - COL_GAP
    return canvas_w, canvas_h
