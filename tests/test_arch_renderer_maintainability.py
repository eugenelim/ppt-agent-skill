"""Acceptance harness for docs/specs/arch-renderer-maintainability-cleanup.

Covers:
  T1: _edge_stroke_attrs resolver (AC1–AC3, AC12)
  T2: _build_arch_layout extraction (AC4–AC7)
  T3: content_bounds + diagnostics round-trip (AC8–AC11)
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


# ── T1: _edge_stroke_attrs resolver ──────────────────────────────────────────

class TestEdgeStrokeAttrs:
    """AC1: 7-case branch coverage of _edge_stroke_attrs."""

    def setup_method(self):
        from mermaid_render.layout._renderer import _edge_stroke_attrs, _NEUTRAL_STROKE
        self._fn = _edge_stroke_attrs
        self._neutral = _NEUTRAL_STROKE

    def _call(self, style: str, faithful: bool = False):
        return self._fn(style, faithful)

    # ── thick ────────────────────────────────────────────────────────────────

    def test_thick_editorial_color(self):
        sc, sw, dash = self._call("thick", faithful=False)
        assert sc == "var(--edge-strong,var(--accent-1,#60a5fa))"
        assert sw == "2"
        assert dash == ""

    def test_thick_faithful_neutral(self):
        sc, sw, dash = self._call("thick", faithful=True)
        assert sc == self._neutral
        assert sw == "2"
        assert dash == ""

    # ── dotted ───────────────────────────────────────────────────────────────

    def test_dotted_editorial_color(self):
        sc, sw, dash = self._call("dotted", faithful=False)
        assert sc == "var(--accent-4,var(--amber,#E8924A))"
        assert sw == "1.5"
        assert 'stroke-dasharray="6 4"' in dash

    def test_dotted_faithful_neutral(self):
        sc, sw, dash = self._call("dotted", faithful=True)
        assert sc == self._neutral
        assert sw == "1.5"
        assert 'stroke-dasharray="6 4"' in dash

    # ── solid / default ──────────────────────────────────────────────────────

    def test_solid_editorial(self):
        sc, sw, dash = self._call("solid", faithful=False)
        assert sc == self._neutral
        assert sw == "1.5"
        assert dash == ""

    def test_solid_faithful(self):
        sc, sw, dash = self._call("solid", faithful=True)
        assert sc == self._neutral
        assert sw == "1.5"
        assert dash == ""

    # ── cls-dotted superset branch (AC1 — endswith guard) ────────────────────

    def test_cls_dotted_dash_present(self):
        """cls-dotted (graph-fragment raw-style) must produce a dash pattern."""
        sc, sw, dash = self._call("cls-dotted", faithful=False)
        assert 'stroke-dasharray="6 4"' in dash, (
            "_edge_stroke_attrs must handle raw -dotted suffix via endswith check"
        )
        assert sw == "1.5"


# ── T1: fragment painter behavioral lock (AC12) ──────────────────────────────

class TestFragmentPainterClsDotted:
    """AC12: _render_graph_fragment passes cls-dotted style through _edge_stroke_attrs.

    Uses _layout_class (the uncalled production caller of _render_graph_fragment)
    with a classDiagram that contains a dependency (..>) relation, which the
    parser assigns style='cls-dotted'. The end-to-end path exercises the superset
    endswith branch.
    """

    def test_dependency_stroke_dasharray_present(self):
        from mermaid_render.layout._strategies import _layout_class
        src = "classDiagram\n  ClassA ..> ClassB : uses"
        html = _layout_class(src, "TB", 800)
        assert 'stroke-dasharray="6 4"' in html, (
            "_render_graph_fragment must emit stroke-dasharray for cls-dotted edges"
        )


# ── T2: _build_arch_layout extraction (AC4–AC7) ──────────────────────────────

class TestBuildArchLayout:
    """AC4, AC7: _build_arch_layout is callable and produces consistent edge IDs."""

    def test_build_arch_layout_importable(self):
        """AC4: _build_arch_layout exists as a module-private function."""
        from mermaid_render.layout.architecture import _build_arch_layout
        assert callable(_build_arch_layout)

    def test_duplicate_pair_edge_id_first_survives(self):
        """AC7: a duplicate (src, dst) pair uses a single seen_pairs counter.

        Builds A->B twice; at least one ArchEdge with id 'A->B' must survive.
        (Zero-length routes are skipped, so we assert at least 1 edge total.)
        """
        from mermaid_render.layout._constants import _Node, _Edge, MarkerSpec, MarkerKind
        from mermaid_render.layout.architecture import (
            _build_arch_layout, ArchitectureDiagramLayout,
        )

        nodes = {
            "A": _Node(id="A", label="A", shape="rect"),
            "B": _Node(id="B", label="B", shape="rect"),
            "C": _Node(id="C", label="C", shape="rect"),
        }
        _arrow = MarkerSpec(kind=MarkerKind.ARROW, end="TARGET")
        edges = [
            _Edge(src="A", dst="B", style="solid", target_marker=_arrow),
            _Edge(src="A", dst="B", style="solid", target_marker=_arrow),  # duplicate pair
            _Edge(src="B", dst="C", style="solid", target_marker=_arrow),
        ]
        result = _build_arch_layout(nodes, edges, {}, width_hint=800)
        assert isinstance(result, ArchitectureDiagramLayout)
        edge_ids = [e.edge_id for e in result.edges]
        # At least one A->B edge must exist (zero-length routes may be dropped)
        ab_ids = [eid for eid in edge_ids if eid.startswith("A->B")]
        assert len(ab_ids) >= 1
        # If two A->B edges survived, second must be A->B#1
        if len(ab_ids) == 2:
            assert "A->B" in ab_ids
            assert "A->B#1" in ab_ids

    def test_fallback_returns_finalized_layout(self):
        """AC5: _arch_fallback_to_finalized still returns FinalizedLayout."""
        from mermaid_render.layout._geometry import FinalizedLayout
        from mermaid_render.layout.architecture import _arch_fallback_to_finalized
        from mermaid_render.layout._constants import _Node
        nodes = {
            "X": _Node(id="X", label="X"),
            "Y": _Node(id="Y", label="Y"),
        }
        fl = _arch_fallback_to_finalized(nodes, [], {}, width_hint=800)
        assert isinstance(fl, FinalizedLayout)


# ── T3: content_bounds + diagnostics round-trip (AC8–AC11) ───────────────────

class TestArchRoundtripCarriesFields:
    """AC8–AC11: ArchServiceTile.content_bounds and ArchitectureDiagramLayout.diagnostics
    survive _finalized_to_arch → arch_to_finalized.
    """

    def _make_minimal_fl(self, custom_content_bounds, custom_diagnostics):
        """Synthetic FinalizedLayout with one node whose content_bounds differs
        from the fixed-offset derivation (outer_bounds = Rect(0,0,120,80) →
        fixed-offset = Rect(8,4,104,72); we use Rect(10,10,100,60) as the
        distinctive synthetic value).
        """
        from mermaid_render.layout._geometry import (
            FinalizedLayout, NodeLayout, LayoutDiagnostics, Rect, _empty_diagnostics,
        )
        nl = NodeLayout(
            node_id="svc",
            semantic_shape="arch-service",
            outer_bounds=Rect(0.0, 0.0, 120.0, 80.0),
            content_bounds=custom_content_bounds,
            title_layout=None, subtitle_layout=None, member_layouts=(),
            icon_bounds=None, ports=(), css_classes=(), extra_css="",
            is_dummy=False, rank=0, is_external=False,
            icon_svg="", accent_color="", parent_group_id=None,
        )
        return FinalizedLayout(
            node_layouts=types.MappingProxyType({"svc": nl}),
            group_layouts=types.MappingProxyType({}),
            routed_edges=(),
            visible_bounds=Rect(0.0, 0.0, 800.0, 600.0),
            diagram_padding=48.0,
            canvas_bounds=Rect(0.0, 0.0, 800.0, 600.0),
            direction="LR",
            diagnostics=custom_diagnostics,
        )

    def _build_nodes(self):
        from mermaid_render.layout._constants import _Node
        return {"svc": _Node(id="svc", label="Service", shape="rect")}

    def test_content_bounds_carried_through(self):
        """AC11: distinctive content_bounds from ELK survives round-trip."""
        from mermaid_render.layout._geometry import (
            Rect, _empty_diagnostics, LayoutDiagnostics,
        )
        from mermaid_render.layout.architecture import (
            _finalized_to_arch, arch_to_finalized,
        )
        custom_cb = Rect(10.0, 10.0, 100.0, 60.0)
        diag = _empty_diagnostics()
        fl = self._make_minimal_fl(custom_cb, diag)
        nodes = self._build_nodes()

        arch = _finalized_to_arch(fl, nodes, {}, backend="elk-js", zoom=1.0)
        result = arch_to_finalized(arch)

        assert "svc" in result.node_layouts
        out_cb = result.node_layouts["svc"].content_bounds
        assert out_cb.x == pytest.approx(10.0), "content_bounds.x must survive round-trip"
        assert out_cb.y == pytest.approx(10.0), "content_bounds.y must survive round-trip"
        assert out_cb.w == pytest.approx(100.0), "content_bounds.w must survive round-trip"
        assert out_cb.h == pytest.approx(60.0), "content_bounds.h must survive round-trip"

    def test_diagnostics_route_failures_carried_through(self):
        """AC11: non-empty route_failures survive round-trip.

        LayoutDiagnostics.route_failures is tuple[str, ...] (edge IDs).
        """
        from mermaid_render.layout._geometry import (
            Rect, LayoutDiagnostics,
        )
        from mermaid_render.layout.architecture import (
            _finalized_to_arch, arch_to_finalized,
        )
        custom_diag = LayoutDiagnostics(
            unsupported_options=(),
            route_failures=("A->B",),
            warnings=(),
        )
        custom_cb = Rect(8.0, 4.0, 104.0, 72.0)  # same as fixed-offset, only diag matters
        fl = self._make_minimal_fl(custom_cb, custom_diag)
        nodes = self._build_nodes()

        arch = _finalized_to_arch(fl, nodes, {}, backend="elk-js", zoom=1.0)
        result = arch_to_finalized(arch)

        assert len(result.diagnostics.route_failures) == 1
        assert result.diagnostics.route_failures[0] == "A->B"

    def test_backend_tag_not_duplicated(self):
        """AC10: backend tag already in diagnostics.warnings is not added again."""
        from mermaid_render.layout._geometry import (
            Rect, LayoutDiagnostics,
        )
        from mermaid_render.layout.architecture import (
            _finalized_to_arch, arch_to_finalized,
        )
        # Simulate ELK-enriched FinalizedLayout that already stamped "elk-js"
        custom_diag = LayoutDiagnostics(
            unsupported_options=(),
            route_failures=(),
            warnings=("elk-js",),
        )
        custom_cb = Rect(8.0, 4.0, 104.0, 72.0)
        fl = self._make_minimal_fl(custom_cb, custom_diag)
        nodes = self._build_nodes()

        arch = _finalized_to_arch(fl, nodes, {}, backend="elk-js", zoom=1.0)
        result = arch_to_finalized(arch)

        elk_count = result.diagnostics.warnings.count("elk-js")
        assert elk_count == 1, (
            f"'elk-js' must appear exactly once in warnings, got {elk_count}: "
            f"{result.diagnostics.warnings}"
        )

    def test_python_fallback_uses_fixed_offset_content_bounds(self):
        """AC9: Python-fallback path (content_bounds=None) uses fixed-offset derivation."""
        from mermaid_render.layout._geometry import _empty_diagnostics
        from mermaid_render.layout.architecture import (
            _arch_fallback_to_finalized,
        )
        from mermaid_render.layout._constants import _Node

        nodes = {"svc": _Node(id="svc", label="Service", shape="rect")}
        fl = _arch_fallback_to_finalized(nodes, [], {}, width_hint=800)
        assert "svc" in fl.node_layouts
        outer = fl.node_layouts["svc"].outer_bounds
        cb = fl.node_layouts["svc"].content_bounds
        # Fixed-offset derivation: x+8, y+4, max(w-16,20), max(h-8,10)
        assert cb.x == pytest.approx(outer.x + 8.0)
        assert cb.y == pytest.approx(outer.y + 4.0)
        expected_w = float(max(outer.w - 16.0, 20.0))
        expected_h = float(max(outer.h - 8.0, 10.0))
        assert cb.w == pytest.approx(expected_w)
        assert cb.h == pytest.approx(expected_h)
