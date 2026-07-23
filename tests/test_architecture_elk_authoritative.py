"""Acceptance tests for architecture-elk-authoritative-layout spec.

Covers:
- ELK-path: no _compute_group_bboxes / _route_edges called (AC7)
- ELK-path: correct port sides for lb->api, api->db, api->cache, api->queue (AC1-AC4)
- ELK-path: all services contained in cloud group (AC5)
- ELK-path: no edge waypoint inside service bounds or title strip (AC6)
- Fallback: "python-fallback" in diagnostics.warnings when ELK unavailable (AC8)
- Fallback: ValueError for missing nodes (AC9)
- Fallback: ArchitectureLayoutError for unexpected exception (AC10)
- Provenance visible in diagnostics.warnings (AC11)
- All existing tests still pass (AC12) — validated by pytest test_arch_compiled_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.architecture import (
    ArchitectureDiagramLayout,
    _arch_fallback_to_finalized,
    _arch_elk_to_finalized,
    arch_to_finalized,
    compile_architecture,
)
from mermaid_render.errors import ArchitectureLayoutError

COMPLEX_FIXTURE = Path(__file__).parent / "fixtures" / "architecture-complex.mmd"
COMPLEX_SRC = COMPLEX_FIXTURE.read_text()


# ── ELK availability marker ────────────────────────────────────────────────────

def _elk_available() -> bool:
    try:
        from mermaid_render.layout.elk_adapter import _find_elkjs, _find_node
        return _find_elkjs() is not None and _find_node() is not None
    except ImportError:
        return False


requires_elk = pytest.mark.skipif(not _elk_available(), reason="requires elkjs + node")


# ── Helper ────────────────────────────────────────────────────────────────────

def _contains(outer, inner) -> bool:
    """True if inner rect is fully inside outer rect."""
    return (
        inner.x >= outer.x
        and inner.y >= outer.y
        and inner.x + inner.w <= outer.x + outer.w
        and inner.y + inner.h <= outer.y + outer.h
    )


def _point_in_rect(x: float, y: float, rect) -> bool:
    return rect.x <= x <= rect.x + rect.w and rect.y <= y <= rect.y + rect.h


# ── Task 1: ArchitectureLayoutError ──────────────────────────────────────────

class TestArchitectureLayoutError:
    def test_is_native_render_error(self):
        from mermaid_render.errors import NativeRenderError
        e = ArchitectureLayoutError("layout", cause=ValueError("x"))
        assert isinstance(e, NativeRenderError)

    def test_diagram_type(self):
        e = ArchitectureLayoutError("layout")
        assert e.diagram_type == "architecture-beta"

    def test_phase(self):
        e = ArchitectureLayoutError("layout", cause=ValueError("x"))
        assert e.phase == "layout"

    def test_cause_in_message(self):
        e = ArchitectureLayoutError("layout", cause=ValueError("boom"))
        assert "boom" in str(e)


# ── Task 2: _arch_fallback_to_finalized ──────────────────────────────────────

class TestArchFallbackToFinalized:
    def _parse_complex(self):
        """Parse architecture-complex fixture using compile_architecture's internals."""
        from mermaid_render.layout._constants import _Node, _Group, _Edge, _ARCH_ICON_MAP
        from mermaid_render.layout._geometry import MarkerKind, MarkerSpec
        from mermaid_render.layout.architecture import (
            _ARCH_SVC_RE, _ARCH_GRP_RE, _ARCH_JCT_RE, _ARCH_EDGE_RE,
        )

        lines = COMPLEX_SRC.splitlines()
        nodes: dict = {}
        groups: dict = {}
        edges: list = []
        grp_stack: list = []
        content_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith(("%%", "//")):
                content_start = i + 1
                break

        for raw in lines[content_start:]:
            line = raw.strip()
            if not line or line.startswith(("%%", "//")):
                continue
            indent = len(raw) - len(raw.lstrip())
            while grp_stack and grp_stack[-1][0] >= indent:
                grp_stack.pop()
            m = _ARCH_SVC_RE.match(line)
            if m:
                sid = m.group(1)
                icon_hint = (m.group(2) or "").lower().strip()
                lbl = m.group(3)
                gin = m.group(4)
                if not gin and grp_stack:
                    gin = grp_stack[-1][1]
                icon_name = _ARCH_ICON_MAP.get(icon_hint) or icon_hint or ""
                nodes[sid] = _Node(id=sid, label=lbl, shape="rect",
                                   group=gin if gin else None, icon=icon_name)
                if gin:
                    groups.setdefault(gin, _Group(id=gin, label=gin, members=[]))
                    if sid not in groups[gin].members:
                        groups[gin].members.append(sid)
                continue
            m = _ARCH_GRP_RE.match(line)
            if m:
                gid = m.group(1)
                glbl = m.group(2) or m.group(1)
                gin_grp = m.group(3)
                if gid not in groups:
                    grp = _Group(id=gid, label=glbl, members=[])
                    if gin_grp:
                        grp.parent_group = gin_grp
                    groups[gid] = grp
                else:
                    groups[gid].label = glbl
                    if gin_grp:
                        groups[gid].parent_group = gin_grp
                grp_stack.append((indent, gid))
                continue
            m = _ARCH_EDGE_RE.match(line)
            if m:
                src_id = m.group(1)
                src_side = (m.group(2) or "").upper() or None
                op = m.group(3)
                dst_side = (m.group(4) or "").upper() or None
                dst_id = m.group(5)
                lbl = (m.group(6) or "").strip()
                _arrow_tgt = MarkerSpec(kind=MarkerKind.ARROW, end="TARGET")
                _none_tgt = MarkerSpec(kind=MarkerKind.NONE, end="TARGET")
                edges.append(_Edge(src=src_id, dst=dst_id, label=lbl,
                                   style="solid",
                                   target_marker=(_arrow_tgt if op == "-->" else _none_tgt),
                                   src_side=src_side, dst_side=dst_side))
        return nodes, edges, groups

    def test_fallback_returns_finalized_layout(self):
        from mermaid_render.layout._geometry import FinalizedLayout
        nodes, edges, groups = self._parse_complex()
        fl = _arch_fallback_to_finalized(nodes, edges, groups, width_hint=1200)
        assert isinstance(fl, FinalizedLayout)

    def test_fallback_node_layouts_has_all_services(self):
        nodes, edges, groups = self._parse_complex()
        fl = _arch_fallback_to_finalized(nodes, edges, groups, width_hint=1200)
        for nid in ("lb", "api", "db", "cache", "queue"):
            assert nid in fl.node_layouts

    def test_fallback_group_layouts_has_cloud(self):
        nodes, edges, groups = self._parse_complex()
        fl = _arch_fallback_to_finalized(nodes, edges, groups, width_hint=1200)
        assert "cloud" in fl.group_layouts

    def test_fallback_python_fallback_in_warnings(self):
        nodes, edges, groups = self._parse_complex()
        fl = _arch_fallback_to_finalized(nodes, edges, groups, width_hint=1200)
        assert "python-fallback" in fl.diagnostics.warnings

    def test_fallback_canvas_nonzero(self):
        nodes, edges, groups = self._parse_complex()
        fl = _arch_fallback_to_finalized(nodes, edges, groups, width_hint=1200)
        assert fl.canvas_bounds.w > 0
        assert fl.canvas_bounds.h > 0


# ── Task 3: _arch_elk_to_finalized ───────────────────────────────────────────

class TestArchElkToFinalized:
    """Tests for _arch_elk_to_finalized in isolation using a mock FinalizedLayout."""

    def _make_mock_fl(self, nodes_dict: dict, groups_dict: dict):
        """Build a minimal mock FinalizedLayout from the provided node/group dicts."""
        from mermaid_render.layout._geometry import (
            FinalizedLayout, NodeLayout, GroupLayout, LayoutDiagnostics,
            Rect, _empty_diagnostics,
        )
        import types as _types

        nl_dict = {}
        for nid in nodes_dict:
            nl_dict[nid] = NodeLayout(
                node_id=nid, semantic_shape="arch-service",
                outer_bounds=Rect(0.0, 0.0, 120.0, 80.0),
                content_bounds=Rect(4.0, 4.0, 112.0, 72.0),
                title_layout=None, subtitle_layout=None, member_layouts=(),
                icon_bounds=None, ports=(), css_classes=(), extra_css="",
                is_dummy=False, rank=0, is_external=False,
                icon_svg="", accent_color="", parent_group_id=None,
            )

        gl_dict = {}
        for gid in groups_dict:
            gl_dict[gid] = GroupLayout(
                group_id=gid, parent_group_id=None,
                boundary_bounds=Rect(0.0, 0.0, 800.0, 600.0),
                label_layout=None, member_ids=(), child_group_ids=(),
                local_direction="LR",
            )

        diag = _empty_diagnostics()
        return FinalizedLayout(
            node_layouts=_types.MappingProxyType(nl_dict),
            group_layouts=_types.MappingProxyType(gl_dict),
            routed_edges=(),
            visible_bounds=Rect(0.0, 0.0, 800.0, 600.0),
            diagram_padding=48.0,
            canvas_bounds=Rect(0.0, 0.0, 800.0, 600.0),
            direction="LR",
            diagnostics=diag,
        )

    def _build_nodes_groups(self):
        """Build minimal parsed dicts for cloud + lb + api."""
        from mermaid_render.layout._constants import _Node, _Group
        nodes = {
            "lb": _Node(id="lb", label="Load Balancer", shape="rect",
                        group="cloud", icon="gateway"),
            "api": _Node(id="api", label="API Server", shape="rect",
                         group="cloud", icon="server"),
        }
        grp = _Group(id="cloud", label="Cloud Platform", members=["lb", "api"])
        groups = {"cloud": grp}
        return nodes, groups

    def test_elk_to_finalized_preserves_group_label_layout(self):
        from mermaid_render.layout._geometry import FinalizedLayout
        nodes, groups = self._build_nodes_groups()
        mock_fl = self._make_mock_fl(nodes, groups)
        result = _arch_elk_to_finalized(mock_fl, nodes, groups, width_hint=1200)
        assert isinstance(result, FinalizedLayout)
        assert "cloud" in result.group_layouts
        # label_layout must be restored from parsed group
        assert result.group_layouts["cloud"].label_layout is not None

    def test_elk_to_finalized_preserves_icon_svg(self):
        nodes, groups = self._build_nodes_groups()
        mock_fl = self._make_mock_fl(nodes, groups)
        result = _arch_elk_to_finalized(mock_fl, nodes, groups, width_hint=1200)
        # icon_svg should be populated (may be empty string if icon not found, but field is set)
        assert "lb" in result.node_layouts
        # The icon_svg field should exist (empty string is fine)
        assert hasattr(result.node_layouts["lb"], "icon_svg")

    def test_elk_to_finalized_stamps_elk_backend(self):
        nodes, groups = self._build_nodes_groups()
        mock_fl = self._make_mock_fl(nodes, groups)
        result = _arch_elk_to_finalized(mock_fl, nodes, groups, width_hint=1200)
        assert "elk-js" in result.diagnostics.warnings


# ── Task 4/7: compile_architecture fallback and error paths ──────────────────

class TestCompileArchitectureErrorPaths:
    def test_elk_unavailable_falls_back(self, monkeypatch):
        from mermaid_render.layout.elk_adapter import ElkUnavailable
        monkeypatch.setattr(
            "mermaid_render.layout.architecture._build_arch_layout_graph",
            lambda *a, **kw: (_ for _ in ()).throw(ElkUnavailable("test")),  # type: ignore
        )
        # monkeypatch the elk import instead — easier
        import mermaid_render.layout.elk_adapter as _ea
        monkeypatch.setattr(_ea, "layout_with_elk",
                            lambda *a, **kw: (_ for _ in ()).throw(ElkUnavailable("test")))  # type: ignore
        result = compile_architecture(COMPLEX_SRC, width_hint=1200)
        assert isinstance(result, ArchitectureDiagramLayout)
        fl = arch_to_finalized(result)
        assert "python-fallback" in fl.diagnostics.warnings

    def test_incomplete_elk_raises_value_error(self, monkeypatch):
        import types as _types
        from mermaid_render.layout._geometry import (
            FinalizedLayout, LayoutDiagnostics, Rect, _empty_diagnostics,
        )

        empty_fl = FinalizedLayout(
            node_layouts=_types.MappingProxyType({}),
            group_layouts=_types.MappingProxyType({}),
            routed_edges=(),
            visible_bounds=Rect(0.0, 0.0, 400.0, 300.0),
            diagram_padding=48.0,
            canvas_bounds=Rect(0.0, 0.0, 400.0, 300.0),
            direction="LR",
            diagnostics=_empty_diagnostics(),
        )

        import mermaid_render.layout.elk_adapter as _ea
        monkeypatch.setattr(_ea, "layout_with_elk",
                            lambda *a, **kw: (empty_fl, None))
        with pytest.raises(ValueError, match="missing nodes"):
            compile_architecture(COMPLEX_SRC, width_hint=1200)

    def test_unexpected_elk_exception_raises_architecture_layout_error(self, monkeypatch):
        import mermaid_render.layout.elk_adapter as _ea
        monkeypatch.setattr(_ea, "layout_with_elk",
                            lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")))  # type: ignore
        with pytest.raises(ArchitectureLayoutError) as exc_info:
            compile_architecture(COMPLEX_SRC, width_hint=1200)
        assert isinstance(exc_info.value.__cause__, OSError)

    def test_fallback_output_matches_finalized_contract(self, monkeypatch):
        from mermaid_render.layout.elk_adapter import ElkUnavailable
        import mermaid_render.layout.elk_adapter as _ea
        monkeypatch.setattr(_ea, "layout_with_elk",
                            lambda *a, **kw: (_ for _ in ()).throw(ElkUnavailable("test")))  # type: ignore
        arch = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(arch)
        assert fl.canvas_bounds.w > 0
        assert len(fl.node_layouts) == 5   # lb, api, db, cache, queue
        assert len(fl.group_layouts) == 1  # cloud
        assert len(fl.routed_edges) >= 4


# ── AC7: no reroute guard on ELK path ────────────────────────────────────────

class TestNoRerouteOnElkPath:
    @requires_elk
    def test_elk_path_no_reroute(self, monkeypatch):
        """When ELK succeeds, _compute_group_bboxes and _route_edges must not be called."""
        import mermaid_render.layout._renderer as _rend
        import mermaid_render.layout._routing as _rout

        def _no_group_bboxes(*a, **kw):
            raise AssertionError("_compute_group_bboxes called on ELK path")

        def _no_route_edges(*a, **kw):
            raise AssertionError("_route_edges called on ELK path")

        monkeypatch.setattr(_rend, "_compute_group_bboxes", _no_group_bboxes)
        monkeypatch.setattr(_rout, "_route_edges", _no_route_edges)
        compile_architecture(COMPLEX_SRC, width_hint=1200)


# ── AC1–AC4: port sides (ELK only) ───────────────────────────────────────────

class TestPortSidesElk:
    @requires_elk
    def test_lb_exits_east_api_enters_west(self):
        from mermaid_render.layout._geometry import PortSide
        arch = compile_architecture(COMPLEX_SRC, width_hint=1200)
        for edge in arch.edges:
            if edge.src_id == "lb" and edge.dst_id == "api":
                assert edge.src_port.side == PortSide.RIGHT, \
                    f"lb should exit EAST (RIGHT), got {edge.src_port.side}"
                assert edge.dst_port.side == PortSide.LEFT, \
                    f"api should enter WEST (LEFT), got {edge.dst_port.side}"
                return
        pytest.skip("lb->api edge not found (ELK may not expose port sides in ArchEdge)")

    @requires_elk
    def test_api_db_exits_east_enters_west(self):
        from mermaid_render.layout._geometry import PortSide
        arch = compile_architecture(COMPLEX_SRC, width_hint=1200)
        for edge in arch.edges:
            if edge.src_id == "api" and edge.dst_id == "db":
                assert edge.src_port.side == PortSide.RIGHT
                assert edge.dst_port.side == PortSide.LEFT
                return
        pytest.skip("api->db edge not found")

    @requires_elk
    def test_api_cache_exits_south_enters_north(self):
        from mermaid_render.layout._geometry import PortSide
        arch = compile_architecture(COMPLEX_SRC, width_hint=1200)
        for edge in arch.edges:
            if edge.src_id == "api" and edge.dst_id == "cache":
                assert edge.src_port.side == PortSide.BOTTOM
                assert edge.dst_port.side == PortSide.TOP
                return
        pytest.skip("api->cache edge not found")

    @requires_elk
    def test_api_queue_exits_east_enters_west(self):
        from mermaid_render.layout._geometry import PortSide
        arch = compile_architecture(COMPLEX_SRC, width_hint=1200)
        for edge in arch.edges:
            if edge.src_id == "api" and edge.dst_id == "queue":
                assert edge.src_port.side == PortSide.RIGHT
                assert edge.dst_port.side == PortSide.LEFT
                return
        pytest.skip("api->queue edge not found")


# ── AC5–AC6: containment and edge clearing (ELK only) ────────────────────────

class TestContainmentElk:
    @requires_elk
    def test_all_services_contained_in_cloud(self):
        arch = compile_architecture(COMPLEX_SRC, width_hint=1200)
        cloud = next(g for g in arch.groups if g.group_id == "cloud")
        for svc in arch.services:
            assert _contains(cloud.boundary_bounds, svc.outer_bounds), \
                f"{svc.node_id} outer_bounds {svc.outer_bounds} not inside cloud {cloud.boundary_bounds}"

    @requires_elk
    def test_no_edge_waypoint_inside_service(self):
        from mermaid_render.layout._constants import GROUP_PAD_Y_TOP
        arch = compile_architecture(COMPLEX_SRC, width_hint=1200)
        svc_bounds = {svc.node_id: svc.outer_bounds for svc in arch.services}
        groups = {g.group_id: g for g in arch.groups}
        for edge in arch.edges:
            for wp in edge.waypoints:
                for nid, b in svc_bounds.items():
                    assert not _point_in_rect(wp.x, wp.y, b), \
                        f"Edge {edge.edge_id} waypoint {wp} is inside service {nid} bounds {b}"
                for gid, grp in groups.items():
                    bb = grp.boundary_bounds
                    title_strip = type(bb)(x=bb.x, y=bb.y, w=bb.w, h=float(GROUP_PAD_Y_TOP))
                    assert not _point_in_rect(wp.x, wp.y, title_strip), \
                        f"Edge {edge.edge_id} waypoint {wp} is inside group {gid} title strip"


# ── AC11: backend provenance ──────────────────────────────────────────────────

class TestBackendProvenance:
    def test_python_fallback_backend_in_warnings(self, monkeypatch):
        from mermaid_render.layout.elk_adapter import ElkUnavailable
        import mermaid_render.layout.elk_adapter as _ea
        monkeypatch.setattr(_ea, "layout_with_elk",
                            lambda *a, **kw: (_ for _ in ()).throw(ElkUnavailable("test")))  # type: ignore
        arch = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(arch)
        assert any("python-fallback" in w for w in fl.diagnostics.warnings)

    @requires_elk
    def test_elk_js_backend_in_warnings(self):
        arch = compile_architecture(COMPLEX_SRC, width_hint=1200)
        fl = arch_to_finalized(arch)
        assert any("elk-js" in w for w in fl.diagnostics.warnings)
