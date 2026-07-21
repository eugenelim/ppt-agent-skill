"""mermaid_render.layout.architecture — Native architecture-beta scene builder.

Runs the same parsing and graph topology layout as _layout_architecture()
in _strategies.py, then calls graph_to_scene() for native SVG output.
"""
from __future__ import annotations

import re

from ..scene import SvgScene
from ..paint import graph_to_scene


# ── Mirrors _ARCH_*_RE from _strategies.py ───────────────────────────────────

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


def layout_architecture_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse architecture-beta source and return an SvgScene."""
    from ._constants import _Node, _Group, NODE_CAP, _ARCH_ICON_MAP
    from ._constants import _Edge
    from ._layout import (
        _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates,
    )
    from ._renderer import _extract_diagram_title

    lines = src.splitlines()
    content_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith(("%%", "//")):
            content_start = i + 1
            break

    nodes: dict[str, _Node] = {}
    groups: dict[str, _Group] = {}
    edges: list = []
    grp_stack: list[tuple[int, str]] = []

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
            from ._constants import _Edge as _E
            src_id = m.group(1)
            src_side = (m.group(2) or "").upper() or None
            op = m.group(3)
            dst_side = (m.group(4) or "").upper() or None
            dst_id = m.group(5)
            lbl = (m.group(6) or "").strip()
            if op == "<-->":
                edges.append(_E(src=src_id, dst=dst_id, label=lbl,
                                style="solid", arrow=True,
                                src_side=src_side, dst_side=dst_side))
                edges.append(_E(src=dst_id, dst=src_id, label="",
                                style="solid", arrow=True,
                                src_side=dst_side, dst_side=src_side))
            elif op == "<--":
                edges.append(_E(src=dst_id, dst=src_id, label=lbl,
                                style="solid", arrow=True,
                                src_side=dst_side, dst_side=src_side))
            else:
                edges.append(_E(src=src_id, dst=dst_id, label=lbl,
                                style="solid", arrow=(op == "-->"),
                                src_side=src_side, dst_side=dst_side))

    if not nodes:
        raise ValueError("No services found in architecture-beta.")

    if len(nodes) > NODE_CAP:
        raise ValueError(
            f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP})."
        )

    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)
    canvas_w, canvas_h = _assign_coordinates(nodes, "LR")

    zoom = 1.0
    if width_hint and canvas_w > 0 and canvas_w > width_hint:
        zoom = width_hint / canvas_w

    from ._routing import _route_edges
    from ._renderer import _compute_group_bboxes
    group_bboxes = _compute_group_bboxes(nodes, groups, canvas_w, canvas_h) if groups else {}
    routes = _route_edges(nodes, edges, canvas_w, "LR", group_bboxes)
    title = _extract_diagram_title(src)

    return graph_to_scene(
        nodes=nodes,
        edges=edges,
        groups=groups,
        routes=routes,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        diagram_type="architecture-beta",
        direction="LR",
        group_bboxes=group_bboxes or None,
        title=title,
        zoom=zoom,
    )
