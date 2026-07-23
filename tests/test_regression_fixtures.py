"""Regression baseline tests for 6 flowchart fixtures.

Spec: docs/specs/flowchart-elk-routing-regression-pack/spec.md
Each test class pins one fixture; ACs that aren't yet fully met are marked xfail.
Run with: python -m pytest tests/test_regression_fixtures.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _compile_flowchart
from mermaid_render.layout._geometry import CompiledFlowchart, RoutedEdge
from mermaid_render.layout._strategies import RenderOptions


# ── helpers ───────────────────────────────────────────────────────────────────

def _compile(fixture_name: str, width: int = 800) -> CompiledFlowchart:
    src = (FIXTURES / fixture_name).read_text()
    return _compile_flowchart(src, width_hint=width, options=RenderOptions())


def _node_ids(result: CompiledFlowchart) -> list:
    return list(result.layout.node_layouts.keys())


def _group_ids(result: CompiledFlowchart) -> list:
    return list(result.layout.group_layouts.keys())


def _back_edges_within_canvas(result: CompiledFlowchart) -> bool:
    canvas_right = result.layout.canvas_bounds.x + result.layout.canvas_bounds.w
    for e in result.layout.routed_edges:
        for pt in e.waypoints:
            if pt.x > canvas_right + 1:
                return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: flowchart-arrows-defs
# ─────────────────────────────────────────────────────────────────────────────

class TestArrowsDefs:
    """flowchart-arrows-defs.mmd: solid, thick, dotted arrow styles (AC6, AC16)."""

    def test_compiles_without_error(self):
        result = _compile("flowchart-arrows-defs.mmd")
        assert isinstance(result, CompiledFlowchart)

    def test_has_expected_nodes(self):
        result = _compile("flowchart-arrows-defs.mmd")
        ids = _node_ids(result)
        assert "A" in ids and "B" in ids and "C" in ids and "D" in ids

    def test_has_edges(self):
        result = _compile("flowchart-arrows-defs.mmd")
        assert len(result.layout.routed_edges) > 0

    def test_solid_edge_style(self):
        result = _compile("flowchart-arrows-defs.mmd")
        styles = {e.edge_style for e in result.layout.routed_edges}
        assert "solid" in styles, f"Expected a solid edge, got styles: {styles}"

    def test_thick_edge_style(self):
        """==> arrows must produce style=thick (AC6)."""
        result = _compile("flowchart-arrows-defs.mmd")
        styles = {e.edge_style for e in result.layout.routed_edges}
        assert "thick" in styles, f"Expected a thick edge, got: {styles}"

    def test_dotted_edge_style(self):
        """-.- arrows must produce style=dotted (AC6)."""
        result = _compile("flowchart-arrows-defs.mmd")
        styles = {e.edge_style for e in result.layout.routed_edges}
        assert "dotted" in styles, f"Expected a dotted edge, got: {styles}"

    def test_routed_edge_has_metrics(self):
        """Every RoutedEdge must have non-negative compactness metrics (AC16)."""
        result = _compile("flowchart-arrows-defs.mmd")
        for e in result.layout.routed_edges:
            assert e.route_length >= 0.0
            assert e.bend_count >= 0
            assert e.canvas_area >= 0
            assert e.max_endpoint_distance >= 0.0

    def test_edges_with_waypoints_have_positive_route_length(self):
        """Edges with 2+ waypoints must have route_length > 0 (AC16)."""
        result = _compile("flowchart-arrows-defs.mmd")
        for e in result.layout.routed_edges:
            if len(e.waypoints) >= 2:
                assert e.route_length > 0.0, (
                    f"Edge {e.edge_id} has {len(e.waypoints)} waypoints but route_length=0"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: flowchart-diamond-branch
# ─────────────────────────────────────────────────────────────────────────────

class TestDiamondBranch:
    """flowchart-diamond-branch.mmd: back-edge Retry->Check (AC1, AC8, AC16)."""

    def test_compiles_without_error(self):
        result = _compile("flowchart-diamond-branch.mmd")
        assert isinstance(result, CompiledFlowchart)

    def test_has_expected_nodes(self):
        result = _compile("flowchart-diamond-branch.mmd")
        ids = set(_node_ids(result))
        expected = {"Start", "Check", "Process", "Error", "Retry", "Done", "Notify"}
        assert expected.issubset(ids), f"Missing nodes. Got: {ids}"

    def test_has_back_edge(self):
        """Retry -> Check is a back-edge; must be present in routed edges."""
        result = _compile("flowchart-diamond-branch.mmd")
        edge_srcs = {e.src_node_id for e in result.layout.routed_edges}
        assert "Retry" in edge_srcs, "No edge from Retry node found"

    def test_back_edge_waypoints_within_canvas(self):
        """Back-edge waypoints must lie within canvas bounds (AC8 proxy)."""
        result = _compile("flowchart-diamond-branch.mmd")
        assert _back_edges_within_canvas(result)

    def test_no_routing_failures(self):
        result = _compile("flowchart-diamond-branch.mmd")
        assert len(result.layout.routing_failures) == 0, (
            f"Routing failures: {result.layout.routing_failures}"
        )

    def test_metrics_on_all_edges(self):
        result = _compile("flowchart-diamond-branch.mmd")
        for e in result.layout.routed_edges:
            assert e.route_length >= 0.0
            assert e.canvas_area >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: flowchart-empty-subgraph
# ─────────────────────────────────────────────────────────────────────────────

class TestEmptySubgraph:
    """flowchart-empty-subgraph.mmd: empty group beside non-empty group (AC4, AC13)."""

    def test_compiles_without_error(self):
        result = _compile("flowchart-empty-subgraph.mmd")
        assert isinstance(result, CompiledFlowchart)

    def test_has_at_least_one_group(self):
        result = _compile("flowchart-empty-subgraph.mmd")
        groups = _group_ids(result)
        assert len(groups) >= 1, "Expected at least 1 group (the empty one)"

    def test_all_groups_have_positive_dimensions(self):
        """All group bboxes must have positive width and height (AC13)."""
        result = _compile("flowchart-empty-subgraph.mmd")
        for gid, gl in result.layout.group_layouts.items():
            assert gl.boundary_bounds.w > 0, f"Group {gid!r} has width=0"
            assert gl.boundary_bounds.h > 0, f"Group {gid!r} has height=0"

    def test_empty_group_meets_minimum_dimensions(self):
        """Empty group width >= MIN_EMPTY_GROUP_W (AC13)."""
        from mermaid_render.layout._constants import (
            MIN_EMPTY_GROUP_W, MIN_EMPTY_GROUP_BODY_H, GROUP_PAD_Y_TOP,
        )
        result = _compile("flowchart-empty-subgraph.mmd")
        min_h = GROUP_PAD_Y_TOP + MIN_EMPTY_GROUP_BODY_H
        for gid, gl in result.layout.group_layouts.items():
            if "empty" in gid.lower():
                assert gl.boundary_bounds.w >= MIN_EMPTY_GROUP_W, (
                    f"Empty group {gid!r} width {gl.boundary_bounds.w} < MIN_EMPTY_GROUP_W={MIN_EMPTY_GROUP_W}"
                )
                assert gl.boundary_bounds.h >= min_h, (
                    f"Empty group {gid!r} height {gl.boundary_bounds.h} < min_h={min_h}"
                )

    def test_canvas_is_deterministic(self):
        """Same source compiled twice must produce identical canvas dimensions (AC4)."""
        src = (FIXTURES / "flowchart-empty-subgraph.mmd").read_text()
        opts = RenderOptions()
        r1 = _compile_flowchart(src, width_hint=800, options=opts)
        r2 = _compile_flowchart(src, width_hint=800, options=opts)
        assert r1.layout.canvas_bounds.w == r2.layout.canvas_bounds.w
        assert r1.layout.canvas_bounds.h == r2.layout.canvas_bounds.h


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: flowchart-groups-complex
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupsComplex:
    """flowchart-groups-complex.mmd: cross-group edges Frontend/Backend/DataLayer (AC3, AC14, AC16)."""

    def test_compiles_without_error(self):
        result = _compile("flowchart-groups-complex.mmd")
        assert isinstance(result, CompiledFlowchart)

    def test_has_three_groups(self):
        result = _compile("flowchart-groups-complex.mmd")
        groups = _group_ids(result)
        assert len(groups) >= 3, f"Expected 3 groups, got {groups}"

    def test_cross_group_edges_present(self):
        """Edges between groups (UI->API, Cache-.->DB etc.) must all be routed."""
        result = _compile("flowchart-groups-complex.mmd")
        edge_srcs = {e.src_node_id for e in result.layout.routed_edges}
        assert "UI" in edge_srcs, "No edge from UI"
        assert "API" in edge_srcs, "No edge from API"

    def test_all_nodes_are_laid_out(self):
        result = _compile("flowchart-groups-complex.mmd")
        ids = set(_node_ids(result))
        for expected in ("UI", "Cache", "API", "Auth", "Worker", "DB", "Queue"):
            assert expected in ids, f"Node {expected!r} missing from layout"

    def test_no_routing_failures(self):
        result = _compile("flowchart-groups-complex.mmd")
        assert len(result.layout.routing_failures) == 0, (
            f"Routing failures: {result.layout.routing_failures}"
        )

    def test_metrics_on_all_edges(self):
        result = _compile("flowchart-groups-complex.mmd")
        for e in result.layout.routed_edges:
            assert e.route_length >= 0.0
            assert e.canvas_area >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: flowchart-inner-direction
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerDirection:
    """flowchart-inner-direction.mmd: TB outer with LR pipeline subgraph (AC2, AC12)."""

    def test_compiles_without_error(self):
        result = _compile("flowchart-inner-direction.mmd")
        assert isinstance(result, CompiledFlowchart)

    def test_has_pipeline_group(self):
        result = _compile("flowchart-inner-direction.mmd")
        groups = _group_ids(result)
        assert len(groups) >= 1, "Expected pipeline group"

    def test_inner_nodes_exist(self):
        result = _compile("flowchart-inner-direction.mmd")
        ids = set(_node_ids(result))
        for n in ("ingest", "transform", "load", "source", "sink"):
            assert n in ids, f"Inner node {n!r} missing"

    def test_pipeline_nodes_are_horizontally_spread(self):
        """ingest, transform, load must have distinct x-coords (LR inner layout, AC2/AC12)."""
        result = _compile("flowchart-inner-direction.mmd")
        nls = result.layout.node_layouts
        if "ingest" in nls and "transform" in nls and "load" in nls:
            x_ingest = nls["ingest"].outer_bounds.x
            x_transform = nls["transform"].outer_bounds.x
            x_load = nls["load"].outer_bounds.x
            assert not (x_ingest == x_transform == x_load), (
                "Pipeline nodes have identical x-coords — inner LR direction not applied"
            )

    def test_source_is_above_or_near_pipeline(self):
        """source node should appear before (above) the pipeline in TB layout."""
        result = _compile("flowchart-inner-direction.mmd")
        nls = result.layout.node_layouts
        gls = result.layout.group_layouts
        if "source" in nls and gls:
            src_y = nls["source"].outer_bounds.y
            first_group_top = min(gl.boundary_bounds.y for gl in gls.values())
            assert src_y <= first_group_top + 250, (
                f"source y={src_y} far below group top {first_group_top}"
            )

    def test_metrics_on_all_edges(self):
        result = _compile("flowchart-inner-direction.mmd")
        for e in result.layout.routed_edges:
            assert e.route_length >= 0.0
            assert e.canvas_area >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: flowchart-parallel-links
# ─────────────────────────────────────────────────────────────────────────────

class TestParallelLinks:
    """flowchart-parallel-links.mmd: A --> B & C & D fan-out/fan-in (AC5, AC9, AC10)."""

    def test_compiles_without_error(self):
        result = _compile("flowchart-parallel-links.mmd")
        assert isinstance(result, CompiledFlowchart)

    def test_has_expected_nodes(self):
        result = _compile("flowchart-parallel-links.mmd")
        ids = set(_node_ids(result))
        for n in ("A", "B", "C", "D", "E"):
            assert n in ids, f"Node {n!r} missing"

    def test_parallel_fan_out_edges_present(self):
        """A must have edges to B, C, and D."""
        result = _compile("flowchart-parallel-links.mmd")
        a_edges = [e for e in result.layout.routed_edges if e.src_node_id == "A"]
        dsts = {e.dst_node_id for e in a_edges}
        assert {"B", "C", "D"}.issubset(dsts), f"A fan-out edges missing. Dst set: {dsts}"

    def test_parallel_fan_in_edges_present(self):
        """E must have edges from B, C, and D."""
        result = _compile("flowchart-parallel-links.mmd")
        e_edges = [e for e in result.layout.routed_edges if e.dst_node_id == "E"]
        srcs = {e.src_node_id for e in e_edges}
        assert {"B", "C", "D"}.issubset(srcs), f"E fan-in edges missing. Src set: {srcs}"

    def test_fan_out_waypoints_are_distinct(self):
        """Parallel edges from A to B/C/D must not share identical waypoints (AC5/AC9)."""
        result = _compile("flowchart-parallel-links.mmd")
        a_edges = [e for e in result.layout.routed_edges if e.src_node_id == "A"]
        if len(a_edges) >= 2:
            wp_sets = [tuple(e.waypoints) for e in a_edges]
            assert len(set(wp_sets)) > 1, (
                "All parallel fan-out edges share identical waypoints — port offsets not applied"
            )

    def test_no_routing_failures(self):
        result = _compile("flowchart-parallel-links.mmd")
        assert len(result.layout.routing_failures) == 0, (
            f"Routing failures: {result.layout.routing_failures}"
        )

    def test_metrics_on_all_edges(self):
        result = _compile("flowchart-parallel-links.mmd")
        for e in result.layout.routed_edges:
            assert e.route_length >= 0.0
            assert e.canvas_area >= 0
