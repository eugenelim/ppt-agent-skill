"""Tests for the immutable geometry IR (_geometry.py)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mermaid_render.layout._geometry import (
    Point, Size, Insets, Rect, PortSide,
    TextStyle, TextRun, TextLine, TextLayout,
    PortRequest, PortLayout,
    NodeLayout, GroupLayout, EdgeLabelLayout, RoutedEdge,
    LayoutDiagnostics, FinalizedLayout,
    _empty_diagnostics,
    # Pre-layout IR (T1)
    MarkerKind, PortSpec, LayoutNode, LayoutGroup, LayoutEdge, LayoutGraph,
)


class TestRect:
    def test_x1_y1(self):
        r = Rect(10, 20, 100, 50)
        assert r.x1 == 110
        assert r.y1 == 70

    def test_center(self):
        r = Rect(0, 0, 100, 80)
        c = r.center
        assert c.x == 50
        assert c.y == 40

    def test_contains_self(self):
        r = Rect(0, 0, 100, 100)
        assert r.contains(r)

    def test_contains_inner(self):
        outer = Rect(0, 0, 100, 100)
        inner = Rect(10, 10, 80, 80)
        assert outer.contains(inner)
        assert not inner.contains(outer)

    def test_overlaps_partial(self):
        a = Rect(0, 0, 50, 50)
        b = Rect(25, 25, 50, 50)
        assert a.overlaps(b)
        assert b.overlaps(a)

    def test_overlaps_touching_edge_false(self):
        a = Rect(0, 0, 50, 50)
        b = Rect(50, 0, 50, 50)
        assert not a.overlaps(b)

    def test_union(self):
        a = Rect(0, 0, 50, 50)
        b = Rect(30, 30, 50, 50)
        u = a.union(b)
        assert u.x == 0 and u.y == 0
        assert u.x1 == 80 and u.y1 == 80

    def test_union_all(self):
        rects = [Rect(0, 0, 10, 10), Rect(5, 5, 10, 10), Rect(-5, 0, 8, 20)]
        u = Rect.union_all(rects)
        assert u.x == -5
        assert u.y == 0
        assert u.x1 == 15
        assert u.y1 == 20

    def test_inflate(self):
        r = Rect(10, 10, 80, 60)
        inflated = r.inflate(5)
        assert inflated.x == 5
        assert inflated.y == 5
        assert inflated.w == 90
        assert inflated.h == 70

    def test_inflate_asymmetric(self):
        r = Rect(0, 0, 100, 50)
        inf = r.inflate(10, 5)
        assert inf.x == -10 and inf.y == -5
        assert inf.w == 120 and inf.h == 60

    def test_translate(self):
        r = Rect(10, 20, 50, 30)
        t = r.translate(5, -10)
        assert t.x == 15 and t.y == 10
        assert t.w == 50 and t.h == 30

    def test_intersection_area_full_overlap(self):
        r = Rect(0, 0, 100, 100)
        assert r.intersection_area(r) == pytest.approx(10000)

    def test_intersection_area_no_overlap(self):
        a = Rect(0, 0, 50, 50)
        b = Rect(100, 100, 50, 50)
        assert a.intersection_area(b) == 0.0

    def test_intersection_area_partial(self):
        a = Rect(0, 0, 50, 50)
        b = Rect(25, 25, 50, 50)
        assert a.intersection_area(b) == pytest.approx(625)

    def test_from_points(self):
        pts = [Point(5, 10), Point(20, 3), Point(15, 25)]
        r = Rect.from_points(pts)
        assert r.x == 5 and r.y == 3
        assert r.x1 == 20 and r.y1 == 25

    def test_from_ltrb(self):
        r = Rect.from_ltrb(10, 20, 110, 70)
        assert r.x == 10 and r.y == 20
        assert r.w == 100 and r.h == 50

    def test_inset(self):
        r = Rect(0, 0, 100, 80)
        ins = Insets(top=10, right=8, bottom=12, left=6)
        inner = r.inset(ins)
        assert inner.x == 6 and inner.y == 10
        assert inner.w == 86 and inner.h == 58

    def test_immutable(self):
        r = Rect(0, 0, 100, 100)
        with pytest.raises((TypeError, AttributeError)):
            r.x = 5  # type: ignore[misc]

    def test_contains_point(self):
        r = Rect(10, 10, 80, 60)
        assert r.contains_point(Point(50, 40))
        assert not r.contains_point(Point(0, 0))
        assert r.contains_point(Point(5, 40), tolerance=6)


class TestPoint:
    def test_translate(self):
        p = Point(10, 20)
        q = p.translate(5, -3)
        assert q.x == 15 and q.y == 17

    def test_distance_to(self):
        a = Point(0, 0)
        b = Point(3, 4)
        assert a.distance_to(b) == pytest.approx(5.0)

    def test_immutable(self):
        p = Point(1, 2)
        with pytest.raises((TypeError, AttributeError)):
            p.x = 99  # type: ignore[misc]


class TestPortSide:
    def test_all_values_present(self):
        sides = {s.value for s in PortSide}
        assert sides == {"AUTO", "LEFT", "RIGHT", "TOP", "BOTTOM"}

    def test_enum_identity(self):
        assert PortSide.AUTO is PortSide.AUTO
        assert PortSide.LEFT != PortSide.RIGHT


class TestInsets:
    def test_uniform(self):
        ins = Insets.uniform(8)
        assert ins.top == ins.right == ins.bottom == ins.left == 8

    def test_symmetric(self):
        ins = Insets.symmetric(vertical=10, horizontal=20)
        assert ins.top == ins.bottom == 10
        assert ins.left == ins.right == 20


class TestFinalizedLayout:
    def _make_layout(self) -> FinalizedLayout:
        vis = Rect(0, 0, 500, 400)
        canvas = vis.inflate(48)
        return FinalizedLayout(
            node_layouts={},
            group_layouts={},
            routed_edges=(),
            visible_bounds=vis,
            diagram_padding=48,
            canvas_bounds=canvas,
            direction="TB",
            diagnostics=_empty_diagnostics(),
        )

    def test_construction(self):
        layout = self._make_layout()
        assert layout.direction == "TB"
        assert layout.diagram_padding == 48

    def test_immutable(self):
        layout = self._make_layout()
        with pytest.raises((TypeError, AttributeError)):
            layout.direction = "LR"  # type: ignore[misc]

    def test_empty_diagnostics(self):
        d = _empty_diagnostics()
        assert d.unsupported_options == ()
        assert d.route_failures == ()
        assert d.warnings == ()

    def test_canvas_contains_visible(self):
        layout = self._make_layout()
        assert layout.canvas_bounds.contains(layout.visible_bounds)


# ── Pre-layout IR (T1: LayoutGraph) ──────────────────────────────────────────

class TestMarkerKind:
    def test_values_importable(self):
        assert MarkerKind.NONE.value == "none"
        assert MarkerKind.ARROW.value == "arrow"
        assert MarkerKind.CROW_ZERO_MANY.value == "crow_zero_many"

    def test_crow_variants_present(self):
        assert MarkerKind.CROW_ONE in MarkerKind
        assert MarkerKind.CROW_MANY in MarkerKind
        assert MarkerKind.CROW_ZERO_ONE in MarkerKind
        assert MarkerKind.CROW_ZERO_MANY in MarkerKind

    def test_string_coercible(self):
        assert MarkerKind("arrow") == MarkerKind.ARROW


class TestPortSpec:
    def test_construction(self):
        ps = PortSpec(id="p0", node_id="A", side="NORTH", index=0,
                      fixed_side=True, fixed_order=False)
        assert ps.side == "NORTH"
        assert ps.fixed_side is True

    def test_immutable(self):
        ps = PortSpec(id="p0", node_id="A", side="EAST", index=0,
                      fixed_side=False, fixed_order=False)
        with pytest.raises((TypeError, AttributeError)):
            ps.side = "WEST"  # type: ignore[misc]


class TestLayoutNode:
    def test_construction(self):
        node = LayoutNode(id="A", measured_width=192, measured_height=42,
                          shape_id="rect", parent_id=None, ports=[], labels=["A"],
                          semantic_data={})
        assert node.id == "A"
        assert node.measured_width == 192
        assert node.parent_id is None
        assert node.labels == ("A",)
        assert node.ports == ()

    def test_ports_coerced_to_tuple(self):
        ps = PortSpec(id="p0", node_id="A", side="NORTH", index=0,
                      fixed_side=True, fixed_order=False)
        node = LayoutNode(id="A", measured_width=100, measured_height=40,
                          shape_id="rect", parent_id=None, ports=[ps], labels=[],
                          semantic_data={})
        assert isinstance(node.ports, tuple)
        assert node.ports[0].id == "p0"

    def test_semantic_data_immutable_proxy(self):
        node = LayoutNode(id="A", measured_width=100, measured_height=40,
                          shape_id="rect", parent_id=None, ports=[], labels=[],
                          semantic_data={"k": "v"})
        assert node.semantic_data["k"] == "v"
        with pytest.raises(TypeError):
            node.semantic_data["k"] = "x"  # type: ignore[index]


class TestLayoutEdge:
    def test_construction(self):
        edge = LayoutEdge(id="e0", sources=["A"], targets=["B"],
                          source_port=None, target_port=None,
                          source_marker=MarkerKind.NONE,
                          target_marker=MarkerKind.ARROW,
                          line_style="solid", label="", semantic_data={})
        assert edge.source_marker == MarkerKind.NONE
        assert edge.target_marker == MarkerKind.ARROW
        assert edge.sources == ("A",)

    def test_marker_string_coercion(self):
        edge = LayoutEdge(id="e0", sources=["A"], targets=["B"],
                          source_port=None, target_port=None,
                          source_marker="arrow",  # type: ignore[arg-type]
                          target_marker="none",   # type: ignore[arg-type]
                          line_style="solid", label="", semantic_data={})
        assert edge.source_marker == MarkerKind.ARROW
        assert edge.target_marker == MarkerKind.NONE


class TestLayoutGraph:
    def test_construction(self):
        node = LayoutNode(id="A", measured_width=192, measured_height=42,
                          shape_id="rect", parent_id=None, ports=[], labels=["A"],
                          semantic_data={})
        graph = LayoutGraph(nodes=[node], groups=[], edges=[], direction="TB")
        assert graph.direction == "TB"
        assert len(graph.nodes) == 1
        assert graph.nodes[0].id == "A"

    def test_immutable(self):
        graph = LayoutGraph(nodes=[], groups=[], edges=[], direction="LR")
        with pytest.raises((TypeError, AttributeError)):
            graph.direction = "TB"  # type: ignore[misc]

    def test_sequences_coerced_to_tuple(self):
        graph = LayoutGraph(nodes=[], groups=[], edges=[], direction="TB")
        assert isinstance(graph.nodes, tuple)
        assert isinstance(graph.edges, tuple)


# ── ShapeGeometry (T2) ────────────────────────────────────────────────────────

class TestShapeRegistry:
    def test_registry_covers_all_shapes(self):
        from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY
        expected = {
            "rect", "round", "stadium", "diamond", "circle", "doublecircle",
            "cylinder", "hexagon", "trapezoid", "trapezoid-alt", "subroutine",
            "flag", "bar",
        }
        assert expected <= set(SHAPE_REGISTRY.keys())

    def test_all_registry_entries_are_shape_geometry(self):
        from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY, ShapeGeometry
        for name, sg in SHAPE_REGISTRY.items():
            assert isinstance(sg, ShapeGeometry), f"{name!r} does not satisfy ShapeGeometry"

    def test_rect_boundary_right(self):
        from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY
        sg = SHAPE_REGISTRY["rect"]
        x, y = sg.boundary_intersection(96, 21, 192, 42, 1.0, 0.0)
        assert x == pytest.approx(192.0)
        assert y == pytest.approx(21.0)

    def test_rect_boundary_left(self):
        from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY
        sg = SHAPE_REGISTRY["rect"]
        x, y = sg.boundary_intersection(96, 21, 192, 42, -1.0, 0.0)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(21.0)

    def test_rect_boundary_top(self):
        from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY
        sg = SHAPE_REGISTRY["rect"]
        x, y = sg.boundary_intersection(96, 21, 192, 42, 0.0, -1.0)
        assert x == pytest.approx(96.0)
        assert y == pytest.approx(0.0)

    def test_diamond_boundary_right(self):
        from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY
        sg = SHAPE_REGISTRY["diamond"]
        x, y = sg.boundary_intersection(0, 0, 80, 40, 1.0, 0.0)
        assert x > 0
        assert abs(y) < 0.1

    def test_diamond_boundary_matches_clip_to_diamond(self):
        """DiamondGeometry.boundary_intersection must be bit-identical to _clip_to_diamond."""
        from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY
        from mermaid_render.layout._routing import _clip_to_diamond
        sg = SHAPE_REGISTRY["diamond"]
        for dx, dy in [(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0),
                       (1.0, 1.0), (-1.0, 1.0)]:
            cx, cy, w, h = 50.0, 25.0, 100.0, 50.0
            reg_x, reg_y = sg.boundary_intersection(cx, cy, w, h, dx, dy)
            # _clip_to_diamond takes (tip_x, tip_y, cx, cy, w, h, dx, dy)
            # where tip is a point in the outward direction; use cx+dx*1000
            tip_x, tip_y = cx + dx * 1000, cy + dy * 1000
            old_x, old_y = _clip_to_diamond(tip_x, tip_y, cx, cy, w, h, dx, dy)
            assert reg_x == pytest.approx(old_x, abs=0.01), f"dx={dx},dy={dy}"
            assert reg_y == pytest.approx(old_y, abs=0.01), f"dx={dx},dy={dy}"

    def test_circle_boundary_right(self):
        from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY
        sg = SHAPE_REGISTRY["circle"]
        x, y = sg.boundary_intersection(0, 0, 80, 80, 1.0, 0.0)
        assert x == pytest.approx(40.0)
        assert abs(y) < 0.1

    def test_bar_available_ports(self):
        from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY
        sg = SHAPE_REGISTRY["bar"]
        ports = sg.available_ports(60, 8)
        assert set(ports) == {"NORTH", "SOUTH"}


class TestShapeRegistryWiring:
    """T2b: _routing.py routes diamond clipping through SHAPE_REGISTRY."""

    def test_diamond_clipping_uses_registry(self, monkeypatch):
        import os
        from mermaid_render.layout import shape_geometry as sg_mod
        original_sg = sg_mod.SHAPE_REGISTRY["diamond"]
        calls: list = []

        class TrackingDiamond:
            def boundary_intersection(self, *args, **kwargs):
                calls.append(args)
                return original_sg.boundary_intersection(*args, **kwargs)
            def __getattr__(self, name):
                return getattr(original_sg, name)

        monkeypatch.setitem(sg_mod.SHAPE_REGISTRY, "diamond", TrackingDiamond())
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")

        from mermaid_render.layout._strategies import _compile_flowchart, RenderOptions
        _compile_flowchart("flowchart TD\n  A{Decision} --> B", None, RenderOptions())

        assert len(calls) > 0, "SHAPE_REGISTRY['diamond'].boundary_intersection was never called"
