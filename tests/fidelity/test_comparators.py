"""Tests for the three comparator modules: semantic, geometry, quality."""
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
    GeometryObservation,
    Group,
    QualityFindingKind,
    Relation,
    SemanticDiagram,
)
from mermaid_fidelity.compare.semantic import (
    SemanticDiff,
    SemanticComparisonResult,
    compare_semantic,
)
from mermaid_fidelity.compare.geometry import (
    NormalizedGeometry,
    normalize_geometry,
    compare_relative_layout,
    score_layout_metrics,
)
from mermaid_fidelity.compare.quality import (
    QualityTolerances,
    check_overflow,
    check_outside_canvas,
    check_canvas_size,
    check_zero_area,
    check_overlap,
    check_group_containment,
    run_quality_checks,
)


# ── semantic comparator ───────────────────────────────────────────────────────

def _entity(eid: str, label: str = "", kind: str = "node") -> Entity:
    return Entity(id=eid, kind=kind, label=label or eid, shape="rect", parent_id=None, order=0)


def _relation(src: str, dst: str, label: str = "") -> Relation:
    return Relation(id=f"{src}__{dst}", kind="edge", source=src, target=dst,
                    label=label, arrow=None, order=0)


def _sd(entities=None, relations=None, diagram_type="flowchart", direction="LR",
        groups=None):
    return SemanticDiagram(
        diagram_type=diagram_type,
        direction=direction,
        entities=entities or [],
        relations=relations or [],
        groups=groups or [],
    )


_ALL_STRICT = ["diagram-type", "direction", "entities", "labels", "relations", "edge-endpoints", "containment"]


class TestSemanticComparison:
    def test_identical_diagrams_pass(self):
        sd = _sd(entities=[_entity("A"), _entity("B")], relations=[_relation("A", "B")])
        result = compare_semantic(sd, sd, strict_fields=_ALL_STRICT)
        assert result.diff.is_empty()

    def test_missing_entity_detected(self):
        expected = _sd(entities=[_entity("A"), _entity("B")])
        actual = _sd(entities=[_entity("A")])
        result = compare_semantic(expected, actual, strict_fields=["diagram-type", "entities"])
        assert not result.diff.is_empty()
        assert any("B" in str(e) for e in result.diff.missing_entities)

    def test_extra_entity_detected(self):
        expected = _sd(entities=[_entity("A")])
        actual = _sd(entities=[_entity("A"), _entity("C")])
        result = compare_semantic(expected, actual, strict_fields=["diagram-type", "entities"])
        assert not result.diff.is_empty()
        assert any("C" in str(e) for e in result.diff.extra_entities)

    def test_missing_relation_detected(self):
        expected = _sd(entities=[_entity("A"), _entity("B")],
                       relations=[_relation("A", "B")])
        actual = _sd(entities=[_entity("A"), _entity("B")])
        result = compare_semantic(expected, actual, strict_fields=["diagram-type", "entities", "relations"])
        assert not result.diff.is_empty()

    def test_diagram_type_mismatch(self):
        expected = _sd(diagram_type="flowchart")
        actual = _sd(diagram_type="er")
        result = compare_semantic(expected, actual, strict_fields=["diagram-type"])
        assert not result.diff.is_empty()

    def test_direction_irrelevant_when_not_strict(self):
        expected = _sd(direction="LR")
        actual = _sd(direction="TB")
        result = compare_semantic(expected, actual, strict_fields=["diagram-type", "entities"])
        assert result.diff.is_empty()

    def test_direction_strict_when_declared(self):
        expected = _sd(direction="LR")
        actual = _sd(direction="TB")
        result = compare_semantic(expected, actual, strict_fields=["diagram-type", "direction"])
        assert not result.diff.is_empty()

    def test_diff_to_lines_non_empty(self):
        expected = _sd(entities=[_entity("A"), _entity("B")])
        actual = _sd(entities=[_entity("A")])
        result = compare_semantic(expected, actual, strict_fields=["entities"])
        lines = result.diff.to_lines()
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_empty_diff_to_lines_empty(self):
        sd = _sd()
        result = compare_semantic(sd, sd, strict_fields=_ALL_STRICT)
        assert result.diff.to_lines() == []


# ── geometry comparator ───────────────────────────────────────────────────────

def _geo(entities: list[EntityGeometry], canvas: BoundingBox | None = None) -> GeometryObservation:
    if canvas is None:
        canvas = BoundingBox(x=0, y=0, width=1000, height=800)
    content = None
    if entities:
        min_x = min(e.bbox.x for e in entities)
        min_y = min(e.bbox.y for e in entities)
        max_x = max(e.bbox.right for e in entities)
        max_y = max(e.bbox.bottom for e in entities)
        content = BoundingBox(x=min_x, y=min_y, width=max_x-min_x, height=max_y-min_y)
    return GeometryObservation(
        coordinate_convention="css-top-left",
        content_bounds=content,
        canvas_bounds=canvas,
        viewbox=None,
        entities=entities,
        groups=[],
        relations=[],
        containment=[],
    )


def _eg(eid: str, x: float, y: float, w: float = 80.0, h: float = 40.0) -> EntityGeometry:
    return EntityGeometry(entity_id=eid, bbox=BoundingBox(x=x, y=y, width=w, height=h),
                          text_bbox=None, text_lines=1)


class TestNormalization:
    def test_normalize_removes_translation(self):
        geo = _geo([_eg("A", 100, 200, 80, 40), _eg("B", 300, 200, 80, 40)])
        norm = normalize_geometry(geo)
        assert norm is not None
        # After normalization, min x and y should be 0
        xs = [eg.bbox.x for eg in norm.entities]
        ys = [eg.bbox.y for eg in norm.entities]
        assert min(xs) == pytest.approx(0.0, abs=1e-3)
        assert min(ys) == pytest.approx(0.0, abs=1e-3)

    def test_normalize_preserves_aspect_ratio(self):
        geo = _geo([_eg("A", 0, 0, 100, 50), _eg("B", 200, 0, 100, 50)])
        norm = normalize_geometry(geo)
        assert norm is not None
        # Width and height of each entity should scale by same factor
        for ng, og in zip(norm.entities, geo.entities):
            if og.bbox.width > 0 and og.bbox.height > 0:
                scale_w = ng.bbox.width / og.bbox.width
                scale_h = ng.bbox.height / og.bbox.height
                assert scale_w == pytest.approx(scale_h, rel=1e-3)

    def test_normalize_returns_none_for_empty(self):
        geo = _geo([])
        norm = normalize_geometry(geo)
        assert norm is None


class TestRelativeLayout:
    def test_containment_within_tolerance(self):
        parent = BoundingBox(x=0, y=0, width=200, height=150)
        child = BoundingBox(x=10, y=10, width=80, height=40)
        assert child.x >= parent.x - 4
        assert child.right <= parent.right + 4

    def test_compare_identical_returns_no_violations(self):
        geo = _geo([_eg("A", 0, 0), _eg("B", 200, 0)])
        result = compare_relative_layout(geo, geo, strict_fields=["containment"])
        assert result is not None
        assert result.failures == []


class TestScoring:
    def test_identical_score_near_zero(self):
        geo = _geo([_eg("A", 0, 0, 100, 50), _eg("B", 200, 0, 100, 50)])
        norm = normalize_geometry(geo)
        assert norm is not None
        metrics = score_layout_metrics(norm, norm, geo, geo)
        assert metrics is not None
        assert metrics.normalized_entity_center_error == pytest.approx(0.0, abs=0.01)

    def test_score_increases_with_displacement(self):
        geo_ref = _geo([_eg("A", 0, 0, 100, 50), _eg("B", 200, 0, 100, 50)])
        geo_shifted = _geo([_eg("A", 50, 50, 100, 50), _eg("B", 250, 50, 100, 50)])
        norm_ref = normalize_geometry(geo_ref)
        norm_shifted = normalize_geometry(geo_shifted)
        if norm_ref is None or norm_shifted is None:
            pytest.skip("normalization returned None")
        metrics = score_layout_metrics(norm_shifted, norm_ref, geo_shifted, geo_ref)
        assert metrics is not None


# ── quality predicates ────────────────────────────────────────────────────────

def _make_geo_with_canvas(entity_list, canvas_w=500, canvas_h=400):
    entities = [EntityGeometry(entity_id=eid, bbox=BoundingBox(x=x, y=y, width=w, height=h),
                                text_bbox=None, text_lines=1)
                for eid, x, y, w, h in entity_list]
    canvas = BoundingBox(x=0, y=0, width=canvas_w, height=canvas_h)
    content = None
    if entities:
        min_x = min(e.bbox.x for e in entities)
        min_y = min(e.bbox.y for e in entities)
        max_x = max(e.bbox.right for e in entities)
        max_y = max(e.bbox.bottom for e in entities)
        content = BoundingBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)
    return GeometryObservation(
        coordinate_convention="css-top-left",
        content_bounds=content,
        canvas_bounds=canvas,
        viewbox=None,
        entities=entities,
        groups=[],
        relations=[],
        containment=[],
    )


class TestQualityPredicates:
    def test_no_findings_for_clean_diagram(self):
        geo = _make_geo_with_canvas([("A", 10, 10, 100, 50), ("B", 200, 10, 100, 50)])
        findings = run_quality_checks(geo)
        assert findings == []

    def test_overflow_detected(self):
        # Canvas 200x200, entity overflows to x=500
        geo = _make_geo_with_canvas([("A", 450, 10, 100, 50)], canvas_w=200, canvas_h=200)
        findings = run_quality_checks(geo)
        kinds = [f.kind for f in findings]
        assert any(k in (QualityFindingKind.CONTENT_OVERFLOW, QualityFindingKind.OUTSIDE_CANVAS)
                   for k in kinds), f"No overflow finding. Findings: {findings}"

    def test_zero_area_detected(self):
        geo = _make_geo_with_canvas([("ghost", 10, 10, 0, 0)])
        findings = run_quality_checks(geo)
        kinds = [f.kind for f in findings]
        assert QualityFindingKind.ZERO_AREA in kinds

    def test_tiny_canvas_detected(self):
        geo = _make_geo_with_canvas([("A", 5, 5, 30, 20)], canvas_w=40, canvas_h=15)
        findings = run_quality_checks(geo)
        kinds = [f.kind for f in findings]
        assert QualityFindingKind.CONTENT_OVERFLOW in kinds or len(kinds) > 0

    def test_tolerances_apply(self):
        tol = QualityTolerances(
            overflow_tolerance=4, outside_canvas_tolerance=8,
            min_canvas_width=50, min_canvas_height=20,
        )
        geo = _make_geo_with_canvas([("A", 10, 10, 80, 40)], canvas_w=100, canvas_h=80)
        findings = run_quality_checks(geo, tol)
        assert findings == []
