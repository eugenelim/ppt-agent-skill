# Structured UI Mode -- CLI 原生结构化采访

## 提炼与丰富化要求（执行纪律）

1. **极端静默交互**：直接输出结构组件，严禁穿插任何“询问原因/步骤说明/口语寒暄”。
2. **拒绝干瘪，提供高密度备选项**：不要只给“商务”、“极客”这种干瘪词汇。必须在每个 option 的 `label` 或 `description` 中提炼出具体的审美/逻辑画面。
   -*反例*：`{label: "商务风"}`
   -*正例*：`{label: "极简商务", description: "Apple-Style 大留白，精炼去图表，适合高级汇报"}`
3. **闭环式诱导**：所有核心字段都不允许开放填空，全部分类转化成极具专业启发性的选项（且带“其他”口子），诱导用户提供能让下游吃饱的丰满参数。
4. **能力名显式对齐**：优先调用 `AskUserQuestion`；若宿主环境对应能力名为 `request_user_input`，也视为同义实现，按同一结构化采访合同执行。

## 组件格式骨架

使用系统支持的最优组件（如 `question/header/id/options`），确保结构如下：

```text
questions: [
  {
    header: "...",
    id: "...",
    question: "...",
    options: [
      { label: "...", description: "..." }
    ]
  }
]
```

## 字段与问题约束

- 至少覆盖 `presentation_scenario`、`core_audience`、`target_action`、`expected_pages`、`page_density`、`visual_style`、`language_mode`、`imagery_strategy`、`material_strategy`、`grounding_mode`、`manual_audit_mode`
- `presentation_scenario`、`core_audience`、`visual_style`、`language_mode`、`imagery_strategy`、`material_strategy`、`grounding_mode`、`manual_audit_mode` 必须优先做成单选题（`grounding_mode` 三选一：`represent_user_work` / `researched` / `illustrative`，即"来源接地契约"，决定这份 deck 代表谁的事实）
- `manual_audit_scope`、`manual_audit_assets`、`must_include`、`must_avoid`、`brand_constraints`、`success_criteria`、`subagent_model_strategy` 可通过第二轮结构化题或“其他”补充收集

## `core_audience` 受众层级选项（单选）

`core_audience` 单选选项 = 受众层级（落盘写入 `audience` 裸 token）：
- `exec` — C-suite / 董事会 / 投资决策方（治理与资本决策权）
- `leadership` — VP / 总监 / 职能负责人（功能层决策者）
- `team` — 业务 / 技术 / 执行团队（交付层）
- `mixed` — exec + 下属同场 / 跨层级受众
- 其他（自定义描述）

用户选中某个层级 token 时，`audience` 归一化为该裸 token（如 `audience: exec`）；大纲 Agent 的 Step 2 派生逻辑识别裸层级 token 为权威值并短路受众路由表。选"其他"时回退到 prose 描述，Step 2 按路由表派生。
