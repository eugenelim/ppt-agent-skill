from __future__ import annotations

import re
from html import escape as _h

from ._constants import (
    _Node, _Edge, _Group,
    NODE_W, NODE_H, RANK_GAP, COL_GAP, CANVAS_PAD,
    GROUP_CAP, GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT,
    _NODE_H_TECH, ICON_COL_WIDTH,
    _TERMINAL_NODE_SIZE, _is_terminal_circle,
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


def _render_label_html(label: str) -> str:
    """Apply inline Markdown-like formatting to a joined label string.

    Handles **bold**, *italic*, ~~strikethrough~~ delimiters.  The state
    machine resets at each <br> so delimiters never cross line boundaries.
    Mismatched or unclosed delimiters are emitted as literal text — no
    partial tags.
    """
    _DELIMS = [("**", "font-weight:700"), ("~~", "text-decoration:line-through"), ("*", "font-style:italic")]
    result_parts: list[str] = []
    for seg in label.split("<br>"):
        buf: list[str] = []
        open_delim = ""
        open_style = ""
        open_pos = -1
        i = 0
        while i < len(seg):
            found = False
            for delim, style in _DELIMS:
                if seg[i : i + len(delim)] == delim:
                    if not open_delim:
                        open_delim = delim
                        open_style = style
                        open_pos = len(buf)
                        buf.append(f'<span style="{style}">')
                    elif open_delim == delim:
                        buf.append("</span>")
                        open_delim = ""
                        open_style = ""
                        open_pos = -1
                    else:
                        buf.append(_h(delim))
                    i += len(delim)
                    found = True
                    break
            if not found:
                buf.append(_h(seg[i]))
                i += 1
        if open_delim:
            # Unclosed — replace the opening span tag with the literal delimiter.
            buf[open_pos] = _h(open_delim)
        result_parts.append("".join(buf))
    return "<br>".join(result_parts)


# ── HTML renderer (graph topology) ───────────────────────────────────────────

_NODE_CSS = {
    "rect": "border-radius:var(--node-radius,8px);",
    "round": "border-radius:28px;",
    "stadium": "border-radius:50px;",
    # diamond uses clip-path to avoid rotating the label
    "diamond": "border-radius:4px; clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);",
    "hexagon": "clip-path:polygon(25% 0%,75% 0%,100% 50%,75% 100%,25% 100%,0% 50%); border-radius:4px; overflow:visible;",
    "subroutine": "border-radius:4px;",
    "trapezoid": "clip-path:polygon(10% 0%,90% 0%,100% 100%,0% 100%); border-radius:4px;",
    "trapezoid-alt": "clip-path:polygon(0% 0%,100% 0%,90% 100%,10% 100%); border-radius:4px;",
    "doublecircle": "border-radius:50%; position:relative;",
    "cylinder": "border-radius:8px 8px 2px 2px;",
    "circle": "border-radius:50%;",
    "flag": "border-radius:0 8px 8px 0;",
}


# Accent colors for group borders (matches THEME_LIGHT accent-1/3/4/2 cycle order)
# Warm earth-tone palette: emerald, amber, sky, violet — cycles across subgraph groups.
_ACCENT_CYCLE = ["var(--accent-1,#3F7D5A)", "var(--accent-3,#B7791F)", "var(--accent-4,#1F3A5F)", "var(--accent-2,#6B4A7A)"]
# Tints echo the border color at low opacity for group fill.
_ACCENT_TINTS = [
    "rgba(63,125,90,0.05)",    # group 0 → accent-1 (emerald)
    "rgba(183,121,31,0.05)",   # group 1 → accent-3 (amber)
    "rgba(31,58,95,0.05)",     # group 2 → accent-4 (sky)
    "rgba(107,74,122,0.05)",   # group 3 → accent-2 (violet)
]

# Rank → depth wash colors: subtle per-layer tints for architectural depth (C4-style)
# rank 0 = client/user layer (warm), rank 1 = neutral, rank 2+ = cool/deep
_DEPTH_TINTS = [
    "rgba(232,146,74,0.06)",   # rank 0 — warm amber (client / user layer)
    "rgba(0,0,0,0)",           # rank 1 — neutral (gateway / edge layer)
    "rgba(34,211,238,0.06)",   # rank 2 — cool cyan (service layer)
    "rgba(99,102,241,0.08)",   # rank 3+ — indigo (data / persistence)
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
            f'position:absolute; top:8px; left:10px; '
            f'font-size:11px; color:{_accent}; '
            f'font-weight:600; letter-spacing:0.04em; text-transform:uppercase; '
            f'max-width:{max(60, gw - 20)}px; line-height:1.3; '
            f'display:block; overflow-wrap:break-word; word-break:break-word; '
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
            f'{glabel}</span></div>'
        )

    # Depth wash: rank-to-tint index for architectural layer encoding
    _real_ranks = [n.rank for n in nodes.values() if not n.is_dummy]
    _max_rank = max(_real_ranks) if _real_ranks else 0

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

        # Depth wash: subtle rank-based tint for architectural layer encoding.
        # External nodes are outside the layered system — no tint (fully neutral).
        if is_external:
            _depth_wash = "rgba(0,0,0,0)"
        else:
            _depth_idx = min(n.rank, len(_DEPTH_TINTS) - 1)
            _depth_wash = _DEPTH_TINTS[_depth_idx]

        # Icon-left cards have a narrower text column; use the same pixel budget
        # as _node_render_h so HTML line breaks match the computed height.
        _wbudget = (NODE_W - 40 - ICON_COL_WIDTH) if icon_svg else (NODE_W - 40)
        main_lines = _wrap_label(main_label, width_budget=_wbudget)
        main_html = _render_label_html("<br>".join(_nh(ln) for ln in main_lines))

        # Accent color comes from group membership; used for top border + icon.
        # External nodes get no accent (greyscale treatment) — dim top border matches dim body.
        fg_var = "var(--node-fg-dim,var(--text-secondary,#75736C))" if is_external else "var(--node-fg,var(--text-primary,#191A17))"
        border_var = "var(--node-fg-dim,var(--text-secondary,#75736C))" if is_external else "var(--node-border,var(--card-border,#DAD7CE))"
        if is_external:
            accent_color = "var(--node-fg-dim,var(--text-secondary,#75736C))"
        elif nid in _node_grp_idx:
            accent_color = _ACCENT_CYCLE[_node_grp_idx[nid] % len(_ACCENT_CYCLE)]
        else:
            accent_color = "var(--node-title-fg,var(--accent-1,#60a5fa))"
        # All text uses the same fg variable regardless of group
        text_color = fg_var

        sub_span = ""
        if bracket_sub:
            sub_lines = _wrap_label(bracket_sub, width_budget=_wbudget)
            sub_html = "<br>".join(_nh(ln) for ln in sub_lines)
            sub_span = (
                f'<span class="node-sub" style="'
                f'display:block; font-size:var(--node-fs-sub,12px); font-weight:400; '
                f'color:{text_color}; opacity:0.7; '
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif)); '
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
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif)); '
                f'line-height:1.3; margin-top:7px; padding-top:7px; '
                f'border-top:1px solid var(--node-border,var(--card-border,#DAD7CE)); '
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
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif)); '
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
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif)); '
                f'line-height:1.4; display:block;">{main_html}</span>'
                f'{sub_span}{tech_span}'
            )

        # Accent appears as a 2px colored top border; other borders stay neutral
        extra_cls = f" node-{n.css_class}" if n.css_class else ""
        if _is_terminal_circle(n):
            # UML initial/final state: small fixed-size circle, no padding, centered symbol
            parts.append(
                f'<div class="node node-circle{extra_cls}" style="'
                f'position:absolute; left:{n.x}px; top:{n.y}px; '
                f'width:{_TERMINAL_NODE_SIZE}px; height:{_TERMINAL_NODE_SIZE}px; '
                f'border-radius:50%; box-sizing:border-box; '
                f'border:2px solid {accent_color}; '
                f'background:{_depth_wash},linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),var(--node-bg-to,var(--card-bg-to,#F7F6F2))); '
                f'display:flex; align-items:center; justify-content:center;">'
                f'<span style="color:{accent_color}; font-size:14px; line-height:1;">'
                f'{_nh(n.label)}</span></div>'
            )
        else:
            # Accent top border only works on shapes without a clip-path.
            # Diamond and flag nodes clip their top edge to a point/slant —
            # the 3px accent stripe is invisible. Use a full 2px accent border
            # for those shapes instead.
            _uses_clip = n.shape in ("diamond", "flag", "hexagon", "trapezoid", "trapezoid-alt")
            if is_external:
                _border_css = f'border:1px dashed {border_var};'
            elif _uses_clip:
                _border_css = f'border:2px solid {accent_color};'
            else:
                _border_css = f'border:1px solid {border_var}; border-top:3px solid {accent_color};'

            if n.shape == "doublecircle":
                # Outer circle + inner concentric circle (5px inset)
                parts.append(
                    f'<div class="node node-doublecircle{extra_cls}" style="'
                    f'position:absolute; left:{n.x}px; top:{n.y}px; '
                    f'width:{node_h}px; height:{node_h}px; '
                    f'border-radius:50%; box-sizing:border-box; overflow:visible; '
                    f'border:2px solid {accent_color}; '
                    f'background:linear-gradient({_depth_wash},{_depth_wash}),linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),var(--node-bg-to,var(--card-bg-to,#F7F6F2))); '
                    f'box-shadow:var(--node-shadow,0 1px 2px rgba(25,26,23,0.06),0 1px 0 rgba(25,26,23,0.03)); '
                    f'display:flex; align-items:center; justify-content:center;">'
                    f'<div style="position:absolute; inset:5px; border-radius:50%; '
                    f'border:2px solid {accent_color}; pointer-events:none;"></div>'
                    f'{inner}</div>'
                )
            elif n.shape == "subroutine":
                # Rect with two inner vertical lines near left and right edges
                parts.append(
                    f'<div class="node node-subroutine{extra_cls}" style="'
                    f'position:absolute; left:{n.x}px; top:{n.y}px; '
                    f'width:var(--node-w,{NODE_W}px); min-height:{node_h}px; '
                    f'min-width:{NODE_W}px; '
                    f'padding:var(--node-pad-v,12px) var(--node-pad-h,12px); '
                    f'box-sizing:border-box; overflow:visible; '
                    f'{_border_css} '
                    f'{shape_css} '
                    f'background:linear-gradient({_depth_wash},{_depth_wash}),linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),var(--node-bg-to,var(--card-bg-to,#F7F6F2))); '
                    f'box-shadow:var(--node-shadow,0 1px 2px rgba(25,26,23,0.06),0 1px 0 rgba(25,26,23,0.03)); '
                    f'display:flex; flex-direction:column; align-items:flex-start; justify-content:center; '
                    f'text-align:left;">'
                    f'{inner}'
                    f'<svg style="position:absolute;inset:0;width:{NODE_W}px;height:{node_h}px;pointer-events:none;overflow:visible;">'
                    f'<line x1="8" y1="0" x2="8" y2="{node_h}" stroke="{accent_color}" stroke-width="1.5"/>'
                    f'<line x1="{NODE_W - 8}" y1="0" x2="{NODE_W - 8}" y2="{node_h}" stroke="{accent_color}" stroke-width="1.5"/>'
                    f'</svg>'
                    f'</div>'
                )
            else:
                # Diamond/hexagon use clip-path: center text so it sits in the
                # widest part of the polygon and doesn't touch the clipped edges.
                _center_shapes = n.shape in ("diamond", "hexagon", "trapezoid", "trapezoid-alt")
                _align = "center" if _center_shapes else "flex-start"
                _text_align = "center" if _center_shapes else "left"
                parts.append(
                    f'<div class="node node-{_h(n.shape)}{extra_cls}" style="'
                    f'position:absolute; left:{n.x}px; top:{n.y}px; '
                    f'width:var(--node-w,{NODE_W}px); min-height:{node_h}px; '
                    f'min-width:{NODE_W}px; '
                    f'padding:var(--node-pad-v,12px) var(--node-pad-h,12px); '
                    f'box-sizing:border-box; overflow:hidden; '
                    f'{_border_css} '
                    f'{shape_css} '
                    f'background:linear-gradient({_depth_wash},{_depth_wash}),linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from,#ffffff)),var(--node-bg-to,var(--card-bg-to,#F7F6F2))); '
                    f'box-shadow:var(--node-shadow,0 1px 2px rgba(25,26,23,0.06),0 1px 0 rgba(25,26,23,0.03)); '
                    f'display:flex; flex-direction:column; align-items:{_align}; justify-content:center; '
                    f'text-align:{_text_align};">'
                    f'{inner}</div>'
                )

    # SVG overlay — paths and arrowheads only; edge labels as HTML siblings below.
    # clip-path:inset(0) keeps edges inside the diagram area so they cannot
    # bleed down into the legend strip when overflow:visible is set.
    parts.append(
        f'<svg style="position:absolute; inset:0; '
        f'width:{canvas_w}px; height:{canvas_h}px; '
        f'overflow:visible; clip-path:inset(-400px 0 0 0); pointer-events:none;">'
    )

    routed = _route_edges(nodes, edges, canvas_w, direction, group_bboxes=_grp_bboxes)

    # Collect which marker IDs are needed and emit a <defs> block.
    _needed_markers = {spec["marker_id"] for spec in routed if spec.get("marker_id")}
    if _needed_markers:
        defs_parts = ["<defs>"]
        if "arrow-normal" in _needed_markers:
            defs_parts.append(
                '<marker id="arrow-normal" viewBox="0 -4 9 8" refX="9" refY="0"'
                ' markerWidth="9" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">'
                '<polygon points="0,-4 9,0 0,4"'
                ' fill="var(--edge,rgba(100,116,139,0.7))"/></marker>'
            )
        if "arrow-thick" in _needed_markers:
            defs_parts.append(
                '<marker id="arrow-thick" viewBox="0 -5 11 10" refX="11" refY="0"'
                ' markerWidth="11" markerHeight="10" markerUnits="userSpaceOnUse" orient="auto">'
                '<polygon points="0,-5 11,0 0,5"'
                ' fill="var(--edge-strong,var(--accent-1,#60a5fa))"/></marker>'
            )
        if "arrow-open" in _needed_markers:
            defs_parts.append(
                '<marker id="arrow-open" viewBox="0 -4 9 8" refX="9" refY="0"'
                ' markerWidth="9" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">'
                '<path d="M 0,-4 L 9,0 L 0,4" fill="none"'
                ' stroke="var(--accent-4,var(--amber,#E8924A))" stroke-width="1.5"/></marker>'
            )
        _cls_edge = "var(--edge,rgba(100,116,139,0.7))"
        if "cls-inherit" in _needed_markers:
            defs_parts.append(
                f'<marker id="cls-inherit" viewBox="0 -6 12 12" refX="12" refY="0"'
                f' markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto">'
                f'<polygon points="0,-6 12,0 0,6" fill="none" stroke="{_cls_edge}" stroke-width="1.5"/></marker>'
            )
        if "cls-composition" in _needed_markers:
            defs_parts.append(
                f'<marker id="cls-composition" viewBox="-10 -5 20 10" refX="10" refY="0"'
                f' markerWidth="20" markerHeight="10" markerUnits="userSpaceOnUse" orient="auto">'
                f'<polygon points="0,0 -10,-4 -20,0 -10,4" fill="{_cls_edge}"/></marker>'
            )
        if "cls-aggregation" in _needed_markers:
            defs_parts.append(
                f'<marker id="cls-aggregation" viewBox="-10 -5 20 10" refX="10" refY="0"'
                f' markerWidth="20" markerHeight="10" markerUnits="userSpaceOnUse" orient="auto">'
                f'<polygon points="0,0 -10,-4 -20,0 -10,4" fill="none" stroke="{_cls_edge}" stroke-width="1.5"/></marker>'
            )
        if "cls-dep" in _needed_markers:
            defs_parts.append(
                f'<marker id="cls-dep" viewBox="0 -4 9 8" refX="9" refY="0"'
                f' markerWidth="9" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">'
                f'<path d="M 0,-4 L 9,0 L 0,4" fill="none" stroke="{_cls_edge}" stroke-width="1.5"/></marker>'
            )
        defs_parts.append("</defs>")
        parts.append("".join(defs_parts))

    for spec in routed:
        d = spec["d"]
        style = spec["style"]
        if style == "thick":
            stroke_color = "var(--edge-strong,var(--accent-1,#60a5fa))"
        elif style in ("dotted",) or style.endswith("-dotted"):
            stroke_color = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"
        else:
            stroke_color = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"
        if style == "dotted":
            stroke_color = "var(--accent-4,var(--amber,#E8924A))"
        is_dashed = style == "dotted" or style.endswith("-dotted")
        dash = ' stroke-dasharray="6 4"' if is_dashed else ""
        stroke_w = "2" if style == "thick" else "1.5"
        mid = spec.get("marker_id")
        marker_attr = f' marker-end="url(#{mid})"' if mid else ""
        parts.append(
            f'<path d="{d}" stroke="{stroke_color}" fill="none" '
            f'stroke-width="{stroke_w}"{dash}{marker_attr}/>'
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
                f'font-size:12px; font-weight:500; '
                f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif)); '
                f'color:var(--node-fg-dim,var(--text-secondary,#75736C)); '
                f'background:var(--edge-label-bg,#F7F6F2); '
                f'padding:1px 4px; border-radius:3px; '
                f'max-width:450px; overflow:hidden; '
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


# ── theme system ──────────────────────────────────────────────────────────────

THEME_DARK: dict[str, str] = {
    "--card-bg-from":   "#161d2e",
    "--card-bg-to":     "#0f1422",
    "--card-border":    "#2a3447",
    "--text-primary":   "#e8eef7",
    "--text-secondary": "#94a3b8",
    "--accent-1":       "#60a5fa",
    "--accent-2":       "#34d399",
    "--accent-3":       "#f472b6",
    "--accent-4":       "#fbbf24",
    "--bg-primary":     "#0d1117",
    "--edge-label-bg":  "#1a2235",
    "--font-primary":   "-apple-system,Inter,sans-serif",
}
"""CSS variable values for the dark theme."""

THEME_LIGHT: dict[str, str] = {
    "--card-bg-from":   "#ffffff",
    "--card-bg-to":     "#F7F6F2",
    "--card-border":    "#DAD7CE",
    "--text-primary":   "#191A17",
    "--text-secondary": "#75736C",
    "--accent-1":       "#3F7D5A",   # emerald — primary group
    "--accent-2":       "#6B4A7A",   # violet  — secondary group
    "--accent-3":       "#B7791F",   # amber   — tertiary group
    "--accent-4":       "#1F3A5F",   # sky     — quaternary group
    "--bg-primary":     "#F7F6F2",
    "--edge-label-bg":  "#F7F6F2",
    "--font-primary":   "-apple-system,Inter,sans-serif",
    "--node-shadow":    "0 1px 2px rgba(25,26,23,0.06),0 1px 0 rgba(25,26,23,0.03)",
    "--node-radius":    "10px",
    "--group-radius":   "10px",
}
"""CSS variable values for the light theme."""


def make_page(fragment: str, theme: str = "auto") -> str:
    """Wrap a diagram HTML fragment in a full standalone HTML page with CSS variables.

    theme: 'dark' | 'light' | 'auto'
    'auto' defaults to dark and switches to light via prefers-color-scheme media query.
    """
    def _vars(d: dict[str, str]) -> str:
        return "\n".join(f"    {k}: {v};" for k, v in d.items())

    if theme == "light":
        root_css = f":root {{\n{_vars(THEME_LIGHT)}\n  }}"
    elif theme == "dark":
        root_css = f":root {{\n{_vars(THEME_DARK)}\n  }}"
    else:
        root_css = (
            f":root {{\n{_vars(THEME_DARK)}\n  }}\n"
            f"  @media (prefers-color-scheme: light) {{\n"
            f"    :root {{\n{_vars(THEME_LIGHT)}\n    }}\n"
            f"  }}"
        )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<style>\n"
        f"  {root_css}\n"
        "  body { margin: 0; padding: 24px;\n"
        "    background: var(--bg-primary, #F7F6F2);\n"
        "    font-family: var(--font-primary, -apple-system, Inter, sans-serif); }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{fragment}\n"
        "</body>\n"
        "</html>"
    )


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
        'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif));">'
    )
    if type_label:
        parts.append(
            f'<span class="diagram-type-chip" style="'
            f'border:1px solid var(--node-fg-dim,var(--text-secondary,#75736C)); '
            f'border-radius:4px; padding:1px 6px; '
            f'font-size:9px; font-weight:700; letter-spacing:0.07em; '
            f'text-transform:uppercase; '
            f'color:var(--node-fg-dim,var(--text-secondary,#75736C));">'
            f'{_h(type_label)}</span>'
        )
    if title:
        parts.append(
            f'<span class="diagram-title" style="'
            f'font-size:11px; font-weight:600; '
            f'color:var(--node-fg,var(--text-primary,#191A17));">'
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
            'stroke="var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))" stroke-width="1.5"/>'
            '<polygon points="20,5 15,2.5 15,7.5" '
            'fill="var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"/>'
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
            'stroke="var(--edge-strong,var(--accent-1,#60a5fa))" stroke-width="2.5"/>'
            '<polygon points="20,5 15,2.5 15,7.5" '
            'fill="var(--edge-strong,var(--accent-1,#60a5fa))"/>'
            '</svg>'
            'Critical path</span>'
        )
    if has_groups:
        items.append(
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<svg width="20" height="10">'
            '<rect x="0" y="1" width="20" height="8" rx="2" '
            'fill="none" stroke="var(--accent-1,#60a5fa)" '
            'stroke-dasharray="3 2" stroke-width="1"/>'
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
        'border-top:1px solid var(--node-fg-dim,var(--card-border,#DAD7CE)); '
        'margin-top:0; '
        'font-size:10px; font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif)); '
        'color:var(--node-fg-dim,var(--text-secondary,#75736C));">'
        f'{joined}'
        '</div>'
    )


# ── group overlap resolution ─────────────────────────────────────────────────

def _is_nested_groups(gid1: str, gid2: str, groups: dict) -> bool:
    """Return True if gid1 and gid2 are in a parent-child relationship (either direction)."""
    cur = groups[gid2].parent_group
    while cur:
        if cur == gid1:
            return True
        cur = groups[cur].parent_group if cur in groups else None
    cur = groups[gid1].parent_group
    while cur:
        if cur == gid2:
            return True
        cur = groups[cur].parent_group if cur in groups else None
    return False


def _separate_groups_lr(
    nodes: dict[str, "_Node"],
    groups: dict[str, "_Group"],
) -> None:
    """Iteratively push overlapping group bounding boxes apart vertically (LR mode only).

    When two groups overlap in both x and y, the lower group is shifted down by the
    overlap depth + COL_GAP. Runs up to GROUP_CAP passes; stops early when stable.
    Skips parent-child group pairs — nested subgraphs are expected to overlap.
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
                if _is_nested_groups(gid1, gid2, groups):
                    continue
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
                if _is_nested_groups(gid1, gid2, groups):
                    continue
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


def _push_nonmembers_out_of_groups_lr(
    nodes: dict[str, "_Node"],
    groups: dict[str, "_Group"],
) -> None:
    """LR mode only: shift non-member nodes that land inside a group's bbox downward.

    Called after _separate_groups_lr and _assign_coordinates so that when a
    non-member node ends up at the same rank (x position) as a group member,
    it is moved below the group's padded bottom edge instead of visually
    appearing inside the group boundary.

    Iterates until stable (at most GROUP_CAP passes).
    """
    member_ids = {nid for grp in groups.values() for nid in grp.members}

    def _grp_bbox(gid: str) -> dict | None:
        mbrs = [nodes[m] for m in groups[gid].members if m in nodes and not nodes[m].is_dummy]
        if not mbrs:
            return None
        return {
            "x0":  min(n.x for n in mbrs) - GROUP_PAD_X,
            "x1":  max(n.x + NODE_W for n in mbrs) + GROUP_PAD_X,
            "y0":  min(n.y for n in mbrs) - GROUP_PAD_Y_TOP,
            "y1":  max(n.y + _node_render_h(n) for n in mbrs) + GROUP_PAD_Y_BOT,
        }

    for _pass in range(GROUP_CAP):
        moved = False
        bboxes = {gid: _grp_bbox(gid) for gid in groups}
        bboxes = {gid: b for gid, b in bboxes.items() if b is not None}
        if not bboxes:
            break
        # Process non-members sorted top-to-bottom so earlier shifts don't invalidate later checks
        nm_nodes = sorted(
            [(nid, n) for nid, n in nodes.items() if not n.is_dummy and nid not in member_ids],
            key=lambda x: x[1].y,
        )
        for nid, nd in nm_nodes:
            nx0, ny0 = nd.x, nd.y
            nx1, ny1 = nd.x + NODE_W, nd.y + _node_render_h(nd)
            for gid, b in bboxes.items():
                if not (b["x0"] < nx1 and nx0 < b["x1"] and b["y0"] < ny1 and ny0 < b["y1"]):
                    continue
                # Non-member overlaps group bbox — push it below the group
                nd.y = int(b["y1"] + COL_GAP)
                moved = True
                # Recompute this group's bbox since nd.y changed (nd is non-member, no effect)
                break
        if not moved:
            break


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
    def _recursive_members(gid: str) -> list[str]:
        """Collect all member node IDs including those in nested child groups."""
        result = list(groups[gid].members)
        for child_gid, child_grp in groups.items():
            if child_grp.parent_group == gid:
                result.extend(_recursive_members(child_gid))
        return result

    bboxes: dict[str, list[float]] = {}
    for gid in groups:
        all_mbr_ids = _recursive_members(gid)
        mbrs = [nodes[m] for m in all_mbr_ids if m in nodes and not nodes[m].is_dummy]
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

    # Pre-compute member coordinate extremes per group for shrink-safety checks.
    # A shrink is "safe" only if no group member falls outside the new edge position.
    _grp_mc: dict[str, dict] = {}
    for gid, grp in groups.items():
        mbrs = [nodes[m] for m in grp.members if m in nodes and not nodes[m].is_dummy]
        if mbrs:
            _grp_mc[gid] = {
                "x0": min(m.x for m in mbrs),
                "x1": max(m.x + NODE_W for m in mbrs),
                "y0": min(m.y for m in mbrs),
                "y1": max(m.y + _node_render_h(m) for m in mbrs),
            }

    # Step 2: non-member node exclusion — shrink the closest group edge, but only
    # when the shrink won't exclude any group member. If no safe direction exists,
    # accept the visual overlap rather than corrupting the group bbox.
    for nid, nd in nodes.items():
        if nd.is_dummy or nid in member_ids:
            continue
        nx0, ny0 = float(nd.x), float(nd.y)
        nx1, ny1 = float(nd.x + NODE_W), float(nd.y + _node_render_h(nd))
        for gid, b in bboxes.items():
            if not (b[0] < nx1 and nx0 < b[2] and b[1] < ny1 and ny0 < b[3]):
                continue
            mc = _grp_mc.get(gid, {})
            # A shrink is safe if it doesn't push the edge past any member coord
            def _safe(axis: str, new_val: float) -> bool:
                if not mc:
                    return True
                if axis == "x0":  # raise left edge
                    return mc["x0"] >= new_val
                if axis == "x1":  # lower right edge
                    return mc["x1"] <= new_val
                if axis == "y0":  # raise top edge
                    return mc["y0"] >= new_val
                if axis == "y1":  # lower bottom edge
                    return mc["y1"] <= new_val
                return True
            x_intrude = min(nx1 - b[0], b[2] - nx0)
            y_intrude = min(ny1 - b[1], b[3] - ny0)
            # Try directions in order of preference (closest intrusion first,
            # then opposite axis). Accept overlap if no direction is safe.
            if x_intrude <= y_intrude:
                if nx0 < (b[0] + b[2]) / 2:
                    new_x0 = nx1 + _NM_GAP
                    if _safe("x0", new_x0):
                        b[0] = new_x0
                    elif _safe("y0", ny1 + _NM_GAP):
                        b[1] = ny1 + _NM_GAP
                    elif _safe("y1", ny0 - _NM_GAP):
                        b[3] = ny0 - _NM_GAP
                    # else: accept overlap
                else:
                    new_x1 = nx0 - _NM_GAP
                    if _safe("x1", new_x1):
                        b[2] = new_x1
                    elif _safe("y0", ny1 + _NM_GAP):
                        b[1] = ny1 + _NM_GAP
                    elif _safe("y1", ny0 - _NM_GAP):
                        b[3] = ny0 - _NM_GAP
                    # else: accept overlap
            else:
                if ny0 < (b[1] + b[3]) / 2:
                    new_y0 = ny1 + _NM_GAP
                    if _safe("y0", new_y0):
                        b[1] = new_y0
                    elif _safe("x1", nx0 - _NM_GAP):
                        b[2] = nx0 - _NM_GAP
                    elif _safe("x0", nx1 + _NM_GAP):
                        b[0] = nx1 + _NM_GAP
                    # else: accept overlap
                else:
                    new_y1 = ny0 - _NM_GAP
                    if _safe("y1", new_y1):
                        b[3] = new_y1
                    elif _safe("x1", nx0 - _NM_GAP):
                        b[2] = nx0 - _NM_GAP
                    elif _safe("x0", nx1 + _NM_GAP):
                        b[0] = nx1 + _NM_GAP
                    # else: accept overlap

    # Step 3: pairwise overlap resolution (iterative, up to GROUP_CAP passes)
    # Skip nested pairs — their bboxes overlap by design (parent wraps child).
    gids = list(bboxes)
    for _ in range(GROUP_CAP):
        changed = False
        for i, g1 in enumerate(gids):
            b1 = bboxes[g1]
            for g2 in gids[i + 1:]:
                if _is_nested_groups(g1, g2, groups):
                    continue
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

