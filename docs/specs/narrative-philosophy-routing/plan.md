# Plan: narrative philosophy routing (RFC-0001)

- **Spec:** [`spec.md`](spec.md)
- **Status:** Drafting

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Three LLM-consumed reference documents gain coordinated edits; the fourth gate
artifact (code/prompt validation) is untouched. The strategy is
`narrative-arc.md` first (T1) because the routing table it gains is the canonical
source the playbooks reference — both playbook tasks (T2, T3) need the routing
table's seven values and tier structure to exist before they can consistently cite
it. T2 and T3 are then independent (different files, no shared edits) and run
sequentially in a single-agent pass. T4 is a read-only consistency lint that
confirms all three files agree and the gate tests stay green.

The riskiest part is the Phase 2 check table edit in T3: one row is updated (#9)
and twelve new rows are added (#10–#21), the checklist header must reflect 21 total
items, the FINALIZE contract block must be replaced with the per-archetype
conditional, and no existing check #1–#8 must be accidentally modified. The plan defends against this with per-task
grep-based `Done when:` tests and a final cross-file consistency check (T4).

All changes are reversible by revert (LLM-consumed docs only; no data migration, no
validator code change). No flag, no infra, no external systems.

## Constraints

- RFC-0001 (`docs/rfc/0001-narrative-philosophy-routing.md`) — all design decisions
  D1–D8 accepted; exact check wording, field formats, and FINALIZE table taken from
  RFC §Proposal.
- Related shipped specs in `docs/specs/reference-runbook-archetype/` and
  `docs/specs/skill-effectiveness-hardening/` — neither is re-opened; reference
  archetype validator code is not touched.
- Backward-compat default: pre-RFC outlines lacking `叙事范式` are treated as `pyramid`
  by Phase 2 checks — this default must be documented in each conditioned check.

## Construction tests

Goal-based greps per task (see Tasks).

**Cross-cutting consistency (T4):**
- `grep -n "叙事范式" references/principles/narrative-arc.md references/playbooks/outline-phase1-playbook.md references/playbooks/outline-phase2-playbook.md` — all three files mention the field.
- Enumerate all seven values (`pyramid`, `sparkline`, `hybrid`, `reference`, `status`, `facilitation`, `informational`) in each file's routing context and confirm they match.
- Count check rows in `outline-phase2-playbook.md` table (should be 21); confirm FINALIZE conditional references `21`.

**Gate non-regression (T4):**
- `python scripts/smoke_test.py && python scripts/lint_diagram_recipes.py && python scripts/check_skill.py` stay green (reference doc edits don't touch code or prompts).

## Design (LLD)

### Design decisions

- **`叙事范式` is derived, not asked.** The outline agent writes it during Step 2 by
  reading the routing table — no new interview field. This mirrors how `论证策略` (also
  agent-derived at outline time) works. Traces to: AC (File 2, field description).
- **Bifurcated fallback, not silent single default.** The agent explicitly decides
  between `pyramid` (persuasion goal apparent) and `informational` (no persuasion goal)
  and documents its reasoning in the field value. Traces to: AC (File 1, fallback rows;
  File 2, field description).
- **Reference archetype routing table entry only.** The `reference` row in the routing
  table is a docs-only pointer to the existing `reference_runbook` code path. No
  validator code changes. Traces to: Boundaries (never do list).
- **Check #9 field-name normalization only.** The `core_thesis` → `核心论点` rename
  aligns with the outline schema field name. The check's intent is unchanged. Traces
  to: AC (File 3, check #9).
- **FINALIZE corrects pre-existing off-by-two.** The current "7 项" is wrong (correct
  count before this RFC was 9). The new conditional FINALIZE is also the opportunity
  to fix this. Traces to: AC (File 3, FINALIZE).

### Behavior & rules

- Checks #9–#12 gate on `叙事范式 ∈ {pyramid | sparkline | hybrid}`.
- Checks #13–#15 gate on `叙事范式: status`.
- Checks #16–#18 gate on `叙事范式: facilitation`.
- Checks #19–#21 gate on `叙事范式: informational`.
- Check #11 has an additional gate: `论证策略 ∈ {narrative_driven | data_driven}` on the Part.
- Absent `叙事范式` → every check treats it as `pyramid`.
- Checks #1–#8 apply to all archetypes (no change from today).

## Tasks

### T1: Add philosophy routing table to `narrative-arc.md`

**Depends on:** none
**Touches:** `references/principles/narrative-arc.md`

**Tests:**
- `grep -c "叙事范式" references/principles/narrative-arc.md` returns ≥ 5 (field name
  appears in multiple rows).
- `grep "pyramid" references/principles/narrative-arc.md` hits the routing table.
- `grep "sparkline" references/principles/narrative-arc.md` hits the routing table.
- `grep "status\|facilitation\|informational" references/principles/narrative-arc.md`
  hits all three Tier 3 rows.
- `grep "bifurcated\|说服目标\|persuasion\|无说服\|informational.*默认\|pyramid.*默认"
  references/principles/narrative-arc.md` — bifurcated fallback rows present.
- `grep "check #11\|check.*11\|门禁" references/principles/narrative-arc.md` — the
  additive note in §说服型的两条"诚实"约定 is present.
- Cover-style targeted greps (each must match at least once):
  - `grep "thesis-first\|论点.*封面\|结论先行\|直述.*论点" references/principles/narrative-arc.md`
    — Tier 1 pyramid/hybrid thesis-first cover.
  - `grep "hook-first\|张力\|tension\|悬念" references/principles/narrative-arc.md`
    — Tier 1 sparkline hook-first cover.
  - `grep "RAG\|红.黄.绿\|on-track\|偏差" references/principles/narrative-arc.md`
    — Tier 3 status RAG/verdict cover.
  - `grep "session.*objective\|会议目标\|今天希望完成" references/principles/narrative-arc.md`
    — Tier 3 facilitation session-objective cover.
  - `grep "learning.*objective\|学习目标\|After this\|完成本" references/principles/narrative-arc.md`
    — Tier 3 informational learning-objectives cover.

**Approach:**

> **Source discipline:** when copying context signals, cover/closing rules, and field
> values, use RFC §Proposal tables (RFC lines ~107–135) as the authoritative source —
> not the §routing-mechanism question prose at RFC line ~75 (which describes a stale
> four-value `叙事范式` set). The §Proposal tables have all seven values.

1. After the existing `§故事弧线` section and before `§注意力曲线`, add a new section
   with a routing table organized in three tiers:
   - **Section heading** (e.g. `## 哲学路由：应用场景与叙事范式`).
   - **Preamble**: one sentence explaining the outline agent reads this table at Step 2
     to write `叙事范式` into the outline header.
   - **Tier 1 — 说服型 (Persuasion)** table with three rows: `pyramid`, `sparkline`,
     `hybrid`. Each row: `叙事结构 / context signals | 叙事范式 | Cover | Transition |
     Closing`. Copy the exact context signals and closing rules from RFC §File 1
     tables verbatim.
   - **Tier 2 — 参考型 (Reference)** table: one `reference` row. State the
     `reference_runbook` Parts requirement and the persuasion-timeline fallback note.
   - **Tier 3 — 非说服型 (Non-persuasion)** table: `status`, `facilitation`,
     `informational` rows with their cover / transition / closing conventions from RFC.
   - **Fallback table**: two rows (persuasion intent → `pyramid` with reasoning;
     non-persuasion intent → `informational` with reasoning). Explain the bifurcated
     default improves on a silent single default by having the agent read intent first.

2. In `§说服型的两条"诚实"约定`, after the two numbered items, add a note paragraph:
   > 上面两条保持指导性。Phase 2 新增强制门（check #11）：`论证策略: narrative_driven` 或
   > `data_driven` 的每个 Part 必须以至少一页 `叙事角色: close` 或 `信息姿态: 结论页`
   > 收束——此为 Phase 2 结构性要求，非写作风格建议，不是对以上两条的修改。

**Done when:** greps above all match; `narrative-arc.md` contains all 7 `叙事范式`
values and the two fallback rows; the additive note follows the two existing
guidance items in §说服型的两条"诚实"约定.

---

### T2: Update `outline-phase1-playbook.md`

**Depends on:** T1
**Touches:** `references/playbooks/outline-phase1-playbook.md`

> **Source discipline:** use RFC §File 2 (RFC lines ~152–214) as the canonical source
> for field formats, step wording, and examples. For the seven `叙事范式` values, use
> the §Proposal Tier tables (RFC lines ~107–135), not the §routing-mechanism prose at
> RFC line ~75 (which has a stale four-value set).

**Tests:**
- `grep "叙事范式" references/playbooks/outline-phase1-playbook.md` returns ≥ 3 hits
  (header field, field description, Step 2 addendum).
- `grep "pyramid / sparkline / hybrid / reference / status / facilitation / informational"
  references/playbooks/outline-phase1-playbook.md` hits the header schema field.
- `grep "并列.*一句话\|一句话.*并列" references/playbooks/outline-phase1-playbook.md` —
  bridge sentence requirement in `与上一 Part 的关系` format.
- `grep "论断句\|claim-shape\|结论页.*页目标\|页目标.*论断" references/playbooks/outline-phase1-playbook.md`
  — `页目标` claim-shape convention block is present.
- `grep "cover.*核心论点\|核心论点.*cover\|封面.*共鸣\|check #10" references/playbooks/outline-phase1-playbook.md`
  — cover-resonance requirement in Step 1.

**Approach:**

1. **Add `叙事范式` field to header schema.** In the `outline.txt` header block (after
   `叙事结构`), add:
   ```
   叙事范式：{pyramid / sparkline / hybrid / reference / status / facilitation / informational}
   ```
   Immediately below (as a field description note, not in the code block), add the
   derived-field description from RFC §File 2: agent derives at Step 2 from routing
   table; not asked of user; `reference` requires `reference_runbook` Parts; bifurcated
   fallback; pre-RFC absent = `pyramid` in Phase 2.

2. **Update Step 2 of the 5-step methodology.** At the end of step 2 ("确定 Part 数量和主题"),
   add the addendum from RFC §File 2 Step 2 change:
   > Step 2 附加：查阅 `principles/narrative-arc.md` 的哲学路由表，基于 `叙事结构` 输入、
   > `论证策略` 选值、以及 deck 的明确用途，写出 `叙事范式`（pyramid / sparkline / hybrid /
   > reference / status / facilitation / informational）。若输入不明确，先判断是否有说服目标：
   > 有则默认 `pyramid`，无则默认 `informational`；两者都要标注原因。

3. **Update `与上一 Part 的关系` format.** Replace the current format line:
   ```
   与上一 Part 的关系：{无（首Part）/ 递进 / 转折 / 因果 / 并列}
   ```
   with the bridge-sentence format from RFC §File 2 D3:
   ```
   与上一 Part 的关系：{无（首Part — first section, no predecessor）/ 递进｜转折｜因果 —
   一句话：上一 Part 建立了什么，本 Part 如何从中生长出来（递进 progressive）、转折（转折 reversal）、
   或因果推导（因果 causal）/ 并列 — 一句话："Part N 建立了[A]；本 Part 以[B]补充并行论据"
   （并列 parallel/coordinate）}
   ```
   Add the two examples from RFC (转折 example and 并列 example) below the format line.

4. **Add `页目标` claim-shape and concreteness convention.** After the existing
   `页目标` field description in the per-page schema block, add the full convention
   block from RFC §File 2 D2, including: the persuasion-deck scope, the two conditions
   (论断句 + 具体可感), the ❌ / ✅ examples, the "X 因此 Y" clarification, the
   navigation-page exemption, and the reference to check #10.

5. **Add cover-resonance requirement to Step 1.** After the existing Step 1 description
   ("提炼全局核心论点"), add the cover-resonance block from RFC §File 2 D6:
   pyramid/hybrid → cover `页目标` directly states or strongly implies `核心论点`;
   sparkline → cover sets a tension that `核心论点` resolves; references check #10
   sub-check ①.

**Done when:** greps above all match; header schema contains `叙事范式` field; Step 2
has the addendum; `与上一 Part 的关系` format requires bridge sentence with examples
(verify the 转折 example matches RFC-0001 line ~179: "Part 1 确立了现有边界防护的逻辑；Part 2
通过三个失效案例…" and the 并列 example matches RFC-0001 line ~181: "Part 1 建立了成本优势论点；
本 Part 以速度优势补充并行论据"); `页目标` convention block present with both conditions and
examples; Step 1 has cover-resonance requirement.

---

### T3: Update `outline-phase2-playbook.md`

**Depends on:** T1
**Touches:** `references/playbooks/outline-phase2-playbook.md`

**Tests:**
- `grep -c "^| [0-9]\|^| [12][0-9]" references/playbooks/outline-phase2-playbook.md`
  returns ≥ 21 (21 check rows in the table).
- `grep "核心论点" references/playbooks/outline-phase2-playbook.md` — check #9 uses
  the new field name.
- `grep "core_thesis\|灵魂论点" references/playbooks/outline-phase2-playbook.md` returns 0
  — old tokens from check #9 are gone.
- `grep "叙事范式.*pyramid.*sparkline\|pyramid.*sparkline.*叙事范式"
  references/playbooks/outline-phase2-playbook.md` — check #9/10/11/12 archetype gates.
- `grep "status" references/playbooks/outline-phase2-playbook.md` — checks #13–#15 present.
- `grep "facilitation" references/playbooks/outline-phase2-playbook.md` — checks #16–#18 present.
- `grep "informational" references/playbooks/outline-phase2-playbook.md` — checks #19–#21 present.
- `grep "21项.*叙事范式\|叙事范式.*21项\|21 项" references/playbooks/outline-phase2-playbook.md`
  — FINALIZE heading updated.
- `grep "pyramid.*12.*reference.*8\|#1–12\|#1–8" references/playbooks/outline-phase2-playbook.md`
  — FINALIZE conditional block with per-archetype counts.
- `grep "7 项\|7 项" references/playbooks/outline-phase2-playbook.md` returns 0 —
  pre-existing bug string gone.
- `grep "9 項\|9项.*检查\|这 9 项" references/playbooks/outline-phase2-playbook.md` returns 0
  — stale intro-sentence count "9 项" updated.
- `grep "pre-RFC\|absent\|缺失.*pyramid\|pyramid.*缺失\|按 pyramid" references/playbooks/outline-phase2-playbook.md`
  returns ≥ 3 — backward-compat default appears in checks #10, #11, and #12.

**Approach:**

1. **Update check #9.** In the `## 自审检查清单` table, find the check #9 row
   (currently `core_thesis` or `灵魂论点`). Replace with:
   ```
   | 9 | **核心论点**（仅 `叙事范式 ∈ {pyramid | sparkline | hybrid}`）| 整套 PPT 的
   `核心论点` 字段是否是一锤定音的核心主张？不能是"AI 需要治理"这类正确的废话——必须有角度、
   有主张、有论断。*非说服型 deck（`status`、`facilitation`、`informational`、`reference`）
   跳过此检查。* | 提纯论点。 |
   ```

2. **Add check #10.** After check #9, insert the full check #10 row from RFC §File 3
   (title-sequence readability + cover resonance), including sub-checks ① (cover
   resonance vs `核心论点`) and ② (title sequence forms assertion chain), the proxy
   limitation note, the archetype gate, and the pre-RFC absent-value default.

3. **Add check #11.** After check #10, insert check #11 (per-Part so-what close gate)
   from RFC §File 3: `narrative_driven`/`data_driven` Parts in persuasion decks must
   close with `叙事角色: close` or `信息姿态: 结论页`; that page's `页目标` must be an
   assertion; includes reference to check #2 preventing single-page Parts from
   reaching this check.

4. **Add check #12.** After check #11, insert check #12 (Rule of Three argument count)
   from RFC §File 3: persuasion deck argumentation Parts ≤ 5; fix guidance.

5. **Add checks #13–#15 (status).** After check #12, insert three rows with
   `叙事范式: status` gate from RFC §File 3: check #13 (opening verdict), check #14
   (decision log completeness), check #15 (backward→forward structure). Include the
   note that check #9 does not apply to status decks. **Do NOT include** the RFC's
   per-check sentence "For pre-RFC outlines where `叙事范式` is absent and the deck's
   purpose is status/review, treat as `status`" — the global backward-compat default
   (absent = `pyramid`, so #13–#15 never fire) is documented once in the FINALIZE
   block and in the field description; a per-check override would contradict it.

6. **Add checks #16–#18 (facilitation).** After check #15, insert three rows with
   `叙事范式: facilitation` gate from RFC §File 3: check #16 (session objective),
   check #17 (activity atomicity), check #18 (closing collection page).

7. **Add checks #19–#21 (informational).** After check #18, insert three rows with
   `叙事范式: informational` gate from RFC §File 3: check #19 (learning objectives),
   check #20 (module recap), check #21 (closing action guidance with training/onboarding
   variants).

8. **Update `## 自审检查清单` heading and intro sentence.** Change `（9项门禁）` to
   `（21项，按叙事范式适用）`. Also update the intro sentence ("必须...走完这 9 项检查") to
   reference the per-archetype applicable set instead of a fixed count — e.g. "必须在脑海里
   走完所有适用于本 deck 叙事范式的检查项（见 FINALIZE 速查）".

9. **Update FINALIZE contract.** Replace the current FINALIZE paragraph ("只有在 7 项检查…")
   with the per-archetype conditional block from RFC §File 3:
   - Change the pre-condition sentence to "所有适用于本 deck 叙事范式的检查全部自审通过".
   - Add the speed-reference table:
     ```
     适用检查速查：
       pyramid / sparkline / hybrid：#1–12（12项）
       reference：#1–8（8项）
       status：#1–8 + #13–15（11项）
       facilitation：#1–8 + #16–18（11项）
       informational：#1–8 + #19–21（11项）
       叙事范式缺失（pre-RFC 大纲）：按 pyramid 处理，#1–12（12项）
     ```

**Done when:** greps above all match; check table has 21 numbered rows; checks #9–#21
exactly match RFC §File 3 text (including archetype gates and pre-RFC defaults for
#10–#12; no per-check absent override for #13–#21); FINALIZE conditional lists all
six speed-reference rows; "7 项" and "灵魂论点" strings are absent.

---

### T3.5: Update orchestrator prompt to count-neutral wording

**Depends on:** T3
**Touches:** `references/prompts/tpl-outline-orchestrator.md`

**Tests:**
- `grep "7 项" references/prompts/tpl-outline-orchestrator.md` returns 0.
- No other line in the file is modified (only line 40 changes).

**Approach:**

1. In `references/prompts/tpl-outline-orchestrator.md` line 40, replace:
   ```
   - 禁止在编写阶段就考虑自审的 7 项检查标准
   ```
   with count-neutral wording:
   ```
   - 禁止在编写阶段就考虑阶段 2 的自审检查标准（检查项数量按 `叙事范式` 而定，见相关 playbook）
   ```

**Done when:** the grep returns 0; file diff shows only line 40 modified.

---

### T4: Cross-file consistency verification

**Depends on:** T1, T2, T3, T3.5
**Touches:** none (read-only)

**Tests:**
- All seven values (`pyramid`, `sparkline`, `hybrid`, `reference`, `status`,
  `facilitation`, `informational`) appear in all three files.
- The seven values are listed in the same canonical order whenever they appear
  as a complete set.
- FINALIZE conditional counts match: `pyramid/sparkline/hybrid` = 12 = checks #1–12;
  `reference` = 8 = checks #1–8; `status/facilitation/informational` = 11 = checks
  #1–8 + 3 archetype-specific.
- Checks #1–#8 in `outline-phase2-playbook.md` are unmodified: `git diff origin/main --
  references/playbooks/outline-phase2-playbook.md` shows no deletions or modifications
  in the lines containing checks #1–#8 (only additions after them).
- `grep "7 项" references/prompts/tpl-outline-orchestrator.md` returns 0.
- `grep "7 项" references/playbooks/style-phase2-playbook.md` returns ≥ 1 hit —
  confirming the style-checklist's own "7 项" is still present (file NOT touched).
- Gate tests still pass: `python scripts/smoke_test.py`, `python scripts/lint_diagram_recipes.py`,
  `python scripts/check_skill.py` all exit 0.

**Approach:**

1. Read all three modified files and confirm:
   - Seven `叙事范式` values present and consistent.
   - Check #9 in phase2 playbook gates on `{pyramid | sparkline | hybrid}`.
   - Checks #13–#15 gate on `status` with no per-check absent-value override
     (absent = `pyramid` global rule applies; status checks simply don't fire).
   - Checks #16–#18 gate on `facilitation`; #19–#21 on `informational`.
   - FINALIZE counts are arithmetically correct.
   - `§说服型的两条"诚实"约定` additive note is present in `narrative-arc.md` and
     does not modify the two existing numbered items.
   - Backward-compat default (absent `叙事范式` = `pyramid`) documented in checks
     #10–#12 (per RFC §Proposal; check #9 omits it by implication of its gate;
     checks #13–#21 omit it because the global default means they never fire).
2. Verify check #1–#8 non-modification via `git diff origin/main` as listed above.
3. Run gate tests. If any gate fails, identify whether a reference doc edit
   accidentally touched a code or prompt file (should not be possible — reference
   docs are not imported by the gate scripts). Surface if unexplained.

**Done when:** all cross-file consistency checks pass; gate tests exit 0.

## Rollout

Pure reference-document change. No flag, no infra, no migration, no external systems.
Reversible by revert. No existing generated outlines are invalidated (new checks only
apply to outlines with `叙事范式` set, and absent value defaults to `pyramid`).

Deployment sequencing: T1 → T2 (T2 cites the routing table) → T3 (T3's checks cite
the routing table) → T4 (consistency verification). All land in a single PR.

## Risks

- **Accidental check #1–#8 modification.** T3 edits the same table as the existing
  checks. Mitigation: T4 reads-back and confirms #1–#8 are byte-identical to pre-PR.
- **FINALIZE count arithmetic error.** The off-by-two bug in the current "7 项" suggests
  manual counting is unreliable. Mitigation: T4 cross-checks every count in the
  conditional block against the actual check numbering.
- **七值一致性漂移 (Value drift).** If one file uses 6 values (e.g. missing `hybrid`)
  and another uses 7, Phase 2 LLM behavior may differ from the routing table. Mitigation:
  T4's consistency grep catches this.
- **Bridge sentence examples drift.** The two examples in `与上一 Part 的关系` must match
  the RFC's Chinese text exactly. Mitigation: T2's approach cites the RFC directly;
  review against RFC §File 2 D3 during T4.

## Changelog

- 2026-07-10: initial plan.
