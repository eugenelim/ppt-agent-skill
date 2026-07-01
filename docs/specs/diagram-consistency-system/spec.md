# Spec: diagram-consistency-system

- **Status:** Implementing <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Contract:** none
- **Shape:** mixed

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The skill produces **diagrams that look engineered, not improvised** — and it
holds that quality *consistently across a whole deck*. The driver is the class
of diagram a slide author actually needs and that the chart templates do not
cover: **architecture views** (layered/tiered stacks, component box-and-line,
grouped-container "cloud" topologies, data-flow pipelines, networks) and
**project-management views** (Gantt/roadmap, swimlane/phase, milestone,
RACI/responsibility matrix, dependency network, org chart), alongside the
existing concept diagrams (pyramid, flowchart, hub-spoke, layers, cycle) and
timelines.

Today these are left to ad-hoc per-slide invention: `blocks/diagram.md` and
`blocks/timeline.md` give three lines of mood ("pick whatever looks best") with
no templates and — critically — **no theming**, so a diagram's colors and type
do not inherit the deck's design system the way a chart's do. The result is
visual inconsistency: every diagram is a fresh guess, and nothing makes slide N
look like it belongs with slide N−1.

A deck author gets, after this work: per-type **recipes** (modeled on the
copy-ready `references/charts/` pattern) that bind every color and font to the
deck's CSS variables, draw connectors and arrows in a way that survives the
HTML→SVG→PPTX pipeline, and keep nodes grid-aligned and consistently sized; plus
**verification controls** that check the visual-consistency dimensions a rigorous
design review checks — palette/theme adherence, type-scale, alignment and
spacing rhythm, corner-radius consistency, element-size consistency, diagram
theme-binding — both per page and, for the first time, **across the deck** (does
this slide belong with the others?).

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines.
*Always do* applies without asking; *Ask first* requires human sign-off
before proceeding; *Never do* is a hard rule, even under time pressure.

### Always do

- Bind every color and typography value in a diagram recipe to the deck's CSS
  variables (`--accent-1..4`, `--card-bg-from/to`, `--card-border`,
  `--card-radius`, `--text-primary/secondary`, `--font-primary`). A diagram
  never invents its own palette.
- Obey `references/pipeline-compat.md` in every recipe: arrowheads as inline SVG
  `<polygon>`, connectors as real `<div>` or SVG `<line>`/`<path>`, all text as
  HTML elements (never SVG `<text>`), labels overlaid in HTML.
- Give every recipe the charts-style completeness set: a one-line *when to use*,
  a JSON data shape, at least one paste-ready HTML/CSS template, a self-check
  list, and a pipeline-safety checklist — matching `references/charts/basic.md`.
- Author every changed/added skill-facing reference (recipe files, playbook
  sections) in the authoring format recorded in `AGENTS.md`: the fixed bold-label
  section order, terse/token-efficient wording, and progressive disclosure (thin
  selector → on-demand detail). The agentskills.io-compliant **frontmatter**
  applies to `SKILL.md` files only — recipe/playbook reference files carry no
  frontmatter.
- Keep `scripts/visual_qa.py` Pillow-only and preserve its `0 / 1 / 2` exit
  contract; new checks emit a stable check id and a PASS / WARN / FAIL line.

### Ask first

- Adding a new routed resource directory, or changing `resource_loader.py`
  routing / `FIELD_ROUTES` (the intended design loads recipes via the existing
  `block_refs` route and needs no loader change).
- Making any new visual check **FAIL-gating** rather than WARN — a check that can
  false-positive must start as WARN so it cannot block FINALIZE on a good slide.
- Expanding scope to the other block types (`comparison`, `matrix-chart`,
  `people`, `quote`) beyond `diagram` and `timeline`.

### Never do

- Never add a new top-level repository dependency; `visual_qa.py` stays
  Pillow-only and the skill stays runtime-free HTML/CSS/SVG.
- Never use a pipeline-forbidden technique in a diagram recipe — no SVG `<text>`,
  no CSS-border triangles (the `width:0` trick), no `::before`/`::after` for
  visual content, no `mask-image` / `conic-gradient` / `background-clip:text` —
  even when it looks better in a browser.
- Never inline a per-type recipe template into the always-loaded selector
  `blocks/diagram.md` — it stays under a fixed line budget and only points to
  family files; per-type recipes load only via explicit `block_refs`. (The
  selector cannot stop a planning agent from over-listing refs, so the *testable*
  invariant is the selector's own content, not the agent's JSON output — no
  context-bloat regression baked into the always-loaded file.)

## Testing Strategy

- **Recipe completeness & pipeline-safety** — goal-based check. A structural lint
  (small script or committed `grep` assertions) over the recipe files verifies
  each recipe carries the five required sections, contains no pipeline-forbidden
  technique, and uses only CSS-variable colors (bar the two documented trend
  colors). Chosen because the property is mechanically decidable from the text.
- **New `visual_qa.py` checks** (palette/theme adherence, hardcoded-color
  detection, type-scale presence, corner-radius consistency, element-size and
  alignment/grid rhythm, diagram theme-binding, deck-level cross-slide aggregate)
  — fixture-driven self-tests, written before the checks (TDD-style). Crafted
  PNG/HTML fixtures assert each check's status and the process exit code. The repo
  has **no pytest/typecheck harness**; the gate is `scripts/smoke_test.py` (a
  phased runner), so these self-tests and the recipe lint are wired in as
  smoke-test phases. Chosen because each check is a compressible invariant over an
  input image/HTML and is the load-bearing logic.
- **Recipes render and theme correctly** — visual / manual QA, exercised by
  rendering one representative diagram per family through `html2png.py` under at
  least three `style.json` variants and confirming colors/type are inherited from
  `:root` and `visual_qa.py` returns non-FAIL. Chosen because "themes correctly /
  looks engineered" is a perceptual outcome no unit test fully captures.
- **Playbook additions, AGENTS.md format, and contradiction fix** — goal-based
  check. `grep`/structural assertions confirm the consistency-scan pass and
  pipeline-safety pointers exist, the AGENTS.md authoring-format section exists,
  `design-specs.md` §E no longer asserts the forbidden features are freely usable,
  and the `css-weapons.md` entries using forbidden techniques carry a
  pipeline-safety note.

## Acceptance Criteria

- [x] Every diagram type in the ratified taxonomy (enumerated in
  [`plan.md`](plan.md) §Design, grounded in `notes/diagram-taxonomy.md`) has a
  recipe carrying the five canonical bold-label markers — `**何时用**` (when to
  use), `**数据格式**` (JSON data shape), `**模板**` (≥1 paste-ready HTML/CSS
  block), `**自检**` (self-check), and `**管线安全**` (pipeline-safety) — modeled
  on `references/charts/basic.md`'s bold-label structure, with `**管线安全**`
  pinned as a separate block (charts fold safety into `**自检**`; diagrams, being
  more pipeline-risky, pin it explicitly).
- [x] The taxonomy covers at least four families — architecture views, process &
  flow, project-management views, hierarchy & relationship — and explicitly
  includes layered/tiered architecture, grouped-container (cloud) architecture,
  data-flow pipeline, Gantt/roadmap, swimlane, RACI matrix, dependency network,
  and org-chart/hierarchy.
- [x] In every recipe template, all color and typography values are CSS variables;
  the only permitted hardcoded colors are the documented trend green (`#22c55e`)
  and red (`#ef4444`); a `grep` finds no other hardcoded hex/`rgb()` in the recipe
  templates.
- [x] No recipe template uses a pipeline-forbidden technique: zero SVG `<text>`,
  zero CSS-border triangles, zero `::before`/`::after` carrying visual content,
  and none of `mask-image` / `conic-gradient` / `background-clip:text`. Connectors
  are real `<div>` or SVG `<line>`/`<path>`; arrowheads are SVG `<polygon>`.
- [x] One representative diagram per family renders without error via
  `html2png.py` and inherits colors/typography from `:root` under three style
  variants spanning the deck's range — a dark, a light, and an editorial/cultural
  style drawn from `references/styles/` (e.g. `dark_tech`, `blue_white`,
  `mocha_editorial`), each injected into the sample's `:root`; `visual_qa.py`
  returns a non-FAIL exit on each.
- [x] The recipe library is delivered to the page-HTML agent per diagram
  type/family in use (via the existing `block_refs` route), not as a single
  always-injected blob; `blocks/diagram.md` is a thin selector/overview that
  carries the theming contract and shared connector/arrow primitives and points
  to the family recipe files. The planning playbook documents how the right
  recipe is selected.
- [x] `visual_qa.py` gains per-page checks, each with a stable id and
  PASS/WARN/FAIL output, Pillow-only, preserving the `0/1/2` exit contract:
  palette/theme adherence (off-palette color ratio against the deck palette),
  hardcoded-color detection in the HTML, type-scale presence (a detectable size
  hierarchy), corner-radius consistency, and element-size / alignment grid rhythm.
- [x] `visual_qa.py` batch mode emits a **deck-level cross-slide consistency
  aggregate** — palette drift, background/family consistency, and type-scale
  drift measured across all pages — with its own check ids and a deck-level
  verdict, requiring no new pipeline stage. First-cut tolerances (provisional,
  recorded as named constants in the script and calibrated on fixtures): a slide
  whose palette-token set has Jaccard similarity < 0.5 against the deck-modal
  palette (`DECK-PAL-01`), whose dominant-background RGB distance from the deck
  mode > 48 (`DECK-BG-01`), or whose top font-size set differs from the deck mode
  by > 2 sizes (`DECK-TYPE-01`) → WARN.
- [x] A diagram **theme-binding** check flags a diagram whose rendered colors fall
  outside the deck palette, surfaced both in `visual_qa.py` and as a P-level item
  in `page-review-playbook.md`.
- [x] `page-review-playbook.md` gains a *consistency scan* pass that enumerates the
  new visual dimensions (palette adherence, type-scale, alignment/spacing rhythm,
  corner-radius/border, element-size consistency, diagram theming, optical
  alignment, cross-slide belonging), maps each to a P0/P1/P2 severity, and
  references the corresponding `visual_qa.py` check ids. The pass **reconciles
  with the existing** P1-5 (hardcoded color) and P2-1 (corner-radius) items —
  the new `HEX-01`/`RAD-01` check ids are cross-referenced to P1-5/P2-1 rather
  than creating a second, divergent severity for the same defect.
- [x] The `design-specs.md` §E ↔ `pipeline-compat.md` contradiction is resolved:
  §E no longer lists `mask-image` / `conic-gradient` / `background-clip:text` /
  pseudo-elements as "freely usable" but points to `pipeline-compat.md` as
  authoritative and marks them fallback-only/degrading; `css-weapons.md` entries
  that use a pipeline-forbidden technique carry an inline pipeline-safety note
  naming the pipeline-safe alternative.
- [x] `AGENTS.md` carries a **skill & reference authoring format** section
  specifying two concrete formats so authored content is consistent: (a) for
  `SKILL.md` files — the agentskills.io-compliant frontmatter set (`name`,
  `description`, `license`, `compatibility`, `metadata`, `allowed-tools`) with a
  terse, trigger-friendly `description` and progressive disclosure (thin SKILL
  body → `references/` detail loaded on demand); (b) for reference recipe files
  (which carry no frontmatter) — the fixed bold-label section order
  (`**何时用** / **数据格式** / **模板** / **自检** / **管线安全**`) and terse,
  token-efficient wording. Reference-file conformance is enforced by the recipe
  lint (see below); the section cites `tools/lint-agent-artifacts.py` as the
  frontmatter lint **only where that lint is installed** (it is not present in
  this repo today).
- [x] A regression run of `visual_qa.py` over the pre-existing sample/fixture set
  produces byte-identical verdicts and exit codes before and after this change
  for any input that trips no new check (the new checks are strictly additive).
- [x] The repo gate `scripts/smoke_test.py` passes with the recipe lint and the
  new `visual_qa.py` self-tests wired in as phases, and no new dependency is
  introduced (Pillow-only).

## Assumptions

- Technical: The copy-ready recipe pattern to emulate (when-to-use + JSON shape +
  paste-ready CSS-variable template + self-check + pipeline-safety) already exists
  for charts (source: `references/charts/basic.md`).
- Technical: `diagram`/`timeline` blocks currently carry only vague "design soul"
  prose with no templates and no CSS-variable theming (source:
  `references/blocks/diagram.md`, `references/blocks/timeline.md`).
- Technical: Diagrams must obey the HTML→SVG→PPTX rules — no SVG `<text>`, SVG
  `<polygon>` arrowheads, no CSS-border triangles, no `::before/::after`
  decoration, no `mask-image`/`conic-gradient`/`background-clip:text` (source:
  `references/pipeline-compat.md`).
- Technical: `design-specs.md` §E lists those forbidden features as "freely
  usable", contradicting pipeline-compat; `html2svg.py` has fallback coverage for
  six of them but the result degrades (source:
  `references/design-runtime/design-specs.md` §E, `references/pipeline-compat.md` §1).
- Technical: `resource_loader.py resolve` routes `card_type` → `blocks/<id>.md`
  and `block_refs` → `blocks/<id>.md`, and silently skips missing files; family
  recipe files placed under `blocks/` load on demand via `block_refs` with no
  loader code change (source: `scripts/resource_loader.py` `FIELD_ROUTES`,
  `REF_FIELD_ROUTES`, `resolve_resources`).
- Technical: `visual_qa.py` is Pillow-only, exit `0/1/2`, current checks
  DIM/BLANK/VTXT/CUT/CONT/SIZE/CARD/DENS + HTML-01..08; the per-page review/fix
  loop with screenshots is `page-review-playbook.md`, ending on `visual_qa.py`
  (source: `scripts/visual_qa.py`, `references/playbooks/step4/page-review-playbook.md`).
- Technical: Deck-level consistency is enforceable in `visual_qa.py` batch mode,
  which already iterates all `slide-*.png`, rather than as a new pipeline stage
  (source: `scripts/visual_qa.py` `main()` batch loop).
- Technical: Established best-practice for pipeline-safe diagrams is CSS-Grid/Flex
  node placement + inline-SVG connectors with `<polygon>`/`<marker>` arrowheads
  and CSS-variable theming; the full design-review consistency dimension set
  (grid/spacing rhythm, type-scale, palette adherence, element-size, corner-radius,
  cross-slide coherence, optical alignment, gestalt grouping, shadow/elevation) is
  grounded in a citation-backed survey recorded in `notes/research-frontend-qa.md`
  (source: research synthesis, 2026-06-30; see notes for URLs).
- Process: Editing existing `references/` files, `scripts/`, and `AGENTS.md` is a
  normal spec/PR, not an RFC trigger — no new top-level directory or convention
  removal (source: `docs/CONVENTIONS.md` §3–4).
- Product: Primary drivers are architecture views and project-management views
  that don't fit the chart templates; diagrams currently have no theming; one
  spec covers both the recipes and the verification; the deck-level consistency
  pass is in scope; the type taxonomy is grounded in an online survey of leading
  diagram taxonomies; QA uses both automated checks and an LLM scan checklist; and
  an AGENTS.md skill-authoring format is added (source: user confirmation
  2026-06-30).
