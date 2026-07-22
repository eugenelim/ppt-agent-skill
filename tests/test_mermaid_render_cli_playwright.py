"""Subprocess smoke tests for python3 -m mermaid_render png subcommand (requires Playwright).

The svg subcommand uses the native pure-Python backend for supported diagram types
(e.g. flowchart) and does NOT require Playwright; that test lives in
test_mermaid_render_cli.py as a browser-free in-process test.

The png subcommand always needs Playwright; it is tested here via subprocess to
verify process-boundary wiring (import isolation + real Chromium path).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

# Bypass pyenv shims to avoid rehash lock contention under concurrent pytest runs.
REAL_PYTHON = os.path.realpath(sys.executable)


def _run(*args):
    return subprocess.run(
        [REAL_PYTHON, "-m", "mermaid_render", *args],
        capture_output=True, cwd=str(SCRIPTS),
    )


@pytest.mark.browser
@pytest.mark.isolation
def test_png_output_file(tmp_path):  # STUB: AC7
    out = tmp_path / "out.png"
    r = _run("png", "--source", "flowchart LR\n  A --> B", "--output", str(out))
    assert r.returncode == 0
    assert out.exists() and out.stat().st_size > 0
