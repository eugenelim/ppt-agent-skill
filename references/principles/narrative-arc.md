# 叙事结构与节奏

> PPT 不是信息的堆砌，而是一段有起承转合的叙事旅程。观众的注意力是一条曲线，好的设计顺着它走。
> 影响字段：`narrative_role`、`rhythm_action`、`variation_guardrails.different_from_previous`。
> 叙事转折页（从问题到方案）必须引用此原则；涵盖三幕式结构、情绪曲线、节奏控制。

## 经典叙事框架

### 金字塔原理（Barbara Minto）
- **结论先行**：先给答案，再给理由
- **以上统下**：上层观点是下层的总结
- **归类分组**：同级信息属于同一逻辑范畴
- **逻辑递进**：时间顺序 / 重要性递减 / 因果关系
- **PPT 应用**：封面就给出核心结论，后续页面是"为什么"和"怎么做"

### SCQA 框架
- **Situation**（情境）：大家都认同的现状
- **Complication**（冲突）：但是出现了问题/变化
- **Question**（疑问）：所以我们该怎么办？
- **Answer**（回答）：我的方案是...
- **PPT 应用**：前 2-3 页建立情境和冲突，中间展开方案，结尾行动号召

### 故事弧线
```
         高潮
        /    \
  上升 /      \ 下降
     /        \
起点 ─         ─ 结局
```
- 不要从第一页就进入高密度信息轰炸
- 用章节封面/金句页制造"呼吸点"
- 结尾页回到开头的核心信息（首尾呼应）

## 哲学路由：应用场景与叙事范式

大纲 Agent 在 Phase 1 Step 2 读取本表，依据 `叙事结构` 输入、`论证策略` 选值及 deck 的明确用途，将 `叙事范式` 写入大纲头部。

### Tier 1 — 说服型（Persuasion）

| `叙事结构` / 场景信号 | `叙事范式` | Cover | Transition | Closing |
|---|---|---|---|---|
| 问题->方案->效果、全景->聚焦->行动、是什么->为什么->怎么做、对比论证；**also routes here:** 咨询 / 顾问 deck、提案 / RFP response、数据报告 + 建议、董事会治理决策议题 | `pyramid` | **Thesis-first**：封面 `页目标` 直述或高度浓缩 `核心论点` | 需要 bridge sentence — 逻辑连线；Part 过渡处使用 SCQA 式桥接 | `narrative_driven` / `data_driven` Parts 必须以至少一页 `叙事角色: close`（结论/综合页）或 `信息姿态: 结论页`（结论/论点页）收束；全 deck 以明确决策 + Owner 收尾 |
| 愿景叙事、变革叙事、品牌叙事；**also routes here:** keynote / 思想领袖 deck、投资人 pitch（Sequoia 10-section 或 YC 模式）、销售 pitch（Challenger / 新旧对比模式） | `sparkline` | **Hook-first**：封面开一个张力句或疑问——观众当前痛点，或"将来可能的样子"——而非演讲者的论断 | 需要 bridge sentence — 情感转折或对比须明确表述（"当前现实是 X；变为可能的是 Y"） | `close` 页命名转化后的状态；投资人 / 销售变体以具体量化的请求结尾（"投资 2M 以在 [日期] 达到 [里程碑]"） |
| 对比论证 with Pyramid structure + 视觉简洁强调 | `hybrid` | **Thesis-first** | 需要 bridge sentence | 同 `pyramid` |

### Tier 2 — 参考型（Reference；existing `reference_runbook` code path，不适用说服规则）

| `叙事结构` / 场景信号 | `叙事范式` | Cover | Transition | Closing |
|---|---|---|---|---|
| 时间线 / 生命周期 **且** 至少一个 Part 声明 `论证策略: reference_runbook` | `reference` | **Navigation-first**：实体名称 + 生命周期阶段 | 仅标签（无需 bridge sentence） | 横切参考 back-matter（RACI、升级路径、质量门）——非 CTA |

**`reference` 要求有 `reference_runbook` Parts。** 说服型时间线（公司历史、愿景路线图）若无 `reference_runbook` Part，落入下方 fallback 行。

### Tier 3 — 非说服型（Non-persuasion；check #9–12 不适用；check #1–8 仍适用）

| `叙事结构` / 场景信号 | `叙事范式` | Cover | Transition | Closing |
|---|---|---|---|---|
| 状态报告、QBR、项目状态、业务回顾、sprint review；围绕指标、计划 vs. 实际、决策、阻塞项结构化 | `status` | **实体 + 周期 + 裁决**：项目 / 公司名、报告周期，以及 RAG（红 / 黄 / 绿）信号或一句"整体符合预期 / 偏差 / 需干预"摘要 | 强制 backward→forward 结构（绩效回顾区块结束后才开前瞻区块）；blocker 页区分"团队可处理"与"需要决策"；各区块间无 SCQA 桥接 | 决策日志含 Owner 和截止日期——"批准 $80K 支出，[日期]前"而非"讨论管道缺口"——每个行动项有 Owner 和日期 |
| 工作坊、研讨会、共创会、对齐会、发现会；产出由参与者共同生产，而非预先装载 | `facilitation` | **会议主题 + 共同问题或目标**（"今天希望完成什么"）；非建议型 | 口语 / 对话式，不在 slide 层做桥接；活动指令页每项活动最多一页（不跨页） | 共同产出的决策 + 未决问题 + 行动项及 Owner，汇集于收尾收集页；非 CTA |
| 培训、入职、L&D、流程培训、知识转移、onboarding；内容预先确定，按序递进 | `informational` | **模块标题 + 学习目标或范围**（"完成本课程后你将能够…"）；功能性，非分析性 | 每个模块（Part）结束前有一页模块收束页，再开下一模块；各模块是独立知识域；章节标题是导航线索 | 第一周行动 + 关键联系人（入职变体）；评估或知识测验（培训变体）；确保学员离开时知道"我接下来做什么" |

### Fallback — 双叉显式默认

| 条件 | `叙事范式` | Agent 的处理方式 |
|---|---|---|
| `叙事结构` 不可识别 **且** 说服目标明显（正在提建议、论证观点、说服决策者） | `pyramid` | 写 `叙事范式: pyramid（默认，原因：[说明为何判断说服意图明显且无已知模式匹配]）`；适用所有 Tier 1 说服规则 |
| `叙事结构` 不可识别 **且** 无说服目标（汇报、引导、知识传递） | `informational` | 写 `叙事范式: informational（默认，原因：[说明为何判断为非说服意图]）`；跳过 check #10–#12 |

双叉默认优于静默单一默认的关键：Agent 在选择前先判断 deck 的明确用途并记录原因。状态更新绝不会静默地套上 pyramid 规则。

## 注意力曲线

观众的注意力不是恒定的：

```
注意力
  ↑  ■■■■
  │  ■    ■■        ■■■
  │  ■      ■■    ■■   ■■
  │  ■        ■■■■       ■■■■
  └──┬──────────────────────→ 时间
    开头    中段（低谷）    结尾（回升）
```

- **开头 2 分钟**：注意力最高，放最重要的结论
- **中段**：注意力下降，用数据/案例/故事重新唤起
- **结尾前**：注意力回升（"要结束了"），放行动号召和核心回顾

## 视觉节奏

叙事节奏通过视觉密度的交替实现：

| 叙事段落 | 视觉密度 | 设计手段 |
|---------|---------|---------|
| 开篇（建立基调） | 低-中 | immersive 大图 / 封面 |
| 论证（信息密集区） | 高 | bento-grid / dashboard |
| 呼吸（节奏舒缓） | 低 | quote / 章节封面 |
| 高潮（核心论点） | 中-高 | 大数据 + 图表组合 |
| 收束（行动号召） | 低 | 结束页 / 总结要点 |

**禁止**：连续 3 页高密度（观众累了）或连续 3 页低密度（观众睡了）。

### 说服型的两条"诚实"约定（顾问简报常用 · 指导性）

> 说服型 deck 越是主张一个结论，越需要两条自律来守住信任。二者天然皮肤是 [`graphite_gold`](../styles/dark.md)，原语见 [`blocks/advisory-brief.md`](../blocks/advisory-brief.md)；但适用于任何论证型 deck，仅为指导，不改引擎。

1. **so-what netline（每张论证卡以一句"所以"收束）**：每张"论点 + 论据"卡底部挂一行——大写 kicker（`Therefore` / `Result` / `Net`）+ 一句结论。它强制作者把"我陈述了什么"翻译成"所以你该得出什么"，避免"堆事实、不下结论"的懒惰。要点密集的论证页尤其需要它把读者接住。
2. **估算数字的诚实横幅（illustrative-banner）**：任何页面若展示的百分比/曲线是**来自可比案例、非本受众自己的数据**，页顶必须挂一条横幅讲清"这是形状不是承诺、真实基线稍后与团队共同设定"。把"示意"和"承诺"划清界线是顾问诚信的底线——宁可显眼地标注，也不让读者误把示例当保证。

上面两条保持指导性。Phase 2 新增强制门（check #11）：`论证策略: narrative_driven` 或 `data_driven` 的每个 Part 必须以至少一页 `叙事角色: close` 或 `信息姿态: 结论页` 收束——此为 Phase 2 结构性要求，非写作风格建议，不是对以上两条的修改。

## 参考型叙事：运行手册 / 工作手册 archetype（非说服弧线）

> 上面整套（金字塔 / SCQA / 故事弧线 / 注意力曲线 / 高潮-呼吸节奏）是**说服型演示**的模型——一次性线性观看、有情绪高潮、以行动号召收束。**但有一类 deck 不是用来"讲"的，是用来"查"的**：运行手册（runbook）、交付手册、SOP、操作/入职手册、playbook。它们明确"meant to be used, not read once"，读者跳读到自己所处的阶段。此时上面的弧线模型**不适用**，改用下面的参考型 archetype。

**何时判定为参考型**：`叙事结构` 落在"时间线 / 生命周期"，且内容是**可执行的操作制品**（模板 / 清单 / 排期 / 责任矩阵 / 升级路径 / 质量门）而非论点+证据。天然皮肤是 [`schematic_blueprint`](../styles/light.md)，成套组件见 [`blocks/worksheet.md`](../blocks/worksheet.md)。

**如何声明（引擎可识别）**：在大纲里给相应 Part 写 `论证策略：reference_runbook`。任一 Part 选此值即把整套 deck 判为参考型 archetype——这是 `论证策略` 枚举的一个值（不新增 `page_type`）。下游 `contract_validator`（大纲阶段）与 `planning_validator`（策划阶段）都据此分支密度规则；未声明时按说服型处理，行为不变。

**叙事脊柱 = 生命周期时间线**（不是论证高潮）：按"阶段先后"组织（准入 → 各交付阶段 → 收尾 → 复盘 + 横切参考），而非"问题→方案→效果"。

**页面级节奏（覆盖高潮-呼吸规则）**：
- 参考型 deck **整体均匀偏密**（都是要查的制品），不追求单一高潮页，也**不要求"密度高页后跟呼吸页"**——"禁止连续 3 页 high"在此**放宽**（`contract_validator` 与 `planning_validator` 都据 archetype 分支此规则，说服型不变）。
- 节奏来自**制品形态的交替**（表格 → 清单 → 短文 → 标注 callout），不是 high/low 密度起伏。
- 每个阶段区段的内部模式：`section-marker`（§NN + kicker + 规线，轻量分隔，**不占整页**）→ `lead`（一句话交代"何时/为何用这段"）→ 操作制品（template / checklist / schedule）→ 失败模式 + 补救 → "why this matters" 聚光 callout。

**收尾不是 CTA，是横切参考 back-matter**：责任矩阵（RACI）、升级路径、质量门、术语表——按"查得到"而非"打动人"组织。

**个页设计要点（从源手册推断）**：
1. **持久页眉/页脚**（masthead + footer 每页常驻）——参考文档要随时回答"我在哪、这是第几节"，keynote 不这么做。
2. **TOC 按"需要的先后"排序 + 编号**，不按逻辑分类。
3. **章节用 `section-marker` 内联分隔**，而非整页 section 封面（跳读者不需要每次一整页呼吸）。
4. **模板配"what good looks like"标注**；清单配准入门槛；失败模式配补救行。

**与强制骨架的关系**：`cover / toc` 仍在（手册也有封面、目录）。archetype 由 `论证策略：reference_runbook` 触发（`论证策略` 枚举值，下游 `contract_validator` / `planning_validator` 据此分支密度规则）；在此 archetype 下，Part 首页的整页 `section` 呼吸规则**放宽**为内联 `section-marker`，收尾由"行动号召"（`close`/`cta` → `end`）改为 `reference` 横切参考 back-matter。参考型有**专属 page_type**——`section-marker`（内联分隔，消费 `page-templates/section-marker.md`）与 `reference`（横切参考 back-matter，消费 `page-templates/reference.md` + `blocks/worksheet.md` 配方）；二者是自映射的叙事角色+page_type（同 `cover`/`toc`/`section`），枚举与映射见 [outline playbook](../playbooks/outline-phase1-playbook.md)。说服型 deck 不用这两个，其强制骨架不变。

## 发现汇报型叙事 archetype（Discovery-Readout；非说服弧线）

> 上面整套弧线模型适用说服型和参考型。但有一类 deck 是"把我们做了什么发现了什么"呈现给委托方——它**既不是用来说服决策的**（无 CTA 收束），**也不是用来查阅的操作手册**，而是一种**证据驱动的假设展示**，以开放性问题桥接下一阶段。此时改用下面的发现汇报型 archetype。

**何时判定为发现汇报型**：`叙事结构` 落在"发现/discovery/洞察/调研汇报"，且产出包含"痛点列举→观察归纳→假设提出→机会映射"四段，收尾以开放式前瞻问题（而非明确建议或行动号召）收束。

**叙事脊柱（"证据→假设→机会"五段式）**：
```
我们做了什么（方法论） → 我们发现了什么（证据列举） →
规律与主题（观察归纳）→ 我们相信什么（假设）→
接下来的问题（前瞻桥接）
```

**与说服型的关键区别**：
- **说服型**：结论先行、以 CTA 收束、立场明确。
- **发现汇报型**：证据优先、以开放问题前瞻桥接、作者保持假设语气而非处方语气。

**页面级节奏**：
- 开场：数字统计看板（`metrics-scoreboard`）或双 callout 摘要面板（`dual-callout-panel`）——快速建立参与深度可信度。
- 核心：每个综合主题一页 `synthesis-theme-card`（观察→假设→机会链）；跨主题覆盖图用 `coverage-heatmap`。
- 分析：`prioritization-scorecard` 或 `impact-effort-chart` 展示方案排序逻辑。
- 收尾：`anchoring-questions-panel`——3–5 个开放式锚定问题，框定下一阶段探索方向，**无结论性建议，无 CTA**。

**推荐组件**：`resources.block_refs:["discovery-readout"]`（见 [`blocks/discovery-readout.md`](../blocks/discovery-readout.md)）。适配 `dark_professional` / `light_premium` 风格；不推荐 `graphite_gold`（后者偏处方型论证）。

**引擎影响**：guidance-only，不新增 `page_type`；大纲阶段写 `叙事结构: discovery-readout` 可提示/引导大纲 agent 使用此脊柱（`叙事结构` 是自由文本，无枚举消费者，不同于 `论证策略: reference_runbook` 的强制分支）；收尾规则和密度规则遵循本段而非 Tier 1/Tier 3 规则。

### 发现汇报型的两条写作约定（指导性）

> 说服型 deck 有"so-what netline"和"诚实横幅"两条纪律；发现汇报型有自己的两条约定，约束的不是"下结论"而是"把观察和结论清晰分离"。

1. **痛点→观察→假设→机会链（Pain–Observation–Hypothesis–Opportunity chain）**：每个综合主题必须完整走完这四个层次——(a) **痛点**（stakeholder 的原话或可引述的直接证据）→ (b) **观察**（主题层级的模式归纳）→ (c) **假设**（"如果…那么…"格式，明示这是假设不是结论）→ (d) **机会**（初步方案概念，非处方建议）。跳过任何一环都会让 deck 看起来像是把"现象"偷渡成了"建议"，侵蚀委托方对发现过程公允性的信任。

2. **开放式锚定问题作为前瞻桥接（Open anchoring questions as forward bridge）**：发现汇报的最后一页或章末过渡页，必须以"我们尚未回答的问题"而非"我们建议你做什么"收束。锚定问题的写作规律：(a) 以"What / Where / How / Which"开头；(b) 假设尚未回答、不声称已知答案；(c) 指向下一阶段的探索而非给出行动指令。这条约定保持了发现汇报的开放性——委托方的反馈和下一阶段的工作决定，需要一个"可以质疑的假设"作为基础，而不是一个"需要接受或拒绝的建议"。

## 自检

- **先判 archetype**：这是说服型（用弧线）还是参考型（用生命周期时间线）还是发现汇报型（用证据→假设→机会脊柱）？别把调研汇报硬塞进建议型故事弧线。
- 说服型：PPT 作为整体是否有清晰的叙事弧线（而非平铺直叙）？密度高的页面后面是否有呼吸页？结尾页是否回应封面的核心主张（首尾呼应）？
- 参考型：是否按生命周期阶段组织？节奏是否靠制品形态交替（而非密度高潮）？是否有持久页眉/页脚与横切参考 back-matter？
- 发现汇报型：每个主题是否走完"痛点→观察→假设→机会"四环？收尾是否以开放式锚定问题前瞻桥接（无 CTA）？假设是否明确标注为假设而非结论？
