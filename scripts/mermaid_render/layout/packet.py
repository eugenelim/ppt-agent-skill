"""mermaid_render.layout.packet — Native packet-beta scene builder.

Parses protocol packet field definitions and renders a horizontal band
diagram where each field's width is proportional to its bit span.
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
    SceneRoundedRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)


# ── Color tokens ──────────────────────────────────────────────────────────────

_BG_FILL = "#f8fafc"
_FIELD_FILL = "#dbeafe"
_FIELD_STROKE = "#93c5fd"
_TEXT_COLOR = "#1e3a5f"
_DIM_COLOR = "#6b7280"
_TITLE_COLOR = "#111827"
_BIT_COLOR = "#94a3b8"

# ── Layout constants ──────────────────────────────────────────────────────────

_ROW_H = 40          # height of the packet band
_BIT_RULER_H = 16    # height of the bit number ruler above the band
_PAD_H = 32
_PAD_V = 24
_TITLE_H = 28
_FONT_SIZE = 12
_BIT_FONT = 9
_TITLE_FONT = 16
_WRAP_BITS = 32      # wrap to new row every 32 bits


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_packet_source(src: str) -> tuple[str, list[tuple[str, int]]]:
    """Return (title, [(label, bit_span), ...]).

    Accepts two syntaxes:
      ``0-15: "Label"``   — absolute bit range (span = end - start + 1)
      ``+8: "Label"``     — relative width in bits
    """
    title = ""
    fields: list[tuple[str, int]] = []

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("packet") or stripped.startswith("%%"):
            continue
        if stripped.lower().startswith("title "):
            title = stripped[6:].strip()
            continue
        if stripped.lower() == "title":
            continue

        # Absolute range: 0-15: "Label"
        m = re.match(r'^(\d+)\s*-\s*(\d+)\s*:\s*"([^"]*)"', stripped)
        if m:
            start, end, label = int(m.group(1)), int(m.group(2)), m.group(3)
            fields.append((label, max(1, end - start + 1)))
            continue

        # Relative: +8: "Label"
        m = re.match(r'^\+\s*(\d+)\s*:\s*"([^"]*)"', stripped)
        if m:
            bits, label = int(m.group(1)), m.group(2)
            fields.append((label, max(1, bits)))
            continue

        # Without quotes: 0-15: Label
        m = re.match(r'^(\d+)\s*-\s*(\d+)\s*:\s*(.+)', stripped)
        if m:
            start, end, label = int(m.group(1)), int(m.group(2)), m.group(3).strip().strip('"')
            fields.append((label, max(1, end - start + 1)))
            continue

    return title, fields


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_packet_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse packet source and return an SvgScene with field band."""
    title, fields = _parse_packet_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("packet-beta", content_hash)

    if not fields:
        w = max(width_hint or 400, 400)
        h = 120
        return SvgScene(
            scene_id=scene_id,
            diagram_type="packet-beta",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title=title or "Packet diagram"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    total_bits = sum(span for _, span in fields)

    # Split fields into rows of _WRAP_BITS bits each
    rows: list[list[tuple[str, int]]] = []  # each row: [(label, span)]
    cur_row: list[tuple[str, int]] = []
    cur_bits = 0
    for label, span in fields:
        if cur_bits + span > _WRAP_BITS and cur_bits > 0:
            rows.append(cur_row)
            cur_row = []
            cur_bits = 0
        cur_row.append((label, span))
        cur_bits += span
    if cur_row:
        rows.append(cur_row)

    title_h = _TITLE_H if title else 0
    n_rows = len(rows)
    row_slot_h = _ROW_H + _BIT_RULER_H + 8

    content_w = max(width_hint - _PAD_H * 2, 400) if width_hint else 600
    canvas_w = float(content_w + _PAD_H * 2)
    canvas_h = float(title_h + _PAD_V * 2 + n_rows * row_slot_h + 8)

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

    for row_idx, row_fields in enumerate(rows):
        row_total_bits = sum(s for _, s in row_fields)
        if row_total_bits == 0:
            row_total_bits = 1
        row_y = float(title_h + _PAD_V + row_idx * row_slot_h)
        band_y = float(row_y + _BIT_RULER_H + 4)

        # Bit ruler numbers
        x_cursor = float(_PAD_H)
        bit_offset = sum(sum(s for _, s in r) for r in rows[:row_idx])
        for label, span in row_fields:
            frac = span / row_total_bits
            field_w = frac * content_w

            # Bit label
            label_elements.append(SceneText(
                element_id=f"{scene_id}-bit-{row_idx}-{bit_offset}",
                lines=(SceneTextLine(
                    text=str(bit_offset),
                    x=x_cursor + 2,
                    y=row_y + _BIT_FONT + 2,
                    font_size=float(_BIT_FONT),
                    fill_color=_BIT_COLOR,
                ),),
                text_anchor="start",
            ))

            # Field rect
            node_elements.append(SceneRect(
                element_id=f"{scene_id}-field-{row_idx}-{bit_offset}",
                x=x_cursor,
                y=band_y,
                w=field_w,
                h=float(_ROW_H),
                paint=PaintStyle(
                    fill=FillStyle(color=_FIELD_FILL),
                    stroke=StrokeStyle(color=_FIELD_STROKE, width=1.0),
                ),
                semantic_role="field",
                data_attrs=(("data-label", label), ("data-bits", str(span))),
            ))

            # Field label (clipped if too narrow)
            label_elements.append(SceneText(
                element_id=f"{scene_id}-flabel-{row_idx}-{bit_offset}",
                lines=(SceneTextLine(
                    text=label,
                    x=x_cursor + field_w / 2,
                    y=band_y + _ROW_H / 2 + _FONT_SIZE * 0.35,
                    font_size=float(_FONT_SIZE),
                    fill_color=_TEXT_COLOR,
                ),),
                text_anchor="middle",
            ))

            x_cursor += field_w
            bit_offset += span

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
        diagram_type="packet-beta",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=title or "Packet diagram",
            description=f"Protocol packet with {len(fields)} fields ({total_bits} bits)",
        ),
        layers=layers,
    )
