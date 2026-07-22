"""C4 diagram layout and rendering.

Implements a dedicated shelf/row packer matching Mermaid 11.15's ordered
Bounds.insert() algorithm, bypassing the generic DAG rank-assignment pipeline.

MIT notice (Bounds.insert port):
  Portions of this file are derived from Mermaid (https://github.com/mermaid-js/mermaid),
  copyright (c) 2014-2023 Knut Sveidqvist. Licensed under the MIT License.
  https://github.com/mermaid-js/mermaid/blob/develop/LICENSE
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from html import escape as _h
from typing import Optional


# ── Mermaid 11.15 C4 layout defaults ─────────────────────────────────────────

C4_NODE_W: int = 216          # c4ShapeWidth
C4_PERSON_H: int = 134        # Person box taller (includes 48px person sprite area)
C4_SYSTEM_H: int = 86         # System / Container / Component default height
C4_LAYOUT_WIDTH: int = 832    # Internal packing canvas (≈ screen.availWidth in Mermaid)
C4_SHAPE_MARGIN: int = 50     # c4ShapeMargin
C4_SHAPES_PER_ROW: int = 4    # c4MaximumNumberOfElements
C4_TITLE_H: int = 66          # Height reserved for title area + padding


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class C4Item:
    alias: str
    kind: str            # "person" | "person_ext" | "system" | "system_ext" | …
    label: str
    description: str
    is_external: bool
    technology: str = ""  # for Container/Component: third arg (e.g. "Java", "PostgreSQL")
    boundary: Optional[str] = None


@dataclass
class C4Relationship:
    src: str
    dst: str
    label: str
    rel_type: str = "rel"  # "rel" | "birel" | "rel_d" | "rel_u" | "rel_l" | "rel_r"


@dataclass
class C4Boundary:
    id: str
    label: str
    members: list[str] = field(default_factory=list)
    parent: Optional[str] = None  # parent boundary id when nested


@dataclass
class C4Box:
    alias: str
    width: float
    height: float
    x: float = 0.0
    y: float = 0.0


# ── Bounds packer (port of Mermaid 11.15 Bounds.insert()) ────────────────────

class C4Bounds:
    """Ordered row packer matching Mermaid 11.15 C4 Bounds.insert().

    Ported from mermaid/packages/mermaid/src/diagrams/c4/svgDraw.ts.
    MIT License — see module docstring for attribution.
    """

    def __init__(
        self,
        *,
        start_x: float,
        start_y: float,
        width_limit: float,
        shape_margin: float = 50.0,
        shapes_per_row: int = 4,
        next_line_padding_x: float = 0.0,
    ) -> None:
        if width_limit <= start_x:
            raise ValueError("width_limit must be greater than start_x")
        if shapes_per_row < 1:
            raise ValueError("shapes_per_row must be at least 1")

        self.start_x = start_x
        self.start_y = start_y
        self.width_limit = width_limit
        self.shape_margin = shape_margin
        self.shapes_per_row = shapes_per_row
        self.next_line_padding_x = next_line_padding_x

        self.next_start_x = start_x
        self.next_stop_x = start_x
        self.next_start_y = start_y
        self.next_stop_y = start_y
        self.count = 0

        self.max_right = start_x
        self.max_bottom = start_y

    def insert(self, box: C4Box) -> None:
        self.count += 1

        # Mermaid uses one margin before the first item and two thereafter.
        first_in_row = self.next_start_x == self.next_stop_x
        x = self.next_stop_x + (
            self.shape_margin if first_in_row else self.shape_margin * 2
        )
        y = self.next_start_y + self.shape_margin * 2

        right = x + box.width
        bottom = y + box.height

        should_wrap = (
            x >= self.width_limit
            or right >= self.width_limit
            or self.count > self.shapes_per_row
        )

        if should_wrap:
            previous_row_bottom = self.next_stop_y

            x = (
                self.next_start_x
                + self.shape_margin
                + self.next_line_padding_x
            )
            y = previous_row_bottom + self.shape_margin * 2

            right = x + box.width
            bottom = y + box.height

            self.next_stop_x = right
            self.next_start_y = previous_row_bottom
            self.next_stop_y = bottom
            self.count = 1

        box.x = x
        box.y = y

        self.next_start_x = min(self.next_start_x, x)
        self.next_start_y = min(self.next_start_y, y)
        self.next_stop_x = max(self.next_stop_x, right)
        self.next_stop_y = max(self.next_stop_y, bottom)

        self.max_right = max(self.max_right, right)
        self.max_bottom = max(self.max_bottom, bottom)


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _mermaid_edge_point(
    src_x: float, src_y: float,    # source node top-left
    src_cx: float, src_cy: float,  # source node center
    src_w: float, src_h: float,    # source dimensions
    dst_cx: float, dst_cy: float,  # target node center
) -> tuple[float, float]:
    """Intersection geometry matching Mermaid 11.15 C4 edge attachment.

    Slope is computed from source top-left to target center (not center-to-center
    as in a conventional ray), then projected from the source center to find the
    exit point.  This pins the formula to the Mermaid 11.15 algorithm observed in
    c4-basic reference output; compare_gallery.py provides visual ground truth.

    MIT notice: inspired by mermaid/packages/mermaid/src/diagrams/c4/svgDraw.ts.
    """
    dx = dst_cx - src_x   # from top-left to target center
    dy = dst_cy - src_y   # from top-left to target center

    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return src_cx, src_cy

    hw = src_w / 2.0
    hh = src_h / 2.0

    if abs(dx) < 1e-9:
        return src_cx, src_cy + (hh if dy > 0 else -hh)
    if abs(dy) < 1e-9:
        return src_cx + (hw if dx > 0 else -hw), src_cy

    m = dy / dx  # slope from top-left to target center

    # Use the top-left-based slope to pick which edge to exit through,
    # then project from the center along that same slope.
    if abs(dy) * hw < abs(dx) * hh:
        # Exits left or right edge
        if dx > 0:
            return src_cx + hw, src_cy + m * hw
        else:
            return src_cx - hw, src_cy - m * hw
    else:
        # Exits top or bottom edge
        if dy > 0:
            return src_cx + hh / m, src_cy + hh
        else:
            return src_cx - hh / m, src_cy - hh


# ── Node HTML rendering ───────────────────────────────────────────────────────

_C4_TYPE_DISPLAY: dict[str, str] = {
    "person": "Person",
    "person_ext": "Person [Ext]",
    "system": "Software System",
    "system_ext": "Software System [Ext]",
    "system_db": "System DB",
    "system_db_ext": "System DB [Ext]",
    "system_queue": "System Queue",
    "system_queue_ext": "System Queue [Ext]",
    "systemdb": "System DB",
    "container": "Container",
    "container_ext": "Container [Ext]",
    "container_db": "Container DB",
    "container_db_ext": "Container DB [Ext]",
    "container_queue": "Container Queue",
    "container_queue_ext": "Container Queue [Ext]",
    "containerdb": "Container DB",
    "containerqueue": "Container Queue",
    "component": "Component",
    "component_ext": "Component [Ext]",
    "component_db": "Component DB",
    "component_db_ext": "Component DB [Ext]",
    "component_queue": "Component Queue",
    "component_queue_ext": "Component Queue [Ext]",
    "componentdb": "Component DB",
    "componentqueue": "Component Queue",
}

# Default accent for C4 nodes not inside a named boundary
_C4_ACCENT = "var(--node-title-fg,var(--accent-1,#60a5fa))"


def _render_c4_node(item: C4Item, box: C4Box) -> str:
    x, y = int(box.x), int(box.y)
    w, h = int(box.width), int(box.height)

    type_tag = _C4_TYPE_DISPLAY.get(item.kind, item.kind.capitalize())
    stereotype_html = _h(f"[{type_tag}]")
    label_html = _h(item.label)
    desc_html = _h(item.description) if item.description else ""

    kind_css = f"c4-{item.kind.replace('_', '-')}"

    if item.is_external:
        border_css = "border:1px solid #8a8a8a;"
        bg_css = "background:#999;"
        fg_css = "color:#fff;"
        top_border_css = ""
    else:
        border_css = "border:1.5px solid var(--node-border,var(--card-border,#DAD7CE));"
        bg_css = (
            "background:linear-gradient(180deg,"
            "var(--node-bg-from,var(--card-bg-from,#ffffff)),"
            "var(--node-bg-to,var(--card-bg-to,#F7F6F2)));"
        )
        fg_css = "color:var(--node-fg,var(--text-primary,#191A17));"
        top_border_css = f"border-top:3px solid {_C4_ACCENT};"

    stereotype_part = (
        f'<span class="c4-stereotype" style="'
        f'display:block; font-size:10px; font-weight:400; opacity:0.6; '
        f'font-family:var(--label-font,-apple-system,Inter,sans-serif); '
        f'line-height:1.3; margin-bottom:2px;">'
        f'{stereotype_html}</span>'
    )
    label_part = (
        f'<span class="c4-label" style="'
        f'display:block; font-size:14px; font-weight:700; '
        f'font-family:var(--label-font,-apple-system,Inter,sans-serif); '
        f'line-height:1.3;">'
        f'{label_html}</span>'
    )
    tech_html = _h(item.technology) if item.technology else ""
    tech_part = ""
    if tech_html:
        tech_part = (
            f'<span class="c4-technology" style="'
            f'display:block; font-size:10px; font-weight:400; opacity:0.7; '
            f'font-family:var(--label-font,-apple-system,Inter,sans-serif); '
            f'line-height:1.3; margin-top:2px; font-style:italic;">'
            f'[{tech_html}]</span>'
        )
    desc_part = ""
    if desc_html:
        desc_part = (
            f'<span class="c4-description" style="'
            f'display:block; font-size:11px; font-weight:400; opacity:0.75; '
            f'font-family:var(--label-font,-apple-system,Inter,sans-serif); '
            f'line-height:1.3; margin-top:4px;">'
            f'{desc_html}</span>'
        )

    inner = stereotype_part + label_part + tech_part + desc_part

    return (
        f'<div class="node c4-node {_h(kind_css)}" data-node-id="{_h(item.alias)}" style="'
        f'position:absolute; left:{x}px; top:{y}px; '
        f'width:{w}px; height:{h}px; '
        f'padding:10px 12px; '
        f'box-sizing:border-box; overflow:hidden; '
        f'{border_css}{top_border_css}{bg_css}{fg_css}'
        f'border-radius:var(--node-radius,8px); '
        f'box-shadow:var(--node-shadow,0 1px 2px rgba(25,26,23,0.06)); '
        f'display:flex; flex-direction:column; align-items:flex-start; justify-content:center;">'
        f'{inner}</div>'
    )


# ── Edge SVG rendering ────────────────────────────────────────────────────────

def _render_c4_edges(
    relationships: list[C4Relationship],
    box_map: dict[str, C4Box],
    canvas_w: int,
    canvas_h: int,
) -> str:
    """Render C4 relationships as an SVG overlay.

    First relationship: straight line (M … L …).
    Subsequent: quadratic Bézier (M … Q … …).
    """
    _STROKE = "var(--node-fg-dim,var(--text-secondary,#75736C))"
    _LABEL_COLOR = "var(--node-fg,var(--text-primary,#191A17))"
    _MARKER_ID = "c4-arrow"

    parts: list[str] = [
        f'<svg style="position:absolute; inset:0; '
        f'width:{canvas_w}px; height:{canvas_h}px; '
        f'overflow:visible; pointer-events:none;">',
        f'<defs>'
        f'<marker id="{_MARKER_ID}" markerWidth="8" markerHeight="8" '
        f'refX="6" refY="3" orient="auto">'
        f'<path d="M0,0 L0,6 L8,3 z" fill="{_STROKE}"/>'
        f'</marker>'
        f'</defs>',
    ]

    labels: list[str] = []

    for i, rel in enumerate(relationships):
        src_box = box_map.get(rel.src)
        dst_box = box_map.get(rel.dst)
        if src_box is None or dst_box is None:
            continue
        if rel.src == rel.dst:
            continue  # self-relation produces a degenerate zero-length path

        src_cx = src_box.x + src_box.width / 2
        src_cy = src_box.y + src_box.height / 2
        dst_cx = dst_box.x + dst_box.width / 2
        dst_cy = dst_box.y + dst_box.height / 2

        # Edge attachment points (Mermaid 11.15 top-left-slope intersection)
        sx, sy = _mermaid_edge_point(
            src_box.x, src_box.y, src_cx, src_cy,
            src_box.width, src_box.height, dst_cx, dst_cy,
        )
        ex, ey = _mermaid_edge_point(
            dst_box.x, dst_box.y, dst_cx, dst_cy,
            dst_box.width, dst_box.height, src_cx, src_cy,
        )

        if i == 0:
            # First relationship: straight line
            d = f"M {sx:.1f} {sy:.1f} L {ex:.1f} {ey:.1f}"
            lx = (sx + ex) / 2
            ly = (sy + ey) / 2
        else:
            # Subsequent: quadratic Bézier (Mermaid 11.15 control point)
            ctrl_x = sx + (ex - sx) / 4
            ctrl_y = sy + (ey - sy) / 2
            d = f"M {sx:.1f} {sy:.1f} Q {ctrl_x:.1f} {ctrl_y:.1f} {ex:.1f} {ey:.1f}"
            # Midpoint of the curve at t=0.5: P = (1-t)²P0 + 2t(1-t)P1 + t²P2
            lx = 0.25 * sx + 0.5 * ctrl_x + 0.25 * ex
            ly = 0.25 * sy + 0.5 * ctrl_y + 0.25 * ey

        parts.append(
            f'<path d="{d}" stroke="{_STROKE}" stroke-width="1.5" '
            f'fill="none" marker-end="url(#{_MARKER_ID})"/>'
        )

        if rel.label:
            labels.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" '
                f'fill="{_LABEL_COLOR}" '
                f'font-size="11" font-family="var(--label-font,-apple-system,Inter,sans-serif)" '
                f'text-anchor="middle" dominant-baseline="middle">'
                f'{_h(rel.label)}</text>'
            )

    parts.extend(labels)
    parts.append('</svg>')
    return ''.join(parts)


# ── Fragment renderer ─────────────────────────────────────────────────────────

_C4_BOUNDARY_PAD = 24   # padding around boundary members inside boundary box


def _render_c4_boundary_box(bnd: "C4Boundary", member_boxes: list["C4Box"]) -> str:
    """Render a dashed boundary box enclosing the given member boxes."""
    if not member_boxes:
        return ""
    xs = [b.x for b in member_boxes]
    ys = [b.y for b in member_boxes]
    x2s = [b.x + b.width for b in member_boxes]
    y2s = [b.y + b.height for b in member_boxes]
    bx = int(min(xs)) - _C4_BOUNDARY_PAD
    by = int(min(ys)) - _C4_BOUNDARY_PAD - 20  # extra 20px for label
    bw = int(max(x2s)) - int(min(xs)) + 2 * _C4_BOUNDARY_PAD
    bh = int(max(y2s)) - int(min(ys)) + 2 * _C4_BOUNDARY_PAD + 20
    return (
        f'<div class="c4-boundary" data-boundary-id="{_h(bnd.id)}" style="'
        f'position:absolute; left:{bx}px; top:{by}px; '
        f'width:{bw}px; height:{bh}px; '
        f'border:2px dashed var(--node-border,#DAD7CE); '
        f'border-radius:8px; box-sizing:border-box;">'
        f'<span style="'
        f'position:absolute; top:4px; left:10px; '
        f'font-size:11px; font-weight:600; opacity:0.6; '
        f'font-family:var(--label-font,-apple-system,Inter,sans-serif); '
        f'white-space:nowrap;">{_h(bnd.label)}</span>'
        f'</div>'
    )


def _render_c4_fragment(
    title: str,
    items: list[C4Item],
    relationships: list[C4Relationship],
    groups: dict[str, C4Boundary],
    width_hint: int,
) -> str:
    """Render a C4 diagram using Mermaid 11.15 ordered shelf packing.

    Layout always uses C4_LAYOUT_WIDTH (832) for packing — independent of
    width_hint — then scales the rendered canvas to fit width_hint via zoom.

    Boundary-grouped items are packed consecutively so that the boundary
    bounding-box overlay aligns with its member cards.
    """
    if not items:
        raise ValueError("No elements found in C4 diagram.")

    # Separate ungrouped items from boundary-grouped ones; preserve insertion order.
    ungrouped = [it for it in items if not it.boundary]
    # Collect boundary ids in declaration order (preserves groups dict order).
    boundary_ids = list(groups.keys())
    boundary_item_map: dict[str, list[C4Item]] = {
        bid: [it for it in items if it.boundary == bid]
        for bid in boundary_ids
    }

    # Ordered packing sequence: ungrouped first, then each boundary in order.
    packing_order: list[C4Item] = list(ungrouped)
    for bid in boundary_ids:
        packing_order.extend(boundary_item_map.get(bid, []))

    # Box dimensions (Mermaid 11.15 defaults)
    def _item_box(item: C4Item) -> C4Box:
        h = C4_PERSON_H if "person" in item.kind else C4_SYSTEM_H
        return C4Box(alias=item.alias, width=C4_NODE_W, height=h)

    start_y = C4_TITLE_H if title else 0
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

    # Canvas width is pinned to the packing canvas (832 px) so sparse diagrams
    # don't produce a narrow, tightly-cropped render.  Height stays content-tight.
    canvas_w = C4_LAYOUT_WIDTH
    canvas_h = int(math.ceil(bounds.max_bottom + C4_SHAPE_MARGIN))

    # Scale for display (packing is always at layout_width=832)
    zoom = 1.0
    if width_hint and canvas_w > 0 and canvas_w > width_hint:
        zoom = width_hint / canvas_w
    zoom_css = f" zoom:{zoom:.4f};" if abs(zoom - 1.0) > 0.005 else ""

    parts: list[str] = [
        f'<div class="diagram mermaid-layout c4-diagram" style="'
        f'position:relative; width:{canvas_w}px; height:{canvas_h}px;{zoom_css}">'
    ]

    # Title
    if title:
        parts.append(
            f'<div class="c4-title" style="'
            f'position:absolute; left:0; top:0; width:100%; '
            f'height:{C4_TITLE_H}px; '
            f'display:flex; align-items:center; justify-content:center; '
            f'font-size:16px; font-weight:700; '
            f'color:var(--node-fg,var(--text-primary,#191A17)); '
            f'font-family:var(--label-font,-apple-system,Inter,sans-serif);">'
            f'{_h(title)}</div>'
        )

    # Boundary boxes (rendered before nodes so nodes appear on top)
    for bid, bnd in groups.items():
        member_boxes = [box_map[alias] for alias in bnd.members if alias in box_map]
        if member_boxes:
            parts.append(_render_c4_boundary_box(bnd, member_boxes))

    # Nodes (in original insertion order for stable data-node-id ordering)
    for item in packing_order:
        box = box_map.get(item.alias)
        if box:
            parts.append(_render_c4_node(item, box))

    # Relationships (SVG overlay)
    if relationships:
        parts.append(_render_c4_edges(relationships, box_map, canvas_w, canvas_h))

    parts.append('</div>')
    return ''.join(parts)
