"""Canonical ordering and normalization helpers for semantic comparison."""
from __future__ import annotations

import html
import re

from .models import Entity, Group, OrderedEvent, Relation, SemanticDiagram


def canonical_label(raw: str) -> str:
    """Normalize a display label for comparison.

    Decodes HTML entities, strips leading/trailing whitespace,
    collapses internal whitespace runs to a single space.
    """
    decoded = html.unescape(raw)
    return re.sub(r"\s+", " ", decoded.strip())


def sort_entities(entities: list[Entity]) -> list[Entity]:
    return sorted(entities, key=lambda e: (e.id, e.kind))


def sort_relations(relations: list[Relation]) -> list[Relation]:
    return sorted(relations, key=lambda r: (r.source, r.target, r.label, r.order))


def sort_groups(groups: list[Group]) -> list[Group]:
    return sorted(groups, key=lambda g: g.id)


def sort_ordered_events(events: list[OrderedEvent]) -> list[OrderedEvent]:
    return sorted(events, key=lambda e: (e.order, e.id))


def canonical_semantic(diagram: SemanticDiagram) -> SemanticDiagram:
    """Return diagram with all collections in canonical order."""
    return SemanticDiagram(
        diagram_type=diagram.diagram_type,
        direction=diagram.direction,
        entities=sort_entities(diagram.entities),
        relations=sort_relations(diagram.relations),
        groups=sort_groups(diagram.groups),
        ordered_events=sort_ordered_events(diagram.ordered_events),
        metadata=dict(sorted(diagram.metadata.items())),
    )


def stable_relation_id(src: str, dst: str, order: int) -> str:
    """Generate a stable relation ID from endpoints and position index."""
    safe_src = re.sub(r"[^\w-]", "_", src)
    safe_dst = re.sub(r"[^\w-]", "_", dst)
    return f"{safe_src}__{safe_dst}__{order}" if order > 0 else f"{safe_src}__{safe_dst}"
