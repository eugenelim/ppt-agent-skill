#!/usr/bin/env python3
"""Requirement diagram syntax coverage tests for the mermaid_render layout engine.

requirementDiagram now has a basic renderer in the pure-Python engine.  These
tests document supported syntax forms and verify they produce HTML output.

Requirement types:   requirement, functionalRequirement, interfaceRequirement,
                     performanceRequirement, physicalRequirement, designConstraint
Risk levels:         High, Medium, Low
Verify methods:      Analysis, Inspection, Test, Demonstration
Relationship types:  contains, copies, derives, satisfies, verifies, refines, traces

Import note: ``to_html`` lives in ``mermaid_render``, not ``mermaid_layout``
(the latter is a shim to ``mermaid_render.layout`` which does not re-export
``to_html``).  We import directly from ``mermaid_render``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_BASIC_REQUIREMENT = """\
requirementDiagram

requirement test_req {
  id: 1
  text: The system shall do something.
  risk: High
  verifymethod: Test
}
"""

_FUNCTIONAL_REQUIREMENT = """\
requirementDiagram

functionalRequirement sys_req {
  id: 2
  text: The system shall provide functionality.
  risk: Medium
  verifymethod: Demonstration
}
"""

_PERFORMANCE_REQUIREMENT = """\
requirementDiagram

performanceRequirement perf_req {
  id: 3
  text: The system shall respond in < 1s.
  risk: Low
  verifymethod: Analysis
}
"""

_ELEMENT_WITH_RELATIONSHIP = """\
requirementDiagram

requirement test_req {
  id: 1
  text: The system shall do something.
  risk: High
  verifymethod: Test
}

element test_entity {
  type: simulation
  docref: /refs/doc.docx
}

test_entity - satisfies -> test_req
"""

_FULL_DIAGRAM = """\
requirementDiagram

requirement test_req {
  id: 1
  text: The system shall do something.
  risk: High
  verifymethod: Test
}

functionalRequirement sys_req {
  id: 2
  text: The system shall provide functionality.
  risk: Medium
  verifymethod: Demonstration
}

performanceRequirement perf_req {
  id: 3
  text: The system shall respond in < 1s.
  risk: Low
  verifymethod: Analysis
}

element test_entity {
  type: simulation
  docref: /refs/doc.docx
}

test_entity - satisfies -> test_req
test_entity - verifies -> perf_req
sys_req - derives -> test_req
sys_req - refines -> test_req
"""


# ---------------------------------------------------------------------------
# TestRequirementRendered
# ---------------------------------------------------------------------------

class TestRequirementRendered:
    def test_basic_requirement_renders(self):
        """A minimal requirement block renders HTML."""
        html = to_html(_BASIC_REQUIREMENT)
        assert html
        assert "test_req" in html

    def test_functional_requirement_renders(self):
        """A functionalRequirement block renders HTML."""
        html = to_html(_FUNCTIONAL_REQUIREMENT)
        assert "sys_req" in html

    def test_performance_requirement_renders(self):
        """A performanceRequirement block renders HTML."""
        html = to_html(_PERFORMANCE_REQUIREMENT)
        assert "perf_req" in html

    def test_element_with_rel_renders(self):
        """A diagram with an element and a satisfies relationship renders HTML."""
        html = to_html(_ELEMENT_WITH_RELATIONSHIP)
        assert "test_entity" in html
        assert "test_req" in html

    def test_satisfies_relation_label_present(self):
        """The 'satisfies' relation label appears in the rendered output."""
        html = to_html(_ELEMENT_WITH_RELATIONSHIP)
        assert "satisfies" in html

    @pytest.mark.parametrize("req_type", [
        "requirement",
        "functionalRequirement",
        "interfaceRequirement",
        "performanceRequirement",
        "physicalRequirement",
        "designConstraint",
    ])
    def test_all_requirement_types_render(self, req_type: str):
        """Every documented requirement type renders HTML."""
        nid = f"req_{req_type.lower()}"
        src = (
            f"requirementDiagram\n\n"
            f"{req_type} {nid} {{\n"
            f"  id: 1\n"
            f"  text: The system shall satisfy this requirement.\n"
            f"  risk: Medium\n"
            f"  verifymethod: Test\n"
            f"}}\n"
        )
        html = to_html(src)
        assert html
        assert nid in html

    @pytest.mark.parametrize("rel_type", [
        "contains",
        "copies",
        "satisfies",
        "verifies",
        "refines",
        "traces",
    ])
    def test_all_relationship_types_render(self, rel_type: str):
        """Every documented relationship type renders in the diagram."""
        src = (
            "requirementDiagram\n\n"
            "requirement req_a {\n"
            "  id: 1\n"
            "  text: Requirement A.\n"
            "  risk: Low\n"
            "  verifymethod: Inspection\n"
            "}\n\n"
            "requirement req_b {\n"
            "  id: 2\n"
            "  text: Requirement B.\n"
            "  risk: Low\n"
            "  verifymethod: Analysis\n"
            "}\n\n"
            f"req_a - {rel_type} -> req_b\n"
        )
        html = to_html(src)
        assert html
        assert "req_a" in html
        assert "req_b" in html

    def test_full_diagram_renders(self):
        """Complex diagram with multiple req types and relations renders."""
        html = to_html(_FULL_DIAGRAM)
        assert html
        assert "test_req" in html
        assert "test_entity" in html


# ---------------------------------------------------------------------------
# TestNativeSceneGeometry — native SVG path (layout_requirement_scene)
# ---------------------------------------------------------------------------

class TestNativeSceneGeometry:
    """Geometry invariants for the native SVG scene builder."""

    def _load_fixture(self):
        from pathlib import Path
        return (Path(__file__).parent / "fixtures" / "requirement-basic.mmd").read_text()

    def test_fixture_has_four_nodes(self):
        """requirement-basic scene contains exactly four card nodes."""
        from mermaid_render.layout.requirement import layout_requirement_scene
        from mermaid_render.scene import SceneRect

        scene = layout_requirement_scene(self._load_fixture())
        node_ids = []
        for _, elements in scene.layers:
            for elem in elements:
                if isinstance(elem, SceneRect):
                    for name, val in getattr(elem, "data_attrs", ()):
                        if name == "node-id":
                            node_ids.append(val)
        assert set(node_ids) == {"test_req", "func_req", "perf_req", "test_entity"}

    def test_fixture_has_three_labeled_relations(self):
        """requirement-basic scene contains three edge polylines with relation labels."""
        from mermaid_render.layout.requirement import layout_requirement_scene
        from mermaid_render.scene import ScenePolyline, SceneText

        scene = layout_requirement_scene(self._load_fixture())
        edges, labels = [], []
        for _, elements in scene.layers:
            for elem in elements:
                if isinstance(elem, ScenePolyline):
                    edges.append(elem)
                if isinstance(elem, SceneText):
                    for line in elem.lines:
                        if line.text in {"satisfies", "verifies", "derives"}:
                            labels.append(line.text)
        assert len(edges) == 3
        assert set(labels) == {"satisfies", "verifies", "derives"}

    def test_no_edge_segment_passes_through_card(self):
        """No edge polyline segment interior crosses any card bounding box."""
        from mermaid_render.layout.requirement import layout_requirement_scene
        from mermaid_render.scene import ScenePolyline, SceneRect

        scene = layout_requirement_scene(self._load_fixture())

        card_boxes = []
        for _, elements in scene.layers:
            for elem in elements:
                if isinstance(elem, SceneRect):
                    for name, _ in getattr(elem, "data_attrs", ()):
                        if name == "node-id":
                            card_boxes.append(
                                (elem.x, elem.y, elem.x + elem.w, elem.y + elem.h)
                            )

        for _, elements in scene.layers:
            for elem in elements:
                if not isinstance(elem, ScenePolyline):
                    continue
                attrs = dict(getattr(elem, "data_attrs", ()))
                src_id = attrs.get("src", "?")
                dst_id = attrs.get("dst", "?")
                for i in range(len(elem.points) - 1):
                    x1, y1 = elem.points[i]
                    x2, y2 = elem.points[i + 1]
                    for rx0, ry0, rx1, ry1 in card_boxes:
                        for t in (0.25, 0.5, 0.75):
                            px = x1 + t * (x2 - x1)
                            py = y1 + t * (y2 - y1)
                            inside = rx0 + 1 < px < rx1 - 1 and ry0 + 1 < py < ry1 - 1
                            assert not inside, (
                                f"Edge {src_id}→{dst_id} segment interior "
                                f"({px:.1f}, {py:.1f}) is inside card "
                                f"[{rx0:.0f},{ry0:.0f},{rx1:.0f},{ry1:.0f}]"
                            )

    def test_unquoted_path_docref_raises_valueerror(self):
        """Native parser raises ValueError for unquoted docref containing path chars."""
        from mermaid_render.layout.requirement import _parse_requirement_source

        bad_src = (
            "requirementDiagram\n"
            "element ent {\n"
            "  type: simulation\n"
            "  docref: /bad/path\n"
            "}\n"
        )
        with pytest.raises(ValueError, match="must be quoted"):
            _parse_requirement_source(bad_src)

    def test_invalid_relation_type_not_parsed(self):
        """Unknown relation types are silently skipped (not emitted as edges)."""
        from mermaid_render.layout.requirement import layout_requirement_scene
        from mermaid_render.scene import ScenePolyline

        src = (
            "requirementDiagram\n"
            "requirement req_a {\n  id: 1\n  text: A.\n  risk: Low\n  verifymethod: Test\n}\n"
            "requirement req_b {\n  id: 2\n  text: B.\n  risk: Low\n  verifymethod: Test\n}\n"
            "req_a - foobar -> req_b\n"
        )
        scene = layout_requirement_scene(src)
        edges = [
            e for _, elems in scene.layers for e in elems
            if isinstance(e, ScenePolyline)
        ]
        assert len(edges) == 0, "Unknown relation type must not produce an edge"
