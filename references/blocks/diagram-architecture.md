# diagram-architecture（架构视图族）

> family `block_ref`: `diagram-architecture`。配方：`architecture-component` / `architecture-deployment` / `er-data-model` / `layers` / `architecture-canvas`。
> 前置：先读 `blocks/diagram.md` 的**主题契约**与**共享基元**（节点盒/连线/箭头/标注/8px 栅格）。本族所有模板的颜色字体只用契约里的局部变量。
> 管线：HTML→SVG→PPTX，遵守 pipeline-compat.md（SVG `<polygon>` 箭头、真实 `<div>`/SVG `<line>` 连线、HTML 叠加标注、禁 `<text>`/`mask-image`/`conic-gradient`/`background-clip:text`）。

---

### 架构-组件图 (architecture-component)

**何时用**：展示软件组件/模块及其依赖关系，含 C4 Context/Container/Component、UML 组件图；适合"系统由哪些部分组成、谁依赖谁"。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "architecture-component",
  "layers": [
    {"label": "接入层", "nodes": [{"id":"web","label":"Web","desc":"React"},{"id":"mobile","label":"App","desc":"iOS/Android"}]},
    {"label": "服务层", "nodes": [{"id":"api","label":"API 网关","desc":"鉴权/路由","focus":true},{"id":"svc","label":"业务服务"}]},
    {"label": "数据层", "nodes": [{"id":"db","label":"PostgreSQL"},{"id":"cache","label":"Redis"}]}
  ]
}
```

**模板**（分层带 + 组件盒 + 层间 SVG 箭头）：
```html
<div class="diagram arch-component" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  font-family:var(--font-primary); display:flex; flex-direction:column; gap:0; width:760px;">

  <div class="layer" style="display:flex; align-items:center; gap:16px; padding:14px 0;">
    <span style="width:64px; flex-shrink:0; font-size:11px; font-weight:700; letter-spacing:1px;
      text-transform:uppercase; color:var(--node-fg-dim);">接入层</span>
    <div style="display:flex; gap:16px; flex:1;">
      <div style="flex:1; min-height:56px; display:flex; flex-direction:column; justify-content:center; gap:2px;
        padding:12px 16px; box-sizing:border-box; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="font-weight:700; font-size:14px;">Web</span>
        <span style="font-size:12px; color:var(--node-fg-dim);">React</span>
      </div>
      <div style="flex:1; min-height:56px; display:flex; flex-direction:column; justify-content:center; gap:2px;
        padding:12px 16px; box-sizing:border-box; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="font-weight:700; font-size:14px;">App</span>
        <span style="font-size:12px; color:var(--node-fg-dim);">iOS / Android</span>
      </div>
    </div>
  </div>

  <!-- 层间依赖箭头：SVG polygon，向下 -->
  <svg viewBox="0 0 760 24" preserveAspectRatio="none" style="width:100%; height:24px; overflow:visible; display:block;">
    <line x1="380" y1="0" x2="380" y2="16" stroke="var(--edge)" stroke-width="1.5"/>
    <polygon points="374,14 380,24 386,14" fill="var(--edge)"/>
  </svg>

  <div class="layer" style="display:flex; align-items:center; gap:16px; padding:14px 0;">
    <span style="width:64px; flex-shrink:0; font-size:11px; font-weight:700; letter-spacing:1px;
      text-transform:uppercase; color:var(--node-fg-dim);">服务层</span>
    <div style="display:flex; gap:16px; flex:1;">
      <!-- focus 节点：accent 描边 + 发光 -->
      <div style="flex:1; min-height:56px; display:flex; flex-direction:column; justify-content:center; gap:2px;
        padding:12px 16px; box-sizing:border-box; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-accent); border-radius:var(--node-radius); color:var(--node-fg);
        box-shadow:0 0 0 1px var(--node-accent);">
        <span style="font-weight:700; font-size:14px;">API 网关</span>
        <span style="font-size:12px; color:var(--node-fg-dim);">鉴权 / 路由</span>
      </div>
      <div style="flex:1; min-height:56px; display:flex; align-items:center;
        padding:12px 16px; box-sizing:border-box; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg); font-weight:700; font-size:14px;">业务服务</div>
    </div>
  </div>
</div>
```
> 复制规律：每层一个 `.layer` 行（左侧层名 + 右侧等宽组件盒），层与层之间夹一段 SVG 箭头。组件数多时 `flex:1` 自动等宽，`min-height:56px` 防坍缩。

**自检**：层名/组件盒/箭头颜色全用契约局部变量；focus 节点用 `--node-accent` 拉开主次；组件盒 `box-sizing:border-box`+`min-height`。

**管线安全**：箭头 `<polygon>`；无 SVG `<text>`（层名/组件名都是 HTML）；无伪元素连线；无 `mask-image`/`conic-gradient`。

---

### 架构-部署/拓扑图 (architecture-deployment)

**何时用**：把运行时构件映射到物理/云节点；C4 Deployment、云分组（VPC/区域）、网络拓扑共用此配方；适合"部署在哪、网络怎么连"。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "architecture-deployment",
  "groups": [
    {"label": "AWS · ap-southeast-1", "nodes": [
      {"id":"alb","label":"ALB"}, {"id":"ecs","label":"ECS 服务","desc":"2× task"}, {"id":"rds","label":"RDS","desc":"Multi-AZ"}]}
  ],
  "links": [{"from":"alb","to":"ecs"},{"from":"ecs","to":"rds"}]
}
```

**模板**（分组容器嵌套 + 内部节点 + SVG 连线）：
```html
<div class="diagram arch-deploy" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to); --node-border:var(--card-border);
  --node-radius:var(--card-radius,8px); --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --group-border:var(--accent-1); font-family:var(--font-primary); width:720px;">

  <!-- 分组容器：虚线 accent 边框 + 左上角标签（真实 span，非伪元素） -->
  <div style="position:relative; border:1.5px dashed var(--group-border); border-radius:12px; padding:28px 20px 20px;">
    <span style="position:absolute; top:-10px; left:16px; padding:0 8px; font-size:11px; font-weight:700;
      letter-spacing:1px; color:var(--group-border); background:var(--bg-primary);">AWS · ap-southeast-1</span>

    <div style="display:flex; align-items:center; gap:0;">
      <div style="min-width:120px; min-height:52px; display:flex; align-items:center; justify-content:center;
        padding:10px 14px; box-sizing:border-box; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg); font-weight:700; font-size:14px;">ALB</div>

      <svg viewBox="0 0 80 16" preserveAspectRatio="none" style="width:80px; height:16px; overflow:visible; display:block;">
        <line x1="0" y1="8" x2="64" y2="8" stroke="var(--edge)" stroke-width="1.5"/>
        <polygon points="64,2 78,8 64,14" fill="var(--edge)"/>
      </svg>

      <div style="min-width:120px; min-height:52px; display:flex; flex-direction:column; justify-content:center; gap:2px;
        padding:10px 14px; box-sizing:border-box; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="font-weight:700; font-size:14px;">ECS 服务</span>
        <span style="font-size:12px; color:var(--node-fg-dim);">2× task</span>
      </div>

      <svg viewBox="0 0 80 16" preserveAspectRatio="none" style="width:80px; height:16px; overflow:visible; display:block;">
        <line x1="0" y1="8" x2="64" y2="8" stroke="var(--edge)" stroke-width="1.5"/>
        <polygon points="64,2 78,8 64,14" fill="var(--edge)"/>
      </svg>

      <div style="min-width:120px; min-height:52px; display:flex; flex-direction:column; justify-content:center; gap:2px;
        padding:10px 14px; box-sizing:border-box; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="font-weight:700; font-size:14px;">RDS</span>
        <span style="font-size:12px; color:var(--node-fg-dim);">Multi-AZ</span>
      </div>
    </div>
  </div>
</div>
```
> 嵌套规律：分组用虚线 `--group-border` 容器 + 角标 span；节点横排，节点间夹 SVG line+polygon。多分组时纵向堆叠多个容器，跨组连线用一段 `overflow:visible` 的 SVG。

**自检**：分组角标是真实 `<span>`；节点/连线颜色全用契约变量；箭头 `<polygon>`。

**管线安全**：分组标签未用 `::before`/`content`；无 SVG `<text>`；无 `mask-image`。

---

### 数据模型/ER 图 (er-data-model)

**何时用**：数据库 schema、领域模型、UML 类图共用；实体 + 字段 + 关系基数。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "er-data-model",
  "entities": [
    {"id":"user","label":"User","fields":["id PK","email","created_at"]},
    {"id":"order","label":"Order","fields":["id PK","user_id FK","total"]}
  ],
  "relations": [{"from":"user","to":"order","card":"1 : N"}]
}
```

**模板**（实体表盒 + 字段行 + 关系连线 + HTML 基数标注）：
```html
<div class="diagram er-model" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to); --node-border:var(--card-border);
  --node-radius:var(--card-radius,8px); --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1); font-family:var(--font-primary);
  display:flex; align-items:center; gap:0; width:620px;">

  <div style="min-width:180px; border:1px solid var(--node-border); border-radius:var(--node-radius); overflow:hidden;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); color:var(--node-fg);">
    <div style="padding:8px 14px; font-weight:700; font-size:14px; background:var(--node-accent); color:var(--card-bg-from);">User</div>
    <div style="padding:8px 14px; font-size:12px; line-height:1.9; color:var(--node-fg-dim);">id PK<br>email<br>created_at</div>
  </div>

  <div style="position:relative; flex:1; height:52px;">
    <svg viewBox="0 0 180 52" preserveAspectRatio="none" style="width:100%; height:100%; overflow:visible; display:block;">
      <line x1="0" y1="26" x2="180" y2="26" stroke="var(--edge)" stroke-width="1.5"/>
    </svg>
    <span style="position:absolute; left:50%; top:2px; transform:translateX(-50%); font-size:11px;
      font-weight:700; color:var(--node-fg-dim);">1 : N</span>
  </div>

  <div style="min-width:180px; border:1px solid var(--node-border); border-radius:var(--node-radius); overflow:hidden;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); color:var(--node-fg);">
    <div style="padding:8px 14px; font-weight:700; font-size:14px; background:var(--node-accent); color:var(--card-bg-from);">Order</div>
    <div style="padding:8px 14px; font-size:12px; line-height:1.9; color:var(--node-fg-dim);">id PK<br>user_id FK<br>total</div>
  </div>
</div>
```
> 规律：每个实体是带表头的盒（表头 accent 实底，字段区 dim 文字）；关系是中间一段 SVG line + HTML 基数标注。多实体时网格排布，连线用 `overflow:visible` SVG。

**自检**：表头用 `--node-accent` 实底 + `--card-bg-from` 反白文字；基数标注是 HTML span；字段区颜色用契约变量。

**管线安全**：基数/字段全是 HTML；连线 SVG `<line>`；无 SVG `<text>`、无伪元素。

---

### 分层栈 (layers)

**何时用**：技术栈/抽象层级的纵深（保留旧 `diagram_type:layers`）；从上到下颜色渐变制造"地层沉积"。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "layers",
  "layers": [
    {"label":"表现层","desc":"UI / 路由"},
    {"label":"应用层","desc":"用例 / 编排"},
    {"label":"领域层","desc":"实体 / 规则","focus":true},
    {"label":"基础设施层","desc":"DB / 消息 / 外部"}
  ]
}
```

**模板**（全宽堆叠带 + 渐变纵深）：
```html
<div class="diagram layers" style="
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px); --node-fg:var(--text-primary);
  --node-fg-dim:var(--text-secondary); --node-accent:var(--accent-1); --bg-a:var(--card-bg-from); --bg-b:var(--card-bg-to);
  font-family:var(--font-primary); display:flex; flex-direction:column; gap:8px; width:560px;">

  <div style="display:flex; align-items:center; justify-content:space-between; min-height:52px; padding:12px 20px;
    box-sizing:border-box; border:1px solid var(--node-border); border-radius:var(--node-radius);
    background:linear-gradient(180deg,var(--bg-a),var(--bg-b)); color:var(--node-fg);">
    <span style="font-weight:700; font-size:15px;">表现层</span>
    <span style="font-size:12px; color:var(--node-fg-dim);">UI / 路由</span>
  </div>

  <div style="display:flex; align-items:center; justify-content:space-between; min-height:52px; padding:12px 20px;
    box-sizing:border-box; border:1px solid var(--node-border); border-radius:var(--node-radius);
    background:linear-gradient(180deg,var(--bg-a),var(--bg-b)); color:var(--node-fg);">
    <span style="font-weight:700; font-size:15px;">应用层</span>
    <span style="font-size:12px; color:var(--node-fg-dim);">用例 / 编排</span>
  </div>

  <!-- focus 层：accent 左边条 + 描边 -->
  <div style="display:flex; align-items:center; justify-content:space-between; min-height:52px; padding:12px 20px;
    box-sizing:border-box; border:1px solid var(--node-accent); border-left:4px solid var(--node-accent);
    border-radius:var(--node-radius); background:linear-gradient(180deg,var(--bg-a),var(--bg-b)); color:var(--node-fg);">
    <span style="font-weight:700; font-size:15px;">领域层</span>
    <span style="font-size:12px; color:var(--node-fg-dim);">实体 / 规则</span>
  </div>

  <div style="display:flex; align-items:center; justify-content:space-between; min-height:52px; padding:12px 20px;
    box-sizing:border-box; border:1px solid var(--node-border); border-radius:var(--node-radius);
    background:linear-gradient(180deg,var(--bg-a),var(--bg-b)); color:var(--node-fg);">
    <span style="font-weight:700; font-size:15px;">基础设施层</span>
    <span style="font-size:12px; color:var(--node-fg-dim);">DB / 消息 / 外部</span>
  </div>
</div>
```
> 纵深技巧：用 `opacity` 或在各层把 `--bg-b` 透明度逐层加深来制造"越往下越实"，但**不要**改成硬编码色值——继续走契约变量。

**自检**：每层等高（`min-height:52px`）；focus 层用 accent 左边条；全宽堆叠 gap=8px。

**管线安全**：纯 `<div>` 堆叠 + `linear-gradient`；无 SVG/伪元素/mask；颜色全用契约变量。

---

### 架构-图标画布 (architecture-canvas)

**何时用**：数据/平台架构的"分层带 + 图标节点"画布——若干**带名横向 zone**，每个 zone 内是一排**图标节点卡**（来自 `assets/icons/` 图标库，内联 `<svg>`），中间一条**高亮主脊 zone**（如数据湖/知识层），zone 之间用**带标注连接线**相接。适合"平台由哪些层构成、每层有哪些能力、数据如何流动"。比 `architecture-component` 多了图标语义与命名脊层；节点少时退化为 `layers`。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "architecture-canvas",
  "zones": [
    {"label":"Sources", "connector_out":"ingest", "nodes":[
      {"icon":"users","label":"Channels","desc":"web · mobile · partners"},
      {"icon":"connector","label":"Connectors","desc":"SaaS · systems"}]},
    {"label":"Platform", "spine":true, "connector_out":"serve", "nodes":[
      {"icon":"database","label":"Data Lake","focus":true},
      {"icon":"knowledge-graph","label":"Knowledge Graph"},
      {"icon":"pipeline","label":"Curate"}]},
    {"label":"Consumers", "nodes":[
      {"icon":"agent","label":"Agents","desc":"autonomous"},
      {"icon":"dashboard","label":"Insights"}]}
  ]
}
```
> `icon` = `assets/icons/<id>.svg` 的 id（用 `python3 scripts/icon_search.py <concept> --snippet` 取内联片段）。图标 `stroke=currentColor`，颜色随节点 `color` 变。

**模板**（zone 带 + 图标节点卡 + 主脊高亮 + 带标注连接线）：
```html
<div class="diagram arch-canvas" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  font-family:var(--font-primary); display:flex; flex-direction:column; gap:6px; width:840px;">

  <!-- zone：左侧 zone 名 + 右侧图标节点卡行 -->
  <div class="zone" style="display:flex; align-items:stretch; gap:14px; padding-left:12px;">
    <span style="width:84px; flex-shrink:0; display:flex; align-items:center; font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--node-fg-dim);">Sources</span>
    <div style="display:flex; gap:12px; flex:1;">
      <div style="flex:1; display:flex; align-items:center; gap:10px; padding:11px 13px; box-sizing:border-box; min-height:52px; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="flex-shrink:0; width:24px; height:24px; color:var(--node-accent); display:inline-flex;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3"/><path d="M3.7 19a5.3 5.3 0 0 1 10.6 0"/><path d="M16 6.3a3 3 0 0 1 0 5.4M17.6 19a5.3 5.3 0 0 0-2.9-4.75"/></svg></span>
        <span style="display:flex; flex-direction:column; gap:1px; min-width:0;"><span style="font-weight:700; font-size:13px;">Channels</span><span style="font-size:11px; color:var(--node-fg-dim);">web · mobile · partners</span></span>
      </div>
      <div style="flex:1; display:flex; align-items:center; gap:10px; padding:11px 13px; box-sizing:border-box; min-height:52px; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="flex-shrink:0; width:24px; height:24px; color:var(--node-accent); display:inline-flex;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 15 6.6 17.4a3 3 0 0 1-4.24-4.24L4.8 10.7"/><path d="M15 9l2.4-2.4a3 3 0 0 0-4.24-4.24L10.7 4.8"/><path d="M9.4 14.6 14.6 9.4"/></svg></span>
        <span style="display:flex; flex-direction:column; gap:1px; min-width:0;"><span style="font-weight:700; font-size:13px;">Connectors</span><span style="font-size:11px; color:var(--node-fg-dim);">SaaS · systems</span></span>
      </div>
    </div>
  </div>

  <!-- 带标注连接线：SVG 线 + polygon 箭头 + HTML mono 标注 -->
  <div style="display:flex; align-items:center; justify-content:center; gap:8px; height:20px; padding-left:96px;">
    <span style="font-family:var(--font-mono,monospace); font-size:9px; letter-spacing:.14em; text-transform:uppercase; color:var(--node-fg-dim);">ingest</span>
    <svg viewBox="0 0 24 20" preserveAspectRatio="none" style="width:24px; height:20px; overflow:visible;"><line x1="12" y1="0" x2="12" y2="12" stroke="var(--edge)" stroke-width="1.5"/><polygon points="7,10 12,20 17,10" fill="var(--edge)"/></svg>
  </div>

  <!-- 主脊 zone：accent 左边条 + accent zone 名 + focus 节点 -->
  <div class="zone spine" style="display:flex; align-items:stretch; gap:14px; padding-left:9px; border-left:3px solid var(--node-accent);">
    <span style="width:84px; flex-shrink:0; display:flex; align-items:center; font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--node-accent);">Platform</span>
    <div style="display:flex; gap:12px; flex:1;">
      <div style="flex:1; display:flex; align-items:center; gap:10px; padding:11px 13px; box-sizing:border-box; min-height:52px; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-accent); border-radius:var(--node-radius); color:var(--node-fg); box-shadow:0 0 0 1px var(--node-accent);">
        <span style="flex-shrink:0; width:24px; height:24px; color:var(--node-accent); display:inline-flex;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="6" rx="7" ry="2.6"/><path d="M5 6v12c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6V6"/><path d="M5 12c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6"/></svg></span>
        <span style="font-weight:700; font-size:13px;">Data Lake</span>
      </div>
      <div style="flex:1; display:flex; align-items:center; gap:10px; padding:11px 13px; box-sizing:border-box; min-height:52px; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="flex-shrink:0; width:24px; height:24px; color:var(--node-accent); display:inline-flex;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="2"/><circle cx="5" cy="17.5" r="2"/><circle cx="19" cy="17.5" r="2"/><circle cx="12" cy="13" r="2"/><path d="M12 7v4M10.4 14.3 6.5 16.2M13.6 14.3l3.9 1.9"/></svg></span>
        <span style="font-weight:700; font-size:13px;">Knowledge Graph</span>
      </div>
      <div style="flex:1; display:flex; align-items:center; gap:10px; padding:11px 13px; box-sizing:border-box; min-height:52px; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="flex-shrink:0; width:24px; height:24px; color:var(--node-accent); display:inline-flex;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="12" r="2.2"/><rect x="9.5" y="9.8" width="5" height="4.4" rx="1"/><circle cx="19" cy="12" r="2.2"/><path d="M7.2 12h2.3M14.5 12h2.3"/></svg></span>
        <span style="font-weight:700; font-size:13px;">Curate</span>
      </div>
    </div>
  </div>

  <div style="display:flex; align-items:center; justify-content:center; gap:8px; height:20px; padding-left:96px;">
    <span style="font-family:var(--font-mono,monospace); font-size:9px; letter-spacing:.14em; text-transform:uppercase; color:var(--node-fg-dim);">serve</span>
    <svg viewBox="0 0 24 20" preserveAspectRatio="none" style="width:24px; height:20px; overflow:visible;"><line x1="12" y1="0" x2="12" y2="12" stroke="var(--edge)" stroke-width="1.5"/><polygon points="7,10 12,20 17,10" fill="var(--edge)"/></svg>
  </div>

  <div class="zone" style="display:flex; align-items:stretch; gap:14px; padding-left:12px;">
    <span style="width:84px; flex-shrink:0; display:flex; align-items:center; font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--node-fg-dim);">Consumers</span>
    <div style="display:flex; gap:12px; flex:1;">
      <div style="flex:1; display:flex; align-items:center; gap:10px; padding:11px 13px; box-sizing:border-box; min-height:52px; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="flex-shrink:0; width:24px; height:24px; color:var(--node-accent); display:inline-flex;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="8.5" width="14" height="9.5" rx="2.5"/><path d="M12 8.5V6"/><circle cx="12" cy="4.7" r="1.1"/><circle cx="9.6" cy="13.2" r="1"/><circle cx="14.4" cy="13.2" r="1"/></svg></span>
        <span style="display:flex; flex-direction:column; gap:1px; min-width:0;"><span style="font-weight:700; font-size:13px;">Agents</span><span style="font-size:11px; color:var(--node-fg-dim);">autonomous</span></span>
      </div>
      <div style="flex:1; display:flex; align-items:center; gap:10px; padding:11px 13px; box-sizing:border-box; min-height:52px; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="flex-shrink:0; width:24px; height:24px; color:var(--node-accent); display:inline-flex;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M8 15.5v-3M12 15.5v-6M16 15.5v-4.5"/></svg></span>
        <span style="display:flex; flex-direction:column; gap:1px; min-width:0;"><span style="font-weight:700; font-size:13px;">Insights</span><span style="font-size:11px; color:var(--node-fg-dim);">dashboards</span></span>
      </div>
    </div>
  </div>
</div>
```
> 复制规律：每个 zone 一行（左 zone 名 + 右等宽图标节点卡）；主脊 zone 加 `border-left:3px solid var(--node-accent)` + accent zone 名；zone 间夹"标注 + SVG 箭头"连接行（`padding-left:96px` 让箭头对齐节点列）。图标一律内联 `<svg>` + `stroke=currentColor`，颜色随卡片 `color`/`--node-accent`。

**自检**：图标全部内联 `<svg currentColor>`（禁 `<img>`/`url()`）；zone 名/节点名/描述均为 HTML 文本；主脊用 `--node-accent` 左边条 + focus 节点描边拉主次；节点卡 `box-sizing:border-box` + `min-height:52px` 防坍缩；颜色字体只用契约局部变量。

**管线安全**：连接线箭头 `<polygon>`、连线 SVG `<line>`；图标内联 `<svg>`（`<circle>`/`<rect>`/`<ellipse>`/`<path>`/`<polygon>`）；无 SVG `<text>`（标注是 HTML `<span>`）；无 `mask-image`/`conic-gradient`/`background-image:url()`/`background-clip:text`/伪元素装饰。
