#!/usr/bin/env python3
"""mermaid_layout.py — deterministic Mermaid-to-HTML/CSS layout engine.

Consumes Mermaid diagram source; emits a self-contained HTML/CSS fragment with
deterministically positioned nodes and SVG edge paths, themed via CSS variables
from the blocks/diagram.md contract. No dagre, no Mermaid.js, no new pip dependency.

Exit 0: HTML fragment written to stdout or --output file.
Exit 1: parse error, cap exceeded, or unsupported directive.

CLI:
    python3 scripts/mermaid_layout.py --source 'flowchart TB\\n  A-->B'
    python3 scripts/mermaid_layout.py --source @file.mmd [--direction LR] \\
        [--width-hint 960] [--output fragment.html]
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass, field
from html import escape as _h
from pathlib import Path
from typing import Optional

# ── icon loader ───────────────────────────────────────────────────────────────

_ICON_DIR = Path(__file__).parent.parent / "assets" / "icons"
_icon_cache: dict[str, str] = {}


def _load_icon(name: str) -> str:
    """Return inline SVG string for icon name, or '' if not found."""
    if name in _icon_cache:
        return _icon_cache[name]
    p = _ICON_DIR / f"{name}.svg"
    if not p.exists():
        _icon_cache[name] = ""
        return ""
    svg = p.read_text(encoding="utf-8").strip()
    # Normalize: remove XML declaration; set width/height="100%" on the <svg> tag
    svg = re.sub(r'<\?xml[^?]*\?>', '', svg).strip()
    # Strip any existing width/height from the opening <svg> tag, then add 100%
    svg = re.sub(r'(<svg\b[^>]*?)\s+width="[^"]*"', r'\1', svg, count=1)
    svg = re.sub(r'(<svg\b[^>]*?)\s+height="[^"]*"', r'\1', svg, count=1)
    svg = svg.replace('<svg ', '<svg width="100%" height="100%" ', 1)
    _icon_cache[name] = svg
    return svg


# Architecture-beta icon hint → asset name
_ARCH_ICON_MAP: dict[str, str] = {
    "server": "node",
    "database": "database",
    "db": "database",
    "cloud": "cloud",
    "internet": "cloud",
    "disk": "database",
    "api": "api",
    "gateway": "connector",
    "queue": "pipeline",
    "worker": "agent",
    "agent": "agent",
    "user": "users",
    "users": "users",
    "client": "users",
    "terminal": "terminal",
    "model": "model",
    "vector": "vector-store",
}

# C4 element type → asset name
_C4_ICON_MAP: dict[str, str] = {
    "person": "users",
    "person_ext": "users",
    "systemdb": "database",
    "containerdb": "database",
    "system": "node",
    "system_ext": "node",
    "container": "connector",
    "container_ext": "connector",
    "component": "bolt",
}


# ── caps ──────────────────────────────────────────────────────────────────────
NODE_CAP = 64
EDGE_CAP = 128
GROUP_CAP = 16
CROSSING_PASSES = 8  # 4 forward + 4 backward barycenter passes

# ── default geometry (px) — matches Appendix §A in spec ──────────────────────
NODE_W = 160
NODE_H = 56
RANK_GAP = 48    # --rank-gap: vertical gap between row tops
COL_GAP = 32     # --col-gap: horizontal gap between nodes in same rank
CANVAS_PAD = 40  # --canvas-pad: outer inset
GROUP_PAD_X = 16  # group container horizontal inner padding
GROUP_PAD_Y_TOP = 28  # group container top inner padding (room for label)
GROUP_PAD_Y_BOT = 16  # group container bottom inner padding
SELF_LOOP_DX = 28  # horizontal reach of self-loop arc

# ── directive sets ────────────────────────────────────────────────────────────
_GRAPH_DIRECTIVES = frozenset({
    "flowchart", "graph", "statediagram-v2", "statediagram",
})
_KNOWN_DIRECTIVES = frozenset({
    "flowchart", "graph", "sequencediagram", "statediagram-v2", "statediagram",
    "erdiagram", "classdiagram", "gantt", "timeline", "quadrantchart", "pie",
    "xychart-beta", "mindmap", "block-beta", "packet-beta", "kanban",
    "architecture-beta", "c4context", "c4container", "c4component",
    "gitgraph", "journey", "requirementdiagram",
})

# ── data structures ───────────────────────────────────────────────────────────

@dataclass
class _Node:
    id: str
    label: str = ""
    shape: str = "rect"           # rect|round|diamond|cylinder|circle|flag
    group: Optional[str] = None   # subgraph id
    rank: int = -1
    col: int = 0
    x: int = 0
    y: int = 0
    is_dummy: bool = False
    bary: float = 0.0
    icon: str = ""                # icon name from assets/icons/ (without .svg)
    css_class: str = ""           # semantic class, e.g. "external"


@dataclass
class _Edge:
    src: str
    dst: str
    label: str = ""
    style: str = "solid"          # solid|dotted|thick
    arrow: bool = True
    reversed_: bool = False       # back-edge flag


@dataclass
class _Group:
    id: str
    label: str = ""
    members: list[str] = field(default_factory=list)


# ── source preprocessing ──────────────────────────────────────────────────────

def _strip_frontmatter(src: str) -> str:
    """Remove YAML frontmatter (---...---) and return the remainder."""
    stripped = src.strip()
    if not stripped.startswith("---"):
        return stripped
    end = stripped.find("\n---", 3)
    if end == -1:
        return stripped
    return stripped[end + 4:].lstrip("\n")


def _detect_directive(src: str) -> tuple[str, str]:
    """Return (directive_lower, direction_upper) from first non-blank line."""
    for line in src.splitlines():
        line = line.strip()
        if not line or line.startswith("%%"):
            continue
        parts = line.split()
        directive = parts[0].lower()
        direction = parts[1].upper() if len(parts) > 1 else "TB"
        return directive, direction
    return "", "TB"


# ── Mermaid node spec parsing ─────────────────────────────────────────────────

# Matches: ID[label] or ID(label) or ID{label} etc.
_SPEC_RE = re.compile(
    r'^(?P<id>[A-Za-z_][A-Za-z0-9_\-\.]*)'
    r'(?:'
    r'\[\((?P<cylinder>[^\)]*)\)\]'      # [(cylinder)]
    r'|\(\((?P<circle>[^\)]*)\)\)'       # ((circle))
    r'|\[(?P<rect>[^\[\]]*)\]'           # [rect]
    r'|\((?P<round>[^\(\)]*)\)'          # (round)
    r'|\{(?P<diamond>[^\{\}]*)\}'        # {diamond}
    r'|>(?P<flag>[^\]]*)\]'              # >flag]
    r')?'
)

def _parse_spec(spec: str) -> tuple[str, str, str]:
    """Return (id, label, shape) from node spec like A[Label]."""
    spec = spec.strip()
    m = _SPEC_RE.match(spec)
    if not m:
        safe = re.match(r'[A-Za-z_][A-Za-z0-9_\-\.]*', spec)
        nid = safe.group(0) if safe else spec
        return nid, nid, "rect"
    nid = m.group("id")
    for shape in ("cylinder", "circle", "rect", "round", "diamond", "flag"):
        val = m.group(shape)
        if val is not None:
            label = val.strip().strip('"\'')
            return nid, label or nid, shape
    return nid, nid, "rect"


# Matches :::className suffix on node specs (e.g. A[Label]:::external)
_CSS_CLASS_RE = re.compile(r':::([A-Za-z][A-Za-z0-9_-]*)$')


def _parse_spec_and_class(spec: str) -> tuple[str, str, str, str]:
    """Return (id, label, shape, css_class). Strips :::class suffix before parsing."""
    spec = spec.strip()
    m = _CSS_CLASS_RE.search(spec)
    css_class = ""
    if m:
        css_class = m.group(1)
        spec = spec[:m.start()].rstrip()
    nid, label, shape = _parse_spec(spec)
    return nid, label, shape, css_class


# ── graph parser (flowchart / graph / stateDiagram) ───────────────────────────

# Matches edge operators with optional label:
#   A -- text --> B    A --> B    A ---B    A -.-> B    A ==> B    A -->|text| B
_EDGE_RE = re.compile(
    r'^(?P<src_raw>.+?)\s*'
    r'(?:'
    r'--\s*(?P<mid_label>[^->=]+?)\s*(?P<arrow_long>-->|---)'   # -- text --> / -- text ---
    r'|(?P<arrow_short>-\.->|-\.-|==>|-->|---)'                  # plain operators
    r')'
    r'\s*(?:\|(?P<pipe_label>[^\|]*)\|)?\s*'
    r'(?P<dst_raw>.+)$'
)


def _parse_graph_source(lines: list[str]) -> tuple[dict[str, _Node], list[_Edge], dict[str, _Group]]:
    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    groups: dict[str, _Group] = {}
    stack: list[str] = []  # subgraph id stack

    def _ensure(nid: str, label: str, shape: str, css_class: str = "") -> None:
        if nid not in nodes:
            nodes[nid] = _Node(id=nid, label=label or nid, shape=shape, css_class=css_class)
        else:
            if label and label != nid:
                nodes[nid].label = label
            if css_class:
                nodes[nid].css_class = css_class
        if stack:
            gid = stack[-1]
            nodes[nid].group = gid
            if nid not in groups[gid].members:
                groups[gid].members.append(nid)

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line.startswith(("style ", "classDef ", "class ", "linkStyle ", "click ")):
            continue

        # Subgraph start
        if line.lower().startswith("subgraph"):
            rest = line[8:].strip()
            # remove trailing [direction] if present
            rest = re.sub(r'\s*\[[A-Z]{2,3}\]\s*$', '', rest).strip()
            # extract label from id["label"] or id[label] — strip surrounding quotes
            _m_bracket = re.match(r'^[A-Za-z_][A-Za-z0-9_\-\.]*\[([^\[\]]*)\]\s*$', rest)
            if _m_bracket:
                label = _m_bracket.group(1).strip().strip('"\'')
            else:
                label = rest.strip('"\'')
            gid = f"_g{len(groups)}"
            groups[gid] = _Group(id=gid, label=label or gid)
            stack.append(gid)
            continue
        if line.lower().strip() in ("end", "end;"):
            if stack:
                stack.pop()
            continue

        # Try to match as edge chain; a line can chain: A --> B --> C
        _parse_line(line, edges, _ensure)

    return nodes, edges, groups


def _parse_line(line: str, edges: list[_Edge], ensure_fn) -> None:
    """Parse one line which may be a node decl, an edge, or a chain."""
    m = _EDGE_RE.match(line)
    if not m:
        # Standalone node declaration
        nid, label, shape, css_class = _parse_spec_and_class(line)
        if re.match(r'[A-Za-z_]', nid):
            ensure_fn(nid, label, shape, css_class)
        return

    src_raw = m.group("src_raw").strip()
    dst_raw = m.group("dst_raw").strip()
    arrow = m.group("arrow_long") or m.group("arrow_short") or "-->"
    edge_label = (m.group("mid_label") or m.group("pipe_label") or "").strip()

    style = "dotted" if "-.-" in arrow else ("thick" if "==" in arrow else "solid")
    has_arrow = arrow.endswith(">")

    src_id, src_lbl, src_shp, src_cls = _parse_spec_and_class(src_raw)
    if not re.match(r'[A-Za-z_]', src_id):
        return
    ensure_fn(src_id, src_lbl, src_shp, src_cls)

    # dst_raw might chain: B --> C
    chain_m = _EDGE_RE.match(dst_raw)
    if chain_m:
        first_dst = chain_m.group("src_raw").strip()
        dst_id, dst_lbl, dst_shp, dst_cls = _parse_spec_and_class(first_dst)
        if not re.match(r'[A-Za-z_]', dst_id):
            return
        ensure_fn(dst_id, dst_lbl, dst_shp, dst_cls)
        edges.append(_Edge(src=src_id, dst=dst_id, label=edge_label, style=style, arrow=has_arrow))
        _parse_line(dst_raw, edges, ensure_fn)
    else:
        dst_id, dst_lbl, dst_shp, dst_cls = _parse_spec_and_class(dst_raw)
        if not re.match(r'[A-Za-z_]', dst_id):
            return
        ensure_fn(dst_id, dst_lbl, dst_shp, dst_cls)
        edges.append(_Edge(src=src_id, dst=dst_id, label=edge_label, style=style, arrow=has_arrow))


# ── cycle break (DFS back-edge detection) ─────────────────────────────────────

def _break_cycles(nodes: dict[str, _Node], edges: list[_Edge]) -> None:
    """Mark back-edges reversed_=True (DFS from source nodes)."""
    adj: dict[str, list[int]] = {nid: [] for nid in nodes}
    for i, e in enumerate(edges):
        if e.src in adj and e.dst in adj:
            adj[e.src].append(i)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    def dfs(u: str) -> None:
        color[u] = GRAY
        for ei in adj[u]:
            v = edges[ei].dst
            if color.get(v) == GRAY:
                edges[ei].reversed_ = True  # back-edge
            elif color.get(v) == WHITE:
                dfs(v)
        color[u] = BLACK

    for nid in list(nodes.keys()):
        if color[nid] == WHITE:
            dfs(nid)


# ── rank assignment (longest path, then dummy insertion) ──────────────────────

def _assign_ranks(nodes: dict[str, _Node], edges: list[_Edge]) -> None:
    """Longest-path rank assignment; inserts dummy nodes for multi-rank edges."""
    # Build effective successors (skip reversed edges for rank calc)
    succ: dict[str, list[str]] = {nid: [] for nid in nodes}
    pred_count: dict[str, int] = {nid: 0 for nid in nodes}
    for e in edges:
        if e.src in nodes and e.dst in nodes and not e.reversed_:
            succ[e.src].append(e.dst)
            pred_count[e.dst] += 1

    # Topological order (Kahn's algorithm on the forward DAG)
    from collections import deque
    queue: deque[str] = deque(nid for nid in nodes if pred_count[nid] == 0)
    topo: list[str] = []
    while queue:
        u = queue.popleft()
        topo.append(u)
        for v in succ[u]:
            pred_count[v] -= 1
            if pred_count[v] == 0:
                queue.append(v)
    # Any node not yet in topo (cycle residue) gets appended in stable id order
    remaining = [nid for nid in nodes if nid not in set(topo)]
    topo.extend(sorted(remaining))

    # Longest-path ranks
    for nid in nodes:
        nodes[nid].rank = 0
    for u in topo:
        for v in succ[u]:
            nodes[v].rank = max(nodes[v].rank, nodes[u].rank + 1)

    # Insert dummy nodes for edges spanning more than 1 rank
    new_nodes: dict[str, _Node] = {}
    new_edges: list[_Edge] = []
    for e in list(edges):
        if e.reversed_ or e.src not in nodes or e.dst not in nodes:
            new_edges.append(e)
            continue
        gap = nodes[e.dst].rank - nodes[e.src].rank
        if gap <= 1:
            new_edges.append(e)
            continue
        # Insert gap-1 dummy nodes
        prev_id = e.src
        for k in range(1, gap):
            dummy_id = f"_dummy_{e.src}_{e.dst}_{k}"
            dummy_rank = nodes[e.src].rank + k
            dummy = _Node(id=dummy_id, label="", is_dummy=True, rank=dummy_rank)
            new_nodes[dummy_id] = dummy
            new_edges.append(_Edge(src=prev_id, dst=dummy_id, label="" if k > 1 else e.label,
                                   style=e.style, arrow=False))
            prev_id = dummy_id
        new_edges.append(_Edge(src=prev_id, dst=e.dst, style=e.style, arrow=e.arrow))

    nodes.update(new_nodes)
    edges[:] = new_edges


# ── crossing minimisation (8-pass barycenter) ─────────────────────────────────

def _minimize_crossings(nodes: dict[str, _Node], edges: list[_Edge]) -> None:
    """8-pass barycenter crossing minimisation; assigns col index to each node."""
    max_rank = max((n.rank for n in nodes.values()), default=0)
    # Build ranks list (sorted by id for stability)
    ranks: list[list[str]] = [[] for _ in range(max_rank + 1)]
    for nid in sorted(nodes.keys()):
        r = nodes[nid].rank
        if 0 <= r <= max_rank:
            ranks[r].append(nid)

    # Build successor and predecessor adjacency (col-weighted)
    succ_ids: dict[str, list[str]] = {nid: [] for nid in nodes}
    pred_ids: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:
        if e.src in nodes and e.dst in nodes:
            succ_ids[e.src].append(e.dst)
            pred_ids[e.dst].append(e.src)

    def _assign_cols(rank_list: list[str]) -> None:
        for i, nid in enumerate(rank_list):
            nodes[nid].col = i
            nodes[nid].bary = float(i)

    # Initialize columns in declaration order (stable)
    for r_list in ranks:
        _assign_cols(r_list)

    def _forward_pass() -> None:
        for r in range(1, max_rank + 1):
            for nid in ranks[r]:
                ps = pred_ids[nid]
                if ps:
                    nodes[nid].bary = sum(nodes[p].col for p in ps if p in nodes) / len(ps)
            ranks[r].sort(key=lambda nid: (nodes[nid].bary, nid))
            _assign_cols(ranks[r])

    def _backward_pass() -> None:
        for r in range(max_rank - 1, -1, -1):
            for nid in ranks[r]:
                ss = succ_ids[nid]
                if ss:
                    nodes[nid].bary = sum(nodes[s].col for s in ss if s in nodes) / len(ss)
            ranks[r].sort(key=lambda nid: (nodes[nid].bary, nid))
            _assign_cols(ranks[r])

    for _ in range(CROSSING_PASSES // 2):
        _forward_pass()
        _backward_pass()


# ── coordinate assignment (integer pixels) ────────────────────────────────────

def _assign_coordinates(nodes: dict[str, _Node]) -> tuple[int, int]:
    """Assign x/y pixel positions; return (canvas_width, canvas_height)."""
    if not nodes:
        return 2 * CANVAS_PAD, 2 * CANVAS_PAD

    col_pitch = NODE_W + COL_GAP
    row_pitch = NODE_H + RANK_GAP

    max_cols_per_rank: dict[int, int] = {}
    for n in nodes.values():
        r = n.rank
        max_cols_per_rank[r] = max(max_cols_per_rank.get(r, 0), n.col)

    max_col = max(max_cols_per_rank.values(), default=0)
    max_rank = max(n.rank for n in nodes.values())

    for n in nodes.values():
        n.x = CANVAS_PAD + n.col * col_pitch
        n.y = CANVAS_PAD + n.rank * row_pitch

    canvas_w = CANVAS_PAD * 2 + (max_col + 1) * col_pitch - COL_GAP
    canvas_h = CANVAS_PAD * 2 + (max_rank + 1) * row_pitch - RANK_GAP
    return canvas_w, canvas_h


# ── edge routing ──────────────────────────────────────────────────────────────

def _arrowhead(tip_x: int, tip_y: int, dx: float, dy: float) -> str:
    """Return SVG polygon points string for an arrowhead tip at (tip_x, tip_y)."""
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    px, py = -uy, ux  # perpendicular
    bx = int(tip_x - ux * 10)
    by = int(tip_y - uy * 10)
    p1x = int(bx + px * 6)
    p1y = int(by + py * 6)
    p2x = int(bx - px * 6)
    p2y = int(by - py * 6)
    return f"{tip_x},{tip_y} {p1x},{p1y} {p2x},{p2y}"


def _fan_offset(index: int, total: int, node_w: int = NODE_W, pad: int = 16) -> int:
    """Distribute fan-in/fan-out endpoints across node edge (spec §Step6)."""
    usable = node_w - 2 * pad
    if total <= 1:
        return node_w // 2
    step = usable // (total + 1)
    return pad + step * (index + 1)


def _route_edges(nodes: dict[str, _Node], edges: list[_Edge], canvas_w: int) -> list[dict]:
    """Return list of edge render specs (path_d, arrowhead_pts, label, style)."""
    # Count fan-in per node (for endpoint distribution)
    fan_in: dict[str, list[str]] = {nid: [] for nid in nodes}
    fan_out: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:
        if e.src in nodes and e.dst in nodes and not e.reversed_:
            fan_in[e.dst].append(e.src)
            fan_out[e.src].append(e.dst)

    right_lane_x = canvas_w - CANVAS_PAD + 32  # reserved right-lane x

    result: list[dict] = []
    for e in edges:
        if e.src not in nodes or e.dst not in nodes:
            continue
        s = nodes[e.src]
        d = nodes[e.dst]

        # Self-loop
        if e.src == e.dst:
            lx = s.x + NODE_W
            ty = s.y
            by_ = s.y + NODE_H
            # Small arc: right of node, curves back
            path = (f"M {lx} {ty + 12} "
                    f"C {lx + SELF_LOOP_DX} {ty} {lx + SELF_LOOP_DX} {by_} "
                    f"{lx} {by_ - 12}")
            tip_x, tip_y = lx, by_ - 12
            ah = _arrowhead(tip_x, tip_y, -1, 0) if e.arrow else None
            result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                           "lx": tip_x + 14, "ly": (ty + by_) // 2})
            continue

        # Back-edge or reversed → right-lane orthogonal
        rank_gap = d.rank - s.rank
        if e.reversed_ or rank_gap < 0 or rank_gap > 1:
            # Right-lane orthogonal: exit right of src, go down to dst rank, enter right of dst
            sx = s.x + NODE_W
            sy = s.y + NODE_H // 2
            dx_ = d.x + NODE_W
            dy_ = d.y + NODE_H // 2
            path = (f"M {sx} {sy} H {right_lane_x} V {dy_} H {dx_}")
            ah = _arrowhead(dx_, dy_, -1, 0) if e.arrow else None
            mid_x = right_lane_x + 4
            mid_y = (sy + dy_) // 2
            result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                           "lx": mid_x, "ly": mid_y})
            continue

        # Adjacent-rank forward edge: cubic Bezier bottom-centre to top-centre
        # Fan-out from src
        out_list = fan_out[e.src]
        out_idx = out_list.index(e.dst) if e.dst in out_list else 0
        out_offset = _fan_offset(out_idx, len(out_list))

        # Fan-in to dst
        in_list = fan_in[e.dst]
        in_idx = in_list.index(e.src) if e.src in in_list else 0
        in_offset = _fan_offset(in_idx, len(in_list))

        x1 = s.x + out_offset
        y1 = s.y + NODE_H
        x2 = d.x + in_offset
        y2 = d.y
        # Control points at 1/3 and 2/3 of vertical span
        cy1 = y1 + (y2 - y1) // 3
        cy2 = y1 + 2 * (y2 - y1) // 3
        path = f"M {x1} {y1} C {x1} {cy1} {x2} {cy2} {x2} {y2}"

        ah = _arrowhead(x2, y2, x2 - x1, y2 - cy2) if e.arrow else None
        mid_x = (x1 + x2) // 2
        mid_y = (y1 + y2) // 2
        result.append({"d": path, "ah": ah, "label": e.label, "style": e.style,
                       "lx": mid_x + 4, "ly": mid_y})

    return result


# ── HTML renderer (graph topology) ───────────────────────────────────────────

_NODE_CSS = {
    "rect": "border-radius:var(--node-radius,8px);",
    "round": "border-radius:28px;",
    # diamond uses clip-path to avoid rotating the label
    "diamond": "border-radius:4px; clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);",
    "cylinder": "border-radius:8px 8px 2px 2px; border-top:2px solid var(--node-border);",
    "circle": "border-radius:50%;",
    "flag": "border-radius:0 8px 8px 0;",
}

_WRAP_CHARS = 22  # label wrap threshold


def _wrap_label(label: str) -> list[str]:
    """Split label into lines of max _WRAP_CHARS characters.

    Treats literal \\n (two-char escape) and real newlines as explicit breaks.
    """
    # Normalise literal \n escape sequences to real newlines first
    normalized = label.replace("\\n", "\n")
    if "\n" in normalized:
        result: list[str] = []
        for chunk in normalized.split("\n"):
            stripped = chunk.strip()
            if stripped:
                result.extend(_wrap_label(stripped))
        return result or [label]
    if len(normalized) <= _WRAP_CHARS:
        return [normalized]
    words = normalized.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > _WRAP_CHARS:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [normalized]


def _render_graph_fragment(
    nodes: dict[str, _Node],
    edges: list[_Edge],
    groups: dict[str, _Group],
    canvas_w: int,
    canvas_h: int,
) -> str:
    parts: list[str] = []

    # Container
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative; width:{canvas_w}px; height:{canvas_h}px; '
        f'--node-w:{NODE_W}px; --node-h:{NODE_H}px; '
        f'--rank-gap:{RANK_GAP}px; --col-gap:{COL_GAP}px; '
        f'--canvas-pad:{CANVAS_PAD}px;">'
    )

    # Group containers (subgraphs)
    for gid, grp in groups.items():
        mbrs = [nodes[m] for m in grp.members if m in nodes and not nodes[m].is_dummy]
        if not mbrs:
            continue
        gx = min(n.x for n in mbrs) - GROUP_PAD_X
        gy = min(n.y for n in mbrs) - GROUP_PAD_Y_TOP
        gw = max(n.x + NODE_W for n in mbrs) - gx + GROUP_PAD_X
        gh = max(n.y + NODE_H for n in mbrs) - gy + GROUP_PAD_Y_BOT
        glabel = _h(grp.label)
        parts.append(
            f'<div class="diagram-group" style="'
            f'position:absolute; left:{gx}px; top:{gy}px; '
            f'width:{gw}px; height:{gh}px; '
            f'border:1px solid var(--group-border,var(--accent-1)); '
            f'border-radius:var(--group-radius,12px); '
            f'box-sizing:border-box;">'
            f'<span class="group-label" style="'
            f'position:absolute; top:4px; left:8px; '
            f'font-size:10px; color:var(--node-fg-dim,var(--text-secondary)); '
            f'font-family:var(--label-font,var(--font-primary));">'
            f'{glabel}</span></div>'
        )

    # Node divs
    for nid, n in nodes.items():
        if n.is_dummy:
            parts.append(
                f'<div style="position:absolute; left:{n.x}px; top:{n.y}px; '
                f'width:0; height:0; overflow:hidden;"></div>'
            )
            continue
        shape_css = _NODE_CSS.get(n.shape, _NODE_CSS["rect"])
        is_external = n.css_class == "external"

        # Split label on first | for tech stereotype sub-label (e.g. "User Service|Spring Boot")
        if "|" in n.label:
            main_label, tech_label = (p.strip() for p in n.label.split("|", 1))
        else:
            main_label, tech_label = n.label, ""

        main_lines = _wrap_label(main_label)
        main_html = "<br>".join(_h(ln) for ln in main_lines)
        icon_svg = _load_icon(n.icon) if n.icon else ""

        # Height: base + multi-line expansion + tech sub-label + icon room
        extra_h = max(0, (len(main_lines) - 1) * 18)
        if icon_svg:
            extra_h = max(extra_h, 20)
        if tech_label:
            extra_h += 16
        node_h = NODE_H + extra_h

        # Color tokens: dim everything for external nodes
        fg_var = "var(--node-fg-dim,var(--text-secondary))" if is_external else "var(--node-fg,var(--text-primary))"
        border_var = "var(--node-fg-dim,var(--text-secondary))" if is_external else "var(--node-border,var(--card-border))"

        tech_span = ""
        if tech_label:
            tech_span = (
                f'<span class="node-tech" style="'
                f'display:block; font-size:11px; font-weight:400; '
                f'color:var(--node-fg-dim,var(--text-secondary)); '
                f'font-family:var(--label-font,var(--font-primary)); '
                f'line-height:1.2; margin-top:2px;">'
                f'{_h(tech_label)}</span>'
            )

        if icon_svg:
            inner = (
                f'<span class="node-icon" style="'
                f'display:block;width:20px;height:20px;margin:0 auto 3px;'
                f'color:{fg_var};">'
                f'{icon_svg}</span>'
                f'<span class="node-label" style="'
                f'font-size:13px; font-weight:700; '
                f'color:{fg_var}; '
                f'font-family:var(--label-font,var(--font-primary)); '
                f'line-height:1.3;">{main_html}</span>'
                f'{tech_span}'
            )
            flex_dir = "column"
        else:
            inner = (
                f'<span class="node-label" style="'
                f'font-size:14px; font-weight:700; '
                f'color:{fg_var}; '
                f'font-family:var(--label-font,var(--font-primary)); '
                f'line-height:1.3;">{main_html}</span>'
                f'{tech_span}'
            )
            flex_dir = "column" if tech_label else "row"

        extra_cls = f" node-{n.css_class}" if n.css_class else ""
        parts.append(
            f'<div class="node node-{_h(n.shape)}{extra_cls}" style="'
            f'position:absolute; left:{n.x}px; top:{n.y}px; '
            f'width:var(--node-w,{NODE_W}px); height:{node_h}px; '
            f'min-width:{NODE_W}px; min-height:{NODE_H}px; '
            f'padding:var(--node-pad-v,12px) var(--node-pad-h,16px); '
            f'box-sizing:border-box; '
            f'border:1px solid {border_var}; '
            f'{shape_css} '
            f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from)),var(--node-bg-to,var(--card-bg-to))); '
            f'display:flex; flex-direction:{flex_dir}; align-items:center; justify-content:center; '
            f'text-align:center;">'
            f'{inner}</div>'
        )

    # SVG overlay — paths and arrowheads only; edge labels as HTML siblings below
    parts.append(
        f'<svg style="position:absolute; inset:0; '
        f'width:{canvas_w}px; height:{canvas_h}px; '
        f'overflow:visible; pointer-events:none;">'
    )

    routed = _route_edges(nodes, edges, canvas_w)
    for spec in routed:
        d = spec["d"]
        style = spec["style"]
        stroke_color = "var(--edge-strong,var(--accent-1))" if style == "thick" else "var(--edge,var(--card-border))"
        dash = ' stroke-dasharray="6 4"' if style == "dotted" else ""
        parts.append(
            f'<path d="{d}" stroke="{stroke_color}" fill="none" '
            f'stroke-width="1.5"{dash}/>'
        )
        if spec["ah"]:
            parts.append(
                f'<polygon points="{spec["ah"]}" fill="{stroke_color}"/>'
            )

    parts.append('</svg>')

    # Edge labels as absolutely-positioned HTML siblings (not inside SVG)
    for spec in routed:
        if spec["label"]:
            lx, ly = spec["lx"], spec["ly"]
            parts.append(
                f'<span class="edge-label" style="'
                f'position:absolute; left:{lx}px; top:{ly - 9}px; '
                f'font-size:11px; font-family:var(--label-font,var(--font-primary)); '
                f'color:var(--node-fg-dim,var(--text-secondary)); '
                f'background:var(--node-bg-from,var(--card-bg-from)); '
                f'padding:0 3px; white-space:nowrap; pointer-events:none;">'
                f'{_h(spec["label"])}</span>'
            )

    parts.append('</div>')
    return "\n".join(parts)


# ── diagram metadata + legend helpers ────────────────────────────────────────

_DIRECTIVE_LABELS: dict[str, str] = {
    "flowchart": "Flowchart", "graph": "Graph",
    "sequencediagram": "Sequence", "statediagram-v2": "State Machine",
    "statediagram": "State Machine", "erdiagram": "ER Diagram",
    "classdiagram": "Class Diagram", "gantt": "Gantt",
    "timeline": "Timeline", "quadrantchart": "Quadrant",
    "pie": "Pie Chart", "xychart-beta": "Chart",
    "mindmap": "Mind Map", "block-beta": "Block",
    "architecture-beta": "Architecture", "c4context": "C4 Context",
    "c4container": "C4 Container", "c4component": "C4 Component",
    "kanban": "Kanban",
}


def _extract_diagram_title(src: str) -> str:
    """Return the text from a '%% title: <text>' comment, or '' if none present."""
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("%%"):
            comment = s[2:].strip()
            if comment.lower().startswith("title:"):
                return comment[6:].strip()
    return ""


def _render_metadata_chip(directive: str, title: str) -> str:
    """Return a type-chip + title bar only when a title is explicitly set.

    Omitting the chip for untitled diagrams avoids adding visual chrome to every
    existing diagram. The type badge only appears alongside a title.
    """
    if not title:
        return ""
    type_label = _DIRECTIVE_LABELS.get(directive.lower(), "")
    parts: list[str] = []
    parts.append(
        '<div class="diagram-meta" style="'
        'display:flex; align-items:center; gap:8px; '
        'margin-bottom:8px; '
        'font-family:var(--label-font,var(--font-primary));">'
    )
    if type_label:
        parts.append(
            f'<span class="diagram-type-chip" style="'
            f'border:1px solid var(--node-fg-dim,var(--text-secondary)); '
            f'border-radius:4px; padding:1px 6px; '
            f'font-size:9px; font-weight:700; letter-spacing:0.07em; '
            f'text-transform:uppercase; '
            f'color:var(--node-fg-dim,var(--text-secondary));">'
            f'{_h(type_label)}</span>'
        )
    if title:
        parts.append(
            f'<span class="diagram-title" style="'
            f'font-size:11px; font-weight:600; '
            f'color:var(--node-fg,var(--text-primary));">'
            f'{_h(title)}</span>'
        )
    parts.append('</div>')
    return "".join(parts)


def _render_legend(edges: list[_Edge], groups: dict) -> str:
    """Return an auto-generated legend row when ≥1 non-solid semantic is present."""
    has_solid = any(e.style == "solid" for e in edges if not e.reversed_)
    has_dashed = any(e.style == "dotted" for e in edges)
    has_thick = any(e.style == "thick" for e in edges)
    has_groups = bool(groups)

    # Only show legend when there's something non-obvious to explain
    semantic_count = sum([has_dashed, has_thick, has_groups])
    if semantic_count == 0:
        return ""

    items: list[str] = []
    if has_solid:
        items.append(
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<svg width="20" height="10" style="overflow:visible;">'
            '<line x1="0" y1="5" x2="20" y2="5" '
            'stroke="var(--edge,var(--card-border))" stroke-width="1.5"/>'
            '<polygon points="20,5 15,2.5 15,7.5" '
            'fill="var(--edge,var(--card-border))"/>'
            '</svg>'
            'Synchronous</span>'
        )
    if has_dashed:
        items.append(
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<svg width="20" height="10" style="overflow:visible;">'
            '<line x1="0" y1="5" x2="20" y2="5" '
            'stroke="var(--edge,var(--card-border))" stroke-width="1.5" '
            'stroke-dasharray="4 3"/>'
            '<polygon points="20,5 15,2.5 15,7.5" '
            'fill="var(--edge,var(--card-border))"/>'
            '</svg>'
            'Async / optional</span>'
        )
    if has_thick:
        items.append(
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<svg width="20" height="10" style="overflow:visible;">'
            '<line x1="0" y1="5" x2="20" y2="5" '
            'stroke="var(--edge-strong,var(--accent-1))" stroke-width="2.5"/>'
            '<polygon points="20,5 15,2.5 15,7.5" '
            'fill="var(--edge-strong,var(--accent-1))"/>'
            '</svg>'
            'Critical path</span>'
        )
    if has_groups:
        items.append(
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<svg width="20" height="10">'
            '<rect x="0" y="1" width="20" height="8" rx="2" '
            'fill="none" stroke="var(--group-border,var(--accent-1))" '
            'stroke-width="1"/>'
            '</svg>'
            'Service boundary</span>'
        )

    if not items:
        return ""
    joined = "\n".join(items)
    return (
        '<div class="diagram-legend" style="'
        'display:flex; flex-wrap:wrap; gap:12px; '
        'margin-top:8px; '
        'font-size:10px; font-family:var(--label-font,var(--font-primary)); '
        'color:var(--node-fg-dim,var(--text-secondary));">'
        f'{joined}'
        '</div>'
    )


# ── graph topology strategy ──────────────────────────────────────────────────

def _layout_graph_topology(src: str, direction: str, width_hint: int) -> str:
    lines = src.splitlines()
    # Skip up to and including the directive line (first non-blank, non-comment line)
    directive_index = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith(("%%", "//")):
            directive_index = i
            break
    content_lines = lines[directive_index + 1:]

    nodes, edges, groups = _parse_graph_source(content_lines)

    if len(nodes) > NODE_CAP:
        raise ValueError(
            f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}). "
            "Split the diagram into smaller slides."
        )
    if len(edges) > EDGE_CAP:
        raise ValueError(
            f"Cap exceeded: {len(edges)} edges (cap {EDGE_CAP}). "
            "Split the diagram into smaller slides."
        )
    if len(groups) > GROUP_CAP:
        raise ValueError(
            f"Cap exceeded: {len(groups)} subgraphs (cap {GROUP_CAP})."
        )

    if not nodes:
        raise ValueError("No nodes found in diagram source.")

    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)
    canvas_w, canvas_h = _assign_coordinates(nodes)

    # Apply width hint scaling if provided
    if width_hint and canvas_w > 0:
        scale = width_hint / canvas_w
        if scale < 0.95 or scale > 1.05:
            for n in nodes.values():
                n.x = int(n.x * scale)
            canvas_w = width_hint

    fragment = _render_graph_fragment(nodes, edges, groups, canvas_w, canvas_h)

    # Wrap with metadata chip (type + title) and auto-legend
    directive, _ = _detect_directive(src)
    title = _extract_diagram_title(src)
    meta_html = _render_metadata_chip(directive, title)
    legend_html = _render_legend(edges, groups)

    if meta_html or legend_html:
        return (
            '<div class="diagram-wrapper" style="'
            'font-family:var(--label-font,var(--font-primary));">'
            f'{meta_html}{fragment}{legend_html}'
            '</div>'
        )
    return fragment


# ── helpers shared by T2/T3 ──────────────────────────────────────────────────

def _directive_content(src: str) -> list[str]:
    """Return lines after the first non-blank, non-comment line (the directive)."""
    lines = src.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith(("%%", "//")):
            return lines[i + 1:]
    return []


# ── T2: sequenceDiagram ───────────────────────────────────────────────────────

_SEQ_PART_RE = re.compile(r'^(?:participant|actor)\s+(\S+)(?:\s+as\s+(.+))?', re.I)
_SEQ_MSG_RE = re.compile(
    r'^(\S+)\s*(->>|-->>|->|-->|-x|--x|-\)|--\))\s*(\S+)\s*:\s*(.*)$'
)
_SEQ_BLOCK_RE = re.compile(r'^(alt|loop|opt|par|critical|break|rect)\s*(.*)', re.I)
_SEQ_END_RE = re.compile(r'^end\s*$', re.I)


def _layout_lifeline(src: str, direction: str, width_hint: int) -> str:
    """sequenceDiagram: participants as columns, messages as horizontal arrows."""
    content_lines = _directive_content(src)
    participants: list[str] = []
    p_label: dict[str, str] = {}

    def _ensure_p(name: str) -> None:
        n = name.strip()
        if n and n not in participants:
            participants.append(n)
            p_label.setdefault(n, n)

    items: list[dict] = []
    block_depth = 0
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m = _SEQ_PART_RE.match(line)
        if m:
            alias = m.group(1).strip()
            display = (m.group(2) or alias).strip()
            p_label[alias] = display
            _ensure_p(alias)
            continue
        m = _SEQ_MSG_RE.match(line)
        if m:
            sp, arrow, dp, lbl = m.group(1), m.group(2), m.group(3), m.group(4)
            _ensure_p(sp); _ensure_p(dp)
            items.append({"type": "msg", "src": sp, "dst": dp,
                          "label": lbl.strip(), "dotted": arrow.startswith("--")})
            continue
        m = _SEQ_BLOCK_RE.match(line)
        if m:
            items.append({"type": "block", "kw": m.group(1), "label": m.group(2).strip()})
            block_depth += 1
            continue
        if _SEQ_END_RE.match(line) and block_depth > 0:
            block_depth -= 1

    if not participants:
        raise ValueError("No participants found in sequenceDiagram.")

    COL_W, COL_GAP, PAD_H, PAD_V = 160, 24, 40, 24
    HDR_H, ROW_H = 48, 40
    col_pitch = COL_W + COL_GAP
    n_parts = len(participants)
    canvas_w = PAD_H * 2 + n_parts * col_pitch - COL_GAP
    if width_hint and canvas_w > 0 and abs(width_hint / canvas_w - 1.0) > 0.05:
        col_pitch = int(col_pitch * width_hint / canvas_w)
        canvas_w = width_hint
    n_rows = sum(1 for it in items if it["type"] in ("msg", "block"))
    canvas_h = PAD_V * 2 + HDR_H + n_rows * ROW_H + 32
    ll_top = PAD_V + HDR_H
    ll_bot = canvas_h - PAD_V

    def _cx(pid: str) -> int:
        idx = participants.index(pid) if pid in participants else 0
        return PAD_H + idx * col_pitch + COL_W // 2

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    for i, pid in enumerate(participants):
        lx = PAD_H + i * col_pitch
        lbl = _h(p_label.get(pid, pid))
        parts.append(
            f'<div class="node node-rect" style="position:absolute;left:{lx}px;top:{PAD_V}px;'
            f'width:{COL_W}px;height:{HDR_H - 8}px;display:flex;align-items:center;'
            f'justify-content:center;border:1px solid var(--node-border,var(--card-border));'
            f'border-radius:var(--node-radius,8px);box-sizing:border-box;'
            f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from)),'
            f'var(--node-bg-to,var(--card-bg-to)));"><span class="node-label" style="'
            f'font-size:13px;font-weight:700;color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));">{lbl}</span></div>'
        )
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    for pid in participants:
        lx = _cx(pid)
        parts.append(
            f'<line x1="{lx}" y1="{ll_top}" x2="{lx}" y2="{ll_bot}" '
            f'stroke="var(--edge,var(--card-border))" stroke-width="1" stroke-dasharray="5 4"/>'
        )
    row = 0
    for it in items:
        if it["type"] == "block":
            ry = ll_top + row * ROW_H
            parts.append(
                f'<rect x="{PAD_H // 2}" y="{ry}" width="{canvas_w - PAD_H}" height="{ROW_H}" '
                f'fill="var(--node-bg-from,var(--card-bg-from))" opacity="0.6" '
                f'stroke="var(--edge,var(--card-border))" stroke-width="1" rx="3"/>'
            )
            row += 1; continue
        if it["type"] != "msg":
            continue
        sx, dx2 = _cx(it["src"]), _cx(it["dst"])
        ry = ll_top + row * ROW_H + ROW_H // 2
        dash = ' stroke-dasharray="6 4"' if it["dotted"] else ""
        if sx == dx2:
            parts.append(
                f'<path d="M {sx} {ry - 8} C {sx + 36} {ry - 8} {sx + 36} {ry + 8} {sx} {ry + 8}" '
                f'stroke="var(--edge,var(--card-border))" fill="none" stroke-width="1.5"{dash}/>'
            )
            ah = _arrowhead(sx, ry + 8, -1, 0)
        else:
            parts.append(
                f'<line x1="{sx}" y1="{ry}" x2="{dx2}" y2="{ry}" '
                f'stroke="var(--edge,var(--card-border))" stroke-width="1.5"{dash}/>'
            )
            ah = _arrowhead(dx2, ry, 1 if dx2 > sx else -1, 0)
        parts.append(f'<polygon points="{ah}" fill="var(--edge,var(--card-border))"/>')
        row += 1
    parts.append('</svg>')
    row = 0
    for it in items:
        if it["type"] == "block":
            ry = ll_top + row * ROW_H
            parts.append(
                f'<span style="position:absolute;left:{PAD_H + 4}px;top:{ry + 3}px;'
                f'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;'
                f'color:var(--node-fg-dim,var(--text-secondary));'
                f'font-family:var(--label-font,var(--font-primary));">'
                f'{_h(it["kw"])}{" " + _h(it["label"]) if it["label"] else ""}</span>'
            )
            row += 1; continue
        if it["type"] != "msg":
            continue
        sx, dx2 = _cx(it["src"]), _cx(it["dst"])
        ry = ll_top + row * ROW_H + ROW_H // 2
        lbl = _h(it["label"])
        if lbl:
            mid_x = (sx + dx2) // 2
            parts.append(
                f'<span class="edge-label" style="position:absolute;'
                f'left:{mid_x - 30}px;top:{ry - 18}px;'
                f'font-size:11px;color:var(--node-fg-dim,var(--text-secondary));'
                f'font-family:var(--label-font,var(--font-primary));'
                f'background:var(--node-bg-from,var(--card-bg-from));'
                f'padding:0 3px;white-space:nowrap;">{lbl}</span>'
            )
        row += 1
    parts.append('</div>')
    return "\n".join(parts)


# ── T2: erDiagram ─────────────────────────────────────────────────────────────

_ER_REL_RE = re.compile(r'^(\w+)\s+[|o}\{]{1,2}-{1,2}[|o{\}]{1,2}\s+(\w+)\s*:\s*(.*)$')


def _layout_er(src: str, direction: str, width_hint: int) -> str:
    """erDiagram: entities as nodes, relationships as edges (graph topology reuse)."""
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    current_entity: Optional[str] = None
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line == "}":
            current_entity = None; continue
        m = re.match(r'^(\w+)\s*\{', line)
        if m:
            eid = m.group(1)
            nodes.setdefault(eid, _Node(id=eid, label=eid, shape="rect"))
            current_entity = eid; continue
        if current_entity:
            continue
        m = _ER_REL_RE.match(line)
        if m:
            e1, e2, lbl = m.group(1), m.group(2), m.group(3).strip()
            for eid in (e1, e2):
                nodes.setdefault(eid, _Node(id=eid, label=eid, shape="rect"))
            edges.append(_Edge(src=e1, dst=e2, label=lbl, style="solid", arrow=True))
    if not nodes:
        raise ValueError("No entities found in erDiagram.")
    return _graph_from_content_nodes(nodes, edges, {}, width_hint)


def _graph_from_content_nodes(
    nodes: dict[str, _Node],
    edges: list[_Edge],
    groups: dict[str, _Group],
    width_hint: int,
) -> str:
    if len(nodes) > NODE_CAP:
        raise ValueError(f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}).")
    if len(edges) > EDGE_CAP:
        raise ValueError(f"Cap exceeded: {len(edges)} edges (cap {EDGE_CAP}).")
    if len(groups) > GROUP_CAP:
        raise ValueError(f"Cap exceeded: {len(groups)} groups/boundaries (cap {GROUP_CAP}).")
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)
    canvas_w, canvas_h = _assign_coordinates(nodes)
    if width_hint and canvas_w > 0 and abs(width_hint / canvas_w - 1.0) > 0.05:
        scale = width_hint / canvas_w
        for n in nodes.values():
            n.x = int(n.x * scale)
        canvas_w = width_hint
    return _render_graph_fragment(nodes, edges, groups, canvas_w, canvas_h)


# ── T2: classDiagram ──────────────────────────────────────────────────────────

_CLASS_REL_RE = re.compile(
    r'^(\w+)\s*(?:"[^"]*"\s*)?'
    r'(<\|--|<\|\.\.|\.\.>\||\|>|\*--|o--|-->|\.\.>|\.\.|\|\|)'
    r'\s*(?:"[^"]*"\s*)?(\w+)(?:\s*:\s*(.*))?$'
)


def _layout_class(src: str, direction: str, width_hint: int) -> str:
    """classDiagram: classes as nodes, relationships as edges (graph topology reuse)."""
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    current_class: Optional[str] = None
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line == "}":
            current_class = None; continue
        m = re.match(r'^class\s+(\w+)', line)
        if m:
            cid = m.group(1)
            nodes.setdefault(cid, _Node(id=cid, label=cid, shape="rect"))
            current_class = cid if "{" in line else None
            continue
        if current_class:
            continue
        m = _CLASS_REL_RE.match(line)
        if m:
            c1, op, c2, lbl = m.group(1), m.group(2), m.group(3), (m.group(4) or "")
            for cid in (c1, c2):
                nodes.setdefault(cid, _Node(id=cid, label=cid, shape="rect"))
            style = "dotted" if ".." in op else "solid"
            edges.append(_Edge(src=c1, dst=c2, label=lbl.strip(), style=style, arrow=True))
            continue
        # Bare "A : method()" — just ensure class exists
        m2 = re.match(r'^(\w+)\s*:', line)
        if m2:
            nodes.setdefault(m2.group(1), _Node(id=m2.group(1), label=m2.group(1), shape="rect"))
    if not nodes:
        raise ValueError("No classes found in classDiagram.")
    return _graph_from_content_nodes(nodes, edges, {}, width_hint)


# ── T3: gantt ─────────────────────────────────────────────────────────────────

def _layout_gantt(src: str, direction: str, width_hint: int) -> str:
    """gantt: sections as swim-lanes, tasks as horizontal bars."""
    content_lines = _directive_content(src)
    title = ""
    sections: list[dict] = [{"name": "Tasks", "tasks": []}]
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        low = line.lower()
        if low.startswith("title "):
            title = line[6:].strip(); continue
        if low.startswith(("dateformat", "axisformat", "excludes", "todaymarker")):
            continue
        if low.startswith("section "):
            sections.append({"name": line[8:].strip(), "tasks": []}); continue
        if ":" in line:
            name, meta = line.split(":", 1)
            flags = {f.strip().lower() for f in meta.split(",")}
            sections[-1]["tasks"].append({
                "name": name.strip(),
                "crit": "crit" in flags, "done": "done" in flags,
            })
    sections = [s for s in sections if s["tasks"]]
    if not sections:
        raise ValueError("No tasks found in gantt.")

    PAD_H, PAD_V = 40, 24
    LABEL_W, BAR_H, ROW_GAP = 120, 28, 6
    SEC_H = 24
    total_rows = sum(len(s["tasks"]) for s in sections)
    canvas_w = width_hint or 720
    canvas_h = PAD_V * 2 + (24 if title else 0) + len(sections) * (SEC_H + 4) + total_rows * (BAR_H + ROW_GAP)
    bar_x = PAD_H + LABEL_W + 8
    bar_w_total = canvas_w - bar_x - PAD_H

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    y = PAD_V
    if title:
        parts.append(
            f'<div style="position:absolute;left:{PAD_H}px;top:{y}px;'
            f'font-size:13px;font-weight:700;color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));">{_h(title)}</div>'
        )
        y += 28
    for sec in sections:
        parts.append(
            f'<div style="position:absolute;left:{PAD_H}px;top:{y}px;'
            f'width:{canvas_w - PAD_H * 2}px;height:{SEC_H}px;'
            f'display:flex;align-items:flex-end;'
            f'border-bottom:1px solid var(--edge,var(--card-border));">'
            f'<span style="font-size:10px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.1em;color:var(--node-fg-dim,var(--text-secondary));'
            f'font-family:var(--label-font,var(--font-primary));">'
            f'{_h(sec["name"])}</span></div>'
        )
        y += SEC_H + 4
        n = len(sec["tasks"])
        each_w = max(32, (bar_w_total - (n - 1) * 4) // n)
        for i, task in enumerate(sec["tasks"]):
            tx = bar_x + i * (each_w + 4)
            bar_color = (
                "var(--edge-strong,var(--accent-1))" if task["crit"]
                else "var(--node-border,var(--card-border))" if task["done"]
                else "var(--node-bg-from,var(--card-bg-from))"
            )
            parts.append(
                f'<div style="position:absolute;left:{PAD_H}px;top:{y}px;'
                f'width:{LABEL_W}px;height:{BAR_H}px;'
                f'display:flex;align-items:center;overflow:hidden;">'
                f'<span style="font-size:11px;color:var(--node-fg,var(--text-primary));'
                f'font-family:var(--label-font,var(--font-primary));'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
                f'{_h(task["name"])}</span></div>'
            )
            parts.append(
                f'<div style="position:absolute;left:{tx}px;top:{y}px;'
                f'width:{each_w}px;height:{BAR_H}px;background:{bar_color};'
                f'border:1px solid var(--node-border,var(--card-border));'
                f'border-radius:4px;box-sizing:border-box;"></div>'
            )
        y += BAR_H + ROW_GAP
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: timeline ──────────────────────────────────────────────────────────────

def _layout_timeline(src: str, direction: str, width_hint: int) -> str:
    """timeline: periods/events as nodes on a horizontal axis."""
    content_lines = _directive_content(src)
    title = ""
    sections: list[dict] = []
    current: Optional[dict] = None
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line.lower().startswith("title "):
            title = line[6:].strip(); continue
        if line.lower().startswith("section "):
            continue
        if not raw.startswith((" ", "\t")) or current is None:
            current = {"period": line, "events": []}
            sections.append(current)
        else:
            current["events"].append(line)
    if not sections:
        raise ValueError("No periods found in timeline.")

    PAD_H, PAD_V = 40, 32
    ITEM_W, ITEM_H, ITEM_GAP = 140, 64, 12
    canvas_w = width_hint or max(400, PAD_H * 2 + len(sections) * (ITEM_W + ITEM_GAP) - ITEM_GAP)
    step = (canvas_w - PAD_H * 2) // max(len(sections), 1)
    axis_y = PAD_V + (28 if title else 0) + ITEM_H + 12
    canvas_h = axis_y + PAD_V + 8

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    if title:
        parts.append(
            f'<div style="position:absolute;left:{PAD_H}px;top:{PAD_V}px;'
            f'font-size:13px;font-weight:700;color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));">{_h(title)}</div>'
        )
    ty = PAD_V + (28 if title else 0)
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    ax1 = PAD_H + ITEM_W // 2
    ax2 = canvas_w - PAD_H - ITEM_W // 2
    parts.append(
        f'<line x1="{ax1}" y1="{axis_y}" x2="{ax2}" y2="{axis_y}" '
        f'stroke="var(--edge,var(--card-border))" stroke-width="1.5"/>'
    )
    parts.append('</svg>')
    for i, sec in enumerate(sections):
        ix = PAD_H + i * step + step // 2 - ITEM_W // 2
        parts.append(
            f'<div class="node node-rect" style="position:absolute;left:{ix}px;top:{ty}px;'
            f'width:{ITEM_W}px;padding:6px 8px;box-sizing:border-box;'
            f'border:1px solid var(--node-border,var(--card-border));'
            f'border-radius:var(--node-radius,8px);'
            f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from)),'
            f'var(--node-bg-to,var(--card-bg-to)));"><span class="node-label" style="'
            f'display:block;font-size:12px;font-weight:700;'
            f'color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));">{_h(sec["period"])}</span>'
        )
        for ev in sec["events"][:2]:
            parts.append(
                f'<span style="display:block;font-size:10px;'
                f'color:var(--node-fg-dim,var(--text-secondary));'
                f'font-family:var(--label-font,var(--font-primary));">{_h(ev)}</span>'
            )
        parts.append('</div>')
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: quadrantChart ─────────────────────────────────────────────────────────

_QUAD_POINT_RE = re.compile(r'^(.+?)\s*:\s*\[([0-9.]+)\s*,\s*([0-9.]+)\]')


def _layout_quadrant(src: str, direction: str, width_hint: int) -> str:
    """quadrantChart: 2×2 fixed grid with plotted data points."""
    content_lines = _directive_content(src)
    title = ""
    x_labels = ("Low", "High")
    y_labels = ("Low", "High")
    quad_labels: dict[str, str] = {}
    points: list[dict] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        low = line.lower()
        if low.startswith("title "):
            title = line[6:].strip(); continue
        if low.startswith("x-axis "):
            ps = line[7:].split("-->")
            x_labels = (ps[0].strip(), ps[1].strip() if len(ps) > 1 else "High"); continue
        if low.startswith("y-axis "):
            ps = line[7:].split("-->")
            y_labels = (ps[0].strip(), ps[1].strip() if len(ps) > 1 else "High"); continue
        m = re.match(r'quadrant-([1-4])\s+(.*)', line, re.I)
        if m:
            quad_labels[m.group(1)] = m.group(2).strip(); continue
        m = _QUAD_POINT_RE.match(line)
        if m:
            points.append({"name": m.group(1).strip(), "x": float(m.group(2)), "y": float(m.group(3))})

    PAD = 48
    canvas_w = width_hint or 480
    canvas_h = max(320, canvas_w * 3 // 4)
    gx = PAD + 24
    gy = PAD + (24 if title else 0)
    gw = canvas_w - gx - PAD
    gh = canvas_h - gy - PAD - 24
    mx, my = gx + gw // 2, gy + gh // 2

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    if title:
        parts.append(
            f'<div style="position:absolute;left:{gx}px;top:{PAD}px;'
            f'font-size:12px;font-weight:700;color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));">{_h(title)}</div>'
        )
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    parts.append(
        f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" '
        f'fill="none" stroke="var(--edge,var(--card-border))" stroke-width="1.5"/>'
        f'<line x1="{mx}" y1="{gy}" x2="{mx}" y2="{gy + gh}" '
        f'stroke="var(--edge,var(--card-border))" stroke-width="1" stroke-dasharray="4 3"/>'
        f'<line x1="{gx}" y1="{my}" x2="{gx + gw}" y2="{my}" '
        f'stroke="var(--edge,var(--card-border))" stroke-width="1" stroke-dasharray="4 3"/>'
    )
    for pt in points:
        px = gx + int(pt["x"] * gw)
        py = gy + gh - int(pt["y"] * gh)
        r = 5
        poly = " ".join(
            f"{px + int(r * math.cos(math.pi * 2 * k / 8))},"
            f"{py + int(r * math.sin(math.pi * 2 * k / 8))}"
            for k in range(8)
        )
        parts.append(f'<polygon points="{poly}" fill="var(--edge-strong,var(--accent-1))"/>')
    parts.append('</svg>')
    for qid, qlbl in quad_labels.items():
        qx = (mx + 8) if qid in ("1",) else (gx + 8)
        qy = (gy + 8) if qid in ("1", "2") else (my + 8)
        parts.append(
            f'<span style="position:absolute;left:{qx}px;top:{qy}px;'
            f'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;'
            f'color:var(--node-fg-dim,var(--text-secondary));'
            f'font-family:var(--label-font,var(--font-primary));">{_h(qlbl)}</span>'
        )
    parts.append(
        f'<span style="position:absolute;left:{gx}px;top:{gy + gh + 6}px;'
        f'font-size:10px;color:var(--node-fg-dim,var(--text-secondary));'
        f'font-family:var(--label-font,var(--font-primary));">{_h(x_labels[0])}</span>'
        f'<span style="position:absolute;right:{PAD}px;top:{gy + gh + 6}px;'
        f'font-size:10px;color:var(--node-fg-dim,var(--text-secondary));'
        f'font-family:var(--label-font,var(--font-primary));">{_h(x_labels[1])}</span>'
    )
    for pt in points:
        px = gx + int(pt["x"] * gw)
        py = gy + gh - int(pt["y"] * gh)
        parts.append(
            f'<span style="position:absolute;left:{px + 8}px;top:{py - 8}px;'
            f'font-size:10px;color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));white-space:nowrap;">'
            f'{_h(pt["name"])}</span>'
        )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: pie ───────────────────────────────────────────────────────────────────

_PIE_SLICE_RE = re.compile(r'^"([^"]+)"\s*:\s*([0-9.]+)')


def _layout_pie(src: str, direction: str, width_hint: int) -> str:
    """pie/pie showData: polygon-approximated donut sectors."""
    content_lines = _directive_content(src)
    title = ""
    slices: list[dict] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line.lower().startswith("title "):
            title = line[6:].strip(); continue
        m = _PIE_SLICE_RE.match(line)
        if m:
            slices.append({"label": m.group(1), "value": float(m.group(2))})
    if not slices:
        raise ValueError("No slices found in pie chart.")

    total = sum(s["value"] for s in slices)
    if total <= 0:
        raise ValueError("Pie chart: all slice values are zero (nothing to render).")

    canvas_w = width_hint or 400
    canvas_h = canvas_w
    cx, cy = canvas_w // 2, canvas_h // 2
    r_out = min(cx, cy) - 60
    r_in = r_out * 2 // 5
    accents = [
        "var(--edge-strong,var(--accent-1))",
        "var(--node-accent-2,var(--accent-2))",
        "var(--node-border,var(--card-border))",
        "var(--node-fg-dim,var(--text-secondary))",
    ]
    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    angle = -math.pi / 2
    for i, sl in enumerate(slices):
        sweep = (sl["value"] / total) * 2 * math.pi
        end_a = angle + sweep
        color = accents[i % len(accents)]
        n_steps = max(3, int(16 * sweep / (2 * math.pi)))
        pts: list[str] = []
        for k in range(n_steps + 1):
            a = end_a - k * sweep / n_steps
            pts.append(f"{cx + int(r_in * math.cos(a))},{cy + int(r_in * math.sin(a))}")
        for k in range(n_steps + 1):
            a = angle + k * sweep / n_steps
            pts.append(f"{cx + int(r_out * math.cos(a))},{cy + int(r_out * math.sin(a))}")
        parts.append(
            f'<polygon points="{" ".join(pts)}" fill="{color}" '
            f'stroke="var(--node-bg-from,var(--card-bg-from))" stroke-width="2"/>'
        )
        angle = end_a
    parts.append('</svg>')
    angle = -math.pi / 2
    for sl in slices:
        sweep = (sl["value"] / total) * 2 * math.pi
        mid_a = angle + sweep / 2
        lr = r_out + 28
        lx = cx + int(lr * math.cos(mid_a))
        ly = cy + int(lr * math.sin(mid_a))
        pct = f"{sl['value'] / total * 100:.0f}%"
        parts.append(
            f'<span style="position:absolute;left:{lx - 30}px;top:{ly - 8}px;'
            f'width:60px;font-size:10px;text-align:center;'
            f'color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));white-space:nowrap;">'
            f'{_h(sl["label"])} {pct}</span>'
        )
        angle += sweep
    if title:
        parts.append(
            f'<div style="position:absolute;left:0;bottom:8px;width:{canvas_w}px;'
            f'text-align:center;font-size:12px;font-weight:700;'
            f'color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));">{_h(title)}</div>'
        )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: xychart-beta ──────────────────────────────────────────────────────────

def _layout_xychart(src: str, direction: str, width_hint: int) -> str:
    """xychart-beta: bar/line chart with axes."""
    content_lines = _directive_content(src)
    title = ""
    x_cats: list[str] = []
    y_range = (0.0, 100.0)
    bar_data: list[float] = []
    line_data: list[float] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        low = line.lower()
        if low.startswith("title "):
            title = line[6:].strip(); continue
        m = re.match(r'x-axis\s+(?:\[(.+)\]|"(.+)")', line, re.I)
        if m:
            cats = m.group(1) or m.group(2) or ""
            x_cats = [c.strip().strip('"') for c in cats.split(",") if c.strip()]; continue
        m = re.match(r'y-axis\s+\[?([0-9.]+)\s*-->\s*([0-9.]+)\]?', line, re.I)
        if m:
            y_range = (float(m.group(1)), float(m.group(2))); continue
        m = re.match(r'bar\s+\[(.+)\]', line, re.I)
        if m:
            bar_data = [float(v.strip()) for v in m.group(1).split(",") if v.strip()]; continue
        m = re.match(r'line\s+\[(.+)\]', line, re.I)
        if m:
            line_data = [float(v.strip()) for v in m.group(1).split(",") if v.strip()]
    data = bar_data or line_data
    if not data:
        raise ValueError("No data found in xychart-beta.")

    PAD_H, PAD_V, AXIS_W = 48, 32, 32
    canvas_w = width_hint or 480
    canvas_h = 300
    cx_start = PAD_H + AXIS_W
    cy_top = PAD_V + (20 if title else 0)
    cw = canvas_w - cx_start - PAD_H
    ch = canvas_h - cy_top - PAD_V - 24
    y_min, y_max = y_range
    y_span = (y_max - y_min) or 1.0
    n = len(data)
    bar_unit = cw // n

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
        f'<line x1="{cx_start}" y1="{cy_top}" x2="{cx_start}" y2="{cy_top + ch}" '
        f'stroke="var(--edge,var(--card-border))" stroke-width="1.5"/>'
        f'<line x1="{cx_start}" y1="{cy_top + ch}" x2="{cx_start + cw}" y2="{cy_top + ch}" '
        f'stroke="var(--edge,var(--card-border))" stroke-width="1.5"/>'
    )
    if line_data and not bar_data:
        pts_coords = []
        for i, v in enumerate(line_data):
            bx = cx_start + i * bar_unit + bar_unit // 2
            by = cy_top + ch - int(max(0.0, min(1.0, (v - y_min) / y_span)) * ch)
            pts_coords.append((bx, by))
        for i in range(len(pts_coords) - 1):
            x1, y1a = pts_coords[i]; x2, y2a = pts_coords[i + 1]
            parts.append(
                f'<line x1="{x1}" y1="{y1a}" x2="{x2}" y2="{y2a}" '
                f'stroke="var(--edge-strong,var(--accent-1))" stroke-width="2"/>'
            )
        for bx, by in pts_coords:
            r = 4
            poly = " ".join(
                f"{bx + int(r * math.cos(math.pi * k / 3))},"
                f"{by + int(r * math.sin(math.pi * k / 3))}"
                for k in range(6)
            )
            parts.append(f'<polygon points="{poly}" fill="var(--edge-strong,var(--accent-1))"/>')
    parts.append('</svg>')
    if bar_data:
        bar_w = max(8, bar_unit - 8)
        for i, v in enumerate(bar_data):
            norm = max(0.0, min(1.0, (v - y_min) / y_span))
            bh = max(4, int(norm * ch))
            bx = cx_start + i * bar_unit + (bar_unit - bar_w) // 2
            by = cy_top + ch - bh
            parts.append(
                f'<div style="position:absolute;left:{bx}px;top:{by}px;'
                f'width:{bar_w}px;height:{bh}px;'
                f'background:var(--edge-strong,var(--accent-1));'
                f'border-radius:2px 2px 0 0;box-sizing:border-box;"></div>'
            )
            cat = x_cats[i] if i < len(x_cats) else str(i + 1)
            parts.append(
                f'<span style="position:absolute;'
                f'left:{bx - (bar_unit - bar_w) // 2}px;top:{cy_top + ch + 4}px;'
                f'width:{bar_unit}px;font-size:10px;text-align:center;'
                f'color:var(--node-fg-dim,var(--text-secondary));'
                f'font-family:var(--label-font,var(--font-primary));">'
                f'{_h(cat)}</span>'
            )
    if title:
        parts.append(
            f'<div style="position:absolute;left:{cx_start}px;top:{PAD_V}px;'
            f'font-size:12px;font-weight:700;color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));">{_h(title)}</div>'
        )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: mindmap ───────────────────────────────────────────────────────────────

def _layout_mindmap(src: str, direction: str, width_hint: int) -> str:
    """mindmap: indented tree layout, root at top."""
    content_lines = _directive_content(src)
    flat: list[dict] = []
    for raw in content_lines:
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith(("%%", "//")):
            continue
        indent = len(line) - len(line.lstrip())
        lbl = re.sub(r'^[\[\(\{:]+|[\]\)\}]+$', '', line.strip()).strip()
        if lbl:
            flat.append({"depth": indent, "label": lbl})
    if not flat:
        raise ValueError("No nodes found in mindmap.")

    # Normalize depths
    min_d = min(n["depth"] for n in flat)
    for n in flat:
        n["depth"] -= min_d

    PAD_H, PAD_V = 40, 24
    NODE_H_MM, NODE_GAP, INDENT_W = 32, 8, 24
    canvas_w = width_hint or 480
    canvas_h = PAD_V * 2 + len(flat) * (NODE_H_MM + NODE_GAP)

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    parts.append(
        f'<svg style="position:absolute;inset:0;width:{canvas_w}px;height:{canvas_h}px;'
        f'overflow:visible;pointer-events:none;">'
    )
    y_pos: list[int] = []
    for i, n in enumerate(flat):
        ny = PAD_V + i * (NODE_H_MM + NODE_GAP) + NODE_H_MM // 2
        nx = PAD_H + n["depth"] * INDENT_W
        y_pos.append(ny)
        if i > 0:
            for j in range(i - 1, -1, -1):
                if flat[j]["depth"] < n["depth"]:
                    pnx = PAD_H + flat[j]["depth"] * INDENT_W + 120
                    parts.append(
                        f'<line x1="{pnx}" y1="{y_pos[j]}" x2="{nx}" y2="{ny}" '
                        f'stroke="var(--edge,var(--card-border))" stroke-width="1"/>'
                    )
                    break
    parts.append('</svg>')
    for i, n in enumerate(flat):
        ny = PAD_V + i * (NODE_H_MM + NODE_GAP)
        nx = PAD_H + n["depth"] * INDENT_W
        bold = "font-weight:700;" if n["depth"] == 0 else ""
        bg = (f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from)),'
              f'var(--node-bg-to,var(--card-bg-to)));'
              f'border:1px solid var(--node-border,var(--card-border));') if n["depth"] == 0 else ""
        parts.append(
            f'<div class="node" style="position:absolute;left:{nx}px;top:{ny}px;'
            f'min-width:120px;height:{NODE_H_MM}px;display:flex;align-items:center;'
            f'padding:4px 8px;box-sizing:border-box;border-radius:var(--node-radius,8px);{bg}">'
            f'<span class="node-label" style="font-size:13px;{bold}'
            f'color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));">'
            f'{_h(n["label"])}</span></div>'
        )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: block-beta ────────────────────────────────────────────────────────────

_BLOCK_ID_RE = re.compile(r'(\w+)(?:\["([^"]+)"\])?(?::(\d+))?')


def _layout_block(src: str, direction: str, width_hint: int) -> str:
    """block-beta: blocks in declared rows/columns."""
    content_lines = _directive_content(src)
    rows: list[list[dict]] = []
    current_row: list[dict] = []
    n_cols = 3
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m = re.match(r'columns\s+(\d+)', line, re.I)
        if m:
            n_cols = int(m.group(1)); continue
        for token in line.split():
            m2 = _BLOCK_ID_RE.match(token)
            if m2 and m2.group(1) not in ("space", "classDef", "class"):
                current_row.append({
                    "id": m2.group(1),
                    "label": m2.group(2) or m2.group(1),
                    "span": int(m2.group(3)) if m2.group(3) else 1,
                })
                if len(current_row) >= n_cols:
                    rows.append(current_row); current_row = []
    if current_row:
        rows.append(current_row)
    if not rows:
        raise ValueError("No blocks found in block-beta.")

    PAD_H, PAD_V, CELL_W, CELL_H, CELL_GAP = 40, 24, 120, 56, 8
    canvas_w = width_hint or PAD_H * 2 + n_cols * CELL_W + (n_cols - 1) * CELL_GAP
    canvas_h = PAD_V * 2 + len(rows) * (CELL_H + CELL_GAP) - CELL_GAP

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    for ri, row in enumerate(rows):
        ry = PAD_V + ri * (CELL_H + CELL_GAP)
        cx_cur = PAD_H
        for blk in row:
            bw = CELL_W * blk["span"] + CELL_GAP * (blk["span"] - 1)
            parts.append(
                f'<div class="node node-rect" style="position:absolute;'
                f'left:{cx_cur}px;top:{ry}px;width:{bw}px;height:{CELL_H}px;'
                f'display:flex;align-items:center;justify-content:center;'
                f'border:1px solid var(--node-border,var(--card-border));'
                f'border-radius:var(--node-radius,8px);box-sizing:border-box;'
                f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from)),'
                f'var(--node-bg-to,var(--card-bg-to)));"><span class="node-label" style="'
                f'font-size:13px;font-weight:700;color:var(--node-fg,var(--text-primary));'
                f'font-family:var(--label-font,var(--font-primary));text-align:center;">'
                f'{_h(blk["label"])}</span></div>'
            )
            cx_cur += bw + CELL_GAP
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: packet-beta ───────────────────────────────────────────────────────────

_PKT_FIELD_RE = re.compile(r'^(\d+)(?:-(\d+))?\s*:\s*(.+)$')


def _layout_packet(src: str, direction: str, width_hint: int) -> str:
    """packet-beta: fixed-width bit-field cells."""
    content_lines = _directive_content(src)
    fields: list[dict] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m = _PKT_FIELD_RE.match(line)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            if start < 0 or end < start:
                raise ValueError(
                    f"packet-beta: invalid bit range {start}-{end} "
                    f"(start must be ≥ 0, end must be ≥ start)."
                )
            fields.append({"start": start, "end": end,
                           "bits": end - start + 1, "label": m.group(3).strip()})
    if not fields:
        raise ValueError("No fields found in packet-beta.")

    total_bits = max(f["end"] for f in fields) + 1
    PAD_H, PAD_V, CELL_H = 40, 40, 56
    canvas_w = width_hint or 640
    available_w = canvas_w - PAD_H * 2
    bit_w = available_w / max(total_bits, 1)
    canvas_h = PAD_V * 2 + CELL_H + 20

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    for fld in fields:
        fx = PAD_H + int(fld["start"] * bit_w)
        fw = max(1, int(fld["bits"] * bit_w) - 1)
        parts.append(
            f'<div class="node node-rect" style="position:absolute;'
            f'left:{fx}px;top:{PAD_V}px;width:{fw}px;height:{CELL_H}px;'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'border:1px solid var(--node-border,var(--card-border));'
            f'box-sizing:border-box;'
            f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from)),'
            f'var(--node-bg-to,var(--card-bg-to)));"><span class="node-label" style="'
            f'font-size:11px;font-weight:700;color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));text-align:center;">'
            f'{_h(fld["label"])}</span>'
            f'<span style="font-size:9px;color:var(--node-fg-dim,var(--text-secondary));'
            f'font-family:var(--label-font,var(--font-primary));">'
            f'{fld["start"]}{"–" + str(fld["end"]) if fld["end"] != fld["start"] else ""}'
            f'</span></div>'
        )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: kanban ────────────────────────────────────────────────────────────────

def _layout_kanban(src: str, direction: str, width_hint: int) -> str:
    """kanban: cards stacked in labeled vertical columns."""
    content_lines = _directive_content(src)
    # Find minimum indentation level — that is the column header depth
    min_indent = 9999
    for raw in content_lines:
        if raw.strip() and not raw.strip().startswith(("%%", "//")):
            min_indent = min(min_indent, len(raw) - len(raw.lstrip()))
    if min_indent == 9999:
        min_indent = 0
    columns: list[dict] = []
    current_col: Optional[dict] = None
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent == min_indent:
            col_name = re.sub(r'@\{[^}]*\}', '', line).strip()
            current_col = {"name": col_name, "cards": []}
            columns.append(current_col)
        elif current_col is not None:
            card = re.sub(r'@\{[^}]*\}', '', line).strip()
            if card:
                current_col["cards"].append(card)
    if not columns:
        raise ValueError("No columns found in kanban.")

    PAD_H, PAD_V = 24, 24
    COL_W, COL_GAP, HDR_H, CARD_H, CARD_GAP = 160, 12, 36, 44, 6
    max_cards = max((len(c["cards"]) for c in columns), default=0)
    canvas_w = width_hint or PAD_H * 2 + len(columns) * (COL_W + COL_GAP) - COL_GAP
    canvas_h = PAD_V * 2 + HDR_H + max_cards * (CARD_H + CARD_GAP)

    parts: list[str] = []
    parts.append(
        f'<div class="diagram mermaid-layout" style="'
        f'position:relative;width:{canvas_w}px;height:{canvas_h}px;">'
    )
    for ci, col in enumerate(columns):
        cx = PAD_H + ci * (COL_W + COL_GAP)
        parts.append(
            f'<div style="position:absolute;left:{cx}px;top:{PAD_V}px;'
            f'width:{COL_W}px;height:{HDR_H}px;'
            f'display:flex;align-items:center;justify-content:center;'
            f'border-bottom:2px solid var(--edge-strong,var(--accent-1));'
            f'box-sizing:border-box;">'
            f'<span style="font-size:12px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.08em;color:var(--node-fg,var(--text-primary));'
            f'font-family:var(--label-font,var(--font-primary));">'
            f'{_h(col["name"])}</span></div>'
        )
        for ki, card in enumerate(col["cards"]):
            ky = PAD_V + HDR_H + ki * (CARD_H + CARD_GAP) + 8
            parts.append(
                f'<div class="node node-rect" style="position:absolute;'
                f'left:{cx}px;top:{ky}px;width:{COL_W}px;height:{CARD_H}px;'
                f'display:flex;align-items:center;padding:6px 10px;'
                f'border:1px solid var(--node-border,var(--card-border));'
                f'border-radius:var(--node-radius,8px);box-sizing:border-box;'
                f'background:linear-gradient(180deg,var(--node-bg-from,var(--card-bg-from)),'
                f'var(--node-bg-to,var(--card-bg-to)));"><span class="node-label" style="'
                f'font-size:12px;color:var(--node-fg,var(--text-primary));'
                f'font-family:var(--label-font,var(--font-primary));overflow:hidden;'
                f'text-overflow:ellipsis;white-space:nowrap;">'
                f'{_h(card)}</span></div>'
            )
    parts.append('</div>')
    return "\n".join(parts)


# ── T3: architecture-beta ─────────────────────────────────────────────────────

_ARCH_SVC_RE = re.compile(
    r'^service\s+(\w+)\s*(?:\(([^)]*)\))?\s*\[([^\]]+)\](?:\s+in\s+(\w+))?', re.I
)
_ARCH_GRP_RE = re.compile(
    r'^(?:group|junction)\s+(\w+)\s*(?:\([^)]*\))?\s*(?:\[([^\]]+)\])?', re.I
)
_ARCH_EDGE_RE = re.compile(
    r'^(\w+)(?::\w+)?\s*(?:-->|<-->|--)\s*(\w+)(?::\w+)?(?:\s*:\s*(.*))?$'
)


def _layout_architecture(src: str, direction: str, width_hint: int) -> str:
    """architecture-beta: zone containers with service nodes and edges."""
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    groups: dict[str, _Group] = {}
    edges: list[_Edge] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m = _ARCH_SVC_RE.match(line)
        if m:
            sid = m.group(1)
            icon_hint = (m.group(2) or "").lower().strip()
            lbl = m.group(3)
            gin = m.group(4)
            icon_name = _ARCH_ICON_MAP.get(icon_hint, "")
            nodes[sid] = _Node(id=sid, label=lbl, shape="rect",
                               group=gin if gin else None, icon=icon_name)
            if gin:
                groups.setdefault(gin, _Group(id=gin, label=gin, members=[]))
                if sid not in groups[gin].members:
                    groups[gin].members.append(sid)
            continue
        m = _ARCH_GRP_RE.match(line)
        if m:
            gid, glbl = m.group(1), m.group(2) or m.group(1)
            if gid not in groups:
                groups[gid] = _Group(id=gid, label=glbl, members=[])
            else:
                groups[gid].label = glbl
            continue
        m = _ARCH_EDGE_RE.match(line)
        if m:
            edges.append(_Edge(src=m.group(1), dst=m.group(2),
                               label=(m.group(3) or "").strip(), style="solid", arrow=True))
    if not nodes:
        raise ValueError("No services found in architecture-beta.")
    return _graph_from_content_nodes(nodes, edges, groups, width_hint)


# ── T3: C4 diagrams ──────────────────────────────────────────────────────────

_C4_ELEM_RE = re.compile(
    r'^(Person|System|Container|Component|SystemDb|ContainerDb|'
    r'Person_Ext|System_Ext|Container_Ext)\s*'
    r'\(\s*(\w+)\s*,\s*"([^"]+)"', re.I
)
_C4_BOUNDARY_RE = re.compile(
    r'^(?:Enterprise_Boundary|System_Boundary|Container_Boundary|Boundary)'
    r'\s*\(\s*(\w+)\s*,\s*"([^"]+)"', re.I
)
_C4_REL_RE = re.compile(
    r'^(?:Rel|Rel_D|Rel_U|Rel_L|Rel_R|BiRel)\s*'
    r'\(\s*(\w+)\s*,\s*(\w+)\s*,\s*"([^"]*)"', re.I
)


def _layout_c4(src: str, direction: str, width_hint: int) -> str:
    """C4Context/C4Container/C4Component: boundary boxes + nodes + relationships."""
    content_lines = _directive_content(src)
    nodes: dict[str, _Node] = {}
    groups: dict[str, _Group] = {}
    edges: list[_Edge] = []
    boundary_stack: list[str] = []
    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        m = _C4_BOUNDARY_RE.match(line)
        if m:
            bid, blbl = m.group(1), m.group(2)
            groups.setdefault(bid, _Group(id=bid, label=blbl, members=[]))
            boundary_stack.append(bid); continue
        if line.startswith(")") and boundary_stack:
            boundary_stack.pop(); continue
        m = _C4_ELEM_RE.match(line)
        if m:
            elem_type = m.group(1).lower()
            eid, elbl = m.group(2), m.group(3)
            shape = "circle" if "person" in elem_type else "rect"
            icon_name = _C4_ICON_MAP.get(elem_type, "node")
            gin = boundary_stack[-1] if boundary_stack else None
            nodes[eid] = _Node(id=eid, label=elbl, shape=shape,
                               group=gin, icon=icon_name)
            if gin:
                groups.setdefault(gin, _Group(id=gin, label=gin, members=[]))
                if eid not in groups[gin].members:
                    groups[gin].members.append(eid)
            continue
        m = _C4_REL_RE.match(line)
        if m:
            edges.append(_Edge(src=m.group(1), dst=m.group(2),
                               label=m.group(3), style="solid", arrow=True))
    if not nodes:
        raise ValueError("No elements found in C4 diagram.")
    return _graph_from_content_nodes(nodes, edges, groups, width_hint)


# ── strategy dispatch ─────────────────────────────────────────────────────────

def _dispatch(src: str, direction_override: Optional[str], width_hint: int) -> str:
    """Detect directive, dispatch to per-type strategy, return HTML fragment."""
    clean = _strip_frontmatter(src)
    directive, auto_direction = _detect_directive(clean)
    direction = (direction_override or auto_direction).upper()
    d = directive.lower()

    if d in _GRAPH_DIRECTIVES:
        return _layout_graph_topology(clean, direction, width_hint)
    if d == "sequencediagram":
        return _layout_lifeline(clean, direction, width_hint)
    if d == "erdiagram":
        return _layout_er(clean, direction, width_hint)
    if d == "classdiagram":
        return _layout_class(clean, direction, width_hint)
    if d == "gantt":
        return _layout_gantt(clean, direction, width_hint)
    if d == "timeline":
        return _layout_timeline(clean, direction, width_hint)
    if d == "quadrantchart":
        return _layout_quadrant(clean, direction, width_hint)
    if d == "pie" or d.startswith("pie "):
        return _layout_pie(clean, direction, width_hint)
    if d == "xychart-beta":
        return _layout_xychart(clean, direction, width_hint)
    if d == "mindmap":
        return _layout_mindmap(clean, direction, width_hint)
    if d == "block-beta":
        return _layout_block(clean, direction, width_hint)
    if d == "packet-beta":
        return _layout_packet(clean, direction, width_hint)
    if d == "kanban":
        return _layout_kanban(clean, direction, width_hint)
    if d == "architecture-beta":
        return _layout_architecture(clean, direction, width_hint)
    if d in ("c4context", "c4container", "c4component"):
        return _layout_c4(clean, direction, width_hint)

    # Unknown directive — graph-topology best-effort fallback
    try:
        return _layout_graph_topology(clean, direction, width_hint)
    except Exception:
        raise ValueError(f"Unsupported or unrecognised Mermaid directive: '{directive}'")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Render Mermaid source to pipeline-safe HTML/CSS fragment."
    )
    ap.add_argument(
        "--source", required=True,
        help="Mermaid source string, or @path to read from file (e.g. @diagram.mmd).",
    )
    ap.add_argument(
        "--direction", choices=["TB", "LR", "RL", "BT"], default=None,
        help="Override graph direction (default: from source directive).",
    )
    ap.add_argument(
        "--width-hint", type=int, default=0, metavar="N",
        help="Target canvas width hint in px; script scales to fit.",
    )
    ap.add_argument(
        "--output", default=None, metavar="FILE",
        help="Write HTML fragment to FILE (default: stdout).",
    )
    args = ap.parse_args()

    # Resolve source
    src_arg: str = args.source
    if src_arg.startswith("@"):
        fpath = Path(src_arg[1:])
        try:
            src = fpath.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"mermaid_layout: cannot read source file: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        src = src_arg.replace("\\n", "\n")

    try:
        fragment = _dispatch(src, args.direction, args.width_hint)
    except RecursionError:
        print("mermaid_layout: diagram too deeply nested (recursion limit)", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"mermaid_layout: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(fragment, encoding="utf-8")
    else:
        print(fragment)


if __name__ == "__main__":
    main()
