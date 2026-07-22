# Spec: mermaid-render CLI + icon consolidation

**Status:** Shipped
**Mode:** Full (risk triggers: structural — new module + package dir; destructive — delete `assets/icons/`; public-interface — new top-level CLI)

## Objective

Consolidate icon assets into the `mermaid_render` package and expose a unified
top-level CLI (`python3 -m mermaid_render`) covering `render`, `svg`, `png`, and
`icons` subcommands. Retire the `assets/icons/` tree (deleted) and make
`icon_search.py` a backward-compat shim.

## Boundaries

**In scope:**
- `scripts/mermaid_render/icons/` — new sub-package (copied from `assets/icons/`)
- `scripts/mermaid_render/_icons_cli.py` — icon search/validate/snippet logic (ported from `icon_search.py`)
- `scripts/mermaid_render/__main__.py` — top-level CLI dispatcher
- `scripts/mermaid_render/layout/_constants.py` — `_ICON_DIR` path fix + `assets/icons/` comment scrub
- `scripts/icon_search.py` — becomes backward-compat shim
- `tests/test_mermaid_render_cli.py` — CLI smoke tests (no-playwright subcommands)
- `tests/test_mermaid_render_cli_playwright.py` — CLI smoke tests (svg/png subcommands)
- `tests/test_mermaid_render_guards.py` — add `test_icon_catalog_drift`
- `references/icons.md` — update path + `icon_search.py` references
- `references/cli-cheatsheet.md` — add `python3 -m mermaid_render` section
- `references/blocks/diagram.md` — update `assets/icons/` path references
- `references/blocks/diagram-architecture.md` — update `assets/icons/` path references
- `.github/workflows/tests.yml` — wire new test files + `python3 tests/test_icon_search.py` CI step

**Not in scope:**
- `mermaid_render.layout.__main__` — kept as-is (still works via `python3 -m mermaid_render.layout`)
- `html2svg.py` / `html2png.py` shims — unchanged
- Any PyPI/packaging config — deferred
- `assets/` directory (other than `icons/`) — untouched

## Acceptance Criteria

- [x] **AC1** `scripts/mermaid_render/icons/` contains all 94 SVGs from `assets/icons/` plus `catalog.json` and `__init__.py`
- [x] **AC2** `_ICON_DIR` in `layout/_constants.py` resolves within the package (no parent-walking past `mermaid_render/`)
- [x] **AC3** `python3 -m mermaid_render render --source "flowchart LR\n  A-->B"` exits 0, stdout contains `<!doctype`
- [x] **AC4** `python3 -m mermaid_render render --source @file.mmd --output out.html` writes file, exits 0
- [x] **AC5** `python3 -m mermaid_render render --source "..." --theme light` produces baked HTML (no `prefers-color-scheme`)
- [x] **AC6** `python3 -m mermaid_render svg --source "..."` exits 0, stdout is SVG (requires Playwright)
- [x] **AC7** `python3 -m mermaid_render png --source "..." --output out.png` exits 0, writes PNG (requires Playwright)
- [x] **AC8** `python3 -m mermaid_render icons --validate` exits 0 against the shipped catalog
- [x] **AC9** `python3 -m mermaid_render icons database` prints match table, exits 0
- [x] **AC10** `python3 -m mermaid_render icons database --snippet` prints `<svg` content, exits 0
- [x] **AC11** `python3 -m mermaid_render icons --list --json` prints valid JSON array, exits 0
- [x] **AC12** `test_icon_catalog_drift` fails if any `catalog.json` entry has no matching SVG file, and if any SVG has no catalog entry
- [x] **AC13** `import icon_search as I; I.load_catalog(); I.search("db", I.load_catalog())` works (shim preserves API)
- [x] **AC14** `python3 tests/test_icon_search.py` exits 0 (standalone test, not pytest)
- [x] **AC15** `assets/icons/` directory is deleted; no code or active reference doc references it (grep `scripts/ references/ --include="*.py" --include="*.md"` returns no hits outside `docs/specs/`)
- [x] **AC16** `references/cli-cheatsheet.md` documents `python3 -m mermaid_render render|svg|png|icons`
- [x] **AC17** All existing test suites pass

## Testing Strategy

| Task | Mode | Gate |
|------|------|------|
| Icon assets move + `_ICON_DIR` fix | Goal-based | `_load_icon("database")` returns non-empty; existing `test_mermaid_layout.py` passes |
| Drift lint | TDD | `test_icon_catalog_drift` green |
| `_icons_cli.py` | TDD | `python3 tests/test_icon_search.py` exits 0 |
| Top-level CLI — no-playwright cmds | TDD (T5 red → T6 green) | `tests/test_mermaid_render_cli.py` green in `mermaid-render-guards` job |
| Top-level CLI — playwright cmds | TDD (T5 red → T6 green) | `tests/test_mermaid_render_cli_playwright.py` green in `render-scripts` job |
| cli-cheatsheet docs (AC16) | Goal-based | `grep -c "mermaid_render" references/cli-cheatsheet.md` ≥ 4 (render, svg, png, icons each present) |
| `icon_search.py` shim | Goal-based | `python3 scripts/icon_search.py --validate` exits 0 |
| `assets/icons/` deletion + ref cleanup | Goal-based | `grep -r "assets/icons" scripts/ references/` returns no active-code hits |

## Assumptions

1. All 94 SVG files in `assets/icons/` are tracked by git and safe to move.
2. `catalog.json` structure: `{"version": 1, "icons": [{id, name, category, tags, keywords, viewBox, file, provenance}, ...]}` — hand-maintained, stays as-is.
3. `mermaid_render.to_svg` / `to_png` are the correct entry points for the `svg`/`png` subcommands (they handle Playwright internally).
4. `render` subcommand produces a full themed HTML page (not just the raw fragment).

## Declined patterns

- `importlib.resources` for icon loading — the direct `Path(__file__)` path is simpler for in-repo use; `importlib.resources` is for installed wheels, deferred.
- `MERMAID_RENDER_ICON_DIR` env-var override — deferred; the within-package path is correct for all current use cases.
- Auto-generating catalog from SVG metadata — user explicitly said catalog stays hand-maintained.
- Collapsing `layout/__main__.py` into the new CLI — `python3 -m mermaid_render.layout` keeps working unchanged; no need to touch it.

## Disposition record (resolve-vs-surface)

| Item | Resolution |
|------|-----------|
| 94-file destructive move | Resolved — files are git-tracked; moved to new path under version control, not deleted |
| `test_icon_search.py` `I.ICONS_DIR` mutation | Resolved — shim pattern (`sys.modules[__name__] = _real`) preserves module-level var mutation; `_icons_cli.ICONS_DIR` is mutated correctly |
| `render` vs fragment output | Resolved — `render` → full themed HTML page (more useful standalone); `layout/__main__.py` → raw fragment (legacy, unchanged) |
| CI job routing for new tests | Resolved — no-playwright tests → `mermaid-render-guards`; playwright tests → `render-scripts` |
