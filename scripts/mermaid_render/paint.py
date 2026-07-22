"""mermaid_render.paint — Generic layout-to-scene converter.

Converts the output of the existing layout algorithms (_Node/_Edge/_Group
mutable objects with computed x,y) to an immutable SvgScene.

This module handles the "mechanical migration" for the 14 diagram types
that use the generic graph topology layout. Specialized renderers for
mindmap, timeline, architecture, C4, and state live in their own modules.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .scene import (
    SvgScene, SceneGroup, SceneRect, SceneRoundedRect, SceneCircle, SceneEllipse,
    SceneLine, ScenePolyline, ScenePolygon, ScenePath, SceneText, SceneTextLine,
    SceneImage, PaintStyle, StrokeStyle, FillStyle,
    MarkerDefinition, AccessibilityMetadata, make_scene_id,
    LAYER_BACKGROUND, LAYER_BOUNDARIES, LAYER_EDGES, LAYER_NODES,
    LAYER_LABELS, LAYER_NOTES, LAYER_OVERLAYS, LAYER_ORDER,
)


# ── Default paint tokens ──────────────────────────────────────────────────────

class _Tokens:
    """Minimal set of paint tokens for the generic graph renderer."""
    bg = "#ffffff"
    node_fill = "#e8f4fd"
    node_stroke = "#4a90d9"
    node_stroke_w = 1.5
    node_rx = 8.0
    text_fill = "#1a1a2e"
    text_size = 14.0
    text_weight = 600
    edge_stroke = "#555566"
    edge_stroke_w = 1.5
    edge_dash = ""
    edge_thick_w = 3.0
    edge_dot_dash = "5,4"
    group_fill = "rgba(63,125,90,0.05)"
    group_stroke = "#3F7D5A"
    group_stroke_w = 1.5
    group_stroke_dash = "6,3"
    group_text = "#2a4a3a"
    group_text_size = 12.0
    label_fill = "#f0f0f8"
    label_stroke = "#ccccdd"
    label_text = "#222233"
    label_text_size = 12.0
    arrowhead_fill = "#555566"
    marker_size = 8.0


_DEFAULT_TOKENS = _Tokens()


def _tokens_from_theme(theme: "str | None") -> _Tokens:
    """Map a theme name onto _Tokens using the CSS-var palette from themes.py.

    Returns _DEFAULT_TOKENS for None / adaptive / auto (light defaults).
    Supports "adaptive-light", "light", "adaptive-dark", "dark", or a dict
    of CSS vars mirroring the THEME_ADAPTIVE_* shape.
    """
    from .themes import THEME_ADAPTIVE_DARK, THEME_ADAPTIVE_LIGHT

    if theme in ("dark", "adaptive-dark"):
        pal: dict = THEME_ADAPTIVE_DARK
    elif theme in ("light", "adaptive-light"):
        pal = THEME_ADAPTIVE_LIGHT
    elif isinstance(theme, dict):
        pal = theme
    else:
        return _DEFAULT_TOKENS

    t = _Tokens()
    t.bg = pal.get("--bg-primary", t.bg)
    t.node_fill = pal.get("--card-bg-from", t.node_fill)
    t.node_stroke = pal.get("--accent-1", t.node_stroke)
    t.text_fill = pal.get("--text-primary", t.text_fill)
    t.edge_stroke = pal.get("--text-secondary", t.edge_stroke)
    t.arrowhead_fill = pal.get("--text-secondary", t.arrowhead_fill)
    t.label_text = pal.get("--text-primary", t.label_text)
    return t


def _natural_size(scene: "SvgScene") -> "tuple[float, float]":
    """Return (width, height) from the scene's view_box visible bounds."""
    vb = scene.view_box
    return (vb[2], vb[3])


# Accent colors for groups — indexed by group position
_ACCENT_COLORS = [
    ("#3F7D5A", "rgba(63,125,90,0.05)"),
    ("#B7791F", "rgba(183,121,31,0.05)"),
    ("#1F3A5F", "rgba(31,58,95,0.05)"),
    ("#6B4A7A", "rgba(107,74,122,0.05)"),
]


# ── SVG path parser (for _smooth_orthogonal_path output) ─────────────────────

def _parse_path_d(d: str) -> Tuple[tuple, ...]:
    """Parse an SVG path 'd' attribute to typed command tuples.

    Handles M, L, Q, C, Z commands used by _smooth_orthogonal_path and other
    internal path generators. User source is never passed here.
    """
    if not d.strip():
        return ()

    tokens = re.findall(r'[MLQCZmlqcz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', d)
    commands: list[tuple] = []
    i = 0
    while i < len(tokens):
        letter = tokens[i]
        i += 1
        if letter.upper() == "Z":
            commands.append(("Z",))
        elif letter.upper() == "M":
            x, y = float(tokens[i]), float(tokens[i+1])
            i += 2
            commands.append(("M", x, y))
        elif letter.upper() == "L":
            x, y = float(tokens[i]), float(tokens[i+1])
            i += 2
            commands.append(("L", x, y))
        elif letter.upper() == "Q":
            x1, y1 = float(tokens[i]), float(tokens[i+1])
            x, y = float(tokens[i+2]), float(tokens[i+3])
            i += 4
            commands.append(("Q", x1, y1, x, y))
        elif letter.upper() == "C":
            x1, y1 = float(tokens[i]), float(tokens[i+1])
            x2, y2 = float(tokens[i+2]), float(tokens[i+3])
            x, y = float(tokens[i+4]), float(tokens[i+5])
            i += 6
            commands.append(("C", x1, y1, x2, y2, x, y))
        else:
            # Skip unknown
            i += 1
    return tuple(commands)


def _parse_polygon_points(pts_str: str) -> Tuple[Tuple[float, float], ...]:
    """Parse SVG polygon points string 'x,y x,y x,y' to typed tuple."""
    if not pts_str:
        return ()
    pts = []
    for pair in pts_str.strip().split():
        parts = pair.split(",")
        if len(parts) == 2:
            try:
                pts.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass
    return tuple(pts)


# ── Node shape converters ─────────────────────────────────────────────────────

def _make_node_paint(stroke_color: str, fill_color: str, stroke_w: float = 1.5) -> PaintStyle:
    return PaintStyle(
        fill=FillStyle(color=fill_color),
        stroke=StrokeStyle(color=stroke_color, width=stroke_w),
    )


def _node_scene_elements(node: Any, tokens: _Tokens, order: int = 0) -> list:
    """Convert a _Node to a list of scene elements."""
    import html as _html
    x, y = float(node.x), float(node.y)
    nw = float(node.width or 192)
    nh = float(getattr(node, "_render_h", None) or _node_render_h_approx(node))
    shape = node.shape or "rect"
    label = node.label or ""
    paint = _make_node_paint(tokens.node_stroke, tokens.node_fill, tokens.node_stroke_w)

    elements = []
    eid = f"node-{node.id}"
    import re as _re
    parent_id = getattr(node, "group", None) or ""
    # Normalize <br> → space in label for canonical data-label value
    label_canonical = _re.sub(r'<br\s*/?>', ' ', label, flags=_re.IGNORECASE).strip()
    _node_data: tuple = (
        ("node-id", node.id),
        ("semantic-id", node.id),
        ("kind", "node"),
        ("label", _html.escape(label_canonical, quote=True)),
        ("shape", shape),
        ("order", str(order)),
    ) + ((("parent-id", parent_id),) if parent_id else ())

    if shape in ("rect", "round", "stadium", "subroutine", "flag"):
        rx = {"rect": tokens.node_rx, "round": 14.0, "stadium": 50.0,
              "subroutine": 4.0, "flag": 0.0}.get(shape, tokens.node_rx)
        elements.append(SceneRoundedRect(
            element_id=eid, x=x, y=y, w=nw, h=nh, rx=rx, ry=rx,
            css_classes=("node", f"node-{shape}"),
            data_attrs=_node_data,
            paint=paint,
        ))

    elif shape == "circle":
        r = min(nw, nh) / 2
        elements.append(SceneCircle(
            element_id=eid, cx=x + nw/2, cy=y + nh/2, r=r,
            css_classes=("node", "node-circle"),
            data_attrs=_node_data,
            paint=paint,
        ))

    elif shape == "doublecircle":
        r_outer = min(nw, nh) / 2
        r_inner = r_outer - 6
        outer_paint = _make_node_paint(tokens.node_stroke, tokens.node_fill, tokens.node_stroke_w)
        inner_paint = PaintStyle(
            fill=FillStyle(color="none"),
            stroke=StrokeStyle(color=tokens.node_stroke, width=tokens.node_stroke_w),
        )
        elements.append(SceneCircle(
            element_id=eid + "-outer", cx=x + nw/2, cy=y + nh/2, r=r_outer,
            css_classes=("node", "node-doublecircle"),
            data_attrs=_node_data,
            paint=outer_paint,
        ))
        elements.append(SceneCircle(
            element_id=eid + "-inner", cx=x + nw/2, cy=y + nh/2, r=r_inner,
            paint=inner_paint,
        ))

    elif shape == "diamond":
        cx, cy = x + nw/2, y + nh/2
        pts = ((cx, y), (x + nw, cy), (cx, y + nh), (x, cy))
        elements.append(ScenePolygon(
            element_id=eid,
            points=pts,
            css_classes=("node", "node-diamond"),
            data_attrs=_node_data,
            paint=paint,
        ))

    elif shape == "hexagon":
        hw = nw * 0.25
        pts = (
            (x + hw, y), (x + nw - hw, y),
            (x + nw, y + nh/2), (x + nw - hw, y + nh),
            (x + hw, y + nh), (x, y + nh/2),
        )
        elements.append(ScenePolygon(
            element_id=eid,
            points=pts,
            css_classes=("node", "node-hexagon"),
            data_attrs=_node_data,
            paint=paint,
        ))

    elif shape in ("trapezoid", "trapezoid-alt"):
        inset = nw * 0.15
        if shape == "trapezoid":
            pts = ((x + inset, y), (x + nw, y), (x + nw - inset, y + nh), (x, y + nh))
        else:
            pts = ((x, y), (x + nw - inset, y), (x + nw, y + nh), (x + inset, y + nh))
        elements.append(ScenePolygon(
            element_id=eid,
            points=pts,
            css_classes=("node", f"node-{shape}"),
            data_attrs=_node_data,
            paint=paint,
        ))

    elif shape == "cylinder":
        # Cylinder: rect body + elliptical top/bottom caps
        cap_ry = max(8.0, nh * 0.12)
        body_paint = _make_node_paint(tokens.node_stroke, tokens.node_fill, tokens.node_stroke_w)
        cap_paint = _make_node_paint(tokens.node_stroke, tokens.node_fill, tokens.node_stroke_w)
        # Body rect
        elements.append(SceneRect(
            element_id=eid + "-body",
            x=x, y=y + cap_ry, w=nw, h=nh - 2*cap_ry,
            css_classes=("node", "node-cylinder"),
            data_attrs=_node_data,
            paint=body_paint,
        ))
        # Bottom cap (filled)
        elements.append(SceneEllipse(
            element_id=eid + "-bottom",
            cx=x + nw/2, cy=y + nh - cap_ry,
            rx=nw/2, ry=cap_ry,
            paint=cap_paint,
        ))
        # Top cap (outline only - to show the "opening")
        elements.append(SceneEllipse(
            element_id=eid + "-top",
            cx=x + nw/2, cy=y + cap_ry,
            rx=nw/2, ry=cap_ry,
            paint=_make_node_paint(tokens.node_stroke, tokens.node_fill, tokens.node_stroke_w),
        ))

    elif shape == "bar":
        # UML fork/join sync bar: solid horizontal rectangle centered vertically
        _bar_h = 8.0
        _bar_y = y + (nh - _bar_h) / 2
        elements.append(SceneRect(
            element_id=eid,
            x=x, y=_bar_y, w=nw, h=_bar_h,
            css_classes=("node", "node-bar"),
            data_attrs=_node_data,
            paint=PaintStyle(
                fill=FillStyle(color=tokens.text_fill),
                stroke=StrokeStyle(color="none", width=0),
            ),
        ))

    else:
        # Default: rounded rect
        elements.append(SceneRoundedRect(
            element_id=eid, x=x, y=y, w=nw, h=nh, rx=tokens.node_rx, ry=tokens.node_rx,
            css_classes=("node",),
            data_attrs=_node_data,
            paint=paint,
        ))

    # Label text
    label_text = label.replace("<br>", "\n").replace("<br/>", "\n")
    lines = [l.strip() for l in label_text.split("\n") if l.strip()]
    if lines:
        center_x = x + nw / 2
        total_h = len(lines) * (tokens.text_size * 1.3)
        start_y = y + nh / 2 - total_h / 2 + tokens.text_size
        scene_lines = tuple(
            SceneTextLine(
                text=line,
                x=center_x,
                y=start_y + i * tokens.text_size * 1.3,
                font_size=tokens.text_size,
                font_weight=tokens.text_weight,
                fill_color=tokens.text_fill,
            )
            for i, line in enumerate(lines)
        )
        elements.append(SceneText(
            element_id=eid + "-label",
            lines=scene_lines,
            text_anchor="middle",
            data_attrs=_node_data,
        ))

    return elements


def _node_render_h_approx(node: Any) -> float:
    """Approximate node render height without importing the full constants."""
    shape = getattr(node, "shape", "rect") or "rect"
    if shape in ("circle", "doublecircle"):
        return float(getattr(node, "width", 80) or 80)
    if shape == "diamond":
        return float(getattr(node, "width", 100) or 100)
    if shape == "hexagon":
        # Use layout-assigned height (consistent with layout engine's _node_render_h).
        # Using width here causes the polygon to exceed layout bounds and overlap siblings.
        return float(getattr(node, "height", 100) or getattr(node, "width", 100) or 100)
    base_h = float(getattr(node, "height", 42) or 42)
    return max(base_h, 42.0)


# ── Edge converters ───────────────────────────────────────────────────────────

def _marker_id_for_edge(route: dict, scene_id_hash: str) -> tuple[str, str]:
    """Return (start_marker_id, end_marker_id) for a route.

    Returns "" for no marker.
    """
    marker_id = route.get("marker_id") or ""
    has_bidir = bool(route.get("bidir"))

    if marker_id:
        end_id = f"arrow-{marker_id}-{scene_id_hash}"
    elif route.get("ah"):
        end_id = f"arrow-end-{scene_id_hash}"
    else:
        end_id = ""

    start_id = f"arrow-start-{scene_id_hash}" if has_bidir else ""
    return start_id, end_id


def _edge_scene_elements(route: dict, tokens: _Tokens, scene_id_hash: str, edge_idx: int = 0) -> list:
    """Convert a route dict to scene elements (path + arrowhead + label)."""
    elements = []

    path_d = route.get("d") or ""
    if not path_d:
        return elements

    style = route.get("style") or "solid"
    stroke_color = tokens.edge_stroke
    stroke_w = tokens.edge_stroke_w
    dasharray = ""
    if style == "dotted":
        dasharray = tokens.edge_dot_dash
    elif style == "thick":
        stroke_w = tokens.edge_thick_w

    cmds = _parse_path_d(path_d)
    if not cmds:
        return elements

    import html as _html
    src = route.get("src") or ""
    dst = route.get("dst") or ""
    edge_id = f"edge-{src}-{dst}"
    edge_label = route.get("label") or ""
    edge_style = route.get("style") or "solid"

    has_arrow = bool(route.get("ah"))
    start_marker_id, end_marker_id = _marker_id_for_edge(route, scene_id_hash)

    _edge_data: tuple = (
        ("src", src),
        ("dst", dst),
        ("label", _html.escape(edge_label, quote=True)),
        ("arrow", edge_style),
        ("relation-id", f"{src}__{dst}__{edge_idx}"),
    )
    edge_paint = PaintStyle(
        fill=FillStyle(color="none"),
        stroke=StrokeStyle(color=stroke_color, width=stroke_w, dasharray=dasharray),
    )
    elements.append(ScenePath(
        element_id=edge_id,
        commands=cmds,
        marker_start=start_marker_id if start_marker_id else "",
        marker_end=end_marker_id if end_marker_id else "",
        paint=edge_paint,
        data_attrs=_edge_data,
    ))

    # Inline arrowhead polygon (if no marker)
    ah_pts_str = route.get("ah") or ""
    if ah_pts_str and not end_marker_id:
        pts = _parse_polygon_points(ah_pts_str)
        if pts:
            ah_paint = PaintStyle(fill=FillStyle(color=tokens.arrowhead_fill))
            elements.append(ScenePolygon(
                element_id=edge_id + "-ah",
                points=pts,
                paint=ah_paint,
            ))

    # Edge label
    label = route.get("label") or ""
    if label:
        lx = float(route.get("lx") or 0)
        ly = float(route.get("ly") or 0)
        label_line = SceneTextLine(
            text=label, x=lx, y=ly + tokens.label_text_size,
            font_size=tokens.label_text_size,
            fill_color=tokens.label_text,
        )
        elements.append(SceneText(
            element_id=edge_id + "-label",
            lines=(label_line,),
            text_anchor="start",
        ))

    return elements


# ── Group (subgraph) converters ───────────────────────────────────────────────

def _group_scene_element(
    group_id: str, group: Any, bbox: tuple, accent_idx: int,
) -> SceneGroup:
    """Convert a group bbox to a SceneGroup with boundary rect + label."""
    import html as _html
    stroke_color, fill_color = _ACCENT_COLORS[accent_idx % len(_ACCENT_COLORS)]
    x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    w, h = x2 - x1, y2 - y1

    grp_label = getattr(group, "label", "") or group_id
    _grp_data: tuple = (
        ("group-id", group_id),
        ("group-label", _html.escape(grp_label, quote=True)),
    )

    boundary_paint = PaintStyle(
        fill=FillStyle(color=fill_color),
        stroke=StrokeStyle(color=stroke_color, width=1.5, dasharray="6,3"),
    )
    boundary = SceneRoundedRect(
        element_id=f"group-{group_id}-boundary",
        x=x1, y=y1, w=w, h=h, rx=6, ry=6,
        css_classes=("diagram-group",),
        data_attrs=(("group-id", group_id),),
        paint=boundary_paint,
    )

    children: list = [boundary]

    label = grp_label
    if label:
        label_line = SceneTextLine(
            text=label,
            x=x1 + 12, y=y1 + 16,
            font_size=12.0,
            font_weight=600,
            fill_color=stroke_color,
        )
        children.append(SceneText(
            element_id=f"group-{group_id}-label",
            lines=(label_line,),
            text_anchor="start",
        ))

    return SceneGroup(
        element_id=f"group-{group_id}",
        css_classes=("diagram-group-container",),
        data_attrs=_grp_data,
        children=tuple(children),
    )


# ── Marker definitions for scene ─────────────────────────────────────────────

def _build_marker_defs(routes: list, scene_id_hash: str, tokens: _Tokens) -> list:
    """Build MarkerDefinition list needed by the routes.

    Uses _marker_id_for_edge to derive IDs so they match what _edge_scene_elements
    puts on each path's marker_end/marker_start attributes.
    """
    markers = []
    seen_ids: set = set()

    for route in routes:
        has_bidir = bool(route.get("bidir"))
        start_id, end_id = _marker_id_for_edge(route, scene_id_hash)

        if end_id and end_id not in seen_ids:
            seen_ids.add(end_id)
            markers.append(MarkerDefinition(
                marker_id=end_id,
                marker_type="arrow-end",
                color=tokens.arrowhead_fill,
                size=tokens.marker_size,
                refX=tokens.marker_size,
                refY=tokens.marker_size / 2,
            ))

        if start_id and start_id not in seen_ids:
            seen_ids.add(start_id)
            markers.append(MarkerDefinition(
                marker_id=start_id,
                marker_type="arrow-start",
                color=tokens.arrowhead_fill,
                size=tokens.marker_size,
                refX=0,
                refY=tokens.marker_size / 2,
            ))

    return markers


# ── Main graph→scene converter ────────────────────────────────────────────────

def graph_to_scene(
    nodes: dict,
    edges: list,
    groups: dict,
    routes: list,
    canvas_w: int,
    canvas_h: int,
    diagram_type: str = "flowchart",
    direction: str = "TB",
    group_bboxes: "dict | None" = None,
    title: str = "",
    zoom: float = 1.0,
    tokens: "_Tokens | None" = None,
) -> SvgScene:
    """Convert positioned layout objects to an SvgScene.

    `nodes`: dict[id, _Node] with x, y, shape, label set
    `edges`: list[_Edge]
    `groups`: dict[id, _Group]
    `routes`: list of route dicts from _route_edges()
    `group_bboxes`: optional {gid: (x1, y1, x2, y2)}
    """
    t = tokens or _DEFAULT_TOKENS

    # Content hash for deterministic IDs
    content = f"{diagram_type}:{canvas_w}:{canvas_h}:{','.join(sorted(nodes.keys()))}"
    content_hash = int(hashlib.sha256(content.encode()).hexdigest(), 16)
    scene_id = make_scene_id(diagram_type, content_hash)
    scene_id_hash = hashlib.sha256(scene_id.encode()).hexdigest()[:6]

    # Apply zoom scaling to canvas dimensions for SVG output
    svg_w = float(canvas_w) * zoom
    svg_h = float(canvas_h) * zoom

    # Collect elements per layer
    boundary_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []
    overlay_elements: list = []

    # Groups → boundaries layer
    if group_bboxes:
        for acc_idx, (gid, bbox) in enumerate(group_bboxes.items()):
            if gid in groups:
                grp_elem = _group_scene_element(gid, groups[gid], bbox, acc_idx)
                boundary_elements.append(grp_elem)

    # Edges → edges layer
    route_edge_elements: list = []
    route_label_elements: list = []
    for edge_idx, route in enumerate(routes):
        els = _edge_scene_elements(route, t, scene_id_hash, edge_idx)
        for el in els:
            if isinstance(el, SceneText):
                route_label_elements.append(el)
            else:
                route_edge_elements.append(el)
    edge_elements.extend(route_edge_elements)

    # Nodes → nodes layer (skip dummy nodes)
    node_text_elements: list = []
    node_order = 0
    for nid, node in sorted(nodes.items()):  # sorted for determinism
        if getattr(node, "is_dummy", False):
            continue
        els = _node_scene_elements(node, t, node_order)
        node_order += 1
        for el in els:
            if isinstance(el, SceneText):
                node_text_elements.append(el)
            else:
                node_elements.append(el)

    # Labels layer: edge labels + node labels
    label_elements.extend(route_label_elements)
    label_elements.extend(node_text_elements)

    # Marker definitions
    marker_defs = _build_marker_defs(routes, scene_id_hash, t)

    # Title text in background layer
    bg_elements: list = []
    if title:
        bg_elements.append(SceneText(
            element_id="diagram-title",
            lines=(SceneTextLine(
                text=title, x=float(canvas_w) / 2, y=20.0,
                font_size=16.0, font_weight=700,
                fill_color=t.text_fill,
            ),),
            text_anchor="middle",
        ))

    layers: tuple = tuple(
        (name, tuple(elems)) for name, elems in [
            (LAYER_BACKGROUND, bg_elements),
            (LAYER_BOUNDARIES, boundary_elements),
            (LAYER_EDGES, edge_elements),
            (LAYER_NODES, node_elements),
            (LAYER_LABELS, label_elements),
            (LAYER_NOTES, []),
            (LAYER_OVERLAYS, overlay_elements),
        ]
    )

    return SvgScene(
        scene_id=scene_id,
        diagram_type=diagram_type,
        width=svg_w,
        height=svg_h,
        view_box=(0.0, 0.0, float(canvas_w), float(canvas_h)),
        accessibility=AccessibilityMetadata(
            title=title or diagram_type,
            description=f"Mermaid {diagram_type} diagram",
        ),
        definitions=tuple(marker_defs),
        layers=layers,
        direction=direction.upper() if direction else "",
    )


# ── FinalizedLayout → SvgScene ────────────────────────────────────────────────

def finalized_layout_to_scene(
    layout: Any,
    *,
    diagram_type: str = "flowchart",
    title: str = "",
    tokens: "_Tokens | None" = None,
    metadata: "AccessibilityMetadata | None" = None,
) -> SvgScene:
    """Convert a FinalizedLayout to an SvgScene.

    Does no geometry work — all coordinates are read directly from the
    immutable layout. Replaces graph_to_scene() on the native pipeline path.
    """
    t = tokens or _DEFAULT_TOKENS

    cw = float(layout.canvas_bounds.w)
    ch = float(layout.canvas_bounds.h)

    content = f"{diagram_type}:{cw}:{ch}:{','.join(sorted(layout.node_layouts.keys()))}"
    content_hash = int(hashlib.sha256(content.encode()).hexdigest(), 16)
    scene_id = make_scene_id(diagram_type, content_hash)
    scene_id_hash = hashlib.sha256(scene_id.encode()).hexdigest()[:6]

    bg_elements: list = []
    boundary_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []
    marker_defs: list = []
    seen_markers: set = set()

    # Title → background layer
    if title:
        bg_elements.append(SceneText(
            element_id="diagram-title",
            lines=(SceneTextLine(
                text=title, x=cw / 2, y=20.0,
                font_size=16.0, font_weight=700,
                fill_color=t.text_fill,
            ),),
            text_anchor="middle",
        ))

    # Groups → boundaries layer (rendered behind nodes)
    for acc_idx, (gid, gl) in enumerate(layout.group_layouts.items()):
        b = gl.boundary_bounds
        stroke_color, fill_color = _ACCENT_COLORS[acc_idx % len(_ACCENT_COLORS)]
        boundary_paint = PaintStyle(
            fill=FillStyle(color=fill_color),
            stroke=StrokeStyle(color=stroke_color, width=1.5, dasharray="6,3"),
        )
        children: list = [SceneRoundedRect(
            element_id=f"group-{gid}-boundary",
            x=float(b.x), y=float(b.y), w=float(b.w), h=float(b.h), rx=6, ry=6,
            css_classes=("diagram-group",),
            data_attrs=(("group-id", gid),),
            paint=boundary_paint,
        )]
        if gl.label_layout and gl.label_layout.lines and gl.label_layout.lines[0].runs:
            lbl = gl.label_layout.lines[0].runs[0].text
            if lbl:
                children.append(SceneText(
                    element_id=f"group-{gid}-label",
                    lines=(SceneTextLine(
                        text=lbl,
                        x=float(b.x) + 12, y=float(b.y) + 16,
                        font_size=t.group_text_size, font_weight=600,
                        fill_color=stroke_color,
                    ),),
                    text_anchor="start",
                ))
        boundary_elements.append(SceneGroup(
            element_id=f"group-{gid}",
            css_classes=("diagram-group-container",),
            data_attrs=(("group-id", gid),),
            children=tuple(children),
        ))

    # Nodes → nodes layer
    import re as _re_node
    import html as _html_node
    _node_order = 0
    for nid, nl in sorted(layout.node_layouts.items()):
        if nl.is_dummy:
            continue
        b = nl.outer_bounds
        x, y, nw, nh = float(b.x), float(b.y), float(b.w), float(b.h)
        shape = nl.semantic_shape or "rect"
        accent = nl.accent_color or t.node_stroke
        # External nodes use a dashed border to indicate they are outside the system boundary
        _stroke_dash = "5,3" if nl.is_external else ""
        node_paint = PaintStyle(
            fill=FillStyle(color=t.node_fill),
            stroke=StrokeStyle(color=accent, width=t.node_stroke_w, dasharray=_stroke_dash),
        )
        eid = f"node-{nid}"
        extra_css = tuple(nl.css_classes)
        # Compute normalized label: extract raw text from title_layout, strip <br>
        _tl = nl.title_layout
        _label_raw = ""
        if _tl and _tl.lines:
            _runs = _tl.lines[0].runs if _tl.lines[0].runs else ()
            _label_raw = " ".join(getattr(r, "text", "") for r in _runs)
        _label_norm = _re_node.sub(r'<br\s*/?>', ' ', _label_raw, flags=_re_node.IGNORECASE).strip()
        _parent_id = getattr(nl, "parent_group_id", None) or ""
        _node_data_attrs: tuple = (
            ("kind", "node"),
            ("label", _html_node.escape(_label_norm, quote=True)),
            ("node-id", nid),
            ("order", str(_node_order)),
            ("semantic-id", nid),
            ("shape", shape),
        ) + ((("parent-id", _parent_id),) if _parent_id else ())
        _node_order += 1

        if shape in ("rect", "round", "stadium", "subroutine", "flag"):
            rx_map = {"rect": t.node_rx, "round": 14.0, "stadium": 50.0, "subroutine": 4.0, "flag": 0.0}
            rx = rx_map.get(shape, t.node_rx)
            node_elements.append(SceneRoundedRect(
                element_id=eid, x=x, y=y, w=nw, h=nh, rx=rx, ry=rx,
                css_classes=("node", f"node-{shape}") + extra_css,
                data_attrs=_node_data_attrs,
                paint=node_paint,
            ))
        elif shape == "circle":
            r = min(nw, nh) / 2
            node_elements.append(SceneCircle(
                element_id=eid, cx=x + nw / 2, cy=y + nh / 2, r=r,
                css_classes=("node", "node-circle") + extra_css,
                data_attrs=_node_data_attrs,
                paint=node_paint,
            ))
        elif shape == "doublecircle":
            r_outer = min(nw, nh) / 2
            node_elements.append(SceneCircle(
                element_id=eid + "-outer", cx=x + nw / 2, cy=y + nh / 2, r=r_outer,
                css_classes=("node", "node-doublecircle") + extra_css,
                data_attrs=_node_data_attrs,
                paint=node_paint,
            ))
            node_elements.append(SceneCircle(
                element_id=eid + "-inner", cx=x + nw / 2, cy=y + nh / 2, r=r_outer - 6,
                paint=PaintStyle(
                    fill=FillStyle(color="none"),
                    stroke=StrokeStyle(color=accent, width=t.node_stroke_w),
                ),
            ))
        elif shape == "diamond":
            cx_, cy_ = x + nw / 2, y + nh / 2
            node_elements.append(ScenePolygon(
                element_id=eid,
                points=((cx_, y), (x + nw, cy_), (cx_, y + nh), (x, cy_)),
                css_classes=("node", "node-diamond") + extra_css,
                data_attrs=_node_data_attrs,
                paint=node_paint,
            ))
        elif shape == "hexagon":
            hw = nw * 0.25
            node_elements.append(ScenePolygon(
                element_id=eid,
                points=(
                    (x + hw, y), (x + nw - hw, y),
                    (x + nw, y + nh / 2), (x + nw - hw, y + nh),
                    (x + hw, y + nh), (x, y + nh / 2),
                ),
                css_classes=("node", "node-hexagon") + extra_css,
                data_attrs=_node_data_attrs,
                paint=node_paint,
            ))
        elif shape in ("trapezoid", "trapezoid-alt"):
            inset = nw * 0.15
            if shape == "trapezoid":
                pts = ((x + inset, y), (x + nw, y), (x + nw - inset, y + nh), (x, y + nh))
            else:
                pts = ((x, y), (x + nw - inset, y), (x + nw, y + nh), (x + inset, y + nh))
            node_elements.append(ScenePolygon(
                element_id=eid, points=pts,
                css_classes=("node", f"node-{shape}") + extra_css,
                data_attrs=_node_data_attrs,
                paint=node_paint,
            ))
        elif shape == "cylinder":
            cap_ry = max(8.0, nh * 0.12)
            node_elements.append(SceneRect(
                element_id=eid + "-body",
                x=x, y=y + cap_ry, w=nw, h=nh - 2 * cap_ry,
                css_classes=("node", "node-cylinder") + extra_css,
                data_attrs=_node_data_attrs,
                paint=node_paint,
            ))
            node_elements.append(SceneEllipse(
                element_id=eid + "-bottom",
                cx=x + nw / 2, cy=y + nh - cap_ry, rx=nw / 2, ry=cap_ry,
                paint=node_paint,
            ))
            node_elements.append(SceneEllipse(
                element_id=eid + "-top",
                cx=x + nw / 2, cy=y + cap_ry, rx=nw / 2, ry=cap_ry,
                paint=node_paint,
            ))
        elif shape == "bar":
            # UML fork/join sync bar: a solid horizontal rectangle centered vertically.
            _bar_h = 8.0
            _bar_y = y + (nh - _bar_h) / 2
            node_elements.append(SceneRect(
                element_id=eid,
                x=x, y=_bar_y, w=nw, h=_bar_h,
                css_classes=("node", "node-bar") + extra_css,
                data_attrs=_node_data_attrs,
                paint=PaintStyle(
                    fill=FillStyle(color=t.text_fill),
                    stroke=StrokeStyle(color="none", width=0),
                ),
            ))
        else:
            node_elements.append(SceneRoundedRect(
                element_id=eid, x=x, y=y, w=nw, h=nh, rx=t.node_rx, ry=t.node_rx,
                css_classes=("node",) + extra_css,
                data_attrs=_node_data_attrs,
                paint=node_paint,
            ))

        # Title text from title_layout
        if nl.title_layout and nl.title_layout.lines:
            cx_ = x + nw / 2
            lh = nl.title_layout.line_height
            start_y = y + nh / 2 - nl.title_layout.height / 2 + lh
            scene_lines = []
            for i, line in enumerate(nl.title_layout.lines):
                if not line.runs:
                    continue
                run_text = " ".join(r.text for r in line.runs)
                fs = line.runs[0].style.font_size
                fw = line.runs[0].style.font_weight
                scene_lines.append(SceneTextLine(
                    text=run_text, x=cx_, y=start_y + i * lh,
                    font_size=fs, font_weight=fw,
                    italic=line.runs[0].style.italic,
                    fill_color=t.text_fill,
                ))
            if scene_lines:
                label_elements.append(SceneText(
                    element_id=eid + "-label",
                    lines=tuple(scene_lines),
                    text_anchor="middle",
                    data_attrs=_node_data_attrs,
                ))

        # Subtitle text from subtitle_layout (e.g. C4 element descriptions)
        if nl.subtitle_layout and nl.subtitle_layout.lines:
            cx_ = x + nw / 2
            title_bottom = y + nh / 2 + (nl.title_layout.height if nl.title_layout else 0) / 2
            sub_lines = []
            sub_lh = nl.subtitle_layout.line_height
            for i, line in enumerate(nl.subtitle_layout.lines):
                if not line.runs:
                    continue
                run_text = " ".join(r.text for r in line.runs)
                fs = line.runs[0].style.font_size
                sub_lines.append(SceneTextLine(
                    text=run_text, x=cx_,
                    y=title_bottom + i * sub_lh + sub_lh,
                    font_size=fs,
                    fill_color=t.text_fill,
                ))
            if sub_lines:
                label_elements.append(SceneText(
                    element_id=eid + "-subtitle",
                    lines=tuple(sub_lines),
                    text_anchor="middle",
                    data_attrs=_node_data_attrs,
                ))

        # Member layouts (class/ER member rows)
        for mi, ml in enumerate(nl.member_layouts):
            if not ml.lines:
                continue
            for line in ml.lines:
                if not line.runs:
                    continue
                member_text = " ".join(r.text for r in line.runs)
                member_y = y + nh / 2 + t.text_size * (mi + 1) * 1.3
                label_elements.append(SceneText(
                    element_id=f"{eid}-member-{mi}",
                    lines=(SceneTextLine(
                        text=member_text, x=x + nw / 2, y=member_y,
                        font_size=t.text_size * 0.9,
                        fill_color=t.text_fill,
                    ),),
                    text_anchor="middle",
                ))

    # Edges → edges layer
    _EDGE_MARKER_STYLE = {"thick": "arrow-thick", "dotted": "arrow-open"}
    for rei, re_obj in enumerate(layout.routed_edges):
        if not re_obj.waypoints:
            continue
        pts = re_obj.waypoints
        cmds: list[tuple] = [("M", float(pts[0].x), float(pts[0].y))]
        for p in pts[1:]:
            cmds.append(("L", float(p.x), float(p.y)))

        marker_end_id = ""
        marker_start_id = ""
        if re_obj.has_marker_end:
            mid = _EDGE_MARKER_STYLE.get(re_obj.edge_style, "arrow-normal")
            marker_end_id = f"{mid}-{scene_id_hash}"
            if marker_end_id not in seen_markers:
                seen_markers.add(marker_end_id)
                marker_defs.append(MarkerDefinition(
                    marker_id=marker_end_id,
                    marker_type="arrow-end",
                    color=t.arrowhead_fill,
                    size=t.marker_size,
                    refX=t.marker_size,
                    refY=t.marker_size / 2,
                ))
        if re_obj.has_marker_start:
            marker_start_id = f"arrow-bidir-start-{scene_id_hash}"
            if marker_start_id not in seen_markers:
                seen_markers.add(marker_start_id)
                marker_defs.append(MarkerDefinition(
                    marker_id=marker_start_id,
                    marker_type="arrow-start",
                    color=t.arrowhead_fill,
                    size=t.marker_size,
                    refX=0,
                    refY=t.marker_size / 2,
                ))

        if re_obj.edge_style == "thick":
            stroke_w = t.edge_thick_w
            dasharray = ""
        elif re_obj.edge_style == "dotted":
            stroke_w = t.edge_stroke_w
            dasharray = t.edge_dot_dash
        else:
            stroke_w = t.edge_stroke_w
            dasharray = ""

        import html as _html_fe
        _edge_label_val = ""
        if re_obj.label_layout:
            _edge_label_val = _html_fe.escape(re_obj.label_layout.text or "", quote=True)
        _re_arrow = re_obj.edge_style or "solid"
        _re_rel_id = f"{re_obj.src_node_id}__{re_obj.dst_node_id}__{rei}"
        edge_elements.append(ScenePath(
            element_id=f"edge-{re_obj.src_node_id}-{re_obj.dst_node_id}-{rei}",
            commands=tuple(cmds),
            marker_start=marker_start_id,
            marker_end=marker_end_id,
            paint=PaintStyle(
                fill=FillStyle(color="none"),
                stroke=StrokeStyle(color=t.edge_stroke, width=stroke_w, dasharray=dasharray),
            ),
            data_attrs=(
                ("arrow", _re_arrow),
                ("dst", re_obj.dst_node_id),
                ("label", _edge_label_val),
                ("relation-id", _re_rel_id),
                ("src", re_obj.src_node_id),
            ),
        ))

        if re_obj.label_layout and re_obj.label_layout.text:
            lb = re_obj.label_layout.bounds
            label_elements.append(SceneText(
                element_id=f"edge-{re_obj.src_node_id}-{re_obj.dst_node_id}-{rei}-label",
                lines=(SceneTextLine(
                    text=re_obj.label_layout.text,
                    x=float(lb.x) + float(lb.w) / 2,
                    y=float(lb.y) + t.label_text_size,
                    font_size=t.label_text_size,
                    fill_color=t.label_text,
                ),),
                text_anchor="middle",
            ))

    layers: tuple = tuple(
        (name, tuple(elems)) for name, elems in [
            (LAYER_BACKGROUND, bg_elements),
            (LAYER_BOUNDARIES, boundary_elements),
            (LAYER_EDGES, edge_elements),
            (LAYER_NODES, node_elements),
            (LAYER_LABELS, label_elements),
            (LAYER_NOTES, []),
            (LAYER_OVERLAYS, []),
        ]
    )

    a11y = metadata or AccessibilityMetadata(
        title=title or diagram_type,
        description=f"Mermaid {diagram_type} diagram",
    )

    _layout_direction = (getattr(layout, "direction", None) or "").upper()
    return SvgScene(
        scene_id=scene_id,
        diagram_type=diagram_type,
        direction=_layout_direction,
        width=cw,
        height=ch,
        view_box=(0.0, 0.0, cw, ch),
        accessibility=a11y,
        definitions=tuple(marker_defs),
        layers=layers,
    )
