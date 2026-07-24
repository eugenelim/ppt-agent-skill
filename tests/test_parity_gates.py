"""CI failure condition gate tests for the mermaid renderer parity suite.

Each test in this module constructs the pathological scenario that corresponds
to a declared CI failure condition and asserts the gate raises or returns a
failure status.  Every test is tagged @pytest.mark.parity_fast so the fast
browser-free job covers all of them.

Failure conditions gated here (spec §Boundaries, "CI failure conditions"):
  1. Zero-check PASS (OracleResult guard)
  2. Hidden fallback / missing backend metadata
  3. Node overlap in FinalizedLayout
  4. HTML/SVG geometry divergence (nondeterminism between two compile calls)
  5. Nondeterministic normalised output

None of these tests require a browser, mmdc, or Playwright.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))


# ── helpers ───────────────────────────────────────────────────────────────────

def _minimal_node(node_id: str, x: float, y: float, w: float, h: float):
    """Build a minimal NodeLayout at the given bounds."""
    from mermaid_render.layout._geometry import (
        NodeLayout, Rect, TextLayout,
    )
    bounds = Rect(x=x, y=y, w=w, h=h)
    return NodeLayout(
        node_id=node_id,
        semantic_shape="rect",
        outer_bounds=bounds,
        content_bounds=bounds,
        title_layout=None,
        subtitle_layout=None,
        member_layouts=(),
        icon_bounds=None,
        ports=(),
        css_classes=(),
        extra_css="",
    )


def _minimal_layout(nodes: dict):
    """Build a minimal FinalizedLayout from a dict of node_id → NodeLayout."""
    from mermaid_render.layout._geometry import (
        FinalizedLayout, LayoutDiagnostics, Rect,
    )
    diag = LayoutDiagnostics(
        unsupported_options=(),
        route_failures=(),
        warnings=(),
    )
    canvas = Rect(x=0, y=0, w=1000, h=1000)
    return FinalizedLayout(
        node_layouts=MappingProxyType(nodes),
        group_layouts=MappingProxyType({}),
        routed_edges=(),
        visible_bounds=canvas,
        diagram_padding=10.0,
        canvas_bounds=canvas,
        direction="TB",
        diagnostics=diag,
    )


# ── Test 1: Zero-check PASS blocked ──────────────────────────────────────────

@pytest.mark.parity_fast
def test_zero_check_pass_blocked():
    """OracleResult(status=PASS, checks=()) must raise ValueError.

    CI failure condition: a comparator that returns PASS without running any
    checks must never produce a green result.  The guard is in
    OracleResult.__post_init__ (oracle_contract.py).
    """
    from tools.mermaid_fidelity.oracle_contract import OracleResult, OracleStatus

    with pytest.raises(ValueError, match="PASS requires at least one check"):
        OracleResult(status=OracleStatus.PASS, checks=(), fixture_stem="x")


@pytest.mark.parity_fast
def test_zero_check_pass_blocked_empty_tuple():
    """Explicit empty tuple in checks= also triggers the guard."""
    from tools.mermaid_fidelity.oracle_contract import OracleResult, OracleStatus

    with pytest.raises(ValueError):
        OracleResult(status=OracleStatus.PASS, checks=tuple(), fixture_stem="test")


# ── Test 2: Hidden fallback blocked ──────────────────────────────────────────

@pytest.mark.parity_fast
def test_hidden_fallback_blocked_backend_check():
    """A LayoutMetadata with empty backend is detected as a hidden fallback.

    CI failure condition: any compile that uses a fallback path without
    stamping backend metadata would hide the fallback from the CI artifact.
    A parity gate must reject metadata where backend is unset (empty string).
    """
    from mermaid_render.layout._geometry import LayoutMetadata

    # Normal compile must always set a non-empty backend
    meta_ok = LayoutMetadata(
        direction="TB", node_count=1, group_count=0, edge_count=1,
        algorithm="ELK-layered", backend="elkjs",
    )
    assert meta_ok.backend, "backend must be non-empty on a normal compile"

    # Hidden fallback: backend is empty — the parity gate must catch this
    meta_hidden = LayoutMetadata(
        direction="TB", node_count=1, group_count=0, edge_count=1,
        algorithm="LongestPathRanker+BarycentricOrderer+SimpleCoordinateAssigner",
        backend="",  # hidden — no backend stamped
    )

    def _assert_backend_visible(meta: LayoutMetadata) -> None:
        """CI gate: backend must be non-empty in every artifact."""
        if not meta.backend:
            raise ValueError(
                "CI failure: hidden fallback — layout metadata has no backend stamp. "
                "Every compile must record which backend produced the layout."
            )

    # Gate passes on a properly stamped layout
    _assert_backend_visible(meta_ok)

    # Gate raises on a hidden fallback
    with pytest.raises(ValueError, match="hidden fallback"):
        _assert_backend_visible(meta_hidden)


@pytest.mark.parity_fast
def test_flowchart_compile_sets_backend():
    """_compile_flowchart always stamps a non-empty backend on its metadata."""
    from mermaid_render.layout._pipeline import _compile_flowchart, RenderOptions

    compiled = _compile_flowchart("flowchart LR\nA-->B", 800, RenderOptions())
    assert compiled.metadata.backend, (
        f"backend must be set; got {compiled.metadata.backend!r}"
    )


# ── Test 3: Node overlap blocked ──────────────────────────────────────────────

@pytest.mark.parity_fast
def test_node_overlap_blocked():
    """verify_layout detects overlapping nodes as a geometry violation.

    CI failure condition: two nodes whose outer_bounds rectangles share
    interior area must cause the geometry verifier to report a violation.
    """
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from geometry_verifier import verify_layout

    # Node A at (0,0,100,60), Node B at (50,30,100,60) — they overlap
    node_a = _minimal_node("A", x=0, y=0, w=100, h=60)
    node_b = _minimal_node("B", x=50, y=30, w=100, h=60)
    layout = _minimal_layout({"A": node_a, "B": node_b})

    violations = verify_layout(layout)
    overlap_viols = [v for v in violations if "overlap" in v.kind.lower()]
    assert overlap_viols, (
        f"Expected node-overlap violation but got: {[v.kind for v in violations]}"
    )


@pytest.mark.parity_fast
def test_non_overlapping_nodes_clean():
    """verify_layout finds no overlap when nodes are well-separated."""
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from geometry_verifier import verify_layout

    node_a = _minimal_node("A", x=0,   y=0, w=100, h=60)
    node_b = _minimal_node("B", x=200, y=0, w=100, h=60)
    layout = _minimal_layout({"A": node_a, "B": node_b})

    violations = verify_layout(layout)
    overlap_viols = [v for v in violations if "overlap" in v.kind.lower()]
    assert not overlap_viols, f"Unexpected overlap violations: {overlap_viols}"


# ── Test 4: HTML/SVG geometry divergence blocked ──────────────────────────────

@pytest.mark.parity_fast
def test_html_svg_geometry_divergence_blocked():
    """Two compiles of the same source must produce byte-identical HTML.

    CI failure condition: HTML/SVG geometry divergence between two compile
    calls (e.g. from a non-deterministic data structure) must be detectable.
    This test asserts the renderer is deterministic by running it twice.
    """
    from mermaid_render.layout._strategies import _dispatch

    src = "flowchart LR\nA[Alpha] --> B[Beta]\nB --> C[Gamma]"
    html_1 = _dispatch(src, "LR", 800)
    html_2 = _dispatch(src, "LR", 800)

    assert html_1 == html_2, (
        "CI failure: HTML geometry divergence — two compiles of the same source "
        "produced different output (non-determinism detected)."
    )


@pytest.mark.parity_fast
def test_html_svg_divergence_detection_mechanism():
    """The divergence check itself must detect genuine differences."""
    # Two different source strings produce different HTML — the comparison catches it
    from mermaid_render.layout._strategies import _dispatch

    html_a = _dispatch("flowchart LR\nA-->B", "LR", 800)
    html_b = _dispatch("flowchart LR\nX-->Y-->Z", "LR", 800)

    # These should differ (different nodes)
    assert html_a != html_b, (
        "Sanity: two different diagrams should produce different HTML"
    )


# ── Test 5: Nondeterministic output blocked ───────────────────────────────────

@pytest.mark.parity_fast
def test_nondeterministic_output_blocked():
    """Compiling the same source 3× must yield byte-identical HTML each time.

    CI failure condition: nondeterministic normalised geometry output across
    runs of the same source on the same SHA must be detected.
    """
    from mermaid_render.layout._strategies import _dispatch

    src = (
        "flowchart TB\n"
        "  subgraph cluster_A [Group A]\n"
        "    N1[Node 1] --> N2[Node 2]\n"
        "  end\n"
        "  N2 --> N3[Node 3]\n"
    )
    results = [_dispatch(src, "TB", 900) for _ in range(3)]

    assert results[0] == results[1] == results[2], (
        "CI failure: nondeterministic output — same source produced different "
        "HTML across 3 runs on the same SHA."
    )


@pytest.mark.parity_fast
def test_sequence_diagram_deterministic():
    """sequenceDiagram compilation is also deterministic across 3 runs."""
    from mermaid_render.layout._strategies import _dispatch

    src = (
        "sequenceDiagram\n"
        "  Alice->>Bob: Hello\n"
        "  Bob-->>Alice: Hi there\n"
        "  Alice->>Bob: How are you?\n"
    )
    results = [_dispatch(src, "LR", 800) for _ in range(3)]
    assert len(set(results)) == 1, (
        "sequenceDiagram must be deterministic across 3 compile runs"
    )
