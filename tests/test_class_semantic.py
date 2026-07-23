"""Semantic tests for class-diagram-marker-semantics and _compile_classdiagram.

Verifies that each UML relationship operator in class-relationships-all.mmd
maps to the correct MarkerSpec (kind, end, line_style) and that the rendered
HTML uses the right SVG marker attributes.

Also tests _compile_classdiagram() and its NodeLayout.member_layouts output.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from mermaid_render.layout._geometry import MarkerKind, MarkerSpec
from mermaid_render.layout._strategies import _CLASS_REL_RE, _class_rel_markers

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "class-relationships-all.mmd"


# ── helpers ───────────────────────────────────────────────────────────────────

def _dispatch(src: str, width: int = 800) -> str:
    """Render classDiagram source to HTML via the HTML pipeline."""
    from mermaid_render.layout._strategies import _dispatch_diagram
    try:
        return _dispatch_diagram(src, None, width)
    except Exception:
        from mermaid_render.layout._strategies import _layout_class
        return _layout_class(src, "TB", width)


def _parse_fixture_relations() -> list[dict]:
    """Parse all relation lines from the fixture and return structured dicts."""
    src = FIXTURE_PATH.read_text()
    results = []
    for raw in src.splitlines():
        line = raw.strip()
        m = _CLASS_REL_RE.match(line)
        if not m:
            continue
        c1, mul_src, op, mul_dst, c2, lbl = (
            m.group(1), m.group(2) or "", m.group(3),
            m.group(4) or "", m.group(5), m.group(6) or "",
        )
        src_spec, tgt_spec, line_style = _class_rel_markers(op)
        results.append({
            "src": c1, "dst": c2, "op": op, "lbl": lbl.strip(),
            "mul_src": mul_src, "mul_dst": mul_dst,
            "source_marker": src_spec,
            "target_marker": tgt_spec,
            "line_style": line_style,
        })
    return results


# ── MarkerSpec model tests ────────────────────────────────────────────────────

class TestMarkerSpecModel:
    """MarkerSpec dataclass behaves correctly."""

    def test_valid_source_end(self):
        spec = MarkerSpec(kind=MarkerKind.HOLLOW_TRIANGLE, end="SOURCE")
        assert spec.kind == MarkerKind.HOLLOW_TRIANGLE
        assert spec.end == "SOURCE"

    def test_valid_target_end(self):
        spec = MarkerSpec(kind=MarkerKind.OPEN_ARROW, end="TARGET")
        assert spec.end == "TARGET"

    def test_invalid_end_raises(self):
        with pytest.raises(ValueError, match="SOURCE.*TARGET"):
            MarkerSpec(kind=MarkerKind.NONE, end="MIDDLE")

    def test_default_size(self):
        spec = MarkerSpec(kind=MarkerKind.NONE, end="SOURCE")
        assert spec.size == 10.0

    def test_default_clearance(self):
        spec = MarkerSpec(kind=MarkerKind.NONE, end="TARGET")
        assert spec.clearance == 0.0

    def test_none_spec_kind(self):
        spec = MarkerSpec(kind=MarkerKind.NONE, end="SOURCE")
        assert spec.kind == MarkerKind.NONE

    def test_frozen(self):
        spec = MarkerSpec(kind=MarkerKind.NONE, end="SOURCE")
        with pytest.raises(Exception):
            spec.kind = MarkerKind.ARROW  # type: ignore[misc]


# ── _class_rel_markers unit tests ─────────────────────────────────────────────

class TestClassRelMarkers:
    """_class_rel_markers maps every operator to correct MarkerSpec pair."""

    def _m(self, op: str):
        return _class_rel_markers(op)

    # Inheritance: hollow triangle at SOURCE
    def test_inherit_solid(self):
        src, tgt, style = self._m("<|--")
        assert src.kind == MarkerKind.HOLLOW_TRIANGLE
        assert src.end == "SOURCE"
        assert tgt.kind == MarkerKind.NONE
        assert style == "cls-solid"

    def test_inherit_dashed_src(self):
        src, tgt, style = self._m("<|..")
        assert src.kind == MarkerKind.HOLLOW_TRIANGLE
        assert src.end == "SOURCE"
        assert style == "cls-dotted"

    # Composition: filled diamond at SOURCE
    def test_composition(self):
        src, tgt, style = self._m("*--")
        assert src.kind == MarkerKind.FILLED_DIAMOND
        assert src.end == "SOURCE"
        assert tgt.kind == MarkerKind.NONE
        assert style == "cls-solid"

    # Composition right-to-left: filled diamond at TARGET
    def test_composition_rev(self):
        src, tgt, style = self._m("--*")
        assert src.kind == MarkerKind.NONE
        assert tgt.kind == MarkerKind.FILLED_DIAMOND
        assert tgt.end == "TARGET"

    # Aggregation: hollow diamond at SOURCE
    def test_aggregation(self):
        src, tgt, style = self._m("o--")
        assert src.kind == MarkerKind.HOLLOW_DIAMOND
        assert src.end == "SOURCE"
        assert tgt.kind == MarkerKind.NONE
        assert style == "cls-solid"

    # Aggregation right-to-left: hollow diamond at TARGET
    def test_aggregation_rev(self):
        src, tgt, style = self._m("--o")
        assert src.kind == MarkerKind.NONE
        assert tgt.kind == MarkerKind.HOLLOW_DIAMOND
        assert tgt.end == "TARGET"

    # Association: open arrow at TARGET
    def test_association(self):
        src, tgt, style = self._m("-->")
        assert src.kind == MarkerKind.NONE
        assert tgt.kind == MarkerKind.OPEN_ARROW
        assert tgt.end == "TARGET"
        assert style == "cls-solid"

    # Dependency: open arrow at TARGET, dashed
    def test_dependency_dashed(self):
        src, tgt, style = self._m("..>")
        assert src.kind == MarkerKind.NONE
        assert tgt.kind == MarkerKind.OPEN_ARROW
        assert tgt.end == "TARGET"
        assert style == "cls-dotted"

    # Realization: hollow triangle at TARGET, dashed
    def test_realization(self):
        src, tgt, style = self._m("..|>")
        assert src.kind == MarkerKind.NONE
        assert tgt.kind == MarkerKind.HOLLOW_TRIANGLE
        assert tgt.end == "TARGET"
        assert style == "cls-dotted"

    # Right-side inheritance notation: hollow triangle at TARGET, solid
    def test_right_inherit(self):
        src, tgt, style = self._m("|>")
        assert src.kind == MarkerKind.NONE
        assert tgt.kind == MarkerKind.HOLLOW_TRIANGLE
        assert tgt.end == "TARGET"
        assert style == "cls-solid"

    # Plain dashed link: open arrow at TARGET, dotted (fallback)
    def test_plain_dashed(self):
        src, tgt, style = self._m("..")
        assert tgt.kind == MarkerKind.OPEN_ARROW
        assert style == "cls-dotted"

    # Double pipe: open arrow at TARGET, solid (association fallback)
    def test_double_pipe(self):
        src, tgt, style = self._m("||")
        assert tgt.kind == MarkerKind.OPEN_ARROW
        assert style == "cls-solid"


# ── Fixture relation semantics ────────────────────────────────────────────────

class TestFixtureRelationSemantics:
    """Every relation in class-relationships-all.mmd has the right MarkerSpec."""

    _RELATIONS = _parse_fixture_relations()

    def _rel(self, src: str, dst: str) -> dict:
        for r in self._RELATIONS:
            if r["src"] == src and r["dst"] == dst:
                return r
        raise AssertionError(f"Relation {src}→{dst} not found in fixture")

    def test_count(self):
        """Fixture has exactly 7 relation lines."""
        assert len(self._RELATIONS) == 7

    def test_animal_dog_inherit(self):
        r = self._rel("Animal", "Dog")
        assert r["source_marker"].kind == MarkerKind.HOLLOW_TRIANGLE
        assert r["source_marker"].end == "SOURCE"
        assert r["target_marker"].kind == MarkerKind.NONE
        assert r["line_style"] == "cls-solid"
        assert r["lbl"] == "inherits"

    def test_animal_cat_inherit(self):
        r = self._rel("Animal", "Cat")
        assert r["source_marker"].kind == MarkerKind.HOLLOW_TRIANGLE
        assert r["source_marker"].end == "SOURCE"
        assert r["target_marker"].kind == MarkerKind.NONE
        assert r["line_style"] == "cls-solid"

    def test_car_engine_composition(self):
        r = self._rel("Car", "Engine")
        assert r["source_marker"].kind == MarkerKind.FILLED_DIAMOND
        assert r["source_marker"].end == "SOURCE"
        assert r["target_marker"].kind == MarkerKind.NONE
        assert r["line_style"] == "cls-solid"
        assert r["lbl"] == "composed of"

    def test_pond_duck_aggregation(self):
        r = self._rel("Pond", "Duck")
        assert r["source_marker"].kind == MarkerKind.HOLLOW_DIAMOND
        assert r["source_marker"].end == "SOURCE"
        assert r["target_marker"].kind == MarkerKind.NONE
        assert r["line_style"] == "cls-solid"
        assert r["lbl"] == "aggregates"

    def test_person_address_association(self):
        r = self._rel("Person", "Address")
        assert r["source_marker"].kind == MarkerKind.NONE
        assert r["target_marker"].kind == MarkerKind.OPEN_ARROW
        assert r["target_marker"].end == "TARGET"
        assert r["line_style"] == "cls-solid"
        assert r["lbl"] == "has"

    def test_iflyable_bird_dependency(self):
        r = self._rel("IFlyable", "Bird")
        assert r["source_marker"].kind == MarkerKind.NONE
        assert r["target_marker"].kind == MarkerKind.OPEN_ARROW
        assert r["target_marker"].end == "TARGET"
        assert r["line_style"] == "cls-dotted"
        assert r["lbl"] == "dependency"

    def test_teacher_professor_realization(self):
        r = self._rel("Teacher", "Professor")
        assert r["source_marker"].kind == MarkerKind.NONE
        assert r["target_marker"].kind == MarkerKind.HOLLOW_TRIANGLE
        assert r["target_marker"].end == "TARGET"
        assert r["line_style"] == "cls-dotted"
        assert r["lbl"] == "realization"


# ── Rendered HTML marker assertions ──────────────────────────────────────────

class TestRenderedMarkers:
    """HTML output uses the correct SVG marker IDs and dash styles."""

    def _render(self, snippet: str) -> str:
        from mermaid_render.layout._strategies import _layout_class
        return _layout_class(f"classDiagram\n{snippet}", "TB", 800)

    def test_inherit_uses_marker_start(self):
        """<|-- uses marker-start (source-end) with cls-inherit-rev."""
        html = self._render("Animal <|-- Dog")
        assert 'marker-start="url(#cls-inherit-rev)"' in html

    def test_composition_uses_marker_start(self):
        """*-- uses marker-start (source-end) with cls-composition-rev."""
        html = self._render("Car *-- Engine")
        assert 'marker-start="url(#cls-composition-rev)"' in html

    def test_aggregation_uses_marker_start(self):
        """o-- uses marker-start (source-end) with cls-aggregation-rev."""
        html = self._render("Pond o-- Duck")
        assert 'marker-start="url(#cls-aggregation-rev)"' in html

    def test_association_uses_marker_end(self):
        """-> uses marker-end (target-end) with cls-dep."""
        html = self._render("Person --> Address")
        assert 'marker-end="url(#cls-dep)"' in html
        assert 'marker-start="url(#cls-dep' not in html

    def test_dependency_uses_marker_end_and_dash(self):
        """..> uses marker-end and stroke-dasharray."""
        html = self._render("IFlyable ..> Bird")
        assert 'marker-end="url(#cls-dep)"' in html
        assert 'stroke-dasharray="6 4"' in html

    def test_realization_uses_marker_end_and_dash(self):
        """..|> uses marker-end (target hollow triangle) and stroke-dasharray."""
        html = self._render("Teacher ..|> Professor")
        assert 'marker-end="url(#cls-inherit)"' in html
        assert 'stroke-dasharray="6 4"' in html

    def test_no_marker_reversal_on_realization(self):
        """..|> must NOT use marker-start — triangle is at target end."""
        html = self._render("Teacher ..|> Professor")
        assert 'marker-start="url(#cls-inherit' not in html

    def test_no_marker_reversal_on_association(self):
        """--> must NOT use marker-start for cls-dep."""
        html = self._render("Person --> Address")
        assert 'marker-start="url(#cls-dep' not in html

    def test_inherit_marker_is_hollow(self):
        """cls-inherit-rev polygon must have fill='none'."""
        html = self._render("Animal <|-- Dog")
        m = re.search(r'<marker id="cls-inherit(?:-rev)?"[^>]*>(.*?)</marker>', html, re.DOTALL)
        assert m, "cls-inherit(-rev) marker must be defined"
        assert 'fill="none"' in m.group(1)

    def test_composition_marker_is_filled(self):
        """cls-composition-rev polygon must NOT have fill='none'."""
        html = self._render("Car *-- Engine")
        m = re.search(r'<marker id="cls-composition(?:-rev)?"[^>]*>(.*?)</marker>', html, re.DOTALL)
        assert m, "cls-composition(-rev) marker must be defined"
        assert 'fill="none"' not in m.group(1)


# ── Multiplicity slot tests ───────────────────────────────────────────────────

class TestMultiplicitySlots:
    """src_label and dst_label are threaded through for both ends."""

    def test_src_label_parsed(self):
        src, tgt, style = _class_rel_markers("<|--")
        _ = src  # source marker present
        m = _CLASS_REL_RE.match('A "1" <|-- "*" B')
        assert m, "regex must match multiplicity notation"
        assert m.group(2) == "1"    # mul_src
        assert m.group(4) == "*"    # mul_dst

    def test_dst_label_parsed(self):
        m = _CLASS_REL_RE.match('Pond "1" o-- "*" Duck')
        assert m
        assert m.group(2) == "1"
        assert m.group(4) == "*"

    def test_edge_src_label_set(self):
        from mermaid_render.layout._strategies import _CLASS_REL_RE, _class_rel_markers
        from mermaid_render.layout._constants import _Edge
        line = 'Pond "1" o-- "*" Duck : aggregates'
        m = _CLASS_REL_RE.match(line)
        assert m, "regex must match multiplicity notation"
        c1, mul_src, op, mul_dst, c2, lbl = (
            m.group(1), m.group(2) or "", m.group(3),
            m.group(4) or "", m.group(5), m.group(6) or "",
        )
        src_spec, tgt_spec, line_style = _class_rel_markers(op)
        edge = _Edge(src=c1, dst=c2, label=lbl.strip(),
                     style=line_style,
                     source_marker=src_spec, target_marker=tgt_spec,
                     src_label=mul_src, dst_label=mul_dst)
        assert edge.src_label == "1"
        assert edge.dst_label == "*"
        assert edge.src == "Pond"
        assert edge.dst == "Duck"


# ── Direction preservation ────────────────────────────────────────────────────

class TestDirectionPreservation:
    """Declared relation direction is preserved independently of rank direction."""

    def _edge_objects(self, snippet: str) -> list:
        """Get _Edge objects by parsing and running layout internally."""
        import re as _re
        from mermaid_render.layout._strategies import _CLASS_REL_RE, _class_rel_markers, _directive_content
        from mermaid_render.layout._constants import _Edge, _Node
        lines = (f"classDiagram\n{snippet}").splitlines()
        edges = []
        nodes: dict = {}
        for raw in lines:
            line = raw.strip()
            m = _CLASS_REL_RE.match(line)
            if m:
                c1, mul_src, op, mul_dst, c2, lbl = (
                    m.group(1), m.group(2) or "", m.group(3),
                    m.group(4) or "", m.group(5), m.group(6) or ""
                )
                src_spec, tgt_spec, line_style = _class_rel_markers(op)
                edges.append(_Edge(src=c1, dst=c2, label=lbl.strip(),
                                   style=line_style,
                                   source_marker=src_spec, target_marker=tgt_spec))
        return edges

    def test_inherit_src_is_subclass(self):
        """For A <|-- B, A is the declared source, B is the declared target."""
        edges = self._edge_objects("Animal <|-- Dog")
        assert len(edges) == 1
        e = edges[0]
        assert e.src == "Animal"
        assert e.dst == "Dog"
        assert e.source_marker.kind == MarkerKind.HOLLOW_TRIANGLE
        assert e.source_marker.end == "SOURCE"

    def test_realization_direction(self):
        """For A ..|> B, A is the source, B is the interface."""
        edges = self._edge_objects("Teacher ..|> Professor")
        assert len(edges) == 1
        e = edges[0]
        assert e.src == "Teacher"
        assert e.dst == "Professor"
        assert e.target_marker.kind == MarkerKind.HOLLOW_TRIANGLE
        assert e.target_marker.end == "TARGET"


# ── _compile_classdiagram unit tests ─────────────────────────────────────────

class TestCompileClassdiagram:
    """Unit tests for _compile_classdiagram() returning FinalizedLayout."""

    def _compile(self, src: str, **kwargs):
        from mermaid_render.layout._strategies import _compile_classdiagram
        return _compile_classdiagram(src, **kwargs)

    def test_returns_compiled_flowchart(self):
        from mermaid_render.layout._geometry import FinalizedLayout
        src = "classDiagram\n  class Animal\n  class Dog\n  Animal <|-- Dog"
        result = self._compile(src)
        assert hasattr(result, "layout")
        assert isinstance(result.layout, FinalizedLayout)

    def test_member_layouts_populated(self):
        src = (
            "classDiagram\n"
            "  class Animal {\n"
            "    +String name\n"
            "    +makeSound() void\n"
            "  }"
        )
        result = self._compile(src)
        nl = result.layout.node_layouts.get("Animal")
        assert nl is not None
        # attrs + "---" divider + methods = 3 rows
        assert len(nl.member_layouts) == 3

    def test_member_layouts_attrs_only(self):
        src = (
            "classDiagram\n"
            "  class Config {\n"
            "    +String host\n"
            "    +int port\n"
            "  }"
        )
        result = self._compile(src)
        nl = result.layout.node_layouts["Config"]
        # No methods → no divider
        assert len(nl.member_layouts) == 2
        texts = [tl.lines[0].runs[0].text for tl in nl.member_layouts if tl.lines and tl.lines[0].runs]
        assert any("host" in t for t in texts)

    def test_member_layouts_methods_only(self):
        src = (
            "classDiagram\n"
            "  class Service {\n"
            "    +connect()\n"
            "    +disconnect()\n"
            "  }"
        )
        result = self._compile(src)
        nl = result.layout.node_layouts["Service"]
        # No attrs → no divider
        assert len(nl.member_layouts) == 2

    def test_class_without_members_has_empty_member_layouts(self):
        src = "classDiagram\n  class Animal\n  class Dog\n  Animal <|-- Dog"
        result = self._compile(src)
        for nid in ("Animal", "Dog"):
            nl = result.layout.node_layouts[nid]
            assert nl.member_layouts == ()

    def test_canvas_bounds_positive(self):
        src = "classDiagram\n  class A\n  class B\n  A --> B"
        result = self._compile(src)
        cb = result.layout.canvas_bounds
        assert cb.w > 0 and cb.h > 0

    def test_routed_edges_present(self):
        src = "classDiagram\n  class A\n  class B\n  A --> B"
        result = self._compile(src)
        assert len(result.layout.routed_edges) == 1

    def test_empty_source_raises(self):
        import pytest
        with pytest.raises(ValueError, match="No classes"):
            self._compile("classDiagram\n")


    def test_compile_clearance_applied(self):
        """_compile_classdiagram: Animal->Dog source waypoint is 12px past Animal face."""
        from mermaid_render.layout._strategies import _compile_classdiagram
        src = "classDiagram\n  class Animal\n  class Dog\n  Animal <|-- Dog"
        result = _compile_classdiagram(src)
        fl = result.layout
        animal_nl = fl.node_layouts.get("Animal")
        assert animal_nl is not None, "Animal node not in layout"
        animal_bottom = animal_nl.outer_bounds.y + animal_nl.outer_bounds.h
        edge = next(
            (e for e in fl.routed_edges if e.src_node_id == "Animal" and e.dst_node_id == "Dog"),
            None,
        )
        assert edge is not None, "Animal->Dog edge not found in routed_edges"
        assert edge.waypoints, "Animal->Dog edge has no waypoints"
        src_y = edge.waypoints[0].y
        # HOLLOW_TRIANGLE source clearance=12: first waypoint must be >= 10px past
        # Animal's bottom face (into the path interior).
        assert src_y >= animal_bottom + 10, (
            f"clearance not applied: src waypoint y={src_y:.1f}, "
            f"animal bottom={animal_bottom:.1f}"
        )

    def test_end_to_end_to_html(self):
        from mermaid_render import to_html
        src = (
            "classDiagram\n"
            "  class Animal {\n"
            "    +String name\n"
            "    +makeSound() void\n"
            "  }\n"
            "  class Dog\n"
            "  Animal <|-- Dog"
        )
        html = to_html(src)
        assert "mermaid-layout finalized" in html
        assert "Animal" in html

    def test_end_to_end_to_svg(self):
        import os
        from unittest.mock import patch
        from mermaid_render import to_svg
        src = "classDiagram\n  class A\n  class B\n  A --> B"
        with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
            svg = to_svg(src, experimental=True)
        assert "<svg" in svg


# ── Marker clearance tests (T1) ───────────────────────────────────────────────

class TestMarkerClearance:
    """_class_rel_markers assigns the correct clearance constant per MarkerKind."""

    def _m(self, op: str):
        return _class_rel_markers(op)

    def test_hollow_triangle_src_clearance(self):
        src, _, _ = self._m("<|--")
        assert src.clearance == 12.0

    def test_hollow_triangle_src_dashed_clearance(self):
        src, _, _ = self._m("<|..")
        assert src.clearance == 12.0

    def test_filled_diamond_src_clearance(self):
        src, _, _ = self._m("*--")
        assert src.clearance == 12.0

    def test_hollow_diamond_src_clearance(self):
        src, _, _ = self._m("o--")
        assert src.clearance == 12.0

    def test_open_arrow_tgt_clearance(self):
        _, tgt, _ = self._m("-->")
        assert tgt.clearance == 9.0

    def test_open_arrow_dashed_tgt_clearance(self):
        _, tgt, _ = self._m("..>")
        assert tgt.clearance == 9.0

    def test_hollow_triangle_tgt_clearance(self):
        _, tgt, _ = self._m("..|>")
        assert tgt.clearance == 12.0

    def test_none_tgt_clearance_zero(self):
        _, tgt, _ = self._m("<|--")
        assert tgt.clearance == 0.0

    def test_none_src_clearance_zero(self):
        src, _, _ = self._m("-->")
        assert src.clearance == 0.0


# ── Route shortening tests (T2) ───────────────────────────────────────────────

class TestRouteShortening:
    """_shorten_cls_route computes correct shortened endpoints and orientation."""

    def _node(self, x: int, y: int, w: int = 80, h: int = 42):
        from mermaid_render.layout._constants import _Node
        return _Node(id="N", x=x, y=y, width=w)

    def _shorten(self, pts, src_cl, tgt_cl, src_node=None, dst_node=None):
        from mermaid_render.layout._routing import _shorten_cls_route
        sn = src_node or self._node(0, 0)
        dn = dst_node or self._node(0, 0)
        return _shorten_cls_route(pts, src_cl, tgt_cl, sn, dn)

    def test_tgt_shortening_vertical(self):
        """Vertical TB route shortened by 12 at target."""
        src_n = self._node(60, 8)   # bottom face at y=50 (8+42)
        dst_n = self._node(60, 150) # top face at y=150
        pts = [(100, 50), (100, 150)]
        result = self._shorten(pts, 0.0, 12.0, src_n, dst_n)
        assert result[-1] == (100, 138)

    def test_src_shortening_vertical(self):
        """Source-end shortening on a vertical route."""
        src_n = self._node(60, 8)
        dst_n = self._node(60, 150)
        pts = [(100, 50), (100, 150)]
        result = self._shorten(pts, 12.0, 0.0, src_n, dst_n)
        assert result[0] == (100, 62)

    def test_orientation_preserved(self):
        """sign(dy) of final segment unchanged after target shortening."""
        dst_n = self._node(0, 100)
        pts = [(0, 0), (0, 100)]
        result = self._shorten(pts, 0.0, 12.0, self._node(0, 0), dst_n)
        dy = result[-1][1] - result[-2][1]
        assert dy > 0  # sign(dy) = +1, same as original

    def test_orientation_fallback(self):
        """Fallback+clamp: non-collinear path endpoint moves to prev (not original endpoint)."""
        from mermaid_render.layout._routing import _shorten_cls_route
        # Non-collinear path: last segment (100,0)->(100,8) len=8 < cl=12 -> fallback.
        # Without clamp: fallback tangent (1,0) would produce (88,0) — past prev=(100,0).
        # With clamp: result[-1] = prev = (100,0).  If this fires incorrectly, result
        # would be either the original endpoint (100,8) or an unclamped (88,0).
        dst_n = self._node(90, 90)
        pts = [(0, 0), (100, 0), (100, 8)]
        result = _shorten_cls_route(pts, 0.0, 12.0, self._node(0, 0), dst_n)
        assert result[-1] == (100, 0), (
            f"expected fallback to clamp result[-1] to prev=(100,0), got {result[-1]}"
        )
        # Verify the endpoint actually changed (shortening ran).
        assert result[-1] != (100, 8), "endpoint unchanged — shortening did not run"

    def test_card_clip_no_interior_point(self):
        """After shortening, no waypoint falls strictly inside either card Rect."""
        src_n = self._node(90, 8)   # x=90..170, y=8..50
        dst_n = self._node(90, 150) # x=90..170, y=150..192
        pts = [(100, 50), (100, 150)]
        result = self._shorten(pts, 12.0, 12.0, src_n, dst_n)
        for nx, ny, nw, nh in [
            (src_n.x, src_n.y, 80, 42),
            (dst_n.x, dst_n.y, 80, 42),
        ]:
            for wx, wy in result:
                inside = nx < wx < nx + nw and ny < wy < ny + nh
                assert not inside, f"waypoint ({wx},{wy}) is inside card ({nx},{ny},{nw},{nh})"

    def test_src_end_clearance_multi_rank(self):
        """Source-end shortening shifts pts[0] by clearance toward the path interior."""
        from mermaid_render.layout._routing import _shorten_cls_route
        src_n = self._node(90, 8)
        dst_n = self._node(90, 200)
        pts = [(100, 50), (100, 130), (100, 242)]
        result = _shorten_cls_route(pts, 12.0, 0.0, src_n, dst_n)
        # pts[0] should move 12px downward (toward pts[1])
        assert result[0] == (100, 62)

    def test_goal_based_clearance_in_rendered_html(self):
        """Source waypoint in FinalizedLayout IR is >= 12px past Animal card bottom face."""
        from mermaid_render.layout._strategies import _compile_classdiagram
        result = _compile_classdiagram(
            "classDiagram\n  class Animal\n  class Dog\n  Animal <|-- Dog"
        )
        fl = result.layout
        animal_nl = fl.node_layouts.get("Animal")
        assert animal_nl is not None, "Animal node not in layout"
        animal_bottom = animal_nl.outer_bounds.y + animal_nl.outer_bounds.h
        edge = next(
            (e for e in fl.routed_edges
             if e.src_node_id == "Animal" and e.dst_node_id == "Dog"),
            None,
        )
        assert edge is not None, "Animal->Dog edge not found in routed_edges"
        assert edge.waypoints, "Animal->Dog edge has no waypoints"
        src_y = edge.waypoints[0].y
        # HOLLOW_TRIANGLE source clearance=12; first waypoint must be >= 10px past
        # Animal's bottom face (into the path interior).
        assert src_y >= animal_bottom + 10, (
            f"source waypoint y={src_y:.1f} too close to Animal bottom y={animal_bottom:.1f}; "
            f"expected >= {animal_bottom + 10:.1f} (clearance=12)"
        )


# ── Label placement tests (T3) ────────────────────────────────────────────────

class TestLabelPlacement:
    """Class-edge label placement respects the 40px floor and shelf fallback."""

    def _span(self, pts):
        from mermaid_render.layout._routing import _cls_eligible_span
        return _cls_eligible_span(pts)

    def test_collinear_span_60(self):
        """Straight vertical 60px path → eligible span = 60."""
        pts = [(0, 0), (0, 60)]
        assert self._span(pts) == 60.0

    def test_collinear_span_20(self):
        """Straight vertical 20px path → eligible span = 20."""
        pts = [(0, 0), (0, 20)]
        assert self._span(pts) == 20.0

    def test_multiseg_longest_segment(self):
        """Multi-segment path → eligible span = max individual segment."""
        pts = [(0, 0), (50, 0), (50, 30)]  # segments: 50px, 30px
        assert self._span(pts) == 50.0

    def test_full_fixture_labels_pairwise_disjoint(self):
        """All label chips from class-relationships-all.mmd are pairwise disjoint."""
        import re as _re
        from mermaid_render.layout._strategies import _layout_class
        from mermaid_render.layout._routing import _est_label_w
        src = (
            "classDiagram\n"
            "    class Animal\n    class Dog\n    class Cat\n"
            "    class Engine\n    class Car\n    class Pond\n    class Duck\n"
            "    class Person\n    class Address\n"
            "    class IFlyable\n    class Bird\n"
            "    class Teacher\n    class Professor\n"
            "    Animal <|-- Dog : inherits\n"
            "    Animal <|-- Cat : inherits\n"
            "    Car *-- Engine : composed of\n"
            "    Pond o-- Duck : aggregates\n"
            "    Person --> Address : has\n"
            "    IFlyable ..> Bird : dependency\n"
            "    Teacher ..|> Professor : realization\n"
        )
        html = _layout_class(src, "TB", 800)
        # Extract chip positions from edge-label spans (no explicit width in style)
        chips = []
        for m in _re.finditer(
            r'data-edge-label="([^"]*)"[^>]*style="[^"]*left:\s*([\d.]+)px[^"]*top:\s*([\d.]+)px',
            html,
        ):
            text, lx, ty = m.group(1), float(m.group(2)), float(m.group(3))
            w = _est_label_w(text)
            chips.append((lx, ty, lx + w, ty + 17))  # 17px chip height
        # Need at least one label chip to validate (diagram renders all 7 labels)
        assert chips, "no edge label chips found in rendered HTML"
        # Pairwise disjoint check
        _MARGIN = 2  # allow 2px tolerance for rounding
        for i, a in enumerate(chips):
            for j, b in enumerate(chips):
                if i >= j:
                    continue
                overlap_x = max(0.0, min(a[2], b[2]) - max(a[0], b[0]) - _MARGIN)
                overlap_y = max(0.0, min(a[3], b[3]) - max(a[1], b[1]) - _MARGIN)
                assert overlap_x * overlap_y == 0.0, (
                    f"chips {i} and {j} overlap: {a} vs {b}"
                )

    def test_shelf_determinism(self):
        """Shelf label position is stable across repeated renders of a short edge."""
        from mermaid_render.layout._strategies import _layout_class
        src = "classDiagram\nAnimal <|-- Dog : inherits\n"
        html1 = _layout_class(src, "TB", 600)
        html2 = _layout_class(src, "TB", 600)
        assert html1 == html2, "render not deterministic"

    def test_shelf_fallback_on_short_span(self):
        """When eligible span < 40px after shortening, shelf label fires at a deterministic position."""
        from mermaid_render.layout._constants import _Node, _Edge
        from mermaid_render.layout._routing import _route_edges, _cls_eligible_span
        from mermaid_render.layout._strategies import _class_rel_markers
        # src card bottom=90, dst card top=130 → gap=40px, after clearance=12 → span=28px < 40.
        src_n = _Node(id="A", x=46, y=48, width=80)   # bottom = 48+42 = 90
        dst_n = _Node(id="B", x=46, y=130, width=80)  # top = 130
        src_spec, tgt_spec, line_style = _class_rel_markers("<|--")
        edge = _Edge(src="A", dst="B", label="shelf", style=line_style,
                     source_marker=src_spec, target_marker=tgt_spec)
        nodes = {"A": src_n, "B": dst_n}
        # Verify shelf fires (span < 40 in actual route).
        r1 = _route_edges(nodes, [edge], 400, "TB")
        r2 = _route_edges(nodes, [edge], 400, "TB")
        assert r1.routed and r2.routed, "no routed edges"
        pts1 = r1.routed[0]["waypoints"]
        span = _cls_eligible_span(pts1)
        assert span < 40, f"shelf branch not triggered: span={span} >= 40"
        # Shelf label positions must be deterministic across repeated renders.
        lx1, ly1 = r1.routed[0]["lx"], r1.routed[0]["ly"]
        lx2, ly2 = r2.routed[0]["lx"], r2.routed[0]["ly"]
        assert (lx1, ly1) == (lx2, ly2), f"shelf positions differ: {(lx1, ly1)} vs {(lx2, ly2)}"
        # Shelf must not be at origin (degenerate fallback check).
        assert lx1 != 0 or ly1 != 0, "shelf landed at canvas origin"
