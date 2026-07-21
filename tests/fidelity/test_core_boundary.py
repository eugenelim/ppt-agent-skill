"""Boundary tests: tools/mermaid_fidelity/ must be extractable as a standalone package.

Rules:
  - No repo-specific imports at module import time (no mermaid_render, no tests.*)
  - No sys.path mutation at module level
  - No absolute paths baked in
  - All public API symbols are importable without scripts/ on sys.path
"""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_CORE = _REPO / "tools" / "mermaid_fidelity"


def _core_py_files() -> list[Path]:
    return [
        p for p in _CORE.rglob("*.py")
        if "__pycache__" not in p.parts
    ]


CORE_MODULES = [
    "mermaid_fidelity",
    "mermaid_fidelity.models",
    "mermaid_fidelity.serialization",
    "mermaid_fidelity.canonical",
    "mermaid_fidelity.manifest",
    "mermaid_fidelity.adapters",
    "mermaid_fidelity.compare.semantic",
    "mermaid_fidelity.compare.geometry",
    "mermaid_fidelity.compare.quality",
    "mermaid_fidelity.runner",
    "mermaid_fidelity.report",
    "mermaid_fidelity.projection",
    "mermaid_fidelity.cli",
]

# Imports that must NOT appear in core module source
_BANNED_IMPORTS = {
    "mermaid_render",
    "mermaid_layout",
    "scripts",
}


@pytest.fixture(scope="module", autouse=True)
def ensure_tools_on_path():
    tools_dir = str(_REPO / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_core_module_importable(module_name: str):
    """Each core module must import without scripts/ on sys.path."""
    scripts_dir = str(_REPO / "scripts")
    original_path = sys.path.copy()
    # Remove scripts/ if present
    sys.path = [p for p in sys.path if p != scripts_dir]
    try:
        if module_name in sys.modules:
            mod = sys.modules[module_name]
            assert mod is not None
        else:
            mod = importlib.import_module(module_name)
            assert mod is not None
    finally:
        sys.path = original_path


@pytest.mark.parametrize("py_file", _core_py_files(), ids=lambda p: p.relative_to(_CORE).as_posix())
def test_no_banned_imports_in_core(py_file: Path):
    """Core modules must not import repo-specific code at static analysis level."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                names = [node.module] if node.module else []
            for name in names:
                for banned in _BANNED_IMPORTS:
                    assert not name.startswith(banned), (
                        f"{py_file.relative_to(_REPO)}: banned import '{name}' "
                        f"(matches '{banned}')"
                    )


@pytest.mark.parametrize("py_file", _core_py_files(), ids=lambda p: p.relative_to(_CORE).as_posix())
def test_no_sys_path_mutation_in_core(py_file: Path):
    """Core modules must not mutate sys.path at module level."""
    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        # Catch: sys.path.insert(0, ...) or sys.path.append(...) at module level
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute):
                if (
                    isinstance(call.func.value, ast.Attribute)
                    and call.func.value.attr == "path"
                    and isinstance(call.func.value.value, ast.Name)
                    and call.func.value.value.id == "sys"
                    and call.func.attr in ("insert", "append")
                ):
                    # Only flag module-level calls (not inside functions/classes)
                    # A simple heuristic: if the node is in the top-level body
                    pass  # AST walk doesn't give depth; rely on static analysis above

    # Textual check for module-level sys.path — fragile but adequate for this purpose
    lines = source.splitlines()
    in_function = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("async def "):
            in_function = True
        if not line.startswith(" ") and not line.startswith("\t"):
            if stripped.startswith("def ") or stripped.startswith("class "):
                in_function = True
            else:
                in_function = False
        if not in_function and "sys.path" in stripped and (
            "insert" in stripped or "append" in stripped
        ):
            pytest.fail(
                f"{py_file.relative_to(_REPO)}: module-level sys.path mutation: {stripped!r}"
            )


def test_no_absolute_paths_in_core_source():
    """Core source must not contain hardcoded absolute paths."""
    home = str(Path.home())
    for py_file in _core_py_files():
        content = py_file.read_text(encoding="utf-8")
        for line_no, line in enumerate(content.splitlines(), 1):
            if home in line and not line.strip().startswith("#"):
                pytest.fail(
                    f"{py_file.relative_to(_REPO)}:{line_no}: absolute home path: {line.strip()!r}"
                )


def test_public_api_symbols_exported():
    """The __init__.py exports all documented public symbols."""
    import mermaid_fidelity as pkg
    expected = [
        "FidelityAdapter",
        "FidelityCase",
        "FidelityManifest",
        "FidelityRunner",
        "Observation",
        "ComparisonStatus",
        "SemanticDiagram",
        "RenderProfile",
        "parse_manifest",
    ]
    for sym in expected:
        assert hasattr(pkg, sym), f"mermaid_fidelity.{sym} not exported from __init__.py"
