from __future__ import annotations

import dataclasses
import math
import re
import types as _types
import warnings
from dataclasses import dataclass
from html import escape as _h
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from ._geometry import (
        ArrowSpec, CompiledFlowchart, FinalizedLayout,
        TextLayout, NodeLayout, GroupLayout, Point, PortSide,
        RoutedEdge, LayoutGraph, ValidationResult,
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
    _compact_group_columns, _group_coherent_cols,
)
from ._routing import (
    _route_edges, _node_render_w, _finalize_self_loop_offsets,
    _astar_route, _blocked_segs, _ensure_orthogonal,
)
from ._renderer import (
    _render_legend,
    _separate_groups_lr,
    _separate_groups_tb,
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
    inferred_legend: bool = True

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
    """Minimal single-run TextLayout for building NodeLayout / GroupLayout IR."""
    from ._geometry import TextLayout, TextLine, TextRun, TextStyle
    style = TextStyle()
    # Cap at 450px to match _routing._est_label_w; without this, long (>56 char)
    # labels diverge between routing placement and stored bounds. Affects
    # node/group width for long labels too (single label-layout path).
    w = min(450.0, _estimate_text_width(text))
    run = TextRun(text=text, style=style, width=w, height=18.0)
    line = TextLine(runs=(run,), width=w, height=18.0, baseline=14.0)
    return TextLayout(
        lines=(line,),
        width=w,
        height=18.0,
        line_height=18.0,
        min_content_width=min(w, 40.0),
        max_content_width=w,
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
        src_dir = {
            PortSide.RIGHT: Point(1.0, 0.0), PortSide.LEFT: Point(-1.0, 0.0),
            PortSide.BOTTOM: Point(0.0, 1.0), PortSide.TOP: Point(0.0, -1.0),
        }.get(src_side, Point(0.0, 1.0))
        dst_dir = {
            PortSide.RIGHT: Point(1.0, 0.0), PortSide.LEFT: Point(-1.0, 0.0),
            PortSide.BOTTOM: Point(0.0, 1.0), PortSide.TOP: Point(0.0, -1.0),
        }.get(dst_side, Point(0.0, -1.0))

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
        }
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
    from ._geometry import LayoutGraph, LayoutNode, LayoutGroup, LayoutEdge, MarkerKind
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
    _assign_ranks(nodes, edges)
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

    # Route edges via Python A*
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

    from ._geometry import LayoutMetadata  # noqa: PLC0415
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
    return validate_finalized_layout(layout, metadata=metadata)


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
        _updated_cw = _separate_groups_tb(nodes, groups, canvas_w)
        canvas_w = _updated_cw

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
    """
    x0, y0, x1, y1 = bbox

    def _inside(p: "tuple[float, float]") -> bool:
        return x0 < p[0] < x1 and y0 < p[1] < y1

    res: "list[tuple[int, float, float]]" = []
    for i in range(len(poly) - 1):
        a, b = poly[i], poly[i + 1]
        if _inside(a) == _inside(b):
            continue
        if a[0] == b[0]:  # vertical segment → crosses a horizontal edge
            yb = y0 if abs(a[1] - y0) + abs(b[1] - y0) <= abs(a[1] - y1) + abs(b[1] - y1) else y1
            res.append((i, float(a[0]), float(yb)))
        else:             # horizontal segment → crosses a vertical edge
            xb = x0 if abs(a[0] - x0) + abs(b[0] - x0) <= abs(a[0] - x1) + abs(b[0] - x1) else x1
            res.append((i, float(xb), float(a[1])))
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


def _reroute_cross_boundary_edges(
    routed: "list[dict]",
    nodes: "dict[str, _Node]",
    grp_bboxes: "dict[str, tuple]",
    canvas_w: float,
    canvas_h: float,
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
        if sn.group == dn.group or (sg is None and dg is None):
            continue

        scx = sn.x + _node_render_w(sn) / 2.0
        scy = sn.y + _node_render_h(sn) / 2.0
        dcx = dn.x + _node_render_w(dn) / 2.0
        dcy = dn.y + _node_render_h(dn) / 2.0
        a = _cbe_node_face(sn, (dcx, dcy))
        b = _cbe_node_face(dn, (scx, scy))

        endpoint_groups = {sn.group, dn.group}
        obstacles: "list[tuple]" = [
            rect for nid, rect in node_rects.items() if nid not in (s, d)
        ]
        for gid, (x0, y0, x1, y1) in grp_bboxes.items():
            obstacles.append((x0, y0, x1, y0 + band))       # title band
            if gid not in endpoint_groups:
                obstacles.append((x0, y0, x1, y1))           # unrelated interior

        gx, gy = _cbe_build_grid(nodes, grp_bboxes, [a, b], canvas_w, canvas_h)
        blocked = _blocked_segs(gx, gy, obstacles)
        path = _astar_route(int(a[0]), int(a[1]), int(b[0]), int(b[1]), gx, gy, blocked)
        if not path or len(path) < 2:
            continue  # keep the original route if A* cannot improve it

        poly = [(float(x), float(y)) for x, y in path]
        poly[0] = (float(a[0]), float(a[1]))
        poly[-1] = (float(b[0]), float(b[1]))
        # A* snaps the endpoints to grid rows/columns; substituting the exact node
        # faces back can leave the first/last segment diagonal, so re-orthogonalize
        # (same invariant the main router enforces) before deriving gates.
        poly = _ensure_orthogonal(poly)
        out = [poly[0]]
        for p in poly[1:]:
            if (round(p[0], 2), round(p[1], 2)) != (round(out[-1][0], 2), round(out[-1][1], 2)):
                out.append(p)

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
        for seg, pt, gid, role in sorted(inserts, key=lambda t: -t[0]):
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

        r["waypoints"] = [(float(x), float(y)) for x, y in out]
        r["_cbe_rerouted"] = True

        # Scope tagging (harness compound-gate validator + AC11 in-pipeline check).
        r["source_scope"] = sn.group if sg else ""
        r["target_scope"] = dn.group if dg else ""
        r["semantic_source_id"] = s
        r["semantic_target_id"] = d
        r["routing_source_id"] = s
        r["routing_target_id"] = d

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

    return tuple(gates)
