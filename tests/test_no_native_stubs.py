"""Static assertions that _html_fallback_scene and native-svg-stub are gone from production.

All checks operate on source text or the live import graph — no rendering needed.
"""
import importlib
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

import pytest

_NATIVE_SVG = pathlib.Path(__file__).parents[1] / "scripts" / "mermaid_render" / "native_svg.py"
_NATIVE_SVG_SRC = _NATIVE_SVG.read_text()

_MERMAID_RENDER_DIR = pathlib.Path(__file__).parents[1] / "scripts" / "mermaid_render"


# ── Static source-text assertions ─────────────────────────────────────────────

def test_no_html_fallback_scene_in_native_svg():
    assert "_html_fallback_scene" not in _NATIVE_SVG_SRC, (
        "_html_fallback_scene must not appear in native_svg.py"
    )


def test_no_native_svg_stub_backend_in_native_svg():
    assert "native-svg-stub" not in _NATIVE_SVG_SRC, (
        "renderer_backend='native-svg-stub' must not appear in native_svg.py"
    )


def test_no_mechanical_stub_in_native_svg():
    assert "mechanical stub" not in _NATIVE_SVG_SRC, (
        "'mechanical stub' accessibility description must not appear in native_svg.py"
    )


def test_no_broad_except_exception_in_native_svg():
    """No bare `except Exception:` or `except Exception as` in native builder wrappers."""
    import ast
    tree = ast.parse(_NATIVE_SVG_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is not None:
                handler_type = ast.unparse(node.type) if hasattr(ast, "unparse") else ""
                assert handler_type != "Exception", (
                    f"Native builder contains broad `except Exception:` at line {node.lineno}. "
                    "Let exceptions propagate to the outer error context."
                )


def test_no_html_fallback_scene_anywhere_in_package():
    """_html_fallback_scene must not appear anywhere in the mermaid_render package."""
    py_files = list(_MERMAID_RENDER_DIR.rglob("*.py"))
    found = [
        str(f) for f in py_files
        if "_html_fallback_scene" in f.read_text()
    ]
    assert not found, f"_html_fallback_scene found in: {found}"


def test_no_native_svg_stub_anywhere_in_package():
    """native-svg-stub renderer_backend must not appear in mermaid_render package."""
    py_files = list(_MERMAID_RENDER_DIR.rglob("*.py"))
    found = [
        str(f) for f in py_files
        if "native-svg-stub" in f.read_text()
    ]
    assert not found, f"native-svg-stub found in: {found}"


# ── Exception propagation tests ───────────────────────────────────────────────

def test_timeline_exception_propagates():
    """Exception in timeline builder must propagate, not be swallowed."""
    from scripts.mermaid_render.native_svg import NativeRenderError
    with patch("scripts.mermaid_render.layout.timeline.layout_timeline_scene",
               side_effect=RuntimeError("timeline layout failed")):
        with pytest.raises((RuntimeError, NativeRenderError, ValueError)):
            from scripts.mermaid_render import to_svg
            to_svg("timeline\n  title My Timeline\n  section A\n    Task : 2024-01-01, 2024-01-07")


def test_mindmap_exception_propagates():
    """Exception in mindmap builder must propagate."""
    from scripts.mermaid_render.native_svg import NativeRenderError
    with patch("scripts.mermaid_render.layout.mindmap.layout_mindmap_scene",
               side_effect=RuntimeError("mindmap layout failed")):
        with pytest.raises((RuntimeError, NativeRenderError, ValueError)):
            from scripts.mermaid_render import to_svg
            to_svg("mindmap\n  root((Root))\n    A\n    B")


def test_architecture_exception_propagates():
    """Exception in architecture builder must propagate."""
    from scripts.mermaid_render.native_svg import NativeRenderError
    with patch("scripts.mermaid_render.layout.architecture.layout_architecture_scene",
               side_effect=RuntimeError("arch layout failed")):
        with pytest.raises((RuntimeError, NativeRenderError, ValueError)):
            from scripts.mermaid_render import to_svg
            to_svg("architecture-beta\n  service A(server)[Server]")


# ── Not-implemented directive raises, not placeholder ─────────────────────────

@pytest.mark.parametrize("src", [
    "sequenceDiagram\nA->>B: hello",
    "erDiagram\n  PERSON { string name }",
    "gantt\n  title G\n  section A\n    Task : 2024-01-01, 2d",
    "quadrantChart\n  x-axis Low --> High\n  y-axis Low --> High",
    "pie\n  title Pets\n  \"Dogs\" : 386",
    "xychart-beta\n  x-axis [a, b, c]\n  y-axis 0 --> 10\n  bar [5, 3, 8]",
    "block-beta\n  A B C",
    "packet-beta\n  0-7: Source Port",
    "kanban\n  column1\n    item1[Task 1]",
    "journey\n  title My working day\n  section Go to work",
    "requirementDiagram\n  requirement req1 { id: 1 }",
    "gitGraph\n  commit",
])
def test_not_implemented_directive_raises_native_render_error(src):
    """NOT_IMPLEMENTED diagram types must raise NativeRenderError, not return SVG."""
    import os
    from scripts.mermaid_render import to_svg
    from scripts.mermaid_render.native_svg import NativeRenderError

    env = {"MERMAID_RENDER_SVG_BACKEND": "native"}
    with patch.dict(os.environ, env):
        with pytest.raises((NativeRenderError, ValueError)):
            to_svg(src)


# ── Unknown directive raises explicitly ───────────────────────────────────────

def test_unknown_directive_raises():
    """Unknown directives must fail explicitly, not use a fallback renderer."""
    import os
    from scripts.mermaid_render import to_svg
    from scripts.mermaid_render.native_svg import NativeRenderError

    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        with pytest.raises((NativeRenderError, ValueError)):
            to_svg("unknownDiagramType\n  some content")


# ── Playwright isolation test ─────────────────────────────────────────────────

def test_to_svg_does_not_import_playwright():
    """to_svg() must never import playwright for supported PARTIAL directives."""
    from scripts.mermaid_render import to_svg
    import os

    supported_sources = [
        "flowchart LR\n  A-->B",
        "graph TD\n  A-->B",
    ]
    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        for src in supported_sources:
            # Block playwright import — if to_svg imports it, this raises
            import sys
            playwright_mock = types.ModuleType("playwright")
            playwright_mock.sync_api = None
            old = sys.modules.get("playwright")
            sys.modules["playwright"] = None  # type: ignore[assignment]
            try:
                result = to_svg(src)
                assert result.startswith("<?xml") or "<svg" in result
            finally:
                if old is None:
                    sys.modules.pop("playwright", None)
                else:
                    sys.modules["playwright"] = old
