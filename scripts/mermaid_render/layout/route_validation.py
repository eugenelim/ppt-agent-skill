"""Routing-layer hard-invariant validation (ini-004 spec 5).

Checks RouteCandidate + PortReservation objects against the invariants from the
initiative brief. Does not touch FinalizedLayout or _geometry.py.

Public API:
  ValidationError  — NamedTuple: edge_id, rule, detail
  validate_routes  — runs all invariant checks; returns list[ValidationError]
"""
from __future__ import annotations

import math
from typing import NamedTuple

from mermaid_render.layout.port_planner import (
    GateAperture,
    PortReservation,
    RouteCandidate,
    RoutePermissions,
    RoutingObstacle,
)

# Old RoutingObstacle.kind values that map to the new six-value set.
_KIND_ALIASES: dict[str, str] = {
    "node": "NODE_INTERIOR",
    "group": "GROUP_INTERIOR",
    "title_band": "GROUP_TITLE",
}

# Kinds that indicate an obstacle that blocks interior traversal.
_BLOCKING_KINDS = frozenset({
    "NODE_INTERIOR", "GROUP_INTERIOR", "GROUP_BOUNDARY", "GROUP_TITLE",
    "node", "group", "title_band",  # old values kept for back-compat
})


class ValidationError(NamedTuple):
    edge_id: str
    rule: str    # short identifier, e.g. "port_on_reservation"
    detail: str  # human-readable description


def validate_routes(
    routes: list[RouteCandidate],
    reservations: dict[str, PortReservation] | None = None,
    obstacles: list[RoutingObstacle] | None = None,
    canvas_bounds: tuple[float, float, float, float] | None = None,
    marker_depths: dict[str, float] | None = None,
    route_permissions: list[RoutePermissions] | None = None,
    gate_apertures: list[GateAperture] | None = None,
) -> list[ValidationError]:
    """Validate routes against all routing-layer hard invariants.

    Returns every violation found; never raises for invariant failures.
    Output order: per-edge checks in routes order, then cross-route shared-segment checks.

    route_permissions / gate_apertures: when both are supplied, per-edge gate
    permission checks are applied (AC4/AC5). When either is None, gate checking
    is skipped and existing obstacle checks are unchanged.
    """
    reservations = reservations or {}
    obstacles = obstacles or []
    marker_depths = marker_depths or {}

    # Build per-edge permission and aperture lookups when supplied.
    perm_by_edge: dict[str, RoutePermissions] = {}
    apertures_by_edge: dict[str, list[GateAperture]] = {}
    if route_permissions is not None and gate_apertures is not None:
        for rp in route_permissions:
            perm_by_edge[rp.edge_id] = rp
        for ga in gate_apertures:
            apertures_by_edge.setdefault(ga.edge_id, []).append(ga)

    errors: list[ValidationError] = []

    for route in routes:
        route_errors = _check_single_route(route, reservations, obstacles, canvas_bounds, marker_depths)
        errors.extend(route_errors)
        if perm_by_edge:
            perm = perm_by_edge.get(route.edge_id)
            apertures = apertures_by_edge.get(route.edge_id, [])
            if perm is not None:
                errors.extend(_check_gate_permissions(route, perm, apertures, obstacles))

    errors.extend(_check_shared_segments(routes))
    return errors


# ── Per-route checks ──────────────────────────────────────────────────────────

def _check_single_route(
    route: RouteCandidate,
    reservations: dict[str, PortReservation],
    obstacles: list[RoutingObstacle],
    canvas_bounds: tuple[float, float, float, float] | None,
    marker_depths: dict[str, float],
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    eid = route.edge_id
    pts = route.points

    # Degenerate guard — must run before any check that indexes into pts
    if len(pts) < 2:
        errors.append(ValidationError(eid, "malformed_route", f"route has {len(pts)} waypoint(s); need ≥ 2"))
        return errors

    first_len = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    last_len = math.hypot(pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])

    if first_len < 1e-9:
        errors.append(ValidationError(eid, "malformed_route", "first segment has zero length"))
        return errors
    if last_len < 1e-9:
        errors.append(ValidationError(eid, "malformed_route", "last segment has zero length"))
        return errors

    errors.extend(_check_port_on_reservation(route, reservations))
    errors.extend(_check_route_endpoints(route))
    errors.extend(_check_axis_aligned(route))
    errors.extend(_check_port_normals(route))
    errors.extend(_check_terminal_length(route, marker_depths))
    errors.extend(_check_dogleg(route))
    errors.extend(_check_obstacles(route, obstacles))
    if canvas_bounds is not None:
        errors.extend(_check_canvas(route, canvas_bounds))
    return errors


def _check_port_on_reservation(
    route: RouteCandidate,
    reservations: dict[str, PortReservation],
) -> list[ValidationError]:
    res = reservations.get(route.edge_id)
    if res is None:
        return []
    errors = []
    sp = route.source_port.point
    rp = res.port_candidate.point
    if abs(sp[0] - rp[0]) > 1e-6 or abs(sp[1] - rp[1]) > 1e-6:
        errors.append(ValidationError(
            route.edge_id, "port_on_reservation",
            f"source_port {sp} != reservation.port_candidate {rp}",
        ))
    return errors


def _check_route_endpoints(route: RouteCandidate) -> list[ValidationError]:
    errors = []
    pts = route.points
    sp = route.source_port.point
    tp = route.target_port.point
    if abs(pts[0][0] - sp[0]) > 1e-6 or abs(pts[0][1] - sp[1]) > 1e-6:
        errors.append(ValidationError(
            route.edge_id, "route_start",
            f"points[0] {pts[0]} != source_port.point {sp}",
        ))
    if abs(pts[-1][0] - tp[0]) > 1e-6 or abs(pts[-1][1] - tp[1]) > 1e-6:
        errors.append(ValidationError(
            route.edge_id, "route_end",
            f"points[-1] {pts[-1]} != target_port.point {tp}",
        ))
    return errors


def _check_axis_aligned(route: RouteCandidate) -> list[ValidationError]:
    errors = []
    pts = route.points
    eid = route.edge_id
    dx0, dy0 = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
    if abs(dx0) >= 1e-9 and abs(dy0) >= 1e-9:
        errors.append(ValidationError(
            eid, "axis_aligned_terminal",
            f"first segment ({pts[0]}→{pts[1]}) is not axis-aligned (Δx={dx0:.4g}, Δy={dy0:.4g})",
        ))
    dx1, dy1 = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
    if abs(dx1) >= 1e-9 and abs(dy1) >= 1e-9:
        errors.append(ValidationError(
            eid, "axis_aligned_terminal",
            f"last segment ({pts[-2]}→{pts[-1]}) is not axis-aligned (Δx={dx1:.4g}, Δy={dy1:.4g})",
        ))
    return errors


def _unit(dx: float, dy: float) -> tuple[float, float]:
    mag = math.sqrt(dx * dx + dy * dy)
    return (dx / mag, dy / mag)


def _check_port_normals(route: RouteCandidate) -> list[ValidationError]:
    errors = []
    pts = route.points
    eid = route.edge_id

    # Source: first segment direction must agree with source outward_normal
    snx, sny = route.source_port.outward_normal
    if abs(snx) > 1e-12 or abs(sny) > 1e-12:
        ux, uy = _unit(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
        if abs(ux - snx) > 1e-9 or abs(uy - sny) > 1e-9:
            errors.append(ValidationError(
                eid, "port_normal_source",
                f"first segment direction ({ux:.4g},{uy:.4g}) != source outward_normal ({snx},{sny})",
            ))

    # Target: last segment direction must agree with negated target outward_normal
    tnx, tny = route.target_port.outward_normal
    if abs(tnx) > 1e-12 or abs(tny) > 1e-12:
        ux, uy = _unit(pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
        neg_tnx, neg_tny = -tnx, -tny
        if abs(ux - neg_tnx) > 1e-9 or abs(uy - neg_tny) > 1e-9:
            errors.append(ValidationError(
                eid, "port_normal_target",
                f"last segment direction ({ux:.4g},{uy:.4g}) != negated target normal ({neg_tnx},{neg_tny})",
            ))
    return errors


def _check_terminal_length(
    route: RouteCandidate,
    marker_depths: dict[str, float],
) -> list[ValidationError]:
    errors = []
    pts = route.points
    eid = route.edge_id

    # First (source) terminal: min 4 px
    first_len = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    if first_len < 4.0:
        errors.append(ValidationError(
            eid, "terminal_length",
            f"first segment length {first_len:.4g} < 4.0 px minimum",
        ))

    # Last (target) terminal: min marker_depth + 4 px
    depth = marker_depths.get(eid, 0.0)
    min_last = depth + 4.0
    last_len = math.hypot(pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
    if last_len < min_last:
        errors.append(ValidationError(
            eid, "terminal_length",
            f"last segment length {last_len:.4g} < {min_last:.4g} px (marker_depth={depth}+4)",
        ))
    return errors


def _check_dogleg(route: RouteCandidate) -> list[ValidationError]:
    errors = []
    pts = route.points
    n = len(pts)
    # Intermediate segments: indices 1..n-3 (both terminals exempt); requires ≥ 4 waypoints
    for i in range(1, n - 2):
        seg_len = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        if seg_len < 4.0:
            errors.append(ValidationError(
                route.edge_id, "dogleg_too_short",
                f"intermediate segment [{i}→{i+1}] length {seg_len:.4g} < 4 px",
            ))
    return errors


def _segment_aabb_intersects(
    ax: float, ay: float, bx: float, by: float,
    ox: float, oy: float, ow: float, oh: float,
) -> bool:
    """Liang-Barsky parametric AABB–segment test.

    Returns True when the segment (A→B) passes through the AABB interior.
    Collinear-with-boundary (parallel + touching edge) returns False.
    """
    dx, dy = bx - ax, by - ay
    t0, t1 = 0.0, 1.0

    for p, q in (
        (-dx, ax - ox),          # left
        (dx, ox + ow - ax),      # right
        (-dy, ay - oy),          # top
        (dy, oy + oh - ay),      # bottom
    ):
        if abs(p) < 1e-12:
            # Segment parallel to this slab
            if q <= 0:
                return False   # outside or on the boundary; not interior
            # else inside the slab; continue
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)

    # Strict interior intersection: t0 < t1 and window overlaps (0,1)
    return t0 < t1 and t1 > 1e-9 and t0 < 1.0 - 1e-9


def _check_obstacles(
    route: RouteCandidate,
    obstacles: list[RoutingObstacle],
) -> list[ValidationError]:
    errors = []
    pts = route.points
    eid = route.edge_id
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        for obs in obstacles:
            # Accept both old and new kind values; silently skip LABEL/MARKER_CLEARANCE/BOUNDARY.
            canonical = _KIND_ALIASES.get(obs.kind, obs.kind)
            if canonical not in ("NODE_INTERIOR", "GROUP_INTERIOR", "GROUP_TITLE"):
                continue
            ox, oy, ow, oh = obs.bounds
            if _segment_aabb_intersects(ax, ay, bx, by, ox, oy, ow, oh):
                errors.append(ValidationError(
                    eid, "obstacle_intersection",
                    f"segment [{i}→{i+1}] intersects {obs.kind} {obs.obstacle_id!r}",
                ))
    return errors


def _check_gate_permissions(
    route: RouteCandidate,
    perm: RoutePermissions,
    apertures: list[GateAperture],
    obstacles: list[RoutingObstacle],
) -> list[ValidationError]:
    """Check per-edge gate permissions for cross-boundary routes.

    Reports ValidationErrors for:
    - GROUP_BOUNDARY crossings outside the assigned GateAperture
    - GROUP_TITLE crossings
    - Unrelated GROUP_INTERIOR traversals
    - Re-entry into the same group
    """
    errors: list[ValidationError] = []
    pts = route.points
    eid = route.edge_id

    # Build aperture lookup keyed by group_id for this edge.
    aperture_by_group: dict[str, GateAperture] = {ga.group_id: ga for ga in apertures}

    # Track which groups the route has already left (for re-entry detection).
    entered_groups: set[str] = set()
    exited_groups: set[str] = set()

    allowed_scopes = (
        set(perm.source_scope_chain)
        | set(perm.target_scope_chain)
        | set(perm.common_ancestor_ids)
    )

    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        for obs in obstacles:
            canonical = _KIND_ALIASES.get(obs.kind, obs.kind)

            if canonical == "GROUP_TITLE":
                ox, oy, ow, oh = obs.bounds
                if _segment_aabb_intersects(ax, ay, bx, by, ox, oy, ow, oh):
                    errors.append(ValidationError(
                        eid, "gate_title_crossing",
                        f"segment [{i}→{i+1}] crosses GROUP_TITLE of {obs.obstacle_id!r}",
                    ))

            elif canonical == "GROUP_INTERIOR":
                if obs.obstacle_id not in allowed_scopes:
                    ox, oy, ow, oh = obs.bounds
                    if _segment_aabb_intersects(ax, ay, bx, by, ox, oy, ow, oh):
                        errors.append(ValidationError(
                            eid, "gate_unrelated_group",
                            f"segment [{i}→{i+1}] crosses unrelated GROUP_INTERIOR {obs.obstacle_id!r}",
                        ))

            elif canonical == "GROUP_BOUNDARY":
                gid = obs.obstacle_id
                ox, oy, ow, oh = obs.bounds
                if _segment_aabb_intersects(ax, ay, bx, by, ox, oy, ow, oh):
                    # Check re-entry
                    if gid in exited_groups:
                        errors.append(ValidationError(
                            eid, "gate_reentry",
                            f"segment [{i}→{i+1}] re-enters group {gid!r}",
                        ))
                    # Check aperture: crossing must be within the assigned aperture
                    aperture = aperture_by_group.get(gid)
                    if aperture is None:
                        errors.append(ValidationError(
                            eid, "gate_violation",
                            f"segment [{i}→{i+1}] crosses GROUP_BOUNDARY {gid!r} with no assigned aperture",
                        ))
                    else:
                        # Compute crossing midpoint along the boundary
                        mid_x, mid_y = (ax + bx) / 2.0, (ay + by) / 2.0
                        cx, cy = aperture.center
                        if aperture.side in ("top", "bottom"):
                            deviation = abs(mid_x - cx)
                        else:
                            deviation = abs(mid_y - cy)
                        if deviation > aperture.half_width + 1e-6:
                            errors.append(ValidationError(
                                eid, "gate_violation",
                                f"segment [{i}→{i+1}] crosses GROUP_BOUNDARY {gid!r} "
                                f"{deviation:.1f}px outside aperture (half_width={aperture.half_width})",
                            ))
                    # Mark exit if the segment leaves a group we were inside
                    if gid in entered_groups:
                        exited_groups.add(gid)
                    else:
                        entered_groups.add(gid)

    return errors


def _check_canvas(
    route: RouteCandidate,
    canvas_bounds: tuple[float, float, float, float],
) -> list[ValidationError]:
    errors = []
    cx, cy, cw, ch = canvas_bounds
    for i, (px, py) in enumerate(route.points):
        if not (cx <= px <= cx + cw and cy <= py <= cy + ch):
            errors.append(ValidationError(
                route.edge_id, "canvas_bounds",
                f"points[{i}] ({px:.4g},{py:.4g}) outside canvas ({cx},{cy},{cx+cw},{cy+ch})",
            ))
    return errors


# ── Cross-route checks ────────────────────────────────────────────────────────

def _check_shared_segments(routes: list[RouteCandidate]) -> list[ValidationError]:
    """Detect pairs of routes sharing an axis-aligned segment > 8 px."""
    errors: list[ValidationError] = []
    n = len(routes)
    for i in range(n):
        for j in range(i + 1, n):
            ri, rj = routes[i], routes[j]
            overlap = _max_shared_overlap(ri.points, rj.points)
            if overlap > 8.0:
                errors.append(ValidationError(
                    ri.edge_id, "shared_segment",
                    f"shares segment of {overlap:.4g} px with edge {rj.edge_id!r}",
                ))
                errors.append(ValidationError(
                    rj.edge_id, "shared_segment",
                    f"shares segment of {overlap:.4g} px with edge {ri.edge_id!r}",
                ))
    return errors


def _max_shared_overlap(
    pts_i: tuple[tuple[float, float], ...],
    pts_j: tuple[tuple[float, float], ...],
) -> float:
    """Return the maximum overlapping length between any co-linear segment pair."""
    max_overlap = 0.0
    for a in range(len(pts_i) - 1):
        ix0, iy0 = pts_i[a]
        ix1, iy1 = pts_i[a + 1]
        for b in range(len(pts_j) - 1):
            jx0, jy0 = pts_j[b]
            jx1, jy1 = pts_j[b + 1]

            # Horizontal pair: same y within 1e-9
            if abs(iy0 - iy1) < 1e-9 and abs(jy0 - jy1) < 1e-9 and abs(iy0 - jy0) < 1e-9:
                lo_i, hi_i = min(ix0, ix1), max(ix0, ix1)
                lo_j, hi_j = min(jx0, jx1), max(jx0, jx1)
                overlap = min(hi_i, hi_j) - max(lo_i, lo_j)
                if overlap > max_overlap:
                    max_overlap = overlap

            # Vertical pair: same x within 1e-9
            elif abs(ix0 - ix1) < 1e-9 and abs(jx0 - jx1) < 1e-9 and abs(ix0 - jx0) < 1e-9:
                lo_i, hi_i = min(iy0, iy1), max(iy0, iy1)
                lo_j, hi_j = min(jy0, jy1), max(jy0, jy1)
                overlap = min(hi_i, hi_j) - max(lo_i, lo_j)
                if overlap > max_overlap:
                    max_overlap = overlap

    return max_overlap
