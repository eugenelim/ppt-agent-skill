#!/usr/bin/env python3
"""test_html_packager.py — the preview assembler collates slide pages by page
NUMBER, not lexicographically.

Regression for the bug where `sorted(dir.glob("*.html"))` ordered
slide-10.html..slide-19.html ahead of slide-2.html ('1' < '2'), so the
packaged preview showed slides 11–19 before slide 2.

No pytest harness; run directly or via smoke_test.py. Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import html_packager as H  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(cond: bool, msg: str) -> None:
        if not cond:
            FAILS.append(msg)


    # --- collect_slides orders by page number (the real, un-padded naming) ---
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        # Real slide files are un-padded (cli-cheatsheet: slides/slide-1.html);
        # 19 pages is enough to expose the lexicographic mis-sort at the 10/2 boundary.
        for n in range(1, 20):
            (d / f"slide-{n}.html").write_text("<html></html>")

        ordered = [p.name for p in H.collect_slides(d)]
        expected = [f"slide-{n}.html" for n in range(1, 20)]
        check(ordered == expected,
              f"collect_slides orders by page number 1..19 (got {ordered[:4]}…)")
        # Pin the exact symptom from the bug report: slide-2 must precede slide-11.
        check(ordered.index("slide-2.html") < ordered.index("slide-11.html"),
              "slide-2 precedes slide-11 (not the other way round)")

    if FAILS:
        print(f"✗ test_html_packager: {len(FAILS)} failure(s)")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("✓ test_html_packager: all checks pass")
    sys.exit(0)
