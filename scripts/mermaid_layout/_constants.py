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

# Flowchart label keyword → icon name (ordered: first match wins; longer phrases before substrings).
# Used by _infer_label_icons to auto-assign icons when no explicit :::icon-name class is set.
# Keep entries specific — generic terms ("server", "service") are excluded to avoid false matches.
_LABEL_ICON_KEYWORDS: list[tuple[list[str], str]] = [
    (["end user", "web user", "mobile user", "user", "person", "actor", "customer", "client", "principal"], "users"),
    (["web app", "webapp", "web portal", "spa", "frontend", "browser", "web ui"], "browser"),
    (["admin", "administrator", "operator", "superuser"], "admin"),
    (["mobile app", "ios app", "android app", "native app", "mobile device"], "mobile"),
    (["vector store", "vector db", "vector index", "embedding store", "rag index", "vector"], "vector-store"),
    (["language model", "llm", "gpt", "claude", "gemini", "ai engine", "ai model", "ai inference", "ml model"], "model"),
    (["model api", "inference api", "openai api", "anthropic api"], "model-api"),
    (["search engine", "elasticsearch", "opensearch", "full-text search", "knowledge search", "search index"], "search"),
    (["message broker", "rabbitmq", "activemq", "kafka broker"], "message-broker"),
    (["event bus", "event-bus", "pub/sub", "pubsub", "eventbridge"], "event-bus"),
    (["job queue", "work queue", "task queue", "sqs queue", "queue"], "queue"),
    (["data pipeline", "etl pipeline", "ingestion pipeline"], "pipeline"),
    (["data lake", "data warehouse", "snowflake", "redshift", "bigquery"], "data-warehouse"),
    (["cache", "redis", "memcache", "memcached"], "cache"),
    (["identity provider", "idp", "sso", "saml", "oidc", "keycloak", "auth0", "auth service", "iam"], "iam"),
    (["vault", "secrets manager", "keyvault", "secret store"], "vault"),
    (["api gateway", "gateway", "reverse proxy", "ingress controller", "api"], "api"),
    (["load balancer", "load-balancer", "nginx", "haproxy"], "load-balancer"),
    (["cdn", "cloudfront", "akamai", "edge network"], "cdn"),
    (["kubernetes", "k8s", "eks cluster", "aks cluster", "gke cluster"], "kubernetes"),
    (["ci/cd", "ci-cd", "github actions", "jenkins", "build pipeline"], "ci-cd"),
    (["scheduler", "cron job", "airflow", "dagster", "prefect"], "scheduler"),
    (["workflow engine", "step function", "temporal", "bpmn engine"], "workflow"),
    (["email", "sendgrid", "ses ", "mailgun", "smtp"], "email"),
    (["push notification", "fcm", "apns", "sns notification"], "notification"),
    (["object store", "s3 bucket", "gcs bucket", "blob storage"], "object-store"),
    (["database", "postgresql", "mysql", "mongodb", "dynamodb", "aurora", "cosmos db", "rds"], "database"),
    (["ai agent", "autonomous agent", "reasoning agent"], "agent"),
    (["cloud platform", "aws ", "azure ", "gcp ", "saas platform"], "cloud"),
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
NODE_H = 42       # minimum card height (2×pad_v + icon_h = 20+24=44 triggers icon bump above 42)
RANK_GAP = 80    # gap in flow direction (vertical in TB, horizontal in LR)
COL_GAP = 52     # gap perpendicular to flow (horizontal in TB, vertical in LR)
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
_NODE_H_TECH = 17   # separator + tech text line (7px margin + 7px padding + ~12px text ÷ 2)
SELF_LOOP_DX = 28  # horizontal reach of self-loop arc
MIN_FAN_STEP = 12  # minimum px between adjacent fan endpoints on a node edge
_TERMINAL_NODE_SIZE = 32  # px square for circle nodes with symbol labels (UML start/end states)

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
    parent_group: Optional[str] = None  # set when this subgraph is nested inside another



_WRAP_CHARS = 20        # label wrap threshold (NODE_W=192 minus ~44px padding = ~148px usable ≈ 20 chars at 7.5px/char)
_WRAP_CHARS_ICON = 18  # reduced limit for icon-left cards (icon 24px + 10px margin reduces usable to ~134px ≈ 16-18 chars; 18 avoids over-eager breaks on short labels)


def _wrap_label(label: str, max_chars: int = _WRAP_CHARS) -> list[str]:
    """Split label into lines of at most max_chars characters.

    Treats literal \\n (two-char escape) and real newlines as explicit breaks.
    Pass max_chars=_WRAP_CHARS_ICON for icon-left card titles where the icon
    consumes ~34px of the available text width.
    """
    # Normalise literal \n escape sequences to real newlines first
    normalized = label.replace("\\n", "\n")
    if "\n" in normalized:
        result: list[str] = []
        for chunk in normalized.split("\n"):
            stripped = chunk.strip()
            if stripped:
                result.extend(_wrap_label(stripped, max_chars))
        return result or [label]
    if len(normalized) <= max_chars:
        return [normalized]
    # Split on spaces first; for hyphen-compound words, also split at hyphens
    # so long kebab-case identifiers (e.g. express-ai-knowledge-source-enterprise-it)
    # break at natural boundaries instead of at arbitrary char positions.
    raw_words = normalized.split()
    words: list[str] = []
    for w in raw_words:
        if len(w) > max_chars and "-" in w:
            parts = w.split("-")
            acc = parts[0]
            for p in parts[1:]:
                candidate = acc + "-" + p
                if len(candidate) <= max_chars:
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
        while len(w) > max_chars:
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(w[:max_chars])
            w = w[max_chars:]
        if cur and len(cur) + 1 + len(w) > max_chars:
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


def _node_render_h(n: "_Node") -> int:
    """Return the rendered pixel height of node n (single source of truth).

    Icon-left layout: icon sits alongside title text, not below.
    header_h = max(icon_h, title_h + sub_h) — icon only adds height when taller than text.
    """
    if _is_terminal_circle(n):
        return _TERMINAL_NODE_SIZE

    raw_label = n.label.split("|", 1)[0].strip() if "|" in n.label else n.label
    main_label, sub_label = _split_sub_label(raw_label)

    has_icon = bool(
        (n.icon and _load_icon(n.icon)) or (n.css_class and _load_icon(n.css_class))
    )
    # Icon-left cards have a narrower text column; use reduced wrap limit so height
    # computation accounts for the extra lines that actually wrap in the rendered card.
    icon_wrap = _WRAP_CHARS_ICON if has_icon else _WRAP_CHARS
    title_lines = _wrap_label(main_label, max_chars=icon_wrap)
    sub_lines = _wrap_label(sub_label, max_chars=icon_wrap) if sub_label else []

    title_h = len(title_lines) * _TITLE_LINE_H
    sub_h = len(sub_lines) * _SUB_LINE_H

    header_h = max(_ICON_H, title_h + sub_h) if has_icon else (title_h + sub_h)
    tech_h = _NODE_H_TECH if "|" in n.label else 0

    return max(NODE_H, 2 * _NODE_PAD_V + header_h + tech_h)

