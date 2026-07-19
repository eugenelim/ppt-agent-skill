# Plan: Playwright Export Migration

- **Spec:** [`spec.md`](spec.md)
- **Status:** Shipped

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Build and commit `scripts/vendor/dom-to-svg.bundle.js` first (the one npm step, then npm is gone). Then introduce `scripts/_browser.py` as the new shared launcher. Migrate the four shipped scripts one at a time in dependency order (html2png, build_pdf, gallery — pure screenshot scripts first since they're simpler — then html2svg, which also needs the bundle). Update the three affected unit tests in lockstep with each script. Migrate `tools/diagram_render_check.py` last. Delete `package.json` / `package-lock.json`. Update shipped-contract docs (SKILL.md, AGENTS.md, READMEs, requirements.txt) and CI.

Riskiest parts: (1) the dom-to-svg in-page JS bodies change from running in Node context to running in Playwright's browser context — they are ported verbatim but any Node-ism (e.g. `fs.readFileSync`) must be removed and replaced with Python-side file I/O; (2) Playwright's `page.route()` replaces Puppeteer's `setRequestInterception` + event-listener; the semantics are equivalent but the Python API differs.

## Constraints

- `build_pdf` must stay on screenshot→Pillow (pixel-1:1 contract). Never switch to `page.pdf()`.
- `dom-to-svg` in-page JS bodies are copied verbatim — no rewrites.
- `scripts/_browser.py` must be reachable from adopter-facing roots via one Python import hop (payload boundary test).
- `playwright==1.61.0` is the pinned version; do not change it without a spec update.

## Construction tests

**Integration tests:**
- End-to-end shipped-payload smoke: `scripts/html2svg.py`, `html2png.py`, `build_pdf.py`, `gallery.py --screenshots` all succeed against real HTML fixtures with `playwright install chromium` as the only browser setup.

**Manual verification:**
- Snapshot baselines re-captured (`pytest tests/test_snapshots.py --snapshot-capture`) and eyeballed for sub-pixel-only drift.
- `build_pdf` output visually 1:1 with source HTML.

## Design (LLD)

### Design decisions

- **Sync Playwright API** (not async): the scripts are invoked as CLI tools; sync keeps `convert()`/`render()` call shapes unchanged. Traces to: AC "four scripts import and use `_browser.py`".
- **`get_browser()` context manager in `_browser.py`**: yields a `Browser` object; each call site creates its own `sync_playwright()` context. Traces to: AC "lazy Chromium provisioning".
- **Lazy provision via exception message sniff**: catch any `Exception` whose `str()` contains `"Executable doesn't exist"`, run `subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])`, retry once. Traces to: AC "lazy Chromium provisioning".
- **`page.route("**/*", handler)` for URL allowlist**: replace `setRequestInterception` + event listener; semantics identical. Traces to: AC "route handler allows only file:// + data:".
- **Deck-root confinement in Python** (`html2svg.py`): the Node-side `fs.readFileSync` loop moves to Python before the `page.evaluate()` call; the JS body receives a pre-populated `imgDataMap` dict. Traces to: AC "deck-root image confinement enforced in Python".
- **`dom-to-svg.bundle.js` via `page.add_script_tag(path=...)`**: replaces `page.addScriptTag({path: bundlePath})`. Traces to: AC "dom-to-svg ships as scripts/vendor/dom-to-svg.bundle.js".

### Dependencies & integration

- `playwright==1.61.0` (shipped `requirements.txt`): wraps headless Chromium; replaces puppeteer+npm.
- `scripts/vendor/dom-to-svg.bundle.js` (committed static asset): built from `dom-to-svg@0.12.2` + `esbuild@0.28.1` in T0; never rebuilt by adopters.
- `Pillow` (existing shipped dep): unchanged — still used by `build_pdf._pngs_to_pdf`.

### Failure, edge cases & resilience

- Playwright/Chromium unavailable after provisioning attempt → each script returns `False` / non-zero exit; callers emit `[SKIP] visual gate: playwright/chromium unavailable` and never hard-fail.
- `page.route` abort on non-file:// URL → same behavior as before; silently blocked, no exception.
- Image outside deck root → Python-side confinement skips with `print("Skipping image outside deck directory: ...", file=sys.stderr)`, matching the prior Node `console.warn`.

---

## Tasks

### T0: Build and commit the dom-to-svg vendor bundle

**Depends on:** none

**Touches:** scripts/vendor/dom-to-svg.bundle.js, package.json, notes/playwright-export-migration/bundle-recipe.md

**Tests:**
- `scripts/vendor/dom-to-svg.bundle.js` exists and is non-empty (goal-based: `test -s scripts/vendor/dom-to-svg.bundle.js`).
- Bundle exports `window.__domToSvg` — verified by grepping the built file for `__domToSvg` (goal-based).
- File is readable as UTF-8 text (no binary corruption).
- `notes/playwright-export-migration/bundle-recipe.md` exists and contains: `dom-to-svg@0.12.2`, `esbuild@0.28.1`, the esbuild command, the `build-entry.js` body, and the output path `scripts/vendor/dom-to-svg.bundle.js` (goal-based: grep for each).

**Approach:**
1. Run `npm ci` in the repo root to install `dom-to-svg@0.12.2` + `esbuild@0.28.1`.
2. Write a one-off build entry `scripts/vendor/build-entry.js`: `import { documentToSVG, elementToSVG, inlineResources } from 'dom-to-svg'; window.__domToSvg = { documentToSVG, elementToSVG, inlineResources };`
3. Run `node_modules/.bin/esbuild scripts/vendor/build-entry.js --bundle --format=iife --outfile=scripts/vendor/dom-to-svg.bundle.js --platform=browser`.
4. Delete `scripts/vendor/build-entry.js` and `node_modules/`.
5. Verify bundle with grep and size check.
6. Write `notes/playwright-export-migration/bundle-recipe.md` documenting the full rebuild recipe: pinned package versions (`dom-to-svg@0.12.2`, `esbuild@0.28.1`), the `build-entry.js` body verbatim, the esbuild command verbatim, and the output path. This is the only surviving `package.json`-adjacent artifact — `package.json` is deleted in T8.
7. Update `package.json` to remove `puppeteer` (keep `dom-to-svg` + `esbuild` for future rebuilds), or simply note that `package.json` is deleted in T8 — leave it for now.

**Done when:** `scripts/vendor/dom-to-svg.bundle.js` exists, is non-empty, and contains `__domToSvg`; `notes/playwright-export-migration/bundle-recipe.md` exists with all required content.

---

### T1: Add `scripts/_browser.py` — shared Playwright launcher with TDD-tested security helpers

**Depends on:** none

**Touches:** scripts/_browser.py, tests/test_browser.py

**Tests:**
- `_url_allowed("file:///path/to/file.html")` → `True` (TDD in `tests/test_browser.py`).
- `_url_allowed("data:text/plain;base64,abc")` → `True` (TDD).
- `_url_allowed("https://evil.com")` → `False` (TDD).
- `_url_allowed("http://localhost")` → `False` (TDD).
- `_url_allowed("filex://not-file")` → `False` (TDD — catches `startswith("file")` false positive).
- `_within_deck_root(deck_root / "slides/s1.html", deck_root)` → `True` (TDD).
- `_within_deck_root(deck_root / "../outside.html", deck_root)` → `False` (TDD — lexical `..` traversal).
- `_within_deck_root(deck_root.resolve(), deck_root)` → `True` (TDD — exact root).
- `_within_deck_root` with a symlink inside the deck root pointing to a path outside → `False` (TDD — symlink escape; requires `Path.resolve()` not just `abspath`).
- `get_browser` context manager is importable from scripts/ via bare `from _browser import get_browser` (goal-based).
- Source contains `"Executable doesn't exist"` as the lazy-provision trigger string (goal-based grep). Note: the lazy-provision retry path is exercised by the T9 fresh-venv smoke, not by T1's unit tests.
- `PLAYWRIGHT_BROWSERS_PATH` and `PLAYWRIGHT_DOWNLOAD_HOST` not hard-coded (goal-based grep).
- `pytest tests/test_browser.py` exits 0 (TDD gate).

**Approach:**
1. Create `scripts/_browser.py` with:
   - `_url_allowed(url: str) -> bool`: returns `url.startswith("file://") or url.startswith("data:")`.
   - `_within_deck_root(path: Path, deck_root: Path) -> bool`: use `Path(path).resolve()` and `deck_root.resolve()` — must call `.resolve()` on both sides to follow symlinks (not just `abspath`); check `is_relative_to` or `str(resolved).startswith(str(deck_root_resolved) + os.sep)`.
   - `get_browser()` context manager using `sync_playwright()`.
   - Launch args: `["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"]`.
   - Lazy provision: catch `Exception` where `"Executable doesn't exist"` in `str(e)`, run `subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)`, retry once.
   - `_setup_page(page, width=1280, height=720, scale=1.0)`: sets viewport via `page.set_viewport_size`; installs route handler using `_url_allowed`.
   - Degradation guard at top of `_browser.py`: `try: from playwright.sync_api import sync_playwright; except ImportError: define stub get_browser that raises RuntimeError("playwright not installed")`. Calling scripts catch `RuntimeError` at the call site in their entry-point function — they do NOT catch `ImportError` and do NOT wrap the `from _browser import` line in a try/except (see B1 resolution below).
2. Write `tests/test_browser.py` with pytest-collectable tests for all `_url_allowed` and `_within_deck_root` cases listed above, including the symlink-escape case. Use `tmp_path` fixture for filesystem cases. No browser required for this test file.

**Done when:** `python3 -c "from _browser import get_browser, _url_allowed, _within_deck_root"` from `scripts/` succeeds; `pytest tests/test_browser.py` exits 0 with all cases passing.

---

### T2: Migrate `scripts/html2png.py` to Playwright

**Depends on:** T1

**Touches:** scripts/html2png.py, tests/test_html2png_cwd.py

**Tests:**
- `html2png.py` no longer defines `get_dep_dir`, `node_env`, `ensure_puppeteer`, or `SCREENSHOT_SCRIPT` (goal-based grep returns empty for each).
- `html2png.py` has top-level bare `from _browser import get_browser, _setup_page` (goal-based grep).
- `html2png.py` does not call `subprocess.run` with `"node"` (goal-based grep).
- `html2png.py` docstring updated to reference Playwright (goal-based grep for "Playwright").
- `convert()` returns `False` cleanly (no traceback) when `get_browser()` raises `RuntimeError("playwright not installed")` (TDD: source-level check that `convert()` wraps `get_browser()` call in a try/except RuntimeError).
- `html2png.py` has an **unguarded top-level** `from _browser import get_browser, _setup_page` — NOT inside a try/except ImportError block (goal-based grep confirms no `try:` wrapping this import line). The degradation guard lives in `_browser.py`, not in each script.
- `tests/test_html2png_cwd.py` updated and exits 0.

**Approach:**
1. Remove `get_dep_dir`, `node_env`, `ensure_puppeteer`, `SCREENSHOT_SCRIPT` from `html2png.py`. Update the module docstring.
2. Add **unguarded top-level** `from _browser import get_browser, _setup_page` (bare, for payload-boundary reachability). Do NOT wrap this line in try/except — `_browser.py` handles ImportError internally by defining a stub.
3. In `convert()`, wrap the `with get_browser() as browser:` block in `try: ... except RuntimeError as e: print(f"[SKIP] html2png: {e}", file=sys.stderr); return False`.
4. Rewrite `convert()` to use `get_browser()`.
5. Rewrite `tests/test_html2png_cwd.py`.

**Done when:** `python3 tests/test_html2png_cwd.py` exits 0; grep confirms no `node` subprocess calls; docstring updated.

---

### T3: Migrate `scripts/build_pdf.py` to Playwright

**Depends on:** T1

**Touches:** scripts/build_pdf.py, tests/test_build_pdf.py

**Tests:**
- `build_pdf.py` no longer defines `_puppeteer_work_dir`, `build_node_script`, or `NODE_TEMPLATE` (goal-based grep returns empty).
- `build_pdf.py` has bare `from _browser import get_browser, _setup_page` (goal-based grep).
- `page.pdf(` absent from `build_pdf.py` (goal-based grep).
- `page.screenshot(` with `clip=` present in `build_pdf.py` (goal-based grep).
- `build_pdf.py` docstring updated (goal-based grep for "Playwright").
- `render()` returns non-zero cleanly on missing `playwright` — `render()` wraps its `get_browser()` call in `try: ... except RuntimeError` (same pattern as T2; goal-based: source-level check).
- `build_pdf.py` has an **unguarded top-level** `from _browser import get_browser, _setup_page` (goal-based grep — no try/except wrapping this import).
- `resolve_documents` and `_pngs_to_pdf` tests in `tests/test_build_pdf.py` still pass (TDD — unchanged).
- `tests/test_build_pdf.py` exits 0.

**Approach:**
1. Remove `NODE_TEMPLATE`, `build_node_script`, `_puppeteer_work_dir` from `build_pdf.py`. Update the module docstring.
2. Add **unguarded top-level** `from _browser import get_browser, _setup_page` (bare). Do NOT wrap in try/except ImportError.
3. Rewrite `render()` to use `get_browser()`; wrap `with get_browser()` in `try: ... except RuntimeError as e: return non-zero`.
4. Update `tests/test_build_pdf.py`: drop `build_node_script` test; add assertions confirming `_browser` import and no `page.pdf(`.

**Done when:** `python3 tests/test_build_pdf.py` exits 0; grep confirms screenshot-only path.

---

### T4: Migrate `scripts/gallery.py` to Playwright

**Depends on:** T1

**Touches:** scripts/gallery.py

**Tests:**
- `gallery.py` no longer embeds Puppeteer JS or calls `subprocess.run` with `"node"` (goal-based grep).
- `gallery.py` has bare `from _browser import get_browser, _setup_page` (goal-based grep).
- `gallery.py --screenshots` path calls `page.screenshot` and routes through `_setup_page` (goal-based grep).
- `gallery.py` docstring updated (goal-based grep for "Playwright").
- `take_screenshots()` returns `False` cleanly on missing `playwright` — wraps its `get_browser()` call in `try: ... except RuntimeError` (same pattern as T2; goal-based: source-level check).
- `gallery.py` has an **unguarded top-level** `from _browser import get_browser, _setup_page` (goal-based grep — no try/except wrapping this import).

**Approach:**
1. Remove the inline Puppeteer JS + `work_dir`/`script_path`/subprocess call from `take_screenshots()`. Update the module docstring.
2. Add **unguarded top-level** `from _browser import get_browser, _setup_page` (bare). Do NOT wrap in try/except ImportError.
3. Rewrite `take_screenshots()`:
   - `with get_browser() as browser:` (wrapped in try/except RuntimeError) → per-item `browser.new_page()` → `_setup_page(page, scale=1.5)` → navigate → `page.wait_for_timeout(800)` → `page.screenshot(path=item["png"], full_page=False)`.
   - `_setup_page` blocks `https://fonts.googleapis.com`. Unlike the other scripts, `gallery.py` previously had **no** request interception, so this is a deliberate (cosmetic) change: web fonts are blocked, system fonts substitute. This is accepted — gallery screenshots are presentational, not pixel-exact.

**Done when:** `grep -n "subprocess.*node" scripts/gallery.py` returns zero; module imports without error; docstring updated.

---

### T5: Migrate `scripts/html2svg.py` to Playwright

**Depends on:** T0, T1

**Touches:** scripts/html2svg.py, tests/test_html2svg_tmp_isolation.py

**Tests:**
- `html2svg.py` no longer defines `ensure_deps`, `make_run_tmp`, `convert_dom_to_svg` (old), `convert_pdf2svg`, `CONVERT_SCRIPT`, `FALLBACK_SCRIPT`, `BUNDLE_ENTRY` (goal-based grep returns empty for each).
- `html2svg.py` has bare `from _browser import get_browser, _setup_page, _within_deck_root` (goal-based grep).
- `html2svg.py` calls `page.add_script_tag(` (goal-based grep).
- Python deck-root confinement logic present (goal-based: grep for `_within_deck_root` or `deck_root` in Python code).
- No `subprocess.run` with `"node"` in `html2svg.py` (goal-based grep).
- `html2svg.py` docstring updated; no mention of pdf2svg fallback (goal-based grep).
- SVG output from a fixture contains at least one `<text>` element (TDD in updated `tests/test_html2svg_tmp_isolation.py` — requires Chromium + playwright).
- `python3 tests/test_html2svg_tmp_isolation.py` exits 0.

**Approach:**
1. Remove all Puppeteer-specific code from `html2svg.py`. Update the module docstring to describe Playwright + dom-to-svg.
2. Add **unguarded top-level** `from _browser import get_browser, _setup_page, _within_deck_root` (bare). Do NOT wrap in try/except ImportError. Wrap the `with get_browser()` call site in `try: ... except RuntimeError as e: return False`.
3. Rewrite `convert()`:
   - `BUNDLE_PATH = Path(__file__).resolve().parent / "vendor" / "dom-to-svg.bundle.js"`.
   - `deck_root = html_file.parent.parent`.
   - Per-file: `browser.new_page()` → `_setup_page(page)` → `goto(...)` → `wait_for_timeout(500)`.
   - **Python-side image inlining**: `img_srcs = page.evaluate("() => Array.from(document.querySelectorAll('img')).map(img => img.getAttribute('src') || '')")` → resolve relative to `html_file.parent` → `_within_deck_root` check → `base64.b64encode(Path(resolved).read_bytes())` → build `img_data_map` dict → pass back via `page.evaluate`.
   - `page.add_script_tag(path=str(BUNDLE_PATH))`.
   - In-page JS preprocessing body (steps 1–6 from old `CONVERT_SCRIPT`): copy verbatim into `page.evaluate(...)`.
   - In-page JS DOM→SVG body: copy verbatim.
   - Write SVG via `Path.write_text`.
4. Update `tests/test_html2svg_tmp_isolation.py`: replace `make_run_tmp` isolation tests with Playwright-contract assertions; add a `<text>` element count assertion on a fixture.

**Done when:** `python3 tests/test_html2svg_tmp_isolation.py` exits 0; grep confirms no `node` subprocess; SVG output contains `<text>` elements.

---

### T6: Migrate `tools/diagram_render_check.py` to Playwright

**Depends on:** T1

**Touches:** tools/diagram_render_check.py

**Tests:**
- `diagram_render_check.py` no longer defines `DOM_INSPECT_SCRIPT`, `_get_dep_dir`, `_node_env`, `_ensure_puppeteer`, `_node_available` (TDD: grep returns empty).
- `diagram_render_check.py` imports `_browser` from `scripts` (goal-based: grep for `from scripts._browser import` or `sys.path` + `_browser`).
- `diagram_render_check.py` has a Playwright/Chromium unavailability `[SKIP]` guard replacing the old `_node_available()` guard (goal-based: grep for `"[SKIP]"` + `"playwright"` in source).
- Tool exits 0 when invoked with no Chromium (simulated by mocking): returns `[SKIP]` (TDD: source-level assertion that the guard exists).

**Approach:**
1. Remove `DOM_INSPECT_SCRIPT`, `_get_dep_dir`, `_node_env`, `_ensure_puppeteer`, `_node_available` from `diagram_render_check.py`.
2. Replace the Node subprocess block with inline Playwright evaluation: use `get_browser()` from `_browser`, navigate each fixture HTML, `page.evaluate(js)` the DOM inspection expression, collect results as Python dicts.
3. Replace `_node_available()` guard at top of `main()` with a `_playwright_available()` function that tries `from playwright.sync_api import sync_playwright` and returns bool. On `False`, print `[SKIP] diagram_render_check: playwright not available` and return 0.
4. `sys.path` insert for `scripts/` at top of file (since `tools/` is not in `scripts/`).

**Done when:** `python3 tools/diagram_render_check.py` runs without errors (Chromium must be installed); grep confirms no `node` subprocess calls.

---

### T7: Update shipped-contract docs and requirements.txt

**Depends on:** T1

**Touches:** SKILL.md, AGENTS.md, README.md, README_EN.md, requirements.txt

**Tests:**
- `grep -n "node\|npm\|puppeteer" SKILL.md` returns only lines referencing the new Playwright setup or the security boundary comments — no "Node.js" prerequisite lines (goal-based).
- `grep "playwright" requirements.txt` returns `playwright==1.61.0` (goal-based).
- `grep "node-≥18" README.md README_EN.md` returns empty (badge removed) (goal-based).
- `grep "Node deps auto-install" AGENTS.md` returns empty (line updated) (goal-based).

**Approach:**
1. `SKILL.md` frontmatter:
   - `subprocess:` line: remove "Node.js (Puppeteer headless Chrome …)"; add "Python3 scripts; Playwright headless Chromium for html2svg/html2png/build_pdf".
   - `network_egress:` line: replace "Puppeteer renders file://" with "Playwright renders file://".
   - `runtime_install:` line: replace "npm (puppeteer, dom-to-svg, esbuild)" with "playwright install chromium (one-time Chromium provisioning)".
   - Node-degradation clauses: flip trigger from "Node unavailable" to "Playwright/Chromium unavailable"; keep behavior (HTML-only fallback, `[SKIP] visual gate`).
2. `README.md` / `README_EN.md`: remove the `node-≥18` badge; replace "puppeteer auto-installs on first html2svg.py run" with "run `playwright install chromium` once after pip install".
3. `AGENTS.md`: replace "Node deps auto-install on first html2svg run" with "Playwright + Chromium (`pip install playwright && playwright install chromium`)".
4. `requirements.txt`: add `playwright==1.61.0`.

**Done when:** All four grep checks pass.

---

### T8: Delete `package.json`, `package-lock.json`; re-capture snapshot baselines

**Depends on:** T0-T7

**Touches:** package.json, package-lock.json, tests/snapshots/

**Tests:**
- `test -f package.json` returns non-zero (file gone) (goal-based).
- `test -f package-lock.json` returns non-zero (file gone) (goal-based).
- `pytest tests/test_payload_boundary.py tests/test_oracle.py tests/test_svg2pptx_shapes.py -q` exits 0 (goal-based).
- Snapshot baselines re-captured: `pytest tests/test_snapshots.py --snapshot-capture` exits 0 (goal-based); human eyeball on diff confirms only sub-pixel Chromium drift.

**Approach:**
1. Delete `package.json` and `package-lock.json`.
2. Run `pytest tests/test_payload_boundary.py tests/test_oracle.py tests/test_svg2pptx_shapes.py -q` — must be green.
3. Run `pytest tests/test_snapshots.py --snapshot-capture` — captures new baselines under new Playwright Chromium.
4. Visually diff old vs new baselines (eyeball check); confirm only sub-pixel drift.

**Done when:** Files deleted; three CI-agnostic tests green; snapshot baselines captured and eyeballed.

---

### T9: Full gate pass + shipped-payload smoke

**Depends on:** T0-T8

**Touches:** (no new files — verification only)

**Tests:**
- `pytest tests/ -x -q` exits 0 (all gates green).
- Shipped-payload smoke: move `tests/`, `tools/`, `package.json` (already gone), `requirements-dev.txt` aside into a temp dir; run `pip install -r requirements.txt` (a fresh venv) + `playwright install chromium`; run each of the four scripts against a real HTML fixture; confirm all succeed with zero Node invocations; restore the moved dirs.
- `grep -r "subprocess.*['\"]node['\"]" scripts/` yields zero lines.

**Approach:**
1. Run `pytest tests/ -x -q`.
2. Run the shipped-payload smoke simulation.
3. Run the no-node grep.

**Done when:** All three checks pass.

---

### T10: Add CI job for browser-based render tests (optional)

**Depends on:** T9

**Touches:** .github/workflows/tests.yml

**Tests:**
- New CI job `render-scripts` has a step `playwright install chromium` before running render-script tests (goal-based: grep in workflow YAML).

**Approach:**
1. Add a new job `render-scripts` to `.github/workflows/tests.yml`:
   - `pip install -r requirements.txt`
   - `playwright install chromium`
   - Run smoke of the four scripts with a small fixture or run `pytest tests/test_snapshots.py`.
2. Leave the existing `mermaid-oracle` job unchanged.

**Done when:** Workflow YAML contains the new job and `playwright install chromium` step.

---

## Rollout

- **Delivery:** Big-bang PR; no flag. Reversible by reverting the PR (Chromium and npm were independent installs; reverting restores the prior Node requirement).
- **Infrastructure:** None — Playwright manages its own Chromium via `playwright install`. `PLAYWRIGHT_BROWSERS_PATH` / `PLAYWRIGHT_DOWNLOAD_HOST` env vars are available for constrained environments.
- **External-system integration:** Playwright 1.61.0 bundles its own Chromium; no external Chromium installation required.
- **Deployment sequencing:** T0 (bundle build) must precede T5 (html2svg migration); all other tasks depend on T1 (_browser.py). T8 (delete package.json) must come last. T10 is optional and independent.

## Risks

- **Sub-pixel snapshot drift** (T8): Playwright's Chromium version differs from Puppeteer's; snapshot baselines must be re-captured. Risk: human eyeball misses a non-trivial regression. Mitigation: eyeball the full diff before committing baselines.
- **In-page JS port regression** (T5): The pseudo-element materialisation and conic-gradient JS bodies are copied verbatim but run in a different browser version. Risk: a subtle rendering difference. Mitigation: snapshot baselines catch it.
- **Deck-root confinement move** (T5): Moving `fs.readFileSync` logic from Node JS to Python changes the confinement enforcement layer. Risk: a path-traversal edge case introduced. Mitigation: security reviewer pass on the diff.
- **`page.route` semantics** (T1-T5): Playwright's `page.route` is slightly different from Puppeteer's `setRequestInterception` — in Playwright, an unhandled route (no `continue_`/`abort`/`fulfill` called) will cause a page timeout. Mitigation: the handler always calls one of the three; verified by the test suite.

## Changelog

- 2026-07-19: initial plan
- 2026-07-19: post-adversarial-review-2 fixes — B1 (ImportError guard moved entirely into `_browser.py`; scripts use unguarded top-level imports + catch RuntimeError at call site); B2 (symlink-escape TDD case added to T1); B3 (bundle-recipe write added to T0 Touches/Tests/Approach); B4 (security-helper tests moved to pytest-collectable `tests/test_browser.py`); C5 (gallery Google Fonts rationale corrected — deliberate cosmetic change); C6 (build_pdf entry point corrected from `convert()` to `render()`)
