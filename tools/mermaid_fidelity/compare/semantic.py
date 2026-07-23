"""Exact semantic comparison between two SemanticDiagram observations.

Semantic checks are hard gates. Styling differences (palette, shadows,
corner-radius) are ignored. Every declared strict field is checked for
missing, extra, and changed objects — not just subset membership.

Relation comparison uses a canonical multiset (Counter keyed on a
7-field tuple) to preserve multiplicity.  Two identical unlabeled A→B
edges compare as count 2, not count 1.

Containment tuples are always (child_id, parent_id).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_label, sort_entities, sort_relations, sort_ordered_events
from ..models import (
    Entity, Group, OrderedEvent, ParseObservation, Relation, SemanticDiagram,
)
from ..oracle_contract import OracleCheck, OracleResult, OracleStatus


# ── diff items ────────────────────────────────────────────────────────────────

@dataclass
class EntityDiff:
    entity_id: str
    field: str
    expected: Any
    actual: Any

    def __str__(self) -> str:
        return (
            f'changed entity id={self.entity_id!r}: {self.field}: '
            f'expected {self.expected!r}, got {self.actual!r}'
        )


@dataclass
class RelationDiff:
    relation_id: str
    field: str
    expected: Any
    actual: Any

    def __str__(self) -> str:
        return (
            f'changed relation id={self.relation_id!r}: {self.field}: '
            f'expected {self.expected!r}, got {self.actual!r}'
        )


@dataclass
class ParseDiff:
    field: str
    expected: Any
    actual: Any

    def __str__(self) -> str:
        return f'parse mismatch: {self.field}: expected {self.expected!r}, got {self.actual!r}'


# ── structured diff ───────────────────────────────────────────────────────────

@dataclass
class SemanticDiff:
    """Structured diff between expected and actual semantic diagrams."""
    missing_entities: list[str] = field(default_factory=list)   # ids in expected, absent in actual
    extra_entities: list[str] = field(default_factory=list)     # ids in actual, absent in expected
    changed_entities: list[EntityDiff] = field(default_factory=list)

    # Relations keyed as canonical 7-tuples — reported as (key_tuple, count_exp, count_act)
    missing_relations: list[tuple] = field(default_factory=list)
    extra_relations: list[tuple] = field(default_factory=list)
    changed_relations: list[RelationDiff] = field(default_factory=list)

    missing_groups: list[str] = field(default_factory=list)
    extra_groups: list[str] = field(default_factory=list)
    changed_groups: list[str] = field(default_factory=list)   # human-readable descriptions

    direction_mismatch: str | None = None     # "expected TB, got LR"
    diagram_type_mismatch: str | None = None

    parse_diffs: list[ParseDiff] = field(default_factory=list)

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
            and not self.parse_diffs
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
        for pd in self.parse_diffs:
            lines.append(str(pd))
        for eid in self.missing_entities:
            lines.append(f"missing entity: id={eid!r}")
        for eid in self.extra_entities:
            lines.append(f"extra entity: id={eid!r}")
        for d in self.changed_entities:
            lines.append(str(d))
        for key in self.missing_relations:
            lines.append(f"missing relation: {_rel_key_str(key)}")
        for key in self.extra_relations:
            lines.append(f"extra relation: {_rel_key_str(key)}")
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


def _rel_key_str(key: tuple) -> str:
    """Human-readable representation of a canonical relation key."""
    if len(key) >= 3:
        kind, src, dst = key[0], key[1], key[2]
        label = key[3] if len(key) > 3 else ""
        return f"edge(kind={kind!r}, source={src!r}, target={dst!r}, label={label!r})"
    return repr(key)


# ── comparison result ─────────────────────────────────────────────────────────

@dataclass
class SemanticComparisonResult:
    passed: bool
    diff: SemanticDiff
    strict_fields_checked: list[str]
    skipped_fields: list[str]           # fields not checked due to extractor gap


# ── parse comparison ──────────────────────────────────────────────────────────

def compare_parse(
    expected: ParseObservation,
    actual: ParseObservation,
) -> list[ParseDiff]:
    """Compare two ParseObservations; return a list of ParseDiff items.

    Outcomes:
    - both accept same diagram family → []
    - reference accepts, native rejects → ParseDiff on accepted
    - reference rejects, native accepts → ParseDiff on accepted
    - accepted family differs → ParseDiff on diagram_type
    - both reject with compatible categories → []
    """
    diffs: list[ParseDiff] = []

    if expected.accepted != actual.accepted:
        diffs.append(ParseDiff(
            field="accepted",
            expected=expected.accepted,
            actual=actual.accepted,
        ))
        return diffs  # accepted mismatch dominates

    if not expected.accepted:
        # Both rejected — compare normalized error category
        exp_cat = expected.error_category or "unknown"
        act_cat = actual.error_category or "unknown"
        if exp_cat != act_cat:
            diffs.append(ParseDiff(
                field="error_category",
                expected=exp_cat,
                actual=act_cat,
            ))
        return diffs

    # Both accepted
    if expected.diagram_type and actual.diagram_type:
        if _normalize_family(expected.diagram_type) != _normalize_family(actual.diagram_type):
            diffs.append(ParseDiff(
                field="diagram_type",
                expected=expected.diagram_type,
                actual=actual.diagram_type,
            ))

    return diffs


def _normalize_family(family: str) -> str:
    """Normalize Mermaid internal names to canonical families."""
    mapping = {
        "sequencediagram": "sequence",
        "erdiagram": "er",
        "classDiagram": "class",
        "stateDiagram": "state",
        "statediagram": "state",
        "statediagram-v2": "state",
        "architecture-beta": "architecture",
        "architecturebeta": "architecture",
        "graph": "flowchart",
    }
    return mapping.get(family.lower(), family.lower())


# ── canonical relation key ────────────────────────────────────────────────────

def _rel_multiset_key(r: Relation) -> tuple:
    """Canonical 7-field key for a relation, used in multiset comparison.

    Includes kind, source, target, label, arrow, cardinality fields, and identifying.
    Parallel relations (same src/dst/label/arrow) produce identical keys and are
    counted separately via Counter.
    """
    return (
        r.kind or "",
        r.source or "",
        r.target or "",
        canonical_label(r.label),
        "",  # arrow: excluded from comparison — reference oracle never extracts arrow type
        r.attributes.get("cardinality_src") or "",
        r.attributes.get("cardinality_dst") or "",
    )


# ── main comparator ───────────────────────────────────────────────────────────

def compare_semantic(
    expected: SemanticDiagram,
    actual: SemanticDiagram,
    strict_fields: list[str],
) -> SemanticComparisonResult:
    """Compare expected vs actual SemanticDiagram for the given strict fields.

    A field check is skipped (EXTRACTOR_GAP) when the expected diagram genuinely
    has no data for it (field is None/unavailable, not just empty).
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

            # Shape: compare explicitly — treat None on native side as distinct from a value.
            for eid in exp_ids & act_ids:
                exp_shape = exp_by_id[eid].shape
                act_shape = act_by_id[eid].shape
                # Only flag mismatch when reference has a shape; None on reference means
                # reference didn't extract it (not a mismatch signal).
                if exp_shape is not None and exp_shape != act_shape:
                    diff.changed_entities.append(EntityDiff(eid, "shape", exp_shape, act_shape))

        if "labels" in strict_fields:
            checked.append("labels")
            for eid in exp_ids & act_ids:
                exp_lbl = canonical_label(exp_by_id[eid].label)
                act_lbl = canonical_label(act_by_id[eid].label)
                if exp_lbl != act_lbl:
                    diff.changed_entities.append(EntityDiff(eid, "label", exp_lbl, act_lbl))

    if "relations" in strict_fields:
        checked.append("relations")
        # Counter-based multiset to preserve parallel edges.
        exp_counts: Counter = Counter(_rel_multiset_key(r) for r in expected.relations)
        act_counts: Counter = Counter(_rel_multiset_key(r) for r in actual.relations)

        for key in exp_counts:
            exp_n = exp_counts[key]
            act_n = act_counts.get(key, 0)
            if act_n < exp_n:
                for _ in range(exp_n - act_n):
                    diff.missing_relations.append(key)

        for key in act_counts:
            exp_n = exp_counts.get(key, 0)
            act_n = act_counts[key]
            if act_n > exp_n:
                for _ in range(act_n - exp_n):
                    diff.extra_relations.append(key)

    if "edge-endpoints" in strict_fields:
        checked.append("edge-endpoints")
        exp_endpoints: Counter = Counter((r.source, r.target) for r in expected.relations)
        act_endpoints: Counter = Counter((r.source, r.target) for r in actual.relations)
        all_pairs = set(exp_endpoints) | set(act_endpoints)
        for pair in all_pairs:
            exp_n = exp_endpoints.get(pair, 0)
            act_n = act_endpoints.get(pair, 0)
            if act_n < exp_n:
                diff.missing_relations.extend([pair] * (exp_n - act_n))
            elif act_n > exp_n:
                diff.extra_relations.extend([pair] * (act_n - exp_n))

    if "containment" in strict_fields:
        checked.append("containment")
        # First: check group existence
        exp_groups_by_id = {g.id: g for g in expected.groups}
        act_groups_by_id = {g.id: g for g in actual.groups}
        exp_gids = set(exp_groups_by_id)
        act_gids = set(act_groups_by_id)

        diff.missing_groups = sorted(exp_gids - act_gids)
        diff.extra_groups = sorted(act_gids - exp_gids)

        # For existing groups: check membership
        for gid in exp_gids & act_gids:
            exp_members = set(exp_groups_by_id[gid].members)
            act_members = set(act_groups_by_id[gid].members)
            missing_m = exp_members - act_members
            extra_m = act_members - exp_members
            if missing_m:
                diff.changed_groups.append(
                    f"group {gid!r}: missing members {sorted(missing_m)}"
                )
            if extra_m:
                diff.changed_groups.append(
                    f"group {gid!r}: extra members {sorted(extra_m)}"
                )
            # Parent group
            exp_parent = exp_groups_by_id[gid].parent_id
            act_parent = act_groups_by_id[gid].parent_id
            if exp_parent != act_parent:
                diff.changed_groups.append(
                    f"group {gid!r}: parent changed from {exp_parent!r} to {act_parent!r}"
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
        # Check ordering of common events (order is semantically meaningful)
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

    # parse check is handled at runner level to produce PARSE_MISMATCH status;
    # we include it in checked so that report knows it ran.
    if "parse" in strict_fields:
        checked.append("parse")

    passed = diff.is_empty()
    return SemanticComparisonResult(
        passed=passed,
        diff=diff,
        strict_fields_checked=checked,
        skipped_fields=skipped,
    )




def compare_semantic_oracle(
    native_diag: "SemanticDiagram | None",
    ref_diag: "SemanticDiagram | None",
) -> OracleResult:
    """Oracle-aware semantic comparison with status rules."""
    if ref_diag is None and native_diag is None:
        return OracleResult(status=OracleStatus.UNVALIDATED, diagnostics=("no diagrams on either side",))
    if ref_diag is None:
        return OracleResult(status=OracleStatus.EXTRACTOR_GAP, diagnostics=("reference side empty",))
    if native_diag is None:
        return OracleResult(status=OracleStatus.FAIL, diagnostics=("native side empty",))
    comparison = compare_semantic(ref_diag, native_diag, strict_fields=["entities", "relations"])
    lines = comparison.diff.to_lines()
    checks = (
        OracleCheck(
            name="entity_topology",
            passed=not comparison.diff.missing_entities and not comparison.diff.extra_entities,
        ),
        OracleCheck(
            name="relation_topology",
            passed=not comparison.diff.missing_relations and not comparison.diff.extra_relations,
        ),
    )
    status = OracleStatus.PASS if not lines else OracleStatus.FAIL
    return OracleResult(status=status, checks=checks, diagnostics=tuple(lines))


# ── Class diagram marker oracle ───────────────────────────────────────────────

def compare_class_diagram_markers(
    expected_markers: "list[tuple]",
    actual_edges: "list",
) -> "OracleResult":
    """Compare expected class-diagram marker semantics against actual RoutedEdge objects.

    Parameters
    ----------
    expected_markers:
        List of ``(edge_id, src_marker_kind_str, dst_marker_kind_str)`` tuples
        where marker kind strings match ``MarkerKind`` lowercase values
        (e.g. ``"none"``, ``"hollow_triangle"``, ``"filled_diamond"``).
    actual_edges:
        Sequence of ``RoutedEdge`` objects from a compiled ``FinalizedLayout``.

    Returns
    -------
    OracleResult
        PASS when every expected marker assertion matches the actual
        RoutedEdge.  FAIL when any marker mismatches.  EXTRACTOR_GAP when
        ``actual_edges`` is empty.  The result always carries at least one
        ``OracleCheck`` per expected marker end so callers can assert
        ``len(oracle_result.checks) > 0`` for diagrams that have markers.
    """
    if not actual_edges:
        return OracleResult(
            status=OracleStatus.EXTRACTOR_GAP,
            diagnostics=("no actual edges provided",),
        )

    # Build lookup by edge_id
    actual_by_id: dict = {re_obj.edge_id: re_obj for re_obj in actual_edges}

    checks: list[OracleCheck] = []
    diagnostics: list[str] = []

    for edge_id, exp_src_str, exp_dst_str in expected_markers:
        actual = actual_by_id.get(edge_id)
        if actual is None:
            # Edge not found in compiled layout
            diagnostics.append(f"edge_id {edge_id!r} not found in actual layout")
            checks.append(OracleCheck(
                name=f"{edge_id}:source_marker",
                passed=False,
                expected=exp_src_str,
                actual=None,
                diagnostic=f"edge_id {edge_id!r} missing from layout",
            ))
            checks.append(OracleCheck(
                name=f"{edge_id}:target_marker",
                passed=False,
                expected=exp_dst_str,
                actual=None,
                diagnostic=f"edge_id {edge_id!r} missing from layout",
            ))
            continue

        # Compare source marker
        actual_src = actual.source_marker.value if hasattr(actual.source_marker, "value") else str(actual.source_marker)
        src_ok = actual_src == exp_src_str
        checks.append(OracleCheck(
            name=f"{edge_id}:source_marker",
            passed=src_ok,
            expected=exp_src_str,
            actual=actual_src,
        ))
        if not src_ok:
            diagnostics.append(
                f"edge {edge_id!r} source_marker: expected {exp_src_str!r}, got {actual_src!r}"
            )

        # Compare target marker
        actual_dst = actual.target_marker.value if hasattr(actual.target_marker, "value") else str(actual.target_marker)
        dst_ok = actual_dst == exp_dst_str
        checks.append(OracleCheck(
            name=f"{edge_id}:target_marker",
            passed=dst_ok,
            expected=exp_dst_str,
            actual=actual_dst,
        ))
        if not dst_ok:
            diagnostics.append(
                f"edge {edge_id!r} target_marker: expected {exp_dst_str!r}, got {actual_dst!r}"
            )

    if not checks:
        return OracleResult(
            status=OracleStatus.EXTRACTOR_GAP,
            diagnostics=("no marker expectations provided",),
        )

    all_passed = all(c.passed for c in checks)
    status = OracleStatus.PASS if all_passed else OracleStatus.FAIL
    return OracleResult(
        status=status,
        checks=tuple(checks),
        diagnostics=tuple(diagnostics),
    )
