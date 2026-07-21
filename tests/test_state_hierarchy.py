"""Tests for state diagram native scene path.

State diagrams are graph-topology types (_GRAPH_DIRECTIVES), so they go through
the _graph_topology_scene() path in native_svg.py and use the same layout +
paint.py pipeline as flowcharts.
"""
from __future__ import annotations

import re

import pytest

from scripts.mermaid_render.native_svg import dispatch_native
from scripts.mermaid_render.scene import (
    ScenePath, SvgScene,
    LAYER_EDGES, LAYER_NODES, LAYER_LABELS,
)


SIMPLE_STATE = """\
stateDiagram-v2
    [*] --> Idle
    Idle --> Running : start
    Running --> Idle : stop
    Running --> [*]
"""

NESTED_STATE = """\
stateDiagram-v2
    [*] --> Active
    state Active {
        [*] --> Ready
        Ready --> Busy : work
        Busy --> Ready : done
    }
    Active --> [*] : exit
"""

STATE_V1 = """\
stateDiagram
    [*] --> Still
    Still --> Moving
    Moving --> Still
    Moving --> Crash
    Crash --> [*]
"""


class TestStateDiagramNative:
    def test_simple_state_produces_svg(self):
        svg = dispatch_native(SIMPLE_STATE)
        assert "<svg" in svg

    def test_no_foreign_object(self):
        svg = dispatch_native(SIMPLE_STATE)
        assert "<foreignObject" not in svg

    def test_state_labels_present(self):
        svg = dispatch_native(SIMPLE_STATE)
        assert "Idle" in svg
        assert "Running" in svg

    def test_has_edges(self):
        svg = dispatch_native(SIMPLE_STATE)
        # Should have path elements for transitions
        assert "<path" in svg

    def test_deterministic(self):
        svg1 = dispatch_native(SIMPLE_STATE)
        svg2 = dispatch_native(SIMPLE_STATE)
        assert svg1 == svg2

    def test_v1_syntax(self):
        svg = dispatch_native(STATE_V1)
        assert "<svg" in svg
        assert "Still" in svg

    def test_valid_xml(self):
        from lxml import etree
        svg = dispatch_native(SIMPLE_STATE)
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        etree.fromstring(body.encode("utf-8"))

    def test_nested_state(self):
        svg = dispatch_native(NESTED_STATE)
        assert "<svg" in svg
        assert "Ready" in svg or "Busy" in svg

    def test_diagram_type_attribute(self):
        svg = dispatch_native(SIMPLE_STATE)
        assert "statediagram" in svg.lower() or "state" in svg.lower()

    def test_no_nan_in_output(self):
        svg = dispatch_native(SIMPLE_STATE)
        assert "NaN" not in svg

    def test_width_hint(self):
        svg = dispatch_native(SIMPLE_STATE, width_hint=800)
        assert "<svg" in svg
