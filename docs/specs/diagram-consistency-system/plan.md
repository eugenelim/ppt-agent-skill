# Plan: diagram-consistency-system

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn.

## Approach

Two coupled workstreams sharing the throughline *visual consistency*:

1. **Themed diagram recipe library.** Replace the vague "design soul" prose in
   `blocks/diagram.md` / `blocks/timeline.md` with the copy-ready recipe pattern
   that `references/charts/` already proves. `blocks/diagram.md` becomes a thin
   **always-loaded selector** carrying the *theming contract* (every color/font
   binds to deck CSS variables) and the *shared connector/arrow primitives*
   (pipeline-safe SVG `<polygon>` arrowheads, real `<div>`/SVG `<line>` connectors,
   HTML-overlay labels). The actual per-type recipes live in four **family files**
   under `blocks/` that load on demand via the existing `block_refs` route — so a
   slide that needs an architecture diagram pulls only the architecture family,
   not 2000 lines of every recipe.

2. **Expanded verification.** Add the missing visual-consistency dimensions to
   `scripts/visual_qa.py` (objective, automatable checks) and to
   `page-review-playbook.md` (perceptual LLM-scan items), plus a new **deck-level
   cross-slide aggregate** in `visual_qa.py` batch mode. Resolve the
   `design-specs.md` §E ↔ `pipeline-compat.md` contradiction so diagrams aren't
   told "mask-image is fine," and add an `AGENTS.md` skill-authoring format so
   recipe content is consistently terse/progressive-disclosure.

Riskiest part: the per-family recipes must be *both* visually engaging *and*
pipeline-safe — the two have historically pulled against each other (browser-only
CSS looks best but breaks in PPTX). The recipe lint (T7) and the 3-style render QA
(T13) are the guardrails. Order: theming contract + AGENTS.md format first (they
constrain every recipe), then recipes per family, then the QA additions (parallel),
then wiring + playbook + render QA.

## Constraints

- `docs/CONVENTIONS.md` §3–4 — editing existing `references/`, `scripts/`,
  `AGENTS.md` is a normal spec/PR; no RFC needed (no new top-level dir / removed
  convention).
- `references/pipeline-compat.md` is the **authoritative** source for what
  survives HTML→SVG→PPTX; recipes and the §E reconciliation conform to it.
- No new ADRs/RFCs constrain this work.

## Construction tests

**The repo gate is `scripts/smoke_test.py`** (a phased runner) — there is no
pytest/typecheck harness and `tools/hooks/pre-pr.py` is an unfilled stub. The
recipe lint and the new `visual_qa.py` self-tests are added as smoke-test phases
(T14), so "the gate is green" means `python3 scripts/smoke_test.py` passes.

**Integration / cross-cutting:**
- **Recipe structural lint** (T7) — one script asserts, across all recipe files,
  the five bold-label markers, zero pipeline-forbidden techniques, and
  CSS-variable-only colors (bar `#22c55e`/`#ef4444`). Runs as a smoke-test phase.
- **3-style render QA** (T13) — render one representative diagram per family via
  `html2png.py` under three style variants (`dark_tech`, `blue_white`,
  `mocha_editorial`); assert non-FAIL `visual_qa.py` and confirm theme inheritance.
- **visual_qa regression** — a recorded run over the existing sample/fixture set
  produces byte-identical verdicts/exit codes pre/post (new checks additive).

**Manual verification:** T13 eyeball pass on the rendered PNGs (theme inheritance,
"looks engineered", arrowheads/connectors intact).

## Design (LLD)

### Design decisions

- **Family-file split over one mega-file** — keeps page-HTML agent context lean;
  mirrors `charts/{basic,complex,advanced}.md`. Rejected: one big `diagram.md`
  (context bloat, AC violation). Traces to: AC "delivered per type/family",
  "thin selector".
- **No `resource_loader.py` change** — family files live under `blocks/` and load
  via the existing `block_refs` route; planning emits the family ref. Rejected:
  adding a `diagram_type→family` FIELD_ROUTE (an "Ask first" loader change).
  Traces to: AC "via the existing block_refs route".
- **Arrowheads = inline SVG `<polygon>`** (not CSS-border triangles, not `<marker>`
  unless verified) — pipeline-compat already mandates polygon; marker has
  older-renderer inconsistencies. Traces to: AC "no pipeline-forbidden technique".
- **Check routing: objective→`visual_qa.py`, perceptual→playbook.** Palette ratio,
  hardcoded-hex, type-scale presence, corner-radius, element-size/alignment are
  pixel/text-decidable; balance, optical alignment, gestalt are LLM-scan. Traces
  to: AC `visual_qa.py` checks + playbook consistency-scan.
- **New checks start WARN, not FAIL** — palette/alignment heuristics can
  false-positive; WARN cannot block FINALIZE on a good slide (Boundary "Ask first").
  Traces to: AC "preserving the 0/1/2 exit contract".
- **`pipeline-compat.md` is the single source of truth**; `design-specs.md` §E and
  `css-weapons.md` point to it rather than restating. Traces to: AC "contradiction
  resolved".

### Component / module decomposition

Reference content (new/changed):
- `references/blocks/diagram.md` — **rewrite** as selector + theming contract +
  shared primitives (always loaded for `card_type:diagram`).
- `references/blocks/diagram-architecture.md` — `architecture-component`,
  `architecture-deployment`, `er-data-model`, `layers` (backward-compat layered stack).
- `references/blocks/diagram-process-flow.md` — `flowchart`, `swimlane`,
  `sequence`, `state-machine`, `data-flow`.
- `references/blocks/diagram-project.md` — `gantt`, `dependency-network`,
  `org-tree`, `kanban`.
- `references/blocks/diagram-concept.md` — `mind-map`, `matrix-quadrant`, `venn`,
  + SVG-metaphor shapes `pyramid`, `funnel`, `cycle`, `hub-spoke`, `onion`,
  `fishbone`.
- `references/blocks/timeline.md` — **rewrite** to the recipe pattern; cross-links
  `gantt`.
- `references/blocks/README.md` — update the component table for the new family files.

Scripts:
- `scripts/visual_qa.py` — add per-page check functions + deck-level batch
  aggregate; new stable ids (e.g. `PAL-01`, `HEX-01`, `TYPE-01`, `RAD-01`,
  `ALIGN-01`, `DTHEME-01`; deck `DECK-PAL-01`, `DECK-BG-01`, `DECK-TYPE-01`).
- `scripts/lint_diagram_recipes.py` — **new** structural lint (T7).
- self-test fixtures for the new `visual_qa.py` checks and the recipe lint,
  consumed by `scripts/smoke_test.py` phases (T14) — no standalone pytest dir.

Playbooks / governance:
- `references/playbooks/step4/page-review-playbook.md` — add Part: *consistency scan*.
- `references/playbooks/step4/page-planning-playbook.md` + the planning prompt
  template — emit the diagram family `block_ref` from `diagram_type`.
- `references/playbooks/step4/page-html-playbook.md` — note diagram theming contract.
- `references/design-runtime/design-specs.md` §E — reconcile with pipeline-compat.
- `references/design-runtime/css-weapons.md` — pipeline-safety notes on W2/W3/W4/W6/W8.
- `AGENTS.md` — skill-authoring format section.

Traces to: all recipe + QA + contradiction ACs.

### Behavior & rules

- **Theming contract:** a diagram recipe declares a local `--node-bg`,
  `--node-border`, `--connector`, `--node-radius`, `--label-font` etc., each
  *sourced from* deck vars (`--card-bg-from`, `--card-border`, `--accent-1`,
  `--card-radius`, `--font-primary`, `--text-*`); SVG `fill`/`stroke` reference the
  local vars. No literal colors inside nodes/connectors.
- **Recipe markers (fixed bold-label form — the lint keys on these exact
  strings):** each recipe is `### <type> (<id>)` then the bold labels `**何时用**`,
  `**数据格式**`, `**模板**` (≥1 fenced HTML/CSS block), `**自检**`, `**管线安全**`.
  Modeled on `charts/basic.md` (which uses `**何时用**` / `**数据格式**` /
  `**HTML 模板**` / `**自检**` and folds safety into `**自检**`); diagrams add an
  explicit `**管线安全**` block. The lint accepts `**模板**` or `**HTML 模板**`.
- **visual_qa palette check:** sample quantized colors; the deck palette is read
  from the slide HTML `:root` vars (and/or `style.json` when provided); ratio of
  off-palette pixels above threshold → WARN. Diagram theme-binding (`DTHEME-01`)
  scopes the same test to detected diagram regions / `data-card-id` of diagram
  cards.
- **Deck aggregate:** over all `slide-*.png`(+html), compare palette token sets,
  dominant background, and font-size histograms; flag drift beyond tolerance.

Traces to: AC palette/theme, type-scale, deck aggregate, diagram theme-binding.

### Failure, edge cases & resilience

- **False positives:** dark themes, gradients, and photos legitimately introduce
  many colors → palette check tolerances tuned on fixtures; stays WARN. Trend
  colors `#22c55e`/`#ef4444` whitelisted.
- **Missing style.json:** palette derived from HTML `:root`; if absent, check
  emits WARN "palette source unavailable", never FAIL.
- **Backward compat:** inputs that don't trip a new check produce identical output
  to today; exit-code contract `0/1/2` preserved (regression test).

Traces to: AC "pre-existing behavior unchanged", "preserving 0/1/2".

### Dependencies & integration

- `resource_loader.py` (`block_refs` route — unchanged), `html2png.py` (render QA),
  Pillow (existing, no new dep). Traces to: Boundary "no new dependency".

## Tasks

### T1: `blocks/diagram.md` is a thin themed selector with shared pipeline-safe primitives

**Depends on:** none

**Tests:**
- Recipe lint (T7) later asserts `diagram.md` carries the theming contract block
  and the shared connector/arrow primitive snippets. (AC: thin selector / theming)
- `grep` confirms `diagram.md` contains no full per-type templates (it points to
  family files) and no pipeline-forbidden technique.

**Approach:**
- Rewrite `diagram.md`: selection table (`diagram_type` → family file), the
  **theming contract** (local vars sourced from deck vars), and shared primitives
  (SVG `<polygon>` arrowhead snippet, `<div>`/SVG `<line>` connector snippets,
  HTML-overlay label pattern, 8px grid discipline).
- Keep `diagram_type` enum additive and **backward-compatible**: the existing
  values `pyramid | flowchart | hub-spoke | cycle` keep same-named recipes, and
  `layers` keeps a same-named `layers` recipe (a layered stack) housed in the
  architecture family file — it is **not** renamed/aliased to
  `architecture-component`. New ids are added alongside; no existing value
  re-homes to a different recipe.

**Done when:** `diagram.md` renders the selector+contract+primitives; recipe lint
passes on it; no per-type template inlined; the old 5 `diagram_type` values still
resolve to a recipe.

### T12: `AGENTS.md` skill & reference authoring-format section

**Depends on:** none
**Ordering note:** T12 is sequenced early (before T2–T5) although `Depends on:
none`, because every recipe file references the authoring format it defines.

**Tests:**
- `grep` asserts `AGENTS.md` has a "Skill & reference authoring format" section
  covering **two** formats: (a) `SKILL.md` — the agentskills.io frontmatter set
  (`name, description, license, compatibility, metadata, allowed-tools`),
  trigger-friendly terse `description`, progressive disclosure (thin body →
  `references/` on demand); (b) reference recipe files (no frontmatter) — the fixed
  bold-label markers and terse wording. The `tools/lint-agent-artifacts.py` citation
  is conditional ("where installed"); the section does **not** claim that file
  exists in this repo, and does **not** assert agentskills frontmatter applies to
  the frontmatter-less recipe `.md` files. (AC: AGENTS.md format)

**Approach:**
- Add the section specifying both concrete formats so authored content is
  consistent; reference-file conformance is enforced by the recipe lint (T7), not
  by a frontmatter lint.

**Done when:** section exists with both formats; `grep` assertions pass; no claim
of a non-existent lint.

### T2: Architecture family recipes

**Depends on:** T1, T12
**Touches:** references/blocks/diagram-architecture.md

**Tests:**
- Recipe lint (T7): each of `architecture-component`, `architecture-deployment`,
  `er-data-model`, and `layers` (the backward-compat layered-stack recipe) has all
  five sections, CSS-var-only colors, no forbidden technique.
- Render QA (T13): renders themed under 3 styles, non-FAIL.

**Approach:** author the recipes — grouped-container nesting for cloud/network,
layer bands for component, tabular entity nodes + cardinality edges for ER, and a
`layers` layered-stack recipe (preserves the existing `diagram_type:layers`).

**Done when:** lint green for the file; one sample renders themed.

### T3: Project-management family recipes (+ timeline rewrite)

**Depends on:** T1, T12
**Touches:** references/blocks/diagram-project.md, references/blocks/timeline.md

**Tests:**
- Recipe lint: `gantt`, `dependency-network`, `org-tree`, `kanban` + rewritten
  `timeline.md` all pass.
- Render QA under 3 styles.

**Approach:** time-axis bar layout (gantt/roadmap/milestone variants), L-R DAG
(dependency/PERT), top-down tree (org/WBS), status-column card stacks (kanban);
rewrite `timeline.md` to the recipe pattern, cross-link `gantt`.

**Done when:** lint green; samples render themed.

### T4: Process & flow family recipes

**Depends on:** T1, T12
**Touches:** references/blocks/diagram-process-flow.md

**Tests:**
- Recipe lint: `flowchart`, `swimlane`, `sequence`, `state-machine`, `data-flow`.
- Render QA under 3 styles.

**Approach:** Grid node lattice + SVG connector cells; lane bands (swimlane/BPMN);
lifeline columns (sequence); loop-back edges (state); leveled DFD.

**Done when:** lint green; samples render themed.

### T5: Concept & SVG-metaphor family recipes

**Depends on:** T1, T12
**Touches:** references/blocks/diagram-concept.md

**Tests:**
- Recipe lint: `mind-map`, `matrix-quadrant`, `venn`, `pyramid`, `funnel`,
  `cycle`, `hub-spoke`, `onion`, `fishbone`.
- Render QA under 3 styles.

**Approach:** radial tree (mind-map), axis+quadrant grid (matrix/SWOT/RACI/risk),
overlap geometry (venn), and inline-SVG `<polygon>`/`<path>` shape geometry for the
six metaphor shapes (no CSS-border tricks).

**Done when:** lint green; samples render themed.

### T6: Diagram family selection wired end-to-end

**Depends on:** T1

**Tests:**
- Goal-based: a planning fixture with a `card_type:diagram, diagram_type:<x>` card
  produces `resources.block_refs` including the matching family; `resource_loader.py
  resolve` then injects that family file. (AC: delivered per family via block_refs)

**Approach:** update `page-planning-playbook.md` + planning prompt template to emit
the family `block_ref` from `diagram_type` (mapping table); note the theming
contract in `page-html-playbook.md`; update `blocks/README.md`.

**Done when:** the fixture resolves the correct family file body.

### T7: Recipe structural lint

**Depends on:** T2, T3, T4, T5

**Tests:**
- Unit: lint passes on a correct fixture recipe; fails on each violation (missing
  section, SVG `<text>`, CSS-border triangle, `::before` visual content,
  `mask-image`/`conic-gradient`/`background-clip:text`, stray hardcoded hex).

**Approach:** add `scripts/lint_diagram_recipes.py` scanning `blocks/diagram*.md` +
`timeline.md`. It keys on the exact bold-label markers from §Behavior
(`**何时用**`, `**数据格式**`, `**模板**`|`**HTML 模板**`, `**自检**`, `**管线安全**`),
counts a recipe per `### <type> (<id>)` heading, and flags forbidden techniques
(`<text` inside `<svg`, `border-*` width:0 triangles, `::before`/`::after` with
`content:` carrying glyphs, `mask-image`/`conic-gradient`/`background-clip:text`)
and stray hardcoded hex/`rgb()` outside the `#22c55e`/`#ef4444` whitelist. Wire it
in as a `scripts/smoke_test.py` phase (T14).

**Done when:** lint green on all real recipe files; self-tests pass; runs in smoke_test.

### T8: `visual_qa.py` per-page consistency checks

**Depends on:** none
**Touches:** scripts/visual_qa.py

**Tests:**
- Unit (fixtures): off-palette image → `PAL-01` WARN; hardcoded hex in HTML →
  `HEX-01` WARN; flat single-size text → `TYPE-01` WARN; mixed radii → `RAD-01`
  WARN; misaligned/odd-size repeated elements → `ALIGN-01` WARN; diagram region
  off-palette → `DTHEME-01` WARN. Clean fixture → all PASS, exit unchanged.
- Regression: an input tripping no new check yields byte-identical prior verdict;
  exit contract `0/1/2` preserved.

**Approach:** add check functions + ids; palette sourced from HTML `:root`/style.json
(WARN "palette source unavailable" if absent, never FAIL); default new checks to
WARN. Provisional per-page tolerances (named constants, fixture-calibrated):
`PAL-01` off-palette pixel ratio > 15%; `HEX-01` any non-whitelisted hardcoded
hex/`rgb()` in HTML; `TYPE-01` fewer than 2 distinct detectable text sizes;
`RAD-01` > 2 distinct corner-radius values among cards; `ALIGN-01` repeated-element
bounding boxes off the 8px grid or size-variance > 15%; `DTHEME-01` diagram-region
off-palette ratio > 15%. Self-tests live with T14 (smoke_test phase).

**Done when:** self-tests + regression test pass; `--help`/exit `0/1/2` semantics intact.

### T9: `visual_qa.py` deck-level cross-slide aggregate

**Depends on:** T8
**Touches:** scripts/visual_qa.py

**Tests:**
- Unit: a multi-PNG fixture set with one off-palette / wrong-background / off-scale
  slide → `DECK-PAL-01`/`DECK-BG-01`/`DECK-TYPE-01` WARN with deck verdict; a
  coherent set → PASS.

**Approach:** in batch mode, accumulate palette token sets, dominant background,
font-size histograms across slides; emit deck aggregate section + verdict using the
provisional thresholds pinned in spec.md (`DECK-PAL-01` Jaccard < 0.5 vs deck mode;
`DECK-BG-01` background RGB distance > 48; `DECK-TYPE-01` top-size set differs by
> 2). Constants named + commented for later calibration.

**Done when:** deck aggregate prints with ids; tests pass; single-file mode
unaffected.

### T10: `page-review-playbook.md` consistency-scan pass

**Depends on:** T8, T9

**Tests:**
- Goal-based `grep`: playbook has a *consistency scan* part enumerating palette,
  type-scale, alignment/spacing, corner-radius/border, element-size, diagram
  theming, optical alignment, cross-slide belonging — each with a P0/P1/P2 and the
  matching `visual_qa.py` check id.

**Approach:** add the part; map dimensions → severities → check ids; reference the
deck aggregate as a final-round step. **Reconcile** the new `HEX-01`/`RAD-01` ids
with the existing P1-5 (hardcoded color) and P2-1 (corner-radius) items —
cross-reference them, do not introduce a second divergent severity for the same
defect.

**Done when:** `grep` assertions pass; P1-5/P2-1 cross-references present, no
duplicate severity for hardcoded-color or corner-radius.

### T11: Resolve §E ↔ pipeline-compat contradiction

**Depends on:** none
**Touches:** references/design-runtime/design-specs.md, references/design-runtime/css-weapons.md

**Tests:**
- Goal-based `grep`: `design-specs.md` §E no longer lists `mask-image`/
  `conic-gradient`/`background-clip:text`/pseudo-elements as freely usable and
  points to `pipeline-compat.md`; each affected `css-weapons.md` weapon carries a
  pipeline-safety note.

**Approach:** rewrite §E "CSS 能力释放" to defer to pipeline-compat (mark those
features fallback-only/degrading); annotate W2/W3/W4/W6/W8 with a one-line
pipeline-safety note + safe alternative.

**Done when:** `grep` assertions pass; no remaining "freely usable" claim for
forbidden features.

### T13: 3-style render QA across families

**Depends on:** T2, T3, T4, T5, T6, T8, T9

**Tests:**
- Manual/visual: one representative diagram per family rendered via `html2png.py`
  under the three named styles (`dark_tech`, `blue_white`, `mocha_editorial`);
  theme inherited from `:root`; `visual_qa.py` non-FAIL on each.

**Approach:** build sample HTML per family from the recipes; render; eyeball;
run `visual_qa.py`.

**Done when:** all family samples render themed without error and pass `visual_qa.py`.

### T14: New checks wired into the `scripts/smoke_test.py` gate

**Depends on:** T7, T8, T9

**Tests:**
- Goal-based: `python3 scripts/smoke_test.py` runs the recipe lint and the
  `visual_qa.py` self-tests as phases and exits non-error on a clean tree; a
  seeded violation (bad recipe / failing check fixture) makes it exit non-zero.

**Approach:** add a smoke-test phase that invokes `scripts/lint_diagram_recipes.py`
and the `visual_qa.py` self-test fixtures; surface results in the phased report.
Leave `tools/hooks/pre-pr.py` as-is unless trivially wirable.

**Done when:** smoke_test runs both and gates on them; report shows the new phases.

## Rollout

- **Delivery:** documentation/skill-content + script change; no runtime service.
  Reversible by revert. No data migration, no published event.
- **Infrastructure:** none.
- **External-system integration:** none.
- **Deployment sequencing:** none beyond task order; the lint (T7) and the gate
  wiring land with the recipes so CI stays green.

## Risks

- **Recipe volume.** 16+ recipes is a large authoring lift; phased by family and
  guarded by the lint so partial progress is always gate-green. Mitigation: ship
  families incrementally; AC requires the full ratified set before spec closes.
- **Palette/alignment false positives** on dark/photo-heavy slides → checks stay
  WARN; tolerances tuned on fixtures.
- **Planning agent forgets the family `block_ref`** → diagram.md selector still
  loads (always-on) and names the family; degraded but not broken. T6 fixture guards it.

## Changelog

- 2026-06-30: initial plan. Taxonomy ratified from online survey
  (`notes/diagram-taxonomy.md`); QA dimensions + connector patterns from
  `notes/research-frontend-qa.md`.
