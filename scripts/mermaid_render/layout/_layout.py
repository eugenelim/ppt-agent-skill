from __future__ import annotations

import math
from typing import Optional

from ._constants import (
    _Node, _Edge, _Group,
    NODE_W, NODE_H, COL_GAP, RANK_GAP, CANVAS_PAD,
    NODE_MIN_W, NODE_MAX_W, NODE_HPAD, ICON_COL_WIDTH,
    _DIAMOND_SIZE, _HEXAGON_SIZE, _BAR_W, _BAR_H, _BAR_LABEL_H,
    CROSSING_PASSES, GROUP_CAP,
    _node_render_h, _measure_text_width, _load_icon,
    _node_size_circle, _node_size_diamond, _node_size_hexagon, _node_size_diamond_hex,
    _is_terminal_circle,
    _TITLE_FS, _TITLE_FW,
)

# ── cycle break (iterative DFS back-edge detection) ───────────────────────────

def _break_cycles(nodes: dict[str, _Node], edges: list[_Edge]) -> None:
    """Mark feedback edges reversed_=True using iterative DFS.

    Iterative DFS avoids Python's recursion limit on large graphs. Declaration
    order of nodes in `nodes` is used as the deterministic traversal order so
    the result is stable across equivalent calls.
    """
    adj: dict[str, list[int]] = {nid: [] for nid in nodes}
    for i, e in enumerate(edges):
        if e.src in adj and e.dst in adj:
            adj[e.src].append(i)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    for start in list(nodes.keys()):
        if color[start] != WHITE:
            continue
        # Iterative DFS: stack holds (node, index into its adjacency list)
        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = GRAY
        while stack:
            u, idx = stack[-1]
            if idx < len(adj[u]):
                stack[-1] = (u, idx + 1)
                ei = adj[u][idx]
                v = edges[ei].dst
                if color.get(v) == GRAY:
                    edges[ei].reversed_ = True  # back-edge
                elif color.get(v) == WHITE:
                    color[v] = GRAY
                    stack.append((v, 0))
            else:
                color[u] = BLACK
                stack.pop()


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
        # Insert gap-1 dummy nodes.
        # The label travels on the LAST segment (the one that reaches the real dst)
        # so that when routing merges the chain into one path, the label is present.
        prev_id = e.src
        for k in range(1, gap):
            dummy_id = f"_dummy_{e.src}_{e.dst}_{k}"
            dummy_rank = nodes[e.src].rank + k
            dummy = _Node(id=dummy_id, label="", is_dummy=True, rank=dummy_rank)
            new_nodes[dummy_id] = dummy
            new_edges.append(_Edge(src=prev_id, dst=dummy_id, label="",
                                   style=e.style, orig_src=e.src, orig_dst=e.dst))
            prev_id = dummy_id
        # Copy only target_marker: reproduces the old `arrow=e.arrow` exactly
        # (arrow ≡ target_marker != NONE) while leaving bidir False, matching the
        # pre-refactor behaviour where the reassembled segment never carried bidir.
        new_edges.append(_Edge(src=prev_id, dst=e.dst, label=e.label,
                               style=e.style, target_marker=e.target_marker,
                               orig_src=e.src, orig_dst=e.dst))

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

def _assign_coordinates(
    nodes: dict[str, _Node],
    direction: str = "TB",
    col_gap: int | None = None,
    rank_gap: int | None = None,
    canvas_pad: int | None = None,
) -> tuple[int, int]:
    """Assign x/y pixel positions; return (canvas_width, canvas_height).

    TB (default): rank→Y (row), col→X (column). Row heights are variable based on
    actual node render heights (mirrors LR's variable column heights — dagre parity).
    LR: rank→X (column), col→Y (row) with variable Y pitch based on node height.
    col_gap / rank_gap / canvas_pad override the module constants (%%{init:...}%% config).
    """
    if not nodes:
        _cp = canvas_pad if canvas_pad is not None else CANVAS_PAD
        return 2 * _cp, 2 * _cp

    _col_gap = col_gap if col_gap is not None else COL_GAP
    _rank_gap = rank_gap if rank_gap is not None else RANK_GAP
    _CANVAS_PAD = canvas_pad if canvas_pad is not None else CANVAS_PAD

    is_lr = direction.upper() in ("LR", "RL")
    # Compute per-node display widths from label text (skip special-shape fixed sizes).
    # Icon-left nodes reserve ICON_COL_WIDTH for the icon; add it to the required width
    # so the text column budget (n.width - NODE_HPAD - ICON_COL_WIDTH) can fit the label.
    # For nodes with pipe-separated member rows (class/ER diagrams), the longest member
    # line drives the width so it doesn't overflow the rendered box.
    # Dynamic sizing for circle/diamond/hexagon/bar (must run before text-box width loop)
    for n in nodes.values():
        if n.width == 0 and not n.is_dummy:
            if n.shape in ("circle", "doublecircle"):
                n.width = _node_size_circle(n)
                n.height = n.width  # circle/doublecircle are square
            elif n.shape == "diamond":
                n.width = _node_size_diamond(n)
                n.height = n.width  # diamond is also square
            elif n.shape == "hexagon":
                _hex_w, _hex_h = _node_size_hexagon(n)
                n.width = _hex_w
                n.height = _hex_h  # hexagon has independent width and height
            elif n.shape == "bar":
                n.width = _BAR_W
                n.height = _BAR_H + _BAR_LABEL_H
    _fixed_shapes = {"circle", "doublecircle", "diamond", "hexagon", "bar"}
    for n in nodes.values():
        if n.width == 0 and not n.is_dummy and n.shape not in _fixed_shapes:
            _has_icon = bool(
                (n.icon and _load_icon(n.icon)) or (n.css_class and _load_icon(n.css_class))
            )
            _icon_extra = ICON_COL_WIDTH if _has_icon else 0
            # Use _TITLE_FS=15 for all nodes (including icon nodes) so that width
            # estimation matches _wrap_label, which also uses _TITLE_FS. The renderer
            # emits 14px for icon nodes (slightly less than 15px) — this overestimates
            # slightly, which is safe (extra whitespace rather than clipping).
            _title_line = n.label.split("|")[0].split("\n")[0].strip()
            _label_w = math.ceil(_measure_text_width(_title_line, _TITLE_FS, _TITLE_FW))
            if "|" in n.label:
                # Scan all member lines (the part after the first |)
                _members = n.label.split("|", 1)[1].replace("---", "").split("\n")
                for _ml in _members:
                    _ml = _ml.strip()
                    if _ml:
                        _label_w = max(_label_w, math.ceil(_measure_text_width(_ml, _TITLE_FS, _TITLE_FW)))
            # Cap only the text portion; icon column is additive and never capped.
            _text_w = min(max(NODE_MIN_W, _label_w + NODE_HPAD), NODE_MAX_W)
            n.width = _text_w + _icon_extra
    # Populate n.height for all non-dummy nodes (must run after widths are set)
    for n in nodes.values():
        if not n.is_dummy:
            n.height = _node_render_h(n)
    if not is_lr:
        # Per-column widths: each column uses the max width of its own non-dummy nodes.
        all_cols = sorted({n.col for n in nodes.values()})
        col_width: dict[int, int] = {
            c: max(
                (n.width for n in nodes.values() if n.col == c and not n.is_dummy and n.width > 0),
                default=NODE_W,
            )
            for c in all_cols
        }
        col_left: dict[int, int] = {}
        _cursor = _CANVAS_PAD
        for c in all_cols:
            col_left[c] = _cursor
            _cursor += col_width[c] + _col_gap

        for n in nodes.values():
            cw = col_width.get(n.col, NODE_W)
            nw = n.width or cw  # dummy has width=0 → nw=cw → centering_offset=0 → x=col_left
            if _is_terminal_circle(n):
                # Terminal circles start at col_left; _strategies.py adds _circ_shift to center
                # them (same contract as before dynamic sizing — do not double-center here).
                n.x = col_left[n.col]
            else:
                n.x = col_left[n.col] + (cw - nw) // 2

        # Pull dummy nodes (routing waypoints) tightly against their sibling column.
        # Without this, a dummy assigned to col 1 sits ~290px from col-0 nodes,
        # creating very wide horizontal sweeps in the rendered edge paths.
        # Strategy: move each dummy to just right of the rightmost sibling column's right edge.
        _DUMMY_MARGIN = 20
        for n in nodes.values():
            if not n.is_dummy:
                continue
            _siblings = [nn for nn in nodes.values() if nn.rank == n.rank and not nn.is_dummy]
            if _siblings:
                _max_sib_col = max(nn.col for nn in _siblings)
                _slot_right = col_left[_max_sib_col] + col_width.get(_max_sib_col, NODE_W)
                n.x = _slot_right + _DUMMY_MARGIN

        # Variable rank heights: accumulate Y positions by actual max node height per rank.
        # Nodes shorter than rank_h are centered vertically within the row.
        rank_to_nodes: dict[int, list] = {}
        for n in nodes.values():
            rank_to_nodes.setdefault(n.rank, []).append(n)
        y_cursor = _CANVAS_PAD
        for rank in sorted(rank_to_nodes):
            rank_h = max(_node_render_h(n) for n in rank_to_nodes[rank])
            for n in rank_to_nodes[rank]:
                n.y = y_cursor + (rank_h - _node_render_h(n)) // 2
            y_cursor += rank_h + _rank_gap

        # Recompute canvas_w using actual node x positions (dummies may have shifted)
        max_x_right = max(n.x + (n.width or col_width.get(n.col, NODE_W)) for n in nodes.values())
        canvas_w = max_x_right + _CANVAS_PAD
        canvas_h = y_cursor + _CANVAS_PAD - _rank_gap
        return canvas_w, canvas_h

    # LR: per-rank x-positions using each rank's own max node width.
    all_ranks = sorted({n.rank for n in nodes.values()})
    rank_width: dict[int, int] = {
        r: max(
            (n.width for n in nodes.values() if n.rank == r and not n.is_dummy and n.width > 0),
            default=NODE_W,
        )
        for r in all_ranks
    }
    rank_left: dict[int, int] = {}
    _cursor = _CANVAS_PAD
    for r in all_ranks:
        rank_left[r] = _cursor
        _cursor += rank_width[r] + _rank_gap
    for n in nodes.values():
        n.x = rank_left.get(n.rank, _CANVAS_PAD)

    # Group nodes by col, accumulate Y positions top-to-bottom.
    # Nodes shorter than col_h are centered vertically within the band.
    col_to_nodes: dict[int, list] = {}
    for n in nodes.values():
        col_to_nodes.setdefault(n.col, []).append(n)
    y_cursor = _CANVAS_PAD
    for col in sorted(col_to_nodes):
        col_h = max(_node_render_h(n) for n in col_to_nodes[col])
        for n in col_to_nodes[col]:
            n.y = y_cursor + (col_h - _node_render_h(n)) // 2
        y_cursor += col_h + _col_gap

    canvas_w = _cursor - _rank_gap + _CANVAS_PAD
    canvas_h = y_cursor + _CANVAS_PAD - _col_gap
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
        sorted_gids = sorted(rng, key=lambda g: rng[g][0])  # type: ignore[index]  # by col_min
        moved = False
        for i, g1 in enumerate(sorted_gids):
            c1_lo, c1_hi, r1_lo, r1_hi = rng[g1]  # type: ignore[misc]
            for g2 in sorted_gids[i + 1:]:
                if _is_nested(g1, g2):
                    continue
                c2_lo, c2_hi, r2_lo, r2_hi = rng[g2]  # type: ignore[misc]
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


# ── fan-in barycenter centering ───────────────────────────────────────────────

def _center_isolated_nodes(nodes: "dict", edges: "list") -> None:
    """Center single-node TB ranks at the predecessor barycenter in pixel space.

    When exactly one non-dummy node occupies a rank and it has two or more real
    predecessors, the column-grid assignment always places it at column 0, which
    biases it toward the leftmost predecessor.  Reposition it so its centre aligns
    with the x-barycenter of its predecessors (fan-in case: e.g. B & C & D → E).

    Collects all (node, new_x) pairs first, then applies them — so the result is
    independent of dict iteration order when multiple eligible nodes exist.
    """
    updates: "list[tuple]" = []
    for nid, n in nodes.items():
        if n.is_dummy:
            continue
        same_rank = [nn for nn in nodes.values() if nn.rank == n.rank and not nn.is_dummy]
        if len(same_rank) != 1:
            continue
        preds: list = []
        seen: set = set()
        for e in edges:
            dst = e.orig_dst if e.orig_dst else e.dst
            src = e.orig_src if e.orig_src else e.src
            if dst == nid and not e.reversed_ and src in nodes and not nodes[src].is_dummy and src not in seen:
                seen.add(src)
                preds.append(src)
        if len(preds) < 2:
            continue
        # Use n.width (set by _assign_coordinates) as effective rendered width.
        bary_x = sum(nodes[p].x + (nodes[p].width or NODE_W) // 2 for p in preds) / len(preds)
        nw = n.width or NODE_W
        updates.append((n, max(0, int(round(bary_x)) - nw // 2)))
    for n, new_x in updates:
        n.x = new_x


# ── inner-direction recursive position fixup ─────────────────────────────────

def _apply_inner_direction_positions(
    nodes: dict[str, _Node],
    edges: list[_Edge],
    groups: dict[str, _Group],
    outer_direction: str,
    col_gap: int | None = None,
) -> None:
    """Post-process inner-direction subgraph member positions after outer layout.

    Replaces the rank-flattening hack: after `_assign_coordinates` places all
    nodes in pixel space, for each group whose declared direction differs from
    the outer direction, re-orders its members' x (or y) positions according to
    the topological ordering of intra-group edges rather than leaving them in
    bary-sort order.

    TB outer + LR inner: members share the same y (from rank-flattening); this
    re-assigns x positions so data-flow goes left-to-right within the group.

    LR outer + TB inner: members share the same x; re-assigns y positions.

    Processes groups bottom-up (leaf groups first) so nested inner groups get
    positioned before their parents pick up their corrected positions.
    """
    _col_gap = col_gap if col_gap is not None else COL_GAP
    is_outer_tb = outer_direction.upper() in ("TB", "TD")

    def _topo_order(member_ids: list[str], intra_edges: list[tuple[str, str]]) -> list[str]:
        """Topological sort of members by intra-group forward-edge flow."""
        in_degree: dict[str, int] = {m: 0 for m in member_ids}
        adj: dict[str, list[str]] = {m: [] for m in member_ids}
        for src, dst in intra_edges:
            adj[src].append(dst)
            in_degree[dst] += 1
        queue = [m for m in member_ids if in_degree[m] == 0]
        result: list[str] = []
        while queue:
            queue.sort(key=lambda n: nodes[n].x if is_outer_tb else nodes[n].y)
            cur = queue.pop(0)
            result.append(cur)
            for nb in adj[cur]:
                in_degree[nb] -= 1
                if in_degree[nb] == 0:
                    queue.append(nb)
        # Append any nodes not reached (cycles) in stable order
        seen = set(result)
        for m in member_ids:
            if m not in seen:
                result.append(m)
        return result

    # Build group tree to process bottom-up
    def _is_leaf_group(gid: str) -> bool:
        return not any(g.parent_group == gid for g in groups.values())

    def _process_group(gid: str) -> None:
        grp = groups[gid]
        if not grp.members or not grp.direction:
            return
        inner_dir = grp.direction.upper()
        if is_outer_tb and inner_dir not in ("LR", "RL"):
            return
        if not is_outer_tb and inner_dir not in ("TB", "TD"):
            return

        member_set = set(grp.members)
        member_ids = [m for m in grp.members if m in nodes and not nodes[m].is_dummy]
        if len(member_ids) < 2:
            return

        intra = [
            (e.src, e.dst) for e in edges
            if e.src in member_set and e.dst in member_set and not e.reversed_
        ]
        ordered = _topo_order(member_ids, intra)
        if inner_dir in ("RL", "BT"):
            ordered = list(reversed(ordered))

        if is_outer_tb:
            # Re-assign x positions; y stays the same (from rank-flattening)
            start_x = min(nodes[m].x for m in member_ids)
            for i, m in enumerate(ordered):
                nw = nodes[m].width or NODE_W
                nodes[m].x = start_x + i * (nw + _col_gap)
        else:
            # Re-assign y positions; x stays the same
            start_y = min(nodes[m].y for m in member_ids)
            for i, m in enumerate(ordered):
                nh = _node_render_h(nodes[m])
                nodes[m].y = start_y + i * (nh + _col_gap)

    # Process groups: leaf groups first (bottom-up)
    all_gids = list(groups.keys())
    # Leaf groups first
    leaves = [g for g in all_gids if _is_leaf_group(g)]
    non_leaves = [g for g in all_gids if not _is_leaf_group(g)]
    for gid in leaves + non_leaves:
        _process_group(gid)
