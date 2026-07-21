"""Geometry IR for the shared graph renderer.

All types are frozen dataclasses — immutable after construction.
After finalize_graph_layout() returns a FinalizedLayout, rendering must
not mutate _Node, _Edge, _Group, or any geometry object.
"""
from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence, Tuple


# ── Primitives ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def translate(self, dx: float, dy: float) -> "Point":
        return Point(self.x + dx, self.y + dy)

    def distance_to(self, other: "Point") -> float:
        return math.hypot(other.x - self.x, other.y - self.y)


@dataclass(frozen=True)
class Size:
    w: float
    h: float

    @property
    def area(self) -> float:
        return self.w * self.h


@dataclass(frozen=True)
class Insets:
    top: float
    right: float
    bottom: float
    left: float

    @staticmethod
    def uniform(v: float) -> "Insets":
        return Insets(v, v, v, v)

    @staticmethod
    def symmetric(vertical: float, horizontal: float) -> "Insets":
        return Insets(vertical, horizontal, vertical, horizontal)


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

    @property
    def center(self) -> Point:
        return Point(self.x + self.w / 2, self.y + self.h / 2)

    @property
    def top_left(self) -> Point:
        return Point(self.x, self.y)

    @property
    def top_right(self) -> Point:
        return Point(self.x1, self.y)

    @property
    def bottom_left(self) -> Point:
        return Point(self.x, self.y1)

    @property
    def bottom_right(self) -> Point:
        return Point(self.x1, self.y1)

    def contains(self, other: "Rect") -> bool:
        """True if other is fully inside (or touching) self."""
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.x1 <= self.x1
            and other.y1 <= self.y1
        )

    def contains_point(self, p: Point, tolerance: float = 0.0) -> bool:
        return (
            self.x - tolerance <= p.x <= self.x1 + tolerance
            and self.y - tolerance <= p.y <= self.y1 + tolerance
        )

    def overlaps(self, other: "Rect") -> bool:
        """True if the two rectangles share interior area (touching edges do not count)."""
        return (
            self.x < other.x1
            and other.x < self.x1
            and self.y < other.y1
            and other.y < self.y1
        )

    def intersection_area(self, other: "Rect") -> float:
        ix = max(0.0, min(self.x1, other.x1) - max(self.x, other.x))
        iy = max(0.0, min(self.y1, other.y1) - max(self.y, other.y))
        return ix * iy

    def union(self, other: "Rect") -> "Rect":
        """Return the smallest Rect enclosing both self and other."""
        nx = min(self.x, other.x)
        ny = min(self.y, other.y)
        nx1 = max(self.x1, other.x1)
        ny1 = max(self.y1, other.y1)
        return Rect(nx, ny, nx1 - nx, ny1 - ny)

    @staticmethod
    def union_all(rects: Sequence["Rect"]) -> "Rect":
        it = iter(rects)
        result = next(it)
        for r in it:
            result = result.union(r)
        return result

    def inflate(self, dx: float, dy: float | None = None) -> "Rect":
        """Return a rect expanded by dx on each horizontal side, dy on vertical."""
        _dy = dx if dy is None else dy
        return Rect(self.x - dx, self.y - _dy, self.w + 2 * dx, self.h + 2 * _dy)

    def translate(self, dx: float, dy: float) -> "Rect":
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def inset(self, ins: Insets) -> "Rect":
        return Rect(
            self.x + ins.left,
            self.y + ins.top,
            self.w - ins.left - ins.right,
            self.h - ins.top - ins.bottom,
        )

    @staticmethod
    def from_points(points: Sequence[Point]) -> "Rect":
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        return Rect(x0, y0, x1 - x0, y1 - y0)

    @staticmethod
    def from_xywh(x: float, y: float, w: float, h: float) -> "Rect":
        return Rect(x, y, w, h)

    @staticmethod
    def from_ltrb(left: float, top: float, right: float, bottom: float) -> "Rect":
        return Rect(left, top, right - left, bottom - top)


# ── Port allocation (used by _routing.py) ─────────────────────────────────────

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


# ── Text IR ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TextStyle:
    font_size: float = 15.0
    font_weight: int = 400     # 400=regular, 700=bold
    italic: bool = False
    strikethrough: bool = False
    letter_spacing: float = 0.0
    line_height_factor: float = 1.2


@dataclass(frozen=True)
class TextRun:
    text: str
    style: TextStyle
    width: float   # measured pixel width
    height: float  # measured pixel height (ascent + descent)


@dataclass(frozen=True)
class TextLine:
    runs: tuple[TextRun, ...]
    width: float   # sum of run widths
    height: float  # max run height × line_height_factor
    baseline: float  # y offset of baseline within this line


@dataclass(frozen=True)
class TextLayout:
    lines: tuple[TextLine, ...]
    width: float               # widest line width
    height: float              # total height including line gaps
    line_height: float         # nominal line height used
    min_content_width: float   # width of widest unbreakable token
    max_content_width: float   # width if all text on one line
    resolved_font_path: Optional[str]
    resolved_font_family: str


# ── Port IR ───────────────────────────────────────────────────────────────────

class PortSide(enum.Enum):
    AUTO = "AUTO"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOP = "TOP"
    BOTTOM = "BOTTOM"


@dataclass(frozen=True)
class PortRequest:
    """Caller's requested port side — may be AUTO to let the router decide."""
    side: PortSide = PortSide.AUTO
    offset_fraction: float = 0.5  # 0=near start edge, 1=near end edge


@dataclass(frozen=True)
class PortLayout:
    """A resolved port: exact canvas position and outgoing direction."""
    node_id: str
    side: PortSide
    position: Point   # exact canvas point on the node boundary
    direction: Point  # unit vector pointing outward from the node


# ── Node / Group layout ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class NodeLayout:
    node_id: str
    semantic_shape: str           # "rect" | "diamond" | "circle" | ...
    outer_bounds: Rect            # includes border/shadow
    content_bounds: Rect          # inner content area (text fits here)
    title_layout: Optional[TextLayout]
    subtitle_layout: Optional[TextLayout]
    member_layouts: tuple[TextLayout, ...]  # class/ER member rows
    icon_bounds: Optional[Rect]
    ports: tuple[PortLayout, ...]
    css_classes: tuple[str, ...]
    extra_css: str
    is_dummy: bool = False


@dataclass(frozen=True)
class GroupLayout:
    group_id: str
    parent_group_id: Optional[str]
    boundary_bounds: Rect          # outer bounds of the whole group box
    label_layout: Optional[TextLayout]
    member_ids: tuple[str, ...]
    child_group_ids: tuple[str, ...]
    local_direction: str           # "TB" | "LR" | "RL" | "BT"


# ── Edge layout ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EdgeLabelLayout:
    text: str
    layout: TextLayout
    bounds: Rect
    anchor_point: Point    # point on the route the label is anchored to


@dataclass(frozen=True)
class RoutedEdge:
    edge_id: str
    src_node_id: str
    dst_node_id: str
    src_port: PortLayout
    dst_port: PortLayout
    waypoints: tuple[Point, ...]   # ordered route points including endpoints
    edge_style: str                # "solid" | "dotted" | "thick"
    has_marker_end: bool
    has_marker_start: bool         # True for bidir edges
    label_layout: Optional[EdgeLabelLayout]
    src_label_layout: Optional[EdgeLabelLayout]
    dst_label_layout: Optional[EdgeLabelLayout]
    is_reversed: bool = False      # back-edge (drawn reversed)
    route_diagnostics: str = ""    # "ok" | "fallback" | "failed:..."


# ── Diagnostics ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LayoutDiagnostics:
    unsupported_options: tuple[str, ...]  # unknown init-config keys
    route_failures: tuple[str, ...]       # edge ids that used fallback routing
    warnings: tuple[str, ...]


# ── Finalized layout (the authoritative output) ───────────────────────────────

@dataclass(frozen=True)
class FinalizedLayout:
    """Immutable geometry produced by finalize_graph_layout().

    The renderer must accept this and perform no geometry work.
    """
    node_layouts: dict[str, NodeLayout]          # node_id → NodeLayout
    group_layouts: dict[str, GroupLayout]         # group_id → GroupLayout
    routed_edges: tuple[RoutedEdge, ...]
    visible_bounds: Rect    # bounding box of all rendered content
    diagram_padding: float
    canvas_bounds: Rect     # visible_bounds + padding on all sides
    direction: str          # "TB" | "LR" | "RL" | "BT"
    diagnostics: LayoutDiagnostics


def _empty_diagnostics() -> LayoutDiagnostics:
    return LayoutDiagnostics(
        unsupported_options=(),
        route_failures=(),
        warnings=(),
    )


# ── Pipeline stubs (used by _strategies.py and __init__.py) ──────────────────

@dataclass(frozen=True, slots=True)
class LayoutResult:
    """Complete layout result for a diagram (stub — full pipeline deferred)."""
    node_boxes: Mapping[str, Rect]
    groups: Mapping[str, GroupLayout]
    edges: Tuple[RoutedEdge, ...]
    decoration_boxes: Tuple[Rect, ...]
    canvas: Rect


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Structured diagnostic for an unsupported or unrecognised construct."""
    feature: str
    line_number: int
    source_text: str


@dataclass(frozen=True, slots=True)
class SequenceGeometry:
    """All computed geometry from a sequenceDiagram layout pass.

    Returned alongside the HTML string by _layout_lifeline so that
    _dispatch_validate can check invariants without parsing HTML.
    Fields are populated incrementally across G3 tasks; unimplemented
    fields default to empty tuples.
    """
    participant_centers: Tuple[Tuple[str, float], ...] = ()  # (pid, cx)
    lifeline_x: Tuple[Tuple[str, float], ...] = ()           # (pid, x)
    activation_bars: Tuple[Tuple[str, float, float], ...] = ()  # (pid, top_y, bot_y)
    message_ys: Tuple[float, ...] = ()
    message_endpoints: Tuple[Tuple[float, float, float, float], ...] = ()  # (sx,sy,dx,dy)
    fragment_bounds: Tuple[Tuple[str, float, float, float, float], ...] = ()  # (id,x,y,w,h)
    branch_separator_bounds: Tuple[Tuple[str, float, float, float, float], ...] = ()  # (frag_id,x,y,w,h)
    note_bounds: Tuple[Tuple[float, float, float, float], ...] = ()  # (x,y,w,h)
    self_loop_bounds: Tuple[Tuple[float, float, float, float], ...] = ()  # (x,y,w,h)
    label_bounds: Tuple[Tuple[float, float, float, float], ...] = ()  # (x,y,w,h)
    marker_bounds: Tuple[Tuple[float, float, float, float], ...] = ()  # (x,y,w,h)
    canvas: Tuple[float, float] = (0.0, 0.0)  # (width, height)
    diagnostics: Tuple["Diagnostic", ...] = ()  # unsupported-construct diagnostics


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of a geometry validation pass.

    Four independent status lanes (render, syntax_coverage, geometry,
    mmdc_oracle) replace the legacy single status property. The old
    errors/warnings/status interface is preserved for existing callers.
    """
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    diagnostics: Tuple[Diagnostic, ...] = ()
    render: str = "pass"              # "pass" | "fail"
    syntax_coverage: str = "pass"     # "pass" | "partial" | "fail"
    geometry: str = "unvalidated"     # "pass" | "fail" | "unvalidated"
    mmdc_oracle: str = "unvalidated"  # "pass" | "warning" | "fail" | "unvalidated"

    @property
    def status(self) -> str:
        if self.errors:
            return "invalid"
        if self.warnings:
            return "warning"
        return "ok"
