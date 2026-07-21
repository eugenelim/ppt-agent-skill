"""Guard tests for scripts/mermaid_render/ — TDD stubs (red until package exists).

(a) Playwright import cleanliness: to_html must not load playwright in-process.
    Verified via subprocess so pytest session pollution cannot pollute this check.
(b) AST scan: mermaid_render/ must import nothing from sibling scripts/*.py modules.
(c) Default-theme unit tests: adaptive output has prefers-color-scheme, not ppt-brand values.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

# Bypass pyenv shims to avoid rehash lock contention under concurrent pytest runs.
REAL_PYTHON = os.path.realpath(sys.executable)

sys.path.insert(0, str(SCRIPTS))


def test_to_html_does_not_load_playwright():
    """to_html() must not import playwright — checked in a fresh subprocess."""
    result = subprocess.run(
        [
            REAL_PYTHON, "-c",
            (
                "import sys; sys.path.insert(0, 'scripts');"
                "import mermaid_render;"
                "mermaid_render.to_html('flowchart LR\\n  A --> B');"
                "import json; print(json.dumps(list(sys.modules.keys())))"
            ),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"subprocess failed:\n{result.stderr}"
    loaded = json.loads(result.stdout)
    pw_mods = [m for m in loaded if "playwright" in m]
    assert pw_mods == [], (
        f"to_html() triggered playwright import: {pw_mods}"
    )


def test_mermaid_render_no_sibling_imports():
    """AST scan: mermaid_render/ must not import any sibling scripts/*.py module."""
    pkg = SCRIPTS / "mermaid_render"
    assert pkg.exists(), "mermaid_render package missing — T1-T7 not yet run"

    sibling_names = (
        {p.stem for p in SCRIPTS.glob("*.py")}
        | {
            p.name
            for p in SCRIPTS.iterdir()
            if p.is_dir()
            and (p / "__init__.py").exists()
            and p.name != "mermaid_render"
        }
    )

    violations: list[str] = []
    for py_file in pkg.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in sibling_names:
                        violations.append(f"{py_file.relative_to(SCRIPTS)}: imports sibling {top!r}")
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    top = node.module.split(".")[0]
                    if top in sibling_names:
                        violations.append(f"{py_file.relative_to(SCRIPTS)}: imports sibling {top!r}")

    assert violations == [], "mermaid_render/ contains sibling imports:\n" + "\n".join(violations)


def test_to_html_adaptive_has_prefers_color_scheme():
    """to_html with no theme arg emits CSS-var-driven markup with prefers-color-scheme."""
    import mermaid_render
    html = mermaid_render.to_html("flowchart LR\n  A --> B")
    assert "prefers-color-scheme" in html, "Adaptive theme must include prefers-color-scheme media query"
    # ppt-brand THEME_DARK value — must NOT appear in adaptive default
    assert "#161d2e" not in html, "Adaptive theme must not use ppt-brand dark colors"
    assert "--bg-primary" in html, "Adaptive theme must define CSS vars"


def test_to_html_explicit_dict_theme():
    """to_html with an explicit dict theme emits those CSS var values."""
    import mermaid_render
    html = mermaid_render.to_html(
        "flowchart LR\n  A --> B",
        theme={"--bg-primary": "#ABCDEF", "--card-bg-from": "#123456"},
    )
    assert "#ABCDEF" in html, "Custom dict theme value must appear in output"
    assert "#123456" in html, "Custom dict theme second value must appear in output"


def test_to_html_named_dark_theme():
    """to_html with theme='dark' bakes THEME_ADAPTIVE_DARK — no prefers-color-scheme."""
    import mermaid_render
    from mermaid_render.themes import THEME_ADAPTIVE_DARK
    html = mermaid_render.to_html("flowchart LR\n  A --> B", theme="dark")
    assert "prefers-color-scheme" not in html, "Baked dark theme must not have media query"
    assert THEME_ADAPTIVE_DARK["--bg-primary"] in html, "THEME_ADAPTIVE_DARK bg-primary must appear"


def test_to_html_named_light_theme():
    """to_html with theme='light' bakes THEME_ADAPTIVE_LIGHT — no prefers-color-scheme."""
    import mermaid_render
    from mermaid_render.themes import THEME_ADAPTIVE_LIGHT
    html = mermaid_render.to_html("flowchart LR\n  A --> B", theme="light")
    assert "prefers-color-scheme" not in html, "Baked light theme must not have media query"
    assert THEME_ADAPTIVE_LIGHT["--bg-primary"] in html, "THEME_ADAPTIVE_LIGHT bg-primary must appear"


def test_to_html_named_auto_theme():
    """to_html with theme='auto' is identical to theme=None (adaptive)."""
    import mermaid_render
    html = mermaid_render.to_html("flowchart LR\n  A --> B", theme="auto")
    assert "prefers-color-scheme" in html, "'auto' theme must include prefers-color-scheme media query"


def test_to_html_unknown_named_theme_raises():
    """to_html with an unrecognized string theme raises ValueError."""
    import mermaid_render
    import pytest
    with pytest.raises(ValueError, match="unknown theme"):
        mermaid_render.to_html("flowchart LR\n  A --> B", theme="lite")


def test_icon_catalog_drift():  # STUB: AC12
    """catalog.json entries must exactly match SVG files in mermaid_render/icons/."""
    import json
    icons_dir = SCRIPTS / "mermaid_render" / "icons"
    catalog = json.loads((icons_dir / "catalog.json").read_text())
    catalog_files = {e["file"] for e in catalog.get("icons", [])}
    actual_svgs = {p.name for p in icons_dir.glob("*.svg")}
    missing = catalog_files - actual_svgs
    orphans = actual_svgs - catalog_files
    assert missing == set(), f"catalog.json references missing SVGs: {sorted(missing)}"
    assert orphans == set(), f"SVGs without catalog.json entries: {sorted(orphans)}"
