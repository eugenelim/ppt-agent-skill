# mmdc Browser Geometry Capture

Mode: full (structural change — new abstraction layer; new external dependencies; browser automation)

- **Status:** Draft

Merges: mmdc-geometry-capture, browser-geometry-capture, browser-probing, batch-mmdc

## Objective

The current reference adapter extracts topology information (node IDs, edge endpoints,
labels) from mmdc SVG output via regex, but produces no structured geometry — no bounding
rectangles, no route path samples, no coordinate-normalized records. This leaves the
oracle unable to compare spatial relationships: whether an endpoint lies on a visible
boundary, whether routes enter unrelated nodes, whether label bounds overlap markers.

This spec introduces a browser-based geometry capture pipeline that renders each in-scope
fixture through a pinned Mermaid CLI / Playwright / Chromium stack and extracts a
`ReferenceDiagram` JSON record from the live DOM. The pipeline runs in a single long-lived
browser process (not one process per fixture), records full provenance, and caches by
source-and-toolchain hash. The structured JSON — not screenshots — is the oracle input.

Depends on: `mermaid-oracle-runtime-unification` (the shared `OracleResult` contract must
exist before capture results can be fed to the oracle).

## Boundaries

**In scope:**
- Pin the reference toolchain: Mermaid CLI 11.15.0, Node version, Playwright version,
  Chromium revision, font family set — recorded in a lockfile or constants module.
- Batch fixture rendering in one long-lived Node/browser process.
- `ReferenceDiagram` dataclass covering: canvas_bounds, view_box, nodes, groups, edges,
  labels, markers, cardinalities, state_symbols, provenance.
- Per-node capture: normalized ID, label, shape/entity kind, bounding rectangle,
  transform chain, parent group.
- Per-group capture: ID, label, bounds, parent group, contained node IDs, contained group
  IDs.
- Per-edge capture: stable normalized edge ID, semantic source and destination, SVG path
  data, sampled path points, marker-start and marker-end references, stroke width, dash
  pattern, edge-label bounds.
- Class diagram marker resolution: hollow triangle, filled diamond, hollow diamond, open
  arrow, none.
- ER cardinality normalization: `CardinalityEnd(minimum=ZERO|ONE, maximum=ONE|MANY)`.
- State diagram symbol distinction: initial, final, simple, composite, composite-boundary
  transition endpoints.
- Coordinate normalization: resolve nested transforms, resolve viewBox scaling, remove
  page/body offsets, preserve subpixel values — all in one top-left coordinate system.
- Provenance record: Mermaid version, mmdc version, Node version, Playwright version,
  Chromium version, platform, font families, font fingerprints, fixture source hash.
- Typed extractor diagnostics for fields that cannot be captured.
- Cache keyed by: source hash, Mermaid version, browser version, font fingerprint, render
  configuration. Stored as structured JSON.
- Minimum-count validation: each record meets the manifest from `mermaid-oracle-runtime-
  unification`.
- Parallel-edge distinctness in extracted records.

**Out of scope:**
- Screenshots as oracle input (screenshots may be generated for debugging only).
- SVG rendering, Python layout compilation, or HTML output changes.
- Non-fixture ad-hoc diagrams.
- Windows platform support (Linux/macOS primary).

**Never:**
- Use a screenshot or PNG as the oracle input.
- Spawn one browser process per fixture (batch is required).
- Silently omit a field that cannot be captured — return a typed diagnostic.

## Acceptance Criteria

- [ ] AC1: Every in-scope fixture produces a `ReferenceDiagram` JSON record containing
  all required fields for that diagram type.
- [ ] AC2: Each record meets the minimum counts declared in the `mermaid-oracle-
  runtime-unification` manifest for that fixture.
- [ ] AC3: Coordinate normalization is deterministic: identical source, toolchain, and
  fonts produce numerically identical bounding rectangles across repeated clean runs.
- [ ] AC4: Parallel edges remain distinct in the extracted record — each has a unique
  normalized edge ID.
- [ ] AC5: Class diagram markers are resolved to canonical kinds (hollow triangle, filled
  diamond, hollow diamond, open arrow, none); ER cardinality ends are represented as
  `CardinalityEnd` with `minimum` and `maximum` fields.
- [ ] AC6: State diagram symbols are classified as initial, final, simple, composite, or
  composite-boundary transition endpoint.
- [ ] AC7: Provenance records tool versions and font fingerprints at capture time;
  records from different toolchain versions compare as distinct in the cache.
- [ ] AC8: The reference extraction process runs in a single batched browser session, not
  one session per fixture.
- [ ] AC9: Fields that cannot be captured produce a typed `ExtractorGap` diagnostic in
  the `ReferenceDiagram`; the overall result is `EXTRACTOR_GAP`, not `PASS`.
- [ ] AC10: The cache correctly invalidates when source hash, Mermaid version, browser
  version, or font fingerprint changes.
- [ ] AC11: `pytest tests/` continues to pass with zero regressions (capture pipeline
  tests are gated on browser availability).

## Testing Strategy

Browser-dependent tests are skipped when Playwright/Chromium is unavailable. All
structural and normalization tests are unit-testable with synthetic SVG input.

- **Coordinate normalization:** supply synthetic SVG with known nested transforms and
  viewBox; assert output bounding rectangles match expected top-left coordinates.
- **Transform chain composition:** parametrize over translate, scale, rotate transforms;
  assert composed result matches manual calculation.
- **Marker resolution (class):** supply synthetic SVG with known `<marker>` elements;
  assert canonical kind mapping is correct for each variant.
- **ER cardinality parsing:** supply synthetic SVG with cardinality glyphs; assert
  `CardinalityEnd` fields are correct.
- **State symbol classification:** supply synthetic SVG with filled-circle and
  concentric-ring elements; assert correct classification.
- **Cache invalidation:** construct two capture calls differing only in source hash;
  assert cache returns distinct records.
- **Typed diagnostics:** supply SVG where a field is missing; assert `ExtractorGap`
  appears in the record and status is `EXTRACTOR_GAP`.
- **Parallel-edge distinctness:** supply SVG with two edges sharing source and target;
  assert both appear with distinct IDs.
- **Integration (browser-gated):** render each in-scope fixture through the full pipeline;
  assert minimum counts from the manifest.
