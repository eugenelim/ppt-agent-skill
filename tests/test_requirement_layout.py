"""TDD tests for compile_requirement() — requirement-finalized-layout-sizing spec.

Every test in this file maps to at least one Acceptance Criterion in
docs/specs/requirement-finalized-layout-sizing/spec.md.

Test coverage:
  AC1-AC3  — basic fixture parses; 4 nodes and 3 edges present
  AC4      — long-text card height (no clipping)
  AC5      — no edge segment passes through any card
  AC6      — width_hint applied to canvas_bounds.w
  AC7      — height_hint applied to canvas_bounds.h
  AC8      — NodeLayout.css_classes contains requirement subtype
  AC9      — RoutedEdge.label_layout is non-None with correct rel-type text
  AC10     — HTML and SVG coordinates are identical (both read same FinalizedLayout)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.requirement import compile_requirement  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "requirement-basic.mmd"


def _basic_src() -> str:
    return _FIXTURE_PATH.read_text()


# The basic fixture has:
#   nodes:     test_req, func_req, perf_req, test_entity
#   relations: test_entity -satisfies-> test_req
#              test_entity -verifies->  perf_req
#              func_req    -derives->   test_req
_BASIC_NODES = {"test_req", "func_req", "perf_req", "test_entity"}
_BASIC_RELATIONS = {"satisfies", "verifies", "derives"}


# ---------------------------------------------------------------------------
# Task 1: TDD stubs for compile_requirement() — all 12 construction tests
# ---------------------------------------------------------------------------


class TestCompileRequirement:
    """compile_requirement() geometry and metadata invariants."""

    # ── AC1-AC2: basic fixture produces a FinalizedLayout with four nodes ──────

    def test_basic_returns_finalized_layout(self):
        """compile_requirement(src) on the basic fixture returns a FinalizedLayout."""
        from mermaid_render.layout._geometry import FinalizedLayout

        fl = compile_requirement(_basic_src())
        assert isinstance(fl, FinalizedLayout)

    def test_basic_four_nodes(self):
        """FinalizedLayout.node_layouts has exactly four entries. (AC2)"""
        fl = compile_requirement(_basic_src())
        assert set(fl.node_layouts.keys()) == _BASIC_NODES

    # ── AC3: three edges present ───────────────────────────────────────────────

    def test_basic_three_edges(self):
        """FinalizedLayout.routed_edges has exactly three entries. (AC3)"""
        fl = compile_requirement(_basic_src())
        assert len(fl.routed_edges) == 3

    # ── AC9: relation labels attached to every edge ────────────────────────────

    def test_relation_labels_attached(self):
        """Every RoutedEdge has a non-None label_layout with correct rel-type text. (AC9)"""
        fl = compile_requirement(_basic_src())
        assert len(fl.routed_edges) == 3, "Precondition: three edges"
        texts = set()
        for edge in fl.routed_edges:
            assert edge.label_layout is not None, (
                f"Edge {edge.edge_id!r} has label_layout=None"
            )
            texts.add(edge.label_layout.text)
        assert texts == _BASIC_RELATIONS

    # ── AC5: no edge segment passes through a card ────────────────────────────

    def test_no_edge_through_card(self):
        """No interior waypoint segment crosses any NodeLayout.outer_bounds. (AC5)"""
        fl = compile_requirement(_basic_src())
        card_boxes = [
            (nl.outer_bounds.x, nl.outer_bounds.y,
             nl.outer_bounds.x + nl.outer_bounds.w,
             nl.outer_bounds.y + nl.outer_bounds.h)
            for nl in fl.node_layouts.values()
        ]
        for edge in fl.routed_edges:
            wps = edge.waypoints
            for i in range(len(wps) - 1):
                x1, y1 = wps[i].x, wps[i].y
                x2, y2 = wps[i + 1].x, wps[i + 1].y
                for rx0, ry0, rx1, ry1 in card_boxes:
                    for t in (0.25, 0.5, 0.75):
                        px = x1 + t * (x2 - x1)
                        py = y1 + t * (y2 - y1)
                        inside = rx0 + 1 < px < rx1 - 1 and ry0 + 1 < py < ry1 - 1
                        assert not inside, (
                            f"Edge {edge.edge_id!r} segment interior "
                            f"({px:.1f}, {py:.1f}) is inside a card"
                        )

    # ── AC1: quoted path docref does not raise ────────────────────────────────

    def test_quoted_path_docref(self):
        """Source with a quoted docref path parses without ValueError. (AC1)"""
        src = (
            "requirementDiagram\n"
            "element doc_ent {\n"
            "  type: simulation\n"
            '  docref: "/refs/spec.docx"\n'
            "}\n"
        )
        fl = compile_requirement(src)
        assert "doc_ent" in fl.node_layouts

    # ── AC4: long text grows card height ──────────────────────────────────────

    def test_long_text_card_height(self):
        """A node with a long text value produces a taller NodeLayout
        than a node with a one-line text. (AC4 - pixel-based wrapping)"""
        long_text = "word " * 30  # 150 characters - clearly exceeds 204 px card text area
        src_long = (
            "requirementDiagram\n"
            "requirement long_req {\n"
            "  id: 1\n"
            f"  text: {long_text}\n"
            "}\n"
        )
        src_short = (
            "requirementDiagram\n"
            "requirement short_req {\n"
            "  id: 1\n"
            "  text: Short.\n"
            "}\n"
        )
        fl_long = compile_requirement(src_long)
        fl_short = compile_requirement(src_short)
        assert fl_long.node_layouts["long_req"].outer_bounds.h > \
               fl_short.node_layouts["short_req"].outer_bounds.h

    # ── Multiple outgoing relations use spread exit fractions ─────────────────

    def test_multiple_outgoing_relations(self):
        """A node with three outgoing relations produces three RoutedEdges
        exiting at distinct x-coordinates on the source face."""
        src = (
            "requirementDiagram\n"
            "requirement src_node {\n  id: 1\n}\n"
            "requirement tgt_a {\n  id: 2\n}\n"
            "requirement tgt_b {\n  id: 3\n}\n"
            "requirement tgt_c {\n  id: 4\n}\n"
            "src_node - satisfies -> tgt_a\n"
            "src_node - verifies -> tgt_b\n"
            "src_node - derives -> tgt_c\n"
        )
        fl = compile_requirement(src)
        src_edges = [e for e in fl.routed_edges if e.src_node_id == "src_node"]
        assert len(src_edges) == 3
        exit_xs = [e.waypoints[0].x for e in src_edges]
        assert len(set(exit_xs)) == 3, (
            f"Expected 3 distinct exit x-coords; got {exit_xs}"
        )

    # ── Same-rank edges use left/right faces ──────────────────────────────────

    def test_same_rank_relations(self):
        """A cyclic pair (both rank 0) produces an edge whose waypoints y-values
        are neither the source top-y nor the source bottom-y."""
        # A bidirectional cycle forces both nodes to rank 0 via the fallback in
        # _compute_ranks (neither node ever reaches in-degree 0 via BFS).
        src = (
            "requirementDiagram\n"
            "requirement req_cycle_a {\n  id: 1\n}\n"
            "requirement req_cycle_b {\n  id: 2\n}\n"
            "req_cycle_a - traces -> req_cycle_b\n"
            "req_cycle_b - traces -> req_cycle_a\n"
        )
        fl = compile_requirement(src)
        a_to_b = next(
            (e for e in fl.routed_edges
             if e.src_node_id == "req_cycle_a" and e.dst_node_id == "req_cycle_b"),
            None,
        )
        assert a_to_b is not None, "Edge req_cycle_a -> req_cycle_b not found"
        src_nl = fl.node_layouts["req_cycle_a"]
        src_top_y = src_nl.outer_bounds.y
        src_bot_y = src_nl.outer_bounds.y + src_nl.outer_bounds.h
        for wp in a_to_b.waypoints:
            assert abs(wp.y - src_top_y) > 0.5, (
                f"Waypoint y={wp.y:.1f} equals source top-y={src_top_y:.1f}"
            )
            assert abs(wp.y - src_bot_y) > 0.5, (
                f"Waypoint y={wp.y:.1f} equals source bottom-y={src_bot_y:.1f}"
            )

    # ── AC8: css_classes carries requirement subtype (memory + HTML + SVG) ────

    def test_semantic_subtype_in_css_classes(self):
        """Each NodeLayout.css_classes contains a req-<subtype> string and the
        subtype is present in both HTML and SVG rendered output. (AC8)"""
        from mermaid_render.layout.requirement import (
            layout_requirement_scene,
            requirement_to_html,
        )
        from mermaid_render.scene import SceneRect

        fl = compile_requirement(_basic_src())
        # ── in-memory check ─────────────────────────────────────────────────
        for nid, nl in fl.node_layouts.items():
            req_classes = [c for c in nl.css_classes if c.startswith("req-")]
            assert req_classes, (
                f"Node {nid!r} css_classes {nl.css_classes!r} has no req-* entry"
            )
        func_req_nl = fl.node_layouts.get("func_req")
        assert func_req_nl is not None
        assert any("functionalrequirement" in c.lower() for c in func_req_nl.css_classes), (
            f"func_req css_classes {func_req_nl.css_classes!r} does not contain "
            f"the functional requirement subtype"
        )

        # ── HTML rendered output ─────────────────────────────────────────────
        html = requirement_to_html(_basic_src())
        # func_req subtype class "req-functionalrequirement" must appear in HTML
        assert "req-functionalrequirement" in html, (
            "HTML output missing req-functionalrequirement subtype class"
        )

        # ── SVG scene data_attrs ─────────────────────────────────────────────
        scene = layout_requirement_scene(_basic_src())
        found_subtypes: set[str] = set()
        for _, elements in scene.layers:
            for elem in elements:
                if not isinstance(elem, SceneRect):
                    continue
                data = dict(getattr(elem, "data_attrs", ()))
                if "node-id" in data and "css-class" in data:
                    found_subtypes.add(data["css-class"])
        assert any("functionalrequirement" in cls.lower() for cls in found_subtypes), (
            f"SVG scene data_attrs missing functionalrequirement subtype; found: {found_subtypes}"
        )

    # ── AC6: width_hint applied ────────────────────────────────────────────────

    def test_width_hint_applied(self):
        """canvas_bounds.w == width_hint when width_hint is nonzero. (AC6)"""
        fl = compile_requirement(_basic_src(), width_hint=800)
        assert fl.canvas_bounds.w == pytest.approx(800.0, abs=0.5)

    # ── AC7: height_hint applied ───────────────────────────────────────────────

    def test_height_hint_applied(self):
        """canvas_bounds.h == height_hint when height_hint is nonzero. (AC7)"""
        fl = compile_requirement(_basic_src(), height_hint=600)
        assert fl.canvas_bounds.h == pytest.approx(600.0, abs=0.5)


# ---------------------------------------------------------------------------
# Task 5: AC10 — HTML and SVG coordinate identity
# ---------------------------------------------------------------------------


class TestCoordinateIdentity:
    """AC10: Both consumers read the same FinalizedLayout, so coordinates match."""

    def test_html_svg_coordinates_identical(self):
        """NodeLayout.outer_bounds.x/.y match SceneRect x/y, and
        RoutedEdge.waypoints match ScenePolyline.points (within 0.5 px). (AC10)"""
        from mermaid_render.layout.requirement import layout_requirement_scene
        from mermaid_render.scene import ScenePolyline, SceneRect

        src = _FIXTURE_PATH.read_text()

        fl = compile_requirement(src)
        scene = layout_requirement_scene(src)

        # Build card position map from SceneRect elements
        svg_card_positions: dict[str, tuple[float, float]] = {}
        for _, elements in scene.layers:
            for elem in elements:
                if not isinstance(elem, SceneRect):
                    continue
                data = dict(getattr(elem, "data_attrs", ()))
                if "node-id" in data:
                    svg_card_positions[data["node-id"]] = (elem.x, elem.y)

        for nid, nl in fl.node_layouts.items():
            assert nid in svg_card_positions, (
                f"Node {nid!r} in FinalizedLayout but missing from SvgScene"
            )
            svg_x, svg_y = svg_card_positions[nid]
            assert nl.outer_bounds.x == pytest.approx(svg_x, abs=0.5), (
                f"Node {nid!r} x: FL={nl.outer_bounds.x:.1f} vs SVG={svg_x:.1f}"
            )
            assert nl.outer_bounds.y == pytest.approx(svg_y, abs=0.5), (
                f"Node {nid!r} y: FL={nl.outer_bounds.y:.1f} vs SVG={svg_y:.1f}"
            )

        # Build edge waypoint map from ScenePolyline elements
        svg_edge_points: dict[tuple, tuple] = {}
        for _, elements in scene.layers:
            for elem in elements:
                if not isinstance(elem, ScenePolyline):
                    continue
                data = dict(getattr(elem, "data_attrs", ()))
                src_id = data.get("src")
                dst_id = data.get("dst")
                if src_id and dst_id:
                    svg_edge_points[(src_id, dst_id)] = elem.points

        for edge in fl.routed_edges:
            key = (edge.src_node_id, edge.dst_node_id)
            assert key in svg_edge_points, (
                f"Edge {key} in FinalizedLayout but missing from SvgScene polylines"
            )
            svg_pts = svg_edge_points[key]
            fl_pts = edge.waypoints
            assert len(fl_pts) == len(svg_pts), (
                f"Edge {key} waypoint count: FL={len(fl_pts)} vs SVG={len(svg_pts)}"
            )
            for i, (fl_wp, svg_pt) in enumerate(zip(fl_pts, svg_pts)):
                assert fl_wp.x == pytest.approx(svg_pt[0], abs=0.5), (
                    f"Edge {key} wp[{i}].x: FL={fl_wp.x:.1f} vs SVG={svg_pt[0]:.1f}"
                )
                assert fl_wp.y == pytest.approx(svg_pt[1], abs=0.5), (
                    f"Edge {key} wp[{i}].y: FL={fl_wp.y:.1f} vs SVG={svg_pt[1]:.1f}"
                )
