"""Route contract tests using the new terminal-normal validation rule names.

Covers AC12 from docs/specs/flowchart-connector-attachment/spec.md.
Tests that validate_routes() emits the correct rule names for the new checks:
  terminal_normal_source, terminal_normal_target, orthogonal_trunk
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mermaid_render.layout.port_planner import PortCandidate, RouteCandidate
from mermaid_render.layout.route_validation import validate_routes


def _pc(
    node_id: str,
    x: float,
    y: float,
    *,
    normal: tuple[float, float] = (1.0, 0.0),
    side: str = "right",
) -> PortCandidate:
    return PortCandidate(
        edge_id="e1",
        node_id=node_id,
        side=side,
        normalized_offset=0.5,
        point=(x, y),
        outward_normal=normal,
        fixed_side=False,
        preference_penalty=0.0,
    )


def _route(*pts: tuple[float, float],
           src_normal: tuple[float, float] = (1.0, 0.0),
           dst_normal: tuple[float, float] = (-1.0, 0.0)) -> RouteCandidate:
    src = _pc("A", pts[0][0], pts[0][1], normal=src_normal)
    dst = _pc("B", pts[-1][0], pts[-1][1], normal=dst_normal)
    total_len = sum(
        math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
        for i in range(len(pts)-1)
    )
    return RouteCandidate("e1", src, dst, pts, 0, total_len, 0, 0.0, 0.0)


# ── terminal_normal_source ────────────────────────────────────────────────────

class TestTerminalNormalSource:
    def test_aligned_source_no_error(self) -> None:
        """Source departs along (1,0); first segment is rightward — OK."""
        r = _route((0.0, 50.0), (100.0, 50.0), (200.0, 50.0),
                   src_normal=(1.0, 0.0), dst_normal=(-1.0, 0.0))
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "terminal_normal_source" not in rules

    def test_misaligned_source_fires(self) -> None:
        """Source normal is (1,0) but first segment is upward — fires."""
        r = _route((0.0, 0.0), (0.0, 100.0), (100.0, 100.0),
                   src_normal=(1.0, 0.0), dst_normal=(-1.0, 0.0))
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "terminal_normal_source" in rules

    def test_diagonal_source_aligned_with_normal(self) -> None:
        """Diagonal stub (45°) aligned with normal (0.707, 0.707) — OK."""
        nx, ny = math.cos(math.radians(45)), math.sin(math.radians(45))
        # First segment goes along (1, 1) direction from (0,0) to (20,20)
        r = _route((0.0, 0.0), (20.0, 20.0), (100.0, 20.0),
                   src_normal=(nx, ny), dst_normal=(-1.0, 0.0))
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "terminal_normal_source" not in rules

    def test_center_port_source_exempt(self) -> None:
        """Center port has outward_normal=(0,0) — terminal_normal_source skipped."""
        r = _route((50.0, 50.0), (200.0, 50.0),
                   src_normal=(0.0, 0.0), dst_normal=(-1.0, 0.0))
        errors = validate_routes([r])
        assert not any(e.rule == "terminal_normal_source" for e in errors)


# ── terminal_normal_target ────────────────────────────────────────────────────

class TestTerminalNormalTarget:
    def test_aligned_target_no_error(self) -> None:
        """Target enters from left (approach rightward, normal=-1,0) — OK."""
        r = _route((0.0, 50.0), (100.0, 50.0), (200.0, 50.0),
                   src_normal=(1.0, 0.0), dst_normal=(-1.0, 0.0))
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "terminal_normal_target" not in rules

    def test_misaligned_target_fires(self) -> None:
        """Target normal is (-1,0) but last segment approaches downward — fires."""
        r = _route((0.0, 0.0), (100.0, 0.0), (100.0, 50.0),
                   src_normal=(1.0, 0.0), dst_normal=(-1.0, 0.0))
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "terminal_normal_target" in rules

    def test_diagonal_target_aligned_with_normal(self) -> None:
        """Diagonal entry stub aligned with negative normal — OK.

        Target at (100, 100) with outward normal (√2/2, √2/2).
        Escape is at (114.14, 114.14). Last segment (escape → boundary) has
        direction (-√2/2, -√2/2), so dot(direction, -target_normal) = 1.0.
        """
        nx, ny = math.cos(math.radians(45)), math.sin(math.radians(45))
        stub = nx * 20.0  # ≈ 14.14
        target_x, target_y = 100.0, 100.0
        escape_x, escape_y = target_x + nx * stub, target_y + ny * stub
        r = _route(
            (0.0, 0.0),
            (0.0, escape_y),
            (escape_x, escape_y),
            (target_x, target_y),
            src_normal=(0.0, 1.0),
            dst_normal=(nx, ny),
        )
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "terminal_normal_target" not in rules

    def test_center_port_target_exempt(self) -> None:
        """Center target port (0,0) — terminal_normal_target skipped."""
        r = _route((0.0, 50.0), (150.0, 50.0),
                   src_normal=(1.0, 0.0), dst_normal=(0.0, 0.0))
        errors = validate_routes([r])
        assert not any(e.rule == "terminal_normal_target" for e in errors)


# ── orthogonal_trunk ──────────────────────────────────────────────────────────

class TestOrthogonalTrunk:
    def test_cardinal_trunk_no_error(self) -> None:
        """All interior segments are axis-aligned — OK."""
        r = _route((0.0, 0.0), (0.0, 50.0), (100.0, 50.0), (100.0, 100.0))
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "orthogonal_trunk" not in rules

    def test_diagonal_trunk_fires(self) -> None:
        """Diagonal interior segment (not terminal) fires orthogonal_trunk."""
        # [src_boundary, escape, diagonal_trunk_segment, escape, dst_boundary]
        r = _route(
            (0.0, 0.0),       # src boundary
            (20.0, 0.0),      # src escape (rightward stub OK)
            (100.0, 50.0),    # diagonal TRUNK segment — bad
            (180.0, 50.0),    # dst escape
            (200.0, 50.0),    # dst boundary
            src_normal=(1.0, 0.0),
            dst_normal=(-1.0, 0.0),
        )
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "orthogonal_trunk" in rules

    def test_only_two_points_no_trunk(self) -> None:
        """Two-point route has no trunk to check."""
        r = _route((0.0, 50.0), (200.0, 50.0),
                   src_normal=(1.0, 0.0), dst_normal=(-1.0, 0.0))
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "orthogonal_trunk" not in rules

    def test_three_point_route_no_trunk(self) -> None:
        """Three-point route: trunk range is empty — no orthogonal_trunk check."""
        r = _route((0.0, 0.0), (100.0, 0.0), (100.0, 50.0),
                   src_normal=(1.0, 0.0), dst_normal=(0.0, -1.0))
        errors = validate_routes([r])
        rules = {e.rule for e in errors}
        assert "orthogonal_trunk" not in rules

    def test_terminal_stubs_not_flagged(self) -> None:
        """Terminal stubs (first and last segments) are exempt from orthogonal_trunk."""
        # Diagonal stubs OK (they're normal stubs); trunk is axis-aligned
        nx, ny = math.cos(math.radians(45)), math.sin(math.radians(45))
        r = _route(
            (0.0, 0.0),       # src boundary
            (14.14, 14.14),   # src escape (diagonal stub along (1,1) normal)
            (14.14, 80.0),    # trunk down (vertical)
            (114.14, 80.0),   # trunk right (horizontal) — actually escape2
            (128.28, 94.14),  # dst boundary (diagonal stub)
            src_normal=(nx, ny),
            dst_normal=(nx, ny),
        )
        errors = validate_routes([r])
        # Trunk: pts[1]→pts[2] = (14.14,14.14)→(14.14,80.0) — vertical ✓
        #        pts[2]→pts[3] = (14.14,80.0)→(114.14,80.0) — horizontal ✓
        # (pts[3]→pts[4] is the target stub — not in trunk range)
        trunk_errors = [e for e in errors if e.rule == "orthogonal_trunk"]
        assert not trunk_errors, f"orthogonal_trunk falsely fired on stubs: {trunk_errors}"


# ── No legacy axis_aligned_terminal rule emitted ─────────────────────────────

def test_no_axis_aligned_terminal_rule() -> None:
    """The old axis_aligned_terminal rule must no longer be emitted."""
    # Route with diagonal first segment (source normal misaligned)
    r = _route((0.0, 0.0), (50.0, 50.0), (100.0, 50.0),
               src_normal=(1.0, 0.0), dst_normal=(-1.0, 0.0))
    errors = validate_routes([r])
    assert not any(e.rule == "axis_aligned_terminal" for e in errors), (
        "axis_aligned_terminal is a legacy rule name that should no longer be emitted"
    )
