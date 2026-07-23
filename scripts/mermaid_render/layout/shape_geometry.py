"""ShapeGeometry protocol + SHAPE_REGISTRY.

Each shape knows how to:
- measure itself (measured_width, measured_height) from label text bounds
- clip an edge connector to its outline (boundary_intersection)
- enumerate available port sides (available_ports)
- report connector marker clearance (marker_clearance)
- paint itself as SVG or HTML (stubs — wired fully in a later pass)
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple
try:
    from typing import Protocol, runtime_checkable
except ImportError:
    from typing_extensions import Protocol, runtime_checkable  # type: ignore[assignment]


# ── Protocol ─────────────────────────────────────────────────────────────────

@runtime_checkable
class ShapeGeometry(Protocol):
    """Boundary geometry contract for a single node shape."""

    def measure(
        self,
        label_w: float,
        label_h: float,
        padding_x: float,
        padding_y: float,
    ) -> Tuple[float, float]:
        """Return (measured_width, measured_height) from label bounds + padding."""
        ...

    def boundary_intersection(
        self,
        cx: float,
        cy: float,
        w: float,
        h: float,
        dx: float,
        dy: float,
    ) -> Tuple[float, float]:
        """Return (x, y) on the shape outline in direction (dx, dy) from center (cx, cy).

        (cx, cy) is the shape center; (w, h) are total width/height; (dx, dy) is the
        outward direction vector (need not be unit-length).
        """
        ...

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        """Return ordered list of valid ELK port sides ('NORTH','SOUTH','EAST','WEST')."""
        ...

    def marker_clearance(self, marker_kind: str) -> float:
        """Return how many px to pull the connector tip back from the boundary
        so an arrowhead of type marker_kind doesn't overdraw the shape fill."""
        ...

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        """Return an SVG fragment string for this shape, or None (stub)."""
        ...

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        """Return an HTML fragment string for this shape, or None (stub)."""
        ...


# ── helpers ──────────────────────────────────────────────────────────────────

_ALL_PORTS = ("NORTH", "SOUTH", "EAST", "WEST")
_DEFAULT_MARKER_CLEARANCE = 8.0


def _rect_boundary(cx: float, cy: float, w: float, h: float,
                   dx: float, dy: float) -> Tuple[float, float]:
    """Intersect a ray from (cx,cy) in direction (dx,dy) with an axis-aligned rect."""
    hw, hh = w / 2.0, h / 2.0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return cx, cy - hh  # degenerate: return top center
    ndx, ndy = dx / length, dy / length
    # parametric t to each face
    tx = (hw / abs(ndx)) if abs(ndx) > 1e-9 else math.inf
    ty = (hh / abs(ndy)) if abs(ndy) > 1e-9 else math.inf
    t = min(tx, ty)
    return cx + ndx * t, cy + ndy * t


def _diamond_boundary(cx: float, cy: float, w: float, h: float,
                      dx: float, dy: float) -> Tuple[float, float]:
    """Intersect a ray with a diamond (rotated rect) outline.

    Ports existing _clip_to_diamond() logic so output is bit-identical.
    Diamond vertices: top=(cx,cy-h/2), right=(cx+w/2,cy),
                      bottom=(cx,cy+h/2), left=(cx-w/2,cy).
    """
    hw, hh = w / 2.0, h / 2.0
    odx = dx
    ody = dy
    length = math.hypot(odx, ody)
    if length < 1e-9:
        vertices: list[Tuple[float, float]] = [
            (cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)
        ]
        # return top vertex as default
        return vertices[0]
    ndx, ndy = odx / length, ody / length
    denom = abs(ndx) / hw + abs(ndy) / hh
    if denom < 1e-9:
        return float(cx), float(cy - hh)
    t = 1.0 / denom
    return float(cx + ndx * t), float(cy + ndy * t)


def _ellipse_boundary(cx: float, cy: float, w: float, h: float,
                      dx: float, dy: float) -> Tuple[float, float]:
    """Intersect a ray with an ellipse outline."""
    a, b = w / 2.0, h / 2.0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return cx, cy - b
    ndx, ndy = dx / length, dy / length
    # parametric: (a*ndy)^2 + (b*ndx)^2 != 0 always for a,b > 0
    denom = (ndx / a) ** 2 + (ndy / b) ** 2
    if denom < 1e-9:
        return cx, cy - b
    t = math.sqrt(1.0 / denom)
    return cx + ndx * t, cy + ndy * t


# ── shape implementations ─────────────────────────────────────────────────────

class RectGeometry:
    """Rectangle (default shape)."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        return label_w + 2 * padding_x, label_h + 2 * padding_y

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class RoundGeometry:
    """Rounded rectangle."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        return label_w + 2 * padding_x, label_h + 2 * padding_y

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class StadiumGeometry:
    """Stadium / pill shape."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        h = label_h + 2 * padding_y
        return label_w + 2 * padding_x + h, h  # end caps add h/2 each side

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class DiamondGeometry:
    """Diamond (decision) shape.

    boundary_intersection ports _clip_to_diamond() so the output is identical;
    _routing.py calls this via the registry on the Python fallback path.
    """

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        side = max(label_w + 2 * padding_x, label_h + 2 * padding_y)
        return side, side

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _diamond_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class CircleGeometry:
    """Circle shape."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        d = math.ceil(math.hypot(label_w + padding_x, label_h + padding_y))
        return float(d), float(d)

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _ellipse_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class DoubleCircleGeometry:
    """Double-circle (UML end-state) shape."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        d = math.ceil(math.hypot(label_w + padding_x, label_h + padding_y))
        return float(d), float(d)

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _ellipse_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class CylinderGeometry:
    """Cylinder / database shape."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        cap_h = 12.0  # approx ellipse cap height
        return label_w + 2 * padding_x, label_h + 2 * padding_y + 2 * cap_h

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class HexagonGeometry:
    """Hexagon shape."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        side = max(label_w + 2 * padding_x, label_h + 2 * padding_y)
        return side, side

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        # Approximate as rect; hexagon closely bounds the rect on NSEW faces.
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class TrapezoidGeometry:
    """Trapezoid (parallelogram with slanted sides)."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        slant = 16.0
        return label_w + 2 * padding_x + slant, label_h + 2 * padding_y

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class TrapezoidAltGeometry:
    """Inverted trapezoid."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        slant = 16.0
        return label_w + 2 * padding_x + slant, label_h + 2 * padding_y

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class SubroutineGeometry:
    """Subroutine (double-border rect)."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        return label_w + 2 * padding_x + 16, label_h + 2 * padding_y

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class FlagGeometry:
    """Flag / document shape."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        return label_w + 2 * padding_x, label_h + 2 * padding_y + 8

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return _ALL_PORTS

    def marker_clearance(self, marker_kind: str) -> float:
        return _DEFAULT_MARKER_CLEARANCE

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


class BarGeometry:
    """Bar / fork-join shape (thin horizontal bar)."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        return max(label_w + 2 * padding_x, 60.0), 8.0

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def available_ports(self, w: float, h: float) -> Sequence[str]:
        return ("NORTH", "SOUTH")

    def marker_clearance(self, marker_kind: str) -> float:
        return 4.0

    def paint_svg(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None

    def paint_html(self, x: float, y: float, w: float, h: float, **kw: object) -> Optional[str]:
        return None


# ── registry ──────────────────────────────────────────────────────────────────

SHAPE_REGISTRY: dict[str, ShapeGeometry] = {
    "rect":          RectGeometry(),
    "round":         RoundGeometry(),
    "stadium":       StadiumGeometry(),
    "diamond":       DiamondGeometry(),
    "circle":        CircleGeometry(),
    "doublecircle":  DoubleCircleGeometry(),
    "cylinder":      CylinderGeometry(),
    "hexagon":       HexagonGeometry(),
    "trapezoid":     TrapezoidGeometry(),
    "trapezoid-alt": TrapezoidAltGeometry(),
    "subroutine":    SubroutineGeometry(),
    "flag":          FlagGeometry(),
    "bar":           BarGeometry(),
}
