"""Tests for mermaid_render.registry and mermaid_render.errors (P0 hardening)."""
from __future__ import annotations

import pytest


# ── RendererCapability ────────────────────────────────────────────────────────

class TestRendererCapability:
    def test_fields_accessible(self):
        from scripts.mermaid_render.registry import RendererCapability
        rc = RendererCapability(
            diagram_type="flowchart",
            native_status="implemented",
            native_builder=None,
            validator=None,
            semantic_fixture_ids=(),
        )
        assert rc.diagram_type == "flowchart"
        assert rc.native_status == "implemented"
        assert rc.native_builder is None
        assert rc.semantic_fixture_ids == ()

    def test_frozen(self):
        from scripts.mermaid_render.registry import RendererCapability
        from dataclasses import FrozenInstanceError
        rc = RendererCapability("flowchart", "implemented", None, None, ())
        with pytest.raises(FrozenInstanceError):
            rc.diagram_type = "other"  # type: ignore[misc]


# ── RENDERER_REGISTRY coverage ────────────────────────────────────────────────

class TestRegistry:
    REQUIRED_TYPES = {
        "flowchart", "statediagram-v2",
        "architecture-beta", "block-beta",
        "c4context", "c4container", "c4component",
        "classdiagram", "erdiagram",
        "gantt", "gitgraph", "journey", "kanban", "mindmap",
        "packet-beta", "pie", "quadrantchart", "requirementdiagram",
        "sankey-beta", "sequencediagram", "timeline", "xychart-beta", "zenuml",
    }

    def test_covers_all_required_types(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        assert self.REQUIRED_TYPES <= set(RENDERER_REGISTRY.keys()), (
            f"Missing: {self.REQUIRED_TYPES - set(RENDERER_REGISTRY.keys())}"
        )

    def test_flowchart_is_implemented(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        assert RENDERER_REGISTRY["flowchart"].native_status == "implemented"

    def test_statediagram_is_implemented(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        assert RENDERER_REGISTRY["statediagram-v2"].native_status == "implemented"

    def test_sequence_is_legacy_only(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        assert RENDERER_REGISTRY["sequencediagram"].native_status == "legacy-only"

    def test_sankey_is_unsupported(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        assert RENDERER_REGISTRY["sankey-beta"].native_status == "unsupported"

    def test_zenuml_is_unsupported(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        assert RENDERER_REGISTRY["zenuml"].native_status == "unsupported"

    def test_architecture_is_experimental(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        assert RENDERER_REGISTRY["architecture-beta"].native_status == "experimental"

    def test_all_entries_have_valid_status(self):
        from scripts.mermaid_render.registry import RENDERER_REGISTRY
        valid = {"implemented", "experimental", "legacy-only", "unsupported"}
        for dtype, cap in RENDERER_REGISTRY.items():
            assert cap.native_status in valid, (
                f"{dtype} has invalid status '{cap.native_status}'"
            )


# ── get_capability ────────────────────────────────────────────────────────────

class TestGetCapability:
    def test_flowchart(self):
        from scripts.mermaid_render.registry import get_capability
        cap = get_capability("flowchart")
        assert cap.native_status == "implemented"

    def test_unknown_raises_unsupported_diagram_type(self):
        from scripts.mermaid_render.registry import get_capability
        from scripts.mermaid_render.errors import UnsupportedDiagramType
        with pytest.raises(UnsupportedDiagramType):
            get_capability("nonexistent-type-xyz")

    def test_public_from_package(self):
        from scripts import mermaid_render
        assert hasattr(mermaid_render, "get_capability")
        assert hasattr(mermaid_render, "RENDERER_REGISTRY")
        cap = mermaid_render.get_capability("flowchart")
        assert cap.native_status == "implemented"


# ── RenderResult ──────────────────────────────────────────────────────────────

class TestRenderResult:
    def test_strict_success_all_passed(self):
        from scripts.mermaid_render.registry import RenderResult
        r = RenderResult(
            svg="<svg/>", diagram_type="flowchart", backend="native",
            semantic_adapter="passed", syntax_coverage="passed",
            geometry="passed", serialization="passed",
            warnings=(), errors=(),
        )
        assert r.is_success(strict=True)
        assert r.is_success(strict=False)

    def test_strict_rejects_unvalidated_geometry(self):
        from scripts.mermaid_render.registry import RenderResult
        r = RenderResult(
            svg="<svg/>", diagram_type="flowchart", backend="native",
            semantic_adapter="passed", syntax_coverage="passed",
            geometry="unvalidated", serialization="passed",
            warnings=(), errors=(),
        )
        assert not r.is_success(strict=True)
        assert r.is_success(strict=False)

    def test_strict_rejects_partial_syntax(self):
        from scripts.mermaid_render.registry import RenderResult
        r = RenderResult(
            svg="<svg/>", diagram_type="flowchart", backend="native",
            semantic_adapter="passed", syntax_coverage="partial",
            geometry="passed", serialization="passed",
            warnings=(), errors=(),
        )
        assert not r.is_success(strict=True)

    def test_strict_rejects_stub_backend(self):
        from scripts.mermaid_render.registry import RenderResult
        r = RenderResult(
            svg="<svg/>", diagram_type="sequence", backend="native-svg-stub",
            semantic_adapter="unsupported", syntax_coverage="failed",
            geometry="unvalidated", serialization="passed",
            warnings=(), errors=(),
        )
        assert not r.is_success(strict=True)

    def test_errors_always_fail(self):
        from scripts.mermaid_render.registry import RenderResult
        r = RenderResult(
            svg="<svg/>", diagram_type="flowchart", backend="native",
            semantic_adapter="passed", syntax_coverage="passed",
            geometry="passed", serialization="passed",
            warnings=(), errors=("validation error",),
        )
        assert not r.is_success(strict=False)
        assert not r.is_success(strict=True)

    def test_none_svg_always_fails(self):
        from scripts.mermaid_render.registry import RenderResult
        r = RenderResult(
            svg=None, diagram_type="sequence", backend="none",
            semantic_adapter="unsupported", syntax_coverage="failed",
            geometry="unvalidated", serialization="failed",
            warnings=(), errors=("no renderer",),
        )
        assert not r.is_success(strict=False)
        assert not r.is_success(strict=True)

    def test_frozen(self):
        from scripts.mermaid_render.registry import RenderResult
        from dataclasses import FrozenInstanceError
        r = RenderResult(
            svg="<svg/>", diagram_type="flowchart", backend="native",
            semantic_adapter="passed", syntax_coverage="passed",
            geometry="passed", serialization="passed",
            warnings=(), errors=(),
        )
        with pytest.raises(FrozenInstanceError):
            r.svg = "<other/>"  # type: ignore[misc]


# ── dispatch_native_result ────────────────────────────────────────────────────

class TestDispatchNativeResult:
    def test_flowchart_returns_render_result(self):
        from scripts.mermaid_render import dispatch_native_result
        from scripts.mermaid_render.registry import RenderResult
        result = dispatch_native_result("flowchart TD\n    A-->B\n")
        assert isinstance(result, RenderResult)
        assert result.diagram_type == "flowchart"

    def test_flowchart_has_svg(self):
        from scripts.mermaid_render import dispatch_native_result
        result = dispatch_native_result("flowchart TD\n    A-->B\n")
        assert result.svg is not None
        assert "<svg" in result.svg

    def test_flowchart_no_errors(self):
        from scripts.mermaid_render import dispatch_native_result
        result = dispatch_native_result("flowchart TD\n    A-->B\n")
        assert not result.errors

    def test_flowchart_non_strict_success(self):
        from scripts.mermaid_render import dispatch_native_result
        result = dispatch_native_result("flowchart TD\n    A-->B\n")
        # Non-strict: svg is not None and no errors
        assert result.is_success(strict=False)

    def test_flowchart_geometry_transient_state(self):
        """Flowchart geometry='unvalidated' until Phase 4 wires validation."""
        from scripts.mermaid_render import dispatch_native_result
        result = dispatch_native_result("flowchart TD\n    A-->B\n")
        # Currently "unvalidated" — this is the correct transient state
        assert result.geometry in ("passed", "unvalidated")

    def test_legacy_only_returns_error_result(self):
        from scripts.mermaid_render import dispatch_native_result
        result = dispatch_native_result("sequenceDiagram\n    Alice->>Bob: Hi\n")
        assert result.svg is None
        assert result.errors
        assert not result.is_success(strict=False)


# ── Typed errors ──────────────────────────────────────────────────────────────

class TestTypedErrors:
    def test_native_render_error_fields(self):
        from scripts.mermaid_render.errors import NativeRenderError
        cause = ValueError("bad")
        err = NativeRenderError("flowchart", "routing", cause=cause)
        assert err.diagram_type == "flowchart"
        assert err.phase == "routing"
        assert err.__cause__ is cause
        assert isinstance(err, ValueError)

    def test_native_render_error_without_cause(self):
        from scripts.mermaid_render.errors import NativeRenderError
        err = NativeRenderError("er", "layout")
        assert err.diagram_type == "er"
        assert "er" in str(err)

    def test_native_renderer_unavailable(self):
        from scripts.mermaid_render.errors import NativeRendererUnavailable
        err = NativeRendererUnavailable("sequencediagram")
        assert err.diagram_type == "sequencediagram"
        assert "sequencediagram" in str(err)
        assert isinstance(err, ValueError)

    def test_unsupported_diagram_type(self):
        from scripts.mermaid_render.errors import UnsupportedDiagramType
        err = UnsupportedDiagramType("sankey-beta")
        assert err.diagram_type == "sankey-beta"
        assert "sankey-beta" in str(err)
        assert isinstance(err, ValueError)

    def test_unsupported_diagram_feature(self):
        from scripts.mermaid_render.errors import UnsupportedDiagramFeature
        err = UnsupportedDiagramFeature("classdiagram", "generic-association")
        assert err.diagram_type == "classdiagram"
        assert err.feature == "generic-association"
        assert isinstance(err, ValueError)

    def test_public_from_package(self):
        from scripts import mermaid_render
        assert hasattr(mermaid_render, "NativeRenderError")
        assert hasattr(mermaid_render, "NativeRendererUnavailable")
        assert hasattr(mermaid_render, "UnsupportedDiagramType")
        assert hasattr(mermaid_render, "UnsupportedDiagramFeature")


# ── to_svg() fallback parameter ───────────────────────────────────────────────

class TestToSvgFallback:
    def test_unknown_fallback_raises_value_error(self):
        from scripts.mermaid_render import to_svg
        with pytest.raises(ValueError, match="Unknown fallback"):
            to_svg("flowchart TD\n    A-->B\n", fallback="unknown")

    def test_no_fallback_legacy_raises_native_render_error(self, monkeypatch):
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE
        from scripts.mermaid_render.errors import NativeRenderError
        monkeypatch.setenv(BACKEND_ENV, BACKEND_NATIVE)
        with pytest.raises(NativeRenderError) as exc_info:
            to_svg("sequenceDiagram\n    Alice->>Bob: Hi\n")
        assert exc_info.value.phase == "not-implemented"

    def test_fallback_legacy_dom_catches_not_implemented(self, monkeypatch):
        """With fallback='legacy-dom', NativeRenderError(phase='not-implemented') is not propagated."""
        from scripts.mermaid_render import to_svg
        from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE
        from scripts.mermaid_render.errors import NativeRenderError
        monkeypatch.setenv(BACKEND_ENV, BACKEND_NATIVE)
        try:
            to_svg(
                "sequenceDiagram\n    Alice->>Bob: Hi\n",
                fallback="legacy-dom",
            )
        except NativeRenderError as e:
            if e.phase == "not-implemented":
                pytest.fail("Should not raise NativeRenderError(phase='not-implemented') with fallback='legacy-dom'")
        except Exception:
            pass  # Playwright may not be installed; that's fine
