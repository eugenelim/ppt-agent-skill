# Outline Phase 1 Playbook -- 大纲编写思路与结构生成

## 目标

基于结构化素材和用户需求，设计一份具有说服力的叙事大纲。你是大纲架构师，职责是**构建叙事骨架**，而不是填充具体内容代码。

---

## 方法论

### 三大支柱

1. **金字塔原理** -- 结论先行、以上统下、归类分组、逻辑递进
2. **叙事弧线** -- 情感轨迹有起伏（开场抓人、中间详实、结尾升华）
3. **密度节奏** -- 整套 deck 先有整体感觉，再给每页留出错落差异

> **先判 archetype（说服型 vs 参考型）**：三大支柱针对**说服型**演示。若 `叙事结构` 落在"时间线/生命周期"且内容是可执行操作制品（模板/清单/排期/责任矩阵/质量门）——如运行手册、交付手册、SOP、playbook——则属**参考型 archetype**：叙事脊柱是生命周期而非论证高潮，密度均匀偏密、靠制品形态交替而非高潮-呼吸，Part 首页用内联 `section-marker` 而非整页 section，收尾用 `reference` 横切参考 back-matter 而非 `close`/`cta`。详见 [`principles/narrative-arc.md` §参考型叙事](../principles/narrative-arc.md)。参考型有专属 page_type：`section-marker`（内联分隔）与 `reference`（横切参考），见下方映射表与骨架规则。

### 5 步思考过程

1. **提炼全局核心论点** -- 纵观全盘，写出 1 句话灵魂

   说服型 deck（`叙事范式: pyramid | sparkline | hybrid`）的封面 `页目标` 必须与 `核心论点` 形成强共鸣：
   - **Pyramid / hybrid 模式：** 封面 `页目标` 直述或高度浓缩 `核心论点`。读者仅凭封面即可感知全篇核心主张。
   - **Sparkline 模式：** 封面可用张力句或激发式问句，但必须与 `核心论点` 形成因果呼应——封面设置的悬念，正是 `核心论点` 所解答的。

   Phase 2 check #10 sub-check ① 会对照封面 `页目标` 与 `核心论点` 两个字段来验证。
2. **确定 Part 数量和主题** -- 含 Part 间逻辑关系（递进/转折/因果）

   *Step 2 附加：查阅 `principles/narrative-arc.md` 的哲学路由表，基于 `叙事结构` 输入、`论证策略` 选值、以及 deck 的明确用途，写出 `叙事范式`（pyramid / sparkline / hybrid / reference / status / facilitation / informational）。若输入不明确，先判断是否有说服目标：有则默认 `pyramid`，无则默认 `informational`；两者都要标注原因。*

   *Step 2 附加（受众与消费模式）：查阅本 playbook 下方的「受众层级路由表」，基于 `audience` 字段（含 `core_audience` 层级标签）和 `scenario` 信号写出 `受众层级`。若 `audience` 是结构化 UI 模式写入的裸层级 token（exec / leadership / team / mixed），直接使用；否则按优先级规则：multi-tier 共存取 `mixed`，单 tier 取最高级别，模糊时默认 `leadership` 并标注原因。同理，查阅「消费模式路由表」写出 `消费模式`（live / pre-read / async）。两字段均为派生字段——不询问用户。*
3. **推导整套密度倾向** -- 把 `requirements-interview.txt` 中的 `page_density` 当成 deck 级倾向，而不是每页固定密度：
   - `少而精 -> relaxed`
   - `适中 -> balanced`
   - `容量极大 / 极高密度 -> ultra_dense`
4. **为每 Part 选择论证策略** -- narrative_driven(叙事) / data_driven / case_study / comparison / framework / step_by_step / authority / reference_runbook（参考型：运行手册 / SOP / playbook，触发参考型 archetype——见 [`principles/narrative-arc.md` §参考型叙事](../principles/narrative-arc.md)）
5. **分配页面并确定每页论点与密度窗口** -- **每页只有一句话 page_goal，绝不能含"和"字**（如果有"和"，说明这页装了两个目标，必须拆分成两页）；同时给出 `密度下限 / 密度目标 / 密度上限`
6. **寻找故事与内容支撑** -- 内容必须结构化！PPT 的力量来自于金字塔顶端洞察与底层强有力数据的对冲。必须优先从素材中提取高度精炼的模块化数据点、对比组和关键特征词。如果遇到纯文叙事，也必须拆解出逻辑骨架。去素材摘要里寻找真正能撑起复杂组件矩阵的武器，拒绝平庸的高分贝长段落。

---

## 密度倾向与页差规则

### deck 级密度倾向

整套 deck 必须先选出一个 `密度倾向`：

| 用户输入 `page_density` | 归一化 `密度倾向` | 含义 |
|---|---|---|
| 少而精 | `relaxed` | 整体偏松，但允许少量 `medium/high` 做高潮 |
| 适中 | `balanced` | 整体均衡，允许明显起伏 |
| 容量极大 / 极高密度 | `ultra_dense` | 整体窗口上移，缓冲页也不能退回 `low` |

### page 级密度标签

每页必须使用以下 5 档之一：

`low` / `mid_low` / `medium` / `high` / `dashboard`

它们是**页级基调**，不是整套 deck 的唯一密度。你要做的是：
- 先让整套 deck 有统一的整体感觉
- 再在允许窗口内制造页差
- 不把所有页压成同一档

### 各倾向下的默认窗口

| `密度倾向` | `content` 页默认分布 | 特别约束 |
|---|---|---|
| `relaxed` | `low ~ medium` | 允许少量 `high` 作为高潮；禁止 `dashboard` |
| `balanced` | `mid_low ~ high` | `dashboard` 只能作为少量特殊页 |
| `ultra_dense` | `medium ~ dashboard` | 必须有相对缓冲页，但缓冲页只能降到 `medium` |

### 共同硬规则

- `cover / section / end` 不允许是 `dashboard`
- 禁止连续 3 页 `high / dashboard`
- `dashboard` 前后必须至少有 1 页非 `dashboard` 过渡
- 整套 deck 必须给出一条 `密度曲线`，说明哪些页是高潮、哪些页是缓冲

---

## 受众层级与消费模式路由（Step 2 派生）

两字段均在 Step 2 派生，正交于 `叙事范式`——`叙事范式` 路由 deck 类型的结构规则，本节路由"讲给谁听"和"怎么被消费"。均**不询问用户**。

### 受众层级路由表

判定边界是**决策权结构，而非职级高低**。目标受众的层级是路由信号，演讲者自身的层级不是。

| `audience` / `scenario` 信号 | `受众层级` |
|---|---|
| 结构化 UI 模式写入的裸层级 token：`exec` / `leadership` / `team` / `mixed` | 直接采用该 token，跳过下方各行 |
| CEO、CFO、COO、CTO、CMO、董事会成员、Managing Partner、出资方（治理角色）、管理合伙人 | `exec` |
| VP、总监（Director）、职能负责人、项目群负责人、Senior Manager（无论职级高低，决策权在职能层而非治理层） | `leadership` |
| 业务/技术/执行团队、分析师、工程师、一线员工、操盘手（非管理层） | `team` |
| 同场包含 exec + 其下属；或用户描述"高层和他们的团队"、"跨层级受众" | `mixed` |

**行优先级规则：**（1）若 `audience` 是裸层级 token → 直接采用，跳过其余行。（2）若多行匹配：≥2 个 tier 明确共存取 `mixed`；否则取受众描述中识别到的**最高级别** tier。（3）路由信号是**目标受众**的层级，不是演讲者的层级。

**四层完整口径（含消费/阅读行为）：**
- **exec**：C-suite / 董事会 / 投资决策方（治理与资本决策权持有者）——非线性扫读；一页内须能独立理解核心主张。
- **leadership**：VP、总监、职能负责人、高级经理（决策权在职能层而非治理层）——顺序阅读；领域细节适当；SCQA 结构有效。
- **team**：业务团队、技术团队、一线员工、执行与交付层——顺序阅读；全量证据内嵌；行动项须具体到人和日期。
- **mixed**：exec 与下属同场——主页密度和摘要规则按**最高层**受众设计；证据细节服务整个房间（下属会读证据，exec 读摘要）。

**Fallback：**

| 条件 | `受众层级` | 处理方式 |
|---|---|---|
| `audience` 描述模糊——无法确定权威层级 | `leadership` | 写 `受众层级: leadership（默认，原因：[说明]）`。中间层默认——偏高触发 exec 检查误报，偏低漏掉 exec 检查；相比之下误报对用户信任伤害更大。|

*pre-RFC 大纲缺少此字段：Phase 2 检查按 `leadership` 处理。*

### 消费模式路由表

| 信号组合 | `消费模式` | 置信度 |
|---|---|---|
| `叙事范式: reference` | `async` | 高——查阅文档，无演讲者 |
| `叙事范式: facilitation` | `live` | 高——主持人恒在场 |
| `叙事范式: informational`（无场景信号时同样成立） | `async` | 高——说明型 deck 无论场景都是自学内容 |
| `叙事范式: informational` + `scenario` 含 培训/L&D/课程/入职/知识转移/流程培训/onboarding | `async` | 高——显式自学信号 |
| `叙事范式: status` | `live` | 高——状态汇报 / QBR / sprint review 是现场演示 |
| `受众层级: exec` + `scenario` 含 董事会/理事会/board/board packet/materials/board materials | `pre-read` | 高——董事会材料提前发送 |
| `受众层级: exec` + `scenario` 含 路演/roadshow/pitch/融资 | `live` | 高——投资路演现场进行 |
| `scenario` 或 `audience` 含 预读/pre-read/提前发送/leave-behind | `pre-read` | 高——显式用户信号 |
| `pyramid/sparkline/hybrid` 无上述信号 | `live` | 中——最常见的企业演示模式 |

*`async` 作为独立值保留以支持未来对异步 deck 的检查（如参考型 runbook 的导航辅助检查）。当前仅 check #26 消费 `消费模式`，且只在 `pre-read` 时触发。*

**Fallback：**

| 条件 | `消费模式` | 处理方式 |
|---|---|---|
| 信号模糊 | `live` | 写 `消费模式: live（默认，原因：[说明]）`；check #26 不适用；若后续确认为预读，修改此字段并重新运行 Phase 2。|

*pre-RFC 大纲缺少此字段：check #26 整项跳过。*

---

## outline.txt 强制格式骨架

你的输出必须严格遵守以下层级与字段，下游的 Step 4 将会逐行解析你的输出。不要随意更改键名（如 `页目标` 不能改成 `页面目的`）。

```text
# 大纲
核心论点：{一句话灵魂，贯穿全篇的中心论断}
叙事结构：{问题->方案->效果 / 是什么->为什么->怎么做 / 全景->聚焦->行动 / 对比论证 / 时间线 / 其他}
叙事范式：{pyramid / sparkline / hybrid / reference / status / facilitation / informational}
受众层级：{exec / leadership / team / mixed}
消费模式：{live / pre-read / async}
密度倾向：{relaxed / balanced / ultra_dense}
密度曲线：{一句话概括整套 deck 的密度节奏，例如：low -> mid_low -> high -> medium -> close}
持久化页框：{on / off}    # 缺省 off；on = 每张 content 页加装 masthead 顶栏 + runbook 页脚做定向导览（见下方约束）
总页数：{N}

---

## Part 1: {part_title}
Part 目标：{part_goal}
论证策略：{narrative_driven / data_driven / case_study / comparison / framework / step_by_step / authority / reference_runbook}
与上一 Part 的关系：{无（首Part — first section, no predecessor）/ 递进｜转折｜因果 — 一句话：上一 Part 建立了什么，本 Part 如何从中生长出来（递进 progressive）、转折（转折 reversal）、或因果推导（因果 causal）/ 并列 — 一句话："Part N 建立了[A]；本 Part 以[B]补充并行论据"（并列 parallel/coordinate）}

示例 `转折`：`转折 — Part 1 确立了现有边界防护的逻辑；Part 2 通过三个失效案例论证边界模型对 AI 辅助内部攻击无效。`

示例 `并列`：`并列 — Part 1 建立了成本优势论点；本 Part 以速度优势补充并行论据。`

`首Part` 保留 `无`（无前驱，无需 bridge sentence）。Bridge sentence 由大纲 Agent 生成。

### 第 1 页：{page_title}
- 页目标：{page_goal，一句话，不含"和"字}
- 叙事角色：{cover / toc / section / section-marker / evidence / comparison / process / reference / close / cta}
- 页面类型映射：{cover / toc / section / section-marker / content / reference / end}
- 密度下限：{low / mid_low / medium / high / dashboard}
- 密度目标：{low / mid_low / medium / high / dashboard}
- 密度上限：{low / mid_low / medium / high / dashboard}
- 节奏动作：{铺垫 / 推进 / 爆发 / 缓冲 / 收束}
- 信息姿态：{结论页 / 解释页 / 证据页 / 仪表盘页 / 呼吸页}
- 锚点类型：{标题 / KPI / 图表 / 表格 / 图片 / 引言}
- 论证方式：{proof_type}
- 内容支撑：{这一页需要哪些结构化的金句、数据骨架和逻辑分类来支撑论点。强烈建议在此处对长文进行初步的数据点级切粒。}
- 素材来源：{found_in_brief: true/false，若 false 标注缺口_说明为何缺失却仍需此页}

### 第 2 页：{page_title}
...

---

## Part 2: ...
```

**字段枚举约束**：
- `叙事范式` 是**派生字段**——大纲 Agent 在 Step 2 通过查阅 `principles/narrative-arc.md` 哲学路由表来选取此值；**不询问用户**。值集：`pyramid / sparkline / hybrid / reference / status / facilitation / informational`。`reference` 要求至少一个 Part 声明 `论证策略: reference_runbook`；仅有 `叙事结构: 时间线` 不足以触发。当 `叙事结构` 不匹配任何已知模式时，使用双叉默认：若 deck 有说服目标写 `pyramid`，否则写 `informational`；两种情况都须在字段值中标注原因。pre-RFC 大纲若缺少此字段，Phase 2 检查一律按 `pyramid` 处理。
- `受众层级` 是**派生字段**——大纲 Agent 在 Step 2 查阅本 playbook 的「受众层级路由表」从 `audience`（含 `core_audience` 层级标签）与 `scenario` 信号派生；**不询问用户**。值集：`exec / leadership / team / mixed`。判定按**决策权结构而非职级**。结构化 UI 模式写入的裸层级 token 直接采用（见路由表优先级规则）。信号模糊无法确定权威层级时，默认 `leadership` 并在字段值中标注原因。pre-RFC 大纲若缺少此字段，Phase 2 检查一律按 `leadership` 处理。
- `消费模式` 是**派生字段**——大纲 Agent 在 Step 2 查阅本 playbook 的「消费模式路由表」派生；**不询问用户**。值集：`live / pre-read / async`。信号模糊时默认 `live` 并标注原因。pre-RFC 大纲若缺少此字段，check #26 整项跳过。
- `叙事角色` 必须从 `{cover, toc, section, section-marker, evidence, comparison, process, reference, close, cta}` 中静态选择。（`section-marker` 与 `reference` 是参考型 archetype 专用，见下方映射与骨架规则。）
- `页面类型映射` 必须从 `{cover, toc, section, section-marker, content, reference, end}` 中静态选择，与下游 Step 4 的 `page_type` 一一对应。
- `密度倾向` 必须从 `{relaxed, balanced, ultra_dense}` 中静态选择。
- `持久化页框 (persistent_chrome)` 必须从 `{on, off}` 中选择；**缺省（不写该字段）= off**。仅**参考型（reference）archetype** 的 deck（运行手册 / SOP / playbook —— 见上方 §先判 archetype 与 [`principles/narrative-arc.md` §参考型叙事](../principles/narrative-arc.md)）建议开启：它为每张 `content` 页加装统一的 masthead 顶栏 + runbook 页脚做"我在哪份文档、翻到哪"的定向导览。说明型 deck 一律 off。该字段是 deck 级开关，独立于风格（任何风格都可开启），与 `style.json` 的 `decorations.masthead` 无关。
- `密度下限 / 密度目标 / 密度上限` 必须从 `{low, mid_low, medium, high, dashboard}` 中静态选择，且必须满足 `下限 <= 目标 <= 上限`。
- `节奏动作` 必须从 `{铺垫, 推进, 爆发, 缓冲, 收束}` 中选择。
- `信息姿态` 必须从 `{结论页, 解释页, 证据页, 仪表盘页, 呼吸页}` 中选择。
- `锚点类型` 必须从 `{标题, KPI, 图表, 表格, 图片, 引言}` 中选择。
- `论证策略`（Part 级）必须从 `{narrative_driven, data_driven, case_study, comparison, framework, step_by_step, authority, reference_runbook}` 中选择；下游 `contract_validator` 会校验此值。任一 Part 选 `reference_runbook` 即把整套 deck 判为**参考型 archetype**（见下方骨架规则）。

**说服型 deck 论证页的 `页目标` 规则（`叙事范式: pyramid | sparkline | hybrid`）：**

`信息姿态` 为 `结论页 / 解释页 / 证据页` 的页面，`页目标` 必须同时满足两个条件：

1. **论断句** — 从观众视角陈述这一页让观众相信什么，而非从制作者视角陈述这一页"展示了"什么。
2. **具体可感** — 使用可量化或可感知的表述，而非抽象概括。"3 倍增速"优于"显著提升"；"每位分析师节省 3 小时/周"优于"提升效率"。

❌ 描述 + 抽象（不符合）：`展示 AI 安全事件的增长趋势`
✅ 论断 + 具体（符合）：`2023 年以来 AI 安全事件增速比传统安全事件快 3 倍，威胁已不可忽视`

**"X 因此 Y" 澄清：** 论断句可以是"前提 + 推论"格式（"X 因此 Y"），这视为单一论断，不违反"一页一目标、禁含'和'"规则。违禁的是两个并列目标（"X 和 Y"）。

*Phase 2 check #10 verifies claim-shape（论断句 vs. 主题标签 topic-label）。The concreteness requirement is a Phase 1 generation convention; Phase 2 does not independently gate on concreteness.*

导航页（`cover / section / toc / end`）不受此约束。

### 叙事角色 → page_type 映射规则

| 叙事角色 | page_type | 说明 |
|---------|-----------|------|
| `cover` | `cover` | 封面页 |
| `toc` | `toc` | 目录页 |
| `section` | `section` | 章节过渡页（整页呼吸封面，说服型）|
| `section-marker` | `section-marker` | 内联章节分隔（§NN + kicker + 规线，不占整页；参考型 archetype）|
| `evidence` / `comparison` / `process` | `content` | 正文内容页 |
| `reference` | `reference` | 横切参考 back-matter（RACI / 质量门 / 升级路径 / 术语表；参考型 archetype）|
| `close` / `cta` | `end` | 结束页（close=总结回顾型，cta=行动号召型）|

> `section-marker` 与 `reference` 是**自映射**行（角色名 == page_type），与 `cover` / `toc` / `section` 同理。二者仅在**参考型 archetype**（运行手册 / 交付手册 / SOP / playbook）使用：`section-marker` 在阶段边界做内联分隔替代整页 `section`；`reference` 收尾放横切参考制品替代 `close` / `cta`。说服型 deck 不用这两个。何时判定为参考型见 [`principles/narrative-arc.md` §参考型叙事](../principles/narrative-arc.md)。

---

## 演示骨架强制规则（不可跳过）

无论主题、页数、素材情况如何，生成的大纲**必须**包含以下页面骨架：

| 位置 | 叙事角色 | page_type | 必须性 | 核心功能 |
|------|---------|-----------|--------|----------|
| 第 1 页 | `cover` | `cover` | **强制** | 标题冲击力 + 品牌仪式感 |
| 第 2 页 | `toc` | `toc` | **强制（总页数 >= 6 时）** | 全局路线图，让观众 3 秒理解结构 |
| 每个 Part 首页 | `section` | `section` | **强制（说服型）** | 章节过渡呼吸页，告诉观众进入新篇章 |
| 最后一页 | `close` 或 `cta` | `end` | **强制** | 核心结论收束 + 行动号召（参考型改为横切参考/复盘） |

> **按 archetype 分支（说服型 vs 参考型）**：本骨架的默认形态针对**说服型**演示。当任一 Part 选 `论证策略：reference_runbook`（参考型 archetype）时，两条规则放宽（其余规则不变）：
> - **Part 首页的整页 `section`** 放宽为**内联 `section-marker`**（§NN + kicker + 规线，不占整页）——跳读者不需要每进一段就来一整页呼吸。`section-marker` 是独立 page_type（消费 `page-templates/section-marker.md`）。
> - **最后一页**放宽为 `reference` 横切参考 back-matter（RACI / 质量门 / 升级路径 / 术语表，消费 `page-templates/reference.md`），替代 `close`/`cta` → `end` 的行动号召。
> - **"禁止连续 3 页 high/dashboard"** 放宽——参考型 deck 整体均匀偏密，节奏来自**制品形态交替**（表格 → 清单 → 短文 → callout），而非高潮-呼吸密度起伏。`contract_validator` 与 `planning_validator` 都据 archetype 分支此规则；说服型 deck 行为不变。详见 [`principles/narrative-arc.md` §参考型叙事](../principles/narrative-arc.md)。

**违规检测**：
- 缺少 cover 或 end = **结构缺陷，必须补回**
- 总页 >= 6 却没有 toc = **结构缺陷，必须补回**
- **说服型**：任何 Part 的首页不是 section（除 Part 1 的首页是 cover/toc 外） = **结构缺陷，该 Part 必须有 section 页**。**参考型**（`reference_runbook`）此规则放宽——Part 以内联 `section-marker` 分隔，不要求整页 `section`。
- section 页只做呼吸过渡，**绝对禁止**在 section 页塞数据图表或多卡片布局

### 主题延续规则（灵活性保障）

- 一个 Part 的主题**不限定只用一个 Part 讲完**：如果一个主题内容丰富，可以拆分为多个 Part，每个 Part 聚焦该主题的不同维度
- Part 之间的关系可以是**递进/深化/展开**（同一主题的不同层级），不必是全新的独立话题
- 例如："Part 2: 技术方案概述 → Part 3: 技术方案深潜"是完全合法的结构
- 但每个 Part 仍然必须有自己明确的 `Part 目标`，即使是同一大主题下的延续

### 密度分配规则（必须执行）

- `cover` 页优先使用 `low / mid_low`
- `toc` 页优先使用 `mid_low / medium`
- `section` 页优先使用 `low / mid_low`
- `content` 页按照 deck 的 `密度倾向` 分布
- `end` 页优先使用 `mid_low / medium`，`ultra_dense` 模式下可上探到 `high`

**不要机械平均分配密度**：
- `relaxed` deck 也允许出现 1 页 `high`
- `balanced` deck 必须至少出现 2 档不同密度
- `ultra_dense` deck 不能把所有内容页都写成 `dashboard`
