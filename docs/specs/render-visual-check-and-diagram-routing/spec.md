# Spec: render-visual-check-and-diagram-routing

- **Status:** Implementing <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Mode:** full (risk triggers: multi-feature; structural change to the render-completion contract; behavior change to a shared script)
- **Constrained by:** [`diagram-consistency-system`](../diagram-consistency-system/spec.md) — this
  spec reuses its `blocks/diagram*.md` recipes (esp. `diagram.md` §3.1 connector
  topology, incl. ④ bus) and its boundaries (Pillow-only / no new dependency /
  `visual_qa.py` `0/1/2` exit / new checks WARN-first). Those stems must be present
  before EXECUTE.
- **Contract:** none
- **Shape:** mixed (docs/playbooks + scripts + validator)

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

When a deck is **rendered**, the skill must (a) verify every slide **visually** —
not just textually — before it is declared done, using a **self-contained
screenshot path that survives sandboxed / cloud-synced filesystems**; and (b) draw
diagrams from the existing themed, pipeline-safe **recipe library on the first pass**
by closing the **planning→recipe routing gap**, so architecture / flow / pipeline
diagrams look engineered the first time instead of being invented ad-hoc and patched
during review.

This is driven by a real deck-build session (field evidence; findings in
`.context/diagram-render-local-preview-findings.md` and
[`notes/session-evidence.md`](notes/session-evidence.md)) where five failures
compounded:

1. The agent tried to preview slides by starting a **local server** via Claude
   Desktop's Preview MCP (`mcp__Claude_Preview__preview_start`). It failed twice —
   first on a tool-contract mismatch (the tool launches a *named* server from
   `.claude/launch.json`, not a file), then on a real environment break under the
   OneDrive CloudStorage mount: `getcwd: … Operation not permitted` / `pyenv: cannot
   change working directory`. Turns were burned; the agent never got a visual read.
2. The skill's **own** screenshot path (`html2png.py`: headless puppeteer over
   `file://`, explicit `cwd`, no shell/server/port) is immune to that failure — but
   it was never used for the agent's visual read.
3. The skill's per-page **orchestrator** (`prompts/step4/tpl-page-orchestrator.md`)
   already chains Planning → HTML → **Review**, and Stage 3
   (`prompts/step4/tpl-page-review.md`) is *already* a mandatory screenshot +
   `visual_qa.py` gate (min 2 rounds, blocks FINALIZE on exit 1). But the session's
   render was dispatched as ad-hoc **HTML-only** batch agents (Stage 2 only) that
   verified slides **textually** (`python3 -c` regex for `data-card-id` presence +
   non-empty file) and **never ran Stage 3**. The mandatory visual gate exists; it was
   *bypassed* because the render fan-out skipped the orchestration. A card-overflow
   defect shipped ("slide 8 bullets don't fit the card").
4. The **diagram recipes never reached the render agent** for the diagrams the user
   complained about. 16 planning files carried `"block_refs": []`; the
   architecture-diagram recipe (`diagram-architecture`) was routed **zero** times.
   The "interview→retrieval pipeline" and "scaffold→enhance" visuals were planned as
   `list` / `text` cards with no `diagram_type`, so they only *became* diagrams at
   HTML render time — bypassing the entire diagram-consistency-system.
5. `planning_validator.py` has **no check** that a diagram-shaped card routes a
   recipe, so nothing flagged the gap.

The skill already owns the hard parts: `html2png.py` (screenshot), `visual_qa.py`
(Pillow visual assertions incl. diagram theme-binding `DTHEME-01` and cross-slide
`DECK-*`), `page-review-playbook.md` (the screenshot bug-hunt loop), and the
`diagram-consistency-system` recipes (`blocks/diagram*.md` — connector topology math,
node-color discipline, 8px grid, pipeline-safety). This spec **wires those together
and closes the routing gap**; it does not rebuild them and adds **no new dependency**.

### The five concerns

- **A — Canonical visual-read path (guidance).** Document `html2png.py` `file://`
  as the *only* sanctioned way for the agent to obtain its own visual read; forbid
  local servers (`python3 -m http.server`) and the Preview MCP for that purpose;
  scope `open <file>` to a hand-off to the human.
- **B — Render fan-out must not bypass the visual gate.** The mandatory Stage-3 visual
  gate already exists per page; the fix forces every render dispatch to run the full
  per-page orchestration (Planning → HTML → **Review**) — an HTML-only batch is
  forbidden — and backs it with a **mechanical render-completeness gate**: a render is
  not "done" until every slide HTML has a matching `png/slide-*.png` (PNGs are produced
  only by Stage 3, so their presence is the behavioral proof the gate ran) **and** the
  deck passes `visual_qa.py` batch (exit ≠ 1). Reconciled with *no forced preview*
  (§Boundaries); degrades with an announcement when Node/puppeteer is absent.
- **C — Contact-sheet montage for the human.** A Pillow-only script that stitches
  all slide PNGs into one review image the agent surfaces on the review turn —
  replacing the "spin up a preview server" instinct with a deterministic artifact.
- **D — `html2png.py` launch robustness.** `html2png.py` already launches node with an
  explicit `cwd` (so it is *not* the script that hit the session's `getcwd` break — that
  was the login-shell Preview server). D is a defensive hardening: make node's module
  resolution and temp-script write depend on an explicitly chosen, validated directory
  (the `dep_dir` holding `node_modules`, via `cwd`/`NODE_PATH`) rather than on the
  caller's inherited cwd or on `work_dir` happening to sit under `ppt-output` — so a
  single-file render or an awkward cwd cannot break puppeteer resolution.
- **E — First-pass diagram quality via planning routing.** The recognition→tag→route
  rule already exists in `page-planning-playbook.md`, but it also tells planners to
  "leave `block_refs: []` when unsure" — the exact behavior that caused the session
  gap. E **strengthens and enforces** it: fix that "leave empty" guidance, add a
  WARN-level `planning_validator.py` check that *surfaces* diagram-shaped cards missing
  a routed recipe (advisory backstop — not an ERROR that blocks a good deck), and add
  author-time HTML-stage guidance (structure-before-coordinates + a first-pass
  self-check + a complexity budget) so diagrams are drawn from the recipe well the
  first time. Grounded in research (`notes/diagram-first-pass-research.md`).

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines. *Always do*
applies without asking; *Ask first* requires human sign-off before proceeding;
*Never do* is a hard rule, even under time pressure.

### Always do

- Keep every new script and check **Pillow-only** and the skill **runtime-free**
  (HTML/CSS/SVG + stdlib Python + the already-declared `puppeteer`). `visual_qa.py`
  keeps its `0 / 1 / 2` exit contract; new `visual_qa.py`/validator checks emit a
  stable check id and a PASS / WARN / FAIL line.
- Make new diagnostic checks **WARN, not FAIL/ERROR**, first (a check that can
  false-positive must not block a good deck).
- **Announce every degradation.** When Node/puppeteer is unavailable the visual gate
  degrades to a declared skip (textual checks + a loud note to the user), never a
  silent pass and never a hard-fail of the render.
- Bind new diagram guidance to the **existing** `blocks/diagram*.md` recipes by
  reference; do not duplicate recipe bodies. Author every changed skill-facing
  reference in the `AGENTS.md` authoring format (fixed bold-label order, terse,
  progressive disclosure).
- Wire new self-tests and the montage/validator checks into `scripts/smoke_test.py`
  as phases (the repo's gate; there is no pytest/typecheck harness).

### Ask first

- **Making the visual gate cost the full multi-round review loop.** The mandatory
  *floor* is one observed screenshot per slide + a deck-level `visual_qa.py` non-FAIL
  (bounded, cheap). The deeper unbounded `page-review-playbook` bug-hunt stays the
  *quality* practice, not the mechanical floor. Raising the floor to N rounds is a
  cost decision for the human.
- Promoting any new check from WARN to FAIL/ERROR-gating.
- Changing `resource_loader.py` routing or `FIELD_ROUTES` (the design uses the
  existing `block_refs` route and needs no loader change).
- Adding a new render *pipeline stage* or a new gate **script** beyond the montage
  (prefer reusing `visual_qa.py` batch as the mechanical terminal check).

### Never do

- Never add a new top-level repository dependency.
- Never eagerly render or preview when the user has **not** asked to render — the
  gate fires only *inside* an already-invoked render (Step 5c+), where screenshotting
  is cheap and non-LLM. "No forced preview" (opt-in delivery) is preserved.
- Never rely on a **local server or the Preview MCP** for the agent's own visual
  read; never use a pipeline-forbidden CSS technique in any diagram guidance example.
- Never degrade silently, and never hard-fail a render solely because the visual
  gate could not run (missing Node) — degrade and announce.

## Testing Strategy

- **A — guidance present (goal-based).** `grep`/structural assertions that SKILL.md,
  `page-review-playbook.md`, and `cli-cheatsheet.md` carry the canonical-path rule,
  the server/Preview-MCP prohibition + rationale, and the `open`=human-handoff
  scoping. Chosen because the property is mechanically decidable from the text.
- **B — render-completeness gate (TDD + goal-based + manual QA).** TDD: the gate
  (extending `milestone_check.py`) reports not-done on a fixture deck with a slide HTML
  lacking (or older than) its PNG, and done when all PNGs are present + fresh +
  `visual_qa` batch is clean — a behavioral fixture test, not a grep. Goal-based: grep confirms SKILL.md
  forbids HTML-only render fan-out and points to the orchestrator; the Stage-2
  "no screenshot" boundary text is confirmed still present (not duplicated). Manual QA:
  render the sample fixture deck end-to-end and confirm the gate runs, blocks on a
  missing-PNG/seeded-overflow deck, and **degrades with an announced skip** when `node`
  is forced unavailable.
- **C — montage (TDD).** Fixture PNGs → `slide_montage.py` produces one PNG with the
  expected grid dimensions and natural-sorted tile order; Pillow-only; deterministic.
  Self-test written before the script, wired as a smoke phase.
- **D — cwd hardening (TDD).** A test invokes `html2png.py`'s node-launch path with
  the process started from / pointed at a cwd that is not the deck dir and asserts it
  still succeeds (module resolution + temp-script write use an explicitly chosen,
  validated directory). Mirrors `test_html2svg_tmp_isolation.py`.
- **E — diagram routing (TDD + goal-based).** TDD: `planning_validator.py` fixtures —
  a `card_type: diagram` card with no `diagram_type` or unrouted family → the new
  WARN with its stable id; a `list`/`text` card whose headline/body is diagram-shaped
  with no diagram family in `block_refs` → WARN; a correctly-tagged+routed diagram →
  clean; a non-diagram card → clean (no false positive). Goal-based: greps confirm
  `page-planning-playbook.md` gained the recognition→tag→route rule and
  `page-html-playbook.md` Phase 8 gained the diagram first-pass self-check referencing
  `blocks/diagram.md` §3.1 + pipeline-safety.
- **Regression.** `visual_qa.py` over the pre-existing fixture set produces
  byte-identical verdicts/exit codes for inputs that trip no new check (new checks are
  strictly additive). `scripts/smoke_test.py` passes with all new phases wired in and
  no new dependency.

## Acceptance Criteria

**A — canonical visual-read path**
- [x] SKILL.md and `references/playbooks/step4/page-review-playbook.md` state that the
  agent's own visual read is obtained via `html2png.py` (`file://`, headless
  puppeteer), and **explicitly forbid** local servers (`python3 -m http.server`) and
  the Preview MCP (`mcp__Claude_Preview`) for that purpose, with the one-line reason
  (ports/shells/`getcwd`+pyenv breakage under CloudStorage/OneDrive). `open <file>` is
  scoped to a hand-off to the human, not agent verification.
- [x] `references/cli-cheatsheet.md` lists `html2png.py` as the visual-check entry
  point for the review loop.

**B — render fan-out must not bypass the visual gate** (reuses the *existing* Stage-3
gate; does not duplicate or relocate it)
- [x] SKILL.md's render-dispatch guidance (Step 5c/6) states that render fan-out **must
  run the full per-page orchestration incl. Stage 3 Review**
  (`prompts/step4/tpl-page-orchestrator.md`); dispatching **HTML-only** batch agents
  that skip Stage 3 is **explicitly forbidden**. The existing Stage-2 boundary
  ("只写 HTML，不截图，不做 QA" in `tpl-page-html.md` / `page-html-playbook.md` Phase 8)
  is **left intact** — B does not add screenshotting to the HTML stage.
- [x] A **mechanical render-completeness gate** is added by **extending
  `milestone_check.py`** (its `check_step4`/`check_step5` already enforce
  `len(pngs) == pages` — the per-slide-PNG half exists today; `deck_probe.py` is the
  assimilate-slides external-deck probe and is **not** touched). The extension: run
  `visual_qa.py` **batch** over the deck (`png/` + `--html-dir` + `--planning-dir` +
  `--style`) and require exit ≠ 1, and add **freshness** — each `png/slide-*.png` must
  have mtime ≥ its matching `slides/slide-*.html` (a stale PNG from a prior render must
  not satisfy the gate). PNG-per-slide + freshness is the behavioral proof Stage 3
  re-ran on the current HTML (Stage 2 produces no PNG).
- [x] The render-done step in SKILL.md (Step 5c/6) **invokes** this gate
  (`milestone_check.py <stage> --output-dir <deck>`) — naming the invocation point, so
  the residual gap that defeated the *existing* PNG-count check (nothing ran it) is
  closed. The render flow additionally clears/regenerates `png/` at render start so the
  freshness check is meaningful.
- [x] The gate fires **only within an invoked render** (Step 5c+); it does not cause
  eager/forced preview when the user has not asked to render (SKILL.md Step 6 "不主动/
  提前" wording is preserved and cross-referenced).
- [x] When `node`/puppeteer is unavailable the gate **degrades to an announced skip**
  (a message to the user naming the missing capability), mirroring the existing
  "no Node → preview.html only" degradation; it never hard-fails the render and never
  passes silently.
- [x] A `smoke_test.py` phase asserts the render-completeness gate's **behavior** on a
  fixture deck: a deck with a slide HTML but no matching PNG → gate reports not-done;
  a deck with all PNGs present + `visual_qa` clean → gate reports done (not a
  grep-for-text assertion).

**C — contact-sheet montage**
- [x] `scripts/slide_montage.py` (Pillow-only, stdlib + Pillow) reads a deck's `png/`
  directory and writes a single natural-sorted contact-sheet PNG
  (`<deck-slug>-contact-sheet.png`) with a deterministic grid; it fails gracefully
  (clear message, non-zero exit) when the png dir is empty/missing.
- [x] The post-render notify step (SKILL.md Step 6 / `print-combiner`-adjacent
  guidance) offers the contact sheet as an artifact the agent surfaces for the human
  review turn, in place of starting a preview server.
- [x] A self-test (fixture PNGs) asserts montage output dimensions and tile ordering;
  wired as a smoke phase.

**D — `html2png.py` cwd hardening**
- [x] `html2png.py` makes puppeteer **module resolution** independent of where
  `work_dir` sits: it sets `NODE_PATH` to `<dep_dir>/node_modules` (and/or runs node
  with `cwd = dep_dir`), so a single-file render whose `parent.parent` is not under
  `ppt-output` resolves puppeteer once `ensure_puppeteer` has provisioned
  `node_modules` in the chosen `dep_dir`. The temp `.js` write prefers `dep_dir` and
  **falls back to the system temp dir if `dep_dir` is not writable** (resolution is
  `NODE_PATH`-driven, so script location is otherwise free). (html2png already passes an
  explicit `cwd`, so this is module-resolution robustness, not a fix for the session's
  login-shell `getcwd` break.) Existing install-location behavior (`get_dep_dir` /
  `ppt-output`) is preserved.
- [x] A self-test asserts the node-launch path succeeds when the process's cwd is not
  the deck directory (mirrors `test_html2svg_tmp_isolation.py`).

**E — first-pass diagram quality via planning routing**
- [x] `references/playbooks/step4/page-planning-playbook.md`'s existing recognition →
  tag → route guidance is **strengthened**: the "leave `block_refs: []` when unsure"
  instruction (line ~61) is replaced with "when a card is diagram-shaped, tag
  `card_type: diagram` + an explicit `diagram_type` and route the matching family file
  into `resources.block_refs`" (families per the `blocks/diagram.md` selector:
  `diagram-architecture` / `diagram-process-flow` / `diagram-project` /
  `diagram-concept`).
- [x] `planning_validator.py` gains a **WARN-level** check with a stable id
  `DIAG-ROUTE-01` that fires when (a) a `card_type: diagram` card lacks a
  `diagram_type`, has an **unknown/typo `diagram_type`** (resolves to no family), or its
  matching family file is absent from `block_refs`; or (b) a card typed
  `list`/`text`/`process` whose headline/body matches a **precision-tuned diagram-shape
  cue set** (a curated subset of the lexicon — some bare high-signal terms like
  `architecture` / `topology` / `funnel`, some multi-word to avoid false positives; not
  every lexicon word, deliberately) and has no diagram family in `block_refs`. **WARN
  only** (the shape heuristic can false-positive, so per the diagram-consistency-system
  boundary a new check starts WARN, not ERROR); ERROR count and exit semantics
  unchanged; a plain non-diagram card produces no finding on the fixture set. Promotion
  to ERROR is Ask-first.
- [x] The `diagram_type → family` map in `planning_validator.py` is guarded against
  drift from `blocks/diagram.md`: a `check_skill.py`/smoke assertion verifies the
  validator's map matches the selector table in `blocks/diagram.md` (single source of
  truth; lockstep consumer recorded).
- [x] `page-planning-playbook.md` records a **diagram complexity budget** grounded in
  the research, **as documented planning guidance**: cap ≈ **8–12 nodes / 10–15 edges**
  per diagram; above it, plan a split into sub-diagrams; flag dense many-to-many for
  **bus topology** (`blocks/diagram.md` §3.1 ④). (Planning JSON carries no node/edge
  count field, so this is authoring guidance, not a mechanical validator check — no
  claim that an over-budget diagram is auto-caught.)
- [x] The HTML-stage guidance — `page-html-playbook.md` **and** the render prompt
  template `references/prompts/step4/tpl-page-html.md` (the file assembled into
  `runtime/prompt-page-html-N.md` that render agents read) — gains a
  **structure-before-coordinates** author-time step for diagram cards: the agent first
  states the diagram's nodes + edges (and any named zones) and a layer/grid assignment,
  then renders with **CSS-grid-by-layer placement + algebraic CSS-variable geometry**
  (`--grid-unit` / `--node-w` / `--node-h` so connector anchors are computed, not
  drifting literals) rather than hand-placing free SVG coordinates. Low-install
  approximation of deterministic layout; no layout-engine dependency.
- [x] `page-html-playbook.md` Phase 8 gains a **diagram first-pass self-check** (fires
  only when the page carries a diagram; a *static* check on the code/data, consistent
  with the Stage-2 "no screenshot" boundary) referencing `blocks/diagram.md` §3.1
  connector topology + the pipeline-safety self-check, plus the research's pre-render
  assertions — every connector endpoint **clamped inside the target node's box** (no
  source-center-y copy), fan-in distributed, **no node overflow / label clipping**, no
  node overlap — so the render agent validates the diagram at author time rather than
  deferring the whole burden to Stage-3 review.
- [x] The added guidance is grounded in and cites `notes/diagram-first-pass-research.md`
  (external, citation-backed synthesis) and reuses the existing recipe primitives; no
  recipe body is duplicated, and no layout-engine dependency (dagre/ELK) is added.

**Cross-cutting**
- [x] No new top-level dependency; `requirements.txt`/`package.json` unchanged.
- [x] `visual_qa.py` regression: byte-identical verdicts/exit codes on the pre-existing
  fixture set for inputs that trip no new check.
- [x] `scripts/smoke_test.py` passes with all new phases wired in.
- [x] `scripts/check_skill.py` passes (no doc/code contract drift introduced).

## Assumptions

- Technical: `html2png.py` renders HTML→PNG via headless puppeteer over `file://`
  with `page.setRequestInterception` blocking non-`file://`/`data:` egress, launching
  `node` with `cwd=work_dir` and writing a temp `.js`; puppeteer is auto-installed via
  `npm ci` in the `ppt-output` dep dir (source: `scripts/html2png.py`).
- Technical: the Preview MCP (`mcp__Claude_Preview__preview_start`) launches a *named*
  server from `.claude/launch.json` through a login shell; under a OneDrive
  CloudStorage cwd it fails with `getcwd … Operation not permitted` + pyenv, whereas
  direct python/node subprocesses under the same mount succeed (source: session
  transcript, `notes/session-evidence.md`).
- Technical: render is done by parallel `Agent` subagents reading
  `runtime/prompt-page-html-N.md`; their completion contract
  (`page-html-playbook.md` Phase 8) is textual only, and in the session they verified
  only textually (source: `notes/session-evidence.md`, `page-html-playbook.md` Phase 8).
- Technical: `visual_qa.py` is Pillow-only, exit `0/1/2`, batch mode iterates
  `slide-*.png` and already carries diagram theme-binding (`DTHEME-01`) and cross-slide
  (`DECK-*`) checks (source: `scripts/visual_qa.py`, `diagram-consistency-system` spec).
- Technical: the diagram recipe library (`blocks/diagram.md` selector + family files)
  is complete and loads on demand via the existing `block_refs` route; planning
  frequently leaves `block_refs: []` and does not tag diagram-shaped cards, so recipes
  don't load (source: `blocks/diagram.md`, session planning files — 16× `block_refs: []`,
  `diagram-architecture` routed 0×).
- Technical: a Pillow thumbnail/montage pattern already exists to reuse
  (source: `scripts/build_hero.py:make_thumbnail`).
- Technical: the repo gate is `scripts/smoke_test.py` (phased); there is no
  pytest/typecheck harness (source: `diagram-consistency-system` spec, repo layout).
- Process: editing `references/`, `scripts/`, playbooks, and `planning_validator.py`
  is a normal spec/PR, not an RFC trigger (source: `docs/CONVENTIONS.md`).
- Product: the deliverable is a spec + plan for human approval before EXECUTE; the
  mandatory-review *cost* (floor vs. full loop) is an explicit Ask-first decision
  (source: user direction, this session; memory `ppt-no-forced-preview`).
