# diagram-concept（概念与 SVG 隐喻族）

> family `block_ref`: `diagram-concept`。配方：`mind-map` / `matrix-quadrant`（含 `consultant-2x2` / `quadrant-trajectory` 变体） / `venn` / `pyramid` / `funnel` / `cycle` / `hub-spoke` / `onion` / `fishbone` / `spectrum-marker` / `iceberg` / `force-field` / `before-after` / `causal-loop`。
> 前置：先读 `blocks/diagram.md` 的**主题契约**与**共享基元**（节点盒/连线/箭头/标注/8px 栅格）。本族所有模板的颜色字体只用契约里的局部变量。
> 管线：HTML→SVG→PPTX，遵守 pipeline-compat.md（SVG `<polygon>`/`<path>`/`<circle>` 几何，HTML 叠加标注，禁 `<text>`/`mask-image`/`conic-gradient`/`background-clip:text`）。

---

### 思维导图 (mind-map)

**何时用**：辐射状主题层级；头脑风暴、概念分解、知识地图；中心节点 + 一级子主题 + 可选二级子主题。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "mind-map",
  "center": {"label": "数字化转型"},
  "branches": [
    {"label": "技术升级", "children": ["云原生", "AI 平台"]},
    {"label": "流程再造", "children": ["自动化", "低代码"]},
    {"label": "数据驱动", "children": ["实时分析", "数据治理"]},
    {"label": "组织变革", "children": ["敏捷团队", "人才引进"]}
  ]
}
```

**模板**（中心节点 + 辐射子节点 + 弯曲路径连线）：
```html
<div class="diagram mind-map" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:640px; height:480px;">

  <!-- SVG 连线层（只画路径，无 <text>） -->
  <svg viewBox="0 0 640 480" style="position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;display:block;">
    <!-- 上方：技术升级 -->
    <path d="M320 240 C320 200 200 160 160 140" fill="none" stroke="var(--node-accent)" stroke-width="2.5" stroke-linecap="round"/>
    <!-- 右上：流程再造 -->
    <path d="M320 240 C340 200 440 160 480 140" fill="none" stroke="var(--node-accent-2)" stroke-width="2.5" stroke-linecap="round"/>
    <!-- 下方：数据驱动 -->
    <path d="M320 240 C320 280 200 320 160 340" fill="none" stroke="var(--node-accent)" stroke-width="2.5" stroke-linecap="round"/>
    <!-- 右下：组织变革 -->
    <path d="M320 240 C340 280 440 320 480 340" fill="none" stroke="var(--node-accent-2)" stroke-width="2.5" stroke-linecap="round"/>
    <!-- 二级：技术升级子项 -->
    <path d="M160 140 C120 130 96 110 80 100" fill="none" stroke="var(--edge)" stroke-width="1.5" stroke-linecap="round"/>
    <path d="M160 140 C120 148 96 156 80 164" fill="none" stroke="var(--edge)" stroke-width="1.5" stroke-linecap="round"/>
    <!-- 二级：流程再造子项 -->
    <path d="M480 140 C510 130 536 110 560 100" fill="none" stroke="var(--edge)" stroke-width="1.5" stroke-linecap="round"/>
    <path d="M480 140 C510 148 536 156 560 164" fill="none" stroke="var(--edge)" stroke-width="1.5" stroke-linecap="round"/>
    <!-- 二级：数据驱动子项 -->
    <path d="M160 340 C120 330 96 314 80 304" fill="none" stroke="var(--edge)" stroke-width="1.5" stroke-linecap="round"/>
    <path d="M160 340 C120 350 96 362 80 374" fill="none" stroke="var(--edge)" stroke-width="1.5" stroke-linecap="round"/>
    <!-- 二级：组织变革子项 -->
    <path d="M480 340 C510 330 536 314 560 304" fill="none" stroke="var(--edge)" stroke-width="1.5" stroke-linecap="round"/>
    <path d="M480 340 C510 350 536 362 560 374" fill="none" stroke="var(--edge)" stroke-width="1.5" stroke-linecap="round"/>
  </svg>

  <!-- 中心节点 -->
  <div style="position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
    min-width:112px; min-height:56px; padding:12px 16px; box-sizing:border-box;
    background:var(--node-accent); border-radius:var(--node-radius);
    color:var(--card-bg-from); font-weight:800; font-size:15px;
    text-align:center; display:flex; align-items:center; justify-content:center;">数字化转型</div>

  <!-- 一级：技术升级 -->
  <div style="position:absolute; left:92px; top:118px; transform:translate(-50%,-50%);
    min-width:88px; padding:8px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1.5px solid var(--node-accent); border-radius:var(--node-radius);
    color:var(--node-fg); font-weight:700; font-size:13px; text-align:center;">技术升级</div>

  <!-- 一级：流程再造 -->
  <div style="position:absolute; left:548px; top:118px; transform:translate(-50%,-50%);
    min-width:88px; padding:8px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1.5px solid var(--node-accent-2); border-radius:var(--node-radius);
    color:var(--node-fg); font-weight:700; font-size:13px; text-align:center;">流程再造</div>

  <!-- 一级：数据驱动 -->
  <div style="position:absolute; left:92px; top:362px; transform:translate(-50%,-50%);
    min-width:88px; padding:8px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1.5px solid var(--node-accent); border-radius:var(--node-radius);
    color:var(--node-fg); font-weight:700; font-size:13px; text-align:center;">数据驱动</div>

  <!-- 一级：组织变革 -->
  <div style="position:absolute; left:548px; top:362px; transform:translate(-50%,-50%);
    min-width:88px; padding:8px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1.5px solid var(--node-accent-2); border-radius:var(--node-radius);
    color:var(--node-fg); font-weight:700; font-size:13px; text-align:center;">组织变革</div>

  <!-- 二级叶节点（font-size:11px，无边框，dim 色） -->
  <span style="position:absolute; left:24px; top:80px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">云原生</span>
  <span style="position:absolute; left:24px; top:144px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">AI 平台</span>
  <span style="position:absolute; left:512px; top:80px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">自动化</span>
  <span style="position:absolute; left:512px; top:144px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">低代码</span>
  <span style="position:absolute; left:24px; top:284px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">实时分析</span>
  <span style="position:absolute; left:24px; top:354px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">数据治理</span>
  <span style="position:absolute; left:512px; top:284px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">敏捷团队</span>
  <span style="position:absolute; left:512px; top:354px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">人才引进</span>
</div>
```
> 辐射规律：中心节点绝对居中；一级子节点用 `position:absolute` 均匀布置在四象限；SVG 只画路径（`<path>`），无 `<text>`；叶节点用 `<span>` HTML 文字。

**自检**：连线是 SVG `<path>`（弯曲）；中心节点用 `--node-accent` 实底；一级节点 accent 描边区分；叶节点 dim 色 HTML `<span>`；所有颜色来自契约变量。

**管线安全**：无 SVG `<text>`；无伪元素连线；无 `mask-image`/`conic-gradient`；连线 `<path>` 有 `overflow:visible`。

---

### 矩阵/象限图 (matrix-quadrant)

**何时用**：2D 优先级定位（机会/威胁、影响/可行性）；也作 SWOT（填满四象限文字列表）/ RACI（行列交叉分配矩阵）/ 风险矩阵（色阶填色）的单一配方——三种变体只改单元格填充内容，结构相同。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "matrix-quadrant",
  "x_label": "实施难度", "y_label": "业务价值",
  "quadrants": ["低价值·低难度", "低价值·高难度", "高价值·低难度（速赢）", "高价值·高难度（战略）"],
  "items": [
    {"label": "项目 A", "x": 0.25, "y": 0.75},
    {"label": "项目 B", "x": 0.75, "y": 0.80},
    {"label": "项目 C", "x": 0.55, "y": 0.35}
  ]
}
```

**模板**（带轴标注 + 象限标签 + 散点 HTML 叠加）：
```html
<div class="diagram matrix-quadrant" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:560px; height:480px;">

  <!-- 轴线 SVG -->
  <svg viewBox="0 0 560 480" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
    <!-- Y 轴 -->
    <line x1="80" y1="24" x2="80" y2="440" stroke="var(--edge)" stroke-width="1.5"/>
    <polygon points="74,30 80,16 86,30" fill="var(--edge)"/>
    <!-- X 轴 -->
    <line x1="80" y1="440" x2="536" y2="440" stroke="var(--edge)" stroke-width="1.5"/>
    <polygon points="530,434 544,440 530,446" fill="var(--edge)"/>
    <!-- 中线十字 -->
    <line x1="80" y1="232" x2="536" y2="232" stroke="var(--edge)" stroke-width="1" stroke-dasharray="4 4"/>
    <line x1="308" y1="24" x2="308" y2="440" stroke="var(--edge)" stroke-width="1" stroke-dasharray="4 4"/>
  </svg>

  <!-- 轴标签（HTML，非 SVG text） -->
  <span style="position:absolute; left:80px; top:444px; transform:translateX(-50%);
    font-size:11px; color:var(--node-fg-dim);">低</span>
  <span style="position:absolute; left:536px; top:444px; transform:translateX(-50%);
    font-size:11px; color:var(--node-fg-dim);">高</span>
  <span style="position:absolute; left:56px; top:440px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim);">低</span>
  <span style="position:absolute; left:56px; top:24px; transform:translateY(-50%);
    font-size:11px; color:var(--node-fg-dim);">高</span>
  <!-- X 轴名称 -->
  <span style="position:absolute; left:308px; top:468px; transform:translateX(-50%);
    font-size:12px; font-weight:700; color:var(--node-fg-dim);">实施难度 →</span>
  <!-- Y 轴名称 -->
  <span style="position:absolute; left:8px; top:232px; transform:translateY(-50%) rotate(-90deg);
    font-size:12px; font-weight:700; color:var(--node-fg-dim); transform-origin:left center;">↑ 业务价值</span>

  <!-- 象限标签 -->
  <span style="position:absolute; left:96px; top:32px; font-size:11px; color:var(--node-fg-dim); opacity:0.6;">高价值·低难度（速赢）</span>
  <span style="position:absolute; left:320px; top:32px; font-size:11px; color:var(--node-fg-dim); opacity:0.6;">高价值·高难度（战略）</span>
  <span style="position:absolute; left:96px; top:248px; font-size:11px; color:var(--node-fg-dim); opacity:0.6;">低价值·低难度</span>
  <span style="position:absolute; left:320px; top:248px; font-size:11px; color:var(--node-fg-dim); opacity:0.6;">低价值·高难度</span>

  <!-- 散点：x/y 为 0-1 比例，映射到 [80,536] x [440,24] -->
  <!-- 项目 A: x=0.25→x_px=80+0.25*456=194, y=0.75→y_px=440-0.75*416=128 -->
  <div style="position:absolute; left:194px; top:128px; transform:translate(-50%,-50%);
    width:40px; height:40px; border-radius:50%;
    background:var(--node-accent); opacity:0.9;
    display:flex; align-items:center; justify-content:center;
    font-size:11px; font-weight:700; color:var(--card-bg-from);">A</div>

  <!-- 项目 B: x=0.75→x_px=80+0.75*456=422, y=0.80→y_px=440-0.80*416=107 -->
  <div style="position:absolute; left:422px; top:107px; transform:translate(-50%,-50%);
    width:40px; height:40px; border-radius:50%;
    background:var(--node-accent); opacity:0.9;
    display:flex; align-items:center; justify-content:center;
    font-size:11px; font-weight:700; color:var(--card-bg-from);">B</div>

  <!-- 项目 C: x=0.55→x_px=80+0.55*456=331, y=0.35→y_px=440-0.35*416=294 -->
  <div style="position:absolute; left:331px; top:294px; transform:translate(-50%,-50%);
    width:40px; height:40px; border-radius:50%;
    background:var(--node-accent-2); opacity:0.85;
    display:flex; align-items:center; justify-content:center;
    font-size:11px; font-weight:700; color:var(--card-bg-from);">C</div>

  <!-- 散点标签 -->
  <span style="position:absolute; left:210px; top:108px; font-size:11px; color:var(--node-fg-dim);">项目 A</span>
  <span style="position:absolute; left:438px; top:87px; font-size:11px; color:var(--node-fg-dim);">项目 B</span>
  <span style="position:absolute; left:347px; top:274px; font-size:11px; color:var(--node-fg-dim);">项目 C</span>
</div>
```
> SWOT 变体：4 象限改为静态文字列表（`position:absolute` 的 `<div>` 填充到各象限区域）。RACI 变体：行列矩阵改用 `display:grid` HTML 表格；散点改为单元格内 R/A/C/I 文字。风险变体：各象限背景用 `linear-gradient` 填浅色（契约变量 + 不同 `opacity`）。

**自检**：轴线/箭头 SVG `<polygon>`；轴标签/象限标签/散点标签全是 HTML `<span>`；散点是 `border-radius:50%` div；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；轴箭头用 `<polygon>`；无伪元素；无 `mask-image`/`conic-gradient`。

#### 顾问 2×2 情景矩阵（consultant-2x2 变体）

`diagram_type: "consultant-2x2"`（同族路由到本配方）。用于**四种未来/四种战略选项**的情景框架（BCG/麦肯锡式），不是散点定位。与基础 matrix-quadrant 的差异只有四点，模板其余部分复用上面的轴线骨架：

1. **双向轴**：X/Y 轴线两端各加一个 `<polygon>` 箭头（`marker-start` + `marker-end` 语义），线宽 `stroke-width:1.2`（轴承担更多信息）。
2. **命名单元格**：四个象限不放散点，改放 `position:absolute` 的 `<div>` 卡片，每格含一个标题（`font-weight:700; font-size:16px; color:var(--node-fg)`）+ 1–3 行描述（`font-size:11px; color:var(--node-fg-dim)`）。
3. **单一焦点格**：只有一个象限着色 —— `background:var(--node-accent); opacity:0.06` 的整格底 + `border:1px solid var(--node-accent)`；其余三格 `border:1px solid var(--node-border)`。选两个焦点等于没有焦点。
4. **Jobs 式轴标**：每个箭头端点只放**一个词**（HTML `<span>`），不带 `↑→` 字形、不带「高/低」括注、不在轴中点放标签。角标编号用 mono：`NN · 维度A / 维度B`。

```html
<!-- 双向轴片段（替换基础模板的单向轴线；其余骨架不变） -->
<svg viewBox="0 0 560 480" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
  <line x1="308" y1="30" x2="308" y2="450" stroke="var(--edge)" stroke-width="1.2"/>
  <polygon points="302,36 308,22 314,36" fill="var(--edge)"/>
  <polygon points="302,444 308,458 314,444" fill="var(--edge)"/>
  <line x1="70" y1="240" x2="546" y2="240" stroke="var(--edge)" stroke-width="1.2"/>
  <polygon points="76,234 62,240 76,246" fill="var(--edge)"/>
  <polygon points="540,234 554,240 540,246" fill="var(--edge)"/>
</svg>
<!-- 焦点单元格（右上，唯一着色）：底色单独一层用 opacity（不含 border），描边放在满不透明的内容层 -->
<div style="position:absolute; left:320px; top:40px; width:210px; height:130px; box-sizing:border-box;
  background:var(--node-accent); opacity:0.06; border-radius:var(--node-radius);"></div>
<div style="position:absolute; left:320px; top:40px; width:210px; height:130px; padding:14px 16px; box-sizing:border-box;
  border:1px solid var(--node-accent); border-radius:var(--node-radius);">
  <div style="font-weight:700; font-size:16px; color:var(--node-accent);">领跑者</div>
  <div style="font-size:11px; color:var(--node-fg-dim); line-height:1.6;">高增长 · 高份额：优先加注</div>
</div>
```

**自检（变体）**：轴两端各一 `<polygon>`；仅 1 格着色（`--node-accent` + 低 opacity 底）；轴标一词、无字形/括注；角标 mono；颜色全用契约变量。

#### 象限轨迹图（quadrant-trajectory 变体）

`diagram_type: "quadrant-trajectory"`（同族路由到本配方）。在基础散点 2×2 上叠加**从"现状点"到"目标点"的移动箭头**，一张图说清"我们在哪 → 要去哪"，省掉单独的前后对比页。差异：

- 现状点用**空心圆**（`fill:transparent; stroke:var(--node-fg-dim); stroke-width:1.5`），目标点用**实心 accent 圆**。
- 两点之间加一条 `<line>` + `<polygon>` 箭头（`stroke="var(--edge-strong)"`，可 `stroke-dasharray="5 4"` 表意图）。

```html
<!-- 轨迹：现状(空心) → 目标(实心 accent)，叠加在基础散点层之上 -->
<svg viewBox="0 0 560 480" style="position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;display:block;">
  <line x1="200" y1="300" x2="410" y2="130" stroke="var(--edge-strong)" stroke-width="2" stroke-dasharray="5 4"/>
  <polygon points="420,120 408,144 400,133" fill="var(--edge-strong)"/>
  <circle cx="200" cy="300" r="9" fill="transparent" stroke="var(--node-fg-dim)" stroke-width="1.5"/>
  <circle cx="410" cy="130" r="9" fill="var(--node-accent)"/>
</svg>
<span style="position:absolute; left:170px; top:312px; font-size:11px; color:var(--node-fg-dim);">现状</span>
<span style="position:absolute; left:420px; top:118px; font-size:11px; color:var(--node-fg);">2027 目标</span>
```

**自检（变体）**：现状空心 / 目标实心；轨迹 `<line>`+`<polygon>` 箭头用 `--edge-strong`；标注 HTML `<span>`；颜色全用契约变量。

---

### 韦恩图 (venn)

**何时用**：集合交叉/共性分析；2–3 个圈对比共有属性；适合"两者相同之处在哪"的演示逻辑。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "venn",
  "circles": [
    {"label": "用户需求", "items": ["个性化", "低价格", "便捷性"]},
    {"label": "技术能力", "items": ["AI 推荐", "实时处理", "弹性扩容"]}
  ],
  "overlap": {"label": "产品机会", "items": ["智能定价", "精准推送"]}
}
```

**模板**（两个半透明圆 + HTML 叠加标注）：
```html
<div class="diagram venn" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:600px; height:360px;">

  <!-- SVG 圆形几何（无 <text>） -->
  <svg viewBox="0 0 600 360" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
    <!-- 左圆 -->
    <circle cx="220" cy="180" r="150" fill="var(--node-accent)" opacity="0.18"
      stroke="var(--node-accent)" stroke-width="1.5"/>
    <!-- 右圆 -->
    <circle cx="380" cy="180" r="150" fill="var(--node-accent-2)" opacity="0.18"
      stroke="var(--node-accent-2)" stroke-width="1.5"/>
  </svg>

  <!-- 左区标签 -->
  <div style="position:absolute; left:72px; top:50%; transform:translateY(-50%);
    width:112px; text-align:center;">
    <div style="font-weight:700; font-size:14px; color:var(--node-fg); margin-bottom:8px;">用户需求</div>
    <div style="font-size:11px; color:var(--node-fg-dim); line-height:1.8;">个性化<br>低价格<br>便捷性</div>
  </div>

  <!-- 右区标签 -->
  <div style="position:absolute; right:72px; top:50%; transform:translateY(-50%);
    width:112px; text-align:center;">
    <div style="font-weight:700; font-size:14px; color:var(--node-fg); margin-bottom:8px;">技术能力</div>
    <div style="font-size:11px; color:var(--node-fg-dim); line-height:1.8;">AI 推荐<br>实时处理<br>弹性扩容</div>
  </div>

  <!-- 交叉区标签（居中） -->
  <div style="position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
    width:100px; text-align:center;">
    <div style="font-weight:800; font-size:13px; color:var(--node-fg); margin-bottom:6px;">产品机会</div>
    <div style="font-size:11px; color:var(--node-fg-dim); line-height:1.8;">智能定价<br>精准推送</div>
  </div>
</div>
```
> 三圆变体：第三个 `<circle>` 置于底部中间，cx=300, cy=290, r=150；三个交叉区分别用更小的 `<span>` 标注。

**自检**：圆形用 SVG `<circle>`；颜色用 `--node-accent`/`--node-accent-2` + `opacity`（非硬编码）；标注全是 HTML；两圆描边 `stroke-width:1.5`。

**管线安全**：无 SVG `<text>`；无 `mask-image`；无伪元素；SVG 半透明圆形管线安全。

---

### 金字塔 (pyramid)

**何时用**：层级重要性/优先级（从基础到顶层）；马斯洛、技术栈分层、价值层级；层越往上越小代表越稀少/高价值。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "pyramid",
  "layers": [
    {"label": "自我实现", "desc": ""},
    {"label": "尊重需求", "desc": ""},
    {"label": "社交需求", "desc": ""},
    {"label": "安全需求", "desc": ""},
    {"label": "生理需求", "desc": "最基础"}
  ]
}
```

**模板**（`<polygon>` 梯形切片叠加 + HTML 标注）：
```html
<div class="diagram pyramid" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:560px; height:400px;">

  <!-- SVG 梯形切片（从下至上：底部最宽，顶部最窄）-->
  <!-- viewBox: 560x400; 金字塔底部 x=40..520, 顶部 x=260..300 -->
  <!-- 5 层，每层高度 72px，从 y=40(顶) 到 y=400(底) -->
  <!-- 层 5（底）y=328..400: x_bot=40..520, x_top=96..464 -->
  <!-- 层 4 y=256..328: x_bot=96..464, x_top=152..408 -->
  <!-- 层 3 y=184..256: x_bot=152..408, x_top=208..352 -->
  <!-- 层 2 y=112..184: x_bot=208..352, x_top=232..328 -->
  <!-- 层 1（顶）y=40..112: x_bot=232..328, x_top=264..296 -->
  <svg viewBox="0 0 560 400" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
    <!-- 底层：生理需求 - 最淡 -->
    <polygon points="40,400 520,400 464,328 96,328" fill="var(--node-accent)" opacity="0.30"
      stroke="var(--node-border)" stroke-width="1.5"/>
    <!-- 第4层：安全需求 -->
    <polygon points="96,328 464,328 408,256 152,256" fill="var(--node-accent)" opacity="0.45"
      stroke="var(--node-border)" stroke-width="1.5"/>
    <!-- 第3层：社交需求 -->
    <polygon points="152,256 408,256 352,184 208,184" fill="var(--node-accent)" opacity="0.60"
      stroke="var(--node-border)" stroke-width="1.5"/>
    <!-- 第2层：尊重需求 -->
    <polygon points="208,184 352,184 328,112 232,112" fill="var(--node-accent)" opacity="0.78"
      stroke="var(--node-border)" stroke-width="1.5"/>
    <!-- 顶层：自我实现 - 最深 -->
    <polygon points="232,112 328,112 296,40 264,40" fill="var(--node-accent)" opacity="1.0"
      stroke="var(--node-border)" stroke-width="1.5"/>
  </svg>

  <!-- HTML 标注（绝对定位在各层中心） -->
  <!-- 层 1（顶）中心 y=(40+112)/2=76 -->
  <span style="position:absolute; left:50%; top:76px; transform:translate(-50%,-50%);
    font-weight:800; font-size:12px; color:var(--card-bg-from); white-space:nowrap;">自我实现</span>
  <!-- 层 2 中心 y=(112+184)/2=148 -->
  <span style="position:absolute; left:50%; top:148px; transform:translate(-50%,-50%);
    font-weight:700; font-size:13px; color:var(--card-bg-from); white-space:nowrap;">尊重需求</span>
  <!-- 层 3 中心 y=(184+256)/2=220 -->
  <span style="position:absolute; left:50%; top:220px; transform:translate(-50%,-50%);
    font-weight:700; font-size:13px; color:var(--node-fg); white-space:nowrap;">社交需求</span>
  <!-- 层 4 中心 y=(256+328)/2=292 -->
  <span style="position:absolute; left:50%; top:292px; transform:translate(-50%,-50%);
    font-weight:700; font-size:13px; color:var(--node-fg); white-space:nowrap;">安全需求</span>
  <!-- 层 5（底）中心 y=(328+400)/2=364 -->
  <span style="position:absolute; left:50%; top:364px; transform:translate(-50%,-50%);
    font-weight:700; font-size:13px; color:var(--node-fg); white-space:nowrap;">生理需求</span>
</div>
```
> 几何规律：N 层金字塔把宽度均匀从底（全宽）收缩到顶（极窄）；每层是 `<polygon>` 梯形（4 顶点：左下、右下、右上、左上）；opacity 从底向上递增制造层次感；层内文字是 HTML `<span>` 绝对定位。

**自检**：梯形切片全是 SVG `<polygon>`；标注全是 HTML `<span>`；颜色用 `--node-accent` + `opacity` 渐变；无硬编码色值。

**管线安全**：无 SVG `<text>`；无 CSS border 三角形；无 `mask-image`；无伪元素。

---

### 漏斗图 (funnel)

**何时用**：转化/筛选流程（销售漏斗、招募漏斗、用户激活路径）；从上到下阶段依次收窄代表逐级转化损失。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "funnel",
  "stages": [
    {"label": "访问", "value": 10000},
    {"label": "注册", "value": 4200},
    {"label": "激活", "value": 1800},
    {"label": "付费", "value": 620},
    {"label": "复购", "value": 310}
  ]
}
```

**模板**（`<polygon>` 梯形向下收窄 + 数值 HTML 叠加）：
```html
<div class="diagram funnel" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:480px; height:400px;">

  <!-- SVG 梯形漏斗（5 段，向下收窄）-->
  <!-- 顶宽 480, 底宽 80, 每段高 72px -->
  <!-- 段1 y=0..72:  left=0..400,  right=400..480 → 上宽 480, 下宽 380 → 缩减 25px/侧 per step -->
  <!-- 每段宽度：480, 380, 280, 180, 80; margin=0, 50, 100, 150, 200 -->
  <svg viewBox="0 0 480 400" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
    <!-- 段1：访问 margin=0 -->
    <polygon points="0,0 480,0 430,72 50,72" fill="var(--node-accent)" opacity="0.85"
      stroke="var(--node-border)" stroke-width="1"/>
    <!-- 段2：注册 margin=50 -->
    <polygon points="50,80 430,80 380,152 100,152" fill="var(--node-accent)" opacity="0.70"
      stroke="var(--node-border)" stroke-width="1"/>
    <!-- 段3：激活 margin=100 -->
    <polygon points="100,160 380,160 330,232 150,232" fill="var(--node-accent)" opacity="0.55"
      stroke="var(--node-border)" stroke-width="1"/>
    <!-- 段4：付费 margin=150 -->
    <polygon points="150,240 330,240 280,312 200,312" fill="var(--node-accent)" opacity="0.42"
      stroke="var(--node-border)" stroke-width="1"/>
    <!-- 段5：复购 margin=200 -->
    <polygon points="200,320 280,320 260,392 220,392" fill="var(--node-accent)" opacity="0.30"
      stroke="var(--node-border)" stroke-width="1"/>
  </svg>

  <!-- HTML 标注（居中于各段） -->
  <div style="position:absolute; left:50%; top:36px; transform:translate(-50%,-50%);
    display:flex; gap:16px; align-items:baseline;">
    <span style="font-weight:700; font-size:14px; color:var(--card-bg-from);">访问</span>
    <span style="font-size:13px; color:var(--card-bg-from); opacity:0.85; font-variant-numeric:tabular-nums;">10,000</span>
  </div>
  <div style="position:absolute; left:50%; top:116px; transform:translate(-50%,-50%);
    display:flex; gap:16px; align-items:baseline;">
    <span style="font-weight:700; font-size:14px; color:var(--card-bg-from);">注册</span>
    <span style="font-size:13px; color:var(--card-bg-from); opacity:0.85; font-variant-numeric:tabular-nums;">4,200</span>
  </div>
  <div style="position:absolute; left:50%; top:196px; transform:translate(-50%,-50%);
    display:flex; gap:16px; align-items:baseline;">
    <span style="font-weight:700; font-size:14px; color:var(--node-fg);">激活</span>
    <span style="font-size:13px; color:var(--node-fg-dim); font-variant-numeric:tabular-nums;">1,800</span>
  </div>
  <div style="position:absolute; left:50%; top:276px; transform:translate(-50%,-50%);
    display:flex; gap:16px; align-items:baseline;">
    <span style="font-weight:700; font-size:14px; color:var(--node-fg);">付费</span>
    <span style="font-size:13px; color:var(--node-fg-dim); font-variant-numeric:tabular-nums;">620</span>
  </div>
  <div style="position:absolute; left:50%; top:356px; transform:translate(-50%,-50%);
    display:flex; gap:16px; align-items:baseline;">
    <span style="font-weight:700; font-size:14px; color:var(--node-fg);">复购</span>
    <span style="font-size:13px; color:var(--node-fg-dim); font-variant-numeric:tabular-nums;">310</span>
  </div>
</div>
```
> 几何规律：每段是 4 顶点梯形 `<polygon>`，上边宽 > 下边宽；段间留 8px 间隙（y 跳 8）；opacity 从上向下递减制造消耗感。数值/标签是 HTML `<div>` 绝对居中。

**自检**：梯形全是 SVG `<polygon>`；数值 `font-variant-numeric:tabular-nums`；opacity 渐减表达转化损失；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；无 CSS border 三角形；无 `mask-image`/`conic-gradient`；段间隙是 y 偏移，非伪元素。

---

### 循环/飞轮图 (cycle)

**何时用**：闭环流程/循环增强逻辑（PDCA、飞轮效应、生命周期）；强调阶段间的循环依赖而非单向线性。也用于飞轮变体（加粗弧线 + 中心驱动力文字）。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "cycle",
  "stages": [
    {"label": "计划", "desc": "Plan"},
    {"label": "执行", "desc": "Do"},
    {"label": "检查", "desc": "Check"},
    {"label": "改进", "desc": "Act"}
  ],
  "center": "PDCA"
}
```

**模板**（`<path>` 弧段 + `<polygon>` 箭头 + HTML 叠加标注）：
```html
<div class="diagram cycle" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --edge-strong:var(--accent-1);
  --node-accent:var(--accent-1); --node-accent-2:var(--accent-2);
  --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:480px; height:480px;">

  <!-- SVG 弧段（4段，每段 80° 弧+10° 间隔, strokeWidth=40, r=160, cx=cy=240） -->
  <!-- 各段起点（顺时针，从 -90° 开始）：-90°、0°、90°、180° -->
  <!-- stroke-dasharray 技巧：弧长 = r*弧度 = 160*(80°/180°*π)=223; 圆周=160*2π=1005 -->
  <svg viewBox="0 0 480 480" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
    <!-- 弧段1（计划）: -90°→-10° = 从顶开始顺时针80° -->
    <circle cx="240" cy="240" r="160" fill="none"
      stroke="var(--node-accent)" stroke-width="40" stroke-linecap="butt"
      stroke-dasharray="223 1005"
      transform="rotate(-90 240 240)"/>
    <!-- 弧段2（执行）: 0°→80° -->
    <circle cx="240" cy="240" r="160" fill="none"
      stroke="var(--node-accent)" stroke-width="40" stroke-linecap="butt"
      stroke-dasharray="223 1005"
      transform="rotate(0 240 240)"/>
    <!-- 弧段3（检查）: 90°→170° -->
    <circle cx="240" cy="240" r="160" fill="none"
      stroke="var(--node-accent-2)" stroke-width="40" stroke-linecap="butt"
      stroke-dasharray="223 1005"
      transform="rotate(90 240 240)"/>
    <!-- 弧段4（改进）: 180°→260° -->
    <circle cx="240" cy="240" r="160" fill="none"
      stroke="var(--node-accent-2)" stroke-width="40" stroke-linecap="butt"
      stroke-dasharray="223 1005"
      transform="rotate(180 240 240)"/>
    <!-- 中心圆 -->
    <circle cx="240" cy="240" r="60" fill="var(--node-bg-from)" stroke="var(--node-border)" stroke-width="1.5"/>
    <!-- 箭头（4个，位于各段末端位置，顺时针方向） -->
    <!-- 箭头1：段1 末端 约在 -10°，r=160，位置(240+160*cos(-10°), 240+160*sin(-10°))≈(397,212) 指向下→右 -->
    <polygon points="400,220 395,208 410,214" fill="var(--node-accent)" transform="rotate(80 240 240)"/>
    <!-- 箭头2：段2 末端 约在 80° -->
    <polygon points="400,220 395,208 410,214" fill="var(--node-accent)" transform="rotate(170 240 240)"/>
    <!-- 箭头3：段3 末端 约在 170° -->
    <polygon points="400,220 395,208 410,214" fill="var(--node-accent-2)" transform="rotate(260 240 240)"/>
    <!-- 箭头4：段4 末端 约在 260° -->
    <polygon points="400,220 395,208 410,214" fill="var(--node-accent-2)" transform="rotate(350 240 240)"/>
  </svg>

  <!-- 中心文字 HTML -->
  <div style="position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
    text-align:center; font-weight:800; font-size:18px; color:var(--node-fg);">PDCA</div>

  <!-- 各阶段标注：r=220（弧外侧），各段中心角 -50°, 40°, 130°, 220° -->
  <!-- cos(-50°)=0.643, sin=-0.766 → 240+220*0.643=381, 240-220*0.766=72 -->
  <div style="position:absolute; left:381px; top:72px; transform:translate(-50%,-50%);
    text-align:center; min-width:56px;">
    <div style="font-weight:700; font-size:13px; color:var(--node-fg);">计划</div>
    <div style="font-size:11px; color:var(--node-fg-dim);">Plan</div>
  </div>
  <!-- cos(40°)=0.766, sin=0.643 → 240+220*0.766=409, 240+220*0.643=381 -->
  <div style="position:absolute; left:409px; top:381px; transform:translate(-50%,-50%);
    text-align:center; min-width:56px;">
    <div style="font-weight:700; font-size:13px; color:var(--node-fg);">执行</div>
    <div style="font-size:11px; color:var(--node-fg-dim);">Do</div>
  </div>
  <!-- cos(130°)=-0.643, sin=0.766 → 240-220*0.643=99, 240+220*0.766=408 -->
  <div style="position:absolute; left:99px; top:408px; transform:translate(-50%,-50%);
    text-align:center; min-width:56px;">
    <div style="font-weight:700; font-size:13px; color:var(--node-fg);">检查</div>
    <div style="font-size:11px; color:var(--node-fg-dim);">Check</div>
  </div>
  <!-- cos(220°)=-0.766, sin=-0.643 → 240-220*0.766=71, 240-220*0.643=99 -->
  <div style="position:absolute; left:71px; top:99px; transform:translate(-50%,-50%);
    text-align:center; min-width:56px;">
    <div style="font-weight:700; font-size:13px; color:var(--node-fg);">改进</div>
    <div style="font-size:11px; color:var(--node-fg-dim);">Act</div>
  </div>
</div>
```
> 弧段技巧：用 `stroke-dasharray` 在 `<circle>` 上截取固定弧长，`transform:rotate` 定位起点；`stroke-width:40` 制造扇形视觉；方向箭头用 `<polygon>` + `transform:rotate` 旋转到弧末位置；禁止 `stroke-dashoffset`。

**自检**：弧段用 `<circle>` + `stroke-dasharray`（禁 `dashoffset`）；箭头 `<polygon>` + rotate；中心文字 HTML div；标注 HTML div；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；无 `stroke-dashoffset`；无 CSS border 三角形；无 `mask-image`/`conic-gradient`。

---

### 中心辐射图 (hub-spoke)

**何时用**：单一中枢与多个卫星节点的关系；平台/生态系统、核心驱动力与支撑模块；不强调顺序，只强调"都连接到中心"。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "hub-spoke",
  "hub": {"label": "数据平台", "desc": "核心"},
  "spokes": [
    {"label": "实时流", "desc": "Kafka"},
    {"label": "批处理", "desc": "Spark"},
    {"label": "ML 服务", "desc": "TensorFlow"},
    {"label": "BI 报表", "desc": "Tableau"},
    {"label": "API 网关", "desc": "Kong"},
    {"label": "数据湖", "desc": "S3/Delta"}
  ]
}
```

**模板**（中心盒 + 辐射辐条 SVG `<line>` + 卫星节点 HTML 绝对定位）：
```html
<div class="diagram hub-spoke" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --edge-strong:var(--accent-1);
  --node-accent:var(--accent-1); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:560px; height:560px;">

  <!-- SVG 辐条（6条，60°间隔，中心 280,280，外圆 r=200）-->
  <!-- 角度 0°,60°,120°,180°,240°,300°（从正上方-90°开始）→ -90,-30,30,90,150,210° -->
  <!-- cos/sin: -90:(0,-1), -30:(0.866,-0.5), 30:(0.866,0.5), 90:(0,1), 150:(-0.866,0.5), 210:(-0.866,-0.5) -->
  <svg viewBox="0 0 560 560" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
    <line x1="280" y1="280" x2="280" y2="80"   stroke="var(--edge-strong)" stroke-width="2"/>
    <line x1="280" y1="280" x2="453" y2="180"  stroke="var(--edge)" stroke-width="2"/>
    <line x1="280" y1="280" x2="453" y2="380"  stroke="var(--edge)" stroke-width="2"/>
    <line x1="280" y1="280" x2="280" y2="480"  stroke="var(--edge)" stroke-width="2"/>
    <line x1="280" y1="280" x2="107" y2="380"  stroke="var(--edge)" stroke-width="2"/>
    <line x1="280" y1="280" x2="107" y2="180"  stroke="var(--edge)" stroke-width="2"/>
  </svg>

  <!-- 中心节点 -->
  <div style="position:absolute; left:280px; top:280px; transform:translate(-50%,-50%);
    min-width:96px; min-height:64px; padding:12px 16px; box-sizing:border-box;
    background:var(--node-accent); border-radius:var(--node-radius);
    color:var(--card-bg-from); text-align:center;
    display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px;">
    <span style="font-weight:800; font-size:15px;">数据平台</span>
    <span style="font-size:11px; opacity:0.8;">核心</span>
  </div>

  <!-- 卫星节点（沿外圆 r=200 均布，各节点中心） -->
  <!-- 实时流 0°（正上）: 280, 80 -->
  <div style="position:absolute; left:280px; top:80px; transform:translate(-50%,-50%);
    min-width:80px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1.5px solid var(--node-accent); border-radius:var(--node-radius);
    color:var(--node-fg); text-align:center;
    display:flex; flex-direction:column; align-items:center; gap:2px;">
    <span style="font-weight:700; font-size:13px;">实时流</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">Kafka</span>
  </div>

  <!-- 批处理 60°: 453, 180 -->
  <div style="position:absolute; left:453px; top:180px; transform:translate(-50%,-50%);
    min-width:80px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-border); border-radius:var(--node-radius);
    color:var(--node-fg); text-align:center;
    display:flex; flex-direction:column; align-items:center; gap:2px;">
    <span style="font-weight:700; font-size:13px;">批处理</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">Spark</span>
  </div>

  <!-- ML 服务 120°: 453, 380 -->
  <div style="position:absolute; left:453px; top:380px; transform:translate(-50%,-50%);
    min-width:80px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-border); border-radius:var(--node-radius);
    color:var(--node-fg); text-align:center;
    display:flex; flex-direction:column; align-items:center; gap:2px;">
    <span style="font-weight:700; font-size:13px;">ML 服务</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">TensorFlow</span>
  </div>

  <!-- BI 报表 180°（正下）: 280, 480 -->
  <div style="position:absolute; left:280px; top:480px; transform:translate(-50%,-50%);
    min-width:80px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-border); border-radius:var(--node-radius);
    color:var(--node-fg); text-align:center;
    display:flex; flex-direction:column; align-items:center; gap:2px;">
    <span style="font-weight:700; font-size:13px;">BI 报表</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">Tableau</span>
  </div>

  <!-- API 网关 240°: 107, 380 -->
  <div style="position:absolute; left:107px; top:380px; transform:translate(-50%,-50%);
    min-width:80px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-border); border-radius:var(--node-radius);
    color:var(--node-fg); text-align:center;
    display:flex; flex-direction:column; align-items:center; gap:2px;">
    <span style="font-weight:700; font-size:13px;">API 网关</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">Kong</span>
  </div>

  <!-- 数据湖 300°: 107, 180 -->
  <div style="position:absolute; left:107px; top:180px; transform:translate(-50%,-50%);
    min-width:80px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-border); border-radius:var(--node-radius);
    color:var(--node-fg); text-align:center;
    display:flex; flex-direction:column; align-items:center; gap:2px;">
    <span style="font-weight:700; font-size:13px;">数据湖</span>
    <span style="font-size:11px; color:var(--node-fg-dim);">S3/Delta</span>
  </div>
</div>
```
> 辐射规律：卫星节点按 `360°/N` 等角分布在外圆上，坐标由三角函数算出并硬写为绝对定位 `left/top`；辐条用 SVG `<line>`；节点是 HTML div；中心强调节点用 `--node-accent` 实底。

**自检**：辐条 SVG `<line>`；中心节点 accent 实底；卫星节点 gradient 背景；标注全 HTML；颜色全用契约变量；`box-sizing:border-box`+`min-width`。

**管线安全**：无 SVG `<text>`；无伪元素；无 `mask-image`/`conic-gradient`；`<line>` 连线管线安全。

---

### 同心圆/洋葱图 (onion)

**何时用**：由内而外的层级包含关系（战略-战术-运营、核心-扩展-生态）；强调内层是基础/核心，外层是扩展/周边。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "onion",
  "rings": [
    {"label": "核心价值"},
    {"label": "产品能力"},
    {"label": "服务生态"},
    {"label": "市场覆盖"}
  ]
}
```

**模板**（同心 `<circle>` + HTML 叠加标注）：
```html
<div class="diagram onion" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:480px; height:480px;">

  <!-- 同心圆：4 圈，r=200/148/96/44，opacity 由外向内递增 -->
  <svg viewBox="0 0 480 480" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
    <!-- 最外圈：市场覆盖 -->
    <circle cx="240" cy="240" r="200" fill="var(--node-accent)" opacity="0.12"
      stroke="var(--node-accent)" stroke-width="1.5"/>
    <!-- 第三圈：服务生态 -->
    <circle cx="240" cy="240" r="148" fill="var(--node-accent)" opacity="0.22"
      stroke="var(--node-accent)" stroke-width="1.5"/>
    <!-- 第二圈：产品能力 -->
    <circle cx="240" cy="240" r="96" fill="var(--node-accent)" opacity="0.38"
      stroke="var(--node-accent)" stroke-width="1.5"/>
    <!-- 最内圈：核心价值 -->
    <circle cx="240" cy="240" r="44" fill="var(--node-accent)" opacity="0.80"
      stroke="var(--node-border)" stroke-width="1.5"/>
  </svg>

  <!-- HTML 标注（每圈在 45° 方向标注，避免重叠）-->
  <!-- 核心值：圆心 -->
  <span style="position:absolute; left:240px; top:240px; transform:translate(-50%,-50%);
    font-weight:800; font-size:12px; color:var(--card-bg-from); white-space:nowrap; text-align:center;">核心价值</span>

  <!-- 产品能力：r=96，标注在右侧 (240+68, 240)=(308, 240) -->
  <span style="position:absolute; left:308px; top:230px; transform:translateY(-50%);
    font-weight:700; font-size:12px; color:var(--node-fg); white-space:nowrap;">产品能力</span>

  <!-- 服务生态：r=148，标注在右下 (240+105, 240+105)=(345, 345) -->
  <span style="position:absolute; left:345px; top:335px; transform:translateY(-50%);
    font-weight:700; font-size:12px; color:var(--node-fg); white-space:nowrap;">服务生态</span>

  <!-- 市场覆盖：r=200，标注在右 (240+142, 240+142)=(382, 382) — 外侧右下角 -->
  <span style="position:absolute; left:382px; top:372px; transform:translateY(-50%);
    font-size:12px; color:var(--node-fg-dim); white-space:nowrap;">市场覆盖</span>
</div>
```
> 同心规律：N 圈用 N 个 `<circle>` 同心叠加，半径均匀收缩；`fill` + `opacity` 由外到内递增制造"核心更实"效果；标注是 HTML `<span>` 绝对定位在各圈带内；无 SVG `<text>`。

**自检**：圆圈用 SVG `<circle>`（非 `border-radius` 技巧或 `clip-path`）；颜色用 `--node-accent` + `opacity`；标注 HTML `<span>`；全用契约变量。

**管线安全**：无 SVG `<text>`；无 `mask-image`/`conic-gradient`/`clip-path`；同心 `<circle>` 管线安全。

---

### 鱼骨图/石川图 (fishbone)

**何时用**：问题根因分析（Ishikawa/因果图）；主骨（效果）+ 大骨（主因类别）+ 小骨（具体原因）；常用于 6M（人·机·料·法·环·测）或自定义类别。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "fishbone",
  "effect": {"label": "产品质量问题"},
  "categories": [
    {"label": "人员",  "causes": ["培训不足", "操作失误"]},
    {"label": "设备",  "causes": ["老化磨损", "维护缺失"]},
    {"label": "材料",  "causes": ["供应商差异", "规格偏差"]},
    {"label": "方法",  "causes": ["流程不规范", "文档缺失"]}
  ]
}
```

**模板**（水平主骨 + 对角大骨 + HTML 标注）：
```html
<div class="diagram fishbone" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --edge-strong:var(--accent-1);
  --node-accent:var(--accent-1); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:720px; height:400px;">

  <!-- SVG 骨架（主骨 + 4条大骨 + 小骨刺）-->
  <svg viewBox="0 0 720 400" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
    <!-- 主骨（水平脊椎）-->
    <line x1="40" y1="200" x2="660" y2="200" stroke="var(--edge-strong)" stroke-width="3"/>
    <!-- 右端箭头（效果节点） -->
    <polygon points="648,193 664,200 648,207" fill="var(--edge-strong)"/>

    <!-- 上方大骨（斜上 45°方向指向主骨）-->
    <!-- 大骨1（人员）：从 (160, 80) 向右下到 (220, 200) -->
    <line x1="160" y1="80" x2="220" y2="200" stroke="var(--node-accent)" stroke-width="2"/>
    <!-- 大骨2（设备）：从 (380, 80) 向右下到 (400, 200) -->
    <line x1="360" y1="80" x2="400" y2="200" stroke="var(--node-accent)" stroke-width="2"/>

    <!-- 下方大骨（斜下 45°方向指向主骨）-->
    <!-- 大骨3（材料）：从 (160, 320) 向右上到 (220, 200) -->
    <line x1="160" y1="320" x2="220" y2="200" stroke="var(--node-accent)" stroke-width="2"/>
    <!-- 大骨4（方法）：从 (380, 320) 向右上到 (400, 200) -->
    <line x1="360" y1="320" x2="400" y2="200" stroke="var(--node-accent)" stroke-width="2"/>

    <!-- 小骨刺（上方人员类别）-->
    <line x1="128" y1="104" x2="148" y2="128" stroke="var(--edge)" stroke-width="1.5"/>
    <line x1="168" y1="112" x2="184" y2="148" stroke="var(--edge)" stroke-width="1.5"/>
    <!-- 小骨刺（上方设备类别）-->
    <line x1="328" y1="104" x2="348" y2="128" stroke="var(--edge)" stroke-width="1.5"/>
    <line x1="368" y1="112" x2="380" y2="148" stroke="var(--edge)" stroke-width="1.5"/>
    <!-- 小骨刺（下方材料类别）-->
    <line x1="128" y1="296" x2="148" y2="272" stroke="var(--edge)" stroke-width="1.5"/>
    <line x1="168" y1="288" x2="184" y2="252" stroke="var(--edge)" stroke-width="1.5"/>
    <!-- 小骨刺（下方方法类别）-->
    <line x1="328" y1="296" x2="348" y2="272" stroke="var(--edge)" stroke-width="1.5"/>
    <line x1="368" y1="288" x2="380" y2="252" stroke="var(--edge)" stroke-width="1.5"/>
  </svg>

  <!-- 效果节点（右端 HTML） -->
  <div style="position:absolute; right:8px; top:200px; transform:translateY(-50%);
    min-width:88px; min-height:48px; padding:10px 12px; box-sizing:border-box;
    background:var(--node-accent); border-radius:var(--node-radius);
    color:var(--card-bg-from); font-weight:800; font-size:13px; text-align:center;
    display:flex; align-items:center; justify-content:center;">产品质量问题</div>

  <!-- 大骨类别标签（HTML，每条大骨末端） -->
  <div style="position:absolute; left:160px; top:72px; transform:translate(-50%,-50%);
    padding:6px 10px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1.5px solid var(--node-accent); border-radius:var(--node-radius);
    color:var(--node-fg); font-weight:700; font-size:13px; text-align:center;
    white-space:nowrap;">人员</div>

  <div style="position:absolute; left:360px; top:72px; transform:translate(-50%,-50%);
    padding:6px 10px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1.5px solid var(--node-accent); border-radius:var(--node-radius);
    color:var(--node-fg); font-weight:700; font-size:13px; text-align:center;
    white-space:nowrap;">设备</div>

  <div style="position:absolute; left:160px; top:328px; transform:translate(-50%,-50%);
    padding:6px 10px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1.5px solid var(--node-accent); border-radius:var(--node-radius);
    color:var(--node-fg); font-weight:700; font-size:13px; text-align:center;
    white-space:nowrap;">材料</div>

  <div style="position:absolute; left:360px; top:328px; transform:translate(-50%,-50%);
    padding:6px 10px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1.5px solid var(--node-accent); border-radius:var(--node-radius);
    color:var(--node-fg); font-weight:700; font-size:13px; text-align:center;
    white-space:nowrap;">方法</div>

  <!-- 小骨原因文字（HTML span，各刺末端） -->
  <!-- 上方人员 -->
  <span style="position:absolute; left:88px; top:88px; font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">培训不足</span>
  <span style="position:absolute; left:136px; top:96px; font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">操作失误</span>
  <!-- 上方设备 -->
  <span style="position:absolute; left:288px; top:88px; font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">老化磨损</span>
  <span style="position:absolute; left:336px; top:96px; font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">维护缺失</span>
  <!-- 下方材料 -->
  <span style="position:absolute; left:88px; top:300px; font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">供应商差异</span>
  <span style="position:absolute; left:136px; top:292px; font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">规格偏差</span>
  <!-- 下方方法 -->
  <span style="position:absolute; left:288px; top:300px; font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">流程不规范</span>
  <span style="position:absolute; left:336px; top:292px; font-size:11px; color:var(--node-fg-dim); white-space:nowrap;">文档缺失</span>
</div>
```
> 骨架规律：主骨是一条水平 `<line>`（左到右），末端 `<polygon>` 箭头；大骨是从分类节点斜向主骨的 `<line>`；小骨是更短的斜刺；所有文字（类别/原因/效果）是 HTML `<div>`/`<span>`，绝对定位在骨刺末端附近。

**自检**：主骨/大骨/小骨全是 SVG `<line>`；效果节点 accent 实底；末端箭头 `<polygon>`；所有标注 HTML；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；无伪元素连线；无 `mask-image`/`conic-gradient`；`<line>` 连线管线安全；`<polygon>` 箭头管线安全。

---

### 光谱定位 (spectrum-marker)

**何时用**：单一维度上的一排选项 + 标出"现状/建议"位置；治理模式（集中↔去中心）、风险偏好、成熟度、自建vs外购。用一条空间论证替代五条选项 bullet —— 冷门但极高价值的"思考型"图解。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "spectrum-marker",
  "axis": {"left": "集中式", "right": "完全去中心"},
  "ticks": ["强管控", "混合", "联邦", "自治"],
  "current": {"label": "现状", "pos": 0.25},
  "recommended": {"label": "建议", "pos": 0.68}
}
```

**模板**（水平连续轴 + 空心现状点 + 实心建议点 + 意图箭头）：
```html
<div class="diagram spectrum-marker" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:640px; height:170px;">

  <!-- 轴 + 端帽 + 刻度 + 标记（无 <text>） -->
  <!-- pos→x：60 + pos*520 -->
  <svg viewBox="0 0 640 170" style="position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;display:block;">
    <line x1="60" y1="96" x2="580" y2="96" stroke="var(--edge)" stroke-width="2"/>
    <line x1="60" y1="86" x2="60" y2="106" stroke="var(--edge)" stroke-width="2"/>
    <line x1="580" y1="86" x2="580" y2="106" stroke="var(--edge)" stroke-width="2"/>
    <!-- 刻度：190 / 320 / 450 -->
    <line x1="190" y1="90" x2="190" y2="102" stroke="var(--edge)" stroke-width="1"/>
    <line x1="320" y1="90" x2="320" y2="102" stroke="var(--edge)" stroke-width="1"/>
    <line x1="450" y1="90" x2="450" y2="102" stroke="var(--edge)" stroke-width="1"/>
    <!-- 意图箭头：现状(190)→建议(414)，虚线在轴上方 -->
    <line x1="190" y1="62" x2="404" y2="62" stroke="var(--node-accent)" stroke-width="1.5" stroke-dasharray="5 4"/>
    <polygon points="404,56 416,62 404,68" fill="var(--node-accent)"/>
    <!-- 现状点：空心 -->
    <circle cx="190" cy="96" r="8" fill="transparent" stroke="var(--node-fg-dim)" stroke-width="1.5"/>
    <!-- 建议点：实心 accent -->
    <circle cx="414" cy="96" r="9" fill="var(--node-accent)"/>
  </svg>

  <!-- 端锚标签（nowrap 防止右端标签换行） -->
  <span style="position:absolute; left:60px; top:116px; transform:translateX(-50%); font-size:12px; font-weight:700; color:var(--node-fg); white-space:nowrap;">集中式</span>
  <span style="position:absolute; left:580px; top:116px; transform:translateX(-50%); font-size:12px; font-weight:700; color:var(--node-fg); white-space:nowrap;">完全去中心</span>
  <!-- 刻度标签 -->
  <span style="position:absolute; left:190px; top:116px; transform:translateX(-50%); font-size:10px; color:var(--node-fg-dim);">强管控</span>
  <span style="position:absolute; left:320px; top:116px; transform:translateX(-50%); font-size:10px; color:var(--node-fg-dim);">混合</span>
  <span style="position:absolute; left:450px; top:116px; transform:translateX(-50%); font-size:10px; color:var(--node-fg-dim);">联邦</span>
  <!-- 标记标签 -->
  <span style="position:absolute; left:190px; top:36px; transform:translateX(-50%); font-size:11px; color:var(--node-fg-dim);">现状</span>
  <span style="position:absolute; left:414px; top:36px; transform:translateX(-50%); font-size:11px; font-weight:700; color:var(--node-accent);">建议</span>
</div>
```
> 规律：轴/刻度/标记全 SVG 几何；标签全 HTML `<span>`；现状空心、建议实心 accent；意图箭头虚线；≤5 个刻度，多了就失去"连续"感。

**自检**：轴/刻度是 SVG `<line>`；标记是 `<circle>`（现状 `fill:transparent`）；箭头 `<polygon>`；标签全 HTML；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；无伪元素；无 `mask-image`/`conic-gradient`；`<line>`/`<circle>`/`<polygon>` 管线安全。

---

### 冰山模型 (iceberg)

**何时用**：揭示"可见表象"下的深层结构 —— 组织文化（Schein）、系统思考（事件→趋势→结构→心智模型）、成本结构、软实力。上约 10% 露出水面、下约 90% 在水下是核心隐喻。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "iceberg",
  "above": {"label": "可见事件 / 行为"},
  "below": [
    {"label": "潜在模式与趋势"},
    {"label": "结构与流程"},
    {"label": "心智模型 · 根本假设"}
  ]
}
```

**模板**（水线 + 水上小三角 + 水下大冰体 + HTML 标注）：
```html
<div class="diagram iceberg" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:520px; height:460px;">

  <svg viewBox="0 0 520 460" style="position:absolute;top:0;left:0;width:100%;height:100%;display:block;">
    <!-- 水线（虚线） -->
    <line x1="30" y1="130" x2="490" y2="130" stroke="var(--edge)" stroke-width="1.5" stroke-dasharray="6 5"/>
    <!-- 水上冰尖（约 10%） -->
    <polygon points="260,44 216,124 304,124" fill="var(--node-accent)" opacity="0.16" stroke="var(--node-accent)" stroke-width="1.5"/>
    <!-- 水下冰体（约 90%，更深） -->
    <polygon points="216,136 304,136 356,300 260,430 164,300" fill="var(--node-accent)" opacity="0.30" stroke="var(--node-border)" stroke-width="1.5"/>
  </svg>

  <!-- 水线标注 -->
  <span style="position:absolute; left:494px; top:130px; transform:translateY(-50%); font-size:10px; color:var(--node-fg-dim);">水面</span>
  <!-- 水上：可见（主色） -->
  <span style="position:absolute; left:260px; top:96px; transform:translateX(-50%); font-size:13px; font-weight:700; color:var(--node-fg); white-space:nowrap;">可见事件 / 行为</span>
  <!-- 水下：三层（dim 色，逐层更深） -->
  <span style="position:absolute; left:260px; top:186px; transform:translateX(-50%); font-size:12px; color:var(--node-fg-dim); white-space:nowrap;">潜在模式与趋势</span>
  <span style="position:absolute; left:260px; top:270px; transform:translateX(-50%); font-size:12px; color:var(--node-fg-dim); white-space:nowrap;">结构与流程</span>
  <span style="position:absolute; left:260px; top:356px; transform:translateX(-50%); font-size:12px; color:var(--node-fg-dim); white-space:nowrap;">心智模型 · 根本假设</span>
</div>
```
> 规律：水上/水下面积比约 1:9（画等分是最常见错误）；水上标注用主色、水下用 dim 色强化"隐藏"隐喻；2–3 个水下层，超过 4 层就乱。

**自检**：水线/冰体是 SVG `<line>`/`<polygon>`；水上主色、水下 dim 色；面积比≈1:9；标注全 HTML `<span>`；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；无伪元素；无 `mask-image`/`conic-gradient`；`<polygon>` 冰体管线安全。

---

### 力场分析 (force-field)

**何时用**：变革管理 —— 对比"驱动力"（推动变革）与"阻力"（阻碍变革），决定从哪里发力。Lewin 洞见：削弱阻力比增强驱动力更有效，所以阻力一侧值得重点分析。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "force-field",
  "change": "全面推行远程办公",
  "driving": [{"label": "人才吸引", "strength": 3}, {"label": "成本节约", "strength": 2}, {"label": "员工诉求", "strength": 3}],
  "restraining": [{"label": "协作损耗", "strength": 3}, {"label": "管理惯性", "strength": 2}, {"label": "合规风险", "strength": 2}]
}
```

**模板**（中央变革轴 + 左驱动箭头→ + 右阻力箭头← ，箭头长度=强度）：
```html
<div class="diagram force-field" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:640px; height:400px;">

  <svg viewBox="0 0 640 400" style="position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;display:block;">
    <!-- 中央变革轴 -->
    <line x1="320" y1="70" x2="320" y2="360" stroke="var(--node-accent)" stroke-width="2"/>
    <!-- 驱动力（左→中，长度=强度）箭头指右 -->
    <line x1="150" y1="130" x2="302" y2="130" stroke="var(--edge)" stroke-width="2"/><polygon points="302,124 314,130 302,136" fill="var(--edge)"/>
    <line x1="190" y1="200" x2="302" y2="200" stroke="var(--edge)" stroke-width="2"/><polygon points="302,194 314,200 302,206" fill="var(--edge)"/>
    <line x1="150" y1="270" x2="302" y2="270" stroke="var(--edge)" stroke-width="2"/><polygon points="302,264 314,270 302,276" fill="var(--edge)"/>
    <!-- 阻力（右→中，长度=强度）箭头指左，用 accent 提示"待削弱" -->
    <line x1="490" y1="130" x2="338" y2="130" stroke="var(--node-accent)" stroke-width="2"/><polygon points="338,124 326,130 338,136" fill="var(--node-accent)"/>
    <line x1="450" y1="200" x2="338" y2="200" stroke="var(--node-accent)" stroke-width="2"/><polygon points="338,194 326,200 338,206" fill="var(--node-accent)"/>
    <line x1="450" y1="270" x2="338" y2="270" stroke="var(--node-accent)" stroke-width="2"/><polygon points="338,264 326,270 338,276" fill="var(--node-accent)"/>
  </svg>

  <!-- 中央变革标签 -->
  <div style="position:absolute; left:320px; top:20px; transform:translateX(-50%); padding:6px 14px; box-sizing:border-box;
    background:var(--node-accent); color:var(--card-bg-from); border-radius:var(--node-radius); font-size:13px; font-weight:700; white-space:nowrap;">全面推行远程办公</div>
  <!-- 表头 -->
  <span style="position:absolute; left:120px; top:92px; font-size:12px; font-weight:700; color:var(--node-fg-dim);">驱动力 →</span>
  <span style="position:absolute; right:120px; top:92px; font-size:12px; font-weight:700; color:var(--node-fg-dim);">← 阻力</span>
  <!-- 驱动力标签（左端，右对齐贴近箭头起点） -->
  <span style="position:absolute; left:20px; top:130px; width:120px; text-align:right; transform:translateY(-50%); font-size:11px; color:var(--node-fg);">人才吸引</span>
  <span style="position:absolute; left:20px; top:200px; width:120px; text-align:right; transform:translateY(-50%); font-size:11px; color:var(--node-fg);">成本节约</span>
  <span style="position:absolute; left:20px; top:270px; width:120px; text-align:right; transform:translateY(-50%); font-size:11px; color:var(--node-fg);">员工诉求</span>
  <!-- 阻力标签（右端，左对齐） -->
  <span style="position:absolute; right:20px; top:130px; width:120px; text-align:left; transform:translateY(-50%); font-size:11px; color:var(--node-fg);">协作损耗</span>
  <span style="position:absolute; right:20px; top:200px; width:120px; text-align:left; transform:translateY(-50%); font-size:11px; color:var(--node-fg);">管理惯性</span>
  <span style="position:absolute; right:20px; top:270px; width:120px; text-align:left; transform:translateY(-50%); font-size:11px; color:var(--node-fg);">合规风险</span>
</div>
```
> 规律：箭头长度编码强度（strength 1–5 → 像素长度）；阻力一侧用 accent 提示"这是要削弱的对象"；每侧 ≤5 个力，多了就是带箭头的列表。

**自检**：中央轴/箭杆是 SVG `<line>`、箭头 `<polygon>`；箭头长度随 strength；阻力用 `--node-accent`；标签全 HTML；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；无伪元素；无 CSS border 三角形（箭头用 `<polygon>`）；无 `mask-image`/`conic-gradient`。

---

### 前后 / 差距桥接 (before-after)

**何时用**：现状 vs 目标态、差距分析、转型叙事、as-is/to-be。三栏（现状｜差距·干预｜目标）比两条 bullet 列表更有说服力，是转型 deck 的常客。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "before-after",
  "current": {"title": "现状 (As-Is)", "items": ["人工审批 3 天", "数据分散 5 系统", "无实时视图"]},
  "bridge": {"title": "差距 · 干预", "items": ["流程自动化", "统一数据中台"]},
  "future": {"title": "目标 (To-Be)", "items": ["审批 2 小时", "单一可信源", "实时看板"]}
}
```

**模板**（现状卡[中性] → 桥接箭头 → 目标卡[accent]）：
```html
<div class="diagram before-after" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --edge-strong:var(--accent-1); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:680px; height:340px;">

  <!-- 现状卡（中性描边） -->
  <div style="position:absolute; left:20px; top:60px; width:190px; height:240px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to));
    border:1px solid var(--node-border); border-radius:var(--node-radius); padding:18px 16px;">
    <div style="font-size:14px; font-weight:700; color:var(--node-fg); margin-bottom:12px;">现状 (As-Is)</div>
    <div style="font-size:12px; color:var(--node-fg-dim); line-height:2.0;">人工审批 3 天<br>数据分散 5 系统<br>无实时视图</div>
  </div>

  <!-- 中间桥接：箭头 + 干预项 -->
  <svg viewBox="0 0 680 340" style="position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;display:block;">
    <line x1="222" y1="180" x2="454" y2="180" stroke="var(--edge-strong)" stroke-width="2.5"/>
    <polygon points="454,171 470,180 454,189" fill="var(--edge-strong)"/>
  </svg>
  <div style="position:absolute; left:250px; top:96px; width:180px; text-align:center;">
    <div style="font-size:11px; font-weight:700; letter-spacing:0.1em; color:var(--node-accent); margin-bottom:6px;">差距 · 干预</div>
    <div style="font-size:11px; color:var(--node-fg-dim); line-height:1.8;">流程自动化<br>统一数据中台</div>
  </div>

  <!-- 目标卡：底色单独一层用 opacity（不含 border），描边放在满不透明的内容层，避免 opacity 把描边一起淡掉 -->
  <div style="position:absolute; left:470px; top:60px; width:190px; height:240px; box-sizing:border-box;
    background:var(--node-accent); opacity:0.06; border-radius:var(--node-radius);"></div>
  <div style="position:absolute; left:470px; top:60px; width:190px; height:240px; box-sizing:border-box; padding:18px 16px;
    border:1px solid var(--node-accent); border-radius:var(--node-radius);">
    <div style="font-size:14px; font-weight:700; color:var(--node-accent); margin-bottom:12px;">目标 (To-Be)</div>
    <div style="font-size:12px; color:var(--node-fg-dim); line-height:2.0;">审批 2 小时<br>单一可信源<br>实时看板</div>
  </div>
</div>
```
> 规律：两卡行数/类目对齐，delta 才一目了然；现状用中性色、目标用 accent、干预用第二强调；每栏 ≤5 行，多了改用表格。

**自检**：卡片是真实 `<div>`；桥接箭头 SVG `<line>`+`<polygon>`；目标卡 accent 描边 + 低 opacity 底；文字全 HTML；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；无伪元素；箭头 `<polygon>`；无 `mask-image`/`conic-gradient`；卡片 `overflow` 用 `box-sizing:border-box` 防坍缩。

---

### 因果回路 (causal-loop)

**何时用**：展示增强回路(R)与调节回路(B)；解释反直觉的系统动态、"干预为何反噬"、复杂利益相关者系统。需要讲解者陪同，不适合冷启动自读。

**数据格式**：
```json
{
  "card_type": "diagram", "diagram_type": "causal-loop",
  "loop_type": "R",
  "nodes": ["投放预算", "新用户", "口碑传播", "活跃度"],
  "links": [
    {"from": "投放预算", "to": "新用户", "polarity": "+"},
    {"from": "新用户", "to": "口碑传播", "polarity": "+"},
    {"from": "口碑传播", "to": "活跃度", "polarity": "+"},
    {"from": "活跃度", "to": "投放预算", "polarity": "+"}
  ]
}
```

**模板**（4 节点闭环 + 弯曲有向连线 + 极性标注 + 中心 R/B 标签）：
```html
<div class="diagram causal-loop" style="
  --node-bg-from:var(--card-bg-from); --node-bg-to:var(--card-bg-to);
  --node-border:var(--card-border); --node-radius:var(--card-radius,8px);
  --node-fg:var(--text-primary); --node-fg-dim:var(--text-secondary);
  --edge:var(--card-border); --node-accent:var(--accent-1);
  --node-accent-2:var(--accent-2); --label-font:var(--font-primary);
  font-family:var(--label-font); position:relative; width:520px; height:400px;">

  <svg viewBox="0 0 520 400" style="position:absolute;top:0;left:0;width:100%;height:100%;overflow:visible;display:block;">
    <!-- 顺时针 4 段弯曲连线（顶→右→底→左→顶），末端 polygon 箭头 -->
    <path d="M300 78 Q400 96 420 166" fill="none" stroke="var(--edge)" stroke-width="1.8"/><polygon points="412,158 424,172 408,172" fill="var(--edge)"/>
    <path d="M424 232 Q404 302 306 320" fill="none" stroke="var(--edge)" stroke-width="1.8"/><polygon points="314,312 300,324 314,326" fill="var(--edge)"/>
    <path d="M214 320 Q116 302 96 232" fill="none" stroke="var(--edge)" stroke-width="1.8"/><polygon points="106,240 92,228 108,226" fill="var(--edge)"/>
    <path d="M96 166 Q116 96 214 78" fill="none" stroke="var(--edge)" stroke-width="1.8"/><polygon points="206,86 220,74 206,72" fill="var(--edge)"/>
    <!-- 中心回路标记圆 -->
    <circle cx="260" cy="200" r="22" fill="transparent" stroke="var(--node-accent)" stroke-width="1.5"/>
  </svg>

  <!-- 中心 R/B -->
  <span style="position:absolute; left:260px; top:200px; transform:translate(-50%,-50%); font-size:16px; font-weight:800; color:var(--node-accent);">R</span>

  <!-- 4 节点（居中于四个方位） -->
  <div style="position:absolute; left:260px; top:60px; transform:translate(-50%,-50%); min-width:104px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius);
    text-align:center; font-size:12px; font-weight:700; color:var(--node-fg);">投放预算</div>
  <div style="position:absolute; left:430px; top:200px; transform:translate(-50%,-50%); min-width:104px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius);
    text-align:center; font-size:12px; font-weight:700; color:var(--node-fg);">新用户</div>
  <div style="position:absolute; left:260px; top:340px; transform:translate(-50%,-50%); min-width:104px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius);
    text-align:center; font-size:12px; font-weight:700; color:var(--node-fg);">口碑传播</div>
  <div style="position:absolute; left:90px; top:200px; transform:translate(-50%,-50%); min-width:104px; padding:10px 12px; box-sizing:border-box;
    background:linear-gradient(180deg,var(--node-bg-from),var(--node-bg-to)); border:1px solid var(--node-border); border-radius:var(--node-radius);
    text-align:center; font-size:12px; font-weight:700; color:var(--node-fg);">活跃度</div>

  <!-- 极性标注（连线中点附近） -->
  <span style="position:absolute; left:392px; top:118px; font-size:13px; font-weight:800; color:var(--node-fg-dim);">+</span>
  <span style="position:absolute; left:378px; top:286px; font-size:13px; font-weight:800; color:var(--node-fg-dim);">+</span>
  <span style="position:absolute; left:128px; top:286px; font-size:13px; font-weight:800; color:var(--node-fg-dim);">+</span>
  <span style="position:absolute; left:128px; top:118px; font-size:13px; font-weight:800; color:var(--node-fg-dim);">+</span>
</div>
```
> 规律：闭环连线用 SVG `<path>` 弯曲、末端手算 `<polygon>` 箭头；每条边标 +/−（HTML `<span>`）；回路内标 R（增强）或 B（调节）；≤12 变量，超了就抽一条"主回路"。

**自检**：连线是 SVG `<path>`、箭头 `<polygon>`；极性/节点/回路标记全 HTML；回路标 R/B；焦点用 `--node-accent`；颜色全用契约变量。

**管线安全**：无 SVG `<text>`；无伪元素连线；箭头 `<polygon>`（不依赖 `<marker orient>`）；无 `mask-image`/`conic-gradient`/`stroke-dashoffset`。
