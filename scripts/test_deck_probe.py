#!/usr/bin/env python3
"""test_deck_probe.py — deck_probe.py extracts reusable form deterministically
and never reaches for an un-bundled library.

Uses a committed HTML gallery mock as the fixture (no external deck needed, no
install, no network). No pytest harness; run directly or via smoke_test.py.
Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import deck_probe as D  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)


def run(argv: list[str]) -> str:
    buf = io.StringIO()
    old = sys.argv
    sys.argv = ["deck_probe.py"] + argv
    try:
        with redirect_stdout(buf):
            D.main()
    finally:
        sys.argv = old
    return buf.getvalue()

# web probe on a committed mock: pulls :root vars, font stacks, hex palette
mock = ROOT / "ppt-output" / "style-gallery" / "schematic_blueprint.html"
check(mock.exists(), "fixture mock must exist")
out = run([str(mock)])
check("--purple: #a100ff" in out or "--purple:#a100ff" in out.replace(" ", ""),
      "web probe must extract :root custom properties")
check("FONT_STACKS" in out and "Fraunces" in out, "web probe must extract font stacks")
check("TOP_HEX_COLORS" in out and "#a100ff" in out.lower(), "web probe must extract hex palette")

# visual/binary formats must yield guidance, never an install
out_pdf = run([str(ROOT / "assets" / "architecture.svg")])
check("do NOT install" in out_pdf, "SVG/visual formats must tell the agent NOT to install a parser")

if FAILS:
    print(f"✗ test_deck_probe: {len(FAILS)} failure(s)")
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
print("✓ test_deck_probe: all checks pass")
sys.exit(0)
