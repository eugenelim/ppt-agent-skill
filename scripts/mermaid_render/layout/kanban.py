"""mermaid_render.layout.kanban — Native kanban scene builder.

Parses ``kanban`` source and renders a columnar board with card stacks.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from ..scene import (
    AccessibilityMetadata,
    FillStyle,
    LAYER_BACKGROUND,
    LAYER_BOUNDARIES,
    LAYER_LABELS,
    LAYER_NODES,
    LAYER_ORDER,
    PaintStyle,
    SceneRect,
    SceneRoundedRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)


# ── Color tokens ──────────────────────────────────────────────────────────────

_BG_FILL = "#f1f5f9"
_COL_FILL = "#e2e8f0"
_COL_STROKE = "#cbd5e1"
_COL_HEADER_FILL = "#334155"
_CARD_FILL = "#ffffff"
_CARD_STROKE = "#cbd5e1"
_TEXT_COLOR = "#1e293b"
_HEADER_TEXT = "#f8fafc"

# ── Layout constants ──────────────────────────────────────────────────────────

_COL_W = 200
_COL_GAP = 16
_COL_HEADER_H = 36
_CARD_H = 40
_CARD_GAP = 8
_CARD_RX = 6
_CARD_PAD_H = 10
_PAD_H = 24
_PAD_V = 24
_FONT_SIZE = 13
_HEADER_FONT = 14


# ── Parser ────────────────────────────────────────────────────────────────────

def _label_from(raw: str) -> str:
    """Extract label from 'id["label"]' or 'id[label]' or 'id'."""
    m = re.match(r'^[^[\s]+\["([^"]*)"\]', raw)
    if m:
        return m.group(1)
    m = re.match(r'^[^[\s]+\[([^\]]*)\]', raw)
    if m:
        return m.group(1)
    return raw.split()[0]


def _parse_kanban_source(src: str) -> list[dict]:
    """Return list of column dicts: {label, tasks: [str]}.

    Kanban grammar (simplified):
      kanban
        col_id["Column Name"]   ← column (indent level 1)
          task_id["Task"]       ← task (indent level 2)
    """
    columns: list[dict] = []
    cur_col: dict | None = None
    col_indent: int | None = None

    lines = src.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("kanban") or stripped.startswith("%%"):
            continue

        indent = len(line) - len(line.lstrip())

        if col_indent is None or indent <= col_indent:
            # New column
            label = _label_from(stripped)
            cur_col = {"label": label, "tasks": []}
            columns.append(cur_col)
            col_indent = indent
        else:
            # Task inside current column
            if cur_col is not None:
                # Strip @{...} metadata
                task_raw = re.sub(r'\s*@\{[^}]*\}', '', stripped).strip()
                label = _label_from(task_raw)
                cur_col["tasks"].append(label)

    return columns


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_kanban_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse kanban source and return an SvgScene with column layout."""
    columns = _parse_kanban_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("kanban", content_hash)

    if not columns:
        w = max(width_hint or 400, 400)
        h = 160
        return SvgScene(
            scene_id=scene_id,
            diagram_type="kanban",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title="Kanban board"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    n_cols = len(columns)
    max_tasks = max((len(c["tasks"]) for c in columns), default=0)
    col_h = _COL_HEADER_H + max_tasks * (_CARD_H + _CARD_GAP) + _CARD_GAP * 2

    canvas_w = float(_PAD_H * 2 + n_cols * _COL_W + (n_cols - 1) * _COL_GAP)
    canvas_h = float(_PAD_V * 2 + col_h)

    bg_elements: list = []
    boundary_elements: list = []
    node_elements: list = []
    label_elements: list = []

    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    for col_idx, col in enumerate(columns):
        col_x = float(_PAD_H + col_idx * (_COL_W + _COL_GAP))
        col_y = float(_PAD_V)

        # Column background
        boundary_elements.append(SceneRect(
            element_id=f"{scene_id}-col-{col_idx}",
            x=col_x,
            y=col_y,
            w=float(_COL_W),
            h=float(col_h),
            paint=PaintStyle(
                fill=FillStyle(color=_COL_FILL),
                stroke=StrokeStyle(color=_COL_STROKE, width=1.0),
            ),
            semantic_role="column",
            data_attrs=(("data-label", col["label"]),),
        ))

        # Column header
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-col-hdr-{col_idx}",
            x=col_x,
            y=col_y,
            w=float(_COL_W),
            h=float(_COL_HEADER_H),
            paint=PaintStyle(fill=FillStyle(color=_COL_HEADER_FILL)),
            semantic_role="column-header",
        ))

        label_elements.append(SceneText(
            element_id=f"{scene_id}-col-lbl-{col_idx}",
            lines=(SceneTextLine(
                text=col["label"],
                x=col_x + _COL_W / 2,
                y=col_y + _COL_HEADER_H / 2 + _HEADER_FONT * 0.35,
                font_size=float(_HEADER_FONT),
                font_weight=600,
                fill_color=_HEADER_TEXT,
            ),),
            text_anchor="middle",
        ))

        # Cards
        for task_idx, task_label in enumerate(col["tasks"]):
            card_x = col_x + _CARD_PAD_H
            card_y = float(col_y + _COL_HEADER_H + _CARD_GAP + task_idx * (_CARD_H + _CARD_GAP))

            node_elements.append(SceneRoundedRect(
                element_id=f"{scene_id}-card-{col_idx}-{task_idx}",
                x=card_x,
                y=card_y,
                w=float(_COL_W - _CARD_PAD_H * 2),
                h=float(_CARD_H),
                rx=float(_CARD_RX),
                ry=float(_CARD_RX),
                paint=PaintStyle(
                    fill=FillStyle(color=_CARD_FILL),
                    stroke=StrokeStyle(color=_CARD_STROKE, width=1.0),
                ),
                semantic_role="card",
                data_attrs=(("data-label", task_label),),
            ))

            label_elements.append(SceneText(
                element_id=f"{scene_id}-card-lbl-{col_idx}-{task_idx}",
                lines=(SceneTextLine(
                    text=task_label,
                    x=card_x + (_COL_W - _CARD_PAD_H * 2) / 2,
                    y=card_y + _CARD_H / 2 + _FONT_SIZE * 0.35,
                    font_size=float(_FONT_SIZE),
                    fill_color=_TEXT_COLOR,
                ),),
                text_anchor="middle",
            ))

    layers = tuple([
        (LAYER_BACKGROUND, tuple(bg_elements)),
        (LAYER_BOUNDARIES, tuple(boundary_elements)),
        *[
            (name, ())
            for name in LAYER_ORDER
            if name not in (LAYER_BACKGROUND, LAYER_BOUNDARIES, LAYER_NODES, LAYER_LABELS)
        ],
        (LAYER_NODES, tuple(node_elements)),
        (LAYER_LABELS, tuple(label_elements)),
    ])

    total_tasks = sum(len(c["tasks"]) for c in columns)
    return SvgScene(
        scene_id=scene_id,
        diagram_type="kanban",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title="Kanban board",
            description=f"Kanban board with {n_cols} columns and {total_tasks} tasks",
        ),
        layers=layers,
    )
