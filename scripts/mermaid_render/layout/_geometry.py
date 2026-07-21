"""Geometry IR for the shared graph renderer.

All types are frozen dataclasses — immutable after construction.
After finalize_graph_layout() returns a FinalizedLayout, rendering must
not mutate _Node, _Edge, _Group, or any geometry object.
"""
from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from types import MappingProxyType
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
    rank: int = 0
    is_external: bool = False
    icon_svg: str = ""
    accent_color: str = ""
    parent_group_id: Optional[str] = None


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


# ── Routing failure (typed result for an edge that could not be routed) ───────

@dataclass(frozen=True, slots=True)
class RoutingFailure:
    """A parsed edge that could not be routed successfully.

    Produced by _route_edges() when no valid path exists. Stored in
    FinalizedLayout.routing_failures and reported as an error by
    validate_finalized_layout().
    """
    edge_id: str
    src_node_id: str
    dst_node_id: str
    reason: str   # human-readable failure description


# ── Diagnostics ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LayoutDiagnostics:
    unsupported_options: tuple[str, ...]  # unknown init-config keys
    route_failures: tuple[str, ...]       # edge ids that used fallback routing (legacy)
    warnings: tuple[str, ...]


# ── Finalized layout (the authoritative output) ───────────────────────────────

@dataclass(frozen=True)
class FinalizedLayout:
    """Immutable geometry produced by _compile_flowchart().

    The renderer must accept this and perform no geometry work.
    node_layouts and group_layouts are always MappingProxyType — __post_init__
    wraps any plain dict passed in at construction time.
    routing_failures has a default of () for backwards compatibility with
    existing test construction sites.
    """
    node_layouts: MappingProxyType  # MappingProxyType[str, NodeLayout]
    group_layouts: MappingProxyType  # MappingProxyType[str, GroupLayout]
    routed_edges: tuple[RoutedEdge, ...]
    visible_bounds: Rect
    diagram_padding: float
    canvas_bounds: Rect
    direction: str          # "TB" | "LR" | "RL" | "BT"
    diagnostics: LayoutDiagnostics
    routing_failures: tuple["RoutingFailure", ...] = ()  # default for compat; always set by pipeline

    def __post_init__(self) -> None:
        # Wrap plain dicts in MappingProxyType for immutability
        if not isinstance(self.node_layouts, MappingProxyType):
            object.__setattr__(self, "node_layouts", MappingProxyType(self.node_layouts))
        if not isinstance(self.group_layouts, MappingProxyType):
            object.__setattr__(self, "group_layouts", MappingProxyType(self.group_layouts))


def _empty_diagnostics() -> LayoutDiagnostics:
    return LayoutDiagnostics(
        unsupported_options=(),
        route_failures=(),
        warnings=(),
    )


# ── Layout metadata (accompanies FinalizedLayout in CompiledFlowchart) ────────

@dataclass(frozen=True, slots=True)
class LayoutMetadata:
    """Metadata about the layout pass — algorithm used, counts, direction."""
    direction: str          # "TB" | "LR" | "RL" | "BT"
    node_count: int
    group_count: int
    edge_count: int         # original parsed edge count (before routing)
    algorithm: str          # e.g. "LongestPathRanker+BarycentricTransposeOrderer+IsotonicCoordinateAssigner"


# ── Compiled flowchart (shared result of _compile_flowchart) ──────────────────

@dataclass(frozen=True, slots=True)
class CompiledFlowchart:
    """Result of _compile_flowchart() — shared by to_html() and validate()."""
    layout: FinalizedLayout
    validation: "ValidationResult"
    metadata: LayoutMetadata


# ── Geometry validation ────────────────────────────────────────────────────────

def validate_finalized_layout(
    layout: FinalizedLayout,
    metadata: "LayoutMetadata | None" = None,
    clearance_threshold: float = 4.0,
) -> "ValidationResult":
    """Validate a FinalizedLayout against geometry constraints.

    Returns a ValidationResult with errors (hard violations) and warnings
    (soft concerns). All checks operate on the immutable IR only — no HTML parsing.
    """
    errors: list[str] = []
    warnings: list[str] = []

    cw, ch = layout.canvas_bounds.w, layout.canvas_bounds.h

    # 1. Canvas must be positive
    if cw <= 0 or ch <= 0:
        errors.append(f"Non-positive canvas: {cw}×{ch}")
        return ValidationResult(errors=tuple(errors), warnings=tuple(warnings))

    canvas = layout.canvas_bounds

    # 2. routing_failures → one error each
    for rf in layout.routing_failures:
        errors.append(
            f"RoutingFailure for edge {rf.edge_id!r} "
            f"({rf.src_node_id} → {rf.dst_node_id}): {rf.reason}"
        )

    # 2b. Edge-count reconciliation
    if metadata is not None:
        accounted = len(layout.routed_edges) + len(layout.routing_failures)
        if accounted < metadata.edge_count:
            missing = metadata.edge_count - accounted
            errors.append(
                f"Missing route: {missing} edge(s) from parsed source absent from "
                f"routed_edges ({len(layout.routed_edges)}) and routing_failures ({len(layout.routing_failures)})"
            )

    # 3. Each node outer_bounds inside canvas
    for nid, nl in layout.node_layouts.items():
        if nl.is_dummy:
            continue
        if not canvas.contains(nl.outer_bounds):
            errors.append(
                f"Node {nid!r} outer_bounds {nl.outer_bounds} outside canvas {canvas}"
            )

    # 4. Each group boundary_bounds inside canvas
    for gid, gl in layout.group_layouts.items():
        if not canvas.contains(gl.boundary_bounds):
            errors.append(
                f"Group {gid!r} boundary_bounds {gl.boundary_bounds} outside canvas {canvas}"
            )

    # 5–6. Label bounds and route waypoint checks
    for re_obj in layout.routed_edges:
        for lbl in (re_obj.label_layout, re_obj.src_label_layout, re_obj.dst_label_layout):
            if lbl is not None and not canvas.contains(lbl.bounds):
                errors.append(
                    f"Edge {re_obj.edge_id!r} label {lbl.text!r} bounds {lbl.bounds} outside canvas"
                )

        # 13. Route validity
        wps = re_obj.waypoints
        if len(wps) < 2:
            errors.append(f"Edge {re_obj.edge_id!r} has fewer than 2 waypoints")
        else:
            for i in range(len(wps) - 1):
                if wps[i].x == wps[i + 1].x and wps[i].y == wps[i + 1].y:
                    errors.append(
                        f"Edge {re_obj.edge_id!r} has zero-length segment at index {i}"
                    )

    # 7. No two ordinary non-dummy node outer_bounds overlap
    real_nodes = [(nid, nl) for nid, nl in layout.node_layouts.items() if not nl.is_dummy]
    for i in range(len(real_nodes)):
        for j in range(i + 1, len(real_nodes)):
            nid_a, nl_a = real_nodes[i]
            nid_b, nl_b = real_nodes[j]
            if nl_a.outer_bounds.overlaps(nl_b.outer_bounds):
                errors.append(
                    f"Node overlap: {nid_a!r} {nl_a.outer_bounds} overlaps {nid_b!r} {nl_b.outer_bounds}"
                )

    # 8. Each child node inside parent group boundary
    for gid, gl in layout.group_layouts.items():
        for mid in gl.member_ids:
            nl = layout.node_layouts.get(mid)
            if nl is not None and not nl.is_dummy:
                if not gl.boundary_bounds.contains(nl.outer_bounds):
                    errors.append(
                        f"Node {mid!r} outer_bounds {nl.outer_bounds} outside "
                        f"parent group {gid!r} boundary {gl.boundary_bounds}"
                    )

    # 9. Intersecting group-title boxes
    group_label_bounds: list[tuple[str, Rect]] = []
    for gid, gl in layout.group_layouts.items():
        if gl.label_layout is not None:
            # Derive title strip rect: top of boundary, full width, title height
            tb = gl.boundary_bounds
            title_h = gl.label_layout.height + 4.0
            title_rect = Rect(tb.x, tb.y, tb.w, title_h)
            group_label_bounds.append((gid, title_rect))
    for i in range(len(group_label_bounds)):
        for j in range(i + 1, len(group_label_bounds)):
            gid_a, rect_a = group_label_bounds[i]
            gid_b, rect_b = group_label_bounds[j]
            if rect_a.overlaps(rect_b):
                errors.append(
                    f"Group-title overlap: {gid_a!r} title box overlaps {gid_b!r} title box"
                )

    # 10. Port not on declared boundary
    for nid, nl in layout.node_layouts.items():
        for port in nl.ports:
            if not nl.outer_bounds.contains_point(port.position, tolerance=2.0):
                errors.append(
                    f"Node {nid!r} port at {port.position} is not on the node boundary {nl.outer_bounds}"
                )

    # 11. Route through unrelated node interior (rough check: any waypoint inside a non-endpoint node)
    all_node_ids_for_edges = {
        (re_obj.src_node_id, re_obj.dst_node_id) for re_obj in layout.routed_edges
    }
    for re_obj in layout.routed_edges:
        endpoint_ids = {re_obj.src_node_id, re_obj.dst_node_id}
        for nid, nl in layout.node_layouts.items():
            if nl.is_dummy or nid in endpoint_ids:
                continue
            inner = nl.outer_bounds.inflate(-4.0)
            for wp in re_obj.waypoints[1:-1]:  # skip endpoints
                if inner.contains_point(wp):
                    errors.append(
                        f"Edge {re_obj.edge_id!r} waypoint {wp} passes through "
                        f"unrelated node {nid!r} interior"
                    )
                    break

    # 12. Label intersecting unrelated node, title, or another label
    all_labels: list[tuple[str, Rect]] = []
    for re_obj in layout.routed_edges:
        for lbl in (re_obj.label_layout, re_obj.src_label_layout, re_obj.dst_label_layout):
            if lbl is not None:
                all_labels.append((re_obj.edge_id, lbl.bounds))

    for edge_id, lbl_bounds in all_labels:
        # Check against unrelated node bounds
        for nid, nl in layout.node_layouts.items():
            if nl.is_dummy:
                continue
            if lbl_bounds.overlaps(nl.outer_bounds):
                errors.append(
                    f"Edge {edge_id!r} label bounds {lbl_bounds} intersect "
                    f"node {nid!r} outer_bounds {nl.outer_bounds}"
                )

    # Label-label collision
    for i in range(len(all_labels)):
        for j in range(i + 1, len(all_labels)):
            eid_a, lb_a = all_labels[i]
            eid_b, lb_b = all_labels[j]
            if lb_a.overlaps(lb_b):
                errors.append(
                    f"Label collision: edge {eid_a!r} label overlaps edge {eid_b!r} label"
                )

    # 14. Clearance warning
    for i in range(len(real_nodes)):
        for j in range(i + 1, len(real_nodes)):
            _, nl_a = real_nodes[i]
            _, nl_b = real_nodes[j]
            ia = nl_a.outer_bounds.intersection_area(nl_b.outer_bounds)
            if ia == 0.0:
                # Approximate minimum gap
                dx = max(0.0, max(nl_a.outer_bounds.x, nl_b.outer_bounds.x) -
                         min(nl_a.outer_bounds.x1, nl_b.outer_bounds.x1))
                dy = max(0.0, max(nl_a.outer_bounds.y, nl_b.outer_bounds.y) -
                         min(nl_a.outer_bounds.y1, nl_b.outer_bounds.y1))
                gap = min(dx, dy) if dx > 0 and dy > 0 else (dx + dy)
                if 0 < gap < clearance_threshold:
                    warnings.append(
                        f"Tight clearance ({gap:.1f}px) between nodes"
                    )

    return ValidationResult(errors=tuple(errors), warnings=tuple(warnings))


# ── Validation result ─────────────────────────────────────────────────────────

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
