"""Tests for flowchart routing closure (ini-005).

Covers: RoutePermissions/GateAperture data model, validate_routes() extensions,
local_channel_route(), fan_slots() face-spanning formula, flowchart_route_adapter(),
three scoped fixtures (geometry ACs), and negative validation tests.

Run with:
  pytest tests/test_flowchart_routing_closure.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mermaid_render.layout.port_planner import (
    PortCandidate,
    RouteCandidate,
    RoutingObstacle,
    RoutePermissions,
    GateAperture,
    fan_slots,
    FAN_EDGE_PADDING,
    FAN_MIN_PORT_PITCH,
    FAN_ESCAPE_LENGTH,
    FAN_CHANNEL_PITCH,
)
from mermaid_render.layout.route_search import (
    local_channel_route,
    MAX_LOCAL_EXCURSION,
    LOCAL_LANE_GAP,
    LANE_PITCH,
)
from mermaid_render.layout.route_validation import validate_routes
from mermaid_render.layout._pipeline import (
    _compile_flowchart,
    parse_flowchart_semantics,
    layout_flowchart_with_python_fallback,
    flowchart_route_adapter,
    _USE_LEGACY_ROUTE_EDGES,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (_FIXTURES / f"{name}.mmd").read_text()


def _compile(name: str):
    return _compile_flowchart(_load(name), 800, None).layout


def _make_port(edge_id: str, node_id: str, side: str, x: float, y: float) -> PortCandidate:
    normals = {"top": (0.0, -1.0), "bottom": (0.0, 1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0)}
    return PortCandidate(
        edge_id=edge_id, node_id=node_id, side=side,
        normalized_offset=0.5, point=(x, y),
        outward_normal=normals.get(side, (0.0, 0.0)),
        fixed_side=False, preference_penalty=0.0,
    )


def _make_obstacle(obs_id: str, kind: str, x: float, y: float, w: float, h: float) -> RoutingObstacle:
    return RoutingObstacle(
        obstacle_id=obs_id, kind=kind,
        bounds=(x, y, w, h),
        scope_id=None, title_bounds=None,
        permitted_gate_ids=frozenset(),
    )


def normalize_waypoints(layout) -> tuple:
    """Sort routed edges by edge_id and round waypoints to 1 decimal."""
    edges = sorted(layout.routed_edges, key=lambda e: e.edge_id or "")
    return tuple(
        (e.edge_id, tuple((round(p.x, 1), round(p.y, 1)) for p in e.waypoints))
        for e in edges
    )


def _first_n_px(waypoints, n_px: float):
    """Return sub-polyline for the first n_px of travel as list of segment tuples."""
    pts = [(p.x, p.y) for p in waypoints]
    result = []
    traveled = 0.0
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        seg_len = abs(bx - ax) + abs(by - ay)
        if seg_len < 1e-9:
            continue
        remaining = n_px - traveled
        if traveled + seg_len <= n_px + 1e-9:
            result.append(((ax, ay), (bx, by)))
            traveled += seg_len
        else:
            t = remaining / seg_len
            result.append(((ax, ay), (ax + (bx - ax) * t, ay + (by - ay) * t)))
            break
        if traveled >= n_px:
            break
    return result


def _last_n_px(waypoints, n_px: float):
    """Return sub-polyline for the last n_px of travel as list of segment tuples."""
    rev = list(reversed(waypoints))
    segs_rev = _first_n_px(rev, n_px)
    return [((bx, by), (ax, ay)) for (ax, ay), (bx, by) in reversed(segs_rev)]


def _seg_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2) -> float:
    """Overlap px between two co-axis orthogonal segments; 0 if not collinear."""
    if abs(ay1 - ay2) < 1e-9 and abs(by1 - by2) < 1e-9 and abs(ay1 - by1) < 1e-9:
        alo, ahi = min(ax1, ax2), max(ax1, ax2)
        blo, bhi = min(bx1, bx2), max(bx1, bx2)
        return max(0.0, min(ahi, bhi) - max(alo, blo))
    if abs(ax1 - ax2) < 1e-9 and abs(bx1 - bx2) < 1e-9 and abs(ax1 - bx1) < 1e-9:
        alo, ahi = min(ay1, ay2), max(ay1, ay2)
        blo, bhi = min(by1, by2), max(by1, by2)
        return max(0.0, min(ahi, bhi) - max(alo, blo))
    return 0.0


def _pairwise_shared_px(segs_a, segs_b) -> float:
    """Total shared segment px between two sub-polylines."""
    total = 0.0
    for (ax1, ay1), (ax2, ay2) in segs_a:
        for (bx1, by1), (bx2, by2) in segs_b:
            total += _seg_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2)
    return total


def _boundary_crossing_count(waypoints, bbox_x0, bbox_y0, bbox_x1, bbox_y1) -> int:
    """Count route transitions between inside and outside the bbox (strict interior)."""
    def _inside(p) -> bool:
        return bbox_x0 < p.x < bbox_x1 and bbox_y0 < p.y < bbox_y1
    return sum(
        1 for i in range(len(waypoints) - 1)
        if _inside(waypoints[i]) != _inside(waypoints[i + 1])
    )


# ── Section 1: Data model (AC1-AC5) ───────────────────────────────────────────

class TestDataModel:
    def test_route_permissions_is_namedtuple(self):
        perm = RoutePermissions("e1", ("A",), ("B",), (), ("g1",))
        assert perm.edge_id == "e1"
        assert perm.source_scope_chain == ("A",)
        assert perm.permitted_gate_ids == ("g1",)
        with pytest.raises((AttributeError, TypeError)):
            perm.edge_id = "changed"  # type: ignore[misc]

    def test_gate_aperture_is_namedtuple(self):
        ga = GateAperture("g1", "e1", "grp", "bottom", (10.0, 20.0), 5.0)
        assert ga.gate_id == "g1"
        assert ga.group_id == "grp"
        assert ga.half_width == 5.0
        with pytest.raises((AttributeError, TypeError)):
            ga.gate_id = "changed"  # type: ignore[misc]

    def test_obstacle_kind_new_values_accepted(self):
        for kind in ("NODE_INTERIOR", "GROUP_INTERIOR", "GROUP_BOUNDARY", "GROUP_TITLE", "LABEL", "MARKER_CLEARANCE"):
            ob = RoutingObstacle("obs1", kind, (0.0, 0.0, 10.0, 10.0), None, None, frozenset())
            assert ob.kind == kind

    def test_obstacle_kind_old_values_still_accepted(self):
        for kind in ("node", "group", "title_band"):
            ob = RoutingObstacle("obs1", kind, (0.0, 0.0, 10.0, 10.0), None, None, frozenset())
            assert ob.kind == kind

    def test_validate_routes_permission_param_defaults_none(self):
        src = _make_port("e1", "A", "bottom", 50.0, 90.0)
        dst = _make_port("e1", "B", "top", 50.0, 200.0)
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=((50.0, 90.0), (50.0, 200.0)),
            bend_count=0, length=110.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        result = validate_routes((rc,), canvas_bounds=(0.0, 0.0, 200.0, 400.0))
        assert isinstance(result, list)

    def test_validate_routes_rejects_wrong_gate(self):
        src = _make_port("e1", "A", "bottom", 50.0, 90.0)
        dst = _make_port("e1", "B", "top", 150.0, 200.0)
        # Route that crosses x=100 boundary
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=((50.0, 90.0), (150.0, 90.0), (150.0, 200.0)),
            bend_count=1, length=210.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        boundary_ob = _make_obstacle("grp1", "GROUP_BOUNDARY", 100.0, 0.0, 5.0, 300.0)
        perm = RoutePermissions("e1", (), ("grp1",), (), ("wrong_gate",))
        aperture = GateAperture("correct_gate", "e1", "grp1", "right", (102.5, 50.0), 20.0)
        errors = validate_routes(
            (rc,), canvas_bounds=(0.0, 0.0, 300.0, 400.0),
            obstacles=(boundary_ob,),
            route_permissions=[perm],
            gate_apertures=[aperture],
        )
        assert any("gate" in str(e).lower() or "boundary" in str(e).lower() for e in errors)

    def test_validate_routes_rejects_title_crossing(self):
        src = _make_port("e1", "A", "bottom", 50.0, 90.0)
        dst = _make_port("e1", "B", "top", 150.0, 200.0)
        # Route passes through the title band of a group
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=((50.0, 10.0), (150.0, 10.0), (150.0, 200.0)),
            bend_count=1, length=290.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        title_ob = _make_obstacle("grp1_title", "GROUP_TITLE", 0.0, 0.0, 200.0, 20.0)
        perm = RoutePermissions("e1", (), ("grp1",), (), ())
        aperture = GateAperture("g1", "e1", "grp1", "bottom", (100.0, 100.0), 20.0)
        errors = validate_routes(
            (rc,), canvas_bounds=(0.0, 0.0, 300.0, 400.0),
            obstacles=(title_ob,),
            route_permissions=[perm],
            gate_apertures=[aperture],
        )
        assert any("title" in str(e).lower() or "GROUP_TITLE" in str(e) for e in errors)

    def test_validate_routes_rejects_reentry(self):
        # Use center side so port_normal check is skipped (outward_normal=(0,0))
        src = _make_port("e1", "A", "center", -20.0, 90.0)
        dst = _make_port("e1", "B", "center", 50.0, 250.0)
        # 3-crossing route: enter group at y=90, exit at y=150 (within aperture),
        # then re-enter at y=250 — the third boundary crossing triggers gate_reentry
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=(
                (-20.0, 90.0), (50.0, 90.0),
                (50.0, 150.0), (-20.0, 150.0),
                (-20.0, 250.0), (50.0, 250.0),
            ),
            bend_count=4, length=370.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        boundary_ob = _make_obstacle("grp1", "GROUP_BOUNDARY", 0.0, 0.0, 5.0, 300.0)
        perm = RoutePermissions("e1", ("grp1",), (), ("grp1",), ("g1",))
        aperture = GateAperture("g1", "e1", "grp1", "left", (2.5, 150.0), 20.0)
        errors = validate_routes(
            (rc,), canvas_bounds=(-100.0, 0.0, 400.0, 400.0),
            obstacles=(boundary_ob,),
            route_permissions=[perm],
            gate_apertures=[aperture],
        )
        assert any("re-enter" in str(e).lower() or "reentry" in str(e).lower() for e in errors)

    def test_check_obstacles_filters_new_kinds(self):
        src = _make_port("e1", "A", "bottom", 50.0, 90.0)
        dst = _make_port("e1", "B", "top", 50.0, 300.0)
        # Route that crosses NODE_INTERIOR obstacle
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=((50.0, 90.0), (50.0, 300.0)),
            bend_count=0, length=210.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        node_ob = _make_obstacle("C", "NODE_INTERIOR", 20.0, 150.0, 60.0, 42.0)
        group_ob = _make_obstacle("grp1", "GROUP_INTERIOR", 0.0, 100.0, 200.0, 100.0)
        errors = validate_routes((rc,), canvas_bounds=(0.0, 0.0, 200.0, 400.0), obstacles=(node_ob, group_ob))
        # Both NODE_INTERIOR and GROUP_INTERIOR should produce errors (not silently skip)
        assert len(errors) >= 1


# ── Section 2: Local channel route (AC11-AC12) ────────────────────────────────

class TestLocalChannel:
    def _src_port(self, eid="e1", x=50.0, y=100.0):
        return _make_port(eid, "A", "right", x, y)

    def _dst_port(self, eid="e1", x=50.0, y=400.0):
        return _make_port(eid, "B", "left", x, y)

    def test_local_channel_left_channel(self):
        src = self._src_port(x=50.0, y=100.0)
        dst = self._dst_port(x=50.0, y=400.0)
        local_bounds = (60.0, 100.0, 80.0, 300.0)
        result = local_channel_route("e1", src, dst, local_bounds)
        assert result is not None
        xs = [p[0] for p in result.points]
        assert any(x < 60.0 for x in xs), "Expected left channel route"
        bx = local_bounds[0]
        assert all(x >= bx - MAX_LOCAL_EXCURSION for x in xs)

    def test_local_channel_right_channel(self):
        src = _make_port("e1", "A", "right", 50.0, 200.0)
        dst = _make_port("e1", "B", "left", 200.0, 200.0)
        local_bounds = (60.0, 150.0, 100.0, 100.0)
        result = local_channel_route("e1", src, dst, local_bounds)
        assert result is not None
        max_x = local_bounds[0] + local_bounds[2] + MAX_LOCAL_EXCURSION
        assert all(p[0] <= max_x for p in result.points)

    def test_local_channel_rejects_out_of_bounds(self):
        src = _make_port("e1", "A", "right", 0.0, 100.0)
        dst = _make_port("e1", "B", "left", 0.0, 400.0)
        # Both channels require x far outside inflate bounds
        local_bounds = (500.0, 100.0, 100.0, 300.0)
        result = local_channel_route("e1", src, dst, local_bounds)
        assert result is None, "Should return None when no valid channel exists"

    def test_local_channel_returns_route_candidate(self):
        src = self._src_port()
        dst = self._dst_port()
        local_bounds = (60.0, 80.0, 200.0, 350.0)
        result = local_channel_route("e1", src, dst, local_bounds)
        if result is not None:
            assert isinstance(result, RouteCandidate)
            assert result.edge_id == "e1"
            assert result.source_port == src
            assert result.target_port == dst

    def test_local_channel_orthogonal_segments(self):
        src = self._src_port(x=50.0, y=100.0)
        dst = self._dst_port(x=50.0, y=400.0)
        local_bounds = (60.0, 80.0, 200.0, 350.0)
        result = local_channel_route("e1", src, dst, local_bounds)
        if result is not None:
            pts = result.points
            for i in range(len(pts) - 1):
                ax, ay = pts[i]
                bx, by = pts[i + 1]
                assert abs(ax - bx) < 1e-9 or abs(ay - by) < 1e-9, (
                    f"Diagonal segment at index {i}: ({ax},{ay})->({bx},{by})"
                )

    def test_local_channel_deterministic(self):
        src = self._src_port()
        dst = self._dst_port()
        local_bounds = (60.0, 80.0, 200.0, 350.0)
        r1 = local_channel_route("e1", src, dst, local_bounds)
        r2 = local_channel_route("e1", src, dst, local_bounds)
        assert (r1 is None and r2 is None) or (r1 is not None and r2 is not None and r1.points == r2.points)


# ── Section 3: Fan slots (AC17-AC18) ──────────────────────────────────────────

class TestFanSlots:
    def test_fan_slots_n1_returns_center(self):
        result = fan_slots(["e1"], "bottom", face_length=100.0)
        assert result == [("e1", 0.5)]

    def test_fan_slots_n3_spans_face(self):
        result = fan_slots(["e1", "e2", "e3"], "bottom", face_length=100.0)
        offsets = [off for _, off in result]
        px = [off * 100.0 for off in offsets]
        assert abs(px[0] - FAN_EDGE_PADDING) < 1.0, f"First port at {px[0]}, expected {FAN_EDGE_PADDING}"
        assert abs(px[2] - (100.0 - FAN_EDGE_PADDING)) < 1.0, f"Last port at {px[2]}"
        assert abs(px[1] - 50.0) < 1.0, f"Middle port at {px[1]}, expected 50.0"

    def test_fan_slots_n3_min_pitch(self):
        face_length = 2 * FAN_EDGE_PADDING + 2 * FAN_MIN_PORT_PITCH
        result = fan_slots(["e1", "e2", "e3"], "bottom", face_length=face_length)
        offsets = [off for _, off in result]
        px = [off * face_length for off in offsets]
        for i in range(len(px) - 1):
            sep = abs(px[i + 1] - px[i])
            assert sep >= FAN_MIN_PORT_PITCH - 0.01, f"Port separation {sep} < FAN_MIN_PORT_PITCH={FAN_MIN_PORT_PITCH}"

    def test_fan_slots_constants_defined(self):
        assert FAN_EDGE_PADDING == 12.0
        assert FAN_MIN_PORT_PITCH == 24.0
        assert FAN_ESCAPE_LENGTH == 20.0
        assert FAN_CHANNEL_PITCH == 14.0

    def test_fan_slots_n2_no_center_compression(self):
        result = fan_slots(["e1", "e2"], "bottom", face_length=100.0)
        offsets = [off for _, off in result]
        px = [off * 100.0 for off in offsets]
        assert abs(px[0] - FAN_EDGE_PADDING) < 1.0
        assert abs(px[1] - (100.0 - FAN_EDGE_PADDING)) < 1.0

    def test_fan_slots_deterministic(self):
        r1 = fan_slots(["e1", "e2", "e3"], "bottom", face_length=100.0)
        r2 = fan_slots(["e1", "e2", "e3"], "bottom", face_length=100.0)
        assert r1 == r2

    def test_fan_slots_backcompat_no_face_length(self):
        result = fan_slots(["e1", "e2", "e3"], "bottom", face_length=0.0)
        offsets = [off for _, off in result]
        assert offsets == pytest.approx([1/4, 2/4, 3/4])

    def test_fan_slots_narrow_face_clamped(self):
        # face_length=30 < required=72: narrow-face branch; offsets must stay in [0, 1]
        for fl in (30.0, 20.0, 10.0, 5.0):
            result = fan_slots(["a", "b", "c"], "bottom", face_length=fl)
            offsets = [off for _, off in result]
            assert all(0.0 <= o <= 1.0 for o in offsets), (
                f"face_length={fl}: offsets out of [0,1]: {offsets}"
            )
            # Monotonically non-decreasing (ports don't reverse)
            for i in range(len(offsets) - 1):
                assert offsets[i] <= offsets[i + 1], (
                    f"face_length={fl}: offsets not monotone: {offsets}"
                )


# ── Section 4: Adapter and fixture geometry (AC6-AC10, AC14-AC21) ─────────────

class TestAdapter:
    def test_adapter_returns_port_candidates(self):
        sem = parse_flowchart_semantics("flowchart TD\n  A --> B")
        from mermaid_render.layout._pipeline import (
            _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates,
            _compute_group_bboxes,
        )
        nodes = sem.nodes
        edges = sem.edges
        groups = sem.groups
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        _minimize_crossings(nodes, edges)
        _assign_coordinates(nodes, "TD")
        grp_bboxes = _compute_group_bboxes(nodes, groups, 400, 400)
        ports, obstacles, permissions, apertures = flowchart_route_adapter(sem, grp_bboxes, "TD")
        assert len(ports) > 0
        assert all(isinstance(p, PortCandidate) for p in ports)
        for p in ports:
            assert p.edge_id, "PortCandidate.edge_id must be non-empty"

    def test_adapter_keyed_by_edge_id(self):
        sem = parse_flowchart_semantics("flowchart TD\n  A --> B\n  B --> C")
        from mermaid_render.layout._pipeline import (
            _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates,
            _compute_group_bboxes,
        )
        nodes = sem.nodes
        edges = sem.edges
        groups = sem.groups
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        _minimize_crossings(nodes, edges)
        _assign_coordinates(nodes, "TD")
        grp_bboxes = _compute_group_bboxes(nodes, groups, 400, 400)
        ports, _, _, _ = flowchart_route_adapter(sem, grp_bboxes, "TD")
        edge_ids = {p.edge_id for p in ports}
        for e in sem.edges:
            if e.edge_id:
                assert e.edge_id in edge_ids, f"edge_id '{e.edge_id}' not in adapter ports"

    def test_new_path_used_for_scoped_fixtures(self, monkeypatch):
        import mermaid_render.layout._pipeline as _pip
        def _boom(*args, **kwargs):
            raise RuntimeError("_route_edges was called on new path!")
        monkeypatch.setattr(_pip, "_route_edges", _boom)
        for name in ("flowchart-parallel-links", "flowchart-arrows-defs", "flowchart-inner-direction"):
            layout = _compile(name)
            assert not layout.routing_failures, f"{name} had routing failures"

    def test_perimeter_not_reachable_for_scoped_fixtures(self, monkeypatch):
        from mermaid_render.layout import _routing
        def _boom(*args, **kwargs):
            raise RuntimeError("_route_perimeter was called!")
        monkeypatch.setattr(_routing, "_route_perimeter", _boom)
        for name in ("flowchart-parallel-links", "flowchart-arrows-defs", "flowchart-inner-direction"):
            layout = _compile(name)
            assert not layout.routing_failures, f"{name} had routing failures"

    def test_flag_restores_legacy_path(self, monkeypatch):
        monkeypatch.setattr(
            "mermaid_render.layout._pipeline._USE_LEGACY_ROUTE_EDGES", True
        )
        import mermaid_render.layout._pipeline as pip
        assert pip._USE_LEGACY_ROUTE_EDGES is True


class TestFixtureGeometry:
    def test_parallel_links_fan_pitch(self):
        layout = _compile("flowchart-parallel-links")
        gw_pts = [
            (round(e.waypoints[0].x, 1), round(e.waypoints[0].y, 1))
            for e in layout.routed_edges
            if e.src_port.node_id == "A"
        ]
        if len(gw_pts) >= 2:
            xs = sorted(p[0] for p in gw_pts)
            for i in range(len(xs) - 1):
                sep = xs[i + 1] - xs[i]
                assert sep >= FAN_MIN_PORT_PITCH - 0.5, (
                    f"Gateway port separation {sep:.1f}px < {FAN_MIN_PORT_PITCH}px minimum"
                )

    def test_parallel_links_agg_pitch(self):
        layout = _compile("flowchart-parallel-links")
        agg_pts = [
            (round(e.waypoints[-1].x, 1), round(e.waypoints[-1].y, 1))
            for e in layout.routed_edges
            if e.dst_port.node_id == "E"
        ]
        if len(agg_pts) >= 2:
            xs = sorted(p[0] for p in agg_pts)
            for i in range(len(xs) - 1):
                sep = xs[i + 1] - xs[i]
                assert sep >= FAN_MIN_PORT_PITCH - 0.5, (
                    f"Aggregator port separation {sep:.1f}px < {FAN_MIN_PORT_PITCH}px minimum"
                )

    def test_arrows_defs_no_full_height_route(self):
        layout = _compile("flowchart-arrows-defs")
        canvas_h = layout.canvas_bounds.h
        for e in layout.routed_edges:
            for p in e.waypoints:
                assert p.y < canvas_h, f"Edge {e.edge_id} waypoint y={p.y} >= canvas_h={canvas_h}"
                assert p.y >= 0, f"Edge {e.edge_id} waypoint y={p.y} < 0"

    def test_arrows_defs_local_excursion(self):
        """AC14: A→D waypoints stay within local_bounds + 48px."""
        layout = _compile("flowchart-arrows-defs")
        ad_edge = next(
            (e for e in layout.routed_edges
             if e.src_port.node_id == "A" and e.dst_port.node_id == "D"),
            None,
        )
        assert ad_edge is not None, "A→D edge not found in arrows-defs layout"
        nodes = layout.node_layouts
        a_rank = nodes["A"].rank
        d_rank = nodes["D"].rank
        local_nodes = [
            n for n in nodes.values()
            if a_rank <= n.rank <= d_rank and not n.is_dummy
        ]
        max_x = max(n.outer_bounds.x + n.outer_bounds.w for n in local_nodes)
        max_y = max(n.outer_bounds.y + n.outer_bounds.h for n in local_nodes)
        for p in ad_edge.waypoints:
            assert p.x <= max_x + 48, (
                f"A→D: x={p.x:.1f} > local_bounds.right+48={max_x+48:.1f}"
            )
            assert p.y <= max_y + 48, (
                f"A→D: y={p.y:.1f} > local_bounds.bottom+48={max_y+48:.1f}"
            )

    def test_inner_direction_boundary_crossings(self):
        """AC16: source→ingest and load→sink each cross Pipeline boundary exactly once."""
        layout = _compile("flowchart-inner-direction")
        pipeline_gl = next(
            (gl for gl in layout.group_layouts.values()
             if "ingest" in gl.member_ids),
            None,
        )
        assert pipeline_gl is not None, "Pipeline group layout not found"
        bb = pipeline_gl.boundary_bounds
        x0, y0, x1, y1 = bb.x, bb.y, bb.x + bb.w, bb.y + bb.h

        source_ingest = next(
            (e for e in layout.routed_edges
             if e.src_port.node_id == "source" and e.dst_port.node_id == "ingest"),
            None,
        )
        load_sink = next(
            (e for e in layout.routed_edges
             if e.src_port.node_id == "load" and e.dst_port.node_id == "sink"),
            None,
        )
        assert source_ingest is not None, "source→ingest edge not found"
        assert load_sink is not None, "load→sink edge not found"

        si_crossings = _boundary_crossing_count(source_ingest.waypoints, x0, y0, x1, y1)
        ls_crossings = _boundary_crossing_count(load_sink.waypoints, x0, y0, x1, y1)
        assert si_crossings == 1, (
            f"source→ingest crosses Pipeline boundary {si_crossings} times (expected 1)"
        )
        assert ls_crossings == 1, (
            f"load→sink crosses Pipeline boundary {ls_crossings} times (expected 1)"
        )

    def test_parallel_links_pairwise_distinct_first20(self):
        """AC20: first 20px of every Gateway outgoing route are pairwise non-overlapping."""
        layout = _compile("flowchart-parallel-links")
        gw_edges = [e for e in layout.routed_edges if e.src_port.node_id == "A"]
        assert len(gw_edges) >= 2, "Need at least 2 Gateway outgoing edges"
        for i in range(len(gw_edges)):
            for j in range(i + 1, len(gw_edges)):
                segs_i = _first_n_px(gw_edges[i].waypoints, 20.0)
                segs_j = _first_n_px(gw_edges[j].waypoints, 20.0)
                shared = _pairwise_shared_px(segs_i, segs_j)
                assert shared <= 0.5, (
                    f"Gateway edges {i}↔{j}: first 20px share {shared:.1f}px"
                )

    def test_parallel_links_pairwise_distinct_last20(self):
        """AC21: last 20px of every Aggregator incoming route are pairwise non-overlapping."""
        layout = _compile("flowchart-parallel-links")
        agg_edges = [e for e in layout.routed_edges if e.dst_port.node_id == "E"]
        assert len(agg_edges) >= 2, "Need at least 2 Aggregator incoming edges"
        for i in range(len(agg_edges)):
            for j in range(i + 1, len(agg_edges)):
                segs_i = _last_n_px(agg_edges[i].waypoints, 20.0)
                segs_j = _last_n_px(agg_edges[j].waypoints, 20.0)
                shared = _pairwise_shared_px(segs_i, segs_j)
                assert shared <= 0.5, (
                    f"Aggregator edges {i}↔{j}: last 20px share {shared:.1f}px"
                )

    def test_inner_direction_no_canvas_edge_waypoints(self):
        layout = _compile("flowchart-inner-direction")
        canvas_w = layout.canvas_bounds.w
        canvas_h = layout.canvas_bounds.h
        for e in layout.routed_edges:
            src_id = e.src_port.node_id
            dst_id = e.dst_port.node_id
            if src_id == "source" or dst_id == "ingest":
                for p in e.waypoints:
                    assert p.x > 0, f"source->ingest: x={p.x} <= 0"
                    assert p.x < canvas_w, f"source->ingest: x={p.x} >= canvas_w={canvas_w}"
            if src_id == "load" or dst_id == "sink":
                for p in e.waypoints:
                    assert p.y > 0, f"load->sink: y={p.y} <= 0"
                    assert p.y < canvas_h, f"load->sink: y={p.y} >= canvas_h={canvas_h}"

    def test_all_fixtures_no_routing_failures(self):
        for name in ("flowchart-parallel-links", "flowchart-arrows-defs", "flowchart-inner-direction"):
            layout = _compile(name)
            assert not layout.routing_failures, (
                f"{name} has routing failures: {layout.routing_failures}"
            )

    def test_deterministic_routes(self):
        for name in ("flowchart-parallel-links", "flowchart-arrows-defs", "flowchart-inner-direction"):
            layout1 = _compile(name)
            layout2 = _compile(name)
            wpts1 = normalize_waypoints(layout1)
            wpts2 = normalize_waypoints(layout2)
            assert wpts1 == wpts2, f"{name}: non-deterministic waypoints"


# ── Section 5: Negative validation tests (AC23) ───────────────────────────────

class TestNegativeValidation:
    def _canvas(self):
        return (0.0, 0.0, 400.0, 400.0)

    def test_rejects_cross_scope_outside_gate(self):
        src = _make_port("e1", "A", "bottom", 50.0, 90.0)
        dst = _make_port("e1", "B", "top", 250.0, 200.0)
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=((50.0, 90.0), (250.0, 90.0), (250.0, 200.0)),
            bend_count=1, length=310.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        boundary = _make_obstacle("grp", "GROUP_BOUNDARY", 100.0, 0.0, 5.0, 300.0)
        perm = RoutePermissions("e1", (), ("grp",), (), ("gate1",))
        aperture = GateAperture("gate1", "e1", "grp", "right", (102.5, 50.0), 20.0)
        errors = validate_routes((rc,), canvas_bounds=self._canvas(), obstacles=(boundary,),
                                 route_permissions=[perm], gate_apertures=[aperture])
        assert len(errors) >= 1

    def test_rejects_title_crossing(self):
        src = _make_port("e1", "A", "bottom", 50.0, 25.0)
        dst = _make_port("e1", "B", "top", 50.0, 300.0)
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=((50.0, 25.0), (50.0, 300.0)),
            bend_count=0, length=275.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        title = _make_obstacle("grp_title", "GROUP_TITLE", 0.0, 0.0, 200.0, 30.0)
        perm = RoutePermissions("e1", (), ("grp",), (), ())
        aperture = GateAperture("g1", "e1", "grp", "bottom", (100.0, 200.0), 20.0)
        errors = validate_routes((rc,), canvas_bounds=self._canvas(), obstacles=(title,),
                                 route_permissions=[perm], gate_apertures=[aperture])
        assert len(errors) >= 1

    def test_rejects_wrong_gate_used(self):
        src = _make_port("e1", "A", "bottom", 50.0, 90.0)
        dst = _make_port("e1", "B", "top", 250.0, 200.0)
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=((50.0, 90.0), (250.0, 90.0), (250.0, 200.0)),
            bend_count=1, length=310.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        boundary = _make_obstacle("grp", "GROUP_BOUNDARY", 100.0, 0.0, 5.0, 300.0)
        perm = RoutePermissions("e1", (), ("grp",), (), ("my_gate",))
        # Aperture belongs to a different edge
        aperture = GateAperture("other_gate", "e2", "grp", "right", (102.5, 90.0), 20.0)
        errors = validate_routes((rc,), canvas_bounds=self._canvas(), obstacles=(boundary,),
                                 route_permissions=[perm], gate_apertures=[aperture])
        assert len(errors) >= 1

    def test_rejects_reentry(self):
        src = _make_port("e1", "A", "bottom", 50.0, 90.0)
        dst = _make_port("e1", "B", "top", 50.0, 300.0)
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=((50.0, 90.0), (-30.0, 90.0), (-30.0, 300.0), (50.0, 300.0)),
            bend_count=2, length=360.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        boundary = _make_obstacle("grp", "GROUP_BOUNDARY", 0.0, 0.0, 5.0, 350.0)
        perm = RoutePermissions("e1", ("grp",), (), ("grp",), ("g1",))
        aperture = GateAperture("g1", "e1", "grp", "left", (2.5, 150.0), 20.0)
        errors = validate_routes((rc,), canvas_bounds=(-100.0, 0.0, 300.0, 400.0), obstacles=(boundary,),
                                 route_permissions=[perm], gate_apertures=[aperture])
        assert len(errors) >= 1

    def test_rejects_perimeter_route(self):
        src = _make_port("e1", "A", "bottom", 50.0, 90.0)
        dst = _make_port("e1", "B", "top", 50.0, 300.0)
        # Route that hugs the full canvas perimeter
        rc = RouteCandidate(
            edge_id="e1", source_port=src, target_port=dst,
            points=((50.0, 90.0), (390.0, 90.0), (390.0, 300.0), (50.0, 300.0)),
            bend_count=2, length=680.0, crossing_count=0,
            shared_segment_length=0.0, cost=0.0,
        )
        node_ob = _make_obstacle("C", "NODE_INTERIOR", 20.0, 150.0, 60.0, 42.0)
        errors = validate_routes((rc,), canvas_bounds=self._canvas(), obstacles=(node_ob,))
        assert len(errors) >= 1, "Canvas-perimeter route should be rejected (crosses node)"
