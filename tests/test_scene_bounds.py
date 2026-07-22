"""Tests for mermaid_render.scene_bounds — visible-bounds and validation."""
import pytest

from scripts.mermaid_render.scene_bounds import (
    _parse_translate,
    element_visible_bounds,
    scene_visible_bounds,
    validate_scene,
)
from scripts.mermaid_render.scene import (
    SceneCircle,
    SceneEllipse,
    SceneGroup,
    SceneImage,
    SceneLine,
    ScenePath,
    ScenePolygon,
    ScenePolyline,
    SceneRect,
    SceneRoundedRect,
    SceneText,
    SceneTextLine,
    SvgScene,
)
from scripts.mermaid_render.layout._geometry import Rect


# ── Helpers ───────────────────────────────────────────────────────────────────

def _scene(*elements, width=200, height=100):
    return SvgScene(
        scene_id="test",
        diagram_type="flowchart",
        width=float(width),
        height=float(height),
        view_box=(0.0, 0.0, float(width), float(height)),
        layers=(("nodes", tuple(elements)),),
    )


# ── _parse_translate ──────────────────────────────────────────────────────────

class TestParseTranslate:
    def test_comma_separated(self):
        assert _parse_translate("translate(10, 20)") == (10.0, 20.0)

    def test_space_separated(self):
        assert _parse_translate("translate(10 20)") == (10.0, 20.0)

    def test_single_argument_zero_y(self):
        assert _parse_translate("translate(5)") == (5.0, 0.0)

    def test_empty_string(self):
        assert _parse_translate("") == (0.0, 0.0)

    def test_unrecognised_transform(self):
        assert _parse_translate("rotate(45)") == (0.0, 0.0)

    def test_scale_not_parsed(self):
        assert _parse_translate("scale(2)") == (0.0, 0.0)

    def test_negative_values(self):
        dx, dy = _parse_translate("translate(-10, -5)")
        assert dx == -10.0
        assert dy == -5.0


# ── element_visible_bounds ────────────────────────────────────────────────────

class TestRectBounds:
    def test_basic_rect(self):
        assert element_visible_bounds(SceneRect(x=10, y=20, w=50, h=30)) == Rect(10, 20, 50, 30)

    def test_rect_with_translate(self):
        r = element_visible_bounds(SceneRect(x=0, y=0, w=10, h=10, transform="translate(5, 3)"))
        assert r == Rect(5, 3, 10, 10)

    def test_rounded_rect(self):
        r = element_visible_bounds(SceneRoundedRect(x=5, y=5, w=40, h=20, rx=5, ry=5))
        assert r == Rect(5, 5, 40, 20)

    def test_zero_size_rect_returns_zero_rect(self):
        r = element_visible_bounds(SceneRect(x=0, y=0, w=0, h=0))
        assert r == Rect(0, 0, 0, 0)


class TestCircleAndEllipseBounds:
    def test_circle(self):
        r = element_visible_bounds(SceneCircle(cx=50, cy=50, r=20))
        assert r == Rect(30, 30, 40, 40)

    def test_zero_radius_circle_is_none(self):
        assert element_visible_bounds(SceneCircle(cx=10, cy=10, r=0)) is None

    def test_ellipse(self):
        r = element_visible_bounds(SceneEllipse(cx=0, cy=0, rx=10, ry=5))
        assert r == Rect(-10, -5, 20, 10)

    def test_zero_rx_ellipse_is_none(self):
        assert element_visible_bounds(SceneEllipse(cx=0, cy=0, rx=0, ry=5)) is None


class TestLineBounds:
    def test_diagonal_line(self):
        r = element_visible_bounds(SceneLine(x1=10, y1=20, x2=30, y2=40))
        assert r == Rect(10, 20, 20, 20)

    def test_horizontal_line_zero_height(self):
        r = element_visible_bounds(SceneLine(x1=0, y1=10, x2=50, y2=10))
        assert r is not None
        assert r.w == 50
        assert r.h == 0

    def test_vertical_line_zero_width(self):
        r = element_visible_bounds(SceneLine(x1=10, y1=0, x2=10, y2=30))
        assert r is not None
        assert r.w == 0
        assert r.h == 30


class TestPolylineBounds:
    def test_polyline(self):
        r = element_visible_bounds(ScenePolyline(points=((0, 0), (10, 5), (20, 0))))
        assert r == Rect(0, 0, 20, 5)

    def test_empty_polyline_is_none(self):
        assert element_visible_bounds(ScenePolyline(points=())) is None

    def test_polygon(self):
        r = element_visible_bounds(ScenePolygon(points=((0, 0), (10, 0), (5, 10))))
        assert r == Rect(0, 0, 10, 10)


class TestPathBounds:
    def test_moveto_lineto(self):
        path = ScenePath(commands=(("M", 0, 0), ("L", 100, 50)))
        assert element_visible_bounds(path) == Rect(0, 0, 100, 50)

    def test_cubic_bezier_includes_control_points(self):
        # C x1,y1,x2,y2,x,y — control points push the conservative bound outward
        path = ScenePath(commands=(("M", 0, 0), ("C", 20, 100, 80, 100, 100, 0)))
        r = element_visible_bounds(path)
        assert r is not None
        assert r.y <= 0
        assert r.y1 >= 100

    def test_arc_uses_endpoint_only(self):
        path = ScenePath(commands=(("M", 0, 0), ("A", 30, 30, 0, 0, 1, 60, 0), ("Z",)))
        r = element_visible_bounds(path)
        assert r is not None
        assert r.w == 60

    def test_empty_path_is_none(self):
        assert element_visible_bounds(ScenePath(commands=())) is None

    def test_closepath_only_is_none(self):
        assert element_visible_bounds(ScenePath(commands=(("Z",),))) is None


class TestTextBounds:
    def test_single_line_has_bounds(self):
        line = SceneTextLine(text="Hello", x=50, y=50, font_size=12)
        text = SceneText(lines=(line,))
        r = element_visible_bounds(text)
        assert r is not None
        assert r.w > 0
        assert r.h > 0

    def test_empty_text_is_none(self):
        assert element_visible_bounds(SceneText(lines=())) is None

    def test_empty_string_lines_is_none(self):
        line = SceneTextLine(text="", x=0, y=0)
        assert element_visible_bounds(SceneText(lines=(line,))) is None

    def test_start_anchor_x_is_left_edge(self):
        line = SceneTextLine(text="X" * 10, x=100, y=50, font_size=10)
        text_start = SceneText(lines=(line,), text_anchor="start")
        text_middle = SceneText(lines=(line,), text_anchor="middle")
        r_start = element_visible_bounds(text_start)
        r_middle = element_visible_bounds(text_middle)
        assert r_start is not None
        assert r_middle is not None
        # start-anchored text begins at x=100; middle-anchored is centred → left edge < 100
        assert r_start.x == pytest.approx(100.0)
        assert r_middle.x < 100.0

    def test_multiple_lines_unioned(self):
        lines = (
            SceneTextLine(text="Line 1", x=50, y=20, font_size=10),
            SceneTextLine(text="Line 2", x=50, y=40, font_size=10),
        )
        r = element_visible_bounds(SceneText(lines=lines))
        assert r is not None
        assert r.y <= 10    # top of first line
        assert r.y1 >= 40   # bottom of second line


class TestImageBounds:
    def test_image_bounds(self):
        img = SceneImage(href="data:image/png;base64,AA==", x=10, y=20, w=100, h=80)
        assert element_visible_bounds(img) == Rect(10, 20, 100, 80)

    def test_image_no_href_is_none(self):
        assert element_visible_bounds(SceneImage()) is None


class TestGroupBounds:
    def test_union_of_children(self):
        grp = SceneGroup(children=(
            SceneRect(x=0, y=0, w=10, h=10),
            SceneRect(x=20, y=20, w=10, h=10),
        ))
        assert element_visible_bounds(grp) == Rect(0, 0, 30, 30)

    def test_group_with_translate_shifts_result(self):
        grp = SceneGroup(
            transform="translate(100, 200)",
            children=(SceneRect(x=0, y=0, w=10, h=10),),
        )
        assert element_visible_bounds(grp) == Rect(100, 200, 10, 10)

    def test_empty_group_is_none(self):
        assert element_visible_bounds(SceneGroup()) is None

    def test_nested_group_propagates_transforms(self):
        inner = SceneGroup(
            transform="translate(10, 10)",
            children=(SceneRect(x=0, y=0, w=5, h=5),),
        )
        outer = SceneGroup(
            transform="translate(20, 20)",
            children=(inner,),
        )
        r = element_visible_bounds(outer)
        # inner child at local (0,0), shifted by inner (10,10) = (10,10)
        # then outer adds (20,20) = (30,30)
        assert r == Rect(30, 30, 5, 5)


# ── scene_visible_bounds ──────────────────────────────────────────────────────

class TestSceneVisibleBounds:
    def test_single_element(self):
        scene = _scene(SceneRect(x=10, y=20, w=50, h=30))
        assert scene_visible_bounds(scene) == Rect(10, 20, 50, 30)

    def test_multiple_elements_union(self):
        scene = _scene(
            SceneRect(x=0, y=0, w=10, h=10),
            SceneRect(x=50, y=50, w=10, h=10),
        )
        assert scene_visible_bounds(scene) == Rect(0, 0, 60, 60)

    def test_empty_scene_is_none(self):
        assert scene_visible_bounds(_scene()) is None

    def test_spans_multiple_layers(self):
        scene = SvgScene(
            scene_id="test",
            diagram_type="flowchart",
            width=200.0,
            height=100.0,
            view_box=(0.0, 0.0, 200.0, 100.0),
            layers=(
                ("nodes", (SceneRect(x=0, y=0, w=10, h=10),)),
                ("edges", (SceneLine(x1=100, y1=100, x2=200, y2=200),)),
            ),
        )
        b = scene_visible_bounds(scene)
        assert b is not None
        assert b.x == 0
        assert b.y == 0
        assert b.x1 == 200
        assert b.y1 == 200


# ── validate_scene ────────────────────────────────────────────────────────────

class TestValidateScene:
    def test_clean_scene_returns_no_errors(self):
        scene = _scene(SceneRect(element_id="r1", x=10, y=10, w=50, h=30))
        assert validate_scene(scene) == []

    def test_duplicate_element_id_detected(self):
        scene = _scene(
            SceneRect(element_id="dup", x=0, y=0, w=10, h=10),
            SceneRect(element_id="dup", x=20, y=0, w=10, h=10),
        )
        errs = validate_scene(scene)
        assert any("dup" in e for e in errs)

    def test_duplicate_in_nested_group(self):
        scene = _scene(
            SceneRect(element_id="shared", x=0, y=0, w=10, h=10),
            SceneGroup(element_id="grp", children=(
                SceneRect(element_id="shared", x=20, y=0, w=10, h=10),
            )),
        )
        errs = validate_scene(scene)
        assert any("shared" in e for e in errs)

    def test_blank_element_ids_not_flagged(self):
        # Unnamed elements should not be treated as duplicate
        scene = _scene(
            SceneRect(x=0, y=0, w=10, h=10),
            SceneRect(x=20, y=0, w=10, h=10),
        )
        assert validate_scene(scene) == []

    def test_negative_rect_width(self):
        scene = _scene(SceneRect(x=0, y=0, w=-10, h=10))
        errs = validate_scene(scene)
        assert any("Negative" in e and "width" in e.lower() for e in errs)

    def test_negative_rect_height(self):
        scene = _scene(SceneRect(x=0, y=0, w=10, h=-5))
        errs = validate_scene(scene)
        assert any("Negative" in e and "height" in e.lower() for e in errs)

    def test_negative_circle_radius(self):
        scene = _scene(SceneCircle(cx=0, cy=0, r=-1))
        errs = validate_scene(scene)
        assert any("radius" in e.lower() for e in errs)

    def test_negative_ellipse_rx(self):
        scene = _scene(SceneEllipse(cx=0, cy=0, rx=-5, ry=10))
        errs = validate_scene(scene)
        assert any("rx" in e for e in errs)

    def test_negative_geometry_in_group(self):
        scene = _scene(SceneGroup(children=(SceneRect(x=0, y=0, w=-1, h=5),)))
        errs = validate_scene(scene)
        assert any("Negative" in e for e in errs)


# ── validate() public API wires through scene_bounds for graph directives ─────

class TestPublicValidateUsesSceneBounds:
    def test_valid_flowchart_returns_geometry_pass(self):
        import sys; sys.path.insert(0, "scripts")
        from mermaid_render import validate
        r = validate("flowchart LR\n  A --> B --> C")
        assert r.geometry == "pass", (
            f"Expected geometry='pass' for valid flowchart; got {r.geometry!r}. "
            "validate() may not be wiring through scene_bounds."
        )

    def test_valid_graph_returns_geometry_pass(self):
        from mermaid_render import validate
        r = validate("graph TD\n  X --> Y")
        assert r.geometry == "pass"

    def test_timeline_returns_geometry_unvalidated(self):
        from mermaid_render import validate
        r = validate("timeline\n  title T\n  section A\n    E1: desc")
        assert r.geometry == "unvalidated"
