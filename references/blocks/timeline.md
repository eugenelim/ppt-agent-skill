# timeline（时间线块）-- 时间的河流

> 适用数据类型：timelines / journey_map / gantt_data。横向/纵向轴线 + 节点。
> 前置：本块复用 `blocks/diagram.md` 的**主题契约**（颜色/字体只用契约局部变量）与共享基元。需要"任务条 + 时间轴"的排期/路线图，改用 diagram family 的 `gantt`（`block_refs: diagram-project`）。
> 推荐 card_style：transparent（自带轴线骨架）。推荐布局：l-shape / waterfall。4-8 节点为宜，超过 8 拆页。
> 管线：遵守 pipeline-compat.md —— 轴线/连线用真实 `<div>` 或 SVG `<line>`，箭头用 SVG `<polygon>`，文字一律 HTML（禁 `<text>`）。

---

### 横向时间线 (timeline)

**何时用**：4-8 个按时间排列的事件，强调"进程的推动力"；节点交替上下打破单调。需要带工期的甘特/路线图时改用 `gantt`。

**数据格式**：
```json
{
  "card_type": "timeline", "orientation": "horizontal",
  "nodes": [
    {"time": "2022", "title": "立项", "description": "简述（30字内）", "highlight": false},
    {"time": "2024", "title": "量产", "description": "里程碑", "highlight": true}
  ]
}
```

**模板**（轴线 + 节点 + 交替标注；highlight 实心放大）：
```html
<div class="diagram timeline-h" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to); --node-border:var(--card-border);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary); --edge:var(--card-border);
  --node-accent:var(--accent-1); font-family:var(--font-primary); position:relative; width:760px; padding:24px 0;">

  <!-- 主轴线：真实 div -->
  <div style="position:absolute; left:0; right:0; top:50%; height:2px; background:var(--edge);"></div>

  <div style="position:relative; display:flex; justify-content:space-between; align-items:center;">
    <!-- 普通节点：描边小圆 + 上方标注 -->
    <div style="display:flex; flex-direction:column; align-items:center; gap:6px; width:120px;">
      <span style="font-size:13px; font-weight:700; color:var(--node-fg);">立项</span>
      <span style="font-size:11px; color:var(--node-fg-dim); text-align:center;">简述</span>
      <span style="width:12px; height:12px; border-radius:50%; background:var(--node-bg-from);
        border:2px solid var(--node-border); box-sizing:border-box;"></span>
      <span style="font-size:12px; color:var(--node-fg-dim);">2022</span>
    </div>

    <!-- highlight 节点：accent 实心大圆 -->
    <div style="display:flex; flex-direction:column; align-items:center; gap:6px; width:120px;">
      <span style="font-size:15px; font-weight:800; color:var(--node-fg);">量产</span>
      <span style="font-size:11px; color:var(--node-fg-dim); text-align:center;">里程碑</span>
      <span style="width:18px; height:18px; border-radius:50%; background:var(--node-accent);
        box-shadow:0 0 0 4px var(--card-bg-from), 0 0 0 5px var(--node-accent);"></span>
      <span style="font-size:13px; font-weight:700; color:var(--node-accent);">2024</span>
    </div>
  </div>
</div>
```
> 灵动：节点可交替上/下排（一组 `flex-direction:column`、一组 `column-reverse`）制造呼吸起伏；轴线末端可加一段渐隐 div 暗示"未来延伸"。

**自检**：highlight 用 `--node-accent` 实心 + 更大尺寸；普通节点描边 + 小尺寸；颜色全用契约变量；时间/标题/描述都是 HTML。

**管线安全**：轴线/节点是真实 `<div>`；无 SVG `<text>`；无伪元素装饰；无 `mask-image`/`conic-gradient`。

---

### 纵向时间线 (timeline-vertical)

**何时用**：事件较多或描述较长时；左侧时间、右侧描述，纵向轴线串联，制造"时间景深"。

**数据格式**：
```json
{
  "card_type": "timeline", "orientation": "vertical",
  "nodes": [
    {"time": "Q1", "title": "调研", "description": "用户访谈与竞品分析", "highlight": false},
    {"time": "Q3", "title": "发布", "description": "首个公开版本上线", "highlight": true}
  ]
}
```

**模板**（左时间 + 轴线节点 + 右描述）：
```html
<div class="diagram timeline-v" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to); --node-border:var(--card-border);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary); --edge:var(--card-border);
  --node-accent:var(--accent-1); font-family:var(--font-primary); width:480px;">

  <div style="display:grid; grid-template-columns:56px 24px 1fr; align-items:start; gap:0 12px;">
    <!-- 行 1 -->
    <span style="font-size:13px; font-weight:700; color:var(--node-fg-dim); text-align:right; padding-top:1px;">Q1</span>
    <div style="display:flex; flex-direction:column; align-items:center;">
      <span style="width:12px; height:12px; border-radius:50%; background:var(--node-bg-from);
        border:2px solid var(--node-border); box-sizing:border-box;"></span>
      <span style="width:2px; flex:1; min-height:40px; background:var(--edge);"></span>
    </div>
    <div style="padding-bottom:20px;">
      <div style="font-size:14px; font-weight:700; color:var(--node-fg);">调研</div>
      <div style="font-size:12px; color:var(--node-fg-dim); line-height:1.6;">用户访谈与竞品分析</div>
    </div>

    <!-- 行 2 · highlight -->
    <span style="font-size:14px; font-weight:800; color:var(--node-accent); text-align:right; padding-top:1px;">Q3</span>
    <div style="display:flex; flex-direction:column; align-items:center;">
      <span style="width:16px; height:16px; border-radius:50%; background:var(--node-accent);
        box-shadow:0 0 0 3px var(--card-bg-from);"></span>
    </div>
    <div>
      <div style="font-size:15px; font-weight:800; color:var(--node-fg);">发布</div>
      <div style="font-size:12px; color:var(--node-fg-dim); line-height:1.6;">首个公开版本上线</div>
    </div>
  </div>
</div>
```
> 灵动：越近的时间标签 opacity 越高（时间景深）；重要事件给更大的右侧描述空间。

**自检**：轴线连续（节点下接 `flex:1` 竖线段）；highlight 放大实心 accent；时间/标题/描述全 HTML；颜色用契约变量。

**管线安全**：轴线/连线/节点全是真实 `<div>`；无 SVG `<text>`；无伪元素；无 `mask-image`/`conic-gradient`。

---

### 相位参与时间线 (phase-engagement-timeline)

**何时用**：以文本叙事方式展示 3–4 个参与/项目阶段——每阶段是一个彩色左边框面板（非甘特网格），含阶段标签、时间跨度、2–4 个关键交付物要点；相位间插入菱形里程碑节点和连线。与 `gantt-engagement`（格子排期图）的区别：本配方是叙事性"做什么"，gantt 是时间性"何时做"。

**数据格式**：
```json
{
  "card_type": "timeline", "orientation": "phase",
  "phases": [
    {
      "badge": "Phase 1", "name": "Discovery",  "duration": "Weeks 1–2",
      "deliverables": ["Stakeholder interviews complete", "Pain points mapped", "Synthesis themes drafted"]
    },
    {
      "badge": "Phase 2", "name": "Design",     "duration": "Weeks 3–4",
      "deliverables": ["Solution concepts defined", "Prioritisation criteria agreed", "Roadmap drafted"]
    },
    {
      "badge": "Phase 3", "name": "Readout",    "duration": "Week 5",
      "deliverables": ["Findings deck delivered", "Next-phase questions framed", "Handoff complete"]
    }
  ]
}
```

**模板**（彩色左边框相位面板 + 菱形里程碑节点连线 · 全走契约变量）：
```html
<div class="diagram phase-engagement-timeline" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-fg:var(--text-primary);
  --node-fg-dim:var(--text-secondary); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary); --mono:var(--font-mono);
  font-family:var(--label-font); display:flex; flex-direction:column; gap:0; width:100%;">

  <!-- Phase 1: Discovery -->
  <div style="display:flex; align-items:stretch; gap:0;">
    <!-- Connector column: milestone diamond + vertical line -->
    <div style="display:flex; flex-direction:column; align-items:center; width:32px; flex-shrink:0; padding-top:14px;">
      <svg viewBox="0 0 16 16" style="width:14px; height:14px; display:block; flex-shrink:0; overflow:visible;">
        <polygon points="7,1 13,7 7,13 1,7" fill="var(--node-accent)"/>
      </svg>
      <div style="width:2px; flex:1; min-height:40px; background:var(--node-border); margin-top:4px;"></div>
    </div>
    <!-- Phase panel -->
    <div style="flex:1; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-left:4px solid var(--node-accent); border-radius:8px; padding:13px 16px; margin-bottom:6px;">
      <div style="display:flex; align-items:baseline; gap:10px; margin-bottom:8px;">
        <span style="font-size:9px; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; padding:2px 8px; border-radius:999px; border:1px solid var(--node-accent); color:var(--node-accent);">Phase 1</span>
        <span style="font-size:15px; font-weight:800; color:var(--node-fg); line-height:1.1;">Discovery</span>
        <span style="font-family:var(--mono); font-size:11px; color:var(--node-fg-dim); margin-left:auto;">Weeks 1–2</span>
      </div>
      <div style="display:flex; flex-direction:column; gap:5px;">
        <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--node-fg);">
          <span style="width:5px; height:5px; border-radius:50%; background:var(--node-accent); flex-shrink:0;"></span>Stakeholder interviews complete</div>
        <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--node-fg);">
          <span style="width:5px; height:5px; border-radius:50%; background:var(--node-accent); flex-shrink:0;"></span>Pain points mapped</div>
        <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--node-fg);">
          <span style="width:5px; height:5px; border-radius:50%; background:var(--node-accent); flex-shrink:0;"></span>Synthesis themes drafted</div>
      </div>
    </div>
  </div>

  <!-- Phase 2: Design -->
  <div style="display:flex; align-items:stretch; gap:0;">
    <div style="display:flex; flex-direction:column; align-items:center; width:32px; flex-shrink:0; padding-top:14px;">
      <svg viewBox="0 0 16 16" style="width:14px; height:14px; display:block; flex-shrink:0; overflow:visible;">
        <polygon points="7,1 13,7 7,13 1,7" fill="var(--node-accent-2)"/>
      </svg>
      <div style="width:2px; flex:1; min-height:40px; background:var(--node-border); margin-top:4px;"></div>
    </div>
    <div style="flex:1; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-left:4px solid var(--node-accent-2); border-radius:8px; padding:13px 16px; margin-bottom:6px;">
      <div style="display:flex; align-items:baseline; gap:10px; margin-bottom:8px;">
        <span style="font-size:9px; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; padding:2px 8px; border-radius:999px; border:1px solid var(--node-accent-2); color:var(--node-accent-2);">Phase 2</span>
        <span style="font-size:15px; font-weight:800; color:var(--node-fg); line-height:1.1;">Design</span>
        <span style="font-family:var(--mono); font-size:11px; color:var(--node-fg-dim); margin-left:auto;">Weeks 3–4</span>
      </div>
      <div style="display:flex; flex-direction:column; gap:5px;">
        <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--node-fg);">
          <span style="width:5px; height:5px; border-radius:50%; background:var(--node-accent-2); flex-shrink:0;"></span>Solution concepts defined</div>
        <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--node-fg);">
          <span style="width:5px; height:5px; border-radius:50%; background:var(--node-accent-2); flex-shrink:0;"></span>Prioritisation criteria agreed</div>
        <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--node-fg);">
          <span style="width:5px; height:5px; border-radius:50%; background:var(--node-accent-2); flex-shrink:0;"></span>Roadmap drafted</div>
      </div>
    </div>
  </div>

  <!-- Phase 3: Readout (no trailing connector line) -->
  <div style="display:flex; align-items:stretch; gap:0;">
    <div style="display:flex; flex-direction:column; align-items:center; width:32px; flex-shrink:0; padding-top:14px;">
      <svg viewBox="0 0 16 16" style="width:14px; height:14px; display:block; flex-shrink:0; overflow:visible;">
        <polygon points="7,1 13,7 7,13 1,7" fill="var(--node-fg-dim)"/>
      </svg>
    </div>
    <div style="flex:1; background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-left:4px solid var(--node-fg-dim); border-radius:8px; padding:13px 16px;">
      <div style="display:flex; align-items:baseline; gap:10px; margin-bottom:8px;">
        <span style="font-size:9px; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; padding:2px 8px; border-radius:999px; border:1px solid var(--node-border); color:var(--node-fg-dim);">Phase 3</span>
        <span style="font-size:15px; font-weight:800; color:var(--node-fg); line-height:1.1;">Readout</span>
        <span style="font-family:var(--mono); font-size:11px; color:var(--node-fg-dim); margin-left:auto;">Week 5</span>
      </div>
      <div style="display:flex; flex-direction:column; gap:5px;">
        <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--node-fg);">
          <span style="width:5px; height:5px; border-radius:50%; background:var(--node-fg-dim); flex-shrink:0;"></span>Findings deck delivered</div>
        <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--node-fg);">
          <span style="width:5px; height:5px; border-radius:50%; background:var(--node-fg-dim); flex-shrink:0;"></span>Next-phase questions framed</div>
        <div style="display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--node-fg);">
          <span style="width:5px; height:5px; border-radius:50%; background:var(--node-fg-dim); flex-shrink:0;"></span>Handoff complete</div>
      </div>
    </div>
  </div>

</div>
```
> 复制规律：每相位 = 连接器列（SVG `<polygon>` 菱形 + 竖线 `<div>`）+ 内容面板（左边框 `4px var(--node-accent/accent-2/fg-dim)` + 卡体）；最后一相位省略竖线尾巴；要点圆点是真实 `<span>` 非伪元素。

**自检**：相位徽章 `border:1px solid var(--node-accent/accent-2)` + 描边文字（非实心底）；菱形节点走相位色 `<polygon>`；左边框随相位色；连接竖线走 `--node-border`；颜色全走契约变量（无 rgba/hex）。

**管线安全**：菱形 SVG `<polygon>`（无 `<text>`）；竖线/圆点是真实 `<div>`/`<span>`；无伪元素；无 `mask-image`/`conic-gradient`。
