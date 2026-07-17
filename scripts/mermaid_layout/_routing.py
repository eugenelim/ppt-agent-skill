from __future__ import annotations

import math

from ._constants import (
    _Node, _Edge,
    NODE_W, NODE_H, SELF_LOOP_DX, MIN_FAN_STEP,
    _node_render_h,
)

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


_LABEL_PERP = 14  # perpendicular offset for edge labels (px)


def _route_edges(nodes: dict[str, _Node], edges: list[_Edge], canvas_w: int,
                 direction: str = "TB") -> list[dict]:
    """Return list of edge render specs (path_d, arrowhead_pts, label, style, lx, ly, rot)."""
    is_lr = direction.upper() in ("LR", "RL")

    # Count fan-in/fan-out per node (for endpoint distribution)
    fan_in: dict[str, list[str]] = {nid: [] for nid in nodes}
    fan_out: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:
        if e.src in nodes and e.dst in nodes and not e.reversed_:
            fan_in[e.dst].append(e.src)
            fan_out[e.src].append(e.dst)

    # Right-lane x: always clears the rightmost node + group container border
    non_dummy = [n for n in nodes.values() if not n.is_dummy]
    right_lane_x = (max(n.x + NODE_W for n in non_dummy) if non_dummy else canvas_w) + 32

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
        ah_kw: dict = {"back": 10, "half_w": 5} if e.style == "thick" else {}

        # Self-loop
        if e.src == e.dst:
            lx = s.x + NODE_W
            ty = s.y
            by_ = s.y + NODE_H
            path = (f"M {lx} {ty + 12} "
                    f"C {lx + SELF_LOOP_DX} {ty} {lx + SELF_LOOP_DX} {by_} "
                    f"{lx} {by_ - 12}")
            tip_x, tip_y = lx, by_ - 12
            ah = _arrowhead(tip_x, tip_y, -1, 0, **ah_kw) if e.arrow else None
            result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                           "lx": tip_x + 14, "ly": (ty + by_) // 2, "rot": 0})
            continue

        rank_gap = d.rank - s.rank

        # Back-edge or skip-rank → right-lane (TB) or bottom-lane (LR) smooth path.
        # Each back-edge gets its own stagger lane so they don't overlap.
        if e.reversed_ or rank_gap < 0 or rank_gap > 1:
            be_lane = back_edge_lane.get(edge_i, 0)
            if is_lr:
                lane_y = bottom_lane_y + 32 * be_lane
                sx = s.x + NODE_W // 2
                sy = s.y + _node_render_h(s)
                dx_ = d.x + NODE_W // 2
                dy_ = d.y + _node_render_h(d)
                path = _smooth_orthogonal_path(
                    [(sx, sy), (sx, lane_y), (dx_, lane_y), (dx_, dy_)]
                )
                ah = _arrowhead(dx_, dy_, 0, -1, **ah_kw) if e.arrow else None
                result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                               "lx": (sx + dx_) // 2, "ly": lane_y + 4, "rot": 0})
            else:
                lane_x = right_lane_x + 32 * be_lane
                sx = s.x + NODE_W
                sy = s.y + NODE_H // 2
                dx_ = d.x + NODE_W
                dy_ = d.y + NODE_H // 2
                path = _smooth_orthogonal_path(
                    [(sx, sy), (lane_x, sy), (lane_x, dy_), (dx_, dy_)]
                )
                ah = _arrowhead(dx_, dy_, -1, 0, **ah_kw) if e.arrow else None
                result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                               "lx": lane_x + 4, "ly": (sy + dy_) // 2, "rot": 0})
            continue

        if is_lr:
            # LR forward edge: horizontal Bézier, right-of-src to left-of-dst
            out_list = fan_out[e.src]
            out_idx = out_list.index(e.dst) if e.dst in out_list else 0
            out_offset = _fan_offset(out_idx, len(out_list), node_w=_node_render_h(s))

            in_list = fan_in[e.dst]
            in_idx = in_list.index(e.src) if e.src in in_list else 0
            in_offset = _fan_offset(in_idx, len(in_list), node_w=_node_render_h(d))

            x1 = s.x + NODE_W
            y1 = s.y + out_offset
            x2 = d.x
            y2 = d.y + in_offset
            cx1 = x1 + (x2 - x1) // 3
            cx2 = x1 + 2 * (x2 - x1) // 3
            path = f"M {x1} {y1} C {cx1} {y1} {cx2} {y2} {x2} {y2}"
            ah = _arrowhead(x2, y2, x2 - cx2, 0.001, **ah_kw) if e.arrow else None
            # Label: perpendicular offset from midpoint
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            edge_dx = float(x2 - x1)
            edge_dy = float(y2 - y1)
            edge_len = math.hypot(edge_dx, edge_dy) or 1.0
            perp_x = edge_dy / edge_len
            perp_y = -edge_dx / edge_len
            lx = int(mid_x + perp_x * _LABEL_PERP)
            ly = int(mid_y + perp_y * _LABEL_PERP)
            # Stagger labels for parallel edges (same src→dst pair)
            _par = parallel_edge_idx.get(edge_i, 0)
            if _par:
                lx = int(lx + perp_x * 12 * _par)
                ly = int(ly + perp_y * 12 * _par)
            rot = 90 if abs(edge_dy) > abs(edge_dx) * 1.5 else 0
            result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                           "lx": lx, "ly": ly, "rot": rot})
            continue

        # TB adjacent-rank forward edge: cubic Bézier bottom-centre to top-centre
        out_list = fan_out[e.src]
        out_idx = out_list.index(e.dst) if e.dst in out_list else 0
        out_offset = _fan_offset(out_idx, len(out_list))

        in_list = fan_in[e.dst]
        in_idx = in_list.index(e.src) if e.src in in_list else 0
        in_offset = _fan_offset(in_idx, len(in_list))

        x1 = s.x + out_offset
        y1 = s.y + NODE_H
        x2 = d.x + in_offset
        y2 = d.y
        cy1 = y1 + (y2 - y1) // 3
        cy2 = y1 + 2 * (y2 - y1) // 3
        path = f"M {x1} {y1} C {x1} {cy1} {x2} {cy2} {x2} {y2}"

        ah = _arrowhead(x2, y2, x2 - x1, y2 - cy2, **ah_kw) if e.arrow else None

        # Label: perpendicular offset from midpoint (prevents crossing the line)
        mid_x = (x1 + x2) // 2
        mid_y = (y1 + y2) // 2
        edge_dx = float(x2 - x1)
        edge_dy = float(y2 - y1)
        edge_len = math.hypot(edge_dx, edge_dy) or 1.0
        # Right perpendicular (90° CW from edge direction)
        perp_x = edge_dy / edge_len
        perp_y = -edge_dx / edge_len
        lx = int(mid_x + perp_x * _LABEL_PERP)
        ly = int(mid_y + perp_y * _LABEL_PERP)
        # Stagger labels for parallel edges (same src→dst pair)
        _par = parallel_edge_idx.get(edge_i, 0)
        if _par:
            lx = int(lx + perp_x * 12 * _par)
            ly = int(ly + perp_y * 12 * _par)
        rot = 90 if abs(edge_dy) > abs(edge_dx) * 1.5 else 0
        result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                       "lx": lx, "ly": ly, "rot": rot})

    return result

