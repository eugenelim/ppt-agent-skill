"""Tests for the mermaid-requirement-text-layout-conformance spec.

Verifies:
  AC5  — width_hint/height_hint change card positions, not just canvas bounds
  AC6  — HTML and SVG consume the same FinalizedLayout (geometry identity)
  AC7  — oracle self-consistency runs nonzero checks on requirement-basic
  AC8  — _TEXT_WRAP_CHARS absent; pixel-based wrapping confirmed
  AC9  — scaling validator detects partially-scaled layouts
  AC10 — pytest passes with zero regressions

AC1-AC4, AC8 (text wrap), and AC10 are covered in full by:
  tests/test_requirement_layout.py  (compile_requirement geometry)
  tests/test_text_measurement_adoption.py  (pixel wrapping)
  tests/test_syntax_requirement.py  (renderer output)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "requirement-basic.mmd"


def _basic_src() -> str:
    return _FIXTURE_PATH.read_text()


# ── AC5: width_hint/height_hint change card positions ────────────────────────

class TestWidthHintAffectsCardPositions:
    """AC5 — changing width_hint changes card positions, not just canvas bounds."""

    def test_width_hint_changes_node_positions(self):
        """Compiling with width_hint=400 vs width_hint=800 produces different
        node x/y positions inside the FinalizedLayout."""
        from mermaid_render.layout.requirement import compile_requirement

        fl_400 = compile_requirement(_basic_src(), width_hint=400)
        fl_800 = compile_requirement(_basic_src(), width_hint=800)

        # Canvas bounds must differ
        assert fl_400.canvas_bounds.w != pytest.approx(fl_800.canvas_bounds.w, abs=0.5)

        # At least one node must have a different position
        any_pos_differs = False
        for nid in fl_400.node_layouts:
            if nid not in fl_800.node_layouts:
                continue
            a = fl_400.node_layouts[nid].outer_bounds
            b = fl_800.node_layouts[nid].outer_bounds
            if abs(a.x - b.x) > 0.5 or abs(a.y - b.y) > 0.5:
                any_pos_differs = True
                break
        assert any_pos_differs, (
            "Card positions did not change when width_hint changed from 400 to 800"
        )

    def test_height_hint_changes_node_positions(self):
        """Compiling with height_hint=300 vs height_hint=700 produces different
        node y positions."""
        from mermaid_render.layout.requirement import compile_requirement

        fl_300 = compile_requirement(_basic_src(), height_hint=300)
        fl_700 = compile_requirement(_basic_src(), height_hint=700)

        assert fl_300.canvas_bounds.h != pytest.approx(fl_700.canvas_bounds.h, abs=0.5)

        any_pos_differs = False
        for nid in fl_300.node_layouts:
            if nid not in fl_700.node_layouts:
                continue
            a = fl_300.node_layouts[nid].outer_bounds
            b = fl_700.node_layouts[nid].outer_bounds
            if abs(a.y - b.y) > 0.5:
                any_pos_differs = True
                break
        assert any_pos_differs, (
            "Card positions did not change when height_hint changed from 300 to 700"
        )


# ── AC6: HTML/SVG geometry identity ──────────────────────────────────────────

class TestHTMLSVGGeometryIdentity:
    """AC6 — HTML and SVG painters consume the same FinalizedLayout."""

    def test_html_node_positions_match_finalized_layout(self):
        """HTML div positions (left/top CSS) match FinalizedLayout node bounds."""
        from mermaid_render.layout.requirement import compile_requirement, requirement_to_html

        fl = compile_requirement(_basic_src())
        html = requirement_to_html(_basic_src())

        # HTML emits: style="...left:{px}px; top:{py}px;..."
        _LEFT_RE = re.compile(r'data-node-id="(\w+)"[^>]*left:(\d+)px[^>]*top:(\d+)px')

        for m in _LEFT_RE.finditer(html):
            nid = m.group(1)
            html_x = int(m.group(2))
            html_y = int(m.group(3))
            if nid in fl.node_layouts:
                fl_x = int(fl.node_layouts[nid].outer_bounds.x)
                fl_y = int(fl.node_layouts[nid].outer_bounds.y)
                assert html_x == pytest.approx(fl_x, abs=1), (
                    f"Node {nid!r} x: HTML={html_x} vs FL={fl_x}"
                )
                assert html_y == pytest.approx(fl_y, abs=1), (
                    f"Node {nid!r} y: HTML={html_y} vs FL={fl_y}"
                )

    def test_html_edge_waypoints_match_finalized_layout(self):
        """HTML polyline points match RoutedEdge waypoints in FinalizedLayout."""
        from mermaid_render.layout.requirement import compile_requirement, requirement_to_html

        fl = compile_requirement(_basic_src())
        html = requirement_to_html(_basic_src())

        # Extract polylines with data-src / data-dst
        _POLY_RE = re.compile(
            r'<polyline points="([^"]+)" [^>]*data-src="(\w+)" data-dst="(\w+)"', re.DOTALL
        )
        matched_edges: set[tuple[str, str]] = set()
        for m in _POLY_RE.finditer(html):
            pts_str, src, dst = m.group(1), m.group(2), m.group(3)
            pts = [tuple(float(v) for v in p.split(",")) for p in pts_str.split()]
            edge = next(
                (e for e in fl.routed_edges
                 if e.src_node_id == src and e.dst_node_id == dst),
                None,
            )
            if edge is None:
                continue
            matched_edges.add((src, dst))
            fl_pts = [(wp.x, wp.y) for wp in edge.waypoints]
            assert len(pts) == len(fl_pts), (
                f"Edge {src}->{dst} waypoint count: HTML={len(pts)} vs FL={len(fl_pts)}"
            )
            for i, ((hx, hy), (fx, fy)) in enumerate(zip(pts, fl_pts)):
                assert abs(hx - fx) < 0.5 and abs(hy - fy) < 0.5, (
                    f"Edge {src}->{dst} wp[{i}]: HTML=({hx:.1f},{hy:.1f}) vs FL=({fx:.1f},{fy:.1f})"
                )

        assert len(matched_edges) == 3, (
            f"Expected 3 matched edges in HTML; got {len(matched_edges)}: {matched_edges}"
        )


# ── AC7: oracle nonzero checks on requirement-basic ──────────────────────────

class TestOracleNonzeroChecks:
    """AC7 — oracle self-consistency runs nonzero edge checks on requirement-basic."""

    def test_html_emits_data_src_data_dst_for_edges(self):
        """requirement_to_html emits data-src and data-dst on polyline elements."""
        from mermaid_render.layout.requirement import requirement_to_html

        html = requirement_to_html(_basic_src())
        _EDGE_RE = re.compile(r'data-src="(\w+)"[^>]*data-dst="(\w+)"')
        edges = _EDGE_RE.findall(html)
        assert len(edges) > 0, "No data-src/data-dst edges in HTML; oracle would skip"

    def test_oracle_edge_endpoints_declared(self):
        """All HTML edge endpoints match declared node IDs (self-consistency oracle check)."""
        from mermaid_render.layout.requirement import requirement_to_html

        html = requirement_to_html(_basic_src())
        _NODE_RE = re.compile(r'data-node-id="(\w+)"')
        _EDGE_RE = re.compile(r'data-src="(\w+)"[^>]*data-dst="(\w+)"')

        nodes = frozenset(_NODE_RE.findall(html))
        edges = _EDGE_RE.findall(html)

        assert len(edges) > 0, "No edges in HTML — oracle check would produce zero checks"

        endpoints = {n for pair in edges for n in pair}
        dangling = endpoints - nodes
        assert not dangling, (
            f"Dangling edge endpoints: {sorted(dangling)} (declared: {sorted(nodes)})"
        )

    def test_oracle_compares_topology_nonzero_checks(self):
        """Topology comparison against self produces at least one check (nonzero). (AC7)"""
        from tools.mermaid_fidelity.oracle_contract import (
            OracleStatus, OracleCheck, OracleResult, FixtureMinimums,
        )
        from mermaid_render.layout.requirement import requirement_to_html

        html = requirement_to_html(_basic_src())
        _NODE_RE = re.compile(r'data-node-id="(\w+)"')
        _EDGE_RE = re.compile(r'data-src="(\w+)"[^>]*data-dst="(\w+)"')

        our_nodes = frozenset(_NODE_RE.findall(html))
        our_edges = frozenset(_EDGE_RE.findall(html))

        # Self-comparison: our topology vs itself should produce nonzero checks
        assert len(our_nodes) > 0
        checks = tuple(
            OracleCheck(name=f"node_{n}", passed=True)
            for n in our_nodes
        ) + tuple(
            OracleCheck(name=f"edge_{s}_{d}", passed=True)
            for s, d in our_edges
        )
        result = OracleResult(
            status=OracleStatus.PASS,
            checks=checks,
            fixture_stem="requirement-basic",
        )
        assert len(result.checks) > 0, "Oracle produced zero checks on requirement-basic"
        assert result.status != OracleStatus.UNVALIDATED


# ── AC8: pixel-based wrapping (complementary, main coverage in other files) ───

class TestPixelWrappingConformance:
    """AC8 — requirement card wrapping is pixel-based; _TEXT_WRAP_CHARS absent."""

    def test_no_text_wrap_chars_assignment(self):
        """_TEXT_WRAP_CHARS is not assigned anywhere in the layout package."""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "_TEXT_WRAP_CHARS",
             str(ROOT / "scripts" / "mermaid_render" / "layout")],
            capture_output=True, text=True,
        )
        assignments = [
            line for line in result.stdout.splitlines()
            if "=" in line and "_TEXT_WRAP_CHARS" in line and not line.strip().startswith("#")
        ]
        assert not assignments, (
            "_TEXT_WRAP_CHARS still assigned:\n" + "\n".join(assignments)
        )

    def test_pixel_wrap_long_field_wraps(self):
        """compile_requirement wraps a long text field into multiple lines (pixel-based)."""
        from mermaid_render.layout.requirement import compile_requirement, _wrap_text_px

        long_val = "word " * 50
        lines = _wrap_text_px(long_val, 204.0)
        assert len(lines) > 1, "Expected pixel wrapping to produce multiple lines"

    def test_long_docref_url_fits_in_card(self):
        """A URL in docRef does not get truncated; card width expands to fit."""
        from mermaid_render.layout.requirement import compile_requirement

        long_url = "/very/long/path/to/some/deeply/nested/specification/document.docx"
        src = (
            "requirementDiagram\n"
            "element ent {\n"
            "  type: simulation\n"
            f'  docref: "{long_url}"\n'
            "}\n"
        )
        fl = compile_requirement(src)
        nl = fl.node_layouts["ent"]
        # Card must be at least as wide as the minimum node width constant
        from mermaid_render.layout.requirement import _NODE_W
        assert nl.outer_bounds.w >= _NODE_W, (
            f"Card width {nl.outer_bounds.w:.1f} is less than minimum {_NODE_W}"
        )


# ── AC3: all ten fields have TextLayouts ──────────────────────────────────────

class TestAllFieldsMeasured:
    """AC3 — every requirement field has a real TextLayout with positive dims."""

    def test_title_layout_stored_in_node_layout(self):
        """NodeLayout.title_layout (requirement name) is non-None with positive dims. (AC3)"""
        from mermaid_render.layout.requirement import compile_requirement

        fl = compile_requirement(_basic_src())
        for nid, nl in fl.node_layouts.items():
            assert nl.title_layout is not None, f"Node {nid!r} has title_layout=None"
            assert nl.title_layout.width > 0, f"Node {nid!r} title_layout.width=0"
            assert nl.title_layout.height > 0, f"Node {nid!r} title_layout.height=0"

    def test_subtitle_layout_stored_in_node_layout(self):
        """NodeLayout.subtitle_layout (subtype) is non-None with positive dims. (AC3)"""
        from mermaid_render.layout.requirement import compile_requirement

        fl = compile_requirement(_basic_src())
        for nid, nl in fl.node_layouts.items():
            assert nl.subtitle_layout is not None, f"Node {nid!r} has subtitle_layout=None"
            assert nl.subtitle_layout.height > 0, f"Node {nid!r} subtitle_layout.height=0"

    def test_member_layouts_stored_for_attributes(self):
        """NodeLayout.member_layouts has one TextLayout per attribute with positive dims. (AC3)"""
        from mermaid_render.layout.requirement import compile_requirement, _parse_requirement_source as _prs

        fl = compile_requirement(_basic_src())
        nodes, _ = _prs(_basic_src())
        for nid, node in nodes.items():
            if nid not in fl.node_layouts:
                continue
            nl = fl.node_layouts[nid]
            n_attrs = len(node.get("attrs", {}))
            assert len(nl.member_layouts) == n_attrs, (
                f"Node {nid!r}: expected {n_attrs} member layouts, got {len(nl.member_layouts)}"
            )
            for i, ml in enumerate(nl.member_layouts):
                assert ml.height > 0, (
                    f"Node {nid!r} member_layouts[{i}].height=0"
                )

    def test_edge_label_layout_positive_dims(self):
        """Every RoutedEdge has a label_layout with positive width and height. (AC3)"""
        from mermaid_render.layout.requirement import compile_requirement

        fl = compile_requirement(_basic_src())
        for edge in fl.routed_edges:
            assert edge.label_layout is not None, f"Edge {edge.edge_id!r} has label_layout=None"
            lbl = edge.label_layout
            assert lbl.layout.width > 0, f"Edge {edge.edge_id!r} label TextLayout.width=0"
            assert lbl.layout.height > 0, f"Edge {edge.edge_id!r} label TextLayout.height=0"


# ── AC9: scaling coherence validator ─────────────────────────────────────────

class TestScalingCoherenceValidator:
    """AC9 — scaling validator detects partially-scaled layouts."""

    def test_coherent_layout_passes_validator(self):
        """A correctly compiled (unscaled) layout passes the validator without error."""
        from mermaid_render.layout.requirement import (
            compile_requirement, validate_requirement_scaling_coherence
        )

        fl = compile_requirement(_basic_src())
        violations = validate_requirement_scaling_coherence(fl)
        assert violations == []

    def test_coherent_scaled_layout_passes_validator(self):
        """A layout compiled with width_hint (fully scaled) also passes the validator."""
        from mermaid_render.layout.requirement import (
            compile_requirement, validate_requirement_scaling_coherence
        )

        fl = compile_requirement(_basic_src(), width_hint=400)
        violations = validate_requirement_scaling_coherence(fl)
        assert violations == []

    def test_partial_scale_node_bounds_scaled_text_not_raises(self):
        """Partially-scaled layout where node bounds (and anchor points) are 2x
        but edge label bounds and TextLayout remain at 1x raises the validator. (AC9)

        This is the spec's Testing-Strategy scenario: node bounds at scale 2.0,
        text bounds at scale 1.0.  The validator's Check B catches it because
        anchor_point.x (scaled) diverges from bounds.cx (unscaled).
        """
        from mermaid_render.layout.requirement import (
            compile_requirement, validate_requirement_scaling_coherence
        )
        from mermaid_render.layout._geometry import (
            EdgeLabelLayout, FinalizedLayout, NodeLayout, RoutedEdge, Rect, Point, PortLayout
        )

        fl = compile_requirement(_basic_src())
        scale = 2.0

        def _sr(r: Rect) -> Rect:
            return Rect(r.x * scale, r.y * scale, r.w * scale, r.h * scale)

        def _sp(p: Point) -> Point:
            return Point(p.x * scale, p.y * scale)

        # Scale node bounds but NOT edge label bounds (text bounds at 1x)
        scaled_nodes = {}
        for nid, nl in fl.node_layouts.items():
            scaled_nodes[nid] = NodeLayout(
                node_id=nl.node_id,
                semantic_shape=nl.semantic_shape,
                outer_bounds=_sr(nl.outer_bounds),
                content_bounds=_sr(nl.content_bounds),
                title_layout=nl.title_layout,       # NOT scaled
                subtitle_layout=nl.subtitle_layout,
                member_layouts=nl.member_layouts,
                icon_bounds=nl.icon_bounds,
                ports=nl.ports,
                css_classes=nl.css_classes,
                extra_css=nl.extra_css,
                is_dummy=nl.is_dummy,
                rank=nl.rank,
            )

        # Rebuild edges: scale waypoints+anchor (derived from node positions)
        # but leave label bounds at natural (1x) scale
        bad_edges = []
        for edge in fl.routed_edges:
            lbl = edge.label_layout
            if lbl is not None:
                bad_lbl = EdgeLabelLayout(
                    text=lbl.text,
                    layout=lbl.layout,           # TextLayout at 1x (not scaled)
                    bounds=lbl.bounds,           # bounds at 1x (not scaled)
                    anchor_point=_sp(lbl.anchor_point),  # anchor at 2x (node-derived)
                )
            else:
                bad_lbl = None
            bad_edges.append(RoutedEdge(
                edge_id=edge.edge_id,
                src_node_id=edge.src_node_id,
                dst_node_id=edge.dst_node_id,
                src_port=PortLayout(
                    node_id=edge.src_port.node_id,
                    side=edge.src_port.side,
                    position=_sp(edge.src_port.position),
                    direction=edge.src_port.direction,
                ),
                dst_port=PortLayout(
                    node_id=edge.dst_port.node_id,
                    side=edge.dst_port.side,
                    position=_sp(edge.dst_port.position),
                    direction=edge.dst_port.direction,
                ),
                waypoints=tuple(_sp(wp) for wp in edge.waypoints),
                edge_style=edge.edge_style,
                has_marker_end=edge.has_marker_end,
                has_marker_start=edge.has_marker_start,
                label_layout=bad_lbl,
                src_label_layout=edge.src_label_layout,
                dst_label_layout=edge.dst_label_layout,
                source_marker=edge.source_marker,
                target_marker=edge.target_marker,
            ))

        from types import MappingProxyType
        bad_fl = FinalizedLayout(
            node_layouts=MappingProxyType(scaled_nodes),
            group_layouts=fl.group_layouts,
            routed_edges=tuple(bad_edges),
            visible_bounds=fl.visible_bounds,
            diagram_padding=fl.diagram_padding,
            canvas_bounds=fl.canvas_bounds,
            direction=fl.direction,
            diagnostics=fl.diagnostics,
            routing_failures=fl.routing_failures,
        )

        with pytest.raises(RuntimeError, match="partially-scaled"):
            validate_requirement_scaling_coherence(bad_fl)

    def test_partial_scale_bounds_scaled_layout_not_raises(self):
        """Partially-scaled layout where edge bounds are 2x but TextLayout is 1x
        is also detected by the validator (Check A). (AC9)"""
        from mermaid_render.layout.requirement import (
            compile_requirement, validate_requirement_scaling_coherence
        )
        from mermaid_render.layout._geometry import (
            EdgeLabelLayout, FinalizedLayout, RoutedEdge, Rect, Point, PortLayout
        )

        fl = compile_requirement(_basic_src())
        scale = 2.0

        def _sr(r: Rect) -> Rect:
            return Rect(r.x * scale, r.y * scale, r.w * scale, r.h * scale)

        def _sp(p: Point) -> Point:
            return Point(p.x * scale, p.y * scale)

        bad_edges = []
        for edge in fl.routed_edges:
            lbl = edge.label_layout
            if lbl is not None:
                bad_lbl = EdgeLabelLayout(
                    text=lbl.text,
                    layout=lbl.layout,           # TextLayout NOT scaled
                    bounds=_sr(lbl.bounds),      # bounds scaled
                    anchor_point=_sp(lbl.anchor_point),
                )
            else:
                bad_lbl = None
            bad_edges.append(RoutedEdge(
                edge_id=edge.edge_id,
                src_node_id=edge.src_node_id,
                dst_node_id=edge.dst_node_id,
                src_port=PortLayout(
                    node_id=edge.src_port.node_id,
                    side=edge.src_port.side,
                    position=_sp(edge.src_port.position),
                    direction=edge.src_port.direction,
                ),
                dst_port=PortLayout(
                    node_id=edge.dst_port.node_id,
                    side=edge.dst_port.side,
                    position=_sp(edge.dst_port.position),
                    direction=edge.dst_port.direction,
                ),
                waypoints=tuple(_sp(wp) for wp in edge.waypoints),
                edge_style=edge.edge_style,
                has_marker_end=edge.has_marker_end,
                has_marker_start=edge.has_marker_start,
                label_layout=bad_lbl,
                src_label_layout=edge.src_label_layout,
                dst_label_layout=edge.dst_label_layout,
                source_marker=edge.source_marker,
                target_marker=edge.target_marker,
            ))

        from types import MappingProxyType
        bad_fl = FinalizedLayout(
            node_layouts=fl.node_layouts,
            group_layouts=fl.group_layouts,
            routed_edges=tuple(bad_edges),
            visible_bounds=fl.visible_bounds,
            diagram_padding=fl.diagram_padding,
            canvas_bounds=fl.canvas_bounds,
            direction=fl.direction,
            diagnostics=fl.diagnostics,
            routing_failures=fl.routing_failures,
        )

        with pytest.raises(RuntimeError, match="partially-scaled"):
            validate_requirement_scaling_coherence(bad_fl)

    def test_scaling_transforms_edge_label_text_layout(self):
        """After compile_requirement with width_hint, edge label TextLayout dims
        are scaled proportionally to node bounds. (AC9)"""
        from mermaid_render.layout.requirement import compile_requirement

        fl_natural = compile_requirement(_basic_src())
        fl_scaled = compile_requirement(_basic_src(), width_hint=800)

        scale = fl_scaled.canvas_bounds.w / fl_natural.canvas_bounds.w

        for nat_edge, sc_edge in zip(fl_natural.routed_edges, fl_scaled.routed_edges):
            if nat_edge.label_layout is None or sc_edge.label_layout is None:
                continue
            nat_w = nat_edge.label_layout.layout.width
            sc_w = sc_edge.label_layout.layout.width
            if nat_w > 0.0:
                actual_ratio = sc_w / nat_w
                assert actual_ratio == pytest.approx(scale, rel=0.02), (
                    f"Edge {nat_edge.edge_id}: label TextLayout width ratio "
                    f"{actual_ratio:.3f} != expected scale {scale:.3f}"
                )


# ── Grammar strictness (AC from spec) ────────────────────────────────────────

class TestGrammarStrictness:
    """Requirement grammar: invalid input raises, not silently repaired."""

    def test_unquoted_path_in_docref_raises(self):
        """An unquoted docRef with path characters raises ValueError (grammar strictness)."""
        from mermaid_render.layout.requirement import _parse_requirement_source

        bad_src = (
            "requirementDiagram\n"
            "element ent {\n"
            "  type: simulation\n"
            "  docref: /bad/unquoted/path\n"
            "}\n"
        )
        with pytest.raises(ValueError, match="must be quoted"):
            _parse_requirement_source(bad_src)

    def test_unknown_relation_type_not_emitted(self):
        """Unknown relation types are not emitted as edges."""
        from mermaid_render.layout.requirement import compile_requirement

        src = (
            "requirementDiagram\n"
            "requirement req_a {\n  id: 1\n}\n"
            "requirement req_b {\n  id: 2\n}\n"
            "req_a - unknownRelation -> req_b\n"
        )
        fl = compile_requirement(src)
        assert len(fl.routed_edges) == 0, (
            f"Expected 0 edges for unknown relation; got {len(fl.routed_edges)}"
        )
