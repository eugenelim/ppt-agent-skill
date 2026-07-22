"""mermaid_render.layout.timeline — Native timeline scene builder.

Column layout: tasks left-to-right, events stacked below each task column.
Each period is a column; its events stack vertically below the period chip.
Section bands span their periods, rendered above the spine.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from ..scene import (
    AccessibilityMetadata,
    FillStyle,
    LAYER_BACKGROUND,
    LAYER_BOUNDARIES,
    LAYER_EDGES,
    LAYER_LABELS,
    LAYER_NODES,
    LAYER_NOTES,
    LAYER_ORDER,
    LAYER_OVERLAYS,
    PaintStyle,
    SceneCircle,
    SceneLine,
    SceneRect,
    SceneRoundedRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)
from ._geometry import TextStyle
from ._text import get_default_measurer


# ── Layout constants ──────────────────────────────────────────────────────────

_COL_W: int = 112          # natural width of each period column
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

_SPINE_STROKE = "#94a3b8"
_DOT_FILL = "#60a5fa"
_DOT_STROKE = "#ffffff"
_CONNECTOR_STROKE = "#94a3b8"
_NODE_FILL = "#f7f6f2"
_NODE_STROKE = "#dad7ce"
_TEXT_COLOR = "#191a17"
_DIM_COLOR = "#75736c"
_TITLE_COLOR = "#111827"


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
) -> SvgScene:
    """Parse timeline source and return a column-layout SvgScene.

    Column layout: periods go left-to-right; events stack below each period.
    Section bands span their periods above the spine.

    width_hint: maximum output width in pixels (0 = unconstrained / content-tight).
    diagram_config: parsed %%{init:...}%% config; used for disableMulticolor.
    """
    title, groups, all_periods = _parse_timeline_source(src)

    if not all_periods:
        raise ValueError("No periods found in timeline.")

    n = len(all_periods)

    # ── Text measurement ─────────────────────────────────────────────────────
    measurer = get_default_measurer()

    period_style = TextStyle(font_size=_PERIOD_FS, font_weight=700)
    event_style = TextStyle(font_size=_EVENT_FS, font_weight=500)
    section_style = TextStyle(font_size=_SECTION_FS, font_weight=700)

    # Use "Aq" as a representative string to measure actual font cap+descender height
    period_line_h = measurer.layout("Aq", period_style, None).line_height
    event_line_h = measurer.layout("Aq", event_style, None).line_height
    section_line_h = measurer.layout("Aq", section_style, None).line_height

    period_h = period_line_h + 2.0 * _PERIOD_CHIP_PAD
    event_h = event_line_h + 2.0 * _EVENT_CHIP_PAD
    section_band_h = section_line_h + 2.0 * _SECTION_CHIP_PAD

    # ── Config ───────────────────────────────────────────────────────────────
    cfg = diagram_config or {}
    timeline_cfg = cfg.get("timeline", {})
    if not isinstance(timeline_cfg, dict):
        timeline_cfg = {}
    disable_multicolor = bool(timeline_cfg.get("disableMulticolor", False))

    title_h = 28 if title else 0

    max_events = max((len(p["events"]) for p in all_periods), default=0)
    events_h = (
        _EVENT_PAD_TOP + max_events * event_h + max(0, max_events - 1) * _EVENT_GAP
        if max_events > 0 else 0
    )

    # Determine whether any named sections exist
    has_sections = any(grp["name"] for grp in groups)
    sec_h = section_band_h if has_sections else 0.0

    # Vertical layout:
    #   PAD_V + title_h + sec_h → spine_y
    #   spine_y + SPINE_DOT_GAP + period_h + events_h + PAD_V → canvas_h
    spine_y = float(_PAD_V + title_h + sec_h)
    canvas_h = float(spine_y + _SPINE_DOT_GAP + period_h + events_h + _PAD_V)

    # ── Width: content-tight; width_hint is an output-maximum constraint ──────
    natural_w = _PAD_H * 2 + n * _COL_W + max(0, n - 1) * _COL_GAP
    if width_hint > 0 and width_hint < natural_w:
        canvas_w = float(width_hint)
        # Compress column widths to fit within the constrained canvas
        available_w = canvas_w - _PAD_H * 2
        col_stride = int(available_w // n) if n > 0 else _COL_W + _COL_GAP
        col_w = max(40, col_stride - _COL_GAP)
    else:
        # Content-tight: use natural width regardless of width_hint
        canvas_w = float(natural_w)
        col_stride = _COL_W + _COL_GAP
        col_w = _COL_W

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
                fill_color=_TITLE_COLOR,
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
                        fill_color=_DIM_COLOR,
                    ),),
                    text_anchor="start",
                    css_classes=("timeline-section-label",),
                ))

    # Spine: horizontal line at spine_y from first to last period center
    cx_first = float(_PAD_H + col_stride // 2)
    cx_last = float(_PAD_H + (n - 1) * col_stride + col_stride // 2)
    edge_elements.append(SceneLine(
        element_id=f"{eid}-spine",
        x1=cx_first - _MARKER_R - 4, y1=spine_y,
        x2=cx_last + _MARKER_R + 4, y2=spine_y,
        paint=PaintStyle(stroke=StrokeStyle(color=_SPINE_STROKE, width=2.0)),
        css_classes=("timeline-spine",),
    ))

    # Per-period column: dot on spine, connector, period chip, event cards
    for i, p in enumerate(all_periods):
        cx = float(_PAD_H + i * col_stride + col_stride // 2)
        col_left = cx - col_w / 2

        # Spine dot
        overlay_elements.append(SceneCircle(
            element_id=f"{eid}-dot-{i}",
            cx=cx, cy=spine_y, r=float(_MARKER_R),
            paint=PaintStyle(
                fill=FillStyle(color=_DOT_FILL),
                stroke=StrokeStyle(color=_DOT_STROKE, width=2.0),
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
                color=_CONNECTOR_STROKE, width=1.0, dasharray="3 3",
            )),
            css_classes=("timeline-connector",),
        ))

        # Period chip
        node_elements.append(SceneRoundedRect(
            element_id=f"{eid}-period-{i}",
            x=col_left, y=period_top,
            w=float(col_w), h=float(period_h),
            rx=4, ry=4,
            paint=PaintStyle(
                fill=FillStyle(color=_NODE_FILL),
                stroke=StrokeStyle(color=_NODE_STROKE, width=1.0),
            ),
            css_classes=("timeline-period",),
            data_attrs=(("period", p["period"]),),
        ))
        label_elements.append(SceneText(
            element_id=f"{eid}-period-lbl-{i}",
            lines=(SceneTextLine(
                text=p["period"],
                x=col_left + col_w / 2,
                y=period_top + period_h / 2 + 0.35 * _PERIOD_FS,
                font_size=_PERIOD_FS,
                font_weight=700,
                fill_color=_TEXT_COLOR,
            ),),
            text_anchor="middle",
            css_classes=("timeline-period-label",),
        ))

        # Event cards stacked below the period chip (in-column)
        for j, ev in enumerate(p["events"]):
            ev_top = period_top + period_h + _EVENT_PAD_TOP + j * (event_h + _EVENT_GAP)
            node_elements.append(SceneRoundedRect(
                element_id=f"{eid}-ev-{i}-{j}",
                x=col_left, y=float(ev_top),
                w=float(col_w), h=float(event_h),
                rx=3, ry=3,
                paint=PaintStyle(
                    fill=FillStyle(color=_NODE_FILL),
                    stroke=StrokeStyle(color=_NODE_STROKE, width=1.0),
                ),
                css_classes=("timeline-event",),
                data_attrs=(("col", str(i)),),
            ))
            label_elements.append(SceneText(
                element_id=f"{eid}-ev-lbl-{i}-{j}",
                lines=(SceneTextLine(
                    text=ev,
                    x=col_left + col_w / 2,
                    y=float(ev_top) + event_h / 2 + 0.35 * _EVENT_FS,
                    font_size=_EVENT_FS,
                    font_weight=500,
                    fill_color=_TEXT_COLOR,
                ),),
                text_anchor="middle",
                css_classes=("timeline-event-label",),
            ))

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
        layers=layers,
    )
