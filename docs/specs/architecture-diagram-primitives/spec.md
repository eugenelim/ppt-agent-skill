# Spec: architecture-canvas primitives + seed icons

Mode: light — a dogfood run of the `assimilate-slides` skill (its steps are the
plan). Parented by `assimilate-slides-skill`.

- **Status:** Shipped <!-- flips to Shipped at the skill's GATES & SHIP step -->
- **Owner:** eugenelim
- **Constrained by:** none

## Objective

Absorb a maintainer-supplied engineering / data-platform **session deck**
(referred to only generically — no source identity anywhere) into the skill as
reusable form, following `assimilate-slides`. The deck's *style* matches the
existing `schematic_blueprint` (line-art on white paper, electric-violet
`--accent-1` focus), so **no new style is minted**. Its value is (a) a signature
**architecture-canvas** primitive — layered horizontal zones of icon-node cards
joined by labeled connectors — added to the `diagram-architecture` family, and
(b) a **seed set of architecture icons** redrawn idea-level into the searchable
icon library. A 1280×720 detailed mock demonstrates both under
`schematic_blueprint`.

## Classification (recorded per the skill's step 3)

- **Absorption shape:** primitives-only — matches `schematic_blueprint`
  (line-art diagram grammar + electric-violet-on-white focus). The deck is a
  corporate-sans cousin (its body sans differs from the style's Fraunces/Inter
  pairing), but the *reusable primitive grammar* is style-agnostic and binds to
  the deck's CSS variables, so it renders faithfully under `schematic_blueprint`.
  **No style JSON, no board-index change.**
- **Board category:** n/a (no new style); the demo runs under `light_premium` /
  `schematic_blueprint`.
- **Narrative type:** solution/offering session — uses existing structures
  (capability walk + layered architecture + an agent-workflow flow + a
  year-over-year adoption ramp). The ramp maps to the **existing**
  `advisory-brief.md` `projection-ramp` primitive. Narrative decision: **none**
  (no new archetype/convention; see `narrative-and-playbooks` review).
- **Discarded (no reusable form):** two image-only divider slides (single image
  ≈72–76% of the canvas, <120 chars) plus the photo-collage slide — dropped, not
  templated.
- **Scrub:** clear across all §39 identifier classes (deck/file name, client,
  customer, employer, project code-name, personal names, emails, internal URLs,
  ticket IDs, product/offering names, verbatim body text); re-checked against the
  full diff at ship.

## Acceptance Criteria

- [x] An **architecture-canvas** recipe (icon-node cards in labeled horizontal
  zones + a data-spine + labeled connectors) is added to
  `references/blocks/diagram-architecture.md` — 5-marker format, CSS-variable
  bound, pipeline-safe, icons inlined verbatim. `lint_diagram_recipes.py` passes.
- [x] ≥8 architecture icons (spanning ≥2 catalog categories) are redrawn
  idea-level into `assets/icons/` with `catalog.json` entries and generic
  provenance; `icon_search.py --validate` exits 0.
- [x] `principles/narrative-arc.md` is reviewed; the one-line decision is
  recorded here (**none**). No validator/enum/`page_type` change is made.
- [x] A 1280×720 detailed mock under `schematic_blueprint` demonstrates the
  architecture-canvas primitive with inlined library icons; it is pipeline-safe,
  gated by the standing `scripts/test_arch_canvas_mock.py` (smoke_test's
  forbidden-CSS/typography checkers + inline-icon check); `gallery.py`
  regenerates without error.
- [x] No source identity appears in any committed file (final scrub pass clear).
- [x] Gates pass: `lint_diagram_recipes.py`, `smoke_test.py --style
  schematic_blueprint`, `check_skill.py`, `icon_search.py --validate`.

## Testing Strategy

Goal-based (reference/design content): the four gates above are the mechanical
check; visual QA is the mock rendering correctly at 1280×720 under the palette.
