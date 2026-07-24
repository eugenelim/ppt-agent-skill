"""Segment-aware layout validators for the eight-case acceptance harness.

These validators are the reusable acceptance harness that gates the later
items of the "Eight-Case Mermaid Compound and Sequence Parity" initiative.
They are intentionally *separate* from the in-pipeline
``validate_finalized_layout`` (in ``_geometry.py``) so that tightening the
acceptance bar here does not perturb the production render/validation path or
the existing regression suites.

Coordinate convention: css-top-left (origin top-left, y increases downward),
matching ``FinalizedLayout``.

Design notes
------------
- All validators return ``list[str]`` (violation messages), mirroring the
  error-list style of ``validate_finalized_layout``. An empty list means the
  layout satisfied that check.
- ``segment_intersects_rect`` is a Liang–Barsky segment-versus-AABB test: it
  reports whether the *open* segment passes through the rectangle interior,
  so a route that merely grazes a boundary within tolerance does not trip it.
- Negative-coordinate layouts are *translated* into positive space
  (``translate_layout_to_positive``), never clipped — clipping would discard
  geometry the spec requires preserved.
"""
from __future__ import annotations

import dataclasses

from ._geometry import (
    BoundaryGate,
    EdgeLabelLayout,
    FinalizedLayout,
    GroupLayout,
    NodeLayout,
    Point,
    PortLayout,
    Rect,
    RoutedEdge,
)

# Height (px) of a group's title band, measured down from the group boundary
# top edge. Route segments crossing this band are obstructions.
DEFAULT_TITLE_BAND_H = 24.0


# ── Primitive: segment vs axis-aligned rectangle ──────────────────────────────

def segment_intersects_rect(
    p1: Point, p2: Point, rect: Rect, tol: float = 0.0
) -> bool:
    """Return True if the open segment ``p1``→``p2`` passes through ``rect``'s interior.

    The rectangle is shrunk by ``tol`` on every side before the test, so a
    segment that only touches (or comes within ``tol`` of) the boundary is not
    counted as an intersection. Uses the Liang–Barsky parametric clip.
    """
    # A tiny epsilon in addition to tol so a segment collinear with (merely
    # touching) a boundary edge is not counted as an interior crossing.
    eps = 1e-6
    x0, y0 = rect.x + tol + eps, rect.y + tol + eps
    x1, y1 = rect.x1 - tol - eps, rect.y1 - tol - eps
    if x1 <= x0 or y1 <= y0:
        # Degenerate (or fully eaten by tolerance) rectangle has no interior.
        return False

    dx = p2.x - p1.x
    dy = p2.y - p1.y
    t_enter, t_exit = 0.0, 1.0

    # (p, q) pairs for the four clip edges: left, right, top, bottom.
    for p, q in (
        (-dx, p1.x - x0),
        (dx, x1 - p1.x),
        (-dy, p1.y - y0),
        (dy, y1 - p1.y),
    ):
        if abs(p) < 1e-12:
            # Segment parallel to this edge; reject only if wholly outside.
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                if t > t_exit:
                    return False
                if t > t_enter:
                    t_enter = t
            else:
                if t < t_enter:
                    return False
                if t < t_exit:
                    t_exit = t

    return t_enter < t_exit - 1e-9


def _rect_within(inner: Rect, outer: Rect, tol: float) -> bool:
    return (
        inner.x >= outer.x - tol
        and inner.y >= outer.y - tol
        and inner.x1 <= outer.x1 + tol
        and inner.y1 <= outer.y1 + tol
    )


def _on_rect_boundary(p: Point, rect: Rect, tol: float) -> bool:
    """True if point lies on (within ``tol`` of) the rectangle perimeter."""
    on_vert = (abs(p.x - rect.x) <= tol or abs(p.x - rect.x1) <= tol) and (
        rect.y - tol <= p.y <= rect.y1 + tol
    )
    on_horiz = (abs(p.y - rect.y) <= tol or abs(p.y - rect.y1) <= tol) and (
        rect.x - tol <= p.x <= rect.x1 + tol
    )
    return on_vert or on_horiz


def _point_near(a: Point, b: Point, tol: float) -> bool:
    return abs(a.x - b.x) <= tol and abs(a.y - b.y) <= tol


def _segment_point_distance(a: Point, b: Point, p: Point) -> float:
    """Shortest distance from point ``p`` to segment ``a``→``b``."""
    dx, dy = b.x - a.x, b.y - a.y
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        return ((p.x - a.x) ** 2 + (p.y - a.y) ** 2) ** 0.5
    t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    cx, cy = a.x + t * dx, a.y + t * dy
    return ((p.x - cx) ** 2 + (p.y - cy) ** 2) ** 0.5


# ── Negative-coordinate translation (never clip) ──────────────────────────────

def _tp(p: Point, dx: float, dy: float) -> Point:
    return Point(p.x + dx, p.y + dy)


def _translate_port(port: PortLayout, dx: float, dy: float) -> PortLayout:
    # direction is a unit vector — unaffected by translation.
    return dataclasses.replace(port, position=_tp(port.position, dx, dy))


def _translate_label(
    label: EdgeLabelLayout | None, dx: float, dy: float
) -> EdgeLabelLayout | None:
    if label is None:
        return None
    return dataclasses.replace(
        label,
        bounds=label.bounds.translate(dx, dy),
        anchor_point=_tp(label.anchor_point, dx, dy),
    )


def _translate_node(nl: NodeLayout, dx: float, dy: float) -> NodeLayout:
    return dataclasses.replace(
        nl,
        outer_bounds=nl.outer_bounds.translate(dx, dy),
        content_bounds=nl.content_bounds.translate(dx, dy),
        icon_bounds=(nl.icon_bounds.translate(dx, dy) if nl.icon_bounds else None),
        ports=tuple(_translate_port(p, dx, dy) for p in nl.ports),
    )


def _translate_group(gl: GroupLayout, dx: float, dy: float) -> GroupLayout:
    return dataclasses.replace(gl, boundary_bounds=gl.boundary_bounds.translate(dx, dy))


def _translate_edge(e: RoutedEdge, dx: float, dy: float) -> RoutedEdge:
    return dataclasses.replace(
        e,
        waypoints=tuple(_tp(w, dx, dy) for w in e.waypoints),
        src_port=_translate_port(e.src_port, dx, dy),
        dst_port=_translate_port(e.dst_port, dx, dy),
        label_layout=_translate_label(e.label_layout, dx, dy),
        src_label_layout=_translate_label(e.src_label_layout, dx, dy),
        dst_label_layout=_translate_label(e.dst_label_layout, dx, dy),
        junction_points=tuple(_tp(j, dx, dy) for j in e.junction_points),
    )


def _translate_gate(g: BoundaryGate, dx: float, dy: float) -> BoundaryGate:
    return dataclasses.replace(g, point=_tp(g.point, dx, dy))


def required_origin_translation(layout: FinalizedLayout) -> tuple[float, float]:
    """Return ``(dx, dy)`` that shifts all geometry into non-negative space.

    Zero on an axis that is already non-negative. Considers node/group bounds,
    every route waypoint, boundary-gate points, and the canvas itself.
    """
    xs: list[float] = [layout.canvas_bounds.x, layout.visible_bounds.x]
    ys: list[float] = [layout.canvas_bounds.y, layout.visible_bounds.y]

    def _add_rect(r: Rect) -> None:
        xs.append(r.x)
        ys.append(r.y)

    def _add_point(p: Point) -> None:
        xs.append(p.x)
        ys.append(p.y)

    for nl in layout.node_layouts.values():
        _add_rect(nl.outer_bounds)
        _add_rect(nl.content_bounds)
        if nl.icon_bounds is not None:
            _add_rect(nl.icon_bounds)
        for port in nl.ports:
            _add_point(port.position)
    for gl in layout.group_layouts.values():
        _add_rect(gl.boundary_bounds)
    for e in layout.routed_edges:
        for w in e.waypoints:
            _add_point(w)
        for j in e.junction_points:
            _add_point(j)
        for lbl in (e.label_layout, e.src_label_layout, e.dst_label_layout):
            if lbl is not None:
                _add_rect(lbl.bounds)
    for g in layout.boundary_gates:
        _add_point(g.point)
    min_x, min_y = min(xs), min(ys)
    dx = -min_x if min_x < 0 else 0.0
    dy = -min_y if min_y < 0 else 0.0
    return dx, dy


def translate_layout_to_positive(layout: FinalizedLayout) -> FinalizedLayout:
    """Translate a layout so no geometry has negative coordinates.

    Returns the layout unchanged when it is already in positive space.
    Geometry is *shifted*, never clipped or discarded.
    """
    dx, dy = required_origin_translation(layout)
    if dx == 0.0 and dy == 0.0:
        return layout
    return dataclasses.replace(
        layout,
        node_layouts={
            nid: _translate_node(nl, dx, dy)
            for nid, nl in layout.node_layouts.items()
        },
        group_layouts={
            gid: _translate_group(gl, dx, dy)
            for gid, gl in layout.group_layouts.items()
        },
        routed_edges=tuple(_translate_edge(e, dx, dy) for e in layout.routed_edges),
        visible_bounds=layout.visible_bounds.translate(dx, dy),
        canvas_bounds=layout.canvas_bounds.translate(dx, dy),
        boundary_gates=tuple(_translate_gate(g, dx, dy) for g in layout.boundary_gates),
    )


# ── Canvas coverage (every waypoint AND every segment inside canvas) ──────────

def validate_canvas_coverage(layout: FinalizedLayout, tol: float = 1.0) -> list[str]:
    """Every route waypoint and route segment must lie inside the canvas.

    Unlike an endpoints-only check, this examines *all* waypoints (including
    intermediate bends) and every consecutive segment, so an excursion between
    the route's first and last points is caught. Node and group bounds are
    also required to fall within the canvas.
    """
    errors: list[str] = []
    canvas = layout.canvas_bounds

    for e in layout.routed_edges:
        wps = e.waypoints
        for i, wp in enumerate(wps):
            if not canvas.contains_point(wp, tol):
                errors.append(
                    f"Edge {e.edge_id!r} waypoint[{i}] ({wp.x:.1f}, {wp.y:.1f}) "
                    f"outside canvas {canvas}"
                )
        # Segment-level check (spec AC7: complete segments participate). For a
        # convex rectangular canvas both-endpoints-inside implies the whole
        # segment is inside, so this reinforces — never weakens — the waypoint
        # loop above; it makes the "segments, not only waypoints" contract
        # explicit and guards a future non-rectangular canvas notion.
        for i in range(len(wps) - 1):
            a, b = wps[i], wps[i + 1]
            if not (canvas.contains_point(a, tol) and canvas.contains_point(b, tol)):
                errors.append(
                    f"Edge {e.edge_id!r} segment[{i}] ({a.x:.1f},{a.y:.1f})→"
                    f"({b.x:.1f},{b.y:.1f}) leaves canvas {canvas}"
                )

    for nid, nl in layout.node_layouts.items():
        if getattr(nl, "is_dummy", False):
            continue  # routing-artifact bend nodes are not real geometry
        if not _rect_within(nl.outer_bounds, canvas, tol):
            errors.append(f"Node {nid!r} bounds {nl.outer_bounds} outside canvas {canvas}")
    for gid, gl in layout.group_layouts.items():
        if not _rect_within(gl.boundary_bounds, canvas, tol):
            errors.append(f"Group {gid!r} bounds {gl.boundary_bounds} outside canvas {canvas}")

    return errors


# ── Segment-vs-rectangle obstruction ──────────────────────────────────────────

def _group_title_band(gl: GroupLayout, band_h: float = DEFAULT_TITLE_BAND_H) -> Rect:
    b = gl.boundary_bounds
    return Rect(b.x, b.y, b.w, min(band_h, b.h))


def _groups_of_node(layout: FinalizedLayout, node_id: str) -> set[str]:
    return {
        gid
        for gid, gl in layout.group_layouts.items()
        if node_id in gl.member_ids
    }


def validate_segment_obstruction(
    layout: FinalizedLayout, tol: float = 0.5, title_band_h: float = DEFAULT_TITLE_BAND_H
) -> list[str]:
    """Each route segment is tested against unrelated obstacle rectangles.

    Obstacles are: unrelated node interiors, unrelated group interiors, group
    title bands, and other edges' label rectangles. The segment portions that
    legitimately meet an edge's own source/target node (or its endpoint group)
    are excluded by dropping those nodes/groups from the obstacle set.
    """
    errors: list[str] = []

    for e in layout.routed_edges:
        related_nodes = {e.src_node_id, e.dst_node_id}
        endpoint_groups = _groups_of_node(layout, e.src_node_id) | _groups_of_node(
            layout, e.dst_node_id
        )

        obstacles: list[tuple[str, str, Rect]] = []
        for nid, nl in layout.node_layouts.items():
            if getattr(nl, "is_dummy", False):
                continue  # dummy bend nodes lie on routes; not obstacles
            if nid not in related_nodes:
                obstacles.append(("node", nid, nl.outer_bounds))
        for gid, gl in layout.group_layouts.items():
            if gid not in endpoint_groups:
                obstacles.append(("group-interior", gid, gl.boundary_bounds))
            # Title band is an obstruction even for the endpoint's own group.
            obstacles.append(("group-title", gid, _group_title_band(gl, title_band_h)))
        for other in layout.routed_edges:
            if other.edge_id == e.edge_id:
                continue
            for lbl in (
                other.label_layout,
                other.src_label_layout,
                other.dst_label_layout,
            ):
                if lbl is not None:
                    obstacles.append(("edge-label", other.edge_id, lbl.bounds))

        wps = e.waypoints
        for i in range(len(wps) - 1):
            a, b = wps[i], wps[i + 1]
            for kind, oid, rect in obstacles:
                if segment_intersects_rect(a, b, rect, tol):
                    errors.append(
                        f"Edge {e.edge_id!r} segment[{i}] crosses {kind} {oid!r} "
                        f"bounds {rect}"
                    )

    return errors


# ── Compound gate validation ──────────────────────────────────────────────────

def _is_cross_scope(e: RoutedEdge) -> bool:
    return bool(e.source_scope or e.target_scope) and e.source_scope != e.target_scope


def _route_boundary_crossings(e: RoutedEdge, rect: Rect) -> int:
    """Number of times the route transitions in/out of ``rect``."""
    wps = e.waypoints
    if len(wps) < 2:
        return 0
    crossings = 0
    prev_inside = rect.contains_point(wps[0])
    for wp in wps[1:]:
        inside = rect.contains_point(wp)
        if inside != prev_inside:
            crossings += 1
        prev_inside = inside
    return crossings


def _route_touches_point(e: RoutedEdge, p: Point, tol: float) -> bool:
    wps = e.waypoints
    if any(_point_near(w, p, tol) for w in wps):
        return True
    for i in range(len(wps) - 1):
        if _segment_point_distance(wps[i], wps[i + 1], p) <= tol:
            return True
    return False


def validate_compound_gates(layout: FinalizedLayout, tol: float = 1.0) -> list[str]:
    """Cross-scope edges must cross group boundaries only through declared gates.

    For every cross-scope edge: require entry/exit gate records; each gate must
    lie on its group boundary; the route must contain the gate (waypoint or
    within tolerance); the route must cross each gated group exactly as many
    times as it has gates on that group (no leave/re-enter); and the route must
    not pass through an unrelated group interior.
    """
    errors: list[str] = []

    for e in layout.routed_edges:
        if not _is_cross_scope(e):
            continue

        gates = [g for g in layout.boundary_gates if g.edge_id == e.edge_id]
        if not gates:
            errors.append(
                f"Cross-scope edge {e.edge_id!r} "
                f"({e.source_scope}→{e.target_scope}) has no boundary gate"
            )
            continue

        gated_group_ids = {g.group_id for g in gates}
        for g in gates:
            gl = layout.group_layouts.get(g.group_id)
            if gl is None:
                errors.append(
                    f"Gate {g.gate_id!r} references unknown group {g.group_id!r}"
                )
                continue
            if not _on_rect_boundary(g.point, gl.boundary_bounds, tol):
                errors.append(
                    f"Gate {g.gate_id!r} point ({g.point.x:.1f},{g.point.y:.1f}) "
                    f"not on group {g.group_id!r} boundary {gl.boundary_bounds}"
                )
            if not _route_touches_point(e, g.point, tol):
                errors.append(
                    f"Edge {e.edge_id!r} route bypasses gate {g.gate_id!r} "
                    f"at ({g.point.x:.1f},{g.point.y:.1f})"
                )

        # Single-crossing: a gated group must be crossed exactly once per gate on it.
        for gid in gated_group_ids:
            gl = layout.group_layouts.get(gid)
            if gl is None:
                continue
            expected = sum(1 for g in gates if g.group_id == gid)
            actual = _route_boundary_crossings(e, gl.boundary_bounds)
            if actual > expected:
                errors.append(
                    f"Edge {e.edge_id!r} crosses group {gid!r} boundary {actual} "
                    f"times (expected {expected}); leaves and re-enters"
                )

        # Unrelated-group interior crossing.
        for gid, gl in layout.group_layouts.items():
            if gid in gated_group_ids:
                continue
            wps = e.waypoints
            for i in range(len(wps) - 1):
                if segment_intersects_rect(wps[i], wps[i + 1], gl.boundary_bounds, tol):
                    errors.append(
                        f"Edge {e.edge_id!r} segment[{i}] crosses unrelated "
                        f"group {gid!r} interior {gl.boundary_bounds}"
                    )
                    break

    return errors


def all_violations(layout: FinalizedLayout, tol: float = 1.0) -> list[str]:
    """Convenience: run every validator and return the concatenated violations."""
    out: list[str] = []
    out += validate_canvas_coverage(layout, tol)
    out += validate_segment_obstruction(layout, tol)
    out += validate_compound_gates(layout, tol)
    return out
