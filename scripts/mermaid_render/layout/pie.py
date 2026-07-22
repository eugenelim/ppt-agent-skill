"""mermaid_render.layout.pie — Native pie chart scene builder.

Parses ``pie [showData] [title ...]`` source and returns a column-layout
SvgScene with arc segments, legend, and optional data labels.
"""
from __future__ import annotations

import hashlib
import math
from typing import Optional

from ..scene import (
    AccessibilityMetadata,
    FillStyle,
    LAYER_BACKGROUND,
    LAYER_LABELS,
    LAYER_NODES,
    LAYER_ORDER,
    PaintStyle,
    SceneCircle,
    ScenePath,
    SceneRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)


# ── Color palette ─────────────────────────────────────────────────────────────

_SLICE_COLORS: tuple[str, ...] = (
    "#60a5fa",  # blue-400
    "#34d399",  # emerald-400
    "#f59e0b",  # amber-400
    "#f87171",  # red-400
    "#a78bfa",  # violet-400
    "#2dd4bf",  # teal-400
    "#fb923c",  # orange-400
    "#e879f9",  # fuchsia-400
    "#4ade80",  # green-400
    "#94a3b8",  # slate-400
    "#facc15",  # yellow-400
    "#38bdf8",  # sky-400
)

_BG_FILL = "#f8fafc"
_STROKE = "#ffffff"
_TEXT_COLOR = "#111827"
_DIM_COLOR = "#6b7280"
_TITLE_COLOR = "#111827"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD = 24
_TITLE_H = 30
_LEGEND_SWATCH_W = 12
_LEGEND_SWATCH_H = 12
_LEGEND_ROW_H = 20
_LEGEND_FONT = 13
_LABEL_FONT = 12
_TITLE_FONT = 18
_PIE_FONT = 13


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_pie_source(src: str) -> tuple[str, bool, list[tuple[str, float]]]:
    """Return (title, show_data, [(label, value), ...])."""
    lines = src.splitlines()
    title = ""
    show_data = False
    slices: list[tuple[str, float]] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        sl = stripped.lower()
        if i == 0 or sl.startswith("pie"):
            # directive line — parse options
            rest = stripped
            # strip leading "pie"
            if rest.lower().startswith("pie"):
                rest = rest[3:].strip()
            if rest.lower().startswith("showdata"):
                show_data = True
                rest = rest[9:].strip()
            if rest.lower().startswith("title "):
                title = rest[6:].strip()
            elif rest.lower().startswith("title"):
                title = rest[5:].strip()
            elif rest:
                # could be a title-only rest
                if not rest.startswith('"'):
                    title = rest
            continue
        if stripped.lower().startswith("title "):
            title = stripped[6:].strip()
            continue
        if stripped.startswith('"'):
            # "label" : value
            end_quote = stripped.find('"', 1)
            if end_quote == -1:
                continue
            label = stripped[1:end_quote]
            rest = stripped[end_quote + 1:].strip()
            if rest.startswith(":"):
                rest = rest[1:].strip()
            try:
                value = float(rest)
            except ValueError:
                continue
            slices.append((label, value))

    return title, show_data, slices


# ── Arc helpers ───────────────────────────────────────────────────────────────

def _polar(cx: float, cy: float, r: float, angle_deg: float) -> tuple[float, float]:
    """Convert polar coordinates to cartesian."""
    rad = math.radians(angle_deg - 90)   # 0° = top
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _arc_commands(
    cx: float, cy: float, r: float,
    start_deg: float, end_deg: float,
) -> list[tuple]:
    """Return SVG path commands for a pie slice arc (filled)."""
    large = 1 if (end_deg - start_deg) > 180 else 0
    x1, y1 = _polar(cx, cy, r, start_deg)
    x2, y2 = _polar(cx, cy, r, end_deg)
    return [
        ("M", cx, cy),
        ("L", x1, y1),
        ("A", r, r, 0.0, float(large), 1.0, x2, y2),
        ("Z",),
    ]


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_pie_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse pie source and return a SvgScene with arc segments and legend."""
    title, show_data, slices = _parse_pie_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("pie", content_hash)

    if not slices:
        # Empty diagram — produce minimal valid scene
        w = max(width_hint or 300, 300)
        h = 200
        return SvgScene(
            scene_id=scene_id,
            diagram_type="pie",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title=title or "pie chart", description="Empty pie chart"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    total = sum(v for _, v in slices)
    if total <= 0:
        total = 1.0

    # Layout geometry
    legend_w = max((len(lbl) for lbl, _ in slices), default=8) * _LEGEND_FONT * 0.6 + _LEGEND_SWATCH_W + 24
    legend_rows = len(slices)
    legend_h = legend_rows * _LEGEND_ROW_H

    title_h = _TITLE_H if title else 0
    pie_diam = max(160, min(320, width_hint - int(legend_w) - _PAD * 3) if width_hint else 240)
    pie_r = pie_diam / 2
    pie_area_h = pie_diam + _PAD * 2
    canvas_h = float(max(pie_area_h, legend_h + _PAD * 2) + title_h + _PAD * 2)
    canvas_w = float(pie_diam + legend_w + _PAD * 3)
    if width_hint and width_hint > canvas_w:
        canvas_w = float(width_hint)

    cx = float(_PAD + pie_r)
    cy = float(title_h + _PAD + pie_r)

    bg_elements: list = []
    node_elements: list = []
    label_elements: list = []

    # Background
    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    # Title
    if title:
        label_elements.append(SceneText(
            element_id=f"{scene_id}-title",
            lines=(SceneTextLine(
                text=title,
                x=canvas_w / 2,
                y=float(_PAD + _TITLE_FONT),
                font_size=float(_TITLE_FONT),
                font_weight=600,
                fill_color=_TITLE_COLOR,
            ),),
            text_anchor="middle",
        ))

    # Pie slices
    cur_angle = 0.0
    for idx, (lbl, val) in enumerate(slices):
        frac = val / total
        sweep = frac * 360.0
        end_angle = cur_angle + sweep
        color = _SLICE_COLORS[idx % len(_SLICE_COLORS)]
        cmds = _arc_commands(cx, cy, pie_r, cur_angle, end_angle)

        node_elements.append(ScenePath(
            element_id=f"{scene_id}-slice-{idx}",
            commands=tuple(cmds),
            paint=PaintStyle(
                fill=FillStyle(color=color),
                stroke=StrokeStyle(color=_STROKE, width=1.5),
            ),
            semantic_role="slice",
            data_attrs=(("data-label", lbl), ("data-value", str(val))),
        ))

        # Percentage label inside or near slice
        mid_angle = cur_angle + sweep / 2
        label_r = pie_r * 0.65
        lx, ly = _polar(cx, cy, label_r, mid_angle)
        if sweep > 12:
            pct_text = f"{frac * 100:.0f}%"
            label_elements.append(SceneText(
                element_id=f"{scene_id}-pct-{idx}",
                lines=(SceneTextLine(
                    text=pct_text,
                    x=lx, y=ly + _PIE_FONT * 0.35,
                    font_size=float(_PIE_FONT),
                    font_weight=600,
                    fill_color="#ffffff",
                ),),
                text_anchor="middle",
            ))

        cur_angle = end_angle

    # Legend
    legend_x = float(pie_diam + _PAD * 2)
    for idx, (lbl, val) in enumerate(slices):
        color = _SLICE_COLORS[idx % len(_SLICE_COLORS)]
        row_y = float(title_h + _PAD + idx * _LEGEND_ROW_H)

        # Swatch
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-swatch-{idx}",
            x=legend_x,
            y=row_y + (_LEGEND_ROW_H - _LEGEND_SWATCH_H) / 2,
            w=float(_LEGEND_SWATCH_W),
            h=float(_LEGEND_SWATCH_H),
            paint=PaintStyle(fill=FillStyle(color=color)),
        ))

        # Label text
        legend_text = f"{lbl} ({val:.4g})" if show_data else lbl
        label_elements.append(SceneText(
            element_id=f"{scene_id}-legend-lbl-{idx}",
            lines=(SceneTextLine(
                text=legend_text,
                x=legend_x + _LEGEND_SWATCH_W + 6,
                y=row_y + _LEGEND_ROW_H * 0.7,
                font_size=float(_LEGEND_FONT),
                fill_color=_TEXT_COLOR,
            ),),
            text_anchor="start",
        ))

    layers = tuple([
        (LAYER_BACKGROUND, tuple(bg_elements)),
        *[
            (name, ())
            for name in LAYER_ORDER
            if name not in (LAYER_BACKGROUND, LAYER_NODES, LAYER_LABELS)
        ],
        (LAYER_NODES, tuple(node_elements)),
        (LAYER_LABELS, tuple(label_elements)),
    ])

    return SvgScene(
        scene_id=scene_id,
        diagram_type="pie",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=title or "Pie chart",
            description=f"Pie chart with {len(slices)} slices",
        ),
        layers=layers,
    )
