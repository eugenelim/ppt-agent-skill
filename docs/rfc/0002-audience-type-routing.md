# RFC-0002: Audience-type routing

- **Status:** Accepted
- **Author:** eugenelim
- **Approver:** eugenelim *(single-maintainer repo — self-approval at standard weight; flag for peer review before merge if a second maintainer joins)*
- **Date opened:** 2026-07-10
- **Date closed:** 2026-07-10
- **Decision weight:** standard
- **Related:** `docs/rfc/0001-narrative-philosophy-routing.md` (RFC-0001 — introduced `叙事范式`, the 7-value deck-archetype field, and explicitly deferred `受众类型` to this RFC)

---

## Reviewer brief

- **Decision:** Should the skill add two derived outline fields — `受众层级` (audience tier: the decision-making authority level of the target audience) and `消费模式` (consumption mode: whether the deck is consumed live with a presenter, read independently before the meeting, or used as async reference) — and add five Phase 2 QA checks gated on these two dimensions?
- **Recommended outcome:** Accept — two new derived outline header fields (`受众层级` 4 values, `消费模式` 3 values), enhanced `core_audience` interview prompting (2 files; no new interview anchor — interview anchors are named fields in `interview-qa.txt`, validated by `contract_validator.py` before the pipeline starts), and 5 new Phase 2 checks (22–26; Phase 2 is the post-outline QA self-review loop defined in `outline-phase2-playbook.md`) that condition on these fields orthogonally to the 7-value `叙事范式` (narrative paradigm — deck archetype) introduced by RFC-0001.
- **Change if accepted:**
  - `references/prompts/tpl-interview.md` + `references/prompts/module-structured-interview-ui.md` — structured tier labels and relationship-prose options added to the existing `core_audience` question; no new anchor, no validator change; structured-UI mode (CLI sessions with enumerated option pickers) exposes exec/leadership/team/mixed directly (short-circuits Step 2 derivation); text-fallback mode (plain-text brief submissions) retains prose routing.
  - `references/playbooks/outline-phase1-playbook.md` — `受众层级` and `消费模式` added as derived header fields; routing tables, Step 2 derivation task, and routing-table precedence rule added.
  - `references/playbooks/outline-phase2-playbook.md` — checks #22–26 added; FINALIZE stacking table updated.
- **Affected surface:** `references/prompts/tpl-interview.md`, `references/prompts/module-structured-interview-ui.md`, `references/playbooks/outline-phase1-playbook.md`, `references/playbooks/outline-phase2-playbook.md`.
- **Stakes:** Reversible. All files are LLM-consumed reference documents. Roll back by reverting the files; no existing generated output is invalidated.
- **Review focus:** (1) Whether check #22 (density cap) should apply to `reference` archetype exec decks — this RFC excludes `reference` on the grounds that RFC-0001's uniform-dense convention takes precedence; confirm or override. (2) Whether check #26's `manual_audit_mode`-gated branching fix path is sufficient — when audit is `off`, the check flags and continues without user IO; confirm this is the right fallback. (3) Whether check #23's ≥10-page threshold is right relative to RFC-0001's planned `exec-summary-slide` spec (which uses ≥15); this RFC argues ≥10 for Phase 2 checks, ≥15 for Phase 1 conventions.
- **Not in scope:** New `受众层级` interview anchor and its 6-file lockstep (explicit escalation path); changes to the planning phase, HTML rendering pipeline, or interview Step 0 architecture beyond the 2-file prompting enhancement; mandating a specific delivery mode for any deck type.

---

## The ask

**Recommendation (BLUF — Bottom Line Up Front):** Add `受众层级` and `消费模式` as derived Phase 1 outline fields — no new interview questions — and add five Phase 2 checks gated on them orthogonally to the existing `叙事范式` routing.

**Why now (SCQA — Situation / Complication / Question / Answer):**

- **Situation:** RFC-0001 introduced `叙事范式` (narrative paradigm — a 7-value derived field routing structural narrative rules by deck type: pyramid, sparkline, hybrid, reference, status, facilitation, informational). Twelve Phase 2 checks now cover all seven archetypes.
- **Complication:** A board deck and a working-team deck can both carry `叙事范式: pyramid`, but need fundamentally different treatment. C-suite audiences scan non-linearly and need a standalone summary within the first two slides; working teams read sequentially and need full evidence inline. RFC-0001 §Non-goals names this gap explicitly: `受众类型 (audience type)` is "scoped to a separate RFC."
- **Question:** What is the lightest mechanism that gives the outline agent a reliable audience-type signal, and which structural conventions should follow from it?

| ID | Question | Recommendation | Why | Decide by | Reviewer action |
|---|---|---|---|---|---|
| D1 | Canonical audience segments | **4-tier: exec / leadership / team / mixed** | MECE (Mutually Exclusive, Collectively Exhaustive) along decision-authority axis; boundary defined by authority structure, not seniority; `mixed` (cross-level room) produces distinct conventions; precedence rule added for multi-match | This review | Confirm 4 values, or collapse to 3 |
| D2 | Conventions per tier | **Full scope: checks 22–24 for `exec/mixed`; check 25 for `team`; check 22 applies to all archetypes except `reference`** | All verifiable from outline schema fields; `leadership` adequately served by existing checks #9–12; `reference` excluded from density cap because RFC-0001's uniform-dense convention takes precedence | This review | Confirm; or include `reference` in check #22 |
| D3 | Mechanism | **Enhanced `core_audience` (2 files): structured-UI mode exposes tier enum (reliable); text-fallback mode retains prose + routing table (~85–90%)**  | Two modes, two accuracy tiers; structured mode is near-deterministic; 2-file cost vs. 6-file lockstep for a new anchor | This review | Confirm; or accept full anchor cost |
| D4 | Cross-cut with `叙事范式` | **Fully orthogonal** | Both dimensions are independent; conflating them produces an unmanageable matrix | This review | Confirm |
| D5 | Include `消费模式` in this RFC | **Yes — derived field + check 26 with `manual_audit_mode`-gated branching fix path** | Delivery mode is the primary structural differentiator (Duarte, verified); routing uncertainty handled by surfacing A/B/C to user (when audit scope includes `outline`) or flag-and-continue (when `off`) | This review | Confirm; or defer to follow-on RFC |

---

## Problem & goals

### The audience-calibration gap

RFC-0001 routes by deck archetype. It does not route by who is in the room or how they will read the deck. Both dimensions produce structural requirements that are currently unverifiable:

**1. Density ceiling by audience authority.** A `叙事范式: pyramid` deck for C-suite and a `pyramid` deck for an engineering team can both pass RFC-0001's Phase 2 checks. But the board version should cap at `balanced` `密度倾向` (deck-level density preference field — one of `relaxed / balanced / ultra_dense`); the engineering version can use `ultra_dense`. The gap extends to non-persuasion archetypes: a board QBR (Quarterly Business Review, `status + exec`) should also not be `ultra_dense`.

**2. Standalone executive summary.** Board members scan non-linearly; a director who only has time for one slide must walk in informed [startupbos.org, verified]. For a 15-slide strategy deck to a board, the first two slides must reconstruct the full argument without the rest. No check enforces this.

**3. Explicit decision ask.** Executive audiences need a specific, structured approval request. A closing page with `页目标: "总结与下一步"` (the per-slide goal field — one sentence stating what belief or decision this slide produces) fails this. No check enforces the structured format for recommendation decks to exec audiences.

**4. Evidence specificity for working-team audiences.** A `证据页` (evidence page, `信息姿态: 证据页` — the per-page information-stance field values include: `结论页 / 解释页 / 证据页 / 仪表盘页 / 呼吸页`) in a working-team deck must reference specific, quantified data. A team that will execute on the recommendation needs to evaluate the evidence. No check enforces this.

**5. Pre-read standalone coverage for breathing slides.** When a deck is consumed as a pre-read (sent before the meeting), `呼吸页` (visual breathing/rest slides, `信息姿态: 呼吸页`) that carry placeholder `页目标` values like "视觉过渡页" fail as standalone content. Duarte formalizes this as a hard binary: live decks and pre-read documents have structurally incompatible slide conventions, with an explicit anti-hybrid warning [duarte.com, verified].

### Goals

- Each of the five unverifiable audience-calibration properties has a checkable representation at outline time.
- Two new derived fields give Phase 2 checks structured anchors without new interview questions or validator changes.
- The `core_audience` question is enriched for both modes: structured-UI exposes tier directly (near-deterministic); text-fallback mode retains prose with a routing table (~85–90%).
- No new interview anchor, no 6-file lockstep, no change to Step 0 interview architecture.

### Non-goals (deliberately dropped)

- **New `受众层级` interview anchor** — requires 6-file lockstep (changes must land simultaneously across `contract_validator.py`, `check_skill.py`, `tpl-interview.md`, `module-text-interview-fallback.md`, `module-structured-interview-ui.md`, and `smoke_skill.py`) and an 11,500-byte rendered prompt budget check (the combined text interview file must stay within this limit). The 2-file enhancement achieves comparable accuracy at a fraction of the cost. Escalation path explicit: if quality audits show ≥25% misclassification in text-fallback mode, promote to full anchor.
- **Closing `core_audience` to a strict enum in text-fallback mode** — users describe audience in context-rich prose; the routing table handles the most common patterns.
- **`消费模式` routing for all edge cases** — `reference` and `facilitation` archetypes have unambiguous consumption mode from `叙事范式` alone. Routing logic here targets the ambiguous `pyramid/sparkline/hybrid` case and `status`.
- **Mandating a delivery mode for any deck type.** Routing table is descriptive; fallback is `live`.
- **Changes to the planning phase (Step 4), HTML rendering pipeline, or per-page text density rules.**

---

## Proposal

Four files change.

### File 1 — `references/prompts/tpl-interview.md`

**Change: `core_audience` question — add structured tier labels**

The existing `core_audience` dimension bullet reads:

> `core_audience`（落盘归一化到 `audience`）: "你是谁，要在台上向谁讲？" 如一线操盘手向高层要资源 / 业务一号位向客户布道 / 讲师向小白泛大众科普

Add structured tier labels immediately after the examples:

> 受众层级参考（大纲 Agent 在 Step 2 据此派生 `受众层级`，不询问用户；结构化 UI 模式下用户直接选择层级，Step 2 短路派生逻辑）：
> - **exec**：CEO / CFO / COO / CTO / CMO、董事会成员、管理合伙人、出资决策方（治理与资本决策权持有者）——非线性扫读；一页内须能独立理解核心主张
> - **leadership**：VP、总监（Director）、职能负责人、高级经理（无论职级高低，决策权在职能层而非治理层）——顺序阅读；领域细节适当；SCQA 结构有效
> - **team**：业务团队、技术团队、一线员工、执行与交付层——顺序阅读；全量证据内嵌；行动项须具体到人和日期
> - **mixed**：exec 与下属同场，或用户描述"高层和他们的团队"——主页密度和摘要规则按最高层受众设计；证据细节服务整个房间

The `audience` anchor name and normalization mapping are unchanged. In text-fallback mode, the agent writes the `audience` anchor as the user's original prose description; `受众层级` is derived from that at Step 2. In structured-UI mode (see File 2), the agent writes the tier token directly into `audience` (e.g., `audience: exec`); Step 2 sees the bare token and short-circuits to that value.

### File 2 — `references/prompts/module-structured-interview-ui.md`

**Change: `core_audience` structured options — expose tier enum directly**

In structured-UI mode, `core_audience` is already a required single-select. Replace relationship-prose options with the tier taxonomy as named options (plus a "其他/自定义" escape hatch for complex descriptions):

- `exec` — C-suite / 董事会 / 投资决策方（治理与资本决策权持有者）
- `leadership` — VP / 总监 / 职能负责人（功能层决策者）
- `team` — 业务 / 技术 / 执行团队（交付层）
- `mixed` — exec + 下属同场 / 跨层级受众
- 其他（自定义描述）

When the user selects a named tier token, the `audience` anchor is normalized to that token (e.g., `exec`). The Step 2 derivation task recognizes bare tier tokens as authoritative and skips the routing table. Routing accuracy in structured-UI mode is effectively deterministic (~99%); the ~85–90% accuracy estimate in D3 applies only to text-fallback mode.

### File 3 — `references/playbooks/outline-phase1-playbook.md`

**Addition: two derived fields in the outline header**

Add to the `outline.txt` schema header block (`outline.txt` — the structured deck outline produced at Phase 1; the Phase 1 outline methodology runs a 5-step derivation sequence: Step 1 scopes the deck; Step 2 computes derived fields like `叙事范式`, and now `受众层级` + `消费模式`; Steps 3–5 build structure, run page planning, and produce the Phase 2 review checklist), after `叙事范式`:

```
受众层级：{exec / leadership / team / mixed}
消费模式：{live / pre-read / async}
```

**`受众层级` routing table** — agent applies at Step 2. Boundary is decision-making authority structure, not seniority level.

**Row-evaluation precedence:** (1) If `audience` is a bare tier token written by structured-UI mode → use that value directly; skip rows below. (2) If multiple rows match the prose description: `mixed` wins if ≥2 tiers are explicitly co-present; otherwise, the most-senior tier identified in the audience description wins. (3) The presenter's own level is not the routing signal — the target audience's level is.

| `audience` / context signals | `受众层级` |
|---|---|
| Bare tier token from structured-UI mode: `exec` / `leadership` / `team` / `mixed` | Use token directly; skip routing |
| CEO、CFO、COO、CTO、CMO、董事会成员、Managing Partner、出资方（治理角色）、管理合伙人 | `exec` |
| VP、总监（Director）、职能负责人、项目群负责人、Senior Manager（无论职级高低，决策权在职能层而非治理层） | `leadership` |
| 业务/技术/执行团队、分析师、工程师、一线员工、操盘手（非管理层） | `team` |
| 同场包含 exec + 其下属；或用户描述"高层和他们的团队"、"跨层级受众" | `mixed` |

Fallback:

| Condition | `受众层级` | How the agent applies it |
|---|---|---|
| `audience` 描述模糊——无法确定权威层级 | `leadership` | 写 `受众层级: leadership（默认，原因：[说明]）`；中间层默认——偏高触发 exec 检查误报，偏低漏掉 exec 检查；两者相比，误报对用户信任的伤害更大 |

*Pre-RFC outlines lacking this field: Phase 2 checks treat absent value as `leadership`.*

**`消费模式` routing table** — agent applies at Step 2:

| Signal combination | `消费模式` | Confidence |
|---|---|---|
| `叙事范式: reference` | `async` | High — lookup document, no presenter |
| `叙事范式: facilitation` | `live` | High — facilitator always present |
| `叙事范式: informational`（含 `叙事范式: informational` 无场景信号时） | `async` | High — informational decks are self-study content regardless of scenario |
| `叙事范式: informational` + `scenario` 含 培训/L&D (Learning & Development)/课程/入职/知识转移/流程培训/onboarding | `async` | High — explicit self-study signal; same conclusion as row above |
| `叙事范式: status` | `live` | High — status reviews / QBR (Quarterly Business Review) / sprint review are live presentations |
| `受众层级: exec` + `scenario` 含 董事会/理事会/board/board packet/materials/board materials | `pre-read` | High — board packets are sent ahead |
| `受众层级: exec` + `scenario` 含 路演/roadshow/pitch/融资 | `live` | High — investor pitch is live |
| `scenario` 或 `audience` 含 预读/pre-read/提前发送/leave-behind | `pre-read` | High — explicit user signal |
| `pyramid/sparkline/hybrid` 无上述信号 | `live` | Medium — most common enterprise presentation mode |

*Note: `async` is retained as a distinct value to support future checks on async decks (e.g., navigation-aid checks for reference runbooks). Only check #26 currently consumes `消费模式`; it fires solely on `pre-read`.*

Fallback:

| Condition | `消费模式` | How the agent applies it |
|---|---|---|
| 信号模糊 | `live` | 写 `消费模式: live（默认，原因：[说明]）`；check #26 不适用；若后续确认为预读，修改此字段并重新运行 Phase 2 |

*Pre-RFC outlines lacking this field: check #26 skips entirely.*

**Change: Step 2 of the 5-step methodology — add derivation tasks**

After the existing `叙事范式` derivation note, add:

> *Step 2 附加（受众与消费模式）：查阅本 playbook 的受众路由表，基于 `audience` 字段（含 `core_audience` 层级标签）和 `scenario` 信号（`scenario` — the `presentation_scenario` interview field normalized to `scenario` in `interview-qa.txt`; free-text describing the deck's business context, e.g. "董事会战略汇报" or "internal team QBR"），写出 `受众层级`。若 `audience` 是结构化 UI 模式写入的裸层级 token（exec / leadership / team / mixed），直接使用；否则按优先级规则：multi-tier 共存取 `mixed`，单 tier 取最高级别，模糊时默认 `leadership` 并标注原因。同理，查阅消费模式路由表，写出 `消费模式`（live / pre-read / async）。两字段均为派生字段——不询问用户。*

### File 4 — `references/playbooks/outline-phase2-playbook.md`

**Add: Checks #22–26**

Check #22 applies to all `叙事范式` values **except `reference`** (RFC-0001's uniform-dense convention takes precedence for reference runbooks). Checks #23–24 apply to persuasion archetypes only; check #24 excludes `sparkline` (whose closing convention is governed by RFC-0001's archetype rules). Check #25 applies to team-tier persuasion decks. Check #26 has a `manual_audit_mode`-gated branching fix path (`manual_audit_mode` — the interview anchor, one of `off / milestone_only / fine_grained`, controlling how often the agent pauses for user input during Phase 2; `scope` is a companion sub-field listing which pipeline stages allow pauses, e.g. `outline / style / page_planning`); options in check #26 are presented in the user's language (`language` anchor — the `language_mode` interview field normalized at write-time, one of `中文 / 英文 / 中英混排`).

| # | 检查项 | 适用条件 | 严苛标准 | 不通过的处理方式 |
|---|---|---|---|---|
| 22 | **密度上限（高层受众）** | `受众层级 ∈ {exec, mixed}` · `叙事范式 ≠ reference` | 大纲头部 `密度倾向` 不得为 `ultra_dense`。高层受众非线性扫读，信息墙式幻灯片在会前或会中均无法有效消化。`balanced` 是允许的上限。*`reference` archetype 豁免：RFC-0001 为参考型 deck 定义了"均匀偏密"约定，此处不覆盖。* | 将 `密度倾向` 修改为 `balanced`。 |
| 23 | **独立摘要页（高层受众 · 说服型）** | `受众层级 ∈ {exec, mixed}` · `叙事范式 ∈ {pyramid \| sparkline \| hybrid}` · 总页数 ≥ 10 | 前 3 页中是否有至少 1 页 `信息姿态: 结论页`，其 `页目标` 让只读这一页的受众能感知到：（a）核心主张（`核心论点`）和（b）所请求的决策或行动？封面 + 目录不等于独立摘要，不通过。*阈值 ≥ 10 页：10 页以下可被高层受众完整阅读；10 页以上，选择性扫读概率高，独立摘要成为必要。与 RFC-0001 计划的 `exec-summary-slide` spec（≥ 15 页触发 Phase 1 生成约定）互补而非冲突——本 check 是 Phase 2 执行层；该 spec 届时将提供 Phase 1 生成约定和 `叙事角色: exec-summary` 专属页面类型（`叙事角色` — 每页叙事角色字段，如 evidence/comparison/close/cta），本 check 届时可更新为基于该页面类型做校验。* | 在大纲前 3 页插入独立摘要页。`页目标` 示例：`建议批准 AI 平台预算 $800K：Q3 ROI > 200%，需本次授权 Alice 为 Owner。` |
| 24 | **决策请求格式（高层受众 · 决策型）** | `受众层级 ∈ {exec, mixed}` · `叙事范式 ∈ {pyramid \| hybrid}` | 收尾区块末页（最后论证 Part 的末页，Part 是 `outline.txt` 中以 `## Part N:` 标记的叙事章节单元；或独立 `close` 页，即 `叙事角色: close` 的综合/收束页）的 `页目标` 是否包含具体的、有 Owner 和时限的批准请求？`"总结与下一步"`、`"行动号召"`、`"感谢"` 均不通过。*不适用于 `sparkline`——该 archetype 的收尾（愿景揭示 / 量化路演请求）由 RFC-0001 的 archetype 规则管理，避免双重覆盖。* | 将收尾页 `页目标` 改写为结构化决策请求。示例：`请批准：（1）$800K Q3 预算 → Alice → 7/31；（2）跨部门数据访问授权 → Bob → 8/15。` |
| 25 | **证据具体性（团队受众 · 说服型）** | `受众层级: team` · `叙事范式 ∈ {pyramid \| sparkline \| hybrid}` | `信息姿态: 证据页` 的每个 `页目标` 是否引用了具体、可量化的数据或命名来源？模糊断言（"效率显著提升"）不通过；具体数据（"每位分析师节省 3 小时/周"）通过。执行层团队需要评估证据，而非信任主张。 | 在 `页目标` 中补充具体数据或来源引用；若数据尚未确认，标 `素材来源: false`（`素材来源` — 每页字段，标记该页声明的素材是否已在用户提供的 Brief 中找到，`false` 表示存在素材缺口）并说明缺口。 |
| 26 | **呼吸页独立可读（预读模式）** | `消费模式: pre-read` | `信息姿态: 呼吸页` 的 `页目标` 是否在无演讲者的情况下携带独立含义？占位符（"视觉过渡页"）或纯视觉描述不通过；语义明确的过渡句通过。**本检查不自动修复；处理方式按 `manual_audit_mode` 分支：** ① `manual_audit_mode` 的 `scope` 包含 `outline` 或为 `fine_grained`：以用户的语言（`language` 锚点：`中文` 则中文呈现，`英文` 则英文呈现，`中英混排` 则双语并列）向用户输出选项并等待选择——**A** 确认预读：将失败页 `页目标` 改写为语义明确的过渡句，或合并入相邻内容页；**B** 本 deck 有演讲者现场呈现：修改 `消费模式: live`，本检查不适用；**C** 自定义：由用户逐页指定 `页目标`。② `manual_audit_mode: off` 或 `scope` 不含 `outline`：将失败页列入 Phase 2 摘要并标注原因，不阻塞流程、不提示用户、不修改大纲；用户可在 Phase 2 摘要中查看并在下次运行时修正。按用户选择或分支②约定执行，不得在用户确认前（分支①）或摘要记录前（分支②）修改大纲。 |

**Update: FINALIZE contract — add stacking rows**

The FINALIZE contract is the `适用检查速查` speed-reference table in `outline-phase2-playbook.md`. It lists which numbered checks (1–21, now extended to 26) apply per `叙事范式` value; the agent verifies all applicable rows before signing off the Phase 2 review. Add the following stacking rows to the existing table:

Add to the existing 适用检查速查 table:

```
受众层级补充（叠加在叙事范式行之上）：
  exec 或 mixed（非 reference 叙事范式）：+#22（+1项）
  exec 或 mixed（pyramid 或 hybrid 说服型）：+#22–24（+3项，含 #22）
  exec 或 mixed（sparkline 说服型）：+#22–23（+2项，不含 #24）
  team（pyramid/sparkline/hybrid 说服型）：+#25（+1项）
  leadership（任何叙事范式）：无新增

消费模式补充（独立叠加）：
  pre-read（任何叙事范式）：+#26（+1项，分支确认，见检查说明）
  live 或 async：无新增

完整检查数速查示例：
  pyramid + exec + live：#1–12 + #22–24 = 15项
  pyramid + exec + pre-read：#1–12 + #22–24 + #26 = 16项
  sparkline + exec + live：#1–12 + #22–23 = 14项
  pyramid + team + live：#1–12 + #25 = 13项
  status + exec + pre-read：#1–8 + #13–15 + #22 + #26 = 13项
  status + exec + live：#1–8 + #13–15 + #22 = 12项
  facilitation + exec + live：#1–8 + #16–18 + #22 = 12项
  informational + leadership + async：#1–8 + #19–21 = 11项
  reference + exec + async：#1–8（check #22 豁免 reference archetype）= 8项
  受众层级缺失（pre-RFC 大纲）：按 leadership 处理；消费模式缺失：#26 跳过
```

### Migration

No existing outlines invalidated. New requirements apply to new outline runs only.

Pre-RFC outlines lacking `受众层级`: Phase 2 treats absent value as `leadership`. Pre-RFC outlines lacking `消费模式`: check #26 skips entirely.

---

## Options considered

### D1 axis: granularity of audience-type segments

*Axis: decision-making authority structure. Exhaustiveness argument: exec covers governance/capital-allocation tier; leadership covers functional decision-making; team covers execution/delivery; mixed handles cross-level co-presence. External audiences (investors, clients) map into these tiers by the authority level of the people present — an investor in a governance role is exec; a client working team is team.*

| Option | Segments | Verdict |
|---|---|---|
| **A. Do nothing** | None | Rejected: five unverifiable properties persist |
| **B. 2-tier (exec / non-exec)** | Coarsest split | Rejected: `non-exec` conflates VPs with junior analysts; too coarse for actionable conventions |
| **C. 3-tier (exec / leadership / team)** | Matches implicit McKinsey 3-segment observation [slideuplift.com, verified] | Rejected: `mixed` (C-suite + reports) is common in enterprise settings; its convention (density cap + exec summary, but full evidence depth for reports) differs from pure `exec` |
| **D. 4-tier (exec / leadership / team / mixed) — chosen** | Adds `mixed`; boundary is authority structure, not seniority; precedence rule handles multi-match | **Chosen** |
| **E. 5-tier+ (adds `external`)** | Adds external-client as tier | Rejected: external clients map into existing tiers by authority level; no distinct structural conventions |

**On the exec/leadership boundary:** A very senior VP is still `leadership`; a newly promoted C-suite member is `exec`. The criterion: governance or capital-allocation authority (`exec`) vs. domain or functional authority (`leadership`).

**On the `mixed` convention:** Density cap and exec summary rules follow the most senior reader's *consumption pattern* (they scan; the deck must survive scanning). Evidence depth serves the full room — reports will read the evidence; the exec will read the summary.

### D2 axis: scope of tier-specific conventions

- **Density ceiling only** — catches exec information overload but leaves exec summary and decision-ask gaps.
- **Full scope (checks 22–25) — chosen** — all verifiable from outline schema fields and `页目标` text. Check #22 is cross-archetype *except* `reference` (RFC-0001's uniform-dense convention takes precedence for runbooks). Checks #23–24 are persuasion-only (non-persuasion exec archetypes have equivalent orientation checks from RFC-0001: check #13 is the status-deck verdict equivalent; check #16 is the facilitation-deck session-objective equivalent). Check #24 excludes `sparkline` — that archetype's closing convention is governed by RFC-0001.
- **`leadership` gets no new checks** — deliberate. Leadership audiences can push back in Q&A; working teams execute on what they receive. Existing checks #9–12 adequately serve leadership persuasion decks.

### D3 axis: reliability vs. cost of the derivation mechanism

| Option | Mechanism | Files | Routing accuracy | Verdict |
|---|---|---|---|---|
| **A. Pure free-text derivation** | Derive from existing `audience` prose as-is | 0 | ~70% (text mode) | Rejected: false-negatives on board decks (missed exec summary) are real quality failures |
| **B. Full new interview anchor** | Add `受众层级` to `REQUIRED_INTERVIEW_ANCHORS` (the required-anchor list in `contract_validator.py`; any field listed here must be present in every `interview-qa.txt` before the pipeline proceeds) | 6 (lockstep) | ~99% | Deferred escalation path: trigger if text-mode quality audits show ≥25% misclassification |
| **C. Enhanced `core_audience` (2 files) — chosen** | Structured UI: user picks tier directly (~99%); text fallback: routing table from enhanced description (~85–90%) | 2 | Mode-dependent: ~99% / ~85–90% | **Chosen** |

The two-mode accuracy split is an acknowledged asymmetry. Users who use the structured UI (most interactive sessions) get near-deterministic routing. Users who submit prose briefs (text-fallback or API mode) get routing-table derivation with documented fallback.

### D4 axis: relationship between `受众层级` and `叙事范式`

- **Influence `叙事范式` routing** — rejected: RFC-0001's bifurcated fallback already handles exec + ambiguous-pattern cases; adding audience tier to `叙事范式` routing produces a 28-combination matrix.
- **Fully orthogonal — chosen** — check #22 is the only cross-archetype gate; checks #23–25 are scoped to persuasion archetypes by design; the `reference` exemption in check #22 is the one explicit interaction with `叙事范式`.

### D5 axis: include `消费模式` in this RFC

- **Defer to follow-on** — misses check #26, which addresses a user-facing quality failure (empty breathing slides in board pre-reads) otherwise undetected.
- **Include with auto-fix** — rejected: `消费模式` routing uncertainty (~70% for ambiguous persuasion decks) means the agent may have wrongly classified the mode; auto-modifying outlines in the wrong direction is worse than not checking.
- **Include with `manual_audit_mode`-gated branching fix — chosen** — check #26 surfaces A/B/C when user is in an auditable mode; flags and continues when `manual_audit_mode: off`. The routing uncertainty is surfaced to the user as a decision point, not silently resolved.
- **Compound `受众情境` field (tier + mode combined)** — rejected: the two dimensions cross-cut (pre-read board deck and live board deck both have `受众层级: exec`); a compound field requires a partially-specified 4×3 matrix that is harder to maintain.

---

## Risks & what would make this wrong

**Pre-mortem: RFC ships, audience-calibration quality doesn't improve.**

- *Most likely cause (text-fallback mode):* `受众层级` derivation still misclassifies ~20–30% of text-mode decks despite enhanced prompting. A working-team deck gets `exec` and ships with artificially low density; a board deck gets `leadership` and ships without an exec summary. **Mitigation:** Fallback requires documented reasoning in the field value; auditors detect systematic errors from reasoning traces. **Escalation:** promote to full new interview anchor (6-file lockstep) if ≥25% misclassification rate on text-mode audited runs.

- *Second cause:* Check #23 (exec summary gate) fires on a `结论页` that is actually a section introduction, not a standalone summary. **Mitigation:** Check #23 requires both the core thesis AND a decision/action request in the `页目标`; section introductions typically lack the decision element.

- *Third cause:* Check #26 never fires because `消费模式` defaults to `live` for persuasion decks with ambiguous scenario descriptions — including many board strategy decks. **Acknowledged:** this is a documented false-negative rate (~30% of cases where check #26 should fire, it won't, due to mode misclassification). When check #26 *does* fire, the `manual_audit_mode`-gated branching gives users agency to correct a wrong classification; the false-negative is the bigger practical risk.

**Key assumptions (falsifiable):**

1. Enhanced `core_audience` prompting yields ~85–90% routing accuracy for `受众层级` in text-fallback mode. *Falsifiable:* generate 10 decks with varied `audience` prose descriptions; if ≥3 derive wrong `受众层级` values, escalate to full anchor.

2. Check #26's Phase 2 LLM can distinguish placeholder `呼吸页` `页目标` from semantically meaningful transition `页目标`. *Falsifiable:* run Phase 2 on a pre-read deck with `呼吸页` `页目标: "视觉过渡页"`; if check #26 passes without surfacing to the user (audit on) or appearing in the summary (audit off), detection is failing.

3. Check #24 correctly gates out of `sparkline` without producing false-negatives on investor/sales `sparkline` decks. *Falsifiable:* RFC-0001's closing conventions for `sparkline` investor variant already require a quantified ask; check #24 is genuinely not needed for `sparkline`.

**Risk — reference + exec interaction:**
A board runbook (`reference + exec`) is exempt from check #22 (density cap). This is a deliberate design choice — the runbook's uniform-dense convention from RFC-0001 takes precedence. A reviewer who disagrees should flag this explicitly.

**Risk — exec/leadership boundary for senior VPs:**
A senior VP exercising de-facto C-suite authority gets `leadership`, and checks #23–24 don't fire. **Mitigation:** The `mixed` tier exists for multi-authority rooms; for single-audience VP decks where the exec checks matter, the user can use structured-UI mode and select `exec` directly.

**Drawbacks:**

- Two new derived fields add Step 2 overhead on every outline run.
- `消费模式` routing for persuasion decks has ~70% confidence for ambiguous cases; check #26 will miss pre-read board decks with non-board-specific scenario descriptions.
- Check #25 (evidence specificity for team) requires Phase 2 LLM to judge "specific vs. vague" in `页目标` text — a fuzzy threshold similar to check #10's claim-shape judgment.
- The FINALIZE stacking table is now three-layered. The worked examples address this; the table is still more complex than RFC-0001's single-axis FINALIZE.

---

## Evidence & prior art

**De-risk — `受众层级` derivation accuracy:**

Two-mode design: structured-UI mode is near-deterministic (user selects tier directly); text-fallback mode uses a routing table with named tier labels (~85–90% estimated accuracy vs. ~70% for pure prose derivation). The riskiest assumption is the text-fallback accuracy estimate, which is based on the analogy to `叙事范式` routing from `叙事结构` (`叙事结构` — the earlier narrative-structure field that RFC-0001 systematized into `叙事范式`; the original routing experiments showed that structured tier labels improved derivation accuracy on this predecessor field) — itself an inference, not a controlled measurement. No calibration run was conducted before drafting; the falsifiable test in Risks section is the designated post-landing check.

**Repo precedent:**

- `docs/rfc/0001-narrative-philosophy-routing.md` — established derived-field mechanism; §Non-goals explicitly names `受众类型` as "scoped to a separate RFC."
- `references/prompts/tpl-interview.md` — confirms `core_audience` → `audience` anchor exists; the enhancement touches only the question description and structured-UI options, not the anchor contract (`interview-qa.txt` write-time normalization table) or validator (`contract_validator.py`).
- Memory `ppt-interview-anchor-consumers.md` — documents 6-file lockstep + 11,500-byte budget for new anchors; confirms 2-file enhancement is significantly cheaper.
- `docs/rfc/0001-notes/slide-storytelling-survey.md` §3 — audience-calibration table and executive prescription set; incorporated here.

**External prior art (all citations fetched and verified during research phase; retrieval log in `docs/rfc/0002-notes/`):**

- **startupbos.org — CEO Guide to Board Presentation Design** [verified, primary] — board directors scan non-linearly; dedicated summary slide required ("directors who only have time for one slide still walk in informed"); claim visible before explanation. `[high confidence]` → grounds checks #22–23.
- **deckary.com — Executive Summary Slides** [verified, primary] — SCR (Situation / Complication / Resolution) structure for exec summary; board presentations "lead with strategic impact and risk implications"; operational updates "lead with status." `[high confidence]` → grounds checks #23–24 and exec/operational distinction.
- **slidemodel.com — Executive Presentations** [verified, primary] — "insights not details"; full analysis deferred to appendix/Q&A. `[high confidence]`
- **duarte.com — Slides vs. Slidedoc** [verified, primary] — hard binary between live slides and Slidedoc (self-contained pre-read); explicit anti-hybrid warning. `[high confidence]` → grounds `消费模式` as a structural dimension and check #26.
- **duarte.com — How to Craft and Nail Your Executive Presentation** [verified, primary] — pre-reads serve to confirm time commitment and prevent surprises. `[high confidence]`
- **slideuplift.com — McKinsey Style** [verified, secondary] — 3-segment audience observation; no canonical named taxonomy from any primary institution. `[moderate]` — confirms 4-tier is a cross-source synthesis.
- **powerwriting.co — Executive Presentation Structure** [verified, secondary] — "insights not details"; full analysis to pre-reads/leave-behinds. `[moderate]`

*No canonical named audience taxonomy exists in primary institutional sources.* The 4-tier taxonomy here is a cross-source synthesis named as such.

---

## Open questions

1. **Should `leadership`-tier decks get an evidence display convention?** A VP-level persuasion deck with vague evidence assertions isn't caught by any current check. **Recommended default:** monitor for leadership-tier evidence failures in post-landing audits; add a lighter form of check #25 if failures appear. **Owner:** RFC author/maintainer. **Decide-by:** first quality audit post-landing.

2. **Should `消费模式` be captured more explicitly at the interview stage?** If post-landing audits show ≥25% of exec-tier persuasion decks misclassifying `live` vs. `pre-read`, adding a delivery-mode sub-option to the structured `core_audience` question (still within the 2-file enhancement, no new anchor) is the natural first escalation step. **Recommended default:** derive first; monitor. **Owner:** RFC author/maintainer. **Decide-by:** first quality audit post-landing.

---

## Follow-on artifacts

*(Filled in when accepted.)*

- **Spec: `docs/specs/audience-type-routing/`** — implementation spec with exact line-level edits to the four files.
- **Potential escalation spec:** if post-landing audits show text-mode `受众层级` misclassification ≥25%, a spec to promote `受众层级` to a full interview anchor (6-file lockstep).
