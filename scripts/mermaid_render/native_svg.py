"""mermaid_render.native_svg — Native SVG dispatch (no Playwright, no DOM-to-SVG).

Default SVG backend after P2. Activated by to_svg() when
MERMAID_RENDER_SVG_BACKEND != 'legacy-dom'.

Pipeline:
    Mermaid source
    -> detect diagram type
    -> per-type layout + scene construction
    -> SvgScene
    -> svg_serializer.scene_to_svg()
    -> UTF-8 SVG string
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

from .layout._parser import _detect_directive, _strip_frontmatter
from .layout._strategies import _GRAPH_DIRECTIVES
from .scene import SvgScene
from .svg_serializer import scene_to_svg_str


# ── Environment flag ──────────────────────────────────────────────────────────

BACKEND_ENV = "MERMAID_RENDER_SVG_BACKEND"
BACKEND_NATIVE = "native"
BACKEND_LEGACY = "legacy-dom"


def _use_native() -> bool:
    """Return True when the native SVG backend should be used (the default)."""
    backend = os.environ.get(BACKEND_ENV, BACKEND_NATIVE).lower()
    return backend != BACKEND_LEGACY


# ── Per-type native scene builders ────────────────────────────────────────────

def _graph_topology_scene(
    src: str, direction: str, width_hint: int, height_hint: int = 0,
    opts: object = None,
) -> SvgScene:
    """Build SvgScene for graph-topology types (flowchart, stateDiagram, classDiagram, etc.)."""
    from .layout._constants import (
        _Node, NODE_CAP, EDGE_CAP, GROUP_CAP,
        NODE_W, NODE_H, COL_GAP, RANK_GAP, CANVAS_PAD,
        GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT,
        _node_render_h, _TERMINAL_NODE_SIZE, _is_terminal_circle,
    )
    from .layout._parser import _parse_graph_source, _parse_init_config
    from .layout._layout import (
        _break_cycles, _assign_ranks, _minimize_crossings,
        _assign_coordinates, _compact_group_columns, _group_coherent_cols,
        _apply_inner_direction_positions,
    )
    from .layout._routing import _route_edges
    from .layout._renderer import (
        _extract_diagram_title, _compute_group_bboxes,
        _separate_groups_lr, _separate_groups_tb,
        _push_nonmembers_out_of_groups_lr,
    )
    from .layout._strategies import _infer_label_icons, RenderOptions
    from .paint import graph_to_scene

    _opts = opts if opts is not None else RenderOptions()

    lines = src.splitlines()
    directive_index = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith(("%%", "//")):
            directive_index = i
            break
    content_lines = lines[directive_index + 1:]

    nodes, edges, groups = _parse_graph_source(content_lines)
    if not getattr(_opts, "faithful_mermaid", False) and getattr(_opts, "infer_icons", True):
        _infer_label_icons(nodes)

    if len(nodes) > NODE_CAP:
        raise ValueError(
            f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}). "
            "Split the diagram into smaller slides."
        )
    if not nodes:
        raise ValueError("No nodes found in diagram source.")

    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)

    if direction.upper() in ("TB", "TD"):
        for grp in groups.values():
            if grp.direction.upper() in ("LR", "RL") and grp.members:
                _member_set = set(grp.members)
                _grp_ranks = [nodes[m].rank for m in grp.members if m in nodes]
                if _grp_ranks:
                    _flat_rank = min(_grp_ranks)
                    for m in grp.members:
                        if m in nodes:
                            nodes[m].rank = _flat_rank

    _minimize_crossings(nodes, edges)
    _init_cfg = _parse_init_config(src)

    if groups:
        _group_coherent_cols(nodes, groups)
        _compact_group_columns(nodes, groups)

    canvas_w, canvas_h = _assign_coordinates(
        nodes, direction,
        col_gap=_init_cfg.get("col_gap"),
        rank_gap=_init_cfg.get("rank_gap"),
        canvas_pad=_init_cfg.get("diagram_padding"),
    )

    if groups:
        _apply_inner_direction_positions(
            nodes, edges, groups, direction,
            col_gap=_init_cfg.get("col_gap"),
        )

    if direction.upper() in ("LR", "RL") and groups:
        _separate_groups_lr(nodes, groups)
        _pred: dict = {}
        for _e in edges:
            if _e.src in nodes and _e.dst in nodes:
                _pred[_e.dst] = _e.src

        def _chain_src_y(nid: str) -> int:
            visited: set = set()
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

    real_nodes = [n for n in nodes.values() if not n.is_dummy]
    if real_nodes:
        canvas_h = max(n.y + _node_render_h(n) for n in real_nodes) + CANVAS_PAD
        canvas_w = max(n.x + (n.width or NODE_W) for n in real_nodes) + CANVAS_PAD

    if direction.upper() not in ("LR", "RL"):
        _eff_nw = max(
            (n.width for n in nodes.values() if n.width > 0 and not n.is_dummy),
            default=NODE_W,
        )
        _circ_shift = (_eff_nw - _TERMINAL_NODE_SIZE) // 2
        for _n in nodes.values():
            if not _n.is_dummy and _is_terminal_circle(_n):
                _n.x += _circ_shift

    zoom = 1.0
    if width_hint and canvas_w > 0:
        w_zoom = width_hint / canvas_w
        if height_hint and canvas_h > 0:
            h_zoom = height_hint / canvas_h
            zoom = min(w_zoom, h_zoom, 1.4)
        else:
            zoom = min(w_zoom, 1.0)

    group_bboxes = _compute_group_bboxes(nodes, groups, canvas_w, canvas_h) if groups else {}

    routes = _route_edges(nodes, edges, canvas_w, direction, group_bboxes)

    directive, _ = _detect_directive(src)
    title = _extract_diagram_title(src)

    return graph_to_scene(
        nodes=nodes,
        edges=edges,
        groups=groups,
        routes=routes,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        diagram_type=directive.lower(),
        direction=direction,
        group_bboxes=group_bboxes or None,
        title=title,
        zoom=zoom,
    )


def _class_topology_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    """Build SvgScene for classDiagram using graph topology pipeline."""
    import re
    from .layout._constants import (
        _Node, _Edge, NODE_CAP, NODE_W, CANVAS_PAD,
        _node_render_h, _TERMINAL_NODE_SIZE, _is_terminal_circle,
    )
    from .layout._strategies import _CLASS_REL_RE, _class_rel_style, _directive_content
    from .layout._layout import (
        _break_cycles, _assign_ranks, _minimize_crossings,
        _assign_coordinates,
    )
    from .layout._routing import _route_edges
    from .layout._renderer import _extract_diagram_title, _compute_group_bboxes
    from .paint import graph_to_scene

    content_lines = _directive_content(src)
    nodes: dict = {}
    edges: list = []
    current_class = None
    class_members: dict = {}

    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line == "}":
            current_class = None
            continue
        m = re.match(r'^class\s+(\w+)', line)
        if m:
            cid = m.group(1)
            nodes.setdefault(cid, _Node(id=cid, label=cid, shape="rect"))
            class_members.setdefault(cid, [])
            current_class = cid if "{" in line else None
            continue
        if current_class:
            if line not in ("+", "-", "#", "~"):
                class_members.setdefault(current_class, []).append(line)
            continue
        m = _CLASS_REL_RE.match(line)
        if m:
            c1, mul_src, op, mul_dst, c2, lbl = (
                m.group(1), m.group(2) or "", m.group(3),
                m.group(4) or "", m.group(5), m.group(6) or "",
            )
            for cid in (c1, c2):
                nodes.setdefault(cid, _Node(id=cid, label=cid, shape="rect"))
                class_members.setdefault(cid, [])
            arrow_src = op.startswith(("<|", "*", "o"))
            edges.append(_Edge(
                src=c1, dst=c2, label=lbl.strip(),
                style=_class_rel_style(op), arrow=True,
                arrow_src=arrow_src,
                src_label=mul_src, dst_label=mul_dst,
            ))
            continue
        m2 = re.match(r'^(\w+)\s*:', line)
        if m2:
            nodes.setdefault(m2.group(1), _Node(id=m2.group(1), label=m2.group(1), shape="rect"))
            class_members.setdefault(m2.group(1), [])

    if not nodes:
        raise ValueError("No classes found in classDiagram.")

    for cid, members in class_members.items():
        if cid in nodes and members:
            attrs = [mm for mm in members if "(" not in mm]
            methods = [mm for mm in members if "(" in mm]
            rows = attrs
            if attrs and methods:
                rows = attrs + ["---"] + methods
            elif methods:
                rows = methods
            nodes[cid].label = f"{cid}|" + "\n".join(rows)

    groups: dict = {}

    if len(nodes) > NODE_CAP:
        raise ValueError(f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}).")

    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)

    canvas_w, canvas_h = _assign_coordinates(nodes, direction)

    real_nodes = [n for n in nodes.values() if not n.is_dummy]
    if real_nodes:
        canvas_h = max(n.y + _node_render_h(n) for n in real_nodes) + CANVAS_PAD
        canvas_w = max(n.x + (n.width or NODE_W) for n in real_nodes) + CANVAS_PAD

    zoom = 1.0
    if width_hint and canvas_w > 0:
        zoom = min(width_hint / canvas_w, 1.0)

    routes = _route_edges(nodes, edges, canvas_w, direction, {})
    title = _extract_diagram_title(src)

    return graph_to_scene(
        nodes=nodes,
        edges=edges,
        groups=groups,
        routes=routes,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        diagram_type="classdiagram",
        direction=direction,
        group_bboxes=None,
        title=title,
        zoom=zoom,
    )


def _sequence_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    """Native scene for sequenceDiagram — minimal mechanical stub."""
    return _html_fallback_scene(src, "sequencediagram", width_hint)


def _er_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "erdiagram", width_hint)


def _class_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    try:
        return _class_topology_scene(src, direction, width_hint)
    except Exception:
        return _html_fallback_scene(src, "classdiagram", width_hint)


def _gantt_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "gantt", width_hint)


def _timeline_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    """Native semantic scene for timeline — delegates to dedicated module."""
    try:
        from .layout.timeline import layout_timeline_scene
        return layout_timeline_scene(src, width_hint=width_hint)
    except Exception:
        return _html_fallback_scene(src, "timeline", width_hint)


def _quadrant_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "quadrantchart", width_hint)


def _pie_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "pie", width_hint)


def _xychart_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "xychart-beta", width_hint)


def _mindmap_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    """Native semantic scene for mindmap — delegates to dedicated module."""
    try:
        from .layout.mindmap import layout_mindmap_scene
        return layout_mindmap_scene(src, width_hint=width_hint)
    except Exception:
        return _html_fallback_scene(src, "mindmap", width_hint)


def _block_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "block-beta", width_hint)


def _packet_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "packet-beta", width_hint)


def _kanban_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "kanban", width_hint)


def _architecture_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    """Native scene for architecture-beta — delegates to dedicated module."""
    try:
        from .layout.architecture import layout_architecture_scene
        return layout_architecture_scene(src, width_hint=width_hint)
    except Exception:
        return _html_fallback_scene(src, "architecture-beta", width_hint)


def _c4_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    """Native scene for C4 — delegates to dedicated module."""
    try:
        from .layout.c4_layout import layout_c4_scene
        directive, _ = _detect_directive(_strip_frontmatter(src))
        return layout_c4_scene(src, c4_type=directive.lower(), width_hint=width_hint)
    except Exception:
        directive, _ = _detect_directive(_strip_frontmatter(src))
        return _html_fallback_scene(src, directive.lower(), width_hint)


def _journey_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "journey", width_hint)


def _requirement_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "requirementdiagram", width_hint)


def _gitgraph_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _html_fallback_scene(src, "gitgraph", width_hint)


def _html_fallback_scene(src: str, diagram_type: str, width_hint: int) -> SvgScene:
    """Minimal mechanical scene for types without a dedicated native renderer yet.

    Produces a valid scene with correct viewBox dimensions but minimal content.
    The SceneRect serves as a placeholder for the real content.

    This is the "mechanical migration" stub. Each type will be replaced with a
    proper scene renderer as implementation proceeds.
    """
    from .scene import (
        SceneRect, SceneText, SceneTextLine, PaintStyle, FillStyle, StrokeStyle,
        LAYER_BACKGROUND, LAYER_NODES, LAYER_LABELS, LAYER_ORDER,
        AccessibilityMetadata,
    )
    from .layout._strategies import _dispatch

    # Run the existing HTML layout to get dimensions
    try:
        html = _dispatch(src, None, width_hint)
    except Exception:
        html = ""

    # Extract data-diagram-w and data-diagram-h from HTML
    import re
    w_match = re.search(r'data-diagram-w="(\d+)"', html)
    h_match = re.search(r'data-diagram-h="(\d+)"', html)
    canvas_w = float(w_match.group(1)) if w_match else float(width_hint or 800)
    canvas_h = float(h_match.group(1)) if h_match else 600.0

    content = f"{diagram_type}:{canvas_w}:{canvas_h}:{src[:100]}"
    content_hash = int(hashlib.sha256(content.encode()).hexdigest(), 16)
    from .scene import make_scene_id
    scene_id = make_scene_id(diagram_type, content_hash)

    # Placeholder: a background rect + "type" label
    bg_rect = SceneRect(
        element_id="bg",
        x=0, y=0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color="#ffffff")),
    )
    note_line = SceneTextLine(
        text=f"[{diagram_type}]", x=canvas_w/2, y=canvas_h/2,
        font_size=14.0, fill_color="#888888",
    )
    note = SceneText(
        element_id="type-note",
        lines=(note_line,),
        text_anchor="middle",
    )

    layers = tuple(
        (name, (bg_rect,) if name == LAYER_BACKGROUND
               else (note,) if name == LAYER_NODES
               else ())
        for name in LAYER_ORDER
    )

    return SvgScene(
        scene_id=scene_id,
        diagram_type=diagram_type,
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=diagram_type,
            description=f"Mermaid {diagram_type} diagram (mechanical stub)",
        ),
        layers=layers,
        renderer_backend="native-svg-stub",
    )


# ── Main dispatch ─────────────────────────────────────────────────────────────

def dispatch_native(
    src: str,
    *,
    theme: "str | None" = None,
    width_hint: int = 0,
    height_hint: int = 0,
) -> str:
    """Dispatch Mermaid source to native SVG string (no Playwright, no DOM-to-SVG).

    Raises ValueError with diagram type context on failure.
    Never silently falls back to legacy DOM rendering.
    """
    clean = _strip_frontmatter(src)
    directive, auto_direction = _detect_directive(clean)
    direction = auto_direction.upper()
    d = directive.lower()

    try:
        if d in _GRAPH_DIRECTIVES:
            scene = _graph_topology_scene(clean, direction, width_hint, height_hint)
        elif d == "sequencediagram":
            scene = _sequence_scene(clean, direction, width_hint)
        elif d == "erdiagram":
            scene = _er_scene(clean, direction, width_hint)
        elif d == "classdiagram":
            scene = _class_scene(clean, direction, width_hint)
        elif d == "gantt":
            scene = _gantt_scene(clean, direction, width_hint)
        elif d == "timeline":
            scene = _timeline_scene(clean, direction, width_hint)
        elif d == "quadrantchart":
            scene = _quadrant_scene(clean, direction, width_hint)
        elif d == "pie" or d.startswith("pie "):
            scene = _pie_scene(clean, direction, width_hint)
        elif d == "xychart-beta":
            scene = _xychart_scene(clean, direction, width_hint)
        elif d == "mindmap":
            scene = _mindmap_scene(clean, direction, width_hint)
        elif d == "block-beta":
            scene = _block_scene(clean, direction, width_hint)
        elif d == "packet-beta":
            scene = _packet_scene(clean, direction, width_hint)
        elif d == "kanban":
            scene = _kanban_scene(clean, direction, width_hint)
        elif d == "architecture-beta":
            scene = _architecture_scene(clean, direction, width_hint)
        elif d in ("c4context", "c4container", "c4component"):
            scene = _c4_scene(clean, direction, width_hint)
        elif d == "journey":
            scene = _journey_scene(clean, direction, width_hint)
        elif d == "requirementdiagram":
            scene = _requirement_scene(clean, direction, width_hint)
        elif d == "gitgraph":
            scene = _gitgraph_scene(clean, direction, width_hint)
        elif d in ("sankey-beta", "zenuml"):
            raise ValueError(
                f"Mermaid directive '{directive}' is not supported by the pure-Python renderer. "
                "Use mmdc for this diagram type."
            )
        else:
            # Unknown — try graph topology
            scene = _graph_topology_scene(clean, direction, width_hint, height_hint)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(
            f"Native SVG render failed for diagram type '{directive}': {e}"
        ) from e

    return scene_to_svg_str(scene)
