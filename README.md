# PPT Agent Skill

**[English](README_EN.md)**

> 模仿万元/页级别 PPT 设计公司的完整工作流，输出**世界级**高质量 HTML 演示文稿 + 可编辑矢量 PPTX。
>
> 风格水准对标 **Linear / Anthropic / Stripe / Apple / NYT / Tom Ford / Pitch / Mercury / Vercel** 等顶级品牌的实际排版做法。

## 工作流概览

```
需求调研 → 资料搜集 → 大纲策划 → 策划稿 → 风格+配图+HTML设计稿 → 后处理(SVG+PPTX)
```

## 效果展示

> 以「新一代小米SU7发布」为主题的示例输出（小米橙风格）：

| 封面页 | 配置对比页 |
|:---:|:---:|
| ![封面页](ppt-output/png/slide_01_cover.png) | ![配置对比](ppt-output/png/slide_02_models.png) |

| 动力续航页 | 智驾安全页 |
|:---:|:---:|
| ![动力续航](ppt-output/png/slide_03_power.png) | ![智驾安全](ppt-output/png/slide_04_smart.png) |

| 结束页 |
|:---:|
| ![结束页](ppt-output/png/slide_05_end.png) |


## 核心特性

| 特性 | 说明 |
|------|------|
| **6步Pipeline** | 需求 → 搜索 → 大纲 → 策划 → 设计 → 后处理，模拟专业 PPT 公司工作流 |
| **26 种世界级风格** | 5 板块覆盖 ｜ Linear / Anthropic / Stripe / Apple / NYT / Tom Ford 等品牌实际排版做法 |
| **18 种数据可视化** | 基础 8 种 + 进阶 6 种 + ECharts 级 4 种（世界地图/关系网络/桑基/热力日历）|
| **Bento Grid 布局** | 7 种卡片式灵活布局，内容驱动版式 |
| **世界级排版系统** | 7 级字号阶梯 + 字距铁律 + tabular-nums + OpenType 特性 + serif italic 混排 + 字体栈三层降级 |
| **智能配图** | AI 生成配图 + 5 种视觉融入技法（渐隐融合/色调蒙版/氛围底图等） |
| **失败模式目录** | 8 种 failure modes（underfill / support_collapse / decorative_substitution 等）+ 修复顺序铁律 |
| **跨页叙事** | 密度交替节奏 / 章节色彩递进 / 封面-结尾呼应 / 渐进揭示 |
| **风格预览画廊** | `gallery.py` 一键生成 26 风格卡片墙索引页 |
| **smoke 测试体系** | `smoke_test.py` 校验 26 风格 JSON + pipeline-compat + 排版铁律 |
| **PPTX 兼容** | HTML → SVG → PPTX 管线，PPT 365 中右键"转换为形状"即可编辑 |

## 输出产物

| 文件 | 说明 |
|------|------|
| `preview.html` | 浏览器翻页预览（自动生成） |
| `presentation.pptx` | PPTX 文件，PPT 365 中右键"转换为形状"可编辑 |
| `svg/*.svg` | 单页矢量 SVG，可直接拖入 PPT |
| `slides/*.html` | 单页 HTML 源文件 |

## 环境依赖

**必须：**
- **Node.js** >= 18（Puppeteer + dom-to-svg）
- **Python** >= 3.8
- **python-pptx**（PPTX 生成）

**一键安装：**
```bash
pip install python-pptx lxml Pillow
npm install puppeteer dom-to-svg
```

## 目录结构

```
ppt-agent-skill/
  SKILL.md                    # 主工作流指令（Agent 入口）
  README.md / README_EN.md    # 本文件 / English
  references/
    prompts.md                # 5 套 Prompt 模板
    typography.md             # 世界级排版铁律（共享）
    bento-grid.md             # 7 种布局规格 + 卡片类型
    pipeline-compat.md        # HTML→SVG→PPTX 管线兼容性规则
    method.md                 # 核心方法论
    style-system.md           # 引导文件（兼容旧引用）
    styles/                   # 26 风格按 5 板块分目录
      index.md                # 索引 + 决策矩阵 + JSON Schema
      dark.md                 # 7 暗色专业（Linear / Apple Hardware / Tom Ford / Cyberpunk 等）
      light.md                # 8 浅色高级（Anthropic / Apple / NYT / iOS 26 / Mayo Clinic 等）
      vibrant.md              # 4 活力鲜明（Stripe / Bauhaus / Quicksand / Macaron 等）
      cultural.md             # 3 东方文化（Beijing 2022 / Wabi-sabi / 新中式国潮）
      natural.md              # 4 自然/复古（Patagonia / Nat Geo / 70s / 党政）
    charts/                   # 18 种图表
      index.md                # 决策矩阵
      basic.md                # 8 种基础（升级版）
      advanced.md             # 6 种进阶（雷达/时间线/漏斗/仪表盘/多组对比/简单地理）
      complex.md              # 4 种 ECharts 级（世界地图/关系网络/桑基/热力日历）
    principles/
      failure-modes.md        # 8 种 failure modes + 修复顺序
  scripts/
    html_packager.py          # 多页 HTML 合并为翻页预览
    html2svg.py               # HTML → SVG（dom-to-svg，保留文字可编辑）
    svg2pptx.py               # SVG → PPTX（OOXML 原生 SVG 嵌入）
    gallery.py                # 生成 26 风格预览画廊 index.html
    smoke_test.py             # 端到端测试 + pipeline-compat 扫描 + 排版自检
  ppt-output/
    style-gallery/            # 26 风格 1280×720 标杆 mock + index.html 卡片墙
    png/                      # 历史示例（小米 SU7 演示）
  tests/
    smoke-results/            # smoke_test 结果归档
```

## 使用方式

在对话中直接描述你的需求即可触发，Agent 会自动执行完整 6 步工作流：

```
你："帮我做一个关于 X 的 PPT"
  → Agent 提问调研需求（等你回复）
  → 自动搜索资料 → 生成大纲 → 策划稿 → 逐页设计 HTML
  → 自动后处理：HTML → SVG → PPTX
  → 输出全部产物到 ppt-output/
```

**触发示例**：

| 场景 | 说法 |
|------|------|
| 纯主题 | "帮我做个 PPT" / "做一个关于 X 的演示" |
| 带素材 | "把这篇文档做成 PPT" / "用这份报告做 slides" |
| 带要求 | "做 15 页暗黑风的 AI 安全汇报材料" |
| 隐式触发 | "我要给老板汇报 Y" / "做个培训课件" / "做路演 deck" |

> 全程无需手动执行任何脚本，所有后处理（预览合并、SVG 转换、PPTX 生成）由 Agent 在 Step 6 自动完成。

## 许可证

[MIT](LICENSE)
