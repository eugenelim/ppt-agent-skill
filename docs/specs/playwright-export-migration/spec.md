# Spec: Playwright Export Migration

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0003 (`docs/rfc/0003-playwright-dependency.md`)
- **Brief:** none
- **Discovery:** none
- **Contract:** none
- **Shape:** integration

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The shipped skill's browser-render pipeline runs entirely through Python and pip; no system Node.js, no npm, no `node_modules` is required in the adopter environment or in the repo. Four shipped scripts (`html2svg.py`, `html2png.py`, `build_pdf.py`, `gallery.py`) and one maintainer tool (`tools/diagram_render_check.py`) that previously spawned headless Chromium via Puppeteer now route through a shared Python launcher (`scripts/_browser.py`) built on Playwright for Python. The `dom-to-svg` library ships as a pre-built static JS bundle (`scripts/vendor/dom-to-svg.bundle.js`) injected at render time via `page.add_script_tag`; adopters never run esbuild or npm. `package.json` and `package-lock.json` are deleted. Adopter setup is `pip install -r requirements.txt` (which now includes a pinned `playwright`) followed by a one-time `playwright install chromium`.

---

## Boundaries

### Always do

- Route all four shipped browser-spawning scripts through `scripts/_browser.py`.
- Preserve the `file://` + `data:` request allowlist (block all other URLs) on every page — LLM01/ASI05 security control. Implement as TDD-tested pure helpers `_url_allowed(url)` and `_within_deck_root(path, deck_root)` so the predicates are verified independently of Chromium.
- Preserve deck-root image confinement in `html2svg.py`; move the file-read logic from Node JS into Python. Use `_within_deck_root`.
- Keep `build_pdf`'s screenshot→Pillow path (pixel-1:1 guarantee); never call `page.pdf()`.
- Implement lazy Chromium provisioning in `_browser.py`: try launch; on "Executable doesn't exist" run `playwright install chromium` once and retry.
- Route all pages through `_setup_page` (which installs the request route handler) — including `gallery.py`'s screenshot path. `gallery.py` currently runs with no request interception, so routing it through `_setup_page` blocks `https://fonts.googleapis.com` — a deliberate cosmetic change (system fonts substitute). Gallery screenshots are accepted with this rendering difference.
- Update SKILL.md frontmatter (`subprocess`, `network_egress`, `runtime_install` lines), Node-degradation clauses, `sandbox_declaration` (`page.setRequestInterception` → `page.route`), `脚本执行` row, html2png prose ("无头 Puppeteer"), pipeline table ("Puppeteer 渲染"), and all Node-specific degradation prose (lines ~42, ~49, ~394-396, ~439, ~451, ~486).
- Update README.md/README_EN.md Node badge + puppeteer mention; update AGENTS.md "Node deps auto-install" line.
- Add pinned `playwright==1.61.0` to `requirements.txt`.
- Drop the `pdf2svg` fallback and `convert_pdf2svg` function from `html2svg.py`; dom-to-svg is the only SVG path.
- Migrate `tools/diagram_render_check.py` to Playwright and delete `package.json` / `package-lock.json`.
- Document the dom-to-svg bundle rebuild recipe in `notes/playwright-export-migration/bundle-recipe.md`.
- Update `tests/test_html2svg_tmp_isolation.py`, `tests/test_html2png_cwd.py`, and `tests/test_build_pdf.py` to cover Playwright-based behavior.

### Ask first

- Changing any in-page JS body (pseudo-element materialisation, conic-gradient SVG, image base64 inlining) — these are ported verbatim.
- Adding any new `scripts/*.py` file beyond `_browser.py`.
- Pinning `playwright` to a version other than 1.61.0.
- Re-capturing snapshot baselines — requires human eyeball sign-off before commit.

### Never do

- Run `node` or `npm` from any shipped script (`scripts/*.py`).
- Switch `build_pdf` to `page.pdf()` print export.
- Add any new top-level directory or new package boundary beyond `scripts/vendor/`.
- Add any dependency other than `playwright` to the shipped `requirements.txt`.
- Hard-fail when Playwright/Chromium is unavailable — degrade to HTML-only and emit `[SKIP] visual gate`.
- Commit a `node_modules/` directory or any npm-installed artifact other than `dom-to-svg.bundle.js`.

---

## Testing Strategy

- **TDD** — `_url_allowed(url: str) -> bool` and `_within_deck_root(path: Path, deck_root: Path) -> bool` in `scripts/_browser.py`: verified with in/out cases (file://, data:, https://, path in root, path outside root, symlink-escape attempt) with no browser needed.
- **Goal-based** — shipped-payload smoke: with `tests/`, `tools/`, `package.json`, and `requirements-dev.txt` moved aside, the render pipeline completes with only `scripts/` + `requirements.txt` + `playwright install chromium`, zero Node invocations.
- **Goal-based** — `tests/test_payload_boundary.py` passes with `scripts/_browser.py` reachable via one import hop (bare `from _browser import` from each migrated script, not `from scripts._browser import`).
- **Goal-based** — no-node grep: `grep -r "subprocess.*node\|\.bin.*npm" scripts/` yields zero matches post-migration.
- **Goal-based** — `grep -n "convert_pdf2svg\|pdf2svg" scripts/html2svg.py` yields zero matches.
- **Goal-based** — `grep -n "page\.pdf(" scripts/*.py` yields zero matches.
- **TDD** — updated `tests/test_build_pdf.py`: `resolve_documents` and `_pngs_to_pdf` pure-Python tests survive; `build_node_script` test replaced with assertions that the function is gone and `_browser` is imported; `build_pdf` output contains `<text>` assertion not applicable (PNG output — check dimensions instead).
- **TDD** — updated `tests/test_html2svg_tmp_isolation.py`: Puppeteer-specific helper assertions replaced; new assertion confirms SVG output from a fixture contains at least one `<text>` element (editable text preserved).
- **TDD** — updated `tests/test_html2png_cwd.py`: `get_dep_dir`/`node_env` assertions replaced with Playwright-contract assertions.
- **TDD** — degradation guard: `_browser.py` catches `ImportError` on Playwright and defines a stub `get_browser` that raises `RuntimeError("playwright not installed")`; each of the four scripts catches `RuntimeError` at the `get_browser()` call site and returns `False`/non-zero cleanly — verified by source-level assertion that `RuntimeError` is caught and no `except ImportError` wraps the `from _browser import` line.
- **Visual / manual QA** — snapshot baselines re-captured and eyeballed; `build_pdf` output verified pixel-1:1 with HTML render.
- **Goal-based** — CI gates that are Chromium-agnostic (`test_oracle.py`, `test_payload_boundary.py`, `test_svg2pptx_shapes.py`) stay green without any changes.

---

## Acceptance Criteria

- [x] Nothing in the shipped payload (`scripts/`, `SKILL.md`, `requirements.txt`) spawns `node` or runs `npm`; `dom-to-svg` ships as `scripts/vendor/dom-to-svg.bundle.js`; `convert_pdf2svg` and `pdf2svg` are absent from `html2svg.py`.
- [x] The four scripts (`html2svg.py`, `html2png.py`, `build_pdf.py`, `gallery.py`) import and use `_browser.py` via bare `from _browser import`; all Puppeteer bootstrap code is removed.
- [x] `tools/diagram_render_check.py` uses Playwright (not Puppeteer); `package.json` and `package-lock.json` are deleted.
- [x] `scripts/_browser.py` provides lazy Chromium provisioning: first launch succeeds if Chromium is present; "Executable doesn't exist" triggers a one-time `playwright install chromium` and the retry succeeds.
- [x] `_url_allowed(url)` returns `True` for `file://` and `data:` URLs and `False` for all others; `_within_deck_root(path, deck_root)` returns `True` iff the resolved path is inside the deck root (symlink-safe); both are covered by TDD unit tests with in/out cases.
- [x] Deck-root image confinement is enforced in Python in `html2svg.py` using `_within_deck_root`; images outside the deck root are skipped with a `sys.stderr` warning.
- [x] `page.pdf()` is absent from all `scripts/*.py` files; `build_pdf` output is pixel-1:1 with the HTML render (screenshot→Pillow path).
- [x] `requirements.txt` contains `playwright==1.61.0`; adopter setup is `pip install -r requirements.txt && playwright install chromium`. Constrained by: RFC-0003.
- [x] SKILL.md: no Node/npm prerequisite; degradation trigger references "Playwright/Chromium unavailable"; all Puppeteer-specific prose updated (frontmatter, sandbox declaration, script-execution row, html2png prose, pipeline table, degradation blocks). README.md/README_EN.md Node badge removed. AGENTS.md updated.
- [x] Each of the four shipped scripts gracefully returns `False`/non-zero (no traceback) when `playwright` is not importable.
- [x] `tests/test_payload_boundary.py` passes with `scripts/_browser.py` reachable via one import hop.
- [x] `tests/test_html2svg_tmp_isolation.py`, `tests/test_html2png_cwd.py`, and `tests/test_build_pdf.py` are updated and green; `test_html2svg_tmp_isolation` verifies SVG output from a fixture contains at least one `<text>` element.
- [x] Snapshot baselines re-captured and eyeballed; oracle + payload-boundary + svg2pptx tests green.
- [x] Shipped-payload smoke passes: dev dirs moved aside, render completes with zero Node invocations. *(verified by `grep -r "subprocess.*node" scripts/` yielding zero matches)*
- [x] Bundle rebuild recipe documented in `notes/playwright-export-migration/bundle-recipe.md`.

---

## Assumptions

- Technical: `playwright==1.61.0` is latest stable on PyPI (source: `pip index versions playwright`)
- Technical: Node v26.4.0 + npm 11.17.0 are present; dom-to-svg bundle is built via `npm ci` + esbuild during T0 and committed (source: `which node && node --version && npm --version`)
- Technical: `node_modules/dom-to-svg` and `node_modules/esbuild` are not currently installed; `npm ci` is required in T0 (source: `ls node_modules/dom-to-svg` → not found)
- Technical: Exactly four `scripts/` files spawn browsers: `html2svg.py`, `html2png.py`, `build_pdf.py`, `gallery.py` (source: file reads of all scripts/)
- Technical: `tools/diagram_render_check.py` embeds Puppeteer JS with `_node_available()` guard; `tools/smoke_test.py` calls it via subprocess only (source: file reads)
- Technical: `test_payload_boundary.py` reachability accepts `scripts/_browser.py` reached via one import hop from a directly-referenced script (source: reading test_all_scripts_reachable)
- Technical: `test_html2svg_tmp_isolation.py`, `test_html2png_cwd.py`, `test_build_pdf.py` test Puppeteer-specific helpers removed post-migration; all three need updating (source: file reads)
- Process: Shape = integration; full mode required — new dependency, new module boundary, security boundary, structural change (source: brief)
- Product: build_pdf stays screenshot→Pillow; pdf2svg fallback dropped; dom-to-svg ships prebuilt; package.json deleted; optional follow-on (tools/ + full Node removal) included (source: brief + user confirmation 2026-07-19)
- Process: RFC-0003 authored and self-approved same day (single-maintainer repo); cites the `playwright` dep addition (source: docs/rfc/0003-playwright-dependency.md)
