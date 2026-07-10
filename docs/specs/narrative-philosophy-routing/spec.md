# Spec: narrative philosophy routing (RFC-0001)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0001 (`docs/rfc/0001-narrative-philosophy-routing.md`)
- **Contract:** none
- **Shape:** data
- **Scope note:** RFC-0001 declared three affected files; this spec adds a fourth (`references/prompts/tpl-outline-orchestrator.md`). The RFC flags the phase2-playbook FINALIZE's `7 项` pre-existing bug; the orchestrator prompt carries a parallel stale `7 项` count at line 40 that the RFC did not enumerate (the RFC's affected surface is three files, confirmed — the orchestrator is never mentioned). This spec treats that as a same-concern erratum discovered during spec authoring. Narrowly scoped: only line 40 of the orchestrator changes.

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The outline engine gains a structured `叙事范式` (narrative paradigm) derived field
covering seven deck archetypes — `pyramid | sparkline | hybrid | reference | status |
facilitation | informational` — together with a philosophy routing table, Phase 1
generation conventions, one updated and twelve new Phase 2 QA checks (checks #9–#21)
that let the outline agent verify archetype-appropriate narrative structure.

Before this change, six narrative properties were unverifiable at QA time: transition
logic, page-level argument completion, title-sequence argument coherence, per-Part
conclusions, thesis-cover alignment, and argument count. Non-persuasion decks
(status, facilitation, informational) had no archetype-specific Phase 2 gates. The
routing mechanism existed only as guidance prose with no structured anchor.

After this change, the outline agent derives `叙事范式` at Step 2 from a routing table
in `narrative-arc.md`, writes it into the outline header, and uses it as the gating
signal for all thirteen new/updated Phase 2 checks. The FINALIZE contract becomes
archetype-conditional (8–12 applicable checks per deck, depending on `叙事范式`),
correcting the pre-existing off-by-two bug (`9`, not `7`, was the correct pre-RFC count).

Four files change: the three LLM-consumed reference documents plus the outline
orchestrator prompt (`references/prompts/tpl-outline-orchestrator.md`), which
hardcodes the stale "7 项" count and must be made count-neutral. No validator code,
no interview fields, no Step 4 planning, and no HTML rendering pipeline are changed.

## Boundaries

### Always do

- Keep all existing Phase 2 checks #1–#8 byte-identical — only #9 is modified.
  The full #9 change is: (a) display heading renamed from `灵魂论点` to `核心论点`;
  (b) field name changed from `core_thesis` to `核心论点`; (c) strictness prose expanded
  to add `必须有角度、有主张、有论断` and the `AI 需要治理` counter-example; (d) archetype
  gate and non-persuasion skip note added. Items (a)–(d) are taken verbatim from RFC §File 3
  check #9 row. The check's *purpose* (verify the deck thesis is a genuine claim, not a
  platitude) is unchanged.
- Keep the `reference` archetype's existing validator code behavior (`reference_runbook`
  Parts, `contract_validator`, `planning_validator`) unmodified — this spec adds only
  the routing-table documentation entry. Note: the FINALIZE AC intentionally drops
  check #9 from the reference deck's applicable set (reference decks have no persuasion
  thesis), which is a Phase 2 text change, not a code behavior change.
- Keep the two `指导性` (guidance-tagged) conventions in `narrative-arc.md §说服型的两条
  "诚实"约定` (so-what netline and illustrative-data banner) unchanged. The per-Part
  close gate (check #11) is new and distinct from these two items; the section gets
  one additive note clarifying the distinction.
- Ensure the seven `叙事范式` values are stated consistently across all three files
  wherever they are listed.
- For pre-RFC outlines lacking `叙事范式`, all Phase 2 checks treat an absent value
  as `pyramid` — document this backward-compat default in checks #10–#12 (the checks
  that explicitly note it per RFC §Proposal). Check #9 carries no separate absent note:
  absent = `pyramid`, so its `{pyramid|sparkline|hybrid}` gate fires for pre-RFC outlines
  without a per-check note. Checks #13–#21 carry no absent-note because absent = `pyramid`
  means they never fire for pre-RFC outlines — the global default covers them.

### Ask first

- Promoting D2 concreteness to a Phase 2 gate (the spec positions it as a Phase 1
  generation convention with an acknowledged limitation; escalation path noted in RFC
  Open question #2).
- Adding a Phase 2 check for bridge-sentence quality (RFC Open question #3).
- Closing the `叙事结构` enum (RFC option B' — the deferred escalation path if LLM
  derivation accuracy falls below 20% error on persuasion decks).
- Any change to the `reference_runbook` validator code or to Step 4 planning.

### Never do

- Add a new interview question or change `叙事结构` values.
- Modify Phase 2 checks #1–#8 (except #9 field-name normalization as specified).
- Change `contract_validator.py` or `planning_validator.py`.
- Change Step 4 planning templates or the HTML rendering pipeline.
- Write `叙事范式` as a new required field (it is derived and optional; absent = `pyramid`).
- Modify the `指导性` tag or the content of the existing so-what netline and
  illustrative-data banner guidance items.

## Testing Strategy

All changes are to LLM-consumed reference document text. No runnable test harness
exists for these files (source: no pytest; gates are `smoke_test.py`,
`lint_diagram_recipes.py`, `check_skill.py` over code/prompts, not reference docs).

**Goal-based check** for every acceptance criterion — a targeted `grep` or `Read`
confirms the specified text is present, the field/check exists, and the stated
conditions (archetype gates, backward-compat defaults, count values) match the RFC
specification. Where the RFC gives explicit example text (check table rows, field
format strings, FINALIZE conditional block), the goal-based check reads for those
key tokens.

**Manual consistency verification** (cross-file) — after all three files are
updated, a cross-file read confirms the seven `叙事范式` values are identical and that
the FINALIZE count table matches the actual check numbering.

## Acceptance Criteria

### File 1 — `references/principles/narrative-arc.md`

- [x] A new section "哲学路由：应用场景与叙事范式" (or equivalent heading) appears after the
  existing framework descriptions (金字塔原理 / SCQA / 故事弧线), containing a routing
  table that covers all seven `叙事范式` values: `pyramid`, `sparkline`, `hybrid`,
  `reference`, `status`, `facilitation`, `informational`, organized in three tiers.
- [x] Each Tier 1 row (`pyramid`, `sparkline`, `hybrid`) specifies cover style,
  transition requirement, and closing requirement; the `pyramid`/`hybrid` rows require
  a thesis-first cover; the `sparkline` row requires a hook-first/tension cover.
- [x] The Tier 2 row (`reference`) states that `reference` requires at least one
  `reference_runbook` Part and that a persuasion timeline without any `reference_runbook`
  Part falls to the fallback rows.
- [x] Each Tier 3 row (`status`, `facilitation`, `informational`) specifies cover,
  transition, and closing conventions; the `status` row requires a RAG/on-track cover;
  the `facilitation` row requires a session objective cover; the `informational` row
  requires a learning-objectives cover.
- [x] Two fallback rows exist: one for `叙事结构` unrecognized + persuasion goal apparent
  (`pyramid` default with documented reasoning) and one for unrecognized + no persuasion
  goal (`informational` default with documented reasoning).
- [x] `§说服型的两条"诚实"约定` gains an additive note after the two existing items
  clarifying that both guidance items remain unchanged and that check #11 adds a new
  mandatory per-Part close-page gate distinct from the two guidance conventions.

### File 2 — `references/playbooks/outline-phase1-playbook.md`

- [x] The `outline.txt` schema header block contains a `叙事范式` field with all seven
  values listed (`pyramid / sparkline / hybrid / reference / status / facilitation /
  informational`), placed after `叙事结构`.
- [x] The `叙事范式` field description states: derived by outline agent at Step 2 from
  the routing table; not asked of user; `reference` requires `reference_runbook` Parts;
  bifurcated fallback (persuasion intent → `pyramid`, non-persuasion → `informational`,
  both with documented reasoning); pre-RFC absent value treated as `pyramid` by Phase 2.
- [x] Step 2 of the 5-step methodology gains an addendum instructing the agent to
  consult the routing table in `principles/narrative-arc.md` and write `叙事范式`
  from the `叙事结构` input, `论证策略` choices, and the deck's stated purpose.
- [x] `与上一 Part 的关系` format in the per-Part schema block is updated to require a
  bridge sentence for all non-首Part transitions: `递进 | 转折 | 因果` transitions
  require a one-sentence logical/emotional through-line; `并列` transitions use
  coordinate-relationship phrasing ("Part N 建立了[A]；本 Part 以[B]补充并行论据").
  `首Part` retains `无` (no bridge).
- [x] A `页目标` claim-shape and concreteness convention block exists for persuasion
  decks (`叙事范式: pyramid | sparkline | hybrid`): states that pages with `信息姿态:
  结论页 / 解释页 / 证据页` must have a `页目标` that is (1) an assertion from the
  audience's perspective, not a topic label, and (2) concrete/quantifiable. Includes
  the "X 因此 Y" clarification and the navigation-page exemption. References check #10.
- [x] Step 1 (提炼全局核心论点) gains a cover-resonance requirement for persuasion decks:
  `pyramid`/`hybrid` — cover `页目标` directly states or strongly implies `核心论点`;
  `sparkline` — cover sets a tension that `核心论点` resolves; references check #10
  sub-check ①.

### File 3 — `references/playbooks/outline-phase2-playbook.md`

- [x] Check #9 row is fully replaced per RFC §File 3: display heading renamed from
  `灵魂论点` to `核心论点`; field name changed from `core_thesis` to `核心论点`; strictness
  prose expanded to include `必须有角度、有主张、有论断` and the `AI 需要治理` counter-example;
  archetype gate `叙事范式 ∈ {pyramid | sparkline | hybrid}` added; non-persuasion
  archetypes skip note added. All taken verbatim from RFC §File 3 check #9 row.
- [x] Check #10 row exists: "标题叙事序列" (仅 `叙事范式 ∈ {pyramid | sparkline | hybrid}`);
  sub-check ① verifies cover `页目标` resonates with `核心论点`; sub-check ② verifies
  that reading only argument-page `页目标` values forms a coherent argument chain of
  assertions (not topic labels); includes fix guidance and pre-RFC absent-value default.
- [x] Check #11 row exists: "结论收束" (仅 `论证策略: narrative_driven` 或 `data_driven`
  Parts, 仅说服型 deck); gates on `叙事范式 ∈ {pyramid | sparkline | hybrid}`;
  requires at least one `叙事角色: close` or `信息姿态: 结论页` page per qualifying Part
  with an assertion-form `页目标`; includes pre-RFC absent-value default (absent = `pyramid`).
- [x] Check #12 row exists: "论证部 Part 数量" (仅 `叙事范式 ∈ {pyramid | sparkline |
  hybrid}`); verifies that argumentation Parts (`论证策略 ∈ {narrative_driven,
  data_driven, case_study, comparison, framework, step_by_step, authority}`) number
  ≤ 5; includes fix guidance; includes pre-RFC absent-value default (absent = `pyramid`).
- [x] Checks #13–#15 rows exist with `叙事范式: status` gate: check #13 (opening
  verdict — RAG signal + status sentence in first 2 pages); check #14 (decision log
  completeness — at least one structured "[decision] → [Owner] → [deadline]" entry);
  check #15 (backward→forward structure — performance review block before forward-look block).
- [x] Checks #16–#18 rows exist with `叙事范式: facilitation` gate: check #16
  (session objective stated in first 2 pages, verifiable goal); check #17 (activity
  atomicity — each activity's instructions fit on one page); check #18 (closing
  collection page present — `叙事角色: close` or equivalent capturing decisions/open
  questions/action owners).
- [x] Checks #19–#21 rows exist with `叙事范式: informational` gate: check #19
  (learning objectives stated in cover or page 2, verifiable "after this you will be
  able to..."); check #20 (module recap page at each Part boundary before next Part
  opens); check #21 (closing action guidance — training variant: knowledge check or
  practice task; onboarding variant: first-week action list + key contacts).
- [x] The `## 自审检查清单` heading is updated from `（9项门禁）` to `（21项，按叙事范式适用）`;
  the FINALIZE conditional block (in `## FINALIZE 签名契约`) lists per-archetype applicable check sets:
  `pyramid/sparkline/hybrid` → #1–12 (12 items); `reference` → #1–8 (8 items);
  `status` → #1–8 + #13–15 (11 items); `facilitation` → #1–8 + #16–18 (11 items);
  `informational` → #1–8 + #19–21 (11 items); absent `叙事范式` → treat as `pyramid`
  (#1–12).
- [x] The intro sentence under `## 自审检查清单` (currently "必须在脑海里（或推演日志中）走完这 9 项检查，任何一项不通过都不允许交卷")
  is updated to reference the per-archetype applicable set instead of a fixed count — e.g.
  "必须在脑海里（或推演日志中）走完所有适用于本 deck 叙事范式的检查项，任何一项不通过都不允许交卷（见 FINALIZE 速查）".

### File 4 — `references/prompts/tpl-outline-orchestrator.md`

- [x] Line 40 (`禁止在编写阶段就考虑自审的 7 项检查标准`) is updated to count-neutral
  wording (e.g. `禁止在编写阶段就考虑阶段 2 的自审检查标准`) — removing the stale
  hardcoded "7 项" count. No other line in the file is modified.

### Cross-file

- [x] The seven `叙事范式` values (`pyramid`, `sparkline`, `hybrid`, `reference`,
  `status`, `facilitation`, `informational`) are listed identically wherever all seven
  appear together in the three reference files.
- [x] No existing Phase 2 check #1–#8 content is modified (only #9 field name and
  gate are updated as specified).
- [x] Gate tool checks (`smoke_test.py`, `lint_diagram_recipes.py`, `check_skill.py`)
  remain green — reference doc edits do not touch code or validator files.
- [x] `grep "7 项" references/prompts/tpl-outline-orchestrator.md` returns 0
  (style-phase2-playbook.md is untouched — its independent "7 项" for the
  style checklist is out of scope).

## Assumptions

- Technical: all three target files are plain Markdown; no parser or validator reads
  them programmatically except as raw injection into LLM prompts (source: repo read —
  `outline-phase1-playbook.md` and `outline-phase2-playbook.md` are injected via
  `{{PLAYBOOK}}` in phase prompt templates; `narrative-arc.md` is linked from the
  playbooks; no code parses their Markdown structure).
- Technical: `check_skill.py`, `smoke_test.py`, `lint_diagram_recipes.py` do not
  scan or validate reference doc content — they run against code/prompt artifacts
  (source: baseline gate run; `scripts/check_skill.py` reads prompts and validators,
  not reference docs).
- Technical: the `outline.txt` contract's `叙事范式` field is new and optional for
  pre-RFC outlines; the Phase 2 agent treats absent = `pyramid` per backward-compat
  default documented in each check (source: RFC §Migration; no validator currently
  parses `叙事范式`).
- Process: this is full-mode (multi-feature, structural public-interface change — adds
  a new outline header field and 12 new Phase 2 checks) (source: work-loop risk trigger
  assessment 2026-07-10).
- Product: all seven RFC decisions (D1–D8) are accepted; the exact text of checks
  #9–#21, field formats, and FINALIZE conditional are taken directly from RFC-0001
  §Proposal (source: RFC status Accepted, date closed 2026-07-10).
