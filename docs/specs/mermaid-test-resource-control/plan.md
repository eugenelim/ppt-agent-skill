# Plan: Mermaid Test Resource Control

**Status:** Done

## Task T1: Pytest markers in conftest.py
Mode: goal-based
Depends on: none

Approach:
- Add `pytest_configure(config)` to `tests/conftest.py` registering 4 markers:
  - `browser`: requires Playwright + Chromium; opt-in
  - `snapshot`: snapshot regression test (implies browser)
  - `external_reference`: requires mmdc binary
  - `isolation`: subprocess process-boundary test
- Annotate `--snapshot-capture` option registration with updated docstring
- Add a comment block documenting canonical tier commands

Done when: `pytest --co -q -m "not browser and not snapshot and not external_reference and not isolation" tests/test_snapshots.py` collects 0 tests; no marker unknown warnings

## Task T2: BrowserSession + remove lazy install (browser.py)
Mode: TDD
Depends on: T1

New class `BrowserSession` in `scripts/mermaid_render/browser.py`:
- `__enter__`: `sync_playwright().start()` + `chromium.launch(args=_LAUNCH_ARGS)` — raise RuntimeError immediately on failure (no install attempt)
- `render_to_png(html_path, scale=1.0, fullpage=False) -> bytes`: fresh `context = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=scale)`, fresh page with `emulate_media(media="screen")` + `_install_route(page)`, `goto("file://"+str(html_path), wait_until="networkidle", timeout=30000)`, `fonts.ready + imgs await` JS, screenshot; `page.close()` + `context.close()` in `finally`
- `__exit__`: `browser.close()` + `self._pw.stop()` wrapped in try/except

Change `get_browser()`: remove lazy `subprocess.run(playwright install chromium)` block; replace with `raise RuntimeError("Chromium not installed — run: playwright install chromium")` when "Executable doesn't exist". The "Executable doesn't exist" RuntimeError propagates cleanly through all existing callers (html2png.convert, svg.convert, build_pdf.render, gallery.take_screenshots) because they all catch RuntimeError and return False/non-zero (verified by existing tests/test_browser.py TestDegradationGuard tests which already cover this path).

Update `tests/test_browser.py`:
- Replace `test_lazy_install_triggered_on_missing_executable` with `test_fail_fast_on_missing_executable`: mock `chromium.launch` to raise "Executable doesn't exist"; assert RuntimeError raised; assert `subprocess.run` NOT called
- Add `test_browser_session_lifecycle`: mock sync_playwright; enter + exit BrowserSession; assert `chromium.launch` called once, `browser.close` called once
- Add `test_browser_session_page_closes_after_render_failure`: mock page.goto to raise; assert `page.close` and `context.close` still called

Tests (red-green):
1. Write failing tests for BrowserSession lifecycle and fail-fast behavior
2. Implement BrowserSession + remove lazy install
3. All tests green

## Task T3: Cross-process browser flock (browser_lock.py)
Mode: TDD
Depends on: none (parallel with T2)

New file `scripts/mermaid_render/browser_lock.py`:
```python
import contextlib, fcntl, os, tempfile, threading

_DEFAULT_LOCK_PATH = os.path.join(tempfile.gettempdir(), "mermaid-browser.lock")

@contextlib.contextmanager
def browser_budget(lock_path=None, timeout_msg_delay=0.5):
    """OS advisory flock limiting concurrent browser-heavy processes to 1.
    
    No-op on platforms without fcntl (Windows). Prints a waiting message
    if lock acquisition takes longer than timeout_msg_delay seconds.
    Released automatically on exit, exception, or SIGINT.
    """
    try:
        import fcntl as _fcntl
    except ImportError:
        yield; return
    
    path = lock_path or _DEFAULT_LOCK_PATH
    with open(path, "w") as fd:
        _msg_sent = False
        def _warn():
            nonlocal _msg_sent
            _msg_sent = True
            print(f"[mermaid-browser] waiting for browser resource lock ({path})", flush=True)
        timer = threading.Timer(timeout_msg_delay, _warn)
        timer.start()
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX)
        finally:
            timer.cancel()
        try:
            yield
        finally:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
```

Tests in new `tests/test_resource_contracts.py` (T3 portion):
- `test_lock_acquired_and_released`: enter browser_budget(); verify exit doesn't raise; verify lock path exists
- `test_lock_released_on_exception`: acquire + raise inside; assert second acquisition immediate (< 0.1s)
- `test_lock_noop_when_fcntl_unavailable`: `sys.modules["fcntl"] = None`; enter browser_budget; no error

## Task T4: Snapshot deduplication — lazy session cache (test_snapshots.py)
Mode: TDD
Depends on: T2, T3

Session-scoped fixture `_png_cache(tmp_path_factory)`:
1. Acquires `browser_budget()` lock for the browser session duration
2. Opens one `BrowserSession`
3. Returns a lazy getter callable `get_png(fixture_path, theme) -> Path | None`:
   - Checks a `dict[tuple[str,str], Path | None]` cache
   - On miss: renders using existing pattern `_dispatch(src, None, 800)` + `make_page(fragment, theme=theme)` (same imports from mermaid_layout — unchanged HTML generation guarantees baseline compatibility)
   - Writes HTML to `_PPT_OUT / f"{stem}-{theme}.html"`, calls `session.render_to_png(html_path, fullpage=True)`, writes PNG to `cache_dir / f"{stem}-{theme}.png"`, cleans up HTML
   - On ValueError from _dispatch: stores None
4. `yield get_png` (browser stays open for session)
5. After yield: BrowserSession and lock release

Rework 4 test functions to accept `_png_cache` fixture:
- `test_snapshot_light(fixture, request, _png_cache)`: get png from cache; call `_compare_or_capture`
- `test_snapshot_dark(fixture, request, _png_cache)`: same
- `test_fidelity_light(fixture, _png_cache)`: get png from cache; call `_fidelity_compare`
- `test_fidelity_dark(fixture, _png_cache)`: same
- Mark all 4 with `@pytest.mark.browser` + `@pytest.mark.snapshot`

Remove: `_render_to_png()` helper, `REAL_PYTHON`, `subprocess` import, `HTML2PNG` constant

Tests added to `tests/test_resource_contracts.py` (T4 portion):
- `test_snapshot_renders_each_pair_once`: use a counter fixture that wraps BrowserSession.render_to_png; run `pytest tests/test_snapshots.py -k "architecture-basic"` in a subprocess; assert render called exactly twice (light + dark)

Note on xdist: snapshot tests MUST NOT use `-n` option. The `_png_cache` fixture is session-scoped with no xdist-safe locking. Document this in conftest.py.

## Task T5: Oracle differential marker
Mode: goal-based
Depends on: T1

- Add `@pytest.mark.external_reference` to `test_topology_matches_reference` in `tests/test_oracle.py`
- Update the CI comment in `mermaid-oracle` job to correct stale "mermaidx" reference: differential mode requires `mmdc` npm CLI binary; it skips when absent

Done when: `pytest -m "not external_reference" tests/test_oracle.py --co -q | tail -3` shows only `test_no_dangling_edges` tests

## Task T6: Cache mmdc version/integrity (reference.py)
Mode: TDD
Depends on: none (parallel with T1-T5)

- Add module-level `_MMDC_VERSION_CACHE: str | None = None` and `_MMDC_INTEGRITY_CACHE: str | None = None` to `tests/fidelity/adapters/reference.py`
- Refactor `_mmdc_version()` and `_mmdc_integrity()` to check/populate cache on first call
- `ReferenceAdapter.identity()` and `_env_identity()` naturally benefit

Test in `tests/fidelity/test_phase1.py` or a new file:
- `test_mmdc_version_cached`: call `_mmdc_version()` twice with mock; assert `subprocess.run` called once; reset cache with monkeypatch after test

## Task T7: SVG test to browser-free lane
Mode: goal-based
Depends on: T1

- Add `test_svg_stdout` to `tests/test_mermaid_render_cli.py` using the existing in-process `_run()` helper:
  ```python
  def test_svg_stdout():  # no Playwright; native SVG backend
      r = _run("svg", "--source", "flowchart LR\n  A --> B")
      assert r.returncode == 0
      assert "<svg" in r.stdout
  ```
- Remove `test_svg_stdout` from `tests/test_mermaid_render_cli_playwright.py`
- Add `@pytest.mark.browser` + `@pytest.mark.isolation` to `test_png_output_file` in that file
- Update docstring of `test_mermaid_render_cli_playwright.py`: "svg uses native backend (no playwright for supported types); png requires playwright"
- Update CI `mermaid-render-guards` comment: note svg in-process test is browser-free

Done when: `pytest tests/test_mermaid_render_cli.py::test_svg_stdout -q` passes without playwright installed

## Task T8: Resource regression tests (test_resource_contracts.py)
Mode: TDD
Depends on: T2, T3

File `tests/test_resource_contracts.py`:

Mock-based:
- `test_fast_to_html_no_playwright_import`: subprocess; assert playwright modules empty after to_html (mirrors existing guard in test_mermaid_render_guards.py — verify this doesn't duplicate it)
- `test_browser_session_single_launch`: mock sync_playwright + chromium.launch; enter+exit BrowserSession; assert launch called once, close called once
- `test_browser_session_reuses_browser_across_renders`: two render_to_png calls; assert `browser.new_context` called twice, `chromium.launch` called once
- `test_browser_session_closes_context_on_render_failure`: mock page.goto raises; assert context.close called
- `test_no_playwright_install_on_missing_chromium`: mock "Executable doesn't exist"; assert RuntimeError; assert subprocess.run not called (fail-fast)

Real browser (skipped when playwright unavailable):
- `test_browser_session_real_lifecycle`: `pytest.importorskip("playwright")`; enter+exit BrowserSession with a real render of a one-liner fixture; assert PNG bytes non-empty; assert browser closed

SIGINT simulation (platform-specific):
- `test_flock_releases_after_sigint`: start subprocess that acquires browser_budget and sleeps; send SIGINT; assert main process can acquire lock within 2s

## Task T9: CI + documentation
Mode: goal-based
Depends on: T1-T8

- Update `.github/workflows/tests.yml`:
  - `mermaid-oracle` job comment: correct stale "mermaidx provides differential mode" claim — differential requires `mmdc` npm CLI; it skips cleanly when absent (no install step added)
  - `mermaid-render-guards` job comment: note svg in-process test is browser-free (native backend)
  - `render-scripts` job: NO marker filter on the explicit file list (markers are for deselection in broad `pytest tests/` runs, not explicit file lists)
- Update `AGENTS.md` Commands section with canonical tier commands:
  ```
  # Mermaid fast/default (no browser, no mmdc, no subprocess renders)
  pytest -m "not browser and not snapshot and not external_reference and not isolation" tests/

  # Mermaid browser (Playwright tests, no snapshots)
  pytest -m "browser and not snapshot" tests/

  # Mermaid snapshots (one browser session, all baselines)
  pytest -m snapshot tests/test_snapshots.py

  # Mermaid oracle — committed data only (no mmdc)
  pytest tests/test_oracle.py -m "not external_reference"

  # Mermaid oracle — live differential (requires mmdc npm CLI)
  pytest tests/test_oracle.py -m external_reference

  # Mermaid all (intentional)
  pytest tests/
  ```
