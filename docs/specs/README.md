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
| [`renderer-stable-ids`](renderer-stable-ids/spec.md) | Implementing | `mermaid-source-bridge` | Stable `data-node-id`, `data-src`, `data-dst`, `data-edge-label` attrs on every primary entity and edge element across all 17 covered diagram types |
| [`diagram-consistency-system`](diagram-consistency-system/spec.md) | Implementing | none | Themed, pipeline-safe per-type diagram/architecture/PM recipes + expanded visual-consistency QA (per-page + deck-level) |
| [`mermaid-source-bridge`](mermaid-source-bridge/spec.md) | Implementing | `diagram-consistency-system` | Extract Mermaid fences from any source document into planning JSON; native Python layout engine (`mermaid_layout.py`) renders all Mermaid diagram types to pipeline-safe HTML/CSS, bypassing dagre |
| [`mermaid-renderer-uplift`](mermaid-renderer-uplift/spec.md) | Draft | none | 9-area renderer quality uplift: pixel-accurate text metrics, diamond clipping, 6 new node shapes, inline label formatting, SVG marker defs, sequence/ER/class notation, visual fixture corpus + screenshot baseline |

## Shipped specs (archived)

<!-- Once a feature is shipped, move its row here. The spec stays in place
     as documentation of the feature's contract. -->

| Spec | Status | Constrained by | Notes |
| --- | --- | --- | --- |
| [`audience-type-routing`](audience-type-routing/spec.md) | Shipped | RFC-0002 | Two derived outline fields (`受众层级` 4-tier, `消费模式` 3-mode) + Phase 2 checks #22–#26 + enriched `core_audience` interview, orthogonal to RFC-0001 `叙事范式`; raises `smoke_skill.py` interview caps to 11000/13000 (5th file; deviation recorded in spec scope note) |
| [`slide-intent-review`](slide-intent-review/spec.md) | Shipped | none | Deterministic, no-LLM slide-intent worksheet (muted `schematic_blueprint` chrome) rendered from `planning/*.json` into `runtime/proof/` for cheap staleness/structure review before the bespoke render, plus a Step 4.5 Review-vs-Render consent gate |
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
