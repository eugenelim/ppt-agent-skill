# Spec: audience-type routing (RFC-0002)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0002 (`docs/rfc/0002-audience-type-routing.md`); builds on RFC-0001 (`docs/rfc/0001-narrative-philosophy-routing.md`)
- **Contract:** none
- **Shape:** data
- **Scope note:** RFC-0002 declared four affected files, all LLM-consumed reference documents, with no validator change. Grounding falsified the implicit no-code premise on one axis: both rendered interview prompts sit at ~99% of a byte cap enforced by `smoke_skill.py` (structured 8977/9000 B; text-fallback 11434/11500 B), so the RFC's File 1/File 2 additions cannot pass the gate as written. Per maintainer decision (2026-07-10, Option A+B, caps revised upward on review), this spec (a) raises those two caps to `11000` / `13000` — a **fifth file, `scripts/smoke_skill.py`** — and (b) keeps the File 1 shared-core addition lean, relocating the full 4-tier descriptive routing detail into File 3 (the uncapped phase-1 playbook) where Step-2 derivation actually reads it. This is a deliberate deviation from the RFC's literal File 1 text and its four-file surface; because an Accepted RFC's body is frozen (`CONVENTIONS.md` § Document lifecycle), **this scope note is the canonical record of the deviation** — the RFC body is not edited.

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The outline engine gains two derived `outline.txt` header fields — `受众层级`
(audience tier: `exec | leadership | team | mixed`, the decision-making authority
level of the target audience) and `消费模式` (consumption mode: `live | pre-read |
async`, how the deck is consumed) — together with two routing tables, a Step-2
derivation task, and five new Phase 2 QA checks (checks #22–#26) that let the
outline agent verify audience-calibration properties orthogonally to RFC-0001's
seven-value `叙事范式` routing.

Before this change, five audience-calibration properties were unverifiable at QA
time: density ceiling for high-authority audiences, standalone executive summary,
structured decision ask, evidence specificity for working teams, and pre-read
standalone coverage for breathing slides. A board deck and a working-team deck
could both carry `叙事范式: pyramid` yet needed fundamentally different treatment,
and nothing gated the difference.

After this change, the outline agent derives `受众层级` and `消费模式` at Step 2 from
routing tables in the phase-1 playbook, writes them into the outline header, and
uses them as gating signals for checks #22–#26. The FINALIZE contract gains an
audience/consumption stacking layer on top of RFC-0001's `叙事范式` rows. The
`core_audience` interview question is enriched in both modes — structured-UI
exposes the tier enum directly (near-deterministic), text-fallback retains prose
with the routing table (~85–90%) — with **no new interview anchor** and **no
`contract_validator.py` change** (`audience` is presence-checked, not
enum-constrained).

Five files change: the two interview-prompt reference documents (`tpl-interview.md`,
`module-structured-interview-ui.md`), the two playbook reference documents
(`outline-phase1-playbook.md`, `outline-phase2-playbook.md`), and — per the scope
note — `scripts/smoke_skill.py`, whose two interview-prompt byte caps rise to
`11000` / `13000`. No validator code, no new interview field, no Step-4 planning,
and no HTML rendering pipeline are changed.

## Boundaries

### Always do

- Derive `受众层级` and `消费模式` from routing tables at Step 2 — **never** ask the
  user a new interview question and **never** add a new required anchor.
- Keep all existing Phase 2 checks #1–#21 byte-identical; checks #22–#26 are purely
  additive rows after #21.
- Take the exact routing-table rows, check text, gate conditions, thresholds, and
  fallbacks verbatim from RFC-0002 §File 3 / §File 4, with the single deliberate
  deviation named in the scope note (File 1 lean, full detail relocated to File 3).
- Keep the two interview prompts within their caps: after all edits, the rendered
  structured prompt is `< 11000 B` and the rendered text-fallback prompt is
  `< 13000 B` (measured via `prompt_harness.py` with the smoke fixture vars).
- Make `受众层级` orthogonal to `叙事范式`: check #22 is the only cross-archetype gate,
  and its `reference`-archetype exemption is the one explicit interaction between
  the two dimensions (RFC-0001's uniform-dense convention takes precedence for
  runbooks).
- Document the pre-RFC backward-compat defaults at each field's definition site (the
  File 3 routing-table fallback rows) and in the File 4 FINALIZE summary: absent
  `受众层级` → treated as `leadership`; absent `消费模式` → check #26 skips entirely.
  (This matches RFC-0002 §Migration, which states the defaults once at field level,
  not per-check.)
- Preserve the `check #26` no-auto-fix contract: when `manual_audit_mode` scope
  includes `outline` (or is `fine_grained`), surface A/B/C options in the user's
  `language`; when `off` or scope excludes `outline`, flag-and-continue into the
  Phase 2 summary without modifying the outline.

### Ask first

- Including the `reference` archetype in check #22's density cap (RFC-0002 Review
  focus #1 — this spec excludes it; a reviewer may override).
- Changing check #23's `≥10`-page threshold relative to RFC-0001's planned
  `exec-summary-slide` `≥15` Phase-1 convention (RFC-0002 Review focus #3).
- Adding a `leadership`-tier evidence-display convention (RFC-0002 Open question #1
  — deferred to post-landing audit).
- Capturing `消费模式` explicitly at the interview stage (RFC-0002 Open question #2
  — deferred; escalation only if audits show ≥25% live/pre-read misclassification).
- Raising the interview-prompt caps beyond the even `11000` / `13000` set here, or
  reclaiming budget by trimming existing interview prose.

### Never do

- Add a new interview anchor (`受众层级` as a `REQUIRED_INTERVIEW_ANCHORS` entry) or
  trigger the 6-file anchor lockstep — this is the deferred escalation path, not
  this spec's scope.
- Change `contract_validator.py`, `planning_validator.py`, `check_skill.py`, or any
  validator/normalization code, or close `audience` to a strict enum.
- Modify Phase 2 checks #1–#21, or any RFC-0001 `叙事范式` routing/check content.
- Change Step-4 planning templates, the HTML rendering pipeline, or per-page density
  rules.
- **Structural:** add a new module boundary, a new top-level directory, a new
  dependency, or a new abstraction layer — the change is text edits to five existing
  files only.
- Fold `受众层级` and `消费模式` into `叙事范式` routing, or introduce a compound
  `受众情境` field — the dimensions stay orthogonal.
- Make `smoke_skill.py` changes beyond the two cap constant values (`9000`→`11000`,
  `11500`→`13000`); the assertion structure and every other budget are untouched.

## Testing Strategy

Four of the five files are LLM-consumed reference documents with no runnable test
harness over their content (source: no pytest over reference docs; gates are
`smoke_skill.py`, `check_skill.py`, `lint_diagram_recipes.py`, `smoke_test.py` over
code/prompts). The fifth (`smoke_skill.py`) is exercised by running the smoke gate
itself.

- **Goal-based check** for every reference-doc acceptance criterion — a targeted
  `grep` or `Read` confirms the specified field, table, check, gate condition,
  threshold, and backward-compat default is present and matches the RFC. Where the
  RFC gives explicit example text (routing rows, check rows, FINALIZE worked
  examples), the check reads for those key tokens. *Why:* no invariant to assert in
  a test file; presence-and-shape is the contract for prompt text.
- **Byte-budget check (goal-based, mechanism = `prompt_harness.py` + `smoke_skill.py`)**
  for the interview-prompt edits and the cap raise — render both interview prompts
  with the smoke fixture vars and assert structured `< 11000 B`, text `< 13000 B`,
  then run `python scripts/smoke_skill.py` and confirm its interview-prompt assertions
  pass (`prompt-interview-structured: ok`, `prompt-interview-text: ok`) with the
  raised caps in force. (`smoke_skill.py`'s overall exit is non-zero in this
  workspace on a pre-existing, unrelated cause — two never-committed files
  `references/styles/runtime-style-rules.md` and `runtime-style-palette-index.md`
  (absent from the repo, not merely untracked) plus pre-existing chart-ref
  (`kpi` / `metric-row` / …) and `prompt-page-planning` resolution failures, all
  identical on pristine `origin/main`; this change introduces no new failure.)
  *Why:* this is the gate the RFC's literal change
  would have failed; it is the load-bearing verification for File 1/File 2/File 5.
  The mechanism exists and is confirmed (rendered current sizes measured during
  spec authoring); no task-zero needed.
- **Manual cross-file consistency verification** — after all edits, a cross-file
  read confirms the tier/mode value sets are identical wherever listed, the FINALIZE
  stacking worked examples are arithmetically correct against the actual check
  numbering, and checks #1–#21 are byte-identical to pre-PR. *Why:* the FINALIZE
  arithmetic and cross-file value-set agreement are exactly the drift RFC-0001's
  spec caught by hand; the same lens applies.

## Acceptance Criteria

### File 3 — `references/playbooks/outline-phase1-playbook.md` (canonical routing source)

- [x] The `outline.txt` schema header block gains `受众层级：{exec / leadership /
  team / mixed}` and `消费模式：{live / pre-read / async}`, placed after `叙事范式`
  (currently line 89) and before `密度倾向`.
- [x] The `字段枚举约束` block gains descriptions for both fields marking them
  **derived at Step 2, not asked of the user**, with value sets listed and the
  pre-RFC backward-compat defaults stated (absent `受众层级` → `leadership`; absent
  `消费模式` → check #26 skips).
- [x] A `受众层级` routing table exists covering all rows from RFC-0002 §File 3:
  bare-token short-circuit, the four authority-tier signal rows (`exec` /
  `leadership` / `team` / `mixed`), and the ambiguous-description fallback
  (`leadership` default with documented-reason instruction). Boundary is decision
  authority, not seniority.
- [x] The `受众层级` row-evaluation precedence rule is stated: (1) bare tier token
  from structured-UI → use directly; (2) multi-tier co-presence → `mixed`, else
  most-senior tier; (3) target audience's level is the signal, not the presenter's.
- [x] A `消费模式` routing table exists covering all signal rows from RFC-0002
  §File 3 (`reference`→async, `facilitation`→live, `informational`→async,
  `status`→live, exec+board→pre-read, exec+roadshow→live, explicit pre-read
  signal→pre-read, `pyramid/sparkline/hybrid` default→live) and the
  ambiguous-signal fallback (`live` default with documented reason).
- [x] Step 2 of the 5-step methodology gains a derivation addendum (after the
  existing `叙事范式` note at line 30) instructing the agent to consult both routing
  tables and write `受众层级` and `消费模式`, honoring the bare-token short-circuit and
  the precedence rule, both as derived fields.
- [x] The full 4-tier descriptive labels (authority definitions + scan/read behavior
  per tier, per RFC-0002 §File 1's tier block) live here (relocated from the
  interview prompt per the scope note), so File 1 can point to this table.

### File 4 — `references/playbooks/outline-phase2-playbook.md`

- [x] Checks #22–#26 rows are appended after check #21, each matching RFC-0002
  §File 4 verbatim (applicable condition, strict standard, fix handling):
  - [x] #22 密度上限（高层受众）: `受众层级 ∈ {exec, mixed}` · `叙事范式 ≠ reference`;
    `密度倾向` must not be `ultra_dense`; `reference` exemption noted.
  - [x] #23 独立摘要页（高层 · 说服型）: `受众层级 ∈ {exec, mixed}` · `叙事范式 ∈
    {pyramid | sparkline | hybrid}` · 总页数 ≥ 10; a `结论页` in the first 3 pages
    conveying both core thesis and the decision/action ask.
  - [x] #24 决策请求格式（高层 · 决策型）: `受众层级 ∈ {exec, mixed}` · `叙事范式 ∈
    {pyramid | hybrid}` (excludes `sparkline`); closing page carries an
    Owner-and-deadline approval request.
  - [x] #25 证据具体性（团队 · 说服型）: `受众层级: team` · `叙事范式 ∈ {pyramid |
    sparkline | hybrid}`; `证据页` `页目标` cites specific/quantified data or named
    source.
  - [x] #26 呼吸页独立可读（预读模式）: `消费模式: pre-read`; `呼吸页` `页目标` carries
    standalone meaning; **no auto-fix** — `manual_audit_mode`-gated branching
    (surface A/B/C in the user's `language` when scope includes `outline` or is
    `fine_grained`; else flag-and-continue into the Phase 2 summary).
- [x] The `## 自审检查清单（21项，按叙事范式适用）` heading is updated to reflect 26
  checks and the added audience/consumption dimension (e.g.
  `（26项，按叙事范式与受众/消费模式适用）`).
- [x] The FINALIZE `适用检查速查` block gains the audience/consumption stacking rows
  and worked examples from RFC-0002 §File 4 (`exec/mixed` non-reference → +#22;
  `exec/mixed` pyramid/hybrid → +#22–24; `exec/mixed` sparkline → +#22–23; `team`
  persuasion → +#25; `leadership` → none; `pre-read` → +#26; `live`/`async` → none),
  including the `reference + exec` = 8-item exemption example.
- [x] The FINALIZE `适用检查速查` block carries the pre-RFC-absent line from RFC-0002
  §File 4 verbatim: absent `受众层级` → treated as `leadership`; absent `消费模式` →
  check #26 skips (this is the secondary documentation site named in Boundaries).
- [x] The FINALIZE worked-example counts are arithmetically consistent with the
  actual check numbering (e.g. `pyramid + exec + live` = #1–12 + #22–24 = 15), and
  every #23-inclusive worked example carries its `总页数 ≥ 10` precondition inline —
  since check #23 only fires at ≥10 pages, a sub-10-page `exec` pyramid deck applies
  14, not 15. The stacking rows and examples must not present #23 as unconditional.

### File 1 — `references/prompts/tpl-interview.md` (shared core, lean)

- [x] A compact `受众层级` reference is added immediately after the `core_audience`
  bullet (line 19) that: names the four tiers with a one-phrase authority gloss
  each, states the field is derived at Step 2 from the phase-1 playbook routing
  table (not asked), and notes structured-UI users pick the tier directly and
  short-circuit derivation. It **points to** the File 3 routing table for the full
  口径 rather than restating it.
- [x] The `audience` anchor name, the `字段归一化映射` table, and the mandatory anchor
  list are unchanged.

### File 2 — `references/prompts/module-structured-interview-ui.md`

- [x] The `core_audience` single-select gains named tier-enum options — `exec`,
  `leadership`, `team`, `mixed`, plus an 其他/自定义 escape hatch — each with a
  one-phrase authority gloss, and a note that selecting a tier normalizes `audience`
  to that bare token (which Step 2 recognizes as authoritative).

### File 5 — `scripts/smoke_skill.py`

- [x] The interview-prompt byte caps are raised: `assert_max_bytes(... 9000 ...)`
  (currently line 1739, `prompt-interview-structured`) → `11000`;
  `assert_max_bytes(... 11500 ...)` (currently line 1753, `prompt-interview-text`)
  → `13000`. No other line and no other budget in the file changes.

### Cross-file

- [x] The tier value set (`exec / leadership / team / mixed`) and the mode value set
  (`live / pre-read / async`) are listed identically wherever each appears as a
  complete set across the four reference files.
- [x] Rendered interview prompts stay within the raised caps: structured `< 11000 B`,
  text-fallback `< 13000 B` (via `prompt_harness.py` with the smoke fixture vars).
- [x] Gates: `check_skill.py`, `lint_diagram_recipes.py`, `smoke_test.py` exit 0;
  `smoke_skill.py`'s interview-prompt assertions pass with the raised caps
  (`prompt-interview-structured: ok`, `prompt-interview-text: ok`). `smoke_skill.py`'s
  overall non-zero exit is a pre-existing, unrelated environmental failure — two
  never-committed files (`references/styles/runtime-style-rules.md`,
  `runtime-style-palette-index.md`, absent from the repo, not merely untracked) plus
  pre-existing chart-ref (`kpi` / `metric-row` / …) and `prompt-page-planning`
  resolution failures, all identical on pristine `origin/main` — no new failure
  introduced by this change.
- [x] Phase 2 checks #1–#21 are unmodified: `git diff origin/main --
  references/playbooks/outline-phase2-playbook.md` shows only additions after #21 and
  the heading/FINALIZE edits — no change inside rows #1–#21.
- [x] `contract_validator.py` is unmodified: `git diff origin/main --
  scripts/contract_validator.py` is empty.

## Assumptions

- Technical: both runtime interview prompts embed the shared core (`tpl-interview.md`
  via `INTERVIEW_CORE`) and their mode module (`INTERVIEW_MODE_MODULE`); editing
  File 1 reaches both modes, File 2 reaches structured only (source: repo read —
  `scripts/smoke_skill.py:1411–1451`).
- Technical: `audience` is presence-checked via `REQUIRED_INTERVIEW_ANCHORS`, not
  value-enum-constrained; a bare tier token `audience: exec` passes the validator
  unchanged (source: `scripts/contract_validator.py:66,84–86`).
- Technical: the interview prompts are byte-capped at 9000 (structured) / 11500
  (text) and currently render at 8977 / 11434 B — ~99% full; the lean A+B edits
  render at 10113 / 11870 B (structured grew past the initial 9795 estimate because
  the shipped File 2 block carries a heading + normalization note), clearing the
  raised 11000 / 13000 caps with 887 / 1130 B headroom (source: probe —
  `prompt_harness.py` render with smoke fixture vars,
  2026-07-10).
- Technical: the phase-2 playbook currently holds checks #1–#21 ("21项",
  `outline-phase2-playbook.md:18`); #22–#26 append without numbering collision
  (source: repo read).
- Technical: reference-doc edits do not touch code the gates import; only File 5's
  cap constants affect gate behavior (source: RFC-0001 spec precedent + repo read —
  playbooks are injected as prompt text, not parsed).
- Process: full-mode work (multi-feature, dependent tasks, public-interface change to
  the `outline.txt` header contract) (source: work-loop risk-trigger assessment
  2026-07-10).
- Process/Product: raise interview caps to an even 11000 / 13000 and keep File 1 lean
  with detail relocated to File 3 — Option A+B, deviating from RFC-0002's literal
  File 1 text and expanding its 4-file surface to 5 (source: maintainer confirmation
  2026-07-10).
- Product: all RFC-0002 decisions D1–D5 are accepted; exact routing rows, check text,
  thresholds, and fallbacks are taken from RFC-0002 §File 3 / §File 4 (source: RFC
  status Accepted, date closed 2026-07-10).
