"""T8b — Integration verification for mermaid-unified-layout-pipeline.

Spec: docs/specs/mermaid-unified-layout-pipeline/spec.md
AC-IR-3: each entry point calls _compile_flowchart exactly once.
Graph-topology fixtures produce valid (no-overlap) layouts under strict=True.
Non-graph-topology fixtures produce non-empty SVG output.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ── path setup ────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / "tests" / "fidelity" / "adapters"))

_FIXTURE_DIR = _ROOT / "tests" / "fixtures"


# ── helpers ───────────────────────────────────────────────────────────────────

def _src(name: str) -> str:
    return (_FIXTURE_DIR / f"{name}.mmd").read_text()


# ── AC-FIX-1: graph-topology fixtures → strict layout validation passes ───────

_GRAPH_FIXTURES = [
    "flowchart-all-shapes",
    "flowchart-arrows-defs",
    "flowchart-diamond-branch",
    "flowchart-diamond-clipping",
    "flowchart-empty-subgraph",
    "flowchart-groups-complex",
    "flowchart-inner-direction",
    "flowchart-parallel-links",
    "statediagram-complex",
    "statediagram-nested",
]


@pytest.mark.parametrize("fixture_name", _GRAPH_FIXTURES)
def test_graph_fixture_no_overlap(fixture_name: str) -> None:
    """Each graph-topology fixture has no node-node overlap and no containment violations (strict=True)."""
    from mermaid_render.layout._geometry import validate_finalized_layout
    from mermaid_render.layout._strategies import _compile_flowchart

    compiled = _compile_flowchart(_src(fixture_name), width_hint=0, options=None)
    result = validate_finalized_layout(compiled.layout, strict=True)

    assert result.geometry == "pass", (
        f"{fixture_name}: geometry errors — {list(result.errors)}"
    )
    assert result.structural_geometry == "pass", (
        f"{fixture_name}: containment violations — "
        f"{[e for e in result.errors if 'outside parent group' in e]}"
    )
    assert len(compiled.layout.node_layouts) > 0, (
        f"{fixture_name}: produced no node layouts"
    )


# ── AC-FIX-2: non-graph-topology fixtures → produce non-empty SVG ─────────────

_NON_GRAPH_FIXTURES = [
    "architecture-complex",
    "class-relationships-all",
    "er-cardinality-all",
    "er-ecommerce",
    "requirement-basic",
]


@pytest.mark.parametrize("fixture_name", _NON_GRAPH_FIXTURES)
def test_non_graph_fixture_produces_output(fixture_name: str) -> None:
    """Each non-graph-topology fixture renders non-empty SVG with at least one semantic entity."""
    import mermaid_render
    from native_svg import _extract_semantic_from_svg

    svg = mermaid_render.to_svg(_src(fixture_name), experimental=True)
    assert svg and len(svg) > 100, (
        f"{fixture_name}: to_svg returned empty or too-short output"
    )
    semantic = _extract_semantic_from_svg(svg, fixture_name)
    assert semantic is not None and len(semantic.entities) >= 1, (
        f"{fixture_name}: expected >= 1 semantic entity, got "
        f"{len(semantic.entities) if semantic else 'None'}"
    )


# ── AC-IR-3: entry points call _compile_flowchart exactly once ────────────────

def test_each_entry_point_calls_compile_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """to_html() and to_svg() each call _compile_flowchart exactly once."""
    import mermaid_render
    import mermaid_render.layout._strategies as strats

    real_compile = strats._compile_flowchart

    def counting_compile(src, width_hint, options, **kw):
        return real_compile(src, width_hint, options, **kw)

    monkeypatch.delenv("MERMAID_RENDER_SVG_BACKEND", raising=False)

    src = "flowchart TD\n  A --> B --> C"

    with patch.object(strats, "_compile_flowchart", side_effect=counting_compile) as mock:
        mermaid_render.to_html(src)
        html_count = mock.call_count
        mock.reset_mock()
        mermaid_render.to_svg(src)
        svg_count = mock.call_count

    assert html_count == 1, (
        f"to_html() called _compile_flowchart {html_count} times (expected 1)"
    )
    assert svg_count == 1, (
        f"to_svg() called _compile_flowchart {svg_count} times (expected 1)"
    )
