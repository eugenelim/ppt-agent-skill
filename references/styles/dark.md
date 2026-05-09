# 暗色专业板块（7 风格）

> 板块定位：深色背景 + 高对比 + 精密科技/奢华情绪。适用于产品发布会、SaaS 平台、技术文档、奢侈品、电竞、Web3 等场景。
>
> 共享：[排版铁律](../typography.md) · [失败模式](../principles/failure-modes.md) · [Bento Grid](../bento-grid.md)

---

## 索引

| # | style_id | 灵感 | 一句话 |
|---|----------|------|-------|
| 1 | `dark_tech` | Linear.app | 天文台扫描光，深空冷寂的精密仪器感 |
| 2 | `xiaomi_orange` | Apple Keynote (硬件) | 暗夜中产品悬浮，橙光辐射的发布会感 |
| 3 | `luxury_purple` | Tom Ford | 黑金菱形装饰，YSL 级时尚奢华 |
| 4 | `nocturne_violet` | Linear (紫光版) | 紫色玻璃光晕，设计师工具的夜曲 |
| 5 | `cyberpunk_neon` | Cyberpunk 2077 | 紫青霓虹 + 扫描线，2077 未来街景 |
| 6 | `chrome_y2k` | Y2K / Vaporwave | 千禧年银色铬感 + 网格透视 |
| 7 | `noir_film` | 黑白电影 | 高反差黑白 + 胶片颗粒，纪录片质感 |

---

## 1. dark_tech — 暗黑科技

```json
{
  "style_id": "dark_tech",
  "style_name": "暗黑科技 (Dark Tech)",
  "category": "dark_professional",

  "inspiration": "Linear.app",
  "mood_keywords": ["深空冷寂", "精密仪器", "微光脉搏", "数据洪流", "未来感"],
  "design_soul": "天文台穹顶内部，深蓝黑幕中冷青的仪器扫描光有节奏地划过 -- 精密、冷寂、但每一次扫描都暗含脉搏。屏幕上的数据像星图一样精确排列。",
  "variation_strategy": "数据页用网格点阵+角标装饰线（紧张高密度），章节封面用大面积深空留白+单一光晕（释放），产品页用全屏暗底+中央悬浮发光数据面板（聚焦）。三种极端交替形成'在深空中切换仪器面板'的节奏。",

  "decoration_dna": {
    "signature_move": "网格点阵底纹 + 极光辉光（双层 radial-gradient） + Inter Tight 紧凑字距 + serif italic 关键词混排",
    "forbidden": [
      "渐变色块 (除背景微妙过渡外)",
      "叶片 / 花卉装饰",
      "波浪分隔线",
      "马卡龙糖果色",
      "serif 杂志感",
      "圆润儿童感字体"
    ],
    "recommended_combos": [
      "网格点阵 + 角标装饰 + 大号水印数字",
      "极光辉光 + 脉冲圆点 label + 半透明数字水印",
      "纤细底线 (linear-gradient transparent → cyan → transparent) + 玻璃卡片"
    ]
  },

  "background": {
    "primary": "#050b1f",
    "gradient_to": "#0a1f3d",
    "gradient_direction": "radial 100% 80% at 50% -20%",
    "texture": { "type": "grid_dot", "size": 80, "opacity": 0.015 },
    "glow": [
      { "x": "80%", "y": "30%", "color": "#6366f1", "opacity": 0.35, "blur": 60 },
      { "x": "20%", "y": "70%", "color": "#22D3EE", "opacity": 0.25, "blur": 60 }
    ]
  },

  "card": {
    "gradient_from": "rgba(34,211,238,0.08)",
    "gradient_to": "rgba(99,102,241,0.04)",
    "border": "rgba(34,211,238,0.2)",
    "border_radius": 8,
    "backdrop_blur": 10
  },

  "text": {
    "primary": "#FFFFFF",
    "secondary": "rgba(255,255,255,0.65)",
    "title_size": 28,
    "body_size": 14,
    "card_title_size": 20
  },

  "accent": {
    "primary": ["#22D3EE", "#3B82F6"],
    "secondary": ["#6366f1", "#FDE047"]
  },

  "typography": {
    "display_font": "'Inter Tight', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "body_font": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "serif_italic_font": "'Instrument Serif', 'Fraunces', Georgia, serif",
    "mono_font": "'JetBrains Mono', 'DM Mono', 'Courier New', monospace",
    "display_letter_spacing": "-0.045em",
    "headline_letter_spacing": "-0.02em",
    "body_letter_spacing": "-0.005em",
    "label_letter_spacing": "0.18em",
    "feature_settings": "'ss01', 'cv11', 'calt', 'kern', 'liga'",
    "tabular_nums": true
  },

  "decorations": {
    "label_anchor": "dot_pulse",
    "title_serif_italic": true,
    "corner_lines": true,
    "vertical_divider": false,
    "drop_cap": false,
    "masthead": false,
    "bottom_thin_line": true
  },

  "font_imports": [
    "https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;600;700;800&family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
  ]
}
```

### CSS Variables

```css
:root {
  --bg-primary: #050b1f;
  --bg-secondary: #0a1f3d;
  --card-bg-from: rgba(34,211,238,0.08);
  --card-bg-to: rgba(99,102,241,0.04);
  --card-border: rgba(34,211,238,0.2);
  --card-radius: 8px;
  --text-primary: #FFFFFF;
  --text-secondary: rgba(255,255,255,0.65);
  --accent-1: #22D3EE;
  --accent-2: #3B82F6;
  --accent-3: #6366f1;
  --accent-4: #FDE047;
  --grid-dot-color: #FFFFFF;
  --grid-dot-opacity: 0.015;
  --grid-size: 80px;
  --display-font: 'Inter Tight', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --body-font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --serif-italic-font: 'Instrument Serif', 'Fraunces', Georgia, serif;
  --mono-font: 'JetBrains Mono', 'DM Mono', 'Courier New', monospace;
}
```

### Mock HTML 标杆

完整 1280×720 mock 见 [`ppt-output/style-gallery/dark_tech.html`](../../ppt-output/style-gallery/dark_tech.html)。

---

## 2-7. 其它 6 个暗色风格

> 待 Phase 2a 批量产出。索引见本文顶部。
