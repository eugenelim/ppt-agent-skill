"""Smoke tests for python3 -m mermaid_render (playwright-free subcommands)."""
from __future__ import annotations

import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mermaid_render.__main__ import main as _mr_main


def _run(*args: str) -> SimpleNamespace:
    """Invoke mermaid_render CLI in-process — no subprocess, no pyenv shim hits."""
    stdout_buf, stderr_buf = StringIO(), StringIO()
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        with patch("sys.argv", ["mermaid_render", *args]):
            try:
                rc = _mr_main()
            except SystemExit as exc:
                rc = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return SimpleNamespace(
        returncode=rc if rc is not None else 0,
        stdout=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
    )


def test_render_stdout():  # STUB: AC3
    r = _run("render", "--source", "flowchart LR\n  A --> B")
    assert r.returncode == 0
    assert "<!doctype" in r.stdout.lower()


def test_render_backslash_n():  # STUB: AC3 (_read_source literal-\n path)
    r = _run("render", "--source", r"flowchart LR\n  A --> B")
    assert r.returncode == 0
    assert "<!doctype" in r.stdout.lower()


def test_render_at_file(tmp_path):  # STUB: AC4
    f = tmp_path / "d.mmd"
    f.write_text("flowchart LR\n  A --> B")
    r = _run("render", "--source", f"@{f}")
    assert r.returncode == 0
    assert "<!doctype" in r.stdout.lower()


def test_render_theme_light():  # STUB: AC5
    r = _run("render", "--source", "flowchart LR\n  A --> B", "--theme", "light")
    assert r.returncode == 0
    assert "prefers-color-scheme" not in r.stdout


def test_render_output_file(tmp_path):  # STUB: AC4 (--output path)
    out = tmp_path / "out.html"
    r = _run("render", "--source", "flowchart LR\n  A --> B", "--output", str(out))
    assert r.returncode == 0
    assert out.exists()


def test_icons_validate():  # STUB: AC8
    r = _run("icons", "--validate")
    assert r.returncode == 0


def test_icons_list():  # STUB: AC11
    r = _run("icons", "--list")
    assert r.returncode == 0
    assert "database" in r.stdout


def test_icons_list_json():  # STUB: AC11 (--json)
    r = _run("icons", "--list", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert isinstance(data, list) and len(data) > 0


def test_icons_search():  # STUB: AC9
    r = _run("icons", "database")
    assert r.returncode == 0
    assert "database" in r.stdout


def test_icons_snippet():  # STUB: AC10
    r = _run("icons", "database", "--snippet")
    assert r.returncode == 0
    assert "<svg" in r.stdout


def test_icons_no_match():  # STUB: AC10 (no-match exit code + message)
    r = _run("icons", "zzznotanicon", "--snippet")
    assert r.returncode != 0
    assert "no match" in r.stderr


def test_svg_stdout():
    """svg subcommand uses the native pure-Python backend — no Playwright required."""
    r = _run("svg", "--source", "flowchart LR\n  A --> B")
    assert r.returncode == 0
    assert "<svg" in r.stdout
