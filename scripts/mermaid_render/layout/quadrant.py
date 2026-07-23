"""mermaid_render.layout.quadrant — Native quadrantChart scene builder.

Parses ``quadrantChart`` source and renders a 4-quadrant scatter plot
with labelled axes, quadrant labels, and data points.
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
    LAYER_ORDER,
    PaintStyle,
    SceneCircle,
    SceneLine,
    SceneRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)


# ── Color tokens ──────────────────────────────────────────────────────────────

_BG_FILL = "#f8fafc"
_GRID_STROKE = "#e2e8f0"
_AXIS_STROKE = "#94a3b8"
_Q_FILLS = (
    "rgba(248,113,113,0.08)",   # Q3 bottom-left
    "rgba(251,191,36,0.08)",    # Q4 bottom-right
    "rgba(167,139,250,0.08)",   # Q2 top-left
    "rgba(96,165,250,0.08)",    # Q1 top-right
)
_POINT_FILL = "#60a5fa"
_POINT_STROKE = "#1d4ed8"
_TEXT_COLOR = "#374151"
_TITLE_COLOR = "#111827"
_AXIS_TEXT = "#6b7280"
_Q_TEXT = "#9ca3af"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD = 48
_TITLE_H = 28
_TITLE_FONT = 17
_CHART_SIZE = 360    # width and height of the chart square
_FONT_SIZE = 12
_Q_FONT = 11
_AXIS_FONT = 11
_POINT_R = 6


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_quadrant_source(src: str) -> tuple[str, str, str, str, str, list[str], list[tuple[str, float, float]]]:
    """Return (title, x_low, x_high, y_low, y_high, q1, q2, q3, q4, points).

    Actually returns (title, x_low, x_high, y_low, y_high, q_labels[4], points).
    """
    title = ""
    x_axis = ("", "")
    y_axis = ("", "")
    q_labels = ["", "", "", ""]   # q1..q4
    points: list[tuple[str, float, float]] = []

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("quadrant") or stripped.startswith("%%"):
            continue

        if stripped.lower().startswith("title "):
            title = stripped[6:].strip()
            continue

        # x-axis Low --> High
        m = re.match(r'^x-axis\s+(.+?)\s*-->\s*(.+)', stripped, re.IGNORECASE)
        if m:
            x_axis = (m.group(1).strip(), m.group(2).strip())
            continue

        # y-axis Low --> High
        m = re.match(r'^y-axis\s+(.+?)\s*-->\s*(.+)', stripped, re.IGNORECASE)
        if m:
            y_axis = (m.group(1).strip(), m.group(2).strip())
            continue

        # quadrant-N Label
        m = re.match(r'^quadrant-([1-4])\s+(.*)', stripped, re.IGNORECASE)
        if m:
            idx = int(m.group(1)) - 1
            q_labels[idx] = m.group(2).strip()
            continue

        # Point: Name: [x, y]
        m = re.match(r'^(.+?)\s*:\s*\[\s*([\d.]+)\s*,\s*([\d.]+)\s*\]', stripped)
        if m:
            name = m.group(1).strip()
            x = float(m.group(2))
            y = float(m.group(3))
            points.append((name, x, y))

    return title, x_axis[0], x_axis[1], y_axis[0], y_axis[1], q_labels, points


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_quadrant_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse quadrantChart source and return an SvgScene with 4-quadrant plot."""
    title, x_low, x_high, y_low, y_high, q_labels, points = _parse_quadrant_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("quadrantchart", content_hash)

    chart_sz = min(_CHART_SIZE, (width_hint - _PAD * 2) if width_hint else _CHART_SIZE)
    chart_sz = max(chart_sz, 200)

    title_h = _TITLE_H if title else 0
    canvas_w = float(chart_sz + _PAD * 2)
    canvas_h = float(chart_sz + _PAD * 2 + title_h)

    chart_x = float(_PAD)
    chart_y = float(_PAD + title_h)

    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
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
                y=float(_PAD * 0.6 + _TITLE_FONT),
                font_size=float(_TITLE_FONT),
                font_weight=600,
                fill_color=_TITLE_COLOR,
            ),),
            text_anchor="middle",
        ))

    half = chart_sz / 2

    # 4 quadrant backgrounds (Q3=BL, Q4=BR, Q2=TL, Q1=TR in Mermaid convention)
    # Mermaid Q1=top-right, Q2=top-left, Q3=bottom-left, Q4=bottom-right
    quad_rects = [
        (chart_x + half, chart_y, half, half, _Q_FILLS[3], q_labels[0]),   # Q1 TR
        (chart_x, chart_y, half, half, _Q_FILLS[2], q_labels[1]),           # Q2 TL
        (chart_x, chart_y + half, half, half, _Q_FILLS[0], q_labels[2]),    # Q3 BL
        (chart_x + half, chart_y + half, half, half, _Q_FILLS[1], q_labels[3]),  # Q4 BR
    ]

    for qi, (qx, qy, qw, qh, qfill, qlabel) in enumerate(quad_rects):
        bg_elements.append(SceneRect(
            element_id=f"{scene_id}-q{qi+1}",
            x=qx, y=qy, w=qw, h=qh,
            paint=PaintStyle(fill=FillStyle(color=qfill)),
            semantic_role=f"quadrant-{qi+1}",
        ))
        if qlabel:
            lx = qx + qw * 0.5
            ly = qy + qh * 0.5
            label_elements.append(SceneText(
                element_id=f"{scene_id}-qlabel-{qi+1}",
                lines=(SceneTextLine(
                    text=qlabel,
                    x=lx, y=ly,
                    font_size=float(_Q_FONT),
                    fill_color=_Q_TEXT,
                ),),
                text_anchor="middle",
            ))

    # Axis lines
    # Horizontal mid-axis
    edge_elements.append(SceneLine(
        element_id=f"{scene_id}-h-axis",
        x1=chart_x, y1=chart_y + half,
        x2=chart_x + chart_sz, y2=chart_y + half,
        paint=PaintStyle(stroke=StrokeStyle(color=_AXIS_STROKE, width=1.5)),
    ))
    # Vertical mid-axis
    edge_elements.append(SceneLine(
        element_id=f"{scene_id}-v-axis",
        x1=chart_x + half, y1=chart_y,
        x2=chart_x + half, y2=chart_y + chart_sz,
        paint=PaintStyle(stroke=StrokeStyle(color=_AXIS_STROKE, width=1.5)),
    ))
    # Chart border
    edge_elements.append(SceneRect(
        element_id=f"{scene_id}-border",
        x=chart_x, y=chart_y, w=float(chart_sz), h=float(chart_sz),
        paint=PaintStyle(
            fill=FillStyle(color="none"),
            stroke=StrokeStyle(color=_AXIS_STROKE, width=1.0),
        ),
    ))

    # Axis labels
    if x_low:
        label_elements.append(SceneText(
            element_id=f"{scene_id}-x-low",
            lines=(SceneTextLine(text=x_low, x=chart_x, y=chart_y + chart_sz + 16,
                                  font_size=float(_AXIS_FONT), fill_color=_AXIS_TEXT),),
            text_anchor="start",
        ))
    if x_high:
        label_elements.append(SceneText(
            element_id=f"{scene_id}-x-high",
            lines=(SceneTextLine(text=x_high, x=chart_x + chart_sz, y=chart_y + chart_sz + 16,
                                  font_size=float(_AXIS_FONT), fill_color=_AXIS_TEXT),),
            text_anchor="end",
        ))
    if y_low:
        label_elements.append(SceneText(
            element_id=f"{scene_id}-y-low",
            lines=(SceneTextLine(text=y_low, x=chart_x - 4, y=chart_y + chart_sz,
                                  font_size=float(_AXIS_FONT), fill_color=_AXIS_TEXT),),
            text_anchor="end",
        ))
    if y_high:
        label_elements.append(SceneText(
            element_id=f"{scene_id}-y-high",
            lines=(SceneTextLine(text=y_high, x=chart_x - 4, y=chart_y + 4,
                                  font_size=float(_AXIS_FONT), fill_color=_AXIS_TEXT),),
            text_anchor="end",
        ))

    # Data points: x ∈ [0,1], y ∈ [0,1]; y=0 is bottom
    for idx, (name, px, py) in enumerate(points):
        dot_x = chart_x + px * chart_sz
        dot_y = chart_y + (1 - py) * chart_sz   # flip y

        node_elements.append(SceneCircle(
            element_id=f"{scene_id}-pt-{idx}",
            cx=dot_x, cy=dot_y, r=float(_POINT_R),
            paint=PaintStyle(
                fill=FillStyle(color=_POINT_FILL),
                stroke=StrokeStyle(color=_POINT_STROKE, width=1.0),
            ),
            semantic_role="data-point",
            data_attrs=(("data-label", name),),
        ))

        label_elements.append(SceneText(
            element_id=f"{scene_id}-pt-lbl-{idx}",
            lines=(SceneTextLine(
                text=name,
                x=dot_x + _POINT_R + 3,
                y=dot_y + _FONT_SIZE * 0.35,
                font_size=float(_FONT_SIZE),
                fill_color=_TEXT_COLOR,
            ),),
            text_anchor="start",
        ))

    layers = tuple([
        (LAYER_BACKGROUND, tuple(bg_elements)),
        *[
            (name, ())
            for name in LAYER_ORDER
            if name not in (LAYER_BACKGROUND, LAYER_EDGES, LAYER_NODES, LAYER_LABELS)
        ],
        (LAYER_EDGES, tuple(edge_elements)),
        (LAYER_NODES, tuple(node_elements)),
        (LAYER_LABELS, tuple(label_elements)),
    ])

    return SvgScene(
        scene_id=scene_id,
        diagram_type="quadrantchart",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=title or "Quadrant chart",
            description=f"Quadrant chart with {len(points)} data points",
        ),
        layers=layers,
    )
