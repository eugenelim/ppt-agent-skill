# Plan: audience-type routing (RFC-0002)

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Five files change in one PR. The strategy is **File 3 first (T1)** because the
phase-1 playbook is the canonical source of the two derived fields and both routing
tables — everything else references it: the phase-2 checks (T2) gate on the fields
it defines, and the lean interview-prompt addition (T3) points to its routing table
for the full 口径. T2, T3, T4 are then independent files.

`smoke_skill.py`'s two cap raises (T5) are **task-zero for the interview-prompt
edits**: the prompts already render at ~99% of their current caps, so T3/T4's added
bytes fail `smoke_skill.py` unless the caps rise first. T5 lands the cap raise
(prompts still well under the raised caps at that point), then T3/T4 add the lean
content that clears the raised caps by a measured margin. T6 is a read-only
cross-file consistency + full-gates pass.

The riskiest parts are (a) the byte budget — the whole reason the RFC's literal
change couldn't ship — defended by a per-task render-and-measure `Done when:` on
T3/T4 and the T5 cap raise; and (b) the phase-2 check-table edit (T2), which must
append #22–#26 and update the FINALIZE stacking arithmetic without touching #1–#21,
defended by grep-based tests and a `git diff` non-modification check in T6.

All changes are reversible by revert (LLM-consumed docs + two integer constants; no
data migration, no validator change, no new outline invalidated — new checks apply
only to outlines carrying the new fields; absent `受众层级` → `leadership`, absent
`消费模式` → check #26 skips).

**Declined patterns (pre-mortem).** Tempted to reclaim interview-prompt budget by
refactoring the shared core's existing prose — declining; the maintainer chose to
raise the caps instead (Option A+B), and trimming tuned interview text risks
regressing interview quality out of scope. Tempted to add a `受众层级` validator/enum
guard so the derived field is checked at write-time — declining; the field is
derived and optional, guarding it would pull in the code change the RFC explicitly
scoped out. Tempted to parameterize the two caps into a shared constant — declining;
two literal edits are clearer than a new indirection for values that move together
rarely.

**Resolve-vs-surface disposition.** The one irreducible item — the RFC-vs-gate byte
budget conflict — was surfaced to the maintainer and resolved by direction (Option
A+B, caps 11000/13000) on 2026-07-10. All other open items resolved against
referents: routing/check text → RFC-0002 §File 3/§File 4; field/prompt mechanics →
repo reads cited in the spec's Assumptions; the `reference`-exemption and `≥10`
threshold are RFC-ratified (Review focus #1/#3 accepted) and parked in Boundaries
§Ask-first for a reviewer override rather than reopened here.

## Constraints

- RFC-0002 (`docs/rfc/0002-audience-type-routing.md`) — decisions D1–D5 accepted;
  exact routing rows, check wording, thresholds, and FINALIZE stacking taken from
  RFC §File 3 / §File 4. The one deliberate deviation (File 1 lean + detail
  relocated to File 3, plus the fifth file `smoke_skill.py`) is recorded in the
  spec's scope note, which is its canonical home — the Accepted RFC body is frozen
  (`CONVENTIONS.md` § Document lifecycle) and is not edited.
- RFC-0001 (`docs/rfc/0001-narrative-philosophy-routing.md`) and its shipped spec
  (`docs/specs/narrative-philosophy-routing/`) — not reopened; `叙事范式` routing and
  checks #1–#21 are untouched. Check #22's `reference` exemption is the only
  cross-dimension interaction.
- Memory `ppt-interview-anchor-consumers.md` — the 6-file anchor lockstep + byte
  budget is the deferred escalation path, explicitly out of scope; this spec adds no
  anchor.
- Backward-compat: absent `受众层级` → Phase 2 treats as `leadership`; absent
  `消费模式` → check #26 skips. Documented at each field-definition site (File 3
  fallback rows) and in the File 4 FINALIZE summary — once at field level, per
  RFC-0002 §Migration, not restated per consuming check.

## Construction tests

Goal-based greps per task (see Tasks). Byte-budget render check on T3/T4/T6.

**Byte budget (T3, T4, T6):**
```bash
python scripts/prompt_harness.py --template references/prompts/tpl-interview-structured-ui.md \
  --var "TOPIC=Linux.do 社区介绍" \
  --var "USER_CONTEXT=4 页介绍型 PPT，目标是快速讲清社区定位、氛围、价值与加入理由。" \
  --inject-file "INTERVIEW_MODE_MODULE=references/prompts/module-structured-interview-ui.md" \
  --inject-file "INTERVIEW_CORE=references/prompts/tpl-interview.md" --output /tmp/s.md
# wc -c /tmp/s.md  →  < 11000
# same for tpl-interview-text-fallback.md + module-text-interview-fallback.md  →  < 13000
```

**Cross-file consistency (T6):**
- `grep -n "受众层级\|消费模式" references/playbooks/outline-phase1-playbook.md references/playbooks/outline-phase2-playbook.md references/prompts/tpl-interview.md references/prompts/module-structured-interview-ui.md` — fields/values present where expected.
- Tier set (`exec / leadership / team / mixed`) and mode set (`live / pre-read / async`) identical wherever each is a complete set.
- FINALIZE worked-example counts arithmetically match the check numbering.

**Gate non-regression (T5, T6):**
- `python scripts/smoke_skill.py && python scripts/check_skill.py && python scripts/lint_diagram_recipes.py && python scripts/smoke_test.py` exit 0.
- `git diff origin/main -- scripts/contract_validator.py` empty; `git diff origin/main -- references/playbooks/outline-phase2-playbook.md` shows no change inside rows #1–#21.

## Design (LLD)

### Design decisions

- **`受众层级` and `消费模式` are derived, not asked.** The outline agent writes them at
  Step 2 from routing tables — no new interview field. Mirrors how `叙事范式` and
  `论证策略` are agent-derived. Traces to: AC (File 3, header fields + Step 2).
- **Full tier detail lives in File 3, not File 1.** The interview prompts are
  byte-capped; the descriptive 4-tier routing 口径 belongs in the uncapped phase-1
  playbook where Step-2 derivation reads it. File 1 carries only a compact pointer.
  Traces to: spec scope note + AC (File 1, File 3).
- **Caps raised, not budget reclaimed.** `smoke_skill.py`'s two interview caps rise
  to an even 11000 / 13000 (maintainer decision); no existing prompt prose is
  trimmed. Traces to: AC (File 5) + Boundaries §Ask-first.
- **Fully orthogonal to `叙事范式`.** Check #22 is the only cross-archetype gate; its
  `reference` exemption is the single explicit interaction. Checks #23–#25 scope to
  persuasion archetypes; #26 keys on `消费模式` alone. Traces to: Boundaries.
- **Check #26 never auto-fixes.** `消费模式` routing has real uncertainty; a wrong
  auto-fix is worse than none. Branching keys on `manual_audit_mode`. Traces to: AC
  (File 4, #26).

### Behavior & rules

- `受众层级` gates: #22 (`{exec, mixed}` · `叙事范式 ≠ reference`), #23 (`{exec, mixed}`
  · `{pyramid|sparkline|hybrid}` · ≥10 pages), #24 (`{exec, mixed}` ·
  `{pyramid|hybrid}`), #25 (`team` · `{pyramid|sparkline|hybrid}`).
- `消费模式` gates: #26 (`pre-read`).
- Absent `受众层级` → `leadership` (no exec/team checks fire). Absent `消费模式` → #26
  skips.
- Structured-UI writes a bare tier token into `audience`; Step 2 recognizes it and
  short-circuits the routing table.
- Checks #1–#21 apply exactly as today (no change).

## Tasks

### T1: Add derived fields + routing tables to `outline-phase1-playbook.md`

**Depends on:** none
**Touches:** `references/playbooks/outline-phase1-playbook.md`
**Mode:** goal-based check

> **Source discipline:** use RFC-0002 §File 3 (RFC lines ~117–176) for the two
> routing tables, precedence rule, Step 2 addendum, and header fields; use §File 1's
> tier block (RFC lines ~95–100) for the full 4-tier descriptive labels relocated
> here.

**Tests:**
- `grep "受众层级：{exec / leadership / team / mixed}" references/playbooks/outline-phase1-playbook.md` hits the header schema.
- `grep "消费模式：{live / pre-read / async}" references/playbooks/outline-phase1-playbook.md` hits the header schema.
- `grep "受众层级" references/playbooks/outline-phase1-playbook.md` returns ≥ 5 (header, enum-constraint block, routing table, Step 2, tier labels).
- `grep "消费模式" references/playbooks/outline-phase1-playbook.md` returns ≥ 4.
- `grep "leadership.*默认\|默认.*leadership\|无法确定权威" references/playbooks/outline-phase1-playbook.md` — `受众层级` fallback present.
- `grep "pre-read\|预读" references/playbooks/outline-phase1-playbook.md` — `消费模式` rows/labels present.
- `grep "决策权\|治理\|职能\|执行交付\|跨层级" references/playbooks/outline-phase1-playbook.md` — authority-based tier labels relocated here.
- `grep "裸.*token\|bare\|短路\|结构化 UI" references/playbooks/outline-phase1-playbook.md` — bare-token short-circuit precedence.

**Approach:**
1. In the `outline.txt` 强制格式骨架 block (after `叙事范式：...` at line 89), add the
   two field lines `受众层级：{exec / leadership / team / mixed}` and
   `消费模式：{live / pre-read / async}` before `密度倾向`.
2. In `字段枚举约束` (after the `叙事范式` bullet at line 131), add two bullets: each
   field derived at Step 2 from the routing table, not asked; value set; pre-RFC
   default (`受众层级` absent → `leadership`; `消费模式` absent → #26 skips).
3. Add a `受众层级` routing table + precedence rule + fallback and a `消费模式` routing
   table + fallback, copying rows verbatim from RFC-0002 §File 3, including the full
   4-tier descriptive labels (authority definition + scan/read behavior) relocated
   from §File 1.
4. Extend Step 2 (after the existing `叙事范式` addendum at line 30) with the
   受众/消费 derivation task from RFC §File 3, honoring the bare-token short-circuit
   and precedence rule.

**Done when:** greps match; both fields in header; both routing tables + precedence
+ fallbacks present; Step 2 addendum present; full tier labels relocated here.

---

### T2: Add checks #22–#26 + FINALIZE stacking to `outline-phase2-playbook.md`

**Depends on:** T1 (soft — checks reference the fields/tables T1 defines; citation-ordering)
**Touches:** `references/playbooks/outline-phase2-playbook.md`
**Mode:** goal-based check

> **Source discipline:** use RFC-0002 §File 4 (RFC lines ~178–221) verbatim for the
> five check rows and the FINALIZE stacking + worked examples.

**Tests:**
- `grep -c "^| 2[2-6] " references/playbooks/outline-phase2-playbook.md` returns 5 (rows #22–#26).
- `grep "密度上限（高层受众）\|独立摘要页\|决策请求格式\|证据具体性\|呼吸页独立可读" references/playbooks/outline-phase2-playbook.md` — all five check titles present.
- `grep "reference.*豁免\|豁免.*reference\|叙事范式 ≠ reference" references/playbooks/outline-phase2-playbook.md` — check #22 reference exemption.
- `grep "≥ 10\|>= 10\|总页数.*10" references/playbooks/outline-phase2-playbook.md` — check #23 ≥10-page threshold.
- `grep "manual_audit_mode" references/playbooks/outline-phase2-playbook.md` — check #26 gated branching.
- `grep "26项\|26 项" references/playbooks/outline-phase2-playbook.md` — heading updated.
- `grep "21项门禁\|（21项，按叙事范式适用）" references/playbooks/outline-phase2-playbook.md` returns 0 — old heading gone.
- `grep "pyramid + exec + live\|reference + exec\|受众层级补充\|消费模式补充" references/playbooks/outline-phase2-playbook.md` — FINALIZE stacking rows + worked examples.
- `grep "受众层级.*缺失\|缺失.*leadership\|消费模式.*缺失\|#26 跳过" references/playbooks/outline-phase2-playbook.md` — FINALIZE carries the pre-RFC-absent defaults line (absent `受众层级` → `leadership`; absent `消费模式` → #26 skips).

**Approach:**
1. Append rows #22–#26 to the `## 自审检查清单` table after check #21 (line 44),
   verbatim from RFC §File 4 (4-column shape: `# | 检查项 | 适用条件+严苛标准 |
   不通过的处理方式` — match the existing table's column structure; the RFC's 5-column
   layout folds 适用条件 into 检查项/严苛标准 to fit).
2. Update the `## 自审检查清单（21项，按叙事范式适用）` heading (line 18) to
   `（26项，按叙事范式与受众/消费模式适用）` and adjust the intro sentence (line 20) if it
   names a count.
3. In `## FINALIZE 签名契约`'s `适用检查速查` block (lines 59–65), add the
   受众层级/消费模式 stacking rows and the worked-example count lines from RFC §File 4
   (including `reference + exec` = 8 items and the pre-RFC-absent line). Annotate
   every #23-inclusive worked example with its `总页数 ≥ 10` precondition — RFC §File 4's
   examples omit it, but check #23 fires only at ≥10 pages, so the count is
   page-conditional (a <10-page exec pyramid deck applies 14, not 15).

**Done when:** greps match; five new rows; heading says 26; FINALIZE stacking +
worked examples present, #23-inclusive examples carry the `≥10 页` precondition, and
counts are arithmetically correct; checks #1–#21 untouched.

---

### T3: Lean `受众层级` reference in `tpl-interview.md`

**Depends on:** T1 (soft — points to T1's routing table), T5 (hard — added bytes fail smoke until caps rise)
**Touches:** `references/prompts/tpl-interview.md`
**Mode:** goal-based check + byte-budget

**Tests:**
- `grep "受众层级" references/prompts/tpl-interview.md` hits the new reference.
- `grep "exec\|leadership\|team\|mixed" references/prompts/tpl-interview.md` — four tiers named.
- `grep "outline-phase1-playbook\|路由表\|Step 2\|短路" references/prompts/tpl-interview.md` — points to File 3 for full detail; names derivation/short-circuit.
- `git diff origin/main -- references/prompts/tpl-interview.md` shows no change to the `字段归一化映射` table or the mandatory-anchor list.
- Byte budget: structured render `< 11000 B`, text render `< 13000 B`.

**Approach:** After the `core_audience` bullet (line 19), add this **pinned** lean
`受众层级` reference (measured at 436 B; renders structured 9795 / text 11870 B — the
implementer starts from this exact text, adjusting only if a grep or wording review
requires, then re-measures):

```text
  - 受众层级参考（`受众层级` 由大纲 Agent 在 Step 2 据 `playbooks/outline-phase1-playbook.md` 受众路由表从本字段派生，不额外询问用户；结构化 UI 模式下用户直接选层级，Step 2 短路）：`exec`（治理/资本决策权）· `leadership`（职能决策权）· `team`（执行交付层）· `mixed`（跨层级同场）。判定按决策权结构而非职级，完整口径见路由表。
```

It names the four tiers with a one-phrase authority gloss each, marks the field
derived at Step 2 (not asked), notes the structured-UI short-circuit, and points to
File 3 for the full 口径 rather than restating it.

**Done when:** greps match; anchor mapping + anchor list unchanged; both prompts
render under the raised caps (re-measure after the edit).

---

### T4: Tier enum options in `module-structured-interview-ui.md`

**Depends on:** T5 (hard — added bytes fail smoke until caps rise); T1 (soft — token semantics defined by T1)
**Touches:** `references/prompts/module-structured-interview-ui.md`
**Mode:** goal-based check + byte-budget

**Tests:**
- `grep "exec\|leadership\|team\|mixed" references/prompts/module-structured-interview-ui.md` — tier options present.
- `grep "其他\|自定义" references/prompts/module-structured-interview-ui.md` — escape hatch present.
- `grep "裸 token\|audience\|归一化" references/prompts/module-structured-interview-ui.md` — bare-token normalization note.
- Byte budget: structured render `< 11000 B`.

**Approach:** Add this tier-enum block. The minimal core is the 6-line option list
below (~382 B); the shipped block wraps it with a `## core_audience 受众层级选项（单选）`
heading and a one-paragraph normalization note (bare-token → Step 2 short-circuit;
"其他" → prose fallback), landing ~700 B and rendering the structured prompt at
**10113 B (< 11000, 887 B headroom)**:

```text
`core_audience` 单选选项 = 受众层级（落盘写入 `audience` 裸 token）：
- `exec` — C-suite / 董事会 / 投资决策方（治理与资本决策权）
- `leadership` — VP / 总监 / 职能负责人（功能层决策者）
- `team` — 业务 / 技术 / 执行团队（交付层）
- `mixed` — exec + 下属同场 / 跨层级受众
- 其他（自定义描述）
```

Selecting a tier normalizes `audience` to that bare token (recognized as
authoritative by Step 2's short-circuit); "其他" falls back to prose.

**Done when:** greps match; structured prompt renders `< 11000 B` (re-measure).

---

### T5: Raise interview-prompt byte caps in `smoke_skill.py`

**Depends on:** none (task-zero for T3/T4)
**Touches:** `scripts/smoke_skill.py`
**Mode:** goal-based check

**Tests:**
- `grep -n "assert_max_bytes(label, rendered, 11000" scripts/smoke_skill.py` — structured cap raised.
- `grep -n "assert_max_bytes(label, rendered, 13000" scripts/smoke_skill.py` — text cap raised.
- `grep -n "9000\|11500" scripts/smoke_skill.py` — the two old interview-cap literals gone (verify no other budget shares those literals before editing).
- `python scripts/smoke_skill.py` exits 0.

**Approach:** Change the `assert_max_bytes(...)` third argument at line 1739
(`9000`→`11000`, `prompt-interview-structured`) and line 1753 (`11500`→`13000`,
`prompt-interview-text`). No other change. (At this point the prompts still render
at 8977 / 11434 B, well under the raised caps; the margin is consumed by T3/T4.)

**Done when:** the two greps for the raised values match; smoke exits 0; diff shows
only the two constants changed.

---

### T6: Cross-file consistency + full-gates verification

**Depends on:** T1, T2, T3, T4, T5
**Touches:** none (read-only)
**Mode:** manual QA / goal-based

**Tests:**
- Tier set (`exec / leadership / team / mixed`) and mode set (`live / pre-read /
  async`) identical wherever each appears as a complete set across the four
  reference files.
- FINALIZE worked-example counts arithmetically match check numbering (e.g.
  `pyramid + exec + live` = #1–12 + #22–24 = 15 **at ≥10 pages**; `reference + exec`
  = 8), and every #23-inclusive example states its `≥10 页` precondition (#23 is
  page-gated, so a <10-page exec pyramid deck applies 14 — the check must not read
  as unconditional).
- `git diff origin/main -- references/playbooks/outline-phase2-playbook.md` — no
  change inside rows #1–#21.
- `git diff origin/main -- scripts/contract_validator.py` — empty.
- Byte budget: structured `< 11000 B`, text `< 13000 B` (final render).
- `python scripts/smoke_skill.py && python scripts/check_skill.py && python
  scripts/lint_diagram_recipes.py && python scripts/smoke_test.py` all exit 0.

**Approach:** Cross-file read confirming value-set agreement, orthogonality (check
#22 is the only cross-archetype gate; #23–#25 persuasion-scoped; #26 on `消费模式`),
backward-compat defaults documented, and #1–#21 non-modification via `git diff`. Run
all four gates. Render both prompts and confirm they clear the raised caps. Surface
if any gate fails for an unexplained reason.

**Done when:** all consistency checks pass; both prompts under caps; all four gates
exit 0.

## Rollout

Pure reference-document change plus two integer constants in a test gate. No flag,
no infra, no migration, no external systems. Reversible by revert. No existing
generated outlines are invalidated (new checks apply only to outlines carrying
`受众层级` / `消费模式`; absent `受众层级` → `leadership`, absent `消费模式` → #26 skips).

Deployment sequencing: T5 (raise caps) and T1 (routing source) first — T5 unblocks
the byte budget for T3/T4, T1 is the source the others cite — then T2 (checks), T3
(shared core), T4 (structured module), then T6 (verification). All land in a single
PR. The fifth file (`smoke_skill.py`) and the File 1-lean / File 3-relocation
deviation are recorded in the spec's scope note (the RFC body stays frozen).

## Risks

- **Byte-budget regression.** The whole reason the RFC's literal change couldn't
  ship; both prompts are ~99% full. Mitigation: T5 raises caps first; T3/T4 carry a
  render-and-measure `Done when:`; T6 re-renders. If the lean content still
  overflows the even 11000/13000 caps, surface — do not silently trim existing
  prose (Boundaries §Ask-first).
- **Accidental check #1–#21 modification.** T2 edits the same table. Mitigation: T6
  `git diff` confirms no change inside #1–#21; only additions after #21.
- **FINALIZE stacking arithmetic error.** Three-layered table (叙事范式 × 受众 ×
  消费模式) with worked examples. Mitigation: T6 recomputes every worked-example count
  against actual numbering.
- **Value-set drift.** A file lists three tiers where another lists four, or `async`
  missing. Mitigation: T6 cross-file value-set grep.
- **Column-shape mismatch in check table.** The existing table is 4-column; RFC
  §File 4 presents checks in a 5-column layout (适用条件 broken out). Mitigation: T2
  folds 适用条件 into the 检查项/严苛标准 cells to match the existing 4-column shape,
  not a new column.
- **`smoke_skill.py` literal collision.** If `9000` or `11500` appears elsewhere in
  the file as a different budget, a blind edit could hit the wrong line.
  Mitigation: T5 edits by line number (1739 / 1753) and confirms via a targeted
  grep that only the two interview asserts changed.

## Changelog

- 2026-07-10: initial plan. Records the Option A+B resolution of the RFC-vs-gate
  byte-budget conflict (caps → 11000/13000; File 1 lean, detail relocated to File 3;
  fifth file `smoke_skill.py`).
- 2026-07-10: adversarial review round 1 applied. Caps revised 10000/12000 → 11000/13000
  (headroom raised to >1 KB per maintainer). Dropped the frozen-RFC-erratum directive
  (Accepted RFC bodies don't change; scope note is the deviation's home). Softened the
  backward-compat Boundary to field-definition + FINALIZE (matches RFC §Migration).
  Pinned the measured lean File 1/File 2 text as concrete task targets. Annotated the
  #23-inclusive FINALIZE worked examples with their `≥10 页` precondition. Fixed T2
  line-ref (43 → 44).
