#!/usr/bin/env python3
"""Flowchart syntax coverage tests — forms not yet exercised by test_mermaid_layout.py.

Import pattern matches the rest of the test suite: sys.path.insert so
tests/ doesn't need a conftest.py and the import is self-contained.

What IS covered here (gaps from the existing suite):
- flowchart BT / RL and graph TD / graph LR render without error
- A -- text --> B  (mid-label dash-dash arrow)
- A -- text --- B  (mid-label dash-dash open line)
- A -.- B          (dotted open — no arrowhead)
- A & B --> C & D  (combined fan-in + fan-out in one statement)
- subgraph SG / direction LR / … / end  (per-subgraph direction hint)
- classDef <name> …  (silently skipped, no spurious node)
- class <id> <name>  (silently skipped, no spurious node)
- style <id> fill:… (inline node CSS — extra_css field populated)
- Unicode / CJK / Latin-extended node labels render and appear in output

What is NOT duplicated (all covered in test_mermaid_layout.py already):
- flowchart TB / LR render (TestFlowchartIntegrationComplete)
- All 13 node shapes parse (TestParserShapesComplete)
- All node shape CSS (TestNewShapeCSS)
- Solid/dotted/thick edge style (TestParserEdgesComplete)
- -->|text| pipe label (TestParserEdgesComplete.test_edge_label_pipe)
- A --- B open line (TestParserEdgesComplete.test_no_arrow_edge)
- --o / --x endpoints (TestEdgeOperators)
- Chained A --> B --> C (TestParserEdgesComplete.test_chained_edges)
- Fan-out A --> B & C (TestParserEdgesComplete.test_parallel_links_expand)
- Fan-in A & B --> C (TestParserEdgesComplete.test_parallel_fan_in_expands)
- Simple / nested / cross-subgraph (TestParserSubgraphsComplete)
- Subgraph with quoted label (TestParserSubgraphsComplete.test_subgraph_with_quoted_label)
- %% comments (TestParserStateDiagramComplete.test_comment_lines_ignored)
- linkStyle silently skipped (TestLinkStyleIgnored)
- inline style via fixture (TestFlowchartIntegrationComplete.test_inline_styles_render)
- Quoted label "…" stripped (TestParserShapesComplete.test_quoted_label_stripped)
- Markdown bold/italic/strike in labels (TestMarkdownFormattingComplete)
- HTML entities (TestHtmlEntityDecoding)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_layout import _dispatch, _parse_graph_source


# ── helpers ────────────────────────────────────────────────────────────────────

def _render(src: str) -> str:
    """Dispatch mermaid source to HTML fragment, width=400."""
    return _dispatch(src, None, 400)


# ── TestFlowchartDirections ────────────────────────────────────────────────────


class TestFlowchartDirections:
    """flowchart BT / RL and graph TD / graph LR all render without error.

    flowchart TB / LR are already covered by TestFlowchartIntegrationComplete;
    only the uncovered directions are parametrized here.
    """

    @pytest.mark.parametrize("direction", ["BT", "RL"])
    def test_flowchart_direction_renders(self, direction: str) -> None:
        """flowchart <DIR> A --> B renders without exception."""
        src = f"flowchart {direction}\n  A --> B"
        html = _render(src)
        assert "diagram mermaid-layout" in html

    @pytest.mark.parametrize("direction", ["TD", "LR"])
    def test_graph_keyword_renders(self, direction: str) -> None:
        """`graph <DIR>` is accepted as a synonym for `flowchart <DIR>`."""
        src = f"graph {direction}\n  A --> B"
        html = _render(src)
        assert "diagram mermaid-layout" in html

    @pytest.mark.parametrize("direction", ["BT", "RL"])
    def test_flowchart_direction_has_nodes(self, direction: str) -> None:
        """Nodes A and B appear in the rendered HTML for every direction."""
        src = f"flowchart {direction}\n  A[Alpha] --> B[Beta]"
        html = _render(src)
        assert "Alpha" in html
        assert "Beta" in html


# ── TestFlowchartEdgeSyntax ────────────────────────────────────────────────────


class TestFlowchartEdgeSyntax:
    """Edge forms not covered by TestParserEdgesComplete.

    Covered here:
    - A -- text --> B  mid-label + arrow
    - A -- text --- B  mid-label + no arrow
    - A -.- B          dotted open (no arrowhead)
    """

    def _edge(self, src: str):
        """Return first edge from a bare edge line (no header)."""
        _, edges, _ = _parse_graph_source([src])
        assert edges, f"no edge parsed from: {src!r}"
        return edges[0]

    def test_mid_label_arrow_label_extracted(self) -> None:
        """A -- My Text --> B extracts label 'My Text'."""
        e = self._edge("A -- My Text --> B")
        assert e.label == "My Text"

    def test_mid_label_arrow_has_arrowhead(self) -> None:
        """A -- text --> B produces an edge with arrow=True."""
        e = self._edge("A -- text --> B")
        assert e.arrow is True

    def test_mid_label_arrow_style_solid(self) -> None:
        """A -- text --> B is a solid edge."""
        e = self._edge("A -- text --> B")
        assert e.style == "solid"

    def test_mid_label_arrow_endpoints(self) -> None:
        """A -- text --> B connects correct src and dst."""
        e = self._edge("A -- text --> B")
        assert e.src == "A"
        assert e.dst == "B"

    def test_mid_label_open_line_label_extracted(self) -> None:
        """A -- My Text --- B extracts label 'My Text'."""
        e = self._edge("A -- My Text --- B")
        assert e.label == "My Text"

    def test_mid_label_open_line_no_arrow(self) -> None:
        """A -- text --- B produces an edge with arrow=False."""
        e = self._edge("A -- text --- B")
        assert e.arrow is False

    def test_dotted_open_style(self) -> None:
        """A -.- B is a dotted edge."""
        e = self._edge("A -.- B")
        assert e.style == "dotted"

    def test_dotted_open_no_arrow(self) -> None:
        """A -.- B has no arrowhead."""
        e = self._edge("A -.- B")
        assert e.arrow is False

    def test_dotted_open_endpoints(self) -> None:
        """A -.- B connects correct src and dst."""
        e = self._edge("A -.- B")
        assert e.src == "A"
        assert e.dst == "B"

    def test_mid_label_arrow_renders(self) -> None:
        """A -- text --> B renders and label text appears in HTML output."""
        html = _render("flowchart LR\n  A -- hello --> B")
        assert "diagram mermaid-layout" in html
        assert "hello" in html

    def test_dotted_open_renders(self) -> None:
        """A -.- B renders with dashed stroke (no arrowhead polygon marker)."""
        html = _render("flowchart LR\n  A -.- B")
        assert "diagram mermaid-layout" in html
        assert "stroke-dasharray" in html


# ── TestFlowchartParallelEdges ─────────────────────────────────────────────────


class TestFlowchartParallelEdges:
    """A & B --> C & D — combined fan-in and fan-out in one statement.

    Fan-out only (A --> B & C) and fan-in only (A & B --> C) are already
    covered; the combined form is tested here.
    """

    def test_combined_parallel_produces_four_edges(self) -> None:
        """A & B --> C & D expands to exactly 4 edges."""
        _, edges, _ = _parse_graph_source(["A & B --> C & D"])
        assert len(edges) == 4

    def test_combined_parallel_all_pairs(self) -> None:
        """A & B --> C & D covers all (src, dst) combinations."""
        _, edges, _ = _parse_graph_source(["A & B --> C & D"])
        pairs = {(e.src, e.dst) for e in edges}
        assert pairs == {("A", "C"), ("A", "D"), ("B", "C"), ("B", "D")}

    def test_combined_parallel_all_nodes_created(self) -> None:
        """All four nodes A, B, C, D are created."""
        nodes, _, _ = _parse_graph_source(["A & B --> C & D"])
        for nid in ("A", "B", "C", "D"):
            assert nid in nodes, f"node {nid!r} missing"

    def test_combined_parallel_renders(self) -> None:
        """A & B --> C & D renders without error."""
        html = _render("flowchart TD\n  A & B --> C & D")
        assert "diagram mermaid-layout" in html
        for label in ("A", "B", "C", "D"):
            assert label in html


# ── TestFlowchartSubgraphDirection ────────────────────────────────────────────


class TestFlowchartSubgraphDirection:
    """subgraph SG / direction LR / … / end — per-subgraph direction hint.

    The parser does not implement the per-subgraph direction hint; the
    `direction LR` line is treated as a standalone node named `direction`
    but the diagram still renders correctly.  This class documents that
    contract: the diagram must not crash.
    """

    def test_subgraph_with_direction_renders(self) -> None:
        """subgraph with `direction LR` renders without error."""
        src = (
            "flowchart TD\n"
            "  subgraph SG\n"
            "    direction LR\n"
            "    A --> B\n"
            "  end\n"
        )
        html = _render(src)
        assert "diagram mermaid-layout" in html

    def test_subgraph_with_direction_has_real_nodes(self) -> None:
        """Nodes A and B are present in the output despite the direction hint."""
        src = (
            "flowchart TD\n"
            "  subgraph SG\n"
            "    direction LR\n"
            "    A[Alpha] --> B[Beta]\n"
            "  end\n"
        )
        html = _render(src)
        assert "Alpha" in html
        assert "Beta" in html

    def test_subgraph_with_direction_group_created(self) -> None:
        """The subgraph group SG is still created when direction hint is present."""
        lines = [
            "subgraph SG",
            "  direction LR",
            "  A --> B",
            "end",
        ]
        _, _, groups = _parse_graph_source(lines)
        assert any(g.label == "SG" for g in groups.values()), "group SG missing"

    def test_subgraph_with_direction_real_edge_present(self) -> None:
        """The edge A --> B is still created when direction hint is present."""
        lines = [
            "subgraph SG",
            "  direction LR",
            "  A --> B",
            "end",
        ]
        _, edges, _ = _parse_graph_source(lines)
        assert any(e.src == "A" and e.dst == "B" for e in edges), "edge A→B missing"


# ── TestFlowchartStyleDirectives ───────────────────────────────────────────────


class TestFlowchartStyleDirectives:
    """`classDef`, `class <id> <name>`, and `style <id> fill:…` directives.

    classDef and `class` assignment are silently skipped by the parser (no
    spurious nodes).  Inline `style` populates the node's `extra_css` field.
    linkStyle is already covered by TestLinkStyleIgnored.
    """

    def test_classdef_does_not_create_node(self) -> None:
        """`classDef myClass fill:#f9f` must not create a node named 'classDef'."""
        nodes, _, _ = _parse_graph_source([
            "flowchart TD",
            "  A --> B",
            "  classDef myClass fill:#f9f,stroke:#333",
        ])
        assert "classDef" not in nodes
        assert "myClass" not in nodes

    def test_classdef_diagram_still_renders(self) -> None:
        """`classDef` line must not prevent the diagram from rendering."""
        html = _render(
            "flowchart LR\n"
            "  A --> B\n"
            "  classDef highlight fill:#ff9,stroke:#f90\n"
        )
        assert "diagram mermaid-layout" in html

    def test_class_assignment_does_not_create_node(self) -> None:
        """`class A myClass` must not create a spurious 'class' node."""
        nodes, _, _ = _parse_graph_source([
            "flowchart TD",
            "  A --> B",
            "  class A myClass",
        ])
        assert "class" not in nodes

    def test_class_assignment_diagram_still_renders(self) -> None:
        """`class A myClass` line must not prevent the diagram from rendering."""
        html = _render(
            "flowchart LR\n"
            "  A[Alpha] --> B[Beta]\n"
            "  classDef highlight fill:#ff9\n"
            "  class A highlight\n"
        )
        assert "diagram mermaid-layout" in html

    def test_inline_style_sets_extra_css(self) -> None:
        """`style A fill:#f9f,stroke:#333` populates A.extra_css."""
        nodes, _, _ = _parse_graph_source([
            "flowchart TD",
            "  A --> B",
            "  style A fill:#f9f,stroke:#333",
        ])
        assert "A" in nodes
        assert nodes["A"].extra_css == "fill:#f9f,stroke:#333"

    def test_inline_style_does_not_affect_other_nodes(self) -> None:
        """`style A …` must not set extra_css on node B."""
        nodes, _, _ = _parse_graph_source([
            "flowchart TD",
            "  A --> B",
            "  style A fill:#f9f",
        ])
        assert nodes.get("B") is not None
        assert nodes["B"].extra_css == ""

    def test_inline_style_renders_without_error(self) -> None:
        """`style A fill:#f9f` renders without exception."""
        html = _render(
            "flowchart LR\n"
            "  A[Alpha] --> B[Beta]\n"
            "  style A fill:#f9f,stroke:#333\n"
        )
        assert "diagram mermaid-layout" in html

    def test_multiple_inline_styles_all_applied(self) -> None:
        """Multiple `style` directives each set their respective node's extra_css."""
        nodes, _, _ = _parse_graph_source([
            "flowchart TD",
            "  A --> B --> C",
            "  style A fill:#f00",
            "  style B fill:#0f0",
            "  style C fill:#00f",
        ])
        assert nodes["A"].extra_css == "fill:#f00"
        assert nodes["B"].extra_css == "fill:#0f0"
        assert nodes["C"].extra_css == "fill:#00f"


# ── TestFlowchartUnicodeLabels ─────────────────────────────────────────────────


class TestFlowchartUnicodeLabels:
    """Node labels with CJK and Latin-extended characters render correctly."""

    def test_cjk_label_renders(self) -> None:
        """A node with a Japanese label renders without error."""
        html = _render('flowchart LR\n  A["こんにちは"] --> B["世界"]')
        assert "diagram mermaid-layout" in html

    def test_cjk_label_text_in_output(self) -> None:
        """CJK label text appears verbatim in the HTML output."""
        html = _render('flowchart LR\n  A["こんにちは"]')
        assert "こんにちは" in html

    def test_latin_extended_label_renders(self) -> None:
        """A node with Latin-extended characters (accents) renders without error."""
        html = _render('flowchart LR\n  A["Héllo Wörld"] --> B["Ñoño"]')
        assert "diagram mermaid-layout" in html

    def test_latin_extended_label_text_in_output(self) -> None:
        """Latin-extended label text appears verbatim in the HTML output."""
        html = _render('flowchart LR\n  A["Héllo Wörld"]')
        assert "Héllo Wörld" in html

    def test_mixed_unicode_and_edge_renders(self) -> None:
        """A full flowchart with Unicode labels and edges renders without error."""
        src = (
            'flowchart TD\n'
            '  A["データ入力"] --> B["処理"]\n'
            '  B --> C["出力結果"]\n'
        )
        html = _render(src)
        assert "diagram mermaid-layout" in html
        assert "データ入力" in html
        assert "出力結果" in html


# ── TestFlowchartShapeFixes ────────────────────────────────────────────────────


class TestFlowchartShapeFixes:
    """Regression tests for the six flowchart rendering bug fixes.

    Each test verifies one specific fix is in effect:
    1. Trapezoid/trapezoid-alt use parallelogram (same-direction) clip-paths.
    2. Circle node uses a square fixed size (not oval from border-radius:50% on a rect).
    3. Round node has a modest border-radius (not the same full-pill as stadium).
    4. Diamond node uses _DIAMOND_SIZE (not oversized NODE_W).
    5. Self-loop label is placed outside the arc, not inside it.
    6. Empty subgraph renders a visible labeled group box.
    """

    def test_trapezoid_parallelogram_clip_path(self) -> None:
        """[/Trap/] uses same-direction-slant clip-path (parallelogram, 15% offset)."""
        html = _render("flowchart TB\n  A[/Lean/]")
        assert "polygon(15% 0%,100% 0%,85% 100%,0% 100%)" in html

    def test_trapezoid_alt_opposite_parallelogram_clip_path(self) -> None:
        r"""[\Trap\] uses opposite-direction parallelogram clip-path."""
        html = _render("flowchart TB\n  A[\\Lean\\]")
        assert "polygon(0% 0%,85% 0%,100% 100%,15% 100%)" in html

    def test_circle_equal_width_height(self) -> None:
        """((Circle)) node has equal width and height — not oval (square regardless of size)."""
        import re
        html = _render("flowchart TB\n  A((My Circle Node))")
        m = re.search(r'class="node node-circle[^"]*"[^>]*style="[^"]*width:(\d+)px;\s*height:(\d+)px', html)
        assert m, "circle div not found"
        assert m.group(1) == m.group(2), f"circle must be square: width={m.group(1)} height={m.group(2)}"

    def test_circle_not_node_w_wide(self) -> None:
        """((Circle)) div uses dynamic size >= _CIRCLE_NODE_SIZE, not the full NODE_W."""
        import re
        from mermaid_render.layout._constants import _CIRCLE_NODE_SIZE, NODE_W
        assert _CIRCLE_NODE_SIZE < NODE_W, "precondition: _CIRCLE_NODE_SIZE < NODE_W"
        html = _render("flowchart TB\n  A((My Circle Node))")
        m = re.search(r'class="node node-circle[^"]*"[^>]*style="[^"]*width:(\d+)px', html)
        assert m, "circle div not found"
        w = int(m.group(1))
        assert w >= _CIRCLE_NODE_SIZE, f"circle width {w} must be >= _CIRCLE_NODE_SIZE={_CIRCLE_NODE_SIZE}"
        assert w < NODE_W, f"circle width {w} must be < NODE_W={NODE_W}"

    def test_round_border_radius_modest(self) -> None:
        """(Round) node has modest border-radius (14px), not the old 28px pill."""
        html = _render("flowchart TB\n  A(Round Node)")
        assert "border-radius:14px" in html
        assert "border-radius:28px" not in html

    def test_stadium_is_full_pill(self) -> None:
        """([Stadium]) node keeps 50px border-radius (full pill)."""
        html = _render("flowchart TB\n  A([Stadium Node])")
        assert "border-radius:50px" in html

    def test_round_and_stadium_differ(self) -> None:
        """Round and stadium nodes render with visually distinct border-radius values."""
        html_round = _render("flowchart TB\n  A(Round)")
        html_stadium = _render("flowchart TB\n  A([Stadium])")
        # Extract the shape_css portion (simplified: look for the key style values)
        assert "border-radius:14px" in html_round
        assert "border-radius:50px" in html_stadium

    def test_diamond_uses_diamond_size(self) -> None:
        """Diamond node div uses dynamic width >= _DIAMOND_SIZE, not the full NODE_W."""
        import re
        from mermaid_render.layout._constants import _DIAMOND_SIZE, NODE_W
        assert _DIAMOND_SIZE < NODE_W, "precondition: _DIAMOND_SIZE < NODE_W"
        html = _render("flowchart TB\n  A{Decision}")
        m = re.search(r'class="node node-diamond[^"]*"[^>]*style="[^"]*width:(\d+)px', html)
        assert m, "diamond div not found"
        w = int(m.group(1))
        assert w >= _DIAMOND_SIZE, f"diamond width {w} must be >= _DIAMOND_SIZE={_DIAMOND_SIZE}"
        assert w < NODE_W, f"diamond width {w} must be < NODE_W={NODE_W}"

    def test_diamond_svg_uses_diamond_size(self) -> None:
        """Diamond SVG border overlay has width >= _DIAMOND_SIZE, not NODE_W."""
        import re
        from mermaid_render.layout._constants import _DIAMOND_SIZE, NODE_W
        html = _render("flowchart TB\n  A{Decision}")
        m = re.search(r'class="node node-diamond[^"]*".*?width="(\d+)"', html, re.S)
        assert m, "diamond SVG width not found"
        w = int(m.group(1))
        assert w >= _DIAMOND_SIZE, f"diamond SVG width {w} must be >= _DIAMOND_SIZE={_DIAMOND_SIZE}"
        assert w < NODE_W, f"diamond SVG width {w} must be < NODE_W={NODE_W}"

    def test_self_loop_label_outside_arc(self) -> None:
        """Self-loop label x is beyond the arc endpoint, not inside it."""
        from mermaid_render.layout._constants import (
            _Node, SELF_LOOP_DX, NODE_W,
        )
        from mermaid_render.layout._routing import _route_edges, _node_render_w
        from mermaid_render.layout._constants import _Edge

        n = _Node(id="A", label="A", x=100, y=100)
        edges = [_Edge(src="A", dst="A", label="loop label")]
        routed = _route_edges({"A": n}, edges, 800)

        assert len(routed) == 1
        spec = routed[0]
        node_right = n.x + _node_render_w(n)
        arc_end_x = node_right + SELF_LOOP_DX
        assert spec["lx"] >= arc_end_x, (
            f"Self-loop label lx={spec['lx']} is inside arc "
            f"(arc endpoint x={arc_end_x})"
        )

    def test_empty_subgraph_renders_group_container(self) -> None:
        """Empty subgraph renders a visible diagram-group container with its label."""
        html = _render(
            "flowchart TB\n"
            "  subgraph SG[EmptyGroupLabel]\n"
            "  end\n"
            "  A --> B\n"
        )
        assert "EmptyGroupLabel" in html
        assert "diagram-group" in html
        assert "diagram mermaid-layout" in html

    def test_circle_long_label_grows_beyond_base(self) -> None:
        """AC-4: ((long label)) circle diameter is strictly > _CIRCLE_NODE_SIZE."""
        import re
        from mermaid_render.layout._constants import _CIRCLE_NODE_SIZE
        html = _render("flowchart TB\n  A((A Long Circle Label That Exceeds Default))")
        m = re.search(r'class="node node-circle[^"]*"[^>]*style="[^"]*width:(\d+)px', html)
        assert m, "circle div not found"
        w = int(m.group(1))
        assert w > _CIRCLE_NODE_SIZE, (
            f"long-label circle width {w} must grow > _CIRCLE_NODE_SIZE={_CIRCLE_NODE_SIZE}"
        )

    def test_diamond_long_label_grows_beyond_base(self) -> None:
        """AC-5: {{long label}} diamond is strictly > _DIAMOND_SIZE for a wide label."""
        import re
        from mermaid_render.layout._constants import _DIAMOND_SIZE
        html = _render("flowchart TB\n  A{A Very Long Decision Label That Exceeds Default Size}")
        m = re.search(r'class="node node-diamond[^"]*"[^>]*style="[^"]*width:(\d+)px', html)
        assert m, "diamond div not found"
        w = int(m.group(1))
        assert w > _DIAMOND_SIZE, (
            f"long-label diamond width {w} must grow > _DIAMOND_SIZE={_DIAMOND_SIZE}"
        )

    def test_polygon_clip_path_on_background_not_outer(self) -> None:
        """AC-6: outer container has no clip-path; background div has clip-path for all 5 shapes."""
        import re
        shapes = [
            ("flowchart TB\n  A{Decision}", "diamond"),
            ("flowchart TB\n  A{{Hexagon}}", "hexagon"),
            ("flowchart TB\n  A[/Trapezoid/]", "trapezoid"),
            ("flowchart TB\n  A[\\\\Trap-alt\\\\]", "trapezoid-alt"),
            ("flowchart TB\n  A>Flag]", "flag"),
        ]
        for src, shape in shapes:
            html = _render(src)
            # Find the outer container div for this shape
            outer_m = re.search(
                rf'class="node node-{re.escape(shape)}[^"]*"[^>]*style="([^"]*)"',
                html,
            )
            assert outer_m, f"{shape}: outer container div not found"
            outer_style = outer_m.group(1)
            assert "clip-path" not in outer_style, (
                f"{shape}: clip-path must NOT be on outer container; found in: {outer_style!r}"
            )
            # Background div follows immediately and must carry the clip-path
            after_outer = html[outer_m.end():]
            bg_m = re.search(r'<div style="([^"]*)"', after_outer)
            assert bg_m, f"{shape}: background div not found after outer container"
            bg_style = bg_m.group(1)
            assert "clip-path" in bg_style, (
                f"{shape}: clip-path must be on background div; got: {bg_style!r}"
            )


class TestDummyChainRouting:
    """Long-range edges (A→C skipping B) must render as ONE path, not two segments."""

    # arrows-defs fixture: A-->B, A==>C, A-.->D, B-->C, C-->D
    # Dummy nodes are inserted for A→C (rank 0→2) and A→D (rank 0→3).
    # Before fix: each segment renders separately → 3 paths for A→D, 2 for A→C.
    # After fix:  each logical edge renders as ONE path from real src to real dst.

    _SRC = (
        "flowchart TB\n"
        "    A-->B\n"
        "    A==>C\n"
        "    A-.->D\n"
        "    B-->C\n"
        "    C-->D\n"
    )

    def _edge_paths(self, html: str):
        """Return list of (src, dst) tuples for all rendered edge paths."""
        import re
        return re.findall(r'data-src="([^"]+)" data-dst="([^"]+)"', html)

    def test_each_logical_edge_renders_one_path(self) -> None:
        """5 logical edges must produce exactly 5 SVG paths (not 8 with dummy segments)."""
        html = _render(self._SRC)
        edges = self._edge_paths(html)
        assert len(edges) == 5, (
            f"Expected 5 edge paths (one per logical edge), got {len(edges)}: {edges}"
        )

    def test_long_edge_src_dst_are_real_nodes(self) -> None:
        """data-src/data-dst on every edge must be a real node (A/B/C/D), not a dummy."""
        html = _render(self._SRC)
        for src, dst in self._edge_paths(html):
            assert not src.startswith("_dummy_"), f"dummy src in edge: {src}→{dst}"
            assert not dst.startswith("_dummy_"), f"dummy dst in edge: {src}→{dst}"

    def test_long_edge_path_stays_within_canvas(self) -> None:
        """The A→C path must not route to x > canvas_w (no off-canvas dummy swings)."""
        import re
        html = _render(self._SRC)
        canvas_w_m = re.search(r'width:(\d+)px', html)
        canvas_w = int(canvas_w_m.group(1)) if canvas_w_m else 800
        # Collect x coords from all M/L/Q path commands
        all_xs = [float(x) for x in re.findall(r'[ML]\s+([\d.]+)\s+[\d.]+', html)]
        # Allow 5px overshoot for arrowhead tips
        if all_xs:
            assert max(all_xs) <= canvas_w + 5, (
                f"Edge path goes off-canvas: max_x={max(all_xs)}, canvas_w={canvas_w}"
            )

    def test_arrow_defs_correct_edge_count(self) -> None:
        """Full render of arrows-defs fixture produces exactly 5 edge paths."""
        import os
        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "flowchart-arrows-defs.mmd"
        )
        if not os.path.exists(fixture):
            pytest.skip("fixture not found")
        src = open(fixture).read()
        html = _render(src)
        edges = self._edge_paths(html)
        assert len(edges) == 5, (
            f"arrows-defs: expected 5 edge paths, got {len(edges)}: {edges}"
        )
