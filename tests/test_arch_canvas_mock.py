#!/usr/bin/env python3
"""test_arch_canvas_mock.py — the architecture-canvas demo mock stays
pipeline-safe. It is not a per-style `smoke_test` fixture (its filename isn't a
style id), so this standing gate runs smoke_test's own checkers against it — a
future edit can't ship forbidden CSS ungated.

No pytest harness; run directly or via smoke_test.py. Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import smoke_test as S  # noqa: E402


if __name__ == "__main__":
    MOCK = ROOT / "ppt-output" / "style-gallery" / "architecture-canvas.demo.html"
    FAILS: list[str] = []

    if not MOCK.exists():
        print(f"✗ demo mock missing: {MOCK}")
        sys.exit(1)

    forbidden = S.check_html_pipeline_compat(MOCK)
    if forbidden:
        FAILS.append(f"forbidden CSS: {forbidden}")

    # icons must be inline <svg>, never referenced (url()/<img>) — the delivery rule
    text = MOCK.read_text(encoding="utf-8")
    if "<img" in text.lower():
        FAILS.append("mock references an <img> — icons must be inline <svg>")
    if text.count("<svg") < 5:
        FAILS.append("expected the architecture-canvas demo to inline multiple icon <svg>s")

    if FAILS:
        print(f"✗ test_arch_canvas_mock: {len(FAILS)} failure(s)")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("✓ test_arch_canvas_mock: demo mock pipeline-safe, icons inline")
    sys.exit(0)
