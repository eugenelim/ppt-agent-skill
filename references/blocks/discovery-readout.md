# discovery-readout 原语（摘要面板 / 洞察卡 / 发现追踪 / 优先级矩阵 / AI 成熟度 / 方法论三栏）-- 咨询发现汇报

> 适用数据类型：dual_callout / metrics_scoreboard / stage_insight_card / synthesis_theme / anchoring_questions / methodology_columns / ai_maturity_taxonomy / opportunity_badge_strip / coverage_heatmap / findings_tracker / prioritization_scorecard / impact_effort_chart。一整套"咨询发现汇报 deck"原语——从"我们做了什么 / 我们发现了什么"到"接下来的问题"。
> 灵感基准：高端咨询发现汇报 deck——证据优先、假设驱动、开放式下一阶段问题、非处方式语气。天生适配任何 `dark_professional` 或 `light_premium` 风格，全部绑定 deck 变量，换风格随 `:root` 改色。
> 加载：非独立 `card_type`——在 `data` / `list` / `timeline` / `text` 卡上以 `resources.block_refs:["discovery-readout"]` 按需注入正文（与 advisory-brief / worksheet 同机制）。
> 推荐 card_style：section / summary 型用 transparent（组件自带结构骨架）；单独 callout 用 default（含卡框）。
> 管线：遵守 pipeline-compat.md —— 一律真实 `<div>` / `<table>` / SVG `<path>`/`<line>`/`<circle>`/`<polygon>`（禁 SVG `<text>`，标注用 HTML 叠加），禁 `mask-image` / `conic-gradient` / `background-image:url()` / `background-clip:text` / `mix-blend-mode`；颜色只用契约变量（信号色见下方碳out）。

**主题契约（根容器局部变量，映射 deck `:root`）**：每个配方根容器内联声明这一组。
```
--focus:var(--accent-1);          /* 主焦点信号 */
--secondary:var(--accent-2);      /* 次要信号色（implication / so-what） */
--paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
--ink:var(--text-primary); --dim:var(--text-secondary);
--rule:var(--card-border);
--sans:var(--font-primary); --mono:var(--font-mono);
```
**信号色碳out**：
- `findings-tracker` severity badge 用两枚语义信号色——高 `--sev-hi:#ef4444`、中 `--sev-med:#b35900` / `--sev-med-soft:#fef3e6`。这是**唯一允许硬编码 hex 的例外**（与图表趋势色 `#ef4444` 及 worksheet warn 同性质），在配方根容器声明为局部变量，可被 deck `:root` 同名变量覆盖。
- `prioritization-scorecard` 评分色——高分 `--heat-ok:#1f7a3a` / `--heat-ok-soft:#e9f5ed`、低分 `--heat-lo:#ef4444`，中分走契约变量。

---

## A. 摘要 & 证据

### 双 callout 摘要面板 (dual-callout-panel)

**何时用**：执行摘要页的核心修辞单元——左侧面板（主色边框）承载"我们发现了什么 / 观察"，右侧面板（次色边框）承载"所以呢 / 战略含义"。适合发现汇报执行摘要、阶段总结页。可 60/40 或 50/50 分栏。

**数据格式**：
```json
{
  "card_type": "text", "block_refs": ["discovery-readout"], "brief_kind": "dual_callout",
  "split": "60/40",
  "left": {
    "label": "What we found",
    "items": [
      "Requirements inconsistencies create compounding rework across build and test.",
      "Manual coordination consumes 30–40% of planning capacity.",
      "Quality signals surface too late in the cycle to prevent rework."
    ]
  },
  "right": {
    "label": "So what",
    "text": "The evidence points to three addressable leverage points. The question is not whether to act, but where to start — and what is already within reach in the current toolchain."
  }
}
```

**HTML 模板**（60/40 双色左边框面板）：
```html
<div style="
  --focus:var(--accent-1); --secondary:var(--accent-2);
  --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --ink:var(--text-primary); --dim:var(--text-secondary); --rule:var(--card-border);
  --sans:var(--font-primary);
  display:grid; grid-template-columns:3fr 2fr; gap:14px; font-family:var(--sans);">
  <!-- Left: observation (primary accent border) -->
  <div style="background:var(--paper); border:1px solid var(--rule); border-left:4px solid var(--focus); border-radius:10px; padding:16px 18px;">
    <div style="font-size:10px; letter-spacing:0.16em; text-transform:uppercase; font-weight:700; color:var(--focus); margin-bottom:10px;">What we found</div>
    <div style="display:flex; flex-direction:column; gap:7px;">
      <div style="position:relative; padding-left:13px; font-size:12.5px; line-height:1.45; color:var(--ink);">
        <span style="position:absolute; left:0; top:7px; width:4px; height:4px; border-radius:50%; background:var(--focus);"></span>
        Requirements inconsistencies create <b style="color:var(--ink);">compounding rework</b> across build and test.</div>
      <div style="position:relative; padding-left:13px; font-size:12.5px; line-height:1.45; color:var(--ink);">
        <span style="position:absolute; left:0; top:7px; width:4px; height:4px; border-radius:50%; background:var(--focus);"></span>
        Manual coordination consumes planning capacity.</div>
      <div style="position:relative; padding-left:13px; font-size:12.5px; line-height:1.45; color:var(--ink);">
        <span style="position:absolute; left:0; top:7px; width:4px; height:4px; border-radius:50%; background:var(--focus);"></span>
        Quality signals surface too late in the cycle.</div>
    </div>
  </div>
  <!-- Right: implication (secondary accent border) -->
  <div style="background:var(--paper-2); border:1px solid var(--rule); border-left:4px solid var(--secondary); border-radius:10px; padding:16px 18px; display:flex; flex-direction:column; justify-content:center;">
    <div style="font-size:10px; letter-spacing:0.16em; text-transform:uppercase; font-weight:700; color:var(--secondary); margin-bottom:10px;">So what</div>
    <div style="font-size:13px; line-height:1.5; color:var(--ink);">The evidence points to three addressable leverage points. The question is not whether to act, but <b style="color:var(--ink);">where to start</b> — and what is already within reach in the current toolchain.</div>
  </div>
</div>
```

**自检**：左框 `4px var(--focus)` 左条；右框 `4px var(--secondary)` 左条；要点圆点真实 `<span>` 走 `--focus`；两框背景分别走 `--paper` / `--paper-2`；颜色全走契约变量。

**管线安全**：真实 `<div>` grid；圆点是真实 `<span>`（非伪元素）；无 SVG `<text>`；无 `mask-image`/`conic-gradient`/`background-image:url()`。

---

### 数字统计看板 (metrics-scoreboard)

**何时用**：发现汇报或参与摘要的开场——5–6 个大字号单色数字（等宽字体）配短大写标签。传递"我们做了多少工作"的可信度信号。可用于页面顶部横幅或独占页。

**数据格式**：
```json
{
  "card_type": "data", "block_refs": ["discovery-readout"], "brief_kind": "metrics_scoreboard",
  "stats": [
    {"value": "10+", "label": "Discovery Sessions"},
    {"value": "20+", "label": "Participants Engaged"},
    {"value": "27",  "label": "Pain Points Identified"},
    {"value": "6",   "label": "Themes Synthesized"},
    {"value": "15",  "label": "Solution Concepts"}
  ]
}
```

**HTML 模板**（等分横排 · 等宽大数字 · 大写小标签 · 发丝分隔）：
```html
<div style="
  --focus:var(--accent-1); --ink:var(--text-primary); --dim:var(--text-secondary);
  --rule:var(--card-border); --mono:var(--font-mono); --sans:var(--font-primary);
  display:flex; font-family:var(--sans); font-variant-numeric:tabular-nums;">
  <div style="flex:1; text-align:center; padding:14px 10px; border-right:1px solid var(--rule);">
    <div style="font-family:var(--mono); font-size:40px; font-weight:800; line-height:1; color:var(--focus);">10+</div>
    <div style="font-size:9px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--dim); margin-top:7px;">Discovery Sessions</div>
  </div>
  <div style="flex:1; text-align:center; padding:14px 10px; border-right:1px solid var(--rule);">
    <div style="font-family:var(--mono); font-size:40px; font-weight:800; line-height:1; color:var(--focus);">20+</div>
    <div style="font-size:9px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--dim); margin-top:7px;">Participants Engaged</div>
  </div>
  <div style="flex:1; text-align:center; padding:14px 10px; border-right:1px solid var(--rule);">
    <div style="font-family:var(--mono); font-size:40px; font-weight:800; line-height:1; color:var(--focus);">27</div>
    <div style="font-size:9px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--dim); margin-top:7px;">Pain Points Identified</div>
  </div>
  <div style="flex:1; text-align:center; padding:14px 10px; border-right:1px solid var(--rule);">
    <div style="font-family:var(--mono); font-size:40px; font-weight:800; line-height:1; color:var(--focus);">6</div>
    <div style="font-size:9px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--dim); margin-top:7px;">Themes Synthesized</div>
  </div>
  <div style="flex:1; text-align:center; padding:14px 10px;">
    <div style="font-family:var(--mono); font-size:40px; font-weight:800; line-height:1; color:var(--focus);">15</div>
    <div style="font-size:9px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--dim); margin-top:7px;">Solution Concepts</div>
  </div>
</div>
```

**自检**：数字走等宽 `var(--mono)` + `tabular-nums`；数字色走 `--focus`；标签走 `--dim` 大写 `.18em`；分隔线走 `1px var(--rule)`；末列无右边框；颜色全走契约变量。

**管线安全**：真实 `<div>` flex；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

## B. 洞察 & 主题

### 阶段映射洞察卡网格 (stage-mapped-insight-card)

**何时用**：3×2 或 2×3 洞察卡网格——每张卡：洞察标题 + 2–3 句正文 + 主题标签 + 底部 SDLC 阶段药丸行（激活=主色；非激活=暗灰）。展示哪些交付阶段受每条洞察影响。高影响力卡用 `4px var(--focus)` 顶边；低影响力用规线色顶边。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["discovery-readout"], "brief_kind": "stage_insight_card",
  "cards": [
    {
      "title": "Manual coordination consumes planning capacity",
      "body": "Cross-team dependencies are resolved through synchronous meetings rather than structured handoffs, consuming a significant share of planning effort.",
      "theme": "Coordination & Dependency Management",
      "impact": "high",
      "active_phases": ["Planning", "Build"]
    }
  ],
  "all_phases": ["Planning", "Requirements", "Design", "Build", "Test", "Deploy"]
}
```

**HTML 模板**（3×2 网格 · 顶边强调 · 阶段药丸行）：
```html
<div style="
  --focus:var(--accent-1); --paper:var(--card-bg-from);
  --ink:var(--text-primary); --dim:var(--text-secondary); --rule:var(--card-border);
  --sans:var(--font-primary);
  display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; font-family:var(--sans);">

  <!-- High-impact card (focus top border) -->
  <div style="background:var(--paper); border:1px solid var(--rule); border-top:4px solid var(--focus); border-radius:10px; padding:14px 15px; display:flex; flex-direction:column;">
    <div style="font-weight:800; font-size:13.5px; line-height:1.25; color:var(--ink); margin-bottom:7px;">Manual coordination consumes planning capacity</div>
    <div style="font-size:12px; line-height:1.5; color:var(--ink); flex:1; margin-bottom:10px;">Cross-team dependencies are resolved through synchronous meetings rather than structured handoffs, consuming a significant share of planning effort.</div>
    <div style="font-size:10px; letter-spacing:0.09em; font-weight:600; color:var(--focus); margin-bottom:8px;">Coordination &amp; Dependency Management</div>
    <!-- Phase pill row -->
    <div style="display:flex; flex-wrap:wrap; gap:4px;">
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--focus); color:var(--paper);">Planning</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--rule); color:var(--dim);">Requirements</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--rule); color:var(--dim);">Design</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--focus); color:var(--paper);">Build</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--rule); color:var(--dim);">Test</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--rule); color:var(--dim);">Deploy</span>
    </div>
  </div>

  <!-- Standard-impact card (rule top border) -->
  <div style="background:var(--paper); border:1px solid var(--rule); border-top:4px solid var(--rule); border-radius:10px; padding:14px 15px; display:flex; flex-direction:column;">
    <div style="font-weight:800; font-size:13.5px; line-height:1.25; color:var(--ink); margin-bottom:7px;">Quality signals surface too late in the cycle</div>
    <div style="font-size:12px; line-height:1.5; color:var(--ink); flex:1; margin-bottom:10px;">Defects and integration issues are discovered in test or UAT rather than during build, compressing the time available for remediation.</div>
    <div style="font-size:10px; letter-spacing:0.09em; font-weight:600; color:var(--focus); margin-bottom:8px;">Testing Effectiveness &amp; Cycle Efficiency</div>
    <div style="display:flex; flex-wrap:wrap; gap:4px;">
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--rule); color:var(--dim);">Planning</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--rule); color:var(--dim);">Requirements</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--rule); color:var(--dim);">Design</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--focus); color:var(--paper);">Build</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--focus); color:var(--paper);">Test</span>
      <span style="font-size:9px; padding:2px 7px; border-radius:999px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; background:var(--rule); color:var(--dim);">Deploy</span>
    </div>
  </div>

</div>
```

**自检**：高影响力卡顶边 `4px var(--focus)`；标准卡顶边 `4px var(--rule)`；激活阶段药丸 `background:var(--focus); color:var(--paper)`；非激活药丸 `background:var(--rule); color:var(--dim)`；药丸是真实 `<span>`；主题标签走 `--focus`；颜色全走契约变量。

**管线安全**：真实 `<div>` grid；药丸是真实 `<span>`（非伪元素）；无 SVG `<text>`；无禁用 CSS。

---

### 综合主题卡 (synthesis-theme-card)

**何时用**：发现综合 / 主题深潜页——展示一个命名主题的完整叙事层：(a) 主题名 + 简述，(b) 观察叙事块，(c) 假设高亮框（"如果…那么…"），(d) 编号改进机会列表（带多类型徽章），(e) 可选的关联方案概念引用。是"痛点 → 观察 → 假设 → 机会"叙事链的容器。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["discovery-readout"], "brief_kind": "synthesis_theme",
  "number": "01",
  "name": "Requirements Quality & Delivery Consistency",
  "observation": "Requirements inconsistencies introduced late in the cycle create compounding rework across build and test phases. Teams spend significant effort reconciling conflicting acceptance criteria after design is underway.",
  "hypothesis": "If a structured quality gate is applied at requirements sign-off with automated completeness checks, then downstream rework in build and test phases will decrease measurably.",
  "opportunities": [
    {
      "number": "01", "title": "Automated requirements quality gate",
      "description": "Validate completeness and acceptance criteria coverage before requirements are baselined.",
      "types": ["Process", "AI"]
    },
    {
      "number": "02", "title": "Shared requirements authoring workflow",
      "description": "Standardize the story and feature authoring process with a shared template and review checklist.",
      "types": ["Process", "People"]
    }
  ]
}
```

**HTML 模板**（深色标题栏 + 观察 + 假设框 + 编号机会）：
```html
<div style="
  --focus:var(--accent-1); --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --ink:var(--text-primary); --dim:var(--text-secondary); --rule:var(--card-border);
  --sans:var(--font-primary); --mono:var(--font-mono);
  background:var(--paper); border:1px solid var(--rule); border-radius:12px;
  overflow:hidden; font-family:var(--sans);">
  <!-- Header bar (dark) -->
  <div style="background:var(--ink); padding:12px 17px; display:flex; align-items:center; gap:12px;">
    <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--focus); flex:0 0 auto;">01</span>
    <span style="font-size:14px; font-weight:800; color:var(--paper); line-height:1.2; flex:1;">Requirements Quality &amp; Delivery Consistency</span>
  </div>
  <!-- Body -->
  <div style="padding:16px 17px; display:flex; flex-direction:column; gap:13px;">
    <!-- Observation -->
    <div>
      <div style="font-size:10px; letter-spacing:0.13em; text-transform:uppercase; font-weight:700; color:var(--dim); margin-bottom:5px;">Observation</div>
      <div style="font-size:12.5px; line-height:1.5; color:var(--ink);">Requirements inconsistencies introduced late in the cycle create compounding rework across build and test phases. Teams spend significant effort reconciling conflicting acceptance criteria after design is underway.</div>
    </div>
    <!-- Hypothesis box -->
    <div style="background:var(--paper-2); border:1px solid var(--rule); border-left:4px solid var(--focus); border-radius:8px; padding:12px 14px;">
      <div style="font-size:10px; letter-spacing:0.13em; text-transform:uppercase; font-weight:700; color:var(--focus); margin-bottom:5px;">Hypothesis</div>
      <div style="font-size:12.5px; line-height:1.5; color:var(--ink); font-style:italic;">If a structured quality gate is applied at requirements sign-off with automated completeness checks, then downstream rework in build and test phases will decrease measurably.</div>
    </div>
    <!-- Opportunities -->
    <div>
      <div style="font-size:10px; letter-spacing:0.13em; text-transform:uppercase; font-weight:700; color:var(--dim); margin-bottom:8px;">Opportunities</div>
      <div style="display:flex; flex-direction:column; gap:9px;">
        <!-- Opportunity row -->
        <div style="display:flex; gap:10px; align-items:flex-start;">
          <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--focus); flex:0 0 20px; padding-top:1px;">01</span>
          <div style="flex:1;">
            <span style="font-size:12.5px; font-weight:800; color:var(--ink);">Automated requirements quality gate</span>
            <span style="font-size:12px; color:var(--dim);"> — Validate completeness and acceptance criteria coverage before requirements are baselined.</span>
            <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:5px;">
              <span style="font-size:9px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; padding:2px 7px; border-radius:4px; border:1px solid var(--rule); color:var(--dim); background:var(--paper);">Process</span>
              <span style="font-size:9px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; padding:2px 7px; border-radius:4px; border:1px solid var(--focus); color:var(--focus); background:var(--paper);">AI</span>
            </div>
          </div>
        </div>
        <div style="display:flex; gap:10px; align-items:flex-start;">
          <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--focus); flex:0 0 20px; padding-top:1px;">02</span>
          <div style="flex:1;">
            <span style="font-size:12.5px; font-weight:800; color:var(--ink);">Shared requirements authoring workflow</span>
            <span style="font-size:12px; color:var(--dim);"> — Standardize the story and feature authoring process with a shared template and review checklist.</span>
            <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:5px;">
              <span style="font-size:9px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; padding:2px 7px; border-radius:4px; border:1px solid var(--rule); color:var(--dim); background:var(--paper);">Process</span>
              <span style="font-size:9px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; padding:2px 7px; border-radius:4px; border:1px solid var(--rule); color:var(--dim); background:var(--paper);">People</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

**自检**：深色标题栏 `background:var(--ink)`，主题编号 `var(--focus)`，标题文字 `var(--paper)`；观察/机会标签走 `--dim` 大写；假设框 `4px var(--focus)` 左条 + `font-style:italic`；机会编号走 `var(--mono)` + `var(--focus)`；AI 类型徽章用 focus 色边框；颜色全走契约变量。

**管线安全**：真实 `<div>`；徽章是真实 `<span>`（非伪元素）；无 SVG `<text>`；无禁用 CSS。

---

## C. 方法论 & 前瞻

### 方法论三栏网格 (methodology-three-column)

**何时用**："我们如何开展这项工作"的方法论页——三栏并列：左列（编号步骤"Our Approach"）/ 中列（主次双列聚焦领域"Focus Areas"）/ 右列（大数字"By the Numbers"）。竖线分隔三栏。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["discovery-readout"], "brief_kind": "methodology_columns",
  "approach_steps": [
    "Structured stakeholder interviews across delivery roles and business units",
    "Process-mapping workshops to trace the end-to-end delivery lifecycle",
    "Pain-point synthesis and theme clustering across interview sessions",
    "Solution ideation mapped to identified pain points and delivery phases"
  ],
  "focus_areas": {
    "primary": ["Planning & Requirements", "Build & Test", "Deploy & Release"],
    "secondary": ["Cross-team Coordination", "Toolchain & AI Enablement"]
  },
  "stats": [
    {"value": "10+", "label": "Sessions"},
    {"value": "20+", "label": "Stakeholders"},
    {"value": "6",   "label": "Weeks"}
  ]
}
```

**HTML 模板**（三栏竖线分隔 · 编号步骤 · 主次聚焦 · 大数字）：
```html
<div style="
  --focus:var(--accent-1); --ink:var(--text-primary); --dim:var(--text-secondary);
  --rule:var(--card-border); --mono:var(--font-mono); --sans:var(--font-primary);
  display:grid; grid-template-columns:1fr 1px 1fr 1px 1fr; gap:0; font-family:var(--sans);">
  <!-- Column 1: Approach steps -->
  <div style="padding:0 18px 0 0;">
    <div style="font-size:10px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--focus); margin-bottom:11px;">Our Approach</div>
    <div style="display:flex; flex-direction:column; gap:10px;">
      <div style="display:flex; gap:10px; align-items:flex-start;">
        <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--focus); flex:0 0 18px; padding-top:1px;">01</span>
        <div style="font-size:12.5px; line-height:1.4; color:var(--ink);">Structured stakeholder interviews across delivery roles and business units</div>
      </div>
      <div style="display:flex; gap:10px; align-items:flex-start;">
        <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--focus); flex:0 0 18px; padding-top:1px;">02</span>
        <div style="font-size:12.5px; line-height:1.4; color:var(--ink);">Process-mapping workshops to trace the end-to-end delivery lifecycle</div>
      </div>
      <div style="display:flex; gap:10px; align-items:flex-start;">
        <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--focus); flex:0 0 18px; padding-top:1px;">03</span>
        <div style="font-size:12.5px; line-height:1.4; color:var(--ink);">Pain-point synthesis and theme clustering across interview sessions</div>
      </div>
      <div style="display:flex; gap:10px; align-items:flex-start;">
        <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--focus); flex:0 0 18px; padding-top:1px;">04</span>
        <div style="font-size:12.5px; line-height:1.4; color:var(--ink);">Solution ideation mapped to identified pain points and delivery phases</div>
      </div>
    </div>
  </div>
  <!-- Divider -->
  <div style="background:var(--rule);"></div>
  <!-- Column 2: Focus Areas -->
  <div style="padding:0 18px;">
    <div style="font-size:10px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--focus); margin-bottom:11px;">Focus Areas</div>
    <div style="font-size:10.5px; font-weight:700; text-transform:uppercase; letter-spacing:0.09em; color:var(--dim); margin-bottom:6px;">Delivery Stages</div>
    <div style="display:flex; flex-direction:column; gap:5px; margin-bottom:13px;">
      <div style="font-size:12.5px; color:var(--ink);"><span style="color:var(--focus); font-weight:700; margin-right:7px;">&#10003;</span>Planning &amp; Requirements</div>
      <div style="font-size:12.5px; color:var(--ink);"><span style="color:var(--focus); font-weight:700; margin-right:7px;">&#10003;</span>Build &amp; Test</div>
      <div style="font-size:12.5px; color:var(--ink);"><span style="color:var(--focus); font-weight:700; margin-right:7px;">&#10003;</span>Deploy &amp; Release</div>
    </div>
    <div style="font-size:10.5px; font-weight:700; text-transform:uppercase; letter-spacing:0.09em; color:var(--dim); margin-bottom:6px;">Cross-cutting</div>
    <div style="display:flex; flex-direction:column; gap:5px;">
      <div style="font-size:12.5px; color:var(--dim);">&#8226; Cross-team Coordination</div>
      <div style="font-size:12.5px; color:var(--dim);">&#8226; Toolchain &amp; AI Enablement</div>
    </div>
  </div>
  <!-- Divider -->
  <div style="background:var(--rule);"></div>
  <!-- Column 3: By the Numbers -->
  <div style="padding:0 0 0 18px;">
    <div style="font-size:10px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--focus); margin-bottom:11px;">By the Numbers</div>
    <div style="display:flex; flex-direction:column; gap:14px; font-variant-numeric:tabular-nums;">
      <div>
        <div style="font-family:var(--mono); font-size:34px; font-weight:800; line-height:1; color:var(--focus);">10+</div>
        <div style="font-size:11px; color:var(--dim); margin-top:3px;">Discovery sessions</div>
      </div>
      <div>
        <div style="font-family:var(--mono); font-size:34px; font-weight:800; line-height:1; color:var(--focus);">20+</div>
        <div style="font-size:11px; color:var(--dim); margin-top:3px;">Stakeholders engaged</div>
      </div>
      <div>
        <div style="font-family:var(--mono); font-size:34px; font-weight:800; line-height:1; color:var(--focus);">6</div>
        <div style="font-size:11px; color:var(--dim); margin-top:3px;">Weeks of discovery</div>
      </div>
    </div>
  </div>
</div>
```

**自检**：三栏通过 `1px var(--rule)` 分隔；编号走 `var(--mono)` + `var(--focus)`；主次聚焦复选标记 `&#10003;` 走 `--focus`；次要项走 `&#8226;` + `--dim`；数字栏走 `var(--mono)` + `tabular-nums`；颜色全走契约变量。

**管线安全**：真实 `<div>` grid；`&#10003;` / `&#8226;` 是文本 glyph；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

### 锚定问题面板 (anchoring-questions-panel)

**何时用**：发现汇报收尾的"前瞻桥接"页——3–5 个开放式锚定问题框定下一阶段，而非给出结论性建议。问题是前瞻的，不是陈述性的。适合"未来状态 / What's Next"过渡页或章末问题框。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["discovery-readout"], "brief_kind": "anchoring_questions",
  "label": "What's next — open questions for the next phase",
  "questions": [
    "What does the future-state delivery landscape look like across all in-flight AI initiatives?",
    "Which AI capabilities in the current toolchain are not yet activated — and what is the unlock path?",
    "Where should agentic solutions be built on top of or alongside existing delivery tooling?",
    "How can automation help govern and maintain delivery compliance end-to-end?"
  ]
}
```

**HTML 模板**（问题编号 + 左边框卡 · 开放语气）：
```html
<div style="
  --focus:var(--accent-1); --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --ink:var(--text-primary); --dim:var(--text-secondary); --rule:var(--card-border);
  --mono:var(--font-mono); --sans:var(--font-primary);
  font-family:var(--sans);">
  <div style="font-size:10px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--focus); margin-bottom:11px;">What's next — open questions for the next phase</div>
  <div style="display:flex; flex-direction:column; gap:9px;">
    <div style="background:var(--paper-2); border:1px solid var(--rule); border-left:3px solid var(--focus); border-radius:8px; padding:12px 16px; display:flex; gap:12px; align-items:flex-start;">
      <span style="font-family:var(--mono); font-size:14px; font-weight:800; color:var(--focus); flex:0 0 22px; padding-top:0px; line-height:1;">01</span>
      <div style="font-size:13px; line-height:1.5; color:var(--ink);">What does the future-state delivery landscape look like across all in-flight AI initiatives?</div>
    </div>
    <div style="background:var(--paper-2); border:1px solid var(--rule); border-left:3px solid var(--focus); border-radius:8px; padding:12px 16px; display:flex; gap:12px; align-items:flex-start;">
      <span style="font-family:var(--mono); font-size:14px; font-weight:800; color:var(--focus); flex:0 0 22px; line-height:1;">02</span>
      <div style="font-size:13px; line-height:1.5; color:var(--ink);">Which AI capabilities in the current toolchain are not yet activated — and what is the unlock path?</div>
    </div>
    <div style="background:var(--paper-2); border:1px solid var(--rule); border-left:3px solid var(--focus); border-radius:8px; padding:12px 16px; display:flex; gap:12px; align-items:flex-start;">
      <span style="font-family:var(--mono); font-size:14px; font-weight:800; color:var(--focus); flex:0 0 22px; line-height:1;">03</span>
      <div style="font-size:13px; line-height:1.5; color:var(--ink);">Where should agentic solutions be built on top of or alongside existing delivery tooling?</div>
    </div>
    <div style="background:var(--paper-2); border:1px solid var(--rule); border-left:3px solid var(--focus); border-radius:8px; padding:12px 16px; display:flex; gap:12px; align-items:flex-start;">
      <span style="font-family:var(--mono); font-size:14px; font-weight:800; color:var(--focus); flex:0 0 22px; line-height:1;">04</span>
      <div style="font-size:13px; line-height:1.5; color:var(--ink);">How can automation help govern and maintain delivery compliance end-to-end?</div>
    </div>
  </div>
</div>
```

**自检**：标签走 `--focus` 大写 `.18em`；每个问题框 `3px var(--focus)` 左条 + `var(--paper-2)` 背景；编号走 `var(--mono)` + `var(--focus)`；框体文字走 `--ink`；无结论性语气；颜色全走契约变量。

**管线安全**：真实 `<div>` flex；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

## D. 分类 & 参考

### AI 成熟度分类 (ai-maturity-taxonomy)

**何时用**：AI 能力分类图例或成熟度模型轴——四级水平进阶：AI Assisted → AI Augmented → AI Adaptive → AI Autonomous。可作为图例参考条、方案分类标签系统、或独立页面展示 AI 采用路线。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["discovery-readout"], "brief_kind": "ai_maturity_taxonomy",
  "levels": [
    {"number": "01", "name": "AI Assisted",   "description": "Human-driven with AI suggestions and recommendations"},
    {"number": "02", "name": "AI Augmented",  "description": "AI executes defined subtasks with human oversight"},
    {"number": "03", "name": "AI Adaptive",   "description": "AI learns and adjusts based on context and outcomes"},
    {"number": "04", "name": "AI Autonomous", "description": "AI operates end-to-end with minimal human intervention"}
  ]
}
```

**HTML 模板**（四级横向进阶 · 箭头连接 · 最高级主色边框强调）：
```html
<div style="
  --focus:var(--accent-1); --ink:var(--text-primary); --dim:var(--text-secondary);
  --rule:var(--card-border); --paper:var(--card-bg-from); --sans:var(--font-primary); --mono:var(--font-mono);
  font-family:var(--sans);">
  <div style="font-size:10px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--dim); margin-bottom:10px;">AI Capability Maturity</div>
  <div style="display:flex; align-items:stretch; gap:0;">
    <!-- Level 1 -->
    <div style="flex:1; background:var(--paper); border:1px solid var(--rule); border-right:0; border-radius:8px 0 0 8px; padding:13px 14px;">
      <div style="font-family:var(--mono); font-size:10px; font-weight:800; color:var(--dim); letter-spacing:0.10em; margin-bottom:5px;">01</div>
      <div style="font-weight:800; font-size:13px; color:var(--ink); margin-bottom:5px;">AI Assisted</div>
      <div style="font-size:11px; line-height:1.4; color:var(--dim);">Human-driven with AI suggestions and recommendations</div>
    </div>
    <div style="display:flex; align-items:center; padding:0 5px; color:var(--dim); font-size:18px; flex:0 0 auto;">&#10142;</div>
    <!-- Level 2 -->
    <div style="flex:1; background:var(--paper); border:1px solid var(--rule); border-right:0; padding:13px 14px;">
      <div style="font-family:var(--mono); font-size:10px; font-weight:800; color:var(--dim); letter-spacing:0.10em; margin-bottom:5px;">02</div>
      <div style="font-weight:800; font-size:13px; color:var(--ink); margin-bottom:5px;">AI Augmented</div>
      <div style="font-size:11px; line-height:1.4; color:var(--dim);">AI executes defined subtasks with human oversight</div>
    </div>
    <div style="display:flex; align-items:center; padding:0 5px; color:var(--dim); font-size:18px; flex:0 0 auto;">&#10142;</div>
    <!-- Level 3 -->
    <div style="flex:1; background:var(--paper); border:1px solid var(--rule); border-right:0; padding:13px 14px;">
      <div style="font-family:var(--mono); font-size:10px; font-weight:800; color:var(--focus); letter-spacing:0.10em; margin-bottom:5px;">03</div>
      <div style="font-weight:800; font-size:13px; color:var(--ink); margin-bottom:5px;">AI Adaptive</div>
      <div style="font-size:11px; line-height:1.4; color:var(--dim);">AI learns and adjusts based on context and outcomes</div>
    </div>
    <div style="display:flex; align-items:center; padding:0 5px; color:var(--focus); font-size:18px; flex:0 0 auto;">&#10142;</div>
    <!-- Level 4 (highest — focus border) -->
    <div style="flex:1; background:var(--paper); border:1px solid var(--focus); border-top:3px solid var(--focus); border-radius:0 8px 8px 0; padding:13px 14px;">
      <div style="font-family:var(--mono); font-size:10px; font-weight:800; color:var(--focus); letter-spacing:0.10em; margin-bottom:5px;">04</div>
      <div style="font-weight:800; font-size:13px; color:var(--ink); margin-bottom:5px;">AI Autonomous</div>
      <div style="font-size:11px; line-height:1.4; color:var(--dim);">AI operates end-to-end with minimal human intervention</div>
    </div>
  </div>
</div>
```

**自检**：1–3 级走 `1px var(--rule)` 常规边框；4 级走 `1px var(--focus)` + `3px var(--focus)` 顶边；3–4 级编号 / 箭头走 `--focus`；箭头 `&#10142;` 是文本 glyph；标签走 `--dim` 大写；颜色全走契约变量。

**管线安全**：真实 `<div>` flex；`&#10142;` 是文本 glyph；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

### 机会类型徽章条 (opportunity-badge-strip)

**何时用**：展示改进机会的六类分类图例，或作为综合主题卡、发现追踪表中每条机会的内联类型标签系统。六个类别：Process & Ways of Working / People & Skills / Tooling & Technology / Automation / AI / Governance & Standards。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["discovery-readout"], "brief_kind": "opportunity_badge_strip",
  "label": "Opportunity Types",
  "badges": [
    {"name": "Process & Ways of Working"},
    {"name": "People & Skills"},
    {"name": "Tooling & Technology"},
    {"name": "Automation"},
    {"name": "AI", "highlight": true},
    {"name": "Governance & Standards"}
  ]
}
```

**HTML 模板**（六类横向药丸 · AI 类型主色高亮）：
```html
<div style="
  --focus:var(--accent-1); --ink:var(--text-primary); --dim:var(--text-secondary);
  --rule:var(--card-border); --paper:var(--card-bg-from); --sans:var(--font-primary);
  font-family:var(--sans);">
  <div style="font-size:10px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--dim); margin-bottom:9px;">Opportunity Types</div>
  <div style="display:flex; flex-wrap:wrap; gap:8px;">
    <span style="font-size:10px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:5px 12px; border-radius:5px; border:1px solid var(--rule); color:var(--ink); background:var(--paper);">Process &amp; Ways of Working</span>
    <span style="font-size:10px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:5px 12px; border-radius:5px; border:1px solid var(--rule); color:var(--ink); background:var(--paper);">People &amp; Skills</span>
    <span style="font-size:10px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:5px 12px; border-radius:5px; border:1px solid var(--rule); color:var(--ink); background:var(--paper);">Tooling &amp; Technology</span>
    <span style="font-size:10px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:5px 12px; border-radius:5px; border:1px solid var(--rule); color:var(--ink); background:var(--paper);">Automation</span>
    <span style="font-size:10px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:5px 12px; border-radius:5px; border:1px solid var(--focus); color:var(--focus); background:var(--paper);">AI</span>
    <span style="font-size:10px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:5px 12px; border-radius:5px; border:1px solid var(--rule); color:var(--ink); background:var(--paper);">Governance &amp; Standards</span>
  </div>
</div>
```

**自检**：AI 徽章用 `var(--focus)` 边框 + 文字颜色高亮；其余走 `1px var(--rule)` 边框 + `--ink` 文字；标签走 `--dim` 大写；颜色全走契约变量。

**管线安全**：真实 `<span>` flex；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

### 覆盖热力图 (coverage-heatmap)

**何时用**：类别行 × 交付阶段列的网格——每格显示两枚计数药丸（生产 = 主色，管道/计划中 = 次色）；格背景色随数量深浅变化（空格 = 纸面色，低密度 = 浅底，高密度 = 稍深底）。展示工具链、AI 用例或任何跨阶段覆盖的密度分布。

**数据格式**：
```json
{
  "card_type": "data", "block_refs": ["discovery-readout"], "brief_kind": "coverage_heatmap",
  "phases": ["Planning", "Requirements", "Design", "Build", "Test", "Deploy"],
  "rows": [
    {
      "category": "AI & Automation",
      "cells": [
        {"prod": 3, "pipe": 12, "density": "high"},
        {"prod": 1, "pipe": 6,  "density": "medium"},
        {"prod": 0, "pipe": 2,  "density": "low"},
        {"prod": 4, "pipe": 18, "density": "high"},
        {"prod": 5, "pipe": 22, "density": "high"},
        {"prod": 2, "pipe": 7,  "density": "medium"}
      ]
    },
    {
      "category": "Code Quality & Security",
      "cells": [
        {"prod": 0, "pipe": 0,  "density": "empty"},
        {"prod": 0, "pipe": 1,  "density": "low"},
        {"prod": 1, "pipe": 3,  "density": "low"},
        {"prod": 3, "pipe": 8,  "density": "high"},
        {"prod": 2, "pipe": 5,  "density": "medium"},
        {"prod": 1, "pipe": 2,  "density": "low"}
      ]
    }
  ],
  "legend": {"prod_label": "Production", "pipe_label": "Pipeline"}
}
```

**HTML 模板**（黑表头 + 密度背景 + 双色计数药丸 + 图例）：
```html
<div style="
  --focus:var(--accent-1); --pipe:var(--accent-2);
  --ink:var(--text-primary); --dim:var(--text-secondary); --rule:var(--card-border);
  --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --mono:var(--font-mono); --sans:var(--font-primary);
  font-family:var(--sans); overflow-x:auto;">
  <table style="border-collapse:collapse; width:100%; font-size:11px; min-width:560px; font-variant-numeric:tabular-nums;">
    <thead>
      <tr>
        <th style="padding:9px 12px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.12em; font-weight:700; text-align:left; min-width:130px;">Category</th>
        <th style="padding:9px 8px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Planning</th>
        <th style="padding:9px 8px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Requirements</th>
        <th style="padding:9px 8px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Design</th>
        <th style="padding:9px 8px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Build</th>
        <th style="padding:9px 8px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Test</th>
        <th style="padding:9px 8px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Deploy</th>
      </tr>
    </thead>
    <tbody>
      <!-- High-density row -->
      <tr>
        <td style="padding:9px 12px; border:1px solid var(--rule); font-weight:700; color:var(--ink);">AI &amp; Automation</td>
        <!-- High-density cell -->
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center; background:var(--paper-2);">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--focus); color:var(--paper); margin:1px;">3</span>
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">12</span>
        </td>
        <!-- Medium-density cell -->
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center;">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--focus); color:var(--paper); margin:1px;">1</span>
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">6</span>
        </td>
        <!-- Low-density cell -->
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center;">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">2</span>
        </td>
        <!-- High-density cell -->
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center; background:var(--paper-2);">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--focus); color:var(--paper); margin:1px;">4</span>
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">18</span>
        </td>
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center; background:var(--paper-2);">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--focus); color:var(--paper); margin:1px;">5</span>
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">22</span>
        </td>
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center;">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--focus); color:var(--paper); margin:1px;">2</span>
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">7</span>
        </td>
      </tr>
      <!-- Second row -->
      <tr style="background:var(--paper-2);">
        <td style="padding:9px 12px; border:1px solid var(--rule); font-weight:700; color:var(--ink);">Code Quality &amp; Security</td>
        <!-- Empty cell -->
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center;">
          <span style="font-size:10px; color:var(--dim);">—</span>
        </td>
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center;">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">1</span>
        </td>
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center;">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--focus); color:var(--paper); margin:1px;">1</span>
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">3</span>
        </td>
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center; background:var(--paper);">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--focus); color:var(--paper); margin:1px;">3</span>
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">8</span>
        </td>
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center;">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--focus); color:var(--paper); margin:1px;">2</span>
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">5</span>
        </td>
        <td style="padding:7px 6px; border:1px solid var(--rule); text-align:center;">
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--focus); color:var(--paper); margin:1px;">1</span>
          <span style="display:inline-block; font-family:var(--mono); font-size:9px; font-weight:800; padding:2px 6px; border-radius:4px; background:var(--pipe); color:var(--paper); margin:1px;">2</span>
        </td>
      </tr>
    </tbody>
  </table>
  <!-- Legend -->
  <div style="display:flex; gap:16px; margin-top:9px; font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.10em; color:var(--dim);">
    <span><span style="display:inline-block; width:10px; height:10px; border-radius:3px; background:var(--focus); vertical-align:middle; margin-right:5px;"></span>Production</span>
    <span><span style="display:inline-block; width:10px; height:10px; border-radius:3px; background:var(--pipe); vertical-align:middle; margin-right:5px;"></span>Pipeline</span>
  </div>
</div>
```

**自检**：表头走 `background:var(--ink)` + `var(--paper)` 反白；生产药丸 `background:var(--focus)`；管道药丸 `background:var(--pipe)`；高密度格 `background:var(--paper-2)` 稍深；空格显示 `—` + `var(--dim)`；数字开 `tabular-nums`；图例走 `var(--mono)` 大写；颜色全走契约变量（无 rgba/hex）。

**管线安全**：真实 `<table>`；药丸是真实 `<span>`；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

## E. 追踪 & 优先级

### 发现追踪表 (findings-tracker)

**何时用**：结构化呈现全部发现项（痛点/洞察/风险）——行：ID / 来源群组 / 交付阶段 / 严重性徽章 / 标题 / 简述 / 主题。深色分组标题行作分区分隔。适合发现汇报附录或工作会议底稿。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["discovery-readout"], "brief_kind": "findings_tracker",
  "groups": [
    {
      "label": "Quality Assurance",
      "rows": [
        {
          "id": "PP-01", "cohort": "QA Lead", "stage": "Test",
          "severity": "High",
          "title": "Regression scope is manually scoped each cycle",
          "description": "Teams manually select regression test cases per release without automated impact analysis.",
          "theme": "Testing Effectiveness"
        }
      ]
    }
  ]
}
```

**HTML 模板**（深色表头 + 分组标题行 + 严重性徽章）：
```html
<div style="
  --sev-hi:#ef4444; --sev-med:#b35900; --sev-med-soft:#fef3e6;
  --ink:var(--text-primary); --dim:var(--text-secondary); --rule:var(--card-border);
  --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --mono:var(--font-mono); --sans:var(--font-primary);
  font-family:var(--sans); overflow-x:auto;">
  <table style="border-collapse:collapse; width:100%; font-size:12px; min-width:640px;">
    <thead>
      <tr style="background:var(--ink);">
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left;">ID</th>
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left;">Cohort</th>
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left;">Stage</th>
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left;">Severity</th>
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left;">Finding</th>
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left;">Theme</th>
      </tr>
    </thead>
    <tbody>
      <!-- Group header row -->
      <tr style="background:var(--ink);">
        <td colspan="6" style="padding:7px 11px; color:var(--paper); font-size:10px; font-family:var(--mono); font-weight:700; text-transform:uppercase; letter-spacing:0.12em;">Quality Assurance</td>
      </tr>
      <!-- Finding row (High severity) -->
      <tr style="border-bottom:1px solid var(--rule);">
        <td style="padding:9px 11px; font-family:var(--mono); font-size:10px; font-weight:700; color:var(--dim); white-space:nowrap;">PP-01</td>
        <td style="padding:9px 11px; color:var(--dim); white-space:nowrap;">QA Lead</td>
        <td style="padding:9px 11px; color:var(--dim); white-space:nowrap;">Test</td>
        <td style="padding:9px 11px; white-space:nowrap;">
          <span style="font-size:9px; font-weight:800; letter-spacing:0.09em; text-transform:uppercase; padding:3px 8px; border-radius:4px; color:var(--paper); background:var(--sev-hi);">High</span>
        </td>
        <td style="padding:9px 11px; font-weight:600; color:var(--ink);">Regression scope is manually scoped each cycle</td>
        <td style="padding:9px 11px; color:var(--dim);">Testing Effectiveness</td>
      </tr>
      <!-- Second group header -->
      <tr style="background:var(--ink);">
        <td colspan="6" style="padding:7px 11px; color:var(--paper); font-size:10px; font-family:var(--mono); font-weight:700; text-transform:uppercase; letter-spacing:0.12em;">Engineering</td>
      </tr>
      <!-- Finding row (Medium severity) -->
      <tr style="background:var(--paper-2); border-bottom:1px solid var(--rule);">
        <td style="padding:9px 11px; font-family:var(--mono); font-size:10px; font-weight:700; color:var(--dim);">PP-02</td>
        <td style="padding:9px 11px; color:var(--dim);">Engineer</td>
        <td style="padding:9px 11px; color:var(--dim);">Build</td>
        <td style="padding:9px 11px;">
          <span style="font-size:9px; font-weight:800; letter-spacing:0.09em; text-transform:uppercase; padding:3px 8px; border-radius:4px; color:var(--paper); background:var(--sev-med);">Med</span>
        </td>
        <td style="padding:9px 11px; font-weight:600; color:var(--ink);">Environment provisioning requires manual steps</td>
        <td style="padding:9px 11px; color:var(--dim);">Pipeline Quality</td>
      </tr>
    </tbody>
  </table>
</div>
```

**自检**：深色表头 `background:var(--ink)` + `var(--paper)` 反白字；分组标题行走 `var(--ink)` 深色 + `var(--mono)` + 大写；High 徽章走 `--sev-hi`（`#ef4444`，碳out）；Med 徽章走 `--sev-med`（`#b35900`，碳out）；Low 走 `var(--dim)` 文字无背景；颜色除碳out全走契约变量。

**管线安全**：真实 `<table>`；徽章是真实 `<span>`；无伪元素；无 SVG `<text>`；无禁用 CSS；`--sev-hi`/`--sev-med` 是唯一允许的碳out hex（与趋势色 `#ef4444` 及 worksheet warn `#b35900` 同条款）。

---

### 优先级评分矩阵 (prioritization-scorecard)

**何时用**：方案概念行 × 评估子准则列的评分矩阵——1–4 热力色标（低=红调，高=绿调）；列按 3 个父维度分组；末列显示总分 + 排名。适合优先级评估工作会议或下一阶段资源筛选讨论。

**数据格式**：
```json
{
  "card_type": "data", "block_refs": ["discovery-readout"], "brief_kind": "prioritization_scorecard",
  "dimensions": [
    {"label": "Strategic Alignment", "criteria": ["Business Value", "AI Fit"]},
    {"label": "Delivery", "criteria": ["Feasibility", "Time to Value"]},
    {"label": "Risk", "criteria": ["Tech Risk", "Change Risk"]}
  ],
  "concepts": [
    {"rank": 1, "name": "Delivery reporting assistant",  "scores": [3, 3, 4, 4, 4, 4]},
    {"rank": 2, "name": "Automated regression scoping",  "scores": [4, 4, 3, 4, 3, 3]},
    {"rank": 3, "name": "Story quality gate",            "scores": [3, 4, 3, 3, 4, 3]}
  ]
}
```

**HTML 模板**（分组列头 + 1–4 热力色标 + 总分排名）：
```html
<div style="
  --heat-ok:#1f7a3a; --heat-ok-soft:#e9f5ed; --heat-lo:#ef4444;
  --ink:var(--text-primary); --dim:var(--text-secondary); --rule:var(--card-border);
  --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --mono:var(--font-mono); --sans:var(--font-primary);
  font-family:var(--sans); overflow-x:auto;">
  <table style="border-collapse:collapse; width:100%; font-size:11px; min-width:600px; font-variant-numeric:tabular-nums;">
    <!-- Parent dimension header row -->
    <thead>
      <tr>
        <th rowspan="2" style="padding:9px 12px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; text-align:left; min-width:180px;">Concept</th>
        <th rowspan="2" style="padding:9px 8px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; text-align:center;">Rank</th>
        <th colspan="2" style="padding:8px; background:var(--ink); color:var(--paper); font-size:10px; font-weight:700; text-align:center; border-left:1px solid var(--dim);">Strategic Alignment</th>
        <th colspan="2" style="padding:8px; background:var(--ink); color:var(--paper); font-size:10px; font-weight:700; text-align:center; border-left:1px solid var(--dim);">Delivery</th>
        <th colspan="2" style="padding:8px; background:var(--ink); color:var(--paper); font-size:10px; font-weight:700; text-align:center; border-left:1px solid var(--dim);">Risk</th>
        <th rowspan="2" style="padding:9px 8px; background:var(--ink); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; text-align:center;">Total</th>
      </tr>
      <tr>
        <th style="padding:7px 8px; background:var(--paper-2); color:var(--dim); font-size:9px; text-transform:uppercase; letter-spacing:0.09em; text-align:center; border-left:1px solid var(--rule);">Biz Value</th>
        <th style="padding:7px 8px; background:var(--paper-2); color:var(--dim); font-size:9px; text-transform:uppercase; letter-spacing:0.09em; text-align:center;">AI Fit</th>
        <th style="padding:7px 8px; background:var(--paper-2); color:var(--dim); font-size:9px; text-transform:uppercase; letter-spacing:0.09em; text-align:center; border-left:1px solid var(--rule);">Feasibility</th>
        <th style="padding:7px 8px; background:var(--paper-2); color:var(--dim); font-size:9px; text-transform:uppercase; letter-spacing:0.09em; text-align:center;">Time-to-Val</th>
        <th style="padding:7px 8px; background:var(--paper-2); color:var(--dim); font-size:9px; text-transform:uppercase; letter-spacing:0.09em; text-align:center; border-left:1px solid var(--rule);">Tech Risk</th>
        <th style="padding:7px 8px; background:var(--paper-2); color:var(--dim); font-size:9px; text-transform:uppercase; letter-spacing:0.09em; text-align:center;">Chg Risk</th>
      </tr>
    </thead>
    <tbody>
      <!-- Rank 1 row (total 22) -->
      <tr>
        <td style="padding:9px 12px; font-weight:700; color:var(--ink); border-bottom:1px solid var(--rule);">Delivery reporting assistant</td>
        <td style="padding:9px 8px; text-align:center; font-family:var(--mono); font-weight:800; color:var(--ink); border-bottom:1px solid var(--rule);">1</td>
        <!-- Score 3 (mid = paper-2) -->
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); border-left:1px solid var(--rule); background:var(--paper-2);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--ink);">3</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); background:var(--paper-2);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--ink);">3</span></td>
        <!-- Score 4 (high = green) -->
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); border-left:1px solid var(--rule); background:var(--heat-ok-soft);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--heat-ok);">4</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); background:var(--heat-ok-soft);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--heat-ok);">4</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); border-left:1px solid var(--rule); background:var(--heat-ok-soft);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--heat-ok);">4</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); background:var(--heat-ok-soft);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--heat-ok);">4</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); font-family:var(--mono); font-weight:800; font-size:14px; color:var(--ink);">22</td>
      </tr>
      <!-- Rank 2 row (total 21) -->
      <tr style="background:var(--paper-2);">
        <td style="padding:9px 12px; font-weight:700; color:var(--ink); border-bottom:1px solid var(--rule);">Automated regression scoping</td>
        <td style="padding:9px 8px; text-align:center; font-family:var(--mono); font-weight:800; color:var(--ink); border-bottom:1px solid var(--rule);">2</td>
        <!-- Score 4 (high = green) -->
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); border-left:1px solid var(--rule); background:var(--heat-ok-soft);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--heat-ok);">4</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); background:var(--heat-ok-soft);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--heat-ok);">4</span></td>
        <!-- Score 3 (mid = paper-2) -->
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); border-left:1px solid var(--rule); background:var(--paper-2);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--ink);">3</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); background:var(--heat-ok-soft);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--heat-ok);">4</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); border-left:1px solid var(--rule); background:var(--paper-2);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--ink);">3</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); background:var(--paper-2);">
          <span style="font-family:var(--mono); font-weight:800; font-size:13px; color:var(--ink);">3</span></td>
        <td style="padding:9px 8px; text-align:center; border-bottom:1px solid var(--rule); font-family:var(--mono); font-weight:800; font-size:14px; color:var(--ink);">21</td>
      </tr>
    </tbody>
  </table>
  <!-- Scale legend -->
  <div style="display:flex; gap:16px; margin-top:8px; font-size:10px; font-family:var(--mono); text-transform:uppercase; letter-spacing:0.09em; color:var(--dim);">
    <span style="color:var(--heat-lo);">1 = Lowest</span>
    <span>2 = Below avg</span>
    <span>3 = Above avg</span>
    <span style="color:var(--heat-ok);">4 = Highest</span>
  </div>
</div>
```

**自检**：分组父维度列头占双行 `rowspan="2"` + `colspan="N"`；4 分格走 `--heat-ok-soft` 背景 + `--heat-ok` 数字；3 分格走 `--paper-2` 背景 + `--ink` 数字；分数走 `var(--mono)` + `font-weight:800`；总分列固定末位；图例文字走碳out变量；颜色除碳out全走契约变量。

**管线安全**：真实 `<table>`；无伪元素；无 SVG `<text>`；无禁用 CSS；`--heat-ok`/`--heat-ok-soft`/`--heat-lo` 是碳out（与 worksheet ok/warn 及趋势色同条款）。

---

### 影响力-投入定位图 (impact-effort-chart)

**何时用**：2D 散点象限图——X 轴=实施投入（低→高），Y 轴=业务影响（低→高）；方案概念标为带标签的圆点；四象限命名（快速获益 / 战略押注 / 低优先级 / 高耗低效）。适合优先级工作会议、方案下一阶段筛选讨论。

**数据格式**：
```json
{
  "card_type": "data", "block_refs": ["discovery-readout"], "brief_kind": "impact_effort_chart",
  "quadrant_labels": {
    "top_left":     "Quick Wins",
    "top_right":    "Strategic Bets",
    "bottom_left":  "Low Priority",
    "bottom_right": "High Cost / Low Return"
  },
  "items": [
    {"label": "Automated regression scoping", "effort": 30, "impact": 78, "highlight": true},
    {"label": "Delivery reporting assistant",  "effort": 20, "impact": 65, "highlight": true},
    {"label": "Story quality gate",            "effort": 45, "impact": 70},
    {"label": "Deployment readiness check",    "effort": 60, "impact": 55},
    {"label": "Test data discovery",           "effort": 70, "impact": 42}
  ]
}
```

**HTML 模板**（SVG 象限底板 + 十字轴 + 圆点 · HTML 叠加标签，无 `<text>`）：
```html
<div style="
  --focus:var(--accent-1); --ink:var(--text-primary); --dim:var(--text-secondary);
  --rule:var(--card-border); --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --mono:var(--font-mono); --sans:var(--font-primary);
  position:relative; width:100%; font-family:var(--sans);">
  <!-- SVG canvas: axes + grid + dots (NO <text>) -->
  <svg viewBox="0 0 680 440" width="100%" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
    <!-- Quadrant fills -->
    <rect x="40" y="20"  width="290" height="200" fill="var(--focus)" opacity="0.06"/>
    <rect x="40" y="220" width="290" height="190" fill="var(--paper-2)" opacity="0.5"/>
    <rect x="330" y="20"  width="300" height="200" fill="var(--paper-2)" opacity="0.5"/>
    <rect x="330" y="220" width="300" height="190" fill="var(--paper-2)" opacity="0.3"/>
    <!-- Grid lines -->
    <line x1="40" y1="20"  x2="40"  y2="410" stroke="var(--rule)" stroke-width="1"/>
    <line x1="40" y1="410" x2="630" y2="410" stroke="var(--rule)" stroke-width="1"/>
    <!-- Axis midlines -->
    <line x1="330" y1="20" x2="330" y2="410" stroke="var(--rule)" stroke-width="1" stroke-dasharray="5,4"/>
    <line x1="40"  y1="215" x2="630" y2="215" stroke="var(--rule)" stroke-width="1" stroke-dasharray="5,4"/>
    <!-- Dots: highlighted (focus color) -->
    <circle cx="204" cy="78"  r="9" fill="var(--focus)"/>
    <circle cx="136" cy="131" r="9" fill="var(--focus)"/>
    <!-- Dots: standard (dim color) -->
    <circle cx="306" cy="100" r="7" fill="var(--rule)"/>
    <circle cx="408" cy="171" r="7" fill="var(--rule)"/>
    <circle cx="476" cy="233" r="7" fill="var(--rule)"/>
  </svg>
  <!-- HTML overlay labels (NO SVG <text>) -->
  <!-- Quadrant labels -->
  <div style="position:absolute; left:2%; top:3%; font-size:10px; font-weight:800; letter-spacing:0.12em; text-transform:uppercase; color:var(--focus);">Quick Wins</div>
  <div style="position:absolute; right:1%; top:3%; font-size:10px; font-weight:800; letter-spacing:0.12em; text-transform:uppercase; color:var(--dim);">Strategic Bets</div>
  <div style="position:absolute; left:2%; bottom:3%; font-size:10px; letter-spacing:0.10em; text-transform:uppercase; color:var(--dim);">Low Priority</div>
  <div style="position:absolute; right:1%; bottom:3%; font-size:10px; letter-spacing:0.10em; text-transform:uppercase; color:var(--dim);">High Cost / Low Return</div>
  <!-- Axis labels -->
  <div style="position:absolute; left:50%; bottom:0; transform:translateX(-50%); font-size:10px; letter-spacing:0.13em; text-transform:uppercase; color:var(--dim);">Implementation Effort →</div>
  <div style="position:absolute; left:0; top:50%; transform:translateY(-50%) rotate(-90deg); font-size:10px; letter-spacing:0.13em; text-transform:uppercase; color:var(--dim);">Business Impact →</div>
  <!-- Item labels (positioned per effort/impact) -->
  <div style="position:absolute; left:26%; top:13%; font-size:10px; font-weight:700; color:var(--focus); max-width:120px; line-height:1.3;">Automated regression scoping</div>
  <div style="position:absolute; left:15%; top:25%; font-size:10px; font-weight:700; color:var(--focus); max-width:120px; line-height:1.3;">Delivery reporting assistant</div>
  <div style="position:absolute; left:40%; top:19%; font-size:10px; color:var(--dim); max-width:100px; line-height:1.3;">Story quality gate</div>
  <div style="position:absolute; left:54%; top:34%; font-size:10px; color:var(--dim); max-width:100px; line-height:1.3;">Deployment readiness check</div>
  <div style="position:absolute; left:62%; top:47%; font-size:10px; color:var(--dim); max-width:100px; line-height:1.3;">Test data discovery</div>
</div>
```

**自检**：象限填色用 SVG `<rect>` + `opacity`（无 rgba）；十字中轴线用 `stroke-dasharray`（非 `stroke-dashoffset`）；亮点圆点走 `var(--focus)`；标准圆点走 `var(--rule)`；所有文字标注（象限名、轴标、项目标签）均为 HTML 叠加 `<div>`（**无 SVG `<text>`**）；highlighted 项目标签走 `--focus`；颜色全走契约变量。

**管线安全**：SVG 仅 `<rect>`/`<circle>`/`<line>`（无 `<text>`）；所有标注是 HTML `<div>`；`stroke-dasharray` 非 `stroke-dashoffset`；无 `mask-image`/`conic-gradient`/`mix-blend-mode`；无禁用 CSS。
