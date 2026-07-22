"""mermaid_render.layout.er — Native erDiagram scene builder.

Parses ``erDiagram`` source and renders entity boxes with attribute lists
and relationship lines between them.
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
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)


# ── Color tokens ──────────────────────────────────────────────────────────────

_BG_FILL = "#f8fafc"
_ENTITY_HEADER_FILL = "#1e3a8a"
_ENTITY_HEADER_TEXT = "#f0f9ff"
_ENTITY_BODY_FILL = "#eff6ff"
_ENTITY_STROKE = "#3b82f6"
_REL_STROKE = "#374151"
_ATTR_TEXT = "#1e293b"
_LABEL_TEXT = "#6b7280"
_PK_COLOR = "#dc2626"
_FK_COLOR = "#7c3aed"

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD_H = 48
_PAD_V = 40
_ENTITY_W = 180
_ENTITY_HEADER_H = 30
_ATTR_H = 20
_ATTR_PAD = 6
_ENTITY_GAP_H = 60    # horizontal gap between entities
_ENTITY_GAP_V = 48    # vertical gap between entity rows
_FONT_HEADER = 13
_FONT_ATTR = 11
_FONT_LABEL = 10
_COLS = 3             # max columns in grid layout


# ── Parser ────────────────────────────────────────────────────────────────────

_CARD_MAP = {
    "||": ("one", "exactly"),
    "|{": ("one-or-more", "one-or-more"),
    "}|": ("one-or-more", "one-or-more"),
    "||": ("one", "one"),
    "|o": ("zero-or-one", "zero-or-one"),
    "o|": ("zero-or-one", "zero-or-one"),
    "o{": ("zero-or-more", "zero-or-more"),
    "}o": ("zero-or-more", "zero-or-more"),
}

_REL_RE = re.compile(
    r'^(\w+)\s+'
    r'([\|o\{\}]+--[\-]*[\|o\{\}]+)\s+'
    r'(\w+)\s*:\s*"?([^"]*)"?',
)


def _parse_cardinality(card_str: str) -> tuple[str, str]:
    """Return (left_card, right_card) description strings."""
    # card_str like "||--o{" or "}|--|{"
    # just return identifying string
    return card_str[:2], card_str[-2:]


def _parse_er_source(src: str) -> tuple[dict[str, list[dict]], list[dict]]:
    """Return (entities, relationships).

    entities: {name: [{type, name, flags}]}
    relationships: [{from, to, label, cardinality}]
    """
    entities: dict[str, list[dict]] = {}
    relationships: list[dict] = []
    cur_entity: str | None = None

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("erdiagram") or stripped.startswith("%%"):
            continue

        # Entity opening: "ENTITY {" or "ENTITY{"
        m = re.match(r'^(\w+)\s*\{', stripped)
        if m:
            ename = m.group(1)
            if ename not in entities:
                entities[ename] = []
            cur_entity = ename
            continue

        # Closing brace
        if stripped == "}":
            cur_entity = None
            continue

        # Attribute inside entity: type name [PK|FK|UK]
        if cur_entity is not None and not stripped.startswith("}"):
            parts = stripped.split()
            if len(parts) >= 2:
                attr = {
                    "type": parts[0],
                    "name": parts[1],
                    "flags": [p for p in parts[2:] if p in ("PK", "FK", "UK")],
                }
                entities[cur_entity].append(attr)
            continue

        # Relationship: A ||--o{ B : "label"
        m = _REL_RE.match(stripped)
        if m:
            from_e = m.group(1)
            card = m.group(2)
            to_e = m.group(3)
            label = m.group(4).strip()
            # Ensure entities exist
            if from_e not in entities:
                entities[from_e] = []
            if to_e not in entities:
                entities[to_e] = []
            left_c, right_c = _parse_cardinality(card)
            relationships.append({
                "from": from_e,
                "to": to_e,
                "label": label,
                "left_card": left_c,
                "right_card": right_c,
                "cardinality": card,
            })

    return entities, relationships


# ── Layout helpers ────────────────────────────────────────────────────────────

def _entity_height(attrs: list[dict]) -> float:
    return float(_ENTITY_HEADER_H + len(attrs) * _ATTR_H + _ATTR_PAD * 2)


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_er_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse erDiagram source and return an SvgScene with entity boxes and edges."""
    entities, relationships = _parse_er_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("erdiagram", content_hash)

    entity_names = list(entities.keys())
    if not entity_names:
        w = max(width_hint or 400, 400)
        h = 160
        return SvgScene(
            scene_id=scene_id,
            diagram_type="erdiagram",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title="ER diagram"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    # Grid layout: up to _COLS columns
    n = len(entity_names)
    cols = min(_COLS, n)
    rows = (n + cols - 1) // cols

    # Position each entity
    pos: dict[str, tuple[float, float]] = {}
    for idx, ename in enumerate(entity_names):
        col = idx % cols
        row = idx // cols
        ex = float(_PAD_H + col * (_ENTITY_W + _ENTITY_GAP_H))
        ey = float(_PAD_V + row * (200 + _ENTITY_GAP_V))   # 200 = max entity h estimate
        pos[ename] = (ex, ey)

    # Compute actual heights
    heights: dict[str, float] = {e: _entity_height(attrs) for e, attrs in entities.items()}

    # Canvas size
    canvas_w = float(_PAD_H * 2 + cols * _ENTITY_W + (cols - 1) * _ENTITY_GAP_H)
    canvas_h = float(_PAD_V * 2 + rows * (max(heights.values(), default=80) + _ENTITY_GAP_V))

    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []
    definitions: list = []

    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    # Entity boxes
    for ename, attrs in entities.items():
        ex, ey = pos[ename]
        eh = heights[ename]

        # Header
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-ent-hdr-{ename}",
            x=ex, y=ey,
            w=float(_ENTITY_W), h=float(_ENTITY_HEADER_H),
            paint=PaintStyle(fill=FillStyle(color=_ENTITY_HEADER_FILL)),
            semantic_role="entity",
            data_attrs=(("data-entity", ename),),
        ))
        label_elements.append(SceneText(
            element_id=f"{scene_id}-ent-lbl-{ename}",
            lines=(SceneTextLine(
                text=ename,
                x=ex + _ENTITY_W / 2,
                y=ey + _ENTITY_HEADER_H / 2 + _FONT_HEADER * 0.35,
                font_size=float(_FONT_HEADER),
                font_weight=700,
                fill_color=_ENTITY_HEADER_TEXT,
            ),),
            text_anchor="middle",
        ))

        # Body
        body_h = eh - _ENTITY_HEADER_H
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-ent-body-{ename}",
            x=ex, y=ey + _ENTITY_HEADER_H,
            w=float(_ENTITY_W), h=body_h,
            paint=PaintStyle(
                fill=FillStyle(color=_ENTITY_BODY_FILL),
                stroke=StrokeStyle(color=_ENTITY_STROKE, width=1.0),
            ),
        ))

        # Attributes
        for ai, attr in enumerate(attrs):
            ay = float(ey + _ENTITY_HEADER_H + _ATTR_PAD + ai * _ATTR_H)
            flag_str = " ".join(attr["flags"])
            flag_color = _PK_COLOR if "PK" in attr["flags"] else (_FK_COLOR if "FK" in attr["flags"] else _ATTR_TEXT)
            attr_text = f"{attr['type']} {attr['name']}"
            label_elements.append(SceneText(
                element_id=f"{scene_id}-attr-{ename}-{ai}",
                lines=(SceneTextLine(
                    text=attr_text,
                    x=ex + 6,
                    y=ay + _FONT_ATTR + 2,
                    font_size=float(_FONT_ATTR),
                    fill_color=_ATTR_TEXT,
                ),),
                text_anchor="start",
            ))
            if flag_str:
                label_elements.append(SceneText(
                    element_id=f"{scene_id}-flag-{ename}-{ai}",
                    lines=(SceneTextLine(
                        text=flag_str,
                        x=ex + _ENTITY_W - 6,
                        y=ay + _FONT_ATTR + 2,
                        font_size=float(_FONT_ATTR),
                        fill_color=flag_color,
                        font_weight=600,
                    ),),
                    text_anchor="end",
                ))

    # Relationship edges
    for rel_idx, rel in enumerate(relationships):
        from_e = rel["from"]
        to_e = rel["to"]
        if from_e not in pos or to_e not in pos:
            continue

        fx, fy = pos[from_e]
        tx, ty = pos[to_e]
        fh = heights.get(from_e, 80)
        th = heights.get(to_e, 80)

        # Connect from right/left edge of entity center
        f_cx = fx + _ENTITY_W / 2
        f_cy = fy + fh / 2
        t_cx = tx + _ENTITY_W / 2
        t_cy = ty + th / 2

        # Simple straight line between entity centers
        edge_elements.append(SceneLine(
            element_id=f"{scene_id}-rel-{rel_idx}",
            x1=f_cx, y1=f_cy,
            x2=t_cx, y2=t_cy,
            paint=PaintStyle(stroke=StrokeStyle(color=_REL_STROKE, width=1.5)),
            semantic_role="relation",
            data_attrs=(
                ("data-from", from_e),
                ("data-to", to_e),
                ("data-label", rel["label"]),
                ("data-cardinality", rel["cardinality"]),
            ),
        ))

        # Relation label at midpoint
        mid_x = (f_cx + t_cx) / 2
        mid_y = (f_cy + t_cy) / 2
        if rel["label"]:
            label_elements.append(SceneText(
                element_id=f"{scene_id}-rel-lbl-{rel_idx}",
                lines=(SceneTextLine(
                    text=rel["label"],
                    x=mid_x, y=mid_y - 4,
                    font_size=float(_FONT_LABEL),
                    fill_color=_LABEL_TEXT,
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

    n_rels = len(relationships)
    return SvgScene(
        scene_id=scene_id,
        diagram_type="erdiagram",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title="ER diagram",
            description=f"ER diagram with {len(entity_names)} entities and {n_rels} relationships",
        ),
        layers=layers,
    )
