# RFC-0001: Narrative philosophy by deck type

- **Status:** Accepted
- **Author:** eugenelim
- **Approver:** eugenelim *(single-maintainer repo — self-approval at standard weight; flag for peer review before merge if a second maintainer joins)*
- **Date opened:** 2026-07-10
- **Date closed:** 2026-07-10
- **Decision weight:** standard
- **Related:** `docs/specs/reference-runbook-archetype/`, `docs/specs/skill-effectiveness-hardening/`, `docs/specs/planning-gate-mandatory/`

---

## Reviewer brief

- **Decision:** Should the skill (the multi-step LLM agent that turns a user brief into a designed slide deck) route narrative structural rules by deck type, and should selected guidance-only narrative rules be promoted to verifiable generation conventions or Phase 2 QA gates?
- **Recommended outcome:** Accept — four targeted changes across three reference files, adding one derived schema field (`叙事范式` — narrative paradigm, expanded to seven values covering the full range of deck archetypes), twelve new or updated Phase 2 checks (three per non-persuasion archetype + four persuasion-specific), two Phase 1 generation conventions (`与上一 Part 的关系` bridge sentence — the inter-section transition field — and `页目标` claim-shape — the per-slide goal field), and a `页目标` concreteness convention from the external storytelling survey.
- **Change if accepted:**
  - `references/principles/narrative-arc.md` — add philosophy routing table with `叙事结构` (the user-declared narrative structure field) → `叙事范式` mapping covering seven deck archetypes; bifurcated fallback row (persuasion intent → `pyramid`; non-persuasion intent → `informational`); generation conventions for three new non-persuasion archetypes (`status`, `facilitation`, `informational`); update so-what netline section to clarify that a new per-Part gate is being added (existing guidance items unchanged).
  - `references/playbooks/outline-phase1-playbook.md` — add `叙事范式` derived header field (7 values); `与上一 Part 的关系` extended to require a bridge sentence (including `并列` coordinate phrasing variant); `页目标` convention updated (claim-shaped + concrete language for persuasion decks); Step 2 of the 5-step methodology gains a `叙事范式` derivation task; Step 1 gains a cover-resonance requirement.
  - `references/playbooks/outline-phase2-playbook.md` — twelve new or updated checks: check #9 (`灵魂论点` — quintessential thesis check) normalized and gated on persuasion archetypes; checks #10–#12 (persuasion-only: title-sequence + cover-resonance, per-Part close gate, Rule-of-Three); checks #13–#15 (`status`-only: opening verdict, decision-log completeness, backward→forward structure); checks #16–#18 (`facilitation`-only: session objective stated, activity atomicity, capture slide present); checks #19–#21 (`informational`-only: learning objectives stated, module recaps, closing actions). FINALIZE contract updated to a conditional: "all applicable checks for this deck's `叙事范式`" with a per-archetype reference table *(note: FINALIZE currently mis-states "7 項" — a pre-existing off-by-two bug; correct current count is 9; this RFC corrects the bug and adds 12 new/updated checks for a total of 21)*.
- **Affected surface:** `references/principles/narrative-arc.md`, `references/playbooks/outline-phase1-playbook.md`, `references/playbooks/outline-phase2-playbook.md`.
- **Stakes:** Reversible. All three files are LLM-consumed reference documents, not code. Roll back by reverting the files; no existing generated output is invalidated.
- **Review focus:** (1) Whether the three new non-persuasion archetypes (`status`, `facilitation`, `informational`) are correctly scoped — especially that the `status`/`facilitation`/`informational` checks don't fire on persuasion decks that happen to share structural patterns. (2) Whether the bifurcated fallback (agent decides between `pyramid` and `informational` based on intent) is more reliable than a simple `pyramid` default. (3) Whether the new non-persuasion checks are verifiable at outline-time or require content inspection (any that require content inspection should be downgraded to conventions).
- **Not in scope:** Changing `叙事结构` to a closed enum in the interview; new Step 0/1 interview questions; changes to the planning phase (Step 4) or HTML rendering pipeline; mandating a specific philosophy for any deck type.

---

## The ask

**Recommendation (BLUF — Bottom Line Up Front):** Introduce a `叙事范式` derived field (7 values, written by the outline agent at Step 2, not asked of the user), add a full archetype routing table to `narrative-arc.md`, tighten two Phase 1 schema rules, add twelve Phase 2 checks covering all seven archetypes, and update the FINALIZE contract to a per-archetype conditional.

**Why now (SCQA — Situation-Complication-Question-Answer, the four-step analytical framing used throughout this RFC):**

- **Situation:** The skill (the multi-step LLM pipeline that converts a user brief into a designed slide deck) already documents three narrative frameworks — Pyramid/Minto (答案优先，演绎结构 — answer-first, deductive structure), SCQA, and story arc (情感弧线 — the rising-and-falling attention curve) — in `narrative-arc.md`, and collects structural intent via the `叙事结构` (narrative structure, a free-text interview field) question. The `reference_runbook` archetype (a structural mode for operational manuals that branches density rules and page types via a Part-level enum + validator code) proves that framework-conditional behavior is achievable in this codebase.
- **Complication:** Generated decks sometimes feel narratively uneven. A survey of external storytelling frameworks — Minto's *Pyramid Principle*, Duarte's *Resonate* (sparkline oscillation), Reynolds' *Presentation Zen*, and McKinsey's "Read-Through Test" consulting convention — confirms the root cause: the skill's narrative rules exist as guidance prose without structured anchors. Phase 2 QA (the outline agent's self-review step) cannot verify six narrative properties because the required fields and checks don't exist.
- **Question:** How should the skill encode narrative philosophy by deck type, and which guidance rules should become verifiable conventions or gates?

| ID | Question | Recommendation | Why | Decide by | Reviewer action |
|---|---|---|---|---|---|
| D1 | How should the skill route narrative rules by deck type, across the full range of deck archetypes (persuasion, reference, status, workshop, informational, etc.)? | **E** — add `叙事范式` derived field (7 values: `pyramid | sparkline | hybrid | reference | status | facilitation | informational`) to Phase 1 outline header, written by the outline agent from the routing table at Step 2; bifurcated fallback (agent actively decides between `pyramid` and `informational` based on intent — not a silent single-default) | Covers the full archetype space; gives Phase 2 checks a structured anchor without changing the interview; mirrors how `论证策略` (a per-Part field the agent derives — not user-declared) works; pure documentation-table routing without a structured field is unproven; previous single `pyramid` fallback incorrectly applied persuasion rules to status/workshop/onboarding decks | This review | Confirm E with 7 values and bifurcated fallback; or propose B' (close the existing `叙事结构` enum) if concerned about LLM derivation accuracy |
| D2 | Should argumentation-page `页目标` be claim-shaped and concrete? | D — convention update in `outline-phase1-playbook.md`; claim-shape is enforced by check #10; concreteness is a Phase 1 generation convention acknowledged as not independently gated by Phase 2 (see Risks — Acknowledged limitation) | A well-written `页目标` already carries both; no new field needed; concreteness as a Phase 2 gate is a follow-on concern | This review | Confirm; or propose a Phase 2 concreteness sub-check |
| D3 | Should `与上一 Part 的关系` (transition label — 递进 progressive / 转折 reversal / 因果 causal / 并列 parallel) require a bridge sentence? | B — label + one-sentence bridge for all non-首Part (non-first-section) transitions; `并列` (parallel/coordinate) transitions use a coordinate-relationship phrasing | Bridge commits the outline agent to an explicit logical or emotional through-line; the agent generates it — no user overhead | This review | Confirm, or limit to `转折`/`因果` only |
| D4 | Should Phase 2 add a title-sequence readability + cover-resonance check? | B — add check #10, gated on `叙事范式 ≠ reference` | Catches topic-label `页目标` values and cover-thesis misalignment in one check; operationalises McKinsey's "Read-Through Test" at outline time; must be archetype-gated to avoid false-positives on `reference` decks | This review | Confirm |
| D5 | Should Phase 2 add a per-Part so-what close gate? | B — add check #11, a new gate for `narrative_driven`/`data_driven` Parts | The per-Part close-page requirement does not currently exist as a gate; the two guidance-tagged conventions in `narrative-arc.md` (per-card so-what line and illustrative-data banner) are distinct and remain guidance; check #11 adds what is currently missing | This review | Confirm |
| D6 | Should `核心论点` (deck-level core thesis) anchor to the cover `页目标`? | B — Phase 1 generation rule in Step 1; verified by check #10 as a sub-check | Direct field comparison is more reliable than a genericness test; both fields are agent-authored; the check works for Pyramid (thesis stated on cover) and Duarte/sparkline (tension on cover that the thesis resolves) | This review | Confirm |
| D7 | Should a Rule of Three argument-count check be added? | B — Phase 2 check #12, gated on `叙事范式 ≠ reference` | Survey evidence [high confidence]: >5 supporting arguments signals unsynthesised thinking in both Pyramid and Duarte frameworks; must apply to `sparkline` decks as well as `pyramid`/`hybrid` | This review | Confirm |
| D8 | Should `status`, `facilitation`, and `informational` archetypes have their own Phase 2 gates? | B — three targeted checks per archetype (checks #13–#21): each addresses the primary structural failure mode for that archetype and is verifiable at outline time from schema fields | Without gates, generation conventions for non-persuasion decks are unverifiable — the same guidance-vs-gate gap this RFC addresses for persuasion decks | This review | Confirm; or flag if any check requires content inspection rather than schema-field inspection (those should remain conventions) |

---

## Problem & goals

### The guidance-vs-gate gap

The skill documents narrative structure well. `narrative-arc.md` names Pyramid, SCQA, story arc, attention curve, and `reference_runbook` archetype. Phase 2 check #8 (叙事弧线 — the existing check for `叙事角色` (narrative role — the per-page categorical field with values: cover / toc / section / evidence / comparison / process / reference / close / cta) variety and breathing pages) verifies density rhythm and role composition. But six narrative properties remain unverifiable at QA time:

1. **Transition logic.** `与上一 Part 的关系` carries a label (`递进 progressive / 转折 reversal / 因果 causal / 并列 parallel`) but no bridge sentence. A `转折` label commits to nothing; the logical thread can break invisibly.

2. **Page-level argument completion.** `页目标` is producer-intent ("this slide establishes X"). Whether the audience carries a belief from the slide is unchecked. A `页目标` like "展示 AI 安全事件的增长趋势" (shows the growth trend) states a topic, not a conclusion.

3. **Title-sequence argument.** `页目标` values can be topic labels ("AI Security Overview") rather than argument claims. Phase 2 check #8 verifies density and role variety, but not whether the sequence forms an argument a cold reader could reconstruct.

4. **Per-Part conclusions.** `narrative_driven` and `data_driven` Parts — where `论证策略` (argumentation strategy, a per-Part enum field the agent declares) sets the Part's rhetorical mode — may never reach an explicit conclusion. No gate currently enforces a closing page.

5. **Thesis-cover alignment.** `核心论点` (the deck-level core thesis, one sentence, declared in the outline header) and the cover `页目标` are independently authored. They can diverge with no check catching it.

6. **Argument count.** No check enforces the Pyramid Principle's "≤5 supporting arguments" rule. More than 5 argumentation Parts signals unsynthesised thinking in both Pyramid and Duarte frameworks; the skill generates no warning.

### Philosophy routing gap and the routing mechanism question

`narrative-arc.md` documents *what* the frameworks are but not *which applies when*, and the outline agent has no structured signal to route on. A user entering `叙事结构: 愿景叙事` implicitly commits to a Duarte-style sparkline (a deck that oscillates between current reality and an inspiring vision), but the agent has no instruction linking that pattern to hook-first covers and emotional oscillation.

The routing mechanism matters architecturally. The codebase's `reference_runbook` routing is not documentation-table routing — it is backed by a Part-level enum value (`论证策略: reference_runbook`) that `contract_validator` and `planning_validator` branch on in code. That precedent proves structured-field routing works; it does not prove that LLM-only documentation-table routing without a structured field is reliable.

This RFC proposes a middle path: the outline agent *derives* a structured `叙事范式` (narrative paradigm — four values: `pyramid | sparkline | hybrid | reference`) during Phase 1 Step 2 from the routing table, writing a machine-readable value that Phase 2 checks can then condition on — without adding a new interview question.

### Goals

- Each of the six unverifiable narrative properties has a checkable representation.
- The routing table in `narrative-arc.md` makes explicit which structural implications follow from which `叙事结构` pattern.
- The `叙事范式` derived field gives Phase 2 checks a structured anchor without exposing framework theory names to users.
- No interview changes, no new user-facing fields, no enum changes to `叙事结构`.

### Non-goals (deliberately dropped)

- **Closed enum on `叙事结构`** — *deferred, not permanently rejected.* If post-landing audits show the LLM-derived `叙事范式` field is unreliable, escalate to closing the `叙事结构` enum (see Options, B'). That path is explicitly named as the fallback.
- **New `受众类型` (audience type) interview question.** The survey identifies board vs. operational vs. pitch calibration as a genuine gap; scoped to a separate RFC (audience-type routing crosses the interview boundary this RFC explicitly avoids).
- **New `观众结论` per-page audience-conclusion field** — rejected: a claim-shaped `页目标` carries the same information.
- **Changes to Step 4 (planning phase)**, Step 0/1 (interview), or the HTML rendering pipeline.
- **Mandating a specific philosophy for any deck type.** The routing table is descriptive.

---

## Proposal

Three files change. All are LLM-consumed reference documents; the changes work by updating the instructions the outline agent follows at Phase 1 (generation) and the checks it applies at Phase 2 (self-review QA).

### File 1 — `references/principles/narrative-arc.md`

**Addition: Philosophy routing table (D1)**

After the existing framework descriptions (§金字塔原理, §SCQA, §故事弧线), add a section: "Which framework applies when — and what it implies." The outline agent reads this table during Phase 1 Step 2 and writes the `叙事范式` field in the outline header accordingly.

**Seven values, three tiers. Checks #9–#12 apply only to Tier 1 (persuasion) archetypes.**

*Tier 1 — Persuasion archetypes:*

| `叙事结构` / context signals | `叙事范式` | Cover | Transition | Closing |
|---|---|---|---|---|
| 问题->方案->效果 (Problem→Solution→Effect), 全景->聚焦->行动 (Overview→Focus→Action), 是什么->为什么->怎么做 (What→Why→How), 对比论证 (Comparative argument); **also routes here:** consulting/advisory deck, proposal/RFP response, data readout with recommendations, board governance decision item | `pyramid` | Thesis-first: cover `页目标` directly states or strongly implies `核心论点` | Bridge sentence required — logical through-line; SCQA-style bridge at Part transitions | `narrative_driven`/`data_driven` Parts must close with a page carrying `叙事角色: close` (conclusion/synthesis page) or `信息姿态: 结论页` (conclusion/argument page); deck closes with explicit decision + owner |
| 愿景叙事 (Vision narrative), 变革叙事 (Transformation narrative), 品牌叙事 (Brand narrative); **also routes here:** keynote / thought leadership deck, investor pitch (Sequoia 10-section or YC pattern), sales pitch (Challenger / old-way-new-way pattern) | `sparkline` | Hook-first: cover opens a tension or question — the audience's present-state pain, or an inspiring "what could be" — not the presenter's thesis statement | Bridge sentence required — emotional shift or contrast stated explicitly ("current reality is X; what becomes possible is Y") | `close` page names the transformed state; investor/sales variant closes with a specific quantified ask ("Invest $2M to reach [milestone] by [date]") |
| 对比论证 with Pyramid structure + visual-simplicity emphasis | `hybrid` | Thesis-first | Bridge sentence required | Same as `pyramid` |

*Tier 2 — Reference archetype (existing `reference_runbook` code path; no persuasion rules apply):*

| `叙事结构` / context signals | `叙事范式` | Cover | Transition | Closing |
|---|---|---|---|---|
| 时间线 / 生命周期 (Timeline / Lifecycle) **AND** at least one Part declares `论证策略: reference_runbook` | `reference` | Navigation-first: entity name + lifecycle period | Label only (no bridge required) | 横切参考 back-matter (cross-cutting reference appendix): RACI, escalation paths, quality gates — not a CTA |

**`reference` requires `reference_runbook` Parts.** A persuasion timeline (company history, vision roadmap) with no `reference_runbook` Parts falls to the fallback rows below.

*Tier 3 — Non-persuasion archetypes (checks #10–#12 do not apply; check #9 does not apply; checks #1–8 still apply):*

| `叙事结构` / context signals | `叙事范式` | Cover | Transition | Closing |
|---|---|---|---|---|
| 状态报告, QBR, 项目状态, 业务回顾, sprint review (Project status / Quarterly Business Review / business review / sprint review); structured around metrics, performance vs. plan, decisions, blockers | `status` | Entity + period + verdict: company/project name, reporting period, and a RAG (Red/Amber/Green traffic-light verdict) or one-sentence on-track/at-risk summary | Mandatory backward→forward structure (performance review closes before forward-look opens); blocker slides distinguish "team-managed" from "decision required"; no SCQA bridges between sections | Decision log with owners and deadlines — "Approve $80K spend by [date]" not "discuss pipeline gap" — each action item has an owner and a date |
| 工作坊, 研讨会, 共创会, 对齐会, 发现会 (Workshop / working session / co-creation / stakeholder alignment / discovery session); outcomes are co-produced, not pre-loaded | `facilitation` | Session title + shared question or objective ("What we hope to accomplish today"); not a recommendation | Verbal/conversational, not slide-level bridges; activity instruction slides are one-slide-maximum per activity (never split across slides) | Co-produced decisions + open questions + action owners captured in a closing collection slide; not a CTA |
| 培训, 入职, L&D, 流程培训, 知识转移, onboarding (Training / employee or client onboarding / L&D module / process training / knowledge transfer); content is pre-determined and builds sequentially | `informational` | Module title + learning objectives or scope ("After this session you will be able to..."); functional, not analytical | Module recap slide at each section boundary before the next module opens; each module is a discrete domain; section headers are navigation cues | First actions + key contacts (onboarding variant); assessment or knowledge check (training variant); close ensures no one leaves uncertain about "what do I do next" |

*Fallback — bifurcated explicit default:*

| Condition | `叙事范式` | How the agent applies it |
|---|---|---|
| `叙事结构` unrecognized **and** persuasion goal apparent (making a recommendation, arguing a case, convincing a stakeholder) | `pyramid` | Write `叙事范式: pyramid（默认，原因：[state why persuasion intent is apparent and why no named pattern matched]）`; apply all Tier 1 persuasion rules |
| `叙事结构` unrecognized **and** no persuasion goal (reporting, facilitating, transferring knowledge) | `informational` | Write `叙事范式: informational（默认，原因：[state why non-persuasion intent is apparent]）`; skip checks #10–#12 |

The key improvement over a silent single default: the agent reads the deck's stated purpose before choosing and documents the reasoning. A status update never silently receives pyramid checks.

Note: the `reference` value is the narrative-arc-level routing signal. The `reference_runbook` archetype is additionally backed by `contract_validator` / `planning_validator` code branches that the `论证策略: reference_runbook` Part-level enum triggers. This RFC adds only the routing table and the derived `叙事范式` field — it does not change the validator code. Phase 2 gates specific to `status`, `facilitation`, and `informational` archetypes are follow-on work.

**Update: So-what netline section — add per-Part gate note (D5)**

The existing §说服型的两条"诚实"约定 (§two guidance conventions for persuasion decks) covers two items: (1) the per-card so-what netline ("每张论证卡以一句'所以'收束" — each argument card closes with a "therefore" summary line) and (2) the illustrative-data banner (disclosure strip for illustrative numbers). **Both remain guidance-tagged.** No change to these items.

Add a note after the two items: "上面两条保持指导性。Phase 2 新增强制门（check #11）：`论证策略: narrative_driven` 或 `data_driven` 的每个 Part 必须以至少一页 `叙事角色: close` 或 `信息姿态: 结论页` 收束——此为 Phase 2 结构性要求，非写作风格建议，不是对以上两条的修改。" (The two guidance items remain. Phase 2 adds a new mandatory gate — check #11 — requiring each `narrative_driven`/`data_driven` Part to close with a conclusion page. This is a new gate, not a promotion of the existing guidance tags.)

---

### File 2 — `references/playbooks/outline-phase1-playbook.md`

**Addition: `叙事范式` derived field in outline header (D1-E)**

Add to the `outline.txt` schema header block, after `叙事结构`:

```
叙事范式：{pyramid / sparkline / hybrid / reference / status / facilitation / informational}
```

*Derived field — the outline agent selects this value at Step 2 by applying the routing table in `principles/narrative-arc.md` to the `叙事结构` input and the deck's stated purpose. Do not ask the user. `reference` requires at least one Part declaring `论证策略: reference_runbook`; `叙事结构: 时间线` alone is not sufficient. When `叙事结构` matches no clear pattern, use the bifurcated fallback: if the deck has a persuasion goal write `pyramid`; if not write `informational`. In both cases document the reasoning. Pre-RFC outlines lacking this field: Phase 2 checks treat an absent value as `pyramid`.*

**Change: Step 2 of the 5-step methodology — add `叙事范式` derivation task**

At the end of step 2 ("确定 Part 数量和主题"), add:

> *Step 2 附加：查阅 `principles/narrative-arc.md` 的哲学路由表，基于 `叙事结构` 输入、`论证策略` 选值、以及 deck 的明确用途，写出 `叙事范式`（pyramid / sparkline / hybrid / reference / status / facilitation / informational）。若输入不明确，先判断是否有说服目标：有则默认 `pyramid`，无则默认 `informational`；两者都要标注原因。*

**Change: `与上一 Part 的关系` format (D3)**

Current:
```
与上一 Part 的关系：{无（首Part）/ 递进 / 转折 / 因果 / 并列}
```

New:
```
与上一 Part 的关系：{无（首Part — first section, no predecessor）/ 递进｜转折｜因果 — 一句话：上一 Part 建立了什么，本 Part 如何从中生长出来（递进 progressive）、转折（转折 reversal）、或因果推导（因果 causal）/ 并列 — 一句话："Part N 建立了[A]；本 Part 以[B]补充并行论据" （并列 parallel/coordinate）}
```

Example `转折`: `转折 — Part 1 确立了现有边界防护的逻辑；Part 2 通过三个失效案例论证边界模型对 AI 辅助内部攻击无效。`

Example `并列`: `并列 — Part 1 建立了成本优势论点；本 Part 以速度优势补充并行论据。`

`首Part` retains `无`. Bridge sentence is generated by the outline agent.

**Change: `页目标` claim-shape and concreteness convention (D2)**

Add to the per-page schema description block:

> **说服型 deck 论证页的 `页目标` 规则（`叙事范式: pyramid | sparkline | hybrid`）：**
>
> `信息姿态` (page information stance — the per-page field with values: 结论页 conclusion/argument / 解释页 explanation / 证据页 evidence / 仪表盘页 dashboard / 呼吸页 breathing/rest) 为 `结论页 / 解释页 / 证据页` 的页面，`页目标` 必须同时满足两个条件：
>
> 1. **论断句** — 从观众视角陈述这一页让观众相信什么，而非从制作者视角陈述这一页"展示了"什么。
> 2. **具体可感** — 使用可量化或可感知的表述，而非抽象概括。"3 倍增速"优于"显著提升"；"每位分析师节省 3 小时/周"优于"提升效率"。
>
> ❌ 描述 + 抽象（不符合）：`展示 AI 安全事件的增长趋势`
> ✅ 论断 + 具体（符合）：`2023 年以来 AI 安全事件增速比传统安全事件快 3 倍，威胁已不可忽视`
>
> **"X 因此 Y" 澄清：** 论断句可以是"前提 + 推论"格式（"X 因此 Y"），这视为单一论断，不违反"一页一目标、禁含'和'"规则。违禁的是两个并列目标（"X 和 Y"）。
>
> *Phase 2 check #10 verifies claim-shape (论断句 vs. 主题标签 topic-label). The concreteness requirement is a Phase 1 generation convention; Phase 2 does not independently gate on concreteness — see Risks (Acknowledged limitation).*
>
> 导航页（`cover / section / toc / end`）不受此约束。

**Change: Step 1 (提炼全局核心论点 — extract global core thesis) — cover resonance requirement (D6)**

Add to step 1:

> 说服型 deck（`叙事范式: pyramid | sparkline | hybrid`）的封面 `页目标` 必须与 `核心论点` (core thesis) 形成强共鸣：
>
> - **Pyramid / hybrid 模式：** 封面 `页目标` 直述或高度浓缩 `核心论点`。读者仅凭封面即可感知全篇核心主张。
> - **Sparkline 模式：** 封面可用张力句或激发式问句，但必须与 `核心论点` 形成因果呼应 — 封面设置的悬念，正是 `核心论点` 所解答的。
>
> Phase 2 check #10 sub-check ① 会对照封面 `页目标` 与 `核心论点` 两个字段来验证。

---

### File 3 — `references/playbooks/outline-phase2-playbook.md`

**Update: Check #9 — normalize field name and gate to persuasion archetypes**

Change `core_thesis` to `核心论点`; add archetype gate. *Applies only when `叙事范式 ∈ {pyramid | sparkline | hybrid}`. Non-persuasion decks (`status`, `facilitation`, `informational`, `reference`) do not have a persuasion thesis; skip this check for those values.*

| 9 | **核心论点**（仅 `叙事范式 ∈ {pyramid | sparkline | hybrid}`）| 整套 PPT 的 `核心论点` 字段是否是一锤定音的核心主张？不能是"AI 需要治理"这类正确的废话——必须有角度、有主张、有论断。 | 提纯论点。 |

**Add: Check #10 — title-sequence readability + cover resonance (D4 + D6)**

*Applies only when `叙事范式 ∈ {pyramid | sparkline | hybrid}`. For pre-RFC outlines where `叙事范式` is absent, treat as `pyramid`.*

| 10 | **标题叙事序列**（仅 `叙事范式 ∈ {pyramid \| sparkline \| hybrid}`）| **① 封面共鸣：** 封面 `页目标` 是否与 `核心论点` 直接呼应（pyramid/hybrid 直述论点，sparkline 设置论点所解答的悬念）？若两者彼此独立、读完封面感知不到论点的影子，则未通过。**② 全序列论断链：** 仅朗读所有论证页（`信息姿态: 结论页/解释页/证据页`）的 `页目标`：拼在一起能否让从未见过本 deck 的陌生人感知到论证链？`页目标` 是论断句（"X 因此 Y"），不是主题标签（"AI 安全概述"）？ | 封面共鸣不足：重写封面 `页目标`；论断链缺失：将描述性标签改写为论断句；逻辑链断裂：检查 Part 之间的衔接。 |

*Note: `页目标` is an outline-time proxy for the eventual rendered slide title. Full Read-Through guarantee requires Step 4 planning to preserve `页目标` content in the slide title — a Step 4 concern, not verified here.*

**Add: Check #11 — per-Part so-what close gate (D5)**

*Applies to Parts where `论证策略: narrative_driven` or `data_driven` AND `叙事范式 ∈ {pyramid | sparkline | hybrid}`. For pre-RFC outlines where `叙事范式` is absent, treat as `pyramid`.*

| 11 | **结论收束（叙事型 Part，仅说服型 deck）** | `论证策略: narrative_driven` 或 `data_driven` 的每个 Part 是否至少有一页 `叙事角色: close` (conclusion/synthesis page) 或 `信息姿态: 结论页`？该页的 `页目标` 是否是论断句？ | 补充结论收束页；或将 Part 末页改写为论断型收束。 |

*Note: check #2 (每 Part ≥ 2 页) already prevents single-page Parts from reaching this check.*

**Add: Check #12 — Rule of Three argument count (D7)**

*Applies when `叙事范式 ∈ {pyramid | sparkline | hybrid}`. For pre-RFC outlines where `叙事范式` is absent, treat as `pyramid`.*

| 12 | **论证部 Part 数量**（仅 `叙事范式 ∈ {pyramid \| sparkline \| hybrid}`）| 说服型 deck（pyramid / sparkline / hybrid）中 `论证策略` 为 `narrative_driven / data_driven / case_study / comparison / framework / step_by_step / authority` 的 Part 数量是否 ≤ 5？Pyramid 和 Duarte 框架均指出超过 5 个论证单元通常意味着思维尚未充分提炼（Duarte 框架中，多个重复震荡而非合并成一条高频弧线是相同的信号）。 | 合并逻辑相近的 Part；或增加一个更高层的统领论点再在其下分组。 |

**Add: Checks #13–#15 — `status` archetype gates (D8)**

*Apply only when `叙事范式: status`. For pre-RFC outlines where `叙事范式` is absent and the deck's purpose is status/review, treat as `status`.*

| 13 | **状态裁决（status deck 开篇）**（仅 `叙事范式: status`）| 大纲前 2 页是否有明确的状态裁决？裁决须含：（a）RAG 信号（绿/黄/红，或"整体符合预期 / 部分偏差 / 需要干预"之类等价表述）和（b）1–2 句说明核心状态。仅有报告名称（如"Q3 QBR"）或指标列表的封面未通过。 | 在封面或第 2 页补写状态裁决句。示例：`Q3 整体偏差：收入完成率 92%，Q4 管道不足，需本次批准追加预算。` |
| 14 | **决策日志完整性（status deck 收尾）**（仅 `叙事范式: status`）| 大纲收尾部分是否包含至少 1 项结构化决策条目，格式为"[决策内容] → [Owner] → [截止日期]"？模糊的"下步待议"不通过；决策须具体、有人负责、有期限。 | 将每个 blocker 或行动项改写为决策条目格式；若本次 review 无需决策则明确标注"本次无待批决策"。 |
| 15 | **回顾→前瞻结构（status deck 结构序）**（仅 `叙事范式: status`）| 大纲是否先有一个"回顾区块"（业绩 vs 计划、已完成项）再有一个"前瞻区块"（下期优先级、承诺）？仅有回顾、缺少前瞻的 status deck 是报告而非 review。 | 补充"下期优先级"或"下阶段承诺"区块，置于回顾区块之后。 |

*Note: check #9 (`核心论点`) does not apply to `status` decks — a status deck has a verdict (`叙事角色: cover` page's `页目标`), not a persuasion thesis. Check #13 gates the equivalent structural requirement.*

**Add: Checks #16–#18 — `facilitation` archetype gates (D8)**

*Apply only when `叙事范式: facilitation`.*

| 16 | **会议目标声明（facilitation deck 开篇）**（仅 `叙事范式: facilitation`）| 大纲前 2 页是否明确声明了会议目标或"今天希望完成什么"？仅有会议名称（如"产品对齐工作坊"）未通过。目标须可验证：会议结束后，参与者应该知道或决定了什么？ | 在开篇页补写会议目标。示例：`今天的目标：就 Q4 产品优先级达成共识，确定 3 项核心功能和 1 名 Owner。` |
| 17 | **活动页原子性（facilitation deck 活动指令）**（仅 `叙事范式: facilitation`）| 每项活动的指令是否在单页内完整呈现？若同一活动的指令跨多页（如"活动 A — 第 1 步"接"活动 A — 第 2 步"分拆为两页），主持人将无法流畅引导。以活动名称 / 活动编号为粒度检查：每项活动只能对应 1 页指令页。 | 将跨页的活动指令合并到单页；若内容过多，精简指令或拆分为两项独立活动。 |
| 18 | **收尾收集页（facilitation deck 收尾）**（仅 `叙事范式: facilitation`）| 大纲末尾是否有专门的收集页（`叙事角色: close` 或等效），用于记录：已达成决策、未决问题、行动项及 Owner？工作坊若无收集机制，产出无法沉淀。 | 在大纲末尾加入收集页；页目标示例：`记录今天达成的决策、未决问题及 Owner。` |

**Add: Checks #19–#21 — `informational` archetype gates (D8)**

*Apply only when `叙事范式: informational`.*

| 19 | **学习目标声明（informational deck 开篇）**（仅 `叙事范式: informational`）| 大纲开篇（cover 或第 2 页）是否明确列出学习目标或课程范围？目标须可验证：完成本材料后，学员应能做什么或知道什么？仅有模块名称（如"新员工入职"）未通过。 | 补写学习目标。示例：`完成本入职材料后，你将了解：组织架构、工具权限申请流程、第一周行程安排。` |
| 20 | **模块收束页（informational deck 模块过渡）**（仅 `叙事范式: informational`）| 每个模块（Part）结束前是否至少有 1 页收束页（`叙事角色: close` 或知识回顾页），在下一模块开启前总结本模块要点？类似说服型的 check #11，但收束页内容是知识摘要而非论断句——`页目标` 可以是"回顾本模块三个要点：…"而非主张句。 | 在每个模块末尾加入要点回顾页。 |
| 21 | **收尾行动指引（informational deck 收尾）**（仅 `叙事范式: informational`）| 大纲收尾是否提供明确的后续行动？根据类型：培训变体 — 知识测验或实践任务；入职变体 — 第一周行动清单 + 各职能关键联系人。仅有"感谢参与"页或纯致谢结尾未通过。 | 补充行动指引页；入职示例：`第一天行动：申请系统权限 → 与直属 Manager 确认第一周计划 → 加入团队 Slack 频道。` |

**Update: FINALIZE contract — variable-count conditional**

Replace the current fixed-count FINALIZE with a conditional form:

- Change checklist header: `## 自审检查清单（9项门禁）` → `## 自审检查清单（21项，按叙事范式适用）`
- Replace FINALIZE contract line with:

```
只有在所有适用于本 deck 叙事范式的检查全部自审通过后，才允许在文件末尾追加签名。
适用检查速查：
  pyramid / sparkline / hybrid：#1–12（12项）
  reference：#1–8（8项）
  status：#1–8 + #13–15（11项）
  facilitation：#1–8 + #16–18（11项）
  informational：#1–8 + #19–21（11项）
  叙事范式缺失（pre-RFC 大纲）：按 pyramid 处理，#1–12（12项）
```

*(The current "7 項" in the FINALIZE is a pre-existing off-by-two bug — the correct count before this RFC was 9. This change corrects the pre-existing error and makes the count archetype-conditional.)*

---

### Migration

No existing generated outlines are invalidated. The new requirements apply to new outline runs only.

The `叙事范式` field is new; pre-RFC outlines lack it. Phase 2 checks conditioned on `叙事范式` treat an absent value as `pyramid` (default). This backward-compatibility default is documented in each check above.

---

## Options considered

### D1 axis: depth and mechanism of narrative routing

*Axis: what mechanism routes narrative structural behavior — and how reliably.*

| Option | Mechanism | Cost | Reliability | Verdict |
|---|---|---|---|---|
| **A. Do nothing** | None | Zero | N/A | Rejected: guidance gap persists |
| **B'. Close existing `叙事结构` enum** | Interview-level; remove the `其他` escape hatch from `叙事结构`; routing table remains for `叙事范式` derivation from structured input | Removes user flexibility in `叙事结构`; no theory names exposed to users | Higher than E for persuasion decks: structured input eliminates the fallback ambiguity; but doesn't help for non-persuasion deck types (status/workshop/onboarding) which would still need routing logic | *Deferred escalation path*: if quality audits show E produces wrong `叙事范式` values in ≥20% of persuasion-deck runs, close the enum for persuasion patterns |
| **C. New `受众类型` interview question** | Interview-level; user selects audience type | New interview question; crosses boundary this RFC avoids | High | Deferred to audience-type RFC |
| **D. Documentation table only** | LLM reads table, behavior implicit; no structured field written | Zero schema cost | Unproven: `reference_runbook` routing works via enum + validator code, not LLM table-reading | Rejected |
| **E. Derived `叙事范式` field, 7 values, bifurcated fallback (chosen)** | Outline agent derives and writes a structured value at Step 2 by reading the routing table and the deck's stated purpose; bifurcated fallback (persuasion intent → `pyramid`, non-persuasion intent → `informational`) replaces silent single default; Phase 2 checks key on the field | One new outline header field, 7 values | Covers the full archetype space — including non-persuasion decks that the previous 4-value design would have incorrectly defaulted to `pyramid`. `论证策略` — the Part-level analog — is *also* agent-derived at outline time, confirming the pattern works | **Chosen** |

### D2 axis: where audience-belief is encoded

- **New `观众结论` per-page field** — rejected: duplicates a well-written `页目标`.
- **Convention reform of `页目标` (chosen)** — zero schema cost; claim-shape verified by check #10; concreteness is a Phase 1 convention with acknowledged limitation (see Risks).
- **Do nothing** — rejected: topic-label `页目标` is the root cause of title sequences that don't form arguments.

### D3 axis: verbosity of transition declaration

- **Label only (current)** — `转折` with no explanation commits to nothing.
- **Label + bridge for all non-首Part (chosen)** — one sentence per transition, agent-generated; `并列` uses coordinate phrasing ("Part N 建立了[A]；本 Part 以[B]补充") to avoid forcing a false derivation narrative onto genuinely coordinate arguments.
- **Bridge only for `转折`/`因果`** — rejected: `递进` drift is also a documented failure mode.

### D5 axis: per-Part conclusion gate

- **Promote existing guidance tag** — inapplicable: the `指导性` tag in `narrative-arc.md` covers the per-card so-what netline and the illustrative-data banner. Neither is a per-Part conclusion gate. There is no per-Part conclusion paragraph to promote. Check #11 is a new gate.
- **New gate (chosen)** — adds the per-Part close-page requirement that currently doesn't exist as a structure check.
- **Per-card gate** — rejected: enforcing the per-card so-what line at outline time is premature; card content isn't written at Phase 1.

### D6 axis: cover-thesis traceability

- **Genericness/transplant test** — rejected: a specific-but-misaligned cover passes the transplant test; it doesn't detect the actual failure. Both cover `页目标` and `核心论点` are agent-authored outline fields that require no `叙事结构` parsing to compare directly.
- **Direct field comparison, sub-check in check #10 (chosen)** — check #10 sub-check ① compares cover `页目标` against `核心论点` directly. Works for pyramid (thesis stated) and sparkline (tension that thesis resolves).
- **Separate check** — would work but is unnecessary; the sub-check in check #10 keeps related title-sequence concerns together and avoids splitting the gating logic for archetype.

---

## Risks & what would make this wrong

**Pre-mortem: RFC ships, narrative flow quality doesn't improve.**

- *Most likely cause:* The outline agent derives `叙事范式` correctly but doesn't apply framework-specific conventions to `页目标`, `与上一 Part 的关系`, and cover resonance. **Mitigation:** Phase 2 checks #10, #11 catch these specifically. If quality still doesn't improve after 10+ runs, the Phase 1 generation conventions are being ignored. Escalation: promote `叙事范式` routing to Option B' (close the `叙事结构` enum) so the structured signal arrives at Phase 1 input time, not output time.

- *Second cause:* Bridge sentences (D3) become formulaic ("Part N 建立了 A; 本 Part 从 A 推导出 B") without advancing the logical thread. **Mitigation:** Check #10 sub-check ② fires if argument claims are still missing in the title sequence regardless.

**Key assumptions (falsifiable):**

1. The outline agent reliably derives `叙事范式` from the routing table for real user inputs. *Falsifiable:* generate 5 decks with `叙事结构: 愿景叙事`; if ≥2 outlines show `叙事范式: pyramid` (not `sparkline`), routing is misread → escalate to B'.

2. Direct comparison of cover `页目标` vs. `核心论点` (check #10 sub-check ①) is meaningful — the two fields are written in the same generation session and are semantically comparable. *Falsifiable:* run check #10 on 3 decks; observe whether the Phase 2 agent produces accurate pass/fail verdicts.

3. The claim-shape requirement on `页目标` (D2 item 1) is reliably caught by check #10 sub-check ②. *Falsifiable:* run Phase 2 on a deck with topic-label `页目标` values; if check #10 passes without flagging them, the claim-shape detection is failing.

**Risk — non-persuasion checks require correct `叙事范式` classification:**
Checks #13–#21 gate on `叙事范式 ∈ {status|facilitation|informational}`. If the outline agent misclassifies a persuasion deck as one of these values (e.g., assigns `status` to a strategic recommendation that uses a status-report framing), that deck would skip checks #9–#12 entirely. *Falsifiable:* if a QBR-framed strategy deck (which is a persuasion deck in disguise) passes Phase 2 without a `核心论点` check, the classification is wrong. Mitigation: check #13 (opening verdict) acts as a secondary signal — a true persuasion deck's cover will have a `核心论点`, not a RAG verdict, and a reviewer should notice the mismatch.

**Acknowledged limitation — D2 concreteness:**
The concreteness requirement ("每位分析师节省 3 小时/周" vs "提升效率") is a Phase 1 generation convention. It is *not* independently gated by Phase 2. Check #10 verifies claim-shape (assertion vs. topic label) but not concreteness (quantifiable vs. abstract). A claim like "威胁已不可忽视，形势严峻" passes check #10 despite being abstract. Promoting concreteness to a Phase 2 gate is a follow-on concern; the generation convention is the first step.

**Drawbacks:**

- `叙事范式` adds one field to every outline header. If the routing table is applied inconsistently across runs, check #10 and #12 results become inconsistent — the cost of LLM-derived routing vs. closing the enum.
- Phase 2 checklist grows from 9 to 21 items total, though each deck sees a subset (8–12 applicable checks) determined by its `叙事范式`. The FINALIZE contract's pre-existing "7 項" error is corrected in the same change; post-RFC the count is archetype-conditional.
- Bridge sentences (D3) add ~1 sentence per Part at generation time (~3–7 sentences for a typical deck).
- Check #10's proxy limitation: `页目标` ≠ rendered slide title. Full Read-Through guarantee requires Step 4 to preserve `页目标` in slide titles — a Step 4 concern explicitly out of scope here.

---

## Evidence & prior art

**De-risk:** `叙事范式` is a deck-level analog of the Part-level `论证策略` field. Crucially, `论证策略` is *also* agent-derived at outline time (not user-declared) — making the analogy for Option E stronger than originally stated. `叙事范式`'s classification is a routing table lookup from one existing field; `论证策略`'s classification is a content judgment. `叙事范式` is arguably *more* deterministic. The key difference: `reference_runbook` has downstream validator code; `叙事范式` is Phase 2 LLM checks only. That is a calculated bet on a lower-cost first step; the escalation path to B' is explicit.

**Repo precedent:**
- `docs/specs/reference-runbook-archetype/` — the archetype routing pattern (enum + validator code) this RFC moves toward at the narrative level.
- `docs/specs/skill-effectiveness-hardening/` + `docs/specs/planning-gate-mandatory/` — promoting advisory guidance to enforced conventions.
- `references/playbooks/outline-phase2-playbook.md` density-rule branching on archetype — the existing pattern for archetype-conditional Phase 2 checks that D4 follows.

**External prior art (full survey: `docs/rfc/0001-notes/slide-storytelling-survey.md`):**

*Persuasion frameworks (D1 Tier 1, D2–D7):*
- **Minto (1987), *The Pyramid Principle*** — answer-first, thesis anchored to cover → D6; Rule of Three (≤5 supporting arguments) → D7; SCQA as opening frame → D1 routing table. `[high confidence — 5+ independent sources]`
- **Duarte (2010), *Resonate*** — sparkline (oscillation between "what is" and "what could be") → D1 sparkline routing; hook-first cover for vision decks → D6; "Big Idea" single-sentence brief → D2 claim-shaped `页目标`; Rule of Three applies to sparkline too. `[moderate confidence — practitioner, retrospective validation]`
- **Reynolds (2007), *Presentation Zen*** — commit to logical bridge between sections before elaborating → D3 bridge sentences; one idea per slide → D2 concreteness. `[moderate confidence — practitioner]`
- **McKinsey "Read-Through Test"** (Slideworks, Deckary) — reading only slide titles reconstructs the argument → D4 title-sequence check. `[high confidence — practitioner consensus]`
- **Heath & Heath (2007), *Made to Stick*** — Concrete is one of the two most actionable principles for presentations → D2 concreteness extension. `[moderate confidence — practitioner consensus]`
- **Frontiers in Communication (2021), peer-reviewed** — processing fluency as the mechanism for narrative persuasion → theoretical basis for D3–D7. `[moderate confidence — single peer-reviewed study]`

*Non-persuasion archetype conventions (D1 Tier 3):*
- **Sequoia Capital pitch deck standard; Y Combinator pitch deck guidance** — investor pitch: company purpose ≤9 words on cover, 10-section completeness checklist (Problem→Solution→Why Now→Market→Competition→Product→Model→Team→Financials→Ask), closing = specific funding ask with milestone → `sparkline` routing with quantified CTA. `[very high confidence — primary sources from YC and Sequoia]`
- **Gainsight, Deckary QBR guides** — QBR: entity + period + RAG verdict on cover; closing = decision log with owners; backward→forward structure required; no SCQA bridges → `status` conventions. `[high confidence — multiple independent QBR templates]`
- **WinningPresentations, Wavetable, SessionLab** — workshop/facilitation: activity slides are one-slide-max; closing = co-produced decisions, not a CTA; facilitator navigates non-linearly → `facilitation` conventions. `[high confidence — consistent across facilitation-specific sources]`
- **SlideModel, Storydoc employee/client onboarding templates** — onboarding: cover states learning objectives; module recaps at section boundaries; closing = first actions + key contacts → `informational` conventions. `[high confidence — multiple independent onboarding templates]`
- **BrightCarbon taxonomy; Presentations.ai; Beautiful.ai template library** — no single authoritative cross-type taxonomy exists; D1's 7-value routing table is a cross-source synthesis, not a published framework. `[moderate confidence — multiple sources agree on archetype existence; structural conventions vary]`

---

## Open questions

1. **Should `叙事范式` routing also condition `密度曲线` (the deck-level density arc — a one-sentence summary of the pacing pattern, declared in the outline header) defaults by philosophy?** (e.g., `pyramid` decks → high-contrast density rhythm; `sparkline` decks → smoother oscillation.) **Recommended default:** out of scope for this RFC; `密度曲线` already handles per-deck pacing explicitly. **Owner:** RFC author/maintainer. **Decide-by:** after 30+ deck runs post-landing.

2. **Should D2 concreteness be promoted to a Phase 2 gate?** A Phase 1 convention is weaker enforcement. **Recommended default:** land the generation convention first and audit whether concreteness failures appear in practice. **Owner:** RFC author/maintainer. **Decide-by:** first quality audit post-landing.

3. **Should bridge sentences (D3) be verified by a Phase 2 check?** **Recommended default:** generation convention only for now; add a Phase 2 check if formulaic bridges persist after 10+ runs. **Owner:** RFC author/maintainer. **Decide-by:** first quality audit post-landing.

4. ~~Should `status`, `facilitation`, and `informational` archetypes get their own Phase 2 gates?~~ **Resolved in this RFC** — checks #13–#21 added (three per archetype). Open question closed.

---

## Follow-on artifacts

*(Filled in when accepted.)*

- **Spec: `docs/specs/narrative-philosophy-routing/`** — implementation spec with exact line-level edits to the three files.
- **Spec: `docs/specs/exec-summary-slide/`** — introduce an `exec-summary` `叙事角色` (narrative role) page type: a 1–2 slide standalone summary encoding the full SCQA + three supporting arguments for non-linear readers. Survey evidence [high confidence — McKinsey conventions, Duarte executive guidance]: C-suite audiences scan, interrupt, and stop reading; every executive who reads only the first two slides must have the complete argument. Currently the skill has `cover` and `section` narrative-role pages but no equivalent exec-summary type. Scope: new `叙事角色` value, Phase 1 outline rule (required for `叙事范式: pyramid | hybrid` when `total_pages ≥ 15`), and planning-phase template.
- Research evidence archived at `docs/rfc/0001-notes/slide-storytelling-survey.md`.
