# Mermaid Current-Head Comparison Baseline

Mode: full (structural change, multi-feature, new tooling surface)

- **Status:** Implementing

## Objective

Regenerate the Mermaid comparison gallery against a recorded, clean commit of
the main branch and lock every output to a machine-readable provenance manifest.
The goal is a reproducible artifact that a developer can re-derive from the
manifest alone — same commit, same fixture hashes, same dependency versions —
and get pixel-compatible outputs.

The gallery is produced by `tools/compare_gallery.py` and currently writes an
HTML artifact to `ppt-output/compare/`. This feature extends that tool with two
rendering modes (fidelity and editorial), a richer per-fixture provenance record
(renderer API, actual layout backend, fallback reason, versions, font families,
viewBox), hard-fail guards against silent ELK fallback and missing mmdc assets,
and a generation script that enforces a clean starting commit.

All 15 fixtures from the agreed scope list must appear in the baseline artifact.
The fidelity lane is the normative Mermaid parity lane: `faithful=True`, no
inferred icons, no inferred legend, no auto-direction, neutral styling. The
editorial lane uses normal project styling and is evaluated for presentation
quality but is not compared as Mermaid parity. The two lanes are written as
separate sections in the gallery HTML and may be generated independently.

## Boundaries

- **In scope:** `tools/compare_gallery.py`, a new `tools/generate_baseline.py`
  driver script, a new `tools/mermaid_fidelity/manifest.py`-adjacent provenance
  schema module (or inline in `compare_gallery.py`), and `tests/test_compare_gallery.py`.
- **Out of scope:** changes to `scripts/mermaid_render/` rendering logic,
  changes to `tests/fidelity/` cases or oracle JSON, any new fixture `.mmd`
  files, Playwright/browser imports outside the existing gallery tool, CI
  workflow changes.
- **Never:** silently represent a Python fallback result as an ELK result;
  generate the gallery from a dirty working tree without an explicit override
  flag; add inferred icons or legends to the fidelity lane; embed external
  network resources in the artifact.

## Acceptance Criteria

- [x] AC1: The gallery HTML header identifies the exact git SHA used for
  generation (full 40-char SHA, not abbreviated).
- [x] AC2: Generating from a dirty working tree exits nonzero unless
  `--allow-dirty` is explicitly passed.
- [x] AC3: The provenance manifest includes, per fixture: full git SHA,
  `git_dirty` flag, fixture source SHA-256, renderer API (`to_html` or
  `to_svg`), actual layout backend (`elk` or `python-fallback`), any backend
  fallback reason, `faithful` flag, `theme`, `width_hint`, `height_hint`,
  Python version, Node version, elkjs version, Mermaid CLI version, Playwright
  version, Chromium version, resolved font families, output width, output
  height, and output viewBox.
- [x] AC4: All 15 target fixtures are present in the generated artifact:
  `architecture-complex`, `class-relationships-all`, `er-cardinality-all`,
  `er-ecommerce`, `flowchart-all-shapes`, `flowchart-arrows-defs`,
  `flowchart-diamond-branch`, `flowchart-diamond-clipping`,
  `flowchart-empty-subgraph`, `flowchart-groups-complex`,
  `flowchart-inner-direction`, `flowchart-parallel-links`,
  `requirement-basic`, `statediagram-complex`, `statediagram-nested`.
- [x] AC5: The fidelity lane renders with `faithful=True`, no inferred icons,
  no inferred legend, no auto-direction, and neutral styling.
- [x] AC6: The editorial lane renders with normal project styling (existing
  compare_gallery defaults).
- [x] AC7: Generation fails when ELK silently falls back without logging a
  fallback reason — i.e., when a fixture records `renderer_backend` indicating
  ELK was expected but the actual layout backend in the manifest is
  `python-fallback` with no recorded reason.
- [x] AC8: Generation fails when any mmdc SVG asset is absent from the artifact
  at write time when mmdc was expected to have produced one (i.e., mmdc was
  invoked and returned success but no SVG was written).
- [x] AC9: Generation fails when the fixture source SHA-256 recorded at render
  time differs from the SHA-256 of the file on disk post-render (detects
  filesystem changes mid-run). Note: since source is read once and passed to
  both renderers, native↔mmdc SHA divergence is structurally impossible; the
  guard compares provenance vs disk instead.
- [x] AC10: Generation fails when any fixture does not record its actual layout
  backend (backend field is empty or absent in the per-fixture provenance).
- [x] AC11: Every mmdc SVG is inlined into the artifact HTML directly; relative
  `<image href>` references are replaced with data URIs.
- [x] AC12: The provenance manifest is displayed beside every fixture in the
  gallery HTML (collapsible detail block).
- [x] AC13: `npm ci --prefix scripts/mermaid_render/layout` is executed before
  any rendering attempt so the pinned elkjs dependency is always available.
- [ ] AC14: A developer can re-run `tools/generate_baseline.py` from the
  manifest's recorded git SHA on a clean checkout and obtain the same fixture
  SHA-256 values and backend assignments. (deferred: requires a real baseline
  run on a clean checkout; tooling is in place via `generate_baseline.py`)
- [x] AC15: `pytest tests/` passes with the new tests in
  `tests/test_compare_gallery.py` covering ACs 1–13.

## Testing Strategy

All new tests live in `tests/test_compare_gallery.py` and must run without a
browser or mmdc binary (using `unittest.mock` patches for `_run_mmdc`,
`_render_ours`, and subprocess calls). Each AC maps to at least one test case:

- Dirty-tree guard: monkeypatch `git status --short` to return a non-empty
  string; assert exit code is nonzero without `--allow-dirty`.
- Provenance completeness: call `_collect_metadata` with a known fixture list;
  assert all required keys are present per fixture.
- 15-fixture coverage: build gallery with the 15 target fixture names in scope;
  assert all 15 appear in `fixture_sha256` and in the HTML `id` anchors.
- Fidelity-lane parameters: capture `to_html` call kwargs; assert `faithful=True`
  and neutral theme.
- ELK-fallback hard fail: monkeypatch the per-fixture backend record to indicate
  ELK was used but provenance shows `python-fallback` with no reason; assert
  `has_failures is True`.
- Missing mmdc asset: patch `_run_mmdc` to return `(False, ...)` for one
  fixture; assert generation exits nonzero.
- Source hash mismatch: set fixture SHA-256 in native provenance to a different
  value than mmdc provenance; assert generation exits nonzero.
- Missing backend field: return a per-fixture record with `actual_layout_backend`
  empty; assert generation exits nonzero.
- mmdc self-containment: inspect the output directory after a mock gallery run;
  assert no SVG file contains a relative `href` or `src` pointing outside the
  output tree.
- Manifest display: parse the generated HTML; assert each fixture section
  contains a `<details>` block with provenance JSON.
