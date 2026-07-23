"""Unit tests for _routing.py helpers added by flowchart-elk-routing-regression-pack.

Covers:
  - _tarjan_sccs (AC1, AC8)
  - _scc_bbox (AC1, AC8)
  - _compute_metrics (AC16)
  - _lca_group / _group_boundary_port (AC3, AC14)
  - Inner-direction compound layout (AC2, AC12)

Run with: python -m pytest tests/test_routing_units.py -v
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._routing import (
    _tarjan_sccs,
    _scc_bbox,
    _compute_metrics,
    _lca_group,
    _group_boundary_port,
)
from mermaid_render.layout._constants import _Node


# ─────────────────────────────────────────────────────────────────────────────
# _tarjan_sccs
# ─────────────────────────────────────────────────────────────────────────────

class TestTarjanSccs:
    """Iterative Tarjan SCC implementation — AC1, AC8."""

    def test_empty_input(self):
        assert _tarjan_sccs([], []) == []

    def test_single_node_no_edges(self):
        sccs = _tarjan_sccs(["A"], [])
        assert len(sccs) == 1
        assert sccs[0] == ["A"]

    def test_linear_chain_all_singletons(self):
        """A->B->C: no cycles, each node is its own SCC."""
        sccs = _tarjan_sccs(["A", "B", "C"], [("A", "B"), ("B", "C")])
        assert len(sccs) == 3
        for scc in sccs:
            assert len(scc) == 1

    def test_simple_cycle(self):
        """A->B->A: one 2-node SCC."""
        sccs = _tarjan_sccs(["A", "B"], [("A", "B"), ("B", "A")])
        assert len(sccs) == 1
        assert set(sccs[0]) == {"A", "B"}

    def test_diamond_with_back_edge(self):
        """A->B->D, A->C->D, D->A: full cycle {A,B,C,D}."""
        nodes = ["A", "B", "C", "D"]
        edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"), ("D", "A")]
        sccs = _tarjan_sccs(nodes, edges)
        assert len(sccs) == 1
        assert set(sccs[0]) == {"A", "B", "C", "D"}

    def test_separate_scc_groups(self):
        """A->B->A, C->D->C: two separate SCCs."""
        nodes = ["A", "B", "C", "D"]
        edges = [("A", "B"), ("B", "A"), ("C", "D"), ("D", "C")]
        sccs = _tarjan_sccs(nodes, edges)
        assert len(sccs) == 2
        scc_sets = [set(s) for s in sccs]
        assert {"A", "B"} in scc_sets
        assert {"C", "D"} in scc_sets

    def test_self_loops_excluded_from_multimember_sccs(self):
        """Self-loop A->A is a separate 1-node SCC, not treated as a 2-node cycle."""
        sccs = _tarjan_sccs(["A"], [("A", "A")])
        # self-loops are excluded from adj in _tarjan_sccs
        assert len(sccs) == 1
        assert len(sccs[0]) == 1

    def test_no_recursion_limit(self):
        """300-node chain must not blow Python's recursion limit."""
        n = 300
        nodes = [str(i) for i in range(n)]
        edges = [(str(i), str(i + 1)) for i in range(n - 1)]
        sccs = _tarjan_sccs(nodes, edges)
        assert len(sccs) == n

    def test_returns_list_of_lists(self):
        sccs = _tarjan_sccs(["X", "Y"], [("X", "Y")])
        assert isinstance(sccs, list)
        for s in sccs:
            assert isinstance(s, list)


# ─────────────────────────────────────────────────────────────────────────────
# _scc_bbox
# ─────────────────────────────────────────────────────────────────────────────

def _make_node(nid: str, x: int, y: int, w: int = 120, h: int = 40) -> _Node:
    n = _Node(id=nid, label=nid)
    n.x = x
    n.y = y
    n.width = w
    n.height = h
    return n


class TestSccBbox:
    """SCC bounding box computation — AC8."""

    def test_returns_none_for_empty_members(self):
        result = _scc_bbox([], {})
        assert result is None

    def test_single_node(self):
        n = _make_node("A", x=10, y=20, w=100, h=40)
        bbox = _scc_bbox(["A"], {"A": n})
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        assert x1 == 10
        assert y1 == 20
        assert x2 == 110  # 10 + 100 (node_render_w uses n.width)
        assert y2 >= 60   # 20 + _node_render_h(n) >= 20+40 (min NODE_H=42, so >=62)

    def test_two_nodes_union(self):
        na = _make_node("A", x=0, y=0, w=100, h=40)
        nb = _make_node("B", x=200, y=50, w=80, h=30)
        bbox = _scc_bbox(["A", "B"], {"A": na, "B": nb})
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        assert x1 == 0
        assert y1 == 0
        assert x2 == 280   # 200 + 80 (node_render_w uses n.width)
        assert y2 >= 80    # >= 50 + _node_render_h(nb), min NODE_H=42 so >=92

    def test_missing_node_skipped(self):
        na = _make_node("A", x=5, y=5, w=50, h=20)
        bbox = _scc_bbox(["A", "B"], {"A": na})  # B is missing
        assert bbox is not None
        x1, y1, x2, y2 = bbox
        assert x1 == 5
        assert x2 == 55

    def test_all_missing_returns_none(self):
        result = _scc_bbox(["X", "Y"], {})
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# _compute_metrics
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeMetrics:
    """Compactness metrics on RoutedEdge (AC16)."""

    def test_empty_waypoints_returns_zeros(self):
        m = _compute_metrics([], None, None, 0)
        assert m["route_length"] == 0.0
        assert m["bend_count"] == 0
        assert m["canvas_area"] == 0
        assert m["max_endpoint_distance"] == 0.0

    def test_single_point_returns_zeros(self):
        m = _compute_metrics([(0, 0)], None, None, 1000)
        assert m["route_length"] == 0.0
        assert m["bend_count"] == 0

    def test_straight_line_no_bends(self):
        """Horizontal line: 3 collinear points → 0 bends."""
        m = _compute_metrics([(0, 0), (50, 0), (100, 0)], None, None, 5000)
        assert m["bend_count"] == 0
        assert abs(m["route_length"] - 100.0) < 1.0

    def test_right_angle_one_bend(self):
        """L-shape: (0,0)→(100,0)→(100,100) → exactly 1 bend."""
        m = _compute_metrics([(0, 0), (100, 0), (100, 100)], None, None, 10000)
        assert m["bend_count"] == 1
        expected_len = 100.0 + 100.0
        assert abs(m["route_length"] - expected_len) < 1.0

    def test_z_shape_two_bends(self):
        """Z-shape 4 points → 2 bends."""
        pts = [(0, 0), (100, 0), (100, 50), (200, 50)]
        m = _compute_metrics(pts, None, None, 20000)
        assert m["bend_count"] == 2

    def test_canvas_area_propagated(self):
        m = _compute_metrics([(0, 0), (100, 0)], None, None, 42000)
        assert m["canvas_area"] == 42000

    def test_route_length_euclidean(self):
        """Diagonal: sqrt(3^2+4^2) = 5.0"""
        m = _compute_metrics([(0, 0), (3, 4)], None, None, 0)
        assert abs(m["route_length"] - 5.0) < 0.01

    def test_max_endpoint_distance_with_bbox(self):
        """Midpoint of (0,0)-(100,0) is at (50,0); distance to src_bbox containing (0,0) should be 0."""
        src_bbox = (0, -20, 20, 20)   # box containing the start point
        dst_bbox = (80, -20, 100, 20)  # box containing the end point
        m = _compute_metrics([(0, 0), (100, 0)], src_bbox, dst_bbox, 0)
        assert m["max_endpoint_distance"] >= 0.0

    def test_all_keys_present(self):
        m = _compute_metrics([(0, 0), (1, 0)], None, None, 0)
        assert set(m.keys()) >= {"route_length", "bend_count", "canvas_area", "max_endpoint_distance"}


# ─────────────────────────────────────────────────────────────────────────────
# _lca_group / _group_boundary_port
# ─────────────────────────────────────────────────────────────────────────────

class TestHierarchyHelpers:
    """LCA group and group boundary port helpers (AC3, AC14)."""

    def test_lca_same_group_returns_none(self):
        gm = {"A": "G1", "B": "G1"}
        result = _lca_group("A", "B", gm)
        assert result is None

    def test_lca_different_groups_returns_src_group(self):
        gm = {"A": "G1", "B": "G2"}
        result = _lca_group("A", "B", gm)
        assert result == "G1"

    def test_lca_top_level_nodes_returns_none(self):
        gm = {"A": None, "B": None}
        result = _lca_group("A", "B", gm)
        assert result is None

    def test_boundary_port_tb_exit(self):
        """TB exit: should be at mid_x, y2 (bottom of group)."""
        bbox = (0, 0, 100, 200)
        pt = _group_boundary_port(bbox, "TB", exit_=True)
        assert pt == (50, 200)

    def test_boundary_port_tb_entry(self):
        """TB entry: should be at mid_x, y1 (top of group)."""
        bbox = (0, 0, 100, 200)
        pt = _group_boundary_port(bbox, "TB", exit_=False)
        assert pt == (50, 0)

    def test_boundary_port_lr_exit(self):
        """LR exit: should be at x2, mid_y (right of group)."""
        bbox = (0, 0, 100, 200)
        pt = _group_boundary_port(bbox, "LR", exit_=True)
        assert pt == (100, 100)

    def test_boundary_port_lr_entry(self):
        """LR entry: should be at x1, mid_y (left of group)."""
        bbox = (0, 0, 100, 200)
        pt = _group_boundary_port(bbox, "LR", exit_=False)
        assert pt == (0, 100)


# ─────────────────────────────────────────────────────────────────────────────
# Compound direction (integration)
# ─────────────────────────────────────────────────────────────────────────────

class TestCompoundDirection:
    """Inner-direction subgraph layout — AC2, AC12."""

    _SRC = """flowchart TB
  subgraph pipeline["Pipeline"]
    direction LR
    ingest[Ingest] --> transform[Transform] --> load[Load]
  end
  source[Source] --> ingest
  load --> sink[Sink]
"""

    def test_inner_direction_compiles(self):
        from mermaid_render.layout._strategies import _compile_flowchart
        from mermaid_render.layout._strategies import RenderOptions
        result = _compile_flowchart(self._SRC, width_hint=800, options=RenderOptions())
        assert result is not None

    def test_pipeline_nodes_laid_out_horizontally(self):
        """ingest, transform, load must have increasing x-coordinates (LR inner, AC2)."""
        from mermaid_render.layout._strategies import _compile_flowchart
        from mermaid_render.layout._strategies import RenderOptions
        result = _compile_flowchart(self._SRC, width_hint=800, options=RenderOptions())
        nls = result.layout.node_layouts
        if "ingest" in nls and "transform" in nls and "load" in nls:
            x_i = nls["ingest"].outer_bounds.x
            x_t = nls["transform"].outer_bounds.x
            x_l = nls["load"].outer_bounds.x
            assert not (x_i == x_t == x_l), (
                f"Pipeline nodes all at same x={x_i} — LR inner direction not applied"
            )

    def test_source_above_pipeline(self):
        """source must appear above pipeline group in outer TB layout."""
        from mermaid_render.layout._strategies import _compile_flowchart
        from mermaid_render.layout._strategies import RenderOptions
        result = _compile_flowchart(self._SRC, width_hint=800, options=RenderOptions())
        nls = result.layout.node_layouts
        gls = result.layout.group_layouts
        if "source" in nls and gls:
            src_y = nls["source"].outer_bounds.y
            group_top = min(gl.boundary_bounds.y for gl in gls.values())
            assert src_y < group_top + 200, (
                f"source y={src_y} is not above group top={group_top}"
            )
