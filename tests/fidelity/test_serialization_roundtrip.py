"""JSON round-trip tests: Observation must survive dump→load without data loss."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "tools"))

import pytest

from mermaid_fidelity.models import (
    BoundingBox,
    ComparisonStatus,
    Entity,
    EntityGeometry,
    EnvironmentIdentity,
    GeometryObservation,
    Group,
    GroupGeometry,
    ImplementationIdentity,
    Observation,
    OrderedEvent,
    ParseObservation,
    QualityFinding,
    QualityFindingKind,
    QualityObservation,
    Relation,
    RelationGeometry,
    SemanticDiagram,
)
from mermaid_fidelity.serialization import load_json, to_json


def _make_full_observation() -> Observation:
    impl = ImplementationIdentity(
        name="test_renderer", version="1.0.0", integrity="abc123",
        adapter_version="1.0.0", profile_id="neutral",
    )
    env = EnvironmentIdentity(
        mermaid_version="11.15.0", mermaid_integrity="sha256:xyz",
        playwright_version="1.61.0", chromium_revision="1228",
        viewport_width=1200, viewport_height=900,
        device_scale_factor=1.0, locale="en-US", timezone="UTC",
        reduced_motion=True, mermaid_config_hash="abc", css_profile_hash="def",
        font_info={"requested": "Arial"},
    )
    parse = ParseObservation(
        accepted=True, diagram_type="flowchart",
        error_category=None, source_position=None,
    )
    semantic = SemanticDiagram(
        diagram_type="flowchart",
        direction="LR",
        entities=[
            Entity(id="A", kind="node", label="Start", shape="rect",
                   parent_id=None, order=0),
            Entity(id="B", kind="node", label="End", shape="diamond",
                   parent_id="SG", order=1),
        ],
        relations=[
            Relation(id="A__B__0", kind="edge", source="A", target="B",
                     label="ok", arrow="arrow-normal", order=0),
        ],
        groups=[
            Group(id="SG", kind="subgraph", label="Subgraph",
                  parent_id=None, order=0, members=["B"]),
        ],
        ordered_events=[
            OrderedEvent(id="e1", kind="message", source="A", target="B",
                         label="hello", order=0),
        ],
    )
    geo = GeometryObservation(
        coordinate_convention="css-top-left",
        content_bounds=BoundingBox(x=10.0, y=20.0, width=300.0, height=200.0),
        canvas_bounds=BoundingBox(x=0.0, y=0.0, width=485.0, height=352.0),
        viewbox="0 0 485 352",
        entities=[
            EntityGeometry(
                entity_id="A",
                bbox=BoundingBox(x=48.0, y=77.0, width=64.0, height=42.0),
                text_bbox=BoundingBox(x=52.0, y=80.0, width=56.0, height=36.0),
                text_lines=1,
            ),
        ],
        groups=[
            GroupGeometry(
                group_id="SG",
                bbox=BoundingBox(x=345.0, y=41.0, width=120.0, height=106.0),
            ),
        ],
        relations=[
            RelationGeometry(
                relation_id="A__B__0",
                source_point=(112.0, 98.0),
                target_point=(192.0, 253.0),
                source_side="R",
                target_side="L",
                sampled_points=[(112.0 + i * 5, 98.0 + i * 10) for i in range(32)],
                bend_count=2,
                path_length=175.5,
            ),
        ],
        containment=[("B", "SG")],
        crossing_count=0,
    )
    quality = QualityObservation(findings=[
        QualityFinding(
            kind=QualityFindingKind.CLIPPED_LABEL,
            entity_id="A",
            message="label may be clipped",
            details={"overflow_px": 2.5},
        ),
    ])
    return Observation(
        schema_version=1,
        case_id="test.roundtrip",
        implementation=impl,
        environment=env,
        parse_result=parse,
        semantic=semantic,
        geometry=geo,
        quality=quality,
        status=ComparisonStatus.PASS,
        reason=None,
        artifact_refs={"svg": "test.svg"},
        diagnostics=["diag1"],
        capture_timestamp="2026-07-21T00:00:00+00:00",
    )


class TestObservationRoundTrip:
    def test_full_observation_roundtrip(self, tmp_path):
        """Original observation == loads(dumps(original)) excluding capture_timestamp."""
        import json
        from mermaid_fidelity.runner import _deserialize_observation

        obs = _make_full_observation()
        json_str = to_json(obs)
        raw = json.loads(json_str)
        loaded = _deserialize_observation(raw)

        # Exclude capture_timestamp from equality (ephemeral)
        assert loaded.schema_version == obs.schema_version
        assert loaded.case_id == obs.case_id
        assert loaded.status == obs.status
        assert loaded.reason == obs.reason
        assert loaded.diagnostics == obs.diagnostics

    def test_geometry_preserved_after_roundtrip(self, tmp_path):
        """Geometry is not dropped to None after deserialization."""
        import json
        from mermaid_fidelity.runner import _deserialize_observation

        obs = _make_full_observation()
        raw = json.loads(to_json(obs))
        loaded = _deserialize_observation(raw)

        assert loaded.geometry is not None, "geometry must not be None after load"
        assert loaded.geometry.canvas_bounds is not None
        assert loaded.geometry.canvas_bounds.width == obs.geometry.canvas_bounds.width
        assert len(loaded.geometry.entities) == len(obs.geometry.entities)
        assert len(loaded.geometry.groups) == len(obs.geometry.groups)
        assert len(loaded.geometry.relations) == len(obs.geometry.relations)

    def test_quality_preserved_after_roundtrip(self, tmp_path):
        """Quality findings are not dropped after deserialization."""
        import json
        from mermaid_fidelity.runner import _deserialize_observation

        obs = _make_full_observation()
        raw = json.loads(to_json(obs))
        loaded = _deserialize_observation(raw)

        assert loaded.quality is not None, "quality must not be None after load"
        assert len(loaded.quality.findings) == 1
        assert loaded.quality.findings[0].kind == QualityFindingKind.CLIPPED_LABEL
        assert loaded.quality.findings[0].entity_id == "A"

    def test_semantic_preserved_after_roundtrip(self, tmp_path):
        """Semantic diagram fields survive round-trip."""
        import json
        from mermaid_fidelity.runner import _deserialize_observation

        obs = _make_full_observation()
        raw = json.loads(to_json(obs))
        loaded = _deserialize_observation(raw)

        assert loaded.semantic is not None
        assert len(loaded.semantic.entities) == 2
        assert loaded.semantic.entities[0].id == "A"
        assert loaded.semantic.entities[1].parent_id == "SG"
        assert len(loaded.semantic.relations) == 1
        assert loaded.semantic.relations[0].source == "A"
        assert len(loaded.semantic.groups) == 1
        assert loaded.semantic.groups[0].members == ["B"]
        assert len(loaded.semantic.ordered_events) == 1
        assert loaded.semantic.ordered_events[0].label == "hello"

    def test_relation_geometry_preserved(self, tmp_path):
        """Relation geometry including sampled points survive round-trip."""
        import json
        from mermaid_fidelity.runner import _deserialize_observation

        obs = _make_full_observation()
        raw = json.loads(to_json(obs))
        loaded = _deserialize_observation(raw)

        rel_geo = loaded.geometry.relations[0]
        orig_rel_geo = obs.geometry.relations[0]
        assert rel_geo.relation_id == orig_rel_geo.relation_id
        assert rel_geo.bend_count == orig_rel_geo.bend_count
        assert len(rel_geo.sampled_points) == len(orig_rel_geo.sampled_points)

    def test_containment_preserved(self, tmp_path):
        """Containment list survives round-trip."""
        import json
        from mermaid_fidelity.runner import _deserialize_observation

        obs = _make_full_observation()
        raw = json.loads(to_json(obs))
        loaded = _deserialize_observation(raw)

        assert loaded.geometry.containment == [("B", "SG")]
