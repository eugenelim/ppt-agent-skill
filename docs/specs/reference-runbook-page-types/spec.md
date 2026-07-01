# Spec: reference-runbook-page-types

- **Status:** Implementing <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Brief:** none
- **Discovery:** none
- **Contract:** none <!-- the "public interface" is the internal planning-JSON page_type enum; its authority is scripts/planning_validator.py VALID_PAGE_TYPES + the two outline/planning playbooks, not a contracts/<type>/ file. -->
- **Shape:** data

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

A PPT author building a **reference runbook** (a deck "meant to be used, not
read once" — SOP, delivery handbook, playbook; see
[`references/principles/narrative-arc.md` §参考型叙事](../../../references/principles/narrative-arc.md))
can divide the deck with **inline** section dividers and close it on
**cross-cutting reference back-matter** instead of a persuasive CTA. Two new
`page_type` values make this expressible end-to-end through the planning
public interface:

- **`section-marker`** — a *divider-led* content page whose chrome is a
  lightweight `§ NN` + mono kicker + 2px rule at the top, with room for the
  section's opening lead and first artifact below. It is distinct from the
  existing full-page **`section`** (a whole-page breather, `visual_weight ≤ 3`,
  no body content): a skimming reader of a runbook does not need a whole
  breathing page at every stage boundary.
- **`reference`** — a back-matter reference page that carries an operating
  artifact (responsibility matrix / quality gates / escalation path / glossary)
  rather than an argument. It reuses the paste-ready
  [`references/blocks/worksheet.md`](../../../references/blocks/worksheet.md)
  recipes via `block_refs` — no new component HTML is authored.

Both values are accepted by every stage that reads `page_type` — the outline
stage, the page-planning stage, `planning_validator.py`, and the HTML-contract
stage (`contract_validator.py`) — with no "unrecognized page_type" warning
anywhere. Each is **both** a `narrative_role` and a `page_type` (self-mapping,
exactly like `cover`/`toc`/`section`) and routes to a real
`references/page-templates/` recipe. Both carry the reference archetype's
**persistent chrome** (`header.slide-header` + `footer.slide-footer`), so the
HTML-stage validators require chrome on them as they already do for
`content`/`toc`/`section`. The mandatory-skeleton rules "each Part opens with a
full-page `section`" and "the deck closes on a CTA/`end`" are **relaxed for the
reference-runbook archetype only** — a runbook divides inline with
`section-marker` and may close on `reference` back-matter. Persuasive decks are
unchanged: their skeleton, enums, and validation behave exactly as before, the
change being purely additive enum entries.

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines.
*Always do* applies without asking; *Ask first* requires human sign-off
before proceeding; *Never do* is a hard rule, even under time pressure.

### Always do

- Keep **all** `page_type` consumer sites in lockstep in the same change — the
  value-set is hardcoded in more than one validator:
  - `scripts/planning_validator.py` — `VALID_PAGE_TYPES`, `VALID_NARRATIVE_ROLES`.
  - `scripts/contract_validator.py` — `NON_DASHBOARD_PAGE_TYPES` and the
    `validate_html` header/footer branch (so no "unrecognized page_type" warn).
  - `scripts/visual_qa.py` and `scripts/smoke_skill.py` — the header/footer
    page_type sets and `smoke_skill`'s `PAGE_TEMPLATE_EXPECTATIONS`.
  - `references/playbooks/outline-phase1-playbook.md` — 页面类型映射 enum,
    叙事角色 enum, and 叙事角色→page_type map.
  - `references/playbooks/step4/page-planning-playbook.md` — page_type enum +
    narrative_role list.
- Theme every recipe/template to deck CSS variables and keep it pipeline-safe
  (real `<table>`/`<div>`, no SVG `<text>`, no `mask-image`/`conic-gradient`/
  `background-image:url()`), per `references/blocks/pipeline-compat.md`.
- Update the prose that would otherwise self-contradict: the "参考型不新增枚举"
  claims in `narrative-arc.md` and `outline-phase1-playbook.md`, and the
  page_type value-list / count prose in `SKILL.md` and `references/README.md`.

### Ask first

- Adding a **third** new `page_type` beyond `section-marker` and `reference`
  (e.g. splitting back-matter into per-artifact types) — the agreed shape is
  exactly these two.
- Authoring any **new** component recipe in `worksheet.md` (e.g. a bespoke
  glossary block) — glossary uses a plain definition-list treatment reusing an
  existing `card_type`; do not mint a new recipe without sign-off.
- Changing the density-budget table or any existing enum *value* (layout hints,
  card types, chart types, narrative roles already present).

### Never do

- **No new top-level dependency and no new module/script boundary** — this is
  markdown-doc + one Python enum-set edit; add no runtime deps, no new script.
- Do not make the new types mandatory or alter the persuasive-deck skeleton,
  enums, or validation — reference behavior is additive and archetype-gated.
- Do not turn a worksheet recipe into a validator `card_type`; back-matter
  consumes them via the existing `block_refs` mechanism only.
- Do not hardcode colors in any recipe/template except the documented
  semantic-signal carve-out already whitelisted in `lint_diagram_recipes.py`.

## Testing Strategy

- **Enum acceptance (`section-marker`, `reference` validate; unknowns still
  reject): TDD.** A compressible invariant over `validate_page` — a **complete**
  page (anchor card + `director_command` + `decoration_hints`, since those
  universal rules fire on every page_type) with each new `page_type` produces
  no `invalid page_type` error, and a bogus value still does. The test asserts
  specifically on the absence of the `invalid page_type` substring (not
  `result.ok`), so co-firing structural errors can't mask the check. This is the
  load-bearing public-interface behavior, so it gets a real regression test.
- **Page-templates load through the router: goal-based check, durable.** The
  new page-templates are added to `smoke_skill.py`'s `PAGE_TEMPLATE_EXPECTATIONS`,
  which builds a page per `page_type`, runs `planning_validator`, and asserts
  `resource_loader` injects the template body — a committed regression guard for
  the `page_type → page-templates/<stem>.md` route, not a throwaway probe.
- **HTML-contract stage accepts the new types: goal-based check.** A synthetic
  rendered page with chrome passes `contract_validator.validate_html` for each
  new type with no "unrecognized page_type" warning — exercised in the T1
  regression test alongside the planning-validator cases.
- **Recipe/lint/doc contract intact: goal-based check.** `smoke_test.py`,
  `lint_diagram_recipes.py`, and `check_skill.py` run green — covering
  recipe-marker completeness, pipeline-safety, and the routing-doc contract.
  `smoke_skill.py` supplies the router coverage above and must show **no net-new
  failures** from this change (it is separately red for pre-existing fixture
  drift, out of scope). No new component logic to unit-test.
- **Density/skeleton guidance reads correctly: manual QA.** The inline-vs-full-page
  choice and the archetype-gated "end relaxation" are prose guidance for a
  downstream LLM; correctness is a human read of the playbook, not an automated
  check.

## Acceptance Criteria

- [x] `scripts/planning_validator.py` accepts `page_type` values `section-marker`
  and `reference` (added to `VALID_PAGE_TYPES`) on a **complete** page; an unknown
  value still raises `invalid page_type`. A committed regression test in `scripts/`
  covers both directions, asserting on the `invalid page_type` substring
  specifically.
- [x] `narrative_role` values `section-marker` and `reference` are recognized by
  `planning_validator.VALID_NARRATIVE_ROLES` **and** appear in the outline
  playbook's closed 叙事角色 enum — the two axes stay consistent (no value that is
  a `narrative_role` in one site but rejected in another).
- [x] `scripts/contract_validator.py` treats both new types as chrome-bearing
  (added to the `validate_html` `("content","toc","section")` header/footer set)
  and dashboard-barred (added to `NON_DASHBOARD_PAGE_TYPES`); neither emits an
  `unrecognized page_type` warning. `scripts/visual_qa.py` and
  `scripts/smoke_skill.py` header/footer sets match.
- [x] `references/playbooks/outline-phase1-playbook.md` lists both new values in
  the 页面类型映射 enum (lines ~95/116) and the 叙事角色 enum (lines ~94/115), adds
  self-mapping rows to the 叙事角色→page_type map (as `cover`/`toc`/`section`
  already are), and carries a guidance note on inline `section-marker` vs
  full-page `section`.
- [x] `references/playbooks/step4/page-planning-playbook.md` documents both new
  `page_type` values in its enum (lines ~111/207) and narrative_role lists
  (lines ~13/208), the inline-vs-full-page choice, and the back-matter roles
  (RACI / quality-gates / escalation / glossary) with the worksheet `block_refs`
  each consumes — glossary via the existing `card_type:list` (no new recipe).
- [x] `references/page-templates/section-marker.md` exists as a paste-ready,
  CSS-variable-themed, pipeline-safe recipe (reusing the `worksheet.md`
  cover-header/section-marker chrome, including persistent header/footer), and
  `references/page-templates/reference.md` exists documenting the back-matter
  page hosting the worksheet recipes.
- [x] `smoke_skill.py`'s `PAGE_TEMPLATE_EXPECTATIONS` covers both new types, so a
  built page with `page_type:"section-marker"` and one with `page_type:"reference"`
  validate and resolve their page-template body through `resource_loader`.
- [x] The mandatory-skeleton **Part-first-page** rule is relaxed for the
  reference-runbook archetype: a Part may open with inline `section-marker`
  instead of a full-page `section` (documented in the outline playbook +
  narrative-arc.md).
- [x] The mandatory-skeleton **deck-close** rule is relaxed for the
  reference-runbook archetype: a runbook may close on `reference` back-matter
  instead of a `close`/`cta` → `end` finale (documented in the outline playbook +
  narrative-arc.md). Persuasive-deck skeleton, enums, and validation are
  unchanged except for the additive enum entries.
- [x] `narrative-arc.md` §参考型叙事 and `outline-phase1-playbook.md` no longer
  claim "不新增枚举"; both point at the new page_types.
- [x] `SKILL.md` and `references/README.md` page_type value-list / page-template
  count prose reflect the two new values/templates (count `4 个页面模板` → `6`).
- [x] Gates pass: `python3 scripts/smoke_test.py`, `python3 scripts/lint_diagram_recipes.py`,
  `python3 scripts/check_skill.py` (zero errors). `smoke_skill.py`'s new-type router
  coverage (`planning-validator-{section-marker,reference}` +
  `resource-loader-resolve-{section-marker,reference}`) passes and this change adds
  **zero** net-new `smoke_skill` failures; `smoke_skill` overall is red only for
  pre-existing, unrelated drift (missing `references/charts/{kpi,metric-row}.md` +
  `references/styles/runtime-style-rules.md`), tracked in `docs/backlog.md`
  (deferred: smoke-skill-pre-existing-fixture-drift).

## Assumptions

- Technical: the `page_type` value-set is hardcoded in **seven** consumer sites,
  not three — `planning_validator.py:29`, `contract_validator.py:42,884,892`,
  `visual_qa.py:457`, `smoke_skill.py:45,434`, the two playbooks
  (`outline-phase1-playbook.md:95,116`, `page-planning-playbook.md:111,207`), and
  the schema doc `references/prompts.md:254` (source: repo grep; spec-mode review
  found `contract_validator` et al., and an EXECUTE-time grep found `prompts.md` —
  see [[ppt-page-type-enum-consumers]]).
- Technical: `contract_validator.py` is a real gate (`SKILL.md:399`) but is **not**
  run by `smoke_test.py` phase 1, so its `unrecognized page_type` warning is
  invisible to the three originally-named gates (source: repo read).
- Technical: `cover`/`toc`/`section` are already self-mapping rows in the outline
  叙事角色→page_type map, so modeling the new values as both narrative_role and
  page_type (self-map) is consistent, not novel (source: `outline-phase1-playbook.md:125-127`).
- Technical: `resource_loader.py:33-38` routes `page_type → page-templates/<stem>.md`;
  a missing template file is silently skipped, not an error (source: repo read).
- Technical: worksheet recipes load via `block_refs`, not as page-templates
  (source: `references/blocks/worksheet.md:5`).
- Technical: both new-type relaxations ("Part opens with `section`", "deck closes
  on `end`") are doc-only; `planning_validator.validate_cross_page` enforces
  neither (source: `scripts/planning_validator.py:572-613`).
- Technical: `check_skill.py:83-96` guards only the route *pattern*, not enum
  values (source: repo read).
- Technical: `validate_page` universal rules (≥1 card, single anchor,
  `director_command`, `decoration_hints`) fire on **every** page_type including
  the new ones — same as existing `cover`/`section`/`end` (source:
  `scripts/planning_validator.py:513-549`).
- Process: public-interface change → full mode; combined spec is sanctioned
  because `docs/backlog.md:80` states item 4 is "unblocked by the same spec" as
  item 1 (source: repo read).
- Product: consumers are reference-runbook deck authors; archetype is documented
  in `narrative-arc.md §参考型叙事` (source: repo read; PR #7).
- Design: back-matter is one `reference` page_type (RACI/gates/escalation/glossary
  selected within it), and `section-marker` is a divider-led content page, not a
  thin empty slide (source: user confirmation 2026-07-01).
- Design: both new values are modeled as **both** narrative_role and page_type
  (self-mapping like `cover`/`toc`/`section`), and both carry persistent
  header/footer chrome (matching the reference archetype), so they join the
  `("content","toc","section")` chrome set in the HTML-stage validators
  (source: user "go with your leans" 2026-07-01 + spec-mode review resolution).
