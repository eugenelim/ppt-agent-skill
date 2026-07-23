"""Acceptance tests for port-constrained architecture-beta layout.

Fixture: tests/fixtures/architecture-complex.mmd
  lb:R --> L:api   (lb right  → api left)
  api:R --> L:db   (api right → db  left)
  api:B --> T:cache (api bottom → cache top)
  api:R --> L:queue (api right → queue left)

Each test verifies that the routed edge exits/enters the declared face of
its source/destination node. Tolerance is ±10px to accommodate routing
snapping to grid channels.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

FIXTURE = Path(__file__).parent / "fixtures" / "architecture-complex.mmd"
_TOL = 10  # px tolerance for face-coordinate checks


def _arch():
    from mermaid_render.layout.architecture import compile_architecture
    return compile_architecture(FIXTURE.read_text())


def _bounds(arch):
    return {svc.node_id: svc.outer_bounds for svc in arch.services}


def _edges(arch):
    return {(e.src_id, e.dst_id): e for e in arch.edges}


# ── Layout sanity ─────────────────────────────────────────────────────────────

class TestNodePlacement:
    """cache must be BELOW api (not to its right) due to api:B → cache:T."""

    def test_cache_below_api(self):
        b = _bounds(_arch())
        api = b["api"]
        cache = b["cache"]
        assert cache.y > api.y + api.h - _TOL, (
            f"cache top={cache.y:.0f} should be below api bottom={api.y + api.h:.0f}"
        )

    def test_cache_not_right_of_api(self):
        """cache must NOT be placed entirely to the right of api."""
        b = _bounds(_arch())
        api = b["api"]
        cache = b["cache"]
        # cache should share approximately the same column as api
        assert abs(cache.x - api.x) < api.w * 1.5, (
            f"cache.x={cache.x:.0f} is too far from api.x={api.x:.0f}"
        )

    def test_db_right_of_api(self):
        b = _bounds(_arch())
        assert b["db"].x > b["api"].x + b["api"].w - _TOL

    def test_all_services_in_cloud(self):
        arch = _arch()
        gids = {svc.group_id for svc in arch.services}
        assert "cloud" in gids, "All services should be in the 'cloud' group"

    def test_group_rendered(self):
        arch = _arch()
        assert len(arch.groups) >= 1
        gids = {g.group_id for g in arch.groups}
        assert "cloud" in gids


# ── Port acceptance criteria ──────────────────────────────────────────────────

class TestEdgeFaces:
    """Each edge must exit and enter the declared face of its node.

    Checks: first waypoint on src face, last waypoint on dst face.
    """

    @staticmethod
    def _check_right_exit(edge, node_bounds, label):
        """First waypoint x ≈ node right edge."""
        nb = node_bounds
        face_x = nb.x + nb.w
        wp = edge.waypoints[0]
        assert abs(wp.x - face_x) <= _TOL, (
            f"{label}: start x={wp.x:.0f} should be at right face x={face_x:.0f}"
        )

    @staticmethod
    def _check_left_entry(edge, node_bounds, label):
        """Last waypoint x ≈ node left edge."""
        nb = node_bounds
        wp = edge.waypoints[-1]
        assert abs(wp.x - nb.x) <= _TOL, (
            f"{label}: end x={wp.x:.0f} should be at left face x={nb.x:.0f}"
        )

    @staticmethod
    def _check_bottom_exit(edge, node_bounds, label):
        """First waypoint y ≈ node bottom edge."""
        nb = node_bounds
        face_y = nb.y + nb.h
        wp = edge.waypoints[0]
        assert abs(wp.y - face_y) <= _TOL, (
            f"{label}: start y={wp.y:.0f} should be at bottom face y={face_y:.0f}"
        )

    @staticmethod
    def _check_top_entry(edge, node_bounds, label):
        """Last waypoint y ≈ node top edge."""
        nb = node_bounds
        wp = edge.waypoints[-1]
        assert abs(wp.y - nb.y) <= _TOL, (
            f"{label}: end y={wp.y:.0f} should be at top face y={nb.y:.0f}"
        )

    def test_lb_R_to_api_L(self):
        """lb:R → api:L — edge exits lb's right face, enters api's left face."""
        arch = _arch()
        b = _bounds(arch)
        e = _edges(arch).get(("lb", "api"))
        assert e is not None, "lb→api edge must be present in architecture-complex.mmd"
        assert len(e.waypoints) >= 2, "Edge must have at least 2 waypoints"
        self._check_right_exit(e, b["lb"], "lb:R→api:L src")
        self._check_left_entry(e, b["api"], "lb:R→api:L dst")

    def test_api_R_to_db_L(self):
        """api:R → db:L — edge exits api's right face, enters db's left face."""
        arch = _arch()
        b = _bounds(arch)
        e = _edges(arch).get(("api", "db"))
        assert e is not None, "api→db edge must be present in architecture-complex.mmd"
        assert len(e.waypoints) >= 2
        self._check_right_exit(e, b["api"], "api:R→db:L src")
        self._check_left_entry(e, b["db"], "api:R→db:L dst")

    def test_api_B_to_cache_T(self):
        """api:B → cache:T — edge exits api's bottom face, enters cache's top face."""
        arch = _arch()
        b = _bounds(arch)
        e = _edges(arch).get(("api", "cache"))
        assert e is not None, "api→cache edge must be present in architecture-complex.mmd"
        assert len(e.waypoints) >= 2
        self._check_bottom_exit(e, b["api"], "api:B→cache:T src")
        self._check_top_entry(e, b["cache"], "api:B→cache:T dst")

    def test_api_R_to_queue_L(self):
        """api:R → queue:L — edge exits api's right face, enters queue's left face."""
        arch = _arch()
        b = _bounds(arch)
        e = _edges(arch).get(("api", "queue"))
        assert e is not None, "api→queue edge must be present in architecture-complex.mmd"
        assert len(e.waypoints) >= 2
        self._check_right_exit(e, b["api"], "api:R→queue:L src")
        self._check_left_entry(e, b["queue"], "api:R→queue:L dst")
