# Spec: gallery title/detail two-tier + toggle

Mode: full (risk trigger: multi-feature / dependent tasks)

- **Status:** Implementing
- **Constrained by:** the `gallery_face()` contract merged in PR #14 (a style's
  gallery face = `<id>.cover.html` if present, else `<id>.html`; `gallery.py`
  screenshots the face → `<id>.png`, `build_hero.py` tiles the PNGs).

## Objective

Give every one of the 29 gallery styles **both** a title/cover slide and a
detail/content slide, and let the style gallery show either. (The 29 styles are
defined across **5 category files** in `references/styles/` —
`dark`/`light`/`vibrant`/`cultural`/`natural`, multiple `style_id` JSON blocks
per file — plus `README.md`/`index.md` schema examples that are *not* styles;
`ls references/styles` showing 7 `.md` files is expected, not a miscount.)

**Grounded finding (corrected).** A visual pass over the 29 existing `<id>.html`
mocks shows they are **predominantly cover / hero slides** — a large hero title
plus, at most, a few supporting stat cards (e.g. `royal_red` = "千年文脉·当代新生
· CHAPTER I — PROLOGUE"; `dark_tech` = "Intelligence, at the edge." + 3 stats).
A genuine multi-section **detail / content** slide (data dashboards, argument
grids, tables, essays) exists only for the 3 newest styles — `graphite_gold`
(advisory-card grid), `schematic_blueprint` (RACI worksheet table),
`editorial_paper` (research essay). A minority of the older mocks are
detail-primary (e.g. `minimal_gray` editorial article, `medical_pulse` ECG
dashboard, `bauhaus_block` exhibition layout).

So the tier that is largely **missing is the detail tier**, and the net-new
authoring is **≈26 slides, predominantly detail slides** — *not* 26 covers (an
earlier draft inverted this). The exact per-tier split is produced by a
classification pass (task-zero of implementation), not assumed here.

**Canonical two-tier model** (uniform across all 29, by filename):

- `<id>.cover.html` = **cover** (title/identity; the gallery's default face,
  fed to `gallery_face()` from PR #14).
- `<id>.html` = **detail** (the fuller content slide; the smoke/spec fixture and
  the "the mock" link target in `references/styles/*.md`).

Per style, normalization depends on what the existing `<id>.html` is:

- **detail-primary** (the 3 new + the content-rich minority): keep `<id>.html`
  as the detail tier; author a net-new `<id>.cover.html`.
- **cover-primary** (the majority): relocate the existing cover
  `<id>.html` → `<id>.cover.html`; author a net-new detail slide at `<id>.html`;
  update that style's mock link in `references/styles/*.md`.

## Acceptance Criteria

- [x] A recorded **classification** of all 29 existing `<id>.html` as
  cover-primary or detail-primary (task-zero), committed to the spec folder as
  `classification.md`, so the per-tier authoring split is grounded not guessed.
- [ ] Every one of the 29 styles has **both** `<id>.cover.html` (cover) and
  `<id>.html` (detail) with the canonical roles above; each 1280×720 and
  pipeline-safe (0 compat failures — no `mask-image`/`-webkit-mask-image`/
  `conic-gradient`/`mix-blend-mode`/`background-image:url()`) and 0 net-new
  typography *failures*. Typography *warns* are advisory and budgeted in the
  Testing Strategy, not a pass bar. (deferred: gallery-tier-authoring)
- [ ] Cover and detail for a style are genuinely distinct: the cover is
  title/identity only and carries **none** of the stat/card/table/chart content
  blocks its detail slide uses (checked against the screenshot). (deferred: gallery-tier-authoring)
- [x] `smoke_test.py` phase 1 validates compat + typography for **both** tiers
  (`<id>.cover.html` and `<id>.html`) of **every** style — i.e. both are
  fixtures — with zero net-new *failures* vs. baseline and net-new *warns* within
  the Testing-Strategy budget. "Every style" = the ID-pattern-valid set (the 29
  passing `_STYLE_ID_PATTERN`; the `README.md` `自定义 ID 或预置 ID` schema example
  is already filtered by that pattern, so it never becomes a phantom fixture). To
  remove the latent script divergence, `smoke_test`'s md-file exclusion is aligned
  with `gallery.py`'s (both skip `index.md` **and** `readme.md`).
- [x] The gallery index renders a per-card **Cover | Detail** segmented toggle
  that swaps the card's iframe between the two tiers, plus a global
  **Show: Covers | Details** switch; default is Cover. A card whose style is
  missing a tier degrades gracefully (control hidden) — this branch **is**
  exercised in-repo mid-flight (before all tiers are authored) and is pinned by a
  construction check driving `build_index_html` with a synthetic one-tier style.
- [x] Category sections show enriched headers: cn/en label, a one-line
  "what it's for", benchmark brands, and per-category counts.
- [ ] Hero composites stay cover-based (`gallery_face` → `<id>.cover.html` for
  all 29) and regenerate cleanly. (After normalization, the hero content is
  unchanged from PR #14 for cover-primary styles — the same cover, relocated.)
  (deferred: gallery-tier-finalize)
- [ ] For every **cover-primary** style relocated, its `references/styles/*.md`
  entry names **both** tiers — the mock link/prose is updated so the cover link
  points at `<id>.cover.html` and a detail link points at `<id>.html`, and the
  surrounding description matches what each URL now renders (no prose that
  describes the cover left sitting next to a link that now resolves to the
  detail). No intra-repo `<id>.html` reference dangles. (deferred: gallery-tier-authoring)
- [ ] `README.md` and `references/style-system.md` describe the two-tier model. (deferred: gallery-tier-finalize)

## Boundaries

Rails for the implementer — do these by default, pause on these, never these.

**Always do:**

- Anchor every cover at `<id>.cover.html` and every detail at `<id>.html`
  (the `gallery_face()` contract).
- Classify a style's existing `<id>.html` before authoring, and author only the
  **missing** tier (relocating the existing slide to its canonical filename when
  it's a cover-primary `<id>.html`).
- Give every net-new slide `font-feature-settings` (+ `tabular-nums` when it
  shows a 2+-digit number) so it adds 0 net-new smoke warns.
- Screenshot-QA every net-new slide at 1280×720 before considering it done.

**Ask first:**

- **Phasing** — whether to ship the infra (toggle + category + smoke both-tier +
  classification) as one PR and the ≈26 net-new slides as category-batched
  follow-ups, or land everything in one PR. This changes PR scope and interacts
  with the hero AC (an interim infra ship must not regenerate a mixed-face hero —
  see plan Notes). The operator decides; the implementer must not default it.

**Never do (structural):**

- Do not relocate or reclassify the 3 detail mocks `graphite_gold`/
  `editorial_paper`/`schematic_blueprint` `<id>.html` — they are shipped-spec
  acceptance artifacts anchored at `<id>.html`.
- No new npm dependency and no build step: the gallery-index toggle is vanilla
  inline JS. The gallery index is a standalone **preview page** (never fed to the
  html2svg pipeline), so inline JS is allowed *there*; pipeline mocks
  (`<id>.html` / `<id>.cover.html`) stay JS-free.
- Do not touch the html2svg pipeline, planning/validator code, or chart recipes.

## Testing Strategy

- **Mechanical gate:** `python3 scripts/smoke_test.py --phase 1` — extended to
  both tiers; must show 0 net-new failures vs. the pre-change baseline (10 warns
  on the untouched mocks are baseline).
- **Warn budget:** the typography heuristics *warn* (not fail) when numbers
  appear without `tabular-nums`, or when `font-feature-settings` is absent
  (`smoke_test.py:231,235`). Every net-new slide **must** carry both
  `font-feature-settings` and (when it shows any 2+-digit number)
  `tabular-nums` — so the expected **net-new warn count is 0**. Any net-new warn
  is a real omission to fix, not accepted drift. (The 3 existing `.cover.html`
  already carry 0 warns, so the 10-warn baseline is invariant under the both-tier
  scan expansion — it only stays invariant if every net-new cover holds this bar.)
- **Goal-based:** grep `index.html` for both tier iframe sources + the toggle
  controls; `gallery.py` regenerates deterministically; the degradation
  construction check on `build_index_html`.
- **Visual / manual QA (the bulk):** screenshot-review every net-new slide at
  1280×720, the toggle interaction (record iframe `src` before/after on a card +
  the global switch), and the enriched category headers. Slides are UI artifacts
  — a passing smoke gate does not substitute for looking at the render.

## Assumptions

- The 29 existing `<id>.html` are predominantly cover/hero slides — **grounded**
  by the visual pass (Objective) and pinned by the task-zero `classification.md`,
  not assumed.
- Puppeteer screenshotting and Pillow are available (used in PR #14).
- No old-style (non-`graphite_gold`/`editorial_paper`/`schematic_blueprint`)
  `<id>.html` is spec-anchored — **verified** by grep of `docs/specs/*/spec.md`;
  only the 3 new specs anchor a mock, so relocating cover-primary `<id>.html` is
  safe (references/styles doc links updated per the AC).
