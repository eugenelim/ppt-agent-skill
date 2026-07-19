#!/usr/bin/env python3
"""test_html2png_cwd.py — html2png Playwright-contract assertions.

Verifies that html2png.py:
- has no Puppeteer/Node bootstrap code
- uses an unguarded top-level bare import from _browser
- wraps get_browser() in a RuntimeError catch (not ImportError)
- has no subprocess node invocations

No pytest harness; run directly or via smoke_test.py. Exit 0 = all pass, 1 = failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


if __name__ == "__main__":
    FAILS: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  [{'OK' if cond else 'XX'}] {name}")
        if not cond:
            FAILS.append(name)

    def main() -> int:
        src = (ROOT / "scripts" / "mermaid_render" / "png.py").read_text()

        # Old Puppeteer helpers must be gone
        check("get_dep_dir removed", "def get_dep_dir(" not in src)
        check("node_env removed", "def node_env(" not in src)
        check("ensure_puppeteer removed", "def ensure_puppeteer(" not in src)
        check("SCREENSHOT_SCRIPT removed", "SCREENSHOT_SCRIPT" not in src)

        # Bare unguarded top-level import (relative, from mermaid_render.png)
        check("bare import from .browser present", "from .browser import" in src)
        # The import line itself must not be preceded by a try: on the same indentation level
        lines = src.splitlines()
        import_lines = [l for l in lines if "from .browser import" in l]
        for il in import_lines:
            check(f"import line not indented (unguarded): {il.strip()!r}", not il.startswith(" ") and not il.startswith("\t"))

        # RuntimeError catch at call site (not ImportError)
        check("RuntimeError catch present", "RuntimeError" in src)
        check("no ImportError catch on import line", "except ImportError" not in src)

        # No node subprocess calls
        check("no subprocess node call", '"node"' not in src and "'node'" not in src)

        # Docstring updated
        check("docstring references Playwright", "Playwright" in src)

        if FAILS:
            print(f"FAIL: {len(FAILS)} check(s) failed")
            return 1
        print("all pass")
        return 0

    sys.exit(main())
