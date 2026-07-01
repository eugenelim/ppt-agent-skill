# Plan: claude-design-absorption

- **Spec:** [`spec.md`](spec.md)
- **Mode:** full (risk trigger: multi-feature / dependent tasks; structural — new style-contract field + new recipes)

## Assumption trio

- **Files touched:** `references/styles/light.md`, `references/styles/index.md`,
  `references/blocks/diagram.md`, `references/blocks/diagram-concept.md`,
  `references/design-runtime/design-specs.md`, `references/principles/taste-gate.md` (new),
  `references/principles/README.md`, `SKILL.md`,
  `references/playbooks/step4/page-review-playbook.md`, `scripts/visual_qa.py`,
  `references/typography.md`,
  `docs/specs/diagram-consistency-system/notes/diagram-taxonomy.md`, and genuine
  style-count references (`README.md`, `README_EN.md`, `references/style-system.md`,
  `scripts/gallery.py` docstring).
- **Done when:** the five gate scripts exit 0; gallery reports 28 styles with both
  new tiles; grep audits confirm each AC's tokens.
- **Not changing:** the 26 existing styles' JSON; pipeline scripts' logic/CLI;
  planning schema; any `diagram_mode`-parsing code (none is added).

## Declined-pattern register

- Tempted to add a separate `diagram-lineart` family file — **declining**;
  line-art is a variable rebinding in the existing theming contract, not new recipes.
- Tempted to give `consultant-2x2` / `quadrant-trajectory` their own recipe
  headings — **declining**; fold as variants of `matrix-quadrant` (matches the
  source skill's own treatment; avoids duplicate marker geometry).
- Tempted to add `diagram_mode` handling code to a script — **declining**; it's a
  prompt/doc contract; no consumer code exists or is wanted.
- Tempted to retrofit mono fonts into all 26 styles — **declining**; only the two
  new styles + typography.md guidance change.
- Tempted to switch to native pptxgenjs — **declining**; out of scope.

## Resolve-vs-surface disposition

- Which style carries `lineart`: **resolved** — only `schematic_blueprint`, so the
  mode is visibly opt-in (referent: user instruction "only for a given theme").
- Line-art default accent = light-theme electric violet `#A100FF`→`#7500C0`:
  **resolved** (referent: user instruction), described in generic color terms only.
- No irreversible risk / value conflict to surface.

## Tasks

### T1 — Two opt-in styles + schema field  ·  verify: visual/manual QA
`Tests:` `python3 scripts/gallery.py` exits 0 and prints `Total styles: 28`;
`grep -l 'anthropic_paper\|schematic_blueprint' references/styles/light.md`.
`Approach:` Read one existing light.md style for exact JSON shape + how gallery
renders it. Append `anthropic_paper` and `schematic_blueprint` JSON blocks. Add
`decorations.diagram_mode` (optional string) to the index.md §3 schema + field
table; add both rows to the §1 table and decision matrix. `schematic_blueprint`
sets `diagram_mode: "lineart"` and accent `["#A100FF","#7500C0"]` on warm paper;
`anthropic_paper` omits `diagram_mode` (filled).

### T2 — Theme-gated line-art render mode  ·  verify: goal-based
`Tests:` `python3 scripts/lint_diagram_recipes.py` exits 0; the added block
contains only `var(...)`/keyword values (no hex/rgb/named color).
`Approach:` Add a "线稿模式 (line-art) — 主题门控" subsection to `diagram.md`
after 主题契约: when active style `decorations.diagram_mode == "lineart"`, rebind
`--node-bg-from/to`→`transparent`, `--label-font`→mono for sublabels/axis-labels
(names stay `--font-primary`), thin strokes, accent on focal node only. Note it is
opt-in; unset = filled.

### T3 — Expanded conceptual recipes  ·  verify: goal-based  ·  depends on T2
`Tests:` `python3 scripts/lint_diagram_recipes.py` exits 0 (all new `### (id)`
recipes carry the 5 markers; no hardcoded colors; no forbidden techniques).
`Approach:` Add `spectrum-marker`, `iceberg`, `force-field`, `before-after`,
`causal-loop` recipes to `diagram-concept.md`, each modeled on the existing
mind-map/matrix templates (SVG `<polygon>`/`<path>`/`<line>` geometry, HTML `<span>`
overlays for all text, variables only). Add `consultant-2x2` + `quadrant-trajectory`
as variant subsections of the existing `matrix-quadrant` recipe. Register new
`diagram_type`s in the `diagram.md` selector table, SKILL.md resource routing note,
and the diagram-taxonomy note (additive "v2" entries).

### T4 — De-slop the title rule  ·  verify: goal-based
`Tests:` `grep` the new guidance in `design-specs.md`; `python3 scripts/check_skill.py`
exits 0.
`Approach:` In `design-specs.md` §A, add an explicit note demoting the decorative
accent underline under titles (AI-slop signal) while keeping `.overline`; adjust the
设计倾向 row that recommends 装饰线.

### T5 — Taste gate principle  ·  verify: goal-based
`Tests:` `python3 scripts/resource_loader.py menu --refs-dir references` lists
`taste-gate`; `python3 scripts/check_skill.py` exits 0.
`Approach:` Create `references/principles/taste-gate.md` (title + blockquote +
body per the principle-file convention). Wire into SKILL.md Step 5c + reference
index table; add to principles/README.md.

### T6 — Visual-QA bug-hunt upgrade  ·  verify: goal-based
`Tests:` `grep` the fresh-eyes / fix-and-verify tokens in the playbook;
`python3 scripts/check_skill.py` exits 0 (visual-QA contract snippets intact).
`Approach:` Add the bug-hunt discipline + inspection checklist to
`page-review-playbook.md`; add a short docstring pointer in `visual_qa.py` (no CLI
change).

### T7 — Mono utility type tier  ·  verify: goal-based
`Tests:` `grep -i 'mono' references/typography.md` shows the new tier section.
`Approach:` Add a mono-utility-tier section to `typography.md`.

### T8 — Count reconciliation 26→28  ·  verify: goal-based  ·  depends on T1
`Tests:` `grep -rn '26 风格\|26 种\|26 个' SKILL.md README.md README_EN.md references/ scripts/`
returns only non-style-count matches; gallery prints 28.
`Approach:` Update genuine style-count references to 28; leave unrelated "26"
matches alone.

## Rollout

Pure additive docs/reference change; no runtime migration. Revert = `git revert`
of the PR. No data, no infra.
