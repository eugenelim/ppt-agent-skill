"""Tests for FinalizedLayout edge invariants (Phase 5 basic, AC-5.1–5.7)."""
from __future__ import annotations

import math
from types import MappingProxyType

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_layout(
    routed_edges=(),
    routing_failures=(),
    canvas_w=200.0,
    canvas_h=200.0,
):
    from scripts.mermaid_render.layout._geometry import (
        FinalizedLayout,
        LayoutDiagnostics,
        Rect,
    )
    return FinalizedLayout(
        node_layouts=MappingProxyType({}),
        group_layouts=MappingProxyType({}),
        routed_edges=routed_edges,
        visible_bounds=Rect(0, 0, canvas_w, canvas_h),
        diagram_padding=10.0,
        canvas_bounds=Rect(0, 0, canvas_w, canvas_h),
        direction="TB",
        diagnostics=LayoutDiagnostics((), (), ()),
        routing_failures=routing_failures,
    )


def _make_metadata(edge_count: int):
    from scripts.mermaid_render.layout._geometry import LayoutMetadata
    return LayoutMetadata(
        direction="TB",
        node_count=0,
        group_count=0,
        edge_count=edge_count,
        algorithm="test",
    )


def _make_edge(edge_id: str, waypoints=None):
    from scripts.mermaid_render.layout._geometry import (
        RoutedEdge, PortLayout, Point,
    )
    if waypoints is None:
        waypoints = (Point(0.0, 0.0), Point(10.0, 10.0))
    src_port = PortLayout(node_id="A", side="bottom", position=Point(0.0, 0.0), direction=Point(0.0, 1.0))
    dst_port = PortLayout(node_id="B", side="top", position=Point(10.0, 10.0), direction=Point(0.0, -1.0))
    return RoutedEdge(
        edge_id=edge_id,
        src_node_id="A",
        dst_node_id="B",
        src_port=src_port,
        dst_port=dst_port,
        waypoints=tuple(waypoints),
        edge_style="solid",
        has_marker_end=True,
        has_marker_start=False,
        label_layout=None,
        src_label_layout=None,
        dst_label_layout=None,
    )


def _make_failure(edge_id: str):
    from scripts.mermaid_render.layout._geometry import RoutingFailure
    return RoutingFailure(
        edge_id=edge_id,
        src_node_id="A",
        dst_node_id="B",
        reason="no path",
    )


def _errors(layout, metadata=None):
    from scripts.mermaid_render.layout._geometry import validate_finalized_layout
    result = validate_finalized_layout(layout, metadata)
    return result.errors


# ── AC-5.1: Edge-count reconciliation ────────────────────────────────────────

class TestEdgeCountReconciliation:
    def test_valid_count_matches(self):
        edge = _make_edge("e1")
        layout = _make_layout(routed_edges=(edge,))
        meta = _make_metadata(1)
        assert not any("mismatch" in e for e in _errors(layout, meta))

    def test_missing_edge_detected(self):
        layout = _make_layout(routed_edges=())
        meta = _make_metadata(1)
        errs = _errors(layout, meta)
        assert any("mismatch" in e for e in errs)

    def test_over_count_detected(self):
        edge1 = _make_edge("e1")
        edge2 = _make_edge("e2")
        layout = _make_layout(routed_edges=(edge1, edge2))
        meta = _make_metadata(1)  # only expected 1
        errs = _errors(layout, meta)
        assert any("mismatch" in e for e in errs)

    def test_failure_counts_toward_total(self):
        failure = _make_failure("e1")
        layout = _make_layout(routing_failures=(failure,))
        meta = _make_metadata(1)
        assert not any("mismatch" in e for e in _errors(layout, meta))

    def test_no_metadata_skips_check(self):
        layout = _make_layout(routed_edges=())
        assert not any("mismatch" in e for e in _errors(layout, None))


# ── AC-5.3: Routed edge ID uniqueness ────────────────────────────────────────

class TestRoutedEdgeIdUniqueness:
    def test_unique_ids_pass(self):
        e1 = _make_edge("e1")
        e2 = _make_edge("e2")
        layout = _make_layout(routed_edges=(e1, e2))
        assert not any("Duplicate routed_edge" in e for e in _errors(layout))

    def test_duplicate_id_detected(self):
        e1 = _make_edge("same")
        e2 = _make_edge("same")
        layout = _make_layout(routed_edges=(e1, e2))
        errs = _errors(layout)
        assert any("Duplicate routed_edge" in e and "same" in e for e in errs)


# ── AC-5.4: Routing failure ID uniqueness ────────────────────────────────────

class TestRoutingFailureIdUniqueness:
    def test_unique_ids_pass(self):
        f1 = _make_failure("f1")
        f2 = _make_failure("f2")
        layout = _make_layout(routing_failures=(f1, f2))
        assert not any("Duplicate routing_failure" in e for e in _errors(layout))

    def test_duplicate_id_detected(self):
        f1 = _make_failure("dup")
        f2 = _make_failure("dup")
        layout = _make_layout(routing_failures=(f1, f2))
        errs = _errors(layout)
        assert any("Duplicate routing_failure" in e and "dup" in e for e in errs)


# ── AC-5.5: Routed ∩ failures disjointness ───────────────────────────────────

class TestRoutedFailureDisjointness:
    def test_disjoint_ids_pass(self):
        e = _make_edge("routed")
        f = _make_failure("failed")
        layout = _make_layout(routed_edges=(e,), routing_failures=(f,))
        assert not any("both" in e for e in _errors(layout))

    def test_same_id_in_both_detected(self):
        e = _make_edge("shared")
        f = _make_failure("shared")
        layout = _make_layout(routed_edges=(e,), routing_failures=(f,))
        errs = _errors(layout)
        assert any("both" in e and "shared" in e for e in errs)


# ── AC-5.6: Waypoint finiteness and distinctness ─────────────────────────────

class TestWaypointValidity:
    def test_finite_distinct_waypoints_pass(self):
        from scripts.mermaid_render.layout._geometry import Point
        e = _make_edge("e1", [Point(0.0, 0.0), Point(10.0, 10.0)])
        layout = _make_layout(routed_edges=(e,))
        assert not any("waypoint" in e.lower() and ("finite" in e.lower() or "non-finite" in e.lower()) for e in _errors(layout))

    def test_nan_waypoint_detected(self):
        from scripts.mermaid_render.layout._geometry import Point
        e = _make_edge("e1", [Point(float("nan"), 0.0), Point(10.0, 10.0)])
        layout = _make_layout(routed_edges=(e,))
        errs = _errors(layout)
        assert any("non-finite" in e for e in errs)

    def test_inf_waypoint_detected(self):
        from scripts.mermaid_render.layout._geometry import Point
        e = _make_edge("e1", [Point(0.0, float("inf")), Point(10.0, 10.0)])
        layout = _make_layout(routed_edges=(e,))
        errs = _errors(layout)
        assert any("non-finite" in e for e in errs)

    def test_fewer_than_2_waypoints_detected(self):
        from scripts.mermaid_render.layout._geometry import Point
        e = _make_edge("e1", [Point(0.0, 0.0)])
        layout = _make_layout(routed_edges=(e,))
        errs = _errors(layout)
        assert any("fewer than 2 waypoints" in e for e in errs)

    def test_zero_length_segment_detected(self):
        from scripts.mermaid_render.layout._geometry import Point
        e = _make_edge("e1", [Point(5.0, 5.0), Point(5.0, 5.0)])
        layout = _make_layout(routed_edges=(e,))
        errs = _errors(layout)
        assert any("zero-length segment" in e for e in errs)


# ── FinalizedLayout.validate() method (AC-5.1) ───────────────────────────────

class TestFinalizedLayoutValidateMethod:
    def test_validate_method_exists(self):
        layout = _make_layout()
        assert hasattr(layout, "validate")

    def test_validate_without_metadata(self):
        layout = _make_layout()
        result = layout.validate()
        from scripts.mermaid_render.layout._geometry import ValidationResult
        assert isinstance(result, ValidationResult)

    def test_validate_with_metadata(self):
        e = _make_edge("e1")
        layout = _make_layout(routed_edges=(e,))
        meta = _make_metadata(1)
        result = layout.validate(meta)
        assert not any("mismatch" in e for e in result.errors)

    def test_validate_with_metadata_detects_mismatch(self):
        layout = _make_layout(routed_edges=())
        meta = _make_metadata(2)
        result = layout.validate(meta)
        assert any("mismatch" in e for e in result.errors)
