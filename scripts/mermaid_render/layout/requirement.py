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
from typing import Optional

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
_TEXT_WRAP_CHARS = 30   # approximate chars per line at 10px font in a 220px card


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
    """Word-wrap text to at most max_chars per line."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
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
    """Card height: header + wrapped attribute rows + vertical padding."""
    n_lines = 0
    for key, val in node.get("attrs", {}).items():
        if key == "text":
            n_lines += len(_wrap_text(val, _TEXT_WRAP_CHARS))
        else:
            n_lines += 1
    return float(_HEADER_H + max(n_lines, 1) * _ATTR_H + _ATTR_PAD * 2)


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


def _route_edge(
    src_name: str,
    dst_name: str,
    node_pos: dict[str, tuple[float, float]],
    node_h: dict[str, float],
    ranks: dict[str, int],
    col_of: dict[str, int],
    exit_fraction: float,
) -> tuple[tuple[float, float], ...]:
    """Compute orthogonal waypoints routing from source boundary to target boundary.

    For cross-rank edges (TB layout): exits the source bottom face and enters
    the target top face via an L-shaped route through the inter-row gap.
    For same-rank edges: routes via left/right faces through the inter-column gap.
    """
    sx, sy = node_pos[src_name]
    sh = node_h[src_name]
    tx, ty = node_pos[dst_name]
    th = node_h[dst_name]

    src_rank = ranks.get(src_name, 0)
    dst_rank = ranks.get(dst_name, 0)

    if src_rank < dst_rank:
        # Source above target — exit bottom, enter top
        exit_x = sx + _NODE_W * exit_fraction
        exit_y = sy + sh
        enter_x = tx + _NODE_W * 0.5
        enter_y = ty
        mid_y = (exit_y + enter_y) / 2
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
        exit_x = sx + _NODE_W * exit_fraction
        exit_y = sy
        enter_x = tx + _NODE_W * 0.5
        enter_y = ty + th
        mid_y = (exit_y + enter_y) / 2
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
            exit_x, exit_y = sx + _NODE_W, sy + sh * 0.5
            enter_x, enter_y = tx, ty + th * 0.5
        else:
            exit_x, exit_y = sx, sy + sh * 0.5
            enter_x, enter_y = tx + _NODE_W, ty + th * 0.5
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


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_requirement_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse requirementDiagram source and return an SvgScene.

    Uses topological rank assignment so edges route between rows rather than
    across a fixed grid.  Each edge exits the source card boundary and enters
    the target card boundary via an orthogonal L-shaped route.
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

    # Measure each card
    heights: dict[str, float] = {n: _node_height(nodes[n]) for n in node_names}

    # Topological rank assignment
    ranks = _compute_ranks(node_names, relations)

    rank_groups: dict[int, list[str]] = defaultdict(list)
    for n in node_names:
        rank_groups[ranks[n]].append(n)

    ordered = _order_nodes_in_ranks(dict(rank_groups), relations, ranks)

    # Compute canvas width from the widest row
    max_cols = max((len(v) for v in ordered.values()), default=1)
    canvas_w = float(_PAD_H * 2 + max_cols * _NODE_W + (max_cols - 1) * _COL_GAP)

    n_ranks = max(ranks.values(), default=0) + 1

    # Compute row heights (tallest card in each rank)
    row_h: dict[int, float] = {
        r: max((heights[n] for n in ordered.get(r, [])), default=64.0)
        for r in range(n_ranks)
    }

    # Assign positions: centre each row on the canvas
    node_pos: dict[str, tuple[float, float]] = {}
    col_of: dict[str, int] = {}
    cumulative_y = _PAD_V

    for r in range(n_ranks):
        row_nodes = ordered.get(r, [])
        n_cols = len(row_nodes)
        row_w = n_cols * _NODE_W + (n_cols - 1) * _COL_GAP
        row_start_x = (canvas_w - row_w) / 2
        for ci, n in enumerate(row_nodes):
            node_pos[n] = (row_start_x + ci * (_NODE_W + _COL_GAP), cumulative_y)
            col_of[n] = ci
        cumulative_y += row_h[r] + _ROW_GAP

    canvas_h = float(cumulative_y - _ROW_GAP + _PAD_V)

    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []

    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    # Draw cards
    for nname, node in nodes.items():
        if nname not in node_pos:
            continue
        px, py = node_pos[nname]
        nh = heights[nname]
        is_element = node["kind"] == "element"
        hdr_fill = _ELEM_HEADER_FILL if is_element else _REQ_HEADER_FILL
        hdr_text_color = _ELEM_HEADER_TEXT if is_element else _REQ_HEADER_TEXT
        body_fill = _ELEM_BODY_FILL if is_element else _REQ_BODY_FILL
        stroke_color = _ELEM_STROKE if is_element else _REQ_STROKE
        subtype = node.get("subtype", "requirement")

        node_elements.append(SceneRect(
            element_id=f"{scene_id}-node-hdr-{nname}",
            x=px, y=py,
            w=float(_NODE_W), h=float(_HEADER_H),
            paint=PaintStyle(fill=FillStyle(color=hdr_fill)),
            semantic_role="node",
            data_attrs=(("node-id", nname), ("kind", node["kind"])),
        ))
        label_elements.append(SceneText(
            element_id=f"{scene_id}-node-lbl-{nname}",
            lines=(SceneTextLine(
                text=nname,
                x=px + _NODE_W / 2,
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
            w=float(_NODE_W), h=body_h,
            paint=PaintStyle(
                fill=FillStyle(color=body_fill),
                stroke=StrokeStyle(color=stroke_color, width=1.0),
            ),
        ))

        # Attributes — text field word-wrapped; others on one line each
        ay = float(py + _HEADER_H + _ATTR_PAD)
        for key, val in node.get("attrs", {}).items():
            if key == "text":
                wrapped = _wrap_text(val, _TEXT_WRAP_CHARS)
                for li, line_text in enumerate(wrapped):
                    display = f"{key}: {line_text}" if li == 0 else f"  {line_text}"
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
            else:
                label_elements.append(SceneText(
                    element_id=f"{scene_id}-attr-{nname}-{key}",
                    lines=(SceneTextLine(
                        text=f"{key}: {val}",
                        x=px + 6, y=ay + _FONT_ATTR + 2,
                        font_size=float(_FONT_ATTR),
                        fill_color=_TEXT_COLOR,
                    ),),
                    text_anchor="start",
                ))
                ay += _ATTR_H

    # Build per-source edge index so multiple outgoing edges spread across the
    # source face rather than all leaving from the same centre point
    outgoing_idx: dict[str, list[int]] = defaultdict(list)
    for ri, rel in enumerate(relations):
        if rel["from"] in node_pos:
            outgoing_idx[rel["from"]].append(ri)

    # Draw edges
    for ri, rel in enumerate(relations):
        fn, tn = rel["from"], rel["to"]
        if fn not in node_pos or tn not in node_pos:
            continue

        src_edges = outgoing_idx[fn]
        edge_rank = src_edges.index(ri)
        n_src_edges = len(src_edges)
        exit_fraction = (edge_rank + 1) / (n_src_edges + 1)

        waypoints = _route_edge(fn, tn, node_pos, heights, ranks, col_of, exit_fraction)

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
