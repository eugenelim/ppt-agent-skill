# worksheet & runbook 原语（表格 / 工作表 / 清单 / 状态 / 页面骨架）-- 可签字讨论的桌面文档

> 适用数据类型：raci / responsibility_matrix / decision_worksheet / fill_in_template / schedule / day_by_day / cadence / escalation / checklist / quality_gate / failure_mode / callout / masthead / section_marker。一整套"编辑部技术文档"原语。
> 灵感基准：工程交付 Runbook / 编辑部技术文档——纯白纸面 + 粗黑顶栏/表头（实心 ink 反白 mono）+ 硬黑边框（1/2/3px solid）+ Fraunces 斜体紫强调 + 单一强调色信号。天生适配 `schematic_blueprint`（`diagram_mode:"lineart"`），但全部绑定 deck 变量，换风格随 `:root` 改色。
> 加载：非独立 `card_type`——在 `data` / `list` / `timeline` / `text` 卡上以 `resources.block_refs:["worksheet"]` 按需注入正文（与 diagram family 文件同机制）。
> 推荐 card_style：transparent（表格/工作表自带黑框骨架，外层不再套卡）。行数 4-8 为宜，超过 8 拆页。
> 管线：遵守 pipeline-compat.md —— 一律真实 `<table>` / `<div>`，禁 SVG `<text>`，禁 `mask-image` / `conic-gradient` / `background-image:url()`；颜色只用契约变量（信号色见下方碳out）。

**主题契约（根容器局部变量，映射 deck `:root`）**：每个配方根容器内联声明这一组，只此一处绑定，body 全走局部变量。
```
--rule:var(--card-border);          /* 发丝/规线 */
--th-bg:var(--text-primary);        /* 黑表头/黑条底 */
--th-fg:var(--card-bg-from);        /* 反白字 */
--zebra:var(--card-bg-to);          /* 斑马行 */
--fg:var(--text-primary); --fg-dim:var(--text-secondary);
--focus:var(--accent-1);            /* 单一强调信号（R / highlight / 焦点 / 紫左条） */
--mono:var(--font-mono); --serif:var(--font-serif-italic,var(--font-primary)); --sans:var(--font-primary);
```
**信号色碳out**：`status-block`（gate/failure）用两枚语义信号色——绿 `--ok:#1f7a3a`/`--ok-soft:#e9f5ed`、琥珀 `--warn:#b35900`/`--warn-soft:#fef3e6`。这是**唯一允许硬编码 hex 的例外**（与图表趋势色 `#22c55e`/`#ef4444` 同性质：语义恒定、非主题色），在配方根容器声明为局部变量，可被 deck `:root` 同名变量覆盖。

---

## A. 表格 & 工作表（讨论 + 排期）

### 责任矩阵 (responsibility-matrix)

**何时用**：4-8 项活动 × 多个角色，用 R/A/C/I（或 ✔/—）表明"谁对什么负责"，作为会议桌上逐格确认的讨论底稿。强调色只落在 `R`（Responsible）上——单一信号，一眼看清主责。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["worksheet"], "worksheet_kind": "responsibility_matrix",
  "columns": ["Tech Lead", "Engineer", "Client"],
  "rows": [
    {"activity": "Kickoff sign-off", "cells": ["C", "I", "A"]},
    {"activity": "Prototype build", "cells": ["A", "R", "I"]}
  ],
  "legend": {"R": "Responsible", "A": "Accountable", "C": "Consulted", "I": "Informed"}
}
```

**模板**（黑表头 + 斑马行 + R 走强调色）：
```html
<div class="worksheet raci" style="
  --rule:var(--card-border); --th-bg:var(--text-primary); --th-fg:var(--card-bg-from);
  --zebra:var(--card-bg-to); --fg:var(--text-primary); --fg-dim:var(--text-secondary);
  --focus:var(--accent-1); --mono:var(--font-mono); font-family:var(--font-primary);">
  <table style="width:100%; border-collapse:collapse; border:1px solid var(--fg); font-size:13px;
    font-variant-numeric:tabular-nums; font-feature-settings:'kern','liga','calt','tnum';">
    <thead>
      <tr style="background:var(--th-bg); color:var(--th-fg);">
        <th style="padding:9px 12px; text-align:left; font-family:var(--mono); font-size:10px;
          text-transform:uppercase; letter-spacing:0.12em; font-weight:700;">Activity</th>
        <th style="padding:9px 12px; text-align:center; width:96px; font-family:var(--mono); font-size:10px;
          text-transform:uppercase; letter-spacing:0.12em; font-weight:700;">Tech Lead</th>
        <th style="padding:9px 12px; text-align:center; width:96px; font-family:var(--mono); font-size:10px;
          text-transform:uppercase; letter-spacing:0.12em; font-weight:700;">Engineer</th>
        <th style="padding:9px 12px; text-align:center; width:96px; font-family:var(--mono); font-size:10px;
          text-transform:uppercase; letter-spacing:0.12em; font-weight:700;">Client</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding:9px 12px; border-top:1px solid var(--rule); color:var(--fg);">Prototype build</td>
        <td style="padding:9px 12px; border-top:1px solid var(--rule); text-align:center; font-family:var(--mono); font-weight:700; color:var(--fg);">A</td>
        <td style="padding:9px 12px; border-top:1px solid var(--rule); text-align:center; font-family:var(--mono); font-weight:700; color:var(--focus);">R</td>
        <td style="padding:9px 12px; border-top:1px solid var(--rule); text-align:center; font-family:var(--mono); font-weight:700; color:var(--fg-dim);">I</td>
      </tr>
      <tr style="background:var(--zebra);">
        <td style="padding:9px 12px; border-top:1px solid var(--rule); color:var(--fg);">Validation checkpoint</td>
        <td style="padding:9px 12px; border-top:1px solid var(--rule); text-align:center; font-family:var(--mono); font-weight:700; color:var(--fg);">A</td>
        <td style="padding:9px 12px; border-top:1px solid var(--rule); text-align:center; font-family:var(--mono); font-weight:700; color:var(--fg-dim);">C</td>
        <td style="padding:9px 12px; border-top:1px solid var(--rule); text-align:center; font-family:var(--mono); font-weight:700; color:var(--focus);">R</td>
      </tr>
    </tbody>
  </table>
  <div style="font-family:var(--mono); font-size:10px; color:var(--fg-dim); margin-top:9px;
    text-transform:uppercase; letter-spacing:0.10em;">
    <b style="color:var(--focus);">R</b> Responsible · <b style="color:var(--fg);">A</b> Accountable · C Consulted · I Informed</div>
</div>
```

**自检**：黑表头（`--th-bg` 实心 + `--th-fg` 反白 mono）；斑马行走 `--zebra`；`R` 唯一走 `--focus`，其余 `--fg`/`--fg-dim`；单字母表格开 `tabular-nums`；全部真实 `<table>`；颜色全走契约变量（无硬编码 hex）。

**管线安全**：真实 `<table>`；无 SVG `<text>`；无伪元素装饰；无 `mask-image`/`conic-gradient`/`background-image:url()`。

---

### 讨论工作表 (discussion-worksheet)

**何时用**：填空式模板——左列 mono 字段名、右列可填内容（含灰斜体提示），顶部浮起一个黑底 mono 标签像文件夹页签。用于把一次讨论的产出（决策记录 / 会议纪要）结构化留白，会上逐条填。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["worksheet"], "worksheet_kind": "fill_in_template",
  "tag": "TEMPLATE · DECISION RECORD", "title": "Decision record entry",
  "fields": [
    {"name": "Context", "content": "What prompted the decision — concrete, citable.", "hint": "e.g. observed N hours lost on task Y"},
    {"name": "Decision", "content": "What was chosen, and by whom."}
  ]
}
```

**模板**（浮起页签 + 字段名/内容两列）：
```html
<div class="worksheet template" style="
  --rule:var(--card-border); --tag-bg:var(--text-primary); --tag-fg:var(--card-bg-from);
  --fg:var(--text-primary); --fg-dim:var(--text-secondary); --focus:var(--accent-1);
  --mono:var(--font-mono); position:relative; background:var(--card-bg-to);
  border:2px solid var(--fg); padding:24px 28px; font-family:var(--font-primary);">
  <span style="position:absolute; top:-11px; left:24px; background:var(--tag-bg); color:var(--tag-fg);
    font-family:var(--mono); font-size:9px; font-weight:700; text-transform:uppercase;
    letter-spacing:0.16em; padding:4px 10px;">TEMPLATE · DECISION RECORD</span>
  <h4 style="font-family:var(--serif,serif); font-weight:500; font-size:18px; margin-bottom:16px; color:var(--fg);">Decision record entry</h4>
  <div style="display:grid; gap:0;">
    <div style="display:grid; grid-template-columns:140px 1fr; gap:18px; padding:10px 0; font-size:13px;">
      <span style="font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.12em;
        color:var(--focus); font-weight:700; padding-top:2px;">Context</span>
      <span style="color:var(--fg); line-height:1.5;">What prompted the decision — concrete, citable.
        <em style="display:block; color:var(--fg-dim); font-size:12px; margin-top:3px;">e.g. observed N hours lost on task Y</em></span>
    </div>
    <div style="display:grid; grid-template-columns:140px 1fr; gap:18px; padding:10px 0; border-top:1px solid var(--rule); font-size:13px;">
      <span style="font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.12em;
        color:var(--focus); font-weight:700; padding-top:2px;">Decision</span>
      <span style="color:var(--fg); line-height:1.5;">What was chosen, and by whom.</span>
    </div>
  </div>
</div>
```

**自检**：黑底 mono 页签浮在上边框（`top:-11px`）；字段名走 mono + `--focus`；提示语 `<em>` 走 `--fg-dim` 斜体；两列 `140px 1fr`；首行不加 `border-top`；颜色全走契约变量。

**管线安全**：真实 `<div>` grid；无 SVG `<text>`；无伪元素（页签是真实 `<span>`）；无禁用 CSS。

---

### 日程表 (schedule-table)

**何时用**：逐日/逐周的详细排期——每行一个时段（mono 期号）+ 任务清单（☐ 复选）+ 责任人（mono）。比 `timeline` 承载更细的"清单级"时间信息。需要"任务条 + 时间轴"的甘特图改用 diagram family 的 `gantt`。变体：行末可挂一条 `border-top:1px dashed var(--focus)` 的斜体"结束条件"脚注（即"day-card"的收尾行）。

**数据格式**：
```json
{
  "card_type": "timeline", "block_refs": ["worksheet"], "worksheet_kind": "schedule",
  "rows": [
    {"period": "DAY 1", "owner": "Engineer", "title": "Kickoff & discovery", "tasks": ["Review the workflow", "Note first blocker"], "note": "≥1 citable blocker captured."},
    {"period": "DAY 2-3", "owner": "Tech Lead", "title": "Prototype", "tasks": ["Hardcoded OK, real data not"], "highlight": true}
  ]
}
```

**模板**（发丝分隔行：期号 + 任务复选 + 责任人；highlight 行左侧强调竖条）：
```html
<div class="worksheet schedule" style="
  --rule:var(--card-border); --fg:var(--text-primary); --fg-dim:var(--text-secondary);
  --focus:var(--accent-1); --mono:var(--font-mono); border:1px solid var(--fg);
  font-family:var(--font-primary);">
  <!-- 非 highlight 行：无左条，padding-left 补偿 3px 与 highlight 行内容对齐 -->
  <div style="display:grid; grid-template-columns:110px 1fr 96px; gap:18px; align-items:start;
    padding:16px 20px 16px 23px;">
    <span style="font-family:var(--mono); font-size:11px; font-weight:700; text-transform:uppercase;
      letter-spacing:0.12em; color:var(--focus); padding-top:2px;">DAY 1</span>
    <div>
      <div style="font-family:var(--serif,serif); font-weight:500; font-size:15px; color:var(--fg); margin-bottom:6px;">Kickoff &amp; discovery</div>
      <div style="display:flex; flex-direction:column; gap:3px;">
        <span style="font-size:13px; color:var(--fg); line-height:1.5;">☐&nbsp; Review the workflow</span>
        <span style="font-size:13px; color:var(--fg); line-height:1.5;">☐&nbsp; Note first blocker</span>
      </div>
      <!-- optional "结束条件" footnote row (renders `note`) -->
      <div style="margin-top:10px; padding-top:8px; border-top:1px dashed var(--focus);
        font-size:12px; font-style:italic; color:var(--focus);">≥1 citable blocker captured.</div>
    </div>
    <span style="font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.12em;
      color:var(--fg-dim); text-align:right;">Engineer</span>
  </div>
  <div style="display:grid; grid-template-columns:110px 1fr 96px; gap:18px; align-items:start;
    padding:16px 20px; border-top:1px solid var(--rule); border-left:3px solid var(--focus);">
    <span style="font-family:var(--mono); font-size:11px; font-weight:700; text-transform:uppercase;
      letter-spacing:0.12em; color:var(--focus); padding-top:2px;">DAY 2-3</span>
    <div>
      <div style="font-family:var(--serif,serif); font-weight:500; font-size:15px; color:var(--fg); margin-bottom:6px;">Prototype</div>
      <div style="display:flex; flex-direction:column; gap:3px;">
        <span style="font-size:13px; color:var(--fg); line-height:1.5;">☐&nbsp; Hardcoded OK, real data not</span>
      </div>
    </div>
    <span style="font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.12em;
      color:var(--fg-dim); text-align:right;">Tech Lead</span>
  </div>
</div>
```

**自检**：三列 `110px 1fr 96px`；期号/责任人走 mono；标题走 serif；任务用 `☐` 复选文本；可选 `note` 用 `1px dashed var(--focus)` 斜体脚注行渲染；highlight 行左侧 `--focus` 竖条、其余无左条（`padding-left` 补偿对齐）；发丝分隔行；颜色全走契约变量。

**管线安全**：真实 `<div>` grid；`☐` 是文本字符非伪元素；无 SVG `<text>`；无 `mask-image`/`conic-gradient`/`background-image:url()`。

---

### 升级路径表 (escalation-matrix)

**何时用**：把"何时→触发条件→行动"三段式并成一张表，用于风险/升级/决策路径的桌面对照。三列 `when / trigger / action`，action 用 `--focus` 左条点亮"该做什么"。cadence（例会节奏）同结构，改列头为 `frequency / ceremony / who` 即可。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["worksheet"], "worksheet_kind": "escalation",
  "rows": [
    {"when": "WITHIN 24H", "trigger": "Access still blocked", "detail": "Day-1 ticket unresolved.", "action": "Raise to sponsor; pause the clock."}
  ]
}
```

**模板**（三列网格 + action 紫左条）：
```html
<div class="worksheet escalation" style="
  --rule:var(--card-border); --fg:var(--text-primary); --fg-dim:var(--text-secondary);
  --focus:var(--accent-1); --mono:var(--font-mono); display:grid; gap:14px; font-family:var(--font-primary);">
  <div style="display:grid; grid-template-columns:120px 1fr 1fr; gap:20px; align-items:start;
    padding:16px 20px; border:1px solid var(--fg);">
    <span style="font-family:var(--mono); font-size:10px; font-weight:700; text-transform:uppercase;
      letter-spacing:0.12em; color:var(--focus);">WITHIN 24H</span>
    <div style="font-size:13px; line-height:1.5; color:var(--fg);">
      <strong style="font-family:var(--serif,serif); font-size:15px; font-weight:500; display:block; margin-bottom:4px;">Access still blocked</strong>
      Day-1 ticket unresolved.</div>
    <div style="font-size:12.5px; line-height:1.5; color:var(--fg-dim); border-left:2px solid var(--focus); padding-left:14px;">
      <strong style="font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.12em; color:var(--fg); display:block; margin-bottom:4px;">Action</strong>
      Raise to sponsor; pause the clock.</div>
  </div>
</div>
```

**自检**：三列 `120px 1fr 1fr`；when 走 mono `--focus`；trigger 标题走 serif；action 走 `--focus` 左条 + mono 小标签；硬黑边框；颜色全走契约变量。

**管线安全**：真实 `<div>` grid；无 SVG `<text>`；无伪元素；无禁用 CSS。

---

## B. 清单 & 状态

### 清单 (checklist)

**何时用**：交付/准入清单——黑条标题 + ☐ 行（strong 主项 + 灰 span 释义）。默认白底硬黑框；准入前置版（preflight）把外层底色换成 `--focus-soft`（紫气雾）即可，其余不变。TOC 目录是它的"编号版"变体：把 `☐` 换成 mono 序号 `01`，两列排布。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["worksheet"], "worksheet_kind": "checklist",
  "title": "Hand-off checklist", "variant": "default",
  "items": [
    {"strong": "Runbook delivered", "desc": "Operating manual handed to the receiving team, reviewed live."},
    {"strong": "Access transferred", "desc": "All credentials rotated to the owning team."}
  ]
}
```

**模板**（黑条标题 + ☐ 行）：
```html
<div class="worksheet checklist" style="
  --rule:var(--card-border); --th-bg:var(--text-primary); --th-fg:var(--card-bg-from);
  --fg:var(--text-primary); --fg-dim:var(--text-secondary); --focus:var(--accent-1);
  --mono:var(--font-mono); border:1px solid var(--fg); font-family:var(--font-primary);">
  <div style="background:var(--th-bg); color:var(--th-fg); font-family:var(--mono); font-size:11px;
    text-transform:uppercase; letter-spacing:0.16em; font-weight:700; padding:12px 20px;">Hand-off checklist</div>
  <div style="display:grid; grid-template-columns:32px 1fr; gap:14px; padding:14px 20px; font-size:13px; line-height:1.5;">
    <span style="color:var(--focus); font-weight:700; font-size:18px; line-height:1.3;">☐</span>
    <span><strong style="display:block; font-family:var(--serif,serif); font-weight:500; font-size:15px; margin-bottom:3px; color:var(--fg);">Runbook delivered</strong>
      <span style="color:var(--fg-dim); font-size:12.5px;">Operating manual handed to the receiving team, reviewed live.</span></span>
  </div>
  <div style="display:grid; grid-template-columns:32px 1fr; gap:14px; padding:14px 20px; border-top:1px solid var(--rule); font-size:13px; line-height:1.5;">
    <span style="color:var(--focus); font-weight:700; font-size:18px; line-height:1.3;">☐</span>
    <span><strong style="display:block; font-family:var(--serif,serif); font-weight:500; font-size:15px; margin-bottom:3px; color:var(--fg);">Access transferred</strong>
      <span style="color:var(--fg-dim); font-size:12.5px;">All credentials rotated to the owning team.</span></span>
  </div>
</div>
```

**自检**：黑条标题走 mono 反白；`☐` 走 `--focus`；主项 serif、释义 `--fg-dim`；发丝分隔行；preflight 变体仅换外层底色为紫气雾；颜色全走契约变量。

**管线安全**：真实 `<div>` grid；`☐` 是文本字符；无 SVG `<text>`；无禁用 CSS。

---

### 状态块 (status-block — gate / failure)

**何时用**：质量门（gate，绿）与失败模式+补救（failure，琥珀）。左侧 3px 语义色竖条 + 浅语义底色，failure 用 `dashed` 分隔的"补救"行。**这是唯一使用硬编码语义信号色的原语**（见顶部信号色碳out）。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["worksheet"], "worksheet_kind": "status_block",
  "gates": [{"stage": "GATE · BUILD", "title": "Runs on real data", "criteria": "Passes on production-shaped input."}],
  "failures": [{"title": "Scope creep mid-build", "body": "New asks land after the checkpoint.", "recovery": "Re-baseline; defer to backlog."}]
}
```

**模板**（gate 绿 + failure 琥珀虚线补救）：
```html
<div class="worksheet status" style="
  --fg:var(--text-primary); --fg-dim:var(--text-secondary); --mono:var(--font-mono);
  --ok:#1f7a3a; --ok-soft:#e9f5ed; --warn:#b35900; --warn-soft:#fef3e6;
  display:grid; gap:14px; font-family:var(--font-primary);">
  <!-- quality gate (ok / green) -->
  <div style="display:grid; grid-template-columns:80px 1fr; gap:20px; padding:18px 22px;
    background:var(--ok-soft); border-left:3px solid var(--ok);">
    <span style="font-family:var(--mono); font-size:10px; font-weight:700; text-transform:uppercase;
      letter-spacing:0.12em; color:var(--ok); padding-top:3px;">GATE · BUILD</span>
    <div>
      <h4 style="font-family:var(--serif,serif); font-weight:500; font-size:15px; margin-bottom:6px; color:var(--fg);">Runs on real data</h4>
      <p style="font-size:12px; font-style:italic; color:var(--ok); margin:0;">Passes on production-shaped input.</p>
    </div>
  </div>
  <!-- failure mode (warn / amber) -->
  <div style="background:var(--warn-soft); border-left:3px solid var(--warn); padding:16px 20px;">
    <h4 style="font-family:var(--serif,serif); font-weight:500; font-size:16px; margin-bottom:6px; color:var(--warn);">Scope creep mid-build</h4>
    <p style="font-size:13px; color:var(--fg); margin-bottom:8px;">New asks land after the checkpoint.</p>
    <div style="display:grid; grid-template-columns:80px 1fr; gap:14px; padding-top:8px;
      border-top:1px dashed var(--warn); font-size:12.5px; line-height:1.5;">
      <span style="font-family:var(--mono); font-size:10px; font-weight:700; text-transform:uppercase;
        letter-spacing:0.12em; color:var(--warn); padding-top:2px;">Recovery</span>
      <span style="color:var(--fg);">Re-baseline; defer to backlog.</span>
    </div>
  </div>
</div>
```

**自检**：gate 用 `--ok`/`--ok-soft` + italic criteria；failure 用 `--warn`/`--warn-soft` + dashed 补救行；左条 3px 语义色；标题走 serif；`--ok`/`--warn` 是唯一硬编码信号 hex（可被 deck 覆盖）；其余全走契约变量。

**管线安全**：真实 `<div>` grid；无 SVG `<text>`；无伪元素；无 `mask-image`/`conic-gradient`/`background-image:url()`。

---

## C. 页面骨架（幻灯片框架 — 本风格签名）

> 这些是 `schematic_blueprint` 的"页面外框"原语，让整页读起来像一份交付手册。HTML 生成阶段可直接粘贴，把内容替换为本页数据。

### 顶栏 (masthead)

**何时用**：每页顶部的黑色 3px 顶栏——左 mono 品牌（紫方块 + `>`）、中 mono 副题、右 mono 状态。是本风格替代"四角角标"的签名骨架。

**数据格式**：无（页面骨架，直接粘贴替换文案）。

**模板**：
```html
<div class="masthead" style="
  --fg:var(--text-primary); --focus:var(--accent-1); --fg-dim:var(--text-secondary); --mono:var(--font-mono);
  border-top:3px solid var(--fg); border-bottom:1px solid var(--fg); padding:10px 0;
  display:flex; justify-content:space-between; align-items:center;
  font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.14em;">
  <span style="color:var(--fg); font-weight:700; display:flex; align-items:center; gap:9px;">
    <span style="width:12px; height:12px; background:var(--focus); display:inline-block;"></span>
    <span style="color:var(--focus); font-weight:700; margin-left:-4px;">&gt;</span>SCHEMATIC · DELIVERY RUNBOOK</span>
  <span style="color:var(--fg-dim);">Engineering Delivery Handbook</span>
  <span style="color:var(--focus); font-weight:700;">REV 2.4</span>
</div>
```

**自检**：3px 黑顶栏 + 1px 黑底线；紫方块 + `>` 紫 glyph；三段 mono 全大写；右段走 `--focus`；颜色全走契约变量。

**管线安全**：真实 `<div>`/`<span>`；紫方块是真实 `<span>` 非伪元素；无 SVG `<text>`；无禁用 CSS。

---

### 封面头 & 章节标记 (cover-header / section-marker)

**何时用**：封面头 = mono 眉标（前置紫短横）+ Fraunces 大标题（关键词 `<em>` 斜体紫）+ serif 副题 + 4 列 mono meta 网格。章节标记 = `§ NN` 序号 + mono kicker，压在一条 2px 黑规线上。

**数据格式**：无（页面骨架，直接粘贴替换文案）。

**模板**：
```html
<!-- cover header -->
<header style="--fg:var(--text-primary); --focus:var(--accent-1); --fg-dim:var(--text-secondary);
  --rule:var(--card-border); --mono:var(--font-mono); --serif:var(--font-serif-italic,serif);">
  <div style="font-family:var(--mono); font-size:11px; text-transform:uppercase; letter-spacing:0.18em;
    color:var(--focus); font-weight:700; display:flex; align-items:center; gap:12px; margin-bottom:14px;">
    <span style="width:24px; height:2px; background:var(--focus);"></span>How we actually run delivery</div>
  <h1 style="font-family:var(--serif,serif); font-weight:300; font-variation-settings:'opsz' 144;
    font-size:46px; line-height:0.98; letter-spacing:-0.03em; color:var(--fg);">
    The <em style="font-style:italic; font-weight:400; color:var(--focus);">Delivery</em> Runbook.</h1>
  <p style="font-family:var(--serif,serif); font-weight:300; font-size:16px; line-height:1.4; color:var(--fg); max-width:640px; margin-top:12px;">
    Day-by-day playbook, cadence, escalation paths, and quality gates — what the team uses, in the field.</p>
  <div style="border-top:1px solid var(--rule); margin-top:24px; padding-top:14px; display:grid;
    grid-template-columns:repeat(4,1fr); gap:16px; font-family:var(--mono); font-size:10px;
    text-transform:uppercase; letter-spacing:0.12em; color:var(--fg-dim); font-variant-numeric:tabular-nums;">
    <div>Audience<strong style="color:var(--fg); display:block; margin-top:2px;">Team &amp; leadership</strong></div>
    <div>Use<strong style="color:var(--fg); display:block; margin-top:2px;">Reference in-field</strong></div>
    <div>Length<strong style="color:var(--fg); display:block; margin-top:2px;">~18 weeks</strong></div>
    <div>Version<strong style="color:var(--fg); display:block; margin-top:2px;">1.0</strong></div>
  </div>
</header>

<!-- section marker -->
<div style="--fg:var(--text-primary); --focus:var(--accent-1); --fg-dim:var(--text-secondary); --mono:var(--font-mono);
  display:flex; align-items:baseline; gap:20px; border-top:2px solid var(--fg); padding-top:16px;">
  <span style="font-family:var(--mono); font-size:12px; font-weight:700; color:var(--focus); letter-spacing:0.1em;">§ 04</span>
  <span style="font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.18em; color:var(--fg-dim);">Responsibility</span>
</div>
```

**自检**：眉标前置 24×2px 紫短横；h1 Fraunces `opsz 144` + 单个 `<em>` 斜体紫；meta 4 列 mono + `tabular-nums`；section 序号 `§ NN` 走 `--focus`、压 2px 黑线；颜色全走契约变量。

**管线安全**：真实 `<header>`/`<div>`；紫短横是真实 `<span>`；无 SVG `<text>`；无禁用 CSS。

---

### 聚光标注 & 页脚 (spotlight-callout / footer)

**何时用**：聚光标注 = 黑底反白大字 + 4px 紫左条 + mono 标签，用于"为什么重要"这类一句定音。页脚 = 3px 黑上线 + 3 列 mono 网格（紫色 h5 小标题），收束整页。

**数据格式**：无（页面骨架，直接粘贴替换文案）。

**模板**：
```html
<!-- spotlight callout -->
<div style="--focus:var(--accent-1); --ink:var(--text-primary); --paper:var(--card-bg-from); --mono:var(--font-mono);
  position:relative; background:var(--ink); color:var(--paper); padding:28px 32px;">
  <span style="position:absolute; top:0; left:0; width:4px; height:100%; background:var(--focus);"></span>
  <div style="font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.18em;
    color:var(--focus); font-weight:700; margin-bottom:12px;">Why this matters</div>
  <p style="font-size:15px; line-height:1.55; max-width:640px; margin:0; color:var(--paper);">
    The biggest predictor of failure is starting before pre-flight is complete — every checklist item exists because skipping it cost a prior project.</p>
</div>

<!-- footer -->
<footer style="--fg:var(--text-primary); --focus:var(--accent-1); --fg-dim:var(--text-secondary); --mono:var(--font-mono);
  border-top:3px solid var(--fg); padding-top:20px; display:grid; grid-template-columns:2fr 1fr 1fr; gap:32px;
  font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.12em; color:var(--fg-dim);">
  <div style="font-family:var(--font-primary); font-size:11px; line-height:1.6; text-transform:none; letter-spacing:0;">
    <strong style="color:var(--fg); font-weight:600;">Delivery Runbook</strong> — the operating manual for a fixed-length delivery project.</div>
  <div><h5 style="font-size:10px; color:var(--focus); margin-bottom:10px; letter-spacing:0.16em; font-weight:700;">Sections</h5>
    <div style="line-height:1.8;">Pre-flight · Cadence · Gates</div></div>
  <div><h5 style="font-size:10px; color:var(--focus); margin-bottom:10px; letter-spacing:0.16em; font-weight:700;">Rev</h5>
    <div style="line-height:1.8;">2.4 · 2026</div></div>
</footer>
```

**自检**：callout 黑底 + 4px 紫左条（真实 `<span>`）+ mono 标签走 `--focus`；footer 3px 黑上线 + 3 列 + 紫 h5；颜色全走契约变量。

**管线安全**：真实 `<div>`/`<footer>`；左条/竖线是真实 `<span>` 非伪元素；无 SVG `<text>`；无禁用 CSS。

---

### 覆盖矩阵 (coverage-matrix)

**何时用**：能力/类别行 × 维度/阶段列的覆盖热力表——每格用深浅背景表示密度（空 / 低 / 高），可含计数徽章或勾号。适合能力覆盖评估、工具链映射、培训覆盖矩阵、特性对比表。需要 SDLC 相位与计数药丸的发现汇报版本，用 `block_refs:["discovery-readout"]` 的 `coverage-heatmap`。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["worksheet"],
  "brief_kind": "coverage_matrix",
  "columns": ["Dimension A", "Dimension B", "Dimension C", "Dimension D"],
  "rows": [
    {"label": "Capability 1", "cells": ["high", "medium", "empty", "high"]},
    {"label": "Capability 2", "cells": ["medium", "empty", "high", "medium"]},
    {"label": "Capability 3", "cells": ["empty", "high", "medium", "empty"]}
  ],
  "density_legend": {"high": "Strong coverage", "medium": "Partial", "empty": "Gap"}
}
```

**模板**（黑表头 + 密度背景 + 可选计数 · 全走契约变量）：
```html
<div style="
  --fg:var(--text-primary); --fg-dim:var(--text-secondary); --focus:var(--accent-1);
  --rule:var(--card-border); --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --mono:var(--font-mono); --sans:var(--font-primary);
  font-family:var(--sans); overflow-x:auto;">
  <table style="border-collapse:collapse; width:100%; font-size:11.5px; min-width:480px; font-variant-numeric:tabular-nums;">
    <thead>
      <tr>
        <th style="padding:9px 12px; background:var(--fg); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.12em; font-weight:700; text-align:left; min-width:140px;"></th>
        <th style="padding:9px 10px; background:var(--fg); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Dimension A</th>
        <th style="padding:9px 10px; background:var(--fg); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Dimension B</th>
        <th style="padding:9px 10px; background:var(--fg); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Dimension C</th>
        <th style="padding:9px 10px; background:var(--fg); color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.10em; font-weight:700; text-align:center;">Dimension D</th>
      </tr>
    </thead>
    <tbody>
      <!-- Row 1 -->
      <tr>
        <td style="padding:9px 12px; font-weight:700; color:var(--fg); border:1px solid var(--rule);">Capability 1</td>
        <!-- High density: dark bg + light text -->
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule); background:var(--fg);">
          <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--paper);">&#10003;</span>
        </td>
        <!-- Medium density: subtle bg -->
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule); background:var(--paper-2);">
          <span style="font-family:var(--mono); font-size:11px; font-weight:700; color:var(--focus);">&#10003;</span>
        </td>
        <!-- Empty: paper bg + dash -->
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule);">
          <span style="font-size:11px; color:var(--rule);">—</span>
        </td>
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule); background:var(--fg);">
          <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--paper);">&#10003;</span>
        </td>
      </tr>
      <!-- Row 2 (zebra) -->
      <tr style="background:var(--paper-2);">
        <td style="padding:9px 12px; font-weight:700; color:var(--fg); border:1px solid var(--rule);">Capability 2</td>
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule); background:var(--paper-2);">
          <span style="font-family:var(--mono); font-size:11px; font-weight:700; color:var(--focus);">&#10003;</span>
        </td>
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule);">
          <span style="font-size:11px; color:var(--rule);">—</span>
        </td>
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule); background:var(--fg);">
          <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--paper);">&#10003;</span>
        </td>
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule); background:var(--paper-2);">
          <span style="font-family:var(--mono); font-size:11px; font-weight:700; color:var(--focus);">&#10003;</span>
        </td>
      </tr>
      <!-- Row 3 -->
      <tr>
        <td style="padding:9px 12px; font-weight:700; color:var(--fg); border:1px solid var(--rule);">Capability 3</td>
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule);">
          <span style="font-size:11px; color:var(--rule);">—</span>
        </td>
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule); background:var(--fg);">
          <span style="font-family:var(--mono); font-size:11px; font-weight:800; color:var(--paper);">&#10003;</span>
        </td>
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule); background:var(--paper-2);">
          <span style="font-family:var(--mono); font-size:11px; font-weight:700; color:var(--focus);">&#10003;</span>
        </td>
        <td style="padding:9px 8px; text-align:center; border:1px solid var(--rule);">
          <span style="font-size:11px; color:var(--rule);">—</span>
        </td>
      </tr>
    </tbody>
  </table>
  <!-- Legend -->
  <div style="display:flex; gap:18px; margin-top:8px; font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.09em; color:var(--fg-dim);">
    <span><span style="display:inline-block; width:10px; height:10px; border-radius:2px; background:var(--fg); vertical-align:middle; margin-right:5px;"></span>Strong</span>
    <span><span style="display:inline-block; width:10px; height:10px; border-radius:2px; background:var(--paper-2); border:1px solid var(--rule); vertical-align:middle; margin-right:5px;"></span>Partial</span>
    <span><span style="display:inline-block; width:10px; height:10px; border-radius:2px; border:1px solid var(--rule); vertical-align:middle; margin-right:5px;"></span>Gap</span>
  </div>
</div>
```

**自检**：黑表头走 `var(--fg)` 背景 + `var(--paper)` 反白字；强覆盖格走 `var(--fg)` 背景 + `var(--paper)` 勾号；弱覆盖走 `var(--paper-2)` + `var(--focus)` 勾号；空格走 `—` + `var(--rule)` 颜色；图例用真实 `<span>` 色块；颜色全走契约变量（无 rgba/hex）。

**管线安全**：真实 `<table>`；勾号 `&#10003;` 是 HTML 字符；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

### 严重性分组发现表 (severity-findings-table)

**何时用**：按主题/类别分组呈现发现项、风险条目、审计发现或议题列表——深色 `<tr>` 行作分组标题，每行含优先级/严重性徽章。适合风险登记册、审计发现、议题追踪、质量检查日志。比 `responsibility-matrix` 更侧重"分类+优先级"而非"责任分工"。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["worksheet"],
  "brief_kind": "severity_findings_table",
  "columns": ["ID", "Area", "Severity", "Finding", "Theme"],
  "groups": [
    {
      "label": "Process",
      "rows": [
        {"id": "F-01", "area": "Planning", "severity": "High",   "finding": "No structured handoff between planning and build", "theme": "Coordination"},
        {"id": "F-02", "area": "Test",     "severity": "Medium", "finding": "Regression scope determined manually each cycle",   "theme": "Efficiency"}
      ]
    },
    {
      "label": "Tooling",
      "rows": [
        {"id": "F-03", "area": "Build", "severity": "Low", "finding": "Local dev environment setup not documented", "theme": "Onboarding"}
      ]
    }
  ]
}
```

**模板**（深色分组标题行 + 严重性徽章 · 碳out信号色声明为局部变量）：
```html
<div style="
  --sev-hi:#ef4444; --sev-med:#b35900;
  --fg:var(--text-primary); --fg-dim:var(--text-secondary);
  --rule:var(--card-border); --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --mono:var(--font-mono); --sans:var(--font-primary);
  font-family:var(--sans); overflow-x:auto;">
  <table style="border-collapse:collapse; width:100%; font-size:12px; min-width:580px;">
    <thead>
      <tr style="background:var(--fg);">
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.12em; font-weight:700; text-align:left; width:60px;">ID</th>
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left;">Area</th>
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left; width:80px;">Severity</th>
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left;">Finding</th>
        <th style="padding:9px 11px; color:var(--paper); font-family:var(--mono); font-size:9px; text-transform:uppercase; letter-spacing:0.11em; font-weight:700; text-align:left;">Theme</th>
      </tr>
    </thead>
    <tbody>
      <!-- Group header: Process -->
      <tr style="background:var(--fg);">
        <td colspan="5" style="padding:7px 11px; color:var(--paper); font-family:var(--mono); font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.13em;">Process</td>
      </tr>
      <!-- High severity row -->
      <tr style="border-bottom:1px solid var(--rule);">
        <td style="padding:9px 11px; font-family:var(--mono); font-size:10px; font-weight:700; color:var(--fg-dim);">F-01</td>
        <td style="padding:9px 11px; color:var(--fg-dim);">Planning</td>
        <td style="padding:9px 11px;">
          <span style="font-size:9px; font-weight:800; letter-spacing:0.09em; text-transform:uppercase; padding:2px 8px; border-radius:4px; color:var(--paper); background:var(--sev-hi);">High</span>
        </td>
        <td style="padding:9px 11px; font-weight:600; color:var(--fg);">No structured handoff between planning and build</td>
        <td style="padding:9px 11px; color:var(--fg-dim);">Coordination</td>
      </tr>
      <!-- Medium severity row (zebra) -->
      <tr style="background:var(--paper-2); border-bottom:1px solid var(--rule);">
        <td style="padding:9px 11px; font-family:var(--mono); font-size:10px; font-weight:700; color:var(--fg-dim);">F-02</td>
        <td style="padding:9px 11px; color:var(--fg-dim);">Test</td>
        <td style="padding:9px 11px;">
          <span style="font-size:9px; font-weight:800; letter-spacing:0.09em; text-transform:uppercase; padding:2px 8px; border-radius:4px; color:var(--paper); background:var(--sev-med);">Med</span>
        </td>
        <td style="padding:9px 11px; font-weight:600; color:var(--fg);">Regression scope determined manually each cycle</td>
        <td style="padding:9px 11px; color:var(--fg-dim);">Efficiency</td>
      </tr>
      <!-- Group header: Tooling -->
      <tr style="background:var(--fg);">
        <td colspan="5" style="padding:7px 11px; color:var(--paper); font-family:var(--mono); font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.13em;">Tooling</td>
      </tr>
      <!-- Low severity row -->
      <tr style="border-bottom:1px solid var(--rule);">
        <td style="padding:9px 11px; font-family:var(--mono); font-size:10px; font-weight:700; color:var(--fg-dim);">F-03</td>
        <td style="padding:9px 11px; color:var(--fg-dim);">Build</td>
        <td style="padding:9px 11px;">
          <span style="font-size:9px; font-weight:700; letter-spacing:0.09em; text-transform:uppercase; padding:2px 8px; border-radius:4px; border:1px solid var(--rule); color:var(--fg-dim);">Low</span>
        </td>
        <td style="padding:9px 11px; font-weight:600; color:var(--fg);">Local dev environment setup not documented</td>
        <td style="padding:9px 11px; color:var(--fg-dim);">Onboarding</td>
      </tr>
    </tbody>
  </table>
</div>
```

**自检**：全局表头 + 分组标题行走 `var(--fg)` 深色背景 + `var(--paper)` 反白字；High 徽章走 `--sev-hi`（碳out `#ef4444`）；Med 走 `--sev-med`（碳out `#b35900`）；Low 走描边款（`1px var(--rule)` + `var(--fg-dim)` 文字，无背景色）；`--sev-hi`/`--sev-med` 声明为根容器局部变量（可被 deck `:root` 覆盖）；其余颜色全走契约变量。

**管线安全**：真实 `<table>`；徽章是真实 `<span>`（非伪元素）；无 SVG `<text>`；无禁用 CSS；`--sev-hi`/`--sev-med` 是唯一碳out（与 worksheet `status-block` warn 及 `discovery-readout` 同条款）。
