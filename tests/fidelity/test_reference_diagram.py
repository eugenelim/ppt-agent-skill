"""Unit tests for ReferenceDiagram types and extractor.

All tests here run WITHOUT a browser — they use synthetic SVG input.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "tools"))

from mermaid_fidelity.models import (
    BoundingBox,
    CardinalityEnd,
    ComparisonStatus,
    ExtractorGap,
    ReferenceEdge,
    ReferenceGroup,
    ReferenceLabel,
    ReferenceMarker,
    ReferenceDiagram,
    ReferenceNode,
    ReferenceProvenance,
    StateSymbolKind,
)
from mermaid_fidelity.capture.extractor import (
    extract_diagram,
    normalize_coordinates,
    _parse_transform_string,
    _Transform,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_provenance(**kwargs) -> ReferenceProvenance:
    defaults = dict(
        mermaid_version="11.15.0",
        mmdc_version="11.15.0",
        node_version="18.0.0",
        playwright_version="1.40.0",
        chromium_version="120.0",
        platform="Linux",
        font_families=["arial"],
        font_fingerprint="abc123",
        fixture_source_hash="def456",
        render_config_hash="",
    )
    defaults.update(kwargs)
    return ReferenceProvenance(**defaults)


def _make_svg(
    *,
    width: str = "400",
    height: str = "200",
    viewbox: str = "0 0 400 200",
    body: str = "",
) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="{viewbox}">'
        f'{body}'
        f'</svg>'
    )


# ── Task 1: ReferenceDiagram field tests ──────────────────────────────────────

class TestCardinalityEnd:
    def test_minimum_zero(self):
        ce = CardinalityEnd(minimum="ZERO", maximum="ONE")
        assert ce.minimum == "ZERO"

    def test_minimum_one(self):
        ce = CardinalityEnd(minimum="ONE", maximum="MANY")
        assert ce.minimum == "ONE"

    def test_maximum_one(self):
        ce = CardinalityEnd(minimum="ZERO", maximum="ONE")
        assert ce.maximum == "ONE"

    def test_maximum_many(self):
        ce = CardinalityEnd(minimum="ZERO", maximum="MANY")
        assert ce.maximum == "MANY"


class TestExtractorGap:
    def test_fields(self):
        gap = ExtractorGap(field="test_field", reason="not found")
        assert gap.field == "test_field"
        assert gap.reason == "not found"


class TestReferenceDiagramFields:
    def test_construction_with_all_required_fields(self):
        prov = _make_provenance()
        diag = ReferenceDiagram(
            fixture_stem="flowchart-basic",
            diagram_type="flowchart",
            canvas_bounds=BoundingBox(x=0, y=0, width=400, height=200),
            view_box="0 0 400 200",
            provenance=prov,
        )
        assert diag.fixture_stem == "flowchart-basic"
        assert diag.diagram_type == "flowchart"
        assert diag.canvas_bounds.width == 400
        assert diag.view_box == "0 0 400 200"
        assert diag.nodes == []
        assert diag.groups == []
        assert diag.edges == []
        assert diag.labels == []
        assert diag.markers == []
        assert diag.gaps == []
        assert diag.status == ComparisonStatus.PASS

    def test_status_becomes_extractor_gap_when_gaps_present(self):
        prov = _make_provenance()
        diag = ReferenceDiagram(
            fixture_stem="test",
            diagram_type="flowchart",
            canvas_bounds=BoundingBox(x=0, y=0, width=100, height=100),
            view_box=None,
            provenance=prov,
            gaps=[ExtractorGap(field="some_field", reason="not found")],
        )
        assert diag.status == ComparisonStatus.EXTRACTOR_GAP

    def test_extractor_gap_in_diagram(self):
        prov = _make_provenance()
        gap = ExtractorGap(field="state_symbol", reason="ambiguous element")
        diag = ReferenceDiagram(
            fixture_stem="state-basic",
            diagram_type="state",
            canvas_bounds=BoundingBox(x=0, y=0, width=200, height=150),
            view_box=None,
            provenance=prov,
            gaps=[gap],
        )
        assert len(diag.gaps) == 1
        assert diag.gaps[0].field == "state_symbol"
        assert diag.status == ComparisonStatus.EXTRACTOR_GAP


class TestReferenceNode:
    def test_construction(self):
        node = ReferenceNode(
            id="A",
            label="Node A",
            shape="rect",
            kind="node",
            bbox=BoundingBox(x=10, y=20, width=100, height=50),
        )
        assert node.id == "A"
        assert node.label == "Node A"
        assert node.shape == "rect"
        assert node.bbox.x == 10

    def test_defaults(self):
        node = ReferenceNode(
            id="B", label="B", shape=None, kind=None,
            bbox=BoundingBox(x=0, y=0, width=50, height=50),
        )
        assert node.transform_chain == []
        assert node.parent_group_id is None
        assert node.attributes == {}


class TestReferenceMarker:
    def test_hollow_triangle(self):
        m = ReferenceMarker(
            marker_id="extensionEnd",
            kind="hollow_triangle",
            edge_id="e1",
            end="end",
        )
        assert m.kind == "hollow_triangle"

    def test_filled_diamond(self):
        m = ReferenceMarker(
            marker_id="compositionStart",
            kind="filled_diamond",
            edge_id="e2",
            end="start",
        )
        assert m.kind == "filled_diamond"


class TestStateSymbolKind:
    def test_enum_values(self):
        assert StateSymbolKind.INITIAL == "initial"
        assert StateSymbolKind.FINAL == "final"
        assert StateSymbolKind.SIMPLE == "simple"
        assert StateSymbolKind.COMPOSITE == "composite"
        assert StateSymbolKind.COMPOSITE_BOUNDARY == "composite_boundary"


# ── Task 5: Coordinate normalization tests ────────────────────────────────────

class TestCoordinateNormalization:
    def test_translate_transform(self):
        raw = BoundingBox(x=0, y=0, width=100, height=50)
        result = normalize_coordinates(raw, "translate(10, 20)")
        assert result.x == pytest.approx(10.0)
        assert result.y == pytest.approx(20.0)
        assert result.width == pytest.approx(100.0)
        assert result.height == pytest.approx(50.0)

    def test_scale_transform(self):
        raw = BoundingBox(x=5, y=5, width=100, height=50)
        result = normalize_coordinates(raw, "scale(2, 2)")
        assert result.x == pytest.approx(10.0)
        assert result.y == pytest.approx(10.0)
        assert result.width == pytest.approx(200.0)
        assert result.height == pytest.approx(100.0)

    def test_identity_transform(self):
        raw = BoundingBox(x=15, y=25, width=80, height=40)
        result = normalize_coordinates(raw, "")
        assert result.x == pytest.approx(15.0)
        assert result.y == pytest.approx(25.0)

    def test_viewbox_scaling(self):
        raw = BoundingBox(x=0, y=0, width=100, height=50)
        result = normalize_coordinates(raw, "", viewbox_scale=(2.0, 2.0))
        assert result.x == pytest.approx(0.0)
        assert result.y == pytest.approx(0.0)
        assert result.width == pytest.approx(200.0)
        assert result.height == pytest.approx(100.0)

    def test_translate_then_viewbox_scale(self):
        raw = BoundingBox(x=0, y=0, width=100, height=50)
        result = normalize_coordinates(raw, "translate(10, 20)", viewbox_scale=(2.0, 2.0))
        assert result.x == pytest.approx(20.0)  # 10 * 2
        assert result.y == pytest.approx(40.0)  # 20 * 2

    def test_deterministic_normalization(self):
        raw = BoundingBox(x=5, y=10, width=200, height=100)
        r1 = normalize_coordinates(raw, "translate(5, 5)", viewbox_scale=(1.5, 1.5))
        r2 = normalize_coordinates(raw, "translate(5, 5)", viewbox_scale=(1.5, 1.5))
        assert r1.x == r2.x
        assert r1.y == r2.y
        assert r1.width == r2.width
        assert r1.height == r2.height


class TestTransformChainComposition:
    def test_identity(self):
        t = _parse_transform_string("")
        x, y = t.apply(10, 20)
        assert x == pytest.approx(10.0)
        assert y == pytest.approx(20.0)

    def test_translate(self):
        t = _parse_transform_string("translate(5, 10)")
        x, y = t.apply(0, 0)
        assert x == pytest.approx(5.0)
        assert y == pytest.approx(10.0)

    def test_scale(self):
        t = _parse_transform_string("scale(3)")
        x, y = t.apply(2, 4)
        assert x == pytest.approx(6.0)
        assert y == pytest.approx(12.0)

    def test_nested_transforms(self):
        """Three levels of translate nesting: compose manually."""
        t1 = _parse_transform_string("translate(10, 0)")
        t2 = _parse_transform_string("translate(0, 20)")
        t3 = _parse_transform_string("translate(5, 5)")
        composed = _Transform.identity().then(t1).then(t2).then(t3)
        x, y = composed.apply(0, 0)
        assert x == pytest.approx(15.0)
        assert y == pytest.approx(25.0)


# ── Task 4: DOM/SVG extractor unit tests ──────────────────────────────────────

class TestNodeExtraction:
    def test_node_extraction_basic(self):
        svg = _make_svg(body='''
            <g id="nodeA" class="node">
              <rect x="10" y="20" width="100" height="50"/>
              <text>Node A</text>
            </g>
            <g id="nodeB" class="node">
              <rect x="150" y="20" width="100" height="50"/>
              <text>Node B</text>
            </g>
        ''')
        diag = extract_diagram(svg, "test-flow", "flowchart")
        assert len(diag.nodes) == 2
        ids = {n.id for n in diag.nodes}
        assert "nodeA" in ids
        assert "nodeB" in ids

    def test_node_bounding_box(self):
        svg = _make_svg(body='''
            <g id="nodeX" class="node">
              <rect x="10" y="20" width="80" height="40"/>
              <text>X</text>
            </g>
        ''')
        diag = extract_diagram(svg, "test", "flowchart")
        assert len(diag.nodes) == 1
        bbox = diag.nodes[0].bbox
        assert bbox.x == pytest.approx(10.0)
        assert bbox.y == pytest.approx(20.0)
        assert bbox.width == pytest.approx(80.0)
        assert bbox.height == pytest.approx(40.0)

    def test_viewbox_scaling_applied_to_nodes(self):
        """viewBox="0 0 200 100" width="400" height="200" → scale=2"""
        svg = _make_svg(
            width="400", height="200", viewbox="0 0 200 100",
            body='''
            <g id="nodeY" class="node">
              <rect x="10" y="10" width="50" height="25"/>
              <text>Y</text>
            </g>
            ''',
        )
        diag = extract_diagram(svg, "test", "flowchart")
        assert len(diag.nodes) == 1
        bbox = diag.nodes[0].bbox
        # Scale factor 2x applied
        assert bbox.x == pytest.approx(20.0)
        assert bbox.y == pytest.approx(20.0)
        assert bbox.width == pytest.approx(100.0)
        assert bbox.height == pytest.approx(50.0)


class TestEdgeExtractionParallel:
    def test_parallel_edges_distinct_ids(self):
        """Two edges sharing (src, dst) must get distinct normalized IDs."""
        svg = _make_svg(body='''
            <path class="flowchart-link" d="M10,10 L100,100"/>
            <path class="flowchart-link" d="M10,10 C50,50 80,80 100,100"/>
        ''')
        diag = extract_diagram(svg, "test", "flowchart")
        assert len(diag.edges) == 2
        ids = [e.id for e in diag.edges]
        assert len(set(ids)) == 2, f"Expected distinct IDs, got: {ids}"

    def test_edge_has_path_data(self):
        svg = _make_svg(body='''
            <path class="edge" d="M5,5 L50,50"/>
        ''')
        diag = extract_diagram(svg, "test", "flowchart")
        assert len(diag.edges) == 1
        assert diag.edges[0].path_data == "M5,5 L50,50"


class TestClassMarkerResolution:
    def test_hollow_triangle_from_id(self):
        svg = _make_svg(body='''
            <defs>
              <marker id="extensionEnd" class="marker-extension">
                <polygon points="0,0 10,5 0,10"/>
              </marker>
            </defs>
            <path class="edge relation" d="M0,0 L50,50"
                  marker-end="url(#extensionEnd)"/>
        ''')
        diag = extract_diagram(svg, "test", "class")
        edges_with_end = [e for e in diag.edges if e.marker_end is not None]
        assert len(edges_with_end) >= 1
        assert edges_with_end[0].marker_end.kind == "hollow_triangle"

    def test_filled_diamond_from_id(self):
        svg = _make_svg(body='''
            <defs>
              <marker id="compositionStart" class="marker-composition">
                <polygon points="0,5 5,0 10,5 5,10"/>
              </marker>
            </defs>
            <path class="edge relation" d="M0,0 L50,50"
                  marker-start="url(#compositionStart)"/>
        ''')
        diag = extract_diagram(svg, "test", "class")
        edges_with_start = [e for e in diag.edges if e.marker_start is not None]
        assert len(edges_with_start) >= 1
        assert edges_with_start[0].marker_start.kind == "filled_diamond"


class TestErCardinalityParsing:
    def test_zero_or_one(self):
        from mermaid_fidelity.capture.extractor import _parse_cardinality
        ce = _parse_cardinality("0..1")
        assert ce is not None
        assert ce.minimum == "ZERO"
        assert ce.maximum == "ONE"

    def test_one_to_many(self):
        from mermaid_fidelity.capture.extractor import _parse_cardinality
        ce = _parse_cardinality("1..*")
        assert ce is not None
        assert ce.minimum == "ONE"
        assert ce.maximum == "MANY"

    def test_zero_to_many(self):
        from mermaid_fidelity.capture.extractor import _parse_cardinality
        ce = _parse_cardinality("0..*")
        assert ce is not None
        assert ce.minimum == "ZERO"
        assert ce.maximum == "MANY"

    def test_exactly_one(self):
        from mermaid_fidelity.capture.extractor import _parse_cardinality
        ce = _parse_cardinality("1")
        assert ce is not None
        assert ce.minimum == "ONE"
        assert ce.maximum == "ONE"

    def test_star_means_zero_to_many(self):
        from mermaid_fidelity.capture.extractor import _parse_cardinality
        ce = _parse_cardinality("*")
        assert ce is not None
        assert ce.minimum == "ZERO"
        assert ce.maximum == "MANY"

    def test_unknown_returns_none(self):
        from mermaid_fidelity.capture.extractor import _parse_cardinality
        ce = _parse_cardinality("???")
        assert ce is None


class TestStateSymbolClassification:
    """Tests for state diagram symbol classification (AC6)."""

    def test_initial_filled_circle(self):
        from mermaid_fidelity.capture.extractor import _classify_state_symbol, ET
        svg_text = _make_svg(body='<circle cx="10" cy="10" r="8" fill="black" class="start"/>')
        root = ET.fromstring(svg_text)
        tree = ET.ElementTree(root)
        ns = "http://www.w3.org/2000/svg"
        circle = root.find(f"{{{ns}}}circle")
        result = _classify_state_symbol(circle, tree)
        assert result == StateSymbolKind.INITIAL

    def test_final_end_class(self):
        from mermaid_fidelity.capture.extractor import _classify_state_symbol, ET
        svg_text = _make_svg(body='<circle cx="10" cy="10" r="8" class="end"/>')
        root = ET.fromstring(svg_text)
        tree = ET.ElementTree(root)
        ns = "http://www.w3.org/2000/svg"
        circle = root.find(f"{{{ns}}}circle")
        result = _classify_state_symbol(circle, tree)
        assert result == StateSymbolKind.FINAL

    def test_simple_rect(self):
        from mermaid_fidelity.capture.extractor import _classify_state_symbol, ET
        svg_text = _make_svg(body='<rect x="10" y="10" width="80" height="40" class="node-rect"/>')
        root = ET.fromstring(svg_text)
        tree = ET.ElementTree(root)
        ns = "http://www.w3.org/2000/svg"
        rect = root.find(f"{{{ns}}}rect")
        result = _classify_state_symbol(rect, tree)
        assert result == StateSymbolKind.SIMPLE

    def test_composite_cluster_rect(self):
        from mermaid_fidelity.capture.extractor import _classify_state_symbol, ET
        svg_text = _make_svg(body='<rect x="10" y="10" width="200" height="150" class="cluster-rect"/>')
        root = ET.fromstring(svg_text)
        tree = ET.ElementTree(root)
        ns = "http://www.w3.org/2000/svg"
        rect = root.find(f"{{{ns}}}rect")
        result = _classify_state_symbol(rect, tree)
        assert result == StateSymbolKind.COMPOSITE

    def test_composite_boundary_fork_bar(self):
        """Fork/join bar: wide and very short (aspect ratio > 5:1)."""
        from mermaid_fidelity.capture.extractor import _classify_state_symbol, ET
        svg_text = _make_svg(body='<rect x="10" y="10" width="200" height="5" fill="#000"/>')
        root = ET.fromstring(svg_text)
        tree = ET.ElementTree(root)
        ns = "http://www.w3.org/2000/svg"
        rect = root.find(f"{{{ns}}}rect")
        result = _classify_state_symbol(rect, tree)
        assert result == StateSymbolKind.COMPOSITE_BOUNDARY

    def test_state_symbol_extractor_gap(self):
        """AC9: when a symbol cannot be classified, the diagram has EXTRACTOR_GAP status."""
        prov = _make_provenance()
        diag = ReferenceDiagram(
            fixture_stem="state-ambiguous",
            diagram_type="state",
            canvas_bounds=BoundingBox(x=0, y=0, width=200, height=200),
            view_box=None,
            provenance=prov,
            gaps=[ExtractorGap(field="state_symbol", reason="ambiguous element")],
        )
        assert diag.status == ComparisonStatus.EXTRACTOR_GAP


# ── Task 7: Cache unit tests ───────────────────────────────────────────────────

class TestDiagramCache:
    def _make_diagram(self, stem: str = "test") -> ReferenceDiagram:
        prov = _make_provenance(fixture_source_hash=stem)
        return ReferenceDiagram(
            fixture_stem=stem,
            diagram_type="flowchart",
            canvas_bounds=BoundingBox(x=0, y=0, width=100, height=100),
            view_box=None,
            provenance=prov,
        )

    def test_cache_hit_returns_same_record(self, tmp_path):
        from mermaid_fidelity.capture.cache import DiagramCache
        cache = DiagramCache(tmp_path / "cache")
        diag = self._make_diagram("myflow")
        cache.put(diag, "hash1", "11.15.0", "chrome120", "font-fp")
        result = cache.get("hash1", "11.15.0", "chrome120", "font-fp")
        assert result is not None
        assert result.fixture_stem == "myflow"

    def test_cache_miss_returns_none(self, tmp_path):
        from mermaid_fidelity.capture.cache import DiagramCache
        cache = DiagramCache(tmp_path / "cache")
        result = cache.get("nonexistent", "11.15.0", "chrome120", "font-fp")
        assert result is None

    def test_cache_invalidates_on_source_hash_change(self, tmp_path):
        from mermaid_fidelity.capture.cache import DiagramCache
        cache = DiagramCache(tmp_path / "cache")
        diag = self._make_diagram("test")
        cache.put(diag, "hash-A", "11.15.0", "chrome120", "font-fp")
        # Different source hash → cache miss
        result = cache.get("hash-B", "11.15.0", "chrome120", "font-fp")
        assert result is None

    def test_cache_invalidates_on_version_change(self, tmp_path):
        from mermaid_fidelity.capture.cache import DiagramCache
        cache = DiagramCache(tmp_path / "cache")
        diag = self._make_diagram("test")
        cache.put(diag, "hash1", "11.15.0", "chrome120", "font-fp")
        # Different Mermaid version → cache miss
        result = cache.get("hash1", "11.0.0", "chrome120", "font-fp")
        assert result is None

    def test_cache_invalidates_on_font_fingerprint_change(self, tmp_path):
        from mermaid_fidelity.capture.cache import DiagramCache
        cache = DiagramCache(tmp_path / "cache")
        diag = self._make_diagram("test")
        cache.put(diag, "hash1", "11.15.0", "chrome120", "font-fp-A")
        result = cache.get("hash1", "11.15.0", "chrome120", "font-fp-B")
        assert result is None
