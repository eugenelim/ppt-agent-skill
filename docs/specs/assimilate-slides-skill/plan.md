# Plan: assimilate-slides skill + icon library

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. When it changes
> substantially, note why in the changelog at the bottom.

## Approach

Build the tooling first (skill docs, icon library, hero backfill), then
**dogfood** it: run the freshly-written skill against a maintainer-supplied
`.pptx` to produce real primitives + icons. Dogfooding is the skill's manual-QA
verification — the best proof the procedure works is that following it yields a
clean, gated assimilation. The riskiest parts are (a) the icon library's
search/validate logic (only TDD-worthy code here) and (b) keeping every
committed artifact free of the source's identity — a scrub discipline enforced
by the skill's own procedure and re-checked at review.

The skill is documentation with progressive disclosure: a thin `SKILL.md` spine
plus six on-demand reference files, each mapping to one machinery cluster the
[mapping investigation](spec.md#assumptions) grounded. Nothing here changes the
shipped PPT product surface or any validator enum.

### Declined-pattern register

- Tempted to mint a `worksheet`-style validator `card_type` for the new
  architecture primitives; **declining** — the existing `block_refs` mechanism
  loads them, exactly as `worksheet.md` / `advisory-brief.md` do; a new enum is
  a public-interface change and out of scope.
- Tempted to add a dependency for icon rendering / SVG parsing (`svgpathtools`,
  `cairosvg`); **declining** — stdlib `xml`/`json`/`re` cover catalog search and
  pipeline-safety validation; the mock proves visual correctness.
- Tempted to build an HTML icon-gallery viewer + fuzzy search index;
  **declining** — a stdlib substring/token search over `catalog.json` is enough
  for the library's current size; revisit if it grows past hundreds.
- Tempted to auto-regenerate the hero collage; **declining** — the spec makes it
  an explicit maintainer prompt (Ask first).

## Constraints

No ADR/RFC governs this. Conforms to `AGENTS.md` (no-PII §39; skill authoring
format §"Skill & reference authoring format"; keep-changes-minimal) and the
recipe/style conventions the two prior assimilation specs established.

## Construction tests

**Integration tests:** the dogfood run itself is the end-to-end integration
test — the skill's procedure executed against a real deck, gated by
`smoke_test.py`, `lint_diagram_recipes.py`, `check_skill.py`, and
`icon_search.py --validate`.
**Manual verification:** trace-through of `SKILL.md` against the two prior
assimilation specs; visual QA of the 1280×720 mock rendering.

## Tasks

### T1: Stand up the searchable icon library subsystem

**Depends on:** none

**Tests:** (TDD for `icon_search.py`)
- `search("database")` returns entries whose id/name/tags/keywords contain the
  token; ranking puts id/name matches above keyword-only matches.
- `search` is case-insensitive and matches on any whitespace/comma token.
- `validate` fails a catalog entry whose `file` is missing on disk.
- `validate` fails an SVG containing `<text`, `mask-image`, `conic-gradient`,
  `background-image:url(`, or a missing `viewBox`.
- `validate` passes a clean monoline `currentColor` SVG present in the catalog.
- `list` emits every catalog id; `--json` output parses.

**Approach:**
- `assets/icons/catalog.json` — array of `{id, name, category, tags[],
  keywords[], viewBox, file, provenance}` (provenance is a generic string,
  never a client name).
- `scripts/icon_search.py` (stdlib only): subcommands / flags `search <query>`,
  `--list`, `--category <c>`, `--json`, `--validate`. Validate cross-checks
  catalog↔`assets/icons/*.svg` and runs the pipeline-safe regex set (shared
  wording with `references/pipeline-compat.md`).
- `references/icons.md` — authoring contract (24-grid, ~1.5–2px stroke,
  `currentColor`, normalized `viewBox`, no `<text>`, no forbidden CSS), the
  idea-not-copy provenance rule, and search usage.
- `scripts/test_icon_search.py` — the tests above (standalone, exit 0/1, per the
  repo's "no pytest harness" convention; runnable via `smoke_test.py`).
- `scripts/deck_probe.py` + `scripts/test_deck_probe.py` — the deterministic
  ingest probe (stdlib + `python-pptx`/`lxml` only, no ad-hoc installs) and its
  test against a committed HTML mock fixture. Removes the "agent improvises a
  parser and pip-installs a random library" failure mode.

**Done when:** `python3 scripts/test_icon_search.py`,
`python3 scripts/test_deck_probe.py`, and `python3 scripts/icon_search.py
--validate` all exit 0.

### T2: Backfill `build_hero.py` coverage (self-contained, merge-safe)

**Depends on:** none

**Tests:** (goal-based)
- A one-liner that **imports `gallery.py`'s `collect_all_styles()`** (the
  canonical enumerator — it skips `index.md`/`README.md`, whose placeholder /
  example `style_id` blocks would otherwise pollute the set) asserts that set of
  ids equals the union of all `build_hero.py` CATEGORIES `ids` (no missing, no
  extra) — passing on **this PR's own tree**. Reusing the enumerator (not
  re-deriving the block-scan) prevents AC↔verifier drift.

**Approach:**
- Add `graphite_gold` → `dark_professional` and `editorial_paper` +
  `schematic_blueprint` → `light_premium` in `scripts/build_hero.py`. This is
  the **identical** addition the in-flight `regenerate-hero-image` branch makes,
  so a 3-way merge sees the same change on both sides — conflict-free. **Do not
  touch `scripts/gallery.py`** (the `gallery_face` / two-mock convention is that
  branch's; editing it would be a real conflict). Editing only the CATEGORIES
  `ids` keeps the coverage AC verifiable here without depending on merge order.

**Done when:** the set-equality one-liner prints OK on this tree.

### T3: Write `assimilate-slides` SKILL.md + six reference files

**Depends on:** T1 (so `build-and-ship.md` and `extract-icons.md` can cite the
real `icon_search.py` interface)

**Tests:** (goal-based + manual QA)
- Frontmatter keys ⊆ agentskills.io pinned set; `description` is one
  `Use when …` sentence (grep).
- Every path token the skill names (`scripts/*.py`, `references/**`,
  `assets/icons/`, `docs/backlog.md`) resolves (`test -f`/`test -d` sweep).
- **Load-bearing trace-through:** a recorded table mapping each skill step to
  the concrete artifact the two prior specs (`graphite-gold-advisory-extract`,
  `schematic-blueprint-runbook-restyle`) produced — this is the non-circular
  proof the *written procedure* is followable by a fresh agent (the dogfood run
  only proves it yields gate-passing output).
- `build-and-ship.md` states that skill-doc verification is this grep + path
  sweep + trace-through, and that `check_skill.py` (which does not scan
  `.claude/skills/**`) guards the product surface, not the skill.

**Approach:**
- `SKILL.md`: frontmatter + thin 10-phase spine (INGEST → CLASSIFY → EXTRACT
  STYLE → INDEX → EXTRACT PRIMITIVES → EXTRACT ICONS → NARRATIVE/PLAYBOOKS →
  MOCK+GALLERY → HERO PROMPT → GATES+SHIP), each phase 2–4 lines + a pointer.
- Six `references/*.md` per the spec ACs. Reference (never restate) the
  canonical machinery docs: `pipeline-compat.md`, `blocks/README.md`,
  `styles/index.md §5`, `principles/narrative-arc.md`.
- `build-and-ship.md` teaches the **two-mock convention**: build both a cover
  mock `<id>.cover.html` and a detailed mock `<id>.html` (each 1280×720,
  pipeline-safe); `gallery.py`'s `gallery_face(sid)` promotes the cover to the
  gallery card + hero thumbnail while the detailed mock remains the `smoke_test`
  fixture + spec deliverable; the hero collage regenerates from cover faces.

**Done when:** frontmatter grep clean, path sweep clean, trace-through recorded.

### T4: Dogfood — ingest, scrub, classify the supplied source

**Depends on:** T3

**Tests:** (manual QA)
- Classification recorded: `schematic_blueprint` match, **no new style**.
- Image-heavy header/divider/collage slides enumerated as discarded (area+text
  heuristic).
- **Scrub checklist recorded** in the run spec: each AGENTS.md §39 identifier
  class — deck name, client, customer, employer, project code-name, personal
  names, emails, internal URLs, ticket IDs, product names — checked against the
  full diff and marked clear. (Re-run at T8 against the final diff.)

**Approach:**
- Create the generic per-run spec `docs/specs/architecture-diagram-primitives/`
  via the skill's process (no client name anywhere).
- Use the scratch analyzer (gitignored `.context/`) to inventory palette, type,
  diagram composition, and image-heavy slides; keep only generic findings.

**Done when:** the generic spec exists with classification + discard list + the
recorded scrub checklist.

### T5: Dogfood — extract architecture-canvas primitives

**Depends on:** T4

**Tests:** (goal-based)
- `lint_diagram_recipes.py` passes with the new recipe (5 markers present; no
  forbidden techniques; CSS-var-bound; icons inlined verbatim, not `url()`/`<img>`).

**Approach:**
- **Reconcile against the existing family first:** `references/blocks/diagram-architecture.md`
  already carries `architecture-component` / `architecture-deployment` /
  `er-data-model` / `layers`. Add the deck's signature **icon-node layered-zone
  canvas + labeled connectors** recipe *into that file* (it is auto-globbed by
  `lint_diagram_recipes.py`'s `diagram*.md` glob, so no target-list edit and no
  orphan). Only if the primitive is genuinely distinct from that family do we
  add a separate `references/blocks/*.md` file — with a stated justification and
  an explicit append to the lint target list. Update `blocks/README.md` if a new
  file is created.

**Done when:** `lint_diagram_recipes.py` exits 0 and the recipe is registered
(auto-globbed in-family, or appended + README-registered if standalone).

### T6: Dogfood — seed the icon library (idea-level redraws)

**Depends on:** T1, T4

**Tests:** (goal-based)
- New SVGs in `assets/icons/` with catalog entries — enough to demonstrate
  search across ≥2 catalog categories (≥8, matching the concepts the source's
  canvas actually uses); `icon_search.py --validate` exits 0; representative
  searches return the seeded icons; each SVG inlines cleanly (has `viewBox`, no
  `<text>`/forbidden CSS).

**Approach:**
- Redraw the architecture concepts the source canvas uses (e.g. database,
  pipeline, model, dashboard, api, storage, security, users, sync, document) as
  clean monoline `currentColor` SVGs — idea-level, never traced. Generic
  `provenance` string (no source identity).

**Done when:** validate clean; searches hit; a mock inlines an icon and renders.

### T7: Dogfood — narrative-arc / playbook review

**Depends on:** T4

**Tests:** (goal-based)
- The run spec records a one-line archetype decision: `new: <name>` or `none`.
- If a flavor is added, `narrative-arc.md` gains a guidance-only section and no
  validator/enum/`page_type` change is made (grep confirms the diff touches only
  docs). If any engine idea is deferred, a `## architecture-diagram-primitives`
  heading is added to `docs/backlog.md` and the run-spec criterion cites it.

**Approach:**
- Assess the source's narrative (offering/solution session). Add a guidance
  section if warranted; otherwise record `none`.

**Done when:** the one-line archetype decision is recorded; no engine change in
the diff; any deferral has a live backlog anchor.

### T8: Build mock, regenerate gallery, run gates, ship both specs

**Depends on:** T2, T5, T6, T7

**Tests:** (goal-based + manual QA)
- Detailed primitives-demo mock at `ppt-output/style-gallery/` renders 1280×720,
  no forbidden CSS, kept as the `smoke_test` fixture.
- `gallery.py` regenerates `index.html` without error (cover face promoted where
  present via `gallery_face`).
- `smoke_test.py --style schematic_blueprint`, `lint_diagram_recipes.py`,
  `check_skill.py`, `icon_search.py --validate` all pass.
- Both specs' Status set to `Shipped`; all ACs `[x]` or deferred with anchor.

**Approach:**
- Build the detailed mock demonstrating the architecture-canvas primitive +
  seeded icons under `schematic_blueprint` (its cover face is supplied by the
  hero session). A brand-new style would instead get both `.cover.html` +
  `.html` per the two-mock convention.
- Regen gallery; **prompt** on hero refresh (collage from cover faces).
- Re-run the scrub checklist (T4) against the final diff; record the pass.
- Run the full gate sequence; mark this spec and the run spec Shipped; run the
  work-loop doc-drift lint `python3 .claude/skills/work-loop/scripts/lint-spec-status.py`.

**Done when:** all gates green; both specs Shipped; final scrub pass recorded;
hero-prompt surfaced.

## Rollout

Pure repo-content + local-script change; no infra, no deploy, no external
system, no flag. Reversible by revert. The one irreversible-if-wrong risk —
leaking source identity — is guarded by the scrub Boundary and the review pass.

## Risks

- **Scrub miss.** A source identifier slips into a committed file. Mitigation:
  the skill's scrub step + a recorded scrub checklist run against the **full
  diff** at T4 and again at T8, enumerating the AGENTS.md §39 identifier classes
  (deck name, client, customer, employer, project code-name, personal names,
  emails, internal URLs, ticket IDs, product names) — a defined needle set, not
  an open-ended grep — plus generic-only spec/plan and the review pass.
- **Icon originality.** Redraws must be idea-level, not traces. Mitigation: the
  provenance rule in `references/icons.md` and review judgment.
- **Scope size.** Skill + library + backfill + live run is large for one PR;
  the task DAG keeps each task a coherent unit and the dogfood doubles as
  verification rather than extra work.
- **Cross-branch overlap with `regenerate-hero-image`.** That in-flight branch
  owns `scripts/gallery.py`, `scripts/build_hero.py`, the `*.cover.html` mocks,
  and the regenerated PNGs/hero composites — and defines the two-mock /
  `gallery_face` convention this skill documents. Mitigation: this PR avoids
  editing those two scripts and consumes the convention; merge order between the
  two PRs is a coordination note, not a code conflict. Open decision (surfaced):
  whether the `build_hero` backfill lives here or solely in the hero PR.

## Changelog

- 2026-07-01: initial plan.
- 2026-07-01: expanded from "skill only" to include the icon-library subsystem,
  the `build_hero.py` backfill, and an in-PR dogfood assimilation of a
  maintainer-supplied deck, per user direction.
- 2026-07-01: aligned to the in-flight `regenerate-hero-image` two-mock
  convention (cover + detailed via `gallery_face`); `gallery.py` ownership stays
  with that branch (this PR never edits it).
- 2026-07-01: added `scripts/deck_probe.py` (+ test) — a deterministic ingest
  probe using only bundled deps — after the maintainer flagged that ad-hoc runs
  otherwise pip-install random parser/renderer libraries; added the
  no-ad-hoc-install dependency discipline to the skill.
- 2026-07-01: added `scripts/build_pdf.py` (+ test) — deterministic PDF *output*
  after the maintainer flagged PDF generation as wonky (an ad-hoc run had used
  WeasyPrint, then a puppeteer-png+Pillow hack). First cut used `page.pdf()`;
  corrected to **Puppeteer screenshot + Pillow** because the requirement is
  guaranteed **pixel-1:1** with the HTML render (the print path isn't 1:1).
  Confirmed by a live render (2560×1440 = 1280×720 × scale 2). No new dep
  (`img2pdf` declined — Pillow already does PNG→PDF); `build-print.sh` +
  print-combiner playbook now route through it instead of manual browser print.
- 2026-07-01: applied pre-EXECUTE adversarial-review fixes — pin icon inline
  delivery (`<svg>` verbatim, never `url()`/`<img>`); include the 3-line
  `build_hero.py` backfill here so the coverage AC verifies on this PR's tree
  (conflict-free identical merge); extend `diagram-architecture.md` rather than
  orphan a new recipe file; make the trace-through the load-bearing "procedure
  followable" proof (dogfood proves gate-passing output only); add structural
  `Never do` rails; enumerate the scrub checklist + record it at T4/T8; tie the
  narrative review to a one-line archetype decision + a pre-declared backlog
  anchor; correct the `lint-spec-status.py` path (work-loop skill script).
