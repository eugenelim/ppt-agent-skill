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
| `architecture-component` `architecture-deployment` `er-data-model` `layers` `architecture-canvas` | 组件/分层架构、部署/云/网络拓扑、数据模型、技术栈分层、图标节点分层画布 | `diagram-architecture` |
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
  --node-shadow:  var(--card-shadow, none); /* 节点立体感（卡片阴影继承） */
  --label-font:   var(--font-primary);
  font-family: var(--label-font);
}
```

内联 SVG 直接引用这些变量：`stroke="var(--edge)"`、`fill="var(--node-accent)"`（CSS 变量会被继承进内联 SVG）。**禁止**在节点/连线里写 `#xxxxxx`、`rgb(...)`；唯一例外是趋势绿 `#22c55e` / 红 `#ef4444`。

### 节点色纪律（流程/连接类图解的铁律）

图解里"类别/分组"信号由**连线与箭头的颜色**承载（`--edge-strong` / `--node-accent` / `--node-accent-2`），**不是**由节点底色或节点描边承载。连线已经带着类别信号，再给节点上色是重复、还会在浅底翻车。

- **禁止 `.node.<color>` 变体改写节点的 `background` 或 `border`。** 给节点套 `linear-gradient(var(--x-soft),var(--x-end))` 之类的浅色类别底，在浅底 deck（近白背景）上几乎不可见，等于没有信号。**带色底区分内容类别是 bento 卡片布局的手法**（见 `card-styles` / `comparison`），不属于流程图。
- 流程图节点一律中性：白/卡片底 + 中性描边（`--node-border`）+ `--node-fg` 文字。类别差异交给它们之间的箭头颜色。
- **确需给单个节点做「每节点类别」标记**（无连线的类别清单/图例等边缘场景）时，用**实心 accent 左边条**（`border-left:2px solid var(--node-accent)`）配中性底 —— 绝不用浅色渐变填充。
- **焦点强调**（单点高亮，1–2 个）仍走既有写法：`border-color:var(--node-accent)` + `box-shadow:0 0 0 1px var(--node-accent)`。这是"强调"不是"类别"，与上面的类别纪律不冲突。

### 节点标题恒为 --node-fg

流程/连接类图解的节点盒标题 / `<h3>` 的颜色**永远是 `--node-fg`（即 `--ink`），绝不改成 accent 色**——包括焦点/关键路径节点：它们的强调已由 accent 描边 + `box-shadow` 发光承载，标题再上色是重复、还会在部分调色板下降低对比。不要写 `.node.<color> h3 { color:var(--accent) }`。强调色只落在连线、箭头、焦点节点描边上，不落在节点文字上。

> 例外（非「流程节点标题」）：分析型图解里的单点强调标题（如 2×2 焦点格、before-after 目标卡）与点标记标注（里程碑名、光谱「建议」、回路 R/B）可保留 accent —— 它们不是连接图里的节点盒标题。

### 线宽平衡（连线 vs 节点描边）

连线/箭头的 `stroke-width` 要与节点描边**同量级**，不能一粗一细失衡：

- 节点描边 1px 时，连线/箭头 `stroke-width ≤ 1.5`。
- 若确需更粗的连线（关键路径），把节点描边也提到 1.5–2px 一起加重，让两者匹配。
- 线稿模式（lineart）已统一收到 1（关键路径 1.2），本规则主要约束 filled 模式。

### 实心填充只留给「强调/交互」，不留给「类别/标签」

实心色块（`background:var(--node-accent)` 满填）比它想标注的节点还重，会造成权重倒挂。**浮动的"标签类"元素（泳道角色标签、分区标签、图例）一律用描边款**：`background:transparent; border:1.5px solid var(--node-accent); color:var(--node-accent)`。实心满填只保留给：焦点/终端强调（1–2 处）、结构性表头色带（如 ER 实体表头）、按钮类交互 UI。

## 线稿模式 (line-art) — 主题门控

> 默认关闭，仅特定主题（`schematic_blueprint` 等）开启。

**这是"Claude/编辑部式"锐利线稿图解的实现方式：不新增任何配方，只重绑主题契约的局部变量。**

判定：读当前 `style.json` 的 `decorations.diagram_mode`。

- **`"filled"` 或该键缺失（27 个既有风格全部如此）** → 图解按上文默认契约渲染（填充节点 + 渐变底 + accent 描边）。**视觉零变化。**
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
焦点节点（**仅 1–2 个，强调而非类别**）：首选 `border-color:var(--node-accent); box-shadow:0 0 0 1px var(--node-accent);`；满填款 `background:var(--node-accent); color:var(--card-bg-from);` 只留给终端节点（开始/结束）这类语义强调，不得用来表类别。普通节点保持中性底 + `--node-fg` 文字（见上文「节点色纪律」）。

### 2. 连线（connector）-- 真实元素，禁伪元素
```html
<!-- 直线：真实 div（水平）——线宽与 1px 节点描边同量级 -->
<div style="height:1.5px; background:var(--edge); align-self:center; flex:1;"></div>
<!-- 折线 / 曲线 / 斜线：内联 SVG path/line，overflow 可溢出格子 -->
<svg viewBox="0 0 100 40" preserveAspectRatio="none" style="width:100%;height:40px;overflow:visible;display:block;">
  <path d="M0 20 H50 V4 H100" fill="none" stroke="var(--edge)" stroke-width="1.5"/>
</svg>
```

### 3. 箭头（arrowhead）-- 内联 SVG `<polygon>`，禁 CSS border 三角形
```html
<svg viewBox="0 0 120 16" preserveAspectRatio="none" style="width:100%;height:16px;overflow:visible;display:block;">
  <line x1="0" y1="8" x2="104" y2="8" stroke="var(--edge-strong)" stroke-width="1.5"/>
  <polygon points="104,2 118,8 104,14" fill="var(--edge-strong)"/>
</svg>
```
（需要随路径旋转时，手动给 polygon 算好顶点坐标；不依赖 `<marker orient>`，下游渲染器对其支持不稳。）

### 3.1 连线拓扑（按连接密度选形）

> **通用根因**：逐点 `source_center_y → target_center_y`（把源节点中线直接抄成终点坐标）**只有 1:1 连接才成立**。源与目标一旦竖直错位、或出现多入/多对多，照抄源 center-y 就会 overshoot、重叠、乱穿。按下面的连接密度阶梯选连线形态 —— 每一档都以此根因为前提。

**① 1:1（单源单目标）** —— 直连即可。仅当源与目标**共享同一条中线**时，终点坐标才允许取源节点 center-y。

**② 多对一 fan-in（N 源 → 1 目标）** —— 入点沿目标节点边**均匀铺开**，不要全打到几何中心（否则连线叠成一坨、分不清来源）。

- 分布区间用目标节点的**内缩（padded）包围盒** `[a, b]`（水平流：`a = dest_top + padding`、`b = dest_bottom − padding`，分布入点 `y`；垂直流用内缩后的左右边分布 `x`；`padding` 取节点圆角或一个箭头半高）。第 `i` 条入线（`i = 1..N`）入点取 `a + (b − a) · i / (N + 1)`，等距排布、避开最顶/最底的角。
- 每条入线的箭头 `<polygon>` 顶点按各自入点单独算，都指向节点边（不是中心）。源侧同理：多条出线的出点也沿源节点边铺开，不共用一个起点。
- 例：目标 `y ∈ [120, 200]`（高 80），3 条入线 → 入点 `y = 140 / 160 / 180`（`120 + 80·i/4`）。

**③ 竖直错位的源→目标** —— 终点必须**夹取（clamp）进目标节点包围盒**，禁止照抄源 center-y（源在目标中线之上/之下时，抄下来会穿过或越过目标）。

- 终点 `y` clamp 进 `[y_top + r, y_bottom − r]`（`r` = 节点圆角 / 一个箭头半高），让箭头落在目标的**近边**上，而不是源头的高度上；垂直流时终点 `x` 同理夹进目标水平边。
- 竖直错位用**折线/正交连线**（先走到目标近边所在的 `x`/`y`，再拐向夹取后的入点），不要画一条斜穿版面、末端越过节点的直线。
- 与 ② **叠加**：fan-in 的 `a + (b−a)·i/(N+1)` 分布区间 `[a,b]` 就是这里 clamp 出来的那段内缩边 —— 分布与夹取是同一条规则的两半。

**④ 稠密多对多 many-to-many（多源 → 同一组 ≥2 目标）** —— 用**总线拓扑（bus）**，不要画 N×M 根独立斜线（既凌乱又把 ③ 的 overshoot 放大成一片乱穿）。

- **触发条件**：检测到"多个源都连到同一组目标"（完全或近似 crossbar）→ 切 bus，不再逐对连线。
- **画法**：源列与目标列之间留一条**总线通道**，画一条主干线（水平流竖直总线 / 垂直流水平总线）；每个源用一小段**支线（stub）**接上总线，每个目标用一小段支线从总线接出 —— N+M 段短支线 + 1 条主干，取代 N×M 根斜线。
- 支线接入总线/节点的点，沿各自节点边用 `a + (b−a)·i/(N+1)` 均匀分布并夹进包围盒；主干两端不出头。
- 稀疏的少量交叉（如 3 根线各去不同目标，非同一组）不属于此档，仍走 ②③ 逐线画；bus 只用于**稠密同组多对多**。

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

## Mermaid 渲染器语义标注

> 仅适用于通过 `mermaid_layout` 渲染的 Mermaid 源码图（`flowchart` / `graph` 指令）。手写 HTML 配方不涉及。

### `:::external` — 外部系统标注

对系统边界之外的节点追加 `:::external`，渲染器自动用次级颜色（`--node-fg-dim`）绘制其边框与文字，形成"灰化"视觉，让内外部边界一目了然。

```
flowchart TD
  client["Web Browser"]:::external --> gateway["API Gateway"]
  gateway --> db["PostgreSQL|Database"]
  gateway --> stripe["Stripe Payments"]:::external
```

- 边框颜色：`var(--node-fg-dim, var(--text-secondary))`
- 文字颜色：`var(--node-fg-dim, var(--text-secondary))`
- 背景：与普通节点相同（不改底色，仅降低视觉权重）

### `:::icon-name` — 节点图标

在节点追加 `:::icon-name`，渲染器从 `assets/icons/<icon-name>.svg` 内联 SVG 图标到节点卡片左侧（同 architecture-canvas 的图标布局）。规划阶段应根据节点语义选择图标；渲染器也会按标签关键词自动回退推断，但显式标注更准确。

```
flowchart LR
  User([End User]):::users --> Web[Web App]:::browser
  Web --> API[API Gateway]:::api
  API --> DB[(User Data)]
  API --> Auth[Auth Service]:::iam
  Auth -.-> IdP[Identity Provider]:::external
```

**常用图标速查（完整列表见 `assets/icons/catalog.json`）：**

| `:::icon-name` | 适用节点 |
|---|---|
| `:::users` | 用户、人员、客户端、端用户 |
| `:::user` | 单一用户（单人图标） |
| `:::browser` | Web 应用、前端、SPA、Web 门户 |
| `:::mobile` | 移动端、iOS/Android App |
| `:::api` | API 网关、REST endpoint |
| `:::connector` | 集成连接器、中间件 |
| `:::database` | 数据库、数据存储 |
| `:::cache` | 缓存层（Redis / Memcache） |
| `:::queue` | 消息队列（SQS / RabbitMQ） |
| `:::message-broker` | 消息中间件（Kafka / ActiveMQ） |
| `:::event-bus` | 事件总线（SNS / EventBridge） |
| `:::search` | 搜索引擎（Elasticsearch / OpenSearch） |
| `:::vector-store` | 向量库 / RAG 索引 |
| `:::model` | AI/ML 模型、LLM 推理 |
| `:::model-api` | 云端模型 API（OpenAI / Anthropic） |
| `:::agent` | AI Agent / 自主 Agent |
| `:::iam` | 鉴权服务、IAM、IdP、SSO |
| `:::vault` | 密钥管理、Secrets Manager |
| `:::pipeline` | 数据流水线、ETL |
| `:::scheduler` | 定时任务、Airflow |
| `:::workflow` | 工作流引擎（Temporal / Step Functions） |
| `:::cloud` | 云平台、SaaS |
| `:::cdn` | CDN、边缘节点 |
| `:::load-balancer` | 负载均衡器 |
| `:::kubernetes` | K8s 集群 |
| `:::logs` | 日志服务 |
| `:::metrics` | 监控指标 |
| `:::external-system` | 第三方系统（也可用 `:::external` 获得灰化+虚线边框） |

> 标注规则：`:::icon-name` 仅追加图标，不影响节点形状；如需同时标注外部系统，两者可叠加（先写形状注解，再用 CSS 类选一个语义——外部系统优先用 `:::external` 获得完整视觉降权，无需另加图标类）。

### `label|tech` — 技术标注副标题（C4 stereotype）

节点 label 含 `|` 分隔符时，`|` 右侧视为技术栈副标题，以 11px `--node-fg-dim` 小字渲染在名称下方。

```
flowchart TD
  A["Auth Service|Go 1.22"] --> B["User DB|PostgreSQL 16"]
  A -.- C["Email Provider|SendGrid"]:::external
```

渲染结果：主标题（14px 粗体）+ 技术副标题（11px 次色），类似 C4 Container 图的 `[Technology]` 标注。

### `%% title:` — 图表标题

在 Mermaid 源码第一行写 `%% title: 标题文字`，渲染器会在图表上方添加类型徽章（如 `FLOWCHART`）和标题行。

```
%% title: 支付系统架构
flowchart TD
  A --> B
```

### 图例自动生成

图表使用超过 1 种边样式时（实线 + 虚线、或实线 + 粗线、或含分组框），渲染器在图表下方自动追加图例行，说明各边样式语义（`Synchronous` / `Async / optional` / `Critical path` / `Service boundary`）。纯实线单一样式图表不生成图例，避免多余噪音。

## 节点颜色角色 / Semantic colour-role guidance

Each CSS variable in the `.diagram` contract maps to a specific architectural role. Use the right variable for the right role — do not re-purpose.

| Variable | Role | When to use |
|---|---|---|
| `--node-bg-from` / `--node-bg-to` | Base node fill | All ordinary nodes (default; no override needed) |
| `--node-border` | Node outline | Default node border; all non-accented nodes |
| `--node-fg` | Primary label text | Node titles, main labels |
| `--node-fg-dim` | Secondary / dim text | Tech sub-labels (`label\|tech`), `:::external` text, edge labels |
| `--node-accent` | Focus highlight (1–2 nodes max) | Start/end terminal nodes; critical single point of focus |
| `--node-accent-2` | Second accent (group contrast) | Secondary grouping or paired comparison — rarely needed |
| `--edge` | Default connector line | All plain connectors and arrowheads |
| `--edge-strong` | Critical path / emphasis line | Key data flow or primary call path; one edge type per diagram |
| `--node-shadow` | Node depth / elevation | Inherits `--card-shadow`; set to `none` on flat/lineart themes |

**Architectural-role mapping (C4 / topology diagrams):**

- **Internal services** — default styling; no override.
- **External systems** — `:::external` class; uses `--node-fg-dim` border + text automatically.
- **Databases / stores** — cylinder node shape; default colours.
- **Critical path** — `--edge-strong` on the connecting edge; do NOT recolour the node.
- **Focus node** — `border-color:var(--node-accent); box-shadow:0 0 0 1px var(--node-accent)`.
- **Subgraph / boundary** — group container already uses `--node-border` at reduced opacity; no extra colour needed.

## 管线安全自检（每个 family 配方都要过）
- [ ] 颜色/字体全部来自主题契约的局部变量（无硬编码，趋势绿红除外）
- [ ] 内联 SVG 内**无 `<text>`**；标注全是 HTML 叠加
- [ ] 箭头是 SVG `<polygon>`；无 CSS border 三角形（`width:0` 技巧）
- [ ] 连线是真实 `<div>` 或 SVG `<line>`/`<path>`；无 `::before`/`::after` 装饰内容
- [ ] 连线拓扑按密度选形（§3.1）：终点未照抄源 center-y；多对一 fan-in 入点沿目标边均匀铺开（`a + (b−a)·i/(N+1)`）未堆在中心；竖直错位终点已 clamp 进目标包围盒、无 overshoot；稠密同组多对多改用总线拓扑（主干 + 短支线）而非 N×M 斜线
- [ ] 无 `mask-image` / `conic-gradient` / `background-clip:text` / `mix-blend-mode`
- [ ] 节点撑开用 `min-width`/`min-height`，`box-sizing:border-box`，防坍缩

## 主题一致性自检（避免在浅底 deck 翻车）
- [ ] **节点不靠底色/描边表类别**：无 `.node.<color>` 改写 `background`/`border`；类别信号在连线/箭头颜色上（浅色渐变类别底 = 浅底不可见，禁用）
- [ ] **节点标题恒为 `--node-fg`**，未改成 accent 色
- [ ] **连线/箭头 `stroke-width` 与节点描边同量级**（1px 描边 → 连线 ≤1.5px），不失衡
- [ ] **标签类元素（泳道角色/分区/图例）用描边款**（`transparent` 底 + accent 描边 + accent 文字），实心满填只留给焦点/终端强调与交互 UI
