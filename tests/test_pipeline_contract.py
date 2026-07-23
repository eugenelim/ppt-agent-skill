"""Pipeline contract tests — Step 1 of the flowchart-pipeline-finish spec.

All 10 tests here are written RED (failing) before implementation. They encode
the observable contracts the new pipeline must satisfy. Each test will fail until
the corresponding implementation task is complete.

Spec: docs/specs/flowchart-pipeline-finish/spec.md
"""
from __future__ import annotations

import ast
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_minimal_finalized_layout(
    *,
    node_layouts: "dict | Any" = None,
    group_layouts: "dict | Any" = None,
    routed_edges: "tuple" = (),
    routing_failures: "tuple" = (),
    canvas_x: float = 0.0,
    canvas_y: float = 0.0,
    canvas_w: float = 400.0,
    canvas_h: float = 300.0,
):
    """Build a minimal FinalizedLayout for geometry tests."""
    from mermaid_render.layout._geometry import (
        FinalizedLayout, LayoutDiagnostics, Rect, _empty_diagnostics,
    )
    return FinalizedLayout(
        node_layouts=node_layouts if node_layouts is not None else {},
        group_layouts=group_layouts if group_layouts is not None else {},
        routed_edges=routed_edges,
        visible_bounds=Rect(canvas_x, canvas_y, canvas_w, canvas_h),
        diagram_padding=20.0,
        canvas_bounds=Rect(canvas_x, canvas_y, canvas_w, canvas_h),
        direction="TB",
        diagnostics=_empty_diagnostics(),
    )


# ── Test 1: validate() reports a known node overlap ──────────────────────────

class TestValidateDetectsNodeOverlap:
    """validate() must return errors when two node bodies overlap."""

    def test_validate_detects_node_overlap(self):
        from mermaid_render.layout._geometry import (
            NodeLayout, Rect, FinalizedLayout,
        )
        try:
            from mermaid_render.layout._geometry import validate_finalized_layout
        except ImportError:
            pytest.fail(
                "validate_finalized_layout() not yet implemented in _geometry.py"
            )

        # Two nodes with identical bounds — clearly overlapping
        def _make_node(nid: str, x: float, y: float) -> NodeLayout:
            r = Rect(x, y, 100, 60)
            return NodeLayout(
                node_id=nid, semantic_shape="rect",
                outer_bounds=r, content_bounds=r,
                title_layout=None, subtitle_layout=None,
                member_layouts=(), icon_bounds=None, ports=(),
                css_classes=(), extra_css="",
            )

        layout = _make_minimal_finalized_layout(
            node_layouts={"A": _make_node("A", 0, 0), "B": _make_node("B", 0, 0)},
        )
        result = validate_finalized_layout(layout)
        assert result.errors, (
            "validate_finalized_layout() returned no errors for two nodes at (0,0) — "
            "expected an overlap error"
        )


# ── Test 2: validate() reports a missing/failed route ────────────────────────

class TestValidateDetectsMissingRoute:
    """validate() must error when metadata.edge_count > len(routed_edges) + len(routing_failures)."""

    def test_validate_detects_missing_route(self):
        try:
            from mermaid_render.layout._geometry import validate_finalized_layout, LayoutMetadata
        except ImportError:
            pytest.fail(
                "validate_finalized_layout() or LayoutMetadata not yet implemented"
            )
        from mermaid_render.layout._geometry import (
            NodeLayout, Rect, FinalizedLayout, _empty_diagnostics,
        )

        def _make_node(nid: str) -> NodeLayout:
            r = Rect(10, 10, 80, 50)
            return NodeLayout(
                node_id=nid, semantic_shape="rect",
                outer_bounds=r, content_bounds=r,
                title_layout=None, subtitle_layout=None,
                member_layouts=(), icon_bounds=None, ports=(),
                css_classes=(), extra_css="",
            )

        # Layout says 1 edge was parsed, but routed_edges=() and routing_failures=()
        # → edge_count=1 vs 0+0=0 → missing route
        layout = _make_minimal_finalized_layout(
            node_layouts={"A": _make_node("A"), "B": _make_node("B")},
            routed_edges=(),
            routing_failures=(),
        )
        # Inject metadata directly to simulate 1 parsed edge
        try:
            from mermaid_render.layout._geometry import CompiledFlowchart
        except ImportError:
            pytest.fail("CompiledFlowchart not yet implemented")

        meta = LayoutMetadata(
            direction="TB",
            node_count=2,
            group_count=0,
            edge_count=1,
            algorithm="LongestPathRanker+BarycentricTransposeOrderer+IsotonicCoordinateAssigner",
        )
        # validate_finalized_layout should accept layout + metadata for edge-count reconciliation
        result = validate_finalized_layout(layout, metadata=meta)
        assert result.errors, (
            "validate_finalized_layout() returned no errors when edge_count=1 but "
            "routed_edges=() and routing_failures=() — expected a missing-route error"
        )


# ── Test 3: validate() reports a group outside the canvas ────────────────────

class TestValidateDetectsGroupOutsideCanvas:
    """validate() must error when a group's boundary_bounds exceeds canvas_bounds."""

    def test_validate_detects_group_outside_canvas(self):
        try:
            from mermaid_render.layout._geometry import validate_finalized_layout
        except ImportError:
            pytest.fail("validate_finalized_layout() not yet implemented")

        from mermaid_render.layout._geometry import GroupLayout, Rect

        # Group extends to x=500, but canvas_w=400
        group = GroupLayout(
            group_id="G",
            parent_group_id=None,
            boundary_bounds=Rect(0, 0, 500, 200),
            label_layout=None,
            member_ids=(),
            child_group_ids=(),
            local_direction="TB",
        )
        layout = _make_minimal_finalized_layout(
            group_layouts={"G": group},
            canvas_w=400.0,
        )
        result = validate_finalized_layout(layout)
        assert result.errors, (
            "validate_finalized_layout() returned no errors when group boundary "
            "extends to x=500 but canvas_w=400 — expected a group-outside-canvas error"
        )


# ── Test 4: validate() reports a blocked edge label ──────────────────────────

class TestValidateDetectsBlockedLabel:
    """validate() must error when an edge label's bounds are outside the canvas."""

    def test_validate_detects_blocked_label(self):
        try:
            from mermaid_render.layout._geometry import validate_finalized_layout
        except ImportError:
            pytest.fail("validate_finalized_layout() not yet implemented")

        from mermaid_render.layout._geometry import (
            RoutedEdge, PortLayout, PortSide, Point, Rect, EdgeLabelLayout,
            TextLayout, TextLine, TextRun, TextStyle,
        )

        # Build a routed edge whose label bounds fall outside the canvas
        label_bounds = Rect(900, 900, 80, 20)   # far outside 400×300 canvas
        ts = TextStyle()
        run = TextRun(text="label", style=ts, width=50.0, height=15.0)
        line = TextLine(runs=(run,), width=50.0, height=15.0, baseline=12.0)
        tl = TextLayout(
            lines=(line,), width=50.0, height=15.0, line_height=15.0,
            min_content_width=50.0, max_content_width=50.0,
            resolved_font_path=None, resolved_font_family="Inter",
        )
        label = EdgeLabelLayout(
            text="label", layout=tl,
            bounds=label_bounds, anchor_point=Point(950, 910),
        )

        def _make_port(node_id: str) -> PortLayout:
            return PortLayout(
                node_id=node_id, side=PortSide.BOTTOM,
                position=Point(50, 60), direction=Point(0, 1),
            )

        edge = RoutedEdge(
            edge_id="e1", src_node_id="A", dst_node_id="B",
            src_port=_make_port("A"), dst_port=_make_port("B"),
            waypoints=(Point(50, 60), Point(50, 120)),
            edge_style="solid",
            has_marker_end=True, has_marker_start=False,
            label_layout=label,
            src_label_layout=None,
            dst_label_layout=None,
        )
        layout = _make_minimal_finalized_layout(routed_edges=(edge,))
        result = validate_finalized_layout(layout)
        assert result.errors, (
            "validate_finalized_layout() returned no errors when edge label is at "
            "(900, 900) but canvas is 400×300 — expected a label-out-of-canvas error"
        )


# ── Test 5: to_html() does NOT call _render_graph_fragment ───────────────────

class TestToHtmlDoesNotCallRenderGraphFragment:
    """to_html() for a flowchart must not call _render_graph_fragment().

    Patches the LOCAL alias in _strategies (where it's actually called today),
    not the attribute on _renderer (which would miss the local import).
    """

    def test_to_html_does_not_call_render_graph_fragment(self):
        import mermaid_render
        import mermaid_render.layout._strategies as _strategies_mod

        original = getattr(_strategies_mod, "_render_graph_fragment", None)

        def _bomb(*args, **kwargs):
            raise AssertionError(
                "_render_graph_fragment() was called by to_html() — "
                "the pipeline must be cut over to render_finalized()"
            )

        _strategies_mod._render_graph_fragment = _bomb
        try:
            html = mermaid_render.to_html("flowchart LR\n    A --> B")
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(
                f"to_html() raised an unexpected exception after replacing "
                f"_render_graph_fragment with a bomb: {e}"
            )
        finally:
            if original is not None:
                _strategies_mod._render_graph_fragment = original

        assert "<div" in html


# ── Test 6: to_html() DOES call render_finalized ─────────────────────────────

class TestToHtmlCallsRenderFinalized:
    """to_html() output for a flowchart must contain the 'finalized' CSS class
    produced by render_finalized(), not the bare 'mermaid-layout' class from
    _render_graph_fragment().
    """

    def test_to_html_calls_render_finalized(self):
        import mermaid_render

        html = mermaid_render.to_html("flowchart LR\n    A --> B")

        assert 'mermaid-layout finalized' in html, (
            "to_html() output does not contain the 'finalized' CSS marker produced by "
            "render_finalized() — the pipeline must be cut over from _render_graph_fragment(). "
            f"Got class string containing: {[c for c in html.split('class=\"') if 'mermaid' in c][:2]}"
        )


# ── Test 7: invalid gallery fixture causes nonzero exit ──────────────────────

class TestGalleryInvalidFixtureExitsNonzero:
    """Gallery command must exit nonzero when validate() returns status='invalid'."""

    def test_gallery_invalid_fixture_exits_nonzero(self, tmp_path):
        import importlib.util
        import subprocess
        import os

        # Write a simple flowchart fixture
        fixture = tmp_path / "flowchart-invalid-test.mmd"
        fixture.write_text("flowchart LR\n    A --> B\n", encoding="utf-8")

        # Run compare_gallery.py with mocked validate that returns invalid status
        runner = REPO_ROOT / "tools" / "compare_gallery.py"
        if not runner.exists():
            pytest.skip("compare_gallery.py not found")

        # Load gallery module and simulate validation returning 'invalid'
        spec = importlib.util.spec_from_file_location("compare_gallery", runner)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Monkeypatch mermaid_render.validate to return an invalid result
        import mermaid_render
        from mermaid_render.layout._geometry import ValidationResult

        original_validate = mermaid_render.validate

        def _always_invalid(src):
            return ValidationResult(errors=("forced invalid geometry",), warnings=())

        mermaid_render.validate = _always_invalid
        try:
            _, has_failures, _ = mod._build_gallery([fixture], tmp_path / "out")
        finally:
            mermaid_render.validate = original_validate

        assert has_failures, (
            "Gallery did not set has_failures=True when validate() returned status='invalid'. "
            "Gallery must wire ValidationResult.status into _classify_status."
        )


# ── Test 8: all parsed edges appear as RoutedEdge or RoutingFailure ───────────

class TestAllParsedEdgesAppearAsRoutedOrFailed:
    """_compile_flowchart() must account for every parsed edge."""

    def test_all_parsed_edges_appear_as_routed_or_failed(self):
        try:
            from mermaid_render.layout._strategies import _compile_flowchart
        except (ImportError, AttributeError):
            pytest.fail(
                "_compile_flowchart() not yet implemented in _strategies.py"
            )

        src = "flowchart LR\n    A --> B\n    B --> C\n    C --> D\n"
        result = _compile_flowchart(src, width_hint=0, options=None)

        routed_ids = {e.edge_id for e in result.layout.routed_edges}
        try:
            failed_ids = {f.edge_id for f in result.layout.routing_failures}
        except AttributeError:
            pytest.fail(
                "FinalizedLayout has no routing_failures field — "
                "add routing_failures: tuple[RoutingFailure, ...] to FinalizedLayout"
            )

        accounted = routed_ids | failed_ids
        assert result.metadata.edge_count == len(accounted), (
            f"edge_count={result.metadata.edge_count} but only {len(accounted)} edges "
            f"appear in routed_edges ({len(routed_ids)}) + routing_failures ({len(failed_ids)})"
        )


# ── Test 9: FinalizedLayout collections cannot be mutated ────────────────────

class TestFinalizedLayoutCollectionsImmutable:
    """FinalizedLayout.node_layouts and .group_layouts must be immutable (MappingProxyType)."""

    def test_finalized_layout_collections_cannot_be_mutated(self):
        from mermaid_render.layout._geometry import (
            FinalizedLayout, NodeLayout, Rect, _empty_diagnostics,
        )

        r = Rect(0, 0, 100, 60)
        node = NodeLayout(
            node_id="A", semantic_shape="rect",
            outer_bounds=r, content_bounds=r,
            title_layout=None, subtitle_layout=None,
            member_layouts=(), icon_bounds=None, ports=(),
            css_classes=(), extra_css="",
        )

        layout = FinalizedLayout(
            node_layouts={"A": node},
            group_layouts={},
            routed_edges=(),
            visible_bounds=Rect(0, 0, 200, 150),
            diagram_padding=20.0,
            canvas_bounds=Rect(0, 0, 200, 150),
            direction="TB",
            diagnostics=_empty_diagnostics(),
        )

        with pytest.raises(TypeError, match=r"(does not support item assignment|'mappingproxy')"):
            layout.node_layouts["B"] = node  # type: ignore[index]


# ── Test 10: no forbidden runtime dependency is imported ──────────────────────

class TestNoForbiddenRuntimeDependency:
    """No layout module may import networkx, numpy, scipy, shapely, graphviz,
    pygraphviz, pydot, subprocess (layout modules only), or playwright (to_html path).
    """

    FORBIDDEN = {
        "networkx", "numpy", "scipy", "shapely",
        "graphviz", "pygraphviz", "pydot",
    }
    LAYOUT_ONLY_FORBIDDEN = {"subprocess"}

    @pytest.fixture(autouse=True)
    def _layout_files(self):
        layout_dir = SCRIPTS / "mermaid_render" / "layout"
        self._py_files = list(layout_dir.glob("*.py"))

    def _imported_names(self, path: Path) -> set[str]:
        """Return all top-level module names imported in a Python file."""
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return set()
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.add(node.module.split(".")[0])
        return names

    # elk_adapter.py and _strategies.py are exempt from the subprocess ban — ADR-001.
    _LAYOUT_SUBPROCESS_EXEMPTIONS: frozenset[str] = frozenset({"elk_adapter.py", "_strategies.py"})

    def test_no_forbidden_runtime_dependency(self):
        violations: list[str] = []
        for path in self._py_files:
            if path.name in self._LAYOUT_SUBPROCESS_EXEMPTIONS:
                forbidden_here = self.FORBIDDEN  # subprocess allowed for exempt file
            else:
                forbidden_here = self.FORBIDDEN | self.LAYOUT_ONLY_FORBIDDEN
            imports = self._imported_names(path)
            for bad in forbidden_here:
                if bad in imports:
                    violations.append(f"{path.name}: imports '{bad}'")
        assert not violations, (
            "Forbidden imports found in layout modules:\n" + "\n".join(violations)
        )


# ── Test 11: validate() never returns geometry="unvalidated" for graph directives ─

class TestValidateNeverReturnsUnvalidatedForGraphDirectives:
    """validate() must set geometry to 'pass' or 'fail' (never 'unvalidated') for
    flowchart/graph/statediagram directives after a successful compile."""

    GRAPH_DIRECTIVES = [
        "flowchart TD\n    A --> B\n",
        "graph LR\n    X --> Y\n",
    ]

    def test_validate_returns_concrete_geometry_for_graph_directives(self):
        import mermaid_render
        for src in self.GRAPH_DIRECTIVES:
            vr = mermaid_render.validate(src)
            assert vr.geometry != "unvalidated", (
                f"validate() returned geometry='unvalidated' for {src!r}; "
                "must be 'pass' or 'fail' after compile."
            )


# ── Test 12: FinalizedLayout deep-copies input dicts ─────────────────────────

class TestFinalizedLayoutDeepCopiesInputDicts:
    """FinalizedLayout must not share a reference with the caller's dict;
    mutations to the original dict after construction must not be visible."""

    def test_deep_copy_node_layouts(self):
        from mermaid_render.layout._geometry import (
            FinalizedLayout, NodeLayout, Rect, _empty_diagnostics,
        )
        r = Rect(0, 0, 100, 60)
        node = NodeLayout(
            node_id="A", semantic_shape="rect",
            outer_bounds=r, content_bounds=r,
            title_layout=None, subtitle_layout=None,
            member_layouts=(), icon_bounds=None, ports=(),
            css_classes=(), extra_css="",
        )
        original = {"A": node}
        layout = FinalizedLayout(
            node_layouts=original,
            group_layouts={},
            routed_edges=(),
            visible_bounds=Rect(0, 0, 200, 150),
            diagram_padding=20.0,
            canvas_bounds=Rect(0, 0, 200, 150),
            direction="TB",
            diagnostics=_empty_diagnostics(),
        )
        # Mutate original after construction — should NOT affect the layout
        original["B"] = node
        assert "B" not in layout.node_layouts, (
            "FinalizedLayout.node_layouts shares a reference with the input dict; "
            "it must be deep-copied before wrapping in MappingProxyType."
        )


# ── Test 13: edge_count comes from parsed edges, not routing output ───────────

class TestEdgeCountFromParsedEdges:
    """LayoutMetadata.edge_count must equal the number of edges parsed before
    _break_cycles, not the number of routed edges."""

    def test_edge_count_matches_parsed_edge_count(self):
        from mermaid_render.layout._strategies import _compile_flowchart
        # Diagram with 3 logical edges
        src = "flowchart TD\n    A --> B\n    B --> C\n    A --> C\n"
        result = _compile_flowchart(src, width_hint=0, options=None)
        # All 3 should be accounted for
        routed = len(result.layout.routed_edges)
        failed = len(result.layout.routing_failures)
        assert result.metadata.edge_count == 3, (
            f"edge_count={result.metadata.edge_count}, expected 3 (parsed edges). "
            "edge_count must be set from the parsed edge list, not routing output."
        )
        assert routed + failed == result.metadata.edge_count, (
            f"routed({routed}) + failed({failed}) != edge_count({result.metadata.edge_count})"
        )


# ── Test 14: RouteBatch returned by _route_edges ──────────────────────────────

class TestRouteBatchReturnedByRouteEdges:
    """_route_edges() must return a RouteBatch with .routed and .failures."""

    def test_route_edges_returns_route_batch(self):
        from mermaid_render.layout._routing import _route_edges
        from mermaid_render.layout._geometry import RouteBatch
        from mermaid_render.layout._constants import _Node, _Edge
        nodes = {
            "A": _Node(id="A", label="A", shape="rect", x=0, y=0, rank=0),
            "B": _Node(id="B", label="B", shape="rect", x=0, y=100, rank=1),
        }
        edges = [_Edge(src="A", dst="B", edge_id="A->B")]
        batch = _route_edges(nodes, edges, canvas_w=300, direction="TB")
        assert isinstance(batch, RouteBatch), (
            f"_route_edges() must return a RouteBatch, got {type(batch).__name__}"
        )
        assert hasattr(batch, "routed"), "RouteBatch must have .routed"
        assert hasattr(batch, "failures"), "RouteBatch must have .failures"


# ── Test 15: PortSide.AUTO must not appear in finalized output ────────────────

class TestPortSideAutoForbiddenInFinalizedOutput:
    """validate_finalized_layout() must report an error when a RoutedEdge port
    has PortSide.AUTO — AUTO is a planning placeholder, not a valid geometry value."""

    def test_port_side_auto_causes_validation_error(self):
        from mermaid_render.layout._geometry import (
            validate_finalized_layout, RoutedEdge, PortLayout, PortSide,
            Point, Rect,
        )
        r = Rect(0, 0, 400, 300)
        auto_port = PortLayout(node_id="A", side=PortSide.AUTO, position=Point(0, 0), direction=Point(0, 1))
        ok_port = PortLayout(node_id="B", side=PortSide.BOTTOM, position=Point(0, 100), direction=Point(0, -1))
        edge = RoutedEdge(
            edge_id="A->B", src_node_id="A", dst_node_id="B",
            src_port=auto_port, dst_port=ok_port,
            waypoints=(Point(0, 0), Point(0, 100)),
            edge_style="solid", has_marker_end=True, has_marker_start=False,
            label_layout=None, src_label_layout=None, dst_label_layout=None,
        )
        layout = _make_minimal_finalized_layout(routed_edges=(edge,))
        vr = validate_finalized_layout(layout)
        assert vr.geometry == "fail", (
            "validate_finalized_layout() must set geometry='fail' when a port has PortSide.AUTO"
        )
        assert any("AUTO" in e for e in vr.errors), (
            "ValidationResult.errors must name the PortSide.AUTO violation"
        )


# ── Test 16: algorithm metadata matches actual calls ─────────────────────────

class TestAlgorithmMetadataIsAccurate:
    """LayoutMetadata.algorithm must name the algorithms actually invoked."""

    PYTHON_ALGO = "LongestPathRanker+BarycentricOrderer+SimpleCoordinateAssigner"
    ELK_ALGO = "ELK-layered"

    def test_algorithm_metadata_matches_actual_calls(self):
        from mermaid_render.layout._strategies import _compile_flowchart
        from mermaid_render.layout.elk_adapter import _find_node, _find_elkjs
        src = "flowchart TD\n    A --> B\n    B --> C\n"
        result = _compile_flowchart(src, width_hint=0, options=None)
        elk_available = _find_node() is not None and _find_elkjs() is not None
        expected = self.ELK_ALGO if elk_available else self.PYTHON_ALGO
        assert result.metadata.algorithm == expected, (
            f"metadata.algorithm={result.metadata.algorithm!r}, "
            f"expected {expected!r}. "
            "Must report the algorithms actually invoked, not the enhanced variants."
        )


# ── Test 17: gallery header has separate lane counts ─────────────────────────

class TestGalleryHeaderHasSeparateCounts:
    """Gallery index.html must show separate render/syntax/geometry/oracle counts."""

    def test_gallery_header_has_lane_counts(self, tmp_path):
        import importlib.util
        runner = REPO_ROOT / "tools" / "compare_gallery.py"
        if not runner.exists():
            pytest.skip("compare_gallery.py not found")
        spec = importlib.util.spec_from_file_location("compare_gallery", runner)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        mmd = tmp_path / "flowchart-header-test.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")
        out_path = tmp_path / "out"
        gallery_path, _, _ = mod._build_gallery([mmd], out_path)
        # _build_gallery returns the path to index.html (or the gallery dir).
        idx = gallery_path / "index.html" if gallery_path.is_dir() else gallery_path
        html = idx.read_text(encoding="utf-8")
        for lane in ("render", "syntax", "geometry", "oracle"):
            assert lane in html, (
                f"Gallery header missing '{lane}' count — "
                "header must show separate render/syntax/geometry/oracle counts."
            )
