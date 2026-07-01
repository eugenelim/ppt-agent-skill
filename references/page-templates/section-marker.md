# 章节标记页 -- 内联分隔（不占整页）

> 内联章节分隔：`§ NN` 序号 + mono kicker 压在一条 2px 规线上 —— 轻量分隔，**不占整页**。是 `section`（整页呼吸封面）的参考型对应物，供运行手册 / 交付手册 / SOP / playbook 这类"用来查、不是一次性读完"的 deck 在阶段边界处使用。
> 必须元素：`§ NN` 序号 + 章节 kicker + 规线；持久页眉/页脚（reference 档随时回答"我在哪、第几节"）。可选：一句 lead 交代"何时/为何用这段" + 本段首个操作制品。
> 与 `section` 的区别：`section` 是整页呼吸（visual_weight <= 3、几乎全留白、不放正文）；`section-marker` 是**分隔条领起的正文页**——顶部轻量分隔条，下方直接承接本段的 lead 与首个制品。跳读者不需要每个阶段都来一整页呼吸。
> 天生皮肤 [`schematic_blueprint`](../styles/light.md)；分隔条 / 页眉 / 页脚配方复用 [`blocks/worksheet.md`](../blocks/worksheet.md) §C。

## 何时用 section-marker，何时用整页 section

- **说服型 deck（故事弧线）**：每个 Part 首页用整页 `section` 制造呼吸点——观众线性观看，需要情绪缓冲。
- **参考型 deck（运行手册 / 生命周期时间线）**：阶段边界用内联 `section-marker`。读者跳读到自己所处的阶段，整页呼吸反而打断查阅；分隔条足够标出"新阶段开始"，同页立即进入可执行制品。
- 判据同 [`principles/narrative-arc.md` §参考型叙事](../principles/narrative-arc.md)：`叙事结构` 落在"时间线/生命周期"且内容是操作制品（模板/清单/排期/责任矩阵/质量门）→ 参考型 → `section-marker`。

## 页面结构（分隔条领起，非整页呼吸）

1. **持久页眉** `<header class="slide-header">`——masthead：品牌 + 副题 + 状态/版本。
2. **章节分隔条**——`§ NN` 序号（走 `--accent-1`）+ mono kicker，压 2px 黑规线。
3. **一句 lead**（可选）——交代"这一段何时/为何用"。
4. **首个操作制品**（可选）——本段第一个 worksheet 制品（清单 / 模板 / 排期…），按 `resources.block_refs:["worksheet"]` 注入。
5. **持久页脚** `<footer class="slide-footer">`。

## 灵动设计指引

- 分隔条是这页的锚点，但它**克制**：不做大编号背景、不占整屏。真正的信息重量在下方的 lead + 首个制品。
- 序号 `§ NN` 只点一处强调色（`--accent-1`），kicker 走次级文字色，规线走 `--card-border` 或 `--text-primary`。
- 连续多个 `section-marker` 之间保持同一分隔条造型（参考文档要的是一致的导航语言，不是每页求变）——这与 `section` 整页封面"连续两页禁止同构图"的规则相反，是参考型的刻意选择。

## 粘贴即用骨架（映射 deck CSS 变量，管线安全）

```html
<!-- 持久页眉：masthead。类名 slide-header 供合同/视觉 QA 校验持久页眉 -->
<header class="slide-header masthead" style="
  --fg:var(--text-primary); --focus:var(--accent-1); --fg-dim:var(--text-secondary); --mono:var(--font-mono);
  border-top:3px solid var(--fg); border-bottom:1px solid var(--fg); padding:10px 0;
  display:flex; justify-content:space-between; align-items:center;
  font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.14em;">
  <span style="color:var(--fg); font-weight:700; display:flex; align-items:center; gap:9px;">
    <span style="width:12px; height:12px; background:var(--focus); display:inline-block;"></span>
    <span style="color:var(--focus); font-weight:700; margin-left:-4px;">&gt;</span>DELIVERY RUNBOOK</span>
  <span style="color:var(--fg-dim);">Engineering Delivery Handbook</span>
  <span style="color:var(--focus); font-weight:700;">REV 2.4</span>
</header>

<!-- 内联章节分隔条：§ NN + kicker 压 2px 规线 -->
<div style="--fg:var(--text-primary); --focus:var(--accent-1); --fg-dim:var(--text-secondary); --mono:var(--font-mono);
  display:flex; align-items:baseline; gap:20px; border-top:2px solid var(--fg); padding-top:16px; margin-top:24px;">
  <span style="font-family:var(--mono); font-size:12px; font-weight:700; color:var(--focus); letter-spacing:0.1em;">§ 04</span>
  <span style="font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.18em; color:var(--fg-dim);">Responsibility</span>
</div>

<!-- 一句 lead：何时/为何用这段（serif 斜体收束语气） -->
<p style="font-family:var(--font-serif-italic,var(--font-primary)); font-size:16px; line-height:1.5;
  color:var(--text-primary); max-width:640px; margin:14px 0 0;">When ownership is unclear, start here — this stage fixes who is accountable before the build begins.</p>

<!-- 下方直接承接本段首个 worksheet 制品；持久页脚收束 -->
<footer class="slide-footer" style="
  --fg:var(--text-primary); --focus:var(--accent-1); --fg-dim:var(--text-secondary); --mono:var(--font-mono);
  border-top:3px solid var(--fg); padding-top:20px; margin-top:24px; display:grid; grid-template-columns:2fr 1fr 1fr; gap:32px;
  font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:0.12em; color:var(--fg-dim);">
  <div style="font-family:var(--font-primary); font-size:11px; line-height:1.6; text-transform:none; letter-spacing:0;">
    <strong style="color:var(--fg); font-weight:600;">Delivery Runbook</strong> — operating manual for a fixed-length project.</div>
  <div><h5 style="font-size:10px; color:var(--focus); margin-bottom:10px; letter-spacing:0.16em; font-weight:700;">Section</h5>
    <div style="line-height:1.8;">04 · Responsibility</div></div>
  <div><h5 style="font-size:10px; color:var(--focus); margin-bottom:10px; letter-spacing:0.16em; font-weight:700;">Rev</h5>
    <div style="line-height:1.8;">2.4 · 2026</div></div>
</footer>
```

## 唯一硬约束

- 所有颜色通过 CSS 变量引用（信号色例外见 `blocks/worksheet.md` 顶部碳out）。
- 持久页眉/页脚必须带 `slide-header` / `slide-footer` 类名——合同校验与视觉 QA 据此确认参考型的持久 chrome。
- 装饰用真实 DOM 节点：紫方块 / 规线是真实 `<span>` / `border`，禁 SVG `<text>`、禁 `mask-image` / `conic-gradient` / `background-image:url()`。
- 分隔条不占整页——它领起正文，不替代正文。要整页呼吸请改用 `section`。
