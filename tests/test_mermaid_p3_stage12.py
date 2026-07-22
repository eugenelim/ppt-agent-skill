"""Tests for Mermaid P3 Stage 12: infra (theme tokens, sizing, to_html wiring, to_png native path).

Task A: to_html frontmatter stripping + validate sequence geometry
Task B: _tokens_from_theme + theme threaded into finalized_layout_to_scene
Task C: _natural_size
Task D: to_png rasterizes native SVG; raises for unsupported types
"""
from __future__ import annotations

import re
import sys
import os

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[1] / "scripts"))


FLOWCHART_SRC = "flowchart TD\n  A --> B"
FLOWCHART_WITH_FM = "---\ntitle: Test\n---\nflowchart TD\n  A --> B"
SEQ_SRC = "sequenceDiagram\nA->>B: hi\n"


# ── Task A: to_html wiring ────────────────────────────────────────────────────

def test_to_html_strips_frontmatter():
    """to_html produces output even when source includes a YAML frontmatter block."""
    import mermaid_render
    html = mermaid_render.to_html(FLOWCHART_WITH_FM)
    assert "<html" in html
    assert "data-node-id" in html


def test_to_html_identical_with_and_without_frontmatter():
    """to_html with frontmatter-prefixed source produces the same fragment as without."""
    import mermaid_render
    html_plain = mermaid_render.to_html(FLOWCHART_SRC)
    html_fm = mermaid_render.to_html(FLOWCHART_WITH_FM)
    # Strip whitespace differences around the fragment body
    assert html_plain.strip() == html_fm.strip()


# ── Task A: validate sequence geometry ───────────────────────────────────────

def test_validate_sequence_geometry_not_unvalidated():
    """validate() must run geometry checks for sequenceDiagram (not return 'unvalidated')."""
    import mermaid_render
    result = mermaid_render.validate(SEQ_SRC)
    assert result.geometry != "unvalidated", (
        f"Expected sequence geometry to be validated, got {result.geometry!r}"
    )


def test_validate_sequence_geometry_passed():
    """A well-formed sequenceDiagram with one message should pass geometry."""
    import mermaid_render
    result = mermaid_render.validate(SEQ_SRC)
    assert result.geometry in ("pass", "passed"), (
        f"Expected 'pass' geometry for simple sequence, got {result.geometry!r}"
    )


# ── Task B: theme token resolution ────────────────────────────────────────────

def test_tokens_from_theme_dark_differs_from_light():
    """_tokens_from_theme('adaptive-dark') must return different node_fill than 'adaptive-light'."""
    from mermaid_render.paint import _tokens_from_theme
    dark = _tokens_from_theme("adaptive-dark")
    light = _tokens_from_theme("adaptive-light")
    assert dark.node_fill != light.node_fill, (
        f"Expected different node_fill: dark={dark.node_fill!r}, light={light.node_fill!r}"
    )


def test_tokens_from_theme_none_returns_defaults():
    """_tokens_from_theme(None) returns the default tokens."""
    from mermaid_render.paint import _tokens_from_theme, _DEFAULT_TOKENS
    tokens = _tokens_from_theme(None)
    assert tokens is _DEFAULT_TOKENS


def test_tokens_from_theme_dark_bg():
    """Dark theme bg should be darker than the default white."""
    from mermaid_render.paint import _tokens_from_theme
    dark = _tokens_from_theme("adaptive-dark")
    assert dark.bg != "#ffffff", f"Dark theme bg should not be white, got {dark.bg!r}"


@pytest.mark.parametrize("theme", ["adaptive-dark", "dark"])
def test_to_svg_dark_theme_produces_different_fill(theme):
    """to_svg with dark theme embeds different fill colors than with light theme."""
    import mermaid_render
    svg_dark = mermaid_render.to_svg(FLOWCHART_SRC, theme=theme)
    svg_light = mermaid_render.to_svg(FLOWCHART_SRC, theme="adaptive-light")
    # node_fill differs between themes — look for fill= attributes
    fills_dark = set(re.findall(r'fill="([^"]+)"', svg_dark))
    fills_light = set(re.findall(r'fill="([^"]+)"', svg_light))
    assert fills_dark != fills_light, (
        f"Dark and light SVG have identical fill colors: {fills_dark}"
    )


# ── Task C: _natural_size ────────────────────────────────────────────────────

def test_natural_size_returns_view_box_dimensions():
    """_natural_size returns the (w, h) from the scene's view_box."""
    from mermaid_render.scene import SvgScene
    from mermaid_render.paint import _natural_size
    scene = SvgScene.make_empty("test-id", "flowchart", width=800.0, height=600.0)
    w, h = _natural_size(scene)
    assert w == 800.0
    assert h == 600.0


def test_svg_width_matches_view_box():
    """SVG width= attribute in to_svg output matches the scene view_box width."""
    import mermaid_render
    svg = mermaid_render.to_svg(FLOWCHART_SRC)
    m = re.search(r'<svg[^>]+width="([^"]+)"', svg)
    assert m is not None, "No width= attribute found on <svg> element"
    svg_width = float(m.group(1))
    vb_m = re.search(r'viewBox="([^"]+)"', svg)
    assert vb_m is not None, "No viewBox attribute found on <svg> element"
    vb_parts = [float(x) for x in vb_m.group(1).split()]
    assert len(vb_parts) == 4
    vb_width = vb_parts[2]
    assert abs(svg_width - vb_width) < 1.0, (
        f"SVG width={svg_width} does not match viewBox width={vb_width}"
    )


# ── Task D: to_png native SVG path ───────────────────────────────────────────

def test_to_png_returns_bytes():
    """to_png returns PNG bytes for a supported diagram type."""
    import mermaid_render
    result = mermaid_render.to_png(FLOWCHART_SRC)
    assert isinstance(result, bytes)
    assert len(result) > 100, "PNG output is suspiciously small"
    assert result[:4] == b"\x89PNG", "Output is not a PNG file"


def test_to_png_raises_for_unsupported_type():
    """to_png raises for diagram types that are not supported."""
    import mermaid_render
    from mermaid_render import UnsupportedDiagramType
    with pytest.raises((UnsupportedDiagramType, ValueError, Exception)) as exc_info:
        mermaid_render.to_png("sankey-beta\n  A,B,10")
    # Must not silently return empty bytes
    assert exc_info.value is not None
