"""mermaid_render.paint_tokens — Resolved paint token system.

A `PaintTokens` dataclass holds all resolved concrete color/style values for
a given theme. Painters receive a resolved `PaintTokens` instance so that
color values are centralised and theme-switchable.

Currently only the "default" theme is defined. Future themes (dark, forest, etc.)
should add entries to `_THEME_REGISTRY`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaintTokens:
    """Resolved paint token set for a theme.

    All colors are concrete hex or rgba strings — no CSS variables.
    """
    # Canvas / background
    background: str = "#ffffff"

    # Nodes
    primary_fill: str = "#e8f4fd"
    primary_border: str = "#4a90d9"
    primary_text: str = "#1a1a2e"

    # External / secondary nodes (C4 external, etc.)
    external_fill: str = "#999999"
    external_border: str = "#8a8a8a"
    external_text: str = "#ffffff"

    # Text
    text: str = "#191a17"
    muted_text: str = "#75736c"
    dim_text: str = "#9ca3af"

    # Edges
    edge_stroke: str = "#555566"
    edge_stroke_width: float = 1.5
    edge_thick_width: float = 3.0
    edge_dot_dash: str = "4 3"
    arrowhead_fill: str = "#555566"
    marker_size: float = 8.0

    # Labels on edges
    edge_label_text: str = "#374151"
    edge_label_bg: str = "#ffffff"

    # Groups / subgraphs
    group_fill: str = "rgba(99,102,241,0.06)"
    group_border: str = "#6366f1"
    group_text: str = "#4f46e5"

    # Notes
    note_fill: str = "#fefce8"
    note_border: str = "#d97706"
    note_text: str = "#92400e"

    # C4
    c4_node_fill: str = "#f7f6f2"
    c4_node_border: str = "#dad7ce"
    c4_external_fill: str = "#999999"
    c4_external_border: str = "#8a8a8a"
    c4_boundary_border: str = "#dad7ce"
    c4_accent: str = "#60a5fa"

    # Architecture
    arch_service_fill: str = "#f7f6f2"
    arch_service_border: str = "#dad7ce"
    arch_service_text: str = "#191a17"
    arch_icon_fill: str = "#4a90d9"

    # Timeline
    timeline_section_palette: tuple = (
        "rgba(96,165,250,0.10)",
        "rgba(52,211,153,0.10)",
        "rgba(251,191,36,0.10)",
        "rgba(167,139,250,0.10)",
        "rgba(248,113,113,0.10)",
    )
    timeline_dot_fill: str = "#60a5fa"
    timeline_spine: str = "#94a3b8"

    # Mindmap
    mindmap_section_fill: tuple = (
        "rgba(53,148,103,0.08)",
        "rgba(99,102,241,0.08)",
        "rgba(245,158,11,0.08)",
        "rgba(239,68,68,0.08)",
        "rgba(20,184,166,0.08)",
        "rgba(168,85,247,0.08)",
        "rgba(236,72,153,0.08)",
    )
    mindmap_edge: str = "rgba(100,116,139,0.6)"

    # Pseudo-states (state diagrams)
    pseudo_state_fill: str = "#1a1a2e"
    pseudo_state_stroke: str = "#1a1a2e"


# ── Theme registry ────────────────────────────────────────────────────────────

_DEFAULT = PaintTokens()

_DARK = PaintTokens(
    background="#1e1e2e",
    primary_fill="#2d3748",
    primary_border="#7c8cf8",
    primary_text="#e2e8f0",
    external_fill="#4a5568",
    external_border="#718096",
    external_text="#e2e8f0",
    text="#e2e8f0",
    muted_text="#a0aec0",
    dim_text="#718096",
    edge_stroke="#a0aec0",
    arrowhead_fill="#a0aec0",
    group_fill="rgba(124,140,248,0.12)",
    group_border="#7c8cf8",
    group_text="#a0aec0",
    note_fill="#2d3748",
    note_border="#d97706",
    note_text="#fbbf24",
    c4_node_fill="#2d3748",
    c4_node_border="#4a5568",
    c4_accent="#7c8cf8",
    arch_service_fill="#2d3748",
    arch_service_border="#4a5568",
    arch_service_text="#e2e8f0",
    timeline_dot_fill="#7c8cf8",
    timeline_spine="#718096",
    mindmap_edge="rgba(160,174,192,0.6)",
    pseudo_state_fill="#e2e8f0",
    pseudo_state_stroke="#e2e8f0",
)

_THEME_REGISTRY: dict[str, PaintTokens] = {
    "default": _DEFAULT,
    "base": _DEFAULT,
    "adaptive-light": _DEFAULT,
    "adaptive-dark": _DARK,
    "dark": _DARK,
    "forest": PaintTokens(
        primary_fill="#d5e8d4",
        primary_border="#82b366",
        primary_text="#1a1a2e",
        edge_stroke="#82b366",
        arrowhead_fill="#82b366",
        group_fill="rgba(130,179,102,0.08)",
        group_border="#82b366",
        group_text="#4d7c0f",
    ),
}


def resolve_tokens(theme: "str | dict | None" = None) -> PaintTokens:
    """Return resolved PaintTokens for the given theme name.

    Accepts str theme names or Theme objects (str | dict | None).
    Falls back to default if theme is not a string or not found.
    """
    if not isinstance(theme, str):
        return _DEFAULT
    return _THEME_REGISTRY.get(theme.lower(), _DEFAULT)
