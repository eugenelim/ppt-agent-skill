"""Port-aware routing data model and port-pair planning (ini-004 spec 1).

Provides four immutable data structures and four planning functions that give
all diagram-type renderers a shared vocabulary for port candidates, route
candidates, port reservations, and routing obstacles.
"""
from __future__ import annotations

from typing import NamedTuple, Any


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
    """A region of the canvas that routes must not intersect without a gate."""

    obstacle_id: str  # keyed by region ID, not edge_id
    kind: str  # "node" | "group" | "title_band"
    bounds: tuple[float, float, float, float]  # x, y, w, h
    scope_id: str | None
    title_bounds: tuple[float, float, float, float] | None
    permitted_gate_ids: frozenset[str]  # gate IDs through which routes may cross


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

    shape_geometry: optional ShapeGeometry instance; when provided, exact
    boundary coordinates come from boundary_anchor(). Falls back to AABB.
    boundary_anchor returns node-local (top-left origin) coords; (node_x, node_y)
    is added to produce canvas-absolute point. Center candidate is always
    (node_x + w/2, node_y + h/2) regardless of shape_geometry.
    """
    node_x, node_y, w, h = node_bounds

    def _make(side: str, offset: float, penalty: float, is_fixed: bool) -> PortCandidate:
        if side == "center":
            px, py = node_x + w / 2.0, node_y + h / 2.0
        elif shape_geometry is not None:
            try:
                lx, ly = shape_geometry.boundary_anchor(side, offset, w, h)
                px, py = node_x + lx, node_y + ly
            except Exception:
                px, py = _aabb_anchor_point(side, offset, node_x, node_y, w, h)
        else:
            px, py = _aabb_anchor_point(side, offset, node_x, node_y, w, h)
        return PortCandidate(
            edge_id=edge_id,
            node_id=node_id,
            side=side,
            normalized_offset=offset,
            point=(px, py),
            outward_normal=_SIDE_NORMALS.get(side, (0.0, 0.0)),
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
) -> list[tuple[str, float]]:
    """Distribute edge_ids evenly along a side.

    Returns (edge_id, normalized_offset) pairs. For n edges, slot i gets
    offset (i+1)/(n+1), guaranteeing all values in (0.0, 1.0) exclusive with
    no duplicates. Input order is preserved.
    """
    if not edge_ids:
        return []
    n = len(edge_ids)
    return [(eid, (i + 1) / (n + 1)) for i, eid in enumerate(edge_ids)]
