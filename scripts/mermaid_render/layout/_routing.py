from __future__ import annotations

import heapq
import math

from ._constants import (
    _Node, _Edge,
    NODE_W, NODE_H, SELF_LOOP_DX, MIN_FAN_STEP,
    GROUP_PAD_Y_TOP,
    _node_render_h, _is_terminal_circle, _TERMINAL_NODE_SIZE,
)


def _node_render_w(n: "_Node") -> int:
    """Effective rendered width for routing exit/entry x-coordinate computation."""
    return _TERMINAL_NODE_SIZE if _is_terminal_circle(n) else NODE_W


# ── A* obstacle-avoiding orthogonal router ────────────────────────────────────

def _build_routing_grid(
    nodes: dict,
    canvas_w: int,
) -> "tuple[list[int], list[int]]":
    """Build sparse routing grid from node AABB boundaries.

    Grid lines are placed at node edges and 8 px outside each edge.
    This guarantees routing lanes in the inter-node gaps without requiring
    a dense pixel grid.
    """
    xs: set[int] = {0, canvas_w}
    ys: set[int] = {0}
    for n in nodes.values():
        if n.is_dummy:
            continue
        nw, nh = _node_render_w(n), _node_render_h(n)
        for off in (-8, 0, nw // 2, nw, nw + 8):
            xs.add(n.x + off)
        for off in (-8, 0, nh // 2, nh, nh + 8):
            ys.add(n.y + off)
    # Clamp negative coordinates
    return sorted(x for x in xs if x >= -8), sorted(y for y in ys if y >= -8)


def _blocked_segs(
    grid_xs: "list[int]",
    grid_ys: "list[int]",
    obstacles: list,
) -> "set[tuple[int, int, int, int]]":
    """Precompute set of (xi, yi, xi2, yi2) grid-index tuples for blocked segments.

    A segment is blocked when it passes through any obstacle AABB interior
    (more than 2 px inside a boundary in the perpendicular direction).
    """
    CLEAR = 2
    blocked: set = set()
    nx, ny = len(grid_xs), len(grid_ys)

    # Horizontal segments
    for yi in range(ny):
        y = grid_ys[yi]
        for xi in range(nx - 1):
            xl, xr = grid_xs[xi], grid_xs[xi + 1]
            for ox1, oy1, ox2, oy2 in obstacles:
                if oy1 + CLEAR < y < oy2 - CLEAR:
                    if ox1 < xr and ox2 > xl:
                        blocked.add((xi, yi, xi + 1, yi))
                        break

    # Vertical segments
    for xi in range(nx):
        x = grid_xs[xi]
        for yi in range(ny - 1):
            yt, yb = grid_ys[yi], grid_ys[yi + 1]
            for ox1, oy1, ox2, oy2 in obstacles:
                if ox1 + CLEAR < x < ox2 - CLEAR:
                    if oy1 < yb and oy2 > yt:
                        blocked.add((xi, yi, xi, yi + 1))
                        break

    return blocked


def _astar_route(
    sx: int, sy: int,
    dx: int, dy: int,
    grid_xs: "list[int]",
    grid_ys: "list[int]",
    blocked: "set[tuple]",
) -> "list[tuple[int, int]]":
    """Obstacle-avoiding A* on sparse orthogonal routing grid.

    Cost function: total Manhattan length + 200 per 90° bend.
    Heuristic: Manhattan distance to goal (admissible).
    Returns a list of (x, y) waypoints with collinear points removed.
    The caller should replace waypoints[0] and waypoints[-1] with the
    exact port coordinates to restore sub-grid precision.
    """
    BEND = 200
    nx, ny = len(grid_xs), len(grid_ys)

    def _snap(val: int, arr: "list[int]") -> int:
        return min(range(len(arr)), key=lambda i: abs(arr[i] - val))

    sxi, syi = _snap(sx, grid_xs), _snap(sy, grid_ys)
    dxi, dyi = _snap(dx, grid_xs), _snap(dy, grid_ys)

    if sxi == dxi and syi == dyi:
        return [(sx, sy)]

    # State: (xi, yi, dir) — dir: 0=horizontal, 1=vertical
    _MOVES = [(-1, 0, 0), (1, 0, 0), (0, -1, 1), (0, 1, 1)]
    INF = float("inf")
    dist: dict = {}
    prev: dict = {}
    heap: list = []
    ctr = 0

    for d0 in (0, 1):
        h0 = abs(grid_xs[dxi] - grid_xs[sxi]) + abs(grid_ys[dyi] - grid_ys[syi])
        dist[(sxi, syi, d0)] = 0
        prev[(sxi, syi, d0)] = None
        heapq.heappush(heap, (h0, ctr, sxi, syi, d0))
        ctr += 1

    while heap:
        f, _, xi, yi, d = heapq.heappop(heap)
        state = (xi, yi, d)
        g = dist.get(state, INF)
        # Discard stale heap entries
        hval = abs(grid_xs[dxi] - grid_xs[xi]) + abs(grid_ys[dyi] - grid_ys[yi])
        if f > g + hval + 1e-6:
            continue

        if xi == dxi and yi == dyi:
            pts: list = []
            s: "tuple | None" = state
            while s is not None:
                pts.append((grid_xs[s[0]], grid_ys[s[1]]))
                s = prev[s]
            pts.reverse()
            return _simplify_waypoints(pts)

        for ddxi, ddyi, nd in _MOVES:
            nxi, nyi = xi + ddxi, yi + ddyi
            if not (0 <= nxi < nx and 0 <= nyi < ny):
                continue
            seg = (min(xi, nxi), min(yi, nyi), max(xi, nxi), max(yi, nyi))
            if seg in blocked:
                continue
            seg_len = abs(grid_xs[nxi] - grid_xs[xi]) + abs(grid_ys[nyi] - grid_ys[yi])
            ng = g + seg_len + (BEND if nd != d else 0)
            ns = (nxi, nyi, nd)
            if ng < dist.get(ns, INF):
                dist[ns] = ng
                prev[ns] = state
                nh = abs(grid_xs[dxi] - grid_xs[nxi]) + abs(grid_ys[dyi] - grid_ys[nyi])
                heapq.heappush(heap, (ng + nh, ctr, nxi, nyi, nd))
                ctr += 1

    # No path found — direct fallback
    return [(sx, sy), (dx, dy)]


def _simplify_waypoints(pts: list) -> list:
    """Remove collinear intermediate waypoints."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        px, py = pts[i - 1]
        cx, cy = pts[i]
        nx_, ny_ = pts[i + 1]
        if not ((px == cx == nx_) or (py == cy == ny_)):
            out.append(pts[i])
    out.append(pts[-1])
    return out


def _try_3seg_clear(
    pts: "list[tuple[int,int]]",
    obstacles: list,
    clearance: int = 2,
) -> bool:
    """Return True if every segment of pts (orthogonal path) is obstacle-free."""
    for i in range(len(pts) - 1):
        x1, y1 = int(pts[i][0]), int(pts[i][1])
        x2, y2 = int(pts[i + 1][0]), int(pts[i + 1][1])
        for ox1, oy1, ox2, oy2 in obstacles:
            if x1 == x2:  # vertical segment
                if ox1 + clearance < x1 < ox2 - clearance:
                    if oy1 < max(y1, y2) and oy2 > min(y1, y2):
                        return False
            else:  # horizontal segment
                if oy1 + clearance < y1 < oy2 - clearance:
                    if ox1 < max(x1, x2) and ox2 > min(x1, x2):
                        return False
    return True


def _label_on_longest(
    pts: list,
    label: str,
    canvas_w: int,
    obstacles: list,
    placed: list,
    y_range: "tuple[int,int] | None" = None,
) -> "tuple[int, int]":
    """Place label chip centred on the longest segment of the path."""
    if not pts:
        return 0, 0
    if len(pts) < 2:
        return pts[0][0], pts[0][1]

    # Find longest segment
    best_p1, best_p2 = pts[0], pts[1]
    best_len = 0
    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i + 1]
        seg_len = abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])
        if seg_len > best_len:
            best_len = seg_len
            best_p1, best_p2 = p1, p2

    mid_x = (best_p1[0] + best_p2[0]) // 2
    mid_y = (best_p1[1] + best_p2[1]) // 2
    w = _est_label_w(label)
    H = _LABEL_CHIP_H
    # Candidates: above and below the segment midpoint, with offsets
    cands = [
        (mid_x - w // 2,          mid_y - H - 4),
        (mid_x - w // 2,          mid_y + 4),
        (mid_x - w // 2 + 20,     mid_y - H - 4),
        (mid_x - w // 2 - 20,     mid_y - H - 4),
        (mid_x - w // 2 + 20,     mid_y + 4),
    ]
    return _best_label_pos(cands, label, obstacles, placed, canvas_w, y_range=y_range)


# ── diamond edge clipping ─────────────────────────────────────────────────────

def _clip_to_diamond(
    tip_x: float, tip_y: float,
    cx: float, cy: float,
    w: float, h: float,
    dx: float, dy: float,
) -> tuple[float, float]:
    """Return the point on the diamond outline in the direction from center to tip.

    Diamond vertices: top=(cx,cy-h/2), right=(cx+w/2,cy), bottom=(cx,cy+h/2),
    left=(cx-w/2,cy). The intersection is computed analytically via the Manhattan
    metric: cast from center outward along (tip-center) and find the face crossing.
    Falls back to the nearest vertex when tip is at the center.
    (dx,dy) is a hint for callers but the computation uses tip position.
    """
    hw, hh = w / 2.0, h / 2.0
    odx = tip_x - cx
    ody = tip_y - cy
    length = math.hypot(odx, ody)
    if length < 1e-9:
        vertices: list[tuple[float, float]] = [
            (cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)
        ]
        return min(vertices, key=lambda v: (v[0] - tip_x) ** 2 + (v[1] - tip_y) ** 2)
    ndx, ndy = odx / length, ody / length
    denom = abs(ndx) / hw + abs(ndy) / hh
    if denom < 1e-9:
        return float(cx), float(cy - hh)
    t = 1.0 / denom
    return float(cx + ndx * t), float(cy + ndy * t)


# ── edge routing ──────────────────────────────────────────────────────────────

def _arrowhead(tip_x: int, tip_y: int, dx: float, dy: float,
               back: int = 8, half_w: int = 4) -> str:
    """Return SVG polygon points string for an arrowhead tip at (tip_x, tip_y).

    back    — distance from tip to base (px). Normal edges: 8, thick: 10, lifeline: 10.
    half_w  — half-width at base (px).       Normal edges: 4, thick:  5, lifeline:  6.
    """
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    px, py = -uy, ux  # perpendicular
    bx = int(tip_x - ux * back)
    by = int(tip_y - uy * back)
    p1x = int(bx + px * half_w)
    p1y = int(by + py * half_w)
    p2x = int(bx - px * half_w)
    p2y = int(by - py * half_w)
    return f"{tip_x},{tip_y} {p1x},{p1y} {p2x},{p2y}"


def _smooth_orthogonal_path(pts: list[tuple[int, int]], r: int = 10) -> str:
    """Build an SVG path through orthogonal waypoints with rounded corners (radius r).

    Each interior corner is replaced by a quadratic bezier arc: a straight line
    segment to (r px before the corner), a Q command through the corner to
    (r px after the corner), then the next segment.  Terminal points are reached
    with a plain L command.  Works for any sequence of ≥2 waypoints.
    """
    if len(pts) < 2:
        return ""
    d = f"M {pts[0][0]} {pts[0][1]}"
    for i in range(1, len(pts)):
        prev = pts[i - 1]
        curr = pts[i]
        nxt = pts[i + 1] if i < len(pts) - 1 else None
        if nxt is None:
            d += f" L {curr[0]} {curr[1]}"
        else:
            dx1 = curr[0] - prev[0]
            dy1 = curr[1] - prev[1]
            len1 = max(math.hypot(dx1, dy1), 0.001)
            # arc-start: r px before the corner along the incoming segment
            ax = curr[0] - dx1 / len1 * min(r, len1 / 2)
            ay = curr[1] - dy1 / len1 * min(r, len1 / 2)
            dx2 = nxt[0] - curr[0]
            dy2 = nxt[1] - curr[1]
            len2 = max(math.hypot(dx2, dy2), 0.001)
            # arc-end: r px after the corner along the outgoing segment
            bx = curr[0] + dx2 / len2 * min(r, len2 / 2)
            by_ = curr[1] + dy2 / len2 * min(r, len2 / 2)
            d += (f" L {ax:.1f} {ay:.1f}"
                  f" Q {curr[0]} {curr[1]} {bx:.1f} {by_:.1f}")
    return d


def _fan_offset(index: int, total: int, node_w: int = NODE_W, pad: int = 16) -> int:
    """Distribute fan-in/fan-out endpoints across node edge (spec §Step6).

    Endpoints are spaced at least MIN_FAN_STEP px apart and centred on the node
    midpoint so parallel edges stay visually separated even on short nodes.
    """
    if total <= 1:
        return node_w // 2
    usable = node_w - 2 * pad
    step = max(usable // (total + 1), MIN_FAN_STEP)
    # Centre the fan: span = step * (total-1), start = mid - span/2.
    centre = node_w // 2
    start = centre - step * (total - 1) // 2
    return start + step * index


_LABEL_PERP = 20  # perpendicular offset for edge labels (px)

# ── edge label placement ──────────────────────────────────────────────────────

_LABEL_CHIP_H = 17    # chip height: 12px font + 2×padding + 1px border ≈ 17px
_LABEL_CHAR_W = 6.8   # average char width at 12px Inter regular (empirical)


def _est_label_w(text: str) -> int:
    return min(450, max(30, int(len(text) * _LABEL_CHAR_W)))


def _label_chip_bbox(lx: int, ly: int, text: str) -> tuple:
    """Bbox (x1,y1,x2,y2) for a chip placed at left=lx, bottom=ly (CSS translateY(-100%))."""
    return (lx, ly - _LABEL_CHIP_H, lx + _est_label_w(text), ly)


def _overlap_area(a: tuple, b: tuple, margin: int = 8) -> float:
    """Intersection area of two bboxes each expanded outward by `margin` px.

    Default margin raised to 8px (was 4) to give labels more clearance from node
    borders at the current 11px chip size — prevents labels from touching card edges.
    """
    ox = max(0.0, min(a[2] + margin, b[2] + margin) - max(a[0] - margin, b[0] - margin))
    oy = max(0.0, min(a[3] + margin, b[3] + margin) - max(a[1] - margin, b[1] - margin))
    return ox * oy


def _best_label_pos(
    candidates: list,
    label: str,
    obstacles: list,
    placed: list,
    canvas_w: int,
    y_range: "tuple[int,int] | None" = None,
) -> tuple:
    """Pick the (lx, ly) from candidates with minimum total overlap.

    Checks against pre-built node/group obstacle bboxes plus already-placed
    label chips so label density is distributed rather than stacked.
    Off-canvas placements (chip_top < 0) are strongly penalised so the
    algorithm never greedily picks clear-but-invisible negative-y positions.

    y_range: (y_lo, y_hi) defines the edge's natural vertical span.  Positions
    above y_lo are penalised at 200px/px to prevent labels from escaping above
    group containers; positions below y_hi get a softer 10px/px nudge.
    """
    w = _est_label_w(label)
    all_obs = obstacles + placed
    best_lx, best_ly = candidates[0][0], candidates[0][1]
    best_score = float("inf")
    for raw_lx, ly in candidates:
        lx = max(4, min(canvas_w - w - 4, raw_lx))
        bbox = _label_chip_bbox(lx, ly, label)
        score = sum(_overlap_area(bbox, obs) for obs in all_obs)
        chip_top = ly - _LABEL_CHIP_H
        if chip_top < 0:
            score += (-chip_top) * 5000
        # Penalise positions that required clamping (raw_lx was off-canvas).
        clamp_dist = abs(raw_lx - lx)
        if clamp_dist > 0:
            score += clamp_dist * 80
        # Penalise positions outside the edge's natural y span.  Heavy above
        # (prevents escape above group boundaries) and soft below.
        if y_range is not None:
            y_lo, y_hi = y_range
            if ly < y_lo:
                score += (y_lo - ly) * 200
            elif ly > y_hi:
                score += (ly - y_hi) * 10
        if score < best_score:
            best_score, best_lx, best_ly = score, lx, ly
        if score == 0:
            break
    placed.append(_label_chip_bbox(best_lx, best_ly, label))
    return best_lx, best_ly


def _route_edges(nodes: dict[str, _Node], edges: list[_Edge], canvas_w: int,
                 direction: str = "TB",
                 group_bboxes: "dict | None" = None) -> list[dict]:
    """Return list of edge render specs (path_d, arrowhead_pts, label, style, lx, ly, rot)."""
    is_lr = direction.upper() in ("LR", "RL")

    # Count fan-in/fan-out per node (for endpoint distribution)
    fan_in: dict[str, list[str]] = {nid: [] for nid in nodes}
    fan_out: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:
        if e.src in nodes and e.dst in nodes and not e.reversed_:
            fan_in[e.dst].append(e.src)
            fan_out[e.src].append(e.dst)

    # Obstacle bboxes for label placement: node cards + group title strips.
    # Full group bboxes push labels above all groups (clear y < CANVAS_PAD area),
    # so only the title strip (top GROUP_PAD_Y_TOP px) is an obstacle — enough to
    # prevent edge labels from landing on group label text.
    obstacles: list = [
        (n.x, n.y, n.x + _node_render_w(n), n.y + _node_render_h(n))
        for n in nodes.values() if not n.is_dummy
    ]
    if group_bboxes:
        obstacles += [
            (int(x1), int(y1), int(x2), int(y1) + GROUP_PAD_Y_TOP)
            for x1, y1, x2, _y2 in group_bboxes.values()
        ]
    placed_labels: list = []  # accumulates placed chip bboxes to prevent inter-label collision

    # ── Routing grid (A* obstacle avoidance) ─────────────────────────────────
    # Build once per route_edges call; used by forward edges that clip obstacles.
    _grid_xs, _grid_ys = _build_routing_grid(nodes, canvas_w)
    # Node-body obstacles only (not group title strips) — group strips are narrow
    # enough that routing over them is acceptable.
    _routing_obs = [(n.x, n.y, n.x + _node_render_w(n), n.y + _node_render_h(n))
                    for n in nodes.values() if not n.is_dummy]
    _blocked = _blocked_segs(_grid_xs, _grid_ys, _routing_obs)

    # Right-lane x: always clears the rightmost node + group container border
    non_dummy = [n for n in nodes.values() if not n.is_dummy]
    right_lane_x = (max(n.x + _node_render_w(n) for n in non_dummy) if non_dummy else canvas_w) + 32

    # LR bottom-lane y: clears the tallest node's bottom + margin
    if is_lr and non_dummy:
        bottom_lane_y = max(n.y + _node_render_h(n) for n in non_dummy) + 32
    else:
        bottom_lane_y = 0

    # Build back-edge lane assignments so each back-edge uses its own stagger lane,
    # preventing multiple back-edges from collapsing onto the same routing lane.
    back_edge_lane: dict[int, int] = {}
    _be_count = 0
    for _i, _e in enumerate(edges):
        if _e.src not in nodes or _e.dst not in nodes or _e.src == _e.dst:
            continue
        _rg = nodes[_e.dst].rank - nodes[_e.src].rank
        if _e.reversed_ or _rg < 0 or _rg > 1:
            back_edge_lane[_i] = _be_count
            _be_count += 1

    # Build parallel-edge indices so labels for A→B, A→B can be staggered.
    _par_count: dict[tuple, int] = {}
    parallel_edge_idx: dict[int, int] = {}
    for _i, _e in enumerate(edges):
        _key = (_e.src, _e.dst)
        parallel_edge_idx[_i] = _par_count.get(_key, 0)
        _par_count[_key] = _par_count.get(_key, 0) + 1

    result: list[dict] = []
    for edge_i, e in enumerate(edges):
        if e.src not in nodes or e.dst not in nodes:
            continue
        s = nodes[e.src]
        d = nodes[e.dst]
        # thick edges get a larger arrowhead; all other edges get a slightly larger
        # head than the default (8/4) for visibility at small zoom levels.
        if e.style == "thick":
            ah_kw: dict = {"back": 11, "half_w": 5}
            _mid = "arrow-thick"
        elif e.style.startswith("cls-"):
            ah_kw = {"back": 9, "half_w": 4}
            # Class markers: strip optional "-dotted" suffix to get the marker id
            _mid = e.style.replace("-dotted", "")
        else:
            ah_kw = {"back": 9, "half_w": 4}
            _mid = "arrow-open" if e.style == "dotted" else "arrow-normal"
        marker_id: str | None = _mid if e.arrow else None

        # Self-loop
        if e.src == e.dst:
            lx = s.x + _node_render_w(s)
            ty = s.y
            by_ = s.y + _node_render_h(s)
            _sl_inset = max(6, min(12, (by_ - ty) // 4))
            path = (f"M {lx} {ty + _sl_inset} "
                    f"C {lx + SELF_LOOP_DX} {ty} {lx + SELF_LOOP_DX} {by_} "
                    f"{lx} {by_ - _sl_inset}")
            tip_x, tip_y = lx, by_ - _sl_inset
            ah = _arrowhead(tip_x, tip_y, -1, 0, **ah_kw) if e.arrow else None
            mid_y = (ty + by_) // 2
            if e.label:
                cands = [
                    (tip_x + 14, mid_y),
                    (tip_x + 14, ty - _LABEL_CHIP_H - 4),
                    (tip_x + 14, by_ + _LABEL_CHIP_H + 4),
                ]
                llx, lly = _best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w)
            else:
                llx, lly = tip_x + 14, mid_y
            result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                           "lx": llx, "ly": lly, "rot": 0, "marker_id": marker_id,
                           "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css})
            continue

        rank_gap = d.rank - s.rank

        # Back-edge → right-lane (TB) or bottom-lane (LR) smooth path.
        # Use geometry to detect direction: works for both Sugiyama (rank-based coords)
        # and ELK (which places long forward edges without dummy nodes).
        # A forward edge goes RIGHT (LR) or DOWN (TB); anything else is a back edge.
        if is_lr:
            _goes_back = (d.x + NODE_W // 2) < s.x  # dst center left of src left
        else:
            _goes_back = (d.y + _node_render_h(d) // 2) < s.y  # dst center above src top
        if e.reversed_ or _goes_back:
            be_lane = back_edge_lane.get(edge_i, 0)
            if is_lr:
                # Right-to-left crossing: source LEFT edge is past destination RIGHT edge.
                # Route directly (left-exit → midpoint → right-enter) instead of
                # the bottom lane, which adds unnecessary vertical canvas space.
                if not e.reversed_ and s.x >= d.x + NODE_W:
                    out_list = fan_out[e.src]
                    out_idx = out_list.index(e.dst) if e.dst in out_list else 0
                    out_off = _fan_offset(out_idx, len(out_list), node_w=_node_render_h(s))
                    in_list = fan_in[e.dst]
                    in_idx = in_list.index(e.src) if e.src in in_list else 0
                    in_off = _fan_offset(in_idx, len(in_list), node_w=_node_render_h(d))
                    x1 = s.x               # exit from LEFT side of source
                    y1 = s.y + out_off
                    x2 = d.x + _node_render_w(d)   # enter RIGHT side of destination
                    y2 = d.y + in_off
                    mid_x = (x1 + x2) // 2
                    path = _smooth_orthogonal_path(
                        [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]
                    )
                    ah = _arrowhead(x2, y2, -1, 0, **ah_kw) if e.arrow else None
                    if e.label:
                        H = _LABEL_CHIP_H
                        w = _est_label_w(e.label)
                        cands = [
                            (x1 - w - 8,         int(y1) - 12),
                            (x1 - w - 8,         int(y1) + H + 4),
                            (mid_x - w // 2,     min(int(y1), int(y2)) - 12),
                            (mid_x - w // 2,     max(int(y1), int(y2)) + H + 4),
                            (int(x2) + 8,        int(y2) - 12),
                            (int(x2) + 8,        int(y2) + H + 4),
                        ]
                        llx, lly = _best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w)
                    else:
                        llx, lly = max(0, x1 - 164), int(y1) - 12
                    result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                                   "lx": llx, "ly": lly, "rot": 0, "marker_id": marker_id,
                                   "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css})
                else:
                    lane_y = bottom_lane_y + 32 * be_lane
                    sx = s.x + _node_render_w(s) // 2
                    sy = s.y + _node_render_h(s)
                    dx_ = d.x + _node_render_w(d) // 2
                    dy_ = d.y + _node_render_h(d)
                    path = _smooth_orthogonal_path(
                        [(sx, sy), (sx, lane_y), (dx_, lane_y), (dx_, dy_)]
                    )
                    ah = _arrowhead(dx_, dy_, 0, -1, **ah_kw) if e.arrow else None
                    if e.label:
                        H = _LABEL_CHIP_H
                        w = _est_label_w(e.label)
                        mid = (sx + dx_) // 2
                        cands = [
                            (mid - w // 2,  lane_y - H - 4),
                            (mid - w // 2,  lane_y + H + 4),
                            (sx + 8,        lane_y - H - 4),
                            (dx_ + 8,       lane_y - H - 4),
                        ]
                        llx, lly = _best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w)
                    else:
                        llx, lly = (sx + dx_) // 2, lane_y + 4
                    result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                                   "lx": llx, "ly": lly, "rot": 0, "marker_id": marker_id,
                                   "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css})
            else:
                lane_x = right_lane_x + 32 * be_lane
                sx = s.x + _node_render_w(s)
                sy = s.y + _node_render_h(s) // 2
                dx_ = d.x + _node_render_w(d)
                dy_ = d.y + _node_render_h(d) // 2
                path = _smooth_orthogonal_path(
                    [(sx, sy), (lane_x, sy), (lane_x, dy_), (dx_, dy_)]
                )
                ah = _arrowhead(dx_, dy_, -1, 0, **ah_kw) if e.arrow else None
                if e.label:
                    H = _LABEL_CHIP_H
                    w = _est_label_w(e.label)
                    mid_y = (sy + dy_) // 2
                    cands = [
                        (lane_x + 4,      mid_y),
                        (lane_x - w - 4,  mid_y),
                        (lane_x + 4,      sy + H + 4),
                        (lane_x + 4,      dy_ - H - 4),
                    ]
                    llx, lly = _best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w)
                else:
                    llx, lly = lane_x + 4, (sy + dy_) // 2
                result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                               "lx": llx, "ly": lly, "rot": 0, "marker_id": marker_id,
                               "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css})
            continue

        if is_lr:
            # LR forward edge: orthogonal path right-of-src to left-of-dst
            out_list = fan_out[e.src]
            out_idx = out_list.index(e.dst) if e.dst in out_list else 0
            out_offset = _fan_offset(out_idx, len(out_list), node_w=_node_render_h(s))

            in_list = fan_in[e.dst]
            in_idx = in_list.index(e.src) if e.src in in_list else 0
            in_offset = _fan_offset(in_idx, len(in_list), node_w=_node_render_h(d))

            # Stagger parallel edges (same src→dst) so they don't share the same path
            _par_nudge = int(
                (parallel_edge_idx.get(edge_i, 0) - (_par_count.get((e.src, e.dst), 1) - 1) / 2)
                * MIN_FAN_STEP
            )
            out_offset += _par_nudge
            in_offset += _par_nudge

            x1 = s.x + _node_render_w(s)
            y1 = s.y + out_offset
            x2 = d.x
            y2 = d.y + in_offset
            # 3-segment fast path (right → vertical → right); fall back to A* if blocked.
            _cross_row = abs(y1 - y2) > _node_render_h(s) // 2 and rank_gap == 1
            bend_x = int(x1 + (x2 - x1) * 3 // 4 if _cross_row else (x1 + x2) // 2)
            _fast_lr = [(int(x1), int(y1)), (bend_x, int(y1)), (bend_x, int(y2)), (int(x2), int(y2))]
            if _try_3seg_clear(_fast_lr, _routing_obs):
                _pts_lr = _fast_lr
            else:
                _pts_lr = _astar_route(int(x1), int(y1), int(x2), int(y2),
                                       _grid_xs, _grid_ys, _blocked)
                if len(_pts_lr) >= 2:
                    _pts_lr[0] = (int(x1), int(y1))
                    _pts_lr[-1] = (int(x2), int(y2))
            path = _smooth_orthogonal_path(_pts_lr)
            ah = _arrowhead(x2, y2, 1, 0, **ah_kw) if e.arrow else None
            if e.label:
                H = _LABEL_CHIP_H
                _yr = (int(min(y1, y2)) - H - 4, int(max(y1, y2)) + H + 4)
                lx, ly = _label_on_longest(_pts_lr, e.label, canvas_w, obstacles, placed_labels,
                                           y_range=_yr)
            else:
                lx, ly = int((x1 + x2) // 2), int(min(y1, y2)) - 12
            result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                           "lx": lx, "ly": ly, "rot": 0, "marker_id": marker_id,
                           "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css})
            continue

        # TB adjacent-rank forward edge: orthogonal path bottom-centre to top-centre
        out_list = fan_out[e.src]
        out_idx = out_list.index(e.dst) if e.dst in out_list else 0
        out_offset = _fan_offset(out_idx, len(out_list), node_w=_node_render_w(s))

        in_list = fan_in[e.dst]
        in_idx = in_list.index(e.src) if e.src in in_list else 0
        in_offset = _fan_offset(in_idx, len(in_list), node_w=_node_render_w(d))

        # Stagger parallel edges (same src→dst) so they don't share the same path
        _par_nudge = int(
            (parallel_edge_idx.get(edge_i, 0) - (_par_count.get((e.src, e.dst), 1) - 1) / 2)
            * MIN_FAN_STEP
        )
        out_offset += _par_nudge
        in_offset += _par_nudge

        x1 = s.x + out_offset
        y1 = s.y + _node_render_h(s)
        x2 = d.x + in_offset
        y2 = d.y

        # Clip to diamond face for diamond-shaped source/destination nodes
        if s.shape == "diamond":
            _sh = _node_render_h(s)
            _sx, _sy = s.x + _node_render_w(s) // 2, s.y + _sh // 2
            x1, y1 = _clip_to_diamond(float(x1), float(y1), float(_sx), float(_sy),
                                       float(_node_render_w(s)), float(_sh), 0, 0)
        if d.shape == "diamond":
            _dh = _node_render_h(d)
            _dx2, _dy2 = d.x + _node_render_w(d) // 2, d.y + _dh // 2
            x2, y2 = _clip_to_diamond(float(x2), float(y2), float(_dx2), float(_dy2),
                                       float(_node_render_w(d)), float(_dh), 0, 0)

        # Route: 3-segment fast path (down → across → down); fall back to A* if blocked.
        mid_y = (int(y1) + int(y2)) // 2
        _fast = [(int(x1), int(y1)), (int(x1), mid_y), (int(x2), mid_y), (int(x2), int(y2))]
        if _try_3seg_clear(_fast, _routing_obs):
            _pts = _fast
        else:
            _pts = _astar_route(int(x1), int(y1), int(x2), int(y2),
                                _grid_xs, _grid_ys, _blocked)
            if len(_pts) >= 2:
                _pts[0] = (int(x1), int(y1))
                _pts[-1] = (int(x2), int(y2))
        path = _smooth_orthogonal_path(_pts)

        ah = _arrowhead(int(x2), int(y2), 0, 1, **ah_kw) if e.arrow else None

        if e.label:
            H = _LABEL_CHIP_H
            _yr = (int(min(y1, y2)) - H - 4, int(max(y1, y2)) + H + 4)
            lx, ly = _label_on_longest(_pts, e.label, canvas_w, obstacles, placed_labels,
                                       y_range=_yr)
        else:
            lx, ly = int(x1 + _LABEL_PERP), int((y1 + mid_y) // 2)
        result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                       "lx": lx, "ly": ly, "rot": 0, "marker_id": marker_id,
                       "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css})

    return result

