"""mermaid_render.layout.architecture — Native architecture-beta scene builder."""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ._geometry import TextLayout

from ..scene import SvgScene


# ── Regex mirrors from _strategies.py ─────────────────────────────────────────

_ARCH_SVC_RE = re.compile(
    r'^service\s+(\w+)\s*(?:\(([^)]*)\))?\s*\[([^\]]+)\](?:\s+in\s+(\w+))?', re.I
)
_ARCH_GRP_RE = re.compile(
    r'^group\s+(\w+)\s*(?:\([^)]*\))?\s*(?:\[([^\]]+)\])?(?:\s+in\s+(\w+))?', re.I
)
_ARCH_JCT_RE = re.compile(r'^junction\s+(\w+)', re.I)
_ARCH_EDGE_RE = re.compile(
    r'^(\w+)(?::([LRTBrlbt]))?'
    r'\s*(<-->|-->|<--|--)\s*'
    r'(?:([LRTBrlbt]):)?(\w+)'
    r'(?::\w+)?'
    r'(?:\s*:\s*(.*))?$'
)


# ── Immutable compiled model ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ArchServiceTile:
    """A parsed + positioned architecture-beta service node."""
    node_id: str
    label: str                       # raw label text
    icon_name: str                   # resolved icon asset name (may be "")
    icon_svg: str                    # loaded SVG string (may be "")
    outer_bounds: object             # Rect from layout coordinates
    label_layout: object             # TextLayout: measured label for the text painter
    icon_bounds: Optional[object]    # Rect: icon area, or None if no icon
    side_ports: tuple                # tuple[PortLayout, ...]: LEFT, RIGHT, TOP, BOTTOM
    group_id: Optional[str]          # parent group id, or None
    accent_color: str                # CSS color for stroke/text


@dataclass(frozen=True)
class ArchJunction:
    """An architecture-beta junction — invisible routing point."""
    node_id: str
    outer_bounds: object             # Rect: layout-assigned bounds (used by router, not rendered)


@dataclass(frozen=True)
class ArchGroupBoundary:
    """An architecture-beta group boundary with label and hierarchy."""
    group_id: str
    parent_group_id: Optional[str]   # set for nested groups
    label: str
    boundary_bounds: object          # Rect
    label_layout: Optional[object]   # TextLayout, or None if no label
    member_ids: tuple                # tuple[str, ...]
    child_group_ids: tuple           # tuple[str, ...]


@dataclass(frozen=True)
class ArchEdge:
    """A routed architecture-beta edge.

    BiRel (<-->) is a single ArchEdge with has_marker_start=True and
    has_marker_end=True — one path, two arrowheads.
    """
    edge_id: str
    src_id: str
    dst_id: str
    label: str
    waypoints: tuple                 # tuple[Point, ...]
    src_port: object                 # PortLayout
    dst_port: object                 # PortLayout
    has_marker_end: bool             # True for --> and <-->
    has_marker_start: bool           # True for <--> only
    label_layout: Optional[object]   # EdgeLabelLayout, or None


@dataclass(frozen=True)
class ArchitectureDiagramLayout:
    """Immutable compiled architecture-beta model — produced by compile_architecture()."""
    services: tuple                  # tuple[ArchServiceTile, ...]
    junctions: tuple                 # tuple[ArchJunction, ...]
    groups: tuple                    # tuple[ArchGroupBoundary, ...]
    edges: tuple                     # tuple[ArchEdge, ...]
    canvas_bounds: object            # Rect
    direction: str
    zoom: float
    backend: str = "python-fallback" # "elk-js" | "python-fallback"


# ── Text layout helper ─────────────────────────────────────────────────────────

def _arch_text_layout(label: str, font_size: float = 15.0, font_weight: int = 700) -> "TextLayout":  # type: ignore[return-value]
    """Single-line TextLayout with bucketed width estimate."""
    from ._geometry import TextLayout, TextLine, TextRun, TextStyle
    from ._constants import _measure_text_width
    line_h = 18.0 if font_size >= 14 else 16.0
    w = float(max(_measure_text_width(label, int(font_size), font_weight), 10.0))
    style = TextStyle(font_size=float(font_size), font_weight=font_weight)
    run = TextRun(text=label, style=style, width=w, height=line_h)
    line = TextLine(runs=(run,), width=w, height=line_h, baseline=line_h - 4.0)
    return TextLayout(
        lines=(line,),
        width=w,
        height=line_h,
        line_height=line_h,
        min_content_width=min(w, 40.0),
        max_content_width=w,
        resolved_font_path=None,
        resolved_font_family="system-ui",
    )


# ── Waypoint extraction (from SVG path string) ─────────────────────────────────

def _extract_waypoints(d: str) -> tuple:
    """Extract Point waypoints from an SVG path d-attribute string."""
    from ._geometry import Point
    pts: list = []
    for cmd, num_str in re.findall(r'([MLQZ])\s*((?:[-\d.]+\s*)*)', d):
        nums = [float(x) for x in num_str.split() if x]
        if cmd in ('M', 'L') and len(nums) >= 2:
            pts.append(Point(nums[0], nums[1]))
        elif cmd == 'Q' and len(nums) >= 4:
            pts.append(Point(nums[2], nums[3]))
    return tuple(pts)


# ── Accent color cycle (mirrors _renderer._ACCENT_CYCLE) ──────────────────────

_ARCH_ACCENT_CYCLE = (
    "var(--accent-1,#60a5fa)",
    "var(--accent-2,#f59e0b)",
    "var(--accent-3,#34d399)",
    "var(--accent-4,#a78bfa)",
)
_ARCH_ACCENT_DEFAULT = "var(--node-title-fg,var(--accent-1,#60a5fa))"


# ── Layout helpers ─────────────────────────────────────────────────────────────

def _build_arch_layout_graph(nodes: dict, groups: dict, edges: list) -> object:
    """Build a LayoutGraph from parsed architecture-beta _Node/_Group/_Edge dicts.

    Collects unique port sides from edge annotations and attaches PortSpec objects
    to each node. Side effect: sets n.width and n.height on non-dummy nodes.
    """
    from ._geometry import LayoutGraph, LayoutNode, LayoutGroup, LayoutEdge, MarkerKind, PortSpec
    from ._constants import NODE_W, _node_render_h
    from ._routing import _node_render_w

    _side_to_elk = {"L": "WEST", "R": "EAST", "T": "NORTH", "B": "SOUTH"}

    # Collect which sides each node is referenced from in edge annotations
    node_sides: dict[str, set] = {nid: set() for nid in nodes}
    for e in edges:
        ss = (getattr(e, "src_side", None) or "").upper()
        ds = (getattr(e, "dst_side", None) or "").upper()
        if ss and e.src in node_sides:
            node_sides[e.src].add(ss)
        if ds and e.dst in node_sides:
            node_sides[e.dst].add(ds)

    layout_nodes = []
    for nid, n in nodes.items():
        if n.is_dummy:
            continue
        nw = _node_render_w(n) or NODE_W
        nh = _node_render_h(n)
        n.width = n.width or nw
        n.height = n.height or nh

        ports = []
        for i, side_char in enumerate(sorted(node_sides.get(nid, set()))):
            elk_side = _side_to_elk.get(side_char)
            if elk_side is None:
                continue
            ports.append(PortSpec(
                id=f"{nid}_{side_char}", node_id=nid, side=elk_side,
                index=i, fixed_side=True, fixed_order=False,
            ))

        layout_nodes.append(LayoutNode(
            id=nid,
            measured_width=float(nw),
            measured_height=float(nh),
            shape_id=n.shape or "rect",
            parent_id=n.group or None,
            ports=ports,
            labels=[n.label or nid],
            semantic_data={},
        ))

    layout_groups = []
    for gid, g in groups.items():
        label = g.label or ""
        layout_groups.append(LayoutGroup(
            id=gid,
            parent_id=getattr(g, "parent_group", None) or None,
            label=label,
            label_width=float(max(80, len(label) * 8)),
            label_height=20.0,
            padding=16.0,
            local_direction=None,
            minimum_width=0.0,
            minimum_height=0.0,
        ))

    seen_ids: dict[str, int] = {}
    layout_edges = []
    for e in edges:
        if getattr(e, "reversed_", False):
            continue
        base_id = f"{e.src}->{e.dst}"
        idx = seen_ids.get(base_id, 0)
        seen_ids[base_id] = idx + 1
        eid = base_id if idx == 0 else f"{base_id}#{idx}"
        ss = (getattr(e, "src_side", None) or "").upper()
        ds = (getattr(e, "dst_side", None) or "").upper()
        bidir = getattr(e, "bidir", False)
        layout_edges.append(LayoutEdge(
            id=eid,
            sources=[e.src],
            targets=[e.dst],
            source_port=f"{e.src}_{ss}" if ss else None,
            target_port=f"{e.dst}_{ds}" if ds else None,
            source_marker=MarkerKind.ARROW if bidir else MarkerKind.NONE,
            target_marker=MarkerKind.ARROW if getattr(e, "arrow", True) else MarkerKind.NONE,
            line_style=e.style or "solid",
            label=e.label or "",
            semantic_data={},
        ))

    return LayoutGraph(nodes=layout_nodes, groups=layout_groups,
                       edges=layout_edges, direction="LR")


def _heuristic_arch_placement(nodes: dict, edges: list, groups: dict) -> tuple:
    """Constraint-propagating 2D grid placement for architecture-beta nodes.

    Uses R→L / L→R edge annotations for column ordering and B→T / T→B for row
    stacking within a column. Resolves (col, row) collisions sequentially.
    Side effect: sets n.x, n.y, n.width, n.height on each non-dummy _Node.
    Returns (canvas_w, canvas_h).
    """
    from ._constants import (
        NODE_W, _node_render_h, CANVAS_PAD, RANK_GAP, COL_GAP,
        GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT,
    )
    from ._routing import _node_render_w

    nids = [nid for nid, n in nodes.items() if not n.is_dummy]

    for nid, n in nodes.items():
        if n.is_dummy:
            continue
        n.width = n.width or (_node_render_w(n) or NODE_W)
        n.height = n.height or _node_render_h(n)

    col: dict[str, int] = {nid: 0 for nid in nids}
    row: dict[str, int] = {nid: 0 for nid in nids}

    # Step 1: column assignment from horizontal port constraints
    for _ in range(20):
        changed = False
        for e in edges:
            src, dst = e.src, e.dst
            if src not in col or dst not in col:
                continue
            ss = (getattr(e, "src_side", None) or "").upper()
            ds = (getattr(e, "dst_side", None) or "").upper()
            if (ss == "R" and ds == "L") or (not ss and not ds):
                if col[dst] <= col[src]:
                    col[dst] = col[src] + 1
                    changed = True
            elif ss == "L" and ds == "R":
                if col[src] <= col[dst]:
                    col[src] = col[dst] + 1
                    changed = True
        if not changed:
            break

    # Step 2: row assignment from vertical port constraints (same column as parent)
    for _ in range(20):
        changed = False
        for e in edges:
            src, dst = e.src, e.dst
            if src not in col or dst not in col:
                continue
            ss = (getattr(e, "src_side", None) or "").upper()
            ds = (getattr(e, "dst_side", None) or "").upper()
            if ss == "B" and ds == "T":
                col[dst] = col[src]
                if row[dst] <= row[src]:
                    row[dst] = row[src] + 1
                    changed = True
            elif ss == "T" and ds == "B":
                col[src] = col[dst]
                if row[src] <= row[dst]:
                    row[src] = row[dst] + 1
                    changed = True
        if not changed:
            break

    # Step 3: resolve (col, row) collisions by bumping to next free row
    occupied: dict[tuple, str] = {}
    for nid in nids:
        c, r = col[nid], row[nid]
        while (c, r) in occupied:
            r += 1
        occupied[(c, r)] = nid
        row[nid] = r

    # Step 4: compute coordinates
    max_row = max(row.values(), default=0)
    row_h: dict[int, int] = {r: 0 for r in range(max_row + 1)}
    for nid in nids:
        row_h[row[nid]] = max(row_h[row[nid]], nodes[nid].height or 48)

    has_group = any(n.group for n in nodes.values() if not n.is_dummy)
    pad_x = CANVAS_PAD + (GROUP_PAD_X if has_group else 0)
    pad_y = CANVAS_PAD + (GROUP_PAD_Y_TOP if has_group else 0)

    for nid in nids:
        c, r = col[nid], row[nid]
        n = nodes[nid]
        n.x = pad_x + c * (NODE_W + RANK_GAP)
        n.y = pad_y + sum(row_h[ri] + COL_GAP for ri in range(r))

    max_x = max((nodes[nid].x + (nodes[nid].width or NODE_W) for nid in nids), default=CANVAS_PAD)
    max_y = max((nodes[nid].y + (nodes[nid].height or 48) for nid in nids), default=CANVAS_PAD)
    canvas_w = max_x + CANVAS_PAD + (GROUP_PAD_X if has_group else 0)
    canvas_h = max_y + CANVAS_PAD + (GROUP_PAD_Y_BOT if has_group else 0)
    return canvas_w, canvas_h


# ── layout helpers ────────────────────────────────────────────────────────────

def _arch_fallback_to_finalized(nodes: dict, edges: list, groups: dict, *,
                                 width_hint: int = 0) -> object:
    """Run heuristic placement + route + finalize; return FinalizedLayout stamped 'python-fallback'.

    Calls _heuristic_arch_placement, _compute_group_bboxes, _route_edges, and
    arch_to_finalized() in sequence, then stamps 'python-fallback' into
    diagnostics.warnings.  Does not raise on internal failure; propagates as-is.
    """
    import dataclasses as _dc
    from ._renderer import _compute_group_bboxes
    from ._routing import _route_edges
    from ._geometry import LayoutDiagnostics, Rect
    from ._constants import NODE_W, _node_render_h, _load_icon, _NODE_PAD_V, _ICON_H
    from ._geometry import Point, PortLayout, PortSide, EdgeLabelLayout, MarkerKind

    canvas_w, canvas_h = _heuristic_arch_placement(nodes, edges, groups)
    zoom = 1.0
    if width_hint and canvas_w > 0 and canvas_w > width_hint:
        zoom = width_hint / canvas_w

    group_bboxes = _compute_group_bboxes(nodes, groups, canvas_w, canvas_h) if groups else {}
    routes = _route_edges(nodes, edges, canvas_w, "LR", group_bboxes or None)

    node_grp_idx: dict = {}
    for gi, gid in enumerate(groups):
        for nid in groups[gid].members:
            node_grp_idx[nid] = gi

    group_children: dict = {gid: [] for gid in groups}
    for gid, grp in groups.items():
        parent = getattr(grp, "parent_group", None)
        if parent and parent in group_children:
            group_children[parent].append(gid)

    services: list = []
    junctions: list = []
    for nid, n in sorted(nodes.items()):
        nw = n.width or NODE_W
        nh = _node_render_h(n)
        outer = Rect(x=float(n.x), y=float(n.y), w=float(nw), h=float(nh))
        if n.is_dummy:
            junctions.append(ArchJunction(node_id=nid, outer_bounds=outer))
            continue
        icon_svg = _load_icon(n.icon) if n.icon else ""
        has_icon = bool(icon_svg)
        icon_bounds = (
            Rect(x=float(n.x + _NODE_PAD_V), y=float(n.y + _NODE_PAD_V),
                 w=float(_ICON_H), h=float(_ICON_H))
            if has_icon else None
        )
        label_layout = _arch_text_layout(n.label, font_size=15.0, font_weight=700)
        cx = float(n.x + nw / 2)
        cy = float(n.y + nh / 2)
        side_ports = (
            PortLayout(node_id=nid, side=PortSide.LEFT,
                       position=Point(float(n.x), cy), direction=Point(-1.0, 0.0)),
            PortLayout(node_id=nid, side=PortSide.RIGHT,
                       position=Point(float(n.x + nw), cy), direction=Point(1.0, 0.0)),
            PortLayout(node_id=nid, side=PortSide.TOP,
                       position=Point(cx, float(n.y)), direction=Point(0.0, -1.0)),
            PortLayout(node_id=nid, side=PortSide.BOTTOM,
                       position=Point(cx, float(n.y + nh)), direction=Point(0.0, 1.0)),
        )
        gi_idx = node_grp_idx.get(nid)  # type: ignore[assignment]
        accent = (
            _ARCH_ACCENT_CYCLE[gi_idx % len(_ARCH_ACCENT_CYCLE)]
            if gi_idx is not None else _ARCH_ACCENT_DEFAULT
        )
        services.append(ArchServiceTile(
            node_id=nid, label=n.label, icon_name=n.icon or "", icon_svg=icon_svg,
            outer_bounds=outer, label_layout=label_layout, icon_bounds=icon_bounds,
            side_ports=side_ports, group_id=n.group, accent_color=accent,
        ))

    arch_groups: list = []
    for gid, grp in groups.items():
        if gid not in group_bboxes:
            continue
        bx1, by1, bx2, by2 = group_bboxes[gid]
        boundary_bounds = Rect(x=float(bx1), y=float(by1),
                               w=float(bx2 - bx1), h=float(by2 - by1))
        lbl = grp.label or ""
        lbl_layout = _arch_text_layout(lbl, font_size=12.0, font_weight=600) if lbl else None  # type: ignore[assignment]
        arch_groups.append(ArchGroupBoundary(
            group_id=gid, parent_group_id=getattr(grp, "parent_group", None),
            label=lbl, boundary_bounds=boundary_bounds, label_layout=lbl_layout,
            member_ids=tuple(grp.members), child_group_ids=tuple(group_children.get(gid, [])),
        ))

    arch_edges: list = []
    seen_pairs: dict = {}
    for spec in routes:
        src = spec.get("src", "")
        dst = spec.get("dst", "")
        pair = (src, dst)
        idx = seen_pairs.get(pair, 0)
        seen_pairs[pair] = idx + 1
        edge_id = f"{src}->{dst}" if idx == 0 else f"{src}->{dst}#{idx}"
        waypoints = _extract_waypoints(spec.get("d", ""))
        if len(waypoints) < 2:
            continue
        src_pos, dst_pos = waypoints[0], waypoints[-1]
        src_port = PortLayout(node_id=src, side=PortSide.AUTO,
                              position=src_pos, direction=Point(0.0, 1.0))
        dst_port = PortLayout(node_id=dst, side=PortSide.AUTO,
                              position=dst_pos, direction=Point(0.0, -1.0))
        mid = spec.get("marker_id") or ""
        has_marker_end = bool(mid) and not mid.endswith("-rev")
        has_marker_start = bool(spec.get("bidir")) or (bool(mid) and mid.endswith("-rev"))
        label_text = spec.get("label", "") or ""
        edge_label = None
        if label_text:
            lx, ly = float(spec.get("lx", 0)), float(spec.get("ly", 0))
            tl = _arch_text_layout(label_text, font_size=12.0, font_weight=400)
            edge_label = EdgeLabelLayout(
                text=label_text, layout=tl,
                bounds=Rect(x=lx, y=ly, w=tl.width, h=tl.height),
                anchor_point=src_pos,
            )
        arch_edges.append(ArchEdge(
            edge_id=edge_id, src_id=src, dst_id=dst, label=label_text,
            waypoints=waypoints, src_port=src_port, dst_port=dst_port,
            has_marker_end=has_marker_end, has_marker_start=has_marker_start,
            label_layout=edge_label,
        ))

    canvas_bounds = Rect(x=0.0, y=0.0, w=float(canvas_w), h=float(canvas_h))
    arch = ArchitectureDiagramLayout(
        services=tuple(services), junctions=tuple(junctions),
        groups=tuple(arch_groups), edges=tuple(arch_edges),
        canvas_bounds=canvas_bounds, direction="LR", zoom=zoom,
        backend="python-fallback",
    )
    fl = arch_to_finalized(arch)
    # arch_to_finalized already stamps arch.backend; return as-is
    return fl


def _arch_elk_to_finalized(elk_fl: object, nodes: dict, groups: dict, *,
                            width_hint: int = 0) -> object:
    """Enrich an ELK FinalizedLayout with architecture-beta metadata (icons, labels, accent colors).

    Takes the raw FinalizedLayout returned by layout_with_elk() and merges
    icon_svg, label_layout, accent_color, and side_ports from the original
    parsed nodes dict.  Merges label_layout and child_group_ids from the
    original groups dict.  Stamps 'elk-js' into diagnostics.warnings.

    routed_edges, canvas_bounds, and visible_bounds are passed through unchanged
    from elk_fl — ELK is authoritative for geometry.
    """
    import dataclasses as _dc
    from ._geometry import (
        FinalizedLayout, LayoutDiagnostics, NodeLayout, GroupLayout, RoutedEdge,
        Rect, Point, PortLayout, PortSide,
    )
    from ._constants import NODE_W, _node_render_h, _load_icon, _NODE_PAD_V, _ICON_H
    import types as _types

    _fl: FinalizedLayout = elk_fl  # type: ignore[assignment]

    node_grp_idx: dict = {}
    for gi, gid in enumerate(groups):
        for nid in getattr(groups[gid], "members", []):
            node_grp_idx[nid] = gi

    group_children: dict = {gid: [] for gid in groups}
    for gid, grp in groups.items():
        parent = getattr(grp, "parent_group", None)
        if parent and parent in group_children:
            group_children[parent].append(gid)

    new_node_layouts: dict = {}
    for nid, nl in _fl.node_layouts.items():
        n = nodes.get(nid)
        if n is None:
            new_node_layouts[nid] = nl
            continue
        icon_svg = _load_icon(n.icon) if (n.icon and not n.is_dummy) else ""
        has_icon = bool(icon_svg)
        b = nl.outer_bounds
        icon_bounds = (
            Rect(x=b.x + float(_NODE_PAD_V), y=b.y + float(_NODE_PAD_V),
                 w=float(_ICON_H), h=float(_ICON_H))
            if has_icon else None
        )
        label_layout = (
            _arch_text_layout(n.label, font_size=15.0, font_weight=700)
            if not n.is_dummy else None
        )
        nw = b.w
        nh = b.h
        cx = b.x + nw / 2
        cy = b.y + nh / 2
        side_ports = (
            PortLayout(node_id=nid, side=PortSide.LEFT,
                       position=Point(b.x, cy), direction=Point(-1.0, 0.0)),
            PortLayout(node_id=nid, side=PortSide.RIGHT,
                       position=Point(b.x + nw, cy), direction=Point(1.0, 0.0)),
            PortLayout(node_id=nid, side=PortSide.TOP,
                       position=Point(cx, b.y), direction=Point(0.0, -1.0)),
            PortLayout(node_id=nid, side=PortSide.BOTTOM,
                       position=Point(cx, b.y + nh), direction=Point(0.0, 1.0)),
        )
        # Prefer ELK's port sides from the existing RoutedEdge src/dst ports;
        # side_ports here are face-centred fallbacks used by the painter.
        gi_idx = node_grp_idx.get(nid)  # type: ignore[assignment]
        accent = (
            _ARCH_ACCENT_CYCLE[gi_idx % len(_ARCH_ACCENT_CYCLE)]
            if gi_idx is not None else _ARCH_ACCENT_DEFAULT
        )
        new_node_layouts[nid] = _dc.replace(
            nl,
            title_layout=label_layout,  # type: ignore[arg-type]
            icon_bounds=icon_bounds,
            ports=side_ports,  # type: ignore[arg-type]
            icon_svg=icon_svg,
            accent_color=accent,
            parent_group_id=n.group,
        )

    new_group_layouts: dict = {}
    for gid, gl in _fl.group_layouts.items():
        grp = groups.get(gid)
        if grp is None:
            new_group_layouts[gid] = gl
            continue
        lbl = grp.label or ""
        lbl_layout = _arch_text_layout(lbl, font_size=12.0, font_weight=600) if lbl else None  # type: ignore[assignment]
        child_ids = tuple(group_children.get(gid, []))
        new_group_layouts[gid] = _dc.replace(
            gl,
            label_layout=lbl_layout,  # type: ignore[arg-type]
            child_group_ids=child_ids,  # type: ignore[arg-type]
        )

    diag = _fl.diagnostics
    enriched_diag = LayoutDiagnostics(
        unsupported_options=diag.unsupported_options,
        route_failures=diag.route_failures,
        warnings=diag.warnings + ("elk-js",),
    )
    return FinalizedLayout(
        node_layouts=_types.MappingProxyType(new_node_layouts),
        group_layouts=_types.MappingProxyType(new_group_layouts),
        routed_edges=_fl.routed_edges,
        visible_bounds=_fl.visible_bounds,
        diagram_padding=_fl.diagram_padding,
        canvas_bounds=_fl.canvas_bounds,
        direction=_fl.direction,
        diagnostics=enriched_diag,
        routing_failures=_fl.routing_failures,
    )


def _elk_routes_to_specs(elk_fl: object, parsed_edges: list) -> list:
    """Convert ELK routed_edges to the route-spec dicts expected by the edge-builder loop.

    Produces one dict per routed edge with keys: src, dst, d (waypoints path string),
    marker_id, bidir, label, lx, ly.
    """
    from ._geometry import FinalizedLayout, MarkerKind
    _fl: FinalizedLayout = elk_fl  # type: ignore[assignment]

    # Build label lookup from parsed edges (src, dst) → label
    label_by_pair: dict = {}
    for e in parsed_edges:
        if not getattr(e, "reversed_", False):
            label_by_pair[(e.src, e.dst)] = e.label or ""

    specs = []
    for re in _fl.routed_edges:
        src = re.src_node_id
        dst = re.dst_node_id
        # Build SVG-ish path string from waypoints
        wps = re.waypoints
        if len(wps) < 2:
            continue
        parts = [f"M {wps[0].x:.1f} {wps[0].y:.1f}"]
        for wp in wps[1:]:
            parts.append(f"L {wp.x:.1f} {wp.y:.1f}")
        d = " ".join(parts)
        # Derive marker flags from RoutedEdge
        from ._constants import _marker_kind
        t_kind = _marker_kind(re.target_marker)
        s_kind = _marker_kind(re.source_marker)
        has_end = t_kind not in (MarkerKind.NONE,)
        has_start = s_kind not in (MarkerKind.NONE,)
        marker_id = "arrow" if has_end else ""
        bidir = has_start
        label = label_by_pair.get((src, dst), "")
        lx = ly = 0.0
        if re.label_layout is not None:
            lx = re.label_layout.bounds.x
            ly = re.label_layout.bounds.y
        specs.append({
            "src": src, "dst": dst, "d": d,
            "marker_id": marker_id, "bidir": bidir,
            "label": label, "lx": lx, "ly": ly,
        })
    return specs


# ── compile_architecture ───────────────────────────────────────────────────────

def compile_architecture(src: str, *, width_hint: int = 0) -> ArchitectureDiagramLayout:
    """Parse + layout architecture-beta source into an immutable ArchitectureDiagramLayout."""
    from ._constants import (
        _Node, _Group, _Edge, NODE_CAP, _ARCH_ICON_MAP,
        NODE_W, _node_render_h, _load_icon, _NODE_PAD_V, _ICON_H,
    )
    from ._renderer import _compute_group_bboxes
    from ._routing import _route_edges
    from ._geometry import Rect, Point, PortLayout, PortSide, EdgeLabelLayout, MarkerKind, MarkerSpec

    # ── Parse ──────────────────────────────────────────────────────────────────
    lines = src.splitlines()
    content_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith(("%%", "//")):
            content_start = i + 1
            break

    nodes: dict = {}
    groups: dict = {}
    edges: list = []
    grp_stack: list = []

    for raw in lines[content_start:]:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        indent = len(raw) - len(raw.lstrip())

        while grp_stack and grp_stack[-1][0] >= indent:
            grp_stack.pop()

        m = _ARCH_SVC_RE.match(line)
        if m:
            sid = m.group(1)
            icon_hint = (m.group(2) or "").lower().strip()
            lbl = m.group(3)
            gin = m.group(4)
            if not gin and grp_stack:
                gin = grp_stack[-1][1]
            icon_name = _ARCH_ICON_MAP.get(icon_hint) or icon_hint or ""
            nodes[sid] = _Node(id=sid, label=lbl, shape="rect",
                               group=gin if gin else None, icon=icon_name)
            if gin:
                groups.setdefault(gin, _Group(id=gin, label=gin, members=[]))
                if sid not in groups[gin].members:
                    groups[gin].members.append(sid)
            continue

        m = _ARCH_JCT_RE.match(line)
        if m:
            jid = m.group(1)
            nodes[jid] = _Node(id=jid, label="", shape="rect", is_dummy=True)
            continue

        m = _ARCH_GRP_RE.match(line)
        if m:
            gid = m.group(1)
            glbl = m.group(2) or m.group(1)
            gin_grp = m.group(3)
            if gid not in groups:
                grp = _Group(id=gid, label=glbl, members=[])
                if gin_grp:
                    grp.parent_group = gin_grp
                groups[gid] = grp
            else:
                groups[gid].label = glbl
                if gin_grp:
                    groups[gid].parent_group = gin_grp
            grp_stack.append((indent, gid))
            continue

        m = _ARCH_EDGE_RE.match(line)
        if m:
            src_id = m.group(1)
            src_side = (m.group(2) or "").upper() or None
            op = m.group(3)
            dst_side = (m.group(4) or "").upper() or None
            dst_id = m.group(5)
            lbl = (m.group(6) or "").strip()
            _arrow_src = MarkerSpec(kind=MarkerKind.ARROW, end="SOURCE")
            _arrow_tgt = MarkerSpec(kind=MarkerKind.ARROW, end="TARGET")
            _none_tgt = MarkerSpec(kind=MarkerKind.NONE, end="TARGET")
            if op == "<-->":
                # BiRel: one edge with bidir (arrowheads on both ends) — one path
                edges.append(_Edge(src=src_id, dst=dst_id, label=lbl,
                                   style="solid", source_marker=_arrow_src, target_marker=_arrow_tgt,
                                   src_side=src_side, dst_side=dst_side))
            elif op == "<--":
                edges.append(_Edge(src=dst_id, dst=src_id, label=lbl,
                                   style="solid", target_marker=_arrow_tgt,
                                   src_side=dst_side, dst_side=src_side))
            else:
                edges.append(_Edge(src=src_id, dst=dst_id, label=lbl,
                                   style="solid",
                                   target_marker=(_arrow_tgt if op == "-->" else _none_tgt),
                                   src_side=src_side, dst_side=dst_side))

    if not nodes:
        raise ValueError("No services found in architecture-beta.")

    if len(nodes) > NODE_CAP:
        raise ValueError(f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}).")

    # ── Layout ─────────────────────────────────────────────────────────────────
    _elk_fl = None
    _backend = "python-fallback"
    try:
        from .elk_adapter import layout_with_elk as _layout_with_elk, ElkUnavailable
        _lg = _build_arch_layout_graph(nodes, groups, edges)
        _raw_fl, _elk_meta = _layout_with_elk(_lg)  # type: ignore[arg-type]
        _expected_nids = {n.id for n in _lg.nodes}  # type: ignore[attr-defined]
        _missing = _expected_nids - set(_raw_fl.node_layouts.keys())
        if _missing:
            raise ValueError(
                f"ELK returned incomplete layout: missing nodes {_missing}"
            )
        _elk_fl = _raw_fl
        _backend = "elk-js"
    except ElkUnavailable:
        pass  # fall through to fallback
    except ValueError:
        raise  # incomplete result — propagate as-is
    except Exception as _exc:
        from ..errors import ArchitectureLayoutError
        raise ArchitectureLayoutError("layout", cause=_exc) from _exc

    if _elk_fl is not None:
        # ELK path: use ELK geometry — no _compute_group_bboxes / _route_edges
        for _nid, _nl in _elk_fl.node_layouts.items():
            if _nid in nodes:
                _n = nodes[_nid]
                _n.x = float(_nl.outer_bounds.x)
                _n.y = float(_nl.outer_bounds.y)
                _n.width = _n.width or float(_nl.outer_bounds.w)
                _n.height = _n.height or float(_nl.outer_bounds.h)
        canvas_w = _elk_fl.canvas_bounds.w
        canvas_h = _elk_fl.canvas_bounds.h
        group_bboxes: dict = {}
        for _gid, _gl in _elk_fl.group_layouts.items():
            _bb = _gl.boundary_bounds
            group_bboxes[_gid] = (_bb.x, _bb.y, _bb.x + _bb.w, _bb.y + _bb.h)
        routes: list = _elk_routes_to_specs(_elk_fl, edges)  # type: ignore[assignment]
    else:
        # Fallback path: heuristic placement + Python router
        canvas_w, canvas_h = _heuristic_arch_placement(nodes, edges, groups)
        group_bboxes = _compute_group_bboxes(nodes, groups, canvas_w, canvas_h) if groups else {}
        routes = _route_edges(nodes, edges, canvas_w, "LR", group_bboxes or None)  # type: ignore[assignment]

    zoom = 1.0
    if width_hint and canvas_w > 0 and canvas_w > width_hint:
        zoom = width_hint / canvas_w

    # ── Build group → index map for accent colors ──────────────────────────────
    node_grp_idx: dict = {}
    for gi, gid in enumerate(groups):
        for nid in groups[gid].members:
            node_grp_idx[nid] = gi

    # ── Build child_group_ids map ──────────────────────────────────────────────
    group_children: dict = {gid: [] for gid in groups}
    for gid, grp in groups.items():
        parent = getattr(grp, "parent_group", None)
        if parent and parent in group_children:
            group_children[parent].append(gid)

    # ── Service tiles and junctions ────────────────────────────────────────────
    services: list = []
    junctions: list = []

    for nid, n in sorted(nodes.items()):
        nw = n.width or NODE_W
        nh = _node_render_h(n)
        outer = Rect(x=float(n.x), y=float(n.y), w=float(nw), h=float(nh))

        if n.is_dummy:
            junctions.append(ArchJunction(node_id=nid, outer_bounds=outer))
            continue

        icon_svg = _load_icon(n.icon) if n.icon else ""
        has_icon = bool(icon_svg)
        icon_bounds = (
            Rect(
                x=float(n.x + _NODE_PAD_V),
                y=float(n.y + _NODE_PAD_V),
                w=float(_ICON_H),
                h=float(_ICON_H),
            )
            if has_icon else None
        )

        label_layout = _arch_text_layout(n.label, font_size=15.0, font_weight=700)

        # Side ports: L / R / T / B face centers
        cx = float(n.x + nw / 2)
        cy = float(n.y + nh / 2)
        side_ports = (
            PortLayout(node_id=nid, side=PortSide.LEFT,
                       position=Point(float(n.x), cy),
                       direction=Point(-1.0, 0.0)),
            PortLayout(node_id=nid, side=PortSide.RIGHT,
                       position=Point(float(n.x + nw), cy),
                       direction=Point(1.0, 0.0)),
            PortLayout(node_id=nid, side=PortSide.TOP,
                       position=Point(cx, float(n.y)),
                       direction=Point(0.0, -1.0)),
            PortLayout(node_id=nid, side=PortSide.BOTTOM,
                       position=Point(cx, float(n.y + nh)),
                       direction=Point(0.0, 1.0)),
        )

        gi = node_grp_idx.get(nid)  # type: ignore[assignment]
        accent = (
            _ARCH_ACCENT_CYCLE[gi % len(_ARCH_ACCENT_CYCLE)]
            if gi is not None else _ARCH_ACCENT_DEFAULT
        )

        services.append(ArchServiceTile(
            node_id=nid,
            label=n.label,
            icon_name=n.icon or "",
            icon_svg=icon_svg,
            outer_bounds=outer,
            label_layout=label_layout,
            icon_bounds=icon_bounds,
            side_ports=side_ports,
            group_id=n.group,
            accent_color=accent,
        ))

    # ── Group boundaries ───────────────────────────────────────────────────────
    arch_groups: list = []
    for gid, grp in groups.items():
        if gid not in group_bboxes:
            continue
        bx1, by1, bx2, by2 = group_bboxes[gid]
        boundary_bounds = Rect(
            x=float(bx1), y=float(by1),
            w=float(bx2 - bx1), h=float(by2 - by1),
        )
        lbl = grp.label or ""
        label_layout = _arch_text_layout(lbl, font_size=12.0, font_weight=600) if lbl else None  # type: ignore[assignment]
        arch_groups.append(ArchGroupBoundary(
            group_id=gid,
            parent_group_id=getattr(grp, "parent_group", None),
            label=lbl,
            boundary_bounds=boundary_bounds,
            label_layout=label_layout,
            member_ids=tuple(grp.members),
            child_group_ids=tuple(group_children.get(gid, [])),
        ))

    # ── Edges ──────────────────────────────────────────────────────────────────
    arch_edges: list = []
    seen_pairs: dict = {}

    for spec in routes:
        src = spec.get("src", "")
        dst = spec.get("dst", "")
        pair = (src, dst)
        idx = seen_pairs.get(pair, 0)
        seen_pairs[pair] = idx + 1
        edge_id = f"{src}->{dst}" if idx == 0 else f"{src}->{dst}#{idx}"

        waypoints = _extract_waypoints(spec.get("d", ""))
        if len(waypoints) < 2:
            continue  # unroutable edge — skip rather than emit a zero-length path
        src_pos = waypoints[0]
        dst_pos = waypoints[-1]

        src_port = PortLayout(node_id=src, side=PortSide.AUTO,
                              position=src_pos, direction=Point(0.0, 1.0))
        dst_port = PortLayout(node_id=dst, side=PortSide.AUTO,
                              position=dst_pos, direction=Point(0.0, -1.0))

        mid = spec.get("marker_id") or ""
        has_marker_end = bool(mid) and not mid.endswith("-rev")
        has_marker_start = bool(spec.get("bidir")) or (bool(mid) and mid.endswith("-rev"))

        label_text = spec.get("label", "") or ""
        edge_label = None
        if label_text:
            lx, ly = float(spec.get("lx", 0)), float(spec.get("ly", 0))
            tl = _arch_text_layout(label_text, font_size=12.0, font_weight=400)
            edge_label = EdgeLabelLayout(
                text=label_text,
                layout=tl,
                bounds=Rect(x=lx, y=ly, w=tl.width, h=tl.height),
                anchor_point=src_pos,
            )

        arch_edges.append(ArchEdge(
            edge_id=edge_id,
            src_id=src,
            dst_id=dst,
            label=label_text,
            waypoints=waypoints,
            src_port=src_port,
            dst_port=dst_port,
            has_marker_end=has_marker_end,
            has_marker_start=has_marker_start,
            label_layout=edge_label,
        ))

    canvas_bounds = Rect(x=0.0, y=0.0, w=float(canvas_w), h=float(canvas_h))
    return ArchitectureDiagramLayout(
        services=tuple(services),
        junctions=tuple(junctions),
        groups=tuple(arch_groups),
        edges=tuple(arch_edges),
        canvas_bounds=canvas_bounds,
        direction="LR",
        zoom=zoom,
        backend=_backend,
    )


# ── arch_to_finalized ──────────────────────────────────────────────────────────

def arch_to_finalized(arch: ArchitectureDiagramLayout) -> object:
    """Lower ArchitectureDiagramLayout to a FinalizedLayout for painting."""
    from ._geometry import (
        FinalizedLayout, LayoutDiagnostics, NodeLayout, GroupLayout, RoutedEdge, Rect,
        _empty_diagnostics, MarkerKind,
    )

    node_layouts: dict = {}

    for svc in arch.services:
        b = svc.outer_bounds
        node_layouts[svc.node_id] = NodeLayout(
            node_id=svc.node_id,
            semantic_shape="arch-service",
            outer_bounds=b,
            content_bounds=Rect(
                x=b.x + 8.0, y=b.y + 4.0,
                w=float(max(b.w - 16.0, 20.0)),
                h=float(max(b.h - 8.0, 10.0)),
            ),
            title_layout=svc.label_layout,
            subtitle_layout=None,
            member_layouts=(),
            icon_bounds=svc.icon_bounds,
            ports=svc.side_ports,
            css_classes=("node-arch-service",),
            extra_css="",
            is_dummy=False,
            rank=0,
            is_external=False,
            icon_svg=svc.icon_svg,
            accent_color=svc.accent_color,
            parent_group_id=svc.group_id,
        )

    for jct in arch.junctions:
        b = jct.outer_bounds
        node_layouts[jct.node_id] = NodeLayout(
            node_id=jct.node_id,
            semantic_shape="arch-junction",
            outer_bounds=b,
            content_bounds=b,
            title_layout=None,
            subtitle_layout=None,
            member_layouts=(),
            icon_bounds=None,
            ports=(),
            css_classes=("node-arch-junction",),
            extra_css="",
            is_dummy=True,
            rank=0,
            is_external=False,
            icon_svg="",
            accent_color="",
            parent_group_id=None,
        )

    group_layouts: dict = {}
    for grp in arch.groups:
        group_layouts[grp.group_id] = GroupLayout(
            group_id=grp.group_id,
            parent_group_id=grp.parent_group_id,
            boundary_bounds=grp.boundary_bounds,
            label_layout=grp.label_layout,
            member_ids=grp.member_ids,
            child_group_ids=grp.child_group_ids,
            local_direction="LR",
        )

    routed_edges = tuple(
        RoutedEdge(
            edge_id=e.edge_id,
            src_node_id=e.src_id,
            dst_node_id=e.dst_id,
            src_port=e.src_port,
            dst_port=e.dst_port,
            waypoints=e.waypoints,
            edge_style="solid",
            has_marker_end=e.has_marker_end,
            has_marker_start=e.has_marker_start,
            label_layout=e.label_layout,
            src_label_layout=None,
            dst_label_layout=None,
            source_marker=MarkerKind.ARROW if e.has_marker_start else MarkerKind.NONE,
            target_marker=MarkerKind.ARROW if e.has_marker_end else MarkerKind.NONE,
        )
        for e in arch.edges
    )

    import types as _types
    diag = _empty_diagnostics()
    if arch.backend:
        diag = LayoutDiagnostics(
            unsupported_options=diag.unsupported_options,
            route_failures=diag.route_failures,
            warnings=diag.warnings + (arch.backend,),
        )
    return FinalizedLayout(
        node_layouts=_types.MappingProxyType(node_layouts),
        group_layouts=_types.MappingProxyType(group_layouts),
        routed_edges=routed_edges,
        visible_bounds=arch.canvas_bounds,  # type: ignore[arg-type]
        diagram_padding=48.0,
        canvas_bounds=arch.canvas_bounds,  # type: ignore[arg-type]
        direction=arch.direction,
        diagnostics=diag,
    )


# ── HTML renderer ─────────────────────────────────────────────────────────────

def arch_to_html(src: str, *, width_hint: int = 0) -> str:
    """Render architecture-beta source as a self-contained HTML div string."""
    from ._renderer import render_finalized

    arch = compile_architecture(src, width_hint=width_hint)
    finalized = arch_to_finalized(arch)
    html = render_finalized(finalized)
    if abs(arch.zoom - 1.0) > 0.005:
        html = (
            f'<div class="diagram-zoom-wrapper"'
            f' style="display:contents; zoom:{arch.zoom:.4f};">'
            f"{html}</div>"
        )
    return html


# ── Public entry point ─────────────────────────────────────────────────────────

def layout_architecture_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse architecture-beta source and return an SvgScene."""
    from ._renderer import _extract_diagram_title
    from ..paint import finalized_layout_to_scene

    arch = compile_architecture(src, width_hint=width_hint)
    finalized = arch_to_finalized(arch)
    title = _extract_diagram_title(src)

    scene = finalized_layout_to_scene(
        finalized,
        diagram_type="architecture-beta",
        title=title,
    )

    # Apply zoom: scale physical width/height while keeping coordinate viewBox intact.
    if arch.zoom != 1.0:
        scene = dataclasses.replace(
            scene,
            width=scene.view_box[2] * arch.zoom,
            height=scene.view_box[3] * arch.zoom,
        )

    return scene
