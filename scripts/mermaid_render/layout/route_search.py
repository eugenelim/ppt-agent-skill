"""Routing search and global edge assignment (ini-004 spec 2).

Provides public functions that turn port candidates into costed route
candidates and assign one final route to every edge via a bounded
rip-up/reroute pass. Also provides local_channel_route() for bounded
multi-rank channel routing (ini-005 flowchart-routing-closure).
"""
from __future__ import annotations

from typing import Any

from mermaid_render.layout.port_planner import (
    PortCandidate,
    RouteCandidate,
    RoutingObstacle,
)

# ── Local channel constants (ini-005) ─────────────────────────────────────────

MAX_LOCAL_EXCURSION: float = 48.0  # max px a channel may extend beyond local_bounds
LOCAL_LANE_GAP: float = 16.0       # gap between local_bounds edge and first channel
LANE_PITCH: float = 14.0           # px between staggered channels


# ── Cost function ─────────────────────────────────────────────────────────────

def compute_route_cost(
    rc: RouteCandidate,
    *,
    port_collision_count: int = 0,
    label_overlap_count: int = 0,
    near_obstacle_penalty: float = 0.0,
    nonpreferred_side_count: int = 0,
    aligned_endpoint_count: int = 0,
) -> float:
    """Compute deterministic cost for a route candidate.

    zero_bend_route_count is derived internally (1 if bend_count == 0 else 0).
    """
    zero_bend = 1 if rc.bend_count == 0 else 0
    return (
        rc.length
        + 80.0 * rc.bend_count
        + 180.0 * rc.crossing_count
        + 12.0 * rc.shared_segment_length
        + 120.0 * label_overlap_count
        + 100.0 * port_collision_count
        + 60.0 * near_obstacle_penalty
        + 50.0 * nonpreferred_side_count
        - 160.0 * zero_bend
        - 60.0 * aligned_endpoint_count
    )


# ── Route-form builders ───────────────────────────────────────────────────────

def _route_length(points: tuple[tuple[float, float], ...]) -> float:
    total = 0.0
    for i in range(len(points) - 1):
        ax, ay = points[i]
        bx, by = points[i + 1]
        total += abs(bx - ax) + abs(by - ay)
    return total


def _shared_segment_length(
    points: tuple[tuple[float, float], ...],
    existing_routes: tuple[RouteCandidate, ...],
) -> float:
    """Sum of overlapping segment lengths against all existing routes (> 0 px)."""
    total = 0.0
    my_segs = _segments(points)
    for er in existing_routes:
        other_segs = _segments(er.points)
        for (ax1, ay1), (ax2, ay2) in my_segs:
            for (bx1, by1), (bx2, by2) in other_segs:
                overlap = _axis_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2)
                if overlap > 0.0:
                    total += overlap
    return total


def _segments(
    points: tuple[tuple[float, float], ...],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def _axis_overlap(
    ax1: float, ay1: float, ax2: float, ay2: float,
    bx1: float, by1: float, bx2: float, by2: float,
) -> float:
    """Return px overlap between two co-axis segments, or 0."""
    # Horizontal segment pair
    if abs(ay1 - ay2) < 1e-9 and abs(by1 - by2) < 1e-9 and abs(ay1 - by1) < 1e-9:
        a_lo, a_hi = min(ax1, ax2), max(ax1, ax2)
        b_lo, b_hi = min(bx1, bx2), max(bx1, bx2)
        return max(0.0, min(a_hi, b_hi) - max(a_lo, b_lo))
    # Vertical segment pair
    if abs(ax1 - ax2) < 1e-9 and abs(bx1 - bx2) < 1e-9 and abs(ax1 - bx1) < 1e-9:
        a_lo, a_hi = min(ay1, ay2), max(ay1, ay2)
        b_lo, b_hi = min(by1, by2), max(by1, by2)
        return max(0.0, min(a_hi, b_hi) - max(a_lo, b_lo))
    return 0.0


def _make_rc(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
    points: tuple[tuple[float, float], ...],
    bend_count: int,
    existing_routes: tuple[RouteCandidate, ...] = (),
) -> RouteCandidate:
    length = _route_length(points)
    shared = _shared_segment_length(points, existing_routes)
    rc = RouteCandidate(
        edge_id=edge_id,
        source_port=src_port,
        target_port=dst_port,
        points=points,
        bend_count=bend_count,
        length=length,
        crossing_count=0,
        shared_segment_length=shared,
        cost=0.0,
    )
    cost = compute_route_cost(rc)
    return RouteCandidate(
        edge_id=edge_id,
        source_port=src_port,
        target_port=dst_port,
        points=points,
        bend_count=bend_count,
        length=length,
        crossing_count=0,
        shared_segment_length=shared,
        cost=cost,
    )


def try_direct_route(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
    existing_routes: tuple[RouteCandidate, ...] = (),
) -> RouteCandidate | None:
    """Return a zero-bend route when src and dst share an axis within 1e-9."""
    sx, sy = src_port.point
    dx, dy = dst_port.point
    if abs(sx - dx) < 1e-9 or abs(sy - dy) < 1e-9:
        points = (src_port.point, dst_port.point)
        return _make_rc(edge_id, src_port, dst_port, points, 0, existing_routes)
    return None


def try_l_route(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
    existing_routes: tuple[RouteCandidate, ...] = (),
) -> list[RouteCandidate]:
    """Return up to two one-bend (L) route candidates: hv and vh variants."""
    sx, sy = src_port.point
    dx, dy = dst_port.point
    results: list[RouteCandidate] = []
    # hv: horizontal then vertical; corner at (dx, sy)
    results.append(_make_rc(
        edge_id, src_port, dst_port,
        ((sx, sy), (dx, sy), (dx, dy)),
        1, existing_routes,
    ))
    # vh: vertical then horizontal; corner at (sx, dy)
    results.append(_make_rc(
        edge_id, src_port, dst_port,
        ((sx, sy), (sx, dy), (dx, dy)),
        1, existing_routes,
    ))
    return results


def try_z_route(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
    existing_routes: tuple[RouteCandidate, ...] = (),
) -> list[RouteCandidate]:
    """Return up to two two-bend (Z) candidates via mid-x or mid-y pivot."""
    sx, sy = src_port.point
    dx, dy = dst_port.point
    results: list[RouteCandidate] = []
    # mid-x pivot
    mid_x = (sx + dx) / 2.0
    results.append(_make_rc(
        edge_id, src_port, dst_port,
        ((sx, sy), (mid_x, sy), (mid_x, dy), (dx, dy)),
        2, existing_routes,
    ))
    # mid-y pivot
    mid_y = (sy + dy) / 2.0
    results.append(_make_rc(
        edge_id, src_port, dst_port,
        ((sx, sy), (sx, mid_y), (dx, mid_y), (dx, dy)),
        2, existing_routes,
    ))
    return results


def local_channel_route(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
    local_bounds: tuple[float, float, float, float],  # (x, y, w, h) bounding the obstruction
    existing_routes: tuple[RouteCandidate, ...] = (),
    lane_index: int = 0,
) -> RouteCandidate | None:
    """Try a bounded left or right local channel route between two ports.

    Computes left_x and right_x as channel x-coordinates relative to local_bounds,
    then builds an orthogonal 4-point route via each channel. Rejects any candidate
    containing a waypoint outside local_bounds inflated by MAX_LOCAL_EXCURSION.
    Returns the lower-cost valid candidate, or None if no valid channel exists.

    Route shape (TB direction example):
        src_port.point → (channel_x, src_y) → (channel_x, dst_y) → dst_port.point
    """
    bx, by, bw, bh = local_bounds
    inflate = MAX_LOCAL_EXCURSION

    # Inflated bounds check
    allowed_x_min = bx - inflate
    allowed_x_max = bx + bw + inflate
    allowed_y_min = by - inflate
    allowed_y_max = by + bh + inflate

    def _within_bounds(pts: tuple[tuple[float, float], ...]) -> bool:
        for px, py in pts:
            if px < allowed_x_min or px > allowed_x_max:
                return False
            if py < allowed_y_min or py > allowed_y_max:
                return False
        return True

    sx, sy = src_port.point
    dx, dy = dst_port.point

    candidates: list[RouteCandidate] = []
    for side in ("left", "right"):
        if side == "left":
            channel_x = bx - LOCAL_LANE_GAP - lane_index * LANE_PITCH
        else:
            channel_x = bx + bw + LOCAL_LANE_GAP + lane_index * LANE_PITCH

        pts: tuple[tuple[float, float], ...] = (
            (sx, sy),
            (channel_x, sy),
            (channel_x, dy),
            (dx, dy),
        )
        if not _within_bounds(pts):
            continue
        rc = _make_rc(edge_id, src_port, dst_port, pts, 2, existing_routes)
        candidates.append(rc)

    if not candidates:
        return None
    return min(candidates, key=lambda c: c.cost)


# ── Validity check ────────────────────────────────────────────────────────────

def _segment_intersects_aabb(
    ax: float, ay: float, bx: float, by: float,
    ox: float, oy: float, ow: float, oh: float,
) -> bool:
    """True when segment AB intersects axis-aligned bounding box (x,y,w,h)."""
    # Separating axis: segment is axis-aligned (orthogonal routing guarantee)
    rx1, ry1, rx2, ry2 = ox, oy, ox + ow, oy + oh
    sx, sy = min(ax, bx), min(ay, by)
    ex, ey = max(ax, bx), max(ay, by)
    # No overlap on x axis
    if ex < rx1 or sx > rx2:
        return False
    # No overlap on y axis
    if ey < ry1 or sy > ry2:
        return False
    return True


def _is_valid_route(
    rc: RouteCandidate,
    obstacles: tuple[RoutingObstacle, ...] = (),
) -> bool:
    """Return False when any segment of rc intersects any obstacle's AABB."""
    for (ax, ay), (bx, by) in _segments(rc.points):
        for ob in obstacles:
            ox, oy, ow, oh = ob.bounds
            if _segment_intersects_aabb(ax, ay, bx, by, ox, oy, ow, oh):
                return False
    return True


# ── route_edge ────────────────────────────────────────────────────────────────

def route_edge(
    edge_id: str,
    src_port: PortCandidate,
    dst_port: PortCandidate,
    obstacles: tuple[RoutingObstacle, ...] = (),
    existing_routes: tuple[RouteCandidate, ...] = (),
) -> RouteCandidate | None:
    """Try direct → L → Z and return lowest-cost valid candidate, or None."""
    candidates: list[RouteCandidate] = []
    direct = try_direct_route(edge_id, src_port, dst_port, existing_routes)
    if direct is not None:
        candidates.append(direct)
    candidates.extend(try_l_route(edge_id, src_port, dst_port, existing_routes))
    candidates.extend(try_z_route(edge_id, src_port, dst_port, existing_routes))
    valid = [c for c in candidates if _is_valid_route(c, obstacles)]
    if not valid:
        return None
    return min(valid, key=lambda c: c.cost)


# ── prioritize_edges ──────────────────────────────────────────────────────────

def prioritize_edges(
    edge_ids: list[str],
    fixed_side_ids: set[str],
    cross_scope_ids: set[str],
    high_degree_ids: set[str],
    zero_bend_ids: set[str],
) -> list[str]:
    """Return edge_ids ordered by priority group (first-match wins for multi-group).

    Order: fixed_side → cross_scope → high_degree → zero_bend → remaining.
    Stable within each group.
    """
    groups: list[list[str]] = [[], [], [], [], []]
    seen: set[str] = set()
    for eid in edge_ids:
        if eid in seen:
            continue
        seen.add(eid)
        if eid in fixed_side_ids:
            groups[0].append(eid)
        elif eid in cross_scope_ids:
            groups[1].append(eid)
        elif eid in high_degree_ids:
            groups[2].append(eid)
        elif eid in zero_bend_ids:
            groups[3].append(eid)
        else:
            groups[4].append(eid)
    result: list[str] = []
    for g in groups:
        result.extend(g)
    return result


# ── assign_routes ─────────────────────────────────────────────────────────────

def _find_conflict(
    assignments: dict[str, RouteCandidate],
) -> tuple[str, str] | None:
    """Return the first pair (eid_a, eid_b) with shared segment > 8 px, or None."""
    items = list(assignments.items())
    for i in range(len(items)):
        eid_a, rc_a = items[i]
        for j in range(i + 1, len(items)):
            eid_b, rc_b = items[j]
            segs_a = _segments(rc_a.points)
            segs_b = _segments(rc_b.points)
            for (ax1, ay1), (ax2, ay2) in segs_a:
                for (bx1, by1), (bx2, by2) in segs_b:
                    overlap = _axis_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2)
                    if overlap > 8.0:
                        return (eid_a, eid_b)
    return None


def assign_routes(
    requests: list[dict[str, Any]],
    obstacles: tuple[RoutingObstacle, ...] = (),
    max_iterations: int = 10,
) -> dict[str, RouteCandidate]:
    """Route all edges; bounded rip-up/reroute for segment conflicts > 8 px.

    Each request: {"edge_id": str, "src_port": PortCandidate, "dst_port": PortCandidate}.
    Unroutable edges are absent from the result. Runs deterministically;
    identical inputs produce identical output. Post-cap: returns best-effort
    with remaining conflicts left as-is.

    Shared-segment detection is O(n²) in edge count; acceptable for < 50 edges.
    """
    # Initial routing pass
    assignments: dict[str, RouteCandidate] = {}
    req_map: dict[str, dict[str, Any]] = {r["edge_id"]: r for r in requests}
    for req in requests:
        eid = req["edge_id"]
        existing = tuple(assignments.values())
        result = route_edge(eid, req["src_port"], req["dst_port"], obstacles, existing)
        if result is not None:
            assignments[eid] = result

    # Rip-up/reroute loop
    for _ in range(max_iterations):
        conflict = _find_conflict(assignments)
        if conflict is None:
            break
        eid_a, eid_b = conflict
        rc_a = assignments[eid_a]
        rc_b = assignments[eid_b]
        # Rip up the higher-cost route
        if rc_a.cost >= rc_b.cost:
            rip_eid = eid_a
        else:
            rip_eid = eid_b
        del assignments[rip_eid]
        # Reroute with updated existing routes
        req = req_map[rip_eid]
        existing = tuple(assignments.values())
        result = route_edge(
            rip_eid, req["src_port"], req["dst_port"], obstacles, existing
        )
        if result is not None:
            assignments[rip_eid] = result

    return assignments
