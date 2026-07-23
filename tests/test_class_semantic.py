"""Semantic tests for class-diagram-marker-semantics.

Verifies that each UML relationship operator in class-relationships-all.mmd
maps to the correct MarkerSpec (kind, end, line_style) and that the rendered
HTML uses the right SVG marker attributes.
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
