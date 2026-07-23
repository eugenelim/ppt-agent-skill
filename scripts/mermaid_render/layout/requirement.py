"""mermaid_render.layout.requirement — Native requirementDiagram scene builder.

Parses ``requirementDiagram`` source and renders requirement/element boxes
with relation edges between them.

Layout: topological rank assignment (BFS from root nodes) so edges route
between rows rather than across a fixed column grid.  Edges exit from node
boundaries and are routed with orthogonal (L-shaped) segments so no line
passes through a card.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from types import MappingProxyType
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ._geometry import FinalizedLayout, RoutedEdge

from ..scene import (
    AccessibilityMetadata,
    FillStyle,
    LAYER_BACKGROUND,
    LAYER_EDGES,
    LAYER_LABELS,
    LAYER_NODES,
    LAYER_ORDER,
    PaintStyle,
    ScenePolyline,
    SceneRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)
from ._text import get_default_measurer, REQUIREMENT_FIELD

# Process-wide text measurer singleton
_MEASURER = get_default_measurer()


# ── Color tokens ──────────────────────────────────────────────────────────────

_BG_FILL = "#f8fafc"
_REQ_HEADER_FILL = "#1e3a8a"
_REQ_HEADER_TEXT = "#f0f9ff"
_REQ_BODY_FILL = "#eff6ff"
_REQ_STROKE = "#3b82f6"
_ELEM_HEADER_FILL = "#064e3b"
_ELEM_HEADER_TEXT = "#f0fdf4"
_ELEM_BODY_FILL = "#ecfdf5"
_ELEM_STROKE = "#10b981"
_REL_STROKE = "#6b7280"
_TEXT_COLOR = "#374151"
_DIM_TEXT = "#6b7280"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD_H = 48
_PAD_V = 48
_NODE_W = 220
_HEADER_H = 28
_ATTR_H = 18
_ATTR_PAD = 8
_ROW_GAP = 64
_COL_GAP = 64
_FONT_HEADER = 12
_FONT_ATTR = 10
_FONT_REL = 9


# ── Parser ────────────────────────────────────────────────────────────────────

_VALID_REL_TYPES = (
    "contains", "copies", "derives", "satisfies", "verifies", "refines", "traces"
)
_REL_RE = re.compile(
    r"^(\w+)\s*-\s*(contains|copies|derives|satisfies|verifies|refines|traces)\s*->\s*(\w+)",
    re.IGNORECASE,
)


def _parse_attr_value(raw: str) -> tuple[str, Optional[str]]:
    """Strip surrounding double-quotes; reject unquoted values containing path chars.

    Mermaid 11.15.0 grammar rejects unquoted values containing ``/`` or ``\\``.
    Returns ``(cleaned_value, error_message_or_None)``.
    """
    s = raw.strip()
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return s[1:-1], None
    if re.search(r"[/\\]", s):
        return s, (
            f"value {s!r} must be quoted — Mermaid requirementDiagram grammar "
            f"rejects unquoted values containing path characters (use double-quotes)"
        )
    return s, None


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Word-wrap text to at most max_chars per line.

    Words longer than ``max_chars`` (e.g. an unbroken file path) are hard-broken
    at the character limit so a single long token cannot overflow the card width.
    """
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        # Hard-break any word that cannot fit on a line on its own.
        while len(word) > max_chars:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:max_chars])
            word = word[max_chars:]
        if not word:
            continue
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _wrap_text_px(text: str, max_width_px: float) -> list[str]:
    """Word-wrap ``text`` to at most ``max_width_px`` pixel width.

    Uses the process-wide text measurer with REQUIREMENT_FIELD style.
    Replaces the old character-count-based ``_TEXT_WRAP_CHARS`` approach.
    Long unbroken tokens are hard-broken at character boundaries
    (``allow_emergency_break=True``) to prevent overflow.
    """
    tl = _MEASURER.layout(text, REQUIREMENT_FIELD, max_width_px, allow_emergency_break=True)
    return ["".join(run.text for run in line.runs) for line in tl.lines] or [""]


def _parse_requirement_source(src: str) -> tuple[dict, list[dict]]:
    """Return ``(nodes, relations)``.

    ``nodes``:     ``{name: {kind, subtype, attrs: {key: val}}}``
    ``relations``: ``[{from, to, rel_type}]``

    Raises ``ValueError`` with a syntax diagnostic when an attribute value
    would be rejected by Mermaid 11.15.0 (e.g. an unquoted path).
    """
    nodes: dict[str, dict] = {}
    relations: list[dict] = []
    cur_node: str | None = None

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("requirementdiagram") or stripped.startswith("%%"):
            continue

        # Node opening — "requirement name {" or "element name {"
        m = re.match(r"^(\w+)\s+(\w+)\s*\{", stripped)
        if m:
            raw_type = m.group(1).lower()
            name = m.group(2)
            kind = "element" if raw_type == "element" else "requirement"
            nodes[name] = {"kind": kind, "subtype": raw_type, "attrs": {}}
            cur_node = name
            continue

        if stripped == "}":
            cur_node = None
            continue

        if cur_node is not None:
            m = re.match(r"^(\w+)\s*:\s*(.+)", stripped)
            if m:
                key = m.group(1)
                val, err = _parse_attr_value(m.group(2))
                if err:
                    raise ValueError(f"requirementDiagram: {err}")
                nodes[cur_node]["attrs"][key] = val
            continue

        # Relation — "A - satisfies -> B"
        m = _REL_RE.match(stripped)
        if m:
            from_n, rel_type, to_n = m.group(1), m.group(2).strip(), m.group(3)
            relations.append({"from": from_n, "to": to_n, "rel_type": rel_type})
            if from_n not in nodes:
                nodes[from_n] = {"kind": "element", "subtype": "element", "attrs": {}}
            if to_n not in nodes:
                nodes[to_n] = {"kind": "requirement", "subtype": "requirement", "attrs": {}}

    return nodes, relations


# ── Layout helpers ────────────────────────────────────────────────────────────

def _node_height(node: dict) -> float:
    """Card height: header + wrapped attribute rows + vertical padding.

    Every attribute display line (``key: value``) is pixel-wrapped at
    ``_NODE_W - 2 * _ATTR_PAD`` so a long value grows the card rather than
    overflowing it.  Must stay in lockstep with the render loop in
    :func:`layout_requirement_scene`.
    """
    _max_w = float(_NODE_W - 2 * _ATTR_PAD)
    n_lines = 0
    for key, val in node.get("attrs", {}).items():
        tl = _MEASURER.layout(f"{key}: {val}", REQUIREMENT_FIELD, _max_w, allow_emergency_break=True)
        n_lines += len(tl.lines)
    return float(_HEADER_H + max(n_lines, 1) * _ATTR_H + _ATTR_PAD * 2)


def _node_width(node: dict, name: str) -> float:
    """Measured card width from the longest rendered line + horizontal padding.

    Uses the process-wide text measurer for accurate pixel widths.  The result is
    clamped to at least _NODE_W so this is always a minimum-preserving measure.
    """
    from ._geometry import TextStyle as _TextStyle
    _header_style = _TextStyle(font_size=float(_FONT_HEADER), font_weight=700)
    header_w = _MEASURER.layout(name, _header_style, None).width
    subtype_w = _MEASURER.layout(node.get("subtype", ""), REQUIREMENT_FIELD, None).width
    max_w = max(header_w, subtype_w)
    _max_px = float(_NODE_W - 2 * _ATTR_PAD)
    for key, val in node.get("attrs", {}).items():
        attr_layout = _MEASURER.layout(f"{key}: {val}", REQUIREMENT_FIELD, _max_px)
        max_w = max(max_w, attr_layout.width)
    return max(float(_NODE_W), max_w + 2 * _ATTR_PAD)


def _compute_ranks(node_names: list[str], relations: list[dict]) -> dict[str, int]:
    """Assign topological rank via longest-path BFS from root nodes (in-degree 0)."""
    successors: dict[str, list[str]] = {n: [] for n in node_names}
    in_degree: dict[str, int] = {n: 0 for n in node_names}

    for rel in relations:
        fn, tn = rel["from"], rel["to"]
        if fn in successors and tn in in_degree:
            successors[fn].append(tn)
            in_degree[tn] += 1

    rank: dict[str, int] = {}
    queue: list[str] = [n for n in node_names if in_degree[n] == 0]
    for n in queue:
        rank[n] = 0

    head = 0
    while head < len(queue):
        n = queue[head]
        head += 1
        for m in successors[n]:
            candidate = rank[n] + 1
            if m not in rank or rank[m] < candidate:
                rank[m] = candidate
            in_degree[m] -= 1
            if in_degree[m] == 0:
                queue.append(m)

    # Cyclic or isolated nodes fall back to rank 0
    for n in node_names:
        if n not in rank:
            rank[n] = 0

    return rank


def _order_nodes_in_ranks(
    rank_groups: dict[int, list[str]],
    relations: list[dict],
    ranks: dict[str, int],
) -> dict[int, list[str]]:
    """Order nodes within each rank by barycenter of their successors (bottom-up pass).

    Minimises edge crossings for the common case of a 2-layer DAG.
    """
    if not rank_groups:
        return {}

    max_rank = max(rank_groups.keys())
    ordered: dict[int, list[str]] = {}

    for r in range(max_rank, -1, -1):
        nodes_here = rank_groups.get(r, [])
        if not nodes_here:
            continue

        if r == max_rank:
            ordered[r] = sorted(nodes_here)
            continue

        next_order = ordered.get(r + 1, sorted(rank_groups.get(r + 1, [])))
        next_pos: dict[str, float] = {n: float(i) for i, n in enumerate(next_order)}

        succ_pos: dict[str, list[float]] = {n: [] for n in nodes_here}
        for rel in relations:
            fn, tn = rel["from"], rel["to"]
            if ranks.get(fn) == r and tn in next_pos:
                succ_pos[fn].append(next_pos[tn])

        def _bc(n: str) -> float:
            positions = succ_pos[n]
            return sum(positions) / len(positions) if positions else float("inf")

        ordered[r] = sorted(nodes_here, key=lambda n: (_bc(n), n))

    return ordered


def _clamp_mid_y(
    mid_y: float,
    src_rank: int,
    dst_rank: int,
    row_bands: dict[tuple[int, int], tuple[float, float]],
) -> float:
    """Clamp the horizontal channel into the true inter-row gap band.

    ``mid_y = (exit_y + enter_y) / 2`` places the channel halfway between the
    two *faces* being connected.  When a taller sibling shares the source rank,
    that midpoint can land inside the sibling's body.  ``row_bands`` gives the
    safe band — ``(max bottom edge of upper-rank nodes, min top edge of
    lower-rank nodes)`` — so clamping into it keeps the channel clear of every
    card in both ranks.
    """
    band = row_bands.get((src_rank, dst_rank))
    if band is None:
        return mid_y
    lo, hi = band
    if lo > hi:  # degenerate (overlapping rows) — leave the midpoint untouched
        return mid_y
    return min(max(mid_y, lo), hi)


def _route_edge(
    src_name: str,
    dst_name: str,
    node_pos: dict[str, tuple[float, float]],
    node_h: dict[str, float],
    ranks: dict[str, int],
    col_of: dict[str, int],
    exit_fraction: float,
    row_bands: dict[tuple[int, int], tuple[float, float]],
    node_w: "dict[str, float] | None" = None,
) -> tuple[tuple[float, float], ...]:
    """Compute orthogonal waypoints routing from source boundary to target boundary.

    For cross-rank edges (TB layout): exits the source bottom face and enters
    the target top face via an L-shaped route through the inter-row gap.  The
    horizontal channel is clamped into the inter-row band (see
    :func:`_clamp_mid_y`) so it can never cross a taller sibling card.
    For same-rank edges: routes via left/right faces through the inter-column gap.
    node_w: optional per-node card-width dict; falls back to _NODE_W when absent.
    """
    sx, sy = node_pos[src_name]
    sh = node_h[src_name]
    tx, ty = node_pos[dst_name]
    th = node_h[dst_name]

    src_w = node_w[src_name] if (node_w and src_name in node_w) else float(_NODE_W)
    dst_w = node_w[dst_name] if (node_w and dst_name in node_w) else float(_NODE_W)

    src_rank = ranks.get(src_name, 0)
    dst_rank = ranks.get(dst_name, 0)

    if src_rank < dst_rank:
        # Source above target — exit bottom, enter top
        exit_x = sx + src_w * exit_fraction
        exit_y = sy + sh
        enter_x = tx + dst_w * 0.5
        enter_y = ty
        mid_y = _clamp_mid_y((exit_y + enter_y) / 2, src_rank, dst_rank, row_bands)
        if abs(exit_x - enter_x) < 2.0:
            return ((exit_x, exit_y), (enter_x, enter_y))
        return (
            (exit_x, exit_y),
            (exit_x, mid_y),
            (enter_x, mid_y),
            (enter_x, enter_y),
        )

    elif src_rank > dst_rank:
        # Back edge — exit top, enter bottom
        exit_x = sx + src_w * exit_fraction
        exit_y = sy
        enter_x = tx + dst_w * 0.5
        enter_y = ty + th
        mid_y = _clamp_mid_y((exit_y + enter_y) / 2, src_rank, dst_rank, row_bands)
        if abs(exit_x - enter_x) < 2.0:
            return ((exit_x, exit_y), (enter_x, enter_y))
        return (
            (exit_x, exit_y),
            (exit_x, mid_y),
            (enter_x, mid_y),
            (enter_x, enter_y),
        )

    else:
        # Same rank — route via left / right faces
        if col_of.get(src_name, 0) < col_of.get(dst_name, 0):
            exit_x, exit_y = sx + src_w, sy + sh * 0.5
            enter_x, enter_y = tx, ty + th * 0.5
        else:
            exit_x, exit_y = sx, sy + sh * 0.5
            enter_x, enter_y = tx + dst_w, ty + th * 0.5
        mid_x = (exit_x + enter_x) / 2
        return (
            (exit_x, exit_y),
            (mid_x, exit_y),
            (mid_x, enter_y),
            (enter_x, enter_y),
        )


def _label_point(waypoints: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    """Return the midpoint of the longest segment in the route."""
    if len(waypoints) < 2:
        return waypoints[0] if waypoints else (0.0, 0.0)
    best_i, best_len = 0, 0.0
    for i in range(len(waypoints) - 1):
        x1, y1 = waypoints[i]
        x2, y2 = waypoints[i + 1]
        seg_len = abs(x2 - x1) + abs(y2 - y1)
        if seg_len > best_len:
            best_len, best_i = seg_len, i
    x1, y1 = waypoints[best_i]
    x2, y2 = waypoints[best_i + 1]
    return ((x1 + x2) / 2, (y1 + y2) / 2)


# ── Geometry compiler ─────────────────────────────────────────────────────────

def compile_requirement(src: str, *, width_hint: int = 0, height_hint: int = 0) -> "FinalizedLayout":
    """Parse requirementDiagram source and return a FinalizedLayout IR.

    Returns
    -------
    FinalizedLayout
        node_layouts[nid].outer_bounds holds each card's bounding box;
        routed_edges[i].waypoints holds the orthogonal route for relation i
        (matching the order from _parse_requirement_source).
        canvas_bounds is the natural (unscaled) canvas rectangle.
    """
    from ._geometry import (
        EdgeLabelLayout,
        FinalizedLayout,
        MarkerKind,
        NodeLayout,
        Point,
        PortLayout,
        PortSide,
        Rect,
        RoutedEdge,
        TextLayout,
        TextStyle,
        _empty_diagnostics,
    )

    def _stub_text_layout(w: float, h: float) -> TextLayout:
        return TextLayout(
            lines=(),
            width=w,
            height=h,
            line_height=h,
            min_content_width=0.0,
            max_content_width=w,
            resolved_font_path=None,
            resolved_font_family="sans-serif",
        )

    nodes, relations = _parse_requirement_source(src)
    node_names = list(nodes.keys())

    _diag = _empty_diagnostics()

    if not node_names:
        w = float(max(width_hint or 400, 400))
        _cr = Rect(0.0, 0.0, w, 160.0)
        return FinalizedLayout(
            node_layouts=MappingProxyType({}),
            group_layouts=MappingProxyType({}),
            routed_edges=(),
            visible_bounds=_cr,
            diagram_padding=float(_PAD_H),
            canvas_bounds=_cr,
            direction="TB",
            diagnostics=_diag,
            routing_failures=(),
        )

    heights: dict[str, float] = {n: _node_height(nodes[n]) for n in node_names}
    card_widths: dict[str, float] = {n: _node_width(nodes[n], n) for n in node_names}
    ranks = _compute_ranks(node_names, relations)

    rank_groups: dict[int, list[str]] = defaultdict(list)
    for n in node_names:
        rank_groups[ranks[n]].append(n)

    ordered = _order_nodes_in_ranks(dict(rank_groups), relations, ranks)

    # slot_w: column slot width derived from the widest card; each column is
    # that wide regardless of the actual card assigned, so rows stay aligned.
    slot_w = max(card_widths.values(), default=float(_NODE_W))
    max_cols = max((len(v) for v in ordered.values()), default=1)
    canvas_w = float(_PAD_H * 2 + max_cols * slot_w + (max_cols - 1) * _COL_GAP)

    n_ranks = max(ranks.values(), default=0) + 1
    row_h: dict[int, float] = {
        r: max((heights[n] for n in ordered.get(r, [])), default=64.0)
        for r in range(n_ranks)
    }

    node_pos: dict[str, tuple[float, float]] = {}
    col_of: dict[str, int] = {}
    cumulative_y = float(_PAD_V)

    for r in range(n_ranks):
        row_nodes = ordered.get(r, [])
        n_cols = len(row_nodes)
        row_w = n_cols * slot_w + (n_cols - 1) * _COL_GAP
        row_start_x = (canvas_w - row_w) / 2
        for ci, n in enumerate(row_nodes):
            node_pos[n] = (row_start_x + ci * (slot_w + _COL_GAP), cumulative_y)
            col_of[n] = ci
        cumulative_y += row_h[r] + _ROW_GAP

    canvas_h = float(cumulative_y - _ROW_GAP + _PAD_V)

    rank_bottom: dict[int, float] = {}
    rank_top: dict[int, float] = {}
    for n, (px, py) in node_pos.items():
        r = ranks[n]
        bottom = py + heights[n]
        rank_bottom[r] = max(rank_bottom.get(r, bottom), bottom)
        rank_top[r] = min(rank_top.get(r, py), py)

    row_bands: dict[tuple[int, int], tuple[float, float]] = {}
    for rel in relations:
        fn, tn = rel["from"], rel["to"]
        if fn not in ranks or tn not in ranks:
            continue
        sr, dr = ranks[fn], ranks[tn]
        if sr == dr:
            continue
        upper, lower = (sr, dr) if sr < dr else (dr, sr)
        row_bands[(sr, dr)] = (rank_bottom.get(upper, 0.0), rank_top.get(lower, 0.0))

    def _side_from_vec(dx: float, dy: float) -> PortSide:
        if dy > 0:
            return PortSide.BOTTOM
        if dy < 0:
            return PortSide.TOP
        if dx > 0:
            return PortSide.RIGHT
        return PortSide.LEFT

    # Build NodeLayout objects
    node_layouts: dict[str, NodeLayout] = {}
    for nname, node in nodes.items():
        if nname not in node_pos:
            continue
        px, py = node_pos[nname]
        nh = heights[nname]
        shape = "req-element" if node["kind"] == "element" else "req-requirement"
        cw_n = card_widths.get(nname, float(_NODE_W))
        node_layouts[nname] = NodeLayout(
            node_id=nname,
            semantic_shape=shape,
            outer_bounds=Rect(px, py, cw_n, nh),
            content_bounds=Rect(px, py + _HEADER_H, cw_n, max(nh - _HEADER_H, 0.0)),
            title_layout=None,
            subtitle_layout=None,
            member_layouts=(),
            icon_bounds=None,
            ports=(),
            css_classes=(f"req-{node['subtype']}",),
            extra_css="",
            is_dummy=False,
            rank=ranks[nname],
        )

    # Build outgoing edge spread index
    outgoing_idx: dict[str, list[int]] = defaultdict(list)
    for ri, rel in enumerate(relations):
        if rel["from"] in node_pos:
            outgoing_idx[rel["from"]].append(ri)

    # Build RoutedEdge objects
    routed_edges_list: list[RoutedEdge] = []
    for ri, rel in enumerate(relations):
        fn, tn = rel["from"], rel["to"]
        if fn not in node_pos or tn not in node_pos:
            continue

        src_edges = outgoing_idx[fn]
        edge_rank = src_edges.index(ri)
        n_src_edges = len(src_edges)
        exit_fraction = (edge_rank + 1) / (n_src_edges + 1)

        raw_wps = _route_edge(fn, tn, node_pos, heights, ranks, col_of, exit_fraction, row_bands, card_widths)
        waypoints = tuple(Point(float(x), float(y)) for x, y in raw_wps)

        if len(waypoints) >= 2:
            dx0 = waypoints[1].x - waypoints[0].x
            dy0 = waypoints[1].y - waypoints[0].y
            dxn = waypoints[-1].x - waypoints[-2].x
            dyn = waypoints[-1].y - waypoints[-2].y
        else:
            dx0, dy0, dxn, dyn = 0.0, 1.0, 0.0, 1.0

        rel_type = rel["rel_type"]
        _rel_style = TextStyle(font_size=float(_FONT_REL), font_weight=400)
        _lbl_tl = _MEASURER.layout(rel_type, _rel_style, None)
        lbl_w = _lbl_tl.width
        lp_x, lp_y = _label_point(tuple((wp.x, wp.y) for wp in waypoints))
        lbl_layout = EdgeLabelLayout(
            text=rel_type,
            layout=_lbl_tl,
            bounds=Rect(lp_x - lbl_w / 2, lp_y - _lbl_tl.height, lbl_w, _lbl_tl.height),
            anchor_point=Point(lp_x, lp_y),
        )

        routed_edges_list.append(RoutedEdge(
            edge_id=f"req-rel-{ri}",
            src_node_id=fn,
            dst_node_id=tn,
            src_port=PortLayout(
                node_id=fn,
                side=_side_from_vec(dx0, dy0),
                position=waypoints[0],
                direction=Point(float(dx0), float(dy0)),
            ),
            dst_port=PortLayout(
                node_id=tn,
                side=_side_from_vec(-dxn, -dyn),
                position=waypoints[-1],
                direction=Point(float(-dxn), float(-dyn)),
            ),
            waypoints=waypoints,
            edge_style="dashed",
            has_marker_end=False,
            has_marker_start=False,
            label_layout=lbl_layout,
            src_label_layout=None,
            dst_label_layout=None,
            source_marker=MarkerKind.NONE,
            target_marker=MarkerKind.NONE,
        ))

    # Apply width/height hint as uniform scaling if either is set.
    # Single-hint case: set the hinted dimension exactly; other dimension scales
    # proportionally.  Both-hint case: scale by the minimum of the two factors.
    scale = 1.0
    if width_hint > 0 and canvas_w > 0:
        scale = float(width_hint) / canvas_w
    if height_hint > 0 and canvas_h > 0:
        h_scale = float(height_hint) / canvas_h
        scale = min(scale, h_scale) if (width_hint > 0) else h_scale

    if scale != 1.0:
        def _sr(r: Rect) -> Rect:
            return Rect(r.x * scale, r.y * scale, r.w * scale, r.h * scale)

        def _sp(p: Point) -> Point:
            return Point(p.x * scale, p.y * scale)

        scaled_node_layouts: dict[str, NodeLayout] = {}
        for nid, nl in node_layouts.items():
            scaled_node_layouts[nid] = NodeLayout(
                node_id=nl.node_id,
                semantic_shape=nl.semantic_shape,
                outer_bounds=_sr(nl.outer_bounds),
                content_bounds=_sr(nl.content_bounds),
                title_layout=nl.title_layout,
                subtitle_layout=nl.subtitle_layout,
                member_layouts=nl.member_layouts,
                icon_bounds=nl.icon_bounds,
                ports=nl.ports,
                css_classes=nl.css_classes,
                extra_css=nl.extra_css,
                is_dummy=nl.is_dummy,
                rank=nl.rank,
            )
        node_layouts = scaled_node_layouts

        scaled_edges: list[RoutedEdge] = []
        for re_obj in routed_edges_list:
            scaled_wps = tuple(_sp(wp) for wp in re_obj.waypoints)
            lbl = re_obj.label_layout
            if lbl is not None:
                lbl = EdgeLabelLayout(
                    text=lbl.text,
                    layout=lbl.layout,
                    bounds=_sr(lbl.bounds),
                    anchor_point=_sp(lbl.anchor_point),
                )
            scaled_edges.append(RoutedEdge(
                edge_id=re_obj.edge_id,
                src_node_id=re_obj.src_node_id,
                dst_node_id=re_obj.dst_node_id,
                src_port=PortLayout(
                    node_id=re_obj.src_port.node_id,
                    side=re_obj.src_port.side,
                    position=_sp(re_obj.src_port.position),
                    direction=re_obj.src_port.direction,
                ),
                dst_port=PortLayout(
                    node_id=re_obj.dst_port.node_id,
                    side=re_obj.dst_port.side,
                    position=_sp(re_obj.dst_port.position),
                    direction=re_obj.dst_port.direction,
                ),
                waypoints=scaled_wps,
                edge_style=re_obj.edge_style,
                has_marker_end=re_obj.has_marker_end,
                has_marker_start=re_obj.has_marker_start,
                label_layout=lbl,
                src_label_layout=re_obj.src_label_layout,
                dst_label_layout=re_obj.dst_label_layout,
                source_marker=re_obj.source_marker,
                target_marker=re_obj.target_marker,
            ))
        routed_edges_list = scaled_edges

        # Set canvas dimensions precisely for single-hint case.
        if width_hint > 0 and height_hint == 0:
            canvas_w = float(width_hint)
            canvas_h = canvas_h * scale
        elif height_hint > 0 and width_hint == 0:
            canvas_h = float(height_hint)
            canvas_w = canvas_w * scale
        else:
            canvas_w = canvas_w * scale
            canvas_h = canvas_h * scale

    canvas_rect = Rect(0.0, 0.0, canvas_w, canvas_h)
    return FinalizedLayout(
        node_layouts=MappingProxyType(node_layouts),
        group_layouts=MappingProxyType({}),
        routed_edges=tuple(routed_edges_list),
        visible_bounds=canvas_rect,
        diagram_padding=float(_PAD_H),
        canvas_bounds=canvas_rect,
        direction="TB",
        diagnostics=_diag,
        routing_failures=(),
    )


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_requirement_scene(src: str, *, width_hint: int = 0, height_hint: int = 0) -> SvgScene:
    """Parse requirementDiagram source and return an SvgScene.

    Delegates layout geometry to compile_requirement() and uses the resulting
    FinalizedLayout for node positions and edge waypoints.
    """
    nodes, relations = _parse_requirement_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("requirementdiagram", content_hash)

    node_names = list(nodes.keys())
    if not node_names:
        w = max(width_hint or 400, 400)
        return SvgScene(
            scene_id=scene_id,
            diagram_type="requirementdiagram",
            width=float(w), height=160.0,
            view_box=(0.0, 0.0, float(w), 160.0),
            accessibility=AccessibilityMetadata(title="Requirement diagram"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    fl = compile_requirement(src, width_hint=width_hint, height_hint=height_hint)
    canvas_w = fl.canvas_bounds.w
    canvas_h = fl.canvas_bounds.h

    # Index routed edges by relation index
    routed_by_idx: dict[int, RoutedEdge] = {}
    for _re in fl.routed_edges:
        _eid = _re.edge_id
        if _eid.startswith("req-rel-"):
            try:
                routed_by_idx[int(_eid[8:])] = _re
            except ValueError:
                pass

    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []

    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    # Draw cards using positions from FinalizedLayout
    for nname, node in nodes.items():
        if nname not in fl.node_layouts:
            continue
        _nl = fl.node_layouts[nname]
        px = _nl.outer_bounds.x
        py = _nl.outer_bounds.y
        nh = _nl.outer_bounds.h
        is_element = node["kind"] == "element"
        hdr_fill = _ELEM_HEADER_FILL if is_element else _REQ_HEADER_FILL
        hdr_text_color = _ELEM_HEADER_TEXT if is_element else _REQ_HEADER_TEXT
        body_fill = _ELEM_BODY_FILL if is_element else _REQ_BODY_FILL
        stroke_color = _ELEM_STROKE if is_element else _REQ_STROKE

        _nw = _nl.outer_bounds.w
        _subtype_cls = _nl.css_classes[0] if _nl.css_classes else ""
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-node-hdr-{nname}",
            x=px, y=py,
            w=_nw, h=float(_HEADER_H),
            paint=PaintStyle(fill=FillStyle(color=hdr_fill)),
            semantic_role="node",
            data_attrs=(("node-id", nname), ("kind", node["kind"]), ("css-class", _subtype_cls)),
        ))
        label_elements.append(SceneText(
            element_id=f"{scene_id}-node-lbl-{nname}",
            lines=(SceneTextLine(
                text=nname,
                x=px + _nw / 2,
                y=py + _HEADER_H / 2 + _FONT_HEADER * 0.35,
                font_size=float(_FONT_HEADER),
                font_weight=700,
                fill_color=hdr_text_color,
            ),),
            text_anchor="middle",
        ))

        body_h = nh - _HEADER_H
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-node-body-{nname}",
            x=px, y=py + _HEADER_H,
            w=_nw, h=body_h,
            paint=PaintStyle(
                fill=FillStyle(color=body_fill),
                stroke=StrokeStyle(color=stroke_color, width=1.0),
            ),
        ))

        ay = float(py + _HEADER_H + _ATTR_PAD)
        for key, val in node.get("attrs", {}).items():
            wrapped = _wrap_text_px(f"{key}: {val}", float(_NODE_W - 2 * _ATTR_PAD))
            for li, line_text in enumerate(wrapped):
                display = line_text if li == 0 else f"  {line_text}"
                label_elements.append(SceneText(
                    element_id=f"{scene_id}-attr-{nname}-{key}-{li}",
                    lines=(SceneTextLine(
                        text=display,
                        x=px + 6, y=ay + _FONT_ATTR + 2,
                        font_size=float(_FONT_ATTR),
                        fill_color=_TEXT_COLOR,
                    ),),
                    text_anchor="start",
                ))
                ay += _ATTR_H

    # Draw edges using waypoints from FinalizedLayout
    for ri, rel in enumerate(relations):
        fn, tn = rel["from"], rel["to"]
        if fn not in fl.node_layouts or tn not in fl.node_layouts:
            continue
        _edge = routed_by_idx.get(ri)
        if _edge is None:
            continue
        waypoints = tuple((wp.x, wp.y) for wp in _edge.waypoints)

        edge_elements.append(ScenePolyline(
            element_id=f"{scene_id}-rel-{ri}",
            points=waypoints,
            paint=PaintStyle(
                stroke=StrokeStyle(color=_REL_STROKE, width=1.5, dasharray="4 2"),
            ),
            semantic_role="relation",
            data_attrs=(
                ("src", fn),
                ("dst", tn),
                ("rel-type", rel["rel_type"]),
            ),
        ))

        if _edge.label_layout is not None:
            lx = _edge.label_layout.anchor_point.x
            ly = _edge.label_layout.anchor_point.y
        else:
            lx, ly = _label_point(waypoints)
        label_elements.append(SceneText(
            element_id=f"{scene_id}-rel-lbl-{ri}",
            lines=(SceneTextLine(
                text=rel["rel_type"],
                x=lx, y=ly - 4,
                font_size=float(_FONT_REL),
                fill_color=_DIM_TEXT,
                italic=True,
            ),),
            text_anchor="middle",
        ))

    layers = tuple([
        (LAYER_BACKGROUND, tuple(bg_elements)),
        *[
            (name, ())
            for name in LAYER_ORDER
            if name not in (LAYER_BACKGROUND, LAYER_EDGES, LAYER_NODES, LAYER_LABELS)
        ],
        (LAYER_EDGES, tuple(edge_elements)),
        (LAYER_NODES, tuple(node_elements)),
        (LAYER_LABELS, tuple(label_elements)),
    ])

    return SvgScene(
        scene_id=scene_id,
        diagram_type="requirementdiagram",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title="Requirement diagram",
            description=(
                f"Requirement diagram with {len(node_names)} nodes "
                f"and {len(relations)} relations"
            ),
        ),
        layers=layers,
    )


# ── HTML renderer ──────────────────────────────────────────────────────────────

def requirement_to_html(src: str, *, width_hint: int = 0, height_hint: int = 0) -> str:
    """Render requirementDiagram source as a self-contained HTML div string.

    Uses compile_requirement() for all geometry, then re-calls
    _parse_requirement_source() to obtain node attribute data for rendering.
    """
    import html as _html_req

    _h = lambda s: _html_req.escape(str(s), quote=True)  # noqa: E731

    fl = compile_requirement(src, width_hint=width_hint, height_hint=height_hint)
    nodes, relations = _parse_requirement_source(src)

    cw = fl.canvas_bounds.w
    ch = fl.canvas_bounds.h

    zoom = 1.0
    if width_hint and cw > 0 and width_hint < cw:
        zoom = width_hint / cw
    zoom_css = f"zoom:{zoom:.4f};" if abs(zoom - 1.0) > 0.005 else ""

    _lf = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"
    _rel_stroke = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative; width:{int(cw)}px; height:{int(ch)}px; {zoom_css}">'
    )

    # Node cards
    for nname, node in nodes.items():
        if nname not in fl.node_layouts:
            continue
        _nl = fl.node_layouts[nname]
        px = int(_nl.outer_bounds.x)
        py = int(_nl.outer_bounds.y)
        nh = int(_nl.outer_bounds.h)
        nw = int(_nl.outer_bounds.w)
        is_element = node["kind"] == "element"
        hdr_fill = _ELEM_HEADER_FILL if is_element else _REQ_HEADER_FILL
        hdr_text_color = _ELEM_HEADER_TEXT if is_element else _REQ_HEADER_TEXT
        body_fill = _ELEM_BODY_FILL if is_element else _REQ_BODY_FILL
        stroke_color = _ELEM_STROKE if is_element else _REQ_STROKE

        _extra_classes = " ".join(_nl.css_classes)
        parts.append(
            f'<div class="node req-node {_extra_classes}" data-node-id="{_h(nname)}" style="'
            f'position:absolute; left:{px}px; top:{py}px; '
            f'width:{nw}px; height:{nh}px; '
            f'box-sizing:border-box; overflow:hidden; '
            f'border:1px solid {stroke_color}; '
            f'font-family:{_lf};">'
        )
        parts.append(
            f'<div style="'
            f'background:{hdr_fill}; color:{hdr_text_color}; '
            f'height:{_HEADER_H}px; '
            f'display:flex; align-items:center; justify-content:center; '
            f'font-size:{_FONT_HEADER}px; font-weight:700; '
            f'padding:0 6px; overflow:hidden; white-space:nowrap;">'
            f'{_h(nname)}</div>'
        )
        parts.append(
            f'<div style="background:{body_fill}; padding:{_ATTR_PAD}px 6px; '
            f'font-size:{_FONT_ATTR}px; color:{_TEXT_COLOR}; overflow:hidden;">'
        )
        for key, val in node.get("attrs", {}).items():
            wrapped = _wrap_text_px(f"{key}: {val}", float(_NODE_W - 2 * _ATTR_PAD))
            for li, line_text in enumerate(wrapped):
                display = line_text if li == 0 else f"  {line_text}"
                parts.append(
                    f'<div style="height:{_ATTR_H}px; overflow:hidden; white-space:nowrap;">'
                    f'{_h(display)}</div>'
                )
        parts.append("</div>")  # body
        parts.append("</div>")  # node card

    # SVG overlay for edges
    parts.append(
        f'<svg style="position:absolute; top:0; left:0; overflow:visible; pointer-events:none;" '
        f'width="{int(cw)}" height="{int(ch)}" viewBox="0 0 {int(cw)} {int(ch)}">'
    )

    routed_by_idx: dict[int, RoutedEdge] = {}
    for _re in fl.routed_edges:
        _eid = _re.edge_id
        if _eid.startswith("req-rel-"):
            try:
                routed_by_idx[int(_eid[8:])] = _re
            except ValueError:
                pass

    for ri, rel in enumerate(relations):
        fn, tn = rel["from"], rel["to"]
        if fn not in fl.node_layouts or tn not in fl.node_layouts:
            continue
        _edge = routed_by_idx.get(ri)
        if _edge is None:
            continue
        pts = " ".join(
            f"{wp.x:.1f},{wp.y:.1f}"
            for wp in _edge.waypoints
        )
        parts.append(
            f'<polyline points="{pts}" '
            f'fill="none" stroke="{_rel_stroke}" stroke-width="1.5" '
            f'stroke-dasharray="4 2"/>'
        )
        if _edge.label_layout is not None:
            lx = _edge.label_layout.anchor_point.x
            ly = _edge.label_layout.anchor_point.y
        else:
            wps_tuple = tuple((wp.x, wp.y) for wp in _edge.waypoints)
            lx, ly = _label_point(wps_tuple)
        parts.append(
            f'<text x="{lx:.1f}" y="{ly - 4:.1f}" '
            f'text-anchor="middle" '
            f'font-size="{_FONT_REL}px" '
            f'fill="{_DIM_TEXT}" '
            f'font-style="italic">'
            f'{_h(rel["rel_type"])}</text>'
        )

    parts.append("</svg>")
    parts.append("</div>")
    return "".join(parts)
