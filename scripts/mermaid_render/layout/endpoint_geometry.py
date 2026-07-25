"""Endpoint and marker geometry for finalized orthogonal routes (ini-004 spec 3).

Converts a RouteCandidate into five geometry components plus a merge flag at
the target endpoint. Corner rounding is a renderer concern; this module flags
the conditions without applying any coordinate transformation.

# Editorial: renderer may round a corner when both adjacent segments
# exceed 2 * corner_radius + terminal_clearance.
"""
from __future__ import annotations

from typing import NamedTuple

from mermaid_render.layout.port_planner import (
    PortReservation,
    RouteCandidate,
)


class EndpointGeometry(NamedTuple):
    """Immutable geometry record for the target endpoint of a route."""

    outline_intersection: tuple[float, float]
    marker_tip: tuple[float, float]
    marker_base: tuple[float, float]
    line_endpoint: tuple[float, float]
    tangent: tuple[float, float]
    merge_required: bool


def compute_endpoint_geometry(
    route: RouteCandidate,
    reservation: PortReservation,
    marker_depth: float = 0.0,
) -> EndpointGeometry:
    """Compute target-endpoint geometry for a finalized orthogonal route.

    Falls back to negated port_candidate.outward_normal when the terminal
    segment has zero length (Assumption 5). If the fallback normal is also
    (0,0) (center port), tangent is (0,0) and merge_required is True.
    """
    outline = reservation.port_candidate.point
    marker_tip = outline
    ox, oy = outline

    # Compute tangent from the terminal segment
    if len(route.points) >= 2:
        px, py = route.points[-2]
        qx, qy = route.points[-1]
        raw_tx, raw_ty = qx - px, qy - py
        l1 = abs(raw_tx) + abs(raw_ty)
    else:
        raw_tx, raw_ty, l1 = 0.0, 0.0, 0.0

    terminal_length = l1

    if l1 < 1e-9:
        # Zero-length terminal: fall back to negated outward_normal
        nx, ny = reservation.port_candidate.outward_normal
        tangent = (-nx, -ny)
        merge_required = True
    else:
        tangent = (raw_tx / l1, raw_ty / l1)
        merge_required = terminal_length < marker_depth + 4

    tx, ty = tangent
    marker_base = (ox - marker_depth * tx, oy - marker_depth * ty)
    line_endpoint = marker_base if marker_depth > 0 else outline

    return EndpointGeometry(
        outline_intersection=outline,
        marker_tip=marker_tip,
        marker_base=marker_base,
        line_endpoint=line_endpoint,
        tangent=tangent,
        merge_required=merge_required,
    )
