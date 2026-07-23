"""mermaid_render.layout.c4_layout — Native C4 scene builder.

Reuses C4Bounds packer from _c4.py for Mermaid-faithful layout, converting
to SvgScene primitives instead of HTML.

Stage 10 painters:
  Person / Person_Ext   — stick figure (circle head + path body)
  System / Container / Component / *_Ext  — rounded box with dashed Ext border
  SystemDb / ContainerDb / ComponentDb / *_Ext  — cylinder (rect + two ellipses)
  SystemQueue / ContainerQueue / ComponentQueue / *_Ext  — box + two vertical bars
  BiRel                 — one path with marker-start + marker-end
  Rel_D/U/L/R           — Bézier with directional control-point bias
  Technology            — separate c4-technology text role below label
  Label placement       — perpendicular offset avoids node/boundary centers
  Nested boundaries     — outer rect contains inner boundary extents
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
    SceneEllipse,
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
# Capturing group 1 = keyword for rel_type
_C4_REL_RE = re.compile(
    r'^(Rel|Rel_D|Rel_U|Rel_L|Rel_R|BiRel)\s*'
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

# Direction-hint rel types
_C4_DIR_HINTS = frozenset({"rel_d", "rel_u", "rel_l", "rel_r"})
_C4_DIR_BIAS = 40.0       # Bézier control-point bias in pixels


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
            parent_bid = boundary_stack[-1] if boundary_stack else None
            if bid not in groups:
                groups[bid] = C4Boundary(id=bid, label=blbl, parent=parent_bid)
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
            # Strip suffixes iteratively to handle both underscore and
            # concatenated forms (e.g. container_db AND containerdb).
            _base = elem_type
            while True:
                _next = re.sub(r"_?(ext|db|queue)$", "", _base)
                if _next == _base:
                    break
                _base = _next
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
            rel_kw = m.group(1).lower()  # "rel", "birel", "rel_d", "rel_u", "rel_l", "rel_r"
            relationships.append(C4Relationship(
                src=m.group(2), dst=m.group(3), label=m.group(4),
                rel_type=rel_kw,
            ))

    return title, items, relationships, groups


# ── Painter helpers ───────────────────────────────────────────────────────────

def _node_colors(item: C4Item) -> tuple[str, str, str]:
    """Return (fill_color, stroke_color, text_color)."""
    if item.is_external:
        return _C4_EXT_FILL, _C4_EXT_STROKE, _C4_EXT_TEXT
    return _C4_NODE_FILL, _C4_NODE_STROKE, _C4_TEXT


def _stroke_for(stroke_c: str, is_ext: bool) -> StrokeStyle:
    """Solid stroke for internal nodes, dashed for Ext variants."""
    if is_ext:
        return StrokeStyle(color=stroke_c, width=1.5, dasharray="4 3")
    return StrokeStyle(color=stroke_c, width=1.5)


def _text_block(
    item: C4Item, cx: float, y_start: float, eid: str,
) -> list:
    """Emit stereotype, label, technology (separate role), description SceneText elements."""
    _, _, text_c = _node_colors(item)
    dim_c = _C4_DIM if not item.is_external else _C4_EXT_TEXT
    type_tag = _C4_TYPE_DISPLAY.get(item.kind, item.kind.capitalize())

    elements: list = [
        SceneText(
            element_id=f"{eid}-stereotype-{item.alias}",
            lines=(SceneTextLine(
                text=f"[{type_tag}]",
                x=cx, y=y_start,
                font_size=10.0, font_weight=400, fill_color=dim_c,
            ),),
            text_anchor="middle",
            css_classes=("c4-stereotype",),
        ),
        SceneText(
            element_id=f"{eid}-label-{item.alias}",
            lines=(SceneTextLine(
                text=item.label,
                x=cx, y=y_start + 18.0,
                font_size=14.0, font_weight=700, fill_color=text_c,
            ),),
            text_anchor="middle",
            css_classes=("c4-label",),
        ),
    ]
    tech_offset = 34.0
    if item.technology:
        elements.append(SceneText(
            element_id=f"{eid}-tech-{item.alias}",
            lines=(SceneTextLine(
                text=f"[{item.technology}]",
                x=cx, y=y_start + tech_offset,
                font_size=10.0, font_weight=400, fill_color=dim_c,
            ),),
            text_anchor="middle",
            css_classes=("c4-technology",),
        ))
    if item.description:
        desc_offset = tech_offset + (14.0 if item.technology else 0.0)
        elements.append(SceneText(
            element_id=f"{eid}-desc-{item.alias}",
            lines=(SceneTextLine(
                text=item.description,
                x=cx, y=y_start + desc_offset,
                font_size=11.0, font_weight=400, fill_color=dim_c,
            ),),
            text_anchor="middle",
            css_classes=("c4-description",),
        ))
    return elements


# ── Distinct shape painters ───────────────────────────────────────────────────

def _make_person_elements(item: C4Item, box: C4Box, eid: str) -> list:
    """Stick-figure painter for Person / Person_Ext."""
    x, y = float(box.x), float(box.y)
    w, h = float(box.width), float(box.height)
    cx = x + w / 2.0

    fill_c, stroke_c, _ = _node_colors(item)
    body_paint = PaintStyle(
        fill=FillStyle(color=fill_c),
        stroke=_stroke_for(stroke_c, item.is_external),
    )
    icon_stroke = StrokeStyle(color=stroke_c, width=1.5)
    icon_fill = FillStyle(color=fill_c)

    head_r = 12.0
    head_cy = y + head_r + 6.0
    trunk_top = head_cy + head_r
    trunk_bot = trunk_top + 20.0
    arm_y = trunk_top + 8.0
    arm_spread = 14.0
    leg_spread = 12.0
    leg_bot = trunk_bot + 14.0
    text_y_start = leg_bot + 10.0

    elements: list = [
        SceneRoundedRect(
            element_id=f"{eid}-node-{item.alias}",
            x=x, y=y, w=w, h=h, rx=8, ry=8,
            paint=body_paint,
            css_classes=("c4-node", f"c4-{item.kind.replace('_', '-')}"),
            data_attrs=(("node-id", item.alias),),
        ),
        SceneCircle(
            element_id=f"{eid}-head-{item.alias}",
            cx=cx, cy=head_cy, r=head_r,
            paint=PaintStyle(fill=icon_fill, stroke=icon_stroke),
            css_classes=("c4-person-head",),
        ),
        ScenePath(
            element_id=f"{eid}-trunk-{item.alias}",
            commands=(("M", cx, trunk_top), ("L", cx, trunk_bot)),
            paint=PaintStyle(fill=FillStyle(color="none"), stroke=icon_stroke),
            css_classes=("c4-person-body",),
        ),
        ScenePath(
            element_id=f"{eid}-arms-{item.alias}",
            commands=(("M", cx - arm_spread, arm_y), ("L", cx + arm_spread, arm_y)),
            paint=PaintStyle(fill=FillStyle(color="none"), stroke=icon_stroke),
            css_classes=("c4-person-arms",),
        ),
        ScenePath(
            element_id=f"{eid}-legs-{item.alias}",
            commands=(
                ("M", cx, trunk_bot), ("L", cx - leg_spread, leg_bot),
                ("M", cx, trunk_bot), ("L", cx + leg_spread, leg_bot),
            ),
            paint=PaintStyle(fill=FillStyle(color="none"), stroke=icon_stroke),
            css_classes=("c4-person-legs",),
        ),
    ]
    elements.extend(_text_block(item, cx, text_y_start, eid))
    return elements


def _make_db_elements(item: C4Item, box: C4Box, eid: str) -> list:
    """Cylinder painter for *Db variants (SystemDb, ContainerDb, ComponentDb)."""
    x, y = float(box.x), float(box.y)
    w, h = float(box.width), float(box.height)
    cx = x + w / 2.0

    fill_c, stroke_c, _ = _node_colors(item)
    fill = FillStyle(color=fill_c)
    stroke = _stroke_for(stroke_c, item.is_external)
    side_stroke = StrokeStyle(color=stroke_c, width=1.5,
                              dasharray=stroke.dasharray if item.is_external else "")
    ry_cap = 8.0
    body_top = y + ry_cap
    text_y_start = y + 26.0

    elements: list = [
        # Barrel body (fill only — stroke on sides comes from explicit lines)
        SceneRect(
            element_id=f"{eid}-node-{item.alias}",
            x=x, y=body_top, w=w, h=h - ry_cap,
            paint=PaintStyle(fill=fill, stroke=None),
            css_classes=("c4-node", f"c4-{item.kind.replace('_', '-')}"),
            data_attrs=(("node-id", item.alias),),
        ),
        # Side stroke lines
        SceneLine(
            element_id=f"{eid}-cyl-ls-{item.alias}",
            x1=x, y1=body_top, x2=x, y2=y + h,
            paint=PaintStyle(fill=FillStyle(color="none"), stroke=side_stroke),
            css_classes=("c4-db-side",),
        ),
        SceneLine(
            element_id=f"{eid}-cyl-rs-{item.alias}",
            x1=x + w, y1=body_top, x2=x + w, y2=y + h,
            paint=PaintStyle(fill=FillStyle(color="none"), stroke=side_stroke),
            css_classes=("c4-db-side",),
        ),
        # Bottom cap (painted first so top ellipse covers it)
        SceneEllipse(
            element_id=f"{eid}-cyl-bot-{item.alias}",
            cx=cx, cy=y + h, rx=w / 2.0, ry=ry_cap,
            paint=PaintStyle(fill=fill, stroke=stroke),
            css_classes=("c4-db-cap",),
        ),
        # Top cap (painted on top of barrel)
        SceneEllipse(
            element_id=f"{eid}-cyl-top-{item.alias}",
            cx=cx, cy=body_top, rx=w / 2.0, ry=ry_cap,
            paint=PaintStyle(fill=fill, stroke=stroke),
            css_classes=("c4-db-cap",),
        ),
    ]
    elements.extend(_text_block(item, cx, text_y_start, eid))
    return elements


def _make_queue_elements(item: C4Item, box: C4Box, eid: str) -> list:
    """Double-bar painter for *Queue variants."""
    x, y = float(box.x), float(box.y)
    w, h = float(box.width), float(box.height)
    cx = x + w / 2.0

    fill_c, stroke_c, _ = _node_colors(item)
    body_paint = PaintStyle(
        fill=FillStyle(color=fill_c),
        stroke=_stroke_for(stroke_c, item.is_external),
    )
    bar_stroke = StrokeStyle(color=stroke_c, width=1.5)
    bar_x = 10.0
    text_y_start = y + 22.0

    elements: list = [
        SceneRoundedRect(
            element_id=f"{eid}-node-{item.alias}",
            x=x, y=y, w=w, h=h, rx=8, ry=8,
            paint=body_paint,
            css_classes=("c4-node", f"c4-{item.kind.replace('_', '-')}"),
            data_attrs=(("node-id", item.alias),),
        ),
    ]
    if not item.is_external:
        elements.append(SceneRoundedRect(
            element_id=f"{eid}-accent-{item.alias}",
            x=x, y=y, w=w, h=3.0, rx=8, ry=8,
            paint=PaintStyle(fill=FillStyle(color=_C4_ACCENT)),
            css_classes=("c4-accent-bar",),
        ))
    elements.extend([
        SceneLine(
            element_id=f"{eid}-qbar-l-{item.alias}",
            x1=x + bar_x, y1=y + 3.0, x2=x + bar_x, y2=y + h - 3.0,
            paint=PaintStyle(fill=FillStyle(color="none"), stroke=bar_stroke),
            css_classes=("c4-queue-bar",),
        ),
        SceneLine(
            element_id=f"{eid}-qbar-r-{item.alias}",
            x1=x + w - bar_x, y1=y + 3.0, x2=x + w - bar_x, y2=y + h - 3.0,
            paint=PaintStyle(fill=FillStyle(color="none"), stroke=bar_stroke),
            css_classes=("c4-queue-bar",),
        ),
    ])
    elements.extend(_text_block(item, cx, text_y_start, eid))
    return elements


def _make_box_elements(item: C4Item, box: C4Box, eid: str) -> list:
    """Default rounded-box painter for System / Container / Component."""
    x, y = float(box.x), float(box.y)
    w, h = float(box.width), float(box.height)
    cx = x + w / 2.0

    fill_c, stroke_c, _ = _node_colors(item)
    body_paint = PaintStyle(
        fill=FillStyle(color=fill_c),
        stroke=_stroke_for(stroke_c, item.is_external),
    )
    text_y_start = y + 22.0

    elements: list = [
        SceneRoundedRect(
            element_id=f"{eid}-node-{item.alias}",
            x=x, y=y, w=w, h=h, rx=8, ry=8,
            paint=body_paint,
            css_classes=("c4-node", f"c4-{item.kind.replace('_', '-')}"),
            data_attrs=(("node-id", item.alias),),
        ),
    ]
    if not item.is_external:
        elements.append(SceneRoundedRect(
            element_id=f"{eid}-accent-{item.alias}",
            x=x, y=y, w=w, h=3.0, rx=8, ry=8,
            paint=PaintStyle(fill=FillStyle(color=_C4_ACCENT)),
            css_classes=("c4-accent-bar",),
        ))
    elements.extend(_text_block(item, cx, text_y_start, eid))
    return elements


def _shape_family(kind: str) -> str:
    """Dispatch key: 'person', 'db', 'queue', or 'box'."""
    k = kind.lower()
    if "person" in k:
        return "person"
    if "db" in k:
        return "db"
    if "queue" in k:
        return "queue"
    return "box"


def _make_c4_node_elements(item: C4Item, box: C4Box, eid: str) -> list:
    """Dispatch to the per-kind painter."""
    family = _shape_family(item.kind)
    if family == "person":
        return _make_person_elements(item, box, eid)
    if family == "db":
        return _make_db_elements(item, box, eid)
    if family == "queue":
        return _make_queue_elements(item, box, eid)
    return _make_box_elements(item, box, eid)


# ── Boundary renderer ─────────────────────────────────────────────────────────

def _make_c4_boundary_rect(
    bnd: C4Boundary, bx: float, by: float, bw: float, bh: float, eid: str,
) -> list:
    """Boundary dashed rect + label from pre-computed dimensions."""
    return [
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
                font_size=11.0, font_weight=600, fill_color=_C4_DIM,
            ),),
            text_anchor="start",
            css_classes=("c4-boundary-label",),
        ),
    ]


# ── Edge renderer ─────────────────────────────────────────────────────────────

def _make_c4_edge_elements(
    relationships: list[C4Relationship],
    box_map: dict[str, C4Box],
    eid: str,
) -> tuple[list, list, list]:
    """Return (edge_paths, label_texts, marker_defs) for C4 relationships.

    BiRel → one path with both marker-start and marker-end.
    Rel_D/U/L/R → Bézier with directional control-point bias.
    Label placement is offset perpendicular to edge to avoid node/boundary overlap.
    """
    edge_els: list = []
    label_els: list = []
    marker_id = f"{eid}-c4-arrow"
    start_marker_id = f"{eid}-c4-arrow-start"
    has_birel = any(r.rel_type == "birel" for r in relationships)

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

        # Direction-hinted and non-first relationships use a Bézier curve.
        use_bezier = (i > 0) or (rel.rel_type in _C4_DIR_HINTS)

        if use_bezier:
            ctrl_x = sx + (ex - sx) / 4
            ctrl_y = sy + (ey - sy) / 2
            if rel.rel_type == "rel_d":
                ctrl_y += _C4_DIR_BIAS
            elif rel.rel_type == "rel_u":
                ctrl_y -= _C4_DIR_BIAS
            elif rel.rel_type == "rel_l":
                ctrl_x -= _C4_DIR_BIAS
            elif rel.rel_type == "rel_r":
                ctrl_x += _C4_DIR_BIAS
            cmds = (
                ("M", float(sx), float(sy)),
                ("Q", float(ctrl_x), float(ctrl_y), float(ex), float(ey)),
            )
            # Label at quadratic midpoint (t=0.5): (1-t)²P0 + 2t(1-t)P1 + t²P2
            lx = 0.25 * sx + 0.5 * ctrl_x + 0.25 * ex
            ly = 0.25 * sy + 0.5 * ctrl_y + 0.25 * ey
        else:
            cmds = (  # type: ignore[assignment]
                ("M", float(sx), float(sy)),
                ("L", float(ex), float(ey)),
            )
            lx = (sx + ex) / 2.0
            ly = (sy + ey) / 2.0

        # Fixed 10px perpendicular offset; keeps label off the edge spine.
        # True obstacle-avoidance (against node/boundary bounding boxes) is deferred.
        dx = ex - sx
        dy = ey - sy
        length = math.hypot(dx, dy)
        if length > 1e-9:
            lx += (-dy / length) * 10.0
            ly += (dx / length) * 10.0

        this_start = start_marker_id if rel.rel_type == "birel" else ""

        edge_els.append(ScenePath(
            element_id=f"{eid}-rel-{i}",
            commands=cmds,
            marker_start=this_start,
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

    marker_defs: list = [MarkerDefinition(
        marker_id=marker_id,
        marker_type="arrow-end",
        color=_C4_EDGE_STROKE,
        size=8.0,
        refX=6.0,
        refY=4.0,
    )]
    if has_birel:
        marker_defs.append(MarkerDefinition(
            marker_id=start_marker_id,
            marker_type="arrow-start",
            color=_C4_EDGE_STROKE,
            size=8.0,
            refX=2.0,
            refY=4.0,
        ))

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
    scene_hash = hashlib.sha256(scene_id.encode()).hexdigest()[:6]

    boundary_els: list = []
    node_els: list = []
    label_els: list = []
    edge_els: list = []
    overlay_els: list = []
    bg_els: list = []

    # Title
    if title:
        bg_els.append(SceneText(
            element_id=f"{scene_hash}-title",
            lines=(SceneTextLine(
                text=title,
                x=canvas_w / 2, y=float(C4_TITLE_H / 2 + 8),
                font_size=16.0, font_weight=700,
                fill_color=_C4_TITLE_COLOR,
            ),),
            text_anchor="middle",
            css_classes=("c4-title",),
        ))

    # ── Boundary rects (nested-boundary aware) ────────────────────────────────
    # Compute each boundary's padded extent recursively (inner before outer).
    pad = float(_C4_BOUNDARY_PAD)

    def _boundary_padded_extent(bid: str) -> Optional[tuple[float, float, float, float]]:
        """Recursively compute (xmin, ymin, xmax, ymax) padded rect for a boundary."""
        bnd = groups[bid]
        raw_xs: list[float] = []
        raw_ys: list[float] = []
        raw_x2s: list[float] = []
        raw_y2s: list[float] = []

        for alias in bnd.members:
            b = box_map.get(alias)
            if b is None:
                continue
            raw_xs.append(b.x); raw_ys.append(b.y)
            raw_x2s.append(b.x + b.width); raw_y2s.append(b.y + b.height)

        # Include nested child boundaries as contributors
        for child_bid, child_bnd in groups.items():
            if child_bnd.parent == bid:
                child_rect = _boundary_padded_extent(child_bid)
                if child_rect is not None:
                    cx, cy, cx2, cy2 = child_rect
                    raw_xs.append(cx); raw_ys.append(cy)
                    raw_x2s.append(cx2); raw_y2s.append(cy2)

        if not raw_xs:
            return None
        return (
            min(raw_xs) - pad,
            min(raw_ys) - pad - 20.0,  # 20 px for label above
            max(raw_x2s) + pad,
            max(raw_y2s) + pad,
        )

    for bid, bnd in groups.items():
        rect = _boundary_padded_extent(bid)
        if rect is not None:
            bx, by, bx2, by2 = rect
            boundary_els.extend(
                _make_c4_boundary_rect(bnd, bx, by, bx2 - bx, by2 - by, scene_hash)
            )

    # ── Nodes ─────────────────────────────────────────────────────────────────
    for item in packing_order:
        box = box_map.get(item.alias)  # type: ignore[assignment]
        if box:
            els = _make_c4_node_elements(item, box, scene_hash)
            for el in els:
                if isinstance(el, SceneText):
                    label_els.append(el)
                else:
                    node_els.append(el)

    # ── Edges ─────────────────────────────────────────────────────────────────
    rel_edges, rel_labels, marker_defs = _make_c4_edge_elements(
        relationships, box_map, scene_hash,
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
