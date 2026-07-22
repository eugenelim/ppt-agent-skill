# Plan: Mermaid Test Performance Pass 2

Spec: docs/specs/mermaid-test-perf-pass2/spec.md

## Tasks

---

### Task 1: Opt-in tiers + missing browser markers (Items A, H; AC-A1–A5, H)

**Depends on:** none

**Verification mode:** Goal-based (collection count)

**Tests:**
- `pytest --collect-only -q` without flags → all browser/snapshot/external_reference/isolation
  items carry a skip mark.
- `pytest --run-browser --collect-only -q` → browser items no longer skipped.
- `pytest --run-snapshots --collect-only -q` → snapshot items no longer skipped.

**Approach:**
1. In `tests/conftest.py`:
   - Add `--run-browser`, `--run-snapshots`, `--run-external-reference`, `--run-isolation`,
     `--run-all-expensive` to `pytest_addoption`.
   - Add `pytest_collection_modifyitems` hook that adds a skip mark to items whose
     marker set includes an expensive tier, unless the matching flag (or `--run-all-expensive`)
     was passed. Skip `snapshot` items first (before `browser`) because snapshot implies browser.
   - Add `browser_lock` fixture that acquires `browser_budget` via a context manager;
     function-scoped; used by non-snapshot browser tests.
2. Add `@pytest.mark.browser` to `test_mermaid_p3_stage12.py::test_to_png_returns_bytes`
   and add `browser_lock` as a parameter.
3. Add `@pytest.mark.browser` to
   `test_html2svg_tmp_isolation.py::TestOutOfRootImageConfinement::test_out_of_root_image_skipped_and_warned`.

**Done when:**
```
pytest --collect-only -q 2>&1 | grep -E "\[browser\]|\[snapshot\]" | grep -v "SKIP" | wc -l
```
returns 0 (no non-skipped expensive items in default mode).

---

### Task 2: xdist guard (Item B; AC-B1–B2)

**Depends on:** Task 1

**Verification mode:** Goal-based (source present + structural verification)

**Tests:**
- Structural: `xdist_worker_count` helper returns correct values for `None`, `0`, `1`, `2`,
  and `"auto"` inputs (unit test; no xdist required).

**Approach:**
In `tests/conftest.py`, add `_xdist_worker_count(config)` helper:
```python
def _xdist_worker_count(config) -> int:
    try:
        n = config.getoption("numprocesses", default=None)
    except (ValueError, AttributeError):
        return 0
    if n is None:
        return 0
    if str(n).lower() in ("auto", "logical"):
        import multiprocessing
        return multiprocessing.cpu_count()
    try:
        return int(n)
    except (ValueError, TypeError):
        return 0
```

In `pytest_collection_modifyitems`, after building the snapshot item list:
```python
if snapshot_items_selected and _xdist_worker_count(config) > 1:
    raise pytest.UsageError(
        "snapshot tests are not xdist-safe (one session cache, one browser). "
        "Run without -n or with -n 1:\n"
        "  pytest --run-snapshots tests/test_snapshots.py"
    )
```

`snapshot_items_selected` = snapshot items that were NOT just skip-marked by the opt-in
guard (i.e., `--run-snapshots` or `--run-all-expensive` was passed).

**Done when:** Helper unit test passes; behavioral test deferred to CI
(see `docs/backlog.md#xdist-snapshot-guard`).

---

### Task 3: Remove networkidle from mermaid raster modules (Item C; AC-C1–C2)

**Depends on:** none

**Verification mode:** TDD (source-level assertion)

**Tests:**
- `test_no_networkidle_in_raster_modules` — assert `"networkidle"` does not appear in
  `browser.py` or `png.py` (read source, check).

**Approach:**
1. `scripts/mermaid_render/browser.py :: BrowserSession.render_to_png` (line 164):
   - Change `wait_until="networkidle"` → `wait_until="domcontentloaded"`.
   - Docstring: remove "waits for networkidle".
2. `scripts/mermaid_render/png.py`:
   - `convert` (line 38): change `wait_until="networkidle"` → `wait_until="domcontentloaded"`.
   - `_to_png_from_html_file` (line 80): same change.
   - `_to_png_from_svg_string` (line 118): change `page.set_content(html, wait_until="networkidle")`
     → `page.set_content(html, wait_until="domcontentloaded")`.
   - For `convert` and `_to_png_from_html_file`, add `page.evaluate(_FONTS_IMGS_READY)` after the
     existing navigate+evaluate block (it already evaluates fonts/imgs separately; just update
     wait_until).
   - Import `_FONTS_IMGS_READY` from `.browser` in `png.py`.
   - For `_to_png_from_svg_string`, add `page.evaluate(_FONTS_IMGS_READY)` after `set_content`.
3. Update docstring in `png.py:convert` to remove reference to networkidle.

**Note:** `build_pdf.py` and `gallery.py` retain `networkidle` — appropriate there.

**Done when:**
```
grep -n "networkidle" scripts/mermaid_render/browser.py scripts/mermaid_render/png.py
```
returns nothing. Source assertion test passes.

---

### Task 4: SnapshotRasterSession in browser.py (Item F; AC-F1–F3)

**Depends on:** Task 3

**Verification mode:** TDD

**Tests:**
- Mock BrowserSession: one `SnapshotRasterSession` renders N HTML strings; assert `new_context`
  called once, `set_content` called N times.
- Assert URL-allowlist route installed on the reusable page (mock route assertion).
- Exception test: `set_content` raises → page recreated via `_recreate_page`, exception propagates.

**Approach:**
In `scripts/mermaid_render/browser.py`, add after `BrowserSession`:

```python
class SnapshotRasterSession:
    """Reusable raster session for snapshot tests: one context+page, set_content per render.

    Preserves the URL-allowlist route (LLM01/ASI05) on the reusable page.
    Use inside a BrowserSession context (shares its Browser instance).
    """

    def __init__(self, browser: "Browser") -> None:
        self._browser = browser
        self._context = None
        self._page = None

    def _ensure_page(self) -> None:
        if self._page is not None:
            return
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1.0,
        )
        self._page = self._context.new_page()
        self._page.emulate_media(media="screen")
        _install_route(self._page)  # LLM01/ASI05 preserved

    def _recreate_page(self) -> None:
        for obj in (self._page, self._context):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        self._page = None
        self._context = None

    def render_html(self, html: str) -> bytes:
        """Render an HTML string to PNG bytes via set_content (no navigation)."""
        self._ensure_page()
        try:
            self._page.set_content(html, wait_until="domcontentloaded")
            self._page.evaluate(_FONTS_IMGS_READY)
            return self._page.screenshot(type="png", full_page=True)
        except Exception:
            self._recreate_page()
            raise

    def close(self) -> None:
        self._recreate_page()
```

**Done when:** Mock tests for one-context, route-installed, and exception-recreate pass.

---

### Task 5: Manifest pre-filter + compile-once in test_snapshots.py (Items D, E; AC-D1–D2, E1)

**Depends on:** none

**Verification mode:** TDD

**Tests:**
- Mock `_dispatch`: in comparison mode, `_get_png` called for fixture with no baseline →
  assert `_dispatch` not called.
- Mock `_dispatch`: `_get_png` called for same fixture with themes "light" then "dark" →
  assert `_dispatch` called exactly once.

**Approach:**
Refactor `_png_cache` in `test_snapshots.py`:

1. Build baseline manifest at fixture entry:
   ```python
   _baseline_manifest: frozenset[tuple[str, str]] = frozenset(
       (path.stem, "light") for path in SNAPSHOTS_LIGHT_DIR.glob("*.png")
   ) | frozenset(
       (path.stem, "dark") for path in SNAPSHOTS_DARK_DIR.glob("*.png")
   )
   ```
   Or pass `capture` bool into fixture.

2. Add `_fragment_cache: dict[str, str | None]` alongside `_cache`.

3. Rewrite `_get_png`:
   ```python
   def _get_png(fixture_path: Path, theme: str) -> "Path | None":
       key = (fixture_path.stem, theme)
       if key in _cache:
           return _cache[key]

       # Comparison mode: skip pairs with no baseline
       if not capture and key not in _baseline_manifest:
           _cache[key] = None
           return None

       # Compile once per fixture
       stem = fixture_path.stem
       if stem not in _fragment_cache:
           src = fixture_path.read_text()
           try:
               _fragment_cache[stem] = _dispatch(src, None, 800)
           except ValueError:
               _fragment_cache[stem] = None
       
       fragment = _fragment_cache[stem]
       if fragment is None:
           _cache[key] = None
           return None
       
       html = make_page(fragment, theme=theme)
       png_bytes = session.render_html(html)
       png_path = cache_dir / f"{stem}-{theme}.png"
       png_path.write_bytes(png_bytes)
       _cache[key] = png_path
       return png_path
   ```

4. `capture` is derived from `request.config.getoption("--snapshot-capture")` at fixture
   entry (the `_png_cache` fixture already has access to request via `tmp_path_factory`; pass
   it via closure).

**Done when:** Mock tests for manifest-filter and compile-once pass.

---

### Task 6: Update _png_cache to use SnapshotRasterSession (Item F integration)

**Depends on:** Tasks 4, 5

**Verification mode:** Goal-based

**Approach:**
In `test_snapshots.py::_png_cache`:
1. Import `SnapshotRasterSession` from `mermaid_render.browser`.
2. Replace the `BrowserSession` block:
   ```python
   with browser_budget():
       with BrowserSession() as bs:
           session = SnapshotRasterSession(bs._browser)
           try:
               yield _get_png
           finally:
               session.close()
   ```
3. Remove `html_path.write_text(...)` and `html_path.unlink(missing_ok=True)` —
   HTML is passed directly to `session.render_html(html)` without disk I/O.
4. Remove the `_PPT_OUT` temp file write (was writing HTML for debugging; no longer needed).

**Done when:** The snapshot fixture uses `render_html` instead of `render_to_png`.

---

### Task 7: Fuse smoke + fidelity comparison (Item G; AC-G1–G4)

**Depends on:** Tasks 5, 6

**Verification mode:** TDD

**Tests:**
- Mock `PIL.Image.open`: called at most once per (fixture, theme); zero times on SHA-match.
- Capture mode: assert baseline file written, no comparison run.
- Failure message test: canvas size mismatch → structured failure string.

**Approach:**
Replace `test_snapshot_light`, `test_snapshot_dark`, `test_fidelity_light`, `test_fidelity_dark`
with one function:

```python
@pytest.mark.browser
@pytest.mark.snapshot
@pytest.mark.parametrize(
    "fixture,theme",
    [(f, t) for f in _FIXTURES for t in ("light", "dark")],
    ids=lambda x: f"{x.stem if hasattr(x,'stem') else x}",
)
def test_snapshot_fused(fixture, theme, _png_cache, request):
    capture = request.config.getoption("--snapshot-capture")
    baseline_dir = SNAPSHOTS_LIGHT_DIR if theme == "light" else SNAPSHOTS_DARK_DIR
    baseline = baseline_dir / (fixture.stem + ".png")
    rendered = _png_cache(fixture, theme)

    if rendered is None:
        pytest.skip(f"{fixture.stem}: unsupported diagram type")

    if capture:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(rendered, baseline)
        return

    if not baseline.exists():
        pytest.skip(f"no baseline for {fixture.stem}[{theme}]")

    rendered_bytes = rendered.read_bytes()
    baseline_bytes = baseline.read_bytes()

    # SHA-256 fast path: identical bytes → no image decode needed
    import hashlib
    if hashlib.sha256(rendered_bytes).digest() == hashlib.sha256(baseline_bytes).digest():
        return

    # Open both images once
    from PIL import Image, ImageChops
    import numpy as np
    img_new = Image.open(rendered).convert("RGB")
    img_base = Image.open(baseline).convert("RGB")

    failures: list[str] = []
    # Canvas, content bounds, pixel diff, smoke-resize checks...
    _collect_comparison_failures(img_new, img_base, failures, fixture.stem + f"[{theme}]")

    assert not failures, "\n".join(failures)
```

Extract `_collect_comparison_failures` from the existing helpers. The helper runs:
1. Canvas width / height check
2. Content bounds (±16 px)
3. Pixel diff at original size (0.5% threshold)
4. Smoke resize-tolerant diff (0.5% threshold after LANCZOS resize)

**Done when:** Collection shows 4 old test names gone, `test_snapshot_fused` present;
mock tests pass.

---

### Task 8: Update AGENTS.md and representative tier (Items A, J; AC-J1–J2)

**Depends on:** Tasks 1, 7

**Verification mode:** Goal-based

**Approach:**
1. In `tests/conftest.py`, add `--run-snapshots-quick` to `pytest_addoption`.
2. Define `_REPRESENTATIVE_STEMS` in `tests/test_snapshots.py`:
   ```python
   _REPRESENTATIVE_STEMS: frozenset[str] = frozenset({
       "architecture-basic", "block-basic", "c4-basic",
       "class-basic", "er-basic", "flowchart-arrows-defs",
       "gantt-basic", "gitgraph-basic", "journey-basic",
       "kanban-basic", "mindmap-basic", "packet-basic",
       "pie-basic", "quadrant-basic", "requirement-basic",
       "sankey-basic", "sequence-basic", "statediagram-basic",
       "timeline-basic", "xychart-basic", "zenuml-basic",
   })  # 21 stems, one per diagram family
   ```
3. In `pytest_collection_modifyitems`, when `--run-snapshots-quick`: select only snapshot items
   whose fixture stem is in `_REPRESENTATIVE_STEMS`; skip all others.
4. Update AGENTS.md "Mermaid test tiers" section.

**Done when:** `pytest --run-snapshots-quick --collect-only -q` shows exactly 42 items.

---

### Task 9: Add regression test for tier enforcement (AC-A1)

**Depends on:** Task 1

**Verification mode:** TDD

**Tests:**
Add `tests/test_conftest_tier_enforcement.py`:
- `test_default_tier_skips_all_browser_snapshot`: run `pytest --collect-only -q`
  programmatically (or via subprocess); count non-skipped browser/snapshot/
  external_reference/isolation items → must be 0.

**Done when:** Test passes without playwright.

---

### Task 10: Add backlog entries and update docs/backlog.md

**Depends on:** none (can be done any time before ship)

**Verification mode:** Goal-based

**Approach:**
Add three entries to `docs/backlog.md` under `## mermaid-test-perf-pass2`:
1. `### batch-mmdc` — batch live reference mmdc invocations
2. `### gpu-benchmark` — benchmark --disable-gpu vs without on CI
3. `### xdist-snapshot-guard` — behavioral test for snapshot xdist guard (requires
   pytest-xdist; currently not installed)

---

## Deferred (to backlog)

- Batch mmdc for live oracle rendering → `docs/backlog.md#batch-mmdc`
- GPU benchmark → `docs/backlog.md#gpu-benchmark`
- xdist behavioral guard test → `docs/backlog.md#xdist-snapshot-guard`
