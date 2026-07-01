# 风格系统（引导文件）

> ⚠️ 本文件已被新结构取代。从 v2.0 起，风格系统从 8 种扩展到 **28 种**，按 5 板块分目录管理。

## 新位置

请改读以下文件：

| 用途 | 新位置 |
|------|-------|
| **28 风格索引 + 决策矩阵 + JSON Schema** | [`references/styles/index.md`](styles/index.md) |
| **暗色专业（7 风格）** | [`references/styles/dark.md`](styles/dark.md) |
| **浅色高级（10 风格）** | [`references/styles/light.md`](styles/light.md) |
| **活力鲜明（4 风格）** | [`references/styles/vibrant.md`](styles/vibrant.md) |
| **东方文化（3 风格）** | [`references/styles/cultural.md`](styles/cultural.md) |
| **自然/复古（4 风格）** | [`references/styles/natural.md`](styles/natural.md) |
| **排版铁律（共享）** | [`references/typography.md`](typography.md) |
| **失败模式目录** | [`references/principles/failure-modes.md`](principles/failure-modes.md) |
| **风格预览画廊** | 执行 `python3 scripts/gallery.py` → `ppt-output/style-gallery/index.html` |

## 兼容性

8 个原 `style_id`（`dark_tech` / `xiaomi_orange` / `blue_white` / `royal_red` / `fresh_green` / `luxury_purple` / `minimal_gray` / `vibrant_rainbow`）**完全保留并升级**到世界级标杆，ID 不变以保兼容。老用户的代码无需修改。

## 升级要点

新风格系统相对原 8 风格的关键改进：

1. **数量**：8 → 28（覆盖更多场景）
2. **每个风格新增字段**：
   - `mood_keywords` 情绪标签
   - `design_soul` 一句话设计灵魂
   - `variation_strategy` 跨页节奏策略
   - `decoration_dna.signature_move` 招牌动作
   - `decoration_dna.forbidden` 明确禁用
   - `decoration_dna.recommended_combos` 推荐组合
   - `typography.*` 完整字体栈 + 字距规则 + OpenType 特性
3. **每个风格附两版 1280×720 标杆 mock（封面 + 详情）**：
   - `ppt-output/style-gallery/<style_id>.cover.html` —— **封面/标题页**（身份视角）。
     画廊卡片与 hero 缩略图默认取它（见 `gallery.py` 的 `gallery_face()`）。
   - `ppt-output/style-gallery/<style_id>.html` —— **详情/内容页**（数据 / 论证 /
     表格 / 编排），spec 验收物 + 主 smoke 夹具。
   - **两版都是 `smoke_test` 夹具**，`phase1` 分别校验各自的 pipeline-compat /
     排版铁律；两版都必须 1280×720、pipeline-safe、含 `font-feature-settings`
     （出现两位以上数字再加 `tabular-nums`）。
   - **吸收 / 新增一个风格时两版一起产出**（不是先出一版事后补）：封面立身份、
     详情证内容表现，二者视觉上要明显不同（封面不含详情的 stat/card/table/chart 块）。
4. **质量参照**：Linear / Anthropic / Stripe / Apple / NYT / Tom Ford / Pitch / Mercury 等品牌的实际排版做法
