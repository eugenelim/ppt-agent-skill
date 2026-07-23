"""mermaid_render.layout.er — Native erDiagram scene builder.

Parses ``erDiagram`` source, lays out entity cards with the Sugiyama layered
pipeline, and renders the result as an ``SvgScene`` with:

  * Measured entity cards (header + attribute rows × row height + padding).
  * Relationship lines routed from card boundaries (not entity centres).
  * Cardinality glyphs rendered in the tangent/normal frame of each edge
    segment (crow's feet have feet at the entity, convergence on the line).
  * Main line trimmed by the glyph reserve so marks never overlap the line.
  * Labels placed at the midpoint of the trimmed segment.

Public API
----------
``parse_er_cardinality(card_str)``
    Parse a raw cardinality token pair (e.g. ``"||--o{"`` ) into a
    ``(CardinalityEnd, CardinalityEnd)`` tuple.

``layout_er_scene(src, *, width_hint)``
    Full parse → layout → scene pipeline.  Returns an ``SvgScene``.
"""
from __future__ import annotations

import hashlib
import math
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ._geometry import FinalizedLayout, RoutedEdge

from ..scene import (
    AccessibilityMetadata,
    FillStyle,
    LAYER_BACKGROUND,
    LAYER_EDGES,
    LAYER_LABELS,
    LAYER_NODES,
    LAYER_ORDER,
    PaintStyle,
    SceneCircle,
    SceneLine,
    SceneRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)
from ._constants import (
    CardinalityEnd,
    Maximum,
    Minimum,
    _Edge,
    _Node,
    CANVAS_PAD,
    RANK_GAP,
)
from ._layout import (
    _assign_coordinates,
    _assign_ranks,
    _break_cycles,
    _minimize_crossings,
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
_UK_COLOR = "#059669"

# ── Card geometry constants ───────────────────────────────────────────────────

_CARD_W = 200            # entity card width (px)
_CARD_HDR_H = 32         # header row height
_CARD_ROW_H = 20         # per-attribute row height
_CARD_PAD_V = 6          # vertical padding (top + bottom inside body)
_FONT_HEADER = 13
_FONT_ATTR = 11
_FONT_LABEL = 10

# Glyph rendering dimensions
_GLYPH_HALF_W = 10.0     # half-width of bars / crow's foot spread
_GLYPH_CIRC_R = 4.5      # radius of the optional-zero circle
_GLYPH_FOOT_CONV = 12.0  # offset to crow's foot convergence point
_GLYPH_BAR1 = 6.0        # offset of first (max=ONE) bar
_GLYPH_BAR2_DELTA = 6.0  # additional offset of second (min=ONE) bar past max symbol
_GLYPH_CIRC_DELTA = 8.0  # additional offset of min=ZERO circle past max symbol


# ── Cardinality parsing ───────────────────────────────────────────────────────

_CARD_TOKEN_RE = re.compile(
    r'^(?P<src>[|o}{]{1,2})[-.]{1,2}(?P<dst>[|o}{]{1,2})$'
)


def _parse_cardinality_token(tok: str) -> CardinalityEnd:
    """Parse a single cardinality token character-set into a CardinalityEnd.

    The rule is character-set–based (order-independent):
      * ``{`` or ``}`` present → maximum = MANY; else → maximum = ONE
      * ``o`` present          → minimum = ZERO; else → minimum = ONE

    This works identically for left-side and right-side tokens because the
    semantic meaning is encoded in the *set of characters*, not their order.
    """
    maximum = Maximum.MANY if any(c in tok for c in "{}") else Maximum.ONE
    minimum = Minimum.ZERO if "o" in tok else Minimum.ONE
    return CardinalityEnd(minimum=minimum, maximum=maximum)


def parse_er_cardinality(card_str: str) -> tuple[CardinalityEnd, CardinalityEnd]:
    """Parse a full cardinality string into ``(src_end, dst_end)``.

    Examples::

        parse_er_cardinality("||--||")  → (ONE..ONE,   ONE..ONE)
        parse_er_cardinality("||--o{")  → (ONE..ONE,   ZERO..MANY)
        parse_er_cardinality("}|--||")  → (ONE..MANY,  ONE..ONE)
        parse_er_cardinality("|o--|{")  → (ZERO..ONE,  ONE..MANY)

    ``card_str`` must match ``<left_token><-- or ..><right_token>``.
    """
    m = _CARD_TOKEN_RE.match(card_str.strip())
    if not m:
        raise ValueError(f"Cannot parse ER cardinality string: {card_str!r}")
    return _parse_cardinality_token(m.group("src")), _parse_cardinality_token(m.group("dst"))


# ── Card measurement ──────────────────────────────────────────────────────────

def _card_height(attrs: list[dict]) -> float:
    """Total pixel height of an entity card with the given attribute list."""
    body_h = len(attrs) * _CARD_ROW_H + _CARD_PAD_V * 2
    return float(_CARD_HDR_H + max(body_h, _CARD_PAD_V * 2))


# ── Glyph geometry ────────────────────────────────────────────────────────────

def _glyph_reserve(end: CardinalityEnd) -> float:
    """How far (px) from the card boundary the glyph extends into the line."""
    max_ext = _GLYPH_FOOT_CONV if end.maximum == Maximum.MANY else _GLYPH_BAR1
    if end.minimum == Minimum.ONE:
        return max_ext + _GLYPH_BAR2_DELTA + 2.0
    else:
        return max_ext + _GLYPH_CIRC_DELTA + _GLYPH_CIRC_R + 2.0


def _er_glyph_elements(
    x: float, y: float, dx: float, dy: float,
    end: CardinalityEnd, id_prefix: str,
) -> list:
    """Scene elements (SceneLine / SceneCircle) for a cardinality end glyph.

    ``(dx, dy)`` is the outward direction from entity toward the other entity.

    Glyph structure from entity boundary outward:
      1. Maximum: crow's foot (MANY) or single bar (ONE) — closest to entity.
      2. Minimum: bar (ONE) or circle (ZERO) — further along the edge.

    Crow's foot: tines at the entity boundary, convergence at ``_GLYPH_FOOT_CONV``
    outward — feet near entity, heel on the line (standard Crow's Foot notation).
    """
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return []
    tx, ty = dx / L, dy / L
    nx, ny = -ty, tx
    hw = _GLYPH_HALF_W
    stroke = PaintStyle(stroke=StrokeStyle(color=_REL_STROKE, width=1.5))
    stroke_open = PaintStyle(
        fill=FillStyle(color="none"),
        stroke=StrokeStyle(color=_REL_STROKE, width=1.5),
    )
    elems: list = []

    if end.maximum == Maximum.MANY:
        conv_x = x + tx * _GLYPH_FOOT_CONV
        conv_y = y + ty * _GLYPH_FOOT_CONV
        for fi, spread in enumerate((-hw, 0.0, hw)):
            toe_x = x + nx * spread
            toe_y = y + ny * spread
            elems.append(SceneLine(
                element_id=f"{id_prefix}-f{fi}",
                x1=toe_x, y1=toe_y, x2=conv_x, y2=conv_y,
                paint=stroke, semantic_role="cardinality-glyph",
            ))
        max_ext = _GLYPH_FOOT_CONV
    else:
        bx = x + tx * _GLYPH_BAR1
        by = y + ty * _GLYPH_BAR1
        elems.append(SceneLine(
            element_id=f"{id_prefix}-b1",
            x1=bx - nx * hw, y1=by - ny * hw,
            x2=bx + nx * hw, y2=by + ny * hw,
            paint=stroke, semantic_role="cardinality-glyph",
        ))
        max_ext = _GLYPH_BAR1

    if end.minimum == Minimum.ONE:
        b2x = x + tx * (max_ext + _GLYPH_BAR2_DELTA)
        b2y = y + ty * (max_ext + _GLYPH_BAR2_DELTA)
        elems.append(SceneLine(
            element_id=f"{id_prefix}-b2",
            x1=b2x - nx * hw, y1=b2y - ny * hw,
            x2=b2x + nx * hw, y2=b2y + ny * hw,
            paint=stroke, semantic_role="cardinality-glyph",
        ))
    else:
        cx = x + tx * (max_ext + _GLYPH_CIRC_DELTA)
        cy = y + ty * (max_ext + _GLYPH_CIRC_DELTA)
        elems.append(SceneCircle(
            element_id=f"{id_prefix}-c",
            cx=cx, cy=cy, r=_GLYPH_CIRC_R,
            paint=stroke_open, semantic_role="cardinality-glyph",
        ))

    return elems


# ── Boundary intersection ─────────────────────────────────────────────────────

def _rect_boundary_pt(
    cx: float, cy: float, w: float, h: float, dx: float, dy: float
) -> tuple[float, float]:
    """Point on the boundary of rect centred at (cx, cy) with size (w, h).

    Shoots a ray in direction (dx, dy) from the centre and returns the first
    intersection with the rect boundary.  Returns the centre for zero vectors.
    """
    hw, hh = w / 2.0, h / 2.0
    ts: list[float] = []
    if dx > 1e-9:
        ts.append(hw / dx)
    elif dx < -1e-9:
        ts.append(-hw / dx)
    if dy > 1e-9:
        ts.append(hh / dy)
    elif dy < -1e-9:
        ts.append(-hh / dy)
    t = min((c for c in ts if c > 0.0), default=0.0)
    return cx + dx * t, cy + dy * t


# ── ER source parser ──────────────────────────────────────────────────────────

_REL_RE = re.compile(
    r'^(?P<e1>[\w-]+)\s+'
    r'(?P<card_src>[|o}{]{1,2})'
    r'(?P<line>-{1,2}|\.{1,2})'
    r'(?P<card_dst>[|o}{]{1,2})'
    r'\s+(?P<e2>[\w-]+)\s*:\s*(?P<lbl>.*)$'
)
_ENTITY_RE = re.compile(r'^([\w-]+)\s*\{')
_ATTR_RE = re.compile(
    r'^(?P<type>\S+)\s+(?P<name>\S+)'
    r'(?:\s+(?P<constraint>PK|FK|UK))?'
    r'(?:\s+"(?P<comment>[^"]*)")?'
    r'\s*$'
)


def _parse_er_source(src: str) -> tuple[dict[str, list[dict]], list[dict]]:
    """Return ``(entities, relationships)``.

    ``entities``: ``{name: [{type, name, constraint, comment}]}``
    ``relationships``: ``[{from, to, label, card_src, card_dst, dotted}]``
    """
    entities: dict[str, list[dict]] = {}
    relationships: list[dict] = []
    current_entity: Optional[str] = None

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("erdiagram") or stripped.startswith(("%%", "//")):
            continue
        if stripped == "}":
            current_entity = None
            continue

        m = _ENTITY_RE.match(stripped)
        if m:
            ename = m.group(1)
            entities.setdefault(ename, [])
            current_entity = ename
            continue

        if current_entity is not None:
            m = _ATTR_RE.match(stripped)
            if m:
                entities[current_entity].append({
                    "type": m.group("type"),
                    "name": m.group("name"),
                    "constraint": (m.group("constraint") or "").strip(),
                    "comment": (m.group("comment") or "").strip(),
                })
            continue

        m = _REL_RE.match(stripped)
        if m:
            e1, e2 = m.group("e1"), m.group("e2")
            for eid in (e1, e2):
                entities.setdefault(eid, [])
            dotted = m.group("line").startswith(".")
            relationships.append({
                "from": e1,
                "to": e2,
                "label": m.group("lbl").strip().strip('"'),
                "card_src": _parse_cardinality_token(m.group("card_src")),
                "card_dst": _parse_cardinality_token(m.group("card_dst")),
                "dotted": dotted,
            })

    return entities, relationships


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_er_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse erDiagram source and return a fully laid-out ``SvgScene``.

    Delegates layout geometry to ``compile_er()`` and uses the resulting
    ``FinalizedLayout`` for entity positions and edge waypoints.  Rendering
    logic (entity cards, cardinality glyphs, labels) is unchanged.
    """
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

    # ── Geometry from compiler ────────────────────────────────────────────────
    fl = compile_er(src, width_hint=width_hint)

    canvas_w = fl.canvas_bounds.w
    canvas_h = fl.canvas_bounds.h
    zoom = 1.0
    if width_hint and canvas_w > 0 and width_hint < canvas_w:
        zoom = width_hint / canvas_w

    # Build a lookup from relationship index → RoutedEdge (by edge_id "er-rel-N")
    routed_by_idx: dict[int, RoutedEdge] = {}
    for _re in fl.routed_edges:
        _eid = _re.edge_id
        if _eid.startswith("er-rel-"):
            try:
                routed_by_idx[int(_eid[7:])] = _re
            except ValueError:
                pass

    # ── Assemble SvgScene elements ────────────────────────────────────────────
    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []

    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    # Entity cards — positions from FinalizedLayout
    for eid, attrs in entities.items():
        if eid not in fl.node_layouts:
            continue
        _nl = fl.node_layouts[eid]
        ex = _nl.outer_bounds.x
        ey = _nl.outer_bounds.y
        eh = _nl.outer_bounds.h

        # Header
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-hdr-{eid}",
            x=ex, y=ey, w=float(_CARD_W), h=float(_CARD_HDR_H),
            paint=PaintStyle(fill=FillStyle(color=_ENTITY_HEADER_FILL)),
            semantic_role="entity",
            data_attrs=(("data-entity", eid),),
        ))
        label_elements.append(SceneText(
            element_id=f"{scene_id}-hdr-lbl-{eid}",
            lines=(SceneTextLine(
                text=eid,
                x=ex + _CARD_W / 2,
                y=ey + _CARD_HDR_H / 2 + _FONT_HEADER * 0.35,
                font_size=float(_FONT_HEADER),
                font_weight=700,
                fill_color=_ENTITY_HEADER_TEXT,
            ),),
            text_anchor="middle",
        ))

        # Body (attribute area)
        body_h = eh - _CARD_HDR_H
        node_elements.append(SceneRect(
            element_id=f"{scene_id}-body-{eid}",
            x=ex, y=ey + _CARD_HDR_H,
            w=float(_CARD_W), h=body_h,
            paint=PaintStyle(
                fill=FillStyle(color=_ENTITY_BODY_FILL),
                stroke=StrokeStyle(color=_ENTITY_STROKE, width=1.0),
            ),
        ))

        # Divider
        if attrs:
            node_elements.append(SceneRect(
                element_id=f"{scene_id}-div-{eid}",
                x=ex, y=ey + _CARD_HDR_H,
                w=float(_CARD_W), h=1.0,
                paint=PaintStyle(fill=FillStyle(color=_ENTITY_STROKE)),
            ))

        # Attribute rows
        for ai, attr in enumerate(attrs):
            ay = ey + _CARD_HDR_H + _CARD_PAD_V + ai * _CARD_ROW_H
            constraint = attr.get("constraint", "")

            # Key/type badge
            if constraint in ("PK", "FK", "UK"):
                badge_color = {"PK": _PK_COLOR, "FK": _FK_COLOR, "UK": _UK_COLOR}[constraint]
                label_elements.append(SceneText(
                    element_id=f"{scene_id}-badge-{eid}-{ai}",
                    lines=(SceneTextLine(
                        text=constraint,
                        x=ex + 6,
                        y=ay + _FONT_ATTR + 2,
                        font_size=9.0,
                        font_weight=700,
                        fill_color=badge_color,
                    ),),
                    text_anchor="start",
                ))
                type_x = ex + 28
            else:
                type_x = ex + 6

            # Type
            label_elements.append(SceneText(
                element_id=f"{scene_id}-type-{eid}-{ai}",
                lines=(SceneTextLine(
                    text=attr["type"],
                    x=type_x,
                    y=ay + _FONT_ATTR + 2,
                    font_size=float(_FONT_ATTR) - 1,
                    fill_color=_ATTR_TEXT,
                ),),
                text_anchor="start",
            ))

            # Name
            label_elements.append(SceneText(
                element_id=f"{scene_id}-name-{eid}-{ai}",
                lines=(SceneTextLine(
                    text=attr["name"],
                    x=ex + _CARD_W - 6,
                    y=ay + _FONT_ATTR + 2,
                    font_size=float(_FONT_ATTR),
                    font_weight=500,
                    fill_color=_ATTR_TEXT,
                ),),
                text_anchor="end",
            ))

    # Relationship edges
    for rel_idx, rel in enumerate(relationships):
        fe, te = rel["from"], rel["to"]
        if fe not in fl.node_layouts or te not in fl.node_layouts:
            continue
        fnl = fl.node_layouts[fe]
        tnl = fl.node_layouts[te]

        fh = fnl.outer_bounds.h
        th = tnl.outer_bounds.h
        fcx = fnl.outer_bounds.x + _CARD_W / 2
        fcy = fnl.outer_bounds.y + fh / 2
        tcx = tnl.outer_bounds.x + _CARD_W / 2
        tcy = tnl.outer_bounds.y + th / 2

        vx, vy = tcx - fcx, tcy - fcy
        norm = math.hypot(vx, vy) or 1.0
        uvx, uvy = vx / norm, vy / norm

        # Boundary intersection points (needed for glyph placement)
        src_bx, src_by = _rect_boundary_pt(fcx, fcy, float(_CARD_W), fh, uvx, uvy)
        dst_bx, dst_by = _rect_boundary_pt(tcx, tcy, float(_CARD_W), th, -uvx, -uvy)

        card_src: Optional[CardinalityEnd] = rel["card_src"]
        card_dst: Optional[CardinalityEnd] = rel["card_dst"]

        # Trimmed line endpoints from FinalizedLayout waypoints
        _re_obj = routed_by_idx.get(rel_idx)
        if _re_obj is not None:
            _wps = _re_obj.waypoints
            lx1 = _wps[0].x
            ly1 = _wps[0].y
            lx2 = _wps[1].x
            ly2 = _wps[1].y
        else:
            src_r = _glyph_reserve(card_src) if card_src else 4.0
            dst_r = _glyph_reserve(card_dst) if card_dst else 4.0
            lx1 = src_bx + uvx * src_r
            ly1 = src_by + uvy * src_r
            lx2 = dst_bx + (-uvx) * dst_r
            ly2 = dst_by + (-uvy) * dst_r

        # Draw main line if long enough to be visible
        seg_len = math.hypot(lx2 - lx1, ly2 - ly1)
        if seg_len > 1.0:
            dash: Optional[str] = "6 4" if rel["dotted"] else None
            edge_elements.append(SceneLine(
                element_id=f"{scene_id}-rel-{rel_idx}",
                x1=lx1, y1=ly1, x2=lx2, y2=ly2,
                paint=PaintStyle(
                    stroke=StrokeStyle(
                        color=_REL_STROKE, width=1.5,
                        dasharray=dash or "",
                    )
                ),
                semantic_role="relation",
                data_attrs=(
                    ("data-from", fe),
                    ("data-to", te),
                    ("data-label", rel["label"]),
                ),
            ))

        # Cardinality glyphs as proper scene elements
        if card_src:
            edge_elements.extend(_er_glyph_elements(
                src_bx, src_by, uvx, uvy, card_src,
                id_prefix=f"{scene_id}-gs-{rel_idx}",
            ))
        if card_dst:
            edge_elements.extend(_er_glyph_elements(
                dst_bx, dst_by, -uvx, -uvy, card_dst,
                id_prefix=f"{scene_id}-gd-{rel_idx}",
            ))

        # Relationship label at trimmed-segment midpoint
        if rel["label"]:
            mid_x = (lx1 + lx2) / 2
            mid_y = (ly1 + ly2) / 2
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
        width=canvas_w * zoom,
        height=canvas_h * zoom,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title="ER diagram",
            description=(
                f"ER diagram with {len(entity_names)} entities and {n_rels} relationships"
            ),
        ),
        layers=layers,
    )


# ── Compiler: layout → FinalizedLayout ───────────────────────────────────────

def compile_er(src: str, *, width_hint: int = 0) -> "FinalizedLayout":
    """Parse erDiagram source and return a ``FinalizedLayout`` IR.

    Runs the full Sugiyama pipeline (rank assignment, crossing minimisation,
    coordinate assignment) and packages the result as an immutable geometry
    record.  The caller may use this for rendering (HTML or SVG) without
    repeating the layout work.

    Returns
    -------
    FinalizedLayout
        ``node_layouts[eid].outer_bounds`` holds each entity card's bounding
        box; ``routed_edges[i].waypoints`` holds the trimmed line endpoints
        for relationship ``i`` (matching the order of relationships from
        ``_parse_er_source``).  ``canvas_bounds`` is the natural (unscaled)
        canvas rectangle.
    """
    from collections import defaultdict

    from ._geometry import (
        EdgeLabelLayout,
        FinalizedLayout,
        LayoutDiagnostics,
        MarkerKind,
        NodeLayout,
        Point,
        PortLayout,
        PortSide,
        Rect,
        RoutedEdge,
        TextLayout,
    )

    entities, relationships = _parse_er_source(src)
    entity_names = list(entities.keys())

    # Empty diagram — return a minimal layout with empty maps
    if not entity_names:
        w = float(max(width_hint or 400, 400))
        h = 160.0
        _diag = LayoutDiagnostics(unsupported_options=(), route_failures=(), warnings=())
        _cr = Rect(0.0, 0.0, w, h)
        return FinalizedLayout(
            node_layouts=MappingProxyType({}),
            group_layouts=MappingProxyType({}),
            routed_edges=(),
            visible_bounds=_cr,
            diagram_padding=float(CANVAS_PAD),
            canvas_bounds=_cr,
            direction="TB",
            diagnostics=_diag,
            routing_failures=(),
        )

    # ── 1. Build Sugiyama graph ───────────────────────────────────────────────
    nodes: dict[str, _Node] = {
        eid: _Node(
            id=eid, label=eid, shape="rect",
            width=_CARD_W,
            height=int(_card_height(entities[eid])),
        )
        for eid in entity_names
    }
    sugi_edges: list[_Edge] = [
        _Edge(src=rel["from"], dst=rel["to"], label=rel["label"])
        for rel in relationships
    ]

    _break_cycles(nodes, sugi_edges)
    _assign_ranks(nodes, sugi_edges)
    _minimize_crossings(nodes, sugi_edges)
    _assign_coordinates(nodes)

    # ── 2. Measure card heights ───────────────────────────────────────────────
    heights: dict[str, float] = {
        eid: _card_height(attrs) for eid, attrs in entities.items()
    }

    # ── 3. Override y-positions per rank with measured heights ────────────────
    rank_to_nids: dict[int, list[str]] = defaultdict(list)
    for nid, n in nodes.items():
        if not n.is_dummy:
            rank_to_nids[n.rank].append(nid)

    y_cursor = float(CANVAS_PAD)
    for rank in range(max(rank_to_nids, default=0) + 1):
        nids_in_rank = rank_to_nids.get(rank, [])
        if not nids_in_rank:
            continue
        rank_h = max(heights[nid] for nid in nids_in_rank)
        for nid in nids_in_rank:
            eh_nid = heights[nid]
            nodes[nid].y = int(y_cursor + (rank_h - eh_nid) / 2)
        y_cursor += rank_h + RANK_GAP

    # ── 4. Natural canvas dimensions (no zoom applied) ────────────────────────
    real_nids = [(nid, n) for nid, n in nodes.items() if not n.is_dummy]
    if real_nids:
        canvas_w = float(max(n.x + _CARD_W for _, n in real_nids) + CANVAS_PAD)
        canvas_h = float(
            max(n.y + heights[nid] for nid, n in real_nids) + CANVAS_PAD
        )
    else:
        canvas_w = float(max(width_hint or 400, 400))
        canvas_h = float(y_cursor - RANK_GAP + CANVAS_PAD)

    # ── 5. Helper: minimal TextLayout stub ────────────────────────────────────
    def _stub_tl(w: float, h: float) -> TextLayout:
        return TextLayout(
            lines=(),
            width=w,
            height=h,
            line_height=h,
            min_content_width=0.0,
            max_content_width=w,
            resolved_font_path=None,
            resolved_font_family="sans-serif",
        )

    # ── 6. Helper: unit vector → PortSide ────────────────────────────────────
    def _tangent_to_side(ux: float, uy: float) -> PortSide:
        if uy > 0:
            return PortSide.BOTTOM
        if uy < 0:
            return PortSide.TOP
        if ux > 0:
            return PortSide.RIGHT
        return PortSide.LEFT

    # ── 7. Build NodeLayout objects ───────────────────────────────────────────
    node_layouts: dict[str, NodeLayout] = {}
    for eid, n in nodes.items():
        if n.is_dummy:
            continue
        eh = heights[eid]
        bounds = Rect(float(n.x), float(n.y), float(_CARD_W), eh)
        node_layouts[eid] = NodeLayout(
            node_id=eid,
            semantic_shape="er-entity",
            outer_bounds=bounds,
            content_bounds=bounds,
            title_layout=_stub_tl(float(_CARD_W), float(_CARD_HDR_H)),
            subtitle_layout=None,
            member_layouts=(),
            icon_bounds=None,
            ports=(),
            css_classes=(),
            extra_css="",
            is_dummy=False,
            rank=n.rank,
        )

    # ── 8. Build RoutedEdge objects ───────────────────────────────────────────
    routed_edges_list: list[RoutedEdge] = []
    for rel_idx, rel in enumerate(relationships):
        fe, te = rel["from"], rel["to"]
        if fe not in nodes or te not in nodes:
            continue
        fn, tn = nodes[fe], nodes[te]
        if fn.is_dummy or tn.is_dummy:
            continue

        fh = heights[fe]
        th = heights[te]
        fcx = float(fn.x) + _CARD_W / 2
        fcy = float(fn.y) + fh / 2
        tcx = float(tn.x) + _CARD_W / 2
        tcy = float(tn.y) + th / 2

        vx, vy = tcx - fcx, tcy - fcy
        norm = math.hypot(vx, vy) or 1.0
        uvx, uvy = vx / norm, vy / norm

        src_bx, src_by = _rect_boundary_pt(fcx, fcy, float(_CARD_W), fh, uvx, uvy)
        dst_bx, dst_by = _rect_boundary_pt(tcx, tcy, float(_CARD_W), th, -uvx, -uvy)

        card_src: Optional[CardinalityEnd] = rel["card_src"]
        card_dst: Optional[CardinalityEnd] = rel["card_dst"]
        src_r = _glyph_reserve(card_src) if card_src else 4.0
        dst_r = _glyph_reserve(card_dst) if card_dst else 4.0

        lx1 = src_bx + uvx * src_r
        ly1 = src_by + uvy * src_r
        lx2 = dst_bx + (-uvx) * dst_r
        ly2 = dst_by + (-uvy) * dst_r

        src_port = PortLayout(
            node_id=fe,
            side=_tangent_to_side(uvx, uvy),
            position=Point(src_bx, src_by),
            direction=Point(uvx, uvy),
        )
        dst_port = PortLayout(
            node_id=te,
            side=_tangent_to_side(-uvx, -uvy),
            position=Point(dst_bx, dst_by),
            direction=Point(-uvx, -uvy),
        )

        mid_x = (lx1 + lx2) / 2
        mid_y = (ly1 + ly2) / 2

        label_layout: Optional[EdgeLabelLayout] = None
        if rel["label"]:
            label_layout = EdgeLabelLayout(
                text=rel["label"],
                layout=_stub_tl(10.0, 10.0),
                bounds=Rect(mid_x, mid_y, 1.0, 1.0),
                anchor_point=Point(mid_x, mid_y),
            )

        src_label_layout: Optional[EdgeLabelLayout] = None
        if card_src:
            src_label_layout = EdgeLabelLayout(
                text=str(card_src),
                layout=_stub_tl(10.0, 10.0),
                bounds=Rect(lx1, ly1, 1.0, 1.0),
                anchor_point=Point(lx1, ly1),
            )

        dst_label_layout: Optional[EdgeLabelLayout] = None
        if card_dst:
            dst_label_layout = EdgeLabelLayout(
                text=str(card_dst),
                layout=_stub_tl(10.0, 10.0),
                bounds=Rect(lx2, ly2, 1.0, 1.0),
                anchor_point=Point(lx2, ly2),
            )

        routed_edges_list.append(RoutedEdge(
            edge_id=f"er-rel-{rel_idx}",
            src_node_id=fe,
            dst_node_id=te,
            src_port=src_port,
            dst_port=dst_port,
            waypoints=(Point(lx1, ly1), Point(lx2, ly2)),
            edge_style="dotted" if rel["dotted"] else "solid",
            has_marker_end=False,
            has_marker_start=False,
            label_layout=label_layout,
            src_label_layout=src_label_layout,
            dst_label_layout=dst_label_layout,
            source_marker=MarkerKind.NONE,
            target_marker=MarkerKind.NONE,
        ))

    canvas_rect = Rect(0.0, 0.0, canvas_w, canvas_h)
    diag = LayoutDiagnostics(unsupported_options=(), route_failures=(), warnings=())

    return FinalizedLayout(
        node_layouts=MappingProxyType(node_layouts),
        group_layouts=MappingProxyType({}),
        routed_edges=tuple(routed_edges_list),
        visible_bounds=canvas_rect,
        diagram_padding=float(CANVAS_PAD),
        canvas_bounds=canvas_rect,
        direction="TB",
        diagnostics=diag,
        routing_failures=(),
    )


# ── HTML renderer ─────────────────────────────────────────────────────────────

def er_to_html(src: str, *, width_hint: int = 0) -> str:
    """Render erDiagram source as a self-contained HTML div string.

    Uses ``compile_er()`` for all geometry, then re-calls
    ``_parse_er_source()`` to obtain entity attribute data for row rendering.
    The output is a ``<div class="diagram mermaid-layout">`` containing entity
    card divs and an SVG overlay for edges and cardinality glyphs.

    Zoom is applied as a CSS ``zoom`` property on the container when the
    natural canvas width exceeds ``width_hint``.
    """
    import html as _html_er

    _h = lambda s: _html_er.escape(str(s), quote=True)  # noqa: E731

    fl = compile_er(src, width_hint=width_hint)
    entities, relationships = _parse_er_source(src)

    if not entities:
        raise ValueError("No entities found in erDiagram.")

    cw = fl.canvas_bounds.w
    ch = fl.canvas_bounds.h

    zoom = 1.0
    if width_hint and cw > 0 and width_hint < cw:
        zoom = width_hint / cw
    zoom_css = f"zoom:{zoom:.4f};" if abs(zoom - 1.0) > 0.005 else ""

    _lf = "var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif))"
    _edge_color = "var(--edge,var(--node-fg-dim,rgba(100,116,139,0.7)))"

    # ── SVG glyph helper (returns list of SVG element strings) ────────────────
    def _render_glyph_svg(
        bx: float, by: float, dx: float, dy: float, end: CardinalityEnd
    ) -> list[str]:
        L = math.hypot(dx, dy)
        if L < 1e-9:
            return []
        tx, ty = dx / L, dy / L
        nx, ny = -ty, tx
        hw = _GLYPH_HALF_W
        svg_parts: list[str] = []
        if end.maximum == Maximum.MANY:
            conv_x = bx + tx * _GLYPH_FOOT_CONV
            conv_y = by + ty * _GLYPH_FOOT_CONV
            for spread in (-hw, 0.0, hw):
                toe_x = bx + nx * spread
                toe_y = by + ny * spread
                svg_parts.append(
                    f'<line x1="{toe_x:.1f}" y1="{toe_y:.1f}" '
                    f'x2="{conv_x:.1f}" y2="{conv_y:.1f}" '
                    f'stroke="{_edge_color}" stroke-width="1.5"/>'
                )
            max_ext = _GLYPH_FOOT_CONV
        else:
            bar_x = bx + tx * _GLYPH_BAR1
            bar_y = by + ty * _GLYPH_BAR1
            svg_parts.append(
                f'<line x1="{(bar_x - nx * hw):.1f}" y1="{(bar_y - ny * hw):.1f}" '
                f'x2="{(bar_x + nx * hw):.1f}" y2="{(bar_y + ny * hw):.1f}" '
                f'stroke="{_edge_color}" stroke-width="1.5"/>'
            )
            max_ext = _GLYPH_BAR1
        if end.minimum == Minimum.ONE:
            b2x = bx + tx * (max_ext + _GLYPH_BAR2_DELTA)
            b2y = by + ty * (max_ext + _GLYPH_BAR2_DELTA)
            svg_parts.append(
                f'<line x1="{(b2x - nx * hw):.1f}" y1="{(b2y - ny * hw):.1f}" '
                f'x2="{(b2x + nx * hw):.1f}" y2="{(b2y + ny * hw):.1f}" '
                f'stroke="{_edge_color}" stroke-width="1.5"/>'
            )
        else:
            cx_ = bx + tx * (max_ext + _GLYPH_CIRC_DELTA)
            cy_ = by + ty * (max_ext + _GLYPH_CIRC_DELTA)
            svg_parts.append(
                f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="{_GLYPH_CIRC_R:.1f}" '
                f'fill="none" stroke="{_edge_color}" stroke-width="1.5"/>'
            )
        return svg_parts

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative; width:{cw}px; height:{ch}px; {zoom_css}">'
    )

    # ── Entity cards ──────────────────────────────────────────────────────────
    for eid, attrs in entities.items():
        if eid not in fl.node_layouts:
            continue
        _nl = fl.node_layouts[eid]
        ex = _nl.outer_bounds.x
        ey = _nl.outer_bounds.y
        ew = _nl.outer_bounds.w
        eh = _nl.outer_bounds.h

        parts.append(
            f'<div class="node node-rect er-entity" data-node-id="{_h(eid)}" style="'
            f'position:absolute; left:{ex}px; top:{ey}px; '
            f'width:{ew}px; height:{eh}px; '
            f'box-sizing:border-box; overflow:hidden; '
            f'border:1px solid var(--node-border,var(--card-border,#DAD7CE)); '
            f'border-top:3px solid var(--node-title-fg,var(--accent-1,#60a5fa)); '
            f'border-radius:var(--node-radius,8px); '
            f'background:linear-gradient(180deg,'
            f'var(--node-bg-from,var(--card-bg-from,#ffffff)),'
            f'var(--node-bg-to,var(--card-bg-to,#F7F6F2))); '
            f'box-shadow:var(--node-shadow,'
            f'0 1px 2px rgba(25,26,23,0.06),0 1px 0 rgba(25,26,23,0.03));">'
        )
        # Entity name header
        parts.append(
            f'<div style="height:{_CARD_HDR_H}px; display:flex; align-items:center; '
            f'justify-content:center; padding:0 8px; box-sizing:border-box;">'
            f'<span class="node-label" style="'
            f'font-size:13px; font-weight:700; '
            f'color:var(--node-fg,var(--text-primary,#191A17)); '
            f'font-family:var(--label-font,var(--font-primary,-apple-system,Inter,sans-serif)); '
            f'overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">'
            f'{_h(eid)}</span></div>'
        )
        # Attribute rows
        if attrs:
            parts.append(
                f'<div style="height:1px; '
                f'background:var(--node-border,var(--card-border,#DAD7CE));"></div>'
            )
            for attr in attrs:
                constraint = attr["constraint"]
                if constraint == "PK":
                    badge_html = (
                        f'<span style="font-size:9px;font-weight:700;'
                        f'color:var(--accent-3,#B7791F);'
                        f'background:rgba(183,121,31,0.12);'
                        f'border-radius:3px;padding:0 3px;margin-right:4px;'
                        f'flex-shrink:0;font-family:{_lf};">PK</span>'
                    )
                elif constraint == "FK":
                    badge_html = (
                        f'<span style="font-size:9px;font-weight:700;'
                        f'color:var(--accent-1,#60a5fa);'
                        f'background:rgba(96,165,250,0.12);'
                        f'border-radius:3px;padding:0 3px;margin-right:4px;'
                        f'flex-shrink:0;font-family:{_lf};">FK</span>'
                    )
                elif constraint == "UK":
                    badge_html = (
                        f'<span style="font-size:9px;font-weight:700;'
                        f'color:var(--accent-2,#34d399);'
                        f'background:rgba(52,211,153,0.12);'
                        f'border-radius:3px;padding:0 3px;margin-right:4px;'
                        f'flex-shrink:0;font-family:{_lf};">UK</span>'
                    )
                else:
                    badge_html = ""
                comment_html = ""
                if attr["comment"]:
                    comment_html = (
                        f'<span style="font-size:9px;font-style:italic;'
                        f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                        f'margin-left:4px;overflow:hidden;text-overflow:ellipsis;'
                        f'white-space:nowrap;flex-shrink:1;font-family:{_lf};">'
                        f'{_h(attr["comment"])}</span>'
                    )
                parts.append(
                    f'<div style="height:{_CARD_ROW_H}px;display:flex;align-items:center;'
                    f'padding:0 8px;overflow:hidden;box-sizing:border-box;">'
                    f'{badge_html}'
                    f'<span style="font-size:10px;'
                    f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
                    f'margin-right:4px;flex-shrink:0;font-family:{_lf};">'
                    f'{_h(attr["type"])}</span>'
                    f'<span style="font-size:11px;font-weight:500;'
                    f'color:var(--node-fg,var(--text-primary,#191A17));'
                    f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
                    f'flex:1;font-family:{_lf};">'
                    f'{_h(attr["name"])}</span>'
                    f'{comment_html}'
                    f'</div>'
                )
        parts.append('</div>')  # close entity box

    # ── SVG overlay: edge lines + crow's feet ─────────────────────────────────
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{cw}px;height:{ch}px;'
        f'overflow:visible;pointer-events:none;">'
    )

    edge_labels: list[tuple[float, float, str]] = []

    for rel in relationships:
        fe, te = rel["from"], rel["to"]
        if fe not in fl.node_layouts or te not in fl.node_layouts:
            continue
        fnl = fl.node_layouts[fe]
        tnl = fl.node_layouts[te]

        fh = fnl.outer_bounds.h
        th = tnl.outer_bounds.h
        fcx = fnl.outer_bounds.x + fnl.outer_bounds.w / 2
        fcy = fnl.outer_bounds.y + fh / 2
        tcx = tnl.outer_bounds.x + tnl.outer_bounds.w / 2
        tcy = tnl.outer_bounds.y + th / 2

        vx, vy = tcx - fcx, tcy - fcy
        norm = math.hypot(vx, vy) or 1.0
        uvx, uvy = vx / norm, vy / norm

        src_bx, src_by = _rect_boundary_pt(fcx, fcy, fnl.outer_bounds.w, fh, uvx, uvy)
        dst_bx, dst_by = _rect_boundary_pt(tcx, tcy, tnl.outer_bounds.w, th, -uvx, -uvy)

        card_src: Optional[CardinalityEnd] = rel["card_src"]
        card_dst: Optional[CardinalityEnd] = rel["card_dst"]
        src_r = _glyph_reserve(card_src) if card_src else 4.0
        dst_r = _glyph_reserve(card_dst) if card_dst else 4.0

        lx1 = src_bx + uvx * src_r
        ly1 = src_by + uvy * src_r
        lx2 = dst_bx + (-uvx) * dst_r
        ly2 = dst_by + (-uvy) * dst_r

        dash = ' stroke-dasharray="6 4"' if rel["dotted"] else ""
        if math.hypot(lx2 - lx1, ly2 - ly1) > 1.0:
            parts.append(
                f'<line x1="{lx1:.1f}" y1="{ly1:.1f}" '
                f'x2="{lx2:.1f}" y2="{ly2:.1f}" '
                f'stroke="{_edge_color}" stroke-width="1.5"{dash}'
                f' data-src="{_h(fe)}" data-dst="{_h(te)}"/>'
            )
        else:
            parts.append(
                f'<line x1="{src_bx:.1f}" y1="{src_by:.1f}" '
                f'x2="{dst_bx:.1f}" y2="{dst_by:.1f}" '
                f'stroke="{_edge_color}" stroke-width="1.5"{dash}'
                f' data-src="{_h(fe)}" data-dst="{_h(te)}"/>'
            )

        if card_src:
            parts.extend(_render_glyph_svg(src_bx, src_by, uvx, uvy, card_src))
        if card_dst:
            parts.extend(_render_glyph_svg(dst_bx, dst_by, -uvx, -uvy, card_dst))

        if rel["label"]:
            edge_labels.append(((lx1 + lx2) / 2, (ly1 + ly2) / 2, rel["label"]))

    parts.append('</svg>')

    # ── Edge labels as HTML overlaid above the SVG ────────────────────────────
    for lx, ly, lbl in edge_labels:
        parts.append(
            f'<span class="edge-label" style="'
            f'position:absolute;left:{lx:.0f}px;top:{ly:.0f}px;'
            f'transform:translate(-50%,-50%);'
            f'font-size:11px;font-weight:500;'
            f'color:var(--node-fg-dim,var(--text-secondary,#75736C));'
            f'background:var(--edge-label-bg,var(--node-bg-from,#F7F6F2));'
            f'padding:1px 4px;border-radius:3px;'
            f'font-family:{_lf};'
            f'white-space:nowrap;pointer-events:none;z-index:2;">'
            f'{_h(lbl)}</span>'
        )

    parts.append('</div>')
    return "\n".join(parts)
