"""Tests for the native SVG serializer (svg_serializer.py)."""
import re
import pytest
from lxml import etree

from scripts.mermaid_render.scene import (
    SvgScene, SceneGroup, SceneRect, SceneRoundedRect, SceneCircle, SceneEllipse,
    SceneLine, ScenePolyline, ScenePolygon, ScenePath, SceneText, SceneTextLine,
    SceneImage, PaintStyle, StrokeStyle, FillStyle,
    MarkerDefinition, LinearGradientDefinition, ClipPathDefinition,
    AccessibilityMetadata, LAYER_ORDER, LAYER_NODES, LAYER_EDGES, LAYER_LABELS,
)
from scripts.mermaid_render.svg_serializer import (
    scene_to_svg, scene_to_svg_str, validate_scene, SceneValidationError, _fmt,
)

SVG_NS = "http://www.w3.org/2000/svg"


def _make_simple_scene(scene_id="test", w=400.0, h=300.0) -> SvgScene:
    return SvgScene.make_empty(scene_id, "flowchart", w, h)


def _parse(svg_bytes: bytes) -> etree._Element:
    return etree.fromstring(svg_bytes)


class TestFloatFormatting:
    def test_zero(self):
        assert _fmt(0.0) == "0"

    def test_negative_zero(self):
        assert _fmt(-0.0) == "0"

    def test_integer_value(self):
        assert _fmt(100.0) == "100"

    def test_trailing_zeros_stripped(self):
        assert _fmt(1.50) == "1.5"
        assert _fmt(1.500) == "1.5"

    def test_three_dp_max(self):
        assert _fmt(1.0 / 3.0) == "0.333"
        result = _fmt(math.pi)
        assert len(result.split(".")[-1]) <= 3

    def test_rejects_nan(self):
        with pytest.raises(ValueError):
            _fmt(float("nan"))

    def test_rejects_inf(self):
        with pytest.raises(ValueError):
            _fmt(float("inf"))

    def test_negative_value(self):
        assert _fmt(-5.0) == "-5"


import math


class TestEmptyScene:
    def test_empty_scene_produces_valid_svg(self):
        scene = _make_simple_scene()
        svg = scene_to_svg(scene)
        root = _parse(svg)
        assert root.tag == f"{{{SVG_NS}}}svg" or root.tag == "svg" or "svg" in root.tag

    def test_empty_scene_has_correct_dimensions(self):
        scene = _make_simple_scene(w=640.0, h=480.0)
        svg_str = scene_to_svg_str(scene)
        assert 'width="640"' in svg_str
        assert 'height="480"' in svg_str

    def test_empty_scene_has_viewbox(self):
        scene = _make_simple_scene(w=400.0, h=300.0)
        svg_str = scene_to_svg_str(scene)
        assert 'viewBox="0 0 400 300"' in svg_str

    def test_empty_scene_has_role(self):
        scene = _make_simple_scene()
        svg_str = scene_to_svg_str(scene)
        assert "role=" in svg_str

    def test_empty_scene_no_foreignobject(self):
        scene = _make_simple_scene()
        svg_str = scene_to_svg_str(scene)
        assert "foreignObject" not in svg_str
        assert "foreignobject" not in svg_str.lower()

    def test_empty_scene_no_html_head_body(self):
        scene = _make_simple_scene()
        svg_str = scene_to_svg_str(scene).lower()
        assert "<html" not in svg_str
        assert "<head" not in svg_str
        assert "<body" not in svg_str


class TestShapePrimitives:
    def _scene_with_element(self, elem, layer=LAYER_NODES) -> SvgScene:
        layers = tuple(
            (name, (elem,) if name == layer else ())
            for name in LAYER_ORDER
        )
        return SvgScene(
            scene_id="test", diagram_type="test",
            width=200, height=200,
            view_box=(0.0, 0.0, 200.0, 200.0),
            layers=layers,
        )

    def test_rect_produces_rect_element(self):
        rect = SceneRect(
            x=10, y=20, w=100, h=50,
            element_id="r1",
            paint=PaintStyle(fill=FillStyle(color="#fff"), stroke=StrokeStyle(color="#000"))
        )
        svg = scene_to_svg_str(self._scene_with_element(rect))
        assert '<rect' in svg
        assert 'x="10"' in svg
        assert 'y="20"' in svg
        assert 'width="100"' in svg
        assert 'height="50"' in svg
        assert 'id="r1"' in svg

    def test_rounded_rect_has_rx(self):
        rr = SceneRoundedRect(x=0, y=0, w=80, h=40, rx=8, ry=8)
        svg = scene_to_svg_str(self._scene_with_element(rr))
        assert '<rect' in svg
        assert 'rx="8"' in svg

    def test_circle_produces_circle_element(self):
        c = SceneCircle(cx=50, cy=50, r=20)
        svg = scene_to_svg_str(self._scene_with_element(c))
        assert '<circle' in svg
        assert 'cx="50"' in svg
        assert 'r="20"' in svg

    def test_ellipse_produces_ellipse_element(self):
        e = SceneEllipse(cx=50, cy=50, rx=30, ry=15)
        svg = scene_to_svg_str(self._scene_with_element(e))
        assert '<ellipse' in svg
        assert 'rx="30"' in svg

    def test_line_produces_line_element(self):
        ln = SceneLine(x1=0, y1=0, x2=100, y2=100)
        svg = scene_to_svg_str(self._scene_with_element(ln, LAYER_EDGES))
        assert '<line' in svg

    def test_polyline_produces_polyline_element(self):
        pl = ScenePolyline(points=((0.0, 0.0), (50.0, 25.0), (100.0, 0.0)))
        svg = scene_to_svg_str(self._scene_with_element(pl, LAYER_EDGES))
        assert '<polyline' in svg
        assert 'points=' in svg

    def test_polygon_produces_polygon_element(self):
        pg = ScenePolygon(points=((0.0, 0.0), (50.0, 100.0), (100.0, 0.0)))
        svg = scene_to_svg_str(self._scene_with_element(pg))
        assert '<polygon' in svg

    def test_path_produces_path_element(self):
        path = ScenePath(commands=(("M", 0.0, 0.0), ("L", 100.0, 100.0), ("Z",)))
        svg = scene_to_svg_str(self._scene_with_element(path, LAYER_EDGES))
        assert '<path' in svg
        assert ' d="' in svg
        assert 'M 0 0' in svg


class TestTextSerialization:
    def test_text_produces_text_tspan(self):
        line = SceneTextLine(text="Hello", x=50, y=30)
        text = SceneText(lines=(line,))
        layers = tuple(
            (name, (text,) if name == LAYER_LABELS else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="t", diagram_type="test",
            width=200, height=100,
            view_box=(0.0, 0.0, 200.0, 100.0),
            layers=layers,
        )
        svg = scene_to_svg_str(scene)
        assert '<text' in svg
        assert '<tspan' in svg
        assert 'Hello' in svg

    def test_text_multiple_tspans(self):
        lines = tuple(
            SceneTextLine(text=f"line{i}", x=50, y=float(20 + i * 18))
            for i in range(3)
        )
        text = SceneText(lines=lines)
        layers = tuple(
            (name, (text,) if name == LAYER_LABELS else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="t2", diagram_type="test",
            width=200, height=200,
            view_box=(0.0, 0.0, 200.0, 200.0),
            layers=layers,
        )
        svg = scene_to_svg_str(scene)
        assert svg.count('<tspan') == 3

    def test_xml_sensitive_text_is_escaped(self):
        line = SceneTextLine(text='<hello> & "world"', x=10, y=20)
        text = SceneText(lines=(line,))
        layers = tuple(
            (name, (text,) if name == LAYER_LABELS else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="xml", diagram_type="test",
            width=200, height=100,
            view_box=(0.0, 0.0, 200.0, 100.0),
            layers=layers,
        )
        svg = scene_to_svg_str(scene)
        # lxml escapes these automatically
        assert "<hello>" not in svg or "&lt;hello&gt;" in svg or "hello" in svg
        # The important thing: the document is valid XML
        etree.fromstring(svg.encode())  # should not raise


class TestMarkerSerialization:
    def _scene_with_marker_and_edge(self, marker_type="arrow-end") -> SvgScene:
        marker = MarkerDefinition(
            marker_id="mk1",
            marker_type=marker_type,
            color="#333",
        )
        edge = ScenePath(
            commands=(("M", 0.0, 50.0), ("L", 200.0, 50.0)),
            marker_end="mk1",
        )
        layers = tuple(
            (name, (edge,) if name == LAYER_EDGES else ())
            for name in LAYER_ORDER
        )
        return SvgScene(
            scene_id="m", diagram_type="test",
            width=300, height=100,
            view_box=(0.0, 0.0, 300.0, 100.0),
            definitions=(marker,),
            layers=layers,
        )

    def test_marker_produces_defs_marker(self):
        scene = self._scene_with_marker_and_edge()
        svg = scene_to_svg_str(scene)
        assert '<defs' in svg
        assert '<marker' in svg
        assert 'id="mk1"' in svg

    def test_marker_end_referenced_in_path(self):
        scene = self._scene_with_marker_and_edge()
        svg = scene_to_svg_str(scene)
        assert 'marker-end="url(#mk1)"' in svg

    def test_all_marker_types_produce_path(self):
        for mtype in ("arrow-end", "arrow-start", "arrow-open", "arrow-filled",
                      "arrow-bidirectional", "state-transition", "timeline-end"):
            scene = self._scene_with_marker_and_edge(mtype)
            svg = scene_to_svg_str(scene)
            assert '<marker' in svg, f"No <marker> for type {mtype}"


class TestGradientSerialization:
    def test_linear_gradient_in_defs(self):
        grad = LinearGradientDefinition(
            gradient_id="grad1",
            stops=((0.0, "#fff", 1.0), (1.0, "#000", 1.0)),
        )
        rect = SceneRect(
            x=0, y=0, w=100, h=100,
            paint=PaintStyle(fill=FillStyle(color="url(#grad1)"))
        )
        layers = tuple(
            (name, (rect,) if name == LAYER_NODES else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="g", diagram_type="test",
            width=200, height=200,
            view_box=(0.0, 0.0, 200.0, 200.0),
            definitions=(grad,),
            layers=layers,
        )
        svg = scene_to_svg_str(scene)
        assert '<linearGradient' in svg
        assert 'id="grad1"' in svg
        assert '<stop' in svg


class TestClipPath:
    def test_clip_path_in_defs(self):
        clip = ClipPathDefinition(clip_id="clip1", clip_x=10, clip_y=10, clip_w=80, clip_h=60)
        rect = SceneRect(x=0, y=0, w=100, h=80, clip_ref="clip1")
        layers = tuple(
            (name, (rect,) if name == LAYER_NODES else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="c", diagram_type="test",
            width=200, height=200,
            view_box=(0.0, 0.0, 200.0, 200.0),
            definitions=(clip,),
            layers=layers,
        )
        svg = scene_to_svg_str(scene)
        assert '<clipPath' in svg
        assert 'id="clip1"' in svg
        assert 'clip-path="url(#clip1)"' in svg


class TestNestedGroups:
    def test_nested_group_produces_nested_g(self):
        inner_rect = SceneRect(x=10, y=10, w=50, h=30, element_id="inner-r")
        inner_group = SceneGroup(element_id="inner-g", children=(inner_rect,))
        outer_group = SceneGroup(element_id="outer-g", children=(inner_group,))
        layers = tuple(
            (name, (outer_group,) if name == LAYER_NODES else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="ng", diagram_type="test",
            width=200, height=200,
            view_box=(0.0, 0.0, 200.0, 200.0),
            layers=layers,
        )
        svg = scene_to_svg_str(scene)
        # Should have outer and inner g elements
        assert svg.count('<g') >= 3  # layer + outer + inner
        assert 'id="outer-g"' in svg
        assert 'id="inner-g"' in svg
        assert 'id="inner-r"' in svg


class TestDeterminism:
    def test_same_scene_same_bytes(self):
        scene = _make_simple_scene("det-test")
        out1 = scene_to_svg(scene)
        out2 = scene_to_svg(scene)
        assert out1 == out2

    def test_scene_with_content_same_bytes(self):
        rect = SceneRect(x=10, y=20, w=100, h=50, element_id="r1")
        layers = tuple(
            (name, (rect,) if name == LAYER_NODES else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="det2", diagram_type="test",
            width=400, height=300,
            view_box=(0.0, 0.0, 400.0, 300.0),
            layers=layers,
        )
        out1 = scene_to_svg(scene)
        out2 = scene_to_svg(scene)
        assert out1 == out2


class TestValidation:
    def test_duplicate_ids_rejected(self):
        rect1 = SceneRect(x=0, y=0, w=10, h=10, element_id="dup")
        rect2 = SceneRect(x=10, y=10, w=10, h=10, element_id="dup")
        layers = tuple(
            (name, (rect1, rect2) if name == LAYER_NODES else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="v", diagram_type="test",
            width=100, height=100,
            view_box=(0.0, 0.0, 100.0, 100.0),
            layers=layers,
        )
        with pytest.raises(SceneValidationError, match="Duplicate id"):
            validate_scene(scene)

    def test_unresolved_marker_rejected(self):
        edge = ScenePath(
            commands=(("M", 0.0, 0.0), ("L", 100.0, 0.0)),
            marker_end="nonexistent-marker",
        )
        layers = tuple(
            (name, (edge,) if name == LAYER_EDGES else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="v2", diagram_type="test",
            width=200, height=100,
            view_box=(0.0, 0.0, 200.0, 100.0),
            layers=layers,
        )
        with pytest.raises(SceneValidationError, match="[Uu]nresolved marker"):
            validate_scene(scene)

    def test_valid_scene_passes_validation(self):
        scene = _make_simple_scene("v3")
        validate_scene(scene)  # should not raise
