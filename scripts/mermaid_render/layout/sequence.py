"""mermaid_render.layout.sequence — Native sequence diagram scene builder.

Parses ``sequenceDiagram`` source and renders participant lifelines with
message arrows between them.
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
    LAYER_NOTES,
    LAYER_OVERLAYS,
    LAYER_ORDER,
    MarkerDefinition,
    PaintStyle,
    SceneLine,
    ScenePath,
    SceneRect,
    SceneRoundedRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)


# ── Color tokens ──────────────────────────────────────────────────────────────

_BG_FILL = "#f8fafc"
_ACTOR_FILL = "#dbeafe"
_ACTOR_STROKE = "#93c5fd"
_ACTOR_TEXT = "#1e3a8a"
_LIFELINE_STROKE = "#cbd5e1"
_MSG_STROKE = "#374151"
_NOTE_FILL = "#fef9c3"
_NOTE_STROKE = "#facc15"
_NOTE_TEXT = "#713f12"
_TITLE_COLOR = "#111827"
_TEXT_COLOR = "#374151"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD_H = 32
_PAD_V = 24
_ACTOR_W = 120
_ACTOR_H = 36
_ACTOR_GAP = 80          # horizontal gap between actor centers
_MSG_STEP = 40           # vertical step per message
_MSG_FONT = 12
_ACTOR_FONT = 13
_LIFELINE_DASH = "4 3"
_TITLE_FONT = 16


# ── Parser ────────────────────────────────────────────────────────────────────


def _parse_sequence_source(src: str) -> tuple[str, list[str], list[dict]]:
    """Return (title, participants, messages).

    message: {src, dst, label, arrow, activate, deactivate, is_note, note_over}
    """
    title = ""
    explicit_participants: list[str] = []
    participant_order: list[str] = []
    messages: list[dict] = []

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("sequencediagram") or stripped.startswith("%%"):
            continue

        if stripped.lower().startswith("title "):
            title = stripped[6:].strip()
            continue

        # participant declaration
        m = re.match(r'^(?:participant|actor)\s+(.+?)(?:\s+as\s+(.+))?$', stripped, re.IGNORECASE)
        if m:
            name = m.group(2).strip() if m.group(2) else m.group(1).strip()
            if name not in participant_order:
                participant_order.append(name)
                explicit_participants.append(name)
            continue

        # Note over / Note left of / Note right of
        m = re.match(r'^note\s+(?:over|left of|right of)\s+([^:]+)(?::\s*(.*))?$', stripped, re.IGNORECASE)
        if m:
            over_who = m.group(1).strip().split(",")[0].strip()
            note_text = m.group(2).strip() if m.group(2) else ""
            messages.append({
                "is_note": True,
                "note_over": over_who,
                "label": note_text,
                "src": over_who,
                "dst": over_who,
                "arrow": "",
                "activate": False,
                "deactivate": False,
            })
            if over_who not in participant_order:
                participant_order.append(over_who)
            continue

        # skip loop/alt/else/end/opt/par/rect/critical/break
        if re.match(r'^(loop|alt|else|end|opt|par|rect|critical|break)\s*', stripped, re.IGNORECASE):
            continue

        # activate / deactivate
        if stripped.lower().startswith("activate ") or stripped.lower().startswith("deactivate "):
            continue

        # Message: Src->>Dst: Label  (or with +/- suffix for activations)
        is_activate = False
        is_deactivate = False
        m2 = re.match(r'^(.+?)\s*(-{1,2}>?>?[+\-]?\s*x?)\s*([^:]+):\s*(.*)$', stripped)
        if m2:
            src_actor = m2.group(1).strip()
            arrow = m2.group(2).strip()
            if arrow.endswith("+"):
                is_activate = True
                arrow = arrow[:-1]
            elif arrow.endswith("-"):
                is_deactivate = True
                arrow = arrow[:-1]
            dst_actor = m2.group(3).strip()
            msg_label = m2.group(4).strip()

            for actor in (src_actor, dst_actor):
                if actor not in participant_order:
                    participant_order.append(actor)

            messages.append({
                "is_note": False,
                "src": src_actor,
                "dst": dst_actor,
                "label": msg_label,
                "arrow": arrow,
                "activate": is_activate,
                "deactivate": is_deactivate,
                "note_over": "",
            })

    return title, participant_order, messages


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_sequence_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse sequenceDiagram source and return an SvgScene with lifelines and messages."""
    title, participants, messages = _parse_sequence_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("sequencediagram", content_hash)

    if not participants:
        participants = ["A", "B"]

    n = len(participants)
    p_idx = {p: i for i, p in enumerate(participants)}

    # Layout
    title_h = 28 if title else 0
    gap = max(_ACTOR_GAP, (((width_hint or 0) - _PAD_H * 2 - _ACTOR_W) // max(n - 1, 1))
              if width_hint and n > 1 else _ACTOR_GAP)
    gap = min(gap, 200)
    p_centers = [float(_PAD_H + _ACTOR_W / 2 + i * (_ACTOR_W + gap)) for i in range(n)]

    lifeline_h = float((len(messages) + 2) * _MSG_STEP)

    canvas_w = float(p_centers[-1] + _ACTOR_W / 2 + _PAD_H if participants else _PAD_H * 2 + _ACTOR_W)
    canvas_h = float(_PAD_V * 2 + title_h + _ACTOR_H * 2 + lifeline_h)

    actor_top = float(_PAD_V + title_h)
    lifeline_top = actor_top + _ACTOR_H
    lifeline_bot = lifeline_top + lifeline_h

    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    note_elements: list = []
    overlay_elements: list = []
    label_elements: list = []
    definitions: list = []

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

    # Participant boxes (top)
    for i, p_name in enumerate(participants):
        cx = p_centers[i]
        box_x = cx - _ACTOR_W / 2
        # Top box
        node_elements.append(SceneRoundedRect(
            element_id=f"{scene_id}-actor-{i}",
            x=box_x, y=actor_top,
            w=float(_ACTOR_W), h=float(_ACTOR_H),
            rx=4.0, ry=4.0,
            paint=PaintStyle(
                fill=FillStyle(color=_ACTOR_FILL),
                stroke=StrokeStyle(color=_ACTOR_STROKE, width=1.5),
            ),
            semantic_role="participant",
            data_attrs=(("data-id", p_name),),
        ))
        label_elements.append(SceneText(
            element_id=f"{scene_id}-actor-lbl-{i}",
            lines=(SceneTextLine(
                text=p_name,
                x=cx,
                y=actor_top + _ACTOR_H / 2 + _ACTOR_FONT * 0.35,
                font_size=float(_ACTOR_FONT),
                font_weight=600,
                fill_color=_ACTOR_TEXT,
            ),),
            text_anchor="middle",
        ))

        # Bottom box (mirror)
        node_elements.append(SceneRoundedRect(
            element_id=f"{scene_id}-actor-bot-{i}",
            x=box_x, y=lifeline_bot,
            w=float(_ACTOR_W), h=float(_ACTOR_H),
            rx=4.0, ry=4.0,
            paint=PaintStyle(
                fill=FillStyle(color=_ACTOR_FILL),
                stroke=StrokeStyle(color=_ACTOR_STROKE, width=1.5),
            ),
        ))
        label_elements.append(SceneText(
            element_id=f"{scene_id}-actor-bot-lbl-{i}",
            lines=(SceneTextLine(
                text=p_name, x=cx,
                y=lifeline_bot + _ACTOR_H / 2 + _ACTOR_FONT * 0.35,
                font_size=float(_ACTOR_FONT), font_weight=600, fill_color=_ACTOR_TEXT,
            ),),
            text_anchor="middle",
        ))

        # Lifeline
        edge_elements.append(SceneLine(
            element_id=f"{scene_id}-lifeline-{i}",
            x1=cx, y1=lifeline_top,
            x2=cx, y2=lifeline_bot,
            paint=PaintStyle(stroke=StrokeStyle(
                color=_LIFELINE_STROKE, width=1.0, dasharray=_LIFELINE_DASH,
            )),
        ))

    # Arrow marker definition
    arrow_marker_id = f"{scene_id}-arrow"
    definitions.append(MarkerDefinition(
        marker_id=arrow_marker_id,
        marker_type="arrow-end",
        color=_MSG_STROKE,
        size=6.0,
    ))

    # Messages
    for msg_idx, msg in enumerate(messages):
        my = float(lifeline_top + (msg_idx + 1) * _MSG_STEP)

        if msg["is_note"]:
            # Note box
            note_p = msg.get("note_over", "")
            note_x_idx = p_idx.get(note_p, 0)
            nx = p_centers[note_x_idx] - _ACTOR_W / 2
            nw = float(_ACTOR_W + 16)
            nh = float(_MSG_STEP - 8)
            note_elements.append(SceneRoundedRect(
                element_id=f"{scene_id}-note-{msg_idx}",
                x=nx, y=my - nh / 2,
                w=nw, h=nh,
                rx=3.0, ry=3.0,
                paint=PaintStyle(
                    fill=FillStyle(color=_NOTE_FILL),
                    stroke=StrokeStyle(color=_NOTE_STROKE, width=1.0),
                ),
                semantic_role="note",
            ))
            if msg["label"]:
                label_elements.append(SceneText(
                    element_id=f"{scene_id}-note-lbl-{msg_idx}",
                    lines=(SceneTextLine(
                        text=msg["label"],
                        x=nx + nw / 2, y=my,
                        font_size=float(_MSG_FONT - 1),
                        fill_color=_NOTE_TEXT,
                    ),),
                    text_anchor="middle",
                ))
            continue

        src_p = msg.get("src", "")
        dst_p = msg.get("dst", "")
        si = p_idx.get(src_p, 0)
        di = p_idx.get(dst_p, 0)
        sx = p_centers[si]
        dx = p_centers[di]
        arrow = msg.get("arrow", "->>")

        # Determine dash pattern
        is_dashed = arrow.startswith("--")

        if si == di:
            # Self-message: small loop
            offset = _ACTOR_W * 0.4
            overlay_elements.append(ScenePath(
                element_id=f"{scene_id}-msg-{msg_idx}",
                commands=(
                    ("M", sx, my),
                    ("L", sx + offset, my),
                    ("L", sx + offset, my + _MSG_STEP * 0.5),
                    ("L", sx, my + _MSG_STEP * 0.5),
                ),
                paint=PaintStyle(
                    fill=FillStyle(color="none"),
                    stroke=StrokeStyle(
                        color=_MSG_STROKE, width=1.5,
                        dasharray="4 3" if is_dashed else "",
                    ),
                ),
                marker_end=arrow_marker_id,
                semantic_role="message",
                data_attrs=(("data-label", msg["label"]),),
            ))
        else:
            direction_fac = 1.0 if dx > sx else -1.0
            end_x = dx - direction_fac * 6   # stop before arrowhead
            overlay_elements.append(SceneLine(
                element_id=f"{scene_id}-msg-{msg_idx}",
                x1=sx, y1=my, x2=end_x, y2=my,
                paint=PaintStyle(stroke=StrokeStyle(
                    color=_MSG_STROKE, width=1.5,
                    dasharray="4 3" if is_dashed else "",
                )),
                marker_end=arrow_marker_id,
                semantic_role="message",
                data_attrs=(
                    ("data-src", src_p),
                    ("data-dst", dst_p),
                    ("data-label", msg["label"]),
                ),
            ))

        if msg["label"]:
            mid_x = (sx + dx) / 2
            label_elements.append(SceneText(
                element_id=f"{scene_id}-msg-lbl-{msg_idx}",
                lines=(SceneTextLine(
                    text=msg["label"],
                    x=mid_x,
                    y=my - 4,
                    font_size=float(_MSG_FONT),
                    fill_color=_TEXT_COLOR,
                ),),
                text_anchor="middle",
            ))

    layers = tuple([
        (LAYER_BACKGROUND, tuple(bg_elements)),
        *[
            (name, ())
            for name in LAYER_ORDER
            if name not in (LAYER_BACKGROUND, LAYER_EDGES, LAYER_NODES,
                             LAYER_NOTES, LAYER_OVERLAYS, LAYER_LABELS)
        ],
        (LAYER_EDGES, tuple(edge_elements)),
        (LAYER_NODES, tuple(node_elements)),
        (LAYER_NOTES, tuple(note_elements)),
        (LAYER_OVERLAYS, tuple(overlay_elements)),
        (LAYER_LABELS, tuple(label_elements)),
    ])

    n_msgs = sum(1 for m in messages if not m["is_note"])
    return SvgScene(
        scene_id=scene_id,
        diagram_type="sequencediagram",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=title or "Sequence diagram",
            description=f"Sequence diagram with {len(participants)} participants and {n_msgs} messages",
        ),
        definitions=tuple(definitions),
        layers=layers,
    )
