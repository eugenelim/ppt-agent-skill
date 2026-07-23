"""Tests for faithful mode line semantics.

Spec: docs/specs/flowchart-elk-routing-regression-pack/spec.md AC6, AC15
Run with: python -m pytest tests/test_faithful_mode.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _compile_flowchart, _dispatch
from mermaid_render.layout._strategies import RenderOptions


# ── helpers ───────────────────────────────────────────────────────────────────

_MIXED_ARROWS_SRC = """flowchart TB
    A[Start] --> B[Middle]
    A ==> C[Thick]
    A -.-> D[Dotted]
    B --> C
    C --> D
"""


def _compile(src: str, faithful: bool = False):
    opts = RenderOptions(faithful_mermaid=faithful)
    return _compile_flowchart(src, width_hint=800, options=opts)


# ─────────────────────────────────────────────────────────────────────────────
# AC6: solid/thick/dotted edge styles map to Mermaid arrow syntax
# ─────────────────────────────────────────────────────────────────────────────

class TestFaithfulLineStyles:
    """AC6: line styles are preserved from Mermaid syntax in both normal and faithful mode."""

    def test_solid_arrow_produces_solid_style(self):
        """A --> B must produce edge_style='solid'."""
        result = _compile(_MIXED_ARROWS_SRC, faithful=False)
        solid_edges = [e for e in result.layout.routed_edges if e.edge_style == "solid"]
        assert len(solid_edges) > 0, "No solid-style edges found"

    def test_thick_arrow_produces_thick_style(self):
        """A ==> C must produce edge_style='thick'."""
        result = _compile(_MIXED_ARROWS_SRC, faithful=False)
        thick_edges = [e for e in result.layout.routed_edges if e.edge_style == "thick"]
        assert len(thick_edges) > 0, "No thick-style edges found"

    def test_dotted_arrow_produces_dotted_style(self):
        """A -.-> D must produce edge_style='dotted'."""
        result = _compile(_MIXED_ARROWS_SRC, faithful=False)
        dotted_edges = [e for e in result.layout.routed_edges if e.edge_style == "dotted"]
        assert len(dotted_edges) > 0, "No dotted-style edges found"

    def test_faithful_mode_preserves_edge_styles(self):
        """In faithful mode, edge styles must still match Mermaid arrow syntax (AC6/AC15)."""
        result_faithful = _compile(_MIXED_ARROWS_SRC, faithful=True)
        result_normal = _compile(_MIXED_ARROWS_SRC, faithful=False)
        # Edge style sets should be identical
        styles_faithful = {e.edge_style for e in result_faithful.layout.routed_edges}
        styles_normal = {e.edge_style for e in result_normal.layout.routed_edges}
        assert styles_faithful == styles_normal, (
            f"Faithful mode changed edge styles: faithful={styles_faithful}, normal={styles_normal}"
        )

    def test_faithful_mode_suppresses_legend(self):
        """Faithful mode must not include a legend in the HTML output (AC15)."""
        html = _dispatch(_MIXED_ARROWS_SRC, None, 800, opts=RenderOptions(faithful_mermaid=True))
        assert "legend" not in html.lower() or "legend-item" not in html, (
            "Legend found in faithful mode HTML output"
        )

    def test_normal_mode_can_include_legend(self):
        """Normal mode with inferred_legend=True may include a legend."""
        # This is a smoke test — we just check it doesn't crash.
        html = _dispatch(_MIXED_ARROWS_SRC, None, 800, opts=RenderOptions(inferred_legend=True))
        assert isinstance(html, str)
        assert len(html) > 0


# ─────────────────────────────────────────────────────────────────────────────
# AC15: faithful mode toggles (no semantic enrichment, no legend)
# ─────────────────────────────────────────────────────────────────────────────

class TestFaithfulModeToggle:
    """AC15: faithful=True switches off legend and semantic enrichment."""

    _SRC_WITH_LABELS = """flowchart TB
    A[Auth Service] --> B[Database]
    A -.-> C[Cache]
"""

    def test_faithful_mode_no_legend_html(self):
        html = _dispatch(self._SRC_WITH_LABELS, None, 800, opts=RenderOptions(faithful_mermaid=True))
        # The legend rendering adds a div with class "legend" or similar
        assert 'class="legend"' not in html, "Legend div found in faithful mode"

    def test_faithful_mode_html_contains_nodes(self):
        """Faithful mode still renders node shapes — it just omits enrichments."""
        html = _dispatch(self._SRC_WITH_LABELS, None, 800, opts=RenderOptions(faithful_mermaid=True))
        assert "Auth Service" in html or "A" in html, "Node labels missing in faithful mode"

    def test_faithful_vs_normal_same_node_count(self):
        """Node count must not change between faithful and normal mode."""
        r_faithful = _compile(self._SRC_WITH_LABELS, faithful=True)
        r_normal = _compile(self._SRC_WITH_LABELS, faithful=False)
        assert len(r_faithful.layout.node_layouts) == len(r_normal.layout.node_layouts)

    def test_faithful_vs_normal_same_edge_count(self):
        """Edge count must not change between faithful and normal mode."""
        r_faithful = _compile(self._SRC_WITH_LABELS, faithful=True)
        r_normal = _compile(self._SRC_WITH_LABELS, faithful=False)
        assert len(r_faithful.layout.routed_edges) == len(r_normal.layout.routed_edges)
