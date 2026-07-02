# diagram-process-flow（流程与过程族）

> family `block_ref`: `diagram-process-flow`。配方：`flowchart` / `swimlane` / `sequence` / `state-machine` / `data-flow`。
> 前置：先读 `blocks/diagram.md` 的**主题契约**与**共享基元**（节点盒/连线/箭头/标注/8px 栅格）。本族所有模板的颜色字体只用契约里的局部变量。
> 管线：HTML→SVG→PPTX，遵守 pipeline-compat.md（SVG `<polygon>` 箭头、真实 `<div>`/SVG `<line>`/`<path>` 连线、HTML 叠加标注、禁 `<text>`/`mask-image`/`conic-gradient`/`background-clip:text`）。

---

### 流程图 (flowchart)

**何时用**：步骤/决策逻辑、业务流程、工作流；兼做 UML Activity 图。节点形状区分动作（矩形）、判断（菱形）、开始/结束（椭圆/圆角矩形）。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "flowchart",
  "nodes": [
    {"id":"start","label":"开始","shape":"oval"},
    {"id":"step1","label":"接收请求","shape":"rect"},
    {"id":"check","label":"鉴权通过？","shape":"diamond"},
    {"id":"step2","label":"处理业务","shape":"rect","focus":true},
    {"id":"reject","label":"返回 401","shape":"rect"},
    {"id":"end","label":"响应成功","shape":"oval"}
  ],
  "edges": [
    {"from":"start","to":"step1"},
    {"from":"step1","to":"check"},
    {"from":"check","to":"step2","label":"是"},
    {"from":"check","to":"reject","label":"否"},
    {"from":"step2","to":"end"},
    {"from":"reject","to":"end"}
  ]
}
```

**模板**（CSS Grid 节点格 + SVG 连线 + HTML 叠加标注）：
```html
<div class="diagram flowchart" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --edge-strong:var(--accent-1);
  --node-accent:var(--accent-1); --label-font:var(--font-primary);
  font-family:var(--label-font); width:640px;">

  <!-- 行1：开始节点 -->
  <div style="display:flex; justify-content:center; margin-bottom:8px;">
    <div style="min-width:120px; min-height:40px; display:flex; align-items:center; justify-content:center;
      padding:8px 20px; box-sizing:border-box; border-radius:999px;
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); color:var(--node-fg); font-size:14px; font-weight:700;">
      开始
    </div>
  </div>

  <!-- 箭头：下 -->
  <div style="display:flex; justify-content:center; height:24px;">
    <svg viewBox="0 0 20 24" style="width:20px; height:24px; overflow:visible; display:block;">
      <line x1="10" y1="0" x2="10" y2="16" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="4,14 10,24 16,14" fill="var(--edge)"/>
    </svg>
  </div>

  <!-- 行2：步骤1 -->
  <div style="display:flex; justify-content:center; margin-bottom:8px;">
    <div style="min-width:160px; min-height:48px; display:flex; align-items:center; justify-content:center;
      padding:10px 20px; box-sizing:border-box; border-radius:var(--node-radius);
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); color:var(--node-fg); font-size:14px; font-weight:700;">
      接收请求
    </div>
  </div>

  <!-- 箭头：下 -->
  <div style="display:flex; justify-content:center; height:24px;">
    <svg viewBox="0 0 20 24" style="width:20px; height:24px; overflow:visible; display:block;">
      <line x1="10" y1="0" x2="10" y2="16" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="4,14 10,24 16,14" fill="var(--edge)"/>
    </svg>
  </div>

  <!-- 行3：判断菱形（inline SVG polygon + HTML label 叠加） -->
  <div style="display:flex; justify-content:center; margin-bottom:8px; position:relative; height:72px;">
    <div style="position:relative; width:200px; height:72px;">
      <svg viewBox="0 0 200 72" style="width:200px; height:72px; overflow:visible; display:block;">
        <polygon points="100,4 196,36 100,68 4,36" fill="var(--node-bg-from)"
          stroke="var(--node-border)" stroke-width="1.5"/>
      </svg>
      <span style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
        font-size:13px; font-weight:700; color:var(--node-fg); white-space:nowrap;">鉴权通过？</span>
    </div>
  </div>

  <!-- 判断分支：左（否）+ 右（是） -->
  <div style="position:relative; display:flex; justify-content:center; height:80px; width:100%;">
    <!-- 中线向左折 → 拒绝节点；中线向下 → 是 -->
    <svg viewBox="0 0 640 80" style="width:640px; height:80px; overflow:visible; display:block; position:absolute; left:0; top:0;">
      <!-- 是：向下 -->
      <line x1="320" y1="0" x2="320" y2="60" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="314,58 320,68 326,58" fill="var(--edge)"/>
      <!-- 否：右侧折线到拒绝节点 -->
      <line x1="320" y1="12" x2="520" y2="12" stroke="var(--edge)" stroke-width="1.5"/>
      <line x1="520" y1="12" x2="520" y2="60" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="514,58 520,68 526,58" fill="var(--edge)"/>
    </svg>
    <!-- 分支标注：HTML 叠加 -->
    <span style="position:absolute; left:325px; top:4px; font-size:11px; font-weight:700; color:var(--node-fg-dim);">是</span>
    <span style="position:absolute; left:400px; top:0px; font-size:11px; font-weight:700; color:var(--node-fg-dim);">否</span>
  </div>

  <!-- 行4：两个节点横排（focus + 拒绝） -->
  <div style="display:flex; justify-content:center; gap:0; align-items:flex-start; position:relative;">
    <!-- 中间留白撑开，让两节点对齐分支线 -->
    <div style="flex:1; display:flex; justify-content:center;">
      <!-- focus 节点 -->
      <div style="min-width:160px; min-height:48px; display:flex; align-items:center; justify-content:center;
        padding:10px 20px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-accent); box-shadow:0 0 0 1px var(--node-accent);
        color:var(--node-fg); font-size:14px; font-weight:700;">
        处理业务
      </div>
    </div>
    <div style="width:200px; display:flex; justify-content:flex-end; padding-right:40px;">
      <!-- 拒绝节点 -->
      <div style="min-width:120px; min-height:48px; display:flex; align-items:center; justify-content:center;
        padding:10px 16px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); color:var(--node-fg); font-size:14px; font-weight:700;">
        返回 401
      </div>
    </div>
  </div>

  <!-- 箭头：两支汇聚向下 -->
  <div style="position:relative; height:48px; width:100%;">
    <svg viewBox="0 0 640 48" style="width:640px; height:48px; overflow:visible; display:block; position:absolute; left:0; top:0;">
      <!-- 左支：处理业务 → 下 -->
      <line x1="320" y1="0" x2="320" y2="32" stroke="var(--edge)" stroke-width="1.5"/>
      <!-- 右支：返回401 折回中心 -->
      <line x1="520" y1="0" x2="520" y2="20" stroke="var(--edge)" stroke-width="1.5"/>
      <line x1="520" y1="20" x2="320" y2="20" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="314,30 320,40 326,30" fill="var(--edge)"/>
    </svg>
  </div>

  <!-- 行5：结束节点 -->
  <div style="display:flex; justify-content:center;">
    <div style="min-width:120px; min-height:40px; display:flex; align-items:center; justify-content:center;
      padding:8px 20px; box-sizing:border-box; border-radius:999px;
      background:var(--node-accent); color:var(--card-bg-from); font-size:14px; font-weight:700;">
      响应成功
    </div>
  </div>
</div>
```
> 复制规律：每步一个节点块，中间夹 SVG arrow；判断菱形 = inline SVG `<polygon>` + HTML 叠加标注；分支用 SVG 折线；focus 节点 accent 描边+glow；开始/结束 border-radius:999px 椭圆形。

**自检**：节点形状（矩形/菱形/椭圆）颜色字体全用契约变量；判断标注是 HTML span；focus 节点 `--node-accent` 描边；`min-height`+`box-sizing:border-box`。

**管线安全**：菱形是 SVG `<polygon>`；箭头是 SVG `<polygon>`；无 `<text>`；无伪元素内容；无 `mask-image`/`conic-gradient`。

---

### 泳道图 (swimlane)

**何时用**：多角色跨职能流程（谁做哪步）；也适用 BPMN pools/lanes、跨系统交互。水平泳道（角色横排）或垂直泳道均可。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "swimlane",
  "orientation": "horizontal",
  "lanes": [
    {"id":"user","label":"用户","nodes":[{"id":"u1","label":"提交申请"},{"id":"u2","label":"收到通知"}]},
    {"id":"sys","label":"系统","nodes":[{"id":"s1","label":"验证数据","focus":true},{"id":"s2","label":"生成记录"}]},
    {"id":"admin","label":"审批人","nodes":[{"id":"a1","label":"审核"},{"id":"a2","label":"批准/驳回"}]}
  ],
  "edges":[
    {"from":"u1","to":"s1"},{"from":"s1","to":"a1"},{"from":"a1","to":"s2"},{"from":"s2","to":"u2"},{"from":"a1","to":"a2"}
  ]
}
```

**模板**（水平泳道：每行一个角色，节点内并排，跨行 SVG 箭头）：
```html
<div class="diagram swimlane" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --edge-strong:var(--accent-1);
  --node-accent:var(--accent-1); --label-font:var(--font-primary);
  font-family:var(--label-font); width:700px; border:1px solid var(--node-border); border-radius:var(--node-radius);">

  <!-- 标题行 -->
  <div style="display:grid; grid-template-columns:72px 1fr 1fr; border-bottom:1px solid var(--node-border);">
    <div style="padding:8px 12px; font-size:11px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:var(--node-fg-dim);">角色</div>
    <div style="padding:8px 12px; font-size:11px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:var(--node-fg-dim); border-left:1px solid var(--node-border);">步骤 1-2</div>
    <div style="padding:8px 12px; font-size:11px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:var(--node-fg-dim); border-left:1px solid var(--node-border);">步骤 3-4</div>
  </div>

  <!-- 泳道：用户 -->
  <div style="display:grid; grid-template-columns:72px 1fr 1fr; border-bottom:1px solid var(--node-border); background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); min-height:72px;">
    <div style="display:flex; align-items:center; padding:8px 12px; font-size:13px; font-weight:700; color:var(--node-fg); border-right:1px solid var(--node-border);">用户</div>
    <div style="display:flex; align-items:center; justify-content:center; padding:12px; border-right:1px solid var(--node-border);">
      <div style="min-width:120px; min-height:48px; display:flex; align-items:center; justify-content:center;
        padding:10px 16px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); color:var(--node-fg); font-size:13px; font-weight:700;">
        提交申请
      </div>
    </div>
    <div style="display:flex; align-items:center; justify-content:center; padding:12px;">
      <div style="min-width:120px; min-height:48px; display:flex; align-items:center; justify-content:center;
        padding:10px 16px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); color:var(--node-fg); font-size:13px; font-weight:700;">
        收到通知
      </div>
    </div>
  </div>

  <!-- 泳道：系统 -->
  <div style="display:grid; grid-template-columns:72px 1fr 1fr; border-bottom:1px solid var(--node-border); min-height:72px;">
    <div style="display:flex; align-items:center; padding:8px 12px; font-size:13px; font-weight:700; color:var(--node-fg); border-right:1px solid var(--node-border);">系统</div>
    <div style="display:flex; align-items:center; justify-content:center; padding:12px; border-right:1px solid var(--node-border);">
      <!-- focus 节点 -->
      <div style="min-width:120px; min-height:48px; display:flex; align-items:center; justify-content:center;
        padding:10px 16px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-accent); box-shadow:0 0 0 1px var(--node-accent);
        color:var(--node-fg); font-size:13px; font-weight:700;">
        验证数据
      </div>
    </div>
    <div style="display:flex; align-items:center; justify-content:center; padding:12px;">
      <div style="min-width:120px; min-height:48px; display:flex; align-items:center; justify-content:center;
        padding:10px 16px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); color:var(--node-fg); font-size:13px; font-weight:700;">
        生成记录
      </div>
    </div>
  </div>

  <!-- 泳道：审批人 -->
  <div style="display:grid; grid-template-columns:72px 1fr 1fr; min-height:72px;">
    <div style="display:flex; align-items:center; padding:8px 12px; font-size:13px; font-weight:700; color:var(--node-fg); border-right:1px solid var(--node-border);">审批人</div>
    <div style="display:flex; align-items:center; justify-content:center; padding:12px; border-right:1px solid var(--node-border);">
      <div style="min-width:120px; min-height:48px; display:flex; align-items:center; justify-content:center;
        padding:10px 16px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); color:var(--node-fg); font-size:13px; font-weight:700;">
        审核
      </div>
    </div>
    <div style="display:flex; align-items:center; justify-content:center; padding:12px;">
      <div style="min-width:120px; min-height:48px; display:flex; align-items:center; justify-content:center;
        padding:10px 16px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); color:var(--node-fg); font-size:13px; font-weight:700;">
        批准/驳回
      </div>
    </div>
  </div>

  <!-- 跨泳道箭头：覆盖层 SVG，overflow:visible -->
  <div style="position:relative; height:0; overflow:visible;">
    <svg viewBox="0 0 700 216" style="position:absolute; top:-216px; left:0; width:700px; height:216px; overflow:visible; pointer-events:none; display:block;">
      <!-- 用户-提交申请 → 系统-验证数据（向下跨行） -->
      <line x1="314" y1="80" x2="314" y2="120" stroke="var(--edge-strong)" stroke-width="1.5"/>
      <polygon points="308,118 314,128 320,118" fill="var(--edge-strong)"/>
      <!-- 系统-验证数据 → 审批人-审核（向下跨行） -->
      <line x1="314" y1="152" x2="314" y2="168" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="308,166 314,176 320,166" fill="var(--edge)"/>
      <!-- 审批人-生成记录标注 → 用户-收到通知（跨行向上，折线） -->
      <line x1="530" y1="176" x2="530" y2="60" stroke="var(--edge)" stroke-width="1.5" stroke-dasharray="4 3"/>
      <polygon points="524,62 530,52 536,62" fill="var(--edge)"/>
    </svg>
  </div>
</div>
```
> 复制规律：每条泳道一行 grid（角色标签 + N 个节点格），用 `grid-template-columns` 对齐各列；跨泳道箭头用 `position:relative; height:0; overflow:visible` 覆盖层的 SVG 连线+polygon 箭头，标注是 HTML span。
>
> **角色/泳道标签用「描边款」，不做实心色块**：角色名保持中性文字（`color:var(--node-fg)`）即可；若要加胶囊/chip 强调，必须 `background:transparent; border:1.5px solid var(--node-accent); color:var(--node-accent)`（描边），**绝不用 `background:var(--node-accent)` 满填**——满填的标签比它要标注的节点还重，权重倒挂（见 `diagram.md`「实心填充只留给强调/交互」）。

**自检**：泳道行用 CSS grid 对齐，角色名是真实 span；**角色/泳道标签为中性文字或描边胶囊，非实心色块**；跨泳道连线用 SVG；focus 节点 accent 描边（非实心底、标题仍为 `--node-fg`）；所有颜色来自契约变量。

**管线安全**：无 SVG `<text>`；无伪元素装饰；箭头 `<polygon>`；连线 SVG `<line>`；无 `mask-image`/`conic-gradient`。

---

### 时序图 (sequence)

**何时用**：参与者/服务之间有时间顺序的消息交互；适合 API 调用链、协议流程、UML Sequence、C4 Dynamic。时间从上到下，生命线纵列，消息为横向带标注箭头。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "sequence",
  "actors": [
    {"id":"client","label":"Client"},
    {"id":"api","label":"API GW","focus":true},
    {"id":"svc","label":"Auth Svc"},
    {"id":"db","label":"DB"}
  ],
  "messages": [
    {"from":"client","to":"api","label":"POST /login","type":"sync"},
    {"from":"api","to":"svc","label":"验证凭据","type":"sync"},
    {"from":"svc","to":"db","label":"查询用户","type":"sync"},
    {"from":"db","to":"svc","label":"用户记录","type":"return"},
    {"from":"svc","to":"api","label":"Token","type":"return"},
    {"from":"api","to":"client","label":"200 OK + JWT","type":"return"}
  ]
}
```

**模板**（生命线列 + 激活框 + 横向消息箭头 + HTML 标注）：
```html
<div class="diagram sequence" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --edge-strong:var(--accent-1);
  --node-accent:var(--accent-1); --label-font:var(--font-primary);
  font-family:var(--label-font); width:680px; position:relative;">

  <!-- 角色头部行 -->
  <div style="display:flex; gap:0; padding-left:0;">
    <!-- 4 角色等宽排列 -->
    <div style="flex:1; display:flex; justify-content:center; padding-bottom:8px;">
      <div style="min-width:100px; min-height:40px; display:flex; align-items:center; justify-content:center;
        padding:8px 14px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); color:var(--node-fg); font-size:13px; font-weight:700;">
        Client
      </div>
    </div>
    <div style="flex:1; display:flex; justify-content:center; padding-bottom:8px;">
      <!-- focus 角色 -->
      <div style="min-width:100px; min-height:40px; display:flex; align-items:center; justify-content:center;
        padding:8px 14px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-accent); box-shadow:0 0 0 1px var(--node-accent);
        color:var(--node-fg); font-size:13px; font-weight:700;">
        API GW
      </div>
    </div>
    <div style="flex:1; display:flex; justify-content:center; padding-bottom:8px;">
      <div style="min-width:100px; min-height:40px; display:flex; align-items:center; justify-content:center;
        padding:8px 14px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); color:var(--node-fg); font-size:13px; font-weight:700;">
        Auth Svc
      </div>
    </div>
    <div style="flex:1; display:flex; justify-content:center; padding-bottom:8px;">
      <div style="min-width:100px; min-height:40px; display:flex; align-items:center; justify-content:center;
        padding:8px 14px; box-sizing:border-box; border-radius:var(--node-radius);
        background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
        border:1px solid var(--node-border); color:var(--node-fg); font-size:13px; font-weight:700;">
        DB
      </div>
    </div>
  </div>

  <!-- 消息区：SVG 画生命线 + 激活框 + 箭头；HTML 叠加标注 -->
  <div style="position:relative; height:320px;">
    <svg viewBox="0 0 680 320" style="width:680px; height:320px; overflow:visible; display:block;">
      <!-- 生命线（虚线竖线），4 列：x=85, 255, 425, 595 -->
      <line x1="85"  y1="0" x2="85"  y2="320" stroke="var(--edge)" stroke-width="1" stroke-dasharray="4 4"/>
      <line x1="255" y1="0" x2="255" y2="320" stroke="var(--edge)" stroke-width="1" stroke-dasharray="4 4"/>
      <line x1="425" y1="0" x2="425" y2="320" stroke="var(--edge)" stroke-width="1" stroke-dasharray="4 4"/>
      <line x1="595" y1="0" x2="595" y2="320" stroke="var(--edge)" stroke-width="1" stroke-dasharray="4 4"/>

      <!-- 激活框：API GW（focus，竖向窄矩形） -->
      <rect x="249" y="30" width="12" height="260" rx="2"
        fill="var(--node-bg-from)" stroke="var(--node-accent)" stroke-width="1.5"/>

      <!-- 消息1：Client→API GW，y=40（同步，实线） -->
      <line x1="85" y1="40" x2="249" y2="40" stroke="var(--edge-strong)" stroke-width="1.5"/>
      <polygon points="241,34 255,40 241,46" fill="var(--edge-strong)"/>

      <!-- 消息2：API GW→Auth Svc，y=80 -->
      <line x1="261" y1="80" x2="421" y2="80" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="413,74 425,80 413,86" fill="var(--edge)"/>

      <!-- 消息3：Auth Svc→DB，y=120 -->
      <line x1="425" y1="120" x2="591" y2="120" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="583,114 595,120 583,126" fill="var(--edge)"/>

      <!-- 消息4：DB→Auth Svc，return y=160（虚线） -->
      <line x1="595" y1="160" x2="429" y2="160" stroke="var(--edge)" stroke-width="1.5" stroke-dasharray="5 3"/>
      <polygon points="437,154 425,160 437,166" fill="var(--edge)"/>

      <!-- 消息5：Auth Svc→API GW，return y=200（虚线） -->
      <line x1="425" y1="200" x2="265" y2="200" stroke="var(--edge)" stroke-width="1.5" stroke-dasharray="5 3"/>
      <polygon points="273,194 261,200 273,206" fill="var(--edge)"/>

      <!-- 消息6：API GW→Client，return y=240（虚线） -->
      <line x1="249" y1="240" x2="89" y2="240" stroke="var(--edge-strong)" stroke-width="1.5" stroke-dasharray="5 3"/>
      <polygon points="97,234 85,240 97,246" fill="var(--edge-strong)"/>
    </svg>

    <!-- HTML 叠加消息标注 -->
    <span style="position:absolute; left:100px; top:26px; font-size:11px; font-weight:600; color:var(--node-fg);">POST /login</span>
    <span style="position:absolute; left:270px; top:66px; font-size:11px; font-weight:600; color:var(--node-fg-dim);">验证凭据</span>
    <span style="position:absolute; left:435px; top:106px; font-size:11px; font-weight:600; color:var(--node-fg-dim);">查询用户</span>
    <span style="position:absolute; left:435px; top:146px; font-size:11px; color:var(--node-fg-dim);">用户记录</span>
    <span style="position:absolute; left:280px; top:186px; font-size:11px; color:var(--node-fg-dim);">Token</span>
    <span style="position:absolute; left:100px; top:226px; font-size:11px; font-weight:600; color:var(--node-fg);">200 OK + JWT</span>
  </div>
</div>
```
> 复制规律：角色等宽 flex 列（`flex:1`）排布；生命线是 SVG 虚线竖线；激活框是 SVG `<rect>`；消息是 SVG `<line>` + `<polygon>` 箭头；标注一律 HTML `<span>` 绝对定位叠加。return 消息用 `stroke-dasharray` 虚线。

**自检**：生命线/消息/激活框颜色全用契约变量；标注是 HTML span；focus 角色 accent 描边+激活框；return 消息虚线区分。

**管线安全**：无 SVG `<text>`；箭头 `<polygon>`；无伪元素；无 `mask-image`/`conic-gradient`。

---

### 状态机 (state-machine)

**何时用**：对象/UI/协议生命周期的状态转换；UML State Diagram。状态节点 + 带 guard 标注的有向边 + 初态（实心圆）+ 终态（靶心圆）+ 回环边。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "state-machine",
  "states": [
    {"id":"idle","label":"空闲"},
    {"id":"processing","label":"处理中","focus":true},
    {"id":"done","label":"已完成"},
    {"id":"error","label":"出错"}
  ],
  "transitions": [
    {"from":"__init__","to":"idle"},
    {"from":"idle","to":"processing","label":"submit"},
    {"from":"processing","to":"done","label":"success"},
    {"from":"processing","to":"error","label":"fail"},
    {"from":"error","to":"idle","label":"reset"},
    {"from":"done","to":"__final__"}
  ]
}
```

**模板**（CSS Grid 节点布局 + SVG 连线/回环边 + HTML 标注）：
```html
<div class="diagram state-machine" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --edge-strong:var(--accent-1);
  --node-accent:var(--accent-1); --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); width:640px; position:relative;">

  <!-- 节点行1：初态 + 空闲 -->
  <div style="display:flex; align-items:center; justify-content:flex-start; gap:0; padding:8px 32px;">

    <!-- 初态：实心圆 -->
    <div style="display:flex; align-items:center; justify-content:center; width:32px; height:32px;">
      <svg viewBox="0 0 32 32" style="width:32px; height:32px; display:block;">
        <circle cx="16" cy="16" r="10" fill="var(--node-fg)"/>
      </svg>
    </div>

    <!-- 初态→空闲 箭头 -->
    <svg viewBox="0 0 56 16" style="width:56px; height:16px; overflow:visible; display:block;">
      <line x1="0" y1="8" x2="40" y2="8" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="38,2 52,8 38,14" fill="var(--edge)"/>
    </svg>

    <!-- 空闲节点 -->
    <div style="min-width:112px; min-height:48px; display:flex; align-items:center; justify-content:center;
      padding:10px 18px; box-sizing:border-box; border-radius:var(--node-radius);
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); color:var(--node-fg); font-size:14px; font-weight:700;">
      空闲
    </div>

    <!-- 空闲→处理中 箭头+标注 -->
    <div style="position:relative; width:120px; height:16px; display:flex; align-items:center;">
      <svg viewBox="0 0 120 16" style="width:120px; height:16px; overflow:visible; display:block;">
        <line x1="0" y1="8" x2="104" y2="8" stroke="var(--edge-strong)" stroke-width="1.5"/>
        <polygon points="102,2 116,8 102,14" fill="var(--edge-strong)"/>
      </svg>
      <span style="position:absolute; left:20px; top:-14px; font-size:11px; font-weight:600; color:var(--node-fg-dim); white-space:nowrap;">submit</span>
    </div>

    <!-- 处理中节点（focus） -->
    <div style="min-width:112px; min-height:48px; display:flex; align-items:center; justify-content:center;
      padding:10px 18px; box-sizing:border-box; border-radius:var(--node-radius);
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-accent); box-shadow:0 0 0 1px var(--node-accent);
      color:var(--node-fg); font-size:14px; font-weight:700;">
      处理中
    </div>
  </div>

  <!-- 分支箭头区：处理中 → 已完成 / 出错 -->
  <div style="position:relative; height:80px; width:100%;">
    <svg viewBox="0 0 640 80" style="width:640px; height:80px; overflow:visible; display:block; position:absolute; left:0; top:0;">
      <!-- 中心 x 约在 490（处理中节点中心） -->
      <!-- 向右到已完成 -->
      <line x1="490" y1="8" x2="600" y2="8" stroke="var(--edge)" stroke-width="1.5"/>
      <line x1="600" y1="8" x2="600" y2="64" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="594,62 600,72 606,62" fill="var(--edge)"/>
      <!-- 向左到出错 -->
      <line x1="434" y1="8" x2="230" y2="8" stroke="var(--edge)" stroke-width="1.5"/>
      <line x1="230" y1="8" x2="230" y2="64" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="224,62 230,72 236,62" fill="var(--edge)"/>
    </svg>
    <!-- guard 标注 -->
    <span style="position:absolute; left:520px; top:0; font-size:11px; font-weight:600; color:var(--node-fg-dim);">success</span>
    <span style="position:absolute; left:280px; top:0; font-size:11px; font-weight:600; color:var(--node-fg-dim);">fail</span>
  </div>

  <!-- 节点行2：出错 + 已完成 + 终态 -->
  <div style="display:flex; align-items:center; padding:0 32px; gap:0;">
    <!-- 出错节点 -->
    <div style="min-width:112px; min-height:48px; display:flex; align-items:center; justify-content:center;
      padding:10px 18px; box-sizing:border-box; border-radius:var(--node-radius);
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-accent-2); color:var(--node-fg); font-size:14px; font-weight:700;">
      出错
    </div>

    <!-- reset 回环箭头：出错 → 空闲（向左上折线） -->
    <div style="flex:1; position:relative; height:48px;">
      <svg viewBox="0 0 300 48" style="width:300px; height:48px; overflow:visible; display:block; position:absolute; left:-80px; top:0;">
        <path d="M 0 24 H -80 V -88 H -246 V -72" fill="none" stroke="var(--edge)" stroke-width="1.5" stroke-dasharray="5 3"/>
        <polygon points="-252,-80 -246,-66 -240,-80" fill="var(--edge)"/>
      </svg>
      <span style="position:absolute; left:-160px; top:-100px; font-size:11px; font-weight:600; color:var(--node-fg-dim);">reset</span>
    </div>

    <!-- 已完成节点 -->
    <div style="min-width:112px; min-height:48px; display:flex; align-items:center; justify-content:center;
      padding:10px 18px; box-sizing:border-box; border-radius:var(--node-radius);
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:1px solid var(--node-border); color:var(--node-fg); font-size:14px; font-weight:700;">
      已完成
    </div>

    <!-- 已完成→终态 箭头 -->
    <svg viewBox="0 0 64 16" style="width:64px; height:16px; overflow:visible; display:block;">
      <line x1="0" y1="8" x2="48" y2="8" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="46,2 60,8 46,14" fill="var(--edge)"/>
    </svg>

    <!-- 终态：靶心圆（外圈+实心内圆） -->
    <div style="display:flex; align-items:center; justify-content:center; width:32px; height:32px;">
      <svg viewBox="0 0 32 32" style="width:32px; height:32px; display:block;">
        <circle cx="16" cy="16" r="12" fill="none" stroke="var(--node-fg)" stroke-width="1.5"/>
        <circle cx="16" cy="16" r="7" fill="var(--node-fg)"/>
      </svg>
    </div>
  </div>
</div>
```
> 复制规律：节点为标准节点盒；初态用实心圆 `<circle>`，终态用靶心双圆；有向边是 SVG `<line>`+`<polygon>`；回环边用 SVG `<path>` 折线；guard 标注是 HTML span；focus 节点 accent 描边。

**自检**：初态/终态是内联 SVG circle；回环边是 SVG path，非 CSS；guard/状态名是 HTML span；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；箭头 `<polygon>`；无伪元素；无 `mask-image`/`conic-gradient`。

---

### 数据流图 (data-flow)

**何时用**：DFD（数据流图），展示数据如何在系统中流动；适合系统分析、威胁建模、架构数据路径说明。区分外部实体（方形）、处理圆（圆形）、数据存储（开口矩形）。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "data-flow",
  "nodes": [
    {"id":"user","label":"用户","shape":"external"},
    {"id":"auth","label":"鉴权服务","shape":"process","focus":true},
    {"id":"store","label":"会话存储","shape":"datastore"},
    {"id":"api","label":"业务 API","shape":"process"},
    {"id":"db","label":"业务数据库","shape":"datastore"}
  ],
  "flows": [
    {"from":"user","to":"auth","label":"凭据"},
    {"from":"auth","to":"store","label":"会话写入"},
    {"from":"store","to":"auth","label":"会话读取"},
    {"from":"auth","to":"api","label":"Token"},
    {"from":"api","to":"db","label":"CRUD"},
    {"from":"db","to":"api","label":"结果集"}
  ]
}
```

**模板**（外部实体方框 + 处理圆 + 数据存储开口矩形 + 带标注数据流箭头）：
```html
<div class="diagram data-flow" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --edge-strong:var(--accent-1);
  --node-accent:var(--accent-1); --label-font:var(--font-primary);
  font-family:var(--label-font); width:680px; position:relative;">

  <!-- 行1：外部实体（用户）→ 处理圆（鉴权） -->
  <div style="display:flex; align-items:center; gap:0; padding:8px 24px;">

    <!-- 外部实体：实线方框 -->
    <div style="min-width:96px; min-height:64px; display:flex; align-items:center; justify-content:center;
      padding:10px 14px; box-sizing:border-box;
      background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
      border:2px solid var(--node-border); color:var(--node-fg); font-size:13px; font-weight:700; text-align:center;">
      用户
    </div>

    <!-- 凭据流箭头 -->
    <div style="position:relative; width:120px; height:16px; display:flex; align-items:center;">
      <svg viewBox="0 0 120 16" style="width:120px; height:16px; overflow:visible; display:block;">
        <line x1="0" y1="8" x2="104" y2="8" stroke="var(--edge-strong)" stroke-width="1.5"/>
        <polygon points="102,2 116,8 102,14" fill="var(--edge-strong)"/>
      </svg>
      <span style="position:absolute; left:16px; top:-14px; font-size:11px; font-weight:600; color:var(--node-fg-dim);">凭据</span>
    </div>

    <!-- 处理圆：鉴权服务（focus，SVG circle + HTML 叠加文字） -->
    <div style="position:relative; width:96px; height:96px; display:flex; align-items:center; justify-content:center;">
      <svg viewBox="0 0 96 96" style="width:96px; height:96px; overflow:visible; display:block; position:absolute; top:0; left:0;">
        <circle cx="48" cy="48" r="44" fill="var(--node-bg-from)"
          stroke="var(--node-accent)" stroke-width="1.5"/>
      </svg>
      <span style="position:relative; z-index:1; font-size:12px; font-weight:700; color:var(--node-fg); text-align:center; line-height:1.3;">鉴权<br>服务</span>
    </div>

    <!-- Token 流箭头 -->
    <div style="position:relative; width:120px; height:16px; display:flex; align-items:center;">
      <svg viewBox="0 0 120 16" style="width:120px; height:16px; overflow:visible; display:block;">
        <line x1="0" y1="8" x2="104" y2="8" stroke="var(--edge)" stroke-width="1.5"/>
        <polygon points="102,2 116,8 102,14" fill="var(--edge)"/>
      </svg>
      <span style="position:absolute; left:20px; top:-14px; font-size:11px; font-weight:600; color:var(--node-fg-dim);">Token</span>
    </div>

    <!-- 处理圆：业务 API -->
    <div style="position:relative; width:96px; height:96px; display:flex; align-items:center; justify-content:center;">
      <svg viewBox="0 0 96 96" style="width:96px; height:96px; overflow:visible; display:block; position:absolute; top:0; left:0;">
        <circle cx="48" cy="48" r="44" fill="var(--node-bg-from)"
          stroke="var(--node-border)" stroke-width="1.5"/>
      </svg>
      <span style="position:relative; z-index:1; font-size:12px; font-weight:700; color:var(--node-fg); text-align:center; line-height:1.3;">业务<br>API</span>
    </div>
  </div>

  <!-- 行间箭头：鉴权←→会话存储；API←→业务数据库（纵向） -->
  <div style="position:relative; height:56px; width:100%;">
    <svg viewBox="0 0 680 56" style="width:680px; height:56px; overflow:visible; display:block; position:absolute; left:0; top:0;">
      <!-- 鉴权服务中心 x≈288; 会话存储在下方 x≈288 -->
      <!-- 写入 -->
      <line x1="304" y1="0" x2="304" y2="40" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="298,38 304,48 310,38" fill="var(--edge)"/>
      <!-- 读取（略偏左）-->
      <line x1="272" y1="40" x2="272" y2="0" stroke="var(--edge)" stroke-width="1.5" stroke-dasharray="4 3"/>
      <polygon points="266,10 272,0 278,10" fill="var(--edge)"/>

      <!-- 业务 API 中心 x≈584; 数据库在下方 -->
      <line x1="600" y1="0" x2="600" y2="40" stroke="var(--edge)" stroke-width="1.5"/>
      <polygon points="594,38 600,48 606,38" fill="var(--edge)"/>
      <line x1="568" y1="40" x2="568" y2="0" stroke="var(--edge)" stroke-width="1.5" stroke-dasharray="4 3"/>
      <polygon points="562,10 568,0 574,10" fill="var(--edge)"/>
    </svg>
    <span style="position:absolute; left:308px; top:12px; font-size:10px; color:var(--node-fg-dim);">写入</span>
    <span style="position:absolute; left:236px; top:12px; font-size:10px; color:var(--node-fg-dim);">读取</span>
    <span style="position:absolute; left:604px; top:12px; font-size:10px; color:var(--node-fg-dim);">CRUD</span>
    <span style="position:absolute; left:532px; top:12px; font-size:10px; color:var(--node-fg-dim);">结果集</span>
  </div>

  <!-- 行2：数据存储（开口矩形） -->
  <div style="display:flex; align-items:center; padding:0 24px; gap:0;">
    <div style="margin-left:192px;">
      <!-- 数据存储：两条横线 + 中间内容，用 div+SVG 顶底横线模拟开口矩形 -->
      <div style="position:relative; min-width:160px; min-height:48px; box-sizing:border-box; padding:10px 16px;
        display:flex; align-items:center; justify-content:center;">
        <svg viewBox="0 0 160 48" style="position:absolute; top:0; left:0; width:160px; height:48px; display:block;">
          <line x1="0" y1="2"  x2="160" y2="2"  stroke="var(--node-border)" stroke-width="1.5"/>
          <line x1="0" y1="46" x2="160" y2="46" stroke="var(--node-border)" stroke-width="1.5"/>
        </svg>
        <span style="position:relative; z-index:1; font-size:13px; font-weight:700; color:var(--node-fg);">会话存储</span>
      </div>
    </div>

    <div style="flex:1;"></div>

    <div style="margin-right:24px;">
      <!-- 业务数据库：同样开口矩形 -->
      <div style="position:relative; min-width:160px; min-height:48px; box-sizing:border-box; padding:10px 16px;
        display:flex; align-items:center; justify-content:center;">
        <svg viewBox="0 0 160 48" style="position:absolute; top:0; left:0; width:160px; height:48px; display:block;">
          <line x1="0" y1="2"  x2="160" y2="2"  stroke="var(--node-border)" stroke-width="1.5"/>
          <line x1="0" y1="46" x2="160" y2="46" stroke="var(--node-border)" stroke-width="1.5"/>
        </svg>
        <span style="position:relative; z-index:1; font-size:13px; font-weight:700; color:var(--node-fg);">业务数据库</span>
      </div>
    </div>
  </div>
</div>
```
> 复制规律：外部实体 = 加粗边框实心方框（2px border）；处理圆 = SVG `<circle>` + HTML 叠加文字；数据存储 = SVG 顶底两条横线（开口矩形）+ HTML 叠加文字；数据流 = SVG `<line>` + `<polygon>` 箭头 + HTML span 标注；双向流用偏移平行线。

**自检**：三种节点形状（方块/圆/开口矩形）颜色字体全用契约变量；数据流标注是 HTML span；处理圆文字是 HTML 叠加；`min-width`/`min-height`+`box-sizing`。

**管线安全**：无 SVG `<text>`（处理圆、数据存储标签均 HTML 叠加）；箭头 `<polygon>`；无伪元素；无 `mask-image`/`conic-gradient`/`background-clip:text`。

---

### 三相位 Roadmap（phase-band-roadmap）

**何时用**：展示三阶段推进计划（基础期→加速期→复利期），每阶段含目标、里程碑点列表，阶段间插入"结果门"（菱形决策点）。适用于工程交付简报、技术转型 deck、组织变革路径图。`graphite_violet` 首推原语；也可用于任何暗色或浅色风格。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "phase-band-roadmap",
  "phases": [
    {
      "badge": "Phase 1", "name": "Pathfinder", "duration": "Months 1–3",
      "cdot": "var(--emerald)",
      "summary": "One team. Prove the model end-to-end.",
      "scope": "1 team · 1 product · end-to-end",
      "milestones_label": "Prove",
      "milestones": ["Baseline established", "Knowledge base seeded", "Target: 2× team output"]
    },
    {
      "badge": "Phase 2", "name": "Acceleration", "duration": "Months 4–9",
      "cdot": "var(--amber)",
      "summary": "Extend to 3–5 teams. Quality gates live.",
      "scope": "3–5 teams · portfolio-level",
      "milestones_label": "Expand",
      "milestones": ["CoE seeded (3–5 people)", "Scoring engine live", "Two domains operational"]
    },
    {
      "badge": "Phase 3", "name": "Compounding", "duration": "Months 10–12+",
      "cdot": "var(--violet)",
      "summary": "Enterprise-wide. System gets smarter daily.",
      "scope": "Enterprise-wide · self-sustaining",
      "milestones_label": "Own",
      "milestones": ["80%+ adoption", "Self-sustaining ops", "Team runs it independently"]
    }
  ],
  "gates": [
    { "label": "Outcome Gate 1" },
    { "label": "The Inflection Point" }
  ]
}
```

**HTML 模板**：
```html
<div class="phase-roadmap" style="
  --emerald: var(--accent-3);
  --amber: var(--accent-4);
  --violet: var(--accent-1);
  --line: var(--card-border);
  --ink: var(--text-primary);
  --muted: var(--text-secondary);
  --card-bg: var(--card-bg-from);
  --mono: var(--mono-font);
  font-family: var(--body-font, sans-serif);
  display: flex; flex-direction: column; gap: 0; width: 100%;">

  <!-- Phase 1: Foundation -->
  <div class="phase-band" style="
    --cdot: var(--emerald);
    border-left: 4px solid var(--cdot);
    background: var(--card-bg); border: 1px solid var(--line);
    border-left: 4px solid var(--cdot);
    border-radius: 10px; padding: 14px 18px; display: flex; gap: 20px;">
    <div style="flex: 0 0 140px;">
      <div class="phase-badge" style="
        display: inline-flex; align-items: center; padding: 3px 10px;
        border-radius: 999px; border: 1px solid var(--cdot); background: var(--card-bg);
        color: var(--cdot); font-size: 11px; font-weight: 700;
        letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px;">Phase 1</div>
      <div style="font-size: 15px; font-weight: 700; color: var(--cdot); line-height: 1.2; margin-bottom: 3px;">Pathfinder</div>
      <div style="font-family: var(--mono); font-size: 11px; color: var(--muted);">Months 1–3</div>
    </div>
    <div style="flex: 1; border-left: 1px solid var(--line); padding-left: 18px;">
      <p style="font-size: 13px; color: var(--ink); line-height: 1.5; margin-bottom: 8px;">One team. Prove the model end-to-end.</p>
      <div style="
        display: inline-block; padding: 2px 8px; border-radius: 4px;
        border: 1px solid var(--line); font-size: 11px; color: var(--muted);
        font-family: var(--mono); margin-bottom: 10px;">1 team · 1 product · end-to-end</div>
      <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--cdot); margin-bottom: 6px;">Prove</div>
      <div style="display: flex; flex-direction: column; gap: 4px;">
        <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);">
          <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--cdot); flex-shrink: 0;"></div>
          Baseline established
        </div>
        <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);">
          <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--cdot); flex-shrink: 0;"></div>
          Knowledge base seeded
        </div>
        <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);">
          <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--cdot); flex-shrink: 0;"></div>
          Target: 2× team output
        </div>
      </div>
    </div>
  </div>

  <!-- Gate 1 -->
  <div style="display: flex; align-items: center; gap: 10px; padding: 8px 18px;">
    <div style="flex: 1; height: 1px; background: var(--line);"></div>
    <svg viewBox="0 0 16 16" style="width: 16px; height: 16px; flex-shrink: 0; display: block;">
      <polygon points="8,1 15,8 8,15 1,8" fill="var(--violet)" opacity="0.55"/>
    </svg>
    <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); white-space: nowrap;">Outcome Gate 1</div>
    <div style="flex: 1; height: 1px; background: var(--line);"></div>
  </div>

  <!-- Phase 2: Acceleration -->
  <div class="phase-band" style="
    --cdot: var(--amber);
    background: var(--card-bg); border: 1px solid var(--line);
    border-left: 4px solid var(--cdot);
    border-radius: 10px; padding: 14px 18px; display: flex; gap: 20px;">
    <div style="flex: 0 0 140px;">
      <div class="phase-badge" style="
        display: inline-flex; align-items: center; padding: 3px 10px;
        border-radius: 999px; border: 1px solid var(--cdot); background: var(--card-bg);
        color: var(--cdot); font-size: 11px; font-weight: 700;
        letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px;">Phase 2</div>
      <div style="font-size: 15px; font-weight: 700; color: var(--cdot); line-height: 1.2; margin-bottom: 3px;">Acceleration</div>
      <div style="font-family: var(--mono); font-size: 11px; color: var(--muted);">Months 4–9</div>
    </div>
    <div style="flex: 1; border-left: 1px solid var(--line); padding-left: 18px;">
      <p style="font-size: 13px; color: var(--ink); line-height: 1.5; margin-bottom: 8px;">Extend to 3–5 teams. Quality gates live.</p>
      <div style="
        display: inline-block; padding: 2px 8px; border-radius: 4px;
        border: 1px solid var(--line); font-size: 11px; color: var(--muted);
        font-family: var(--mono); margin-bottom: 10px;">3–5 teams · portfolio-level</div>
      <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--cdot); margin-bottom: 6px;">Expand</div>
      <div style="display: flex; flex-direction: column; gap: 4px;">
        <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);">
          <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--cdot); flex-shrink: 0;"></div>
          CoE seeded (3–5 people)
        </div>
        <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);">
          <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--cdot); flex-shrink: 0;"></div>
          Scoring engine live
        </div>
        <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);">
          <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--cdot); flex-shrink: 0;"></div>
          Two domains operational
        </div>
      </div>
    </div>
  </div>

  <!-- Gate 2 -->
  <div style="display: flex; align-items: center; gap: 10px; padding: 8px 18px;">
    <div style="flex: 1; height: 1px; background: var(--line);"></div>
    <svg viewBox="0 0 16 16" style="width: 16px; height: 16px; flex-shrink: 0; display: block;">
      <polygon points="8,1 15,8 8,15 1,8" fill="var(--violet)" opacity="0.55"/>
    </svg>
    <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); white-space: nowrap;">The Inflection Point</div>
    <div style="flex: 1; height: 1px; background: var(--line);"></div>
  </div>

  <!-- Phase 3: Compounding -->
  <div class="phase-band" style="
    --cdot: var(--violet);
    background: var(--card-bg); border: 1px solid var(--line);
    border-left: 4px solid var(--cdot);
    border-radius: 10px; padding: 14px 18px; display: flex; gap: 20px;">
    <div style="flex: 0 0 140px;">
      <div class="phase-badge" style="
        display: inline-flex; align-items: center; padding: 3px 10px;
        border-radius: 999px; border: 1px solid var(--cdot); background: var(--card-bg);
        color: var(--cdot); font-size: 11px; font-weight: 700;
        letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px;">Phase 3</div>
      <div style="font-size: 15px; font-weight: 700; color: var(--cdot); line-height: 1.2; margin-bottom: 3px;">Compounding</div>
      <div style="font-family: var(--mono); font-size: 11px; color: var(--muted);">Months 10–12+</div>
    </div>
    <div style="flex: 1; border-left: 1px solid var(--line); padding-left: 18px;">
      <p style="font-size: 13px; color: var(--ink); line-height: 1.5; margin-bottom: 8px;">Enterprise-wide. System gets smarter daily.</p>
      <div style="
        display: inline-block; padding: 2px 8px; border-radius: 4px;
        border: 1px solid var(--line); font-size: 11px; color: var(--muted);
        font-family: var(--mono); margin-bottom: 10px;">Enterprise-wide · self-sustaining</div>
      <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--cdot); margin-bottom: 6px;">Own</div>
      <div style="display: flex; flex-direction: column; gap: 4px;">
        <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);">
          <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--cdot); flex-shrink: 0;"></div>
          80%+ adoption
        </div>
        <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);">
          <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--cdot); flex-shrink: 0;"></div>
          Self-sustaining ops
        </div>
        <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);">
          <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--cdot); flex-shrink: 0;"></div>
          Team runs it independently
        </div>
      </div>
    </div>
  </div>

</div>
```

**自检**：三相位带 `border-left:4px solid var(--cdot)` 各取相位色；菱形门 `<polygon>` 用 `var(--violet)` 非硬码；徽章 `border:1px solid var(--cdot)` + `background:var(--card-bg)` 纯 CSS 变量（无 rgba）；里程碑点 6px 圆 `background: var(--cdot)`；CSS 自定义属性声明无十六进制回退值；无 `<text>` 节点。

**管线安全**：菱形门 SVG `<polygon>`（无 `<text>`，无 `<marker>`）；无 `mask-image`/`conic-gradient`/`background-clip:text`/`mix-blend-mode`/伪元素装饰内容；所有文字均为 HTML 元素。
