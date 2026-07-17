# Page Planning Playbook -- 单页策划稿

## ⚠️ 高频 Schema 陷阱（先读这里，防止 100+ 行 validator 错误）

以下两类错误在每张幻灯片上都会触发，累计导致 100-200 行 ERROR。**在写任何 JSON 或生成脚本之前先核对这两条：**

### 陷阱 1：`body` 必须是字符串数组，绝不能是裸字符串

```jsonc
// ❌ 错误 — 所有 body 为字符串的卡片都会报 "skeleton card" ERROR
"body": "This is my body text"

// ✅ 正确
"body": ["This is my body text"]
```

validator 的 `as_list()` 遇到非列表值返回 `[]`，导致 `has_body = False`，即使有 `headline` 也会把该卡片判定为骨架卡并报 ERROR。

### 陷阱 2：`density_contract` 必须包含全部 9 个字段

每页 `density_contract` 缺少任何一个字段就会在该页报 ERROR。9 个字段是：

```
deck_bias, page_lower_bound, page_upper_bound,
max_cards, max_charts, min_body_font_px, max_lines_per_card,
image_policy, decoration_budget, overflow_strategy
```

**首选：不要自己写批量脚本，用 `assemble_planning.py`（见下方「确定性装配器」节）**——它已经把 `DENSITY_DEFAULTS` 等常量从 validator import 进来并自校验，是最不容易出错的路径。若你确有理由自己拼 JSON，也务必直接从 `scripts/planning_validator.py` 复制 `DENSITY_DEFAULTS` 字典而非凭记忆重录（手写极易漏掉末尾 3 个字段或弄错数值，例如 `medium.max_charts` 是 **2** 不是 1，`dashboard.max_lines_per_card` 是 **3** 不是 4）。

### 陷阱 3：`data_points` 是内容信号，`data` 不是

validator 只检查 `data_points: [{"label": "...", "value": "..."}]`（对象数组）来判断卡片是否有数据内容。  
`"data": {"key": "val"}` 这种自由格式字典**不会被识别为内容信号**，卡片仍会被判定为骨架卡。

```jsonc
// ❌ 错误 — validator 不识别 data 字段，card 还是骨架卡
"data": {"TG-A": "Partial", "TG-B": "Strong"}

// ✅ 正确
"data_points": [{"label": "TG-A", "value": "Partial"}, {"label": "TG-B", "value": "Strong"}]
```

### 陷阱 4：`resources.*_refs` 只能写**真实存在的文件 stem**，绝不能写枚举值或臆造名

validator 会把 `layout_refs` / `block_refs` / `chart_refs` / `principle_refs` 里的每一项去 `references/<子目录>/` 下查文件，查不到就报 ERROR。最常见的两类错误：把 `card_type` / `chart_type` 的**枚举值**（如 `text`、`list`、`process`、`data_highlight`、`progress_bar`）当成 refs 填进去；或凭记忆臆造一个不存在的文件名。**只有下面这份清单里的 stem 是合法的**（validator 会自动把下划线归一为连字符，所以 `matrix_chart`→`matrix-chart.md` 也能命中；但 `process`、`data_highlight` 等根本没有对应文件）：

```
layout_refs    : asymmetric hero-top l-shape mixed-grid primary-secondary
                 single-focus symmetric t-shape three-column waterfall
block_refs     : advisory-brief card-styles comparison diagram diagram-architecture
                 diagram-concept diagram-process-flow diagram-project image-hero
                 matrix-chart people quote timeline worksheet
chart_refs     : basic advanced complex index          ← 不是 chart_type 枚举值！
principle_refs : cognitive-load color-psychology composition data-visualization
                 design-principles-cheatsheet failure-modes narrative-arc
                 runtime-failure-modes taste-gate visual-hierarchy
page_template  : cover toc section section-marker reference end
```

> **拿不准就留空 `[]`**——**diagram 除外**。空数组对普通卡片永远合法；写一个不存在的 stem 一定报 ERROR。`card_type` 与 `block_refs` 是**两套不同的集合**——选了某个 `card_type` 不等于要在 `block_refs` 里重复它。
>
> **但只要这一页要画图（架构 / 流程 / 管线 / 拓扑 / 生命周期 / 组织树 / 时序 / 象限 等），"留空"就是错的**：必须把该卡标成 `card_type:diagram` + 明确的 `diagram_type`，并按下方 Phase 2 的 `diagram_type → block_refs` 映射把 family 配方（如 `diagram-architecture`）加进 `block_refs`——否则 HTML 阶段拿不到主题化、管线安全、连线拓扑正确的配方正文，只能凭空临摹（现场事故的直接成因）。`planning_validator.py` 的 **`DIAG-ROUTE-01`（WARN）** 会拦这类"图形卡未路由配方"，看到就补齐 `diagram_type` + family ref。**别把 pipeline/flow/architecture 这类明显要画的内容塞进 `list`/`text` 卡当散文交出去。**

### 图解复杂度预算（画得下、画得对的前提）

> 依据：LLM 在单遍生成里同时"定拓扑 + 手排坐标"最容易翻车（坐标算术错误、多约束整合 <50%、随规模崩塌）。把复杂度压在预算内，第一遍就更可能画对。

- **每张图 ≈ 8–12 个节点、10–15 条连线封顶**；超了就在 planning 阶段拆成子图（分两页或主图+细节图），不要硬塞。
- **稠密多对多（一组源都连同一组目标）** → 规划成**总线拓扑**（主干 + 短支线，见 `blocks/diagram.md` §3.1 ④），不要 N×M 根斜线。
- 预算落到 `content_budget` / `density_contract` 的措辞里，让 HTML 阶段知道该页图解的规模上限。（planning JSON 无"节点数"字段，这是**规划期书面约束**，不是机器校验。）

### 陷阱 5：`narrative_role` 与 `argument_role` 是**两条不同的轴**，别互相串用

- `narrative_role`（页级叙事角色）合法值只有：`cover` `toc` `section` `section-marker` `opening` `orientation` `transition` `setup` `evidence` `comparison` `framework` `process` `case` `quote` `breath` `reference` `close` `cta`。**`claim` 不是 `narrative_role`**——写进去会报 WARN。
- `argument_role`（卡片级论证角色）合法值只有：`claim` `evidence` `contrast` `constraint` `method` `synthesis` `prerequisite` `framework`。`claim` 属于**这里**。注意 `context` 是 `role`（卡片角色 anchor/support/**context**）的值，**不是** `argument_role` 的值——别把它填进 `argument_role`。

---

## 确定性装配器 `assemble_planning.py`（默认生成路径 —— 强烈推荐）

**别再手写整份 planning JSON。** 上面这些陷阱几乎全是 mechanical 样板（9 字段 density_contract、workflow_metadata、content_budget、card_id、图片合同）出错。把这些交给装配器：你只写**判断字段**的最小 payload，脚本从 validator 的常量把样板一次填齐、并在写盘前自校验——产出**必然零 ERROR**，否则脚本报一条指名字段的 `ASSEMBLY ERROR`（退出码 2）让你改 payload，而不是让你在 100 行 validator 输出里大海捞针。

**最小 payload 契约**（页级 + 每张卡；装配器会补齐其余一切）：

```jsonc
{
  "slide_number": 3, "page_type": "content",
  "title": "...", "page_goal": "...",
  "narrative_role": "evidence", "narrative_archetype": "persuasive",  // archetype 缺省 persuasive
  "visual_weight": 5,                                                 // 1..9
  "density_label": "medium", "density_reason": "...",
  "deck_bias": "balanced", "page_lower_bound": "mid_low", "page_upper_bound": "high",  // 来自 outline
  "layout_hint": "mixed-grid",                                        // 仅 content 页必填
  "resources": {"layout_refs": ["mixed-grid"], "chart_refs": ["basic"], "principle_refs": ["visual-hierarchy"], "block_refs": []},
  "cards": [
    {"role": "anchor", "card_type": "data", "card_style": "elevated", "argument_role": "claim",
     "headline": "2x usage", "body": "可裸字符串，装配器包成数组", "chart_type": "metric_row"},
    {"role": "support", "card_type": "text", "card_style": "outline",
     "headline": "What changed", "body": ["列表也行", "第二行"]}
  ]
}
```

**装配器替你做的（所以你不用写）**：`card_id` 自动生成（`s{页}-{role}-{序}`）；`body` 裸字符串→数组；`density_contract` 9 字段按 `density_label` 从 `DENSITY_DEFAULTS` 填 + 你的 3 个 outline 字段；`content_budget` 生成且 `body_max_lines` 按密度**自动封顶**；`workflow_metadata` 注入；每张卡的完整图片合同（无图片→全 null 的 `needed:false` 对象）；`source_guidance` / `director_command` / `decoration_hints` 缺省兜底；解析不到的 `*_ref` **丢弃并告警**（不再报 ERROR）。

**你仍要负责的（判断，选错会 fail-fast）**：所有枚举**选对值**（`card_type` / `card_style` / `chart_type` / `image.usage` / `image.placement` / `page_type` / `layout_hint` / `density_label` / `deck_bias`）；每张卡有内容信号（别只给 headline）；每页**恰好 1 张 anchor**；content 页 ≥2 卡要 ≥2 种 `card_style`；`density_label` 落在 outline 窗口内。装配器会逐条指名报错。

**卡片图片写法**：不需要图→省略 `image` 或写 `null`；需要图→ `"image": {"usage": "<枚举>", "placement": "<枚举>", "content_description": "...", "source_hint": "..."}`（4 项齐全，枚举见陷阱区）。

**可选 `resource_ref`**：如需为某张卡定向绑定组件，写 `"resource_ref": {"block": "<stem>", "chart": "<stem>", "principle": "<stem>"}`（缺省可省略）；解析不到的 stem 会被丢弃并告警，不会报 ERROR。

> **payload 文件名铁律**：写 payload 时**文件名不要以 `planning` 开头**（下游按 `planning*.json` 通配收集本目录，payload 匹配了会被当成一页混入、污染全册校验）；prompt 里给的 `{{PAGE_NUM}}.payload.json` 就是安全命名，装配成功后该中间文件也会被删除。

> **何时手写回退**：只有当某页结构确实超出上面 payload 契约能表达的范围时，才落回手写完整 JSON（见下方 Skeleton 与 Phase 4 schema），并照旧跑 `planning_validator.py` 校验。绝大多数页用装配器即可。

---

## 复制即用 Skeleton（**手写回退路径**才需要；默认请走上面的装配器）

### 卡片骨架（所有 card_type 通用）

```jsonc
{
  "card_id": "s{N}-anchor-1",
  "role": "anchor",
  "card_type": "text",
  "card_style": "elevated",
  "argument_role": "claim",
  "headline": "",
  "body": [],               // ← 必须是数组。单句也要 ["一句话"]，绝不能写裸字符串
  "data_points": [],        // ← 对象数组 [{label, value, unit, source}]。无数据时留 []
  "chart": null,
  "content_budget": {"headline_max_chars": 12, "body_max_bullets": 3, "body_max_lines": 3},
  // ↑ body_max_lines 必须 ≤ 本页 density_contract.max_lines_per_card。
  //   骨架给的是最安全值 3（低于所有档位上限）；把它改到 ≤ 你这一档的上限即可
  //   （low=3 / mid_low=4 / medium=5 / high=4 / dashboard=3）。照抄 5 会在
  //   low/mid_low/high/dashboard 页报 ERROR。
  "image": {
    "mode": "decorate",
    "needed": false,
    "usage": null,
    "placement": null,
    "content_description": null,
    "source_hint": null,
    "decorate_brief": ""
  },
  "resource_ref": {"chart": null, "principle": null}
}
```

> `needed=true` 时：`usage`/`placement`/`content_description`/`source_hint` 全部改为非 null，且 `usage` 与 `placement` **必须从下列闭集里选**（写别的值报 ERROR）：
> - `usage` ∈ `hero-background` `inline-illustration` `icon-accent` `data-visualization-bg`
> - `placement` ∈ `full-bleed` `left-half` `right-half` `card-bg` `inline`
>
> 有图表时：把 `chart: null` 改为 `"chart": {"chart_type": "<枚举值>"}`。`chart_type` 闭集（**下划线命名**）：`kpi` `metric_row` `sparkline` `comparison_bar` `ring` `stacked_bar` `timeline` `funnel` `radar` `treemap` `waffle` `progress_bar` `rating`。
>
> **多卡片页的两条组合硬规则**（照抄骨架最容易违反）：① 每页**恰好 1 张** `role:anchor` 卡，其余为 `support`/`context`——0 张或 ≥2 张 anchor 都报 ERROR；② `content` 页只要有 ≥2 张卡，就必须用**至少 2 种不同的 `card_style`**（别把每张都设成 `elevated`）。

> **写批量脚本时的 `card()` 辅助函数铁律**：如果你用一个 `card(headline, body, ...)` 之类的辅助函数生成卡片，函数**内部**必须把 `body` 包成列表再落盘——`"body": body if isinstance(body, list) else [body]`（单句直接传字符串也不会出错）。这是陷阱 1 在批量场景下的头号复发原因：辅助函数直接 `"body": body`，调用方传了裸字符串，于是**每一张卡**都变成骨架卡报 ERROR。同理 `data_points` 默认应为 `[]` 而非 `None`。

### `density_contract` 骨架（按 density_label 复制对应行）

`deck_bias`/`page_lower_bound`/`page_upper_bound` 3 个字段来自 outline，其余 7 个字段直接复制不要改数值：

```jsonc
// low
{"deck_bias":"<relaxed|balanced|ultra_dense>","page_lower_bound":"<outline值>","page_upper_bound":"<outline值>","max_cards":2,"max_charts":1,"min_body_font_px":24,"max_lines_per_card":3,"image_policy":"flexible","decoration_budget":"generous","overflow_strategy":"rebalance_layout"}
// mid_low
{"deck_bias":"<>","page_lower_bound":"<>","page_upper_bound":"<>","max_cards":3,"max_charts":1,"min_body_font_px":20,"max_lines_per_card":4,"image_policy":"flexible","decoration_budget":"medium","overflow_strategy":"rebalance_layout"}
// medium
{"deck_bias":"<>","page_lower_bound":"<>","page_upper_bound":"<>","max_cards":4,"max_charts":2,"min_body_font_px":18,"max_lines_per_card":5,"image_policy":"support_only","decoration_budget":"medium","overflow_strategy":"tighten_budget"}
// high
{"deck_bias":"<>","page_lower_bound":"<>","page_upper_bound":"<>","max_cards":6,"max_charts":2,"min_body_font_px":16,"max_lines_per_card":4,"image_policy":"support_only","decoration_budget":"low","overflow_strategy":"table_or_microchart"}
// dashboard
{"deck_bias":"<>","page_lower_bound":"<>","page_upper_bound":"<>","max_cards":8,"max_charts":4,"min_body_font_px":14,"max_lines_per_card":3,"image_policy":"decorate_only","decoration_budget":"minimal","overflow_strategy":"rollback_planning"}
```

---

## 目标

制定一张从布局、字体、配图策略到卡片组织的 1280x720 物理画幅精细蓝图。**本阶段只写 JSON，不写 HTML。**

---

## Phase 1：理解当前页定位

从 `outline.txt` 中找到第 N 页的定义，明确：
- `page_goal`：这一页的核心论点（一句话，不含"和"字）
- `narrative_role`：叙事角色（常用子集：cover/toc/section/section-marker/evidence/comparison/process/reference/close/cta；完整合法集见上文陷阱 5）
- `proof_type`：论证方式（数据驱动/案例/对比/框架/步骤）
- `密度下限 / 密度目标 / 密度上限`
- `节奏动作 / 信息姿态 / 锚点类型`
- deck 级 `密度倾向` 与整套 `密度曲线`
- **本页所属 `## Part N` 头部的 `论证策略`**（在 Part 块里，不在页块里）→ 据此定 `narrative_archetype`

> **硬边界**：本阶段不是重新发明这一页的密度，而是把 outline 定下的窗口冻结成单页可执行的 `density_contract`。

> **叙事 archetype（`narrative_archetype`，必填）**：读本页所属 Part 头部的 `论证策略`；若为 `reference_runbook` 则 `narrative_archetype: "reference_runbook"`，否则 `"persuasive"`。**每页都要写**——这是让下游 `planning_validator` 对参考型 deck 放宽"连续 3 页 high/dashboard"密度规则的唯一信号；漏写按 `persuasive` 处理（说服型密度规则照常生效）。参考型 archetype 详见 [`principles/narrative-arc.md` §参考型叙事](../../principles/narrative-arc.md)。

---

## Phase 2：资源发现与设计决策

运行 `resource_loader.py menu` 获取可用组件菜单后，**你是严密的架构师，不是随性的画家**。必须深刻理解物理数据类型并严丝合缝地对接组件栈：

1. **观众在这一页应该先看到什么？** → 决定你的视觉锚点和主次关系
2. **这一页的信息是怎么“流动”的？** → 决定空间布局和视觉动线
3. **这一页和上一页的视觉感受应该有什么不同？** → 决定节奏变化
4. **在菜单中的工具里，哪些能最好地服务上面 3 个答案？** → 决定 layout_hint、card_type、chart、resource_ref

> **重要**：菜单里的工具是你的工业模具库，不是随手涂鸦的画笔。对于不同的数据虽然可以跨界利用高阶模具，但必须确保逻辑自洽、严防骨架崩塌。

**填写 `resources` 字段时必须说明为什么选择该组件**（`resource_rationale` 字段）。

### 命名合同（必须区分 schema 枚举 与 资源文件 stem）

- `layout_hint` / `page_type`：写 validator 认可的值。`layout_hint` 推荐使用真实文件 stem，如 `hero-top`、`mixed-grid`、`l-shape`。
- 非 `content` 页优先通过 `page_type` 消费 `page-templates/`（如 `cover` / `toc` / `section` / `section-marker` / `reference` / `end`）。通常不需要再写 `layout_hint`；只有在要显式钉住模板正文时，才额外填写 `resources.page_template`。

### 参考型 page_type：`section-marker` 与 `reference`（何时用）

`section-marker` 与 `reference` 是**参考型 archetype**（运行手册 / 交付手册 / SOP / playbook——"用来查、不是一次性读完"的 deck）专用的 page_type。判据见 [`principles/narrative-arc.md` §参考型叙事](../../principles/narrative-arc.md)。说服型 deck 不用它们。

- **内联 `section-marker` vs 整页 `section`**：
  - 整页 `section`——说服型 deck 的 Part 首页，整页呼吸封面，`visual_weight <= 3`、几乎全留白、不放正文。观众线性观看需要情绪缓冲。
  - 内联 `section-marker`——参考型 deck 的阶段边界，`§NN` + kicker 压 2px 规线的轻量分隔条**领起正文**（顶部分隔条 + 下方 lead + 首个制品），不占整页。跳读者不需要每阶段一整页呼吸。消费 `page-templates/section-marker.md`。
- **`reference` 横切参考 back-matter**：参考型 deck 的收尾（替代 `close`/`cta` → `end` 的行动号召），一页放一个可查制品。消费 `page-templates/reference.md`，制品复用 `blocks/worksheet.md` 既有配方，按 `resources.block_refs:["worksheet"]` 注入——**不写新组件**：

  | back-matter 角色 | worksheet 配方 | card_type | block_refs |
  |------------------|----------------|-----------|------------|
  | 责任矩阵（RACI） | `responsibility-matrix` | `list` | `["worksheet"]` |
  | 质量门 / 失败模式 | `status-block` | `list` | `["worksheet"]` |
  | 升级路径 / 例会节奏 | `escalation-matrix` | `list` | `["worksheet"]` |
  | 术语表（glossary） | 原生 `card_type:list` 定义列表（**不新增配方**） | `list` | 可选 `["worksheet"]` |

- 两者均为非 `content` 页：不要求 `layout_hint`、禁 `dashboard` 密度；但仍受通用规则约束（>= 1 张卡、恰好 1 张 anchor、`director_command`、`decoration_hints`）。均携带持久页眉/页脚（`slide-header` / `slide-footer`）。
- `card_type`：写 validator 认可的枚举，如 `data_highlight`、`image_hero`、`matrix_chart`。
- `chart.chart_type`：写 validator 认可的枚举，**使用下划线命名**，如 `metric_row`、`comparison_bar`、`stacked_bar`、`progress_bar`。
- `resources.chart_refs`：写 `references/charts/` 下的**文件 stem**，而非图表类型名。有效值为 `basic`、`advanced`、`complex`、`index`（对应 `basic.md` 等文件）。**不要把 `chart_type` 值（如 `progress_bar`、`comparison_bar`）直接填到 `chart_refs` 里**——那些是枚举值，不是文件名，validator 找不到对应文件会报 ERROR。
- `resources.layout_refs`、`block_refs`、`principle_refs`：推荐写 `references/` 对应子目录中的真实文件 stem，如 `hero-top`、`visual-hierarchy`；`resource_loader.py` 会自动做下划线/连字符归一化。
- `process` 是 schema 原生 `card_type`，但当前没有 `blocks/process.md`。若使用它，必须同时给出更强的 `layout_refs`、`principle_refs`、`director_command` 和必要的 `chart_refs` / `resource_ref`，不要假设会有专属 block 正文可加载。
- **diagram 配方按 family 加载（重要）**：`card_type:diagram` 永远会注入选择器 `blocks/diagram.md`（主题契约 + 共享基元），但**每类图解的配方正文在按需加载的 family 文件里**。根据 `diagram_type` 在 `resources.block_refs` 里加上对应 family stem，否则 HTML 阶段拿不到该类配方正文：

  | diagram_type | block_refs 追加 |
  |--------------|-----------------|
  | `flowchart` `swimlane` `sequence` `state-machine` `data-flow` | `diagram-process-flow` |
  | `architecture-component` `architecture-deployment` `er-data-model` `layers` `architecture-canvas` | `diagram-architecture` |
  | `gantt` `dependency-network` `org-tree` `kanban` | `diagram-project` |
  | `mind-map` `matrix-quadrant` `venn` `pyramid` `funnel` `cycle` `hub-spoke` `onion` `fishbone` | `diagram-concept` |

  例：一页用 `diagram_type:architecture-deployment` → `"block_refs": ["diagram-architecture"]`。`timeline` 卡走 `card_type:timeline`（自动加载 `blocks/timeline.md`），不需要 family ref。

  > **`diagram_source` 必须放在卡片级，不是页顶层**：若来源文档含 Mermaid fence，把 `diagram_source` 对象放在 **diagram 卡本身**（`cards[i].diagram_source`），不要放在 JSON 顶层。页顶层放置会导致 HTML 阶段的 `mermaid_layout.py` 预处理优先级降低（仍可回退检测，但不是规范路径）。正确写法：
  > ```json
  > {
  >   "cards": [{
  >     "card_type": "diagram",
  >     "diagram_source": {
  >       "mermaid_source": "flowchart LR\n    A --> B",
  >       "origin": "<来源文件路径>",
  >       "source_ref": "<章节/fence标题>",
  >       "fence_index": 0
  >     }
  >   }]
  > }
  > ```
  > 用装配器路径时，`diagram_source` 直接写在 payload 的对应卡片对象里——装配器会原样透传。

### principle_refs 指导（重要：设计原则文件按场景选用）

`resources.principle_refs[]` 字段决定 HTML 阶段能否收到设计原则正文。按以下规则填写：

| 本页特征 | 应引用 |
|---------|--------|
| 数据图表主导页 | `data-visualization` |
| 多卡片排版，需要层次感 | `visual-hierarchy` |
| 封面/章节页，需要情绪校准 | `color-psychology` |
| 信息超密、担心认知负担 | `cognitive-load` |
| 叙事转折页（从问题到方案）| `narrative-arc` |
| 任何页面的排版构图优化 | `composition` |
| 不确定选哪个 | `design-principles-cheatsheet`（综合速查）|

在 planning JSON 中写法示例：
```json
"resources": {
  "principle_refs": ["visual-hierarchy", "composition"],
  "layout_refs": ["hero-top"],
  "block_refs": [],
  "chart_refs": ["kpi"]
}
```

填写后，`resource_loader.py resolve` 会自动把对应原则文件的完整正文注入 HTML 阶段的上下文。

---

## Phase 3：密度合同冻结（强制）

### 五档基础预算（9 字段全部必填，validator 逐一校验）

> **注意**：这 9 个字段直接来自 `scripts/planning_validator.py` 中的 `DENSITY_DEFAULTS` 字典。写批量生成脚本时请直接复用该字典而非手工重录，以避免漏字段或数值偏差（特别注意 `medium.max_charts=2`，`dashboard.max_lines_per_card=3`）。

| `density_label` | `max_cards` | `max_charts` | `min_body_font_px` | `max_lines_per_card` | `image_policy` | `decoration_budget` | `overflow_strategy` |
|---|---:|---:|---:|---:|---|---|---|
| `low` | 2 | 1 | 24 | 3 | `flexible` | `generous` | `rebalance_layout` |
| `mid_low` | 3 | 1 | 20 | 4 | `flexible` | `medium` | `rebalance_layout` |
| `medium` | 4 | **2** | 18 | 5 | `support_only` | `medium` | `tighten_budget` |
| `high` | 6 | 2 | 16 | 4 | `support_only` | `low` | `table_or_microchart` |
| `dashboard` | 8 | 4 | 14 | **3** | `decorate_only` | `minimal` | `rollback_planning` |

### 冻结规则

- `density_label` 必须落在 outline 的 `密度下限 / 密度上限` 之间。
- `density_reason` 必须说明为什么这页最终落在该档，而不是空泛地写“内容较多”。
- `density_contract` 必须显式写出 `deck_bias`、`page_lower_bound`、`page_upper_bound`、`max_cards`、`max_charts`、`min_body_font_px`、`max_lines_per_card`、`image_policy`、`decoration_budget`、`overflow_strategy`。
- `dashboard` 只允许 `content` 页使用，且优先 `mixed-grid` / `t-shape`。
- `high / dashboard` 禁 `image_hero` 主卡，禁 `hero-background` 大图。
- **跨页密度规则（你看不到邻页，但下游会连起来校验）**：validator 的 `validate_cross_page` 会拦下两类跨页问题——(a)"连续 3 页 `density_label` 落在 `{high, dashboard}`"；(b) 任何 `dashboard` 页的**前后必须至少各有 1 页非 dashboard 过渡**（deck 首/尾页放 dashboard、或两张 dashboard 相邻都会报 ERROR）。你这个单页代理受 ASI03 范围闸门约束、读不到邻页 planning，**唯一能拉的杠杆是把 `narrative_archetype` 如实写对 + 忠实沿用 outline 密度曲线**——参考型 deck（`reference_runbook`）会被豁免规则 (a)，说服型（`persuasive`）不会。所以：① 每页都必须写 `narrative_archetype`（漏写按 `persuasive` 处理）；② `density_label` 必须严格落在 outline 给的窗口内，不要为了"信息多"擅自把本该 `medium` 的页拉到 `high`——擅自抬档正是凑出连续 3 页 high 的元凶。

## Phase 4：`planningN.json` 结构合同（强制）

你的输出必须是**可直接被 `planning_validator.py` 校验的 JSON**。以下是 schema 骨架（**只展示结构，不展示设计决策** -- 布局、卡片类型、视觉风格全部由你自主决定）：

```json
{
  "page": {
    "slide_number": "<页码>",
    "page_type": "<cover/toc/section/section-marker/content/reference/end>",
    "narrative_role": "<叙事角色>",
    "narrative_archetype": "<persuasive | reference_runbook — 由本页所属 Part 的 论证策略 推导>",
    "title": "<页标题>",
    "page_goal": "<一句话核心论点>",
    "audience_takeaway": "<观众带走什么>",
    "visual_weight": "<1-9 信息密度整数；validator 只接受 1..9，写 10 会报 ERROR>",
    "density_label": "<low/mid_low/medium/high/dashboard>",
    "density_reason": "<为什么这一页最终落在这个密度档>",
    "density_contract": {
      "deck_bias": "<relaxed/balanced/ultra_dense>",
      "page_lower_bound": "<来自 outline 的密度下限>",
      "page_upper_bound": "<来自 outline 的密度上限>",
      "max_cards": "<整数>",
      "max_charts": "<整数>",
      "min_body_font_px": "<整数>",
      "max_lines_per_card": "<整数>",
      "image_policy": "<flexible/support_only/decorate_only>",
      "decoration_budget": "<generous/medium/low/minimal>",
      "overflow_strategy": "<rebalance_layout/tighten_budget/table_or_microchart/rollback_planning>"
    },
    "layout_hint": "<你的布局选择>",
    "layout_variation_note": "<与上一页的结构对比（如果有微调），要求详尽>",
    "focus_zone": "<视觉焦点区域描述>",
    "negative_space_target": "<high/medium/low>",
    "page_text_strategy": "<文字策略>",
    "rhythm_action": "<推进/爆发/缓冲/收束>",
    "must_avoid": ["<你认为这页最危险的平庸设计陷阱>"],
    "variation_guardrails": {
      "same_gene_as_deck": "<哪些元素跨页保持统一>",
      "different_from_previous": ["<与上一页的具体变化维度>"]
    },
    "director_command": {
      "mood": "<你为这页设定的情绪基调>",
      "spatial_strategy": "<你的空间编排策略>",
      "anchor_treatment": "<你怎么处理视觉锚点>",
      "techniques": ["<你选用的技法编号>"],
      "prose": "<用电影镜头语言描述这页的视觉感受>"
    },
    "decoration_hints": {
      "background": {"feel": "<>", "restraint": "<>", "techniques": ["<>"]},
      "floating": {"feel": "<>", "restraint": "<>", "techniques": ["<>"]},
      "page_accent": {"feel": "<>", "restraint": "<>", "techniques": ["<>"]}
    },
    "source_guidance": {
      "brief_sections": ["<素材引用路径>"],
      "citation_expectation": "<引用策略>",
      "strictness": "<证据边界>"
    },
    "resources": {
      "page_template": "<null 或页面模板 ref>",
      "layout_refs": ["<你的 layout ref>"],
      "block_refs": [],
      "chart_refs": ["<你选用的 chart ref>"],
      "principle_refs": ["<你需要的设计原则>"],
      "resource_rationale": "<为什么选这些资源，必须说明理由>"
    },
    "cards": [
      {
        "card_id": "<s页码-role-序号>",
        "role": "<anchor/support/context>",
        "card_type": "<你的卡片类型选择>",
        "card_style": "<你的视觉变体选择>",
        "argument_role": "<claim/evidence/contrast/constraint/method/synthesis/prerequisite/framework — 不含 context>",
        "headline": "<精炼标题>",
        "body": ["<正文字符串数组>"],
        "data_points": [{"label": "<>", "value": "<>", "unit": "<>", "source": "<>"}],
        "chart": {"chart_type": "<你的图表类型>"},
        "content_budget": {"headline_max_chars": 12, "body_max_bullets": 3, "body_max_lines": 3},
        // ↑ body_max_lines 必须 ≤ 本页 density_contract.max_lines_per_card
        //   （low=3 / mid_low=4 / medium=5 / high=4 / dashboard=3）。给的是最安全值 3；
        //   照抄 5 会在 low/mid_low/high/dashboard 页报 ERROR。
        "image": {
          "mode": "<generate/provided/manual_slot/decorate>",
          "needed": "<true/false>",
          "usage": "<null 或图片用途>",
          "placement": "<null 或放置位置>",
          "content_description": "<null 或描述>",
          "source_hint": "<null 或路径>",
          "decorate_brief": "<装饰说明>"
        },
        "resource_ref": {"chart": "<>", "principle": "<>"}
      }
    ],
    "workflow_metadata": {
      "stage": "planning",
      "workflow_version": "2026.04.09-v4.1",
      "planning_schema_version": "4.1",
      "planning_packet_version": "4.1",
      "planning_continuity_version": "4.1"
    }
    // ↑ 版本字符串必须精确匹配 scripts/workflow_versions.py 中的常量。
    //   批量生成脚本中直接从该模块 import 而不要硬编码字符串：
    //   from workflow_versions import build_workflow_metadata
    //   "workflow_metadata": build_workflow_metadata("planning")
  }
}
```

> **重要提醒**：以上每个 `<>` 占位符最终都将落地为坚如磐石的代码。你需要如严密工程师一般，根据本页的内容、受众和物理界限出具精确的排版装配图。

### 必填字段与枚举底线

- 顶层页字段至少要有：`slide_number`（整数）、`page_type`、`title`、`page_goal`、`cards`、`visual_weight`、`density_label`、`density_reason`、`density_contract`、`director_command`、`decoration_hints`、`resources`、`workflow_metadata`；`content` 页还必须有 `source_guidance`。
- `visual_weight`：**1..9 之间的整数**（不是 1-10，写 10 报 ERROR）。
- `page_type`：`cover` / `toc` / `section` / `section-marker` / `content` / `reference` / `end`
- `narrative_role`：与 outline 的叙事角色对齐，常用子集为 `cover` / `toc` / `section` / `section-marker` / `evidence` / `comparison` / `process` / `reference` / `close` / `cta`（完整合法集见陷阱 5；非法值仅报 WARN）
- `density_label`：`low` / `mid_low` / `medium` / `high` / `dashboard`
- `density_contract.image_policy`：`flexible` / `support_only` / `decorate_only`
- `density_contract.decoration_budget`：`generous` / `medium` / `low` / `minimal`
- `density_contract.overflow_strategy`：`rebalance_layout` / `tighten_budget` / `table_or_microchart` / `rollback_planning`
- 内容页必须有 `layout_hint`，并从 validator 认可的集合中选，如 `single-focus`、`symmetric`、`asymmetric`、`three-column`、`primary-secondary`、`hero-top`、`mixed-grid`、`l-shape`、`t-shape`、`waterfall`
- `cards[].role`：`anchor` / `support` / `context`。**每页恰好 1 张 `anchor`**（缺失或多于 1 张都报 ERROR）。
- `cards[].card_style`：`accent` / `elevated` / `filled` / `outline` / `glass` / `transparent`。**`content` 页有 ≥2 张卡时，必须出现 ≥2 种不同的 `card_style`**（不能全同一种）。
- `cards[].card_type`：`text` / `data` / `list` / `process` / `tag_cloud` / `data_highlight` / `timeline` / `diagram` / `quote` / `comparison` / `people` / `image_hero` / `matrix_chart`
- `cards[].chart.chart_type`（若有图表）：`kpi` / `metric_row` / `sparkline` / `comparison_bar` / `ring` / `stacked_bar` / `timeline` / `funnel` / `radar` / `treemap` / `waffle` / `progress_bar` / `rating`
- `cards[].image.usage`（`needed=true` 时）：`hero-background` / `inline-illustration` / `icon-accent` / `data-visualization-bg`
- `cards[].image.placement`（`needed=true` 时）：`full-bleed` / `left-half` / `right-half` / `card-bg` / `inline`
- `cards[].body` 必须是**字符串数组**，不要写成单个字符串
- `cards[].data_points` 必须是对象数组；有数字时尽量带 `source`
- `cards[].content_budget` 必须是对象；哪怕是最小对象也要显式写出。它还必须服从页级 `density_contract`
- `cards[].image.needed = true` 时，`usage` / `placement` / `content_description` / `source_hint` 都必须填写；否则这些字段应为 `null`

### 密度专项底线

- `cards` 总数不得超过 `density_contract.max_cards`
- 有 `chart.chart_type` 的卡片数不得超过 `density_contract.max_charts`
- 每张卡的 `content_budget.body_max_lines` 不得超过 `density_contract.max_lines_per_card`
- `dashboard` 页不得使用 `image_hero` 卡片，不得把大图当主锚
- `dashboard` 页的 `image_policy` 必须是 `decorate_only`

---

## Phase 5：图片策略决策（必须明确，不得含糊）

| 模式 | 适用场景 | 必填字段 |
|------|---------|---------|
| `generate` | 封面页、章节页、需要强视觉冲击的核心页 | `image.needed=true`、`usage`、`placement`、`content_description`、`source_hint`（目标落盘路径）、`image.prompt`（英文图生图提示词） |
| `provided` | 用户已提供图片/品牌图库/截图 | `image.needed=true`、`source_hint`（真实本地路径）|
| `manual_slot` | 用户后续自己补图，先占位 | `image.needed=false`、`image.slot_note` 说明槽位位置、比例、替换建议 |
| `decorate` | 数据页、逻辑页、纯排版页 | `image.needed=false`、`image.decorate_brief` 说明内部视觉语言（SVG/渐变/色块/水印/字体装饰）|

**禁止留模棱两可的 mode。选定后不得在 HTML 阶段临时改变。**

**额外密度约束**：
- `low / mid_low`：可使用更自由的图片策略
- `medium`：图片只能做支撑，避免吞掉正文
- `high`：不得用 `hero-background`，图片只可做支撑或局部说明
- `dashboard`：默认 `decorate`，不得把大图当主锚

---

## Phase 6：你是架构师，纪律与创意并重

> **核心理念**：上面的 Phase 2 菜单、Phase 3 密度合同和 Phase 4 schema 不是让你随意发挥的草稿，而是你作为架构设计者定下的**硬性工程图纸**。真正的创意，是在极致严酷的约束条件内绽放的。

**绝对的执行纪律（The Execution Discipline）：**
- `layout_hint` **是界面的黄金承重墙**。在下游的渲染阶段，它将被**以不妥协的精确度**映射到真实的 DOM 网格结构上，不可随意打破原有的版面重心设定。
- `card_type` 和 `chart_type` 意味着**特定设计规范的强制降临**。选定了特定类型，就必须遵循其最佳实践，否则后续的图审环节将直接把页面打回重做。
- `director_command` 是你的图纸批注 —— 这是对空间利用的更高维度说明，指导下游在不破坏骨架的前提下，该着重把哪些 CSS 精工细作落实。图审也不会为你善后，必须指令严密。
- `must_avoid` 是致命红线 —— 每页至少写 1 条真正有意义的禁区，提醒自己在边界内做到最好，主动拒绝平庸妥协。

**图审警示**：你在此阶段定下的所有结构决策，都必须对最终代码全权负责。不要以为有“像素级图审”兜底就可以随意偏离框架，图审是用来打磨微调的，绝不是来擦屁股和重构骨架的。

---

## Phase 7：cards 字段填充规范

每张卡片必须包含：
- `card_id`：稳定唯一，建议 `s{页码}-{anchor|support|context}-{序号}`
- `role`：`anchor` / `support` / `context`
- `card_type`：validator 枚举值，如 `text` / `data` / `list` / `process` / `data_highlight` / `timeline` / `diagram` / `quote` / `comparison` / `people` / `image_hero` / `matrix_chart`
- `card_style`：6 种合法视觉变体之一
- `headline`：标题（精炼，不超过 12 字）
- `body`：正文字符串数组，不能为空
- **【反泄漏铁律】**：`headline` 和 `body` 里面**只能且必须**填写最终展示给观众看的内容文案！绝不准许把纲要里的“旁白说明”、“工作动作”、“排版大意”（例如：*“这一页先把整场内容压缩成地图，再看拆解”* 这种明显属于幕后解说的话）当成台词本填进去！所有面向设计的幕后说明请扔进 `director_command`，若将工作指导语暴露在卡片正文上将被视为重大设计事故！
- **【反捏造铁律 / 可溯源否则省略】**：`headline` / `body` / `data_points` / 引语归属里的任何**具体事实**都必须来自资料或用户输入——不只是数字，还包括**联系方式（邮箱/电话/网址/账号/二维码）、人名/职衔/机构名、引语的出处、日期/引用**。无可溯源真值时**宁可省略该项或留显眼占位**（如 `[演讲人邮箱]`），**绝不填一个像真的假值**（凭空编一个联系邮箱是重大事故——它看着可信、会被当真发出去）。参见 [`../../method.md`](../../method.md) §7 可溯源否则省略。
- `data_points`：如有数值则填对象数组
- `content_budget`：内容预算对象，且必须服从页级 `density_contract`
- `image`：完整图片合同对象，带 `mode`。**重要**：`needed=true` 时必填 `content_description` 和 `source_hint`（不是 `prompt`）；`needed=false` 时 `usage`/`placement`/`content_description`/`source_hint` 都必须是 `null`，不得出现非 null 值。
- `resource_ref`：需要定向绑定某个 block/chart/principle 时写这里
- `image.slot_note` / `image.decorate_brief`：按图片模式按需补充

可选但推荐：
- `argument_role`
- `chart`

**不得出现空 `body` 的卡片。**

---

## Phase 8：设计意图传递字段

在坚守骨架的基础上拔高呈现品质。请严格定义并使用以下字段，向 HTML 阶段下达你的精确工程指令与微雕方案，它们构成了后续视觉落地的强制合同：

- `focus_zone`：提议的主张和视觉焦点区域
- `must_avoid`：明确提配 HTML 阶段不要陷入的平庸模板化设计
- `director_command`：给出富有创意性的结构、锚点和高级技法方向
- `decoration_hints`：描述装饰强度与视觉层次
- `source_guidance`：约束证据边界与引用期望
- `resources` / `resource_ref`：推荐消费的组件资源

---

## Phase 9：自审（强制）

运行 `planning_validator.py`，直到零 ERROR：

```bash
python3 SKILL_DIR/scripts/planning_validator.py $(dirname PLANNING_OUTPUT) --refs REFS_DIR --page PAGE_NUM
```

- ERROR 必须全部修复才能 FINALIZE
- WARNING 建议修复，不强制
- 自审通过后立即发送 FINALIZE，然后等待 HTML 阶段指令
