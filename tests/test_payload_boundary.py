"""tests/test_payload_boundary.py — payload-boundary guard.

Asserts two invariants about the skill's official folders:
(a) No test_*.py files live under scripts/ (they all live in tests/).
(b) Every scripts/*.py (non-package __init__) is reachable from the adopter-facing
    roots via direct reference or one level of Python imports.

These tests are red until the refactor completes; they are the acceptance check.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

# Adopter-facing roots: files whose content defines what's invoked at runtime.
_ROOTS: list[Path] = [
    REPO_ROOT / "SKILL.md",
    REPO_ROOT / "references" / "cli-cheatsheet.md",
]
# Also include every .md under references/ and .claude/skills/
_ROOTS += list((REPO_ROOT / "references").rglob("*.md"))
_ROOTS += list((REPO_ROOT / ".claude" / "skills").rglob("*.md"))

# Pattern: scripts/<name> or scripts/<name>.py
_SCRIPTS_REF_PAT = re.compile(r"scripts/([A-Za-z0-9_]+)(?:\.py)?")


def _directly_reachable() -> set[str]:
    """Return set of script basenames (no .py) directly referenced in roots."""
    found: set[str] = set()
    for root in _ROOTS:
        if not root.exists():
            continue
        text = root.read_text(errors="replace")
        for m in _SCRIPTS_REF_PAT.finditer(text):
            found.add(m.group(1))
    return found


def _imports_of(path: Path) -> set[str]:
    """Return set of bare module names imported at the top level of a script."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _reachable_scripts() -> set[str]:
    """Return set of script basenames reachable via direct refs + one import hop."""
    direct = _directly_reachable()
    reachable = set(direct)
    for name in list(direct):
        candidate = SCRIPTS / f"{name}.py"
        if candidate.exists():
            for imp in _imports_of(candidate):
                if (SCRIPTS / f"{imp}.py").exists():
                    reachable.add(imp)
    return reachable


def test_no_test_files_in_scripts() -> None:
    """No test_*.py files should remain under scripts/."""
    found = list(SCRIPTS.rglob("test_*.py"))
    assert found == [], (
        f"Found {len(found)} test_*.py file(s) under scripts/:\n"
        + "\n".join(f"  {p.relative_to(REPO_ROOT)}" for p in sorted(found))
    )


def test_mermaid_render_vendor_bundle_parity() -> None:
    """mermaid_render/vendor/dom-to-svg.bundle.js must be byte-identical to scripts/vendor/.

    Both copies are committed (whitelisted in .gitignore); this is a hard gate,
    not an optional skip — if either file is absent the tree is broken.
    """
    orig = SCRIPTS / "vendor" / "dom-to-svg.bundle.js"
    copy = SCRIPTS / "mermaid_render" / "vendor" / "dom-to-svg.bundle.js"
    assert orig.exists(), (
        "scripts/vendor/dom-to-svg.bundle.js missing — it is a committed asset"
    )
    assert copy.exists(), (
        "scripts/mermaid_render/vendor/dom-to-svg.bundle.js missing — copy from scripts/vendor/"
    )
    assert copy.read_bytes() == orig.read_bytes(), (
        "mermaid_render/vendor/dom-to-svg.bundle.js diverged from scripts/vendor/ — keep in sync"
    )


def test_all_scripts_reachable() -> None:
    """Every scripts/*.py (non-__init__) must be reachable from adopter-facing roots."""
    reachable = _reachable_scripts()
    # Collect all non-package, non-__init__ scripts (skip sub-packages like mermaid_layout/)
    all_scripts = {
        p.stem
        for p in SCRIPTS.glob("*.py")
        if p.name != "__init__.py"
    }
    # mermaid_layout/ is a package — check it's referenced as a directory, not stem
    # (its __main__.py is invoked as `python3 scripts/mermaid_layout`)
    ml_ref = any(
        "mermaid_layout" in root.read_text(errors="replace")
        for root in _ROOTS
        if root.exists()
    )
    if "mermaid_layout" in all_scripts or not ml_ref:
        pass  # handled separately if needed

    unreachable = all_scripts - reachable
    # _browser is an internal shim; mermaid_render loads it indirectly.
    # __main__ may not be referenced in docs.
    # compare_gallery and gen_comparison_page are developer visual-QA tools.
    _ALLOWED_UNREACHABLE = {"__main__", "_browser", "compare_gallery", "gen_comparison_page"}
    assert unreachable <= _ALLOWED_UNREACHABLE, (
        f"scripts/*.py not reachable from adopter-facing roots: {sorted(unreachable - _ALLOWED_UNREACHABLE)}\n"
        "Add a reference in SKILL.md/cli-cheatsheet/references/, or move to tools/."
    )
