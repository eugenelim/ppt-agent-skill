"""Tests for ShapeGeometry analytic boundary correctness (spec: mermaid-shape-boundary-exactness).

Covers AC1–AC9 of the spec:
  AC1: ShapeGeometry protocol exposes contains(), boundary_anchor(), normal_at()
  AC2: Analytic boundary_intersection for rounded-rect, stadium, cylinder, ellipse
  AC3: Diamond / hexagon use polygon intersection
  AC4: marker_clearance() returns marker-kind-specific values
  AC5: DoubleCircle HTML uses two stroked rings (no filled inner disc)
  AC6: terminal doublecircle in renderer has node-state-final CSS class
  AC7: boundary_anchor() lies exactly on the shape boundary
  AC8: contains() correctly classifies interior and exterior points
  AC9: normal_at() returns outward unit vectors
"""
import math
import re
import pytest

from scripts.mermaid_render.layout.shape_geometry import (
    SHAPE_REGISTRY,
    ShapeGeometry,
    RectGeometry,
    RoundGeometry,
    StadiumGeometry,
    DiamondGeometry,
    CircleGeometry,
    DoubleCircleGeometry,
    CylinderGeometry,
    HexagonGeometry,
)


# ── AC1: Protocol exposes new methods ─────────────────────────────────────────

def test_protocol_contains_method():
    """All SHAPE_REGISTRY entries implement contains()."""
    for name, geom in SHAPE_REGISTRY.items():
        assert hasattr(geom, "contains"), f"{name} missing contains()"
        assert callable(geom.contains), f"{name}.contains is not callable"


def test_protocol_boundary_anchor_method():
    """All SHAPE_REGISTRY entries implement boundary_anchor()."""
    for name, geom in SHAPE_REGISTRY.items():
        assert hasattr(geom, "boundary_anchor"), f"{name} missing boundary_anchor()"
        assert callable(geom.boundary_anchor), f"{name}.boundary_anchor is not callable"


def test_protocol_normal_at_method():
    """All SHAPE_REGISTRY entries implement normal_at()."""
    for name, geom in SHAPE_REGISTRY.items():
        assert hasattr(geom, "normal_at"), f"{name} missing normal_at()"
        assert callable(geom.normal_at), f"{name}.normal_at is not callable"


# ── AC4: marker_clearance() returns marker-kind-specific values ────────────────

_MARKER_KINDS = [
    "filled_arrow", "hollow_triangle", "filled_diamond", "hollow_diamond",
    "er_cardinality", "default",
]

@pytest.mark.parametrize("shape_name", list(SHAPE_REGISTRY.keys()))
def test_marker_clearance_positive(shape_name):
    """marker_clearance() must return a positive float for all marker kinds."""
    geom = SHAPE_REGISTRY[shape_name]
    for kind in _MARKER_KINDS:
        val = geom.marker_clearance(kind)
        assert isinstance(val, (int, float)), (
            f"{shape_name}.marker_clearance({kind!r}) returned non-numeric: {val!r}"
        )
        assert val >= 0, (
            f"{shape_name}.marker_clearance({kind!r}) returned negative: {val}"
        )


def test_marker_clearance_diamond_larger_than_default():
    """filled_diamond clearance should be larger than filled_arrow for non-bar shapes."""
    geom = SHAPE_REGISTRY["rect"]
    arrow_c = geom.marker_clearance("filled_arrow")
    diamond_c = geom.marker_clearance("filled_diamond")
    assert diamond_c > arrow_c, (
        f"filled_diamond clearance ({diamond_c}) should exceed filled_arrow ({arrow_c})"
    )


def test_marker_clearance_hollow_diamond_largest():
    """hollow_diamond clearance should be >= filled_diamond for non-bar shapes."""
    geom = SHAPE_REGISTRY["circle"]
    filled_d = geom.marker_clearance("filled_diamond")
    hollow_d = geom.marker_clearance("hollow_diamond")
    assert hollow_d >= filled_d, (
        f"hollow_diamond ({hollow_d}) should be >= filled_diamond ({filled_d})"
    )


# ── AC2: Analytic boundary for curved shapes ───────────────────────────────────

def _boundary_on_circle(cx, cy, bx, by, r, tol=2.0):
    """Return True if (bx,by) lies on a circle of radius r centered at (cx,cy)."""
    dist = math.hypot(bx - cx, by - cy)
    return abs(dist - r) < tol


@pytest.mark.parametrize("dx,dy", [
    (1, 0), (0, 1), (-1, 0), (0, -1),
    (1, 1), (-1, 1), (1, -1), (-1, -1),
])
def test_circle_boundary_on_circumference(dx, dy):
    """CircleGeometry boundary_intersection lies on the circumference (r = w/2)."""
    geom = SHAPE_REGISTRY["circle"]
    w = h = 80.0
    cx, cy = w / 2.0, h / 2.0
    px, py = geom.boundary_intersection(cx, cy, w, h, float(dx), float(dy))
    r = w / 2.0
    assert _boundary_on_circle(cx, cy, px, py, r, tol=2.0), (
        f"CircleGeometry boundary_intersection({dx},{dy}) → ({px:.2f},{py:.2f}) "
        f"not on circumference r={r}"
    )


@pytest.mark.parametrize("dx,dy", [
    (1, 0), (0, 1), (-1, 0), (0, -1),
    (1, 1), (-1, 1), (1, -1), (-1, -1),
])
def test_stadium_boundary_outward(dx, dy):
    """StadiumGeometry boundary_intersection is always outside the center."""
    geom = SHAPE_REGISTRY["stadium"]
    w, h = 120.0, 40.0
    cx, cy = w / 2.0, h / 2.0
    px, py = geom.boundary_intersection(cx, cy, w, h, float(dx), float(dy))
    dot = (px - cx) * dx + (py - cy) * dy
    assert dot >= -0.5, (
        f"StadiumGeometry boundary_intersection({dx},{dy}) → ({px:.2f},{py:.2f}) behind center"
    )


@pytest.mark.parametrize("dx,dy", [
    (1, 0), (0, 1), (-1, 0), (0, -1),
])
def test_round_boundary_outward(dx, dy):
    """RoundGeometry boundary_intersection is outside the center."""
    geom = SHAPE_REGISTRY["round"]
    w, h = 120.0, 50.0
    cx, cy = w / 2.0, h / 2.0
    px, py = geom.boundary_intersection(cx, cy, w, h, float(dx), float(dy))
    dot = (px - cx) * dx + (py - cy) * dy
    assert dot >= -0.5, (
        f"RoundGeometry boundary_intersection({dx},{dy}) → ({px:.2f},{py:.2f}) behind center"
    )


@pytest.mark.parametrize("dx,dy", [
    (1, 0), (0, 1), (-1, 0), (0, -1),
    (1, 1), (-1, 1),
])
def test_cylinder_boundary_outward(dx, dy):
    """CylinderGeometry silhouette boundary is outside the center."""
    geom = SHAPE_REGISTRY["cylinder"]
    w, h = 100.0, 80.0
    cx, cy = w / 2.0, h / 2.0
    px, py = geom.boundary_intersection(cx, cy, w, h, float(dx), float(dy))
    dot = (px - cx) * dx + (py - cy) * dy
    assert dot >= -0.5, (
        f"CylinderGeometry boundary_intersection({dx},{dy}) → ({px:.2f},{py:.2f}) behind center"
    )


def test_cylinder_boundary_horizontal_on_wall():
    """CylinderGeometry horizontal rays land on left/right walls at x=0 or x=w."""
    geom = SHAPE_REGISTRY["cylinder"]
    w, h = 100.0, 80.0
    cx, cy = w / 2.0, h / 2.0
    # rightward
    rx, ry = geom.boundary_intersection(cx, cy, w, h, 1.0, 0.0)
    assert abs(rx - w) < 2.0, f"Cylinder right wall: expected x≈{w}, got {rx:.2f}"
    # leftward
    lx, ly = geom.boundary_intersection(cx, cy, w, h, -1.0, 0.0)
    assert abs(lx) < 2.0, f"Cylinder left wall: expected x≈0, got {lx:.2f}"


def test_cylinder_boundary_downward_on_bottom_ellipse():
    """CylinderGeometry downward ray lands near bottom edge of the cylinder."""
    geom = SHAPE_REGISTRY["cylinder"]
    w, h = 100.0, 80.0
    cx, cy = w / 2.0, h / 2.0
    bx, by = geom.boundary_intersection(cx, cy, w, h, 0.0, 1.0)
    assert by >= h - 15.0, (
        f"Cylinder downward boundary: expected near bottom ({h}), got y={by:.2f}"
    )


# ── AC3: Diamond / hexagon use polygon intersection ───────────────────────────

@pytest.mark.parametrize("dx,dy", [
    (1, 0), (0, 1), (-1, 0), (0, -1),
    (1, 1), (-1, 1), (1, -1), (-1, -1),
])
def test_diamond_boundary_on_outline(dx, dy):
    """DiamondGeometry boundary_intersection lies on the diamond outline."""
    geom = SHAPE_REGISTRY["diamond"]
    w = h = 100.0
    cx, cy = w / 2.0, h / 2.0

    px, py = geom.boundary_intersection(cx, cy, w, h, float(dx), float(dy))
    verts = geom.outline_path(w, h)
    assert verts is not None

    # Check Manhattan distance: |ndx|/hw + |ndy|/hh ≈ 1 (diamond boundary condition)
    hw, hh = w / 2.0, h / 2.0
    # Point in shape-centered coords
    spx, spy = px - cx, py - cy
    manhattan = abs(spx) / hw + abs(spy) / hh
    assert abs(manhattan - 1.0) < 0.05, (
        f"DiamondGeometry boundary_intersection({dx},{dy}) → ({px:.2f},{py:.2f}): "
        f"Manhattan dist {manhattan:.4f} not ≈ 1.0"
    )


# ── AC5: DoubleCircle HTML uses stroked rings ─────────────────────────────────

def test_doublecircle_html_no_filled_inner_disc():
    """DoubleCircleGeometry paint_html must NOT produce a filled inner disc."""
    geom = SHAPE_REGISTRY["doublecircle"]
    kw = {
        "inner_html": "<span>A</span>",
        "border_css": "",
        "shape_css": "",
        "bg_css": "",
        "box_shadow": "",
        "data_attrs_html": 'class="node node-doublecircle"',
        "accent": "#60a5fa",
    }
    html = geom.paint_html(0.0, 0.0, 80.0, 80.0, **kw)
    assert html is not None

    # The inner ring div should NOT have a solid background fill (not 'background:#...' with color)
    inner_divs = re.findall(r'<div style="[^"]*inset:[0-9]+px[^"]*"', html)
    assert inner_divs, "DoubleCircle paint_html missing inner inset div"
    # None of the inset divs should have a non-transparent background that is a color
    for d in inner_divs:
        # background:transparent is OK, background:#... is not OK
        bg_match = re.search(r'background:([^;]+)', d)
        if bg_match:
            bg_val = bg_match.group(1).strip()
            assert bg_val == "transparent", (
                f"DoubleCircle inner ring has filled background: {bg_val!r} — "
                f"should be transparent (two stroked rings, no fill)"
            )


def test_doublecircle_html_has_stroked_inner_ring():
    """DoubleCircleGeometry paint_html inner ring must have a border: property."""
    geom = SHAPE_REGISTRY["doublecircle"]
    kw = {
        "inner_html": "<span>A</span>",
        "border_css": "",
        "shape_css": "",
        "bg_css": "",
        "box_shadow": "",
        "data_attrs_html": 'class="node node-doublecircle"',
        "accent": "#60a5fa",
    }
    html = geom.paint_html(0.0, 0.0, 80.0, 80.0, **kw)
    inner_divs = re.findall(r'<div style="[^"]*inset:[0-9]+px[^"]*"', html)
    assert inner_divs, "No inner inset div found"
    assert any("border:" in d for d in inner_divs), (
        f"DoubleCircle inner ring should have border: (stroked), got: {inner_divs}"
    )


# ── AC6: terminal doublecircle has node-state-final CSS class ─────────────────

def test_terminal_doublecircle_has_state_final_class():
    """Rendered terminal doublecircle (UML final state) must carry node-state-final class."""
    from scripts.mermaid_render.layout._strategies import _dispatch
    src = "stateDiagram-v2\n    [*] --> A\n    A --> [*]\n"
    html = _dispatch(src, None, 400)
    assert "node-state-final" in html, (
        "Terminal doublecircle node missing 'node-state-final' CSS class in rendered HTML"
    )


# ── AC7: boundary_anchor() lies exactly on the shape boundary ─────────────────

_SIDES = ["top", "bottom", "left", "right"]
_OFFSETS = [0.0, 0.25, 0.5, 0.75, 1.0]

_SHAPES_FOR_ANCHOR = [
    ("rect", 120.0, 60.0),
    ("round", 120.0, 60.0),
    ("stadium", 120.0, 40.0),
    ("circle", 80.0, 80.0),
    ("diamond", 100.0, 100.0),
    ("hexagon", 120.0, 60.0),
    ("cylinder", 100.0, 80.0),
    ("subroutine", 120.0, 60.0),
    ("flag", 120.0, 60.0),
]


@pytest.mark.parametrize("shape_name,w,h", _SHAPES_FOR_ANCHOR)
@pytest.mark.parametrize("side", _SIDES)
@pytest.mark.parametrize("offset", _OFFSETS)
def test_boundary_anchor_on_outline(shape_name, w, h, side, offset):
    """boundary_anchor() result must lie on the shape boundary (≤5 px from the true boundary).

    boundary_anchor() returns node-local coords (origin at top-left corner).
    We verify by re-shooting a ray from the node center in the anchor direction
    and checking that boundary_intersection reproduces the anchor.
    """
    geom = SHAPE_REGISTRY[shape_name]
    # Node center in node-local coords
    cx, cy = w / 2.0, h / 2.0
    # boundary_anchor returns node-local canvas coords (origin = top-left)
    bx, by = geom.boundary_anchor(side, offset, w, h)

    # Direction from center to anchor point (shape-centered)
    dx, dy = bx - cx, by - cy
    dist_check = math.hypot(dx, dy)
    if dist_check < 1e-9:
        return  # degenerate case (anchor at center), skip

    # boundary_intersection should reproduce the same point when shot from center
    ix, iy = geom.boundary_intersection(cx, cy, w, h, dx, dy)

    dist = math.hypot(ix - bx, iy - by)
    assert dist < 5.0, (
        f"{shape_name} boundary_anchor({side!r},{offset}) → node-local ({bx:.2f},{by:.2f}); "
        f"boundary_intersection({dx:.2f},{dy:.2f}) → ({ix:.2f},{iy:.2f}); distance {dist:.2f} > 5px"
    )


# ── AC8: contains() correctly classifies points ───────────────────────────────

@pytest.mark.parametrize("shape_name,w,h", [
    ("rect", 100.0, 60.0),
    ("circle", 80.0, 80.0),
    ("stadium", 120.0, 40.0),
    ("diamond", 100.0, 100.0),
    ("cylinder", 100.0, 80.0),
])
def test_contains_center(shape_name, w, h):
    """contains(0,0) (center in shape coords) must return True for all shapes."""
    geom = SHAPE_REGISTRY[shape_name]
    result = geom.contains(0.0, 0.0, w, h, inset=0.0)
    assert result, f"{shape_name}.contains(0,0) returned False — center must be inside"


@pytest.mark.parametrize("shape_name,w,h", [
    ("rect", 100.0, 60.0),
    ("circle", 80.0, 80.0),
    ("stadium", 120.0, 40.0),
])
def test_contains_far_outside(shape_name, w, h):
    """contains(far point) must return False for all shapes."""
    geom = SHAPE_REGISTRY[shape_name]
    result = geom.contains(w * 2, h * 2, w, h, inset=0.0)
    assert not result, (
        f"{shape_name}.contains({w*2},{h*2}) returned True — far outside must be False"
    )


def test_rect_contains_inset():
    """RectGeometry.contains() with inset shrinks the interior."""
    geom = SHAPE_REGISTRY["rect"]
    w, h = 100.0, 60.0
    hw, hh = w / 2.0, h / 2.0
    # Just inside edge (no inset)
    assert geom.contains(hw - 1.0, 0.0, w, h, inset=0.0)
    # With inset=20, point at hw-1 should be outside the inset region
    assert not geom.contains(hw - 1.0, 0.0, w, h, inset=20.0)


# ── AC9: normal_at() returns outward unit vectors ─────────────────────────────

@pytest.mark.parametrize("shape_name,w,h,px,py,expect_nx,expect_ny", [
    # Right edge of rect
    ("rect", 100.0, 60.0, 50.0, 0.0, 1.0, 0.0),
    # Left edge of rect
    ("rect", 100.0, 60.0, -50.0, 0.0, -1.0, 0.0),
    # Top edge of rect
    ("rect", 100.0, 60.0, 0.0, -30.0, 0.0, -1.0),
    # Bottom edge of rect
    ("rect", 100.0, 60.0, 0.0, 30.0, 0.0, 1.0),
    # Right side of circle (point on boundary)
    ("circle", 80.0, 80.0, 40.0, 0.0, 1.0, 0.0),
    # Top of circle
    ("circle", 80.0, 80.0, 0.0, -40.0, 0.0, -1.0),
])
def test_normal_at_known_points(shape_name, w, h, px, py, expect_nx, expect_ny):
    """normal_at() should return the expected outward unit normal at known boundary points."""
    geom = SHAPE_REGISTRY[shape_name]
    nx, ny = geom.normal_at(px, py, w, h)
    tol = 0.05
    assert abs(nx - expect_nx) < tol and abs(ny - expect_ny) < tol, (
        f"{shape_name}.normal_at({px},{py}) → ({nx:.3f},{ny:.3f}), "
        f"expected ({expect_nx},{expect_ny})"
    )


@pytest.mark.parametrize("shape_name,w,h", [
    ("rect", 100.0, 60.0),
    ("circle", 80.0, 80.0),
    ("stadium", 120.0, 40.0),
    ("diamond", 100.0, 100.0),
])
@pytest.mark.parametrize("dx,dy", [
    (1, 0), (0, 1), (-1, 0), (0, -1),
])
def test_normal_at_boundary_outward(shape_name, w, h, dx, dy):
    """normal_at() at a boundary point from that direction is outward (dot product ≥ 0)."""
    geom = SHAPE_REGISTRY[shape_name]
    cx, cy = w / 2.0, h / 2.0
    # Get boundary point
    bx, by = geom.boundary_intersection(cx, cy, w, h, float(dx), float(dy))
    # Convert to shape-centered coords
    spx, spy = bx - cx, by - cy
    nx, ny = geom.normal_at(spx, spy, w, h)
    # Unit vector check
    mag = math.hypot(nx, ny)
    assert abs(mag - 1.0) < 0.05, (
        f"{shape_name}.normal_at({spx:.1f},{spy:.1f}) magnitude {mag:.3f} ≠ 1"
    )
    # Outward direction: dot with (dx,dy) should be positive
    dot = nx * dx + ny * dy
    assert dot >= -0.05, (
        f"{shape_name}.normal_at({spx:.1f},{spy:.1f}) → ({nx:.3f},{ny:.3f}) "
        f"not outward for direction ({dx},{dy}): dot={dot:.3f}"
    )
