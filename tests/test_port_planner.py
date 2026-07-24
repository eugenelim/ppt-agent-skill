"""Tests for scripts/mermaid_render/layout/port_planner.py (ini-004 spec 1)."""
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
    RoutingObstacle,
    build_edge_lists,
    fan_slots,
    generate_port_candidates,
    plan_straight_corridor,
)


# ── Task 1: Data structures (AC1, AC2, AC3) ──────────────────────────────────

def test_port_candidate_is_immutable():  # STUB: AC2
    pc = PortCandidate(
        edge_id="e1", node_id="A", side="top",
        normalized_offset=0.5, point=(10.0, 20.0),
        outward_normal=(0.0, -1.0), fixed_side=False,
        preference_penalty=0.0,
    )
    with pytest.raises(AttributeError):
        pc.side = "bottom"  # type: ignore[misc]


def test_port_candidate_edge_id_field():  # STUB: AC3
    pc = PortCandidate(
        edge_id="e1", node_id="A", side="top",
        normalized_offset=0.5, point=(10.0, 20.0),
        outward_normal=(0.0, -1.0), fixed_side=False,
        preference_penalty=0.0,
    )
    assert pc.edge_id == "e1"


def test_port_reservation_is_immutable():  # STUB: AC2
    pc = PortCandidate(
        edge_id="e1", node_id="A", side="top",
        normalized_offset=0.5, point=(10.0, 20.0),
        outward_normal=(0.0, -1.0), fixed_side=False,
        preference_penalty=0.0,
    )
    pr = PortReservation(
        edge_id="e1", node_id="A", port_candidate=pc,
        terminal_clearance=10.0, escape_point=(10.0, 15.0),
    )
    with pytest.raises(AttributeError):
        pr.terminal_clearance = 999.0  # type: ignore[misc]


def test_port_reservation_edge_id_field():  # STUB: AC3
    pc = PortCandidate(
        edge_id="e1", node_id="A", side="top",
        normalized_offset=0.5, point=(10.0, 20.0),
        outward_normal=(0.0, -1.0), fixed_side=False,
        preference_penalty=0.0,
    )
    pr = PortReservation(
        edge_id="e1", node_id="A", port_candidate=pc,
        terminal_clearance=10.0, escape_point=(10.0, 15.0),
    )
    assert pr.edge_id == "e1"


def test_route_candidate_is_immutable():  # STUB: AC2
    pc = PortCandidate(
        edge_id="e1", node_id="A", side="top",
        normalized_offset=0.5, point=(10.0, 20.0),
        outward_normal=(0.0, -1.0), fixed_side=False,
        preference_penalty=0.0,
    )
    rc = RouteCandidate(
        edge_id="e1", source_port=pc, target_port=pc,
        points=((10.0, 20.0),), bend_count=0, length=0.0,
        crossing_count=0, shared_segment_length=0.0, cost=0.0,
    )
    with pytest.raises(AttributeError):
        rc.cost = 999.0  # type: ignore[misc]


def test_route_candidate_edge_id_field():  # STUB: AC3
    pc = PortCandidate(
        edge_id="e1", node_id="A", side="top",
        normalized_offset=0.5, point=(10.0, 20.0),
        outward_normal=(0.0, -1.0), fixed_side=False,
        preference_penalty=0.0,
    )
    rc = RouteCandidate(
        edge_id="e1", source_port=pc, target_port=pc,
        points=((10.0, 20.0),), bend_count=0, length=0.0,
        crossing_count=0, shared_segment_length=0.0, cost=0.0,
    )
    assert rc.edge_id == "e1"


def test_routing_obstacle_immutable_and_keyed_by_obstacle_id():  # STUB: AC2, AC3
    ob = RoutingObstacle(
        obstacle_id="n1", kind="node",
        bounds=(0.0, 0.0, 100.0, 60.0),
        scope_id=None, title_bounds=None,
        permitted_gate_ids=frozenset(["g1"]),
    )
    assert isinstance(ob.permitted_gate_ids, frozenset)
    assert ob.obstacle_id == "n1"
    assert not hasattr(ob, "edge_id")
    with pytest.raises(AttributeError):
        ob.kind = "group"  # type: ignore[misc]


# ── Task 2: build_edge_lists (AC12) ──────────────────────────────────────────

def test_build_edge_lists_single_edge():  # STUB: AC12
    edges = [{"edge_id": "e1", "source_id": "A", "target_id": "B"}]
    el = build_edge_lists(edges)
    assert "e1" in el["A"]
    assert "e1" in el["B"]


def test_build_edge_lists_multi_edge_same_node():  # STUB: AC12
    edges = [
        {"edge_id": "e1", "source_id": "A", "target_id": "B"},
        {"edge_id": "e2", "source_id": "A", "target_id": "C"},
    ]
    el = build_edge_lists(edges)
    assert sorted(el["A"]) == ["e1", "e2"]


def test_build_edge_lists_no_duplicate_ids():  # STUB: AC12
    edges = [{"edge_id": "e1", "source_id": "A", "target_id": "A"}]
    el = build_edge_lists(edges)
    assert el["A"].count("e1") == 1


# ── Task 3: generate_port_candidates (AC4, AC5, AC6) ─────────────────────────

def test_generate_fixed_side_returns_only_that_side():  # STUB: AC4
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(0.0, 0.0, 120.0, 60.0),
        edge_id="e1", fixed_side="top",
    )
    assert all(c.side == "top" for c in candidates)
    assert all(c.fixed_side is True for c in candidates)
    assert all(c.preference_penalty == 0.0 for c in candidates)
    assert len(candidates) >= 1


def test_generate_all_sides_when_no_fixed():  # STUB: AC5
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(0.0, 0.0, 120.0, 60.0),
        edge_id="e1",
    )
    sides_present = {c.side for c in candidates}
    assert {"top", "right", "bottom", "left", "center"}.issubset(sides_present)


def test_generate_center_has_highest_penalty():  # STUB: AC5
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(0.0, 0.0, 120.0, 60.0),
        edge_id="e1",
    )
    center_candidates = [c for c in candidates if c.side == "center"]
    preferred = [c for c in candidates if c.preference_penalty == 0.0]
    assert center_candidates, "center candidate must be present"
    assert all(c.preference_penalty > p.preference_penalty
               for c in center_candidates for p in preferred)


def test_generate_with_shape_geometry_rect_point_on_boundary():  # STUB: AC6
    from mermaid_render.layout.shape_geometry import RectGeometry
    geom = RectGeometry()
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(10.0, 20.0, 120.0, 60.0),
        edge_id="e1", fixed_side="top",
        shape_geometry=geom,
    )
    assert len(candidates) == 1
    px, py = candidates[0].point
    assert abs(py - 20.0) < 0.5
    assert 10.0 - 0.5 <= px <= 130.0 + 0.5


def test_generate_center_candidate_point_is_node_center():  # STUB: AC6
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(10.0, 20.0, 120.0, 60.0),
        edge_id="e1",
    )
    center = [c for c in candidates if c.side == "center"]
    assert len(center) == 1
    assert center[0].point == (10.0 + 120.0 / 2, 20.0 + 60.0 / 2)


# ── Task 4: plan_straight_corridor (AC7, AC8, AC9, AC13) ─────────────────────

def test_plan_straight_corridor_vertical():  # STUB: AC7
    src = (40.0, 0.0, 80.0, 60.0)
    dst = (50.0, 100.0, 80.0, 60.0)
    result = plan_straight_corridor(src, dst)
    assert result is not None
    kind, val = result
    assert kind == "vertical"
    assert abs(val - 85.0) < 1.0


def test_plan_straight_corridor_horizontal():  # STUB: AC8
    src = (0.0, 30.0, 80.0, 60.0)
    dst = (120.0, 40.0, 80.0, 60.0)
    result = plan_straight_corridor(src, dst)
    assert result is not None
    kind, val = result
    assert kind == "horizontal"
    assert abs(val - 65.0) < 1.0


def test_plan_straight_corridor_no_overlap():  # STUB: AC9
    src = (0.0, 0.0, 60.0, 40.0)
    dst = (200.0, 200.0, 60.0, 40.0)
    assert plan_straight_corridor(src, dst) is None


def test_plan_straight_corridor_touching_nodes_not_strict():  # STUB: AC7
    src = (0.0, 0.0, 60.0, 40.0)
    dst = (0.0, 40.0, 60.0, 40.0)
    result = plan_straight_corridor(src, dst)
    assert result is None


def test_plan_straight_corridor_vertical_takes_priority():  # STUB: AC13
    src = (0.0, 0.0, 200.0, 60.0)
    dst = (0.0, 100.0, 200.0, 60.0)
    result = plan_straight_corridor(src, dst)
    assert result is not None
    kind, _ = result
    assert kind == "vertical"


# ── Task 5: fan_slots (AC10) ─────────────────────────────────────────────────

def test_fan_slots_even_distribution():  # STUB: AC10
    slots = fan_slots(["e1", "e2", "e3"], "bottom")
    assert len(slots) == 3
    offsets = [o for _, o in slots]
    assert sorted(offsets) == offsets
    assert abs(offsets[0] - 0.25) < 1e-9
    assert abs(offsets[1] - 0.50) < 1e-9
    assert abs(offsets[2] - 0.75) < 1e-9


def test_fan_slots_no_duplicate_offsets():  # STUB: AC10
    slots = fan_slots(["e1", "e2", "e3", "e4"], "top")
    offsets = [o for _, o in slots]
    assert len(set(offsets)) == len(offsets)


def test_fan_slots_all_in_open_unit_interval():  # STUB: AC10
    slots = fan_slots(["e1", "e2"], "right")
    offsets = [o for _, o in slots]
    assert all(0.0 < o < 1.0 for o in offsets)


def test_fan_slots_empty():  # STUB: AC10
    slots = fan_slots([], "left")
    assert slots == []


def test_fan_slots_preserves_edge_id_order():  # STUB: AC10
    eids = ["e3", "e1", "e2"]
    slots = fan_slots(eids, "bottom")
    assert [eid for eid, _ in slots] == eids
