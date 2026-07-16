# diagram-project（项目管理视图族）

> family `block_ref`: `diagram-project`。配方：`gantt` / `dependency-network` / `org-tree` / `kanban`。
> 前置：先读 `blocks/diagram.md` 的**主题契约**与**共享基元**（节点盒/连线/箭头/标注/8px 栅格）。本族所有模板的颜色字体只用契约里的局部变量。
> 管线：HTML→SVG→PPTX，遵守 pipeline-compat.md（SVG `<polygon>` 箭头、真实 `<div>`/SVG `<line>` 连线、HTML 叠加标注、禁 `<text>`/`mask-image`/`conic-gradient`/`background-clip:text`）。

---

### 甘特图 (gantt)

**何时用**：展示项目排期/路线图/冲刺计划；时间横轴 × 任务行，含里程碑菱形与可选依赖箭头；适合"谁在何时做什么、关键节点在哪"。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "gantt",
  "time_range": {"start": "2025-01", "end": "2025-06", "unit": "month"},
  "rows": [
    {"id": "discovery", "label": "需求调研", "start": 0, "span": 2},
    {"id": "design",    "label": "设计",     "start": 1, "span": 2, "focus": true},
    {"id": "dev",       "label": "开发",     "start": 2, "span": 3},
    {"id": "qa",        "label": "测试",     "start": 4, "span": 1}
  ],
  "milestones": [
    {"label": "立项", "at": 0},
    {"label": "发布", "at": 5}
  ]
}
```

**模板**（时间轴标尺 + 任务条 `<div>` + 里程碑 SVG `<polygon>` 菱形）：
```html
<div class="diagram gantt" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,6px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); width:720px;">

  <!-- 时间轴标尺 -->
  <div style="display:flex; margin-left:120px; margin-bottom:4px;">
    <div style="flex:1; text-align:center; font-size:11px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">1月</div>
    <div style="flex:1; text-align:center; font-size:11px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">2月</div>
    <div style="flex:1; text-align:center; font-size:11px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">3月</div>
    <div style="flex:1; text-align:center; font-size:11px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">4月</div>
    <div style="flex:1; text-align:center; font-size:11px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">5月</div>
    <div style="flex:1; text-align:center; font-size:11px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">6月</div>
  </div>

  <!-- 任务行：行标签 + 进度条 -->
  <div style="display:flex; flex-direction:column; gap:8px;">

    <!-- 需求调研：从第0格跨2格 -->
    <div style="display:flex; align-items:center; min-height:40px;">
      <span style="width:112px; flex-shrink:0; font-size:12px; font-weight:600;
        color:var(--node-fg); padding-right:8px; text-align:right;">需求调研</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); gap:0; position:relative; height:40px;">
        <!-- 占位格子（可选网格线） -->
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <!-- 任务条：绝对定位在格子上 -->
        <div style="position:absolute; left:0%; width:33.33%; top:8px; height:24px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-border); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 8px;">
          <span style="font-size:11px; color:var(--node-fg-dim);">需求调研</span>
        </div>
      </div>
    </div>

    <!-- 设计（focus）：从第1格跨2格 -->
    <div style="display:flex; align-items:center; min-height:40px;">
      <span style="width:112px; flex-shrink:0; font-size:12px; font-weight:600;
        color:var(--node-fg); padding-right:8px; text-align:right;">设计</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); gap:0; position:relative; height:40px;">
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <!-- focus 条：accent 描边 -->
        <div style="position:absolute; left:16.67%; width:33.33%; top:8px; height:24px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-accent); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 8px;
          box-shadow:0 0 0 1px var(--node-accent);">
          <span style="font-size:11px; color:var(--node-fg); font-weight:700;">设计</span>
        </div>
      </div>
    </div>

    <!-- 开发：从第2格跨3格 -->
    <div style="display:flex; align-items:center; min-height:40px;">
      <span style="width:112px; flex-shrink:0; font-size:12px; font-weight:600;
        color:var(--node-fg); padding-right:8px; text-align:right;">开发</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); gap:0; position:relative; height:40px;">
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="position:absolute; left:33.33%; width:50%; top:8px; height:24px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-border); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 8px;">
          <span style="font-size:11px; color:var(--node-fg-dim);">开发</span>
        </div>
      </div>
    </div>

    <!-- 测试：从第4格跨1格 -->
    <div style="display:flex; align-items:center; min-height:40px;">
      <span style="width:112px; flex-shrink:0; font-size:12px; font-weight:600;
        color:var(--node-fg); padding-right:8px; text-align:right;">测试</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); gap:0; position:relative; height:40px;">
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="position:absolute; left:66.67%; width:16.67%; top:8px; height:24px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-border); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 8px;">
          <span style="font-size:11px; color:var(--node-fg-dim);">测试</span>
        </div>
      </div>
    </div>

  </div><!-- /任务行 -->

  <!-- 里程碑行：SVG polygon 菱形 + HTML 标注 -->
  <div style="position:relative; margin-left:120px; height:32px; margin-top:8px;">
    <!-- 立项里程碑（第0格 = left:0%） -->
    <div style="position:absolute; left:0%; top:0; display:flex; flex-direction:column; align-items:center;">
      <svg viewBox="0 0 16 16" style="width:16px; height:16px; display:block; overflow:visible;">
        <polygon points="8,1 15,8 8,15 1,8" fill="var(--node-accent)"/>
      </svg>
      <span style="font-size:10px; font-weight:700; color:var(--node-accent); margin-top:2px; white-space:nowrap;">立项</span>
    </div>
    <!-- 发布里程碑（第5格末 = left:100%） -->
    <div style="position:absolute; left:100%; top:0; transform:translateX(-50%); display:flex; flex-direction:column; align-items:center;">
      <svg viewBox="0 0 16 16" style="width:16px; height:16px; display:block; overflow:visible;">
        <polygon points="8,1 15,8 8,15 1,8" fill="var(--node-accent-2)"/>
      </svg>
      <span style="font-size:10px; font-weight:700; color:var(--node-accent-2); margin-top:2px; white-space:nowrap;">发布</span>
    </div>
  </div>

</div>
```
> 复制规律：任务条 = 绝对定位 `<div>`，`left` = `(start / total) * 100%`，`width` = `(span / total) * 100%`；里程碑 = SVG `<polygon>` 菱形（旋转 45° 的正方形顶点）+ HTML 标注；时间格线用低 opacity 的 `<div>` 竖线。

**自检**：任务条/格线/里程碑颜色全用契约局部变量；`box-sizing:border-box`+`min-height` 防坍缩；`position:relative` 格子 + `position:absolute` 任务条；focus 任务用 `--node-accent` 拉开主次；里程碑用 `<polygon>` 菱形。

**管线安全**：箭头/菱形 `<polygon>`；无 SVG `<text>`（标注全是 HTML span）；无伪元素装饰；无 `mask-image`/`conic-gradient`；任务条为真实 `<div>`。

---

### 依赖网络图 (dependency-network)

**何时用**：PERT/CPM 依赖关系、先决条件图、任务关键路径；左→右有向无环图，关键路径用强调色高亮；适合"A 完成才能启动 B"。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "dependency-network",
  "nodes": [
    {"id":"A","label":"需求","desc":"2d"},
    {"id":"B","label":"设计","desc":"3d","critical":true},
    {"id":"C","label":"API","desc":"4d","critical":true},
    {"id":"D","label":"前端","desc":"5d","critical":true},
    {"id":"E","label":"测试","desc":"2d"},
    {"id":"F","label":"发布","desc":"1d","critical":true}
  ],
  "edges": [
    {"from":"A","to":"B"},{"from":"A","to":"E"},
    {"from":"B","to":"C","critical":true},
    {"from":"C","to":"D","critical":true},
    {"from":"D","to":"F","critical":true},
    {"from":"E","to":"F"}
  ]
}
```

**模板**（L-R DAG：节点盒 + SVG `<line>` 连线 + SVG `<polygon>` 箭头 + 关键路径强调）：
```html
<div class="diagram dependency-network" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --edge-strong:var(--accent-1);
  --node-accent:var(--accent-1); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:700px; height:280px;">

  <!-- 节点：用绝对定位放置在 DAG 坐标上 -->

  <!-- 列 0：需求 -->
  <div style="position:absolute; left:0; top:100px; min-width:88px; min-height:56px;
    display:flex; flex-direction:column; justify-content:center; gap:2px;
    padding:10px 14px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
    <span style="font-weight:700; font-size:13px;">需求</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">2d</span>
  </div>

  <!-- 列 1：设计（关键路径，accent 描边） -->
  <div style="position:absolute; left:160px; top:40px; min-width:88px; min-height:56px;
    display:flex; flex-direction:column; justify-content:center; gap:2px;
    padding:10px 14px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-accent); border-radius:var(--node-radius); color:var(--node-fg);
    box-shadow:0 0 0 1px var(--node-accent);">
    <span style="font-weight:700; font-size:13px; color:var(--node-fg);">设计</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">3d</span>
  </div>

  <!-- 列 1：测试（非关键） -->
  <div style="position:absolute; left:160px; top:168px; min-width:88px; min-height:56px;
    display:flex; flex-direction:column; justify-content:center; gap:2px;
    padding:10px 14px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-border); border-radius:var(--node-radius); color:var(--node-fg);">
    <span style="font-weight:700; font-size:13px;">测试</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">2d</span>
  </div>

  <!-- 列 2：API（关键） -->
  <div style="position:absolute; left:320px; top:40px; min-width:88px; min-height:56px;
    display:flex; flex-direction:column; justify-content:center; gap:2px;
    padding:10px 14px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-accent); border-radius:var(--node-radius); color:var(--node-fg);
    box-shadow:0 0 0 1px var(--node-accent);">
    <span style="font-weight:700; font-size:13px; color:var(--node-fg);">API</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">4d</span>
  </div>

  <!-- 列 3：前端（关键） -->
  <div style="position:absolute; left:480px; top:40px; min-width:88px; min-height:56px;
    display:flex; flex-direction:column; justify-content:center; gap:2px;
    padding:10px 14px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-accent); border-radius:var(--node-radius); color:var(--node-fg);
    box-shadow:0 0 0 1px var(--node-accent);">
    <span style="font-weight:700; font-size:13px; color:var(--node-fg);">前端</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">5d</span>
  </div>

  <!-- 列 4：发布（关键） -->
  <div style="position:absolute; left:608px; top:100px; min-width:88px; min-height:56px;
    display:flex; flex-direction:column; justify-content:center; gap:2px;
    padding:10px 14px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-accent); border-radius:var(--node-radius); color:var(--node-fg);
    box-shadow:0 0 0 1px var(--node-accent);">
    <span style="font-weight:700; font-size:13px; color:var(--node-fg);">发布</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">1d</span>
  </div>

  <!-- 连线层：SVG，overflow:visible 让线段越出容器边界 -->
  <svg style="position:absolute; left:0; top:0; width:100%; height:100%; overflow:visible; display:block;"
       viewBox="0 0 700 280" preserveAspectRatio="none">

    <!-- 需求 → 设计（关键，edge-strong） -->
    <line x1="88"  y1="128" x2="154" y2="72"  stroke="var(--edge-strong)" stroke-width="1.5"/>
    <polygon points="148,64 160,74 152,82" fill="var(--edge-strong)"/>

    <!-- 需求 → 测试（普通） -->
    <line x1="88"  y1="128" x2="154" y2="196" stroke="var(--edge)" stroke-width="1.5"/>
    <polygon points="148,188 160,198 152,206" fill="var(--edge)"/>

    <!-- 设计 → API（关键） -->
    <line x1="248" y1="72"  x2="314" y2="72"  stroke="var(--edge-strong)" stroke-width="1.5"/>
    <polygon points="308,66 320,72 308,78" fill="var(--edge-strong)"/>

    <!-- API → 前端（关键） -->
    <line x1="408" y1="72"  x2="474" y2="72"  stroke="var(--edge-strong)" stroke-width="1.5"/>
    <polygon points="468,66 480,72 468,78" fill="var(--edge-strong)"/>

    <!-- 前端 → 发布（关键） -->
    <line x1="568" y1="72"  x2="604" y2="124" stroke="var(--edge-strong)" stroke-width="1.5"/>
    <polygon points="596,116 606,128 614,120" fill="var(--edge-strong)"/>

    <!-- 测试 → 发布（普通） -->
    <line x1="248" y1="196" x2="604" y2="132" stroke="var(--edge)" stroke-width="1.5"/>
    <polygon points="596,124 608,134 600,142" fill="var(--edge)"/>

  </svg>

</div>
```
> 复制规律：节点用 `position:absolute` 摆放在 DAG 列/行坐标；关键路径节点加 `--node-accent` 描边+发光；SVG 层铺满容器（`overflow:visible`）画 `<line>` 连线 + `<polygon>` 箭头；普通边 `--edge`，关键路径边 `--edge-strong`。

**自检**：节点颜色/连线颜色全用契约变量；关键路径用 `--edge-strong`/`--node-accent` 区分；节点 `box-sizing:border-box`+`min-width/min-height`；箭头 `<polygon>`。

**管线安全**：箭头 `<polygon>`；连线 SVG `<line>`；无 SVG `<text>`（所有标注是 HTML）；无伪元素；无 `mask-image`/`conic-gradient`。

---

### 组织树 (org-tree)

**何时用**：组织架构/汇报链、工作分解结构（WBS）、决策树、目录树；顶→下父子层级；适合"谁向谁汇报、任务如何分解"。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "org-tree",
  "root": {
    "id": "ceo", "label": "CEO", "desc": "张三",
    "children": [
      {"id":"cto","label":"CTO","desc":"李四","focus":true,
        "children":[
          {"id":"fe","label":"前端","desc":"5人"},
          {"id":"be","label":"后端","desc":"8人"}
        ]},
      {"id":"cmo","label":"CMO","desc":"王五",
        "children":[
          {"id":"ops","label":"运营","desc":"3人"},
          {"id":"ds","label":"设计","desc":"2人"}
        ]}
    ]
  }
}
```

**模板**（顶→下三层：根 + 二级 + 三级，SVG `<line>` 垂直/水平连线）：
```html
<div class="diagram org-tree" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --label-font:var(--font-primary);
  font-family:var(--label-font); display:flex; flex-direction:column; align-items:center;
  gap:0; width:680px;">

  <!-- 根节点 -->
  <div style="min-width:120px; min-height:56px; display:flex; flex-direction:column;
    justify-content:center; gap:2px; padding:12px 20px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-accent); border-radius:var(--node-radius); color:var(--node-fg);
    box-shadow:0 0 0 1px var(--node-accent); text-align:center;">
    <span style="font-weight:700; font-size:14px;">CEO</span>
    <span style="font-size:12px; color:var(--node-fg-dim);">张三</span>
  </div>

  <!-- 根 → 二级连线（T形：竖线 + 水平横线） -->
  <svg viewBox="0 0 400 32" preserveAspectRatio="none"
       style="width:400px; height:32px; overflow:visible; display:block;">
    <!-- 竖线：根节点中心向下 -->
    <line x1="200" y1="0" x2="200" y2="16" stroke="var(--edge)" stroke-width="1.5"/>
    <!-- 水平横线：跨越两个子节点中心 -->
    <line x1="100" y1="16" x2="300" y2="16" stroke="var(--edge)" stroke-width="1.5"/>
    <!-- CTO 侧向下 -->
    <line x1="100" y1="16" x2="100" y2="32" stroke="var(--edge)" stroke-width="1.5"/>
    <!-- CMO 侧向下 -->
    <line x1="300" y1="16" x2="300" y2="32" stroke="var(--edge)" stroke-width="1.5"/>
  </svg>

  <!-- 二级节点行 -->
  <div style="display:flex; gap:0; width:400px; justify-content:space-around;">

    <!-- CTO（focus） -->
    <div style="display:flex; flex-direction:column; align-items:center;">
      <div style="min-width:120px; min-height:56px; display:flex; flex-direction:column;
        justify-content:center; gap:2px; padding:12px 16px; box-sizing:border-box;
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-accent); border-radius:var(--node-radius); color:var(--node-fg);
        box-shadow:0 0 0 1px var(--node-accent); text-align:center;">
        <span style="font-weight:700; font-size:13px; color:var(--node-fg);">CTO</span>
        <span style="font-size:11px; color:var(--node-fg-dim);">李四</span>
      </div>

      <!-- CTO → 三级连线 -->
      <svg viewBox="0 0 200 28" preserveAspectRatio="none"
           style="width:200px; height:28px; overflow:visible; display:block;">
        <line x1="100" y1="0"  x2="100" y2="14" stroke="var(--edge)" stroke-width="1.5"/>
        <line x1="50"  y1="14" x2="150" y2="14" stroke="var(--edge)" stroke-width="1.5"/>
        <line x1="50"  y1="14" x2="50"  y2="28" stroke="var(--edge)" stroke-width="1.5"/>
        <line x1="150" y1="14" x2="150" y2="28" stroke="var(--edge)" stroke-width="1.5"/>
      </svg>

      <!-- 三级节点 -->
      <div style="display:flex; gap:8px;">
        <div style="min-width:80px; min-height:48px; display:flex; flex-direction:column;
          justify-content:center; gap:2px; padding:8px 12px; box-sizing:border-box;
          background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-border); border-radius:var(--node-radius);
          color:var(--node-fg); text-align:center;">
          <span style="font-weight:700; font-size:12px;">前端</span>
          <span style="font-size:11px; color:var(--node-fg-dim);">5人</span>
        </div>
        <div style="min-width:80px; min-height:48px; display:flex; flex-direction:column;
          justify-content:center; gap:2px; padding:8px 12px; box-sizing:border-box;
          background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-border); border-radius:var(--node-radius);
          color:var(--node-fg); text-align:center;">
          <span style="font-weight:700; font-size:12px;">后端</span>
          <span style="font-size:11px; color:var(--node-fg-dim);">8人</span>
        </div>
      </div>
    </div><!-- /CTO 列 -->

    <!-- CMO -->
    <div style="display:flex; flex-direction:column; align-items:center;">
      <div style="min-width:120px; min-height:56px; display:flex; flex-direction:column;
        justify-content:center; gap:2px; padding:12px 16px; box-sizing:border-box;
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); border-radius:var(--node-radius);
        color:var(--node-fg); text-align:center;">
        <span style="font-weight:700; font-size:13px;">CMO</span>
        <span style="font-size:11px; color:var(--node-fg-dim);">王五</span>
      </div>

      <!-- CMO → 三级连线 -->
      <svg viewBox="0 0 200 28" preserveAspectRatio="none"
           style="width:200px; height:28px; overflow:visible; display:block;">
        <line x1="100" y1="0"  x2="100" y2="14" stroke="var(--edge)" stroke-width="1.5"/>
        <line x1="50"  y1="14" x2="150" y2="14" stroke="var(--edge)" stroke-width="1.5"/>
        <line x1="50"  y1="14" x2="50"  y2="28" stroke="var(--edge)" stroke-width="1.5"/>
        <line x1="150" y1="14" x2="150" y2="28" stroke="var(--edge)" stroke-width="1.5"/>
      </svg>

      <!-- 三级节点 -->
      <div style="display:flex; gap:8px;">
        <div style="min-width:80px; min-height:48px; display:flex; flex-direction:column;
          justify-content:center; gap:2px; padding:8px 12px; box-sizing:border-box;
          background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-border); border-radius:var(--node-radius);
          color:var(--node-fg); text-align:center;">
          <span style="font-weight:700; font-size:12px;">运营</span>
          <span style="font-size:11px; color:var(--node-fg-dim);">3人</span>
        </div>
        <div style="min-width:80px; min-height:48px; display:flex; flex-direction:column;
          justify-content:center; gap:2px; padding:8px 12px; box-sizing:border-box;
          background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-border); border-radius:var(--node-radius);
          color:var(--node-fg); text-align:center;">
          <span style="font-weight:700; font-size:12px;">设计</span>
          <span style="font-size:11px; color:var(--node-fg-dim);">2人</span>
        </div>
      </div>
    </div><!-- /CMO 列 -->

  </div><!-- /二级节点行 -->

</div>
```
> 复制规律：每层节点 `flexbox` 行 + 层与层之间夹 T 形 SVG 连线（竖线从父节点中心向下→水平横线覆盖子节点区间→竖线分别向下）；叶节点可省略子连线。

**自检**：连线颜色/节点颜色全用契约变量；根/focus 节点用 `--node-accent` 拉开层次；所有节点 `box-sizing:border-box`+`min-width/min-height`；连线是真实 SVG `<line>`。

**管线安全**：连线 SVG `<line>`；无 SVG `<text>`（标注全是 HTML）；无 CSS 箭头技巧；无伪元素；无 `mask-image`/`conic-gradient`。

---

### 看板 (kanban)

**何时用**：按阶段/状态管理在制品（WIP）；竖列代表状态，卡片堆代表任务；适合"有哪些任务在哪个阶段、哪里有瓶颈"。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "kanban",
  "columns": [
    {"id":"backlog","label":"待办",  "cards":[{"title":"用户反馈分析"},{"title":"竞品调研"}]},
    {"id":"doing",  "label":"进行中","cards":[{"title":"原型设计","focus":true},{"title":"API 文档"}]},
    {"id":"review", "label":"评审",  "cards":[{"title":"UI 走查"}]},
    {"id":"done",   "label":"完成",  "cards":[{"title":"需求确认"},{"title":"技术方案"}]}
  ]
}
```

**模板**（四列状态栏 + 卡片堆栈）：
```html
<div class="diagram kanban" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); display:flex; gap:12px; width:720px; align-items:flex-start;">

  <!-- 列：待办 -->
  <div style="flex:1; display:flex; flex-direction:column; gap:8px; min-width:0;">
    <!-- 列标题 -->
    <div style="padding:8px 12px; text-align:center; font-size:11px; font-weight:700;
      letter-spacing:1px; text-transform:uppercase; color:var(--node-fg-dim);
      border-bottom:2px solid var(--node-border);">待办</div>
    <!-- 卡片 -->
    <div style="min-height:48px; padding:10px 12px; box-sizing:border-box;
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); border-radius:var(--node-radius);
      color:var(--node-fg); font-size:12px; font-weight:600;">用户反馈分析</div>
    <div style="min-height:48px; padding:10px 12px; box-sizing:border-box;
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); border-radius:var(--node-radius);
      color:var(--node-fg); font-size:12px; font-weight:600;">竞品调研</div>
  </div>

  <!-- 列：进行中（accent 顶部色条标识活跃列） -->
  <div style="flex:1; display:flex; flex-direction:column; gap:8px; min-width:0;">
    <div style="padding:8px 12px; text-align:center; font-size:11px; font-weight:700;
      letter-spacing:1px; text-transform:uppercase; color:var(--node-accent);
      border-bottom:2px solid var(--node-accent);">进行中</div>
    <!-- focus 卡片：accent 左边条 -->
    <div style="min-height:48px; padding:10px 12px; box-sizing:border-box;
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-accent); border-left:4px solid var(--node-accent);
      border-radius:var(--node-radius); color:var(--node-fg);
      font-size:12px; font-weight:600;">原型设计</div>
    <div style="min-height:48px; padding:10px 12px; box-sizing:border-box;
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); border-radius:var(--node-radius);
      color:var(--node-fg); font-size:12px; font-weight:600;">API 文档</div>
  </div>

  <!-- 列：评审 -->
  <div style="flex:1; display:flex; flex-direction:column; gap:8px; min-width:0;">
    <div style="padding:8px 12px; text-align:center; font-size:11px; font-weight:700;
      letter-spacing:1px; text-transform:uppercase; color:var(--node-fg-dim);
      border-bottom:2px solid var(--node-border);">评审</div>
    <div style="min-height:48px; padding:10px 12px; box-sizing:border-box;
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); border-radius:var(--node-radius);
      color:var(--node-fg); font-size:12px; font-weight:600;">UI 走查</div>
  </div>

  <!-- 列：完成（accent-2 顶部标识） -->
  <div style="flex:1; display:flex; flex-direction:column; gap:8px; min-width:0;">
    <div style="padding:8px 12px; text-align:center; font-size:11px; font-weight:700;
      letter-spacing:1px; text-transform:uppercase; color:var(--node-accent-2);
      border-bottom:2px solid var(--node-accent-2);">完成</div>
    <div style="min-height:48px; padding:10px 12px; box-sizing:border-box;
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); border-radius:var(--node-radius);
      color:var(--node-fg-dim); font-size:12px; font-weight:600;">需求确认</div>
    <div style="min-height:48px; padding:10px 12px; box-sizing:border-box;
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); border-radius:var(--node-radius);
      color:var(--node-fg-dim); font-size:12px; font-weight:600;">技术方案</div>
  </div>

</div>
```
> 复制规律：每列一个 `flex:1` 竖向容器（列标题 + 卡片堆），列间 `gap:12px`；活跃列用 `--node-accent` 顶部色条；focus 卡片用 `border-left:4px solid var(--node-accent)`；完成列用 `--node-accent-2` 区分；卡片全走 `min-height` 防坍缩。

**自检**：列标题/卡片颜色全用契约变量；活跃列/focus 卡片用 `--node-accent` 突出；完成列用 `--node-accent-2` 或 `--node-fg-dim` 弱化；所有卡片 `box-sizing:border-box`+`min-height`。

**管线安全**：纯 `<div>` 堆叠；无 SVG/箭头（看板无方向箭头需求）；无伪元素装饰内容；无 `mask-image`/`conic-gradient`/`background-clip:text`；颜色全用契约变量。

---

### 交付参与阶段甘特图 (gantt-engagement)

**何时用**：展示多阶段咨询/交付参与计划——三阶段（Discovery / Design / Delivery）用彩色相位标题行分隔，每阶段下含 2–4 个工作流任务条，主色菱形里程碑标注关键交付物。适合参与汇报、交付路线图、项目启动 deck 中的"我们如何推进"页。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "gantt-engagement",
  "phases": [
    {
      "label": "Discovery", "color_var": "var(--node-accent)",
      "rows": [
        {"label": "Stakeholder Interviews", "start": 0, "span": 1},
        {"label": "Process Mapping",        "start": 0, "span": 2}
      ]
    },
    {
      "label": "Design", "color_var": "var(--node-accent-2)",
      "rows": [
        {"label": "Theme Synthesis", "start": 2, "span": 1},
        {"label": "Solution Concepts", "start": 3, "span": 1}
      ]
    },
    {
      "label": "Delivery", "color_var": "var(--node-fg-dim)",
      "rows": [
        {"label": "Prioritisation Workshop", "start": 4, "span": 1},
        {"label": "Readout & Handoff",       "start": 5, "span": 1}
      ]
    }
  ],
  "total_weeks": 6,
  "milestones": [
    {"label": "Kickoff",  "at": 0},
    {"label": "Synthesis","at": 2},
    {"label": "Readout",  "at": 5}
  ]
}
```

**模板**（相位标题行 + 任务条 + 主色菱形里程碑，HTML 叠加标注，禁 SVG `<text>`）：
```html
<div class="diagram gantt-engagement" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,6px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); width:720px;">

  <!-- Week ruler -->
  <div style="display:flex; margin-left:160px; margin-bottom:4px;">
    <div style="flex:1; text-align:center; font-size:10px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">Wk 1</div>
    <div style="flex:1; text-align:center; font-size:10px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">Wk 2</div>
    <div style="flex:1; text-align:center; font-size:10px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">Wk 3</div>
    <div style="flex:1; text-align:center; font-size:10px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">Wk 4</div>
    <div style="flex:1; text-align:center; font-size:10px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">Wk 5</div>
    <div style="flex:1; text-align:center; font-size:10px; font-weight:700; color:var(--node-fg-dim); letter-spacing:1px;">Wk 6</div>
  </div>

  <!-- Phase 1: Discovery (accent header row) -->
  <div style="display:flex; align-items:center; background:var(--node-accent); border-radius:6px 6px 0 0; margin-bottom:2px;">
    <span style="width:160px; flex-shrink:0; font-size:11px; font-weight:800; letter-spacing:0.10em; text-transform:uppercase; color:var(--node-bg-from); padding:6px 10px 6px 0; text-align:right;">Discovery</span>
    <div style="flex:6; height:6px;"></div>
  </div>

  <!-- Discovery rows -->
  <div style="display:flex; flex-direction:column; gap:6px; margin-bottom:8px;">
    <div style="display:flex; align-items:center; min-height:34px;">
      <span style="width:152px; flex-shrink:0; font-size:11px; font-weight:600; color:var(--node-fg); padding-right:8px; text-align:right;">Stakeholder Interviews</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); position:relative; height:34px;">
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="position:absolute; left:0%; width:16.67%; top:7px; height:20px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-accent); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 6px;">
          <span style="font-size:10px; color:var(--node-fg-dim);">Interviews</span></div>
      </div>
    </div>
    <div style="display:flex; align-items:center; min-height:34px;">
      <span style="width:152px; flex-shrink:0; font-size:11px; font-weight:600; color:var(--node-fg); padding-right:8px; text-align:right;">Process Mapping</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); position:relative; height:34px;">
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="position:absolute; left:0%; width:33.33%; top:7px; height:20px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-accent); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 6px;">
          <span style="font-size:10px; color:var(--node-fg-dim);">Process Mapping</span></div>
      </div>
    </div>
  </div>

  <!-- Phase 2: Design (accent-2 header row) -->
  <div style="display:flex; align-items:center; background:var(--node-accent-2); border-radius:6px 6px 0 0; margin-bottom:2px;">
    <span style="width:160px; flex-shrink:0; font-size:11px; font-weight:800; letter-spacing:0.10em; text-transform:uppercase; color:var(--node-bg-from); padding:6px 10px 6px 0; text-align:right;">Design</span>
    <div style="flex:6; height:6px;"></div>
  </div>

  <!-- Design rows -->
  <div style="display:flex; flex-direction:column; gap:6px; margin-bottom:8px;">
    <div style="display:flex; align-items:center; min-height:34px;">
      <span style="width:152px; flex-shrink:0; font-size:11px; font-weight:600; color:var(--node-fg); padding-right:8px; text-align:right;">Theme Synthesis</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); position:relative; height:34px;">
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="position:absolute; left:33.33%; width:16.67%; top:7px; height:20px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-accent-2); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 6px;">
          <span style="font-size:10px; color:var(--node-fg-dim);">Synthesis</span></div>
      </div>
    </div>
    <div style="display:flex; align-items:center; min-height:34px;">
      <span style="width:152px; flex-shrink:0; font-size:11px; font-weight:600; color:var(--node-fg); padding-right:8px; text-align:right;">Solution Concepts</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); position:relative; height:34px;">
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="position:absolute; left:50%; width:16.67%; top:7px; height:20px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-accent-2); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 6px;">
          <span style="font-size:10px; color:var(--node-fg-dim);">Concepts</span></div>
      </div>
    </div>
  </div>

  <!-- Phase 3: Delivery (dim header row) -->
  <div style="display:flex; align-items:center; background:var(--node-fg-dim); border-radius:6px 6px 0 0; margin-bottom:2px;">
    <span style="width:160px; flex-shrink:0; font-size:11px; font-weight:800; letter-spacing:0.10em; text-transform:uppercase; color:var(--node-bg-from); padding:6px 10px 6px 0; text-align:right;">Delivery</span>
    <div style="flex:6; height:6px;"></div>
  </div>

  <!-- Delivery rows -->
  <div style="display:flex; flex-direction:column; gap:6px; margin-bottom:8px;">
    <div style="display:flex; align-items:center; min-height:34px;">
      <span style="width:152px; flex-shrink:0; font-size:11px; font-weight:600; color:var(--node-fg); padding-right:8px; text-align:right;">Prioritisation Workshop</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); position:relative; height:34px;">
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="position:absolute; left:66.67%; width:16.67%; top:7px; height:20px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-border); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 6px;">
          <span style="font-size:10px; color:var(--node-fg-dim);">Workshop</span></div>
      </div>
    </div>
    <div style="display:flex; align-items:center; min-height:34px;">
      <span style="width:152px; flex-shrink:0; font-size:11px; font-weight:600; color:var(--node-fg); padding-right:8px; text-align:right;">Readout &amp; Handoff</span>
      <div style="flex:6; display:grid; grid-template-columns:repeat(6,1fr); position:relative; height:34px;">
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="border-left:1px solid var(--edge); opacity:0.3;"></div><div style="border-left:1px solid var(--edge); opacity:0.3;"></div>
        <div style="position:absolute; left:83.33%; width:16.67%; top:7px; height:20px;
          background:linear-gradient(90deg,var(--node-bg-from),var(--node-bg-to));
          border:1px solid var(--node-accent); border-radius:var(--node-radius);
          box-sizing:border-box; display:flex; align-items:center; padding:0 6px;">
          <span style="font-size:10px; color:var(--node-fg-dim);">Readout</span></div>
      </div>
    </div>
  </div>

  <!-- Milestones (SVG polygon diamonds + HTML labels, no SVG <text>) -->
  <div style="position:relative; margin-left:160px; height:36px; margin-top:4px;">
    <div style="position:absolute; left:0%; top:0; display:flex; flex-direction:column; align-items:center;">
      <svg viewBox="0 0 14 14" style="width:14px; height:14px; display:block; overflow:visible;">
        <polygon points="7,1 13,7 7,13 1,7" fill="var(--node-accent)"/>
      </svg>
      <span style="font-size:9px; font-weight:700; color:var(--node-accent); margin-top:2px; white-space:nowrap;">Kickoff</span>
    </div>
    <div style="position:absolute; left:33.33%; top:0; transform:translateX(-50%); display:flex; flex-direction:column; align-items:center;">
      <svg viewBox="0 0 14 14" style="width:14px; height:14px; display:block; overflow:visible;">
        <polygon points="7,1 13,7 7,13 1,7" fill="var(--node-accent)"/>
      </svg>
      <span style="font-size:9px; font-weight:700; color:var(--node-accent); margin-top:2px; white-space:nowrap;">Synthesis</span>
    </div>
    <div style="position:absolute; left:83.33%; top:0; transform:translateX(-50%); display:flex; flex-direction:column; align-items:center;">
      <svg viewBox="0 0 14 14" style="width:14px; height:14px; display:block; overflow:visible;">
        <polygon points="7,1 13,7 7,13 1,7" fill="var(--node-accent)"/>
      </svg>
      <span style="font-size:9px; font-weight:700; color:var(--node-accent); margin-top:2px; white-space:nowrap;">Readout</span>
    </div>
  </div>

</div>
```

**自检**：Discovery 标题行走 `var(--node-accent)` 背景 + `var(--node-bg-from)` 文字；Design 走 `var(--node-accent-2)`；Delivery 走 `var(--node-fg-dim)`；任务条边框随相位色；里程碑用 SVG `<polygon>` 菱形 + HTML span 标注（无 SVG `<text>`）；颜色全走契约变量。

**管线安全**：菱形 SVG `<polygon>`；无 SVG `<text>`（标注全是 HTML span）；无伪元素；无 `mask-image`/`conic-gradient`；任务条为真实 `<div>`。
