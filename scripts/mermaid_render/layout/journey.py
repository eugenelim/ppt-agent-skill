"""mermaid_render.layout.journey — Native user-journey scene builder.

Parses ``journey`` source and renders sections as column bands with
task rows coloured by satisfaction score (1–5).
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from ..scene import (
    AccessibilityMetadata,
    FillStyle,
    LAYER_BACKGROUND,
    LAYER_LABELS,
    LAYER_NODES,
    LAYER_ORDER,
    PaintStyle,
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
_SECTION_FILL = "#e0f2fe"
_SECTION_STROKE = "#7dd3fc"
_SECTION_TEXT = "#0c4a6e"

# Score-based task fill: index 0 = score 1 (lowest), index 4 = score 5 (highest)
_SCORE_FILLS = (
    "#fca5a5",  # score 1 — red-300
    "#fcd34d",  # score 2 — amber-300
    "#fde68a",  # score 3 — yellow-200
    "#86efac",  # score 4 — green-300
    "#4ade80",  # score 5 — green-400
)
_TASK_STROKE = "#94a3b8"
_TASK_TEXT = "#1e293b"
_ACTOR_FILL = "#dbeafe"
_ACTOR_STROKE = "#93c5fd"
_ACTOR_TEXT = "#1e3a8a"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD_H = 32
_PAD_V = 24
_TITLE_H = 28
_TITLE_FONT = 17
_SECTION_LABEL_W = 100  # width reserved for section label on left
_TASK_H = 36
_TASK_GAP = 6
_TASK_PAD_H = 8
_FONT_SIZE = 12
_SECTION_FONT = 12


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_journey_source(src: str) -> tuple[str, list[dict]]:
    """Return (title, sections).

    section: {name: str, tasks: [{name, score, actors}]}
    """
    title = ""
    sections: list[dict] = []
    cur_section: dict | None = None

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("journey") or stripped.startswith("%%"):
            continue

        if stripped.lower().startswith("title "):
            title = stripped[6:].strip()
            continue

        if stripped.lower().startswith("section "):
            section_name = stripped[8:].strip()
            cur_section = {"name": section_name, "tasks": []}
            sections.append(cur_section)
            continue

        # Task line: "Task name: score: Actor1, Actor2"
        m = re.match(r'^(.+?):\s*(\d+)\s*:(.*)', stripped)
        if m and cur_section is not None:
            task_name = m.group(1).strip()
            score = min(5, max(1, int(m.group(2))))
            actors = [a.strip() for a in m.group(3).split(",") if a.strip()]
            cur_section["tasks"].append({"name": task_name, "score": score, "actors": actors})

    return title, sections


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_journey_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse journey source and return an SvgScene with task band layout."""
    title, sections = _parse_journey_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("journey", content_hash)

    if not sections:
        w = max(width_hint or 400, 400)
        h = 160
        return SvgScene(
            scene_id=scene_id,
            diagram_type="journey",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title=title or "User journey"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    all_tasks: list[dict] = [t for s in sections for t in s["tasks"]]
    n_tasks = len(all_tasks)
    max_task_name = max((len(t["name"]) for t in all_tasks), default=8) if all_tasks else 8
    task_area_w = max(max_task_name * _FONT_SIZE * 0.6 + _TASK_PAD_H * 2, 120)

    # Each section gets a column band; tasks are rows spanning all section bands
    n_sections = len(sections)
    section_w = max(80, (((width_hint or 800) - _PAD_H * 2 - _SECTION_LABEL_W - task_area_w) // n_sections)) if n_sections else 80

    title_h = _TITLE_H if title else 0
    chart_h = n_tasks * (_TASK_H + _TASK_GAP) + _TASK_GAP
    canvas_w = float(_PAD_H * 2 + _SECTION_LABEL_W + task_area_w + n_sections * section_w)
    canvas_h = float(_PAD_V * 2 + title_h + 28 + chart_h)  # 28 = section header row

    SECTION_HEADER_H = 28
    chart_top = float(_PAD_V + title_h + SECTION_HEADER_H)
    task_start_x = float(_PAD_H + _SECTION_LABEL_W)

    bg_elements: list = []
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

    # Section column headers + background bands
    for sec_idx, section in enumerate(sections):
        sec_x = float(task_start_x + task_area_w + sec_idx * section_w)
        sec_w = float(section_w)

        # Section header
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-sec-hdr-{sec_idx}",
            x=sec_x,
            y=float(_PAD_V + title_h),
            w=sec_w,
            h=float(SECTION_HEADER_H),
            paint=PaintStyle(
                fill=FillStyle(color=_SECTION_FILL),
                stroke=StrokeStyle(color=_SECTION_STROKE, width=1.0),
            ),
            semantic_role="section",
            data_attrs=(("data-label", section["name"]),),
        ))

        label_elements.append(SceneText(
            element_id=f"{scene_id}-sec-lbl-{sec_idx}",
            lines=(SceneTextLine(
                text=section["name"],
                x=sec_x + sec_w / 2,
                y=float(_PAD_V + title_h + SECTION_HEADER_H / 2 + _SECTION_FONT * 0.35),
                font_size=float(_SECTION_FONT),
                font_weight=600,
                fill_color=_SECTION_TEXT,
            ),),
            text_anchor="middle",
        ))

        # Background band for section column
        bg_elements.append(SceneRect(
            element_id=f"{scene_id}-sec-bg-{sec_idx}",
            x=sec_x,
            y=chart_top,
            w=sec_w,
            h=float(chart_h),
            paint=PaintStyle(
                fill=FillStyle(color=_SECTION_FILL, opacity=0.3),
                stroke=StrokeStyle(color=_SECTION_STROKE, width=0.5),
            ),
        ))

    # Tasks rows (flattened across all sections)
    global_task_idx = 0
    for sec_idx, section in enumerate(sections):
        for task in section["tasks"]:
            task_y = float(chart_top + _TASK_GAP + global_task_idx * (_TASK_H + _TASK_GAP))
            color_idx = min(4, max(0, task["score"] - 1))
            fill_color = _SCORE_FILLS[color_idx]

            # Task label column
            node_elements.append(SceneRect(
                element_id=f"{scene_id}-task-{global_task_idx}",
                x=float(task_start_x),
                y=task_y,
                w=float(task_area_w),
                h=float(_TASK_H),
                paint=PaintStyle(
                    fill=FillStyle(color=fill_color),
                    stroke=StrokeStyle(color=_TASK_STROKE, width=1.0),
                ),
                semantic_role="task",
                data_attrs=(
                    ("data-label", task["name"]),
                    ("data-score", str(task["score"])),
                ),
            ))

            label_elements.append(SceneText(
                element_id=f"{scene_id}-task-lbl-{global_task_idx}",
                lines=(SceneTextLine(
                    text=task["name"],
                    x=float(task_start_x + task_area_w / 2),
                    y=task_y + _TASK_H / 2 + _FONT_SIZE * 0.35,
                    font_size=float(_FONT_SIZE),
                    fill_color=_TASK_TEXT,
                ),),
                text_anchor="middle",
            ))

            # Score dot in corresponding section column
            sec_x = float(task_start_x + task_area_w + sec_idx * section_w)
            dot_x = sec_x + section_w / 2
            dot_y = task_y + _TASK_H / 2

            node_elements.append(SceneRect(
                element_id=f"{scene_id}-score-{global_task_idx}",
                x=dot_x - 12,
                y=dot_y - 12,
                w=24.0,
                h=24.0,
                paint=PaintStyle(
                    fill=FillStyle(color=fill_color),
                    stroke=StrokeStyle(color=_TASK_STROKE, width=1.0),
                ),
                data_attrs=(("data-score", str(task["score"])),),
            ))

            label_elements.append(SceneText(
                element_id=f"{scene_id}-score-lbl-{global_task_idx}",
                lines=(SceneTextLine(
                    text=str(task["score"]),
                    x=dot_x,
                    y=dot_y + _FONT_SIZE * 0.35,
                    font_size=float(_FONT_SIZE),
                    font_weight=600,
                    fill_color=_TASK_TEXT,
                ),),
                text_anchor="middle",
            ))

            global_task_idx += 1

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
        diagram_type="journey",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=title or "User journey",
            description=f"User journey with {len(sections)} sections and {n_tasks} tasks",
        ),
        layers=layers,
    )
