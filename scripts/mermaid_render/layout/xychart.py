"""mermaid_render.layout.xychart — Native xychart-beta scene builder.

Parses ``xychart-beta`` source and renders a bar chart with optional
overlaid line series and labelled axes.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from ..scene import (
    AccessibilityMetadata,
    FillStyle,
    LAYER_BACKGROUND,
    LAYER_EDGES,
    LAYER_LABELS,
    LAYER_NODES,
    LAYER_OVERLAYS,
    LAYER_ORDER,
    PaintStyle,
    Rotate,
    SceneCircle,
    SceneLine,
    ScenePath,
    SceneRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)


# ── Color tokens ──────────────────────────────────────────────────────────────

_BG_FILL = "#f8fafc"
_TITLE_COLOR = "#111827"
_BAR_FILL = "#60a5fa"
_BAR_STROKE = "#1d4ed8"
_LINE_STROKE = "#f59e0b"
_LINE_POINT_FILL = "#fbbf24"
_AXIS_STROKE = "#94a3b8"
_GRID_STROKE = "#e2e8f0"
_TEXT_COLOR = "#374151"
_AXIS_TEXT = "#6b7280"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD_LEFT = 56      # y-axis label space
_PAD_RIGHT = 24
_PAD_TOP = 16
_PAD_BOTTOM = 40    # x-axis label space
_TITLE_H = 30
_TITLE_FONT = 16
_FONT_SIZE = 11
_BAR_GAP_FRAC = 0.2   # fraction of bar slot width reserved for gap
_LINE_DOT_R = 4
_MIN_CHART_W = 400
_MIN_CHART_H = 200
_GRID_LINES = 5


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_list(s: str) -> list[str]:
    """Parse '[a, b, c]' → ['a', 'b', 'c']."""
    s = s.strip()
    if s.startswith("["):
        s = s[1:]
    if s.endswith("]"):
        s = s[:-1]
    return [item.strip().strip('"') for item in s.split(",") if item.strip()]


def _parse_xychart_source(src: str) -> tuple[str, str, list[str], float, float, list[float], list[float]]:
    """Return (title, y_label, x_cats, y_min, y_max, bar_data, line_data)."""
    title = ""
    y_label = ""
    x_cats: list[str] = []
    y_min = 0.0
    y_max = 100.0
    bar_data: list[float] = []
    line_data: list[float] = []

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("xychart") or stripped.startswith("%%"):
            continue

        if stripped.lower().startswith("title "):
            title = stripped[6:].strip().strip('"')
            continue
        if stripped.lower() == "title":
            continue

        # x-axis [cat1, cat2, ...]
        m = re.match(r'^x-axis\s+(.*)', stripped, re.IGNORECASE)
        if m:
            rest = m.group(1).strip()
            if "[" in rest:
                cats_str = rest[rest.index("["):]
                x_cats = _parse_list(cats_str)
            continue

        # y-axis ["label"] min --> max  OR  y-axis min --> max
        m = re.match(r'^y-axis\s+(.*)', stripped, re.IGNORECASE)
        if m:
            rest = m.group(1).strip()
            # Optional quoted label
            lm = re.match(r'^"([^"]*)"(.*)$', rest)
            if lm:
                y_label = lm.group(1)
                rest = lm.group(2).strip()
            # min --> max
            rm = re.match(r'([\d.]+)\s*-->\s*([\d.]+)', rest)
            if rm:
                y_min = float(rm.group(1))
                y_max = float(rm.group(2))
            continue

        # bar [values...]
        if stripped.lower().startswith("bar "):
            vals = _parse_list(stripped[4:])
            bar_data = [float(v) for v in vals if v]
            continue

        # line [values...]
        if stripped.lower().startswith("line "):
            vals = _parse_list(stripped[5:])
            line_data = [float(v) for v in vals if v]
            continue

    return title, y_label, x_cats, y_min, y_max, bar_data, line_data


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_xychart_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse xychart-beta source and return an SvgScene with bar/line chart."""
    title, y_label, x_cats, y_min, y_max, bar_data, line_data = _parse_xychart_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("xychart-beta", content_hash)

    # Determine number of categories
    n = max(len(x_cats), len(bar_data), len(line_data))
    if n == 0:
        w = max(width_hint or 400, 400)
        h = 200
        return SvgScene(
            scene_id=scene_id,
            diagram_type="xychart-beta",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title=title or "XY Chart"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    title_h = _TITLE_H if title else 0
    chart_w = max(width_hint - _PAD_LEFT - _PAD_RIGHT if width_hint else _MIN_CHART_W, _MIN_CHART_W)
    chart_h = max(_MIN_CHART_H, 300)
    canvas_w = float(chart_w + _PAD_LEFT + _PAD_RIGHT)
    canvas_h = float(chart_h + _PAD_TOP + _PAD_BOTTOM + title_h)

    chart_left = float(_PAD_LEFT)
    chart_top = float(_PAD_TOP + title_h)
    chart_right = chart_left + chart_w
    chart_bottom = chart_top + chart_h

    y_span = y_max - y_min if y_max != y_min else 1.0
    slot_w = chart_w / n
    bar_w = slot_w * (1.0 - _BAR_GAP_FRAC)
    bar_offset = slot_w * _BAR_GAP_FRAC / 2

    def _y_to_px(val: float) -> float:
        return chart_bottom - (val - y_min) / y_span * chart_h

    def _x_slot_center(idx: int) -> float:
        return chart_left + idx * slot_w + slot_w / 2

    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    overlay_elements: list = []
    label_elements: list = []

    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    if title:
        label_elements.append(SceneText(
            element_id=f"{scene_id}-title",
            lines=(SceneTextLine(
                text=title,
                x=canvas_w / 2,
                y=float(_PAD_TOP + _TITLE_FONT),
                font_size=float(_TITLE_FONT),
                font_weight=600,
                fill_color=_TITLE_COLOR,
            ),),
            text_anchor="middle",
        ))

    # Grid lines + y-axis labels
    for gi in range(_GRID_LINES + 1):
        gval = y_min + gi * y_span / _GRID_LINES
        gy = _y_to_px(gval)
        edge_elements.append(SceneLine(
            element_id=f"{scene_id}-grid-{gi}",
            x1=chart_left, y1=gy, x2=chart_right, y2=gy,
            paint=PaintStyle(stroke=StrokeStyle(color=_GRID_STROKE, width=0.5)),
        ))
        label_elements.append(SceneText(
            element_id=f"{scene_id}-y-lbl-{gi}",
            lines=(SceneTextLine(
                text=f"{gval:.4g}",
                x=chart_left - 4, y=gy + _FONT_SIZE * 0.35,
                font_size=float(_FONT_SIZE), fill_color=_AXIS_TEXT,
            ),),
            text_anchor="end",
        ))

    # Axes
    edge_elements.append(SceneLine(
        element_id=f"{scene_id}-y-axis",
        x1=chart_left, y1=chart_top, x2=chart_left, y2=chart_bottom,
        paint=PaintStyle(stroke=StrokeStyle(color=_AXIS_STROKE, width=1.5)),
    ))
    edge_elements.append(SceneLine(
        element_id=f"{scene_id}-x-axis",
        x1=chart_left, y1=chart_bottom, x2=chart_right, y2=chart_bottom,
        paint=PaintStyle(stroke=StrokeStyle(color=_AXIS_STROKE, width=1.5)),
    ))

    # Bars
    for idx in range(n):
        if idx < len(bar_data):
            bval = max(y_min, min(y_max, bar_data[idx]))
            bx = chart_left + idx * slot_w + bar_offset
            by = _y_to_px(bval)
            bh = chart_bottom - by

            node_elements.append(SceneRect(
                element_id=f"{scene_id}-bar-{idx}",
                x=bx, y=by, w=bar_w, h=bh,
                paint=PaintStyle(
                    fill=FillStyle(color=_BAR_FILL),
                    stroke=StrokeStyle(color=_BAR_STROKE, width=0.5),
                ),
                semantic_role="bar",
                data_attrs=(("data-value", str(bar_data[idx])),),
            ))

        # x-axis category label
        cat = x_cats[idx] if idx < len(x_cats) else str(idx + 1)
        label_elements.append(SceneText(
            element_id=f"{scene_id}-x-lbl-{idx}",
            lines=(SceneTextLine(
                text=cat,
                x=_x_slot_center(idx),
                y=chart_bottom + 16,
                font_size=float(_FONT_SIZE),
                fill_color=_AXIS_TEXT,
            ),),
            text_anchor="middle",
        ))

    # Line series
    if line_data and n > 0:
        line_cmds: list[tuple] = []
        for idx in range(n):
            if idx < len(line_data):
                lval = max(y_min, min(y_max, line_data[idx]))
                lx = _x_slot_center(idx)
                ly = _y_to_px(lval)
                cmd = ("M", lx, ly) if idx == 0 else ("L", lx, ly)
                line_cmds.append(cmd)

                overlay_elements.append(SceneCircle(
                    element_id=f"{scene_id}-line-pt-{idx}",
                    cx=lx, cy=ly, r=float(_LINE_DOT_R),
                    paint=PaintStyle(fill=FillStyle(color=_LINE_POINT_FILL)),
                    semantic_role="line-point",
                ))

        if line_cmds:
            overlay_elements.insert(0, ScenePath(
                element_id=f"{scene_id}-line",
                commands=tuple(line_cmds),
                paint=PaintStyle(
                    fill=FillStyle(color="none"),
                    stroke=StrokeStyle(color=_LINE_STROKE, width=2.0),
                ),
                semantic_role="line",
            ))

    # y-axis label
    if y_label:
        label_elements.append(SceneText(
            element_id=f"{scene_id}-y-axis-lbl",
            lines=(SceneTextLine(
                text=y_label,
                x=8.0,
                y=chart_top + chart_h / 2,
                font_size=float(_FONT_SIZE),
                fill_color=_AXIS_TEXT,
            ),),
            text_anchor="middle",
            transform=Rotate(angle=-90.0, cx=8.0, cy=float(chart_top + chart_h / 2)),
        ))

    layers = tuple([
        (LAYER_BACKGROUND, tuple(bg_elements)),
        *[
            (name, ())
            for name in LAYER_ORDER
            if name not in (LAYER_BACKGROUND, LAYER_EDGES, LAYER_NODES, LAYER_LABELS, LAYER_OVERLAYS)
        ],
        (LAYER_EDGES, tuple(edge_elements)),
        (LAYER_NODES, tuple(node_elements)),
        (LAYER_LABELS, tuple(label_elements)),
        (LAYER_OVERLAYS, tuple(overlay_elements)),
    ])

    return SvgScene(
        scene_id=scene_id,
        diagram_type="xychart-beta",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=title or "XY chart",
            description=f"XY chart with {n} categories",
        ),
        layers=layers,
    )
