"""Style-neutral SVG projections from measured geometry.

Generates deterministic SVG that shows layout structure without
production palette, shadows, gradients, or font glyph rasterization.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from .models import BoundingBox, GeometryObservation

Layer = Literal["entities", "groups", "relations", "text", "arrows", "all"]

_ENTITY_FILL = "#e8edf4"
_ENTITY_STROKE = "#4a6fa5"
_GROUP_FILL = "rgba(200,220,240,0.25)"
_GROUP_STROKE = "#7090b0"
_RELATION_STROKE = "#666"
_TEXT_FILL = "#333"
_ARROW_FILL = "#666"


def generate_projection(
    obs: GeometryObservation,
    layers: list[Layer] | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
    label: str = "",
) -> str:
    """Generate a style-neutral SVG projection of the observed geometry.

    layers: which layers to include (default: all).
    The geometry reflects actual measured output, not idealized layout.
    """
    if layers is None:
        layers = ["all"]
    include_all = "all" in layers
    include_entities = include_all or "entities" in layers
    include_groups = include_all or "groups" in layers
    include_relations = include_all or "relations" in layers
    include_text = include_all or "text" in layers
    include_arrows = include_all or "arrows" in layers

    # Compute SVG viewport
    if obs.canvas_bounds:
        vw = width or int(obs.canvas_bounds.width)
        vh = height or int(obs.canvas_bounds.height)
        vb = f"0 0 {obs.canvas_bounds.width} {obs.canvas_bounds.height}"
    elif obs.content_bounds:
        cb = obs.content_bounds
        vw = width or int(cb.width) + 32
        vh = height or int(cb.height) + 32
        vb = f"{int(cb.x)-16} {int(cb.y)-16} {int(cb.width)+32} {int(cb.height)+32}"
    else:
        vw, vh = width or 800, height or 600
        vb = f"0 0 {vw} {vh}"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' width="{vw}" height="{vh}"'
        f' viewBox="{vb}"'
        f' style="background:#fafafa;">'
    ]

    if label:
        parts.append(
            f'<text x="8" y="16" font-size="11" fill="#888"'
            f' font-family="monospace">{_esc(label)}</text>'
        )

    # Groups (render first, behind entities)
    if include_groups:
        for gg in obs.groups:
            b = gg.bbox
            parts.append(
                f'<rect x="{b.x:.1f}" y="{b.y:.1f}"'
                f' width="{b.width:.1f}" height="{b.height:.1f}"'
                f' fill="{_GROUP_FILL}" stroke="{_GROUP_STROKE}"'
                f' stroke-width="1" stroke-dasharray="5 3" rx="4"/>'
            )
            parts.append(
                f'<text x="{b.x + 4:.1f}" y="{b.y + 12:.1f}"'
                f' font-size="9" fill="{_GROUP_STROKE}"'
                f' font-family="monospace">{_esc(gg.group_id)}</text>'
            )

    # Relations (connector skeletons)
    if include_relations:
        for rg in obs.relations:
            if len(rg.sampled_points) >= 2:
                pts = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in rg.sampled_points)
                parts.append(
                    f'<polyline points="{pts}"'
                    f' fill="none" stroke="{_RELATION_STROKE}"'
                    f' stroke-width="1.5" opacity="0.7"/>'
                )
            elif rg.source_point and rg.target_point:
                x1, y1 = rg.source_point
                x2, y2 = rg.target_point
                parts.append(
                    f'<line x1="{x1:.1f}" y1="{y1:.1f}"'
                    f' x2="{x2:.1f}" y2="{y2:.1f}"'
                    f' stroke="{_RELATION_STROKE}" stroke-width="1.5" opacity="0.7"/>'
                )

    # Entities (silhouettes)
    if include_entities:
        for eg in obs.entities:
            b = eg.bbox
            parts.append(
                f'<rect x="{b.x:.1f}" y="{b.y:.1f}"'
                f' width="{b.width:.1f}" height="{b.height:.1f}"'
                f' fill="{_ENTITY_FILL}" stroke="{_ENTITY_STROKE}"'
                f' stroke-width="1.5" rx="3"/>'
            )
            if include_text:
                label_x = b.x + b.width / 2
                label_y = b.y + b.height / 2 + 4
                parts.append(
                    f'<text x="{label_x:.1f}" y="{label_y:.1f}"'
                    f' font-size="10" fill="{_TEXT_FILL}"'
                    f' font-family="monospace" text-anchor="middle"'
                    f' dominant-baseline="middle">{_esc(eg.entity_id[:20])}</text>'
                )

    parts.append("</svg>")
    return "\n".join(parts)


def generate_overlay(
    native_obs: GeometryObservation,
    ref_obs: GeometryObservation,
) -> str:
    """Generate an overlay SVG showing native (blue) and reference (red) geometry."""
    all_bounds = [
        b for b in [
            native_obs.canvas_bounds, native_obs.content_bounds,
            ref_obs.canvas_bounds, ref_obs.content_bounds,
        ]
        if b is not None
    ]
    if all_bounds:
        min_x = min(b.x for b in all_bounds)
        min_y = min(b.y for b in all_bounds)
        max_x = max(b.right for b in all_bounds)
        max_y = max(b.bottom for b in all_bounds)
        vb = f"{min_x:.0f} {min_y:.0f} {(max_x - min_x):.0f} {(max_y - min_y):.0f}"
        vw = int(max_x - min_x)
        vh = int(max_y - min_y)
    else:
        vw, vh = 800, 600
        vb = f"0 0 {vw} {vh}"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{vw}" height="{vh}"'
        f' viewBox="{vb}" style="background:#fafafa;">'
    ]

    # Native = blue
    for eg in native_obs.entities:
        b = eg.bbox
        parts.append(
            f'<rect x="{b.x:.1f}" y="{b.y:.1f}" width="{b.width:.1f}" height="{b.height:.1f}"'
            f' fill="rgba(60,100,200,0.1)" stroke="#3c64c8" stroke-width="1.5" rx="3"/>'
        )

    # Reference = red (dashed)
    for eg in ref_obs.entities:
        b = eg.bbox
        parts.append(
            f'<rect x="{b.x:.1f}" y="{b.y:.1f}" width="{b.width:.1f}" height="{b.height:.1f}"'
            f' fill="none" stroke="#c83c3c" stroke-width="1.5"'
            f' stroke-dasharray="4 3" rx="3"/>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
