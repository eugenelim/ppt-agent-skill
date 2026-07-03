# Spec: slide-intent-review

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

A deck author cleaning high-volume knowledge needs to catch stale facts, missing
sources, wrong structure, and over-stuffed slides **before** paying for the
expensive bespoke HTML render — because those problems only become obvious when
content is seen slide-by-slide, and re-rendering to review is slow and
token-costly. **Slide-Intent Review Mode** gives them a cheap, deterministic,
low-fidelity review artifact: a **slide-intent worksheet** rendered directly from
`planning/*.json` (no LLM), styled as an engineering worksheet (a color-muted
derivative of the `schematic_blueprint` look) so it reads as a *draft spec, not a
finished deck*. Each slide is one worksheet card showing its real content, its
data values, and whether each claim carries a source; a pinned index gives the
whole-deck flow at a glance. At the planning → render handoff the author is asked
**Review first** vs **Render now** (with a warning that rendering locks in the
shape before the facts are checked). The author reviews, fixes `planning.json`,
re-renders the worksheet — cheaply, as many cycles as needed — then renders the
deck once. The worksheet is disposable scratch; `planning.json` stays the single
source of truth.

## Boundaries

### Always do

- Read `planning/*.json` and `outline.json` as inputs; write worksheet output
  only under `OUTPUT_DIR/runtime/proof/`.
- Show every stale-able content field (headline, body, items, data values,
  source status) in full — never truncate them; collapse art-direction fields
  and omit routing fields.
- Derive titles by reading existing clean fields: deck title from
  `outline.json` `cover.title` (fallback deck-slug), per-slide heading from
  `planning` `page.title`.
- Regenerate the worksheet from `planning/*.json` on every review cycle
  (it is a derived view).

### Ask first

- Any change to the planning schema, `planning_validator.py`, or the Step-0
  interview-anchor contract.
- Adding any runtime dependency.
- Wiring the intent-derived title into the *deliverable* render path
  (`design-specs.md` `<title>` template / `html_packager.py`) — that is the
  deferred, separate title-cleanup work.

### Never do

- Make the proof a gallery or deliverable style, or place anything carrying a
  `style_id` under `references/styles/` — the gallery style set stays unchanged.
- Treat the worksheet as a source: it is read-only scratch. Fixes land in
  `planning.json`.
- Call an LLM, hit the network, or introduce any nondeterminism in the proof
  render — including reading the system clock (the as-of date is an explicit arg).
- Write `workflow_metadata` or bump any version constant from the proof path.
- Auto-detect or fabricate a staleness/source date. Status is source *presence*
  only.
- Add a new top-level dependency or a new module boundary beyond
  `scripts/proof_worksheet.py` + `assets/proof/`.

## Testing Strategy

- **Serializer field mapping** (SHOWN / meta / collapsed / omitted set, source
  status ●/○, density over-budget flag, titles): **TDD** — a fixture
  `planning` page asserts the worksheet's structure and field placement.
- **Determinism**: **TDD** — same inputs (including CLI args) render byte-identical
  output across two runs; the render reads no system clock and no network; ordering
  derives solely from `slide_number` and the explicit field list, never from
  `dict`/`set` iteration.
- **Spillover**: **TDD** — an oversized page yields a continuation card with
  content fields intact and art-direction fields collapsed first.
- **Isolation**: **goal-based check** — the render's write-set is a subset of
  `runtime/proof/` (nothing under `references/styles/`, `ppt-output/style-gallery/`,
  or `slides/`), and `gallery.py`'s `collect_all_styles()` returns the known style
  id-set (exercised as an integration check).
- **Consent gate & docs**: **goal-based check** — `SKILL.md` carries the Step 4.5
  gate + warning text; `check_skill.py` stays green.
- **Staleness surfacing**: **manual QA** — open the worksheet for a real deck and
  confirm stale facts and un-sourced claims are visible at a glance.

## Acceptance Criteria

- [x] `scripts/proof_worksheet.py` renders all `planning/*.json` pages to
  `OUTPUT_DIR/runtime/proof/<deck-slug>-intent.html` with **no LLM call and no
  network**; the same inputs (including CLI args) produce byte-identical output,
  with card and field ordering derived solely from `slide_number` and the explicit
  field list — never from `dict`/`set` iteration.
- [x] Each slide card shows the SHOWN set: header (`№ · page_type ·
  narrative_role`), `title`, takeaway (`audience_takeaway` when present, else the
  guaranteed `page_goal`), and per card `role · card_type/card_style ·
  argument_role · headline · body/items · data_points · source status ·
  chart_type`, plus image intent and `source_guidance`. `data_points` entries may
  be plain strings or dicts (value·unit shown when a dict carries them).
- [x] A meta strip shows `layout_hint` (label), `density_label` with a **⚠ flag
  when `len(cards) == density_contract.max_cards` or chart count `==
  density_contract.max_charts`** (the validator rejects strictly-over-budget pages
  upstream, so "at budget" is the reachable signal), the counts vs those maxes, and
  `№ of N`. A card counts as a chart only when its `chart` is a dict with a
  **non-empty** string `chart_type` (a stricter variant of the validator, which
  counts any string).
- [x] Source status is derived solely from `data_points` (the same field shown in
  the SHOWN set above): a card shows a marker only when its `data_points` is
  non-empty — **●** if any entry is a dict with a
  truthy `source`, otherwise **○** (this covers plain-string entries and
  source-less dicts). Cards with empty/absent `data_points` (body/items/chart-only)
  show no marker. The page's required `source_guidance` renders in the card's meta
  area (a source-guidance line below the meta strip) as the sourcing contract. No
  freshness verdict, no date.
- [x] Art-direction fields (`director_command`, `decoration_hints`,
  `variation_guardrails`, `must_avoid`, pacing hints, `content_budget`,
  `density_reason`) render collapsed; routing fields (`resources.*`,
  `resource_ref`, `visual_weight`) are omitted; `narrative_archetype` (a per-page
  field) shows once in the deck header, read from the lowest-`slide_number` page as
  the tie-break.
- [x] Layout is **one-up worksheets with a pinned deck-overview index** (`№`,
  `title`, `density`, flag count, jump link). No two-up view exists.
- [x] Spillover: when a page overflows one card, content fields are **never
  truncated**, art-direction fields collapse first, and remaining overflow moves
  to a continuation card labelled `№ · 2/2`.
- [x] Deck heading and browser tab title come from `outline.json cover.title`
  (fallback deck-slug); per-card heading from `planning page.title`.
- [x] An optional `--as-of DATE` argument renders a deck as-of date in the header;
  when omitted, no date renders and the system clock is never read (preserving
  byte-identical determinism).
- [x] Chrome is `assets/proof/proof.css` — an owned, hand-authored muted
  derivative of `schematic_blueprint` (decorative purple dropped; amber/green
  status colors kept); it carries **no `style_id`** and is **not** under
  `references/styles/`.
- [x] The render's write-set is a subset of `runtime/proof/` — nothing is written
  under `references/styles/`, `ppt-output/style-gallery/`, or `slides/` — and
  `gallery.py`'s `collect_all_styles()` returns the same style id-set, with
  `check_skill.py` green.
- [x] The proof path writes **no `workflow_metadata`** and bumps **no version
  constant**; opening a `planning.json` stamped with an older version produces at
  most a soft drift warning and still renders.
- [x] `SKILL.md` defines a **Step 4.5 consent gate** that elicits *Review first*
  vs *Render now* via the structured-UI mechanism (text fallback), carries the
  warning "⚠️ Rendering now locks in the shape before the facts are checked —
  later fixes cost a re-render and can drift `planning.json` out of sync. Still
  reviewable after, just more LLM- and time-intensive.", derives its recommended
  default from `grounding_mode` (G1/G2→Review, G3→Render-ok) + deck size, and is
  asked once per deck. It is **not** added to the Step-0 interview-anchor
  contract.

## Assumptions

- Technical: Jinja2 3.1.6 is present, so templating needs no new dependency
  (source: probe `python3 -c "import jinja2"` → 3.1.6).
- Technical: gallery styles are enumerated only from `references/styles/*.md`
  `style_id` blocks and no hardcoded style count exists, so isolation holds by
  keeping proof assets outside that directory (source: `scripts/gallery.py:26,97`;
  `scripts/check_skill.py`).
- Technical: `schematic_blueprint` is an existing deliverable style; the proof
  chrome is an owned hand-authored derivative, not generated from it (source:
  `references/styles/index.md:31`, `references/styles/light.md`).
- Technical: `planning.json` carries no date/recency field, so status is
  source-presence only, not a freshness verdict (source:
  `scripts/planning_validator.py`; research artifacts carry no source date; user
  confirmation 2026-07-03).
- Technical: `data_points` entries may be plain strings or dicts and a per-point
  `source` sub-key is not validated, while `source_guidance` is a **required** field
  on content pages — so the status marker derives **solely** from per-card
  `data_points` (● on any dict entry with a truthy `source`, else ○, none when
  empty) and `source_guidance` renders separately in the meta as the page's
  sourcing contract, not as an input to the marker (source:
  `scripts/planning_validator.py:308` has_data dict-check, `:566` source_guidance
  required; `references/prompts.md:273` string example; fixture uses dicts).
- Technical: `narrative_archetype` is a per-page field (`VALID_NARRATIVE_ARCHETYPES`
  in `validate_page`); there is no deck-level planning object, so the deck-header
  value uses the lowest-`slide_number` page as tie-break (source:
  `scripts/planning_validator.py`).
- Technical: `slides/` is the per-deck HTML output directory (one HTML per slide)
  under `OUTPUT_DIR`, so it is a real sibling surface the proof must not write to
  (source: `SKILL.md` output-directory structure).
- Technical: the slide title is set at outline (Step 3), carried as the required
  `planning page.title`, and merely injected at render (`{{SLIDE_TITLE}}`), so the
  proof reads `planning.title` / `outline.cover.title` directly — both already
  clean (source: `references/design-runtime/design-specs.md:364`,
  `references/prompts.md:155,171`, `scripts/planning_validator.py` required
  fields).
- Technical: `WORKFLOW_VERSION` and schema versions are soft provenance stamps —
  `validate_workflow_metadata` only *warns* on mismatch, never errors — so no bump
  is needed and old `planning.json` opens fine (source:
  `scripts/planning_validator.py:405`).
- Technical: `OUTPUT_DIR/runtime/` is gitignored, so worksheet output is scratch
  (source: `.gitignore` `ppt-output/*`).
- Process: the consent gate reuses the structured-UI mechanism but is standalone;
  `check_step0_interview_contract` is scoped to the Step-0 interview files, so the
  gate does not join that lockstep contract (source: `scripts/check_skill.py:337`;
  user confirmation 2026-07-03).
- Process: specs live in `docs/specs/<feature>/{spec,plan}.md` (source:
  `AGENTS.md` Source-of-truth table).
- Product: field set, one-up default, two-up considered-and-declined, HTML-title
  reuse deferred, and the consent-gate default heuristic (source: user
  confirmation 2026-07-03).
