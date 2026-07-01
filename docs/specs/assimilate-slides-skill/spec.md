# Spec: assimilate-slides skill + icon library

- **Status:** Shipped <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Contract:** none <!-- documentation + scripts; no wire contract -->
- **Shape:** mixed

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

A repo maintainer can turn a pile of source slides — an HTML/CSS deck, a
`.pptx`, a `.pdf`, or loose images / SVGs, located in **any local folder or at
a URL** — into first-class skill assets by invoking one internal skill,
`assimilate-slides`, and following its procedure end to end. The skill encodes
the process that produced the `graphite_gold` and `schematic_blueprint` styles
and generalizes it: it **scrubs all confidential and personally-identifying
material** before anything is written to the repo; classifies the source
(new-style vs. restyle vs. primitives-only; board category; narrative type);
extracts the visual style as a validated style JSON plus an N-point styling
spec; extracts reusable UI primitives into a paste-ready, pipeline-safe block
recipe; **redraws** distinctive iconography — idea-level, never traced — into a
**searchable, growing SVG icon library**; reviews the narrative-arc and playbook
references for new archetypes, conventions, or authoring patterns; builds and
tests the 1280×720 gallery mocks — **a cover mock (`<id>.cover.html`) and a
detailed mock (`<id>.html`)** per the gallery's two-mock convention; regenerates
the gallery index; prompts the maintainer on whether to refresh the hero
collage; runs the mechanical gates; and closes by marking its per-run spec
Shipped.

The gallery's two-mock convention is set by the in-flight `regenerate-hero-image`
work, which owns `scripts/gallery.py` and `scripts/build_hero.py`: `gallery.py`'s
`gallery_face(sid)` uses `<id>.cover.html` for the gallery card + hero thumbnail
when it exists (a uniform cover-view wall) and falls back to `<id>.html`; the
detailed `<id>.html` is always kept as the spec deliverable and `smoke_test`
fixture. This skill conforms to that convention rather than re-defining it.

The skill is proven by dogfooding: this PR runs it against a real
maintainer-supplied session deck, producing a set of architecture-canvas
primitives and seed icons under the existing `schematic_blueprint` style, with
every committed artifact referring to the source **only generically**.

## Boundaries

### Always do

- **Scrub before write.** Reproduce only *reusable form* (layout, palette,
  type, primitives, icon ideas). Strip every identifier — client / customer /
  employer names, project or deck code-names, personal names, emails, internal
  URLs, ticket IDs, product names — and replace with neutral placeholders
  (`Acme`, `Program`, `example.com`). This applies to committed files *and* to
  the spec/plan themselves. Before commit, run the scrub checklist (the
  AGENTS.md §39 identifier classes above) against the **full diff** and record
  the pass as a manual-QA artifact in the run spec.
- **Redraw icons idea-level, deliver them inline.** Icons enter the library as
  clean re-drawings of a *concept* (a database, a pipeline, a model) — never a
  byte-copy or trace of a source glyph — and compose into mocks by verbatim
  inline `<svg>`, never `url()`/`<img>`.
- **Bind to CSS variables and stay pipeline-safe.** All extracted CSS/SVG binds
  to deck theme variables and passes the forbidden-CSS rules in
  [`references/pipeline-compat.md`](../../../references/pipeline-compat.md)
  (no `<text>`, `mask-image`, `conic-gradient`, `background-image:url()`, etc.).
- **Discard non-reusable slides.** Image-only cover / divider / photo-collage
  slides carry no reusable form and are dropped, not templated.

### Ask first

- **Updating the hero collage.** Regenerating `assets/hero-*.png` is a
  maintainer decision the skill surfaces as an explicit prompt, never automatic.
- **Minting a new validator `card_type`** or any engine-level enum / `page_type`
  change — deferred to `docs/backlog.md` unless the maintainer approves it.
- **Adding a new top-level style board** (a sixth `references/styles/*.md`
  category file).

### Never do

- **Never commit the source's identity or contents** — no deck name, client,
  employer, project code-name, or verbatim confidential text in any file in the
  repo (spec, plan, skill, recipes, icons, mocks, commit messages).
- **Never add a runtime dependency** to satisfy this work; the icon search and
  validation tooling is stdlib-only Python, matching the existing `scripts/`.
- **Never introduce a new top-level directory** (icons live under existing
  `assets/` and `references/`; scripts under existing `scripts/`).
- **Never mint a new validator `card_type` or `page_type`** for the extracted
  primitives — load them via the existing `block_refs` mechanism; engine-enum
  changes are deferred to `docs/backlog.md`.
- **Never grow the icon subsystem an interface it doesn't need yet** — no
  fuzzy-search index, no HTML gallery viewer, no SVG-render/parse dependency;
  stdlib substring/token search over `catalog.json` is the whole contract.
- **Never edit `scripts/gallery.py`** — the two-mock / `gallery_face` convention
  is owned by the in-flight `regenerate-hero-image` branch.

## Testing Strategy

- **`assimilate-slides` skill (docs) — goal-based + manual QA.** Goal-based: the
  frontmatter is agentskills.io-compliant (keys drawn only from the pinned set;
  a one-sentence `Use when …` trigger), and every script path, reference path,
  and repo path the skill names resolves (a `grep`/`test -f` sweep). Manual QA
  has two distinct claims: **"the written procedure is followable"** is proven by
  a recorded **trace-through** mapping each skill step to the concrete artifact
  the two prior specs produced (the *non-circular* proof, since a fresh agent
  reads the same steps); **"the procedure produces gate-passing output"** is
  proven by the dogfood run. The dogfood does not, by itself, prove the
  procedure is correct (same agent writes and runs it) — the trace-through is
  the load-bearing artifact for that.
- **Icon search/validate (`scripts/icon_search.py`) — TDD.** Search-token
  matching and the catalog↔file / pipeline-safety validation are pure logic with
  compressible invariants; unit tests pin them.
- **Ingest probe + PDF exporter (`deck_probe.py`, `build_pdf.py`) — TDD +
  goal-based.** `test_deck_probe.py` pins deterministic extraction from a
  committed HTML fixture + the no-install discipline; `test_build_pdf.py` pins
  input resolution, that the node script screenshots (not `page.pdf()`), and the
  Pillow PNG→PDF assembly. A live render additionally confirms pixel-1:1.
- **Icon library + extracted primitives + mocks — goal-based.** `icon_search.py
  --validate` is clean; `lint_diagram_recipes.py` passes with the new recipe on
  its target list; `smoke_test.py --style schematic_blueprint` passes; both the
  cover mock and the detailed mock render at 1280×720 with no forbidden CSS.
- **build_hero coverage — goal-based.** The set of real style ids — enumerated
  by **reusing `gallery.py`'s `collect_all_styles()`** (the canonical discovery,
  which skips `index.md`/`README.md` so their placeholder/example blocks don't
  pollute the set) — equals the union of `build_hero.py` CATEGORIES `ids`. The
  check passes on this PR's own tree. This PR adds the three missing ids to
  `build_hero.py` (identical to the `regenerate-hero-image` branch's addition →
  conflict-free 3-way merge); it does not touch `gallery.py`.

## Acceptance Criteria

- [x] `.claude/skills/assimilate-slides/SKILL.md` exists, is
  agentskills.io-compliant (frontmatter keys only from the pinned set; project
  keys under `metadata:`; `description` is one `Use when …` trigger sentence),
  and its body is a thin spine that delegates depth to `references/*.md`.
- [x] Six reference files exist under
  `.claude/skills/assimilate-slides/references/`:
  `ingest-and-classify.md`, `extract-style.md`, `extract-primitives.md`,
  `extract-icons.md`, `narrative-and-playbooks.md`, `build-and-ship.md`.
- [x] `ingest-and-classify.md` documents source acquisition for **local folder
  and URL** across HTML/CSS, PPTX (`python-pptx`), PDF, images, and SVG; the
  **mandatory PII/confidentiality scrub**; **image-heavy-header discard** (an
  area-fraction + low-text heuristic); and the classify decision (new-style vs.
  restyle vs. primitives-only; board category enum; narrative type).
- [x] A deterministic ingest probe `scripts/deck_probe.py` exists (stdlib +
  `python-pptx`/`lxml` only, **no ad-hoc installs**): it extracts reusable form
  from PPTX (per-slide composition, top fonts/colors, dense-diagram + image-heavy
  flags) and HTML/CSS (`:root` vars, font stacks, hex palette), and tells the
  agent to read PDF/images/SVG with the harness viewer rather than installing a
  parser. The skill's INGEST step and the **no-ad-hoc-install dependency
  discipline** point to it. (Poppler `pdftotext`/`pdfinfo` is used for a source
  PDF only when already installed — never provisioned.)
- [x] A deterministic PDF **exporter** `scripts/build_pdf.py` exists (Puppeteer
  screenshot + already-present Pillow — no new dependency): it renders HTML→PDF
  **pixel-1:1 with the on-screen render** (each mock → one page; `--out`/`--deck`
  → one multi-page PDF), and bans WeasyPrint / `pdf2svg` / `img2pdf` / Chrome's
  `page.pdf()` print path (none guarantee 1:1). Verified by
  `scripts/test_build_pdf.py` and a live render (embedded frame 2560×1440 =
  1280×720 × deviceScaleFactor 2). The skill's `build-and-ship.md`, the ingest
  dependency-discipline, and `build-print.sh` all route PDF export through it.
- [x] `extract-style.md` documents the 15-key style JSON (validated by
  `smoke_test.py`), the N-point styling spec, the **restyle / no-new-style path**
  (map to an existing style when the source matches), and every index counter/row
  to update (per-board header count + table row; `index.md` total, panorama,
  decision matrix).
- [x] `extract-primitives.md` documents the blocks recipe format (fixed
  `何时用 / 数据格式 / 模板 / 自检 / 管线安全` order), CSS-variable binding,
  pipeline-safety, registration in `references/blocks/README.md`, and appending
  the file to the `lint_diagram_recipes.py` target list.
- [x] `extract-icons.md` documents the idea-not-copy provenance rule, the
  pipeline-safe monoline SVG authoring contract (`currentColor`, normalized
  viewBox, no `<text>`), a catalog entry, `icon_search.py` usage, and the
  **delivery mechanism**: a catalog icon is composed into a mock by pasting its
  `<svg>` **inline, verbatim** — never referenced via `background-image:url()`
  or `<img>` (both lossy/forbidden per `pipeline-compat.md`). `icon_search.py`
  can emit the inline snippet for a matched id.
- [x] `narrative-and-playbooks.md` documents when a source adds a narrative
  **archetype** vs. a **convention** vs. an authoring **playbook** — all
  guidance-only, with engine-level enum/`page_type` changes deferred to
  `docs/backlog.md`.
- [x] `build-and-ship.md` documents the **two-mock convention** — a cover mock
  `<id>.cover.html` (the gallery face + hero thumbnail via `gallery.py`'s
  `gallery_face`) and a detailed mock `<id>.html` (the spec deliverable +
  `smoke_test` fixture), both 1280×720 pipeline-safe — `gallery.py` regen (+
  `--screenshots`), the **hero-update prompt** (collage regenerated from cover
  faces), the gate sequence (`smoke_test.py --style <id>`,
  `lint_diagram_recipes.py`, `check_skill.py`, `icon_search.py --validate`), and
  the closing **mark-spec-Shipped** step.
- [x] A searchable icon library exists: `assets/icons/` holds pipeline-safe
  monoline SVGs and a `catalog.json`; `references/icons.md` documents authoring
  rules, the idea-not-copy provenance rule, and search usage; `scripts/icon_search.py`
  supports keyword/tag **search**, **list**, and **validate** (catalog↔file
  consistency + pipeline-safety, including that each SVG is inline-safe: has a
  `viewBox`, no `<text>`/forbidden CSS), stdlib-only.
- [x] `scripts/build_hero.py` CATEGORIES lists every real `style_id` exactly
  once — this PR adds the missing `graphite_gold`, `schematic_blueprint`,
  `editorial_paper` (the identical three-line addition the `regenerate-hero-image`
  branch also makes, so the 3-way merge is conflict-free); `scripts/gallery.py`
  is left to that branch. The set-equality check enumerates ids by **reusing
  `gallery.py`'s `collect_all_styles()`** (which excludes `index.md`/`README.md`)
  and passes on this PR's own tree.
- [x] Dogfood run (committed generically): the supplied source is classified as
  a **`schematic_blueprint` match — no new style**; its architecture-canvas
  primitives are extracted into a pipeline-safe recipe **added to the existing
  `references/blocks/diagram-architecture.md` family** (auto-globbed by the lint;
  a separate new file is used only with a stated justification and an explicit
  lint-target append); ≥8 seed icons — enough to demonstrate search across ≥2
  catalog categories — are redrawn into the library; the narrative review records
  a one-line archetype decision (`new: <name>` | `none`) in the run spec; the
  image-heavy header slides are documented as discarded. Anything deferred to
  the engine (a `card_type`/`page_type`) adds a `docs/backlog.md` heading in this
  PR and the run-spec criterion cites that anchor.
- [x] A 1280×720 **detailed** gallery mock demonstrating the new
  architecture-canvas primitives + seeded icons under `schematic_blueprint`
  renders pipeline-safe. It is a standalone primitives-demo (its filename is not
  a style id, so `smoke_test`'s per-style scan doesn't cover it); a standing gate
  `scripts/test_arch_canvas_mock.py` runs `smoke_test`'s forbidden-CSS/typography
  checkers + an inline-icon check against it. `gallery.py` regenerates the index
  without error. (A new-style assimilation, by contrast, produces both a
  `.cover.html` and a detailed `.html`; the dogfood extends an existing style, so
  it adds the standalone primitives-demo mock only.)
- [x] Gates pass: `smoke_test.py --style schematic_blueprint`,
  `lint_diagram_recipes.py`, `check_skill.py`, `icon_search.py --validate`.
  (`check_skill.py` guards the shipped product surface and does **not** scan
  `.claude/skills/**`; the skill's own doc verification is the frontmatter grep +
  path sweep, per `build-and-ship.md`.)
- [x] Both specs are marked `Shipped`: this spec and the generic per-run
  assimilation spec the dogfood produces.

## Assumptions

- Technical: style is a fenced ` ```json ` block with 15 required keys enforced
  by `STYLE_REQUIRED_FIELDS`; `category` is a 5-value JSON enum (source:
  `scripts/smoke_test.py:39-43`).
- Technical: `gallery.py` auto-discovers styles by regex over ` ```json ` blocks
  and regenerates `index.html`; `--screenshots` shells to puppeteer (source:
  `scripts/gallery.py:46-66`).
- Technical: `build_hero.py` CATEGORIES ids and the `lint_diagram_recipes.py`
  target list are hardcoded and appended to per style/recipe (source:
  `scripts/build_hero.py:23-49`, `scripts/lint_diagram_recipes.py:201-206`).
- Technical: `check_skill.py` does not scan `.claude/skills/**`, so the new skill
  does not trip it (source: read of `scripts/check_skill.py`).
- Technical: forbidden-CSS authority is `references/pipeline-compat.md`; blocks
  recipes require 5 bold markers (source: `scripts/lint_diagram_recipes.py:38`).
- Technical: `python-pptx` 1.0.2 is available; PDF/image read via the harness;
  URL fetch via WebFetch (source: probe `python3 -c "import pptx"`; `AGENTS.md:140`).
- Technical: the supplied source's type palette (electric-violet `#A100FF` focus
  on black/white) and line-art diagram grammar match `schematic_blueprint`, so no
  new style is minted (source: scratch `python-pptx` analysis of the source deck).
- Process: internal maintainer skills live in `.claude/skills/`; the shipped PPT
  product surface (top-level `SKILL.md`/`references/`) is separate (source: repo
  layout — `bug-fix`, `work-loop`, `new-spec`).
- Process: prior assimilations each shipped a generic `docs/specs/<x>/spec.md`
  under work-loop; each run makes and ships its own spec (source:
  `docs/specs/{graphite-gold-advisory-extract,schematic-blueprint-runbook-restyle}/spec.md`).
- Process: the pre-existing `build_hero.py` gap is backfilled, the icon library
  is built, and the deck is assimilated in this PR; the source is referred to
  only generically in all committed files (source: user confirmation 2026-07-01).
- Process: the gallery's **two-mock convention** (`<id>.cover.html` cover face
  via `gallery_face` + `<id>.html` detailed fixture) is owned by the in-flight
  `regenerate-hero-image` branch; this skill conforms to it and does not edit
  `gallery.py`. This PR does add the identical three-line `build_hero.py`
  backfill (conflict-free with that branch's identical addition) so the coverage
  AC is verifiable on this PR's own tree (source: working-tree of
  `~/conductor/workspaces/ppt-agent-skill/regenerate-hero-image` — `gallery.py`
  `gallery_face`, new `*.cover.html`, `build_hero.py` CATEGORIES).
