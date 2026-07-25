# 三栏等宽版式

> 3 列内容并列。
> 空间划分：1fr 1fr 1fr 列。三栏等宽并列。
> 适用数据：parallel_items / pricing_plans / team_profiles / phase_overview / scoping_matrix（3个等重并列元素）。

适用：3 个并列比较（三大优势、三个阶段、三个产品线）

---

## 默认实现：统一列面板（推荐）

**并列内容优先使用 `columnar-panel` 块（`block_refs: ["columnar-panel"]`）而非三个独立卡片。**

统一列面板：
- 单一外框容器（`border:1px solid var(--rule); border-radius:10px; overflow:hidden`）
- 列间只用 `border-right:1px solid var(--rule)` 分隔，末列无右边框
- 每列内一个 `col-header`（大写 + 2px accent 色底边），可加 `section-label` 和 `bullet-dot`
- 可选：在外框顶部加一条 accent 色顶栏（含 eyebrow / 主标题 / 副标题），顶栏与列面板无缝连接

具体 HTML 骨架见 [`blocks/columnar-panel.md`](../blocks/columnar-panel.md)（A 组基础三列 / B 组带顶栏）。

### 反 AI 感铁律 —— 禁止三个独立描边卡片并排

> **三张 `border + border-radius + box-shadow` 的卡片并排 = 最典型的 AI PPT 信号。**
> 独立卡框对等地"框住"每一列，会让画面显得像网页 UI 组件库，而非演讲设计。
> 唯一例外：某列需要做 `accent` / `elevated` 强调（一页最多 1 张），可单独拔高该列。

---

## 灵动化指引

### 统一面板内的列差异化

三列共享外框并不代表"三栏完全一样"——视觉差异通过以下方式注入：

1. **列头色彩的梯度**：第 1 列用 `var(--focus)`（最强）、第 2 列用 `var(--secondary)`、第 3 列用 `var(--dim)`（最弱 / muted），在同一容器内制造主次层级
2. **徽章语义编码**：每列顶部的状态徽章（green / amber / gray）从视觉上传达列的状态，取代重复的 card_style 差异
3. **内容密度的波浪**：三列的项目数不必相同，形成节奏感（多 / 中 / 少）
4. **section-label 的颗粒度**：第 1 列可有多个 section-label 分段，第 3 列可以不分段（内容稀疏）

### 什么时候仍用三个独立卡片

以下场景可突破统一面板，用独立卡片：
- 三列中有一列需要 `accent` / `elevated` 强调（该列独立拔高，其余两列用统一面板或更轻量处理）
- 每列内容的结构差异极大（一列含 `data_highlight`，一列含 `timeline`，一列含纯文本）

### 跨列装饰

可在三列面板上方或下方叠加一个 `transparent` 跨列容器（如一行汇总标签、总结句、指标横幅），在保持主体并列结构的前提下加强跨列叙事。

### 布局控制

三列等分由外容器 `display:grid; grid-template-columns:1fr 1fr 1fr` 控制，不需要写 `grid-row` / `grid-column`。
