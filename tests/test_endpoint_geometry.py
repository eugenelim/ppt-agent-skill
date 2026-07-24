"""Tests for scripts/mermaid_render/layout/endpoint_geometry.py (ini-004 spec 3)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.port_planner import (
    PortCandidate,
    PortReservation,
    RouteCandidate,
)
from mermaid_render.layout.endpoint_geometry import (
    EndpointGeometry,
    compute_endpoint_geometry,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pc(edge_id: str, x: float, y: float, normal=(0.0, 1.0)) -> PortCandidate:
    return PortCandidate(
        edge_id=edge_id, node_id="n", side="bottom",
        normalized_offset=0.5, point=(x, y),
        outward_normal=normal, fixed_side=False, preference_penalty=0.0,
    )


def _reservation(point: tuple[float, float], normal=(0.0, 1.0)) -> PortReservation:
    pc = PortCandidate(
        edge_id="e1", node_id="n", side="bottom",
        normalized_offset=0.5, point=point,
        outward_normal=normal, fixed_side=False, preference_penalty=0.0,
    )
    return PortReservation(
        edge_id="e1", node_id="n",
        port_candidate=pc,
        terminal_clearance=10.0,
        escape_point=(0.0, 0.0),
    )


def _route(points: tuple[tuple[float, float], ...]) -> RouteCandidate:
    pc = _pc("e1", 0.0, 0.0)
    return RouteCandidate(
        edge_id="e1", source_port=pc, target_port=pc,
        points=points, bend_count=len(points) - 2,
        length=0.0, crossing_count=0,
        shared_segment_length=0.0, cost=0.0,
    )


# ── T1: Structure (AC1, AC2, AC3) ────────────────────────────────────────────

def test_endpoint_geometry_immutable():  # AC2
    eg = EndpointGeometry(
        outline_intersection=(0.0, 0.0),
        marker_tip=(0.0, 0.0),
        marker_base=(0.0, 0.0),
        line_endpoint=(0.0, 0.0),
        tangent=(1.0, 0.0),
        merge_required=False,
    )
    with pytest.raises(AttributeError):
        eg.merge_required = True  # type: ignore[misc]


def test_endpoint_geometry_fields():  # AC3
    eg = EndpointGeometry(
        outline_intersection=(1.0, 2.0),
        marker_tip=(1.0, 2.0),
        marker_base=(0.5, 2.0),
        line_endpoint=(0.5, 2.0),
        tangent=(1.0, 0.0),
        merge_required=False,
    )
    assert eg.outline_intersection == (1.0, 2.0)
    assert eg.marker_tip == (1.0, 2.0)
    assert eg.marker_base == (0.5, 2.0)
    assert eg.line_endpoint == (0.5, 2.0)
    assert eg.tangent == (1.0, 0.0)
    assert eg.merge_required is False


# ── T2: Tangent, merge_required, marker_base + outline/line_endpoint (AC5-AC10)

def test_tangent_horizontal_right():  # AC9
    route = _route(((0.0, 50.0), (100.0, 50.0)))
    res = _reservation((100.0, 50.0), normal=(1.0, 0.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=0.0)
    assert abs(eg.tangent[0] - 1.0) < 1e-9
    assert abs(eg.tangent[1]) < 1e-9


def test_tangent_horizontal_left():  # AC9
    route = _route(((100.0, 50.0), (0.0, 50.0)))
    res = _reservation((0.0, 50.0), normal=(-1.0, 0.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=0.0)
    assert abs(eg.tangent[0] - (-1.0)) < 1e-9
    assert abs(eg.tangent[1]) < 1e-9


def test_tangent_vertical_down():  # AC9
    route = _route(((50.0, 0.0), (50.0, 100.0)))
    res = _reservation((50.0, 100.0), normal=(0.0, 1.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=0.0)
    assert abs(eg.tangent[0]) < 1e-9
    assert abs(eg.tangent[1] - 1.0) < 1e-9


def test_tangent_vertical_up():  # AC9
    route = _route(((50.0, 100.0), (50.0, 0.0)))
    res = _reservation((50.0, 0.0), normal=(0.0, -1.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=0.0)
    assert abs(eg.tangent[0]) < 1e-9
    assert abs(eg.tangent[1] - (-1.0)) < 1e-9


def test_tangent_zero_length_fallback():  # AC9, Assumption 5
    route = _route(((100.0, 50.0), (100.0, 50.0)))  # zero-length terminal
    res = _reservation((100.0, 50.0), normal=(1.0, 0.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=0.0)
    # Fallback: negated outward_normal (1,0) → tangent=(-1,0)
    assert eg.tangent == (-1.0, 0.0)
    assert eg.merge_required is True


def test_merge_required_true():  # AC10
    route = _route(((0.0, 50.0), (5.0, 50.0)))   # length=5
    res = _reservation((5.0, 50.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=8.0)  # 5 < 12
    assert eg.merge_required is True


def test_merge_required_false_boundary():  # AC10 — terminal == marker_depth+4 → False
    route = _route(((0.0, 50.0), (12.0, 50.0)))  # length=12, depth=8 → 12==12
    res = _reservation((12.0, 50.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=8.0)
    assert eg.merge_required is False


def test_merge_required_false_long():  # AC10
    route = _route(((0.0, 50.0), (20.0, 50.0)))  # length=20, depth=8 → 20>12
    res = _reservation((20.0, 50.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=8.0)
    assert eg.merge_required is False


def test_marker_base_right_tangent():  # AC7
    route = _route(((0.0, 50.0), (100.0, 50.0)))
    res = _reservation((100.0, 50.0), normal=(1.0, 0.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=8.0)
    # marker_base = (100 - 8*1, 50 - 8*0) = (92, 50)
    assert abs(eg.marker_base[0] - 92.0) < 1e-9
    assert abs(eg.marker_base[1] - 50.0) < 1e-9


def test_marker_base_down_tangent():  # AC7
    route = _route(((0.0, 0.0), (0.0, 80.0)))
    res = _reservation((0.0, 80.0), normal=(0.0, 1.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=8.0)
    # tangent=(0,1), marker_base=(0 - 8*0, 80 - 8*1) = (0, 72)
    assert abs(eg.marker_base[0]) < 1e-9
    assert abs(eg.marker_base[1] - 72.0) < 1e-9


def test_compute_outline_intersection():  # AC5 — independent point, not AABB
    route = _route(((0.0, 17.0), (42.0, 17.0)))
    res = _reservation((42.0, 17.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=0.0)
    assert eg.outline_intersection == (42.0, 17.0)


def test_compute_marker_tip_equals_outline():  # AC6
    route = _route(((0.0, 50.0), (100.0, 50.0)))
    res = _reservation((100.0, 50.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=8.0)
    assert eg.marker_tip == eg.outline_intersection


def test_compute_no_marker():  # AC8
    route = _route(((0.0, 50.0), (100.0, 50.0)))
    res = _reservation((100.0, 50.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=0.0)
    assert eg.line_endpoint == eg.outline_intersection


def test_compute_with_marker():  # AC8
    route = _route(((0.0, 50.0), (100.0, 50.0)))
    res = _reservation((100.0, 50.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=8.0)
    assert eg.line_endpoint == eg.marker_base


# ── T3: Integration (AC4) ─────────────────────────────────────────────────────

def test_compute_endpoint_full_pipeline():  # AC4
    route = _route(((0.0, 0.0), (50.0, 0.0), (50.0, 100.0)))
    res = _reservation((50.0, 100.0), normal=(0.0, 1.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=8.0)
    assert eg.outline_intersection == (50.0, 100.0)
    assert eg.marker_tip == eg.outline_intersection
    assert eg.line_endpoint == eg.marker_base
    assert eg.merge_required is False  # terminal=100, depth=8 → 100 >= 12


# ── T4: No rounding (AC11) ───────────────────────────────────────────────────

def test_no_rounding_applied():  # AC11
    # 3-point S-bend near terminal; assert raw-points-derived values throughout
    route = _route(((0.0, 0.0), (25.0, 0.0), (25.0, 80.0)))
    res = _reservation((25.0, 80.0), normal=(0.0, 1.0))
    eg = compute_endpoint_geometry(route, res, marker_depth=8.0)
    # tangent should be (0,1) — exactly from raw points, no smoothing
    assert eg.tangent == (0.0, 1.0)
    # marker_base = (25, 80 - 8*1) = (25, 72) — no midpoint rounding
    assert abs(eg.marker_base[0] - 25.0) < 1e-9
    assert abs(eg.marker_base[1] - 72.0) < 1e-9
    # line_endpoint == marker_base (not a smoothed value)
    assert eg.line_endpoint == eg.marker_base
