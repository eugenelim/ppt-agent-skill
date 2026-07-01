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
2. **确定 Part 数量和主题** -- 含 Part 间逻辑关系（递进/转折/因果）
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

## outline.txt 强制格式骨架

你的输出必须严格遵守以下层级与字段，下游的 Step 4 将会逐行解析你的输出。不要随意更改键名（如 `页目标` 不能改成 `页面目的`）。

```text
# 大纲
核心论点：{一句话灵魂，贯穿全篇的中心论断}
叙事结构：{问题->方案->效果 / 是什么->为什么->怎么做 / 全景->聚焦->行动 / 对比论证 / 时间线 / 其他}
密度倾向：{relaxed / balanced / ultra_dense}
密度曲线：{一句话概括整套 deck 的密度节奏，例如：low -> mid_low -> high -> medium -> close}
持久化页框：{on / off}    # 缺省 off；on = 每张 content 页加装 masthead 顶栏 + runbook 页脚做定向导览（见下方约束）
总页数：{N}

---

## Part 1: {part_title}
Part 目标：{part_goal}
论证策略：{narrative_driven / data_driven / case_study / comparison / framework / step_by_step / authority / reference_runbook}
与上一 Part 的关系：{无（首Part）/ 递进 / 转折 / 因果 / 并列}

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
- `叙事角色` 必须从 `{cover, toc, section, section-marker, evidence, comparison, process, reference, close, cta}` 中静态选择。（`section-marker` 与 `reference` 是参考型 archetype 专用，见下方映射与骨架规则。）
- `页面类型映射` 必须从 `{cover, toc, section, section-marker, content, reference, end}` 中静态选择，与下游 Step 4 的 `page_type` 一一对应。
- `密度倾向` 必须从 `{relaxed, balanced, ultra_dense}` 中静态选择。
- `持久化页框 (persistent_chrome)` 必须从 `{on, off}` 中选择；**缺省（不写该字段）= off**。仅**参考型（reference）archetype** 的 deck（运行手册 / SOP / playbook —— 见上方 §先判 archetype 与 [`principles/narrative-arc.md` §参考型叙事](../principles/narrative-arc.md)）建议开启：它为每张 `content` 页加装统一的 masthead 顶栏 + runbook 页脚做"我在哪份文档、翻到哪"的定向导览。说明型 deck 一律 off。该字段是 deck 级开关，独立于风格（任何风格都可开启），与 `style.json` 的 `decorations.masthead` 无关。
- `密度下限 / 密度目标 / 密度上限` 必须从 `{low, mid_low, medium, high, dashboard}` 中静态选择，且必须满足 `下限 <= 目标 <= 上限`。
- `节奏动作` 必须从 `{铺垫, 推进, 爆发, 缓冲, 收束}` 中选择。
- `信息姿态` 必须从 `{结论页, 解释页, 证据页, 仪表盘页, 呼吸页}` 中选择。
- `锚点类型` 必须从 `{标题, KPI, 图表, 表格, 图片, 引言}` 中选择。
- `论证策略`（Part 级）必须从 `{narrative_driven, data_driven, case_study, comparison, framework, step_by_step, authority, reference_runbook}` 中选择；下游 `contract_validator` 会校验此值。任一 Part 选 `reference_runbook` 即把整套 deck 判为**参考型 archetype**（见下方骨架规则）。

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
