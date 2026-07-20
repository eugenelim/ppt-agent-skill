#!/usr/bin/env python3
"""Regression tests for architecture-beta renderer fixes.

Covers:
1. Indentation-based group containment (basic fixture)
2. LR layout direction (horizontal node flow)
3. ``<--`` reverse-arrow support
4. ``<-->`` bidirectional arrow (two edges emitted)
5. Junction nodes rendered as invisible routing points
6. Icon fallback for un-mapped hints (e.g. "pipeline")
7. ``in <group>`` explicit syntax still works (complex fixture)
8. Nested groups via ``in <parent>`` syntax
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _layout_architecture, _ARCH_EDGE_RE, _ARCH_GRP_RE, _ARCH_JCT_RE


# ── helpers ───────────────────────────────────────────────────────────────────

def _dispatch_arch(src: str, width: int = 1200) -> str:
    return _layout_architecture(src, "LR", width)


def _node_left(html: str, node_id: str) -> int | None:
    """Return the CSS left value for the given node-id div, or None if not found.

    The HTML emits ``<div ... data-node-id="X" style="... left:Npx; top:Mpx; ...">``
    so the position attributes follow the node-id in the source.
    """
    idx = html.find(f'data-node-id="{node_id}"')
    if idx < 0:
        return None
    snippet = html[idx:idx + 300]
    m = re.search(r"left:(\d+)px", snippet)
    return int(m.group(1)) if m else None


def _node_top(html: str, node_id: str) -> int | None:
    idx = html.find(f'data-node-id="{node_id}"')
    if idx < 0:
        return None
    snippet = html[idx:idx + 300]
    m = re.search(r"top:(\d+)px", snippet)
    return int(m.group(1)) if m else None


# ── A1: regex checks ──────────────────────────────────────────────────────────

class TestArchRegexes:
    """Unit-level checks on the three compiled regexes."""

    def test_edge_re_forward_with_sides(self):
        m = _ARCH_EDGE_RE.match("api:R --> L:lambda")
        assert m is not None
        assert m.group(1) == "api"
        assert m.group(2) == "-->"
        assert m.group(3) == "lambda"

    def test_edge_re_reverse(self):
        m = _ARCH_EDGE_RE.match("api <-- lambda")
        assert m is not None
        assert m.group(1) == "api"
        assert m.group(2) == "<--"
        assert m.group(3) == "lambda"

    def test_edge_re_bidirectional(self):
        m = _ARCH_EDGE_RE.match("api <--> lambda")
        assert m is not None
        assert m.group(2) == "<-->"

    def test_edge_re_undirected(self):
        m = _ARCH_EDGE_RE.match("api -- lambda")
        assert m is not None
        assert m.group(2) == "--"

    def test_edge_re_with_label(self):
        m = _ARCH_EDGE_RE.match("api:R --> L:db : HTTPS")
        assert m is not None
        assert m.group(4) == "HTTPS"

    def test_group_re_no_longer_matches_junction(self):
        """After the fix _ARCH_GRP_RE must NOT match 'junction' lines."""
        m = _ARCH_GRP_RE.match("junction jLeft")
        assert m is None

    def test_group_re_with_in(self):
        m = _ARCH_GRP_RE.match("group az1[AZ-1] in vpc")
        assert m is not None
        assert m.group(1) == "az1"
        assert m.group(3) == "vpc"

    def test_junction_re(self):
        m = _ARCH_JCT_RE.match("junction jLeft")
        assert m is not None
        assert m.group(1) == "jLeft"


# ── A2: indentation-based group containment ───────────────────────────────────

class TestIndentGroupContainment:
    """Services indented under a group block become members of that group."""

    FIXTURE = Path(__file__).parent / "fixtures" / "architecture-basic.mmd"

    def test_basic_fixture_renders(self):
        html = _dispatch_arch(self.FIXTURE.read_text())
        assert "diagram mermaid-layout" in html

    def test_group_boundary_rendered(self):
        """The AWS group bounding box is rendered as a dashed container."""
        html = _dispatch_arch(self.FIXTURE.read_text())
        assert "diagram-group" in html

    def test_group_label_visible(self):
        """The group label 'AWS' appears in the rendered HTML."""
        html = _dispatch_arch(self.FIXTURE.read_text())
        assert "AWS" in html

    def test_all_services_present(self):
        html = _dispatch_arch(self.FIXTURE.read_text())
        for nid in ("api", "lambda", "db"):
            assert f'data-node-id="{nid}"' in html, f"{nid} not rendered"

    def test_lr_layout_horizontal(self):
        """In LR layout the three services should be at increasing x (left) positions."""
        html = _dispatch_arch(self.FIXTURE.read_text())
        left_api = _node_left(html, "api")
        left_lambda = _node_left(html, "lambda")
        left_db = _node_left(html, "db")
        assert left_api is not None
        assert left_lambda is not None
        assert left_db is not None
        assert left_api < left_lambda < left_db, (
            f"Expected api ({left_api}) < lambda ({left_lambda}) < db ({left_db})"
        )

    def test_same_rank_nodes_at_same_y(self):
        """Nodes in the same rank (same column in LR) should share the same top value."""
        html = _dispatch_arch(self.FIXTURE.read_text())
        top_api = _node_top(html, "api")
        top_lambda = _node_top(html, "lambda")
        assert top_api == top_lambda, (
            f"api and lambda should be at same y; got {top_api} vs {top_lambda}"
        )

    def test_edges_present(self):
        html = _dispatch_arch(self.FIXTURE.read_text())
        assert 'data-src="api"' in html
        assert 'data-dst="lambda"' in html


# ── A3: explicit in-group syntax ──────────────────────────────────────────────

class TestExplicitInGroup:
    """``service X in group`` explicit syntax continues to work."""

    FIXTURE = Path(__file__).parent / "fixtures" / "architecture-complex.mmd"

    def test_complex_fixture_renders(self):
        html = _dispatch_arch(self.FIXTURE.read_text())
        assert "diagram mermaid-layout" in html

    def test_cloud_group_rendered(self):
        html = _dispatch_arch(self.FIXTURE.read_text())
        assert "Cloud Platform" in html
        assert "diagram-group" in html

    def test_all_five_services(self):
        html = _dispatch_arch(self.FIXTURE.read_text())
        for nid in ("lb", "api", "db", "cache", "queue"):
            assert f'data-node-id="{nid}"' in html, f"{nid} not rendered"

    def test_edges_from_lb(self):
        html = _dispatch_arch(self.FIXTURE.read_text())
        assert 'data-src="lb"' in html


# ── A4: reverse arrow <-- ─────────────────────────────────────────────────────

class TestReverseArrow:
    """``A <-- B`` emits a B→A edge (src and dst swapped)."""

    SRC = "architecture-beta\n  service a(server)[A]\n  service b(database)[B]\n  a <-- b"

    def test_reverse_edge_emitted(self):
        html = _dispatch_arch(self.SRC)
        assert 'data-src="b"' in html
        assert 'data-dst="a"' in html

    def test_forward_edge_not_emitted(self):
        html = _dispatch_arch(self.SRC)
        # There should be no edge with src=a, dst=b
        assert not ('data-src="a"' in html and 'data-dst="b"' in html)


# ── A5: bidirectional arrow <--> ──────────────────────────────────────────────

class TestBidirectionalArrow:
    """``A <--> B`` emits BOTH A→B and B→A edges."""

    SRC = "architecture-beta\n  service a(server)[A]\n  service b(database)[B]\n  a <--> b"

    def test_forward_edge_emitted(self):
        html = _dispatch_arch(self.SRC)
        assert 'data-src="a"' in html
        assert 'data-dst="b"' in html

    def test_reverse_edge_also_emitted(self):
        html = _dispatch_arch(self.SRC)
        assert 'data-src="b"' in html
        assert 'data-dst="a"' in html


# ── A6: junction nodes ────────────────────────────────────────────────────────

class TestJunctionNodes:
    """``junction id`` creates an invisible routing point, not a group."""

    SRC = (
        "architecture-beta\n"
        "  service a(server)[A]\n"
        "  junction j\n"
        "  service b(database)[B]\n"
        "  a --> j\n"
        "  j --> b"
    )

    def test_services_rendered(self):
        html = _dispatch_arch(self.SRC)
        assert 'data-node-id="a"' in html
        assert 'data-node-id="b"' in html

    def test_junction_has_no_visible_label(self):
        """Junction nodes are is_dummy=True and render as zero-size divs."""
        html = _dispatch_arch(self.SRC)
        # dummy nodes render as <div style="...width:0; height:0; overflow:hidden;">
        assert "width:0" in html or "overflow:hidden" in html

    def test_junction_not_treated_as_group(self):
        """Junction nodes should not create a group boundary box."""
        html = _dispatch_arch(self.SRC)
        # The only diagram-group (if any) must not be for the junction
        groups = re.findall(r'data-group-id="(\w+)"', html)
        assert "j" not in groups


# ── A7: icon fallback ─────────────────────────────────────────────────────────

class TestIconFallback:
    """Icon hints not in _ARCH_ICON_MAP fall back to the hint name directly."""

    def test_pipeline_icon_loaded(self):
        """'pipeline' hint loads pipeline.svg (not in _ARCH_ICON_MAP, but file exists)."""
        src = "architecture-beta\n  service q(pipeline)[Queue]"
        html = _dispatch_arch(src)
        # pipeline.svg is inlined as an SVG element
        assert "<svg" in html, "Expected inline SVG icon for pipeline hint"

    def test_mapped_hint_still_works(self):
        """'database' hint (which IS in _ARCH_ICON_MAP) continues to load correctly."""
        src = "architecture-beta\n  service db(database)[Database]"
        html = _dispatch_arch(src)
        assert "<svg" in html


# ── A8: ``-- `` undirected edge ───────────────────────────────────────────────

class TestUndirectedEdge:
    """``A -- B`` renders without an arrowhead (arrow=False)."""

    def test_undirected_edge_rendered(self):
        src = "architecture-beta\n  service a(server)[A]\n  service b(database)[B]\n  a -- b"
        html = _dispatch_arch(src)
        assert 'data-src="a"' in html
        assert 'data-dst="b"' in html
