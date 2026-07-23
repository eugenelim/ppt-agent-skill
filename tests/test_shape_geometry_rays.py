"""Ray intersection and structural tests for ShapeGeometry implementations.

AC-4:  outline_path() returns polygon vertices / None for curved shapes.
AC-5:  boundary_intersection for hexagon/trapezoid/flag uses polygon math.
AC-8:  Flag has SVG polygon border, no CSS rect border.
AC-9:  Subroutine inner lines stay inside the outer rect (y=2 to y=node_h-2).
AC-10: DiamondGeometry.measure() uses sum-of-dimensions formula.
AC-11: DoubleCircleGeometry.measure() includes the ring gap.
AC-12: 8 angles × every polygon shape; intersection lies on the outline (≤2px).
AC-13: Diamond outer div has no CSS border property in flowchart-diamond-clipping.
"""
import math
import re
import pytest

from scripts.mermaid_render.layout.shape_geometry import (
    SHAPE_REGISTRY,
    DiamondGeometry,
    DoubleCircleGeometry,
)
from scripts.mermaid_render.layout._strategies import _dispatch
from scripts.mermaid_render.layout._renderer import _CLIP_PATH_CSS


# ── helpers ──────────────────────────────────────────────────────────────────

def _on_segment(ax, ay, bx, by, px, py, tol=2.0):
    """Return True if (px,py) lies on segment (ax,ay)-(bx,by) within tol px."""
    ex, ey = bx - ax, by - ay
    edge_len = math.hypot(ex, ey)
    if edge_len < 1e-9:
        return math.hypot(px - ax, py - ay) < tol
    t = ((px - ax) * ex + (py - ay) * ey) / (edge_len ** 2)
    if t < -tol / edge_len or t > 1 + tol / edge_len:
        return False
    foot_x = ax + t * ex
    foot_y = ay + t * ey
    return math.hypot(px - foot_x, py - foot_y) < tol


def _outline_verts_canvas(shape_name, w, h, cx, cy):
    """Return polygon vertices in canvas coords (origin = cx,cy is shape center)."""
    local = SHAPE_REGISTRY[shape_name].outline_path(w, h)
    if local is None:
        return None
    hw, hh = w / 2.0, h / 2.0
    return [(cx - hw + lx, cy - hh + ly) for lx, ly in local]


# Eight outward directions at 45° intervals
_EIGHT_DIRS = [
    (1, 0), (1, 1), (0, 1), (-1, 1),
    (-1, 0), (-1, -1), (0, -1), (1, -1),
]

# Polygon shapes that have an outline_path
# Note: cylinder is excluded — it uses silhouette boundary intersection, not polygon math
_POLYGON_SHAPES = [
    "rect",
    "diamond",
    "hexagon",
    "trapezoid",
    "trapezoid-alt",
    "flag",
    "subroutine",
    "bar",
]

# Polygon shapes that should have no CSS border on the outer div (SVG border only)
_NO_CSS_BORDER_SHAPES = ["diamond", "hexagon", "trapezoid", "trapezoid-alt", "flag"]


# ── AC-10: DiamondGeometry.measure() ─────────────────────────────────────────

def test_diamond_measure_sum_formula():
    """DiamondGeometry.measure() uses label_w + label_h + padding sum formula."""
    geom = DiamondGeometry()
    from scripts.mermaid_render.layout._constants import DIAMOND_MIN
    label_w, label_h, px, py = 60.0, 20.0, 12.0, 6.0
    w, h = geom.measure(label_w, label_h, px, py)
    expected = float(max(DIAMOND_MIN, math.ceil(label_w + label_h + 2 * px + py)))
    assert w == expected, f"diamond measure width: got {w}, expected {expected}"
    assert h == expected, "diamond must be square"


def test_diamond_measure_square():
    """DiamondGeometry always returns equal width and height."""
    geom = DiamondGeometry()
    w, h = geom.measure(80.0, 40.0, 12.0, 6.0)
    assert w == h, "diamond width must equal height"


# ── AC-11: DoubleCircleGeometry.measure() ────────────────────────────────────

def test_doublecircle_measure_includes_ring_gap():
    """DoubleCircleGeometry.measure() must be strictly larger than CircleGeometry.measure()."""
    dc = DoubleCircleGeometry()
    c = SHAPE_REGISTRY["circle"]
    label_w, label_h, px, py = 50.0, 18.0, 12.0, 6.0
    dw, dh = dc.measure(label_w, label_h, px, py)
    cw, ch = c.measure(label_w, label_h, px, py)
    assert dw > cw, f"doublecircle ({dw}) must be wider than circle ({cw})"
    assert dw - cw == 2 * dc._RING_GAP, (
        f"ring gap wrong: expected {2 * dc._RING_GAP} extra, got {dw - cw}"
    )


def test_doublecircle_measure_square():
    """DoubleCircleGeometry always returns equal width and height."""
    geom = DoubleCircleGeometry()
    w, h = geom.measure(60.0, 20.0, 12.0, 6.0)
    assert w == h, "doublecircle width must equal height"


# ── AC-4: outline_path() ─────────────────────────────────────────────────────

@pytest.mark.parametrize("shape_name", _POLYGON_SHAPES)
def test_outline_path_closed(shape_name):
    """outline_path returns ≥ 3 vertices for polygon shapes."""
    verts = SHAPE_REGISTRY[shape_name].outline_path(100.0, 60.0)
    if verts is None:
        pytest.skip(f"{shape_name} is a curved shape")
    assert len(verts) >= 3, f"{shape_name} outline has fewer than 3 vertices"


@pytest.mark.parametrize("shape_name", ["circle", "doublecircle", "stadium", "round"])
def test_curved_shapes_outline_path_none(shape_name):
    """Curved shapes return None for outline_path (no polygon approximation)."""
    verts = SHAPE_REGISTRY[shape_name].outline_path(100.0, 60.0)
    assert verts is None, f"{shape_name} should return None from outline_path"


# ── AC-5 / consistency: outline_path matches _CLIP_PATH_CSS percentages ──────

_CLIP_PATH_SHAPES = list(_CLIP_PATH_CSS.keys())


def _clip_pct_to_verts(shape_name, w, h):
    """Parse _CLIP_PATH_CSS polygon percentages into (x,y) tuples."""
    css = _CLIP_PATH_CSS[shape_name]
    raw = re.search(r'polygon\(([^)]+)\)', css).group(1)
    verts = []
    for pair in raw.split(","):
        pair = pair.strip()
        xs, ys = pair.split()
        x = float(xs.rstrip("%")) / 100.0 * w
        y = float(ys.rstrip("%")) / 100.0 * h
        verts.append((x, y))
    return verts


@pytest.mark.parametrize("shape_name", _CLIP_PATH_SHAPES)
def test_outline_path_matches_clip_path_css(shape_name):
    """outline_path vertices must match _CLIP_PATH_CSS polygon percentages (±1 px)."""
    w, h = 120.0, 60.0
    expected = _clip_pct_to_verts(shape_name, w, h)
    actual = SHAPE_REGISTRY[shape_name].outline_path(w, h)
    assert actual is not None, f"{shape_name} outline_path returned None"
    assert len(actual) == len(expected), (
        f"{shape_name}: outline_path has {len(actual)} verts, clip-path has {len(expected)}"
    )
    for i, ((ax, ay), (ex, ey)) in enumerate(zip(actual, expected)):
        assert abs(ax - ex) < 1.5 and abs(ay - ey) < 1.5, (
            f"{shape_name} vertex {i}: outline_path=({ax:.1f},{ay:.1f}) "
            f"vs clip-path=({ex:.1f},{ey:.1f})"
        )


# ── AC-12: Ray tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("shape_name", _POLYGON_SHAPES)
@pytest.mark.parametrize("dx,dy", _EIGHT_DIRS)
def test_ray_hits_outline(shape_name, dx, dy):
    """boundary_intersection result lies on the polygon outline within 2 px."""
    geom = SHAPE_REGISTRY[shape_name]
    w, h = 100.0, 60.0
    if shape_name in ("diamond",):
        w = h = 100.0
    cx, cy = w / 2.0, h / 2.0

    verts_canvas = _outline_verts_canvas(shape_name, w, h, cx, cy)
    if verts_canvas is None:
        pytest.skip(f"{shape_name} has no polygon outline_path")

    px, py = geom.boundary_intersection(cx, cy, w, h, float(dx), float(dy))

    n = len(verts_canvas)
    on_any_edge = any(
        _on_segment(verts_canvas[i][0], verts_canvas[i][1],
                    verts_canvas[(i + 1) % n][0], verts_canvas[(i + 1) % n][1],
                    px, py, tol=2.0)
        for i in range(n)
    )

    assert on_any_edge, (
        f"{shape_name} boundary_intersection({dx},{dy}) → ({px:.2f},{py:.2f}) "
        f"not on any polygon edge (verts={verts_canvas})"
    )


@pytest.mark.parametrize("shape_name", _POLYGON_SHAPES)
@pytest.mark.parametrize("dx,dy", _EIGHT_DIRS)
def test_ray_outward(shape_name, dx, dy):
    """Intersection is always outward from the center (dot product with direction ≥ 0)."""
    geom = SHAPE_REGISTRY[shape_name]
    w, h = 100.0, 60.0
    if shape_name in ("diamond",):
        w = h = 100.0
    cx, cy = w / 2.0, h / 2.0

    px, py = geom.boundary_intersection(cx, cy, w, h, float(dx), float(dy))
    dot = (px - cx) * dx + (py - cy) * dy
    assert dot >= -1.0, (
        f"{shape_name} boundary_intersection({dx},{dy}) → ({px:.2f},{py:.2f}) "
        f"is behind the center (dot={dot:.2f})"
    )


# ── AC-8 / AC-3: No CSS border on polygon outer divs ─────────────────────────

def _render_fixture(filename: str) -> str:
    import os
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    with open(fixture) as f:
        src = f.read()
    return _dispatch(src, None, 600)


def _get_outer_div_styles(html: str, shape_name: str) -> list[str]:
    """Extract style attribute values from outer divs with class node-{shape_name}."""
    return re.findall(
        rf'class="node node-{re.escape(shape_name)}[^"]*"[^>]*style="([^"]*)"',
        html,
    )


def _assert_no_visible_border(style: str, shape_name: str) -> None:
    """Assert style contains no CSS border that would show a rectangular artifact."""
    border_match = re.search(r'\bborder\s*:', style)
    if border_match:
        border_val = style[border_match.end():].strip().split(";")[0].strip()
        assert border_val in ("none", "0", "0px"), (
            f"{shape_name} outer container has unexpected CSS border: "
            f"'border:{border_val}'"
        )


@pytest.mark.parametrize("shape_name", _NO_CSS_BORDER_SHAPES)
def test_no_rect_border_on_polygon_nodes(shape_name):
    """Polygon nodes must have no CSS border on the outer div (SVG polygon border only)."""
    html = _render_fixture("flowchart-all-shapes.mmd")
    containers = _get_outer_div_styles(html, shape_name)
    assert containers, f"No {shape_name} node containers found in rendered output"
    for style in containers:
        _assert_no_visible_border(style, shape_name)


def test_diamond_no_rect_border_in_clipping_fixture():
    """Diamond nodes in flowchart-diamond-clipping must have no CSS border on outer div."""
    html = _render_fixture("flowchart-diamond-clipping.mmd")
    containers = _get_outer_div_styles(html, "diamond")
    assert containers, "No diamond node containers found in flowchart-diamond-clipping output"
    for style in containers:
        _assert_no_visible_border(style, "diamond")


def test_diamond_svg_polygon_border():
    """Diamond nodes must have an SVG polygon border in the output."""
    html = _render_fixture("flowchart-diamond-clipping.mmd")
    assert "<polygon" in html, "No SVG polygon found in diamond-clipping output"
    assert "node-diamond" in html, "No diamond node class found in rendered output"


def test_flag_svg_polygon_border():
    """Flag node must have an SVG polygon border in the output."""
    html = _render_fixture("flowchart-all-shapes.mmd")
    assert "node-flag" in html, "No flag node found in all-shapes output"
    # The flag SVG polygon is output as part of shape_overlay
    assert "<polygon" in html, "No SVG polygon found — flag border polygon missing"


# ── AC-9: Subroutine inner lines inside rect ──────────────────────────────────

def test_subroutine_inner_lines_inside_border():
    """Subroutine inner vertical lines must start at y=2 (inside the outer rect border)."""
    html = _render_fixture("flowchart-all-shapes.mmd")

    # Extract only the subroutine node HTML
    subroutine_match = re.search(
        r'class="node node-subroutine[^"]*"[^>]*>(.*?)</div>',
        html,
        re.DOTALL,
    )
    assert subroutine_match, "No subroutine node found in rendered output"
    subroutine_html = subroutine_match.group(0)

    # Inner lines must NOT start at y1="0"
    assert 'y1="0"' not in subroutine_html, (
        "Subroutine inner lines start at y=0 — should start at y=2"
    )
    # Inner lines must start at y1="2"
    assert 'y1="2"' in subroutine_html, (
        "Subroutine inner lines should start at y=2 (inside outer border)"
    )


# ── AC-6/7: Routing clipping fires for polygon shapes ─────────────────────────

def _parse_path_first_point(html: str) -> tuple[float, float] | None:
    """Parse (x, y) of the first M command in any <path d="..."> SVG element."""
    m = re.search(r'<path[^>]*\sd="M\s*([\d.]+)[ ,]([\d.]+)', html)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def _parse_path_last_point(html: str) -> tuple[float, float] | None:
    """Parse (x, y) of the last L or M coordinate in the edge path."""
    all_m = re.findall(r'<path[^>]*\sd="([^"]+)"', html)
    if not all_m:
        return None
    d = all_m[-1] if all_m else ""
    coords = re.findall(r'[LM]\s*([\d.]+)[ ,]([\d.]+)', d)
    if not coords:
        return None
    return float(coords[-1][0]), float(coords[-1][1])


def _node_canvas_bounds(html: str, shape: str) -> tuple[float, float, float, float] | None:
    """Return (x, y, w, h) canvas bounds for the first node of the given shape."""
    m = re.search(
        rf'data-shape="{re.escape(shape)}"[^>]*style="[^"]*left:(\d+)px[^"]*top:(\d+)px[^"]*width:(\d+)px[^"]*height:(\d+)px',
        html,
    )
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    return None


def test_polygon_routing_clip_tb_endpoint_on_outline():
    """TB routing: diamond source endpoint lies on the diamond polygon outline."""
    src = "flowchart TB\n    A{Decision}\n    B[Action]\n    A-->B\n"
    html = _dispatch(src, None, 400)

    first_pt = _parse_path_first_point(html)
    assert first_pt is not None, "No edge path found in TB rendered output"
    px, py = first_pt

    bounds = _node_canvas_bounds(html, "diamond")
    assert bounds is not None, "Diamond node not found in rendered output"
    nx, ny, nw, nh = bounds
    cx, cy = nx + nw / 2.0, ny + nh / 2.0

    verts = SHAPE_REGISTRY["diamond"].outline_path(nw, nh)
    canvas_verts = [(nx + lx, ny + ly) for lx, ly in verts]

    n = len(canvas_verts)
    on_outline = any(
        _on_segment(canvas_verts[i][0], canvas_verts[i][1],
                    canvas_verts[(i + 1) % n][0], canvas_verts[(i + 1) % n][1],
                    px, py, tol=3.0)
        for i in range(n)
    )
    assert on_outline, (
        f"TB diamond source endpoint ({px:.1f},{py:.1f}) not on diamond outline "
        f"(center=({cx:.1f},{cy:.1f}), verts={canvas_verts})"
    )


def test_polygon_routing_clip_lr_endpoint_on_outline():
    """LR routing: diamond source endpoint lies on the diamond polygon outline."""
    src = "flowchart LR\n    A{Decision}\n    B[Action]\n    A-->B\n"
    html = _dispatch(src, None, 400)

    first_pt = _parse_path_first_point(html)
    assert first_pt is not None, "No edge path found in LR rendered output"
    px, py = first_pt

    bounds = _node_canvas_bounds(html, "diamond")
    assert bounds is not None, "Diamond node not found in rendered output"
    nx, ny, nw, nh = bounds
    cx, cy = nx + nw / 2.0, ny + nh / 2.0

    verts = SHAPE_REGISTRY["diamond"].outline_path(nw, nh)
    canvas_verts = [(nx + lx, ny + ly) for lx, ly in verts]

    n = len(canvas_verts)
    on_outline = any(
        _on_segment(canvas_verts[i][0], canvas_verts[i][1],
                    canvas_verts[(i + 1) % n][0], canvas_verts[(i + 1) % n][1],
                    px, py, tol=3.0)
        for i in range(n)
    )
    assert on_outline, (
        f"LR diamond source endpoint ({px:.1f},{py:.1f}) not on diamond outline "
        f"(center=({cx:.1f},{cy:.1f}), verts={canvas_verts})"
    )


# ── AC-N: paint_svg / paint_html painter tests ───────────────────────────────

_ALL_SHAPES = list(SHAPE_REGISTRY.keys())

_COMMON_PAINT_KW = {
    "inner_html": "<span>Label</span>",
    "border_css": "",
    "shape_css": "",
    "bg_css": "background:#fff;",
    "box_shadow": "0 1px 2px rgba(0,0,0,0.06)",
    "data_attrs_html": 'class="node node-test"',
    "accent": "#60a5fa",
}


@pytest.mark.parametrize("shape_name", _ALL_SHAPES)
def test_paint_svg_not_none(shape_name):
    """paint_svg() must return a non-empty string for every registered shape."""
    geom = SHAPE_REGISTRY[shape_name]
    result = geom.paint_svg(10.0, 20.0, 120.0, 60.0, fill="#eee", stroke="#333", stroke_w=1.5)
    assert result is not None, f"{shape_name}: paint_svg returned None"
    assert isinstance(result, str), f"{shape_name}: paint_svg returned non-string"
    assert len(result) > 0, f"{shape_name}: paint_svg returned empty string"


@pytest.mark.parametrize("shape_name", _ALL_SHAPES)
def test_paint_html_not_none(shape_name):
    """paint_html() must return a non-empty HTML string for every registered shape."""
    geom = SHAPE_REGISTRY[shape_name]
    kw = dict(_COMMON_PAINT_KW)
    if shape_name == "bar":
        kw["bar_label_html"] = "Sync"
    result = geom.paint_html(10.0, 20.0, 120.0, 60.0, **kw)
    assert result is not None, f"{shape_name}: paint_html returned None"
    assert isinstance(result, str), f"{shape_name}: paint_html returned non-string"
    assert "<div" in result, f"{shape_name}: paint_html missing <div"


# Shapes that render with a visual polygon (clip-path or SVG overlay)
_VISUAL_POLYGON_SHAPES = ["diamond", "hexagon", "trapezoid", "trapezoid-alt", "flag"]


@pytest.mark.parametrize("shape_name", _VISUAL_POLYGON_SHAPES)
def test_painter_vertex_parity(shape_name):
    """Polygon shapes must embed their clip-path or SVG border polygon
    in paint_html output, verifying painter and geometry are wired together."""
    geom = SHAPE_REGISTRY[shape_name]
    outline = geom.outline_path(120.0, 60.0)
    assert outline is not None, f"{shape_name}: outline_path returned None"
    html = geom.paint_html(10.0, 20.0, 120.0, 60.0, **_COMMON_PAINT_KW)
    assert html is not None
    # Must contain either clip-path polygon or SVG polygon border
    assert ("clip-path" in html or "<polygon" in html), (
        f"{shape_name}: paint_html has outline_path but no clip-path or <polygon in output"
    )


def test_flag_svg_polygon_5_vertices():
    """FlagGeometry paint_html must produce an SVG <polygon> with exactly 5 vertex pairs."""
    from scripts.mermaid_render.layout.shape_geometry import FlagGeometry
    geom = FlagGeometry()
    html = geom.paint_html(0.0, 0.0, 160.0, 48.0, **_COMMON_PAINT_KW)
    assert html is not None
    polys = re.findall(r'<polygon[^>]+points="([^"]+)"', html)
    assert polys, "FlagGeometry paint_html missing SVG <polygon>"
    pts = polys[0].strip().split()
    assert len(pts) == 5, (
        f"Flag SVG polygon should have 5 vertices, got {len(pts)}: {pts}"
    )


def test_subroutine_svg_vertical_rules():
    """SubroutineGeometry paint_html must include two SVG <line> elements with y1='2'."""
    from scripts.mermaid_render.layout.shape_geometry import SubroutineGeometry
    geom = SubroutineGeometry()
    html = geom.paint_html(0.0, 0.0, 140.0, 48.0, **_COMMON_PAINT_KW)
    assert html is not None
    lines = re.findall(r'<line[^>]+/>', html)
    assert len(lines) >= 2, f"SubroutineGeometry should produce 2 SVG lines, got {len(lines)}"
    # Both lines must have y1="2" (inside the border, not at 0)
    for ln in lines[:2]:
        assert 'y1="2"' in ln, (
            f"Subroutine vertical rule should have y1='2', got: {ln}"
        )


def test_doublecircle_ring_semantics_svg():
    """DoubleCircleGeometry paint_svg must output exactly 2 <circle> elements."""
    geom = SHAPE_REGISTRY["doublecircle"]
    svg = geom.paint_svg(0.0, 0.0, 80.0, 80.0, fill="#eee", stroke="#333", stroke_w=1.5)
    assert svg is not None
    circles = re.findall(r'<circle[^>]+/>', svg)
    assert len(circles) == 2, (
        f"DoubleCircle paint_svg should have 2 circles, got {len(circles)}: {circles}"
    )


def test_doublecircle_ring_semantics_html():
    """DoubleCircleGeometry paint_html inner ring must use two stroked rings (no filled disc).

    AC5: double-circle HTML/SVG equivalence — two concentric rings, no background fill.
    The outer ring is the main container border; the inner ring is an inset div with
    border:2px solid and background:transparent.
    """
    geom = SHAPE_REGISTRY["doublecircle"]
    html = geom.paint_html(0.0, 0.0, 80.0, 80.0, **_COMMON_PAINT_KW)
    assert html is not None
    # Inner ring: must have an inset div with a stroked border, no fill
    inner_divs = re.findall(r'<div style="[^"]*inset:[0-9]+px[^"]*"', html)
    assert inner_divs, "DoubleCircle paint_html missing inner inset div"
    assert any("border:" in d for d in inner_divs), (
        f"DoubleCircle inner ring should have border: (stroked ring), got: {inner_divs}"
    )
    assert all("background:transparent" in d or "background:" not in d.replace("background:transparent","")
               for d in inner_divs), (
        f"DoubleCircle inner ring must use background:transparent (no filled disc), got: {inner_divs}"
    )


def test_cylinder_outline_full_height():
    """CylinderGeometry outline_path must span the full height (0..h) on the y axis."""
    from scripts.mermaid_render.layout.shape_geometry import CylinderGeometry
    geom = CylinderGeometry()
    w, h = 100.0, 80.0
    verts = geom.outline_path(w, h)
    assert verts is not None, "CylinderGeometry outline_path should not be None"
    ys = [vy for _, vy in verts]
    assert min(ys) == pytest.approx(0.0, abs=0.1), (
        f"Cylinder outline_path min y should be 0, got {min(ys)}"
    )
    assert max(ys) == pytest.approx(h, abs=0.1), (
        f"Cylinder outline_path max y should be {h}, got {max(ys)}"
    )
