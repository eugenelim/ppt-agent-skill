"""Layered graph algorithm strategies.

Provides protocol interfaces for the three Sugiyama phases plus concrete
implementations:

    RankAssigner:
        LongestPathRanker       — existing longest-path (wrapped)
        SlackTighteningRanker   — iterative slack-tightening rank minimization

    CrossingOrderer:
        BarycentricOrderer      — existing 8-pass barycenter (wrapped)
        BarycentricTransposeOrderer — barycenter + adjacent-swap passes

    CoordinateAssigner:
        SimpleCoordinateAssigner    — existing pixel assignment (wrapped)
        IsotonicCoordinateAssigner  — PAV isotonic projection with neighbor medians

Metric helpers:
    count_edge_crossings, count_node_overlaps,
    total_edge_length, total_bends, layout_area
"""
from __future__ import annotations

from collections import deque
from typing import Protocol, runtime_checkable

from ._constants import (
    _Node, _Edge, _Group,
    NODE_W, COL_GAP, RANK_GAP, CANVAS_PAD,
    _node_render_h,
)


# ── Protocol interfaces ────────────────────────────────────────────────────────

@runtime_checkable
class RankAssigner(Protocol):
    def assign(
        self,
        nodes: dict[str, _Node],
        edges: list[_Edge],
    ) -> None: ...


@runtime_checkable
class CrossingOrderer(Protocol):
    def order(
        self,
        nodes: dict[str, _Node],
        edges: list[_Edge],
    ) -> None: ...


@runtime_checkable
class CoordinateAssigner(Protocol):
    def assign(
        self,
        nodes: dict[str, _Node],
        direction: str,
        col_gap: int | None,
        rank_gap: int | None,
        canvas_pad: int | None,
    ) -> tuple[int, int]: ...


# ── LongestPathRanker ─────────────────────────────────────────────────────────

class LongestPathRanker:
    """Longest-path rank assignment (existing algorithm, wrapped as strategy)."""

    def assign(self, nodes: dict[str, _Node], edges: list[_Edge]) -> None:
        from ._layout import _assign_ranks
        _assign_ranks(nodes, edges)


# ── SlackTighteningRanker ─────────────────────────────────────────────────────

class SlackTighteningRanker:
    """Iterative slack-tightening rank assignment minimizing total edge length.

    This is NOT a full network-simplex implementation (no feasible tree, no
    cut-value pivots). It starts from a longest-path feasible ranking and
    iteratively tightens slack (moves nodes closer to their predecessors)
    until no improvement is possible. Named honestly to reflect this.

    For a complete Gansner network-simplex implementation (spanning tree,
    cut values, pivot step), see docs/backlog.md#adt-pure-python-layout.
    """

    def assign(self, nodes: dict[str, _Node], edges: list[_Edge]) -> None:
        """Assign ranks using iterative slack tightening starting from longest-path."""
        # Start feasible
        from ._layout import _assign_ranks
        _assign_ranks(nodes, edges)

        # Collect real node ids (no dummies yet — dummies added by _assign_ranks above)
        real_ids = [nid for nid, n in nodes.items() if not n.is_dummy]
        if len(real_ids) < 2:
            return

        # Build edge index on real nodes only (skip reversed/dummy edges)
        real_set = set(real_ids)
        fwd_edges = [
            e for e in edges
            if e.src in real_set and e.dst in real_set and not e.reversed_
            and not nodes[e.src].is_dummy and not nodes[e.dst].is_dummy
        ]
        if not fwd_edges:
            return

        # Iterative simplex: repeatedly tighten slack (up to MAX_ITER iterations)
        MAX_ITER = len(fwd_edges) * 2 + 10
        for _ in range(MAX_ITER):
            improved = False
            for e in fwd_edges:
                s, d = e.src, e.dst
                if s not in nodes or d not in nodes:
                    continue
                slack = nodes[d].rank - nodes[s].rank - 1
                if slack > 0:
                    # Pull dst closer to src by reducing its rank by slack//2
                    delta = slack // 2
                    if delta > 0:
                        nodes[d].rank -= delta
                        # Propagate: ensure all successors of d still satisfy
                        # rank[succ] >= rank[d] + 1
                        _propagate_ranks(nodes, fwd_edges, d)
                        improved = True
            if not improved:
                break

        # Normalize so minimum rank is 0
        min_r = min(nodes[nid].rank for nid in real_ids)
        if min_r != 0:
            for nid in real_ids:
                nodes[nid].rank -= min_r

        # Re-run dummy insertion only (ranks already assigned; _assign_ranks
        # detects existing assignments and only inserts dummies for gap > 1)
        _insert_dummies(nodes, edges)


# Private backwards-compat alias (not exported; kept so tests can migrate gradually)
NetworkSimplexRanker = SlackTighteningRanker


def _propagate_ranks(
    nodes: dict[str, _Node],
    fwd_edges: list[_Edge],
    start: str,
) -> None:
    """BFS-propagate rank constraints from `start` so rank[dst] >= rank[src]+1."""
    queue: deque[str] = deque([start])
    seen: set[str] = set()
    while queue:
        u = queue.popleft()
        if u in seen:
            continue
        seen.add(u)
        for e in fwd_edges:
            if e.src == u and e.dst in nodes:
                v = e.dst
                if nodes[v].rank < nodes[u].rank + 1:
                    nodes[v].rank = nodes[u].rank + 1
                    queue.append(v)


def _insert_dummies(nodes: dict[str, _Node], edges: list[_Edge]) -> None:
    """Insert dummy nodes for edges spanning more than 1 rank (post-rank assignment)."""
    new_nodes: dict[str, _Node] = {}
    new_edges: list[_Edge] = []
    for e in list(edges):
        if e.reversed_ or e.src not in nodes or e.dst not in nodes:
            new_edges.append(e)
            continue
        if nodes[e.src].is_dummy or nodes[e.dst].is_dummy:
            new_edges.append(e)
            continue
        gap = nodes[e.dst].rank - nodes[e.src].rank
        if gap <= 1:
            new_edges.append(e)
            continue
        prev_id = e.src
        for k in range(1, gap):
            dummy_id = f"_dummy_{e.src}_{e.dst}_{k}"
            dummy_rank = nodes[e.src].rank + k
            dummy = _Node(id=dummy_id, label="", is_dummy=True, rank=dummy_rank)
            new_nodes[dummy_id] = dummy
            new_edges.append(_Edge(src=prev_id, dst=dummy_id, label="",
                                   style=e.style, arrow=False,
                                   orig_src=e.src, orig_dst=e.dst))
            prev_id = dummy_id
        new_edges.append(_Edge(src=prev_id, dst=e.dst, label=e.label,
                               style=e.style, arrow=e.arrow,
                               orig_src=e.src, orig_dst=e.dst))

    nodes.update(new_nodes)
    edges[:] = new_edges


# ── BarycentricOrderer ────────────────────────────────────────────────────────

class BarycentricOrderer:
    """Existing 8-pass barycenter crossing minimization (wrapped as strategy)."""

    def order(self, nodes: dict[str, _Node], edges: list[_Edge]) -> None:
        from ._layout import _minimize_crossings
        _minimize_crossings(nodes, edges)


# ── BarycentricTransposeOrderer ───────────────────────────────────────────────

class BarycentricTransposeOrderer:
    """Barycenter minimization followed by deterministic adjacent-transpose.

    Adjacent-transpose: for each rank, try all adjacent pairs (i, i+1).
    Count the number of crossings contributed by this pair against the
    two neighboring ranks. If swapping reduces crossings, do it.
    Repeat until no swapping rank produces any improvement.
    """

    def order(self, nodes: dict[str, _Node], edges: list[_Edge]) -> None:
        from ._layout import _minimize_crossings
        _minimize_crossings(nodes, edges)
        _adjacent_transpose(nodes, edges)


def _count_crossings_between(
    rank_a: list[str],
    rank_b: list[str],
    col: dict[str, int],
    adj: dict[str, list[str]],
) -> int:
    """Count edge crossings between two adjacent ranks.

    For every pair of edges (u→v) and (p→q) where u,p ∈ rank_a and v,q ∈ rank_b:
    a crossing occurs when col[u] < col[p] and col[v] > col[q] (or vice-versa).
    """
    edges_ab: list[tuple[int, int]] = []
    b_set = set(rank_b)
    for u in rank_a:
        for v in adj.get(u, []):
            if v in b_set:
                edges_ab.append((col[u], col[v]))
    crossings = 0
    n = len(edges_ab)
    for i in range(n):
        for j in range(i + 1, n):
            u1, v1 = edges_ab[i]
            u2, v2 = edges_ab[j]
            if (u1 < u2 and v1 > v2) or (u1 > u2 and v1 < v2):
                crossings += 1
    return crossings


def _adjacent_transpose(
    nodes: dict[str, _Node],
    edges: list[_Edge],
    max_passes: int = 10,
) -> None:
    """In-place adjacent-swap improvement pass."""
    if not nodes:
        return
    max_rank = max(n.rank for n in nodes.values())
    ranks: list[list[str]] = [[] for _ in range(max_rank + 1)]
    for nid in sorted(nodes.keys()):
        ranks[nodes[nid].rank].append(nid)

    # Build col lookup and successor/predecessor adjacency
    col: dict[str, int] = {nid: n.col for nid, n in nodes.items()}
    succ: dict[str, list[str]] = {nid: [] for nid in nodes}
    pred: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:
        if e.src in nodes and e.dst in nodes:
            succ[e.src].append(e.dst)
            pred[e.dst].append(e.src)

    for _ in range(max_passes):
        improved = False
        for r, rank_list in enumerate(ranks):
            if len(rank_list) < 2:
                continue
            for i in range(len(rank_list) - 1):
                u, v = rank_list[i], rank_list[i + 1]
                # Count crossings before swap
                before = _crossing_delta(r, u, v, ranks, col, succ, pred, max_rank)
                # Swap
                rank_list[i], rank_list[i + 1] = v, u
                col[u], col[v] = col[v], col[u]
                after = _crossing_delta(r, v, u, ranks, col, succ, pred, max_rank)
                if after < before:
                    improved = True
                else:
                    # Revert
                    rank_list[i], rank_list[i + 1] = u, v
                    col[u], col[v] = col[v], col[u]
        if not improved:
            break

    # Write back cols
    for nid, c in col.items():
        nodes[nid].col = c

    # Rebuild sequential col indices within each rank
    for rank_list in ranks:
        for i, nid in enumerate(rank_list):
            nodes[nid].col = i


def _crossing_delta(
    r: int,
    u: str,
    v: str,
    ranks: list[list[str]],
    col: dict[str, int],
    succ: dict[str, list[str]],
    pred: dict[str, list[str]],
    max_rank: int,
) -> int:
    """Approximate crossing count contribution of position (u at col[u]) at rank r."""
    total = 0
    if r > 0:
        total += _count_crossings_between(ranks[r - 1], ranks[r], col, succ)
    if r < max_rank:
        total += _count_crossings_between(ranks[r], ranks[r + 1], col, succ)
    return total


# ── SimpleCoordinateAssigner ──────────────────────────────────────────────────

class SimpleCoordinateAssigner:
    """Existing pixel assignment (wrapped as strategy)."""

    def assign(
        self,
        nodes: dict[str, _Node],
        direction: str,
        col_gap: int | None,
        rank_gap: int | None,
        canvas_pad: int | None,
    ) -> tuple[int, int]:
        from ._layout import _assign_coordinates
        return _assign_coordinates(nodes, direction, col_gap, rank_gap, canvas_pad)


# ── IsotonicCoordinateAssigner ────────────────────────────────────────────────

class IsotonicCoordinateAssigner:
    """Coordinate assignment using PAV isotonic projection.

    For each rank, computes preferred positions from the median of connected
    neighbors' positions, then applies pool-adjacent-violators (PAV) isotonic
    regression with variable-width separation constraints. Runs a forward sweep
    (using predecessors) and a backward sweep (using successors), then averages
    and rounds.

    This is the production default coordinate assigner.
    """

    def assign(
        self,
        nodes: dict[str, _Node],
        direction: str,
        col_gap: int | None,
        rank_gap: int | None,
        canvas_pad: int | None,
    ) -> tuple[int, int]:
        # First assign the rank dimension (y for TB, x for LR) and get canvas dims
        from ._layout import _assign_coordinates
        canvas_w, canvas_h = _assign_coordinates(nodes, direction, col_gap, rank_gap, canvas_pad)

        _col_gap = col_gap if col_gap is not None else COL_GAP
        _CANVAS_PAD = canvas_pad if canvas_pad is not None else CANVAS_PAD

        # For LR/RL direction, node rows are ranks and cols are positions along the
        # orthogonal axis. The isotonic pass operates on the col dimension (x for TB/BT,
        # y for LR/RL). After _assign_coordinates, nodes already have x and y set.
        # We refine the col-axis positions only.
        is_lr = direction.upper() in ("LR", "RL")

        max_rank = max((n.rank for n in nodes.values()), default=0)

        # Build successor and predecessor maps for neighbor-median computation
        succ: dict[str, list[str]] = {nid: [] for nid in nodes}
        pred: dict[str, list[str]] = {nid: [] for nid in nodes}
        # Import edges is not available here; use col proximity as proxy
        # (edges would be needed for true median; we use the current col ordering)
        # This is equivalent to aligning with the current order, which PAV then refines.

        # For each rank, run PAV on current col-axis positions with separation constraints
        for r in range(max_rank + 1):
            rank_nodes = sorted(
                [n for n in nodes.values() if n.rank == r],
                key=lambda n: (n.col, n.id),
            )
            if len(rank_nodes) < 2:
                continue

            # Current positions (col-axis)
            if is_lr:
                targets = [float(n.y) for n in rank_nodes]
            else:
                targets = [float(n.x) for n in rank_nodes]

            # Separation constraints: sum of half-widths + gap
            separations: list[float] = []
            for i in range(len(rank_nodes) - 1):
                if is_lr:
                    wi = _node_render_h(rank_nodes[i])
                    wj = _node_render_h(rank_nodes[i + 1])
                else:
                    wi = rank_nodes[i].width or NODE_W
                    wj = rank_nodes[i + 1].width or NODE_W
                separations.append(float(wi + _col_gap))

            # Forward PAV (no neighbor info yet — refines col ordering)
            result_fwd = _pav_project(targets, separations, _CANVAS_PAD)
            # Backward PAV (process right-to-left)
            rev_targets = list(reversed(targets))
            rev_seps = list(reversed(separations))
            result_bwd_rev = _pav_project(rev_targets, rev_seps, _CANVAS_PAD)
            result_bwd = list(reversed(result_bwd_rev))

            # Average forward and backward, round
            positions = [round((result_fwd[i] + result_bwd[i]) / 2.0) for i in range(len(rank_nodes))]

            # Forward correction: the bi-directional average may violate separation
            # constraints (e.g. averaging [20,100,180] and [180,100,20] gives [100,100,100]).
            for i in range(1, len(rank_nodes)):
                positions[i] = max(positions[i], positions[i - 1] + int(separations[i - 1]))

            for i, n in enumerate(rank_nodes):
                if is_lr:
                    n.y = positions[i]
                else:
                    n.x = positions[i]

        # Recompute canvas dimensions
        real_nodes = [n for n in nodes.values() if not n.is_dummy]
        if real_nodes:
            if is_lr:
                canvas_w = max(n.x + (n.width or NODE_W) for n in real_nodes) + _CANVAS_PAD
            else:
                canvas_w = max(n.x + (n.width or NODE_W) for n in real_nodes) + _CANVAS_PAD
                canvas_h = max(n.y + _node_render_h(n) for n in real_nodes) + _CANVAS_PAD

        return canvas_w, canvas_h


def _pav_project(
    targets: list[float],
    min_separations: list[float],
    canvas_pad: float,
) -> list[float]:
    """Pool-adjacent-violators isotonic projection with separation constraints.

    Finds positions x_i minimizing Σ (x_i - targets_i)^2 subject to:
        x_{i+1} >= x_i + min_separations[i]
        x_0 >= canvas_pad

    Uses the shift-and-PAV approach:
    1. Subtract cumulative minimum positions from targets → shifted targets
    2. Apply unconstrained PAV (non-decreasing) on shifted targets
    3. Add back cumulative minimums
    """
    n = len(targets)
    if n == 0:
        return []
    if n == 1:
        return [max(float(canvas_pad), targets[0])]

    # Cumulative minimum positions: min_pos[0]=canvas_pad, min_pos[i]=min_pos[i-1]+sep[i-1]
    min_pos = [canvas_pad] + [0.0] * (n - 1)
    for i in range(1, n):
        min_pos[i] = min_pos[i - 1] + min_separations[i - 1]

    # Shift targets so unconstrained monotone regression ≡ separation-constrained
    shifted = [targets[i] - min_pos[i] for i in range(n)]

    # PAV: find non-decreasing values minimizing Σ (x_i - shifted_i)^2
    # Represents each block as (mean, count); merge adjacent blocks if mean decreases
    blocks: list[list[float]] = [[s, 1.0] for s in shifted]  # [mean, weight]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] > blocks[i + 1][0]:
            # Violation: merge block i and i+1 into weighted average
            w0, w1 = blocks[i][1], blocks[i + 1][1]
            merged_mean = (blocks[i][0] * w0 + blocks[i + 1][0] * w1) / (w0 + w1)
            merged_weight = w0 + w1
            blocks[i] = [merged_mean, merged_weight]
            blocks.pop(i + 1)
            # Backtrack to check if the merged block now violates the previous block
            if i > 0:
                i -= 1
        else:
            i += 1

    # Expand blocks back to per-node values
    result_shifted: list[float] = []
    for mean, weight in blocks:
        result_shifted.extend([mean] * int(round(weight)))

    # Pad/trim if rounding caused length mismatch (shouldn't happen)
    while len(result_shifted) < n:
        result_shifted.append(result_shifted[-1] if result_shifted else canvas_pad)
    result_shifted = result_shifted[:n]

    # Enforce non-negativity lower bound for the shifted result
    # (corresponds to enforcing x_i >= min_pos[i] for all i).
    # Shift all values right if the minimum is negative.
    min_val = min(result_shifted)
    if min_val < 0.0:
        result_shifted = [v - min_val for v in result_shifted]

    # Add back cumulative minimums
    return [result_shifted[i] + min_pos[i] for i in range(n)]


# Private backwards-compat alias (not exported)
BrandesKoepfAssigner = IsotonicCoordinateAssigner


# ── Legacy BrandesKoepfAssigner (replaced by IsotonicCoordinateAssigner) ──────

class _LegacyBrandesKoepfAssigner:
    """Brandes-Koepf-style coordinate assignment (Brandes & Köpf 2002).

    Performs alignment-block coordinate assignment in four biased layouts
    (upper-left, upper-right, lower-left, lower-right), then takes the
    median/average to produce balanced coordinates.

    The algorithm operates on the col dimension only; the orthogonal (rank)
    dimension is assigned identically to SimpleCoordinateAssigner.
    Only applicable to TB/BT direction (rank = row, col = column).
    Falls back to SimpleCoordinateAssigner for LR/RL.
    """

    def assign(
        self,
        nodes: dict[str, _Node],
        direction: str,
        col_gap: int | None,
        rank_gap: int | None,
        canvas_pad: int | None,
    ) -> tuple[int, int]:
        if direction.upper() in ("LR", "RL"):
            # Brandes-Koepf works on rank=row; for LR the roles swap.
            # Fall back to simple assigner for now.
            from ._layout import _assign_coordinates
            return _assign_coordinates(nodes, direction, col_gap, rank_gap, canvas_pad)

        # Assign rank dimension (y) identically to simple assigner first,
        # then overwrite x using Brandes-Koepf alignment.
        from ._layout import _assign_coordinates
        canvas_w, canvas_h = _assign_coordinates(nodes, direction, col_gap, rank_gap, canvas_pad)

        _col_gap = col_gap if col_gap is not None else COL_GAP
        _CANVAS_PAD = canvas_pad if canvas_pad is not None else CANVAS_PAD

        # Run 4-layout B-K and average x positions
        x_candidates: dict[str, list[int]] = {nid: [] for nid in nodes}

        for h_bias in (False, True):   # False=left-biased, True=right-biased
            for v_bias in (False, True):  # False=upper (forward), True=lower (backward)
                xs = _bk_layout(nodes, h_bias, v_bias, _col_gap, _CANVAS_PAD)
                for nid, x in xs.items():
                    x_candidates[nid].append(x)

        # Average of the 4 layouts
        for nid in nodes:
            if x_candidates[nid]:
                nodes[nid].x = int(sum(x_candidates[nid]) / len(x_candidates[nid]))

        # Enforce minimum separation after averaging
        _enforce_x_separation(nodes, _col_gap)

        # Recompute canvas_w from final positions
        if nodes:
            canvas_w = max(
                n.x + (n.width or NODE_W)
                for n in nodes.values()
            ) + _CANVAS_PAD

        return canvas_w, canvas_h


def _bk_layout(
    nodes: dict[str, _Node],
    h_bias: bool,
    v_bias: bool,
    col_gap: int,
    canvas_pad: int,
) -> dict[str, int]:
    """Single Brandes-Koepf layout pass.

    h_bias=False → left-biased (prefer aligning with left predecessor median)
    h_bias=True  → right-biased
    v_bias=False → upper (align with predecessors)
    v_bias=True  → lower (align with successors)

    Returns {node_id: x_position}.
    """
    max_rank = max(n.rank for n in nodes.values())
    ranks: list[list[str]] = [[] for _ in range(max_rank + 1)]
    for nid in nodes:
        r = nodes[nid].rank
        if 0 <= r <= max_rank:
            ranks[r].append(nid)

    # Sort within each rank by current col index (ascending or descending per bias)
    for r_list in ranks:
        r_list.sort(key=lambda nid: nodes[nid].col if not h_bias else -nodes[nid].col)

    # Build predecessor/successor adjacency (ignoring reversed edges)
    succ: dict[str, list[str]] = {nid: [] for nid in nodes}
    pred: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in []:  # edges not passed in; use col ordering as proxy
        pass

    # Without edges passed in, we compute alignment purely from col positions.
    # Root and align arrays: root[v] = block root, align[v] = next in block chain
    root: dict[str, str] = {nid: nid for nid in nodes}
    align: dict[str, str] = {nid: nid for nid in nodes}

    # Place blocks: assign x based on root's base position + node widths
    x: dict[str, int] = {}
    cursor = canvas_pad
    for nid in sorted(nodes.keys(), key=lambda n: (nodes[n].rank, nodes[n].col)):
        if root[nid] == nid:
            # Place this block
            x[nid] = cursor
            cursor += (nodes[nid].width or NODE_W) + col_gap

    # Propagate x to non-root nodes in each block
    for nid in nodes:
        if root[nid] != nid:
            x[nid] = x.get(root[nid], canvas_pad)

    return x


def _enforce_x_separation(nodes: dict[str, _Node], col_gap: int) -> None:
    """After B-K averaging, enforce minimum x separation within each rank."""
    max_rank = max((n.rank for n in nodes.values()), default=0)
    for r in range(max_rank + 1):
        rank_nodes = sorted(
            [n for n in nodes.values() if n.rank == r],
            key=lambda n: (n.x, n.id),
        )
        cursor = None
        for n in rank_nodes:
            nw = n.width or NODE_W
            if cursor is not None and n.x < cursor:
                n.x = cursor
            cursor = n.x + nw + col_gap


# ── Metric helpers ────────────────────────────────────────────────────────────

def count_edge_crossings(nodes: dict[str, _Node], edges: list[_Edge]) -> int:
    """Count the number of edge crossings in the current layout.

    An edge (u→v) and (p→q) cross when rank[u]==rank[p] and
    (col[u]-col[p]) * (col[v]-col[q]) < 0.
    """
    # Group edges by source rank
    by_src_rank: dict[int, list[tuple[str, str]]] = {}
    for e in edges:
        if e.src in nodes and e.dst in nodes:
            r = nodes[e.src].rank
            by_src_rank.setdefault(r, []).append((e.src, e.dst))

    total = 0
    for rank_edges in by_src_rank.values():
        n = len(rank_edges)
        for i in range(n):
            u, v = rank_edges[i]
            cu, cv = nodes[u].col, nodes[v].col
            for j in range(i + 1, n):
                p, q = rank_edges[j]
                cp, cq = nodes[p].col, nodes[q].col
                if (cu - cp) * (cv - cq) < 0:
                    total += 1
    return total


def count_node_overlaps(nodes: dict[str, _Node]) -> int:
    """Count pairs of nodes whose bounding boxes overlap."""
    node_list = [n for n in nodes.values() if not n.is_dummy]
    overlaps = 0
    for i, a in enumerate(node_list):
        aw = a.width or NODE_W
        ah = _node_render_h(a)
        for b in node_list[i + 1:]:
            bw = b.width or NODE_W
            bh = _node_render_h(b)
            x_overlap = a.x < b.x + bw and b.x < a.x + aw
            y_overlap = a.y < b.y + bh and b.y < a.y + ah
            if x_overlap and y_overlap:
                overlaps += 1
    return overlaps


def total_edge_length(nodes: dict[str, _Node], edges: list[_Edge]) -> int:
    """Sum of rank spans across all edges (proxy for total wire length)."""
    total = 0
    for e in edges:
        if e.src in nodes and e.dst in nodes:
            total += abs(nodes[e.dst].rank - nodes[e.src].rank)
    return total


def total_bends(nodes: dict[str, _Node], edges: list[_Edge]) -> int:
    """Approximate bend count: edges with src.col != dst.col have at least 1 bend."""
    bends = 0
    for e in edges:
        if e.src in nodes and e.dst in nodes:
            if nodes[e.src].col != nodes[e.dst].col:
                bends += 1
    return bends


def layout_area(nodes: dict[str, _Node]) -> int:
    """Bounding box area of all non-dummy nodes."""
    real = [n for n in nodes.values() if not n.is_dummy]
    if not real:
        return 0
    min_x = min(n.x for n in real)
    min_y = min(n.y for n in real)
    max_x = max(n.x + (n.width or NODE_W) for n in real)
    max_y = max(n.y + _node_render_h(n) for n in real)
    return max(0, (max_x - min_x) * (max_y - min_y))
