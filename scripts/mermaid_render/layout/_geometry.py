"""Geometry IR for flowchart layout.

Provides frozen dataclasses used across layout, routing, and rendering.
LayoutResult and RoutedEdge are stubs reserved for the full-IR sprint
that makes the renderer serialization-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple


@dataclass(frozen=True, slots=True)
class Point:
    """Immutable 2-D integer point (canvas coordinates, px)."""
    x: int
    y: int


@dataclass(frozen=True)
class Rect:
    """Immutable axis-aligned bounding rectangle.

    x, y: top-left corner (canvas coordinates, px)
    w, h: width and height (px)
    """
    x: float
    y: float
    w: float
    h: float

    @property
    def x1(self) -> float:
        return self.x + self.w

    @property
    def y1(self) -> float:
        return self.y + self.h

    def contains(self, other: "Rect") -> bool:
        """True if other is fully inside (or touching) self."""
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.x1 <= self.x1
            and other.y1 <= self.y1
        )

    def overlaps(self, other: "Rect") -> bool:
        """True if the two rectangles share interior area (touching edges do not count)."""
        return (
            self.x < other.x1
            and other.x < self.x1
            and self.y < other.y1
            and other.y < self.y1
        )

    def union(self, other: "Rect") -> "Rect":
        """Return the smallest Rect enclosing both self and other."""
        nx = min(self.x, other.x)
        ny = min(self.y, other.y)
        nx1 = max(self.x1, other.x1)
        ny1 = max(self.y1, other.y1)
        return Rect(nx, ny, nx1 - nx, ny1 - ny)

    def translate(self, dx: float, dy: float) -> "Rect":
        """Return a copy shifted by (dx, dy)."""
        return Rect(self.x + dx, self.y + dy, self.w, self.h)


@dataclass(frozen=True, slots=True)
class Port:
    """A connection point on a node face."""
    point: Point
    side: str   # "top" | "bottom" | "left" | "right"
    slot: int   # index among ports on this face
    lane: int   # overflow lane (0 = first lane)


@dataclass(frozen=True, slots=True)
class PortAllocation:
    """Result of face-port allocation for one edge endpoint."""
    offset: int  # px from the face origin (top-left corner of the face)
    lane: int    # overflow lane (0 = first lane)


@dataclass(frozen=True, slots=True)
class GroupLayout:
    """Bounding geometry for a subgraph group."""
    box: Rect
    title_box: Rect


@dataclass(frozen=True, slots=True)
class RoutedEdge:
    """Fully-routed edge with geometric decoration."""
    edge_id: int
    src: str
    dst: str
    points: Tuple[Point, ...]
    src_port: Port
    dst_port: Port
    label_box: "Rect | None"
    marker_boxes: Tuple[Rect, ...]


@dataclass(frozen=True, slots=True)
class LayoutResult:
    """Complete layout result for a diagram (stub — full pipeline deferred)."""
    node_boxes: Mapping[str, Rect]
    groups: Mapping[str, GroupLayout]
    edges: Tuple[RoutedEdge, ...]
    decoration_boxes: Tuple[Rect, ...]
    canvas: Rect


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of a geometry validation pass."""
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    @property
    def status(self) -> str:
        if self.errors:
            return "invalid"
        if self.warnings:
            return "warning"
        return "ok"
