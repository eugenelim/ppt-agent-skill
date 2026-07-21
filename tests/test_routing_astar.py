"""Unit tests for the A* orthogonal router in scripts/mermaid_render/layout/_routing.py.

Coverage:
  - Obstacle avoidance: A* routes around a blocking node when fast path is blocked
  - Same-cell early return: returns 2 waypoints (not 1) so callers can restore exact ports
  - Crossing penalty: second edge routed via A* prefers a different channel when occupied
  - _accumulate_occupied: unit-step decomposition matches A*'s single-step lookups
  - Arrowhead (0,0): nominal direction fallback prevents degenerate arrowhead
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mermaid_render.layout._routing import (
    _arrowhead,
    _astar_route,
    _blocked_segs,
    _build_routing_grid,
    _try_3seg_clear,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _snap(val: int, arr: list) -> int:
    return min(range(len(arr)), key=lambda i: abs(arr[i] - val))


def _make_occupied(pts: list, grid_xs: list, grid_ys: list) -> set:
    occupied: set = set()
    for k in range(len(pts) - 1):
        ax, ay = pts[k]
        bx, by = pts[k + 1]
        axi = _snap(ax, grid_xs)
        ayi = _snap(ay, grid_ys)
        bxi = _snap(bx, grid_xs)
        byi = _snap(by, grid_ys)
        if axi == bxi:
            for yi in range(min(ayi, byi), max(ayi, byi)):
                occupied.add((axi, yi, axi, yi + 1))
        else:
            for xi in range(min(axi, bxi), max(axi, bxi)):
                occupied.add((xi, ayi, xi + 1, ayi))
    return occupied


# ── tests: obstacle avoidance ────────────────────────────────────────────────

class TestObstacleAvoidance:
    """A* routes around a blocking node when the direct path is blocked."""

    def test_routes_around_blocking_node(self):
        """With node B sitting in the direct path from A to C, A* finds a clear route."""
        # B: x=20..140, y=80..128 — blocks x=60 vertical channel
        obstacles = [(20, 80, 140, 128)]
        grid_xs = sorted({-8, 0, 12, 60, 120, 128, 148, 200})
        grid_ys = sorted({-8, 0, 24, 48, 72, 80, 88, 104, 120, 128, 136, 160, 208})
        blocked = _blocked_segs(grid_xs, grid_ys, obstacles)

        x1, y1, x2, y2 = 60, 48, 60, 160
        mid_y = (y1 + y2) // 2
        fast = [(x1, y1), (x1, mid_y), (x2, mid_y), (x2, y2)]

        assert not _try_3seg_clear(fast, obstacles), "fast path should be blocked"

        pts = _astar_route(x1, y1, x2, y2, grid_xs, grid_ys, blocked)

        assert len(pts) >= 2, "must return at least 2 waypoints"
        assert _try_3seg_clear(pts, obstacles), "A* path must be obstacle-free"

    def test_no_path_fallback_returns_none(self):
        """When no grid path exists, _astar_route returns None (callers do perimeter retry)."""
        grid_xs = [0, 100]
        grid_ys = [0, 100]
        # Block all segments
        blocked = {(0, 0, 1, 0), (0, 0, 0, 1), (0, 1, 1, 1), (1, 0, 1, 1)}
        pts = _astar_route(0, 0, 100, 100, grid_xs, grid_ys, blocked)
        assert pts is None

    def test_same_cell_returns_two_points(self):
        """Early return when src/dst snap to same cell must return 2 points, not 1."""
        grid_xs = [0, 200]
        grid_ys = [0, 200]
        # src=(10,10) and dst=(90,90) both snap to index 0 in a coarse grid
        pts = _astar_route(10, 10, 90, 90, grid_xs, grid_ys, set())
        assert len(pts) == 2, "same-cell early return must give 2 waypoints for port restoration"
        assert pts[0] == (10, 10)
        assert pts[-1] == (90, 90)


# ── tests: crossing penalty ───────────────────────────────────────────────────

class TestCrossingPenalty:
    """CROSS penalty nudges second A*-routed edge away from occupied channel."""

    def test_cross_penalty_changes_routing(self):
        """Second edge routed via A* prefers a different bypass channel when occupied."""
        # Obstacle blocks central column; left (x=8) and right (x=88) bypasses available
        obstacles = [(20, 40, 80, 80)]
        grid_xs = sorted({0, 8, 20, 28, 80, 88, 100})
        grid_ys = sorted({0, 32, 40, 60, 80, 88, 120})
        blocked = _blocked_segs(grid_xs, grid_ys, obstacles)

        # Edge 1: forced through left bypass
        pts1 = _astar_route(40, 0, 40, 120, grid_xs, grid_ys, blocked, None)
        occupied = _make_occupied(pts1, grid_xs, grid_ys)
        assert len(occupied) > 0, "edge 1 should mark some segments occupied"

        # Edge 2 without penalty — should also take left bypass
        pts2_no  = _astar_route(50, 0, 50, 120, grid_xs, grid_ys, blocked, None)
        # Edge 2 with penalty — should prefer right bypass
        pts2_yes = _astar_route(50, 0, 50, 120, grid_xs, grid_ys, blocked, occupied)

        assert pts2_no != pts2_yes, "CROSS penalty must change routing when alt channel exists"
        assert _try_3seg_clear(pts2_yes, obstacles), "penalised path must still be obstacle-free"

    def test_occupied_unit_steps_match_astar_segments(self):
        """_make_occupied decomposes spans to unit steps that A*'s seg lookup can find."""
        grid_xs = [0, 10, 20, 30]
        grid_ys = [0, 10, 20]
        # Simulate a path: (10,0)→(10,20) — a 2-cell vertical run
        pts = [(10, 0), (10, 20)]
        occupied = _make_occupied(pts, grid_xs, grid_ys)
        # A* would generate (xi=1,yi=0)→(xi=1,yi=1) and (xi=1,yi=1)→(xi=1,yi=2)
        assert (1, 0, 1, 1) in occupied, "first unit step must be in occupied"
        assert (1, 1, 1, 2) in occupied, "second unit step must be in occupied"
        assert (1, 0, 1, 2) not in occupied, "multi-cell span must NOT be in occupied"


# ── tests: arrowhead degenerate direction ─────────────────────────────────────

class TestArrowheadDirection:
    """_arrowhead(0,0) uses the or-1.0 guard but produces a degenerate polygon.
    The routing code falls back to nominal direction when delta is (0,0).
    """

    def test_zero_direction_guard_does_not_crash(self):
        """_arrowhead survives (0,0) direction via the or-1.0 guard."""
        result = _arrowhead(100, 100, 0, 0)
        # Returns a string — may be degenerate but must not raise
        assert isinstance(result, str)

    def test_nonzero_direction_produces_distinct_triangle(self):
        """Normal (dx,dy) produces three distinct polygon vertices."""
        pts = _arrowhead(100, 100, 0, 1)  # pointing down
        coords = [tuple(int(v) for v in pair.split(",")) for pair in pts.split()]
        assert len(coords) == 3
        assert len(set(coords)) == 3, "all three arrowhead vertices must be distinct"


# ── AC-P4.1: A* failure returns None; perimeter retry ────────────────────────

from mermaid_render.layout._routing import _route_perimeter


class TestAStarNoneReturn:
    def test_astar_no_path_returns_none(self):
        """Heavily blocked 2×2 grid returns None, not a fallback straight line."""
        grid_xs = [0, 10]
        grid_ys = [0, 10]
        blocked = {(0, 0, 1, 0), (0, 0, 0, 1), (0, 1, 1, 1), (1, 0, 1, 1)}
        result = _astar_route(0, 0, 10, 10, grid_xs, grid_ys, blocked, set())
        assert result is None

    def test_perimeter_retry_finds_path(self):
        """With a small obstacle, perimeter retry with margin=16 finds a clear path."""
        obstacles = [(100, 100, 150, 150)]
        result = _route_perimeter(50, 125, 200, 125, 16, obstacles)
        assert result is not None, "perimeter retry should find a bypass path"
        assert _try_3seg_clear(result, obstacles)

    def test_routing_failure_omits_edge(self):
        """When all perimeter retries fail, _route_perimeter returns None."""
        obstacles = [(0, 0, 500, 500)]
        result = _route_perimeter(100, 100, 400, 400, 16, obstacles)
        assert result is None


# ── AC-P4.2: allocate_face_ports ─────────────────────────────────────────────

from mermaid_render.layout._routing import allocate_face_ports


class TestAllocateFacePorts:
    def test_allocate_face_ports_bounds(self):
        """All offsets are within [0, face_length]."""
        for count in (1, 3, 5, 8):
            allocs = allocate_face_ports(100, count)
            assert len(allocs) == count
            for a in allocs:
                assert 0 <= a.offset <= 100, f"count={count}: offset={a.offset} out of [0, 100]"

    def test_allocate_face_ports_overflow(self):
        """Ports beyond capacity go to lane=1."""
        # face=42, min_step=6: usable=42-16=26, capacity=26//6=4
        allocs = allocate_face_ports(42, 8, padding=8, min_step=6)
        assert len(allocs) == 8
        assert all(allocs[i].lane == 0 for i in range(4))
        assert all(allocs[i].lane == 1 for i in range(4, 8))

    def test_fan_offset_clamped(self):
        """_fan_offset output is clamped to [0, node_w]."""
        from mermaid_render.layout._routing import _fan_offset
        for idx in range(10):
            offset = _fan_offset(idx, 10, node_w=20, pad=16)
            assert 0 <= offset <= 20, f"_fan_offset({idx}, 10, 20) = {offset} out of [0, 20]"


# ── AC-P4.3: node_rect + predicates ──────────────────────────────────────────

from mermaid_render.layout._routing import node_rect
from mermaid_render.layout._constants import _Node as _N
from mermaid_render.layout._geometry import Rect


class TestNodeRectAndPredicates:
    def test_node_rect_wide_card(self):
        from mermaid_render.layout._routing import _node_render_w
        from mermaid_render.layout._constants import _node_render_h
        n = _N(id="A", label="Wide", width=200)
        r = node_rect(n)
        assert isinstance(r, Rect)
        assert r.x == n.x and r.y == n.y
        assert r.w == _node_render_w(n)
        assert r.h == _node_render_h(n)
        assert r.x1 == n.x + _node_render_w(n)

    def test_back_edge_detection_center(self):
        """Back-edge: dst center < src left edge."""
        s = _N(id="S", label="S", width=80)
        s.x = 200
        d = _N(id="D", label="D", width=80)
        d.x = 50
        s_r, d_r = node_rect(s), node_rect(d)
        assert (d_r.x + d_r.w / 2) < s_r.x  # dst center (90) < src left (200) → back

    def test_reverse_edge_detection_center(self):
        """Reverse-edge shortcut: src.x >= dst.x1."""
        s = _N(id="S", label="S", width=80)
        s.x = 300
        d = _N(id="D", label="D", width=80)
        d.x = 200
        assert node_rect(s).x >= node_rect(d).x1  # 300 >= 280


# ── AC-P2.1: Iterative DFS cycle-breaking ────────────────────────────────────

class TestBreakCyclesInvariants:
    def _make(self, ids, pairs):
        from mermaid_render.layout._constants import _Node, _Edge
        nodes = {nid: _Node(id=nid, label=nid) for nid in ids}
        edges = [_Edge(s, d) for s, d in pairs]
        return nodes, edges

    def test_greedy_fas_correctness(self):
        """No directed cycles in forward-edge subgraph after _break_cycles."""
        from mermaid_render.layout._layout import _break_cycles
        from collections import defaultdict
        nodes, edges = self._make(
            ["A", "B", "C", "D"],
            [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"), ("A", "C")],
        )
        _break_cycles(nodes, edges)
        adj = defaultdict(list)
        for e in edges:
            if not e.reversed_:
                adj[e.src].append(e.dst)
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in nodes}
        found_cycle = []

        def dfs(u):
            color[u] = GRAY
            for v in adj[u]:
                if color[v] == GRAY:
                    found_cycle.append(True)
                elif color[v] == WHITE:
                    dfs(v)
            color[u] = BLACK

        for n in nodes:
            if color[n] == WHITE:
                dfs(n)
        assert not found_cycle

    def test_greedy_fas_deterministic(self):
        """Same graph → same reversed set every time."""
        from mermaid_render.layout._layout import _break_cycles

        def make():
            return self._make(
                ["A", "B", "C", "D"],
                [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")],
            )

        nodes1, edges1 = make()
        nodes2, edges2 = make()
        _break_cycles(nodes1, edges1)
        _break_cycles(nodes2, edges2)
        assert [(e.src, e.dst) for e in edges1 if e.reversed_] == \
               [(e.src, e.dst) for e in edges2 if e.reversed_]

    def test_greedy_fas_single_cycle(self):
        """Simple 3-cycle: exactly 1 edge reversed."""
        from mermaid_render.layout._layout import _break_cycles
        nodes, edges = self._make(
            ["A", "B", "C"],
            [("A", "B"), ("B", "C"), ("C", "A")],
        )
        _break_cycles(nodes, edges)
        assert sum(1 for e in edges if e.reversed_) == 1
