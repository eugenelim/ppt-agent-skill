"""Tests for the SvgScene immutable IR (scene.py)."""
import math
import pytest

from scripts.mermaid_render.scene import (
    SvgScene, SceneGroup, SceneRect, SceneRoundedRect, SceneCircle, SceneEllipse,
    SceneLine, ScenePolyline, ScenePolygon, ScenePath, SceneText, SceneTextLine,
    SceneImage, PaintStyle, StrokeStyle, FillStyle,
    MarkerDefinition, LinearGradientDefinition, RadialGradientDefinition,
    ClipPathDefinition, AccessibilityMetadata, RendererCapability,
    LAYER_ORDER, LAYER_BACKGROUND, LAYER_NODES, make_scene_id,
)


class TestPrimitiveImmutability:
    def test_rect_is_frozen(self):
        r = SceneRect(x=10, y=20, w=100, h=50)
        with pytest.raises((AttributeError, TypeError)):
            r.x = 5  # type: ignore[misc]

    def test_circle_is_frozen(self):
        c = SceneCircle(cx=50, cy=50, r=20)
        with pytest.raises((AttributeError, TypeError)):
            c.r = 10  # type: ignore[misc]

    def test_path_is_frozen(self):
        p = ScenePath(commands=(("M", 0.0, 0.0), ("L", 10.0, 10.0)))
        with pytest.raises((AttributeError, TypeError)):
            p.commands = ()  # type: ignore[misc]

    def test_svg_scene_is_frozen(self):
        s = SvgScene.make_empty("s1", "flowchart", 100, 100)
        with pytest.raises((AttributeError, TypeError)):
            s.width = 200  # type: ignore[misc]


class TestGeometryValidation:
    def test_rect_rejects_nan(self):
        with pytest.raises(ValueError, match="finite"):
            SceneRect(x=float("nan"), y=0, w=100, h=50)

    def test_rect_rejects_inf(self):
        with pytest.raises(ValueError, match="finite"):
            SceneRect(x=float("inf"), y=0, w=100, h=50)

    def test_circle_rejects_nan_r(self):
        with pytest.raises(ValueError, match="finite"):
            SceneCircle(cx=0, cy=0, r=float("nan"))

    def test_path_rejects_nan_in_command(self):
        with pytest.raises(ValueError, match="non-finite"):
            ScenePath(commands=(("M", float("nan"), 0.0),))

    def test_path_rejects_unknown_command(self):
        with pytest.raises(ValueError, match="unsupported letter"):
            ScenePath(commands=(("X", 0.0, 0.0),))

    def test_scene_rejects_zero_viewbox_width(self):
        with pytest.raises(ValueError):
            SvgScene(
                scene_id="s", diagram_type="test",
                width=100, height=100,
                view_box=(0.0, 0.0, 0.0, 100.0),
            )

    def test_scene_rejects_nonfinite_width(self):
        with pytest.raises(ValueError):
            SvgScene(
                scene_id="s", diagram_type="test",
                width=float("nan"), height=100,
                view_box=(0.0, 0.0, 100.0, 100.0),
            )

    def test_stroke_style_rejects_negative_width(self):
        with pytest.raises(ValueError):
            StrokeStyle(width=-1.0)

    def test_fill_style_rejects_bad_opacity(self):
        with pytest.raises(ValueError):
            FillStyle(opacity=1.5)

    def test_scene_image_rejects_non_data_uri(self):
        with pytest.raises(ValueError, match="data:"):
            SceneImage(href="https://example.com/img.png", x=0, y=0, w=10, h=10)

    def test_polyline_rejects_nan_point(self):
        with pytest.raises(ValueError, match="finite"):
            ScenePolyline(points=((float("nan"), 0.0),))


class TestSvgSceneStructure:
    def test_make_empty_has_all_layers(self):
        scene = SvgScene.make_empty("s1", "flowchart", 800, 600)
        layer_names = [name for name, _ in scene.layers]
        assert set(LAYER_ORDER).issubset(set(layer_names))

    def test_make_empty_layers_are_empty_tuples(self):
        scene = SvgScene.make_empty("s1", "flowchart", 800, 600)
        for _, elems in scene.layers:
            assert elems == ()

    def test_get_layer_returns_correct(self):
        rect = SceneRect(x=0, y=0, w=10, h=10)
        layers = tuple(
            (name, (rect,) if name == LAYER_NODES else ())
            for name in LAYER_ORDER
        )
        scene = SvgScene(
            scene_id="s1", diagram_type="test",
            width=200, height=200,
            view_box=(0.0, 0.0, 200.0, 200.0),
            layers=layers,
        )
        nodes = scene.get_layer(LAYER_NODES)
        assert len(nodes) == 1
        assert nodes[0] is rect

    def test_get_layer_missing_returns_empty(self):
        scene = SvgScene.make_empty("s1", "test", 100, 100)
        assert scene.get_layer("nonexistent") == ()

    def test_scene_id_is_stored(self):
        scene = SvgScene.make_empty("my-id", "test", 100, 100)
        assert scene.scene_id == "my-id"

    def test_make_scene_id_deterministic(self):
        id1 = make_scene_id("flowchart", 12345)
        id2 = make_scene_id("flowchart", 12345)
        assert id1 == id2

    def test_make_scene_id_differs_by_type(self):
        id1 = make_scene_id("flowchart", 12345)
        id2 = make_scene_id("timeline", 12345)
        assert id1 != id2


class TestSceneElements:
    def test_scene_rect_defaults(self):
        r = SceneRect()
        assert r.x == 0.0 and r.y == 0.0 and r.w == 0.0 and r.h == 0.0
        assert r.element_id == ""
        assert r.css_classes == ()

    def test_scene_text_lines_are_immutable(self):
        line = SceneTextLine(text="hello", x=10, y=20)
        t = SceneText(lines=(line,))
        with pytest.raises((AttributeError, TypeError)):
            t.lines = ()  # type: ignore[misc]

    def test_scene_group_has_children(self):
        rect = SceneRect(x=0, y=0, w=10, h=10)
        group = SceneGroup(children=(rect,))
        assert len(group.children) == 1

    def test_renderer_capability_fields(self):
        cap = RendererCapability(
            diagram_type="flowchart",
            native_scene=True,
            semantic_parity_level="mechanical",
        )
        assert cap.diagram_type == "flowchart"
        assert cap.native_scene is True

    def test_paint_style_defaults(self):
        ps = PaintStyle()
        assert ps.fill.color == "none"
        assert ps.stroke is None
        assert ps.opacity == 1.0

    def test_accessibility_metadata_defaults(self):
        am = AccessibilityMetadata()
        assert am.title == ""
        assert am.role == "graphics-document document"
