"""mermaid_render.layout.c4_layout — Native C4 scene builder.

Reuses C4Bounds packer from _c4.py for Mermaid-faithful layout, converting
to SvgScene primitives instead of HTML.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Optional

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
    MarkerDefinition,
    PaintStyle,
    SceneCircle,
    SceneLine,
    ScenePath,
    SceneRoundedRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)
from ._c4 import (
    C4Item, C4Relationship, C4Boundary, C4Box, C4Bounds,
    C4_NODE_W, C4_PERSON_H, C4_SYSTEM_H, C4_LAYOUT_WIDTH,
    C4_SHAPE_MARGIN, C4_SHAPES_PER_ROW, C4_TITLE_H,
    _mermaid_edge_point, _C4_TYPE_DISPLAY, _C4_BOUNDARY_PAD,
)

# ── C4 element regexes (mirror _strategies.py) ───────────────────────────────

_C4_ELEM_RE = re.compile(
    r'^(Person|System|Container|Component'
    r'|SystemDb|System_Db|SystemQueue|System_Queue'
    r'|ContainerDb|Container_Db|ContainerQueue|Container_Queue'
    r'|ComponentDb|Component_Db|ComponentQueue|Component_Queue'
    r'|Person_Ext|System_Ext|SystemDb_Ext|System_Db_Ext'
    r'|SystemQueue_Ext|System_Queue_Ext'
    r'|Container_Ext|ContainerDb_Ext|Container_Db_Ext'
    r'|ContainerQueue_Ext|Container_Queue_Ext'
    r'|Component_Ext|ComponentDb_Ext|Component_Db_Ext'
    r'|ComponentQueue_Ext|Component_Queue_Ext)\s*'
    r'\(\s*(\w+)\s*,\s*"([^"]+)"'
    r'(?:\s*,\s*"([^"]*)")?'
    r'(?:\s*,\s*"([^"]*)")?',
    re.I
)
_C4_BOUNDARY_RE = re.compile(
    r'^(?:Enterprise_Boundary|System_Boundary|Container_Boundary|Boundary)'
    r'\s*\(\s*(\w+)\s*,\s*"([^"]+)"', re.I
)
_C4_REL_RE = re.compile(
    r'^(?:Rel|Rel_D|Rel_U|Rel_L|Rel_R|BiRel)\s*'
    r'\(\s*(\w+)\s*,\s*(\w+)\s*,\s*"([^"]*)"', re.I
)

# ── Concrete color tokens (no CSS vars) ──────────────────────────────────────

_C4_NODE_FILL = "#f7f6f2"
_C4_NODE_STROKE = "#dad7ce"
_C4_EXT_FILL = "#999999"
_C4_EXT_STROKE = "#8a8a8a"
_C4_EXT_TEXT = "#ffffff"
_C4_TEXT = "#191a17"
_C4_DIM = "#75736c"
_C4_ACCENT = "#60a5fa"
_C4_BOUNDARY_STROKE = "#dad7ce"
_C4_BOUNDARY_FILL = "none"
_C4_EDGE_STROKE = "#75736c"
_C4_TITLE_COLOR = "#191a17"


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_c4_source(src: str) -> tuple[str, list, list, dict]:
    """Return (title, items, relationships, groups)."""
    lines = src.splitlines()
    content_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith(("%%", "//")):
            content_start = i + 1
            break

    title = ""
    items: list[C4Item] = []
    relationships: list[C4Relationship] = []
    groups: dict[str, C4Boundary] = {}
    boundary_stack: list[str] = []

    for raw in lines[content_start:]:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line.lower().startswith("title "):
            title = line[6:].strip()
            continue
        m = _C4_BOUNDARY_RE.match(line)
        if m:
            bid, blbl = m.group(1), m.group(2)
            groups.setdefault(bid, C4Boundary(id=bid, label=blbl))
            boundary_stack.append(bid)
            continue
        if line.startswith((")", "}")) and boundary_stack:
            boundary_stack.pop()
            continue
        m = _C4_ELEM_RE.match(line)
        if m:
            elem_type = m.group(1).lower().replace("-", "_")
            eid, elbl = m.group(2), m.group(3)
            arg3 = m.group(4) or ""
            arg4 = m.group(5) or ""
            is_ext = elem_type.endswith("_ext")
            _base = re.sub(r"_(ext|db|queue)$", "", elem_type)
            if _base in ("container", "component") and arg4:
                tech, desc = arg3, arg4
            elif _base in ("container", "component"):
                tech, desc = arg3, ""
            else:
                tech, desc = "", arg3
            gin = boundary_stack[-1] if boundary_stack else None
            items.append(C4Item(
                alias=eid, kind=elem_type, label=elbl, description=desc,
                is_external=is_ext, technology=tech, boundary=gin,
            ))
            if gin:
                groups.setdefault(gin, C4Boundary(id=gin, label=gin))
                if eid not in groups[gin].members:
                    groups[gin].members.append(eid)
            continue
        m = _C4_REL_RE.match(line)
        if m:
            relationships.append(C4Relationship(
                src=m.group(1), dst=m.group(2), label=m.group(3),
            ))

    return title, items, relationships, groups


# ── Scene builders ────────────────────────────────────────────────────────────

def _make_c4_node_elements(
    item: C4Item, box: C4Box, eid: str,
) -> list:
    """Convert a C4Item + its box to a list of scene elements."""
    elements = []
    x, y = float(box.x), float(box.y)
    w, h = float(box.width), float(box.height)

    type_tag = _C4_TYPE_DISPLAY.get(item.kind, item.kind.capitalize())

    if item.is_external:
        fill_c = _C4_EXT_FILL
        stroke_c = _C4_EXT_STROKE
        text_c = _C4_EXT_TEXT
    else:
        fill_c = _C4_NODE_FILL
        stroke_c = _C4_NODE_STROKE
        text_c = _C4_TEXT

    # Node box
    elements.append(SceneRoundedRect(
        element_id=f"{eid}-node-{item.alias}",
        x=x, y=y, w=w, h=h,
        rx=8, ry=8,
        paint=PaintStyle(
            fill=FillStyle(color=fill_c),
            stroke=StrokeStyle(color=stroke_c, width=1.5),
        ),
        css_classes=("c4-node", f"c4-{item.kind.replace('_', '-')}"),
        data_attrs=(("node-id", item.alias),),
    ))

    # Accent top bar (non-external only)
    if not item.is_external:
        elements.append(SceneRoundedRect(
            element_id=f"{eid}-accent-{item.alias}",
            x=x, y=y, w=w, h=3.0,
            rx=8, ry=8,
            paint=PaintStyle(fill=FillStyle(color=_C4_ACCENT)),
            css_classes=("c4-accent-bar",),
        ))

    # Text content: stereotype, label, technology, description
    text_x = x + w / 2
    text_y_start = y + 22.0

    elements.append(SceneText(
        element_id=f"{eid}-stereotype-{item.alias}",
        lines=(SceneTextLine(
            text=f"[{type_tag}]",
            x=text_x, y=text_y_start,
            font_size=10.0, font_weight=400,
            fill_color=_C4_DIM if not item.is_external else _C4_EXT_TEXT,
        ),),
        text_anchor="middle",
        css_classes=("c4-stereotype",),
    ))
    elements.append(SceneText(
        element_id=f"{eid}-label-{item.alias}",
        lines=(SceneTextLine(
            text=item.label,
            x=text_x, y=text_y_start + 18.0,
            font_size=14.0, font_weight=700,
            fill_color=text_c,
        ),),
        text_anchor="middle",
        css_classes=("c4-label",),
    ))
    if item.technology:
        elements.append(SceneText(
            element_id=f"{eid}-tech-{item.alias}",
            lines=(SceneTextLine(
                text=f"[{item.technology}]",
                x=text_x, y=text_y_start + 34.0,
                font_size=10.0, font_weight=400,
                fill_color=_C4_DIM if not item.is_external else _C4_EXT_TEXT,
            ),),
            text_anchor="middle",
            css_classes=("c4-technology",),
        ))
    if item.description:
        elements.append(SceneText(
            element_id=f"{eid}-desc-{item.alias}",
            lines=(SceneTextLine(
                text=item.description,
                x=text_x, y=text_y_start + (48.0 if item.technology else 34.0),
                font_size=11.0, font_weight=400,
                fill_color=_C4_DIM if not item.is_external else _C4_EXT_TEXT,
            ),),
            text_anchor="middle",
            css_classes=("c4-description",),
        ))

    return elements


def _make_c4_boundary_elements(
    bnd: C4Boundary, member_boxes: list[C4Box], eid: str,
) -> list:
    """Boundary dashed rect + label."""
    if not member_boxes:
        return []
    xs = [b.x for b in member_boxes]
    ys = [b.y for b in member_boxes]
    x2s = [b.x + b.width for b in member_boxes]
    y2s = [b.y + b.height for b in member_boxes]
    bx = float(min(xs)) - _C4_BOUNDARY_PAD
    by = float(min(ys)) - _C4_BOUNDARY_PAD - 20
    bw = float(max(x2s)) - float(min(xs)) + 2 * _C4_BOUNDARY_PAD
    bh = float(max(y2s)) - float(min(ys)) + 2 * _C4_BOUNDARY_PAD + 20

    elements = [
        SceneRoundedRect(
            element_id=f"{eid}-bnd-{bnd.id}",
            x=bx, y=by, w=bw, h=bh,
            rx=8, ry=8,
            paint=PaintStyle(
                fill=FillStyle(color="none"),
                stroke=StrokeStyle(color=_C4_BOUNDARY_STROKE, width=2.0, dasharray="6 3"),
            ),
            css_classes=("c4-boundary",),
            data_attrs=(("boundary-id", bnd.id),),
        ),
        SceneText(
            element_id=f"{eid}-bnd-lbl-{bnd.id}",
            lines=(SceneTextLine(
                text=bnd.label,
                x=bx + 10, y=by + 15,
                font_size=11.0, font_weight=600,
                fill_color=_C4_DIM,
            ),),
            text_anchor="start",
            css_classes=("c4-boundary-label",),
        ),
    ]
    return elements


def _make_c4_edge_elements(
    relationships: list[C4Relationship],
    box_map: dict[str, C4Box],
    eid: str,
) -> tuple[list, list, list]:
    """Return (edge_paths, label_texts, marker_defs) for C4 relationships."""
    edge_els: list = []
    label_els: list = []
    marker_id = f"{eid}-c4-arrow"

    for i, rel in enumerate(relationships):
        src_box = box_map.get(rel.src)
        dst_box = box_map.get(rel.dst)
        if src_box is None or dst_box is None:
            continue
        if rel.src == rel.dst:
            continue

        src_cx = src_box.x + src_box.width / 2
        src_cy = src_box.y + src_box.height / 2
        dst_cx = dst_box.x + dst_box.width / 2
        dst_cy = dst_box.y + dst_box.height / 2

        sx, sy = _mermaid_edge_point(
            src_box.x, src_box.y, src_cx, src_cy,
            src_box.width, src_box.height, dst_cx, dst_cy,
        )
        ex, ey = _mermaid_edge_point(
            dst_box.x, dst_box.y, dst_cx, dst_cy,
            dst_box.width, dst_box.height, src_cx, src_cy,
        )

        if i == 0:
            cmds = (
                ("M", float(sx), float(sy)),
                ("L", float(ex), float(ey)),
            )
            lx = (sx + ex) / 2
            ly = (sy + ey) / 2
        else:
            ctrl_x = sx + (ex - sx) / 4
            ctrl_y = sy + (ey - sy) / 2
            cmds = (
                ("M", float(sx), float(sy)),
                ("Q", float(ctrl_x), float(ctrl_y), float(ex), float(ey)),
            )
            lx = 0.25 * sx + 0.5 * ctrl_x + 0.25 * ex
            ly = 0.25 * sy + 0.5 * ctrl_y + 0.25 * ey

        edge_els.append(ScenePath(
            element_id=f"{eid}-rel-{i}",
            commands=cmds,
            marker_end=marker_id,
            paint=PaintStyle(
                fill=FillStyle(color="none"),
                stroke=StrokeStyle(color=_C4_EDGE_STROKE, width=1.5),
            ),
            css_classes=("c4-relation",),
        ))

        if rel.label:
            label_els.append(SceneText(
                element_id=f"{eid}-rel-lbl-{i}",
                lines=(SceneTextLine(
                    text=rel.label,
                    x=float(lx), y=float(ly),
                    font_size=11.0, fill_color=_C4_TEXT,
                ),),
                text_anchor="middle",
                css_classes=("c4-relation-label",),
            ))

    marker_defs = [MarkerDefinition(
        marker_id=marker_id,
        marker_type="arrow-end",
        color=_C4_EDGE_STROKE,
        size=8.0,
        refX=6.0,
        refY=4.0,
    )]

    return edge_els, label_els, marker_defs


# ── Public entry point ────────────────────────────────────────────────────────

def layout_c4_scene(
    src: str, *, c4_type: str = "c4context", width_hint: int = 0,
) -> SvgScene:
    """Parse C4 source and return a fully-laid-out SvgScene."""
    title, items, relationships, groups = _parse_c4_source(src)

    if not items:
        raise ValueError("No elements found in C4 diagram.")

    ungrouped = [it for it in items if not it.boundary]
    boundary_ids = list(groups.keys())
    boundary_item_map = {
        bid: [it for it in items if it.boundary == bid]
        for bid in boundary_ids
    }
    packing_order: list[C4Item] = list(ungrouped)
    for bid in boundary_ids:
        packing_order.extend(boundary_item_map.get(bid, []))

    def _item_box(item: C4Item) -> C4Box:
        h = C4_PERSON_H if "person" in item.kind else C4_SYSTEM_H
        return C4Box(alias=item.alias, width=C4_NODE_W, height=h)

    start_y = float(C4_TITLE_H if title else 0)
    bounds = C4Bounds(
        start_x=2 * C4_SHAPE_MARGIN,
        start_y=start_y,
        width_limit=C4_LAYOUT_WIDTH,
        shape_margin=C4_SHAPE_MARGIN,
        shapes_per_row=C4_SHAPES_PER_ROW,
    )
    box_map: dict[str, C4Box] = {}
    for item in packing_order:
        box = _item_box(item)
        bounds.insert(box)
        box_map[item.alias] = box

    canvas_w = float(C4_LAYOUT_WIDTH)
    canvas_h = float(math.ceil(bounds.max_bottom + C4_SHAPE_MARGIN))

    zoom = 1.0
    if width_hint and canvas_w > 0 and canvas_w > width_hint:
        zoom = width_hint / canvas_w

    svg_w = canvas_w * zoom
    svg_h = canvas_h * zoom

    content = f"{c4_type}:{canvas_w}:{canvas_h}:{','.join(i.alias for i in packing_order)}"
    content_hash = int(hashlib.sha256(content.encode()).hexdigest(), 16)
    scene_id = make_scene_id(c4_type, content_hash)
    eid = hashlib.sha256(scene_id.encode()).hexdigest()[:6]

    boundary_els: list = []
    node_els: list = []
    label_els: list = []
    edge_els: list = []
    overlay_els: list = []
    bg_els: list = []

    # Title
    if title:
        bg_els.append(SceneText(
            element_id=f"{eid}-title",
            lines=(SceneTextLine(
                text=title,
                x=canvas_w / 2, y=float(C4_TITLE_H / 2 + 8),
                font_size=16.0, font_weight=700,
                fill_color=_C4_TITLE_COLOR,
            ),),
            text_anchor="middle",
            css_classes=("c4-title",),
        ))

    # Boundary boxes (before nodes, nodes paint on top)
    for bid, bnd in groups.items():
        member_boxes = [box_map[alias] for alias in bnd.members if alias in box_map]
        if member_boxes:
            boundary_els.extend(_make_c4_boundary_elements(bnd, member_boxes, eid))

    # Nodes
    for item in packing_order:
        box = box_map.get(item.alias)
        if box:
            els = _make_c4_node_elements(item, box, eid)
            for el in els:
                if isinstance(el, SceneText):
                    label_els.append(el)
                else:
                    node_els.append(el)

    # Edges
    rel_edges, rel_labels, marker_defs = _make_c4_edge_elements(
        relationships, box_map, eid,
    )
    edge_els.extend(rel_edges)
    label_els.extend(rel_labels)

    layers = tuple(
        (name, tuple(elems)) for name, elems in [
            (LAYER_BACKGROUND, bg_els),
            (LAYER_BOUNDARIES, boundary_els),
            (LAYER_EDGES, edge_els),
            (LAYER_NODES, node_els),
            (LAYER_LABELS, label_els),
            (LAYER_NOTES, []),
            (LAYER_OVERLAYS, overlay_els),
        ]
    )

    return SvgScene(
        scene_id=scene_id,
        diagram_type=c4_type,
        width=svg_w,
        height=svg_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title=title or c4_type,
            description=f"Mermaid {c4_type} diagram",
        ),
        definitions=tuple(marker_defs) if rel_edges else (),
        layers=layers,
    )
