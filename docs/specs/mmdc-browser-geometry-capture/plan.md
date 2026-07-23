# Implementation Plan — mmdc Browser Geometry Capture

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: new `tools/mermaid_fidelity/capture/` package (browser runner, extractor, cache, provenance); `tools/mermaid_fidelity/models.py` (add `ReferenceDiagram` and related types); `tools/mermaid_fidelity/compare/geometry.py` (consume `ReferenceDiagram`); test files under `tests/` (browser-gated).
2. Done when: `pytest tests/ -m "not browser"` passes; `pytest tests/ -m browser` passes in an environment with Playwright + Chromium + mmdc 11.15.0 installed; each in-scope fixture produces a `ReferenceDiagram` JSON record meeting its manifest minimums.
3. Not changing: the `OracleResult` contract (from item 1); renderer production code; fixture `.mmd` files; the non-browser parity test job.

**Declined patterns:**
- Tempted to use Puppeteer instead of Playwright; declining — Playwright is already in the dependency graph for other tests.
- Tempted to spawn one process per fixture; declining — the spec requires a single long-lived browser process for batching.
- Tempted to use screenshots as oracle input; declining — the spec explicitly prohibits this; only structured JSON records are oracle input.
- Tempted to do full coordinate normalization in the browser JavaScript; declining — do DOM extraction in the browser, coordinate normalization in Python where it can be unit-tested.

---

## Tasks

### Task 1: `ReferenceDiagram` and supporting types
Depends on: none
Verification: TDD

**Tests:**
- `test_reference_diagram_fields`: construct a `ReferenceDiagram` with all required fields; assert each field is accessible and has the correct type.
- `test_cardinality_end_values`: assert `CardinalityEnd.minimum` accepts `ZERO` and `ONE`; assert `CardinalityEnd.maximum` accepts `ONE` and `MANY`.
- `test_extractor_gap_in_diagram`: construct a `ReferenceDiagram` with one `ExtractorGap`; assert the field is present.

**Approach:**
- Add to `tools/mermaid_fidelity/models.py`:
  - `CardinalityEnd(minimum: Literal["ZERO","ONE"], maximum: Literal["ONE","MANY"])`.
  - `ExtractorGap(field: str, reason: str)`.
  - `ReferenceNode`, `ReferenceGroup`, `ReferenceEdge`, `ReferenceLabel`, `ReferenceMarker`.
  - `ReferenceProvenance` with all required version and fingerprint fields.
  - `ReferenceDiagram` frozen dataclass with all required collections and `provenance`.

---

### Task 2: Toolchain lockfile
Depends on: none
Verification: Goal-based check

**Done when:** a lockfile or constants module exists at `tools/mermaid_fidelity/capture/versions.py` (or equivalent) pinning Mermaid CLI 11.15.0, and its contents can be read by the provenance recorder.

**Approach:**
- Create `tools/mermaid_fidelity/capture/versions.py` with constants:
  `MERMAID_CLI_VERSION = "11.15.0"`, `NODE_MIN_VERSION`, `PLAYWRIGHT_MIN_VERSION`.
- Add a `detect_versions() -> dict[str, str]` function that shells out to `mmdc --version`, `node --version`, `npx playwright --version` and returns the detected values.
- CI lockfile check: assert detected Mermaid CLI version matches the pinned constant.

---

### Task 3: Batched browser runner
Depends on: Task 1, Task 2
Verification: Goal-based check

**Done when:** `from tools.mermaid_fidelity.capture.runner import BatchRunner; r = BatchRunner(); r.render_all(fixture_sources)` returns a list of raw SVG strings without spawning more than one browser process.

**Approach:**
- Create `tools/mermaid_fidelity/capture/runner.py`.
- `BatchRunner` opens one Playwright Chromium context; iterates fixtures; calls mmdc (or injects source into an iframe) to render SVG; collects raw SVG.
- On completion, closes the browser context.
- Gate with `@pytest.mark.browser` and `@pytest.mark.skipif(not _HAVE_PLAYWRIGHT, ...)`.

---

### Task 4: DOM/SVG extractor
Depends on: Task 1, Task 3
Verification: TDD

**Tests (unit, synthetic SVG):**
- `test_node_extraction`: supply SVG with two known nodes; assert `ReferenceDiagram.nodes` has correct IDs, labels, bounds.
- `test_edge_extraction_parallel`: supply SVG with two edges sharing `(src, dst)`; assert both appear with distinct normalized IDs.
- `test_class_marker_resolution`: supply SVG with a `<marker>` element for each canonical kind; assert correct `ReferenceMarker.kind`.
- `test_er_cardinality_parsing`: supply SVG with cardinality text elements; assert correct `CardinalityEnd` fields.
- `test_state_symbol_classification`: supply SVG with elements for each of the five state symbol kinds; assert `initial` (filled circle), `final` (concentric rings), `simple` (rounded rect without children), `composite` (rounded rect with children), and `composite-boundary` (fork/join bar) are each classified correctly (AC6).
- `test_state_symbol_extractor_gap`: supply SVG with a state symbol kind that cannot be unambiguously classified; assert the overall `ReferenceDiagram.status` is `EXTRACTOR_GAP`, not `PASS` (AC9).

**Approach:**
- Create `tools/mermaid_fidelity/capture/extractor.py`.
- `extract_diagram(svg_text: str, fixture_type: str) -> ReferenceDiagram`.
- Use `lxml` or stdlib `xml.etree.ElementTree` for SVG parsing (no browser dependency in this layer).
- Implement node, group, edge, label, marker, cardinality, state-symbol extraction using the SVG patterns documented in the spec.

---

### Task 5: Coordinate normalization
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_translate_transform`: supply a node with `transform="translate(10, 20)"`; assert extracted bounds shift by (10, 20).
- `test_viewbox_scaling`: supply SVG with `viewBox="0 0 200 100" width="400" height="200"`; assert all coordinates are scaled by 2.
- `test_nested_transforms`: supply three levels of `<g transform="translate(...)">` nesting; assert final coordinate is the composed translation.
- `test_deterministic_normalization`: call normalization twice on identical input; assert output is identical.

**Approach:**
- Add `normalize_coordinates(element, viewport) -> BoundingRect` to `extractor.py`.
- Implement transform composition: walk ancestors, compose translate/scale/matrix transforms.
- Apply viewBox scaling: compute `(width / viewBox_width, height / viewBox_height)` and multiply all coordinates.
- Strip page/body offsets if any.

---

### Task 6: Provenance recorder
Depends on: Task 2, Task 3
Verification: TDD

**Tests:**
- `test_provenance_has_required_fields`: call `record_provenance()`; assert all fields present.
- `test_provenance_includes_font_fingerprint`: assert `font_fingerprint` is a non-empty hex string.
- `test_provenance_mermaid_version_matches_lockfile`: assert detected Mermaid version equals the pinned constant.

**Approach:**
- Add `record_provenance(source_hash: str, fixture: str) -> ReferenceProvenance` to `tools/mermaid_fidelity/capture/provenance.py`.
- Shell out to version-detection calls from Task 2.
- Compute font fingerprint as `sha256` of the font file(s) used.
- Record platform from `platform.system()`.

---

### Task 7: Cache layer
Depends on: Tasks 4, 5, 6
Verification: TDD

**Tests:**
- `test_cache_hit_returns_same_record`: call capture twice with identical inputs; assert second call returns the cached record without re-rendering.
- `test_cache_invalidates_on_source_hash_change`: change source hash; assert the cache returns a fresh record.
- `test_cache_invalidates_on_version_change`: change Mermaid version string; assert cache miss.

**Approach:**
- Create `tools/mermaid_fidelity/capture/cache.py`.
- Cache key: `sha256(source_hash + mermaid_version + browser_version + font_fingerprint + render_config)`.
- Store records as JSON in a `.cache/mermaid_reference/` directory (gitignored).
- Serialize/deserialize `ReferenceDiagram` via `dataclasses.asdict` + `json`.

---

### Task 8: Integration and manifest validation
Depends on: Tasks 4, 5, 6, 7
Verification: Goal-based check (browser-gated)

**Done when:** `pytest tests/ -m browser -k "test_capture_all_fixtures"` passes in an environment with Playwright + mmdc 11.15.0; each fixture's record meets its manifest minimums from the oracle-contract manifest.

**Approach:**
- Add `tests/test_browser_capture.py` with `@pytest.mark.browser` mark.
- `test_capture_all_fixtures`: iterate in-scope fixtures, call the full capture pipeline, assert each `ReferenceDiagram` passes `validate_against_manifest(diagram, fixture_stem)`.
- `validate_against_manifest` uses the `FIXTURE_MINIMUMS` from `mermaid-oracle-runtime-unification`.
