# Spec: SDLC Discovery Readout Assimilation

Mode: light (no single risk trigger — multi-file but familiar territory, primitives-only)
- **Status:** Shipped

## Objective

Assimilate the reusable design language from a consulting SDLC discovery readout into
the PPT agent skill's reference library. Source: an analyzed HTML discovery readout
artifact (scrubbed of all identifiers per §39 before this spec was written).
Output: new block primitives, narrative conventions, and diagram variants — guidance-
only; no validator/enum/page_type changes.

## Boundaries

- **In scope**: `references/blocks/discovery-readout.md` (new), `blocks/README.md`,
  `scripts/lint_diagram_recipes.py` (target-list append), `diagram-project.md` (new
  gantt variant), `diagram-process-flow.md` (new swimlane variant), `narrative-arc.md`
  (new archetype + conventions).
- **Out of scope**: validators, enums, page_type changes, Python scripts beyond the
  lint target-list append, SKILL.md, any HTML mock files.
- **Deferred to backlog**: engine-level `discovery_readout` card_type/archetype flag.

## Acceptance Criteria

- [x] `references/blocks/discovery-readout.md` exists with ≥12 recipes, each with all
      5 mandatory markers (何时用 / 数据格式 / 模板 / 自检 / 管线安全).
- [x] `scripts/lint_diagram_recipes.py` includes `discovery-readout.md` in target list.
- [x] `references/blocks/README.md` registers discovery-readout as 按需加载 companion.
- [x] `references/principles/narrative-arc.md` has a "发现汇报型" (discovery-readout)
      archetype section and ≥2 new named conventions.
- [x] `references/blocks/diagram-project.md` has a `gantt-engagement` variant recipe.
- [x] `references/blocks/diagram-process-flow.md` has a `swimlane-solution` variant recipe.
- [x] `python3 scripts/lint_diagram_recipes.py` exits 0 with no violations.
- [x] `python scripts/check_skill.py` exits 0.
- [x] Grep for any of: client names, org names, internal product names, session labels,
      email addresses → zero hits in committed files.

## Testing Strategy

Goal-based: run `python3 scripts/lint_diagram_recipes.py` and `python scripts/check_skill.py`.
Manual QA: grep the new files for forbidden identifiers; spot-check 3 primitives for
pipeline-safety (no SVG `<text>`, no hardcoded hex outside whitelist, no `rgba()`).

## Assumptions (trio)

1. Adding `discovery-readout.md` to the lint target list is a safe one-line append;
   the lint doesn't validate cross-file content.
2. The narrative-arc.md additions are guidance-only and do not require a validator
   change (confirmed by the assimilate-slides SKILL.md).
3. The carbout hex values I need (`#ef4444` for High severity) are already in the
   lint whitelist.

## Declined patterns

- Tempted to add a `discovery_readout` validator enum — declining; guidance-only per
  assimilate-slides SKILL.md; deferred to backlog.
- Tempted to create a full gallery mock HTML file — declining; out of scope for this
  assimilation (primitives-only run, no new style).
- Tempted to add a new `playbook` for the discovery-readout authoring workflow —
  declining; scope; can be added in a follow-up.
- Tempted to restructure narrative-arc.md into a new table format — declining;
  extend existing table structure only.
