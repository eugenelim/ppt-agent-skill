# 暗色专业板块（9 风格）

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
| 8 | `graphite_gold` | 高端顾问简报（黄昏会议室） | 石墨炭底 + 香槟金焦点 + 尘调五信号，克制的战略简报 |
| 9 | `graphite_violet` | 工程交付演讲（深夜作战室） | 近纯黑底 + 石墨紫焦点 + 技术四色相位，开发者交付简报 |

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

Cover (title/identity hero): [`ppt-output/style-gallery/dark_tech.cover.html`](../../ppt-output/style-gallery/dark_tech.cover.html) — "Intelligence, at the edge." hero + 3 stats + gauge.

Detail (content/data): [`ppt-output/style-gallery/dark_tech.html`](../../ppt-output/style-gallery/dark_tech.html) — edge node health matrix: 4 KPI metric cards + 6-row component layer status table with status badges.

---

---

## 2. xiaomi_orange — 小米橙（升级版）

```json
{
  "style_id": "xiaomi_orange",
  "style_name": "小米橙 (Xiaomi Orange)",
  "category": "dark_professional",
  "inspiration": "Apple Keynote (硬件发布会版)",
  "mood_keywords": ["产品舞台", "暗夜悬浮", "橙光辐射", "金属光感"],
  "design_soul": "暗夜中的产品舞台，金属橙色光球从右下角升起，把整个画面染成温暖的火焰色。",
  "variation_strategy": "封面用中央悬浮产品光球（最强冲击），规格页用 3 张暗黑数据卡 + 右下橙光辐射，对比页用左右对称的产品阴影投射。",
  "decoration_dna": {
    "signature_move": "金属橙色产品光球（多层 radial-gradient + 内高光 + 投影）+ 底部橙光辐射 + Inter Tight 紧凑字距",
    "forbidden": ["紫色 / 蓝色 accent", "马卡龙糖果色", "serif 杂志感", "渐变色块", "波浪线"],
    "recommended_combos": ["产品光球 + 橙光辐射 + 大数字 tabular-nums", "暗夜底 + 角标线 + 金属球反光"]
  },
  "background": {
    "primary": "#0a0a0a",
    "gradient_to": "#1a1a1a",
    "gradient_direction": "radial 70% 100% at 70% 100%",
    "texture": { "type": "vignette", "opacity": 0.3 },
    "glow": [{ "x": "70%", "y": "100%", "color": "#FF6900", "opacity": 0.4, "blur": 80 }]
  },
  "card": { "gradient_from": "#1a1a1a", "gradient_to": "#0a0a0a", "border": "rgba(255,105,0,0.2)", "border_radius": 8, "backdrop_blur": 0 },
  "text": { "primary": "#FFFFFF", "secondary": "rgba(255,255,255,0.65)", "title_size": 28, "body_size": 14, "card_title_size": 20 },
  "accent": { "primary": ["#FF6900", "#ff9d4a"], "secondary": ["#FFFFFF", "#ffd16b"] },
  "typography": {
    "display_font": "'Inter Tight', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "body_font": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "serif_italic_font": "'Instrument Serif', 'Fraunces', Georgia, serif",
    "mono_font": "'JetBrains Mono', 'DM Mono', 'Courier New', monospace",
    "display_letter_spacing": "-0.045em",
    "headline_letter_spacing": "-0.02em",
    "body_letter_spacing": "-0.005em",
    "label_letter_spacing": "0.22em",
    "feature_settings": "'ss01', 'cv11', 'calt', 'kern', 'liga'",
    "tabular_nums": true
  },
  "decorations": { "label_anchor": "dot_pulse", "title_serif_italic": true, "corner_lines": true, "vertical_divider": false, "drop_cap": false, "masthead": false, "bottom_thin_line": true },
  "font_imports": ["https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;600;700;800&family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"]
}
```

Cover: [`ppt-output/style-gallery/xiaomi_orange.cover.html`](../../ppt-output/style-gallery/xiaomi_orange.cover.html) — "让性能不再设限" launch hero + 3 orange-glow stat cards.

Detail: [`ppt-output/style-gallery/xiaomi_orange.html`](../../ppt-output/style-gallery/xiaomi_orange.html) — performance benchmark matrix: 3-generation product comparison table (compute, battery, camera specs) with orange accent highlights.

---

## 3. luxury_purple — 紫金奢华（YSL 级重做）

```json
{
  "style_id": "luxury_purple",
  "style_name": "紫金奢华 (Luxury, Tom Ford-grade)",
  "category": "dark_professional",
  "inspiration": "Tom Ford / The Row / YSL Beauty",
  "mood_keywords": ["极致黑金", "对称仪式", "Didot 巨字", "时装周"],
  "design_soul": "纯黑墨幕中央，金色 Didot 巨字以对称姿态悬浮，金线与菱形装饰像高定服装上的纽扣。",
  "variation_strategy": "封面用 Didot 巨字居中 + 金线菱形装饰，章节页用 4 个角的金色 L 线 + Maison label，内容页用左右对称的双栏 + 金线分割。",
  "decoration_dna": {
    "signature_move": "Playfair/Didot italic 巨字 + 金线 + 金色菱形 + 居中对称布局 + 0.65em 字距 Maison label",
    "forbidden": ["sans serif 主标题", "渐变文字", "霓虹色", "活泼装饰", "圆角过大", "亮色背景"],
    "recommended_combos": ["金线 + 金色菱形 + 对称居中", "Didot 巨字 + 大字距小标 + 极简留白"]
  },
  "background": { "primary": "#060606", "gradient_to": "#0a0a0a", "texture": { "type": "none" } },
  "card": { "gradient_from": "rgba(201,169,96,0.04)", "gradient_to": "rgba(201,169,96,0.01)", "border": "rgba(201,169,96,0.2)", "border_radius": 0, "backdrop_blur": 0 },
  "text": { "primary": "#f5e8c8", "secondary": "rgba(245,232,200,0.55)", "title_size": 124, "body_size": 14, "card_title_size": 16 },
  "accent": { "primary": ["#c9a960", "#f5e8c8"], "secondary": ["#1a1a1a", "#fff"] },
  "typography": {
    "display_font": "'Playfair Display', 'Bodoni Moda', 'Didot', Georgia, serif",
    "body_font": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "serif_italic_font": "'Playfair Display', 'Didot', serif",
    "mono_font": "'JetBrains Mono', 'Courier New', monospace",
    "display_letter_spacing": "-0.005em",
    "headline_letter_spacing": "0",
    "body_letter_spacing": "0",
    "label_letter_spacing": "0.65em",
    "feature_settings": "'kern', 'liga', 'dlig', 'swsh'",
    "tabular_nums": true
  },
  "decorations": { "label_anchor": "horizontal_line", "title_serif_italic": true, "corner_lines": true, "vertical_divider": true, "drop_cap": false, "masthead": false, "centered_symmetric": true },
  "font_imports": ["https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Inter:wght@300;400;500;600&display=swap"]
}
```

Cover: [`ppt-output/style-gallery/luxury_purple.cover.html`](../../ppt-output/style-gallery/luxury_purple.cover.html) — "Æternum" pure serif italic title in gold on black.

Detail: [`ppt-output/style-gallery/luxury_purple.html`](../../ppt-output/style-gallery/luxury_purple.html) — collection performance analysis: two-column editorial layout with KPI stats grid + 5-collection sell-through table and gold bar indicators.

---

## 4. nocturne_violet — 紫光夜曲（新增）

```json
{
  "style_id": "nocturne_violet",
  "style_name": "紫光夜曲 (Nocturne Violet)",
  "category": "dark_professional",
  "inspiration": "Linear.app (紫色版) / 设计师工具",
  "mood_keywords": ["夜曲玻璃", "紫色辉光", "设计师工具", "玻璃态卡片"],
  "design_soul": "深紫黑夜里，紫色辉光像星云一样浮动，玻璃态卡片在光晕中折射出微妙的紫色光影。",
  "variation_strategy": "封面用大紫色辉光 + 玻璃徽章，数据页用玻璃态卡片承载关键指标，章节页用紫光大留白。",
  "decoration_dna": {
    "signature_move": "紫色 radial-gradient 辉光 + 玻璃态卡片 (backdrop-filter blur + rgba 紫色边框) + Inter Tight + Editorial New italic 关键词",
    "forbidden": ["青色 / 蓝色 accent (与 dark_tech 区分)", "橙色 (与 xiaomi_orange 区分)", "霓虹色", "传统装饰"],
    "recommended_combos": ["紫光辉光 + 玻璃卡片 + 网格底纹", "脉冲圆点 label + 玻璃徽章 + 进度环"]
  },
  "background": {
    "primary": "#0a0612",
    "gradient_to": "#1a0d2e",
    "gradient_direction": "radial 100% 80% at 50% -20%",
    "texture": { "type": "grid_dot", "size": 80, "opacity": 0.015 },
    "glow": [
      { "x": "75%", "y": "30%", "color": "#9b64ff", "opacity": 0.4, "blur": 60 },
      { "x": "20%", "y": "70%", "color": "#6d3df0", "opacity": 0.25, "blur": 60 }
    ]
  },
  "card": { "gradient_from": "rgba(155,100,255,0.10)", "gradient_to": "rgba(155,100,255,0.04)", "border": "rgba(155,100,255,0.30)", "border_radius": 12, "backdrop_blur": 18 },
  "text": { "primary": "#FFFFFF", "secondary": "rgba(255,255,255,0.65)", "title_size": 28, "body_size": 14, "card_title_size": 20 },
  "accent": { "primary": ["#9b64ff", "#c4a8ff"], "secondary": ["#6d3df0", "#FDE047"] },
  "typography": {
    "display_font": "'Inter Tight', 'Inter', -apple-system, sans-serif",
    "body_font": "'Inter', -apple-system, sans-serif",
    "serif_italic_font": "'Instrument Serif', 'Fraunces', Georgia, serif",
    "mono_font": "'JetBrains Mono', 'DM Mono', 'Courier New', monospace",
    "display_letter_spacing": "-0.045em",
    "headline_letter_spacing": "-0.02em",
    "body_letter_spacing": "-0.005em",
    "label_letter_spacing": "0.18em",
    "feature_settings": "'ss01', 'cv11', 'calt', 'kern', 'liga', 'ccmp'",
    "tabular_nums": true
  },
  "decorations": { "label_anchor": "dot_pulse", "title_serif_italic": true, "corner_lines": true, "vertical_divider": false, "drop_cap": false, "masthead": false, "glass_card": true, "bottom_thin_line": true },
  "font_imports": ["https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;600;700;800&family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"]
}
```

Cover: [`ppt-output/style-gallery/nocturne_violet.cover.html`](../../ppt-output/style-gallery/nocturne_violet.cover.html) — "Designed for the dreamers" hero + glassmorphism stat badges.

Detail: [`ppt-output/style-gallery/nocturne_violet.html`](../../ppt-output/style-gallery/nocturne_violet.html) — product usage & reliability report: 4 glass KPI cards with tier breakdown bars + feature rollout matrix, purple aurora background.

---

## 5. cyberpunk_neon — 赛博霓虹（新增）

```json
{
  "style_id": "cyberpunk_neon",
  "style_name": "赛博霓虹 (Cyberpunk Neon)",
  "category": "dark_professional",
  "inspiration": "Cyberpunk 2077 / 攻壳机动队 / Blade Runner 2049",
  "mood_keywords": ["紫青霓虹", "扫描线", "故障美学", "2077 街景"],
  "design_soul": "2077 年的夜色街道，青色霓虹和品红光斑交错闪烁，扫描线在屏幕上滚动，每个文字都像电视故障一样有双色错位。",
  "variation_strategy": "封面用 glitch 巨字 + 扫描线，数据页用切角科幻盒子 + 霓虹边框，章节页用大号像素艺术装饰。",
  "decoration_dna": {
    "signature_move": "扫描线 (repeating-linear-gradient) + glitch 文字 (双色 text-shadow 错位) + clip-path 切角科幻盒子 + 霓虹文字辉光 (text-shadow 大量)",
    "forbidden": ["serif 字体 (用 mono)", "传统圆角", "暖橙色", "金色 accent (那是 luxury 的)", "微妙渐变"],
    "recommended_combos": ["扫描线 + glitch 标题 + 切角盒子", "霓虹辉光 + 像素艺术 + mono 字体"]
  },
  "background": { "primary": "#0a0014", "gradient_to": "#1a0020", "texture": { "type": "scanlines", "opacity": 0.02 } },
  "card": { "gradient_from": "rgba(255,0,200,0.08)", "gradient_to": "rgba(0,255,255,0.04)", "border": "#ff00c8", "border_radius": 0, "backdrop_blur": 0 },
  "text": { "primary": "#FFFFFF", "secondary": "rgba(255,255,255,0.65)", "title_size": 152, "body_size": 14, "card_title_size": 18 },
  "accent": { "primary": ["#00ffff", "#ff00c8"], "secondary": ["#ffd60a", "#ff3b3b"] },
  "typography": {
    "display_font": "'Orbitron', 'JetBrains Mono', 'DM Mono', 'Courier New', monospace",
    "body_font": "'JetBrains Mono', 'DM Mono', 'Courier New', monospace",
    "serif_italic_font": "'Instrument Serif', Georgia, serif",
    "mono_font": "'JetBrains Mono', 'DM Mono', 'Courier New', monospace",
    "display_letter_spacing": "-0.035em",
    "headline_letter_spacing": "-0.01em",
    "body_letter_spacing": "0",
    "label_letter_spacing": "0.30em",
    "feature_settings": "'kern', 'liga', 'calt', 'ss01', 'cv11', 'ccmp'",
    "tabular_nums": true
  },
  "decorations": { "label_anchor": "horizontal_line", "title_serif_italic": false, "corner_lines": false, "vertical_divider": false, "drop_cap": false, "masthead": false, "scanlines": true, "glitch_text": true, "clip_path_corners": true },
  "font_imports": ["https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600&display=swap"]
}
```

Cover: [`ppt-output/style-gallery/cyberpunk_neon.cover.html`](../../ppt-output/style-gallery/cyberpunk_neon.cover.html) — "JACK IN" glitch hero + HUD scan panels + scanlines.

Detail: [`ppt-output/style-gallery/cyberpunk_neon.html`](../../ppt-output/style-gallery/cyberpunk_neon.html) — threat matrix HUD: dual CVE/anomaly tables with CVSS scores and colour-coded severity, + sector event breakdown panel.

---

## 6. chrome_y2k — 千禧铬感（新增）

```json
{
  "style_id": "chrome_y2k",
  "style_name": "千禧铬感 (Chrome Y2K)",
  "category": "dark_professional",
  "inspiration": "Y2K / Vaporwave / Apple iPod (2001) / Daft Punk",
  "mood_keywords": ["银色铬感", "千禧未来", "网格透视", "镭射光泽"],
  "design_soul": "千禧年的电子梦境，银色铬感金属球漂浮在蓝紫渐变中，地平线上的网格无限延伸，标题闪烁着镭射的银光。",
  "variation_strategy": "封面用居中镭射文字 + 双侧金属球 + 透视网格地平线，规格页用银色卡片 + 蓝色 accent。",
  "decoration_dna": {
    "signature_move": "镭射银色渐变文字 (linear-gradient clip text) + 银色金属球 (多层 radial-gradient) + SVG 透视网格地平线 + 千禧年光泽",
    "forbidden": ["哑光纯色", "暖色 (橙黄红)", "serif 字体", "传统装饰"],
    "recommended_combos": ["镭射文字 + 金属球 + 网格地平线", "银色卡片 + 蓝色 accent + mono 元数据"]
  },
  "background": { "primary": "#0a0518", "gradient_to": "#1a0d3a", "gradient_direction": "linear 180deg", "texture": { "type": "starfield", "opacity": 0.05 } },
  "card": { "gradient_from": "rgba(192,208,224,0.08)", "gradient_to": "rgba(160,160,232,0.04)", "border": "rgba(0,212,255,0.3)", "border_radius": 4, "backdrop_blur": 10 },
  "text": { "primary": "#e0e8f0", "secondary": "rgba(224,232,240,0.6)", "title_size": 132, "body_size": 14, "card_title_size": 18 },
  "accent": { "primary": ["#c0d0e0", "#00d4ff"], "secondary": ["#ff6bcd", "#a0a0e8"] },
  "typography": {
    "display_font": "'Inter Tight', 'Orbitron', 'Inter', sans-serif",
    "body_font": "'Inter', -apple-system, sans-serif",
    "serif_italic_font": "'Instrument Serif', Georgia, serif",
    "mono_font": "'JetBrains Mono', 'DM Mono', 'Courier New', monospace",
    "display_letter_spacing": "-0.045em",
    "headline_letter_spacing": "-0.02em",
    "body_letter_spacing": "-0.005em",
    "label_letter_spacing": "0.55em",
    "feature_settings": "'ss01', 'cv11', 'calt', 'kern', 'liga', 'ccmp'",
    "tabular_nums": true
  },
  "decorations": { "label_anchor": "horizontal_line", "title_serif_italic": false, "corner_lines": false, "vertical_divider": false, "drop_cap": false, "masthead": false, "centered_symmetric": true, "chrome_text": true, "metal_orbs": true, "perspective_grid": true },
  "font_imports": ["https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;600;700;800&family=Orbitron:wght@500;700;900&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"]
}
```

Cover: [`ppt-output/style-gallery/chrome_y2k.cover.html`](../../ppt-output/style-gallery/chrome_y2k.cover.html) — "DIGITAL FUTURE" chrome-text hero + silver orbs + perspective grid.

Detail: [`ppt-output/style-gallery/chrome_y2k.html`](../../ppt-output/style-gallery/chrome_y2k.html) — AX-2026 system spec sheet: 4-column technical datasheet (processor, memory/storage, display/GPU, connectivity/AI) with Orbitron headers and silver-on-dark palette.

---

## 7. noir_film — 黑白胶片（新增）

```json
{
  "style_id": "noir_film",
  "style_name": "黑白胶片 (Noir Film)",
  "category": "dark_professional",
  "inspiration": "Magnum Photos / Henri Cartier-Bresson / 杜可风 / 苏珊桑塔格",
  "mood_keywords": ["黑白对比", "胶片颗粒", "纪录片质感", "杂志胶片标签"],
  "design_soul": "暗房里的相纸缓慢显影，纯黑底色上浮现出高反差的白色文字和胶片元数据，颗粒感细腻而克制。",
  "variation_strategy": "封面用大号 sans + serif italic 关键词 + 胶片元数据，章节页用极简单线分割 + 序号，内容页用胶片接片墙感。",
  "decoration_dna": {
    "signature_move": "SVG turbulence noise 胶片颗粒 + 胶片元数据 chip (mono font) + L 形角标 + 单色调（无任何彩色 accent）",
    "forbidden": ["任何彩色 accent (青/橙/金/紫/红/绿)", "渐变背景", "圆角大于 4px", "霓虹效果", "卡通元素"],
    "recommended_combos": ["黑底白字 + 胶片颗粒 + 元数据 chip 排", "L 角标 + 接片墙 + 单线分割"]
  },
  "background": { "primary": "#0a0a0a", "gradient_to": "#0a0a0a", "texture": { "type": "film_grain", "opacity": 0.06 } },
  "card": { "gradient_from": "rgba(250,250,250,0.04)", "gradient_to": "transparent", "border": "rgba(250,250,250,0.08)", "border_radius": 0, "backdrop_blur": 0 },
  "text": { "primary": "#fafafa", "secondary": "rgba(250,250,250,0.5)", "title_size": 96, "body_size": 14, "card_title_size": 18 },
  "accent": { "primary": ["#fafafa", "#5a5a5a"], "secondary": ["#2a2a2a", "#9a9a9a"] },
  "typography": {
    "display_font": "'Inter Tight', 'Helvetica Neue', -apple-system, sans-serif",
    "body_font": "'Inter', -apple-system, sans-serif",
    "serif_italic_font": "'Source Serif 4', 'Fraunces', 'Iowan Old Style', Georgia, serif",
    "mono_font": "'JetBrains Mono', 'DM Mono', 'Courier New', monospace",
    "display_letter_spacing": "-0.045em",
    "headline_letter_spacing": "-0.02em",
    "body_letter_spacing": "-0.005em",
    "label_letter_spacing": "0.30em",
    "feature_settings": "'ss01', 'cv11', 'calt', 'kern', 'liga', 'ccmp'",
    "tabular_nums": true
  },
  "decorations": { "label_anchor": "horizontal_line", "title_serif_italic": true, "corner_lines": true, "vertical_divider": true, "drop_cap": false, "masthead": false, "film_grain": true, "film_metadata_chips": true, "monochrome_only": true },
  "font_imports": ["https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;600;700;800;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;1,8..60,400&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"]
}
```

Cover: [`ppt-output/style-gallery/noir_film.cover.html`](../../ppt-output/style-gallery/noir_film.cover.html) — "The City Awakens" photo-essay cover + film metadata chips.

Detail: [`ppt-output/style-gallery/noir_film.html`](../../ppt-output/style-gallery/noir_film.html) — urban light evidence report: two-column monochrome editorial essay + fieldwork data stats + contact sheet film-frame grid, strict monochrome palette.

---

## 8. graphite_gold — 石墨金（高端顾问简报 · 黄昏会议室）

> 视觉基准：高端咨询/顾问的**内部战略简报** deck——石墨炭灰底（带一丝紫青冷调）+ 香槟/古金焦点 + 一整套**尘调（去饱和）五信号**（茶青 / 钢蓝 / 陶红 / 薰衣草紫）。没有任何霓虹或高饱和主色，全场"安静的奢华"。
>
> 与既有暗色风格的区别：`dark_tech`/`cyberpunk_neon` 用冷青/霓虹高饱和；`luxury_purple`/`nocturne_violet` 是单一紫的品牌奢华；`noir_film` 是纯黑白单色；`champagne_gold` 是**浅色**婚庆风。本风格是唯一的"暗底 + 暖金 + 尘调多信号"顾问简报皮肤。成套论证卡/条件列表/相位流原语见 [`blocks/advisory-brief.md`](../blocks/advisory-brief.md)。

```json
{
  "style_id": "graphite_gold",
  "style_name": "石墨金 (Graphite Gold)",
  "category": "dark_professional",
  "inspiration": "高端咨询顾问内部战略简报 · 石墨炭底 + 香槟古金 + 尘调五信号",
  "mood_keywords": ["石墨炭底", "香槟金焦点", "尘调五信号", "顾问克制", "黄昏会议室"],
  "design_soul": "黄昏时分的董事会议室：石墨灰的墙面吸掉了所有喧哗，一束香槟金的光落在唯一要看的那句结论上，四种褪了色的信号色像旧铜、旧青、旧陶、旧紫一样各自安静地标注着一列论证——克制、笃定，每张卡片都以一句『所以』收束。",
  "variation_strategy": "封面居中大标题（关键词香槟金 + em 强调）+ 金渐变规线；论证页用『顶栏彩条 + per-card 信号点 + psec 分段小标 + 底部 so-what netline』的推理卡网格；条件页用 key/minor 排序的横条列表（转角标签 + 金/红左条渐变）；相位页用彩条顶边的列 + 箭头相位流；数据页用尘调面积斜坡图 + 相位卡；插图/估算页顶部必挂红色『先读这个』诚实横幅。",
  "decoration_dna": {
    "signature_move": "卡片顶部 3px 信号彩条（per-card --cdot 驱动彩条 + 项目符号点）+ 底部 so-what『Therefore / Result』收束行（金色大写 kicker + heading 字体结论）+ 金渐变规线 + 尘调五信号在暗底上作单点信号",
    "forbidden": ["高饱和/霓虹主色", "冷青科技风扫描光", "多主色平分画面（信号色只作 ≤~200px² 点缀）", "浅色/白纸背景", "厚重投影", "圆角 > 16px"],
    "recommended_combos": ["顶栏彩条卡 + psec 分段小标 + so-what netline", "key/minor 条件列表 + 转角标签 + 金/红左条", "尘调面积斜坡图 + 相位卡 + 红色诚实横幅"]
  },
  "background": { "primary": "#111118", "gradient_to": "#16161f", "texture": { "type": "grid_dot", "size": 80, "opacity": 0.015 } },
  "card": { "gradient_from": "#1c1d28", "gradient_to": "#21222f", "border": "#2C2D3A", "border_radius": 14, "backdrop_blur": 0 },
  "text": { "primary": "#ECECF2", "secondary": "#9A9BA8", "title_size": 52, "body_size": 14, "card_title_size": 18 },
  "accent": { "primary": ["#D4A96E", "#B98E4E"], "secondary": ["#6DBEA3", "#7BB4CC"] },
  "typography": {
    "display_font": "'Sora', 'Inter Tight', -apple-system, sans-serif",
    "body_font": "'DM Sans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    "serif_italic_font": "'Sora', Georgia, serif",
    "mono_font": "'JetBrains Mono', 'DM Mono', 'SF Mono', monospace",
    "display_letter_spacing": "-0.02em",
    "headline_letter_spacing": "-0.01em",
    "body_letter_spacing": "0em",
    "label_letter_spacing": "0.22em",
    "feature_settings": "'kern', 'liga', 'calt', 'tnum'",
    "tabular_nums": true
  },
  "decorations": { "label_anchor": "horizontal_line", "title_serif_italic": false, "corner_lines": false, "vertical_divider": false, "drop_cap": false, "masthead": false, "accent_topline": true, "netline_sowhat": true },
  "font_imports": ["https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&display=swap"]
}
```

**尘调五信号色**（去饱和信号色，暗底上作 per-card 单点信号 —— 非 accent，保持"香槟金唯一焦点"纪律）：`--gold:#D4A96E`（焦点 / 主信号）· `--gold-deep:#B98E4E`（深金）· `--teal:#6DBEA3` · `--blue:#7BB4CC` · `--red:#D46B6B`（也用作『先读这个』诚实横幅）· `--violet:#9B8BD4` · `--ink:#ECECF2` · `--muted:#9A9BA8` · `--line:#2C2D3A` · `--card:#1c1d28` · `--card-2:#21222f`。五信号色各自恒定语义（一列 = 一色），像图表趋势色一样是本风格允许的信号 hex；每张卡通过 `--cdot` 选一色驱动顶栏彩条 + 项目符号点，副色只作 ≤~200px² 点缀。

### 样式细则（styling spec）—— 让生成页"像一份顾问战略简报"

> 风格 JSON 只给粗粒度的色/字/字距；下面这套细则才是让整页读起来克制、笃定、"安静奢华"的关键。HTML 生成阶段照此施工。

1. **顶栏彩条卡（signature move）**：内容卡 `border-radius:14px` + `1px var(--line)` 边，卡顶贴一条 `3px` 的信号彩条（`.topline`，`margin:-padding` 顶满卡宽，圆角 `3px 3px 0 0`）。彩条颜色 = 该卡 `--cdot` 的信号色。一页多卡时，每卡选一枚不同信号色（金 / 青 / 蓝 / 紫 / 陶红），彩条 + 卡内项目符号点 + psec 小标同色，形成"一卡一色"的编码。
2. **so-what netline（signature move）**：每张论证卡底部用 `margin-top:auto` 顶到卡底、`border-top:1px var(--line)` 起一条收束行——先一行金色大写 kicker（`Therefore` / `Result` / `Net`，`font-size:10px letter-spacing:.05em`），下面一句 heading 字体的结论（`~12.5px`，暖白 `#EFE3CC`）。这是本风格的"论证诚实"纪律：每张卡都要回答"所以呢"。
3. **psec 分段推理小标**：卡内正文按语义分 2–3 段，每段一枚大写小标（`.sl2`，`10px letter-spacing:.14em`）领起一簇要点。小标用语义色区分角色——如 `AI 做的事`=金、`移除等待`=蓝、`结论`=……；要点用无序 `ul.sb`（小圆点 `--cdot`）。
4. **单一香槟金焦点纪律**：金色（`--gold`）只落在——眉标、金渐变规线、标题 `<em>` 强调词、netline kicker、条件列表 key 左条、callout 边、pblabel、页脚。尘调副信号（青/蓝/陶/紫）只在 per-card 编码与图表里出现，不与金争焦点；一页金色出现点 ≤ ~6 处。
5. **金渐变规线**：页眉下压一条 `height:2px; background:linear-gradient(90deg, var(--gold), transparent); border:0` 的规线——从金到透明，是"顾问文件页眉"的签名分隔。（唯一保留的渐变；其余 rgba 洗色面板在提取原语里改为实色 + 左条，见 `blocks/advisory-brief.md`。）
6. **页眉/页脚 chrome**：页眉 `.topbar` 左侧 eyebrow（金色大写 `.22em` 字距）+ H2 标题，右侧 `.brand`（灰 + `<b>` 反白品牌名）；页脚 `.pagefoot` 绝对定位贴底，两段 mono 感的大写点码（`11px letter-spacing:.18em`，暗灰 `#54556a`）——左品牌·右页码 `NN / NN`。
7. **色彩角色**：`--gold`（焦点 / 主信号 / kicker）· `--gold-deep`（深金）· `--teal`/`--blue`/`--violet`（per-card 副信号，冷侧）· `--red`（陶红：make-or-break 条件左条 + 诚实横幅）· `--ink`（主文字）· `--muted`（次要 / 页脚）· `--line`（发丝边 / 分隔）· `--card`/`--card-2`（卡底 / 副底 / 斑马）。
8. **数字全站 tabular**：`font-variant-numeric:tabular-nums` + `font-feature-settings:'kern','liga','calt','tnum'`——页码 / 百分比 / 天数逐列对齐。
9. **间距节奏**：整页 `padding:38px clamp(34px,4.6vw,78px) 56px`；卡片 `padding:17px 18px`；网格 `gap:16px`；正文 `line-height:1.46` + `max-width:~90ch`；导语 `p.lead`/`p.flowintro` 略大一档（16px）。
10. **条件列表排序纪律**：`.cond` 横条列表按重要性排序——`key`（金左条 + 金渐变底 + 转角标签"Make-or-break"）在前，`minor`（虚线边、微降 opacity）在后；make-or-break 的第二条用 `red`（陶红左条）。转角 `.ctag` 是 heading 字体的大写小胶囊。
11. **诚实横幅（persuasion-integrity）**：任何用"来自可比案例、非本客户"的估算数字的页面，顶部必挂 `.illbanner`（陶红边 + 红色大写 `先读这个` kicker），一句话讲清"这是形状不是承诺"。见 [`principles/narrative-arc.md`](../principles/narrative-arc.md) 的 so-what / 诚实横幅约定。

Mock: [`ppt-output/style-gallery/graphite_gold.html`](../../ppt-output/style-gallery/graphite_gold.html) · 组件原语: [`blocks/advisory-brief.md`](../blocks/advisory-brief.md)

---

## 9. graphite_violet — 石墨紫（工程交付简报 · 深夜作战室）

> 视觉基准：工程/技术交付演讲的**内部推进 deck**——近纯黑底 + 石墨紫焦点 + 一整套**技术四色相位信号**（翠绿 / 琥珀 / 天蓝 / 玫红）。去掉金色温度，换成冷静的紫色聚焦；相位编码替代顾问论证信号；JetBrains Mono 贯穿数字与代码。
>
> 与 `graphite_gold` 的关系：同属 graphite 家族（grid-dot 底纹、3px 顶栏彩条、页框 chrome），但 graphite_gold 是"顾问黄昏暖金"，graphite_violet 是"工程深夜冷紫"。相位信号取代金色焦点；三相位 roadmap / 三柱骨架 / 技术层矩阵是本风格的原语套件（原语分布于 [`diagram-process-flow.md`](../blocks/diagram-process-flow.md)、[`diagram-concept.md`](../blocks/diagram-concept.md)、[`diagram-architecture.md`](../blocks/diagram-architecture.md)）。

```json
{
  "style_id": "graphite_violet",
  "style_name": "石墨紫 (Graphite Violet)",
  "category": "dark_professional",
  "inspiration": "工程交付演讲 · 近纯黑底 + 石墨紫焦点 + 三相位技术四色",
  "mood_keywords": ["深夜作战室", "石墨紫焦点", "三相位编码", "开发者克制", "相位门控"],
  "design_soul": "深夜的工程作战室：近纯黑的屏幕上只有一条石墨紫的光线精准落在下一个里程碑上。三相位的颜色带——翠绿启动、琥珀加速、紫色复利——像进度条一样无声地告知距离目标还有多远。不华丽，但每一个数字都有位置，每一个里程碑都有颜色。",
  "variation_strategy": "封面用紫色渐变规线 + 三相位信号圆点预告；三柱骨架页用等宽三列 + 信号色标题 + 图标圆圈；相位 roadmap 页用水平相位带 + 菱形门 + 里程碑点列表；技术层矩阵页用行标题 + 工具格列；数据页用相位面积图 + 紫色聚焦数字。",
  "decoration_dna": {
    "signature_move": "3px 相位顶栏彩条（--cdot 驱动翠绿/琥珀/天蓝/玫红/紫）+ 菱形相位门（SVG polygon）+ 里程碑点列表 + 紫色渐变规线 + JetBrains Mono 数字",
    "forbidden": ["香槟金/暖金 accent（那是 graphite_gold 的领地）", "高饱和/霓虹主色（用柔化后的石墨紫）", "冷青扫描光（与 dark_tech 区分）", "渐变色块背景", "浅色/白纸背景", "圆角 > 16px"],
    "recommended_combos": ["三相位带 + 菱形门 + 里程碑点", "三柱骨架 + 信号色标题 + currentColor 图标", "技术层矩阵 + 相位徽章 + 紫色聚焦列"]
  },
  "background": { "primary": "#0a0a0a", "gradient_to": "#0f0f14", "texture": { "type": "grid_dot", "size": 80, "opacity": 0.018 }, "glow": [{ "x": "78%", "y": "18%", "color": "#7B54F5", "opacity": 0.18, "blur": 80 }] },
  "card": { "gradient_from": "#0d0d0d", "gradient_to": "#111115", "border": "#1e1e28", "border_radius": 12, "backdrop_blur": 0 },
  "text": { "primary": "#EDEDF0", "secondary": "#8B8C9B", "title_size": 48, "body_size": 14, "card_title_size": 17 },
  "accent": { "primary": ["#7B54F5", "#A37EFB"], "secondary": ["#3FC882", "#E8924A"] },
  "typography": {
    "display_font": "'Inter Tight', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "body_font": "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif",
    "serif_italic_font": "'Instrument Serif', 'Fraunces', Georgia, serif",
    "mono_font": "'JetBrains Mono', 'DM Mono', 'SF Mono', monospace",
    "display_letter_spacing": "-0.03em",
    "headline_letter_spacing": "-0.015em",
    "body_letter_spacing": "0em",
    "label_letter_spacing": "0.20em",
    "feature_settings": "'kern', 'liga', 'calt', 'tnum', 'ss01'",
    "tabular_nums": true
  },
  "decorations": { "label_anchor": "horizontal_line", "title_serif_italic": false, "corner_lines": false, "vertical_divider": false, "drop_cap": false, "masthead": false, "accent_topline": true, "phase_diamond_gate": true },
  "font_imports": ["https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"]
}
```

**技术四色相位信号**（三相位 + 附加信号，暗底上作 per-card 单点信号）：`--violet:#7B54F5`（焦点 / 主信号 / 复利相位）· `--violet-hi:#A37EFB`（浅紫高亮）· `--emerald:#3FC882`（翠绿：基础相位 / 成功）· `--amber:#E8924A`（琥珀：加速相位 / 警示）· `--sky:#4DB8EC`（天蓝：知识 / 信息）· `--rose:#E85476`（玫红：风险 / 阻断）· `--ink:#EDEDF0`（主文字）· `--muted:#8B8C9B`（次要 / 页脚）· `--line:#1e1e28`（发丝边 / 分隔）· `--card:#0d0d0d`（卡底）。相位各有恒定语义：翠绿=基础期、琥珀=加速期、紫=复利期；卡片通过 `--cdot` 选色驱动顶栏彩条 + 里程碑点。

### 样式细则（styling spec）—— 让生成页"像一份工程交付简报"

> graphite_violet 与 graphite_gold 共享 graphite 家族骨架（grid-dot、3px 顶栏彩条、页框 chrome、tabular-nums），但以工程感替换顾问感：紫替金、相位带替论证卡、JetBrains Mono 替 DM Sans 数字。

1. **3px 相位顶栏彩条（signature move）**：内容卡 `border-radius:12px` + `1px var(--line)` 边，卡顶贴 `3px` 彩条（`.topline`，圆角 `3px 3px 0 0`，满卡宽）。彩条颜色 = 该卡 `--cdot`（翠绿/琥珀/天蓝/玫红/紫）。一页多卡时每卡取一色，彩条 + 卡内里程碑点同色，形成相位编码。
2. **紫色渐变规线（signature move）**：页眉下压 `height:2px; background:linear-gradient(90deg, var(--violet), transparent); border:0`——从紫到透明，是本风格的签名分隔（对应 graphite_gold 的金渐变规线）。
3. **菱形相位门**：相位带之间插入 SVG `<polygon>` 菱形（12×12，fill=var(--violet)，opacity 0.6）+ 两侧水平线 + `.gate-label` 文字（10px，letter-spacing:.14em，大写，--muted 色）。见 [`diagram-process-flow.md`](../blocks/diagram-process-flow.md) 的 phase-band-roadmap 模板。
4. **三相位带布局**：每相位 `.phase-band` 用 `4px border-left` in `--cdot` 色 + `.phase-badge`（相位徽章小胶囊：padding 4px 10px，border-radius 999px，背景 rgba(--cdot, 0.12)，字色 --cdot）+ `.phase-name`（Inter Tight 14px 600）+ 里程碑点列表（`.m-dot` 6px 圆，颜色 = `--cdot`）。
5. **三柱骨架**：三列 `flex-1`，每列顶部 `64×64` 图标圆（`stroke-only SVG`，viewBox 0 0 48 48，外环 `circle r=22` rgba(--cdot, 0.10) fill + rgba(--cdot, 0.25) stroke）+ 信号色 `<h3>`（color=--cdot）+ 收益点列表。图标 `currentColor` 继承列容器的 `color`。
6. **单一紫色焦点纪律**：`--violet` 只落在——眉标、紫色规线、标题 `<strong>` 强调词、相位复利带顶栏、callout 边、页脚品牌。相位副信号（翠绿/琥珀/天蓝/玫红）只在 per-card 编码与图表里出现；一页紫色出现点 ≤ ~6 处。
7. **技术层矩阵**：`display:grid; grid-template-columns: 120px 1fr` 的行布局，每行 `.layer-row`（行标题 Inter Tight 11px letter-spacing:.18em 大写 + 工具格 flex-wrap）。工具格 `.tool-chip`（6px 8px padding，border-radius 6px，1px --line 边，13px mono 字）。见 [`diagram-architecture.md`](../blocks/diagram-architecture.md) 的 tech-layer-matrix 模板。
8. **JetBrains Mono 作数字/代码**：所有指标数字（百分比、天数、版本号）用 `--mono` 字体 + tabular-nums；代码段、命令行、工具名优先 mono。
9. **页眉/页脚 chrome**（同 graphite_gold 结构）：页眉 `.topbar` 左侧眉标（紫色 `--violet` 大写 `.20em` 字距）+ H2 标题；右侧 `.brand`（灰 + `<b>` 反白品牌名）；页脚 `.pagefoot` 贴底两端 mono 感大写点码（11px letter-spacing:.18em，暗灰 `--muted`）。
10. **间距节奏**：整页 `padding:40px 60px 52px`；卡片 `padding:16px 18px`；网格 `gap:16px`；正文 `line-height:1.48`。
11. **诚实横幅（persuasion-integrity）**：基准数字来自公开参考案例（非当前客户）时，顶部挂 `.illbanner`（玫红 `--rose` 边 + 大写 kicker）。

Cover mock: [`ppt-output/style-gallery/graphite_violet.cover.html`](../../ppt-output/style-gallery/graphite_violet.cover.html)
Detail mock: [`ppt-output/style-gallery/graphite_violet.html`](../../ppt-output/style-gallery/graphite_violet.html) · 组件原语: [`diagram-process-flow.md`](../blocks/diagram-process-flow.md) / [`diagram-concept.md`](../blocks/diagram-concept.md) / [`diagram-architecture.md`](../blocks/diagram-architecture.md)
