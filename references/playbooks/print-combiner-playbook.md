# Print-combiner playbook — 多文件幻灯 + 生成式打印/PDF 视图

> 从一份用户提供的顾问 deck 里提炼出来的**产出/编排模式**（不是设计风格）。适用于任何"每页一个 HTML 文件"的 deck 想要一键导出连续打印/PDF。

## 何时用

当 deck 按"一页一个 `slide-NN.html`"组织、外加一个可翻页的 `index.html`（导航壳）时，需要一个**合并的 `index-print.html`**——把所有页拼进一个可滚动文档，加打印 CSS，让浏览器 `Print → Save as PDF` 一次导出整套 landscape 幻灯。

## 三件套结构

1. **`slide-NN.html`（内容页）**：每页一个文件，`<div id="slide-container">` 里放一个 `<section class="slide">`。共享 `css/styles.css`（deck 的全部风格变量与组件类都在这里，单一真源）。
2. **`index.html`（导航壳）**：只装第一页 + 上/下/打印导航按钮 + 键盘翻页 JS（`ArrowLeft/Right` 跳到对应 `slide-NN.html`）+ 页码计数。
3. **`index-print.html`（合并打印视图）**：由脚本生成——抽出每个文件 `#slide-container` 的内容、按序拼接、包进打印外框（顶部工具条 + `@media print` 规则）。**不手改**，改内容后重跑脚本。

## 关键打印 CSS 约定（合并视图的外框）

- 屏幕态：`.slide` 固定 `--slide-width/height`（如 1280×720）、`margin:20px auto`、灰边框，便于预览；顶部一条 `.print-toolbar`（Back / Print / 页数）。
- 打印态 `@media print`：`@page{size:landscape; margin:0}`；每张 `.slide` → `width:100vw; height:100vh`；`page-break-after:always` + `break-inside:avoid` 保证一页一屏、不跨页断裂；`.slide:last-child` 收掉尾部空白页；隐藏工具条与导航；`-webkit-print-color-adjust:exact` 保住暗底/彩条不被浏览器"省墨"洗白。

## 生成脚本

见 [`scripts/build-print.sh`](../../scripts/build-print.sh)（通用版，无任何客户/deck 名）。用法：

```
./scripts/build-print.sh <deck-dir>    # deck-dir 内含 index.html + slide-*.html + css/styles.css
```

脚本按 `index.html` → `slide-*.html`（sort）收集页序，用 Python 正则抽出各页 `#slide-container` 内容拼接，注入统一的打印外框，写出 `<deck-dir>/index-print.html`。**改动/增删/重排页面后重跑**。

导出 PDF 时**不要**靠浏览器手动 `Print → Save as PDF`（不确定、非 1:1）。用确定性的
[`scripts/build_pdf.py`](../../scripts/build_pdf.py)——Puppeteer 截图（与 HTML 渲染 1:1）+ 现有 Pillow 封装成 PDF，禁用 WeasyPrint / `pdf2svg` / `img2pdf` / `page.pdf()` 打印导出：

```
python3 scripts/build_pdf.py --deck <deck-dir>    # 各页截图 → 一份多页 PDF（像素级 1:1）
```

不带 `--out` 时，PDF 以 deck 目录名（即 `<deck-slug>`）命名 → `<deck-dir>/<deck-slug>.pdf`，和 `<deck-slug>-preview.html` / `.pptx` 一样带主题名，单独下载也认得出。合并视图（`index-print.html` / `<deck-slug>-preview.html`）不会被当成正文页塞进 PDF。

## 为什么值得单列

- **单一样式真源**：所有页共享一个 `css/styles.css`，风格改一处全体生效——比每页内联样式好维护。
- **导航壳与打印视图分离**：屏幕演示用可翻页 `index.html`，交付/评审用连续 `index-print.html` → PDF，两种消费方式一套内容。
- **暗底 deck 的打印保真**：`print-color-adjust:exact` + landscape 满屏是暗色 deck 导出 PDF 不掉色的关键，容易漏。
