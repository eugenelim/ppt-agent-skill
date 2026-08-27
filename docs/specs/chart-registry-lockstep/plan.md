# Plan: Chart Registry Lockstep

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as the implementation learns.

## Approach

Introduce one small Python registry that owns normalization, the 20 supported
planning identifiers, and their grouped recipe destinations. Make the validator
and loader consume it, then lock the registry to the recipe indexes with focused
tests. Add the missing stacked-bar and treemap recipes directly to the grouped
files the loader already injects. Finally, align the skill-facing selectors and
remove dead per-chart links without expanding into data ingestion or native
Office chart generation.

## Constraints

- Preserve the public `snake_case` planning vocabulary and grouped-file loading
  model.
- Add no dependency and no new top-level directory.
- Follow the fixed chart-recipe section order and pipeline-safety rules in
  `AGENTS.md`.
- Preserve unrelated and pre-existing worktree changes.
- Do not change `scripts/html_packager.py`; `docs/product/DESIGN.md` therefore
  remains outside this change.

## Construction tests

**Integration tests:** one lockstep suite imports the registry, validator, and
loader; checks all 20 types; and confirms grouped recipe files and indexes.

**Manual verification:** inspect the two new recipes for CSS-variable colors,
HTML text labels, static geometry, and absence of prohibited runtime features.

## Design (LLD)

### Design decisions

- A dedicated `chart_registry.py` avoids making either consumer depend on the
  other and gives two existing callers one source of truth. Traces to AC1-AC3.
- Canonical keys use `snake_case`; normalization converts hyphens to underscores
  at resource boundaries. Traces to AC1-AC3.
- `stacked_bar` belongs in `advanced.md`; `treemap` belongs in `complex.md`.
  Traces to AC4-AC5.

### Data & schema

The registry is an insertion-ordered `dict[str, str]` from planning identifier
to recipe family. The supported set is derived from its keys. No persisted data
or migration is introduced. Traces to AC1.

### Interfaces & contracts

- Planning JSON continues to expose `cards[].chart.chart_type` as a closed
  underscore-named enum.
- Chart refs may use underscores or hyphens and resolve to a grouped Markdown
  file. Traces to AC1-AC3.

### Component / module decomposition

- `scripts/chart_registry.py`: canonical identifiers, normalization, lookup.
- `scripts/planning_validator.py`: validation consumer.
- `scripts/resource_loader.py`: loading consumer.
- `references/charts/*.md`: human- and agent-readable recipe contract.
- `tests/test_chart_registry_lockstep.py`: cross-surface tripwire.

### Failure, edge cases & resilience

Unknown chart types remain validator errors and fall back to the loader's
existing direct-file resolution. Empty references remain harmless. A missing
grouped file fails the lockstep test. Traces to AC2, AC3, and AC6.

### Dependencies & integration

No external dependency. Both scripts import the new sibling module through the
same `scripts/` execution path already used by repository tests and CLIs.

## Tasks

### T1: The approved 20-type chart contract is explicit

**Depends on:** none

**Tests:**
- Spec and plan name the same scope, exclusions, and verification surfaces.

**Approach:**
- Record the confirmed assumptions and initiatives.
- Keep future capabilities in their own shaping queues.

**Done when:** the spec is Approved, the plan is Executing, and TOML parses.

### T2: Stacked-bar and treemap have pipeline-safe recipes

**Depends on:** T1

**Tests:**
- Recipe-index checks find both IDs in their declared families.
- Source audit finds no JavaScript, SVG `<text>`, or hardcoded palette colors in
  the new templates.

**Approach:**
- Add a 100% stacked-bar template to `advanced.md`.
- Add a precomputed rectangular treemap template to `complex.md`.

**Done when:** both recipes follow the required fixed section order and are
paste-ready.

### T3: Validator and loader consume one authoritative registry

**Depends on:** T2

**Tests:**
- All 20 identifiers validate.
- Hyphen and underscore refs resolve to the declared family.
- An unknown identifier still fails validation.

**Approach:**
- Add the canonical registry and normalization helper.
- Replace both duplicate maps with imports and derived sets.

**Done when:** no duplicate chart-routing table remains in either consumer.

### T4: Published chart guidance agrees with runtime support

**Depends on:** T2, T3

**Tests:**
- Searches find no dead `charts/<type>.md` references.
- Skill and page-planning contract enumerate the registry's 20 identifiers.

**Approach:**
- Update indexes, selectors, mappings, and count claims.
- Route guidance links to grouped files.

**Done when:** every published supported type has one recipe family and no dead
per-chart path.

### T5: Lockstep and repository gates are green

**Depends on:** T3, T4

**Tests:**
- Run the new lockstep suite and planning-schema suite.
- Run `python tools/check_skill.py` and `git diff --check`.

**Approach:**
- Fix only failures introduced by this change.
- Run the required bounded adversarial review after gates pass.

**Done when:** all scoped gates pass and review has no unresolved blocking
finding.

## Rollout

This is an atomic local contract update with no deployment, infrastructure, or
external-system sequencing. Reverting the registry, recipes, and documentation
together restores the previous behavior.

## Risks

- A new type could be added to runtime code without a usable recipe; the
  cross-surface test prevents this.
- Recipe headings are prose and could become hard to parse; the test targets
  the explicit `chart_id` index tables rather than full document structure.
- Large example templates can obscure the core routing diff; recipes remain
  bounded examples with precomputed geometry.

## Changelog

- 2026-08-26: initial plan; expanded the confirmed contract from 18 to 20 by
  adding recipe-backed `stacked_bar` and `treemap`.
- 2026-08-26: adversarial review tightened count claims, exercised the loader
  across both accepted ref spellings, and locked family index tables to unique
  recipe headings.
