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

_ER_REL_RE = re.compile(
    r'^(?P<e1>\w+)\s+'
    r'(?P<card_src>[|o}{]{1,2})'
    r'(?P<line>-{1,2}|\.{1,2})'
    r'(?P<card_dst>[|o}{]{1,2})'
    r'\s+(?P<e2>\w+)\s*:\s*(?P<lbl>.*)$'
)
_ER_CARD_SRC_MAP = {"||": "one", "o|": "zero-one", "}|": "many", "}o": "zero-many"}
_ER_CARD_DST_MAP = {"||": "one", "|o": "zero-one", "|{": "many", "o{": "zero-many"}


def _render_crow_foot(x: float, y: float, dx: float, dy: float, kind: str, color: str) -> list[str]:
    """Return SVG strings for a crow's foot marker at (x, y) with edge direction (dx, dy)."""
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
    """erDiagram: entities as nodes, relationships as edges (graph topology reuse)."""
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    current_entity: Optional[str] = None
    _entity_attrs: dict[str, list[str]] = {}  # eid → attribute lines
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line == "}":
            current_entity = None; continue
        m = re.match(r'^(\w+)\s*\{', line)
        if m:
            eid = m.group(1)
            nodes.setdefault(eid, _Node(id=eid, label=eid, shape="rect"))
            _entity_attrs.setdefault(eid, [])
            current_entity = eid; continue
        if current_entity:
            _entity_attrs.setdefault(current_entity, []).append(line)
            continue
        m = _ER_REL_RE.match(line)
        if m:
            e1 = m.group("e1")
            card_src_tok = m.group("card_src")
            card_dst_tok = m.group("card_dst")
            e2 = m.group("e2")
            lbl = m.group("lbl").strip()
            for eid in (e1, e2):
                nodes.setdefault(eid, _Node(id=eid, label=eid, shape="rect"))
            er_style = "dotted" if m.group("line").startswith(".") else "solid"
            edges.append(_Edge(
                src=e1, dst=e2, label=lbl, style=er_style, arrow=True,
                cardinality_src=_ER_CARD_SRC_MAP.get(card_src_tok),
                cardinality_dst=_ER_CARD_DST_MAP.get(card_dst_tok),
            ))
    if not nodes:
        raise ValueError("No entities found in erDiagram.")

    # Encode entity attributes into label pipe-separated tech section
    for eid, attrs in _entity_attrs.items():
        if eid in nodes and attrs:
            nodes[eid].label = f"{eid}|" + "\n".join(attrs)

    # Layout
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)
    canvas_w, canvas_h = _assign_coordinates(nodes)
    if width_hint and canvas_w > 0 and abs(width_hint / canvas_w - 1.0) > 0.05:
        scale = width_hint / canvas_w
        for n in nodes.values():
            n.x = int(n.x * scale)
        canvas_w = width_hint

    html = _render_graph_fragment(nodes, edges, {}, canvas_w, canvas_h)

    # Inject crow's foot markers into the overlay SVG
    _er_color = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"
    crow_parts: list[str] = []
    for e in edges:
        if not e.cardinality_src and not e.cardinality_dst:
            continue
        if e.src not in nodes or e.dst not in nodes:
            continue
        s = nodes[e.src]
        d_node = nodes[e.dst]
        sx = float(s.x + NODE_W // 2)
        sy = float(s.y + _node_render_h(s))
        dx2 = float(d_node.x + NODE_W // 2)
        dy2 = float(d_node.y)
        if e.cardinality_src:
            crow_parts.extend(_render_crow_foot(sx, sy, 0.0, 1.0, e.cardinality_src, _er_color))
        if e.cardinality_dst:
            crow_parts.extend(_render_crow_foot(dx2, dy2, 0.0, -1.0, e.cardinality_dst, _er_color))

    if crow_parts:
        # Inject crow's foot SVG elements into the first </svg> (the overlay)
        html = html.replace("</svg>", "\n".join(crow_parts) + "\n</svg>", 1)

    return html


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
    """gantt: sections as swim-lanes, tasks as horizontal bars."""
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
                    task_start_str = _pl
                elif re.match(r'^\d+[dwm]$', _pl):
                    task_dur_str = _p
                elif re.match(r'^[a-z_]\w*$', _pl) and not task_id:
                    task_id = _pl
            sections[-1]["tasks"].append({
                "name": name.strip(),
                "crit": "crit" in task_flags, "done": "done" in task_flags,
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
            ref_id = ss[6:].strip()
            t_start = id_end_date.get(ref_id) or _date(2024, 1, 1)
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

    # Date axis (top)
    _tick_count = min(6, total_days)
    _tick_days = max(1, total_days // _tick_count)
    parts.append(
        f'<div style="position:absolute;left:{bar_x}px;top:{y}px;'
        f'width:{bar_w_total}px;height:{AXIS_H}px;overflow:hidden;">'
    )
    for _ti in range(_tick_count + 1):
        _td_off = _ti * _tick_days
        if _td_off > total_days:
            break
        _tx = int(_td_off / total_days * bar_w_total)
        _tick_d = earliest + _td(days=_td_off)
        _label = f"{_tick_d.month}/{_tick_d.day}"
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
            bar_color = (
                "var(--accent-4,rgba(31,58,95,0.7))" if task["crit"]
                else "var(--node-border,rgba(100,116,139,0.25))" if task["done"]
                else "rgba(53,148,103,0.25)"
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
            parts.append(
                f'<div data-task-id="{_h(_task_id_val)}" style="position:absolute;left:{bx}px;top:{y + 1}px;'
                f'width:{bw}px;height:{BAR_H - 2}px;background:{bar_color};'
                f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
                f'border-radius:3px;box-sizing:border-box;"></div>'
            )
            y += BAR_H + ROW_GAP
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: timeline ──────────────────────────────────────────────────────────────

def _layout_timeline(src: str, direction: str, width_hint: int) -> str:
    """timeline: periods/events as nodes on a horizontal axis."""
    content_lines = _directive_content(src)
    title = ""
    sections: list[dict] = []
    current: Optional[dict] = None
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line.lower().startswith("title "):
            title = line[6:].strip(); continue
        if line.lower().startswith("section "):
            continue
        if ' : ' in line:
            period_name, first_event = line.split(' : ', 1)
            current = {"period": period_name.strip(), "events": [first_event.strip()]}
        else:
            current = {"period": line, "events": []}
        sections.append(current)
    if not sections:
        raise ValueError("No periods found in timeline.")

    PAD_H, PAD_V = 40, 32
    ITEM_W, ITEM_H, ITEM_GAP = 140, 64, 12
    canvas_w = width_hint or max(400, PAD_H * 2 + len(sections) * (ITEM_W + ITEM_GAP) - ITEM_GAP)
    step = (canvas_w - PAD_H * 2) // max(len(sections), 1)
    axis_y = PAD_V + (28 if title else 0) + ITEM_H + 12
    canvas_h = axis_y + PAD_V + 8

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    if title:
        parts.append(
            f'<div style="position:absolute;left:{PAD_H}px;top:{PAD_V}px;'
            f'font-size:13px;font-weight:700;color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">{_h(title)}</div>'
        )
    ty = PAD_V + (28 if title else 0)
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    ax1 = PAD_H + ITEM_W // 2
    ax2 = canvas_w - PAD_H - ITEM_W // 2
    parts.append(
        f'<line x1="{ax1}" y1="{axis_y}" x2="{ax2}" y2="{axis_y}" '
        f'stroke="var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))" stroke-width="1.5"/>'
    )
    parts.append('</svg>')
    for i, sec in enumerate(sections):
        ix = PAD_H + i * step + step // 2 - ITEM_W // 2
        parts.append(
            f'<div class="node node-rect" data-node-id="{_h(sec["period"])}" style="position:absolute;left:{ix}px;top:{ty}px;'
            f'width:{ITEM_W}px;padding:6px 8px;box-sizing:border-box;'
            f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
            f'border-radius:var(--node-radius,8px);'
            f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
            f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));"><span class="node-label" style="'
            f'display:block;font-size:12px;font-weight:700;'
            f'color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">{_h(sec["period"])}</span>'
        )
        for ev in sec["events"][:2]:
            parts.append(
                f'<span style="display:block;font-size:10px;'
                f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">{_h(ev)}</span>'
            )
        parts.append('</div>')
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: quadrantChart ─────────────────────────────────────────────────────────

_QUAD_POINT_RE = re.compile(r'^(.+?)\s*:\s*\[([0-9.]+)\s*,\s*([0-9.]+)\]')


def _layout_quadrant(src: str, direction: str, width_hint: int) -> str:
    """quadrantChart: 2×2 fixed grid with plotted data points."""
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
    canvas_w = width_hint or 800
    canvas_h = max(600, canvas_w * 3 // 4)
    gx = PAD + 24
    gy = PAD + (24 if title else 0)
    gw = canvas_w - gx - PAD
    gh = canvas_h - gy - PAD - 24
    mx, my = gx + gw // 2, gy + gh // 2

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    if title:
        parts.append(
            f'<div style="position:absolute;left:{gx}px;top:{PAD}px;'
            f'font-size:12px;font-weight:700;color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">{_h(title)}</div>'
        )
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    parts.append(
        f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" '
        f'fill="none" stroke="var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))" stroke-width="1.5"/>'
        f'<line x1="{mx}" y1="{gy}" x2="{mx}" y2="{gy + gh}" '
        f'stroke="var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))" stroke-width="1" stroke-dasharray="4 3"/>'
        f'<line x1="{gx}" y1="{my}" x2="{gx + gw}" y2="{my}" '
        f'stroke="var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))" stroke-width="1" stroke-dasharray="4 3"/>'
    )
    for pt in points:
        px = gx + int(pt["x"] * gw)
        py = gy + gh - int(pt["y"] * gh)
        r = 5
        poly = " ".join(
            f"{px + int(r * math.cos(math.pi * 2 * k / 8))},"
            f"{py + int(r * math.sin(math.pi * 2 * k / 8))}"
            for k in range(8)
        )
        parts.append(f'<polygon points="{poly}" fill="var(--edge-strong,var(--accent-1,#60a5fa))"/>')
    parts.append('</svg>')
    for qid, qlbl in quad_labels.items():
        qx = (mx + 8) if qid in ("1", "4") else (gx + 8)
        qy = (gy + 8) if qid in ("1", "2") else (my + 8)
        parts.append(
            f'<span style="position:absolute;left:{qx}px;top:{qy}px;'
            f'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;'
            f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">{_h(qlbl)}</span>'
        )
    parts.append(
        f'<span style="position:absolute;left:{gx}px;top:{gy + gh + 6}px;'
        f'font-size:10px;color:var(--node-fg-dim,var(--text-secondary,#75736C));'
        f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">{_h(x_labels[0])}</span>'
        f'<span style="position:absolute;right:{PAD}px;top:{gy + gh + 6}px;'
        f'font-size:10px;color:var(--node-fg-dim,var(--text-secondary,#75736C));'
        f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">{_h(x_labels[1])}</span>'
    )
    for pt in points:
        px = gx + int(pt["x"] * gw)
        py = gy + gh - int(pt["y"] * gh)
        parts.append(
            f'<span data-point="{_h(pt["name"])}" style="position:absolute;left:{px + 8}px;top:{py - 8}px;'
            f'font-size:10px;color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));white-space:nowrap;">'
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
        parts.append(
            f'<line x1="{cx_start - 4}" y1="{_ty}" x2="{cx_start}" y2="{_ty}" '
            f'stroke="{_tick_color}" stroke-width="1"/>'
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

def _layout_mindmap(src: str, direction: str, width_hint: int) -> str:
    """mindmap: indented tree layout, root at top."""
    content_lines = _directive_content(src)
    flat: list[dict] = []
    for raw in content_lines:
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith(("%%", "//")):
            continue
        indent = len(line) - len(line.lstrip())
        raw_node = line.strip()
        # Strip id-prefix + shape wrappers: id((lbl)), id[lbl], id(lbl), id{lbl}
        m_shape = re.match(r'^\w+(?:\(\((.+?)\)\)|\[(.+?)\]|\((.+?)\)|\{(.+?)\})', raw_node)
        if m_shape:
            lbl = next(g for g in m_shape.groups() if g is not None)
        else:
            lbl = re.sub(r'^[\[\(\{:]+|[\]\)\}]+$', '', raw_node).strip()
        if lbl:
            flat.append({"depth": indent, "label": lbl})
    if not flat:
        raise ValueError("No nodes found in mindmap.")

    # Normalize depths
    min_d = min(n["depth"] for n in flat)
    for n in flat:
        n["depth"] -= min_d

    PAD_H, PAD_V = 40, 24
    NODE_H_MM, NODE_GAP, INDENT_W = 32, 8, 24
    canvas_w = width_hint or 480
    canvas_h = PAD_V * 2 + len(flat) * (NODE_H_MM + NODE_GAP)

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    y_pos: list[int] = []
    for i, n in enumerate(flat):
        ny = PAD_V + i * (NODE_H_MM + NODE_GAP) + NODE_H_MM // 2
        nx = PAD_H + n["depth"] * INDENT_W
        y_pos.append(ny)
        if i > 0:
            for j in range(i - 1, -1, -1):
                if flat[j]["depth"] < n["depth"]:
                    parent_cy = y_pos[j]
                    child_cy = ny
                    elbow_x = PAD_H + flat[j]["depth"] * INDENT_W + 8
                    parts.append(
                        f'<path d="M{elbow_x},{parent_cy} V{child_cy} H{nx}" '
                        f'fill="none" stroke="var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))" stroke-width="1"/>'
                    )
                    break
    parts.append('</svg>')
    for i, n in enumerate(flat):
        ny = PAD_V + i * (NODE_H_MM + NODE_GAP)
        nx = PAD_H + n["depth"] * INDENT_W
        bold = "font-weight:700;" if n["depth"] == 0 else ""
        if n["depth"] == 0:
            bg = (
                f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
                f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));'
                f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
            )
        elif n["depth"] == 1:
            bg = 'background:rgba(53,148,103,0.08);'
        else:
            bg = 'background:rgba(53,148,103,0.05);'
        parts.append(
            f'<div class="node" data-node-id="{i}" style="position:absolute;left:{nx}px;top:{ny}px;'
            f'min-width:120px;height:{NODE_H_MM}px;display:flex;align-items:center;'
            f'padding:4px 8px;box-sizing:border-box;border-radius:var(--node-radius,8px);{bg}">'
            f'<span class="node-label" style="font-size:13px;{bold}'
            f'color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
            f'{_h(n["label"])}</span></div>'
        )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: block-beta ────────────────────────────────────────────────────────────

_BLOCK_ID_RE = re.compile(r'(\w+)(?:\["([^"]+)"\])?(?::(\d+))?')


_BLOCK_EDGE_RE = re.compile(r'(\w+)\s*(?:-->|<-->|---)\s*(\w+)')


def _layout_block(src: str, direction: str, width_hint: int) -> str:
    """block-beta: blocks in declared rows/columns with arrows."""
    content_lines = _directive_content(src)
    rows: list[list[dict]] = []
    current_row: list[dict] = []
    edges: list[tuple[str, str]] = []
    n_cols = 3
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m = re.match(r'columns\s+(\d+)', line, re.I)
        if m:
            n_cols = int(m.group(1)); continue
        # Edge lines contain --> or <-->
        # Split on operators to handle chaining: A --> B --> C → [(A,B),(B,C)]
        if '-->' in line or '<-->' in line or '---' in line:
            _ids = re.findall(r'\b(\w+)\b', line)
            for _i in range(len(_ids) - 1):
                edges.append((_ids[_i], _ids[_i + 1]))
            continue
        for token in line.split():
            m2 = _BLOCK_ID_RE.match(token)
            if m2 and m2.group(1) not in ("space", "classDef", "class"):
                current_row.append({
                    "id": m2.group(1),
                    "label": m2.group(2) or m2.group(1),
                    "span": int(m2.group(3)) if m2.group(3) else 1,
                })
                if len(current_row) >= n_cols:
                    rows.append(current_row); current_row = []
    if current_row:
        rows.append(current_row)
    if not rows:
        raise ValueError("No blocks found in block-beta.")

    PAD_H, PAD_V, CELL_H, CELL_GAP = 40, 24, 56, 24
    canvas_w = width_hint or PAD_H * 2 + n_cols * 120 + (n_cols - 1) * CELL_GAP
    # Compute responsive cell width so blocks fill the canvas
    available = canvas_w - 2 * PAD_H - (n_cols - 1) * CELL_GAP
    cell_w = max(80, available // n_cols)
    canvas_h = PAD_V * 2 + len(rows) * (CELL_H + CELL_GAP) - CELL_GAP

    # Build block positions for edge routing
    block_pos: dict[str, dict] = {}
    for ri, row in enumerate(rows):
        ry = PAD_V + ri * (CELL_H + CELL_GAP)
        cx_cur = PAD_H
        for blk in row:
            bw = cell_w * blk["span"] + CELL_GAP * (blk["span"] - 1)
            block_pos[blk["id"]] = {"x": cx_cur, "y": ry, "w": bw, "h": CELL_H}
            cx_cur += bw + CELL_GAP

    edge_color = "var(--edge,rgba(100,116,139,0.7))"
    svg_edges: list[str] = []
    for src_id, dst_id in edges:
        if src_id not in block_pos or dst_id not in block_pos:
            continue
        s, d = block_pos[src_id], block_pos[dst_id]
        # Right-center of source to left-center of dest (same row)
        # For cross-row, use bottom-center to top-center
        if abs((s["y"] + s["h"] / 2) - (d["y"] + d["h"] / 2)) < CELL_H:
            x1 = s["x"] + s["w"]; y1 = s["y"] + s["h"] // 2
            x2 = d["x"]; y2 = d["y"] + d["h"] // 2
        else:
            x1 = s["x"] + s["w"] // 2; y1 = s["y"] + s["h"]
            x2 = d["x"] + d["w"] // 2; y2 = d["y"]
        mx = (x1 + x2) // 2
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
            parts.append(
                f'<div class="node node-rect" data-node-id="{_h(blk["id"])}" style="position:absolute;'
                f'left:{cx_cur}px;top:{ry}px;width:{bw}px;height:{CELL_H}px;'
                f'display:flex;align-items:center;justify-content:center;'
                f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
                f'border-radius:var(--node-radius,8px);box-sizing:border-box;'
                f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
                f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));"><span class="node-label" style="'
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

_PKT_FIELD_RE = re.compile(r'^(\d+)(?:-(\d+))?\s*:\s*(.+)$')


def _layout_packet(src: str, direction: str, width_hint: int) -> str:
    """packet-beta: fixed-width bit-field cells."""
    content_lines = _directive_content(src)
    fields: list[dict] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m = _PKT_FIELD_RE.match(line)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            if start < 0 or end < start:
                raise ValueError(
                    f"packet-beta: invalid bit range {start}-{end} "
                    f"(start must be ≥ 0, end must be ≥ start)."
                )
            fields.append({"start": start, "end": end,
                           "bits": end - start + 1, "label": m.group(3).strip().strip('"')})
    if not fields:
        raise ValueError("No fields found in packet-beta.")

    total_bits = max(f["end"] for f in fields) + 1
    PAD_H, PAD_V, CELL_H = 40, 40, 56
    canvas_w = width_hint or 640
    available_w = canvas_w - PAD_H * 2
    bit_w = available_w / max(total_bits, 1)
    canvas_h = PAD_V * 2 + CELL_H + 20

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    for fld in fields:
        fx = PAD_H + int(fld["start"] * bit_w)
        fw = max(1, int(fld["bits"] * bit_w) - 1)
        _fld_id = f'{fld["start"]}-{fld["end"]}' if fld["end"] != fld["start"] else str(fld["start"])
        parts.append(
            f'<div class="node node-rect" data-field="{_fld_id}" style="position:absolute;'
            f'left:{fx}px;top:{PAD_V}px;width:{fw}px;height:{CELL_H}px;'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'border:1px solid var(--node-border,var(--card-border,#DAD7CE));'
            f'box-sizing:border-box;'
            f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),'
            f'var(--node-bg-to,var(--card-bg-to,#F7F6F2)));"><span class="node-label" style="'
            f'font-size:11px;font-weight:700;color:var(--node-fg,var(--text-primary,#191A17));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));text-align:center;">'
            f'{_h(fld["label"])}</span>'
            f'<span style="font-size:9px;color:var(--node-fg-dim,var(--text-secondary,#75736C));'
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
            f'{fld["start"]}{"–" + str(fld["end"]) if fld["end"] != fld["start"] else ""}'
            f'</span></div>'
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
_ARCH_GRP_RE = re.compile(
    r'^(?:group|junction)\s+(\w+)\s*(?:\([^)]*\))?\s*(?:\[([^\]]+)\])?', re.I
)
_ARCH_EDGE_RE = re.compile(
    r'^(\w+)(?::\w+)?\s*(?:-->|<-->|--)\s*(?:\w+:)?(\w+)(?::\w+)?(?:\s*:\s*(.*))?$'
)


def _layout_architecture(src: str, direction: str, width_hint: int) -> str:
    """architecture-beta: zone containers with service nodes and edges."""
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    groups: dict[str, _Group] = {}
    edges: list[_Edge] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m = _ARCH_SVC_RE.match(line)
        if m:
            sid = m.group(1)
            icon_hint = (m.group(2) or "").lower().strip()
            lbl = m.group(3)
            gin = m.group(4)
            icon_name = _ARCH_ICON_MAP.get(icon_hint, "")
            nodes[sid] = _Node(id=sid, label=lbl, shape="rect",
                               group=gin if gin else None, icon=icon_name)
            if gin:
                groups.setdefault(gin, _Group(id=gin, label=gin, members=[]))
                if sid not in groups[gin].members:
                    groups[gin].members.append(sid)
            continue
        m = _ARCH_GRP_RE.match(line)
        if m:
            gid, glbl = m.group(1), m.group(2) or m.group(1)
            if gid not in groups:
                groups[gid] = _Group(id=gid, label=glbl, members=[])
            else:
                groups[gid].label = glbl
            continue
        m = _ARCH_EDGE_RE.match(line)
        if m:
            edges.append(_Edge(src=m.group(1), dst=m.group(2),
                               label=(m.group(3) or "").strip(), style="solid", arrow=True))
    if not nodes:
        raise ValueError("No services found in architecture-beta.")
    return _graph_from_content_nodes(nodes, edges, groups, width_hint)


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
