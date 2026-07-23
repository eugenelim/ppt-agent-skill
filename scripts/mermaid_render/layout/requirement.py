"""mermaid_render.layout.requirement — Native requirementDiagram scene builder.

Parses ``requirementDiagram`` source and renders requirement/element boxes
with relation edges between them.
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
_REQ_HEADER_FILL = "#1e3a8a"
_REQ_HEADER_TEXT = "#f0f9ff"
_REQ_BODY_FILL = "#eff6ff"
_REQ_STROKE = "#3b82f6"
_ELEM_HEADER_FILL = "#064e3b"
_ELEM_HEADER_TEXT = "#f0fdf4"
_ELEM_BODY_FILL = "#ecfdf5"
_ELEM_STROKE = "#10b981"
_REL_STROKE = "#6b7280"
_TEXT_COLOR = "#374151"
_DIM_TEXT = "#6b7280"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD_H = 40
_PAD_V = 40
_NODE_W = 200
_HEADER_H = 28
_ATTR_H = 18
_ATTR_PAD = 6
_NODE_GAP_H = 60
_NODE_GAP_V = 48
_FONT_HEADER = 12
_FONT_ATTR = 10
_FONT_REL = 9
_COLS = 3


# ── Parser ────────────────────────────────────────────────────────────────────

_REQ_TYPES = {
    "requirement", "functionalrequirement", "performancerequirement",
    "interfacerequirement", "physicalrequirement", "designconstraint",
}

_REL_RE = re.compile(r'^(\w+)\s*-\s*(.+?)\s*->\s*(\w+)', re.IGNORECASE)


def _parse_requirement_source(src: str) -> tuple[dict, list[dict]]:
    """Return (nodes, relations).

    nodes: {name: {kind, attrs: {key: val}}}
    relations: [{from, to, rel_type}]
    """
    nodes: dict[str, dict] = {}
    relations: list[dict] = []
    cur_node: str | None = None
    cur_kind: str = "requirement"

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("requirementdiagram") or stripped.startswith("%%"):
            continue

        # Node opening: "requirement name {" or "element name {"
        m = re.match(r'^(\w+)\s+(\w+)\s*\{', stripped)
        if m:
            kind = m.group(1).lower()
            name = m.group(2)
            nodes[name] = {"kind": kind, "attrs": {}}
            cur_node = name
            cur_kind = kind
            continue

        # Closing brace
        if stripped == "}":
            cur_node = None
            continue

        # Attribute inside node
        if cur_node is not None:
            m = re.match(r'^(\w+)\s*:\s*(.+)', stripped)
            if m:
                nodes[cur_node]["attrs"][m.group(1)] = m.group(2).strip()
            continue

        # Relation: A - satisfies -> B
        m = _REL_RE.match(stripped)
        if m:
            from_n = m.group(1)
            rel_type = m.group(2).strip()
            to_n = m.group(3)
            relations.append({"from": from_n, "to": to_n, "rel_type": rel_type})
            # Ensure nodes exist
            if from_n not in nodes:
                nodes[from_n] = {"kind": "element", "attrs": {}}
            if to_n not in nodes:
                nodes[to_n] = {"kind": "requirement", "attrs": {}}

    return nodes, relations


def _node_height(node: dict) -> float:
    n_attrs = len(node.get("attrs", {}))
    return float(_HEADER_H + n_attrs * _ATTR_H + _ATTR_PAD * 2)


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_requirement_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse requirementDiagram source and return an SvgScene with requirement boxes."""
    nodes, relations = _parse_requirement_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("requirementdiagram", content_hash)

    node_names = list(nodes.keys())
    if not node_names:
        w = max(width_hint or 400, 400)
        h = 160
        return SvgScene(
            scene_id=scene_id,
            diagram_type="requirementdiagram",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title="Requirement diagram"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    n = len(node_names)
    cols = min(_COLS, n)
    rows = (n + cols - 1) // cols
    max_h = max((_node_height(nodes[nm]) for nm in node_names), default=80)

    pos: dict[str, tuple[float, float]] = {}
    for idx, nname in enumerate(node_names):
        col = idx % cols
        row = idx // cols
        px = float(_PAD_H + col * (_NODE_W + _NODE_GAP_H))
        py = float(_PAD_V + row * (max_h + _NODE_GAP_V))
        pos[nname] = (px, py)

    canvas_w = float(_PAD_H * 2 + cols * _NODE_W + (cols - 1) * _NODE_GAP_H)
    canvas_h = float(_PAD_V * 2 + rows * (max_h + _NODE_GAP_V))

    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []

    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    # Draw nodes
    for nname, node in nodes.items():
        if nname not in pos:
            continue
        px, py = pos[nname]
        nh = _node_height(node)
        is_element = node["kind"] == "element"
        hdr_fill = _ELEM_HEADER_FILL if is_element else _REQ_HEADER_FILL
        hdr_text = _ELEM_HEADER_TEXT if is_element else _REQ_HEADER_TEXT
        body_fill = _ELEM_BODY_FILL if is_element else _REQ_BODY_FILL
        stroke = _ELEM_STROKE if is_element else _REQ_STROKE

        node_elements.append(SceneRect(
            element_id=f"{scene_id}-node-hdr-{nname}",
            x=px, y=py,
            w=float(_NODE_W), h=float(_HEADER_H),
            paint=PaintStyle(fill=FillStyle(color=hdr_fill)),
            semantic_role="node",
            data_attrs=(("node-id", nname), ("data-name", nname), ("data-kind", node["kind"])),
        ))
        label_elements.append(SceneText(
            element_id=f"{scene_id}-node-lbl-{nname}",
            lines=(SceneTextLine(
                text=nname,
                x=px + _NODE_W / 2,
                y=py + _HEADER_H / 2 + _FONT_HEADER * 0.35,
                font_size=float(_FONT_HEADER),
                font_weight=700,
                fill_color=hdr_text,
            ),),
            text_anchor="middle",
        ))

        # Body
        body_h = nh - _HEADER_H
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-node-body-{nname}",
            x=px, y=py + _HEADER_H,
            w=float(_NODE_W), h=body_h,
            paint=PaintStyle(
                fill=FillStyle(color=body_fill),
                stroke=StrokeStyle(color=stroke, width=1.0),
            ),
        ))

        # Attributes
        for ai, (key, val) in enumerate(node.get("attrs", {}).items()):
            ay = float(py + _HEADER_H + _ATTR_PAD + ai * _ATTR_H)
            label_elements.append(SceneText(
                element_id=f"{scene_id}-attr-{nname}-{ai}",
                lines=(SceneTextLine(
                    text=f"{key}: {val}",
                    x=px + 6,
                    y=ay + _FONT_ATTR + 2,
                    font_size=float(_FONT_ATTR),
                    fill_color=_TEXT_COLOR,
                ),),
                text_anchor="start",
            ))

    # Draw relation edges
    node_centers: dict[str, tuple[float, float]] = {}
    for nname, (px, py) in pos.items():
        nh = _node_height(nodes[nname])
        node_centers[nname] = (px + _NODE_W / 2, py + nh / 2)

    for ri, rel in enumerate(relations):
        fn = rel["from"]
        tn = rel["to"]
        if fn not in node_centers or tn not in node_centers:
            continue
        fx, fy = node_centers[fn]
        tx, ty = node_centers[tn]

        edge_elements.append(SceneLine(
            element_id=f"{scene_id}-rel-{ri}",
            x1=fx, y1=fy, x2=tx, y2=ty,
            paint=PaintStyle(stroke=StrokeStyle(
                color=_REL_STROKE, width=1.5, dasharray="4 2",
            )),
            semantic_role="relation",
            data_attrs=(
                ("data-from", fn),
                ("data-to", tn),
                ("data-rel-type", rel["rel_type"]),
            ),
        ))

        # Relation label
        mid_x = (fx + tx) / 2
        mid_y = (fy + ty) / 2
        label_elements.append(SceneText(
            element_id=f"{scene_id}-rel-lbl-{ri}",
            lines=(SceneTextLine(
                text=rel["rel_type"],
                x=mid_x, y=mid_y - 4,
                font_size=float(_FONT_REL),
                fill_color=_DIM_TEXT,
                italic=True,
            ),),
            text_anchor="middle",
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

    return SvgScene(
        scene_id=scene_id,
        diagram_type="requirementdiagram",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title="Requirement diagram",
            description=f"Requirement diagram with {n} nodes and {len(relations)} relations",
        ),
        layers=layers,
    )
