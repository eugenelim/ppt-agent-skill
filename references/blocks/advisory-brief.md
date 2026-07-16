# advisory-brief 原语（论证卡 / 排序列表 / 相位流 / 诚实横幅 / 页面骨架）-- 高端顾问战略简报

> 适用数据类型：reasoning_card / claim_evidence_sowhat / precondition_list / priority_list / recommendation / phase_flow / stage_progression / pillband / projection_ramp / callout / illustrative_disclaimer / page_chrome。一整套"咨询顾问内部战略简报"原语。
> 灵感基准：高端咨询/顾问的内部战略简报 deck——石墨炭底 + 香槟古金焦点 + 尘调（去饱和）五信号。每张论证卡以一句 so-what『Therefore / Result』收束；估算数字页顶必挂红色『先读这个』诚实横幅。天生适配 `graphite_gold`，但全部绑定 deck 变量，换风格随 `:root` 改色。
> 加载：非独立 `card_type`——在 `data` / `list` / `timeline` / `text` 卡上以 `resources.block_refs:["advisory-brief"]` 按需注入正文（与 diagram family / worksheet 同机制）。
> 推荐 card_style：论证卡族自带彩条骨架，用 default（有卡框）；相位流 / 斜坡图 / 横幅用 transparent（自带结构，外层不再套卡）。
> 管线：遵守 pipeline-compat.md —— 一律真实 `<div>` / SVG `<path>`/`<line>`/`<circle>`（禁 SVG `<text>`，标注用 HTML 叠加），禁 `mask-image` / `conic-gradient` / `background-image:url()` / `background-clip:text` / `mix-blend-mode`；颜色只用契约变量（信号色见下方碳out）。

**主题契约（根容器局部变量，映射 deck `:root`）**：每个配方根容器内联声明这一组，只此一处绑定，body 全走局部变量。
```
--focus:var(--accent-1);            /* 香槟金 — 唯一主焦点信号 */
--cdot:var(--accent-1);             /* per-card 信号色，卡上 inline 覆盖（多信号 deck 每卡选一枚） */
--paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
--ink:var(--text-primary); --dim:var(--text-secondary);
--rule:var(--card-border);
--sans:var(--font-primary); --mono:var(--font-mono);
```
**信号色碳out**：诚实横幅 `illustrative-banner` 用一枚"注意/告警"语义信号色——琥珀 `--warn:#b35900` / `--warn-soft:#fef3e6`。这是**唯一允许硬编码 hex 的例外**（与图表趋势色 `#22c55e`/`#ef4444`、worksheet status-block 同性质：语义恒定、非主题色），在配方根容器声明为局部变量，可被 deck `:root` 同名变量覆盖（`graphite_gold` 可覆写为其陶红信号）。
**per-card 信号编码**：多信号 deck（如 `graphite_gold` 的金/青/蓝/紫/陶红）在每张卡 inline 写 `style="--cdot:var(--teal)"` 等选一枚信号色，驱动顶栏彩条 + 项目符号点 + 分段小标；单-accent deck 省略即全部落回 `var(--accent-1)`。
**washed 面板说明**：源 deck 的 callout / scalenote / 条件左条用 rgba 渐变洗色；提取原语改为**实色卡底 + 焦点色左条/边**（管线安全 + lint 干净）。唯一保留的渐变是页眉 `rule`（焦点色 → `transparent`）。

---

## A. 论证卡族（claim → reasoning → so-what）

### 顶栏彩条论证卡 (accent-topline-card)

**何时用**：一页 2–4 张并排的推理卡，每卡讲一个论点——卡顶一条信号彩条 + 标签/副标 + 若干 psec 分段小标领起的要点簇 + 底部 so-what netline 收束。是本风格的主力叙事卡。多卡时每卡选一枚不同信号色（`--cdot`）形成"一卡一色"编码。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["advisory-brief"], "brief_kind": "reasoning_card",
  "signal": "teal",
  "tag": "Data Pipeline Support", "subtag": "Incidents resolved faster — recurring ones prevented before they page anyone.",
  "sections": [
    {"label": "AI does the work", "role": "focus", "items": ["Agents triage, find root cause, and draft the fix."]},
    {"label": "Remove the waits", "role": "cool", "items": ["No triage backlog — failures routed the moment they land.", "No re-diagnosing — known patterns resolve automatically."]}
  ],
  "netline": {"kicker": "Result", "text": "Pipeline MTTR drops and the recurring-failure tail shrinks."}
}
```

**HTML 模板**（顶栏彩条 + psec 分段 + so-what netline）：
```html
<div class="brief-card" style="
  --cdot:var(--teal); --focus:var(--accent-1); --paper:var(--card-bg-from);
  --ink:var(--text-primary); --dim:var(--text-secondary); --rule:var(--card-border);
  --sans:var(--font-primary); background:var(--paper); border:1px solid var(--rule);
  border-radius:14px; padding:17px 18px; display:flex; flex-direction:column;
  font-family:var(--sans);">
  <div style="height:3px; border-radius:3px 3px 0 0; margin:-17px -18px 14px; background:var(--cdot);"></div>
  <div style="font-size:18px; font-weight:800; line-height:1.12; color:var(--ink);">Data Pipeline Support</div>
  <div style="font-size:12px; color:var(--dim); margin:4px 0 13px; line-height:1.3;">Incidents resolved faster — recurring ones prevented before they page anyone.</div>
  <!-- psec section 1 -->
  <div style="margin-bottom:11px;">
    <span style="display:block; font-size:10px; letter-spacing:0.14em; text-transform:uppercase; font-weight:700; margin-bottom:5px; color:var(--focus);">AI does the work</span>
    <div style="display:flex; flex-direction:column; gap:5px;">
      <span style="position:relative; padding-left:12px; font-size:11.5px; line-height:1.36; color:var(--ink);">
        <span style="position:absolute; left:0; top:6px; width:4px; height:4px; border-radius:50%; background:var(--cdot);"></span>
        Agents <b style="color:var(--ink); font-weight:700;">triage, find root cause, and draft the fix</b>.</span>
    </div>
  </div>
  <!-- psec section 2 -->
  <div style="margin-bottom:11px;">
    <span style="display:block; font-size:10px; letter-spacing:0.14em; text-transform:uppercase; font-weight:700; margin-bottom:5px; color:var(--cdot);">Remove the waits</span>
    <div style="display:flex; flex-direction:column; gap:5px;">
      <span style="position:relative; padding-left:12px; font-size:11.5px; line-height:1.36; color:var(--ink);">
        <span style="position:absolute; left:0; top:6px; width:4px; height:4px; border-radius:50%; background:var(--cdot);"></span>
        No triage backlog — failures routed the moment they land.</span>
      <span style="position:relative; padding-left:12px; font-size:11.5px; line-height:1.36; color:var(--ink);">
        <span style="position:absolute; left:0; top:6px; width:4px; height:4px; border-radius:50%; background:var(--cdot);"></span>
        No re-diagnosing — known patterns resolve automatically.</span>
    </div>
  </div>
  <!-- so-what netline -->
  <div style="margin-top:auto; padding-top:11px; border-top:1px solid var(--rule);
    font-weight:700; font-size:12.5px; line-height:1.38; color:var(--ink);">
    <span style="display:block; color:var(--focus); letter-spacing:0.05em; text-transform:uppercase; font-size:10px; margin-bottom:2px;">Result</span>
    Pipeline MTTR drops and the recurring-failure tail shrinks.</div>
</div>
```

**自检**：卡顶 3px 彩条走 `--cdot`；分段小标大写 `.14em` 字距；要点小圆点走 `--cdot`（真实 `<span>` 非伪元素）；netline 用 `margin-top:auto` 顶到卡底 + `1px var(--rule)` 上线 + 金色大写 kicker + heading 结论；多卡每卡 inline 换 `--cdot`；颜色全走契约变量。

**管线安全**：真实 `<div>`；彩条/圆点是真实 `<span>`/`<div>` 非 `::before`；无 SVG `<text>`；无 `mask-image`/`conic-gradient`/`background-image:url()`。

---

### so-what 收束行 (sowhat-netline)

**何时用**：单独复用 netline——挂在任意卡 / 面板底部，用一行金色大写 kicker（`Therefore` / `Result` / `Net` / `So what`）+ 一句 heading 字体结论，强制每段论证回答"所以呢"。本风格的论证诚实纪律。

**数据格式**：
```json
{ "brief_kind": "sowhat", "kicker": "Therefore", "text": "The CI/CD governance agent is the fastest first win — Skills-only, no DB access." }
```

**模板**（金 kicker + heading 结论 + 发丝上线）：
```html
<div style="--focus:var(--accent-1); --ink:var(--text-primary); --rule:var(--card-border);
  padding-top:11px; border-top:1px solid var(--rule); font-family:var(--font-primary);
  font-weight:700; font-size:12.5px; line-height:1.38; color:var(--ink);">
  <span style="display:block; color:var(--focus); letter-spacing:0.05em; text-transform:uppercase; font-size:10px; margin-bottom:2px;">Therefore</span>
  The CI/CD governance agent is the fastest first win — Skills-only, no DB access.</div>
```

**自检**：kicker 走 `--focus` 大写 `.05em`；结论走 heading 字体加粗；`1px var(--rule)` 发丝上线；颜色全走契约变量。

**管线安全**：真实 `<div>`；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

## B. 排序列表 & 相位带

### 优先级条件列表 (condition-list)

**何时用**：一列"必须为真 / 从哪开始"的横条，按重要性排序——`key`（焦点色左条 + 转角标签 make-or-break）在前，`minor`（虚线边、微降 opacity）在后；第二枚 make-or-break 用 `red`（陶红左条）。每条：名称（左固定列）+ 释义 + 可选转角标签。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["advisory-brief"], "brief_kind": "precondition_list",
  "rows": [
    {"name": "Leadership support", "desc": "A named sponsor who funds the 90 days and protects the team's time.", "tag": "Make-or-break", "rank": "key"},
    {"name": "The team wants it", "desc": "Genuinely interested and leaning in.", "tag": "Make-or-break", "rank": "key", "tone": "red"},
    {"name": "Day-1 access", "desc": "IDs, sandbox, repos, model-endpoint approvals — cleared early.", "rank": "minor"}
  ]
}
```

**模板**（key 金左条 + 转角标签 / red 陶红左条 / minor 虚线）：
```html
<div style="--focus:var(--accent-1); --red:var(--red); --paper:var(--card-bg-from);
  --ink:var(--text-primary); --dim:var(--text-secondary); --rule:var(--card-border);
  --sans:var(--font-primary); display:flex; flex-direction:column; gap:10px; font-family:var(--sans);">
  <!-- key row (focus/gold) -->
  <div style="display:flex; gap:16px; align-items:center; background:var(--paper);
    border:1px solid var(--rule); border-left:4px solid var(--focus); border-radius:11px; padding:13px 18px;">
    <div style="font-weight:800; font-size:15px; color:var(--ink); flex:0 0 188px; line-height:1.18;">Leadership support</div>
    <div style="font-size:13px; line-height:1.45; color:var(--ink); flex:1;">A named sponsor who <b style="color:var(--ink);">funds the 90 days</b> and protects the team's time.</div>
    <div style="flex:0 0 auto; font-size:9px; letter-spacing:0.13em; text-transform:uppercase; font-weight:800;
      padding:4px 9px; border-radius:5px; color:var(--paper); background:var(--focus);">Make-or-break</div>
  </div>
  <!-- key row (red tone) -->
  <div style="display:flex; gap:16px; align-items:center; background:var(--paper);
    border:1px solid var(--rule); border-left:4px solid var(--red); border-radius:11px; padding:13px 18px;">
    <div style="font-weight:800; font-size:15px; color:var(--ink); flex:0 0 188px; line-height:1.18;">The team wants it</div>
    <div style="font-size:13px; line-height:1.45; color:var(--ink); flex:1;">The team is <b style="color:var(--ink);">genuinely interested</b> and leaning in.</div>
    <div style="flex:0 0 auto; font-size:9px; letter-spacing:0.13em; text-transform:uppercase; font-weight:800;
      padding:4px 9px; border-radius:5px; color:var(--paper); background:var(--red);">Make-or-break</div>
  </div>
  <!-- minor row (dashed) -->
  <div style="display:flex; gap:16px; align-items:center; background:var(--paper);
    border:1px dashed var(--rule); border-radius:11px; padding:13px 18px; opacity:0.96;">
    <div style="font-weight:800; font-size:13.5px; color:var(--ink); flex:0 0 188px; line-height:1.18;">Day-1 access</div>
    <div style="font-size:13px; line-height:1.45; color:var(--ink); flex:1;">IDs, sandbox, repos, model-endpoint approvals — cleared early.</div>
  </div>
</div>
```

**自检**：按重要性排序 key→minor；key 左条 `4px var(--focus)`、red 变体左条 `var(--red)`；转角标签 heading 字体大写小胶囊 `background:var(--focus)`/`var(--red)` 反白；minor 用 `1px dashed var(--rule)` + `opacity:.96`；名称列固定 `188px`；颜色全走契约变量。

**管线安全**：真实 `<div>`；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

### 相位流 (phaseflow)

**何时用**：3–4 个前后相接的阶段（Prove → Repeat → Scale / Shadow → Enable → Harden），每列彩条顶边 + 标题 + 时间副题 + 目标斜体 + 要点，列间用箭头 `➔` 相接。承载"生命周期/演进"的横向进程。

**数据格式**：
```json
{
  "card_type": "timeline", "block_refs": ["advisory-brief"], "brief_kind": "phase_flow",
  "cols": [
    {"signal": "gold", "head": "Prove it", "when": "The 90-day pilot", "goal": "One team, one measured result.", "items": ["Hits the target metric we set together", "We walk away with a repeatable pattern"]},
    {"signal": "blue", "head": "Repeat", "when": "Next team · next stack", "goal": "Each team starts ahead of the last.", "items": ["Knowledge base + tooling carry over"]}
  ]
}
```

**模板**（彩条顶边列 + 箭头相接）：
```html
<div style="--focus:var(--accent-1); --paper:var(--card-bg-from); --ink:var(--text-primary);
  --dim:var(--text-secondary); --rule:var(--card-border); --sans:var(--font-primary);
  display:flex; align-items:stretch; gap:0; font-family:var(--sans);">
  <div style="--cdot:var(--focus); flex:1; background:var(--paper); border:1px solid var(--rule);
    border-top:3px solid var(--cdot); border-radius:12px; padding:15px 17px; display:flex; flex-direction:column;">
    <div style="font-weight:800; font-size:18px; color:var(--ink); line-height:1.1;">Prove it</div>
    <div style="font-size:11px; color:var(--focus); font-weight:600; letter-spacing:0.04em; margin:2px 0 7px;">The 90-day pilot</div>
    <div style="font-size:12px; color:var(--dim); font-style:italic; line-height:1.4; margin-bottom:11px;
      border-bottom:1px solid var(--rule); padding-bottom:10px;">One team, one measured result.</div>
    <div style="display:flex; flex-direction:column; gap:7px;">
      <span style="position:relative; padding-left:14px; font-size:12px; line-height:1.4; color:var(--ink);">
        <span style="position:absolute; left:0; top:7px; width:4px; height:4px; border-radius:50%; background:var(--cdot);"></span>
        Hits the target metric we set together.</span>
    </div>
  </div>
  <div style="display:flex; align-items:center; justify-content:center; flex:0 0 36px; color:var(--dim); font-size:24px;">&#10142;</div>
  <div style="--cdot:var(--blue); flex:1; background:var(--paper); border:1px solid var(--rule);
    border-top:3px solid var(--cdot); border-radius:12px; padding:15px 17px; display:flex; flex-direction:column;">
    <div style="font-weight:800; font-size:18px; color:var(--ink); line-height:1.1;">Repeat</div>
    <div style="font-size:11px; color:var(--focus); font-weight:600; letter-spacing:0.04em; margin:2px 0 7px;">Next team · next stack</div>
    <div style="font-size:12px; color:var(--dim); font-style:italic; line-height:1.4; margin-bottom:11px;
      border-bottom:1px solid var(--rule); padding-bottom:10px;">Each team starts ahead of the last.</div>
    <div style="display:flex; flex-direction:column; gap:7px;">
      <span style="position:relative; padding-left:14px; font-size:12px; line-height:1.4; color:var(--ink);">
        <span style="position:absolute; left:0; top:7px; width:4px; height:4px; border-radius:50%; background:var(--cdot);"></span>
        Knowledge base + tooling carry over.</span>
    </div>
  </div>
</div>
```

**自检**：每列 `border-top:3px var(--cdot)`（inline 换信号色）；时间副题走 `--focus`；目标斜体 + `1px var(--rule)` 下线；要点小圆点走 `--cdot`；箭头 `&#10142;` 走 `--dim`；颜色全走契约变量。

**管线安全**：真实 `<div>`；箭头是文本 glyph；圆点真实 `<span>`；无 SVG `<text>`；无禁用 CSS。

---

### 优先级药丸带 (pillband)

**何时用**：一条带标签的横向药丸带，把"推荐从哪开始"的 2–3 个选项排成条——每颗药丸彩条顶边 + 名称 + 释义 + 状态标签（Start here / Then here）。比 condition-list 更紧凑。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["advisory-brief"], "brief_kind": "pillband",
  "label": "Where to start — our recommendation",
  "pills": [
    {"signal": "gold", "name": "Pipeline Support", "gloss": "Fastest first win, lowest infosec risk.", "tag": "Start here"},
    {"signal": "blue", "name": "Platform Engineering", "gloss": "Strategic, but a longer arc to measure.", "tag": "Then here"}
  ]
}
```

**模板**（标签 + 彩条顶边药丸）：
```html
<div style="--focus:var(--accent-1); --paper:var(--card-bg-from); --ink:var(--text-primary);
  --dim:var(--text-secondary); --rule:var(--card-border); --sans:var(--font-primary); font-family:var(--sans);">
  <div style="font-size:10.5px; letter-spacing:0.18em; text-transform:uppercase; color:var(--focus);
    font-weight:800; margin-bottom:8px;">Where to start — our recommendation</div>
  <div style="display:grid; grid-template-columns:1fr 1fr; gap:13px;">
    <div style="--cdot:var(--focus); background:var(--paper); border:1px solid var(--rule);
      border-top:3px solid var(--cdot); border-radius:12px; padding:13px 17px;">
      <div style="font-weight:800; font-size:16px; color:var(--ink); line-height:1.1;">Pipeline Support
        <span style="font-size:9px; letter-spacing:0.13em; text-transform:uppercase; font-weight:800;
          padding:3px 8px; border-radius:5px; margin-left:6px; color:var(--paper); background:var(--cdot);">Start here</span></div>
      <div style="font-size:12px; color:var(--dim); line-height:1.36; margin-top:6px;">Fastest first win, lowest infosec risk.</div>
    </div>
    <div style="--cdot:var(--blue); background:var(--paper); border:1px solid var(--rule);
      border-top:3px solid var(--cdot); border-radius:12px; padding:13px 17px;">
      <div style="font-weight:800; font-size:16px; color:var(--ink); line-height:1.1;">Platform Engineering
        <span style="font-size:9px; letter-spacing:0.13em; text-transform:uppercase; font-weight:800;
          padding:3px 8px; border-radius:5px; margin-left:6px; color:var(--paper); background:var(--cdot);">Then here</span></div>
      <div style="font-size:12px; color:var(--dim); line-height:1.36; margin-top:6px;">Strategic, but a longer arc to measure.</div>
    </div>
  </div>
</div>
```

**自检**：标签走 `--focus` 大写 `.18em`；每颗药丸 `border-top:3px var(--cdot)`；状态小标签反白胶囊；释义走 `--dim`；颜色全走契约变量。

**管线安全**：真实 `<div>` grid；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

## C. 强调 & 页面骨架

### 焦点洗色面板 (tinted-callout)

**何时用**：一句定音的强调面板（封面共同目标 / 章末规模注脚）——实色卡底 + 焦点色 `4px` 左条 + heading 字体大字 + 可选小字脚注。源 deck 用 rgba 金/青渐变洗色，提取原语改为**实色 + 焦点左条**（管线安全）；换 `--focus` 即变主题色（金 = callout，可 inline 换 `--focus:var(--teal)` 作 scalenote 变体）。

**数据格式**：
```json
{
  "card_type": "text", "block_refs": ["advisory-brief"], "brief_kind": "callout",
  "focus": "gold",
  "text": "The shared goal: a measurable step-change in productivity — 2× or more.",
  "small": "Our investment. The number is agreed with the team, not imposed."
}
```

**模板**（实色底 + 焦点左条 + heading 大字）：
```html
<div style="--focus:var(--accent-1); --paper-2:var(--card-bg-to); --ink:var(--text-primary);
  --dim:var(--text-secondary); position:relative; background:var(--paper-2);
  border:1px solid var(--focus); border-left:4px solid var(--focus); border-radius:12px;
  padding:15px 22px; font-family:var(--font-primary); font-weight:600; font-size:19px;
  color:var(--ink); line-height:1.34;">
  The shared goal: a measurable step-change in productivity — <em style="color:var(--focus); font-style:italic;">2× or more</em>.
  <small style="display:block; font-weight:400; color:var(--dim); font-size:13px; margin-top:6px;">Our investment. The number is agreed with the team, not imposed.</small>
</div>
```

**自检**：实色卡底 `var(--paper-2)` + `4px var(--focus)` 左条；强调词 `<em>` 走 `--focus` 斜体；脚注 `<small>` 走 `--dim`；scalenote 变体仅 inline 换 `--focus:var(--teal)`；颜色全走契约变量（无 rgba）。

**管线安全**：真实 `<div>`；无伪元素；无 SVG `<text>`；无 `background-image:url()`。

---

### 诚实横幅 (illustrative-banner)

**何时用**：任何用"来自可比案例、非本客户"的**估算数字**的页面，顶部必挂——琥珀语义边 + 红色大写 `先读这个` kicker + 一句"这是形状不是承诺"。本风格的 persuasion-integrity 签名（见 `principles/narrative-arc.md`）。

**数据格式**：
```json
{
  "card_type": "text", "block_refs": ["advisory-brief"], "brief_kind": "illustrative_disclaimer",
  "kicker": "⚠ Read this first",
  "text": "These percentages are a baseline from a comparable client engagement — not the client's numbers. They show the shape of the ramp, nothing more."
}
```

**模板**（琥珀语义边 + 红 kicker）：
```html
<div style="--warn:#b35900; --warn-soft:#fef3e6; --ink:var(--text-primary);
  --paper-2:var(--card-bg-to); background:var(--paper-2); border:1px solid var(--warn);
  border-radius:10px; padding:12px 16px; font-size:13px; line-height:1.45; color:var(--ink);
  font-family:var(--font-primary);">
  <span style="font-size:11px; letter-spacing:0.14em; text-transform:uppercase; color:var(--warn);
    font-weight:800; margin-right:8px;">&#9888; Read this first</span>
  These percentages are a <b style="color:var(--ink);">baseline from a comparable client engagement — not the client's numbers</b>. They show the shape of the ramp, nothing more.</div>
```

**自检**：`--warn`/`--warn-soft` 是唯一硬编码语义信号 hex（可被 deck 覆盖为陶红）；kicker 走 `--warn` 大写 `.14em` + `⚠` glyph；正文强调 `<b>` 走 `--ink`；颜色其余全走契约变量。

**管线安全**：真实 `<div>`；`⚠` 是文本 glyph；无伪元素；无 SVG `<text>`；无禁用 CSS。

---

### 估算斜坡图 (projection-ramp)

**何时用**：一条分段上扬的面积/折线斜坡，配轴标 + 阶段点 + 下方相位卡——用于"生产力增益路线"这类**估算趋势**（务必配 `illustrative-banner`）。折线/面积用 SVG `<path>`，轴标与点标用 HTML 叠加 `<div>`（**禁 SVG `<text>`**）。

**数据格式**：
```json
{
  "card_type": "data", "block_refs": ["advisory-brief"], "brief_kind": "projection_ramp",
  "y_axis": ["0%", "20%", "40%", "60%"],
  "points": [
    {"x": "7%", "label": "Today · 0%", "signal": "violet"},
    {"x": "27%", "label": "Day 90 · ~30%", "signal": "gold"},
    {"x": "54%", "label": "~Year 1 · ~45%", "signal": "blue"},
    {"x": "94%", "label": "Year 2–3 · ~60%", "signal": "teal"}
  ]
}
```

**模板**（SVG path 斜坡 + HTML 叠加标注，无 `<text>`）：
```html
<div style="--focus:var(--accent-1); --ink:var(--text-primary); --dim:var(--text-secondary);
  --rule:var(--card-border); position:relative; width:100%; font-family:var(--font-primary);
  font-variant-numeric:tabular-nums;">
  <svg viewBox="0 0 1180 230" width="100%" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="ramp-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--focus)" stop-opacity="0.22"/>
        <stop offset="100%" stop-color="var(--focus)" stop-opacity="0.02"/>
      </linearGradient>
    </defs>
    <line x1="50" y1="193" x2="1150" y2="193" stroke="var(--rule)" stroke-width="0.7"/>
    <line x1="50" y1="141" x2="1150" y2="141" stroke="var(--rule)" stroke-width="0.7"/>
    <line x1="50" y1="89" x2="1150" y2="89" stroke="var(--rule)" stroke-width="0.7"/>
    <line x1="50" y1="37" x2="1150" y2="37" stroke="var(--rule)" stroke-width="0.7"/>
    <line x1="50" y1="193" x2="1150" y2="193" stroke="var(--focus)" stroke-width="1.4" stroke-dasharray="7,5" opacity="0.5"/>
    <path d="M85,193 C250,193 250,115 320,115 C540,115 540,89 640,89 C1000,89 1000,42 1110,42 L1110,193 L85,193 Z" fill="url(#ramp-fill)"/>
    <path d="M85,193 C250,193 250,115 320,115 C540,115 540,89 640,89 C1000,89 1000,42 1110,42" fill="none" stroke="var(--focus)" stroke-width="3" stroke-linecap="round"/>
    <circle cx="85" cy="193" r="6" fill="var(--focus)"/>
    <circle cx="320" cy="115" r="6" fill="var(--focus)"/>
    <circle cx="640" cy="89" r="6" fill="var(--focus)"/>
    <circle cx="1110" cy="42" r="6" fill="var(--focus)"/>
  </svg>
  <!-- HTML overlay labels (NO SVG <text>) -->
  <div style="position:absolute; left:1.5%; top:2%; font-size:11px; color:var(--dim);">60%</div>
  <div style="position:absolute; left:1.5%; bottom:16%; font-size:11px; color:var(--dim);">0%</div>
  <div style="position:absolute; left:5%; bottom:-4%; font-size:11px; color:var(--dim);">Today</div>
  <div style="position:absolute; left:24%; bottom:-4%; font-size:11px; color:var(--focus); font-weight:700;">Day 90 · ~30%</div>
  <div style="position:absolute; left:52%; bottom:-4%; font-size:11px; color:var(--focus); font-weight:700;">~Year 1 · ~45%</div>
  <div style="position:absolute; right:1%; bottom:-4%; font-size:11px; color:var(--focus); font-weight:700;">Year 2–3 · ~60%</div>
</div>
```

**自检**：折线/面积用 SVG `<path>`（stroke/fill 走 `var(--focus)` + 渐变 `stop-color:var(--focus)`）；轴标 / 点标 / 阶段名一律 HTML 叠加 `<div>`（**无 `<text>`**）；基线用 `stroke-dasharray`（非 dashoffset）；数字开 `tabular-nums`；颜色全走契约变量。

**管线安全**：SVG 仅 `<path>`/`<line>`/`<circle>`/`<linearGradient>`；**无 SVG `<text>`**；标注是 HTML `<div>`；无 `mask-image`/`conic-gradient`/`stroke-dashoffset`。

---

### 页眉页脚骨架 (page-chrome)

**何时用**：每页的框——页眉 `topbar`（左 eyebrow 金色大写 + H2 标题，右 brand 灰 + 反白品牌名）+ 金渐变 `rule` 分隔；页脚 `pagefoot` 贴底两段大写点码（左品牌 · 右页码 `NN / NN`）。让整页读起来像一份顾问文件。

**数据格式**：无（页面骨架，直接粘贴替换文案）。

**模板**（topbar + 金渐变 rule + pagefoot）：
```html
<!-- topbar -->
<div style="--focus:var(--accent-1); --ink:var(--text-primary); --dim:var(--text-secondary);
  display:flex; align-items:flex-end; justify-content:space-between; margin-bottom:6px; font-family:var(--font-primary);">
  <div>
    <div style="font-size:12px; letter-spacing:0.22em; text-transform:uppercase; color:var(--focus); font-weight:600; margin-bottom:6px;">01 · The approach</div>
    <div style="font-size:31px; font-weight:700; line-height:1.1; letter-spacing:-0.01em; color:var(--ink);">AI-Native SDLC</div>
  </div>
  <div style="font-weight:700; font-size:13px; letter-spacing:0.04em; color:var(--dim);"><b style="color:var(--ink);">Acme</b> Program</div>
</div>
<!-- gold-gradient rule (only surviving gradient) -->
<hr style="height:2px; background:linear-gradient(90deg, var(--accent-1), transparent); margin:9px 0 15px; border:0;">
<!-- pagefoot -->
<div style="--dim:var(--text-secondary); display:flex; justify-content:space-between;
  font-size:11px; letter-spacing:0.18em; text-transform:uppercase; color:var(--dim);
  font-family:var(--font-primary); font-variant-numeric:tabular-nums;">
  <span>Acme · 90-Day Program · internal</span><span>03 / 07</span></div>
```

**自检**：eyebrow 走 `--focus` 大写 `.22em`；H2 走 heading 收紧字距；brand 灰 + `<b>` 反白；rule 是唯一保留的渐变（`var(--accent-1)` → `transparent`）；pagefoot 两段大写点码 `.18em` + `tabular-nums`；颜色全走契约变量。

**管线安全**：真实 `<div>`/`<hr>`；无伪元素；无 SVG `<text>`；`transparent` 是关键字非命名色；无禁用 CSS。

---

### 带标签的概念卡 (tagged-initiative-card)

**何时用**：单张或网格排列的概念/举措/能力卡——标题 + 可选简述 + 底部类型/分类徽章行。无容器约束，可独立使用于任何布局：2×3 网格展示机会组合、`three-column` 版式的每格方案概念、`l-shape` 版式的主区域能力清单。比 `discovery-readout` 的 `stage-mapped-insight-card`（含 SDLC 阶段药丸）更轻量通用；比 `stage-concept-band`（相位带）更小粒度。

**数据格式**：
```json
{
  "card_type": "list", "block_refs": ["advisory-brief"],
  "brief_kind": "tagged_initiative_card",
  "cards": [
    {
      "title": "Automated quality gate",
      "description": "Validate completeness and acceptance criteria coverage before requirements are baselined.",
      "tags": [{"label": "Process"},{"label": "AI", "highlight": true}],
      "cdot": "var(--accent-1)"
    },
    {
      "title": "Delivery reporting assistant",
      "description": "AI-generated delivery status summaries synthesised from project data.",
      "tags": [{"label": "AI", "highlight": true},{"label": "Tooling"}],
      "cdot": "var(--accent-2)"
    }
  ]
}
```

**HTML 模板**（2×N 卡网格，每卡：左边框 cdot + 标题 + 简述 + 底部标签行）：
```html
<div style="
  --focus:var(--accent-1); --ink:var(--text-primary); --dim:var(--text-secondary);
  --rule:var(--card-border); --paper:var(--card-bg-from); --paper-2:var(--card-bg-to);
  --sans:var(--font-primary);
  display:grid; grid-template-columns:1fr 1fr; gap:12px; font-family:var(--sans);">

  <!-- Card 1 (cdot = accent-1) -->
  <div style="--cdot:var(--accent-1); background:var(--paper); border:1px solid var(--rule); border-left:4px solid var(--cdot); border-radius:10px; padding:14px 16px; display:flex; flex-direction:column;">
    <div style="font-weight:800; font-size:13.5px; line-height:1.25; color:var(--ink); margin-bottom:7px;">Automated quality gate</div>
    <div style="font-size:12px; line-height:1.5; color:var(--dim); flex:1; margin-bottom:10px;">Validate completeness and acceptance criteria coverage before requirements are baselined.</div>
    <div style="display:flex; flex-wrap:wrap; gap:4px;">
      <span style="font-size:9px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:2px 8px; border-radius:4px; border:1px solid var(--rule); color:var(--dim); background:var(--paper);">Process</span>
      <span style="font-size:9px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:2px 8px; border-radius:4px; border:1px solid var(--cdot); color:var(--cdot); background:var(--paper);">AI</span>
    </div>
  </div>

  <!-- Card 2 (cdot = accent-2) -->
  <div style="--cdot:var(--accent-2); background:var(--paper); border:1px solid var(--rule); border-left:4px solid var(--cdot); border-radius:10px; padding:14px 16px; display:flex; flex-direction:column;">
    <div style="font-weight:800; font-size:13.5px; line-height:1.25; color:var(--ink); margin-bottom:7px;">Delivery reporting assistant</div>
    <div style="font-size:12px; line-height:1.5; color:var(--dim); flex:1; margin-bottom:10px;">AI-generated delivery status summaries synthesised from project data.</div>
    <div style="display:flex; flex-wrap:wrap; gap:4px;">
      <span style="font-size:9px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:2px 8px; border-radius:4px; border:1px solid var(--cdot); color:var(--cdot); background:var(--paper);">AI</span>
      <span style="font-size:9px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:2px 8px; border-radius:4px; border:1px solid var(--rule); color:var(--dim); background:var(--paper);">Tooling</span>
    </div>
  </div>

  <!-- Single-column wide card (span full grid) -->
  <div style="--cdot:var(--accent-1); grid-column:1/-1; background:var(--paper-2); border:1px solid var(--rule); border-left:4px solid var(--cdot); border-radius:10px; padding:14px 16px; display:flex; align-items:center; gap:16px;">
    <div style="flex:1;">
      <div style="font-weight:800; font-size:13.5px; line-height:1.25; color:var(--ink); margin-bottom:5px;">Environment provisioning automation</div>
      <div style="font-size:12px; line-height:1.5; color:var(--dim);">Eliminate manual steps from developer environment setup with infrastructure-as-code templates.</div>
    </div>
    <div style="display:flex; flex-wrap:wrap; gap:4px; flex-shrink:0;">
      <span style="font-size:9px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:2px 8px; border-radius:4px; border:1px solid var(--rule); color:var(--dim); background:var(--paper);">Automation</span>
      <span style="font-size:9px; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; padding:2px 8px; border-radius:4px; border:1px solid var(--rule); color:var(--dim); background:var(--paper);">Tooling</span>
    </div>
  </div>

</div>
```
> 复制规律：每张卡声明 `--cdot:var(--accent-N)` 局部变量，左边框和高亮标签均引用 `var(--cdot)`——换色仅改该声明；网格宽度由外层 `grid-template-columns` 控制（`1fr 1fr` / `repeat(3,1fr)` / `1fr` 均可）；`grid-column:1/-1` 让单张卡横跨整行。

**自检**：每卡 `--cdot` 局部变量独立声明；左边框 `4px solid var(--cdot)`；高亮标签走 `border:1px solid var(--cdot); color:var(--cdot)`（描边，非实心底）；普通标签走 `var(--rule)` 边框 + `var(--dim)` 文字；标签是真实 `<span>`（非伪元素）；颜色全走契约变量（无 rgba/hex）。

**管线安全**：真实 `<div>` grid；标签是真实 `<span>`；无伪元素装饰内容；无 SVG `<text>`；无禁用 CSS。
