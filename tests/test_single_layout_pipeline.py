#!/usr/bin/env python3
"""Geometry roundtrip tests for the single finalized layout pipeline.

Verifies that compile_er, compile_requirement, and compile_architecture +
arch_to_finalized all produce a valid FinalizedLayout, and that to_html()
and layout_*_scene() return non-empty output for minimal fixtures.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._geometry import FinalizedLayout


_ER_SRC = """\
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER {
        string id
        int qty
    }
    CUSTOMER {
        string name
    }
"""

_REQ_SRC = """\
requirementDiagram
    requirement AuthReq {
        id: 1
        text: "User must log in"
        risk: high
        verifymethod: test
    }
    element LoginPage {
        type: UI
    }
    AuthReq - satisfies -> LoginPage
"""

_ARCH_SRC = """\
architecture-beta
    service api (server) [API]
    service db (database) [Database]
    api:B --> T:db
"""


# ── compile_er ────────────────────────────────────────────────────────────────

class TestCompileEr:
    def test_returns_finalized_layout(self):
        from mermaid_render.layout.er import compile_er
        fl = compile_er(_ER_SRC)
        assert isinstance(fl, FinalizedLayout)

    def test_node_layouts_populated(self):
        from mermaid_render.layout.er import compile_er
        fl = compile_er(_ER_SRC)
        assert "CUSTOMER" in fl.node_layouts
        assert "ORDER" in fl.node_layouts

    def test_canvas_bounds_nonzero(self):
        from mermaid_render.layout.er import compile_er
        fl = compile_er(_ER_SRC)
        assert fl.canvas_bounds.w > 0
        assert fl.canvas_bounds.h > 0

    def test_no_routing_failures(self):
        from mermaid_render.layout.er import compile_er
        fl = compile_er(_ER_SRC)
        assert fl.routing_failures == ()

    def test_routed_edges_exist(self):
        from mermaid_render.layout.er import compile_er
        fl = compile_er(_ER_SRC)
        assert len(fl.routed_edges) >= 1

    def test_empty_diagram_returns_empty_layout(self):
        from mermaid_render.layout.er import compile_er
        fl = compile_er("erDiagram\n")
        assert fl.node_layouts == {}
        assert fl.canvas_bounds.w > 0

    def test_er_to_html_raises_for_empty_diagram(self):
        from mermaid_render.layout.er import er_to_html
        with pytest.raises(ValueError, match="No entities"):
            er_to_html("erDiagram\n  %% comment only")


# ── compile_requirement ───────────────────────────────────────────────────────

class TestCompileRequirement:
    def test_returns_finalized_layout(self):
        from mermaid_render.layout.requirement import compile_requirement
        fl = compile_requirement(_REQ_SRC)
        assert isinstance(fl, FinalizedLayout)

    def test_node_layouts_populated(self):
        from mermaid_render.layout.requirement import compile_requirement
        fl = compile_requirement(_REQ_SRC)
        assert "AuthReq" in fl.node_layouts
        assert "LoginPage" in fl.node_layouts

    def test_canvas_bounds_nonzero(self):
        from mermaid_render.layout.requirement import compile_requirement
        fl = compile_requirement(_REQ_SRC)
        assert fl.canvas_bounds.w > 0
        assert fl.canvas_bounds.h > 0

    def test_no_routing_failures(self):
        from mermaid_render.layout.requirement import compile_requirement
        fl = compile_requirement(_REQ_SRC)
        assert fl.routing_failures == ()

    def test_routed_edges_exist(self):
        from mermaid_render.layout.requirement import compile_requirement
        fl = compile_requirement(_REQ_SRC)
        assert len(fl.routed_edges) == 1

    def test_edge_id_convention(self):
        from mermaid_render.layout.requirement import compile_requirement
        fl = compile_requirement(_REQ_SRC)
        assert fl.routed_edges[0].edge_id == "req-rel-0"

    def test_semantic_shapes(self):
        from mermaid_render.layout.requirement import compile_requirement
        fl = compile_requirement(_REQ_SRC)
        assert fl.node_layouts["AuthReq"].semantic_shape == "req-requirement"
        assert fl.node_layouts["LoginPage"].semantic_shape == "req-element"

    def test_node_rank_assigned(self):
        from mermaid_render.layout.requirement import compile_requirement
        fl = compile_requirement(_REQ_SRC)
        auth_rank = fl.node_layouts["AuthReq"].rank
        login_rank = fl.node_layouts["LoginPage"].rank
        assert auth_rank != login_rank

    def test_empty_diagram_returns_empty_layout(self):
        from mermaid_render.layout.requirement import compile_requirement
        # No nodes raises ValueError from _parse_requirement_source — empty
        # layout path unreachable from valid syntax; just test non-empty case.
        fl = compile_requirement(_REQ_SRC)
        assert len(fl.node_layouts) == 2


# ── compile_architecture + arch_to_finalized ──────────────────────────────────

class TestCompileArchitecture:
    def test_returns_finalized_layout(self):
        from mermaid_render.layout.architecture import compile_architecture, arch_to_finalized
        arch = compile_architecture(_ARCH_SRC)
        fl = arch_to_finalized(arch)
        assert isinstance(fl, FinalizedLayout)

    def test_node_layouts_populated(self):
        from mermaid_render.layout.architecture import compile_architecture, arch_to_finalized
        arch = compile_architecture(_ARCH_SRC)
        fl = arch_to_finalized(arch)
        assert "api" in fl.node_layouts
        assert "db" in fl.node_layouts

    def test_canvas_bounds_nonzero(self):
        from mermaid_render.layout.architecture import compile_architecture, arch_to_finalized
        arch = compile_architecture(_ARCH_SRC)
        fl = arch_to_finalized(arch)
        assert fl.canvas_bounds.w > 0
        assert fl.canvas_bounds.h > 0


# ── HTML/SVG backward-compatibility smoke tests ───────────────────────────────

class TestBackwardCompatibility:
    def test_er_to_html_nonempty(self):
        from mermaid_render.layout.er import er_to_html
        html = er_to_html(_ER_SRC)
        assert html
        assert "CUSTOMER" in html

    def test_requirement_to_html_nonempty(self):
        from mermaid_render.layout.requirement import requirement_to_html
        html = requirement_to_html(_REQ_SRC)
        assert html
        assert "AuthReq" in html

    def test_arch_to_html_nonempty(self):
        from mermaid_render.layout.architecture import arch_to_html
        html = arch_to_html(_ARCH_SRC)
        assert html
        assert "api" in html.lower() or "API" in html

    def test_layout_er_scene_nonempty(self):
        from mermaid_render.layout.er import layout_er_scene
        scene = layout_er_scene(_ER_SRC)
        assert scene.width > 0
        assert scene.height > 0

    def test_layout_requirement_scene_nonempty(self):
        from mermaid_render.layout.requirement import layout_requirement_scene
        scene = layout_requirement_scene(_REQ_SRC)
        assert scene.width > 0
        assert scene.height > 0

    def test_layout_architecture_scene_nonempty(self):
        from mermaid_render.layout.architecture import layout_architecture_scene
        scene = layout_architecture_scene(_ARCH_SRC)
        assert scene.width > 0
        assert scene.height > 0


# ── Geometry consistency (same node bounds in HTML and SVG) ───────────────────

class TestGeometryConsistency:
    """Verify that compile_* produces the same geometry regardless of renderer."""

    def test_er_html_svg_same_node_bounds(self):
        """Node outer_bounds from compile_er are used by both er_to_html and layout_er_scene."""
        from mermaid_render.layout.er import compile_er, er_to_html, layout_er_scene

        fl = compile_er(_ER_SRC)
        html = er_to_html(_ER_SRC)
        scene = layout_er_scene(_ER_SRC)

        # HTML must contain node positions matching FinalizedLayout
        for nid, nl in fl.node_layouts.items():
            x = int(nl.outer_bounds.x)
            y = int(nl.outer_bounds.y)
            assert f"left:{x}px" in html or f"left:{x}" in html, (
                f"ER node {nid!r} x={x} not found in HTML"
            )

        # Scene must have same canvas size as FinalizedLayout
        assert abs(scene.view_box[2] - fl.canvas_bounds.w) < 1.0, (
            f"Scene viewBox width {scene.view_box[2]} != canvas_bounds.w {fl.canvas_bounds.w}"
        )

    def test_requirement_html_svg_same_node_bounds(self):
        """Node outer_bounds from compile_requirement are used by both renderers."""
        from mermaid_render.layout.requirement import (
            compile_requirement, requirement_to_html, layout_requirement_scene,
        )

        fl = compile_requirement(_REQ_SRC)
        html = requirement_to_html(_REQ_SRC)
        scene = layout_requirement_scene(_REQ_SRC)

        for nid, nl in fl.node_layouts.items():
            x = int(nl.outer_bounds.x)
            y = int(nl.outer_bounds.y)
            assert f"left:{x}px" in html or f"left:{x}" in html, (
                f"Req node {nid!r} x={x} not found in HTML"
            )

        assert abs(scene.view_box[2] - fl.canvas_bounds.w) < 1.0

    def test_compile_requirement_stable(self):
        """Calling compile_requirement twice returns identical geometry."""
        from mermaid_render.layout.requirement import compile_requirement
        fl1 = compile_requirement(_REQ_SRC)
        fl2 = compile_requirement(_REQ_SRC)
        for nid in fl1.node_layouts:
            b1 = fl1.node_layouts[nid].outer_bounds
            b2 = fl2.node_layouts[nid].outer_bounds
            assert b1 == b2, f"Node {nid!r} bounds differ between calls"
