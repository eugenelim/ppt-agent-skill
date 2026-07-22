"""Fidelity data-attribute annotation tests.

Verifies that to_html() emits the full set of fidelity data attributes
used by the fidelity harness to locate diagram elements:
  data-kind, data-label, data-shape, data-order,
  data-parent-id, data-group-id, data-relation-id, data-arrow.

No browser or mmdc required — pure Python renderer only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html


def _attrs(html: str, attr: str) -> list[str]:
    return re.findall(rf'{attr}="([^"]*)"', html)


def _unique_attrs(html: str) -> set[str]:
    return {m.split("=")[0] for m in re.findall(r'data-[a-z-]+="[^"]*"', html)}


# ── flowchart (richest annotation surface) ────────────────────────────────────

class TestFlowchartAnnotations:
    """Flowchart to_html() must emit the full fidelity attribute set."""

    SRC = "flowchart TD\n  A[Start] --> B{Decision}\n  B -->|yes| C[End]\n  B -->|no| D[Retry]"

    def test_data_kind_node(self):
        """Every node element carries data-kind='node'."""
        html = to_html(self.SRC)
        kinds = _attrs(html, "data-kind")
        assert "node" in kinds, "No data-kind='node' found"

    def test_data_label_present(self):
        """Node labels appear in data-label attributes."""
        html = to_html(self.SRC)
        labels = _attrs(html, "data-label")
        assert any("Start" in lbl for lbl in labels), (
            f"data-label='Start' missing; labels={labels[:5]}"
        )

    def test_data_shape_present(self):
        """data-shape attribute reflects the node's semantic shape."""
        html = to_html(self.SRC)
        shapes = set(_attrs(html, "data-shape"))
        assert shapes, "No data-shape attributes found"
        assert "diamond" in shapes or "rect" in shapes, (
            f"Expected diamond or rect shape; got {shapes}"
        )

    def test_data_order_present(self):
        """Every node carries a data-order rank attribute."""
        html = to_html(self.SRC)
        orders = _attrs(html, "data-order")
        assert orders, "No data-order attributes found"
        assert all(o.lstrip("-").isdigit() for o in orders), (
            f"Non-integer data-order values: {orders}"
        )

    def test_data_relation_id_on_edges(self):
        """Edge elements carry data-relation-id attributes."""
        html = to_html(self.SRC)
        rels = _attrs(html, "data-relation-id")
        assert rels, "No data-relation-id found on edges"

    def test_data_arrow_on_edges(self):
        """Edge elements carry data-arrow attributes."""
        html = to_html(self.SRC)
        arrows = _attrs(html, "data-arrow")
        assert arrows, "No data-arrow found on edges"

    def test_edge_label_in_html(self):
        """Edge labels ('yes', 'no') appear somewhere in the rendered HTML."""
        html = to_html(self.SRC)
        assert "yes" in html, "Edge label 'yes' missing"
        assert "no" in html, "Edge label 'no' missing"


class TestSubgraphAnnotations:
    """Nodes inside subgraphs must carry data-parent-id and group must have data-group-id."""

    SRC = "flowchart TD\n  subgraph MyGroup\n    A --> B\n  end\n  B --> C"

    def test_data_group_id_on_group(self):
        """Subgraph boundary carries data-group-id."""
        html = to_html(self.SRC)
        group_ids = _attrs(html, "data-group-id")
        assert group_ids, "No data-group-id found for subgraph"

    def test_data_parent_id_for_members(self):
        """Nodes inside a subgraph carry data-parent-id matching the group id."""
        html = to_html(self.SRC)
        group_ids = set(_attrs(html, "data-group-id"))
        parent_ids = set(_attrs(html, "data-parent-id"))
        assert parent_ids, "No data-parent-id found for subgraph members"
        assert parent_ids & group_ids, (
            f"data-parent-id values {parent_ids} don't overlap group ids {group_ids}"
        )

    def test_nodes_outside_subgraph_no_parent_id(self):
        """Node C (outside the subgraph) must NOT have data-parent-id."""
        html = to_html(self.SRC)
        c_nodes = re.findall(r'<div[^>]*data-node-id="C"[^>]*/?>',html)
        assert c_nodes, "Node C not found"
        for frag in c_nodes:
            assert "data-parent-id" not in frag, (
                f"Node C should not have data-parent-id but found: {frag[:200]}"
            )


# ── attribute completeness across diagram types ───────────────────────────────

@pytest.mark.parametrize("src,required_attrs", [
    (
        "flowchart LR\n  A --> B",
        {"data-kind", "data-label", "data-shape", "data-order", "data-relation-id"},
    ),
    (
        "sequenceDiagram\n  Alice->>Bob: hello",
        set(),  # sequence uses different HTML structure; baseline = no crash
    ),
    (
        "erDiagram\n  CUSTOMER ||--o{ ORDER : places",
        {"data-node-id"},  # ER renderer uses data-node-id; data-kind/label not yet annotated
    ),
])
def test_required_annotations_present(src: str, required_attrs: set[str]) -> None:
    """Specified data attributes must be present in to_html() output."""
    html = to_html(src)
    assert html, "to_html() returned empty string"
    present = _unique_attrs(html)
    missing = required_attrs - present
    assert not missing, (
        f"Missing fidelity annotations: {sorted(missing)}\n"
        f"Present: {sorted(present)}"
    )
