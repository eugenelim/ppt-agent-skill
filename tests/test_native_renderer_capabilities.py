"""Tests for the native renderer capability registry.

Asserts NativeRendererSpec structure and that FULL/PARTIAL directives
produce real semantic output (not stubs). NOT_IMPLEMENTED and UNSUPPORTED
directives must raise.
"""
import os
from unittest.mock import patch

import pytest

from scripts.mermaid_render.scene import (
    NativeParityLevel,
    NativeRendererSpec,
    NATIVE_RENDERER_REGISTRY,
)
from scripts.mermaid_render.native_svg import NativeRenderError


# ── Registry structure tests ──────────────────────────────────────────────────

def test_native_renderer_spec_is_frozen():
    spec = NativeRendererSpec(directive="test", parity=NativeParityLevel.PARTIAL)
    with pytest.raises((AttributeError, TypeError)):
        spec.directive = "other"  # type: ignore[misc]


def test_registry_contains_known_directives():
    for d in (
        "flowchart", "graph", "statediagram-v2", "statediagram",
        "classdiagram", "timeline", "mindmap",
        "architecture-beta", "c4context", "c4container", "c4component",
    ):
        assert d in NATIVE_RENDERER_REGISTRY, f"Missing directive in registry: {d}"


def test_registry_contains_not_implemented_directives():
    for d in (
        "sequencediagram", "erdiagram", "gantt", "quadrantchart", "pie",
        "xychart-beta", "block-beta", "packet-beta", "kanban", "journey",
        "requirementdiagram", "gitgraph",
    ):
        assert d in NATIVE_RENDERER_REGISTRY, f"Missing directive in registry: {d}"
        assert NATIVE_RENDERER_REGISTRY[d].parity == NativeParityLevel.NOT_IMPLEMENTED, (
            f"Expected {d} to be NOT_IMPLEMENTED, got {NATIVE_RENDERER_REGISTRY[d].parity}"
        )


def test_registry_contains_unsupported_directives():
    assert NATIVE_RENDERER_REGISTRY["sankey-beta"].parity == NativeParityLevel.UNSUPPORTED
    assert NATIVE_RENDERER_REGISTRY["zenuml"].parity == NativeParityLevel.UNSUPPORTED


def test_native_parity_level_has_four_members():
    members = {m.value for m in NativeParityLevel}
    assert "full" in members
    assert "partial" in members
    assert "not-implemented" in members
    assert "unsupported" in members


def test_flowchart_is_partial():
    assert NATIVE_RENDERER_REGISTRY["flowchart"].parity == NativeParityLevel.PARTIAL


def test_classdiagram_is_partial():
    assert NATIVE_RENDERER_REGISTRY["classdiagram"].parity == NativeParityLevel.PARTIAL


# ── PARTIAL directives produce real semantic output ───────────────────────────

_PARTIAL_FIXTURES = [
    ("flowchart", "flowchart LR\n  A[Node A] -->|edge label| B[Node B]"),
    ("graph", "graph TD\n  A --> B\n  B --> C"),
    ("statediagram-v2", "stateDiagram-v2\n  [*] --> Active\n  Active --> [*]"),
    ("classdiagram", "classDiagram\n  class Animal {\n    +name : string\n  }\n  Animal <|-- Dog"),
]


@pytest.mark.parametrize("directive,src", _PARTIAL_FIXTURES)
def test_partial_directive_produces_svg_not_stub(directive, src):
    """PARTIAL directives must produce real SVG output, not a stub."""
    from scripts.mermaid_render import to_svg

    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        result = to_svg(src)

    assert result, f"Empty SVG for {directive}"
    assert "<svg" in result, f"No <svg> tag for {directive}"
    assert "foreignObject" not in result, f"<foreignObject> in {directive} output"
    assert "html" not in result.lower().split("<svg")[0], f"HTML wrapper in {directive} output"


@pytest.mark.parametrize("directive,src", [
    ("flowchart", "flowchart LR\n  A[Alpha] --> B[Beta]"),
    ("graph", "graph TD\n  X[Xray] --> Y[Yankee]"),
])
def test_partial_directive_contains_source_labels(directive, src):
    """Source node labels must appear in the SVG output."""
    from scripts.mermaid_render import to_svg

    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        result = to_svg(src)

    # Each node label should appear in the SVG
    for label in ("Alpha", "Beta") if directive == "flowchart" else ("Xray", "Yankee"):
        assert label in result, f"Label {label!r} missing from {directive} SVG output"


# ── NOT_IMPLEMENTED and UNSUPPORTED directives raise ─────────────────────────

@pytest.mark.parametrize("directive", [
    "sequencediagram", "erdiagram", "gantt", "quadrantchart", "pie",
    "xychart-beta", "block-beta", "packet-beta", "kanban", "journey",
    "requirementdiagram", "gitgraph",
])
def test_not_implemented_directives_raise_native_render_error(directive):
    from scripts.mermaid_render.native_svg import dispatch_native

    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        with pytest.raises(NativeRenderError) as exc_info:
            dispatch_native(f"{directive}\n  content")
    assert exc_info.value.phase == "not-implemented"
    assert directive in exc_info.value.diagram_type


@pytest.mark.parametrize("directive,src", [
    ("sankey-beta", "sankey-beta\n  A,B,10"),
    ("zenuml", "zenuml\n  title Hello"),
])
def test_unsupported_directives_raise(directive, src):
    from scripts.mermaid_render.native_svg import dispatch_native

    with pytest.raises((NativeRenderError, ValueError)):
        dispatch_native(src)


# ── Registry all-coverage: no directive is missing ───────────────────────────

def test_all_known_directives_have_registry_entry():
    from scripts.mermaid_render.layout._constants import _KNOWN_DIRECTIVES

    # These additional directives should also be registered
    registered = set(NATIVE_RENDERER_REGISTRY.keys())
    for d in _KNOWN_DIRECTIVES:
        assert d in registered, (
            f"Directive {d!r} in _KNOWN_DIRECTIVES but missing from NATIVE_RENDERER_REGISTRY"
        )
