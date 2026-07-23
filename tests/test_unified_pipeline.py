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


# ── AC: orthogonal routing properties (orthogonal-routing-fixes) ──────────────

def _python_compile(fixture_name: str):
    """Compile a fixture forcing the Python Sugiyama path (no ELK)."""
    import os
    from mermaid_render.layout._strategies import _compile_flowchart
    env = os.environ.copy()
    env["MERMAID_LAYOUT_ENGINE"] = "python"
    old = os.environ.get("MERMAID_LAYOUT_ENGINE")
    os.environ["MERMAID_LAYOUT_ENGINE"] = "python"
    try:
        return _compile_flowchart(_src(fixture_name), width_hint=0, options=None)
    finally:
        if old is None:
            os.environ.pop("MERMAID_LAYOUT_ENGINE", None)
        else:
            os.environ["MERMAID_LAYOUT_ENGINE"] = old


def test_diamond_branch_all_waypoints_orthogonal() -> None:
    """Every waypoint segment in flowchart-diamond-branch is axis-aligned (no diagonals)."""
    compiled = _python_compile("flowchart-diamond-branch")
    for re in compiled.layout.routed_edges:
        wpts = [(round(p.x), round(p.y)) for p in re.waypoints]
        for i in range(len(wpts) - 1):
            dx = wpts[i + 1][0] - wpts[i][0]
            dy = wpts[i + 1][1] - wpts[i][1]
            assert dx == 0 or dy == 0, (
                f"Edge {re.src_node_id}->{re.dst_node_id} segment {i} "
                f"is diagonal: {wpts[i]} -> {wpts[i + 1]}"
            )


def test_diamond_branch_back_edge_local_lane() -> None:
    """Retry→Check back-edge lane stays close to the two nodes, not the global canvas right."""
    compiled = _python_compile("flowchart-diamond-branch")
    nl = compiled.layout.node_layouts
    retry_right = nl["Retry"].outer_bounds.x + nl["Retry"].outer_bounds.w
    check_right = nl["Check"].outer_bounds.x + nl["Check"].outer_bounds.w
    local_bound = max(retry_right, check_right) + 48  # 12 * (4+1) worst-case stagger

    retry_check = next(
        re for re in compiled.layout.routed_edges
        if re.src_node_id == "Retry" and re.dst_node_id == "Check"
    )
    wpts = [(p.x, p.y) for p in retry_check.waypoints]
    max_x = max(p[0] for p in wpts)
    assert max_x <= local_bound, (
        f"Retry→Check back-edge lane x={max_x} exceeds local bound {local_bound}; "
        f"expected route to stay close to the two nodes"
    )


def test_parallel_links_aggregator_near_barycenter() -> None:
    """E (Aggregator) is positioned near the x-barycenter of B, C, D predecessors (±20 px)."""
    compiled = _python_compile("flowchart-parallel-links")
    nl = compiled.layout.node_layouts

    def cx(nid: str) -> float:
        b = nl[nid].outer_bounds
        return b.x + b.w / 2

    barycenter = (cx("B") + cx("C") + cx("D")) / 3
    e_bounds = nl["E"].outer_bounds
    e_center = e_bounds.x + e_bounds.w / 2
    assert abs(e_center - barycenter) <= 20, (
        f"E center x={e_center:.1f} deviates from barycenter {barycenter:.1f} by "
        f"{abs(e_center - barycenter):.1f} px (limit 20 px)"
    )
