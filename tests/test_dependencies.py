"""Dependency enforcement tests for the mermaid_render layout engine.

AC-DEP.1: isolated interpreter test (no site-packages)
AC-DEP.2: import allowlist (no forbidden heavy dependencies)
AC-DEP.3: no subprocess in runtime renderer
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYOUT_DIR = ROOT / "scripts" / "mermaid_render" / "layout"

_FORBIDDEN_IMPORTS = {
    "networkx", "numpy", "scipy", "shapely",
    "graphviz", "pygraphviz", "pydot",
    "PIL", "playwright",
}


def _collect_imports(path: Path) -> set[str]:
    """Return top-level module names imported anywhere in a .py file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


class TestIsolatedInterpreter:
    """AC-DEP.1: renderer works without user site-packages."""

    def test_to_html_runs_without_site_packages(self):
        src = "flowchart TD\\n    A --> B"
        code = (
            "import sys; sys.path.insert(0, 'scripts'); "
            "import mermaid_render; "
            f"html = mermaid_render.to_html('{src}'); "
            "assert 'data-node-id' in html"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-c", code],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, (
            f"to_html failed without site-packages:\n{result.stderr}"
        )


class TestImportAllowlist:
    """AC-DEP.2: layout module imports no forbidden heavy dependencies."""

    def test_layout_import_allowlist(self):
        py_files = list(LAYOUT_DIR.rglob("*.py"))
        assert py_files, f"No .py files found under {LAYOUT_DIR}"
        violations: list[str] = []
        for path in py_files:
            imports = _collect_imports(path)
            forbidden_found = imports & _FORBIDDEN_IMPORTS
            if forbidden_found:
                rel = path.relative_to(ROOT)
                violations.append(f"{rel}: {sorted(forbidden_found)}")
        assert not violations, (
            "Forbidden imports found in layout engine:\n" + "\n".join(violations)
        )


class TestNoSubprocess:
    """AC-DEP.3: layout module does not import subprocess."""

    def test_no_subprocess_in_runtime_renderer(self):
        py_files = list(LAYOUT_DIR.rglob("*.py"))
        assert py_files, f"No .py files found under {LAYOUT_DIR}"
        violations: list[str] = []
        for path in py_files:
            imports = _collect_imports(path)
            if "subprocess" in imports:
                violations.append(str(path.relative_to(ROOT)))
        assert not violations, (
            "subprocess imported in layout engine:\n" + "\n".join(violations)
        )
