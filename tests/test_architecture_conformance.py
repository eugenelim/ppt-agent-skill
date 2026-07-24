"""Architecture ELK metadata-preservation conformance tests.

Covers the spec at docs/specs/mermaid-architecture-metadata-preservation/spec.md.

All tests use unittest.mock.patch to avoid requiring a real ELK runtime in CI.
ELK-unavailable tests trigger the fallback path and verify its contract.

Test categories:
  - Task 1: success path returns FinalizedLayout; _elk_routes_to_specs not called
  - Task 2: edge metadata keyed by edge_id (not (src, dst) tuple)
  - Task 3: fixed-side port constraints preserved through full pipeline
  - Task 4: measured labels use TextLayout from _MEASURER
  - Task 5: fallback contract (ElkUnavailable → python-fallback in warnings)
  - Task 6: architecture-complex fixture conformance
"""
from __future__ import annotations

import sys
import types as _types
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.architecture import (
    compile_architecture,
    arch_to_finalized,
    _arch_elk_to_finalized,
)
from mermaid_render.layout._geometry import (
    FinalizedLayout, LayoutDiagnostics, NodeLayout, GroupLayout, RoutedEdge,
    PortLayout, PortSide, Point, Rect, TextLayout, EdgeLabelLayout,
    MarkerKind, _empty_diagnostics,
)
from mermaid_render.layout.elk_adapter import ElkUnavailable, ElkInvalidResult

COMPLEX_FIXTURE = Path(__file__).parent / "fixtures" / "architecture-complex.mmd"
COMPLEX_SRC = COMPLEX_FIXTURE.read_text()

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_node_layout(nid: str, x: float = 0.0, y: float = 0.0,
                      w: float = 120.0, h: float = 80.0,
                      parent_group_id: str | None = None) -> NodeLayout:
    outer = Rect(x, y, w, h)
    return NodeLayout(
        node_id=nid, semantic_shape="rect",
        outer_bounds=outer, content_bounds=outer,
        title_layout=TextLayout(
            lines=(), width=w, height=h, line_height=14.0,
            min_content_width=0.0, max_content_width=w,
            resolved_font_path=None, resolved_font_family="sans-serif",
        ),
        subtitle_layout=None, member_layouts=(), icon_bounds=None,
        ports=(), css_classes=(), extra_css="",
        is_dummy=False, rank=0, is_external=False,
        icon_svg="", accent_color="", parent_group_id=parent_group_id,
    )


def _make_group_layout(gid: str) -> GroupLayout:
    return GroupLayout(
        group_id=gid, parent_group_id=None,
        boundary_bounds=Rect(0.0, 0.0, 900.0, 700.0),
        label_layout=None, member_ids=(), child_group_ids=(),
        local_direction="LR",
    )


def _make_routed_edge(eid: str, src: str, dst: str, *,
                      src_side: PortSide = PortSide.AUTO,
                      dst_side: PortSide = PortSide.AUTO,
                      label: str = "") -> RoutedEdge:
    src_pos = Point(120.0, 40.0)
    dst_pos = Point(200.0, 40.0)
    label_layout = None
    if label:
        tl = TextLayout(
            lines=(), width=60.0, height=14.0, line_height=14.0,
            min_content_width=0.0, max_content_width=60.0,
            resolved_font_path=None, resolved_font_family="sans-serif",
        )
        label_layout = EdgeLabelLayout(
            text=label, layout=tl,
            bounds=Rect(x=160.0, y=30.0, w=60.0, h=14.0),
            anchor_point=Point(160.0, 40.0),
        )
    return RoutedEdge(
        edge_id=eid, src_node_id=src, dst_node_id=dst,
        src_port=PortLayout(node_id=src, side=src_side,
                            position=src_pos, direction=Point(1.0, 0.0)),
        dst_port=PortLayout(node_id=dst, side=dst_side,
                            position=dst_pos, direction=Point(-1.0, 0.0)),
        waypoints=(src_pos, dst_pos),
        edge_style="solid", has_marker_end=True, has_marker_start=False,
        label_layout=label_layout, src_label_layout=None, dst_label_layout=None,
        source_marker=MarkerKind.NONE, target_marker=MarkerKind.ARROW,
    )


def _make_mock_elk_result(node_ids: list[str], group_ids: list[str],
                          routed_edges: list[RoutedEdge],
                          group_map: dict | None = None) -> tuple:
    """Build (FinalizedLayout, None) as a mock return from layout_with_elk."""
    nl_dict = {nid: _make_node_layout(nid, parent_group_id=(group_map or {}).get(nid))
               for nid in node_ids}
    gl_dict = {gid: _make_group_layout(gid) for gid in group_ids}
    fl = FinalizedLayout(
        node_layouts=_types.MappingProxyType(nl_dict),
        group_layouts=_types.MappingProxyType(gl_dict),
        routed_edges=tuple(routed_edges),
        visible_bounds=Rect(0.0, 0.0, 900.0, 700.0),
        diagram_padding=48.0,
        canvas_bounds=Rect(0.0, 0.0, 900.0, 700.0),
        direction="LR",
        diagnostics=_empty_diagnostics(),
    )
    return (fl, None)


# ── Task 1: success path returns the compiled model; no _elk_routes_to_specs ──
#
# Contract updated by architecture-fixed-port-integration (item 5 of ini-003):
# compile_architecture now returns the documented ArchitectureDiagramLayout on
# BOTH the ELK and Python-fallback paths (the eight_case AC9 harness reads
# ``.services``/``.groups``/``.edges``). The FinalizedLayout is obtained via
# arch_to_finalized() — the ELK geometry is consumed directly (no re-routing),
# so every invariant the prior contract asserted still holds on the lowered
# FinalizedLayout.

class TestSuccessPathReturnsCompiledModel:
    """Task 1 tests — ELK success path returns ArchitectureDiagramLayout."""

    def _make_complex_mock(self):
        node_ids = ["lb", "api", "db", "cache", "queue"]
        group_ids = ["cloud"]
        group_map = {nid: "cloud" for nid in node_ids}
        edges = [
            _make_routed_edge("lb->api", "lb", "api"),
            _make_routed_edge("api->db", "api", "db"),
            _make_routed_edge("api->cache", "api", "cache"),
            _make_routed_edge("api->queue", "api", "queue"),
        ]
        return _make_mock_elk_result(node_ids, group_ids, edges, group_map=group_map)

    def test_success_path_returns_compiled_model(self):
        """ELK success path returns ArchitectureDiagramLayout; arch_to_finalized lowers it."""
        from mermaid_render.layout.architecture import ArchitectureDiagramLayout
        mock_ret = self._make_complex_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        assert isinstance(result, ArchitectureDiagramLayout), (
            f"Expected ArchitectureDiagramLayout, got {type(result).__name__}"
        )
        assert result.backend == "elk-js"
        assert isinstance(arch_to_finalized(result), FinalizedLayout)

    def test_elk_routes_to_specs_deleted(self):
        """_elk_routes_to_specs must not exist — it is dead code deleted by AC7.

        The function used a (src, dst) tuple identity map that silently dropped
        duplicate edges (AC7 violation).  Verify it is gone entirely so it
        cannot be re-introduced by accident.
        """
        import mermaid_render.layout.architecture as _arch_mod
        assert not hasattr(_arch_mod, "_elk_routes_to_specs"), (
            "_elk_routes_to_specs still exists in architecture.py — "
            "delete it (AC7: dead code with tuple-identity map)."
        )

    def test_elk_backend_stamped_in_diagnostics(self):
        """Successful ELK path must stamp 'elk-js' in diagnostics.warnings."""
        mock_ret = self._make_complex_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        assert "elk-js" in fl.diagnostics.warnings

    def test_success_path_has_node_layouts_for_all_services(self):
        mock_ret = self._make_complex_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        for nid in ("lb", "api", "db", "cache", "queue"):
            assert nid in fl.node_layouts, f"Missing node layout for {nid!r}"

    def test_success_path_has_group_layout_for_cloud(self):
        mock_ret = self._make_complex_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        assert "cloud" in fl.group_layouts


# ── Task 2: edge-id keyed metadata ───────────────────────────────────────────

class TestEdgeIdKeyedMetadata:
    """Task 2 tests — edge metadata keyed by edge_id, not (src, dst) tuple."""

    DUAL_EDGE_SRC = """\
architecture-beta
  service a(server)[A]
  service b(database)[B]
  a --> b : first
  a --> b : second
"""

    def _make_dual_edge_mock(self):
        node_ids = ["a", "b"]
        edges = [
            _make_routed_edge("a->b", "a", "b", label="first"),
            _make_routed_edge("a->b#1", "a", "b", label="second"),
        ]
        return _make_mock_elk_result(node_ids, [], edges)

    def test_dual_edges_both_routed_with_unique_ids(self):
        """Two edges from same (src, dst) survive with distinct edge_ids."""
        mock_ret = self._make_dual_edge_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(self.DUAL_EDGE_SRC)
        fl = arch_to_finalized(result)
        edge_ids = [re.edge_id for re in fl.routed_edges]
        assert len(set(edge_ids)) == 2, f"Expected 2 distinct edge_ids, got {edge_ids}"

    def test_duplicate_src_dst_both_survive(self):
        """Two edges with identical (src, dst) but different labels both survive."""
        mock_ret = self._make_dual_edge_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(self.DUAL_EDGE_SRC)
        fl = arch_to_finalized(result)
        assert len(fl.routed_edges) == 2

    def test_no_src_dst_tuple_lookup_in_pipeline(self):
        """The (src,dst) tuple-identity map (_elk_routes_to_specs) must not exist.

        The function was deleted (AC7).  This test is the companion to
        test_elk_routes_to_specs_deleted in TestSuccessPathReturnsFinalizedLayout
        and serves as the edge-ID keying spec constraint: duplicate edges with
        identical (src, dst) must survive because routing is keyed by edge_id.
        """
        import mermaid_render.layout.architecture as _arch_mod
        assert not hasattr(_arch_mod, "_elk_routes_to_specs"), (
            "_elk_routes_to_specs re-introduced — duplicate (src,dst) edges would be dropped."
        )


# ── Task 3: fixed-side port preservation ─────────────────────────────────────

class TestFixedSidePortPreservation:
    """Task 3 tests — declared port sides are never replaced by AUTO."""

    # architecture-complex has lb:R→L:api, api:R→L:db, api:B→T:cache, api:R→L:queue

    def _complex_edges_with_sides(self):
        """Mock ELK result with AUTO sides (as ELK might return from tangent)."""
        node_ids = ["lb", "api", "db", "cache", "queue"]
        group_ids = ["cloud"]
        group_map = {nid: "cloud" for nid in node_ids}
        # ELK returns AUTO sides — the enrichment step must override with declared sides
        edges = [
            _make_routed_edge("lb->api", "lb", "api",
                              src_side=PortSide.AUTO, dst_side=PortSide.AUTO),
            _make_routed_edge("api->db", "api", "db",
                              src_side=PortSide.AUTO, dst_side=PortSide.AUTO),
            _make_routed_edge("api->cache", "api", "cache",
                              src_side=PortSide.AUTO, dst_side=PortSide.AUTO),
            _make_routed_edge("api->queue", "api", "queue",
                              src_side=PortSide.AUTO, dst_side=PortSide.AUTO),
        ]
        return _make_mock_elk_result(node_ids, group_ids, edges, group_map=group_map)

    def _get_edge(self, fl: FinalizedLayout, src: str, dst: str) -> RoutedEdge | None:
        for re in fl.routed_edges:
            if re.src_node_id == src and re.dst_node_id == dst:
                return re
        return None

    def test_lb_api_src_side_is_right(self):
        """lb:R→L:api — src_port.side must be RIGHT (not AUTO)."""
        mock_ret = self._complex_edges_with_sides()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        edge = self._get_edge(fl, "lb", "api")
        assert edge is not None, "lb->api not found in routed_edges"
        assert edge.src_port.side == PortSide.RIGHT, (
            f"Expected RIGHT, got {edge.src_port.side}"
        )

    def test_lb_api_dst_side_is_left(self):
        """lb:R→L:api — dst_port.side must be LEFT (not AUTO)."""
        mock_ret = self._complex_edges_with_sides()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        edge = self._get_edge(fl, "lb", "api")
        assert edge is not None
        assert edge.dst_port.side == PortSide.LEFT

    def test_api_cache_src_side_is_bottom(self):
        """api:B→T:cache — src_port.side must be BOTTOM (not AUTO)."""
        mock_ret = self._complex_edges_with_sides()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        edge = self._get_edge(fl, "api", "cache")
        assert edge is not None, "api->cache not found"
        assert edge.src_port.side == PortSide.BOTTOM, (
            f"Expected BOTTOM, got {edge.src_port.side}"
        )

    def test_api_cache_dst_side_is_top(self):
        """api:B→T:cache — dst_port.side must be TOP (not AUTO)."""
        mock_ret = self._complex_edges_with_sides()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        edge = self._get_edge(fl, "api", "cache")
        assert edge is not None
        assert edge.dst_port.side == PortSide.TOP

    def test_no_auto_for_fixed_ports(self):
        """No declared-fixed port should have PortSide.AUTO after enrichment."""
        mock_ret = self._complex_edges_with_sides()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        # architecture-complex declares fixed sides on all 4 edges
        for re in fl.routed_edges:
            assert re.src_port.side != PortSide.AUTO, (
                f"Edge {re.edge_id} src_port.side is AUTO — fixed side was overwritten"
            )
            assert re.dst_port.side != PortSide.AUTO, (
                f"Edge {re.edge_id} dst_port.side is AUTO — fixed side was overwritten"
            )


# ── Task 4: measured labels ───────────────────────────────────────────────────

class TestMeasuredLabels:
    """Task 4 tests — all labels use TextLayout from _MEASURER."""

    LABELED_SRC = """\
architecture-beta
  group g[My Group]
  service a(server)[Alpha Service] in g
  service b(database)[Beta Service] in g
  a --> b : connection label
"""

    def _make_labeled_mock(self):
        node_ids = ["a", "b"]
        group_ids = ["g"]
        group_map = {"a": "g", "b": "g"}
        edges = [
            _make_routed_edge("a->b", "a", "b", label="connection label"),
        ]
        return _make_mock_elk_result(node_ids, group_ids, edges, group_map=group_map)

    def test_service_label_uses_text_layout(self):
        """Service node title_layout must be a TextLayout measured by _MEASURER."""
        mock_ret = self._make_labeled_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(self.LABELED_SRC)
        fl = arch_to_finalized(result)
        for nid, nl in fl.node_layouts.items():
            if not nl.is_dummy:
                assert isinstance(nl.title_layout, TextLayout), (
                    f"Node {nid}: title_layout is not a TextLayout"
                )
                assert nl.title_layout.width > 0, (
                    f"Node {nid}: title_layout.width is 0"
                )

    def test_group_label_uses_text_layout(self):
        """Group label_layout must be a TextLayout measured by _MEASURER."""
        mock_ret = self._make_labeled_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(self.LABELED_SRC)
        fl = arch_to_finalized(result)
        gl = fl.group_layouts.get("g")
        assert gl is not None
        assert isinstance(gl.label_layout, TextLayout), (
            f"Group g: label_layout is not a TextLayout"
        )

    def test_edge_label_remeasured_by_measurer(self):
        """Edge label_layout must have TextLayout.lines from _MEASURER, not empty tuple."""
        mock_ret = self._make_labeled_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(self.LABELED_SRC)
        fl = arch_to_finalized(result)
        labeled = [re for re in fl.routed_edges if re.label_layout is not None]
        assert len(labeled) == 1, "Expected one labeled edge"
        ll = labeled[0].label_layout
        assert ll is not None
        assert isinstance(ll.layout, TextLayout)
        assert ll.layout.width > 0, "Remeasured edge label width must be > 0"

    def test_group_min_width_from_measured_label(self):
        """Wider group label → larger label_layout.width (from _MEASURER)."""
        short_src = "architecture-beta\ngroup g[Hi]\n    service s(server)[S]\n"
        long_src = "architecture-beta\ngroup g[A Much Longer Group Name]\n    service s(server)[S]\n"

        short_edges = [_make_routed_edge("s->s_dummy", "s", "s")]
        long_edges = [_make_routed_edge("s->s_dummy", "s", "s")]

        def _mock_short(*a, **kw):
            return _make_mock_elk_result(["s"], ["g"], [], group_map={"s": "g"})

        def _mock_long(*a, **kw):
            return _make_mock_elk_result(["s"], ["g"], [], group_map={"s": "g"})

        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   side_effect=_mock_short):
            short_result = compile_architecture(short_src)
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   side_effect=_mock_long):
            long_result = compile_architecture(long_src)

        short_fl = arch_to_finalized(short_result)
        long_fl = arch_to_finalized(long_result)
        short_w = short_fl.group_layouts["g"].label_layout
        long_w = long_fl.group_layouts["g"].label_layout
        assert short_w is not None and long_w is not None
        assert long_w.width > short_w.width, (
            f"Longer label should have wider TextLayout: {long_w.width} <= {short_w.width}"
        )


# ── Task 5: fallback contract ─────────────────────────────────────────────────

class TestFallbackContract:
    """Task 5 tests — ElkUnavailable fallback satisfies FinalizedLayout contract."""

    def test_fallback_returns_on_elk_unavailable(self):
        """When ELK is unavailable, compile_architecture must not raise."""
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   side_effect=ElkUnavailable("test unavailable")):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        # Should return without error; may be ArchitectureDiagramLayout or FinalizedLayout
        assert result is not None

    def test_fallback_can_be_finalized(self):
        """arch_to_finalized on fallback result produces a valid FinalizedLayout."""
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   side_effect=ElkUnavailable("test")):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = result if isinstance(result, FinalizedLayout) else arch_to_finalized(result)
        assert isinstance(fl, FinalizedLayout)
        assert fl.canvas_bounds.w > 0

    def test_fallback_has_python_fallback_in_warnings(self):
        """Fallback result must record 'python-fallback' in diagnostics.warnings."""
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   side_effect=ElkUnavailable("test")):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = result if isinstance(result, FinalizedLayout) else arch_to_finalized(result)
        assert "python-fallback" in fl.diagnostics.warnings, (
            f"Expected 'python-fallback' in warnings; got {fl.diagnostics.warnings}"
        )

    def test_fallback_satisfies_finalized_layout_contract(self):
        """Fallback FinalizedLayout has node_layouts, group_layouts, routed_edges, canvas_bounds."""
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   side_effect=ElkUnavailable("test")):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = result if isinstance(result, FinalizedLayout) else arch_to_finalized(result)
        assert isinstance(fl, FinalizedLayout)
        assert len(fl.node_layouts) == 5   # lb, api, db, cache, queue
        assert len(fl.group_layouts) == 1  # cloud
        assert len(fl.routed_edges) >= 4
        assert fl.canvas_bounds.w > 0
        assert fl.canvas_bounds.h > 0

    def test_incomplete_elk_result_raises_elk_invalid_result(self):
        """Mock ELK result with missing edge sections raises ElkInvalidResult."""
        # Return a FinalizedLayout with all nodes present but ZERO routed_edges.
        # The compile_architecture validation should detect the missing edge sections.
        node_ids = ["lb", "api", "db", "cache", "queue"]
        group_ids = ["cloud"]
        group_map = {nid: "cloud" for nid in node_ids}
        nl_dict = {nid: _make_node_layout(nid, parent_group_id="cloud")
                   for nid in node_ids}
        gl_dict = {"cloud": _make_group_layout("cloud")}
        empty_fl = FinalizedLayout(
            node_layouts=_types.MappingProxyType(nl_dict),
            group_layouts=_types.MappingProxyType(gl_dict),
            routed_edges=(),  # no edges — simulates missing sections
            visible_bounds=Rect(0.0, 0.0, 900.0, 700.0),
            diagram_padding=48.0,
            canvas_bounds=Rect(0.0, 0.0, 900.0, 700.0),
            direction="LR",
            diagnostics=_empty_diagnostics(),
        )
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=(empty_fl, None)):
            with pytest.raises(ElkInvalidResult):
                compile_architecture(COMPLEX_SRC, width_hint=1200)


# ── Task 6: architecture-complex conformance ──────────────────────────────────

class TestArchitectureComplexConformance:
    """Task 6 tests — full conformance against architecture-complex fixture."""

    def _make_complex_mock(self):
        node_ids = ["lb", "api", "db", "cache", "queue"]
        group_ids = ["cloud"]
        group_map = {nid: "cloud" for nid in node_ids}
        edges = [
            _make_routed_edge("lb->api", "lb", "api",
                              src_side=PortSide.AUTO, dst_side=PortSide.AUTO),
            _make_routed_edge("api->db", "api", "db",
                              src_side=PortSide.AUTO, dst_side=PortSide.AUTO),
            _make_routed_edge("api->cache", "api", "cache",
                              src_side=PortSide.AUTO, dst_side=PortSide.AUTO),
            _make_routed_edge("api->queue", "api", "queue",
                              src_side=PortSide.AUTO, dst_side=PortSide.AUTO),
        ]
        return _make_mock_elk_result(node_ids, group_ids, edges, group_map=group_map)

    def test_architecture_complex_fixed_sides(self):
        """All four declared fixed-side constraints survive compilation."""
        mock_ret = self._make_complex_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        edge_map = {re.edge_id: re for re in fl.routed_edges}

        # lb:R → L:api
        e = edge_map.get("lb->api")
        assert e is not None, "lb->api missing"
        assert e.src_port.side == PortSide.RIGHT, f"lb src side: {e.src_port.side}"
        assert e.dst_port.side == PortSide.LEFT, f"api dst side: {e.dst_port.side}"

        # api:R → L:db
        e = edge_map.get("api->db")
        assert e is not None, "api->db missing"
        assert e.src_port.side == PortSide.RIGHT
        assert e.dst_port.side == PortSide.LEFT

        # api:B → T:cache
        e = edge_map.get("api->cache")
        assert e is not None, "api->cache missing"
        assert e.src_port.side == PortSide.BOTTOM
        assert e.dst_port.side == PortSide.TOP

        # api:R → L:queue
        e = edge_map.get("api->queue")
        assert e is not None, "api->queue missing"
        assert e.src_port.side == PortSide.RIGHT
        assert e.dst_port.side == PortSide.LEFT

    def test_architecture_complex_unique_edge_ids(self):
        """All relations have distinct edge_id values."""
        mock_ret = self._make_complex_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        edge_ids = [re.edge_id for re in fl.routed_edges]
        assert len(edge_ids) == len(set(edge_ids)), (
            f"Duplicate edge_ids found: {edge_ids}"
        )

    def test_architecture_complex_no_rerouting(self):
        """ELK result is not rerouted through the Python fallback."""
        from mermaid_render.layout import _routing as _rout
        mock_ret = self._make_complex_mock()
        route_calls = []
        original_route = _rout._route_edges

        def _spy_route(*a, **kw):
            route_calls.append(True)
            return original_route(*a, **kw)

        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            with patch.object(_rout, "_route_edges", side_effect=_spy_route):
                result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        assert not route_calls, (
            "_route_edges was called on ELK success path — rerouting detected"
        )

    def test_architecture_complex_measured_labels(self):
        """All service and group labels derive from TextMeasurer (_MEASURER.layout)."""
        mock_ret = self._make_complex_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        for nid, nl in fl.node_layouts.items():
            if not nl.is_dummy:
                assert isinstance(nl.title_layout, TextLayout), (
                    f"Node {nid} title_layout is not a TextLayout"
                )
                assert nl.title_layout.width > 0

    def test_arch_to_finalized_lowers_elk_model(self):
        """arch_to_finalized lowers the ELK-origin model to a FinalizedLayout.

        The ELK geometry is consumed directly (no re-routing), so the lowered
        layout keeps ELK's node bounds, group bounds, and routed waypoints.
        """
        mock_ret = self._make_complex_mock()
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   return_value=mock_ret):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(result)
        assert isinstance(fl, FinalizedLayout)
        assert set(fl.node_layouts) == {"lb", "api", "db", "cache", "queue"}
        assert {re.edge_id for re in fl.routed_edges} == {
            "lb->api", "api->db", "api->cache", "api->queue"
        }


# ── architecture-fixed-port-integration AC5/AC6: fallback declared-side ports ──

class TestFallbackDeclaredSides:
    """Item-5 AC5/AC6 — the Python fallback copies declared sides into the
    finalized ports (no PortSide.AUTO) and raises a typed error rather than
    silently substituting AUTO when a declared side cannot be honored."""

    def _fallback_finalized(self):
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   side_effect=ElkUnavailable("forced fallback")):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        assert result.backend == "python-fallback"
        return arch_to_finalized(result)

    def test_fallback_no_auto_ports(self):
        """AC5: no finalized port remains PortSide.AUTO in the fallback."""
        fl = self._fallback_finalized()
        for re in fl.routed_edges:
            assert re.src_port.side != PortSide.AUTO, f"{re.edge_id} src AUTO"
            assert re.dst_port.side != PortSide.AUTO, f"{re.edge_id} dst AUTO"

    def test_fallback_preserves_declared_sides(self):
        """AC5: all four declared source/destination sides survive the fallback."""
        fl = self._fallback_finalized()
        by_id = {re.edge_id: re for re in fl.routed_edges}
        expected = {
            "lb->api": (PortSide.RIGHT, PortSide.LEFT),
            "api->db": (PortSide.RIGHT, PortSide.LEFT),
            "api->cache": (PortSide.BOTTOM, PortSide.TOP),
            "api->queue": (PortSide.RIGHT, PortSide.LEFT),
        }
        for eid, (ss, ds) in expected.items():
            e = by_id.get(eid)
            assert e is not None, f"{eid} missing"
            assert e.src_port.side == ss, f"{eid} src {e.src_port.side} != {ss}"
            assert e.dst_port.side == ds, f"{eid} dst {e.dst_port.side} != {ds}"

    def test_fallback_source_directions_point_outward(self):
        """AC5: source endpoint directions point outward from the source face."""
        fl = self._fallback_finalized()
        by_id = {re.edge_id: re for re in fl.routed_edges}
        # api:B → cache — source BOTTOM points down (+y); dest TOP points into cache (+y down).
        e = by_id["api->cache"]
        assert e.src_port.direction.y > 0, "BOTTOM source should point downward"
        # lb:R → api — source RIGHT points right (+x).
        e = by_id["lb->api"]
        assert e.src_port.direction.x > 0, "RIGHT source should point rightward"

    def test_fallback_typed_error_on_unknown_side(self):
        """AC6: an unknown declared side raises ArchitectureLayoutError, not AUTO."""
        from mermaid_render.errors import ArchitectureLayoutError
        from mermaid_render.layout.architecture import _resolve_fallback_port
        rect = Rect(0.0, 0.0, 100.0, 60.0)
        with pytest.raises(ArchitectureLayoutError):
            _resolve_fallback_port("n", rect, "Z", Point(100.0, 30.0),
                                   is_source=True, edge_id="n->m")

    def test_fallback_typed_error_on_offface_endpoint(self):
        """AC6: a routed endpoint that cannot honor the declared face raises."""
        from mermaid_render.errors import ArchitectureLayoutError
        from mermaid_render.layout.architecture import _resolve_fallback_port
        rect = Rect(0.0, 0.0, 100.0, 60.0)
        # declared RIGHT (face x=100) but endpoint sits at x=20 — cannot honor.
        with pytest.raises(ArchitectureLayoutError):
            _resolve_fallback_port("n", rect, "R", Point(20.0, 30.0),
                                   is_source=True, edge_id="n->m")

    def test_fallback_no_declared_side_infers_face(self):
        """AC5: an endpoint with no declared side infers the nearest face (never AUTO)."""
        from mermaid_render.layout.architecture import _resolve_fallback_port
        rect = Rect(0.0, 0.0, 100.0, 60.0)
        port = _resolve_fallback_port("n", rect, "", Point(100.0, 30.0),
                                      is_source=True, edge_id="n->m")
        assert port.side == PortSide.RIGHT
        assert port.side != PortSide.AUTO


# ── architecture-fixed-port-integration AC11: faithful-mode guard ─────────────

class TestFaithfulModeGuard:
    """Item-5 AC11 — faithful_mermaid=True adds no synchronous / service-boundary
    legend and infers no business semantics beyond the architecture source."""

    def _html(self, faithful: bool) -> str:
        import mermaid_render as mr
        return mr.to_html(COMPLEX_SRC, faithful=faithful)

    def test_faithful_no_synchronous_legend(self):
        assert "Synchronous" not in self._html(True)

    def test_faithful_no_service_boundary_legend(self):
        html = self._html(True)
        assert "Service boundary" not in html
        assert "diagram-legend" not in html

    def test_faithful_no_inferred_semantics(self):
        """Faithful output annotates no edge with async/critical-path semantics."""
        html = self._html(True)
        for term in ("Async / optional", "Critical path"):
            assert term not in html

    def test_editorial_variant_also_has_no_arch_legend(self):
        """architecture-complex has only solid edges, so neither variant shows a legend."""
        assert "diagram-legend" not in self._html(False)


# ── architecture-fixed-port-integration AC7/AC8/AC9: validation assertions ────

class TestArchitectureValidationAssertions:
    """Item-5 AC7/AC8/AC9 — service existence, group containment, and clean
    routing. Containment/existence hold on both backends; the no-interior-
    crossing assertion is validated on the Python fallback (the ELK path has a
    pre-existing api→cache/queue crossing tracked under
    arch-elk-edge-interior-crossing — see spec Deviations)."""

    def _fallback_finalized(self):
        with patch("mermaid_render.layout.elk_adapter.layout_with_elk",
                   side_effect=ElkUnavailable("forced fallback")):
            result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        return arch_to_finalized(result)

    def test_all_five_services_exist(self):
        """AC7: all five services are present in the layout."""
        fl = self._fallback_finalized()
        for nid in ("lb", "api", "db", "cache", "queue"):
            assert nid in fl.node_layouts, f"missing service {nid!r}"

    def test_all_services_inside_cloud_group(self):
        """AC8: every service is contained by the Cloud Platform group bounds."""
        fl = self._fallback_finalized()
        cloud = fl.group_layouts["cloud"]
        cb = cloud.boundary_bounds
        for nid, nl in fl.node_layouts.items():
            if nl.parent_group_id == "cloud":
                b = nl.outer_bounds
                assert (b.x >= cb.x and b.y >= cb.y
                        and b.x + b.w <= cb.x + cb.w
                        and b.y + b.h <= cb.y + cb.h), (
                    f"{nid} {b} not inside cloud {cb}"
                )

    def test_no_edge_crosses_service_interior_fallback(self):
        """AC9 (fallback): no route segment crosses a service interior or the
        Cloud Platform title band — the segment-aware validators are clean."""
        from mermaid_render.layout._layout_validation import (
            all_violations, translate_layout_to_positive,
        )
        fl = translate_layout_to_positive(self._fallback_finalized())
        assert all_violations(fl) == [], all_violations(fl)

    def test_stable_edge_ids_fallback(self):
        """AC10 (fallback): each relation carries a unique, non-empty edge_id."""
        fl = self._fallback_finalized()
        ids = [re.edge_id for re in fl.routed_edges]
        assert all(isinstance(i, str) and i for i in ids)
        assert len(ids) == len(set(ids)), f"duplicate edge_ids: {ids}"
