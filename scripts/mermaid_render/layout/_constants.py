from __future__ import annotations

import html as _html
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ._geometry import MarkerKind, MarkerSpec

# ── icon loader ───────────────────────────────────────────────────────────────

_ICON_DIR = Path(__file__).parent.parent / "icons"
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

# Flowchart label keyword → icon name (ordered: first match wins; longer phrases before substrings).
# Used by _infer_label_icons to auto-assign icons when no explicit :::icon-name class is set.
# Matching uses word boundaries (\b) so short tokens like "cli" or "mcp" don't false-positive
# inside longer words ("client", "compact"). Keep entries specific — generic terms ("server",
# "service") are excluded to avoid false matches.
_LABEL_ICON_KEYWORDS: list[tuple[list[str], str]] = [
    # Human actors — longer phrases first so "developer" doesn't fall through to generic "user"
    (["end user", "web user", "mobile user", "developer", "repository maintainer",
      "pack installer", "user", "person", "actor", "customer", "client", "principal"], "users"),
    # Development tools
    (["coding ide", "code editor", "ide"], "ide"),
    (["cli"], "terminal"),
    # AI/knowledge protocol
    (["mcp server", "mcp tool", "mcp"], "mcp-server"),
    # GraphRAG / specialised retrieval — before generic "search"
    (["graphrag", "graph rag"], "graphrag-search"),
    # Agent skill catalogues — before generic "agent"
    (["coding subagent", "agent skill", "skills catalogue", "skill catalogue",
      "artifact registry"], "coding-subagent"),
    # Knowledge infrastructure — specific sub-types before "database"
    (["knowledge source", "knowledge-source"], "knowledge-corpus"),
    (["knowledge graph", "graph database", "graph db", "neo4j"], "knowledge-graph"),
    (["knowledge search", "knowledge layer"], "knowledge-search"),
    # Source code and versioned artifacts
    (["application source", "source code", "source artifact", "project artifact"], "source-code"),
    (["pack directory", "repository-scoped", "scoped packs"], "package"),
    (["git working tree", "git repo", "version control"], "code-branch"),
    # Web / frontend
    (["web app", "webapp", "web portal", "spa", "frontend", "browser", "web ui"], "browser"),
    (["admin", "administrator", "operator", "superuser"], "admin"),
    (["mobile app", "ios app", "android app", "native app", "mobile device"], "mobile"),
    # Data stores
    (["vector store", "vector db", "vector index", "embedding store", "rag index", "vector"], "vector-store"),
    # "amazon rds" replaces bare "rds" which false-positives on "standards"
    (["database", "postgresql", "mysql", "mongodb", "dynamodb", "aurora",
      "cosmos db", "amazon rds"], "database"),
    # AI/ML models
    (["language model", "llm", "gpt", "claude", "gemini", "ai engine",
      "ai model", "ai inference", "ml model"], "model"),
    (["model api", "inference api", "openai api", "anthropic api"], "model-api"),
    # Search (generic, after graphrag-search and knowledge-search)
    (["search engine", "elasticsearch", "opensearch", "full-text search",
      "knowledge search", "search index"], "search"),
    # Messaging / eventing
    (["message broker", "rabbitmq", "activemq", "kafka broker"], "message-broker"),
    (["event bus", "event-bus", "pub/sub", "pubsub", "eventbridge"], "event-bus"),
    (["job queue", "work queue", "task queue", "sqs queue", "queue"], "queue"),
    # Pipelines
    (["data pipeline", "etl pipeline", "ingestion pipeline"], "pipeline"),
    (["data lake", "data warehouse", "snowflake", "redshift", "bigquery"], "data-warehouse"),
    # Infrastructure services
    (["cache", "redis", "memcache", "memcached"], "cache"),
    (["identity provider", "idp", "sso", "saml", "oidc",
      "keycloak", "auth0", "auth service", "iam"], "iam"),
    (["vault", "secrets manager", "keyvault", "secret store"], "vault"),
    (["api gateway", "gateway", "reverse proxy", "ingress controller", "api"], "api"),
    (["load balancer", "load-balancer", "nginx", "haproxy"], "load-balancer"),
    (["cdn", "cloudfront", "akamai", "edge network"], "cdn"),
    (["kubernetes", "k8s", "eks cluster", "aks cluster", "gke cluster"], "kubernetes"),
    (["ci/cd", "ci-cd", "github actions", "jenkins", "build pipeline"], "ci-cd"),
    (["scheduler", "cron job", "airflow", "dagster", "prefect"], "scheduler"),
    (["workflow engine", "step function", "temporal", "bpmn engine"], "workflow"),
    # "ses" with word-boundary matching no longer false-positives on "processes"
    (["email", "sendgrid", "ses", "mailgun", "smtp"], "email"),
    (["push notification", "fcm", "apns", "sns notification"], "notification"),
    (["object store", "s3 bucket", "gcs bucket", "blob storage"], "object-store"),
    # Generic agents
    (["ai agent", "autonomous agent", "reasoning agent"], "agent"),
    # Cloud (bare "aws"/"azure"/"gcp" safe with word boundaries)
    (["cloud platform", "aws", "azure", "gcp", "saas platform"], "cloud"),
    # Observability
    (["log store", "log stream", "cloudwatch logs", "datadog logs", "splunk"], "logs"),
    (["metrics store", "prometheus", "grafana", "monitoring platform"], "metrics"),
]


# ── caps ──────────────────────────────────────────────────────────────────────
NODE_CAP = 64
EDGE_CAP = 128
GROUP_CAP = 16
CROSSING_PASSES = 8  # 4 forward + 4 backward barycenter passes

# ── default geometry (px) ────────────────────────────────────────────────────
NODE_W = 192
NODE_MIN_W = 64   # minimum per-node width (never narrower than this)
NODE_HPAD = 24    # horizontal padding (12px each side) added to measured text width
NODE_H = 42       # minimum card height (2×pad_v + icon_h = 20+24=44 triggers icon bump above 42)
RANK_GAP = 80    # gap in flow direction (vertical in TB, horizontal in LR)
COL_GAP = 56     # gap perpendicular to flow (horizontal in TB, vertical in LR)
CANVAS_PAD = 48  # outer inset on all sides
GROUP_PAD_X = 28  # group container horizontal inner padding
GROUP_PAD_Y_TOP = 36  # group container top inner padding (room for label)
GROUP_PAD_Y_BOT = 28  # group container bottom inner padding

# Node height constants — icon-left layout: icon sits ALONGSIDE text (not below).
# header_h = max(icon_h, title_h + sub_h); icon only adds height when taller than text.
_NODE_PAD_V = 12   # vertical padding per side (top and bottom)
_TITLE_LINE_H = 18  # title text line height (~14px font × 1.3)
_SUB_LINE_H = 16    # sub-label line height (~12px font × 1.3)
_ICON_H = 24        # icon SVG height in card header
_NODE_H_TECH = 17   # separator + first tech line (7px margin + 7px padding + ~12px text ÷ 2)
_MEMBER_LINE_H = 16  # height of each additional member/attribute row after the first
SELF_LOOP_DX = 28  # horizontal reach of self-loop arc (TB-mode fallback, unused after direction-aware routing)
MIN_FAN_STEP = 12  # minimum px between adjacent fan endpoints on a node edge
_TERMINAL_NODE_SIZE = 32  # px square for circle nodes with symbol labels (UML start/end states)
_CIRCLE_NODE_SIZE = 80    # px square for regular (non-terminal) circle nodes
DOUBLE_CIRCLE_RING = 8    # extra ring clearance px added to each side for doublecircle
_DIAMOND_SIZE = 100       # px square for diamond nodes (keeps aspect ratio 1:1)
DIAMOND_MIN = 80          # minimum diamond side length
_HEXAGON_SIZE = 100       # px square for hexagon nodes (keeps aspect ratio 1:1)
HEX_MIN_W = 80            # minimum hexagon width
HEX_MIN_H = 60            # minimum hexagon height
_BAR_W = 60               # px width of fork/join bar (horizontal UML sync bar)
_BAR_H = 8                # px height of the visible bar stroke
_BAR_LABEL_H = 20         # px height reserved below bar for the node label text
ICON_COL_WIDTH: int = 34  # icon 24px + margin 10px (icon-left card column reserved width)
NODE_MAX_W: int = 220     # upper bound for text-box node widths (circle/diamond/hexagon uncapped)
# Self-loop direction-aware routing constants
BASE_LOOP_EXTENT = 32     # minimum side-protrusion of a self-loop arc (px)
LOOP_LANE_GAP = 20        # additional extent per lane index for multiple loops on one node
LABEL_PAD = 6             # padding each side of edge label chip within the loop extent

# Font constants matching _renderer.py's emitted CSS variables
_TITLE_FS: int = 15   # var(--node-fs-title, 15px) — standard node title
_TITLE_FW: int = 700  # font-weight for both icon and non-icon titles
_ICON_FS: int = 14    # var(--node-fs-title, 14px) — icon-left node title (slightly smaller)


def _measure_text_px(label: str) -> int:
    """Approximate pixel width of a text label at the renderer's title font (15px/700).

    Only the first display line is measured (before any | separator or newline).
    """
    text = label.split("|")[0].split("\n")[0]
    return math.ceil(_measure_text_width(text, _TITLE_FS, _TITLE_FW))


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
    icon: str = ""                # icon name from mermaid_render/icons/ (without .svg)
    css_class: str = ""           # semantic class, e.g. "external"
    extra_css: str = ""           # inline CSS overrides (from `style NodeId fill:...`)
    width: int = 0                # computed per-node render width (0 → use global NODE_W)
    height: int = 0               # computed per-node render height (0 → use _node_render_h)


# Sentinel MarkerSpec values used as default field values on _Edge.
# Frozen dataclasses are immutable so they are safe as dataclass defaults.
_NONE_SRC_SPEC: MarkerSpec = MarkerSpec(kind=MarkerKind.NONE, end="SOURCE")
_NONE_TGT_SPEC: MarkerSpec = MarkerSpec(kind=MarkerKind.NONE, end="TARGET")


def _marker_kind(m: object) -> MarkerKind:
    """Coerce a polymorphic marker to its MarkerKind, total over every form the
    pipeline produces (MarkerSpec | MarkerKind | str | None) and degrading any
    unrecognised value to MarkerKind.NONE. Check MarkerKind before str because
    MarkerKind subclasses str."""
    if m is None:
        return MarkerKind.NONE
    if isinstance(m, MarkerKind):
        return m
    kind = getattr(m, "kind", None)  # MarkerSpec
    if kind is not None:
        m = kind
    if isinstance(m, MarkerKind):
        return m
    if isinstance(m, str):
        try:
            return MarkerKind(m)
        except ValueError:
            return MarkerKind.NONE
    return MarkerKind.NONE


@dataclass
class _Edge:
    src: str
    dst: str
    label: str = ""
    style: str = "solid"          # solid|dotted|thick
    reversed_: bool = False       # back-edge flag
    source_marker: MarkerSpec = field(default_factory=lambda: _NONE_SRC_SPEC)
    target_marker: MarkerSpec = field(default_factory=lambda: _NONE_TGT_SPEC)
    src_label: str = ""           # text label near source endpoint (e.g. class multiplicities)
    dst_label: str = ""           # text label near destination endpoint
    cardinality_src: Optional[str] = None  # ER crow's foot: 'one'|'zero-one'|'many'|'zero-many'
    cardinality_dst: Optional[str] = None
    orig_src: Optional[str] = None  # original src for dummy-chained edges
    orig_dst: Optional[str] = None  # original dst for dummy-chained edges
    extra_css: str = ""           # inline CSS overrides (from `linkStyle N stroke:...`)
    src_side: Optional[str] = None  # architecture-beta port side: L|R|T|B
    dst_side: Optional[str] = None  # architecture-beta port side: L|R|T|B
    edge_id: str = ""             # stable parse-time ID: "src->dst" (or "src->dst#N" for duplicates)
    src_group: Optional[str] = None  # group ID whose boundary clips the source endpoint (cross-scope exit)

    @property
    def arrow(self) -> bool:
        """True when a target-end marker (arrowhead) is present. Derived from the
        canonical target_marker — the single source of truth for edge markers."""
        return _marker_kind(self.target_marker) != MarkerKind.NONE

    @property
    def bidir(self) -> bool:
        """True for <--> edges: an arrowhead on both ends. Derived from the
        markers — both ends must be plain ARROW (class relationship markers such
        as diamonds/triangles are not bidirectional)."""
        return (_marker_kind(self.source_marker) == MarkerKind.ARROW
                and _marker_kind(self.target_marker) == MarkerKind.ARROW)


@dataclass
class _Group:
    id: str
    label: str = ""
    members: list[str] = field(default_factory=list)
    parent_group: Optional[str] = None  # set when this subgraph is nested inside another
    direction: str = ""                 # inner layout direction override (e.g. "LR")


# ── ER cardinality model ──────────────────────────────────────────────────────

class Minimum(Enum):
    """Minimum cardinality of an ER relationship end."""
    ZERO = "zero"
    ONE = "one"


class Maximum(Enum):
    """Maximum cardinality of an ER relationship end."""
    ONE = "one"
    MANY = "many"


@dataclass(frozen=True)
class CardinalityEnd:
    """Structured representation of one end of an ER relationship cardinality.

    Examples (token → CardinalityEnd):
        ``||``  → CardinalityEnd(ONE, ONE)
        ``o{``  → CardinalityEnd(ZERO, MANY)
        ``}|``  → CardinalityEnd(ONE, MANY)
        ``|o``  → CardinalityEnd(ZERO, ONE)
        ``|{``  → CardinalityEnd(ONE, MANY)
    """
    minimum: Minimum
    maximum: Maximum


# ── text metrics ──────────────────────────────────────────────────────────────

_NARROW_CHARS = frozenset("iltfjI1!|.,:;'")
_SEMI_NARROW_CHARS = frozenset("()[]{}/\\-\"`")
_WIDE_CHARS = frozenset("WMwm@%")


def _measure_text_width(text: str, font_size: int, font_weight: int) -> float:
    """Estimate rendered text width in px via character-class bucketing.

    Approximates browser canvas.measureText for system-ui/Inter at the
    given font_size and font_weight. Accuracy is within ±15% of real
    browser measurements for typical UI text (ASCII + CJK + punctuation).
    """
    if not text:
        return 0.0
    base = 0.60 if font_weight >= 600 else (0.57 if font_weight >= 500 else 0.54)
    total = 0.0
    for c in text:
        cp = ord(c)
        if 0x0300 <= cp <= 0x036F:  # combining marks — zero width
            ratio = 0.0
        elif c == " ":
            ratio = 0.3
        elif c in _NARROW_CHARS:
            ratio = 0.4
        elif c in _SEMI_NARROW_CHARS:
            ratio = 0.5
        elif c == "r":
            ratio = 0.8
        elif c in _WIDE_CHARS:  # check before generic uppercase A–Z
            ratio = 1.5
        elif "A" <= c <= "Z":
            ratio = 1.2
        elif cp >= 0x4E00:  # CJK unified ideographs + emoji surrogates
            ratio = 2.0
        else:
            ratio = 1.0
        total += ratio
    return total * font_size * base + font_size * 0.15


def _wrap_label(label: str, width_budget: int = NODE_W - 40) -> list[str]:
    """Split label into lines fitting within width_budget pixels.

    Uses _measure_text_width at _TITLE_FS/_TITLE_FW to estimate pixel widths,
    matching the renderer's emitted font. Treats literal \\n and real newlines
    as explicit breaks. For icon-left cards pass width_budget=NODE_W - 40 - ICON_COL_WIDTH.
    """
    # 1. Normalize <br> variants to \n so they split before _nh() escapes angle brackets.
    # 2. Decode HTML entities (&lt; → <, &amp; → & etc.) for correct re-escaping by _nh().
    # 3. Re-normalize any <br> that entity decoding re-introduced (e.g. &lt;br&gt; → <br>).
    #    Those are treated as explicit line breaks — consistent with actual <br> tags.
    _br_step1 = re.sub(r'<br\s*/?>', '\n', label, flags=re.IGNORECASE).replace("\\n", "\n")
    _decoded  = _html.unescape(_br_step1)
    normalized = re.sub(r'<br\s*/?>', '\n', _decoded, flags=re.IGNORECASE)
    if "\n" in normalized:
        result: list[str] = []
        for chunk in normalized.split("\n"):
            stripped = chunk.strip()
            if stripped:
                result.extend(_wrap_label(stripped, width_budget))
        return result or [label]
    if _measure_text_width(normalized, _TITLE_FS, _TITLE_FW) <= width_budget:
        return [normalized]
    # Split on spaces; for hyphen-compound words also split at hyphens so
    # long kebab-case identifiers break at natural boundaries.
    raw_words = normalized.split()
    words: list[str] = []
    for w in raw_words:
        if _measure_text_width(w, _TITLE_FS, _TITLE_FW) > width_budget and "-" in w:
            parts = w.split("-")
            acc = parts[0]
            for p in parts[1:]:
                candidate = acc + "-" + p
                if _measure_text_width(candidate, _TITLE_FS, _TITLE_FW) <= width_budget:
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
        # Break individual tokens that still exceed the budget
        while _measure_text_width(w, _TITLE_FS, _TITLE_FW) > width_budget:
            if cur:
                lines.append(cur)
                cur = ""
            # Find max prefix that fits in budget
            split_i = 1
            while (split_i < len(w) and
                   _measure_text_width(w[:split_i + 1], _TITLE_FS, _TITLE_FW) <= width_budget):
                split_i += 1
            lines.append(w[:split_i])
            w = w[split_i:]
        if not w:
            continue
        if cur and _measure_text_width(cur + " " + w, _TITLE_FS, _TITLE_FW) > width_budget:
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


def _is_terminal_circle(n: "_Node") -> bool:
    """True for circle nodes with a single symbol label (UML initial/final state dots)."""
    return n.shape == "circle" and len(n.label.strip()) <= 2


def _is_terminal_doublecircle(n: "_Node") -> bool:
    """True for UML final-state doublecircle nodes (global or scoped _sm_end_ suffix)."""
    return n.shape == "doublecircle" and n.id.endswith("_sm_end_")


def _node_size_circle(n: "_Node") -> int:
    """Dynamic diameter for a regular circle / doublecircle node.

    Measures ALL label lines (not just the first) so multiline circles size correctly.
    Doublecircle adds DOUBLE_CIRCLE_RING px per side of ring clearance.
    """
    if _is_terminal_doublecircle(n):
        return _TERMINAL_NODE_SIZE
    if _is_terminal_circle(n):
        return _TERMINAL_NODE_SIZE
    raw = n.label.split("|")[0].strip()
    # Resolve line breaks: handle \n and <br> variants
    import re as _re
    raw = _re.sub(r'<br\s*/?>', '\n', raw, flags=_re.IGNORECASE).replace("\\n", "\n")
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()] or [raw]
    content_w = max(_measure_text_width(ln, _TITLE_FS, _TITLE_FW) for ln in lines)
    content_h = len(lines) * _TITLE_LINE_H
    diameter = max(_CIRCLE_NODE_SIZE, math.ceil(math.hypot(content_w + NODE_HPAD, content_h + NODE_HPAD)))
    if n.shape == "doublecircle":
        diameter += 2 * DOUBLE_CIRCLE_RING
    return diameter


def _node_size_diamond(n: "_Node") -> int:
    """Side length for a diamond node: max_line_content_w + total_content_h + padding.

    Diamond has a rotated-square geometry; both content dimensions add to the
    required side, unlike hexagon where width and height are independent.
    All lines are measured (like circle/hexagon) so multi-line labels aren't clipped.
    """
    raw = n.label.split("|")[0].strip()
    import re as _re
    raw = _re.sub(r'<br\s*/?>', '\n', raw, flags=_re.IGNORECASE).replace("\\n", "\n")
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()] or [raw]
    content_w = max(_measure_text_width(ln, _TITLE_FS, _TITLE_FW) for ln in lines)
    content_h = len(lines) * _TITLE_LINE_H
    return max(DIAMOND_MIN, math.ceil(content_w + content_h + NODE_HPAD + _NODE_PAD_V // 2))


def _node_size_hexagon(n: "_Node") -> tuple[int, int]:
    """Independent (width, height) for a hexagon node.

    Hexagon height is driven by content height; width adds shoulder protrusion.
    Returns (width, height) rather than a square side to avoid conflating the axes.
    """
    raw = n.label.split("|")[0].strip()
    import re as _re
    raw = _re.sub(r'<br\s*/?>', '\n', raw, flags=_re.IGNORECASE).replace("\\n", "\n")
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()] or [raw]
    content_w = max(_measure_text_width(ln, _TITLE_FS, _TITLE_FW) for ln in lines)
    content_h = len(lines) * _TITLE_LINE_H
    height = max(HEX_MIN_H, math.ceil(content_h + 2 * _NODE_PAD_V))
    shoulder = max(10, math.ceil(height * 0.25))
    width = max(HEX_MIN_W, math.ceil(content_w + NODE_HPAD + 2 * shoulder))
    return width, height


def _node_size_diamond_hex(n: "_Node", base_size: int) -> int:
    """Backward-compat: returns a square side for diamond or hexagon.

    Prefer _node_size_diamond() and _node_size_hexagon() for new call sites.
    This shim keeps old call sites working without breakage.
    """
    if n.shape == "diamond":
        return _node_size_diamond(n)
    if n.shape == "hexagon":
        w, _ = _node_size_hexagon(n)
        return w
    label = n.label.split("|")[0].split("\n")[0].strip()
    content_w = _measure_text_width(label, _TITLE_FS, _TITLE_FW)
    content_h = _TITLE_LINE_H
    return max(base_size, math.ceil(content_w + content_h + NODE_HPAD))


def _node_render_h(n: "_Node") -> int:
    """Return the rendered pixel height of node n (single source of truth).

    Icon-left layout: icon sits alongside title text, not below.
    header_h = max(icon_h, title_h + sub_h) — icon only adds height when taller than text.
    """
    if _is_terminal_doublecircle(n):
        return _TERMINAL_NODE_SIZE
    if _is_terminal_circle(n):
        return _TERMINAL_NODE_SIZE
    if n.shape in ("circle", "doublecircle"):
        return n.width if n.width > 0 else _CIRCLE_NODE_SIZE
    if n.shape == "diamond":
        return n.width if n.width > 0 else _DIAMOND_SIZE
    if n.shape == "hexagon":
        return n.height if n.height > 0 else _HEXAGON_SIZE
    if n.shape == "bar":
        return _BAR_H + _BAR_LABEL_H

    raw_label = n.label.split("|", 1)[0].strip() if "|" in n.label else n.label
    main_label, sub_label = _split_sub_label(raw_label)

    has_icon = bool(
        (n.icon and _load_icon(n.icon)) or (n.css_class and _load_icon(n.css_class))
    )
    # Use per-node width for wrap budget; fall back to global NODE_W for nodes whose
    # width hasn't been computed yet (e.g. called before _assign_coordinates).
    # Deduct NODE_HPAD (not the historical -40) to stay consistent with how
    # _assign_coordinates computes n.width = measure_text + NODE_HPAD.
    _node_w = n.width if n.width > 0 else NODE_W
    _wbudget = (_node_w - NODE_HPAD - ICON_COL_WIDTH) if has_icon else (_node_w - NODE_HPAD)
    title_lines = _wrap_label(main_label, width_budget=_wbudget)
    sub_lines = _wrap_label(sub_label, width_budget=_wbudget) if sub_label else []

    title_h = len(title_lines) * _TITLE_LINE_H
    sub_h = len(sub_lines) * _SUB_LINE_H

    header_h = max(_ICON_H, title_h + sub_h) if has_icon else (title_h + sub_h)
    tech_h = 0
    if "|" in n.label:
        _tech_lines = n.label.split("|", 1)[1].split("\n")
        _n_member = sum(1 for ln in _tech_lines if ln.strip() and ln.strip() != "---")
        _n_divider = sum(1 for ln in _tech_lines if ln.strip() == "---")
        _n_lines = max(1, _n_member)
        tech_h = _NODE_H_TECH + (_n_lines - 1) * _MEMBER_LINE_H + _n_divider * 7

    return max(NODE_H, 2 * _NODE_PAD_V + header_h + tech_h)

