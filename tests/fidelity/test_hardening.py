"""Tests for the Phase 1 fidelity hardening spec.

Covers:
- False-green elimination: unrelated ValueError → INTERNAL_ERROR
- Active NATIVE_UNSUPPORTED → INTERNAL_ERROR escalation
- Unknown --case ID → nonzero exit
- Parallel relation multiset: count=2 vs count=1 → mismatch
- parse comparison: all outcomes (accept/accept match, accept/reject, both-reject)
- Group existence, membership, parent checked under containment strict
- Containment tuple convention: (child_id, parent_id)
- Vacuous layout pass prevented: extractor gap when no entity-id overlap
- source_sha256 stale oracle detection
- Lifecycle validation: unknown value rejected
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "tools"))

from mermaid_fidelity.models import (
    BoundingBox,
    ComparisonStatus,
    Entity,
    EntityGeometry,
    EnvironmentIdentity,
    FidelityCase,
    FidelityManifest,
    GeometryObservation,
    Group,
    GroupGeometry,
    ImplementationIdentity,
    Observation,
    ParseObservation,
    Relation,
    RenderProfile,
    SemanticDiagram,
)
from mermaid_fidelity.compare.geometry import compare_relative_layout
from mermaid_fidelity.compare.semantic import compare_semantic, compare_parse, ParseDiff
from mermaid_fidelity.runner import FidelityRunner, _build_summary, CaseRunResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _dummy_impl() -> ImplementationIdentity:
    return ImplementationIdentity(
        name="test", version="0.0", integrity=None,
        adapter_version="0", profile_id="test",
    )


def _dummy_env() -> EnvironmentIdentity:
    return EnvironmentIdentity(
        mermaid_version="0", mermaid_integrity=None,
        playwright_version="0", chromium_revision="0",
        viewport_width=1200, viewport_height=900,
        device_scale_factor=1.0, locale="en-US",
        timezone="UTC", reduced_motion=True,
        mermaid_config_hash="", css_profile_hash="",
        font_info={},
    )


def _dummy_parse(accepted: bool = True, diagram_type: str | None = "flowchart") -> ParseObservation:
    return ParseObservation(
        accepted=accepted,
        diagram_type=diagram_type,
        error_category=None if accepted else "parse_error",
        source_position=None,
    )


def _pass_obs(case_id: str = "test", source_sha256: str | None = None) -> Observation:
    return Observation(
        schema_version=1, case_id=case_id,
        implementation=_dummy_impl(), environment=_dummy_env(),
        parse_result=_dummy_parse(),
        semantic=SemanticDiagram(diagram_type="flowchart", direction="TB"),
        geometry=None, quality=None,
        status=ComparisonStatus.PASS, reason=None,
        source_sha256=source_sha256,
    )


def _entity(eid: str) -> Entity:
    return Entity(id=eid, kind="node", label=eid, shape="rect", parent_id=None, order=0)


def _relation(src: str, dst: str, label: str = "") -> Relation:
    return Relation(id=f"{src}__{dst}", kind="edge", source=src, target=dst,
                    label=label, arrow=None, order=0)


def _bbox(x: float = 0, y: float = 0, w: float = 100, h: float = 40) -> BoundingBox:
    return BoundingBox(x=x, y=y, width=w, height=h)


def _geo(entities: list, groups: list | None = None,
         containment: list | None = None) -> GeometryObservation:
    return GeometryObservation(
        coordinate_convention="css-top-left",
        content_bounds=None, canvas_bounds=None, viewbox=None,
        entities=entities,
        groups=groups or [],
        relations=[],
        containment=containment or [],
    )


# ── false-green elimination ───────────────────────────────────────────────────

class TestFalseGreenElimination:
    """Unrelated ValueError must produce INTERNAL_ERROR, not NATIVE_UNSUPPORTED."""

    def test_unrelated_valueerror_is_internal_error(self):
        """An unrelated ValueError from the renderer → INTERNAL_ERROR."""
        sys.path.insert(0, str(_REPO / "scripts"))
        try:
            from mermaid_render.errors import (
                UnsupportedDiagramType, NativeRendererUnavailable, UnsupportedDiagramFeature,
            )
            # These are the ONLY exceptions that should map to NATIVE_UNSUPPORTED.
            # A plain ValueError (e.g., from a geometry bug) must map to INTERNAL_ERROR.
            assert issubclass(UnsupportedDiagramType, ValueError)
            assert issubclass(NativeRendererUnavailable, ValueError)
            assert issubclass(UnsupportedDiagramFeature, ValueError)
        finally:
            sys.path.pop(0)

        # The key: UnsupportedDiagramType IS a ValueError, but the adapter's
        # except clause catches the typed exceptions BEFORE the plain ValueError clause.
        # Verify via the native_svg adapter code: import it and simulate a render call.
        sys.path.insert(0, str(_REPO / "scripts"))
        sys.path.insert(0, str(_REPO))
        try:
            from tests.fidelity.adapters.native_svg import NativeSvgAdapter
            profile = RenderProfile(id="test")
            case = FidelityCase(
                id="t1",
                source_path=Path("t.mmd"),
                source="flowchart TB\n  A-->B",
                diagram="flowchart",
                lifecycle="active",
            )
            # Patch the local binding in the adapter module, not the original module.
            with patch("tests.fidelity.adapters.native_svg.to_svg",
                       side_effect=ValueError("some unrelated error")):
                obs = NativeSvgAdapter().observe(case, profile)
            assert obs.status == ComparisonStatus.INTERNAL_ERROR, (
                f"Expected INTERNAL_ERROR for plain ValueError, got {obs.status}"
            )
        finally:
            sys.path.pop(0)
            sys.path.pop(0)

    def test_unsupported_typed_exception_is_native_unsupported(self):
        """UnsupportedDiagramType → NATIVE_UNSUPPORTED (the only valid path)."""
        sys.path.insert(0, str(_REPO / "scripts"))
        sys.path.insert(0, str(_REPO))
        try:
            from mermaid_render.errors import UnsupportedDiagramType
            from tests.fidelity.adapters.native_svg import NativeSvgAdapter
            profile = RenderProfile(id="test")
            case = FidelityCase(
                id="t2",
                source_path=Path("t.mmd"),
                source="sequenceDiagram\n  A->>B: hello",
                diagram="sequence",
                lifecycle="planned",
            )
            with patch("tests.fidelity.adapters.native_svg.to_svg",
                       side_effect=UnsupportedDiagramType("seq")):
                obs = NativeSvgAdapter().observe(case, profile)
            assert obs.status == ComparisonStatus.NATIVE_UNSUPPORTED
        finally:
            sys.path.pop(0)
            sys.path.pop(0)


# ── active case NATIVE_UNSUPPORTED escalation ─────────────────────────────────

class TestActiveNativeUnsupported:
    """Active cases must not produce NATIVE_UNSUPPORTED — runner escalates to INTERNAL_ERROR."""

    def _make_runner_with_obs(self, obs: Observation) -> FidelityRunner:
        adapter = MagicMock()
        adapter.observe.return_value = obs
        runner = FidelityRunner(
            native_adapter=adapter,
            oracle_dir=Path("/nonexistent"),
        )
        return runner

    def test_active_native_unsupported_escalates(self):
        """runner.run_all() escalates NATIVE_UNSUPPORTED to INTERNAL_ERROR for active cases."""
        from mermaid_fidelity.manifest import FidelityManifest

        case = FidelityCase(
            id="flowchart.simple",
            source_path=Path("f.mmd"),
            source="flowchart TB\n  A-->B",
            diagram="flowchart",
            lifecycle="active",
        )
        manifest = FidelityManifest(schema_version=1, cases=[case])
        profile = RenderProfile(id="test")

        obs = Observation(
            schema_version=1, case_id=case.id,
            implementation=_dummy_impl(), environment=_dummy_env(),
            parse_result=_dummy_parse(accepted=False),
            semantic=None, geometry=None, quality=None,
            status=ComparisonStatus.NATIVE_UNSUPPORTED,
            reason="not implemented",
        )
        runner = self._make_runner_with_obs(obs)
        # Patch out oracle loading so ref_obs is None → STALE_ORACLE first.
        # We must set the oracle_dir to a real dir with no oracle to trigger
        # the STALE_ORACLE path (status != PASS before escalation runs).
        # For this test, the obs already has NATIVE_UNSUPPORTED, so it won't
        # enter the comparison block; escalation runs unconditionally.
        summary = runner.run_all(manifest, profile, ref_id="ref-test")
        result = summary.results[0]
        assert result.final_status == ComparisonStatus.INTERNAL_ERROR, (
            f"Expected INTERNAL_ERROR for active NATIVE_UNSUPPORTED, got {result.final_status}"
        )

    def test_planned_native_unsupported_not_escalated(self):
        """NATIVE_UNSUPPORTED for planned cases stays NATIVE_UNSUPPORTED."""
        from mermaid_fidelity.manifest import FidelityManifest

        case = FidelityCase(
            id="sequence.simple",
            source_path=Path("s.mmd"),
            source="sequenceDiagram\n  A->>B: hi",
            diagram="sequence",
            lifecycle="planned",
        )
        manifest = FidelityManifest(schema_version=1, cases=[case])
        profile = RenderProfile(id="test")

        obs = Observation(
            schema_version=1, case_id=case.id,
            implementation=_dummy_impl(), environment=_dummy_env(),
            parse_result=_dummy_parse(accepted=False),
            semantic=None, geometry=None, quality=None,
            status=ComparisonStatus.NATIVE_UNSUPPORTED,
            reason="not implemented",
        )
        adapter = MagicMock()
        adapter.observe.return_value = obs
        runner = FidelityRunner(native_adapter=adapter, oracle_dir=Path("/nonexistent"))
        summary = runner.run_all(manifest, profile, ref_id="ref-test")
        result = summary.results[0]
        assert result.final_status == ComparisonStatus.NATIVE_UNSUPPORTED


# ── parallel relation multiset ────────────────────────────────────────────────

class TestRelationMultiset:
    """Counter-based multiset must catch count mismatches for parallel edges."""

    def test_parallel_edge_count_mismatch(self):
        """Two parallel A→B edges in expected but only one in actual → mismatch."""
        exp = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A"), _entity("B")],
            relations=[
                Relation(id="r1", kind="edge", source="A", target="B", label="", arrow=None, order=0),
                Relation(id="r2", kind="edge", source="A", target="B", label="", arrow=None, order=1),
            ],
        )
        act = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A"), _entity("B")],
            relations=[
                Relation(id="r1", kind="edge", source="A", target="B", label="", arrow=None, order=0),
            ],
        )
        result = compare_semantic(exp, act, strict_fields=["relations"])
        assert not result.passed
        assert len(result.diff.missing_relations) == 1

    def test_parallel_edge_same_count_passes(self):
        """Two parallel A→B edges in both expected and actual → pass."""
        rels = [
            Relation(id="r1", kind="edge", source="A", target="B", label="", arrow=None, order=0),
            Relation(id="r2", kind="edge", source="A", target="B", label="", arrow=None, order=1),
        ]
        diagram = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A"), _entity("B")],
            relations=rels,
        )
        result = compare_semantic(diagram, diagram, strict_fields=["relations"])
        assert result.passed

    def test_extra_relation_in_actual_caught(self):
        """Extra A→B in actual (count=2 vs expected count=1) → extra_relations."""
        exp = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A"), _entity("B")],
            relations=[
                Relation(id="r1", kind="edge", source="A", target="B", label="", arrow=None, order=0),
            ],
        )
        act = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A"), _entity("B")],
            relations=[
                Relation(id="r1", kind="edge", source="A", target="B", label="", arrow=None, order=0),
                Relation(id="r2", kind="edge", source="A", target="B", label="", arrow=None, order=1),
            ],
        )
        result = compare_semantic(exp, act, strict_fields=["relations"])
        assert not result.passed
        assert len(result.diff.extra_relations) == 1


# ── parse comparison ──────────────────────────────────────────────────────────

class TestParseComparison:
    """compare_parse() covers all branching paths."""

    def test_both_accept_same_family(self):
        exp = ParseObservation(accepted=True, diagram_type="flowchart",
                               error_category=None, source_position=None)
        act = ParseObservation(accepted=True, diagram_type="flowchart",
                               error_category=None, source_position=None)
        assert compare_parse(exp, act) == []

    def test_both_accept_normalized_aliases(self):
        """graph and flowchart are the same family after normalization."""
        exp = ParseObservation(accepted=True, diagram_type="flowchart",
                               error_category=None, source_position=None)
        act = ParseObservation(accepted=True, diagram_type="graph",
                               error_category=None, source_position=None)
        assert compare_parse(exp, act) == []

    def test_reference_accepts_native_rejects(self):
        exp = ParseObservation(accepted=True, diagram_type="flowchart",
                               error_category=None, source_position=None)
        act = ParseObservation(accepted=False, diagram_type=None,
                               error_category="parse_error", source_position=None)
        diffs = compare_parse(exp, act)
        assert len(diffs) == 1
        assert diffs[0].field == "accepted"

    def test_reference_rejects_native_accepts(self):
        exp = ParseObservation(accepted=False, diagram_type=None,
                               error_category="parse_error", source_position=None)
        act = ParseObservation(accepted=True, diagram_type="flowchart",
                               error_category=None, source_position=None)
        diffs = compare_parse(exp, act)
        assert len(diffs) == 1
        assert diffs[0].field == "accepted"

    def test_both_reject_same_category(self):
        exp = ParseObservation(accepted=False, diagram_type=None,
                               error_category="parse_error", source_position=None)
        act = ParseObservation(accepted=False, diagram_type=None,
                               error_category="parse_error", source_position=None)
        assert compare_parse(exp, act) == []

    def test_both_reject_different_category(self):
        exp = ParseObservation(accepted=False, diagram_type=None,
                               error_category="parse_error", source_position=None)
        act = ParseObservation(accepted=False, diagram_type=None,
                               error_category="internal_error", source_position=None)
        diffs = compare_parse(exp, act)
        assert len(diffs) == 1
        assert diffs[0].field == "error_category"

    def test_different_accepted_families(self):
        exp = ParseObservation(accepted=True, diagram_type="flowchart",
                               error_category=None, source_position=None)
        act = ParseObservation(accepted=True, diagram_type="sequence",
                               error_category=None, source_position=None)
        diffs = compare_parse(exp, act)
        assert len(diffs) == 1
        assert diffs[0].field == "diagram_type"


# ── group containment ─────────────────────────────────────────────────────────

class TestGroupContainment:
    """containment strict field: checks existence, membership, parent_id."""

    def _grp(self, gid: str, members: list[str], parent_id: str | None = None) -> Group:
        return Group(id=gid, kind="subgraph", label=gid, parent_id=parent_id,
                     order=0, members=members)

    def test_missing_group_caught(self):
        exp = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A")],
            groups=[self._grp("G1", members=["A"])],
        )
        act = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A")],
            groups=[],
        )
        result = compare_semantic(exp, act, strict_fields=["containment"])
        assert not result.passed
        assert "G1" in result.diff.missing_groups

    def test_extra_group_caught(self):
        exp = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A")],
            groups=[],
        )
        act = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A")],
            groups=[self._grp("G1", members=["A"])],
        )
        result = compare_semantic(exp, act, strict_fields=["containment"])
        assert not result.passed
        assert "G1" in result.diff.extra_groups

    def test_missing_member_caught(self):
        exp = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A"), _entity("B")],
            groups=[self._grp("G1", members=["A", "B"])],
        )
        act = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A"), _entity("B")],
            groups=[self._grp("G1", members=["A"])],  # B missing
        )
        result = compare_semantic(exp, act, strict_fields=["containment"])
        assert not result.passed
        assert any("missing members" in msg for msg in result.diff.changed_groups)

    def test_parent_mismatch_caught(self):
        exp = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A")],
            groups=[self._grp("G1", members=["A"], parent_id="outer")],
        )
        act = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A")],
            groups=[self._grp("G1", members=["A"], parent_id=None)],
        )
        result = compare_semantic(exp, act, strict_fields=["containment"])
        assert not result.passed
        assert any("parent changed" in msg for msg in result.diff.changed_groups)

    def test_matching_groups_pass(self):
        grps = [self._grp("G1", members=["A", "B"])]
        diagram = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A"), _entity("B")],
            groups=grps,
        )
        result = compare_semantic(diagram, diagram, strict_fields=["containment"])
        assert result.passed


# ── containment tuple convention ──────────────────────────────────────────────

class TestContainmentTupleConvention:
    """(child_id, parent_id) convention is correctly iterated in geometry checks."""

    def _eg(self, eid: str, x: float, y: float, w: float = 50, h: float = 20) -> EntityGeometry:
        return EntityGeometry(entity_id=eid, bbox=_bbox(x, y, w, h), text_bbox=None, text_lines=1)

    def _gg(self, gid: str, x: float, y: float, w: float = 200, h: float = 100) -> GroupGeometry:
        return GroupGeometry(group_id=gid, bbox=_bbox(x, y, w, h))

    def test_child_inside_parent_passes(self):
        """Entity (child) inside group (parent): (child_id, parent_id) → no containment failure."""
        native_obs = _geo(
            entities=[self._eg("child", x=10, y=10)],
            groups=[self._gg("parent", x=0, y=0, w=200, h=100)],
            containment=[("child", "parent")],  # (child_id, parent_id)
        )
        ref_obs = _geo(
            entities=[self._eg("child", x=10, y=10)],
            groups=[self._gg("parent", x=0, y=0, w=200, h=100)],
            containment=[("child", "parent")],
        )
        result = compare_relative_layout(native_obs, ref_obs, strict_fields=["containment"])
        assert result.passed, f"Expected pass, failures: {result.failures}"

    def test_child_outside_parent_fails(self):
        """Entity clearly outside group bounds → containment violation."""
        native_obs = _geo(
            entities=[self._eg("child", x=300, y=300)],  # way outside parent
            groups=[self._gg("parent", x=0, y=0, w=100, h=100)],
            containment=[("child", "parent")],
        )
        ref_obs = _geo(
            entities=[self._eg("child", x=10, y=10)],
            groups=[self._gg("parent", x=0, y=0, w=100, h=100)],
            containment=[("child", "parent")],
        )
        result = compare_relative_layout(native_obs, ref_obs, strict_fields=["containment"])
        assert not result.passed


# ── vacuous layout pass ───────────────────────────────────────────────────────

class TestVacuousLayoutPass:
    """No entity-ID overlap when both sides have entities → EXTRACTOR_GAP, not pass."""

    def _eg(self, eid: str) -> EntityGeometry:
        return EntityGeometry(entity_id=eid, bbox=_bbox(), text_bbox=None, text_lines=1)

    def test_no_common_ids_with_entities_fails(self):
        """Native uses {X, Y}, reference uses {A, B} → no overlap → extractor gap failure."""
        native_obs = _geo(entities=[self._eg("X"), self._eg("Y")])
        ref_obs = _geo(entities=[self._eg("A"), self._eg("B")])
        result = compare_relative_layout(native_obs, ref_obs, strict_fields=["containment"])
        assert not result.passed
        assert any("extractor gap" in f.lower() or "no common" in f.lower()
                   for f in result.failures)

    def test_both_empty_entities_passes(self):
        """Both sides empty → no entities to compare → pass (nothing to check)."""
        native_obs = _geo(entities=[])
        ref_obs = _geo(entities=[])
        result = compare_relative_layout(native_obs, ref_obs, strict_fields=[])
        assert result.passed

    def test_common_ids_present_does_not_trigger_gap(self):
        """Shared entity IDs → comparison proceeds normally, no false gap."""
        native_obs = _geo(entities=[self._eg("A"), self._eg("B")])
        ref_obs = _geo(entities=[self._eg("A"), self._eg("C")])
        result = compare_relative_layout(native_obs, ref_obs, strict_fields=[])
        # A is common, so we proceed — result should be True (no strict failures checked)
        assert result.passed


# ── source_sha256 stale oracle detection ──────────────────────────────────────

class TestStaleOracleDetection:
    """source_sha256 mismatch between native and oracle → STALE_ORACLE."""

    def _make_case(self, cid: str = "flowchart.simple") -> FidelityCase:
        return FidelityCase(
            id=cid, source_path=Path("f.mmd"),
            source="flowchart TB\n  A-->B",
            diagram="flowchart", lifecycle="active",
        )

    def test_sha256_mismatch_yields_stale_oracle(self):
        """When native_obs.source_sha256 != ref_obs.source_sha256 → STALE_ORACLE."""
        case = self._make_case()
        native_obs = _pass_obs(case.id, source_sha256="aabbcc")
        ref_obs = _pass_obs(case.id, source_sha256="ddeeff")  # different hash

        adapter = MagicMock()
        adapter.observe.return_value = native_obs
        runner = FidelityRunner(native_adapter=adapter, oracle_dir=Path("/nonexistent"))

        result = runner._compare(case, native_obs, ref_obs)
        assert result.final_status == ComparisonStatus.STALE_ORACLE
        assert "source hash mismatch" in (result.reason or "").lower()

    def test_sha256_match_does_not_stale(self):
        """When both sha256 match → comparison continues normally."""
        case = self._make_case()
        sha = "cafebabe"
        native_obs = _pass_obs(case.id, source_sha256=sha)
        ref_obs = _pass_obs(case.id, source_sha256=sha)

        adapter = MagicMock()
        adapter.observe.return_value = native_obs
        runner = FidelityRunner(native_adapter=adapter, oracle_dir=Path("/nonexistent"))

        result = runner._compare(case, native_obs, ref_obs)
        # With matching sha256, result should be PASS (no semantic mismatch since both are empty)
        assert result.final_status == ComparisonStatus.PASS

    def test_sha256_none_does_not_stale(self):
        """When either sha256 is None (old oracle), stale detection is skipped."""
        case = self._make_case()
        native_obs = _pass_obs(case.id, source_sha256="aabbcc")
        ref_obs = _pass_obs(case.id, source_sha256=None)  # old oracle, no hash

        adapter = MagicMock()
        adapter.observe.return_value = native_obs
        runner = FidelityRunner(native_adapter=adapter, oracle_dir=Path("/nonexistent"))

        result = runner._compare(case, native_obs, ref_obs)
        # No stale detection when either is None
        assert result.final_status != ComparisonStatus.STALE_ORACLE


# ── lifecycle validation ──────────────────────────────────────────────────────

class TestLifecycleValidation:
    """Unknown lifecycle values must be rejected at manifest parse time."""

    def test_unknown_lifecycle_rejected(self, tmp_path: Path):
        from mermaid_fidelity.manifest import parse_manifest, ManifestValidationError

        # Use a relative path so TOML content is simple and portable.
        mmd = tmp_path / "t.mmd"
        mmd.write_text("flowchart TB\n  A-->B", encoding="utf-8")

        toml_lines = [
            "schema_version = 1",
            "",
            "[[case]]",
            'id = "flowchart.test"',
            'diagram = "flowchart"',
            'lifecycle = "beta"',
            'source = "t.mmd"',
            'strict = ["parse", "entities"]',
            "scored = []",
            "ignored = []",
        ]
        toml_path = tmp_path / "cases.toml"
        toml_path.write_text("\n".join(toml_lines) + "\n", encoding="utf-8")

        with pytest.raises((ManifestValidationError, ValueError, Exception)) as exc_info:
            parse_manifest(toml_path, load_sources=False)

        assert "beta" in str(exc_info.value).lower() or "lifecycle" in str(exc_info.value).lower()

    def test_valid_lifecycle_values_accepted(self, tmp_path: Path):
        from mermaid_fidelity.manifest import parse_manifest

        mmd = tmp_path / "t.mmd"
        mmd.write_text("flowchart TB\n  A-->B", encoding="utf-8")

        for lifecycle in ("active", "planned"):
            toml_lines = [
                "schema_version = 1",
                "",
                "[[case]]",
                'id = "flowchart.test"',
                'diagram = "flowchart"',
                f'lifecycle = "{lifecycle}"',
                'source = "t.mmd"',
                'strict = ["parse", "entities"]',
                "scored = []",
                "ignored = []",
            ]
            toml_path = tmp_path / f"cases_{lifecycle}.toml"
            toml_path.write_text("\n".join(toml_lines) + "\n", encoding="utf-8")
            manifest = parse_manifest(toml_path, load_sources=False)
            case = manifest.cases[0]
            assert case.lifecycle == lifecycle


# ── unknown --case ID ─────────────────────────────────────────────────────────

class TestUnknownCaseId:
    """run_all() must raise ValueError for unknown case IDs."""

    def test_unknown_case_id_raises(self):
        from mermaid_fidelity.manifest import FidelityManifest

        case = FidelityCase(
            id="flowchart.simple", source_path=Path("f.mmd"),
            source="flowchart TB\n  A-->B", diagram="flowchart", lifecycle="active",
        )
        manifest = FidelityManifest(schema_version=1, cases=[case])
        profile = RenderProfile(id="test")

        obs = _pass_obs("flowchart.simple")
        adapter = MagicMock()
        adapter.observe.return_value = obs
        runner = FidelityRunner(native_adapter=adapter, oracle_dir=Path("/nonexistent"))

        with pytest.raises(ValueError, match="Unknown case IDs"):
            runner.run_all(manifest, profile, ref_id="ref-test",
                           case_ids=["does.not.exist"])


# ── AC8: semantic extractor gap ───────────────────────────────────────────────

class TestSemanticExtractorGap:
    """Strict semantic checks declared but no semantic data → EXTRACTOR_GAP."""

    def _make_case(self, cid: str = "fc.test") -> FidelityCase:
        return FidelityCase(
            id=cid, source_path=Path("f.mmd"),
            source="flowchart TB\n  A-->B", diagram="flowchart", lifecycle="active",
            strict=["entities", "relations"],
        )

    def test_native_semantic_none_with_strict_checks(self):
        """native semantic=None + ref semantic present + strict checks → EXTRACTOR_GAP."""
        case = self._make_case()
        native_obs = _pass_obs(case.id)
        native_obs.semantic = None  # extractor produced nothing

        ref_obs = _pass_obs(case.id)
        ref_obs.semantic = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[_entity("A"), _entity("B")],
        )

        adapter = MagicMock()
        adapter.observe.return_value = native_obs
        runner = FidelityRunner(native_adapter=adapter, oracle_dir=Path("/nonexistent"))

        result = runner._compare(case, native_obs, ref_obs)
        assert result.final_status == ComparisonStatus.EXTRACTOR_GAP

    def test_both_semantic_none_no_strict_checks(self):
        """Both semantic=None and no strict checks → PASS (nothing to check)."""
        case = FidelityCase(
            id="fc.test", source_path=Path("f.mmd"),
            source="flowchart TB\n  A-->B", diagram="flowchart", lifecycle="active",
            strict=[],  # no strict checks declared
        )
        native_obs = _pass_obs(case.id)
        native_obs.semantic = None
        ref_obs = _pass_obs(case.id)
        ref_obs.semantic = None

        adapter = MagicMock()
        adapter.observe.return_value = native_obs
        runner = FidelityRunner(native_adapter=adapter, oracle_dir=Path("/nonexistent"))

        result = runner._compare(case, native_obs, ref_obs)
        assert result.final_status == ComparisonStatus.PASS


# ── AC11: shape comparison ────────────────────────────────────────────────────

class TestShapeComparison:
    """Shape mismatch must be caught when reference has a shape and actual has None."""

    def test_shape_mismatch_none_vs_value(self):
        """ref shape='diamond', actual shape=None → SEMANTIC_MISMATCH."""
        exp = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[
                Entity(id="A", kind="node", label="A", shape="diamond",
                       parent_id=None, order=0),
            ],
        )
        act = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[
                Entity(id="A", kind="node", label="A", shape=None,
                       parent_id=None, order=0),
            ],
        )
        result = compare_semantic(exp, act, strict_fields=["entities"])
        assert not result.passed
        assert any(d.field == "shape" for d in result.diff.changed_entities)

    def test_both_none_shape_passes(self):
        """ref shape=None, actual shape=None → pass (reference didn't extract shape)."""
        exp = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[Entity(id="A", kind="node", label="A", shape=None,
                             parent_id=None, order=0)],
        )
        act = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[Entity(id="A", kind="node", label="A", shape="rect",
                             parent_id=None, order=0)],
        )
        result = compare_semantic(exp, act, strict_fields=["entities"])
        assert result.passed

    def test_matching_shapes_pass(self):
        """ref shape='rect', actual shape='rect' → pass."""
        diag = SemanticDiagram(
            diagram_type="flowchart", direction="TB",
            entities=[Entity(id="A", kind="node", label="A", shape="rect",
                             parent_id=None, order=0)],
        )
        result = compare_semantic(diag, diag, strict_fields=["entities"])
        assert result.passed


# ── AC21: transactional capture ───────────────────────────────────────────────

class TestTransactionalCapture:
    """Oracle capture must gate the replace on zero errors and leave old oracle intact on failure."""

    def _make_manifest(self, case_id: str = "flowchart.simple") -> FidelityManifest:
        case = FidelityCase(
            id=case_id, source_path=Path("f.mmd"),
            source="flowchart TB\n  A-->B", diagram="flowchart", lifecycle="active",
        )
        return FidelityManifest(schema_version=1, cases=[case])

    def test_capture_error_does_not_overwrite_oracle(self, tmp_path: Path):
        """When an observation fails, the existing oracle must remain intact."""
        import argparse
        from mermaid_fidelity.cli import cmd_capture_reference

        # Pre-populate an existing oracle
        oracle_dir = tmp_path / "oracle"
        ref_id = "ref-test"
        cases_dir = oracle_dir / ref_id / "cases"
        cases_dir.mkdir(parents=True)
        existing = cases_dir / "flowchart.simple.json"
        existing.write_text('{"existing": true}\n', encoding="utf-8")

        args = argparse.Namespace(
            manifest=tmp_path / "cases.toml",  # not read in this test
            output=oracle_dir,
            ref_id=ref_id,
            force=True,  # override force check; we test error-gating, not existence check
        )

        # Adapter that returns a REFERENCE_RENDER_FAILURE observation
        fail_obs = Observation(
            schema_version=1, case_id="flowchart.simple",
            implementation=_dummy_impl(), environment=_dummy_env(),
            parse_result=_dummy_parse(accepted=False),
            semantic=None, geometry=None, quality=None,
            status=ComparisonStatus.REFERENCE_RENDER_FAILURE,
            reason="test failure",
        )
        ref_adapter = MagicMock()
        ref_adapter.observe.return_value = fail_obs
        ref_adapter.identity.return_value = _dummy_impl()

        manifest = self._make_manifest()

        result = cmd_capture_reference(
            args,
            manifest_loader=lambda _: manifest,
            ref_adapter_factory=lambda: ref_adapter,
            profile_loader=lambda _: RenderProfile(id="mermaid-neutral"),
        )

        # Must return nonzero (failure)
        assert result != 0
        # Existing oracle must still be intact
        assert existing.exists()
        assert '"existing": true' in existing.read_text(encoding="utf-8")
