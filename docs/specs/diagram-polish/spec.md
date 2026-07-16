# Diagram Polish — spec

Mode: full (multi-feature, structural public-interface change)
- **Status:** Shipped

## Objective

Raise diagram visual quality from 62% → target 80%+ against the enterprise rubric
(`.context/diagram-polish-rubric-score.md`). Fix two parser bugs and implement
five polish improvements to `mermaid_layout.py` and the architecture recipe family.

## Acceptance Criteria

- [x] **AC-1 (BUG)** `_parse_spec` strips surrounding quotes from captured labels  
  (e.g. `A["My Service"]` renders as `My Service`, not `"My Service"`)
- [x] **AC-2 (BUG)** Subgraph `ID["Label"]` form already fixed (bracket extraction committed)
- [x] **AC-2b (BUG)** Node labels with `\n` literal render as `<br>` line breaks
- [x] **AC-3** `COL_GAP` increased from 16 → 32px; group container inner padding uses named constants
- [x] **AC-4** `:::external` inline class renders with dim border + dim text via `--node-fg-dim`; no hardcoded hex
- [x] **AC-5** Node label `|` separator renders main label + tech sub-label (11px `--node-fg-dim`)
- [x] **AC-6** Legend auto-appended for multi-style diagrams; absent for single-style
- [x] **AC-7** Diagram metadata chip (type always; title when `%% title:` present) prepended
- [x] **AC-8** All 145 tests pass; lint_diagram_recipes.py 0 violations
- [x] **AC-9** `diagram.md` documents `:::external`, `|`, `%% title:`, and legend conventions (deferred: recipe-example-updates)

## Boundaries

**In scope:**
- `scripts/mermaid_layout.py` — parser + renderer
- `references/blocks/diagram.md` — document `:::external` convention
- `references/blocks/diagram-architecture.md` — update recipe examples
- `scripts/test_diagram_qa.py` — add tests for new features

**Not in scope:**
- C4 layer-depth color palette (separate work item)
- Auto-legend for non-graph layouts (sequence, ER, class diagrams)
- Arrow routing improvements
- Non-graph layout spacing changes

## Declined patterns

- Tempted to add a full C4 color depth system; declining — requires hardcoded hex values
  that violate the CSS variable contract
- Tempted to support all Mermaid classDef syntax (`classDef external fill:#xxx`); declining —
  mermaid_layout.py is a custom renderer, not Mermaid.js; `:::external` as a single
  semantic class is sufficient
- Tempted to add external node settings/config; declining — the rendering is deterministic
  from `:::external` annotation, no config needed
- Tempted to add legend to sequence/ER/class diagrams; declining — those have different
  rendering paths; graph topology only for now

## Testing Strategy

Goal-based checks + unit tests for new behavior:
- `_parse_spec("A[\\"My Service\\"]")` returns label `My Service` (no quotes)
- `_parse_spec("A[Service]:::external")` — spec is stripped, external class captured
- Node label `"User Service|Spring Boot"` splits into main + tech sub-label
- Legend generated when dotted edge present; not generated for plain graph
- Metadata chip present when `%% title: X` comment in source
