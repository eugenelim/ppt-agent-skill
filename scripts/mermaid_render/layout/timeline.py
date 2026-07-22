"""mermaid_render.layout.timeline — Native timeline scene builder.

Column layout: tasks left-to-right, events stacked below each task column.
Each period is a column; its events stack vertically below the period chip.
Section bands span their periods, rendered above the spine.
"""
from __future__ import annotations

import hashlib
from typing import NamedTuple, Optional

from ..scene import (
    AccessibilityMetadata,
    FillStyle,
    LAYER_BACKGROUND,
    LAYER_BOUNDARIES,
    LAYER_EDGES,
    LAYER_LABELS,
    LAYER_NODES,
    LAYER_NOTES,
    LAYER_OVERLAYS,
    LAYER_ORDER,
    MarkerDefinition,
    PaintStyle,
    SceneCircle,
    SceneLine,
    SceneRoundedRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)
from ._geometry import TextLayout, TextStyle
from ._text import get_default_measurer


# ── Layout constants ──────────────────────────────────────────────────────────

_COL_W: int = 112          # retained for test import; col_w is derived from measurement
_MIN_COL_W: float = 64.0   # absolute minimum column width
_COL_GAP: int = 12         # gap between columns
_EVENT_GAP: int = 4        # vertical gap between event cards
_EVENT_PAD_TOP: int = 6    # gap from period chip bottom to first event
_SPINE_DOT_GAP: int = 6    # gap from spine to top of period chip
_MARKER_R: int = 5         # spine dot radius
_PAD_H: int = 40           # horizontal canvas padding
_PAD_V: int = 24           # vertical canvas padding

# Font sizes for each text role
_PERIOD_FS: float = 11.0
_EVENT_FS: float = 10.0
_SECTION_FS: float = 9.0

# Vertical padding inside each chip (top + bottom per side)
_PERIOD_CHIP_PAD: float = 6.0
_EVENT_CHIP_PAD: float = 4.0
_SECTION_CHIP_PAD: float = 4.0

_SECTION_COLORS: tuple[str, ...] = (
    "rgba(96,165,250,0.10)",
    "rgba(52,211,153,0.10)",
    "rgba(251,191,36,0.10)",
    "rgba(167,139,250,0.10)",
    "rgba(248,113,113,0.10)",
)
_SECTION_COLOR_MONO = "rgba(148,163,184,0.10)"


# ── Theme tokens ──────────────────────────────────────────────────────────────

class _TimelineTokens(NamedTuple):
    """Color tokens for timeline rendering. Hardcoded defaults match THEME_ADAPTIVE_LIGHT."""
    spine_stroke: str = "#94a3b8"
    dot_fill: str = "#60a5fa"
    dot_stroke: str = "#ffffff"
    connector_stroke: str = "#94a3b8"
    node_fill: str = "#f7f6f2"
    node_stroke: str = "#dad7ce"
    text_color: str = "#191a17"
    dim_color: str = "#75736c"
    title_color: str = "#111827"


def _tokens_from_theme(theme: Optional[dict]) -> _TimelineTokens:
    """Populate _TimelineTokens from a CSS-var-keyed theme dict; fall back to defaults."""
    d = _TimelineTokens()
    if not theme:
        return d
    return _TimelineTokens(
        spine_stroke=theme.get("--text-secondary", d.spine_stroke),
        dot_fill=theme.get("--accent-1", d.dot_fill),
        dot_stroke=d.dot_stroke,
        connector_stroke=theme.get("--text-secondary", d.connector_stroke),
        node_fill=theme.get("--card-bg-to", d.node_fill),
        node_stroke=theme.get("--card-border", d.node_stroke),
        text_color=theme.get("--text-primary", d.text_color),
        dim_color=theme.get("--text-secondary", d.dim_color),
        title_color=theme.get("--text-primary", d.title_color),
    )


# ── Text helpers ──────────────────────────────────────────────────────────────

def _chip_text_lines(
    layout: TextLayout,
    box_x: float,
    box_y: float,
    box_w: float,
    box_h: float,
    font_size: float,
    font_weight: int,
    color: str,
    anchor: str = "middle",
) -> tuple[SceneTextLine, ...]:
    """Convert a TextLayout into SceneTextLines vertically centered within a chip box."""
    start_y = box_y + (box_h - layout.height) / 2.0
    if anchor == "middle":
        text_x = box_x + box_w / 2.0
    else:
        text_x = box_x + _EVENT_CHIP_PAD

    result: list[SceneTextLine] = []
    cum_y = start_y
    for line in layout.lines:
        line_text = " ".join(run.text for run in line.runs)
        result.append(SceneTextLine(
            text=line_text,
            x=text_x,
            y=cum_y + line.baseline,
            font_size=font_size,
            font_weight=font_weight,
            fill_color=color,
        ))
        cum_y += line.height
    return tuple(result)


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_timeline_source(src: str) -> tuple[str, list, list]:
    """Return (title, groups, all_periods).

    groups: list of {"name": str|None, "periods": list[{"period", "events"}]}
    all_periods: flat list of {"period", "events", "section", "g_idx"}
    """
    lines = src.splitlines()
    content_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith(("%%", "//")):
            content_start = i + 1
            break

    title = ""
    groups: list[dict] = [{"name": None, "periods": []}]
    current_period: Optional[dict] = None

    for raw in lines[content_start:]:
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
        if line.startswith(":"):
            evt = line[1:].strip()
            if current_period is not None and evt:
                current_period["events"].append(evt)
            continue
        if " : " in line:
            period_name, first_event = line.split(" : ", 1)
            current_period = {"period": period_name.strip(), "events": [first_event.strip()]}
        else:
            current_period = {"period": line, "events": []}
        groups[-1]["periods"].append(current_period)

    all_periods: list[dict] = []
    for g_idx, grp in enumerate(groups):
        for p in grp["periods"]:
            all_periods.append({
                "period": p["period"],
                "events": list(p["events"]),
                "section": grp["name"],
                "g_idx": g_idx,
            })

    return title, groups, all_periods


# ── Scene builders ────────────────────────────────────────────────────────────

def layout_timeline_scene(
    src: str,
    *,
    width_hint: int = 0,
    diagram_config: Optional[dict] = None,
    theme: Optional[dict] = None,
) -> SvgScene:
    """Parse timeline source and return a column-layout SvgScene.

    Column layout: periods go left-to-right; events stack below each period.
    Section bands span their periods above the spine.

    width_hint: maximum output width in pixels (0 = unconstrained / content-tight).
    diagram_config: parsed %%{init:...}%% config; used for disableMulticolor.
    theme: CSS-var-keyed color dict (e.g. THEME_ADAPTIVE_LIGHT); falls back to defaults.
    """
    title, groups, all_periods = _parse_timeline_source(src)

    if not all_periods:
        raise ValueError("No periods found in timeline.")

    n = len(all_periods)

    # ── Text measurement ─────────────────────────────────────────────────────
    measurer = get_default_measurer()
    tokens = _tokens_from_theme(theme)

    period_style = TextStyle(font_size=_PERIOD_FS, font_weight=700)
    event_style = TextStyle(font_size=_EVENT_FS, font_weight=500)
    section_style = TextStyle(font_size=_SECTION_FS, font_weight=700)

    # Derive col_w from the widest period label (unconstrained measurement)
    period_ideal_widths = [
        measurer.layout(p["period"], period_style, None).width
        for p in all_periods
    ]
    col_w_from_text = max(period_ideal_widths, default=0.0) + 2.0 * _PERIOD_CHIP_PAD + 4.0
    col_w = max(_MIN_COL_W, col_w_from_text)

    # ── Config ───────────────────────────────────────────────────────────────
    cfg = diagram_config or {}
    timeline_cfg = cfg.get("timeline", {})
    if not isinstance(timeline_cfg, dict):
        timeline_cfg = {}
    disable_multicolor = bool(timeline_cfg.get("disableMulticolor", False))

    title_h = 28 if title else 0

    # ── Width: content-tight; width_hint is an output-maximum constraint ──────
    natural_w = _PAD_H * 2 + n * col_w + max(0, n - 1) * _COL_GAP
    if width_hint > 0 and width_hint < natural_w:
        canvas_w = float(width_hint)
        available_w = canvas_w - _PAD_H * 2
        col_stride = available_w / n if n > 0 else col_w + _COL_GAP
        col_w = max(40.0, col_stride - _COL_GAP)
    else:
        canvas_w = float(natural_w)
        col_stride = col_w + _COL_GAP

    # ── Measure period chips (per-period) ────────────────────────────────────
    period_text_pad = col_w - 2.0 * _PERIOD_CHIP_PAD
    period_layouts: list[TextLayout] = [
        measurer.layout(p["period"], period_style, max(1.0, period_text_pad))
        for p in all_periods
    ]
    period_heights = [lay.height + 2.0 * _PERIOD_CHIP_PAD for lay in period_layouts]

    # ── Measure event cards (per-event) and compute per-column events_h ──────
    event_text_pad = col_w - 2.0 * _EVENT_CHIP_PAD
    # event_layouts[i][j] = layout for column i, event j
    event_layouts: list[list[TextLayout]] = []
    for p in all_periods:
        col_layouts = [
            measurer.layout(ev, event_style, max(1.0, event_text_pad))
            for ev in p["events"]
        ]
        event_layouts.append(col_layouts)

    event_heights: list[list[float]] = [
        [lay.height + 2.0 * _EVENT_CHIP_PAD for lay in col]
        for col in event_layouts
    ]

    # Per-column total events block height
    col_events_h: list[float] = []
    for i, heights in enumerate(event_heights):
        if heights:
            col_events_h.append(
                _EVENT_PAD_TOP + sum(heights) + max(0, len(heights) - 1) * _EVENT_GAP
            )
        else:
            col_events_h.append(0.0)

    # Section band height (single line — section labels never wrap)
    section_line_h = measurer.layout("Aq", section_style, None).line_height
    section_band_h = section_line_h + 2.0 * _SECTION_CHIP_PAD
    has_sections = any(grp["name"] for grp in groups)
    sec_h = section_band_h if has_sections else 0.0

    # Vertical layout:
    #   PAD_V + title_h + sec_h → spine_y
    #   spine_y + SPINE_DOT_GAP + tallest(period_h + events_h) + PAD_V → canvas_h
    spine_y = float(_PAD_V + title_h + sec_h)
    max_col_content = max(
        (
            period_heights[i] + col_events_h[i]
            for i in range(n)
        ),
        default=0.0,
    )
    canvas_h = float(spine_y + _SPINE_DOT_GAP + max_col_content + _PAD_V)

    content = f"timeline:{canvas_w}:{canvas_h}:{','.join(p['period'] for p in all_periods)}"
    content_hash = int(hashlib.sha256(content.encode()).hexdigest(), 16)
    scene_id = make_scene_id("timeline", content_hash)
    eid = hashlib.sha256(scene_id.encode()).hexdigest()[:6]

    bg_elements: list = []
    boundary_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []
    overlay_elements: list = []

    # Title
    if title:
        label_elements.append(SceneText(
            element_id=f"{eid}-title",
            lines=(SceneTextLine(
                text=title,
                x=float(_PAD_H),
                y=float(_PAD_V + 16),
                font_size=13.0,
                font_weight=700,
                fill_color=tokens.title_color,
            ),),
            text_anchor="start",
        ))

    # Section bands: horizontal band above the spine spanning each section's columns
    g_period_cols: dict[int, list[int]] = {}
    for col_i, p in enumerate(all_periods):
        g_period_cols.setdefault(p["g_idx"], []).append(col_i)

    if has_sections:
        sec_color_idx = 0
        for grp in groups:
            g_idx = groups.index(grp)
            cols = g_period_cols.get(g_idx, [])
            if not cols:
                if grp["name"]:
                    sec_color_idx += 1
                continue
            bx = float(_PAD_H + min(cols) * col_stride)
            bw = float((max(cols) - min(cols) + 1) * col_stride - _COL_GAP)
            band_y = float(_PAD_V + title_h)
            band_h = float(sec_h)

            if disable_multicolor:
                color = _SECTION_COLOR_MONO
            else:
                color = _SECTION_COLORS[sec_color_idx % len(_SECTION_COLORS)]
            if grp["name"]:
                sec_color_idx += 1

            boundary_elements.append(SceneRoundedRect(
                element_id=f"{eid}-band-{g_idx}",
                x=bx, y=band_y, w=bw, h=band_h,
                rx=3, ry=3,
                paint=PaintStyle(fill=FillStyle(color=color)),
                css_classes=("timeline-section-band",),
            ))

            if grp["name"]:
                label_elements.append(SceneText(
                    element_id=f"{eid}-sec-lbl-{g_idx}",
                    lines=(SceneTextLine(
                        text=grp["name"].upper(),
                        x=bx + 6,
                        y=band_y + sec_h / 2.0 + 0.35 * _SECTION_FS,
                        font_size=_SECTION_FS,
                        font_weight=700,
                        fill_color=tokens.dim_color,
                    ),),
                    text_anchor="start",
                    css_classes=("timeline-section-label",),
                ))

    # Spine: horizontal line at spine_y from first to last period center
    cx_first = float(_PAD_H + col_stride / 2)
    cx_last = float(_PAD_H + (n - 1) * col_stride + col_stride / 2)
    spine_marker_id = f"{eid}-spine-arrow"
    edge_elements.append(SceneLine(
        element_id=f"{eid}-spine",
        x1=cx_first - _MARKER_R - 4, y1=spine_y,
        x2=cx_last + _MARKER_R + 4, y2=spine_y,
        paint=PaintStyle(stroke=StrokeStyle(color=tokens.spine_stroke, width=2.0)),
        css_classes=("timeline-spine",),
        marker_end=spine_marker_id,
    ))

    # Per-period column: dot on spine, connector, period chip, event cards
    for i, p in enumerate(all_periods):
        cx = float(_PAD_H + i * col_stride + col_stride / 2)
        col_left = cx - col_w / 2

        # Spine dot
        overlay_elements.append(SceneCircle(
            element_id=f"{eid}-dot-{i}",
            cx=cx, cy=spine_y, r=float(_MARKER_R),
            paint=PaintStyle(
                fill=FillStyle(color=tokens.dot_fill),
                stroke=StrokeStyle(color=tokens.dot_stroke, width=2.0),
            ),
            css_classes=("timeline-dot",),
            data_attrs=(("period", p["period"]),),
        ))

        # Vertical connector from dot to period chip
        period_top = spine_y + _SPINE_DOT_GAP
        edge_elements.append(SceneLine(
            element_id=f"{eid}-con-{i}",
            x1=cx, y1=spine_y + _MARKER_R,
            x2=cx, y2=period_top,
            paint=PaintStyle(stroke=StrokeStyle(
                color=tokens.connector_stroke, width=1.0, dasharray="3 3",
            )),
            css_classes=("timeline-connector",),
        ))

        # Period chip — height derived from measured label
        p_h = period_heights[i]
        node_elements.append(SceneRoundedRect(
            element_id=f"{eid}-period-{i}",
            x=col_left, y=period_top,
            w=float(col_w), h=float(p_h),
            rx=4, ry=4,
            paint=PaintStyle(
                fill=FillStyle(color=tokens.node_fill),
                stroke=StrokeStyle(color=tokens.node_stroke, width=1.0),
            ),
            css_classes=("timeline-period",),
            data_attrs=(("period", p["period"]),),
        ))
        label_elements.append(SceneText(
            element_id=f"{eid}-period-lbl-{i}",
            lines=_chip_text_lines(
                period_layouts[i],
                col_left, period_top, col_w, p_h,
                _PERIOD_FS, 700, tokens.text_color, "middle",
            ),
            text_anchor="middle",
            css_classes=("timeline-period-label",),
        ))

        # Event cards stacked below the period chip (in-column)
        ev_top = period_top + p_h + _EVENT_PAD_TOP
        for j, ev in enumerate(p["events"]):
            e_h = event_heights[i][j]
            node_elements.append(SceneRoundedRect(
                element_id=f"{eid}-ev-{i}-{j}",
                x=col_left, y=float(ev_top),
                w=float(col_w), h=float(e_h),
                rx=3, ry=3,
                paint=PaintStyle(
                    fill=FillStyle(color=tokens.node_fill),
                    stroke=StrokeStyle(color=tokens.node_stroke, width=1.0),
                ),
                css_classes=("timeline-event",),
                data_attrs=(("col", str(i)),),
            ))
            label_elements.append(SceneText(
                element_id=f"{eid}-ev-lbl-{i}-{j}",
                lines=_chip_text_lines(
                    event_layouts[i][j],
                    col_left, ev_top, col_w, e_h,
                    _EVENT_FS, 500, tokens.text_color, "middle",
                ),
                text_anchor="middle",
                css_classes=("timeline-event-label",),
            ))
            ev_top += e_h + _EVENT_GAP

    # Spine arrowhead marker definition
    spine_marker = MarkerDefinition(
        marker_id=spine_marker_id,
        marker_type="timeline-end",
        color=tokens.spine_stroke,
        size=6.0,
        refX=6.0,
        refY=3.0,
    )

    layers = tuple(
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
        diagram_type="timeline",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=title or "timeline",
            description="Mermaid timeline diagram",
        ),
        definitions=(spine_marker,),
        layers=layers,
    )
