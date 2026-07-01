# diagram-architecture（架构视图族）

> family `block_ref`: `diagram-architecture`。配方：`architecture-component` / `architecture-deployment` / `er-data-model` / `layers`。
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
    <line x1="380" y1="0" x2="380" y2="16" stroke="var(--edge)" stroke-width="2"/>
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
        <line x1="0" y1="8" x2="64" y2="8" stroke="var(--edge)" stroke-width="2"/>
        <polygon points="64,2 78,8 64,14" fill="var(--edge)"/>
      </svg>

      <div style="min-width:120px; min-height:52px; display:flex; flex-direction:column; justify-content:center; gap:2px;
        padding:10px 14px; box-sizing:border-box; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
        <span style="font-weight:700; font-size:14px;">ECS 服务</span>
        <span style="font-size:12px; color:var(--node-fg-dim);">2× task</span>
      </div>

      <svg viewBox="0 0 80 16" preserveAspectRatio="none" style="width:80px; height:16px; overflow:visible; display:block;">
        <line x1="0" y1="8" x2="64" y2="8" stroke="var(--edge)" stroke-width="2"/>
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
      <line x1="0" y1="26" x2="180" y2="26" stroke="var(--edge)" stroke-width="2"/>
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
