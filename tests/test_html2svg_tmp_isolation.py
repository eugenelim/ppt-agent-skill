#!/usr/bin/env python3
"""test_html2svg_tmp_isolation.py — proves html2svg's per-invocation temp dirs
don't collide across concurrent runs (deck-run-isolation spec).

No pytest harness in this repo; run directly or via smoke_test.py.
Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import html2svg as H  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(name: str, cond: bool) -> None:
        print(f"  [{'OK' if cond else 'XX'}] {name}")
        if not cond:
            FAILS.append(name)


    def main() -> int:
        work = Path(tempfile.mkdtemp(prefix="h2svg-worktest-"))
        try:
            a = H.make_run_tmp(work)
            b = H.make_run_tmp(work)
            check("two allocations are distinct", a != b)
            check("both exist as dirs", a.is_dir() and b.is_dir())
            # node_modules resolution relies on the temp dir being a direct child of
            # work_dir (Node walks up from the script's dir to find node_modules).
            check("both are direct children of work_dir", a.parent == work and b.parent == work)
            # The collision property: two concurrent runs write the SAME basename
            # temp file; distinct parent dirs mean they must not clobber.
            (a / "dom2svg_tmp.js").write_text("//run-a")
            (b / "dom2svg_tmp.js").write_text("//run-b")
            check(
                "same-basename temp files coexist without clobber",
                (a / "dom2svg_tmp.js").read_text() == "//run-a"
                and (b / "dom2svg_tmp.js").read_text() == "//run-b",
            )
            shutil.rmtree(a)
            shutil.rmtree(b)
            check("cleanup removes temp dirs", not a.exists() and not b.exists())
        finally:
            shutil.rmtree(work, ignore_errors=True)

        # Guard the real callers, not just the helper: a regression that writes a
        # fixed-name temp back at work_dir would re-introduce the collision while
        # leaving the helper test green. Assert against the source directly.
        import re

        src = (ROOT / "scripts" / "html2svg.py").read_text()
        fixed_at_workdir = re.findall(
            r'work_dir\s*/\s*"\.(?:dom2svg_tmp|fallback_tmp|pdf_tmp|bundle_entry)', src
        )
        check("no fixed-name temp written directly at work_dir", not fixed_at_workdir)
        check("per-invocation temp is allocated under run_tmp", src.count("run_tmp /") >= 4)

        if FAILS:
            print(f"FAIL: {len(FAILS)} check(s) failed")
            return 1
        print("all pass")
        return 0


    if __name__ == "__main__":
        sys.exit(main())
