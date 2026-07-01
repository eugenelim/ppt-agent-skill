# Spec: claude-design-absorption

- **Status:** Implementing <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** `docs/specs/diagram-consistency-system/spec.md` (diagram theming contract + recipe lint)
- **Contract:** none
- **Shape:** docs/reference-content

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification is derivable from the gate
> scripts named in each Acceptance Criterion.

## Objective

Absorb the recognizable "Claude / Anthropic design" grammar — the *sharp-lines,
editorial, thinking/modeling* look — into the skill as **opt-in options**, with
**zero change to how the existing 26 styles render**. The mined source (Anthropic's
open-source `pptx` / `brand-guidelines` / `frontend-design` / `canvas-design`
skills, and the community "Schematic" diagram skill) is captured in
`.context/claude-design-mining.md`.

The load-bearing design decision: **line-art is a property a *style* opts into,
not a global mode.** It rides entirely on the existing diagram theming contract
(local semantic vars bound to deck CSS variables), so it needs no new diagram
recipes and no hardcoded colors — a style that declares `diagram_mode: "lineart"`
rebinds those vars to a stroke-only regime; every other style is untouched and
defaults to the current filled rendering.

## Acceptance Criteria

- [x] **AC1 — two new opt-in styles.** `references/styles/light.md` gains
  `editorial_paper` (warm cream + clay accent, serif+sans+mono, filled diagrams)
  and `schematic_blueprint` (warm paper + **light-theme electric-violet accent
  `#A100FF`→`#7500C0`**, hairlines, mono labels, `diagram_mode: "lineart"`). Both
  set `category: "light_premium"` (else `gallery.py` drops them from the grid).
  Both are complete per the index.md §3 JSON schema. **Both get a 1280×720 mock at
  `ppt-output/style-gallery/<style_id>.html`** (gallery.py references, does not
  generate these). `python3 scripts/gallery.py` runs clean and reports **28** total
  styles; both new tiles render in the 浅色高级 section of `index.html`.
- [x] **AC2 — existing gallery unaffected.** The 26 existing styles' JSON and mock
  files are byte-unchanged; the two additions are purely additive (no tile removed
  or restyled). Verified by `git diff` showing only additions in the existing
  styles' region.
- [x] **AC3 — theme-gated line-art mode.** `references/blocks/diagram.md` documents
  a `diagram_mode: "lineart"` branch of the theming contract that rebinds
  `--node-bg-from/to`→`transparent`, keeps borders hairline, routes sublabels/
  axis-labels to the mono font, and limits accent to the focal node — **all
  variable-driven, no literal colors.** Default (unset) = current filled behavior.
- [x] **AC4 — expanded conceptual recipes.** `references/blocks/diagram-concept.md`
  gains 5 new recipes — `spectrum-marker`, `iceberg`, `force-field`,
  `before-after`, `causal-loop` — each with all five markers (何时用 / 数据格式 /
  模板 / 自检 / 管线安全), plus `consultant-2x2` and `quadrant-trajectory` as
  documented variants of `matrix-quadrant`. All 7 new `diagram_type` strings —
  including the two variants — are registered in the `diagram.md` selector row (so
  routing resolves), SKILL.md routing, and the taxonomy note. The two variants are
  subsections (not `### (id)` headings), so the 5-marker lint applies only to the 5
  recipes.
- [x] **AC5 — de-slop the title rule.** `references/design-runtime/design-specs.md`
  demotes the decorative accent *rule/underline under titles* from a default
  (naming it an AI-slop signal) while explicitly **keeping the mono eyebrow
  (`.overline`)**.
- [x] **AC6 — taste gate.** A new `references/principles/taste-gate.md` captures
  the anti-slop self-critique (the 3 AI-default clusters; "would I produce this
  for any brief?"; the remove-test; one signature move; focal-accent discipline)
  and a pre-output checklist; SKILL.md Step 5c and the reference index point to it.
- [x] **AC7 — visual-QA bug-hunt.** `references/playbooks/step4/page-review-playbook.md`
  adopts the "assume there are problems / fresh-eyes subagent / fix-and-verify
  loop" discipline with the concrete inspection checklist; `scripts/visual_qa.py`
  gains a short docstring pointer. No existing `check_skill.py` visual-QA contract
  token is removed.
- [x] **AC8 — mono utility tier.** `references/typography.md` documents a mono
  utility type tier (DM Mono / Geist Mono / IBM Plex Mono) for captions, data
  labels, and reference markers, with the "mono = technical content only, names in
  sans" rule.
- [x] **AC9 — all gates green.** `python3 scripts/lint_diagram_recipes.py`,
  `scripts/check_skill.py`, `scripts/planning_validator.py`,
  `scripts/contract_validator.py`, and `scripts/gallery.py` all exit 0. Style-count
  "26" references updated to "28" wherever they are genuine style counts.
- [x] **AC10 — no brand attribution on the new work.** The violet palette and both
  new styles are described in generic color/aesthetic terms only — no organization
  name is attached to the violet accent or used as a new `style_id`/`style_name`.
  (The pre-existing `mocha_editorial` "Anthropic" inspiration string is grandfathered
  and out of scope for this AC.) Verify: the violet hexes (`#a100ff`/`#7500ff`-family)
  never co-occur with a brand token; new style ids are generic.

## Boundaries (out of scope)

- No change to the HTML→SVG→PPTX pipeline scripts' logic or CLI.
- No change to the planning JSON schema or `planning_validator` rules.
- No native pptxgenjs generation path (our HTML-first pipeline stays).
- No re-theming of the 26 existing styles (no mono fonts retrofitted, etc.).
- `diagram_mode` is a doc/prompt-level contract read by the HTML-generation
  agent; **no script parses or enforces it** (kept intentionally out of code).

## Testing Strategy

All tasks verify **goal-based** (run the relevant gate script / grep) except AC1,
which is **visual/manual QA**: run `scripts/gallery.py`, confirm exit 0, 28 styles
reported, and both new tiles present in the generated `index.html`. There is no
application logic and thus no TDD-mode task. The five gate scripts in AC9 are the
mechanical termination criteria.

## Assumptions

- `diagram_type` is not enum-validated in any script (verified: no enum in
  `scripts/`), so new types are additive and only bound by `lint_diagram_recipes.py`.
- `gallery.py` auto-discovers styles by globbing `styles/*.md` for `style_id` and
  computes the count dynamically (verified), so new styles append without gallery
  edits beyond the style JSON itself.
- `check_skill.py` does not assert the style count, but does assert specific tokens
  in SKILL.md / cli-cheatsheet.md / README.md — edits must be additive there.
