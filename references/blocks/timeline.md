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
