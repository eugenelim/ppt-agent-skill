"""T4: ELK adapter tests (AC-ELK-1 through AC-ELK-5).

Default tier: mocked subprocess calls — runs in the fast test suite.
Isolation tier: real Node subprocess — gated by @pytest.mark.isolation.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mermaid_render.layout.elk_adapter as _mod
from mermaid_render.layout.elk_adapter import ElkUnavailable, layout_with_elk, _to_elk_json, _from_elk_result
from mermaid_render.layout._geometry import (
    LayoutEdge, LayoutGraph, LayoutGroup, LayoutNode, MarkerKind, PortSide,
    PortSpec, Point,
)


def _simple_graph() -> LayoutGraph:
    return LayoutGraph(
        nodes=[
            LayoutNode("A", 192, 42, "rect", None, [], ["A"], {}),
            LayoutNode("B", 192, 42, "rect", None, [], ["B"], {}),
        ],
        groups=[],
        edges=[
            LayoutEdge("e0", ["A"], ["B"], None, None,
                       MarkerKind.NONE, MarkerKind.ARROW, "solid", "", {}),
        ],
        direction="TB",
    )


def _minimal_elk_output() -> dict:
    return {
        "id": "root", "x": 0, "y": 0, "width": 500, "height": 300,
        "children": [
            {"id": "A", "x": 10, "y": 10, "width": 192, "height": 42},
            {"id": "B", "x": 10, "y": 132, "width": 192, "height": 42},
        ],
        "edges": [{"id": "e0", "sections": [
            {"startPoint": {"x": 106, "y": 52},
             "endPoint": {"x": 106, "y": 132},
             "bendPoints": []},
        ]}],
    }


@pytest.fixture()
def elk_available(monkeypatch):
    """Patch _find_node and _find_elkjs to appear available without real install."""
    monkeypatch.setattr(_mod, "_find_node", lambda: "/usr/bin/node")
    monkeypatch.setattr(_mod, "_find_elkjs", lambda: "/fake/elk.bundled.js")


# ── Mocked subprocess tests (default fast tier) ───────────────────────────────

class TestElkAdapterMocked:
    def test_elk_unavailable_when_node_absent(self, monkeypatch):
        """AC-ELK-4 trigger: Node runtime absent → ElkUnavailable."""
        monkeypatch.setattr(_mod, "_find_node", lambda: None)
        with pytest.raises(ElkUnavailable):
            layout_with_elk(_simple_graph())

    def test_env_var_forces_python_path(self, monkeypatch):
        """AC-ELK-4 trigger: MERMAID_LAYOUT_ENGINE=python → ElkUnavailable."""
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
        with pytest.raises(ElkUnavailable):
            layout_with_elk(_simple_graph())

    def test_elk_returns_finalized_layout_from_mock(self, elk_available):
        """AC-ELK-3: FinalizedLayout built from ELK child x/y and edge sections."""
        elk_output = _minimal_elk_output()
        with patch.object(_mod, "_run_elk", return_value=elk_output):
            result, _meta = layout_with_elk(_simple_graph())
        assert "A" in result.node_layouts
        assert "B" in result.node_layouts
        assert result.node_layouts["B"].outer_bounds.y > result.node_layouts["A"].outer_bounds.y

    def test_elk_nonzero_exit_raises_unavailable(self, elk_available):
        """AC-ELK-5: non-zero exit → ElkUnavailable."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            with pytest.raises(ElkUnavailable):
                layout_with_elk(_simple_graph())

    def test_elk_malformed_json_raises_unavailable(self, elk_available):
        """AC-ELK-5: malformed JSON stdout → ElkUnavailable."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
            with pytest.raises(ElkUnavailable):
                layout_with_elk(_simple_graph())

    def test_elk_timeout_raises_unavailable(self, elk_available):
        """AC-ELK-5: subprocess timeout → ElkUnavailable."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("node", 30)):
            with pytest.raises(ElkUnavailable):
                layout_with_elk(_simple_graph())

    def test_elk_subprocess_called_with_timeout(self, elk_available):
        """AC-ELK-5: subprocess.run is called with timeout=30."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(_minimal_elk_output()),
                stderr="",
            )
            layout_with_elk(_simple_graph())
        _, kwargs = mock.call_args
        assert kwargs.get("timeout") == 30


# ── Compound layout unit tests (pure, no subprocess) ─────────────────────────

def _compound_graph() -> LayoutGraph:
    """Graph with one group 'cloud' containing two nodes lb and api."""
    lb_port = PortSpec(id="lb_R", node_id="lb", side="EAST", index=0,
                       fixed_side=True, fixed_order=False)
    api_port = PortSpec(id="api_L", node_id="api", side="WEST", index=0,
                        fixed_side=True, fixed_order=False)
    return LayoutGraph(
        nodes=[
            LayoutNode("lb", 192, 48, "rect", "cloud", [lb_port], ["lb"], {}),
            LayoutNode("api", 192, 48, "rect", "cloud", [api_port], ["api"], {}),
        ],
        groups=[
            LayoutGroup(id="cloud", parent_id=None, label="Cloud",
                        label_width=80.0, label_height=20.0, padding=16.0,
                        local_direction="LR", minimum_width=0.0, minimum_height=0.0),
        ],
        edges=[
            LayoutEdge("e0", ["lb"], ["api"], "lb_R", "api_L",
                       MarkerKind.NONE, MarkerKind.ARROW, "solid", "", {}),
        ],
        direction="LR",
    )


class TestElkJsonCompound:
    """Unit tests for _to_elk_json with compound group hierarchy."""

    def test_group_is_root_child(self):
        """The 'cloud' group must appear as a root-level child, not a flat node."""
        j = _to_elk_json(_compound_graph())
        root_ids = [c["id"] for c in j["children"]]
        assert "cloud" in root_ids, f"cloud should be root child, got: {root_ids}"
        assert "lb" not in root_ids
        assert "api" not in root_ids

    def test_nodes_nested_inside_group(self):
        """lb and api must be nested inside the 'cloud' compound node."""
        j = _to_elk_json(_compound_graph())
        cloud = next(c for c in j["children"] if c["id"] == "cloud")
        nested_ids = [n["id"] for n in cloud.get("children", [])]
        assert "lb" in nested_ids
        assert "api" in nested_ids

    def test_port_constraint_set_on_nodes_with_ports(self):
        """Nodes with PortSpec should have portConstraints=FIXED_SIDE."""
        j = _to_elk_json(_compound_graph())
        cloud = next(c for c in j["children"] if c["id"] == "cloud")
        for node in cloud["children"]:
            assert node.get("properties", {}).get("portConstraints") == "FIXED_SIDE"

    def test_edge_uses_port_ids_at_root(self):
        """Edge sources/targets reference port IDs; edges live at root level."""
        j = _to_elk_json(_compound_graph())
        assert len(j["edges"]) == 1
        e = j["edges"][0]
        assert e["sources"] == ["lb_R"]
        assert e["targets"] == ["api_L"]

    def test_group_padding_in_layout_options(self):
        """The group's layoutOptions must include elk.padding."""
        j = _to_elk_json(_compound_graph())
        cloud = next(c for c in j["children"] if c["id"] == "cloud")
        assert "elk.padding" in cloud.get("layoutOptions", {})

    def test_nested_group_child_list_shared(self):
        """A child group added after parent group construction must appear in parent's children."""
        # Simulates a group-in-group scenario: cloud → az (child group) → svc (node)
        svc_port = PortSpec(id="svc_R", node_id="svc", side="EAST", index=0,
                            fixed_side=True, fixed_order=False)
        g = LayoutGraph(
            nodes=[LayoutNode("svc", 192, 48, "rect", "az", [svc_port], ["svc"], {})],
            groups=[
                LayoutGroup(id="cloud", parent_id=None, label="Cloud",
                            label_width=80.0, label_height=20.0, padding=16.0,
                            local_direction="LR", minimum_width=0.0, minimum_height=0.0),
                LayoutGroup(id="az", parent_id="cloud", label="AZ-1",
                            label_width=60.0, label_height=20.0, padding=16.0,
                            local_direction="LR", minimum_width=0.0, minimum_height=0.0),
            ],
            edges=[],
            direction="LR",
        )
        j = _to_elk_json(g)
        cloud = next(c for c in j["children"] if c["id"] == "cloud")
        nested_ids = [c["id"] for c in cloud.get("children", [])]
        assert "az" in nested_ids, (
            f"child group 'az' must be in cloud.children; got {nested_ids}"
        )


class TestElkFromResultCompound:
    """Unit tests for _from_elk_result with compound ELK output."""

    def _compound_output(self) -> dict:
        """Synthetic ELK compound output: cloud at (48, 48), lb at (28, 36) relative."""
        return {
            "id": "root", "x": 0, "y": 0, "width": 600, "height": 300,
            "children": [{
                "id": "cloud", "x": 48, "y": 48, "width": 460, "height": 200,
                "children": [
                    {"id": "lb", "x": 28, "y": 36, "width": 192, "height": 48},
                    {"id": "api", "x": 240, "y": 36, "width": 192, "height": 48},
                ],
            }],
            "edges": [],
        }

    def test_nodes_get_absolute_positions(self):
        """lb and api positions must be group-offset + local coords."""
        result = _from_elk_result(self._compound_output(), _compound_graph())
        assert "lb" in result.node_layouts
        assert "api" in result.node_layouts
        lb = result.node_layouts["lb"].outer_bounds
        api = result.node_layouts["api"].outer_bounds
        # lb absolute: (48+28, 48+36) = (76, 84)
        assert abs(lb.x - 76.0) < 1
        assert abs(lb.y - 84.0) < 1
        # api absolute: (48+240, 48+36) = (288, 84)
        assert abs(api.x - 288.0) < 1
        assert abs(api.y - 84.0) < 1

    def test_group_layout_built(self):
        """GroupLayout for 'cloud' should be populated with the group's bounds."""
        result = _from_elk_result(self._compound_output(), _compound_graph())
        assert "cloud" in result.group_layouts
        b = result.group_layouts["cloud"].boundary_bounds
        assert abs(b.x - 48.0) < 1
        assert abs(b.y - 48.0) < 1
        assert abs(b.w - 460.0) < 1

    def test_api_right_of_lb(self):
        """After compound layout, api.x should be greater than lb.x."""
        result = _from_elk_result(self._compound_output(), _compound_graph())
        assert result.node_layouts["api"].outer_bounds.x > result.node_layouts["lb"].outer_bounds.x


# ── Real Node subprocess tests (isolation tier) ───────────────────────────────

@pytest.mark.isolation
class TestElkAdapterReal:
    def test_elk_places_nodes_real(self):
        """AC-ELK-3 (real): ELK subprocess places B below A in TB direction."""
        result, _meta = layout_with_elk(_simple_graph())
        assert result.node_layouts["B"].outer_bounds.y > result.node_layouts["A"].outer_bounds.y

    def test_elk_routed_edges_have_waypoints_real(self):
        """AC-ELK-3 (real): ELK edge sections produce waypoints in RoutedEdge."""
        result, _meta = layout_with_elk(_simple_graph())
        assert len(result.routed_edges) > 0
        assert len(result.routed_edges[0].waypoints) >= 2


# ── Round-trip tests (T1–T10) ─────────────────────────────────────────────────

class TestRoundTrip:
    """Tests for the _from_elk_result improvements (T1-T10) and layout_with_elk metadata (T10)."""

    # T1: junction_points field on RoutedEdge
    def test_junction_points_collected_from_sections(self):
        """T1/AC9: junctionPoints in ELK sections are captured on RoutedEdge."""
        out = {
            "id": "root", "width": 400, "height": 300,
            "children": [
                {"id": "A", "x": 10, "y": 10, "width": 100, "height": 40},
                {"id": "B", "x": 10, "y": 150, "width": 100, "height": 40},
            ],
            "edges": [{"id": "e0", "sections": [{
                "startPoint": {"x": 60, "y": 50},
                "endPoint": {"x": 60, "y": 150},
                "bendPoints": [],
                "junctionPoints": [{"x": 60, "y": 100}],
            }]}],
        }
        result = _from_elk_result(out, _simple_graph())
        assert len(result.routed_edges) == 1
        re = result.routed_edges[0]
        assert len(re.junction_points) == 1
        assert re.junction_points[0] == Point(60.0, 100.0)

    def test_junction_points_empty_when_none(self):
        """T1: junction_points is empty tuple when no junctionPoints in sections."""
        result = _from_elk_result(_minimal_elk_output(), _simple_graph())
        assert result.routed_edges[0].junction_points == ()

    # T2: edge_style from orig_edge.line_style
    def test_edge_style_from_orig_edge(self):
        """T2: edge_style on RoutedEdge reflects orig_edge.line_style."""
        graph = LayoutGraph(
            nodes=[
                LayoutNode("A", 100, 40, "rect", None, [], ["A"], {}),
                LayoutNode("B", 100, 40, "rect", None, [], ["B"], {}),
            ],
            groups=[],
            edges=[
                LayoutEdge("e0", ["A"], ["B"], None, None,
                           MarkerKind.NONE, MarkerKind.ARROW, "dashed", "", {}),
            ],
            direction="TB",
        )
        out = _minimal_elk_output()
        result = _from_elk_result(out, graph)
        assert result.routed_edges[0].edge_style == "dashed"

    # T3: src/dst node IDs from orig_edge (not port strings from ELK)
    def test_src_dst_ids_from_orig_edge(self):
        """T3: RoutedEdge.src_node_id / dst_node_id taken from orig_edge.sources/targets."""
        lb_port = PortSpec(id="lb_R", node_id="lb", side="EAST", index=0,
                           fixed_side=True, fixed_order=False)
        api_port = PortSpec(id="api_L", node_id="api", side="WEST", index=0,
                            fixed_side=True, fixed_order=False)
        graph = LayoutGraph(
            nodes=[
                LayoutNode("lb", 192, 48, "rect", None, [lb_port], ["lb"], {}),
                LayoutNode("api", 192, 48, "rect", None, [api_port], ["api"], {}),
            ],
            groups=[],
            edges=[
                LayoutEdge("e0", ["lb"], ["api"], "lb_R", "api_L",
                           MarkerKind.NONE, MarkerKind.ARROW, "solid", "", {}),
            ],
            direction="LR",
        )
        out = {
            "id": "root", "width": 600, "height": 200,
            "children": [
                {"id": "lb", "x": 10, "y": 80, "width": 192, "height": 48},
                {"id": "api", "x": 300, "y": 80, "width": 192, "height": 48},
            ],
            "edges": [{"id": "e0",
                       "sources": ["lb_R"],  # ELK uses port IDs
                       "targets": ["api_L"],
                       "sections": [{"startPoint": {"x": 202, "y": 104},
                                     "endPoint": {"x": 300, "y": 104},
                                     "bendPoints": []}]}],
        }
        result = _from_elk_result(out, graph)
        re = result.routed_edges[0]
        assert re.src_node_id == "lb"   # not "lb_R"
        assert re.dst_node_id == "api"  # not "api_L"

    # T5: tangent-based port direction and side
    def test_src_port_direction_right_going_edge(self):
        """T5: src_port.side==RIGHT and direction.x>0 for a left-to-right edge."""
        out = {
            "id": "root", "width": 600, "height": 200,
            "children": [
                {"id": "A", "x": 0, "y": 0, "width": 192, "height": 42},
                {"id": "B", "x": 300, "y": 0, "width": 192, "height": 42},
            ],
            "edges": [{"id": "e0", "sections": [{
                "startPoint": {"x": 192, "y": 21},
                "bendPoints": [{"x": 250, "y": 21}],
                "endPoint": {"x": 300, "y": 21},
            }]}],
        }
        graph = LayoutGraph(
            nodes=[
                LayoutNode("A", 192, 42, "rect", None, [], ["A"], {}),
                LayoutNode("B", 192, 42, "rect", None, [], ["B"], {}),
            ],
            groups=[],
            edges=[LayoutEdge("e0", ["A"], ["B"], None, None,
                              MarkerKind.NONE, MarkerKind.ARROW, "solid", "", {})],
            direction="LR",
        )
        result = _from_elk_result(out, graph)
        re = result.routed_edges[0]
        assert re.src_port.side == PortSide.RIGHT
        assert re.src_port.direction.x > 0

    def test_dst_port_direction_into_top(self):
        """T5: dst_port.side==TOP and direction.y<0 when edge arrives from above."""
        out = {
            "id": "root", "width": 400, "height": 300,
            "children": [
                {"id": "A", "x": 50, "y": 0, "width": 100, "height": 40},
                {"id": "B", "x": 50, "y": 200, "width": 100, "height": 40},
            ],
            "edges": [{"id": "e0", "sections": [{
                "startPoint": {"x": 100, "y": 40},
                "endPoint": {"x": 100, "y": 200},
                "bendPoints": [],
            }]}],
        }
        graph = LayoutGraph(
            nodes=[
                LayoutNode("A", 100, 40, "rect", None, [], ["A"], {}),
                LayoutNode("B", 100, 40, "rect", None, [], ["B"], {}),
            ],
            groups=[],
            edges=[LayoutEdge("e0", ["A"], ["B"], None, None,
                              MarkerKind.NONE, MarkerKind.ARROW, "solid", "", {})],
            direction="TB",
        )
        result = _from_elk_result(out, graph)
        re = result.routed_edges[0]
        assert re.dst_port.side == PortSide.TOP
        assert re.dst_port.direction.y < 0

    # T7: EdgeLabelLayout from ELK label geometry
    def test_edge_label_layout_from_elk(self):
        """T7: EdgeLabelLayout populated when orig_edge has a label and ELK returns label geometry."""
        graph = LayoutGraph(
            nodes=[
                LayoutNode("A", 100, 40, "rect", None, [], ["A"], {}),
                LayoutNode("B", 100, 40, "rect", None, [], ["B"], {}),
            ],
            groups=[],
            edges=[
                LayoutEdge("e0", ["A"], ["B"], None, None,
                           MarkerKind.NONE, MarkerKind.ARROW, "solid", "uses", {}),
            ],
            direction="TB",
        )
        out = {
            "id": "root", "width": 400, "height": 300,
            "children": [
                {"id": "A", "x": 10, "y": 10, "width": 100, "height": 40},
                {"id": "B", "x": 10, "y": 150, "width": 100, "height": 40},
            ],
            "edges": [{"id": "e0",
                       "labels": [{"x": 40, "y": 90, "width": 40, "height": 14}],
                       "sections": [{"startPoint": {"x": 60, "y": 50},
                                     "endPoint": {"x": 60, "y": 150},
                                     "bendPoints": []}]}],
        }
        result = _from_elk_result(out, graph)
        re = result.routed_edges[0]
        assert re.label_layout is not None
        assert re.label_layout.text == "uses"
        assert re.label_layout.bounds.x == 40.0

    # T8: GroupLayout.label_layout from LayoutGroup.label
    def test_group_label_layout_populated(self):
        """T8: GroupLayout.label_layout is not None when the group has a label."""
        result = _from_elk_result(
            {
                "id": "root", "width": 600, "height": 300,
                "children": [{
                    "id": "cloud", "x": 48, "y": 48, "width": 460, "height": 200,
                    "children": [
                        {"id": "lb", "x": 28, "y": 36, "width": 192, "height": 48},
                        {"id": "api", "x": 240, "y": 36, "width": 192, "height": 48},
                    ],
                }],
                "edges": [],
            },
            _compound_graph(),
        )
        assert result.group_layouts["cloud"].label_layout is not None

    # T9: NodeLayout.rank from coordinates
    def test_node_rank_reconstructed_from_positions(self):
        """T9: rank=1 for top node, rank=2 for lower node in TB layout."""
        result = _from_elk_result(_minimal_elk_output(), _simple_graph())
        # A is at y=10, B is at y=132 → A gets rank 1, B gets rank 2
        assert result.node_layouts["A"].rank == 1
        assert result.node_layouts["B"].rank == 2

    # T10: LayoutMetadata with ELK provenance fields
    def test_layout_metadata_elk_fields(self, monkeypatch):
        """T10: layout_with_elk returns LayoutMetadata with backend=elkjs."""
        monkeypatch.setattr(_mod, "_find_node", lambda: "/usr/bin/node")
        monkeypatch.setattr(_mod, "_find_elkjs", lambda: "/fake/elk.bundled.js")
        with patch.object(_mod, "_run_elk", return_value=_minimal_elk_output()):
            _result, meta = layout_with_elk(_simple_graph())
        assert meta.backend == "elkjs"
        assert meta.backend_version == "0.12.0"
        assert meta.fallback_reason is None
        assert meta.elapsed_ms >= 0.0
        assert "elk.algorithm" in meta.options_applied

    def test_multi_section_waypoints_deduped(self):
        """T1/AC10: consecutive duplicate points from section joins are removed."""
        out = {
            "id": "root", "width": 400, "height": 300,
            "children": [
                {"id": "A", "x": 10, "y": 10, "width": 100, "height": 40},
                {"id": "B", "x": 10, "y": 200, "width": 100, "height": 40},
            ],
            "edges": [{"id": "e0", "sections": [
                {"startPoint": {"x": 60, "y": 50}, "endPoint": {"x": 60, "y": 120},
                 "bendPoints": []},
                # second section starts where first ended → duplicate should be dropped
                {"startPoint": {"x": 60, "y": 120}, "endPoint": {"x": 60, "y": 200},
                 "bendPoints": []},
            ]}],
        }
        result = _from_elk_result(out, _simple_graph())
        wps = result.routed_edges[0].waypoints
        # (60,50) → (60,120) → (60,200): the shared join point appears once
        assert len(wps) == 3
        assert wps[0] == Point(60.0, 50.0)
        assert wps[1] == Point(60.0, 120.0)
        assert wps[2] == Point(60.0, 200.0)
