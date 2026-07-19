# Scripts Index

本目录包含 PPT 工作流的全部执行脚本。

## 核心调度

| 脚本 | 用途 | 调用方 |
|------|------|--------|
| `prompt_harness.py` | 模板变量填充，生成 subagent prompt | 主 agent |
| `resolve_output_dir.py` | 主题定后原子抢占 `OUTPUT_DIR`（kebab 归一化 + `<slug>`/`<slug>-N` 抢占；仅新建、不猜续跑） | 主 agent |
| `resource_loader.py` | 资源路由器（menu 菜单 / resolve 按需加载 / images 图片清单） | 主 agent + subagent |
| `subagent_logger.py` | 记录 subagent 阶段命令的 stdout/stderr 与阶段注记到 runtime 日志 | subagent |

## 校验工具

| 脚本 | 用途 | 调用方 |
|------|------|--------|
| `contract_validator.py` | 合同校验（`interview` / `requirements-interview` / `search` / `search-brief` / `source-brief` / `outline` / `style` / `images` / `page-review` / `page-audit-request` / `delivery-manifest`） | 主 agent |
| `planning_validator.py` | Step 4 planning JSON 单页/全量验证 | subagent 自审 + 主 agent gate |
| `proof_worksheet.py` | Step 4.5 确定性、零 LLM 策划意图评审工作表（渲染 `planning/*.json` 为只读脚手架） | 主 agent |
| `proof_gate.py` | Step 4.5 Review/Render 决定落盘（`--decision`）+ Step 5c 渲染前置检查（`--check`，非零=硬 STOP） | 主 agent |
| `milestone_check.py` | 按里程碑阶段验收 | 主 agent |
说明：

- `contract_validator.py style` 现已按 runtime style 合同检查 `style_id`、`style_name`、`mood_keywords`、`design_soul`、`variation_strategy`、`decoration_dna`、`css_variables`、`font_family`
- `resource_loader.py` 的 `menu` / `resolve` 会跳过 `runtime-*` 文件；这些文件由主链定向注入
- Step 4 现在会先用 `resource_loader.py menu --output ...` 生成 `runtime/page-planning-menu-N.md`，既给 planning 阶段读取，也方便维护时直接检查

> 维护工具（`check_skill.py`、`smoke_skill.py`、`smoke_test.py`、`lint_diagram_recipes.py`、`build_hero.py`、`diagram_gallery.py`、`diagram_render_check.py`）已迁移至 `tools/`。

## 导出工具

| 脚本 | 用途 |
|------|------|
| `html_packager.py` | 生成 preview.html |
| `html2png.py` | HTML -> PNG 截图 |
| `html2svg.py` | HTML -> SVG 转换 |
| `png2pptx.py` | PNG -> PPTX 导出 |
| `svg2pptx.py` | SVG -> PPTX 导出 |

## 辅助

| 脚本 | 用途 |
|------|------|
| `workflow_versions.py` | 统一 workflow/schema version 常量 |

## 依赖关系

```
prompt_harness.py       -- 独立
resource_loader.py      -- 独立
contract_validator.py   -> planning_validator.py -> workflow_versions.py
milestone_check.py      -- 独立
```
