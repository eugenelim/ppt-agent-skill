# diagram（图解块）-- 结构的星图

> 适用数据类型：hierarchies / architecture_diagram / cycle_flow / decision_tree / pyramid_layers / stakeholder_map / process / project_plan。
> 本文件是**选择器 + 主题契约 + 共享基元**，永远随 `card_type:diagram` 注入。具体的每类图解配方在按需加载的 family 文件里（见下表），由 planning 的 `block_refs` 选取，避免一次灌入全部配方。
> 推荐 card_style：transparent（图解自带视觉骨架，方块包裹是画蛇添足）。推荐布局：single-focus / t-shape。
> **管线铁律**：本块所有配方走 HTML→SVG→PPTX，必须遵守 [pipeline-compat.md](../pipeline-compat.md)。箭头用内联 SVG `<polygon>`，连线用真实 `<div>` 或 SVG `<line>`/`<path>`，文字标注一律 HTML 叠加（禁 SVG `<text>`）。

## 配方选择器（diagram_type → family 文件 → block_ref）

按 `diagram_type` 在 planning 的 `resources.block_refs` 里加上对应 family 文件名，HTML 阶段只会注入用到的那一族。

| diagram_type | 何时用 | family 文件 / block_ref |
|--------------|--------|------------------------|
| `flowchart` `swimlane` `sequence` `state-machine` `data-flow` | 步骤/决策逻辑、谁做哪步、时序消息、状态机、数据流 | `diagram-process-flow` |
| `architecture-component` `architecture-deployment` `er-data-model` `layers` | 组件/分层架构、部署/云/网络拓扑、数据模型、技术栈分层 | `diagram-architecture` |
| `gantt` `dependency-network` `org-tree` `kanban` | 排期/路线图/里程碑、依赖网络/PERT、组织树/WBS、看板 | `diagram-project` |
| `mind-map` `matrix-quadrant` `venn` `pyramid` `funnel` `cycle` `hub-spoke` `onion` `fishbone` `spectrum-marker` `iceberg` `force-field` `before-after` `causal-loop` `consultant-2x2` `quadrant-trajectory` | 思维导图、矩阵/象限(含 SWOT/RACI/风险)、韦恩、金字塔、漏斗、循环/飞轮、中心辐射、同心圆、鱼骨、光谱定位、冰山、力场分析、前后/差距、因果回路；`consultant-2x2` / `quadrant-trajectory` 为 `matrix-quadrant` 变体（同族路由） | `diagram-concept` |

> 兼容旧枚举：`pyramid` / `flowchart` / `hub-spoke` / `cycle` / `layers` 仍各自有同名配方（`layers` 为分层栈，归在 architecture family），不改名、不别名。

## 主题契约（强制 -- 这是图解"有主题"的根）

图解不得自带调色板。每个图解根容器先把**局部语义变量**绑定到 deck 的 CSS 变量，所有节点/连线/文字只引用这些局部变量；换风格时整张图随 `:root` 自动改色，节点内部零硬编码颜色。

```css
.diagram {
  --node-bg-from: var(--card-bg-from);   /* 节点底色（渐变起） */
  --node-bg-to:   var(--card-bg-to);     /* 节点底色（渐变止） */
  --node-border:  var(--card-border);    /* 节点描边 */
  --node-radius:  var(--card-radius, 8px);
  --node-fg:      var(--text-primary);   /* 节点主文字 */
  --node-fg-dim:  var(--text-secondary); /* 节点次文字/标注 */
  --edge:         var(--card-border);    /* 普通连线 */
  --edge-strong:  var(--accent-1);       /* 强调连线/关键路径 */
  --node-accent:  var(--accent-1);       /* 焦点/高亮节点 */
  --node-accent-2:var(--accent-2);       /* 第二强调（分组/对比） */
  --label-font:   var(--font-primary);
  font-family: var(--label-font);
}
```

内联 SVG 直接引用这些变量：`stroke="var(--edge)"`、`fill="var(--node-accent)"`（CSS 变量会被继承进内联 SVG）。**禁止**在节点/连线里写 `#xxxxxx`、`rgb(...)`；唯一例外是趋势绿 `#22c55e` / 红 `#ef4444`。

## 线稿模式 (line-art) — 主题门控（默认关闭，仅特定主题开启）

**这是"Claude/编辑部式"锐利线稿图解的实现方式：不新增任何配方，只重绑主题契约的局部变量。**

判定：读当前 `style.json` 的 `decorations.diagram_mode`。

- **`"filled"` 或该键缺失（25+ 既有风格全部如此）** → 图解按上文默认契约渲染（填充节点 + 渐变底 + accent 描边）。**视觉零变化。**
- **`"lineart"`（仅 `schematic_blueprint` 等线稿主题）** → 生成图解 HTML 时，把每个配方**根容器**上内联声明的局部变量改写为下方线稿规制。因为每个配方的 `.diagram` 根都是自带一份内联 `--node-* : var(--card-*)` 绑定（不走中央级联），所以线稿化是**在根容器上覆写这几个变量**，其余模板 body 一字不改。

**根容器覆写（filled → lineart 对照）：**

```css
/* filled（默认）：节点有渐变底 + 卡片描边 */
.diagram {
  --node-bg-from: var(--card-bg-from);
  --node-bg-to:   var(--card-bg-to);
  --node-border:  var(--card-border);
  --label-font:   var(--font-primary);
}
/* lineart：节点透明无填充、发丝描边、mono 标注、仅焦点着色 */
.diagram {
  --node-bg-from: transparent;         /* 节点无填充 —— 只剩线 */
  --node-bg-to:   transparent;
  --node-border:  var(--card-border);  /* 发丝细线（本主题 card.border 即 1px hairline）*/
  --edge:         var(--card-border);  /* 连线同为发丝 */
  --edge-strong:  var(--node-accent);  /* 关键路径才用强调色 */
  --label-mono:   var(--font-mono);    /* 端口/坐标/轴标/图号走等宽 */
  --label-font:   var(--font-primary); /* 人类可读节点名仍用 sans/serif 主字体 */
}
```

**线稿模式五铁律：**

1. **透明节点**：`--node-bg-from/to` 置 `transparent`，共享基元里的 `linear-gradient(var(--node-bg-from),var(--node-bg-to))` 自然渲染为无填充 —— 无需改基元。
2. **发丝描边**：所有 `stroke-width` 收到 `1`（关键路径 `1.2`），描边取 `var(--edge)`；焦点节点用 `border-color:var(--node-accent)`。
3. **焦点纪律**：`--node-accent` 只落在 **1–2 个焦点节点/关键路径**上，其余全部 `--node-fg`/`--node-fg-dim`。强调色用在 5 个节点上等于没有强调。
4. **mono 承载技术标注**：端口、URL、字段类型、坐标、轴标签、图号用 `font-family:var(--label-mono)`；节点**名称**仍用主字体（`--label-font`）。别把等宽体当"技术味"滤镜全局套。
5. **零投影零大圆角**：不加 `box-shadow`；`--node-radius` 收到 `4px` 或 `0`。层次靠线与留白，不靠阴影。

**管线安全**：以上全部是 `var(...)` 与 `transparent` 关键字，无硬编码颜色、无 `<text>`、无 `mask-image`/`conic-gradient`/伪元素 —— 与默认契约同样安全。线稿模式是**变量重绑**，不是新配方，因此上文所有 family 配方（本族与 process-flow/architecture/project）自动获得线稿变体。

## 共享基元（所有 family 配方复用，均为管线安全写法）

### 1. 节点盒（themed node）
```html
<div style="
  display:flex; flex-direction:column; gap:4px; justify-content:center;
  min-width:120px; min-height:56px; padding:12px 16px; box-sizing:border-box;
  background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
  border:1px solid var(--node-border); border-radius:var(--node-radius);
  color:var(--node-fg); font-size:14px; line-height:1.4;
">
  <span style="font-weight:700;">节点标题</span>
  <span style="font-size:12px; color:var(--node-fg-dim);">描述（可选）</span>
</div>
```
焦点节点：`border-color:var(--node-accent); box-shadow:0 0 0 1px var(--node-accent);` 或 `background:var(--node-accent); color:var(--card-bg-from);`。

### 2. 连线（connector）-- 真实元素，禁伪元素
```html
<!-- 直线：真实 div（水平） -->
<div style="height:2px; background:var(--edge); align-self:center; flex:1;"></div>
<!-- 折线 / 曲线 / 斜线：内联 SVG path/line，overflow 可溢出格子 -->
<svg viewBox="0 0 100 40" preserveAspectRatio="none" style="width:100%;height:40px;overflow:visible;display:block;">
  <path d="M0 20 H50 V4 H100" fill="none" stroke="var(--edge)" stroke-width="2"/>
</svg>
```

### 3. 箭头（arrowhead）-- 内联 SVG `<polygon>`，禁 CSS border 三角形
```html
<svg viewBox="0 0 120 16" preserveAspectRatio="none" style="width:100%;height:16px;overflow:visible;display:block;">
  <line x1="0" y1="8" x2="104" y2="8" stroke="var(--edge-strong)" stroke-width="2"/>
  <polygon points="104,2 118,8 104,14" fill="var(--edge-strong)"/>
</svg>
```
（需要随路径旋转时，手动给 polygon 算好顶点坐标；不依赖 `<marker orient>`，下游渲染器对其支持不稳。）

### 4. 文字标注 -- HTML 绝对定位叠加，禁 SVG `<text>`
```html
<div style="position:relative;">
  <svg viewBox="0 0 200 100" style="width:100%;height:100%;"><!-- 只画图形 --></svg>
  <span style="position:absolute; left:30%; top:40%; font-size:12px; color:var(--node-fg-dim);">标注</span>
</div>
```

### 5. 8px 栅格纪律（让图"工整如工程图"）
- 节点放置用 CSS Grid（`display:grid; gap:16px` 等 8 的倍数）或 Flex；同层节点等宽等高。
- 所有 padding/gap/偏移取 4/8/16/24/32px。
- `align-items:center; justify-items:center` 让节点在格内光学居中。
- 连线 SVG 用 `overflow:visible` 以越出所在格连到相邻节点。

## 管线安全自检（每个 family 配方都要过）
- [ ] 颜色/字体全部来自主题契约的局部变量（无硬编码，趋势绿红除外）
- [ ] 内联 SVG 内**无 `<text>`**；标注全是 HTML 叠加
- [ ] 箭头是 SVG `<polygon>`；无 CSS border 三角形（`width:0` 技巧）
- [ ] 连线是真实 `<div>` 或 SVG `<line>`/`<path>`；无 `::before`/`::after` 装饰内容
- [ ] 无 `mask-image` / `conic-gradient` / `background-clip:text` / `mix-blend-mode`
- [ ] 节点撑开用 `min-width`/`min-height`，`box-sizing:border-box`，防坍缩
