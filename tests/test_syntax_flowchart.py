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
