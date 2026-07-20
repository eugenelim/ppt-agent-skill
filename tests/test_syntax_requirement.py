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
