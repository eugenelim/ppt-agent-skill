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
