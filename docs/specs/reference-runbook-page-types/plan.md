# Plan: reference-runbook-page-types

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

The change is additive: two new `page_type` values threaded through the
planning public interface, plus two paste-ready page-template recipes and the
guidance prose that tells a downstream LLM when to use them.

The riskiest part is **enum drift** — the value-set is hardcoded in six consumer
sites (`planning_validator.py`, `contract_validator.py`, `visual_qa.py`,
`smoke_skill.py`, and the two playbooks; see spec Assumptions). Miss one and a
planning JSON using the new type validates in one stage and silently degrades in
another — notably `contract_validator.py`, a real gate that `smoke_test.py`
phase 1 does **not** run, so its `unrecognized page_type` warning would be
invisible. So the Python enum edits + their regression test lead (T1), and a
final join task (T7) re-runs the whole gate set including `smoke_skill.py`.

What keeps this bounded: the new types are **non-`content`** pages that behave
like `cover`/`section`/`end` — no `layout_hint` requirement, auto-barred from
`dashboard` density (the density rules already gate on `page_type == "content"`),
and routed by `page_type → page-templates/<stem>.md` through the unchanged
`resource_loader` route. They are **not** exempt from `validate_page`'s universal
rules, though: every page_type (the existing non-content ones included) must
carry ≥1 card, exactly one anchor card, `director_command`, and
`decoration_hints`. So the Python delta is the enum-set additions plus the
chrome/dashboard-set additions in `contract_validator`/`visual_qa`/`smoke_skill`;
everything else is markdown.

The new types are modeled as **both** `narrative_role` and `page_type`
(self-mapping like `cover`/`toc`/`section`) and carry persistent header/footer
chrome, so they join the `("content","toc","section")` chrome set in the
HTML-stage validators.

Doc tasks (T3–T5) touch disjoint files and can run in parallel; T1 (Python
validators) and T2 (page-templates) are independent; T6 (runtime QA consumers)
depends on T1+T2; T7 is the join.

## Constraints

- No ADR/RFC governs this; the spec's Boundaries are the binding constraints.
- `references/blocks/pipeline-compat.md` governs recipe HTML (real DOM, no SVG
  `<text>`, no forbidden CSS).
- `docs/CONVENTIONS.md:691` — public-interface change runs in full mode.
- Reuse worksheet recipes via `block_refs`; do not mint a new `card_type`
  (mirrors the `schematic-blueprint-runbook-restyle` boundary).

## Construction tests

**Integration tests:** the enum↔router↔template consistency is exercised in T6
via `smoke_skill.py`'s `PAGE_TEMPLATE_EXPECTATIONS`, which builds a page per
`page_type`, runs `planning_validator` (accepts), and asserts `resource_loader`
injects the matching `page-templates/*.md` body — a committed guard, not a
throwaway probe.

**Manual verification:** read the inline-vs-full-page guidance and the
archetype-gated end-relaxation in the outline + page-planning playbooks and
confirm they are unambiguous for a downstream LLM.

## Design (LLD)

Shape: `data` — the surface is an enum/schema value-set plus its documentation.

### Design decisions

- **Two page_types, not four.** RACI / quality-gates / escalation / glossary are
  selected *within* the `reference` page via `narrative_role` + worksheet
  `block_refs`, not as four page_types. Rejected the four-type shape: it explodes
  the enum and forces four page-templates for what is one back-matter concept.
  Traces to: AC1, AC5 · contracts/: none.
- **Both narrative_role and page_type (self-map).** Modeled exactly like
  `cover`/`toc`/`section`, which are already self-mapping rows in the outline
  map. Rejected "page_type only, map from existing roles": no existing role
  (`close`/`process`) cleanly means "back-matter reference" or "inline divider",
  and self-map rows are already the norm for structural pages. Keeps the two
  axes consistent across `planning_validator` and the outline closed enum.
  Traces to: AC2, AC4.
- **New types are non-`content` but chrome-bearing.** They route via
  `page_type → page-templates/` like cover/section/end (no `layout_hint`
  requirement, `dashboard`-barred). They are **not** exempt from `validate_page`'s
  universal rules (≥1 card, single anchor, `director_command`,
  `decoration_hints`) — same as existing non-content types. Because the reference
  archetype wants persistent orientation, they join the header/footer-required
  set (`("content","toc","section")`) in `contract_validator`/`visual_qa`/`smoke_skill`.
  Traces to: AC1, AC3, AC6.
- **Both relaxations are doc-only.** `validate_cross_page` enforces neither the
  Part-first-page `section` rule nor the deck-close `end` rule, so relaxing them
  for reference decks is a playbook-guidance edit, not a validator branch.
  Traces to: AC8, AC9.

### Data & schema

- `scripts/planning_validator.py`: `VALID_PAGE_TYPES` and `VALID_NARRATIVE_ROLES`
  each gain `"section-marker"`, `"reference"`. No other rule changes.
  Traces to: AC1, AC2 · contracts/: none.
- `scripts/contract_validator.py`: `NON_DASHBOARD_PAGE_TYPES` and the
  `validate_html` header/footer branch each gain the two values.
  `scripts/visual_qa.py` and `scripts/smoke_skill.py` header/footer sets match;
  `smoke_skill.PAGE_TEMPLATE_EXPECTATIONS` gains the two template titles.
  Traces to: AC3, AC7.
- Playbook enums (`outline-phase1-playbook.md`, `page-planning-playbook.md`):
  the human-facing mirror of the same value-set. Traces to: AC4, AC5.

### Interfaces & contracts

- The planning-JSON `page_type` field is the interface. Its six consumer sites
  are listed above; the `resource_loader` route
  (`FIELD_ROUTES["page_type"] == "page-templates"`) is **unchanged** and needs
  only the two new files to exist. Traces to: AC6, AC7.

## Tasks

### T1: Python validators accept the two new page_types (and unknowns still reject)

**Depends on:** none

**Touches:** scripts/planning_validator.py, scripts/contract_validator.py, scripts/test_reference_page_types.py

**Tests:** (TDD — write first, red → green). Build **complete** fixtures (anchor
card + `director_command` + `decoration_hints`) so structural rules don't mask
the check; assert on the `invalid page_type` / `unrecognized page_type`
**substring**, not `result.ok`.
- `validate_page` on a complete page with `page_type:"section-marker"` yields
  **no** `invalid page_type` error; same for `"reference"` (AC1).
- `validate_page` with `page_type:"bogus"` **still** yields `invalid page_type`
  (AC1 — guards against widening to "anything goes").
- a page with `narrative_role:"section-marker"` (and `"reference"`) yields **no**
  `unknown narrative_role` warning (AC2).
- `contract_validator.validate_html` on a chrome-bearing rendered page with each
  new type yields **no** `unrecognized page_type` warn and **does** require
  header+footer (AC3).
- Place the test at `scripts/test_reference_page_types.py`, runnable with
  `python3 scripts/test_reference_page_types.py` (stdlib `unittest`, matching the
  repo's script-test style).

**Approach:**
- `planning_validator.py`: add `"section-marker"`, `"reference"` to
  `VALID_PAGE_TYPES` (~L29) and `VALID_NARRATIVE_ROLES` (~L30). Confirm the
  `{cover,section,end}` / `== "content"` density gates need no change (they
  already do the right thing for non-content pages).
- `contract_validator.py`: add both to `NON_DASHBOARD_PAGE_TYPES` (~L42) and to
  the `validate_html` `("content","toc","section")` header/footer set (~L884), so
  the `elif ... unrecognized` branch (~L892) no longer fires.

**Done when:** `python3 scripts/test_reference_page_types.py` is green and the
bogus-value case still fails validation.

### T2: page-template recipes for `section-marker` and `reference` (AC6)

**Depends on:** none

**Touches:** references/page-templates/section-marker.md, references/page-templates/reference.md

**Tests:** (goal-based)
- Both files exist and, if they contain fenced recipe blocks, pass
  `python3 scripts/lint_diagram_recipes.py` conventions where applicable
  (pipeline-safe, no hardcoded non-whitelisted colors). Note: the linter targets
  `blocks/`, not `page-templates/`, so these are checked by the existing
  `page-templates/*.md` prose style (see `section.md`) + a manual pipeline-safety
  read.
- `resource_loader.extract_body` returns non-empty for both (so the router
  injects real content) — the durable resolution check lives in T6.

**Approach:**
- `section-marker.md`: model on `section.md`'s prose shape (title + blockquote
  menu line + guidance). Embed the paste-ready divider from
  `worksheet.md` §C cover-header/section-marker (the `§ NN` + mono kicker over a
  2px rule) plus the persistent `header.slide-header`/`footer.slide-footer`
  chrome, themed to deck CSS variables. State it is divider-led (chrome at
  top, section lead/first artifact below), distinct from full-page `section`.
- `reference.md`: prose page-template describing a back-matter page that hosts a
  worksheet artifact with persistent chrome; list the four roles → recipe map
  (RACI→responsibility-matrix, quality-gates→status-block,
  escalation→escalation-matrix, glossary→plain definition-list on the existing
  native `card_type:list` — **no new worksheet recipe**) and instruct
  `resources.block_refs:["worksheet"]`.
- Keep colors on deck CSS variables only (+ the whitelisted semantic-signal
  carve-out); real DOM only.

**Done when:** both files exist, are pipeline-safe on read, and T6's
`PAGE_TEMPLATE_EXPECTATIONS` resolution asserts their bodies are injected.

### T3: outline playbook — enum + map + skeleton relaxation

**Depends on:** none

**Touches:** references/playbooks/outline-phase1-playbook.md

**Tests:** (manual QA + goal-based)
- 页面类型映射 enum (lines ~95/116) **and** 叙事角色 enum (lines ~94/115) list
  `section-marker` and `reference` (AC4, AC2).
- 叙事角色→page_type map gains `section-marker`→`section-marker` and
  `reference`→`reference` self-map rows (consistent with the existing
  `cover`/`toc`/`section` self-maps) (AC4).
- The archetype note (line ~17) no longer says "不新增枚举"; the mandatory-skeleton
  rules (lines ~139-149) carry the reference-archetype relaxation of "Part 首页
  full-page section" → inline `section-marker` (AC8) and "last page = CTA/end" →
  may close on `reference` back-matter (AC9). Persuasive-deck rules unchanged.

**Approach:**
- Edit the two enum blocks (页面类型映射 + 叙事角色, at both the template ~L94/95
  and the constraint ~L115/116), add two self-map rows with a one-line 说明 each,
  add a guidance sentence on inline `section-marker` vs full-page `section`, and
  gate both skeleton relaxations on the reference archetype.

**Done when:** a human read confirms both new values appear in every enum/map and
both relaxations are archetype-gated; `check_skill.py` stays green.

### T4: page-planning playbook — enum + inline-vs-full + back-matter roles

**Depends on:** none

**Touches:** references/playbooks/step4/page-planning-playbook.md

**Tests:** (manual QA + goal-based)
- page_type enum (lines ~111/207) lists `section-marker` and `reference` (AC5).
- narrative_role guidance (lines ~13/208) mentions the two new roles (AC5).
- New guidance paragraph: when to pick inline `section-marker` vs full-page
  `section`; the back-matter role→worksheet `block_refs` map, glossary via
  native `card_type:list` (AC5).
- `check_skill.check_planning_example` still passes (no required schema field
  removed) — run `python3 scripts/check_skill.py`.

**Approach:**
- Edit the two enum occurrences, extend the narrative_role lists, add the
  inline-vs-full-page + back-matter-roles guidance keyed to the reference archetype.

**Done when:** enums list both values, guidance is present, `check_skill.py` green.

### T5: reconcile self-contradicting prose (narrative-arc + SKILL + README)

**Depends on:** none

**Touches:** references/principles/narrative-arc.md, SKILL.md, references/README.md

**Tests:** (goal-based)
- `narrative-arc.md` §参考型叙事 no longer asserts "不新增枚举"; it points at the
  `section-marker` / `reference` page_types (AC10).
- `SKILL.md` page_type value-list (line ~346) and page-template count (line ~375,
  `4 个页面模板` → `6`) reflect the two new values / templates;
  `references/README.md` (lines ~16/92) likewise (AC11).
- `python3 scripts/check_skill.py` green (the `page_type→page-templates/` route
  pattern is untouched; only value/count prose changes).

**Approach:**
- Update narrative-arc.md lines ~85/88 (章节用 section-marker; the 不新增枚举
  clause) and the outline-playbook cross-reference to state the enums now exist.
- Update SKILL.md + README page_type value list and the "4 个页面模板" count → 6.

**Done when:** no doc still claims "不新增枚举"; counts/lists match reality;
`check_skill.py` green.

### T6: runtime QA consumers — visual_qa + smoke_skill

**Depends on:** T1, T2

**Touches:** scripts/visual_qa.py, scripts/smoke_skill.py

**Tests:** (goal-based)
- `scripts/visual_qa.py` header/footer set (~L457) includes both new types so a
  `section-marker`/`reference` page is checked for chrome, matching the
  `contract_validator` decision in T1 (AC3).
- `scripts/smoke_skill.py`: `PAGE_TEMPLATE_EXPECTATIONS` (~L45) gains both types
  with their expected page-template titles; `build_html` header/footer set (~L434)
  includes them so smoke-built HTML carries chrome (AC7, AC3).
- `python3 scripts/smoke_skill.py` → the `planning-validator-<type>` and
  `resource-loader-resolve-<type>` assertions pass for both new types (durable
  router-resolution coverage — replaces a throwaway probe) (AC7).

**Approach:**
- Add the two values to the `{"content","toc","section"}` header/footer sets in
  `visual_qa.py` and `smoke_skill.py`; add the two `PAGE_TEMPLATE_EXPECTATIONS`
  entries keyed to the titles authored in T2's page-templates.

**Done when:** `python3 scripts/smoke_skill.py` is green with both new types
exercised through validate + resolve.

### T7: gate join

**Depends on:** T1, T2, T3, T4, T5, T6

**Touches:** (none — verification only)

**Tests:** (goal-based / integration)
- `python3 scripts/smoke_test.py` → 0 fail; `python3 scripts/lint_diagram_recipes.py`
  → OK; `python3 scripts/check_skill.py` → 0 errors; `python3 scripts/smoke_skill.py`
  → 0 fail (AC12).

**Approach:**
- Run the full gate set after all edits are merged into the working tree.

**Done when:** all four gates green.

## Rollout

Pure additive doc + enum change; no infra, no migration, no flag. Reversible by
reverting the PR. No deployment sequencing — the enum values and the
page-templates ship in the same commit, and nothing consumes them until an author
opts into the reference archetype.

## Risks

- **Enum drift** — a value added in some but not all six consumer sites, e.g.
  the easy-to-miss `contract_validator.py` (a gate `smoke_test` doesn't run).
  Mitigated by T1 covering both Python validators with a regression test, T6
  covering the runtime QA consumers, and T7 re-running the full gate set
  including `smoke_skill.py`.
- **Doc self-contradiction** — leaving a "不新增枚举" claim stale would poison a
  downstream LLM. Mitigated by T5 explicitly hunting those clauses.
- **Over-reach** — an implementer minting a glossary recipe or a third page_type.
  Mitigated by the spec's *Ask first* / *Never do* boundaries.

## Changelog

- 2026-07-01: initial plan.
- 2026-07-01: after spec-mode adversarial review — corrected "three enum sites"
  to six (added `contract_validator.py`, `visual_qa.py`, `smoke_skill.py`);
  split T1 to cover both Python validators; added T6 for the runtime QA
  consumers; made router-resolution coverage durable via `smoke_skill`'s
  `PAGE_TEMPLATE_EXPECTATIONS` (was a throwaway probe); modeled the new values as
  both narrative_role and page_type (self-map) with chrome; fixed T1 fixtures to
  be complete pages asserting on the `invalid page_type` substring.
