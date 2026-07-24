# Mermaid Parity CI and Maintainability Cleanup

Mode: full (structural — CI pipeline; _strategies.py split; dead-code deletion)

- **Status:** Shipped

Merges: differential-parity-test, playwright-gated-snapshot-verification,
strategies-module-split

Dependencies: all items 1–12 of the boston-v1 initiative.

## Objective

Turn the completed semantic and geometry contracts from items 1–12 into a reproducible
CI gate, then remove obsolete compatibility paths. The large `_strategies.py` module is
split into focused modules after behavior is locked by the new contracts.

## Boundaries

**In scope:**
- **Fast per-PR CI job (browser-free):**
  - Parser tests, semantic counts, `FinalizedLayout` validation, deterministic
    compilation, HTML/SVG geometry identity, node overlap checks, containment checks,
    boundary-endpoint checks, route-obstacle checks, marker/cardinality checks,
    backend/fallback metadata checks.
- **Pinned browser integration job:**
  - Batched mmdc rendering, structured reference extraction, oracle comparison,
    deterministic snapshot generation, optional raster diagnostics.
  - Retain existing `pytest-xdist` protection: snapshot/browser jobs must not run in
    unsafe parallel worker mode.
- **Published artifacts:** structured native geometry, structured reference geometry,
  oracle JSON, provenance JSON, failing fixture source, normalized SVGs for debugging,
  optional newly generated screenshots.
- **CI failure conditions:** zero-check pass, hidden fallback, missing backend metadata,
  node overlap, containment violation, route entering a node, endpoint not on visible
  boundary, marker/cardinality mismatch, HTML/SVG geometry divergence, nondeterministic
  normalized output, missing expected reference observations.
- **Raster similarity:** diagnostic only until stable, justified thresholds exist; not a
  hard gate.
- **Differential tests:** between current `to_svg()` path and pre-rearchitecture golden
  behavior where semantically applicable.
- **`_strategies.py` split** (after CI gates are green):
  - `_pipeline.py`, `_flowchart_compile.py`, `_sequence_compile.py`,
    `_compound_layout.py`, `_layout_fallback.py`, `_layout_validation.py`.
  - Parsing and semantic compilation separate from placement and painting.
- **Dead-code deletion:**
  - Successful-ELK-to-legacy round trips.
  - Post-layout compound shuffling.
  - Broad fallback exception handlers.
  - Source/destination pair identity maps.
  - Raw string-length layout estimates.
  - Dead ER compiler implementations.
  - Duplicated oracle status types.
  - Vacuous comparison branches.
- **Import-boundary tests:**
  - Painters cannot invoke layout algorithms.
  - Layout code cannot emit HTML or SVG.
  - Parsers cannot choose editorial colors.
  - Comparators cannot return PASS without checks.
- **Renderer architecture documentation update:** semantic pipeline, layout graph,
  ELK and fallback rules, recursive compounds, text measurement, shape geometry, oracle
  statuses, faithful mode, CI reproduction.
- Do not use previously generated visual artifacts as acceptance evidence; regenerate all
  integration outputs from the checked-out SHA.

**Out of scope:**
- New diagram type features.
- Changes to the renderer public API (backward compatibility is required).
- New CI infrastructure providers (changes are within the existing CI system).

**Never:**
- Use a preexisting generated artifact as the source of truth.
- Merge `_strategies.py` before CI gates are green.
- Remove a public renderer API without a migration path.

## Acceptance Criteria

- [ ] AC1: One command runs the fast local parity checks (browser-free); the command is
  documented in `AGENTS.md` or equivalent.
- [ ] AC2: One documented command runs the pinned browser/reference suite.
- [ ] AC3: All 15 in-scope fixtures have explicit non-vacuous statuses in the fast job.
- [ ] AC4: All CI failure conditions listed in scope produce a CI failure; none silently
  pass.
- [ ] AC5: Fallbacks are visible and typed in every CI artifact; no hidden fallback
  can produce a green CI result.
- [ ] AC6: `_strategies.py` no longer owns unrelated compilation systems after the split.
- [ ] AC7: No dead duplicate compiler remains in the codebase.
- [ ] AC8: No painter performs independent geometry work.
- [ ] AC9: No comparator treats absent data as success.
- [ ] AC10: All public renderer APIs remain backward compatible; a deprecation warning
  is emitted for any removed alias, not a hard error, for at least one release cycle.
- [ ] AC11: Import-boundary tests pass: a test asserts painters do not call layout
  functions; a test asserts layout code does not produce HTML/SVG strings; a test asserts
  comparators do not return PASS with zero checks.
- [ ] AC12: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

- **Fast job:** add a `pytest` configuration target or Makefile target that runs only
  browser-free parity checks; assert it completes in under 60 seconds on a standard CI
  worker.
- **CI failure conditions (parametric):** for each failure condition, construct a minimal
  scenario that triggers it; assert the CI check raises.
- **Zero-check pass blocked:** assert the `OracleResult` construction guard (from item 1)
  causes the fast job to fail if any fixture would otherwise produce a zero-check PASS.
- **Import-boundary tests:** use `ast.parse` or `importlib` to assert that `_renderer.py`
  does not import from `_layout.py` or `_routing.py`; assert `_layout.py` does not
  import from `_renderer.py`.
- **Module split completeness:** after the split, assert each new module file exists and
  that `_strategies.py` has been reduced to a re-export shim or deleted.
- **Dead-code deletion:** grep for `_compile_er_legacy`, `_elk_routes_to_specs`,
  source/destination tuple identity maps, and the old duplicated `OracleStatus` enum;
  assert zero matches.
- **Backward compatibility:** import all documented public API symbols from
  `scripts/mermaid_render`; assert none raise `ImportError`.
- **Determinism:** run the fast parity check twice on the same SHA; assert the normalized
  geometry outputs are byte-identical.
