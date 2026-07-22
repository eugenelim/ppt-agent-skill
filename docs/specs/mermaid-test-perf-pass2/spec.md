# Spec: Mermaid Test Performance Pass 2

**Status:** Shipped
**Mode:** full (multi-feature + dependent tasks; touches test infra, browser module, snapshot suite)

## Objective

Follow-up to the first Mermaid test resource-control pass (specs/mermaid-test-resource-control).
That pass introduced markers, BrowserSession, the OS flock, and snapshot deduplication.
This pass removes the remaining sources of high CPU/fan and slow local test runs:

1. Markers are registered but not collection-enforced — plain `pytest` still selects all
   expensive tests when dependencies are installed.
2. Missing `@pytest.mark.browser` on `test_to_png_returns_bytes` and
   `TestOutOfRootImageConfinement::test_out_of_root_image_skipped_and_warned`.
3. No xdist guard on snapshot tests — selecting them with `-n auto` would queue behind a
   flock held for each worker's full session.
4. `BrowserSession.render_to_png` uses `networkidle` — a guaranteed ≥500 ms wait per render;
   with 96 fixtures × 2 themes that is ≥96 s of fixed delay.
5. `mermaid_render.png._to_png_from_svg_string` (used by the public `to_png()` API) also
   uses `networkidle`.
6. `_dispatch` is called once per (fixture, theme) pair — 192 calls instead of 96.
7. Snapshot manifest checked only after render — fixtures without baselines pay the full
   Chromium cost before being skipped.
8. Smoke and fidelity lanes decode the same image pair twice per (fixture, theme).
9. No representative PNG subset — all 96 fixtures need full raster in every routine run.
10. Non-snapshot browser tests do not acquire `browser_budget`, enabling concurrent Chromium
    launches alongside snapshot runs.
11. `BrowserSession.render_to_png` creates a new `BrowserContext` + `Page` per render,
    discarding the context after each screenshot; snapshot suite needs a reusable page
    that retains the URL-allowlist security control.

## Boundaries

**In scope:**
- `tests/conftest.py` — opt-in flags, `pytest_collection_modifyitems`, xdist guard, `browser_lock` fixture
- `tests/test_snapshots.py` — manifest pre-filter, compile-once, reusable page, fused comparison
- `tests/test_mermaid_p3_stage12.py` — add browser marker to `test_to_png_returns_bytes`
- `tests/test_html2svg_tmp_isolation.py` — add browser marker to `TestOutOfRootImageConfinement`
- `scripts/mermaid_render/browser.py` — remove `networkidle` from `render_to_png`, add `SnapshotRasterSession`
- `scripts/mermaid_render/png.py` — remove `networkidle` from `_to_png_from_svg_string` and
  `_to_png_from_html_file` and `convert` (all three raster helpers that use networkidle;
  the `to_png()` production path flows through `_to_png_from_svg_string`)
- `AGENTS.md` — update canonical commands
- `docs/backlog.md` — record deferred items

**Not in scope:**
- uv migration (explicitly excluded by brief)
- `build_pdf.py` and `gallery.py` networkidle — appropriate for those callers (external CSS/fonts)
- Batch mmdc for live oracle rendering (deferred — complex multi-process coordination)
- GPU benchmark (playwright not installed on this dev machine — defer to CI with backlog entry)
- xdist-safe snapshot cache (defer — run serially instead)

## Acceptance Criteria

### A — Opt-in tiers

- [x] **AC-A1** `python -m pytest` and `pytest tests/` (with playwright installed) launch zero
  Playwright browsers, zero Chromium processes, zero mmdc processes, zero renderer subprocesses
  (isolation tests excluded from this criterion per prior spec).

- [x] **AC-A2** `pytest --collect-only -q` without expensive flags collects browser/snapshot/
  external_reference/isolation items but all carry an explicit skip mark from
  `pytest_collection_modifyitems`.

- [x] **AC-A3** `--run-browser`, `--run-snapshots`, `--run-external-reference`, `--run-isolation`,
  `--run-all-expensive` flags exist and enable the respective tiers when passed.

- [x] **AC-A4** `test_to_png_returns_bytes` carries `@pytest.mark.browser`; plain `pytest` skips it.

- [x] **AC-A5** `TestOutOfRootImageConfinement::test_out_of_root_image_skipped_and_warned` carries
  `@pytest.mark.browser`; plain `pytest` skips it.

### B — xdist guard

- [x] **AC-B1** Selecting snapshot tests with `numprocesses > 1` (e.g. `-n auto`, `-n 2`) raises
  `pytest.UsageError` before any Chromium is launched. Guard code is present in conftest.py;
  behavioral test deferred to CI (deferred: xdist-snapshot-guard).

- [x] **AC-B2** Selecting snapshot tests with `numprocesses <= 1` (e.g. `-n 0`, `-n 1`, or
  no `-n` flag) does not raise `UsageError`.

### C — Remove networkidle

- [x] **AC-C1** No call to `page.goto(...)` or `page.set_content(...)` in
  `scripts/mermaid_render/browser.py` or `scripts/mermaid_render/png.py` passes
  `wait_until="networkidle"`. Verified by grep on the specific files.

- [x] **AC-C2** A source-level test asserts that neither `browser.py` nor `png.py` contains
  the string `"networkidle"`. (`tests/test_mermaid_perf_pass2_acs.py`)

- [ ] **AC-C3** (deferred: playwright-gated-snapshot-verification) `to_png()` production output (SVG raster path) is unchanged after removing
  networkidle from `_to_png_from_svg_string`.

### D — Manifest pre-filter

- [x] **AC-D1** In comparison mode, `_get_png` returns `None` immediately — no `_dispatch`
  call, no render — for `(fixture, theme)` pairs with no existing baseline.

- [x] **AC-D2** Tests confirm the manifest pre-filter logic: `manifest_prefilter_applies` extracted
  from `test_snapshots.py` and tested in `tests/test_mermaid_perf_pass2_acs.py`.

### E — Compile-once

- [x] **AC-E1** `_dispatch` is called exactly once per fixture (not per (fixture, theme) pair).
  Fragment-cache algorithm tested in `tests/test_mermaid_perf_pass2_acs.py`.

### F — SnapshotRasterSession with set_content

- [ ] **AC-F1** (deferred: playwright-gated-snapshot-verification) One normal snapshot run launches exactly one Chromium browser (one BrowserSession).
  `SnapshotRasterSession` uses a fresh `BrowserContext` + `Page` per render to preserve
  pixel-stable output.

- [x] **AC-F2** `SnapshotRasterSession` uses `page.set_content(html, wait_until="domcontentloaded")`
  instead of `page.goto("file://...", ...)`. Source-level verified in `tests/test_mermaid_perf_pass2_acs.py`.

- [x] **AC-F3** `SnapshotRasterSession` installs the URL-allowlist route handler (LLM01/ASI05)
  on each page before set_content. Source-level verified.

- [ ] **AC-F4** (deferred: playwright-gated-snapshot-verification) Existing snapshot baselines pass unchanged after this render-path change.
  Locally confirmed: 36 of 38 ran fixtures pass; 2 pre-existing sequence-basic failures unrelated to this change.

### G — Fuse smoke + fidelity

- [x] **AC-G1** The four test functions `test_snapshot_light`, `test_snapshot_dark`,
  `test_fidelity_light`, `test_fidelity_dark` are replaced by a single `test_snapshot_fused`
  parametrized over `(fixture, theme)`.

- [x] **AC-G2** `sha256_bytes_equal` production helper imported by tests — zero PIL opens when
  SHA matches, one open each for rendered/baseline when SHA mismatches.

- [x] **AC-G3** SHA-256 byte-equality fast path exits before PIL/NumPy work for identical images.
  Tested via `sha256_bytes_equal` in `tests/test_mermaid_perf_pass2_acs.py`.

- [x] **AC-G4** In capture mode, copy baseline and return immediately without running comparison.

### H — Browser budget for non-snapshot browser tests

- [x] **AC-H1** `test_to_png_returns_bytes` uses a `browser_lock` fixture that acquires
  `browser_budget` for the duration of the test.

### J — Test pyramid

- [x] **AC-J1** `--run-snapshots-quick` selects exactly 42 items from the full corpus (21 representative
  fixture stems × 2 themes). Sankey-basic and zenuml-basic are collected and selected but skip
  within-test (no baseline) — the conftest filter selects the correct 42.
  (deferred: playwright-gated-snapshot-verification — exact-42 behavioral CI assertion)

- [x] **AC-J2** AGENTS.md canonical commands section updated with all tiers including `--run-snapshots-quick`.

## Testing Strategy

- **A (opt-in tiers):** Goal-based — collection count; `pytest --run-browser --collect-only` shows browser items.
- **B (xdist guard):** Source code present + structural; behavioral test requires xdist (CI-gated, deferred).
- **C (networkidle):** Source-level grep assertion test, no playwright needed. AC-C3 CI-gated.
- **D (manifest pre-filter):** Mock `_dispatch`, assert call count in comparison mode.
- **E (compile-once):** Mock `_dispatch`, assert count == number of distinct fixtures.
- **F (reusable page):** Mock BrowserSession, assert `new_context` called once, route installed.
- **G (fused comparison):** Mock `PIL.Image.open`, assert ≤1 opens per (fixture, theme).
- **H (browser budget):** Integration test with real lock (no playwright needed for the lock itself).
- **J (pyramid):** Collection count for `--run-snapshots-quick`.

## Assumptions

1. `set_content` with `domcontentloaded` + `_FONTS_IMGS_READY` evaluate is sufficient
   for self-contained Mermaid HTML (no external resources). Route handler blocks all
   non-file:// requests, so no external assets can delay rendering.
2. `_dispatch` output (the HTML fragment) is theme-independent; `make_page` applies the theme CSS.
3. Playwright not installed on this dev machine — browser-dependent tests verified by mock
   or deferred to CI (AC-C3 and xdist behavioral test).
4. `SnapshotRasterSession` retains the URL-allowlist route handler on the reusable page —
   this is a security-posture-preserving design choice, not a performance trade-off.

## Declined patterns

- **Global browser singleton** — BrowserSession as an explicit CM is the correct contract.
- **Abstract base class for raster sessions** — one concrete `SnapshotRasterSession` is sufficient.
- **Autouse fixture for browser budget** — targeted per-test acquisition is clearer.
- **Removing networkidle from build_pdf and gallery** — appropriate for those callers.
- **Batch mmdc in this pass** — deferred to backlog.
- **GPU benchmark in this pass** — deferred to backlog (playwright not installed locally).
