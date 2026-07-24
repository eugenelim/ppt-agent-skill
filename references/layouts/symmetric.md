# 对称双栏版式 (50/50)

> 2 列内容并列。
> 空间划分建议：1fr 1fr 列。左右 50/50 等量对峙。
> 适用数据：before_after / phase_split / two_tracks / parallel_workstreams（两类平等内容）。
> **有明确立场的 A vs B 对比（谁更好 / 推荐方案）仍用 `comparison` 块；本版式用于无立场的并列。**

适用：两类并列概念（现状 vs 目标、两条服务线、两期计划）

---

## 默认实现：统一列面板（推荐）

**并列内容优先使用 `columnar-panel` 块（`block_refs: ["columnar-panel"]`）的 C 组双列版，而非两个独立卡片。**

统一列面板：
- 单一外框容器（`border:1px solid var(--rule); border-radius:10px; overflow:hidden`）
- 两列间只用 `border-right:1px solid var(--rule)` 分隔，右列无右边框
- 每列内一个 `col-header`（大写 + 2px accent 色底边）
- 两列各自可选不同的 accent 色（左 `var(--focus)` / 右 `var(--secondary)`）

具体 HTML 骨架见 [`blocks/columnar-panel.md`](../blocks/columnar-panel.md) C 组（两列面板）。

### 反 AI 感铁律 —— 禁止两个独立等宽描边卡片并排

> 两个 `border + border-radius` 的等宽卡片左右对称 = 最无聊的默认布局。
> 替代：统一面板内部竖线分隔，或刻意拉开两侧视觉重量制造"形式对称、重力偏心"的张力。

---

## 灵动化指引

### "对称"不等于"一模一样"

- 两列共享外框，但内部可以拉开差异：左列内容丰满（多项目 + 徽章 + section-label），右列内容稀疏（大号核心数据 + 一句话）
- 列头色可以左 `var(--focus)` / 右 `var(--secondary)`，制造微妙的颜色调性差异
- 内容密度不对称：左多右少，或左结构化列表、右叙述性段落

### 何时仍用两个独立卡片

- 两列中有一列需要 `accent` / `elevated` 强调（该列独立拔高，另一列退为 `outline` / `filled`）
- 内容结构差异极大（一侧含大图 / diagram，另一侧纯文本）

### 重力倾斜技法

统一面板内部，虽然空间 50/50，但可以：
- 让左列字号更大、内容更丰满，右列字号略小、内容留白更多
- 右列的 col-header 用 `var(--secondary)` 降调，暗示"右列是补充"

### 等列分配

两列由 `display:grid; grid-template-columns:1fr 1fr` 控制，不需要写 `grid-row` / `grid-column`。如需不对等分割（如 60/40），在 `grid-template-columns` 处调整为 `3fr 2fr` 即可。
