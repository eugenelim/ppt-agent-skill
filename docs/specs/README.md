# Specs

> Feature specifications and implementation plans. See
> [`../CONVENTIONS.md`](../CONVENTIONS.md#4-specs-and-plans--docsspecsfeature)
> for the spec / plan distinction and lifecycle.

Each feature gets a directory:

```
docs/specs/<feature>/
├── spec.md      ← the contract (objective, boundaries, testing strategy, acceptance criteria): what this feature does
├── plan.md      ← the strategy + construction tests: how we'll build it
└── notes/       ← (optional) research, sketches, rejected approaches
```

## Active specs

<!-- Update this list as features are added. -->

| Spec | Status | Constrained by | Notes |
| --- | --- | --- | --- |
| [`diagram-consistency-system`](diagram-consistency-system/spec.md) | Implementing | none | Themed, pipeline-safe per-type diagram/architecture/PM recipes + expanded visual-consistency QA (per-page + deck-level) |

## Shipped specs (archived)

<!-- Once a feature is shipped, move its row here. The spec stays in place
     as documentation of the feature's contract. -->

| Spec | Status | Constrained by | Notes |
| --- | --- | --- | --- |
| [`reference-runbook-archetype`](reference-runbook-archetype/spec.md) | Shipped | none | Outline engine honors the `reference_runbook` narrative archetype: `论证策略` enum + archetype-branched density/skeleton rules in both validators, persuasive decks unchanged |
| [`reference-runbook-page-types`](reference-runbook-page-types/spec.md) | Shipped | none | `section-marker` (inline divider) + `reference` (back-matter) page_types across all seven enum consumer sites; completes the reference-runbook archetype (backlog items 1 + 4) |
| [`persistent-chrome-flag`](persistent-chrome-flag/spec.md) | Shipped | none | Deck-global `persistent_chrome` flag (default off) — masthead + runbook footer on every content page for reference decks, reusing worksheet.md group-C chrome recipes |
| [`assimilate-slides-skill`](assimilate-slides-skill/spec.md) | Shipped | none | Internal `assimilate-slides` authoring skill (ingest→scrub→classify→extract style/primitives/icons→narrative→mock→gates→ship) + searchable SVG icon library + deterministic `deck_probe.py`/`build_pdf.py`; dogfooded on a maintainer-supplied deck |
| [`architecture-diagram-primitives`](architecture-diagram-primitives/spec.md) | Shipped | none | Dogfood run of `assimilate-slides`: architecture-canvas primitives + seed icons under `schematic_blueprint` (no new style) |

## Adding a new spec

```bash
mkdir -p docs/specs/<feature-name>
cp .claude/skills/new-spec/assets/spec.md docs/specs/<feature-name>/spec.md
cp .claude/skills/new-spec/assets/plan.md docs/specs/<feature-name>/plan.md
```

Or, in Claude Code, run `/new-spec "<feature-name>"`.
