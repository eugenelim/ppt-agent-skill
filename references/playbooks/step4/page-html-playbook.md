# Page HTML Playbook -- 单页 HTML 设计稿

## 目标

忠实还原 planning JSON 里的骨架与精神，运用 `resource_loader.py resolve` 的解析能力，将抽象组件组装成极具高级设计感的**单页自包含 HTML**。

---

## Phase 1：骨架理解（不得跳过）

读取 `planning{n}.json` 的以下字段作为本阶段的硬约束：

| 字段 | HTML 阶段的含义 |
|------|--------------|
| `page_type` / `layout_hint` | 决定整体骨架与页面自由度 |
| `density_label` / `density_contract` | 决定本页是高自由度还是低自由度执行模式 |
| `focus_zone` | 决定哪个卡片/区域应该有最大视觉权重 |
| `negative_space_target` | 决定留白比例（high=宽松 / medium=适中 / low=密集）|
| `cards[].role` / `cards[].card_style` | 决定主次顺序与卡片存在感 |
| `cards[].card_id` | 要在 HTML 中逐一落地，并映射到 `data-card-id` |
| `cards[].content_budget` | 限制每张卡片的承载量，防止溢出 |
| `director_command` / `decoration_hints` | 决定镜头感、装饰层次和实现边界 |
| `source_guidance` / `must_avoid` | 决定证据呈现方式与禁止动作 |
| `image.mode` | 严格按下面第 3 条执行 |
| `persistent_chrome` / `deck_chrome` | 顶层布尔开关 + 文案对象。为 `true` 且本页 `page_type == content` 时，按 Phase 5「持久化页框例外」加装 masthead 顶栏 + runbook 页脚（文案取自 `deck_chrome`）；缺省 / `false` 时忽略，走普通统一骨架 |

---

## Phase 2：资源正文消费（强制执行，不得跳过）

```bash
python3 SKILL_DIR/scripts/resource_loader.py resolve --refs-dir REFS_DIR --planning PLANNING_OUTPUT
```

脚本返回 planning 中引用的每个资源的**完整正文实现**，包含：
- 组件的 HTML 结构骨架（含 class 命名示例）
- 推荐的 CSS 参数（间距、字号、颜色变量用法）
- 数据格式要求（如 chart 的 data 格式）

**你必须将此作为不可逾越的底层骨架。基于此骨架，你可以运用高级的表达技巧（如 CSS 空间处理）增强它，但绝对禁止偏离或破坏原始结构的逻辑编排。图审只会拦截错误，不会为你重构错乱的骨架。**

特别注意：
- 虽然 resolve 提供了基础结构，但你必须**严格对齐原 `layout_hint` 所赋予的空间逻辑**。你可以用更现代、精细的 CSS 增强它，但绝不支持“摧毁重建”。
- 允许在极致对齐和还原规划骨架的前提下优化视觉，但不要妄图在此时挑战原本规划好的数据主次。
- `process` 这类没有独立 block 文件的 card_type，须用坚固的原生 DOM 结构结合严谨的布局技法将其承接，禁止随意破坏既定的阅读动线。

### 密度执行模式（必须服从）

- `low / mid_low`：高自由度，可使用更强的留白、图片和材质变化
- `medium`：中自由度，允许有设计表达，但不能破坏阅读秩序
- `high / dashboard`：低自由度，只能做稳态 grid / flex 骨架，优先表格、矩阵、微图表，禁止依赖复杂绝对定位硬塞内容

**特别红线**：
- `high / dashboard` 禁主视觉大图卡
- `dashboard` 禁大面积水印、禁装饰抢主阅读路径
- `density_contract` 是最高施工合同，HTML 不得自行抬高或降低本页密度

---

## Phase 3：图片模式严格执行

| image.mode | HTML 要做什么 | 绝对禁止 |
|-----------|-------------|---------|
| `generate` / `provided` | 用 `source_hint` 路径渲染 `<img src>` 或 `background-image: url()` | 不得用占位色块替代真实图 |
| `manual_slot` | 渲染明确尺寸的图片占位框（带虚线边框 + 文字说明"[图片替换位]"）| 不得删掉或做成看不出来的空白 |
| `decorate` | 使用内联 SVG、CSS 渐变、几何色块、大字水印、圆圈装饰等内部视觉语言补足氛围 | 不得留空白大洞，不得放空的 `<div>` |

同时严格服从 `density_contract.image_policy`：
- `flexible`：可自由选图，但仍须服务 page_goal
- `support_only`：图片只能做支撑，不得做整页背景大图
- `decorate_only`：不得渲染外部图片，只能 `decorate`

---

## Phase 4：卡片落地对账（强制）

- `planning.cards[]` 中的每一张卡都必须有一个对应的 HTML 根节点。
- 每个根节点都要带 `data-card-id="<card_id>"`，便于 Review 阶段与 planning 对账。
- `role = anchor` 的卡必须成为全页第一视觉落点；`support/context` 退后，但不能消失。
- 任何**纯装饰节点**都必须带 `data-decoration-layer="background|floating|page-accent"`，并同时写 `aria-hidden="true"`；`visual_qa.py` 会直接按这个标记统计装饰预算。
- 若卡片带 `chart.chart_type`，最终图表类型必须与 planning 保持一致；不要把 `comparison_bar` 偷换成普通 list。
- 若 `source_guidance` 要求保留来源，至少在卡片 footer / caption / 注释位中给出来源提示。
- 卡片数量、图表数量、每卡行数都不得超出 `density_contract` 的预算上限。
- **【反泄漏清扫防线】**：在你把 JSON 里的 `body` 和 `headline` 填入 HTML 标签时，如果读到了明显的**“旁白解说”、“排版动作”**（例如：“这一页先做铺垫，最后收束到结论”等废话），**绝对不准老实巴交地把它渲染在大屏幕上！** 这是前置 Planning 代理漏掉的导演指导语，你必须主动充当最后一道防火墙将其直接剔除，或自行将其改写为干货文案！

---

## Phase 5：画布物理红线（不可违反）

```css
* {
  box-sizing: border-box; /* 像素级排版防崩核心 */
}

body {
  width: 1280px;
  height: 720px;
  overflow: hidden;
  margin: 0;
  padding: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale; /* 保障文字渲染精度 */
}
```

**像素级渲染安全防线（涉及无头浏览器最终出图质量，极度重要）：**
- **流体坍缩预防**：在高度自由发挥时，`flex` / `grid` 极易出现子项挤压坍缩。凡是重要卡片或必须撑开的区域，务必使用 `min-width`, `min-height` 或 `flex-shrink: 0`。
- **行高裁剪预防**：文字的 `line-height` 若低于 `1.3`，部分英文小写字母下端极其容易被隐形裁剪，正文需保持合理行高。
- **边框与阴影溢出**：所有的边框宽度、`box-shadow` 都可能溢出原有容器。借助于 `box-sizing: border-box`，确保 padding 和 border 在规划宽度内。
- **密度合同预防**：正文最小字号不得低于 `density_contract.min_body_font_px`；如果放不下，先减装饰，再收紧预算，再回退 planning，不得偷缩到不可读。

- **禁止** `width: 100%; height: 100%` 然后依赖父容器
- **禁止** `transform: scale()` 缩放 hack
- **禁止** 引用外部 CSS 文件（如 `common.css`、`deck.css`）

### 统一导航骨架（强制 -- 保证全 deck 视觉一致性）

每个页面由独立的 PageAgent 生成，**必须**使用统一的标题区和页脚区 HTML 骨架，避免拼装后各页标题/页脚形态各异。骨架规范详见 `design-specs.md` A 节「统一导航骨架合同」，核心规则如下：

| page_type | 标题区 | 页脚区 |
|-----------|--------|--------|
| `content` / `toc` | **强制** `header.slide-header > span.overline + h1.page-title`，`position:absolute; top:20px` | **强制** `footer.slide-footer`，`position:absolute; bottom:12px` |
| `section` | **自由**（章节标题是设计主角） | **强制** 同上 |
| `cover` / `end` | **自由** | **可选** |

**视觉创意不受影响**：overline 内容、page-title 字号、装饰线、页脚风格（W12 终端/印章/进度条）都可按风格变化。统一的只是 **HTML 结构和定位方式**。

#### 持久化页框例外（persistent_chrome —— 仅参考型 deck 开启时）

当 planning JSON 顶层 `persistent_chrome == true` **且** 本页 `page_type == content` 时，为本页套一层"页框"（`cover`/`section`/`toc`/`end` 不受影响；`false` / 缺省时本节不生效，按上表走普通骨架）：

- **masthead 顶栏 + runbook 页脚**：结构逐字取自 [`blocks/worksheet.md` C 组页面骨架](../../blocks/worksheet.md)（`masthead` + `footer` 配方），只改文案、不改结构，全部绑定 deck 契约变量（`--text-primary` / `--accent-1` / `--card-bg-from` / `--font-mono` / `--font-primary`）随风格换色。
- **三条绝对定位带 + 内容区收窄**：masthead `position:absolute; top:20px`（~32px）；`slide-header` **下移到** `top:64px`（保留每页标题）；content 从 y≈120px 起、可用高度 **≈500px**（`density_contract` 按 ≈500px 计，不按 580px）；runbook 页脚 `position:absolute; bottom:12px`（~56px）**整块替换** `.slide-footer`。完整像素带见 `design-runtime/design-specs.md` §A「持久化页框例外」。
- **文案逐槽映射填满，别留空列**：masthead 左 = `deck_chrome.title`、中 = `deck_chrome.subtitle`、右 = 本页页码 `{当前页}/{总页}`；footer 列1 = `deck_chrome.title` + `deck_chrome.subtitle`（作释义句）、列2（小标题改 `Section`）= 本页 section 标签、列3（小标题改 `Page`）= 本页页码。**绝不渲染 C 组配方里的示例文案**（如 `SCHEMATIC · DELIVERY RUNBOOK` / `REV 2.4`；完整禁用清单以 `design-runtime/design-specs.md` §A「持久化页框例外」为准），确无来源的槽位才留空省略。footer 列1 破折号回退规则同 §A。
- **铁律**：一张页要么普通骨架、要么这套页框，二者只居其一，绝不并存；页框只用真实 `<div>`/`<span>`/`<footer>`——禁 `::before`/`::after` 装饰、禁硬编码色/字（沿用 C 组配方即天然满足管线红线）。

---

## Phase 6：风格变量严格绑定

从 `style.json` 的 `css_variables` 提取所有变量，写入 HTML 的 `:root`：

```css
:root {
  --bg-primary: [从 style.json 取];
  --bg-secondary: [从 style.json 取];
  --card-bg-from: [从 style.json 取];
  --card-bg-to: [从 style.json 取];
  --card-border: [从 style.json 取];
  --card-radius: [从 style.json 取];
  --text-primary: [从 style.json 取];
  --text-secondary: [从 style.json 取];
  --accent-1: [从 style.json 取];
  --accent-2: [从 style.json 取];
  --accent-3: [从 style.json 取];
  --accent-4: [从 style.json 取];
  --font-primary: [从 style.json font_family 取];
}
```

- `design_soul`：用来校准情绪，不得直接抄成页面文案
- `variation_strategy`：控制这一页的变化幅度，避免与相邻页同构复制
- `decoration_dna.forbidden`：硬边界，违反即自动不达标
- `decoration_dna.recommended_combos`：优先采用
- `decoration_dna.signature_move`：跨页识别锚点，必须出现
- `card_fills`：**省略或 `false`（单-accent 风格）时，内容卡片一律用中性/白卡片底（`.card.flat` 为默认形态），禁止用副色（`--accent-2/3/4`）铺卡片背景 —— 副色只作信号色（见 design-specs B/C 节）；彩色卡片底仅在 `card_fills:true`（vibrant 板块）或 planning 显式给出上色理由时才用。**
- `density_contract.decoration_budget`：同时约束装饰层数量。默认上限建议为：`generous <= 6`、`medium <= 4`、`low <= 2`、`minimal <= 1`

---

## Phase 7：你是最顶级的架构执行者

> **核心理念**：planning JSON 是你的核心工程图纸，resource resolve 的组件正文是你的模具。你的工作是结合高精度的 CSS（阴影、滤镜、裁切），在绝对服从图纸尺寸和空间设定的前提下，雕琢出令人惊艳的最终渲染结果。

**你的架构底线与渲染特权：**
- **严守骨架**：绝不允许在宏观上摧毁 Planning 划定的 `layout_hint` 结构体系和文档重力场。
- **释放渲染力**：在确保结构坚如磐石的前提下，CSS 的实现特权完全下放给你。你可以大胆使用绝对定位、高级滤镜、复杂渐变、clip-path 去雕琢卡片，尽情通过 CSS 解放被原数据束缚的表现张力。
- **密度服从优先**：`high / dashboard` 页首先要清晰、稳定、可扫读，再谈戏剧化表现。不得为了“酷”牺牲结构。

**设计独立性自检（追问：我的执行是否精准且克制？）**：
- 本页的底层承重墙（DOM结构）与 `page_goal` 和 `director_command` 的原意做到了一比一还原吗？
- 视觉锚点的位置是否彻底捍卫了原设计稿中定义的信息主次？
- 严禁套模板的心理：不可直接拿通用结构的冗余代码应付了事，任何多余的包裹标签都是负面的。

**核心保障约束**：你是本次渲染过程的全权负责方。图审环节（Review）只是出厂前的最后一道质检防线，它不会替你收拾结构混乱的烂摊子，所有的错误都必须由你亲自修复。

---

## Phase 7.5：图解卡「结构先行」（structure-before-coordinates · 仅 diagram 卡）

> **为什么**：LLM 单遍同时"定拓扑 + 手排坐标"是它最弱的一环（坐标算术错误约占一半、多空间约束整合 <50%、随节点数崩塌）。把"先定结构、再由结构派生坐标"固化成步骤，第一遍就更可能画对，而不是留给 Review 收拾。

> **【绝对红线 — 违反即 P0】**：
> 1. **严禁手算像素坐标布局节点**：无论是否有 `mermaid_layout` 输出，diagram 卡布局**必须**走 CSS Grid / Flex，**绝不**用 `position:absolute; left:NNpx; top:NNpx` 给节点定位——这条在 ad-hoc 路径下同样生效。
> 2. **节点字号下限**：主标签 ≥ **14px**、副标签（tech sub-label、说明行）≥ **12px**、连线标注 ≥ **11px**。此下限**优先于** `density_contract.min_body_font_px`，在 mermaid_layout.py 路径和 ad-hoc 路径中均强制执行。
> 3. **节点防溢出与文字留白**：每个节点盒子必须写 `min-width` + `min-height` + `box-sizing:border-box`，禁止依赖 `overflow:hidden` 裁掉节点文字——文字消失不是溢出防护，是渲染错误。内边距至少 **14px 上下 / 20px 左右**，`line-height` ≥ **1.4**——文字不得紧贴节点边框。节点宽应满足 `文本长度 × 字宽 + padding × 2`；多行标签用 `white-space:normal; word-break:break-word` 让节点自然撑高，不得硬设固定高度截断内容。

本页若含 `card_type:diagram` 卡（family 配方已由 `block_refs` 注入），**先声明结构，再落 HTML**：

1. **先写结构清单（不落坐标）**：节点列表（含所属 zone / 分组）+ 连线列表（源→目标 + 方向）。这一步只在对话里想清楚，不写进 HTML。
2. **分层/网格指派**：按数据流方向做拓扑分层（源在前、汇在后），每层一列/一行；用 **CSS Grid 按层排布**（`display:grid; grid-template-columns/rows` + `gap` 取 8 的倍数），让节点落在网格线上——**不要手摆自由 SVG 坐标**。Grid `gap` 最小 **32px**（连线需要这个空间穿过而不贴边）。
3. **几何用变量、不用漂移字面量**：`--grid-unit` / `--node-w` / `--node-h` 定义一次，连线锚点用它们**算出来**（如中点 `--node-w/2`），换算全程代数化，避免每个节点各写一套会漂移的数字。
4. **分组容器内边距**：zone / subgraph 容器内边距至少 `20px`（水平）和 `28px`（顶部，留标签行） + `20px`（底部）。节点绝不应贴着分组边框——贴边的节点会让连线与边框叠压。
5. **连线间距**：多条平行连线（fan-in / fan-out）在同一节点边沿的间隔不小于 **12px**；若连线太多导致 12px 无法满足，改用**总线**（汇集成一根，再在目标侧分叉）。如果水平宽度放不下所有列，**缩小节点（`--node-w`）而非压缩列间距**——列间距优先保证 32px。
6. 连线拓扑严格照 `blocks/diagram.md` §3.1：终点**夹进目标节点包围盒**（禁止照抄源 center-y）、多对一 fan-in 沿目标边 `a+(b−a)·i/(N+1)` 均匀铺开、稠密同组多对多改**总线**。

## Phase 8：完成条件

写入目标 HTML 文件后：
- 文件非空
- 格式绝对纯净：HTML 中不得以可见文本形式包含大模型思考过程（如阴阳自检、摘要阐述、策略说明等与实际幻灯片不相关的文字）
- 无语法错误（HTML 标签闭合完整）
- 没有明显乱码或缺失的 CSS 变量引用
- `planning.cards[]` 全部能在 HTML 中找到对应的 `data-card-id`
- **【图解首过静态自检 —— 仅本页含 diagram 卡时】**（对着代码/结构核对，不截图，属本阶段边界内）：
  - **布局方式**：节点用 CSS Grid / Flex 布局，**没有** `position:absolute; left:NNpx; top:NNpx` 给节点定位（连线 SVG 的 `<line>`/`<path>` 例外）。
  - **字号合规**：在代码中确认实际声明值（非继承推算）：主标签 ≥ 14px、副标签 ≥ 12px、连线标注 ≥ 11px。
  - **节点防溢出**：每个节点都有 `min-width`/`min-height` + `box-sizing:border-box`；无 `overflow:hidden` 截断文字；多行文本用 `white-space:normal; word-break:break-word` 自然撑高。
  - 每条连线终点都**落在目标节点包围盒内**（无 overshoot、无照抄源 center-y）；fan-in 已沿目标边均匀分布；稠密同组多对多用了总线而非 N×M 斜线（依据 `blocks/diagram.md` §3.1）。
  - 同层节点无相互重叠（成对包围盒不相交）。
  - 管线安全自检通过（`blocks/diagram.md`「管线安全自检」全绿：无 SVG `<text>`、箭头为 `<polygon>`、连线为真实 `<div>`/`<line>`/`<path>`、颜色全走主题变量）。
  - 任一项不过 → 就地修，别指望 Review 兜底。

发送 FINALIZE 信号，然后等待 Review 阶段指令。
