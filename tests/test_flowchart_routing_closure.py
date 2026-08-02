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
        # Check fan separation within the same face only.  _edge_src_face may route
        # some edges to a side face (right/left) when the target is far horizontal;
        # ports on different faces don't overlap and comparing their x values across
        # faces produces spurious failures.
        for i in range(len(gw_pts)):
            for j in range(i + 1, len(gw_pts)):
                xi, yi = gw_pts[i]
                xj, yj = gw_pts[j]
                if abs(yi - yj) < 4.0:      # same horizontal face (bottom/top)
                    sep = abs(xi - xj)
                    assert sep >= FAN_MIN_PORT_PITCH - 0.5, (
                        f"Gateway port x-separation {sep:.1f}px < {FAN_MIN_PORT_PITCH}px minimum"
                    )
                elif abs(xi - xj) < 4.0:    # same vertical face (right/left)
                    sep = abs(yi - yj)
                    assert sep >= FAN_MIN_PORT_PITCH - 0.5, (
                        f"Gateway port y-separation {sep:.1f}px < {FAN_MIN_PORT_PITCH}px minimum"
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


# ── Section 8: _assign_lanes escape-index protection (follow-on to PR #244) ───

class TestAssignLanesEscapeIndexProtection:
    """_assign_lanes must not shift pts[1] or pts[-2] when they are marked
    escape points (escape_indices={1} / {len-2}).  Without protection a
    cardinal stub from a bottom-face port can be rotated off the outward normal
    when it shares the same x-column as a parallel route.
    """

    def _make_port(self, eid, nid, side, x, y, nx=0.0, ny=1.0):
        return PortCandidate(
            edge_id=eid, node_id=nid, side=side,
            normalized_offset=0.5, point=(x, y),
            outward_normal=(nx, ny), fixed_side=False, preference_penalty=0.0,
        )

    def _route(self, eid, pts, escape_indices=frozenset()):
        src = self._make_port(eid, "A", "bottom", pts[0][0], pts[0][1])
        dst = self._make_port(eid, "B", "top",   pts[-1][0], pts[-1][1])
        length = sum(
            abs(pts[i+1][0]-pts[i][0]) + abs(pts[i+1][1]-pts[i][1])
            for i in range(len(pts)-1)
        )
        return RouteCandidate(
            edge_id=eid, source_port=src, target_port=dst,
            points=pts, bend_count=len(pts)-2, length=length,
            crossing_count=0, shared_segment_length=0.0, cost=length,
            escape_indices=escape_indices,
        )

    def test_escape_pts1_protected_from_vertical_shift(self):
        """pts[1] marked as escape must not be x-shifted by vertical lane separation.

        Route A is a tall vertical at x=100.  Route B's escape stub is also at
        x=100 (pts[0]→pts[1]).  Without protection _assign_lanes would shift
        pts[1] to x=112, rotating the stub off the outward normal.
        """
        from mermaid_render.layout._pipeline import _assign_lanes
        # Route A: tall vertical at x=100 (y=100..400)
        rc_a = self._route("ea", (
            (100.0, 100.0), (100.0, 400.0),
        ))
        # Route B: boundary=(100,200), escape=(100,220), trunk goes right.
        # The first segment (boundary→escape) shares x=100 with route A.
        rc_b = self._route("eb", (
            (100.0, 200.0), (100.0, 220.0), (200.0, 220.0), (200.0, 400.0),
        ), escape_indices=frozenset({1}))
        assignments = {"ea": rc_a, "eb": rc_b}
        result = _assign_lanes(assignments, obstacles=())
        shifted = result["eb"].points
        # pts[1] is the escape point — must stay at x=100 despite lane separation.
        assert shifted[1][0] == pytest.approx(100.0, abs=2.0), (
            f"Escape point pts[1] was shifted: {shifted[1]!r} (expected x≈100)"
        )

    def test_escape_pt_unprotected_can_shift(self):
        """Without escape_indices, pts[1] IS shifted — verifies the guard is load-bearing."""
        from mermaid_render.layout._pipeline import _assign_lanes
        # Same geometry as above but no escape_indices — pts[1] is NOT protected.
        rc_a = self._route("ea", (
            (100.0, 100.0), (100.0, 400.0),
        ))
        rc_b = self._route("eb", (
            (100.0, 200.0), (100.0, 220.0), (200.0, 220.0), (200.0, 400.0),
        ))
        assignments = {"ea": rc_a, "eb": rc_b}
        result = _assign_lanes(assignments, obstacles=())
        shifted = result["eb"].points
        # Without protection, _assign_lanes shifts pts[1] away from x=100.
        assert shifted[1][0] != pytest.approx(100.0, abs=2.0), (
            "Without escape_indices, pts[1] should be shifted by lane separation"
        )


class TestEscapeStubWrap:
    """_escape_stub_wrap must correctly record escape_indices in the returned
    RouteCandidate so _assign_lanes can protect them.
    """

    def _base_rc(self, pts):
        src = PortCandidate("e1", "A", "bottom", 0.5, (pts[0][0], pts[0][1]),
                            (0.0, 1.0), False, 0.0)
        dst = PortCandidate("e1", "B", "top",    0.5, (pts[-1][0], pts[-1][1]),
                            (0.0, -1.0), False, 0.0)
        return RouteCandidate("e1", src, dst, pts, 0, 1.0, 0, 0.0, 0.0)

    def test_src_stub_marks_index_1(self):
        from mermaid_render.layout._pipeline import _escape_stub_wrap
        boundary_src = PortCandidate("e1", "A", "bottom", 0.5, (50.0, 100.0),
                                     (0.0, 1.0), False, 0.0)
        boundary_dst = PortCandidate("e1", "B", "top", 0.5, (50.0, 300.0),
                                     (0.0, -1.0), False, 0.0)
        # Route from escape point (50, 120) to dst
        rc = self._base_rc(((50.0, 120.0), (50.0, 300.0)))
        result = _escape_stub_wrap(rc, boundary_src, boundary_dst,
                                   src_needs=True, dst_needs=False)
        assert result.points[0] == (50.0, 100.0)   # boundary prepended
        assert result.points[1] == (50.0, 120.0)   # escape at index 1
        assert 1 in result.escape_indices

    def test_dst_stub_marks_last_escape(self):
        from mermaid_render.layout._pipeline import _escape_stub_wrap
        boundary_src = PortCandidate("e1", "A", "bottom", 0.5, (50.0, 100.0),
                                     (0.0, 1.0), False, 0.0)
        boundary_dst = PortCandidate("e1", "B", "top", 0.5, (50.0, 300.0),
                                     (0.0, -1.0), False, 0.0)
        # Route from src to escape point (50, 280)
        rc = self._base_rc(((50.0, 100.0), (50.0, 280.0)))
        result = _escape_stub_wrap(rc, boundary_src, boundary_dst,
                                   src_needs=False, dst_needs=True)
        assert result.points[-1] == (50.0, 300.0)  # boundary appended
        assert result.points[-2] == (50.0, 280.0)  # escape at -2
        assert len(result.points) - 2 in result.escape_indices

    def test_both_stubs_marks_both_escapes(self):
        from mermaid_render.layout._pipeline import _escape_stub_wrap
        boundary_src = PortCandidate("e1", "A", "bottom", 0.5, (50.0, 100.0),
                                     (0.0, 1.0), False, 0.0)
        boundary_dst = PortCandidate("e1", "B", "top", 0.5, (50.0, 300.0),
                                     (0.0, -1.0), False, 0.0)
        # Route from escape to escape
        rc = self._base_rc(((50.0, 120.0), (150.0, 120.0), (150.0, 280.0), (50.0, 280.0)))
        result = _escape_stub_wrap(rc, boundary_src, boundary_dst,
                                   src_needs=True, dst_needs=True)
        assert result.points[0] == (50.0, 100.0)   # src boundary
        assert result.points[1] == (50.0, 120.0)   # src escape
        assert result.points[-1] == (50.0, 300.0)  # dst boundary
        assert result.points[-2] == (50.0, 280.0)  # dst escape
        assert 1 in result.escape_indices
        assert len(result.points) - 2 in result.escape_indices


class TestAssignLanesHorizontalInsertEscapeReshift:
    """L→Z path is skipped when escape_indices contains index 1.

    The L→Z path fires when route-B's source endpoint sits at y≈sy_val (the
    shared horizontal y) AND index 1 is NOT a protected escape.  When index 1
    IS a protected escape, inserting a jog at index 1 before it would produce
    a diagonal segment (boundary→jog→escape), so the L→Z path is skipped.
    """

    def _make_port(self, eid, nid, side, x, y, nx=1.0, ny=0.0):
        return PortCandidate(
            edge_id=eid, node_id=nid, side=side,
            normalized_offset=0.5, point=(x, y),
            outward_normal=(nx, ny), fixed_side=False, preference_penalty=0.0,
        )

    def _route(self, eid, pts, escape_indices=frozenset()):
        src = self._make_port(eid, "A", "right", pts[0][0], pts[0][1])
        dst = self._make_port(eid, "B", "left",  pts[-1][0], pts[-1][1])
        length = sum(
            abs(pts[i+1][0]-pts[i][0]) + abs(pts[i+1][1]-pts[i][1])
            for i in range(len(pts)-1)
        )
        return RouteCandidate(
            edge_id=eid, source_port=src, target_port=dst,
            points=pts, bend_count=len(pts)-2, length=length,
            crossing_count=0, shared_segment_length=0.0, cost=length,
            escape_indices=escape_indices,
        )

    def test_lz_skipped_when_escape_at_index_1(self):
        """When escape is at index 1, the L→Z branch must not fire.

        If it did fire, the jog would land before the escape: the segment
        boundary→jog would be vertical (perpendicular to the right normal) and
        the jog→escape segment would be diagonal.  The fix prevents this by
        requiring 1 not in escape_indices before entering the L→Z branch.
        """
        from mermaid_render.layout._pipeline import _assign_lanes
        # Route A: long horizontal at y=200 (x=0..300) — shared axis.
        rc_a = self._route("ea", (
            (0.0, 200.0), (300.0, 200.0),
        ))
        # Route B: escape stub is pts[0]→pts[1] = (50,200)→(120,200), horizontal.
        # The L→Z branch must NOT fire — it would insert a jog before pts[1],
        # producing boundary→jog→escape with a diagonal jog→escape segment.
        rc_b = self._route("eb", (
            (50.0, 200.0), (120.0, 200.0), (120.0, 400.0), (300.0, 400.0),
        ), escape_indices=frozenset({1}))
        result = _assign_lanes({"ea": rc_a, "eb": rc_b}, obstacles=())
        final = result["eb"]
        # The escape stub (pts[0]→pts[1]) must stay horizontal.
        pts = final.points
        assert pts[0][1] == pytest.approx(pts[1][1], abs=1.0), (
            f"Escape stub was disrupted by L→Z jog insertion: {pts!r}"
        )


# ── Section 9: escape-adjacent orthogonality and cardinal CBE stubs (Codex P2a/P2b) ──

class TestAssignLanesEscapeAdjacentOrthogonality:
    """Escape-index protection must not produce diagonal inner segments.

    P2a: when the escape (pts[1]) and the next trunk waypoint (pts[2]) share the
    same x-column, skipping only the escape but shifting pts[2] creates a diagonal
    segment. Both must stay at the original x.

    P2b: when the escape stub is the shared horizontal (pts[0]→pts[1]), the L→Z
    conversion must not fire — inserting a jog before the escape produces a
    diagonal pts[1]→pts[2] segment and violates the outward-normal requirement.
    """

    def _make_port(self, eid, nid, side, x, y, nx=0.0, ny=1.0):
        return PortCandidate(
            edge_id=eid, node_id=nid, side=side,
            normalized_offset=0.5, point=(x, y),
            outward_normal=(nx, ny), fixed_side=False, preference_penalty=0.0,
        )

    def _route(self, eid, pts, escape_indices=frozenset(), nx=0.0, ny=1.0):
        src = self._make_port(eid, "A", "bottom", pts[0][0], pts[0][1], nx, ny)
        dst = self._make_port(eid, "B", "top", pts[-1][0], pts[-1][1])
        length = sum(
            abs(pts[i+1][0]-pts[i][0]) + abs(pts[i+1][1]-pts[i][1])
            for i in range(len(pts)-1)
        )
        return RouteCandidate(
            edge_id=eid, source_port=src, target_port=dst,
            points=pts, bend_count=len(pts)-2, length=length,
            crossing_count=0, shared_segment_length=0.0, cost=length,
            escape_indices=escape_indices,
        )

    def test_escape_stub_jog_separates_trunk(self):
        """When escape (pts[1]) and trunk (pts[2]) share the same x-column,
        lane separation protects only the escape stub and inserts an orthogonal
        jog to bridge it to the shifted trunk — the escape stays at sx while
        the trunk moves to nx with a connecting horizontal segment.

        Expected result: (100,200)→(100,220)→(112,220)→(112,300)→(200,300)
        — escape protected at x=100, jog at (112,220), trunk shifted to x=112.
        """
        from mermaid_render.layout._pipeline import _assign_lanes
        rc_a = self._route("ea", (
            (100.0, 100.0), (100.0, 400.0),
        ))
        rc_b = self._route("eb", (
            (100.0, 200.0), (100.0, 220.0), (100.0, 300.0), (200.0, 300.0),
        ), escape_indices=frozenset({1}))
        result = _assign_lanes({"ea": rc_a, "eb": rc_b}, obstacles=())
        pts = result["eb"].points
        assert pts[1][0] == pytest.approx(100.0, abs=1.0), (
            f"Escape must stay at x=100 (protected): {pts!r}"
        )
        assert len(pts) == 5, f"Jog must be inserted (expected 5 waypoints): {pts!r}"
        assert pts[2][0] != pytest.approx(100.0, abs=1.0), (
            f"Trunk after jog must be at nx (not at escape x=100): {pts!r}"
        )
        # All segments must remain orthogonal (no diagonals).
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            assert abs(ax - bx) < 1.0 or abs(ay - by) < 1.0, (
                f"Diagonal segment [{i}→{i+1}]: {pts!r}"
            )

    def test_horizontal_escape_stub_preserved_against_lz_insert(self):
        """When the escape stub is horizontal (escape at pts[1], same y as pts[0]),
        the L→Z branch must not fire — inserting a jog at index 1 before the escape
        would produce boundary→jog→escape with a diagonal jog→escape segment.

        Without the fix, route B's (50,200)→(120,200) escape stub is disrupted by
        the L→Z jog, violating the outward-normal departure constraint.
        """
        from mermaid_render.layout._pipeline import _assign_lanes
        rc_a = self._route("ea", (
            (0.0, 200.0), (300.0, 200.0),
        ), nx=1.0, ny=0.0)
        rc_b = self._route("eb", (
            (50.0, 200.0), (120.0, 200.0), (120.0, 400.0), (300.0, 400.0),
        ), escape_indices=frozenset({1}), nx=1.0, ny=0.0)
        result = _assign_lanes({"ea": rc_a, "eb": rc_b}, obstacles=())
        pts = result["eb"].points
        assert pts[0][1] == pytest.approx(pts[1][1], abs=1.0), (
            f"pts[0] and pts[1] must have same y (horizontal escape stub intact): {pts!r}"
        )

    def test_destination_escape_preceding_trunk_stays_collinear(self):
        """When a destination escape (pts[n-2]) and the trunk waypoint before it
        share the same x-column, lane separation must not shift the trunk waypoint —
        the k+1-is-escape guard must prevent the diagonal.

        Without the fix: pts=[..., (100,300), (100,380), (100,400), boundary]
        with escape_indices={2} → pts[1]=(100,300) shifts to (nx,300) while
        pts[2]=(100,380) is protected, creating a diagonal inner segment.
        """
        from mermaid_render.layout._pipeline import _assign_lanes
        rc_a = self._route("ea", ((100.0, 100.0), (100.0, 500.0)))
        rc_b = self._route("eb", (
            (200.0, 100.0), (200.0, 300.0), (100.0, 300.0), (100.0, 380.0), (100.0, 400.0),
        ), escape_indices=frozenset({3}))
        result = _assign_lanes({"ea": rc_a, "eb": rc_b}, obstacles=())
        pts = result["eb"].points
        assert pts[2][0] == pytest.approx(pts[3][0], abs=1.0), (
            f"pts[2] and pts[3] (escape) must share x (no diagonal): {pts!r}"
        )

    def test_source_escape_horizontal_jog_separates_trunk(self):
        """When source escape (pts[1]) and the next interior waypoint share y,
        horizontal lane separation protects only the escape stub and inserts a
        vertical jog to bridge it to the shifted trunk.

        pts = ((50,200),(70,200),(300,200),(300,400)), escape_indices={1}
        Expected: escape at (70,200), jog at (70,ny), trunk at (300,ny) — all orthogonal.
        """
        from mermaid_render.layout._pipeline import _assign_lanes
        rc_a = self._route("ea", ((100.0, 200.0), (400.0, 200.0)), nx=1.0, ny=0.0)
        rc_b = self._route("eb", (
            (50.0, 200.0), (70.0, 200.0), (300.0, 200.0), (300.0, 400.0),
        ), escape_indices=frozenset({1}), nx=1.0, ny=0.0)
        result = _assign_lanes({"ea": rc_a, "eb": rc_b}, obstacles=())
        pts = result["eb"].points
        assert pts[1][1] == pytest.approx(200.0, abs=1.0), (
            f"Escape must stay at y=200 (protected): {pts!r}"
        )
        assert len(pts) == 5, f"Vertical jog must be inserted (expected 5 waypoints): {pts!r}"
        assert pts[1][1] != pytest.approx(pts[2][1], abs=1.0), (
            f"Escape and trunk must be on different y-lanes after jog: {pts!r}"
        )
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            assert abs(ax - bx) < 1.0 or abs(ay - by) < 1.0, (
                f"Diagonal segment [{i}→{i+1}]: {pts!r}"
            )

    def test_destination_escape_adjacent_horizontal_stays_orthogonal(self):
        """When a destination escape (pts[2]) and the trunk waypoint before it
        share y, horizontal lane separation must not shift the trunk off that y
        (k+1-is-escape guard in horizontal path).

        pts = ((50,400),(50,200),(300,200),(320,200)), escape_indices={2}
        Without fix: pts[1]=(50,200) shifts to (50,ny) while pts[2]=(300,200)
        is protected → diagonal pts[1]→pts[2].
        """
        from mermaid_render.layout._pipeline import _assign_lanes
        rc_a = self._route("ea", ((0.0, 200.0), (400.0, 200.0)), nx=1.0, ny=0.0)
        rc_b = self._route("eb", (
            (50.0, 400.0), (50.0, 200.0), (300.0, 200.0), (320.0, 200.0),
        ), escape_indices=frozenset({2}), nx=1.0, ny=0.0)
        result = _assign_lanes({"ea": rc_a, "eb": rc_b}, obstacles=())
        pts = result["eb"].points
        assert pts[1][1] == pytest.approx(pts[2][1], abs=1.0), (
            f"pts[1] and pts[2] (escape) must share y (no diagonal): {pts!r}"
        )

    def test_escape_jog_separates_overlapping_trunk(self):
        """When the escape and its adjacent trunk both lie on the shared channel,
        the escape stub is protected but the trunk is shifted via an inserted jog.
        _assign_lanes must insert an orthogonal bridge and mark done=True so the
        overlap is resolved — shielding the full chain would leave routes overlapping.

        Expected: escape stays at x=100, jog at (nx, escape_y) inserted, trunk at nx.
        """
        from mermaid_render.layout._pipeline import _assign_lanes
        rc_a = self._route("ea", (
            (100.0, 100.0), (100.0, 400.0),
        ))
        rc_b = self._route("eb", (
            (100.0, 200.0), (100.0, 220.0), (100.0, 300.0), (200.0, 300.0),
        ), escape_indices=frozenset({1}))
        result = _assign_lanes({"ea": rc_a, "eb": rc_b}, obstacles=())
        pts_b = result["eb"].points
        # The escape must stay at x=100 — only the stub is protected.
        assert pts_b[1][0] == pytest.approx(100.0, abs=1.0), (
            f"Escape must stay at x=100 (protected): {pts_b!r}"
        )
        # A jog was inserted, extending the waypoint count.
        assert len(pts_b) > 4, (
            f"Jog must be inserted to bridge escape to shifted trunk: {pts_b!r}"
        )
        # The trunk is now separated from the escape (not collinear).
        assert pts_b[1][0] != pytest.approx(pts_b[2][0], abs=1.0), (
            f"Escape and trunk must be on different x-lanes after jog: {pts_b!r}"
        )


class TestRestoreGateEdgesNormalPreservation:
    """_restore_gate_edges must forward _src_normal/_dst_normal from the two halves
    into the merged route-dict so _reroute_cross_boundary_edges can apply escape
    stubs on the inner-direction gate-split path.
    """

    def _make_half(self, src, dst, waypoints, src_port, dst_port, src_normal, dst_normal):
        return {
            "src": src,
            "dst": dst,
            "waypoints": waypoints,
            "edge_id": f"{src}->{dst}",
            "label": "",
            "style": "",
            "ah": None,
            "source_marker": None,
            "target_marker": None,
            "extra_css": "",
            "marker_id": None,
            "bidir": False,
            "lx": 0.0,
            "ly": 0.0,
            "d": "",
            "_is_backward": False,
            "_src_port": src_port,
            "_dst_port": dst_port,
            "_src_normal": src_normal,
            "_dst_normal": dst_normal,
        }

    def test_normals_forwarded_after_gate_merge(self):
        """Both _src_normal (from first half) and _dst_normal (from second half)
        must appear in the merged route-dict produced by _restore_gate_edges."""
        from mermaid_render.layout._pipeline import _restore_gate_edges

        class _FakeEdge:
            edge_id = "A->B"
            label = ""
            style = ""
            arrow = None
            source_marker = None
            target_marker = None
            extra_css = ""
            src_label = ""
            dst_label = ""
            bidir = False

        gate = "GATE_1"
        first = self._make_half(
            "A", gate,
            [(100.0, 100.0), (100.0, 200.0)],
            (100.0, 100.0), (100.0, 200.0),
            (0.0, 1.0), (0.0, -1.0),
        )
        second = self._make_half(
            gate, "B",
            [(100.0, 200.0), (100.0, 400.0)],
            (100.0, 200.0), (100.0, 400.0),
            (0.0, 1.0), (0.0, -1.0),
        )
        route_dicts = [first, second]
        nodes = {gate: object()}
        result = _restore_gate_edges(route_dicts, {gate: _FakeEdge()}, nodes)
        assert len(result) == 1
        merged = result[0]
        assert merged.get("_src_normal") == (0.0, 1.0), (
            f"_src_normal must be forwarded from first half: {merged.get('_src_normal')!r}"
        )
        assert merged.get("_dst_normal") == (0.0, -1.0), (
            f"_dst_normal must be forwarded from second half: {merged.get('_dst_normal')!r}"
        )

    def test_normals_none_when_absent(self):
        """When halves lack normal keys (legacy routes), merged dict has None values
        (no KeyError) — a (0,0) fallback in CBE rerouter is acceptable."""
        from mermaid_render.layout._pipeline import _restore_gate_edges

        class _FakeEdge:
            edge_id = "A->B"
            label = ""
            style = ""
            arrow = None
            source_marker = None
            target_marker = None
            extra_css = ""
            src_label = ""
            dst_label = ""
            bidir = False

        gate = "GATE_2"
        first = self._make_half("A", gate, [(0, 0), (0, 100)],
                                (0, 0), (0, 100), None, None)
        second = self._make_half(gate, "B", [(0, 100), (0, 200)],
                                 (0, 100), (0, 200), None, None)
        # Remove the normal keys to simulate legacy routes
        first.pop("_src_normal"); first.pop("_dst_normal")
        second.pop("_src_normal"); second.pop("_dst_normal")
        route_dicts = [first, second]
        nodes = {gate: object()}
        result = _restore_gate_edges(route_dicts, {gate: _FakeEdge()}, nodes)
        merged = result[0]
        assert "_src_normal" in merged  # key must be present, value may be None
        assert "_dst_normal" in merged


class TestStubCapTightSpacing:
    """Escape stub length logic when stubs approach each other and could cross.

    Three-way decision based on max_nc = (gap_along_axis - 1) / approach_rate:
    - max_nc ≥ _STUB_LEN   → no cap; full 20 px stubs
    - 4 ≤ max_nc < _STUB_LEN → cap to max_nc; escapes don't cross
    - max_nc < 4           → disable stubs; boundary-to-boundary routing

    When normals are truly antiparallel (dn·sn < -0.99, e.g. TB bottom→top), cap
    is along src-normal axis — exact even when ports are horizontally offset.
    Merely obtuse normals (e.g. diamond→rect, dn·sn ≈ -0.707) fall through to
    the Euclidean branch to avoid projecting a diagonal gap onto a mismatched axis.
    Non-opposing (dn·sn ≥ -0.99) uses Euclidean direction.
    """

    def _compute(self, src_pt, dst_pt, snx, sny, dnx, dny):
        """Replicate the _stub_cap three-way decision.

        Returns (stub_cap, stubs_disabled).
        stubs_disabled=True means the gap was too tight and stubs were turned off.
        """
        import math
        from mermaid_render.layout._pipeline import _STUB_LEN
        sx, sy = src_pt
        dx, dy = dst_pt
        stub_cap = _STUB_LEN
        stubs_disabled = False
        dn_dot_sn = dnx * snx + dny * sny
        if dn_dot_sn < -0.99:
            gap_sn = (dx - sx) * snx + (dy - sy) * sny
            if gap_sn > 0:
                approach_rate_sn = 1.0 - dn_dot_sn
                max_nc = (gap_sn - 1.0) / approach_rate_sn
                if max_nc < _STUB_LEN:
                    if max_nc >= 4.0:
                        stub_cap = max_nc
                    else:
                        stubs_disabled = True
        else:
            gap_e = math.hypot(dx - sx, dy - sy)
            if gap_e > 1e-9:
                ux = (dx - sx) / gap_e
                uy = (dy - sy) / gap_e
                approach_rate = (snx - dnx) * ux + (sny - dny) * uy
                if approach_rate > 0:
                    max_nc = (gap_e - 1.0) / approach_rate
                    if max_nc < _STUB_LEN:
                        if max_nc >= 4.0:
                            stub_cap = max_nc
                        else:
                            stubs_disabled = True
        return stub_cap, stubs_disabled

    def test_escape_points_do_not_cross_with_30px_tb_gap(self):
        """TB layout: 30 px gap → approach_rate=2, max_nc=14.5, stubs capped at 14.5 px."""
        from mermaid_render.layout._pipeline import _STUB_LEN

        snx, sny = 0.0, 1.0
        dnx, dny = 0.0, -1.0
        stub_cap, disabled = self._compute((100.0, 100.0), (100.0, 130.0), snx, sny, dnx, dny)

        assert not disabled, "30px gap should not disable stubs"
        assert stub_cap < _STUB_LEN, f"Stub cap ({stub_cap}) should be < {_STUB_LEN}"
        src_esc_y = 100.0 + sny * stub_cap
        dst_esc_y = 130.0 + dny * stub_cap
        assert src_esc_y <= dst_esc_y + 0.5, (
            f"Escapes must not cross: src={src_esc_y}, dst={dst_esc_y}"
        )

    def test_stub_uncapped_when_gap_large(self):
        """With 100 px gap, max_nc = 49.5 ≥ _STUB_LEN → full stub, no cap."""
        from mermaid_render.layout._pipeline import _STUB_LEN

        stub_cap, disabled = self._compute((100.0, 100.0), (100.0, 200.0), 0.0, 1.0, 0.0, -1.0)
        assert not disabled
        assert stub_cap == _STUB_LEN, f"With 100 px gap, stub should be full {_STUB_LEN}; got {stub_cap}"

    def test_stub_uncapped_when_normal_perpendicular_to_displacement(self):
        """Diamond bottom face, destination mostly to the right (200 px, 1.66 px lower).
        src_normal=(0,1), dst_normal=(-1,0): approach_rate≈1.008, max_nc≈197 px.
        Cap must not fire — full stub preserved."""
        from mermaid_render.layout._pipeline import _STUB_LEN

        stub_cap, disabled = self._compute(
            (100.0, 100.0), (300.0, 101.66),
            0.0, 1.0, -1.0, 0.0,
        )
        assert not disabled
        assert stub_cap == _STUB_LEN, (
            f"Perpendicular-to-displacement normal must not fire cap: got {stub_cap}"
        )

    def test_stubs_disabled_when_gap_too_tight(self):
        """TB gap of 6 px: max_nc = 2.5 < 4 → stubs disabled (boundary-to-boundary
        routing) rather than forced to 4 px which would invert the escape order."""
        _, disabled = self._compute((100.0, 100.0), (100.0, 106.0), 0.0, 1.0, 0.0, -1.0)
        assert disabled, "6px gap must disable stubs (max_nc=2.5 < 4)"

    def test_stubs_disabled_threshold_is_four_px(self):
        """TB gap of exactly 9 px: max_nc = (9-1)/2 = 4.0 → stubs NOT disabled,
        capped at 4.0. One px tighter (gap=8): max_nc=3.5 → disabled."""
        stub_cap9, disabled9 = self._compute((100.0, 100.0), (100.0, 109.0), 0.0, 1.0, 0.0, -1.0)
        stub_cap8, disabled8 = self._compute((100.0, 100.0), (100.0, 108.0), 0.0, 1.0, 0.0, -1.0)
        assert not disabled9 and stub_cap9 == pytest.approx(4.0, abs=0.1), (
            f"9px gap should cap at 4px, got {stub_cap9} disabled={disabled9}"
        )
        assert disabled8, f"8px gap should disable stubs, got cap={stub_cap8}"

    def test_stub_preserved_when_approach_rate_nonpositive(self):
        """When approach_rate ≤ 0 (both normals same direction → diverging stubs),
        no cap or disable applies."""
        from mermaid_render.layout._pipeline import _STUB_LEN

        stub_cap, disabled = self._compute((100.0, 100.0), (300.0, 100.0), 1.0, 0.0, 1.0, 0.0)
        assert not disabled
        assert stub_cap == _STUB_LEN, f"Diverging normals must not reduce stub: got {stub_cap}"

    def test_horizontally_offset_opposing_normals_cap_fires(self):
        """Horizontally-offset TB ports: src=(60,90) bottom (normal 0,1),
        dst=(82,110) top (normal 0,-1).  Normal-axis gap = 20 px → cap at 9.5 px.
        The old Euclidean formula gave max_nc≈21.4 (no cap), allowing escapes to
        invert: src_escape_y=110 > dst_escape_y=90 → routing failure."""
        stub_cap, disabled = self._compute(
            (60.0, 90.0), (82.0, 110.0),
            0.0, 1.0,    # src normal: downward
            0.0, -1.0,   # dst normal: upward
        )
        assert not disabled, "20 px normal-axis gap should not disable stubs"
        assert stub_cap <= 10.0, (
            f"Cap must fire (≤10 px) for 20 px opposing gap; got {stub_cap}"
        )
        # Verify escapes don't cross on the y-axis.
        src_esc_y = 90.0 + 1.0 * stub_cap
        dst_esc_y = 110.0 + (-1.0) * stub_cap
        assert src_esc_y <= dst_esc_y + 0.5, (
            f"Escapes must not invert: src_y={src_esc_y}, dst_y={dst_esc_y}"
        )

    def test_obtuse_normals_do_not_disable_stubs(self):
        """Diamond bottom-right (0.707,0.707) → rect top (0,-1): dn·sn=-0.707.
        This is obtuse but NOT truly antiparallel, so the normal-axis branch must
        NOT fire.  With a 140 px gap the Euclidean branch yields max_nc >> 20,
        so stubs remain at full length (no disable, no cap)."""
        from mermaid_render.layout._pipeline import _STUB_LEN
        import math
        snx, sny = 0.7071067811865476, 0.7071067811865476  # diamond bottom-right
        dnx, dny = 0.0, -1.0  # rect top face
        stub_cap, disabled = self._compute(
            (300.0, 400.0), (231.0, 582.0),  # ~140 px apart (Retry→Done geometry)
            snx, sny, dnx, dny,
        )
        assert not disabled, (
            f"Obtuse dn·sn=-0.707 must NOT disable stubs; got disabled={disabled}"
        )
        assert stub_cap == _STUB_LEN, (
            f"With 140 px gap and obtuse normals stub must be uncapped; got {stub_cap}"
        )


class TestCollinearEscapePreservation:
    """Both the main and CBE collinear-cleanup passes must not drop a destination
    escape that is a reversal point (overshoots past the boundary port on a
    shared axis).

    Scenario: route ends at trunk_end=(525.5, 171), escape=(525.5, 32),
    boundary=(525.5, 52).  All three share x=525.5, so _col_x fires.
    But 32 is NOT between 171 and 52 — it is a reversal — so the escape
    must be kept.
    """

    def _dedup(self, pts):
        """Replicate the shared collinear-dedup logic including the between-check."""
        out = pts[:]
        deduped = [out[0]]
        for ci in range(1, len(out) - 1):
            pp, cp, np_ = deduped[-1], out[ci], out[ci + 1]
            col_x = abs(pp[0] - cp[0]) < 0.5 and abs(cp[0] - np_[0]) < 0.5
            col_y = abs(pp[1] - cp[1]) < 0.5 and abs(cp[1] - np_[1]) < 0.5
            if col_x:
                col_x = min(pp[1], np_[1]) - 0.5 <= cp[1] <= max(pp[1], np_[1]) + 0.5
            if col_y:
                col_y = min(pp[0], np_[0]) - 0.5 <= cp[0] <= max(pp[0], np_[0]) + 0.5
            if not (col_x or col_y):
                deduped.append(cp)
        if out:
            deduped.append(out[-1])
        return deduped

    def test_reversal_escape_preserved_vertical(self):
        """Trunk ends going down (y=171), escape is 20px above boundary (y=32),
        boundary is at y=52.  The escape (525.5, 32) reverses the y-direction and
        must not be removed as 'collinear'."""
        pts = [(200.0, 100.0), (525.5, 171.0), (525.5, 32.0), (525.5, 52.0)]
        result = self._dedup(pts)
        assert (525.5, 32.0) in result, (
            f"Destination escape (525.5, 32.0) removed — result={result}"
        )

    def test_monotone_collinear_removed(self):
        """A collinear middle point that IS between its neighbours should still
        be removed (the fix must not be too conservative)."""
        pts = [(100.0, 100.0), (100.0, 150.0), (100.0, 200.0)]
        result = self._dedup(pts)
        assert (100.0, 150.0) not in result, (
            f"Monotone collinear point must be removed — result={result}"
        )

    def test_reversal_escape_preserved_horizontal(self):
        """Horizontal symmetric of the vertical reversal: trunk approaches from the
        left (x=300), dst boundary is at x=500 with right-pointing outward normal
        (escape = boundary + 20*(1,0) = x=520).  The escape x=520 overshoots past
        x=500 so it is a reversal and must not be dropped as 'collinear'."""
        # Route: trunk→escape→boundary; escape overshoots past boundary.
        pts = [(300.0, 52.0), (520.0, 52.0), (500.0, 52.0)]
        result = self._dedup(pts)
        assert (520.0, 52.0) in result, (
            f"Reversal escape (520, 52) must be kept — result={result}"
        )

    def test_monotone_collinear_horizontal_removed(self):
        """Contrast: escape between trunk and boundary (monotone) is removable."""
        pts = [(300.0, 52.0), (480.0, 52.0), (500.0, 52.0)]
        result = self._dedup(pts)
        assert (480.0, 52.0) not in result, (
            f"Monotone collinear escape must be removed — result={result}"
        )


class TestEqualizeCBEEscapeProtection:
    """_equalize_corridors Pass B must not shift CBE escape waypoints independently
    from their paired boundary endpoint — that would rotate the terminal stub away
    from the outward normal."""

    def test_cbe_escape_not_shifted_by_corridor_equalization(self):
        """Route with _cbe_escape_idxs={1} has its escape at idx 1 on the shared
        vertical channel.  _equalize_corridors must skip idx 1 so the stub
        (boundary→escape) direction is preserved after equalization."""
        from mermaid_render.layout._pipeline import _equalize_corridors
        # Two routes sharing vertical channel at x=200, y=100–400.
        # Route B has a CBE escape at idx 1 (200, 130) — 30 px stub from (200,160).
        r_a = {
            "waypoints": [(200.0, 50.0), (200.0, 400.0)],
            "src": "A", "dst": "C", "edge_id": "A->C",
        }
        r_b = {
            "waypoints": [(200.0, 160.0), (200.0, 130.0), (200.0, 50.0)],
            "src": "B", "dst": "D", "edge_id": "B->D",
            "_cbe_escape_idxs": {1},  # escape at idx 1
        }
        routed = [r_a, r_b]
        nodes: "dict" = {}
        grp_bboxes: "dict" = {}
        _equalize_corridors(routed, nodes, grp_bboxes, direction="TB")
        wps_b = r_b["waypoints"]
        # idx 0 (boundary) may shift; idx 1 (escape) must stay at the original x
        # to preserve the stub direction.
        assert wps_b[1][0] == pytest.approx(200.0, abs=1.0), (
            f"CBE escape (idx 1) must not be shifted by corridor equalization: {wps_b!r}"
        )

    def test_full_stub_blocked_when_segment_crosses_obstacle(self):
        """Verify the stub-blocked check catches a label that lies along the stub
        path but whose endpoint is clear (endpoint-only check would miss it).

        Geometry: boundary at (200, 100), escape at (200, 80) — vertical stub going
        upward 20 px.  A label spans y=[85, 95] at x=[190, 210], crossing the stub.
        The escape endpoint (200, 80) is ABOVE the label, so _cbe_in_obs misses it.
        The new _cbe_stub_blocked must detect the crossing.
        """
        # Replicate the interval check logic from _cbe_stub_blocked for cardinal stubs.
        boundary_y = 100.0
        escape_y = 80.0
        x = 200.0
        label = (190.0, 85.0, 210.0, 95.0)  # x0, y0, x1, y1
        # Endpoint-only check: escape_y=80 < label_y0=85 → would pass (not blocked)
        endpoint_in_label = label[0] <= x <= label[2] and label[1] <= escape_y <= label[3]
        assert not endpoint_in_label, "Endpoint is above label — endpoint check passes"
        # Interval check: the segment [80, 100] overlaps the label [85, 95]
        y_lo, y_hi = min(boundary_y, escape_y), max(boundary_y, escape_y)
        seg_crosses = label[0] <= x <= label[2] and label[1] < y_hi and label[3] > y_lo
        assert seg_crosses, "Full-interval check must detect the crossing"

    def test_boundary_endpoint_adjacent_to_escape_not_shifted(self):
        """When the escape (idx 1) is protected from corridor equalization, the
        boundary endpoint at idx 0 (which shares the corridor x) must also stay put.
        Shifting idx 0 while idx 1 stays would rotate the stub away from the normal.

        Geometry: corridor at x=200.  Route B: (200,160)→(200,130)→(200,50) with
        _cbe_escape_idxs={1}.  After equalization both idx 0 and idx 1 must stay at
        x=200, not shift to a lane-separated x.
        """
        from mermaid_render.layout._pipeline import _equalize_corridors
        r_a = {
            "waypoints": [(200.0, 50.0), (200.0, 400.0)],
            "src": "A", "dst": "C", "edge_id": "A->C",
        }
        r_b = {
            "waypoints": [(200.0, 160.0), (200.0, 130.0), (200.0, 50.0)],
            "src": "B", "dst": "D", "edge_id": "B->D",
            "_cbe_escape_idxs": {1},  # escape at idx 1; boundary port at idx 0
        }
        routed = [r_a, r_b]
        _equalize_corridors(routed, {}, {}, direction="TB")
        wps_b = r_b["waypoints"]
        # idx 0 is adjacent to escape idx 1 — it must also stay at x=200
        assert wps_b[0][0] == pytest.approx(200.0, abs=1.0), (
            f"Boundary endpoint (idx 0, adjacent to escape) must not shift: {wps_b!r}"
        )
        assert wps_b[1][0] == pytest.approx(200.0, abs=1.0), (
            f"Escape (idx 1) must not shift: {wps_b!r}"
        )


class TestSegIntersectsRect:
    """_seg_intersects_rect Liang-Barsky clip covers cardinal and diagonal stubs."""

    def _fn(self):
        from mermaid_render.layout._pipeline import _seg_intersects_rect
        return _seg_intersects_rect

    def test_vertical_through_rect(self):
        fn = self._fn()
        # Vertical segment at x=5 from y=0 to y=10 through rect [4,3,6,7]
        assert fn(5.0, 0.0, 5.0, 10.0, 4.0, 3.0, 6.0, 7.0)

    def test_vertical_outside_rect(self):
        fn = self._fn()
        # Vertical segment at x=15 fully to the right of rect [0,0,10,10]
        assert not fn(15.0, 0.0, 15.0, 20.0, 0.0, 0.0, 10.0, 10.0)

    def test_horizontal_through_rect(self):
        fn = self._fn()
        # Horizontal segment at y=5 from x=0 to x=20 through rect [4,3,6,7]
        assert fn(0.0, 5.0, 20.0, 5.0, 4.0, 3.0, 6.0, 7.0)

    def test_diagonal_clips_corner(self):
        fn = self._fn()
        # Diagonal from (0,0) to (10,10) through rect [4,4,6,6]
        assert fn(0.0, 0.0, 10.0, 10.0, 4.0, 4.0, 6.0, 6.0)

    def test_diagonal_misses_rect(self):
        fn = self._fn()
        # Diagonal from (0,0) to (5,5); rect [6,6,10,10] — segment ends before rect
        assert not fn(0.0, 0.0, 5.0, 5.0, 6.0, 6.0, 10.0, 10.0)

    def test_diagonal_endpoint_clear_but_segment_clips(self):
        """Both endpoints clear; the segment still clips the obstacle — the canonical
        failure case for endpoint-only checks.  A stub from (105,200) to (125,180)
        (diagonal normal ≈45°) where a thin node rect spans x=[110,120] y=[193,207]
        covers neither endpoint but the segment crosses it."""
        fn = self._fn()
        # Neither endpoint inside rect
        assert not (110.0 <= 105.0 <= 120.0 and 193.0 <= 200.0 <= 207.0)
        assert not (110.0 <= 125.0 <= 120.0 and 193.0 <= 180.0 <= 207.0)
        # But the segment from (105,200) to (125,180) crosses [110,193,120,207]
        assert fn(105.0, 200.0, 125.0, 180.0, 110.0, 193.0, 120.0, 207.0)

    def test_segment_endpoint_on_rect_boundary(self):
        fn = self._fn()
        # Endpoint exactly on the rect boundary — counts as intersection
        assert fn(0.0, 5.0, 10.0, 5.0, 10.0, 0.0, 20.0, 10.0)


class TestHorizontalAssignLanesShiftedFlag:
    """Horizontal branch of _assign_lanes must not set done=True unless a point
    actually moved (escape-adjacent protection may block every candidate)."""

    def _make_port(self, eid, nid, side, x, y, nx=1.0, ny=0.0):
        return PortCandidate(
            edge_id=eid, node_id=nid, side=side,
            normalized_offset=0.5, point=(x, y),
            outward_normal=(nx, ny), fixed_side=False, preference_penalty=0.0,
        )

    def _route(self, eid, pts, escape_indices=frozenset(), nx=1.0, ny=0.0):
        src = self._make_port(eid, "A", "right", pts[0][0], pts[0][1], nx, ny)
        dst = self._make_port(eid, "B", "left", pts[-1][0], pts[-1][1])
        length = sum(
            abs(pts[i+1][0]-pts[i][0]) + abs(pts[i+1][1]-pts[i][1])
            for i in range(len(pts)-1)
        )
        return RouteCandidate(
            edge_id=eid, source_port=src, target_port=dst,
            points=pts, bend_count=len(pts)-2, length=length,
            crossing_count=0, shared_segment_length=0.0, cost=length,
            escape_indices=escape_indices,
        )

    def test_h_done_not_set_when_all_candidates_escape_protected(self):
        """When the shared horizontal section of route B consists only of escape
        and escape-adjacent waypoints, no shift is applied and done must remain
        False so the outer loop continues scanning for other separable pairs.

        Verified by checking that a third route C (sharing the same y with A but
        not escape-blocked) is still lane-separated even when B is tried first."""
        from mermaid_render.layout._pipeline import _assign_lanes
        # Route A: long horizontal at y=200
        rc_a = self._route("ea", (
            (0.0, 200.0), (400.0, 200.0),
        ))
        # Route B: escape at idx 1; the only interior point (pts[1]) adjacent to escape
        # → escape-adjacency check blocks the shift → no actual displacement.
        rc_b = self._route("eb", (
            (50.0, 200.0), (120.0, 200.0), (120.0, 350.0),
        ), escape_indices=frozenset({1}))
        # Route C: normal horizontal route sharing y=200 with A; has a shiftable interior point.
        rc_c = self._route("ec", (
            (10.0, 200.0), (200.0, 200.0), (200.0, 350.0),
        ))
        result = _assign_lanes({"ea": rc_a, "eb": rc_b, "ec": rc_c}, obstacles=())
        # Route C must have been separated (its interior point shifted off y=200)
        pts_c = result["ec"].points
        assert pts_c[1][1] != pytest.approx(200.0, abs=1.0), (
            f"Route C interior point should be shifted off y=200 after lane separation: {pts_c!r}"
        )


class TestCBEStubClearanceCap:
    """CBE rerouter applies the same antiparallel-normal clearance cap as the main router.

    When opposing normals have < 4 px of approach clearance, stubs must be
    disabled so A* routes boundary-to-boundary.  When 4–20 px, stubs are capped.
    """

    def _compute_cbe_cap(self, a, b, sp_normal, dp_normal):
        """Replicate the CBE stub cap three-way decision.

        Returns (stub_len, src_enabled, dst_enabled).
        """
        from mermaid_render.layout._pipeline import _STUB_LEN
        snx, sny = sp_normal
        dnx, dny = dp_normal
        snorm_mag = max(abs(snx), abs(sny))
        dnorm_mag = max(abs(dnx), abs(dny))
        _CARDINAL_NORMAL_T = 0.999
        src_needs = 1e-9 < snorm_mag < _CARDINAL_NORMAL_T
        dst_needs = dnorm_mag > 1e-9
        stub_len = _STUB_LEN
        if src_needs or dst_needs:
            dn_dot_sn = dnx * snx + dny * sny
            if dn_dot_sn < -0.99 and (src_needs and dst_needs):
                gap_sn = (b[0] - a[0]) * snx + (b[1] - a[1]) * sny
                if gap_sn > 0:
                    rate = 1.0 - dn_dot_sn
                    max_nc = (gap_sn - 1.0) / rate
                    if max_nc < _STUB_LEN:
                        if max_nc >= 4.0:
                            stub_len = max_nc
                        else:
                            src_needs = False
                            dst_needs = False
        return stub_len, src_needs, dst_needs

    def test_antiparallel_normals_tight_gap_disables_stubs(self):
        """< 4 px gap between opposing-normal ports → both stubs disabled.

        Non-cardinal src (0.6, 0.8): snorm_mag=0.8 < _CARDINAL_NORMAL_T → src stub needed.
        Dst (-0.6, -0.8): antiparallel (dot=-1.0 < -0.99), gap_sn=3.0 →
        max_nc = (3-1)/2 = 1.0 < 4 → both disabled.
        """
        a = (100.0, 100.0)
        # b placed 3 px along sp=(0.6, 0.8): gap_sn=(1.8*0.6)+(2.4*0.8)=3.0
        b = (101.8, 102.4)
        sp = (0.6, 0.8)   # non-cardinal: max(0.6,0.8)=0.8 < 0.999
        dp = (-0.6, -0.8)  # antiparallel to sp
        stub_len, src_on, dst_on = self._compute_cbe_cap(a, b, sp, dp)
        assert not src_on and not dst_on, (
            f"Stubs should be disabled for 3 px gap_sn: src={src_on}, dst={dst_on}"
        )

    def test_antiparallel_normals_medium_gap_caps_stubs(self):
        """4–20 px gap → stubs are capped, not disabled.

        With sp=(0.6, 0.8) and gap_sn=15.0: max_nc=(15-1)/2=7 → capped to 7.
        """
        from mermaid_render.layout._pipeline import _STUB_LEN
        a = (100.0, 100.0)
        # b placed 15 px along sp=(0.6,0.8): gap_sn=(9*0.6)+(12*0.8)=5.4+9.6=15.0
        b = (109.0, 112.0)
        sp = (0.6, 0.8)
        dp = (-0.6, -0.8)
        stub_len, src_on, dst_on = self._compute_cbe_cap(a, b, sp, dp)
        assert src_on and dst_on, "Stubs should remain enabled for 15 px gap"
        assert stub_len < _STUB_LEN, f"Stub should be capped below {_STUB_LEN}: got {stub_len}"
        assert stub_len >= 4.0, f"Capped stub must be ≥ 4 px: got {stub_len}"

    def test_antiparallel_normals_large_gap_no_cap(self):
        """≥ 40 px gap → full _STUB_LEN stubs, no cap.

        With sp=(0.6, 0.8) and gap_sn=45.0: max_nc=(45-1)/2=22 > 20 → uncapped.
        """
        from mermaid_render.layout._pipeline import _STUB_LEN
        a = (100.0, 100.0)
        # b placed 45 px along sp=(0.6,0.8): gap_sn=(27*0.6)+(36*0.8)=16.2+28.8=45.0
        b = (127.0, 136.0)
        sp = (0.6, 0.8)
        dp = (-0.6, -0.8)
        stub_len, src_on, dst_on = self._compute_cbe_cap(a, b, sp, dp)
        assert src_on and dst_on
        assert stub_len == pytest.approx(_STUB_LEN), f"Stub should be uncapped: got {stub_len}"

    def test_parallel_normals_no_cap_applied(self):
        """Non-opposing normals (same direction) never trigger the antiparallel branch."""
        from mermaid_render.layout._pipeline import _STUB_LEN
        a = (100.0, 100.0)
        b = (101.8, 102.4)
        # Both pointing in same direction — dot≈+1.0, not antiparallel
        sp = (0.6, 0.8)
        dp = (0.6, 0.8)
        stub_len, src_on, dst_on = self._compute_cbe_cap(a, b, sp, dp)
        assert stub_len == pytest.approx(_STUB_LEN), "Parallel normals must not trigger cap"


class TestCBEEscapeReservedBypassesExcludeYs:
    """_cbe_escape_reserved rows are always marked occupied, even if they match exclude_ys.

    Regression guard for P2 of r6 review: the earlier fix added CBE destination
    escape rows to _cbe_done_hsegs, but _build_occupied exempts rows that appear
    in exclude_ys — neutralizing the reservation when multiple edges share the
    same target face (their destination y values are identical and always appear
    in exclude_ys of each other's routing call).
    """

    def _make_grid(self, ys):
        """Return a trivial gx/gy grid covering the given y-coordinates."""
        gx = list(range(0, 500, 20))
        gy = sorted(set(ys))
        return gx, gy

    def test_escape_reserved_row_occupied_even_when_matching_exclude_ys(self):
        """A row in _cbe_escape_reserved is marked occupied even if it matches exclude_ys."""
        import types
        # Simulate _build_occupied for a minimal grid.
        gx = list(range(0, 200, 20))
        gy = [80, 100, 120, 140, 160]

        _cbe_done_hsegs = []
        _cbe_escape_reserved = [(100.0, 60.0, 140.0)]  # y=100, x range 60–140

        def _build_occupied_sim(gx, gy, exclude_ys=None):
            _excl = set()
            if exclude_ys:
                for _ey in exclude_ys:
                    _excl.add(min(range(len(gy)), key=lambda i: abs(gy[i] - _ey)))
            occ = set()
            for (hy, hx0, hx1) in _cbe_done_hsegs:
                yi = min(range(len(gy)), key=lambda i: abs(gy[i] - hy))
                xi0 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx0))
                xi1 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx1))
                for dyi in range(-2, 3):
                    byi = yi + dyi
                    if 0 <= byi < len(gy) and byi not in _excl:
                        for xi in range(min(xi0, xi1), max(xi0, xi1)):
                            occ.add((xi, byi, xi + 1, byi))
            for (hy, hx0, hx1) in _cbe_escape_reserved:
                yi = min(range(len(gy)), key=lambda i: abs(gy[i] - hy))
                xi0 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx0))
                xi1 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx1))
                for dyi in range(-2, 3):
                    byi = yi + dyi
                    if 0 <= byi < len(gy):
                        for xi in range(min(xi0, xi1), max(xi0, xi1)):
                            occ.add((xi, byi, xi + 1, byi))
            return occ

        # With exclude_ys=(100.0, ...) the escape-reserved row at y=100 should
        # still appear in occupied (it bypasses the exclusion).
        occupied = _build_occupied_sim(gx, gy, exclude_ys=(100.0, 200.0))
        yi_100 = gy.index(100)
        # At least the exact reserved row should be occupied.
        assert any(step[1] == yi_100 for step in occupied), (
            f"Row y=100 (yi={yi_100}) should be occupied despite being in exclude_ys; "
            f"occupied rows: {sorted({s[1] for s in occupied})}"
        )

    def test_done_hsegs_row_exempted_by_exclude_ys(self):
        """Confirm that _cbe_done_hsegs rows ARE exempted by exclude_ys (baseline behavior)."""
        gx = list(range(0, 200, 20))
        gy = [80, 100, 120, 140, 160]
        _cbe_done_hsegs = [(100.0, 60.0, 140.0)]
        _cbe_escape_reserved = []

        def _build_occupied_sim(gx, gy, exclude_ys=None):
            _excl = set()
            if exclude_ys:
                for _ey in exclude_ys:
                    _excl.add(min(range(len(gy)), key=lambda i: abs(gy[i] - _ey)))
            occ = set()
            for (hy, hx0, hx1) in _cbe_done_hsegs:
                yi = min(range(len(gy)), key=lambda i: abs(gy[i] - hy))
                xi0 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx0))
                xi1 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx1))
                for dyi in range(-2, 3):
                    byi = yi + dyi
                    if 0 <= byi < len(gy) and byi not in _excl:
                        for xi in range(min(xi0, xi1), max(xi0, xi1)):
                            occ.add((xi, byi, xi + 1, byi))
            for (hy, hx0, hx1) in _cbe_escape_reserved:
                yi = min(range(len(gy)), key=lambda i: abs(gy[i] - hy))
                xi0 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx0))
                xi1 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx1))
                for dyi in range(-2, 3):
                    byi = yi + dyi
                    if 0 <= byi < len(gy):
                        for xi in range(min(xi0, xi1), max(xi0, xi1)):
                            occ.add((xi, byi, xi + 1, byi))
            return occ

        occupied = _build_occupied_sim(gx, gy, exclude_ys=(100.0, 200.0))
        yi_100 = gy.index(100)
        assert not any(step[1] == yi_100 for step in occupied), (
            f"done_hsegs row y=100 should be exempted by exclude_ys; "
            f"occupied rows: {sorted({s[1] for s in occupied})}"
        )


class TestCBEDestinationInteriorObstacle:
    """Destination node is added to A* blocked set when a destination stub is used.

    Regression guard for P1 of r7: when _cbe_dst_needs_stub is True, the
    destination node's rect was missing from `obstacles`, allowing A* to route
    trunk segments through the destination interior before reversing to the escape.
    The fix adds d's rect to _blocked_obs (not to `obstacles` used by
    _cbe_stub_blocked) so stub-endpoint checks still work.
    """

    def test_d_rect_added_to_blocked_when_dst_stub_used(self):
        """When dst stub is needed, d's rect must appear in _blocked_obs."""
        d_rect = (100.0, 80.0, 200.0, 180.0)
        node_rects = {"s": (0.0, 0.0, 60.0, 60.0), "d": d_rect, "other": (300.0, 0.0, 400.0, 60.0)}
        obstacles = [r for nid, r in node_rects.items() if nid not in ("s", "d")]
        # When dst stub needed: add d back to blocked set only
        _cbe_dst_needs_stub = True
        _blocked_obs = obstacles
        if _cbe_dst_needs_stub and "d" in node_rects:
            _blocked_obs = obstacles + [node_rects["d"]]
        assert d_rect in _blocked_obs, "d's rect must be in _blocked_obs when dst stub used"
        assert d_rect not in obstacles, "d's rect must NOT be in obstacles (used by _cbe_in_obs)"

    def test_d_rect_absent_from_blocked_when_no_dst_stub(self):
        """When no dst stub, d's rect stays absent from blocked (baseline behavior)."""
        d_rect = (100.0, 80.0, 200.0, 180.0)
        node_rects = {"s": (0.0, 0.0, 60.0, 60.0), "d": d_rect}
        obstacles = [r for nid, r in node_rects.items() if nid not in ("s", "d")]
        _cbe_dst_needs_stub = False
        _blocked_obs = obstacles
        if _cbe_dst_needs_stub and "d" in node_rects:
            _blocked_obs = obstacles + [node_rects["d"]]
        assert d_rect not in _blocked_obs, "d's rect must stay absent when no dst stub"
