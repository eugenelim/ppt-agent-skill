from __future__ import annotations

import re
from typing import Optional

from ._constants import (
    _Node, _Edge, _Group,
    _GRAPH_DIRECTIVES,
)

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
# Quoted variants (rect_q, round_q, cylinder_q) come first so that labels
# containing bracket characters — e.g. NODE["name\n[inner]"] — are matched
# by the quote-delimited form before the bracket-delimited fallback rejects them.
_SPEC_RE = re.compile(
    r'^(?P<id>[A-Za-z_][A-Za-z0-9_\-\.]*)'
    r'(?:'
    r'\[\("(?P<cylinder_q>[^"]*)"\)\]'   # [("quoted cylinder")]
    r'|\[\((?P<cylinder>[^\)]*)\)\]'     # [(unquoted cylinder)]
    r'|\(\((?P<circle>[^\)]*)\)\)'       # ((circle))
    r'|\["(?P<rect_q>[^"]*)"\]'          # ["quoted rect"]
    r'|\[(?P<rect>[^\[\]]*)\]'           # [unquoted rect]
    r'|\("(?P<round_q>[^"]*)"\)'         # ("quoted round")
    r'|\((?P<round>[^\(\)]*)\)'          # (unquoted round)
    r'|\{(?P<diamond>[^\{\}]*)\}'        # {diamond}
    r'|>(?P<flag>[^\]]*)\]'              # >flag]
    r')?'
)

# Maps _SPEC_RE group names → canonical shape names
_SPEC_SHAPE_MAP = {
    "cylinder_q": "cylinder", "cylinder": "cylinder",
    "circle": "circle",
    "rect_q": "rect", "rect": "rect",
    "round_q": "round", "round": "round",
    "diamond": "diamond",
    "flag": "flag",
}


def _parse_spec(spec: str) -> tuple[str, str, str]:
    """Return (id, label, shape) from node spec like A[Label]."""
    spec = spec.strip()
    m = _SPEC_RE.match(spec)
    if not m:
        safe = re.match(r'[A-Za-z_][A-Za-z0-9_\-\.]*', spec)
        nid = safe.group(0) if safe else spec
        return nid, nid, "rect"
    nid = m.group("id")
    for group_name, shape in _SPEC_SHAPE_MAP.items():
        val = m.group(group_name)
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
    r'|(?P<arrow_short>-\.->|-\.-o|-\.-x|-\.-|==>|-->|--o|--x|---)'  # plain operators (longer patterns first)
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
    edge_label = (m.group("mid_label") or m.group("pipe_label") or "").strip().strip('"\'')  # strip mermaid |"..."|  quotes

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


