"""Smoke tests for python3 -m mermaid_render svg/png subcommands (requires Playwright)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

# Bypass pyenv shims to avoid rehash lock contention under concurrent pytest runs.
REAL_PYTHON = os.path.realpath(sys.executable)


def _run(*args):
    return subprocess.run(
        [REAL_PYTHON, "-m", "mermaid_render", *args],
        capture_output=True, cwd=str(SCRIPTS),
    )


def test_svg_stdout():  # STUB: AC6
    r = _run("svg", "--source", "flowchart LR\n  A --> B")
    assert r.returncode == 0
    assert b"<svg" in r.stdout


def test_png_output_file(tmp_path):  # STUB: AC7
    out = tmp_path / "out.png"
    r = _run("png", "--source", "flowchart LR\n  A --> B", "--output", str(out))
    assert r.returncode == 0
    assert out.exists() and out.stat().st_size > 0
