"""Mutation tests for semantic comparator.

Tests that structural mutations (dropped node, renamed node, extra node, etc.)
trigger the comparator, while palette-only mutations do NOT trigger semantic
differences.

All 12 mutations:
 1. dropped_node           — must trigger (entity missing)
 2. renamed_node_label     — must trigger (label mismatch)
 3. extra_node             — must trigger (extra entity)
 4. dropped_edge           — must trigger (relation missing)
 5. extra_edge             — must trigger (extra relation)
 6. reversed_edge          — must trigger (src/dst swapped)
 7. node_becomes_group     — must trigger (kind change / containment change)
 8. group_dropped          — must trigger (group missing)
 9. diagram_type_changed   — must trigger (type mismatch)
10. direction_changed      — must trigger (direction mismatch under strict)
11. edge_label_changed     — must trigger (label mismatch)
12. palette_only_change    — must NOT trigger semantic difference
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "tools"))

from mermaid_fidelity.models import (
    Entity,
    Group,
    Relation,
    SemanticDiagram,
)
from mermaid_fidelity.compare.semantic import compare_semantic, SemanticDiff


def _e(eid: str, label: str = "", kind: str = "node", parent_id: str | None = None) -> Entity:
    return Entity(id=eid, kind=kind, label=label or eid, shape="rect",
                  parent_id=parent_id, order=0)


def _r(src: str, dst: str, label: str = "", order: int = 0) -> Relation:
    return Relation(id=f"{src}__{dst}__{order}", kind="edge", source=src, target=dst,
                    label=label, arrow=None, order=order)


def _g(gid: str, members: list[str]) -> Group:
    return Group(id=gid, kind="subgraph", label=gid, parent_id=None, order=0, members=members)


def _sd(entities=None, relations=None, groups=None, diagram_type="flowchart",
        direction="LR") -> SemanticDiagram:
    return SemanticDiagram(
        diagram_type=diagram_type,
        direction=direction,
        entities=entities or [],
        relations=relations or [],
        groups=groups or [],
    )


_FULL_STRICT = ["diagram-type", "direction", "entities", "labels", "relations", "edge-endpoints", "containment"]


def _must_trigger(expected: SemanticDiagram, actual: SemanticDiagram,
                  strict_fields: list[str] | None = None) -> SemanticDiff:
    result = compare_semantic(expected, actual, strict_fields=strict_fields or _FULL_STRICT)
    assert not result.diff.is_empty(), (
        f"Expected diff to be non-empty but got empty diff.\n"
        f"Lines: {result.diff.to_lines()}"
    )
    return result.diff


def _must_not_trigger(expected: SemanticDiagram, actual: SemanticDiagram,
                      strict_fields: list[str] | None = None):
    result = compare_semantic(expected, actual, strict_fields=strict_fields or _FULL_STRICT)
    assert result.diff.is_empty(), (
        f"Expected empty diff but got:\n{chr(10).join(result.diff.to_lines())}"
    )


# ── base diagram ─────────────────────────────────────────────────────────────

_BASE_ENTITIES = [_e("A"), _e("B"), _e("C")]
_BASE_RELATIONS = [_r("A", "B"), _r("B", "C")]
_BASE = _sd(entities=_BASE_ENTITIES, relations=_BASE_RELATIONS)


# ── mutation 1: dropped node ──────────────────────────────────────────────────

def test_mutation_dropped_node():
    mutated = _sd(entities=[_e("A"), _e("C")], relations=_BASE_RELATIONS)
    diff = _must_trigger(_BASE, mutated)
    assert any("B" in str(e) for e in diff.missing_entities)


# ── mutation 2: renamed node label ────────────────────────────────────────────

def test_mutation_renamed_node_label():
    mutated = _sd(
        entities=[_e("A"), _e("B", label="BEE"), _e("C")],
        relations=_BASE_RELATIONS,
    )
    _must_trigger(_BASE, mutated)


# ── mutation 3: extra node ────────────────────────────────────────────────────

def test_mutation_extra_node():
    mutated = _sd(
        entities=_BASE_ENTITIES + [_e("D")],
        relations=_BASE_RELATIONS,
    )
    diff = _must_trigger(_BASE, mutated)
    assert any("D" in str(e) for e in diff.extra_entities)


# ── mutation 4: dropped edge ──────────────────────────────────────────────────

def test_mutation_dropped_edge():
    mutated = _sd(entities=_BASE_ENTITIES, relations=[_r("A", "B")])
    _must_trigger(_BASE, mutated)


# ── mutation 5: extra edge ────────────────────────────────────────────────────

def test_mutation_extra_edge():
    mutated = _sd(entities=_BASE_ENTITIES, relations=_BASE_RELATIONS + [_r("A", "C")])
    _must_trigger(_BASE, mutated)


# ── mutation 6: reversed edge ─────────────────────────────────────────────────

def test_mutation_reversed_edge():
    mutated = _sd(
        entities=_BASE_ENTITIES,
        relations=[_r("B", "A"), _r("B", "C")],
    )
    _must_trigger(_BASE, mutated)


# ── mutation 7: node becomes group (kind change) ──────────────────────────────

def test_mutation_node_becomes_group():
    base_with_group = _sd(
        entities=[_e("A"), _e("B", kind="group"), _e("C")],
        relations=_BASE_RELATIONS,
        groups=[_g("B", members=["C"])],
    )
    mutated = _sd(
        entities=[_e("A"), _e("B", kind="node"), _e("C")],
        relations=_BASE_RELATIONS,
        groups=[],
    )
    _must_trigger(base_with_group, mutated)


# ── mutation 8: group dropped ─────────────────────────────────────────────────

def test_mutation_group_dropped():
    base_with_group = _sd(
        entities=_BASE_ENTITIES,
        relations=_BASE_RELATIONS,
        groups=[_g("G1", members=["A", "B"])],
    )
    mutated = _sd(entities=_BASE_ENTITIES, relations=_BASE_RELATIONS, groups=[])
    _must_trigger(base_with_group, mutated)


# ── mutation 9: diagram type changed ─────────────────────────────────────────

def test_mutation_diagram_type_changed():
    base = _sd(diagram_type="flowchart")
    mutated = _sd(diagram_type="er")
    _must_trigger(base, mutated, strict_fields=["diagram-type", "entities", "relations"])


# ── mutation 10: direction changed (strict) ───────────────────────────────────

def test_mutation_direction_changed_strict():
    base = _sd(direction="LR")
    mutated = _sd(direction="TB")
    _must_trigger(base, mutated, strict_fields=["diagram-type", "direction", "entities", "relations"])


def test_mutation_direction_changed_non_strict():
    base = _sd(direction="LR")
    mutated = _sd(direction="TB")
    _must_not_trigger(base, mutated, strict_fields=["diagram-type", "entities", "relations"])


# ── mutation 11: edge label changed ──────────────────────────────────────────

def test_mutation_edge_label_changed():
    base = _sd(
        entities=[_e("A"), _e("B")],
        relations=[_r("A", "B", label="yes")],
    )
    mutated = _sd(
        entities=[_e("A"), _e("B")],
        relations=[_r("A", "B", label="no")],
    )
    _must_trigger(base, mutated)


# ── mutation 12: palette-only change must NOT trigger ─────────────────────────

def test_mutation_palette_only_no_trigger():
    """Changing colors/styles without structural changes must not cause semantic diff."""
    # Same topology; the "palette" distinction is that no structural field changes.
    # In our semantic model, palette is not stored — so this is the identity case.
    base = _sd(entities=[_e("A"), _e("B")], relations=[_r("A", "B")])
    palette_mutated = _sd(entities=[_e("A"), _e("B")], relations=[_r("A", "B")])
    _must_not_trigger(base, palette_mutated)
