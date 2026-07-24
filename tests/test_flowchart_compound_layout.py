"""Flowchart compound layout + boundary gates (initiative item 3).

Covers the plan tasks for
``docs/specs/flowchart-compound-layout-and-boundary-gates``:

  Task 1: non-compound flowcharts attempt ELK first; inner-direction compound
          diagrams use the gate-emitting bottom-up Python compound path.
  Task 2: the Python fallback is bottom-up (leaf groups sized before parents).
  Task 3: empty groups are first-class measured proxies.
  Task 4: boundary gates are real route waypoints (single crossing, off the band).
  Task 5: cross-boundary routes avoid unrelated group interiors / title bands and
          use local channels rather than the canvas perimeter.

The scoped fixtures are compiled through the real ``_compile_flowchart`` and
checked with the item-1 segment-aware validators — the same gate the eight-case
harness applies. The Python backend is forced for deterministic geometry;
``MERMAID_LAYOUT_ENGINE=python`` also exercises the typed-fallback path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mermaid_render.layout._pipeline as _pipeline_mod  # noqa: E402
from mermaid_render.layout._geometry import BoundaryGateKind  # noqa: E402
from mermaid_render.layout._pipeline import (  # noqa: E402
    parse_flowchart_semantics,
    _compile_flowchart,
)
from mermaid_render.layout._strategies import RenderOptions  # noqa: E402
from mermaid_render.layout._layout_validation import (  # noqa: E402
    DEFAULT_TITLE_BAND_H,
    all_violations,
    translate_layout_to_positive,
    validate_canvas_coverage,
    validate_compound_gates,
    validate_segment_obstruction,
)
from mermaid_render.layout.elk_adapter import ElkUnavailable  # noqa: E402

_FIXTURES = Path(__file__).parent / "fixtures"


def _src(stem: str) -> str:
    return (_FIXTURES / f"{stem}.mmd").read_text()


def _compiled(stem: str, monkeypatch):
    """Compile a fixture on the deterministic Python compound path."""
    monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
    return _compile_flowchart(_src(stem), None, RenderOptions())


def _layout(stem: str, monkeypatch):
    return translate_layout_to_positive(_compiled(stem, monkeypatch).layout)


def _node_rect(layout, nid):
    return layout.node_layouts[nid].outer_bounds


def _group_rect(layout, gid):
    return layout.group_layouts[gid].boundary_bounds


def _edge(layout, edge_id):
    for e in layout.routed_edges:
        if e.edge_id == edge_id:
            return e
    raise AssertionError(f"edge {edge_id!r} not found in {[e.edge_id for e in layout.routed_edges]}")


# ── Task 1: ELK-first for non-compound; compound → gate-emitting Python path ───

class TestPathSelection:
    _INNER = "flowchart-inner-direction"
    _FLAT = "flowchart-groups-complex"  # groups but no inner direction

    def test_non_compound_attempts_elk_first(self, monkeypatch):
        """A grouped-but-non-compound flowchart attempts ELK before any fallback,
        and only reaches the Python path via the typed ElkUnavailable condition
        (reason 'elk-unavailable') — never a silent bypass like the compound path's
        'inner-direction'."""
        calls: list = []
        real = _pipeline_mod.layout_flowchart_with_elk

        def _spy(graph, spacing=None):
            calls.append(graph)
            return real(graph, spacing=spacing)

        monkeypatch.setattr(_pipeline_mod, "layout_flowchart_with_elk", _spy)
        compiled = _compile_flowchart(_src(self._FLAT), None, RenderOptions())
        assert calls, "ELK layout entry point was never attempted for a non-compound flowchart"
        # ELK unavailable here → typed fallback; reason proves ELK was attempted,
        # not bypassed. (With elkjs present this fixture consumes ELK directly.)
        if compiled.metadata.backend == "python":
            assert compiled.metadata.fallback_reason == "elk-unavailable"
        else:
            assert compiled.metadata.backend == "elkjs"
            assert compiled.metadata.fallback_reason is None

    def test_inner_direction_uses_gate_emitting_python_path(self, monkeypatch):
        """Inner-direction compound diagrams use the bottom-up Python compound path
        (backend 'python', reason 'inner-direction') — the only path that emits the
        BoundaryGate records AC7 and the harness min_gates contract require."""
        compiled = _compile_flowchart(_src(self._INNER), None, RenderOptions())
        assert compiled.metadata.backend == "python"
        assert compiled.metadata.fallback_reason == "inner-direction"
        assert compiled.layout.boundary_gates, "compound path must emit boundary gates"

    def test_non_compound_fallback_only_on_typed_condition(self, monkeypatch):
        """When ELK raises ElkUnavailable, a non-compound flowchart selects the
        Python fallback with a typed (non-None) reason — never a silent bypass."""
        monkeypatch.setattr(
            _pipeline_mod, "layout_flowchart_with_elk",
            lambda graph, spacing=None: (_ for _ in ()).throw(ElkUnavailable("no node")),
        )
        compiled = _compile_flowchart(_src(self._FLAT), None, RenderOptions())
        assert compiled.metadata.backend == "python"
        assert compiled.metadata.fallback_reason == "elk-unavailable"


# ── Task 2: bottom-up Python compound fallback ─────────────────────────────────

class TestBottomUpFallback:
    def test_inner_group_sized_from_members_not_global(self, monkeypatch):
        """The Pipeline group's box is derived from its measured LR members, not a
        prior global placement: its width spans all three ordered members."""
        layout = _layout("flowchart-inner-direction", monkeypatch)
        pipe = _group_rect(layout, "_g0")
        ingest = _node_rect(layout, "ingest")
        load = _node_rect(layout, "load")
        # Group box encloses the leftmost and rightmost members with real width.
        assert pipe.x <= ingest.x + 1
        assert pipe.x1 >= load.x1 - 1
        assert pipe.w >= (load.x1 - ingest.x) - 1

    def test_pipeline_members_monotonic_x(self, monkeypatch):
        """AC4: Ingest, Transform, Load have monotonically increasing x (local LR)."""
        layout = _layout("flowchart-inner-direction", monkeypatch)
        xs = [_node_rect(layout, n).x for n in ("ingest", "transform", "load")]
        assert xs[0] < xs[1] < xs[2], xs


# ── Task 3: first-class empty groups ───────────────────────────────────────────

class TestEmptyGroups:
    _STEM = "flowchart-empty-subgraph"

    def _empty_and_full(self, layout):
        empty = full = None
        for gid, gl in layout.group_layouts.items():
            if len(gl.member_ids) == 0:
                empty = gl
            else:
                full = gl
        return empty, full

    def test_empty_group_present_and_nonzero(self, monkeypatch):
        """AC1: both groups exist and the empty group has nonzero measured bounds.

        Fails (does not skip) when the empty group is absent."""
        layout = _layout(self._STEM, monkeypatch)
        assert len(layout.group_layouts) == 2, "empty subgraph must survive as a real group"
        empty, full = self._empty_and_full(layout)
        assert empty is not None, "empty group missing from compiled layout"
        assert empty.boundary_bounds.w > 0 and empty.boundary_bounds.h > 0

    def test_empty_group_not_at_origin(self, monkeypatch):
        layout = _layout(self._STEM, monkeypatch)
        empty, _ = self._empty_and_full(layout)
        assert (empty.boundary_bounds.x, empty.boundary_bounds.y) != (0.0, 0.0)

    def test_empty_group_no_overlap(self, monkeypatch):
        layout = _layout(self._STEM, monkeypatch)
        empty, full = self._empty_and_full(layout)
        assert empty.boundary_bounds.intersection_area(full.boundary_bounds) == 0.0

    def test_sibling_empty_groups_do_not_overlap(self, monkeypatch):
        """Two top-level sibling empty groups are each placed off-origin in their
        own slot and do not overlap each other or the populated content."""
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
        src = (
            "flowchart TD\n"
            '  subgraph E1["Empty One"]\n  end\n'
            '  subgraph E2["Empty Two"]\n  end\n'
            "  A[Real] --> B[Also Real]\n"
        )
        layout = translate_layout_to_positive(_compile_flowchart(src, None, RenderOptions()).layout)
        empties = [gl for gl in layout.group_layouts.values() if len(gl.member_ids) == 0]
        assert len(empties) == 2
        for gl in empties:
            b = gl.boundary_bounds
            assert b.w > 0 and b.h > 0
            assert (b.x, b.y) != (0.0, 0.0)
        assert empties[0].boundary_bounds.intersection_area(empties[1].boundary_bounds) == 0.0

    def test_nested_empty_group_compiles_within_canvas(self, monkeypatch):
        """A nested empty group is left to its parent's packing (the top-level
        placement pass skips it); the diagram still compiles cleanly with both
        groups inside the canvas."""
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
        src = (
            "flowchart TD\n"
            '  subgraph Outer["Outer"]\n'
            '    subgraph Inner["Inner Empty"]\n    end\n'
            "  end\n"
            "  A --> B\n"
        )
        layout = translate_layout_to_positive(_compile_flowchart(src, None, RenderOptions()).layout)
        assert len(layout.group_layouts) == 2
        cb = layout.canvas_bounds
        for gl in layout.group_layouts.values():
            b = gl.boundary_bounds
            assert b.x >= -1 and b.y >= -1 and b.x1 <= cb.x1 + 1 and b.y1 <= cb.y1 + 1


# ── Task 4: boundary gates as route waypoints ──────────────────────────────────

class TestBoundaryGates:
    _STEM = "flowchart-cross-scope-edge"

    def test_boundary_gate_exists_for_cross_scope_edge(self, monkeypatch):
        """AC7: B→C (entry) and D→E (exit) each own a BoundaryGate record."""
        layout = _layout(self._STEM, monkeypatch)
        by_edge = {}
        for g in layout.boundary_gates:
            by_edge.setdefault(g.edge_id, []).append(g)
        assert "B->C" in by_edge and any(g.kind is BoundaryGateKind.ENTRY for g in by_edge["B->C"])
        assert "D->E" in by_edge and any(g.kind is BoundaryGateKind.EXIT for g in by_edge["D->E"])

    def test_gate_on_group_boundary(self, monkeypatch):
        """AC7: every gate point lies on its group's boundary (± 1px)."""
        layout = _layout(self._STEM, monkeypatch)
        for g in layout.boundary_gates:
            b = _group_rect(layout, g.group_id)
            on_v = (abs(g.point.x - b.x) <= 1 or abs(g.point.x - b.x1) <= 1) and b.y - 1 <= g.point.y <= b.y1 + 1
            on_h = (abs(g.point.y - b.y) <= 1 or abs(g.point.y - b.y1) <= 1) and b.x - 1 <= g.point.x <= b.x1 + 1
            assert on_v or on_h, f"gate {g.gate_id} at {g.point} not on boundary {b}"

    def test_gate_is_route_waypoint(self, monkeypatch):
        """AC2: the declared gate point coincides with a point on its edge route."""
        layout = _layout(self._STEM, monkeypatch)
        for g in layout.boundary_gates:
            e = _edge(layout, g.edge_id)
            near = any(abs(w.x - g.point.x) <= 1 and abs(w.y - g.point.y) <= 1 for w in e.waypoints)
            assert near, f"gate {g.gate_id} at {g.point} is not a waypoint of {g.edge_id}"

    def test_single_boundary_crossing_and_no_band(self, monkeypatch):
        """AC2: neither cross-scope route re-enters its group or crosses the title
        band; the compound-gate + obstruction validators are both clean."""
        layout = _layout(self._STEM, monkeypatch)
        assert validate_compound_gates(layout) == []
        assert validate_segment_obstruction(layout) == []

    def test_gate_below_title_band_for_tb_group(self, monkeypatch):
        """AC2/Task4: a left/right entry gate sits at or below the destination
        group's title-band bottom, so the internal segment never crosses the band."""
        layout = _layout(self._STEM, monkeypatch)
        b = _group_rect(layout, "_g0")
        gate = next(g for g in layout.boundary_gates if g.edge_id == "B->C")
        # Gate y is below the band the obstruction validator enforces; a gate
        # moved into the band (b.y .. b.y+DEFAULT_TITLE_BAND_H) reddens this.
        assert gate.point.y >= b.y + DEFAULT_TITLE_BAND_H

    def test_rerouted_segments_are_orthogonal(self, monkeypatch):
        """Task4/5: every segment of a rerouted cross-scope edge is axis-aligned
        (no diagonal introduced by endpoint substitution)."""
        layout = _layout(self._STEM, monkeypatch)
        for e in layout.routed_edges:
            if not (e.source_scope or e.target_scope):
                continue
            for i in range(len(e.waypoints) - 1):
                p, q = e.waypoints[i], e.waypoints[i + 1]
                assert abs(p.x - q.x) < 0.01 or abs(p.y - q.y) < 0.01, (
                    f"{e.edge_id} segment[{i}] {p}->{q} is diagonal"
                )


# ── Task 5: group-aware routing obstacles ──────────────────────────────────────

class TestRoutingObstacles:
    _STEM = "flowchart-groups-complex"

    def test_no_route_crosses_unrelated_group_or_band(self, monkeypatch):
        """AC3: no relationship segment threads an unrelated group interior or any
        group title band."""
        layout = _layout(self._STEM, monkeypatch)
        assert validate_segment_obstruction(layout) == []

    def test_all_validators_clean(self, monkeypatch):
        """AC3: the full segment-aware validator battery passes on groups-complex."""
        layout = _layout(self._STEM, monkeypatch)
        assert all_violations(layout) == []

    def test_worker_queue_local_route(self, monkeypatch):
        """AC3: Worker→Queue uses a local cross-group channel — its route is shorter
        than routing around the full canvas perimeter."""
        layout = _layout(self._STEM, monkeypatch)
        e = _edge(layout, "Worker->Queue")
        length = sum(
            abs(e.waypoints[i + 1].x - e.waypoints[i].x) + abs(e.waypoints[i + 1].y - e.waypoints[i].y)
            for i in range(len(e.waypoints) - 1)
        )
        perimeter = 2 * (layout.canvas_bounds.w + layout.canvas_bounds.h)
        assert length < perimeter, (length, perimeter)


# ── AC-level: every scoped fixture compiles clean on the live lane ─────────────

@pytest.mark.parametrize("stem", [
    "flowchart-cross-scope-edge",
    "flowchart-empty-subgraph",
    "flowchart-groups-complex",
    "flowchart-inner-direction",
])
def test_scoped_fixture_geometry_clean(stem, monkeypatch):
    """AC2/AC3/AC7: each scoped fixture compiles to canvas-, obstruction- and
    gate-clean geometry."""
    layout = _layout(stem, monkeypatch)
    assert validate_canvas_coverage(layout) == []
    assert all_violations(layout) == []
