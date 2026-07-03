# 智能配图 — generate_image 提示词构造

> Step 5b 配图执行细则。仅当用户在需求调研（Step 1 第 7 题）中确认需要配图时按本文件生成；
> 配图时机与产物路径见 SKILL.md Step 5b（在生成每页 HTML 之前生成，每页至少 1 张，存入
> `OUTPUT_DIR/images/`）。

## generate_image 提示词构造公式

提示词必须同时满足 **4 个维度**，按以下公式组装：

```
[内容主题] + [视觉风格] + [画面构图] + [技术约束]
```

| 维度 | 说明 | 示例 |
|------|------|------|
| 内容主题 | 从该页策划稿 JSON 的核心概念提炼，具体到场景/对象 | "DMSO molecular purification process, crystallization flask with clear liquid" |
| 视觉风格 | 与 style.json 的配色方案和情感基调对齐 | 暗黑科技 -> "deep blue dark tech background, subtle cyan glow, futuristic" |
| 画面构图 | 根据图片在页面中的放置方式决定 | 右侧半透明 -> "clean composition, main subject on left, fade to transparent on right" |
| 技术约束 | 固定后缀，确保输出质量 | "no text, no watermark, high quality, professional illustration" |

## 风格与配图关键词对应

| PPT 风格 | 配图风格关键词 |
|---------|--------------|
| 暗黑科技 | dark tech background, neon glow, futuristic, digital, cyber |
| 小米橙 | minimal dark background, warm orange accent, clean product shot, modern |
| 蓝白商务 | clean professional, light blue, corporate, minimal, bright |
| 朱红宫墙 | traditional Chinese, elegant red gold, ink painting, cultural |
| 清新自然 | fresh green, organic, nature, soft light, watercolor |
| 紫金奢华 | luxury, purple gold, premium, elegant, metallic |
| 极简灰白 | minimal, grayscale, clean, geometric, academic |
| 活力彩虹 | colorful, vibrant, energetic, playful, gradient, pop art |

## 按页面类型调整

| 页面类型 | 图片特征 | Prompt 额外关键词 |
|---------|---------|-----------------|
| 封面页 | 主题概览，视觉冲击 | "hero image, wide composition, dramatic lighting" |
| 章节封面 | 该章主题的象征性视觉 | "symbolic, conceptual, centered composition" |
| 内容页 | 辅助说明，不喧宾夺主 | "supporting illustration, subtle, background-suitable" |
| 数据页 | 抽象数据可视化氛围 | "abstract data visualization, flowing lines, tech" |

## 禁止事项
- 禁止图片中出现文字（AI 生成的文字质量差）
- 禁止与页面配色冲突的颜色（暗色主题配暗色图，亮色主题配亮色图）
- 禁止与内容无关的装饰图（每张图必须与该页内容有语义关联）
- 禁止重复使用相同 prompt（每页图片必须独特）
