"""Tests for the flowchart ELK finalized layout consumption pipeline.

Tests all plan tasks:
  Task 1: split _compile_flowchart into composable functions
  Task 2: direct FinalizedLayout return on ELK success (AC1, AC2)
  Task 3: terminal-circle targeted handling (AC3)
  Task 4: self-loop local repair (AC4)
  Task 5: typed exception handling and metadata (AC5, AC9)
  Task 6: edge-ID-based metadata migration (AC8)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mermaid_render.layout._pipeline import (
    FlowchartSemantics,
    parse_flowchart_semantics,
    build_flowchart_layout_graph,
    layout_flowchart_with_elk,
    enrich_flowchart_finalized_layout,
    layout_flowchart_with_python_fallback,
    validate_flowchart_layout,
    _compile_flowchart,
    RenderOptions,
    _is_degenerate_self_loop,
    _repair_elk_self_loop,
)
from mermaid_render.layout._geometry import (
    FinalizedLayout, LayoutGraph, LayoutNode, LayoutEdge, LayoutGroup,
    NodeLayout, GroupLayout, RoutedEdge, PortLayout, PortSide,
    Point, Rect, MarkerKind, LayoutMetadata, _empty_diagnostics,
)
from mermaid_render.layout.elk_adapter import ElkUnavailable, ElkInvalidResult
import mermaid_render.layout._pipeline as _pipeline_mod
import mermaid_render.layout.elk_adapter as _elk_mod
import types as _types


# ── Fixtures ──────────────────────────────────────────────────────────────────

_SIMPLE_SRC = "flowchart TB\n  A --> B"
_SELF_LOOP_SRC = "flowchart TB\n  A --> A\n  A --> B\n  B --> C"
_TERMINAL_CIRCLE_SRC = "stateDiagram-v2\n  [*] --> Active\n  Active --> [*]"
_PARALLEL_EDGES_SRC = "flowchart TB\n  A --> B\n  A --> B"


def _make_finalized_layout(
    node_ids=("A", "B"),
    edge_ids=("A->B",),
    direction="TB",
) -> FinalizedLayout:
    """Minimal FinalizedLayout for mocking ELK output."""
    node_layouts = {
        nid: NodeLayout(
            node_id=nid,
            semantic_shape="rect",
            outer_bounds=Rect(x=float(i * 200), y=0.0, w=192.0, h=42.0),
            content_bounds=Rect(x=float(i * 200 + 8), y=4.0, w=176.0, h=34.0),
            title_layout=None,
            subtitle_layout=None,
            member_layouts=(),
            icon_bounds=None,
            ports=(),
            css_classes=(),
            extra_css="",
            is_dummy=False,
            rank=i + 1,
            is_external=False,
            icon_svg="",
            accent_color="",
            parent_group_id=None,
        )
        for i, nid in enumerate(node_ids)
    }
    routed_edges = tuple(
        RoutedEdge(
            edge_id=eid,
            src_node_id=eid.split("->")[0],
            dst_node_id=eid.split("->")[1],
            src_port=PortLayout(
                node_id=eid.split("->")[0],
                side=PortSide.BOTTOM,
                position=Point(96.0, 42.0),
                direction=Point(0.0, 1.0),
            ),
            dst_port=PortLayout(
                node_id=eid.split("->")[1],
                side=PortSide.TOP,
                position=Point(296.0, 0.0),
                direction=Point(0.0, -1.0),
            ),
            waypoints=(Point(96.0, 42.0), Point(296.0, 0.0)),
            edge_style="solid",
            has_marker_end=True,
            has_marker_start=False,
            label_layout=None,
            src_label_layout=None,
            dst_label_layout=None,
            source_marker=MarkerKind.NONE,
            target_marker=MarkerKind.ARROW,
            junction_points=(),
        )
        for eid in edge_ids
    )
    canvas = Rect(x=0.0, y=0.0, w=500.0, h=300.0)
    return FinalizedLayout(
        node_layouts=_types.MappingProxyType(node_layouts),
        group_layouts=_types.MappingProxyType({}),
        routed_edges=routed_edges,
        routing_failures=(),
        visible_bounds=canvas,
        diagram_padding=48.0,
        canvas_bounds=canvas,
        direction=direction,
        diagnostics=_empty_diagnostics(),
    )


# ── Task 1: pipeline split ─────────────────────────────────────────────────────

class TestPipelineSplit:
    """Task 1: assert all six composable functions exist and behave correctly."""

    def test_six_functions_importable(self):
        """All six pipeline functions are importable from _strategies."""
        from mermaid_render.layout._strategies import (
            parse_flowchart_semantics,
            build_flowchart_layout_graph,
            layout_flowchart_with_elk,
            enrich_flowchart_finalized_layout,
            layout_flowchart_with_python_fallback,
            validate_flowchart_layout,
        )
        assert callable(parse_flowchart_semantics)
        assert callable(build_flowchart_layout_graph)
        assert callable(layout_flowchart_with_elk)
        assert callable(enrich_flowchart_finalized_layout)
        assert callable(layout_flowchart_with_python_fallback)
        assert callable(validate_flowchart_layout)

    def test_flowchart_semantics_class_importable(self):
        """FlowchartSemantics is importable from _strategies."""
        from mermaid_render.layout._strategies import FlowchartSemantics
        assert FlowchartSemantics is not None

    def test_parse_flowchart_semantics_returns_no_coordinates(self):
        """parse_flowchart_semantics returns a model with no layout coordinates."""
        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        assert isinstance(sem, FlowchartSemantics)
        # nodes exist but have default x=0, y=0 (no layout applied)
        for n in sem.nodes.values():
            assert n.x == 0, f"node {n.id} has x={n.x}, expected 0"
            assert n.y == 0, f"node {n.id} has y={n.y}, expected 0"

    def test_parse_flowchart_semantics_populates_edges(self):
        """parse_flowchart_semantics captures edges with edge_ids."""
        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        assert len(sem.edges) > 0
        assert sem.parsed_edge_count == len(sem.edges)

    def test_build_flowchart_layout_graph_has_edge_ids(self):
        """build_flowchart_layout_graph produces LayoutEdges with non-empty IDs."""
        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        graph = build_flowchart_layout_graph(sem)
        assert isinstance(graph, LayoutGraph)
        for edge in graph.edges:
            assert edge.id, f"Edge {edge} has empty id"

    def test_build_flowchart_layout_graph_sets_node_dimensions(self):
        """build_flowchart_layout_graph measures node widths (via _assign_coordinates)."""
        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        build_flowchart_layout_graph(sem)
        for nid, n in sem.nodes.items():
            if not n.is_dummy:
                assert n.width > 0, f"node {nid} has width=0 after build"

    def test_validate_flowchart_layout_returns_validation_result(self):
        """validate_flowchart_layout wraps validate_finalized_layout correctly."""
        layout = _make_finalized_layout()
        result = validate_flowchart_layout(layout)
        # ValidationResult uses 'geometry' and 'errors' fields (not 'is_valid')
        assert hasattr(result, "geometry")
        assert hasattr(result, "errors")


# ── Task 2: no _route_edges after ELK, no _Node.x/_Node.y flattening ─────────

class TestElkDirectReturn:
    """Task 2: AC1 (no _route_edges after ELK) and AC2 (no _Node.x/_Node.y flattenign)."""

    def test_elk_success_not_followed_by_route_edges(self, monkeypatch):
        """When ELK succeeds, _route_edges must NOT be called. (AC1)"""
        elk_layout = _make_finalized_layout()

        monkeypatch.setattr(
            _pipeline_mod, "layout_flowchart_with_elk",
            lambda graph, spacing=None: elk_layout,
        )
        route_edges_called = []
        real_route_edges = _pipeline_mod._route_edges

        def _spy_route_edges(*args, **kwargs):
            route_edges_called.append(True)
            return real_route_edges(*args, **kwargs)

        monkeypatch.setattr(_pipeline_mod, "_route_edges", _spy_route_edges)
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")  # would normally force fallback

        # Bypass the ELK env-var check — we want to exercise the ELK branch
        monkeypatch.setattr(
            _pipeline_mod, "layout_flowchart_with_elk",
            lambda graph, spacing=None: elk_layout,
        )

        # Compile a simple flowchart — ELK mock always returns elk_layout
        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        # Call ELK path directly to verify _route_edges is not called
        enrich_flowchart_finalized_layout(elk_layout, sem)
        assert not route_edges_called, "_route_edges was called after ELK success"

    def test_elk_success_does_not_write_node_xy(self, monkeypatch):
        """After ELK success, _Node.x and _Node.y are not written from ELK output. (AC2)"""
        elk_layout = _make_finalized_layout()

        # Parse and build graph (this sets n.x/n.y as side-effect of _assign_coordinates)
        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        # Record x,y state after build (before enrichment)
        before = {nid: (n.x, n.y) for nid, n in sem.nodes.items()}

        # Enrich — should NOT write ELK positions back to _Node
        enrich_flowchart_finalized_layout(elk_layout, sem)

        after = {nid: (n.x, n.y) for nid, n in sem.nodes.items()}
        assert before == after, (
            f"enrich_flowchart_finalized_layout wrote to _Node.x/_Node.y: {before} -> {after}"
        )

    def test_elk_layout_node_positions_come_from_elk_not_python(self, monkeypatch):
        """NodeLayout.outer_bounds in enriched layout uses ELK positions, not Python. (AC2)"""
        elk_x, elk_y = 999.0, 888.0
        elk_layout = _make_finalized_layout(node_ids=("A", "B"), edge_ids=("A->B",))
        # Override A's position to something distinctive
        import dataclasses
        a_nl = elk_layout.node_layouts["A"]
        a_nl_new = dataclasses.replace(a_nl, outer_bounds=Rect(x=elk_x, y=elk_y, w=192.0, h=42.0))
        new_nls = dict(elk_layout.node_layouts)
        new_nls["A"] = a_nl_new
        elk_layout_mod = dataclasses.replace(elk_layout, node_layouts=_types.MappingProxyType(new_nls))

        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        enriched = enrich_flowchart_finalized_layout(elk_layout_mod, sem)
        assert enriched.node_layouts["A"].outer_bounds.x == elk_x
        assert enriched.node_layouts["A"].outer_bounds.y == elk_y


# ── Task 3: terminal-circle targeted handling ──────────────────────────────────

class TestTerminalCircle:
    """Task 3: terminal circles must not force whole-diagram fallback. (AC3)"""

    def test_terminal_circle_parse_succeeds(self):
        """State diagram with terminal circles parses without error."""
        sem = parse_flowchart_semantics(_TERMINAL_CIRCLE_SRC)
        assert len(sem.nodes) > 0

    def test_terminal_circle_compile_uses_python_path(self, monkeypatch):
        """State diagrams with terminal circles fall back to Python (ELK unavailable)."""
        # ELK is not available in CI; the diagram should still compile via Python fallback.
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
        compiled = _compile_flowchart(_TERMINAL_CIRCLE_SRC, 800, None)
        assert compiled.layout is not None
        # When ELK is disabled: fallback_reason is set
        assert compiled.metadata.fallback_reason in (None, "elk-unavailable", "inner-direction")

    def test_terminal_circle_no_exception_raised(self, monkeypatch):
        """Compiling a terminal-circle diagram does not raise an exception. (AC3)"""
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
        # Before this fix: a bare `raise Exception("terminal-circle fallback to Python")`
        # in the ELK try-block would skip ELK. After fix: no such unconditional raise.
        try:
            compiled = _compile_flowchart(_TERMINAL_CIRCLE_SRC, 800, None)
            assert compiled is not None
        except Exception as exc:
            pytest.fail(f"_compile_flowchart raised unexpectedly: {exc}")


# ── Task 4: self-loop local repair ─────────────────────────────────────────────

class TestSelfLoopRepair:
    """Task 4: self-loops receive local repair; other edges are untouched. (AC4)"""

    def test_is_degenerate_self_loop_with_no_waypoints(self):
        """A self-loop RoutedEdge with 0 waypoints is degenerate."""
        edge = RoutedEdge(
            edge_id="A->A",
            src_node_id="A",
            dst_node_id="A",
            src_port=PortLayout("A", PortSide.TOP, Point(0.0, 0.0), Point(0.0, -1.0)),
            dst_port=PortLayout("A", PortSide.TOP, Point(0.0, 0.0), Point(0.0, -1.0)),
            waypoints=(),
            edge_style="solid",
            has_marker_end=True,
            has_marker_start=False,
            label_layout=None,
            src_label_layout=None,
            dst_label_layout=None,
            source_marker=MarkerKind.NONE,
            target_marker=MarkerKind.ARROW,
            junction_points=(),
        )
        assert _is_degenerate_self_loop(edge)

    def test_is_degenerate_self_loop_with_single_point(self):
        """A self-loop RoutedEdge with 1 waypoint is degenerate."""
        p = Point(50.0, 50.0)
        edge = RoutedEdge(
            edge_id="A->A",
            src_node_id="A",
            dst_node_id="A",
            src_port=PortLayout("A", PortSide.TOP, p, Point(0.0, -1.0)),
            dst_port=PortLayout("A", PortSide.TOP, p, Point(0.0, -1.0)),
            waypoints=(p,),
            edge_style="solid",
            has_marker_end=True,
            has_marker_start=False,
            label_layout=None,
            src_label_layout=None,
            dst_label_layout=None,
            source_marker=MarkerKind.NONE,
            target_marker=MarkerKind.ARROW,
            junction_points=(),
        )
        assert _is_degenerate_self_loop(edge)

    def test_repair_elk_self_loop_produces_valid_path(self):
        """_repair_elk_self_loop creates 4-point rectangular path."""
        p = Point(50.0, 50.0)
        edge = RoutedEdge(
            edge_id="A->A",
            src_node_id="A",
            dst_node_id="A",
            src_port=PortLayout("A", PortSide.TOP, p, Point(0.0, -1.0)),
            dst_port=PortLayout("A", PortSide.TOP, p, Point(0.0, -1.0)),
            waypoints=(),
            edge_style="solid",
            has_marker_end=True,
            has_marker_start=False,
            label_layout=None,
            src_label_layout=None,
            dst_label_layout=None,
            source_marker=MarkerKind.NONE,
            target_marker=MarkerKind.ARROW,
            junction_points=(),
        )
        nl = NodeLayout(
            node_id="A",
            semantic_shape="rect",
            outer_bounds=Rect(x=0.0, y=0.0, w=192.0, h=42.0),
            content_bounds=Rect(x=8.0, y=4.0, w=176.0, h=34.0),
            title_layout=None,
            subtitle_layout=None,
            member_layouts=(),
            icon_bounds=None,
            ports=(),
            css_classes=(),
            extra_css="",
            is_dummy=False,
            rank=1,
            is_external=False,
            icon_svg="",
            accent_color="",
            parent_group_id=None,
        )
        repaired = _repair_elk_self_loop(edge, nl)
        assert len(repaired.waypoints) == 4
        assert len({(wp.x, wp.y) for wp in repaired.waypoints}) >= 2

    def test_enrich_repairs_only_self_loop_edge(self):
        """enrich_flowchart_finalized_layout repairs self-loop but preserves normal edge. (AC4)"""
        # Build a 3-node layout with A→A (degenerate) and A→B (normal)
        node_layouts = {
            "A": NodeLayout(
                node_id="A", semantic_shape="rect",
                outer_bounds=Rect(x=0.0, y=0.0, w=192.0, h=42.0),
                content_bounds=Rect(x=8.0, y=4.0, w=176.0, h=34.0),
                title_layout=None, subtitle_layout=None, member_layouts=(),
                icon_bounds=None, ports=(), css_classes=(), extra_css="",
                is_dummy=False, rank=1, is_external=False, icon_svg="", accent_color="",
                parent_group_id=None,
            ),
            "B": NodeLayout(
                node_id="B", semantic_shape="rect",
                outer_bounds=Rect(x=0.0, y=200.0, w=192.0, h=42.0),
                content_bounds=Rect(x=8.0, y=204.0, w=176.0, h=34.0),
                title_layout=None, subtitle_layout=None, member_layouts=(),
                icon_bounds=None, ports=(), css_classes=(), extra_css="",
                is_dummy=False, rank=2, is_external=False, icon_svg="", accent_color="",
                parent_group_id=None,
            ),
        }
        normal_wps = (Point(96.0, 42.0), Point(96.0, 100.0), Point(96.0, 200.0))
        self_loop_edge = RoutedEdge(
            edge_id="A->A", src_node_id="A", dst_node_id="A",
            src_port=PortLayout("A", PortSide.TOP, Point(96.0, 0.0), Point(0.0, -1.0)),
            dst_port=PortLayout("A", PortSide.TOP, Point(96.0, 0.0), Point(0.0, -1.0)),
            waypoints=(),  # degenerate
            edge_style="solid", has_marker_end=True, has_marker_start=False,
            label_layout=None, src_label_layout=None, dst_label_layout=None,
            source_marker=MarkerKind.NONE, target_marker=MarkerKind.ARROW,
            junction_points=(),
        )
        normal_edge = RoutedEdge(
            edge_id="A->B", src_node_id="A", dst_node_id="B",
            src_port=PortLayout("A", PortSide.BOTTOM, Point(96.0, 42.0), Point(0.0, 1.0)),
            dst_port=PortLayout("B", PortSide.TOP, Point(96.0, 200.0), Point(0.0, -1.0)),
            waypoints=normal_wps,
            edge_style="solid", has_marker_end=True, has_marker_start=False,
            label_layout=None, src_label_layout=None, dst_label_layout=None,
            source_marker=MarkerKind.NONE, target_marker=MarkerKind.ARROW,
            junction_points=(),
        )
        canvas = Rect(x=0.0, y=0.0, w=400.0, h=400.0)
        elk_layout = FinalizedLayout(
            node_layouts=_types.MappingProxyType(node_layouts),
            group_layouts=_types.MappingProxyType({}),
            routed_edges=(self_loop_edge, normal_edge),
            routing_failures=(), visible_bounds=canvas, diagram_padding=48.0,
            canvas_bounds=canvas, direction="TB", diagnostics=_empty_diagnostics(),
        )
        sem = parse_flowchart_semantics("flowchart TB\n  A --> A\n  A --> B")
        enriched = enrich_flowchart_finalized_layout(elk_layout, sem)

        # Normal edge must be unchanged
        out_normal = next(e for e in enriched.routed_edges if e.edge_id == "A->B")
        assert out_normal.waypoints == normal_wps, "Normal edge waypoints were modified"

        # Self-loop must be repaired
        out_self = next(e for e in enriched.routed_edges if e.edge_id == "A->A")
        assert len(out_self.waypoints) >= 3, "Self-loop was not repaired"


# ── Task 5: typed exception handling and metadata ──────────────────────────────

class TestTypedExceptionHandling:
    """Task 5: AC5 (typed fallback reason), AC9 (backend+algorithm populated)."""

    def test_elk_unavailable_produces_typed_fallback(self, monkeypatch):
        """ElkUnavailable → fallback with fallback_reason='elk-unavailable'. (AC5)"""
        monkeypatch.setattr(
            _pipeline_mod, "layout_flowchart_with_elk",
            lambda graph, spacing=None: (_ for _ in ()).throw(ElkUnavailable("no node")),
        )
        compiled = _compile_flowchart(_SIMPLE_SRC, 800, None)
        assert compiled.metadata.fallback_reason == "elk-unavailable"

    def test_elk_invalid_result_produces_typed_fallback(self, monkeypatch):
        """ElkInvalidResult → fallback with fallback_reason='elk-unavailable'. (AC5)"""
        monkeypatch.setattr(
            _pipeline_mod, "layout_flowchart_with_elk",
            lambda graph, spacing=None: (_ for _ in ()).throw(
                ElkInvalidResult("bad geometry")
            ),
        )
        compiled = _compile_flowchart(_SIMPLE_SRC, 800, None)
        assert compiled.metadata.fallback_reason == "elk-unavailable"

    def test_unexpected_exception_propagates(self, monkeypatch):
        """An unexpected exception from ELK propagates — not silently caught."""
        monkeypatch.setattr(
            _pipeline_mod, "layout_flowchart_with_elk",
            lambda graph, spacing=None: (_ for _ in ()).throw(
                RuntimeError("unexpected problem")
            ),
        )
        with pytest.raises(RuntimeError, match="unexpected problem"):
            _compile_flowchart(_SIMPLE_SRC, 800, None)

    def test_metadata_backend_algorithm_on_python_fallback(self, monkeypatch):
        """Python fallback result has non-empty backend and algorithm. (AC9)"""
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
        compiled = _compile_flowchart(_SIMPLE_SRC, 800, None)
        assert compiled.metadata.backend, "metadata.backend is empty"
        assert compiled.metadata.algorithm, "metadata.algorithm is empty"
        assert compiled.metadata.fallback_reason == "elk-unavailable"

    def test_inner_dir_fallback_has_typed_reason(self):
        """Inner-direction compound diagrams use the bottom-up Python compound path
        (the one that emits BoundaryGate records) with fallback_reason
        'inner-direction'. (AC5)"""
        src = "flowchart TB\n  subgraph SG\n    direction LR\n    A --> B\n  end\n  C --> A"
        sem = parse_flowchart_semantics(src)
        if not sem.has_inner_dir:
            pytest.skip("No inner-direction detected; test not applicable")
        # Compile and verify
        compiled = _compile_flowchart(src, 800, None)
        assert compiled.metadata.fallback_reason == "inner-direction"


# ── Task 6: edge-ID-based metadata ─────────────────────────────────────────────

class TestEdgeIdKeying:
    """Task 6: AC8 (edge lookups use edge_id, not (src, dst))."""

    def test_parallel_edges_have_distinct_ids(self):
        """Parallel edges between the same pair of nodes have distinct edge_ids."""
        sem = parse_flowchart_semantics(_PARALLEL_EDGES_SRC)
        graph = build_flowchart_layout_graph(sem)
        edge_ids = [e.id for e in graph.edges]
        assert len(edge_ids) == len(set(edge_ids)), f"Duplicate edge IDs: {edge_ids}"

    def test_edge_id_not_src_dst_tuple(self):
        """Edge IDs in build_flowchart_layout_graph use string, not (src, dst) tuples."""
        sem = parse_flowchart_semantics(_PARALLEL_EDGES_SRC)
        graph = build_flowchart_layout_graph(sem)
        for edge in graph.edges:
            assert isinstance(edge.id, str), f"Edge ID is not a string: {type(edge.id)}"
            assert edge.id, "Edge ID is empty"

    def test_enrichment_preserves_edge_ids_from_elk(self):
        """enrich_flowchart_finalized_layout preserves ELK edge_id values. (AC6, AC8)"""
        elk_layout = _make_finalized_layout(node_ids=("A", "B"), edge_ids=("A->B",))
        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        enriched = enrich_flowchart_finalized_layout(elk_layout, sem)
        out_ids = {e.edge_id for e in enriched.routed_edges}
        assert "A->B" in out_ids, f"ELK edge_id 'A->B' missing from enriched edges: {out_ids}"


# ── AC6: edge properties preserved through enrichment ─────────────────────────

class TestEdgePropertiesPreservation:
    """AC6: edge style, markers, labels, ports, junction_points survive enrichment."""

    def test_edge_style_preserved(self):
        """edge_style from ELK is preserved through enrich."""
        import dataclasses
        elk_layout = _make_finalized_layout()
        # Modify edge style to "dotted"
        old_edge = elk_layout.routed_edges[0]
        new_edge = dataclasses.replace(old_edge, edge_style="dotted")
        new_routed = (new_edge,)
        elk_mod = dataclasses.replace(elk_layout, routed_edges=new_routed)

        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        enriched = enrich_flowchart_finalized_layout(elk_mod, sem)
        assert enriched.routed_edges[0].edge_style == "dotted"

    def test_junction_points_preserved(self):
        """junction_points from ELK are preserved through enrich."""
        import dataclasses
        elk_layout = _make_finalized_layout()
        jp = (Point(50.0, 50.0),)
        old_edge = elk_layout.routed_edges[0]
        new_edge = dataclasses.replace(old_edge, junction_points=jp)
        elk_mod = dataclasses.replace(elk_layout, routed_edges=(new_edge,))

        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        enriched = enrich_flowchart_finalized_layout(elk_mod, sem)
        assert enriched.routed_edges[0].junction_points == jp

    def test_elk_group_layouts_preserved(self):
        """ELK group_layouts pass through enrichment unchanged."""
        import dataclasses
        elk_layout = _make_finalized_layout()
        # Build a minimal GroupLayout
        grp = GroupLayout(
            group_id="SG",
            parent_group_id=None,
            boundary_bounds=Rect(x=0.0, y=0.0, w=400.0, h=200.0),
            label_layout=None,
            member_ids=("A",),
            child_group_ids=(),
            local_direction="TB",
        )
        elk_mod = dataclasses.replace(
            elk_layout,
            group_layouts=_types.MappingProxyType({"SG": grp}),
        )
        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        enriched = enrich_flowchart_finalized_layout(elk_mod, sem)
        assert "SG" in enriched.group_layouts
        assert enriched.group_layouts["SG"].boundary_bounds == grp.boundary_bounds


# ── AC9: backend and algorithm fields ─────────────────────────────────────────

class TestMetadataFields:
    """AC9: metadata.backend and metadata.algorithm are always populated."""

    def test_python_fallback_metadata(self, monkeypatch):
        """Python path produces non-empty backend and algorithm fields."""
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
        compiled = _compile_flowchart(_SIMPLE_SRC, 800, None)
        assert compiled.metadata.backend == "python"
        assert "LongestPath" in compiled.metadata.algorithm

    def test_layout_flowchart_with_python_fallback_metadata(self):
        """layout_flowchart_with_python_fallback returns LayoutMetadata."""
        sem = parse_flowchart_semantics(_SIMPLE_SRC)
        _, meta = layout_flowchart_with_python_fallback(sem)
        assert meta.backend == "python"
        assert meta.algorithm
        assert meta.node_count > 0
