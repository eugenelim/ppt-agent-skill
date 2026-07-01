# Plan: gallery title/detail two-tier + toggle

- **Status:** Executing
- **Constrained by:** the `gallery_face()` contract from PR #14 (cover =
  `<id>.cover.html` if present, else `<id>.html`).

## Pre-mortem (assumption trio + declined patterns)

- **Files touched:** `scripts/gallery.py` (toggle UI, two-tier model, category
  headers), `scripts/smoke_test.py` (both-tier validation), ≈26 net-new
  slides + ≈relocations under `ppt-output/style-gallery/`, per-style link updates
  in `references/styles/*.md`, regenerated PNGs + `assets/hero-*.png`, `README.md`,
  `references/style-system.md`, plus `docs/specs/.../classification.md`.
- **"Done" demonstrated by:** smoke both-tier 0 net-new fail; screenshot QA of
  every net-new slide + the toggle + category headers; hero regenerates for 29;
  classification.md committed.
- **Not changing:** the 3 detail mocks (`graphite_gold`/`editorial_paper`/
  `schematic_blueprint`) `<id>.html`, the pipeline, validators.

**Declined patterns:** Tempted to add a JSON manifest of per-style tiers;
declining — filesystem presence (`<id>.cover.html` / `<id>.html`) is the single
source of truth, already encoded in `gallery_face()`. Tempted to a client
framework for the toggle; declining — a few lines of vanilla JS. Tempted to keep
cover-primary covers at `<id>.html` and add details at `<id>.detail.html`
(avoid relocation); declining — it splits the cover tier across two filename
conventions and muddies the smoke fixture; the uniform `<id>.cover.html` /
`<id>.html`=detail invariant is worth 26 `git mv`s + link updates.

## Resolve-vs-surface disposition

- Scope model (detail=missing tier for most; net-new predominantly details) —
  **resolved** by the visual classification pass (referent: rendered slides).
- Per-style cover-vs-detail classification — **resolved** by task-zero
  `classification.md` (referent: the screenshot of each `<id>.html`).
- Toggle default (Cover) — **resolved**: identity-first, matches hero = cover.
- Phasing — **surfaced** (value/scope decision) as an Ask-first boundary.

## Tasks

### T0 — Classify all 29 existing `<id>.html`  ·  Depends on: none

Verification: **goal-based** (artifact exists + covers all 29).

- **Done when:** `docs/specs/gallery-title-detail-tiers/classification.md` lists
  every style with `cover-primary | detail-primary` + a one-line reason, and the
  derived per-tier authoring split (how many net-new details, how many net-new
  covers, how many relocations). Drives T4 batching.
- **Approach:** screenshot each `<id>.html` (reuse the generated `<id>.png`),
  classify by whether the slide is title/identity-dominant (cover) or
  multi-section content (detail). The 3 new styles are detail-primary + complete.

### T1 — Two-tier gallery model + toggle UX  ·  Depends on: none

Verification: **visual/manual QA** + goal-based. Proof set = the 3 styles that
already have both tiers (graphite_gold, editorial_paper, schematic_blueprint).

- **Done when:** `index.html` renders, per card, a Cover|Detail segmented control
  that swaps the iframe `src` between `<id>.cover.html` and `<id>.html`; a global
  "Show: Covers | Details" switch flips all cards; default = Cover; a style with
  only one tier hides its control.
- **Verification (behavior, not just markup):** grep proves the two srcs +
  control markup exist, not that the swap works. Also record an
  **assertion-based manual-QA transcript**: observe the card's rendered iframe
  `src` before and after (a) clicking a card's Detail then Cover, and (b) the
  global switch — the before/after `src` values are the artifact, plus a
  screenshot of each state. The missing-tier guard gets a **construction check**
  here: call `build_index_html` with a synthetic one-tier style and assert the
  emitted card has no toggle control (also fires naturally in-repo while tiers
  are incomplete).
- **Approach:** extend `build_index_html`: emit both tier URLs as data-attrs,
  render the control, add a small inline `<script>`. Reuse `gallery_face()` for
  the cover URL; inline `f"{sid}.html"` for the detail URL (no single-use helper).

### T2 — Category enhancement  ·  Depends on: T1

Verification: **visual/manual QA**.

- **Done when:** each category section header shows cn/en label + a one-line
  "what it's for" + benchmark brands + counts.
- **Approach:** add a `CATEGORY_BLURB`/brands map; render into `.section-head`;
  screenshot-review.

### T3 — smoke_test both-tier validation  ·  Depends on: none

Verification: **goal-based**.

- **Done when:** `smoke_test.py --phase 1` runs compat + typography on **both**
  `<id>.cover.html` and `<id>.html` for every style; 0 net-new failures vs
  baseline; report lists both tiers. Also align the md-file exclusion with
  `gallery.py` (skip `readme.md` in addition to `index.md`) so the two scripts
  iterate the same style set — same-concern ride-along, since this task already
  edits the style-iteration loop.
- **Approach:** in `phase1_tests`, iterate the two tiers per style; key results
  by `<id>` + tier; a tier absent mid-flight is reported, not failed. (The
  `README.md` schema example is already filtered by `_STYLE_ID_PATTERN`, so the
  exclusion alignment is hygiene against a future valid-id-in-readme, not a live
  bug.)

### T4a–T4e — Author the missing tier per style, batched by category  ·  Depends on: T0

Verification: **visual/manual QA** (screenshot every net-new slide at 1280×720).
For each style: if **cover-primary**, `git mv <id>.html <id>.cover.html`
(**relocation is `git mv` only — the relocated cover file is left byte-unchanged**,
so the hero-unchanged guarantee in T5/AC is mechanically true), author a net-new
**detail** at `<id>.html`, and update its `references/styles/*.md` entry to name
both tiers (cover + detail links, prose matching each render); if
**detail-primary**, author a net-new **cover** at `<id>.cover.html`. The
predominant net-new artifact is the **detail** slide.

- Batches: **T4a** dark_professional · **T4b** light_premium · **T4c** vibrant ·
  **T4d** cultural_oriental · **T4e** natural_retro. (The 3 complete styles need
  nothing.) Exact per-batch author/relocate counts come from T0's
  `classification.md`.
- **Done when (each):** every style in the batch has both canonical-filename
  tiers; each net-new slide is 1280×720, pipeline-safe, faithful to the style
  (palette/fonts/soul from `references/styles` + the sibling slide's head),
  carries `font-feature-settings` (+ `tabular-nums` when it shows a 2+-digit
  number) → 0 net-new warns, and screenshot-QA'd. **Distinctness** is checked
  against **two recorded renders**: screenshot `<id>.html` (detail) and
  `<id>.cover.html` (cover) separately — the cover carries none of the
  stat/card/table/chart content blocks the detail uses. (The pipeline's single
  `<id>.png` is the cover face; the detail screenshot is a separate QA artifact.)
- **Approach:** template covers off the 3 PR-#14 covers; author details as
  genuine content slides (data / argument / editorial) fitting each style's
  domain. Resumable: track per-style done/pending in a scratch file.

### T5 — Regenerate + docs + final gate  ·  Depends on: T1–T4e

Verification: **goal-based** + visual.

- **Done when:** `gallery.py --screenshots` + `build_hero.py` regenerate cleanly
  (hero = covers for all 29); README + style-system.md describe the two-tier model
  + toggle; `smoke_test --phase 1` = 0 net-new fail; no dangling `<id>.html`
  refs; `git status` clean.

## Notes

- T0, T1, T3 are independent; T2 needs T1; T4 needs T0; T5 needs all.
- Phasing option (an **Ask first** boundary): ship T0–T3 (classification + toggle
  + category + smoke, provable on the 3 complete styles) as one PR, then the ≈26
  net-new slides (T4) as category-batched follow-ups. Recommended for cleaner
  review + incremental value.
  - **Infra-PR (T0–T3) done-when** — its own gate, distinct from T5's all-in-one
    shape: `classification.md` committed; toggle + global switch work and are QA'd
    on the 3 complete styles (before/after `src` recorded); the degradation
    branch is exercised (the 26 not-yet-both-tier styles render control-hidden);
    smoke both-tier passes 0 net-new fail; **no relocations, no hero regen** (the
    hero from PR #14 stays); the hero AC + references-link AC are explicitly
    *deferred* to the T4 PR(s) via `(deferred: <anchor>)`.
  - **Hero-AC interaction:** do **not** regenerate a partial-face hero in the
    infra PR — leave PR-#14's hero in place and satisfy the hero AC only once the
    covers/details land.
- If instead landing everything in one PR, T5's done-when is the gate and the
  infra-PR carve-out above is moot.
