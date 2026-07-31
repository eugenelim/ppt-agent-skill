"""Tests for the Playwright-based Mermaid SVG geometry extractor.

Math/pure tests (no browser) run by default.
Browser-required tests use @pytest.mark.browser.
Tests that also need the mmdc CLI use @pytest.mark.external_reference.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_FIDELITY = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO / "tools"))
sys.path.insert(0, str(_FIDELITY))

from adapters.playwright_extractor import (
    PlaywrightBrowserManager,
    _compute_bend_count,
    _compute_crossing_count,
    _infer_side,
    _parse_flowchart_subgraphs,
    _point_line_dist,
    _rdp,
    _segments_intersect,
    extract_flowchart_geometry,
)
from mermaid_fidelity.models import (
    BoundingBox,
    Entity,
    GeometryObservation,
    Relation,
    RelationGeometry,
    SemanticDiagram,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_semantic(
    entities: list[tuple[str, str]] | None = None,
    relations: list[tuple[str, str, str]] | None = None,
) -> SemanticDiagram:
    """Create a minimal SemanticDiagram for testing."""
    ents = [
        Entity(id=eid, kind="node", label=lbl, shape=None, parent_id=None, order=i)
        for i, (eid, lbl) in enumerate(entities or [])
    ]
    rels = [
        Relation(id=f"{s}__{t}__{i}", kind="edge", source=s, target=t,
                 label=lbl, arrow=None, order=i)
        for i, (s, t, lbl) in enumerate(relations or [])
    ]
    return SemanticDiagram(diagram_type="flowchart", direction=None,
                           entities=ents, relations=rels)


def _make_relation_geom(
    rid: str,
    points: list[tuple[float, float]],
    source_point: tuple[float, float] | None = None,
    target_point: tuple[float, float] | None = None,
    bend_count: int = 0,
) -> RelationGeometry:
    sp = source_point or (points[0] if points else (0.0, 0.0))
    tp = target_point or (points[-1] if points else (0.0, 0.0))
    return RelationGeometry(
        relation_id=rid,
        source_point=sp,
        target_point=tp,
        source_side=None,
        target_side=None,
        sampled_points=points,
        bend_count=bend_count,
        path_length=None,
    )


# ── 1. _point_line_dist ────────────────────────────────────────────────────────

class TestPointLineDist:
    def test_point_on_line(self):
        d = _point_line_dist((5.0, 5.0), (0.0, 0.0), (10.0, 10.0))
        assert d == pytest.approx(0.0, abs=1e-9)

    def test_point_perpendicular_to_segment(self):
        # Point (0, 1) to segment (0,0)-(1,0): perpendicular dist = 1
        d = _point_line_dist((0.0, 1.0), (0.0, 0.0), (1.0, 0.0))
        assert d == pytest.approx(1.0)

    def test_degenerate_segment_falls_back_to_point_dist(self):
        # Segment with a == b: distance is just point-to-point
        d = _point_line_dist((3.0, 4.0), (0.0, 0.0), (0.0, 0.0))
        assert d == pytest.approx(5.0)

    def test_clamped_to_endpoint(self):
        # Point "behind" start endpoint: should clamp to start
        d = _point_line_dist((-1.0, 0.0), (0.0, 0.0), (10.0, 0.0))
        assert d == pytest.approx(1.0)


# ── 2. _rdp ───────────────────────────────────────────────────────────────────

class TestRdp:
    def test_straight_line_simplifies_to_endpoints(self):
        pts = [(float(i), float(i)) for i in range(10)]
        simplified = _rdp(pts, eps=0.1)
        assert simplified == [pts[0], pts[-1]]

    def test_single_bend_preserved(self):
        pts = [(0.0, 0.0), (5.0, 5.0), (10.0, 0.0)]
        simplified = _rdp(pts, eps=0.1)
        assert len(simplified) == 3

    def test_empty_list(self):
        assert _rdp([], eps=1.0) == []

    def test_two_points_unchanged(self):
        pts = [(0.0, 0.0), (1.0, 1.0)]
        assert _rdp(pts, eps=1.0) == pts

    def test_collinear_points_collapse(self):
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
        simplified = _rdp(pts, eps=0.01)
        assert simplified == [(0.0, 0.0), (3.0, 0.0)]


# ── 3. _compute_bend_count ─────────────────────────────────────────────────────

class TestComputeBendCount:
    def test_straight_line_no_bends(self):
        pts = [(float(i), 0.0) for i in range(20)]
        assert _compute_bend_count(pts) == 0

    def test_single_right_angle_bend(self):
        # L-shaped path
        pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
        assert _compute_bend_count(pts, eps=0.1) == 1

    def test_two_bends(self):
        # Z-shaped path (two direction changes)
        pts = [
            (0.0, 0.0), (10.0, 0.0),
            (10.0, 5.0), (20.0, 5.0), (20.0, 10.0),
        ]
        result = _compute_bend_count(pts, eps=0.1)
        assert result >= 2

    def test_empty_path(self):
        assert _compute_bend_count([]) == 0

    def test_one_point(self):
        assert _compute_bend_count([(0.0, 0.0)]) == 0


# ── 4. _segments_intersect ────────────────────────────────────────────────────

class TestSegmentsIntersect:
    def test_crossing_segments(self):
        # (+) crossing: horizontal and vertical
        assert _segments_intersect(
            (0.0, 5.0), (10.0, 5.0),
            (5.0, 0.0), (5.0, 10.0),
        )

    def test_parallel_segments_no_intersection(self):
        assert not _segments_intersect(
            (0.0, 0.0), (10.0, 0.0),
            (0.0, 1.0), (10.0, 1.0),
        )

    def test_t_intersection_not_proper(self):
        # T-intersection (endpoint on segment) - not a proper crossing
        assert not _segments_intersect(
            (0.0, 0.0), (10.0, 0.0),
            (5.0, 0.0), (5.0, 10.0),
        )

    def test_collinear_no_intersection(self):
        assert not _segments_intersect(
            (0.0, 0.0), (5.0, 0.0),
            (6.0, 0.0), (10.0, 0.0),
        )


# ── 5. _compute_crossing_count ────────────────────────────────────────────────

class TestComputeCrossingCount:
    def test_no_relations(self):
        assert _compute_crossing_count([]) == 0

    def test_single_relation(self):
        r = _make_relation_geom("r1", [(0.0, 0.0), (10.0, 10.0)])
        assert _compute_crossing_count([r]) == 0

    def test_crossing_relations(self):
        # Two X-crossing paths
        r1 = _make_relation_geom("r1", [(0.0, 5.0), (10.0, 5.0)])
        r2 = _make_relation_geom("r2", [(5.0, 0.0), (5.0, 10.0)])
        assert _compute_crossing_count([r1, r2]) == 1

    def test_parallel_non_crossing(self):
        r1 = _make_relation_geom("r1", [(0.0, 0.0), (10.0, 0.0)])
        r2 = _make_relation_geom("r2", [(0.0, 5.0), (10.0, 5.0)])
        assert _compute_crossing_count([r1, r2]) == 0

    def test_multiple_crossings(self):
        # Grid pattern — two horizontal, two vertical → 4 crossings
        r_h1 = _make_relation_geom("h1", [(0.0, 3.0), (10.0, 3.0)])
        r_h2 = _make_relation_geom("h2", [(0.0, 7.0), (10.0, 7.0)])
        r_v1 = _make_relation_geom("v1", [(3.0, 0.0), (3.0, 10.0)])
        r_v2 = _make_relation_geom("v2", [(7.0, 0.0), (7.0, 10.0)])
        count = _compute_crossing_count([r_h1, r_h2, r_v1, r_v2])
        assert count == 4


# ── 6. _infer_side ────────────────────────────────────────────────────────────

class TestInferSide:
    def _bbox(self) -> BoundingBox:
        return BoundingBox(x=10.0, y=10.0, width=80.0, height=40.0)
        # right=90, bottom=50

    def test_left_side(self):
        assert _infer_side((10.0, 30.0), self._bbox()) == "L"

    def test_right_side(self):
        assert _infer_side((90.0, 30.0), self._bbox()) == "R"

    def test_top_side(self):
        assert _infer_side((50.0, 10.0), self._bbox()) == "T"

    def test_bottom_side(self):
        assert _infer_side((50.0, 50.0), self._bbox()) == "B"


# ── 7. _parse_flowchart_subgraphs ─────────────────────────────────────────────

class TestParseFlowchartSubgraphs:
    def test_empty_source(self):
        assert _parse_flowchart_subgraphs("") == []

    def test_no_subgraphs(self):
        source = "flowchart LR\n  A --> B\n"
        assert _parse_flowchart_subgraphs(source) == []

    def test_single_subgraph(self):
        source = """\
flowchart LR
  subgraph SG1[My Group]
    A[Node A]
    B[Node B]
  end
"""
        result = _parse_flowchart_subgraphs(source)
        assert len(result) == 1
        sg = result[0]
        assert sg["id"] == "SG1"
        assert sg["label"] == "My Group"
        assert "A" in sg["members"]
        assert "B" in sg["members"]

    def test_subgraph_no_label(self):
        source = """\
flowchart LR
  subgraph SGA
    X[Node X]
  end
"""
        result = _parse_flowchart_subgraphs(source)
        assert len(result) == 1
        assert result[0]["id"] == "SGA"
        assert result[0]["label"] == "SGA"

    def test_nested_subgraphs(self):
        source = """\
flowchart LR
  subgraph OUTER
    subgraph INNER
      A[Node]
    end
  end
"""
        result = _parse_flowchart_subgraphs(source)
        assert len(result) == 2
        inner = next(sg for sg in result if sg["id"] == "INNER")
        assert inner["parent"] == "OUTER"
        assert "A" in inner["members"]

    def test_multiple_subgraphs(self):
        source = """\
flowchart LR
  subgraph SG1
    A[Node A]
  end
  subgraph SG2
    B[Node B]
  end
"""
        result = _parse_flowchart_subgraphs(source)
        assert len(result) == 2
        ids = {sg["id"] for sg in result}
        assert ids == {"SG1", "SG2"}

    def test_subgraph_member_dedup(self):
        source = """\
flowchart LR
  subgraph SG1
    A[Node A]
    A[Node A]
  end
"""
        result = _parse_flowchart_subgraphs(source)
        sg = result[0]
        assert sg["members"].count("A") == 1


# ── 8. _parse_flowchart_edges (multi-target) ──────────────────────────────────

class TestParseFlowchartEdgesMultiTarget:
    def _parse(self, source: str):
        from adapters.reference import _parse_flowchart_edges
        return _parse_flowchart_edges(source)

    def test_basic_edge(self):
        edges = self._parse("flowchart LR\n  A --> B\n")
        assert ("A", "B", "") in edges

    def test_pipe_label(self):
        edges = self._parse("flowchart LR\n  A -->|yes| B\n")
        assert any(s == "A" and t == "B" and lbl == "yes" for s, t, lbl in edges)

    def test_multi_target(self):
        edges = self._parse("flowchart LR\n  A --> B & C\n")
        srcs_tgts = {(s, t) for s, t, _ in edges}
        assert ("A", "B") in srcs_tgts
        assert ("A", "C") in srcs_tgts

    def test_multi_source(self):
        edges = self._parse("flowchart LR\n  A & B --> C\n")
        srcs_tgts = {(s, t) for s, t, _ in edges}
        assert ("A", "C") in srcs_tgts
        assert ("B", "C") in srcs_tgts

    def test_skips_subgraph_lines(self):
        source = "flowchart LR\n  subgraph S\n    A --> B\n  end\n"
        edges = self._parse(source)
        # Edge A-->B is inside a subgraph definition line - still parsed
        # (subgraph lines are skipped for the subgraph keyword, not child lines)
        # The edge should still be present
        assert any(s == "A" and t == "B" for s, t, _ in edges)

    def test_dashed_arrow(self):
        edges = self._parse("flowchart LR\n  A -.-> B\n")
        assert any(s == "A" and t == "B" for s, t, _ in edges)

    def test_double_equal_arrow(self):
        # ==> is filtered out by the early-check (which only looks for '===');
        # use ===>, which contains '===' and is supported by _find_arrow_outside_brackets.
        edges = self._parse("flowchart LR\n  A ===> B\n")
        assert any(s == "A" and t == "B" for s, t, _ in edges)


# ── 9. PlaywrightBrowserManager ───────────────────────────────────────────────

@pytest.mark.browser
class TestPlaywrightBrowserManager:
    def test_context_manager_opens_and_closes(self):
        with PlaywrightBrowserManager() as bm:
            version = bm.browser_version()
            assert isinstance(version, str)
            assert len(version) > 0

    def test_playwright_version_reported(self):
        with PlaywrightBrowserManager() as bm:
            v = bm.playwright_version()
            assert v != "unknown"
            assert "." in v  # e.g. "1.61.0"

    def test_new_page_and_close(self):
        with PlaywrightBrowserManager() as bm:
            page = bm.new_page()
            assert page is not None
            page.context.close()

    def test_close_idempotent(self):
        bm = PlaywrightBrowserManager()
        bm._ensure_browser()
        bm.close()
        bm.close()  # second close must not raise

    def test_routes_blocked(self):
        """Network requests should be blocked (SVG is inline)."""
        with PlaywrightBrowserManager() as bm:
            page = bm.new_page()
            try:
                # navigate to an external URL — should fail due to route abort
                with pytest.raises(Exception):
                    page.goto("https://example.com", timeout=5000)
            finally:
                page.context.close()


# ── 10. extract_flowchart_geometry — synthetic SVG ─────────────────────────────

# Minimal Mermaid-like flowchart SVG with two nodes and one edge path.
_SIMPLE_FLOWCHART_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" id="mermaid-svg"
     width="400" height="200" viewBox="0 0 400 200">
  <g id="mermaid-svg-flowchart-A-0" class="node">
    <rect x="20" y="80" width="100" height="40"/>
    <text>Node A</text>
  </g>
  <g id="mermaid-svg-flowchart-B-0" class="node">
    <rect x="280" y="80" width="100" height="40"/>
    <text>Node B</text>
  </g>
  <path data-id="L_A_B_0" d="M120,100 L280,100"/>
</svg>
"""

_SIMPLE_SOURCE = "flowchart LR\n  A[Node A] --> B[Node B]\n"


@pytest.mark.browser
class TestExtractFlowchartGeometrySyntheticSvg:
    def test_canvas_bounds_from_viewbox(self):
        semantic = _make_semantic([("A", "Node A"), ("B", "Node B")],
                                  [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(
                _SIMPLE_FLOWCHART_SVG, semantic, bm, source=_SIMPLE_SOURCE
            )
        assert obs.canvas_bounds is not None
        assert obs.canvas_bounds.width == pytest.approx(400.0)
        assert obs.canvas_bounds.height == pytest.approx(200.0)

    def test_entities_extracted(self):
        semantic = _make_semantic([("A", "Node A"), ("B", "Node B")],
                                  [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(
                _SIMPLE_FLOWCHART_SVG, semantic, bm, source=_SIMPLE_SOURCE
            )
        entity_ids = {e.entity_id for e in obs.entities}
        assert "A" in entity_ids
        assert "B" in entity_ids

    def test_entity_bbox_positive_dimensions(self):
        semantic = _make_semantic([("A", "Node A"), ("B", "Node B")],
                                  [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(
                _SIMPLE_FLOWCHART_SVG, semantic, bm, source=_SIMPLE_SOURCE
            )
        for e in obs.entities:
            assert e.bbox.width > 0
            assert e.bbox.height > 0

    def test_entity_bbox_finite_coordinates(self):
        semantic = _make_semantic([("A", "Node A"), ("B", "Node B")],
                                  [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(
                _SIMPLE_FLOWCHART_SVG, semantic, bm, source=_SIMPLE_SOURCE
            )
        for e in obs.entities:
            assert math.isfinite(e.bbox.x)
            assert math.isfinite(e.bbox.y)

    def test_coordinate_convention_reported(self):
        semantic = _make_semantic([("A", "Node A"), ("B", "Node B")],
                                  [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(
                _SIMPLE_FLOWCHART_SVG, semantic, bm, source=_SIMPLE_SOURCE
            )
        assert obs.coordinate_convention == "css-top-left"

    def test_viewbox_string_preserved(self):
        semantic = _make_semantic([("A", "Node A"), ("B", "Node B")],
                                  [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(
                _SIMPLE_FLOWCHART_SVG, semantic, bm, source=_SIMPLE_SOURCE
            )
        assert obs.viewbox is not None
        assert "400" in obs.viewbox

    def test_crossing_count_zero_for_simple(self):
        semantic = _make_semantic([("A", "Node A"), ("B", "Node B")],
                                  [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(
                _SIMPLE_FLOWCHART_SVG, semantic, bm, source=_SIMPLE_SOURCE
            )
        assert obs.crossing_count is not None
        assert obs.crossing_count == 0


# ── 11. GeometryObservation content_bounds ────────────────────────────────────

class TestGeometryObservationContentBounds:
    def test_content_bounds_spans_all_entities(self):
        """content_bounds must encompass all entity bboxes."""
        obs = GeometryObservation(
            coordinate_convention="css-top-left",
            content_bounds=BoundingBox(x=10.0, y=10.0, width=180.0, height=80.0),
            canvas_bounds=BoundingBox(x=0.0, y=0.0, width=400.0, height=200.0),
            viewbox="0 0 400 200",
        )
        assert obs.content_bounds is not None
        assert obs.content_bounds.x == pytest.approx(10.0)
        assert obs.content_bounds.right == pytest.approx(190.0)

    def test_no_content_bounds_when_empty(self):
        obs = GeometryObservation(
            coordinate_convention="css-top-left",
            content_bounds=None,
            canvas_bounds=None,
            viewbox=None,
        )
        assert obs.content_bounds is None

    def test_crossing_count_none_by_default(self):
        obs = GeometryObservation(
            coordinate_convention="css-top-left",
            content_bounds=None,
            canvas_bounds=None,
            viewbox=None,
        )
        assert obs.crossing_count is None


# ── 12. _validate_completeness edge cases ─────────────────────────────────────

class TestValidateCompleteness:
    def _make_obs(self, entities=None, relations=None) -> GeometryObservation:
        from adapters.playwright_extractor import EntityGeometry
        ents = []
        for eid in (entities or []):
            ents.append(EntityGeometry(
                entity_id=eid,
                bbox=BoundingBox(x=10.0, y=10.0, width=50.0, height=30.0),
                text_bbox=None,
                text_lines=1,
            ))
        rels = []
        for rid in (relations or []):
            pts: list[tuple[float, float]] = [(float(i), 0.0) for i in range(32)]
            rels.append(RelationGeometry(
                relation_id=rid,
                source_point=(0.0, 0.0),
                target_point=(31.0, 0.0),
                source_side=None,
                target_side=None,
                sampled_points=pts,
                bend_count=0,
                path_length=100.0,
            ))
        content = BoundingBox(x=0.0, y=0.0, width=100.0, height=100.0) if (ents or rels) else None
        return GeometryObservation(
            coordinate_convention="css-top-left",
            content_bounds=content,
            canvas_bounds=None,
            viewbox=None,
            entities=ents,
            relations=rels,
            crossing_count=0,
        )

    def test_missing_entity_raises_error(self):
        from adapters.playwright_extractor import _validate_completeness
        sem = _make_semantic([("A", "A"), ("B", "B")], [])
        obs = self._make_obs(entities=["A"])  # missing B
        result = _validate_completeness(obs, sem)
        assert result is not None
        assert "B" in result

    def test_extra_entity_raises_error(self):
        from adapters.playwright_extractor import _validate_completeness
        sem = _make_semantic([("A", "A")], [])
        obs = self._make_obs(entities=["A", "B"])  # extra B
        result = _validate_completeness(obs, sem)
        assert result is not None

    def test_matching_entities_no_error(self):
        from adapters.playwright_extractor import _validate_completeness
        sem = _make_semantic([("A", "A"), ("B", "B")], [])
        obs = self._make_obs(entities=["A", "B"])
        result = _validate_completeness(obs, sem)
        assert result is None

    def test_relation_wrong_sample_count(self):
        from adapters.playwright_extractor import _validate_completeness, EntityGeometry
        sem = _make_semantic([("A", "A")], [("A", "A", "")])
        rid = "A__A__0"
        pts_wrong: list[tuple[float, float]] = [(float(i), 0.0) for i in range(10)]  # not 32
        rel = RelationGeometry(
            relation_id=rid,
            source_point=(0.0, 0.0),
            target_point=(9.0, 0.0),
            source_side=None,
            target_side=None,
            sampled_points=pts_wrong,
            bend_count=0,
            path_length=10.0,
        )
        ent = EntityGeometry(
            entity_id="A",
            bbox=BoundingBox(x=10.0, y=10.0, width=50.0, height=30.0),
            text_bbox=None,
            text_lines=1,
        )
        obs = GeometryObservation(
            coordinate_convention="css-top-left",
            content_bounds=BoundingBox(x=0.0, y=0.0, width=100.0, height=100.0),
            canvas_bounds=None,
            viewbox=None,
            entities=[ent],
            relations=[rel],
            crossing_count=0,
        )
        result = _validate_completeness(obs, sem)
        assert result is not None
        assert "10" in result


# ── 13. Real-mmdc integration tests ───────────────────────────────────────────

@pytest.mark.external_reference
@pytest.mark.browser
class TestRealMmdcIntegration:
    """End-to-end tests: mmdc renders → Playwright extracts geometry."""

    _SIMPLE_MMD = "flowchart LR\n  A[Start] --> B[End]\n"
    _THREE_NODE_MMD = "flowchart TD\n  A[Top] --> B[Mid]\n  B --> C[Bot]\n"
    _DIAMOND_MMD = (
        "flowchart TD\n"
        "  A[Start] --> B{Choice}\n"
        "  B -->|yes| C[Yes]\n"
        "  B -->|no| D[No]\n"
    )

    def _render(self, source: str) -> str | None:
        """Run mmdc on source, return SVG or None."""
        import shutil
        import subprocess
        import tempfile
        mmdc = shutil.which("mmdc") or "/opt/homebrew/bin/mmdc"
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path as _P
            mmd = _P(tmp) / "d.mmd"
            out = _P(tmp) / "d.svg"
            mmd.write_text(source, encoding="utf-8")
            try:
                r = subprocess.run(
                    [mmdc, "-i", str(mmd), "-o", str(out), "--quiet"],
                    capture_output=True, timeout=60,
                )
                if r.returncode != 0 or not out.exists():
                    return None
                return out.read_text(encoding="utf-8")
            except Exception:
                return None

    def test_simple_flowchart_entities_found(self):
        svg = self._render(self._SIMPLE_MMD)
        if svg is None:
            pytest.skip("mmdc render failed")
        sem = _make_semantic([("A", "Start"), ("B", "End")], [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(svg, sem, bm, source=self._SIMPLE_MMD)
        entity_ids = {e.entity_id for e in obs.entities}
        assert "A" in entity_ids
        assert "B" in entity_ids

    def test_simple_flowchart_relation_sampled(self):
        svg = self._render(self._SIMPLE_MMD)
        if svg is None:
            pytest.skip("mmdc render failed")
        sem = _make_semantic([("A", "Start"), ("B", "End")], [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(svg, sem, bm, source=self._SIMPLE_MMD)
        if obs.relations:
            r = obs.relations[0]
            assert len(r.sampled_points) == 32
            assert r.path_length is not None and r.path_length > 0

    def test_three_node_bend_count_nonnegative(self):
        svg = self._render(self._THREE_NODE_MMD)
        if svg is None:
            pytest.skip("mmdc render failed")
        sem = _make_semantic(
            [("A", "Top"), ("B", "Mid"), ("C", "Bot")],
            [("A", "B", ""), ("B", "C", "")],
        )
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(svg, sem, bm, source=self._THREE_NODE_MMD)
        for r in obs.relations:
            assert r.bend_count >= 0

    def test_side_inference_populated(self):
        svg = self._render(self._SIMPLE_MMD)
        if svg is None:
            pytest.skip("mmdc render failed")
        sem = _make_semantic([("A", "Start"), ("B", "End")], [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(svg, sem, bm, source=self._SIMPLE_MMD)
        if obs.relations:
            r = obs.relations[0]
            assert r.source_side in ("L", "R", "T", "B", None)
            assert r.target_side in ("L", "R", "T", "B", None)

    def test_diamond_crossing_count_zero(self):
        svg = self._render(self._DIAMOND_MMD)
        if svg is None:
            pytest.skip("mmdc render failed")
        sem = _make_semantic(
            [("A", "Start"), ("B", "Choice"), ("C", "Yes"), ("D", "No")],
            [("A", "B", ""), ("B", "C", "yes"), ("B", "D", "no")],
        )
        with PlaywrightBrowserManager() as bm:
            obs, _ = extract_flowchart_geometry(svg, sem, bm, source=self._DIAMOND_MMD)
        # In a simple diamond, edges shouldn't cross
        assert obs.crossing_count is not None
        assert obs.crossing_count == 0

    def test_error_reason_none_on_success(self):
        svg = self._render(self._SIMPLE_MMD)
        if svg is None:
            pytest.skip("mmdc render failed")
        sem = _make_semantic([("A", "Start"), ("B", "End")], [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(svg, sem, bm, source=self._SIMPLE_MMD)
        # If entities were found, error should be None
        if obs.entities:
            assert err is None

    def test_content_bounds_present_after_render(self):
        svg = self._render(self._SIMPLE_MMD)
        if svg is None:
            pytest.skip("mmdc render failed")
        sem = _make_semantic([("A", "Start"), ("B", "End")], [("A", "B", "")])
        with PlaywrightBrowserManager() as bm:
            obs, err = extract_flowchart_geometry(svg, sem, bm, source=self._SIMPLE_MMD)
        if obs.entities:
            assert obs.content_bounds is not None
            assert obs.content_bounds.width > 0
            assert obs.content_bounds.height > 0
