"""ShapeGeometry protocol + SHAPE_REGISTRY.

Each shape knows how to:
- measure itself (measured_width, measured_height) from label text bounds
- return its polygon outline (outline_path)
- clip an edge connector to its outline (boundary_intersection)
- enumerate available port sides (available_ports)
- report connector marker clearance (marker_clearance)
- paint itself as SVG or HTML (stubs — wired fully in a later pass)
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple
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

    def outline_path(
        self,
        w: float,
        h: float,
    ) -> Optional[List[Tuple[float, float]]]:
        """Return polygon vertices in top-left-origin local coords, or None for curved shapes."""
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

    def anchor(
        self,
        side: str,
        offset: float,
        w: float,
        h: float,
    ) -> Tuple[float, float]:
        """Return the canvas-local (x, y) on the shape boundary for a named side.

        side: 'top'|'bottom'|'left'|'right' (or NSEW equivalents).
        offset: fractional position along the face (0=start, 0.5=center, 1=end).
        w, h: total node width and height.
        Returned coords are relative to the node's top-left corner.
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

# Side → unit direction vector (outward from shape center).
_SIDE_DIRS: dict[str, Tuple[float, float]] = {
    "top": (0.0, -1.0), "north": (0.0, -1.0),
    "bottom": (0.0, 1.0), "south": (0.0, 1.0),
    "left": (-1.0, 0.0), "west": (-1.0, 0.0),
    "right": (1.0, 0.0), "east": (1.0, 0.0),
}


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


def _polygon_boundary(cx: float, cy: float,
                      local_verts: List[Tuple[float, float]],
                      w: float, h: float,
                      dx: float, dy: float) -> Tuple[float, float]:
    """Ray–polygon intersection.

    local_verts are in top-left-origin node-local coordinates.
    Returns the first intersection point (in canvas coords) of the ray starting at
    (cx, cy) going in direction (dx, dy) with any edge of the polygon.
    Falls back to _rect_boundary when no intersection is found.
    """
    hw, hh = w / 2.0, h / 2.0
    # Convert local coords (origin = top-left) to centered coords (origin = cx,cy).
    verts = [(x - hw, y - hh) for x, y in local_verts]

    length = math.hypot(dx, dy)
    if length < 1e-9:
        return cx, cy - hh
    ndx, ndy = dx / length, dy / length

    best_t = math.inf
    n = len(verts)
    for i in range(n):
        ax, ay = verts[i]
        bx, by = verts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        # Solve: [ndx, -ex; ndy, -ey] * [t; s]^T = [ax; ay]
        # det = ndx*(-ey) - (-ex)*ndy
        det = -ndx * ey + ex * ndy
        if abs(det) < 1e-9:
            continue
        t = (-ax * ey + ex * ay) / det
        s = (ndx * ay - ndy * ax) / det
        if t >= -1e-6 and -1e-6 <= s <= 1.0 + 1e-6:
            if t < best_t:
                best_t = t

    if math.isinf(best_t):
        return _rect_boundary(cx, cy, w, h, dx, dy)
    return cx + ndx * best_t, cy + ndy * best_t


def _diamond_boundary(cx: float, cy: float, w: float, h: float,
                      dx: float, dy: float) -> Tuple[float, float]:
    """Intersect a ray with a diamond (rotated rect) outline.

    Ports existing _clip_to_diamond() logic so output is bit-identical.
    Diamond vertices: top=(cx,cy-h/2), right=(cx+w/2,cy),
                      bottom=(cx,cy+h/2), left=(cx-w/2,cy).
    """
    hw, hh = w / 2.0, h / 2.0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return float(cx), float(cy - hh)
    ndx, ndy = dx / length, dy / length
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
    denom = (ndx / a) ** 2 + (ndy / b) ** 2
    if denom < 1e-9:
        return cx, cy - b
    t = math.sqrt(1.0 / denom)
    return cx + ndx * t, cy + ndy * t


def _default_anchor(geom: ShapeGeometry, side: str, offset: float,
                    w: float, h: float) -> Tuple[float, float]:
    """Generic anchor via boundary_intersection in the named side's direction."""
    cx, cy = w / 2.0, h / 2.0
    dx, dy = _SIDE_DIRS.get(side.lower(), (0.0, -1.0))
    bx, by = geom.boundary_intersection(cx, cy, w, h, dx, dy)
    # Offset shifts along the face perpendicular to dx,dy.
    # For top/bottom faces, perpendicular is horizontal; for left/right, vertical.
    if abs(dy) > abs(dx):  # top or bottom face
        perp = (offset - 0.5) * w
        bx += perp
    else:  # left or right face
        perp = (offset - 0.5) * h
        by += perp
    return bx, by


# ── shape implementations ─────────────────────────────────────────────────────

class RectGeometry:
    """Rectangle (default shape)."""

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        return label_w + 2 * padding_x, label_h + 2 * padding_y

    def outline_path(self, w: float, h: float) -> List[Tuple[float, float]]:
        return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> None:
        return None  # rounded corners — not a simple polygon

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> None:
        return None  # semi-circular end caps — not a simple polygon

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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
        # Sum-of-dimensions formula: a rhombus containing label_w × label_h requires
        # side = label_w + label_h + padding so both diagonals fully enclose the label.
        from ._constants import DIAMOND_MIN  # type: ignore[attr-defined]
        side = float(max(DIAMOND_MIN, math.ceil(
            label_w + label_h + 2 * padding_x + padding_y
        )))
        return side, side

    def outline_path(self, w: float, h: float) -> List[Tuple[float, float]]:
        return [(w * 0.5, 0.0), (w, h * 0.5), (w * 0.5, h), (0.0, h * 0.5)]

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _diamond_boundary(cx, cy, w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> None:
        return None  # circle — no polygon approximation

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _ellipse_boundary(cx, cy, w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    # Ring gap matches DOUBLE_CIRCLE_RING in _constants.py (8 px per side).
    _RING_GAP = 8.0

    def measure(self, label_w: float, label_h: float,
                padding_x: float, padding_y: float) -> Tuple[float, float]:
        d = math.ceil(math.hypot(label_w + padding_x, label_h + padding_y))
        d += 2 * int(self._RING_GAP)  # outer ring adds gap on each side
        return float(d), float(d)

    def outline_path(self, w: float, h: float) -> None:
        return None  # circle — no polygon approximation

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _ellipse_boundary(cx, cy, w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> List[Tuple[float, float]]:
        # Bounding silhouette is rectangular; the elliptical caps are within this box.
        return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> List[Tuple[float, float]]:
        # Matches clip-path: 25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%
        return [
            (w * 0.25, 0.0), (w * 0.75, 0.0),
            (w, h * 0.5),
            (w * 0.75, h), (w * 0.25, h),
            (0.0, h * 0.5),
        ]

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _polygon_boundary(cx, cy, self.outline_path(w, h), w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> List[Tuple[float, float]]:
        # Matches clip-path: 15% 0%, 100% 0%, 85% 100%, 0% 100%
        return [(w * 0.15, 0.0), (w, 0.0), (w * 0.85, h), (0.0, h)]

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _polygon_boundary(cx, cy, self.outline_path(w, h), w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> List[Tuple[float, float]]:
        # Matches clip-path: 0% 0%, 85% 0%, 100% 100%, 15% 100%
        return [(0.0, 0.0), (w * 0.85, 0.0), (w, h), (w * 0.15, h)]

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _polygon_boundary(cx, cy, self.outline_path(w, h), w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> List[Tuple[float, float]]:
        # Outer boundary is rectangular; inner lines don't affect edge routing.
        return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> List[Tuple[float, float]]:
        # Matches clip-path: 0% 0%, 88% 0%, 100% 50%, 88% 100%, 0% 100%
        return [(0.0, 0.0), (w * 0.88, 0.0), (w, h * 0.5), (w * 0.88, h), (0.0, h)]

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _polygon_boundary(cx, cy, self.outline_path(w, h), w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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

    def outline_path(self, w: float, h: float) -> List[Tuple[float, float]]:
        return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]

    def boundary_intersection(self, cx: float, cy: float, w: float, h: float,
                               dx: float, dy: float) -> Tuple[float, float]:
        return _rect_boundary(cx, cy, w, h, dx, dy)

    def anchor(self, side: str, offset: float, w: float, h: float) -> Tuple[float, float]:
        return _default_anchor(self, side, offset, w, h)

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
