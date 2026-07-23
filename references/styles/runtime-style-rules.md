# Runtime Style Rules

> 本文件是 style-phase1 runtime 主链注入文件，包含 style.json 字段合同。

## style.json 字段合同

style.json 输出时必须包含以下字段（缺一不可）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `style_id` | string | 预置 ID 或自定义 ID（slug 格式） |
| `style_name` | string | 风格名称 |
| `mood_keywords` | string[] | 3-5 个情绪关键词 |
| `design_soul` | string | 一句话灵魂宣言（画面感通感描述） |
| `variation_strategy` | string | 跨页变奏策略（描述页间变化节奏型） |
| `decoration_dna` | object | 装饰基因（见下方） |
| `css_variables` | object | 纯色值变量（见下方合规键名） |
| `font_family` | string | 字体栈 |
| `css_snippets` | object | 固化 CSS 片段（标题/列表/正文/间距） |

### decoration_dna 结构

```json
{
  "signature_move": "最标志性装饰手法（每 3-4 页至少出现一次）",
  "forbidden": ["禁止手法列表"],
  "recommended_combos": ["推荐组合 A", "推荐组合 B"]
}
```

### css_variables 合规键名

必须且只能使用以下键名（不可自创必备项）：

```json
{
  "bg_primary": "#主背景",
  "bg_secondary": "#渐变过渡色",
  "card_bg_from": "#卡片渐变起",
  "card_bg_to": "#卡片渐变止",
  "card_border": "rgba(边框色)",
  "card_radius": "12px",
  "text_primary": "#标题/正文",
  "text_secondary": "rgba(辅助文字)",
  "accent_1": "#主强调",
  "accent_2": "#次强调",
  "accent_3": "#第三强调",
  "accent_4": "#第四强调"
}
```

## 色彩原则（硬底线）

| 原则 | 要求 |
|------|------|
| 对比度安全 | 文字与背景对比度 >= 4.5:1 |
| 60-30-10 法则 | 背景色 60%、卡片/辅助色 30%、accent 色 10% |
| accent 克制 | 同一页 accent 色不超过 2 种 |
| 深浅一致 | 深色背景配浅色文字，浅色背景配深色文字 |
| 卡片与背景区分 | 卡片背景与页面背景至少 5% 明度差 |

## 输出规则

- 输出完整的 style.json（必须包含 mood_keywords / design_soul / variation_strategy / decoration_dna，不能只有 css_variables）
- css_variables 的键名必须完全合规，不可自创必备项
- 所有颜色必须通过 CSS 变量引用
