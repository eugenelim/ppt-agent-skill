"""Smoke tests for python3 -m mermaid_render (playwright-free subcommands)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "mermaid_render", *args],
        capture_output=True, text=True, cwd=str(SCRIPTS),
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
