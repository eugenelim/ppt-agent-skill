# Plan: mermaid-render-rearchitecture

- **Status:** Done
- **Spec:** [`spec.md`](spec.md)

## Files touched

**New:** `scripts/mermaid_render/` (entire package), `tests/test_mermaid_render_guards.py`

**Modified (shims):** `scripts/mermaid_layout/__init__.py`, `scripts/mermaid_layout/__main__.py`,
and all `scripts/mermaid_layout/_*.py` submodules (module-aliasing shims);
`scripts/html2svg.py`, `scripts/html2png.py`, `scripts/_browser.py`

**Modified:** `tests/test_payload_boundary.py`, `.github/workflows/tests.yml`

**Not touched:** `scripts/svg2pptx.py`, `SKILL.md`, `tests/test_oracle.py`,
`tests/test_mermaid_layout.py`, `tests/test_browser.py`, all other scripts

## Not changing

- `svg2pptx.py` — no coupling in either direction
- `SKILL.md` — thin shims preserve existing CLI invocations
- `test_oracle.py`, `test_mermaid_layout.py`, `test_browser.py`, `test_html2svg_tmp_isolation.py`,
  `test_html2png_cwd.py` — shims make all existing imports work unchanged

## Declined-pattern register

- **Tempted to inline `_dispatch` + theme logic into `to_svg`/`to_png`:** declining — spec says delegate through `to_html`; duplication causes drift.
- **Tempted to rename `make_page` in `_renderer.py`:** declining — ppt skill internals call it; break-free is not in scope.
- **Tempted to use `from X import *` for shim submodules:** declining — no `__all__` means underscore names silently dropped; must use `sys.modules` aliasing.
- **Tempted to add pyproject.toml:** declining — spec explicitly excludes packaging.
- **Tempted to add a ThemeRegistry or extensible theme system:** declining — simple Union type alias is enough; over-engineering a hypothetical future.

## Tasks

### T0 — Guard tests (red stubs) [TDD, Depends on: none]

**Tests (red until T7 completes):**
- `test_to_html_does_not_load_playwright` — subprocess check: playwright not in sys.modules after to_html call
- `test_mermaid_render_no_sibling_imports` — AST scan of `mermaid_render/`
- `test_to_html_adaptive_has_prefers_color_scheme` — unit: adaptive output contains media query
- `test_to_html_explicit_dict_theme` — unit: custom dict theme vars appear in output

**Approach:**
Write `tests/test_mermaid_render_guards.py`. Tests 1-2 are red (mermaid_render doesn't exist yet);
tests 3-4 are also red until `__init__.py` and `themes.py` exist.

**Done when:** file created; `pytest tests/test_mermaid_render_guards.py` shows failures (not collection errors).

---

### T1 — Create `scripts/mermaid_render/layout/` [Goal-based, Depends on: none]

**Approach:**
1. `mkdir -p scripts/mermaid_render/layout/`
2. Copy all 8 files from `scripts/mermaid_layout/`.
3. In `layout/_constants.py`: change `_ICON_DIR` line to:
   `_ICON_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "icons"`
   (4 parents: `layout/` → `mermaid_render/` → `scripts/` → repo root; icons at repo root)
4. In `layout/__main__.py`: update `_pkg_parent` to go 3 levels up (not 2):
   `_pkg_parent = Path(__file__).parent.parent.parent`
   (so `scripts/` lands on sys.path, enabling `from mermaid_render.layout._strategies import _dispatch`)
   And update the import:
   `from mermaid_render.layout._strategies import _dispatch`
5. All other files: intra-package imports are already relative (`from ._xxx import`) — no changes.

**Done when:** `python3 -c "import sys; sys.path.insert(0,'scripts'); from mermaid_render.layout import _dispatch; print('ok')"` exits 0 from repo root.

---

### T2 — Create `scripts/mermaid_render/browser.py` [Goal-based, Depends on: none]

**Approach:**
Copy `scripts/_browser.py` verbatim as `scripts/mermaid_render/browser.py`.
No import changes needed — only stdlib + playwright (no siblings).

**Done when:** `python3 -c "import sys; sys.path.insert(0,'scripts'); from mermaid_render.browser import _url_allowed; print('ok')"` exits 0.

---

### T3 — Copy vendor bundle [Goal-based, Depends on: none]

**Approach:**
```bash
mkdir -p scripts/mermaid_render/vendor/
cp scripts/vendor/dom-to-svg.bundle.js scripts/mermaid_render/vendor/
```

**Done when:** both files exist and are byte-identical.

---

### T4 — Create `scripts/mermaid_render/themes.py` [Goal-based, Depends on: none]

**Approach:**
New file. Contains:
- `THEME_ADAPTIVE_DARK: dict[str, str]` — neutral dark palette (spec Design section)
- `THEME_ADAPTIVE_LIGHT: dict[str, str]` — neutral light palette
- `Theme = str | dict[str, str] | None` type alias (Python 3.10+ union; use `Union` for 3.9 compat)
- `make_adaptive_page(fragment: str) -> str` — CSS-var driven, prefers-color-scheme
- `make_baked_page(fragment: str, palette: dict[str, str]) -> str` — concrete vars, no media query
- `render_page(fragment: str, theme: Theme = None) -> str` — unified routing:
  - `None` / `"adaptive"` / `"auto"` → `make_adaptive_page(fragment)`
  - `"light"` / `"adaptive-light"` → `make_baked_page(fragment, THEME_ADAPTIVE_LIGHT)`
  - `"dark"` / `"adaptive-dark"` → `make_baked_page(fragment, THEME_ADAPTIVE_DARK)`
  - `dict` → `make_baked_page(fragment, theme)`

Note: `render_page` is the unified entry (not `make_page`, which lives in `layout._renderer` with different signature).

**Done when:** `from mermaid_render.themes import render_page, THEME_ADAPTIVE_LIGHT` succeeds;
`render_page("<div/>", None)` output contains `prefers-color-scheme` and not `#161d2e` (ppt-brand dark color).

---

### T5 — Create `scripts/mermaid_render/svg.py` [Goal-based, Depends on: T2, T3]

**Approach:**
Adapt `scripts/html2svg.py`:
1. Change `from _browser import _setup_page, _within_deck_root, get_browser` → `from .browser import _setup_page, _within_deck_root, get_browser`
2. Change `BUNDLE_PATH` → `Path(__file__).resolve().parent / "vendor" / "dom-to-svg.bundle.js"`
3. Keep `convert(html_dir, output_dir)` unchanged
4. Add `_to_svg_from_html_string(html: str) -> str`:
   ```python
   def _to_svg_from_html_string(html: str) -> str:
       import tempfile
       from pathlib import Path as _Path
       with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
           f.write(html)
           tmp = _Path(f.name)
       try:
           return _to_svg_from_html_file(tmp)
       finally:
           tmp.unlink(missing_ok=True)
   ```
5. Add `_to_svg_from_html_file(html_file: Path) -> str` — single-file conversion returning SVG string
6. Keep `main()` for CLI use

**Done when:** `from mermaid_render.svg import convert` succeeds (no browser needed for import).

---

### T6 — Create `scripts/mermaid_render/png.py` [Goal-based, Depends on: T2]

**Approach:**
Adapt `scripts/html2png.py`:
1. Change `from _browser import get_browser, new_page` → `from .browser import get_browser, new_page`
2. Keep `convert(html_dir, output_dir, scale, full_page)` unchanged
3. Add `_to_png_from_html_string(html: str, scale: float = 1.0) -> bytes`
4. Add `_to_png_from_html_file(html_path: Path, scale: float = 1.0) -> bytes`
5. Keep `main()` for CLI use

**Done when:** `from mermaid_render.png import convert` succeeds (no browser needed for import).

---

### T7 — Create `scripts/mermaid_render/__init__.py` (public API) [TDD, Depends on: T1, T4, T5, T6]

**Tests:**
All four tests in `test_mermaid_render_guards.py` go green.

**Approach:**
```python
from __future__ import annotations
from typing import Union

Theme = Union[str, dict, None]

def to_html(src: str, *, theme: Theme = None) -> str:
    from .layout._strategies import _dispatch
    from .themes import render_page
    return render_page(_dispatch(src, None, 0), theme)

def to_svg(src: str, *, theme: Theme = None) -> str:
    _resolved = theme if theme is not None else "adaptive-light"
    html = to_html(src, theme=_resolved)
    from .svg import _to_svg_from_html_string
    return _to_svg_from_html_string(html)

def to_png(src: str, *, theme: Theme = None, scale: float = 1.0) -> bytes:
    _resolved = theme if theme is not None else "adaptive-light"
    html = to_html(src, theme=_resolved)
    from .png import _to_png_from_html_string
    return _to_png_from_html_string(html, scale=scale)
```

**Done when:** all four guard tests green.

---

### T8 — Create shims and update consumers [Goal-based, Depends on: T1, T2, T5, T6, T7]

**Approach:**

**a. Shim `scripts/mermaid_layout/` submodules** (one pattern per `_*.py` file):
For each of `_constants.py`, `_layout.py`, `_parser.py`, `_renderer.py`, `_routing.py`, `_strategies.py`:
```python
# scripts/mermaid_layout/_strategies.py
import sys as _sys, pathlib as _p
_sys.path.insert(0, str(_p.Path(__file__).parent.parent))
from mermaid_render.layout import _strategies as _real
_sys.modules[__name__] = _real
```
(Analogous for each submodule.)

**b. Shim `scripts/mermaid_layout/__init__.py`:**
```python
import sys as _sys, pathlib as _p
_sys.path.insert(0, str(_p.Path(__file__).parent.parent))
from mermaid_render.layout._strategies import _dispatch  # noqa: F401
from mermaid_render.layout import (
    NODE_CAP, EDGE_CAP, NODE_W, NODE_H, COL_GAP, RANK_GAP, CANVAS_PAD,
    GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT, ICON_COL_WIDTH,
    _Node, _Edge, _Group,
    _load_icon, _measure_text_width, _wrap_label, _split_sub_label, _node_render_h,
    _strip_frontmatter, _detect_directive, _parse_spec,
    _parse_spec_and_class, _parse_graph_source,
    _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates,
    _compact_group_columns,
    _arrowhead, _smooth_orthogonal_path, _fan_offset, _route_edges, _clip_to_diamond,
    _render_graph_fragment, _render_label_html, _extract_diagram_title, _render_metadata_chip,
    _render_legend, _separate_groups_lr, _separate_groups_tb, _compute_group_bboxes,
    _push_nonmembers_out_of_groups_lr,
    STYLE_COMPACT, STYLE_LARGE,
    THEME_DARK, THEME_LIGHT, make_page,
    _group_coherent_cols,
)
```
(mirrors the existing `__all__` list)

**c. Shim `scripts/mermaid_layout/__main__.py`:**
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from mermaid_render.layout.__main__ import main
if __name__ == "__main__":
    main()
```

**d. `scripts/html2svg.py`** → `sys.modules` alias shim (required — `test_html2svg_tmp_isolation.py` pytest class calls `H.convert(...)` which needs `convert` exposed; also `test_browser.py` calls `html2svg.convert` with browser mocked, needs same object):
```python
#!/usr/bin/env python3
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mermaid_render import svg as _real
sys.modules[__name__] = _real
```

Update `test_html2svg_tmp_isolation.py` `__main__` block: change `src = (ROOT / "scripts" / "html2svg.py").read_text()` → `src = (ROOT / "scripts" / "mermaid_render" / "svg.py").read_text()`. Also update the `from _browser import` assertion to check `from .browser import` (relative import in the real module).

**e. `scripts/html2png.py`** → `sys.modules` alias shim (same pattern):
```python
#!/usr/bin/env python3
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mermaid_render import png as _real
sys.modules[__name__] = _real
```
Update `test_html2png_cwd.py` `__main__` block: change `src` path and `from _browser import` assertion analogously.

**f. `scripts/_browser.py`** → `sys.modules` alias shim (required — test_browser.py mutates `_PLAYWRIGHT_AVAILABLE` and uses `mock.patch("_browser.sync_playwright")` which must reach the real module globals):
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mermaid_render import browser as _real
sys.modules[__name__] = _real
```

**g. `tests/test_payload_boundary.py`** — add `mermaid_render` directory handling:
Patch the `test_all_scripts_reachable` test to also check that `mermaid_render` is referenced
(the same pattern as the existing `mermaid_layout` check). Add the vendor-bundle parity assertion.

**h. `.github/workflows/tests.yml`** — add new job:
```yaml
mermaid-render-guards:
  name: mermaid-render guards
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.13"
        cache: "pip"
    - run: pip install pytest
    - run: python3 -m pytest tests/test_mermaid_render_guards.py -q
```
(No playwright install — the subprocess test forks a fresh Python and fails if playwright loads.)

**Done when:** Full gate passes:
```
pytest tests/test_mermaid_render_guards.py tests/test_oracle.py tests/test_mermaid_layout.py tests/test_payload_boundary.py tests/test_svg2pptx_shapes.py tests/test_browser.py tests/test_html2svg_tmp_isolation.py -q
```
(test_diagram_qa.py and test_snapshots.py also run — add if present and runnable without Chromium.)

---

### T9 — Backlog entries [Goal-based, Depends on: T8]

**Approach:**
Add to `docs/backlog.md`:
- Differential parity test (byte-compare CLI output before/after shim)
- Vendor bundle single-source (post-lift: replace dual-copy with symlink)
- ADR for lift-seam architectural decision
- `vendor/` bundle checksum parity gate (currently asserted by test; could be a pre-commit hook)

**Done when:** entries exist in `docs/backlog.md` under a `mermaid-render-rearchitecture` heading.
