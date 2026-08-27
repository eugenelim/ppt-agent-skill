# Spec: Chart Registry Lockstep

- **Status:** Shipped
- **Owner:** unassigned
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Contract:** planning `chart_type` vocabulary and chart-resource routing
- **Shape:** mixed

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Deck authors can choose any supported chart with one stable `chart_type` value
and receive the matching paste-ready recipe during rendering. The published
vocabulary, planning validator, resource loader, and grouped recipe files agree
on the same 20 chart types, including recipe-backed stacked bars and treemaps.

## Boundaries

### Always do

- Treat the 20 recipe-backed chart types as one closed planning vocabulary.
- Keep planning JSON identifiers in `snake_case` and accept hyphenated forms
  only while resolving resource references.
- Keep every recipe compatible with the static HTML/SVG-to-PowerPoint pipeline:
  CSS-variable colors, HTML labels, no SVG `<text>`, and no runtime JavaScript.
- Detect registry, validator, loader, and recipe-index disagreement in tests.

### Ask first

- Add another chart type or move an existing type between recipe families.
- Change the planning JSON naming convention or accept new aliases.
- Introduce generated geometry, a runtime chart library, or a new dependency.

### Never do

- Represent a chart as supported without a paste-ready grouped-file recipe.
- Add native PowerPoint chart objects or embedded workbook behavior in this
  spec; that belongs to the Native PowerPoint Charts initiative.
- Add CSV/XLSX ingestion, analysis, transformation, or automatic chart
  selection in this spec; that belongs to the Data-to-Charts initiative.
- Add standalone per-chart Markdown files when grouped recipe files are the
  runtime loading contract.

## Testing Strategy

- Registry normalization and routing invariants use TDD because the supported
  vocabulary and family mapping are finite, deterministic sets.
- Validator and loader agreement uses integration tests that exercise both
  consumers against the canonical registry.
- Recipe presence, published vocabulary, dead-link removal, skill drift, and
  TOML validity use goal-based checks over committed artifacts.
- The two new static templates receive a manual source audit for pipeline-safe
  primitives; browser rendering is not required because no renderer behavior
  changes.

## Acceptance Criteria

- [x] A single canonical registry contains exactly 20 `snake_case` chart types
  and maps each type to `basic`, `advanced`, or `complex`.
- [x] `planning_validator.py` accepts exactly the canonical types and resolves
  all 20 chart references to existing grouped recipe files.
- [x] `resource_loader.py` uses the canonical registry and loads the same
  grouped file for underscore and hyphen forms of every supported type.
- [x] `advanced.md` contains a paste-ready, pipeline-safe `stacked_bar` recipe;
  `complex.md` contains a paste-ready, pipeline-safe `treemap` recipe.
- [x] The chart index, skill contract, planning playbook, research guidance,
  and data-to-visual mapping publish the same 20 recipe-backed types and contain
  no links to nonexistent per-chart recipe files.
- [x] Automated tests fail if the canonical registry, consumer behavior, or
  grouped recipe indexes drift apart.
- [x] `workspace.toml` parses and records separate Native PowerPoint Charts and
  Data-to-Charts and Complex Visualization initiatives.
- [x] Focused chart tests, planning-schema tests, `tools/check_skill.py`, and
  whitespace checks pass without weakening existing checks.

## Assumptions

- Technical: grouped files under `references/charts/` are the runtime recipe
  loading boundary (source: `scripts/planning_validator.py`,
  `scripts/resource_loader.py`, and `references/charts/index.md`).
- Technical: current chart output is a static HTML/SVG snapshot rather than a
  native Office chart (source: `references/charts/index.md` and pipeline docs).
- Product: `stacked_bar` and `treemap` remain supported by gaining real recipes,
  producing a 20-type contract (source: user confirmation 2026-08-26).
- Product: native PowerPoint charts and raw-data transformation remain separate
  initiatives, not hidden scope in this repair (source: user confirmation
  2026-08-26).
