# Plan: mermaid-render CLI + icon consolidation

**Status:** Executing

## Task list

### T1 — Copy icon assets into package
**Mode:** Goal-based
**Depends on:** none
**Touches:** `scripts/mermaid_render/icons/`

**Copy** (not `git mv`) all 94 SVGs and `catalog.json` from `assets/icons/` into
`scripts/mermaid_render/icons/`. Create `__init__.py`. Keep `assets/icons/` intact
until T8 — `icon_search.py` reads from `assets/icons/` until the shim lands in T7.

**Tests:** `ls scripts/mermaid_render/icons/*.svg | wc -l` = 94; `catalog.json` present; `__init__.py` present.
**Done when:** files present in new location and staged (`git add scripts/mermaid_render/icons/`); `assets/icons/` still intact.

---

### T2 — Fix `_ICON_DIR` in `layout/_constants.py` + scrub stale comment
**Mode:** Goal-based
**Depends on:** T1
**Touches:** `scripts/mermaid_render/layout/_constants.py`

Two changes in the same file:

1. Line 11 — change:
```python
_ICON_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "icons"
```
to:
```python
_ICON_DIR = Path(__file__).parent.parent / "icons"
```
(`__file__` = `.../scripts/mermaid_render/layout/_constants.py`; two parents = `scripts/mermaid_render/`; `/ "icons"` = `scripts/mermaid_render/icons/`.)

2. Line ~198 — update the inline comment that says `assets/icons/` to say `mermaid_render/icons/`:
```python
icon: str = ""  # icon name from mermaid_render/icons/ (without .svg)
```

**Tests:** `python3 -c "import sys; sys.path.insert(0,'scripts'); from mermaid_render.layout._constants import _load_icon; assert _load_icon('database')"` exits 0. Existing `test_mermaid_layout.py` `_load_icon` tests pass.
**Done when:** gate above passes; `grep "assets/icons" scripts/mermaid_render/layout/_constants.py` returns empty.

---

### T3 — Add `test_icon_catalog_drift` to guards
**Mode:** TDD
**Depends on:** T1, T2
**Touches:** `tests/test_mermaid_render_guards.py`

Add to `tests/test_mermaid_render_guards.py`:

```python
def test_icon_catalog_drift():  # STUB: AC12
    """catalog.json entries must exactly match SVG files in mermaid_render/icons/."""
    import json
    icons_dir = SCRIPTS / "mermaid_render" / "icons"
    catalog = json.loads((icons_dir / "catalog.json").read_text())
    catalog_files = {e["file"] for e in catalog.get("icons", [])}
    actual_svgs = {p.name for p in icons_dir.glob("*.svg")}
    missing = catalog_files - actual_svgs
    orphans = actual_svgs - catalog_files
    assert missing == set(), f"catalog.json references missing SVGs: {sorted(missing)}"
    assert orphans == set(), f"SVGs without catalog.json entries: {sorted(orphans)}"
```

**Tests:** stub: true — `python3 -m pytest tests/test_mermaid_render_guards.py::test_icon_catalog_drift -q` is red before T1 and green after T2.
**Done when:** test passes (green).

---

### T4 — Add `scripts/mermaid_render/_icons_cli.py`
**Mode:** TDD (driven by `test_icon_search.py` + new drift test)
**Depends on:** T1, T2
**Touches:** `scripts/mermaid_render/_icons_cli.py` (new)

Port `icon_search.py` logic; key differences:
- `ICONS_DIR = Path(__file__).parent / "icons"`
- `CATALOG = ICONS_DIR / "catalog.json"`
- Keep all public symbols: `ICONS_DIR`, `CATALOG`, `FORBIDDEN`, `load_catalog()`, `search()`, `validate()`, `score()`, `_tokens()`
- Add `run_icons(args: argparse.Namespace) -> int` for dispatch from `__main__.py`
- Keep `main(argv=None) -> int` for shim backward compat
- **Scrub `assets/icons/` from module docstring and `validate()` error message** — update to say `mermaid_render/icons/`

**Approach:**
```
ICONS_DIR = Path(__file__).parent / "icons"
CATALOG   = ICONS_DIR / "catalog.json"
FORBIDDEN = [...]                         # unchanged from icon_search.py
_PAINT_ATTR = ...                         # unchanged
_ALLOWED_PAINT = ...                      # unchanged

def load_catalog() -> dict: ...
def _tokens(s: str) -> list[str]: ...
def score(icon: dict, query_tokens: list[str]) -> int: ...
def search(query: str, catalog: dict, category: str | None = None) -> list[dict]: ...
def validate(catalog: dict) -> list[str]: ...   # reads ICONS_DIR (global, mutable for tests)

def run_icons(args: argparse.Namespace) -> int:
    """Dispatcher called by mermaid_render.__main__ icons subcommand."""
    if args.validate:
        problems = validate(load_catalog())
        if problems:
            for p in problems: print(p, file=sys.stderr)
            return 1
        print("icon library OK")
        return 0
    if args.snippet:
        hits = search(args.query, load_catalog(), args.category)
        if not hits:
            print("no match", file=sys.stderr); return 1
        print((ICONS_DIR / hits[0]["file"]).read_text(encoding="utf-8").rstrip())
        return 0
    if args.list or not args.query:
        icons = load_catalog().get("icons", [])
        if args.category:
            icons = [i for i in icons if i.get("category") == args.category]
        if args.json_out:
            import json; print(json.dumps(icons, indent=2))
        else:
            for i in icons:
                print(f"{i['id']:<18} {i.get('category',''):<16} {' · '.join(i.get('tags', []))}")
        return 0
    # search
    hits = search(args.query, load_catalog(), args.category)
    if args.json_out:
        import json; print(json.dumps(hits, indent=2))
    else:
        for i in hits:
            print(f"{i['id']:<18} {i.get('category',''):<16} {' · '.join(i.get('tags', []))}  → {i['file']}")
    return 0

def main(argv=None) -> int:
    """Standalone entry point (used by icon_search.py shim)."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--category")
    ap.add_argument("--json", action="store_true", dest="json_out")
    ap.add_argument("--snippet", action="store_true")
    ap.add_argument("--validate", action="store_true")
    return run_icons(ap.parse_args(argv))
```

**Tests:** `python3 tests/test_icon_search.py` exits 0 (after T7 shim, or directly by setting sys.path so `icon_search` maps to `_icons_cli`).
**Done when:** `python3 -c "import sys; sys.path.insert(0,'scripts'); from mermaid_render._icons_cli import load_catalog, validate; assert validate(load_catalog()) == []"` exits 0.

---

### T5 — Write CLI smoke test files (red stubs)
**Mode:** TDD
**Depends on:** T4
**Touches:** `tests/test_mermaid_render_cli.py` (new), `tests/test_mermaid_render_cli_playwright.py` (new), `.github/workflows/tests.yml`

Write the test files and wire them into CI. Before T6 creates `__main__.py`, these tests
are red (exit non-zero with "No module `__main__`" or subcommand-not-found).

`tests/test_mermaid_render_cli.py` (no-playwright; runs in `mermaid-render-guards`):
```python
"""Smoke tests for python3 -m mermaid_render (playwright-free subcommands)."""
import json, subprocess, sys
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
```

`tests/test_mermaid_render_cli_playwright.py` (playwright; runs in `render-scripts`):
```python
"""Smoke tests for svg/png subcommands (require Playwright)."""
import subprocess, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "mermaid_render", *args],
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
```

CI additions to `tests.yml`:
- `mermaid-render-guards` job: add `tests/test_mermaid_render_cli.py` to pytest command
- `mermaid-render-guards` job: add `python3 tests/test_icon_search.py` as a separate run step
- `render-scripts` job: add `tests/test_mermaid_render_cli_playwright.py` to pytest command

**Tests:** stub: true — all test functions carry `# STUB: AC<n>` markers; running `pytest tests/test_mermaid_render_cli.py` before T6 exits non-zero (red — `__main__.py` absent).
**Done when:** test files exist and committed; CI job includes them; tests are red.

---

### T6 — Add `scripts/mermaid_render/__main__.py` (make T5 tests green)
**Mode:** TDD
**Depends on:** T3, T4, T5
**Touches:** `scripts/mermaid_render/__main__.py` (new)

Implement the top-level CLI; T5's tests go from red to green.

```python
#!/usr/bin/env python3
"""python3 -m mermaid_render <subcommand>"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

_scripts_dir = Path(__file__).parent.parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))


def _read_source(source: str) -> str:
    if source.startswith("@"):
        try:
            return Path(source[1:]).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"mermaid_render: {exc}", file=sys.stderr); sys.exit(1)
    return source.replace("\\n", "\n")


def _write_text(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def _cmd_render(args: argparse.Namespace) -> int:
    from . import to_html
    src = _read_source(args.source)
    try:
        html = to_html(src, theme=args.theme)
    except Exception as exc:
        print(f"mermaid_render render: {exc}", file=sys.stderr); return 1
    _write_text(html, args.output)
    return 0


def _cmd_svg(args: argparse.Namespace) -> int:
    from . import to_svg
    src = _read_source(args.source)
    try:
        _write_text(to_svg(src, theme=args.theme), args.output)
    except Exception as exc:
        print(f"mermaid_render svg: {exc}", file=sys.stderr); return 1
    return 0


def _cmd_png(args: argparse.Namespace) -> int:
    from . import to_png
    src = _read_source(args.source)
    try:
        data = to_png(src, theme=args.theme, scale=args.scale)
    except Exception as exc:
        print(f"mermaid_render png: {exc}", file=sys.stderr); return 1
    if args.output:
        Path(args.output).write_bytes(data)
    else:
        sys.stdout.buffer.write(data)
    return 0


def _cmd_icons(args: argparse.Namespace) -> int:
    from ._icons_cli import run_icons
    return run_icons(args)


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="python3 -m mermaid_render",
        description="Mermaid diagram renderer.",
    )
    sub = ap.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    def _src(p): p.add_argument("--source", required=True, metavar="TEXT",
        help="Mermaid source, or @file.mmd.")
    def _out(p): p.add_argument("--output", default=None, metavar="FILE")
    def _theme(p): p.add_argument("--theme", default=None, choices=["auto", "light", "dark"])

    p = sub.add_parser("render", help="Mermaid → themed HTML page (no browser)")
    _src(p); _theme(p); _out(p)
    p.set_defaults(func=_cmd_render)

    p = sub.add_parser("svg", help="Mermaid → SVG (requires Playwright)")
    _src(p); _theme(p); _out(p)
    p.set_defaults(func=_cmd_svg)

    p = sub.add_parser("png", help="Mermaid → PNG (requires Playwright)")
    _src(p); _theme(p); _out(p)
    p.add_argument("--scale", type=float, default=1.0, metavar="FLOAT")
    p.set_defaults(func=_cmd_png)

    p = sub.add_parser("icons", help="Icon library: search, validate, snippet")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--list", action="store_true")
    p.add_argument("--category", metavar="TEXT")
    p.add_argument("--snippet", action="store_true")
    p.add_argument("--json", action="store_true", dest="json_out")
    p.add_argument("--validate", action="store_true")
    p.set_defaults(func=_cmd_icons)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

**Done when:** `python3 -m pytest tests/test_mermaid_render_cli.py -q` green (all T5 tests pass).

---

### T7 — Update `icon_search.py` → shim
**Mode:** Goal-based
**Depends on:** T4
**Touches:** `scripts/icon_search.py`

Replace content:
```python
#!/usr/bin/env python3
"""Backward-compat shim: icon_search → mermaid_render._icons_cli."""
import sys as _sys, pathlib as _p
_sys.path.insert(0, str(_p.Path(__file__).parent))
from mermaid_render import _icons_cli as _real  # noqa: E402
_sys.modules[__name__] = _real
if __name__ == "__main__":
    _sys.exit(_real.main())
```

**Tests:** `python3 scripts/icon_search.py --validate` exits 0; `python3 tests/test_icon_search.py` exits 0.
**Done when:** both pass.

---

### T8 — Delete `assets/icons/`, update all refs
**Mode:** Goal-based
**Depends on:** T5, T6, T7, T9
**Touches:** `assets/icons/`, `references/icons.md`, `references/blocks/diagram.md`, `references/blocks/diagram-architecture.md`, `tests/test_icon_search.py`

- `git rm -r assets/icons/` (git-tracked removal)
- Update `references/icons.md`: replace `assets/icons/` path references with `scripts/mermaid_render/icons/` only (command reference rewrite owned by T9)
- Update `references/blocks/diagram.md` lines 211, 222: `assets/icons/` path → `scripts/mermaid_render/icons/`
- Update `references/blocks/diagram-architecture.md` lines 271, 291: same substitution (note: line 291's `icon_search.py` command reference is retained — the shim is still valid)
- Fix stale path in `tests/test_icon_search.py` docstring (line 5): `python3 scripts/test_icon_search.py` → `python3 tests/test_icon_search.py`
- Check `.gitignore` for any `assets/icons` exception — none expected, but verify
- Confirm `test_payload_boundary.py` passes (no change needed — it only scans `scripts/*.py`)

**Behavior note:** bare `mermaid_render icons` (no query, no flags) lists all icons and exits 0 — an intentional UX improvement over `icon_search.py`'s bare-invocation help+exit-2. The shim inherits the new behavior.

**Tests:**
```bash
grep -r "assets/icons" scripts/ references/ --include="*.py" --include="*.md" | grep -v "docs/specs"
# must return empty
```
**Done when:** grep returns no active-code hits (AC15); all test suites pass (AC17); `python3 tests/test_icon_search.py` exits 0 (AC14).

---

### T9 — Document new CLI in `references/cli-cheatsheet.md`
**Mode:** Goal-based
**Depends on:** T6
**Touches:** `references/cli-cheatsheet.md`, `references/icons.md`

Add a `python3 -m mermaid_render` section documenting all four subcommands with one example each. Update `references/icons.md` `icon_search.py` command invocations to `python3 -m mermaid_render icons` (path references handled separately by T8).

**Tests:**
```bash
grep -c "mermaid_render" references/cli-cheatsheet.md
# must return ≥ 4 (render, svg, png, icons)
grep "scripts/icon_search.py" references/icons.md
# must return empty
```
**Done when:** cheatsheet grep ≥ 4 (AC16); no `scripts/icon_search.py` invocation remains in `references/icons.md`.
