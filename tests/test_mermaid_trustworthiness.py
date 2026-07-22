"""
tests/test_mermaid_trustworthiness.py

Regression tests for strict public API enforcement (Phase 1) and
single-registry invariants (Phase 2) from the mermaid-trustworthiness-pass spec.
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch

# ── helpers ───────────────────────────────────────────────────────────────────

BACKEND_ENV = "MERMAID_RENDER_SVG_BACKEND"
BACKEND_NATIVE = "native"

_ARCH_SRC = "architecture-beta\n  service s(internet)[S]\n"
_FLOW_SRC = "flowchart LR\n  A --> B\n"
_SEQ_SRC = "sequenceDiagram\n  Alice->>Bob: Hi\n"


def _native():
    return patch.dict(os.environ, {BACKEND_ENV: BACKEND_NATIVE})


# ── Phase 1: RenderResult.semantic_adapter "partial" ─────────────────────────

class TestRenderResultSemanticAdapter:
    def test_experimental_type_produces_partial_not_unsupported(self):
        """dispatch_native_result() must set semantic_adapter='partial' for experimental types."""
        from scripts.mermaid_render import dispatch_native_result
        with _native():
            result = dispatch_native_result(_ARCH_SRC)
        assert result.semantic_adapter == "partial", (
            f"Expected 'partial' for experimental type, got {result.semantic_adapter!r}"
        )
        assert result.semantic_adapter != "unsupported"

    def test_implemented_type_produces_passed(self):
        """IMPLEMENTED types must still produce semantic_adapter='passed'."""
        from scripts.mermaid_render import dispatch_native_result
        with _native():
            result = dispatch_native_result(_FLOW_SRC)
        assert result.semantic_adapter == "passed"


# ── Phase 1: RenderResult.to_exception() dispatch ────────────────────────────

class TestRenderResultToException:
    def test_partial_returns_experimental_opt_in(self):
        """RenderResult with semantic_adapter='partial' → ExperimentalOptInRequired."""
        from scripts.mermaid_render.registry import RenderResult
        from scripts.mermaid_render.errors import ExperimentalOptInRequired
        r = RenderResult(
            svg="<svg/>",
            diagram_type="architecture-beta",
            backend="native",
            semantic_adapter="partial",
            syntax_coverage="partial",
            geometry="unvalidated",
            serialization="passed",
            warnings=(),
            errors=(),
        )
        exc = r.to_exception()
        assert isinstance(exc, ExperimentalOptInRequired), type(exc)
        assert exc.diagram_type == "architecture-beta"

    def test_unsupported_returns_unsupported_diagram_type(self):
        """RenderResult with semantic_adapter='unsupported' → UnsupportedDiagramType."""
        from scripts.mermaid_render.registry import RenderResult
        from scripts.mermaid_render.errors import UnsupportedDiagramType
        r = RenderResult(
            svg=None,
            diagram_type="sankey-beta",
            backend="none",
            semantic_adapter="unsupported",
            syntax_coverage="failed",
            geometry="unvalidated",
            serialization="failed",
            warnings=(),
            errors=("unsupported",),
        )
        exc = r.to_exception()
        assert isinstance(exc, UnsupportedDiagramType), type(exc)

    def test_partial_checked_before_geometry(self):
        """semantic_adapter='partial' wins over geometry='failed' in priority."""
        from scripts.mermaid_render.registry import RenderResult
        from scripts.mermaid_render.errors import ExperimentalOptInRequired
        r = RenderResult(
            svg="<svg/>",
            diagram_type="architecture-beta",
            backend="native",
            semantic_adapter="partial",
            syntax_coverage="partial",
            geometry="failed",   # set failed deliberately
            serialization="passed",
            warnings=(),
            errors=("some geometry error",),
        )
        exc = r.to_exception()
        # 'partial' must win over 'geometry failed'
        assert isinstance(exc, ExperimentalOptInRequired), type(exc)


# ── Phase 1: ExperimentalOptInRequired importable from public API ─────────────

def test_experimental_opt_in_required_importable():
    from scripts.mermaid_render.errors import ExperimentalOptInRequired
    exc = ExperimentalOptInRequired("architecture-beta")
    assert exc.diagram_type == "architecture-beta"
    assert "architecture-beta" in str(exc)
    assert isinstance(exc, ValueError)


# ── Phase 1: to_svg() strict enforcement ─────────────────────────────────────

class TestToSvgStrictPolicy:
    def test_normal_to_svg_rejects_experimental(self):
        """to_svg() with defaults raises ExperimentalOptInRequired for experimental types."""
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.errors import ExperimentalOptInRequired
        with _native():
            with pytest.raises(ExperimentalOptInRequired) as exc_info:
                to_svg(_ARCH_SRC)
        assert exc_info.value.diagram_type == "architecture-beta"

    def test_experimental_true_permits_partial(self):
        """to_svg(experimental=True) returns SVG for experimental types."""
        from scripts.mermaid_render import to_svg
        with _native():
            result = to_svg(_ARCH_SRC, experimental=True)
        assert result and "<svg" in result

    def test_implemented_strict_always_succeeds(self):
        """to_svg() on IMPLEMENTED types with default strict=True still works."""
        from scripts.mermaid_render import to_svg
        with _native():
            result = to_svg(_FLOW_SRC)
        assert result and "<svg" in result

    def test_unsupported_still_raises_value_error(self):
        """to_svg() on unsupported types raises UnsupportedDiagramType (unchanged)."""
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.errors import UnsupportedDiagramType
        with _native():
            with pytest.raises(UnsupportedDiagramType):
                to_svg("sankey-beta\n  A[1,2,3]")

    def test_experimental_sequence_permitted_with_flag(self):
        """sequenceDiagram (experimental) returns SVG when experimental=True."""
        from scripts.mermaid_render import to_svg
        with _native():
            result = to_svg(_SEQ_SRC, experimental=True)
        assert result and "<svg" in result

    def test_experimental_sequence_rejected_without_flag(self):
        """sequenceDiagram (experimental) raises without experimental=True."""
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.errors import ExperimentalOptInRequired
        with _native():
            with pytest.raises(ExperimentalOptInRequired):
                to_svg(_SEQ_SRC)


# ── Phase 1: to_png() follows same policy ────────────────────────────────────

class TestToPngStrictPolicy:
    def test_to_png_rejects_experimental(self):
        """to_png() raises ExperimentalOptInRequired for experimental types."""
        from scripts.mermaid_render import to_png
        from scripts.mermaid_render.errors import ExperimentalOptInRequired
        with _native():
            with pytest.raises(ExperimentalOptInRequired):
                to_png(_ARCH_SRC)

    def test_to_png_experimental_true_reaches_svg(self):
        """to_png(experimental=True) does not raise ExperimentalOptInRequired."""
        from scripts.mermaid_render import to_png
        from scripts.mermaid_render.errors import ExperimentalOptInRequired
        with _native():
            try:
                to_png(_ARCH_SRC, experimental=True)
            except ExperimentalOptInRequired:
                pytest.fail("to_png with experimental=True raised ExperimentalOptInRequired")
            except Exception:
                pass  # Playwright unavailability is fine; opt-in check must pass


# ── Phase 2: Single registry ──────────────────────────────────────────────────

class TestSingleRegistry:
    def test_native_registry_canonical_keys_match_renderer_registry(self):
        """NATIVE_RENDERER_REGISTRY canonical keys must match RENDERER_REGISTRY keys."""
        from scripts.mermaid_render.scene import NATIVE_RENDERER_REGISTRY
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        renderer_keys = set(RENDERER_REGISTRY.keys())
        native_keys = set(NATIVE_RENDERER_REGISTRY.keys())
        missing = renderer_keys - native_keys
        assert not missing, f"Types in RENDERER not in NATIVE: {missing}"

    def test_no_stale_key_in_native_registry(self):
        """No type in NATIVE_RENDERER_REGISTRY that is absent from both RENDERER and aliases."""
        from scripts.mermaid_render.scene import NATIVE_RENDERER_REGISTRY
        from scripts.mermaid_render.registry import RENDERER_REGISTRY, DIRECTIVE_ALIASES
        valid_keys = set(RENDERER_REGISTRY.keys()) | set(DIRECTIVE_ALIASES.keys())
        stale = set(NATIVE_RENDERER_REGISTRY.keys()) - valid_keys
        assert not stale, f"Stale types in NATIVE_RENDERER_REGISTRY: {stale}"

    def test_graph_alias_present_in_native_registry(self):
        """'graph' alias must survive in NATIVE_RENDERER_REGISTRY."""
        from scripts.mermaid_render.scene import NATIVE_RENDERER_REGISTRY
        assert "graph" in NATIVE_RENDERER_REGISTRY

    def test_implemented_entries_have_builder(self):
        """Every IMPLEMENTED entry in RENDERER_REGISTRY must have a native_builder."""
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        for dtype, cap in RENDERER_REGISTRY.items():
            if cap.native_status == "implemented":
                assert cap.native_builder is not None, (
                    f"{dtype!r} is implemented but has no native_builder"
                )

    def test_unsupported_entries_have_no_builder(self):
        """Every UNSUPPORTED entry must have no native_builder."""
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        for dtype, cap in RENDERER_REGISTRY.items():
            if cap.native_status == "unsupported":
                assert cap.native_builder is None, (
                    f"{dtype!r} is unsupported but has a native_builder"
                )

    def test_native_registry_exact_set_equality(self):
        """NATIVE_RENDERER_REGISTRY keys == RENDERER_REGISTRY keys ∪ DIRECTIVE_ALIASES keys."""
        from scripts.mermaid_render.scene import NATIVE_RENDERER_REGISTRY
        from scripts.mermaid_render.registry import RENDERER_REGISTRY, DIRECTIVE_ALIASES
        expected = set(RENDERER_REGISTRY.keys()) | set(DIRECTIVE_ALIASES.keys())
        actual = set(NATIVE_RENDERER_REGISTRY.keys())
        assert actual == expected, (
            f"Extra in NATIVE: {actual - expected}; "
            f"Missing from NATIVE: {expected - actual}"
        )


# ── AC-1.10: fallback='legacy-dom' does not bypass experimental strictness ─────

class TestFallbackDoesNotBypassExperimental:
    def test_legacy_fallback_still_requires_experimental_flag(self):
        """fallback='legacy-dom' must not bypass ExperimentalOptInRequired."""
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.errors import ExperimentalOptInRequired
        with _native():
            with pytest.raises(ExperimentalOptInRequired):
                to_svg(_ARCH_SRC, fallback="legacy-dom")

    def test_implemented_geometry_failure_raises_regardless_of_experimental(self, monkeypatch):
        """experimental=True must NOT suppress NativeRenderError for IMPLEMENTED types."""
        import scripts.mermaid_render.registry as reg_mod
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.errors import NativeRenderError
        from scripts.mermaid_render.registry import _make, _build_flowchart
        from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE

        def _builder_with_errors(req):
            scene, _ = _build_flowchart(req)

            class FakeValidation:
                errors = ["overlap detected"]

            return scene, FakeValidation()

        bad_cap = _make("flowchart", "implemented", builder=_builder_with_errors)
        monkeypatch.setitem(reg_mod.RENDERER_REGISTRY, "flowchart", bad_cap)
        monkeypatch.setenv(BACKEND_ENV, BACKEND_NATIVE)
        with pytest.raises(NativeRenderError) as exc_info:
            to_svg(_FLOW_SRC, experimental=True)
        assert exc_info.value.phase == "geometry"

    def test_unexpected_builder_exception_is_typed(self, monkeypatch):
        """A raw builder exception from to_svg() surfaces as NativeRenderError."""
        import scripts.mermaid_render.registry as reg_mod
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.errors import NativeRenderError
        from scripts.mermaid_render.registry import _make
        from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE

        def _bad(*a, **kw):
            raise RuntimeError("builder exploded")

        bad_cap = _make("flowchart", "implemented", builder=_bad)
        monkeypatch.setitem(reg_mod.RENDERER_REGISTRY, "flowchart", bad_cap)
        monkeypatch.setenv(BACKEND_ENV, BACKEND_NATIVE)
        with pytest.raises(NativeRenderError) as exc_info:
            to_svg(_FLOW_SRC)
        assert "builder exploded" in str(exc_info.value.__cause__)
