# Plan: reference-runbook narrative archetype in the outline engine

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

The change is additive and gated on a single signal. A deck author writes
`论证策略：reference_runbook` on a Part in `outline.txt`; the outline validator
derives a deck-level "reference archetype" flag from that and, when set, skips the
one persuasive-only rule the guidance names — the "no 3 consecutive high/dashboard"
density streak. The archetype is carried forward into the planning phase as an
optional per-page `narrative_archetype` field so the planning validator's parallel
streak rule branches the same way. Everything else — enum validation of `论证策略`,
density windows, dashboard sandwiching, the cover/toc/end skeleton — is untouched,
and the absence of the signal reproduces today's behavior byte-for-byte.

The riskiest part is regression: two validators enforce the streak rule, and a
sloppy branch could silently weaken it for persuasive decks. The defense is a pair
of expected-pass / expected-fail `smoke_skill.py` fixtures per validator — the same
page shape passes under reference and fails under persuasive — so the gate proves
both the relaxation *and* its gating in one move. Work order: outline validator +
its fixtures (T1), planning validator + its fixtures (T2), then reconcile the four
docs to the field names the code settled (T3).

## Constraints

- No ADR/RFC governs this. It is the engine follow-through on the guidance in
  `references/principles/narrative-arc.md §参考型叙事` (shipped PR #7) and is tracked
  as the second item of `docs/backlog.md § schematic-blueprint-runbook-restyle`.
- The `section-marker` page_type, `persistent_chrome` deck flag, and back-matter
  reference page_types are *sibling* deferred items in the same backlog section and
  are explicitly out of scope here.

## Construction tests

Per-task `smoke_skill.py` cases carry the bulk (see Tasks). Cross-cutting:

**Integration tests:** the planning-validator branch (T2) is exercised at the
multi-page-directory level (`planning_validator <dir>`), since the streak rule is a
cross-page check — a single-page fixture cannot express a 3-page streak.

**Manual verification:** run the three named gates + `smoke_skill.py`; confirm the
new reference cases pass, the paired persuasive cases still fail as expected, and no
previously-green subtest regresses.

## Design (LLD)

### Design decisions

- **Archetype signal = `论证策略：reference_runbook` on any Part** (outline), not a
  separate deck-level header field. Traces to: AC1, AC2 · rejected alt: a new
  `叙事原型` header — more surface, and the task frames the signal as a value of the
  existing per-Part `论证策略` enum. A deck is reference-archetype iff ≥1 Part uses it.
- **Planning carries archetype per-page, not on a deck wrapper.** Production splits
  planning into per-slide `planning*.json` files (`load_planning_pages`), so a
  wrapper-only field would not survive the split; each page self-declares
  `narrative_archetype`, defaulting to `persuasive`. Traces to: AC3.
- **Relax only the streak rule.** `narrative-arc.md §76` lifts only "禁止连续 3 页
  high"; dashboard sandwiching, density windows, single-focus, and skeleton stay
  enforced under both archetypes. Traces to: AC5.
- **Validate the enum when present, do not newly require it.** Outlines that omit
  `论证策略` (today's norm) keep validating. Traces to: AC1 · Boundaries "Ask first".

### Interfaces & contracts

- **Outline text contract** (`contract_validator.py` `validate_outline`): gains
  Part-block parsing to read `论证策略`; `VALID_ARGUMENT_STRATEGIES` enum set;
  reference-archetype detection; streak-rule branch. No formal `contracts/` file —
  the contract is the validator + `outline-phase1-playbook.md`.
- **Planning JSON contract** (`planning_validator.py`): optional per-page
  `narrative_archetype` ∈ {`persuasive`, `reference_runbook`}; validated when
  present; drives the `validate_cross_page` streak branch. Emission is instructed by
  `page-planning-playbook.md` (T3) — the field is derived from the outline `论证策略`,
  shown in the schema skeleton, and copied by the planning subagent. `check_skill.py`'s
  required-field list is unchanged (the field is optional, so it is not added to
  `required_field_names`).

### Behavior & rules

- `validate_outline`: parse `## Part N` blocks → collect `论证策略` per Part →
  `is_reference = any(v == "reference_runbook")`. For each declared value not in
  `VALID_ARGUMENT_STRATEGIES`, emit an error. When `is_reference`, do not emit the
  `禁止连续 3 页 high/dashboard` error (still compute the streak so other logic is
  unaffected). Persuasive path unchanged.
- `validate_cross_page`: read per-page `narrative_archetype`, validate values,
  `is_reference = any(page archetype == "reference_runbook")`; when reference, skip
  the 3-consecutive-`{high,dashboard}` error. Dashboard-sandwiching stays.

## Tasks

### T1: Outline validator honors the reference archetype

**Depends on:** none
**Touches:** scripts/contract_validator.py, scripts/smoke_skill.py

**Tests:** (new `smoke_skill.py` cases, run against `contract_validator.py outline`)
- Reference fixture: an outline whose Part declares `论证策略：reference_runbook` with
  ≥3 consecutive `密度目标：high` content pages → `run_cmd` expects `OK` (red before
  the branch, green after). Verifies AC2.
- Persuasive control: the same page shape with a non-reference `论证策略` (e.g.
  `data_driven`) → `run_cmd_expect_failure` expecting `禁止连续 3 页` → proves
  non-regression. Verifies AC2 + AC5.
- Enum (reject): an outline Part with `论证策略：not_a_strategy` →
  `run_cmd_expect_failure` asserting the specific unknown-`论证策略` error token (not just
  a nonzero exit). Verifies AC1.
- Enum (accept, full set): a loop that runs the validator once per value in the
  8-member `VALID_ARGUMENT_STRATEGIES` set (the 7 existing + `reference_runbook`),
  each `run_cmd` expecting `OK` — so a mistyped entry in the set is caught. Verifies AC1.

**Approach:**
- Add `VALID_ARGUMENT_STRATEGIES = {narrative_driven, data_driven, case_study,
  comparison, framework, step_by_step, authority, reference_runbook}`.
- Add a `parse_outline_parts(text)` (or inline regex on `^##\s*Part`) to extract each
  Part's `论证策略` via the existing `extract_named_field`.
- In `validate_outline`: validate each present strategy against the set (error on
  unknown); set `is_reference`; guard the `high_pressure_streak >= 3` error
  (`contract_validator.py:422-423`) behind `not is_reference`.
- Add the three fixture cases to `smoke_skill.py` `run_smoke()` near the existing
  `contract-validator-outline*` block, with a `build_reference_outline_fixture` helper.

**Done when:** the three new `smoke_skill.py` cases pass, existing
`contract-validator-outline*` cases stay green, and `contract_validator.py outline`
on a reference fixture prints `OK`.

### T2: Planning validator honors the reference archetype

**Depends on:** none
**Touches:** scripts/planning_validator.py, scripts/smoke_skill.py

**Tests:** (new `smoke_skill.py` cases against `planning_validator.py <dir>`)
- Reference: a 3-page planning dir, each page `density_label: high` +
  `narrative_archetype: reference_runbook` → `run_cmd` expects `OK`. Verifies AC3.
- Persuasive control: the same 3 pages without `narrative_archetype` →
  `run_cmd_expect_failure` with `expected_tokens=["3 consecutive slides"]`. Proves
  non-regression. Verifies AC3 + AC5.
- Enum: a page with `narrative_archetype: bogus` → `run_cmd_expect_failure` with
  `expected_tokens=["narrative_archetype"]`, so the case fails for the *right* reason
  (the archetype-enum error, not an incidental malformed-fixture error). Verifies AC3.

**Approach:**
- Add `VALID_NARRATIVE_ARCHETYPES = {"persuasive", "reference_runbook"}`.
- In `validate_page` (or a small helper), when `narrative_archetype` is present and not
  in the set, emit an error; absent → treated as `persuasive`.
- In `validate_cross_page`: compute `is_reference = any(page.get("narrative_archetype")
  == "reference_runbook")`; guard the `high_pressure_streak >= 3` error
  (`planning_validator.py:600-601`) behind `not is_reference`. Leave the
  dashboard-transition check intact.
- Extend `build_content_page_fixture` (or add a helper) in `smoke_skill.py` to emit the
  3-page reference/persuasive dirs and register the cases.

**Done when:** the new `smoke_skill.py` planning cases pass, existing
`planning-validator*` cases stay green.

### T3: Docs state both archetype branches consistently

**Depends on:** T1, T2
**Touches:** references/playbooks/outline-phase1-playbook.md, references/playbooks/outline-phase2-playbook.md, references/principles/narrative-arc.md, references/playbooks/step4/page-planning-playbook.md, references/prompts/step4/tpl-page-planning.md

**Tests:** goal-based — a `grep` confirming each of:
- `outline-phase1-playbook.md` lists `reference_runbook` in both enum spots (~L27, L89);
  its `演示骨架强制规则` names the reference branch; **and its violation-detection bullet
  (`任何 Part 的首页不是 section = 结构缺陷`, ~L149) is made archetype-aware** so the file
  does not assert the rule as unconditional *and* relax it (Blocker 1 fix).
- `outline-phase2-playbook.md §密度专项铁律` states the streak rule is relaxed for
  reference decks.
- `narrative-arc.md` references the `reference_runbook` value + both validators.
- `page-planning-playbook.md` (a) instructs emission of `narrative_archetype` derived
  from the outline `论证策略`, and (b) shows `"narrative_archetype"` in its JSON schema
  skeleton (~L112 region).
- `tpl-page-planning.md` read-scope step (~L58) tells the PageAgent to also read its
  **owning `## Part N` header's `论证策略`** (not only its own page block), closing the
  read-scope gap that would otherwise leave the field unemittable.

Verifies AC1, AC4, AC6, AC7.

**Approach:**
- `outline-phase1-playbook.md`: add `reference_runbook` to the `论证策略` enum on the
  step-4 methodology line (~L27) and the skeleton field enum (~L89); in
  `演示骨架强制规则` (~L135-150) add an archetype note — reference decks relax the
  Part-opening full-page `section` (→ inline section-marker guidance) and the streak
  rule; persuasive unchanged. **Edit the violation-detection bullet at ~L149 to condition
  the "首页必须是 section" defect on the persuasive archetype** (reference Parts open with
  an inline section-marker instead), so the rule and its relaxation are stated together.
- `outline-phase2-playbook.md §密度专项铁律` (~L34-40): make the "禁止连续 3 页
  high/dashboard" bullet archetype-aware (persuasive enforces; reference relaxes,
  rhythm from artifact-shape alternation).
- `narrative-arc.md §参考型叙事`: tighten to name the `论证策略：reference_runbook` enum
  value and that both `contract_validator` and `planning_validator` honor it.
- `page-planning-playbook.md`: **instruct** the planning subagent to set
  `narrative_archetype` on every page — read the owning Part's `论证策略` from
  `{{OUTLINE_PATH}}`, map `reference_runbook → reference_runbook`, else `persuasive` — and
  add `"narrative_archetype": "<persuasive | reference_runbook>"` to the JSON schema
  skeleton (~L112 region). This field is *optional* (absent → persuasive), so it is
  **not** added to `check_skill.py`'s `required_field_names`; adding it to the skeleton is
  additive and does not trip `check_planning_example`.
- `tpl-page-planning.md` (~L58): widen the "只关注你这一页" outline-read step so the
  PageAgent also reads the `## Part N` header owning its page and extracts `论证策略`
  (the field lives in the Part block, not the page block). No new `{{VAR}}` placeholder is
  introduced (the outline is already `{{OUTLINE_PATH}}`), so `check_prompt_harness_coverage`
  is unaffected; the text adds no Step-4 legacy alias.

**Done when:** `check_skill.py` stays green and every goal-based grep above matches.

## Rollout

Pure-logic + docs change. No flag, no infra, no external systems, no migration; fully
reversible by revert. Deployment sequencing is intra-PR only: the docs (T3) name the
field values the validators (T1/T2) settle, so T3 lands after them in the same PR.

## Risks

- **Silent persuasive regression** — the streak branch weakens the rule for all decks
  if the gate is wrong. Mitigated by the paired persuasive expected-fail fixtures in
  T1/T2 (same shape must still fail).
- **smoke_skill.py merge overlap** — T1 and T2 both edit `smoke_skill.py`; done serially
  (single author), so no live conflict, but noted for any parallel dispatch.
- **Archetype not reaching planning** — if the pipeline never writes `narrative_archetype`
  into planning JSON, the planning branch is inert (the validator would only *accept* a
  hand-added tag). Mitigated in T3 by making `page-planning-playbook.md` **instruct**
  emission of the field (derived from the outline `论证策略`) and adding it to the schema
  skeleton the subagent copies — this markdown-first pipeline has no separate
  planning-generation code, so the playbook edit *is* the wiring. The validator still
  defaults to persuasive, so a missing tag is safe (validated as persuasive), not wrong.

## Changelog

- 2026-07-01: initial plan.
- 2026-07-01: applied post-implementation review findings — tightened the enum-reject
  test token to `invalid 论证策略`, iterate `VALID_ARGUMENT_STRATEGIES` in the enum-accept
  loop (so a new strategy is covered automatically), documented the intentional
  outline-lenient / planning-strict archetype-normalization asymmetry, and added a
  `chart_free` TODO. Spec ACs checked, Status → Shipped.
