# Implementation Plan — Mermaid Current-Head Comparison Baseline

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `tools/compare_gallery.py`, `tools/generate_baseline.py`
   (new), `tests/test_compare_gallery.py`.
2. Done when: `pytest tests/` passes; `tools/generate_baseline.py` exits 0 on a
   clean checkout at commit 45055ac or later; the output directory contains all
   15 mmdc SVGs and an `index.html` with embedded provenance.
3. Not changing: `scripts/mermaid_render/` rendering logic, `tests/fidelity/`
   oracle JSON, any `.mmd` fixture files, `tests/fidelity/cases.toml`.

**Declined patterns:**
- Tempted to add a third rendering mode (debug); declining — spec defines
  exactly two lanes (fidelity, editorial) and a third adds untested surface.
- Tempted to move provenance JSON into a separate `provenance/` module;
  declining — all provenance logic already lives in `_collect_metadata` in
  `compare_gallery.py`; extend it in place rather than splitting the file.
- Tempted to use `git stash` to achieve a clean tree; declining — per project
  memory, `refs/stash` is shared across worktrees and stash pop can silently
  drop a sibling session's stash. Use `--allow-dirty` flag or explicit
  committed state instead.
- Tempted to reuse `tools/mermaid_fidelity/manifest.py` for per-fixture
  provenance records; declining — that module is the fidelity harness data
  model and has a different schema; keep gallery provenance self-contained.

**Resolve-vs-surface disposition:**
- "Should ELK fallback detection live in elk_adapter.py or compare_gallery.py?"
  → resolved at surface in `compare_gallery.py`; `elk_adapter.py` already
  raises `ElkUnavailable` on failure, so the gallery tool captures the
  exception and writes the fallback reason into provenance without touching the
  adapter.
- "Should `npm ci` be run inside `compare_gallery.py` or only in
  `generate_baseline.py`?" → resolved in `generate_baseline.py` only; running
  `npm ci` inside the main gallery tool would change behavior for non-baseline
  callers. The driver script handles dependency setup before invoking the tool.
- "How do we record the actual layout backend per fixture?" → `renderer_backend`
  on `ValidationResult` tracks the high-level backend (`native`, `legacy-dom`,
  `none`); the finer `elk` vs `python-fallback` distinction must be extracted
  by detecting whether `ElkUnavailable` was raised during the run. Extend the
  per-fixture provenance dict in `_build_gallery_into` to include
  `actual_layout_backend` alongside the existing `renderer_backend` field.

## Tasks

### Task 1: Extend per-fixture provenance record in compare_gallery.py
Depends on: none
Verification: TDD

**Tests:**
- `test_provenance_record_contains_required_keys`: call `_build_gallery` with a
  single mock `.mmd` file; inspect the returned per-fixture provenance list;
  assert keys `actual_layout_backend`, `fallback_reason`, `faithful`,
  `theme`, `width_hint`, `height_hint`, `output_width`, `output_height`,
  `output_viewbox`, `renderer_api` are all present.
- `test_elk_fallback_recorded`: monkeypatch layout dispatch to raise
  `ElkUnavailable("test reason")`; assert `actual_layout_backend` is
  `"python-fallback"` and `fallback_reason` is `"test reason"` in the fixture
  record.
- `test_elk_success_recorded`: normal render path; assert
  `actual_layout_backend` is `"elk"` and `fallback_reason` is `None`.

**Approach:**
- In `_build_gallery_into`, after calling `_render_ours`, determine the actual
  layout backend by inspecting whether `ElkUnavailable` was raised (wrap the
  render call to catch it, record reason, then re-render via Python fallback).
  Store `actual_layout_backend: "elk" | "python-fallback"` and
  `fallback_reason: str | None` in the per-fixture `provenance` dict.
- Add `renderer_api` (`"to_html"` — current default), `faithful` flag,
  `theme`, `width_hint`, `height_hint` to the per-fixture dict (already
  available as local variables or call kwargs).
- After the SVG or HTML is produced, parse the root `<svg>` element using the
  existing `_svg_dimensions` helper to extract `output_width`, `output_height`,
  `output_viewbox`; store in the per-fixture dict.
- Extend the per-run `metadata.json` with a new `per_fixture_provenance` key
  mapping fixture name to its provenance dict.

### Task 2: Add Node, elkjs, and Mermaid CLI version fields to _collect_metadata
Depends on: none
Verification: TDD

**Tests:**
- `test_collect_metadata_includes_node_version`: monkeypatch `subprocess.run`
  for `node --version`; assert `node_version` key is present in metadata.
- `test_collect_metadata_includes_elkjs_version`: monkeypatch `_find_elkjs` to
  return a path; monkeypatch package.json read; assert `elkjs_version` is
  present.
- `test_collect_metadata_includes_mmdc_version`: existing `mmdc_version` key
  already collected; assert it is present and non-empty when mmdc responds.
- `test_collect_metadata_graceful_on_missing_node`: monkeypatch `node --version`
  subprocess to raise `FileNotFoundError`; assert `node_version` is `None`
  (not an exception).

**Approach:**
- In `_collect_metadata`, add a `node --version` subprocess call (best-effort,
  same pattern as `mmdc --version`); store in `node_version`.
- Read `scripts/mermaid_render/layout/node_modules/elkjs/package.json` and
  extract the `version` field; store in `elkjs_version`. If the file is absent,
  store `None`.
- All three calls are wrapped in `try/except Exception` so missing binaries
  never abort metadata collection.

### Task 3: Add dirty-tree guard to compare_gallery.py
Depends on: none
Verification: TDD

**Tests:**
- `test_dirty_tree_exits_nonzero_without_flag`: monkeypatch `git status --short`
  to return `" M tools/compare_gallery.py\n"`; call `_build_gallery` without
  `allow_dirty=True`; assert `has_failures is True`.
- `test_dirty_tree_allowed_with_flag`: same monkeypatch; call with
  `allow_dirty=True`; assert generation proceeds (no immediate exit).
- `test_clean_tree_passes`: monkeypatch `git status --short` to return `""`;
  assert generation proceeds normally.

**Approach:**
- Add an `allow_dirty: bool = False` parameter to `_build_gallery` and
  `_build_gallery_into`.
- At the top of `_build_gallery_into`, call `git status --short` and check the
  output. If non-empty and `allow_dirty` is False, append an error to the
  provenance and set `has_failures = True`; return early.
- Wire `--allow-dirty` CLI flag through `argparse` to the `allow_dirty`
  parameter.

### Task 4: Add hard-fail guards for missing mmdc assets, source-hash mismatch, missing backend
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_missing_mmdc_asset_is_hard_fail`: after gallery build, remove one mmdc
  SVG from the output directory; call the post-build validation helper; assert
  `has_failures is True`.
- `test_source_hash_mismatch_is_hard_fail`: set `fixture_sha256` in metadata to
  a value different from the SHA-256 of the file on disk; assert `has_failures
  is True`.
- `test_missing_backend_field_is_hard_fail`: set `actual_layout_backend` to
  `""` in a fixture provenance record; assert `has_failures is True`.
- `test_elk_fallback_without_reason_is_hard_fail`: set
  `actual_layout_backend = "python-fallback"` and `fallback_reason = None` on
  a fixture whose `renderer_backend` indicates ELK was requested; assert
  `has_failures is True`.

**Approach:**
- After all fixtures are rendered in `_build_gallery_into`, run a
  `_validate_outputs` step that checks:
  1. Each of the 15 target fixtures has an `.svg` in `out_dir/mmdc/`.
  2. Each per-fixture provenance dict has a non-empty `actual_layout_backend`.
  3. If `actual_layout_backend == "python-fallback"`, `fallback_reason` is
     non-None and non-empty (a silent fallback is a hard fail).
  4. The SHA-256 of each source fixture file on disk matches the value stored
     in `fixture_sha256` (detects a dirty checkout that wasn't caught by
     the git-status guard).
- Any failing check appends an error string to a `failures` list; if
  `failures` is non-empty, set `has_failures = True`.

### Task 5: Add fidelity rendering lane to compare_gallery.py
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_fidelity_render_uses_faithful_true`: monkeypatch `mermaid_render.to_html`
  to capture kwargs; run `_render_fidelity`; assert `faithful=True` in the
  captured call.
- `test_fidelity_render_uses_neutral_theme`: assert `theme` kwarg is
  `"neutral"` (or the project's defined neutral theme constant) in the
  captured `to_html` call.
- `test_fidelity_lane_absent_inferred_icons`: mock render result string;
  assert the fidelity lane HTML does not contain any icon class or `<img>` tag
  that the gallery would inject editorially.
- `test_editorial_lane_uses_default_params`: run `_render_ours` (existing
  function); assert `faithful` kwarg is not passed or is `False`.

**Approach:**
- Add `_render_fidelity(src: str, width_hint: int = 0) -> tuple[str | None, str]`
  alongside the existing `_render_ours`. It calls `mermaid_render.to_html` with
  `faithful=True`, a neutral theme, and no auto-direction override.
- In `_build_gallery_into`, when `mode == "fidelity"`, use `_render_fidelity`;
  when `mode == "editorial"` or not set, use the existing `_render_ours`.
- Add a `--mode` argument to `argparse` accepting `fidelity | editorial | both`
  (default `both`). When `both`, generate two HTML sections in the same
  `index.html`.
- The fidelity lane's per-fixture provenance records `faithful=True`; the
  editorial lane records `faithful=False`.

### Task 6: Embed mmdc SVGs self-contained into the artifact
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_mmdc_svg_no_external_references`: after a gallery build with mocked mmdc
  output, parse each mmdc SVG in `out_dir/mmdc/`; assert no `href` or `src`
  attribute points to a path that does not exist inside `out_dir`.
- `test_mmdc_svg_inlined_in_html`: parse the generated `index.html`; for each
  fixture section, assert the mmdc pane contains an `<svg>` element directly
  (not an `<img src="...">` pointing outside the document) or a data-URI
  embedded `<img>`.

**Approach:**
- The current `_run_mmdc` writes SVG to `out_dir/mmdc/<name>.svg`. After
  writing, post-process the SVG to resolve any relative `href` or `xlink:href`
  attributes that reference paths outside `out_dir`.
- When embedding in `index.html`, inline the SVG string directly into the
  mmdc pane `<div>` (already done for the ours pane with `<iframe>`); wrap in
  a `<div class="mmdc-inline-svg">`.
- Add a helper `_resolve_svg_references(svg_str: str, svg_path: Path, out_dir: Path) -> str`
  that walks the element tree and converts relative references to data URIs or
  raises a `ValueError` for any reference it cannot resolve.

### Task 7: Show provenance manifest beside every fixture in gallery HTML
Depends on: Task 1, Task 5
Verification: TDD

**Tests:**
- `test_provenance_block_present_per_fixture`: parse the generated `index.html`;
  for each fixture section (identified by `id` anchor), assert a `<details>`
  element containing a `<pre>` with valid JSON is present.
- `test_provenance_json_includes_backend_field`: parse the JSON from one
  fixture's `<details>` block; assert `actual_layout_backend` key is present.

**Approach:**
- In the per-fixture HTML block rendered in `_build_gallery_into`, append a
  `<details><summary>provenance</summary><pre>{json}</pre></details>` block
  after the comparison grid.
- The JSON is the per-fixture provenance dict from Task 1 (not the full
  `metadata.json`), pretty-printed with `indent=2`.

### Task 8: Implement generate_baseline.py driver script
Depends on: Tasks 1–7
Verification: goal-based check

**Done when:** `python3 tools/generate_baseline.py` on a clean checkout at
commit 45055ac or later exits 0, writes `ppt-output/compare/index.html`, and
`ppt-output/compare/metadata.json` contains the full git SHA and all 15
fixture SHA-256 values.

**Approach:**
- Create `tools/generate_baseline.py` as a thin driver:
  1. Check `git rev-parse HEAD` and compare against the minimum recorded commit
     `45055ac827f4a7e68a01090e4468338aaed6bd7f`; abort if the tree is at an
     older commit or is dirty (unless `--allow-dirty` is passed through).
  2. Run `npm ci --prefix scripts/mermaid_render/layout` via subprocess; abort
     on nonzero exit.
  3. Build the fixture list: all 15 `.mmd` files from `tests/fixtures/` matching
     the scope list.
  4. Call `compare_gallery._build_gallery` with `mode="both"`, the 15 fixture
     paths, and `allow_dirty=False` (or `True` if `--allow-dirty` passed).
  5. Write `ppt-output/compare/metadata.json` (already done by `compare_gallery`
     via `_collect_metadata`).
  6. Print a summary line: fixture count, git SHA, whether ELK was available.
  7. Exit with the `has_failures` flag from `_build_gallery`.

### Task 9: Write/extend tests for ACs 1–15 in tests/test_compare_gallery.py
Depends on: Tasks 1–8
Verification: TDD

**Tests (new):**
- `test_ac1_html_header_contains_full_sha`: monkeypatch `git rev-parse HEAD` to
  return a 40-char SHA; parse the generated `index.html` `<header>` element;
  assert the full 40-char SHA appears.
- `test_ac2_dirty_tree_exits_nonzero`: covered by Task 3 tests.
- `test_ac3_provenance_all_keys_present`: verify all keys from AC3 list are in
  the per-fixture provenance dict.
- `test_ac4_all_15_fixtures_in_artifact`: build gallery with all 15 fixture
  paths; assert all 15 appear in `fixture_sha256` and in the HTML.
- `test_ac13_npm_ci_called_before_render`: monkeypatch `subprocess.run`; run
  `generate_baseline.py` main function; assert `npm ci` subprocess call
  precedes any `to_html` call.
- `test_ac14_reproducible_from_manifest`: build gallery twice with identical
  inputs; assert `fixture_sha256` dicts are identical across both runs
  (determinism check).

**Approach:**
- All tests use `unittest.mock.patch` for `subprocess.run`, `_run_mmdc`, and
  `mermaid_render.to_html`/`validate` so no browser, Node, or mmdc binary is
  required.
- Import `compare_gallery` via the existing `_import_gallery()` helper.
- Gate: `pytest tests/test_compare_gallery.py` must pass in the CI
  browser-free job.
