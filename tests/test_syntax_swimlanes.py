#!/usr/bin/env python3
"""Pytest tests for swimlane-style flowcharts.

Mermaid has no dedicated swimlane keyword.  Swimlanes are modelled as
``flowchart LR`` (or ``graph LR``) diagrams where each lane is a
``subgraph`` block.  Tests here cover the swimlane subset: multiple
parallel lanes, cross-lane edges, lane labels, and activities (nodes)
within lanes.

Import pattern mirrors tests/test_mermaid_layout.py: sys.path.insert so
tests/ does not need a conftest.py and the import is self-contained.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_layout import (
    _dispatch,
    _parse_graph_source,
)


def _render(src: str) -> str:
    """Call _dispatch with a generous canvas width; returns HTML fragment."""
    return _dispatch(src, None, 900)


# ── fixture sources ───────────────────────────────────────────────────────────

_LR_TWO_LANES = """\
flowchart LR
  subgraph lane1["Lane 1"]
    A[Start] --> B[Process]
  end
  subgraph lane2["Lane 2"]
    C[Review] --> D[End]
  end
  B --> C
"""

_LR_THREE_LANES = """\
flowchart LR
  subgraph intake["Intake"]
    R[Request] --> V[Validate]
  end
  subgraph processing["Processing"]
    P1[Step 1] --> P2[Step 2]
  end
  subgraph delivery["Delivery"]
    S[Ship] --> N[Notify]
  end
  V --> P1
  P2 --> S
"""

_TB_TWO_LANES = """\
flowchart TB
  subgraph frontend["Frontend"]
    direction LR
    UI[UI] --> API[API Client]
  end
  subgraph backend["Backend"]
    direction LR
    SVC[Service] --> DB[(Database)]
  end
  API --> SVC
"""

_GRAPH_LR = """\
graph LR
  subgraph alpha["Alpha Lane"]
    X[Task X] --> Y[Task Y]
  end
  subgraph beta["Beta Lane"]
    Z[Task Z]
  end
  Y --> Z
"""


# ── parser-level tests ────────────────────────────────────────────────────────

class TestSwimlanesParser:
    """_parse_graph_source correctly ingests LR swimlane source."""

    def test_lr_two_lanes_creates_two_groups(self):
        """Two subgraph blocks in an LR flowchart produce exactly two groups."""
        lines = _LR_TWO_LANES.splitlines()
        _, _, groups = _parse_graph_source(lines)
        assert len(groups) == 2, f"expected 2 groups, got {len(groups)}: {list(groups)}"

    def test_lr_lane_labels_stored(self):
        """Quoted subgraph labels are stored verbatim in the group objects."""
        lines = _LR_TWO_LANES.splitlines()
        _, _, groups = _parse_graph_source(lines)
        labels = {g.label for g in groups.values()}
        assert "Lane 1" in labels, f"'Lane 1' missing from group labels: {labels}"
        assert "Lane 2" in labels, f"'Lane 2' missing from group labels: {labels}"

    def test_lr_nodes_assigned_to_lanes(self):
        """Nodes declared inside a subgraph are members of that group."""
        lines = _LR_TWO_LANES.splitlines()
        _, _, groups = _parse_graph_source(lines)
        lane1 = next(g for g in groups.values() if g.label == "Lane 1")
        lane2 = next(g for g in groups.values() if g.label == "Lane 2")
        assert "A" in lane1.members, f"A should be in Lane 1; members={lane1.members}"
        assert "B" in lane1.members, f"B should be in Lane 1; members={lane1.members}"
        assert "C" in lane2.members, f"C should be in Lane 2; members={lane2.members}"
        assert "D" in lane2.members, f"D should be in Lane 2; members={lane2.members}"

    def test_lr_cross_lane_edge_parsed(self):
        """The cross-lane edge B --> C is captured in the edge list."""
        lines = _LR_TWO_LANES.splitlines()
        _, edges, _ = _parse_graph_source(lines)
        assert any(e.src == "B" and e.dst == "C" for e in edges), (
            f"cross-lane edge B→C not found; edges={[(e.src,e.dst) for e in edges]}"
        )

    def test_three_lanes_all_groups_created(self):
        """Three subgraph lanes all produce distinct group objects."""
        lines = _LR_THREE_LANES.splitlines()
        _, _, groups = _parse_graph_source(lines)
        labels = {g.label for g in groups.values()}
        assert len(groups) == 3, f"expected 3 groups, got {len(groups)}"
        assert {"Intake", "Processing", "Delivery"} == labels


# ── render-level tests ────────────────────────────────────────────────────────

class TestSwimlanesRender:
    """_dispatch produces valid HTML for swimlane patterns."""

    def test_lr_swimlane_renders_without_error(self):
        """Basic two-lane LR swimlane produces the mermaid-layout container."""
        html = _render(_LR_TWO_LANES)
        assert "diagram mermaid-layout" in html

    def test_lr_lane_labels_present_in_html(self):
        """Both lane labels appear somewhere in the rendered output."""
        html = _render(_LR_TWO_LANES)
        assert "Lane 1" in html, "Lane 1 label missing from HTML"
        assert "Lane 2" in html, "Lane 2 label missing from HTML"

    def test_lr_node_labels_present_in_html(self):
        """All four activity labels from both lanes appear in the HTML."""
        html = _render(_LR_TWO_LANES)
        for label in ("Start", "Process", "Review", "End"):
            assert label in html, f"node label '{label}' missing from HTML"

    def test_lr_three_lane_labels_all_present(self):
        """Three-lane diagram renders all lane labels."""
        html = _render(_LR_THREE_LANES)
        for label in ("Intake", "Processing", "Delivery"):
            assert label in html, f"lane label '{label}' missing"

    def test_tb_swimlane_renders(self):
        """TB-direction swimlane (horizontal sub-flows per lane) renders correctly."""
        html = _render(_TB_TWO_LANES)
        assert "diagram mermaid-layout" in html
        assert "Frontend" in html
        assert "Backend" in html

    def test_graph_lr_directive_renders(self):
        """``graph LR`` (not ``flowchart LR``) swimlane renders without error."""
        html = _render(_GRAPH_LR)
        assert "diagram mermaid-layout" in html
        assert "Alpha Lane" in html
        assert "Beta Lane" in html

    def test_cross_lane_edge_not_dropped(self):
        """The cross-lane edge is reflected in the HTML (an SVG path or arrow exists)."""
        html = _render(_LR_TWO_LANES)
        # An edge between lanes must produce at least one SVG path element
        assert "<path" in html, "no SVG path found — cross-lane edge was dropped"
