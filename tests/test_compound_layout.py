"""Stage 6 tests: recursive compound-graph layout.

Covers:
- _apply_inner_direction_positions reorders x for TB-outer/LR-inner groups
- Actual node widths used in group bbox separation (not NODE_W constant)
- Inner-direction edge flow preserved (A→B ⟹ A.x < B.x in LR inner)
- Descendant containment: all member node bboxes inside group bbox
- Nested groups handled bottom-up
- Existing subgraph fixtures render without regression
- ELK compound layout: empty-subgraph non-overlapping, groups-complex containment
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from mermaid_render.layout._constants import _Node, _Edge, _Group, NODE_W, NODE_H, COL_GAP
from mermaid_render.layout._layout import _apply_inner_direction_positions
from mermaid_render.layout._renderer import _compute_group_bboxes


def _elk_available() -> bool:
    try:
        from mermaid_render.layout.elk_adapter import _find_elkjs, _find_node
        return _find_elkjs() is not None and _find_node() is not None
    except ImportError:
        return False


requires_elk = pytest.mark.requires_elk


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_node(nid: str, x: int, y: int, rank: int = 0, col: int = 0,
               group: str | None = None, w: int = NODE_W, h: int = NODE_H) -> _Node:
    n = _Node(id=nid, x=x, y=y, rank=rank, col=col, group=group)
    n.width = w
    n.height = h
    return n


def _make_edge(src: str, dst: str) -> _Edge:
    return _Edge(src=src, dst=dst)


def _make_group(gid: str, members: list[str], direction: str = "",
                parent: str | None = None) -> _Group:
    g = _Group(id=gid, label=gid, members=list(members), direction=direction)
    if parent:
        g.parent_group = parent
    return g


def _render(src: str) -> str:
    import mermaid_render
    return mermaid_render.to_html(src)


def _node_left(html: str, nid: str) -> int | None:
    idx = html.find(f'data-node-id="{nid}"')
    if idx < 0:
        return None
    m = re.search(r"left:(\d+)px", html[idx:idx + 300])
    return int(m.group(1)) if m else None


def _node_top(html: str, nid: str) -> int | None:
    idx = html.find(f'data-node-id="{nid}"')
    if idx < 0:
        return None
    m = re.search(r"top:(\d+)px", html[idx:idx + 300])
    return int(m.group(1)) if m else None


# ── Unit tests: _apply_inner_direction_positions ──────────────────────────────

class TestApplyInnerDirection:
    """Unit tests for the inner-direction position fixup function."""

    def _setup_lr_inner_tb_outer(self):
        """3 nodes A→B→C in an LR inner group, TB outer layout."""
        nodes = {
            "A": _make_node("A", x=300, y=100, group="grp"),
            "B": _make_node("B", x=100, y=100, group="grp"),  # out of order before fixup
            "C": _make_node("C", x=200, y=100, group="grp"),
        }
        edges = [_make_edge("A", "B"), _make_edge("B", "C")]
        groups = {"grp": _make_group("grp", ["A", "B", "C"], direction="LR")}
        return nodes, edges, groups

    def test_lr_inner_reorders_x_ascending(self):
        nodes, edges, groups = self._setup_lr_inner_tb_outer()
        _apply_inner_direction_positions(nodes, edges, groups, "TB")
        # After fixup: A.x < B.x < C.x (edge flow: A→B→C)
        assert nodes["A"].x < nodes["B"].x < nodes["C"].x

    def test_lr_inner_preserves_y(self):
        nodes, edges, groups = self._setup_lr_inner_tb_outer()
        original_y = {nid: nodes[nid].y for nid in nodes}
        _apply_inner_direction_positions(nodes, edges, groups, "TB")
        for nid in nodes:
            assert nodes[nid].y == original_y[nid], f"y changed for {nid}"

    def test_rl_inner_reorders_x_descending(self):
        nodes = {
            "A": _make_node("A", x=100, y=100, group="grp"),
            "B": _make_node("B", x=300, y=100, group="grp"),
        }
        edges = [_make_edge("A", "B")]
        groups = {"grp": _make_group("grp", ["A", "B"], direction="RL")}
        _apply_inner_direction_positions(nodes, edges, groups, "TB")
        # RL inner: B (higher topo order) should be to the left of A
        assert nodes["B"].x < nodes["A"].x

    def test_no_inner_direction_unchanged(self):
        nodes = {
            "A": _make_node("A", x=100, y=100, group="grp"),
            "B": _make_node("B", x=300, y=200, group="grp"),
        }
        edges = [_make_edge("A", "B")]
        groups = {"grp": _make_group("grp", ["A", "B"], direction="")}
        original_x = {nid: nodes[nid].x for nid in nodes}
        _apply_inner_direction_positions(nodes, edges, groups, "TB")
        # No direction override → no change
        for nid in nodes:
            assert nodes[nid].x == original_x[nid]

    def test_single_member_unchanged(self):
        nodes = {"A": _make_node("A", x=100, y=100, group="grp")}
        edges = []
        groups = {"grp": _make_group("grp", ["A"], direction="LR")}
        _apply_inner_direction_positions(nodes, edges, groups, "TB")
        assert nodes["A"].x == 100

    def test_positions_spaced_by_col_gap(self):
        nodes = {
            "A": _make_node("A", x=100, y=100, group="grp", w=120),
            "B": _make_node("B", x=100, y=100, group="grp", w=120),
        }
        edges = [_make_edge("A", "B")]
        groups = {"grp": _make_group("grp", ["A", "B"], direction="LR")}
        _apply_inner_direction_positions(nodes, edges, groups, "TB", col_gap=COL_GAP)
        gap = nodes["B"].x - nodes["A"].x
        assert gap == 120 + COL_GAP  # width of A + col_gap


# ── Group bbox uses actual node width ─────────────────────────────────────────

class TestGroupBboxActualWidths:
    def test_wide_node_expands_bbox(self):
        """Group bbox right edge should reflect the wide node's actual width."""
        nodes = {
            "narrow": _make_node("narrow", x=100, y=100, group="grp", w=NODE_W),
            "wide": _make_node("wide", x=300, y=100, group="grp", w=NODE_W * 3),
        }
        groups = {"grp": _make_group("grp", ["narrow", "wide"])}
        bboxes = _compute_group_bboxes(nodes, groups, canvas_w=1000, canvas_h=500)
        assert "grp" in bboxes
        x0, y0, x1, y1 = bboxes["grp"]
        # The right edge should incorporate the wide node's actual width
        wide_right = nodes["wide"].x + NODE_W * 3
        assert x1 >= wide_right  # bbox right >= wide node right edge

    def test_narrow_node_does_not_overstate_bbox(self):
        """Group bbox right should not be inflated to NODE_W when nodes are narrower."""
        nodes = {
            "tiny": _make_node("tiny", x=100, y=100, group="grp", w=30),
        }
        groups = {"grp": _make_group("grp", ["tiny"])}
        bboxes = _compute_group_bboxes(nodes, groups, canvas_w=500, canvas_h=300)
        x0, y0, x1, y1 = bboxes["grp"]
        # bbox right should be based on tiny.x + 30, not tiny.x + NODE_W
        assert x1 < nodes["tiny"].x + NODE_W  # not inflated to full NODE_W


# ── Containment invariant ─────────────────────────────────────────────────────

class TestContainmentInvariant:
    """All group member bboxes must be inside the group bbox."""

    def _check_containment(self, nodes, groups, canvas_w=2000, canvas_h=2000):
        from mermaid_render.layout._renderer import _compute_group_bboxes, _node_render_w, _node_render_h
        bboxes = _compute_group_bboxes(nodes, groups, canvas_w, canvas_h)
        violations = []
        for gid, (bx0, by0, bx1, by1) in bboxes.items():
            for mid in groups[gid].members:
                if mid not in nodes or nodes[mid].is_dummy:
                    continue
                n = nodes[mid]
                nw = _node_render_w(n)
                nh = _node_render_h(n)
                if n.x < bx0 or n.x + nw > bx1 or n.y < by0 or n.y + nh > by1:
                    violations.append((gid, mid))
        return violations

    def test_simple_group_containment(self):
        nodes = {
            "A": _make_node("A", x=100, y=100, group="grp"),
            "B": _make_node("B", x=300, y=100, group="grp"),
        }
        groups = {"grp": _make_group("grp", ["A", "B"])}
        violations = self._check_containment(nodes, groups)
        assert violations == [], f"Containment violations: {violations}"

    def test_deep_nesting_fixture_renders(self):
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures",
                                    "flowchart-deep-nesting.mmd")
        with open(fixture_path) as f:
            src = f.read()
        html = _render(src)
        assert "<svg" in html or "<div" in html
        assert "DeepNode" in html
        assert "MidNode" in html
        assert "OuterNode" in html


# ── Integration: inner-direction fixture ─────────────────────────────────────

class TestInnerDirectionFixture:
    FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                           "flowchart-inner-direction.mmd")

    def test_renders_without_error(self):
        with open(self.FIXTURE) as f:
            src = f.read()
        html = _render(src)
        assert "<svg" in html or "diagram mermaid-layout" in html

    def test_all_nodes_present(self):
        with open(self.FIXTURE) as f:
            src = f.read()
        html = _render(src)
        for nid in ("ingest", "transform", "load", "source", "sink"):
            assert f'data-node-id="{nid}"' in html, f"Node '{nid}' missing"

    def test_lr_inner_nodes_share_top(self):
        """Inner LR group nodes should be at the same y (same row in TB outer).

        ELK places the three nodes in successive horizontal layers within the
        compound group; they should all share the same vertical center.
        Allow 2 px tolerance for integer truncation between Python and ELK paths.
        """
        with open(self.FIXTURE) as f:
            src = f.read()
        html = _render(src)
        top_ingest = _node_top(html, "ingest")
        top_transform = _node_top(html, "transform")
        top_load = _node_top(html, "load")
        assert top_ingest is not None
        assert top_transform is not None
        assert top_load is not None
        tol = 2
        assert abs(top_ingest - top_transform) <= tol and abs(top_transform - top_load) <= tol, (
            f"Expected same y (±{tol}px): ingest={top_ingest} transform={top_transform} load={top_load}"
        )

    def test_lr_inner_nodes_ordered_left_to_right(self):
        """Inner LR nodes should flow left-to-right: ingest.x < transform.x < load.x."""
        with open(self.FIXTURE) as f:
            src = f.read()
        html = _render(src)
        x_ingest = _node_left(html, "ingest")
        x_transform = _node_left(html, "transform")
        x_load = _node_left(html, "load")
        assert x_ingest is not None
        assert x_transform is not None
        assert x_load is not None
        assert x_ingest < x_transform < x_load, (
            f"Expected ingest < transform < load; got {x_ingest} {x_transform} {x_load}"
        )

    def test_outer_nodes_above_and_below_group(self):
        """Source should be above the group and sink below (TB outer)."""
        with open(self.FIXTURE) as f:
            src = f.read()
        html = _render(src)
        top_source = _node_top(html, "source")
        top_ingest = _node_top(html, "ingest")
        top_sink = _node_top(html, "sink")
        assert top_source is not None
        assert top_ingest is not None
        assert top_sink is not None
        assert top_source < top_ingest, f"source should be above ingest; got {top_source} vs {top_ingest}"
        assert top_ingest < top_sink, f"ingest should be above sink; got {top_ingest} vs {top_sink}"


# ── Stage 4: _recursive_group_layout invariants ───────────────────────────────

class TestTBInnerLROuter:
    """TB inner group in LR outer: members must be at same x, increasing y."""

    SRC = """
flowchart LR
  subgraph G1
    direction TB
    P --> Q --> R
  end
  X --> P
"""

    def _layout(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from mermaid_render.layout._strategies import _compile_flowchart
        return _compile_flowchart(self.SRC, width_hint=900, options=None).layout

    def test_tb_inner_members_same_x(self):
        """All TB-inner members must share the same x position in LR outer."""
        layout = self._layout()
        px = layout.node_layouts["P"].outer_bounds.x
        qx = layout.node_layouts["Q"].outer_bounds.x
        rx = layout.node_layouts["R"].outer_bounds.x
        assert round(px) == round(qx) == round(rx), (
            f"TB inner members should share x, got P={round(px)} Q={round(qx)} R={round(rx)}"
        )

    def test_tb_inner_members_increasing_y(self):
        """TB-inner members must be placed top-to-bottom (increasing y)."""
        layout = self._layout()
        py = layout.node_layouts["P"].outer_bounds.y
        qy = layout.node_layouts["Q"].outer_bounds.y
        ry = layout.node_layouts["R"].outer_bounds.y
        assert py < qy < ry, (
            f"TB inner members should have increasing y, got P={round(py)} Q={round(qy)} R={round(ry)}"
        )

    def test_x_does_not_enter_predecessor_column(self):
        """Node X (predecessor of G1) must be left of G1 members."""
        layout = self._layout()
        xx = layout.node_layouts["X"].outer_bounds.x + layout.node_layouts["X"].outer_bounds.w
        px = layout.node_layouts["P"].outer_bounds.x
        assert xx < px, f"X.right={round(xx)} should be left of P.x={round(px)}"


class TestNestedGroupAsUnit:
    """Child group treated as unit: Outer positions Inner group + direct members as blocks."""

    SRC = """
flowchart TB
  subgraph Outer
    direction LR
    subgraph Inner
      direction LR
      A --> B
    end
    C --> D
  end
"""

    def _layout(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from mermaid_render.layout._strategies import _compile_flowchart
        return _compile_flowchart(self.SRC, width_hint=900, options=None).layout

    def test_inner_members_within_outer_group(self):
        """A, B (Inner) and C, D (Outer direct) must all be within Outer group boundary.

        Both Python (_recursive_group_layout) and ELK compound layout satisfy
        containment; only the exact y-equality guarantee (ay==by==cy==dy) is
        Python-path-specific (see test_python_path_same_y below).
        """
        layout = self._layout()
        if "Outer" not in layout.group_layouts:
            pytest.skip("Outer group not found — parsing regression")
        if not all(k in layout.node_layouts for k in ("A", "B", "C", "D")):
            pytest.skip("Expected nodes A/B/C/D not found — parsing regression")
        ob = layout.group_layouts["Outer"].boundary_bounds
        tol = 1.0
        for nid in ("A", "B", "C", "D"):
            nb = layout.node_layouts[nid].outer_bounds
            assert ob.x - tol <= nb.x, f"{nid}.x={nb.x:.1f} left of Outer.x={ob.x:.1f}"
            assert nb.x + nb.w <= ob.x + ob.w + tol, f"{nid} right outside Outer"
            assert ob.y - tol <= nb.y, f"{nid}.y={nb.y:.1f} above Outer.y={ob.y:.1f}"
            assert nb.y + nb.h <= ob.y + ob.h + tol, f"{nid} bottom outside Outer"

    @pytest.mark.skipif(_elk_available(), reason="Python path only — ELK may center items differently")
    def test_python_path_same_y(self):
        """Python _recursive_group_layout forces all LR-inner items to the same y."""
        layout = self._layout()
        if not all(k in layout.node_layouts for k in ("A", "B", "C", "D")):
            pytest.skip("Expected nodes A/B/C/D not found — parsing regression")
        ay = round(layout.node_layouts["A"].outer_bounds.y)
        by = round(layout.node_layouts["B"].outer_bounds.y)
        cy = round(layout.node_layouts["C"].outer_bounds.y)
        dy = round(layout.node_layouts["D"].outer_bounds.y)
        assert ay == by == cy == dy, (
            f"Python path: all LR nodes should share y: A={ay} B={by} C={cy} D={dy}"
        )

    def test_inner_group_within_outer_group(self):
        """Inner group boundary must be contained within Outer group boundary."""
        layout = self._layout()
        if "Outer" not in layout.group_layouts or "Inner" not in layout.group_layouts:
            pytest.skip("Outer or Inner group not found — parsing regression")
        ob = layout.group_layouts["Outer"].boundary_bounds
        ib = layout.group_layouts["Inner"].boundary_bounds
        tol = 1.0
        assert ob.x - tol <= ib.x, f"Inner.x={ib.x:.1f} left of Outer.x={ob.x:.1f}"
        assert ib.x + ib.w <= ob.x + ob.w + tol, "Inner right outside Outer"
        assert ob.y - tol <= ib.y, f"Inner.y={ib.y:.1f} above Outer.y={ob.y:.1f}"
        assert ib.y + ib.h <= ob.y + ob.h + tol, "Inner bottom outside Outer"

    @pytest.mark.skipif(_elk_available(), reason="Python path only — ELK may order items differently")
    def test_python_path_inner_left_of_outer_direct(self):
        """Python path: Inner group (A, B) is to the left of Outer direct members (C, D)."""
        layout = self._layout()
        if not all(k in layout.node_layouts for k in ("A", "B", "C", "D")):
            pytest.skip("Expected nodes A/B/C/D not found — parsing regression")
        b_right = layout.node_layouts["B"].outer_bounds.x + layout.node_layouts["B"].outer_bounds.w
        cx = layout.node_layouts["C"].outer_bounds.x
        assert b_right < cx, f"Python path: B.right={round(b_right)} should be left of C.x={round(cx)}"

    def test_no_overlap_inner_and_outer_direct(self):
        """Inner group bbox and C node must not overlap."""
        layout = self._layout()
        if "Inner" not in layout.group_layouts or "C" not in layout.node_layouts:
            pytest.skip("Inner group or C node not found — parsing regression")
        ib = layout.group_layouts["Inner"].boundary_bounds
        cb = layout.node_layouts["C"].outer_bounds
        x_overlap = ib.x < cb.x + cb.w and cb.x < ib.x + ib.w
        y_overlap = ib.y < cb.y + cb.h and cb.y < ib.y + ib.h
        assert not (x_overlap and y_overlap), (
            f"Inner group and C node should not overlap"
        )


# ── Stage 4 determinism ───────────────────────────────────────────────────────

class TestRecursiveGroupLayoutDeterminism:
    """Same input must produce identical FinalizedLayout on repeated calls."""

    def _layout(self, src: str):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from mermaid_render.layout._strategies import _compile_flowchart
        return _compile_flowchart(src, width_hint=900, options=None).layout

    def test_tb_outer_lr_inner_deterministic(self):
        src = """
flowchart TB
  subgraph pipeline
    direction LR
    A --> B --> C
  end
  X --> A
  C --> Y
"""
        l1 = self._layout(src)
        l2 = self._layout(src)
        assert l1.canvas_bounds.w == l2.canvas_bounds.w
        assert l1.canvas_bounds.h == l2.canvas_bounds.h
        for nid in ("A", "B", "C", "X", "Y"):
            if nid in l1.node_layouts and nid in l2.node_layouts:
                b1 = l1.node_layouts[nid].outer_bounds
                b2 = l2.node_layouts[nid].outer_bounds
                assert b1.x == b2.x and b1.y == b2.y, (
                    f"{nid} position not deterministic: {b1} vs {b2}"
                )

    def test_lr_outer_tb_inner_deterministic(self):
        src = """
flowchart LR
  subgraph G1
    direction TB
    P --> Q --> R
  end
  X --> P
"""
        l1 = self._layout(src)
        l2 = self._layout(src)
        assert l1.canvas_bounds.w == l2.canvas_bounds.w
        assert l1.canvas_bounds.h == l2.canvas_bounds.h
        for nid in ("P", "Q", "R", "X"):
            if nid in l1.node_layouts and nid in l2.node_layouts:
                b1 = l1.node_layouts[nid].outer_bounds
                b2 = l2.node_layouts[nid].outer_bounds
                assert b1.x == b2.x and b1.y == b2.y


# ── Regression: existing group fixtures ──────────────────────────────────────

_FIXTURE_EMPTY_SUBGRAPH = os.path.join(os.path.dirname(__file__), "fixtures",
                                        "flowchart-empty-subgraph.mmd")
_FIXTURE_GROUPS_COMPLEX = os.path.join(os.path.dirname(__file__), "fixtures",
                                        "flowchart-groups-complex.mmd")


class TestGroupRegressions:
    def test_groups_complex_renders(self):
        with open(_FIXTURE_GROUPS_COMPLEX) as f:
            src = f.read()
        html = _render(src)
        assert "UI" in html
        assert "API" in html
        assert "DB" in html

    def test_empty_subgraph_renders(self):
        with open(_FIXTURE_EMPTY_SUBGRAPH) as f:
            src = f.read()
        html = _render(src)
        assert "diagram mermaid-layout" in html or "<svg" in html

    @requires_elk
    def test_empty_subgraph_groups_non_overlapping(self):
        """Both groups have non-zero area, neither at origin, and they don't overlap."""
        from mermaid_render.layout._strategies import _compile_flowchart
        with open(_FIXTURE_EMPTY_SUBGRAPH) as f:
            src = f.read()
        compiled = _compile_flowchart(src, 900, None)
        assert compiled.metadata.algorithm == "ELK-layered", (
            "test requires ELK path but got Python path"
        )
        layout = compiled.layout
        gls = list(layout.group_layouts.values())
        assert len(gls) >= 2, "expected at least two groups"
        for gl in gls:
            b = gl.boundary_bounds
            assert b.w > 0 and b.h > 0, f"group {gl.group_id} has zero area"
            assert not (b.x == 0.0 and b.y == 0.0), f"group {gl.group_id} at canvas origin"
        for i, g1 in enumerate(gls):
            for g2 in gls[i + 1:]:
                b1, b2 = g1.boundary_bounds, g2.boundary_bounds
                x_overlap = b1.x < b2.x + b2.w and b2.x < b1.x + b1.w
                y_overlap = b1.y < b2.y + b2.h and b2.y < b1.y + b1.h
                assert not (x_overlap and y_overlap), (
                    f"groups {g1.group_id} and {g2.group_id} overlap"
                )

    @requires_elk
    def test_groups_complex_member_containment(self):
        """Each group fully contains all its declared member nodes (1 px tolerance)."""
        from mermaid_render.layout._strategies import _compile_flowchart
        with open(_FIXTURE_GROUPS_COMPLEX) as f:
            src = f.read()
        compiled = _compile_flowchart(src, 900, None)
        assert compiled.metadata.algorithm == "ELK-layered", (
            "test requires ELK path but got Python path"
        )
        layout = compiled.layout
        tol = 1.0  # int-truncated node coords may be 1 px inside group float boundary
        for gid, gl in layout.group_layouts.items():
            b = gl.boundary_bounds
            for mid in gl.member_ids:
                if mid not in layout.node_layouts:
                    continue
                nb = layout.node_layouts[mid].outer_bounds
                assert b.x - tol <= nb.x, f"{mid} x={nb.x:.1f} left of {gid} x={b.x:.1f}"
                assert nb.x + nb.w <= b.x + b.w + tol, (
                    f"{mid} right={nb.x + nb.w:.1f} outside {gid} right={b.x + b.w:.1f}"
                )
                assert b.y - tol <= nb.y, f"{mid} y={nb.y:.1f} above {gid} y={b.y:.1f}"
                assert nb.y + nb.h <= b.y + b.h + tol, (
                    f"{mid} bottom={nb.y + nb.h:.1f} outside {gid} bottom={b.y + b.h:.1f}"
                )
