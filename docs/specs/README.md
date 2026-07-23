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
| [`mermaid-current-head-comparison-baseline`](mermaid-current-head-comparison-baseline/spec.md) | Draft | none | Provenance-locked gallery (15 fixtures) with per-renderer backend, git SHA, and fidelity/editorial lanes; hard-fail on silent ELK fallback |
| [`mermaid-non-vacuous-oracle`](mermaid-non-vacuous-oracle/spec.md) | Draft | none | Remove vacuous comparison passes; fixture minimum-count manifest; checks_run > 0 required for any pass status; arrow/cardinality in semantic multiset |
| [`elk-finalized-layout-roundtrip`](elk-finalized-layout-roundtrip/spec.md) | Draft | none | Lossless LayoutGraph → FinalizedLayout round trip via elk_adapter: ports, line_style, markers, labels, junction points, LayoutMetadata |
| [`mermaid-single-finalized-layout-pipeline`](mermaid-single-finalized-layout-pipeline/spec.md) | Draft | `elk-finalized-layout-roundtrip` | One compile_er/requirement/architecture() per type; HTML and SVG share identical geometry; dead dual-layout code retired |
| [`architecture-elk-authoritative-layout`](architecture-elk-authoritative-layout/spec.md) | Draft | `elk-finalized-layout-roundtrip` | ELK authoritative for architecture-complex placement, compounds, and edge routes; typed error handling replaces broad except |
| [`shape-geometry-authoritative-painters`](shape-geometry-authoritative-painters/spec.md) | Draft | none | paint_html() + paint_svg() for all 13 flowchart shapes via SHAPE_REGISTRY; flag polygon, subroutine rules, doublecircle rings, cylinder bounds corrected |
| [`class-diagram-marker-clearance`](class-diagram-marker-clearance/spec.md) | Draft | `class-diagram-marker-semantics` | Nonzero MarkerSpec.clearance per kind; route shortening + card-boundary clip; 40 px label-segment floor + shelf; mmdc class oracle extractor |
| [`flowchart-elk-routing-regression-pack`](flowchart-elk-routing-regression-pack/spec.md) | Draft | `elk-finalized-layout-roundtrip` | ELK edge sections + SCC feedback routing + obstacle model for 6 flowchart fixtures; compactness metrics; faithful mode preserves only Mermaid line semantics |
| [`state-diagram-local-cycle-routing`](state-diagram-local-cycle-routing/spec.md) | Draft | none | Semantic/routing/scope fields on RoutedEdge; local cycle routing around smallest SCC; composite boundary and title-region clipping |
| [`er-finalized-layout-and-dynamic-width`](er-finalized-layout-and-dynamic-width/spec.md) | Draft | `elk-finalized-layout-roundtrip`, `mermaid-single-finalized-layout-pipeline` | Per-entity dynamic card width; compile_er_layout() → FinalizedLayout; cardinality from port tangents; HTML/SVG coordinate identity |
| [`requirement-finalized-layout-sizing`](requirement-finalized-layout-sizing/spec.md) | Draft | `mermaid-single-finalized-layout-pipeline` | compile_requirement() → FinalizedLayout; measured card dimensions; width_hint/height_hint scaling; HTML/SVG coordinate identity |
| [`playwright-export-migration`](playwright-export-migration/spec.md) | Shipped | RFC-0003 | Migrate 4 shipped browser scripts + tools/diagram_render_check.py from Puppeteer/Node to Playwright for Python; ship dom-to-svg prebuilt; remove Node from repo entirely |
| [`renderer-stable-ids`](renderer-stable-ids/spec.md) | Implementing | `mermaid-source-bridge` | Stable `data-node-id`, `data-src`, `data-dst`, `data-edge-label` attrs on every primary entity and edge element across all 17 covered diagram types |
| [`diagram-consistency-system`](diagram-consistency-system/spec.md) | Implementing | none | Themed, pipeline-safe per-type diagram/architecture/PM recipes + expanded visual-consistency QA (per-page + deck-level) |
| [`mermaid-source-bridge`](mermaid-source-bridge/spec.md) | Implementing | `diagram-consistency-system` | Extract Mermaid fences from any source document into planning JSON; native Python layout engine (`mermaid_layout.py`) renders all Mermaid diagram types to pipeline-safe HTML/CSS, bypassing dagre |
| [`mermaid-renderer-uplift`](mermaid-renderer-uplift/spec.md) | Draft | none | 9-area renderer quality uplift: pixel-accurate text metrics, diamond clipping, 6 new node shapes, inline label formatting, SVG marker defs, sequence/ER/class notation, visual fixture corpus + screenshot baseline |
| [`mermaid-unified-layout-pipeline`](mermaid-unified-layout-pipeline/spec.md) | Shipped | ADR-001 | ELK-layered algorithm via elkjs 0.12.0 Node subprocess for flowchart/stateDiagram; Python fallback for inner-direction groups, terminal circles, self-loops; strict layout validation; fidelity oracle entity-mismatch classification |

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
