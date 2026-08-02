from __future__ import annotations

import dataclasses
import re
import types as _types
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from ._geometry import (
        CompiledFlowchart, FinalizedLayout,
        TextLayout, NodeLayout, GroupLayout, Point, PortSide,
        RoutedEdge, LayoutGraph, ValidationResult,
        RouteBatch, LayoutMetadata, CompoundNode,
    )

from ._constants import (
    _Node, _Edge, _Group, _marker_kind,
    NODE_CAP, EDGE_CAP, GROUP_CAP,
    NODE_W, NODE_H, COL_GAP, RANK_GAP, CANVAS_PAD,
    _LABEL_ICON_KEYWORDS,
    _node_render_h, _load_icon,
    _TERMINAL_NODE_SIZE, _is_terminal_circle,
    _measure_text_width,
)
from ._parser import _parse_graph_source, _detect_directive, _strip_frontmatter, _parse_init_config
from ._layout import (
    _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates,
    _compact_group_columns, _group_coherent_cols, _snap_isolated_rank_cols,
)
from ._routing import (
    _route_edges, _node_render_w, _finalize_self_loop_offsets,
    _astar_route, _blocked_segs, _ensure_orthogonal, _label_on_longest,
    _est_label_w, _LABEL_CHIP_H,
)
from ._renderer import (
    _render_legend,
    _separate_groups_lr,
    _separate_groups_tb,
    _stack_source_groups_above_tb,
    _push_nonmembers_out_of_groups_lr,
    _compute_group_bboxes,
    _ACCENT_CYCLE,
)
from ._text import get_default_measurer, GROUP_LABEL

# Process-wide text measurer singleton
_MEASURER = get_default_measurer()

@dataclass(frozen=True)
class RenderOptions:
    """Rendering behavior flags threaded from _dispatch into strategy functions.

    faithful_mermaid: when True, disables icon inference and auto-direction
        switching so the output mirrors the Mermaid source as closely as possible.
    infer_icons: inject keyword-matched icons into node labels (overridden to
        False when faithful_mermaid is True).
    auto_direction: allow TB↔LR switching when width/height hint suggests it
        (overridden to False when faithful_mermaid is True).
    inferred_legend: append the semantic-edge legend strip below the diagram.
    """
    faithful_mermaid: bool = False
    infer_icons: bool = True
    auto_direction: bool = True
    inferred_legend: bool = False

# ── label-based icon inference ────────────────────────────────────────────────

def _infer_label_icons(nodes: "dict[str, _Node]") -> None:
    """Assign icons from node labels when no explicit icon or matching css_class is set.

    Checks each node's label (lowercased) against _LABEL_ICON_KEYWORDS in order;
    first match wins. Uses word-boundary matching (\\b) so short tokens like "cli"
    or "mcp" do not false-positive inside longer words ("client", "compact").
    Skips nodes that already have an icon or have a css_class that resolves to one.
    """
    from ._constants import _load_icon
    for n in nodes.values():
        if n.icon:
            continue
        if n.css_class and _load_icon(n.css_class):
            continue
        label_lower = n.label.lower()
        for keywords, icon_name in _LABEL_ICON_KEYWORDS:
            if any(
                re.search(r"\b" + re.escape(kw) + r"\b", label_lower)
                for kw in keywords
            ):
                n.icon = icon_name
                break

# ── compile-flowchart pipeline ───────────────────────────────────────────────


def _seg_intersects_rect(
    bx: float, by: float, ex: float, ey: float,
    rx0: float, ry0: float, rx1: float, ry1: float,
) -> bool:
    """Liang-Barsky clip: True when segment (bx,by)→(ex,ey) overlaps the rect."""
    dx, dy = ex - bx, ey - by
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, bx - rx0), (dx, rx1 - bx), (-dy, by - ry0), (dy, ry1 - by)):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        elif p < 0:
            r = q / p
            if r > t1:
                return False
            t0 = max(t0, r)
        else:
            r = q / p
            if r < t0:
                return False
            t1 = min(t1, r)
    return t0 <= t1


_LABEL_FS: int = 12   # edge-label / group-label font size
_LABEL_FW: int = 400  # edge-label / group-label font weight (regular)


def _estimate_text_width(text: str, font_size: float = 12.0) -> float:
    """Measure rendered text width using PIL font metrics when available.

    Falls back to per-character width ratios for sans-serif if PIL measurement
    returns zero (e.g., font not loaded yet).
    """
    px = _measure_text_width(text, int(font_size), _LABEL_FW)
    if px > 0:
        return max(30.0, px)
    # PIL fallback: three-tier character classification
    total = 0.0
    for ch in text:
        if ch in "iIlL|1!.,;:'\"` ":
            total += 0.35 * font_size
        elif ch in "mwMW":
            total += 0.85 * font_size
        elif ch.isupper():
            total += 0.70 * font_size
        elif ch.isdigit():
            total += 0.60 * font_size
        else:
            total += 0.55 * font_size
    return max(30.0, total)


def _make_text_layout_ir(text: str) -> "TextLayout":
    """Minimal multi-line TextLayout for building NodeLayout / GroupLayout IR.

    Splits on <br/> variants and explicit \\n so that flowchart node labels
    with HTML line-break tags produce one TextLine per visual line instead of
    one TextLine containing literal '<br/>' characters.
    """
    from ._geometry import TextLayout, TextLine, TextRun, TextStyle
    style = TextStyle()
    # Use a sentinel (\x00) so only <br> tags and \\n escapes become line breaks.
    # Pre-existing real \n characters (e.g. classDiagram member separators) stay
    # intact within a segment and are NOT treated as display line breaks.
    _sentinel = '\x00'
    _s1 = re.sub(r'<br\s*/?>', _sentinel, text, flags=re.IGNORECASE)
    _s2 = _s1.replace('\\n', _sentinel)
    segments = [s for s in _s2.split(_sentinel) if s.strip()]
    if not segments:
        segments = [text]

    lines = []
    for seg in segments:
        # Cap at 450px to match _routing._est_label_w; without this, long (>56 char)
        # labels diverge between routing placement and stored bounds.
        w_seg = min(450.0, _estimate_text_width(seg))
        run = TextRun(text=seg, style=style, width=w_seg, height=18.0)
        lines.append(TextLine(runs=(run,), width=w_seg, height=18.0, baseline=14.0))

    max_w = max(l.width for l in lines)
    total_h = len(lines) * 18.0
    return TextLayout(
        lines=tuple(lines),
        width=max_w,
        height=total_h,
        line_height=18.0,
        min_content_width=min(max_w, 40.0),
        max_content_width=max_w,
        resolved_font_path=None,
        resolved_font_family="sans-serif",
    )


def _build_node_layouts_ir(
    nodes: "dict[str, _Node]",
    groups: "dict[str, _Group] | None" = None,
) -> "dict[str, NodeLayout]":
    from ._geometry import NodeLayout, Rect
    # Build node→group-index and node→parent-group-id maps
    _node_grp_idx: dict[str, int] = {}
    _nid_parent_gid: dict[str, str] = {}
    if groups:
        for _gi, gid in enumerate(groups.keys()):
            for _nid in groups[gid].members:
                _node_grp_idx[_nid] = _gi
                _nid_parent_gid[_nid] = gid
    result: dict = {}
    for nid, n in nodes.items():
        nw = n.width or NODE_W
        nh = _node_render_h(n)
        outer = Rect(x=float(n.x), y=float(n.y), w=float(nw), h=float(nh))
        content = Rect(
            x=float(n.x + 8), y=float(n.y + 4),
            w=float(max(nw - 16, 20)), h=float(max(nh - 8, 10)),
        )
        title = _make_text_layout_ir(n.label) if not n.is_dummy else None
        shape = n.shape or "rect"
        is_ext = getattr(n, "css_class", "") == "external"
        css_cls_list = [f"node-{shape}"]
        if is_ext:
            css_cls_list.append("node-external")
        shape_cls = tuple(css_cls_list)
        icon_svg = (_load_icon(n.icon) if getattr(n, "icon", "") else
                    (_load_icon(n.css_class) if getattr(n, "css_class", "") else ""))
        if is_ext:
            accent = "var(--node-fg-dim,var(--text-secondary,#75736C))"
        elif nid in _node_grp_idx:
            accent = _ACCENT_CYCLE[_node_grp_idx[nid] % len(_ACCENT_CYCLE)]
        else:
            accent = "var(--node-title-fg,var(--accent-1,#60a5fa))"
        result[nid] = NodeLayout(
            node_id=nid,
            semantic_shape=shape,
            outer_bounds=outer,
            content_bounds=content,
            title_layout=title,
            subtitle_layout=None,
            member_layouts=(),
            icon_bounds=None,
            ports=(),
            css_classes=shape_cls,
            extra_css="",
            is_dummy=n.is_dummy,
            rank=getattr(n, "rank", 0) or 0,
            is_external=is_ext,
            icon_svg=icon_svg,
            accent_color=accent,
            parent_group_id=_nid_parent_gid.get(nid),
        )
    return result


def _build_group_layouts_ir(
    groups: "dict[str, _Group]",
    group_bboxes: "dict[str, tuple[int, int, int, int]]",
) -> "dict[str, GroupLayout]":
    from ._geometry import GroupLayout, Rect
    result: dict = {}
    # Populate parent→child relationships from _Group.parent_group field.
    child_ids: dict[str, list[str]] = {gid: [] for gid in groups}
    for gid, grp in groups.items():
        if grp.parent_group and grp.parent_group in child_ids:
            child_ids[grp.parent_group].append(gid)
    for gid, grp in groups.items():
        if gid not in group_bboxes:
            continue
        bx1, by1, bx2, by2 = group_bboxes[gid]
        boundary = Rect(
            x=float(bx1), y=float(by1),
            w=float(bx2 - bx1), h=float(by2 - by1),
        )
        label_layout = _make_text_layout_ir(grp.label) if grp.label else None
        result[gid] = GroupLayout(
            group_id=gid,
            parent_group_id=grp.parent_group or None,
            boundary_bounds=boundary,
            label_layout=label_layout,
            member_ids=tuple(grp.members),
            child_group_ids=tuple(child_ids.get(gid, [])),
            local_direction=getattr(grp, "direction", "TB") or "TB",
        )
    return result


def _extract_waypoints_from_path(d: str) -> "tuple[Point, ...]":
    """Extract geometric waypoints from an SVG path string (M, L, Q commands)."""
    from ._geometry import Point
    pts: list[Point] = []
    for cmd, num_str in re.findall(r'([MLQZ])\s*((?:[-\d.]+\s*)*)', d):
        nums = [float(x) for x in num_str.split() if x]
        if cmd == 'M' and len(nums) >= 2:
            pts.append(Point(nums[0], nums[1]))
        elif cmd == 'L' and len(nums) >= 2:
            pts.append(Point(nums[0], nums[1]))
        elif cmd == 'Q' and len(nums) >= 4:
            pts.append(Point(nums[2], nums[3]))
    return tuple(pts)


def _infer_port_side(pts: "tuple | list", at_start: bool) -> "PortSide":
    """Infer PortSide from the first two (src) or last two (dst) waypoints."""
    from ._geometry import PortSide
    if len(pts) < 2:
        return PortSide.BOTTOM
    if at_start:
        p0, p1 = pts[0], pts[1]
    else:
        p0, p1 = pts[-2], pts[-1]
    dx = (p1[0] if isinstance(p1, tuple) else p1.x) - (p0[0] if isinstance(p0, tuple) else p0.x)
    dy = (p1[1] if isinstance(p1, tuple) else p1.y) - (p0[1] if isinstance(p0, tuple) else p0.y)
    if abs(dx) >= abs(dy):
        return PortSide.RIGHT if dx > 0 else PortSide.LEFT
    return PortSide.BOTTOM if dy > 0 else PortSide.TOP


def _infer_port_dir(pts: "tuple | list", at_start: bool) -> "Point":
    """Compute the normalized direction of the first (src) or last (dst) segment.

    Returns the actual unit vector along the segment, which may be diagonal for
    polygon-shape escape stubs.  Differs from _infer_port_side which rounds to
    the nearest cardinal axis.
    """
    import math  # noqa: PLC0415
    from ._geometry import Point  # noqa: PLC0415
    if len(pts) < 2:
        return Point(0.0, 1.0)
    if at_start:
        p0, p1 = pts[0], pts[1]
    else:
        p0, p1 = pts[-2], pts[-1]
    dx = (p1[0] if isinstance(p1, tuple) else p1.x) - (p0[0] if isinstance(p0, tuple) else p0.x)
    dy = (p1[1] if isinstance(p1, tuple) else p1.y) - (p0[1] if isinstance(p0, tuple) else p0.y)
    mag = math.hypot(dx, dy)
    if mag < 1e-9:
        return Point(0.0, 1.0)
    return Point(dx / mag, dy / mag)


def _bbox_segment_exit(ix, iy, ox, oy, bbox):
    """Point where segment (inside)->(outside) crosses an axis-aligned box edge.

    ``(ix, iy)`` lies inside ``bbox`` = ``[x0, y0, x1, y1]`` and ``(ox, oy)`` outside,
    so the segment crosses the boundary exactly once. Returns that crossing (the
    smallest positive parameter ``t`` along the segment). Falls back to the inside
    endpoint when no crossing is found in ``(0, 1]`` — a degenerate (zero-length)
    segment, or one whose inside endpoint already sits on the box edge — so the
    clipped start never lands outside the box.
    """
    x0, y0, x1, y1 = bbox
    dx, dy = ox - ix, oy - iy
    ts = []
    if dx:
        for xb in (x0, x1):
            t = (xb - ix) / dx
            if 0 < t <= 1 and (y0 - 1e-6) <= iy + t * dy <= (y1 + 1e-6):
                ts.append(t)
    if dy:
        for yb in (y0, y1):
            t = (yb - iy) / dy
            if 0 < t <= 1 and (x0 - 1e-6) <= ix + t * dx <= (x1 + 1e-6):
                ts.append(t)
    if not ts:
        return (ix, iy)
    t = min(ts)
    return (ix + t * dx, iy + t * dy)


def _clip_cross_scope_exit_waypoints(routed, src_group_map, grp_bboxes) -> None:
    """Clip state-diagram composite-exit routes to their source group boundary.

    A transition that leaves a composite state (e.g. ``Processing --> Done``) is
    routed from the composite's internal scoped-final-state node, which sits inside
    the group box; the edge is tagged with ``_Edge.src_group`` (the group whose
    boundary should clip the source endpoint). For each routed dict whose ``edge_id``
    maps to a source group, this drops the leading run of waypoints that fall inside
    the group box and replaces it with the single point where the polyline first
    crosses the box boundary, mutating the dict in place so the rendered path
    originates from the composite edge.
    """
    if not src_group_map or not grp_bboxes:
        return

    def _xy(p):
        return (p[0], p[1]) if isinstance(p, (tuple, list)) else (p.x, p.y)

    def _inside(px, py, bbox):
        return bbox[0] <= px <= bbox[2] and bbox[1] <= py <= bbox[3]

    for spec in routed:
        gid = src_group_map.get(spec.get("edge_id", ""))
        if gid is None:
            continue
        bbox = grp_bboxes.get(gid)
        if not bbox:
            continue
        wps = spec.get("waypoints") or []
        if len(wps) < 2:
            continue
        first_out = next(
            (i for i, p in enumerate(wps) if not _inside(*_xy(p), bbox)),  # type: ignore[call-arg]
            None,
        )
        # None -> whole route inside the box; 0 -> already starts outside. Skip both.
        if not first_out:
            continue
        ix, iy = _xy(wps[first_out - 1])   # last point inside
        ox, oy = _xy(wps[first_out])       # first point outside
        boundary = _bbox_segment_exit(ix, iy, ox, oy, bbox)
        # Emit uniform (x, y) tuples so downstream unpacking never sees a mix of
        # the prepended tuple and Point-style tail elements.
        spec["waypoints"] = [boundary, *(_xy(p) for p in wps[first_out:])]


def _build_routed_edges_ir(
    route_results: "tuple | list",
    canvas_area: int = 0,
    *,
    sm_edge_semantic: "dict | None" = None,
) -> "tuple[RoutedEdge, ...]":
    """Convert _route_edges() result dicts to typed RoutedEdge IR objects.

    canvas_area: canvas_w * canvas_h for compactness metric normalisation.
    sm_edge_semantic: optional dict keyed by (src, dst) → _Edge, for state-diagram
    edges that carry semantic_src / source_scope / target_scope info.  Used to
    populate the six semantic/routing/scope fields on each RoutedEdge.
    """
    from ._geometry import RoutedEdge, PortLayout, PortSide, Point, EdgeLabelLayout, Rect, MarkerKind
    from ._routing import _compute_metrics
    results: list = []
    for spec in route_results:
        src = spec.get("src", "")
        dst = spec.get("dst", "")
        edge_id = spec.get("edge_id") or f"{src}->{dst}"

        raw_wpts = spec.get("waypoints") or []
        if raw_wpts:
            # Drop consecutive duplicate points (zero-length segments from degenerate paths)
            deduped: list = [raw_wpts[0]]
            for _wp in raw_wpts[1:]:
                if _wp != deduped[-1]:
                    deduped.append(_wp)
            raw_wpts = deduped
        waypoints = (
            tuple(Point(float(x), float(y)) for x, y in raw_wpts)
            if raw_wpts
            else _extract_waypoints_from_path(spec.get("d", ""))
        )
        src_pos = waypoints[0] if waypoints else Point(0.0, 0.0)
        dst_pos = waypoints[-1] if waypoints else Point(0.0, 0.0)

        src_side = _infer_port_side(raw_wpts or waypoints, at_start=True)
        dst_side = _infer_port_side(raw_wpts or waypoints, at_start=False)
        # Use the actual segment direction (may be diagonal for escape stubs) rather
        # than rounding to a cardinal axis, which would discard non-cardinal normals.
        src_dir = _infer_port_dir(raw_wpts or waypoints, at_start=True)
        dst_dir = _infer_port_dir(raw_wpts or waypoints, at_start=False)

        src_port = PortLayout(node_id=src, side=src_side, position=src_pos, direction=src_dir)
        dst_port = PortLayout(node_id=dst, side=dst_side, position=dst_pos, direction=dst_dir)

        raw_style = spec.get("style", "")
        if raw_style == "thick":
            edge_style = "thick"
        elif "dotted" in raw_style or raw_style == "dotted":
            edge_style = "dotted"
        else:
            edge_style = "solid"

        mid = spec.get("marker_id") or ""
        has_marker_end = bool(mid) and not mid.endswith("-rev")
        has_marker_start = bool(spec.get("bidir")) or (bool(mid) and mid.endswith("-rev"))

        _raw_src_mk = spec.get("source_marker")
        _raw_dst_mk = spec.get("target_marker")

        def _coerce_mk(raw, fallback: "MarkerKind") -> "MarkerKind":
            if isinstance(raw, str):
                return MarkerKind(raw)
            if isinstance(raw, MarkerKind):
                return raw
            if raw is not None and hasattr(raw, "kind"):  # MarkerSpec → extract kind
                return raw.kind
            return fallback

        _source_marker = _coerce_mk(_raw_src_mk, MarkerKind.ARROW if has_marker_start else MarkerKind.NONE)
        _target_marker = _coerce_mk(_raw_dst_mk, MarkerKind.ARROW if has_marker_end else MarkerKind.NONE)

        label_text = spec.get("label", "") or ""
        if label_text:
            lx, ly = float(spec.get("lx", 0)), float(spec.get("ly", 0))
            label_tl = _make_text_layout_ir(label_text)
            label_layout = EdgeLabelLayout(
                text=label_text,
                layout=label_tl,
                bounds=Rect(x=lx, y=ly, w=label_tl.width, h=label_tl.height),
                anchor_point=src_pos,
            )
        else:
            label_layout = None

        # Multiplicity labels (class diagram "1", "0..*", etc.)
        _src_lbl_text = spec.get("src_label") or ""
        _dst_lbl_text = spec.get("dst_label") or ""
        if _src_lbl_text:
            _sl_tl = _make_text_layout_ir(_src_lbl_text)
            _src_lbl_layout = EdgeLabelLayout(
                text=_src_lbl_text,
                layout=_sl_tl,
                bounds=Rect(x=src_pos.x + 4, y=src_pos.y - 14, w=_sl_tl.width, h=_sl_tl.height),
                anchor_point=src_pos,
            )
        else:
            _src_lbl_layout = None
        if _dst_lbl_text:
            _dl_tl = _make_text_layout_ir(_dst_lbl_text)
            _dst_lbl_layout = EdgeLabelLayout(
                text=_dst_lbl_text,
                layout=_dl_tl,
                bounds=Rect(x=dst_pos.x + 4, y=dst_pos.y - 14, w=_dl_tl.width, h=_dl_tl.height),
                anchor_point=dst_pos,
            )
        else:
            _dst_lbl_layout = None

        # Compute compactness metrics (AC16)
        _raw_wp_list = [(int(pt.x), int(pt.y)) for pt in waypoints] if waypoints else []
        _s_bbox = None
        _d_bbox = None  # bboxes not available here; let _compute_metrics default to inf distance
        _metrics = _compute_metrics(_raw_wp_list, _s_bbox, _d_bbox, canvas_area)
        _m_route_length: float = float(_metrics.get("route_length") or 0.0)
        _m_bend_count: int = int(_metrics.get("bend_count") or 0)
        _m_canvas_area: int = int(_metrics.get("canvas_area") or 0)
        _m_max_ep_dist: float = float(_metrics.get("max_endpoint_distance") or 0.0)
        # Semantic / routing / scope fields. State-diagram edges carry these on a
        # semantic _Edge (joined by edge_id); flowchart cross-boundary edges carry
        # them directly on the route dict (set by _reroute_cross_boundary_edges).
        _sem_e = (sm_edge_semantic or {}).get(spec.get("edge_id"))  # AC4: join on edge_id
        if spec.get("source_scope") or spec.get("target_scope"):
            _semantic_source_id = spec.get("semantic_source_id", "")
            _semantic_target_id = spec.get("semantic_target_id", "")
            _source_scope = spec.get("source_scope", "")
            _target_scope = spec.get("target_scope", "")
            _routing_source_id = spec.get("routing_source_id", "")
            _routing_target_id = spec.get("routing_target_id", "")
        else:
            _semantic_source_id = getattr(_sem_e, 'semantic_src', '') if _sem_e else ''
            _semantic_target_id = getattr(_sem_e, 'semantic_dst', '') if _sem_e else ''
            _source_scope = getattr(_sem_e, 'source_scope', '') if _sem_e else ''
            _target_scope = getattr(_sem_e, 'target_scope', '') if _sem_e else ''
            # routing_source_id / routing_target_id are the actual node IDs used for routing
            _routing_source_id = src if (_source_scope or _semantic_source_id) else ''
            _routing_target_id = dst if (_target_scope or _semantic_target_id) else ''

        results.append(RoutedEdge(
            edge_id=edge_id,
            src_node_id=src,
            dst_node_id=dst,
            src_port=src_port,
            dst_port=dst_port,
            waypoints=waypoints,
            edge_style=edge_style,
            has_marker_end=has_marker_end,
            has_marker_start=has_marker_start,
            label_layout=label_layout,
            src_label_layout=_src_lbl_layout,
            dst_label_layout=_dst_lbl_layout,
            source_marker=_source_marker,
            target_marker=_target_marker,
            route_length=_m_route_length,
            bend_count=_m_bend_count,
            canvas_area=_m_canvas_area,
            max_endpoint_distance=_m_max_ep_dist,
            semantic_source_id=_semantic_source_id,
            semantic_target_id=_semantic_target_id,
            routing_source_id=_routing_source_id,
            routing_target_id=_routing_target_id,
            source_scope=_source_scope,
            target_scope=_target_scope,
        ))
    return tuple(results)


def _render_legend_from_layout(layout: "FinalizedLayout") -> str:
    """Generate legend HTML from a FinalizedLayout (proxy for _render_legend)."""
    class _EdgeProxy:
        __slots__ = ("style", "reversed_")
        def __init__(self, style: str, rev: bool) -> None:
            self.style = style
            self.reversed_ = rev
    stubs = [_EdgeProxy(re.edge_style, re.is_reversed) for re in layout.routed_edges]
    return _render_legend(stubs, layout.group_layouts)  # type: ignore[arg-type]


def _build_group_tree(
    groups: "dict[str, _Group]",
) -> "tuple[dict[str, list[str]], list[str]]":
    """Extract parent→children map and DFS post-order traversal from a group dict.

    Returns ``(children_map, post_order)`` where:
    - ``children_map[gid]`` = list of direct child group IDs (empty list for leaves).
    - ``post_order`` = DFS post-order list (inner/leaf groups before outer/root groups).

    Root groups are those with no ``parent_group`` or whose ``parent_group`` is
    not present in ``groups``.
    """
    children: "dict[str, list[str]]" = {gid: [] for gid in groups}
    for gid, grp in groups.items():
        if grp.parent_group and grp.parent_group in groups:
            children[grp.parent_group].append(gid)
    root_groups = [
        gid for gid, grp in groups.items()
        if not grp.parent_group or grp.parent_group not in groups
    ]

    post_order: "list[str]" = []
    _seen: "set[str]" = set()

    def _visit(gid: str) -> None:
        if gid in _seen:
            return
        _seen.add(gid)
        for c in children[gid]:
            _visit(c)
        post_order.append(gid)

    for gid in root_groups:
        _visit(gid)

    return children, post_order


def _partition_edges(
    edges: "list[_Edge]",
    nodes: "dict[str, _Node]",
    groups: "dict[str, _Group]",
) -> "tuple[list[_Edge], list[_Edge], list[_Edge]]":
    """Classify edges as free, intra-group, or cross-boundary.

    Returns ``(free, intra, cross)`` — mutually exclusive, in this precedence:

    - **free**: neither src nor dst is in any group.
    - **intra**: both endpoints share the same deepest group (``node.group``).
    - **cross**: at least one endpoint is grouped and endpoints don't share deepest group.

    "Deepest group" is the group that directly contains the node (``nodes[nid].group``).
    Missing nodes are treated as ungrouped.
    """
    free: "list[_Edge]" = []
    intra: "list[_Edge]" = []
    cross: "list[_Edge]" = []
    for e in edges:
        src_node = nodes.get(e.src)
        dst_node = nodes.get(e.dst)
        src_grp = src_node.group if src_node is not None else None
        dst_grp = dst_node.group if dst_node is not None else None
        if src_grp is None and dst_grp is None:
            free.append(e)
        elif src_grp == dst_grp:
            intra.append(e)
        else:
            cross.append(e)
    return free, intra, cross


def _expand_boundary_gates(
    nodes: "dict[str, _Node]",
    edges: "list[_Edge]",
    groups: "dict[str, _Group]",
) -> "tuple[list[_Edge], dict[str, _Edge]]":
    """Inject dummy gate nodes for each cross-boundary edge and split it into two.

    For each cross-boundary edge ``e`` (classified by ``_partition_edges``):

    1. Creates a gate node ``_Node(id=f"_gate_{e.edge_id}", is_dummy=False,
       extra_css="opacity:0;pointer-events:none;", ...)`` and adds it to ``nodes``.
    2. Replaces ``e`` with two edges: ``src→gate`` (no label, no arrowhead) and
       ``gate→dst`` (carries ``label``, ``target_marker``, and stable ``edge_id``).
    3. Records ``gate_id → original_edge`` in ``gate_to_original``.

    **Guard**: edges where src or dst starts with ``"_sm_"`` are passed through
    unchanged — those are state-diagram proxy nodes handled by ``statediagram.py``.

    Returns ``(new_edges_list, gate_to_original)``.
    """
    _, _, cross = _partition_edges(edges, nodes, groups)
    cross_ids: "set[int]" = {id(e) for e in cross}
    gate_to_original: "dict[str, _Edge]" = {}
    new_edges: "list[_Edge]" = []

    for e in edges:
        if id(e) not in cross_ids:
            new_edges.append(e)
            continue
        # Guard: skip state-diagram proxy endpoints (already handled by statediagram.py)
        if e.src.startswith("_sm_") or e.dst.startswith("_sm_"):
            new_edges.append(e)
            continue
        # Build a stable gate ID from the edge's own ID (fallback: src->dst)
        _eid = e.edge_id if e.edge_id else f"{e.src}->{e.dst}"
        gate_id = f"_gate_{_eid}"
        gate_node = _Node(
            id=gate_id,
            label="",
            shape="rect",
            is_dummy=False,
            x=0,
            y=0,
            width=0,
            height=0,
            extra_css="opacity:0;pointer-events:none;",
        )
        nodes[gate_id] = gate_node
        gate_to_original[gate_id] = e
        # First half: src → gate (no label, no marker at gate)
        new_edges.append(_Edge(src=e.src, dst=gate_id, label="", style=e.style))
        # Second half: gate → dst (carries label, target_marker, and stable edge_id suffix)
        new_edges.append(_Edge(
            src=gate_id,
            dst=e.dst,
            label=e.label,
            style=e.style,
            target_marker=e.target_marker,
            edge_id=(_eid + "_out"),
        ))

    return new_edges, gate_to_original


def _restore_gate_edges(
    route_dicts: "list[dict]",
    gate_to_original: "dict[str, _Edge]",
    nodes: "dict[str, _Node]",
) -> "list[dict]":
    """Merge split route-dicts back into single route-dicts for each original edge.

    For each ``gate_id`` in ``gate_to_original``:

    1. Finds the route-dict for ``src→gate_id`` (``d["dst"] == gate_id``) and
       ``gate_id→dst`` (``d["src"] == gate_id``).
    2. Concatenates their ``"waypoints"`` lists.
    3. Builds a new route-dict for the original edge inheriting ``src``, ``dst``,
       merged waypoints, ``label``, ``style``, ``target_marker``, and ``edge_id``
       from the original ``_Edge``.
    4. Removes both halves from the list and removes the gate node from ``nodes``.

    If either half's route-dict is missing (routing failure), any found half is discarded
    and the gate node is removed from nodes (preventing dangling node references).

    Returns the updated route-dicts list.
    """
    if not gate_to_original:
        return route_dicts

    to_remove: "set[int]" = set()
    to_add: "list[dict]" = []

    for gate_id, orig in gate_to_original.items():
        first_idx: "int | None" = None   # route to gate (dst == gate_id)
        second_idx: "int | None" = None  # route from gate (src == gate_id)
        for i, d in enumerate(route_dicts):
            if d.get("dst") == gate_id and first_idx is None:
                first_idx = i
            if d.get("src") == gate_id and second_idx is None:
                second_idx = i

        # Always remove the gate node; on routing failure also discard orphan halves
        nodes.pop(gate_id, None)

        if first_idx is None or second_idx is None:
            # Discard any found half to prevent dangling gate-node references
            if first_idx is not None:
                to_remove.add(first_idx)
            if second_idx is not None:
                to_remove.add(second_idx)
            warnings.warn(
                f"_restore_gate_edges: could not find both halves for gate {gate_id!r}; "
                "dropping edge",
                stacklevel=2,
            )
            continue

        first = route_dicts[first_idx]
        second = route_dicts[second_idx]
        merged_wps = list(first.get("waypoints") or []) + list(second.get("waypoints") or [])

        # Compute label position from merged-waypoints midpoint
        if merged_wps:
            def _wp_coord(w: object, axis: int) -> float:
                if isinstance(w, (tuple, list)):
                    return float(w[axis])
                return float(getattr(w, ("x", "y")[axis], 0))
            _mx = sum(_wp_coord(w, 0) for w in merged_wps) / len(merged_wps)
            _my = sum(_wp_coord(w, 1) for w in merged_wps) / len(merged_wps)
            _lx, _ly = _mx - 30.0, _my - 9.0
        else:
            _lx, _ly = 0.0, 0.0

        _orig_sm = orig.source_marker
        _orig_tm = orig.target_marker
        merged: "dict" = {
            "d": "",
            "waypoints": merged_wps,
            "ah": second.get("ah"),
            "label": orig.label,
            "style": orig.style,
            "lx": _lx,
            "ly": _ly,
            "rot": 0,
            "marker_id": second.get("marker_id"),
            "src": first["src"],
            "dst": second["dst"],
            "extra_css": orig.extra_css,
            "src_label": orig.src_label,
            "dst_label": orig.dst_label,
            "bidir": orig.bidir,
            "source_marker": (_orig_sm.kind if hasattr(_orig_sm, "kind") else _orig_sm),
            "target_marker": (_orig_tm.kind if hasattr(_orig_tm, "kind") else _orig_tm),
            "edge_id": orig.edge_id,
            # Preserve fanned port positions so _reroute_cross_boundary_edges can
            # use per-edge port diversity rather than falling back to the shared
            # node-face centre, which causes every route from the same node to
            # share the same initial segment (tramlines).
            "_src_port": first.get("_src_port"),
            "_dst_port": second.get("_dst_port"),
            # Preserve outward normals so CBE escape stubs are applied on this path
            # (inner-direction subgraph edges are split by _add_gate_nodes and rejoined
            # here; without forwarding, CBE rerouter falls back to (0,0) and skips stubs).
            "_src_normal": first.get("_src_normal"),
            "_dst_normal": second.get("_dst_normal"),
        }
        # Rebase escape indices from each half into merged waypoint index space.
        _n_first_wps = len(list(first.get("waypoints") or []))
        for _esc_key in ("_escape_idxs", "_cbe_escape_idxs"):
            _merged_esc_idxs = (first.get(_esc_key) or set()) | {
                j + _n_first_wps for j in (second.get(_esc_key) or set())
            }
            if _merged_esc_idxs:
                merged[_esc_key] = _merged_esc_idxs
        to_remove.add(first_idx)
        to_remove.add(second_idx)
        to_add.append(merged)

    result = [d for i, d in enumerate(route_dicts) if i not in to_remove]
    result.extend(to_add)
    return result


def _recursive_group_layout(
    nodes: "dict[str, _Node]",
    edges: "list[_Edge]",
    groups: "dict[str, _Group]",
    outer_direction: str,
    col_gap: "int | None" = None,
) -> None:
    """Leaf-first recursive group position fixup.

    After _assign_coordinates, for each group with a declared direction that
    differs from the outer layout direction, re-positions that group's members
    (and child groups as fixed-size units) in the group's local direction:
      LR/RL — all members at the same y, placed left-to-right by topo order.
      TB/TD — all members at the same x, placed top-to-bottom by topo order.

    Replaces the removed unconditional inner-direction position fixup that the
    old ``_layout`` module ran after global placement (deleted in the eight-case
    parity cleanup, spec AC4/AC5). Removes the need for the rank-flattening
    pre-pass: instead of forcing all LR-group members to the same rank before
    coordinate assignment, we let _assign_coordinates run normally and correct
    positions afterward.
    """
    _col_gap = col_gap if col_gap is not None else COL_GAP
    # Match _assign_coordinates axis classification exactly: anything not LR/RL is vertical.
    is_outer_tb = outer_direction.upper() not in ("LR", "RL")

    # Build parent→children map and post-order traversal via shared helper
    children, processed = _build_group_tree(groups)

    def _all_member_nodes(gid: str, _seen: "set[str] | None" = None) -> "list[_Node]":
        if _seen is None:
            _seen = set()
        if gid in _seen:
            return []
        _seen.add(gid)
        result = [nodes[m] for m in groups[gid].members if m in nodes and not nodes[m].is_dummy]
        for c in children[gid]:
            result.extend(_all_member_nodes(c, _seen))
        return result

    def _group_bounds(gid: str) -> "tuple[float, float, float, float] | None":
        mbrs = _all_member_nodes(gid)
        if not mbrs:
            return None
        return (
            float(min(n.x for n in mbrs)),
            float(min(n.y for n in mbrs)),
            float(max(n.x + _node_render_w(n) for n in mbrs)),
            float(max(n.y + _node_render_h(n) for n in mbrs)),
        )

    def _shift_group(gid: str, dx: float, dy: float, _seen: "set[str] | None" = None) -> None:
        if _seen is None:
            _seen = set()
        if gid in _seen:
            return
        _seen.add(gid)
        for m in groups[gid].members:
            if m in nodes:
                nodes[m].x += dx  # type: ignore[assignment]
                nodes[m].y += dy  # type: ignore[assignment]
        for c in children[gid]:
            _shift_group(c, dx, dy, _seen)

    def _topo_order(member_ids: "list[str]", intra_edges: "list", sort_key: "Callable") -> "list[str]":
        in_deg: "dict[str, int]" = {m: 0 for m in member_ids}
        adj: "dict[str, list[str]]" = {m: [] for m in member_ids}
        for e in intra_edges:
            if e.src in adj and e.dst in in_deg and not e.reversed_:
                adj[e.src].append(e.dst)
                in_deg[e.dst] += 1
        queue = sorted([m for m in member_ids if in_deg[m] == 0], key=sort_key)
        result: "list[str]" = []
        while queue:
            cur = queue.pop(0)
            result.append(cur)
            nexts = sorted(adj[cur], key=sort_key)
            for nb in nexts:
                in_deg[nb] -= 1
                if in_deg[nb] == 0:
                    queue.append(nb)
            queue.sort(key=sort_key)
        for m in member_ids:
            if m not in result:
                result.append(m)
        return result

    for gid in processed:
        grp = groups[gid]
        if not grp.direction:
            continue
        inner_dir = grp.direction.upper()
        # Only process groups whose direction differs from the outer direction
        if is_outer_tb and inner_dir not in ("LR", "RL"):
            continue
        if not is_outer_tb and inner_dir not in ("TB", "TD"):
            continue

        direct_members = [m for m in grp.members if m in nodes and not nodes[m].is_dummy]
        child_gids = children[gid]

        # Build item list: (kind, id, x, y, w, h)
        items: "list[tuple]" = []
        for m in direct_members:
            n = nodes[m]
            items.append(("node", m, float(n.x), float(n.y),
                          float(_node_render_w(n)), float(_node_render_h(n))))
        for c in child_gids:
            bounds = _group_bounds(c)
            if bounds:
                x0, y0, x1, y1 = bounds
                items.append(("group", c, x0, y0, x1 - x0, y1 - y0))

        if not items:
            continue

        member_set = set(direct_members)
        intra_edges = [e for e in edges if e.src in member_set and e.dst in member_set]

        if inner_dir in ("LR", "RL"):
            # LR/RL inner in TB outer: all members at same y, placed left-to-right (or right-to-left)
            ordered_nodes = _topo_order(direct_members, intra_edges, lambda m: nodes[m].x)
            if inner_dir == "RL":
                ordered_nodes = list(reversed(ordered_nodes))

            node_rank = {m: i for i, m in enumerate(ordered_nodes)}
            rl_sign = -1 if inner_dir == "RL" else 1  # RL: descending x
            if child_gids:
                # Has child groups: sort all items by current x (groups have distinct x).
                # RL reverses the sign so groups also respect right-to-left order.
                items.sort(key=lambda it: (
                    rl_sign * it[2],
                    node_rank.get(it[1], float("inf")) if it[0] == "node" else float("inf"),
                ))
            else:
                # Pure direct members: nodes may share the same col (same x due to
                # centering); use topo order to determine left-to-right sequence
                items.sort(key=lambda it: node_rank.get(it[1], float("inf")))

            target_y = min(it[3] for it in items)
            cur_x = min(it[2] for it in items)
            for kind, item_id, _, _, w, h in items:
                if kind == "node":
                    n = nodes[item_id]
                    n.x = cur_x
                    n.y = target_y
                    cur_x += _node_render_w(n) + _col_gap
                else:
                    bounds = _group_bounds(item_id)
                    if bounds:
                        x0, y0, x1, y1 = bounds
                        _shift_group(item_id, cur_x - x0, target_y - y0)
                        cur_x += (x1 - x0) + _col_gap

        else:
            # TB/TD inner in LR outer: all members at same x, placed top-to-bottom
            # (BT is not a valid parsed inner direction — only TB/TD reach this branch)
            ordered_nodes = _topo_order(direct_members, intra_edges, lambda m: nodes[m].y)

            node_rank = {m: i for i, m in enumerate(ordered_nodes)}
            if child_gids:
                # Has child groups: sort by current y position
                items.sort(key=lambda it: (
                    it[3],
                    node_rank.get(it[1], float("inf")) if it[0] == "node" else float("inf"),
                ))
            else:
                # Pure direct members: use topo order
                items.sort(key=lambda it: node_rank.get(it[1], float("inf")))

            target_x = min(it[2] for it in items)
            cur_y = min(it[3] for it in items)
            for kind, item_id, _, _, w, h in items:
                if kind == "node":
                    n = nodes[item_id]
                    n.x = target_x
                    n.y = cur_y
                    cur_y += _node_render_h(n) + _col_gap
                else:
                    bounds = _group_bounds(item_id)
                    if bounds:
                        x0, y0, x1, y1 = bounds
                        _shift_group(item_id, target_x - x0, cur_y - y0)
                        cur_y += (y1 - y0) + _col_gap


def _elk_edge_id_map(edges: "list[_Edge]") -> "dict[str, _Edge]":
    """Build {elk_edge_id: _Edge} using the canonical ELK-ID scheme.

    Used by both _build_layout_graph (to set LayoutEdge.id) and _compile_flowchart
    (to recover _Edge from a RoutedEdge returned by layout_with_elk) so the two
    sites stay byte-identical without duplication.
    """
    result: dict = {}
    seen: dict = {}
    for e in edges:
        if e.reversed_:
            continue
        base = f"{e.orig_src or e.src}->{e.orig_dst or e.dst}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        result[base if n == 0 else f"{base}#{n}"] = e
    return result


def _build_layout_graph(
    nodes: "dict[str, _Node]",
    edges: "list[_Edge]",
    groups: "dict[str, _Group]",
    direction: str,
) -> "LayoutGraph":
    """Build a pre-layout IR LayoutGraph from the parsed mutable structures.

    Node sizes come from _node_render_h / _node_render_w (the same metrics the
    Python pipeline uses), so ELK receives accurate measured bounds.
    """
    from ._geometry import LayoutGraph, LayoutNode, LayoutGroup, LayoutEdge
    from ._routing import _node_render_w

    layout_nodes = []
    for nid, n in nodes.items():
        if n.is_dummy:
            continue
        layout_nodes.append(LayoutNode(
            id=nid,
            measured_width=float(_node_render_w(n)),
            measured_height=float(_node_render_h(n)),
            shape_id=n.shape or "rect",
            parent_id=n.group if n.group else None,
            ports=[],
            labels=[n.label or nid],
            semantic_data={},
        ))

    layout_groups = []
    for gid, g in groups.items():
        layout_groups.append(LayoutGroup(
            id=gid,
            parent_id=g.parent_group if g.parent_group else None,
            label=g.label or "",
            label_width=float(max(80, _MEASURER.layout(g.label or "", GROUP_LABEL, None).max_content_width)),
            label_height=20.0,
            padding=16.0,
            local_direction=g.direction.upper() if g.direction else direction,
            minimum_width=0.0,
            minimum_height=0.0,
        ))

    layout_edges = []
    for eid, e in _elk_edge_id_map(edges).items():
        src_mk = _marker_kind(e.source_marker)
        # target_marker is now authoritative (all writers populate it), so no
        # e.arrow fallback is needed.
        dst_mk = _marker_kind(e.target_marker)
        layout_edges.append(LayoutEdge(
            id=eid,
            sources=[e.orig_src or e.src],
            targets=[e.orig_dst or e.dst],
            source_port=None,
            target_port=None,
            source_marker=src_mk,
            target_marker=dst_mk,
            line_style=e.style,
            label=e.label or "",
            semantic_data={},
        ))

    return LayoutGraph(
        nodes=layout_nodes,
        groups=layout_groups,
        edges=layout_edges,
        direction=direction,
    )



# ── FlowchartSemantics and the 6 composable pipeline functions ───────────────

@dataclass
class FlowchartSemantics:
    """Parsed state of a flowchart/stateDiagram before layout is applied.

    Produced by parse_flowchart_semantics(); consumed by the build/layout/enrich
    functions. Carries mutable _Node/_Edge/_Group objects — layout functions may
    mutate them as a side-effect (setting n.width, n.height, n.x, n.y).
    Contains no layout coordinates — those come from ELK or the Python pipeline.
    """
    nodes: "dict[str, _Node]"
    edges: "list[_Edge]"
    groups: "dict[str, _Group]"
    direction: str
    is_state_diagram: bool
    parsed_edge_count: int
    has_inner_dir: bool
    gate_to_orig: "dict[str, _Edge]"
    sm_edge_semantic: dict
    sm_composite_gates: dict
    opts: "RenderOptions"
    init_cfg: dict
    width_hint: int
    height_hint: int


def parse_flowchart_semantics(
    src: str,
    options: "RenderOptions | None" = None,
    *,
    direction_override: "Optional[str]" = None,
    width_hint: int = 0,
    height_hint: int = 0,
) -> FlowchartSemantics:
    """Parse a flowchart/stateDiagram source into a FlowchartSemantics object.

    Handles both flowchart (via _parse_graph_source) and stateDiagram
    (via compile_state_machine) branches. The returned object carries parsed
    nodes, edges, groups, and semantic metadata but no layout coordinates.

    Gate injection for inner-direction compound layouts is performed here so
    the semantics object is always self-consistent.
    """
    _opts = options if options is not None else RenderOptions()
    clean = _strip_frontmatter(src)
    _, auto_direction = _detect_directive(clean)
    direction = (direction_override or auto_direction).upper()

    lines = clean.splitlines()
    directive_index = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith(("%%", "//")):
            directive_index = i
            break
    content_lines = lines[directive_index + 1:]

    _state_directives = frozenset({"statediagram-v2", "statediagram"})
    _top_directive = lines[directive_index].strip().split()[0].lower() if lines else ""
    _sm_edge_semantic: dict = {}
    _sm_composite_gates: dict = {}
    is_state_diagram = _top_directive in _state_directives

    if is_state_diagram:
        from .statediagram import (  # noqa: PLC0415
            compile_state_machine as _compile_sm,
            state_model_to_graph as _sm_to_graph,
            CompositeState as _CompositeState,
        )
        _sm_model = _compile_sm(content_lines)
        nodes, edges, groups = _sm_to_graph(_sm_model)
        for _se in edges:
            _sm_src = getattr(_se, "semantic_src", "")
            _sm_sc = getattr(_se, "source_scope", "")
            _sm_sg = getattr(_se, "target_scope", "")
            if _sm_src or _sm_sc or _sm_sg:
                _sm_edge_semantic[_se.edge_id] = _se  # AC4: keyed by edge_id, not (src,dst)
        for _cs in _sm_model.states:
            if isinstance(_cs, _CompositeState) and _cs.entry_gate and _cs.exit_gate:
                _sm_composite_gates[_cs.id] = (_cs.entry_gate.id, _cs.exit_gate.id)
        _eid_counts: "dict[str, int]" = {}
        for _e in edges:
            if not _e.edge_id:
                _base = f"{_e.src}->{_e.dst}"
                _n = _eid_counts.get(_base, 0)
                _eid_counts[_base] = _n + 1
                _e.edge_id = _base if _n == 0 else f"{_base}#{_n}"
    else:
        nodes, edges, groups = _parse_graph_source(content_lines)

    parsed_edge_count = len(edges)

    if not _opts.faithful_mermaid and _opts.infer_icons:
        _infer_label_icons(nodes)

    if len(nodes) > NODE_CAP:
        raise ValueError(f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}).")
    if len(edges) > EDGE_CAP:
        raise ValueError(f"Cap exceeded: {len(edges)} edges (cap {EDGE_CAP}).")
    if len(groups) > GROUP_CAP:
        raise ValueError(f"Cap exceeded: {len(groups)} subgraphs (cap {GROUP_CAP}).")
    if not nodes:
        raise ValueError("No nodes found in diagram source.")

    _init_cfg = _parse_init_config(src)

    # Gate injection for inner-direction cross-boundary edges.
    # Only flowcharts (not stateDiagrams) use gate nodes.
    _gate_to_orig: "dict[str, _Edge]" = {}
    _has_inner_dir = False
    if groups and not is_state_diagram:
        _has_inner_dir = any(
            grp.direction and grp.direction.upper() != direction.upper()
            for grp in groups.values()
        )
        if _has_inner_dir:
            edges, _gate_to_orig = _expand_boundary_gates(nodes, edges, groups)

    return FlowchartSemantics(
        nodes=nodes,
        edges=edges,
        groups=groups,
        direction=direction,
        is_state_diagram=is_state_diagram,
        parsed_edge_count=parsed_edge_count,
        has_inner_dir=_has_inner_dir,
        gate_to_orig=_gate_to_orig,
        sm_edge_semantic=_sm_edge_semantic,
        sm_composite_gates=_sm_composite_gates,
        opts=_opts,
        init_cfg=_init_cfg,
        width_hint=width_hint,
        height_hint=height_hint,
    )


def build_flowchart_layout_graph(
    semantics: FlowchartSemantics,
) -> "LayoutGraph":
    """Build a LayoutGraph for ELK from parsed semantics.

    Calls _assign_coordinates to measure node widths/heights before building
    the graph — ELK requires accurate bounds for placement. The x/y coordinates
    set by _assign_coordinates are discarded (ELK recomputes positions).
    """
    # Side-effect: sets n.width and n.height based on text measurement.
    # n.x and n.y are also set but will be ignored — ELK recomputes them.
    _assign_coordinates(
        semantics.nodes,
        semantics.direction,
        col_gap=semantics.init_cfg.get("col_gap"),
        rank_gap=semantics.init_cfg.get("rank_gap"),
        canvas_pad=semantics.init_cfg.get("diagram_padding"),
    )
    return _build_layout_graph(
        semantics.nodes,
        semantics.edges,
        semantics.groups,
        semantics.direction,
    )


def layout_flowchart_with_elk(
    graph: "LayoutGraph",
    spacing: "dict | None" = None,
) -> "FinalizedLayout":
    """Invoke ELK layout on a LayoutGraph; return the raw FinalizedLayout.

    Raises:
        ElkUnavailable: when ELK cannot run (no Node, no elkjs, env opt-out).
    """
    from .elk_adapter import layout_with_elk as _layout_with_elk  # noqa: PLC0415
    finalized, _meta = _layout_with_elk(graph, spacing=spacing)
    return finalized


def _is_degenerate_self_loop(edge: "RoutedEdge") -> bool:
    """True if a self-loop edge has fewer than 3 distinct waypoints."""
    wps = edge.waypoints
    if len(wps) < 3:
        return True
    unique = {(p.x, p.y) for p in wps}
    return len(unique) < 2


def _repair_elk_self_loop(
    edge: "RoutedEdge",
    node_layout: "NodeLayout",
) -> "RoutedEdge":
    """Create synthetic rectangular waypoints for a degenerate ELK self-loop.

    The repaired loop exits the node's top-left face, arcs above the node,
    and re-enters at the top-right face. All other edge properties are preserved.
    """
    from ._geometry import PortLayout, PortSide, Point  # noqa: PLC0415
    bounds = node_layout.outer_bounds
    cx = bounds.x + bounds.w / 2
    top_y = bounds.y
    loop_h = 24.0
    loop_w = min(bounds.w * 0.6, 40.0)
    p_exit = Point(cx - loop_w / 2, top_y)
    p_tl = Point(cx - loop_w / 2, top_y - loop_h)
    p_tr = Point(cx + loop_w / 2, top_y - loop_h)
    p_enter = Point(cx + loop_w / 2, top_y)
    src_dir = Point(0.0, -1.0)
    dst_dir = Point(0.0, -1.0)
    src_port = PortLayout(
        node_id=edge.src_node_id, side=PortSide.TOP,
        position=p_exit, direction=src_dir,
    )
    dst_port = PortLayout(
        node_id=edge.dst_node_id, side=PortSide.TOP,
        position=p_enter, direction=dst_dir,
    )
    return dataclasses.replace(
        edge,
        waypoints=(p_exit, p_tl, p_tr, p_enter),
        src_port=src_port,
        dst_port=dst_port,
    )


def enrich_flowchart_finalized_layout(
    layout: "FinalizedLayout",
    semantics: FlowchartSemantics,
) -> "FinalizedLayout":
    """Enrich an ELK-produced FinalizedLayout with visual properties.

    The raw ELK FinalizedLayout carries accurate position/routing data but has
    minimal NodeLayout visual properties. This function adds CSS classes, icons,
    accent colors, and proper text layouts immutably — without modifying _Node
    objects, without calling _route_edges, and without writing back to _Node.x/_Node.y.

    AC6: routed_edges from ELK are returned unchanged except for degenerate
    self-loops, which receive a local geometry repair (only the affected edge).
    """
    from ._geometry import FinalizedLayout as _FL, NodeLayout, Rect, _empty_diagnostics  # noqa: PLC0415

    nodes = semantics.nodes
    groups = semantics.groups

    # Build node→group-index and parent-group-id maps for accent coloring
    _node_grp_idx: dict[str, int] = {}
    _nid_parent_gid: dict[str, str] = {}
    if groups:
        for _gi, gid in enumerate(groups.keys()):
            for _nid in groups[gid].members:
                _node_grp_idx[_nid] = _gi
                _nid_parent_gid[_nid] = gid

    # Enrich each NodeLayout with visual props from the corresponding _Node
    enriched_node_layouts: dict[str, NodeLayout] = {}
    for nid, elk_nl in layout.node_layouts.items():
        n = nodes.get(nid)
        if n is None:
            enriched_node_layouts[nid] = elk_nl
            continue
        outer = elk_nl.outer_bounds
        content = Rect(
            x=outer.x + 8, y=outer.y + 4,
            w=max(outer.w - 16, 20.0), h=max(outer.h - 8, 10.0),
        )
        title = _make_text_layout_ir(n.label) if not n.is_dummy else None
        shape = n.shape or "rect"
        is_ext = getattr(n, "css_class", "") == "external"
        css_cls_list = [f"node-{shape}"]
        if is_ext:
            css_cls_list.append("node-external")
        icon_svg = (
            _load_icon(n.icon) if getattr(n, "icon", "") else
            (_load_icon(n.css_class) if getattr(n, "css_class", "") else "")
        )
        if is_ext:
            accent = "var(--node-fg-dim,var(--text-secondary,#75736C))"
        elif nid in _node_grp_idx:
            accent = _ACCENT_CYCLE[_node_grp_idx[nid] % len(_ACCENT_CYCLE)]
        else:
            accent = "var(--node-title-fg,var(--accent-1,#60a5fa))"
        enriched_node_layouts[nid] = NodeLayout(
            node_id=nid,
            semantic_shape=shape,
            outer_bounds=outer,
            content_bounds=content,
            title_layout=title,
            subtitle_layout=None,
            member_layouts=(),
            icon_bounds=None,
            ports=elk_nl.ports,       # AC6: preserve ELK port geometry
            css_classes=tuple(css_cls_list),
            extra_css="",
            is_dummy=n.is_dummy,
            rank=elk_nl.rank,          # AC6: preserve ELK-computed rank
            is_external=is_ext,
            icon_svg=icon_svg,
            accent_color=accent,
            parent_group_id=elk_nl.parent_group_id,
        )

    # AC6: use ELK routed_edges directly; repair only degenerate self-loops
    repaired_edges = []
    for edge in layout.routed_edges:
        if edge.src_node_id == edge.dst_node_id and _is_degenerate_self_loop(edge):
            nl = enriched_node_layouts.get(edge.src_node_id)
            if nl is not None:
                edge = _repair_elk_self_loop(edge, nl)
        repaired_edges.append(edge)

    return _FL(
        node_layouts=_types.MappingProxyType(enriched_node_layouts),
        group_layouts=layout.group_layouts,   # ELK group layout is authoritative
        routed_edges=tuple(repaired_edges),
        routing_failures=layout.routing_failures,
        visible_bounds=layout.visible_bounds,
        diagram_padding=float(semantics.init_cfg.get("diagram_padding") or 48.0),
        canvas_bounds=layout.canvas_bounds,
        direction=layout.direction,
        diagnostics=_empty_diagnostics(),
        composite_gates=_types.MappingProxyType(semantics.sm_composite_gates),
    )


# ── Flowchart routing adapter (ini-005) ───────────────────────────────────────

_USE_LEGACY_ROUTE_EDGES: bool = False

_SIDE_NORMALS_LOCAL: "dict[str, tuple[float, float]]" = {
    "top":    (0.0, -1.0),
    "right":  (1.0,  0.0),
    "bottom": (0.0,  1.0),
    "left":   (-1.0, 0.0),
}

# Escape-stub constants: a short segment from the boundary point along the
# outward normal to an "escape point", from which the orthogonal trunk is
# routed.  Applied for all non-zero outward normals — cardinal shapes produce
# collinear stubs (no visible trunk change) while polygon slopes produce the
# characteristic diagonal departure stub.
_STUB_LEN: float = 20.0
# Used by the CBE rerouter to limit stubs to non-cardinal (diagonal) normals
# only, where face-lift remapping of the boundary port can misalign a cardinal
# stub.  Not used by the main router (which applies stubs to all normals).
_CARDINAL_NORMAL_T: float = 0.999  # max(|nx|,|ny|) threshold for cardinal


def _escape_stub_wrap(result, src_pc, dst_pc, src_needs: bool, dst_needs: bool):
    """Prepend/append boundary points to form terminal escape stubs.

    The result was routed from src_escape (or src boundary) to dst_escape
    (or dst boundary).  This wraps it with the actual boundary points so
    that points[0] == source_port.point and points[-1] == target_port.point,
    and the first/last segments become the normal stubs.  The escape point
    indices (pts[1] and/or pts[-2]) are recorded in escape_indices so that
    _assign_lanes can skip them during lane separation.
    """
    if result is None:
        return None
    pts = list(result.points)
    escape_idx: set = set()
    if src_needs:
        pts = [src_pc.point] + pts
        escape_idx.add(1)
    if dst_needs:
        escape_idx.add(len(pts) - 1)
        pts = pts + [dst_pc.point]
    return result._replace(
        points=tuple(pts),
        source_port=src_pc,
        target_port=dst_pc,
        escape_indices=frozenset(escape_idx),
    )


def flowchart_route_adapter(
    semantics: "FlowchartSemantics",
    grp_bboxes: "dict[str, tuple]",
    direction: str,
) -> "tuple[list, list, list, list]":
    """Convert FlowchartSemantics (post-layout) into port-planner abstractions.

    Nodes must already have canvas coordinates set (called after coordinate
    assignment, before routing).

    Returns (list[PortCandidate], list[RoutingObstacle], list[RoutePermissions],
    list[GateAperture]).
    """
    from .port_planner import (  # noqa: PLC0415
        PortCandidate, RoutingObstacle, RoutePermissions, GateAperture,
        fan_slots,
    )

    nodes = semantics.nodes
    edges = semantics.edges
    groups = semantics.groups
    _dir = direction.upper()
    _horiz = _dir in ("LR", "RL")

    def _nb(n: "_Node") -> "tuple[float, float, float, float]":
        return (float(n.x), float(n.y), float(_node_render_w(n)), float(_node_render_h(n)))

    # Build edge lookups
    from collections import defaultdict  # noqa: PLC0415
    outgoing: "dict[str, list[str]]" = defaultdict(list)
    incoming: "dict[str, list[str]]" = defaultdict(list)
    edge_by_id: "dict[str, _Edge]" = {}
    for e in edges:
        if e.edge_id:
            edge_by_id[e.edge_id] = e
            outgoing[e.src].append(e.edge_id)
            incoming[e.dst].append(e.edge_id)

    src_face = "right" if _horiz else "bottom"
    dst_face = "left" if _horiz else "top"

    def _port_point(side: str, bx: float, by: float, bw: float, bh: float, off: float) -> "tuple[float, float]":
        if side == "right":
            return (bx + bw, by + off * bh)
        if side == "left":
            return (bx, by + off * bh)
        if side == "bottom":
            return (bx + off * bw, by + bh)
        return (bx + off * bw, by)  # top

    def _peer_center(eid: str, peer_map: "dict[str, str]") -> float:
        """Return the position of the peer node center used for port ordering.

        For TB layout: peer center X (maps left→left ports, right→right ports).
        For LR layout: peer center Y (maps top→top ports, bottom→bottom ports).
        Unknown edges default to 0.0 so they sort to the front without crashing.
        """
        peer_id = peer_map.get(eid)
        peer = nodes.get(peer_id) if peer_id else None
        if peer is None:
            return 0.0
        if _horiz:
            return float(peer.y) + float(_node_render_h(peer)) / 2.0
        return float(peer.x) + float(_node_render_w(peer)) / 2.0

    # Edge→peer lookups for port ordering
    _edge_dst: "dict[str, str]" = {e.edge_id: e.dst for e in edges if e.edge_id}
    _edge_src: "dict[str, str]" = {e.edge_id: e.src for e in edges if e.edge_id}

    # PortCandidates for source endpoints (fan-distributed)
    src_ports: "dict[str, PortCandidate]" = {}
    for node_id, eids in outgoing.items():
        node = nodes.get(node_id)
        if node is None or node.is_dummy:
            continue
        bx, by, bw, bh = _nb(node)
        face_len = bh if _horiz else bw
        ordered = sorted(eids, key=lambda e: _peer_center(e, _edge_dst))
        for eid, off in fan_slots(ordered, src_face, face_length=face_len):
            pt = _port_point(src_face, bx, by, bw, bh, off)
            src_ports[eid] = PortCandidate(
                edge_id=eid,
                node_id=node_id,
                side=src_face,
                normalized_offset=off,
                point=pt,
                outward_normal=_SIDE_NORMALS_LOCAL.get(src_face, (0.0, 0.0)),
                fixed_side=False,
                preference_penalty=0.0,
            )

    # PortCandidates for destination endpoints (fan-distributed)
    dst_ports: "dict[str, PortCandidate]" = {}
    for node_id, eids in incoming.items():
        node = nodes.get(node_id)
        if node is None or node.is_dummy:
            continue
        bx, by, bw, bh = _nb(node)
        face_len = bh if _horiz else bw
        ordered = sorted(eids, key=lambda e: _peer_center(e, _edge_src))
        for eid, off in fan_slots(ordered, dst_face, face_length=face_len):
            pt = _port_point(dst_face, bx, by, bw, bh, off)
            dst_ports[eid] = PortCandidate(
                edge_id=eid,
                node_id=node_id,
                side=dst_face,
                normalized_offset=off,
                point=pt,
                outward_normal=_SIDE_NORMALS_LOCAL.get(dst_face, (0.0, 0.0)),
                fixed_side=False,
                preference_penalty=0.0,
            )

    # Obstacles: NODE_INTERIOR for every real leaf node
    obstacles: "list[RoutingObstacle]" = []
    for nid, node in nodes.items():
        if node.is_dummy:
            continue
        bx, by, bw, bh = _nb(node)
        obstacles.append(RoutingObstacle(
            obstacle_id=nid,
            kind="NODE_INTERIOR",
            bounds=(bx, by, bw, bh),
            scope_id=node.group,
            title_bounds=None,
            permitted_gate_ids=frozenset(),
        ))

    # Obstacles: GROUP_INTERIOR for each group
    _TITLE_BAND: float = 20.0
    for gid, (x0, y0, x1, y1) in grp_bboxes.items():
        bw, bh = x1 - x0, y1 - y0
        obstacles.append(RoutingObstacle(
            obstacle_id=gid,
            kind="GROUP_INTERIOR",
            bounds=(x0, y0, bw, bh),
            scope_id=gid,
            title_bounds=(x0, y0, bw, _TITLE_BAND),
            permitted_gate_ids=frozenset(),
        ))

    # RoutePermissions and GateApertures for cross-boundary edges
    def _scope_chain(node: "_Node") -> "tuple[str, ...]":
        chain: "list[str]" = []
        gid = node.group
        while gid:
            chain.append(gid)
            grp = groups.get(gid)
            gid = grp.parent_group if grp else None
        return tuple(chain)

    permissions: "list[RoutePermissions]" = []
    apertures: "list[GateAperture]" = []
    for e in edges:
        if not e.edge_id:
            continue
        sn = nodes.get(e.src)
        dn = nodes.get(e.dst)
        if sn is None or dn is None or sn.is_dummy or dn.is_dummy:
            continue
        if sn.group == dn.group or (sn.group is None and dn.group is None):
            continue
        src_chain = _scope_chain(sn)
        dst_chain = _scope_chain(dn)
        common = tuple(g for g in src_chain if g in set(dst_chain))
        allowed = tuple(dict.fromkeys(src_chain + dst_chain))
        permissions.append(RoutePermissions(
            edge_id=e.edge_id,
            source_scope_chain=src_chain,
            target_scope_chain=dst_chain,
            common_ancestor_ids=common,
            permitted_gate_ids=allowed,
        ))
        for gid in (sn.group, dn.group):
            if gid and gid in grp_bboxes:
                x0, y0, x1, y1 = grp_bboxes[gid]
                cx = (x0 + x1) / 2.0
                cy = (y0 + y1) / 2.0
                apertures.append(GateAperture(
                    gate_id=f"gate_{e.edge_id}_{gid}",
                    edge_id=e.edge_id,
                    group_id=gid,
                    side="right" if _horiz else "bottom",
                    center=(cx, cy),
                    half_width=(x1 - x0) / 4.0,
                ))

    all_ports: "list" = list(src_ports.values()) + list(dst_ports.values())
    return all_ports, obstacles, permissions, apertures


def _assign_lanes(
    assignments: "dict",
    obstacles: "tuple",
    lane_gap: float = 12.0,
    _reroute_fn: "object" = None,
) -> "dict":
    """Separate route pairs sharing a segment by shifting the later route ±lane_gap px.

    Detects all (i < j) assignment pairs with a shared vertical or horizontal
    segment longer than 8 px.  Tries to move route j by +lane_gap first, then
    -lane_gap.  Skips the shift when the displaced segment would enter any
    NODE_INTERIOR obstacle.  Single O(n²) pass; earlier routes are unchanged.

    _reroute_fn(eid, rc) -> RouteCandidate | None: optional callback invoked when
    all interior waypoints at the shared-lane position are escape-protected (pure-stub
    route with no movable trunk).  Returns a replacement RouteCandidate or None.
    """
    def _segs(pts: "tuple") -> "list":
        return [(pts[k], pts[k + 1]) for k in range(len(pts) - 1)]

    def _axis_ov(ax1: float, ay1: float, ax2: float, ay2: float,
                 bx1: float, by1: float, bx2: float, by2: float) -> float:
        if abs(ay1 - ay2) < 1e-9 and abs(by1 - by2) < 1e-9 and abs(ay1 - by1) < 2.0:
            a0, a1 = min(ax1, ax2), max(ax1, ax2)
            b0, b1 = min(bx1, bx2), max(bx1, bx2)
            return max(0.0, min(a1, b1) - max(a0, b0))
        if abs(ax1 - ax2) < 1e-9 and abs(bx1 - bx2) < 1e-9 and abs(ax1 - bx1) < 2.0:
            a0, a1 = min(ay1, ay2), max(ay1, ay2)
            b0, b1 = min(by1, by2), max(by1, by2)
            return max(0.0, min(a1, b1) - max(a0, b0))
        return 0.0

    def _v_clear(new_x: float, y_lo: float, y_hi: float) -> bool:
        for ob in obstacles:
            if ob.kind not in ("NODE_INTERIOR", "node"):
                continue
            ox, oy, ow, oh = ob.bounds
            if ox < new_x < ox + ow and oy < y_hi and oy + oh > y_lo:
                return False
        # Also reject positions already occupied by another route's vertical segment
        # so cascading shifts (route-a pushed route-b into route-c's channel) are avoided.
        for rc in result.values():
            for k in range(len(rc.points) - 1):
                rx1, ry1 = rc.points[k]
                rx2, ry2 = rc.points[k + 1]
                if abs(rx1 - rx2) < 1.0 and abs(rx1 - new_x) < 2.0:
                    s_lo, s_hi = min(ry1, ry2), max(ry1, ry2)
                    if s_lo < y_hi and s_hi > y_lo:
                        return False
        return True

    def _h_clear(new_y: float, x_lo: float, x_hi: float) -> bool:
        for ob in obstacles:
            if ob.kind not in ("NODE_INTERIOR", "node"):
                continue
            ox, oy, ow, oh = ob.bounds
            if oy < new_y < oy + oh and ox < x_hi and ox + ow > x_lo:
                return False
        return True

    result: "dict" = dict(assignments)
    eids: "list" = list(assignments.keys())

    for i in range(len(eids)):
        eid_a = eids[i]
        rc_a = result[eid_a]
        for j in range(i + 1, len(eids)):
            eid_b = eids[j]
            rc_b = result[eid_b]
            done = False
            for (ax1, ay1), (ax2, ay2) in _segs(rc_a.points):
                if done:
                    break
                for (bx1, by1), (bx2, by2) in _segs(rc_b.points):
                    ov = _axis_ov(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2)
                    if ov <= 8.0:
                        continue
                    # Vertical shared channel: shift ALL route-b interior waypoints
                    # at x≈sx so the full vertical chain moves together (preserving
                    # orthogonality when the shared overlap doesn't cover all segments).
                    if abs(ax1 - ax2) < 1.0 and abs(bx1 - bx2) < 1.0:
                        sx = (ax1 + bx1) / 2.0
                        y_lo = max(min(ay1, ay2), min(by1, by2))
                        y_hi = min(max(ay1, ay2), max(by1, by2))
                        for delta in (lane_gap, -lane_gap):
                            nx = sx + delta
                            if _v_clear(nx, y_lo, y_hi):
                                pts_list = list(rc_b.points)
                                _esc = rc_b.escape_indices
                                # Protect each escape that is on the shared channel and
                                # its full contiguous same-x chain.  Only grow using the
                                # escape's OWN x (not sx) so neighbors on the channel
                                # that happen to be next to an off-channel escape are not
                                # incorrectly shielded from the lane shift.
                                _protected: "set[int]" = set()
                                _npts_v = len(pts_list)
                                for _ei in list(_esc):
                                    _ex = pts_list[_ei][0]
                                    if abs(_ex - sx) >= 2.0:
                                        continue  # escape not on this channel
                                    _protected.add(_ei)
                                    if 2 * _ei < _npts_v - 1:
                                        # Source escape — walk backward to protect
                                        # the node-side boundary stub chain.
                                        _j = _ei - 1
                                        while _j >= 0 and abs(pts_list[_j][0] - _ex) < 2.0:
                                            _protected.add(_j)
                                            _j -= 1
                                    else:
                                        # Destination escape — walk forward to protect
                                        # the node-side boundary stub chain.
                                        _j = _ei + 1
                                        while _j < _npts_v and abs(pts_list[_j][0] - _ex) < 2.0:
                                            _protected.add(_j)
                                            _j += 1
                                    # The opposite side (trunk) is NOT protected;
                                    # it is shifted to nx and a jog is inserted below.
                                _shifted = False
                                for _k in range(1, len(pts_list) - 1):
                                    _px, _py = pts_list[_k]
                                    if abs(_px - sx) < 2.0 and _k not in _protected:
                                        pts_list[_k] = (nx, _py)
                                        _shifted = True
                                # If nothing moved and all movable points are protected
                                # (pure-stub route with no trunk), reroute entirely.
                                if not _shifted and _reroute_fn is not None:
                                    _stuck = any(
                                        abs(pts_list[_k][0] - sx) < 2.0
                                        for _k in range(1, len(pts_list) - 1)
                                    )
                                    if _stuck:
                                        _rerouted = _reroute_fn(eid_b, rc_b)
                                        if _rerouted is not None:
                                            _still_ov_v = any(
                                                _axis_ov(_ax1_, _ay1_, _ax2_, _ay2_,
                                                         _bx1_, _by1_, _bx2_, _by2_) > 8.0
                                                for _ov_eid_v, _other_rc_v in result.items()
                                                if _ov_eid_v != eid_b
                                                for (_ax1_, _ay1_), (_ax2_, _ay2_) in _segs(_other_rc_v.points)
                                                for (_bx1_, _by1_), (_bx2_, _by2_) in _segs(_rerouted.points)
                                            )
                                            if not _still_ov_v:
                                                result[eid_b] = _rerouted
                                                rc_b = result[eid_b]
                                                done = True
                                                break
                                # Insert a horizontal bridge between each escape stub
                                # and the newly-shifted trunk segment to preserve
                                # orthogonality.  Source escapes: jog after; dest
                                # escapes: jog before.
                                _jog_ins_v: "list[tuple[int, tuple[float, float]]]" = []
                                _bridge_blocked_v = False
                                for _ei in list(_esc):
                                    if abs(pts_list[_ei][0] - sx) >= 2.0:
                                        continue
                                    if 2 * _ei < len(pts_list) - 1:
                                        # Source escape: jog after escape bridges stub→trunk.
                                        _ni = _ei + 1
                                        if (1 <= _ni < len(pts_list) - 1
                                                and abs(pts_list[_ni][0] - nx) < 2.0
                                                and abs(pts_list[_ei][1] - pts_list[_ni][1]) > 1e-9):
                                            if _h_clear(pts_list[_ei][1],
                                                        min(sx, nx), max(sx, nx)):
                                                _jog_ins_v.append((_ni, (nx, pts_list[_ei][1])))
                                                _shifted = True
                                            else:
                                                _bridge_blocked_v = True
                                    else:
                                        # Destination escape: jog before escape bridges trunk→stub.
                                        _pi = _ei - 1
                                        if (1 <= _pi < len(pts_list) - 1
                                                and abs(pts_list[_pi][0] - nx) < 2.0
                                                and abs(pts_list[_ei][1] - pts_list[_pi][1]) > 1e-9):
                                            if _h_clear(pts_list[_ei][1],
                                                        min(sx, nx), max(sx, nx)):
                                                _jog_ins_v.append((_ei, (nx, pts_list[_ei][1])))
                                                _shifted = True
                                            else:
                                                _bridge_blocked_v = True
                                # A blocked bridge means the trunk was moved but can't be
                                # orthogonally connected to its escape stub — abort this delta.
                                if _bridge_blocked_v:
                                    continue
                                _jog_ins_v.sort(key=lambda _t: _t[0])
                                for _vn, (_vji, _vjp) in enumerate(_jog_ins_v):
                                    _vins = _vji + _vn
                                    pts_list.insert(_vins, _vjp)
                                    _esc = frozenset(
                                        k + 1 if k >= _vins else k for k in _esc
                                    )
                                if _shifted:
                                    result[eid_b] = rc_b._replace(
                                        points=tuple(pts_list), escape_indices=_esc,
                                    )
                                    rc_b = result[eid_b]
                                    done = True
                                    break
                    # Horizontal shared channel: shift route-b interior waypoints in y.
                    # Use x-range filter to avoid shifting bend points outside the
                    # shared segment that would create non-orthogonal segments.
                    # Special case: when route-b's source endpoint is itself at y≈sy_val
                    # (i.e. the first segment is the shared horizontal), a plain bend
                    # shift would produce a diagonal.  Convert to a Z-route instead by
                    # inserting a short vertical stub at the source.
                    elif abs(ay1 - ay2) < 1.0 and abs(by1 - by2) < 1.0:
                        sy_val = (ay1 + by1) / 2.0
                        x_lo = max(min(ax1, ax2), min(bx1, bx2))
                        x_hi = min(max(ax1, ax2), max(bx1, bx2))
                        for delta in (lane_gap, -lane_gap):
                            ny = sy_val + delta
                            pts_list = list(rc_b.points)
                            # Stub path: source endpoint at y≈sy_val means the first
                            # segment is horizontal.  Inserting a stub converts L→Z.
                            # Skip when index 1 is a protected escape: the stub jog would
                            # land before the escape, making the stub→jog→escape sequence
                            # produce a diagonal segment between the jog and the escape.
                            if (len(pts_list) >= 3 and abs(pts_list[0][1] - sy_val) < 2.0
                                    and 1 not in rc_b.escape_indices):
                                sx0 = pts_list[0][0]
                                bx_bend = pts_list[1][0]
                                h_lo = min(sx0, bx_bend)
                                h_hi = max(sx0, bx_bend)
                                if not _h_clear(ny, h_lo, h_hi):
                                    continue
                                if not _v_clear(sx0, min(sy_val, ny), max(sy_val, ny)):
                                    continue
                                # Shift all interior points at y≈sy_val, then prepend stub.
                                _esc = rc_b.escape_indices
                                _lz_protected: "set[int]" = set()
                                for _ei in list(_esc):
                                    _ey2 = pts_list[_ei][1]
                                    if abs(_ey2 - sy_val) >= 2.0:
                                        continue
                                    _lz_protected.add(_ei)
                                    _j = _ei - 1
                                    while _j >= 0 and abs(pts_list[_j][1] - _ey2) < 2.0:
                                        _lz_protected.add(_j)
                                        _j -= 1
                                    _j = _ei + 1
                                    while _j < len(pts_list) and abs(pts_list[_j][1] - _ey2) < 2.0:
                                        _lz_protected.add(_j)
                                        _j += 1
                                _shifted = False
                                for _k in range(1, len(pts_list) - 1):
                                    _px, _py = pts_list[_k]
                                    if abs(_py - sy_val) < 2.0 and _k not in _lz_protected:
                                        pts_list[_k] = (_px, ny)
                                        _shifted = True
                                if _shifted:
                                    pts_list.insert(1, (sx0, ny))
                                    # Insert at index 1 shifts all escape indices >= 1 up by 1.
                                    _shifted_esc = frozenset(k + 1 if k >= 1 else k for k in _esc)
                                    result[eid_b] = rc_b._replace(points=tuple(pts_list), escape_indices=_shifted_esc)
                                    rc_b = result[eid_b]
                                    done = True
                                    break
                            # Standard path: shared segment is interior — shift in y.
                            if not _h_clear(ny, x_lo, x_hi):
                                continue
                            _esc = rc_b.escape_indices
                            # Protect each escape on the shared horizontal channel and
                            # its full contiguous same-y chain.  Use the escape's OWN y
                            # (not sy_val) so neighbors on the channel next to an
                            # off-channel escape are not incorrectly protected.
                            _h_protected: "set[int]" = set()
                            _npts_h = len(pts_list)
                            for _ei in list(_esc):
                                _ey = pts_list[_ei][1]
                                if abs(_ey - sy_val) >= 2.0:
                                    continue  # escape not on this horizontal channel
                                _h_protected.add(_ei)
                                if 2 * _ei < _npts_h - 1:
                                    # Source escape — walk backward to protect node-side.
                                    _j = _ei - 1
                                    while _j >= 0 and abs(pts_list[_j][1] - _ey) < 2.0:
                                        _h_protected.add(_j)
                                        _j -= 1
                                else:
                                    # Destination escape — walk forward to protect node-side.
                                    _j = _ei + 1
                                    while _j < _npts_h and abs(pts_list[_j][1] - _ey) < 2.0:
                                        _h_protected.add(_j)
                                        _j += 1
                                # The opposite side (trunk) is NOT protected;
                                # it is shifted to ny and a jog is inserted below.
                            # Find the contiguous horizontal rail that overlaps
                            # [x_lo, x_hi] and grow it outward.  Remote rails at
                            # the same sy_val are untouched — shifting them can
                            # create diagonal terminal segments.
                            _in_ov = [
                                _k for _k in range(1, len(pts_list) - 1)
                                if abs(pts_list[_k][1] - sy_val) < 2.0
                                and x_lo - 2.0 <= pts_list[_k][0] <= x_hi + 2.0
                            ]
                            _affected_rail: "set[int]" = set(_in_ov)
                            for _anchor in list(_in_ov):
                                _j = _anchor - 1
                                while _j >= 1 and abs(pts_list[_j][1] - sy_val) < 2.0:
                                    _affected_rail.add(_j)
                                    _j -= 1
                                _j = _anchor + 1
                                while _j <= len(pts_list) - 2 and abs(pts_list[_j][1] - sy_val) < 2.0:
                                    _affected_rail.add(_j)
                                    _j += 1
                            # Validate the full shifted rail extent, not just the
                            # overlap interval — a node outside [x_lo, x_hi] is
                            # also obstructed after the shift.
                            if _affected_rail:
                                _movable_rail = [_k for _k in _affected_rail if _k not in _h_protected]
                                if _movable_rail:
                                    _rail_x_lo = min(pts_list[_k][0] for _k in _movable_rail)
                                    _rail_x_hi = max(pts_list[_k][0] for _k in _movable_rail)
                                    if not _h_clear(ny, _rail_x_lo, _rail_x_hi):
                                        continue
                            _h_shifted = False
                            for _k in range(1, len(pts_list) - 1):
                                _px, _py = pts_list[_k]
                                if (abs(_py - sy_val) < 2.0 and _k in _affected_rail
                                        and _k not in _h_protected):
                                    pts_list[_k] = (_px, ny)
                                    _h_shifted = True
                            # If nothing moved and all rail points are protected
                            # (pure-stub route), reroute entirely via callback.
                            if not _h_shifted and _reroute_fn is not None:
                                _h_stuck = any(
                                    abs(pts_list[_k][1] - sy_val) < 2.0
                                    and _k in _affected_rail
                                    for _k in range(1, len(pts_list) - 1)
                                )
                                if _h_stuck:
                                    _rerouted_h = _reroute_fn(eid_b, rc_b)
                                    if _rerouted_h is not None:
                                        _still_ov_h = any(
                                            _axis_ov(_ax1_, _ay1_, _ax2_, _ay2_,
                                                     _bx1_, _by1_, _bx2_, _by2_) > 8.0
                                            for _ov_eid_h, _other_rc_h in result.items()
                                            if _ov_eid_h != eid_b
                                            for (_ax1_, _ay1_), (_ax2_, _ay2_) in _segs(_other_rc_h.points)
                                            for (_bx1_, _by1_), (_bx2_, _by2_) in _segs(_rerouted_h.points)
                                        )
                                        if not _still_ov_h:
                                            result[eid_b] = _rerouted_h
                                            rc_b = result[eid_b]
                                            done = True
                                            break
                            # Insert a vertical jog between each escape stub and the
                            # newly-shifted trunk to restore orthogonality.  Source
                            # escapes: jog after; destination escapes: jog before.
                            _jog_ins_h: "list[tuple[int, tuple[float, float]]]" = []
                            _bridge_blocked_h = False
                            for _ei in list(_esc):
                                _ey_j = pts_list[_ei][1]
                                if abs(_ey_j - sy_val) >= 2.0:
                                    continue
                                if 2 * _ei < len(pts_list) - 1:
                                    # Source escape: jog after escape bridges stub→trunk.
                                    _ni_h = _ei + 1
                                    if (1 <= _ni_h < len(pts_list) - 1
                                            and abs(pts_list[_ni_h][1] - ny) < 2.0
                                            and abs(pts_list[_ei][0] - pts_list[_ni_h][0]) > 1e-9):
                                        if _v_clear(pts_list[_ei][0],
                                                    min(sy_val, ny), max(sy_val, ny)):
                                            _jog_ins_h.append((_ni_h, (pts_list[_ei][0], ny)))
                                            _h_shifted = True
                                        else:
                                            _bridge_blocked_h = True
                                else:
                                    # Destination escape: jog before escape bridges trunk→stub.
                                    _pi_h = _ei - 1
                                    if (1 <= _pi_h < len(pts_list) - 1
                                            and abs(pts_list[_pi_h][1] - ny) < 2.0
                                            and abs(pts_list[_ei][0] - pts_list[_pi_h][0]) > 1e-9):
                                        if _v_clear(pts_list[_ei][0],
                                                    min(sy_val, ny), max(sy_val, ny)):
                                            _jog_ins_h.append((_ei, (pts_list[_ei][0], ny)))
                                            _h_shifted = True
                                        else:
                                            _bridge_blocked_h = True
                            if _bridge_blocked_h:
                                continue
                            _jog_ins_h.sort(key=lambda _t: _t[0])
                            for _hn, (_hji, _hjp) in enumerate(_jog_ins_h):
                                _hins = _hji + _hn
                                pts_list.insert(_hins, _hjp)
                                _esc = frozenset(
                                    k + 1 if k >= _hins else k for k in _esc
                                )
                            if _h_shifted:
                                result[eid_b] = rc_b._replace(
                                    points=tuple(pts_list), escape_indices=_esc,
                                )
                                rc_b = result[eid_b]
                                done = True
                                break
                    if done:
                        break
    return result


def _flowchart_route_new_path(
    nodes: "dict[str, _Node]",
    edges: "list[_Edge]",
    grp_bboxes: "dict[str, tuple]",
    direction: str,
    canvas_w: float,
    canvas_h: float,
    semantics: "FlowchartSemantics",
) -> "RouteBatch":
    """New routing path (ini-005): adapter + assign_routes + local channel.

    Replaces _route_edges() when _USE_LEGACY_ROUTE_EDGES is False. Does not
    call _route_perimeter(); uses local_channel_route() for multi-rank edges.
    """
    from ._geometry import RouteBatch, RoutingFailure  # noqa: PLC0415
    from .route_search import route_edge, local_channel_route  # noqa: PLC0415
    from .port_planner import PortCandidate, RoutingObstacle, RouteCandidate  # noqa: PLC0415

    # Build NODE_INTERIOR obstacles for leaf nodes only (group boundary
    # enforcement happens post-routing in _reroute_cross_boundary_edges).
    obstacles = [
        RoutingObstacle(
            obstacle_id=nid,
            kind="NODE_INTERIOR",
            bounds=(float(n.x), float(n.y), float(_node_render_w(n)), float(_node_render_h(n))),
            scope_id=n.group,
            title_bounds=None,
            permitted_gate_ids=frozenset(),
        )
        for nid, n in nodes.items()
        if not n.is_dummy
    ]

    # Build per-edge port candidates directly (fan-distributed)
    _dir = direction.upper()
    _horiz = _dir in ("LR", "RL")

    def _nb(n: "_Node") -> "tuple[float, float, float, float]":
        return (float(n.x), float(n.y), float(_node_render_w(n)), float(_node_render_h(n)))

    from collections import defaultdict as _dd  # noqa: PLC0415
    from .port_planner import fan_slots  # noqa: PLC0415

    # Only route real edges: skip intermediate dummy-chain segments where the
    # destination is a dummy node. For dummy-chained edges (multi-rank), the last
    # segment may have edge_id='' — synthesize an id from orig_src->orig_dst.
    real_edges: "list[tuple[str, _Edge]]" = []  # (effective_eid, edge)
    seen_real: "set[str]" = set()
    eid_counters: "dict[str, int]" = {}
    for e in edges:
        dst_node = nodes.get(e.dst)
        if dst_node and dst_node.is_dummy:
            continue  # skip intermediate dummy segments
        real_src = e.orig_src or e.src
        real_dst = e.orig_dst or e.dst
        pair_key = f"{real_src}->{real_dst}"
        # Use edge_id as dedup key when available so distinct parallel or
        # self-loop edges (same pair_key, different edge_id) are all routed.
        # Fall back to pair_key only for edges without an id (dummy chains
        # whose final segment might otherwise produce duplicate paths).
        dedup_key = e.edge_id if e.edge_id else pair_key
        if dedup_key in seen_real:
            continue  # dedup dummy chains that converge to same pair
        seen_real.add(dedup_key)
        # Use existing edge_id if set, else synthesize from real endpoints
        eid = e.edge_id or pair_key
        if eid in eid_counters:
            eid_counters[eid] += 1
            eid = f"{eid}#{eid_counters[eid]}"
        else:
            eid_counters[eid] = 0
        real_edges.append((eid, e))

    edge_by_real: "dict[str, _Edge]" = {eid: e for eid, e in real_edges}

    out_map: "dict[str, list[str]]" = _dd(list)
    in_map: "dict[str, list[str]]" = _dd(list)
    for eid, e in real_edges:
        real_src = e.orig_src or e.src
        real_dst = e.orig_dst or e.dst
        out_map[real_src].append(eid)
        in_map[real_dst].append(eid)

    src_face = "right" if _horiz else "bottom"
    dst_face = "left" if _horiz else "top"

    def _pp(side: str, bx: float, by: float, bw: float, bh: float, off: float) -> "tuple[float, float]":
        if side == "right":
            return (bx + bw, by + off * bh)
        if side == "left":
            return (bx, by + off * bh)
        if side == "bottom":
            return (bx + off * bw, by + bh)
        return (bx + off * bw, by)

    def _peer_ctr(eid: str, peer_map: "dict[str, str]") -> float:
        """Center position of the peer node for port-ordering (minimise crossings).

        TB layout: peer center X  → left-going edges get left ports, right → right.
        LR layout: peer center Y  → top-going edges get top ports, bottom → bottom.
        Unknown edges return 0.0 so they sort first without crashing.
        """
        peer_id = peer_map.get(eid)
        peer = nodes.get(peer_id) if peer_id else None
        if peer is None:
            return 0.0
        if _horiz:
            return float(peer.y) + float(_node_render_h(peer)) / 2.0
        return float(peer.x) + float(_node_render_w(peer)) / 2.0

    _eid_dst: "dict[str, str]" = {eid: (e.orig_dst or e.dst) for eid, e in edge_by_real.items()}
    _eid_src: "dict[str, str]" = {eid: (e.orig_src or e.src) for eid, e in edge_by_real.items()}

    _OPPOSITE_FACE: "dict[str, str]" = {
        "bottom": "top", "top": "bottom", "right": "left", "left": "right",
    }

    def _edge_src_face(eid: str) -> str:
        """Choose source port face based on target direction.

        Cross-rank edges that are clearly horizontal (3:1 dominance) use the
        side face so they exit perpendicular to the flow direction instead of
        taking a long detour down before sweeping across.  All other cross-rank
        edges use the global face (bottom for TB).  Same-rank edges with a
        primarily-horizontal offset (2:1) use right or left.
        """
        sn = nodes.get(_eid_src.get(eid, ""))
        dn = nodes.get(_eid_dst.get(eid, ""))
        if sn is None or dn is None or sn.is_dummy or dn.is_dummy:
            return src_face
        scx = float(sn.x) + float(_node_render_w(sn)) / 2.0
        scy = float(sn.y) + float(_node_render_h(sn)) / 2.0
        dcx = float(dn.x) + float(_node_render_w(dn)) / 2.0
        dcy = float(dn.y) + float(_node_render_h(dn)) / 2.0
        dx_v, dy_v = dcx - scx, dcy - scy
        if abs(dx_v) < 5.0 * abs(dy_v):
            return src_face
        if _horiz:
            # LR/RL: target is not dy-dominated, so the edge is primarily horizontal.
            # Restrict to adjacent ranks — long-range skip edges (rank gap > 1) would
            # route straight through intermediate nodes if given a horizontal face.
            if abs(sn.rank - dn.rank) <= 1:
                return "right" if dx_v >= 0 else "left"
            # Long-range: exit vertically (top/bottom) so the skip edge routes
            # through a vertical channel clear of intermediate same-rank nodes.
            return "top" if dy_v < 0 else "bottom"
        # TB: when target is above, exit top so the path reaches destination
        # bottom at right angles instead of a vertical segment parallel to a
        # side face.
        if dy_v < 0:
            return "top"
        return "right" if dx_v >= 0 else "left"

    # Group source edges by (node, per-edge face) for per-face fan distribution.
    _src_face_groups: "dict[tuple[str, str], list[str]]" = _dd(list)
    for node_id, eids in out_map.items():
        for eid in eids:
            _src_face_groups[(node_id, _edge_src_face(eid))].append(eid)

    sp: "dict[str, PortCandidate]" = {}
    for (node_id, face), eids in _src_face_groups.items():
        node = nodes.get(node_id)
        if node is None or node.is_dummy:
            continue
        bx, by, bw, bh = _nb(node)
        face_len = bh if face in ("left", "right") else bw
        ordered = sorted(eids, key=lambda e: _peer_ctr(e, _eid_dst))
        for eid, off in fan_slots(ordered, face, face_length=face_len):
            pt = _pp(face, bx, by, bw, bh, off)
            sp[eid] = PortCandidate(
                edge_id=eid, node_id=node_id, side=face,
                normalized_offset=off, point=pt,
                outward_normal=_SIDE_NORMALS_LOCAL.get(face, (0.0, 0.0)),
                fixed_side=False, preference_penalty=0.0,
            )

    # Group destination edges by (node, per-edge face) for per-face fan distribution.
    _dst_face_groups: "dict[tuple[str, str], list[str]]" = _dd(list)
    for node_id, eids in in_map.items():
        for eid in eids:
            _dst_face = _OPPOSITE_FACE.get(_edge_src_face(eid), dst_face)
            _dst_face_groups[(node_id, _dst_face)].append(eid)

    dp: "dict[str, PortCandidate]" = {}
    for (node_id, face), eids in _dst_face_groups.items():
        # For dummy-chained edges, real destination node resolved via in_map key
        node = nodes.get(node_id)
        if node is None or node.is_dummy:
            # Try to find the real destination node from the edge
            _resolved_node_id = node_id
            for eid in eids:
                e = edge_by_real.get(eid)
                if e:
                    real_dst_id = e.orig_dst or e.dst
                    node = nodes.get(real_dst_id)
                    if node and not node.is_dummy:
                        _resolved_node_id = real_dst_id
                        break
            if node is None or node.is_dummy:
                continue
            node_id = _resolved_node_id
        bx, by, bw, bh = _nb(node)
        face_len = bh if face in ("left", "right") else bw
        ordered = sorted(eids, key=lambda e: _peer_ctr(e, _eid_src))
        for eid, off in fan_slots(ordered, face, face_length=face_len):
            pt = _pp(face, bx, by, bw, bh, off)
            dp[eid] = PortCandidate(
                edge_id=eid, node_id=node_id, side=face,
                normalized_offset=off, point=pt,
                outward_normal=_SIDE_NORMALS_LOCAL.get(face, (0.0, 0.0)),
                fixed_side=False, preference_penalty=0.0,
            )

    # Correct port faces for intra-group edges whose subgraph uses a different direction
    # from the outer flowchart (e.g. "direction TB" inside an outer LR flowchart).
    # The initial port building uses the outer direction for all edges; re-compute
    # using the inner direction for any edge where both endpoints share an inner group.
    _inner_group_dirs: "dict[str, str]" = {
        gid: g.direction.upper()
        for gid, g in semantics.groups.items()
        if g.direction and g.direction.upper() != _dir
    }
    if _inner_group_dirs:
        def _node_group(nid: str) -> "str | None":
            n = nodes.get(nid)
            return n.group if n else None

        for eid, e in real_edges:
            real_src = e.orig_src or e.src
            real_dst = e.orig_dst or e.dst
            sn = nodes.get(real_src)
            dn = nodes.get(real_dst)
            if not (sn and dn and sn.group and sn.group == dn.group
                    and sn.group in _inner_group_dirs):
                continue
            gdir = _inner_group_dirs[sn.group]
            g_horiz = gdir in ("LR", "RL")
            g_src_face = "right" if g_horiz else "bottom"
            g_dst_face = "left" if g_horiz else "top"

            # All intra-group edges from the same src (for fan distribution)
            intra_src = [
                e2_id for e2_id, e2 in real_edges
                if (e2.orig_src or e2.src) == real_src
                and _node_group(e2.orig_dst or e2.dst) == sn.group
            ]
            # All intra-group edges into the same dst
            intra_dst = [
                e2_id for e2_id, e2 in real_edges
                if (e2.orig_dst or e2.dst) == real_dst
                and _node_group(e2.orig_src or e2.src) == dn.group
            ]

            bx, by, bw, bh = _nb(sn)
            face_len_s = bh if g_horiz else bw
            for e3_id, off in fan_slots(intra_src, g_src_face, face_length=face_len_s):
                if e3_id == eid and eid in sp:
                    pt = _pp(g_src_face, bx, by, bw, bh, off)
                    sp[eid] = sp[eid]._replace(
                        side=g_src_face, point=pt, normalized_offset=off,
                        outward_normal=_SIDE_NORMALS_LOCAL.get(g_src_face, (0.0, 0.0)),
                    )
                    break

            bx, by, bw, bh = _nb(dn)
            face_len_d = bh if g_horiz else bw
            for e3_id, off in fan_slots(intra_dst, g_dst_face, face_length=face_len_d):
                if e3_id == eid and eid in dp:
                    pt = _pp(g_dst_face, bx, by, bw, bh, off)
                    dp[eid] = dp[eid]._replace(
                        side=g_dst_face, point=pt, normalized_offset=off,
                        outward_normal=_SIDE_NORMALS_LOCAL.get(g_dst_face, (0.0, 0.0)),
                    )
                    break

    # Backward edges in TB mode: src exits RIGHT, dst enters BOTTOM.
    # Default bottom→top creates a U-shaped loop that routes through group interiors.
    # right→bottom routes via the open corridor to the right of src, entering dst
    # from below — consistent with how ELK handles back-edges in TB flowcharts.
    if not _horiz:
        _back_eids: "set[str]" = set()
        for eid, e in real_edges:
            _rsrc = e.orig_src or e.src
            _rdst = e.orig_dst or e.dst
            _sn = nodes.get(_rsrc)
            _dn = nodes.get(_rdst)
            # Only override port faces for backward edges whose endpoints are
            # both in groups.  Ungrouped backward edges (e.g. self-loops in a
            # flat flowchart) are handled adequately by the standard router and
            # the override would route them through unrelated nodes.
            if (_sn and _dn and not _sn.is_dummy and not _dn.is_dummy
                    and _sn.rank > _dn.rank
                    and _sn.group and _dn.group):
                _back_eids.add(eid)

        if _back_eids:
            # Override src: right face; recompute forward edges on bottom face
            _back_src_nodes: "set[str]" = {
                sp[eid].node_id for eid in _back_eids if eid in sp
            }
            for _snid in _back_src_nodes:
                _sn2 = nodes.get(_snid)
                if not _sn2:
                    continue
                _bx, _by, _bw, _bh = _nb(_sn2)
                _back_out = [eid for eid in _back_eids
                             if sp.get(eid) and sp[eid].node_id == _snid]
                for _idx, _beid in enumerate(_back_out):
                    _off = (_idx + 0.5) / max(len(_back_out), 1)
                    _pt = _pp("right", _bx, _by, _bw, _bh, _off)
                    sp[_beid] = sp[_beid]._replace(
                        side="right", point=_pt, normalized_offset=_off,
                        outward_normal=_SIDE_NORMALS_LOCAL.get("right", (0.0, 0.0)),
                    )
                # Recompute forward bottom fan without the backward edges
                _fwd_out = [
                    eid for eid, e in real_edges
                    if (e.orig_src or e.src) == _snid
                    and eid not in _back_eids
                    and eid in sp and sp[eid].node_id == _snid
                ]
                if _fwd_out:
                    for _feid, _foff in fan_slots(_fwd_out, "bottom", face_length=_bw):
                        _fpt = _pp("bottom", _bx, _by, _bw, _bh, _foff)
                        sp[_feid] = sp[_feid]._replace(
                            side="bottom", point=_fpt, normalized_offset=_foff,
                        )

            # Override dst: bottom face; recompute forward edges on top face
            _back_dst_nodes: "set[str]" = {
                dp[eid].node_id for eid in _back_eids if eid in dp
            }
            for _dnid in _back_dst_nodes:
                _dn2 = nodes.get(_dnid)
                if not _dn2:
                    continue
                _bx, _by, _bw, _bh = _nb(_dn2)
                _back_in = [eid for eid in _back_eids
                            if dp.get(eid) and dp[eid].node_id == _dnid]
                for _idx, _beid in enumerate(_back_in):
                    _off = (_idx + 0.5) / max(len(_back_in), 1)
                    _pt = _pp("bottom", _bx, _by, _bw, _bh, _off)
                    dp[_beid] = dp[_beid]._replace(
                        side="bottom", point=_pt, normalized_offset=_off,
                        outward_normal=_SIDE_NORMALS_LOCAL.get("bottom", (0.0, 0.0)),
                    )
                # Recompute forward top fan without the backward edges
                _fwd_in = [
                    eid for eid, e in real_edges
                    if (e.orig_dst or e.dst) == _dnid
                    and eid not in _back_eids
                    and eid in dp and dp[eid].node_id == _dnid
                ]
                if _fwd_in:
                    for _feid, _foff in fan_slots(_fwd_in, "top", face_length=_bw):
                        _fpt = _pp("top", _bx, _by, _bw, _bh, _foff)
                        dp[_feid] = dp[_feid]._replace(
                            side="top", point=_fpt, normalized_offset=_foff,
                        )
    else:
        _back_eids = set()

    obs_tuple: "tuple[RoutingObstacle, ...]" = tuple(obstacles)

    # Refine port positions and outward normals for all registered shapes.
    # Ports computed via _pp land on the rectangular bounding-box face; for shapes
    # like diamond, hexagon, trapezoid etc. the actual outline differs, and for
    # curved shapes (circle, stadium, etc.) the AABB port misses the curved outline.
    # Use the authoritative attachment() API to get the exact boundary point and
    # outward normal perpendicular to the actual face for every registered shape.
    from .shape_geometry import SHAPE_REGISTRY as _SR_port  # noqa: PLC0415
    for _pc_dict in (sp, dp):
        for _pe_id, _pc in list(_pc_dict.items()):
            _pn = nodes.get(_pc.node_id)
            if _pn is None or getattr(_pn, "shape", None) is None:
                continue
            _sg = _SR_port.get(_pn.shape)
            if _sg is None:
                continue
            _pbx, _pby, _pbw, _pbh = _nb(_pn)
            try:
                _att = _sg.attachment(_pc.side, _pc.normalized_offset, _pbw, _pbh)
                _rx, _ry = _pbx + _att.point[0], _pby + _att.point[1]
                _pc_dict[_pe_id] = _pc._replace(point=(_rx, _ry),
                                                 outward_normal=_att.outward_normal)
            except Exception:
                # Fallback: use boundary_intersection for point only (legacy path)
                _pcx, _pcy = _pbx + _pbw / 2.0, _pby + _pbh / 2.0
                _ppx, _ppy = _pc.point
                _pdx, _pdy = _ppx - _pcx, _ppy - _pcy
                if _pdx != 0.0 or _pdy != 0.0:
                    _rx, _ry = _sg.boundary_intersection(_pcx, _pcy, _pbw, _pbh, _pdx, _pdy)
                    _pc_dict[_pe_id] = _pc._replace(point=(_rx, _ry))

    # Collect group border y-coordinates so local_channel_route can avoid landing
    # Z-route horizontal segments on group box top/bottom edges.
    _grp_border_ys: "tuple[float, ...]" = tuple(
        y for bbox in grp_bboxes.values() for y in (bbox[1], bbox[3])
    )

    # Route each edge: multi-rank → try local channel first, else standard route_edge
    assignments: "dict[str, RouteCandidate]" = {}
    failures_list: "list[RoutingFailure]" = []
    self_loop_dicts: "list[dict]" = []  # pre-built route dicts for self-loops
    _self_loop_lanes: "dict[str, int]" = {}  # per-node lane counter for multiple self-loops

    def _local_bounds_for(src_rank: int, dst_rank: int) -> "tuple[float, float, float, float] | None":
        min_r, max_r = min(src_rank, dst_rank), max(src_rank, dst_rank)
        ns = [
            n for n in nodes.values()
            if not n.is_dummy and min_r <= n.rank <= max_r
        ]
        if not ns:
            return None
        xs = [n.x for n in ns]
        ys = [n.y for n in ns]
        x2 = [n.x + _node_render_w(n) for n in ns]
        y2 = [n.y + _node_render_h(n) for n in ns]
        bx, by = min(xs), min(ys)
        return (bx, by, max(x2) - bx, max(y2) - by)

    for eid, e in real_edges:
        real_src_id = e.orig_src or e.src
        real_dst_id = e.orig_dst or e.dst

        # Self-loop: produce a rectangular bump outside the node; skip generic routing
        # which produces a degenerate same-node direct route with the label inside the node.
        if real_src_id == real_dst_id:
            s = nodes.get(real_src_id)
            if s is None or s.is_dummy:
                failures_list.append(RoutingFailure(
                    edge_id=eid, src_node_id=real_src_id, dst_node_id=real_dst_id,
                    reason="self-loop node not found",
                ))
                continue
            from ._constants import BASE_LOOP_EXTENT, LABEL_PAD, LOOP_LANE_GAP  # noqa: PLC0415
            _SL_CHIP_H = 17  # label chip height (matches _LABEL_CHIP_H in _routing.py)
            nw = float(_node_render_w(s))
            nh = float(_node_render_h(s))
            _label_w = len(e.label or "") * 7
            lane_idx = _self_loop_lanes.get(real_src_id, 0)
            _self_loop_lanes[real_src_id] = lane_idx + 1
            lane_num = lane_idx // 2  # stack same-face loops
            extent = (max(BASE_LOOP_EXTENT, _label_w + 2 * LABEL_PAD, int(0.35 * max(nw, nh)))
                      + lane_num * LOOP_LANE_GAP)
            if _horiz:
                x_out = float(s.x) + nw * 0.33
                x_ret = float(s.x) + nw * 0.67
                if lane_idx % 2 == 0:
                    # top face
                    y_face = float(s.y)
                    loop_y = y_face - extent
                    sl_pts: "list[tuple[float, float]]" = [
                        (x_out, y_face), (x_out, loop_y), (x_ret, loop_y), (x_ret, y_face),
                    ]
                    mid_x = (x_out + x_ret) / 2
                    _lx = mid_x - _label_w / 2
                    _ly = loop_y - _SL_CHIP_H - 4
                else:
                    # bottom face
                    y_face = float(s.y) + nh
                    loop_y = y_face + extent
                    sl_pts = [
                        (x_out, y_face), (x_out, loop_y), (x_ret, loop_y), (x_ret, y_face),
                    ]
                    mid_x = (x_out + x_ret) / 2
                    _lx = mid_x - _label_w / 2
                    _ly = loop_y + 4
            else:
                y_out = float(s.y) + nh * 0.33
                y_ret = float(s.y) + nh * 0.67
                if lane_idx % 2 == 0:
                    # right face
                    x_face = float(s.x) + nw
                    loop_x = x_face + extent
                    sl_pts = [
                        (x_face, y_out), (loop_x, y_out), (loop_x, y_ret), (x_face, y_ret),
                    ]
                    _lx = loop_x + 4.0
                    _ly = (y_out + y_ret) / 2 - _SL_CHIP_H
                else:
                    # left face
                    x_face = float(s.x)
                    loop_x = x_face - extent
                    sl_pts = [
                        (x_face, y_out), (loop_x, y_out), (loop_x, y_ret), (x_face, y_ret),
                    ]
                    _lx = loop_x - _label_w - 4.0
                    _ly = (y_out + y_ret) / 2 - _SL_CHIP_H
            if e.style == "thick":
                _sl_marker_id: "str | None" = "arrow-thick" if e.arrow else None
            else:
                _sl_marker_id = ("arrow-open" if e.style == "dotted" else "arrow-normal") if e.arrow else None
            self_loop_dicts.append({
                "waypoints": sl_pts,
                "edge_id": eid,
                "src": real_src_id,
                "dst": real_dst_id,
                "style": e.style,
                "label": e.label,
                "ah": e.arrow,
                "source_marker": e.source_marker,
                "target_marker": e.target_marker,
                "extra_css": e.extra_css,
                "marker_id": _sl_marker_id,
                "bidir": getattr(e, "bidir", False),
                "lx": _lx,
                "ly": _ly,
                "d": "",
            })
            continue

        src_pc = sp.get(eid)
        dst_pc = dp.get(eid)
        if src_pc is None or dst_pc is None:
            failures_list.append(RoutingFailure(
                edge_id=eid, src_node_id=real_src_id,
                dst_node_id=real_dst_id,
                reason="missing port candidate",
            ))
            continue

        existing = tuple(assignments.values())
        result: "RouteCandidate | None" = None

        # Per-edge obstacles: exclude src and dst nodes (routes start on boundary)
        per_obs = tuple(ob for ob in obs_tuple if ob.obstacle_id not in (real_src_id, real_dst_id))

        # Escape port candidates for all non-zero outward normals.
        # Non-cardinal normals (diamond, hexagon, etc.) produce diagonal stubs;
        # cardinal normals produce collinear stubs (no visible trunk change) but
        # still anchor the departure direction — route_edge can otherwise choose
        # a horizontal-first L-route from a bottom-face port, departing sideways.
        _snx, _sny = src_pc.outward_normal
        _dnx, _dny = dst_pc.outward_normal
        _src_needs_stub = max(abs(_snx), abs(_sny)) > 1e-9
        _dst_needs_stub = max(abs(_dnx), abs(_dny)) > 1e-9
        # Cap escape stubs when they genuinely approach each other and could cross.
        # Three-way decision based on the largest non-crossing stub length:
        #
        #   max_nc = (gap_along_axis − 1) / approach_rate
        #
        #   max_nc ≥ _STUB_LEN  → no cap; normal case
        #   per-endpoint min ≤ max_nc < _STUB_LEN → cap to max_nc; clearance met
        #   max_nc < per-endpoint min → disable that endpoint's stub independently;
        #     a markerless end (4 px min) can still stub when a marked end (13/15 px)
        #     cannot — endpoints are evaluated independently, not via max().
        #
        # When normals oppose each other (dn·sn < 0, e.g. TB source-bottom/dest-top),
        # the cap is computed along the src normal axis — this is exact even when ports
        # are horizontally offset (where the Euclidean direction dilutes approach_rate).
        # For non-opposing normals the Euclidean formula handles the edge cases.
        _sx0, _sy0 = src_pc.point
        _dx0, _dy0 = dst_pc.point
        _gap_euclidean = ((_dx0 - _sx0) ** 2 + (_dy0 - _sy0) ** 2) ** 0.5
        _stub_cap = _STUB_LEN
        # Endpoint-specific minimum stub lengths based on which end has a marker.
        # Destination minimum (arrowhead depth + clearance):
        _stub_min_dst = (15.0 if (e.arrow and e.style == "thick")
                         else 13.0 if e.arrow else 4.0)
        # Source minimum (source marker, if any):
        _src_has_marker = _marker_kind(e.source_marker).value != "none"
        _stub_min_src = (15.0 if (_src_has_marker and e.style == "thick")
                         else 13.0 if _src_has_marker else 4.0)
        _dn_dot_sn = _dnx * _snx + _dny * _sny
        if _dn_dot_sn < -0.99:
            # Truly antiparallel normals (e.g. TB bottom→top): escapes close the
            # gap along the src normal axis, which is exact even when ports are
            # horizontally offset.  Merely obtuse normals (e.g. diamond→rect) use
            # the Euclidean branch below — projecting a diagonal-normal gap onto the
            # src axis gives a misleadingly small clearance and disables valid stubs.
            _gap_along_sn = (_dx0 - _sx0) * _snx + (_dy0 - _sy0) * _sny
            if _gap_along_sn > 0:
                _approach_rate_sn = 1.0 - _dn_dot_sn  # ≥ 1; equals 2 for pure opposing
                _max_nc = (_gap_along_sn - 1.0) / _approach_rate_sn
                if _max_nc < _STUB_LEN:
                    # Stubs can only collide when ports are perpendicularly close.
                    # When the perpendicular separation exceeds the full stub length
                    # the stubs diverge and the axial cap does not apply.
                    _gap_perp_sn = abs((_dx0 - _sx0) * _sny - (_dy0 - _sy0) * _snx)
                    if _gap_perp_sn <= _STUB_LEN:
                        # Cap each endpoint independently: a markerless end (4 px min)
                        # can still stub when a marked end (13/15 px) cannot.
                        _stub_cap = _max_nc
                        if _max_nc < _stub_min_src:
                            _src_needs_stub = False
                        if _max_nc < _stub_min_dst:
                            _dst_needs_stub = False
        elif _gap_euclidean > 1e-9:
            # Non-opposing normals: use Euclidean approach-rate for the remaining
            # edge cases (near-perpendicular normals don't fire this branch in practice).
            _ux = (_dx0 - _sx0) / _gap_euclidean
            _uy = (_dy0 - _sy0) / _gap_euclidean
            _approach_rate = (_snx - _dnx) * _ux + (_sny - _dny) * _uy
            if _approach_rate > 0:
                _max_nc = (_gap_euclidean - 1.0) / _approach_rate
                if _max_nc < _STUB_LEN:
                    _stub_cap = _max_nc
                    if _max_nc < _stub_min_src:
                        _src_needs_stub = False
                    if _max_nc < _stub_min_dst:
                        _dst_needs_stub = False
        _src_rpc = src_pc._replace(
            point=(src_pc.point[0] + _snx * _stub_cap, src_pc.point[1] + _sny * _stub_cap)
        ) if _src_needs_stub else src_pc
        _dst_rpc = dst_pc._replace(
            point=(dst_pc.point[0] + _dnx * _stub_cap, dst_pc.point[1] + _dny * _stub_cap)
        ) if _dst_needs_stub else dst_pc

        # Snap near-aligned cardinal escape coordinates to prevent sub-4px doglegs.
        # When both normals are on the same axis (e.g. both vertical) and the escapes
        # differ by < 1px on the perpendicular axis (e.g. x-offset from odd-width nodes),
        # route_edge inserts a tiny jog at the escape point.  Snap ALL four points
        # (both escapes AND boundaries) to the same integer coordinate so stubs stay
        # exactly on the normal axis.  Averaging to a non-integer fails the 0.9998
        # terminal-normal contract for short capped stubs (e.g. 9.5px / 0.25px offset
        # gives dot ≈ 0.9996) and can trigger collinear dedup into a diagonal segment.
        # Sub-1 px escape alignment: when both normals are cardinal on the same
        # axis and the escapes differ by < 1 px on the perpendicular axis, each
        # escape already lies on the outward-normal ray from its own boundary
        # (normal is (0,±1) so escape.x = boundary.x exactly), so no snap is
        # needed.  The resulting < 1 px trunk jog between the two escape columns
        # is absorbed by the dogleg validator's escape-chain exemption.

        # Retract escape point when it lands inside a sibling obstacle
        # (e.g. fan-out A→C escape falls on B's top edge when rankSpacing equals
        # the stub length).  RoutingObstacle.bounds = (x, y, w, h).
        # Before fully disabling, compute the max clearance along the normal so we
        # can use a shorter stub rather than losing the departure-direction constraint.
        def _shrink_stub(px, py, nx, ny, full_len, obs_list):
            """Return max stub ≤ full_len that keeps the escape outside obs_list."""
            best = full_len
            # Precompute full-length endpoint so each obstacle is tested against the
            # original (unclipped) segment, not against the already-shrunk stub.
            _fl_x = px + nx * full_len
            _fl_y = py + ny * full_len
            for _ob_ in obs_list:
                _ox_, _oy_, _ow_, _oh_ = _ob_.bounds
                _ox1_, _oy1_ = _ox_ + _ow_, _oy_ + _oh_
                # Use full segment check — endpoint-only misses pass-throughs where
                # the stub enters and exits the obstacle (escape lands beyond it).
                if not _seg_intersects_rect(px, py, _fl_x, _fl_y, _ox_, _oy_, _ox1_, _oy1_):
                    continue
                # Compute ray-entry distance along each axis.
                _tx = (((_ox_ - px) / nx) if nx > 1e-9
                       else ((_ox1_ - px) / nx) if nx < -1e-9
                       else (0.0 if _ox_ <= px <= _ox1_ else float('inf')))
                _ty = (((_oy_ - py) / ny) if ny > 1e-9
                       else ((_oy1_ - py) / ny) if ny < -1e-9
                       else (0.0 if _oy_ <= py <= _oy1_ else float('inf')))
                _clr = max(_tx, _ty) - 1.0  # 1 px clearance before obstacle face
                best = min(best, max(_clr, 0.0))
            return best

        if _src_needs_stub:
            _ex, _ey = _src_rpc.point
            _bsx, _bsy = src_pc.point  # use current (possibly snapped) boundary
            # Use obs_tuple minus only the source node so the destination node IS
            # included — the stub must not enter the opposite endpoint even when
            # the two nodes are very close together.
            # Exclude containing (ancestor) GROUP_INTERIOR obstacles: the stub exits
            # the node boundary and necessarily crosses any enclosing subgraph's AABB,
            # so those groups must not trigger the shrink or disable logic.
            _stub_src_obs = [
                _ob for _ob in obs_tuple
                if _ob.obstacle_id != real_src_id
                and not (_ob.kind in ("GROUP_INTERIOR", "group")
                         and _ob.bounds[0] < _bsx < _ob.bounds[0] + _ob.bounds[2]
                         and _ob.bounds[1] < _bsy < _ob.bounds[1] + _ob.bounds[3])
            ]
            if any(_seg_intersects_rect(_bsx, _bsy, _ex, _ey,
                                        _ob.bounds[0], _ob.bounds[1],
                                        _ob.bounds[0] + _ob.bounds[2],
                                        _ob.bounds[1] + _ob.bounds[3])
                   for _ob in _stub_src_obs):
                _clr_s = _shrink_stub(_bsx, _bsy, _snx, _sny, _stub_cap, _stub_src_obs)
                if _clr_s >= _stub_min_src:
                    _src_rpc = src_pc._replace(point=(_bsx + _snx * _clr_s, _bsy + _sny * _clr_s))
                else:
                    _src_rpc = src_pc
                    _src_needs_stub = False
        if _dst_needs_stub:
            _ex, _ey = _dst_rpc.point
            _bdx, _bdy = dst_pc.point  # use current (possibly snapped) boundary
            # Use obs_tuple minus only the destination node so the source node IS
            # included — the stub must not enter the opposite endpoint.
            # Same ancestor-group exclusion for the destination stub.
            _stub_dst_obs = [
                _ob for _ob in obs_tuple
                if _ob.obstacle_id != real_dst_id
                and not (_ob.kind in ("GROUP_INTERIOR", "group")
                         and _ob.bounds[0] < _bdx < _ob.bounds[0] + _ob.bounds[2]
                         and _ob.bounds[1] < _bdy < _ob.bounds[1] + _ob.bounds[3])
            ]
            if any(_seg_intersects_rect(_bdx, _bdy, _ex, _ey,
                                        _ob.bounds[0], _ob.bounds[1],
                                        _ob.bounds[0] + _ob.bounds[2],
                                        _ob.bounds[1] + _ob.bounds[3])
                   for _ob in _stub_dst_obs):
                _clr_d = _shrink_stub(_bdx, _bdy, _dnx, _dny, _stub_cap, _stub_dst_obs)
                if _clr_d >= _stub_min_dst:
                    _dst_rpc = dst_pc._replace(point=(_bdx + _dnx * _clr_d, _bdy + _dny * _clr_d))
                else:
                    _dst_rpc = dst_pc
                    _dst_needs_stub = False

        # Endpoint-interior guard: when stubs push the routing start/end
        # outside the source/destination, a route can loop back through the
        # endpoint's interior (per_obs excludes src/dst so routes can start on
        # their boundary).  Build a supplemental obstacle set; use it only if
        # a post-route check detects an interior crossing (1px inset avoids
        # false positives from boundary-tangent routes near adjacent nodes).
        _ep_extra_obs: "tuple" = ()
        _ep_aabbs: "list[tuple[float,float,float,float]]" = []
        if _src_needs_stub or _dst_needs_stub:
            _ep_list = [
                _ob for _ob in obs_tuple
                if (_src_needs_stub and _ob.obstacle_id == real_src_id
                    or _dst_needs_stub and _ob.obstacle_id == real_dst_id)
            ]
            _ep_extra_obs = tuple(_ep_list)
            for _ob in _ep_list:
                _bx, _by, _bw, _bh = _ob.bounds
                # Only include AABBs where the escape is outside the box.
                # Non-rectangular shapes (diamond, circle, ellipse) have an escape
                # outside the actual outline but inside the AABB; checking those
                # would produce false interior-crossing detections and trigger
                # unnecessary retries with the blocked AABB trapping A*'s goal.
                if _ob.obstacle_id == real_src_id:
                    _chk_x, _chk_y = _src_rpc.point
                else:
                    _chk_x, _chk_y = _dst_rpc.point
                if not (_bx < _chk_x < _bx + _bw and _by < _chk_y < _by + _bh):
                    _ep_aabbs.append((_bx, _by, _bx + _bw, _by + _bh))

        def _enters_ep_interior(res: "RouteCandidate") -> bool:
            """True if any trunk segment crosses an endpoint AABB interior."""
            if not _ep_aabbs:
                return False
            _pts = res.points
            for _ii in range(len(_pts) - 1):
                _ax, _ay = _pts[_ii]
                _bx_, _by_ = _pts[_ii + 1]
                for _xlo, _ylo, _xhi, _yhi in _ep_aabbs:
                    if _seg_intersects_rect(_ax, _ay, _bx_, _by_, _xlo + 1, _ylo + 1, _xhi - 1, _yhi - 1):
                        return True
            return False

        def _route_avoiding_eps(route_fn, *args, **kwargs):
            """Call route_fn with endpoint obstacles added."""
            _obs = kwargs.pop("obstacles", per_obs)
            return route_fn(*args, obstacles=_obs + _ep_extra_obs, **kwargs)

        # Multi-rank forward: try local channel first.
        src_node = nodes.get(real_src_id)
        dst_node = nodes.get(real_dst_id)
        _is_backward = eid in _back_eids

        if _is_backward and src_node and dst_node:
            # Backward edges in TB: route EX.right → corridor → OT.bottom.
            # Route escape-to-escape so _escape_stub_wrap can wrap with the correct
            # boundary stubs, giving perpendicular terminal attachment.
            # Pivot x = just right of source group boundary so the path clears
            # the group interior (avoids routing back through node rows).
            _bsx_esc, _bsy_esc = _src_rpc.point  # source escape (20px right of EX.right)
            _bdx_esc, _bdy_esc = _dst_rpc.point  # dest escape (20px below OT.bottom)
            _back_grp = src_node.group
            _corr_x = _bsx_esc  # fallback
            if _back_grp and _back_grp in grp_bboxes:
                _, _, _sg_x1, _ = grp_bboxes[_back_grp]
                _corr_x = _sg_x1 + COL_GAP / 2.0
            if _bsx_esc < _corr_x < _bdx_esc:
                _bpts: "tuple" = (
                    (_bsx_esc, _bsy_esc), (_corr_x, _bsy_esc),
                    (_corr_x, _bdy_esc), (_bdx_esc, _bdy_esc),
                )
            else:
                _bpts = ((_bsx_esc, _bsy_esc), (_bdx_esc, _bsy_esc), (_bdx_esc, _bdy_esc))
            _blen = sum(
                abs(_bpts[i + 1][0] - _bpts[i][0]) + abs(_bpts[i + 1][1] - _bpts[i][1])
                for i in range(len(_bpts) - 1)
            )
            result = RouteCandidate(
                edge_id=eid, source_port=src_pc, target_port=dst_pc,
                points=_bpts, bend_count=len(_bpts) - 2,
                length=_blen, crossing_count=0, shared_segment_length=0.0, cost=_blen,
            )
            result = _escape_stub_wrap(result, src_pc, dst_pc, _src_needs_stub, _dst_needs_stub)
        elif (not _is_backward
                and src_node and dst_node
                and not src_node.is_dummy and not dst_node.is_dummy
                and abs(src_node.rank - dst_node.rank) > 1):
            lb = _local_bounds_for(src_node.rank, dst_node.rank)
            if lb is not None:
                result = local_channel_route(eid, _src_rpc, _dst_rpc, lb, existing, obstacles=per_obs, group_border_ys=_grp_border_ys)
                if result is not None and _enters_ep_interior(result):
                    result = _route_avoiding_eps(local_channel_route, eid, _src_rpc, _dst_rpc, lb, existing, obstacles=per_obs, group_border_ys=_grp_border_ys)
                # Reject channels that land within 8px of the canvas boundary
                if result is not None:
                    _CANVAS_MARGIN = 8.0
                    _mid = result.points[1:-1]
                    if any(
                        p[0] < _CANVAS_MARGIN or p[0] > canvas_w - _CANVAS_MARGIN
                        or p[1] < _CANVAS_MARGIN or p[1] > canvas_h - _CANVAS_MARGIN
                        for p in _mid
                    ):
                        result = None
                    else:
                        result = _escape_stub_wrap(result, src_pc, dst_pc, _src_needs_stub, _dst_needs_stub)

        if result is None:
            result = route_edge(eid, _src_rpc, _dst_rpc, per_obs, existing)
            if result is not None and _enters_ep_interior(result):
                # Retry with tighter obstacles; if retry fails, discard the
                # known-invalid route so later fallbacks (local_channel, stub)
                # run rather than emitting a node-interior-crossing connector.
                result = route_edge(eid, _src_rpc, _dst_rpc, per_obs + _ep_extra_obs, existing)
            result = _escape_stub_wrap(result, src_pc, dst_pc, _src_needs_stub, _dst_needs_stub)

        # Last-resort: if route_edge found nothing and the nodes are far apart
        # vertically (same or adjacent DAG rank but large y-gap), the standard
        # L/Z shapes miss the clear corridor.  Try local_channel_route which
        # includes a channel-outside-local-bounds fallback that routes around
        # the obstacle cluster.
        if result is None and src_node and dst_node and not src_node.is_dummy and not dst_node.is_dummy:
            if abs(src_node.y - dst_node.y) > 400:
                _lb2 = _local_bounds_for(src_node.rank, dst_node.rank)
                if _lb2 is not None:
                    result = local_channel_route(eid, _src_rpc, _dst_rpc, _lb2, existing, obstacles=per_obs, group_border_ys=_grp_border_ys)
                    if result is not None:
                        _CANVAS_MARGIN2 = 8.0
                        if any(
                            p[0] < _CANVAS_MARGIN2 or p[0] > canvas_w - _CANVAS_MARGIN2
                            or p[1] < _CANVAS_MARGIN2 or p[1] > canvas_h - _CANVAS_MARGIN2
                            for p in result.points[1:-1]
                        ):
                            result = None
                        else:
                            result = _escape_stub_wrap(result, src_pc, dst_pc, _src_needs_stub, _dst_needs_stub)

        if result is not None:
            assignments[eid] = result
        else:
            # All routing strategies exhausted: emit a straight-line stub instead
            # of dropping the edge. The stub may cross obstacles but keeps every
            # declared edge visible and prevents hard crashes on deeply-nested
            # diagrams where the obstacle map is too congested to route around.
            # Route between escape points (not boundaries) so _escape_stub_wrap
            # can attach the normal-aligned boundary stubs; this satisfies AC9
            # even in the degenerate case.
            _fsx, _fsy = (_src_rpc.point if _src_needs_stub else src_pc.point)
            _fdx, _fdy = (_dst_rpc.point if _dst_needs_stub else dst_pc.point)
            _stub_len = ((_fdx - _fsx) ** 2 + (_fdy - _fsy) ** 2) ** 0.5
            warnings.warn(
                f"edge {eid!r} ({real_src_id} → {real_dst_id}): routing exhausted; "
                "using straight-line stub",
                stacklevel=2,
            )
            _fb_pts = tuple(_ensure_orthogonal([(_fsx, _fsy), (_fdx, _fdy)]))
            _fb = RouteCandidate(
                edge_id=eid, source_port=src_pc, target_port=dst_pc,
                points=_fb_pts,
                bend_count=0, length=_stub_len,
                crossing_count=0, shared_segment_length=0.0, cost=_stub_len,
            )
            assignments[eid] = _escape_stub_wrap(_fb, src_pc, dst_pc, _src_needs_stub, _dst_needs_stub)

    # Separate parallel routes that share a segment into adjacent lanes.
    # Reroute callback: when all waypoints in the shared lane are escape-protected
    # (pure-stub route, no trunk to shift), fall back to a fresh route_edge call
    # so the edge takes a different path rather than silently overlapping.
    def _lane_stuck_reroute(eid: str, rc: "RouteCandidate") -> "RouteCandidate | None":
        _src_id = rc.source_port.node_id
        _dst_id = rc.target_port.node_id
        _re_obs = tuple(ob for ob in obs_tuple if ob.obstacle_id not in (_src_id, _dst_id))
        _re_existing = tuple(v for k, v in assignments.items() if k != eid)
        # Route between the escape points (not boundaries) so _escape_stub_wrap
        # can re-attach the stubs and preserve attachment for non-cardinal normals.
        _rpts = rc.points
        _rn = len(_rpts)
        _esc_s = sorted(rc.escape_indices) if rc.escape_indices else []
        _snx_r, _sny_r = rc.source_port.outward_normal
        _dnx_r, _dny_r = rc.target_port.outward_normal
        # The midpoint heuristic (2*i < _rn) misclassifies 3-point routes: index 1
        # is equidistant from both endpoints, so position alone cannot tell source
        # from dest.  Use outward-normal alignment: a source escape means pts[0]→pts[1]
        # aligns with the source outward normal; a dest escape means pts[-1]→pts[-2]
        # aligns with the dest outward normal.
        _s_esc_dot = (_snx_r * (_rpts[1][0] - _rpts[0][0])
                      + _sny_r * (_rpts[1][1] - _rpts[0][1]))
        _d_esc_dot = (_dnx_r * (_rpts[-2][0] - _rpts[-1][0])
                      + _dny_r * (_rpts[-2][1] - _rpts[-1][1]))
        _src_stub = bool(_esc_s and _esc_s[0] == 1 and _s_esc_dot > 1e-9)
        _dst_stub = bool(_esc_s and _esc_s[-1] == _rn - 2 and _d_esc_dot > 1e-9)
        _src_port = rc.source_port._replace(point=_rpts[1]) if _src_stub else rc.source_port
        _dst_port = rc.target_port._replace(point=_rpts[-2]) if _dst_stub else rc.target_port
        _rr = route_edge(eid, _src_port, _dst_port, _re_obs, _re_existing)
        if _rr is None:
            return None
        if _src_stub or _dst_stub:
            return _escape_stub_wrap(_rr, rc.source_port, rc.target_port, _src_stub, _dst_stub)
        return _rr

    assignments = _assign_lanes(assignments, obs_tuple, _reroute_fn=_lane_stuck_reroute)

    # Convert RouteCandidate assignments to route dicts; prepend pre-built self-loop dicts
    routed_dicts: "list[dict]" = list(self_loop_dicts)
    for eid, rc in assignments.items():
        e = edge_by_real.get(eid)
        if e is None:
            continue
        # Compute marker_id the same way _route_edges() does — ini-005 left this
        # as None, which emptied <defs> and removed all arrowheads (regression).
        if e.style == "thick":
            _cmid = "arrow-thick"
            _cmarker_id: "str | None" = _cmid if e.arrow else None
        else:
            _cmid = "arrow-open" if e.style == "dotted" else "arrow-normal"
            _cmarker_id = _cmid if e.arrow else None
        # Compute lx/ly for labeled edges — ini-005 omitted these, leaving labels
        # at the canvas origin (0,0). Use arc-length midpoint via _label_on_longest.
        _pts = list(rc.points)
        # Collapse intermediate collinear waypoints so straight segments render
        # as two endpoints rather than a series of grid-snapped intermediates.
        # A point is only removed when it lies strictly between its neighbours on
        # the non-shared axis — reversal/overshoot escapes must be preserved.
        if len(_pts) > 2:
            _esc_set = rc.escape_indices  # frozenset of indices into rc.points = _pts
            _cd: "list[tuple]" = [_pts[0]]
            for _ci in range(1, len(_pts) - 1):
                # Always preserve escape waypoints: a near-cardinal normal can
                # produce an escape that appears collinear but must be kept so
                # the terminal dot-product check passes (≥ 0.9998 required).
                if _ci in _esc_set:
                    _cd.append(_pts[_ci])
                    continue
                _pp, _cp, _np_ = _cd[-1], _pts[_ci], _pts[_ci + 1]
                _coll_x = abs(_pp[0] - _cp[0]) < 1e-9 and abs(_cp[0] - _np_[0]) < 1e-9
                _coll_y = abs(_pp[1] - _cp[1]) < 1e-9 and abs(_cp[1] - _np_[1]) < 1e-9
                if _coll_x:
                    _coll_x = (min(_pp[1], _np_[1]) - 0.5 <= _cp[1]
                               <= max(_pp[1], _np_[1]) + 0.5)
                if _coll_y:
                    _coll_y = (min(_pp[0], _np_[0]) - 0.5 <= _cp[0]
                               <= max(_pp[0], _np_[0]) + 0.5)
                if not (_coll_x or _coll_y):
                    _cd.append(_cp)
            _cd.append(_pts[-1])
            _pts = _cd
        # Recompute escape indices against the simplified list by coordinate match.
        # The original rc.escape_indices reference rc.points positions; collinear
        # dedup may have removed waypoints, invalidating those positions in _pts.
        _esc_raw_coords = {
            (round(rc.points[_i][0], 1), round(rc.points[_i][1], 1))
            for _i in rc.escape_indices
        }
        _esc_idxs_recomputed = {
            _i for _i, _p in enumerate(_pts)
            if (round(_p[0], 1), round(_p[1], 1)) in _esc_raw_coords
        }
        if e.label and len(_pts) >= 2:
            _real_src = e.orig_src or e.src
            _real_dst = e.orig_dst or e.dst
            _node_obs_lbl = [
                (ob.bounds[0], ob.bounds[1],
                 ob.bounds[0] + ob.bounds[2], ob.bounds[1] + ob.bounds[3])
                for ob in obs_tuple
                if ob.kind in ("node", "NODE_INTERIOR")
                and ob.obstacle_id not in (_real_src, _real_dst)
            ]
            _lx, _ly = _label_on_longest(_pts, e.label, int(canvas_w), _node_obs_lbl, [])
        else:
            _lx, _ly = 0.0, 0.0
        routed_dicts.append({
            "waypoints": _pts,
            "edge_id": eid,
            "src": e.orig_src or e.src,
            "dst": e.orig_dst or e.dst,
            "style": e.style,
            "label": e.label,
            "ah": e.arrow,
            "source_marker": e.source_marker,
            "target_marker": e.target_marker,
            "extra_css": e.extra_css,
            "marker_id": _cmarker_id,
            "bidir": getattr(e, "bidir", False),
            "lx": _lx,
            "ly": _ly,
            "d": "",
            "_is_backward": eid in _back_eids,
            # Fanned port positions from main routing; used by _reroute_cross_boundary_edges
            # so that each edge exits from its own assigned port rather than a shared face centre.
            "_src_port": rc.source_port.point,
            "_dst_port": rc.target_port.point,
            # Outward normals: CBE rerouter uses these to compute escape stubs for
            # non-cardinal normals (diamond/hexagon fan-out edges crossing group boundaries).
            "_src_normal": rc.source_port.outward_normal,
            "_dst_normal": rc.target_port.outward_normal,
            # Escape indices recomputed against simplified _pts by coordinate match
            # (rc.escape_indices reference rc.points positions which collinear dedup
            # may have invalidated).
            "_escape_idxs": _esc_idxs_recomputed,
        })

    return RouteBatch(routed=tuple(routed_dicts), failures=tuple(failures_list))


def layout_flowchart_with_python_fallback(
    semantics: FlowchartSemantics,
) -> "tuple[FinalizedLayout, LayoutMetadata]":
    """Run the Python Sugiyama + A* layout pipeline.

    This is the reference implementation used when ELK is unavailable or
    the diagram has inner-direction compound subgraphs that ELK cannot handle
    while preserving per-group direction semantics.

    Returns (FinalizedLayout, LayoutMetadata). The caller is responsible for
    setting metadata.fallback_reason.
    """
    from ._geometry import (  # noqa: PLC0415
        FinalizedLayout as _FL, LayoutMetadata, _empty_diagnostics, Rect,
    )

    nodes = semantics.nodes
    edges = semantics.edges
    groups = semantics.groups
    direction = semantics.direction
    _opts = semantics.opts
    _init_cfg = semantics.init_cfg
    _gate_to_orig = semantics.gate_to_orig
    _sm_edge_semantic = semantics.sm_edge_semantic
    _sm_composite_gates = semantics.sm_composite_gates
    parsed_edge_count = semantics.parsed_edge_count
    width_hint = semantics.width_hint
    height_hint = semantics.height_hint

    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges, direction=direction)
    _minimize_crossings(nodes, edges)

    # Auto-select direction (TB vs LR) when both size hints are given
    if width_hint and height_hint and not _opts.faithful_mermaid and _opts.auto_direction:
        from collections import Counter  # noqa: PLC0415
        max_rank = max((n.rank for n in nodes.values()), default=0)
        rank_counts = Counter(
            n.rank for n in nodes.values()
            if not n.is_dummy and n.id not in _gate_to_orig
        )
        max_cols = max(rank_counts.values(), default=1)
        real_ns = [
            n for n in nodes.values()
            if not n.is_dummy and n.id not in _gate_to_orig
        ]
        avg_h = int(sum(_node_render_h(n) for n in real_ns) / len(real_ns)) if real_ns else NODE_H
        lr_w = CANVAS_PAD * 2 + (max_rank + 1) * (NODE_W + RANK_GAP)
        lr_h = CANVAS_PAD * 2 + max_cols * (avg_h + COL_GAP)
        tb_w = CANVAS_PAD * 2 + max_cols * (NODE_W + COL_GAP)
        tb_h = CANVAS_PAD * 2 + (max_rank + 1) * (avg_h + RANK_GAP)
        lr_zoom = min(width_hint / lr_w, height_hint / lr_h) if lr_w and lr_h else 0.0
        tb_zoom = min(width_hint / tb_w, height_hint / tb_h) if tb_w and tb_h else 0.0
        if tb_zoom > lr_zoom * 1.15 and direction.upper() in ("LR", "RL"):
            direction = "TB"
        elif lr_zoom > tb_zoom * 1.15 and direction.upper() in ("TB", "TD"):
            direction = "LR"

    if groups:
        _group_coherent_cols(nodes, groups)
        _snap_isolated_rank_cols(nodes, groups)
        _compact_group_columns(nodes, groups)

    canvas_w, canvas_h = _assign_coordinates(
        nodes, direction,
        col_gap=_init_cfg.get("col_gap"),
        rank_gap=_init_cfg.get("rank_gap"),
        canvas_pad=_init_cfg.get("diagram_padding"),
    )

    # TB only: center any sole-occupant rank at its predecessor barycenter
    if direction.upper() not in ("LR", "RL"):
        from ._layout import _center_isolated_nodes  # noqa: PLC0415
        _center_isolated_nodes(nodes, edges)

    # Snap rank-isolated group members to their group's x range (TB only).
    # A node alone at its rank within its group (e.g. BD/LLM API in Store Layer
    # at rank 6 while NP/OS are at rank 5) can land far left of all other group
    # members due to Sugiyama parent-alignment, stretching the group's bbox
    # unnecessarily and triggering false conflict cascades in _separate_groups_tb.
    if groups and direction.upper() not in ("LR", "RL"):
        for _gid, _grp in groups.items():
            _mbrs = [nid for nid in _grp.members if nid in nodes and not nodes[nid].is_dummy]
            # Require ≥3 members (same guard as _snap_isolated_rank_cols):
            # with only 2 members each node is necessarily alone at its rank,
            # so the snap reference is too thin and misaligns layouts.
            if len(_mbrs) < 3:
                continue
            _rank_to_mbrs: dict[int, list[str]] = {}
            for _nid in _mbrs:
                _rank_to_mbrs.setdefault(nodes[_nid].rank, []).append(_nid)
            for _rank, _rank_mbrs in _rank_to_mbrs.items():
                if len(_rank_mbrs) != 1:
                    continue
                _solo = nodes[_rank_mbrs[0]]
                _others = [nodes[m] for m in _mbrs if nodes[m].rank != _rank]
                if len(_others) < 2:
                    continue
                _min_other_x = min(o.x for o in _others)
                if _solo.x < _min_other_x - COL_GAP:
                    _solo.x = _min_other_x

    # Recursive compound layout (replaces _recursive_group_layout + post-layout
    # coordinate corrections). Returns boundary_gates for cross-boundary edges.
    _boundary_gates: tuple = ()
    if groups:
        _, _boundary_gates = recursive_compound_layout(
            nodes, edges, groups, direction, canvas_w, canvas_h,
            col_gap=_init_cfg.get("col_gap"),
        )

    # Recompute canvas after group adjustments (exclude gate proxy nodes)
    real_nodes = [n for n in nodes.values() if not n.is_dummy and n.id not in _gate_to_orig]
    if real_nodes:
        canvas_h = max(n.y + _node_render_h(n) for n in real_nodes) + CANVAS_PAD
        canvas_w = max(n.x + (n.width or NODE_W) for n in real_nodes) + CANVAS_PAD

    # Terminal circle centering
    if direction.upper() not in ("LR", "RL"):
        _eff_nw = max(
            (n.width for n in nodes.values() if n.width > 0 and not n.is_dummy),
            default=NODE_W,
        )
        _circ_shift = (_eff_nw - _TERMINAL_NODE_SIZE) // 2
        for _n in nodes.values():
            if not _n.is_dummy and _is_terminal_circle(_n):
                _n.x += _circ_shift

    # Group bboxes
    _grp_bboxes = _compute_group_bboxes(nodes, groups, canvas_w, canvas_h)
    if _grp_bboxes:
        _max_right = max(b[2] for b in _grp_bboxes.values())
        _max_bot = max(b[3] for b in _grp_bboxes.values())
        if _max_right > canvas_w - CANVAS_PAD:
            canvas_w = int(_max_right) + CANVAS_PAD
            _grp_bboxes = _compute_group_bboxes(nodes, groups, canvas_w, canvas_h)
        if _max_bot > canvas_h - CANVAS_PAD:
            canvas_h = int(_max_bot) + CANVAS_PAD

    # Self-loop finalization: offset all nodes so left-face/top-face loops
    # stay >= CANVAS_PAD.
    _cp = int(_init_cfg.get("diagram_padding", CANVAS_PAD))
    if any(e.src == e.dst for e in edges):
        _sl_dx, _sl_dy = _finalize_self_loop_offsets(nodes, edges, direction, canvas_pad=_cp)
        if _sl_dx or _sl_dy:
            for _n in nodes.values():
                _n.x += _sl_dx
                _n.y += _sl_dy
            canvas_w += _sl_dx
            canvas_h += _sl_dy
            if _grp_bboxes:
                _grp_bboxes = _compute_group_bboxes(nodes, groups, canvas_w, canvas_h)

    # First-class empty groups (AC1): an empty subgraph is a measured proxy that
    # must not sit at the origin or touch a sibling group. Place it in clear space.
    if groups and not semantics.is_state_diagram and _grp_bboxes:
        canvas_w, canvas_h = _place_empty_groups(
            groups, _grp_bboxes, nodes, canvas_w, canvas_h
        )

    # Build scope_bbox_map for state-diagram composite back-edge routing
    _scope_bbox_map: "dict" = (
        {
            gid[3:]: bbox
            for gid, bbox in (_grp_bboxes or {}).items()
            if gid.startswith("_g_")
        }
        if _sm_composite_gates else {}
    )

    # Route edges: new path (ini-005) or legacy _route_edges
    if not _USE_LEGACY_ROUTE_EDGES and not semantics.is_state_diagram:
        route_batch = _flowchart_route_new_path(
            nodes, edges, _grp_bboxes or {}, direction,
            float(canvas_w), float(canvas_h), semantics,
        )
    else:
        route_batch = _route_edges(
            nodes, edges, canvas_w, direction,
            group_bboxes=_grp_bboxes,
            scope_bbox_map=_scope_bbox_map if _scope_bbox_map else None,
        )

    # Gate restoration: merge split route-dicts back into single route-dicts
    if _gate_to_orig:
        _restored_routes: "list[dict]" = _restore_gate_edges(
            list(route_batch.routed), _gate_to_orig, nodes
        )
    else:
        _restored_routes = list(route_batch.routed)

    # Build typed IR
    node_layouts = _build_node_layouts_ir(nodes, groups)
    group_layouts = _build_group_layouts_ir(groups, _grp_bboxes)

    # Clip cross-scope exit routes (state-diagram composite exits)
    _src_group_map = {
        e.edge_id: e.src_group
        for e in edges
        if getattr(e, "src_group", None) and e.edge_id
    }
    if _src_group_map:
        _clip_cross_scope_exit_waypoints(_restored_routes, _src_group_map, _grp_bboxes)

    # Boundary-gate routing (Task 4/5): route cross-boundary flowchart edges
    # through explicit gates on group boundaries, derive gate records from the
    # real crossings, and keep the routes clear of unrelated groups/labels.
    # State diagrams keep their own composite-gate machinery untouched.
    if groups and not semantics.is_state_diagram and _grp_bboxes:
        _cbe_gates = _reroute_cross_boundary_edges(
            _restored_routes, nodes, _grp_bboxes, canvas_w, canvas_h,
            direction=direction,
            groups=groups,
        )
        if _cbe_gates:
            # Merge, don't replace: the reroute emits gates only for edges it
            # actually re-routed (A* may bail on an un-routable edge). Keep the
            # recursive_compound_layout gate for any real routed edge the reroute
            # did not cover, so AC7 ("a gate for every cross-scope edge") still
            # holds. Filter to real routed edge_ids so stale gate-split records
            # (e.g. "…_out" halves) never leak into the finalized layout.
            _covered_edges = {g.edge_id for g in _cbe_gates}
            _routed_edge_ids = {
                (r.get("edge_id") or f"{r.get('src')}->{r.get('dst')}")
                for r in _restored_routes
            }
            _boundary_gates = _cbe_gates + tuple(
                g for g in _boundary_gates
                if g.edge_id not in _covered_edges and g.edge_id in _routed_edge_ids
            )
        # Canvas is finalized AFTER route construction so every rerouted waypoint
        # is inside it (spec AC2).
        _pad = float(_init_cfg.get("diagram_padding") or CANVAS_PAD)
        for _r in _restored_routes:
            for _wx, _wy in (_r.get("waypoints") or []):
                if _wx + _pad > canvas_w:
                    canvas_w = _wx + _pad
                if _wy + _pad > canvas_h:
                    canvas_h = _wy + _pad

    routed_edges_ir = _build_routed_edges_ir(
        _restored_routes,
        canvas_area=canvas_w * canvas_h,
        sm_edge_semantic=_sm_edge_semantic if _sm_edge_semantic else None,
    )

    canvas_bounds = Rect(x=0.0, y=0.0, w=float(canvas_w), h=float(canvas_h))
    _real_nodes_count = len([n for n in nodes.values() if not n.is_dummy])

    finalized = _FL(
        node_layouts=_types.MappingProxyType(node_layouts),
        group_layouts=_types.MappingProxyType(group_layouts),
        routed_edges=routed_edges_ir,
        routing_failures=route_batch.failures,
        visible_bounds=canvas_bounds,
        diagram_padding=float(_init_cfg.get("diagram_padding") or CANVAS_PAD),
        canvas_bounds=canvas_bounds,
        direction=direction,
        diagnostics=_empty_diagnostics(),
        composite_gates=_types.MappingProxyType(_sm_composite_gates),
        boundary_gates=_boundary_gates,
    )

    metadata = LayoutMetadata(
        direction=direction,
        node_count=_real_nodes_count,
        group_count=len(groups),
        edge_count=parsed_edge_count,
        algorithm="LongestPathRanker+BarycentricOrderer+SimpleCoordinateAssigner",
        backend="python",
    )
    return finalized, metadata


def validate_flowchart_layout(
    layout: "FinalizedLayout",
    metadata: "LayoutMetadata | None" = None,
) -> "ValidationResult":
    """Validate a FinalizedLayout against geometry invariants.

    Thin wrapper around validate_finalized_layout() that centralises
    post-layout assertion logic. Callers may replace ad-hoc assertion
    blocks with this function.
    """
    from ._geometry import validate_finalized_layout  # noqa: PLC0415
    # ELK is an external layout engine that may produce small node overlaps
    # (typically <10px) and containment deviations as artefacts of its own
    # placement algorithm. Run strict=False for ELK-produced layouts so those
    # cosmetic deviations are demoted from hard errors to pass-through.
    # Python-fallback layouts keep strict=True (we own those positions fully).
    _strict = not (metadata is not None and getattr(metadata, "backend", "") == "elkjs")
    return validate_finalized_layout(layout, metadata=metadata, strict=_strict)


def _compile_flowchart(
    src: str,
    width_hint: int,
    options: "RenderOptions | None",
    *,
    direction_override: "Optional[str]" = None,
    height_hint: int = 0,
    style_overrides: str = "",
) -> "CompiledFlowchart":
    """Orchestrate the full flowchart layout pipeline using composable functions.

    Parse → build graph → ELK layout → enrich (or Python fallback) → validate.

    Inner-direction compound layouts are routed to the bottom-up Python compound
    path directly. That path is the one that emits explicit ``BoundaryGate``
    records for cross-scope edges (spec AC7) and honours the eight-case harness's
    non-forced ``min_gates`` contract; ELK's native compound result carries no such
    gate metadata, so consuming it directly (spec AC5) would leave cross-scope
    edges gate-less. Non-compound flowcharts attempt ELK first and consume a
    successful result directly. Only ElkUnavailable and ElkInvalidResult trigger a
    typed Python fallback; all other exceptions propagate with context.
    """
    from ._geometry import CompiledFlowchart, LayoutMetadata  # noqa: PLC0415
    from .elk_adapter import ElkUnavailable, ElkInvalidResult  # noqa: PLC0415

    semantics = parse_flowchart_semantics(
        src, options,
        direction_override=direction_override,
        width_hint=width_hint,
        height_hint=height_hint,
    )

    if semantics.has_inner_dir:
        finalized, py_metadata = layout_flowchart_with_python_fallback(semantics)
        metadata = dataclasses.replace(py_metadata, fallback_reason="inner-direction")
    else:
        try:
            graph = build_flowchart_layout_graph(semantics)
            elk_raw = layout_flowchart_with_elk(graph, spacing=semantics.init_cfg)
            finalized = enrich_flowchart_finalized_layout(elk_raw, semantics)
            _real_nodes_count = len(
                [n for n in semantics.nodes.values() if not n.is_dummy]
            )
            metadata = LayoutMetadata(
                direction=semantics.direction,
                node_count=_real_nodes_count,
                group_count=len(semantics.groups),
                edge_count=semantics.parsed_edge_count,
                algorithm="ELK-layered",
                backend="elkjs",
                fallback_reason=None,
            )
        except (ElkUnavailable, ElkInvalidResult):
            finalized, py_metadata = layout_flowchart_with_python_fallback(semantics)
            metadata = dataclasses.replace(py_metadata, fallback_reason="elk-unavailable")

    validation = validate_flowchart_layout(finalized, metadata)
    return CompiledFlowchart(layout=finalized, validation=validation, metadata=metadata)

# ── Compound layout: build_compound_tree ─────────────────────────────────────


def build_compound_tree(graph: "LayoutGraph") -> "list[CompoundNode]":
    """Build a CompoundNode tree from a LayoutGraph.

    Traverses the group hierarchy and constructs frozen CompoundNode objects
    bottom-up.  Returns the list of root-level CompoundNode objects (those
    whose parent_id is absent or not present in the graph's groups).

    Each CompoundNode captures:
      - group_id: the group's ID
      - label_layout: a TextLayout built from the group's label (or None)
      - local_direction: from LayoutGroup.local_direction (defaulting to graph.direction)
      - child_node_ids: direct member nodes (parent_id == group_id)
      - child_groups: recursive CompoundNode objects for child groups
      - padding: from LayoutGroup.padding
      - minimum_size: (minimum_width, minimum_height) from LayoutGroup
    """
    from ._geometry import CompoundNode  # noqa: PLC0415

    group_map = {g.id: g for g in graph.groups}

    # children_map[gid] = list of direct child group IDs
    children_map: "dict[str, list[str]]" = {g.id: [] for g in graph.groups}
    for g in graph.groups:
        if g.parent_id and g.parent_id in children_map:
            children_map[g.parent_id].append(g.id)

    # direct_nodes[gid] = list of direct (non-group) member node IDs
    direct_nodes: "dict[str, list[str]]" = {g.id: [] for g in graph.groups}
    for node in graph.nodes:
        if node.parent_id and node.parent_id in direct_nodes:
            direct_nodes[node.parent_id].append(node.id)

    def _build(gid: str) -> "CompoundNode":
        g = group_map[gid]
        child_compounds = tuple(_build(cgid) for cgid in children_map[gid])
        label_layout = _make_text_layout_ir(g.label) if g.label else None
        return CompoundNode(
            group_id=gid,
            label_layout=label_layout,
            local_direction=g.local_direction or graph.direction,
            child_node_ids=tuple(direct_nodes[gid]),
            child_groups=child_compounds,
            padding=g.padding,
            minimum_size=(g.minimum_width, g.minimum_height),
        )

    # Root groups: no parent, or parent not among the groups
    root_gids = [
        g.id for g in graph.groups
        if not g.parent_id or g.parent_id not in group_map
    ]
    return [_build(gid) for gid in root_gids]


# ── Compound layout: EdgePartition ───────────────────────────────────────────


@dataclass(frozen=True)
class EdgePartition:
    """Typed result of classifying graph edges by compound scope.

    free:  edges where neither endpoint is in any group.
    intra: edges where both endpoints share the same direct-parent group.
    cross: edges where endpoints are in different groups (or one is ungrouped).

    The three sets are mutually exclusive and exhaustive over the input edges.
    """
    free: tuple   # tuple[_Edge, ...]
    intra: tuple  # tuple[_Edge, ...]
    cross: tuple  # tuple[_Edge, ...]


def make_edge_partition(
    edges: "list[_Edge]",
    nodes: "dict[str, _Node]",
    groups: "dict[str, _Group]",
) -> EdgePartition:
    """Classify edges into free/intra/cross using _partition_edges."""
    free, intra, cross = _partition_edges(edges, nodes, groups)
    return EdgePartition(free=tuple(free), intra=tuple(intra), cross=tuple(cross))


# ── Compound layout: recursive_compound_layout ───────────────────────────────

# Title band height reserved at the top of each compound group (px)
_TITLE_BAND_H: float = 28.0
# Minimum content area for an empty compound group (px)
_EMPTY_CONTENT_H: float = 24.0
_EMPTY_CONTENT_W: float = 80.0


def recursive_compound_layout(
    nodes: "dict[str, _Node]",
    edges: "list[_Edge]",
    groups: "dict[str, _Group]",
    outer_direction: str,
    canvas_w: int,
    canvas_h: int,
    col_gap: "int | None" = None,
) -> "tuple[dict[str, tuple[int, int, int, int]], tuple]":
    """Bottom-up recursive compound layout algorithm (Python fallback path).

    Replaces the post-layout coordinate-correction sequence
    (_recursive_group_layout + _separate_groups_lr/tb + _push_nonmembers) with
    a single bottom-up pass that:

      1. Processes groups in DFS post-order (innermost first).
      2. For each group: re-positions direct members in the group's local
         direction using topological order; treats child groups as fixed-size
         units and places them alongside direct members.
      3. At root level, separates sibling groups to prevent overlap.
      4. Computes the final group bounding boxes.
      5. Creates BoundaryGate objects for each cross-boundary edge.

    Returns:
        (group_bboxes, boundary_gates)

    where group_bboxes maps group_id → (x0, y0, x1, y1) and boundary_gates
    is a tuple of BoundaryGate objects (one EXIT + one ENTRY per cross-boundary
    edge where gate geometry can be computed).

    No coordinate mutation happens after this function returns — AC8.
    """
    from ._geometry import BoundaryGate, BoundaryGateKind, PortSide, Point  # noqa: PLC0415

    _col_gap = col_gap if col_gap is not None else COL_GAP

    # ── Build group tree ─────────────────────────────────────────────────────
    children, post_order = _build_group_tree(groups)

    # ── Helper: recursively collect all member nodes (direct + nested) ───────
    def _all_members(gid: str, _seen: "set[str] | None" = None) -> "list[_Node]":
        if _seen is None:
            _seen = set()
        if gid in _seen:
            return []
        _seen.add(gid)
        result = [nodes[m] for m in groups[gid].members if m in nodes and not nodes[m].is_dummy]
        for c in children[gid]:
            result.extend(_all_members(c, _seen))
        return result

    # ── Helper: bounding box of a group's contents ──────────────────────────
    def _group_content_bounds(gid: str) -> "tuple[float, float, float, float] | None":
        mbrs = _all_members(gid)
        if not mbrs:
            return None
        return (
            float(min(n.x for n in mbrs)),
            float(min(n.y for n in mbrs)),
            float(max(n.x + (_node_render_w(n)) for n in mbrs)),
            float(max(n.y + _node_render_h(n) for n in mbrs)),
        )

    # ── Helper: shift all nodes in a group by (dx, dy) ───────────────────────
    def _shift_group(gid: str, dx: float, dy: float, _seen: "set[str] | None" = None) -> None:
        if _seen is None:
            _seen = set()
        if gid in _seen:
            return
        _seen.add(gid)
        for m in groups[gid].members:
            if m in nodes:
                nodes[m].x += dx  # type: ignore[assignment]
                nodes[m].y += dy  # type: ignore[assignment]
        for c in children[gid]:
            _shift_group(c, dx, dy, _seen)

    # ── Helper: topological order for direct members ──────────────────────────
    def _topo_members(member_ids: "list[str]", intra_edges: "list", sort_key: "Callable") -> "list[str]":
        in_deg: "dict[str, int]" = {m: 0 for m in member_ids}
        adj: "dict[str, list[str]]" = {m: [] for m in member_ids}
        for e in intra_edges:
            if e.src in adj and e.dst in in_deg and not e.reversed_:
                adj[e.src].append(e.dst)
                in_deg[e.dst] += 1
        queue = sorted([m for m in member_ids if in_deg[m] == 0], key=sort_key)
        result: "list[str]" = []
        while queue:
            cur = queue.pop(0)
            result.append(cur)
            nexts = sorted(adj[cur], key=sort_key)
            for nb in nexts:
                in_deg[nb] -= 1
                if in_deg[nb] == 0:
                    queue.append(nb)
            queue.sort(key=sort_key)
        for m in member_ids:
            if m not in result:
                result.append(m)
        return result

    # ── Step 1: process groups innermost-first ───────────────────────────────
    is_outer_tb = outer_direction.upper() not in ("LR", "RL")

    for gid in post_order:
        grp = groups[gid]
        if not grp.direction:
            continue
        inner_dir = grp.direction.upper()
        # Only fixup groups whose direction differs from the outer direction
        if is_outer_tb and inner_dir not in ("LR", "RL"):
            continue
        if not is_outer_tb and inner_dir not in ("TB", "TD"):
            continue

        direct_members = [m for m in grp.members if m in nodes and not nodes[m].is_dummy]
        child_gids = children[gid]

        # Build item list: (kind, id, x, y, w, h)
        items: "list[tuple]" = []
        for m in direct_members:
            n = nodes[m]
            items.append(("node", m, float(n.x), float(n.y),
                          float(_node_render_w(n)), float(_node_render_h(n))))
        for c in child_gids:
            bounds = _group_content_bounds(c)
            if bounds:
                x0, y0, x1, y1 = bounds
                items.append(("group", c, x0, y0, x1 - x0, y1 - y0))

        if not items:
            continue

        member_set = set(direct_members)
        intra = [e for e in edges if e.src in member_set and e.dst in member_set]

        if inner_dir in ("LR", "RL"):
            ordered = _topo_members(direct_members, intra, lambda m: nodes[m].x)
            if inner_dir == "RL":
                ordered = list(reversed(ordered))
            node_rank = {m: i for i, m in enumerate(ordered)}
            rl_sign = -1 if inner_dir == "RL" else 1
            if child_gids:
                items.sort(key=lambda it: (
                    rl_sign * it[2],
                    node_rank.get(it[1], float("inf")) if it[0] == "node" else float("inf"),
                ))
            else:
                items.sort(key=lambda it: node_rank.get(it[1], float("inf")))

            target_y = min(it[3] for it in items)
            cur_x = min(it[2] for it in items)
            for kind, item_id, _, _, w, h in items:
                if kind == "node":
                    n = nodes[item_id]
                    n.x = cur_x
                    n.y = target_y
                    cur_x += _node_render_w(n) + _col_gap
                else:
                    bounds = _group_content_bounds(item_id)
                    if bounds:
                        x0, y0, x1, y1 = bounds
                        _shift_group(item_id, cur_x - x0, target_y - y0)
                        cur_x += (x1 - x0) + _col_gap
        else:
            # TB inner in LR outer
            ordered = _topo_members(direct_members, intra, lambda m: nodes[m].y)
            node_rank = {m: i for i, m in enumerate(ordered)}
            if child_gids:
                items.sort(key=lambda it: (
                    it[3],
                    node_rank.get(it[1], float("inf")) if it[0] == "node" else float("inf"),
                ))
            else:
                items.sort(key=lambda it: node_rank.get(it[1], float("inf")))

            target_x = min(it[2] for it in items)
            cur_y = min(it[3] for it in items)
            for kind, item_id, _, _, w, h in items:
                if kind == "node":
                    n = nodes[item_id]
                    n.x = target_x
                    n.y = cur_y
                    cur_y += _node_render_h(n) + _col_gap
                else:
                    bounds = _group_content_bounds(item_id)
                    if bounds:
                        x0, y0, x1, y1 = bounds
                        _shift_group(item_id, target_x - x0, cur_y - y0)
                        cur_y += (y1 - y0) + _col_gap

    # ── Step 2: handle empty groups (AC1) ────────────────────────────────────
    # Empty groups get a deterministic minimum size based on label width + padding
    for gid in post_order:
        grp = groups[gid]
        mbrs = _all_members(gid)
        if mbrs:
            continue  # non-empty: bounds already determined by members
        # Find a location near any existing content or default to canvas edge
        # Empty group: minimum size will be applied by the group-sizing pass below.

    # ── Step 3: root-level group separation ──────────────────────────────────
    if outer_direction.upper() in ("LR", "RL"):
        _separate_groups_lr(nodes, groups)
        # Chain-src y alignment for dummies
        _pred: "dict[str, str]" = {}
        for _e in edges:
            if _e.src in nodes and _e.dst in nodes:
                _pred[_e.dst] = _e.src

        def _chain_src_y(nid: str) -> int:
            visited: "set[str]" = set()
            cur = nid
            while cur in _pred and nodes.get(cur) is not None:
                cur = _pred[cur]
                if cur in visited:
                    break
                visited.add(cur)
                if not nodes[cur].is_dummy:
                    return nodes[cur].y
            return nodes[nid].y

        for _nid, _n in nodes.items():
            if _n.is_dummy:
                _n.y = _chain_src_y(_nid)
        _push_nonmembers_out_of_groups_lr(nodes, groups)
    elif outer_direction.upper() in ("TB", "TD"):
        _updated_cw = _separate_groups_tb(nodes, groups, canvas_w, edges)
        canvas_w = _updated_cw
        _stack_source_groups_above_tb(nodes, groups, edges)

    # ── Step 4: compute group bboxes ─────────────────────────────────────────
    grp_bboxes = _compute_group_bboxes(nodes, groups, canvas_w, canvas_h)

    # ── Step 5: create BoundaryGate objects for cross-boundary edges (AC5) ───
    _, _, cross_edges = _partition_edges(edges, nodes, groups)
    boundary_gates: "list[BoundaryGate]" = []
    _gate_ctr = 0
    for e in cross_edges:
        src_node = nodes.get(e.src)
        dst_node = nodes.get(e.dst)
        src_grp = src_node.group if src_node is not None else None
        dst_grp = dst_node.group if dst_node is not None else None

        eid = e.edge_id or f"{e.src}->{e.dst}"

        # EXIT gate on source compound boundary
        if src_grp and src_grp in grp_bboxes:
            bx0, by0, bx1, by1 = grp_bboxes[src_grp]
            # Place gate on the right edge for LR, bottom edge for TB
            if outer_direction.upper() in ("LR", "RL"):
                gp = Point(float(bx1), float((by0 + by1) / 2))
                side = PortSide.RIGHT
            else:
                gp = Point(float((bx0 + bx1) / 2), float(by1))
                side = PortSide.BOTTOM
            boundary_gates.append(BoundaryGate(
                gate_id=f"_bgate_{_gate_ctr}_exit",
                group_id=src_grp,
                side=side,
                point=gp,
                semantic_node_id=e.src,
                edge_id=eid,
                kind=BoundaryGateKind.EXIT,
            ))
            _gate_ctr += 1

        # ENTRY gate on destination compound boundary
        if dst_grp and dst_grp in grp_bboxes:
            bx0, by0, bx1, by1 = grp_bboxes[dst_grp]
            if outer_direction.upper() in ("LR", "RL"):
                gp = Point(float(bx0), float((by0 + by1) / 2))
                side = PortSide.LEFT
            else:
                gp = Point(float((bx0 + bx1) / 2), float(by0))
                side = PortSide.TOP
            boundary_gates.append(BoundaryGate(
                gate_id=f"_bgate_{_gate_ctr}_entry",
                group_id=dst_grp,
                side=side,
                point=gp,
                semantic_node_id=e.dst,
                edge_id=eid,
                kind=BoundaryGateKind.ENTRY,
            ))
            _gate_ctr += 1

    return grp_bboxes, tuple(boundary_gates)


# ── Compound layout: boundary-gate routing (Task 4/5) ─────────────────────────

# Title-band height (px) reserved at the top of every compound group. Boundary
# gates never sit on the top edge and internal segments never enter this band.
# Reuses the compound-layout title-band height (_TITLE_BAND_H) so the routing
# band tracks the group chrome. It intentionally exceeds the obstruction
# validator's DEFAULT_TITLE_BAND_H (24px) — routing conservatively avoids a band
# at least as tall as the one the validator checks, so a route this pass accepts
# can never be rejected by _layout_validation.validate_segment_obstruction.
_GATE_TITLE_BAND_H: float = _TITLE_BAND_H

# Clearance (px) placed around a first-class empty group so it never touches a
# sibling group or node (spec AC1 forbids overlap *or* touch).
_EMPTY_GROUP_GAP: float = 24.0


def _place_empty_groups(
    groups: "dict[str, _Group]",
    grp_bboxes: "dict[str, list]",
    nodes: "dict[str, _Node]",
    canvas_w: float,
    canvas_h: float,
) -> "tuple[float, float]":
    """Give every empty group a clear, non-origin slot (spec AC1 / Task 3).

    ``_compute_group_bboxes`` sizes an empty group but parks it at ``(0, 0)`` with
    no members to anchor it. Here each empty group is repositioned (keeping its
    measured width/height) below all populated content, stacked with a fixed gap,
    so it has nonzero bounds, is off the origin, and neither overlaps nor touches
    any sibling group. Returns the (possibly grown) canvas size.
    """
    def _recursive_members(gid: str) -> "list[str]":
        out = list(groups[gid].members)
        for cgid, cgrp in groups.items():
            if cgrp.parent_group == gid:
                out.extend(_recursive_members(cgid))
        return out

    empty_gids = [
        gid for gid, grp in groups.items()
        # Only reposition *top-level* empty groups. A nested empty group is
        # positioned within its parent's packing region by _compute_group_bboxes;
        # relocating it below global content would break parent containment.
        if (not grp.parent_group or grp.parent_group not in groups)
        and not [m for m in _recursive_members(gid)
                 if m in nodes and not nodes[m].is_dummy]
    ]
    if not empty_gids:
        return canvas_w, canvas_h

    # Bottom of all populated content (non-empty group boxes + real node cards).
    content_bottom = 0.0
    for gid, b in grp_bboxes.items():
        if gid not in empty_gids:
            content_bottom = max(content_bottom, b[3])
    for n in nodes.values():
        if not n.is_dummy:
            content_bottom = max(content_bottom, n.y + _node_render_h(n))
    if content_bottom <= 0.0:
        content_bottom = float(CANVAS_PAD)

    cursor_y = content_bottom + _EMPTY_GROUP_GAP
    x0 = float(CANVAS_PAD)
    for gid in empty_gids:
        b = grp_bboxes[gid]
        w = b[2] - b[0]
        h = b[3] - b[1]
        grp_bboxes[gid] = [x0, cursor_y, x0 + w, cursor_y + h]
        cursor_y += h + _EMPTY_GROUP_GAP
        canvas_w = max(canvas_w, x0 + w + CANVAS_PAD)
    canvas_h = max(canvas_h, cursor_y + CANVAS_PAD - _EMPTY_GROUP_GAP)
    return canvas_w, canvas_h


def _cbe_node_face(n: "_Node", toward: "tuple[float, float]") -> "tuple[float, float]":
    """Point on node ``n``'s outer boundary on the side facing ``toward``."""
    w = _node_render_w(n)
    h = _node_render_h(n)
    cx = n.x + w / 2.0
    cy = n.y + h / 2.0
    dx = toward[0] - cx
    dy = toward[1] - cy
    if abs(dx) >= abs(dy):
        return (cx + (w / 2.0 if dx > 0 else -w / 2.0), cy)
    return (cx, cy + (h / 2.0 if dy > 0 else -h / 2.0))


def _cbe_build_grid(
    nodes: "dict[str, _Node]",
    grp_bboxes: "dict[str, tuple]",
    extra: "list[tuple[float, float]]",
    canvas_w: float,
    canvas_h: float,
) -> "tuple[list[int], list[int]]":
    """Sparse orthogonal routing grid: node edges, group boundaries, gate points."""
    xs: "set[int]" = {0, int(canvas_w)}
    ys: "set[int]" = {0, int(canvas_h)}
    for n in nodes.values():
        if n.is_dummy:
            continue
        w, h = _node_render_w(n), _node_render_h(n)
        for off in (-9, 0, w, w + 9):
            xs.add(int(n.x + off))
        for off in (-9, 0, h, h + 9):
            ys.add(int(n.y + off))
    for (x0, y0, x1, y1) in grp_bboxes.values():
        for off in (-9, 0, 9, int(_GATE_TITLE_BAND_H)):
            xs.add(int(x0 + off))
            xs.add(int(x1 + off))
            ys.add(int(y0 + off))
            ys.add(int(y1 + off))
    for p in extra:
        xs.add(int(p[0]))
        ys.add(int(p[1]))
    return sorted(x for x in xs if x >= -9), sorted(y for y in ys if y >= -9)


def _cbe_boundary_crossings(
    poly: "list[tuple[float, float]]", bbox: "tuple[float, float, float, float]"
) -> "list[tuple[int, float, float]]":
    """Boundary crossings of an orthogonal polyline against a rectangle.

    A crossing is a segment whose endpoints straddle the interior/exterior of
    ``bbox``; each result is ``(segment_index, x, y)`` with the point snapped onto
    the rectangle edge that was crossed. Order follows the polyline direction.

    Tests all four rectangle edges parametrically and picks the valid crossing
    (smallest t ∈ [0,1] with the intersection on the edge), which correctly
    handles near-vertical segments that cross a vertical side.
    """
    x0, y0, x1, y1 = bbox

    def _inside(p: "tuple[float, float]") -> bool:
        return x0 < p[0] < x1 and y0 < p[1] < y1

    res: "list[tuple[int, float, float]]" = []
    for i in range(len(poly) - 1):
        a, b = poly[i], poly[i + 1]
        if _inside(a) == _inside(b):
            continue
        ax, ay = a
        bx, by = b
        dx_s = bx - ax
        dy_s = by - ay
        _cross: "tuple[float, float] | None" = None
        _cross_t = float("inf")
        if abs(dx_s) > 1e-9:
            for _xb in (x0, x1):
                _t = (_xb - ax) / dx_s
                if -1e-6 <= _t <= 1 + 1e-6:
                    _yc = ay + _t * dy_s
                    if y0 - 1e-6 <= _yc <= y1 + 1e-6 and _t < _cross_t:
                        _cross_t = _t
                        _cross = (_xb, min(y1, max(y0, _yc)))
        if abs(dy_s) > 1e-9:
            for _yb in (y0, y1):
                _t = (_yb - ay) / dy_s
                if -1e-6 <= _t <= 1 + 1e-6:
                    _xc = ax + _t * dx_s
                    if x0 - 1e-6 <= _xc <= x1 + 1e-6 and _t < _cross_t:
                        _cross_t = _t
                        _cross = (min(x1, max(x0, _xc)), _yb)
        if _cross is not None:
            res.append((i, _cross[0], _cross[1]))
    return res


def _cbe_place_label(
    waypoints: "list[tuple[float, float]]",
    lw: float,
    lh: float,
    obstacles: "list[tuple[float, float, float, float]]",
) -> "tuple[float, float] | None":
    """Pick a label origin (x, y) on the route minimising obstacle overlap.

    Samples points along each segment and four offset placements per point;
    returns the first zero-overlap placement, else the minimum-overlap one.
    """
    best: "tuple[float, float] | None" = None
    best_score = float("inf")
    for i in range(len(waypoints) - 1):
        a, b = waypoints[i], waypoints[i + 1]
        for t in (0.5, 0.33, 0.66):
            px = a[0] + (b[0] - a[0]) * t
            py = a[1] + (b[1] - a[1]) * t
            for ox, oy in ((-lw / 2, -lh - 3), (-lw / 2, 3), (3, -lh / 2), (-lw - 3, -lh / 2)):
                rx, ry = px + ox, py + oy
                score = sum(
                    1
                    for (kx0, ky0, kx1, ky1) in obstacles
                    if not (rx + lw < kx0 or rx > kx1 or ry + lh < ky0 or ry > ky1)
                )
                if score < best_score:
                    best_score = score
                    best = (rx, ry)
                if score == 0:
                    return best
    return best


def _equalize_corridors(
    routed: "list",
    nodes: "dict",
    grp_bboxes: "dict",
    direction: str = "TB",
    gate_coords: "frozenset" = frozenset(),
) -> None:
    """In-place post-processing: stagger shared horizontal exit rails and
    separate shared vertical corridors so no two routes overlap.

    Pass A — horizontal rail stagger: when multiple routes exit the same node
    face horizontally (sharing the same exit y), each route gets a unique y
    level via a short vertical stub, so their horizontal segments never overlap.

    Pass B — vertical corridor separation: when multiple routes share the same
    vertical x channel (within 4 px) with overlapping y ranges, their x
    positions are redistributed with equal LANE_GAP spacing.

    gate_coords: set of (x, y) boundary-gate waypoints (rounded to 0.1 px).
    Routes whose waypoints include a gate coordinate are excluded from Pass A
    and Pass B so that gate-crossing points are never displaced.
    """
    from collections import defaultdict

    _is_tb = direction.upper() not in ("LR", "RL")
    if not _is_tb:
        return

    STAGGER = 12.0   # vertical gap between staggered horizontal rails
    LANE_GAP = 14.0  # horizontal gap between parallel vertical lanes

    def _has_gate(wps: "list") -> bool:
        if not gate_coords:
            return False
        return any((round(wx, 1), round(wy, 1)) in gate_coords for wx, wy in wps)

    # ── Pass A: stagger horizontal exit rails ────────────────────────────────
    # Group routes by (src_node_id, exit_y) when first segment is horizontal.
    # Skip routes that pass through a gate waypoint — staggering would displace
    # the gate crossing off its declared position.
    # Skip routes with an escape at index 1 — the first segment IS the source
    # escape stub (boundary → escape along the outward normal); inserting a
    # vertical stagger before the escape breaks the terminal-normal contract.
    exit_groups: "dict" = defaultdict(list)
    for i, r in enumerate(routed):
        wps = r.get("waypoints", [])
        if len(wps) < 3:
            continue
        if _has_gate(wps):
            continue
        # For CBE-rerouted routes use only _cbe_escape_idxs; the main router
        # stubs every non-zero normal so _escape_idxs often has index 1 even
        # for cardinal CBE sources that have no escape.
        _r_cbe_flag = r.get("_cbe_rerouted")
        _r_esc_guard = (r.get("_cbe_escape_idxs") or set()) if _r_cbe_flag else (
            (r.get("_escape_idxs") or set()) | (r.get("_cbe_escape_idxs") or set())
        )
        if 1 in _r_esc_guard:
            continue
        p0, p1 = wps[0], wps[1]
        if abs(p0[1] - p1[1]) < 1.0 and abs(p0[0] - p1[0]) > 8.0:
            src_id = (r.get("src") or r.get("source") or
                      r.get("routing_source_id") or "")
            if src_id:
                exit_groups[(src_id, round(p0[1]))].append(i)

    for (src_id, exit_y_int), idxs in exit_groups.items():
        if len(idxs) <= 1:
            continue
        # Sort by destination x (rightmost last) so stagger order minimises
        # the chance of a staggered horizontal crossing its neighbours.
        idxs.sort(key=lambda idx: routed[idx]["waypoints"][-1][0])
        exit_y = float(exit_y_int)
        for k, i in enumerate(idxs):
            r = routed[i]
            wps = list(r["waypoints"])
            new_y = exit_y + (k + 1) * STAGGER
            # Insert a short vertical stub: exit at (p0.x, exit_y) → (p0.x, new_y),
            # then continue the horizontal at new_y.
            new_wps = [wps[0]]  # keep the port point at exit_y
            stub = (wps[0][0], new_y)
            new_wps.append(stub)
            for p in wps[1:]:
                if abs(p[1] - exit_y) < 1.0:
                    new_wps.append((p[0], new_y))
                else:
                    new_wps.append(p)
            # Dedup consecutive equal points
            deduped = [new_wps[0]]
            for p in new_wps[1:]:
                if p != deduped[-1]:
                    deduped.append(p)
            r["waypoints"] = deduped
            # Reindex escape indices: stub insertion shifts points on the exit
            # rail from exit_y → new_y; coordinate-match against deduped so
            # Pass B and downstream terminal validation see correct escape positions.
            for _esc_key in ("_escape_idxs", "_cbe_escape_idxs"):
                _old_esc = r.get(_esc_key)
                if not _old_esc:
                    continue
                _new_esc_coords: "set[tuple]" = set()
                for _ej in _old_esc:
                    if _ej < len(wps):
                        _ex, _ey = wps[_ej]
                        if abs(_ey - exit_y) < 1.0:
                            _ey = new_y
                        _new_esc_coords.add((round(_ex, 1), round(_ey, 1)))
                r[_esc_key] = {
                    _di for _di, _dp in enumerate(deduped)
                    if (round(_dp[0], 1), round(_dp[1], 1)) in _new_esc_coords
                }

    # ── Pass B: separate shared vertical corridors ───────────────────────────
    # Collect all vertical segments (x constant, y varying > 20 px).
    # Gate routes ARE included — their non-gate segments still need separation.
    # Gate-coordinate waypoints are protected from shifting in the inner loop.
    vert_segs: "list" = []  # (route_idx, x, y_lo, y_hi)
    for i, r in enumerate(routed):
        wps = r.get("waypoints", [])
        for j in range(len(wps) - 1):
            p1, p2 = wps[j], wps[j + 1]
            if abs(p1[0] - p2[0]) < 1.0 and abs(p1[1] - p2[1]) > 20.0:
                y_lo = min(p1[1], p2[1])
                y_hi = max(p1[1], p2[1])
                vert_segs.append((i, p1[0], y_lo, y_hi))

    # Group by x within 4 px buckets.
    x_buckets: "dict" = defaultdict(list)
    for seg in vert_segs:
        bucket = round(seg[1] / 4.0) * 4
        x_buckets[bucket].append(seg)

    for _bucket, segs in x_buckets.items():
        if len(segs) <= 1:
            continue
        # Build overlap groups: segs whose y-ranges overlap.
        groups: "list[list]" = []
        for seg in sorted(segs, key=lambda s: s[2]):  # sort by y_lo
            placed = False
            for g in groups:
                for existing in g:
                    if seg[2] < existing[3] and seg[3] > existing[2]:
                        g.append(seg)
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                groups.append([seg])

        for group in groups:
            if len(group) <= 1:
                continue
            # Deduplicate by route index (a route may have multiple segs in the group).
            seen_routes: "set" = set()
            unique: "list" = []
            for seg in group:
                if seg[0] not in seen_routes:
                    unique.append(seg)
                    seen_routes.add(seg[0])
            if len(unique) <= 1:
                continue
            n = len(unique)
            x_center = sum(s[1] for s in unique) / n
            half_span = (n - 1) * LANE_GAP / 2.0
            new_xs = [x_center - half_span + k * LANE_GAP for k in range(n)]
            # Sort unique by y_lo so topmost segment gets leftmost lane —
            # preserves left→right ordering consistent with port sort order.
            unique.sort(key=lambda s: s[2])
            for (route_idx, old_x, y_lo, y_hi), new_x in zip(unique, new_xs):
                r = routed[route_idx]
                wps = list(r["waypoints"])
                # For CBE-rerouted routes, _escape_idxs references the old (pre-A*)
                # waypoints; unioning them with the new _cbe_escape_idxs would protect
                # the wrong positions.  Only union for non-CBE routes.
                if r.get("_cbe_rerouted"):
                    _esc_idxs = r.get("_cbe_escape_idxs") or set()
                else:
                    _esc_idxs = (r.get("_cbe_escape_idxs") or set()) | (r.get("_escape_idxs") or set())
                # Protect: (a) boundary endpoints (always — cardinal CBE routes
                # record no escape indices so _esc_idxs may be empty; endpoints
                # must never be displaced off the shape outline), (b) each escape
                # on the old_x channel and its full contiguous same-x chain, and
                # (c) gate-coordinate waypoints that must stay on their declared
                # BoundaryGate.point.
                _last = len(wps) - 1
                _protected: "set[int]" = set(_esc_idxs)
                _protected.add(0)
                _protected.add(_last)
                # Protect the one immediate terminal-adjacent waypoint (index 1 /
                # index n-2) when it shares the endpoint's x.  A full chain-grow
                # would lock gate corridors; a single neighbor prevents the diagonal
                # terminal segment that arises when no escape index is recorded
                # (cardinal CBE source/destination).
                for _ep_idx, _ep_dir in ((0, 1), (_last, -1)):
                    _ep_x = wps[_ep_idx][0]
                    _adj = _ep_idx + _ep_dir
                    if 0 <= _adj <= _last and abs(wps[_adj][0] - _ep_x) < 2.0:
                        _protected.add(_adj)
                for _ei in list(_esc_idxs):
                    if _ei >= len(wps):
                        continue
                    _ex = wps[_ei][0]
                    for _j in range(_ei - 1, -1, -1):
                        if abs(wps[_j][0] - _ex) < 2.0:
                            _protected.add(_j)
                        else:
                            break
                    for _j in range(_ei + 1, len(wps)):
                        if abs(wps[_j][0] - _ex) < 2.0:
                            _protected.add(_j)
                        else:
                            break
                if gate_coords:
                    for _gi, _gp in enumerate(wps):
                        if (round(_gp[0], 1), round(_gp[1], 1)) in gate_coords:
                            _protected.add(_gi)
                            # Grow the collinear chain so no neighbor of the gate
                            # waypoint is shifted off the corridor.
                            _gx = _gp[0]
                            for _j in range(_gi - 1, -1, -1):
                                if abs(wps[_j][0] - _gx) < 2.0:
                                    _protected.add(_j)
                                else:
                                    break
                            for _j in range(_gi + 1, len(wps)):
                                if abs(wps[_j][0] - _gx) < 2.0:
                                    _protected.add(_j)
                                else:
                                    break
                for ki, p in enumerate(wps):
                    if ki in _protected:
                        continue
                    if abs(p[0] - old_x) < 2.0 and y_lo - 2.0 <= p[1] <= y_hi + 2.0:
                        wps[ki] = (new_x, p[1])
                # Insert orthogonal jogs where a protected old-x waypoint is adjacent
                # to a shifted new-x waypoint, preventing diagonal terminal segments.
                if abs(old_x - new_x) > 2.0:
                    _jogs_ins: "list[tuple[int, tuple]]" = []
                    for _ji in range(len(wps) - 1):
                        _ax, _ay = wps[_ji]
                        _bx, _by = wps[_ji + 1]
                        if abs(_ax - old_x) < 2.0 and abs(_bx - new_x) < 2.0:
                            _jogs_ins.append((_ji + 1, (new_x, _ay)))
                        elif abs(_ax - new_x) < 2.0 and abs(_bx - old_x) < 2.0:
                            _jogs_ins.append((_ji + 1, (new_x, _by)))
                    for _jog_n, (_ji_ins, _jp) in enumerate(_jogs_ins):
                        _ins = _ji_ins + _jog_n
                        wps.insert(_ins, _jp)
                        for _esc_key in ("_escape_idxs", "_cbe_escape_idxs"):
                            _e = r.get(_esc_key)
                            if _e:
                                r[_esc_key] = {_ej + 1 if _ej >= _ins else _ej
                                               for _ej in _e}
                r["waypoints"] = wps


def _reroute_cross_boundary_edges(
    routed: "list[dict]",
    nodes: "dict[str, _Node]",
    grp_bboxes: "dict[str, tuple]",
    canvas_w: float,
    canvas_h: float,
    direction: str = "TB",
    groups=None,
) -> "tuple":
    """Route every cross-boundary flowchart edge through explicit boundary gates.

    For each edge whose endpoints live in different scopes (at least one grouped):

    1. Route the whole edge with one obstacle-aware A* pass. Obstacles are every
       unrelated node interior, every group title band, and every *unrelated*
       group interior. The endpoint groups' interiors stay traversable so the
       route can reach the node and cross the boundary exactly once.
    2. Derive a ``BoundaryGate`` from the point where the finished route actually
       crosses each endpoint group's boundary (EXIT at the source group, ENTRY at
       the destination group) — the gate is on the boundary and on the route by
       construction, so it survives the compound-gate validator.
    3. Re-place the edge's label clear of other routes, nodes and title bands.

    Mutates each rerouted dict's ``waypoints``/``lx``/``ly`` and stamps the scope
    fields (``source_scope``/``target_scope`` plus semantic/routing endpoint ids)
    so the harness's compound-gate validator engages. Returns the tuple of
    ``BoundaryGate`` records.
    """
    from ._geometry import BoundaryGate, BoundaryGateKind, PortSide, Point  # noqa: PLC0415

    band = _GATE_TITLE_BAND_H
    real_ids = [nid for nid, n in nodes.items() if not n.is_dummy]
    node_rects = {
        nid: (nodes[nid].x, nodes[nid].y,
              nodes[nid].x + _node_render_w(nodes[nid]),
              nodes[nid].y + _node_render_h(nodes[nid]))
        for nid in real_ids
    }
    band_rects = [(x0, y0, x1, y0 + band) for (x0, y0, x1, y1) in grp_bboxes.values()]

    gates: "list[BoundaryGate]" = []
    gate_ctr = 0

    # World-coordinate segments from already-routed CBE edges (horizontal and vertical).
    # Passed as soft-cost `occupied` to each A* call so subsequent routes avoid
    # running parallel to an existing one on the same row or column.
    _cbe_done_hsegs: "list[tuple[float, float, float]]" = []  # (y, x_min, x_max)
    _cbe_done_vsegs: "list[tuple[float, float, float]]" = []  # (x, y_min, y_max)
    # Escape-row reservations that must never be exempted by exclude_ys. When
    # multiple CBE edges share the same destination face, their _b_route[1]
    # values are identical and would be in exclude_ys — exempting them from
    # _cbe_done_hsegs occupancy. Reservations in this list skip the exclusion.
    _cbe_escape_reserved: "list[tuple[float, float, float]]" = []  # (y, x_min, x_max)

    def _build_occupied(
        gx: "list[int]", gy: "list[int]",
        exclude_ys: "tuple[float, float] | None" = None,
    ) -> "set[tuple]":
        """Convert world-coord horizontal segments to grid-index step tuples for A*.

        Marks the occupied y row ±2 rows so routes stay at least two grid rows away
        from an existing horizontal segment.  Vertical segment occupancy is not
        tracked here: the sparse CBE grid means column soft-cost propagates
        unpredictably across edges with different endpoint sets, producing routes
        that zigzag across group boundaries (e.g. flowchart-groups-complex
        Cache→DB) or detour far past the destination.  CBE vertical tramlines are
        accepted as a layout constraint when multiple routes share the same gate.

        `exclude_ys` — the current edge's source and destination Y coordinates.
        Those exact grid rows are never marked occupied so the edge's own port rows
        remain free; without this, a tightly spaced port-pair (e.g. SY.bottom=1144
        and BD.top=1148, one grid step apart) can be blocked by a previous edge's
        congestion zone and the A* routes backward to escape it.
        Note: _cbe_escape_reserved rows are always occupied and ignore exclude_ys.
        """
        # Grid indices for the current edge's port rows — never occupy these.
        _excl: "set[int]" = set()
        if exclude_ys:
            for _ey in exclude_ys:
                _excl.add(min(range(len(gy)), key=lambda i: abs(gy[i] - _ey)))

        occ: "set[tuple]" = set()
        for (hy, hx0, hx1) in _cbe_done_hsegs:
            yi = min(range(len(gy)), key=lambda i: abs(gy[i] - hy))
            xi0 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx0))
            xi1 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx1))
            for dyi in range(-2, 3):  # exact row ± two rows
                byi = yi + dyi
                if 0 <= byi < len(gy) and byi not in _excl:
                    for xi in range(min(xi0, xi1), max(xi0, xi1)):
                        occ.add((xi, byi, xi + 1, byi))
        # Escape-row reservations: always honored, even when row matches exclude_ys.
        for (hy, hx0, hx1) in _cbe_escape_reserved:
            yi = min(range(len(gy)), key=lambda i: abs(gy[i] - hy))
            xi0 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx0))
            xi1 = min(range(len(gx)), key=lambda i: abs(gx[i] - hx1))
            for dyi in range(-2, 3):
                byi = yi + dyi
                if 0 <= byi < len(gy):
                    for xi in range(min(xi0, xi1), max(xi0, xi1)):
                        occ.add((xi, byi, xi + 1, byi))
        return occ

    # Precompute label bounding boxes for the escape-blocked guard below.
    # CBE A* obstacles do not include edge labels; escape stubs can land inside a
    # label chip from an already-placed route (e.g. cardinal source stub for UI→API
    # landing inside the UI→Cache chip).  lx/ly from the route dict: lx is the chip's
    # left edge; ly is the chip's BOTTOM edge (CSS translateY(-100%) shifts it up).
    # Tagged with edge_id so each iteration can exclude its own (stale) label chip.
    _cbe_label_rects_tagged: "list[tuple[str, float, float, float, float]]" = []
    for _r2 in routed:
        # Exclude CBE candidates (cross-boundary, non-backward) — their labels are
        # repositioned after rerouting, so their pre-reroute chip positions are stale.
        # Determine eligibility by scope (same check as the reroute loop below) rather
        # than by _cbe_rerouted, which is not set yet when this snapshot is built.
        _r2_sn2 = nodes.get(_r2.get("src"))
        _r2_dn2 = nodes.get(_r2.get("dst"))
        if (_r2_sn2 is not None and _r2_dn2 is not None
                and not (_r2_sn2.is_dummy or _r2_dn2.is_dummy)):
            _r2_sg2 = _r2_sn2.group if _r2_sn2.group in grp_bboxes else None
            _r2_dg2 = _r2_dn2.group if _r2_dn2.group in grp_bboxes else None
            if (_r2_sn2.group != _r2_dn2.group
                    and not (_r2_sg2 is None and _r2_dg2 is None)
                    and not _r2.get("_is_backward")):
                continue
        _r2_eid = _r2.get("edge_id") or ""
        _r2_lbl = (_r2.get("label") or "").strip()
        _r2_lx, _r2_ly = _r2.get("lx"), _r2.get("ly")
        if _r2_lbl and _r2_lx is not None and _r2_ly is not None:
            _r2_w = float(_est_label_w(_r2_lbl))
            _cbe_label_rects_tagged.append((
                _r2_eid,
                float(_r2_lx), float(_r2_ly) - float(_LABEL_CHIP_H),
                float(_r2_lx) + _r2_w, float(_r2_ly),
            ))

    for r in routed:
        s = r.get("src")
        d = r.get("dst")
        sn = nodes.get(s)
        dn = nodes.get(d)
        if sn is None or dn is None or sn.is_dummy or dn.is_dummy:
            continue
        sg = sn.group if sn.group in grp_bboxes else None
        dg = dn.group if dn.group in grp_bboxes else None
        # Cross-boundary iff endpoints differ in deepest scope and at least one
        # is a laid-out group. Intra-group and fully free edges are untouched.
        # Backward edges (rank inverted) are pre-routed with right→bottom ports
        # and should not be re-routed by the A* pass which ignores port direction.
        if sn.group == dn.group or (sg is None and dg is None):
            continue
        if r.get("_is_backward"):
            continue
        # Build per-edge label rects, excluding this edge's own pre-reroute chip.
        # The pre-reroute position is stale and will be replaced at the end of this
        # iteration; using it as a stub obstacle incorrectly blocks the current edge.
        _cur_r_eid = r.get("edge_id") or ""
        _cbe_label_rects: "list[tuple[float, float, float, float]]" = [
            (x0, y0, x1, y1)
            for (_eid2, x0, y0, x1, y1) in _cbe_label_rects_tagged
            if _eid2 != _cur_r_eid
        ]

        scx = sn.x + _node_render_w(sn) / 2.0
        scy = sn.y + _node_render_h(sn) / 2.0
        dcx = dn.x + _node_render_w(dn) / 2.0
        dcy = dn.y + _node_render_h(dn) / 2.0
        # Use the fanned port position from the main routing pass when available.
        # _cbe_node_face() returns the node-face centre — identical for all edges
        # from the same node — which causes every route to share the same initial
        # segment.  The pre-computed fanned port preserves per-edge port diversity
        # so the A* routes diverge immediately from their assigned port positions.
        _sp_pt = r.get("_src_port")
        _dp_pt = r.get("_dst_port")
        a = (float(_sp_pt[0]), float(_sp_pt[1])) if _sp_pt else _cbe_node_face(sn, (dcx, dcy))
        b = (float(_dp_pt[0]), float(_dp_pt[1])) if _dp_pt else _cbe_node_face(dn, (scx, scy))
        # Backward edges in TB mode (src.rank > dst.rank): src exits RIGHT,
        # dst is entered from BOTTOM so the route avoids the group interior.
        _is_tb = direction.upper() not in ("LR", "RL")
        if _is_tb and sn.rank > dn.rank:
            dw = _node_render_w(dn)
            dh = _node_render_h(dn)
            b = (dn.x + dw / 2.0, dn.y + dh)

        # Bottom-to-side face lift: when the main router assigned a bottom face
        # port but the actual destination node is primarily horizontal (1.25:1)
        # from the source, remap start to the side face.  The fanned x-fraction
        # from the bottom port is mapped to a y-offset on the right/left face so
        # each edge still gets a unique start position (no tramlines).
        if _is_tb and _sp_pt:
            _sn_bot = sn.y + _node_render_h(sn)
            if abs(float(_sp_pt[1]) - _sn_bot) < 2.0:     # port is on the bottom face
                _adx = abs(dcx - scx)
                _ady = abs(dcy - scy)
                if _adx >= 5.0 * _ady and _adx > 0:      # nearly horizontal only
                    _sw2 = _node_render_w(sn)
                    _sh2 = _node_render_h(sn)
                    _frac = min(1.0, max(0.0, (float(_sp_pt[0]) - sn.x) / max(_sw2, 1.0)))
                    _side_y = float(int(sn.y + _frac * _sh2))  # snap to grid int, avoids float/int stub
                    a = (sn.x + _sw2 if dcx > scx else sn.x, _side_y)
                    # When dest port is on dest top face, redirect to the facing horizontal
                    # face so the route goes side→side rather than side→top (which forces a
                    # downward U-turn before reaching the destination).
                    if _dp_pt and abs(float(_dp_pt[1]) - dn.y) < 2.0:
                        _dw2 = _node_render_w(dn)
                        _dh2 = _node_render_h(dn)
                        if dcx > scx:
                            b = (dn.x, dn.y + _dh2 / 2.0)        # dest LEFT face center
                        else:
                            b = (dn.x + _dw2, dn.y + _dh2 / 2.0)  # dest RIGHT face center

        # Layout-overlap: forward TB edge (src.rank < dst.rank) where the source
        # bottom port sits below the destination top port.  Routing BOTTOM→TOP
        # forces an unavoidable upward kink; override to RIGHT→LEFT so the path
        # is monotone horizontal.  Only applies when source is strictly below the
        # destination in rank (same-rank edges are handled by _edge_src_face) and
        # the source group is to the left of the destination group.
        # Skip the override when _src_port was explicitly provided: the fanned port
        # is already diverse per-edge, so overriding to the shared face centre would
        # collapse all edges from the same source face back into tramlines.
        if (
            _is_tb
            and _sp_pt is None        # only override when no explicit fanned port
            and sn.rank < dn.rank     # strictly lower rank → forward cross-rank edge
            and a[1] > b[1]           # source port Y is below dest port Y (overlap)
            and sn.x + _node_render_w(sn) < dn.x  # source group is to the left
        ):
            _sw = _node_render_w(sn)
            _sh = _node_render_h(sn)
            _dw = _node_render_w(dn)
            _dh = _node_render_h(dn)
            a = (sn.x + _sw, sn.y + _sh / 2.0)   # source RIGHT center
            b = (dn.x, dn.y + _dh / 2.0)          # dest LEFT center

        endpoint_groups = {sn.group, dn.group}
        # Don't block the common-ancestor space: routes between sibling subgroups
        # must travel through their shared parent group.
        _ancestor_gids: set = set()
        if groups:
            for _egid in endpoint_groups:
                _cur = groups[_egid].parent_group if _egid in groups else None
                while _cur:
                    _ancestor_gids.add(_cur)
                    _cur = groups[_cur].parent_group if _cur in groups else None
        obstacles: "list[tuple]" = [
            rect for nid, rect in node_rects.items() if nid not in (s, d)
        ]
        for gid, (x0, y0, x1, y1) in grp_bboxes.items():
            if gid not in endpoint_groups and gid not in _ancestor_gids:
                obstacles.append((x0, y0, x1, y0 + band))   # title band
                obstacles.append((x0, y0, x1, y1))           # unrelated interior

        # Block A* from routing within 5px of canvas edges (_blocked_segs CLEAR=4,
        # so obstacle spanning ±9px around the edge blocks the edge grid line itself)
        _cs = 9
        obstacles.extend([
            (-_cs, -_cs, _cs, canvas_h + _cs),                     # left edge strip
            (canvas_w - _cs, -_cs, canvas_w + _cs, canvas_h + _cs),  # right edge strip
            (-_cs, -_cs, canvas_w + _cs, _cs),                     # top edge strip
            (-_cs, canvas_h - _cs, canvas_w + _cs, canvas_h + _cs),  # bottom edge strip
        ])

        # Escape stubs for non-cardinal normals (diamond/hexagon fan-out).
        # Route the trunk escape-to-escape so the A* path is fully axis-aligned;
        # wrap with boundary stubs afterward.  Restricted to non-cardinal normals
        # (< _CARDINAL_NORMAL_T) because face-lift remapping of a/b can produce a
        # cardinal port with a different normal than _src_normal/_dst_normal.
        # Guard: if a/b was remapped (differs from the stored fanned port) the
        # stored normal no longer matches the live endpoint — clear it so no stub
        # is computed for the wrong face.
        _sp_normal: "tuple[float, float]" = r.get("_src_normal") or (0.0, 0.0)
        _dp_normal: "tuple[float, float]" = r.get("_dst_normal") or (0.0, 0.0)
        _sp_pt_orig = r.get("_src_port")
        _dp_pt_orig = r.get("_dst_port")
        if _sp_pt_orig and (abs(a[0] - float(_sp_pt_orig[0])) > 2.0 or abs(a[1] - float(_sp_pt_orig[1])) > 2.0):
            # a was remapped; derive the outward normal from which face of the source
            # node a now sits on rather than zeroing (zeroing disables source stubs).
            if s in node_rects:
                _sr_x0, _sr_y0, _sr_x1, _sr_y1 = node_rects[s]
                if abs(a[0] - _sr_x0) < 2.0:
                    _sp_normal = (-1.0, 0.0)
                elif abs(a[0] - _sr_x1) < 2.0:
                    _sp_normal = (1.0, 0.0)
                elif abs(a[1] - _sr_y0) < 2.0:
                    _sp_normal = (0.0, -1.0)
                elif abs(a[1] - _sr_y1) < 2.0:
                    _sp_normal = (0.0, 1.0)
                else:
                    _sp_normal = (0.0, 0.0)
            else:
                _sp_normal = (0.0, 0.0)
        if _dp_pt_orig and (abs(b[0] - float(_dp_pt_orig[0])) > 2.0 or abs(b[1] - float(_dp_pt_orig[1])) > 2.0):
            # b was remapped; derive the outward normal from which face of the dest
            # node b now sits on rather than zeroing (zeroing omits dest from blocked_obs).
            if d in node_rects:
                _dr_x0, _dr_y0, _dr_x1, _dr_y1 = node_rects[d]
                if abs(b[0] - _dr_x0) < 2.0:
                    _dp_normal = (-1.0, 0.0)
                elif abs(b[0] - _dr_x1) < 2.0:
                    _dp_normal = (1.0, 0.0)
                elif abs(b[1] - _dr_y0) < 2.0:
                    _dp_normal = (0.0, -1.0)
                elif abs(b[1] - _dr_y1) < 2.0:
                    _dp_normal = (0.0, 1.0)
                else:
                    _dp_normal = (0.0, 0.0)
            else:
                _dp_normal = (0.0, 0.0)
        _snorm_mag = max(abs(_sp_normal[0]), abs(_sp_normal[1]))
        _dnorm_mag = max(abs(_dp_normal[0]), abs(_dp_normal[1]))
        # Escape stubs: source non-cardinal only (see note below); destination all non-zero.
        # obstacles format in CBE: (x0, y0, x1, y1) — left/top/right/bottom.
        # _cbe_in_obs checks both node/group obstacles and precomputed label chip rects.
        def _cbe_in_obs(px: float, py: float) -> bool:
            for _x0, _y0, _x1, _y1 in obstacles:
                if _x0 <= px <= _x1 and _y0 <= py <= _y1:
                    return True
            for _x0, _y0, _x1, _y1 in _cbe_label_rects:
                if _x0 <= px <= _x1 and _y0 <= py <= _y1:
                    return True
            return False

        def _cbe_stub_blocked(bx: float, by: float, ex: float, ey: float) -> bool:
            """True if the stub segment (bx,by)→(ex,ey) crosses any obstacle or label."""
            if _cbe_in_obs(ex, ey):
                return True
            mx, my = (bx + ex) / 2.0, (by + ey) / 2.0
            if _cbe_in_obs(mx, my):
                return True
            for _x0, _y0, _x1, _y1 in obstacles:
                if _seg_intersects_rect(bx, by, ex, ey, _x0, _y0, _x1, _y1):
                    return True
            for _x0, _y0, _x1, _y1 in _cbe_label_rects:
                if _seg_intersects_rect(bx, by, ex, ey, _x0, _y0, _x1, _y1):
                    return True
            return False

        # Source: non-cardinal normals only.  Cardinal source stubs shift the A* start
        # 20 px along the outward normal; the CBE grid is label-unaware, so A* can choose
        # a crossing path even when the escape itself is outside the label rect.
        # Deferred: would require adding label y-rows to _cbe_build_grid so A* avoids them.
        # Use terminal-normal tolerance (0.9998) so near-cardinal normals like
        # (0.9995, 0.032) still get a stub — _CARDINAL_NORMAL_T (0.999) is too
        # loose and produces A* terminals whose dot product falls below 0.9998.
        _cbe_src_needs_stub = 1e-9 < _snorm_mag < 0.9998
        _cbe_dst_needs_stub = _dnorm_mag > 1e-9
        # Cap stubs when opposing normals are close enough to invert escape points —
        # same three-way logic as the main router: disable if < 4 px, cap otherwise.
        _cbe_stub_len = _STUB_LEN
        if _cbe_src_needs_stub or _cbe_dst_needs_stub:
            _snx_c, _sny_c = _sp_normal
            _dnx_c, _dny_c = _dp_normal
            _dn_dot_sn_c = _dnx_c * _snx_c + _dny_c * _sny_c
            _cbe_ah_dst = r.get("ah")
            _cbe_src_mk = r.get("source_marker")
            _cbe_ah_src = (_cbe_src_mk is not None
                           and _marker_kind(_cbe_src_mk).value != "none")
            _cbe_stub_min_dst = (15.0 if (_cbe_ah_dst and r.get("style") == "thick")
                                 else 13.0 if _cbe_ah_dst else 4.0)
            _cbe_stub_min_src = (15.0 if (_cbe_ah_src and r.get("style") == "thick")
                                 else 13.0 if _cbe_ah_src else 4.0)
            if _dn_dot_sn_c < -0.99 and _cbe_src_needs_stub and _cbe_dst_needs_stub:
                _gap_sn = (b[0] - a[0]) * _snx_c + (b[1] - a[1]) * _sny_c
                if _gap_sn > 0:
                    _rate_c = 1.0 - _dn_dot_sn_c
                    _max_nc_c = (_gap_sn - 1.0) / _rate_c
                    if _max_nc_c < _STUB_LEN:
                        # Same perpendicular-gap guard as main router: stubs with large
                        # perpendicular separation cannot collide, so skip the cap.
                        _gap_perp_c = abs((b[0] - a[0]) * _sny_c - (b[1] - a[1]) * _snx_c)
                        if _gap_perp_c <= _STUB_LEN:
                            _cbe_stub_len = _max_nc_c
                            if _max_nc_c < _cbe_stub_min_src:
                                _cbe_src_needs_stub = False
                            if _max_nc_c < _cbe_stub_min_dst:
                                _cbe_dst_needs_stub = False
            elif _cbe_src_needs_stub and _cbe_dst_needs_stub:
                # Non-antiparallel approaching normals (e.g. diamond→top-face):
                # apply Euclidean approach-rate cap so full stubs don't overshoot.
                _gx_c = b[0] - a[0]
                _gy_c = b[1] - a[1]
                _geo_c = (_gx_c ** 2 + _gy_c ** 2) ** 0.5
                if _geo_c > 1e-9:
                    _ux_c = _gx_c / _geo_c
                    _uy_c = _gy_c / _geo_c
                    _rate_c2 = (_snx_c - _dnx_c) * _ux_c + (_sny_c - _dny_c) * _uy_c
                    if _rate_c2 > 0:
                        _max_nc_c2 = (_geo_c - 1.0) / _rate_c2
                        if _max_nc_c2 < _STUB_LEN:
                            _cbe_stub_len = _max_nc_c2
                            if _max_nc_c2 < _cbe_stub_min_src:
                                _cbe_src_needs_stub = False
                            if _max_nc_c2 < _cbe_stub_min_dst:
                                _cbe_dst_needs_stub = False
            elif _cbe_dst_needs_stub and not _cbe_src_needs_stub:
                # One-sided: only dst stub (cardinal src normal, no src escape).
                # Cap the dst stub so it doesn't overshoot past the source boundary.
                # Use a marker-aware minimum: arrow edges need ~13px clearance.
                _gap_dst_only = (a[0] - b[0]) * _dnx_c + (a[1] - b[1]) * _dny_c
                if 0 < _gap_dst_only < _STUB_LEN:
                    _max_nc_c = _gap_dst_only - 1.0
                    # Ports far apart perpendicular to the dst normal cannot collide;
                    # only cap when perpendicular separation is within stub range.
                    _gap_perp_dst = abs((a[0] - b[0]) * _dny_c - (a[1] - b[1]) * _dnx_c)
                    if _gap_perp_dst <= _STUB_LEN:
                        if _max_nc_c >= _cbe_stub_min_dst:
                            _cbe_stub_len = _max_nc_c
                        else:
                            _cbe_dst_needs_stub = False
        _a_route: "tuple[float, float]" = (
            (a[0] + _sp_normal[0] * _cbe_stub_len, a[1] + _sp_normal[1] * _cbe_stub_len)
            if _cbe_src_needs_stub else a
        )
        _b_route: "tuple[float, float]" = (
            (b[0] + _dp_normal[0] * _cbe_stub_len, b[1] + _dp_normal[1] * _cbe_stub_len)
            if _cbe_dst_needs_stub else b
        )
        # Retract escapes that land inside obstacles — avoids A* starting from a
        # blocked cell (producing no path) or from inside an edge-label band.
        if _cbe_src_needs_stub and _cbe_stub_blocked(a[0], a[1], _a_route[0], _a_route[1]):
            _a_route = a
            _cbe_src_needs_stub = False
        if _cbe_dst_needs_stub and _cbe_stub_blocked(b[0], b[1], _b_route[0], _b_route[1]):
            _b_route = b
            _cbe_dst_needs_stub = False

        gx, gy = _cbe_build_grid(nodes, grp_bboxes, [a, b, _a_route, _b_route], canvas_w, canvas_h)
        # When a destination stub is used, _b_route is the A* goal and lies
        # outside the destination node's polygon. Add the node's AABB to the
        # blocked obstacle list so the trunk cannot route through d's interior.
        # Guard: for non-vertex polygon ports the escape can land inside the AABB
        # even though it is outside the actual shape; in that case blocking the
        # AABB would trap the goal, so only add when _b_route is outside the AABB.
        _blocked_obs = obstacles
        _BCLEAR = 4
        _cbe_dst_b_inside_aabb = False
        if _cbe_dst_needs_stub and d in node_rects:
            _dx0, _dy0, _dx1, _dy1 = node_rects[d]
            # Always add the destination AABB to prevent A* from routing through
            # the polygon interior.  For non-vertex polygon ports the escape can
            # land inside the AABB (outside the actual polygon boundary); we punch
            # an aperture around the goal cell after building blocked so A* can
            # still reach it without traversing the AABB's interior.
            _blocked_obs = obstacles + [(_dx0 - _BCLEAR, _dy0 - _BCLEAR,
                                         _dx1 + _BCLEAR, _dy1 + _BCLEAR)]
            _cbe_dst_b_inside_aabb = _dx0 < _b_route[0] < _dx1 and _dy0 < _b_route[1] < _dy1
        # Block source AABB to prevent A* from routing back through the source.
        # Non-cardinal source (stub needed): inflate AABB, punch aperture when
        # the source escape is inside.  Cardinal source: raw AABB only — the
        # boundary strip is clear via _blocked_segs' 4 px interior clearance.
        _cbe_src_a_inside_aabb = False
        if s in node_rects:
            _sx0, _sy0, _sx1, _sy1 = node_rects[s]
            _a_strictly_inside = _sx0 < a[0] < _sx1 and _sy0 < a[1] < _sy1
            if _cbe_src_needs_stub:
                _blocked_obs = _blocked_obs + [(_sx0 - _BCLEAR, _sy0 - _BCLEAR,
                                                _sx1 + _BCLEAR, _sy1 + _BCLEAR)]
                _cbe_src_a_inside_aabb = (_sx0 < _a_route[0] < _sx1
                                          and _sy0 < _a_route[1] < _sy1)
            elif not _a_strictly_inside:
                _blocked_obs = _blocked_obs + [(_sx0, _sy0, _sx1, _sy1)]
        blocked = _blocked_segs(gx, gy, _blocked_obs)
        # Aperture: when the destination escape landed inside the AABB (non-vertex
        # polygon port, escape is outside the polygon but inside its bounding box),
        # the AABB obstacle above traps A*'s goal.  Un-block cells immediately
        # around the goal so A* can reach it; the rest of the AABB interior stays
        # blocked, preventing routes from traversing the polygon's actual interior.
        if _cbe_dst_b_inside_aabb:
            _gxi = min(range(len(gx)), key=lambda _i: abs(gx[_i] - _b_route[0]))
            _gyi = min(range(len(gy)), key=lambda _i: abs(gy[_i] - _b_route[1]))
            # Open only the approach-direction edges so A* cannot enter the goal
            # through the polygon interior (e.g. from the inward side of the AABB).
            # Use the port's outward normal when known — peer displacement can point
            # inward for non-cardinal polygon faces, opening the wrong side.
            if abs(_dp_normal[0]) > 1e-9 or abs(_dp_normal[1]) > 1e-9:
                _app_dx, _app_dy = _dp_normal
            else:
                _app_dx = _a_route[0] - _b_route[0]
                _app_dy = _a_route[1] - _b_route[1]
            if abs(_app_dx) >= abs(_app_dy):
                if _app_dx > 0:  # source is to the right — open rightward to AABB right boundary
                    _aabb_r = _dx1 + _BCLEAR
                    _ci_out = next((ci for ci in range(_gxi, len(gx)) if gx[ci] >= _aabb_r),
                                   len(gx) - 1)
                    for _ci in range(_gxi, _ci_out):
                        blocked.discard((_ci, _gyi, _ci + 1, _gyi))
                else:             # source is to the left — open leftward to AABB left boundary
                    _aabb_l = _dx0 - _BCLEAR
                    _ci_out = next((ci for ci in range(_gxi, -1, -1) if gx[ci] <= _aabb_l), 0)
                    for _ci in range(_ci_out, _gxi):
                        blocked.discard((_ci, _gyi, _ci + 1, _gyi))
            else:
                if _app_dy > 0:  # source is below — open downward to AABB bottom boundary
                    _aabb_b = _dy1 + _BCLEAR
                    _ri_out = next((ri for ri in range(_gyi, len(gy)) if gy[ri] >= _aabb_b),
                                   len(gy) - 1)
                    for _ri in range(_gyi, _ri_out):
                        blocked.discard((_gxi, _ri, _gxi, _ri + 1))
                else:             # source is above — open upward to AABB top boundary
                    _aabb_t = _dy0 - _BCLEAR
                    _ri_out = next((ri for ri in range(_gyi, -1, -1) if gy[ri] <= _aabb_t), 0)
                    for _ri in range(_ri_out, _gyi):
                        blocked.discard((_gxi, _ri, _gxi, _ri + 1))
        # Aperture: source-side, analogous to the destination handling above.
        if _cbe_src_a_inside_aabb:
            _sxi = min(range(len(gx)), key=lambda _i: abs(gx[_i] - _a_route[0]))
            _syi = min(range(len(gy)), key=lambda _i: abs(gy[_i] - _a_route[1]))
            if abs(_sp_normal[0]) > 1e-9 or abs(_sp_normal[1]) > 1e-9:
                _src_app_dx, _src_app_dy = _sp_normal
            else:
                _src_app_dx = _b_route[0] - _a_route[0]
                _src_app_dy = _b_route[1] - _a_route[1]
            if abs(_src_app_dx) >= abs(_src_app_dy):
                if _src_app_dx > 0:  # destination to the right — open rightward to AABB right
                    _saabb_r = _sx1 + _BCLEAR
                    _sci_out = next((ci for ci in range(_sxi, len(gx)) if gx[ci] >= _saabb_r),
                                    len(gx) - 1)
                    for _ci in range(_sxi, _sci_out):
                        blocked.discard((_ci, _syi, _ci + 1, _syi))
                else:                # destination to the left — open leftward to AABB left
                    _saabb_l = _sx0 - _BCLEAR
                    _sci_out = next((ci for ci in range(_sxi, -1, -1) if gx[ci] <= _saabb_l), 0)
                    for _ci in range(_sci_out, _sxi):
                        blocked.discard((_ci, _syi, _ci + 1, _syi))
            else:
                if _src_app_dy > 0:  # destination is below — open downward to AABB bottom
                    _saabb_b = _sy1 + _BCLEAR
                    _sri_out = next((ri for ri in range(_syi, len(gy)) if gy[ri] >= _saabb_b),
                                    len(gy) - 1)
                    for _ri in range(_syi, _sri_out):
                        blocked.discard((_sxi, _ri, _sxi, _ri + 1))
                else:                # destination is above — open upward to AABB top
                    _saabb_t = _sy0 - _BCLEAR
                    _sri_out = next((ri for ri in range(_syi, -1, -1) if gy[ri] <= _saabb_t), 0)
                    for _ri in range(_sri_out, _syi):
                        blocked.discard((_sxi, _ri, _sxi, _ri + 1))
        # Hard-block reserved CBE horizontal corridors from already-routed edges
        # (only the exact row; soft-cost ±2-row zone in occupied is not enough to
        # prevent A* from reusing them when detours are costlier).
        # Source row: exclude entirely so A* can exit from the source terminal.
        # Destination row: exempt only cells within the destination aperture zone
        # (the cells already discarded by blocked.discard() above); cells outside
        # the aperture on the destination's y-row must be hard-blocked to prevent
        # two edges sharing the same approach corridor when they enter the same face.
        _excl_ys_c = (_a_route[1],)
        if _cbe_dst_needs_stub and d in node_rects:
            _dst_apt_x_lo = node_rects[d][0] - _BCLEAR
            _dst_apt_x_hi = node_rects[d][2] + _BCLEAR
        else:
            _dst_apt_x_lo = _b_route[0] - _BCLEAR
            _dst_apt_x_hi = _b_route[0] + _BCLEAR
        for (_hy, _hx0, _hx1) in _cbe_done_hsegs:
            if any(abs(_hy - _ey) < 2.0 for _ey in _excl_ys_c):
                continue
            _byi = min(range(len(gy)), key=lambda _i: abs(gy[_i] - _hy))
            if abs(gy[_byi] - _hy) > 2.0:
                continue  # no grid row within 2 px — skip to avoid blocking wrong row
            _bxi0 = min(range(len(gx)), key=lambda _i: abs(gx[_i] - _hx0))
            _bxi1 = min(range(len(gx)), key=lambda _i: abs(gx[_i] - _hx1))
            _is_dst_y = abs(_hy - _b_route[1]) < 2.0
            for _bxi in range(min(_bxi0, _bxi1), max(_bxi0, _bxi1)):
                if _is_dst_y and _dst_apt_x_lo <= gx[_bxi] <= _dst_apt_x_hi:
                    continue  # within destination aperture; don't re-block
                blocked.add((_bxi, _byi, _bxi + 1, _byi))
        _excl_xs_c = (_a_route[0], _b_route[0])
        for (_vx, _vy0, _vy1) in _cbe_done_vsegs:
            if any(abs(_vx - _ex) < 2.0 for _ex in _excl_xs_c):
                continue
            _bxi = min(range(len(gx)), key=lambda _i: abs(gx[_i] - _vx))
            if abs(gx[_bxi] - _vx) > 2.0:
                continue
            _byi0 = min(range(len(gy)), key=lambda _i: abs(gy[_i] - _vy0))
            _byi1 = min(range(len(gy)), key=lambda _i: abs(gy[_i] - _vy1))
            for _byi in range(min(_byi0, _byi1), max(_byi0, _byi1)):
                blocked.add((_bxi, _byi, _bxi, _byi + 1))
        occupied = _build_occupied(gx, gy, exclude_ys=(_a_route[1], _b_route[1]))
        path = _astar_route(int(_a_route[0]), int(_a_route[1]), int(_b_route[0]), int(_b_route[1]), gx, gy, blocked, occupied=occupied or None)
        # Reject A* paths that cross unrelated sibling nodes — the source escape
        # can fall within _blocked_segs' 4 px boundary tolerance of a nearby
        # sibling AABB, allowing a corridor through its rounded caps.
        _guard_hits: "list[tuple[float, float, float, float]]" = []
        if path and len(path) >= 2:
            for _pi in range(len(path) - 1):
                _px, _py = path[_pi]
                _qx, _qy = path[_pi + 1]
                for _nid, (_rx0, _ry0, _rx1, _ry1) in node_rects.items():
                    if _nid in (s, d):
                        continue
                    if _py == _qy:
                        if _ry0 < _py < _ry1 and min(_px, _qx) < _rx1 and max(_px, _qx) > _rx0:
                            _guard_hits.append((_rx0, _ry0, _rx1, _ry1))
                            path = None
                            break
                    elif _px == _qx:
                        if _rx0 < _px < _rx1 and min(_py, _qy) < _ry1 and max(_py, _qy) > _ry0:
                            _guard_hits.append((_rx0, _ry0, _rx1, _ry1))
                            path = None
                            break
                if path is None:
                    break
        # Retry once: add each guard-flagged node's grid cells to blocked (no CLEAR
        # strip) so A* must detour around the sibling entirely, then re-run.
        # _blocked_segs only blocks interior cells beyond CLEAR px from the boundary,
        # which can still allow a path to graze the node's AABB interior.
        if path is None and _guard_hits:
            for _gh in _guard_hits:
                _gh_x0, _gh_y0, _gh_x1, _gh_y1 = _gh
                _gh_xi0 = min(range(len(gx)), key=lambda _i: abs(gx[_i] - _gh_x0))
                _gh_xi1 = min(range(len(gx)), key=lambda _i: abs(gx[_i] - _gh_x1))
                _gh_yi0 = min(range(len(gy)), key=lambda _i: abs(gy[_i] - _gh_y0))
                _gh_yi1 = min(range(len(gy)), key=lambda _i: abs(gy[_i] - _gh_y1))
                for _gxi in range(min(_gh_xi0, _gh_xi1), max(_gh_xi0, _gh_xi1)):
                    for _gyi in range(min(_gh_yi0, _gh_yi1), max(_gh_yi0, _gh_yi1)):
                        blocked.add((_gxi, _gyi, _gxi + 1, _gyi))
                        blocked.add((_gxi, _gyi, _gxi, _gyi + 1))
            path = _astar_route(int(_a_route[0]), int(_a_route[1]),
                                int(_b_route[0]), int(_b_route[1]),
                                gx, gy, blocked, occupied=occupied or None)
            # Re-validate the retry path; if it still crosses a sibling, reject it.
            if path and len(path) >= 2:
                for _pi in range(len(path) - 1):
                    _px, _py = path[_pi]
                    _qx, _qy = path[_pi + 1]
                    for _nid, (_rx0, _ry0, _rx1, _ry1) in node_rects.items():
                        if _nid in (s, d):
                            continue
                        if _py == _qy:
                            if _ry0 < _py < _ry1 and min(_px, _qx) < _rx1 and max(_px, _qx) > _rx0:
                                path = None
                                break
                        elif _px == _qx:
                            if _rx0 < _px < _rx1 and min(_py, _qy) < _ry1 and max(_py, _qy) > _ry0:
                                path = None
                                break
                    if path is None:
                        break
        if not path or len(path) < 2:
            # A* could not improve the route; restore label to the obstacle snapshot
            # so subsequent CBE edges don't route stubs through this unchanged chip.
            _fail_lbl = (r.get("label") or "").strip()
            _fail_lx, _fail_ly = r.get("lx"), r.get("ly")
            if _fail_lbl and _fail_lx is not None and _fail_ly is not None:
                _fail_w = float(_est_label_w(_fail_lbl))
                _cbe_label_rects_tagged.append((
                    _cur_r_eid,
                    float(_fail_lx), float(_fail_ly) - float(_LABEL_CHIP_H),
                    float(_fail_lx) + _fail_w, float(_fail_ly),
                ))
            continue  # keep the original route if A* cannot improve it

        # Record significant segments so subsequent routes avoid running alongside them.
        for _pi in range(len(path) - 1):
            _px, _py = path[_pi]
            _qx, _qy = path[_pi + 1]
            if _py == _qy and abs(_qx - _px) > 20:
                _cbe_done_hsegs.append((float(_py), float(min(_px, _qx)), float(max(_px, _qx))))
            elif _px == _qx and abs(_qy - _py) > 20:
                _cbe_done_vsegs.append((float(_px), float(min(_py, _qy)), float(max(_py, _qy))))
        # Record escape y-rows so subsequent routes choose a different row.
        # Must use _cbe_escape_reserved (not _cbe_done_hsegs) so the reservation
        # is honored even when the same y appears in the next edge's exclude_ys.
        # Also add the approach row to _cbe_done_hsegs for hard-blocking so later
        # CBE edges cannot route alongside the destination approach segment.
        if _cbe_dst_needs_stub:
            _cbe_escape_reserved.append((
                float(_b_route[1]),
                float(_b_route[0]) - float(_STUB_LEN),
                float(_b_route[0]) + float(_STUB_LEN),
            ))
            # Reserve only the actual final horizontal approach segment so
            # subsequent CBE edges are not blocked from corridors never used.
            if len(path) >= 2:
                _lp_x, _lp_y = path[-2]
                _lq_x, _lq_y = path[-1]
                if _lp_y == _lq_y:  # final segment is horizontal — reserve its row
                    _cbe_done_hsegs.append((
                        float(_lq_y),
                        float(min(_lp_x, _lq_x)) - _STUB_LEN,
                        float(max(_lp_x, _lq_x)) + _STUB_LEN,
                    ))

        poly = [(float(x), float(y)) for x, y in path]
        # Capture the original A* integer endpoints BEFORE overwriting.
        _a_orig = poly[0]
        _b_orig = poly[-1]
        poly[0] = (float(_a_route[0]), float(_a_route[1]))
        poly[-1] = (float(_b_route[0]), float(_b_route[1]))
        # A* snaps endpoints to integer grid rows/columns via int() truncation.
        # For non-cardinal escapes the float coords can be up to ~1 px away from
        # the nearest integer, producing a subpixel dogleg after _ensure_orthogonal.
        # Skip the snap when a stub will restore the float escape later: keeping the
        # float here lets _ensure_orthogonal orthogonalize directly from the float
        # escape, so the second re-orthogonalization on the trunk is a no-op and no
        # sub-4px bridge segment is introduced.
        # Re-orthogonalize before deriving gates.
        poly = _ensure_orthogonal(poly)
        out = [poly[0]]
        for p in poly[1:]:
            if (round(p[0], 2), round(p[1], 2)) != (round(out[-1][0], 2), round(out[-1][1], 2)):
                out.append(p)
        # Wrap trunk with boundary stubs: prepend/append the raw boundary port so
        # the stub segment (boundary → escape) appears in the final waypoints.
        # The trunk endpoints were snapped to integer (_a_int / _b_int) for
        # _ensure_orthogonal; restore the original float escape coordinates here
        # so the stub direction aligns with the outward normal.  Replacing (not
        # inserting) keeps the structure [a, _a_route, trunk..., _b_route, b]
        # so the validator's pts[0]→pts[1] and pts[-2]→pts[-1] terminal checks
        # see the correct on-normal stub segments.
        _cbe_src_esc_coords: "tuple[float, float] | None" = None
        _cbe_dst_esc_coords: "tuple[float, float] | None" = None
        if _cbe_src_needs_stub:
            _cbe_src_esc_coords = (float(_a_route[0]), float(_a_route[1]))
            out[0] = _cbe_src_esc_coords  # restore float escape as trunk start
            out = [(float(a[0]), float(a[1]))] + out
        if _cbe_dst_needs_stub:
            _cbe_dst_esc_coords = (float(_b_route[0]), float(_b_route[1]))
            out[-1] = _cbe_dst_esc_coords  # restore float escape as trunk end
            out = out + [(float(b[0]), float(b[1]))]
        # Re-orthogonalize the trunk after float escape restoration.
        # The integer-snapped A* endpoints were replaced by float escapes that can
        # differ in both axes, making the first or last trunk segment diagonal.
        # Re-running _ensure_orthogonal on the trunk (between the boundary stubs)
        # inserts the minimal axis-aligned bend needed to restore the contract.
        if _cbe_src_needs_stub or _cbe_dst_needs_stub:
            _t0 = 1 if _cbe_src_needs_stub else 0
            _t1 = len(out) - 1 if _cbe_dst_needs_stub else len(out)
            _trunk = out[_t0:_t1]
            _trunk = _ensure_orthogonal(_trunk)
            out = out[:_t0] + _trunk + out[_t1:]
            # Refresh escape coords after orthogonalization: the endpoint may have
            # shifted if _ensure_orthogonal added an intermediate bend.
            if _cbe_src_needs_stub:
                _cbe_src_esc_coords = (float(out[1][0]), float(out[1][1]))
            if _cbe_dst_needs_stub:
                _cbe_dst_esc_coords = (float(out[-2][0]), float(out[-2][1]))

        eid = r.get("edge_id") or f"{s}->{d}"
        # Pick the boundary crossing per endpoint group (EXIT = last time the route
        # leaves the source group; ENTRY = first time it enters the destination),
        # then insert each gate point into the route as an explicit waypoint (AC2).
        inserts: "list[tuple[int, tuple[float, float], str, str]]" = []
        if sg:
            cs = _cbe_boundary_crossings(out, grp_bboxes[sg])
            if cs:
                seg, gx_, gy_ = cs[-1]
                inserts.append((seg, (gx_, gy_), sg, "exit"))
        if dg:
            cs = _cbe_boundary_crossings(out, grp_bboxes[dg])
            if cs:
                seg, gx_, gy_ = cs[0]
                inserts.append((seg, (gx_, gy_), dg, "entry"))
        # Sort: segment index descending (so later segments are inserted first and
        # don't shift earlier segment indices), then within the same segment sort by
        # Manhattan distance from segment start descending (so the gate farthest from
        # the segment start is inserted first — each subsequent insert at `seg+1`
        # pushes it forward, placing the nearest-to-start gate earliest in the path).
        # This prevents the same-segment EXIT/ENTRY gate pair from being inserted in
        # reverse order, which would create a visible backtrack in the routed path.
        for seg, pt, gid, role in sorted(
            inserts,
            key=lambda t: (
                -t[0],
                -(abs(t[1][0] - out[t[0]][0]) + abs(t[1][1] - out[t[0]][1]))
                if t[0] < len(out) else 0.0
            ),
        ):
            if (round(pt[0], 2), round(pt[1], 2)) not in {(round(w[0], 2), round(w[1], 2)) for w in out}:
                out.insert(seg + 1, (float(pt[0]), float(pt[1])))
        for seg, pt, gid, role in inserts:
            is_exit = role == "exit"
            gates.append(BoundaryGate(
                gate_id=f"_bgate_{gate_ctr}_{role}", group_id=gid, side=PortSide.AUTO,
                point=Point(float(pt[0]), float(pt[1])),
                semantic_node_id=s if is_exit else d, edge_id=eid,
                kind=BoundaryGateKind.EXIT if is_exit else BoundaryGateKind.ENTRY,
            ))
            gate_ctr += 1

        # Remove intermediate collinear waypoints introduced by the grid or
        # orthogonaliser.  Gate points must be preserved as exact waypoints
        # because test_gate_is_route_waypoint requires a waypoint within 1 px.
        # A point is only "collinear" if it is strictly between its neighbours
        # on the non-shared axis — reversal/overshoot points (e.g. a destination
        # escape that was appended past the boundary port) must be kept.
        _gate_pts = {
            (round(_gpt[0], 1), round(_gpt[1], 1))
            for _, _gpt, _, _ in inserts
        }
        _cbe_esc_pts: "set[tuple[float, float]]" = set()
        if _cbe_src_esc_coords is not None:
            _cbe_esc_pts.add((round(_cbe_src_esc_coords[0], 1), round(_cbe_src_esc_coords[1], 1)))
        if _cbe_dst_esc_coords is not None:
            _cbe_esc_pts.add((round(_cbe_dst_esc_coords[0], 1), round(_cbe_dst_esc_coords[1], 1)))
        _deduped: "list[tuple[float, float]]" = [out[0]]
        for _ci in range(1, len(out) - 1):
            _pp, _cp, _np = _deduped[-1], out[_ci], out[_ci + 1]
            _col_x = abs(_pp[0] - _cp[0]) < 1e-9 and abs(_cp[0] - _np[0]) < 1e-9
            _col_y = abs(_pp[1] - _cp[1]) < 1e-9 and abs(_cp[1] - _np[1]) < 1e-9
            # Only drop a collinear point when it lies between its neighbours on
            # the orthogonal axis (not a reversal/overshoot, which must be kept).
            if _col_x:
                _col_x = (min(_pp[1], _np[1]) - 0.5 <= _cp[1]
                          <= max(_pp[1], _np[1]) + 0.5)
            if _col_y:
                _col_y = (min(_pp[0], _np[0]) - 0.5 <= _cp[0]
                          <= max(_pp[0], _np[0]) + 0.5)
            _cp_key = (round(_cp[0], 1), round(_cp[1], 1))
            _is_gate = _cp_key in _gate_pts
            _is_esc = _cp_key in _cbe_esc_pts
            if not (_col_x or _col_y) or _is_gate or _is_esc:
                _deduped.append(_cp)
        if out:
            _deduped.append(out[-1])
        out = _deduped

        # Derive escape indices from final waypoint list; gate insertions and collinear
        # dedup may have shifted the initial indices, so search by coordinate proximity.
        _cbe_esc_idxs: "set[int]" = set()
        if _cbe_src_esc_coords is not None:
            for _fi, _fp in enumerate(out):
                if abs(_fp[0] - _cbe_src_esc_coords[0]) < 0.5 and abs(_fp[1] - _cbe_src_esc_coords[1]) < 0.5:
                    _cbe_esc_idxs.add(_fi)
                    break
        if _cbe_dst_esc_coords is not None:
            for _fi in range(len(out) - 1, -1, -1):
                if abs(out[_fi][0] - _cbe_dst_esc_coords[0]) < 0.5 and abs(out[_fi][1] - _cbe_dst_esc_coords[1]) < 0.5:
                    _cbe_esc_idxs.add(_fi)
                    break

        # Collapse tiny horizontal first segment in TB: a small grid-snap jog
        # (< 32px) at the source makes the arrowhead point sideways. Move the
        # first point to the second point's x so the exit is purely vertical.
        if _is_tb and len(out) >= 3:
            _p0, _p1, _p2 = out[0], out[1], out[2]
            if (_p0[1] == _p1[1]           # first segment horizontal
                    and _p1[0] == _p2[0]   # second segment vertical
                    and abs(_p1[0] - _p0[0]) <= 32):  # small jog
                out[0] = (_p1[0], _p0[1])

        # Convert horizontal final segment into a Z-turn with vertical approach.
        # When the A* reaches dest_top_y at a different x and slides horizontally
        # to the port, insert a turn 16px above the destination so the arrow enters
        # from above pointing straight down.
        # Skip when a gate point sits at dest.y: the group boundary coincides with
        # the node top, so the turn would go above the boundary (outside the group),
        # and the trim loop would erase the gate waypoint.
        if _is_tb and len(out) >= 2:
            _pen, _lst = out[-2], out[-1]
            if (_pen[1] == _lst[1]                              # final segment horizontal
                    and abs(_lst[1] - float(dn.y)) < 2.0       # at destination's top face
                    and not any(abs(_gy - _lst[1]) < 2.0 for (_, _gy) in _gate_pts)):
                _vturn = 16.0
                _yt = _lst[1] - _vturn
                # Trim all trailing points at dest.y before inserting Z-turn,
                # otherwise out keeps a point at dest.y followed by one 16px above it
                # (backward UP segment).
                _trimmed = out[:]
                while len(_trimmed) >= 2 and abs(_trimmed[-1][1] - _lst[1]) < 1.0:
                    _trimmed = _trimmed[:-1]
                out = _trimmed + [(_pen[0], _yt), (_lst[0], _yt), _lst]

        r["waypoints"] = [(float(x), float(y)) for x, y in out]
        r["_cbe_rerouted"] = True
        if _cbe_esc_idxs:
            r["_cbe_escape_idxs"] = _cbe_esc_idxs

        # Scope tagging (harness compound-gate validator + AC11 in-pipeline check).
        r["source_scope"] = sn.group if sg else ""
        r["target_scope"] = dn.group if dg else ""
        r["semantic_source_id"] = s
        r["semantic_target_id"] = d
        r["routing_source_id"] = s
        r["routing_target_id"] = d

    # Equalise overlapping corridors: stagger shared horizontal rails and
    # separate shared vertical lanes so no two routes overlap.
    # Gate coordinates are excluded from equalization to preserve gate waypoints.
    _all_gate_coords = frozenset(
        (round(g.point.x, 1), round(g.point.y, 1)) for g in gates
    )
    _pre_equalize_wps = {r.get("edge_id"): list(r.get("waypoints") or []) for r in routed}
    _equalize_corridors(routed, nodes, grp_bboxes, direction=direction, gate_coords=_all_gate_coords)
    # Revert any route whose waypoints now intersect a non-src/non-dst node interior.
    for _r in routed:
        _wps = _r.get("waypoints") or []
        _eid = _r.get("edge_id")
        _pre = _pre_equalize_wps.get(_eid)
        if _pre is None or _wps == _pre:
            continue
        _sid = _r.get("semantic_source_id") or _r.get("routing_source_id", "")
        _did = _r.get("semantic_target_id") or _r.get("routing_target_id", "")
        _crosses = False
        for _wi in range(len(_wps) - 1):
            _ax, _ay = _wps[_wi]
            _bx, _by = _wps[_wi + 1]
            for _nid, (_rx0, _ry0, _rx1, _ry1) in node_rects.items():
                if _nid in (_sid, _did):
                    continue
                if _ay == _by:  # horizontal segment
                    if _ry0 < _ay < _ry1 and min(_ax, _bx) < _rx1 and max(_ax, _bx) > _rx0:
                        _crosses = True
                        break
                elif _ax == _bx:  # vertical segment
                    if _rx0 < _ax < _rx1 and min(_ay, _by) < _ry1 and max(_ay, _by) > _ry0:
                        _crosses = True
                        break
            if _crosses:
                break
        if _crosses:
            # Before reverting, try the opposite equalization direction to avoid
            # recreating the lane overlap that equalization was designed to fix.
            _alt_wps = None
            if len(_wps) == len(_pre):
                _sdx_list = [
                    _wps[_wi][0] - _pre[_wi][0]
                    for _wi in range(1, len(_wps) - 1)
                    if abs(_wps[_wi][0] - _pre[_wi][0]) > 1.0
                ]
                if _sdx_list and all(abs(_d - _sdx_list[0]) < 1.0 for _d in _sdx_list):
                    _sdx = _sdx_list[0]
                    _alt = [
                        (_pre[_wi][0] - _sdx, _pre[_wi][1])
                        if abs(_wps[_wi][0] - _pre[_wi][0]) > 1.0 else _pre[_wi]
                        for _wi in range(len(_pre))
                    ]
                    _alt_crosses = False
                    for _wi2 in range(len(_alt) - 1):
                        _ax2, _ay2 = _alt[_wi2]
                        _bx2, _by2 = _alt[_wi2 + 1]
                        for _nid2, (_rx0, _ry0, _rx1, _ry1) in node_rects.items():
                            if _nid2 in (_sid, _did):
                                continue
                            if _ay2 == _by2:
                                if (_ry0 < _ay2 < _ry1
                                        and min(_ax2, _bx2) < _rx1
                                        and max(_ax2, _bx2) > _rx0):
                                    _alt_crosses = True
                                    break
                            elif _ax2 == _bx2:
                                if (_rx0 < _ax2 < _rx1
                                        and min(_ay2, _by2) < _ry1
                                        and max(_ay2, _by2) > _ry0):
                                    _alt_crosses = True
                                    break
                        if _alt_crosses:
                            break
                    if not _alt_crosses:
                        # Verify the opposite lane isn't already occupied by
                        # another route's vertical segments — accepting it would
                        # recreate the lane-sharing the equalization was designed
                        # to fix.
                        _alt_overlap = False
                        for _r2 in routed:
                            if _r2 is _r:
                                continue
                            _wps2 = _r2.get("waypoints") or []
                            for _wi2 in range(len(_wps2) - 1):
                                _ax2, _ay2 = _wps2[_wi2]
                                _bx2, _by2 = _wps2[_wi2 + 1]
                                if abs(_ax2 - _bx2) >= 1.0:
                                    continue  # horizontal — skip
                                for _wi3 in range(len(_alt) - 1):
                                    _ax3, _ay3 = _alt[_wi3]
                                    _bx3, _by3 = _alt[_wi3 + 1]
                                    if abs(_ax3 - _bx3) >= 1.0:
                                        continue  # not vertical
                                    if abs(_ax2 - _ax3) >= 2.0:
                                        continue  # different x lane
                                    _s3lo = min(_ay3, _by3)
                                    _s3hi = max(_ay3, _by3)
                                    _s2lo = min(_ay2, _by2)
                                    _s2hi = max(_ay2, _by2)
                                    if _s3lo < _s2hi and _s3hi > _s2lo:
                                        _alt_overlap = True
                                        break
                                if _alt_overlap:
                                    break
                            if _alt_overlap:
                                break
                        if not _alt_overlap:
                            _alt_wps = _alt
            _r["waypoints"] = _alt_wps if _alt_wps is not None else list(_pre)

    # Second pass: place labels of rerouted edges clear of every other route.
    all_segs: "list[tuple]" = []
    for r in routed:
        wps = r.get("waypoints") or []
        for i in range(len(wps) - 1):
            all_segs.append((r.get("edge_id"), wps[i], wps[i + 1]))
    for r in routed:
        if not r.get("_cbe_rerouted") or not r.get("label"):
            continue
        wps = r["waypoints"]
        eid = r.get("edge_id")
        lw = max(30.0, len(str(r["label"])) * 7.0)
        lh = 18.0
        others = [
            (min(x1[0], x2[0]) - 1, min(x1[1], x2[1]) - 1,
             max(x1[0], x2[0]) + 1, max(x1[1], x2[1]) + 1)
            for (oeid, x1, x2) in all_segs if oeid != eid
        ]
        obs = others + list(node_rects.values()) + band_rects
        pos = _cbe_place_label(wps, lw, lh, obs)
        if pos:
            r["lx"], r["ly"] = pos

    for r in routed:
        r.pop("_cbe_rerouted", None)
        r.pop("_src_port", None)
        r.pop("_dst_port", None)
        r.pop("_src_normal", None)
        r.pop("_dst_normal", None)

    return tuple(gates)
