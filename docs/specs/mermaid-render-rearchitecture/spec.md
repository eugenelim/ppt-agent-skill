# Spec: mermaid-render-rearchitecture

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Mode:** Full (structural re-architecture — new module boundary + public interface)

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Consolidate the mermaid render core **in-repo** into a single cohesive, lift-ready
package `scripts/mermaid_render/` with a clean public API (`to_html` / `to_svg` /
`to_png`), a built-in **brand-neutral adaptable default theme**, and a
Playwright-optional import split. This establishes the exact seam a future external
repo will lift wholesale to publish as a standalone Python package — after which
this repo swaps its internal import for that dependency.

This is **NOT** a packaging task (no `pyproject.toml`, `setup.py`, version, or PyPI
metadata) and **NOT** an external repo. It is also **NOT coupled to `svg2pptx`** —
that stays a separate downstream SVG consumer and is not touched by this spec.

## Acceptance Criteria

- [x] `scripts/mermaid_render/` is a cohesive package; consistent relative imports
  throughout; no absolute imports from sibling `scripts/*.py`.
- [x] Public API (`__init__.py`) exposes `to_html(src, *, theme=None) -> str`,
  `to_svg(src, *, theme=None) -> str`, `to_png(src, *, theme=None, scale=1.0) -> bytes`.
- [x] `theme=None` yields the adaptive default:
  - `to_html`: CSS-var-driven markup with neutral fallbacks + `prefers-color-scheme`
    auto light/dark; polished standalone and adapts when a host page overrides vars.
  - `to_svg`/`to_png`: adaptive palette baked concretely (light mode, no ambient CSS).
- [x] Named themes `"adaptive"`, `"auto"`, `"light"`, `"dark"` supported; `dict`
  of CSS-var overrides accepted for custom theming.
- [x] Guard test (subprocess-isolated): `python -c "import mermaid_render; mermaid_render.to_html('flowchart LR\n  A --> B')"` completes without importing playwright in that process.
- [x] Guard test: AST scan confirms `mermaid_render/` imports nothing from sibling `scripts/*.py` modules.
- [x] Guard tests wired into CI (separate job from browser tests to preserve subprocess isolation).
- [x] The ppt skill's rendered output is pixel/byte-unchanged — it passes an explicit
  theme (`THEME_DARK` or dict) so the adaptive default does not alter it.
- [x] `svg2pptx.py` is unchanged; no coupling in either direction.
- [x] Gates green: `tests/test_oracle.py`, `tests/test_mermaid_layout.py`,
  `tests/test_payload_boundary.py`, `tests/test_svg2pptx_shapes.py`,
  `tests/test_mermaid_render_guards.py`; render-scripts CI job green.
- [x] No PyPI artifacts (`pyproject.toml`/`setup.py`/version).
- [x] `make_page` in `layout/_renderer.py` is not shadowed — `themes.py` exposes `render_page` (the new unified entry) to avoid name collision.

## Boundaries

### Always do

- Create `scripts/mermaid_render/` with the file structure below.
- Create `scripts/mermaid_render/layout/` by adapting `scripts/mermaid_layout/`
  (update icon path to 4 parents up, keep all relative intra-package imports).
- Create `scripts/mermaid_render/browser.py` by adapting `scripts/_browser.py`
  (no import changes — no siblings used).
- Create `scripts/mermaid_render/svg.py` by adapting `scripts/html2svg.py`
  (replace `from _browser import` with `from .browser import`; update BUNDLE_PATH).
- Create `scripts/mermaid_render/png.py` by adapting `scripts/html2png.py`
  (replace `from _browser import` with `from .browser import`).
- Create `scripts/mermaid_render/vendor/dom-to-svg.bundle.js` (copy from `scripts/vendor/`).
- Create `scripts/mermaid_render/themes.py` with `THEME_ADAPTIVE_DARK`, `THEME_ADAPTIVE_LIGHT`,
  `Theme` type, `make_adaptive_page(fragment) -> str`, `make_baked_page(fragment, palette) -> str`,
  `render_page(fragment, theme) -> str` (unified entry point, not named `make_page` to avoid collision with `layout._renderer.make_page`).
- Create `scripts/mermaid_render/__init__.py` with `to_html`, `to_svg`, `to_png`;
  `to_svg` and `to_png` delegate through `to_html` (no duplicated dispatch+theme logic).
- Keep `scripts/mermaid_layout/` as a thin shim; each private submodule (`_strategies.py`,
  `_routing.py`, etc.) uses `sys.modules[__name__] = <real module>` to expose all symbols
  (including underscore-prefixed ones, bypassing the no-`__all__` limitation).
- Keep `scripts/html2svg.py` as a thin CLI wrapper delegating to `mermaid_render.svg.main()`.
- Keep `scripts/html2png.py` as a thin CLI wrapper delegating to `mermaid_render.png.main()`.
- Keep `scripts/_browser.py` as a thin shim re-exporting from `mermaid_render.browser`.
- Add guard tests in `tests/test_mermaid_render_guards.py` using **subprocess** for the
  playwright-cleanliness assertion (not in-process, which is polluted by other test modules).
- Wire `test_mermaid_render_guards.py` into `.github/workflows/tests.yml` as a standalone job.
- `test_oracle.py` is **left untouched** (the shim carries `_dispatch` via the shim `__init__.py`).
- Update `tests/test_payload_boundary.py` to handle `mermaid_render/` directory.

### Never do

- No `pyproject.toml`, `setup.py`, version fields, or PyPI metadata.
- No changes to `scripts/svg2pptx.py` or any import coupling to/from it.
- No changes to the ppt skill's rendered output (explicit theme callers unchanged).
- Do not delete `scripts/mermaid_layout/` — it becomes a shim (backward compat for SKILL.md
  and for `test_mermaid_layout.py`, `test_snapshots.py`, `test_diagram_qa.py`).
- Do not rename `make_page` in `layout/_renderer.py` — it stays for internal layout use.
- Do not inline `_dispatch` + theme logic into `to_svg`/`to_png` — they must delegate to `to_html`.

## Design

### File structure after refactor

```
scripts/
├── mermaid_render/              # NEW cohesive package (lift unit)
│   ├── __init__.py              # public API: to_html, to_svg, to_png, Theme
│   ├── themes.py                # ADAPTIVE_DARK/LIGHT palettes, render_page
│   ├── browser.py               # ← _browser.py (no imports changed)
│   ├── svg.py                   # ← html2svg.py (relative browser import)
│   ├── png.py                   # ← html2png.py (relative browser import)
│   ├── vendor/
│   │   └── dom-to-svg.bundle.js # ← copy from scripts/vendor/
│   └── layout/                  # ← mermaid_layout/ (icon path fix only)
│       ├── __init__.py          # re-exports (unchanged — all relative)
│       ├── __main__.py          # updated sys.path + import
│       ├── _constants.py        # icon path: 4 parents up
│       ├── _layout.py
│       ├── _parser.py
│       ├── _renderer.py         # keeps make_page (internal use)
│       ├── _routing.py
│       └── _strategies.py
├── mermaid_layout/              # SHIM → each *.py aliases real module via sys.modules trick
├── html2svg.py                  # THIN WRAPPER → mermaid_render.svg.main()
├── html2png.py                  # THIN WRAPPER → mermaid_render.png.main()
└── _browser.py                  # SHIM → re-exports from mermaid_render.browser
```

### Public API (`__init__.py`)

```python
Theme = str | dict[str, str] | None

def to_html(src: str, *, theme: Theme = None) -> str:
    # no playwright import path
    from .layout._strategies import _dispatch
    from .themes import render_page
    return render_page(_dispatch(src, None, 0), theme)

def to_svg(src: str, *, theme: Theme = None) -> str:
    # playwright triggered here, not at import time
    _resolved_theme = theme if theme is not None else "adaptive-light"
    html = to_html(src, theme=_resolved_theme)
    from .svg import _to_svg_from_html_string
    return _to_svg_from_html_string(html)

def to_png(src: str, *, theme: Theme = None, scale: float = 1.0) -> bytes:
    _resolved_theme = theme if theme is not None else "adaptive-light"
    html = to_html(src, theme=_resolved_theme)
    from .png import _to_png_from_html_string
    return _to_png_from_html_string(html, scale=scale)
```

### Adaptive theme design

Two palettes, WCAG AA compliant, brand-neutral, distinct from ppt THEME_DARK/THEME_LIGHT:

**Adaptive Light** (baked for SVG/PNG when `theme=None`):
```
--bg-primary:    #FAFAF9
--card-bg-from:  #FFFFFF
--card-bg-to:    #F5F4F0
--card-border:   #E2E0D8
--text-primary:  #1A1916   (contrast ~18:1 on white)
--text-secondary: #6B6860  (contrast ~5.5:1)
--accent-1:      #2563EB   (blue)
--accent-2:      #059669   (green)
--accent-3:      #D97706   (amber)
--accent-4:      #7C3AED   (violet)
--edge-label-bg: #F5F4F0
--font-primary:  -apple-system, Inter, sans-serif
--node-shadow:   0 1px 3px rgba(0,0,0,0.08)
--node-radius:   8px
--group-radius:  8px
```

**Adaptive Dark** (default in `to_html` CSS vars, overridden by light via media query):
```
--bg-primary:    #0F1117
--card-bg-from:  #1C2033
--card-bg-to:    #161929
--card-border:   #2D3454
--text-primary:  #E8EDF7   (contrast ~14:1 on dark bg)
--text-secondary: #94A3B8
--accent-1:      #60A5FA
--accent-2:      #34D399
--accent-3:      #FBBF24
--accent-4:      #A78BFA
--edge-label-bg: #1C2033
--font-primary:  -apple-system, Inter, sans-serif
--node-shadow:   0 1px 3px rgba(0,0,0,0.4)
--node-radius:   8px
--group-radius:  8px
```

`to_html` with `theme=None`: `:root { /* adaptive dark defaults */ } @media (prefers-color-scheme: light) { :root { /* adaptive light */ } }`.

`to_svg`/`to_png` with `theme=None`: internally calls `to_html(src, theme="adaptive-light")` to bake concrete light vars. Chromium resolves them deterministically.

### Playwright-optional import split

`__init__.py` top-level imports ONLY from `.themes` and `.layout._strategies` (both playwright-free).
`to_svg` and `to_png` do a function-level deferred import:
```python
from .svg import _to_svg_from_html_string  # triggers playwright only here
```

### `mermaid_layout/` shim pattern

Each private submodule uses module-aliasing to expose all symbols (including underscore-prefixed):
```python
# scripts/mermaid_layout/_strategies.py (shim)
import sys
from mermaid_render.layout import _strategies as _real
sys.modules[__name__] = _real
```

This is the only safe pattern when there is no `__all__` — `import *` would silently drop all `_`-prefixed names.

The shim `__init__.py` re-exports the public names that `test_oracle.py` and others use:
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from mermaid_render.layout import *  # noqa: F401,F403
from mermaid_render.layout._strategies import _dispatch  # noqa: F401
```
(This import works because `__all__` in `mermaid_render.layout.__init__.py` lists every symbol.)

### Lift-readiness invariant

`mermaid_render/` imports only:
- stdlib
- `playwright` (lazy, only `browser.py`, `svg.py`, `png.py`)
- its own submodules (relative imports)
- vendored JS bundle (path reference)

**Enforced by guard test** — AST scan of every `.py` in `mermaid_render/` asserts no import targets sibling `scripts/*.py` module names.

### Vendor bundle note

`scripts/vendor/dom-to-svg.bundle.js` is copied (not symlinked) into `mermaid_render/vendor/`. While both copies coexist in-repo, they must stay identical. A note in `test_payload_boundary.py` asserts byte-identity of the two copies. The canonical source stays in `scripts/vendor/`; `mermaid_render/vendor/` is the lift-ready copy. (deferred: `docs/backlog.md` — replace dual-copy with single canonical + symlink after lift)

## Testing Strategy

### Guard tests (`tests/test_mermaid_render_guards.py`) — TDD mode

**(a) Playwright import cleanliness — subprocess-isolated:**
```python
def test_to_html_does_not_load_playwright():
    import subprocess, sys, json
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'scripts');"
         "import mermaid_render;"
         "mermaid_render.to_html('flowchart LR\\n  A --> B');"
         "import json; print(json.dumps(list(sys.modules.keys())))"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    assert result.returncode == 0, result.stderr
    loaded = json.loads(result.stdout)
    assert not any("playwright" in m for m in loaded)
```

**(b) No sibling-scripts imports (AST scan):**
```python
def test_mermaid_render_no_sibling_imports():
    import ast
    scripts = REPO_ROOT / "scripts"
    sibling_names = (
        {p.stem for p in scripts.glob("*.py")}
        | {p.name for p in scripts.iterdir()
           if p.is_dir() and (p / "__init__.py").exists()
           and p.name != "mermaid_render"}
    )
    pkg = scripts / "mermaid_render"
    for py_file in pkg.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in sibling_names, f"{py_file.name}: imports sibling {top!r}"
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    top = node.module.split(".")[0]
                    assert top not in sibling_names, f"{py_file.name}: imports sibling {top!r}"
```

**(c) Default-theme unit tests:**
```python
def test_to_html_adaptive_has_prefers_color_scheme():
    html = mermaid_render.to_html("flowchart LR\n  A --> B")
    assert "prefers-color-scheme" in html
    assert "#161d2e" not in html  # ppt-brand THEME_DARK value, must not appear

def test_to_html_explicit_dict_theme():
    html = mermaid_render.to_html("flowchart LR\n  A --> B", theme={"--bg-primary": "#ABCDEF"})
    assert "#ABCDEF" in html
```

### Parity tests (existing suites as regression nets)

- `test_oracle.py` — left untouched; uses shim `from mermaid_layout import _dispatch`.
- `test_mermaid_layout.py` — left untouched; shim submodules expose all `_`-prefixed symbols.
- `test_svg2pptx_shapes.py` — left untouched; `svg2pptx.py` unchanged.
- `test_browser.py` — left untouched; uses shim `import _browser`.
- `test_html2svg_tmp_isolation.py` — left untouched; uses shim `html2svg.py` thin wrapper.
- `test_html2png_cwd.py` — left untouched; uses shim `html2png.py` thin wrapper.
- `test_payload_boundary.py` — updated: add `mermaid_render` dir handling + bundle parity check.

### CI gate

New CI job `mermaid-render-guards` in `tests.yml` runs `test_mermaid_render_guards.py` in isolation (no other test files) to preserve subprocess isolation for finding (a).

## Assumptions

1. `scripts/mermaid_layout/` is the sole consumer of the layout engine within the
   shipped payload (SKILL.md references it as a CLI); confirmed from SKILL.md audit.
2. `scripts/html2svg.py` and `scripts/html2png.py` are called with dir-based CLI
   args (`html_dir` / `output_dir`), not string args — thin wrappers preserve this.
3. `mermaid_render.layout.__init__.py` defines `__all__` (verified: it does);
   the shim `from mermaid_render.layout import *` therefore propagates all listed symbols.
   Private `_`-prefixed names NOT in `__all__` are exposed via the per-submodule
   `sys.modules` aliasing pattern.
4. `vendor/dom-to-svg.bundle.js` is a stable pre-built artifact; copying into
   `mermaid_render/vendor/` is safe for lift-readiness. The two copies are asserted
   identical by a test gate while both live in-repo.
5. The ppt skill always passes an explicit theme dict or named theme to `make_page`;
   `theme=None` (adaptive default) is not used by existing callers — confirmed by
   grepping SKILL.md.
6. `test_diagram_qa.py` and `test_snapshots.py` import from `mermaid_layout` — they
   will ride the shim and are included in the final gate run.
7. The lift-seam decision (consolidating render core before extracting to external
   package) is an architectural choice documented in the spec objective, not yet in
   a formal ADR. An ADR will be authored prior to the external extraction step.
   (deferred: `docs/backlog.md`)

## Deferred

- Differential parity test (byte-compare CLI output before/after) — needs browser, deferred: `docs/backlog.md`
- Vendor bundle single-source (symlink vs copy, post-lift) — deferred: `docs/backlog.md`
- ADR for lift-seam decision — deferred: `docs/backlog.md`
