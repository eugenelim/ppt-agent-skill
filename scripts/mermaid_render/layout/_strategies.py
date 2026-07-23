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
    fragment = render_finalized(layout)

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


# ── helpers shared by T2/T3 ──────────────────────────────────────────────────


# ── helpers shared by T2/T3 ──────────────────────────────────────────────────
# _directive_content has moved to ._parser and is imported above.


# ── T8: arrow-spec helpers ───────────────────────────────────────────────────

def _emit_arrow_or_diagnostic(
    token: str,
    diagnostics: "list",
) -> "ArrowSpec":
    """Look up token in ARROW_SPECS; on miss emit diagnostic and return no-marker fallback."""
    from ._geometry import ARROW_SPECS, ArrowSpec, SequenceDiagnostic  # noqa: PLC0415
    spec = ARROW_SPECS.get(token)
    if spec is None:
        diagnostics.append(SequenceDiagnostic(
            severity="warning",
            code="unsupported_arrow",
            message=f"Unknown arrow token '{token}'",
            source_text=token,
        ))
        spec = ArrowSpec(dashed=False, start_marker=None, end_marker=None)
    return spec


def _cx_or_diagnostic(
    pid: str,
    p_index: "dict[str, int]",
    *,
    col_centers: "list[float]",
    diags: "list",
    _PAD_H: float = 40.0,
) -> float:
    """Return cx for pid, or emit diagnostic and return PAD_H fallback (AC-9.3, AC-4.5).

    Defensive hardening — all pids are auto-registered through parsing so this
    site is unreachable by user input. Verified via direct unit tests.
    """
    from ._geometry import SequenceDiagnostic  # noqa: PLC0415
    idx = p_index.get(pid, -1)
    if idx < 0 or idx >= len(col_centers):
        diags.append(SequenceDiagnostic(
            severity="error",
            code="unknown_participant",
            message=f"Participant '{pid}' not registered (defensive invariant)",
            source_text=pid,
        ))
        return _PAD_H
    return col_centers[idx]


def _emit_message_or_skip(
    src_pid: str,
    dst_pid: str,
    p_index: "dict[str, int]",
    col_centers: "list[float]",
    diags: "list",
    row_tops: "list[float]",
    event_idx: int,
) -> bool:
    """Return True (skip) if either pid is unregistered, emitting a diagnostic (AC-4.5).

    Defensive hardening — all pids are auto-registered through parsing so this
    site is unreachable by user input. Verified via direct unit tests.
    """
    from ._geometry import SequenceDiagnostic  # noqa: PLC0415
    skipped = False
    for unknown in [p for p in (src_pid, dst_pid) if p and p not in p_index]:
        diags.append(SequenceDiagnostic(
            severity="error",
            code="unknown_participant",
            message=f"Participant '{unknown}' not registered (defensive invariant)",
            source_text=unknown,
        ))
        skipped = True
    return skipped


# ── T2: sequenceDiagram ───────────────────────────────────────────────────────

_SEQ_PART_RE = re.compile(r'^(?:participant|actor)\s+(\S+)(?:\s+as\s+(.+))?', re.I)
_SEQ_MSG_RE = re.compile(
    r'^(\S+?)\s*(<<-->>|<<->>|-->>|->>|-->|->|--x|-x|--\)|-\))\s*(\S+)\s*:\s*(.*)$'
)
_SEQ_BLOCK_RE = re.compile(r'^(alt|loop|opt|par|critical|break|rect)\s*(.*)', re.I)
_SEQ_END_RE = re.compile(r'^end\s*$', re.I)
_SEQ_ACTIVATE_RE = re.compile(r'^(activate|deactivate)\s+(\S+)', re.I)
_SEQ_SKIP_RE = re.compile(
    r'^(autonumber|create\s+actor|par_over)\b', re.I
)
_SEQ_CREATE_RE = re.compile(r'^create\s+participant\s+(\S+)', re.I)
_SEQ_DESTROY_RE = re.compile(r'^destroy\s+(\S+)', re.I)
# Group 1: position ("over", "left of", "right of")
# Group 2: participant list (comma-separated)
# Group 3: note text
_SEQ_NOTE_RE = re.compile(
    r'^[Nn]ote\s+(over|left\s+of|right\s+of)\s+([^:]+):\s*(.+)', re.I
)
_SEQ_ELSE_RE = re.compile(r'^(else|and|option)\s*(.*)', re.I)

# ── Box directive helpers ─────────────────────────────────────────────────────
_BOX_FUNC_COLOR_RE = re.compile(
    r'^box\s+(?P<color>rgba?\([0-9,.%\s]+\)|hsla?\([0-9,.%\s]+\))\s*(?P<label>.*)$', re.I
)
_BOX_SIMPLE_RE = re.compile(r'^box(?:\s+(?P<first>\S+))?(?:\s+(?P<rest>.*))?$', re.I)
_CSS_NAMED_COLORS = frozenset({
    "aliceblue", "antiquewhite", "aqua", "aquamarine", "azure", "beige", "bisque",
    "black", "blanchedalmond", "blue", "blueviolet", "brown", "burlywood", "cadetblue",
    "chartreuse", "chocolate", "coral", "cornflowerblue", "cornsilk", "crimson", "cyan",
    "darkblue", "darkcyan", "darkgoldenrod", "darkgray", "darkgreen", "darkgrey",
    "darkkhaki", "darkmagenta", "darkolivegreen", "darkorange", "darkorchid", "darkred",
    "darksalmon", "darkseagreen", "darkslateblue", "darkslategray", "darkslategrey",
    "darkturquoise", "darkviolet", "deeppink", "deepskyblue", "dimgray", "dimgrey",
    "dodgerblue", "firebrick", "floralwhite", "forestgreen", "fuchsia", "gainsboro",
    "ghostwhite", "gold", "goldenrod", "gray", "green", "greenyellow", "grey",
    "honeydew", "hotpink", "indianred", "indigo", "ivory", "khaki", "lavender",
    "lavenderblush", "lawngreen", "lemonchiffon", "lightblue", "lightcoral", "lightcyan",
    "lightgoldenrodyellow", "lightgray", "lightgreen", "lightgrey", "lightpink",
    "lightsalmon", "lightseagreen", "lightskyblue", "lightslategray", "lightslategrey",
    "lightsteelblue", "lightyellow", "lime", "limegreen", "linen", "magenta", "maroon",
    "mediumaquamarine", "mediumblue", "mediumorchid", "mediumpurple", "mediumseagreen",
    "mediumslateblue", "mediumspringgreen", "mediumturquoise", "mediumvioletred",
    "midnightblue", "mintcream", "mistyrose", "moccasin", "navajowhite", "navy",
    "oldlace", "olive", "olivedrab", "orange", "orangered", "orchid", "palegoldenrod",
    "palegreen", "paleturquoise", "palevioletred", "papayawhip", "peachpuff", "peru",
    "pink", "plum", "powderblue", "purple", "red", "rosybrown", "royalblue",
    "saddlebrown", "salmon", "sandybrown", "seagreen", "seashell", "sienna", "silver",
    "skyblue", "slateblue", "slategray", "slategrey", "snow", "springgreen",
    "steelblue", "tan", "teal", "thistle", "tomato", "turquoise", "violet", "wheat",
    "white", "whitesmoke", "yellow", "yellowgreen", "transparent",
})


def _parse_box_color_label(line: str) -> "tuple[str, str]":
    """Parse 'box [color] [label]' → (color_css, label_text).

    Color token is accepted when it matches #hex, rgb/rgba/hsl/hsla(...), or a
    CSS named color.  Otherwise the entire remainder is treated as the label and
    color defaults to rgba(200,200,200,0.3).  This prevents arbitrary first-word
    labels (e.g. 'box Frontend') from being misread as an invalid color.
    """
    _default_color = "rgba(200,200,200,0.3)"
    # Functional colors may contain spaces inside parens; match them first.
    m = _BOX_FUNC_COLOR_RE.match(line)
    if m:
        return m.group("color").strip(), m.group("label").strip()
    m = _BOX_SIMPLE_RE.match(line)
    if not m:
        return _default_color, ""
    first = (m.group("first") or "").strip()
    rest = (m.group("rest") or "").strip()
    if not first:
        return _default_color, ""
    if re.match(r'^#[0-9A-Fa-f]{3,8}$', first) or first.lower() in _CSS_NAMED_COLORS:
        return first, rest
    # Not a recognizable color — whole remainder is the label
    return _default_color, (first + (" " + rest if rest else "")).strip()


def _layout_lifeline(
    src: str, direction: str, width_hint: int
) -> "tuple[str, SequenceGeometry]":
    """sequenceDiagram: participants as columns, messages as horizontal arrows."""
    from ._geometry import (  # noqa: PLC0415
        Bounds, ParticipantGeometry, MessageGeometry, ActivationGeometry,
        NoteGeometry, FragmentGeometry, BranchGeometry,
        Diagnostic, SequenceGeometry, TextStyle,
    )
    from ._text import get_default_measurer  # noqa: PLC0415
    _MEASURER = get_default_measurer()
    content_lines = _directive_content(src)
    participants: list[str] = []
    p_label: dict[str, str] = {}
    _diagnostics: list[Diagnostic] = []
    _all_box_groups: "list[dict]" = []
    _open_box_stack: "list[dict]" = []
    # "box" | "block" — tracks what each block_depth level is for end-handling
    _block_type_stack: "list[str]" = []

    def _ensure_p(name: str) -> None:
        n = name.strip()
        if n and n not in participants:
            participants.append(n)
            p_label.setdefault(n, n)
            if _open_box_stack and n not in _open_box_stack[-1]["members"]:
                _open_box_stack[-1]["members"].append(n)

    # ── Arrow spec table (SEQ-012) ────────────────────────────────────────────
    _ARROW_SPECS: "dict[str, dict]" = {
        "->":     {"dashed": False, "start_m": None,       "end_m": None},
        "-->":    {"dashed": True,  "start_m": None,       "end_m": None},
        "->>":    {"dashed": False, "start_m": None,       "end_m": "triangle"},
        "-->>":   {"dashed": True,  "start_m": None,       "end_m": "triangle"},
        "-x":     {"dashed": False, "start_m": None,       "end_m": "cross"},
        "--x":    {"dashed": True,  "start_m": None,       "end_m": "cross"},
        "-)":     {"dashed": False, "start_m": None,       "end_m": "filled_head"},
        "--)":    {"dashed": True,  "start_m": None,       "end_m": "filled_head"},
        "<<->>":  {"dashed": False, "start_m": "triangle", "end_m": "triangle"},
        "<<-->>": {"dashed": True,  "start_m": "triangle", "end_m": "triangle"},
    }

    items: list[dict] = []
    block_depth = 0
    _created_at: "dict[str, int]" = {}   # pid → row index of creation
    _destroyed_at: "dict[str, int]" = {} # pid → row index of destruction
    _parse_row_ctr = 0  # count of row-type items appended so far
    _parse_row_types = frozenset({"msg", "block", "note", "else", "rect"})
    for lineno, raw in enumerate(content_lines, start=1):
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        # Box directive — parse color/label/membership (must precede _SEQ_SKIP_RE which also matches 'box').
        # Guard against participant named "Box" (e.g. "Box ->> Alice: hi"): skip if _SEQ_MSG_RE matches.
        if re.match(r'^box(?:\s|$)', line, re.I) and not _SEQ_MSG_RE.match(line):
            _box_color, _box_label = _parse_box_color_label(line)
            _new_box: "dict" = {"color": _box_color, "label": _box_label, "members": []}
            _open_box_stack.append(_new_box)
            _all_box_groups.append(_new_box)
            _block_type_stack.append("box")
            block_depth += 1
            continue
        m_create = _SEQ_CREATE_RE.match(line)
        if m_create:
            _cpid = m_create.group(1).strip()
            _ensure_p(_cpid)
            _created_at[_cpid] = _parse_row_ctr
            continue
        m_destroy = _SEQ_DESTROY_RE.match(line)
        if m_destroy:
            _dpid = m_destroy.group(1).strip()
            _ensure_p(_dpid)
            _destroyed_at[_dpid] = _parse_row_ctr
            continue
        m_skip = _SEQ_SKIP_RE.match(line)
        if m_skip:
            kw = m_skip.group(1).lower().replace(" ", "_")
            _diagnostics.append(Diagnostic(feature=kw, line_number=lineno, source_text=line))
            if re.match(r'^par_over\b', line, re.I):
                block_depth += 1
                _block_type_stack.append("block")  # keep block_depth ↔ _block_type_stack in sync
            continue
        m = _SEQ_PART_RE.match(line)
        if m:
            alias = m.group(1).strip()
            display = (m.group(2) or alias).strip()
            p_label[alias] = display
            _ensure_p(alias)
            continue
        m = _SEQ_ACTIVATE_RE.match(line)
        if m:
            act_type = "activate" if m.group(1).lower() == "activate" else "deactivate"
            _ap = m.group(2).strip()
            _ensure_p(_ap)  # SEQ-014: activate/deactivate also register participants
            items.append({"type": act_type, "pid": _ap})
            continue
        m = _SEQ_NOTE_RE.match(line)
        if m:
            _note_pos = m.group(1).lower().replace(" ", "_")  # "over", "left_of", "right_of"
            _note_pids = [p.strip() for p in m.group(2).strip().split(",")]
            for _np in _note_pids:  # SEQ-014: register note participants
                _ensure_p(_np)
            items.append({"type": "note", "pos": _note_pos,
                          "pids": _note_pids, "pid": _note_pids[0],
                          "text": m.group(3).strip()})
            _parse_row_ctr += 1
            continue
        m = _SEQ_MSG_RE.match(line)
        if m:
            sp_raw, arrow, dp_raw, lbl = m.group(1), m.group(2), m.group(3), m.group(4)
            # Activation shorthand: ->>+Dest activates Dest; -->>-Dest deactivates src
            dp_prefix = dp_raw[0] if dp_raw and dp_raw[0] in ('+', '-') else ''
            dp = dp_raw[1:] if dp_prefix else dp_raw
            sp = sp_raw.lstrip('+')
            _ensure_p(sp); _ensure_p(dp)
            items.append({"type": "msg", "src": sp, "dst": dp,
                          "label": lbl.strip(), "arrow": arrow})
            _parse_row_ctr += 1
            if dp_prefix == '+':
                items.append({"type": "activate", "pid": dp})
            elif dp_prefix == '-':
                items.append({"type": "deactivate", "pid": sp})
            continue
        if block_depth > 0:
            me = _SEQ_ELSE_RE.match(line)
            if me:
                items.append({"type": "else", "kw": me.group(1).lower(), "label": me.group(2).strip()})
                _parse_row_ctr += 1
                continue
        m = _SEQ_BLOCK_RE.match(line)
        if m:
            kw = m.group(1).lower()
            # SEQ-013: rect is a solid fill background, not a dashed labeled fragment
            item_type = "rect" if kw == "rect" else "block"
            items.append({"type": item_type, "kw": m.group(1), "label": m.group(2).strip()})
            _parse_row_ctr += 1
            block_depth += 1
            _block_type_stack.append("block")
            continue
        if _SEQ_END_RE.match(line) and block_depth > 0:
            block_depth -= 1
            _closed = _block_type_stack.pop() if _block_type_stack else "block"
            if _closed == "box":
                if _open_box_stack:
                    _open_box_stack.pop()
            else:
                items.append({"type": "block_end"})
        else:
            _diagnostics.append(
                Diagnostic(feature="unrecognized_line", line_number=lineno, source_text=line)
            )

    if not participants:
        raise ValueError("No participants found in sequenceDiagram.")

    # ── Block-span prepass + fragment participant tracking (SEQ-008) ──────────
    _bstack: list[int] = []
    _frag_parts: "dict[int, set]" = {}
    _frag_id: "dict[int, str]" = {}
    _branch_parent_id: "dict[int, str]" = {}  # T7: else_item_idx → parent frag_id
    _frag_ctr = 0
    _row_types = {"msg", "block", "note", "else", "rect"}
    for _bi, _bit in enumerate(items):
        if _bit["type"] in ("block", "rect"):
            _bstack.append(_bi)
            _frag_parts[_bi] = set()
            _frag_id[_bi] = f"f{_frag_ctr}"
            _frag_ctr += 1
        elif _bit["type"] in ("else",) and _bstack:
            _branch_parent_id[_bi] = _frag_id[_bstack[-1]]
        elif _bit["type"] == "block_end" and _bstack:
            _si = _bstack.pop()
            items[_si]["span"] = sum(
                1 for _ji in range(_si, _bi) if items[_ji]["type"] in _row_types
            )
            items[_si]["frag_parts"] = _frag_parts.get(_si, set())
        elif _bit["type"] == "msg":
            for _fsi in _bstack:
                _frag_parts[_fsi].add(_bit["src"])
                _frag_parts[_fsi].add(_bit["dst"])
        elif _bit["type"] == "note":
            for _fsi in _bstack:
                for _np in _bit.get("pids", [_bit.get("pid", "")]):
                    if _np:
                        _frag_parts[_fsi].add(_np)
        elif _bit["type"] in ("activate", "deactivate"):
            for _fsi in _bstack:
                _frag_parts[_fsi].add(_bit["pid"])
    for _bit in items:
        if _bit["type"] in ("block", "rect"):
            _bit.setdefault("span", 1)
            _bit.setdefault("frag_parts", set())

    # ── Column geometry ───────────────────────────────────────────────────────
    COL_GAP, PAD_H, PAD_V = 24, 40, 24
    HDR_H, ROW_H = 48, 40
    ACTIVATION_W = 10   # px width of a single activation bar (SEQ-006)
    ACTIVATION_DX = 4   # px x-shift per nesting depth (SEQ-006)
    NOTE_SPAN_OVERHANG = 24  # px a spanning note extends past edge lifelines (SEQ-010)
    SIDE_NOTE_GAP = 24
    BOX_HPAD, BOX_MIN_W, LABEL_PAD = 32, 80, 40  # T8a: constraint-based layout

    n_parts = len(participants)

    # Measure participant name widths (13px bold matches _seq_label_css)
    _PART_STYLE = TextStyle(font_size=13, font_weight=700)
    _LABEL_STYLE = TextStyle(font_size=12)  # message label font
    _half_w: "list[float]" = []
    for _pp in participants:
        _pl = p_label.get(_pp, _pp)
        _pw = _MEASURER.layout(_pl, _PART_STYLE, max_width=float("inf")).max_content_width
        _half_w.append(max(_pw + BOX_HPAD, BOX_MIN_W) / 2.0)

    # ── SEQ-014: precomputed participant index ────────────────────────────────
    _p_index: "dict[str, int]" = {p: i for i, p in enumerate(participants)}

    def _box_hw(pid: str) -> float:
        """Half-width of the participant box for pid."""
        _idx = _p_index.get(pid, 0)
        return _half_w[_idx] if _idx < len(_half_w) else BOX_MIN_W / 2.0

    # Collect constraints: adjacent participant spacing + message label spans
    # + spanning-note text widths + fragment-header text widths (T8b)
    _col_constraints: "list[tuple[int, int, float]]" = []
    for _ci in range(n_parts - 1):
        _col_constraints.append((_ci, _ci + 1, _half_w[_ci] + COL_GAP + _half_w[_ci + 1]))
    _NOTE_STYLE_C = TextStyle(font_size=10)
    _FRAG_HDR_STYLE = TextStyle(font_size=11, font_weight=700)
    for _it in items:
        _itype = _it.get("type")
        if _itype == "msg" and _it.get("src") != _it.get("dst"):
            _si = _p_index.get(_it.get("src", ""), -1)
            _di = _p_index.get(_it.get("dst", ""), -1)
            if _si >= 0 and _di >= 0:
                _lo, _hi = min(_si, _di), max(_si, _di)
                _lbl = _it.get("label", "")
                if _lbl:
                    _lw = _MEASURER.layout(_lbl, _LABEL_STYLE, max_width=float("inf")).max_content_width
                    _col_constraints.append((_lo, _hi, _lw + LABEL_PAD))
        elif _itype == "note" and _it.get("pos") == "over":
            _npids = _it.get("pids", [])
            _nidxs = [_p_index[p] for p in _npids if p in _p_index]
            if len(_nidxs) >= 2:
                _nlo, _nhi = min(_nidxs), max(_nidxs)
                _ntxt = _it.get("text", "")
                if _ntxt:
                    _ntl = _MEASURER.layout(_ntxt, _NOTE_STYLE_C, max_width=float("inf"))
                    # Ensure the longest unbreakable word fits inside the usable note width.
                    # Note width = (cx_hi - cx_lo) + 2*NOTE_SPAN_OVERHANG; usable = note_w - 8.
                    # → cx_hi - cx_lo >= min_content_width - 2*NOTE_SPAN_OVERHANG + 8
                    _ngap = _ntl.min_content_width - 2 * NOTE_SPAN_OVERHANG + 8
                    if _ngap > 0:
                        _col_constraints.append((_nlo, _nhi, _ngap))
        elif _itype == "block":
            _fps = _it.get("frag_parts", set())
            _fps_idxs = [_p_index[p] for p in _fps if p in _p_index]
            if _fps_idxs:
                _flo, _fhi = min(_fps_idxs), max(_fps_idxs)
            else:
                _flo, _fhi = 0, max(0, n_parts - 1)
            _fhdr = (_it.get("kw", "") + " " + _it.get("label", "")).strip()
            if _fhdr and _flo < _fhi:
                _ftw = _MEASURER.layout(_fhdr, _FRAG_HDR_STYLE, max_width=float("inf")).max_content_width
                # frag width = cx(hi)-cx(lo) + half_w[lo] + half_w[hi] + PAD_H >= ftw + LABEL_PAD
                _fgap = _ftw + LABEL_PAD - _half_w[_flo] - _half_w[_fhi] - PAD_H
                if _fgap > 0:
                    _col_constraints.append((_flo, _fhi, _fgap))

    # Longest-path left-to-right solver (O(n) over sorted constraints)
    def _solve_col_centers(constraints: "list[tuple[int, int, float]]", n: int) -> "list[float]":
        centers: "list[float]" = [0.0] * n
        for _i, _j, _gap in sorted(constraints, key=lambda c: (c[0], c[1])):
            if _i < n and _j < n:
                centers[_j] = max(centers[_j], centers[_i] + _gap)
        return centers

    _raw_centers = _solve_col_centers(_col_constraints, n_parts) if n_parts > 0 else []
    _col_off = PAD_H + (_half_w[0] if _half_w else 0)
    _col_centers: "list[float]" = [c + _col_off for c in _raw_centers]

    canvas_w: float = (_col_centers[-1] + _half_w[-1] + PAD_H) if _col_centers else float(2 * PAD_H)

    BOX_H = HDR_H - 8
    ll_top = PAD_V + BOX_H + 4

    _cx_offset = [0]

    def _cx(pid: str) -> int:
        _idx = _p_index.get(pid, 0)
        _base = _col_centers[_idx] if _idx < len(_col_centers) else float(PAD_H)
        return int(round(_base + _cx_offset[0]))

    # ── SEQ-009: row-height accumulator (T6: variable heights) ──────────────
    _NOTE_STYLE = TextStyle(font_size=10)
    _MSG_LABEL_STYLE = TextStyle(font_size=11)

    def _note_row_h(it: dict) -> int:
        text = it.get("text", "")
        if not text:
            return ROW_H
        pids_list = it.get("pids", [it.get("pid", "")])
        primary = pids_list[0] if pids_list else (participants[0] if participants else "")
        pos = it.get("pos", "over")
        if pos in ("left_of", "right_of"):
            nw = _box_hw(primary) * 2
        elif pos == "over" and len(pids_list) >= 2:
            valid_idxs = [_p_index[p] for p in pids_list if p in _p_index]
            if valid_idxs:
                lo_i, hi_i = min(valid_idxs), max(valid_idxs)
                span_w = _col_centers[hi_i] - _col_centers[lo_i] if lo_i < len(_col_centers) and hi_i < len(_col_centers) else 0.0
                nw = span_w + 2 * NOTE_SPAN_OVERHANG
            else:
                nw = _box_hw(primary) * 2
        else:
            nw = _box_hw(primary) * 2
        usable_w = max(1.0, nw - 8)
        tl = _MEASURER.layout(text, _NOTE_STYLE, max_width=usable_w)
        return max(ROW_H, int(math.ceil(tl.height)) + 8)

    def _msg_row_h(it: dict) -> int:
        lbl = it.get("label", "")
        if not lbl:
            return ROW_H
        src, dst = it.get("src", ""), it.get("dst", "")
        si = _p_index.get(src, -1)
        di = _p_index.get(dst, -1)
        if si < 0 or di < 0 or si >= len(_col_centers) or di >= len(_col_centers):
            return ROW_H
        span_w = abs(_col_centers[si] - _col_centers[di])
        if span_w < 1.0:
            span_w = _box_hw(src) * 2
        tl = _MEASURER.layout(lbl, _MSG_LABEL_STYLE, max_width=max(1.0, span_w - 8))
        return max(ROW_H, int(math.ceil(tl.height)) + 16)

    def _block_row_h(it: dict) -> int:
        hdr = (it.get("kw", "") + " " + it.get("label", "")).strip()
        if not hdr:
            return ROW_H
        fparts = it.get("frag_parts", set())
        fps_idxs = [_p_index[p] for p in fparts if p in _p_index]
        if fps_idxs and len(fps_idxs) >= 2:
            lo_i, hi_i = min(fps_idxs), max(fps_idxs)
            if lo_i < len(_col_centers) and hi_i < len(_col_centers):
                frag_w = (_col_centers[hi_i] - _col_centers[lo_i]
                          + _half_w[lo_i] + _half_w[hi_i] + PAD_H)
            else:
                frag_w = canvas_w
        else:
            # Single-participant (or no participants): use actual fragment rect width, not canvas_w.
            # canvas_w is wider than the fragment rect for single-participant diagrams.
            # Note: _frag_x_bounds is defined later; inline the equivalent logic here.
            _fv = [p for p in it.get("frag_parts", set()) if p in _p_index]
            if _fv:
                _lp = min(_fv, key=lambda p: _p_index[p])
                _rp = max(_fv, key=lambda p: _p_index[p])
                frag_w = (float(_cx(_rp)) + _box_hw(_rp) + PAD_H / 2
                          - (float(_cx(_lp)) - _box_hw(_lp) - PAD_H / 2))
            else:
                frag_w = canvas_w
        tl = _MEASURER.layout(hdr, _FRAG_HDR_STYLE, max_width=max(1.0, frag_w - 8))
        return max(ROW_H, int(math.ceil(tl.height)) + 8)

    def _row_h_for(it: dict) -> int:
        t = it["type"]
        if t == "note":
            return _note_row_h(it)
        if t == "msg":
            return _msg_row_h(it)
        if t == "block":
            return _block_row_h(it)
        return ROW_H

    _row_h_list: "list[int]" = [_row_h_for(it) for it in items if it["type"] in _row_types]
    _row_top_list: "list[int]" = []
    _acc = 0
    for _rh in _row_h_list:
        _row_top_list.append(_acc)
        _acc += _rh
    ll_bot = ll_top + _acc + 8
    canvas_h = ll_bot + BOX_H + PAD_V

    # ── SEQ-006: event y-coordinate pass ─────────────────────────────────────
    _event_y: "dict[int, float]" = {}
    _ev_row = 0
    for _i, _it in enumerate(items):
        if _it["type"] == "msg":
            _event_y[_i] = ll_top + _row_top_list[_ev_row] + _row_h_list[_ev_row] // 2
            _ev_row += 1
        elif _it["type"] in _row_types:
            _ev_row += 1

    # ── SEQ-006: activation span computation (exact message baselines) ────────
    _act_stacks_v2: "dict[str, list]" = {}
    _act_spans_v2: "list[tuple]" = []  # (pid, start_y, end_y, depth)
    _last_msg_y: float = float(ll_top)
    for _i, _it in enumerate(items):
        if _it["type"] == "msg":
            _last_msg_y = _event_y[_i]
        elif _it["type"] == "activate":
            _pid = _it["pid"]
            _stk = _act_stacks_v2.setdefault(_pid, [])
            _stk.append((_last_msg_y, len(_stk)))
        elif _it["type"] == "deactivate":
            _pid = _it["pid"]
            _stk = _act_stacks_v2.get(_pid, [])
            if _stk:
                _sy, _depth = _stk.pop()
                _act_spans_v2.append((_pid, _sy, _last_msg_y, _depth))
            else:
                _diagnostics.append(Diagnostic(
                    feature="unmatched_deactivate",
                    line_number=0,
                    source_text=f"deactivate {_pid}",
                ))
    # Flush unclosed activations to lifeline bottom (SEQ-006)
    _implicitly_closed: "set[tuple[str, float, int]]" = set()
    for _pid, _stk in _act_stacks_v2.items():
        while _stk:
            _sy, _depth = _stk.pop()
            _implicitly_closed.add((_pid, _sy, _depth))
            _act_spans_v2.append((_pid, _sy, float(ll_bot), _depth))
            _diagnostics.append(Diagnostic(
                feature="unclosed_activation",
                line_number=0,
                source_text=f"activate {_pid}",
            ))

    # ── SEQ-007: activation-aware message endpoint resolver ───────────────────
    def _act_bounds_at(pid: str, y: float) -> "Optional[tuple[float, float]]":
        """Return (left, right) edges of combined active activation bars at y."""
        cx = _cx(pid)
        active = [(sy, ey, d) for p, sy, ey, d in _act_spans_v2 if p == pid and sy <= y <= ey]
        if not active:
            return None
        lo = min(cx - ACTIVATION_W // 2 + d * ACTIVATION_DX for _, _, d in active)
        hi = max(cx - ACTIVATION_W // 2 + d * ACTIVATION_DX + ACTIVATION_W for _, _, d in active)
        return lo, hi

    def activation_bounds_at(pid: str, y: float) -> "tuple[float, float]":
        """Return (left, right) of outermost active bar, or (cx, cx) if idle."""
        ab = _act_bounds_at(pid, y)
        cx = float(_cx(pid))
        return ab if ab else (cx, cx)

    def _msg_endpoints(src: str, dst: str, y: float) -> "tuple[float, float]":
        """Return (x_start, x_end) for a message, honoring activation bar edges."""
        scx, dcx = float(_cx(src)), float(_cx(dst))
        ltr = scx < dcx
        sb = _act_bounds_at(src, y)
        db = _act_bounds_at(dst, y)
        if ltr:
            sx2 = sb[1] if sb else scx
            dx2 = db[0] if db else dcx
        else:
            sx2 = sb[0] if sb else scx
            dx2 = db[1] if db else dcx
        return sx2, dx2

    # ── Note geometry ─────────────────────────────────────────────────────────
    def _note_geom(it: dict, _row: int) -> "tuple[float, float, float, float]":
        note_y = ll_top + _row_top_list[_row] + 4
        note_h = _row_h_list[_row] - 8
        pos = it.get("pos", "over")
        pids_list = it.get("pids", [it.get("pid", "")])
        primary = pids_list[0] if pids_list else ""
        if pos == "left_of":
            nw = _box_hw(primary) * 2
            nx = _cx(primary) - nw - SIDE_NOTE_GAP
        elif pos == "right_of":
            nw = _box_hw(primary) * 2
            nx = _cx(primary) + SIDE_NOTE_GAP
        elif pos == "over" and len(pids_list) >= 2:
            xs = [_cx(p) for p in pids_list if p in _p_index]
            if xs:
                # SEQ-010: anchor to lifeline centers + fixed overhang
                left_cx, right_cx = float(min(xs)), float(max(xs))
                nw = (right_cx - left_cx) + 2 * NOTE_SPAN_OVERHANG
                nx = (left_cx + right_cx) / 2 - nw / 2
            else:
                nw = _box_hw(primary) * 2
                nx = float(_cx(primary) - _box_hw(primary))
        else:
            nw = _box_hw(primary) * 2
            nx = float(_cx(primary) - _box_hw(primary))
        return nx, note_y, nw, note_h

    # ── Note-bounds pre-pass ──────────────────────────────────────────────────
    _min_note_x = PAD_H
    _max_note_x = canvas_w - PAD_H
    for _nit in items:
        if _nit["type"] != "note":
            continue
        _npos = _nit.get("pos", "over")
        _npids = _nit.get("pids", [_nit.get("pid", "")])
        _nprimary = _npids[0] if _npids else ""
        if _npos == "left_of" and _nprimary in _p_index:
            _nx = _cx(_nprimary) - _box_hw(_nprimary) * 2 - SIDE_NOTE_GAP
            _min_note_x = min(_min_note_x, _nx)  # type: ignore[assignment]
        elif _npos == "right_of" and _nprimary in _p_index:
            _nx = _cx(_nprimary) + SIDE_NOTE_GAP
            _max_note_x = max(_max_note_x, _nx + _box_hw(_nprimary) * 2)
    if _min_note_x < PAD_H:
        _cx_offset[0] = PAD_H - _min_note_x
        _max_note_x += _cx_offset[0]
        canvas_w += _cx_offset[0]
    if _max_note_x > canvas_w - PAD_H:
        canvas_w = _max_note_x + PAD_H

    # ── SEQ-008: per-fragment x bounds ────────────────────────────────────────
    def _frag_x_bounds(it: dict) -> "tuple[float, float]":
        fparts = it.get("frag_parts", set())
        valid = [p for p in fparts if p in _p_index] if fparts else []
        if valid:
            left_p = min(valid, key=lambda p: _p_index[p])
            right_p = max(valid, key=lambda p: _p_index[p])
            return (
                float(_cx(left_p)) - _box_hw(left_p) - PAD_H / 2,
                float(_cx(right_p)) + _box_hw(right_p) + PAD_H / 2,
            )
        l_p = participants[0] if participants else ""
        r_p = participants[-1] if participants else ""
        return (
            float(_cx(l_p)) - _box_hw(l_p) - PAD_H / 2,
            float(_cx(r_p)) + _box_hw(r_p) + PAD_H / 2,
        )

    # Precompute else→parent fragment x bounds so labels/separators use parent bounds
    _else_x: "dict[int, tuple[float, float]]" = {}
    _bstk_else: "list[int]" = []
    for _bi, _bit in enumerate(items):
        if _bit["type"] in ("block", "rect"):
            _bstk_else.append(_bi)
        elif _bit["type"] == "block_end" and _bstk_else:
            _bstk_else.pop()
        elif _bit["type"] == "else":
            if _bstk_else:
                _else_x[_bi] = _frag_x_bounds(items[_bstk_else[-1]])
            else:
                _lp = participants[0] if participants else ""
                _rp = participants[-1] if participants else ""
                _else_x[_bi] = (
                    float(_cx(_lp)) - _box_hw(_lp) - PAD_H / 2,
                    float(_cx(_rp)) + _box_hw(_rp) + PAD_H / 2,
                )

    # ── T7: self-loop geometry pre-pass (canvas expansion + data collection) ──
    _SELF_LOOP_STYLE = TextStyle(font_size=10)
    _self_loop_data: "dict[int, tuple[float, float, float]]" = {}  # msg_idx → (ax_right, loop_w, ry)
    _sl_row = 0
    for _sl_i, _sl_it in enumerate(items):
        if _sl_it["type"] in _row_types:
            if _sl_it["type"] == "msg" and _sl_it["src"] == _sl_it["dst"]:
                _sl_ry = float(ll_top + _row_top_list[_sl_row] + _row_h_list[_sl_row] // 2)
                _sl_ax = activation_bounds_at(_sl_it["src"], _sl_ry)[1]
                _sl_lbl = _sl_it.get("label", "")
                _sl_lw = max(36, int(math.ceil(
                    _MEASURER.layout(_sl_lbl, _SELF_LOOP_STYLE, max_width=None).max_content_width
                )) + 16) if _sl_lbl else 36
                _self_loop_data[_sl_i] = (_sl_ax, _sl_lw, _sl_ry)
                _needed = _sl_ax + _sl_lw + PAD_H
                if _needed > canvas_w:
                    canvas_w = int(math.ceil(_needed))
            _sl_row += 1

    # ── Geometry accumulators (T7) ────────────────────────────────────────────
    _geom_self_loops: "list[tuple[float,float,float,float]]" = []
    _geom_msg_endpoints: "list[tuple[float,float,float,float]]" = []
    _geom_msg_ys: "list[float]" = []
    _geom_note_bounds: "list[tuple[float,float,float,float]]" = []
    _geom_frag_bounds: "list[tuple[str,float,float,float,float]]" = []
    _geom_branch_bounds: "list[tuple[str,float,float,float,float]]" = []
    _geom_marker_bounds: "list[tuple[float,float,float,float]]" = []
    # ── Typed geometry IR accumulators (T3b) ─────────────────────────────────
    _typed_participants: "list[ParticipantGeometry]" = []
    _typed_messages: "list[MessageGeometry]" = []
    _typed_activations: "list[ActivationGeometry]" = []
    _typed_notes: "list[NoteGeometry]" = []
    _typed_fragments: "list[FragmentGeometry]" = []
    _typed_branches: "list[BranchGeometry]" = []
    _msg_ctr = 0

    # ─────────────────────────────────────────────────────────────────────────
    # HTML EMISSION
    # ─────────────────────────────────────────────────────────────────────────
    _canvas_w_int = int(round(canvas_w))
    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout diagram-lifeline" style="'
        f'position:relative;width:{_canvas_w_int}px;height:{canvas_h}px;">'
    )
    _seq_box_css = (
        f'display:flex;align-items:center;justify-content:center;'
        f'border:1.5px solid var(--node-border,var(--card-border,#DAD7CE));'
        f'border-radius:var(--node-radius,8px);box-sizing:border-box;overflow:hidden;'
        f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
        f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));'
    )
    _seq_label_css = (
        f'font-size:13px;font-weight:700;color:var(--node-fg,var(--text-primary,#191A17));'
        f'white-space:nowrap;'
        f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));'
    )
    _x_markers: "list[tuple[float, float]]" = []  # (cx, y) for destroyed participants
    # ── Box group backgrounds (lowest z-order, render before participants) ─────
    for _bg in _all_box_groups:
        _bm = [p for p in _bg["members"] if p in _p_index]
        if not _bm:
            continue
        _lo_p = min(_bm, key=lambda p: _p_index[p])
        _hi_p = max(_bm, key=lambda p: _p_index[p])
        _bx0 = float(_cx(_lo_p)) - _box_hw(_lo_p) - PAD_H / 2 - 4
        _bx1 = float(_cx(_hi_p)) + _box_hw(_hi_p) + PAD_H / 2 + 4
        _bcolor = _h(_bg["color"])
        _blabel = _h(_bg["label"])
        parts.append(
            f'<div style="position:absolute;left:{_bx0:.1f}px;top:0px;'
            f'width:{_bx1 - _bx0:.1f}px;height:{canvas_h}px;'
            f'background:{_bcolor};opacity:0.2;border:1px solid {_bcolor};'
            f'box-sizing:border-box;" data-box-group="true"></div>'
        )
        if _blabel:
            parts.append(
                f'<span style="position:absolute;left:{_bx0:.1f}px;top:4px;'
                f'width:{_bx1 - _bx0:.1f}px;text-align:center;'
                f'font-size:10px;font-weight:700;color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
                f'{_blabel}</span>'
            )
    for pid in participants:
        _bw = int(round(_box_hw(pid) * 2))
        lx = int(round(_cx(pid) - _box_hw(pid)))
        _lbl_str = p_label.get(pid, pid)
        lbl = _h(_lbl_str)
        _p_created_row = _created_at.get(pid)
        _p_destroyed_row = _destroyed_at.get(pid)

        # Lifecycle: compute adjusted lifeline top/bottom
        if _p_created_row is not None and _p_created_row < len(_row_top_list):
            _ll_top_pid = ll_top + _row_top_list[_p_created_row]
        else:
            _ll_top_pid = ll_top
        if _p_destroyed_row is not None and _p_destroyed_row < len(_row_top_list):
            _destroy_y = ll_top + _row_top_list[_p_destroyed_row] + _row_h_list[_p_destroyed_row] // 2
            _ll_bot_pid = _destroy_y
        else:
            _destroy_y = None
            _ll_bot_pid = ll_bot

        _top_box_y = _ll_top_pid - BOX_H if _p_created_row is not None and _ll_top_pid > ll_top else PAD_V
        _typed_participants.append(ParticipantGeometry(
            participant_id=pid, label=_lbl_str, center_x=float(_cx(pid)),
            top_box=Bounds(float(lx), float(_top_box_y), float(lx + _bw), float(_top_box_y + BOX_H)),
            bottom_box=Bounds(float(lx), float(_ll_bot_pid), float(lx + _bw), float(_ll_bot_pid + BOX_H)),
            lifeline_top=float(_ll_top_pid), lifeline_bottom=float(_ll_bot_pid),
            created_at_row=_p_created_row,
            destroyed_at_row=_p_destroyed_row,
        ))
        # Top box: placed at creation row (mid-diagram) or at diagram top (normal)
        parts.append(
            f'<div class="node node-rect" data-node-id="{_h(pid)}" style="'
            f'position:absolute;left:{lx}px;top:{int(round(_top_box_y))}px;'
            f'width:{_bw}px;height:{BOX_H}px;{_seq_box_css}">'
            f'<span class="node-label" style="{_seq_label_css}">{lbl}</span></div>'
        )
        # Bottom box: only for non-destroyed participants
        if _destroy_y is None:
            parts.append(
                f'<div class="node node-rect node-lifeline-bottom" data-node-id="{_h(pid)}-bottom" style="'
                f'position:absolute;left:{lx}px;top:{ll_bot}px;'
                f'width:{_bw}px;height:{BOX_H}px;{_seq_box_css}">'
                f'<span class="node-label" style="{_seq_label_css}">{lbl}</span></div>'
            )
        else:
            _x_markers.append((float(_cx(pid)), _destroy_y))

    parts.append(
        f'<svg style="position:absolute;inset:0;width:{_canvas_w_int}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    _seq_edge = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"

    # ── Pass A: fragment background rects ─────────────────────────────────────
    _rp_a = 0
    for _bi_a, it in enumerate(items):
        if it["type"] in ("block", "rect"):
            x0, x1 = _frag_x_bounds(it)
            ry = ll_top + _row_top_list[_rp_a]
            bh = sum(_row_h_list[_rp_a: _rp_a + it.get("span", 1)])
            span = it.get("span", 1)
            if it["type"] == "rect":
                color = _h(it.get("label", "") or "rgba(200,200,200,0.3)")
                # T11: don't add opacity when fill already has rgba() — avoids double-alpha
                _rect_opacity = "" if "rgba(" in color.lower() else ' opacity="0.3"'
                parts.append(
                    f'<rect x="{x0}" y="{ry}" width="{x1 - x0}" height="{bh}" '
                    f'fill="{color}"{_rect_opacity} rx="3"/>'
                )
            else:
                fid = _frag_id.get(_bi_a, "")
                pids_str = " ".join(sorted(it.get("frag_parts", set())))
                parts.append(
                    f'<rect x="{x0}" y="{ry}" width="{x1 - x0}" height="{bh}" '
                    f'data-fragment-id="{fid}" data-fragment-kind="{_h(it["kw"])}" '
                    f'data-participants="{_h(pids_str)}" '
                    f'data-start-event="{_rp_a}" data-end-event="{_rp_a + span}" '
                    f'fill="var(--node-bg-from,var(--card-bg-from,#ffffff))" opacity="0.5" '
                    f'stroke="{_seq_edge}" stroke-width="1" stroke-dasharray="5 3" rx="3"/>'
                )
                _geom_frag_bounds.append((fid, float(x0), float(ry), float(x1 - x0), float(bh)))
                _typed_fragments.append(FragmentGeometry(
                    fragment_id=fid, kind=it["kw"].lower(),
                    participant_ids=tuple(sorted(it.get("frag_parts", set()))),
                    bounds=Bounds(float(x0), float(ry), float(x1), float(ry + bh)),
                    header_text=(it.get("kw", "") + (" " + it.get("label", "") if it.get("label") else "")).strip(),
                ))
        if it["type"] in _row_types:
            _rp_a += 1

    # ── Lifeline dashes ────────────────────────────────────────────────────────
    for pg in _typed_participants:
        lx = int(round(pg.center_x))
        _lly1 = int(round(pg.lifeline_top))
        _lly2 = int(round(pg.lifeline_bottom))
        parts.append(
            f'<line x1="{lx}" y1="{_lly1}" x2="{lx}" y2="{_lly2}" '
            f'stroke="{_seq_edge}" stroke-width="1" stroke-dasharray="5 4"/>'
        )
    # ── Destroy X markers ────────────────────────────────────────────────────
    _XA = 8  # half-arm length of X marker
    for _xcx, _xy in _x_markers:
        parts.append(
            f'<line x1="{_xcx - _XA}" y1="{_xy - _XA}" x2="{_xcx + _XA}" y2="{_xy + _XA}" '
            f'stroke="{_seq_edge}" stroke-width="2"/>'
        )
        parts.append(
            f'<line x1="{_xcx + _XA}" y1="{_xy - _XA}" x2="{_xcx - _XA}" y2="{_xy + _XA}" '
            f'stroke="{_seq_edge}" stroke-width="2"/>'
        )

    # ── SEQ-006: activation bars with exact y baselines ───────────────────────
    for _pid, _sy, _ey, _depth in _act_spans_v2:
        _cx_pid = _cx(_pid)
        _ax = _cx_pid - ACTIVATION_W // 2 + _depth * ACTIVATION_DX
        _act_h = max(4, _ey - _sy)
        parts.append(
            f'<rect x="{_ax}" y="{_sy}" width="{ACTIVATION_W}" height="{_act_h}" '
            f'fill="var(--edge-strong,var(--accent-1,#60a5fa))" opacity="0.35" rx="2"'
            f' data-pid="{_h(_pid)}"/>'
        )
        _typed_activations.append(ActivationGeometry(
            activation_id=f"act-{_pid}-{int(_sy)}",
            participant_id=_pid, start_y=float(_sy), end_y=float(_ey), depth=_depth,
            bounds=Bounds(float(_ax), float(_sy), float(_ax + ACTIVATION_W), float(_sy + _act_h)),
            was_implicitly_closed=(_pid, _sy, _depth) in _implicitly_closed,
        ))

    # ── Arrow marker helper ────────────────────────────────────────────────────
    def _draw_marker(marker: "Optional[str]", x: float, y: float, dirn: int) -> str:
        xi, yi = int(round(x)), int(round(y))
        if marker == "triangle":
            ah = _arrowhead(xi, yi, dirn, 0, back=10, half_w=6)
            return f'<polygon points="{ah}" fill="{_seq_edge}"/>'
        if marker == "cross":
            sz = 6
            return (
                f'<line x1="{xi - dirn * sz}" y1="{yi - sz}" x2="{xi}" y2="{yi + sz}" '
                f'stroke="{_seq_edge}" stroke-width="1.5"/>'
                f'<line x1="{xi - dirn * sz}" y1="{yi + sz}" x2="{xi}" y2="{yi - sz}" '
                f'stroke="{_seq_edge}" stroke-width="1.5"/>'
            )
        if marker == "point":
            return (
                f'<circle cx="{xi}" cy="{yi}" r="4" fill="none" '
                f'stroke="{_seq_edge}" stroke-width="1.5"/>'
            )
        if marker == "filled_head":
            # Half-arrowhead matching Mermaid 11.15 #filled-head marker.
            # Path M 18,7 L9,13 L14,7 L9,1 Z scaled to renderer marker size.
            # dirn=1 → pointing right (end marker); dirn=-1 → pointing left (start marker).
            sz = 7
            if dirn == 1:  # pointing right
                pts = (
                    f"{xi},{yi} "
                    f"{xi - sz},{yi + sz // 2 + 1} "
                    f"{xi - sz // 2},{yi} "
                    f"{xi - sz},{yi - sz // 2 - 1}"
                )
            else:  # pointing left
                pts = (
                    f"{xi},{yi} "
                    f"{xi + sz},{yi + sz // 2 + 1} "
                    f"{xi + sz // 2},{yi} "
                    f"{xi + sz},{yi - sz // 2 - 1}"
                )
            return f'<polygon points="{pts}" fill="{_seq_edge}"/>'
        return ""

    # ── Pass B: else separators, note polygons, message lines + markers ───────
    row = 0
    for _bi, it in enumerate(items):
        if it["type"] == "block" or it["type"] == "rect":
            row += 1; continue
        if it["type"] == "else":
            _fb_lp = participants[0] if participants else ""
            _fb_rp = participants[-1] if participants else ""
            x0, x1 = _else_x.get(_bi, (
                float(_cx(_fb_lp)) - _box_hw(_fb_lp) - PAD_H / 2,
                float(_cx(_fb_rp)) + _box_hw(_fb_rp) + PAD_H / 2,
            ))
            ry = ll_top + _row_top_list[row]
            branch_cond = it.get("label", "")
            parts.append(
                f'<line x1="{x0}" y1="{ry}" x2="{x1}" y2="{ry}" '
                f'data-branch-condition="{_h(branch_cond)}" '
                f'stroke="{_seq_edge}" stroke-width="1" stroke-dasharray="4 4"/>'
            )
            _par_fid = _branch_parent_id.get(_bi, "")
            _geom_branch_bounds.append((_par_fid, float(x0), float(ry), float(x1 - x0), 1.0))
            _typed_branches.append(BranchGeometry(
                branch_id=f"branch-{len(_typed_branches)}",
                parent_fragment_id=_par_fid,
                label=branch_cond,
                bounds=Bounds(float(x0), float(ry), float(x1), float(ry + 1.0)),
            ))
            row += 1; continue
        if it["type"] == "note":
            nx, ny, nw, nh = _note_geom(it, row)
            fold = 10
            pts = (f"{nx},{ny} {nx + nw - fold},{ny} {nx + nw},{ny + fold} "
                   f"{nx + nw},{ny + nh} {nx},{ny + nh}")
            parts.append(
                f'<polygon points="{pts}" '
                f'fill="var(--node-bg-from,var(--card-bg-from,#ffffff))" '
                f'stroke="{_seq_edge}" stroke-width="1"/>'
            )
            _geom_note_bounds.append((float(nx), float(ny), float(nw), float(nh)))
            _note_pids = it.get("pids") or ([it.get("pid", "")] if it.get("pid") else [])
            _typed_notes.append(NoteGeometry(
                note_id=f"note-{len(_typed_notes)}",
                participant_ids=tuple(_note_pids),
                placement=it.get("pos", "over").replace("_", " "),
                bounds=Bounds(float(nx), float(ny), float(nx + nw), float(ny + nh)),
            ))
            row += 1; continue
        if it["type"] in ("activate", "deactivate", "block_end"):
            continue
        if it["type"] != "msg":
            continue

        # T11: strict participant lookup — unknown names emit Diagnostic and skip
        _msg_src, _msg_dst = it.get("src", ""), it.get("dst", "")
        for _unknown in [p for p in (_msg_src, _msg_dst) if p and p not in _p_index]:
            _diagnostics.append(Diagnostic(
                feature="unknown_participant",
                line_number=0,
                source_text=f"{_unknown}",
            ))
        if _msg_src not in _p_index or _msg_dst not in _p_index:
            row += 1; continue

        ry = ll_top + _row_top_list[row] + _row_h_list[row] // 2
        _geom_msg_ys.append(float(ry))
        arrow = it.get("arrow", "->>")
        spec = _ARROW_SPECS.get(arrow, _ARROW_SPECS["->>"])
        dash = ' stroke-dasharray="6 4"' if spec["dashed"] else ""
        # SEQ-007: activation-aware endpoints
        sx, dx2 = _msg_endpoints(_msg_src, _msg_dst, ry)

        if _msg_src == _msg_dst:
            # T7: anchor self-loop at right edge of active activation bar (or lifeline cx)
            sl_data = _self_loop_data.get(_bi)
            if sl_data:
                ax_right, loop_w, _sl_ry = sl_data
            else:
                ax_right = activation_bounds_at(_msg_src, ry)[1]
                loop_w = 36
            loop_top = ry - 8
            loop_bot = ry + 8
            parts.append(
                f'<path d="M {ax_right} {loop_top} C {ax_right + loop_w} {loop_top} '
                f'{ax_right + loop_w} {loop_bot} {ax_right} {loop_bot}" '
                f'stroke="{_seq_edge}" fill="none" stroke-width="1.5"{dash}'
                f' data-src="{_h(_msg_src)}" data-dst="{_h(_msg_dst)}"/>'
            )
            parts.append(_draw_marker(spec["end_m"], ax_right, loop_bot, -1))
            if spec.get("start_m"):  # bidirectional self-message (AC-5.6)
                parts.append(_draw_marker(spec["start_m"], ax_right, loop_top, 1))
            _geom_self_loops.append((float(ax_right), float(loop_top), float(loop_w), 16.0))
            _geom_msg_endpoints.append((float(ax_right), float(loop_top), float(ax_right), float(loop_bot)))
            _typed_messages.append(MessageGeometry(
                event_id=f"msg-{_msg_ctr}",
                source_id=_msg_src, destination_id=_msg_dst,
                baseline_y=float(ry), source_x=float(ax_right), destination_x=float(ax_right),
                label_x=float(ax_right + loop_w / 2), arrow_token=arrow, is_self_message=True,
                path_bounds=Bounds(float(ax_right), float(loop_top),
                                   float(ax_right + loop_w), float(loop_bot)),
                start_marker=spec.get("start_m"), end_marker=spec.get("end_m"),
            ))
            _msg_ctr += 1
        else:
            parts.append(
                f'<line x1="{sx}" y1="{ry}" x2="{dx2}" y2="{ry}" '
                f'stroke="{_seq_edge}" stroke-width="1.5"{dash}'
                f' data-src="{_h(_msg_src)}" data-dst="{_h(_msg_dst)}"/>'
            )
            dirn = 1 if dx2 > sx else -1
            parts.append(_draw_marker(spec["end_m"], dx2, ry, dirn))
            if spec["start_m"]:  # bidirectional (SEQ-012)
                parts.append(_draw_marker(spec["start_m"], sx, ry, -dirn))
            _geom_msg_endpoints.append((float(sx), float(ry), float(dx2), float(ry)))
            _typed_messages.append(MessageGeometry(
                event_id=f"msg-{_msg_ctr}",
                source_id=_msg_src, destination_id=_msg_dst,
                baseline_y=float(ry), source_x=float(sx), destination_x=float(dx2),
                label_x=float((sx + dx2) / 2), arrow_token=arrow, is_self_message=False,
                path_bounds=Bounds(min(float(sx), float(dx2)), float(ry) - 1.0,
                                   max(float(sx), float(dx2)), float(ry) + 1.0),
                start_marker=spec.get("start_m"), end_marker=spec.get("end_m"),
            ))
            _msg_ctr += 1
        row += 1

    parts.append('</svg>')

    # ── Pass C: keyword labels, else labels, note texts, edge labels (HTML) ───
    row = 0
    for _bi, it in enumerate(items):
        if it["type"] in ("block", "rect"):
            ry = ll_top + _row_top_list[row]
            if it["type"] == "block":
                x0, x1 = _frag_x_bounds(it)
                _lbl_w = max(1, int(x1 - x0) - 8)
                parts.append(
                    f'<span style="position:absolute;left:{x0 + 4}px;top:{ry + 3}px;'
                    f'max-width:{_lbl_w}px;overflow-wrap:break-word;'
                    f'font-size:10px;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.08em;'
                    f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                    f'font-family:var(--label-font,var(--font-primary,'
                    f'-apple-system,Inter,sans-serif));">'
                    f'{_h(it["kw"])}{" " + _h(it["label"]) if it["label"] else ""}</span>'
                )
            row += 1; continue
        if it["type"] == "else":
            ry = ll_top + _row_top_list[row]
            if it["label"]:
                _el_lp = participants[0] if participants else ""
                x0, _ = _else_x.get(_bi, (
                    float(_cx(_el_lp)) - _box_hw(_el_lp) - PAD_H / 2,
                    0.0,
                ))
                parts.append(
                    f'<span style="position:absolute;left:{x0 + 4}px;top:{ry + 3}px;'
                    f'font-size:10px;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.08em;'
                    f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                    f'font-family:var(--label-font,var(--font-primary,'
                    f'-apple-system,Inter,sans-serif));">'
                    f'{_h(it.get("kw", "else"))} {_h(it["label"])}</span>'
                )
            row += 1; continue
        if it["type"] == "note":
            nx, ny, nw, nh = _note_geom(it, row)
            parts.append(
                f'<span style="position:absolute;left:{nx}px;top:{ny + 4}px;'
                f'width:{nw}px;font-size:10px;text-align:center;overflow:hidden;'
                f'overflow-wrap:break-word;'
                f'color:var(--node-fg,var(--text-primary,#191A17));'
                f'font-family:var(--label-font,var(--font-primary,'
                f'-apple-system,Inter,sans-serif));">'
                f'{_h(it["text"])}</span>'
            )
            row += 1; continue
        if it["type"] not in ("msg",):
            continue
        _lbl_src, _lbl_dst = it.get("src", ""), it.get("dst", "")
        if _lbl_src not in _p_index or _lbl_dst not in _p_index:
            row += 1; continue
        ry = ll_top + _row_top_list[row] + _row_h_list[row] // 2
        # T11: center label over activation-adjusted segment midpoint, not bare lifeline cx
        if _lbl_src == _lbl_dst:
            sx_lbl = float(_cx(_lbl_src))
            dx_lbl = sx_lbl
        else:
            sx_lbl, dx_lbl = _msg_endpoints(_lbl_src, _lbl_dst, float(ry))
        lbl = _h(it["label"])
        if lbl:
            mid_x = int((sx_lbl + dx_lbl) / 2)
            parts.append(
                f'<span class="edge-label" '
                f'data-src="{_h(it["src"])}" data-dst="{_h(it["dst"])}" '
                f'data-edge-label="{lbl}" '
                f'style="position:absolute;'
                f'left:{mid_x}px;top:{ry - 18}px;transform:translateX(-50%);'
                f'font-size:11px;color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                f'font-family:var(--label-font,var(--font-primary,'
                f'-apple-system,Inter,sans-serif));'
                f'background:var(--node-bg-from,var(--card-bg-from,#ffffff));'
                f'padding:0 3px;white-space:nowrap;">{lbl}</span>'
            )
        row += 1
    parts.append('</div>')
    _geom = SequenceGeometry(
        participant_centers=tuple((p, float(_cx(p))) for p in participants),
        lifeline_x=tuple((p, float(_cx(p))) for p in participants),
        activation_bars=tuple((_pid, float(_sy), float(_ey)) for _pid, _sy, _ey, _ in _act_spans_v2),
        message_ys=tuple(_geom_msg_ys),
        message_endpoints=tuple(_geom_msg_endpoints),
        fragment_bounds=tuple(_geom_frag_bounds),
        branch_separator_bounds=tuple(_geom_branch_bounds),
        note_bounds=tuple(_geom_note_bounds),
        self_loop_bounds=tuple(_geom_self_loops),
        label_bounds=(),
        marker_bounds=tuple(_geom_marker_bounds),
        canvas=(float(canvas_w), float(canvas_h)),
        diagnostics=tuple(_diagnostics),
        participants=tuple(_typed_participants),
        messages=tuple(_typed_messages),
        activations=tuple(_typed_activations),
        notes=tuple(_typed_notes),
        fragments=tuple(_typed_fragments),
        branches=tuple(_typed_branches),
    )
    return "\n".join(parts), _geom


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

def compile_sequence(
    source: str,
    *,
    width_hint: int = 0,
    height_hint: int = 0,
    theme: "str | None" = None,
) -> "SequenceCompileResult":
    """Compile a sequenceDiagram exactly once and return a SequenceCompileResult.

    Both _dispatch (rendering) and _dispatch_validate (validation) consume this
    result so _layout_lifeline is called at most once per source string.
    T1: scale=1.0, rendered_width=natural_width.
    T2: fills scale and CSS-transform viewport when width_hint < natural_width.
    """
    from ._geometry import SequenceCompileResult, SequenceDiagnostic  # noqa: PLC0415
    clean = _strip_frontmatter(source)
    # Always render at natural size; CSS transform scales the viewport.
    html, geom = _layout_lifeline(clean, "LR", 0)
    natural_w = float(geom.canvas[0]) if geom.canvas else 0.0
    natural_h = float(geom.canvas[1]) if geom.canvas else 0.0
    # Compute uniform CSS-transform scale (T2, AC-2.5).
    w_scale = (width_hint / natural_w) if (width_hint and natural_w > 0) else 1.0
    h_scale = (height_hint / natural_h) if (height_hint and natural_h > 0) else 1.0
    scale = min(1.0, w_scale, h_scale)
    if scale < 1.0:
        rendered_w = round(natural_w * scale, 2)
        rendered_h = round(natural_h * scale, 2)
        html = (
            f'<div class="sequence-viewport" style="'
            f'position:relative;width:{rendered_w}px;height:{rendered_h}px;overflow:hidden;">'
            f'<div class="sequence-natural-stage" style="'
            f'position:absolute;top:0;left:0;'
            f'width:{natural_w}px;height:{natural_h}px;'
            f'transform:scale({scale:.6g});transform-origin:top left;">'
            f'{html}'
            f'</div></div>'
        )
    else:
        rendered_w = natural_w
        rendered_h = natural_h
        scale = 1.0
    # Lift legacy Diagnostic objects to SequenceDiagnostic for uniform access.
    seq_diags: "tuple[SequenceDiagnostic, ...]" = tuple(
        SequenceDiagnostic(
            severity="warning",
            code=d.feature or "unsupported_construct",
            message=d.source_text or d.feature or "",
            feature=d.feature,
            line_number=d.line_number,
            source_text=d.source_text,
        )
        for d in geom.diagnostics
    )
    return SequenceCompileResult(
        html=html,
        geometry=geom,
        natural_width=natural_w,
        natural_height=natural_h,
        scale=scale,
        rendered_width=rendered_w,
        rendered_height=rendered_h,
        diagnostics=seq_diags,
    )


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

    # Unknown directive — graph-topology best-effort fallback
    try:
        return _layout_graph_topology(
            clean, direction, width_hint, style_overrides=style_overrides,
        )
    except Exception:
        raise ValueError(f"Unsupported or unrecognised Mermaid directive: '{directive}'")


def _validate_sequence_geometry(geom: "SequenceGeometry") -> "list[str]":
    """Check 11 geometric invariants on a SequenceGeometry.  Returns a list of
    violation strings; empty means geometry="pass"."""
    from ._geometry import SequenceGeometry  # noqa: PLC0415
    violations: list[str] = []

    cw, ch = geom.canvas
    lx = [x for _, x in geom.lifeline_x]

    # INV-1: canvas dimensions positive
    if cw <= 0 or ch <= 0:
        violations.append(f"INV-1: canvas {cw}×{ch} not positive")

    # INV-2: all lifeline x-coords within canvas
    for pid, x in geom.lifeline_x:
        if not (0 <= x <= cw + 1):  # +1 tolerance for rounding
            violations.append(f"INV-2: lifeline '{pid}' x={x} outside canvas w={cw}")

    # INV-3: lifeline centers strictly increasing (left→right order preserved)
    for i in range(len(lx) - 1):
        if lx[i] >= lx[i + 1]:
            pid_a = geom.lifeline_x[i][0]
            pid_b = geom.lifeline_x[i + 1][0]
            violations.append(
                f"INV-3: lifelines not left-to-right: '{pid_a}'@{lx[i]} >= '{pid_b}'@{lx[i + 1]}"
            )

    # INV-4: adjacent lifelines separated by at least 20 px (no overlap)
    for i in range(len(lx) - 1):
        gap = lx[i + 1] - lx[i]
        if gap < 20:
            pid_a = geom.lifeline_x[i][0]
            pid_b = geom.lifeline_x[i + 1][0]
            violations.append(f"INV-4: lifelines '{pid_a}'–'{pid_b}' overlap (gap={gap:.1f}px)")

    # INV-5: message_ys count matches message_endpoints count
    if len(geom.message_ys) != len(geom.message_endpoints):
        violations.append(
            f"INV-5: message_ys ({len(geom.message_ys)}) ≠ message_endpoints ({len(geom.message_endpoints)})"
        )

    # INV-6: message y-coordinates are monotonically non-decreasing
    for i in range(len(geom.message_ys) - 1):
        if geom.message_ys[i] > geom.message_ys[i + 1] + 0.5:  # 0.5 rounding tolerance
            violations.append(
                f"INV-6: message_ys not monotone at index {i}: {geom.message_ys[i]:.1f} > {geom.message_ys[i + 1]:.1f}"
            )

    # INV-7: message endpoints within canvas bounds
    for i, (sx, sy, dx, dy) in enumerate(geom.message_endpoints):
        for coord, name in ((sx, "sx"), (dx, "dx")):
            if not (-1 <= coord <= cw + 1):
                violations.append(f"INV-7: msg[{i}].{name}={coord:.1f} outside canvas w={cw}")
        for coord, name in ((sy, "sy"), (dy, "dy")):
            if not (-1 <= coord <= ch + 1):
                violations.append(f"INV-7: msg[{i}].{name}={coord:.1f} outside canvas h={ch}")

    # INV-8: note bounds within canvas width (x >= 0 and x+w <= canvas_w + tolerance)
    for i, (nx, ny, nw, nh) in enumerate(geom.note_bounds):
        if nx < -1:
            violations.append(f"INV-8: note[{i}] left edge {nx:.1f} < 0")
        if nx + nw > cw + 2:
            violations.append(f"INV-8: note[{i}] right edge {nx + nw:.1f} > canvas w={cw}")

    # INV-9: self-loop bounds within canvas (must not overflow right edge)
    for i, (slx, sly, slw, slh) in enumerate(geom.self_loop_bounds):
        if slx + slw > cw + 2:
            violations.append(f"INV-9: self_loop[{i}] right edge {slx + slw:.1f} > canvas w={cw}")

    # INV-10: fragment bounds within canvas width
    for fid, fx, fy, fw, fh in geom.fragment_bounds:
        if fx < -1:
            violations.append(f"INV-10: fragment '{fid}' left edge {fx:.1f} < 0")
        if fx + fw > cw + 2:
            violations.append(f"INV-10: fragment '{fid}' right edge {fx + fw:.1f} > canvas w={cw}")

    # INV-11: activation bar top < bottom (no inverted bars)
    for pid, top_y, bot_y in geom.activation_bars:
        if top_y > bot_y + 0.5:
            violations.append(f"INV-11: activation bar for '{pid}' inverted: top={top_y:.1f} > bot={bot_y:.1f}")

    return violations


def validate_sequence_geometry(
    geom: "SequenceGeometry",
) -> "SequenceValidationResult":
    """Public API: run structural + semantic validation on a SequenceGeometry.

    Returns SequenceValidationResult with independent structural_geometry and
    semantic_geometry lanes plus collected errors/warnings (AC-4.1, AC-4.2, AC-4.3).
    """
    from ._geometry import SequenceValidationResult  # noqa: PLC0415

    struct_violations: "list[str]" = list(_validate_sequence_geometry(geom))

    # Structural checks on typed geometry records (AC-4.2 extension)
    for act in geom.activations:
        if act.end_y < act.start_y - 0.5:
            struct_violations.append(
                f"STRUCT: activation '{act.activation_id}' inverted end_y={act.end_y} < start_y={act.start_y}"
            )
        if act.bounds.right < act.bounds.left or act.bounds.bottom < act.bounds.top:
            struct_violations.append(
                f"STRUCT: activation '{act.activation_id}' has non-positive bounds"
            )
    for frag in geom.fragments:
        if frag.bounds.right < frag.bounds.left or frag.bounds.bottom < frag.bounds.top:
            struct_violations.append(
                f"STRUCT: fragment '{frag.fragment_id}' has non-positive bounds"
            )
    for branch in geom.branches:
        if branch.bounds.right < branch.bounds.left:
            struct_violations.append(
                f"STRUCT: branch '{branch.branch_id}' has negative width"
            )

    # Semantic checks (AC-4.3)
    sem_violations: "list[str]" = []
    frag_id_set = {f.fragment_id for f in geom.fragments}
    registered_pids = {p.participant_id for p in geom.participants}
    participant_lifeline_bottom: "dict[str, float]" = {
        p.participant_id: p.lifeline_bottom for p in geom.participants
    }

    # Branch parent_fragment_id must be non-empty and in fragment_id set
    for branch in geom.branches:
        if not branch.parent_fragment_id:
            sem_violations.append(
                f"SEM: branch '{branch.branch_id}' has empty parent_fragment_id"
            )
        elif branch.parent_fragment_id not in frag_id_set:
            sem_violations.append(
                f"SEM: branch '{branch.branch_id}' parent '{branch.parent_fragment_id}' not in fragments"
            )

    # Note participants must be registered
    for note in geom.notes:
        for pid in note.participant_ids:
            if pid and pid not in registered_pids:
                sem_violations.append(
                    f"SEM: note '{note.note_id}' references unregistered participant '{pid}'"
                )

    # was_implicitly_closed activations should extend near lifeline_bottom
    for act in geom.activations:
        if act.was_implicitly_closed:
            ll_bot = participant_lifeline_bottom.get(act.participant_id)
            if ll_bot is not None and abs(act.end_y - ll_bot) > 3:
                sem_violations.append(
                    f"SEM: implicitly-closed activation '{act.activation_id}' "
                    f"end_y={act.end_y} not at lifeline_bottom={ll_bot}"
                )

    structural_status = "fail" if struct_violations else "pass"
    semantic_status = "fail" if sem_violations else "pass"
    all_warnings = tuple(struct_violations + sem_violations)
    return SequenceValidationResult(
        structural_geometry=structural_status,
        semantic_geometry=semantic_status,
        errors=(),
        warnings=all_warnings,
    )


def _dispatch_validate(src: str) -> "ValidationResult":
    """Validate Mermaid source including geometry invariants."""
    from ._geometry import ValidationResult
    clean = _strip_frontmatter(src)
    directive, _ = _detect_directive(clean)
    d = directive.lower()

    if d == "sequencediagram":
        try:
            compiled = compile_sequence(clean)
        except Exception as exc:
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
        except Exception as exc:
            return ValidationResult(
                render="fail",
                syntax_coverage="fail",
                geometry="unvalidated",
                errors=(str(exc),),
            )
        return compiled_fc.validation

    return ValidationResult(geometry="unvalidated")


# ── CLI ───────────────────────────────────────────────────────────────────────
