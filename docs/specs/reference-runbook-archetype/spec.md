# Spec: reference-runbook narrative archetype in the outline engine

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Contract:** none <!-- the outline-text and planning-JSON contracts are enforced by validators + documented in playbooks; no formal contracts/<type>/ file exists for them -->
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The planning phase supports two narrative archetypes, not one. The **persuasive**
archetype (pyramid / SCQA / story-arc, climax-then-breath density rhythm) is the
default and behaves exactly as it always has. The **reference-runbook** archetype
serves decks that are *used, not read once* — runbooks, delivery handbooks, SOPs,
playbooks — where the spine is a lifecycle timeline and every page is a dense,
look-up-able operating artifact (template / checklist / schedule / responsibility
matrix / quality gate). A deck author selects it by writing `论证策略：reference_runbook`
on a Part in `outline.txt`; from that point the outline and planning validators
stop imposing the persuasive arc's density rhythm on the deck, while every other
structural rule (single-focus page goals, density windows, dashboard sandwiching,
cover/toc/end skeleton) continues to hold. The success outcome: a uniformly-dense
reference outline (and the planning packet derived from it) validates clean instead
of being rejected by the persuasive-only "no 3 consecutive high-density pages" rule,
and no persuasive deck changes behavior. This is the engine-level follow-through on
the guidance shipped in `principles/narrative-arc.md §参考型叙事` (PR #7); see
`docs/backlog.md § schematic-blueprint-runbook-restyle` (second item).

## Boundaries

### Always do

- Treat `persuasive` as the implicit default: an outline with no `reference_runbook`
  Part, and a planning packet with no `narrative_archetype` field, validate exactly
  as they do today (byte-for-byte identical error sets).
- Keep the archetype signal single-sourced: the deck is reference-archetype **iff**
  at least one Part declares `论证策略：reference_runbook`; the planning packet carries
  the resolved archetype forward per page so the planning validator agrees with the
  outline validator.
- Keep `narrative-arc.md`, `outline-phase1-playbook.md`, `outline-phase2-playbook.md`,
  and `page-planning-playbook.md` in agreement on the archetype rules — a doc that
  restates a branched rule states both branches.

### Ask first

- Relaxing any rule beyond the two the guidance names (the Part-opening full-page
  `section` rule and the "no 3 consecutive high/dashboard" streak rule). The dashboard
  sandwiching rule, density windows, single-focus page goal, and cover/toc/end skeleton
  are **not** relaxed without sign-off.
- Making `论证策略` a newly *required* outline field (today it is optional and
  guidance-only).

### Never do

- No new top-level dependency, and no new module or script — the change lives inside
  the two existing validators (`contract_validator.py`, `planning_validator.py`), the
  four existing docs, and the existing `smoke_skill.py` fixtures.
- Never mint a `section-marker` page_type or any new `page_type` / `card_type` enum
  value — reference decks map to the existing `section` / `content` / `end` page_types
  (the `section-marker` page_type is a separate deferred backlog item).
- Never let the archetype branch weaken a rule for *persuasive* decks — the relaxation
  is gated on the reference-archetype signal and is invisible to every existing deck.

## Testing Strategy

- **Enum validation** (`论证策略` accepts `reference_runbook`, rejects typos):
  TDD — a compressible invariant, exercised as a `contract_validator outline` case in
  `smoke_skill.py` (an outline with an unknown strategy fails; one with `reference_runbook`
  passes).
- **Outline density-streak branch** (reference outline with ≥3 consecutive high pages
  validates clean; the same shape under persuasive is rejected): TDD — two
  `smoke_skill.py` outline fixtures, one expected-pass (`run_cmd`) and one
  expected-fail (`run_cmd_expect_failure`), proving both the branch and non-regression.
- **Planning density-streak branch** (planning packet tagged `narrative_archetype:
  reference_runbook` with ≥3 consecutive high pages validates clean; untagged packet is
  rejected): TDD — mirror the above against `planning_validator`, exercised as an
  integration-level `smoke_skill.py` case (multi-page planning dir).
- **Doc agreement** (the four docs state the branched rules consistently): goal-based —
  a `grep`/read confirming each doc names the `reference_runbook` value and both branches
  of each rule it restates.
- **Gate non-regression**: goal-based — `smoke_test.py`, `lint_diagram_recipes.py`,
  `check_skill.py` stay green; `smoke_skill.py`'s `contract-validator-outline*` and
  `planning-validator*` subtests stay green (its pre-existing, unrelated
  `runtime-style-rules.md` / resource-loader failures are out of scope).

## Acceptance Criteria

- [x] `reference_runbook` is a valid `论证策略`: `outline-phase1-playbook.md` lists it in
  the enum (both the step-4 methodology line and the skeleton field enum), and
  `contract_validator.py` validates `论证策略` against a set that includes it — an unknown
  value errors, `reference_runbook` and the seven existing values pass.
- [x] `contract_validator.validate_outline` detects the reference archetype from
  `论证策略：reference_runbook` on any Part and, when detected, does **not** raise the
  "禁止连续 3 页 high/dashboard" error; a persuasive outline of the same page shape still
  raises it.
- [x] `planning_validator` reads an optional per-page `narrative_archetype`
  (`persuasive` | `reference_runbook`, default `persuasive`), validates it when present
  (an unknown value raises a `narrative_archetype`-named error), and when the deck is
  reference-archetype does **not** raise the "3 consecutive slides with density_label in
  {high, dashboard}" error; an untagged (persuasive) packet of the same shape still
  raises it.
- [x] `page-planning-playbook.md` **instructs the planning subagent to emit**
  `narrative_archetype` on every page, derived from the outline's `论证策略`
  (`reference_runbook` → `reference_runbook`, else `persuasive`), and shows the field in
  its JSON schema skeleton — so a reference outline's planning packet is actually tagged
  in production, not merely accepted if hand-tagged. Because the per-page planning prompt
  (`tpl-page-planning.md`) today scopes the PageAgent's outline read to *its own page
  block* ("只关注你这一页") while `论证策略` lives in the `## Part N` header, that prompt's
  read-scope step is widened so the PageAgent also reads its **owning Part's** `论证策略`.
  This is the end-to-end wiring: the planning prompt injects this playbook
  (`{{PLAYBOOK}}`) and reads the outline (`{{OUTLINE_PATH}}`).
- [x] The dashboard-sandwiching rule, density-window (`下限 ≤ 目标 ≤ 上限`), single-focus
  page goal, and cover/toc/end skeleton rules remain enforced under **both** archetypes.
- [x] `narrative-arc.md §参考型叙事`, `outline-phase1-playbook.md §演示骨架强制规则`, and
  `outline-phase2-playbook.md §密度专项铁律` agree: each names `reference_runbook` and
  states both branches (persuasive keeps the streak/section rules; reference relaxes
  them, rhythm coming from artifact-shape alternation).
- [x] The "every Part opens with a full-page `section`" guidance is relaxed to inline
  section-marker for reference decks in the playbook + narrative-arc docs only (no
  validator enforces this rule today, so no validator changes for this half).
  Specifically, the `outline-phase1-playbook.md §演示骨架强制规则` violation-detection
  bullet ("任何 Part 的首页不是 section = 结构缺陷") is made archetype-aware, so the file
  does not simultaneously assert the rule as an unconditional defect *and* its relaxation
  — the two statements are connected in the same section.
- [x] Gates pass: `smoke_test.py`, `lint_diagram_recipes.py`, `check_skill.py` green;
  new `smoke_skill.py` reference-archetype cases (outline + planning, expected-pass and
  expected-fail) pass, and all previously-green `smoke_skill.py` subtests stay green.

## Assumptions

- Technical: `论证策略` is guidance-only today — no validator parses it; only the
  `build_outline_fixture` helper in `smoke_skill.py` emits it as a fixture string
  (source: `scripts/contract_validator.py` `parse_outline_pages`).
- Technical: the "no 3 consecutive high/dashboard" rule is enforced in two places —
  the `high_pressure_streak >= 3` error in `contract_validator.validate_outline` (outline)
  and in `planning_validator.validate_cross_page` (planning) (source: repo read).
- Technical: the "every Part opens with a full-page `section`" rule is documented but
  not enforced in any validator (source: `outline-phase1-playbook.md:143,149`;
  `contract_validator.validate_outline` parses pages only, not Parts).
- Technical: the outline prompt injects the playbook via `{{PLAYBOOK}}`, so playbook
  edits reach "Prompt 1" with no separate prompt edit (source:
  `references/prompts/tpl-outline-phase1.md:29`).
- Technical: no `section-marker` page_type exists; it is a separate deferred item and
  reference decks map to the existing `section` page_type (source: `docs/backlog.md:66-68`;
  `narrative-arc.md:88`).
- Technical: there is no pytest harness; validator behavior is tested via `smoke_skill.py`
  `run_cmd` / `run_cmd_expect_failure` cases (source: `scripts/test_diagram_qa.py:5`; no
  `pyproject.toml`).
- Process: gates are `smoke_test.py`, `lint_diagram_recipes.py`, `check_skill.py`, all
  green at baseline; `smoke_skill.py` has pre-existing unrelated failures (missing
  `references/styles/runtime-style-rules.md`; one resource-loader snapshot) whose
  `contract-validator-outline*` / `planning-validator*` subtests pass (source: baseline
  gate run).
- Process: this crosses the planning public interface → full-mode spec (source:
  `docs/backlog.md § schematic-blueprint-runbook-restyle`; task brief).
- Product: the four design decisions take the higher-integrity option — key archetype off
  `论证策略`, branch both validators for end-to-end correctness, machine-enforce the enum,
  keep the section-opening relaxation docs-only (source: user confirmation 2026-07-01).
