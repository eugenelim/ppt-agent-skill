"""Port-aware routing data model and port-pair planning (ini-004 spec 1).

Provides immutable data structures and planning functions that give all
diagram-type renderers a shared vocabulary for port candidates, route
candidates, port reservations, routing obstacles, route permissions, and
gate apertures.
"""
from __future__ import annotations

import math
from typing import NamedTuple, Any


# ── Fan distribution constants (ini-005 flowchart-routing-closure) ────────────

FAN_EDGE_PADDING: float = 12.0   # px from face edge to first/last port
FAN_MIN_PORT_PITCH: float = 24.0  # minimum px between adjacent fan ports
FAN_ESCAPE_LENGTH: float = 20.0   # minimum straight exclusive segment after leaving a fan node
FAN_CHANNEL_PITCH: float = 14.0   # px between staggered fan channels


# ── Data structures ───────────────────────────────────────────────────────────

class PortCandidate(NamedTuple):
    """A candidate port location on a node boundary for a specific edge."""

    edge_id: str
    node_id: str
    side: str  # "top" | "right" | "bottom" | "left" | "center"
    normalized_offset: float  # 0.0–1.0 along the side
    point: tuple[float, float]  # absolute canvas coordinates
    outward_normal: tuple[float, float]  # unit vector pointing away from shape
    fixed_side: bool  # True when source syntax fixed the side
    preference_penalty: float  # 0.0 = preferred; higher = penalised


class PortReservation(NamedTuple):
    """A confirmed port assignment for an edge endpoint."""

    edge_id: str
    node_id: str
    port_candidate: PortCandidate
    terminal_clearance: float  # min px the terminal segment must have
    escape_point: tuple[float, float]  # first waypoint after leaving the node


class RouteCandidate(NamedTuple):
    """A candidate orthogonal polyline route for a specific edge."""

    edge_id: str
    source_port: PortCandidate
    target_port: PortCandidate
    points: tuple[tuple[float, float], ...]  # orthogonal polyline waypoints
    bend_count: int
    length: float
    crossing_count: int
    shared_segment_length: float
    cost: float


class RoutingObstacle(NamedTuple):
    """A region of the canvas that routes must not intersect without a gate.

    kind values (new six-value set; old values remain accepted for back-compat):
      "NODE_INTERIOR"    — interior of a leaf node (old: "node")
      "GROUP_INTERIOR"   — interior of a compound group (old: "group")
      "GROUP_BOUNDARY"   — the boundary ring of a compound group
      "GROUP_TITLE"      — the measured title-label rectangle of a group (old: "title_band")
      "LABEL"            — an edge label chip
      "MARKER_CLEARANCE" — clearance zone around an arrowhead marker

    Old values "node", "group", "title_band" are still accepted by callers and
    by route_validation._check_obstacles (aliased to the new names internally).
    """

    obstacle_id: str  # keyed by region ID, not edge_id
    kind: str  # see docstring above
    bounds: tuple[float, float, float, float]  # x, y, w, h
    scope_id: str | None
    title_bounds: tuple[float, float, float, float] | None
    permitted_gate_ids: frozenset[str]  # gate IDs through which routes may cross


class RoutePermissions(NamedTuple):
    """Per-edge permission record for cross-boundary routing.

    Produced by the flowchart adapter for every edge that crosses one or more
    group boundaries. validate_routes() uses this to enforce that the route
    only crosses its own group boundaries at the assigned gates.
    """

    edge_id: str
    source_scope_chain: tuple[str, ...]  # group IDs from source node up to root
    target_scope_chain: tuple[str, ...]  # group IDs from target node up to root
    common_ancestor_ids: tuple[str, ...]  # groups that contain both endpoints
    permitted_gate_ids: tuple[str, ...]  # gate IDs this edge is allowed to cross


class GateAperture(NamedTuple):
    """A permitted crossing point on a group boundary for one specific edge.

    Produced alongside RoutePermissions for cross-boundary edges. The aperture
    defines the exact region of the boundary through which the edge may cross.
    validate_routes() rejects a crossing that falls outside the aperture.
    """

    gate_id: str
    edge_id: str
    group_id: str
    side: str  # "top" | "right" | "bottom" | "left"
    center: tuple[float, float]  # absolute canvas center of the aperture
    half_width: float  # half-width of the allowed crossing window (px)


class TerminalAttachment(NamedTuple):
    """Resolved terminal geometry for one endpoint of a flowchart edge.

    boundary_point: canvas-absolute point on the shape outline.
    outward_normal: unit vector pointing away from the shape at boundary_point.
    escape_point: canvas-absolute point outside the shape along the normal.
    terminal_clearance: minimum px the terminal segment must occupy.
    side: semantic side ("top" | "right" | "bottom" | "left").
    face_id: polygon edge index (None for curved shapes, or at a corner = vertex index).
    at_corner: True when boundary_point is within epsilon of a polygon vertex.
    """

    boundary_point: tuple[float, float]
    outward_normal: tuple[float, float]
    escape_point: tuple[float, float]
    terminal_clearance: float
    side: str
    face_id: int | None
    at_corner: bool


# ── Side outward-normal lookup ────────────────────────────────────────────────

_SIDE_NORMALS: dict[str, tuple[float, float]] = {
    "top":    (0.0, -1.0),
    "right":  (1.0,  0.0),
    "bottom": (0.0,  1.0),
    "left":   (-1.0, 0.0),
    "center": (0.0,  0.0),
}

_PREFERRED_PENALTY: float = 0.0
_OTHER_SIDE_PENALTY: float = 25.0
_CENTER_PENALTY: float = 50.0


# ── Private helpers ───────────────────────────────────────────────────────────

def _aabb_anchor_point(
    side: str,
    offset: float,
    node_x: float,
    node_y: float,
    w: float,
    h: float,
) -> tuple[float, float]:
    """Compute canvas-absolute anchor via AABB interpolation (fallback path)."""
    if side == "top":
        return node_x + offset * w, node_y
    if side == "bottom":
        return node_x + offset * w, node_y + h
    if side == "left":
        return node_x, node_y + offset * h
    if side == "right":
        return node_x + w, node_y + offset * h
    return node_x + w / 2.0, node_y + h / 2.0


# ── Public API ────────────────────────────────────────────────────────────────

def build_edge_lists(edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Return mapping node_id → incident edge_ids (incoming + outgoing).

    Each edge dict must contain "edge_id", "source_id", and "target_id".
    Missing or None values are skipped silently.
    """
    result: dict[str, list[str]] = {}
    for edge in edges:
        eid = edge.get("edge_id")
        if not eid:
            continue
        for key in ("source_id", "target_id"):
            node = edge.get(key)
            if not node:
                continue
            if node not in result:
                result[node] = []
            if eid not in result[node]:
                result[node].append(eid)
    return result


def generate_port_candidates(
    node_id: str,
    node_bounds: tuple[float, float, float, float],  # (x, y, w, h) in canvas coords
    edge_id: str,
    fixed_side: str | None = None,
    shape_geometry: Any | None = None,
) -> list[PortCandidate]:
    """Generate PortCandidate list for an edge endpoint at a node.

    When fixed_side is set: exactly one candidate on that side.
    When fixed_side is None: preferred sides + other sides + center (five sides).

    shape_geometry: optional ShapeGeometry instance; when provided, boundary
    coordinates and outward normals come from attachment(). Falls back to AABB
    when shape_geometry is None or lacks the attachment() method.
    attachment() returns node-local (top-left origin) coords; (node_x, node_y)
    is added to produce canvas-absolute point. Center candidate is always
    (node_x + w/2, node_y + h/2) regardless of shape_geometry.
    """
    node_x, node_y, w, h = node_bounds

    def _make(side: str, offset: float, penalty: float, is_fixed: bool) -> PortCandidate:
        if side == "center":
            px, py = node_x + w / 2.0, node_y + h / 2.0
            return PortCandidate(
                edge_id=edge_id,
                node_id=node_id,
                side=side,
                normalized_offset=offset,
                point=(px, py),
                outward_normal=(0.0, 0.0),
                fixed_side=is_fixed,
                preference_penalty=penalty,
            )
        if shape_geometry is not None:
            try:
                att = shape_geometry.attachment(side, offset, w, h)
                px, py = node_x + att.point[0], node_y + att.point[1]
                normal = att.outward_normal
            except AttributeError:
                # shape_geometry predates attachment() — fall back to AABB
                px, py = _aabb_anchor_point(side, offset, node_x, node_y, w, h)
                normal = _SIDE_NORMALS.get(side, (0.0, 0.0))
        else:
            px, py = _aabb_anchor_point(side, offset, node_x, node_y, w, h)
            normal = _SIDE_NORMALS.get(side, (0.0, 0.0))
        return PortCandidate(
            edge_id=edge_id,
            node_id=node_id,
            side=side,
            normalized_offset=offset,
            point=(px, py),
            outward_normal=normal,
            fixed_side=is_fixed,
            preference_penalty=penalty,
        )

    if fixed_side is not None:
        return [_make(fixed_side, 0.5, _PREFERRED_PENALTY, True)]

    # Preferred sides (bottom, right), other sides (top, left), center.
    candidates: list[PortCandidate] = []
    for side in ("bottom", "right"):
        candidates.append(_make(side, 0.5, _PREFERRED_PENALTY, False))
    for side in ("top", "left"):
        candidates.append(_make(side, 0.5, _OTHER_SIDE_PENALTY, False))
    candidates.append(_make("center", 0.5, _CENTER_PENALTY, False))
    return candidates


def build_terminal_attachment(
    node_bounds: tuple[float, float, float, float],
    side: str,
    offset: float,
    shape_geometry: Any | None = None,
    marker_kind: str = "arrow",
    preferred_direction: tuple[float, float] | None = None,
    stub_length: float | None = None,
) -> TerminalAttachment:
    """Build a TerminalAttachment for one endpoint of a flowchart edge.

    Computes the exact boundary point and outward normal via shape_geometry.attachment()
    when available; falls back to AABB when shape_geometry is None or lacks attachment().
    The escape_point is boundary_point + outward_normal * terminal_clearance.

    node_bounds: (x, y, w, h) in canvas coordinates.
    side: "top" | "right" | "bottom" | "left".
    offset: 0.0–1.0 along the side.
    shape_geometry: ShapeGeometry instance or None.
    marker_kind: arrowhead kind, used to compute marker_clearance.
    preferred_direction: hint for vertex normal disambiguation.
    stub_length: override for terminal clearance (px); defaults to FAN_ESCAPE_LENGTH.
    """
    node_x, node_y, w, h = node_bounds
    face_id: int | None = None
    at_corner = False

    if shape_geometry is not None:
        try:
            att = shape_geometry.attachment(side, offset, w, h,
                                            preferred_direction=preferred_direction)
            bx, by = node_x + att.point[0], node_y + att.point[1]
            nx, ny = att.outward_normal
            face_id = att.face_id
            at_corner = att.at_corner
        except AttributeError:
            bx, by = _aabb_anchor_point(side, offset, node_x, node_y, w, h)
            nx, ny = _SIDE_NORMALS.get(side, (0.0, -1.0))
    else:
        bx, by = _aabb_anchor_point(side, offset, node_x, node_y, w, h)
        nx, ny = _SIDE_NORMALS.get(side, (0.0, -1.0))

    # Normalize defensively (should already be unit, but floating-point can drift)
    mag = math.hypot(nx, ny)
    if mag > 1e-9:
        nx, ny = nx / mag, ny / mag
    else:
        nx, ny = _SIDE_NORMALS.get(side, (0.0, -1.0))

    if stub_length is not None:
        clearance = stub_length
    else:
        clearance = FAN_ESCAPE_LENGTH
        if shape_geometry is not None and marker_kind:
            try:
                mc = shape_geometry.marker_clearance(marker_kind)
                clearance = max(clearance, mc)
            except AttributeError:
                pass
    ex, ey = bx + nx * clearance, by + ny * clearance

    return TerminalAttachment(
        boundary_point=(bx, by),
        outward_normal=(nx, ny),
        escape_point=(ex, ey),
        terminal_clearance=clearance,
        side=side,
        face_id=face_id,
        at_corner=at_corner,
    )


def plan_straight_corridor(
    src_bounds: tuple[float, float, float, float],
    dst_bounds: tuple[float, float, float, float],
) -> tuple[str, float] | None:
    """Detect a zero-bend straight-corridor opportunity between two nodes.

    Assumes direction-normalized inputs: src is the upstream node.
    The two guards are mutually exclusive: vertical fires when src is strictly
    above dst with x-axis overlap; horizontal fires when src is strictly left of
    dst with y-axis overlap. Both cannot fire simultaneously (AC13).

    Returns ("vertical", common_x), ("horizontal", common_y), or None.
    """
    sx, sy, sw, sh = src_bounds
    dx, dy, dw, dh = dst_bounds

    if sy + sh < dy:
        overlap_l = max(sx, dx)
        overlap_r = min(sx + sw, dx + dw)
        if overlap_r > overlap_l:
            return ("vertical", (overlap_l + overlap_r) / 2.0)

    if sx + sw < dx:
        overlap_t = max(sy, dy)
        overlap_b = min(sy + sh, dy + dh)
        if overlap_b > overlap_t:
            return ("horizontal", (overlap_t + overlap_b) / 2.0)

    return None


def fan_slots(
    edge_ids: list[str],
    side: str,
    face_length: float = 0.0,
) -> list[tuple[str, float]]:
    """Distribute edge_ids evenly along a side, returning (edge_id, normalized_offset) pairs.

    When face_length > 0 and N >= 2 (face-spanning mode):
      Ports are linearly interpolated between first_px and last_px (absolute pixel
      positions), then normalised by face_length. Offsets are always in [0, 1].
      Wide faces: first_px=FAN_EDGE_PADDING, last_px=face_length-FAN_EDGE_PADDING.
      Narrow faces (too small for FAN_MIN_PORT_PITCH spacing): ports are compressed
      into the available inset range — first_px=min(FAN_EDGE_PADDING,face_length/2),
      last_px=face_length-first_px — accepting sub-minimum pitch.

    When face_length <= 0 or N == 1 (back-compat / center mode):
      N=1: center (offset=0.5).
      N>1: original (i+1)/(N+1) formula — all values in (0,1) exclusive.
    """
    if not edge_ids:
        return []
    n = len(edge_ids)
    if n == 1:
        return [(edge_ids[0], 0.5)]

    if face_length <= 0.0:
        # Back-compat: original centre-compressed formula
        return [(eid, (i + 1) / (n + 1)) for i, eid in enumerate(edge_ids)]

    # Face-spanning: distribute between first_px and last_px
    required = 2.0 * FAN_EDGE_PADDING + (n - 1) * FAN_MIN_PORT_PITCH
    if face_length >= required:
        first_px = FAN_EDGE_PADDING
        last_px = face_length - FAN_EDGE_PADDING
    else:
        # Face too narrow: compress into available inset range; offsets always in [0, 1]
        first_px = min(FAN_EDGE_PADDING, face_length / 2.0)
        last_px = max(first_px, face_length - first_px)

    result: list[tuple[str, float]] = []
    for i, eid in enumerate(edge_ids):
        px = first_px + i * (last_px - first_px) / (n - 1) if n > 1 else (first_px + last_px) / 2.0
        result.append((eid, px / face_length))
    return result
