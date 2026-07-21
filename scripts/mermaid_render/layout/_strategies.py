from __future__ import annotations

import math
import re
from dataclasses import dataclass
from html import escape as _h
from typing import Optional


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

from ._constants import (
    _Node, _Edge, _Group,
    NODE_CAP, EDGE_CAP, GROUP_CAP,
    NODE_W, NODE_H, COL_GAP, RANK_GAP, CANVAS_PAD,
    GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT,
    _ARCH_ICON_MAP, _LABEL_ICON_KEYWORDS,
    _KNOWN_DIRECTIVES, _GRAPH_DIRECTIVES,
    _node_render_h,
    _TERMINAL_NODE_SIZE, _is_terminal_circle,
)
from ._parser import _parse_graph_source, _detect_directive, _strip_frontmatter, _parse_init_config
from ._layout import _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates, _compact_group_columns, _group_coherent_cols, _apply_inner_direction_positions
from ._routing import _route_edges, _arrowhead
from ._c4 import _render_c4_fragment, C4Item, C4Relationship, C4Boundary
from ._renderer import (
    _render_graph_fragment,
    _extract_diagram_title, _render_metadata_chip, _render_legend,
    _separate_groups_lr,
    _separate_groups_tb,
    _push_nonmembers_out_of_groups_lr,
)

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


# ── graph topology strategy ──────────────────────────────────────────────────

def _layout_graph_topology(
    src: str, direction: str, width_hint: int, height_hint: int = 0,
    style_overrides: str = "",
    opts: "RenderOptions | None" = None,
) -> str:
    _opts = opts if opts is not None else RenderOptions()
    lines = src.splitlines()
    # Skip up to and including the directive line (first non-blank, non-comment line)
    directive_index = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith(("%%", "//")):
            directive_index = i
            break
    content_lines = lines[directive_index + 1:]

    nodes, edges, groups = _parse_graph_source(content_lines)
    if not _opts.faithful_mermaid and _opts.infer_icons:
        _infer_label_icons(nodes)

    if len(nodes) > NODE_CAP:
        raise ValueError(
            f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}). "
            "Split the diagram into smaller slides."
        )
    if len(edges) > EDGE_CAP:
        raise ValueError(
            f"Cap exceeded: {len(edges)} edges (cap {EDGE_CAP}). "
            "Split the diagram into smaller slides."
        )
    if len(groups) > GROUP_CAP:
        raise ValueError(
            f"Cap exceeded: {len(groups)} subgraphs (cap {GROUP_CAP})."
        )

    if not nodes:
        raise ValueError("No nodes found in diagram source.")

    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)

    # Honor inner `direction LR` inside a TB subgraph: flatten all member nodes to
    # the same rank so they appear side-by-side (same y) rather than top-to-bottom.
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

    # Auto-select direction (TB vs LR) when a size constraint is given and the
    # source direction was not explicitly overridden by the caller.  Estimate the
    # canvas footprint for both orientations and choose the one that requires
    # less shrinkage (i.e. fits best inside width_hint × height_hint).
    # Disabled when opts.auto_direction is False or opts.faithful_mermaid is True.
    if width_hint and height_hint and not _opts.faithful_mermaid and _opts.auto_direction:
        max_rank = max((n.rank for n in nodes.values()), default=0)
        from collections import Counter
        rank_counts = Counter(n.rank for n in nodes.values() if not n.is_dummy)
        max_cols = max(rank_counts.values(), default=1)
        # Use actual average node height (accounts for sub-labels, icons, multi-line)
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

    _init_cfg = _parse_init_config(src)

    # Keep group members in adjacent column bands (reduces group bbox y-span in LR mode)
    if groups:
        _group_coherent_cols(nodes, groups)
    # Compact group column ranges before coordinate assignment (dagre-inspired)
    if groups:
        _compact_group_columns(nodes, groups)
    canvas_w, canvas_h = _assign_coordinates(
        nodes, direction,
        col_gap=_init_cfg.get("col_gap"),
        rank_gap=_init_cfg.get("rank_gap"),
        canvas_pad=_init_cfg.get("diagram_padding"),
    )

    # Recursive inner-direction fixup: re-order member x/y positions for groups
    # whose declared direction differs from the outer direction (replaces the
    # flat rank-flattening that was the only prior mechanism).
    if groups:
        _apply_inner_direction_positions(
            nodes, edges, groups, direction,
            col_gap=_init_cfg.get("col_gap"),
        )

    # Push overlapping group bounding boxes apart after coordinate assignment
    if direction.upper() in ("LR", "RL") and groups:
        _separate_groups_lr(nodes, groups)
        # Snap dummy node y-positions to match their non-dummy chain-source so
        # the horizontal routing segment stays in the source's y band instead of
        # cutting across intermediate groups after _separate_groups_lr shifts them.
        _pred: dict[str, str] = {}
        for _e in edges:
            if _e.src in nodes and _e.dst in nodes:
                _pred[_e.dst] = _e.src

        def _chain_src_y(nid: str) -> int:
            """Walk predecessor chain to first non-dummy node; return its y."""
            visited: set[str] = set()
            cur = nid
            while cur in _pred and nodes.get(cur) is not None:
                cur = _pred[cur]
                if cur in visited:
                    break
                visited.add(cur)
                if not nodes[cur].is_dummy:
                    return nodes[cur].y
            return nodes[nid].y  # fallback: keep original

        for _nid, _n in nodes.items():
            if _n.is_dummy:
                _n.y = _chain_src_y(_nid)

        # Also push non-member nodes that visually land inside a group bbox downward
        _push_nonmembers_out_of_groups_lr(nodes, groups)
    elif direction.upper() in ("TB", "TD") and groups:
        canvas_w = _separate_groups_tb(nodes, groups, canvas_w)

    # Recompute canvas dimensions using actual rendered node heights after any group shifts
    real_nodes = [n for n in nodes.values() if not n.is_dummy]
    if real_nodes:
        canvas_h = max(n.y + _node_render_h(n) for n in real_nodes) + CANVAS_PAD
        canvas_w = max(n.x + (n.width or NODE_W) for n in real_nodes) + CANVAS_PAD

    # Center terminal-circle nodes (start ● / end ◎) within their TB column slot.
    # _assign_coordinates places terminal circles at col_left[col] with no centering
    # offset (other nodes are centered within their per-column slot by _assign_coordinates).
    # Terminal circles are _TERMINAL_NODE_SIZE (32 px) wide; without this shift their centre
    # is col_left[col] + 16, producing a visible horizontal jog vs adjacent rect state nodes.
    # _eff_nw uses the global max node width as an approximation of the column width, which
    # is exact when all real nodes share one column (typical state diagrams); multi-column
    # diagrams with terminal circles in a narrower column may show a slight jog (P1 fix).
    # Canvas dimensions are already finalised above, so this shift does not affect sizing.
    if direction.upper() not in ("LR", "RL"):
        _eff_nw = max(
            (n.width for n in nodes.values() if n.width > 0 and not n.is_dummy),
            default=NODE_W,
        )
        _circ_shift = (_eff_nw - _TERMINAL_NODE_SIZE) // 2
        for _n in nodes.values():
            if not _n.is_dummy and _is_terminal_circle(_n):
                _n.x += _circ_shift

    # Scale to fit width/height constraints via CSS zoom.
    # Without height_hint: scale down only (never scale up — a tall diagram
    # scaled up to fill width overflows the slide height).
    # With height_hint: scale to fit both dimensions, capped at 1.4× scale-up.
    zoom = 1.0
    if width_hint and canvas_w > 0:
        w_zoom = width_hint / canvas_w
        if height_hint and canvas_h > 0:
            h_zoom = height_hint / canvas_h
            zoom = min(w_zoom, h_zoom, 1.4)  # fit both, cap scale-up
        else:
            zoom = min(w_zoom, 1.0)  # scale down only; avoids height overflow

    fragment = _render_graph_fragment(
        nodes, edges, groups, canvas_w, canvas_h, direction, zoom,
        style_overrides=style_overrides,
        show_legend=False,
    )

    # Wrap with metadata chip (type + title) and auto-legend
    directive, _ = _detect_directive(src)
    title = _extract_diagram_title(src)
    meta_html = _render_metadata_chip(directive, title)
    _show_legend = _opts.inferred_legend and not _opts.faithful_mermaid
    legend_html = _render_legend(edges, groups) if _show_legend else ""

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

def _directive_content(src: str) -> list[str]:
    """Return lines after the first non-blank, non-comment line (the directive)."""
    lines = src.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith(("%%", "//")):
            return lines[i + 1:]
    return []


# ── T2: sequenceDiagram ───────────────────────────────────────────────────────

_SEQ_PART_RE = re.compile(r'^(?:participant|actor)\s+(\S+)(?:\s+as\s+(.+))?', re.I)
_SEQ_MSG_RE = re.compile(
    r'^(\S+?)\s*(<<-->>|<<->>|-->>|->>|-->|->|--x|-x|--\)|-\))\s*(\S+)\s*:\s*(.*)$'
)
_SEQ_BLOCK_RE = re.compile(r'^(alt|loop|opt|par|critical|break|rect)\s*(.*)', re.I)
_SEQ_END_RE = re.compile(r'^end\s*$', re.I)
_SEQ_ACTIVATE_RE = re.compile(r'^(activate|deactivate)\s+(\S+)', re.I)
_SEQ_SKIP_RE = re.compile(
    r'^(autonumber|create\s+participant|create\s+actor|destroy|box|par_over)\b', re.I
)
# Group 1: position ("over", "left of", "right of")
# Group 2: participant list (comma-separated)
# Group 3: note text
_SEQ_NOTE_RE = re.compile(
    r'^[Nn]ote\s+(over|left\s+of|right\s+of)\s+([^:]+):\s*(.+)', re.I
)
_SEQ_ELSE_RE = re.compile(r'^(else|and|option)\s*(.*)', re.I)


def _layout_lifeline(
    src: str, direction: str, width_hint: int
) -> "tuple[str, object]":
    """sequenceDiagram: participants as columns, messages as horizontal arrows."""
    from ._geometry import Diagnostic, SequenceGeometry, TextStyle  # noqa: PLC0415
    from ._text import get_default_measurer  # noqa: PLC0415
    _MEASURER = get_default_measurer()
    content_lines = _directive_content(src)
    participants: list[str] = []
    p_label: dict[str, str] = {}
    _diagnostics: list[Diagnostic] = []

    def _ensure_p(name: str) -> None:
        n = name.strip()
        if n and n not in participants:
            participants.append(n)
            p_label.setdefault(n, n)

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
    for lineno, raw in enumerate(content_lines, start=1):
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m_skip = _SEQ_SKIP_RE.match(line)
        if m_skip:
            kw = m_skip.group(1).lower().replace(" ", "_")
            _diagnostics.append(Diagnostic(feature=kw, line_number=lineno, source_text=line))
            if re.match(r'^(box|par_over)\b', line, re.I):
                block_depth += 1
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
            if dp_prefix == '+':
                items.append({"type": "activate", "pid": dp})
            elif dp_prefix == '-':
                items.append({"type": "deactivate", "pid": sp})
            continue
        if block_depth > 0:
            me = _SEQ_ELSE_RE.match(line)
            if me:
                items.append({"type": "else", "kw": me.group(1).lower(), "label": me.group(2).strip()})
                continue
        m = _SEQ_BLOCK_RE.match(line)
        if m:
            kw = m.group(1).lower()
            # SEQ-013: rect is a solid fill background, not a dashed labeled fragment
            item_type = "rect" if kw == "rect" else "block"
            items.append({"type": item_type, "kw": m.group(1), "label": m.group(2).strip()})
            block_depth += 1
            continue
        if _SEQ_END_RE.match(line) and block_depth > 0:
            block_depth -= 1
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
    _frag_ctr = 0
    _row_types = {"msg", "block", "note", "else", "rect"}
    for _bi, _bit in enumerate(items):
        if _bit["type"] in ("block", "rect"):
            _bstack.append(_bi)
            _frag_parts[_bi] = set()
            _frag_id[_bi] = f"f{_frag_ctr}"
            _frag_ctr += 1
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
    _col_constraints: "list[tuple[int, int, float]]" = []
    for _ci in range(n_parts - 1):
        _col_constraints.append((_ci, _ci + 1, _half_w[_ci] + COL_GAP + _half_w[_ci + 1]))
    for _it in items:
        if _it.get("type") == "msg" and _it.get("src") != _it.get("dst"):
            _si = _p_index.get(_it.get("src", ""), -1)
            _di = _p_index.get(_it.get("dst", ""), -1)
            if _si >= 0 and _di >= 0:
                _lo, _hi = min(_si, _di), max(_si, _di)
                _lbl = _it.get("label", "")
                if _lbl:
                    _lw = _MEASURER.layout(_lbl, _LABEL_STYLE, max_width=float("inf")).max_content_width
                    _col_constraints.append((_lo, _hi, _lw + LABEL_PAD))

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

    # Apply width_hint: scale only column positions (box widths stay natural for text measurement).
    # T8b will replace this with a full uniform scale that also adjusts font sizes.
    if width_hint and canvas_w > 0 and abs(width_hint / canvas_w - 1.0) > 0.05:
        _wh_scale = width_hint / canvas_w
        _col_centers = [c * _wh_scale for c in _col_centers]
        canvas_w = float(width_hint)

    BOX_H = HDR_H - 8
    ll_top = PAD_V + BOX_H + 4

    _cx_offset = [0]

    def _cx(pid: str) -> int:
        _idx = _p_index.get(pid, 0)
        _base = _col_centers[_idx] if _idx < len(_col_centers) else float(PAD_H)
        return int(round(_base + _cx_offset[0]))

    # ── SEQ-009: row-height accumulator ──────────────────────────────────────
    _NOTE_STYLE = TextStyle(font_size=10)

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

    _row_h_list: "list[int]" = [
        _note_row_h(it) if it["type"] == "note" else ROW_H
        for it in items if it["type"] in _row_types
    ]
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
    # Flush unclosed activations to lifeline bottom (SEQ-006)
    for _pid, _stk in _act_stacks_v2.items():
        while _stk:
            _sy, _depth = _stk.pop()
            _act_spans_v2.append((_pid, _sy, float(ll_bot), _depth))

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
            _min_note_x = min(_min_note_x, _nx)
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
    for pid in participants:
        _bw = int(round(_box_hw(pid) * 2))
        lx = int(round(_cx(pid) - _box_hw(pid)))
        lbl = _h(p_label.get(pid, pid))
        parts.append(
            f'<div class="node node-rect" data-node-id="{_h(pid)}" style="'
            f'position:absolute;left:{lx}px;top:{PAD_V}px;'
            f'width:{_bw}px;height:{BOX_H}px;{_seq_box_css}">'
            f'<span class="node-label" style="{_seq_label_css}">{lbl}</span></div>'
        )
        parts.append(
            f'<div class="node node-rect node-lifeline-bottom" data-node-id="{_h(pid)}-bottom" style="'
            f'position:absolute;left:{lx}px;top:{ll_bot}px;'
            f'width:{_bw}px;height:{BOX_H}px;{_seq_box_css}">'
            f'<span class="node-label" style="{_seq_label_css}">{lbl}</span></div>'
        )

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
                parts.append(
                    f'<rect x="{x0}" y="{ry}" width="{x1 - x0}" height="{bh}" '
                    f'fill="{color}" opacity="0.3" rx="3"/>'
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
        if it["type"] in _row_types:
            _rp_a += 1

    # ── Lifeline dashes ────────────────────────────────────────────────────────
    for pid in participants:
        lx = int(round(_cx(pid)))
        parts.append(
            f'<line x1="{lx}" y1="{ll_top}" x2="{lx}" y2="{ll_bot}" '
            f'stroke="{_seq_edge}" stroke-width="1" stroke-dasharray="5 4"/>'
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
            # find parent fragment id for branch_separator_bounds
            _par_fid = ""
            for _pbi in reversed(_bstk_else):  # _bstk_else rebuilt; use _else_x dict key
                _par_fid = _frag_id.get(_pbi, "")
                break
            _geom_branch_bounds.append((_par_fid, float(x0), float(ry), float(x1 - x0), 1.0))
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
            row += 1; continue
        if it["type"] in ("activate", "deactivate", "block_end"):
            continue
        if it["type"] != "msg":
            continue

        ry = ll_top + _row_top_list[row] + _row_h_list[row] // 2
        _geom_msg_ys.append(float(ry))
        arrow = it.get("arrow", "->>")
        spec = _ARROW_SPECS.get(arrow, _ARROW_SPECS["->>"])
        dash = ' stroke-dasharray="6 4"' if spec["dashed"] else ""
        # SEQ-007: activation-aware endpoints
        sx, dx2 = _msg_endpoints(it["src"], it["dst"], ry)

        if it["src"] == it["dst"]:
            # T7: anchor self-loop at right edge of active activation bar (or lifeline cx)
            sl_data = _self_loop_data.get(_bi)
            if sl_data:
                ax_right, loop_w, _sl_ry = sl_data
            else:
                ax_right = activation_bounds_at(it["src"], ry)[1]
                loop_w = 36
            loop_top = ry - 8
            loop_bot = ry + 8
            parts.append(
                f'<path d="M {ax_right} {loop_top} C {ax_right + loop_w} {loop_top} '
                f'{ax_right + loop_w} {loop_bot} {ax_right} {loop_bot}" '
                f'stroke="{_seq_edge}" fill="none" stroke-width="1.5"{dash}'
                f' data-src="{_h(it["src"])}" data-dst="{_h(it["dst"])}"/>'
            )
            parts.append(_draw_marker(spec["end_m"], ax_right, loop_bot, -1))
            _geom_self_loops.append((float(ax_right), float(loop_top), float(loop_w), 16.0))
            _geom_msg_endpoints.append((float(ax_right), float(loop_top), float(ax_right), float(loop_bot)))
        else:
            parts.append(
                f'<line x1="{sx}" y1="{ry}" x2="{dx2}" y2="{ry}" '
                f'stroke="{_seq_edge}" stroke-width="1.5"{dash}'
                f' data-src="{_h(it["src"])}" data-dst="{_h(it["dst"])}"/>'
            )
            dirn = 1 if dx2 > sx else -1
            parts.append(_draw_marker(spec["end_m"], dx2, ry, dirn))
            if spec["start_m"]:  # bidirectional (SEQ-012)
                parts.append(_draw_marker(spec["start_m"], sx, ry, -dirn))
            _geom_msg_endpoints.append((float(sx), float(ry), float(dx2), float(ry)))
        row += 1

    parts.append('</svg>')

    # ── Pass C: keyword labels, else labels, note texts, edge labels (HTML) ───
    row = 0
    for _bi, it in enumerate(items):
        if it["type"] in ("block", "rect"):
            ry = ll_top + _row_top_list[row]
            if it["type"] == "block":
                x0, _ = _frag_x_bounds(it)
                parts.append(
                    f'<span style="position:absolute;left:{x0 + 4}px;top:{ry + 3}px;'
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
        sx_lbl = float(_cx(it["src"]))
        dx_lbl = float(_cx(it["dst"]))
        ry = ll_top + _row_top_list[row] + _row_h_list[row] // 2
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
_ER_CARD_SRC_MAP = {"||": "one", "|o": "zero-one", "}|": "many", "}o": "zero-many"}
_ER_CARD_DST_MAP = {"||": "one", "|o": "zero-one", "|{": "many", "o{": "zero-many"}

# Entity box geometry constants (px)
_ER_HDR_H = 34    # entity name header height
_ER_ROW_H = 22    # attribute row height
_ER_BOT_PAD = 8   # bottom padding below last attribute row


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


def _render_crow_foot(x: float, y: float, dx: float, dy: float, kind: str, color: str) -> list[str]:
    """Return SVG strings for a crow's foot marker at (x, y) with edge direction (dx, dy).

    (dx, dy) points from the entity boundary outward along the edge (toward the
    other entity).  Markers are drawn in that outward direction.
    """
    import math as _math
    px, py = -dy, dx  # perpendicular to edge direction
    HALF_W = 10.0
    parts: list[str] = []
    if kind in ("one", "zero-one"):
        bx, by = x + dx * 8, y + dy * 8
        parts.append(
            f'<line x1="{bx - px * HALF_W:.1f}" y1="{by - py * HALF_W:.1f}" '
            f'x2="{bx + px * HALF_W:.1f}" y2="{by + py * HALF_W:.1f}" '
            f'stroke="{color}" stroke-width="1.5"/>'
        )
        if kind == "one":
            bx2, by2 = x + dx * 14, y + dy * 14
            parts.append(
                f'<line x1="{bx2 - px * HALF_W:.1f}" y1="{by2 - py * HALF_W:.1f}" '
                f'x2="{bx2 + px * HALF_W:.1f}" y2="{by2 + py * HALF_W:.1f}" '
                f'stroke="{color}" stroke-width="1.5"/>'
            )
        else:
            cx_, cy_ = x + dx * 20, y + dy * 20
            parts.append(
                f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="4" '
                f'fill="none" stroke="{color}" stroke-width="1.5"/>'
            )
    elif kind in ("many", "zero-many"):
        bx, by = x + dx * 8, y + dy * 8
        edge_angle = _math.atan2(dy, dx)
        for ang in (-12, 0, 12):
            fa = edge_angle + _math.radians(ang)
            ex_ = bx + _math.cos(fa) * 12
            ey_ = by + _math.sin(fa) * 12
            parts.append(
                f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{ex_:.1f}" y2="{ey_:.1f}" '
                f'stroke="{color}" stroke-width="1.5"/>'
            )
        if kind == "zero-many":
            cx_, cy_ = x + dx * 24, y + dy * 24
            parts.append(
                f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="4" '
                f'fill="none" stroke="{color}" stroke-width="1.5"/>'
            )
    return parts


def _layout_er(src: str, direction: str, width_hint: int) -> str:
    """erDiagram: entity boxes with attribute tables; SVG edges with crow's feet.

    Improvements over the original:
    - Entity boxes show entity name header + typed attribute rows (PK/FK/UK badges).
    - Attribute comments (quoted strings) rendered as italic dim text.
    - Hyphenated entity names (e.g. LINE-ITEM) parsed correctly.
    - Crow's foot markers positioned at actual edge endpoints using correct
      direction vectors (not hardcoded top/bottom centres).
    - Non-identifying relationships (.. separator) rendered as dashed lines.
    """
    import math as _math
    from collections import defaultdict

    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    # eid -> list of {type, name, constraint, comment}
    entity_attrs: dict[str, list[dict]] = {}
    current_entity: Optional[str] = None

    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line == "}":
            current_entity = None
            continue
        # Entity block opening (supports hyphens: LINE-ITEM)
        m = _ER_ENTITY_RE.match(line)
        if m:
            eid = m.group(1)
            nodes.setdefault(eid, _Node(id=eid, label=eid, shape="rect"))
            entity_attrs.setdefault(eid, [])
            current_entity = eid
            continue
        # Attribute row inside entity block
        if current_entity:
            m = _ER_ATTR_RE.match(line)
            if m:
                entity_attrs[current_entity].append({
                    "type": m.group("type"),
                    "name": m.group("name"),
                    "constraint": (m.group("constraint") or "").strip(),
                    "comment": (m.group("comment") or "").strip(),
                })
            continue
        # Relationship line (supports hyphens in entity names)
        m = _ER_REL_RE.match(line)
        if m:
            e1, e2 = m.group("e1"), m.group("e2")
            lbl = m.group("lbl").strip().strip('"')
            for eid in (e1, e2):
                nodes.setdefault(eid, _Node(id=eid, label=eid, shape="rect"))
                entity_attrs.setdefault(eid, [])
            er_style = "dotted" if m.group("line").startswith(".") else "solid"
            edges.append(_Edge(
                src=e1, dst=e2, label=lbl, style=er_style, arrow=False,
                cardinality_src=_ER_CARD_SRC_MAP.get(m.group("card_src")),
                cardinality_dst=_ER_CARD_DST_MAP.get(m.group("card_dst")),
            ))

    if not nodes:
        raise ValueError("No entities found in erDiagram.")

    # Save original relationships before layout algorithms modify the edge list
    # (_assign_ranks inserts dummy nodes and replaces long-span edges with chains)
    er_rels = [
        {
            "src": e.src, "dst": e.dst, "label": e.label,
            "style": e.style,
            "card_src": e.cardinality_src,
            "card_dst": e.cardinality_dst,
        }
        for e in edges
    ]

    # Layout
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)
    canvas_w, _ = _assign_coordinates(nodes)

    # Override y-positions with attribute-aware entity heights
    rank_to_nids: dict[int, list[str]] = defaultdict(list)
    for nid, n in nodes.items():
        if not n.is_dummy:
            rank_to_nids[n.rank].append(nid)

    y_cursor = CANVAS_PAD
    for rank in range(max(rank_to_nids.keys(), default=0) + 1):
        nids = rank_to_nids.get(rank, [])
        if not nids:
            continue
        rank_h = max(_er_entity_h(len(entity_attrs.get(nid, []))) for nid in nids)
        for nid in nids:
            eh = _er_entity_h(len(entity_attrs.get(nid, [])))
            nodes[nid].y = y_cursor + (rank_h - eh) // 2
        y_cursor += rank_h + RANK_GAP

    # Scale x-positions to fit width_hint
    if width_hint and canvas_w > 0 and abs(width_hint / canvas_w - 1.0) > 0.05:
        scale = width_hint / canvas_w
        for n in nodes.values():
            n.x = int(n.x * scale)
        canvas_w = width_hint

    # Recompute canvas dimensions from actual node positions
    real_nids = [(nid, n) for nid, n in nodes.items() if not n.is_dummy]
    if real_nids:
        canvas_w = max(n.x + NODE_W for _, n in real_nids) + CANVAS_PAD
        canvas_h = (
            max(n.y + _er_entity_h(len(entity_attrs.get(nid, [])))
                for nid, n in real_nids)
            + CANVAS_PAD
        )
    else:
        canvas_h = y_cursor - RANK_GAP + CANVAS_PAD

    _edge_color = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"
    _lf = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"
    _er_accent = "var(--node-title-fg,var(--accent-1,#60a5fa))"

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )

    # Entity boxes
    for nid, n in nodes.items():
        if n.is_dummy:
            continue
        attrs = entity_attrs.get(nid, [])
        eh = _er_entity_h(len(attrs))

        parts.append(
            f'<div class="node node-rect er-entity" data-node-id="{_h(nid)}" style="'
            f'position:absolute;left:{n.x}px;top:{n.y}px;'
            f'width:{NODE_W}px;height:{eh}px;'
            f'box-sizing:border-box;overflow:hidden;'
            f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
            f'border-top:3px solid {_er_accent};'
            f'border-radius:var(--node-radius,8px);'
            f'background:linear-gradient(180deg,'
            f'var(--node-bg-from,var(--card-bg-from,#ffffff)),'
            f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));'
            f'box-shadow:var(--node-shadow,'
            f'0 1px 2px rgba(25,26,23,0.06),0 1px 0 rgba(25,26,23,0.03));">'
        )
        # Entity name header
        parts.append(
            f'<div style="height:{_ER_HDR_H}px;display:flex;align-items:center;'
            f'justify-content:center;padding:0 8px;box-sizing:border-box;">'
            f'<span class="node-label" style="'
            f'font-size:13px;font-weight:700;'
            f'color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:{_lf};'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
            f'{_h(nid)}</span></div>'
        )
        if attrs:
            parts.append(
                f'<div style="height:1px;'
                f'background:var(--node-border,var(--card-border,#DAD7CE));"></div>'
            )
            for attr in attrs:
                constraint = attr["constraint"]
                if constraint == "PK":
                    badge_html = (
                        f'<span style="font-size:9px;font-weight:700;'
                        f'color:var(--accent-3,#B7791F);'
                        f'background:rgba(183,121,31,0.12);'
                        f'border-radius:3px;padding:0 3px;margin-right:4px;'
                        f'flex-shrink:0;font-family:{_lf};">PK</span>'
                    )
                elif constraint == "FK":
                    badge_html = (
                        f'<span style="font-size:9px;font-weight:700;'
                        f'color:var(--accent-1,#60a5fa);'
                        f'background:rgba(96,165,250,0.12);'
                        f'border-radius:3px;padding:0 3px;margin-right:4px;'
                        f'flex-shrink:0;font-family:{_lf};">FK</span>'
                    )
                elif constraint == "UK":
                    badge_html = (
                        f'<span style="font-size:9px;font-weight:700;'
                        f'color:var(--accent-2,#34d399);'
                        f'background:rgba(52,211,153,0.12);'
                        f'border-radius:3px;padding:0 3px;margin-right:4px;'
                        f'flex-shrink:0;font-family:{_lf};">UK</span>'
                    )
                else:
                    badge_html = ""
                comment_html = ""
                if attr["comment"]:
                    comment_html = (
                        f'<span style="font-size:9px;font-style:italic;'
                        f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                        f'margin-left:4px;overflow:hidden;text-overflow:ellipsis;'
                        f'white-space:nowrap;flex-shrink:1;font-family:{_lf};">'
                        f'{_h(attr["comment"])}</span>'
                    )
                parts.append(
                    f'<div style="height:{_ER_ROW_H}px;display:flex;align-items:center;'
                    f'padding:0 8px;overflow:hidden;box-sizing:border-box;">'
                    f'{badge_html}'
                    f'<span style="font-size:10px;'
                    f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                    f'margin-right:4px;flex-shrink:0;font-family:{_lf};">'
                    f'{_h(attr["type"])}</span>'
                    f'<span style="font-size:11px;font-weight:500;'
                    f'color:var(--node-fg,var(--text-primary,#191A17));'
                    f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
                    f'flex:1;font-family:{_lf};">'
                    f'{_h(attr["name"])}</span>'
                    f'{comment_html}'
                    f'</div>'
                )
        parts.append('</div>')  # close entity box

    # SVG overlay: edge lines + crow's feet
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )

    edge_labels: list[tuple[float, float, str]] = []

    for rel in er_rels:
        e_src, e_dst = rel["src"], rel["dst"]
        if e_src not in nodes or e_dst not in nodes:
            continue
        s = nodes[e_src]
        d_node = nodes[e_dst]
        if s.is_dummy or d_node.is_dummy:
            continue

        sh = float(_er_entity_h(len(entity_attrs.get(e_src, []))))
        dh = float(_er_entity_h(len(entity_attrs.get(e_dst, []))))

        src_cx = float(s.x + NODE_W // 2)
        src_cy = float(s.y) + sh / 2.0
        dst_cx = float(d_node.x + NODE_W // 2)
        dst_cy = float(d_node.y) + dh / 2.0

        vx, vy = dst_cx - src_cx, dst_cy - src_cy
        norm = _math.hypot(vx, vy) or 1.0
        uvx, uvy = vx / norm, vy / norm

        # Exit/entry points on each entity's bounding box
        src_ex, src_ey = _er_rect_edge_pt(src_cx, src_cy, float(NODE_W), sh, uvx, uvy)
        dst_ex, dst_ey = _er_rect_edge_pt(dst_cx, dst_cy, float(NODE_W), dh, -uvx, -uvy)

        dash = ' stroke-dasharray="6 4"' if rel["style"] == "dotted" else ""
        parts.append(
            f'<line x1="{src_ex:.1f}" y1="{src_ey:.1f}" '
            f'x2="{dst_ex:.1f}" y2="{dst_ey:.1f}" '
            f'stroke="{_edge_color}" stroke-width="1.5"{dash}'
            f' data-src="{_h(e_src)}" data-dst="{_h(e_dst)}"/>'
        )

        # Crow's feet: direction from boundary outward toward the other entity
        if rel["card_src"]:
            parts.extend(_render_crow_foot(
                src_ex, src_ey, uvx, uvy, rel["card_src"], _edge_color
            ))
        if rel["card_dst"]:
            parts.extend(_render_crow_foot(
                dst_ex, dst_ey, -uvx, -uvy, rel["card_dst"], _edge_color
            ))

        if rel["label"]:
            edge_labels.append((
                (src_ex + dst_ex) / 2.0,
                (src_ey + dst_ey) / 2.0,
                rel["label"],
            ))

    parts.append('</svg>')

    # Edge labels as HTML (float above SVG)
    for lx, ly, lbl in edge_labels:
        parts.append(
            f'<span class="edge-label" style="'
            f'position:absolute;left:{lx:.0f}px;top:{ly:.0f}px;'
            f'transform:translate(-50%,-50%);'
            f'font-size:11px;font-weight:500;'
            f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
            f'background:var(--edge-label-bg,var(--node-bg-from,#F7F6F2));'
            f'padding:1px 4px;border-radius:3px;'
            f'font-family:{_lf};'
            f'white-space:nowrap;pointer-events:none;z-index:2;">'
            f'{_h(lbl)}</span>'
        )

    parts.append('</div>')
    return "\n".join(parts)


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
    """Map a class relationship operator to an _Edge style value."""
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
            # For operators where the UML marker is on the LEFT (c1) side,
            # arrow_src=True so the renderer places marker-start at c1.
            _arrow_src = op.startswith(("<|", "*", "o"))
            edges.append(_Edge(src=c1, dst=c2, label=lbl.strip(),
                               style=_class_rel_style(op), arrow=True,
                               arrow_src=_arrow_src,
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


# ── T3: gantt ─────────────────────────────────────────────────────────────────

def _layout_gantt(src: str, direction: str, width_hint: int) -> str:
    """gantt: sections as swim-lanes, tasks as horizontal bars.

    Renders:
    - Date axis at top with tick labels and full-height vertical grid lines
    - Section headers with border-bottom dividers
    - Task bars colour-coded: crit=red, done=grey, active=blue, default=green
    - Milestone tasks as a rotated-45deg diamond at their start date
    - ``after id1 id2`` resolved to max(end(id1), end(id2)) for multi-id deps
    """
    content_lines = _directive_content(src)
    title = ""
    sections: list[dict] = [{"name": "Tasks", "tasks": []}]
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        low = line.lower()
        if low.startswith("title "):
            title = line[6:].strip().strip('"\''); continue
        if low.startswith(("dateformat", "axisformat", "excludes", "todaymarker")):
            continue
        if low.startswith("section "):
            sections.append({"name": line[8:].strip(), "tasks": []}); continue
        if ":" in line:
            name, meta = line.split(":", 1)
            _meta_parts = [p.strip() for p in meta.split(",")]
            _flags = {"crit", "done", "active", "milestone"}
            task_flags: set[str] = set()
            task_id: str = ""
            task_start_str: str = ""
            task_dur_str: str = ""
            for _p in _meta_parts:
                _pl = _p.lower()
                if _pl in _flags:
                    task_flags.add(_pl)
                elif re.match(r'\d{4}-\d{2}-\d{2}', _p):
                    if not task_start_str:
                        task_start_str = _p
                    else:
                        task_dur_str = _p
                elif _pl.startswith("after "):
                    # Preserve entire "after id1 id2 ..." string for multi-id resolution
                    task_start_str = _pl
                elif re.match(r'^\d+[dwm]$', _pl):
                    task_dur_str = _p
                elif re.match(r'^[a-z_]\w*$', _pl) and not task_id:
                    task_id = _pl
            sections[-1]["tasks"].append({
                "name": name.strip(),
                "crit": "crit" in task_flags,
                "done": "done" in task_flags,
                "active": "active" in task_flags,
                "milestone": "milestone" in task_flags,
                "id": task_id,
                "start_str": task_start_str,
                "dur_str": task_dur_str,
            })
    sections = [s for s in sections if s["tasks"]]
    if not sections:
        raise ValueError("No tasks found in gantt.")

    # ── Date resolution ──
    from datetime import date as _date, timedelta as _td
    _GANTT_DATE_RE = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
    def _parse_date(s: str) -> Optional[_date]:
        m = _GANTT_DATE_RE.match(s)
        return _date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

    def _parse_dur(s: str) -> int:
        if not s:
            return 7
        m = re.match(r'^(\d+)([dwm])$', s.lower())
        if not m:
            return 7
        n, unit = int(m.group(1)), m.group(2)
        return n * (1 if unit == 'd' else 7 if unit == 'w' else 30)

    id_end_date: dict[str, _date] = {}
    all_tasks_flat: list[dict] = []
    for sec in sections:
        for task in sec["tasks"]:
            all_tasks_flat.append(task)

    # First pass: compute absolute dates for each task
    earliest = _date(2100, 1, 1)
    latest = _date(2000, 1, 1)
    for task in all_tasks_flat:
        ss = task["start_str"]
        ds = task["dur_str"]
        if ss.startswith("after "):
            # Multi-id: "after id1 id2 ..." -> max(end(id1), end(id2), ...)
            ref_ids = ss[6:].strip().split()
            end_dates = [id_end_date[rid] for rid in ref_ids if rid in id_end_date]
            t_start = max(end_dates) if end_dates else _date(2024, 1, 1)
        else:
            t_start = _parse_date(ss) or _date(2024, 1, 1)
        dur = _parse_dur(ds)
        t_end = t_start + _td(days=dur)
        task["t_start"] = t_start
        task["t_end"] = t_end
        if task["id"]:
            id_end_date[task["id"]] = t_end
        if t_start < earliest:
            earliest = t_start
        if t_end > latest:
            latest = t_end

    total_days = max(1, (latest - earliest).days)

    PAD_H, PAD_V = 40, 24
    LABEL_W, BAR_H, ROW_GAP = 140, 24, 5
    SEC_H, AXIS_H = 22, 28
    total_rows = sum(len(s["tasks"]) for s in sections)
    canvas_w = width_hint or 720
    canvas_h = (PAD_V * 2 + (22 if title else 0) + AXIS_H
                + len(sections) * (SEC_H + 4) + total_rows * (BAR_H + ROW_GAP))
    bar_x = PAD_H + LABEL_W + 4
    bar_w_total = canvas_w - bar_x - PAD_H

    _lc = "var(--node-fg-dim,var(--text-secondary,#75736C))"
    _lf = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"
    _ec = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    y = PAD_V
    if title:
        parts.append(
            f'<div style="position:absolute;left:{PAD_H}px;top:{y}px;'
            f'font-size:13px;font-weight:700;color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:{_lf};">{_h(title)}</div>'
        )
        y += 22

    # Date axis (top) -- tick labels and small indicator marks.
    # Ticks are evenly spaced at total_days/N intervals so they always reach
    # the end date regardless of how total_days divides.
    _tick_count = min(10, total_days)  # up to 10 ticks; for short spans this shows every day
    parts.append(
        f'<div style="position:absolute;left:{bar_x}px;top:{y}px;'
        f'width:{bar_w_total}px;height:{AXIS_H}px;overflow:hidden;">'
    )
    _tick_xs: list[int] = []
    _step = total_days / _tick_count  # float step ensures last tick == total_days
    for _ti in range(_tick_count + 1):
        _td_off = round(_ti * _step)
        if _td_off > total_days:
            _td_off = total_days
        _tx = int(_td_off / total_days * bar_w_total)
        _tick_d = earliest + _td(days=_td_off)
        _label = f"{_tick_d.month}/{_tick_d.day}"
        _tick_xs.append(_tx)
        parts.append(
            f'<span style="position:absolute;left:{_tx}px;top:2px;'
            f'font-size:9px;color:{_lc};font-family:{_lf};white-space:nowrap;">'
            f'{_label}</span>'
            f'<div style="position:absolute;left:{_tx}px;top:18px;'
            f'width:1px;height:10px;background:{_ec};"></div>'
        )
    parts.append('</div>')
    # Axis baseline
    parts.append(
        f'<div style="position:absolute;left:{bar_x}px;top:{y + AXIS_H - 1}px;'
        f'width:{bar_w_total}px;height:1px;background:{_ec};"></div>'
    )
    y += AXIS_H

    # Full-height vertical grid lines rendered behind task bars
    _grid_y_top = y
    _grid_h = canvas_h - _grid_y_top - PAD_V
    if _grid_h > 0 and _tick_xs:
        parts.append(
            f'<svg style="position:absolute;left:{bar_x}px;top:{_grid_y_top}px;'
            f'width:{bar_w_total}px;height:{_grid_h}px;overflow:visible;pointer-events:none;">'
        )
        for _tx in _tick_xs:
            parts.append(
                f'<line x1="{_tx}" y1="0" x2="{_tx}" y2="{_grid_h}" '
                f'stroke="{_ec}" stroke-width="1" stroke-dasharray="3 4" opacity="0.45"/>'
            )
        parts.append('</svg>')

    for sec in sections:
        parts.append(
            f'<div style="position:absolute;left:{PAD_H}px;top:{y}px;'
            f'width:{canvas_w - PAD_H * 2}px;height:{SEC_H}px;'
            f'display:flex;align-items:flex-end;'
            f'border-bottom:1px solid {_ec};">'
            f'<span style="font-size:10px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.1em;color:{_lc};font-family:{_lf};">'
            f'{_h(sec["name"])}</span></div>'
        )
        y += SEC_H + 4
        for task in sec["tasks"]:
            # Bar colour: crit=red, done=grey, active=blue, default=green
            bar_color = (
                "rgba(220,38,38,0.75)" if task["crit"]
                else "var(--node-border,rgba(100,116,139,0.35))" if task["done"]
                else "rgba(59,130,246,0.55)" if task.get("active")
                else "rgba(53,148,103,0.35)"
            )
            t_off = (task["t_start"] - earliest).days
            t_len = (task["t_end"] - task["t_start"]).days
            bx = bar_x + int(t_off / total_days * bar_w_total)
            bw = max(4, int(t_len / total_days * bar_w_total))
            parts.append(
                f'<div style="position:absolute;left:{PAD_H}px;top:{y}px;'
                f'width:{LABEL_W}px;height:{BAR_H}px;'
                f'display:flex;align-items:center;overflow:hidden;">'
                f'<span style="font-size:11px;color:var(--node-fg,var(--text-primary,#191A17));'
                f'font-family:{_lf};'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
                f'{_h(task["name"])}</span></div>'
            )
            _task_id_val = task["id"] if task["id"] else task["name"]
            if task.get("milestone"):
                # Milestone: a square rotated 45deg (diamond) pinned at the start date
                _ms = BAR_H - 4
                _ms_half = _ms // 2
                _ms_cx = bx + _ms_half
                _ms_cy = y + BAR_H // 2
                parts.append(
                    f'<div data-task-id="{_h(_task_id_val)}" data-milestone="1" '
                    f'style="position:absolute;'
                    f'left:{_ms_cx - _ms_half}px;top:{_ms_cy - _ms_half}px;'
                    f'width:{_ms}px;height:{_ms}px;'
                    f'background:{bar_color};'
                    f'border:1.5px solid var(--node-border,var(--card-border,#DAD7CE));'
                    f'box-sizing:border-box;'
                    f'transform:rotate(45deg);"></div>'
                )
            else:
                parts.append(
                    f'<div data-task-id="{_h(_task_id_val)}" style="position:absolute;left:{bx}px;top:{y + 1}px;'
                    f'width:{bw}px;height:{BAR_H - 2}px;background:{bar_color};'
                    f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
                    f'border-radius:3px;box-sizing:border-box;"></div>'
                )
            y += BAR_H + ROW_GAP
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: timeline helpers ───────────────────────────────────────────────────────

# Vertical gap between the spine and the period-label chip (px)
_TL_LABEL_GAP: int = 6
# Height of the period-label chip (px)
_TL_LABEL_H: int = 22
# Height of each event card (px)
_TL_CARD_H: int = 22
# Vertical gap between consecutive event cards (px)
_TL_CARD_GAP: int = 4
# Gap between the period-label edge and the first event card (px)
_TL_CARD_PAD: int = 8
# Radius of the spine period-marker dot (px)
_TL_MARKER_R: int = 5
# Cycling section-band fill colours (semi-transparent)
_TL_SECTION_COLORS: list = [
    "rgba(96,165,250,0.10)",
    "rgba(52,211,153,0.10)",
    "rgba(251,191,36,0.10)",
    "rgba(167,139,250,0.10)",
    "rgba(248,113,113,0.10)",
]


def _tl_branch_height(n_events: int) -> int:
    """Pixels from the spine surface to the far edge of all content for one period.

    Applies symmetrically for both above-spine and below-spine placements:
    label gap + label chip + (optional: card padding + N cards with gaps).
    """
    h = _TL_LABEL_GAP + _TL_LABEL_H
    if n_events > 0:
        h += _TL_CARD_PAD + n_events * _TL_CARD_H + (n_events - 1) * _TL_CARD_GAP
    return h


# ── T3: timeline ──────────────────────────────────────────────────────────────

def _layout_timeline(src: str, direction: str, width_hint: int) -> str:
    """timeline: horizontal spine with alternating above/below event cards.

    Parsing rules
    -------------
    - ``title TEXT``      -> diagram title rendered above the spine.
    - ``section TEXT``    -> named section band grouping subsequent periods.
    - ``PERIOD : EVENT``  -> new period node with its first event.
    - ``: EVENT``         -> continuation event appended to the current period.
    """
    content_lines = _directive_content(src)
    title = ""
    # groups: list of {"name": str|None, "periods": list[{"period": str, "events": list}]}
    groups: list[dict] = [{"name": None, "periods": []}]
    current_period: Optional[dict] = None

    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line.lower().startswith("title "):
            title = line[6:].strip()
            continue
        if line.lower().startswith("section "):
            groups.append({"name": line[8:].strip(), "periods": []})
            current_period = None
            continue
        # Continuation event: ": EVENT" — no period text before the colon
        if line.startswith(":"):
            evt = line[1:].strip()
            if current_period is not None and evt:
                current_period["events"].append(evt)
            continue
        # New period, optionally with an inline first event
        if " : " in line:
            period_name, first_event = line.split(" : ", 1)
            current_period = {"period": period_name.strip(), "events": [first_event.strip()]}
        else:
            current_period = {"period": line, "events": []}
        groups[-1]["periods"].append(current_period)

    # Flatten to all_periods, tagging each with its group index
    all_periods: list[dict] = []
    for g_idx, grp in enumerate(groups):
        for p in grp["periods"]:
            all_periods.append({
                "period": p["period"],
                "events": p["events"],
                "section": grp["name"],
                "g_idx": g_idx,
            })

    if not all_periods:
        raise ValueError("No periods found in timeline.")

    # ── Geometry ───────────────────────────────────────────────────────────────
    PAD_H = 40
    PAD_V = 32
    title_h = 28 if title else 0

    # Assign alternating above (even index) / below (odd index) placement
    for i, p in enumerate(all_periods):
        p["_above"] = (i % 2 == 0)

    max_above = max(
        (_tl_branch_height(len(p["events"])) for p in all_periods if p["_above"]),
        default=_tl_branch_height(0),
    )
    max_below = max(
        (_tl_branch_height(len(p["events"])) for p in all_periods if not p["_above"]),
        default=_tl_branch_height(0),
    )

    canvas_w = width_hint or max(
        500, PAD_H * 2 + len(all_periods) * 136 - 16
    )
    n = len(all_periods)
    step = (canvas_w - PAD_H * 2) // max(n, 1)
    card_w = max(64, min(120, step - 8))

    spine_y = PAD_V + title_h + max_above
    canvas_h = spine_y + max_below + PAD_V

    # CSS variable aliases for concision
    _ec = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"
    _fg = "var(--node-fg,var(--text-primary,#191A17))"
    _fg_dim = "var(--node-fg-dim,var(--text-secondary,#75736C))"
    _lf = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"
    _dot_fill = "var(--edge-strong,var(--accent-1,#60a5fa))"
    _dot_stroke = "var(--node-bg-from,var(--card-bg-from,#ffffff))"

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )

    # Title
    if title:
        parts.append(
            f'<div style="position:absolute;left:{PAD_H}px;top:{PAD_V}px;'
            f'font-size:13px;font-weight:700;color:{_fg};'
            f'font-family:{_lf};">{_h(title)}</div>'
        )

    # ── SVG layer: section bands, spine, connectors, period dots ──────────────
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )

    # Section bands — one rect per named group spanning its period columns
    sec_color_idx = 0
    # Build a map: g_idx -> sorted list of period-column indices
    g_period_cols: dict[int, list[int]] = {}
    for col_i, p in enumerate(all_periods):
        g_period_cols.setdefault(p["g_idx"], []).append(col_i)

    for grp in groups:
        g_idx = groups.index(grp)
        if grp["name"] is None:
            # Advance colour index for unnamed groups only if they have periods,
            # so named sections get visually distinct cycling colours.
            if g_period_cols.get(g_idx):
                sec_color_idx += 1
            continue
        cols = g_period_cols.get(g_idx, [])
        if not cols:
            sec_color_idx += 1
            continue
        bx = PAD_H + min(cols) * step
        bw = (max(cols) - min(cols) + 1) * step
        band_y = PAD_V + title_h
        band_h = canvas_h - band_y - PAD_V // 2
        color = _TL_SECTION_COLORS[sec_color_idx % len(_TL_SECTION_COLORS)]
        sec_color_idx += 1
        parts.append(
            f'<rect x="{bx}" y="{band_y}" width="{bw}" height="{band_h}" '
            f'fill="{color}" rx="4"/>'
        )

    # Horizontal spine
    cx_first = PAD_H + step // 2
    cx_last = PAD_H + (n - 1) * step + step // 2
    spine_ext = max(8, step // 6)
    parts.append(
        f'<line x1="{cx_first - spine_ext}" y1="{spine_y}" '
        f'x2="{cx_last + spine_ext}" y2="{spine_y}" '
        f'stroke="{_ec}" stroke-width="2"/>'
    )

    # Per-period: dashed connector + filled dot (dot drawn last, sits atop connector)
    for i, p in enumerate(all_periods):
        cx_ = PAD_H + i * step + step // 2
        above = p["_above"]
        label_y = (spine_y - _TL_LABEL_GAP - _TL_LABEL_H if above
                   else spine_y + _TL_LABEL_GAP)

        # Dashed connector from dot surface to period-label edge
        con_y1 = spine_y - _TL_MARKER_R if above else spine_y + _TL_MARKER_R
        con_y2 = label_y + _TL_LABEL_H if above else label_y
        parts.append(
            f'<line x1="{cx_}" y1="{con_y1}" x2="{cx_}" y2="{con_y2}" '
            f'stroke="{_ec}" stroke-width="1" stroke-dasharray="3 3"/>'
        )

        # Filled dot
        parts.append(
            f'<circle cx="{cx_}" cy="{spine_y}" r="{_TL_MARKER_R}" '
            f'fill="{_dot_fill}" stroke="{_dot_stroke}" stroke-width="2"/>'
        )

    parts.append('</svg>')

    # ── Section labels (HTML div, not SVG, so they clip cleanly) ──────────────
    sec_color_idx = 0
    for grp in groups:
        g_idx = groups.index(grp)
        if grp["name"] is None:
            if g_period_cols.get(g_idx):
                sec_color_idx += 1
            continue
        cols = g_period_cols.get(g_idx, [])
        if not cols:
            sec_color_idx += 1
            continue
        lx = PAD_H + min(cols) * step + 6
        lbl_top = PAD_V + title_h + 4
        sec_color_idx += 1
        parts.append(
            f'<div style="position:absolute;left:{lx}px;top:{lbl_top}px;'
            f'font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;'
            f'color:{_fg_dim};font-family:{_lf};pointer-events:none;">{_h(grp["name"])}</div>'
        )

    # ── Period labels and event cards ─────────────────────────────────────────
    for i, p in enumerate(all_periods):
        cx_ = PAD_H + i * step + step // 2
        lx = cx_ - card_w // 2
        above = p["_above"]
        label_y = (spine_y - _TL_LABEL_GAP - _TL_LABEL_H if above
                   else spine_y + _TL_LABEL_GAP)

        # Period-label chip (carries data-node-id for identity tracking)
        parts.append(
            f'<div class="node node-rect" data-node-id="{_h(p["period"])}" '
            f'style="position:absolute;left:{lx}px;top:{label_y}px;'
            f'width:{card_w}px;height:{_TL_LABEL_H}px;'
            f'display:flex;align-items:center;justify-content:center;'
            f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
            f'border-radius:var(--node-radius,4px);'
            f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
            f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));'
            f'overflow:hidden;">'
            f'<span class="node-label" style="font-size:11px;font-weight:700;color:{_fg};'
            f'font-family:{_lf};white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis;">{_h(p["period"])}</span></div>'
        )

        # Event cards stacked away from the spine
        for j, ev in enumerate(p["events"]):
            if above:
                # Stack upward: card[0] is just above the period label
                ev_y = label_y - _TL_CARD_PAD - (j + 1) * _TL_CARD_H - j * _TL_CARD_GAP
            else:
                # Stack downward: card[0] is just below the period label
                ev_y = label_y + _TL_LABEL_H + _TL_CARD_PAD + j * (_TL_CARD_H + _TL_CARD_GAP)
            parts.append(
                f'<div style="position:absolute;left:{lx}px;top:{ev_y}px;'
                f'width:{card_w}px;height:{_TL_CARD_H}px;'
                f'padding:0 6px;box-sizing:border-box;'
                f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
                f'border-radius:var(--node-radius,4px);'
                f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
                f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));'
                f'display:flex;align-items:center;justify-content:center;'
                f'overflow:hidden;">'
                f'<span style="font-size:10px;font-weight:500;color:{_fg};'
                f'font-family:{_lf};white-space:nowrap;overflow:hidden;'
                f'text-overflow:ellipsis;">{_h(ev)}</span></div>'
            )

    parts.append('</div>')
    return "\n".join(parts)

# ── T3: quadrantChart ─────────────────────────────────────────────────────────

_QUAD_POINT_RE = re.compile(r'^(.+?)\s*:\s*\[([0-9.]+)\s*,\s*([0-9.]+)\]')


def _layout_quadrant(src: str, direction: str, width_hint: int) -> str:
    """quadrantChart: 2×2 fixed grid with plotted data points.

    Renders: title, x/y axis labels (including y-axis which was previously
    dropped), quadrant background fills, quadrant labels, data-point circles,
    and point labels.  Center dividers are solid lines (not dashed).
    """
    content_lines = _directive_content(src)
    title = ""
    x_labels = ("Low", "High")
    y_labels = ("Low", "High")
    quad_labels: dict[str, str] = {}
    points: list[dict] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        low = line.lower()
        if low.startswith("title "):
            title = line[6:].strip(); continue
        if low.startswith("x-axis "):
            ps = line[7:].split("-->")
            x_labels = (ps[0].strip(), ps[1].strip() if len(ps) > 1 else "High"); continue
        if low.startswith("y-axis "):
            ps = line[7:].split("-->")
            y_labels = (ps[0].strip(), ps[1].strip() if len(ps) > 1 else "High"); continue
        m = re.match(r'quadrant-([1-4])\s+(.*)', line, re.I)
        if m:
            quad_labels[m.group(1)] = m.group(2).strip(); continue
        m = _QUAD_POINT_RE.match(line)
        if m:
            points.append({"name": m.group(1).strip(), "x": float(m.group(2)), "y": float(m.group(3))})

    PAD = 48
    canvas_w = width_hint or 480
    canvas_h = max(320, canvas_w * 3 // 4)
    # Left margin: PAD (48) outer + 24 reserved for rotated y-axis labels.
    gx = PAD + 24
    gy = PAD + (24 if title else 0)
    gw = canvas_w - gx - PAD
    gh = canvas_h - gy - PAD - 24
    mx, my = gx + gw // 2, gy + gh // 2

    _edge = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"
    _lc = "var(--node-fg-dim,var(--text-secondary,#75736C))"
    _lf = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"
    _dot = "var(--edge-strong,var(--accent-1,#60a5fa))"

    # Per-quadrant subtle background fills (Q1=top-right, Q2=top-left,
    # Q3=bottom-left, Q4=bottom-right), consistent with mermaid's own palette.
    _QUAD_BG: dict[str, str] = {
        "1": "rgba(96,165,250,0.08)",   # top-right
        "2": "rgba(52,211,153,0.07)",   # top-left
        "3": "rgba(251,191,36,0.07)",   # bottom-left
        "4": "rgba(248,113,113,0.07)",  # bottom-right
    }
    # (rect_x, rect_y, rect_w, rect_h) for each quadrant
    _QUAD_RECT: dict[str, tuple[int, int, int, int]] = {
        "1": (mx,  gy,  gw - gw // 2, gh // 2),
        "2": (gx,  gy,  gw // 2,       gh // 2),
        "3": (gx,  my,  gw // 2,       gh - gh // 2),
        "4": (mx,  my,  gw - gw // 2,  gh - gh // 2),
    }

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    if title:
        parts.append(
            f'<div style="position:absolute;left:{gx}px;top:{PAD}px;'
            f'font-size:12px;font-weight:700;color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:{_lf};">{_h(title)}</div>'
        )
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )

    # Quadrant background fills (rendered first, behind border and dividers)
    for qid, (qrx, qry, qrw, qrh) in _QUAD_RECT.items():
        parts.append(
            f'<rect x="{qrx}" y="{qry}" width="{qrw}" height="{qrh}" '
            f'fill="{_QUAD_BG[qid]}" stroke="none"/>'
        )

    # Outer border + solid center dividers (solid, not dashed)
    parts.append(
        f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" '
        f'fill="none" stroke="{_edge}" stroke-width="1.5"/>'
        f'<line x1="{mx}" y1="{gy}" x2="{mx}" y2="{gy + gh}" '
        f'stroke="{_edge}" stroke-width="1"/>'
        f'<line x1="{gx}" y1="{my}" x2="{gx + gw}" y2="{my}" '
        f'stroke="{_edge}" stroke-width="1"/>'
    )

    # Data-point circles
    for pt in points:
        px = gx + int(pt["x"] * gw)
        py = gy + gh - int(pt["y"] * gh)
        parts.append(f'<circle cx="{px}" cy="{py}" r="5" fill="{_dot}"/>')

    # Y-axis labels as rotated SVG text: Low label at bottom, High at top.
    # rotate(-90, anchor_x, anchor_y) pivots the text -90deg around the anchor.
    # text-anchor="end" aligns the text end at the anchor for Low (bottom edge),
    # text-anchor="start" aligns the text start at the anchor for High (top edge).
    _yax_x = gx - 10
    parts.append(
        f'<text transform="rotate(-90,{_yax_x},{gy + gh})" '
        f'x="{_yax_x}" y="{gy + gh}" font-size="10" fill="{_lc}" '
        f'font-family="-apple-system,Inter,sans-serif" text-anchor="end">'
        f'{_h(y_labels[0])}</text>'
        f'<text transform="rotate(-90,{_yax_x},{gy})" '
        f'x="{_yax_x}" y="{gy}" font-size="10" fill="{_lc}" '
        f'font-family="-apple-system,Inter,sans-serif" text-anchor="start">'
        f'{_h(y_labels[1])}</text>'
    )

    parts.append('</svg>')

    # Quadrant labels (HTML layer, corner-anchored inside each quadrant)
    for qid, qlbl in quad_labels.items():
        qx = (mx + 8) if qid in ("1", "4") else (gx + 8)
        qy = (gy + 8) if qid in ("1", "2") else (my + 8)
        parts.append(
            f'<span style="position:absolute;left:{qx}px;top:{qy}px;'
            f'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;'
            f'color:{_lc};font-family:{_lf};">{_h(qlbl)}</span>'
        )

    # X-axis labels (low at left, high at right, below the chart)
    parts.append(
        f'<span style="position:absolute;left:{gx}px;top:{gy + gh + 6}px;'
        f'font-size:10px;color:{_lc};font-family:{_lf};">{_h(x_labels[0])}</span>'
        f'<span style="position:absolute;right:{PAD}px;top:{gy + gh + 6}px;'
        f'font-size:10px;color:{_lc};font-family:{_lf};">{_h(x_labels[1])}</span>'
    )

    # Point labels (HTML layer, positioned next to each dot)
    for pt in points:
        px = gx + int(pt["x"] * gw)
        py = gy + gh - int(pt["y"] * gh)
        parts.append(
            f'<span data-point="{_h(pt["name"])}" style="position:absolute;left:{px + 8}px;top:{py - 8}px;'
            f'font-size:10px;color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:{_lf};white-space:nowrap;">'
            f'{_h(pt["name"])}</span>'
        )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: pie ───────────────────────────────────────────────────────────────────

_PIE_SLICE_RE = re.compile(r'^"([^"]+)"\s*:\s*([0-9.]+)')

# Eight distinct accent tokens so charts with up to 8 slices each get a unique colour.
_PIE_ACCENTS = [
    "var(--edge-strong,var(--accent-1,#60a5fa))",
    "var(--node-accent-2,var(--accent-2,#34d399))",
    "var(--accent-3,#f59e0b)",
    "var(--accent-4,#818cf8)",
    "var(--accent-5,#f87171)",
    "var(--accent-6,#2dd4bf)",
    "var(--node-border,var(--card-border,#DAD7CE))",
    "var(--node-fg-dim,var(--text-secondary,#75736C))",
]


def _layout_pie(src: str, direction: str, width_hint: int) -> str:
    """pie / pie showData: SVG arc-path donut with title, legend, and percentage labels.

    Fixes vs. old implementation:
    - Title extracted from inline ``pie title …`` directive syntax (not just content lines).
    - Title rendered at the **top** of the canvas, not at the bottom.
    - ``showData`` flag detected; raw values appended to legend entries when set.
    - Legend column on the right: colour swatch + label + percentage (+ raw value).
    - Palette expanded to 8 distinct accents so charts with up to 8 slices never repeat.
    - ``data-slice`` identity attribute placed on every SVG ``<path>`` element so
      selector-based oracle tests can locate each slice.
    - Percentage labels rendered inside each slice at mid-radius; suppressed only for
      slices narrower than ~14° (0.25 rad) where text would overlap neighbours.
    """
    # ── parse directive line for showData and inline title ────────────────────
    first_line = ""
    for _raw in src.splitlines():
        _s = _raw.strip()
        if _s and not _s.startswith(("%%", "//")):
            first_line = _s
            break
    show_data = bool(re.search(r'\bshowdata\b', first_line, re.I))
    _m_inline = re.match(r'^pie\b.*?\btitle\s+(.*)', first_line, re.I)
    title_from_directive = _m_inline.group(1).strip().strip('"\'') if _m_inline else ""

    # ── parse content lines ───────────────────────────────────────────────────
    content_lines = _directive_content(src)
    title = title_from_directive
    slices: list[dict] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line.lower().startswith("title "):
            title = line[6:].strip().strip('"\''); continue
        m = _PIE_SLICE_RE.match(line)
        if m:
            slices.append({"label": m.group(1), "value": float(m.group(2))})
    if not slices:
        raise ValueError("No slices found in pie chart.")

    total = sum(s["value"] for s in slices)
    if total <= 0:
        raise ValueError("Pie chart: all slice values are zero (nothing to render).")

    # ── layout geometry ───────────────────────────────────────────────────────
    TITLE_H = 28 if title else 0
    PAD = 16
    LEGEND_W = 144
    LEGEND_ITEM_H = 20
    LEGEND_SWATCH = 10

    canvas_w = width_hint or 400
    # Pie occupies the left band; legend the right.
    pie_zone_w = canvas_w - LEGEND_W - PAD * 3
    if pie_zone_w < 80:
        # Narrow canvas: stack legend below the pie instead.
        pie_zone_w = canvas_w - PAD * 2
    n_slices = len(slices)
    legend_h = n_slices * LEGEND_ITEM_H + 4

    r_out = max(40, pie_zone_w // 2 - PAD)
    pie_diam = r_out * 2 + PAD * 2
    canvas_h = TITLE_H + max(pie_diam, legend_h) + PAD * 2
    canvas_h = min(canvas_h, 560)

    # Tighten r_out so pie fits the actual canvas height too.
    pie_zone_h = canvas_h - TITLE_H - PAD * 2
    r_out = max(40, min(pie_zone_w // 2 - PAD, pie_zone_h // 2 - PAD))
    r_in = 0  # solid pie (no donut hole) — matches mermaid.js default

    cx = PAD + pie_zone_w // 2
    cy = TITLE_H + PAD + pie_zone_h // 2

    _lf = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )

    # ── title at top ──────────────────────────────────────────────────────────
    if title:
        parts.append(
            f'<div style="position:absolute;left:0;top:{PAD // 2}px;width:{canvas_w}px;'
            f'text-align:center;font-size:13px;font-weight:700;'
            f'color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:{_lf};">'
            f'{_h(title)}</div>'
        )

    # ── SVG layer: one <path> arc per slice ───────────────────────────────────
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    angle = -math.pi / 2
    for i, sl in enumerate(slices):
        sweep = (sl["value"] / total) * 2 * math.pi
        end_a = angle + sweep
        color = _PIE_ACCENTS[i % len(_PIE_ACCENTS)]
        large_arc = 1 if sweep > math.pi else 0
        ox0 = cx + r_out * math.cos(angle)
        oy0 = cy + r_out * math.sin(angle)
        ox1 = cx + r_out * math.cos(end_a)
        oy1 = cy + r_out * math.sin(end_a)
        ix0 = cx + r_in * math.cos(angle)
        iy0 = cy + r_in * math.sin(angle)
        ix1 = cx + r_in * math.cos(end_a)
        iy1 = cy + r_in * math.sin(end_a)
        d = (
            f"M {ox0:.2f},{oy0:.2f} "
            f"A {r_out},{r_out} 0 {large_arc},1 {ox1:.2f},{oy1:.2f} "
            f"L {ix1:.2f},{iy1:.2f} "
            f"A {r_in},{r_in} 0 {large_arc},0 {ix0:.2f},{iy0:.2f} "
            f"Z"
        )
        parts.append(
            f'<path d="{d}" data-slice="{_h(sl["label"])}" fill="{color}" '
            f'stroke="var(--node-bg-from,var(--card-bg-from,#ffffff))" stroke-width="2"/>'
        )
        angle = end_a
    parts.append('</svg>')

    # ── percentage labels inside each slice ───────────────────────────────────
    angle = -math.pi / 2
    for sl in slices:
        sweep = (sl["value"] / total) * 2 * math.pi
        mid_a = angle + sweep / 2
        # Place at 65% of the way from r_in to r_out (inside the slice body).
        lr = r_in + (r_out - r_in) * 0.65
        lx = cx + int(lr * math.cos(mid_a))
        ly = cy + int(lr * math.sin(mid_a))
        pct = f"{sl['value'] / total * 100:.1f}%"
        # Suppress label on slivers narrower than ~14° to avoid overlap.
        if sweep >= 0.25:
            parts.append(
                f'<span style="position:absolute;left:{lx - 20}px;top:{ly - 7}px;'
                f'width:40px;font-size:9px;font-weight:600;text-align:center;'
                f'color:var(--node-bg-from,var(--card-bg-from,#ffffff));'
                f'font-family:{_lf};pointer-events:none;">'
                f'{pct}</span>'
            )
        angle += sweep

    # ── legend (right panel) ──────────────────────────────────────────────────
    legend_x = canvas_w - LEGEND_W - PAD
    legend_y_start = TITLE_H + max(0, (canvas_h - TITLE_H - legend_h) // 2)
    if legend_y_start < TITLE_H + PAD:
        legend_y_start = TITLE_H + PAD
    for i, sl in enumerate(slices):
        color = _PIE_ACCENTS[i % len(_PIE_ACCENTS)]
        item_y = legend_y_start + i * LEGEND_ITEM_H
        pct = f"{sl['value'] / total * 100:.1f}%"
        val_suffix = f" ({sl['value']:.4g})" if show_data else ""
        label_html = f"{_h(sl['label'])} {pct}{_h(val_suffix)}"
        parts.append(
            f'<div style="position:absolute;left:{legend_x}px;top:{item_y}px;'
            f'height:{LEGEND_ITEM_H}px;display:flex;align-items:center;gap:6px;">'
            f'<div style="width:{LEGEND_SWATCH}px;height:{LEGEND_SWATCH}px;'
            f'border-radius:2px;background:{color};flex-shrink:0;"></div>'
            f'<span style="font-size:10px;'
            f'color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:{_lf};overflow:hidden;text-overflow:ellipsis;'
            f'white-space:nowrap;max-width:{LEGEND_W - LEGEND_SWATCH - 10}px;">'
            f'{label_html}</span>'
            f'</div>'
        )

    parts.append('</div>')
    return "\n".join(parts)
# ── T3: xychart-beta ──────────────────────────────────────────────────────────

def _layout_xychart(src: str, direction: str, width_hint: int) -> str:
    """xychart-beta: bar/line chart with axes."""
    content_lines = _directive_content(src)
    title = ""
    x_cats: list[str] = []
    y_range = (0.0, 100.0)
    y_label = ""  # optional axis title from  y-axis "label" min --> max
    bar_data: list[float] = []
    line_data: list[float] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        low = line.lower()
        if low.startswith("title "):
            title = line[6:].strip().strip('"\''); continue
        m = re.match(r'x-axis\s+(?:\[(.+)\]|"(.+)")', line, re.I)
        if m:
            cats = m.group(1) or m.group(2) or ""
            x_cats = [c.strip().strip('"') for c in cats.split(",") if c.strip()]; continue
        # y-axis with optional quoted label then range: y-axis "Revenue" 0 --> 10000
        m = re.match(r'y-axis\s+"([^"]+)"\s+([0-9.]+)\s*-->\s*([0-9.]+)', line, re.I)
        if m:
            y_label = m.group(1)
            y_range = (float(m.group(2)), float(m.group(3))); continue
        # y-axis range only: y-axis 0 --> 100
        m = re.match(r'y-axis\s+\[?([0-9.]+)\s*-->\s*([0-9.]+)\]?', line, re.I)
        if m:
            y_range = (float(m.group(1)), float(m.group(2))); continue
        m = re.match(r'bar\s+\[(.+)\]', line, re.I)
        if m:
            bar_data = [float(v.strip()) for v in m.group(1).split(",") if v.strip()]; continue
        m = re.match(r'line\s+\[(.+)\]', line, re.I)
        if m:
            line_data = [float(v.strip()) for v in m.group(1).split(",") if v.strip()]
    data = bar_data or line_data
    if not data:
        raise ValueError("No data found in xychart-beta.")

    PAD_H, PAD_V, AXIS_W = 48, 32, 32
    canvas_w = width_hint or 480
    canvas_h = 300
    cx_start = PAD_H + AXIS_W
    cy_top = PAD_V + (20 if title else 0)
    cw = canvas_w - cx_start - PAD_H
    ch = canvas_h - cy_top - PAD_V - 24
    y_min, y_max = y_range
    y_span = (y_max - y_min) or 1.0
    n = len(data)
    bar_unit = cw // n

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    # Axes-only SVG (bottom layer — behind bars)
    _tick_color = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"
    _tick_count = 5
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
        f'<line x1="{cx_start}" y1="{cy_top}" x2="{cx_start}" y2="{cy_top + ch}" '
        f'stroke="{_tick_color}" stroke-width="1.5"/>'
        f'<line x1="{cx_start}" y1="{cy_top + ch}" x2="{cx_start + cw}" y2="{cy_top + ch}" '
        f'stroke="{_tick_color}" stroke-width="1.5"/>'
    )
    for _i in range(_tick_count + 1):
        _tv = y_min + (y_span * _i / _tick_count)
        _ty = cy_top + ch - int((_tv - y_min) / y_span * ch)
        # tick mark on the Y-axis
        parts.append(
            f'<line x1="{cx_start - 4}" y1="{_ty}" x2="{cx_start}" y2="{_ty}" '
            f'stroke="{_tick_color}" stroke-width="1"/>'
        )
        # horizontal grid line across the plot area (skip the bottom baseline)
        if _i > 0:
            parts.append(
                f'<line x1="{cx_start}" y1="{_ty}" x2="{cx_start + cw}" y2="{_ty}" '
                f'stroke="{_tick_color}" stroke-width="0.5" '
                f'stroke-dasharray="4 3" opacity="0.5"/>'
            )
    parts.append('</svg>')
    # Y-axis tick labels
    _label_color = "var(--node-fg-dim,var(--text-secondary,#75736C))"
    _label_font = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"
    for _i in range(_tick_count + 1):
        _tv = y_min + (y_span * _i / _tick_count)
        _ty = cy_top + ch - int((_tv - y_min) / y_span * ch)
        parts.append(
            f'<span style="position:absolute;right:{canvas_w - cx_start + 6}px;'
            f'top:{_ty - 6}px;font-size:9px;line-height:1;'
            f'color:{_label_color};font-family:{_label_font};">'
            f'{int(_tv)}</span>'
        )
    # Y-axis label (optional; from  y-axis "label" min --> max  syntax)
    if y_label:
        parts.append(
            f'<span data-y-label="{_h(y_label)}" style="position:absolute;'
            f'writing-mode:vertical-lr;transform:rotate(180deg);'
            f'left:2px;top:{cy_top}px;height:{ch}px;width:{PAD_H - 4}px;'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-size:9px;color:{_label_color};font-family:{_label_font};'
            f'white-space:nowrap;overflow:hidden;">'
            f'{_h(y_label)}</span>'
        )
    if bar_data:
        bar_w = max(8, bar_unit - 8)
        for i, v in enumerate(bar_data):
            norm = max(0.0, min(1.0, (v - y_min) / y_span))
            bh = max(4, int(norm * ch))
            bx = cx_start + i * bar_unit + (bar_unit - bar_w) // 2
            by = cy_top + ch - bh
            cat = x_cats[i] if i < len(x_cats) else str(i + 1)
            parts.append(
                f'<div data-category="{_h(cat)}" style="position:absolute;left:{bx}px;top:{by}px;'
                f'width:{bar_w}px;height:{bh}px;'
                f'background:var(--edge-strong,var(--accent-1,#60a5fa));'
                f'border-radius:2px 2px 0 0;box-sizing:border-box;"></div>'
            )
            parts.append(
                f'<span style="position:absolute;'
                f'left:{bx - (bar_unit - bar_w) // 2}px;top:{cy_top + ch + 4}px;'
                f'width:{bar_unit}px;font-size:10px;text-align:center;'
                f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
                f'{_h(cat)}</span>'
            )
    # Line series SVG overlay — rendered after bars so line appears on top
    _line_color = "var(--accent-3,#B7791F)"
    if line_data:
        pts_coords = []
        for i, v in enumerate(line_data):
            bx = cx_start + i * bar_unit + bar_unit // 2
            by = cy_top + ch - int(max(0.0, min(1.0, (v - y_min) / y_span)) * ch)
            pts_coords.append((bx, by))
        parts.append(
            f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
            f'overflow:visible;pointer-events:none;">'
        )
        for i in range(len(pts_coords) - 1):
            x1, y1a = pts_coords[i]; x2, y2a = pts_coords[i + 1]
            parts.append(
                f'<line x1="{x1}" y1="{y1a}" x2="{x2}" y2="{y2a}" '
                f'stroke="{_line_color}" stroke-width="2.5"/>'
            )
        for bx, by in pts_coords:
            r = 4
            poly = " ".join(
                f"{bx + int(r * math.cos(math.pi * k / 3))},"
                f"{by + int(r * math.sin(math.pi * k / 3))}"
                for k in range(6)
            )
            parts.append(f'<polygon points="{poly}" fill="{_line_color}"/>')
        parts.append('</svg>')
    if title:
        parts.append(
            f'<div style="position:absolute;left:{cx_start}px;top:{PAD_V}px;'
            f'font-size:12px;font-weight:700;color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">{_h(title)}</div>'
        )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: mindmap ───────────────────────────────────────────────────────────────

# Section colour palette for depth-1 branches (rotates for > 7 branches).
# Section-0 is rgba(53,148,103,...) so existing colour-check tests continue
# to pass without modification.
_MINDMAP_SECTION_COLORS: tuple[str, ...] = (
    "rgba(53,148,103,0.08)",   # teal-green  — section 0 (colour tests depend on this)
    "rgba(99,102,241,0.08)",   # indigo
    "rgba(245,158,11,0.08)",   # amber
    "rgba(239,68,68,0.08)",    # red
    "rgba(20,184,166,0.08)",   # teal
    "rgba(168,85,247,0.08)",   # purple
    "rgba(236,72,153,0.08)",   # pink
)

# Leaf opacity — lighter tint of the section colour; satisfies "≤0.06" assertion.
_MINDMAP_LEAF_ALPHA: str = "0.04"


def _mindmap_count_leaves(idx: int, children: "list[list[int]]") -> int:
    """Return the number of leaf nodes in the subtree rooted at *idx*."""
    if not children[idx]:
        return 1
    return sum(_mindmap_count_leaves(c, children) for c in children[idx])


def _layout_mindmap(src: str, direction: str, width_hint: int) -> str:
    """mindmap: radial spider layout — root at centre, branches radiating outward."""
    content_lines = _directive_content(src)
    flat: list[dict] = []
    for raw in content_lines:
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith(("%%", "//")):
            continue
        indent = len(line) - len(line.lstrip())
        raw_node = line.strip()
        # Strip class annotations (:::classname) and icon hints (::icon(...))
        raw_node = re.sub(r'\s*:{2,3}[\w-]+(?:\([^)]*\))?', '', raw_node).strip()
        # Detect Mermaid mindmap shape from syntax wrapper
        shape = "default"
        m = re.match(r'^\w+\(\((.+?)\)\)', raw_node)       # id((circle))
        if m:
            lbl, shape = m.group(1), "circle"
        else:
            m = re.match(r'^\w+\)\)(.+?)\(\(', raw_node)   # id))cloud((
            if m:
                lbl, shape = m.group(1), "cloud"
            else:
                m = re.match(r'^\w+\[(.+?)\]', raw_node)   # id[rect]
                if m:
                    lbl, shape = m.group(1), "rect"
                else:
                    m = re.match(r'^\w+\((.+?)\)', raw_node)  # id(pill)
                    if m:
                        lbl, shape = m.group(1), "pill"
                    else:
                        lbl = re.sub(r'^[\[\(\{:]+|[\]\)\}]+$', '', raw_node).strip()
        # Strip Markdown bold/italic markers from label text
        lbl = re.sub(r'\*\*(.+?)\*\*', r'\1', lbl)
        lbl = re.sub(r'\*(.+?)\*', r'\1', lbl)
        if lbl:
            flat.append({"depth": indent, "label": lbl, "shape": shape})

    if not flat:
        raise ValueError("No nodes found in mindmap.")

    # Normalise indentation so root is always depth 0
    min_d = min(n["depth"] for n in flat)
    for n in flat:
        n["depth"] -= min_d

    # Build parent-child tree from the flat, indented list
    n_nodes = len(flat)
    children: list[list[int]] = [[] for _ in range(n_nodes)]
    parent_of: list[int] = [-1] * n_nodes
    for i in range(1, n_nodes):
        for j in range(i - 1, -1, -1):
            if flat[j]["depth"] < flat[i]["depth"]:
                parent_of[i] = j
                children[j].append(i)
                break

    # Propagate depth-1 section index to every descendant (for colour coding)
    section_of: list[int] = [-1] * n_nodes
    for sect_idx, child_idx in enumerate(children[0]):
        section_of[child_idx] = sect_idx
    pending: list[int] = list(children[0])
    while pending:
        cur = pending.pop()
        for ci in children[cur]:
            section_of[ci] = section_of[cur]
            pending.append(ci)

    # Compute actual tree depth (0 for root, 1 for root's children, etc.)
    # The raw flat[i]["depth"] is raw indentation — not reliable as a depth level.
    tree_depth: list[int] = [0] * n_nodes
    for i in range(1, n_nodes):
        if parent_of[i] >= 0:
            tree_depth[i] = tree_depth[parent_of[i]] + 1

    # Canvas dimensions — expand to fit the maximum depth radially
    max_depth = max(tree_depth)
    _BASE_R = 85    # root → depth-1 radius in px
    _STEP_R = 70    # additional radius per depth level
    max_r = _BASE_R + max_depth * _STEP_R
    _MARGIN = 90    # px clearance for node label + padding beyond the outermost ring
    min_side = 2 * (max_r + _MARGIN)
    canvas_w = max(width_hint or 480, min_side)
    canvas_h = canvas_w
    cx = canvas_w // 2
    cy = canvas_h // 2

    # Assign radial positions: flat index → (x, y) floats
    positions: dict[int, tuple[float, float]] = {0: (float(cx), float(cy))}

    def _place_radial(idx: int, start: float, end: float, depth: int) -> None:
        """Place children of *idx* in the angular sector [start, end] at *depth*."""
        ch = children[idx]
        if not ch:
            return
        total = sum(_mindmap_count_leaves(c, children) for c in ch)
        cur = start
        for ci in ch:
            leaves = _mindmap_count_leaves(ci, children)
            span = (end - start) * leaves / total
            mid = cur + span / 2
            r = _BASE_R + depth * _STEP_R
            positions[ci] = (
                cx + r * math.cos(math.radians(mid)),
                cy + r * math.sin(math.radians(mid)),
            )
            _place_radial(ci, cur, cur + span, depth + 1)
            cur += span

    # Sweep from top (−90°) clockwise to bottom (+270°) so root branches upward
    _place_radial(0, -90.0, 270.0, 1)

    # ── Render ────────────────────────────────────────────────────────────────
    _ROOT_DIAM = 60   # root circle diameter in px
    _NODE_H = 32      # pill / rect node height in px
    _NODE_W_MIN = 80  # minimum pill / rect node width in px

    parts: list[str] = [
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    ]

    # Pre-compute approximate bounding-box half-dimensions for each node so that
    # edges can start/end at the node boundary rather than the node center.
    from ._constants import _measure_text_px as _mm_px
    def _node_hw(idx: int) -> tuple[float, float]:
        """Return (half_w, half_h) of node idx for boundary clipping."""
        nd = flat[idx]
        depth_i = tree_depth[idx]
        shape_i = nd["shape"]
        if depth_i == 0 and shape_i in ("circle", "default"):
            return _ROOT_DIAM / 2, _ROOT_DIAM / 2  # circle
        if shape_i == "circle":
            return 24.0, 24.0  # radius
        # rect / pill / cloud / default: use measured text width
        lbl_w = max(_NODE_W_MIN, _mm_px(nd["label"]) + 16)
        return lbl_w / 2, _NODE_H / 2

    def _boundary_pt(
        ox: float, oy: float, tx: float, ty: float, hw: float, hh: float, is_circle: bool
    ) -> tuple[float, float]:
        """Return the point on the boundary of the *origin* node in the direction of (tx, ty)."""
        ddx, ddy = tx - ox, ty - oy
        dist = math.hypot(ddx, ddy) or 1.0
        if is_circle:
            r = hw  # hw == hh for circles
            return ox + ddx / dist * r, oy + ddy / dist * r
        # Rect / pill: find first intersection with the bounding box edges
        t = float("inf")
        if ddx != 0:
            t = min(t, hw / abs(ddx))
        if ddy != 0:
            t = min(t, hh / abs(ddy))
        return ox + ddx * t, oy + ddy * t

    # SVG edge layer — drawn first so node divs render above connectors
    edge_color = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.6)))"
    svg_parts: list[str] = [
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;'
        f'height:{canvas_h}px;overflow:visible;pointer-events:none;">'
    ]
    for i in range(1, n_nodes):
        p = parent_of[i]
        if p < 0:
            continue
        px_p, py_p = positions[p]
        px_c, py_c = positions[i]
        # Compute boundary start/end points so edges touch node edges, not centres
        p_hw, p_hh = _node_hw(p)
        c_hw, c_hh = _node_hw(i)
        p_is_circ = flat[p]["shape"] in ("circle", "default") and tree_depth[p] == 0
        p_is_circ = p_is_circ or flat[p]["shape"] == "circle"
        c_is_circ = flat[i]["shape"] == "circle"
        sx, sy = _boundary_pt(px_p, py_p, px_c, py_c, p_hw, p_hh, p_is_circ)
        ex, ey = _boundary_pt(px_c, py_c, px_p, py_p, c_hw, c_hh, c_is_circ)
        # Quadratic bezier with control point nudged radially outward from centre
        mx = (sx + ex) / 2
        my = (sy + ey) / 2
        dx, dy = mx - cx, my - cy
        dl = math.hypot(dx, dy) or 1.0
        qx = mx + dx / dl * 18
        qy = my + dy / dl * 18
        svg_parts.append(
            f'<path d="M{sx:.1f},{sy:.1f} Q{qx:.1f},{qy:.1f} {ex:.1f},{ey:.1f}" '
            f'fill="none" stroke="{edge_color}" stroke-width="1.5"/>'
        )
    svg_parts.append('</svg>')
    parts.extend(svg_parts)

    # Node divs
    for i, node in enumerate(flat):
        px, py = positions[i]
        depth = tree_depth[i]
        shape = node["shape"]
        sec = section_of[i]

        # Background colour — root uses card gradient; branches use section palette
        if depth == 0:
            bg = (
                f'background:linear-gradient(180deg,'
                f'var(--node-bg-from,var(--card-bg-from,#ffffff)),'
                f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));'
                f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
            )
        elif depth == 1:
            sec_idx = sec % len(_MINDMAP_SECTION_COLORS) if sec >= 0 else 0
            bg = f'background:{_MINDMAP_SECTION_COLORS[sec_idx]};'
        else:
            sec_idx = sec % len(_MINDMAP_SECTION_COLORS) if sec >= 0 else 0
            base_color = _MINDMAP_SECTION_COLORS[sec_idx]
            # Replace the opacity to produce a lighter leaf tint (≤ 0.06)
            leaf_bg = re.sub(r'0\.\d+\)', f'{_MINDMAP_LEAF_ALPHA})', base_color)
            bg = f'background:{leaf_bg};'

        bold = "font-weight:700;" if depth == 0 else ""

        # Shape geometry: root or ((circle)) → disc; [rect] → sharp corners; default → pill
        if depth == 0 and shape in ("circle", "default"):
            w = h = _ROOT_DIAM
            pos_s = (
                f'left:{int(px - w / 2)}px;top:{int(py - h / 2)}px;'
                f'width:{w}px;height:{h}px;'
            )
            layout_s = 'display:flex;align-items:center;justify-content:center;'
            pad_s = 'padding:4px;box-sizing:border-box;'
            radius_s = 'border-radius:50%;'
        elif shape == "circle":
            diam = 48
            pos_s = (
                f'left:{int(px - diam / 2)}px;top:{int(py - diam / 2)}px;'
                f'width:{diam}px;height:{diam}px;'
            )
            layout_s = 'display:flex;align-items:center;justify-content:center;'
            pad_s = 'padding:4px;box-sizing:border-box;'
            radius_s = 'border-radius:50%;'
        elif shape == "rect":
            pos_s = (
                f'left:{int(px - _NODE_W_MIN / 2)}px;top:{int(py - _NODE_H / 2)}px;'
                f'min-width:{_NODE_W_MIN}px;height:{_NODE_H}px;'
            )
            layout_s = 'display:flex;align-items:center;'
            pad_s = 'padding:4px 8px;box-sizing:border-box;'
            radius_s = 'border-radius:4px;'
        else:
            # pill / cloud / default
            pos_s = (
                f'left:{int(px - _NODE_W_MIN / 2)}px;top:{int(py - _NODE_H / 2)}px;'
                f'min-width:{_NODE_W_MIN}px;height:{_NODE_H}px;'
            )
            layout_s = 'display:flex;align-items:center;'
            pad_s = 'padding:4px 8px;box-sizing:border-box;'
            radius_s = 'border-radius:var(--node-radius,16px);'

        parts.append(
            f'<div class="node" data-node-id="{i}" style="position:absolute;'
            f'{pos_s}{layout_s}{pad_s}{radius_s}{bg}">'
            f'<span class="node-label" style="font-size:13px;{bold}'
            f'color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));'
            f'text-align:center;">'
            f'{_h(node["label"])}</span></div>'
        )

    parts.append('</div>')
    return "\n".join(parts)


# ── T3: block-beta ────────────────────────────────────────────────────────────

# Matches a complete block-beta token (ID + optional shape + optional :span),
# honouring quoted labels that may contain spaces.  Shape alternatives are
# ordered longest-first so that (( and ([ do not shadow each other.
_BLOCK_TOKEN_RE = re.compile(
    r'(?P<id>\w+)'
    r'(?:'
        r'>>"(?P<arrow_lbl>[^"]*)"'               # >> arrow chevron
        r'|>\[\"(?P<asym_lbl>[^\"]*)\"\]'           # >[ asymmetric
        r'|\(\(\"(?P<circle_lbl>[^\"]*)\"\)\)'       # (( circle
        r'|\(\[\"(?P<stadium_lbl>[^\"]*)\"\]\)'      # ([ stadium
        r'|\[\(\"(?P<cyl_lbl>[^\"]*)\"\)\]'          # [( cylinder
        r'|\{\{\"(?P<hex_lbl>[^\"]*)\"\}\}'          # {{ hexagon
        r'|\{\"(?P<diam_lbl>[^\"]*)\"\}'             # { diamond
        r'|\[\"(?P<rect_lbl>[^\"]*)\"\]'             # [ rect with label
        r'|\(\"(?P<round_lbl>[^\"]*)\"\)'            # ( rounded rect
    r')?'
    r'(?::(?P<span>\d+))?'
)

# Lines that start with these keywords are whole-line directives; skip them
# instead of tokenising their tokens as spurious block nodes.
_BLOCK_SKIP_LINE_RE = re.compile(r'^(style|classDef|class)\b', re.I)

# Extra inline CSS appended to the base node style per block shape.
# Clipped shapes override border to none to avoid rectangular CSS-border artefacts.
_BLOCK_SHAPE_CSS: dict[str, str] = {
    "arrow":   (
        "clip-path:polygon(0% 0%,calc(100% - 14px) 0%,100% 50%,"
        "calc(100% - 14px) 100%,0% 100%);border-radius:0;border:none;"
    ),
    "circle":  "border-radius:50%;",
    "stadium": "border-radius:28px;",
    "diamond": (
        "clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);"
        "border-radius:0;border:none;"
    ),
    "hexagon": (
        "clip-path:polygon(25% 0%,75% 0%,100% 50%,75% 100%,25% 100%,0% 50%);"
        "border-radius:0;border:none;"
    ),
    "asym":    (
        "clip-path:polygon(0% 0%,100% 0%,100% 100%,10px 100%);"
        "border-radius:0;border:none;"
    ),
    "cyl":     "border-radius:4px 4px 0 0;",
    "round":   "border-radius:28px;",
    "rect":    "",
}

# CSS class name (after "node ") per block shape.
_BLOCK_SHAPE_CLASS: dict[str, str] = {
    "arrow":   "node-arrow",
    "circle":  "node-circle",
    "stadium": "node-stadium",
    "diamond": "node-diamond",
    "hexagon": "node-hexagon",
    "asym":    "node-asym",
    "cyl":     "node-cyl",
    "round":   "node-round",
    "rect":    "node-rect",
}


def _layout_block(src: str, direction: str, width_hint: int) -> str:
    '''block-beta: blocks in declared rows/columns with arrows.

    Fixes vs. original implementation:
    - Whole-line directives (style, classDef, class) are skipped rather than
      tokenised into spurious block nodes.
    - Tokeniser uses _BLOCK_TOKEN_RE.finditer() so quoted labels with spaces
      (e.g. A["Foo Bar"]) are preserved intact.
    - space / space:N tokens advance the column cursor without producing a
      visible block node.
    - >> arrow shape is parsed and rendered with a clip-path chevron.
    - Standard flowchart shapes ((circle)), (["stadium"]), [("cylinder")],
      {diamond}, {{hexagon}} are parsed and rendered with matching CSS.
    - Column cursor tracks cumulative span so spanning blocks (:2) and
      spacers correctly advance the grid position.
    '''
    content_lines = _directive_content(src)
    rows: list[list[dict]] = []
    current_row: list[dict] = []
    col_cursor = 0          # column slots consumed in the current row
    edges: list[tuple[str, str]] = []
    n_cols = 3
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        # columns N directive
        m = re.match(r'columns\s+(\d+)', line, re.I)
        if m:
            n_cols = int(m.group(1)); continue
        # Skip whole-line styling directives (style / classDef / class)
        if _BLOCK_SKIP_LINE_RE.match(line):
            continue
        # Edge lines -- split on operators: A --> B --> C -> [(A,B),(B,C)]
        if '-->' in line or '<-->' in line or '---' in line:
            _ids = re.findall(r'\b(\w+)\b', line)
            for _i in range(len(_ids) - 1):
                edges.append((_ids[_i], _ids[_i + 1]))
            continue
        # Block content -- tokenise respecting quoted labels
        for m2 in _BLOCK_TOKEN_RE.finditer(line):
            nid = m2.group("id")
            span_str = m2.group("span")
            span = int(span_str) if span_str else 1

            if nid.lower() == "space":
                # Spacer: advance column cursor span times, no visible block
                for _ in range(span):
                    current_row.append({"is_space": True, "span": 1})
                    col_cursor += 1
                    if col_cursor >= n_cols:
                        rows.append(current_row); current_row = []; col_cursor = 0
                continue

            # Determine shape and label from matched named groups
            arrow_lbl   = m2.group("arrow_lbl")
            asym_lbl    = m2.group("asym_lbl")
            circle_lbl  = m2.group("circle_lbl")
            stadium_lbl = m2.group("stadium_lbl")
            cyl_lbl     = m2.group("cyl_lbl")
            hex_lbl     = m2.group("hex_lbl")
            diam_lbl    = m2.group("diam_lbl")
            rect_lbl    = m2.group("rect_lbl")
            round_lbl   = m2.group("round_lbl")

            if arrow_lbl is not None:
                shape, label = "arrow", arrow_lbl
            elif asym_lbl is not None:
                shape, label = "asym", asym_lbl
            elif circle_lbl is not None:
                shape, label = "circle", circle_lbl
            elif stadium_lbl is not None:
                shape, label = "stadium", stadium_lbl
            elif cyl_lbl is not None:
                shape, label = "cyl", cyl_lbl
            elif hex_lbl is not None:
                shape, label = "hexagon", hex_lbl
            elif diam_lbl is not None:
                shape, label = "diamond", diam_lbl
            elif rect_lbl is not None:
                shape, label = "rect", rect_lbl
            elif round_lbl is not None:
                shape, label = "round", round_lbl
            else:
                shape, label = "rect", nid  # bare ID -- use ID as label

            current_row.append({
                "id": nid,
                "label": label,
                "span": span,
                "shape": shape,
                "is_space": False,
            })
            col_cursor += span
            if col_cursor >= n_cols:
                rows.append(current_row); current_row = []; col_cursor = 0

    if current_row:
        rows.append(current_row)
    if not rows or not any(not b.get("is_space") for row in rows for b in row):
        raise ValueError("No blocks found in block-beta.")

    PAD_H, PAD_V, CELL_H, CELL_GAP = 40, 24, 56, 24
    canvas_w = width_hint or PAD_H * 2 + n_cols * 120 + (n_cols - 1) * CELL_GAP
    # Compute responsive cell width so blocks fill the canvas
    available = canvas_w - 2 * PAD_H - (n_cols - 1) * CELL_GAP
    cell_w = max(80, available // n_cols)
    canvas_h = PAD_V * 2 + len(rows) * (CELL_H + CELL_GAP) - CELL_GAP

    # Build block positions for edge routing (non-space blocks only)
    block_pos: dict[str, dict] = {}
    for ri, row in enumerate(rows):
        ry = PAD_V + ri * (CELL_H + CELL_GAP)
        cx_cur = PAD_H
        for blk in row:
            bw = cell_w * blk["span"] + CELL_GAP * (blk["span"] - 1)
            if not blk.get("is_space"):
                block_pos[blk["id"]] = {"x": cx_cur, "y": ry, "w": bw, "h": CELL_H}
            cx_cur += bw + CELL_GAP

    edge_color = "var(--edge,rgba(100,116,139,0.7))"
    svg_edges: list[str] = []
    for src_id, dst_id in edges:
        if src_id not in block_pos or dst_id not in block_pos:
            continue
        s, d = block_pos[src_id], block_pos[dst_id]
        # Right-center of source to left-center of dest (same row);
        # cross-row: bottom-center to top-center.
        if abs((s["y"] + s["h"] / 2) - (d["y"] + d["h"] / 2)) < CELL_H:
            x1 = s["x"] + s["w"]; y1 = s["y"] + s["h"] // 2
            x2 = d["x"]; y2 = d["y"] + d["h"] // 2
        else:
            x1 = s["x"] + s["w"] // 2; y1 = s["y"] + s["h"]
            x2 = d["x"] + d["w"] // 2; y2 = d["y"]
        svg_edges.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{edge_color}" stroke-width="1.5" '
            f'marker-end="url(#arr)"'
            f' data-src="{_h(src_id)}" data-dst="{_h(dst_id)}"/>'
        )

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    # Block nodes first, SVG edges on top (later in DOM = higher stacking order)
    for ri, row in enumerate(rows):
        ry = PAD_V + ri * (CELL_H + CELL_GAP)
        cx_cur = PAD_H
        for blk in row:
            bw = cell_w * blk["span"] + CELL_GAP * (blk["span"] - 1)
            if not blk.get("is_space"):
                shape = blk.get("shape", "rect")
                shape_css = _BLOCK_SHAPE_CSS.get(shape, "")
                shape_class = _BLOCK_SHAPE_CLASS.get(shape, "node-rect")
                parts.append(
                    f'<div class="node {shape_class}" data-node-id="{_h(blk["id"])}" style="position:absolute;'
                    f'left:{cx_cur}px;top:{ry}px;width:{bw}px;height:{CELL_H}px;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
                    f'border-radius:var(--node-radius,8px);box-sizing:border-box;{shape_css}'
                    f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
                    f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));">'
                    f'<span class="node-label" style="'
                    f'font-size:13px;font-weight:700;color:var(--node-fg,var(--text-primary,#191A17));'
                    f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));text-align:center;">'
                    f'{_h(blk["label"])}</span></div>'
                )
            cx_cur += bw + CELL_GAP
    # SVG edge layer last so connectors appear above block backgrounds
    if svg_edges:
        parts.append(
            f'<svg style="position:absolute;top:0;left:0;width:{canvas_w}px;height:{canvas_h}px;'
            f'overflow:visible;pointer-events:none;">'
            f'<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
            f'<path d="M0,0 L0,6 L8,3 z" fill="{edge_color}"/></marker></defs>'
            + "".join(svg_edges) + '</svg>'
        )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: packet-beta ───────────────────────────────────────────────────────────

# Absolute range: "start-end: label" or "start: label"
_PKT_FIELD_RE = re.compile(r'^(\d+)(?:-(\d+))?\s*:\s*(.+)$')
# Relative width: "+N: label"  — N bits wide starting from current cursor position
_PKT_REL_RE = re.compile(r'^\+(\d+)\s*:\s*(.+)$')
_PKT_BITS_PER_ROW = 32   # standard protocol row width; mmdc wraps here
_PKT_RULER_H = 20        # height of the per-row bit-number ruler strip
_PKT_CELL_H = 48         # height of each field row
_PKT_ROW_GAP = 12        # vertical gap between successive rows


def _layout_packet(src: str, direction: str, width_hint: int) -> str:
    """packet-beta: proportional bit-field cells, 32-bit row wrapping, bit ruler.

    Supports absolute ranges ("start-end: label", "start: label") and relative
    widths ("+N: label" — N bits wide from the current cursor position).
    Fields that span a 32-bit row boundary are rendered in both affected rows,
    clipped to the visible portion of each row.  A ruler strip with tick marks
    at every 8 bits sits above each field row.
    """
    content_lines = _directive_content(src)
    fields: list[dict] = []
    _next_bit = 0  # cursor for relative +N syntax
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        # Relative +N syntax (must be tested before absolute to avoid false matches)
        m = _PKT_REL_RE.match(line)
        if m:
            n_bits = int(m.group(1))
            if n_bits <= 0:
                raise ValueError(
                    f"packet-beta: relative width +{n_bits} must be > 0."
                )
            start = _next_bit
            end = _next_bit + n_bits - 1
            fields.append({
                "start": start, "end": end,
                "bits": n_bits, "label": m.group(2).strip().strip('"'),
            })
            _next_bit = end + 1
            continue
        # Absolute range: "start-end: label" or "start: label"
        m = _PKT_FIELD_RE.match(line)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            if start < 0 or end < start:
                raise ValueError(
                    f"packet-beta: invalid bit range {start}-{end} "
                    f"(start must be \u2265 0, end must be \u2265 start)."
                )
            fields.append({
                "start": start, "end": end,
                "bits": end - start + 1, "label": m.group(3).strip().strip('"'),
            })
            _next_bit = end + 1
    if not fields:
        raise ValueError("No fields found in packet-beta.")

    max_bit = max(f["end"] for f in fields)
    BITS_PER_ROW = _PKT_BITS_PER_ROW
    n_rows = math.ceil((max_bit + 1) / BITS_PER_ROW)

    PAD_H, PAD_V = 40, 24
    RULER_H = _PKT_RULER_H
    CELL_H = _PKT_CELL_H
    ROW_GAP = _PKT_ROW_GAP
    canvas_w = width_hint or 640
    available_w = canvas_w - PAD_H * 2
    # One bit unit is always 1/32 of available_w so proportions are consistent
    bit_unit = available_w / BITS_PER_ROW

    row_pitch = RULER_H + CELL_H + ROW_GAP
    canvas_h = PAD_V * 2 + n_rows * row_pitch - ROW_GAP

    _bc = "var(--node-border,var(--card-border,#DAD7CE))"
    _lc = "var(--node-fg-dim,var(--text-secondary,#75736C))"
    _fc = "var(--node-fg,var(--text-primary,#191A17))"
    _bg = (
        "linear-gradient(180deg,"
        "var(--node-bg-from,var(--card-bg-from,#ffffff)),"
        "var(--node-bg-to,var(--card-bg-to,#F7F6F2)))"
    )
    _lf = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )

    for row_idx in range(n_rows):
        row_start_bit = row_idx * BITS_PER_ROW
        row_end_bit = row_start_bit + BITS_PER_ROW - 1
        row_y = PAD_V + row_idx * row_pitch

        # ── Bit ruler SVG ────────────────────────────────────
        # Ticks at every 8 bits (0, 8, 16, 24) plus the last bit of the row
        # (31, 63, \u2026).  SVG text labels are placed above the tick lines.
        tick_offsets: list[int] = list(range(0, BITS_PER_ROW, 8)) + [BITS_PER_ROW - 1]
        seen: set[int] = set()
        ruler_ticks: list[str] = []
        for tick_off in tick_offsets:
            if tick_off in seen:
                continue
            seen.add(tick_off)
            tx = int(tick_off * bit_unit)
            ruler_ticks.append(
                f'<line x1="{tx}" y1="{RULER_H - 6}" x2="{tx}" y2="{RULER_H}" '
                f'stroke="{_bc}" stroke-width="1"/>'
                f'<text x="{tx}" y="{RULER_H - 8}" text-anchor="middle" '
                f'font-size="9" fill="{_lc}" '
                f'font-family="var(--label-font,-apple-system,Inter,sans-serif)">'
                f'{row_start_bit + tick_off}</text>'
            )
        parts.append(
            f'<svg data-pkt-ruler="{row_idx}" '
            f'style="position:absolute;left:{PAD_H}px;top:{row_y}px;'
            f'width:{available_w}px;height:{RULER_H}px;'
            f'overflow:visible;pointer-events:none;">'
            + "".join(ruler_ticks)
            + "</svg>"
        )

        # ── Field cells ───────────────────────────────────────────
        # Include every field whose bit range overlaps this row's bit band.
        cell_y = row_y + RULER_H
        row_fields = [
            f for f in fields
            if f["start"] <= row_end_bit and f["end"] >= row_start_bit
        ]
        for fld in row_fields:
            # Clip visible portion to this row's bit band
            vis_start = max(fld["start"], row_start_bit)
            vis_end = min(fld["end"], row_end_bit)
            local_start = vis_start - row_start_bit
            local_bits = vis_end - vis_start + 1
            fx = PAD_H + int(local_start * bit_unit)
            fw = max(2, int(local_bits * bit_unit) - 1)
            _fld_id = (
                f'{fld["start"]}-{fld["end"]}' if fld["end"] != fld["start"]
                else str(fld["start"])
            )
            bit_range_lbl = (
                f'{fld["start"]}\u2013{fld["end"]}' if fld["end"] != fld["start"]
                else str(fld["start"])
            )
            parts.append(
                f'<div class="node node-rect" data-field="{_fld_id}" style="position:absolute;'
                f'left:{fx}px;top:{cell_y}px;width:{fw}px;height:{CELL_H}px;'
                f'display:flex;flex-direction:column;align-items:center;justify-content:center;'
                f'border:1px solid {_bc};box-sizing:border-box;background:{_bg};">'
                f'<span class="node-label" style="'
                f'font-size:11px;font-weight:700;color:{_fc};'
                f'font-family:{_lf};text-align:center;'
                f'overflow:hidden;word-break:break-word;">'
                f'{_h(fld["label"])}</span>'
                f'<span style="font-size:9px;color:{_lc};font-family:{_lf};">'
                f'{bit_range_lbl}</span>'
                f'</div>'
            )

    parts.append('</div>')
    return "\n".join(parts)



# ── T3: kanban ────────────────────────────────────────────────────────────────

_KANBAN_PRIORITY_COLORS: dict[str, str] = {
    "very high": "#ef4444",
    "high":      "#f97316",
    "medium":    "#eab308",
    "low":       "#60a5fa",
    "very low":  "#9ca3af",
}

_KANBAN_META_RE = re.compile(r'@\{\s*(.*?)\s*\}', re.DOTALL)
_KANBAN_META_PAIR_RE = re.compile(
    r"""(\w+)\s*:\s*(?:'([^']*)'|"([^"]*)"|([^,}]+))"""
)


def _parse_kanban_meta(meta_str: str) -> "dict[str, str]":
    """Parse ``key: value`` pairs from a kanban ``@{...}`` metadata block.

    Supports single-quoted, double-quoted, and bare values.
    Returns a dict with lower-cased keys.
    """
    result: dict[str, str] = {}
    for m in _KANBAN_META_PAIR_RE.finditer(meta_str):
        key = m.group(1).lower()
        value = (
            m.group(2) if m.group(2) is not None
            else m.group(3) if m.group(3) is not None
            else (m.group(4) or "")
        ).strip()
        result[key] = value
    return result


def _layout_kanban(src: str, direction: str, width_hint: int) -> str:
    """kanban: cards stacked in labeled vertical columns.

    Enhancements over the baseline renderer:
    - Responsive column width fills the canvas evenly.
    - Quoted column labels (``id["Label"]``) are unwrapped.
    - ``@{ticket: …, priority: …, assigned: …}`` metadata is parsed and
      rendered as inline badge pills on the card.
    - Priority badges are colour-coded: Very High → red (#ef4444),
      High → orange (#f97316), Low → blue (#60a5fa), Very Low → grey (#9ca3af).
    - Cards with metadata are taller to accommodate the badge row.
    """
    content_lines = _directive_content(src)
    # Find minimum indentation level — that is the column header depth
    min_indent = 9999
    for raw in content_lines:
        if raw.strip() and not raw.strip().startswith(("%%", "//")):
            min_indent = min(min_indent, len(raw) - len(raw.lstrip()))
    if min_indent == 9999:
        min_indent = 0

    columns: list[dict] = []
    current_col: Optional[dict] = None
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent == min_indent:
            # Column header: strip @{…}, then unwrap quoted label if present
            col_clean = re.sub(r'@\{[^}]*\}', '', line).strip()
            m_col_lbl = re.match(r'^\w+\["([^"]+)"\]', col_clean)
            col_name = m_col_lbl.group(1) if m_col_lbl else col_clean
            current_col = {"name": col_name, "cards": []}
            columns.append(current_col)
        elif current_col is not None:
            # Card line: extract @{…} metadata block first
            meta_match = _KANBAN_META_RE.search(line)
            meta: dict[str, str] = {}
            if meta_match:
                meta = _parse_kanban_meta(meta_match.group(1))
                line_no_meta = line[:meta_match.start()].strip()
            else:
                line_no_meta = line.strip()
            # Strip any remaining @{…} fragments then unwrap quoted label
            line_no_meta = re.sub(r'@\{[^}]*\}', '', line_no_meta).strip()
            m_lbl = re.match(r'^\w+\["([^"]+)"\]', line_no_meta)
            card_label = m_lbl.group(1) if m_lbl else line_no_meta
            if card_label:
                current_col["cards"].append({"label": card_label, "meta": meta})

    if not columns:
        raise ValueError("No columns found in kanban.")

    PAD_H, PAD_V = 24, 24
    COL_GAP, HDR_H = 12, 36
    CARD_H_BASE, CARD_H_META, CARD_GAP = 44, 68, 6
    n_cols = len(columns)
    canvas_w = width_hint or (PAD_H * 2 + n_cols * 160 + max(n_cols - 1, 0) * COL_GAP)

    # Responsive column width: divide available space evenly across all columns
    available_w = canvas_w - PAD_H * 2 - max(n_cols - 1, 0) * COL_GAP
    col_w = max(100, available_w // n_cols)

    # Canvas height driven by the tallest column's content
    def _col_content_h(col: dict) -> int:
        total = 0
        for card in col["cards"]:
            total += (CARD_H_META if card["meta"] else CARD_H_BASE) + CARD_GAP
        return total

    max_col_h = max((_col_content_h(c) for c in columns), default=0)
    canvas_h = PAD_V * 2 + HDR_H + 8 + max_col_h

    _lf = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"
    _fg = "var(--node-fg,var(--text-primary,#191A17))"
    _fg_dim = "var(--node-fg-dim,var(--text-secondary,#75736C))"

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    for ci, col in enumerate(columns):
        cx = PAD_H + ci * (col_w + COL_GAP)
        parts.append(
            f'<div data-col="{_h(col["name"])}" style="position:absolute;left:{cx}px;top:{PAD_V}px;'
            f'width:{col_w}px;height:{HDR_H}px;'
            f'display:flex;align-items:center;justify-content:center;'
            f'border-bottom:2px solid var(--edge-strong,var(--accent-1,#60a5fa));'
            f'box-sizing:border-box;">'
            f'<span style="font-size:12px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.08em;color:{_fg};font-family:{_lf};">'
            f'{_h(col["name"])}</span></div>'
        )
        ky = PAD_V + HDR_H + 8
        for card in col["cards"]:
            meta = card["meta"]
            card_h = CARD_H_META if meta else CARD_H_BASE
            if meta:
                # Build badge pills: ticket, priority (coloured), assigned
                badges: list[str] = []
                priority_val = meta.get("priority", "").strip()
                if meta.get("ticket"):
                    badges.append(
                        f'<span data-badge="ticket" style="'
                        f'font-size:9px;padding:1px 5px;border-radius:3px;'
                        f'background:var(--node-bg-to,var(--card-bg-to,#F7F6F2));'
                        f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
                        f'color:{_fg_dim};font-family:{_lf};white-space:nowrap;">'
                        f'{_h(meta["ticket"])}</span>'
                    )
                if priority_val:
                    p_bg = _KANBAN_PRIORITY_COLORS.get(priority_val.lower(),
                                                        "var(--node-border,var(--card-border,#DAD7CE))")
                    p_fg = "#fff" if p_bg.startswith("#") else _fg_dim
                    badges.append(
                        f'<span data-badge="priority" style="'
                        f'font-size:9px;padding:1px 5px;border-radius:3px;'
                        f'background:{p_bg};color:{p_fg};'
                        f'font-family:{_lf};white-space:nowrap;">'
                        f'{_h(priority_val)}</span>'
                    )
                if meta.get("assigned"):
                    badges.append(
                        f'<span data-badge="assigned" style="'
                        f'font-size:9px;padding:1px 5px;border-radius:3px;'
                        f'background:rgba(96,165,250,0.12);'
                        f'border:1px solid var(--edge-strong,var(--accent-1,#60a5fa));'
                        f'color:{_fg};font-family:{_lf};white-space:nowrap;">'
                        f'{_h(meta["assigned"])}</span>'
                    )
                badge_row = (
                    '<div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:4px;">'
                    + "".join(badges) + "</div>"
                ) if badges else ""
                parts.append(
                    f'<div class="node node-rect" data-card="{_h(card["label"])}" style="position:absolute;'
                    f'left:{cx}px;top:{ky}px;width:{col_w}px;height:{card_h}px;'
                    f'display:flex;flex-direction:column;justify-content:center;padding:6px 10px;'
                    f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
                    f'border-radius:var(--node-radius,8px);box-sizing:border-box;'
                    f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
                    f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));'
                    f'box-shadow:0 1px 3px rgba(0,0,0,0.07);">'
                    f'<span class="node-label" style="'
                    f'font-size:12px;color:{_fg};font-family:{_lf};'
                    f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
                    f'{_h(card["label"])}</span>{badge_row}</div>'
                )
            else:
                parts.append(
                    f'<div class="node node-rect" data-card="{_h(card["label"])}" style="position:absolute;'
                    f'left:{cx}px;top:{ky}px;width:{col_w}px;height:{card_h}px;'
                    f'display:flex;align-items:center;padding:6px 10px;'
                    f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
                    f'border-radius:var(--node-radius,8px);box-sizing:border-box;'
                    f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
                    f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));'
                    f'box-shadow:0 1px 3px rgba(0,0,0,0.07);">'
                    f'<span class="node-label" style="'
                    f'font-size:12px;color:{_fg};font-family:{_lf};'
                    f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
                    f'{_h(card["label"])}</span></div>'
                )
            ky += card_h + CARD_GAP
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: architecture-beta ─────────────────────────────────────────────────────

_ARCH_SVC_RE = re.compile(
    r'^service\s+(\w+)\s*(?:\(([^)]*)\))?\s*\[([^\]]+)\](?:\s+in\s+(\w+))?', re.I
)
# Group declarations: "group id [(icon)] [Label] [in parent]"
_ARCH_GRP_RE = re.compile(
    r'^group\s+(\w+)\s*(?:\([^)]*\))?\s*(?:\[([^\]]+)\])?(?:\s+in\s+(\w+))?', re.I
)
# Junction declarations: "junction id" — renders as invisible routing point
_ARCH_JCT_RE = re.compile(r'^junction\s+(\w+)', re.I)
# Edge syntax: "src[:side] (<-->|-->|<--|--) [side:]dst [: label]"
# Operator order: <--> before <-- before -- to avoid prefix shadowing.
# Side codes: L(eft) R(ight) T(op) B(ottom)
_ARCH_EDGE_RE = re.compile(
    r'^(\w+)(?::([LRTBrlbt]))?'        # group 1: src_id, group 2: src_side
    r'\s*(<-->|-->|<--|--)\s*'          # group 3: operator
    r'(?:([LRTBrlbt]):)?(\w+)'          # group 4: dst_side, group 5: dst_id
    r'(?::\w+)?'                        # trailing annotation (ignore)
    r'(?:\s*:\s*(.*))?$'                # group 6: edge label
)


def _layout_architecture(src: str, direction: str, width_hint: int) -> str:
    """architecture-beta: zone containers with service nodes and directional edges.

    Supports:
    - ``service id (icon) [Label] [in group]`` — service nodes with icons
    - ``group id [(icon)] [Label] [in parent]`` — dashed group boundaries
    - ``junction id`` — invisible routing-point nodes
    - Indentation-based group membership (services indented under a group block)
    - ``A:R --> L:B``, ``A <--> B`` (bidirectional), ``A <-- B`` (reverse)
    """
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    groups: dict[str, _Group] = {}
    edges: list[_Edge] = []

    # Indentation-based group tracking.
    # Stack of (indent_level, group_id): when a line's indent drops to or
    # below a stack entry's level, that entry's group is no longer active.
    grp_stack: list[tuple[int, str]] = []

    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        indent = len(raw) - len(raw.lstrip())

        # Pop groups whose indent level is no longer the enclosing context.
        while grp_stack and grp_stack[-1][0] >= indent:
            grp_stack.pop()

        m = _ARCH_SVC_RE.match(line)
        if m:
            sid = m.group(1)
            icon_hint = (m.group(2) or "").lower().strip()
            lbl = m.group(3)
            gin = m.group(4)  # explicit "in <group>"

            # Indentation-based membership: if no explicit "in" and we are
            # inside an active group block, assign to the innermost one.
            if not gin and grp_stack:
                gin = grp_stack[-1][1]

            # Icon resolution: explicit map first, then try the hint itself as
            # a file name (pipeline.svg, queue.svg, etc. are present in icons/).
            icon_name = _ARCH_ICON_MAP.get(icon_hint) or icon_hint or ""
            nodes[sid] = _Node(id=sid, label=lbl, shape="rect",
                               group=gin if gin else None, icon=icon_name)
            if gin:
                groups.setdefault(gin, _Group(id=gin, label=gin, members=[]))
                if sid not in groups[gin].members:
                    groups[gin].members.append(sid)
            continue

        m = _ARCH_JCT_RE.match(line)
        if m:
            # Junction = invisible routing point (zero-size dummy node).
            jid = m.group(1)
            nodes[jid] = _Node(id=jid, label="", shape="rect", is_dummy=True)
            continue

        m = _ARCH_GRP_RE.match(line)
        if m:
            gid = m.group(1)
            glbl = m.group(2) or m.group(1)
            gin_grp = m.group(3)  # "in <parent_group>"
            if gid not in groups:
                grp = _Group(id=gid, label=glbl, members=[])
                if gin_grp:
                    grp.parent_group = gin_grp
                groups[gid] = grp
            else:
                groups[gid].label = glbl
                if gin_grp:
                    groups[gid].parent_group = gin_grp
            # Push onto indent stack so indented services below belong to this group.
            grp_stack.append((indent, gid))
            continue

        m = _ARCH_EDGE_RE.match(line)
        if m:
            src_id = m.group(1)
            src_side = (m.group(2) or "").upper() or None
            op = m.group(3)
            dst_side = (m.group(4) or "").upper() or None
            dst_id = m.group(5)
            lbl = (m.group(6) or "").strip()
            if op == "<-->":
                # Bidirectional: emit forward + reverse edges so both ends get arrowheads.
                edges.append(_Edge(src=src_id, dst=dst_id, label=lbl,
                                   style="solid", arrow=True,
                                   src_side=src_side, dst_side=dst_side))
                edges.append(_Edge(src=dst_id, dst=src_id, label="",
                                   style="solid", arrow=True,
                                   src_side=dst_side, dst_side=src_side))
            elif op == "<--":
                # Reverse arrow: swap src/dst so layout flows correctly.
                edges.append(_Edge(src=dst_id, dst=src_id, label=lbl,
                                   style="solid", arrow=True,
                                   src_side=dst_side, dst_side=src_side))
            else:
                # --> (directed) or -- (undirected)
                edges.append(_Edge(src=src_id, dst=dst_id, label=lbl,
                                   style="solid", arrow=(op == "-->"),
                                   src_side=src_side, dst_side=dst_side))

    if not nodes:
        raise ValueError("No services found in architecture-beta.")

    # Architecture diagrams flow left-to-right by convention (services as columns).
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)
    canvas_w, canvas_h = _assign_coordinates(nodes, "LR")
    zoom = 1.0
    if width_hint and canvas_w > 0 and canvas_w > width_hint:
        zoom = width_hint / canvas_w
    return _render_graph_fragment(nodes, edges, groups, canvas_w, canvas_h,
                                  direction="LR", zoom=zoom)


# ── T3: C4 diagrams ──────────────────────────────────────────────────────────

_C4_ELEM_RE = re.compile(
    r'^(Person|System|Container|Component'
    r'|SystemDb|System_Db|SystemQueue|System_Queue'
    r'|ContainerDb|Container_Db|ContainerQueue|Container_Queue'
    r'|ComponentDb|Component_Db|ComponentQueue|Component_Queue'
    r'|Person_Ext|System_Ext|SystemDb_Ext|System_Db_Ext'
    r'|SystemQueue_Ext|System_Queue_Ext'
    r'|Container_Ext|ContainerDb_Ext|Container_Db_Ext'
    r'|ContainerQueue_Ext|Container_Queue_Ext'
    r'|Component_Ext|ComponentDb_Ext|Component_Db_Ext'
    r'|ComponentQueue_Ext|Component_Queue_Ext)\s*'
    r'\(\s*(\w+)\s*,\s*"([^"]+)"'    # alias, label
    r'(?:\s*,\s*"([^"]*)")?'           # arg3: technology or description
    r'(?:\s*,\s*"([^"]*)")?',          # arg4: description (for container/component)
    re.I
)
_C4_BOUNDARY_RE = re.compile(
    r'^(?:Enterprise_Boundary|System_Boundary|Container_Boundary|Boundary)'
    r'\s*\(\s*(\w+)\s*,\s*"([^"]+)"', re.I
)
_C4_REL_RE = re.compile(
    r'^(?:Rel|Rel_D|Rel_U|Rel_L|Rel_R|BiRel)\s*'
    r'\(\s*(\w+)\s*,\s*(\w+)\s*,\s*"([^"]*)"', re.I
)


def _layout_c4(src: str, direction: str, width_hint: int) -> str:
    """C4Context/C4Container/C4Component: ordered shelf packing via C4Bounds."""
    content_lines = _directive_content(src)
    title = ""
    items: list[C4Item] = []
    relationships: list[C4Relationship] = []
    groups: dict[str, C4Boundary] = {}
    boundary_stack: list[str] = []

    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line.lower().startswith("title "):
            title = line[6:].strip()
            continue
        m = _C4_BOUNDARY_RE.match(line)
        if m:
            bid, blbl = m.group(1), m.group(2)
            groups.setdefault(bid, C4Boundary(id=bid, label=blbl))
            boundary_stack.append(bid)
            continue
        if line.startswith((")", "}")) and boundary_stack:
            boundary_stack.pop()
            continue
        m = _C4_ELEM_RE.match(line)
        if m:
            elem_type = m.group(1).lower().replace("-", "_")
            eid, elbl = m.group(2), m.group(3)
            arg3 = m.group(4) or ""
            arg4 = m.group(5) or ""
            is_ext = elem_type.endswith("_ext")
            # Container/Component have signature (alias, label, technology, description).
            # Person/System have signature (alias, label, description).
            _base = re.sub(r"_(ext|db|queue)$", "", elem_type)
            if _base in ("container", "component") and arg4:
                tech, desc = arg3, arg4
            elif _base in ("container", "component"):
                tech, desc = arg3, ""
            else:
                tech, desc = "", arg3
            gin = boundary_stack[-1] if boundary_stack else None
            items.append(C4Item(
                alias=eid,
                kind=elem_type,
                label=elbl,
                description=desc,
                is_external=is_ext,
                technology=tech,
                boundary=gin,
            ))
            if gin:
                groups.setdefault(gin, C4Boundary(id=gin, label=gin))
                if eid not in groups[gin].members:
                    groups[gin].members.append(eid)
            continue
        m = _C4_REL_RE.match(line)
        if m:
            relationships.append(C4Relationship(
                src=m.group(1), dst=m.group(2), label=m.group(3),
            ))

    if not items:
        raise ValueError("No elements found in C4 diagram.")
    return _render_c4_fragment(title, items, relationships, groups, width_hint)


# ── T16: journey ──────────────────────────────────────────────────────────────

def _layout_journey(src: str, direction: str, width_hint: int) -> str:
    """journey: section bands with task score cards."""
    content_lines = _directive_content(src)
    title = ""
    sections: list[dict] = []
    cur_section: dict = {"name": "", "tasks": []}

    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line.lower().startswith("title "):
            title = line[6:].strip()
            continue
        if line.lower().startswith("section "):
            if cur_section["tasks"] or cur_section["name"]:
                sections.append(cur_section)
            cur_section = {"name": line[8:].strip(), "tasks": []}
            continue
        # task: score: Actor1, Actor2
        parts = line.split(":", 2)
        if len(parts) >= 2:
            task_name = parts[0].strip()
            try:
                score = max(1, min(5, int(parts[1].strip())))
            except ValueError:
                score = 3
            actors = parts[2].strip() if len(parts) > 2 else ""
            cur_section["tasks"].append({"name": task_name, "score": score, "actors": actors})

    if cur_section["tasks"] or cur_section["name"]:
        sections.append(cur_section)

    if not sections:
        raise ValueError("No sections or tasks found in journey diagram.")

    PAD = 32
    TITLE_H = 28
    SECTION_LABEL_W = 120
    TASK_W = 140
    TASK_H = 60
    SECTION_PAD_V = 16
    SECTION_H = TASK_H + SECTION_PAD_V * 2

    max_tasks = max((len(s["tasks"]) for s in sections), default=1)
    canvas_w = width_hint or max(500, PAD + SECTION_LABEL_W + max_tasks * (TASK_W + 8) + PAD)
    title_h = TITLE_H + 8 if title else 0
    canvas_h = PAD + title_h + len(sections) * (SECTION_H + 4) + PAD

    # accent palette (one colour per section, cycling)
    _SECTION_COLORS = [
        "#EEF2FF", "#FFF7ED", "#F0FDF4", "#FDF2F8", "#FFFBEB",
        "#EFF6FF", "#FDF4FF", "#F0FDFA",
    ]
    _ACCENT_COLORS = [
        "#4F46E5", "#EA580C", "#16A34A", "#C026D3", "#D97706",
        "#2563EB", "#9333EA", "#0D9488",
    ]

    parts_html: list[str] = []
    parts_html.append(
        f'<div class="diagram mermaid-layout" style="position:relative;width:{canvas_w}px;height:{canvas_h}px;'
        f'font-family:system-ui,sans-serif;overflow:hidden;">'
    )

    if title:
        parts_html.append(
            f'<div style="position:absolute;top:{PAD}px;left:{PAD}px;'
            f'font-size:16px;font-weight:700;color:#1E293B;">{title}</div>'
        )

    y_cursor = PAD + title_h
    for s_idx, sec in enumerate(sections):
        bg = _SECTION_COLORS[s_idx % len(_SECTION_COLORS)]
        accent = _ACCENT_COLORS[s_idx % len(_ACCENT_COLORS)]
        # section band
        parts_html.append(
            f'<div style="position:absolute;top:{y_cursor}px;left:{PAD}px;'
            f'width:{canvas_w - PAD * 2}px;height:{SECTION_H}px;'
            f'background:{bg};border-radius:8px;"></div>'
        )
        # section label
        label_html = (sec["name"] or f"Section {s_idx + 1}").replace("&", "&amp;").replace("<", "&lt;")
        parts_html.append(
            f'<div style="position:absolute;top:{y_cursor + SECTION_PAD_V}px;'
            f'left:{PAD + 8}px;width:{SECTION_LABEL_W - 16}px;height:{TASK_H}px;'
            f'display:flex;align-items:center;font-size:12px;font-weight:600;color:{accent};">'
            f'{label_html}</div>'
        )
        # task cards
        x_task = PAD + SECTION_LABEL_W
        for t in sec["tasks"]:
            score = t["score"]
            score_pct = (score - 1) / 4  # 0..1
            # score bar colour: green for high scores, red for low
            score_color = f"hsl({int(score_pct * 120)},70%,45%)"
            task_html = t["name"].replace("&", "&amp;").replace("<", "&lt;")
            actors_html = t["actors"].replace("&", "&amp;").replace("<", "&lt;")
            parts_html.append(
                f'<div style="position:absolute;top:{y_cursor + SECTION_PAD_V}px;'
                f'left:{x_task}px;width:{TASK_W - 4}px;height:{TASK_H}px;'
                f'background:#fff;border:1.5px solid {accent};border-radius:6px;'
                f'overflow:hidden;">'
                f'<div style="height:4px;background:{score_color};"></div>'
                f'<div style="padding:4px 8px;">'
                f'<div style="font-size:11px;font-weight:600;color:#1E293B;'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{task_html}</div>'
                f'<div style="font-size:10px;color:#64748B;margin-top:2px;">'
                f'Score: {score}/5</div>'
                f'<div style="font-size:10px;color:#94A3B8;white-space:nowrap;'
                f'overflow:hidden;text-overflow:ellipsis;">{actors_html}</div>'
                f'</div></div>'
            )
            x_task += TASK_W + 8
        y_cursor += SECTION_H + 4

    parts_html.append("</div>")
    return "".join(parts_html)


# ── T17: requirementDiagram ───────────────────────────────────────────────────

_REQ_REL_RE = re.compile(
    r'^(\w+)\s*-\s*(satisfies|copies|refines|traces|contains|verifies|derives)\s*->\s*(\w+)',
    re.I,
)

def _layout_requirement(src: str, direction: str, width_hint: int) -> str:
    """requirementDiagram: requirement/element nodes + typed relation edges."""
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []

    cur_block: Optional[dict] = None  # {"id": str, "type": str, "attrs": list[str]}

    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue

        # Block end
        if line == "}":
            if cur_block is not None:
                nid = cur_block["id"]
                # Build label: "id\n|attrs..."
                attr_lines = "\n".join(cur_block["attrs"][:4])  # cap at 4 attrs
                label = nid if not attr_lines else f'{nid}\n|{attr_lines}'
                shape = "cylinder" if cur_block["type"] == "element" else "rect"
                n = _Node(id=nid, label=label, shape=shape)
                n.css_class = f'req-{cur_block["type"]}'
                nodes[nid] = n
            cur_block = None
            continue

        # Block start: requirement/element/functionalRequirement etc.
        _blk_m = re.match(
            r'^(requirement|functionalrequirement|performancerequirement|'
            r'interfacerequirement|physicalrequirement|designconstraint|element)\s+(\w+)\s*\{',
            line, re.I,
        )
        if _blk_m:
            btype = "element" if _blk_m.group(1).lower() == "element" else "requirement"
            cur_block = {"id": _blk_m.group(2), "type": btype, "attrs": []}
            continue

        # Attribute inside block
        if cur_block is not None:
            _attr_m = re.match(r'^(\w+)\s*:\s*(.+)', line)
            if _attr_m:
                cur_block["attrs"].append(f'{_attr_m.group(1)}: {_attr_m.group(2).strip()}')
            continue

        # Relation outside block
        m = _REQ_REL_RE.match(line)
        if m:
            src_id, rel_type, dst_id = m.group(1), m.group(2).lower(), m.group(3)
            edges.append(_Edge(src=src_id, dst=dst_id, label=rel_type, style="solid", arrow=True))
            continue

    if not nodes:
        raise ValueError("No requirements or elements found in requirementDiagram.")

    return _graph_from_content_nodes(nodes, edges, {}, width_hint)


# ── T18: gitGraph ──────────────────────────────────────────────────────────────

def _layout_gitgraph(src: str, direction: str, width_hint: int) -> str:
    """gitGraph: commits as circles on horizontal branch lanes, merges connected."""
    content_lines = _directive_content(src)

    # Parse git commands
    branches: list[str] = ["main"]   # ordered list of known branch names
    branch_order: dict[str, int] = {"main": 0}

    commits: list[dict] = []
    cur_branch = "main"
    _commit_counter = 0

    # map branch name → index of last commit on that branch
    branch_head: dict[str, int] = {}

    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        lc = line.lower()

        if lc.startswith("commit"):
            _id = f"c{_commit_counter}"
            _commit_counter += 1
            _msg_m = re.search(r'id:\s*"([^"]*)"', line, re.I)
            _msg = _msg_m.group(1) if _msg_m else ""
            _tag_m = re.search(r'tag:\s*"([^"]*)"', line, re.I)
            _tag = _tag_m.group(1) if _tag_m else ""
            _type = "NORMAL"
            for _t in ("HIGHLIGHT", "REVERSE", "MERGE"):
                if _t in line.upper():
                    _type = _t; break
            parent = branch_head.get(cur_branch)
            c = {
                "id": _id, "branch": cur_branch, "msg": _msg, "tag": _tag,
                "type": _type, "parent": parent, "merge_from": None,
            }
            commits.append(c)
            branch_head[cur_branch] = len(commits) - 1
            continue

        _br_m = re.match(r'branch\s+(\S+)', line, re.I)
        if _br_m:
            bname = _br_m.group(1)
            if bname not in branch_order:
                branch_order[bname] = len(branches)
                branches.append(bname)
            continue

        if lc.startswith("checkout "):
            bname = line[9:].strip()
            if bname not in branch_order:
                branch_order[bname] = len(branches)
                branches.append(bname)
            cur_branch = bname
            continue

        _merge_m = re.match(r'merge\s+(\S+)', line, re.I)
        if _merge_m:
            src_branch = _merge_m.group(1)
            _id = f"c{_commit_counter}"
            _commit_counter += 1
            _tag_m = re.search(r'tag:\s*"([^"]*)"', line, re.I)
            _tag = _tag_m.group(1) if _tag_m else ""
            parent = branch_head.get(cur_branch)
            merge_from = branch_head.get(src_branch)
            c = {
                "id": _id, "branch": cur_branch, "msg": "merge", "tag": _tag,
                "type": "MERGE", "parent": parent, "merge_from": merge_from,
            }
            commits.append(c)
            branch_head[cur_branch] = len(commits) - 1
            branch_head[src_branch] = len(commits) - 1
            continue

    if not commits:
        raise ValueError("No commits found in gitGraph.")

    # ── Geometry ───────────────────────────────────────────────────────────────
    PAD = 32
    LANE_H = 56
    COMMIT_R = 10
    COMMIT_STEP = 60
    LABEL_W = 80

    n_lanes = len(branches)
    canvas_h = PAD + n_lanes * LANE_H + PAD
    n_commits_per_branch = {b: sum(1 for c in commits if c["branch"] == b) for b in branches}
    max_commits = max(n_commits_per_branch.values(), default=1)
    canvas_w = width_hint or max(400, PAD + LABEL_W + max_commits * COMMIT_STEP + PAD)

    # Assign x positions: sequential across the full timeline
    for i, c in enumerate(commits):
        c["_x"] = PAD + LABEL_W + i * COMMIT_STEP + COMMIT_STEP // 2
        c["_y"] = PAD + branch_order.get(c["branch"], 0) * LANE_H + LANE_H // 2

    _BRANCH_COLORS = [
        "#4F46E5", "#16A34A", "#EA580C", "#C026D3", "#D97706",
        "#2563EB", "#9333EA", "#0D9488", "#DC2626",
    ]

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="position:relative;width:{canvas_w}px;height:{canvas_h}px;'
        f'font-family:system-ui,sans-serif;overflow:hidden;">'
    )

    # SVG overlay for lines
    svg_lines: list[str] = []

    # Branch lane lines
    for b_idx, bname in enumerate(branches):
        _cy = PAD + b_idx * LANE_H + LANE_H // 2
        color = _BRANCH_COLORS[b_idx % len(_BRANCH_COLORS)]
        svg_lines.append(
            f'<line x1="{PAD + LABEL_W}" y1="{_cy}" x2="{canvas_w - PAD}" y2="{_cy}" '
            f'stroke="{color}" stroke-width="2" stroke-dasharray="4 2" opacity="0.4"/>'
        )

    # Commit-to-commit edges
    for c in commits:
        if c["parent"] is not None:
            p = commits[c["parent"]]
            color = _BRANCH_COLORS[branch_order.get(c["branch"], 0) % len(_BRANCH_COLORS)]
            svg_lines.append(
                f'<path d="M{p["_x"]},{p["_y"]} C{(p["_x"]+c["_x"])//2},{p["_y"]} '
                f'{(p["_x"]+c["_x"])//2},{c["_y"]} {c["_x"]},{c["_y"]}" '
                f'fill="none" stroke="{color}" stroke-width="2"/>'
            )
        if c["merge_from"] is not None:
            mf = commits[c["merge_from"]]
            color = _BRANCH_COLORS[branch_order.get(mf["branch"], 0) % len(_BRANCH_COLORS)]
            svg_lines.append(
                f'<path d="M{mf["_x"]},{mf["_y"]} C{(mf["_x"]+c["_x"])//2},{mf["_y"]} '
                f'{(mf["_x"]+c["_x"])//2},{c["_y"]} {c["_x"]},{c["_y"]}" '
                f'fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="4 2"/>'
            )

    svg_markup = (
        f'<svg style="position:absolute;top:0;left:0;pointer-events:none;" '
        f'width="{canvas_w}" height="{canvas_h}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(svg_lines) + "</svg>"
    )
    parts.append(svg_markup)

    # Branch labels
    for b_idx, bname in enumerate(branches):
        _cy = PAD + b_idx * LANE_H + LANE_H // 2
        color = _BRANCH_COLORS[b_idx % len(_BRANCH_COLORS)]
        bname_html = bname.replace("&", "&amp;").replace("<", "&lt;")
        parts.append(
            f'<div style="position:absolute;top:{_cy - 10}px;left:{PAD}px;'
            f'width:{LABEL_W - 8}px;font-size:11px;font-weight:600;color:{color};'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{bname_html}</div>'
        )

    # Commit circles
    for c in commits:
        cx, cy = c["_x"], c["_y"]
        color = _BRANCH_COLORS[branch_order.get(c["branch"], 0) % len(_BRANCH_COLORS)]
        fill = "#fff"
        if c["type"] == "HIGHLIGHT":
            fill = color
        elif c["type"] == "REVERSE":
            fill = "#6B7280"
        parts.append(
            f'<div data-node-id="{c["id"]}" style="position:absolute;'
            f'top:{cy - COMMIT_R}px;left:{cx - COMMIT_R}px;'
            f'width:{COMMIT_R * 2}px;height:{COMMIT_R * 2}px;'
            f'border-radius:50%;background:{fill};border:2.5px solid {color};'
            f'box-sizing:border-box;"></div>'
        )
        if c["msg"] or c["tag"]:
            label = c["tag"] or c["msg"]
            label_html = label[:12].replace("&", "&amp;").replace("<", "&lt;")
            parts.append(
                f'<div style="position:absolute;top:{cy - COMMIT_R - 16}px;'
                f'left:{cx - 24}px;width:48px;font-size:9px;text-align:center;'
                f'color:{color};font-weight:600;">{label_html}</div>'
            )

    parts.append("</div>")
    return "".join(parts)


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
        html, _ = _layout_lifeline(clean, direction, width_hint)
        return html
    if d == "erdiagram":
        return _layout_er(clean, direction, width_hint)
    if d == "classdiagram":
        return _layout_class(clean, direction, width_hint)
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
        return _layout_architecture(clean, direction, width_hint)
    if d in ("c4context", "c4container", "c4component"):
        return _layout_c4(clean, direction, width_hint)
    if d == "journey":
        return _layout_journey(clean, direction, width_hint)
    if d == "requirementdiagram":
        return _layout_requirement(clean, direction, width_hint)
    if d == "gitgraph":
        return _layout_gitgraph(clean, direction, width_hint)

    if d in ("sankey-beta", "zenuml"):
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


def _dispatch_validate(src: str) -> "ValidationResult":
    """Validate Mermaid source. Geometry checking is unvalidated until T9."""
    from ._geometry import ValidationResult
    clean = _strip_frontmatter(src)
    directive, _ = _detect_directive(clean)
    if directive.lower() == "sequencediagram":
        try:
            _, geom = _layout_lifeline(clean, "LR", 900)
        except Exception as exc:
            return ValidationResult(
                render="fail",
                syntax_coverage="fail",
                geometry="unvalidated",
                errors=(str(exc),),
            )
        diagnostics = geom.diagnostics
        sc = "partial" if diagnostics else "pass"
        return ValidationResult(
            diagnostics=diagnostics,
            syntax_coverage=sc,
            geometry="unvalidated",
        )
    return ValidationResult(geometry="unvalidated")


# ── CLI ───────────────────────────────────────────────────────────────────────
