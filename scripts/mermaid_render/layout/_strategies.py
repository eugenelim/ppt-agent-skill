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
        RoutedEdge, SequenceCompileResult, SequenceGeometry,
        SequenceValidationResult, ValidationResult, LayoutGraph,
    )



from ._constants import (
    _Node, _Edge, _Group, _marker_kind,
    NODE_CAP, EDGE_CAP, GROUP_CAP,
    NODE_W, NODE_H, COL_GAP, CANVAS_PAD,
    _LABEL_ICON_KEYWORDS, _KNOWN_DIRECTIVES, _GRAPH_DIRECTIVES,
    CardinalityEnd, Maximum, Minimum,
    _node_render_h, _load_icon,
)
from ._parser import (
    _parse_graph_source, _detect_directive, _strip_frontmatter,
    _directive_content,
)
from ._layout import (
    _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates,
    _compact_group_columns, _group_coherent_cols,
)
from ._routing import _route_edges, _arrowhead, _finalize_self_loop_offsets
from ._c4 import _render_c4_fragment, C4Item, C4Relationship, C4Boundary
from ._renderer import (
    _render_graph_fragment,
    _extract_diagram_title, _render_metadata_chip,
    render_finalized,
)
from .requirement import _parse_attr_value  # noqa: F401 — imported for downstream compatibility
# ── imports from split modules ───────────────────────────────────────────────
from ._pipeline import (
    RenderOptions,
    FlowchartSemantics,
    _infer_label_icons,
    _compile_flowchart,
    _render_legend_from_layout,
    _make_text_layout_ir,
    _build_node_layouts_ir,
    _build_routed_edges_ir,
    _clip_cross_scope_exit_waypoints,
    parse_flowchart_semantics,
    build_flowchart_layout_graph,
    layout_flowchart_with_elk,
    enrich_flowchart_finalized_layout,
    layout_flowchart_with_python_fallback,
    validate_flowchart_layout,
)
from ._diagram_types import (
    _layout_gantt,
    _layout_timeline,
    _layout_quadrant,
    _layout_pie,
    _layout_sankey,
    _layout_xychart,
    _layout_mindmap,
    _layout_block,
    _layout_packet,
    _layout_kanban,
    _layout_c4,
    _layout_journey,
    _layout_gitgraph,
    _ARCH_SVC_RE,
    _ARCH_GRP_RE,
    _ARCH_JCT_RE,
    _ARCH_EDGE_RE,
    _PIE_ACCENTS,
    _tl_branch_height,
    _TL_LABEL_GAP,
    _TL_LABEL_H,
    _TL_CARD_H,
    _TL_CARD_GAP,
    _TL_CARD_PAD,
    _TL_MARKER_R,
    _TL_SECTION_COLORS,
)


# ── graph topology strategy ──────────────────────────────────────────────────

def _layout_graph_topology(
    src: str, direction: str, width_hint: int, height_hint: int = 0,
    style_overrides: str = "",
    opts: "RenderOptions | None" = None,
) -> str:
    """Produce the HTML fragment for flowchart/graph/stateDiagram sources.

    Delegates geometry to _compile_flowchart, serializes via render_finalized.
    """
    _opts = opts if opts is not None else RenderOptions()

    compiled = _compile_flowchart(
        src, width_hint, _opts,
        direction_override=direction,
        height_hint=height_hint,
        style_overrides=style_overrides,
    )  # options= accepted as positional arg
    layout = compiled.layout
    canvas_w = int(layout.canvas_bounds.w)
    canvas_h = int(layout.canvas_bounds.h)

    # Scale to fit width/height constraints via CSS zoom.
    zoom = 1.0
    if width_hint and canvas_w > 0:
        w_zoom = width_hint / canvas_w
        if height_hint and canvas_h > 0:
            h_zoom = height_hint / canvas_h
            zoom = min(w_zoom, h_zoom, 1.4)
        else:
            zoom = min(w_zoom, 1.0)

    # Core fragment from render_finalized (not _render_graph_fragment)
    fragment = render_finalized(layout, faithful=_opts.faithful_mermaid)

    # Apply zoom + style via a wrapper div when needed
    zoom_css = f" zoom:{zoom:.4f};" if abs(zoom - 1.0) > 0.005 else ""
    extra_style = (" " + style_overrides.strip()) if style_overrides else ""
    if zoom_css or extra_style:
        fragment = (
            f'<div class="diagram-zoom-wrapper"'
            f' style="display:contents;{zoom_css}{extra_style}">'
            f'{fragment}</div>'
        )

    # Metadata chip and legend
    directive, _ = _detect_directive(src)
    title = _extract_diagram_title(src)
    meta_html = _render_metadata_chip(directive, title)
    _show_legend = _opts.inferred_legend and not _opts.faithful_mermaid
    legend_html = _render_legend_from_layout(layout) if _show_legend else ""

    if legend_html:
        return (
            '<div class="diagram-wrapper" style="'
            'display:flex; flex-direction:column; '
            'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
            f'{meta_html}{fragment}'
            f'{legend_html}'
            '</div>'
        )
    if meta_html:
        return (
            '<div class="diagram-wrapper" style="'
            'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
            f'{meta_html}{fragment}'
            '</div>'
        )
    return fragment


# ── imports from sequence compilation module ─────────────────────────────────
from ._sequence_compile import (
    # Arrow-spec helpers
    _emit_arrow_or_diagnostic,
    _cx_or_diagnostic,
    _emit_message_or_skip,
    # Sequence regex patterns
    _SEQ_PART_RE,
    _SEQ_MSG_RE,
    _SEQ_BLOCK_RE,
    _SEQ_END_RE,
    _SEQ_ACTIVATE_RE,
    _SEQ_SKIP_RE,
    _SEQ_CREATE_RE,
    _SEQ_DESTROY_RE,
    _SEQ_NOTE_RE,
    _SEQ_ELSE_RE,
    # Box helpers
    _BOX_FUNC_COLOR_RE,
    _BOX_SIMPLE_RE,
    _CSS_NAMED_COLORS,
    _parse_box_color_label,
    # Core sequence layout
    _layout_lifeline,
    # Shared-compiler pipeline (parse → compile geometry → paint html/scene)
    parse_sequence_semantics,
    compile_sequence_geometry,
    sequence_geometry_to_html,
    sequence_geometry_to_scene,
    # Compile-once entry point
    compile_sequence,
    # Geometry validation
    _validate_sequence_geometry,
    validate_sequence_geometry,
)


# ── T2: erDiagram ─────────────────────────────────────────────────────────────

# Relationship line: entity names may contain hyphens (e.g. LINE-ITEM)
_ER_REL_RE = re.compile(
    r'^(?P<e1>[\w-]+)\s+'
    r'(?P<card_src>[|o}{]{1,2})'
    r'(?P<line>-{1,2}|\.{1,2})'
    r'(?P<card_dst>[|o}{]{1,2})'
    r'\s+(?P<e2>[\w-]+)\s*:\s*(?P<lbl>.*)$'
)
# Entity block opening: supports hyphens (LINE-ITEM { ... })
_ER_ENTITY_RE = re.compile(r'^([\w-]+)\s*\{')
# Attribute row inside entity block: type name [PK|FK|UK] ["comment"]
_ER_ATTR_RE = re.compile(
    r'^(?P<type>\S+)\s+(?P<name>\S+)'
    r'(?:\s+(?P<constraint>PK|FK|UK))?'
    r'(?:\s+"(?P<comment>[^"]*)")?'
    r'\s*$'
)
# Token → CardinalityEnd (character-set rule, side-independent)
def _to_cardinality_end(tok: str) -> CardinalityEnd:
    """Parse a cardinality token using the character-set rule.

    ``{`` or ``}`` → maximum=MANY; else maximum=ONE.
    ``o``           → minimum=ZERO; else minimum=ONE.

    This rule is symmetric for left-side and right-side tokens.
    """
    maximum = Maximum.MANY if any(c in tok for c in "{}") else Maximum.ONE
    minimum = Minimum.ZERO if "o" in tok else Minimum.ONE
    return CardinalityEnd(minimum=minimum, maximum=maximum)


# Entity box geometry constants (px)
_ER_HDR_H = 34    # entity name header height
_ER_ROW_H = 22    # attribute row height
_ER_BOT_PAD = 8   # bottom padding below last attribute row

# Glyph geometry constants (px)
_ER_GLYPH_HW = 10.0    # half-width of bars / crow's foot spread
_ER_GLYPH_CIRC_R = 4.5  # radius of the zero-cardinality circle
_ER_FOOT_CONV = 12.0    # crow's foot convergence offset from boundary
_ER_BAR1 = 6.0          # first bar offset (max=ONE)
_ER_BAR2_DELTA = 6.0    # second bar offset past max symbol
_ER_CIRC_DELTA = 8.0    # circle offset past max symbol


def _er_entity_h(n_attrs: int) -> int:
    """Pixel height of an entity box with n_attrs attribute rows."""
    if n_attrs == 0:
        return max(NODE_H, _ER_HDR_H + _ER_BOT_PAD)
    return _ER_HDR_H + 1 + n_attrs * _ER_ROW_H + _ER_BOT_PAD


def _er_rect_edge_pt(
    cx: float, cy: float, w: float, h: float, vx: float, vy: float
) -> tuple[float, float]:
    """Point on the boundary of a rect (cx+-w/2, cy+-h/2) in direction (vx, vy).

    Finds the smallest t > 0 where (cx + vx*t, cy + vy*t) hits a face of the
    rectangle.  Returns the centre when direction is zero (degenerate case).
    """
    hw, hh = w / 2.0, h / 2.0
    ts: list[float] = []
    if vx > 1e-9:
        ts.append(hw / vx)
    elif vx < -1e-9:
        ts.append(-hw / vx)
    if vy > 1e-9:
        ts.append(hh / vy)
    elif vy < -1e-9:
        ts.append(-hh / vy)
    t = min((c for c in ts if c > 0.0), default=0.0)
    return cx + vx * t, cy + vy * t


def _er_glyph_reserve(end: CardinalityEnd) -> float:
    """Pixels to reserve at the card boundary for the cardinality glyph."""
    max_ext = _ER_FOOT_CONV if end.maximum == Maximum.MANY else _ER_BAR1
    if end.minimum == Minimum.ONE:
        return max_ext + _ER_BAR2_DELTA + 2.0
    else:
        return max_ext + _ER_CIRC_DELTA + _ER_GLYPH_CIRC_R + 2.0


def _render_crow_foot(
    x: float, y: float, dx: float, dy: float, end: CardinalityEnd, color: str
) -> list[str]:
    """SVG strings for the cardinality glyph at card boundary point (x, y).

    ``(dx, dy)`` is the outward direction from entity toward the other entity.

    Glyph structure (from entity boundary outward along the edge):
      1. Maximum symbol: crow's foot (MANY) or bar (ONE) — closest to entity.
      2. Minimum symbol: bar (ONE) or circle (ZERO) — further along the edge.

    Crow's foot orientation: tines at the entity boundary, convergence on the
    line (standard Crow's Foot notation — feet touch the entity).
    """
    import math as _math
    L = _math.hypot(dx, dy)
    if L < 1e-9:
        return []
    tx, ty = dx / L, dy / L   # outward tangent
    nx, ny = -ty, tx            # normal (perpendicular)
    hw = _ER_GLYPH_HW
    parts: list[str] = []

    # Maximum symbol
    if end.maximum == Maximum.MANY:
        # Crow's foot: three lines spread at entity boundary → convergence outward
        conv_x = x + tx * _ER_FOOT_CONV
        conv_y = y + ty * _ER_FOOT_CONV
        for spread in (-hw, 0.0, hw):
            toe_x = x + nx * spread
            toe_y = y + ny * spread
            parts.append(
                f'<line x1="{toe_x:.1f}" y1="{toe_y:.1f}" '
                f'x2="{conv_x:.1f}" y2="{conv_y:.1f}" '
                f'stroke="{color}" stroke-width="1.5"/>'
            )
        max_ext = _ER_FOOT_CONV
    else:
        # Single bar perpendicular to edge at _ER_BAR1 from boundary
        bx = x + tx * _ER_BAR1
        by = y + ty * _ER_BAR1
        parts.append(
            f'<line x1="{bx - nx * hw:.1f}" y1="{by - ny * hw:.1f}" '
            f'x2="{bx + nx * hw:.1f}" y2="{by + ny * hw:.1f}" '
            f'stroke="{color}" stroke-width="1.5"/>'
        )
        max_ext = _ER_BAR1

    # Minimum symbol (further from entity than maximum)
    if end.minimum == Minimum.ONE:
        b2x = x + tx * (max_ext + _ER_BAR2_DELTA)
        b2y = y + ty * (max_ext + _ER_BAR2_DELTA)
        parts.append(
            f'<line x1="{b2x - nx * hw:.1f}" y1="{b2y - ny * hw:.1f}" '
            f'x2="{b2x + nx * hw:.1f}" y2="{b2y + ny * hw:.1f}" '
            f'stroke="{color}" stroke-width="1.5"/>'
        )
    else:
        cx_ = x + tx * (max_ext + _ER_CIRC_DELTA)
        cy_ = y + ty * (max_ext + _ER_CIRC_DELTA)
        parts.append(
            f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="{_ER_GLYPH_CIRC_R:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="1.5"/>'
        )
    return parts


def _graph_from_content_nodes(
    nodes: dict[str, _Node],
    edges: list[_Edge],
    groups: dict[str, _Group],
    width_hint: int,
) -> str:
    if len(nodes) > NODE_CAP:
        raise ValueError(f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}).")
    if len(edges) > EDGE_CAP:
        raise ValueError(f"Cap exceeded: {len(edges)} edges (cap {EDGE_CAP}).")
    if len(groups) > GROUP_CAP:
        raise ValueError(f"Cap exceeded: {len(groups)} groups/boundaries (cap {GROUP_CAP}).")
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)
    canvas_w, canvas_h = _assign_coordinates(nodes)
    zoom = 1.0
    if width_hint and canvas_w > 0 and canvas_w > width_hint:
        zoom = width_hint / canvas_w
    return _render_graph_fragment(nodes, edges, groups, canvas_w, canvas_h, zoom=zoom)


# ── T2: classDiagram ──────────────────────────────────────────────────────────

_CLASS_REL_RE = re.compile(
    r'^(\w+)\s*(?:"([^"]*)"\s*)?'
    r'(<\|--|<\|\.\.|\.\.>\||\.\.\|>|\|>|\*--|--\*|o--|--o|-->|\.\.>|\.\.|\|\|)'
    r'\s*(?:"([^"]*)"\s*)?(\w+)(?:\s*:\s*(.*))?$'
)

def _class_rel_style(op: str) -> str:
    """Map a class relationship operator to an _Edge style value.

    Kept for backward compatibility with tests that import this function.
    New code should use _class_rel_markers() which returns MarkerSpec objects.
    """
    is_dashed = ".." in op
    if "<|" in op or "|>" in op:
        base = "cls-inherit"
    elif "*" in op:
        base = "cls-composition"
    elif "o" in op:
        base = "cls-aggregation"
    else:
        base = "cls-dep"
    return base + ("-dotted" if is_dashed else "")


def _class_rel_markers(op: str) -> "tuple":
    """Map a Mermaid classDiagram operator to (source_spec, target_spec, line_style).

    Returns:
        source_spec:  MarkerSpec for the source (left/A) endpoint.
        target_spec:  MarkerSpec for the target (right/B) endpoint.
        line_style:   "cls-solid" or "cls-dotted".

    Operator → marker mapping:
        <|--  / <|..   → HOLLOW_TRIANGLE @ SOURCE
        *--             → FILLED_DIAMOND  @ SOURCE
        --*             → FILLED_DIAMOND  @ TARGET
        o--             → HOLLOW_DIAMOND  @ SOURCE
        --o             → HOLLOW_DIAMOND  @ TARGET
        |>              → HOLLOW_TRIANGLE @ TARGET (right-side inheritance)
        ..|>            → HOLLOW_TRIANGLE @ TARGET, dotted (realization)
        --> / ..>       → OPEN_ARROW      @ TARGET
        .. / ||         → OPEN_ARROW      @ TARGET  (plain/association lines)
        ..>|            → OPEN_ARROW      @ TARGET, dotted (fallback)
    """
    from ._geometry import MarkerKind as _MK, MarkerSpec as _MS
    is_dashed = ".." in op
    line_style = "cls-dotted" if is_dashed else "cls-solid"
    NONE_SRC = _MS(kind=_MK.NONE, end="SOURCE")
    NONE_TGT = _MS(kind=_MK.NONE, end="TARGET")

    # Source-end markers (left / A-end)
    if op.startswith("<|"):          # <|--, <|..
        return (_MS(kind=_MK.HOLLOW_TRIANGLE, end="SOURCE", clearance=12.0), NONE_TGT, line_style)
    if op.startswith("*"):           # *--
        return (_MS(kind=_MK.FILLED_DIAMOND, end="SOURCE", clearance=12.0), NONE_TGT, line_style)
    if op.startswith("o"):           # o--
        return (_MS(kind=_MK.HOLLOW_DIAMOND, end="SOURCE", clearance=12.0), NONE_TGT, line_style)

    # Target-end markers (right / B-end)
    if op.endswith("*"):             # --*
        return (NONE_SRC, _MS(kind=_MK.FILLED_DIAMOND, end="TARGET", clearance=12.0), line_style)
    if op.endswith("o"):             # --o
        return (NONE_SRC, _MS(kind=_MK.HOLLOW_DIAMOND, end="TARGET", clearance=12.0), line_style)
    if op.endswith("|>") or op == "|>":   # ..|>, |>
        return (NONE_SRC, _MS(kind=_MK.HOLLOW_TRIANGLE, end="TARGET", clearance=12.0), line_style)

    # Default: open arrow at target (-->, ..>, .., ||, ..>|, etc.)
    return (NONE_SRC, _MS(kind=_MK.OPEN_ARROW, end="TARGET", clearance=9.0), line_style)


def _layout_class(src: str, direction: str, width_hint: int) -> str:
    """classDiagram: classes as nodes, relationships as edges (graph topology reuse)."""
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    current_class: Optional[str] = None
    _class_members: dict[str, list[str]] = {}  # cid → member lines
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line == "}":
            current_class = None; continue
        m = re.match(r'^class\s+(\w+)', line)
        if m:
            cid = m.group(1)
            nodes.setdefault(cid, _Node(id=cid, label=cid, shape="rect"))
            _class_members.setdefault(cid, [])
            current_class = cid if "{" in line else None
            continue
        if current_class:
            # Collect member line (attribute or method)
            if line not in ("+", "-", "#", "~"):
                _class_members.setdefault(current_class, []).append(line)
            continue
        m = _CLASS_REL_RE.match(line)
        if m:
            c1, mul_src, op, mul_dst, c2, lbl = (
                m.group(1), m.group(2) or "", m.group(3),
                m.group(4) or "", m.group(5), m.group(6) or ""
            )
            for cid in (c1, c2):
                nodes.setdefault(cid, _Node(id=cid, label=cid, shape="rect"))
                _class_members.setdefault(cid, [])
            src_spec, tgt_spec, line_style = _class_rel_markers(op)
            edges.append(_Edge(src=c1, dst=c2, label=lbl.strip(),
                               style=line_style,
                               source_marker=src_spec, target_marker=tgt_spec,
                               src_label=mul_src, dst_label=mul_dst))
            continue
        # Bare "A : method()" — just ensure class exists
        m2 = re.match(r'^(\w+)\s*:', line)
        if m2:
            nodes.setdefault(m2.group(1), _Node(id=m2.group(1), label=m2.group(1), shape="rect"))
            _class_members.setdefault(m2.group(1), [])
    if not nodes:
        raise ValueError("No classes found in classDiagram.")
    # Assign stable parse-time edge IDs. Parallel relations (same src→dst) get
    # a #N suffix so every edge has a unique ID that is stable across runs.
    _cls_eid_counts: dict[str, int] = {}
    for _ce in edges:
        _base = f"{_ce.src}->{_ce.dst}"
        _n = _cls_eid_counts.get(_base, 0)
        _cls_eid_counts[_base] = _n + 1
        _ce.edge_id = _base if _n == 0 else f"{_base}#{_n}"
    # Encode members into label as pipe-separated multi-line tech section.
    # Attributes (no parens) come first, then a "---" divider, then methods.
    for cid, members in _class_members.items():
        if cid in nodes and members:
            attrs = [m for m in members if "(" not in m]
            methods = [m for m in members if "(" in m]
            rows = attrs
            if attrs and methods:
                rows = attrs + ["---"] + methods
            elif methods:
                rows = methods
            nodes[cid].label = f"{cid}|" + "\n".join(rows)
    return _graph_from_content_nodes(nodes, edges, {}, width_hint)


def _compile_classdiagram(
    src: str,
    width_hint: int = 0,
    direction: str = "TB",
    height_hint: int = 0,
) -> "CompiledFlowchart":
    """Parse classDiagram and return a CompiledFlowchart with NodeLayout.member_layouts populated.

    Replaces the mutable _class_topology_scene() path for both to_html() and to_svg().
    """
    from ._geometry import (
        CompiledFlowchart, FinalizedLayout, LayoutMetadata, Rect,
        validate_finalized_layout, _empty_diagnostics,
    )
    from dataclasses import replace as _dc_replace

    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    class_members: dict[str, list[str]] = {}
    current_class: "Optional[str]" = None

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
            src_spec, tgt_spec, line_style = _class_rel_markers(op)
            edges.append(_Edge(
                src=c1, dst=c2, label=lbl.strip(),
                style=line_style,
                source_marker=src_spec, target_marker=tgt_spec,
                src_label=mul_src, dst_label=mul_dst,
            ))
            continue
        m2 = re.match(r'^(\w+)\s*:', line)
        if m2:
            nodes.setdefault(m2.group(1), _Node(id=m2.group(1), label=m2.group(1), shape="rect"))
            class_members.setdefault(m2.group(1), [])

    if not nodes:
        raise ValueError("No classes found in classDiagram.")
    if len(nodes) > NODE_CAP:
        raise ValueError(f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}).")

    # Assign stable parse-time edge IDs. Parallel relations (same src→dst) get
    # a #N suffix so every edge has a unique ID that is stable across runs.
    _cls_eid_counts: dict[str, int] = {}
    for _ce in edges:
        _base = f"{_ce.src}->{_ce.dst}"
        _n = _cls_eid_counts.get(_base, 0)
        _cls_eid_counts[_base] = _n + 1
        _ce.edge_id = _base if _n == 0 else f"{_base}#{_n}"

    # Encode members into labels for height computation (pipe-separated multi-row label).
    for cid, members in class_members.items():
        if cid in nodes and members:
            attrs = [mm for mm in members if "(" not in mm]
            methods = [mm for mm in members if "(" in mm]
            rows = attrs if not methods else (
                attrs + ["---"] + methods if attrs else methods
            )
            nodes[cid].label = f"{cid}|" + "\n".join(rows)

    # Layout pipeline (Python Sugiyama; no ELK for classDiagram)
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)
    canvas_w, canvas_h = _assign_coordinates(nodes, direction)

    real_nodes = [n for n in nodes.values() if not n.is_dummy]
    if real_nodes:
        canvas_h = max(n.y + _node_render_h(n) for n in real_nodes) + CANVAS_PAD
        canvas_w = max(n.x + (n.width or NODE_W) for n in real_nodes) + CANVAS_PAD

    if any(e.src == e.dst for e in edges):
        _sl_dx, _sl_dy = _finalize_self_loop_offsets(nodes, edges, direction)
        if _sl_dx or _sl_dy:
            for _n in nodes.values():
                _n.x += _sl_dx
                _n.y += _sl_dy
            canvas_w += _sl_dx
            canvas_h += _sl_dy

    route_batch = _route_edges(nodes, edges, canvas_w, direction, {})

    # Build base NodeLayout IR, then populate member_layouts for each class node.
    node_layouts = _build_node_layouts_ir(nodes)
    _member_tls: dict[str, tuple] = {}
    for cid, members in class_members.items():
        if not members:
            _member_tls[cid] = ()
            continue
        attrs = [mm for mm in members if "(" not in mm]
        methods = [mm for mm in members if "(" in mm]
        rows = attrs if not methods else (
            attrs + ["---"] + methods if attrs else methods
        )
        _member_tls[cid] = tuple(_make_text_layout_ir(row) for row in rows)
    node_layouts = {
        nid: _dc_replace(nl, member_layouts=_member_tls[nid])
        if nid in _member_tls else nl
        for nid, nl in node_layouts.items()
    }

    routed_edges_ir = _build_routed_edges_ir(route_batch.routed, canvas_area=canvas_w * canvas_h)
    canvas_bounds = Rect(x=0.0, y=0.0, w=float(canvas_w), h=float(canvas_h))

    finalized = FinalizedLayout(
        node_layouts=_types.MappingProxyType(node_layouts),
        group_layouts=_types.MappingProxyType({}),
        routed_edges=routed_edges_ir,
        routing_failures=route_batch.failures,
        visible_bounds=canvas_bounds,
        diagram_padding=float(CANVAS_PAD),
        canvas_bounds=canvas_bounds,
        direction=direction,
        diagnostics=_empty_diagnostics(),
    )

    metadata = LayoutMetadata(
        direction=direction,
        node_count=len(real_nodes),
        group_count=0,
        edge_count=len(edges),
        algorithm="LongestPathRanker+BarycentricOrderer+SimpleCoordinateAssigner",
    )

    validation = validate_finalized_layout(finalized, metadata=metadata)
    return CompiledFlowchart(layout=finalized, validation=validation, metadata=metadata)


# ── sequence compile-once helper ─────────────────────────────────────────────
# ── strategy dispatch ─────────────────────────────────────────────────────────

def _dispatch(
    src: str,
    direction_override: Optional[str],
    width_hint: int,
    height_hint: int = 0,
    style_overrides: str = "",
    opts: "RenderOptions | None" = None,
) -> str:
    """Detect directive, dispatch to per-type strategy, return HTML fragment."""
    clean = _strip_frontmatter(src)
    directive, auto_direction = _detect_directive(clean)
    # When the caller supplied an explicit direction override, respect it and
    # disable auto-direction (pass height_hint=0 to _layout_graph_topology so
    # the auto-select branch doesn't fire).
    direction = (direction_override or auto_direction).upper()
    effective_height = height_hint if not direction_override else 0
    d = directive.lower()

    if d in _GRAPH_DIRECTIVES:
        return _layout_graph_topology(
            clean, direction, width_hint, effective_height,
            style_overrides=style_overrides,
            opts=opts,
        )
    if d == "sequencediagram":
        return compile_sequence(clean, width_hint=width_hint, height_hint=effective_height).html
    if d == "erdiagram":
        from .er import er_to_html
        return er_to_html(clean, width_hint=width_hint)
    if d == "classdiagram":
        compiled = _compile_classdiagram(clean, width_hint, direction, effective_height)
        _cls_layout = compiled.layout
        _cls_w = int(_cls_layout.canvas_bounds.w)
        _cls_h = int(_cls_layout.canvas_bounds.h)
        _cls_zoom = 1.0
        if width_hint and _cls_w > 0:
            _cls_zoom = min(width_hint / _cls_w, 1.0)
        _cls_fragment = render_finalized(_cls_layout)
        if abs(_cls_zoom - 1.0) > 0.005:
            _cls_fragment = (
                f'<div class="diagram-zoom-wrapper"'
                f' style="display:contents; zoom:{_cls_zoom:.4f};">'
                f'{_cls_fragment}</div>'
            )
        return _cls_fragment
    if d == "gantt":
        return _layout_gantt(clean, direction, width_hint)
    if d == "timeline":
        return _layout_timeline(clean, direction, width_hint)
    if d == "quadrantchart":
        return _layout_quadrant(clean, direction, width_hint)
    if d == "pie" or d.startswith("pie "):
        return _layout_pie(clean, direction, width_hint)
    if d == "xychart-beta":
        return _layout_xychart(clean, direction, width_hint)
    if d == "mindmap":
        return _layout_mindmap(clean, direction, width_hint)
    if d == "block-beta":
        return _layout_block(clean, direction, width_hint)
    if d == "packet-beta":
        return _layout_packet(clean, direction, width_hint)
    if d == "kanban":
        return _layout_kanban(clean, direction, width_hint)
    if d == "architecture-beta":
        from .architecture import arch_to_html
        return arch_to_html(clean, width_hint=width_hint)
    if d in ("c4context", "c4container", "c4component"):
        return _layout_c4(clean, direction, width_hint)
    if d == "journey":
        return _layout_journey(clean, direction, width_hint)
    if d == "requirementdiagram":
        from .requirement import requirement_to_html
        return requirement_to_html(clean, width_hint=width_hint, height_hint=effective_height)
    if d == "gitgraph":
        return _layout_gitgraph(clean, direction, width_hint)
    if d == "sankey-beta":
        return _layout_sankey(clean, direction, width_hint)

    if d == "zenuml":
        raise ValueError(
            f"Mermaid directive '{directive}' is not supported by the pure-Python renderer. "
            "Use mmdc (mermaid-js CLI) for this diagram type."
        )

    # Unknown directive — graph-topology best-effort fallback.
    # Catch only parse / value errors; propagate programming errors unmasked.
    try:
        return _layout_graph_topology(
            clean, direction, width_hint, style_overrides=style_overrides,
        )
    except (ValueError, KeyError, AttributeError):
        raise ValueError(f"Unsupported or unrecognised Mermaid directive: '{directive}'")



def _dispatch_validate(src: str) -> "ValidationResult":
    """Validate Mermaid source including geometry invariants."""
    from ._geometry import ValidationResult
    clean = _strip_frontmatter(src)
    directive, _ = _detect_directive(clean)
    d = directive.lower()

    if d == "sequencediagram":
        try:
            compiled = compile_sequence(clean)
        except Exception as exc:  # intentional: validation must return a result, never raise
            return ValidationResult(
                render="fail",
                syntax_coverage="fail",
                geometry="unvalidated",
                errors=(str(exc),),
            )
        geom = compiled.geometry
        legacy_diags = geom.diagnostics  # legacy Diagnostic tuples for ValidationResult
        sc = "partial" if legacy_diags else "pass"
        svr = validate_sequence_geometry(geom)
        return ValidationResult(
            diagnostics=legacy_diags,
            syntax_coverage=sc,
            geometry=svr.structural_geometry,
            structural_geometry=svr.structural_geometry,
            semantic_geometry=svr.semantic_geometry,
            warnings=tuple(svr.warnings),
        )

    if d in _GRAPH_DIRECTIVES:
        try:
            compiled_fc = _compile_flowchart(clean, 0, None)
        except Exception as exc:  # intentional: validation must return a result, never raise
            return ValidationResult(
                render="fail",
                syntax_coverage="fail",
                geometry="unvalidated",
                errors=(str(exc),),
            )
        return compiled_fc.validation

    return ValidationResult(geometry="unvalidated")


# ── CLI ───────────────────────────────────────────────────────────────────────
