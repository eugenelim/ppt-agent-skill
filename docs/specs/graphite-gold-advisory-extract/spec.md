# Spec: graphite_gold style + advisory-brief primitives extraction

Mode: light (no risk trigger fired)

- **Status:** Shipped

## Objective

Absorb a user-supplied dark consulting/advisory deck (a print HTML view + a
nav index + a shared `css/styles.css`) into the skill as a new
**`graphite_gold`** style, extract its reusable UI primitives
(chiefly the **accent-topline reasoning card + so-what netline**) into a
paste-ready, CSS-variable-themed block-recipe file, and harvest its multi-file
authoring + print-combiner workflow.

The source is a *persuasion-type* advisory brief (SCQA/pyramid), not a
reference-runbook — so no new narrative archetype; instead we name two
reusable persuasion-integrity conventions.

Scope adds one new style + one new blocks file + supporting registrations. No
existing style's JSON, mock, or rendered output changes.

## Why a new style (not an existing one)

The deck is a **desaturated** dark palette — warm champagne/antique-gold hero
(`#D4A96E`) on cool graphite/slate (`#111118`, cards `#1c1d28`) with a dusty
5-signal set (teal `#6DBEA3`, steel-blue `#7BB4CC`, clay-rose `#D46B6B`,
lavender `#9B8BD4`). No current dark style fits: `dark_tech`/`cyberpunk_neon`
are saturated & cold, `luxury_purple`/`nocturne_violet` are single-purple
brand-luxury, `noir_film` is monochrome, and `champagne_gold` is a **light**
wedding style. Name chosen from the color scheme: graphite base + antique gold.

## Acceptance Criteria

- [x] New `graphite_gold` JSON in `references/styles/dark.md` (§8) with the
  charcoal/champagne palette, Sora + DM Sans type, muted-multi-signal DNA,
  `border_radius:14`, `masthead:false`, `title_serif_italic:false`, plus the
  documented signal-token list and an 11-point **styling spec**.
- [x] Style index rows added in `references/styles/dark.md` (header count 7→8,
  index table) and `references/styles/index.md` (panorama 28→29, decision
  matrix, §4 new-style count).
- [x] New `references/blocks/advisory-brief.md` documenting the extracted kit —
  **A. reasoning cards:** accent-topline card, psec labeled triptych, so-what
  netline; **B. ranked lists & bands:** condition-list (key/minor/red +
  corner-tag), phaseflow (arrow-joined stages), pillband; **C. emphasis &
  chrome:** tinted callout, illustrative-warning banner, projection-ramp
  (SVG paths + HTML-overlay labels, no `<text>`), page chrome (eyebrow/brand
  topbar, gold-gradient rule, dotted-caps pagefoot). Each paste-ready, bound to
  deck CSS variables, pipeline-safe. Registered in `blocks/README.md` as a
  `block_refs` companion (not a new validator `card_type`).
- [x] Gallery mock `ppt-output/style-gallery/graphite_gold.html` — 1280×720,
  pipeline-safe (no forbidden CSS, no SVG `<text>`), shows the accent-topline
  cards + netline + condition list.
- [x] `references/principles/narrative-arc.md` names two persuasion conventions
  (so-what netline; illustrative-data honesty banner) — guidance only.
- [x] Harvested authoring pattern: `references/playbooks/print-combiner-playbook.md`
  documenting the separate-slide-files + shared-CSS + generated print view, with
  the `scripts/build-print.sh` combiner ported in.
- [x] Gates pass: `smoke_test.py --style graphite_gold`, `lint_diagram_recipes.py`
  (with `advisory-brief.md` added to its target list), `check_skill.py`.

## Boundaries

- Not minting a `worksheet`-style validator `card_type`; loaded via existing
  `block_refs` mechanism (mirrors diagram family + worksheet).
- The native deck uses rgba gradient washes on its tinted panels; the extracted
  primitives use solid theme-var fills + accent bars for pipeline-safety and
  lint-cleanliness (documented divergence, as worksheet did with black-fill
  inversion). The gold-gradient rule survives (theme-var → `transparent` stop).
- The 5-signal palette is graphite_gold-specific; the generic block recipe
  drives per-card color via `--cdot` and degrades to single `--accent-1` on
  single-accent decks.
- No other style touched.

## Testing Strategy

Goal-based verification (reference/design content, not testable logic): the
three smoke/lint scripts are the mechanical gate; visual QA is the 1280×720 mock
rendering correctly under the new palette.
