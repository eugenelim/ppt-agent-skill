"""mermaid_render.layout.mindmap — Native mindmap scene builder.

Radial spider layout matching _layout_mindmap() geometry, converted to SvgScene
instead of HTML. Root is placed at canvas center; branches radiate outward using
the same leaf-count angular distribution as the HTML renderer.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any

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
    SceneEllipse,
    ScenePath,
    ScenePolygon,
    SceneRoundedRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)
from ._constants import _measure_text_px


# ── Colour palette (mirrors _MINDMAP_SECTION_COLORS) ─────────────────────────

_SECTION_STROKE: tuple[str, ...] = (
    "#359467",  # teal-green
    "#6366f1",  # indigo
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#14b8a6",  # teal
    "#a855f7",  # purple
    "#ec4899",  # pink
)

_SECTION_FILL: tuple[str, ...] = (
    "rgba(53,148,103,0.08)",
    "rgba(99,102,241,0.08)",
    "rgba(245,158,11,0.08)",
    "rgba(239,68,68,0.08)",
    "rgba(20,184,166,0.08)",
    "rgba(168,85,247,0.08)",
    "rgba(236,72,153,0.08)",
)

_LEAF_FILL: tuple[str, ...] = (
    "rgba(53,148,103,0.04)",
    "rgba(99,102,241,0.04)",
    "rgba(245,158,11,0.04)",
    "rgba(239,68,68,0.04)",
    "rgba(20,184,166,0.04)",
    "rgba(168,85,247,0.04)",
    "rgba(236,72,153,0.04)",
)

_ROOT_FILL = "#f7f6f2"
_ROOT_STROKE = "#dad7ce"
_EDGE_STROKE = "rgba(100,116,139,0.6)"
_TEXT_COLOR = "#1a1a2e"
_ROOT_TEXT_COLOR = "#111827"


# ── Geometry constants (must match HTML renderer) ─────────────────────────────

_BASE_R = 85    # root → depth-1 radius in px
_STEP_R = 70    # additional radius per depth level
_MARGIN = 90    # px clearance beyond outermost ring
_ROOT_DIAM = 60
_NODE_H = 32
_NODE_W_MIN = 80


# ── Parser (mirrors _layout_mindmap source parsing) ───────────────────────────

def _parse_mindmap_source(src: str) -> list[dict]:
    """Return flat list of {depth, label, shape} from mindmap source."""
    lines = src.splitlines()
    # Skip the directive line ("mindmap") and frontmatter
    content_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith(("%%", "//")):
            content_start = i + 1
            break

    flat: list[dict] = []
    for raw in lines[content_start:]:
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith(("%%", "//")):
            continue
        indent = len(line) - len(line.lstrip())
        raw_node = line.strip()
        raw_node = re.sub(r'\s*:{2,3}[\w-]+(?:\([^)]*\))?', '', raw_node).strip()

        shape = "default"
        lbl = raw_node
        m = re.match(r'^\w+\(\((.+?)\)\)', raw_node)
        if m:
            lbl, shape = m.group(1), "circle"
        else:
            m = re.match(r'^\w+\)\)(.+?)\(\(', raw_node)
            if m:
                lbl, shape = m.group(1), "cloud"
            else:
                m = re.match(r'^\w+\[(.+?)\]', raw_node)
                if m:
                    lbl, shape = m.group(1), "rect"
                else:
                    m = re.match(r'^\w+\((.+?)\)', raw_node)
                    if m:
                        lbl, shape = m.group(1), "pill"
                    else:
                        lbl = re.sub(r'^[\[\(\{:]+|[\]\)\}]+$', '', raw_node).strip()

        lbl = re.sub(r'\*\*(.+?)\*\*', r'\1', lbl)
        lbl = re.sub(r'\*(.+?)\*', r'\1', lbl)
        if lbl:
            flat.append({"depth": indent, "label": lbl, "shape": shape})

    return flat


def _count_leaves(idx: int, children: list[list[int]]) -> int:
    if not children[idx]:
        return 1
    return sum(_count_leaves(c, children) for c in children[idx])


def _build_tree(flat: list[dict]) -> tuple[list[list[int]], list[int], list[int]]:
    """Build parent/children arrays and tree_depth from flat node list."""
    n = len(flat)
    children: list[list[int]] = [[] for _ in range(n)]
    parent_of: list[int] = [-1] * n
    for i in range(1, n):
        for j in range(i - 1, -1, -1):
            if flat[j]["depth"] < flat[i]["depth"]:
                parent_of[i] = j
                children[j].append(i)
                break

    tree_depth: list[int] = [0] * n
    for i in range(1, n):
        if parent_of[i] >= 0:
            tree_depth[i] = tree_depth[parent_of[i]] + 1

    return children, parent_of, tree_depth


def _radial_positions(
    children: list[list[int]],
    cx: float,
    cy: float,
) -> dict[int, tuple[float, float]]:
    """Compute (x, y) float positions via recursive radial placement."""
    positions: dict[int, tuple[float, float]] = {0: (cx, cy)}

    def _place(idx: int, start: float, end: float, depth: int) -> None:
        ch = children[idx]
        if not ch:
            return
        total = sum(_count_leaves(c, children) for c in ch)
        cur = start
        for ci in ch:
            leaves = _count_leaves(ci, children)
            span = (end - start) * leaves / total
            mid = cur + span / 2
            r = _BASE_R + depth * _STEP_R
            positions[ci] = (
                cx + r * math.cos(math.radians(mid)),
                cy + r * math.sin(math.radians(mid)),
            )
            _place(ci, cur, cur + span, depth + 1)
            cur += span

    _place(0, -90.0, 270.0, 1)
    return positions


# ── Node half-dimensions ──────────────────────────────────────────────────────

def _node_hw(
    flat: list[dict], tree_depth: list[int], idx: int,
) -> tuple[float, float]:
    nd = flat[idx]
    depth_i = tree_depth[idx]
    shape_i = nd["shape"]
    if depth_i == 0 and shape_i in ("circle", "default"):
        return _ROOT_DIAM / 2, _ROOT_DIAM / 2
    if shape_i == "circle":
        return 24.0, 24.0
    lbl_w = max(_NODE_W_MIN, _measure_text_px(nd["label"]) + 16)
    return lbl_w / 2, _NODE_H / 2


def _boundary_pt(
    ox: float, oy: float, tx: float, ty: float,
    hw: float, hh: float, is_circle: bool,
) -> tuple[float, float]:
    ddx, ddy = tx - ox, ty - oy
    dist = math.hypot(ddx, ddy) or 1.0
    if is_circle:
        return ox + ddx / dist * hw, oy + ddy / dist * hh
    t = float("inf")
    if ddx != 0:
        t = min(t, hw / abs(ddx))
    if ddy != 0:
        t = min(t, hh / abs(ddy))
    return ox + ddx * t, oy + ddy * t


# ── Scene element builders ────────────────────────────────────────────────────

def _node_fill_stroke(
    depth: int, sec: int, shape: str,
) -> tuple[str, str]:
    """Return (fill_color, stroke_color) for a node."""
    if depth == 0:
        return _ROOT_FILL, _ROOT_STROKE
    if depth == 1:
        sec_idx = sec % len(_SECTION_FILL) if sec >= 0 else 0
        return _SECTION_FILL[sec_idx], _SECTION_STROKE[sec_idx]
    sec_idx = sec % len(_LEAF_FILL) if sec >= 0 else 0
    return _LEAF_FILL[sec_idx], _SECTION_STROKE[sec_idx % len(_SECTION_STROKE)]


def _make_node_element(
    idx: int, flat: list[dict], tree_depth: list[int],
    positions: dict[int, tuple[float, float]],
    section_of: list[int],
    eid_prefix: str,
) -> list:
    """Build scene elements for a single mindmap node."""
    nd = flat[idx]
    px, py = positions[idx]
    depth = tree_depth[idx]
    shape = nd["shape"]
    sec = section_of[idx]
    label = nd["label"]
    fill_c, stroke_c = _node_fill_stroke(depth, sec, shape)
    elements = []

    font_size = 13.0 if depth == 0 else 12.0
    font_weight = 700 if depth == 0 else 400
    text_color = _ROOT_TEXT_COLOR if depth == 0 else _TEXT_COLOR

    if depth == 0 and shape in ("circle", "default"):
        r = _ROOT_DIAM / 2
        elements.append(SceneCircle(
            element_id=f"{eid_prefix}n{idx}",
            cx=px, cy=py, r=r,
            paint=PaintStyle(
                fill=FillStyle(color=fill_c),
                stroke=StrokeStyle(color=stroke_c, width=1.5),
            ),
            css_classes=("mindmap-root",),
        ))
    elif shape == "circle":
        r = 24.0
        elements.append(SceneCircle(
            element_id=f"{eid_prefix}n{idx}",
            cx=px, cy=py, r=r,
            paint=PaintStyle(
                fill=FillStyle(color=fill_c),
                stroke=StrokeStyle(color=stroke_c, width=1.0),
            ),
            css_classes=("mindmap-node",),
        ))
    elif shape == "rect":
        hw, hh = _node_hw(flat, tree_depth, idx)
        elements.append(SceneRoundedRect(
            element_id=f"{eid_prefix}n{idx}",
            x=px - hw, y=py - hh, w=hw * 2, h=hh * 2,
            rx=4, ry=4,
            paint=PaintStyle(
                fill=FillStyle(color=fill_c),
                stroke=StrokeStyle(color=stroke_c, width=1.0),
            ),
            css_classes=("mindmap-node",),
        ))
    else:
        # pill (default rounded) / cloud
        hw, hh = _node_hw(flat, tree_depth, idx)
        elements.append(SceneRoundedRect(
            element_id=f"{eid_prefix}n{idx}",
            x=px - hw, y=py - hh, w=hw * 2, h=hh * 2,
            rx=hh, ry=hh,
            paint=PaintStyle(
                fill=FillStyle(color=fill_c),
                stroke=StrokeStyle(color=stroke_c, width=1.0),
            ),
            css_classes=("mindmap-node",),
        ))

    # Label
    elements.append(SceneText(
        element_id=f"{eid_prefix}t{idx}",
        lines=(SceneTextLine(
            text=label,
            x=px, y=py + font_size * 0.35,
            font_size=font_size,
            font_weight=font_weight,
            fill_color=text_color,
        ),),
        text_anchor="middle",
        css_classes=("mindmap-label",),
    ))

    return elements


def _make_edge_element(
    idx: int, parent_of: list[int], flat: list[dict],
    tree_depth: list[int], positions: dict[int, tuple[float, float]],
    eid_prefix: str,
) -> list:
    """Build a curved edge ScenePath from node idx to its parent."""
    p = parent_of[idx]
    if p < 0:
        return []

    px_p, py_p = positions[p]
    px_c, py_c = positions[idx]
    cx = (max(positions[i][0] for i in range(len(flat))) + min(positions[i][0] for i in range(len(flat)))) / 2
    cy = (max(positions[i][1] for i in range(len(flat))) + min(positions[i][1] for i in range(len(flat)))) / 2

    p_hw, p_hh = _node_hw(flat, tree_depth, p)
    c_hw, c_hh = _node_hw(flat, tree_depth, idx)
    p_is_circ = (flat[p]["shape"] in ("circle", "default") and tree_depth[p] == 0) or flat[p]["shape"] == "circle"
    c_is_circ = flat[idx]["shape"] == "circle"

    sx, sy = _boundary_pt(px_p, py_p, px_c, py_c, p_hw, p_hh, p_is_circ)
    ex, ey = _boundary_pt(px_c, py_c, px_p, py_p, c_hw, c_hh, c_is_circ)

    mx = (sx + ex) / 2
    my = (sy + ey) / 2
    dx, dy = mx - cx, my - cy
    dl = math.hypot(dx, dy) or 1.0
    qx = mx + dx / dl * 18
    qy = my + dy / dl * 18

    cmds = (
        ("M", float(sx), float(sy)),
        ("Q", float(qx), float(qy), float(ex), float(ey)),
    )
    return [ScenePath(
        element_id=f"{eid_prefix}e{p}-{idx}",
        commands=cmds,
        paint=PaintStyle(
            fill=FillStyle(color="none"),
            stroke=StrokeStyle(color=_EDGE_STROKE, width=1.5),
        ),
        css_classes=("mindmap-edge",),
    )]


# ── Public entry point ────────────────────────────────────────────────────────

def layout_mindmap_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse mindmap source and return a fully-laid-out SvgScene."""
    flat = _parse_mindmap_source(src)
    if not flat:
        raise ValueError("No nodes found in mindmap.")

    # Normalise indentation to depth 0
    min_d = min(n["depth"] for n in flat)
    for n in flat:
        n["depth"] -= min_d

    n_nodes = len(flat)
    children, parent_of, tree_depth = _build_tree(flat)

    # Section colour propagation
    section_of: list[int] = [-1] * n_nodes
    for sect_idx, child_idx in enumerate(children[0]):
        section_of[child_idx] = sect_idx
    pending = list(children[0])
    while pending:
        cur = pending.pop()
        for ci in children[cur]:
            section_of[ci] = section_of[cur]
            pending.append(ci)

    max_depth = max(tree_depth) if tree_depth else 1
    max_r = _BASE_R + max_depth * _STEP_R
    min_side = 2 * (max_r + _MARGIN)
    canvas_w = float(max(width_hint or 480, int(min_side)))
    canvas_h = canvas_w
    cx = canvas_w / 2
    cy = canvas_h / 2

    positions = _radial_positions(children, cx, cy)

    # Deterministic scene ID
    content = f"mindmap:{canvas_w}:{canvas_h}:{','.join(n['label'] for n in flat)}"
    content_hash = int(hashlib.sha256(content.encode()).hexdigest(), 16)
    scene_id = make_scene_id("mindmap", content_hash)
    eid_prefix = hashlib.sha256(scene_id.encode()).hexdigest()[:6]

    edge_els: list = []
    node_els: list = []
    label_els: list = []

    for i in range(1, n_nodes):
        edge_els.extend(_make_edge_element(i, parent_of, flat, tree_depth, positions, eid_prefix))

    for i in range(n_nodes):
        els = _make_node_element(i, flat, tree_depth, positions, section_of, eid_prefix)
        for el in els:
            if isinstance(el, SceneText):
                label_els.append(el)
            else:
                node_els.append(el)

    layers = tuple(
        (name, tuple(elems)) for name, elems in [
            (LAYER_BACKGROUND, []),
            (LAYER_BOUNDARIES, []),
            (LAYER_EDGES, edge_els),
            (LAYER_NODES, node_els),
            (LAYER_LABELS, label_els),
            (LAYER_NOTES, []),
            (LAYER_OVERLAYS, []),
        ]
    )

    return SvgScene(
        scene_id=scene_id,
        diagram_type="mindmap",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title="mindmap",
            description="Mermaid mindmap diagram",
        ),
        layers=layers,
    )
