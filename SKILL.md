---
name: ppt-agent
description: 专业 PPT 演示文稿全流程 AI 生成助手。模拟顶级 PPT 设计公司的完整工作流（需求调研 -> 资料搜集 -> 大纲策划 -> 策划稿 -> 设计稿），输出高质量 HTML 格式演示文稿。当用户提到制作 PPT、做演示文稿、做 slides、做幻灯片、做汇报材料、做培训课件、做路演 deck、做产品介绍页面时触发此技能。即使用户只说"帮我做个关于 X 的介绍"或"我要给老板汇报 Y"，只要暗示需要结构化的多页演示内容，都应该触发。也适用于用户说"帮我把这篇文档做成 PPT"、"把这个主题做成演示"等需要将内容转化为演示格式的场景。
---

# PPT Agent -- 专业演示文稿全流程生成

## 核心理念

模仿专业 PPT 设计公司（报价万元/页级别）的完整工作流，而非"给个大纲套模板"：

1. **先调研后生成** -- 用真实数据填充内容，不凭空杜撰
2. **策划与设计分离** -- 先验证信息结构，再做视觉包装
3. **内容驱动版式** -- Bento Grid 卡片式布局，每页由内容决定版式
4. **全局风格一致** -- 先定风格再逐页生成，保证跨页统一
5. **智能配图** -- 利用图片生成能力为每页配插图（绝大多数环境都有此能力）

---

## 环境感知

开始工作前自省 agent 拥有的工具能力：

| 能力 | 降级策略 |
|------|---------|
| **信息获取**（搜索/URL/文档/知识库） | 全部缺失 **且** 用户也没给资料 -> **STOP，不得凭主题记忆编造**（见下方接地契约）|
| **图片生成**（绝大多数环境都有） | 缺失 -> 纯 CSS 装饰替代 |
| **文件输出** | 必须有 |
| **脚本执行**（Python/Node.js） | 缺失 -> 跳过自动打包和 SVG 转换 |

**原则**：检查实际可调用的工具列表，有什么用什么。

---

## 来源接地契约（Grounding Contract）— 不可静默降级

**一份 deck 的每条实质内容，要么来自用户提供的资料，要么来自本次调研到的事实，要么是基于模型常识的示意——这三选一必须在开工前显式确定，且绝不允许在流程中静默滑落。** 典型事故：说好"基于某文件"，文件却没找到，流程没停下，改用"模型对该主题的记忆"凭空造了一整套内容，当成事实交付给用户。这必须被拦住。

| 接地模式 | 含义 | 硬前提 | 前提不满足时 |
|---------|------|-------|-----------|
| **G1 代表用户的工作** | 内容来自用户提供的资料；每条实质主张可回溯到该资料；模型**不掺入**外部事实 | 资料必须**存在且可读** | 指名的资料**找不到/为空/读不了** → **STOP**：如实报告，把决定权交回用户，**不得**改用模型知识 |
| **G2 基于调研** | 内容来自本次调研（搜索/URL/知识库）；每条实质主张带 `[来源]` | 有可用信息获取工具**且确有结果** | 无工具或搜索**零结果** → **STOP**：如实报告缺口，**不得**凭主题记忆补写 |
| **G3 示意 / 模型知识** | 允许基于模型常识生成，但**须用户明确同意**，且成品**通篇显著标注"示意稿·未经核实"** | 用户**已知情并同意** | 即便在 G3，具体事实（数字/引语/联系方式/人名机构名）仍**不得伪造成真**——用占位或就地标"示意" |

**铁律**：G1/G2 的来源获取失败时，唯一合法动作是**停下 → 如实说明缺了什么 → 把选择权交回用户**（补资料 / 换调研路径 / 显式转 G3 示意稿）。**严禁**在用户不知情的情况下用模型对主题的记忆把页面填满并当作事实——这是本技能最严重的内容事故，比任何排版问题都严重。接地模式的落地细则见 [`references/method.md`](references/method.md) §7。

---

## 路径约定

整个流程中反复用到以下路径。`SKILL_DIR` 触发时即知；`OUTPUT_DIR` 在主题确定后（Step 0/1 采访之前）立即解析，并在整个 run 内复用：

| 变量 | 含义 | 获取方式 |
|------|------|---------|
| `SKILL_DIR` | 本 SKILL.md 所在目录的绝对路径 | 即触发 Skill 时读取 SKILL.md 的目录 |
| `OUTPUT_ROOT` | 所有 deck 的共享父目录 | 用户当前工作目录下的 `ppt-output/`（首次使用时 `mkdir -p` 创建） |
| `OUTPUT_DIR` | 本次 deck 的产物目录（每个 PPT 一个） | `OUTPUT_ROOT/<deck-slug>/`（见下方 slug 规则；用原子 `mkdir` 抢占，见下） |

**`<deck-slug>` 规则**：由主题生成的简短 kebab-case 目录名。
- CJK 主题先转写/翻译成简洁英文短语，再 kebab 化：转小写、把每段非 `[a-z0-9]` 字符替换为单个 `-`、去掉首尾 `-`。字符集 `[a-z0-9-]`，≤40 字符。
- **解析一次**：主题确定后（采访之前）就定下 `OUTPUT_DIR`，整个 run 复用同一目录。
- **原子抢占（防并发撞车）**：新建 deck 时优先运行 `python3 SKILL_DIR/scripts/resolve_output_dir.py --root OUTPUT_ROOT --slug "<英文短语>"`——它做 kebab 归一化，再用原子 `mkdir` 抢占 `<slug>`（已被占用则自动依次试 `<slug>-2`…`<slug>-99`），把抢到的绝对路径打到 stdout；全被占用则报错求助。CJK→英文转写仍由主 agent 在传入 `--slug` 前完成（脚本只吃 `[a-z0-9]`）。**无 Python 时的降级**：手工用**不带 `-p` 的 `mkdir`** 抢占（目录已存在则失败），失败依次试 `<slug>-2`/`<slug>-3`…；第一个成功的 `mkdir` 即占位（`mkdir -p` 不报错、无法当抢占用），最多试到 `<slug>-99` 仍抢不到就停下报错。两条路径都保证同一 cwd 下两个同主题 run 不会选到同一目录。
- **续跑**：续跑或跨对话恢复进行中的 deck 时**复用已有目录（匹配，不重新抢占）**——先扫描 `OUTPUT_ROOT/<slug>*`，复用其中产物与本 run 吻合的那个（首个 run 可能已被去重成 `<slug>-2`），别盲目按 slug 重新解析。**续跑不走上面的抢占脚本**：哪个目录算"本 run"需要判断，由主 agent 扫描匹配后直接复用（`resolve_output_dir.py` 只做新建抢占、不猜续跑目录）。重新抢占会把续跑产物散落到空的兄弟目录里。续跑假定**单写者**（一个 deck 同一时刻只有一个 run 在续），并发续同一 deck 不在保护范围内。

后续所有路径均基于 `SKILL_DIR` 与 `OUTPUT_DIR`，不再重复说明。工具类产物（`style-gallery/` 等）挂在 `OUTPUT_ROOT` 下、与各 deck 目录平级，不属于任何 deck。

---

## 输入模式与复杂度判断

### 入口判断

| 入口 | 示例 | 从哪步开始 |
|------|------|-----------| 
| 纯主题 | "做一个 Dify 企业介绍 PPT" | Step 1 完整流程 |
| 主题 + 需求 | "15 页 AI 安全 PPT，暗黑风" | Step 1（跳部分已知问题）|
| 源材料 | "把这篇报告做成 PPT" | Step 1（材料为主）|
| 已有大纲 | "我有大纲了，生成设计稿" | Step 4 或 5 |

### 跳步规则

跳过前置步骤时，必须补全对应依赖产物：

| 起始步骤 | 缺失依赖 | 补全方式 |
|---------|---------|---------|
| Step 4 | 每页内容文本 | 先用 Prompt #3 为每页生成内容分配 |
| Step 5 | 策划稿 JSON | 用户提供或先执行 Step 4 |

### 复杂度自适应

根据目标页数自动调整流程粒度：

| 规模 | 页数 | 调研 | 搜索 | 策划 | 生成 |
|------|------|------|------|------|------|
| **轻量** | <= 8 页 | 3 题精简版（场景+受众+补充信息） | 3-5 个查询 | Step 3 可与 Step 4 合并一步完成 | 逐页生成 |
| **标准** | 9-18 页 | 完整 7 题 | 8-12 个查询 | 完整流程 | 按 Part 分批，每批 3-5 页 |
| **大型** | > 18 页 | 完整 7 题 | 10-15 个查询 | 完整流程 | 按 Part 分批，每批 3-5 页，批间确认 |

---

## 6 步 Pipeline

### Step 1: 需求调研 [STOP -- 必须等用户回复]

> **禁止跳过。** 无论主题多简单，都必须提问并等用户回复后才能继续。不替用户做决定。

**执行**：使用 `references/prompts.md` Prompt #1
1. 搜索主题背景资料（3-5 条）
2. 根据复杂度选择完整 7 题或精简 3 题，一次性发给用户
3. **等待用户回复**（阻断点）
4. 整理为需求 JSON

**7 题三层递进结构**（轻量模式只问第 1、2、7 题）：

| 层级 | 问题 | 决定什么 |
|------|------|---------|
| 场景层 | 1. 演示场景（现场/自阅/培训） | 信息密度和视觉风格 |
| 场景层 | 2. 核心受众（动态生成画像） | 专业深度和说服策略 |
| 场景层 | 3. 期望行动（决策/理解/执行/改变认知） | 内容编排的最终导向 |
| 内容层 | 4. 叙事结构（问题->方案/科普/对比/时间线） | 大纲骨架逻辑 |
| 内容层 | 5. 内容侧重（搜索结果动态生成，可多选） | 各 Part 主题权重 |
| 内容层 | 6. 说服力要素（数据/案例/权威/方法，可多选） | 卡片内容类型偏好 |
| 执行层 | 7. 补充信息（演讲人/品牌色/必含/必避/页数/配图偏好） | 具体执行细节 |

**产物**：需求 JSON（topic + requirements）

---

### Step 2: 资料搜集

> 盘点所有信息获取能力，全部用上。

**执行**：
1. 根据主题规划查询（数量参考复杂度表）
2. 用所有可用的信息获取工具并行搜索
3. 每组结果摘要总结

> **来源获取闸门（不可静默降级）。** 进入 Step 3 之前，按本次 deck 的接地模式核对来源已到位——**G1** 指名的每个资料路径都要实际读到内容，**G2** 搜索/URL/知识库要确有可用结果；任一前提不满足即 **STOP**（各模式的处置细则见上方「来源接地契约」表「前提不满足时」列）。
> - 任何情况下都**不允许**因为"没搜到/没读到"就凭主题记忆把内容补满当成事实——那是最严重的内容事故。转 G3 示意稿必须经用户明确同意，且成品通篇标注"示意稿·未经核实"。

**产物**：搜索结果集合 JSON

---

### Step 3: 大纲策划

**执行**：使用 `references/prompts.md` Prompt #2（大纲架构师 v2.0）

**方法论**：金字塔原理 -- 结论先行、以上统下、归类分组、逻辑递进

**自检**：页数符合要求 / 每 part >= 2 页 / 要点有数据支撑

**产物**：`[PPT_OUTLINE]` JSON

---

### Step 4: 内容分配 + 策划稿 [建议等用户确认]

> 将内容分配和策划稿生成合为一步。在思考每页应该放什么内容的同时，决定布局和卡片类型，更自然高效。

**执行**：使用 `references/prompts.md` Prompt #3（内容分配与策划稿）

**要点**：
- 将搜索素材精准映射到每页
- 为每页设计多层次内容结构（主卡片 40-100 字 + 数据亮点 + 辅助要点）
- 同时确定 page_type / layout_hint / cards[] 结构
- **每个内容页至少 3 张卡片 + 2 种 card_type + 1 张 data 卡片**
- 布局选择参考 `references/bento-grid.md` 的决策矩阵

向用户展示策划稿概览，建议等用户确认后再进入 Step 5。

**产物**：每页策划卡 JSON -> 逐页保存为 `OUTPUT_DIR/planning/planningN.json`（校验闸门与 cli-cheatsheet 均按此每页路径运行 `planning_validator.py`）

> **策划必须过闸门。** 无论用 PageAgent 流程还是手动产出，策划都必须能通过 `planning_validator.py` 且每张卡有真实内容（body/items/data/chart/image 之一），才能进入 Step 5c 生成 HTML（见 5c 的强制策划闸门）。不要用离线/自建脚本产出绕过校验的骨架策划。

---

### Step 5: 风格决策 + 设计稿生成

分三个子步骤，**顺序不可颠倒**：

#### 5a. 风格决策

**执行**：阅读 `references/styles/index.md` 主索引（含决策矩阵），按主题关键词匹配 29 种预置风格之一

**29 风格按 5 板块分组**（详细 JSON 定义在板块文件中）：

| 板块 | 数量 | 风格 ID | 板块文件 |
|------|------|--------|---------|
| 暗色专业 | 8 | dark_tech / xiaomi_orange / luxury_purple / nocturne_violet / cyberpunk_neon / chrome_y2k / noir_film / graphite_gold | `references/styles/dark.md` |
| 浅色高级 | 10 | blue_white / fresh_green / minimal_gray / mocha_editorial / medical_pulse / earth_concrete / champagne_gold / liquid_glass / editorial_paper / schematic_blueprint | `references/styles/light.md` |
| 活力鲜明 | 4 | vibrant_rainbow / kindergarten_pop / bauhaus_block / candy_pastel | `references/styles/vibrant.md` |
| 东方文化 | 3 | royal_red / sakura_wabi / ink_jade | `references/styles/cultural.md` |
| 自然/复古 | 4 | botanic_forest / safari_savanna / retro_70s / gov_authority | `references/styles/natural.md` |

**风格预览**：执行 `python3 SKILL_DIR/scripts/gallery.py` 生成 `ppt-output/style-gallery/index.html`，浏览器打开可视化对比 29 风格。

**也必读**：`references/typography.md`（排版铁律：字距 / tabular-nums / OpenType / serif italic 混排 / 首字下沉 / 不对称网格 / 字体栈三层降级 / 微妙纹理）

**产物**：风格定义 JSON -> 保存为 `OUTPUT_DIR/style.json`

#### 5b. 智能配图（根据用户偏好）

> 在需求调研（Step 1 第 7 题）中确认用户的配图偏好后执行。如果用户选择"不需要配图"则跳过。

##### 配图时机

在生成每页 HTML **之前**，先为该页生成配图。每页至少 1 张（封面页、章节封面必须有），生成后保存到 `OUTPUT_DIR/images/`。

##### 提示词构造

`generate_image` 提示词的四维构造公式（`[内容主题] + [视觉风格] + [画面构图] + [技术约束]`）、各 PPT 风格的配图关键词、按页面类型的调整、以及禁止事项 —— 详见 [`references/image-generation.md`](references/image-generation.md)，按该文件组装每页 prompt。

**产物**：`OUTPUT_DIR/images/` 下的配图文件

#### 5c. 逐页 HTML 设计稿生成

**执行**：使用 `references/prompts.md` Prompt #4 + `references/bento-grid.md`

> **强制策划闸门（不可绕过）。** 生成任何一页 slide HTML 之前，该页策划必须先**通过 `planning_validator.py`（零 ERROR）**——`skeleton card`（只有 headline、无 body/items/data/chart/image 内容）或 `empty card payload` 都直接拦下、禁止进入 HTML。**禁止**跳过策划稿直接生成，也**禁止**用自建脚本/离线流程绕过本闸门。骨架策划是 P0 缺陷，不是交付物。

**每页 Prompt 组装公式**：
```
Prompt #4 模板
+ 风格定义 JSON（5a 产物）[必须]
+ 该页策划稿 JSON（Step 4 产物，含 cards[]/card_type/position/layout_hint）[必须]
+ 该页内容文本（Step 4 产物）[必须]
+ 配图路径（5b 产物）[可选 -- 无配图时省略 IMAGE_INFO 块]
```

**核心设计约束**（完整清单见 Prompt #4 内部）：
- 画布 1280x720px，overflow:hidden
- 所有颜色通过 CSS 变量引用，禁止硬编码
- 凡视觉可见元素必须是真实 DOM 节点，图形优先用内联 SVG
- 禁止 `::before`/`::after` 伪元素用于视觉装饰、禁止 `conic-gradient`、禁止 CSS border 三角形
- 配图融入设计：渐隐融合/色调蒙版/氛围底图/裁切视窗/圆形裁切（技法详见 Prompt #4）
- **出片前过品味闸门** `references/principles/taste-gate.md`：反 AI 感自审（三个"默认长相"别踩）+ 焦点纪律（accent ≤ 2）+ 删除测试 + 无标题装饰横线

**分批策略**：按 Part 为单位分批生成，每批 3-5 页。每批完成后将 HTML 写入 `OUTPUT_DIR/slides/` 目录，再开始下一批。避免上下文爆炸的同时保证同一 Part 内的风格一致性。

**跨页视觉叙事**（让 PPT 有节奏感，不只是独立页面的堆砌）：

| 策略 | 规则 | 原因 |
|------|------|------|
| **密度交替** | 高密度页（混合网格/英雄式）后面跟低密度页（章节封面/单一焦点），形成张弛有度的节奏 | 连续 3+ 页高密度内容会导致观众视觉疲劳 |
| **章节色彩递进** | Part 1 卡片主用 accent-1，Part 2 用 accent-2，Part 3 用 accent-3 ... 每章换一种 accent 主色 | 通过颜色让受众无意识感知章节切换 |
| **封面-结尾呼应** | 结束页的视觉元素与封面页形成呼应（相同装饰图案、对称布局），给出完整闭环感 | 首尾呼应是最基本的叙事美学 |
| **渐进揭示** | 同一概念跨多页展开时，视觉复杂度应递增（第1页简单色块 -> 第2页加数据 -> 第3页完整图表） | 引导观众逐步深入理解 |

**产物**：每页一个 HTML 文件 -> `OUTPUT_DIR/slides/`

---

### Step 6: 后处理 [必做 -- HTML 生成完后立即执行]

> **禁止跳过。** HTML 生成完后必须自动执行以下四步，不要停在 preview.html 就结束。

> 三个终产物统一带 `<deck-slug>-` 前缀（`<deck-slug>` = `OUTPUT_DIR` 目录名），单独下载也能看出主题；中间目录（`svg/`、`png/`）与单页文件名不变。产物文件名以 `references/cli-cheatsheet.md` 为准。

```
slides/*.html --> <deck-slug>-preview.html --> svg/*.svg --> <deck-slug>-svg.pptx
```

**依赖检查**（首次运行自动执行）：
```bash
pip install python-pptx lxml Pillow 2>/dev/null
```

**依次执行**：

1. **合并预览** -- 运行 `html_packager.py`
   ```bash
   python3 SKILL_DIR/scripts/html_packager.py OUTPUT_DIR/slides/ -o OUTPUT_DIR/<deck-slug>-preview.html --title "本演示文稿标题"
   ```
   `--title` 传演示文稿的真实标题（大纲主标题），它会成为浏览器标签页标题，多个 deck 同时打开时便于区分。省略时自动推断：优先读 `outline.json/outline.txt` 的 `cover.title`，其次剥离首页 `<title>` 的 `Slide N -` 前缀，再退到首页 `<h1>`，最后回退 deck 目录名（占位符与未替换模板变量会被跳过）。

2. **SVG 转换** -- 运行 `html2svg.py`（DOM 直接转 SVG，保留 `<text>` 可编辑）
   > **重要**：HTML 设计稿必须遵守 `references/pipeline-compat.md` 中的管线兼容性规则，否则转换后会出现元素丢失、位置错位等问题。
   ```bash
   python3 SKILL_DIR/scripts/html2svg.py OUTPUT_DIR/slides/ -o OUTPUT_DIR/svg/
   ```
   底层用 dom-to-svg（自动安装），首次运行会 esbuild 打包。
   **降级**：如果 Node.js 不可用或 dom-to-svg 安装失败，跳过此步和步骤 3，只输出 preview.html。

3. **PPTX 生成** -- 运行 `svg2pptx.py`（OOXML 原生 SVG 嵌入，PPT 365 可编辑）
   ```bash
   python3 SKILL_DIR/scripts/svg2pptx.py OUTPUT_DIR/svg/ -o OUTPUT_DIR/<deck-slug>-svg.pptx --html-dir OUTPUT_DIR/slides/
   ```
   PPT 365 中右键图片 -> "转换为形状" 即可编辑文字和形状。

4. **通知用户** -- 告知产物位置和使用方式：
   - `<deck-slug>-preview.html` -- 浏览器打开即可翻页预览
   - `<deck-slug>-svg.pptx` -- PPTX（右键 -> "转换为形状" 可编辑）
   - `svg/` -- 每个 SVG 也可单独拖入 PPT
   - **如果步骤 2-3 被降级跳过**，说明原因并告知用户手动安装 Node.js 后可重新运行

**产物**：`<deck-slug>-preview.html` + svg/*.svg + `<deck-slug>-svg.pptx`

---

## 输出目录结构

每个 PPT 一个 `<deck-slug>/` 目录，编号 HTML 页面嵌套在其下的 `slides/`。产物文件名以 `references/cli-cheatsheet.md` 为准（下方仅为示意）。**本 run 写出的一切——含临时目录与构建脚手架——都必须落在本 `<deck-slug>/` 内，不得散到 `OUTPUT_ROOT` 根或项目根**（这样并发 run 各占一个 deck 目录即可互不干扰）：

```
ppt-output/                    # OUTPUT_ROOT：所有 deck 的共享父目录
  <deck-slug>/                 # OUTPUT_DIR：每个 PPT 一个目录
    slides/            # 每页 HTML（编号），嵌套在本 deck 目录下
    svg/               # 矢量 SVG（可导入 PPT 编辑）
    png/               # 高清 PNG（供 PPT/图审）
    images/            # AI 配图
    runtime/           # 阶段 prompt / 中间快照（会话 scratch）
    pptx-work/         # 可选：走原生 PPTX 构建路径时的脚手架（含自带 node_modules），也必须留在 deck 内
    <deck-slug>-preview.html   # 可翻页预览
    <deck-slug>-svg.pptx       # 可编辑 PPTX（右键"转换为形状"）
    outline.json       # 大纲
    planning/          # 每页策划稿 planningN.json（planning_validator 校验闸门对象）
    style.json         # 风格定义
  style-gallery/               # 29 风格预览（工具产物，与 deck 目录平级，非 deck）
```

---

## 质量自检

| 维度 | 检查项 |
|------|-------|
| 内容 | 每页 >= 2 信息卡片 / >= 60% 内容页含数据 / 章节有递进 |
| 视觉 | 全局风格一致 / 配图风格统一 / 卡片不重叠 / 文字不溢出 |
| 技术 | CSS 变量统一 / SVG 友好约束遵守 / HTML 可被 Puppeteer 渲染 / `pipeline-compat.md` 禁止清单检查 |

---

## 资源路由表（字段 → 文件夹）

策划稿 JSON 中各字段决定从哪个目录抽取相应资源：

- 字段路由：`layout_hint→layouts/`、`page_type→page-templates/`、`card_type→blocks/`、`chart_type→charts/`

| 字段 | 取值 | 路由到 | 例 |
|------|------|-------|---|
| `layout_hint` | asymmetric / hero-top / l-shape / mixed-grid / primary-secondary / single-focus / symmetric / t-shape / three-column / waterfall | `references/layouts/<name>.md` | 主次结合 → `references/layouts/primary-secondary.md` |
| `page_type` | cover / toc / section / section-marker / reference / end | `references/page-templates/<name>.md` | 封面 → `references/page-templates/cover.md` |
| `card_type` | text / data / list / quote / timeline / comparison / diagram / image-hero / matrix-chart / people | `references/blocks/<name>.md` | 数据卡 → `references/blocks/card-styles.md` |
| `chart_type` | progress-bar / ring / sparkline / radar / funnel / kpi / metric-row / waffle / rating / timeline / treemap / comparison-bar / stacked-bar | `references/charts/index.md`（按类别取 basic/advanced/complex） | 雷达 → `references/charts/advanced.md` |

## Step 0/1 采访模板规则

**Step 0 默认强制模板化**：主 agent 必须先生成 `OUTPUT_DIR/runtime/prompt-interview.md`，再依据渲染结果向用户发问；采访运行时模板必须按能力在 `tpl-interview-structured-ui.md` 与 `tpl-interview-text-fallback.md` 之间二选一。

**Step 0 优先结构化采访 UI**：只要当前 CLI 提供任何等价于 `AskUserQuestion` / `request_user_input` 的原生提问能力，主 agent 就必须优先使用结构化采访 UI；不支持时回退到 `tpl-interview-text-fallback.md`。

**Step 0 唯一例外**：仅当 prompt 生成在 Step 0 发生真实脚本接口故障，并已判定 `BLOCKED_SCRIPT_INTERFACE` 时，才允许主 agent 直接发问；但覆盖维度不得低于 `prompt-interview.md` 的最终要求。

详细模板：[`references/prompts/tpl-interview.md`](references/prompts/tpl-interview.md) · [`references/prompts/tpl-interview-structured-ui.md`](references/prompts/tpl-interview-structured-ui.md) · [`references/prompts/tpl-interview-text-fallback.md`](references/prompts/tpl-interview-text-fallback.md)

## Reference 文件索引

| 文件 | 何时阅读 | 关键内容 |
|------|---------|---------|
| `references/prompts.md` | **内联单 agent 流程**（Step 1-5 直接引用 Prompt #1-#5）| 5 套合并 Prompt 模板（调研/大纲/策划/设计/备注）|
| `references/prompts/*.md` | **子 agent 编排管线**（按 phase 拆分、含 STAGE COMPLETE 交接锚点，23 文件：tpl-* 21 + module-* 2）| 与 prompts.md 是两条并行执行路径、非彼此副本；prompts.md 服务内联流程，prompts/ 服务 PageAgent/分阶段编排 |
| `references/playbooks/*.md` | 每步执行手册（11 文件）| outline / research / source / style / step4 各 phase 的执行 playbook |
| `references/styles/index.md` | **Step 5a** | 29 种预置风格索引 + 决策矩阵 + JSON Schema |
| `references/styles/{dark,light,vibrant,cultural,natural}.md` | Step 5a 选定风格后 | 该板块所有风格的完整 JSON + CSS 变量 + Mock 链接 |
| `references/typography.md` | **Step 5c** | 排版铁律 14 条（字距/tabular-nums/OpenType/serif italic 混排/字体栈降级）|
| `references/charts/index.md` | **Step 5c 涉及数据可视化时** | 18 种图表索引 + 决策矩阵 |
| `references/charts/{basic,advanced,complex}.md` | 选定图表后 | 完整 HTML 模板（基础 8 种 / 进阶 6 种 / ECharts 级 4 种）；单一图表精细规格按类别在此三文件内查 |
| `references/layouts/*.md` | Step 5c layout_hint 路由 | 10 个 layout 各成文件（asymmetric / hero-top / l-shape 等）|
| `references/blocks/*.md` | Step 5c card_type 路由 | 9 个可复用卡片原型（card-styles / comparison / diagram / quote 等）|
| `references/page-templates/*.md` | Step 5c page_type 路由 | 6 个页面模板（cover / end / reference / section / section-marker / toc）|
| `references/principles/*.md` | **Step 4-5 自检与原则** | 8 设计原则 + failure-modes + **taste-gate（反 AI 感自审 / 出片前品味闸门）**（cognitive-load / color-psychology / composition / data-visualization / narrative-arc / runtime-failure-modes / visual-hierarchy / taste-gate）|
| `references/design-runtime/*.md` | Step 5c 设计运行时 | css-weapons / data-type-decoration-mapping / data-type-visual-mapping / design-specs / director-command-rules-examples |
| `references/image-generation.md` | **Step 5b 配图时** | generate_image 四维构造公式 + 风格配图关键词 + 按页面类型调整 + 禁止事项 |
| `references/bento-grid.md` | Step 5c | 7 种布局精确坐标 + 5 种卡片类型 + 决策矩阵 |
| `references/method.md` | 初次了解 | 核心理念与方法论 |
| `references/pipeline-compat.md` | **Step 5c 设计稿生成时** | CSS 禁止清单 + 图片路径 + 字号混排 + SVG text + 环形图 + svg2pptx 注意事项 |
| `references/cli-cheatsheet.md` | 脚本调用查阅 | 所有 scripts 的完整调用命令速查 |
| `references/style-system.md` | （兼容引导文件） | 已升级为引导文件，redirect 到 `styles/index.md` |

## 维护与校验

**真源文件**：

| 资源 | 真源位置 | 用途 |
|------|---------|------|
| Step 4 schema | `scripts/planning_validator.py` | P4 planning Gate |
| Workflow 版本 | `scripts/workflow_versions.py` | 跨脚本版本号 |
| Skill 一致性 | `scripts/check_skill.py` | 文档/代码合同漂移检查 |

**自动检查入口**：修改 prompt / playbook / cheatsheet / Step 4 schema 示例后，运行：

```bash
python3 scripts/check_skill.py            # 文档与代码合同漂移检查
python3 scripts/planning_validator.py     # 策划稿 schema 校验
python3 scripts/contract_validator.py     # 各 phase 间 JSON 合同校验
python3 scripts/visual_qa.py              # 视觉 QA 双层断言（planning + html）
python3 scripts/smoke_test.py             # 我们简化版端到端冒烟测试
python3 scripts/smoke_skill.py            # sunbigfly 完整版冒烟测试
```
