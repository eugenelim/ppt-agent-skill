from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── icon loader ───────────────────────────────────────────────────────────────

_ICON_DIR = Path(__file__).parent.parent.parent / "assets" / "icons"
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
NODE_H = 56       # base height for a single-line node (see _node_render_h formula below)
RANK_GAP = 72    # gap in flow direction (vertical in TB, horizontal in LR)
COL_GAP = 48     # gap perpendicular to flow (horizontal in TB, vertical in LR)
CANVAS_PAD = 48  # outer inset on all sides
GROUP_PAD_X = 24  # group container horizontal inner padding
GROUP_PAD_Y_TOP = 32  # group container top inner padding (room for label)
GROUP_PAD_Y_BOT = 24  # group container bottom inner padding

# Node height composition — single source of truth used by _node_render_h:
#   NODE_H          = base (padding + one text line)
#   _NODE_H_LINE    = added per extra text line beyond the first
#   _NODE_H_ICON    = icon block (20px icon + 4px margin) added when icon resolves
#   _NODE_H_TECH    = tech sub-label line (11px × 1.4 ≈ 16px)
# All extra_h components are ADDITIVE (not max) so icon + multiline nodes size correctly.
_NODE_H_LINE = 20   # px per additional text line (14px font × 1.4 line-height)
_NODE_H_ICON = 24   # icon box: 20px SVG + 4px bottom margin
_NODE_H_TECH = 16   # tech sub-label line height
SELF_LOOP_DX = 28  # horizontal reach of self-loop arc
MIN_FAN_STEP = 12  # minimum px between adjacent fan endpoints on a node edge

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



_WRAP_CHARS = 18  # label wrap threshold (~120px usable at 7px/char, NODE_W=160 minus 40px padding)


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
    # Split on spaces first; for hyphen-compound words, also split at hyphens
    # so long kebab-case identifiers (e.g. express-ai-knowledge-source-enterprise-it)
    # break at natural boundaries instead of at arbitrary char positions.
    raw_words = normalized.split()
    words: list[str] = []
    for w in raw_words:
        if len(w) > _WRAP_CHARS and "-" in w:
            parts = w.split("-")
            acc = parts[0]
            for p in parts[1:]:
                candidate = acc + "-" + p
                if len(candidate) <= _WRAP_CHARS:
                    acc = candidate
                else:
                    words.append(acc + "-")
                    acc = p
            words.append(acc)
        else:
            words.append(w)
    lines: list[str] = []
    cur = ""
    for w in words:
        # Break individual tokens that still exceed the wrap limit
        while len(w) > _WRAP_CHARS:
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(w[:_WRAP_CHARS])
            w = w[_WRAP_CHARS:]
        if cur and len(cur) + 1 + len(w) > _WRAP_CHARS:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [normalized]


def _split_sub_label(label: str) -> tuple[str, str]:
    """Split a node label into (main, sub) parts.

    The convention is: label lines before the first [bracketed line] are main;
    the bracketed portion (stripped of outer brackets) is the sub-label.
    E.g. "Service name\\n[Tech stack]" → ("Service name", "Tech stack").
    """
    normalized = label.replace("\\n", "\n")
    if "\n" not in normalized:
        return label, ""
    chunks = [c.strip() for c in normalized.split("\n") if c.strip()]
    main_parts, sub_parts = [], []
    in_sub = False
    for chunk in chunks:
        if not in_sub and chunk.startswith("[") and chunk.endswith("]"):
            in_sub = True
            sub_parts.append(chunk[1:-1].strip())
        elif in_sub:
            sub_parts.append(chunk)
        else:
            main_parts.append(chunk)
    main = "\n".join(main_parts) if main_parts else label
    sub = " ".join(sub_parts)
    return main, sub


def _node_render_h(n: "_Node") -> int:
    """Return the rendered pixel height of node n (single source of truth).

    Mirrors the height calculation in _render_graph_fragment so that group
    bounding boxes, canvas height, and LR layout pitch all stay in sync.
    Uses n.icon and n.css_class (via _load_icon) to determine effective icon.
    """
    raw_label = n.label.split("|", 1)[0].strip() if "|" in n.label else n.label
    main_label, sub_label = _split_sub_label(raw_label)
    lines = _wrap_label(main_label)
    extra_h = max(0, (len(lines) - 1) * _NODE_H_LINE)
    if n.icon and _load_icon(n.icon):
        effective_icon = n.icon
    elif n.css_class and _load_icon(n.css_class):
        effective_icon = n.css_class
    else:
        effective_icon = ""
    if effective_icon:
        extra_h += _NODE_H_ICON  # additive: icon + multiple lines don't fight each other
    if "|" in n.label:
        extra_h += _NODE_H_TECH
    if sub_label:
        sub_lines = _wrap_label(sub_label)
        extra_h += len(sub_lines) * _NODE_H_LINE
    return NODE_H + extra_h

