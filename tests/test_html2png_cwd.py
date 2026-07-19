#!/usr/bin/env python3
"""test_html2png_cwd.py — html2png resolves puppeteer via an explicit NODE_PATH
(module resolution independent of the caller's cwd / of work_dir sitting under
ppt-output), and writes its temp script to a unique path (no fixed-name collision).

Mirrors test_html2svg_tmp_isolation.py. No pytest harness; run directly or via
smoke_test.py. Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import html2png as H  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(name: str, cond: bool) -> None:
        print(f"  [{'OK' if cond else 'XX'}] {name}")
        if not cond:
            FAILS.append(name)


    def main() -> int:
        work = Path(tempfile.mkdtemp(prefix="h2png-cwdtest-"))
        try:
            dep_dir = H.get_dep_dir(work)
            env = H.node_env(work)
            node_path = env.get("NODE_PATH", "")
            expected_nm = str((dep_dir / "node_modules").resolve())
            check(f"NODE_PATH includes <dep_dir>/node_modules ({expected_nm!r} in {node_path!r})",
                  expected_nm in node_path.split(os.pathsep))

            # Resolution must not depend on the process cwd.
            cur = os.getcwd()
            try:
                os.chdir(tempfile.gettempdir())
                env2 = H.node_env(work)
                check("NODE_PATH stable regardless of os.getcwd()",
                      env2.get("NODE_PATH", "").split(os.pathsep)[0] == node_path.split(os.pathsep)[0])
            finally:
                os.chdir(cur)
        finally:
            import shutil
            shutil.rmtree(work, ignore_errors=True)

        # Source guard (mirrors html2svg test): the old fixed-name temp at work_dir
        # is gone — a regression would re-introduce the concurrent-run collision.
        src = (ROOT / "scripts" / "html2png.py").read_text()
        fixed = re.findall(r'work_dir\s*/\s*"\.html2png_tmp\.js"', src)
        check("no fixed-name temp written at work_dir", not fixed)
        check("html2png exposes node_env() helper", "def node_env(" in src)

        if FAILS:
            print(f"FAIL: {len(FAILS)} check(s) failed")
            return 1
        print("all pass")
        return 0


    if __name__ == "__main__":
        sys.exit(main())
