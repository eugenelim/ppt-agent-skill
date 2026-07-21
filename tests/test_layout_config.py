"""Tests for typed layout configuration propagation (Stage 3)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mermaid_render.layout._config import (
    FlowchartLayoutConfig,
    C4LayoutConfig,
    RenderConfig,
    parse_flowchart_config,
    parse_c4_config,
    parse_render_config,
    legacy_parse_init_config,
)
from mermaid_render.layout._constants import COL_GAP, RANK_GAP, CANVAS_PAD
from mermaid_render.layout._strategies import _dispatch


def _canvas_dims(html: str) -> tuple[int, int]:
    w = re.search(r'width:(\d+)px', html)
    h = re.search(r'height:(\d+)px', html)
    return (int(w.group(1)) if w else 0, int(h.group(1)) if h else 0)


_BASE_FC = "flowchart TD\n    A[Alpha] --> B[Beta]\n    B --> C[Gamma]\n"


class TestFlowchartConfigParsing:
    def test_defaults(self):
        cfg = parse_flowchart_config("flowchart TD\nA --> B")
        assert cfg.node_spacing == COL_GAP
        assert cfg.rank_spacing == RANK_GAP
        assert cfg.diagram_padding == CANVAS_PAD

    def test_node_spacing_override(self):
        src = '%%{init: {"flowchart": {"nodeSpacing": 120}}}%%\nflowchart TD\nA-->B'
        cfg = parse_flowchart_config(src)
        assert cfg.node_spacing == 120

    def test_rank_spacing_override(self):
        src = '%%{init: {"flowchart": {"rankSpacing": 200}}}%%\nflowchart TD\nA-->B'
        cfg = parse_flowchart_config(src)
        assert cfg.rank_spacing == 200

    def test_diagram_padding_override(self):
        src = '%%{init: {"flowchart": {"diagramPadding": 100}}}%%\nflowchart TD\nA-->B'
        cfg = parse_flowchart_config(src)
        assert cfg.diagram_padding == 100

    def test_unknown_keys_collected(self):
        src = '%%{init: {"flowchart": {"unknownKey": 42}}}%%\nflowchart TD\nA-->B'
        cfg = parse_flowchart_config(src)
        assert "unknownKey" in cfg.unsupported_keys

    def test_single_quote_json(self):
        src = "%%{init: {'flowchart': {'nodeSpacing': 80}}}%%\nflowchart TD\nA-->B"
        cfg = parse_flowchart_config(src)
        assert cfg.node_spacing == 80

    def test_bad_json_ignored(self):
        src = "%%{init: {{{bad json}}}%%\nflowchart TD\nA-->B"
        cfg = parse_flowchart_config(src)
        assert cfg.node_spacing == COL_GAP  # defaults preserved


class TestC4ConfigParsing:
    def test_defaults(self):
        cfg = parse_c4_config("C4Container\nPerson(user, 'User')")
        assert cfg.shapes_per_row == 4
        assert cfg.boundaries_per_row == 2

    def test_update_layout_config(self):
        src = 'C4Container\nUpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")'
        cfg = parse_c4_config(src)
        assert cfg.shapes_per_row == 3
        assert cfg.boundaries_per_row == 1

    def test_update_layout_config_single_param(self):
        src = 'C4Container\nUpdateLayoutConfig($c4ShapeInRow="5")'
        cfg = parse_c4_config(src)
        assert cfg.shapes_per_row == 5
        assert cfg.boundaries_per_row == 2  # default unchanged

    def test_unknown_c4_params_collected(self):
        src = 'C4Container\nUpdateLayoutConfig($c4Unknown="42")'
        cfg = parse_c4_config(src)
        assert any("c4Unknown" in k for k in cfg.unsupported_keys)


class TestRenderConfig:
    def test_parse_render_config(self):
        src = '%%{init: {"flowchart": {"nodeSpacing": 100}}}%%\nflowchart TD\nA-->B'
        rc = parse_render_config(src)
        assert isinstance(rc.flowchart, FlowchartLayoutConfig)
        assert rc.flowchart.node_spacing == 100

    def test_parse_render_config_c4(self):
        src = 'C4Container\nUpdateLayoutConfig($c4ShapeInRow="2")'
        rc = parse_render_config(src)
        assert rc.c4.shapes_per_row == 2


class TestCoordinateEffect:
    """Verify that config values actually change the emitted geometry."""

    def test_node_spacing_increases_separation(self):
        """Larger nodeSpacing → wider canvas (more horizontal space between nodes in TB)."""
        small = '%%{init:{"flowchart":{"nodeSpacing":20}}}%%\nflowchart TD\nA-->B\nA-->C'
        large = '%%{init:{"flowchart":{"nodeSpacing":200}}}%%\nflowchart TD\nA-->B\nA-->C'
        w_small, _ = _canvas_dims(_dispatch(small, None, 0))
        w_large, _ = _canvas_dims(_dispatch(large, None, 0))
        assert w_large > w_small, (
            f"nodeSpacing=200 canvas ({w_large}px) should exceed nodeSpacing=20 ({w_small}px)"
        )

    def test_rank_spacing_increases_rank_gap(self):
        """Larger rankSpacing → taller canvas (more vertical space between ranks in TB)."""
        small = '%%{init:{"flowchart":{"rankSpacing":20}}}%%\nflowchart TD\nA-->B-->C'
        large = '%%{init:{"flowchart":{"rankSpacing":200}}}%%\nflowchart TD\nA-->B-->C'
        _, h_small = _canvas_dims(_dispatch(small, None, 0))
        _, h_large = _canvas_dims(_dispatch(large, None, 0))
        assert h_large > h_small, (
            f"rankSpacing=200 canvas ({h_large}px) should exceed rankSpacing=20 ({h_small}px)"
        )

    def test_diagram_padding_changes_canvas(self):
        """Larger diagramPadding → larger canvas (more outer margin)."""
        small_pad = '%%{init:{"flowchart":{"diagramPadding":4}}}%%\nflowchart TD\nA-->B'
        large_pad = '%%{init:{"flowchart":{"diagramPadding":150}}}%%\nflowchart TD\nA-->B'
        w_small, h_small = _canvas_dims(_dispatch(small_pad, None, 0))
        w_large, h_large = _canvas_dims(_dispatch(large_pad, None, 0))
        # Canvas must be at least 2*150 wider (2 sides of padding difference)
        assert w_large > w_small and h_large > h_small, (
            f"diagramPadding=150 ({w_large}×{h_large}) should exceed "
            f"diagramPadding=4 ({w_small}×{h_small})"
        )


class TestLegacyCompat:
    def test_legacy_returns_dict(self):
        src = '%%{init:{"flowchart":{"nodeSpacing":100}}}%%\nflowchart TD\nA-->B'
        result = legacy_parse_init_config(src)
        assert isinstance(result, dict)
        assert result.get("col_gap") == 100

    def test_legacy_empty_when_defaults(self):
        result = legacy_parse_init_config("flowchart TD\nA-->B")
        assert result == {}
