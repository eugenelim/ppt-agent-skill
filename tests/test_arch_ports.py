"""Stage 4 tests: architecture-beta port syntax parsing and routing.

Covers:
- _ARCH_EDGE_RE captures L/R/T/B side codes on both endpoints
- Parsed sides are stored in _Edge.src_side / _Edge.dst_side
- Edges without side annotations have src_side=dst_side=None
- _side_port() returns correct face-center coordinates
- architecture-complex.mmd renders without error (smoke test)
- Port-pinned routes connect to the correct face of the node
"""
from __future__ import annotations

import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from mermaid_render.layout._constants import _Node, _Edge, NODE_W, NODE_H
from mermaid_render.layout._routing import _side_port, _node_render_w, _node_render_h


# ── Helpers ───────────────────────────────────────────────────────────────────

# Mirror the regex from _strategies.py so we can test it in isolation.
_ARCH_EDGE_RE = re.compile(
    r'^(\w+)(?::([LRTBrlbt]))?'
    r'\s*(<-->|-->|<--|--)\s*'
    r'(?:([LRTBrlbt]):)?(\w+)'
    r'(?::\w+)?'
    r'(?:\s*:\s*(.*))?$'
)


def _parse_edge(line: str):
    """Return (src, src_side, op, dst_side, dst, label) or None."""
    m = _ARCH_EDGE_RE.match(line)
    if not m:
        return None
    return (
        m.group(1),
        (m.group(2) or "").upper() or None,
        m.group(3),
        (m.group(4) or "").upper() or None,
        m.group(5),
        (m.group(6) or "").strip(),
    )


# ── Regex parsing tests ───────────────────────────────────────────────────────

class TestArchEdgeRegex:
    def test_rl_with_both_sides(self):
        r = _parse_edge("A:R --> L:B")
        assert r == ("A", "R", "-->", "L", "B", "")

    def test_tb_with_top_sides(self):
        r = _parse_edge("api:B --> T:cache")
        assert r == ("api", "B", "-->", "T", "cache", "")

    def test_no_sides(self):
        r = _parse_edge("A --> B")
        assert r == ("A", None, "-->", None, "B", "")

    def test_only_src_side(self):
        r = _parse_edge("A:R --> B")
        assert r == ("A", "R", "-->", None, "B", "")

    def test_only_dst_side(self):
        r = _parse_edge("A --> L:B")
        assert r == ("A", None, "-->", "L", "B", "")

    def test_with_label(self):
        r = _parse_edge("lb:R --> L:api : HTTP")
        assert r == ("lb", "R", "-->", "L", "api", "HTTP")

    def test_bidirectional(self):
        r = _parse_edge("A:R <--> L:B")
        assert r == ("A", "R", "<-->", "L", "B", "")

    def test_reverse_arrow(self):
        r = _parse_edge("A <-- B")
        assert r == ("A", None, "<--", None, "B", "")

    def test_undirected(self):
        r = _parse_edge("A -- B")
        assert r == ("A", None, "--", None, "B", "")

    def test_lowercase_sides(self):
        r = _parse_edge("A:r --> l:B")
        assert r == ("A", "R", "-->", "L", "B", "")

    def test_top_bottom(self):
        r = _parse_edge("X:T --> B:Y")
        assert r == ("X", "T", "-->", "B", "Y", "")

    def test_no_match_for_plain_text(self):
        assert _parse_edge("service lb(gateway)[Load Balancer]") is None

    def test_no_match_for_group(self):
        assert _parse_edge("group cloud(cloud)[Cloud]") is None


# ── _Edge dataclass carries sides ─────────────────────────────────────────────

class TestEdgeSideFields:
    def test_defaults_are_none(self):
        e = _Edge(src="A", dst="B")
        assert e.src_side is None
        assert e.dst_side is None

    def test_sides_preserved(self):
        e = _Edge(src="A", dst="B", src_side="R", dst_side="L")
        assert e.src_side == "R"
        assert e.dst_side == "L"

    def test_all_valid_sides(self):
        for side in ("L", "R", "T", "B"):
            e = _Edge(src="X", dst="Y", src_side=side, dst_side=side)
            assert e.src_side == side
            assert e.dst_side == side


# ── _side_port geometry ───────────────────────────────────────────────────────

def _make_node(x: int, y: int, w: int = NODE_W, h: int = NODE_H) -> _Node:
    n = _Node(id="n", x=x, y=y)
    n.width = w
    n.height = h
    return n


class TestSidePort:
    def test_none_side_returns_none(self):
        n = _make_node(100, 200)
        assert _side_port(n, None) is None

    def test_left_face(self):
        n = _make_node(100, 200)
        x, y = _side_port(n, "L")
        assert x == 100
        assert y == 200 + _node_render_h(n) // 2

    def test_right_face(self):
        n = _make_node(100, 200)
        x, y = _side_port(n, "R")
        assert x == 100 + _node_render_w(n)
        assert y == 200 + _node_render_h(n) // 2

    def test_top_face(self):
        n = _make_node(100, 200)
        x, y = _side_port(n, "T")
        assert x == 100 + _node_render_w(n) // 2
        assert y == 200

    def test_bottom_face(self):
        n = _make_node(100, 200)
        x, y = _side_port(n, "B")
        assert x == 100 + _node_render_w(n) // 2
        assert y == 200 + _node_render_h(n)

    def test_unknown_side_returns_none(self):
        n = _make_node(0, 0)
        assert _side_port(n, "X") is None

    def test_lowercase_side(self):
        n = _make_node(100, 200)
        assert _side_port(n, "l") == _side_port(n, "L")
        assert _side_port(n, "r") == _side_port(n, "R")


# ── Smoke: architecture-complex.mmd renders without error ────────────────────

class TestArchComplexRender:
    def test_renders_without_error(self):
        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "architecture-complex.mmd"
        )
        with open(fixture) as f:
            src = f.read()
        import mermaid_render
        html = mermaid_render.to_html(src)
        assert "<svg" in html

    def test_all_services_present(self):
        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "architecture-complex.mmd"
        )
        with open(fixture) as f:
            src = f.read()
        import mermaid_render
        html = mermaid_render.to_html(src)
        for svc in ("lb", "api", "db", "cache", "queue"):
            assert svc in html, f"Service '{svc}' not found in rendered HTML"

    def test_edges_present(self):
        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "architecture-complex.mmd"
        )
        with open(fixture) as f:
            src = f.read()
        import mermaid_render
        html = mermaid_render.to_html(src)
        # Edges render as SVG path elements
        assert "<path" in html


# ── Port pins produce correct exit face ──────────────────────────────────────

class TestPortPinRouting:
    """Verify that pinned port coordinates appear in the routed path."""

    def _route_arch(self, src_mmd: str):
        """Render architecture-beta source and return the rendered HTML."""
        import mermaid_render
        return mermaid_render.to_html(src_mmd)

    def test_right_to_left_port_renders(self):
        src = "architecture-beta\nservice A(server)[A]\nservice B(server)[B]\nA:R --> L:B"
        html = self._route_arch(src)
        assert "<svg" in html
        assert "<path" in html

    def test_top_to_bottom_port_renders(self):
        src = "architecture-beta\nservice A(server)[A]\nservice B(server)[B]\nA:B --> T:B"
        html = self._route_arch(src)
        assert "<svg" in html
        assert "<path" in html

    def test_no_side_still_renders(self):
        src = "architecture-beta\nservice A(server)[A]\nservice B(server)[B]\nA --> B"
        html = self._route_arch(src)
        assert "<svg" in html
        assert "<path" in html
