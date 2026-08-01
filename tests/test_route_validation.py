"""Tests for route_validation.py (ini-004 spec 5).

Coverage: AC1-AC15 per docs/specs/routing-validation-invariants/spec.md.
"""
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.route_validation import ValidationError, validate_routes
from mermaid_render.layout.port_planner import (
    PortCandidate, PortReservation, RouteCandidate, RoutingObstacle,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pc(node_id, x, y, normal=(1.0, 0.0), side="right"):
    """Build a PortCandidate at (x,y) with given outward_normal."""
    return PortCandidate(
        edge_id="e1", node_id=node_id, side=side,
        normalized_offset=0.5, point=(x, y),
        outward_normal=normal, fixed_side=False, preference_penalty=0.0,
    )


def _route(src_pt, dst_pt, *mid, src_normal=(1.0, 0.0), dst_normal=(-1.0, 0.0), eid="e1"):
    """Build a RouteCandidate with axis-aligned points and consistent normals."""
    # src_normal: outward from source node (rightward by default)
    # dst_normal: outward from target node (leftward by default)
    src_port = _pc("A", *src_pt, normal=src_normal, side="right")
    dst_port = _pc("B", *dst_pt, normal=dst_normal, side="left")
    pts = (src_pt,) + mid + (dst_pt,)
    length = sum(
        abs(pts[i+1][0]-pts[i][0]) + abs(pts[i+1][1]-pts[i][1])
        for i in range(len(pts)-1)
    )
    return RouteCandidate(
        edge_id=eid,
        source_port=src_port,
        target_port=dst_port,
        points=pts,
        bend_count=len(mid),
        length=float(length),
        crossing_count=0,
        shared_segment_length=0.0,
        cost=float(length),
    )


def _valid_route(eid="e1"):
    """A simple L-route satisfying all invariants."""
    # Source at (0,50), rightward normal; target at (200,100), leftward normal
    # Route: (0,50) → (100,50) → (100,100) → (200,100)
    # First segment: rightward (+x), consistent with src_normal (1,0)
    # Last segment: rightward (+x), consistent with negated dst_normal -(-1,0) = (1,0)
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 200.0, 100.0, normal=(-1.0, 0.0), side="left")
    pts = ((0.0, 50.0), (100.0, 50.0), (100.0, 100.0), (200.0, 100.0))
    return RouteCandidate(
        edge_id=eid,
        source_port=src_port,
        target_port=dst_port,
        points=pts,
        bend_count=2,
        length=250.0,
        crossing_count=0,
        shared_segment_length=0.0,
        cost=250.0,
    )


# ── T1: AC1, AC2 ─────────────────────────────────────────────────────────────

def test_import_smoke():
    assert callable(validate_routes)
    assert callable(ValidationError)


def test_validation_error_fields():
    e = ValidationError(edge_id="e1", rule="test", detail="desc")
    assert e.edge_id == "e1"
    assert e.rule == "test"
    assert e.detail == "desc"


# ── T2: AC4, AC5, AC14 ───────────────────────────────────────────────────────

def test_malformed_route_under_2_waypoints():
    src_port = _pc("A", 0.0, 0.0)
    dst_port = _pc("B", 100.0, 0.0)
    route = RouteCandidate("e1", src_port, dst_port, ((0.0, 0.0),), 0, 0.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    assert len(errors) == 1
    assert errors[0].rule == "malformed_route"


def test_malformed_route_zero_first_segment():
    src_port = _pc("A", 0.0, 0.0)
    dst_port = _pc("B", 100.0, 0.0)
    # Both points identical → first segment length = 0
    route = RouteCandidate("e1", src_port, dst_port, ((0.0, 0.0), (0.0, 0.0)), 0, 0.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    rules = [e.rule for e in errors]
    assert "malformed_route" in rules


def test_malformed_route_zero_last_segment():
    src_port = _pc("A", 0.0, 0.0)
    dst_port = _pc("B", 100.0, 0.0)
    # Last two points identical → last segment length = 0
    route = RouteCandidate("e1", src_port, dst_port, ((0.0, 0.0), (100.0, 0.0), (100.0, 0.0)), 0, 0.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    rules = [e.rule for e in errors]
    assert "malformed_route" in rules


def test_port_on_reservation_violation():
    route = _valid_route()
    # Reservation points to a different location than source_port
    bad_candidate = _pc("A", 999.0, 999.0)
    res = PortReservation("e1", "A", bad_candidate, 0.0, (999.0, 999.0))
    errors = validate_routes([route], reservations={"e1": res})
    rules = [e.rule for e in errors]
    assert "port_on_reservation" in rules


def test_port_on_reservation_no_reservation_ok():
    route = _valid_route()
    # No reservation provided — should not produce port_on_reservation error
    errors = validate_routes([route], reservations={})
    rules = [e.rule for e in errors]
    assert "port_on_reservation" not in rules


def test_route_start_violation():
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0))
    dst_port = _pc("B", 200.0, 50.0, normal=(-1.0, 0.0))
    # points[0] is (5,50) but source_port.point is (0,50)
    route = RouteCandidate("e1", src_port, dst_port, ((5.0, 50.0), (200.0, 50.0)), 0, 195.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    rules = [e.rule for e in errors]
    assert "route_start" in rules


def test_route_end_violation():
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0))
    dst_port = _pc("B", 200.0, 50.0, normal=(-1.0, 0.0))
    # points[-1] is (195,50) but target_port.point is (200,50)
    route = RouteCandidate("e1", src_port, dst_port, ((0.0, 50.0), (195.0, 50.0)), 0, 195.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    rules = [e.rule for e in errors]
    assert "route_end" in rules


# ── T3: AC6, AC7, AC8, AC9 ───────────────────────────────────────────────────

def test_terminal_normal_source_violation():
    # First segment is diagonal, but source normal is (1,0). Dot < 0.9998 → terminal_normal_source.
    src_port = _pc("A", 0.0, 0.0, normal=(1.0, 0.0))
    dst_port = _pc("B", 100.0, 50.0, normal=(-1.0, 0.0))
    route = RouteCandidate("e1", src_port, dst_port, ((0.0, 0.0), (100.0, 50.0)), 0, 150.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    rules = [e.rule for e in errors]
    assert "terminal_normal_source" in rules


def test_terminal_normal_target_violation():
    # Last segment is diagonal, but target normal is (-1,0). Approach dot < 0.9998 → terminal_normal_target.
    src_port = _pc("A", 0.0, 0.0, normal=(1.0, 0.0))
    dst_port = _pc("B", 200.0, 50.0, normal=(-1.0, 0.0))
    pts = ((0.0, 0.0), (100.0, 0.0), (200.0, 50.0))
    route = RouteCandidate("e1", src_port, dst_port, pts, 1, 250.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    rules = [e.rule for e in errors]
    assert "terminal_normal_target" in rules


def test_port_normal_source_violation():
    # Source normal is rightward (1,0) but first segment goes upward (0,1)
    src_port = _pc("A", 0.0, 0.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 0.0, 100.0, normal=(0.0, -1.0), side="top")  # negated: (0,1)
    # First segment goes UP, last goes UP — last direction (0,1) matches negated dst_normal (0,1) ✓
    # First direction (0,1) should match src_normal (1,0) but doesn't
    pts = ((0.0, 0.0), (0.0, 50.0), (0.0, 100.0))
    route = RouteCandidate("e1", src_port, dst_port, pts, 0, 100.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    rules = [e.rule for e in errors]
    assert "port_normal_source" in rules


def test_port_normal_target_violation():
    # Target normal is leftward (-1,0); approaching direction should be negated = (1,0) rightward
    # but last segment goes leftward (-1,0)
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 100.0, 50.0, normal=(-1.0, 0.0), side="left")
    # Route goes left from 200 to 100 — approaching leftward, but should approach rightward
    pts = ((0.0, 50.0), (200.0, 50.0), (100.0, 50.0))
    # First segment rightward ✓ source normal; last segment leftward ✗ (should be rightward)
    route = RouteCandidate("e1", src_port, dst_port, pts, 1, 250.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    rules = [e.rule for e in errors]
    assert "port_normal_target" in rules


def test_port_normal_center_port_source_exempt():
    # Source center port (outward_normal=(0,0)) → no port_normal_source error
    src_port = _pc("A", 50.0, 50.0, normal=(0.0, 0.0), side="center")
    dst_port = _pc("B", 200.0, 50.0, normal=(-1.0, 0.0), side="left")
    pts = ((50.0, 50.0), (200.0, 50.0))
    route = RouteCandidate("e1", src_port, dst_port, pts, 0, 150.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    assert not any(e.rule == "port_normal_source" for e in errors)


def test_port_normal_center_port_target_exempt():
    # Target center port (outward_normal=(0,0)) → no port_normal_target error
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 150.0, 50.0, normal=(0.0, 0.0), side="center")
    pts = ((0.0, 50.0), (150.0, 50.0))
    route = RouteCandidate("e1", src_port, dst_port, pts, 0, 150.0, 0, 0.0, 0.0)
    errors = validate_routes([route])
    assert not any(e.rule == "port_normal_target" for e in errors)


def test_terminal_length_target_violation():
    # Last segment is 2 px (< marker_depth(0)+4=4)
    route = _valid_route()
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 198.0, 50.0, normal=(-1.0, 0.0), side="left")
    # Last segment: 196→198 = 2px
    pts = ((0.0, 50.0), (196.0, 50.0), (198.0, 50.0))
    r = RouteCandidate("e1", src_port, dst_port, pts, 1, 198.0, 0, 0.0, 0.0)
    errors = validate_routes([r])
    rules = [e.rule for e in errors]
    assert "terminal_length" in rules


def test_terminal_length_source_violation():
    # First segment is 2 px (< 4 minimum)
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 200.0, 50.0, normal=(-1.0, 0.0), side="left")
    # First segment: 0→2 = 2px (too short)
    pts = ((0.0, 50.0), (2.0, 50.0), (200.0, 50.0))
    r = RouteCandidate("e1", src_port, dst_port, pts, 1, 200.0, 0, 0.0, 0.0)
    errors = validate_routes([r])
    rules = [e.rule for e in errors]
    assert "terminal_length" in rules


def test_dogleg_too_short_violation():
    # 4-waypoint route with 2px intermediate segment
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 200.0, 50.0, normal=(-1.0, 0.0), side="left")
    # pts[1]→pts[2] = (100,50)→(102,50) = 2px (too short; intermediate)
    pts = ((0.0, 50.0), (100.0, 50.0), (102.0, 50.0), (200.0, 50.0))
    r = RouteCandidate("e1", src_port, dst_port, pts, 1, 200.0, 0, 0.0, 0.0)
    errors = validate_routes([r])
    rules = [e.rule for e in errors]
    assert "dogleg_too_short" in rules


def test_dogleg_first_last_exempt():
    # 2-waypoint route: single short segment is first AND last, no dogleg error
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 2.0, 50.0, normal=(-1.0, 0.0), side="left")
    pts = ((0.0, 50.0), (2.0, 50.0))
    r = RouteCandidate("e1", src_port, dst_port, pts, 0, 2.0, 0, 0.0, 0.0)
    errors = validate_routes([r])
    assert not any(e.rule == "dogleg_too_short" for e in errors)


def test_2waypoint_terminal_length_double_emit():
    # Assumption 14: 2-waypoint route with short segment → exactly 2 terminal_length errors
    # (first-segment check + last-segment check; no deduplication)
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 2.0, 50.0, normal=(-1.0, 0.0), side="left")
    pts = ((0.0, 50.0), (2.0, 50.0))
    r = RouteCandidate("e1", src_port, dst_port, pts, 0, 2.0, 0, 0.0, 0.0)
    errors = validate_routes([r], marker_depths={"e1": 0.0})
    terminal_errors = [e for e in errors if e.rule == "terminal_length"]
    assert len(terminal_errors) == 2


# ── T4: AC10, AC11 ───────────────────────────────────────────────────────────

def _make_obstacle(obs_id, x, y, w, h, kind="node"):
    return RoutingObstacle(
        obstacle_id=obs_id, kind=kind,
        bounds=(x, y, w, h), scope_id=None, title_bounds=None,
        permitted_gate_ids=frozenset(),
    )


def test_obstacle_intersection_violation():
    # Route passes through a node obstacle at (80,0,60,100)
    route = _valid_route()
    obs = _make_obstacle("N1", 80.0, 0.0, 60.0, 100.0)
    errors = validate_routes([route], obstacles=[obs])
    rules = [e.rule for e in errors]
    assert "obstacle_intersection" in rules


def test_obstacle_boundary_touch_ok():
    # Horizontal route at y=50; obstacle AABB has bottom edge at y=50 (top=0, h=50)
    # The segment is collinear with the bottom boundary → no intersection
    src_port = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst_port = _pc("B", 200.0, 50.0, normal=(-1.0, 0.0), side="left")
    pts = ((0.0, 50.0), (200.0, 50.0))
    route = RouteCandidate("e1", src_port, dst_port, pts, 0, 200.0, 0, 0.0, 0.0)
    # Obstacle bottom edge at y=50 (y=0, h=50 → bottom = y+h = 50)
    obs = _make_obstacle("N1", 50.0, 0.0, 50.0, 50.0)
    errors = validate_routes([route], obstacles=[obs])
    assert not any(e.rule == "obstacle_intersection" for e in errors)


def test_canvas_bounds_violation():
    route = _valid_route()
    # Canvas is 100×100, but route extends to x=200
    errors = validate_routes([route], canvas_bounds=(0.0, 0.0, 100.0, 100.0))
    rules = [e.rule for e in errors]
    assert "canvas_bounds" in rules


def test_canvas_none_skip():
    route = _valid_route()
    # canvas_bounds=None → no canvas check regardless of route extent
    errors = validate_routes([route], canvas_bounds=None)
    assert not any(e.rule == "canvas_bounds" for e in errors)


# ── T5: AC12, AC13 ───────────────────────────────────────────────────────────

def test_shared_segment_violation():
    # Two routes sharing horizontal segment x=0..200 at y=50 (200px > 8px)
    r1 = _valid_route("e1")  # (0,50)→(100,50)→(100,100)→(200,100)
    # r2 has a segment from (0,50) to (100,50) — same as r1's first segment
    src2 = _pc("C", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst2 = _pc("D", 100.0, 200.0, normal=(0.0, 1.0), side="bottom")
    # negated dst_normal = (0,-1) → last seg approaches from bottom
    pts2 = ((0.0, 50.0), (100.0, 50.0), (100.0, 200.0))
    r2 = RouteCandidate("e2", src2, dst2, pts2, 1, 250.0, 0, 0.0, 0.0)
    errors = validate_routes([r1, r2])
    shared_errors = [e for e in errors if e.rule == "shared_segment"]
    # Both edges should have a shared_segment error
    edge_ids = {e.edge_id for e in shared_errors}
    assert "e1" in edge_ids
    assert "e2" in edge_ids


def test_shared_segment_short_ok():
    # Two routes sharing only 4px of a segment (≤ 8px → no error)
    src1 = _pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right")
    dst1 = _pc("B", 200.0, 50.0, normal=(-1.0, 0.0), side="left")
    r1 = RouteCandidate("e1", src1, dst1, ((0.0, 50.0), (200.0, 50.0)), 0, 200.0, 0, 0.0, 0.0)

    src2 = _pc("C", 196.0, 50.0, normal=(1.0, 0.0), side="right")
    dst2 = _pc("D", 300.0, 50.0, normal=(-1.0, 0.0), side="left")
    r2 = RouteCandidate("e2", src2, dst2, ((196.0, 50.0), (300.0, 50.0)), 0, 104.0, 0, 0.0, 0.0)
    # Shared from x=196 to x=200 = 4px ≤ 8px → no error
    errors = validate_routes([r1, r2])
    assert not any(e.rule == "shared_segment" for e in errors)


def test_deterministic():
    route = _valid_route()
    e1 = validate_routes([route])
    e2 = validate_routes([route])
    assert e1 == e2


# ── T6: AC3, AC15 ────────────────────────────────────────────────────────────

def test_valid_routes_all_invariants():
    # A well-formed route satisfying every invariant produces []
    route = _valid_route()
    errors = validate_routes(
        [route],
        reservations={
            "e1": PortReservation(
                edge_id="e1",
                node_id="A",
                port_candidate=_pc("A", 0.0, 50.0, normal=(1.0, 0.0), side="right"),
                terminal_clearance=0.0,
                escape_point=(1.0, 50.0),
            )
        },
        obstacles=[],
        canvas_bounds=(0.0, 0.0, 400.0, 400.0),
        marker_depths={"e1": 0.0},
    )
    assert errors == []
