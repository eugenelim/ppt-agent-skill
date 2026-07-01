# Plan: persistent_chrome deck flag

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

This is a prompt-pipeline wiring change: no runtime code, no new script. The
flag is a boolean that rides the existing three-stage path — outline header →
planning JSON → page-html emission — expressed entirely in the stage documents
the subagents read. The riskiest part is not the flag itself but its
**interaction with the mandatory unified nav-skeleton contract** in
`design-specs.md` §A (content pages *must* carry `header.slide-header` +
`footer.slide-footer`): the runbook footer is structurally unlike the plain
20px `.slide-footer`, so §A gains a flag-gated exception, and every emission
instruction is conditioned on the flag being set so a deck that leaves it off is
byte-for-byte unchanged.

Order of operations: define the field at its source (outline), then teach each
downstream stage to carry/consume it, authoring the §A exception before the
page-html stage that depends on it. The chrome markup is **not** reinvented —
the page-html stage is pointed at the existing `masthead` and `footer` recipes
in `references/blocks/worksheet.md` group C, which already pass the recipe lint.

## Constraints

- No ADR/RFC governs this. The binding prior decision is the sibling spec
  `schematic-blueprint-runbook-restyle`, which extracted the worksheet group-C
  chrome recipes and deferred this engine-level flag to
  `docs/backlog.md` §schematic-blueprint-runbook-restyle (3rd item).
- `pipeline-compat.md` forbidden-technique list bounds the emitted markup;
  reusing the group-C recipes verbatim keeps that guarantee.

## Construction tests

**Integration tests:** none beyond per-task tests — the pipeline stages are
prompt documents exercised by subagents at runtime, not unit-testable code.

**Manual verification (required — the second half of spec AC1):** read-through
consistency check across the four edited stage documents + `design-specs.md` §A —
confirm the flag name is spelled identically everywhere, every masthead/footer
emission instruction is inside a "when `persistent_chrome` is set" conditional
(no unconditional emission), the flag-off path adds nothing to the rendering
instructions, and no page can be instructed to render both the plain skeleton and
the chrome. Record the result of this read-through in the PR / spec Changelog,
since no automated flag-off render diff exists in the gates.

**Cross-cutting gate:** `smoke_test.py`, `lint_diagram_recipes.py`,
`check_skill.py` all pass (spec AC7). `lint_diagram_recipes.py` re-confirms the
untouched `worksheet.md` group-C recipes stay pipeline-safe; `check_skill.py`
confirms no broken cross-references were introduced by the doc edits.

## Design (LLD)

### Design decisions

- **Flag home = outline header, not `style.json` or `requirements-interview`.**
  Deck-global narrative decisions already live in the outline header
  (核心论点/密度倾向/…); `persistent_chrome` is a deck-authoring choice
  orthogonal to style, so it lands there. Rejected: piggy-backing on
  `style.json decorations.masthead` — that is a style-level DNA hint and would
  couple orientation chrome to one style. Traces to: AC2.
- **Masthead additive, footer replacing — with concrete geometry.** The plain
  skeleton positions header/footer as absolute overlays (`.slide-header`
  `top:20px; height:50px`; `.slide-footer` `bottom:12px; height:20px`), so a
  flow-layout masthead/footer would not "stack above/replace" them coherently.
  Resolution (fixed in `design-specs.md` §A, T3): with the flag on, all three
  chrome elements are **absolute bands** within the existing 40px side margins —
  masthead `top:20px` (~32px tall, y≈20–52); `slide-header` **downshifted** to
  `top:64px` (retained so per-page titles survive navigation); content area
  starts y≈120px with usable height **≈500px** (vs 580px); runbook footer
  `bottom:12px` (~56px tall) **replacing** `.slide-footer` entirely.
  `density_contract` for chrome-on content pages is computed against ≈500px.
  Traces to: AC4, AC5.
- **Copy reaches page-html via a `deck_chrome` object, not the outline.** The
  page-html stage never reads the outline, and the group-C recipes ship
  `schematic_blueprint` sample literals — so the planning stage (which does read
  the outline) records `deck_chrome.title` (deck topic/title) + `deck_chrome.subtitle`
  (outline 核心论点) into every page's planning JSON, and the page-html stage
  fills the recipe text slots from it (unsourced slots like a revision string are
  omitted, never invented). Traces to: AC3, AC4, AC6.
- **Emission gated on `page_type == content` AND flag set.** Keeps
  cover/section/toc/end on their existing treatment and keeps flag-off decks
  unchanged. Traces to: AC1, AC4.

### Interfaces & contracts

The interface surface is documentation, not a `contracts/` artifact:
- **Outline field:** `持久化页框 (persistent_chrome)：{on / off}` in the outline
  header format skeleton; absent = off.
- **Planning-JSON fields:** `persistent_chrome` (boolean) plus, when true, a
  `deck_chrome` object (`{title, subtitle}`) — both recorded by the planning
  stage on every page's planning JSON, read by the page-html stage.
  `planning_validator.py` ignores unknown top-level keys, so no validator change
  is needed. Traces to: AC2, AC3, AC4.

### Dependencies & integration

Consumes the existing `masthead` + `footer` recipes in
`references/blocks/worksheet.md` group C (reused verbatim). No new external
dependency. Traces to: AC4, AC6.

## Tasks

### T1: Outline deck-global `persistent_chrome` field

**Depends on:** none

**Touches:** references/playbooks/outline-phase1-playbook.md

**Tests:**
- Goal-based: `grep persistent_chrome references/playbooks/outline-phase1-playbook.md`
  shows the field in the outline header format skeleton, enumerated `{on / off}`.
  Verifies spec AC2.
- Goal-based: the "absent = off" default is stated in the `字段枚举约束` list
  alongside 密度倾向, so the format contract carries the default-off rule at its
  source. Verifies the default-off half of spec AC1.

**Approach:**
- Add `持久化页框 (persistent_chrome)：{on / off}` to the `# 大纲` header block in
  the `outline.txt 强制格式骨架` section, after `密度曲线`.
- Add an enum-constraint bullet: `持久化页框` must be `{on, off}`, absent = off.
- Add one sentence tying it to 参考型 (reference-archetype) decks, cross-linking
  the existing 参考型叙事 pointer.

**Done when:** the two greps above match and `check_skill.py` passes.

### T2: Planning stage carries the flag + deck chrome copy into planning JSON

**Depends on:** T1

**Touches:** references/prompts/step4/tpl-page-planning.md

**Tests:**
- Goal-based: `grep -E 'persistent_chrome|deck_chrome' references/prompts/step4/tpl-page-planning.md`
  shows a step instructing the planning stage to read the outline value and
  record both `persistent_chrome` and (when set) `deck_chrome` into the planning
  JSON. Verifies spec AC3.
- Goal-based: the instruction states the deck-global read is **mandatory on
  every page** (each per-page planning agent re-records the same values), so the
  chrome cannot silently drop on one page. Verifies the fan-out risk mitigation.

**Approach:**
- In the 执行链路 step that reads the outline (step 1 — currently scoped to
  "只关注你这一页"), add an explicit deck-global sub-read: also extract the
  deck-global `持久化页框 (persistent_chrome)` value from the outline header
  (this is in addition to the per-page fields, not instead of them).
- Add an instruction to record, at the top level of the planning JSON:
  `persistent_chrome` (boolean; default `false` when absent), and when it is
  `true`, a `deck_chrome` object `{title, subtitle}` where `title` = deck
  topic/title and `subtitle` = outline 核心论点 — the copy the masthead/footer
  recipes need, since the page-html stage does not read the outline.
- State that this deck-global read + record is **mandatory on every page**, so
  each per-page planning agent emits the same flag + copy (a single missed page
  would otherwise drop the chrome for that page only).

**Done when:** both greps match and `check_skill.py` passes.

### T3: design-specs §A flag-gated nav-skeleton exception

**Depends on:** none

**Touches:** references/design-runtime/design-specs.md

**Tests:**
- Goal-based: `grep persistent_chrome references/design-runtime/design-specs.md`
  shows §A documenting the flag-gated exception. Verifies spec AC5.
- Goal-based + read-through: the new exception subsection states **concrete band
  geometry** (positions + heights for masthead / downshifted slide-header /
  runbook footer) and the reduced content usable-height. `grep` confirms the px
  values are present in the file; a read of the subsection confirms they belong
  to the three bands (grep can't scope to a subsection, so the read is the real
  check). Verifies the geometry half of spec AC5 (and closes the vertical-budget
  concern).

**Approach:**
- In §A, after the 统一页脚区 skeleton block, add a `持久化页框 (persistent_chrome)`
  exception subsection. Flag off → skeleton exactly as specified today. Flag on
  + `content` page → the three absolute chrome bands within the existing 40px
  side margins:
  - **Masthead:** `position:absolute; top:20px; left:40px; right:40px;` — the
    group-C masthead (~32px tall, y≈20–52).
  - **slide-header:** downshifted to `top:64px` (retained; per-page title
    survives), height ~44px (y≈64–108).
  - **Content area:** starts y≈120px, usable height **≈500px** (vs 580px);
    `density_contract` is computed against ≈500px on chrome-on content pages.
  - **Runbook footer:** `position:absolute; bottom:12px; left:40px; right:40px;`
    — the group-C footer (~56px tall) **replacing** `.slide-footer` entirely.
  - Both chrome recipes are from `blocks/worksheet.md` group C, deck-var-bound.
- State the invariant explicitly: a page renders the plain skeleton **or** the
  chrome frame, never both.

**Done when:** both greps match, the exception names worksheet group C and gives
band positions/heights + reduced usable-height, and `smoke_test.py` +
`check_skill.py` pass.

### T4: page-html stage emits masthead + footer when flag set

**Depends on:** T2, T3

**Touches:** references/playbooks/step4/page-html-playbook.md, references/prompts/step4/tpl-page-html.md

**Tests:**
- Goal-based: `grep persistent_chrome references/playbooks/step4/page-html-playbook.md
  references/prompts/step4/tpl-page-html.md` shows both docs instructing: when
  planning `persistent_chrome` is set AND `page_type == content`, emit the
  worksheet group-C masthead (top) + footer (bottom), bound to deck CSS
  variables. Verifies spec AC4.
- Goal-based: the instruction names the deck variables (`--text-primary`,
  `--accent-1`, `--card-bg-from`, `--font-mono`, `--font-primary`) and directs
  every recipe text slot to be filled from `deck_chrome` + per-page fields, with
  unsourced slots omitted and the group-C sample literals never emitted. Verifies
  spec AC6.
- Gate: `smoke_test.py` (no new `::before`/`::after` — advisory), `lint_diagram_recipes.py`,
  `check_skill.py` all pass. Verifies spec AC7.

**Approach:**
- In `page-html-playbook.md`: add `persistent_chrome` (+ `deck_chrome`) to the
  Phase-1 field table, and extend the Phase-5 「统一导航骨架」 section with a
  flag-gated block pointing at `references/blocks/worksheet.md` group C (masthead
  + footer), reiterating the §A band geometry, the deck-variable binding, and
  copy-from-`deck_chrome` (never the recipe literals).
- In `tpl-page-html.md`: add `persistent_chrome` + `deck_chrome` to the fields
  extracted in 执行链路 step 1, and add a conditional emission step (content pages
  only) that fills the recipe text slots from `deck_chrome`.
- Confirm the emission text carries no forbidden techniques, no hardcoded
  colors/fonts, and no group-C sample literals (structure inherited verbatim;
  copy from `deck_chrome`).

**Done when:** the greps match, and the three gate scripts pass.

## Rollout

- **Delivery:** behind the `persistent_chrome` flag, default off — fully
  reversible and inert for existing decks. No infra, no external system, no data
  migration.
- **Deployment sequencing:** none beyond the intra-plan task order (field defined
  before it is consumed; §A exception authored before the page-html stage that
  relies on it).

## Risks

- **Flag name drift across five files.** The whole feature is a consistent
  string threaded through separate documents; a typo silently breaks
  propagation. Mitigated by the per-task greps and the manual read-through.
- **Per-page fan-out inconsistency (runtime, not edit-time).** `persistent_chrome`
  is deck-global but is re-extracted and re-recorded by each per-page planning
  subagent (each reads "只关注你这一页"). If one page's agent misses the
  deck-global read, that single page silently drops the chrome — a
  different failure from the string-drift risk above (which is about the edited
  docs, not the N runtime agents). Mitigated by T2's explicit "mandatory on every
  page" instruction; a deck-level shared artifact both stages read would remove
  the redundancy but does not exist in the current pipeline (page-html reads only
  per-page planning JSON + `style.json`), so per-page redundancy is accepted.
- **§A exception under-specified → agent renders both skeleton and chrome.**
  Mitigated by stating the "one or the other, never both" invariant explicitly
  in T3.
- **Vertical budget within the 720px canvas height (580px plain-skeleton content area).** masthead + slide-header + runbook footer is more
  top/bottom chrome than the plain skeleton; on dense pages content could crowd
  or overflow. Mitigated (not just accepted): the §A exception fixes the reduced
  usable height (≈500px) explicitly and requires `density_contract` to be
  computed against it on chrome-on content pages, so budget accounting matches the
  actual content area rather than the plain-skeleton 580px.

## Changelog

- 2026-07-01: initial plan.
- 2026-07-01: revised after spec-mode adversarial review — fixed masthead/footer
  band geometry against the absolute nav-skeleton (T3), added `deck_chrome` copy
  propagation so masthead/footer text reaches the page-html stage instead of
  leaking the group-C sample literals (T2/T4), made AC1 default-off honest
  (grep + recorded read-through), and added the per-page fan-out risk.
- 2026-07-01: implemented T1–T4; all three gates green
  (`smoke_test.py`/`lint_diagram_recipes.py`/`check_skill.py` exit 0). Diff-mode
  adversarial review pass 1 → applied all 6 findings: pinned the masthead/footer
  copy-slot→`deck_chrome` mapping so per-page agents don't guess and the reserved
  bands aren't empty (Concerns 4–5), reworded the vertical-budget risk (Nit 6),
  flipped spec/plan Status + checked ACs (Blockers 1–2).
- 2026-07-01: **AC1 default-off read-through — run and passed.** Verified across
  all five edited stage files: (1) the flag handle `persistent_chrome` is spelled
  identically in every file; (2) every masthead/footer emission instruction sits
  inside a `persistent_chrome`-set + `page_type == content` conditional — grep
  found no unconditional chrome emission; (3) the flag-off / flag-absent path adds
  nothing to the rendering instructions (the plain slide-header/slide-footer
  skeleton sections are untouched); (4) both `design-specs.md` §A and the
  page-html playbook state the "renders the plain skeleton **or** the chrome
  frame, never both" invariant. AC1 satisfied.
