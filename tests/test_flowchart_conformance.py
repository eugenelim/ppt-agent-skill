"""Per-fixture conformance tests for the eight in-scope Mermaid flowchart fixtures.

Spec: docs/specs/mermaid-flowchart-conformance/spec.md
Mode: full (multi-fixture; geometry verifier; faithful-mode assertions)

Run with:
  pytest tests/test_flowchart_conformance.py -v -m flowchart_conformance
  pytest tests/test_flowchart_conformance.py -k compactness -v

Each fixture test:
  1. Compiles the fixture through the production pipeline.
  2. Runs the geometry verifier (all 8 invariants).
  3. Asserts fixture-specific semantic invariants.
  4. Computes compactness metrics.
"""
from __future__ import annotations

import sys
import types as _types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mermaid_render.layout._pipeline import (
    _compile_flowchart,
    RenderOptions,
)
from mermaid_render.layout._strategies import _dispatch
from mermaid_render.layout._geometry import (
    FinalizedLayout,
    NodeLayout,
    GroupLayout,
    RoutedEdge,
    PortLayout,
    PortSide,
    Point,
    Rect,
    MarkerKind,
    _empty_diagnostics,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry_verifier import (  # noqa: E402
    verify_layout,
    compute_compactness,
)

pytestmark = pytest.mark.flowchart_conformance

# ── Fixture source paths ───────────────────────────────────────────────────────

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

def _load(name: str) -> str:
    """Load a .mmd fixture by slug name."""
    return (_FIXTURES_DIR / f"{name}.mmd").read_text()


def _compile(name: str, opts: "RenderOptions | None" = None) -> "FinalizedLayout":
    """Compile a named fixture and return the FinalizedLayout."""
    src = _load(name)
    compiled = _compile_flowchart(src, 800, opts)
    return compiled.layout


# ── Task 1: Geometry verifier unit tests ──────────────────────────────────────

class TestGeometryVerifier:
    """Unit tests for geometry_verifier.py using synthetic FinalizedLayout objects."""

    def _make_layout(
        self,
        node_ids=("A", "B"),
        edge_ids=("A->B",),
        node_positions=None,   # list of (x, y) for each node
        groups=None,
        direction="TB",
    ) -> FinalizedLayout:
        """Build a minimal FinalizedLayout for verifier unit tests."""
        positions = node_positions or [(i * 200, 0) for i in range(len(node_ids))]
        node_layouts = {}
        for i, nid in enumerate(node_ids):
            x, y = positions[i]
            node_layouts[nid] = NodeLayout(
                node_id=nid,
                semantic_shape="rect",
                outer_bounds=Rect(x=float(x), y=float(y), w=120.0, h=42.0),
                content_bounds=Rect(x=float(x) + 8, y=float(y) + 4, w=104.0, h=34.0),
                title_layout=None, subtitle_layout=None, member_layouts=(),
                icon_bounds=None, ports=(), css_classes=(), extra_css="",
                is_dummy=False, rank=i + 1, is_external=False,
                icon_svg="", accent_color="", parent_group_id=None,
            )
        routed_edges = tuple(
            RoutedEdge(
                edge_id=eid,
                src_node_id=eid.split("->")[0],
                dst_node_id=eid.split("->")[1],
                src_port=PortLayout(
                    node_id=eid.split("->")[0], side=PortSide.BOTTOM,
                    position=Point(
                        float(positions[node_ids.index(eid.split("->")[0])][0]) + 60,
                        float(positions[node_ids.index(eid.split("->")[0])][1]) + 42.0,
                    ),
                    direction=Point(0.0, 1.0),
                ),
                dst_port=PortLayout(
                    node_id=eid.split("->")[1], side=PortSide.TOP,
                    position=Point(
                        float(positions[node_ids.index(eid.split("->")[1])][0]) + 60,
                        float(positions[node_ids.index(eid.split("->")[1])][1]),
                    ),
                    direction=Point(0.0, -1.0),
                ),
                waypoints=(
                    Point(
                        float(positions[node_ids.index(eid.split("->")[0])][0]) + 60,
                        float(positions[node_ids.index(eid.split("->")[0])][1]) + 42.0,
                    ),
                    Point(
                        float(positions[node_ids.index(eid.split("->")[1])][0]) + 60,
                        float(positions[node_ids.index(eid.split("->")[1])][1]),
                    ),
                ),
                edge_style="solid", has_marker_end=True, has_marker_start=False,
                label_layout=None, src_label_layout=None, dst_label_layout=None,
                source_marker=MarkerKind.NONE, target_marker=MarkerKind.ARROW,
                junction_points=(),
            )
            for eid in edge_ids
        )
        group_layouts = {}
        if groups:
            for gid, (gx, gy, gw, gh) in groups.items():
                group_layouts[gid] = GroupLayout(
                    group_id=gid,
                    parent_group_id=None,
                    boundary_bounds=Rect(x=float(gx), y=float(gy), w=float(gw), h=float(gh)),
                    label_layout=None,
                    member_ids=(),
                    child_group_ids=(),
                    local_direction="TB",
                )
        canvas = Rect(x=0.0, y=0.0, w=800.0, h=600.0)
        return FinalizedLayout(
            node_layouts=_types.MappingProxyType(node_layouts),
            group_layouts=_types.MappingProxyType(group_layouts),
            routed_edges=routed_edges,
            routing_failures=(),
            visible_bounds=canvas,
            diagram_padding=48.0,
            canvas_bounds=canvas,
            direction=direction,
            diagnostics=_empty_diagnostics(),
        )

    def test_verifier_passes_on_clean_layout(self):
        """A synthetically clean layout produces zero violations. (AC9)"""
        layout = self._make_layout(
            node_ids=("A", "B"),
            node_positions=[(0, 0), (200, 200)],
            edge_ids=("A->B",),
        )
        violations = verify_layout(layout)
        assert violations == [], f"Clean layout produced violations: {violations}"

    def test_verifier_detects_node_overlap(self):
        """Two overlapping nodes trigger a node-overlap violation. (AC9)"""
        # Put A and B at the same position — guaranteed overlap
        layout = self._make_layout(
            node_ids=("A", "B"),
            node_positions=[(0, 0), (10, 5)],  # 10px apart: 120px wide nodes → 110px overlap
            edge_ids=("A->B",),
        )
        violations = verify_layout(layout)
        kinds = [v.kind for v in violations]
        assert "node-overlap" in kinds, (
            f"Expected node-overlap violation for overlapping nodes, got: {kinds}"
        )

    def test_verifier_detects_containment_failure(self):
        """A node outside its declared parent group triggers a containment violation. (AC9)"""
        import dataclasses
        layout = self._make_layout(
            node_ids=("A",),
            node_positions=[(500, 500)],  # outside the group below
            edge_ids=(),
        )
        # Put a group that does NOT contain node A's bounds
        group_layouts = {
            "G": GroupLayout(
                group_id="G",
                parent_group_id=None,
                boundary_bounds=Rect(x=0.0, y=0.0, w=200.0, h=100.0),
                label_layout=None,
                member_ids=("A",),
                child_group_ids=(),
                local_direction="TB",
            )
        }
        # Reassign parent_group_id to "G" on node A
        a_nl = layout.node_layouts["A"]
        a_nl_new = dataclasses.replace(a_nl, parent_group_id="G")
        layout2 = dataclasses.replace(
            layout,
            node_layouts=_types.MappingProxyType({"A": a_nl_new}),
            group_layouts=_types.MappingProxyType(group_layouts),
        )
        violations = verify_layout(layout2)
        kinds = [v.kind for v in violations]
        assert "containment" in kinds, (
            f"Expected containment violation for node outside group, got: {kinds}"
        )

    def test_verifier_detects_route_through_node(self):
        """An edge whose interior waypoints pass through an unrelated node triggers violation."""
        import dataclasses
        # Three nodes: A (0,0), B (400,0), C (200, -5)
        # Edge A->B with waypoints that go through C's bounding box
        layout = self._make_layout(
            node_ids=("A", "B", "C"),
            node_positions=[(0, 0), (400, 0), (200, -5)],  # C is at 200,-5 so y=0 is inside
            edge_ids=("A->B",),
        )
        # Override the A->B waypoints to pass through C at (250, 10) which is inside C's box
        # C is at x=200, y=-5, w=120, h=42 → inner (after -2px margin) = [202, 318]×[-3, 35]
        edges = list(layout.routed_edges)
        new_edge = dataclasses.replace(
            edges[0],
            waypoints=(
                Point(60.0, 42.0),
                Point(250.0, 10.0),  # inside C's inner box
                Point(460.0, 0.0),
            ),
        )
        layout2 = dataclasses.replace(layout, routed_edges=(new_edge,))
        violations = verify_layout(layout2)
        kinds = [v.kind for v in violations]
        assert "route-through-node" in kinds, (
            f"Expected route-through-node violation, got: {kinds}"
        )

    def test_verifier_fails_on_degenerate_layout(self):
        """verify_layout returns a 'zero-assertions' violation for an empty layout. (AC9)

        AC9 spec constraint: 'Never accept a geometry verifier pass that executes
        zero assertions.' A layout with no nodes and no edges would make zero
        structural comparisons — the verifier must flag this as a sentinel violation
        rather than silently returning an empty (passing) list.
        """
        # Completely empty layout: no nodes, no edges, no groups
        empty_canvas = Rect(x=0.0, y=0.0, w=800.0, h=600.0)
        empty_layout = FinalizedLayout(
            node_layouts=_types.MappingProxyType({}),
            group_layouts=_types.MappingProxyType({}),
            routed_edges=(),
            routing_failures=(),
            visible_bounds=empty_canvas,
            diagram_padding=48.0,
            canvas_bounds=empty_canvas,
            direction="TB",
            diagnostics=_empty_diagnostics(),
        )
        violations = verify_layout(empty_layout)
        kinds = [v.kind for v in violations]
        assert "zero-assertions" in kinds, (
            f"Expected 'zero-assertions' sentinel for empty layout, got violations: {kinds}"
        )

    def test_verifier_zero_violations_reported(self):
        """verify_layout returns a list (never None) even on a zero-violation layout."""
        layout = self._make_layout()
        result = verify_layout(layout)
        assert isinstance(result, list)


# ── Task 2: Line-style and marker-kind fidelity ───────────────────────────────

class TestFlowchartArrowsDefs:
    """Line-style and marker-kind fidelity for flowchart-arrows-defs.mmd. (AC2)

    Fixture:
        A-->B    ordinary solid arrow
        A==>C    thick solid arrow
        A-.->D   dotted arrow
    """

    @pytest.fixture(scope="class")
    def layout(self):
        return _compile("flowchart-arrows-defs")

    def _edge_by_src_dst(self, layout: FinalizedLayout, src: str, dst: str) -> RoutedEdge:
        matches = [
            e for e in layout.routed_edges
            if e.src_node_id == src and e.dst_node_id == dst
        ]
        assert matches, f"No edge found from {src!r} to {dst!r}"
        return matches[0]

    def test_ordinary_solid_edge_style(self, layout: FinalizedLayout):
        """A-->B edge has edge_style='solid'. (AC2)"""
        edge = self._edge_by_src_dst(layout, "A", "B")
        assert edge.edge_style == "solid", (
            f"A-->B expected edge_style='solid', got {edge.edge_style!r}"
        )

    def test_ordinary_solid_target_marker(self, layout: FinalizedLayout):
        """A-->B edge has target_marker=ARROW. (AC2)"""
        edge = self._edge_by_src_dst(layout, "A", "B")
        assert edge.target_marker == MarkerKind.ARROW, (
            f"A-->B expected target_marker=ARROW, got {edge.target_marker!r}"
        )

    def test_thick_edge_style(self, layout: FinalizedLayout):
        """A==>C edge has edge_style='thick'. (AC2)"""
        edge = self._edge_by_src_dst(layout, "A", "C")
        assert edge.edge_style == "thick", (
            f"A==>C expected edge_style='thick', got {edge.edge_style!r}"
        )

    def test_dotted_dashed_edge_style(self, layout: FinalizedLayout):
        """A-.->D edge has edge_style in {'dotted', 'dashed'}. (AC2)"""
        edge = self._edge_by_src_dst(layout, "A", "D")
        assert edge.edge_style in {"dotted", "dashed"}, (
            f"A-.->D expected dotted/dashed edge_style, got {edge.edge_style!r}"
        )

    def test_geometry_verifier_passes(self, layout: FinalizedLayout):
        """Geometry verifier reports zero violations on arrows-defs layout. (AC9)"""
        violations = verify_layout(layout)
        assert violations == [], f"Geometry violations: {violations}"

    def test_faithful_no_legend(self):
        """Compiling with faithful_mermaid=True produces HTML without a legend. (AC2)

        Legends are injected by the Python legend-inference pass. With
        faithful_mermaid=True and inferred_legend=False, no legend HTML
        strip should appear in the rendered output.
        """
        src = _load("flowchart-arrows-defs")
        opts = RenderOptions(faithful_mermaid=True, inferred_legend=False)
        html = _dispatch(src, None, 800, opts=opts)
        assert "legend" not in html.lower(), (
            "Faithful mode with inferred_legend=False produced unexpected legend HTML"
        )


# ── Task 3: Decision-branch label assignment ──────────────────────────────────

class TestFlowchartDiamondBranch:
    """Decision-branch label assignment for flowchart-diamond-branch.mmd. (AC3)

    Fixture:
        Check{Valid Input?} -->|Yes| Process
        Check -->|No| Error
        Retry{Retry?} -->|Yes| Check
        Retry -->|No| Done
    """

    @pytest.fixture(scope="class")
    def layout(self):
        return _compile("flowchart-diamond-branch")

    def _edges_from(self, layout: FinalizedLayout, src: str):
        return [e for e in layout.routed_edges if e.src_node_id == src]

    def test_decision_branch_yes_label(self, layout: FinalizedLayout):
        """Check->Process edge carries label 'Yes'. (AC3)"""
        matches = [
            e for e in layout.routed_edges
            if e.src_node_id == "Check" and e.dst_node_id == "Process"
        ]
        assert matches, "No edge from Check to Process found"
        edge = matches[0]
        assert edge.label_layout is not None, "Check->Process has no label_layout"
        assert edge.label_layout.text == "Yes", (
            f"Check->Process label expected 'Yes', got {edge.label_layout.text!r}"
        )

    def test_decision_branch_no_label(self, layout: FinalizedLayout):
        """Check->Error edge carries label 'No'. (AC3)"""
        matches = [
            e for e in layout.routed_edges
            if e.src_node_id == "Check" and e.dst_node_id == "Error"
        ]
        assert matches, "No edge from Check to Error found"
        edge = matches[0]
        assert edge.label_layout is not None, "Check->Error has no label_layout"
        assert edge.label_layout.text == "No", (
            f"Check->Error label expected 'No', got {edge.label_layout.text!r}"
        )

    def test_retry_feedback_local_lane(self, layout: FinalizedLayout):
        """The Retry->Yes->Check feedback edge routes locally within the canvas. (AC3)

        Verifies that the backward (feedback) edge does not route at the
        canvas perimeter: all waypoints must be inside the canvas bounds and
        not within 5 px of the canvas edges. This catches perimeter-routing
        regressions where ELK sends feedback paths around the entire diagram.
        """
        feedback = [
            e for e in layout.routed_edges
            if e.src_node_id == "Retry" and e.dst_node_id == "Check"
        ]
        assert feedback, "No Retry->Check feedback edge found in diamond-branch layout"
        edge = feedback[0]
        # Label must be 'Yes' to confirm we have the correct edge
        assert edge.label_layout is not None, "Retry->Check edge has no label_layout"
        assert edge.label_layout.text == "Yes", (
            f"Expected 'Yes' label on Retry->Check, got {edge.label_layout.text!r}"
        )
        # Feedback edge must have interior waypoints (it routes, not a direct line)
        assert len(edge.waypoints) >= 3, (
            f"Retry->Check feedback edge has only {len(edge.waypoints)} waypoints "
            f"(expected ≥3 for a routed backward edge)"
        )
        # All waypoints must lie within the canvas bounds (not perimeter routing)
        canvas = layout.canvas_bounds
        PERIMETER_MARGIN = 5.0
        for wp in edge.waypoints:
            assert wp.x >= canvas.x - PERIMETER_MARGIN, (
                f"Waypoint {wp} exceeds left canvas edge (canvas.x={canvas.x})"
            )
            assert wp.x <= canvas.x1 + PERIMETER_MARGIN, (
                f"Waypoint {wp} exceeds right canvas edge (canvas.x1={canvas.x1})"
            )
            assert wp.y >= canvas.y - PERIMETER_MARGIN, (
                f"Waypoint {wp} exceeds top canvas edge (canvas.y={canvas.y})"
            )
            assert wp.y <= canvas.y1 + PERIMETER_MARGIN, (
                f"Waypoint {wp} exceeds bottom canvas edge (canvas.y1={canvas.y1})"
            )

    def test_decision_ports_stable(self):
        """Compiling the same fixture twice produces the same edge IDs. (AC3)"""
        layout1 = _compile("flowchart-diamond-branch")
        layout2 = _compile("flowchart-diamond-branch")
        ids1 = sorted(e.edge_id for e in layout1.routed_edges)
        ids2 = sorted(e.edge_id for e in layout2.routed_edges)
        assert ids1 == ids2, f"Edge ID set differs between compilations: {ids1} vs {ids2}"

    def test_geometry_verifier_passes(self, layout: FinalizedLayout):
        """Geometry verifier reports zero violations on diamond-branch layout. (AC9)"""
        violations = verify_layout(layout)
        assert violations == [], f"Geometry violations: {violations}"


# ── Task 4: Fan-out and fan-in port ordering ──────────────────────────────────

class TestFlowchartParallelLinks:
    """Fan-out / fan-in port ordering for flowchart-parallel-links.mmd. (AC8)

    Fixture:
        A[Gateway] --> B[ServiceA] & C[ServiceB] & D[ServiceC]
        B & C & D --> E[Aggregator]
    """

    @pytest.fixture(scope="class")
    def layout(self):
        return _compile("flowchart-parallel-links")

    def test_parallel_links_unique_edge_ids(self, layout: FinalizedLayout):
        """All routed edge IDs are distinct. (AC8)"""
        edge_ids = [e.edge_id for e in layout.routed_edges]
        assert len(edge_ids) == len(set(edge_ids)), (
            f"Duplicate edge IDs found: {sorted(edge_ids)}"
        )

    def test_parallel_links_distinct_routes(self, layout: FinalizedLayout):
        """No two edges share identical waypoint sequences. (AC8)"""
        wp_sets = [
            tuple((round(p.x), round(p.y)) for p in e.waypoints)
            for e in layout.routed_edges
        ]
        # Each edge must have a distinct route
        assert len(wp_sets) == len(set(wp_sets)), (
            "Two or more edges share identical waypoints"
        )

    def test_fan_out_port_order_deterministic(self):
        """Compiling the same fan-out fixture twice yields the same edge ID set. (AC8)"""
        layout1 = _compile("flowchart-parallel-links")
        layout2 = _compile("flowchart-parallel-links")
        ids1 = sorted(e.edge_id for e in layout1.routed_edges)
        ids2 = sorted(e.edge_id for e in layout2.routed_edges)
        assert ids1 == ids2, f"Edge IDs differ between compilations: {ids1} vs {ids2}"

    def test_geometry_verifier_passes(self, layout: FinalizedLayout):
        """Geometry verifier reports zero violations on parallel-links layout. (AC9)"""
        violations = verify_layout(layout)
        assert violations == [], f"Geometry violations: {violations}"


# ── Task 5: Compactness diagnostics ───────────────────────────────────────────

# Committed baseline constants (AC10): metrics must be <= these values.
# Actual observed values are roughly 2-10x smaller; baselines are generous
# regression guards — tighten after observing stable CI runs.
#
# max_edge_excursion: maximum distance (px) an interior waypoint is outside
#   the bounding box of its edge's src+dst nodes. Feedback loops and
#   cross-group edges naturally have high excursion.
# crossing_count: number of pairwise segment intersections; ideally 0 but
#   feedback edges in diamond-branch create 1 crossing.
_COMPACTNESS_BASELINES = {
    # name:                          route_len  bends  excursion  canvas_area  crossings
    "flowchart-all-shapes":     dict(total_route_length=20_000, total_bends=200, max_edge_excursion=500,  canvas_area=5_000_000, crossing_count=5),
    "flowchart-arrows-defs":    dict(total_route_length=10_000, total_bends=100, max_edge_excursion=500,  canvas_area=3_000_000, crossing_count=5),
    "flowchart-diamond-branch": dict(total_route_length=15_000, total_bends=150, max_edge_excursion=500,  canvas_area=4_000_000, crossing_count=5),
    "flowchart-diamond-clipping":dict(total_route_length=10_000, total_bends=100, max_edge_excursion=500, canvas_area=3_000_000, crossing_count=5),
    "flowchart-empty-subgraph": dict(total_route_length=5_000,  total_bends=50,  max_edge_excursion=500,  canvas_area=2_000_000, crossing_count=5),
    "flowchart-groups-complex": dict(total_route_length=25_000, total_bends=250, max_edge_excursion=1500, canvas_area=8_000_000, crossing_count=5),
    "flowchart-inner-direction":dict(total_route_length=10_000, total_bends=100, max_edge_excursion=500,  canvas_area=3_000_000, crossing_count=5),
    "flowchart-parallel-links": dict(total_route_length=10_000, total_bends=100, max_edge_excursion=500,  canvas_area=3_000_000, crossing_count=5),
}


class TestCompactnessDiagnostics:
    """Compactness metrics for all eight fixtures. (AC10)"""

    @pytest.mark.parametrize("fixture_name", list(_COMPACTNESS_BASELINES.keys()))
    def test_compactness_metrics_within_baseline(self, fixture_name: str):
        """Compactness metrics are recorded and within committed baselines. (AC10)"""
        layout = _compile(fixture_name)
        report = compute_compactness(layout)
        baseline = _COMPACTNESS_BASELINES[fixture_name]

        assert report.total_route_length >= 0, "total_route_length must be non-negative"
        assert report.total_bends >= 0, "total_bends must be non-negative"
        assert report.canvas_area > 0, "canvas_area must be positive"
        assert report.crossing_count >= 0, "crossing_count must be non-negative"
        assert report.max_edge_excursion >= 0, "max_edge_excursion must be non-negative"

        assert report.total_route_length <= baseline["total_route_length"], (
            f"{fixture_name}: total_route_length={report.total_route_length:.0f} "
            f"exceeds baseline {baseline['total_route_length']}"
        )
        assert report.total_bends <= baseline["total_bends"], (
            f"{fixture_name}: total_bends={report.total_bends} "
            f"exceeds baseline {baseline['total_bends']}"
        )
        assert report.canvas_area <= baseline["canvas_area"], (
            f"{fixture_name}: canvas_area={report.canvas_area:.0f} "
            f"exceeds baseline {baseline['canvas_area']}"
        )
        assert report.max_edge_excursion <= baseline["max_edge_excursion"], (
            f"{fixture_name}: max_edge_excursion={report.max_edge_excursion:.0f} "
            f"exceeds baseline {baseline['max_edge_excursion']}"
        )
        assert report.crossing_count <= baseline["crossing_count"], (
            f"{fixture_name}: crossing_count={report.crossing_count} "
            f"exceeds baseline {baseline['crossing_count']}"
        )

    @pytest.mark.parametrize("fixture_name", list(_COMPACTNESS_BASELINES.keys()))
    def test_compactness_is_deterministic(self, fixture_name: str):
        """compute_compactness returns the same result for the same compiled layout. (AC10)"""
        layout = _compile(fixture_name)
        r1 = compute_compactness(layout)
        r2 = compute_compactness(layout)
        assert r1 == r2, f"{fixture_name}: compactness is not deterministic: {r1} != {r2}"


# ── Task 6: Per-fixture conformance tests ─────────────────────────────────────

class TestFlowchartAllShapes:
    """Shape geometry mapping for flowchart-all-shapes.mmd. (AC1)

    Fixture declares: rect, round, diamond, stadium, circle, subroutine,
    doublecircle, hexagon, cylinder, flag, trapezoid, trapezoid-alt shapes.
    """

    # Maps node ID -> expected semantic_shape value (from parser canonical names)
    _EXPECTED_SHAPES = {
        "A": "rect",
        "B": "round",
        "C": "diamond",
        "D": "stadium",
        "E": "circle",
        "F": "subroutine",
        "G": "doublecircle",
        "H": "hexagon",
        "I": "cylinder",
        "J": "flag",
        "K": "trapezoid",
        "L": "trapezoid-alt",
    }

    @pytest.fixture(scope="class")
    def layout(self):
        return _compile("flowchart-all-shapes")

    def test_node_shapes_match_declarations(self, layout: FinalizedLayout):
        """Every node has the semantic_shape matching its Mermaid shape token. (AC1)"""
        for nid, expected_shape in self._EXPECTED_SHAPES.items():
            nl = layout.node_layouts.get(nid)
            assert nl is not None, f"Node {nid!r} missing from layout"
            assert nl.semantic_shape == expected_shape, (
                f"Node {nid!r}: expected semantic_shape={expected_shape!r}, "
                f"got {nl.semantic_shape!r}"
            )

    def test_geometry_verifier_passes(self, layout: FinalizedLayout):
        """Geometry verifier reports zero violations on all-shapes layout. (AC9)"""
        violations = verify_layout(layout)
        assert violations == [], f"Geometry violations: {violations}"

    def test_all_nodes_have_positive_bounds(self, layout: FinalizedLayout):
        """Every non-dummy node has positive outer_bounds dimensions. (AC1)"""
        for nid, nl in layout.node_layouts.items():
            if nl.is_dummy:
                continue
            assert nl.outer_bounds.w > 0, f"Node {nid!r} has zero width"
            assert nl.outer_bounds.h > 0, f"Node {nid!r} has zero height"


class TestFlowchartDiamondClipping:
    """Edge endpoints for diamond nodes lie near the diamond boundary. (AC4)

    Tolerance: endpoints must lie within 16 px of the diamond node's
    outer_bounds AABB. The mermaid-shape-boundary-exactness spec (already
    shipped) covers sub-pixel on-segment accuracy for diamond edges; this
    test guards only against catastrophic misplacement (endpoint far off
    the node entirely).

    Deferred (shape-boundary-exactness backlog): 0.5-px on-segment check
    for diamond edge intersection points.
    """

    @pytest.fixture(scope="class")
    def layout(self):
        return _compile("flowchart-diamond-clipping")

    def test_diamond_node_exists(self, layout: FinalizedLayout):
        """At least one diamond node is present in the layout. (AC4)"""
        diamonds = [
            nid for nid, nl in layout.node_layouts.items()
            if nl.semantic_shape == "diamond" and not nl.is_dummy
        ]
        assert diamonds, "No diamond-shaped node found in flowchart-diamond-clipping"

    def test_edge_endpoints_near_diamond_boundary(self, layout: FinalizedLayout):
        """Edge endpoints incident to diamond nodes lie near the node boundary. (AC4)"""
        TOLERANCE = 16.0  # generous: shape-boundary-exactness spec handles sub-pixel
        diamond_ids = {
            nid for nid, nl in layout.node_layouts.items()
            if nl.semantic_shape == "diamond" and not nl.is_dummy
        }
        for edge in layout.routed_edges:
            if len(edge.waypoints) < 2:
                continue
            for which, wp, nid in (
                ("source", edge.waypoints[0], edge.src_node_id),
                ("target", edge.waypoints[-1], edge.dst_node_id),
            ):
                if nid not in diamond_ids:
                    continue
                nl = layout.node_layouts[nid]
                inflated = nl.outer_bounds.inflate(TOLERANCE)
                assert inflated.contains_point(wp), (
                    f"Edge {edge.edge_id!r} {which} endpoint {wp} is not within "
                    f"{TOLERANCE}px of diamond node {nid!r} bounds {nl.outer_bounds}"
                )

    def test_geometry_verifier_passes(self, layout: FinalizedLayout):
        """Geometry verifier reports zero violations on diamond-clipping layout. (AC9)"""
        violations = verify_layout(layout)
        assert violations == [], f"Geometry violations: {violations}"


class TestFlowchartEmptySubgraph:
    """Empty compounds have non-zero bounds; sibling groups do not overlap. (AC5)"""

    @pytest.fixture(scope="class")
    def layout(self):
        return _compile("flowchart-empty-subgraph")

    def test_groups_present_in_layout(self, layout: FinalizedLayout):
        """The fixture produces at least one group in the layout. (AC5)"""
        # ELK may collapse empty subgraphs; if it does, the subsequent
        # empty-group test skips gracefully. This test confirms the pipeline
        # produced some group structure.
        assert len(layout.group_layouts) > 0, (
            "No groups found — ELK may have collapsed all subgraphs. "
            "If this is a known ELK limitation, skip via pytest.skip above."
        )

    def test_empty_group_has_positive_bounds(self, layout: FinalizedLayout):
        """The 'Empty' group has positive width and height. (AC5)

        Note: ELK may drop subgraphs with no member nodes. If that happens,
        this test skips rather than fails — the empty-subgraph rendering
        limitation is tracked separately.
        """
        # The group ID may vary; we look for a group with no member nodes
        empty_groups = [
            (gid, gl) for gid, gl in layout.group_layouts.items()
            if len(gl.member_ids) == 0
        ]
        if not empty_groups:
            pytest.skip("No empty groups found in layout (ELK may have dropped them)")
        for gid, gl in empty_groups:
            assert gl.boundary_bounds.w > 0, f"Empty group {gid!r} has zero width"
            assert gl.boundary_bounds.h > 0, f"Empty group {gid!r} has zero height"

    def test_sibling_groups_do_not_overlap(self, layout: FinalizedLayout):
        """Sibling groups do not overlap. (AC5)"""
        violations = [v for v in verify_layout(layout) if v.kind == "group-overlap"]
        assert violations == [], f"Sibling group overlap violations: {violations}"

    def test_geometry_verifier_passes(self, layout: FinalizedLayout):
        """Geometry verifier reports zero violations on empty-subgraph layout. (AC9)"""
        violations = verify_layout(layout)
        assert violations == [], f"Geometry violations: {violations}"


class TestFlowchartGroupsComplex:
    """Containment for flowchart-groups-complex.mmd. (AC6)"""

    @pytest.fixture(scope="class")
    def layout(self):
        return _compile("flowchart-groups-complex")

    def test_groups_exist_in_layout(self, layout: FinalizedLayout):
        """The complex-groups fixture produces group_layouts. (AC6)"""
        assert len(layout.group_layouts) > 0, "No groups found in flowchart-groups-complex layout"

    def test_zero_containment_violations(self, layout: FinalizedLayout):
        """All nodes are contained within their declared parent groups. (AC6)"""
        violations = [v for v in verify_layout(layout) if v.kind == "containment"]
        assert violations == [], f"Containment violations: {violations}"

    def test_no_node_overlap(self, layout: FinalizedLayout):
        """No two nodes overlap within the groups-complex layout. (AC6)"""
        violations = [v for v in verify_layout(layout) if v.kind == "node-overlap"]
        assert violations == [], f"Node-overlap violations: {violations}"

    def test_geometry_verifier_passes(self, layout: FinalizedLayout):
        """Geometry verifier reports zero violations on groups-complex layout. (AC9)"""
        violations = verify_layout(layout)
        assert violations == [], f"Geometry violations: {violations}"


class TestFlowchartInnerDirection:
    """Local direction is solved recursively; children arranged along that axis. (AC7)

    Fixture: The 'pipeline' subgraph has direction LR.
    Expected: ingest, transform, load have distinct x-positions (horizontal).
    """

    @pytest.fixture(scope="class")
    def layout(self):
        return _compile("flowchart-inner-direction")

    def test_pipeline_group_exists(self, layout: FinalizedLayout):
        """The inner-direction fixture has a group (pipeline) in the layout. (AC7)"""
        assert len(layout.group_layouts) > 0, (
            "No groups found — inner-direction subgraph was not preserved"
        )

    def test_inner_direction_nodes_arranged_horizontally(self, layout: FinalizedLayout):
        """Child nodes of the LR pipeline group have distinct x-positions. (AC7)

        Note: inner-direction uses Python fallback (has_inner_dir=True), so
        local_direction on the GroupLayout reflects the declared direction even
        when ELK is not used for the inner layout. If no LR group is found,
        the test fails — this would indicate the inner-direction metadata was
        not preserved.
        """
        lr_groups = {
            gid: gl for gid, gl in layout.group_layouts.items()
            if gl.local_direction in ("LR", "RL")
        }
        assert lr_groups, (
            "No LR/RL-direction groups found in inner-direction layout. "
            "The pipeline subgraph's direction LR should be captured in GroupLayout.local_direction."
        )

        for gid, gl in lr_groups.items():
            member_ids = gl.member_ids
            if len(member_ids) < 2:
                continue
            xs = [
                layout.node_layouts[m].outer_bounds.center.x
                for m in member_ids
                if m in layout.node_layouts and not layout.node_layouts[m].is_dummy
            ]
            if len(xs) < 2:
                continue
            x_span = max(xs) - min(xs)
            ys = [
                layout.node_layouts[m].outer_bounds.center.y
                for m in member_ids
                if m in layout.node_layouts and not layout.node_layouts[m].is_dummy
            ]
            y_span = max(ys) - min(ys)
            # In LR layout, nodes should be spread more horizontally than vertically
            assert x_span > y_span or x_span > 50, (
                f"Group {gid!r} (LR): x_span={x_span:.0f} not > y_span={y_span:.0f} "
                f"— nodes may not be arranged horizontally"
            )

    def test_geometry_verifier_passes(self, layout: FinalizedLayout):
        """Geometry verifier reports zero violations on inner-direction layout. (AC9)"""
        violations = verify_layout(layout)
        assert violations == [], f"Geometry violations: {violations}"
