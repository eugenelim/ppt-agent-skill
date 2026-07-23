"""Tests for state-diagram-local-cycle-routing — SCC routing helpers and
proximity constraints.

Tests:
  - _tarjan_sccs(): SCC detection on simple cycles
  - _scc_bbox(): bounding box computation over SCC member nodes
  - _route_local_cycle(): proximity constraint (no waypoint > 2*NODE_W from pair bbox)
  - Boundary-containment check: lane stays within scope + small stagger
  - Title-avoidance check: TB routing goes RIGHT, not through top title strip
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._routing import (
    _tarjan_sccs,
    _scc_bbox,
    _route_local_cycle,
)
from mermaid_render.layout._geometry import Rect
from mermaid_render.layout._constants import NODE_W, NODE_H


# ── _tarjan_sccs ──────────────────────────────────────────────────────────────

class TestTarjanSccs:
    """_tarjan_sccs() identifies strongly-connected components."""

    def test_empty_graph(self):
        sccs = _tarjan_sccs([], [])
        assert sccs == []

    def test_single_node_no_loop(self):
        sccs = _tarjan_sccs(["A"], [])
        assert len(sccs) == 1
        assert sccs[0] == ["A"]

    def test_simple_cycle(self):
        """A → B → A forms one SCC of size 2."""
        sccs = _tarjan_sccs(["A", "B"], [("A", "B"), ("B", "A")])
        big = [s for s in sccs if len(s) > 1]
        assert len(big) == 1
        assert set(big[0]) == {"A", "B"}

    def test_two_separate_nodes(self):
        """A → B (no cycle): two SCCs of size 1."""
        sccs = _tarjan_sccs(["A", "B"], [("A", "B")])
        assert len(sccs) == 2
        # Each SCC has exactly one member
        assert all(len(s) == 1 for s in sccs)

    def test_chain_no_cycle(self):
        """A → B → C: three single-node SCCs."""
        sccs = _tarjan_sccs(["A", "B", "C"], [("A", "B"), ("B", "C")])
        assert len(sccs) == 3
        assert all(len(s) == 1 for s in sccs)

    def test_three_node_cycle(self):
        """A → B → C → A forms one SCC of size 3."""
        sccs = _tarjan_sccs(
            ["A", "B", "C"],
            [("A", "B"), ("B", "C"), ("C", "A")],
        )
        big = [s for s in sccs if len(s) > 1]
        assert len(big) == 1
        assert set(big[0]) == {"A", "B", "C"}

    def test_two_independent_cycles(self):
        """Two disjoint cycles: {A,B} and {C,D}."""
        sccs = _tarjan_sccs(
            ["A", "B", "C", "D"],
            [("A", "B"), ("B", "A"), ("C", "D"), ("D", "C")],
        )
        big = [s for s in sccs if len(s) > 1]
        assert len(big) == 2
        members = {frozenset(s) for s in big}
        assert frozenset({"A", "B"}) in members
        assert frozenset({"C", "D"}) in members

    def test_self_loop(self):
        """A → A: single SCC containing just A."""
        sccs = _tarjan_sccs(["A"], [("A", "A")])
        assert len(sccs) == 1
        assert sccs[0] == ["A"]

    def test_ignores_unknown_nodes_in_edges(self):
        """Edges referencing unknown nodes don't crash."""
        sccs = _tarjan_sccs(["A"], [("A", "Z"), ("Z", "A")])
        # Z is not in nodes list; edge filtered out; A is its own SCC
        assert len(sccs) == 1
        assert sccs[0] == ["A"]


# ── _scc_bbox ─────────────────────────────────────────────────────────────────

from mermaid_render.layout._constants import _Node as _RealNode


def _make_node(x: int, y: int, w: int = NODE_W, h: int = NODE_H) -> "_RealNode":
    """Create a real _Node for bbox testing."""
    n = _RealNode(id="test", label="", shape="rect", width=w, height=h)
    n.x = x
    n.y = y
    return n


def _make_dummy(x: int = 0, y: int = 0) -> "_RealNode":
    """Create a dummy _Node."""
    n = _RealNode(id="dummy", label="", is_dummy=True)
    n.x = x
    n.y = y
    return n


class TestSccBbox:
    """_scc_bbox() returns the (x1, y1, x2, y2) bounding box of real SCC member nodes."""

    def test_single_node(self):
        n = _make_node(10, 20)
        bbox = _scc_bbox(["N0"], {"N0": n})
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        assert x1 == 10
        assert y1 == 20
        assert x2 == 10 + NODE_W

    def test_two_nodes_side_by_side(self):
        n0 = _make_node(0, 0)
        n1 = _make_node(NODE_W + 20, 0)
        bbox = _scc_bbox(["N0", "N1"], {"N0": n0, "N1": n1})
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        assert x1 == 0
        assert y1 == 0
        assert x2 == pytest.approx(2 * NODE_W + 20, abs=2)

    def test_skips_dummy_nodes(self):
        real = _make_node(10, 10)
        dummy = _make_dummy(999, 999)
        bbox = _scc_bbox(["real", "dummy"], {"real": real, "dummy": dummy})
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        assert x1 == 10
        assert y1 == 10

    def test_skips_missing_nodes(self):
        n = _make_node(5, 5)
        bbox = _scc_bbox(["exists", "missing"], {"exists": n})
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        assert x1 == 5

    def test_empty_scc(self):
        bbox = _scc_bbox([], {})
        assert bbox is None

    def test_all_dummies(self):
        d = _make_dummy()
        bbox = _scc_bbox(["d"], {"d": d})
        assert bbox is None


# ── _route_local_cycle ────────────────────────────────────────────────────────

class TestRouteLocalCycle:
    """_route_local_cycle() produces waypoints satisfying the proximity constraint."""

    # A pair of nodes 200px wide, 50px tall at positions (0,0) and (0,100)
    SRC = Rect(x=0.0, y=0.0, w=float(NODE_W), h=float(NODE_H))
    DST = Rect(x=0.0, y=100.0, w=float(NODE_W), h=float(NODE_H))
    # SCC / scope bbox encompassing both
    SCOPE = Rect(x=0.0, y=0.0, w=float(NODE_W), h=150.0)

    def _pair_right(self) -> float:
        return max(self.SRC.x + self.SRC.w, self.DST.x + self.DST.w)

    def _pair_bottom(self) -> float:
        return max(self.SRC.y + self.SRC.h, self.DST.y + self.DST.h)

    def test_tb_returns_four_waypoints(self):
        wps = _route_local_cycle(self.SRC, self.DST, self.SCOPE, 0, direction="TB")
        assert len(wps) == 4

    def test_lr_returns_four_waypoints(self):
        wps = _route_local_cycle(self.SRC, self.DST, self.SCOPE, 0, direction="LR")
        assert len(wps) == 4

    def test_tb_lane_x_right_of_scope(self):
        """TB: lane_x must be >= scope_bbox.right."""
        wps = _route_local_cycle(self.SRC, self.DST, self.SCOPE, 0, direction="TB")
        lane_x = wps[1][0]  # second waypoint has lane_x
        assert lane_x >= self.SCOPE.x + self.SCOPE.w

    def test_lr_lane_y_below_scope(self):
        """LR: lane_y must be >= scope_bbox.bottom."""
        wps = _route_local_cycle(self.SRC, self.DST, self.SCOPE, 0, direction="LR")
        lane_y = wps[1][1]  # second waypoint has lane_y
        assert lane_y >= self.SCOPE.y + self.SCOPE.h

    def test_tb_proximity_constraint(self):
        """TB: lane_x <= pair_right + 2*NODE_W (AC5/AC6)."""
        for be_lane in range(3):
            wps = _route_local_cycle(self.SRC, self.DST, self.SCOPE, be_lane, direction="TB")
            lane_x = wps[1][0]
            pair_right = self._pair_right()
            assert lane_x <= pair_right + 2 * NODE_W, (
                f"lane_x={lane_x} exceeds pair_right ({pair_right}) + 2*NODE_W "
                f"for be_lane={be_lane}"
            )

    def test_lr_proximity_constraint(self):
        """LR: lane_y <= pair_bottom + 2*NODE_W (AC5/AC6 — constraint is 2*NODE_W in any axis)."""
        for be_lane in range(3):
            wps = _route_local_cycle(self.SRC, self.DST, self.SCOPE, be_lane, direction="LR")
            lane_y = wps[1][1]
            pair_bottom = self._pair_bottom()
            assert lane_y <= pair_bottom + 2 * NODE_W, (
                f"lane_y={lane_y} exceeds pair_bottom ({pair_bottom}) + 2*NODE_W "
                f"for be_lane={be_lane}"
            )

    def test_tb_stagger_increases_with_lane(self):
        """Each successive back-edge lane is further right."""
        wps0 = _route_local_cycle(self.SRC, self.DST, self.SCOPE, 0, direction="TB")
        wps1 = _route_local_cycle(self.SRC, self.DST, self.SCOPE, 1, direction="TB")
        assert wps1[1][0] > wps0[1][0]

    def test_lr_stagger_increases_with_lane(self):
        wps0 = _route_local_cycle(self.SRC, self.DST, self.SCOPE, 0, direction="LR")
        wps1 = _route_local_cycle(self.SRC, self.DST, self.SCOPE, 1, direction="LR")
        assert wps1[1][1] > wps0[1][1]

    def test_title_avoidance_tb(self):
        """TB back-edge lane goes RIGHT of source, not through the title strip
        (top region).  The route must not include any waypoint with y < scope.y
        (title strip is at the top of the scope box).
        """
        # scope starts at y=10 (simulating a title strip at the top)
        scope = Rect(x=0.0, y=10.0, w=float(NODE_W), h=200.0)
        src = Rect(x=0.0, y=50.0, w=float(NODE_W), h=float(NODE_H))
        dst = Rect(x=0.0, y=150.0, w=float(NODE_W), h=float(NODE_H))
        wps = _route_local_cycle(src, dst, scope, 0, direction="TB")
        # All waypoints must be at x >= scope.x + scope.w (lane is to the right)
        lane_x = wps[1][0]
        assert lane_x >= scope.x + scope.w, (
            f"TB back-edge lane_x={lane_x} should be >= scope.right={scope.x+scope.w}"
        )
        # The route does NOT pass through the top title strip (y < scope.y + some_height)
        # by virtue of going RIGHT rather than UP — all y values are between src and dst
        min_y = min(wp[1] for wp in wps)
        assert min_y >= min(src.y, dst.y) - 1, (
            f"Route passes above src/dst min_y={min_y}"
        )

    def test_boundary_containment_tb(self):
        """TB: when scope_bbox is tight around the node pair, lane stays near the scope."""
        # Tight scope: exactly the pair bbox (no extra padding)
        src = Rect(x=100.0, y=50.0, w=float(NODE_W), h=float(NODE_H))
        dst = Rect(x=100.0, y=150.0, w=float(NODE_W), h=float(NODE_H))
        scope = Rect(
            x=100.0, y=50.0,
            w=float(NODE_W), h=150.0 + float(NODE_H)
        )
        wps = _route_local_cycle(src, dst, scope, 0, direction="TB")
        lane_x = wps[1][0]
        scope_right = scope.x + scope.w
        # Lane must be just outside the scope right boundary
        assert lane_x >= scope_right
        assert lane_x <= scope_right + 2 * NODE_W, (
            f"lane_x={lane_x} too far from scope_right={scope_right}"
        )
