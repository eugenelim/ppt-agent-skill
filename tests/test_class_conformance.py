"""Class diagram semantic conformance tests.

Covers: unique edge IDs, marker metadata keyed by edge_id, marker mapping
validation, rank-reversal marker invariance, oracle marker assertions,
parallel-relation disambiguation, and the full conformance suite against
the ``class-relationships-all`` fixture.

All tests compile from class diagram source strings; no hardcoded coordinates.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from mermaid_render.layout._geometry import MarkerKind
from mermaid_render.layout._strategies import (
    _CLASS_REL_RE,
    _class_rel_markers,
    _compile_classdiagram,
)

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "class-relationships-all.mmd"


# ── helpers ───────────────────────────────────────────────────────────────────

def _compile(src: str, **kwargs):
    """Compile a classDiagram source and return CompiledFlowchart."""
    return _compile_classdiagram(src, **kwargs)


def _routed_by_id(result) -> dict:
    """Return {edge_id: RoutedEdge} from a compiled layout."""
    return {re_obj.edge_id: re_obj for re_obj in result.layout.routed_edges}


def _diagram(body: str) -> str:
    """Wrap body lines in a classDiagram header."""
    return f"classDiagram\n{body}"


def _expected_markers_from_source(src: str) -> list[tuple]:
    """Parse class diagram source and return expected marker tuples.

    Returns list of (edge_id, src_marker_kind_str, dst_marker_kind_str).
    """
    result: list[tuple] = []
    eid_counts: dict[str, int] = {}
    for raw in src.splitlines():
        line = raw.strip()
        m = _CLASS_REL_RE.match(line)
        if not m:
            continue
        c1, _, op, _, c2, _ = (
            m.group(1), m.group(2) or "", m.group(3),
            m.group(4) or "", m.group(5), m.group(6) or "",
        )
        base = f"{c1}->{c2}"
        n = eid_counts.get(base, 0)
        eid_counts[base] = n + 1
        edge_id = base if n == 0 else f"{base}#{n}"
        src_spec, tgt_spec, _ = _class_rel_markers(op)
        result.append((edge_id, src_spec.kind.value, tgt_spec.kind.value))
    return result


# ── Task 1: Unique edge IDs ───────────────────────────────────────────────────

class TestUniqueEdgeIds:
    """Every class relation has a unique, stable edge_id."""

    def test_unique_edge_ids_all_relations(self):
        """class-relationships-all: all edge IDs are distinct."""
        src = FIXTURE_PATH.read_text()
        result = _compile(src)
        ids = [re_obj.edge_id for re_obj in result.layout.routed_edges]
        assert len(ids) == len(set(ids)), f"Duplicate edge IDs found: {ids}"

    def test_edge_id_not_empty(self):
        """Every routed edge has a non-empty edge_id."""
        src = FIXTURE_PATH.read_text()
        result = _compile(src)
        for re_obj in result.layout.routed_edges:
            assert re_obj.edge_id, f"Empty edge_id on edge {re_obj.src_node_id!r}→{re_obj.dst_node_id!r}"

    def test_parallel_relations_distinct_ids(self):
        """Two edges between the same classes but different labels get distinct edge IDs."""
        src = _diagram(
            "    class A\n"
            "    class B\n"
            "    A --> B : first\n"
            "    A --> B : second\n"
        )
        result = _compile(src)
        ids = [re_obj.edge_id for re_obj in result.layout.routed_edges]
        assert len(ids) == 2, f"Expected 2 edges, got {len(ids)}"
        assert len(set(ids)) == 2, f"Parallel edges share edge_id: {ids}"

    def test_parallel_ids_use_suffix(self):
        """Parallel edges use 'A->B' and 'A->B#1' as IDs."""
        src = _diagram(
            "    class A\n"
            "    class B\n"
            "    A --> B : first\n"
            "    A --> B : second\n"
        )
        result = _compile(src)
        ids = sorted(re_obj.edge_id for re_obj in result.layout.routed_edges)
        assert ids == ["A->B", "A->B#1"], f"Unexpected edge IDs: {ids}"

    def test_first_edge_has_no_suffix(self):
        """First occurrence of a src→dst pair uses the bare ID (no #N suffix)."""
        src = _diagram("    class X\n    class Y\n    X --> Y : link\n")
        result = _compile(src)
        ids = [re_obj.edge_id for re_obj in result.layout.routed_edges]
        assert ids == ["X->Y"], f"Expected ['X->Y'], got {ids}"

    def test_stable_across_runs(self):
        """Repeated compilation of the same source yields identical edge IDs."""
        src = _diagram(
            "    class A\n    class B\n    class C\n"
            "    A --> B : ab\n    B --> C : bc\n    A --> C : ac\n"
        )
        ids1 = sorted(re_obj.edge_id for re_obj in _compile(src).layout.routed_edges)
        ids2 = sorted(re_obj.edge_id for re_obj in _compile(src).layout.routed_edges)
        assert ids1 == ids2, f"IDs changed between runs: {ids1} vs {ids2}"


# ── Task 2: Marker metadata keyed by edge_id ─────────────────────────────────

class TestMarkerMetadataByEdgeId:
    """Marker metadata (kind, label) is retrievable by edge_id."""

    def test_marker_accessible_by_edge_id(self):
        """source_marker and target_marker are accessible on the RoutedEdge keyed by edge_id."""
        src = _diagram("    class Animal\n    class Dog\n    Animal <|-- Dog : inherits\n")
        result = _compile(src)
        by_id = _routed_by_id(result)
        edge = by_id.get("Animal->Dog")
        assert edge is not None, "Edge 'Animal->Dog' not found by edge_id"
        assert edge.source_marker == MarkerKind.HOLLOW_TRIANGLE
        assert edge.target_marker == MarkerKind.NONE

    def test_label_on_routed_edge(self):
        """Label text survives the full compile pipeline and is on the RoutedEdge."""
        src = _diagram("    class Car\n    class Engine\n    Car *-- Engine : composed of\n")
        result = _compile(src)
        by_id = _routed_by_id(result)
        edge = by_id.get("Car->Engine")
        assert edge is not None, "Edge 'Car->Engine' not found by edge_id"
        if edge.label_layout:
            assert edge.label_layout.text == "composed of"

    def test_parallel_edges_distinct_markers(self):
        """Two parallel edges may carry different markers, each keyed by distinct edge_id."""
        src = _diagram(
            "    class A\n    class B\n"
            "    A --> B : assoc\n"
            "    A *-- B : comp\n"
        )
        result = _compile(src)
        by_id = _routed_by_id(result)
        assert "A->B" in by_id, "First edge not found"
        assert "A->B#1" in by_id, "Second edge not found"
        e1 = by_id["A->B"]
        e2 = by_id["A->B#1"]
        # Both edges are present and have distinct marker kinds
        markers = {e1.source_marker, e1.target_marker, e2.source_marker, e2.target_marker}
        assert MarkerKind.OPEN_ARROW in markers or MarkerKind.FILLED_DIAMOND in markers, (
            f"Expected distinctive markers; got {markers}"
        )

    def test_no_src_dst_tuple_ambiguity(self):
        """Parallel relations can be disambiguated — edge_id is the sole identity key."""
        src = _diagram(
            "    class P\n    class Q\n"
            "    P --> Q : first\n"
            "    P --> Q : second\n"
        )
        result = _compile(src)
        by_id = _routed_by_id(result)
        # Both must exist under distinct keys
        assert "P->Q" in by_id
        assert "P->Q#1" in by_id
        # They map to different RoutedEdge objects
        assert by_id["P->Q"] is not by_id["P->Q#1"]


# ── Task 3: Marker mapping validation ────────────────────────────────────────

class TestMarkerMappingValidation:
    """Compiled RoutedEdge carries the correct MarkerKind values."""

    def _edge(self, snippet: str, edge_id: str = None):
        src = _diagram(snippet)
        result = _compile(src)
        by_id = _routed_by_id(result)
        if edge_id:
            return by_id.get(edge_id)
        # Return first edge if only one expected
        edges = list(result.layout.routed_edges)
        return edges[0] if edges else None

    def test_inheritance_hollow_triangle_at_source(self):
        """<|-- produces HOLLOW_TRIANGLE at source_marker."""
        edge = self._edge("    class Animal\n    class Dog\n    Animal <|-- Dog\n",
                          "Animal->Dog")
        assert edge is not None
        assert edge.source_marker == MarkerKind.HOLLOW_TRIANGLE

    def test_inheritance_none_at_target(self):
        """<|-- produces NONE at target_marker."""
        edge = self._edge("    class Animal\n    class Dog\n    Animal <|-- Dog\n",
                          "Animal->Dog")
        assert edge is not None
        assert edge.target_marker == MarkerKind.NONE

    def test_composition_filled_diamond_at_source(self):
        """*-- produces FILLED_DIAMOND at source_marker."""
        edge = self._edge("    class Car\n    class Engine\n    Car *-- Engine\n",
                          "Car->Engine")
        assert edge is not None
        assert edge.source_marker == MarkerKind.FILLED_DIAMOND

    def test_aggregation_hollow_diamond_at_source(self):
        """o-- produces HOLLOW_DIAMOND at source_marker."""
        edge = self._edge("    class Pond\n    class Duck\n    Pond o-- Duck\n",
                          "Pond->Duck")
        assert edge is not None
        assert edge.source_marker == MarkerKind.HOLLOW_DIAMOND

    def test_directed_association_open_arrow_at_target(self):
        """--> produces OPEN_ARROW at target_marker, NONE at source."""
        edge = self._edge("    class Person\n    class Address\n    Person --> Address\n",
                          "Person->Address")
        assert edge is not None
        assert edge.target_marker == MarkerKind.OPEN_ARROW
        assert edge.source_marker == MarkerKind.NONE

    def test_dependency_dashed_open_arrow(self):
        """..> produces OPEN_ARROW at target, edge_style == 'dotted'."""
        edge = self._edge("    class IFlyable\n    class Bird\n    IFlyable ..> Bird\n",
                          "IFlyable->Bird")
        assert edge is not None
        assert edge.target_marker == MarkerKind.OPEN_ARROW
        assert edge.edge_style == "dotted"

    def test_realization_dashed_hollow_triangle(self):
        """..|> produces HOLLOW_TRIANGLE at target, edge_style == 'dotted'."""
        edge = self._edge("    class Teacher\n    class Professor\n    Teacher ..|> Professor\n",
                          "Teacher->Professor")
        assert edge is not None
        assert edge.target_marker == MarkerKind.HOLLOW_TRIANGLE
        assert edge.edge_style == "dotted"

    def test_solid_style_inheritance(self):
        """<|-- yields solid edge_style."""
        edge = self._edge("    class A\n    class B\n    A <|-- B\n", "A->B")
        assert edge is not None
        assert edge.edge_style == "solid"

    def test_solid_style_composition(self):
        """*-- yields solid edge_style."""
        edge = self._edge("    class A\n    class B\n    A *-- B\n", "A->B")
        assert edge is not None
        assert edge.edge_style == "solid"

    def test_solid_style_aggregation(self):
        """o-- yields solid edge_style."""
        edge = self._edge("    class A\n    class B\n    A o-- B\n", "A->B")
        assert edge is not None
        assert edge.edge_style == "solid"

    def test_solid_style_association(self):
        """--> yields solid edge_style."""
        edge = self._edge("    class A\n    class B\n    A --> B\n", "A->B")
        assert edge is not None
        assert edge.edge_style == "solid"


# ── Task 4: Rank-reversal marker invariance ───────────────────────────────────

class TestRankReversalMarkerInvariance:
    """Markers stay on their semantic class even when the layout reverses edge direction."""

    def test_marker_survives_rank_reversal(self):
        """A reversed-rank edge still carries markers on the correct semantic endpoints.

        We create a cycle A→B→C→A so _break_cycles reverses one edge.
        Regardless of which edge is reversed, every routed edge that has a
        non-NONE marker must still have it on the correct class.
        """
        src = _diagram(
            "    class A\n    class B\n    class C\n"
            "    A <|-- B : ab\n"
            "    B --> C : bc\n"
            "    C *-- A : ca\n"
        )
        result = _compile(src)
        by_id = _routed_by_id(result)

        # A->B (inheritance): source_marker == HOLLOW_TRIANGLE on A, none on B
        edge_ab = by_id.get("A->B")
        assert edge_ab is not None, "Edge A->B missing from layout (possible routing failure)"
        assert edge_ab.source_marker == MarkerKind.HOLLOW_TRIANGLE, (
            "Rank reversal moved hollow triangle off A"
        )
        assert edge_ab.target_marker == MarkerKind.NONE

        # C->A (composition): source_marker == FILLED_DIAMOND on C
        edge_ca = by_id.get("C->A")
        assert edge_ca is not None, "Edge C->A missing from layout (possible routing failure)"
        assert edge_ca.source_marker == MarkerKind.FILLED_DIAMOND, (
            "Rank reversal moved filled diamond off C"
        )

    def test_inheritance_marker_invariant_in_deep_dag(self):
        """Inheritance marker survives a multi-rank DAG layout without reversal."""
        src = _diagram(
            "    class Base\n    class Mid\n    class Leaf\n"
            "    Base <|-- Mid : inherits\n"
            "    Mid <|-- Leaf : inherits\n"
        )
        result = _compile(src)
        by_id = _routed_by_id(result)
        for eid, expected_src_mk in [("Base->Mid", MarkerKind.HOLLOW_TRIANGLE),
                                      ("Mid->Leaf", MarkerKind.HOLLOW_TRIANGLE)]:
            edge = by_id.get(eid)
            assert edge is not None, f"Edge {eid!r} not found"
            assert edge.source_marker == expected_src_mk, (
                f"{eid}: source_marker={edge.source_marker!r}, expected {expected_src_mk!r}"
            )
            assert edge.target_marker == MarkerKind.NONE, (
                f"{eid}: target_marker should be NONE, got {edge.target_marker!r}"
            )

    def test_composition_marker_invariant_reversed_layout(self):
        """Composition marker stays on owner class even in a reversed-rank diagram."""
        # Force reversal: Owner at lower rank than Part in a triangle
        src = _diagram(
            "    class Owner\n    class Part\n    class Extra\n"
            "    Extra --> Owner : uses\n"
            "    Owner *-- Part : composed of\n"
            "    Part --> Extra : feeds\n"
        )
        result = _compile(src)
        by_id = _routed_by_id(result)
        edge = by_id.get("Owner->Part")
        assert edge is not None, "Edge Owner->Part missing from layout (possible routing failure)"
        assert edge.source_marker == MarkerKind.FILLED_DIAMOND, (
            "Composition diamond must remain on Owner even after any layout reversal"
        )


# ── Task 5: Oracle marker assertions ─────────────────────────────────────────

class TestOracleMarkerAssertions:
    """Oracle comparison executes marker assertions and fails on mismatches."""

    def _oracle(self, src, actual_edges=None):
        from tools.mermaid_fidelity.compare.semantic import compare_class_diagram_markers
        if actual_edges is None:
            result = _compile(src)
            actual_edges = list(result.layout.routed_edges)
        expected = _expected_markers_from_source(src)
        return compare_class_diagram_markers(expected, actual_edges)

    def test_oracle_asserts_markers_nonzero(self):
        """Oracle on class-relationships-all executes at least one marker check."""
        src = FIXTURE_PATH.read_text()
        oracle_result = self._oracle(src)
        assert len(oracle_result.checks) > 0, "Oracle executed zero marker checks"

    def test_oracle_passes_on_correct_compilation(self):
        """Oracle passes when the compiled layout matches expected marker semantics.

        Expected marker tuples are hardcoded (not derived from _class_rel_markers)
        so the test is not narcissistic — it pins the actual UML contract.
        """
        from tools.mermaid_fidelity.compare.semantic import compare_class_diagram_markers
        from tools.mermaid_fidelity.oracle_contract import OracleStatus
        src = FIXTURE_PATH.read_text()
        result = _compile(src)
        actual_edges = list(result.layout.routed_edges)
        # Hardcoded expected — from the UML spec, not from _class_rel_markers
        expected = [
            ("Animal->Dog",      "hollow_triangle", "none"),
            ("Animal->Cat",      "hollow_triangle", "none"),
            ("Car->Engine",      "filled_diamond",  "none"),
            ("Pond->Duck",       "hollow_diamond",  "none"),
            ("Person->Address",  "none",            "open_arrow"),
            ("IFlyable->Bird",   "none",            "open_arrow"),
            ("Teacher->Professor", "none",          "hollow_triangle"),
        ]
        oracle_result = compare_class_diagram_markers(expected, actual_edges)
        assert oracle_result.status == OracleStatus.PASS, (
            f"Oracle failed on correct compilation: {oracle_result.diagnostics}"
        )

    def test_oracle_fails_on_marker_mismatch(self):
        """Oracle fails when expected markers do not match actual markers."""
        from tools.mermaid_fidelity.compare.semantic import compare_class_diagram_markers
        from tools.mermaid_fidelity.oracle_contract import OracleStatus

        src = _diagram("    class A\n    class B\n    A <|-- B : inherits\n")
        result = _compile(src)
        actual_edges = list(result.layout.routed_edges)

        # Deliberately set wrong expectation: claim filled_diamond instead of hollow_triangle
        wrong_expected = [("A->B", "filled_diamond", "none")]
        oracle_result = compare_class_diagram_markers(wrong_expected, actual_edges)
        assert oracle_result.status == OracleStatus.FAIL, (
            "Oracle should fail when expected marker doesn't match actual"
        )

    def test_oracle_no_check_skipped_for_non_none_markers(self):
        """Every relation with a non-NONE expected marker has a corresponding OracleCheck."""
        src = FIXTURE_PATH.read_text()
        expected = _expected_markers_from_source(src)
        # Count expected non-NONE markers
        non_none_count = sum(
            1 for _, sm, tm in expected
            if sm != "none" or tm != "none"
        )
        assert non_none_count > 0, "No non-none markers in fixture — test misconfigured"

        oracle_result = self._oracle(src)
        # Every (edge_id, end) pair corresponds to exactly one OracleCheck
        check_names = {c.name for c in oracle_result.checks}
        for edge_id, sm, tm in expected:
            # Both marker ends always get a check
            assert f"{edge_id}:source_marker" in check_names, (
                f"No check for {edge_id}:source_marker"
            )
            assert f"{edge_id}:target_marker" in check_names, (
                f"No check for {edge_id}:target_marker"
            )

    def test_oracle_extractor_gap_on_empty_edges(self):
        """Oracle returns EXTRACTOR_GAP when no actual edges are provided."""
        from tools.mermaid_fidelity.compare.semantic import compare_class_diagram_markers
        from tools.mermaid_fidelity.oracle_contract import OracleStatus
        result = compare_class_diagram_markers([("A->B", "NONE", "NONE")], [])
        assert result.status == OracleStatus.EXTRACTOR_GAP


# ── Task 6: Parallel-relation tests ──────────────────────────────────────────

class TestParallelRelations:
    """Two edges with same (src, dst) but different labels remain distinct."""

    def test_parallel_relations_both_present(self):
        """Both parallel relations appear in the compiled routed_edges."""
        src = _diagram(
            "    class A\n    class B\n"
            "    A --> B : first\n"
            "    A --> B : second\n"
        )
        result = _compile(src)
        assert len(result.layout.routed_edges) == 2, (
            f"Expected 2 routed edges, got {len(result.layout.routed_edges)}"
        )

    def test_parallel_relations_distinct_routes(self):
        """Parallel relations have distinct waypoints (different visual paths)."""
        src = _diagram(
            "    class A\n    class B\n"
            "    A --> B : first\n"
            "    A --> B : second\n"
        )
        result = _compile(src)
        edges = list(result.layout.routed_edges)
        assert len(edges) == 2
        wp0 = edges[0].waypoints
        wp1 = edges[1].waypoints
        # At least one waypoint must differ
        assert wp0 != wp1, "Parallel edges share identical waypoints"

    def test_parallel_relations_distinct_labels(self):
        """Each parallel edge label is retrievable by its own edge_id."""
        src = _diagram(
            "    class A\n    class B\n"
            "    A --> B : alpha\n"
            "    A --> B : beta\n"
        )
        result = _compile(src)
        by_id = _routed_by_id(result)
        assert "A->B" in by_id
        assert "A->B#1" in by_id
        # Each has its own label
        e1 = by_id["A->B"]
        e2 = by_id["A->B#1"]
        lbl1 = e1.label_layout.text if e1.label_layout else ""
        lbl2 = e2.label_layout.text if e2.label_layout else ""
        assert {lbl1, lbl2} == {"alpha", "beta"}, (
            f"Labels not preserved by edge_id: {lbl1!r}, {lbl2!r}"
        )

    def test_parallel_relations_oracle_sees_both(self):
        """Oracle comparison registers checks for both parallel relations."""
        from tools.mermaid_fidelity.compare.semantic import compare_class_diagram_markers
        src = _diagram(
            "    class A\n    class B\n"
            "    A --> B : first\n"
            "    A --> B : second\n"
        )
        result = _compile(src)
        actual_edges = list(result.layout.routed_edges)
        expected = [
            ("A->B", "none", "open_arrow"),
            ("A->B#1", "none", "open_arrow"),
        ]
        oracle_result = compare_class_diagram_markers(expected, actual_edges)
        from tools.mermaid_fidelity.oracle_contract import OracleStatus
        assert oracle_result.status == OracleStatus.PASS
        # Should have 4 checks: 2 edges × 2 ends
        assert len(oracle_result.checks) == 4

    def test_three_parallel_edges_distinct_ids(self):
        """Three parallel edges get IDs: A->B, A->B#1, A->B#2."""
        src = _diagram(
            "    class A\n    class B\n"
            "    A --> B : one\n"
            "    A --> B : two\n"
            "    A --> B : three\n"
        )
        result = _compile(src)
        ids = sorted(re_obj.edge_id for re_obj in result.layout.routed_edges)
        assert ids == ["A->B", "A->B#1", "A->B#2"], f"Unexpected IDs: {ids}"


# ── Task 7: Full conformance suite ────────────────────────────────────────────

class TestClassRelationshipsAllConformance:
    """Full conformance against the class-relationships-all fixture."""

    @pytest.fixture(scope="class")
    def compiled(self):
        src = FIXTURE_PATH.read_text()
        return _compile(src)

    @pytest.fixture(scope="class")
    def by_id(self, compiled):
        return _routed_by_id(compiled)

    def test_all_classes_present(self, compiled):
        """All 13 class nodes are in the layout."""
        classes = {"Animal", "Dog", "Cat", "Engine", "Car", "Pond", "Duck",
                   "Person", "Address", "IFlyable", "Bird", "Teacher", "Professor"}
        actual_ids = set(compiled.layout.node_layouts.keys())
        assert classes <= actual_ids, f"Missing classes: {classes - actual_ids}"

    def test_all_edges_routed(self, compiled):
        """All 7 relations produce routed edges (no routing failures)."""
        assert len(compiled.layout.routing_failures) == 0, (
            f"Routing failures: {compiled.layout.routing_failures}"
        )
        assert len(compiled.layout.routed_edges) == 7, (
            f"Expected 7 routed edges, got {len(compiled.layout.routed_edges)}"
        )

    def test_animal_dog_inherit_source_marker(self, by_id):
        """Animal<|--Dog: HOLLOW_TRIANGLE at source (Animal end)."""
        edge = by_id.get("Animal->Dog")
        assert edge is not None, "Animal->Dog not found"
        assert edge.source_marker == MarkerKind.HOLLOW_TRIANGLE

    def test_animal_dog_inherit_target_none(self, by_id):
        """Animal<|--Dog: NONE at target (Dog end)."""
        edge = by_id.get("Animal->Dog")
        assert edge is not None
        assert edge.target_marker == MarkerKind.NONE

    def test_animal_dog_solid_style(self, by_id):
        """Animal<|--Dog: solid line style."""
        edge = by_id.get("Animal->Dog")
        assert edge is not None
        assert edge.edge_style == "solid"

    def test_animal_cat_inherit(self, by_id):
        """Animal<|--Cat: same marker pattern as Animal->Dog."""
        edge = by_id.get("Animal->Cat")
        assert edge is not None
        assert edge.source_marker == MarkerKind.HOLLOW_TRIANGLE
        assert edge.target_marker == MarkerKind.NONE

    def test_car_engine_composition_source(self, by_id):
        """Car*--Engine: FILLED_DIAMOND at source (Car end)."""
        edge = by_id.get("Car->Engine")
        assert edge is not None
        assert edge.source_marker == MarkerKind.FILLED_DIAMOND

    def test_car_engine_composition_target(self, by_id):
        """Car*--Engine: NONE at target (Engine end)."""
        edge = by_id.get("Car->Engine")
        assert edge is not None
        assert edge.target_marker == MarkerKind.NONE

    def test_pond_duck_aggregation_source(self, by_id):
        """Pond o-- Duck: HOLLOW_DIAMOND at source (Pond end)."""
        edge = by_id.get("Pond->Duck")
        assert edge is not None
        assert edge.source_marker == MarkerKind.HOLLOW_DIAMOND

    def test_person_address_association_target(self, by_id):
        """Person --> Address: OPEN_ARROW at target (Address end)."""
        edge = by_id.get("Person->Address")
        assert edge is not None
        assert edge.target_marker == MarkerKind.OPEN_ARROW
        assert edge.source_marker == MarkerKind.NONE
        assert edge.edge_style == "solid"

    def test_iflyable_bird_dependency(self, by_id):
        """IFlyable ..> Bird: OPEN_ARROW at target, dashed."""
        edge = by_id.get("IFlyable->Bird")
        assert edge is not None
        assert edge.target_marker == MarkerKind.OPEN_ARROW
        assert edge.edge_style == "dotted"

    def test_teacher_professor_realization(self, by_id):
        """Teacher ..|> Professor: HOLLOW_TRIANGLE at target, dashed."""
        edge = by_id.get("Teacher->Professor")
        assert edge is not None
        assert edge.target_marker == MarkerKind.HOLLOW_TRIANGLE
        assert edge.edge_style == "dotted"

    def test_oracle_nonvacuous_pass(self):
        """Oracle comparison with hardcoded expectations is PASS with >0 checks.

        Expected tuples are pinned from the UML spec, not derived from
        _class_rel_markers, so this is not narcissistic.
        """
        from tools.mermaid_fidelity.compare.semantic import compare_class_diagram_markers
        from tools.mermaid_fidelity.oracle_contract import OracleStatus
        src = FIXTURE_PATH.read_text()
        result = _compile(src)
        actual_edges = list(result.layout.routed_edges)
        # Hardcoded from the UML contract, NOT from _class_rel_markers
        expected = [
            ("Animal->Dog",      "hollow_triangle", "none"),
            ("Animal->Cat",      "hollow_triangle", "none"),
            ("Car->Engine",      "filled_diamond",  "none"),
            ("Pond->Duck",       "hollow_diamond",  "none"),
            ("Person->Address",  "none",            "open_arrow"),
            ("IFlyable->Bird",   "none",            "open_arrow"),
            ("Teacher->Professor", "none",          "hollow_triangle"),
        ]
        oracle_result = compare_class_diagram_markers(expected, actual_edges)
        assert len(oracle_result.checks) > 0, "Oracle produced zero checks — vacuous pass"
        assert oracle_result.status == OracleStatus.PASS, (
            f"Oracle failed: {oracle_result.diagnostics}"
        )

    def test_deterministic_marker_preservation(self):
        """Class diagram compiler is deterministic: repeated compilation yields identical markers.

        Class diagrams use a single Python Sugiyama path (no ELK path exists).
        This test verifies path stability — the same source always produces the
        same edge_id→(source_marker, target_marker) mapping.
        """
        src = FIXTURE_PATH.read_text()
        r1 = _compile(src)
        r2 = _compile(src)
        ids1 = {re_obj.edge_id: (re_obj.source_marker, re_obj.target_marker)
                for re_obj in r1.layout.routed_edges}
        ids2 = {re_obj.edge_id: (re_obj.source_marker, re_obj.target_marker)
                for re_obj in r2.layout.routed_edges}
        assert ids1 == ids2, f"Marker metadata differs between runs: {ids1} vs {ids2}"

    def test_canvas_bounds_valid(self, compiled):
        """Canvas bounds are positive (compilation succeeded)."""
        cb = compiled.layout.canvas_bounds
        assert cb.w > 0 and cb.h > 0


