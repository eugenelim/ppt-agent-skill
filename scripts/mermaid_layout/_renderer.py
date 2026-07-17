from __future__ import annotations

import re
from html import escape as _h

from ._constants import (
    _Node, _Edge, _Group,
    NODE_W, NODE_H, RANK_GAP, COL_GAP, CANVAS_PAD,
    GROUP_CAP, GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT,
    _NODE_H_TECH, _WRAP_CHARS, _WRAP_CHARS_ICON,
    _load_icon, _wrap_label, _split_sub_label, _node_render_h,
)
from ._routing import _route_edges


def _nh(text: str) -> str:
    """HTML-escape text and replace hyphens with non-breaking hyphens (U+2011).

    Prevents the browser from using hyphens inside node labels as soft line-break
    opportunities — those breaks come from our wrap algorithm via <br>, not CSS.
    U+2011 is visually identical to U+002D and supported by Inter/system fonts.
    """
    return _h(text).replace("-", "‑")


# ── HTML renderer (graph topology) ───────────────────────────────────────────

_NODE_CSS = {
    "rect": "border-radius:var(--node-radius,8px);",
    "round": "border-radius:28px;",
    # diamond uses clip-path to avoid rotating the label
    "diamond": "border-radius:4px; clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);",
    "cylinder": "border-radius:8px 8px 2px 2px;",
    "circle": "border-radius:50%;",
    "flag": "border-radius:0 8px 8px 0;",
}


# Accent colors in RGBA for group background tints (matches CSS --accent-1/3/4/2 order)
_ACCENT_CYCLE = ["var(--accent-1)", "var(--accent-3)", "var(--accent-4)", "var(--accent-2)"]
_ACCENT_TINTS = [
    "rgba(63,200,130,0.05)",   # emerald (accent-1)
    "rgba(77,184,236,0.05)",   # sky     (accent-3)
    "rgba(232,146,74,0.05)",   # amber   (accent-4)
    "rgba(123,84,245,0.05)",   # violet  (accent-2)
]


_LEGEND_H = 44  # px reserved below the diagram canvas for the legend strip


def _render_graph_fragment(
    nodes: dict[str, _Node],
    edges: list[_Edge],
    groups: dict[str, _Group],
    canvas_w: int,
    canvas_h: int,
    direction: str = "TB",
    zoom: float = 1.0,
    style_overrides: str = "",
    group_bboxes: dict[str, tuple[int, int, int, int]] | None = None,
    show_legend: bool = True,
) -> str:
    """Render an HTML fragment for a positioned graph.

    group_bboxes: optional {gid: (x1, y1, x2, y2)} override — pass ELK's
    pre-computed compound bboxes to skip _compute_group_bboxes entirely.
    show_legend: append a legend strip below the diagram when semantic edge styles exist.
    """
    # Generate legend early so we know whether to expand height.
    legend_html = _render_legend(edges, groups) if show_legend else ""
    effective_h = canvas_h + ((_LEGEND_H) if legend_html else 0)

    parts: list[str] = []

    # Container — zoom scales the whole diagram proportionally when it exceeds
    # the width hint, preserving geometry without distorting node sizes or gaps.
    zoom_css = f" zoom:{zoom:.4f};" if abs(zoom - 1.0) > 0.005 else ""
    extra_style = (" " + style_overrides.strip()) if style_overrides else ""
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative; width:{canvas_w}px; height:{effective_h}px; '
        f'--node-w:{NODE_W}px; --node-h:{NODE_H}px; '
        f'--rank-gap:{RANK_GAP}px; --col-gap:{COL_GAP}px; '
        f'--canvas-pad:{CANVAS_PAD}px;{zoom_css}{extra_style}">'
    )

    # Build node → group accent index for title-color inheritance
    _grp_ids = list(groups.keys())
    _node_grp_idx: dict[str, int] = {}
    for _gi, gid in enumerate(_grp_ids):
        for _nid in groups[gid].members:
            _node_grp_idx[_nid] = _gi

    # Group containers (subgraphs) — dashed border + subtle tint per accent slot.
    _grp_bboxes = group_bboxes if group_bboxes is not None else _compute_group_bboxes(nodes, groups, canvas_w, canvas_h)
    for _gi, (gid, grp) in enumerate(groups.items()):
        if gid not in _grp_bboxes:
            continue
        _b = _grp_bboxes[gid]
        gx, gy = int(_b[0]), int(_b[1])
        gw, gh = max(1, int(_b[2] - _b[0])), max(1, int(_b[3] - _b[1]))
        glabel = _h(grp.label)
        _accent = _ACCENT_CYCLE[_gi % len(_ACCENT_CYCLE)]
        _tint = _ACCENT_TINTS[_gi % len(_ACCENT_TINTS)]
        parts.append(
            f'<div class="diagram-group" style="'
            f'position:absolute; left:{gx}px; top:{gy}px; '
            f'width:{gw}px; height:{gh}px; '
            f'border:1px dashed {_accent}; '
            f'background:{_tint}; '
            f'border-radius:var(--group-radius,12px); '
            f'box-sizing:border-box; overflow:visible;">'
            f'<span class="group-label" style="'
            f'position:absolute; top:4px; left:8px; '
            f'font-size:10px; color:{_accent}; '
            f'font-weight:600; letter-spacing:0.06em; text-transform:uppercase; '
            f'max-width:{max(60, gw - 16)}px; line-height:1.3; '
            f'font-family:var(--label-font,var(--font-primary));">'
            f'{glabel}</span></div>'
        )

    # Node divs
    for nid, n in nodes.items():
        if n.is_dummy:
            parts.append(
                f'<div style="position:absolute; left:{n.x}px; top:{n.y}px; '
                f'width:0; height:0; overflow:hidden;"></div>'
            )
            continue
        shape_css = _NODE_CSS.get(n.shape, _NODE_CSS["rect"])
        is_external = n.css_class == "external"

        # Split label on first | for tech stereotype sub-label (e.g. "User Service|Spring Boot")
        if "|" in n.label:
            raw_label, tech_label = (p.strip() for p in n.label.split("|", 1))
        else:
            raw_label, tech_label = n.label, ""

        # Split [bracketed sub-label] on newline from the main title
        main_label, bracket_sub = _split_sub_label(raw_label)

        icon_svg = _load_icon(n.icon) if n.icon else (_load_icon(n.css_class) if n.css_class else "")
        node_h = _node_render_h(n)

        # Icon-left cards have a narrower text column; use reduced wrap limit so the
        # HTML line breaks match what _node_render_h already assumed for height sizing.
        _wc = _WRAP_CHARS_ICON if icon_svg else _WRAP_CHARS
        main_lines = _wrap_label(main_label, max_chars=_wc)
        main_html = "<br>".join(_nh(ln) for ln in main_lines)

        # Accent color comes from group membership; used for top border + icon.
        # External nodes get no accent (greyscale treatment) — dim top border matches dim body.
        fg_var = "var(--node-fg-dim,var(--text-secondary))" if is_external else "var(--node-fg,var(--text-primary))"
        border_var = "var(--node-fg-dim,var(--text-secondary))" if is_external else "var(--node-border,var(--card-border))"
        if is_external:
            accent_color = "var(--node-fg-dim,var(--text-secondary))"
        elif nid in _node_grp_idx:
            accent_color = _ACCENT_CYCLE[_node_grp_idx[nid] % len(_ACCENT_CYCLE)]
        else:
            accent_color = "var(--node-title-fg,var(--accent-1))"
        # All text uses the same fg variable regardless of group
        text_color = fg_var

        sub_span = ""
        if bracket_sub:
            sub_lines = _wrap_label(bracket_sub, max_chars=_wc)
            sub_html = "<br>".join(_nh(ln) for ln in sub_lines)
            sub_span = (
                f'<span class="node-sub" style="'
                f'display:block; font-size:var(--node-fs-sub,12px); font-weight:400; '
                f'color:{text_color}; opacity:0.7; '
                f'font-family:var(--label-font,var(--font-primary)); '
                f'line-height:1.3; margin-top:2px; text-align:left;">'
                f'{sub_html}</span>'
            )

        # tech_span: full-width separator line (expanded card body section)
        tech_span = ""
        if tech_label:
            tech_span = (
                f'<span class="node-tech" style="'
                f'display:block; font-size:var(--node-fs-tech,12px); font-weight:400; '
                f'color:{text_color}; opacity:0.6; '
                f'font-family:var(--label-font,var(--font-primary)); '
                f'line-height:1.3; margin-top:7px; padding-top:7px; '
                f'border-top:1px solid var(--node-border,var(--card-border)); '
                f'text-align:left; width:100%;">'
                f'{_h(tech_label)}</span>'
            )

        if icon_svg:
            # Icon-left, text-right layout for header; tech body below full-width separator.
            header_row = (
                f'<div class="node-header" style="display:flex; flex-direction:row; '
                f'align-items:center; width:100%;">'
                f'<span class="node-icon" style="'
                f'display:block; flex-shrink:0; width:24px; height:24px; '
                f'margin-right:10px; color:{accent_color};">'
                f'{icon_svg}</span>'
                f'<div class="node-text" style="min-width:0; flex:1; overflow-wrap:break-word; word-break:break-word;">'
                f'<span class="node-label" style="'
                f'font-size:var(--node-fs-title,14px); font-weight:700; '
                f'color:{text_color}; '
                f'font-family:var(--label-font,var(--font-primary)); '
                f'line-height:1.3; display:block;">{main_html}</span>'
                f'{sub_span}'
                f'</div></div>'
            )
            inner = header_row + tech_span
        else:
            inner = (
                f'<span class="node-label" style="'
                f'font-size:var(--node-fs-title,15px); font-weight:700; '
                f'color:{text_color}; '
                f'font-family:var(--label-font,var(--font-primary)); '
                f'line-height:1.4; display:block;">{main_html}</span>'
                f'{sub_span}{tech_span}'
            )

        # Accent appears as a 2px colored top border; other borders stay neutral
        extra_cls = f" node-{n.css_class}" if n.css_class else ""
        parts.append(
            f'<div class="node node-{_h(n.shape)}{extra_cls}" style="'
            f'position:absolute; left:{n.x}px; top:{n.y}px; '
            f'width:var(--node-w,{NODE_W}px); min-height:{node_h}px; '
            f'min-width:{NODE_W}px; '
            f'padding:var(--node-pad-v,12px) var(--node-pad-h,12px); '
            f'box-sizing:border-box; overflow:hidden; '
            f'border:1px solid {border_var}; border-top:3px solid {accent_color}; '
            f'{shape_css} '
            f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from)),var(--node-bg-to,var(--card-bg-to))); '
            f'box-shadow:var(--node-shadow,none); '
            f'display:flex; flex-direction:column; align-items:flex-start; justify-content:center; '
            f'text-align:left;">'
            f'{inner}</div>'
        )

    # SVG overlay — paths and arrowheads only; edge labels as HTML siblings below
    parts.append(
        f'<svg style="position:absolute; inset:0; '
        f'width:{canvas_w}px; height:{canvas_h}px; '
        f'overflow:visible; pointer-events:none;">'
    )

    routed = _route_edges(nodes, edges, canvas_w, direction, group_bboxes=_grp_bboxes)
    for spec in routed:
        d = spec["d"]
        style = spec["style"]
        if style == "thick":
            stroke_color = "var(--edge-strong,var(--accent-1))"
        elif style == "dotted":
            stroke_color = "var(--accent-4,var(--amber,#E8924A))"
        else:
            stroke_color = "var(--edge,var(--card-border))"
        dash = ' stroke-dasharray="6 4"' if style == "dotted" else ""
        stroke_w = "2" if style == "thick" else "1.5"
        parts.append(
            f'<path d="{d}" stroke="{stroke_color}" fill="none" '
            f'stroke-width="{stroke_w}"{dash}/>'
        )
        if spec["ah"]:
            parts.append(
                f'<polygon points="{spec["ah"]}" fill="{stroke_color}"/>'
            )

    parts.append('</svg>')

    # Edge labels as absolutely-positioned HTML siblings (not inside SVG)
    for spec in routed:
        if spec["label"]:
            lx, ly = spec["lx"], spec["ly"]
            rot = spec.get("rot", 0)
            rot_part = f" rotate({rot}deg)" if rot else ""
            parts.append(
                f'<span class="edge-label" style="'
                f'position:absolute; left:{lx}px; top:{ly}px; '
                f'font-size:11px; font-weight:500; '
                f'font-family:var(--label-font,var(--font-primary)); '
                f'color:var(--node-fg-dim,var(--text-secondary)); '
                f'background:var(--bg-primary,var(--card-bg-from,#0a0a0a)); '
                f'padding:1px 4px; border-radius:3px; '
                f'max-width:300px; overflow:hidden; '
                f'white-space:nowrap; text-overflow:ellipsis; pointer-events:none; z-index:2; '
                f'transform:translateY(-100%){rot_part};">'
                f'{_h(spec["label"])}</span>'
            )

    # Legend strip at bottom of diagram container (only when semantic styles present)
    if legend_html:
        parts.append(
            f'<div style="position:absolute; bottom:0; left:{CANVAS_PAD}px; '
            f'right:{CANVAS_PAD}px; height:{_LEGEND_H}px; '
            f'display:flex; align-items:center;">{legend_html}</div>'
        )

    parts.append('</div>')
    return "\n".join(parts)


# ── style preset strings for _dispatch(style_overrides=...) ──────────────────

# Default (no overrides): 15px title, 12px sub/tech — optimized for presentation slides.
# Pass one of these to _dispatch() to switch layout density:

STYLE_COMPACT = (
    "--node-fs-title:13px;"
    "--node-fs-sub:11px;"
    "--node-fs-tech:11px;"
    "--node-pad-v:12px;"
    "--node-pad-h:16px;"
)
"""Compact style for information-dense diagrams (smaller fonts, tighter padding)."""

STYLE_LARGE = (
    "--node-fs-title:17px;"
    "--node-fs-sub:14px;"
    "--node-fs-tech:14px;"
    "--node-pad-v:20px;"
    "--node-pad-h:24px;"
)
"""Large style for hero/title slides with fewer nodes."""


# ── diagram metadata + legend helpers ────────────────────────────────────────

_DIRECTIVE_LABELS: dict[str, str] = {
    "flowchart": "Flowchart", "graph": "Graph",
    "sequencediagram": "Sequence", "statediagram-v2": "State Machine",
    "statediagram": "State Machine", "erdiagram": "ER Diagram",
    "classdiagram": "Class Diagram", "gantt": "Gantt",
    "timeline": "Timeline", "quadrantchart": "Quadrant",
    "pie": "Pie Chart", "xychart-beta": "Chart",
    "mindmap": "Mind Map", "block-beta": "Block",
    "architecture-beta": "Architecture", "c4context": "C4 Context",
    "c4container": "C4 Container", "c4component": "C4 Component",
    "kanban": "Kanban",
}


def _extract_diagram_title(src: str) -> str:
    """Return the text from a '%% title: <text>' comment, or '' if none present."""
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("%%"):
            comment = s[2:].strip()
            if comment.lower().startswith("title:"):
                return comment[6:].strip()
    return ""


def _render_metadata_chip(directive: str, title: str) -> str:
    """Return a type-chip + title bar only when a title is explicitly set.

    Omitting the chip for untitled diagrams avoids adding visual chrome to every
    existing diagram. The type badge only appears alongside a title.
    """
    if not title:
        return ""
    type_label = _DIRECTIVE_LABELS.get(directive.lower(), "")
    parts: list[str] = []
    parts.append(
        '<div class="diagram-meta" style="'
        'display:flex; align-items:center; gap:8px; '
        'margin-bottom:8px; '
        'font-family:var(--label-font,var(--font-primary));">'
    )
    if type_label:
        parts.append(
            f'<span class="diagram-type-chip" style="'
            f'border:1px solid var(--node-fg-dim,var(--text-secondary)); '
            f'border-radius:4px; padding:1px 6px; '
            f'font-size:9px; font-weight:700; letter-spacing:0.07em; '
            f'text-transform:uppercase; '
            f'color:var(--node-fg-dim,var(--text-secondary));">'
            f'{_h(type_label)}</span>'
        )
    if title:
        parts.append(
            f'<span class="diagram-title" style="'
            f'font-size:11px; font-weight:600; '
            f'color:var(--node-fg,var(--text-primary));">'
            f'{_h(title)}</span>'
        )
    parts.append('</div>')
    return "".join(parts)


def _render_legend(edges: list[_Edge], groups: dict) -> str:
    """Return an auto-generated legend row when ≥1 non-solid semantic is present."""
    has_solid = any(e.style == "solid" for e in edges if not e.reversed_)
    has_dashed = any(e.style == "dotted" for e in edges)
    has_thick = any(e.style == "thick" for e in edges)
    has_groups = bool(groups)

    # Only show legend when there's something non-obvious to explain
    semantic_count = sum([has_dashed, has_thick, has_groups])
    if semantic_count == 0:
        return ""

    items: list[str] = []
    if has_solid:
        items.append(
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<svg width="20" height="10" style="overflow:visible;">'
            '<line x1="0" y1="5" x2="20" y2="5" '
            'stroke="var(--edge,var(--card-border))" stroke-width="1.5"/>'
            '<polygon points="20,5 15,2.5 15,7.5" '
            'fill="var(--edge,var(--card-border))"/>'
            '</svg>'
            'Synchronous</span>'
        )
    if has_dashed:
        items.append(
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<svg width="20" height="10" style="overflow:visible;">'
            '<line x1="0" y1="5" x2="20" y2="5" '
            'stroke="var(--accent-4,var(--amber,#E8924A))" stroke-width="1.5" '
            'stroke-dasharray="4 3"/>'
            '<polygon points="20,5 15,2.5 15,7.5" '
            'fill="var(--accent-4,var(--amber,#E8924A))"/>'
            '</svg>'
            'Async / optional</span>'
        )
    if has_thick:
        items.append(
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<svg width="20" height="10" style="overflow:visible;">'
            '<line x1="0" y1="5" x2="20" y2="5" '
            'stroke="var(--edge-strong,var(--accent-1))" stroke-width="2.5"/>'
            '<polygon points="20,5 15,2.5 15,7.5" '
            'fill="var(--edge-strong,var(--accent-1))"/>'
            '</svg>'
            'Critical path</span>'
        )
    if has_groups:
        items.append(
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<svg width="20" height="10">'
            '<rect x="0" y="1" width="20" height="8" rx="2" '
            'fill="none" stroke="var(--group-border,var(--accent-1))" '
            'stroke-width="1"/>'
            '</svg>'
            'Service boundary</span>'
        )

    if not items:
        return ""
    joined = "\n".join(items)
    return (
        '<div class="diagram-legend" style="'
        'display:flex; flex-wrap:wrap; gap:12px; '
        'padding-top:8px; '
        'border-top:1px solid var(--node-fg-dim,var(--card-border)); '
        'margin-top:0; '
        'font-size:10px; font-family:var(--label-font,var(--font-primary)); '
        'color:var(--node-fg-dim,var(--text-secondary));">'
        f'{joined}'
        '</div>'
    )


# ── group overlap resolution ─────────────────────────────────────────────────

def _separate_groups_lr(
    nodes: dict[str, "_Node"],
    groups: dict[str, "_Group"],
) -> None:
    """Iteratively push overlapping group bounding boxes apart vertically (LR mode only).

    When two groups overlap in both x and y, the lower group is shifted down by the
    overlap depth + COL_GAP. Runs up to GROUP_CAP passes; stops early when stable.
    """

    def _bbox(gid: str) -> dict | None:
        mbrs = [nodes[m] for m in groups[gid].members if m in nodes and not nodes[m].is_dummy]
        if not mbrs:
            return None
        return {
            "gy":       min(n.y for n in mbrs) - GROUP_PAD_Y_TOP,
            "gy_bot":   max(n.y + _node_render_h(n) for n in mbrs) + GROUP_PAD_Y_BOT,
            "gx":       min(n.x for n in mbrs) - GROUP_PAD_X,
            "gx_right": max(n.x + NODE_W for n in mbrs) + GROUP_PAD_X,
        }

    for _pass in range(GROUP_CAP):
        boxes = {gid: _bbox(gid) for gid in groups}
        boxes = {gid: b for gid, b in boxes.items() if b is not None}
        if not boxes:
            break

        sorted_gids = sorted(boxes, key=lambda g: boxes[g]["gy"])
        moved = False
        for i, gid1 in enumerate(sorted_gids):
            b1 = boxes[gid1]
            for gid2 in sorted_gids[i + 1:]:
                b2 = boxes[gid2]
                x_overlap = b1["gx"] < b2["gx_right"] and b2["gx"] < b1["gx_right"]
                y_overlap = b1["gy"] < b2["gy_bot"] and b2["gy"] < b1["gy_bot"]
                if x_overlap and y_overlap:
                    shift = b1["gy_bot"] - b2["gy"] + COL_GAP
                    for nid in groups[gid2].members:
                        if nid in nodes:
                            nodes[nid].y += shift
                    moved = True
                    break
            if moved:
                break
        if not moved:
            break


def _separate_groups_tb(
    nodes: dict[str, "_Node"],
    groups: dict[str, "_Group"],
    canvas_w: int,
) -> int:
    """Iteratively push groups with overlapping X+Y bboxes apart horizontally (TB mode).

    When two groups overlap in both x and y, the right-er group is shifted right by
    the X overlap + COL_GAP. Returns updated canvas_w (shifted nodes may extend it).
    Runs up to GROUP_CAP passes; stops early when stable.
    """
    def _bbox(gid: str) -> dict | None:
        mbrs = [nodes[m] for m in groups[gid].members if m in nodes and not nodes[m].is_dummy]
        if not mbrs:
            return None
        return {
            "gx":       min(n.x for n in mbrs) - GROUP_PAD_X,
            "gx_right": max(n.x + NODE_W for n in mbrs) + GROUP_PAD_X,
            "gy":       min(n.y for n in mbrs) - GROUP_PAD_Y_TOP,
            "gy_bot":   max(n.y + _node_render_h(n) for n in mbrs) + GROUP_PAD_Y_BOT,
        }

    for _pass in range(GROUP_CAP):
        boxes = {gid: _bbox(gid) for gid in groups}
        boxes = {gid: b for gid, b in boxes.items() if b is not None}
        if not boxes:
            break
        sorted_gids = sorted(boxes, key=lambda g: boxes[g]["gx"])
        moved = False
        for i, gid1 in enumerate(sorted_gids):
            b1 = boxes[gid1]
            for gid2 in sorted_gids[i + 1:]:
                b2 = boxes[gid2]
                x_overlap = b1["gx"] < b2["gx_right"] and b2["gx"] < b1["gx_right"]
                y_overlap = b1["gy"] < b2["gy_bot"] and b2["gy"] < b1["gy_bot"]
                if x_overlap and y_overlap:
                    shift = int(b1["gx_right"] - b2["gx"] + COL_GAP)
                    for nid in groups[gid2].members:
                        if nid in nodes:
                            nodes[nid].x += shift
                    moved = True
                    break
            if moved:
                break
        if not moved:
            break

    # Recompute canvas_w from the furthest non-dummy node right edge + CANVAS_PAD
    all_non_dummy = [n for n in nodes.values() if not n.is_dummy]
    if all_non_dummy:
        canvas_w = int(max(n.x + NODE_W for n in all_non_dummy) + CANVAS_PAD)
    return canvas_w


def _compute_group_bboxes(
    nodes: dict[str, "_Node"],
    groups: dict[str, "_Group"],
    canvas_w: int,
    canvas_h: int,
) -> dict[str, list[float]]:
    """Compute non-overlapping, canvas-clipped group bounding boxes [x0, y0, x1, y1].

    1. Compute padded bboxes (GROUP_PAD_* outset).
    2. Exclude non-member node intrusions: shrink the nearest group edge away from
       each standalone node that falls inside a group's bbox (4px gap min).
    3. Resolve pairwise bbox overlaps by splitting each overlap at its midpoint.
    4. Clip all bboxes to [0, canvas_w] × [0, canvas_h].
    """
    bboxes: dict[str, list[float]] = {}
    for gid, grp in groups.items():
        mbrs = [nodes[m] for m in grp.members if m in nodes and not nodes[m].is_dummy]
        if not mbrs:
            continue
        x0 = float(min(n.x for n in mbrs) - GROUP_PAD_X)
        y0 = float(min(n.y for n in mbrs) - GROUP_PAD_Y_TOP)
        x1 = float(max(n.x + NODE_W for n in mbrs) + GROUP_PAD_X)
        y1 = float(max(n.y + _node_render_h(n) for n in mbrs) + GROUP_PAD_Y_BOT)
        bboxes[gid] = [x0, y0, x1, y1]

    if not bboxes:
        return bboxes

    member_ids = {nid for grp in groups.values() for nid in grp.members}
    _NM_GAP = 4.0  # minimum gap between group edge and intruding non-member

    # Step 2: non-member node exclusion
    for nid, nd in nodes.items():
        if nd.is_dummy or nid in member_ids:
            continue
        nx0, ny0 = float(nd.x), float(nd.y)
        nx1, ny1 = float(nd.x + NODE_W), float(nd.y + _node_render_h(nd))
        for b in bboxes.values():
            if not (b[0] < nx1 and nx0 < b[2] and b[1] < ny1 and ny0 < b[3]):
                continue
            # Intrusion detected — shrink closest edge
            x_intrude = min(nx1 - b[0], b[2] - nx0)
            y_intrude = min(ny1 - b[1], b[3] - ny0)
            if x_intrude <= y_intrude:
                if nx0 < (b[0] + b[2]) / 2:
                    b[0] = nx1 + _NM_GAP
                else:
                    b[2] = nx0 - _NM_GAP
            else:
                if ny0 < (b[1] + b[3]) / 2:
                    b[1] = ny1 + _NM_GAP
                else:
                    b[3] = ny0 - _NM_GAP

    # Step 3: pairwise overlap resolution (iterative, up to GROUP_CAP passes)
    gids = list(bboxes)
    for _ in range(GROUP_CAP):
        changed = False
        for i, g1 in enumerate(gids):
            b1 = bboxes[g1]
            for g2 in gids[i + 1:]:
                b2 = bboxes[g2]
                ox = min(b1[2], b2[2]) - max(b1[0], b2[0])
                oy = min(b1[3], b2[3]) - max(b1[1], b2[1])
                if ox > 0 and oy > 0:
                    if ox <= oy:
                        mid = (max(b1[0], b2[0]) + min(b1[2], b2[2])) / 2
                        if b1[0] < b2[0]:
                            b1[2] = mid
                            b2[0] = mid
                        else:
                            b2[2] = mid
                            b1[0] = mid
                    else:
                        mid = (max(b1[1], b2[1]) + min(b1[3], b2[3])) / 2
                        if b1[1] < b2[1]:
                            b1[3] = mid
                            b2[1] = mid
                        else:
                            b2[3] = mid
                            b1[1] = mid
                    changed = True
                    break
            if changed:
                break
        if not changed:
            break

    # Step 4: clip to canvas bounds
    for b in bboxes.values():
        b[0] = max(0.0, b[0])
        b[1] = max(0.0, b[1])
        b[2] = min(float(canvas_w), b[2])
        b[3] = min(float(canvas_h), b[3])

    return bboxes

