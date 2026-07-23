from __future__ import annotations

import json
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


_INIT_RE = re.compile(r'%%\s*\{(.+?)\}\s*%%', re.DOTALL)


def _parse_mermaid_init_block(raw: str) -> dict:
    """Parse a %%{...}%% block body into a dict.

    Handles unquoted-key Mermaid format: init: {"flowchart": {...}}
    and standard JSON: {"init": {"flowchart": {...}}}.
    """
    raw = raw.strip()
    raw_dq = re.sub(r"'([^']*)'", r'"\1"', raw)
    # Try standard JSON
    try:
        obj = json.loads(raw_dq)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    # Mermaid's "init: {...}" format
    init_m = re.match(r'^init\s*:\s*(\{.+\})\s*$', raw_dq, re.DOTALL)
    if init_m:
        try:
            inner = json.loads(init_m.group(1))
            if isinstance(inner, dict):
                return {"init": inner}
        except (json.JSONDecodeError, ValueError):
            pass
    # Fallback: try wrapping
    try:
        obj = json.loads("{" + raw_dq + "}")
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    return {}


def _parse_init_config(src: str) -> dict[str, int]:
    """Extract layout overrides from %%{init:{...}}%% directives.

    Recognises flowchart config keys:
      nodeSpacing    → col_gap
      rankSpacing    → rank_gap
      diagramPadding → diagram_padding

    Ignores unknown keys and unparseable JSON.
    """
    overrides: dict[str, int] = {}
    for m in _INIT_RE.finditer(src):
        obj = _parse_mermaid_init_block(m.group(1))
        if not obj:
            continue
        fc = obj.get("flowchart") or obj.get("init", {}).get("flowchart", {})
        if isinstance(fc, dict):
            if "nodeSpacing" in fc:
                try:
                    overrides["col_gap"] = int(fc["nodeSpacing"])
                except (TypeError, ValueError):
                    pass
            if "rankSpacing" in fc:
                try:
                    overrides["rank_gap"] = int(fc["rankSpacing"])
                except (TypeError, ValueError):
                    pass
            if "diagramPadding" in fc:
                try:
                    overrides["diagram_padding"] = int(fc["diagramPadding"])
                except (TypeError, ValueError):
                    pass
    return overrides


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
    r'\[\("(?P<cylinder_q>[^"]*)"\)\]'           # [("quoted cylinder")]
    r'|\[\((?P<cylinder>[^\)]*)\)\]'             # [(unquoted cylinder)]
    r'|\(\(\((?P<doublecircle>[^\)]*)\)\)\)'     # (((doublecircle)))
    r'|\(\((?P<circle>[^\)]*)\)\)'               # ((circle))
    r'|\(\[(?P<stadium>[^\]]*)\]\)'              # ([stadium]) — pill/capsule shape
    r'|\["(?P<rect_q>[^"]*)"\]'                  # ["quoted rect"]
    r'|\[\\(?P<trapezoid_alt>[^\]]*)\\\]'        # [\trapezoid-alt\]
    r'|\[/(?P<trapezoid>[^/]*)/\]'               # [/trapezoid/]
    r'|\[\[(?P<subroutine>[^\]]*)\]\]'           # [[subroutine]]
    r'|\[(?P<rect>[^\[\]]*)\]'                   # [unquoted rect]
    r'|\("(?P<round_q>[^"]*)"\)'                 # ("quoted round")
    r'|\((?P<round>[^\(\)]*)\)'                  # (unquoted round)
    r'|\{\{(?P<hexagon>[^\}]*)\}\}'              # {{hexagon}}
    r'|\{(?P<diamond>[^\{\}]*)\}'                # {diamond}
    r'|>(?P<flag>[^\]]*)\]'                      # >flag]
    r')?'
)

# Maps _SPEC_RE group names → canonical shape names
_SPEC_SHAPE_MAP = {
    "cylinder_q": "cylinder", "cylinder": "cylinder",
    "doublecircle": "doublecircle",
    "circle": "circle",
    "stadium": "stadium",
    "rect_q": "rect", "rect": "rect",
    "trapezoid_alt": "trapezoid-alt",
    "trapezoid": "trapezoid",
    "subroutine": "subroutine",
    "round_q": "round", "round": "round",
    "hexagon": "hexagon",
    "diamond": "diamond",
    "flag": "flag",
}


# Mermaid v11 @{ shape: ... } attribute syntax — maps shape attribute values to
# canonical shape names.  Short aliases appear alongside the canonical names.
_AT_SHAPE_MAP: dict[str, str] = {
    "diam": "diamond", "diamond": "diamond", "rhombus": "diamond",
    "circle": "circle", "f-circ": "circle", "fork": "circle", "join": "circle",
    "rect": "rect", "rectangle": "rect", "notch-rect": "rect", "win-pane": "rect",
    "rounded": "round", "brace": "round", "brace-l": "round", "brace-r": "round",
    "stadium": "stadium", "pill": "stadium", "terminal": "stadium",
    "hex": "hexagon", "hexagon": "hexagon", "odd": "hexagon",
    "cyl": "cylinder", "cylinder": "cylinder", "lin-cyl": "cylinder",
    "subroutine": "subroutine",
    "trap-b": "trapezoid", "trapezoid": "trapezoid", "lean-r": "trapezoid",
    "trap-t": "trapezoid-alt", "lean-l": "trapezoid-alt",
    "doublecircle": "doublecircle",
    "flag": "flag",
}

# Regex for ID@{ key: value, ... } attribute block.
# Captures the node ID and the full attribute string for further key/value parsing.
_AT_BLOCK_RE = re.compile(
    r'^(?P<id>[A-Za-z_][A-Za-z0-9_\-\.]*)@\{(?P<attrs>[^}]*)\}'
)


def _parse_spec(spec: str) -> tuple[str, str, str]:
    """Return (id, label, shape) from node spec like A[Label].

    Also handles the Mermaid v11 @{ shape: ..., label: "..." } attribute syntax.
    """
    spec = spec.strip()
    # Mermaid v11 @{ } attribute syntax — check before bracket-based spec
    at_m = _AT_BLOCK_RE.match(spec)
    if at_m:
        nid = at_m.group("id")
        attrs_raw = at_m.group("attrs")
        shape = "rect"
        label = nid
        # Parse key: value pairs (comma-separated; values may be quoted)
        for kv in re.split(r',\s*', attrs_raw):
            kv = kv.strip()
            km = re.match(r'(\w[\w-]*)\s*:\s*"([^"]*)"', kv)
            if not km:
                km = re.match(r"(\w[\w-]*)\s*:\s*'([^']*)'", kv)
            if not km:
                km = re.match(r'(\w[\w-]*)\s*:\s*(\S+)', kv)
            if not km:
                continue
            key, val = km.group(1).lower(), km.group(2).strip().strip('"\'')
            if key == "shape":
                shape = _AT_SHAPE_MAP.get(val.lower(), "rect")
            elif key == "label":
                label = val
        return nid, label, shape

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
#   A <--> B  (bidirectional — produces a single edge with bidir=True)
_EDGE_RE = re.compile(
    r'^(?P<src_raw>.+?)\s*'
    r'(?:'
    r'--\s*(?P<mid_label>[^->=]+?)\s*(?P<arrow_long>-->|---)'   # -- text --> / -- text ---
    r'|(?P<arrow_short><-->|-\.->|-\.-o|-\.-x|-\.-|==>|-->|--o|--x|---)'  # <--> before --> (longer first)
    r')'
    r'\s*(?:\|(?P<pipe_label>[^\|]*)\|)?\s*'
    r'(?P<dst_raw>.+)$'
)


def _parse_graph_source(lines: list[str]) -> tuple[dict[str, _Node], list[_Edge], dict[str, _Group]]:
    nodes: dict[str, _Node] = {}
    edges: list[_Edge] = []
    groups: dict[str, _Group] = {}
    stack: list[str] = []  # subgraph id stack
    _pending_link_styles: list[tuple[int, str]] = []
    _composite_gids: set[str] = set()  # group IDs that are state diagram composite states
    _note_counter: int = 0
    _note_lines: list[str] = []
    _note_target: str = ""  # stateDiagram note: target state ID accumulating block

    _STATE_NOTE_INLINE = re.compile(r'^note\s+(?:right|left)\s+of\s+(\w+)\s*:\s*(.+)', re.I)
    _STATE_NOTE_OPEN = re.compile(r'^note\s+(?:right|left)\s+of\s+(\w+)\s*$', re.I)

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
        if line.startswith(("classDef ", "click ")):
            continue
        if line.startswith("style "):
            # `style NodeId fill:#f00,stroke:#333,color:#fff`
            _sm = re.match(r'^style\s+(\S+)\s+(.*)', line)
            if _sm:
                _snid, _scss = _sm.group(1), _sm.group(2).strip()
                if _snid in nodes:
                    nodes[_snid].extra_css = _scss
                else:
                    # Node may not exist yet; store for post-processing below
                    nodes.setdefault(_snid, _Node(id=_snid, label=_snid))
                    nodes[_snid].extra_css = _scss
            continue
        if line.startswith("linkStyle "):
            # `linkStyle <index> stroke:#f00,stroke-width:2px`
            _lm = re.match(r'^linkStyle\s+(\d+)\s+(.*)', line)
            if _lm:
                _lidx, _lcss = int(_lm.group(1)), _lm.group(2).strip()
                if _lidx < len(edges):
                    edges[_lidx].extra_css = _lcss
                else:
                    # Edge not yet parsed; defer by tagging a placeholder
                    # (linkStyle appears after the edges in mermaid source)
                    _pending_link_styles.append((_lidx, _lcss))
            continue
        if line.startswith("class ") and not line.startswith("classDiagram"):
            continue
        # stateDiagram-v2 notes: accumulate block or emit inline
        if _note_target:
            # Inside a note block — accumulate until "end note"
            if line.lower().strip() == "end note":
                _note_text = " ".join(_note_lines).strip()
                if _note_text:
                    _ensure(_note_target, _note_target, "rect", "")  # forward-ref guard
                    _nid = f"_note_{_note_counter}"
                    _note_counter += 1
                    _ensure(_nid, _note_text, "rect", "state-note")
                    edges.append(_Edge(src=_note_target, dst=_nid, label="", style="dotted", arrow=False))
                _note_target = ""
                _note_lines = []
            else:
                _note_lines.append(line)
            continue
        _note_inline = _STATE_NOTE_INLINE.match(line)
        if _note_inline:
            _ni_target, _ni_text = _note_inline.group(1), _note_inline.group(2).strip()
            _nid = f"_note_{_note_counter}"
            _note_counter += 1
            _ensure(_nid, _ni_text, "rect", "state-note")
            # Ensure target node exists (may be forward-referenced)
            _ensure(_ni_target, _ni_target, "rect", "")
            edges.append(_Edge(src=_ni_target, dst=_nid, label="", style="dotted", arrow=False))
            continue
        _note_open = _STATE_NOTE_OPEN.match(line)
        if _note_open:
            _note_target = _note_open.group(1)
            _note_lines = []
            continue

        # stateDiagram-v2 / flowchart subgraph: inline direction directive
        _dir_m = re.match(r'direction\s+(LR|RL|TB|TD)\s*$', line, re.I)
        if _dir_m:
            # If inside a subgraph, store direction on the current group
            if stack:
                _cur_gid = stack[-1]
                if _cur_gid in groups:
                    groups[_cur_gid].direction = _dir_m.group(1).upper()
            continue
        # stateDiagram-v2: [*] is the initial/terminal state marker; map to a
        # renderable node id. Inside a composite state (stack non-empty), use a
        # scoped id so inner start/end don't collide with the outer [*] markers.
        _sm_scope = stack[-1] if stack else ""
        _sm_s = f"{_sm_scope}_sm_start_" if _sm_scope else "_sm_start_"
        _sm_e = f"{_sm_scope}_sm_end_" if _sm_scope else "_sm_end_"
        line = re.sub(r'^\[\*\]\s*(?=-->|--)', _sm_s + ' ', line).strip()
        line = re.sub(r'(?<=-->)\s*\[\*\]', f' {_sm_e}', line)

        # stateDiagram-v2 state alias: state "Long Label" as id
        _alias_m = re.match(r'^state\s+"([^"]+)"\s+as\s+(\w+)', line)
        if _alias_m:
            _ensure(_alias_m.group(2), _alias_m.group(1), "rect", "")
            continue

        # stateDiagram-v2 pseudo-state: state X <<fork|join|choice|history|historydeep>>
        _pseudo_m = re.match(r'^state\s+(\w+)\s+<<(\w+)>>', line, re.I)
        if _pseudo_m:
            _ps_id, _ps_kind = _pseudo_m.group(1), _pseudo_m.group(2).lower()
            if _ps_kind in ("fork", "join"):
                _ensure(_ps_id, _ps_id, "bar", f"state-{_ps_kind}")
            elif _ps_kind == "choice":
                _ensure(_ps_id, _ps_id, "diamond", "state-choice")
            elif _ps_kind in ("history", "historydeep", "deephistory"):
                _ensure(_ps_id, _ps_id, "circle", "state-history")
            else:
                _ensure(_ps_id, _ps_id, "rect", "")
            continue

        # stateDiagram-v2 composite state: state ID { (opens a nested group)
        _composite_m = re.match(r'^state\s+(\w+)\s*\{', line)
        if _composite_m:
            _cs_id = _composite_m.group(1)
            gid = f"_g{len(groups)}"
            parent_gid = stack[-1] if stack else None
            groups[gid] = _Group(id=gid, label=_cs_id, parent_group=parent_gid)
            # Do NOT create an atomic node for the composite state here.
            # Transition lines like "Processing --> Done" will call _ensure("Processing")
            # and re-create it; we remove it and rewire edges in the post-processing step below.
            _composite_gids.add(gid)
            stack.append(gid)
            continue

        # stateDiagram-v2: standalone closing brace ends composite state
        if line.strip() == "}":
            if stack:
                stack.pop()
            continue

        # stateDiagram-v2 state description: id : label (standalone, no edge operator)
        if re.match(r'^\w+\s*:\s*\S', line) and '--' not in line and not line.startswith('http'):
            _sd_parts = line.split(':', 1)
            _sd_id = _sd_parts[0].strip()
            _sd_label = _sd_parts[1].strip()
            if re.match(r'^[A-Za-z_]\w*$', _sd_id) and _sd_label:
                _ensure(_sd_id, _sd_label, "rect", "")
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
            parent_gid = stack[-1] if stack else None
            groups[gid] = _Group(id=gid, label=label or gid, parent_group=parent_gid)
            stack.append(gid)
            continue
        if line.lower().strip() in ("end", "end;"):
            if stack:
                stack.pop()
            continue

        # Try to match as edge chain; a line can chain: A --> B --> C
        _parse_line(line, edges, _ensure)

    # Flush any unterminated note block (missing "end note" swallows trailing diagram)
    if _note_target and _note_lines:
        _note_text = " ".join(_note_lines).strip()
        if _note_text:
            _ensure(_note_target, _note_target, "rect", "")
            _nid = f"_note_{_note_counter}"
            _ensure(_nid, _note_text, "rect", "state-note")
            edges.append(_Edge(src=_note_target, dst=_nid, label="", style="dotted", arrow=False))

    # Apply deferred linkStyle overrides (linkStyle appears after edges in source)
    for _lidx, _lcss in _pending_link_styles:
        if _lidx < len(edges):
            edges[_lidx].extra_css = _lcss

    # Post-process: all _sm_start_ / _sm_end_ nodes (global and scoped) get circle shape
    for _sm_id in list(nodes.keys()):
        if _sm_id.endswith("_sm_start_"):
            nodes[_sm_id].shape = "circle"
            nodes[_sm_id].label = "●"
        elif _sm_id.endswith("_sm_end_"):
            nodes[_sm_id].shape = "doublecircle"
            nodes[_sm_id].label = ""

    # Post-process: composite state names are group labels, not standalone atomic nodes.
    # Transition parsing re-creates them as nodes; remove them and rewire edges to
    # the group's entry/exit anchor nodes (scoped _sm_start_ / _sm_end_).
    for _cgid in _composite_gids:
        _cs_name = groups[_cgid].label
        if _cs_name not in nodes:
            continue
        del nodes[_cs_name]
        _entry = f"{_cgid}_sm_start_"
        _exit = f"{_cgid}_sm_end_"
        if _entry not in nodes:
            _entry = next(
                (m for m in groups[_cgid].members if m in nodes and not m.endswith("_sm_end_")),
                _entry,
            )
        if _exit not in nodes:
            _exit = next(
                (m for m in reversed(groups[_cgid].members) if m in nodes and not m.endswith("_sm_start_")),
                _exit,
            )
        for _e in edges:
            if _e.src == _cs_name:
                _e.src = _exit
            if _e.dst == _cs_name:
                _e.dst = _entry

    # Assign stable parse-time edge IDs.  Duplicates get a #N suffix so every
    # edge has a unique ID that survives across layout stages.
    _id_counts: dict[str, int] = {}
    for _e in edges:
        _base = f"{_e.src}->{_e.dst}"
        _n = _id_counts.get(_base, 0)
        _id_counts[_base] = _n + 1
        _e.edge_id = _base if _n == 0 else f"{_base}#{_n}"

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

    # Expand parallel `&` notation: "A & B --> C & D" → all (src, dst) pairs.
    # Split only when & appears outside brackets to avoid splitting node labels.
    def _split_parallel(raw: str) -> list[str]:
        parts, buf, depth = [], [], 0
        for ch in raw:
            if ch in "([{":
                depth += 1; buf.append(ch)
            elif ch in ")]}":
                depth -= 1; buf.append(ch)
            elif ch == "&" and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append("".join(buf).strip())
        return [p for p in parts if p]

    srcs = _split_parallel(src_raw)
    dsts = _split_parallel(dst_raw)
    if len(srcs) > 1 or len(dsts) > 1:
        for _s in srcs:
            for _d in dsts:
                _parse_line(f"{_s} {arrow} {_d}", edges, ensure_fn)
        return

    # stateDiagram-v2 uses ": transition_label" appended to the destination node.
    # Only extract it when the dst has no bracket/paren spec (stateDiagram nodes are
    # plain identifiers) to avoid stripping colons from flowchart labels like B["k:v"].
    if not edge_label and ' : ' in dst_raw and not re.search(r'[\[\](){}]', dst_raw.split(' : ', 1)[0]):
        _parts = dst_raw.split(' : ', 1)
        dst_raw = _parts[0].strip()
        edge_label = _parts[1].strip().strip('"\'')


    style = "dotted" if "-.-" in arrow else ("thick" if "==" in arrow else "solid")
    is_bidir = arrow == "<-->"
    has_arrow = is_bidir or arrow.endswith(">")

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
        edges.append(_Edge(src=src_id, dst=dst_id, label=edge_label, style=style, arrow=has_arrow, bidir=is_bidir))
        _parse_line(dst_raw, edges, ensure_fn)
    else:
        dst_id, dst_lbl, dst_shp, dst_cls = _parse_spec_and_class(dst_raw)
        if not re.match(r'[A-Za-z_]', dst_id):
            return
        ensure_fn(dst_id, dst_lbl, dst_shp, dst_cls)
        edges.append(_Edge(src=src_id, dst=dst_id, label=edge_label, style=style, arrow=has_arrow, bidir=is_bidir))


