# Plan: consulting-grade deck contract

- **Spec:** [`spec.md`](spec.md)
- **Status:** Draft

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document may change as implementation teaches us more. Substantive changes are
> recorded in the changelog.

## Approach

Implement the contract at the earliest stage that still has the information
needed to make the decision:

1. Decide title applicability and repair title wording in the outline, where
   `叙事范式`, discovery-readout signals, `page_goal`, and page titles coexist.
2. Preserve the approved title through planning and HTML rather than deriving a
   second title downstream.
3. Preserve `source_guidance.strictness`, add warning-only per-point evidence
   checks, and use requirements-level `grounding_mode` during Evidence review.
4. Make the existing Story → Evidence → Design reviews explicit, keeping the
   evidence pass before the Review/Render choice.
5. Lock the distributed contract with `check_skill.py` and focused validator
   tests, then run the normal skill gates.

This is a public skill-contract and dependent multi-file change, so execution
uses the work-loop's full mode. The changes remain reversible; there is no data
migration, dependency, renderer modification, or deployment action.

## PLAN trio

### Files expected to change

- `SKILL.md`
- `references/principles/narrative-arc.md`
- `references/playbooks/outline-phase1-playbook.md`
- `references/playbooks/outline-phase2-playbook.md`
- `references/playbooks/step4/page-planning-playbook.md`
- `references/playbooks/step4/page-html-playbook.md`
- `references/playbooks/step4/page-review-playbook.md`
- `references/prompts.md`
- `references/prompts/step4/tpl-page-orchestrator.md`
- `references/prompts/step4/tpl-page-planning.md`
- `references/prompts/step4/tpl-page-html.md`
- `references/prompts/step4/tpl-page-review.md`
- `scripts/planning_validator.py`
- `tools/check_skill.py`
- `tests/test_planning_evidence_warnings.py` (new focused test file)
- `tools/smoke_skill.py` only if its generated fixtures otherwise create
  unintended evidence-warning noise
- `docs/specs/consulting-grade-deck-contract/{spec,plan}.md`
- `docs/specs/README.md`

### Tests

- Goal-based title-matrix and preservation checks while authoring T1/T2.
- `pytest tests/test_planning_evidence_warnings.py -q`
- `python tools/check_skill.py`
- `python tools/smoke_skill.py`
- `pytest tests/`
- `python tools/pii_lint.py --paths-from-stdin` against the changed-file list if
  that invocation is supported; otherwise the repository's documented PII lint
  mode over the worktree diff.

### Explicitly not changing

- Accepted RFC bodies or adding a new RFC.
- `scripts/html_packager.py`, preview HTML behavior, or `docs/product/DESIGN.md`.
- Planning schema fields, workflow-version constants, or
  `VALID_NARRATIVE_ARCHETYPES`.
- Page-type, narrative-role, card-type, or chart-type enums.
- Proof-gate choices, proof worksheet output, or PageAgent stage count.
- Styles, visual templates, gallery inventory, dependencies, or top-level dirs.

## Constraints

- RFC-0001 remains the authority for seven-value narrative routing; RFC-0002
  remains the authority for audience/consumption-mode checks.
- The discovery-readout route stays guidance-only. Do not create a validator
  enum merely to detect it downstream.
- Planning `narrative_archetype` remains the existing density signal
  (`persuasive | reference_runbook`), not a synonym for `叙事范式`.
- Existing planning files must still validate successfully. New evidence
  findings are WARN only.
- `page_goal` remains present and meaningful after title reuse; it is not deleted
  or replaced by `title`.
- `source_guidance.strictness` keeps its current evidence-boundary semantics;
  it is not repurposed as a grounding-mode enum.
- Skill and reference edits follow the existing agentskills/progressive-
  disclosure conventions; do not add a new reference file when the selector
  already has an appropriate home.

## Construction tests

### Title contract

- All five applicable routes are named: pyramid, hybrid, sparkline, status, and
  discovery-readout.
- All three explicit exemptions are named: reference, facilitation,
  informational; navigation-page exemptions are also present.
- Phase 2 says to read actual outline page titles alongside `page_goal`; it no
  longer describes a page-goal-only proxy as the title sequence.
- Planning instructions say `title` is copied verbatim from the approved outline
  page title and `page_goal` remains separate.
- HTML instructions say content/TOC `h1.page-title` and the primary visible
  heading on free-layout pages equal planning `title`; browser title may add
  only the existing mechanical slide-number prefix.
- Stage 3 compares normalized rendered heading/`<title>` text to planning
  `title` before FINALIZE.
- `rg -n "action_title" SKILL.md references scripts tools tests` has no new schema
  field declaration (descriptive declined-pattern mentions are allowed).

### Evidence warnings

Focused tests cover this matrix:

| Entry/value | Source | Expected |
| --- | --- | --- |
| non-object entry | n/a | EVID-DATA-01 WARN |
| object value `42`, `"42%"`, `"$2.4M"`, or `"3 hours"` | empty/non-string | EVID-SRC-01 WARN |
| same measurement values | real source | no evidence-source warning |
| same measurement values | closed illustrative sentinel | no evidence-source warning |
| object value `Q3`, `Phase 2`, `ID-42`, `TG-A`, or boolean | empty | no EVID-SRC-01 warning |
| absent/empty `data_points` | n/a | no evidence-source warning |

Each test also asserts zero new ERRORs. A golden valid page remains `result.ok`.

### Cross-contract checks

`tools/check_skill.py` verifies stable anchors for:

- applicable title routes and exemptions in narrative/outline guidance;
- outline-title → planning-title → HTML-title preservation;
- EVID-DATA-01 and EVID-SRC-01 in validator and planning guidance;
- the ordered Story, Evidence, and Design passes in `SKILL.md`;
- every functional-template inventory route using only existing enum tokens;
- PageAgent's planning handoff is validation-only after Evidence review.

## Design (LLD)

### Title flow

```text
outline page heading ──copy──> planning.title ──render──> primary heading
          │                                      └──────> browser title
          └──proposition-equivalent── page_goal (applicable routes only)
```

- Phase 1 authors route-appropriate titles.
- Phase 2 repairs topic labels and epistemic overstatement while both title and
  `page_goal` are available.
- Step 4 copies; it does not reinterpret.
- HTML consumes; it does not rewrite.

"Equivalent" permits a shorter title but not a weaker or different proposition.
For example, a goal that says a delayed dependency requires a steering decision
may shorten to "The dependency delay now requires a steering decision"; it may
not become "Dependency status".

### Evidence-warning helpers

Keep the code local to `planning_validator.py` until a second caller exists:

- A private predicate identifies a measurement value: real `int`/`float`
  (excluding booleans), or a trimmed string matching optional comparison/sign,
  optional currency, grouped/decimal digits, and optional magnitude/percent/unit.
  The closed grammar must reject quarter/phase/identifier labels in the test
  matrix rather than treating any digit as a measurement.
- A private normalizer recognizes exactly `Illustrative — unverified` and
  `示意稿·未经核实`, allowing square brackets, case-folding English, and normalizing
  Unicode dash/whitespace variants.
- `validate_card` emits EVID-DATA-01 for each non-dict data point. For dict
  points, it emits EVID-SRC-01 only when the value is a measurement and `source`
  is not a non-empty string. Warnings include page/card/data-point location.
- The validator does not infer grounding mode. The agent Evidence pass reads
  the validated requirements mode and rejects illustrative sentinels in G1/G2
  or unmarked invented numbers in G3.

### Three-pass placement

- **Story:** existing Step 3 Phase 2 outline self-review.
- **Evidence:** Step 4.5 pre-consent internal review, after the all-pages planning
  wave and before either proof decision is written.
- **Design:** existing Step 5c PageAgent Stage 3 and deck-level visual gate.

The Review-first branch may additionally show the proof worksheet. The
render-direct branch omits that user-facing artifact but enters Step 5 only after
the same internal evidence review. During Step 5, PageAgent Stage 1 validates and
hands off existing planning without rewriting it. Any planning rollback ends the
render attempt and returns through Evidence review.

### Functional inventory placement

Add one compact selector table in `page-planning-playbook.md` beside the current
page-type/resource-routing guidance. Cross-link existing principles rather than
copying recipes. The table is a map, not a new component catalogue.

## Tasks

### T1: Author and gate route-specific title reuse

**Depends on:** none

**Touches:**

- `references/principles/narrative-arc.md`
- `references/playbooks/outline-phase1-playbook.md`
- `references/playbooks/outline-phase2-playbook.md`
- the outline portion of `references/prompts.md`

**Approach:**

1. Add a compact title-behavior column/section to the narrative routing guidance,
   including the discovery-readout epistemic variants and explicit exemptions.
2. Change the Phase 1 page-title convention so applicable page headings carry
   the `page_goal` proposition; retain both fields.
3. Update Phase 2 check #10 to review the actual page-heading sequence and its
   equivalence to `page_goal`, rather than calling a page-goal-only read-through
   a title sequence.
4. Add status and discovery title checks to the relevant route guidance without
   expanding the numbered-check total unless an existing check cannot express
   the behavior cleanly.
5. Keep cover and navigation exemptions explicit.

**Tests:** title-contract construction checks above; `python tools/check_skill.py`
may be red only for T5 anchors not yet installed, but existing checks must pass.

**Done when:** each applicable route has positive and negative examples; all
exemptions remain unambiguous; Phase 2 reads real titles and repairs divergence.

---

### T2: Preserve titles, propagate source mode, and publish the template map

**Depends on:** T1

**Touches:**

- `references/playbooks/step4/page-planning-playbook.md`
- `references/playbooks/step4/page-html-playbook.md`
- `references/playbooks/step4/page-review-playbook.md`
- `references/prompts/step4/tpl-page-orchestrator.md`
- `references/prompts/step4/tpl-page-planning.md`
- `references/prompts/step4/tpl-page-html.md`
- `references/prompts/step4/tpl-page-review.md`
- the planning/render portions of `references/prompts.md`

**Approach:**

1. Require planning `title` to copy the approved outline page heading verbatim;
   carry `page_goal` independently.
2. Preserve `source_guidance.strictness` as evidence-boundary prose; document
   real sources and the two closed illustrative sentinels on data points.
3. Add the chart-to-claim Evidence checklist and require unit, baseline/timeframe,
   and source status where applicable.
4. Add the complete functional-template inventory using only existing selectors.
5. Require PageAgent Stage 1, after Evidence review, to validate and hand off the
   existing planning file without rewriting it. A planning change hard-stops
   rendering and returns through Evidence review.
6. Require HTML to use planning `title` for the surface-appropriate primary
   heading, with only the existing browser-title prefix allowed; require Stage 3
   to compare normalized output text to planning before FINALIZE.

**Tests:** goal-based greps for title preservation, source tokens, chart evidence,
and all inventory routes; run `python tools/check_skill.py` for existing checks.

**Done when:** both the PageAgent path and monolithic prompt path carry the same
title/evidence rules; reviewed planning remains unchanged across render; no enum,
schema field, or component has been added.

---

### T3: Add warning-only numeric-source validation

**Depends on:** T2

**Touches:**

- `scripts/planning_validator.py`
- `tests/test_planning_evidence_warnings.py`
- `tools/smoke_skill.py` only if needed to keep generated golden fixtures free
  of unintended warning noise

**Approach:** write the focused tests first, then add the measurement predicate,
illustrative-sentinel normalizer, and per-point WARN emissions described in the
LLD. Do not inspect or redefine `source_guidance.strictness`; do not change
`result.ok`, ERROR counts, workflow versions, or schema enums.

**Tests:** `pytest tests/test_planning_evidence_warnings.py -q`; relevant existing
planning tests; `python tools/smoke_skill.py` after fixture adjustment if needed.

**Done when:** the complete warning and false-positive matrix passes, warnings
include stable IDs and point locations, and every case still produces zero
evidence-related ERROR.

---

### T4: Name and order the three review passes

**Depends on:** T1, T2, T3

**Touches:** `SKILL.md`

**Approach:**

1. Label Step 3 Phase 2 as Story pass.
2. Insert the internal Evidence pass after planning completes and before the
   Step 4.5 Review/Render decision; require repair of validator evidence warnings
   and semantic chart misalignment using the requirements grounding mode.
3. State explicitly that render-direct bypasses only the user-facing worksheet.
4. State that Step 5 consumes the reviewed planning unchanged; a planning
   rollback returns to Evidence review.
5. Label PageAgent Stage 3 / visual QA as Design pass.
6. Remove the sentence that defers intent-line/title reuse; point to this shipped
   contract once implemented.

**Tests:** ordered anchor check plus existing proof-gate and render-gate tests.

**Done when:** the main workflow names the three passes once, in order, and no
branch can enter rendering before evidence review.

---

### T5: Add drift guards

**Depends on:** T1, T2, T3, T4

**Touches:** `tools/check_skill.py`

**Approach:** add narrow contract checks for the cross-file anchors listed under
Construction tests. Validate public tokens and required relationships; do not
freeze prose, line counts, or article-specific wording.

**Tests:** run `python tools/check_skill.py`; mutate one anchor locally during
construction to prove each new check fails, then restore it without committing
the mutation.

**Done when:** deleting any load-bearing title flow, evidence-warning ID,
three-pass ordering, exemption, or inventory route makes the checker fail with a
specific message.

---

### T6: Verify, adversarially review, and close the docs

**Depends on:** T5

**Touches:**

- implementation-touched files only for fixes
- `docs/specs/consulting-grade-deck-contract/{spec,plan}.md`
- `docs/specs/README.md`

**Approach:**

1. Run focused tests, `check_skill.py`, `smoke_skill.py`, then `pytest tests/`.
2. Run the work-loop adversarial reviewer against spec, plan, and diff; address
   all findings or record reasoned declines in the handoff.
3. Verify the article crosswalk against the implemented files.
4. Change spec/plan status only when implementation state warrants it and update
   the spec index.

**Done when:** all supported gates pass, review has no unresolved P0/P1 findings,
acceptance criteria match reality, and the diff contains no unrelated changes.

## Declined patterns

- **New `mckinsey` arc:** declined because consulting-grade quality is a
  cross-cutting execution contract, not an eighth story shape.
- **Universal answer-first titles:** declined because reference, facilitation,
  informational, and discovery work have different epistemic/user contracts.
- **New `action_title` field:** declined because it creates two audience-facing
  title sources and invites render drift.
- **Planning-archetype expansion:** declined because the existing field is a
  density-routing signal; outline-time information already resolves titles.
- **Semantic string-similarity validator:** declined because chart-to-claim
  alignment requires judgment and would create false confidence.
- **Immediate ERROR-level source gate:** declined until warning baselines and
  compatibility impact are measured.
- **Dedicated executive-summary/article templates:** declined because existing
  roles and check #23 already express the function.
- **New review artifact or service:** declined because existing outline, proof,
  and visual stages cover the three passes.
- **Branded style/template, dependency, top-level directory, or preview change:**
  declined as unrelated to the behavioral contract.

## Changelog

- 2026-08-26 — Initial plan after confirmed assumption gate; title reuse moved
  into this spec by explicit user direction; new RFC intentionally skipped.
