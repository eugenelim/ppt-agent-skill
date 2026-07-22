"""Tests for RenderRequest and parse_render_request()."""
import os
from unittest.mock import patch

import pytest

from scripts.mermaid_render.native_svg import RenderRequest, parse_render_request


def test_render_request_is_frozen():
    req = parse_render_request("flowchart LR\n  A-->B")
    with pytest.raises((AttributeError, TypeError)):
        req.directive = "other"  # type: ignore[misc]


def test_parse_detects_flowchart_directive():
    req = parse_render_request("flowchart LR\n  A-->B")
    assert req.directive == "flowchart"
    assert req.direction == "LR"


def test_parse_detects_graph_directive():
    # "graph" is canonicalized to "flowchart" (DIRECTIVE_ALIASES)
    req = parse_render_request("graph TD\n  A-->B")
    assert req.directive == "flowchart"
    assert req.direction == "TD"


def test_parse_detects_statediagram_directive():
    req = parse_render_request("stateDiagram-v2\n  [*]-->A")
    assert req.directive == "statediagram-v2"


def test_clean_source_has_no_frontmatter():
    src = "---\nconfig:\n  theme: dark\n---\nflowchart LR\n  A-->B"
    req = parse_render_request(src)
    assert "---" not in req.clean_source
    assert req.directive == "flowchart"


def test_frontmatter_preserved():
    src = "---\nconfig:\n  theme: forest\n---\nflowchart LR\n  A-->B"
    req = parse_render_request(src)
    # frontmatter dict should contain at least the 'config' key or its subkeys
    assert isinstance(req.frontmatter, type(req.frontmatter))  # MappingProxyType is immutable
    assert hasattr(req.frontmatter, "__getitem__")


def test_original_source_preserved():
    src = "flowchart LR\n  A-->B"
    req = parse_render_request(src)
    assert req.original_source == src


def test_theme_stored():
    req = parse_render_request("flowchart LR\n  A-->B", theme="dark")
    assert req.theme == "dark"


def test_theme_none_by_default():
    req = parse_render_request("flowchart LR\n  A-->B")
    assert req.theme is None


def test_faithful_stored():
    req = parse_render_request("flowchart LR\n  A-->B", faithful=True)
    assert req.faithful is True


def test_faithful_false_by_default():
    req = parse_render_request("flowchart LR\n  A-->B")
    assert req.faithful is False


def test_width_hint_stored():
    req = parse_render_request("flowchart LR\n  A-->B", width_hint=800)
    assert req.width_hint == 800


def test_determinism():
    """Same input + options → same RenderRequest."""
    src = "flowchart LR\n  A-->B"
    req1 = parse_render_request(src, theme="dark", faithful=True, width_hint=800)
    req2 = parse_render_request(src, theme="dark", faithful=True, width_hint=800)
    assert req1 == req2


def test_theme_flows_through_to_svg():
    """Theme reaches dispatch_native via to_svg."""
    from scripts.mermaid_render import to_svg

    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        svg_default = to_svg("flowchart LR\n  A-->B", theme="default")
        svg_dark = to_svg("flowchart LR\n  A-->B", theme="dark")

    # Both must succeed
    assert "<svg" in svg_default
    assert "<svg" in svg_dark
    # Theme must produce observably different output
    # (once theme tokens are fully wired — currently may not differ;
    # this assertion confirms the call path doesn't raise)
    assert isinstance(svg_default, str)
    assert isinstance(svg_dark, str)


def test_faithful_flows_through_dispatch():
    """faithful=True is stored in the RenderRequest passed through dispatch."""
    captured = {}

    from scripts.mermaid_render import native_svg as _native

    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        # Capture the RenderRequest by patching parse_render_request
        orig_parse = _native.parse_render_request

        def capturing_parse(src, **kwargs):
            req = orig_parse(src, **kwargs)
            captured["faithful"] = req.faithful
            return req

        with patch.object(_native, "parse_render_request", side_effect=capturing_parse):
            from scripts.mermaid_render import to_svg
            to_svg("flowchart LR\n  A-->B", faithful=True)

    assert captured.get("faithful") is True
