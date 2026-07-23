from __future__ import annotations

import math
import re
import types as _types
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
from ._routing import _route_edges, _node_render_w, _finalize_self_loop_offsets
from ._renderer import (
    _render_legend,
    _separate_groups_lr,
    _separate_groups_tb,
    _push_nonmembers_out_of_groups_lr,
    _compute_group_bboxes,
    _ACCENT_CYCLE,
)

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
        # Semantic / routing / scope fields for state-diagram edges
        _sem_e = (sm_edge_semantic or {}).get((src, dst))
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

    Replaces the _apply_inner_direction_positions call in _compile_flowchart.
    Removes the need for the rank-flattening pre-pass: instead of forcing all
    LR-group members to the same rank before coordinate assignment, we let
    _assign_coordinates run normally and correct positions afterward.
    """
    _col_gap = col_gap if col_gap is not None else COL_GAP
    # Match _assign_coordinates axis classification exactly: anything not LR/RL is vertical.
    is_outer_tb = outer_direction.upper() not in ("LR", "RL")

    # Build parent → children map
    children: "dict[str, list[str]]" = {gid: [] for gid in groups}
    for gid, grp in groups.items():
        if grp.parent_group and grp.parent_group in groups:
            children[grp.parent_group].append(gid)
    root_groups = [
        gid for gid, grp in groups.items()
        if not grp.parent_group or grp.parent_group not in groups
    ]

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

    # Process groups leaf-first (DFS post-order)
    processed: "list[str]" = []
    _visit_seen: "set[str]" = set()

    def _visit(gid: str) -> None:
        if gid in _visit_seen:
            return
        _visit_seen.add(gid)
        for c in children[gid]:
            _visit(c)
        processed.append(gid)

    for gid in root_groups:
        _visit(gid)

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
            label_width=float(max(80, len(g.label or "") * 8)),
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


def _compile_flowchart(
    src: str,
    width_hint: int,
    options: "RenderOptions | None",
    *,
    direction_override: "Optional[str]" = None,
    height_hint: int = 0,
    style_overrides: str = "",
) -> "CompiledFlowchart":
    """Run the full flowchart layout pipeline and return a CompiledFlowchart.

    This is the single authoritative entry point for flowchart/graph/stateDiagram
    geometry. All layout, routing, IR construction, and validation happen here.
    """
    from ._geometry import (
        CompiledFlowchart, FinalizedLayout, LayoutMetadata,
        NodeLayout, GroupLayout, RoutedEdge,
        validate_finalized_layout, _empty_diagnostics, Rect, Point,
    )

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
    _sm_edge_semantic: "dict" = {}    # (src, dst) → _Edge with semantic info
    _sm_composite_gates: "dict" = {}  # composite_id → (entry_gate_id, exit_gate_id)
    if _top_directive in _state_directives:
        from .statediagram import compile_state_machine as _compile_sm, state_model_to_graph as _sm_to_graph, CompositeState as _CompositeState
        _sm_model = _compile_sm(content_lines)
        nodes, edges, groups = _sm_to_graph(_sm_model)
        # Capture edge semantic info BEFORE _break_cycles() modifies the edge list
        for _se in edges:
            _sm_src = getattr(_se, 'semantic_src', '')
            _sm_sc = getattr(_se, 'source_scope', '')
            _sm_sg = getattr(_se, 'target_scope', '')
            if _sm_src or _sm_sc or _sm_sg:
                _sm_edge_semantic[(_se.src, _se.dst)] = _se
        # AC3: collect composite gates from the compiled model
        for _cs in _sm_model.states:
            if isinstance(_cs, _CompositeState) and _cs.entry_gate and _cs.exit_gate:
                _sm_composite_gates[_cs.id] = (_cs.entry_gate.id, _cs.exit_gate.id)
        # Assign stable edge IDs to any not already set by state_model_to_graph
        _eid_counts: dict[str, int] = {}
        for _e in edges:
            if not _e.edge_id:
                _base = f"{_e.src}->{_e.dst}"
                _n = _eid_counts.get(_base, 0)
                _eid_counts[_base] = _n + 1
                _e.edge_id = _base if _n == 0 else f"{_base}#{_n}"
    else:
        nodes, edges, groups = _parse_graph_source(content_lines)
    parsed_edge_count = len(edges)  # count before _break_cycles adds dummy edges
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

    # ── ELK layout path ──────────────────────────────────────────────────────
    # Try ELK for positions and edge waypoints. On success, we still run the
    # existing IR builders (_build_node_layouts_ir, _build_routed_edges_ir)
    # so that text layout, icons, and other visual properties are computed
    # identically to the Python path. ELK only provides x/y/w/h and waypoints.
    # On ElkUnavailable: fall through to Python Sugiyama + A* below.
    # Limitation: state diagrams use terminal circles ([*]) that require
    # column-centering post-processing the Python path applies but ELK does not.
    _has_terminal_circles = any(
        _is_terminal_circle(n) for n in nodes.values()
    )
    # Limitation: ELK self-loop routing produces coordinates relative to node,
    # not canvas — fall back to Python A* which handles self-loops correctly.
    _has_self_loops = any(e.src == e.dst for e in edges)
    _elk_routed: "list | None" = None
    _elk_grp_bboxes: "dict | None" = None
    _use_elk = False
    _has_inner_dir = False
    try:
        if _has_terminal_circles:
            raise Exception("terminal-circle fallback to Python")
        if _has_self_loops:
            raise Exception("self-loop fallback to Python")
        from .elk_adapter import layout_with_elk as _layout_with_elk  # noqa: PLC0415
        # ELK needs correct measured bounds; _assign_coordinates initialises w/h.
        _assign_coordinates(
            nodes, direction,
            col_gap=_init_cfg.get("col_gap"),
            rank_gap=_init_cfg.get("rank_gap"),
            canvas_pad=_init_cfg.get("diagram_padding"),
        )
        _layout_graph = _build_layout_graph(nodes, edges, groups, direction)
        _orig_edge_map = _elk_edge_id_map(edges)
        _elk_result, _elk_meta = _layout_with_elk(_layout_graph, spacing=_init_cfg)
        for _nid_elk, _nl_elk in _elk_result.node_layouts.items():
            if _nid_elk in nodes:
                nodes[_nid_elk].x = int(_nl_elk.outer_bounds.x)
                nodes[_nid_elk].y = int(_nl_elk.outer_bounds.y)
        # Fix inner-direction groups after ELK: ELK with INCLUDE_CHILDREN uses
        # outer direction for all nodes; re-apply per-group inner direction post-hoc.
        _has_inner_dir = any(
            g.local_direction and g.local_direction.upper() != direction.upper()
            for g in _layout_graph.groups
        )
        if _has_inner_dir and groups:
            _recursive_group_layout(nodes, edges, groups, direction,
                                    col_gap=_init_cfg.get("col_gap"))
            # Clear ELK bboxes — _py_grp_bboxes (padded, recursive) is computed
            # from the new node positions downstream and takes precedence.
            _elk_grp_bboxes = None
        else:
            # Capture ELK compound-node bounds directly — authoritative when
            # all groups share the outer direction.
            _elk_grp_bboxes = {
                gid: [
                    gl.boundary_bounds.x,
                    gl.boundary_bounds.y,
                    gl.boundary_bounds.x + gl.boundary_bounds.w,
                    gl.boundary_bounds.y + gl.boundary_bounds.h,
                ]
                for gid, gl in _elk_result.group_layouts.items()
            }
        _elk_routed = [
            {
                "id": _re.edge_id,
                "waypoints": [(p.x, p.y) for p in _re.waypoints],
                "edge": _orig_edge_map.get(_re.edge_id),
            }
            for _re in _elk_result.routed_edges
        ]
        _use_elk = True
        _elk_metadata_algo = "ELK-layered+python-routed" if _has_inner_dir else "ELK-layered"
    except Exception:  # includes ElkUnavailable
        pass  # fall through to Python Sugiyama pipeline

    # Always run topology passes: needed for widths/heights (via _assign_coordinates)
    # even when ELK supplies x/y. ELK positions overwrite Python positions after.
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)

    if _use_elk:
        # ELK positions already applied to _Node.x/_Node.y above.
        # n.rank is set by _assign_ranks (always runs now), so depth-tint works.
        # Use ELK compound-node bounds directly as group bboxes. Fall back to
        # Python-computed bounds only for any group ELK did not return (rare).
        _elk_pad = int(_init_cfg.get("diagram_padding", CANVAS_PAD))
        _py_grp_bboxes = _compute_group_bboxes(nodes, groups, 99999, 99999) if groups else {}
        _grp_bboxes = {**_py_grp_bboxes, **(_elk_grp_bboxes or {})}
        # Canvas from union of ELK-positioned nodes and group boundaries.
        _all_x1: "list[float]" = [
            float(n.x + (n.width or NODE_W)) for n in nodes.values() if not n.is_dummy
        ]
        _all_y1: "list[float]" = [
            float(n.y + _node_render_h(n)) for n in nodes.values() if not n.is_dummy
        ]
        for _b in _grp_bboxes.values():
            _all_x1.append(float(_b[2]))
            _all_y1.append(float(_b[3]))
        canvas_w = (int(max(_all_x1)) + _elk_pad) if _all_x1 else _elk_pad * 2
        canvas_h = (int(max(_all_y1)) + _elk_pad) if _all_y1 else _elk_pad * 2
        if _has_inner_dir:
            # Nodes were repositioned by _recursive_group_layout;
            # ELK waypoints are stale. Re-route with Python A*.
            route_batch = _route_edges(nodes, edges, canvas_w, direction,
                                       group_bboxes=_grp_bboxes)
        else:
            # Build RoutedEdge dicts from ELK waypoints.
            _elk_route_dicts = []
            for _er in (_elk_routed or []):
                _e_obj = _er.get("edge")
                # Prefer matched edge's src/dst to avoid misparse of "A->B#1" id suffixes.
                if _e_obj is not None:
                    _src_node_id = _e_obj.src
                    _dst_node_id = _e_obj.dst
                elif "->" in _er["id"]:
                    _parts = _er["id"].split("->", 1)
                    _src_node_id = _parts[0]
                    _dst_node_id = _parts[1].split("#")[0]  # strip duplicate-edge suffix
                else:
                    _src_node_id = ""
                    _dst_node_id = ""
                _mk_id = None
                if _e_obj is not None and _e_obj.arrow:
                    _mk_id = "arrow-normal"
                # Label centered on geometric midpoint of waypoints.
                # Avoids origin-overlap validation failures; uses top-left anchor convention.
                _wps = _er["waypoints"]
                if _wps:
                    from ._routing import _est_label_w as _elk_est_lw
                    def _wp_x(w): return w[0] if isinstance(w, (tuple, list)) else getattr(w, "x", 0)
                    def _wp_y(w): return w[1] if isinstance(w, (tuple, list)) else getattr(w, "y", 0)
                    _cx = sum(_wp_x(w) for w in _wps) / len(_wps)
                    _cy = sum(_wp_y(w) for w in _wps) / len(_wps)
                    _lbl_txt = _e_obj.label if _e_obj else ""
                    _est_lh = 18  # single-line edge label height
                    _lx = _cx - _elk_est_lw(_lbl_txt) / 2
                    _ly = _cy - _est_lh / 2
                else:
                    _lx, _ly = 0, 0
                _elk_route_dicts.append({
                    "d": "", "waypoints": _er["waypoints"], "ah": None,
                    "label": _e_obj.label if _e_obj else "",
                    "style": _e_obj.style if _e_obj else "solid",
                    "lx": _lx, "ly": _ly, "rot": 0,
                    "marker_id": _mk_id,
                    "src": _src_node_id, "dst": _dst_node_id,
                    "extra_css": _e_obj.extra_css if _e_obj else "",
                    "src_label": _e_obj.src_label if _e_obj else "",
                    "dst_label": _e_obj.dst_label if _e_obj else "",
                    "bidir": _e_obj.bidir if _e_obj else False,
                    "source_marker": (_e_obj.source_marker.kind if hasattr(_e_obj.source_marker, "kind") else _e_obj.source_marker) if _e_obj else None,
                    "target_marker": (_e_obj.target_marker.kind if hasattr(_e_obj.target_marker, "kind") else _e_obj.target_marker) if _e_obj else None,
                    "edge_id": _er["id"],
                })
            from ._routing import RouteBatch as _RouteBatch
            route_batch = _RouteBatch(routed=tuple(_elk_route_dicts), failures=())
    else:
        # Python Sugiyama + A* path.
        # Auto-select direction (TB vs LR) when both size hints are given
        if width_hint and height_hint and not _opts.faithful_mermaid and _opts.auto_direction:
            from collections import Counter
            max_rank = max((n.rank for n in nodes.values()), default=0)
            rank_counts = Counter(n.rank for n in nodes.values() if not n.is_dummy)
            max_cols = max(rank_counts.values(), default=1)
            real_ns = [n for n in nodes.values() if not n.is_dummy]
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
        # so fan-in nodes (e.g. B & C & D → E) are not pinned to column 0.
        if direction.upper() not in ("LR", "RL"):
            from ._layout import _center_isolated_nodes  # noqa: PLC0415
            _center_isolated_nodes(nodes, edges)

        if groups:
            _recursive_group_layout(
                nodes, edges, groups, direction,
                col_gap=_init_cfg.get("col_gap"),
            )

        if direction.upper() in ("LR", "RL") and groups:
            _separate_groups_lr(nodes, groups)
            _pred: dict[str, str] = {}
            for _e in edges:
                if _e.src in nodes and _e.dst in nodes:
                    _pred[_e.dst] = _e.src

            def _chain_src_y(nid: str) -> int:
                visited: set[str] = set()
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
        elif direction.upper() in ("TB", "TD") and groups:
            canvas_w = _separate_groups_tb(nodes, groups, canvas_w)

        # Recompute canvas after group adjustments
        real_nodes = [n for n in nodes.values() if not n.is_dummy]
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
        # stay ≥ CANVAS_PAD (eliminates the old provisional coordinate clamps).
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

        # Build scope_bbox_map for state-diagram composite back-edge routing (AC5/AC6/AC7)
        # Maps composite_id → (x0, y0, x1, y1) from group_bboxes using "_g_" prefix convention
        _scope_bbox_map: "dict" = {
            gid[3:]: bbox
            for gid, bbox in (_grp_bboxes or {}).items()
            if gid.startswith("_g_")
        } if _sm_composite_gates else {}

        # Route edges
        route_batch = _route_edges(nodes, edges, canvas_w, direction, group_bboxes=_grp_bboxes,
                                   scope_bbox_map=_scope_bbox_map if _scope_bbox_map else None)

    # Build typed IR
    node_layouts = _build_node_layouts_ir(nodes, groups)
    group_layouts = _build_group_layouts_ir(groups, _grp_bboxes)
    # Clip cross-scope exit routes (state-diagram composite exits) so the path
    # originates from the source group's boundary rather than from the internal
    # scoped-final-state node inside the box. src_group is set only by
    # state_model_to_graph(); the map is empty (and this is a no-op) otherwise.
    _src_group_map = {
        e.edge_id: e.src_group
        for e in edges
        if getattr(e, "src_group", None) and e.edge_id
    }
    if _src_group_map:
        _clip_cross_scope_exit_waypoints(route_batch.routed, _src_group_map, _grp_bboxes)

    routed_edges_ir = _build_routed_edges_ir(
        route_batch.routed,
        canvas_area=canvas_w * canvas_h,
        sm_edge_semantic=_sm_edge_semantic if _sm_edge_semantic else None,
    )

    canvas_bounds = Rect(x=0.0, y=0.0, w=float(canvas_w), h=float(canvas_h))

    finalized = FinalizedLayout(
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
    )

    _algo = "ELK-layered" if _use_elk else "LongestPathRanker+BarycentricOrderer+SimpleCoordinateAssigner"
    _real_nodes_count = len([n for n in nodes.values() if not n.is_dummy])
    metadata = LayoutMetadata(
        direction=direction,
        node_count=_real_nodes_count,
        group_count=len(groups),
        edge_count=parsed_edge_count,
        algorithm=_algo,
        backend="elkjs" if _use_elk else "python",
    )

    validation = validate_finalized_layout(finalized, metadata=metadata)

    return CompiledFlowchart(layout=finalized, validation=validation, metadata=metadata)


