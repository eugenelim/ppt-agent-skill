"""Stage 9 tests: renderer serialization-only.

Verifies that render_finalized(FinalizedLayout) performs no geometry work —
specifically that it does NOT call _route_edges, _compute_group_bboxes, or
any other geometry-computing function.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from mermaid_render.layout._geometry import (
    FinalizedLayout, NodeLayout, GroupLayout, RoutedEdge,
    Rect, Point, PortLayout, PortSide, TextLayout, TextLine, TextRun, TextStyle,
    LayoutDiagnostics,
)
from mermaid_render.layout._renderer import render_finalized


# ── Minimal fixture factories ─────────────────────────────────────────────────

def _empty_text_layout() -> TextLayout:
    return TextLayout(
        lines=(), width=0.0, height=0.0, line_height=15.0,
        min_content_width=0.0, max_content_width=0.0,
        resolved_font_path=None, resolved_font_family="system-ui",
    )


def _simple_text_layout(text: str) -> TextLayout:
    style = TextStyle(font_size=15.0)
    run = TextRun(text=text, style=style, width=len(text) * 8.0, height=18.0)
    line = TextLine(runs=(run,), width=run.width, height=18.0, baseline=14.0)
    return TextLayout(
        lines=(line,), width=run.width, height=18.0, line_height=18.0,
        min_content_width=run.width, max_content_width=run.width,
        resolved_font_path=None, resolved_font_family="system-ui",
    )


def _make_port(node_id: str, side: PortSide = PortSide.AUTO) -> PortLayout:
    return PortLayout(
        node_id=node_id, side=side,
        position=Point(0, 0), direction=Point(1, 0),
    )


def _make_node_layout(nid: str, x: float, y: float, w: float = 100, h: float = 40) -> NodeLayout:
    b = Rect(x, y, w, h)
    return NodeLayout(
        node_id=nid, semantic_shape="rect",
        outer_bounds=b, content_bounds=b,
        title_layout=_simple_text_layout(nid),
        subtitle_layout=None,
        member_layouts=(),
        icon_bounds=None,
        ports=(_make_port(nid),),
        css_classes=(),
        extra_css="",
        is_dummy=False,
    )


def _make_routed_edge(src: str, dst: str, has_arrow: bool = True) -> RoutedEdge:
    return RoutedEdge(
        edge_id=f"{src}->{dst}",
        src_node_id=src, dst_node_id=dst,
        src_port=_make_port(src), dst_port=_make_port(dst),
        waypoints=(Point(0, 0), Point(100, 100)),
        edge_style="solid",
        has_marker_end=has_arrow, has_marker_start=False,
        label_layout=None, src_label_layout=None, dst_label_layout=None,
    )


def _make_finalized(
    nodes: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
    canvas_w: float = 300, canvas_h: float = 200,
) -> FinalizedLayout:
    node_layouts = {
        nid: _make_node_layout(nid, x, y)
        for nid, (x, y) in nodes.items()
    }
    routed_edges = tuple(
        _make_routed_edge(src, dst) for src, dst in edges
    )
    cb = Rect(0, 0, canvas_w, canvas_h)
    return FinalizedLayout(
        node_layouts=node_layouts,
        group_layouts={},
        routed_edges=routed_edges,
        visible_bounds=cb,
        diagram_padding=20.0,
        canvas_bounds=cb,
        direction="TB",
        diagnostics=LayoutDiagnostics(
            unsupported_options=(), route_failures=(), warnings=()
        ),
    )


# ── Core: no geometry work during render_finalized ────────────────────────────

class TestNoGeometryWork:
    """Prove render_finalized does not call routing or geometry functions."""

    def test_route_edges_not_called(self, monkeypatch):
        """_route_edges must not be called during render_finalized."""
        import mermaid_render.layout._renderer as _mod

        def _bad_route(*args, **kwargs):
            raise AssertionError("_route_edges was called during render_finalized")

        monkeypatch.setattr(_mod, "_route_edges", _bad_route)

        layout = _make_finalized({"A": (10, 10), "B": (10, 100)}, [("A", "B")])
        # Should not raise
        html = render_finalized(layout)
        assert html  # sanity

    def test_compute_group_bboxes_not_called(self, monkeypatch):
        """_compute_group_bboxes must not be called during render_finalized."""
        import mermaid_render.layout._renderer as _mod

        def _bad_bbox(*args, **kwargs):
            raise AssertionError("_compute_group_bboxes was called during render_finalized")

        monkeypatch.setattr(_mod, "_compute_group_bboxes", _bad_bbox)

        layout = _make_finalized({"A": (10, 10), "B": (10, 100)}, [("A", "B")])
        html = render_finalized(layout)
        assert html

    def test_no_import_of_routing_on_call(self, monkeypatch):
        """render_finalized must not import and call _route_edges indirectly."""
        import mermaid_render.layout._routing as _routing_mod

        _calls: list[str] = []
        orig = _routing_mod._route_edges

        def _tracking_route(*args, **kwargs):
            _calls.append("_route_edges")
            return orig(*args, **kwargs)

        monkeypatch.setattr(_routing_mod, "_route_edges", _tracking_route)

        layout = _make_finalized({"A": (10, 10), "B": (10, 100)}, [("A", "B")])
        render_finalized(layout)
        assert _calls == [], f"_route_edges was called: {_calls}"


# ── Output structure tests ────────────────────────────────────────────────────

class TestRenderFinalizedOutput:
    """Verify that render_finalized produces valid, stable HTML."""

    def _simple_layout(self) -> FinalizedLayout:
        return _make_finalized({"A": (10, 10), "B": (10, 100)}, [("A", "B")])

    def test_produces_non_empty_html(self):
        html = render_finalized(self._simple_layout())
        assert html.strip()

    def test_contains_diagram_class(self):
        html = render_finalized(self._simple_layout())
        assert "diagram mermaid-layout" in html

    def test_contains_node_ids(self):
        html = render_finalized(self._simple_layout())
        assert 'data-node-id="A"' in html
        assert 'data-node-id="B"' in html

    def test_contains_edge_path(self):
        html = render_finalized(self._simple_layout())
        assert "<path" in html

    def test_contains_edge_data_attributes(self):
        html = render_finalized(self._simple_layout())
        assert 'data-src="A"' in html
        assert 'data-dst="B"' in html

    def test_canvas_dimensions_in_root_div(self):
        html = render_finalized(self._simple_layout())
        assert 'data-diagram-w="300"' in html
        assert 'data-diagram-h="200"' in html

    def test_node_positions_in_html(self):
        layout = _make_finalized({"A": (50, 80)}, [])
        html = render_finalized(layout)
        assert "left:50px" in html
        assert "top:80px" in html

    def test_deterministic_repeated_calls(self):
        layout = self._simple_layout()
        html1 = render_finalized(layout)
        html2 = render_finalized(layout)
        assert html1 == html2

    def test_empty_layout_does_not_crash(self):
        layout = _make_finalized({}, [])
        html = render_finalized(layout)
        assert "diagram mermaid-layout" in html

    def test_group_boundary_rendered(self):
        """Groups are rendered as dashed boxes."""
        from mermaid_render.layout._geometry import GroupLayout
        layout = _make_finalized({"A": (10, 10)}, [])
        gl = GroupLayout(
            group_id="grp", parent_group_id=None,
            boundary_bounds=Rect(0, 0, 200, 100),
            label_layout=_simple_text_layout("My Group"),
            member_ids=("A",), child_group_ids=(),
            local_direction="TB",
        )
        layout2 = FinalizedLayout(
            node_layouts=layout.node_layouts,
            group_layouts={"grp": gl},
            routed_edges=layout.routed_edges,
            visible_bounds=layout.visible_bounds,
            diagram_padding=layout.diagram_padding,
            canvas_bounds=layout.canvas_bounds,
            direction=layout.direction,
            diagnostics=layout.diagnostics,
        )
        html = render_finalized(layout2)
        assert 'data-group-id="grp"' in html

    def test_dummy_nodes_excluded(self):
        """Dummy nodes must not appear in render_finalized output."""
        from mermaid_render.layout._geometry import NodeLayout
        layout = _make_finalized({"A": (10, 10)}, [])
        dummy = NodeLayout(
            node_id="_dummy_X_Y_1", semantic_shape="rect",
            outer_bounds=Rect(50, 50, 0, 0), content_bounds=Rect(50, 50, 0, 0),
            title_layout=None, subtitle_layout=None,
            member_layouts=(), icon_bounds=None,
            ports=(), css_classes=(), extra_css="",
            is_dummy=True,
        )
        layout2 = FinalizedLayout(
            node_layouts={"A": layout.node_layouts["A"], "_dummy_X_Y_1": dummy},
            group_layouts={},
            routed_edges=(),
            visible_bounds=layout.visible_bounds,
            diagram_padding=layout.diagram_padding,
            canvas_bounds=layout.canvas_bounds,
            direction=layout.direction,
            diagnostics=layout.diagnostics,
        )
        html = render_finalized(layout2)
        assert "_dummy_X_Y_1" not in html

    def test_edge_label_rendered(self):
        """If a RoutedEdge has a label_layout, the label text appears in output."""
        from mermaid_render.layout._geometry import EdgeLabelLayout
        layout = _make_finalized({"A": (10, 10), "B": (10, 100)}, [])
        lbl = EdgeLabelLayout(
            text="calls",
            layout=_simple_text_layout("calls"),
            bounds=Rect(50, 50, 60, 20),
            anchor_point=Point(80, 60),
        )
        re_with_label = RoutedEdge(
            edge_id="A->B", src_node_id="A", dst_node_id="B",
            src_port=_make_port("A"), dst_port=_make_port("B"),
            waypoints=(Point(0, 0), Point(100, 100)),
            edge_style="solid",
            has_marker_end=True, has_marker_start=False,
            label_layout=lbl, src_label_layout=None, dst_label_layout=None,
        )
        layout2 = FinalizedLayout(
            node_layouts=layout.node_layouts,
            group_layouts={},
            routed_edges=(re_with_label,),
            visible_bounds=layout.visible_bounds,
            diagram_padding=layout.diagram_padding,
            canvas_bounds=layout.canvas_bounds,
            direction=layout.direction,
            diagnostics=layout.diagnostics,
        )
        html = render_finalized(layout2)
        assert "calls" in html
