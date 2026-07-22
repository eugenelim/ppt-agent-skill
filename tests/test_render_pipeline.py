"""Tests for P0 registry hardening: aliasing, builders, render_svg_result() pipeline.

Covers AC-1 through AC-13 from docs/specs/mermaid-native-p0/spec.md.
"""
from __future__ import annotations

import pytest


# ── AC-1 / AC-2: Directive aliasing ──────────────────────────────────────────

class TestDirectiveAliasing:
    def test_canonicalize_directive_graph_maps_to_flowchart(self):
        from scripts.mermaid_render.registry import canonicalize_directive
        assert canonicalize_directive("graph") == "flowchart"

    def test_canonicalize_directive_unknown_returns_same(self):
        from scripts.mermaid_render.registry import canonicalize_directive
        assert canonicalize_directive("xyzunknown") == "xyzunknown"

    def test_canonicalize_directive_already_canonical(self):
        from scripts.mermaid_render.registry import canonicalize_directive
        assert canonicalize_directive("flowchart") == "flowchart"
        assert canonicalize_directive("statediagram-v2") == "statediagram-v2"

    def test_get_capability_graph_returns_flowchart_entry(self):
        from scripts.mermaid_render.registry import get_capability
        cap = get_capability("graph")
        assert cap.diagram_type == "flowchart"
        assert cap.native_status == "implemented"

    def test_get_capability_unknown_raises_unsupported_diagram_type(self):
        from scripts.mermaid_render.registry import get_capability
        from scripts.mermaid_render.errors import UnsupportedDiagramType
        with pytest.raises(UnsupportedDiagramType):
            get_capability("xyz-nonexistent-type")

    def test_parse_render_request_graph_canonical_is_flowchart(self):
        from scripts.mermaid_render.native_svg import parse_render_request
        req = parse_render_request("graph TD\n  A-->B")
        assert req.directive == "flowchart"


# ── AC-3: Unknown directive raises UnsupportedDiagramType ────────────────────

class TestUnknownDirectiveFails:
    def test_render_svg_result_unknown_raises_unsupported(self):
        from scripts.mermaid_render.native_svg import render_svg_result
        from scripts.mermaid_render.errors import UnsupportedDiagramType
        with pytest.raises(UnsupportedDiagramType):
            render_svg_result("unknownxyz TD\n  A-->B\n")

    def test_dispatch_native_result_unknown_directive_returns_error_result(self):
        from scripts.mermaid_render import dispatch_native_result
        result = dispatch_native_result("unknownxyz TD\n  A-->B\n")
        assert result.svg is None
        assert result.errors
        assert not result.is_success(strict=False)


# ── AC-4 / AC-5: Registry builders populated ─────────────────────────────────

class TestRegistryBuilders:
    def test_implemented_entries_have_native_builder(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        for dtype, cap in RENDERER_REGISTRY.items():
            if cap.native_status == "implemented":
                assert cap.native_builder is not None, (
                    f"{dtype} is implemented but has no native_builder"
                )

    def test_experimental_entries_have_native_builder(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        for dtype, cap in RENDERER_REGISTRY.items():
            if cap.native_status == "experimental":
                assert cap.native_builder is not None, (
                    f"{dtype} is experimental but has no native_builder"
                )

    def test_legacy_entries_have_no_native_builder(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        for dtype, cap in RENDERER_REGISTRY.items():
            if cap.native_status == "legacy-only":
                assert cap.native_builder is None, (
                    f"{dtype} is legacy-only but has a native_builder"
                )

    def test_unsupported_entries_have_no_native_builder(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        for dtype, cap in RENDERER_REGISTRY.items():
            if cap.native_status == "unsupported":
                assert cap.native_builder is None, (
                    f"{dtype} is unsupported but has a native_builder"
                )


# ── AC-11: RenderResult.to_exception() ───────────────────────────────────────

class TestToException:
    def test_to_exception_geometry_failed_with_errors(self):
        """geometry=failed takes priority over errors; validator messages go to __cause__."""
        from scripts.mermaid_render.registry import RenderResult
        from scripts.mermaid_render.errors import NativeRenderError
        r = RenderResult(
            svg=None, diagram_type="flowchart", backend="native-svg",
            semantic_adapter="passed", syntax_coverage="passed",
            geometry="failed", serialization="failed",
            warnings=(), errors=("something went wrong",),
        )
        exc = r.to_exception()
        assert isinstance(exc, NativeRenderError)
        assert exc.phase == "geometry"
        assert exc.__cause__ is not None
        assert "something went wrong" in str(exc.__cause__)

    def test_to_exception_geometry_failed_no_errors(self):
        from scripts.mermaid_render.registry import RenderResult
        from scripts.mermaid_render.errors import NativeRenderError
        r = RenderResult(
            svg=None, diagram_type="flowchart", backend="native-svg",
            semantic_adapter="passed", syntax_coverage="passed",
            geometry="failed", serialization="failed",
            warnings=(), errors=(),
        )
        exc = r.to_exception()
        assert isinstance(exc, NativeRenderError)
        assert exc.phase == "geometry"
        assert exc.__cause__ is None

    def test_to_exception_pipeline_errors_without_geometry_failure(self):
        """Non-geometry errors (geometry=unvalidated + errors) → phase=pipeline."""
        from scripts.mermaid_render.registry import RenderResult
        from scripts.mermaid_render.errors import NativeRenderError
        r = RenderResult(
            svg=None, diagram_type="flowchart", backend="native-svg",
            semantic_adapter="passed", syntax_coverage="passed",
            geometry="unvalidated", serialization="failed",
            warnings=(), errors=("pipeline error",),
        )
        exc = r.to_exception()
        assert isinstance(exc, NativeRenderError)
        assert exc.phase == "pipeline"

    def test_to_exception_svg_none(self):
        from scripts.mermaid_render.registry import RenderResult
        from scripts.mermaid_render.errors import NativeRenderError
        r = RenderResult(
            svg=None, diagram_type="flowchart", backend="native-svg",
            semantic_adapter="passed", syntax_coverage="passed",
            geometry="unvalidated", serialization="failed",
            warnings=(), errors=(),
        )
        exc = r.to_exception()
        assert isinstance(exc, NativeRenderError)
        assert exc.phase == "build"


# ── AC-6 / AC-7: render_svg_result() pipeline ────────────────────────────────

class TestRenderSvgResult:
    def test_render_svg_result_flowchart_strict_success(self):
        from scripts.mermaid_render.native_svg import render_svg_result
        result = render_svg_result("flowchart TD\n  A-->B\n")
        assert result.is_success(strict=True), (
            f"Expected strict success; geometry={result.geometry} errors={result.errors}"
        )

    def test_render_svg_result_flowchart_geometry_passed(self):
        from scripts.mermaid_render.native_svg import render_svg_result
        result = render_svg_result("flowchart TD\n  A-->B\n")
        assert result.geometry == "passed"

    def test_render_svg_result_flowchart_backend_native_svg(self):
        from scripts.mermaid_render.native_svg import render_svg_result
        result = render_svg_result("flowchart TD\n  A-->B\n")
        assert result.backend == "native-svg"

    def test_render_svg_result_flowchart_has_svg(self):
        from scripts.mermaid_render.native_svg import render_svg_result
        result = render_svg_result("flowchart TD\n  A-->B\n")
        assert result.svg is not None
        assert "<svg" in result.svg

    def test_render_svg_result_sequence_has_svg(self):
        from scripts.mermaid_render.native_svg import render_svg_result
        result = render_svg_result("sequenceDiagram\n  Alice->>Bob: Hi\n")
        assert result.svg is not None
        assert "<svg" in result.svg

    def test_render_svg_result_experimental_has_partial_syntax(self):
        from scripts.mermaid_render.native_svg import render_svg_result
        result = render_svg_result("classDiagram\n  class Animal\n")
        assert result.syntax_coverage == "partial"
        assert result.semantic_adapter == "partial"  # was "unsupported"; "partial" = experimental
        assert result.geometry == "unvalidated"

    def test_render_svg_result_builder_exception_wraps_cause(self, monkeypatch):
        import scripts.mermaid_render.registry as reg_mod
        import scripts.mermaid_render.native_svg as native_mod
        from scripts.mermaid_render.errors import NativeRenderError

        def _bad(*a, **kw):
            raise RuntimeError("builder exploded")

        # Patch the capability's native_builder via a mock registry entry
        from scripts.mermaid_render.registry import _make
        bad_cap = _make("flowchart", "implemented", builder=_bad)
        monkeypatch.setitem(reg_mod.RENDERER_REGISTRY, "flowchart", bad_cap)
        with pytest.raises(NativeRenderError) as exc_info:
            native_mod.render_svg_result("flowchart TD\n  A-->B\n")
        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert "builder exploded" in str(exc_info.value.__cause__)

    def test_render_svg_result_geometry_failed_errors_propagated(self, monkeypatch):
        """Geometry-failed results must carry the validator's error strings, not ()."""
        import scripts.mermaid_render.registry as reg_mod
        import scripts.mermaid_render.native_svg as native_mod
        from scripts.mermaid_render.registry import _make, _build_flowchart

        def _builder_with_errors(req):
            scene, _ = _build_flowchart(req)

            class FakeValidation:
                errors = ["overlap detected", "route infeasible"]

            return scene, FakeValidation()

        bad_cap = _make("flowchart", "implemented", builder=_builder_with_errors)
        monkeypatch.setitem(reg_mod.RENDERER_REGISTRY, "flowchart", bad_cap)
        result = native_mod.render_svg_result("flowchart TD\n  A-->B\n")
        assert result.geometry == "failed"
        assert "overlap detected" in result.errors
        assert "route infeasible" in result.errors


# ── AC-6 / AC-10: dispatch_native_result and to_svg wired to pipeline ─────────

class TestPipelineWiring:
    def test_dispatch_native_result_flowchart_geometry_passed(self):
        from scripts.mermaid_render import dispatch_native_result
        result = dispatch_native_result("flowchart TD\n  A-->B\n")
        assert result.geometry == "passed"
        assert result.is_success(strict=True)

    def test_dispatch_native_result_graph_alias_succeeds(self):
        """AC-2: 'graph' alias canonicalizes to flowchart and produces strict success."""
        from scripts.mermaid_render import dispatch_native_result
        result = dispatch_native_result("graph TD\n  A-->B\n")
        assert result.is_success(strict=True)
        assert result.diagram_type == "flowchart"

    def test_to_svg_uses_render_svg_result_pipeline(self):
        """AC-9: to_svg() returns SVG via the geometry-passed pipeline."""
        import os
        from unittest.mock import patch
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE
        with patch.dict(os.environ, {BACKEND_ENV: BACKEND_NATIVE}):
            svg = to_svg("flowchart TD\n  A-->B\n")
        assert "<svg" in svg

    def test_to_svg_geometry_failed_raises(self, monkeypatch):
        """Headline behavior: to_svg() raises NativeRenderError(phase='geometry') on validation failure."""
        import os
        import scripts.mermaid_render.registry as reg_mod
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE
        from scripts.mermaid_render.errors import NativeRenderError
        from scripts.mermaid_render.registry import _make, _build_flowchart

        def _builder_with_errors(req):
            scene, _ = _build_flowchart(req)

            class FakeValidation:
                errors = ["overlap detected"]

            return scene, FakeValidation()

        bad_cap = _make("flowchart", "implemented", builder=_builder_with_errors)
        monkeypatch.setitem(reg_mod.RENDERER_REGISTRY, "flowchart", bad_cap)
        monkeypatch.setenv(BACKEND_ENV, BACKEND_NATIVE)
        with pytest.raises(NativeRenderError) as exc_info:
            to_svg("flowchart TD\n  A-->B\n")
        assert exc_info.value.phase == "geometry"
        assert "overlap detected" in str(exc_info.value.__cause__)

    def test_sequence_native_produces_svg(self, monkeypatch):
        """sequenceDiagram has an experimental native builder; experimental=True required."""
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE
        monkeypatch.setenv(BACKEND_ENV, BACKEND_NATIVE)
        result = to_svg("sequenceDiagram\n    Alice->>Bob: Hi\n", experimental=True)
        assert result
        assert "<svg" in result
