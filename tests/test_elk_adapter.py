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
from mermaid_render.layout.elk_adapter import ElkUnavailable, layout_with_elk
from mermaid_render.layout._geometry import (
    LayoutEdge, LayoutGraph, LayoutNode, MarkerKind,
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
            result = layout_with_elk(_simple_graph())
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


# ── Real Node subprocess tests (isolation tier) ───────────────────────────────

@pytest.mark.isolation
class TestElkAdapterReal:
    def test_elk_places_nodes_real(self):
        """AC-ELK-3 (real): ELK subprocess places B below A in TB direction."""
        result = layout_with_elk(_simple_graph())
        assert result.node_layouts["B"].outer_bounds.y > result.node_layouts["A"].outer_bounds.y

    def test_elk_routed_edges_have_waypoints_real(self):
        """AC-ELK-3 (real): ELK edge sections produce waypoints in RoutedEdge."""
        result = layout_with_elk(_simple_graph())
        assert len(result.routed_edges) > 0
        assert len(result.routed_edges[0].waypoints) >= 2
