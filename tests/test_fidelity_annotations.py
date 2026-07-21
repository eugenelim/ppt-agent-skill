"""Verify that the native renderer emits the new fidelity data-* annotations.

Tests that every node div has data-kind, data-label, data-shape, data-order,
and that edge paths/labels have data-relation-id and data-arrow.
Does NOT require a browser — checks the raw HTML string.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts"))

from mermaid_render import to_html

_SIMPLE_FLOWCHART = """\
flowchart LR
  A[Node A] --> B{Decision}
  B -->|Yes| C[End]
  B -->|No| D[Retry]
"""

_GROUPED_FLOWCHART = """\
flowchart TB
  subgraph Group1
    A[Alpha] --> B[Beta]
  end
  B --> C[Gamma]
"""

_NODE_DATA_ATTRS = re.compile(
    r'data-node-id="([^"]*)"[^>]*?'
    r'data-kind="([^"]*)"[^>]*?'
    r'data-label="([^"]*)"[^>]*?'
    r'data-shape="([^"]*)"[^>]*?'
    r'data-order="([^"]*)"',
    re.DOTALL,
)

_EDGE_RELATION_ID = re.compile(r'data-relation-id="([^"]*)"')
_EDGE_ARROW = re.compile(r'data-arrow="([^"]*)"')
_NODE_ID_RE = re.compile(r'data-node-id="([^"]*)"')
_GROUP_ID_RE = re.compile(r'data-group-id="([^"]*)"')
_PARENT_ID_RE = re.compile(r'data-parent-id="([^"]*)"')


class TestNodeAnnotations:
    def test_all_nodes_have_data_kind(self):
        html = to_html(_SIMPLE_FLOWCHART)
        node_ids = _NODE_ID_RE.findall(html)
        assert node_ids, "No data-node-id found in rendered HTML"
        # Every node-id occurrence should be accompanied by data-kind
        for block in re.finditer(r'data-node-id="[^"]*"[^>]*>', html):
            assert 'data-kind=' in block.group(), (
                f"Node div missing data-kind: {block.group()[:200]}"
            )

    def test_all_nodes_have_data_label(self):
        html = to_html(_SIMPLE_FLOWCHART)
        for block in re.finditer(r'data-node-id="[^"]*"[^>]*>', html):
            assert 'data-label=' in block.group(), (
                f"Node div missing data-label: {block.group()[:200]}"
            )

    def test_all_nodes_have_data_shape(self):
        html = to_html(_SIMPLE_FLOWCHART)
        for block in re.finditer(r'data-node-id="[^"]*"[^>]*>', html):
            assert 'data-shape=' in block.group(), (
                f"Node div missing data-shape: {block.group()[:200]}"
            )

    def test_all_nodes_have_data_order(self):
        html = to_html(_SIMPLE_FLOWCHART)
        for block in re.finditer(r'data-node-id="[^"]*"[^>]*>', html):
            assert 'data-order=' in block.group(), (
                f"Node div missing data-order: {block.group()[:200]}"
            )

    def test_node_count_matches_expected(self):
        html = to_html(_SIMPLE_FLOWCHART)
        node_ids = set(_NODE_ID_RE.findall(html))
        # flowchart has 4 nodes: A, B, C, D
        assert len(node_ids) == 4, f"Expected 4 nodes, got {len(node_ids)}: {node_ids}"

    def test_diamond_node_has_shape_diamond(self):
        html = to_html(_SIMPLE_FLOWCHART)
        # Find the {Decision} node — it's a diamond
        # data-shape should be "diamond" for that node
        # The node B has shape diamond
        blocks = re.findall(r'data-node-id="[^"]*"[^>]*data-shape="([^"]*)"', html, re.DOTALL)
        shapes = set(blocks)
        assert "diamond" in shapes, f"No diamond shape found. Shapes: {shapes}"


class TestEdgeAnnotations:
    def test_edge_paths_have_relation_id(self):
        html = to_html(_SIMPLE_FLOWCHART)
        rel_ids = _EDGE_RELATION_ID.findall(html)
        assert rel_ids, "No data-relation-id found on edge paths"

    def test_edge_paths_have_arrow(self):
        html = to_html(_SIMPLE_FLOWCHART)
        arrow_vals = _EDGE_ARROW.findall(html)
        assert arrow_vals, "No data-arrow found on edge paths"

    def test_relation_id_encodes_src_dst(self):
        html = to_html(_SIMPLE_FLOWCHART)
        rel_ids = _EDGE_RELATION_ID.findall(html)
        # Each relation-id should be of the form "src__dst__N"
        for rid in rel_ids:
            assert "__" in rid, f"data-relation-id lacks __ separator: {rid!r}"

    def test_labeled_edges_have_relation_id(self):
        html = to_html(_SIMPLE_FLOWCHART)
        # Check that edge-label spans also have data-relation-id
        for block in re.finditer(r'class="edge-label"[^>]*>', html):
            assert 'data-relation-id=' in block.group(), (
                f"edge-label span missing data-relation-id: {block.group()[:200]}"
            )


class TestGroupAnnotations:
    def test_group_has_data_group_id(self):
        html = to_html(_GROUPED_FLOWCHART)
        group_ids = _GROUP_ID_RE.findall(html)
        assert group_ids, "No data-group-id found in rendered HTML with subgraph"

    def test_grouped_nodes_have_parent_id(self):
        html = to_html(_GROUPED_FLOWCHART)
        parent_ids = _PARENT_ID_RE.findall(html)
        assert parent_ids, "No data-parent-id found on nodes inside subgraph"
        # Parent IDs should match the group ID
        group_ids = set(_GROUP_ID_RE.findall(html))
        for pid in parent_ids:
            assert pid in group_ids, (
                f"data-parent-id '{pid}' not in known group IDs {group_ids}"
            )


class TestRegressionDataNodeId:
    """Verify the existing data-node-id is still present after our changes."""

    def test_data_node_id_still_emitted(self):
        html = to_html(_SIMPLE_FLOWCHART)
        node_ids = _NODE_ID_RE.findall(html)
        assert "A" in node_ids or any("A" in x for x in node_ids), (
            f"Node 'A' not found in data-node-id attributes. IDs: {node_ids}"
        )

    def test_data_src_dst_still_emitted(self):
        html = to_html(_SIMPLE_FLOWCHART)
        assert 'data-src=' in html
        assert 'data-dst=' in html
