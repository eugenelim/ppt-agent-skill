#!/usr/bin/env python3
"""Requirement diagram syntax coverage tests for the mermaid_render layout engine.

requirementDiagram is not supported by the pure-Python renderer. Every test
in this file asserts that to_html raises ValueError for valid requirementDiagram
source, documenting both supported syntax forms and the graceful-failure contract.

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
# TestRequirementUnsupported
# ---------------------------------------------------------------------------

class TestRequirementUnsupported:
    def test_basic_requirement_raises(self):
        """A minimal requirement block raises ValueError."""
        with pytest.raises(ValueError):
            to_html(_BASIC_REQUIREMENT)

    def test_functional_requirement_raises(self):
        """A functionalRequirement block raises ValueError."""
        with pytest.raises(ValueError):
            to_html(_FUNCTIONAL_REQUIREMENT)

    def test_performance_requirement_raises(self):
        """A performanceRequirement block raises ValueError."""
        with pytest.raises(ValueError):
            to_html(_PERFORMANCE_REQUIREMENT)

    def test_element_with_rel_raises(self):
        """A diagram with an element and a satisfies relationship raises ValueError."""
        with pytest.raises(ValueError):
            to_html(_ELEMENT_WITH_RELATIONSHIP)

    @pytest.mark.parametrize("req_type", [
        "requirement",
        "functionalRequirement",
        "interfaceRequirement",
        "performanceRequirement",
        "physicalRequirement",
        "designConstraint",
    ])
    def test_all_requirement_types_raise(self, req_type: str):
        """Every documented requirement type raises ValueError."""
        src = (
            f"requirementDiagram\n\n"
            f"{req_type} req_{req_type.lower()} {{\n"
            f"  id: 1\n"
            f"  text: The system shall satisfy this requirement.\n"
            f"  risk: Medium\n"
            f"  verifymethod: Test\n"
            f"}}\n"
        )
        with pytest.raises(ValueError):
            to_html(src)

    @pytest.mark.parametrize("rel_type", [
        "contains",
        "copies",
        "derives",
        "satisfies",
        "verifies",
        "refines",
        "traces",
    ])
    def test_all_relationship_types_raise(self, rel_type: str):
        """Every documented relationship type raises ValueError when the diagram is rendered."""
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
        with pytest.raises(ValueError):
            to_html(src)

    def test_error_is_value_error(self):
        """The exception type is exactly ValueError — not a subclass."""
        exc = None
        try:
            to_html(_FULL_DIAGRAM)
        except ValueError as e:
            exc = e
        assert exc is not None, "Expected ValueError but no exception was raised"
        assert type(exc) is ValueError, (
            f"Expected ValueError exactly, got {type(exc).__name__}"
        )

    def test_error_message_names_directive(self):
        """The ValueError message contains the directive string (lowercased by _detect_directive)."""
        with pytest.raises(ValueError, match="requirementdiagram"):
            to_html(_BASIC_REQUIREMENT)

    def test_error_message_not_supported(self):
        """The ValueError message states the type is not supported."""
        with pytest.raises(ValueError, match="not supported"):
            to_html(_BASIC_REQUIREMENT)
