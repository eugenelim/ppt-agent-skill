"""Authoritative real-ELK integration lane for architecture-beta.

Spec: docs/specs/architecture-fixed-port-integration/spec.md

Unlike the mocked conformance tests, this lane runs the *actual* elkjs
subprocess end-to-end — ``layout_with_elk`` is never patched. The lane is
opt-in (``--run-elk-integration`` or ``-m elk_integration``) and, when selected,
FAILS rather than skips if elkjs/node are unavailable (spec AC1): a green run of
this lane certifies that ELK produced the layout, not the Python fallback.

Coverage:
  - AC1: real elkjs subprocess; layout_backend == "elkjs"; fallback_reason None.
  - AC2: the Python router (_route_edges) is not called after ELK succeeds.
  - AC3: all four declared port sides preserved (lb:R→L:api, api:R→L:db,
         api:B→T:cache, api:R→L:queue).
  - AC4: first/last route-segment tangents agree with the declared sides.
  - AC10: each relation has a stable, unique edge_id.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.elk_integration

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.architecture import compile_architecture, arch_to_finalized  # noqa: E402
from mermaid_render.layout._geometry import PortSide  # noqa: E402

COMPLEX_SRC = (Path(__file__).parent / "fixtures" / "architecture-complex.mmd").read_text()

# Declared sides from the fixture: id -> (src_side, dst_side).
_DECLARED = {
    "lb->api": (PortSide.RIGHT, PortSide.LEFT),
    "api->db": (PortSide.RIGHT, PortSide.LEFT),
    "api->cache": (PortSide.BOTTOM, PortSide.TOP),
    "api->queue": (PortSide.RIGHT, PortSide.LEFT),
}


def _elk_available() -> bool:
    from mermaid_render.layout.elk_adapter import _find_elkjs, _find_node
    return _find_elkjs() is not None and _find_node() is not None


def _require_elk() -> None:
    """AC1: this lane fails (not skips) when ELK is unavailable."""
    assert _elk_available(), (
        "elkjs + node are required for the architecture ELK integration lane "
        "(install with `npm ci --prefix scripts/mermaid_render/layout`)"
    )


def _compile_via_real_elk():
    """Compile architecture-complex through the real elkjs subprocess (no mocks)."""
    _require_elk()
    return compile_architecture(COMPLEX_SRC, width_hint=1200)


def _finalized():
    return arch_to_finalized(_compile_via_real_elk())


def _first_segment(waypoints):
    for wp in waypoints[1:]:
        dx, dy = wp.x - waypoints[0].x, wp.y - waypoints[0].y
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            return dx, dy
    return 0.0, 0.0


def _last_segment(waypoints):
    for wp in reversed(waypoints[:-1]):
        dx, dy = waypoints[-1].x - wp.x, waypoints[-1].y - wp.y
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            return dx, dy
    return 0.0, 0.0


# outward normal (source) — the first tangent points away from the source node.
_OUTWARD_OK = {
    PortSide.LEFT: lambda dx, dy: dx < 0,
    PortSide.RIGHT: lambda dx, dy: dx > 0,
    PortSide.TOP: lambda dx, dy: dy < 0,
    PortSide.BOTTOM: lambda dx, dy: dy > 0,
}
# inward normal (destination) — the last tangent points into the destination node.
_INWARD_OK = {
    PortSide.LEFT: lambda dx, dy: dx > 0,
    PortSide.RIGHT: lambda dx, dy: dx < 0,
    PortSide.TOP: lambda dx, dy: dy > 0,
    PortSide.BOTTOM: lambda dx, dy: dy < 0,
}


# ── AC1: real subprocess + backend provenance ─────────────────────────────────

def test_elk_available_or_fail():
    """AC1: the lane fails loudly when ELK is unavailable — never a silent skip."""
    _require_elk()


def test_layout_backend_is_elkjs():
    """AC1: the compiled model records the elkjs backend (no fallback)."""
    arch = _compile_via_real_elk()
    assert arch.backend == "elk-js", f"expected elk-js backend, got {arch.backend!r}"
    fl = arch_to_finalized(arch)
    assert "elk-js" in fl.diagnostics.warnings
    assert "python-fallback" not in fl.diagnostics.warnings


def test_node_and_elkjs_versions_present():
    """AC1: node + elkjs are resolvable (records provenance for the ELK lane)."""
    from mermaid_render.layout.elk_adapter import _find_elkjs, _find_node
    _require_elk()
    assert _find_node()
    assert _find_elkjs()


# ── AC2: ELK result consumed directly (no reroute) ────────────────────────────

def test_python_router_not_called_after_elk_success(monkeypatch):
    """AC2: _route_edges must not be invoked once ELK produces a layout."""
    _require_elk()
    import mermaid_render.layout._routing as _rout

    calls = []
    original = _rout._route_edges

    def _spy(*a, **kw):
        calls.append(True)
        return original(*a, **kw)

    monkeypatch.setattr(_rout, "_route_edges", _spy)
    compile_architecture(COMPLEX_SRC, width_hint=1200)
    assert not calls, "_route_edges was called on the ELK success path (reroute detected)"


# ── AC3: declared port sides preserved through ELK ────────────────────────────

def test_declared_port_sides_preserved():
    """AC3: all four declared source/destination sides survive the ELK layout."""
    fl = _finalized()
    by_id = {re.edge_id: re for re in fl.routed_edges}
    for eid, (src_side, dst_side) in _DECLARED.items():
        edge = by_id.get(eid)
        assert edge is not None, f"{eid} missing from routed edges {list(by_id)}"
        assert edge.src_port.side == src_side, (
            f"{eid}: src side {edge.src_port.side} != declared {src_side}"
        )
        assert edge.dst_port.side == dst_side, (
            f"{eid}: dst side {edge.dst_port.side} != declared {dst_side}"
        )


def test_no_finalized_port_is_auto():
    """AC3/AC5: no finalized architecture port remains PortSide.AUTO."""
    fl = _finalized()
    for re in fl.routed_edges:
        assert re.src_port.side != PortSide.AUTO, f"{re.edge_id} src_port AUTO"
        assert re.dst_port.side != PortSide.AUTO, f"{re.edge_id} dst_port AUTO"


# ── AC4: route tangents agree with declared sides ─────────────────────────────

def test_source_tangent_agrees_with_declared_side():
    """AC4: the first route segment leaves along the declared source side."""
    fl = _finalized()
    by_id = {re.edge_id: re for re in fl.routed_edges}
    for eid, (src_side, _dst) in _DECLARED.items():
        edge = by_id[eid]
        dx, dy = _first_segment(edge.waypoints)
        assert _OUTWARD_OK[src_side](dx, dy), (
            f"{eid}: first tangent ({dx:.1f},{dy:.1f}) disagrees with source {src_side}"
        )


def test_destination_tangent_agrees_with_declared_side():
    """AC4: the last route segment enters along the declared destination side."""
    fl = _finalized()
    by_id = {re.edge_id: re for re in fl.routed_edges}
    for eid, (_src, dst_side) in _DECLARED.items():
        edge = by_id[eid]
        dx, dy = _last_segment(edge.waypoints)
        assert _INWARD_OK[dst_side](dx, dy), (
            f"{eid}: last tangent ({dx:.1f},{dy:.1f}) disagrees with dest {dst_side}"
        )


# ── AC10: stable unique edge ids ──────────────────────────────────────────────

def test_stable_unique_edge_ids():
    """AC10: each relation carries a stable, unique, non-empty edge_id."""
    fl = _finalized()
    ids = [re.edge_id for re in fl.routed_edges]
    assert all(isinstance(i, str) and i for i in ids), f"empty/non-str edge_id in {ids}"
    assert len(ids) == len(set(ids)), f"duplicate edge_ids: {ids}"
    assert set(ids) == set(_DECLARED), f"edge ids {set(ids)} != {set(_DECLARED)}"
