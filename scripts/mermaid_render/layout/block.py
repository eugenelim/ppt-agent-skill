"""mermaid_render.layout.block — Native block-beta scene builder.

Parses ``block-beta`` source and renders a grid of labelled blocks
with optional arrows between them.
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
    MarkerDefinition,
    PaintStyle,
    SceneLine,
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
_BLOCK_FILL = "#dbeafe"
_BLOCK_STROKE = "#93c5fd"
_BLOCK_TEXT = "#1e3a8a"
_EDGE_STROKE = "#374151"
_TITLE_COLOR = "#111827"
_SPACE_FILL = "none"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD_H = 32
_PAD_V = 32
_CELL_W = 120
_CELL_H = 60
_CELL_GAP = 16
_RX = 6
_FONT_SIZE = 13
_TITLE_FONT = 16
_TITLE_H = 28


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_block_label(token: str) -> tuple[str, str]:
    """Parse 'id["label"]' or 'id[label]' or 'id' → (id, label)."""
    m = re.match(r'^([^[\s]+)\["([^"]*)"\]', token)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r'^([^[\s]+)\(["(]?([^")\]]*)[")?\]]?\)?', token)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r'^([^[\s(]+)\[([^\]]*)\]', token)
    if m:
        return m.group(1), m.group(2)
    return token.split()[0], token.split()[0]


def _parse_block_source(src: str) -> tuple[int, list[list[tuple[str, str]]], list[tuple[str, str]]]:
    """Return (columns, grid_rows, edges).

    grid_rows: list of row; each row is a list of (id, label) tuples.
    edges: [(src_id, dst_id)]
    """
    columns = 1
    rows: list[list[tuple[str, str]]] = []
    edges: list[tuple[str, str]] = []
    cur_row: list[tuple[str, str]] = []
    in_block = False

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("block-beta") or stripped.startswith("%%"):
            continue

        # columns N
        m = re.match(r'^columns\s+(\d+)', stripped, re.IGNORECASE)
        if m:
            columns = int(m.group(1))
            continue

        # Arrow line: A --> B --> C
        if "-->" in stripped and not stripped.startswith('"'):
            parts = re.split(r'\s*-->\s*', stripped)
            block_ids_only = [_parse_block_label(p.strip())[0] for p in parts if p.strip()]
            for i in range(len(block_ids_only) - 1):
                edges.append((block_ids_only[i], block_ids_only[i + 1]))
            # Also add blocks from the first part if they have labels
            for p in parts:
                token = p.strip()
                if token and "[" in token:
                    bid, blabel = _parse_block_label(token)
                    # Find or add to a row
                    found = any(bid == b for r in rows for b, _ in r)
                    if not found:
                        if not rows:
                            rows.append([])
                        rows[-1].append((bid, blabel))
            continue

        # Block row: tokens separated by spaces
        # Each token can be: id["label"], space:N (span), id
        tokens = re.findall(r'\w+(?:\["[^"]*"\]|\[[^\]]*\]|\([^)]*\))?', stripped)
        if tokens:
            row: list[tuple[str, str]] = []
            for tok in tokens:
                if tok.startswith("space"):
                    m = re.match(r'^space(?::(\d+))?', tok)
                    n_space = int(m.group(1)) if (m and m.group(1)) else 1
                    for _ in range(n_space):
                        row.append(("", ""))
                else:
                    bid, blabel = _parse_block_label(tok)
                    row.append((bid, blabel))
            if row:
                rows.append(row)

    return columns, rows, edges


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_block_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse block-beta source and return an SvgScene with grid of blocks."""
    columns, rows, edges = _parse_block_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("block-beta", content_hash)

    if not rows:
        w = max(width_hint or 400, 400)
        h = 160
        return SvgScene(
            scene_id=scene_id,
            diagram_type="block-beta",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title="Block diagram"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    n_rows = len(rows)
    max_cols = max((len(r) for r in rows), default=columns)
    effective_cols = max(columns, max_cols)

    # Scale cell size to fit width_hint
    if width_hint:
        available_w = width_hint - _PAD_H * 2
        computed_cell_w = max(60, (available_w - (effective_cols - 1) * _CELL_GAP) // effective_cols)
    else:
        computed_cell_w = _CELL_W

    canvas_w = float(_PAD_H * 2 + effective_cols * computed_cell_w + (effective_cols - 1) * _CELL_GAP)
    canvas_h = float(_PAD_V * 2 + n_rows * _CELL_H + (n_rows - 1) * _CELL_GAP)

    # Build block positions
    block_pos: dict[str, tuple[float, float]] = {}
    block_center: dict[str, tuple[float, float]] = {}

    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []

    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    for ri, row in enumerate(rows):
        row_y = float(_PAD_V + ri * (_CELL_H + _CELL_GAP))
        for ci, (bid, blabel) in enumerate(row):
            cell_x = float(_PAD_H + ci * (computed_cell_w + _CELL_GAP))

            if bid:  # skip space cells
                block_pos[bid] = (cell_x, row_y)
                block_center[bid] = (cell_x + computed_cell_w / 2, row_y + _CELL_H / 2)

                node_elements.append(SceneRoundedRect(
                    element_id=f"{scene_id}-block-{bid}",
                    x=cell_x, y=row_y,
                    w=float(computed_cell_w), h=float(_CELL_H),
                    rx=float(_RX), ry=float(_RX),
                    paint=PaintStyle(
                        fill=FillStyle(color=_BLOCK_FILL),
                        stroke=StrokeStyle(color=_BLOCK_STROKE, width=1.5),
                    ),
                    semantic_role="block",
                    data_attrs=(("data-id", bid), ("data-label", blabel)),
                ))

                label_elements.append(SceneText(
                    element_id=f"{scene_id}-block-lbl-{bid}",
                    lines=(SceneTextLine(
                        text=blabel or bid,
                        x=cell_x + computed_cell_w / 2,
                        y=row_y + _CELL_H / 2 + _FONT_SIZE * 0.35,
                        font_size=float(_FONT_SIZE),
                        font_weight=500,
                        fill_color=_BLOCK_TEXT,
                    ),),
                    text_anchor="middle",
                ))

    # Draw edges
    for eid_src, eid_dst in edges:
        if eid_src not in block_center or eid_dst not in block_center:
            continue
        sx, sy = block_center[eid_src]
        dx, dy = block_center[eid_dst]
        edge_elements.append(SceneLine(
            element_id=f"{scene_id}-edge-{eid_src}-{eid_dst}",
            x1=sx, y1=sy, x2=dx, y2=dy,
            paint=PaintStyle(stroke=StrokeStyle(color=_EDGE_STROKE, width=1.5)),
            semantic_role="edge",
            data_attrs=(("data-src", eid_src), ("data-dst", eid_dst)),
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

    all_blocks = [bid for r in rows for bid, _ in r if bid]
    return SvgScene(
        scene_id=scene_id,
        diagram_type="block-beta",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title="Block diagram",
            description=f"Block diagram with {len(all_blocks)} blocks and {len(edges)} edges",
        ),
        layers=layers,
    )
