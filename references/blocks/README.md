# 区域展示组件库 -- PPTX 演讲设计语言

> 复合组件不是"网页 UI 组件"，而是**信息叙事的视觉载体**。每个组件是一种独特的信息组织方式，承载着特定的演讲节奏和观众情绪。

## 组件总表

| card_type | 叙事角色 | 文件 |
|----------|---------|------|
| `timeline` | **时间的河流** -- 让历史/进程产生流动感 | `timeline.md` |
| `diagram` | **结构的星图** -- 让抽象关系变得可触摸 | `diagram.md` |
| `quote` | **灵魂的锚点** -- 用权威之声为论述加冕 | `quote.md` |
| `comparison` | **碰撞的擂台** -- 让对立面产生戏剧性张力 | `comparison.md` |
| `people` | **面孔的力量** -- 用人物拉近与观众的距离 | `people.md` |
| `image_hero` | **画面的沉浸** -- 用图像制造情感冲击波 | `image-hero.md` |
| `matrix_chart` | **象限的定位** -- 用二维坐标揭示战略位置 | `matrix-chart.md` |

## 选择指南

| 内容特征 | 推荐组件 | 为什么 |
|---------|---------|-------|
| 时间顺序的事件（4-8 个）/ SDLC 相位叙事面板 | **timeline**（含 `phase-engagement-timeline` 变体） | 时间线让观众感受到"进程的动力"；相位叙事面板用左色边 + 阶段药丸 + 交付物列表呈现项目阶段 |
| 架构/流程/多层关系 | **diagram** | 图解让观众从"听描述"变成"看全景" |
| 权威引用/颠覆性观点 | **quote** | 金句是演讲中"让全场安静一秒"的武器 |
| A vs B 对比决策 | **comparison** | 并排对比让观众"自己得出结论"而非被动接受 |
| 团队/人物展示 | **people** | 面孔是建立信任最快的通道 |
| 情感冲击/场景营造 | **image_hero** | 一张好图胜过千言万语 |
| 2x2 战略定位分析 | **matrix_chart** | 象限图是商业决策最直觉的工具 |
| 责任矩阵/填空工作表/逐日排期表/覆盖度矩阵/严重性发现表 | **worksheet**（按需加载） | 桌面文档式表格——可在会上逐格签字讨论 |
| 论证卡/条件列表/相位流/估算斜坡/诚实横幅/标记型计划卡 | **advisory-brief**（按需加载） | 顾问战略简报——每张卡以一句 so-what 收束 |
| 双 callout/评分看板/洞察卡/综合主题/热力图/发现追踪/优先级矩阵/AI 成熟度/锚定问题 | **discovery-readout**（按需加载） | 咨询发现汇报原语——证据优先、假设驱动、开放式前瞻问题 |

## discovery-readout 原语（按需加载）

`discovery-readout` 同为**按需注入配方**（非 validator 枚举）：在 `data` / `list` / `text` 卡上写 `resources.block_refs:["discovery-readout"]` 加载 [`blocks/discovery-readout.md`](discovery-readout.md) 的整套"咨询发现汇报"原语，分五组：

- **A. 摘要 & 证据**：双 callout 摘要面板（左色 = 发现、右色 = 含义）· 数字统计看板（5–6 枚等宽大数字 + 大写标签）。
- **B. 洞察 & 主题**：阶段映射洞察卡网格（3×2，顶边高亮 + SDLC 阶段药丸）· 综合主题卡（深色标题栏 + 观察 + 假设框 + 编号机会）。
- **C. 方法论 & 前瞻**：方法论三栏网格（编号步骤 / 聚焦领域 / 大数字三栏竖线分隔）· 锚定问题面板（开放式前瞻问题编号左条行）。
- **D. 分类 & 参考**：AI 成熟度分类（四级横向进阶 + 最高级主色顶边）· 机会类型徽章条（六类 + AI 高亮）· 覆盖热力图（HTML `<table>` 黑表头 + 双色计数药丸）。
- **E. 追踪 & 优先级**：发现追踪表（深色分组标题行 + 严重性徽章，碳out `#ef4444`/`#b35900`）· 优先级评分矩阵（分组列头 + 1–4 热力色标）· 影响力-投入定位图（SVG 圆点 + HTML 叠加标签，禁 `<text>`）。

全部绑定 deck 契约变量（焦点 = `var(--accent-1)`、次色 = `var(--accent-2)`、纸 = `var(--card-bg-from)`/`var(--card-bg-to)`、墨 = `var(--text-primary)`、规线 = `var(--card-border)`），换风格随 `:root` 改色；与 `dark_professional` / `light_premium` 最契合。**管线安全**：真实 `<div>`/`<table>`、SVG 仅 `<circle>`/`<line>`/`<polygon>`/`<rect>` + HTML 叠加标注（禁 `<text>`）；仅 `findings-tracker` severity 及 `prioritization-scorecard` 热力色是语义信号 hex 碳out。

## 灵动组合原则

- 复合组件自带视觉骨架，推荐 `transparent` card_style -- 方块包裹是画蛇添足
- 一页中复合组件与基础卡片共存时，让复合组件用跨列成为画面的主角，基础卡片退为配角
- 同一页不宜超过 1 个跨列跨行的复合组件，否则两个"主角"会互相抢戏
- 当复合组件用 `transparent` 裸露在画面中时，它的视觉张力来自组件自身的结构（轴线、节点、面板），不需要额外的卡片边框去"框住"它

## diagram 配方族（按需加载）

`diagram` 不是单文件：`blocks/diagram.md` 是**永远注入的选择器 + 主题契约 + 共享基元**，每类图解的配方正文在四个 family 文件里，由 planning 的 `block_refs` 按 `diagram_type` 选取（见 `playbooks/step4/page-planning-playbook.md` 的映射表）：

| family 文件 | 覆盖的 diagram_type |
|------------|---------------------|
| `diagram-architecture.md` | architecture-component / architecture-deployment / er-data-model / layers / architecture-canvas |
| `diagram-process-flow.md` | flowchart / swimlane / sequence / state-machine / data-flow |
| `diagram-project.md` | gantt / dependency-network / org-tree / kanban |
| `diagram-concept.md` | mind-map / matrix-quadrant / venn / pyramid / funnel / cycle / hub-spoke / onion / fishbone |

**主题契约**：所有图解颜色/字体只绑定 deck 的 CSS 变量（经 `diagram.md` 的 `--node-*` 局部变量），换风格整图随 `:root` 改色。**管线安全**：箭头 SVG `<polygon>`、连线真实 `<div>`/SVG `<line>`、标注 HTML 叠加、禁 SVG `<text>`，由 `scripts/lint_diagram_recipes.py` 把关。

## worksheet 原语（按需加载）

`worksheet` 不是独立 `card_type`（不入 validator 枚举），而是与 diagram family 同机制的**按需注入配方**：在 `data` / `list` / `timeline` / `text` 卡上写 `resources.block_refs:["worksheet"]` 加载 [`blocks/worksheet.md`](worksheet.md) 的整套"编辑部技术文档"原语，分三组：

- **A. 表格 & 工作表**：责任矩阵（RACI，黑表头 + R 单一强调）· 填空讨论工作表（浮起 mono 页签 + 字段名/内容两列）· 日程表（期号 + 任务复选 + 责任人）· 升级路径表（when → trigger → action，含 cadence 变体）· 覆盖度矩阵（category × dimension 密度编码，深色 = 强 / paper-2 = 局部 / 破折号 = 缺口）· 严重性发现表（深色分组标题行 + High/Med/Low 徽章，carbout `#ef4444`/`#b35900`）。
- **B. 清单 & 状态**：清单 checklist（黑条标题 + ☐ 行，含 preflight / TOC 变体）· 状态块 status-block（gate 绿 / failure 琥珀 + 虚线补救，消费信号色）。
- **C. 页面骨架（本风格签名）**：masthead 顶栏 · cover-header 封面头（Fraunces 斜体紫 em + meta 网格）· section-marker 章节标记 · spotlight-callout 聚光标注 · footer 页脚。

全部绑定 deck 契约变量（黑表头 = `var(--text-primary)`、发丝 = `var(--card-border)`、焦点 = `var(--accent-1)`），换风格随 `:root` 改色；与 `schematic_blueprint`（`diagram_mode:"lineart"`）最契合，其**样式细则**（边框层级 / 黑底反白反转 / 斜体紫 em / mono 字距阶梯 / 间距节奏）见 [`styles/light.md` §10](../styles/light.md)。**管线安全**：真实 `<table>`/`<div>`、禁 SVG `<text>`、禁 `mask-image`/`conic-gradient`/`background-image:url()`；仅 `status-block` 的 warn/ok 是语义信号 hex 碳out。

## advisory-brief 原语（按需加载）

`advisory-brief` 同为**按需注入配方**（非 validator 枚举）：在 `data` / `list` / `timeline` / `text` 卡上写 `resources.block_refs:["advisory-brief"]` 加载 [`blocks/advisory-brief.md`](advisory-brief.md) 的整套"顾问战略简报"原语，分三组：

- **A. 论证卡族**：顶栏彩条论证卡（per-card 信号彩条 + psec 分段小标 + 底部 so-what netline）· so-what 收束行（`Therefore/Result` 金 kicker + heading 结论，可单独复用）· 标记型计划卡（`--cdot` 左边框 + 标题/描述/类别徽章，支持 2×N 网格或 `1/-1` 满宽跨列）。
- **B. 排序列表 & 相位带**：优先级条件列表（key/minor/red + 转角标签 + 焦点左条）· 相位流（彩条顶边列 + 箭头相接）· 优先级药丸带（标签 + 彩条药丸）。
- **C. 强调 & 页面骨架**：焦点洗色面板 callout（实色 + 焦点左条）· 诚实横幅 illustrative-banner（估算数字页顶必挂，消费 warn 信号色）· 估算斜坡图 projection-ramp（SVG path + HTML 叠加标注，禁 `<text>`）· 页眉页脚骨架 page-chrome（topbar + 金渐变 rule + pagefoot）。

全部绑定 deck 契约变量（焦点 = `var(--accent-1)`、per-card = inline `--cdot`、发丝 = `var(--card-border)`），换风格随 `:root` 改色；与 `graphite_gold` 最契合，其**样式细则**（顶栏彩条 / so-what 纪律 / 单一香槟金焦点 / 金渐变规线 / 诚实横幅）见 [`styles/dark.md` §8](../styles/dark.md)。**管线安全**：真实 `<div>`、SVG 仅 `<path>`/`<line>`/`<circle>`（标注用 HTML 叠加、禁 SVG `<text>`）、禁 `mask-image`/`conic-gradient`/`background-image:url()`；仅 `illustrative-banner` 的 warn 是语义信号 hex 碳out。
