"""mermaid_render.layout.gantt — Native Gantt chart scene builder.

Parses ``gantt`` source and renders horizontal task bars on a time axis.
Supports dateFormat YYYY-MM-DD, absolute/relative dates, and Nd duration.
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
_TITLE_COLOR = "#111827"
_AXIS_COLOR = "#94a3b8"
_SECTION_FILLS = (
    "rgba(96,165,250,0.12)",
    "rgba(52,211,153,0.12)",
    "rgba(251,191,36,0.12)",
    "rgba(167,139,250,0.12)",
    "rgba(248,113,113,0.12)",
)
_SECTION_TEXT = "#374151"

# Task status fill colours
_STATUS_FILLS: dict[str, str] = {
    "done": "#6ee7b7",
    "active": "#60a5fa",
    "crit": "#f87171",
    "milestone": "#fbbf24",
    "default": "#93c5fd",
}
_TASK_STROKE = "#64748b"
_TASK_TEXT = "#1e293b"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD_H = 140      # left margin for task labels
_PAD_V = 24
_TITLE_H = 28
_TITLE_FONT = 17
_AXIS_H = 30      # height of the time axis header
_ROW_H = 28
_ROW_GAP = 4
_SECTION_LABEL_W = _PAD_H - 8
_FONT_SIZE = 12
_SECTION_FONT = 11
_AXIS_FONT = 10
_MIN_CANVAS_W = 600


# ── Date helpers ──────────────────────────────────────────────────────────────

def _ymd_to_days(date_str: str) -> Optional[int]:
    """Parse YYYY-MM-DD to integer day count (days since epoch)."""
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str.strip())
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    # Simplified day calculation (no leap year accuracy needed for layout)
    return y * 365 + mo * 30 + d


def _duration_to_days(dur_str: str) -> int:
    """Parse '7d', '2w', '1m' to approximate days."""
    m = re.match(r'^(\d+)\s*([dwm])', dur_str.strip().lower())
    if not m:
        return 1
    n = int(m.group(1))
    unit = m.group(2)
    if unit == 'd':
        return n
    elif unit == 'w':
        return n * 7
    else:  # m
        return n * 30


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_gantt_source(src: str) -> tuple[str, list[dict]]:
    """Return (title, sections).

    section: {name: str, tasks: [{id, label, start, end, status}]}
    where start/end are integer days.
    """
    title = ""
    date_format = "YYYY-MM-DD"
    sections: list[dict] = []
    cur_section: dict | None = None
    task_by_id: dict[str, dict] = {}

    lines = src.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("gantt") or stripped.startswith("%%"):
            continue

        if stripped.lower().startswith("title "):
            title = stripped[6:].strip()
            continue
        if stripped.lower().startswith("dateformat "):
            date_format = stripped[11:].strip()
            continue
        if stripped.lower().startswith("excludes"):
            continue
        if stripped.lower().startswith("section "):
            section_name = stripped[8:].strip()
            cur_section = {"name": section_name, "tasks": []}
            sections.append(cur_section)
            continue

        # Task line: "Label :modifiers, id, startDate, duration"
        # or "Label :modifiers, startDate, duration"
        # or "Label :after id, duration"
        if ":" not in stripped:
            continue

        label_part, _, rest = stripped.partition(":")
        label = label_part.strip()
        parts = [p.strip() for p in rest.split(",")]

        # Extract modifiers (done, active, crit, milestone)
        status = "default"
        clean_parts = []
        for part in parts:
            pl = part.lower().strip()
            if pl in ("done", "active", "crit", "milestone"):
                status = pl
            else:
                clean_parts.append(part.strip())

        task_id = ""
        start_days: Optional[int] = None
        end_days: Optional[int] = None

        if not clean_parts:
            continue

        # Check if first clean_part looks like an ID (no digits, no dash-date)
        first = clean_parts[0]
        if first and not re.match(r'^\d{4}-', first) and not first.lower().startswith("after") and not re.match(r'^\d+[dwm]', first.lower()):
            task_id = first
            clean_parts = clean_parts[1:]

        if not clean_parts:
            start_days = 0
            end_days = 1
        elif clean_parts[0].lower().startswith("after "):
            # Relative to another task's end
            dep_id = clean_parts[0][6:].strip()
            dep = task_by_id.get(dep_id)
            start_days = dep["end"] if dep else 0
            dur = _duration_to_days(clean_parts[1]) if len(clean_parts) > 1 else 1
            end_days = (start_days or 0) + dur
        else:
            # Absolute start
            start_days = _ymd_to_days(clean_parts[0])
            if start_days is None:
                start_days = 0
            if len(clean_parts) > 1:
                # Could be end date or duration
                end_part = clean_parts[1]
                if re.match(r'^\d{4}-', end_part):
                    end_days = _ymd_to_days(end_part) or (start_days + 1)
                else:
                    end_days = start_days + _duration_to_days(end_part)
            else:
                end_days = start_days + 1

        task = {
            "id": task_id,
            "label": label,
            "start": start_days or 0,
            "end": end_days or ((start_days or 0) + 1),
            "status": status,
        }
        if task_id:
            task_by_id[task_id] = task

        if cur_section is None:
            cur_section = {"name": "", "tasks": []}
            sections.append(cur_section)
        cur_section["tasks"].append(task)

    return title, sections


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_gantt_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse gantt source and return an SvgScene with horizontal task bars."""
    title, sections = _parse_gantt_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("gantt", content_hash)

    all_tasks = [t for s in sections for t in s["tasks"]]
    if not all_tasks:
        w = max(width_hint or 500, 500)
        h = 160
        return SvgScene(
            scene_id=scene_id,
            diagram_type="gantt",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title=title or "Gantt chart"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    min_day = min(t["start"] for t in all_tasks)
    max_day = max(t["end"] for t in all_tasks)
    span = max(max_day - min_day, 1)

    title_h = _TITLE_H if title else 0
    n_tasks = len(all_tasks)
    chart_h = n_tasks * (_ROW_H + _ROW_GAP) + _ROW_GAP

    canvas_w = float(max(width_hint or _MIN_CANVAS_W, _MIN_CANVAS_W))
    chart_w = canvas_w - _PAD_H * 2
    canvas_h = float(_PAD_V * 2 + title_h + _AXIS_H + chart_h)

    chart_top = float(_PAD_V + title_h + _AXIS_H)
    chart_left = float(_PAD_H)

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
                y=float(_PAD_V + _TITLE_FONT),
                font_size=float(_TITLE_FONT),
                font_weight=600,
                fill_color=_TITLE_COLOR,
            ),),
            text_anchor="middle",
        ))

    def _day_to_x(day: int) -> float:
        return chart_left + (day - min_day) / span * chart_w

    # Axis line
    edge_elements.append(SceneLine(
        element_id=f"{scene_id}-axis",
        x1=chart_left,
        y1=float(_PAD_V + title_h + _AXIS_H),
        x2=chart_left + chart_w,
        y2=float(_PAD_V + title_h + _AXIS_H),
        paint=PaintStyle(stroke=StrokeStyle(color=_AXIS_COLOR, width=1.0)),
    ))

    # Tasks and section backgrounds
    global_row = 0
    for sec_idx, section in enumerate(sections):
        if not section["tasks"]:
            continue

        # Section background band
        sec_row_start = global_row
        sec_h = len(section["tasks"]) * (_ROW_H + _ROW_GAP) + _ROW_GAP
        sec_y = chart_top + sec_row_start * (_ROW_H + _ROW_GAP)
        fill_color = _SECTION_FILLS[sec_idx % len(_SECTION_FILLS)]
        bg_elements.append(SceneRect(
            element_id=f"{scene_id}-sec-{sec_idx}",
            x=chart_left,
            y=sec_y,
            w=chart_w,
            h=sec_h,
            paint=PaintStyle(fill=FillStyle(color=fill_color)),
            semantic_role="section",
            data_attrs=(("data-label", section["name"]),),
        ))

        if section["name"]:
            label_elements.append(SceneText(
                element_id=f"{scene_id}-sec-lbl-{sec_idx}",
                lines=(SceneTextLine(
                    text=section["name"],
                    x=chart_left - 4,
                    y=sec_y + sec_h / 2 + _SECTION_FONT * 0.35,
                    font_size=float(_SECTION_FONT),
                    font_weight=600,
                    fill_color=_SECTION_TEXT,
                    italic=True,
                ),),
                text_anchor="end",
            ))

        for task in section["tasks"]:
            row_y = chart_top + _ROW_GAP + global_row * (_ROW_H + _ROW_GAP)
            bar_x = _day_to_x(task["start"])
            bar_w = max(4.0, _day_to_x(task["end"]) - bar_x)
            fill = _STATUS_FILLS.get(task["status"], _STATUS_FILLS["default"])

            node_elements.append(SceneRect(
                element_id=f"{scene_id}-task-{global_row}",
                x=bar_x,
                y=row_y,
                w=bar_w,
                h=float(_ROW_H),
                paint=PaintStyle(
                    fill=FillStyle(color=fill),
                    stroke=StrokeStyle(color=_TASK_STROKE, width=0.5),
                ),
                semantic_role="task",
                data_attrs=(
                    ("data-label", task["label"]),
                    ("data-status", task["status"]),
                ),
            ))

            # Task label in left margin
            label_elements.append(SceneText(
                element_id=f"{scene_id}-lbl-{global_row}",
                lines=(SceneTextLine(
                    text=task["label"],
                    x=chart_left - 6,
                    y=row_y + _ROW_H / 2 + _FONT_SIZE * 0.35,
                    font_size=float(_FONT_SIZE),
                    fill_color=_TASK_TEXT,
                ),),
                text_anchor="end",
            ))

            global_row += 1

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
        diagram_type="gantt",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=title or "Gantt chart",
            description=f"Gantt chart with {len(sections)} sections and {n_tasks} tasks",
        ),
        layers=layers,
    )
