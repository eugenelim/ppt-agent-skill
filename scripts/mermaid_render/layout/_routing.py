from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from ._constants import (
    _Node, _Edge,
    NODE_W, NODE_H, SELF_LOOP_DX, MIN_FAN_STEP,
    BASE_LOOP_EXTENT, LOOP_LANE_GAP, LABEL_PAD,
    GROUP_PAD_Y_TOP,
    _node_render_h, _is_terminal_circle, _TERMINAL_NODE_SIZE,
    _CIRCLE_NODE_SIZE, _DIAMOND_SIZE, _HEXAGON_SIZE,
)
from ._geometry import Rect


@dataclass(frozen=True)
class LabelPlacement:
    """Result of label position selection.

    box: the chip Rect when a position was found; None only when candidates list is empty.
    reroute_required: True when the best available position still overlaps an obstacle.
    """
    box: "Rect | None"
    reroute_required: bool


def _node_render_w(n: "_Node") -> int:
    """Effective rendered width for routing exit/entry x-coordinate computation."""
    if _is_terminal_circle(n):
        return _TERMINAL_NODE_SIZE
    if n.shape in ("circle", "doublecircle"):
        return n.width if n.width > 0 else _CIRCLE_NODE_SIZE
    if n.shape == "diamond":
        return n.width if n.width > 0 else _DIAMOND_SIZE
    if n.shape == "hexagon":
        return n.width if n.width > 0 else _HEXAGON_SIZE
    return n.width or NODE_W


def _side_port(node: "_Node", side: "str | None") -> "tuple[int, int] | None":
    """Return face-center (x, y) for a named port side, or None if side is not set.

    Side codes: L(eft), R(ight), T(op), B(ottom) — case-insensitive.
    Used by architecture-beta edges with explicit port annotations (A:R --> L:B).
    """
    if not side:
        return None
    nw = _node_render_w(node)
    nh = _node_render_h(node)
    s = side.upper()
    if s == "L":
        return (node.x, node.y + nh // 2)
    if s == "R":
        return (node.x + nw, node.y + nh // 2)
    if s == "T":
        return (node.x + nw // 2, node.y)
    if s == "B":
        return (node.x + nw // 2, node.y + nh)
    return None


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
        # External bypass channels are at ±8 px outside node edges, giving visual
        # clearance. Exact boundary positions (0, nw) are still included because the
        # A* start/end override restores exact port coords regardless of grid snapping.
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
    (more than 4 px inside a boundary in the perpendicular direction).
    """
    CLEAR = 4
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


_ASTAR_FALLBACK = object()  # sentinel: A* used the L-shaped fallback


def _astar_route(
    sx: int, sy: int,
    dx: int, dy: int,
    grid_xs: "list[int]",
    grid_ys: "list[int]",
    blocked: "set[tuple]",
    occupied: "set[tuple] | None" = None,
    _failures: "list | None" = None,
) -> "list[tuple[int, int]]":
    """Obstacle-avoiding A* on sparse orthogonal routing grid.

    Cost function: seg_length + SEG_COST per segment + BEND per 90° bend
                   + CROSS penalty for each segment that crosses an already-routed edge.
    Heuristic: Manhattan distance to goal (admissible).
    Returns a list of (x, y) waypoints with collinear points removed.
    The caller should replace waypoints[0] and waypoints[-1] with the
    exact port coordinates to restore sub-grid precision.
    """
    BEND = 100   # reduced from 200; segment-count term handles turn avoidance
    SEG_COST = 25
    CROSS = 60   # soft penalty for crossing an already-routed edge
    nx, ny = len(grid_xs), len(grid_ys)

    def _snap(val: int, arr: "list[int]") -> int:
        return min(range(len(arr)), key=lambda i: abs(arr[i] - val))

    sxi, syi = _snap(sx, grid_xs), _snap(sy, grid_ys)
    dxi, dyi = _snap(dx, grid_xs), _snap(dy, grid_ys)

    if sxi == dxi and syi == dyi:
        return [(sx, sy), (dx, dy)]

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
            cross = CROSS if (occupied and seg in occupied) else 0
            ng = g + seg_len + SEG_COST + (BEND if nd != d else 0) + cross
            ns = (nxi, nyi, nd)
            if ng < dist.get(ns, INF):
                dist[ns] = ng
                prev[ns] = state
                nh = abs(grid_xs[dxi] - grid_xs[nxi]) + abs(grid_ys[dyi] - grid_ys[nyi])
                heapq.heappush(heap, (ng + nh, ctr, nxi, nyi, nd))
                ctr += 1

    # No path found
    return None


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
    clearance: int = 4,
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


def _route_perimeter(
    sx: int, sy: int, dx: int, dy: int,
    margin: int,
    obstacles: list,
) -> "list | None":
    """Try to route around obstacles using a 3-segment bypass path.

    Computes the bounding box of all obstacles, inflates it by margin, then tries
    4 bypass directions (top, bottom, left, right). Returns the first path that
    passes _try_3seg_clear, or None if all four bypass paths are blocked.
    """
    if not obstacles:
        return [(sx, sy), (dx, dy)]
    bx1 = min(o[0] for o in obstacles) - margin
    by1 = min(o[1] for o in obstacles) - margin
    bx2 = max(o[2] for o in obstacles) + margin
    by2 = max(o[3] for o in obstacles) + margin

    bypass_paths = [
        # top bypass: go above the obstacle bounding box
        [(sx, sy), (sx, by1), (dx, by1), (dx, dy)],
        # bottom bypass: go below
        [(sx, sy), (sx, by2), (dx, by2), (dx, dy)],
        # left bypass: go left of the bounding box
        [(sx, sy), (bx1, sy), (bx1, dy), (dx, dy)],
        # right bypass: go right of the bounding box
        [(sx, sy), (bx2, sy), (bx2, dy), (dx, dy)],
    ]
    for path in bypass_paths:
        if _try_3seg_clear(path, obstacles):
            return path
    return None


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
    _lp = _best_label_pos(cands, label, obstacles, placed, canvas_w, y_range=y_range)
    if _lp.box is None:
        return 0, 0
    return int(_lp.box.x), int(_lp.box.y + _lp.box.h)


def _lp_xy(lp: LabelPlacement) -> tuple:
    """Unwrap a LabelPlacement to (lx, ly) for use as render coordinates."""
    if lp.box is None:
        return 0, 0
    return int(lp.box.x), int(lp.box.y + lp.box.h)


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


def node_rect(n: "_Node") -> Rect:
    """Return the bounding Rect for node n using rendered (not fixed) dimensions."""
    return Rect(n.x, n.y, _node_render_w(n), _node_render_h(n))


def _fan_offset(index: int, total: int, node_w: int = NODE_W, pad: int = 16) -> int:
    """Distribute fan-in/fan-out endpoints across node edge (spec §Step6).

    Endpoints are spaced at least MIN_FAN_STEP px apart and centred on the node
    midpoint so parallel edges stay visually separated even on short nodes.
    Result is clamped to [0, node_w] to prevent out-of-bounds port placement.
    """
    if total <= 1:
        return node_w // 2
    usable = node_w - 2 * pad
    step = max(usable // (total + 1), MIN_FAN_STEP)
    # Centre the fan: span = step * (total-1), start = mid - span/2.
    centre = node_w // 2
    start = centre - step * (total - 1) // 2
    return max(0, min(node_w, start + step * index))


def allocate_face_ports(
    face_length: int,
    count: int,
    *,
    padding: int = 8,
    min_step: int = 6,
) -> "tuple[PortAllocation, ...]":
    """Allocate port positions along a node face.

    Returns a tuple of PortAllocation with offset in [0, face_length] and lane.
    When count exceeds capacity (usable / min_step), excess ports cycle to lane 1+.
    """
    from ._geometry import PortAllocation as _PA  # local import avoids circular at module level
    if count == 0:
        return ()
    usable = max(0, face_length - 2 * padding)
    capacity = max(1, usable // min_step)
    results = []
    for i in range(count):
        slot = i % capacity
        lane = i // capacity
        if capacity == 1:
            offset = face_length // 2
        else:
            step = usable // (capacity - 1) if capacity > 1 else 0
            offset = padding + slot * step
        offset = max(0, min(face_length, offset))
        results.append(_PA(offset=offset, lane=lane))
    return tuple(results)


_LABEL_PERP = 20  # perpendicular offset for edge labels (px)

# ── edge label placement ──────────────────────────────────────────────────────

_LABEL_CHIP_H = 17    # chip height: 12px font + 2×padding + 1px border ≈ 17px
_LABEL_CHAR_W = 6.8   # average char width at 12px Inter regular (empirical)


def _est_label_w(text: str) -> int:
    """Estimate rendered edge-label chip width in px.

    Uses the TextLayout measurer (Pillow FreeType when available) for accuracy;
    falls back to character-bucketing heuristic when measurement fails.
    """
    if not text:
        return 0
    try:
        from ._text import get_default_measurer, TextStyle
        run = get_default_measurer().measure_run(text, TextStyle(font_size=11))
        return min(450, max(30, int(run.width)))
    except Exception:
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
) -> LabelPlacement:
    """Pick the best position from candidates with minimum total overlap.

    Returns a LabelPlacement. When candidates is empty, returns box=None.
    When all candidates are blocked by node obstacles, returns the least-overlap
    position with reroute_required=True so callers know a reroute is desirable.

    y_range: (y_lo, y_hi) defines the edge's natural vertical span.  Positions
    above y_lo are penalised at 200px/px to prevent labels from escaping above
    group containers; positions below y_hi get a softer 10px/px nudge.
    """
    if not candidates:
        return LabelPlacement(box=None, reroute_required=True)
    w = _est_label_w(label)
    all_obs = obstacles + placed
    # Hard-reject: candidates that overlap any node obstacle are excluded in a first
    # pass so labels never print on top of nodes even when scoring would accept them.
    # Fall back to all candidates only if every candidate is blocked.
    _clear = [c for c in candidates if all(
        _overlap_area(_label_chip_bbox(max(4, min(canvas_w - w - 4, c[0])), c[1], label), obs, margin=0) == 0
        for obs in obstacles
    )]
    _all_blocked = not _clear
    _active_candidates = _clear if _clear else candidates
    best_lx, best_ly = _active_candidates[0][0], _active_candidates[0][1]
    best_score = float("inf")
    for raw_lx, ly in _active_candidates:
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
    chip = _label_chip_bbox(best_lx, best_ly, label)
    placed.append(chip)
    box = Rect(chip[0], chip[1], chip[2] - chip[0], chip[3] - chip[1])
    return LabelPlacement(box=box, reroute_required=_all_blocked)


def _route_edges(nodes: dict[str, _Node], edges: list[_Edge], canvas_w: int,
                 direction: str = "TB",
                 group_bboxes: "dict | None" = None,
                 route_failures: "list | None" = None) -> list[dict]:
    """Return list of edge render specs (path_d, arrowhead_pts, label, style, lx, ly, rot).

    route_failures: if provided, mutable list where (src, dst) pairs are appended
    whenever A* fails to find an obstacle-free path and the L-shaped fallback is used.
    """
    is_lr = direction.upper() in ("LR", "RL")

    # Count fan-in/fan-out per node using REAL endpoints.
    # Dummy-chain edges (orig_src/orig_dst set) are counted once at the last segment
    # so that multi-rank edges like A→C (via dummy) appear as one port on A and one
    # on C, not as multiple ports pointing to invisible intermediate dummies.
    fan_in: dict[str, list[str]] = {nid: [] for nid in nodes}
    fan_out: dict[str, list[str]] = {nid: [] for nid in nodes}
    _seen_fan_pairs: set = set()
    for e in edges:
        if e.src not in nodes or e.dst not in nodes or e.reversed_:
            continue
        if nodes[e.dst].is_dummy:
            continue  # skip intermediate segments; handled at last segment
        real_src = e.orig_src or e.src
        real_dst = e.orig_dst or e.dst
        pair = (real_src, real_dst)
        if pair not in _seen_fan_pairs:
            _seen_fan_pairs.add(pair)
            fan_in[real_dst].append(real_src)
            fan_out[real_src].append(real_dst)

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
    # Node-body obstacles + group title strips for the A* grid.
    _routing_obs = [(n.x, n.y, n.x + _node_render_w(n), n.y + _node_render_h(n))
                    for n in nodes.values() if not n.is_dummy]
    if group_bboxes:
        _routing_obs += [
            (int(x1), int(y1), int(x2), int(y1) + GROUP_PAD_Y_TOP)
            for x1, y1, x2, _y2 in group_bboxes.values()
        ]
    _blocked = _blocked_segs(_grid_xs, _grid_ys, _routing_obs)
    # Tracks grid-index segments used by already-routed edges so subsequent
    # edges pay a soft CROSS penalty for reusing the same channel.
    _occupied: set = set()

    def _snap_to_grid(val: int, arr: list) -> int:
        return min(range(len(arr)), key=lambda i: abs(arr[i] - val))

    def _accumulate_occupied(pts: list) -> None:
        for _k in range(len(pts) - 1):
            _ax, _ay = pts[_k]
            _bx, _by = pts[_k + 1]
            _axi = _snap_to_grid(_ax, _grid_xs)
            _ayi = _snap_to_grid(_ay, _grid_ys)
            _bxi = _snap_to_grid(_bx, _grid_xs)
            _byi = _snap_to_grid(_by, _grid_ys)
            # Decompose into unit grid steps to match A*'s single-step segments
            if _axi == _bxi:
                for _yi in range(min(_ayi, _byi), max(_ayi, _byi)):
                    _occupied.add((_axi, _yi, _axi, _yi + 1))
            else:
                for _xi in range(min(_axi, _bxi), max(_axi, _bxi)):
                    _occupied.add((_xi, _ayi, _xi + 1, _ayi))

    # Right-lane x: always clears the rightmost node + group container border
    non_dummy = [n for n in nodes.values() if not n.is_dummy]
    right_lane_x = (max(n.x + _node_render_w(n) for n in non_dummy) if non_dummy else canvas_w) + 32

    # LR bottom-lane y: clears the tallest node's bottom + margin
    if is_lr and non_dummy:
        bottom_lane_y = max(n.y + _node_render_h(n) for n in non_dummy) + 32
    else:
        bottom_lane_y = 0

    # Per-node self-loop lane counter — incremented each time a self-loop is emitted
    # for that node so multiple loops get staggered extents.
    self_loop_lanes: dict[str, int] = {}

    # Build back-edge lane assignments so each back-edge uses its own stagger lane,
    # preventing multiple back-edges from collapsing onto the same routing lane.
    # Skip intermediate dummy-chain edges; use real endpoint ranks for gap detection.
    back_edge_lane: dict[int, int] = {}
    _be_count = 0
    for _i, _e in enumerate(edges):
        if _e.src not in nodes or _e.dst not in nodes or _e.src == _e.dst:
            continue
        if nodes[_e.dst].is_dummy:
            continue  # skip intermediate dummy segments
        _real_s = nodes.get(_e.orig_src or _e.src)
        _real_s_rank = _real_s.rank if _real_s else nodes[_e.src].rank
        _rg = nodes[_e.dst].rank - _real_s_rank
        if _e.reversed_ or _rg < 0:
            back_edge_lane[_i] = _be_count
            _be_count += 1

    # Build parallel-edge indices using real endpoints for deduplication.
    # Intermediate dummy-chain segments are skipped so each logical edge counts once.
    _par_count: dict[tuple, int] = {}
    parallel_edge_idx: dict[int, int] = {}
    for _i, _e in enumerate(edges):
        if nodes.get(_e.dst) and nodes[_e.dst].is_dummy:
            continue  # skip intermediate segments
        _real_s = _e.orig_src or _e.src
        _real_d = _e.orig_dst or _e.dst
        _key = (_real_s, _real_d)
        parallel_edge_idx[_i] = _par_count.get(_key, 0)
        _par_count[_key] = _par_count.get(_key, 0) + 1

    # Assign right-lane slots to TB skip-rank forward edges (rank_gap > 1) so they
    # route around intermediate nodes cleanly instead of boundary-touching via A*.
    _skip_lane: dict[int, int] = {}
    if not is_lr:
        _skip_count = 0
        for _i, _e in enumerate(edges):
            if _e.src not in nodes or _e.dst not in nodes:
                continue
            if nodes[_e.dst].is_dummy:
                continue
            if _e.reversed_:
                continue
            _real_s = nodes.get(_e.orig_src or _e.src)
            _real_s_rank = _real_s.rank if _real_s else nodes[_e.src].rank
            _rg = nodes[_e.dst].rank - _real_s_rank
            if _rg > 1:
                _skip_lane[_i] = _skip_count
                _skip_count += 1

    result: list[dict] = []
    for edge_i, e in enumerate(edges):
        if e.src not in nodes or e.dst not in nodes:
            continue
        s_node = nodes[e.src]
        d_node = nodes[e.dst]

        # Dummy-chain routing: edges are split into unit-rank segments via dummy nodes.
        # Skip all intermediate segments (dst is dummy). For the last segment (src is
        # dummy, dst is real), substitute orig_src as the routing start so the full
        # logical edge is drawn as ONE path from the original source to the destination.
        if d_node.is_dummy:
            continue  # intermediate segment — handled by last segment
        if s_node.is_dummy:
            orig = e.orig_src or e.src
            s = nodes.get(orig)
            if s is None:
                continue
        else:
            s = s_node
        d = d_node

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
        # arrow_src=True: UML marker belongs at the source end; use a -rev ID so
        # the renderer emits marker-start with orient="auto-start-reverse".
        if e.arrow and getattr(e, "arrow_src", False):
            marker_id: str | None = _mid + "-rev"
        else:
            marker_id: str | None = _mid if e.arrow else None

        # Self-loop: direction-aware rectangular orthogonal loop.
        # LR: exits top face (even lane_idx) / bottom face (odd lane_idx).
        # TB: exits right face (even lane_idx) / left face (odd lane_idx).
        # Extent = max(BASE_LOOP_EXTENT, label_w + 2*LABEL_PAD, 0.35*max(nw,nh)) + lane_num*LOOP_LANE_GAP
        if e.src == e.dst:
            lane_idx = self_loop_lanes.get(e.src, 0)
            self_loop_lanes[e.src] = lane_idx + 1
            nw = _node_render_w(s)
            nh = _node_render_h(s)
            label_w = _est_label_w(e.label) if e.label else 0
            lane_num = lane_idx // 2  # stack multiple loops of same face
            extent = (max(BASE_LOOP_EXTENT, label_w + 2 * LABEL_PAD, int(0.35 * max(nw, nh)))
                      + lane_num * LOOP_LANE_GAP)
            if is_lr:
                # LR: top face (even) / bottom face (odd)
                x_out = int(s.x + nw * 0.33)
                x_ret = int(s.x + nw * 0.67)
                if lane_idx % 2 == 0:
                    # top face — clamp so loop stays within canvas
                    y_face = s.y
                    loop_y = max(0, y_face - extent)
                    path = _smooth_orthogonal_path(
                        [(x_out, y_face), (x_out, loop_y), (x_ret, loop_y), (x_ret, y_face)]
                    )
                    ah = _arrowhead(x_ret, y_face, 0, 1, **ah_kw) if e.arrow else None
                    mid_x = (x_out + x_ret) // 2
                    cands = [
                        (mid_x - 20, max(0, loop_y - _LABEL_CHIP_H - 4)),
                        (x_out - 4, loop_y),
                        (x_ret + 4, loop_y),
                    ]
                    llx, lly = (_lp_xy(_best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w))
                                if e.label else (mid_x - 20, max(0, loop_y - _LABEL_CHIP_H - 4)))
                else:
                    # bottom face
                    y_face = s.y + nh
                    loop_y = y_face + extent
                    path = _smooth_orthogonal_path(
                        [(x_out, y_face), (x_out, loop_y), (x_ret, loop_y), (x_ret, y_face)]
                    )
                    ah = _arrowhead(x_ret, y_face, 0, -1, **ah_kw) if e.arrow else None
                    mid_x = (x_out + x_ret) // 2
                    cands = [
                        (mid_x - 20, loop_y + 4),
                        (x_out - 4, loop_y),
                        (x_ret + 4, loop_y),
                    ]
                    llx, lly = (_lp_xy(_best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w))
                                if e.label else (mid_x - 20, loop_y + 4))
            else:
                # TB: right face (even lane_idx) / left face (odd lane_idx)
                y_out = int(s.y + nh * 0.33)
                y_ret = int(s.y + nh * 0.67)
                if lane_idx % 2 == 0:
                    # right face
                    lx_face = s.x + nw
                    loop_x = lx_face + extent
                    path = _smooth_orthogonal_path(
                        [(lx_face, y_out), (loop_x, y_out), (loop_x, y_ret), (lx_face, y_ret)]
                    )
                    ah = _arrowhead(lx_face, y_ret, -1, 0, **ah_kw) if e.arrow else None
                    mid_y = (y_out + y_ret) // 2
                    cands = [
                        (loop_x + 4, mid_y),
                        (loop_x + 4, y_out - _LABEL_CHIP_H - 4),
                        (loop_x + 4, y_ret + _LABEL_CHIP_H + 4),
                    ]
                    llx, lly = (_lp_xy(_best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w))
                                if e.label else (loop_x + 4, mid_y))
                else:
                    # left face
                    lx_face = s.x
                    loop_x = max(0, lx_face - extent)  # clamp to canvas left edge
                    path = _smooth_orthogonal_path(
                        [(lx_face, y_out), (loop_x, y_out), (loop_x, y_ret), (lx_face, y_ret)]
                    )
                    ah = _arrowhead(lx_face, y_ret, 1, 0, **ah_kw) if e.arrow else None
                    mid_y = (y_out + y_ret) // 2
                    cands = [
                        (loop_x - 4 - label_w, mid_y),
                        (loop_x - 4 - label_w, y_out - _LABEL_CHIP_H - 4),
                        (loop_x - 4 - label_w, y_ret + _LABEL_CHIP_H + 4),
                    ]
                    llx, lly = (_lp_xy(_best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w))
                                if e.label else (loop_x - 4 - label_w, mid_y))
            result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                           "lx": llx, "ly": lly, "rot": 0, "marker_id": marker_id,
                           "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css,
                           "src_label": e.src_label, "dst_label": e.dst_label, "bidir": getattr(e, "bidir", False)})
            continue

        rank_gap = d.rank - s.rank

        # Back-edge → right-lane (TB) or bottom-lane (LR) smooth path.
        # Use geometry to detect direction: works for both Sugiyama (rank-based coords)
        # and ELK (which places long forward edges without dummy nodes).
        # A forward edge goes RIGHT (LR) or DOWN (TB); anything else is a back edge.
        if is_lr:
            _s_r, _d_r = node_rect(s), node_rect(d)
            _goes_back = (_d_r.x + _d_r.w / 2) < _s_r.x  # dst center left of src left
        else:
            _goes_back = (d.y + _node_render_h(d) // 2) < s.y  # dst center above src top
        if e.reversed_ or _goes_back:
            be_lane = back_edge_lane.get(edge_i, 0)
            if is_lr:
                # Right-to-left crossing: source LEFT edge is past destination RIGHT edge.
                # Route directly (left-exit → midpoint → right-enter) instead of
                # the bottom lane, which adds unnecessary vertical canvas space.
                if not e.reversed_ and node_rect(s).x >= node_rect(d).x1:
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
                        llx, lly = _lp_xy(_best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w))
                    else:
                        llx, lly = max(0, x1 - 164), int(y1) - 12
                    result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                                   "lx": llx, "ly": lly, "rot": 0, "marker_id": marker_id,
                                   "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css,
                           "src_label": e.src_label, "dst_label": e.dst_label, "bidir": getattr(e, "bidir", False)})
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
                        llx, lly = _lp_xy(_best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w))
                    else:
                        llx, lly = (sx + dx_) // 2, lane_y + 4
                    result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                                   "lx": llx, "ly": lly, "rot": 0, "marker_id": marker_id,
                                   "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css,
                           "src_label": e.src_label, "dst_label": e.dst_label, "bidir": getattr(e, "bidir", False)})
            else:
                lane_x = right_lane_x + 12 * be_lane
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
                    llx, lly = _lp_xy(_best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w))
                else:
                    llx, lly = lane_x + 4, (sy + dy_) // 2
                result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                               "lx": llx, "ly": lly, "rot": 0, "marker_id": marker_id,
                               "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css,
                           "src_label": e.src_label, "dst_label": e.dst_label, "bidir": getattr(e, "bidir", False)})
            continue

        # TB skip-rank forward edge: rank_gap > 1 means this edge bypasses intermediate
        # nodes. Route via the right lane to avoid visual boundary-touching via A*.
        if not is_lr and rank_gap > 1 and not e.reversed_ and edge_i in _skip_lane:
            skip_i = _skip_lane[edge_i]
            _sk_lane_x = right_lane_x + 8 * skip_i
            _tb_real_src = e.orig_src or e.src
            _tb_real_dst = e.orig_dst or e.dst
            out_list = fan_out.get(_tb_real_src, [])
            out_idx = out_list.index(_tb_real_dst) if _tb_real_dst in out_list else 0
            out_offset = _fan_offset(out_idx, len(out_list), node_w=_node_render_w(s))
            in_list = fan_in.get(_tb_real_dst, [])
            in_idx = in_list.index(_tb_real_src) if _tb_real_src in in_list else 0
            in_offset = _fan_offset(in_idx, len(in_list), node_w=_node_render_w(d))
            x1 = int(s.x + out_offset)
            y1 = int(s.y + _node_render_h(s))   # src bottom
            x2 = int(d.x + in_offset)
            y2 = int(d.y)                         # dst top
            path = _smooth_orthogonal_path(
                [(x1, y1), (_sk_lane_x, y1), (_sk_lane_x, y2), (x2, y2)]
            )
            ah = _arrowhead(x2, y2, 0, 1, **ah_kw) if e.arrow else None
            if e.label:
                H = _LABEL_CHIP_H
                mid_y = (y1 + y2) // 2
                cands = [
                    (_sk_lane_x + 4, mid_y),
                    (_sk_lane_x + 4, y1 + H + 4),
                    (_sk_lane_x + 4, y2 - H - 4),
                ]
                llx, lly = _lp_xy(_best_label_pos(cands, e.label, obstacles, placed_labels, canvas_w))
            else:
                llx, lly = _sk_lane_x + 4, (y1 + y2) // 2
            result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                           "lx": llx, "ly": lly, "rot": 0, "marker_id": marker_id,
                           "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css,
                           "src_label": e.src_label, "dst_label": e.dst_label, "bidir": getattr(e, "bidir", False)})
            continue

        if is_lr:
            # LR forward edge: orthogonal path right-of-src to left-of-dst
            # Use real endpoints for fan lookup (dummy-chain edges have orig_src/orig_dst).
            _lr_real_src = e.orig_src or e.src
            _lr_real_dst = e.orig_dst or e.dst
            out_list = fan_out.get(_lr_real_src, [])
            out_idx = out_list.index(_lr_real_dst) if _lr_real_dst in out_list else 0
            out_offset = _fan_offset(out_idx, len(out_list), node_w=_node_render_h(s))

            in_list = fan_in.get(_lr_real_dst, [])
            in_idx = in_list.index(_lr_real_src) if _lr_real_src in in_list else 0
            in_offset = _fan_offset(in_idx, len(in_list), node_w=_node_render_h(d))

            # Stagger parallel edges (same real src→dst) so they don't share the same path
            _par_nudge = int(
                (parallel_edge_idx.get(edge_i, 0) - (_par_count.get((_lr_real_src, _lr_real_dst), 1) - 1) / 2)
                * MIN_FAN_STEP
            )
            out_offset += _par_nudge
            in_offset += _par_nudge

            x1 = s.x + _node_render_w(s)
            y1 = s.y + out_offset
            x2 = d.x
            y2 = d.y + in_offset

            # Architecture-beta explicit port overrides (A:R --> L:B syntax).
            # When set, pin the endpoint to the named face-center and force A*.
            _src_port = _side_port(s, getattr(e, "src_side", None))
            _dst_port = _side_port(d, getattr(e, "dst_side", None))
            _has_fixed_port = _src_port is not None or _dst_port is not None
            if _src_port:
                x1, y1 = _src_port
            if _dst_port:
                x2, y2 = _dst_port

            # 3-segment fast path (right → vertical → right); fall back to A* if blocked.
            # Skip fast path when ports are pinned to non-standard faces.
            _cross_row = abs(y1 - y2) > _node_render_h(s) // 2 and rank_gap == 1
            bend_x = int(x1 + (x2 - x1) * 3 // 4 if _cross_row else (x1 + x2) // 2)
            _fast_lr = [(int(x1), int(y1)), (bend_x, int(y1)), (bend_x, int(y2)), (int(x2), int(y2))]
            if not _has_fixed_port and _try_3seg_clear(_fast_lr, _routing_obs):
                _pts_lr = _fast_lr
            else:
                _pts_lr = _astar_route(int(x1), int(y1), int(x2), int(y2),
                                       _grid_xs, _grid_ys, _blocked, _occupied)
                if _pts_lr is None:
                    for _margin in (16, 32, 64, 128):
                        _pts_lr = _route_perimeter(int(x1), int(y1), int(x2), int(y2),
                                                   _margin, _routing_obs)
                        if _pts_lr is not None:
                            break
                if _pts_lr is None:
                    continue  # skip edge — omit rather than draw through obstacle
                if len(_pts_lr) >= 2:
                    _pts_lr[0] = (int(x1), int(y1))
                    _pts_lr[-1] = (int(x2), int(y2))
            _accumulate_occupied(_pts_lr)
            path = _smooth_orthogonal_path(_pts_lr)
            if e.arrow:
                _ldx_lr, _ldy_lr = 1, 0  # LR nominal default
                if len(_pts_lr) >= 2:
                    _ddx = _pts_lr[-1][0] - _pts_lr[-2][0]
                    _ddy = _pts_lr[-1][1] - _pts_lr[-2][1]
                    if _ddx != 0 or _ddy != 0:
                        _ldx_lr, _ldy_lr = _ddx, _ddy
                ah = _arrowhead(int(x2), int(y2), _ldx_lr, _ldy_lr, **ah_kw)
            else:
                ah = None
            if e.label:
                H = _LABEL_CHIP_H
                _yr = (int(min(y1, y2)) - H - 4, int(max(y1, y2)) + H + 4)
                lx, ly = _label_on_longest(_pts_lr, e.label, canvas_w, obstacles, placed_labels,
                                           y_range=_yr)
            else:
                lx, ly = int((x1 + x2) // 2), int(min(y1, y2)) - 12
            result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                           "lx": lx, "ly": ly, "rot": 0, "marker_id": marker_id,
                           "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css,
                           "src_label": e.src_label, "dst_label": e.dst_label, "bidir": getattr(e, "bidir", False)})
            continue

        # TB adjacent-rank forward edge: orthogonal path bottom-centre to top-centre
        # Use real endpoints for fan lookup (dummy-chain edges have orig_src/orig_dst).
        _tb_real_src = e.orig_src or e.src
        _tb_real_dst = e.orig_dst or e.dst
        out_list = fan_out.get(_tb_real_src, [])
        out_idx = out_list.index(_tb_real_dst) if _tb_real_dst in out_list else 0
        out_offset = _fan_offset(out_idx, len(out_list), node_w=_node_render_w(s))

        in_list = fan_in.get(_tb_real_dst, [])
        in_idx = in_list.index(_tb_real_src) if _tb_real_src in in_list else 0
        in_offset = _fan_offset(in_idx, len(in_list), node_w=_node_render_w(d))

        # Stagger parallel edges (same real src→dst) so they don't share the same path
        _par_nudge = int(
            (parallel_edge_idx.get(edge_i, 0) - (_par_count.get((_tb_real_src, _tb_real_dst), 1) - 1) / 2)
            * MIN_FAN_STEP
        )
        out_offset += _par_nudge
        in_offset += _par_nudge

        x1 = s.x + out_offset
        y1 = s.y + _node_render_h(s)
        x2 = d.x + in_offset
        y2 = d.y

        # Architecture-beta explicit port overrides.
        _src_port_tb = _side_port(s, getattr(e, "src_side", None))
        _dst_port_tb = _side_port(d, getattr(e, "dst_side", None))
        _has_fixed_port_tb = _src_port_tb is not None or _dst_port_tb is not None
        if _src_port_tb:
            x1, y1 = _src_port_tb
        if _dst_port_tb:
            x2, y2 = _dst_port_tb

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
        # Skip fast path when ports are pinned to non-standard faces.
        mid_y = (int(y1) + int(y2)) // 2
        _fast = [(int(x1), int(y1)), (int(x1), mid_y), (int(x2), mid_y), (int(x2), int(y2))]
        if not _has_fixed_port_tb and _try_3seg_clear(_fast, _routing_obs):
            _pts = _fast
        else:
            _pts = _astar_route(int(x1), int(y1), int(x2), int(y2),
                                _grid_xs, _grid_ys, _blocked, _occupied)
            if _pts is None:
                for _margin in (16, 32, 64, 128):
                    _pts = _route_perimeter(int(x1), int(y1), int(x2), int(y2),
                                           _margin, _routing_obs)
                    if _pts is not None:
                        break
            if _pts is None:
                continue  # skip edge — omit rather than draw through obstacle
            if len(_pts) >= 2:
                _pts[0] = (int(x1), int(y1))
                _pts[-1] = (int(x2), int(y2))
        _accumulate_occupied(_pts)
        path = _smooth_orthogonal_path(_pts)

        # Derive arrowhead direction from the actual last path segment so A*-routed
        # edges whose final segment is not perfectly downward still point correctly.
        if e.arrow:
            _ldx, _ldy = 0, 1  # TB nominal default
            if len(_pts) >= 2:
                _ddx = _pts[-1][0] - _pts[-2][0]
                _ddy = _pts[-1][1] - _pts[-2][1]
                if _ddx != 0 or _ddy != 0:
                    _ldx, _ldy = _ddx, _ddy
            ah = _arrowhead(int(x2), int(y2), _ldx, _ldy, **ah_kw)
        else:
            ah = None

        if e.label:
            H = _LABEL_CHIP_H
            _yr = (int(min(y1, y2)) - H - 4, int(max(y1, y2)) + H + 4)
            lx, ly = _label_on_longest(_pts, e.label, canvas_w, obstacles, placed_labels,
                                       y_range=_yr)
        else:
            lx, ly = int(x1 + _LABEL_PERP), int((y1 + mid_y) // 2)
        result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                       "lx": lx, "ly": ly, "rot": 0, "marker_id": marker_id,
                       "src": e.orig_src or e.src, "dst": e.orig_dst or e.dst, "extra_css": e.extra_css,
                           "src_label": e.src_label, "dst_label": e.dst_label, "bidir": getattr(e, "bidir", False)})

    return result

