# Spec: schematic_blueprint → delivery-runbook restyle + worksheet primitives

Mode: light (no risk trigger fired)

- **Status:** Shipped

## Objective

Restyle the `schematic_blueprint` style to match the visual language of a
user-supplied engineering-delivery runbook reference document (an editorial
technical document) — color, type, spacing, and slide design — and extract its
reusable UI primitives (chiefly the discussion/timeline **table-as-worksheet**)
into the skill as paste-ready, CSS-variable-themed block recipes.

Scope is limited to `schematic_blueprint`. No other style's JSON, mock, or
rendered output changes.

## Acceptance Criteria

- [x] `schematic_blueprint` JSON in `references/styles/light.md` adopts the
  runbook palette (pure white paper `#ffffff`/`#fafafa`, hard-black rules,
  single electric-violet `#a100ff` focus), typography (Fraunces display +
  Inter Tight body + JetBrains Mono labels), and DNA (zero radius, zero
  shadow, `masthead: true`, `diagram_mode: "lineart"` retained).
- [x] Style index rows updated in `references/styles/light.md` and
  `references/styles/index.md` (panorama + decision matrix).
- [x] Gallery mock `ppt-output/style-gallery/schematic_blueprint.html`
  rebuilt to demonstrate the new look and showcase the worksheet table;
  stays 1280×720 and pipeline-safe (no forbidden CSS, no SVG `<text>`).
- [x] New `references/blocks/worksheet.md` documents the full extracted
  primitive kit (three groups) — **A. tables/worksheets:** responsibility-matrix
  (RACI), discussion-worksheet (fill-in template), schedule-table (detailed
  timeline), escalation-matrix (with cadence variant); **B. checklist/status:**
  checklist (with preflight/TOC variants), status-block (gate/failure);
  **C. page chrome:** masthead, cover-header, section-marker, spotlight-callout,
  footer — each paste-ready, bound to deck CSS variables, pipeline-safe, in the
  fixed recipe section order. Registered in `references/blocks/README.md` as a
  `block_refs` companion (not a new validator `card_type`).
- [x] `references/styles/light.md` §10 carries a **styling spec** capturing the
  source's fine styling: border-rule hierarchy (3/2/1px + dashed), black-fill
  inversion, italic-purple `<em>`, Fraunces opsz/weight map, mono letter-spacing
  ladder, single-focus discipline, color roles, tabular numerals, spacing
  rhythm, checkbox glyph, and eyebrow/masthead decorations.
- [x] Gates pass: `smoke_test.py --style schematic_blueprint` (style JSON +
  mock compat + typography), `lint_diagram_recipes.py`, `check_skill.py`.
- [x] `smoke_test.py` gains a **warning-level** pseudo-element-decoration check
  (`::before`/`::after` declaring `content:` → prefer a real `<span>`/`<div>`
  per `pipeline-compat.md`); warning not hard-fail because `html2svg.py` has a
  lossy fallback and 10 existing mocks rely on it. Also documents the deck-level
  narrative archetype: `principles/narrative-arc.md` gains a reference-runbook
  section and the outline playbook a pointer (guidance only — engine-level
  enum/page_type changes are deferred to `docs/backlog.md`).

## Boundaries

- Not minting a new `worksheet` validator `card_type` (would be a
  public-interface change to the planning enum + validators — out of scope
  and higher-risk). Loaded via the existing `block_refs` mechanism instead,
  mirroring the diagram-family files.
- Not porting the runbook's `warn`/`ok` semantic colors into `accent.secondary`
  — kept as documented local signal tokens so the "single electric-violet
  focus" discipline holds.
- No other style touched.

## Testing Strategy

Goal-based verification (this is reference/design content, not testable logic):
the three smoke/lint scripts above are the mechanical gate; visual QA is the
1280×720 mock rendering correctly under the new palette.
