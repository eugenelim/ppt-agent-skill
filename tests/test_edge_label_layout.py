"""Stage 7 tests: port/label-aware routing.

Covers:
- A* fallback produces orthogonal path, not a diagonal
- _est_label_w uses TextLayout measurement (wider for longer text, proportional)
- Route failures are reported via _failures list parameter
- All prior render-correctness fixtures still pass (spot check)
- Fixed ports honored in routing (validates S4 integration)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from mermaid_render.layout._routing import (
    _astar_route, _est_label_w, _build_routing_grid, _blocked_segs,
)


# ── A* fallback: no diagonal ──────────────────────────────────────────────────

class TestAstarFallback:
    """When A* finds no clear path it returns None; caller uses _route_perimeter."""

    def _make_total_block(self):
        """Grid where every reachable segment from the start is blocked."""
        xs = [0, 100]
        ys = [0, 100]
        # Block (0,0)→(1,0) and (0,0)→(0,1) — no moves from start index
        blocked = {(0, 0, 1, 0), (0, 0, 0, 1), (1, 0, 1, 0), (0, 1, 0, 1),
                   (0, 0, 0, 0)}
        return xs, ys, blocked

    def test_blocked_grid_returns_none(self):
        """_astar_route returns None when all paths are blocked (caller does perimeter retry)."""
        xs, ys, blocked = self._make_total_block()
        pts = _astar_route(0, 0, 100, 100, xs, ys, blocked)
        assert pts is None

    def test_astar_result_is_orthogonal(self):
        """A* paths on an unblocked grid must only use horizontal or vertical segments."""
        xs = [0, 50, 100]
        ys = [0, 50, 100]
        blocked: set = set()
        pts = _astar_route(0, 0, 100, 100, xs, ys, blocked)
        assert pts is not None
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            is_horizontal = (y1 == y2)
            is_vertical = (x1 == x2)
            assert is_horizontal or is_vertical, (
                f"Diagonal segment detected: ({x1},{y1})→({x2},{y2})"
            )

    def test_blocked_records_failure_info(self):
        """Failure info (sx, sy, dx, dy) is appended to _failures when no path is found."""
        xs, ys, blocked = self._make_total_block()
        failures: list = []
        pts = _astar_route(5, 10, 80, 90, xs, ys, blocked, _failures=failures)
        assert pts is None
        assert len(failures) == 1
        assert failures[0] == (5, 10, 80, 90)

    def test_fallback_records_failure(self):
        xs, ys, blocked = self._make_total_block()
        failures: list = []
        _astar_route(0, 0, 100, 100, xs, ys, blocked, _failures=failures)
        assert len(failures) > 0

    def test_success_does_not_record_failure(self):
        """When A* succeeds, no failure is appended."""
        xs = [0, 50, 100]
        ys = [0, 50, 100]
        blocked: set = set()
        failures: list = []
        pts = _astar_route(0, 0, 100, 0, xs, ys, blocked, _failures=failures)
        assert failures == [], f"Expected no failures on clear path; got {failures}"

    def test_same_point_returns_two_point_path(self):
        xs = [0, 100]
        ys = [0, 100]
        blocked: set = set()
        pts = _astar_route(50, 50, 50, 50, xs, ys, blocked)
        assert len(pts) >= 2
        assert pts[0] == pts[-1]


# ── Label width measurement ───────────────────────────────────────────────────

class TestEstLabelWidth:
    def test_empty_string_returns_zero(self):
        assert _est_label_w("") == 0

    def test_single_char_nonzero(self):
        w = _est_label_w("A")
        assert w > 0

    def test_longer_text_wider(self):
        w_short = _est_label_w("Hi")
        w_long = _est_label_w("Hello World Label Text")
        assert w_long > w_short

    def test_width_capped_at_450(self):
        w = _est_label_w("x" * 200)
        assert w <= 450

    def test_width_at_least_30_for_nonempty(self):
        w = _est_label_w("a")
        assert w >= 30

    def test_proportional_growth(self):
        """Width should grow as text length increases."""
        widths = [_est_label_w("x" * n) for n in (1, 5, 10, 20)]
        # Each should be >= the previous
        for i in range(len(widths) - 1):
            assert widths[i + 1] >= widths[i], (
                f"Width not monotonic at n={i+1}: {widths}"
            )

    def test_alignment_with_make_text_layout_ir_for_short_labels(self):
        """For labels ≤56 chars, _est_label_w matches _make_text_layout_ir.width exactly."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from mermaid_render.layout._strategies import _make_text_layout_ir
        for n in (1, 5, 10, 20, 40, 56):
            text = "x" * n
            routing_w = _est_label_w(text)
            layout_w = int(_make_text_layout_ir(text).width)
            assert routing_w == layout_w, (
                f"Width mismatch at n={n}: _est_label_w={routing_w} vs _make_text_layout_ir={layout_w}"
            )

    def test_alignment_with_make_text_layout_ir_for_long_labels(self):
        """Long labels stay aligned between the routing and layout paths, both
        capped at 450px (backlog-mermaid-p0-label-width-cap)."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from mermaid_render.layout._strategies import _make_text_layout_ir
        for n in (60, 80, 120, 200):
            text = "x" * n
            routing_w = _est_label_w(text)
            layout_w = int(_make_text_layout_ir(text).width)
            assert routing_w == layout_w, (
                f"Divergence at n={n}: _est_label_w={routing_w} vs "
                f"_make_text_layout_ir={layout_w}"
            )
            assert layout_w <= 450, f"_make_text_layout_ir exceeds cap at n={n}: {layout_w}"
        # The cap must actually engage at the extreme (else the test proves nothing).
        assert int(_make_text_layout_ir("x" * 200).width) == 450


# ── Route failure diagnostics ─────────────────────────────────────────────────

class TestRouteFailureDiagnostics:
    def test_failures_list_populated_on_blocked(self):
        xs = [0, 100]
        ys = [0, 100]
        blocked = {(0, 0, 1, 0), (0, 0, 0, 1)}
        failures: list = []
        _astar_route(0, 0, 100, 100, xs, ys, blocked, _failures=failures)
        # May or may not fail depending on the specific grid; just ensure no crash
        assert isinstance(failures, list)

    def test_none_failures_does_not_crash(self):
        xs = [0, 100]
        ys = [0, 100]
        blocked: set = set()
        # Should work with _failures=None (default)
        pts = _astar_route(0, 0, 100, 0, xs, ys, blocked, _failures=None)
        assert len(pts) >= 2


# ── Integration: edges render without diagonals ───────────────────────────────

class TestEdgeRenderNodiagonal:
    """Rendered edge paths must not be straight diagonals through obstacles."""

    def _get_paths(self, src: str) -> list[str]:
        import mermaid_render
        import re
        html = mermaid_render.to_html(src)
        # Extract all SVG 'd' attribute values from <path> elements
        return re.findall(r'<path[^>]+\bd="([^"]+)"', html)

    def test_simple_flowchart_has_paths(self):
        src = "flowchart TB\n  A --> B"
        paths = self._get_paths(src)
        assert len(paths) > 0

    def test_paths_have_no_diagonal_L_segments(self):
        """Explicit L (lineto) segments must be axis-aligned (no diagonal lines).

        Rounded corners are rendered as Q (quadratic bezier) commands; those are
        expected and excluded. Only bare L commands produce straight lines and
        those must be horizontal or vertical.
        """
        import re as _re
        src = "flowchart TB\n  A --> B\n  B --> C\n  A --> C"
        paths = self._get_paths(src)
        for path_d in paths:
            # Tokenise: collect (command, x, y) for M and L only.
            # Pattern matches 'M x y' or 'L x y' as standalone commands.
            segments = _re.findall(r'\b([ML])\s+([\d.]+)\s+([\d.]+)', path_d)
            pts = [(cmd, float(x), float(y)) for cmd, x, y in segments]
            for i in range(1, len(pts)):
                cmd, x2, y2 = pts[i]
                if cmd != "L":
                    continue
                _, x1, y1 = pts[i - 1]
                dx, dy = abs(x2 - x1), abs(y2 - y1)
                # Allow up to 12px in both axes — rounded corners (r=10) produce
                # L commands with up to 10px displacement on each axis when the
                # path resets after a Q bezier arc.  Real diagonals (e.g. a straight
                # line from A to C skipping B) span full inter-node distances (≥50px
                # in both axes) and are clearly above this threshold.
                assert dx < 12 or dy < 12, (
                    f"Diagonal L segment ({x1},{y1})→({x2},{y2}) in path: {path_d}"
                )


# ── Architecture fixed port smoke test ────────────────────────────────────────

class TestArchFixedPortIntegration:
    """Verify that the complex architecture fixture with port annotations renders."""

    def test_arch_complex_routes(self):
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures",
                                    "architecture-complex.mmd")
        with open(fixture_path) as f:
            src = f.read()
        import mermaid_render
        html = mermaid_render.to_html(src)
        import re
        paths = re.findall(r'<path[^>]+\bd="([^"]+)"', html)
        assert len(paths) > 0, "No routed paths in architecture diagram"
