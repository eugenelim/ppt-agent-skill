# Spec: Mermaid Test Resource Control

**Status:** Shipped
**Mode:** full (multi-feature + structural change + unfamiliar territory)

## Objective

Prevent running Mermaid tests locally from creating a Python/Chromium process-launch storm. Preserve all test coverage and failure quality.

## Boundaries

**In scope:**
- pytest marker system for cost tiers (browser, snapshot, external_reference, isolation)
- BrowserSession context manager replacing per-render browser launches
- Snapshot deduplication: one render per (fixture, theme) pair, reused by both lanes
- Cross-process browser resource budget (OS flock) — test-specific; no lock in production code
- Removing lazy `playwright install chromium` from `get_browser()` and `BrowserSession.__enter__` — this is intentionally a production-visible behavior change per AC6; fail-fast with a clear error message is the correct contract
- SVG subprocess test moved to browser-free lane (native SVG backend, no Playwright needed for flowchart)
- mmdc version/integrity cached once per process in reference.py
- CI workflow comments + explicit marker opt-ins, preserving existing coverage
- AGENTS.md canonical commands

**Out of scope:**
- uv migration (separate follow-up plan at end)
- Production rendering pipeline logic (layout, compositing, output)
- New top-level directories
- Schema or API changes outside test infrastructure
- Installing mmdc in CI (differential oracle already skips cleanly when mmdc absent)

## Acceptance Criteria

- [x] AC1: `pytest -m "not browser and not snapshot and not external_reference and not isolation" tests/` collects zero tests that launch Chromium, mmdc, or renderer subprocesses (import-isolation isolation-marked subprocess may remain)
- [x] AC2: `pytest -m snapshot tests/test_snapshots.py` renders each supported (fixture, theme) pair exactly once per session and opens at most one Playwright browser per pytest session (no xdist for snapshot tier)
- [x] AC3: Concurrent `pytest -m snapshot` invocations are serialized by an OS advisory flock held for the snapshot session; interrupted processes release the lock automatically (verified by SIGINT simulation test). Scope: snapshot tier only — this was the storm source; non-snapshot browser tests do not acquire the shared flock.
- [x] AC4: `pytest -m "not external_reference" tests/test_oracle.py` does not invoke mmdc
- [x] AC5: mmdc version and integrity are calculated once per capture process (not once per case); verified by mock asserting subprocess.run call count
- [x] AC6: No test or render operation installs Chromium implicitly; RuntimeError raised immediately when Chromium executable is absent; all existing callers degrade correctly on this RuntimeError
- [x] AC7: `python -m mermaid_render svg` test (flowchart, native backend) runs in the browser-free lane using in-process helper
- [x] AC8: Resource regression tests: mock-based launch-count verification + one bounded real-Playwright test renders a fixture when Chromium is available (skips when absent)
- [x] AC9: CI jobs updated; existing per-job test selection preserved; no coverage lost; stale comments corrected
- [x] AC10: All pre-existing targeted tests pass (snapshot baselines match — HTML generation is unchanged; only browser launch path changes). Verified locally on macOS (darwin); pixel comparison skipped in CI (cross-platform pixel-exact comparison is unreliable).

## Testing Strategy

- Markers: `pytest --co -q -m "not browser and not snapshot and not external_reference and not isolation"` collects no browser/mmdc tests
- BrowserSession: mocked launch-count; real render skips when Playwright unavailable
- Snapshot: session fixture is lazy; single-fixture run opens 1 browser; full run opens 1 browser
- flock: SIGINT simulation; assert second process can acquire < 2s after SIGINT to first
- mmdc caching: monkeypatch + call count assertion; reset cache between tests
- SVG: `pytest tests/test_mermaid_render_cli.py::test_svg_stdout` passes without Playwright

## Assumptions

1. macOS/Linux only for flock (Windows: no-op — not a CI target here)
2. HTML generation in snapshot tests must use the exact same path as before: `mermaid_layout._dispatch(src, None, 800)` + `make_page(fragment, theme=theme)` — not `mermaid_render.to_html()` — to guarantee pixel-identical baselines
3. mmdc differential oracle skips cleanly in CI when mmdc binary is absent; no npm install step added
4. Snapshot tests do not use pytest-xdist (concurrency within one invocation); the flock only guards concurrent invocations

## Declined patterns

- Factory/registry for browser sessions — direct construction is fine for one session type
- Process-global browser singleton — the spec explicitly prohibits it
- Per-test-function lazy install — just remove the behavior; clear error message is better
- A separate `BrowserPool` class — BrowserSession wraps one browser; the flock is the budget control
- Adding xdist-safe locking inside the session cache — out of scope; snapshot tests run single-threaded
