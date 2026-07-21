"""Geometry IR for flowchart layout.

Provides the Rect frozen dataclass used across layout, routing, and rendering.
GroupLayout, RoutedEdge, and FinalizedLayout are reserved for a future
full-IR sprint that makes the renderer serialization-only.
"""
from __future__ import annotations

from dataclasses import dataclass


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
