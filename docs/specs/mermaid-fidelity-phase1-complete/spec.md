# Spec: Mermaid Fidelity Phase 1 — Complete End-to-End Harness

**Mode: full (multi-feature, structural change, dependent tasks, unfamiliar territory)**

**Status:** Implementing

**Constrained by:** source brief `.context/attachments/XL7Rq2/pasted_text_2026-07-21_16-53-49.txt`

## Objective

Turn the existing Phase 1 fidelity scaffolding (`tools/mermaid_fidelity/`,
`tests/fidelity/`) into a working, deterministic end-to-end compatibility
benchmark that exercises the repository's current public native SVG path
(`scripts/mermaid_render/ → mermaid_render.to_svg(source)`), compares it
against a committed Mermaid reference oracle, and gates CI on parse,
semantic, strict relative-layout, and quality failures.

Source brief: `.context/attachments/XL7Rq2/pasted_text_2026-07-21_16-53-49.txt`

## Boundaries

**Always do:**
- Fix pre-existing `NodeLayout.parent_group_id` AttributeError in `_renderer.py:1667`
- Add `RELATIVE_LAYOUT_MISMATCH`, `STALE_ORACLE`, `INVALID_MANIFEST` to `ComparisonStatus` enum and re-map `runner._compare` to emit them
- Make `run.py` delegate to `tools/mermaid_fidelity/cli.py` `build_parser()` / `cmd_*` (thin runner pattern); do not re-implement CLI logic in run.py
- Create `tests/fidelity/adapters/native_svg.py` (`NativeSvgAdapter`) calling `to_svg()`
- Rename `NativeAdapter` → `NativeHtmlAdapter` (secondary consistency lane)
- Fix `runner._deserialize_observation` to reconstruct geometry/quality from dict (not hardcode `None`)
- Add semantic `data-*` attributes to native SVG output
- Capture all 24 oracle observations; commit after manual inspection
- Extend existing `fidelity-phase1` CI job (browser-free) for the full `run`/`validate`/`determinism` gate

**Ask first (irreversible or value-originating):**
- Committing 24 oracle JSON files to `oracle/mermaid-11.15.0-neutral/cases/` — confirm each is manually inspected before commit
- Mutating `.github/workflows/tests.yml` — confirm job selection before editing

**Never do:**
- Add implementation to `scripts/mermaid_layout/` (shim only)
- Make `scripts/mermaid_render/` depend on `mermaid_fidelity`
- Move or duplicate existing Mermaid fixture files
- Add PyPI packaging or release automation
- Add a second Mermaid reference version, version ranges, or automatic upstream harvesting
- Use pixel-perfect screenshot gating or raw SVG DOM equality
- Re-implement CLI logic inline in `run.py` that already exists in `tools/mermaid_fidelity/cli.py`

**Ownership rules:**
- `scripts/mermaid_render/` — active renderer; fidelity must not depend on it
- `tools/mermaid_fidelity/` — reusable core; no repo-specific imports, no sys.path mutation
- `tests/fidelity/` — repo-specific adapters, manifests, oracle, tests

## Acceptance Criteria

### Checkpoint 1 — Real native SVG renderer + execution repair
- [ ] `ComparisonStatus` enum includes `RELATIVE_LAYOUT_MISMATCH`, `STALE_ORACLE`, `INVALID_MANIFEST`; runner emits them correctly (missing oracle → `STALE_ORACLE`; layout failure → `RELATIVE_LAYOUT_MISMATCH`)
- [ ] `run.py` delegates to `tools/mermaid_fidelity/cli.py` `build_parser()`/`cmd_run`/`cmd_capture_reference`/`cmd_determinism`/`cmd_validate`; does not duplicate CLI logic
- [ ] `runner._deserialize_observation` (and helpers `_deserialize_semantic`, `_deserialize_geometry`, `_deserialize_quality`) reconstructs all fields from loaded JSON dict — no `geometry=None` / `quality=None` placeholder
- [ ] `tests/fidelity/adapters/native_svg.py` exists and calls `to_svg()` (not `to_html()`)
- [ ] `NativeHtmlAdapter` in `adapters/native.py` is clearly marked secondary; not the authoritative target
- [ ] `run.py run --case flowchart.groups.complex --report-dir <dir>` succeeds end-to-end (exit 0)
- [ ] `run.py validate` exits 0
- [ ] `run.py capture-reference --output <dir>` refuses to overwrite existing files without `--force`
- [ ] `run.py capture-reference --output <dir> --force` overwrites atomically
- [ ] JSON round-trip: `loads(dumps(obs)) == obs` for all Observation fields
- [ ] New semantic SVG attributes (`data-semantic-id`, `data-kind`, `data-label`, `data-shape`, `data-parent-id`, `data-order` on nodes; `data-src`, `data-dst`, `data-arrow`, `data-relation-id` on edges; `data-group-id`, `data-group-label` on groups) present on native SVG output
- [ ] Stripping only the new data attributes produces identical visual geometry
- [ ] Pre-existing `NodeLayout.parent_group_id` AttributeError is fixed (all 20 previously-failing to_svg tests pass)
- [ ] New focused serializer tests for every new SVG attribute

### Checkpoint 2 — Reproducible Mermaid reference oracle
- [ ] All 24 cases have committed JSON observations under `oracle/mermaid-11.15.0-neutral/cases/`
- [ ] Environment identity in `environment.json` reflects actual probed versions (not hardcoded)
- [ ] `run.py validate` checks: all manifest cases have oracle file; no unexpected oracle files; all files use expected schema_version; all files use same reference identity; no strict field has unresolved EXTRACTOR_GAP; every source hash matches current fixture
- [ ] Source hash in each oracle file matches the corresponding fixture file
- [ ] `capture-reference` leaves oracle intact after interrupted/failed capture (atomic write)
- [ ] Reference adapter extracts flowchart: direction, node IDs, labels, shapes, edges, multiplicity, subgraphs
- [ ] Reference adapter extracts sequence: actors, messages, order, arrow types, activations, notes, blocks
- [ ] Reference adapter extracts architecture: services, groups, containment, connections
- [ ] Reference adapter extracts ER: entities, relationships, cardinality, identifying state

### Checkpoint 3 — Trustworthy comparisons
- [ ] `flowchart.parallel.links` regression test verifies parallel edges are not collapsed
- [ ] Missing strict data surfaces as `EXTRACTOR_GAP` not silent pass
- [ ] All comparison fields implemented (entity ID/kind/label/shape/parent/order; relation multiplicity/source/target/label/arrow/order; group existence/membership/containment; ordered event kind/source/target/order)
- [ ] Relation geometry survives serialization and normalization
- [ ] Native quality checks detect: clipped text, content outside viewBox, zero-area objects, substantial unrelated overlap, group containment violations, detached endpoints
- [ ] Scored metrics reported independently (not composited)
- [ ] Style-only mutations (palette, shadow) do not produce semantic failures
- [ ] All 19+ mutation tests pass (covering deleted/reversed relation, phantom entity, label change, shape change, group re-parent, parallel edge count, sequence order, arrow type, ER cardinality, identifying state, containment escape, overlap, detached endpoint, direction, crossing, clipping, palette, shadow, scored-only change)
- [ ] `run.py validate` fails on unknown checks, duplicates, unsupported strict checks

### Checkpoint 4 — CI and determinism
- [ ] `python3 tests/fidelity/run.py validate` exits 0
- [ ] `python3 tests/fidelity/run.py run --report-dir tests/fidelity/reports/local` runs all 24 cases, exits 0 or 1 based on hard failures only
- [ ] `python3 tests/fidelity/run.py determinism --runs 3 --report-dir tests/fidelity/reports/determinism` exits 0 for stable cases
- [ ] Existing `fidelity-phase1` browser-free CI job extended to also run `validate`, `run --report-dir tests/fidelity/reports/ci`, `determinism --runs 3`; artifacts uploaded always
- [ ] CI does not re-capture reference (loads committed oracle JSON)
- [ ] CI fails on PARSE_MISMATCH/SEMANTIC_MISMATCH/RELATIVE_LAYOUT_MISMATCH/QUALITY_FAILURE/EXTRACTOR_GAP/STALE_ORACLE/INVALID_MANIFEST/NONDETERMINISTIC/INTERNAL_ERROR; not on scored metrics alone
- [ ] Scored continuous metrics alone do not produce nonzero exit
- [ ] `tools/mermaid_fidelity/` passes isolation tests (no scripts/tests/mermaid_render imports, no sys.path mutation, subprocess import test, Playwright not loaded on base import, no hardcoded fixtures paths)
- [ ] All pre-existing repository tests still pass
- [ ] `tests/fidelity/README.md` updated per spec

## Testing Strategy

Verification modes per task:
- T0, T4: TDD (unit tests for new attributes and NodeLayout fix)
- T0a: TDD (status enum + gating set tests)
- T0b: TDD (deserializer round-trip tests)
- T0c: goal-based (CLI delegation commands succeed)
- T2, T3: goal-based (adapter wiring and CLI commands succeed)
- T5, T6: TDD (serialization round-trip, capture-reference overwrite)
- T7: goal-based (vertical slice end-to-end smoke)
- T8: goal-based (probe environment versions, check environment.json)
- T9–T11: goal-based (reference adapter extracts correct fields per family)
- T12: goal-based (capture all 24 cases, manual inspection)
- T13–T19: TDD (comparison logic, geometry, quality, mutation tests)
- T20–T21: goal-based (full local run + determinism run succeed)
- T22: goal-based (CI YAML updated, jobs configured correctly)
- T23: TDD (boundary isolation tests)
- T24: goal-based (README updated with correct content)

New test files:
- `tests/fidelity/test_native_svg_adapter.py` — SVG adapter unit tests
- `tests/fidelity/test_serialization_roundtrip.py` — JSON round-trip
- `tests/fidelity/test_svg_attributes.py` — attribute regression
- Additions to `tests/fidelity/test_mutations.py` — expanded 19+ mutation set
- Additions to `tests/fidelity/test_core_boundary.py` — strengthened isolation

Existing test suite: all 105 fidelity unit tests must remain green throughout.
