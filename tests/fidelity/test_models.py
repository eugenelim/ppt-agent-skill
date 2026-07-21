"""Tests for core data model dataclasses and enums."""
from __future__ import annotations

import sys
from pathlib import Path

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
    GeometryObservation,
    Group,
    ImplementationIdentity,
    Observation,
    OrderedEvent,
    ParseObservation,
    QualityFinding,
    QualityFindingKind,
    QualityObservation,
    Relation,
    RenderProfile,
    SemanticDiagram,
)


class TestBoundingBox:
    def test_right(self):
        bb = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
        assert bb.right == 110.0

    def test_bottom(self):
        bb = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
        assert bb.bottom == 70.0

    def test_cx(self):
        bb = BoundingBox(x=0.0, y=0.0, width=100.0, height=60.0)
        assert bb.cx == 50.0

    def test_cy(self):
        bb = BoundingBox(x=0.0, y=0.0, width=100.0, height=60.0)
        assert bb.cy == 30.0

    def test_area(self):
        bb = BoundingBox(x=0.0, y=0.0, width=4.0, height=5.0)
        assert bb.area() == 20.0

    def test_zero_area(self):
        bb = BoundingBox(x=0.0, y=0.0, width=0.0, height=0.0)
        assert bb.area() == 0.0


class TestComparisonStatus:
    def test_is_str_enum(self):
        assert ComparisonStatus.PASS == "PASS"
        assert ComparisonStatus.SEMANTIC_MISMATCH == "SEMANTIC_MISMATCH"

    def test_all_values(self):
        expected = {
            "PASS", "PARSE_MISMATCH", "SEMANTIC_MISMATCH",
            "RELATIVE_LAYOUT_MISMATCH", "QUALITY_FAILURE",
            "EXTRACTOR_GAP", "REFERENCE_RENDER_FAILURE", "NATIVE_UNSUPPORTED",
            "NONDETERMINISTIC", "STALE_ORACLE", "INVALID_MANIFEST", "INTERNAL_ERROR",
        }
        actual = {s.value for s in ComparisonStatus}
        assert actual == expected

    def test_new_statuses_exist(self):
        assert ComparisonStatus.RELATIVE_LAYOUT_MISMATCH.value == "RELATIVE_LAYOUT_MISMATCH"
        assert ComparisonStatus.STALE_ORACLE.value == "STALE_ORACLE"
        assert ComparisonStatus.INVALID_MANIFEST.value == "INVALID_MANIFEST"


class TestObservation:
    def _make_observation(self, status=ComparisonStatus.PASS) -> Observation:
        impl = ImplementationIdentity(
            name="test", version="1.0", integrity=None,
            adapter_version="1.0", profile_id="neutral",
        )
        env = EnvironmentIdentity(
            mermaid_version="1.0", mermaid_integrity=None,
            playwright_version="1.0", chromium_revision="0",
            viewport_width=1200, viewport_height=900,
            device_scale_factor=1.0, locale="en-US", timezone="UTC",
            reduced_motion=True, mermaid_config_hash="", css_profile_hash="",
            font_info={},
        )
        parse = ParseObservation(accepted=True, diagram_type="flowchart",
                                 error_category=None, source_position=None)
        return Observation(
            schema_version=1,
            case_id="test.case",
            implementation=impl,
            environment=env,
            parse_result=parse,
            semantic=None,
            geometry=None,
            quality=None,
            status=status,
            reason=None,
        )

    def test_construction(self):
        obs = self._make_observation()
        assert obs.schema_version == 1
        assert obs.status == ComparisonStatus.PASS

    def test_default_artifact_refs(self):
        obs = self._make_observation()
        assert obs.artifact_refs == {}

    def test_default_diagnostics(self):
        obs = self._make_observation()
        assert obs.diagnostics == []

    def test_capture_timestamp_defaults_none(self):
        obs = self._make_observation()
        assert obs.capture_timestamp is None


class TestSemanticDiagram:
    def test_empty(self):
        sd = SemanticDiagram(diagram_type="flowchart", direction=None)
        assert sd.entities == []
        assert sd.relations == []
        assert sd.groups == []
        assert sd.ordered_events == []

    def test_with_entities(self):
        e = Entity(id="A", kind="node", label="A", shape="rect", parent_id=None, order=0)
        sd = SemanticDiagram(diagram_type="flowchart", direction="LR", entities=[e])
        assert len(sd.entities) == 1
        assert sd.entities[0].id == "A"


class TestRenderProfile:
    def test_defaults(self):
        profile = RenderProfile(id="test")
        assert profile.viewport_width == 1200
        assert profile.viewport_height == 900
        assert profile.device_scale_factor == 1.0
        assert profile.locale == "en-US"
        assert profile.timezone == "UTC"
        assert profile.reduced_motion is True
        assert profile.css_path is None
        assert profile.mermaid_config is None


class TestQualityFindingKind:
    def test_is_str_enum(self):
        assert QualityFindingKind.CONTENT_OVERFLOW == "content_overflow"
        assert QualityFindingKind.OUTSIDE_CANVAS == "outside_canvas"

    def test_expected_values(self):
        expected = {
            "content_overflow", "outside_canvas", "zero_area",
            "unrelated_overlap", "group_containment_violation",
            "clipped_label", "detached_endpoint",
        }
        actual = {k.value for k in QualityFindingKind}
        assert expected.issubset(actual), f"Missing: {expected - actual}"
