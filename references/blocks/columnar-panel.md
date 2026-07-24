# columnar-panel — 统一列面板（内部竖线分隔 · 无独立卡框）

> 适用数据类型：parallel_items / status_columns / phase_overview / scoping_matrix / feature_comparison / multi-track-content。
> 核心设计哲学：**用内部竖线替代独立卡框**——N 列内容共享一个外框容器，列间只用 `border-right:1px solid var(--card-border)` 分隔，绝不给每列套独立的 `border + border-radius`。外框感知、内容轻盈，是并列信息最专业的呈现方式。
> 推荐 card_style：`transparent`（外框交给容器本身）。推荐布局：`three-column`（3 列）/ `symmetric`（2 列）。
> 管线：真实 `<div>`；无 SVG `<text>`；无 `mask-image`/`conic-gradient`/`background-image:url()`；颜色走契约变量。

**禁止反模式（anti-pattern）**：三列并列内容**绝对禁止**给每一列套独立的 `border + border-radius + box-shadow`——那是"三个盒子叠在一起"，不是设计，是 Word 文档。唯一允许的独立卡框是单张 `accent` 或 `elevated` 强调卡，且一页最多 1 个。

---

## 主题契约（根容器局部变量）

```css
--focus: var(--accent-1);
--secondary: var(--accent-2);
--paper: var(--card-bg-from);
--ink: var(--text-primary);
--dim: var(--text-secondary);
--rule: var(--card-border);
--sans: var(--font-primary);
```

---

## A. 基础三列面板（无顶栏）

**何时用**：三类并列信息（三个阶段 / 三大支柱 / In-scope vs. TBD vs. Next），内容地位平等、无需大标题统帅。

**数据格式**：
```json
{
  "card_type": "list",
  "layout_hint": "three-column",
  "block_refs": ["columnar-panel"],
  "brief_kind": "columnar_panel",
  "columns": [
    {
      "header": "What's In",
      "header_accent": "primary",
      "badge": {"text": "Live & under testing", "tone": "green"},
      "sections": [
        {"label": "Three modes", "items": ["Ask — quick answers", "Research — multi-source", "Generate — structured outputs"]},
        {"label": "Architecture", "items": ["Amazon Bedrock KB", "Next.js frontend"]}
      ]
    },
    {
      "header": "Under Clarification",
      "header_accent": "secondary",
      "badge": {"text": "Being defined", "tone": "amber"},
      "sections": [
        {"label": "Deployment", "items": ["Target environment TBD"]},
        {"label": "Connectors", "items": ["Web search", "SharePoint"]}
      ]
    },
    {
      "header": "What's Next",
      "header_accent": "muted",
      "badge": {"text": "Future dev", "tone": "gray"},
      "sections": [
        {"label": "Security", "items": ["Monitoring & alerting", "Audit logging"]},
        {"label": "Extended access", "items": ["Post-PoC user access"]}
      ]
    }
  ]
}
```

**HTML 模板**（三列 · 内部竖线分隔 · 无独立卡框）：
```html
<div style="
  --focus:var(--accent-1); --secondary:var(--accent-2);
  --paper:var(--card-bg-from); --ink:var(--text-primary);
  --dim:var(--text-secondary); --rule:var(--card-border); --sans:var(--font-primary);
  display:grid; grid-template-columns:1fr 1fr 1fr;
  border:1px solid var(--rule); border-radius:10px; overflow:hidden;
  background:var(--paper); font-family:var(--sans);">

  <!-- Column 1 (primary accent) -->
  <div style="padding:18px 20px; border-right:1px solid var(--rule);">
    <!-- Col header: uppercase label + 2px accent underline -->
    <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
      color:var(--focus); border-bottom:2px solid var(--focus); padding-bottom:7px; margin-bottom:12px;">
      What's In</div>
    <!-- Optional status badge -->
    <span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
      border-radius:20px; margin-bottom:11px; background:rgba(34,197,94,0.12); color:#166534;">
      Live &amp; under testing</span>
    <!-- Section label -->
    <div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.07em;
      color:var(--dim); margin:12px 0 5px;">Three modes</div>
    <!-- Bullet items -->
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--focus);"></span>
      <span><b>Ask</b> — quick source-grounded answers</span></div>
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--focus);"></span>
      <span><b>Research</b> — multi-source synthesis</span></div>
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--focus);"></span>
      <span><b>Generate</b> — structured outputs</span></div>
    <div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.07em;
      color:var(--dim); margin:12px 0 5px;">Architecture</div>
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--focus);"></span>
      <span>Amazon Bedrock Knowledge Base</span></div>
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--focus);"></span>
      <span>Next.js frontend + API routes</span></div>
  </div>

  <!-- Column 2 (secondary accent — border-right only, no full box) -->
  <div style="padding:18px 20px; border-right:1px solid var(--rule);">
    <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
      color:var(--secondary); border-bottom:2px solid var(--secondary); padding-bottom:7px; margin-bottom:12px;">
      Under Clarification</div>
    <span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
      border-radius:20px; margin-bottom:11px; background:rgba(245,158,11,0.12); color:#92400e;">
      Being defined</span>
    <div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.07em;
      color:var(--dim); margin:12px 0 5px;">Deployment</div>
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--secondary);"></span>
      <span>Target environment — TIAA vs. external</span></div>
    <div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.07em;
      color:var(--dim); margin:12px 0 5px;">Connectors</div>
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--secondary);"></span>
      <span>Web search — supplemental knowledge</span></div>
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--secondary);"></span>
      <span>SharePoint — auto-sync document libraries</span></div>
  </div>

  <!-- Column 3 (muted/tertiary — no border-right, it's the last column) -->
  <div style="padding:18px 20px;">
    <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
      color:var(--dim); border-bottom:2px solid var(--dim); padding-bottom:7px; margin-bottom:12px; opacity:0.7;">
      What's Next</div>
    <span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
      border-radius:20px; margin-bottom:11px; background:rgba(0,0,0,0.05); color:var(--dim);">
      Future dev</span>
    <div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.07em;
      color:var(--dim); margin:12px 0 5px;">Security &amp; ops</div>
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--dim); opacity:0.5;"></span>
      <span>Monitoring, alerting &amp; runbook</span></div>
    <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
      <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--dim); opacity:0.5;"></span>
      <span>Audit logging &amp; incident response</span></div>
  </div>
</div>
```

**自检**：外容器只有一层 `border + border-radius`；列间只有 `border-right:1px solid var(--rule)`，末列无右边框；列头走 `border-bottom:2px solid` + 列专属色；圆点走真实 `<span>`（非伪元素）；颜色全走契约变量。

**管线安全**：真实 `<div>` grid；无伪元素；无 SVG `<text>`；无 `mask-image`/`conic-gradient`/`background-image:url()`。

---

## B. 带顶栏的列面板（header-bar + columns，一体式）

**何时用**：内容需要一个统帅性标题时——顶部一条深色 / accent 色实底横幅（含 eyebrow + 主标题 + 副标题），直接贴合在列面板顶部，圆角只在外壳四角，顶栏与列面板之间**无缝隙**。整体读作一个独立的版块单元，而非"标题 + N 列卡片"两个独立元素。

**数据格式**：
```json
{
  "card_type": "list",
  "block_refs": ["columnar-panel"],
  "brief_kind": "columnar_panel_with_header",
  "header": {
    "eyebrow": "AI Products · Solutioning Session",
    "title": "Research Agent",
    "subtitle": "PoC scope overview — July 2026"
  },
  "columns": [ ... ]
}
```

**HTML 模板**（顶栏 + 三列，一体容器）：
```html
<div style="
  --focus:var(--accent-1); --secondary:var(--accent-2);
  --paper:var(--card-bg-from); --ink:var(--text-primary);
  --dim:var(--text-secondary); --rule:var(--card-border); --sans:var(--font-primary);
  border:1px solid var(--focus); border-radius:12px; overflow:hidden;
  font-family:var(--sans);">

  <!-- Header bar: solid accent background, no bottom border (columns are flush below) -->
  <div style="background:var(--focus); padding:20px 28px 18px;">
    <div style="font-size:10px; letter-spacing:0.1em; text-transform:uppercase; font-weight:600;
      color:#fff; opacity:0.65; margin-bottom:3px;">AI Products &middot; Solutioning Session</div>
    <h2 style="font-size:22px; font-weight:700; color:#fff; margin:0 0 4px; line-height:1.2;">
      Research Agent</h2>
    <p style="font-size:12px; color:#fff; opacity:0.75; margin:0; line-height:1.5;">
      PoC scope overview — July 2026</p>
  </div>

  <!-- Column body: white/paper background, columns separated by border-right only -->
  <div style="display:grid; grid-template-columns:1fr 1fr 1fr; background:var(--paper);">

    <!-- Col 1 -->
    <div style="padding:18px 20px; border-right:1px solid var(--rule);">
      <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
        color:var(--focus); border-bottom:2px solid var(--focus); padding-bottom:7px; margin-bottom:12px;">
        What's In</div>
      <!-- badge -->
      <span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
        border-radius:20px; margin-bottom:11px; background:rgba(34,197,94,0.12); color:#166534;">
        Live &amp; under testing</span>
      <!-- section label -->
      <div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.07em;
        color:var(--dim); margin:12px 0 5px;">Three modes</div>
      <!-- bullets -->
      <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
        <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--focus);"></span>
        <span><b>Ask</b> — quick source-grounded answers</span></div>
      <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
        <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--focus);"></span>
        <span><b>Research</b> — multi-source synthesis</span></div>
    </div>

    <!-- Col 2 -->
    <div style="padding:18px 20px; border-right:1px solid var(--rule);">
      <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
        color:var(--secondary); border-bottom:2px solid var(--secondary); padding-bottom:7px; margin-bottom:12px;">
        Under Clarification</div>
      <span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
        border-radius:20px; margin-bottom:11px; background:rgba(245,158,11,0.12); color:#92400e;">
        Being defined</span>
      <div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.07em;
        color:var(--dim); margin:12px 0 5px;">Connectors</div>
      <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
        <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--secondary);"></span>
        <span>Web search — supplemental knowledge</span></div>
      <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
        <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--secondary);"></span>
        <span>SharePoint — auto-sync libraries</span></div>
    </div>

    <!-- Col 3 -->
    <div style="padding:18px 20px;">
      <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
        color:var(--dim); border-bottom:2px solid var(--dim); padding-bottom:7px; margin-bottom:12px; opacity:0.7;">
        What's Next</div>
      <span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
        border-radius:20px; margin-bottom:11px; background:rgba(0,0,0,0.05); color:var(--dim);">
        Future dev</span>
      <div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.07em;
        color:var(--dim); margin:12px 0 5px;">Security &amp; ops</div>
      <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
        <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--dim); opacity:0.5;"></span>
        <span>Monitoring &amp; alerting</span></div>
      <div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
        <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--dim); opacity:0.5;"></span>
        <span>Audit logging &amp; incident response</span></div>
    </div>
  </div>
</div>
```

**自检**：外壳一层 `border:1px solid var(--focus)` + `border-radius:12px; overflow:hidden`；顶栏和列 body 无缝隙（overflow:hidden 裁切）；列 body 用 `display:grid` 非 flex 确保等高；列头走 `border-bottom:2px solid` 专属色；末列无 `border-right`；颜色全走契约变量，顶栏用 `#fff` / `rgba(255,255,255,*)` 覆盖文字色（唯一允许的白色硬编码，因为它叠在实色 accent 背景上）。

**管线安全**：真实 `<div>` grid；无伪元素；无 SVG `<text>`；无 `mask-image`/`conic-gradient`。

---

## C. 两列面板（symmetric · 内部竖线）

**何时用**：两类并列内容（before/after · 现状/目标 · 两条服务线 · 两阶段对比），但**无强立场**——有立场的 A vs B 对比仍用 `comparison` 块。

**HTML 模板**（双列 · 单竖线分隔）：
```html
<div style="
  --focus:var(--accent-1); --secondary:var(--accent-2);
  --paper:var(--card-bg-from); --ink:var(--text-primary);
  --dim:var(--text-secondary); --rule:var(--card-border); --sans:var(--font-primary);
  display:grid; grid-template-columns:1fr 1fr;
  border:1px solid var(--rule); border-radius:10px; overflow:hidden;
  background:var(--paper); font-family:var(--sans);">

  <div style="padding:20px 24px; border-right:1px solid var(--rule);">
    <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
      color:var(--focus); border-bottom:2px solid var(--focus); padding-bottom:7px; margin-bottom:14px;">
      Column A</div>
    <!-- content -->
  </div>

  <div style="padding:20px 24px;">
    <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
      color:var(--secondary); border-bottom:2px solid var(--secondary); padding-bottom:7px; margin-bottom:14px;">
      Column B</div>
    <!-- content -->
  </div>
</div>
```

---

## D. 列内微原语（可在 A/B/C 内自由组合）

### D1. 列头（col-header）

```html
<!-- Primary accent col-header -->
<div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
  color:var(--focus); border-bottom:2px solid var(--focus); padding-bottom:7px; margin-bottom:12px;">
  Column Title</div>

<!-- Secondary col-header -->
<div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
  color:var(--secondary); border-bottom:2px solid var(--secondary); padding-bottom:7px; margin-bottom:12px;">
  Column Title</div>

<!-- Muted / de-emphasized col-header (e.g., "future" or "excluded" column) -->
<div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
  color:var(--dim); border-bottom:2px solid var(--dim); padding-bottom:7px; margin-bottom:12px; opacity:0.65;">
  Column Title</div>
```

### D2. 섹션 라벨 (section-label)

```html
<div style="font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.07em;
  color:var(--dim); margin:12px 0 5px;">Section Label</div>
```

### D3. 圆点项目符号（bullet-dot）

```html
<!-- 色跟随列主色 -->
<div style="display:flex; align-items:flex-start; gap:7px; font-size:12.5px; color:var(--ink); line-height:1.5; margin-bottom:5px;">
  <span style="width:6px; height:6px; border-radius:50%; margin-top:5px; flex-shrink:0; background:var(--focus);"></span>
  <span>Item text here — <b>bold for emphasis</b></span></div>
```

### D4. 状态徽章（status badge）

```html
<!-- green: live / confirmed -->
<span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
  border-radius:20px; background:rgba(34,197,94,0.12); color:#166534;">Live &amp; under testing</span>

<!-- amber: in progress / TBD -->
<span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
  border-radius:20px; background:rgba(245,158,11,0.12); color:#92400e;">Being defined</span>

<!-- gray: future / deferred -->
<span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
  border-radius:20px; background:rgba(0,0,0,0.06); color:var(--dim);">Future dev</span>

<!-- accent: active / selected -->
<span style="display:inline-block; font-size:10px; font-weight:600; padding:2px 9px;
  border-radius:20px; background:var(--focus); color:#fff;">Active</span>
```

**管线安全（全组件通用）**：
- 圆点：真实 `<span>`（非 `::before`）
- 徽章绿/琥珀色：语义信号色，允许 rgba 形式硬编码（与 worksheet status-block 同性质）
- 颜色优先 `var(--*)` 契约变量
- 无 SVG `<text>`；无 `mask-image`/`conic-gradient`/`background-image:url()`
