from __future__ import annotations

import math
import re
from html import escape as _h
from typing import Optional

from ._constants import (
    _Node, _Edge, _Group,
    NODE_CAP, EDGE_CAP, GROUP_CAP,
    NODE_W, NODE_H, COL_GAP, RANK_GAP, CANVAS_PAD,
    GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT,
    _ARCH_ICON_MAP, _C4_ICON_MAP, _LABEL_ICON_KEYWORDS,
    _KNOWN_DIRECTIVES, _GRAPH_DIRECTIVES,
    _node_render_h,
    _TERMINAL_NODE_SIZE, _is_terminal_circle,
)
from ._parser import _parse_graph_source, _detect_directive, _strip_frontmatter
from ._layout import _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates, _compact_group_columns, _group_coherent_cols
from ._routing import _route_edges, _arrowhead
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
) -> str:
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
    _minimize_crossings(nodes, edges)

    # Auto-select direction (TB vs LR) when a size constraint is given and the
    # source direction was not explicitly overridden by the caller.  Estimate the
    # canvas footprint for both orientations and choose the one that requires
    # less shrinkage (i.e. fits best inside width_hint × height_hint).
    if width_hint and height_hint:
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

    # Keep group members in adjacent column bands (reduces group bbox y-span in LR mode)
    if groups:
        _group_coherent_cols(nodes, groups)
    # Compact group column ranges before coordinate assignment (dagre-inspired)
    if groups:
        _compact_group_columns(nodes, groups)
    canvas_w, canvas_h = _assign_coordinates(nodes, direction)

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
        canvas_w = max(n.x + NODE_W for n in real_nodes) + CANVAS_PAD

    # Center terminal-circle nodes (start ● / end ◎) within their TB column slot.
    # _assign_coordinates places every node at the column's left edge (n.x = CANVAS_PAD +
    # col * (NODE_W + COL_GAP)).  Rect nodes fill the full NODE_W so their visual centre is
    # n.x + NODE_W // 2.  Terminal circles are _TERMINAL_NODE_SIZE (32 px) wide; without this
    # adjustment their centre is n.x + 16, producing a visible horizontal jog in arrows that
    # connect them to adjacent rect states.  Shifting right by (NODE_W - _TERMINAL_NODE_SIZE) // 2
    # aligns their centres.  Canvas dimensions are already finalised above, so this shift does
    # not affect zoom or canvas sizing.
    if direction.upper() not in ("LR", "RL"):
        _circ_shift = (NODE_W - _TERMINAL_NODE_SIZE) // 2
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
    legend_html = _render_legend(edges, groups)

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
    r'^(\S+?)\s*(-->>|->>|-->|->|--x|-x|--\)|-\))\s*(\S+)\s*:\s*(.*)$'
)
_SEQ_BLOCK_RE = re.compile(r'^(alt|loop|opt|par|critical|break|rect)\s*(.*)', re.I)
_SEQ_END_RE = re.compile(r'^end\s*$', re.I)
_SEQ_ACTIVATE_RE = re.compile(r'^(activate|deactivate)\s+(\S+)', re.I)
_SEQ_NOTE_RE = re.compile(r'^[Nn]ote\s+(?:over|left\s+of|right\s+of)\s+([^:]+):\s*(.+)', re.I)
_SEQ_ELSE_RE = re.compile(r'^(else|and)\s*(.*)', re.I)


def _layout_lifeline(src: str, direction: str, width_hint: int) -> str:
    """sequenceDiagram: participants as columns, messages as horizontal arrows."""
    content_lines = _directive_content(src)
    participants: list[str] = []
    p_label: dict[str, str] = {}

    def _ensure_p(name: str) -> None:
        n = name.strip()
        if n and n not in participants:
            participants.append(n)
            p_label.setdefault(n, n)

    items: list[dict] = []
    block_depth = 0
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
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
            items.append({"type": act_type, "pid": m.group(2).strip()})
            continue
        m = _SEQ_NOTE_RE.match(line)
        if m:
            items.append({"type": "note", "pid": m.group(1).strip().split(",")[0].strip(),
                          "text": m.group(2).strip()})
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
                          "label": lbl.strip(), "dotted": arrow.startswith("--")})
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
            items.append({"type": "block", "kw": m.group(1), "label": m.group(2).strip()})
            block_depth += 1
            continue
        if _SEQ_END_RE.match(line) and block_depth > 0:
            block_depth -= 1
            items.append({"type": "block_end"})

    if not participants:
        raise ValueError("No participants found in sequenceDiagram.")

    # Pre-compute span (row count) for each block so alt/loop/par boxes cover
    # their full height rather than collapsing to a single-row band.
    _bstack: list[int] = []
    _row_types = {"msg", "block", "note", "else"}
    for _bi, _bit in enumerate(items):
        if _bit["type"] == "block":
            _bstack.append(_bi)
        elif _bit["type"] == "block_end" and _bstack:
            _si = _bstack.pop()
            items[_si]["span"] = sum(
                1 for _ji in range(_si, _bi) if items[_ji]["type"] in _row_types
            )
    for _bit in items:
        if _bit["type"] == "block":
            _bit.setdefault("span", 1)

    COL_W, COL_GAP, PAD_H, PAD_V = 160, 24, 40, 24
    HDR_H, ROW_H = 48, 40
    col_pitch = COL_W + COL_GAP
    n_parts = len(participants)
    canvas_w = PAD_H * 2 + n_parts * col_pitch - COL_GAP
    if width_hint and canvas_w > 0 and abs(width_hint / canvas_w - 1.0) > 0.05:
        col_pitch = int(col_pitch * width_hint / canvas_w)
        canvas_w = width_hint
    col_w = min(COL_W, max(40, col_pitch - 8))  # header scales with pitch; min 8px gap
    n_rows = sum(1 for it in items if it["type"] in ("msg", "block", "note", "else"))
    canvas_h = PAD_V * 2 + HDR_H * 2 + n_rows * ROW_H + 32  # extra HDR_H for bottom boxes

    # Pre-compute activation spans: [(pid, start_row, end_row)]
    _act_stacks: dict[str, list[int]] = {}
    _act_spans: list[tuple[str, int, int]] = []
    _row_pre = 0
    for it in items:
        if it["type"] in ("msg", "block", "note", "else"):
            _row_pre += 1
        elif it["type"] == "activate":
            _act_stacks.setdefault(it["pid"], []).append(_row_pre)
        elif it["type"] == "deactivate":
            pid = it["pid"]
            if pid in _act_stacks and _act_stacks[pid]:
                _act_spans.append((pid, _act_stacks[pid].pop(), _row_pre))
    ll_top = PAD_V + HDR_H
    ll_bot = canvas_h - PAD_V

    def _cx(pid: str) -> int:
        idx = participants.index(pid) if pid in participants else 0
        return PAD_H + idx * col_pitch + col_pitch // 2

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
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
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'
        f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));'
    )
    for i, pid in enumerate(participants):
        lx = PAD_H + i * col_pitch + (col_pitch - col_w) // 2  # centered in pitch slot
        lbl = _h(p_label.get(pid, pid))
        # Top participant box
        parts.append(
            f'<div class="node node-rect" data-node-id="{_h(pid)}" style="'
            f'position:absolute;left:{lx}px;top:{PAD_V}px;'
            f'width:{col_w}px;height:{HDR_H - 8}px;{_seq_box_css}">'
            f'<span class="node-label" style="{_seq_label_css}">{lbl}</span></div>'
        )
        # Bottom participant box (same label, anchored to lifeline bottom)
        parts.append(
            f'<div class="node node-rect" data-node-id="{_h(pid)}-bottom" style="'
            f'position:absolute;left:{lx}px;top:{ll_bot}px;'
            f'width:{col_w}px;height:{HDR_H - 8}px;{_seq_box_css}">'
            f'<span class="node-label" style="{_seq_label_css}">{lbl}</span></div>'
        )
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    _seq_edge = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"
    for pid in participants:
        lx = _cx(pid)
        parts.append(
            f'<line x1="{lx}" y1="{ll_top}" x2="{lx}" y2="{ll_bot}" '
            f'stroke="{_seq_edge}" stroke-width="1" stroke-dasharray="5 4"/>'
        )
    # Activation boxes (rendered below lifelines, above messages)
    for pid, start_row, end_row in _act_spans:
        ax = _cx(pid) - 4
        ay = ll_top + start_row * ROW_H
        act_h = max(ROW_H, (end_row - start_row) * ROW_H)
        parts.append(
            f'<rect x="{ax}" y="{ay}" width="8" height="{act_h}" '
            f'fill="var(--edge-strong,var(--accent-1,#60a5fa))" opacity="0.35" rx="2"/>'
        )
    row = 0
    for it in items:
        if it["type"] == "block":
            ry = ll_top + row * ROW_H
            bh = it.get("span", 1) * ROW_H
            parts.append(
                f'<rect x="{PAD_H // 2}" y="{ry}" width="{canvas_w - PAD_H}" height="{bh}" '
                f'fill="var(--node-bg-from,var(--card-bg-from,#ffffff))" opacity="0.6" '
                f'stroke="{_seq_edge}" stroke-width="1" rx="3"/>'
            )
            row += 1; continue
        if it["type"] == "else":
            ry = ll_top + row * ROW_H
            parts.append(
                f'<line x1="{PAD_H // 2}" y1="{ry}" x2="{canvas_w - PAD_H // 2}" y2="{ry}" '
                f'stroke="{_seq_edge}" stroke-width="1" stroke-dasharray="4 4"/>'
            )
            row += 1; continue
        if it["type"] == "note":
            pid = it["pid"]
            note_x = _cx(pid) - col_w // 2
            note_y = ll_top + row * ROW_H + 4
            note_w, note_h = col_w, ROW_H - 8
            fold = 10
            pts = (f"{note_x},{note_y} "
                   f"{note_x + note_w - fold},{note_y} "
                   f"{note_x + note_w},{note_y + fold} "
                   f"{note_x + note_w},{note_y + note_h} "
                   f"{note_x},{note_y + note_h}")
            parts.append(
                f'<polygon points="{pts}" '
                f'fill="var(--node-bg-from,var(--card-bg-from,#ffffff))" '
                f'stroke="{_seq_edge}" stroke-width="1"/>'
            )
            row += 1; continue
        if it["type"] in ("activate", "deactivate"):
            continue
        if it["type"] != "msg":
            continue
        sx, dx2 = _cx(it["src"]), _cx(it["dst"])
        ry = ll_top + row * ROW_H + ROW_H // 2
        dash = ' stroke-dasharray="6 4"' if it["dotted"] else ""
        if sx == dx2:
            parts.append(
                f'<path d="M {sx} {ry - 8} C {sx + 36} {ry - 8} {sx + 36} {ry + 8} {sx} {ry + 8}" '
                f'stroke="{_seq_edge}" fill="none" stroke-width="1.5"{dash}'
                f' data-src="{_h(it["src"])}" data-dst="{_h(it["dst"])}"/>'
            )
            ah = _arrowhead(sx, ry + 8, -1, 0, back=10, half_w=6)
        else:
            parts.append(
                f'<line x1="{sx}" y1="{ry}" x2="{dx2}" y2="{ry}" '
                f'stroke="{_seq_edge}" stroke-width="1.5"{dash}'
                f' data-src="{_h(it["src"])}" data-dst="{_h(it["dst"])}"/>'
            )
            ah = _arrowhead(dx2, ry, 1 if dx2 > sx else -1, 0, back=10, half_w=6)
        parts.append(f'<polygon points="{ah}" fill="{_seq_edge}"/>')
        row += 1
    parts.append('</svg>')
    row = 0
    for it in items:
        if it["type"] == "block":
            ry = ll_top + row * ROW_H
            parts.append(
                f'<span style="position:absolute;left:{PAD_H + 4}px;top:{ry + 3}px;'
                f'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;'
                f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
                f'{_h(it["kw"])}{" " + _h(it["label"]) if it["label"] else ""}</span>'
            )
            row += 1; continue
        if it["type"] == "else":
            ry = ll_top + row * ROW_H
            if it["label"]:
                parts.append(
                    f'<span style="position:absolute;left:{PAD_H + 4}px;top:{ry + 3}px;'
                    f'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;'
                    f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                    f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
                    f'{_h(it.get("kw", "else"))} {_h(it["label"])}</span>'
                )
            row += 1; continue
        if it["type"] == "note":
            pid = it["pid"]
            note_x = _cx(pid) - col_w // 2
            note_y = ll_top + row * ROW_H + 4
            note_w = col_w
            parts.append(
                f'<span style="position:absolute;left:{note_x}px;top:{note_y + 4}px;'
                f'width:{note_w}px;font-size:10px;text-align:center;overflow:hidden;'
                f'color:var(--node-fg,var(--text-primary,#191A17));'
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
                f'{_h(it["text"])}</span>'
            )
            row += 1; continue
        if it["type"] not in ("msg",):
            continue
        sx, dx2 = _cx(it["src"]), _cx(it["dst"])
        ry = ll_top + row * ROW_H + ROW_H // 2
        lbl = _h(it["label"])
        if lbl:
            mid_x = (sx + dx2) // 2
            parts.append(
                f'<span class="edge-label" '
                f'data-src="{_h(it["src"])}" data-dst="{_h(it["dst"])}" data-edge-label="{lbl}" '
                f'style="position:absolute;'
                f'left:{mid_x - 30}px;top:{ry - 18}px;'
                f'font-size:11px;color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));'
                f'background:var(--node-bg-from,var(--card-bg-from,#ffffff));'
                f'padding:0 3px;white-space:nowrap;">{lbl}</span>'
            )
        row += 1
    parts.append('</div>')
    return "\n".join(parts)


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
_ER_CARD_SRC_MAP = {"||": "one", "o|": "zero-one", "}|": "many", "}o": "zero-many"}
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
            lbl = m.group("lbl").strip()
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
    r'^(\w+)\s*(?:"[^"]*"\s*)?'
    r'(<\|--|<\|\.\.|\.\.>\||\.\.\|>|\|>|\*--|--\*|o--|--o|-->|\.\.>|\.\.|\|\|)'
    r'\s*(?:"[^"]*"\s*)?(\w+)(?:\s*:\s*(.*))?$'
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
            c1, op, c2, lbl = m.group(1), m.group(2), m.group(3), (m.group(4) or "")
            for cid in (c1, c2):
                nodes.setdefault(cid, _Node(id=cid, label=cid, shape="rect"))
                _class_members.setdefault(cid, [])
            edges.append(_Edge(src=c1, dst=c2, label=lbl.strip(),
                               style=_class_rel_style(op), arrow=True))
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

    # Date axis (top) -- tick labels and small indicator marks
    _tick_count = min(6, total_days)
    _tick_days = max(1, total_days // _tick_count)
    parts.append(
        f'<div style="position:absolute;left:{bar_x}px;top:{y}px;'
        f'width:{bar_w_total}px;height:{AXIS_H}px;overflow:hidden;">'
    )
    _tick_xs: list[int] = []
    for _ti in range(_tick_count + 1):
        _td_off = _ti * _tick_days
        if _td_off > total_days:
            break
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
    r_in = r_out * 2 // 5  # donut hole

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
        # Quadratic bezier with control point nudged radially outward from centre
        mx = (px_p + px_c) / 2
        my = (py_p + py_c) / 2
        dx, dy = mx - cx, my - cy
        dl = math.hypot(dx, dy) or 1.0
        qx = mx + dx / dl * 18
        qy = my + dy / dl * 18
        svg_parts.append(
            f'<path d="M{px_p:.1f},{py_p:.1f} Q{qx:.1f},{qy:.1f} {px_c:.1f},{py_c:.1f}" '
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

def _layout_kanban(src: str, direction: str, width_hint: int) -> str:
    """kanban: cards stacked in labeled vertical columns."""
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
            col_name = re.sub(r'@\{[^}]*\}', '', line).strip()
            current_col = {"name": col_name, "cards": []}
            columns.append(current_col)
        elif current_col is not None:
            card = re.sub(r'@\{[^}]*\}', '', line).strip()
            m_lbl = re.match(r'^\w+\["([^"]+)"\]', card)
            if m_lbl:
                card = m_lbl.group(1)
            if card:
                current_col["cards"].append(card)
    if not columns:
        raise ValueError("No columns found in kanban.")

    PAD_H, PAD_V = 24, 24
    COL_W, COL_GAP, HDR_H, CARD_H, CARD_GAP = 160, 12, 36, 44, 6
    max_cards = max((len(c["cards"]) for c in columns), default=0)
    canvas_w = width_hint or PAD_H * 2 + len(columns) * (COL_W + COL_GAP) - COL_GAP
    canvas_h = PAD_V * 2 + HDR_H + max_cards * (CARD_H + CARD_GAP)

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    for ci, col in enumerate(columns):
        cx = PAD_H + ci * (COL_W + COL_GAP)
        parts.append(
            f'<div data-col="{_h(col["name"])}" style="position:absolute;left:{cx}px;top:{PAD_V}px;'
            f'width:{COL_W}px;height:{HDR_H}px;'
            f'display:flex;align-items:center;justify-content:center;'
            f'border-bottom:2px solid var(--edge-strong,var(--accent-1,#60a5fa));'
            f'box-sizing:border-box;">'
            f'<span style="font-size:12px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.08em;color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
            f'{_h(col["name"])}</span></div>'
        )
        for ki, card in enumerate(col["cards"]):
            ky = PAD_V + HDR_H + ki * (CARD_H + CARD_GAP) + 8
            parts.append(
                f'<div class="node node-rect" data-card="{_h(card)}" style="position:absolute;'
                f'left:{cx}px;top:{ky}px;width:{COL_W}px;height:{CARD_H}px;'
                f'display:flex;align-items:center;padding:6px 10px;'
                f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
                f'border-radius:var(--node-radius,8px);box-sizing:border-box;'
                f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
                f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));"><span class="node-label" style="'
                f'font-size:12px;color:var(--node-fg,var(--text-primary,#191A17));'
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));overflow:hidden;'
                f'text-overflow:ellipsis;white-space:nowrap;">'
                f'{_h(card)}</span></div>'
            )
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
_ARCH_EDGE_RE = re.compile(
    r'^(\w+)(?::\w+)?\s*(<-->|-->|<--|--)\s*(?:\w+:)?(\w+)(?::\w+)?'
    r'(?:\s*:\s*(.*))?$'
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
            op = m.group(2)
            dst_id = m.group(3)
            lbl = (m.group(4) or "").strip()
            if op == "<-->":
                # Bidirectional: emit forward + reverse edges so both ends get arrowheads.
                edges.append(_Edge(src=src_id, dst=dst_id, label=lbl,
                                   style="solid", arrow=True))
                edges.append(_Edge(src=dst_id, dst=src_id, label="",
                                   style="solid", arrow=True))
            elif op == "<--":
                # Reverse arrow: swap src/dst so layout flows correctly.
                edges.append(_Edge(src=dst_id, dst=src_id, label=lbl,
                                   style="solid", arrow=True))
            else:
                # --> (directed) or -- (undirected)
                edges.append(_Edge(src=src_id, dst=dst_id, label=lbl,
                                   style="solid", arrow=(op == "-->")))

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
    r'^(Person|System|Container|Component|SystemDb|ContainerDb|'
    r'Person_Ext|System_Ext|Container_Ext)\s*'
    r'\(\s*(\w+)\s*,\s*"([^"]+)"', re.I
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
    """C4Context/C4Container/C4Component: boundary boxes + nodes + relationships."""
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    groups: dict[str, _Group] = {}
    edges: list[_Edge] = []
    boundary_stack: list[str] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m = _C4_BOUNDARY_RE.match(line)
        if m:
            bid, blbl = m.group(1), m.group(2)
            groups.setdefault(bid, _Group(id=bid, label=blbl, members=[]))
            boundary_stack.append(bid); continue
        if line.startswith(")") and boundary_stack:
            boundary_stack.pop(); continue
        m = _C4_ELEM_RE.match(line)
        if m:
            elem_type = m.group(1).lower()
            eid, elbl = m.group(2), m.group(3)
            shape = "circle" if "person" in elem_type else "rect"
            icon_name = _C4_ICON_MAP.get(elem_type, "node")
            css_class = "external" if elem_type.endswith("_ext") else ""
            gin = boundary_stack[-1] if boundary_stack else None
            nodes[eid] = _Node(id=eid, label=elbl, shape=shape,
                               group=gin, icon=icon_name, css_class=css_class)
            if gin:
                groups.setdefault(gin, _Group(id=gin, label=gin, members=[]))
                if eid not in groups[gin].members:
                    groups[gin].members.append(eid)
            continue
        m = _C4_REL_RE.match(line)
        if m:
            edges.append(_Edge(src=m.group(1), dst=m.group(2),
                               label=m.group(3), style="solid", arrow=True))
    if not nodes:
        raise ValueError("No elements found in C4 diagram.")
    return _graph_from_content_nodes(nodes, edges, groups, width_hint)


# ── strategy dispatch ─────────────────────────────────────────────────────────

def _dispatch(
    src: str,
    direction_override: Optional[str],
    width_hint: int,
    height_hint: int = 0,
    style_overrides: str = "",
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
        )
    if d == "sequencediagram":
        return _layout_lifeline(clean, direction, width_hint)
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

    if d in ("gitgraph", "journey", "requirementdiagram"):
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


# ── CLI ───────────────────────────────────────────────────────────────────────
