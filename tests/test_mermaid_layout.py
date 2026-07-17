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

from mermaid_layout import (
    _strip_frontmatter,
    _detect_directive,
    _parse_spec,
    _parse_spec_and_class,
    _parse_graph_source,
    _break_cycles,
    _assign_ranks,
    _minimize_crossings,
    _assign_coordinates,
    _separate_groups_lr,
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

    def test_icon_node_label_uses_title_accent_var(self):
        """Icon nodes also get the title accent color on their label and icon."""
        html = _dispatch("flowchart LR\n  A[DB]:::database", None, 400)
        assert "node-title-fg" in html

    def test_accent_color_not_on_tech_sublabel(self):
        """Tech sub-label (below the title) should use dim color, not accent."""
        html = _dispatch("flowchart LR\n  A[\"Service|Spring Boot\"]", None, 400)
        # tech label uses node-fg-dim
        assert "node-fg-dim" in html


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
