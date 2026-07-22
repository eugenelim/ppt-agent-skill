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


# ── Tidy-tree layout (Buchheim variable-size algorithm) ──────────────────────

_TT_H_GAP = 60.0   # horizontal gap between depth levels
_TT_V_GAP = 14.0   # vertical gap between siblings
_TT_MARGIN = 40.0  # canvas margin for tidy-tree layout


class _TidyNode:
    """Working node for the Buchheim tidy-tree layout algorithm."""

    __slots__ = (
        "idx", "children", "parent",
        "hh", "hw",
        "prelim", "mod", "shift", "change",
        "thread", "ancestor",
        "child_index",
        "y", "x",
    )

    def __init__(
        self, idx: int, parent: "Any", hh: float, hw: float, child_index: int
    ) -> None:
        self.idx = idx
        self.children: list["_TidyNode"] = []
        self.parent = parent
        self.hh = hh
        self.hw = hw
        self.prelim = 0.0
        self.mod = 0.0
        self.shift = 0.0
        self.change = 0.0
        self.thread: "_TidyNode | None" = None
        self.ancestor: "_TidyNode" = self  # default self-reference
        self.child_index = child_index
        self.y = 0.0
        self.x = 0.0


def _tt_sep(v: _TidyNode, w: _TidyNode) -> float:
    return v.hh + w.hh + _TT_V_GAP


def _tt_next_left(v: _TidyNode) -> "_TidyNode | None":
    return v.children[0] if v.children else v.thread


def _tt_next_right(v: _TidyNode) -> "_TidyNode | None":
    return v.children[-1] if v.children else v.thread


def _tt_move_subtree(w_minus: _TidyNode, w_plus: _TidyNode, shift: float) -> None:
    subtrees = w_plus.child_index - w_minus.child_index
    if subtrees == 0:
        return
    w_plus.change -= shift / subtrees
    w_plus.shift += shift
    w_minus.change += shift / subtrees
    w_plus.prelim += shift
    w_plus.mod += shift


def _tt_execute_shifts(v: _TidyNode) -> None:
    shift = 0.0
    change = 0.0
    for w in reversed(v.children):
        w.prelim += shift
        w.mod += shift
        change += w.change
        shift += w.shift + change


def _tt_ancestor(
    vil: _TidyNode, v: _TidyNode, default_ancestor: _TidyNode
) -> _TidyNode:
    if vil.ancestor is not None and vil.ancestor.parent is v.parent:
        return vil.ancestor
    return default_ancestor


def _tt_apportion(v: _TidyNode, default_ancestor: _TidyNode) -> _TidyNode:
    if v.child_index == 0:
        return default_ancestor
    w = v.parent.children[v.child_index - 1]  # left sibling

    vir = vor = v
    vil = w
    vol = v.parent.children[0]  # leftmost sibling

    sir = vir.mod
    sor = vor.mod
    sil = vil.mod
    sol = vol.mod

    while _tt_next_right(vil) and _tt_next_left(vir):
        vil = _tt_next_right(vil)
        vir = _tt_next_left(vir)
        vol = _tt_next_left(vol)
        vor = _tt_next_right(vor)
        vor.ancestor = v

        shift = (vil.prelim + sil) - (vir.prelim + sir) + _tt_sep(vil, vir)
        if shift > 0:
            a = _tt_ancestor(vil, v, default_ancestor)
            _tt_move_subtree(a, v, shift)
            sir += shift
            sor += shift

        sil += vil.mod
        sir += vir.mod
        sol += vol.mod
        sor += vor.mod

    if _tt_next_right(vil) and not _tt_next_right(vor):
        vor.thread = _tt_next_right(vil)
        vor.mod += sil - sor

    if _tt_next_left(vir) and not _tt_next_left(vol):
        vol.thread = _tt_next_left(vir)
        vol.mod += sir - sol
        default_ancestor = v

    return default_ancestor


def _tt_first_walk(v: _TidyNode) -> None:
    if not v.children:
        if v.child_index > 0:
            w = v.parent.children[v.child_index - 1]
            v.prelim = w.prelim + _tt_sep(w, v)
        else:
            v.prelim = 0.0
    else:
        default_ancestor = v.children[0]
        for w in v.children:
            _tt_first_walk(w)
            default_ancestor = _tt_apportion(w, default_ancestor)
        _tt_execute_shifts(v)
        midpoint = (v.children[0].prelim + v.children[-1].prelim) / 2.0
        if v.child_index > 0:
            w = v.parent.children[v.child_index - 1]
            v.prelim = w.prelim + _tt_sep(w, v)
            v.mod = v.prelim - midpoint
        else:
            v.prelim = midpoint


def _tt_second_walk(
    v: _TidyNode, m: float, level_x: list[float], depth: int
) -> None:
    if v.idx >= 0:
        v.y = v.prelim + m
        v.x = level_x[depth] if depth < len(level_x) else level_x[-1]
    for w in v.children:
        _tt_second_walk(w, m + v.mod, level_x, depth + 1)


def _tidy_tree_positions(
    flat: list[dict],
    children: list[list[int]],
    tree_depth: list[int],
) -> dict[int, tuple[float, float]]:
    """Buchheim variable-size tidy-tree layout.

    Returns (x, y) relative to root at (0, 0).
    Even-indexed root children → right side (x > 0).
    Odd-indexed root children → left side (x < 0).
    """
    n = len(flat)
    hh_list = [_node_hw(flat, tree_depth, i)[1] for i in range(n)]
    hw_list = [_node_hw(flat, tree_depth, i)[0] for i in range(n)]

    root_ch = children[0]
    right_roots = [root_ch[i] for i in range(0, len(root_ch), 2)]
    left_roots = [root_ch[i] for i in range(1, len(root_ch), 2)]

    max_td = max(tree_depth) if tree_depth else 1
    max_hw_d: list[float] = [0.0] * (max_td + 1)
    for i in range(n):
        d = tree_depth[i]
        max_hw_d[d] = max(max_hw_d[d], hw_list[i])

    level_x: list[float] = [0.0]
    for d in range(1, max_td + 1):
        level_x.append(
            level_x[-1] + max_hw_d[d - 1] + max_hw_d[d] + _TT_H_GAP
        )

    def _build_node(idx: int, parent: _TidyNode, ci: int) -> _TidyNode:
        node = _TidyNode(idx, parent, hh_list[idx], hw_list[idx], ci)
        for k, child_idx in enumerate(children[idx]):
            node.children.append(_build_node(child_idx, node, k))
        return node

    def _collect_real(node: _TidyNode, out: list) -> None:
        if node.idx >= 0:
            out.append(node)
        for ch in node.children:
            _collect_real(ch, out)

    def _layout_side(side_roots: list[int]) -> dict[int, tuple[float, float]]:
        if not side_roots:
            return {}
        vroot = _TidyNode(-1, None, 0.0, 0.0, 0)
        for ci, ridx in enumerate(side_roots):
            vroot.children.append(_build_node(ridx, vroot, ci))
        _tt_first_walk(vroot)
        _tt_second_walk(vroot, 0.0, level_x, 0)
        real: list[_TidyNode] = []
        _collect_real(vroot, real)
        if not real:
            return {}
        y_lo = min(nd.y - hh_list[nd.idx] for nd in real)
        y_hi = max(nd.y + hh_list[nd.idx] for nd in real)
        y_center = (y_lo + y_hi) / 2.0
        return {nd.idx: (nd.x, nd.y - y_center) for nd in real}

    right_pos = _layout_side(right_roots)
    left_pos = {idx: (-x, y) for idx, (x, y) in _layout_side(left_roots).items()}

    positions: dict[int, tuple[float, float]] = {0: (0.0, 0.0)}
    positions.update(right_pos)
    positions.update(left_pos)
    return positions


def _make_tidy_edge_element(
    idx: int,
    parent_of: list[int],
    flat: list[dict],
    tree_depth: list[int],
    positions: dict[int, tuple[float, float]],
    eid_prefix: str,
) -> list:
    """Cubic-bezier S-curve edge for the tidy-tree layout."""
    p = parent_of[idx]
    if p < 0:
        return []

    px_p, py_p = positions[p]
    px_c, py_c = positions[idx]
    p_hw, p_hh = _node_hw(flat, tree_depth, p)
    c_hw, c_hh = _node_hw(flat, tree_depth, idx)
    p_is_circ = (
        flat[p]["shape"] in ("circle", "default") and tree_depth[p] == 0
    ) or flat[p]["shape"] == "circle"
    c_is_circ = flat[idx]["shape"] == "circle"

    sx, sy = _boundary_pt(px_p, py_p, px_c, py_c, p_hw, p_hh, p_is_circ)
    ex, ey = _boundary_pt(px_c, py_c, px_p, py_p, c_hw, c_hh, c_is_circ)

    mid_x = (sx + ex) / 2.0
    cmds = (
        ("M", float(sx), float(sy)),
        ("C", float(mid_x), float(sy), float(mid_x), float(ey), float(ex), float(ey)),
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

def layout_mindmap_scene(
    src: str, *, width_hint: int = 0, layout: str = "radial"
) -> SvgScene:
    """Parse mindmap source and return a fully-laid-out SvgScene.

    layout="radial"     — default radial spider layout (unchanged behaviour)
    layout="tidy-tree"  — Buchheim horizontal tidy-tree, activated by frontmatter
    """
    flat = _parse_mindmap_source(src)
    if not flat:
        raise ValueError("No nodes found in mindmap.")

    min_d = min(n["depth"] for n in flat)
    for n in flat:
        n["depth"] -= min_d

    n_nodes = len(flat)
    children, parent_of, tree_depth = _build_tree(flat)

    # Section colour propagation (shared between both layout modes)
    section_of: list[int] = [-1] * n_nodes
    for sect_idx, child_idx in enumerate(children[0]):
        section_of[child_idx] = sect_idx
    pending = list(children[0])
    while pending:
        cur = pending.pop()
        for ci in children[cur]:
            section_of[ci] = section_of[cur]
            pending.append(ci)

    if layout == "tidy-tree":
        # ── Tidy-tree branch ─────────────────────────────────────────────────
        positions_rel = _tidy_tree_positions(flat, children, tree_depth)
        hh_list = [_node_hw(flat, tree_depth, i)[1] for i in range(n_nodes)]
        hw_list = [_node_hw(flat, tree_depth, i)[0] for i in range(n_nodes)]

        x_min = min(positions_rel[i][0] - hw_list[i] for i in range(n_nodes))
        x_max = max(positions_rel[i][0] + hw_list[i] for i in range(n_nodes))
        y_min = min(positions_rel[i][1] - hh_list[i] for i in range(n_nodes))
        y_max = max(positions_rel[i][1] + hh_list[i] for i in range(n_nodes))

        natural_w = x_max - x_min + 2 * _TT_MARGIN
        canvas_w = float(max(width_hint or 0, int(natural_w)))
        natural_h = y_max - y_min + 2 * _TT_MARGIN
        canvas_h = max(240.0, natural_h)

        # Centre layout on canvas (extra space distributed symmetrically)
        root_cx = (canvas_w - (x_max - x_min)) / 2.0 - x_min
        root_cy = (canvas_h - (y_max - y_min)) / 2.0 - y_min

        positions = {
            i: (positions_rel[i][0] + root_cx, positions_rel[i][1] + root_cy)
            for i in range(n_nodes)
        }

        edge_fn = _make_tidy_edge_element
        content = f"mindmap:tidy:{canvas_w}:{canvas_h}:{','.join(n['label'] for n in flat)}"
    else:
        # ── Radial branch (original behaviour, unchanged) ────────────────────
        max_depth = max(tree_depth) if tree_depth else 1
        max_r = _BASE_R + max_depth * _STEP_R
        min_side = 2 * (max_r + _MARGIN)
        canvas_w = float(max(width_hint or 480, int(min_side)))
        canvas_h = canvas_w
        cx = canvas_w / 2
        cy = canvas_h / 2
        positions = _radial_positions(children, cx, cy)
        edge_fn = _make_edge_element
        content = f"mindmap:{canvas_w}:{canvas_h}:{','.join(n['label'] for n in flat)}"
    content_hash = int(hashlib.sha256(content.encode()).hexdigest(), 16)
    scene_id = make_scene_id("mindmap", content_hash)
    eid_prefix = hashlib.sha256(scene_id.encode()).hexdigest()[:6]

    edge_els: list = []
    node_els: list = []
    label_els: list = []

    for i in range(1, n_nodes):
        edge_els.extend(edge_fn(i, parent_of, flat, tree_depth, positions, eid_prefix))

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
