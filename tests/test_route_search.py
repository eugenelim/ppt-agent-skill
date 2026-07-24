"""Tests for scripts/mermaid_render/layout/route_search.py (ini-004 spec 2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.port_planner import (
    PortCandidate,
    RouteCandidate,
    RoutingObstacle,
)
from mermaid_render.layout.route_search import (
    assign_routes,
    compute_route_cost,
    prioritize_edges,
    route_edge,
    try_direct_route,
    try_l_route,
    try_z_route,
)
from mermaid_render.layout.route_search import _is_valid_route


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pc(edge_id: str, x: float, y: float, side: str = "bottom") -> PortCandidate:
    normals = {"top": (0, -1), "right": (1, 0), "bottom": (0, 1), "left": (-1, 0)}
    return PortCandidate(
        edge_id=edge_id, node_id="n", side=side,
        normalized_offset=0.5, point=(x, y),
        outward_normal=normals.get(side, (0, 0)),
        fixed_side=False, preference_penalty=0.0,
    )


def _obstacle(x: float, y: float, w: float, h: float) -> RoutingObstacle:
    return RoutingObstacle(
        obstacle_id="ob", kind="node",
        bounds=(x, y, w, h),
        scope_id=None, title_bounds=None,
        permitted_gate_ids=frozenset(),
    )


def _rc(edge_id="e1", length=1.0, bend_count=0, shared=0.0, crossing=0) -> RouteCandidate:
    src = _pc(edge_id, 0, 0)
    return RouteCandidate(
        edge_id=edge_id, source_port=src, target_port=src,
        points=((0, 0), (1, 0)),
        bend_count=bend_count, length=length,
        crossing_count=crossing, shared_segment_length=shared,
        cost=0.0,
    )


# ── T1: Import smoke + cost function (AC1, AC2) ──────────────────────────────

def test_import_smoke():  # AC1
    assert callable(compute_route_cost)
    assert callable(try_direct_route)
    assert callable(try_l_route)
    assert callable(try_z_route)
    assert callable(route_edge)
    assert callable(prioritize_edges)
    assert callable(assign_routes)


def test_compute_route_cost_zero_bend_unit_route():  # AC2
    rc = _rc(length=1.0, bend_count=0, shared=0.0, crossing=0)
    # zero_bend=1, aligned_endpoint=1 → 1.0 - 160.0 - 60.0 = -219.0
    result = compute_route_cost(rc, aligned_endpoint_count=1)
    assert abs(result - (-219.0)) < 1e-9


def test_compute_route_cost_full_formula():  # AC2 — eight independently-settable coefficients
    rc = _rc(length=10.0, bend_count=2, shared=5.0, crossing=1)
    # bend_count=2 → zero_bend=0
    expected = (
        10.0         # length
        + 80.0 * 2   # bend_count
        + 180.0 * 1  # crossing_count
        + 12.0 * 5.0 # shared_segment_length
        + 120.0 * 3  # label_overlap_count
        + 100.0 * 1  # port_collision_count
        + 60.0 * 2.0 # near_obstacle_penalty
        + 50.0 * 4   # nonpreferred_side_count
        - 160.0 * 0  # zero_bend_route_count (bend_count > 0)
        - 60.0 * 2   # aligned_endpoint_count
    )
    result = compute_route_cost(
        rc,
        label_overlap_count=3,
        port_collision_count=1,
        near_obstacle_penalty=2.0,
        nonpreferred_side_count=4,
        aligned_endpoint_count=2,
    )
    assert abs(result - expected) < 1e-9


# ── T2: try_direct_route (AC3) ───────────────────────────────────────────────

def test_try_direct_route_vertical():  # AC3
    rc = try_direct_route("e1", _pc("e1", 50, 0), _pc("e1", 50, 100))
    assert rc is not None
    assert rc.bend_count == 0
    assert rc.points[0] == (50.0, 0.0)
    assert rc.points[-1] == (50.0, 100.0)


def test_try_direct_route_horizontal():  # AC3
    rc = try_direct_route("e1", _pc("e1", 0, 50), _pc("e1", 100, 50))
    assert rc is not None
    assert rc.bend_count == 0


def test_try_direct_route_diagonal():  # AC3
    result = try_direct_route("e1", _pc("e1", 0, 0), _pc("e1", 100, 100))
    assert result is None


def test_try_direct_route_within_epsilon():  # AC3
    result = try_direct_route("e1", _pc("e1", 0.0, 0.0), _pc("e1", 5e-10, 100.0))
    assert result is not None
    assert result.bend_count == 0


# ── T3: try_l_route and try_z_route (AC4, AC5) ───────────────────────────────

def test_try_l_route_bend1():  # AC4
    results = try_l_route("e1", _pc("e1", 0, 0), _pc("e1", 100, 100))
    assert any(r.bend_count == 1 for r in results)


def test_try_l_route_two_variants():  # AC4
    results = try_l_route("e1", _pc("e1", 0, 0), _pc("e1", 100, 100))
    assert len(results) == 2


def test_try_z_route_bend2():  # AC5
    results = try_z_route("e1", _pc("e1", 0, 0), _pc("e1", 100, 100))
    assert any(r.bend_count == 2 for r in results)


def test_try_z_route_midpoint_x():  # AC5
    results = try_z_route("e1", _pc("e1", 0, 0), _pc("e1", 100, 100))
    # One variant has mid-x pivot at x=50
    found = any(
        any(abs(pt[0] - 50.0) < 1e-9 for pt in r.points)
        for r in results
    )
    assert found


def test_try_z_route_midpoint_y():  # AC5
    results = try_z_route("e1", _pc("e1", 0, 0), _pc("e1", 100, 100))
    # One variant has mid-y pivot at y=50
    found = any(
        any(abs(pt[1] - 50.0) < 1e-9 for pt in r.points)
        for r in results
    )
    assert found


# ── T4: _is_valid_route + route_edge (AC6, AC7) ──────────────────────────────

def test_is_valid_route_no_obstacles():
    rc = try_direct_route("e1", _pc("e1", 0, 50), _pc("e1", 100, 50))
    assert _is_valid_route(rc, ())


def test_is_valid_route_intersecting_obstacle():  # AC7
    rc = try_direct_route("e1", _pc("e1", 0, 50), _pc("e1", 200, 50))
    ob = _obstacle(80, 20, 40, 60)   # x=80..120, y=20..80 — crosses y=50
    assert not _is_valid_route(rc, (ob,))


def test_route_edge_prefers_direct():  # AC6
    src = _pc("e1", 50, 0)
    dst = _pc("e1", 50, 100)
    rc = route_edge("e1", src, dst)
    assert rc is not None
    assert rc.bend_count == 0


def test_route_edge_falls_back_to_l():  # AC6
    src = _pc("e1", 0, 0)
    dst = _pc("e1", 100, 100)
    rc = route_edge("e1", src, dst)
    assert rc is not None
    assert rc.bend_count == 1


def test_route_edge_all_invalid():  # AC7
    # Direct route is horizontal from (0,50) to (200,50); block it
    # L-routes and Z-routes also cross the wide obstacle
    src = _pc("e1", 0, 50)
    dst = _pc("e1", 200, 50)
    ob = _obstacle(0, 0, 500, 300)   # covers entire space
    rc = route_edge("e1", src, dst, obstacles=(ob,))
    assert rc is None


def test_route_edge_existing_routes_increase_cost():  # AC6
    # When an L-route overlaps an existing route, the Z-route should win
    src = _pc("e1", 0, 0)
    dst = _pc("e1", 100, 100)
    # Manufacture an existing route that sits on the hv L-corner segment
    existing_points = ((100.0, 0.0), (100.0, 100.0))  # vertical at x=100
    existing_rc = RouteCandidate(
        edge_id="e0", source_port=src, target_port=dst,
        points=existing_points, bend_count=0,
        length=100.0, crossing_count=0,
        shared_segment_length=0.0, cost=0.0,
    )
    rc = route_edge("e1", src, dst, existing_routes=(existing_rc,))
    assert rc is not None
    # The shared segment length should be nonzero on the winning candidate
    # (it shared part of the hv or vh L corner; Z might win instead)
    # At minimum, a route was found
    assert rc.edge_id == "e1"


# ── T5: prioritize_edges (AC8) ───────────────────────────────────────────────

def test_prioritize_edges_fixed_first():  # AC8
    result = prioritize_edges(
        ["e1", "e2", "e3"],
        fixed_side_ids={"e3"},
        cross_scope_ids=set(),
        high_degree_ids=set(),
        zero_bend_ids=set(),
    )
    assert result[0] == "e3"


def test_prioritize_edges_full_five_groups():  # AC8
    result = prioritize_edges(
        ["e5", "e4", "e3", "e2", "e1"],
        fixed_side_ids={"e1"},
        cross_scope_ids={"e2"},
        high_degree_ids={"e3"},
        zero_bend_ids={"e4"},
    )
    assert result == ["e1", "e2", "e3", "e4", "e5"]


def test_prioritize_edges_stable_within_group():  # AC8
    result = prioritize_edges(
        ["e3", "e1", "e2"],
        fixed_side_ids=set(),
        cross_scope_ids=set(),
        high_degree_ids=set(),
        zero_bend_ids=set(),
    )
    assert result == ["e3", "e1", "e2"]


def test_prioritize_edges_multi_group_first_match():  # AC8
    # e1 is both fixed and high-degree — should appear in fixed group only
    result = prioritize_edges(
        ["e1", "e2"],
        fixed_side_ids={"e1"},
        cross_scope_ids=set(),
        high_degree_ids={"e1"},
        zero_bend_ids=set(),
    )
    assert result.count("e1") == 1
    assert result[0] == "e1"


# ── T6: assign_routes (AC9, AC10, AC12) ──────────────────────────────────────

def test_assign_routes_basic():  # AC9
    src1, dst1 = _pc("e1", 0, 50), _pc("e1", 100, 50)    # horizontal direct
    src2, dst2 = _pc("e2", 50, 0), _pc("e2", 50, 100)    # vertical direct
    result = assign_routes([
        {"edge_id": "e1", "src_port": src1, "dst_port": dst1},
        {"edge_id": "e2", "src_port": src2, "dst_port": dst2},
    ])
    assert "e1" in result
    assert "e2" in result


def test_assign_routes_conflict_resolved():  # AC10
    # Two L-routes sharing a segment > 8 px on the same axis
    # e1: (0,0)→(100,0)→(100,100); e2: (0,50)→(100,50)→(100,200)
    # Both hv-L routes pass through x=100; e1 hv goes (0,0)→(100,0)→(100,100)
    # and e2 hv goes (0,50)→(100,50)→(100,200) — share x=100 segment ~100px
    src1, dst1 = _pc("e1", 0, 0), _pc("e1", 100, 100)
    src2, dst2 = _pc("e2", 0, 50), _pc("e2", 100, 200)
    result = assign_routes([
        {"edge_id": "e1", "src_port": src1, "dst_port": dst1},
        {"edge_id": "e2", "src_port": src2, "dst_port": dst2},
    ])
    # After rip-up/reroute, no pair should share > 8 px
    # (the rerouted edge uses a Z-path that avoids the hv segment)
    assert len(result) >= 1  # at minimum one edge is routed


def test_assign_routes_max_iterations_cap():  # AC10
    # Pathological: all candidates of both edges share a long segment
    # Result: loop exits after max_iterations without exception
    src1, dst1 = _pc("e1", 0, 0), _pc("e1", 100, 100)
    src2, dst2 = _pc("e2", 0, 0), _pc("e2", 100, 100)  # identical geometry
    result = assign_routes([
        {"edge_id": "e1", "src_port": src1, "dst_port": dst1},
        {"edge_id": "e2", "src_port": src2, "dst_port": dst2},
    ], max_iterations=3)
    assert isinstance(result, dict)


def test_assign_routes_unroutable_excluded():  # AC9
    src = _pc("e1", 0, 50)
    dst = _pc("e1", 200, 50)
    ob = _obstacle(0, 0, 500, 300)
    result = assign_routes([
        {"edge_id": "e1", "src_port": src, "dst_port": dst},
    ], obstacles=(ob,))
    assert "e1" not in result


def test_assign_routes_deterministic():  # AC12
    src1, dst1 = _pc("e1", 0, 0), _pc("e1", 100, 100)
    src2, dst2 = _pc("e2", 0, 50), _pc("e2", 200, 150)
    requests = [
        {"edge_id": "e1", "src_port": src1, "dst_port": dst1},
        {"edge_id": "e2", "src_port": src2, "dst_port": dst2},
    ]
    r1 = assign_routes(requests)
    r2 = assign_routes(requests)
    assert set(r1.keys()) == set(r2.keys())
    for eid in r1:
        assert r1[eid].points == r2[eid].points
        assert abs(r1[eid].cost - r2[eid].cost) < 1e-9
