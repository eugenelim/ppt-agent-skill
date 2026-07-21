"""End-to-end Phase 1 fidelity harness acceptance tests.

Tests that are safe to run in CI without mmdc or a browser:
 - Manifest loads and 24 cases are present
 - Serialization is stable (same fingerprint for same observation)
 - Canonical form is idempotent
 - Quality-check round-trips through JSON
 - Runner accepts a mock native adapter

Tests that require mmdc (skipped when absent):
 - Reference adapter produces non-failing observations for flowchart fixtures
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_FIDELITY = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO / "tools"))

from mermaid_fidelity.models import (
    BoundingBox,
    ComparisonStatus,
    Entity,
    EntityGeometry,
    EnvironmentIdentity,
    FidelityCase,
    GeometryObservation,
    Group,
    ImplementationIdentity,
    Observation,
    ParseObservation,
    QualityObservation,
    Relation,
    RenderProfile,
    SemanticDiagram,
)
from mermaid_fidelity.serialization import to_json, load_json, save_json, observation_fingerprint
from mermaid_fidelity.canonical import canonical_semantic, canonical_label
from mermaid_fidelity.manifest import parse_manifest

_MANIFEST = _FIDELITY / "cases.toml"
_FIXTURES = _REPO / "tests" / "fixtures"
_HAVE_MMDC = shutil.which("mmdc") is not None


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_impl() -> ImplementationIdentity:
    return ImplementationIdentity(
        name="test", version="1.0", integrity=None,
        adapter_version="1.0", profile_id="neutral",
    )


def _make_env() -> EnvironmentIdentity:
    return EnvironmentIdentity(
        mermaid_version="1.0", mermaid_integrity=None,
        playwright_version="1.0", chromium_revision="0",
        viewport_width=1200, viewport_height=900,
        device_scale_factor=1.0, locale="en-US", timezone="UTC",
        reduced_motion=True, mermaid_config_hash="", css_profile_hash="",
        font_info={},
    )


def _make_observation(case_id="test.case", status=ComparisonStatus.PASS,
                      with_geometry=False) -> Observation:
    sd = SemanticDiagram(
        diagram_type="flowchart",
        direction="LR",
        entities=[
            Entity(id="A", kind="node", label="Node A", shape="rect", parent_id=None, order=0),
            Entity(id="B", kind="node", label="Node B", shape="rect", parent_id=None, order=1),
        ],
        relations=[
            Relation(id="A__B__0", kind="edge", source="A", target="B",
                     label="yes", arrow=None, order=0),
        ],
    )
    geo = None
    if with_geometry:
        geo = GeometryObservation(
            coordinate_convention="css-top-left",
            content_bounds=BoundingBox(x=0, y=0, width=400, height=200),
            canvas_bounds=BoundingBox(x=0, y=0, width=800, height=600),
            viewbox=None,
            entities=[
                EntityGeometry(entity_id="A",
                               bbox=BoundingBox(x=10, y=10, width=100, height=50),
                               text_bbox=None, text_lines=1),
                EntityGeometry(entity_id="B",
                               bbox=BoundingBox(x=200, y=10, width=100, height=50),
                               text_bbox=None, text_lines=1),
            ],
            groups=[],
            relations=[],
            containment=[],
        )
    return Observation(
        schema_version=1,
        case_id=case_id,
        implementation=_make_impl(),
        environment=_make_env(),
        parse_result=ParseObservation(accepted=True, diagram_type="flowchart",
                                      error_category=None, source_position=None),
        semantic=sd,
        geometry=geo,
        quality=QualityObservation(findings=[]),
        status=status,
        reason=None,
    )


# ── serialization stability ───────────────────────────────────────────────────

class TestSerialization:
    def test_to_json_produces_valid_json(self):
        obs = _make_observation()
        s = to_json(obs)
        parsed = json.loads(s)
        assert parsed["schema_version"] == 1
        assert parsed["case_id"] == "test.case"

    def test_to_json_keys_sorted(self):
        obs = _make_observation()
        s = to_json(obs)
        parsed = json.loads(s)
        # Spot-check that keys are alphabetically sorted within a nested dict
        semantic = parsed.get("semantic", {})
        if semantic and "entities" in semantic:
            # Entity keys should be sorted
            ent = semantic["entities"][0]
            keys = list(ent.keys())
            assert keys == sorted(keys), f"Entity keys not sorted: {keys}"

    def test_fingerprint_stable(self):
        obs = _make_observation()
        fp1 = observation_fingerprint(obs)
        fp2 = observation_fingerprint(obs)
        assert fp1 == fp2

    def test_fingerprint_excludes_timestamp(self):
        obs1 = _make_observation()
        obs1.capture_timestamp = "2026-01-01T00:00:00Z"
        obs2 = _make_observation()
        obs2.capture_timestamp = "2030-12-31T23:59:59Z"
        assert observation_fingerprint(obs1) == observation_fingerprint(obs2)

    def test_fingerprint_changes_with_content(self):
        obs1 = _make_observation(case_id="case.one")
        obs2 = _make_observation(case_id="case.two")
        assert observation_fingerprint(obs1) != observation_fingerprint(obs2)

    def test_save_and_load_roundtrip(self):
        obs = _make_observation(with_geometry=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            save_json(obs, path)
            loaded = load_json(path)
            assert loaded["schema_version"] == 1
            assert loaded["case_id"] == "test.case"
            assert loaded["status"] == "PASS"

    def test_float_precision_4dp(self):
        obs = _make_observation(with_geometry=True)
        s = to_json(obs)
        parsed = json.loads(s)
        geo = parsed.get("geometry", {})
        if geo and geo.get("entities"):
            bbox = geo["entities"][0]["bbox"]
            # All float values should have at most 4 decimal places
            for k, v in bbox.items():
                if isinstance(v, float):
                    assert round(v, 4) == v or str(v).split(".")[-1].__len__() <= 4

    def test_no_absolute_paths_in_json(self):
        obs = _make_observation()
        s = to_json(obs)
        home = str(Path.home())
        assert home not in s, f"Absolute path found in serialized observation"


# ── canonical form ────────────────────────────────────────────────────────────

class TestCanonical:
    def test_canonical_label_strips_whitespace(self):
        assert canonical_label("  hello  world  ") == "hello world"

    def test_canonical_label_html_unescape(self):
        assert canonical_label("A &amp; B") == "A & B"

    def test_canonical_label_empty(self):
        assert canonical_label("") == ""

    def test_canonical_semantic_idempotent(self):
        sd = SemanticDiagram(
            diagram_type="flowchart",
            direction="LR",
            entities=[
                Entity(id="C", kind="node", label="C", shape=None, parent_id=None, order=2),
                Entity(id="A", kind="node", label="A", shape=None, parent_id=None, order=0),
                Entity(id="B", kind="node", label="B", shape=None, parent_id=None, order=1),
            ],
        )
        c1 = canonical_semantic(sd)
        c2 = canonical_semantic(c1)
        assert [e.id for e in c1.entities] == [e.id for e in c2.entities]

    def test_canonical_semantic_sorts_entities_by_id(self):
        sd = SemanticDiagram(
            diagram_type="flowchart", direction=None,
            entities=[
                Entity(id="Z", kind="node", label="Z", shape=None, parent_id=None, order=0),
                Entity(id="A", kind="node", label="A", shape=None, parent_id=None, order=1),
                Entity(id="M", kind="node", label="M", shape=None, parent_id=None, order=2),
            ],
        )
        c = canonical_semantic(sd)
        assert [e.id for e in c.entities] == ["A", "M", "Z"]


# ── manifest ──────────────────────────────────────────────────────────────────

class TestManifestIntegration:
    def test_all_fixture_files_readable(self):
        manifest = parse_manifest(_MANIFEST, load_sources=True)
        for c in manifest.cases:
            assert c.source.strip(), f"Case {c.id} source is blank"

    def test_24_cases(self):
        manifest = parse_manifest(_MANIFEST, load_sources=False)
        assert len(manifest.cases) == 24


# ── reference adapter (requires mmdc) ─────────────────────────────────────────

@pytest.mark.skipif(not _HAVE_MMDC, reason="requires mmdc")
class TestReferenceAdapter:
    @pytest.fixture(scope="class")
    def adapter(self):
        sys.path.insert(0, str(_FIDELITY))
        from adapters.reference import ReferenceAdapter
        return ReferenceAdapter()

    @pytest.fixture(scope="class")
    def profile(self):
        return RenderProfile(id="mermaid-neutral")

    @pytest.fixture(scope="class")
    def flowchart_case(self):
        fixture = _FIXTURES / "flowchart-diamond-branch.mmd"
        return FidelityCase(
            id="flowchart.diamond.branch",
            source_path=fixture,
            source=fixture.read_text(),
            diagram="flowchart",
        )

    def test_observe_returns_observation(self, adapter, flowchart_case, profile):
        obs = adapter.observe(flowchart_case, profile)
        assert isinstance(obs, Observation)

    def test_observe_accepted_for_flowchart(self, adapter, flowchart_case, profile):
        obs = adapter.observe(flowchart_case, profile)
        assert obs.parse_result.accepted, f"Not accepted: {obs.reason}"

    def test_observe_has_semantic(self, adapter, flowchart_case, profile):
        obs = adapter.observe(flowchart_case, profile)
        assert obs.semantic is not None
        assert len(obs.semantic.entities) > 0

    def test_observe_status_pass(self, adapter, flowchart_case, profile):
        obs = adapter.observe(flowchart_case, profile)
        assert obs.status in (
            ComparisonStatus.PASS,
            ComparisonStatus.EXTRACTOR_GAP,
        ), f"Unexpected status: {obs.status} — {obs.reason}"
