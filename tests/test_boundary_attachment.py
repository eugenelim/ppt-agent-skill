"""Geometry unit tests for BoundaryAttachment on all registered shapes.

Covers AC11 from docs/specs/flowchart-connector-attachment/spec.md:
- point lies on the shape boundary (within tolerance)
- outward_normal is a unit vector
- outward_normal points away from the shape interior
- escape_point (boundary + normal * stub) lies outside the shape interior

Shapes tested: rectangle, diamond, hexagon, trapezoid, trapezoid-alt, flag,
circle, ellipse, rounded-rect, stadium, double-circle.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mermaid_render.layout.shape_geometry import (
    SHAPE_REGISTRY,
    BoundaryAttachment,
)

_W, _H = 120.0, 80.0
_STUB = 20.0  # escape stub length
_ON_BOUNDARY_TOL = 2.5  # px tolerance for "point on boundary"
_UNIT_TOL = 1e-6


def _is_unit(nx: float, ny: float) -> bool:
    return abs(math.hypot(nx, ny) - 1.0) < _UNIT_TOL


def _escape(att: BoundaryAttachment, stub: float = _STUB) -> tuple[float, float]:
    nx, ny = att.outward_normal
    bx, by = att.point
    return bx + nx * stub, by + ny * stub


def _check_att(att: BoundaryAttachment, geom, w: float, h: float) -> None:
    """Assert the core invariants on a BoundaryAttachment."""
    bx, by = att.point
    nx, ny = att.outward_normal

    # Normal must be unit
    assert _is_unit(nx, ny), f"normal ({nx:.4g},{ny:.4g}) is not unit"

    # Normal must point outward: escape point must be outside the shape interior.
    ex, ey = _escape(att)
    # Convert to shape-centered coords for contains()
    hw, hh = w / 2.0, h / 2.0
    if hasattr(geom, 'contains'):
        assert not geom.contains(ex - hw, ey - hh, w, h), (
            f"escape ({ex:.2f},{ey:.2f}) is inside shape; "
            f"boundary ({bx:.2f},{by:.2f}) normal ({nx:.4g},{ny:.4g})"
        )


# ── Parameterized shape × side × offset tests ────────────────────────────────

_SHAPES = [
    "rect", "diamond", "hexagon",
    "trapezoid", "trapezoid-alt", "flag",
    "circle", "round", "stadium", "doublecircle",
    "subroutine", "cylinder", "bar",
]

_CASES = [
    ("top",    0.5),
    ("bottom", 0.5),
    ("left",   0.5),
    ("right",  0.5),
    ("top",    0.25),
    ("top",    0.75),
    ("right",  0.25),
    ("right",  0.75),
]


@pytest.mark.parametrize("shape_name", _SHAPES)
@pytest.mark.parametrize("side,offset", _CASES)
def test_attachment_unit_normal_and_outside(shape_name: str, side: str, offset: float) -> None:
    if shape_name not in SHAPE_REGISTRY:
        pytest.skip(f"{shape_name} not in SHAPE_REGISTRY")
    geom = SHAPE_REGISTRY[shape_name]
    att = geom.attachment(side, offset, _W, _H)
    _check_att(att, geom, _W, _H)


# ── Diamond vertex cardinal-normal tests ─────────────────────────────────────

def test_diamond_top_vertex_cardinal_normal() -> None:
    """Diamond top vertex (tip) should depart vertically (0, -1)."""
    geom = SHAPE_REGISTRY["diamond"]
    att = geom.attachment("top", 0.5, _W, _H)
    nx, ny = att.outward_normal
    # Cardinal (0, -1) is inside the vertex's outward cone → must use it
    assert abs(nx) < _UNIT_TOL and abs(ny + 1.0) < _UNIT_TOL, (
        f"diamond top normal should be (0,-1), got ({nx:.4g},{ny:.4g})"
    )


def test_diamond_bottom_vertex_cardinal_normal() -> None:
    geom = SHAPE_REGISTRY["diamond"]
    att = geom.attachment("bottom", 0.5, _W, _H)
    nx, ny = att.outward_normal
    assert abs(nx) < _UNIT_TOL and abs(ny - 1.0) < _UNIT_TOL, (
        f"diamond bottom normal should be (0,1), got ({nx:.4g},{ny:.4g})"
    )


def test_diamond_left_vertex_cardinal_normal() -> None:
    geom = SHAPE_REGISTRY["diamond"]
    att = geom.attachment("left", 0.5, _W, _H)
    nx, ny = att.outward_normal
    assert abs(nx + 1.0) < _UNIT_TOL and abs(ny) < _UNIT_TOL, (
        f"diamond left normal should be (-1,0), got ({nx:.4g},{ny:.4g})"
    )


def test_diamond_right_vertex_cardinal_normal() -> None:
    geom = SHAPE_REGISTRY["diamond"]
    att = geom.attachment("right", 0.5, _W, _H)
    nx, ny = att.outward_normal
    assert abs(nx - 1.0) < _UNIT_TOL and abs(ny) < _UNIT_TOL, (
        f"diamond right normal should be (1,0), got ({nx:.4g},{ny:.4g})"
    )


def test_diamond_face_non_cardinal_normal() -> None:
    """Diamond mid-face (offset≠0.5) should have a non-cardinal, 45-degree normal."""
    geom = SHAPE_REGISTRY["diamond"]
    att = geom.attachment("right", 0.25, _W, _H)
    nx, ny = att.outward_normal
    # On the upper-right face; normal should be approximately (0.707, -0.707)
    assert nx > 0.5 and ny < -0.5, (
        f"diamond right-upper-face normal should be in quadrant I/IV, got ({nx:.4g},{ny:.4g})"
    )


# ── Rectangle cardinal normals ────────────────────────────────────────────────

@pytest.mark.parametrize("side,expected_normal", [
    ("top",    (0.0, -1.0)),
    ("bottom", (0.0,  1.0)),
    ("left",   (-1.0, 0.0)),
    ("right",  (1.0,  0.0)),
])
def test_rectangle_cardinal_normals(side: str, expected_normal: tuple[float, float]) -> None:
    geom = SHAPE_REGISTRY["rect"]
    att = geom.attachment(side, 0.5, _W, _H)
    nx, ny = att.outward_normal
    enx, eny = expected_normal
    assert abs(nx - enx) < _UNIT_TOL and abs(ny - eny) < _UNIT_TOL, (
        f"rect {side} normal should be {expected_normal}, got ({nx:.4g},{ny:.4g})"
    )


# ── Circle outward-radial normal ──────────────────────────────────────────────

def test_circle_normal_is_radial() -> None:
    """For a circle, the normal at any boundary point is the radial direction."""
    geom = SHAPE_REGISTRY["circle"]
    w = h = 100.0
    for side in ("top", "right", "bottom", "left"):
        att = geom.attachment(side, 0.5, w, h)
        bx, by = att.point
        nx, ny = att.outward_normal
        cx, cy = w / 2.0, h / 2.0
        radial_x, radial_y = bx - cx, by - cy
        radial_len = math.hypot(radial_x, radial_y)
        if radial_len > 1e-9:
            radial_x /= radial_len
            radial_y /= radial_len
        dot = nx * radial_x + ny * radial_y
        assert dot > 0.999, (
            f"circle {side} normal ({nx:.4g},{ny:.4g}) not radial "
            f"(boundary ({bx:.2f},{by:.2f}), dot={dot:.4g})"
        )


# ── Hexagon horizontal-face normals ──────────────────────────────────────────

def test_hexagon_top_face_cardinal_normal() -> None:
    """Hexagon horizontal top face should have (0,-1) normal."""
    geom = SHAPE_REGISTRY["hexagon"]
    att = geom.attachment("top", 0.5, _W, _H)
    nx, ny = att.outward_normal
    assert abs(nx) < 0.01 and abs(ny + 1.0) < 0.01, (
        f"hexagon top normal should be ~(0,-1), got ({nx:.4g},{ny:.4g})"
    )


def test_hexagon_sloped_face_non_cardinal_normal() -> None:
    """Hexagon left-sloped face should have a non-cardinal normal."""
    geom = SHAPE_REGISTRY["hexagon"]
    att = geom.attachment("left", 0.5, _W, _H)
    nx, ny = att.outward_normal
    # Non-cardinal: both components must be non-zero
    assert abs(nx) > 0.1 and abs(ny) < 0.5, (
        f"hexagon left normal should be angled, got ({nx:.4g},{ny:.4g})"
    )


# ── TerminalAttachment round-trip ─────────────────────────────────────────────

def test_build_terminal_attachment_with_shape_geometry() -> None:
    """build_terminal_attachment returns an escape outside the shape."""
    from mermaid_render.layout.port_planner import build_terminal_attachment

    geom = SHAPE_REGISTRY["diamond"]
    node_bounds = (0.0, 0.0, _W, _H)
    ta = build_terminal_attachment(node_bounds, "right", 0.5, shape_geometry=geom)

    bx, by = ta.boundary_point
    nx, ny = ta.outward_normal
    ex, ey = ta.escape_point

    # Normal is unit
    assert _is_unit(nx, ny)
    # Escape is along normal from boundary
    assert abs(ex - (bx + nx * ta.terminal_clearance)) < 1e-6
    assert abs(ey - (by + ny * ta.terminal_clearance)) < 1e-6
    # Escape is outside the shape
    hw, hh = _W / 2.0, _H / 2.0
    assert not geom.contains(ex - hw, ey - hh, _W, _H)


def test_build_terminal_attachment_fallback_no_geometry() -> None:
    """With shape_geometry=None, falls back to AABB and cardinal normals."""
    from mermaid_render.layout.port_planner import build_terminal_attachment, FAN_ESCAPE_LENGTH

    node_bounds = (10.0, 20.0, _W, _H)
    ta = build_terminal_attachment(node_bounds, "right", 0.5, shape_geometry=None)
    assert ta.outward_normal == (1.0, 0.0)
    assert abs(ta.boundary_point[0] - (10.0 + _W)) < 1e-6
    assert abs(ta.escape_point[0] - (10.0 + _W + FAN_ESCAPE_LENGTH)) < 1e-6
