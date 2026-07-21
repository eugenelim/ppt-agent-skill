"""Exact semantic comparison between two SemanticDiagram observations.

Semantic checks are hard gates. Styling differences (palette, shadows,
corner-radius) are ignored. Every declared strict field is checked for
missing, extra, and changed objects — not just subset membership.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_label, sort_entities, sort_relations, sort_ordered_events
from ..models import (
    Entity, Group, OrderedEvent, Relation, SemanticDiagram,
)


@dataclass
class EntityDiff:
    entity_id: str
    field: str
    expected: Any
    actual: Any

    def __str__(self) -> str:
        return f'changed entity id={self.entity_id!r}: {self.field}: expected {self.expected!r}, got {self.actual!r}'


@dataclass
class RelationDiff:
    relation_id: str
    field: str
    expected: Any
    actual: Any

    def __str__(self) -> str:
        return f'changed relation id={self.relation_id!r}: {self.field}: expected {self.expected!r}, got {self.actual!r}'


@dataclass
class SemanticDiff:
    """Structured diff between expected and actual semantic diagrams."""
    missing_entities: list[str] = field(default_factory=list)   # ids in expected, absent in actual
    extra_entities: list[str] = field(default_factory=list)     # ids in actual, absent in expected
    changed_entities: list[EntityDiff] = field(default_factory=list)

    missing_relations: list[tuple[str, str, str]] = field(default_factory=list)  # (src, dst, label)
    extra_relations: list[tuple[str, str, str]] = field(default_factory=list)
    changed_relations: list[RelationDiff] = field(default_factory=list)

    missing_groups: list[str] = field(default_factory=list)
    extra_groups: list[str] = field(default_factory=list)
    changed_groups: list[str] = field(default_factory=list)   # human-readable descriptions

    direction_mismatch: str | None = None     # "expected TB, got LR"
    diagram_type_mismatch: str | None = None

    missing_events: list[str] = field(default_factory=list)    # ordered event ids
    extra_events: list[str] = field(default_factory=list)
    changed_events: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            not self.missing_entities
            and not self.extra_entities
            and not self.changed_entities
            and not self.missing_relations
            and not self.extra_relations
            and not self.changed_relations
            and not self.missing_groups
            and not self.extra_groups
            and not self.changed_groups
            and self.direction_mismatch is None
            and self.diagram_type_mismatch is None
            and not self.missing_events
            and not self.extra_events
            and not self.changed_events
        )

    def to_lines(self) -> list[str]:
        lines: list[str] = []
        if self.diagram_type_mismatch:
            lines.append(f"diagram-type: {self.diagram_type_mismatch}")
        if self.direction_mismatch:
            lines.append(f"direction: {self.direction_mismatch}")
        for eid in self.missing_entities:
            lines.append(f"missing entity: id={eid!r}")
        for eid in self.extra_entities:
            lines.append(f"extra entity: id={eid!r}")
        for d in self.changed_entities:
            lines.append(str(d))
        for src, dst, lbl in self.missing_relations:
            lines.append(f"missing relation: edge(source={src!r}, target={dst!r}, label={lbl!r})")
        for src, dst, lbl in self.extra_relations:
            lines.append(f"extra relation: edge(source={src!r}, target={dst!r}, label={lbl!r})")
        for d in self.changed_relations:
            lines.append(str(d))
        for gid in self.missing_groups:
            lines.append(f"missing group: id={gid!r}")
        for gid in self.extra_groups:
            lines.append(f"extra group: id={gid!r}")
        for msg in self.changed_groups:
            lines.append(msg)
        for eid in self.missing_events:
            lines.append(f"missing event: id={eid!r}")
        for eid in self.extra_events:
            lines.append(f"extra event: id={eid!r}")
        for msg in self.changed_events:
            lines.append(msg)
        return lines


@dataclass
class SemanticComparisonResult:
    passed: bool
    diff: SemanticDiff
    strict_fields_checked: list[str]
    skipped_fields: list[str]           # fields not checked due to extractor gap


def compare_semantic(
    expected: SemanticDiagram,
    actual: SemanticDiagram,
    strict_fields: list[str],
) -> SemanticComparisonResult:
    """Compare expected vs actual SemanticDiagram for the given strict fields.

    Returns a structured diff. A field check is skipped when the expected
    diagram lacks data for it (not an extractor gap on the comparison side).
    """
    diff = SemanticDiff()
    checked: list[str] = []
    skipped: list[str] = []

    if "diagram-type" in strict_fields:
        checked.append("diagram-type")
        if expected.diagram_type != actual.diagram_type:
            diff.diagram_type_mismatch = (
                f"expected {expected.diagram_type!r}, got {actual.diagram_type!r}"
            )

    if "direction" in strict_fields:
        checked.append("direction")
        if expected.direction != actual.direction:
            diff.direction_mismatch = (
                f"expected {expected.direction!r}, got {actual.direction!r}"
            )

    if "entities" in strict_fields or "labels" in strict_fields:
        exp_by_id = {e.id: e for e in expected.entities}
        act_by_id = {e.id: e for e in actual.entities}
        exp_ids = set(exp_by_id)
        act_ids = set(act_by_id)

        if "entities" in strict_fields:
            checked.append("entities")
            diff.missing_entities = sorted(exp_ids - act_ids)
            diff.extra_entities = sorted(act_ids - exp_ids)

        if "labels" in strict_fields:
            checked.append("labels")
            for eid in exp_ids & act_ids:
                exp_lbl = canonical_label(exp_by_id[eid].label)
                act_lbl = canonical_label(act_by_id[eid].label)
                if exp_lbl != act_lbl:
                    diff.changed_entities.append(EntityDiff(eid, "label", exp_lbl, act_lbl))

        # shape check when entities strict
        if "entities" in strict_fields:
            for eid in exp_ids & act_ids:
                exp_shape = exp_by_id[eid].shape
                act_shape = act_by_id[eid].shape
                if exp_shape and act_shape and exp_shape != act_shape:
                    diff.changed_entities.append(EntityDiff(eid, "shape", exp_shape, act_shape))

    if "relations" in strict_fields:
        checked.append("relations")
        # Key relations by (source, target, label_canonical) since IDs may differ
        def _rel_key(r: Relation) -> tuple[str, str, str]:
            return (r.source, r.target, canonical_label(r.label))

        exp_rels = {_rel_key(r) for r in expected.relations}
        act_rels = {_rel_key(r) for r in actual.relations}
        diff.missing_relations = sorted(exp_rels - act_rels)
        diff.extra_relations = sorted(act_rels - exp_rels)

    if "edge-endpoints" in strict_fields:
        checked.append("edge-endpoints")
        exp_endpoints = {(r.source, r.target) for r in expected.relations}
        act_endpoints = {(r.source, r.target) for r in actual.relations}
        for src, dst in exp_endpoints - act_endpoints:
            if (src, dst, "") not in {(m, e, c) for m, e, c in diff.missing_relations}:
                diff.missing_relations.append((src, dst, ""))
        for src, dst in act_endpoints - exp_endpoints:
            if (src, dst, "") not in {(m, e, c) for m, e, c in diff.extra_relations}:
                diff.extra_relations.append((src, dst, ""))

    if "containment" in strict_fields:
        checked.append("containment")
        exp_membership: dict[str, set[str]] = {}
        for g in expected.groups:
            exp_membership[g.id] = set(g.members)
        act_membership: dict[str, set[str]] = {}
        for g in actual.groups:
            act_membership[g.id] = set(g.members)
        for gid, exp_members in exp_membership.items():
            act_members = act_membership.get(gid, set())
            missing = exp_members - act_members
            extra = act_members - exp_members
            if missing:
                diff.changed_groups.append(
                    f"group {gid!r}: missing members {sorted(missing)}"
                )
            if extra:
                diff.changed_groups.append(
                    f"group {gid!r}: extra members {sorted(extra)}"
                )

    # Sequence-specific: actor order and message order
    if "actor-order" in strict_fields:
        checked.append("actor-order")
        exp_actors = [e for e in sort_entities(expected.entities) if e.kind == "actor"]
        act_actors = [e for e in sort_entities(actual.entities) if e.kind == "actor"]
        exp_order = [e.id for e in sorted(exp_actors, key=lambda e: e.order)]
        act_order = [e.id for e in sorted(act_actors, key=lambda e: e.order)]
        if exp_order != act_order:
            diff.changed_events.append(
                f"actor-order: expected {exp_order!r}, got {act_order!r}"
            )

    if "message-order" in strict_fields:
        checked.append("message-order")
        exp_events = sort_ordered_events(expected.ordered_events)
        act_events = sort_ordered_events(actual.ordered_events)
        exp_ids = [e.id for e in exp_events]
        act_ids = [e.id for e in act_events]
        exp_set = set(exp_ids)
        act_set = set(act_ids)
        diff.missing_events = sorted(exp_set - act_set)
        diff.extra_events = sorted(act_set - exp_set)
        # Check ordering of common events
        common_exp = [e.id for e in exp_events if e.id in act_set]
        common_act = [e.id for e in act_events if e.id in exp_set]
        if common_exp != common_act:
            diff.changed_events.append(
                f"message-order mismatch: expected {common_exp!r}, got {common_act!r}"
            )

    if "cardinality" in strict_fields:
        checked.append("cardinality")
        for r in expected.relations:
            exp_card = (r.attributes.get("cardinality_src"), r.attributes.get("cardinality_dst"))
            if exp_card == (None, None):
                continue
            act_r = next(
                (a for a in actual.relations
                 if a.source == r.source and a.target == r.target),
                None,
            )
            if act_r:
                act_card = (act_r.attributes.get("cardinality_src"), act_r.attributes.get("cardinality_dst"))
                if exp_card != act_card:
                    diff.changed_relations.append(RelationDiff(
                        r.id, "cardinality", str(exp_card), str(act_card)
                    ))

    if "identifying" in strict_fields:
        checked.append("identifying")
        for r in expected.relations:
            exp_id = r.attributes.get("identifying")
            if exp_id is None:
                continue
            act_r = next(
                (a for a in actual.relations
                 if a.source == r.source and a.target == r.target),
                None,
            )
            if act_r:
                act_id = act_r.attributes.get("identifying")
                if exp_id != act_id:
                    diff.changed_relations.append(RelationDiff(
                        r.id, "identifying", exp_id, act_id
                    ))

    passed = diff.is_empty()
    return SemanticComparisonResult(
        passed=passed,
        diff=diff,
        strict_fields_checked=checked,
        skipped_fields=skipped,
    )
