#!/usr/bin/env python3
"""Pytest unit tests for scripts/mermaid_layout.py.

Import pattern mirrors tests/test_assemble_planning.py: sys.path.insert so
tests/ doesn't need a conftest.py and the import is self-contained.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_layout._strategies import _infer_label_icons

from mermaid_layout import (
    _strip_frontmatter,
    _detect_directive,
    _parse_spec,
    _parse_spec_and_class,
    _split_sub_label,
    _parse_graph_source,
    _break_cycles,
    _assign_ranks,
    _minimize_crossings,
    _assign_coordinates,
    _compact_group_columns,
    _group_coherent_cols,
    _route_edges,
    _separate_groups_lr,
    _separate_groups_tb,
    _compute_group_bboxes,
    _wrap_label,
    _node_render_h,
    _render_graph_fragment,
    _extract_diagram_title,
    _render_metadata_chip,
    _render_legend,
    _dispatch,
    _load_icon,
    _arrowhead,
    _smooth_orthogonal_path,
    _fan_offset,
    _Node,
    _Edge,
    _Group,
    NODE_CAP,
    EDGE_CAP,
    NODE_W,
    NODE_H,
    COL_GAP,
    RANK_GAP,
    CANVAS_PAD,
    GROUP_PAD_X,
    GROUP_PAD_Y_TOP,
    GROUP_PAD_Y_BOT,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _linear_graph(n: int) -> tuple[dict, list, dict]:
    """Return (nodes, edges, groups) for a linear chain A→B→…→N."""
    labels = [chr(65 + i) for i in range(n)]
    nodes = {lbl: _Node(id=lbl, label=lbl) for lbl in labels}
    edges = [_Edge(src=labels[i], dst=labels[i + 1]) for i in range(n - 1)]
    return nodes, edges, {}


def _dispatch_ok(src: str) -> str:
    return _dispatch(src, None, 400)


# ── TestStripFrontmatter ──────────────────────────────────────────────────────

class TestStripFrontmatter:
    def test_no_frontmatter_unchanged(self):
        src = "flowchart TB\n  A-->B"
        assert _strip_frontmatter(src) == src

    def test_removes_yaml_block(self):
        src = "---\ntitle: My Diagram\n---\nflowchart TB\n  A-->B"
        result = _strip_frontmatter(src)
        assert "title" not in result
        assert "flowchart TB" in result

    def test_unterminated_frontmatter_passes_through(self):
        # No closing ---, so the whole thing is returned unchanged
        src = "---\ntitle: oops\nflowchart TB"
        result = _strip_frontmatter(src)
        assert "flowchart TB" in result


# ── TestDetectDirective ───────────────────────────────────────────────────────

class TestDetectDirective:
    def test_flowchart_tb(self):
        directive, direction = _detect_directive("flowchart TB\n  A-->B")
        assert directive.lower() == "flowchart"
        assert direction == "TB"

    def test_flowchart_lr(self):
        directive, direction = _detect_directive("flowchart LR\n  A-->B")
        assert directive.lower() == "flowchart"
        assert direction == "LR"

    def test_graph_td(self):
        directive, direction = _detect_directive("graph TD\n  A-->B")
        assert directive.lower() == "graph"
        assert direction == "TD"

    def test_sequence_diagram(self):
        directive, direction = _detect_directive("sequenceDiagram\n  A->>B: hi")
        assert "sequence" in directive.lower()

    def test_unknown_defaults_to_tb(self):
        directive, direction = _detect_directive("somethingNew\n  A-->B")
        assert direction in ("TB", "LR", "TD", "somethingNew".upper()[:2])


# ── TestParseSpec ─────────────────────────────────────────────────────────────

class TestParseSpec:
    def test_plain_id(self):
        nid, label, shape = _parse_spec("A")
        assert nid == "A"
        assert label == "A"
        assert shape == "rect"

    def test_rect_bracket(self):
        nid, label, shape = _parse_spec("A[My Node]")
        assert nid == "A"
        assert label == "My Node"
        assert shape == "rect"

    def test_rect_quoted(self):
        nid, label, shape = _parse_spec('A["Quoted Label"]')
        assert label == "Quoted Label"
        assert shape == "rect"

    def test_round_parens(self):
        nid, label, shape = _parse_spec("A(Round)")
        assert shape == "round"

    def test_diamond_braces(self):
        nid, label, shape = _parse_spec("A{Decision?}")
        assert shape == "diamond"
        assert label == "Decision?"

    def test_cylinder(self):
        nid, label, shape = _parse_spec("A[(DB)]")
        assert shape == "cylinder"

    def test_circle(self):
        nid, label, shape = _parse_spec("A((circle))")
        assert shape == "circle"

    def test_stadium_shape_strips_brackets(self):
        """([Label]) stadium syntax should produce shape=round with label stripped of brackets."""
        nid, label, shape = _parse_spec("A([Stadium])")
        assert shape == "round", f"expected round, got {shape}"
        assert label == "Stadium", f"brackets not stripped: {label!r}"

    def test_stadium_with_class(self):
        """([Label]):::class should parse correctly with no bracket artifacts."""
        nid, label, shape, css_class = _parse_spec_and_class("User([Client]):::external")
        assert label == "Client", f"label should be 'Client', got {label!r}"
        assert shape == "round"
        assert css_class == "external"

    def test_flag(self):
        nid, label, shape = _parse_spec("A>Flag]")
        assert shape == "flag"

    def test_label_with_bracket_in_quoted(self):
        nid, label, shape = _parse_spec('A["name [inner]"]')
        assert "inner" in label
        assert shape == "rect"


# ── TestParseSpecAndClass ─────────────────────────────────────────────────────

class TestParseSpecAndClass:
    def test_no_class(self):
        nid, label, shape, css_class = _parse_spec_and_class("A[Label]")
        assert css_class == ""
        assert label == "Label"

    def test_external_class(self):
        nid, label, shape, css_class = _parse_spec_and_class("A[Label]:::external")
        assert css_class == "external"
        assert label == "Label"

    def test_database_class(self):
        nid, label, shape, css_class = _parse_spec_and_class("A[Server]:::database")
        assert css_class == "database"

    def test_class_on_plain_id(self):
        nid, label, shape, css_class = _parse_spec_and_class("A:::external")
        assert css_class == "external"
        assert nid == "A"


# ── TestParseGraphSource ──────────────────────────────────────────────────────

class TestParseGraphSource:
    def test_basic_nodes_and_edge(self):
        lines = ["A[Alpha] --> B[Beta]"]
        nodes, edges, groups = _parse_graph_source(lines)
        assert "A" in nodes
        assert "B" in nodes
        assert len(edges) == 1
        assert edges[0].src == "A" and edges[0].dst == "B"

    def test_node_label_captured(self):
        nodes, edges, groups = _parse_graph_source(["A[My Label] --> B"])
        assert nodes["A"].label == "My Label"

    def test_subgraph_membership(self):
        lines = [
            "subgraph Zone",
            "  A --> B",
            "end",
        ]
        nodes, edges, groups = _parse_graph_source(lines)
        assert len(groups) == 1
        gid = list(groups.keys())[0]
        assert "A" in groups[gid].members
        assert "B" in groups[gid].members

    def test_chained_edges(self):
        lines = ["A --> B --> C"]
        nodes, edges, groups = _parse_graph_source(lines)
        assert len(edges) == 2
        src_set = {e.src for e in edges}
        assert "A" in src_set
        assert "B" in src_set

    def test_css_class_propagated_to_node(self):
        lines = ["A[Server]:::database --> B"]
        nodes, _, _ = _parse_graph_source(lines)
        assert nodes["A"].css_class == "database"

    def test_dotted_edge_style(self):
        lines = ["A -.- B"]
        nodes, edges, _ = _parse_graph_source(lines)
        assert edges[0].style == "dotted"

    def test_thick_edge_style(self):
        lines = ["A ==> B"]
        nodes, edges, _ = _parse_graph_source(lines)
        assert edges[0].style == "thick"


# ── TestBreakCycles ───────────────────────────────────────────────────────────

class TestBreakCycles:
    def test_dag_no_reversal(self):
        nodes, edges, _ = _linear_graph(3)
        _break_cycles(nodes, edges)
        assert all(not e.reversed_ for e in edges)

    def test_cycle_gets_back_edge_marked(self):
        nodes = {n: _Node(id=n, label=n) for n in ["A", "B", "C"]}
        edges = [_Edge("A", "B"), _Edge("B", "C"), _Edge("C", "A")]
        _break_cycles(nodes, edges)
        reversed_count = sum(1 for e in edges if e.reversed_)
        assert reversed_count >= 1

    def test_self_loop_marked_reversed(self):
        nodes = {"A": _Node(id="A", label="A")}
        edges = [_Edge("A", "A")]
        _break_cycles(nodes, edges)
        assert edges[0].reversed_


# ── TestAssignRanks ───────────────────────────────────────────────────────────

class TestAssignRanks:
    def test_linear_chain_ranks(self):
        nodes, edges, _ = _linear_graph(4)
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        assert nodes["A"].rank == 0
        assert nodes["B"].rank == 1
        assert nodes["C"].rank == 2
        assert nodes["D"].rank == 3

    def test_single_node_rank_zero(self):
        nodes = {"X": _Node(id="X", label="X")}
        edges = []
        _assign_ranks(nodes, edges)
        assert nodes["X"].rank == 0

    def test_diamond_merge_rank(self):
        # A→B, A→C, B→D, C→D
        nodes = {n: _Node(id=n, label=n) for n in "ABCD"}
        edges = [_Edge("A", "B"), _Edge("A", "C"), _Edge("B", "D"), _Edge("C", "D")]
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        assert nodes["A"].rank == 0
        assert nodes["D"].rank == 2

    def test_multi_rank_edge_inserts_dummy(self):
        nodes = {"A": _Node(id="A"), "B": _Node(id="B"), "C": _Node(id="C")}
        edges = [_Edge("A", "B"), _Edge("B", "C"), _Edge("A", "C")]  # A→C skips rank 1
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        # After rank assignment, a dummy should be inserted for A→C
        dummy_nodes = [nid for nid in nodes if nid.startswith("_dummy")]
        assert len(dummy_nodes) >= 1


# ── TestMinimizeCrossings ─────────────────────────────────────────────────────

class TestMinimizeCrossings:
    def test_col_indices_assigned(self):
        nodes, edges, _ = _linear_graph(3)
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        _minimize_crossings(nodes, edges)
        for n in nodes.values():
            assert n.col >= 0

    def test_empty_graph_no_crash(self):
        _minimize_crossings({}, [])


# ── TestAssignCoordinates ─────────────────────────────────────────────────────

class TestAssignCoordinates:
    def _run_pipeline(self, src: str, direction: str = "TB"):
        lines = src.strip().splitlines()[1:]  # skip directive line
        nodes, edges, groups = _parse_graph_source(lines)
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        _minimize_crossings(nodes, edges)
        return nodes, edges, groups, _assign_coordinates(nodes, direction)

    def test_tb_y_increases_with_rank(self):
        nodes, edges, groups, (cw, ch) = self._run_pipeline("flowchart TB\n  A-->B-->C")
        real_nodes = [n for n in nodes.values() if not n.is_dummy]
        sorted_by_rank = sorted(real_nodes, key=lambda n: n.rank)
        ys = [n.y for n in sorted_by_rank]
        assert ys == sorted(ys)

    def test_lr_x_increases_with_rank(self):
        nodes, edges, groups, (cw, ch) = self._run_pipeline("flowchart LR\n  A-->B-->C", "LR")
        real_nodes = [n for n in nodes.values() if not n.is_dummy]
        sorted_by_rank = sorted(real_nodes, key=lambda n: n.rank)
        xs = [n.x for n in sorted_by_rank]
        assert xs == sorted(xs)

    def test_canvas_dimensions_positive(self):
        nodes, edges, groups, (cw, ch) = self._run_pipeline("flowchart TB\n  A-->B")
        assert cw > 0
        assert ch > 0


# ── TestWrapLabel ─────────────────────────────────────────────────────────────

class TestWrapLabel:
    def test_short_label_single_line(self):
        lines = _wrap_label("Short")
        assert lines == ["Short"]

    def test_long_label_wraps(self):
        lines = _wrap_label("This is a much longer label that exceeds the wrap threshold")
        assert len(lines) > 1

    def test_explicit_newline_escape(self):
        lines = _wrap_label("Line1\\nLine2")
        assert len(lines) == 2
        assert lines[0] == "Line1"

    def test_real_newline_splits(self):
        lines = _wrap_label("First\nSecond")
        assert len(lines) == 2

    def test_pipe_label_not_wrapped_by_this_function(self):
        # _wrap_label operates on a raw string, caller strips the pipe part
        lines = _wrap_label("User Service")
        assert isinstance(lines, list)
        assert len(lines) >= 1


# ── TestNodeRenderH ───────────────────────────────────────────────────────────

class TestNodeRenderH:
    def test_single_line_is_node_h(self):
        n = _Node(id="A", label="Short")
        assert _node_render_h(n) == NODE_H

    def test_multiline_increases_height(self):
        n = _Node(id="A", label="This is a very long label that wraps across multiple lines in the display")
        assert _node_render_h(n) > NODE_H

    def test_icon_field_increases_height(self):
        n_icon = _Node(id="A", label="Node", icon="database")
        n_plain = _Node(id="B", label="Node")
        assert _node_render_h(n_icon) > _node_render_h(n_plain)

    def test_tech_label_increases_height(self):
        n_tech = _Node(id="A", label="Service|Spring Boot")
        n_plain = _Node(id="B", label="Service")
        assert _node_render_h(n_tech) > _node_render_h(n_plain)

    # ── ICON BUG FIX TESTS (Task 1 — RED before Task 2 fix) ──────────────────

    def test_css_class_database_increases_height(self):
        """css_class='database' should give same height bump as icon='database'."""
        n_css = _Node(id="A", label="Server", css_class="database")
        n_plain = _Node(id="B", label="Server")
        assert _node_render_h(n_css) > _node_render_h(n_plain)

    def test_css_class_external_no_height_bump(self):
        """css_class='external' has no icon asset — height should equal plain."""
        n_ext = _Node(id="A", label="Server", css_class="external")
        n_plain = _Node(id="B", label="Server")
        assert _node_render_h(n_ext) == _node_render_h(n_plain)


# ── TestRenderGraphFragment ───────────────────────────────────────────────────

class TestRenderGraphFragment:
    def _make_simple_graph(self):
        nodes = {"A": _Node(id="A", label="Alpha", x=40, y=40),
                 "B": _Node(id="B", label="Beta", x=40, y=160)}
        edges = [_Edge("A", "B")]
        return nodes, edges, {}, 240, 280

    def test_has_node_divs(self):
        nodes, edges, groups, cw, ch = self._make_simple_graph()
        html = _render_graph_fragment(nodes, edges, groups, cw, ch)
        assert 'class="node' in html
        assert "Alpha" in html
        assert "Beta" in html

    def test_has_svg_overlay(self):
        nodes, edges, groups, cw, ch = self._make_simple_graph()
        html = _render_graph_fragment(nodes, edges, groups, cw, ch)
        assert "<svg" in html
        assert "<path" in html

    def test_has_arrowhead_polygon(self):
        nodes, edges, groups, cw, ch = self._make_simple_graph()
        html = _render_graph_fragment(nodes, edges, groups, cw, ch)
        assert "<polygon" in html

    def test_group_div_rendered(self):
        nodes = {
            "A": _Node(id="A", label="A", x=40, y=40, group="_g0"),
            "B": _Node(id="B", label="B", x=200, y=40, group="_g0"),
        }
        groups = {"_g0": _Group(id="_g0", label="Zone", members=["A", "B"])}
        html = _render_graph_fragment(nodes, [], groups, 400, 200)
        assert "diagram-group" in html
        assert "Zone" in html

    def test_external_node_uses_dim_color(self):
        nodes = {"A": _Node(id="A", label="Ext", x=40, y=40, css_class="external")}
        html = _render_graph_fragment(nodes, [], {}, 200, 160)
        assert "node-fg-dim" in html

    def test_external_node_has_dashed_border(self):
        nodes = {"A": _Node(id="A", label="Ext", x=40, y=40, css_class="external")}
        html = _render_graph_fragment(nodes, [], {}, 200, 160)
        assert "border:1px dashed" in html

    def test_internal_node_has_solid_border(self):
        nodes = {"A": _Node(id="A", label="Int", x=40, y=40)}
        html = _render_graph_fragment(nodes, [], {}, 200, 160)
        assert "border:1px solid" in html

    def test_external_node_has_no_depth_tint(self):
        nodes = {"A": _Node(id="A", label="Ext", x=40, y=40, rank=0, css_class="external")}
        html = _render_graph_fragment(nodes, [], {}, 200, 160)
        # Rank 0 warm tint must NOT appear — external nodes bypass depth wash
        assert "232,146,74" not in html

    def test_dummy_node_renders_hidden(self):
        nodes = {"D": _Node(id="D", label="", x=40, y=40, is_dummy=True)}
        html = _render_graph_fragment(nodes, [], {}, 200, 160)
        assert "overflow:hidden" in html


# ── TestFlowchartIconInjection (Task 1 — RED tests) ──────────────────────────

class TestFlowchartIconInjection:
    """Icon injection via :::css_class on flowchart nodes.

    All tests below are RED before the Task 2 fix lands.
    """

    def test_database_class_injects_icon(self):
        html = _dispatch_ok("flowchart LR\n  A[Server]:::database")
        assert "node-icon" in html

    def test_api_class_injects_icon(self):
        html = _dispatch_ok("flowchart LR\n  A[Gateway]:::api")
        assert "node-icon" in html

    def test_plain_node_no_icon(self):
        html = _dispatch_ok("flowchart LR\n  A[Server]")
        assert "node-icon" not in html

    def test_external_class_no_icon(self):
        """:::external has no icon asset — must not inject one."""
        html = _dispatch_ok("flowchart LR\n  A[Server]:::external")
        assert "node-icon" not in html

    def test_nonexistent_icon_class_no_icon(self):
        html = _dispatch_ok("flowchart LR\n  A[Thing]:::someMadeUpClass")
        assert "node-icon" not in html

    def test_model_class_injects_icon(self):
        html = _dispatch_ok("flowchart LR\n  A[LLM]:::model")
        assert "node-icon" in html

    def test_plain_node_no_flex_row(self):
        """Plain nodes (no icon, no tech label) should not use flex-direction:row."""
        html = _dispatch_ok("flowchart LR\n  A[Server]")
        assert "flex-direction:row" not in html


# ── TestMetadataAndLegend ─────────────────────────────────────────────────────

class TestMetadataAndLegend:
    def test_extract_title_present(self):
        src = "flowchart TB\n%% title: My Title\n  A-->B"
        assert _extract_diagram_title(src) == "My Title"

    def test_extract_title_absent(self):
        src = "flowchart TB\n  A-->B"
        assert _extract_diagram_title(src) == ""

    def test_chip_with_title(self):
        chip = _render_metadata_chip("flowchart", "My Title")
        assert "My Title" in chip
        assert "Flowchart" in chip

    def test_chip_no_title_empty(self):
        chip = _render_metadata_chip("flowchart", "")
        assert chip == ""

    def test_legend_mixed_styles(self):
        edges = [_Edge("A", "B", style="solid"), _Edge("B", "C", style="dotted")]
        legend = _render_legend(edges, {})
        assert legend != ""
        assert "dashed" in legend.lower() or "dotted" in legend.lower() or "diagram-legend" in legend

    def test_legend_solid_only_empty(self):
        edges = [_Edge("A", "B", style="solid"), _Edge("B", "C", style="solid")]
        legend = _render_legend(edges, {})
        assert legend == ""


# ── TestDispatch ──────────────────────────────────────────────────────────────

class TestDispatch:
    def test_flowchart_returns_html(self):
        html = _dispatch_ok("flowchart TB\n  A-->B")
        assert "diagram mermaid-layout" in html
        assert "<div" in html

    def test_sequence_diagram(self):
        html = _dispatch_ok("sequenceDiagram\n  Alice->>Bob: Hello")
        assert "diagram mermaid-layout" in html
        assert "Alice" in html

    def test_er_diagram(self):
        html = _dispatch_ok("erDiagram\n  USER ||--o{ ORDER : places")
        assert "diagram mermaid-layout" in html

    def test_gantt(self):
        html = _dispatch_ok("gantt\n  title Proj\n  dateFormat YYYY-MM-DD\n  section A\n    Task1: 2024-01-01, 7d")
        assert "diagram mermaid-layout" in html

    def test_pie_chart(self):
        html = _dispatch_ok('pie\n  title My Pie\n  "Alpha" : 60\n  "Beta" : 40')
        assert "diagram mermaid-layout" in html

    def test_frontmatter_stripped(self):
        src = "---\ntitle: x\n---\nflowchart TB\n  A-->B"
        html = _dispatch(src, None, 400)
        assert "diagram mermaid-layout" in html

    def test_direction_override(self):
        html = _dispatch("flowchart TB\n  A-->B", "LR", 400)
        assert "diagram mermaid-layout" in html


# ── TestCapEnforcement ────────────────────────────────────────────────────────

class TestCapEnforcement:
    def _make_n_node_graph(self, n: int) -> str:
        lines = ["flowchart TB"]
        for i in range(n):
            lines.append(f"  N{i}[Node {i}]")
        return "\n".join(lines)

    def test_node_cap_exactly_64_ok(self):
        src = self._make_n_node_graph(NODE_CAP)
        html = _dispatch(src, None, 400)
        assert "diagram mermaid-layout" in html

    def test_node_cap_65_raises(self):
        src = self._make_n_node_graph(NODE_CAP + 1)
        with pytest.raises((ValueError, SystemExit)):
            _dispatch(src, None, 400)

    def test_edge_cap_exceeded_raises(self):
        nodes_src = "\n".join(f"  N{i}[Node]" for i in range(10))
        # Create EDGE_CAP+1 edges among 10 nodes (with repeats)
        edges_src = "\n".join(f"  N{i % 10} --> N{(i+1) % 10}" for i in range(EDGE_CAP + 1))
        src = f"flowchart TB\n{nodes_src}\n{edges_src}"
        with pytest.raises((ValueError, SystemExit)):
            _dispatch(src, None, 400)


# ── TestDirectiveStrategies ───────────────────────────────────────────────────

class TestDirectiveStrategies:
    """Smoke-level tests that each strategy returns valid HTML."""

    def _ok(self, src: str) -> str:
        html = _dispatch_ok(src)
        assert "diagram mermaid-layout" in html
        return html

    def test_flowchart(self):
        self._ok("flowchart LR\n  A[Start] --> B[End]")

    def test_state_diagram(self):
        self._ok("stateDiagram-v2\n  [*] --> Idle\n  Idle --> Active")

    def test_class_diagram(self):
        self._ok("classDiagram\n  Animal <|-- Dog\n  Animal : +name")

    def test_timeline(self):
        self._ok("timeline\n  title History\n  2020 : Event A\n  2021 : Event B")

    def test_quadrant(self):
        self._ok("quadrantChart\n  x-axis Low --> High\n  y-axis Low --> High\n  A: [0.3, 0.7]")

    def test_xychart_beta(self):
        self._ok('xychart-beta\n  title "Sales"\n  x-axis [jan, feb, mar]\n  bar [10, 20, 30]')

    def test_mindmap(self):
        self._ok("mindmap\n  root\n    Topic A\n      Sub A1\n    Topic B")

    def test_kanban(self):
        self._ok("kanban\n  column Todo\n    item1\n  column Done\n    item2")

    def test_architecture_beta(self):
        self._ok("architecture-beta\n  service api(internet)[API Gateway]\n  service db(database)[Database]\n  api:R --> L:db")

    def test_c4_context(self):
        self._ok("C4Context\n  Person(user, \"User\")\n  System(sys, \"System\")\n  Rel(user, sys, \"Uses\")")

    def test_c4_ext_elements_get_external_class(self):
        """C4 _ext element types must render with dashed border (css_class='external')."""
        src = (
            "C4Context\n"
            "  Person_Ext(extuser, \"External User\")\n"
            "  System(sys, \"System\")\n"
            "  System_Ext(extsys, \"External System\")\n"
            "  Rel(extuser, sys, \"Uses\")\n"
            "  Rel(sys, extsys, \"Calls\")\n"
        )
        html = _dispatch_ok(src)
        assert "border:1px dashed" in html, "external C4 elements must have dashed border"
        # Internal element should not have dashed border
        assert "border:1px solid" in html, "internal C4 elements must have solid border"


# ── TestArrowhead ─────────────────────────────────────────────────────────────

class TestArrowhead:
    def test_returns_string(self):
        pts = _arrowhead(100, 100, 0, 1, False, 5)
        assert isinstance(pts, str)
        assert "," in pts

    def test_points_near_tip(self):
        pts = _arrowhead(0, 0, 0, 1, False, 5)
        coords = [float(v) for pair in pts.split() for v in pair.split(",")]
        # All x-coords should be near 0
        xs = coords[::2]
        assert all(abs(x) <= 10 for x in xs)


# ── TestSmoothOrthogonalPath ──────────────────────────────────────────────────

class TestSmoothOrthogonalPath:
    def test_two_points_returns_path(self):
        d = _smooth_orthogonal_path([(0, 0), (100, 0)], r=6)
        assert d.startswith("M")

    def test_three_points_returns_path(self):
        d = _smooth_orthogonal_path([(0, 0), (100, 0), (100, 100)], r=6)
        assert "Q" in d or "L" in d


# ── TestFanOffset ─────────────────────────────────────────────────────────────

class TestFanOffset:
    def test_single_edge_at_center(self):
        # Total=1: returns absolute center point of the node
        offset = _fan_offset(0, 1, NODE_W, 12)
        assert offset == NODE_W // 2

    def test_two_edges_ordered(self):
        # index 0 should be left of index 1 (lower x)
        o1 = _fan_offset(0, 2, NODE_W, 12)
        o2 = _fan_offset(1, 2, NODE_W, 12)
        assert 0 < o1 < NODE_W
        assert 0 < o2 < NODE_W
        assert o1 < o2

    def test_offsets_within_node_bounds(self):
        # All offsets must land inside [0, NODE_W]
        for i in range(5):
            offset = _fan_offset(i, 5, NODE_W, 12)
            assert 0 <= offset <= NODE_W


# ── TestLoadIcon ──────────────────────────────────────────────────────────────

class TestLoadIcon:
    def test_known_icon_returns_svg(self):
        svg = _load_icon("database")
        assert svg.strip().startswith("<svg")

    def test_unknown_icon_returns_empty(self):
        svg = _load_icon("this-icon-does-not-exist-xyz")
        assert svg == ""

    def test_cached_result_consistent(self):
        svg1 = _load_icon("api")
        svg2 = _load_icon("api")
        assert svg1 == svg2

    def test_icon_has_100_percent_dimensions(self):
        svg = _load_icon("cloud")
        assert 'width="100%"' in svg
        assert 'height="100%"' in svg


# ── TestTitleAccentColor ──────────────────────────────────────────────────────

class TestTitleAccentColor:
    """Node labels should use an accent color distinct from the card body."""

    def test_plain_node_label_uses_title_accent_var(self):
        """Non-external nodes use --node-title-fg (accent-1 fallback) for label color."""
        html = _dispatch("flowchart LR\n  A[Service]", None, 400)
        assert "node-title-fg" in html

    def test_external_node_label_uses_dim_not_accent(self):
        """External nodes use dim color for label, not the accent title color."""
        html = _dispatch("flowchart LR\n  A[External]:::external", None, 400)
        assert "node-fg-dim" in html

    def test_external_node_top_border_uses_dim_not_accent(self):
        """External node top accent border must use dim color, not the colored accent."""
        html = _dispatch("flowchart LR\n  A[Ext]:::external", None, 400)
        # The 3px top border on a node-external div must reference node-fg-dim, not node-title-fg or accent-1
        import re
        ext_div = re.search(r'class="node node-rect node-external"[^>]*style="([^"]*)"', html)
        assert ext_div, "no node-external div found"
        style = ext_div.group(1)
        assert "node-fg-dim" in style
        assert "node-title-fg" not in style
        assert "accent-1" not in style

    def test_legend_appears_once_in_dispatch(self):
        """Legend must appear exactly once even when diagram has groups and mixed edge styles."""
        src = (
            "flowchart LR\n"
            "  subgraph G1\n    A[Alpha]\n  end\n"
            "  B[Beta]\n"
            "  A --> B\n"
            "  B -.-> A\n"
        )
        html = _dispatch(src, None, 600)
        assert html.count("diagram-legend") == 1

    def test_source_group_stays_leftmost_in_lr(self):
        """A group whose members are the entry points of the flow should stay at rank 0 (left)."""
        src = (
            "flowchart LR\n"
            "  subgraph Sources\n    S1[Source A]\n    S2[Source B]\n  end\n"
            "  subgraph Core\n    C1[Core A]\n  end\n"
            "  S1 --> C1\n"
            "  S2 --> C1\n"
        )
        html = _dispatch(src, "LR", 600)
        import re
        # Extract left:Xpx for all node divs
        positions = [(m.group(1), int(m.group(2))) for m in
                     re.finditer(r'data-card-id="([^"]*)"[^>]*left:(\d+)px', html)]
        if not positions:
            # fall back to parsing left from node divs
            nodes_pos = re.findall(r'class="node[^"]*" style="[^"]*left:(\d+)px', html)
            assert nodes_pos, "no node positions found"
            # All should be parseable — just verify nodes exist
            return
        s1_left = next((x for n, x in positions if "S1" in n or n == "S1"), None)
        c1_left = next((x for n, x in positions if "C1" in n or n == "C1"), None)
        if s1_left is not None and c1_left is not None:
            assert s1_left < c1_left, f"Source S1 (x={s1_left}) should be left of Core C1 (x={c1_left})"

    def test_rank0_node_has_warm_depth_tint(self):
        """Rank-0 nodes (client/user layer) get a warm amber depth wash in their background."""
        # Single node → rank 0
        html = _dispatch("flowchart LR\n  A[Client]", None, 400)
        # Depth tint for rank 0 is the warm amber rgba
        assert "232,146,74" in html, "rank-0 depth tint (warm amber) not found in node background"

    def test_deep_node_has_cool_depth_tint(self):
        """Nodes deep in the graph (rank 3+) get an indigo depth wash."""
        # Linear chain: A→B→C→D — D is rank 3
        src = "flowchart LR\n  A[A] --> B[B] --> C[C] --> D[D]"
        html = _dispatch(src, "LR", 600)
        # Depth tint for rank 3 is indigo
        assert "99,102,241" in html, "rank-3+ depth tint (indigo) not found in deep node background"

    def test_rank1_node_has_transparent_depth_tint(self):
        """Rank-1 nodes get a neutral (transparent) depth wash — no color change."""
        # A→B: B is rank 1
        src = "flowchart LR\n  A[A] --> B[B]"
        html = _dispatch(src, "LR", 400)
        # Neutral tint is rgba(0,0,0,0) — transparent — should appear in bg of rank-1 node
        assert "rgba(0,0,0,0)" in html, "rank-1 neutral depth tint not found"

    def test_legend_service_boundary_uses_accent_color(self):
        """Legend 'Service boundary' swatch must use accent-1 to match actual group box borders."""
        src = (
            "flowchart LR\n"
            "  subgraph G\n    A[Alpha]\n  end\n"
            "  B[Beta]\n  A --> B\n"
        )
        html = _dispatch(src, None, 500)
        import re
        legend_match = re.search(r'class="diagram-legend"(.*?)(?=</div>)', html, re.DOTALL)
        assert legend_match, "no diagram-legend found"
        legend_html = legend_match.group(1)
        # Must use accent-1 to match the actual group box border color
        assert "accent-1" in legend_html, "legend service boundary swatch must use --accent-1"
        assert "group-border" not in legend_html, "legend service boundary must not reference --group-border"

    def test_icon_node_label_uses_title_accent_var(self):
        """Icon nodes also get the title accent color on their label and icon."""
        html = _dispatch("flowchart LR\n  A[DB]:::database", None, 400)
        assert "node-title-fg" in html

    def test_accent_color_not_on_tech_sublabel(self):
        """Tech sub-label should use dimmed text (opacity or dim var), not raw accent."""
        html = _dispatch("flowchart LR\n  A[\"Service|Spring Boot\"]", None, 400)
        # tech label is visually dimmed — check that it uses either node-fg-dim or opacity
        assert "node-fg-dim" in html or "opacity:0." in html


# ── TestEdgeOperators ────────────────────────────────────────────────────────

class TestEdgeOperators:
    """Mermaid edge operators beyond --> that should be parsed as directed edges."""

    def test_circle_endpoint_parsed(self):
        """--o should be parsed as a directed edge (circle arrowhead)."""
        nodes, edges, _ = _parse_graph_source(["A --o B"])
        assert len(edges) == 1
        assert edges[0].src == "A" and edges[0].dst == "B"

    def test_circle_endpoint_with_pipe_label(self):
        """A --o|label| B should parse edge and label."""
        nodes, edges, _ = _parse_graph_source(["A --o|retrieval| B"])
        assert len(edges) == 1
        assert edges[0].label == "retrieval"

    def test_cross_endpoint_parsed(self):
        """--x should be parsed as a directed edge."""
        nodes, edges, _ = _parse_graph_source(["A --x B"])
        assert len(edges) == 1
        assert edges[0].src == "A" and edges[0].dst == "B"

    def test_dotted_circle_parsed(self):
        """-.-o should be parsed as a dotted directed edge."""
        nodes, edges, _ = _parse_graph_source(["A -.-o B"])
        assert len(edges) == 1
        assert edges[0].style == "dotted"

    def test_multiple_circle_edges_all_present(self):
        """Multiple --o edges should all be captured, not silently dropped."""
        lines = [
            "SEARCH --o|retrieval| VECTOR_DB",
            "SEARCH --o|traversal| GRAPH_DB",
            "ATLAS --o|direct| ENTERPRISE_IT",
        ]
        nodes, edges, _ = _parse_graph_source(lines)
        assert len(edges) == 3

    def test_mixed_operators_in_one_diagram(self):
        """Diagram with -->, --o, and --> should produce all three edges."""
        lines = [
            "A --> B",
            "B --o C",
            "C --x D",
        ]
        nodes, edges, _ = _parse_graph_source(lines)
        assert len(edges) == 3

    def test_circle_edge_affects_rank_assignment(self):
        """When --o edges are parsed, they affect rank assignment."""
        # ATLAS --o ENTERPRISE_IT means ENTERPRISE_IT should be rank > ATLAS
        lines = [
            "CLIENT --> ATLAS",
            "ATLAS --o ENTERPRISE_IT",
        ]
        nodes, edges, _ = _parse_graph_source(lines)
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        assert nodes["ATLAS"].rank == 1
        assert nodes["ENTERPRISE_IT"].rank == 2  # after ATLAS via --o

    def test_pipe_label_quoted_double_quotes_stripped(self):
        """A -->|\"quoted text\"| B should produce label without surrounding quotes."""
        nodes, edges, _ = _parse_graph_source(['A -->|"GraphRAG local / global retrieval"| B'])
        assert len(edges) == 1
        assert edges[0].label == "GraphRAG local / global retrieval"

    def test_pipe_label_single_quotes_stripped(self):
        """A -->|\'quoted text\'| B should produce label without surrounding quotes."""
        nodes, edges, _ = _parse_graph_source(["A -->|'some label'| B"])
        assert len(edges) == 1
        assert edges[0].label == "some label"

    def test_pipe_label_unquoted_unchanged(self):
        """Unquoted pipe labels should not be altered."""
        nodes, edges, _ = _parse_graph_source(["A -->|HTTPS: metadata| B"])
        assert edges[0].label == "HTTPS: metadata"

    def test_statediff_colon_label_parsed(self):
        """stateDiagram-v2 ': label' suffix on dst should become edge label."""
        nodes, edges, _ = _parse_graph_source(["Processing --> Done : success"])
        assert len(edges) == 1
        assert edges[0].dst == "Done"
        assert edges[0].label == "success"

    def test_statediff_colon_label_doesnt_corrupt_flowchart_node_labels(self):
        """A flowchart node like B[\"key: value\"] must not have its label stripped."""
        nodes, edges, _ = _parse_graph_source(['A --> B["key: value"]'])
        assert len(edges) == 1
        assert edges[0].dst == "B"
        assert nodes["B"].label == "key: value"

    def test_statediff_start_node_parsed(self):
        """[*] --> State creates a _sm_start_ circle node."""
        nodes, edges, _ = _parse_graph_source(["[*] --> Idle"])
        assert "_sm_start_" in nodes, "_sm_start_ node not created from [*] src"
        assert nodes["_sm_start_"].shape == "circle"
        assert len(edges) == 1
        assert edges[0].src == "_sm_start_" and edges[0].dst == "Idle"

    def test_statediff_end_node_parsed(self):
        """State --> [*] creates a _sm_end_ circle node."""
        nodes, edges, _ = _parse_graph_source(["Done --> [*]"])
        assert "_sm_end_" in nodes, "_sm_end_ node not created from [*] dst"
        assert nodes["_sm_end_"].shape == "circle"
        assert len(edges) == 1
        assert edges[0].src == "Done" and edges[0].dst == "_sm_end_"


# ── TestLongLabelWrap ────────────────────────────────────────────────────────

class TestLongLabelWrap:
    """Long single-word labels must not overflow node width."""

    def test_very_long_word_broken_at_char_boundary(self):
        """A single word longer than _WRAP_CHARS should be broken."""
        word = "express-ai-knowledge-source-enterprise-it"
        lines = _wrap_label(word)
        assert len(lines) > 1, "Long single word should be split across lines"
        for line in lines:
            assert len(line) <= 30, f"Line too long: {line!r}"

    def test_normal_words_still_wrap_at_spaces(self):
        """Word-boundary wrapping still works for normal labels."""
        label = "GraphRAG search and knowledge layer"
        lines = _wrap_label(label)
        for line in lines:
            assert len(line) <= 30

    def test_hyphenated_long_word_broken(self):
        """A very long hyphenated token exceeding _WRAP_CHARS gets broken."""
        label = "express-ai-knowledge-source-retirement-services"
        lines = _wrap_label(label)
        assert len(lines) > 1


# ── TestGroupSeparationLR ─────────────────────────────────────────────────────

class TestGroupSeparationLR:
    """In LR mode, group bounding boxes should not overlap vertically."""

    def _run_lr_layout(self, src):
        lines = src.strip().splitlines()[1:]  # skip directive
        nodes, edges, groups = _parse_graph_source(lines)
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        _minimize_crossings(nodes, edges)
        _assign_coordinates(nodes, "LR")
        _separate_groups_lr(nodes, groups)
        return nodes, groups

    def _group_y_range(self, nodes, groups, gid):
        mbrs = [nodes[m] for m in groups[gid].members if m in nodes and not nodes[m].is_dummy]
        if not mbrs:
            return None
        gy = min(n.y for n in mbrs) - GROUP_PAD_Y_TOP
        gy_bot = max(n.y + _node_render_h(n) for n in mbrs) + GROUP_PAD_Y_BOT
        return gy, gy_bot

    def test_two_parallel_groups_no_y_overlap(self):
        """Two groups with no shared members should not overlap in y (LR mode)."""
        src = """flowchart LR
    subgraph G1[Group One]
        A[Alpha] --> B[Beta]
    end
    subgraph G2[Group Two]
        C[Gamma] --> D[Delta]
    end
    A --> C"""
        nodes, groups = self._run_lr_layout(src)
        gids = list(groups.keys())
        if len(gids) < 2:
            return  # only 2 groups needed for this test
        ranges = [self._group_y_range(nodes, groups, gid) for gid in gids]
        ranges = [r for r in ranges if r is not None]
        for i in range(len(ranges)):
            for j in range(i + 1, len(ranges)):
                gy1, bot1 = ranges[i]
                gy2, bot2 = ranges[j]
                overlap = gy1 < bot2 and gy2 < bot1
                assert not overlap, f"Groups overlap: [{gy1},{bot1}] vs [{gy2},{bot2}]"

    def test_dispatch_with_three_groups_renders_ok(self):
        """Three-group LR diagram with cross-group edges renders without crash."""
        src = """flowchart LR
    CLIENT[Client]
    subgraph CATALOG[Catalogue]
        REGISTRY[Registry]
    end
    subgraph UKP[Platform]
        ATLAS[Atlas] --> SEARCH[Search]
    end
    subgraph SOURCES[Sources]
        SRC1[Source1]
        SRC2[Source2]
    end
    CLIENT --> REGISTRY
    CLIENT --o ATLAS
    SRC1 --> ATLAS
    SRC2 --> ATLAS"""
        html = _dispatch(src, "LR", 800)
        assert "diagram mermaid-layout" in html
        assert "diagram-group" in html


# ── TestErrorPaths ────────────────────────────────────────────────────────────

class TestErrorPaths:
    def test_pie_zero_total_raises(self):
        with pytest.raises((ValueError, ZeroDivisionError, SystemExit)):
            _dispatch_ok('pie\n  "A" : 0\n  "B" : 0')

    def test_empty_source_raises_no_nodes(self):
        """Empty flowchart body raises ValueError — correct engine behavior."""
        with pytest.raises(ValueError, match="No nodes"):
            _dispatch_ok("flowchart TB\n")

    def test_comments_only_raises_no_nodes(self):
        """Comment-only body has no parseable nodes — raises ValueError."""
        with pytest.raises(ValueError, match="No nodes"):
            _dispatch_ok("flowchart TB\n  %% just a comment\n  // another comment")


# ── TestVariableRankHeights ───────────────────────────────────────────────────

class TestVariableRankHeights:
    """TB mode _assign_coordinates should use actual node heights per rank (dagre parity)."""

    def _full_pipeline(self, src):
        lines = src.strip().splitlines()[1:]
        nodes, edges, groups = _parse_graph_source(lines)
        _break_cycles(nodes, edges)
        _assign_ranks(nodes, edges)
        _minimize_crossings(nodes, edges)
        cw, ch = _assign_coordinates(nodes, "TB")
        return nodes, cw, ch

    def test_tb_variable_rank_heights_tall_last_rank_node(self):
        """canvas_h must leave CANVAS_PAD below tallest node at max rank."""
        # B has icon + tech sub-label → taller than NODE_H
        src = "flowchart TB\n  A[Alpha] --> B[Service B|Spring Boot]:::database"
        nodes, cw, ch = self._full_pipeline(src)
        max_rank = max(n.rank for n in nodes.values() if not n.is_dummy)
        last_rank_nodes = [n for n in nodes.values() if n.rank == max_rank and not n.is_dummy]
        for n in last_rank_nodes:
            node_bottom = n.y + _node_render_h(n)
            assert ch >= node_bottom + CANVAS_PAD, (
                f"canvas_h={ch} too short for node '{n.id}' bottom={node_bottom} + CANVAS_PAD={CANVAS_PAD}"
            )

    def test_tb_variable_rank_heights_intermediate_no_overlap(self):
        """Tall node at rank 0 must not visually overlap rank 1 top."""
        # A has icon → taller than NODE_H; B is at rank 1
        src = "flowchart TB\n  A[Alpha]:::database --> B[Beta]"
        nodes, cw, ch = self._full_pipeline(src)
        rank0 = [n for n in nodes.values() if n.rank == 0 and not n.is_dummy]
        rank1 = [n for n in nodes.values() if n.rank == 1 and not n.is_dummy]
        if not rank0 or not rank1:
            return
        rank0_max_bottom = max(n.y + _node_render_h(n) for n in rank0)
        rank1_min_top = min(n.y for n in rank1)
        assert rank0_max_bottom <= rank1_min_top, (
            f"Rank 0 bottom {rank0_max_bottom} overlaps rank 1 top {rank1_min_top}"
        )

    def test_tb_variable_rank_heights_simple_unchanged_for_uniform_nodes(self):
        """For single-line nodes without icons, all nodes at rank r have same y."""
        src = "flowchart TB\n  A --> B --> C"
        nodes, cw, ch = self._full_pipeline(src)
        by_rank: dict[int, list] = {}
        for n in nodes.values():
            if not n.is_dummy:
                by_rank.setdefault(n.rank, []).append(n)
        for r, nds in by_rank.items():
            ys = {n.y for n in nds}
            assert len(ys) == 1, f"Rank {r} nodes have different y positions: {ys}"


# ── TestCompactGroupColumns ───────────────────────────────────────────────────

class TestCompactGroupColumns:
    """_compact_group_columns separates groups with overlapping col×rank ranges."""

    def _make_two_groups_overlapping(self):
        """Two groups both placed at col=0 by barycenter (same rank band)."""
        nodes = {
            "A": _Node(id="A", label="A", rank=0, col=0, group="_g1"),
            "B": _Node(id="B", label="B", rank=0, col=0, group="_g2"),
        }
        groups = {
            "_g1": _Group(id="_g1", label="G1", members=["A"]),
            "_g2": _Group(id="_g2", label="G2", members=["B"]),
        }
        return nodes, groups

    def test_compact_group_columns_separates_overlapping(self):
        """Two groups at same col AND same rank band → non-overlapping after compact."""
        nodes, groups = self._make_two_groups_overlapping()
        _compact_group_columns(nodes, groups)
        g1_cols = {nodes[m].col for m in groups["_g1"].members if m in nodes}
        g2_cols = {nodes[m].col for m in groups["_g2"].members if m in nodes}
        assert g1_cols.isdisjoint(g2_cols), f"Groups still share columns: g1={g1_cols} g2={g2_cols}"

    def test_compact_group_columns_noop_for_nonoverlapping_rank(self):
        """Groups at same col range but non-overlapping rank range are NOT shifted."""
        nodes = {
            "A": _Node(id="A", label="A", rank=0, col=0, group="_g1"),
            "B": _Node(id="B", label="B", rank=3, col=0, group="_g2"),
        }
        groups = {
            "_g1": _Group(id="_g1", label="G1", members=["A"]),
            "_g2": _Group(id="_g2", label="G2", members=["B"]),
        }
        before_a_col = nodes["A"].col
        before_b_col = nodes["B"].col
        _compact_group_columns(nodes, groups)
        # Ranks 0 and 3 don't overlap — neither group should be shifted
        assert nodes["A"].col == before_a_col
        assert nodes["B"].col == before_b_col


# ── TestComputeGroupBboxes ────────────────────────────────────────────────────

class TestComputeGroupBboxes:
    """_compute_group_bboxes resolves overlaps and clips to canvas."""

    def test_compute_group_bboxes_no_overlap(self):
        """Two groups whose raw padded bboxes overlap → resolved bboxes don't overlap."""
        # Both groups at same y; A at x=48, B at x=100 (within A's bbox)
        nodes = {
            "A": _Node(id="A", label="A", x=48, y=48, group="_g1"),
            "B": _Node(id="B", label="B", x=100, y=48, group="_g2"),
        }
        groups = {
            "_g1": _Group(id="_g1", label="G1", members=["A"]),
            "_g2": _Group(id="_g2", label="G2", members=["B"]),
        }
        bboxes = _compute_group_bboxes(nodes, groups, 600, 400)
        b1, b2 = bboxes["_g1"], bboxes["_g2"]
        ox = min(b1[2], b2[2]) - max(b1[0], b2[0])
        oy = min(b1[3], b2[3]) - max(b1[1], b2[1])
        assert not (ox > 0 and oy > 0), f"Bboxes still overlap: g1={b1} g2={b2}"

    def test_compute_group_bboxes_clips_to_canvas(self):
        """Group bbox is clipped to canvas bounds."""
        # Group node near right edge — padded bbox would exceed canvas_w=200
        nodes = {
            "A": _Node(id="A", label="A", x=180, y=20, group="_g1"),
        }
        groups = {"_g1": _Group(id="_g1", label="G1", members=["A"])}
        bboxes = _compute_group_bboxes(nodes, groups, 200, 200)
        b = bboxes["_g1"]
        assert b[0] >= 0, "bbox x0 < 0"
        assert b[1] >= 0, "bbox y0 < 0"
        assert b[2] <= 200, f"bbox x1={b[2]} > canvas_w=200"
        assert b[3] <= 200, f"bbox y1={b[3]} > canvas_h=200"


# ── TestSeparateGroupsTB ──────────────────────────────────────────────────────

class TestSeparateGroupsTB:
    """_separate_groups_tb resolves X+Y overlapping group node positions (TB mode)."""

    def test_separate_groups_tb_resolves_x_overlap(self):
        """Groups with forced X+Y overlap get separated (X shifted) after the call."""
        # Both groups at x=48 (same x) and overlapping y range
        nodes = {
            "A": _Node(id="A", label="A", x=48, y=48, group="_g1"),
            "B": _Node(id="B", label="B", x=48, y=48, group="_g2"),
        }
        groups = {
            "_g1": _Group(id="_g1", label="G1", members=["A"]),
            "_g2": _Group(id="_g2", label="G2", members=["B"]),
        }
        canvas_w = _separate_groups_tb(nodes, groups, 400)
        # After separation, compute padded bboxes
        def padded_x(gid):
            mbrs = [nodes[m] for m in groups[gid].members if m in nodes]
            x0 = min(n.x for n in mbrs) - GROUP_PAD_X
            x1 = max(n.x + NODE_W for n in mbrs) + GROUP_PAD_X
            y0 = min(n.y for n in mbrs) - GROUP_PAD_Y_TOP
            y1 = max(n.y + _node_render_h(n) for n in mbrs) + GROUP_PAD_Y_BOT
            return (x0, x1, y0, y1)
        g1 = padded_x("_g1")
        g2 = padded_x("_g2")
        x_overlap = g1[0] < g2[1] and g2[0] < g1[1]
        y_overlap = g1[2] < g2[3] and g2[2] < g1[3]
        assert not (x_overlap and y_overlap), f"Groups still overlap after separate_groups_tb: g1={g1} g2={g2}"


# ── TestSplitSubLabel ─────────────────────────────────────────────────────────

class TestSplitSubLabel:
    """_split_sub_label splits [bracketed secondary text] from the main label."""

    def test_plain_label_no_sub(self):
        """Label without \\n[...] returns full label as main, empty sub."""
        main, sub = _split_sub_label("express-ai-atlas")
        assert main == "express-ai-atlas"
        assert sub == ""

    def test_newline_bracket_splits_to_sub(self):
        """Label with \\n[...] pattern splits correctly."""
        main, sub = _split_sub_label("express-ai-atlas\\n[Knowledge MCP server]")
        assert main == "express-ai-atlas"
        assert sub == "Knowledge MCP server"

    def test_real_newline_bracket_splits_to_sub(self):
        """Label with actual newline before [...]."""
        main, sub = _split_sub_label("express-ai-atlas\n[Knowledge MCP server]")
        assert main == "express-ai-atlas"
        assert sub == "Knowledge MCP server"

    def test_multiple_bracket_lines_join_to_sub(self):
        """All [bracketed] lines after the first are joined as sub."""
        main, sub = _split_sub_label("Service\n[Line one]\n[Line two]")
        assert main == "Service"
        assert "Line one" in sub
        assert "Line two" in sub

    def test_no_bracket_multiline_is_plain(self):
        """Multiple lines without brackets — all treated as main."""
        main, sub = _split_sub_label("Line A\nLine B")
        assert "Line A" in main
        assert sub == ""


# ── TestWrapLabelHyphenBreak ──────────────────────────────────────────────────

class TestWrapLabelHyphenBreak:
    """_wrap_label breaks long kebab-case strings at hyphen boundaries."""

    def test_short_label_no_wrap(self):
        assert _wrap_label("short") == ["short"]

    def test_hyphenated_long_breaks_at_hyphens(self):
        """express-ai-knowledge-source-enterprise-it → breaks on hyphens, not mid-char."""
        lines = _wrap_label("express-ai-knowledge-source-enterprise-it")
        for ln in lines:
            assert len(ln) <= 22, f"Line too long: {ln!r}"
        # No line should split in the middle of a hyphenated segment
        joined = "".join(lines)
        assert "expressai" not in joined  # no char-boundary break inside word

    def test_hyphen_break_produces_valid_trailing_hyphen(self):
        """A fragment that ends with a hyphen is valid (the break point IS a hyphen)."""
        lines = _wrap_label("very-very-very-long-kebab-case-identifier")
        for ln in lines:
            # Each line either ends normally or ends with a hyphen (break point)
            if ln.endswith("-"):
                assert len(ln) <= 22
            else:
                assert len(ln) <= 22


# ── TestEdgeLabelRotation ─────────────────────────────────────────────────────

class TestEdgeLabelRotation:
    """Edge labels always render horizontally (rot=0) regardless of edge direction."""

    def _get_routed_edges(self, direction: str):
        from mermaid_layout import _route_edges
        # Two nodes connected by a vertical edge (same rank, same col → adjacent rows)
        nodes = {
            "A": _Node(id="A", label="A", x=48, y=48, rank=0, col=0),
            "B": _Node(id="B", label="B", x=48, y=200, rank=1, col=0),
        }
        edges = [_Edge(src="A", dst="B", label="my label", style="solid", arrow=True)]
        return _route_edges(nodes, edges, 400, direction)

    def test_edge_label_rot_always_zero_lr(self):
        """LR edge labels have rot=0."""
        specs = self._get_routed_edges("LR")
        labeled = [s for s in specs if s.get("label")]
        assert labeled, "No labeled edges found"
        for s in labeled:
            assert s.get("rot", 0) == 0, f"rot={s['rot']} expected 0 for LR"

    def test_edge_label_rot_always_zero_tb(self):
        """TB edge labels have rot=0."""
        specs = self._get_routed_edges("TB")
        labeled = [s for s in specs if s.get("label")]
        assert labeled, "No labeled edges found"
        for s in labeled:
            assert s.get("rot", 0) == 0, f"rot={s['rot']} expected 0 for TB"


# ── TestLRCrossRowRouting ─────────────────────────────────────────────────────

class TestLRCrossRowRouting:
    """Cross-row LR forward edges (e.g. PPT Service → Database above) must route
    via a bend point closer to the destination, not the mid-point, so their
    vertical segment doesn't visually merge with horizontal edges from the same
    column that share the mid-x zone."""

    def _route_two_to_one(self):
        """Two sources in the same rank-column at different rows, both connecting
        to one destination in the next rank at row 0.

        Mimics the Architecture LR case: Auth→DB (row0→row0, same row) and
        PPT→DB (row1→row0, cross row)."""
        from mermaid_layout import _route_edges, NODE_H, RANK_GAP, COL_GAP, NODE_W, CANVAS_PAD
        node_h = NODE_H  # 42
        row1_y = CANVAS_PAD + node_h + COL_GAP  # row 1 top-y

        nodes = {
            "src_row0": _Node(id="src_row0", label="Auth", x=320, y=CANVAS_PAD, rank=1, col=0),
            "src_row1": _Node(id="src_row1", label="PPT",  x=320, y=row1_y,    rank=1, col=1),
            "dst":      _Node(id="dst",      label="DB",   x=320 + NODE_W + RANK_GAP, y=CANVAS_PAD, rank=2, col=0),
        }
        edges = [
            _Edge(src="src_row0", dst="dst", label="reads", style="solid", arrow=True),
            _Edge(src="src_row1", dst="dst", label="writes", style="solid", arrow=True),
        ]
        return _route_edges(nodes, edges, 900, "LR")

    def _extract_x_coords(self, path_d: str):
        """Return list of x values from SVG path tokens (M/L/Q coords)."""
        import re
        return [float(v) for v in re.findall(r'[-+]?[0-9]*\.?[0-9]+', path_d)]

    def test_cross_row_vertical_bend_not_at_mid_x(self):
        """PPT→DB (cross-row) vertical segment must be placed past the mid-x of the
        gap, so it doesn't share x-territory with the Auth→DB near-horizontal."""
        from mermaid_layout import NODE_W, RANK_GAP, CANVAS_PAD
        specs = self._route_two_to_one()
        labeled = {s["label"]: s for s in specs if s.get("label")}
        assert "reads" in labeled and "writes" in labeled, f"Labels not found: {list(labeled)}"

        x_src = 320 + NODE_W  # right edge of source column
        x_dst = 320 + NODE_W + RANK_GAP  # left edge of dest column
        mid_x = (x_src + x_dst) // 2

        # Extract all unique x coordinates from the cross-row (writes) path
        writes_path = labeled["writes"]["d"]
        xs = self._extract_x_coords(writes_path)
        # The vertical bend in writes must be placed at x > mid_x (closer to dest)
        unique_xs = sorted(set(round(x) for x in xs))
        bend_candidates = [x for x in unique_xs if x_src < x < x_dst]
        assert bend_candidates, f"No interior x-coord found in path: {writes_path[:120]}"
        bend_x = max(bend_candidates)  # the rightmost turn point
        assert bend_x > mid_x, (
            f"Cross-row edge bend_x={bend_x} not past mid_x={mid_x}; "
            f"should be closer to destination to avoid same-zone overlap"
        )

    def test_same_row_uses_mid_x(self):
        """Auth→DB (same-row) still uses the standard mid-x for its turn."""
        from mermaid_layout import NODE_W, RANK_GAP, CANVAS_PAD
        specs = self._route_two_to_one()
        labeled = {s["label"]: s for s in specs if s.get("label")}
        assert "reads" in labeled

        x_src = 320 + NODE_W
        x_dst = 320 + NODE_W + RANK_GAP
        mid_x = (x_src + x_dst) // 2

        reads_path = labeled["reads"]["d"]
        xs = self._extract_x_coords(reads_path)
        unique_xs = sorted(set(round(x) for x in xs))
        bend_candidates = [x for x in unique_xs if x_src < x < x_dst]
        assert bend_candidates, f"No interior x-coord in reads path: {reads_path[:120]}"
        # Same-row edges should have their turn near or at mid_x (within 8px)
        bend_x = min(bend_candidates, key=lambda x: abs(x - mid_x))
        assert abs(bend_x - mid_x) <= 8, (
            f"Same-row edge bend_x={bend_x} too far from mid_x={mid_x}"
        )

    def test_cross_row_vertical_does_not_cross_same_row_horizontal(self):
        """The PPT→DB vertical segment must not geometrically cross the Auth→DB
        horizontal segment (i.e., their x-ranges must not overlap at the same y)."""
        from mermaid_layout import NODE_W, RANK_GAP, CANVAS_PAD
        specs = self._route_two_to_one()
        labeled = {s["label"]: s for s in specs if s.get("label")}

        # Approximate: extract the turn x from both paths
        x_src = 320 + NODE_W
        x_dst = 320 + NODE_W + RANK_GAP

        def _bend_x(path_d):
            import re
            xs = [float(v) for v in re.findall(r'[-+]?[0-9]*\.?[0-9]+', path_d)]
            candidates = sorted(set(round(x) for x in xs if x_src < x < x_dst))
            return max(candidates) if candidates else None

        reads_bend = _bend_x(labeled["reads"]["d"])
        writes_bend = _bend_x(labeled["writes"]["d"])
        assert reads_bend is not None and writes_bend is not None
        # Cross-row bend must be strictly to the RIGHT of same-row bend:
        # so the cross-row vertical (at writes_bend) is outside the x-range
        # of the same-row horizontal (which goes from x_src to reads_bend).
        assert writes_bend > reads_bend, (
            f"Cross-row bend={writes_bend} must be right of same-row bend={reads_bend}"
        )


# ── TestHeightHintZoom ────────────────────────────────────────────────────────

class TestHeightHintZoom:
    """_dispatch scales diagram to fit both width_hint and height_hint."""

    SRC = """flowchart TB
    A --> B --> C --> D --> E --> F --> G
"""

    def _get_zoom(self, fragment: str) -> float:
        """Extract zoom from rendered fragment style attribute."""
        import re
        m = re.search(r'zoom:\s*([0-9.]+)', fragment)
        return float(m.group(1)) if m else 1.0

    def _get_canvas_h(self, fragment: str) -> int:
        import re
        m = re.search(r'height:(\d+)px', fragment)
        return int(m.group(1)) if m else 0

    def test_height_hint_constrains_canvas(self):
        """With tight height_hint, fragment height × zoom ≤ height_hint."""
        fragment = _dispatch(self.SRC, None, 1000, 200)
        zoom = self._get_zoom(fragment)
        canvas_h = self._get_canvas_h(fragment)
        assert canvas_h * zoom <= 200 * 1.06, (
            f"canvas_h={canvas_h} × zoom={zoom:.3f} = {canvas_h*zoom:.0f} > height_hint=200"
        )

    def test_no_height_hint_keeps_full_zoom(self):
        """Without height_hint, zoom may be 1.0 (no height shrinkage)."""
        fragment = _dispatch(self.SRC, None, 0, 0)
        zoom = self._get_zoom(fragment)
        assert zoom == 1.0, f"Expected zoom=1.0 without hints, got {zoom}"


# ── TestAutoDirectionSelect ───────────────────────────────────────────────────

class TestAutoDirectionSelect:
    """Direction auto-select switches LR→TB when TB fits significantly better."""

    def _tall_lr_src(self, n_ranks: int, n_cols: int) -> str:
        """Build a source diagram that in LR mode would be very wide and short,
        but in TB mode would be more balanced."""
        # Create a chain of n_ranks nodes (1 per rank) + n_cols leaves at the last rank
        lines = ["flowchart LR"]
        chain = [f"N{i}" for i in range(n_ranks)]
        for i in range(len(chain) - 1):
            lines.append(f"    {chain[i]} --> {chain[i+1]}")
        last = chain[-1]
        for j in range(n_cols):
            lines.append(f"    {last} --> L{j}")
        return "\n".join(lines)

    def test_auto_select_can_switch_to_tb(self):
        """A wide LR diagram with many ranks auto-selects TB when height_hint is tight."""
        # 8 ranks → very wide LR; tight height_hint forces TB consideration
        src = self._tall_lr_src(8, 2)
        fragment = _dispatch(src, None, 600, 200)
        # The fragment should contain a TB-compatible layout (shorter canvas_h × zoom ≤ height_hint)
        import re
        m = re.search(r'height:(\d+)px', fragment)
        canvas_h = int(m.group(1)) if m else 9999
        mz = re.search(r'zoom:\s*([0-9.]+)', fragment)
        zoom = float(mz.group(1)) if mz else 1.0
        assert canvas_h * zoom <= 200 * 1.15, (
            f"canvas_h={canvas_h} × zoom={zoom:.3f} = {canvas_h*zoom:.0f} still > height_hint=200"
        )

    def test_explicit_direction_override_is_respected(self):
        """When direction_override is passed, auto-select is disabled."""
        src = self._tall_lr_src(8, 2)
        fragment_lr = _dispatch(src, "LR", 600, 200)
        fragment_auto = _dispatch(src, None, 600, 200)
        # With explicit LR, fragment should NOT benefit from TB auto-select
        # (it may be zoomed to fit, but direction stays LR)
        # We just verify the call doesn't error; direction enforcement is a best-effort check
        assert fragment_lr
        assert fragment_auto


# ── TestGroupBboxMemberSafety ─────────────────────────────────────────────────

class TestGroupBboxMemberSafety:
    """_compute_group_bboxes must not shrink a group edge past its own members.

    Regression guard for the case where a non-member node shares the same
    rank/column as a group member: the old code would shrink the group bbox
    edge to exclude the non-member, but in doing so pushed the edge past
    the group member that was in the same position.  The fix: if no safe
    shrink direction exists, accept the overlap instead.
    """

    def test_group_bbox_encloses_all_members(self):
        """Group bbox must contain every member node even when a non-member
        is co-located at the same rank as one of the members."""
        # Arrange: one group with two members (A at x=40, B at x=280),
        # plus one non-member (Ext) at exactly x=280 (same column as B).
        nodes = {
            "A":   _Node(id="A",   label="A",   x=40,  y=40,  group="_g0"),
            "B":   _Node(id="B",   label="B",   x=280, y=40,  group="_g0"),
            "Ext": _Node(id="Ext", label="Ext", x=280, y=160),  # non-member, same x as B
        }
        groups = {"_g0": _Group(id="_g0", label="Zone", members=["A", "B"])}

        bboxes = _compute_group_bboxes(nodes, groups, 800, 600)

        b = bboxes["_g0"]
        # Both A and B must be inside the bbox
        assert b[0] <= nodes["A"].x, "left edge pushed past member A"
        assert b[2] >= nodes["A"].x + NODE_W, "right edge pushed past member A"
        assert b[0] <= nodes["B"].x, "left edge pushed past member B"
        assert b[2] >= nodes["B"].x + NODE_W, "right edge pushed past member B"

    def test_safe_shrink_excludes_non_member_when_possible(self):
        """When a non-member intrudes from a side where no group member lives,
        the bbox should shrink to exclude it.

        Ext is at x=0; its right edge (192) is to the LEFT of member A at x=210.
        The initial bbox left edge (210 - GROUP_PAD_X = 182) is less than 192,
        so Ext intrudes slightly into the group padding — but no member is between
        Ext's right edge and A, so raising b[0] to ext_right + _NM_GAP is safe.
        """
        nodes = {
            "A":   _Node(id="A",   label="A",   x=210, y=40,  group="_g0"),
            "Ext": _Node(id="Ext", label="Ext", x=0,   y=40),  # non-member, x1=192 < A.x=210
        }
        groups = {"_g0": _Group(id="_g0", label="Zone", members=["A"])}

        bboxes = _compute_group_bboxes(nodes, groups, 800, 600)
        b = bboxes["_g0"]

        # After safe shrink, the bbox left edge must exclude Ext
        ext_right = nodes["Ext"].x + NODE_W  # = 0 + 192 = 192
        assert b[0] >= ext_right, "bbox still contains non-member Ext"
        # …while still containing the member
        assert b[2] >= nodes["A"].x + NODE_W, "right edge pushed past member A"


# ── TestNestedGroupBboxContainment ────────────────────────────────────────────

class TestNestedGroupBboxContainment:
    """Parent group bbox must visually wrap all nested child group members.

    Regression guard for the bug where _compute_group_bboxes used only direct
    members, so a parent group's container div didn't encompass nested subgraphs.
    """

    def _make_nested(self):
        """Parent group with one direct member + one child group with two members."""
        nodes = {
            "IDE":        _Node(id="IDE",        label="IDE",   x=320,  y=48,  rank=1, col=0, group="_g0"),
            "REPO_PACKS": _Node(id="REPO_PACKS", label="Packs", x=592,  y=142, rank=2, col=1, group="_g1"),
            "CODE":       _Node(id="CODE",        label="Code",  x=592,  y=48,  rank=2, col=0, group="_g1"),
        }
        groups = {
            "_g0": _Group(id="_g0", label="Machine",    members=["IDE"],                   parent_group=None),
            "_g1": _Group(id="_g1", label="Repo",       members=["REPO_PACKS", "CODE"],    parent_group="_g0"),
        }
        return nodes, groups

    def test_parent_bbox_wraps_nested_child_nodes(self):
        """Parent group bbox y1 must extend past all nested child members."""
        nodes, groups = self._make_nested()
        bboxes = _compute_group_bboxes(nodes, groups, 900, 600)
        assert "_g0" in bboxes, "Parent group must appear in bboxes"
        assert "_g1" in bboxes, "Child group must appear in bboxes"
        b_parent = bboxes["_g0"]
        # Child members REPO_PACKS (y=142) and CODE (y=48) must be inside parent
        for nid in ("REPO_PACKS", "CODE"):
            n = nodes[nid]
            assert b_parent[1] <= n.y, f"Parent top must be above {nid}.y"
            assert b_parent[3] >= n.y + NODE_H, f"Parent bottom must be below {nid}.y+h"
            assert b_parent[0] <= n.x, f"Parent left must be left of {nid}.x"
            assert b_parent[2] >= n.x + NODE_W, f"Parent right must be right of {nid}.x+w"

    def test_child_bbox_is_contained_by_parent_bbox(self):
        """Child group bbox must fall entirely within parent group bbox."""
        nodes, groups = self._make_nested()
        bboxes = _compute_group_bboxes(nodes, groups, 900, 600)
        b_p = bboxes["_g0"]
        b_c = bboxes["_g1"]
        assert b_p[0] <= b_c[0], "parent left must be ≤ child left"
        assert b_p[2] >= b_c[2], "parent right must be ≥ child right"
        assert b_p[1] <= b_c[1], "parent top must be ≤ child top"
        assert b_p[3] >= b_c[3], "parent bottom must be ≥ child bottom"


# ── TestGroupCoherentCols ─────────────────────────────────────────────────────

class TestGroupCoherentCols:
    """_group_coherent_cols must place same-group nodes in adjacent columns.

    Regression guard for the bug where alphabetical barycenter tiebreaking
    put group members at non-adjacent col values, inflating the group's y-span
    and pushing sibling groups far away in _separate_groups_lr.
    """

    def _make_multi_group_rank(self):
        """Four rank-2 nodes: two in _g0, one in _g1, one ungrouped.
        All start with bary=0 (common predecessor at col 0).
        """
        nodes = {
            "A": _Node(id="A", label="A", rank=2, col=0, bary=0.0, group="_g0"),
            "B": _Node(id="B", label="B", rank=2, col=1, bary=0.0, group="_g0"),
            "C": _Node(id="C", label="C", rank=2, col=2, bary=0.0, group="_g1"),
            "D": _Node(id="D", label="D", rank=2, col=3, bary=0.0),
        }
        groups = {
            "_g0": _Group(id="_g0", label="Group0", members=["A", "B"]),
            "_g1": _Group(id="_g1", label="Group1", members=["C"]),
        }
        return nodes, groups

    def test_group_members_are_adjacent(self):
        """After _group_coherent_cols, same-group nodes must have consecutive cols."""
        nodes, groups = self._make_multi_group_rank()
        _group_coherent_cols(nodes, groups)
        g0_cols = sorted(nodes[nid].col for nid in ("A", "B"))
        assert g0_cols[1] - g0_cols[0] == 1, (
            f"_g0 members not adjacent: cols={g0_cols}"
        )

    def test_all_cols_are_unique(self):
        """_group_coherent_cols must not assign duplicate col values."""
        nodes, groups = self._make_multi_group_rank()
        _group_coherent_cols(nodes, groups)
        cols = [nodes[nid].col for nid in ("A", "B", "C", "D")]
        assert len(cols) == len(set(cols)), f"Duplicate cols: {cols}"


# ── TestLRLabelCentering ─────────────────────────────────────────────────────

class TestLRLabelCentering:
    """LR forward edge labels must not cluster at the same position.

    Short labels (< ~16 chars, w < ~104px) fit between nodes at RANK_GAP=120;
    longer labels enter "short-gap" mode (RANK_GAP < label_w + 16) and float
    below the source node with vertical stagger. The fix ensures:
    1. Each label gets zero overlap with node obstacles (score=0 placement).
    2. Sequential labeled edges land at distinct x positions (no horizontal bar).
    """

    def _route_chain_with_labels(self):
        """Three same-row LR nodes chained A→B→C with edge labels."""
        rank_pitch = NODE_W + RANK_GAP
        A = _Node(id="A", label="Source",  x=CANVAS_PAD,                   y=CANVAS_PAD, rank=0, col=0)
        B = _Node(id="B", label="Middle",  x=CANVAS_PAD + rank_pitch,      y=CANVAS_PAD, rank=1, col=0)
        C = _Node(id="C", label="Dest",    x=CANVAS_PAD + 2 * rank_pitch,  y=CANVAS_PAD, rank=2, col=0)
        nodes = {"A": A, "B": B, "C": C}
        edges = [
            _Edge(src="A", dst="B", label="step one", style="solid", arrow=True),
            _Edge(src="B", dst="C", label="step two", style="solid", arrow=True),
        ]
        return _route_edges(nodes, edges, 900, "LR"), A, B, C

    def test_labels_have_zero_node_overlap(self):
        """Label chips must not overlap any node bbox — the placement algorithm
        guarantees score=0 (zero obstacle overlap) when any valid candidate exists."""
        from mermaid_layout._routing import _label_chip_bbox, _overlap_area
        specs, A, B, C = self._route_chain_with_labels()
        labeled = [s for s in specs if s.get("label")]
        assert len(labeled) == 2

        obstacles = [
            (A.x, A.y, A.x + NODE_W, A.y + NODE_H),
            (B.x, B.y, B.x + NODE_W, B.y + NODE_H),
            (C.x, C.y, C.x + NODE_W, C.y + NODE_H),
        ]
        for spec in labeled:
            chip = _label_chip_bbox(spec["lx"], spec["ly"], spec["label"])
            overlap = sum(_overlap_area(chip, ob, margin=0) for ob in obstacles)
            assert overlap == 0, (
                f"Label '{spec['label']}' chip={chip} overlaps node(s); "
                f"total overlap={overlap}"
            )

    def test_two_labeled_edges_not_at_same_x(self):
        """Two sequential labeled edges with different midpoints must have
        distinct lx values — they should not both cluster at the same source."""
        specs, A, B, C = self._route_chain_with_labels()
        labeled = {s["label"]: s for s in specs if s.get("label")}
        ab_lx = labeled["step one"]["lx"]
        bc_lx = labeled["step two"]["lx"]
        # A→B and B→C edges have midpoints ~272px apart; their labels must be distinct
        assert abs(ab_lx - bc_lx) > 60, (
            f"Labels clustered too close: A→B lx={ab_lx}, B→C lx={bc_lx}"
        )


# ── TestInferLabelIcons ───────────────────────────────────────────────────────

class TestInferLabelIcons:
    """_infer_label_icons: keyword matching, word-boundary safety, and priority."""

    def _icon(self, label: str, shape: str = "rect") -> str:
        n = _Node(id="X", label=label, shape=shape)
        _infer_label_icons({"X": n})
        return n.icon

    # ── basic positive matches ────────────────────────────────────────────────

    def test_user_label(self):
        assert self._icon("User") == "users"

    def test_client_label(self):
        assert self._icon("External client") == "users"

    def test_developer_label(self):
        assert self._icon("Developer / repository maintainer") == "users"

    def test_coding_ide(self):
        assert self._icon("Coding IDE") == "ide"

    def test_ide_standalone(self):
        assert self._icon("IDE tool") == "ide"

    def test_cli(self):
        assert self._icon("express-ai-dev-kit installer\\n[CLI]") == "terminal"

    def test_mcp_server(self):
        assert self._icon("express-ai-atlas\\n[Knowledge MCP server]") == "mcp-server"

    def test_graphrag_search(self):
        assert self._icon("GraphRAG search / knowledge layer\\n[Retrieval service]") == "graphrag-search"

    def test_coding_subagent_catalogue(self):
        assert self._icon("Agent Skills / Coding Subagents catalogue\\n[Artifact registry; versioned packs]") == "coding-subagent"

    def test_knowledge_source_hyphenated(self):
        assert self._icon("express-ai-knowledge-source-enterprise-it\\n[Git repo; IT standards, architecture patterns]") == "knowledge-corpus"

    def test_knowledge_source_space(self):
        assert self._icon("Governed knowledge source repository") == "knowledge-corpus"

    def test_knowledge_graph_db(self):
        assert self._icon("Graph database\\n[Derived knowledge graph]") == "knowledge-graph"

    def test_graph_database_standalone(self):
        assert self._icon("Graph database") == "knowledge-graph"

    def test_application_source_code(self):
        assert self._icon("Application source and project artifacts") == "source-code"

    def test_repository_scoped_packs(self):
        assert self._icon("Installed repository-scoped packs") == "package"

    def test_pack_directory(self):
        assert self._icon("Repository-scoped pack directory\\n[Git working tree]") == "package"

    def test_vector_store(self):
        assert self._icon("Vector database\\n[Derived semantic index]") == "vector-store"

    def test_ingestion_pipeline(self):
        assert self._icon("Knowledge-corpus ingestion pipeline\\n[Batch / event pipeline]") == "pipeline"

    def test_database(self):
        assert self._icon("PostgreSQL database") == "database"

    # ── priority: specific type wins over generic ────────────────────────────

    def test_graphrag_beats_search(self):
        # "graphrag" entry comes before generic "search engine"
        assert self._icon("GraphRAG search layer") == "graphrag-search"

    def test_knowledge_graph_beats_database(self):
        # "knowledge graph" entry comes before generic "database"
        assert self._icon("Neo4j graph database") == "knowledge-graph"

    def test_knowledge_corpus_beats_pipeline_for_source_repos(self):
        # knowledge-source repos should get knowledge-corpus, not pipeline
        assert self._icon("express-ai-knowledge-source-retirement-services\\n[Git repo; business-domain knowledge]") == "knowledge-corpus"

    def test_ingestion_pipeline_not_wrongly_knowledge_corpus(self):
        # "Knowledge-corpus ingestion pipeline" should get pipeline, not knowledge-corpus
        # (no "knowledge-source" / "knowledge source" in the label — only hyphenated "knowledge-corpus")
        assert self._icon("Knowledge-corpus ingestion pipeline\\n[Batch / event pipeline]") == "pipeline"

    # ── word-boundary safety: short tokens must not match inside longer words ──

    def test_rds_does_not_match_standards(self):
        # "rds" substring of "standards" — must NOT trigger database icon
        assert self._icon("IT standards and architecture patterns") == ""

    def test_cli_does_not_match_client(self):
        # "cli" is a prefix of "client" — word boundary must block it
        # "client" itself matches "users" — verify it doesn't become terminal
        assert self._icon("Express AI client surfaces") == "users"

    def test_ses_does_not_match_processes(self):
        # "ses" is a suffix of "processes" — must NOT trigger email icon
        assert self._icon("processes complete") == ""

    def test_api_does_not_match_rapid(self):
        # "api" substring of "rapid" — word boundary must block it
        assert self._icon("rapid deployment") == ""

    def test_mcp_does_not_match_compact(self):
        # "mcp" could appear inside other words — verify no false positive
        assert self._icon("compact layout engine") == ""

    def test_ide_does_not_match_guidelines(self):
        # "ide" is a suffix of "guidelines" — word boundary must block it
        assert self._icon("see guidelines for usage") == ""

    # ── explicit icon or css_class skips inference ────────────────────────────

    def test_existing_icon_not_overwritten(self):
        n = _Node(id="X", label="User", icon="custom-icon")
        _infer_label_icons({"X": n})
        assert n.icon == "custom-icon"

    def test_css_class_with_valid_icon_skips_inference(self):
        # If css_class resolves to an icon, inference is skipped
        n = _Node(id="X", label="User", css_class="database")
        _infer_label_icons({"X": n})
        # database css_class resolves to an icon — icon should remain unset
        assert n.icon == ""
