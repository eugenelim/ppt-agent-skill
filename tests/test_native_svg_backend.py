"""Tests for the native SVG dispatch backend (native_svg.py + __init__.py integration)."""
from __future__ import annotations

import os
import re

import pytest

from scripts.mermaid_render import to_svg
from scripts.mermaid_render.native_svg import (
    dispatch_native,
    NativeRenderError,
    _use_native,
    BACKEND_ENV,
    BACKEND_NATIVE,
    BACKEND_LEGACY,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

FLOWCHART_SIMPLE = """\
flowchart TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Do it]
    B -->|No| D[Skip]
    C --> E[End]
    D --> E
"""

FLOWCHART_LR = """\
flowchart LR
    X[Input] --> Y[Process] --> Z[Output]
"""

FLOWCHART_WITH_GROUPS = """\
flowchart TD
    subgraph P[Phase 1]
        A --> B
    end
    B --> C
"""

STATE_DIAGRAM = """\
stateDiagram-v2
    [*] --> Idle
    Idle --> Running : start
    Running --> Idle : stop
    Running --> [*]
"""

SEQUENCE_DIAGRAM = """\
sequenceDiagram
    Alice->>Bob: Hello
    Bob-->>Alice: Hi
"""


# ── Backend flag ──────────────────────────────────────────────────────────────

class TestBackendFlag:
    def test_default_is_native(self, monkeypatch):
        monkeypatch.delenv(BACKEND_ENV, raising=False)
        assert _use_native() is True

    def test_legacy_env_disables_native(self, monkeypatch):
        monkeypatch.setenv(BACKEND_ENV, BACKEND_LEGACY)
        assert _use_native() is False

    def test_explicit_native_is_native(self, monkeypatch):
        monkeypatch.setenv(BACKEND_ENV, BACKEND_NATIVE)
        assert _use_native() is True

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv(BACKEND_ENV, "Legacy-DOM")
        assert _use_native() is False


# ── dispatch_native core contract ─────────────────────────────────────────────

class TestDispatchNativeContract:
    def test_returns_string(self):
        result = dispatch_native(FLOWCHART_SIMPLE)
        assert isinstance(result, str)

    def test_produces_svg_element(self):
        svg = dispatch_native(FLOWCHART_SIMPLE)
        assert "<svg" in svg

    def test_no_foreign_object(self):
        svg = dispatch_native(FLOWCHART_SIMPLE)
        assert "<foreignObject" not in svg

    def test_no_playwright_import(self):
        # to_svg via native path must not import playwright
        import sys
        before = set(sys.modules.keys())
        dispatch_native(FLOWCHART_SIMPLE)
        after = set(sys.modules.keys())
        new_imports = after - before
        playwright_imports = [m for m in new_imports if "playwright" in m]
        assert playwright_imports == [], f"Playwright imported: {playwright_imports}"

    def test_deterministic_output(self):
        svg1 = dispatch_native(FLOWCHART_SIMPLE)
        svg2 = dispatch_native(FLOWCHART_SIMPLE)
        assert svg1 == svg2

    def test_has_viewbox(self):
        svg = dispatch_native(FLOWCHART_SIMPLE)
        assert "viewBox=" in svg

    def test_has_width_height(self):
        svg = dispatch_native(FLOWCHART_SIMPLE)
        assert re.search(r'width="[\d.]+', svg)
        assert re.search(r'height="[\d.]+', svg)

    def test_contains_node_text(self):
        svg = dispatch_native(FLOWCHART_SIMPLE)
        assert "Start" in svg

    def test_lr_direction(self):
        svg = dispatch_native(FLOWCHART_LR)
        assert "<svg" in svg
        assert "Input" in svg
        assert "Output" in svg

    def test_subgraph_groups(self):
        svg = dispatch_native(FLOWCHART_WITH_GROUPS)
        assert "<svg" in svg

    def test_accessibility_title(self):
        svg = dispatch_native(FLOWCHART_SIMPLE)
        assert "<title>" in svg or "aria-label=" in svg

    def test_diagram_type_attribute(self):
        svg = dispatch_native(FLOWCHART_SIMPLE)
        assert 'data-diagram-type="flowchart"' in svg

    def test_no_nan_in_output(self):
        svg = dispatch_native(FLOWCHART_SIMPLE)
        assert "NaN" not in svg
        assert "Infinity" not in svg

    def test_valid_xml(self):
        from lxml import etree
        svg = dispatch_native(FLOWCHART_SIMPLE)
        # Strip XML declaration for lxml parse
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        try:
            etree.fromstring(body.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            pytest.fail(f"Native SVG is not valid XML: {e}")


# ── State diagram ─────────────────────────────────────────────────────────────

class TestStateDiagram:
    def test_produces_svg(self):
        svg = dispatch_native(STATE_DIAGRAM)
        assert "<svg" in svg

    def test_no_foreign_object(self):
        svg = dispatch_native(STATE_DIAGRAM)
        assert "<foreignObject" not in svg

    def test_contains_state_text(self):
        svg = dispatch_native(STATE_DIAGRAM)
        assert "Idle" in svg or "Running" in svg


# ── NOT_IMPLEMENTED types (stubs removed in P3) ───────────────────────────────

class TestNotImplementedTypes:
    """NOT_IMPLEMENTED types must raise NativeRenderError, not return placeholder SVG."""

    @pytest.mark.parametrize("src, dtype", [
        (SEQUENCE_DIAGRAM, "sequencediagram"),
        ("erDiagram\n    CUSTOMER ||--o{ ORDER : places\n", "erdiagram"),
        ("gantt\n    title MyProject\n    section A\n    Task1 :t1, 2024-01-01, 7d\n", "gantt"),
        ("pie\n    title Colors\n    \"Red\" : 30\n    \"Blue\" : 70\n", "pie"),
    ])
    def test_not_implemented_raises(self, src, dtype):
        with pytest.raises(NativeRenderError) as exc_info:
            dispatch_native(src)
        assert exc_info.value.phase == "not-implemented"
        assert dtype in exc_info.value.diagram_type


# ── to_svg() public API integration ──────────────────────────────────────────

class TestToSvgIntegration:
    def test_to_svg_uses_native_by_default(self, monkeypatch):
        monkeypatch.delenv(BACKEND_ENV, raising=False)
        svg = to_svg(FLOWCHART_SIMPLE)
        assert "<svg" in svg
        assert "<foreignObject" not in svg

    def test_to_svg_returns_string(self):
        result = to_svg(FLOWCHART_SIMPLE)
        assert isinstance(result, str)

    def test_to_svg_width_hint(self):
        svg = to_svg(FLOWCHART_SIMPLE, width_hint=800)
        assert "<svg" in svg

    def test_to_svg_deterministic(self):
        svg1 = to_svg(FLOWCHART_SIMPLE)
        svg2 = to_svg(FLOWCHART_SIMPLE)
        assert svg1 == svg2

    def test_to_svg_different_diagrams_differ(self):
        svg1 = to_svg(FLOWCHART_SIMPLE)
        svg2 = to_svg(FLOWCHART_LR)
        assert svg1 != svg2


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_unsupported_sankey_raises(self):
        src = "sankey-beta\nA,B,10"
        with pytest.raises((NativeRenderError, ValueError)):
            dispatch_native(src)

    def test_empty_graph_raises(self):
        with pytest.raises(ValueError):
            dispatch_native("flowchart TD\n")
