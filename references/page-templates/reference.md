# 横切参考页 -- 运行手册 back-matter

> 横切参考 back-matter：责任矩阵（RACI）/ 质量门 / 升级路径 / 术语表——按"查得到"而非"打动人"组织。是参考型 deck（运行手册 / 交付手册 / SOP / playbook）的收束方式，**替代**说服型 deck 的行动号召（CTA）结尾。
> 必须元素：一个可执行操作制品（责任矩阵 / 质量门 / 升级路径 / 术语表之一）；持久页眉/页脚。可选：一句 lead 交代这份参考"何时查"。
> 与 `end` 的区别：`end` 是说服弧线的收束（总结回顾 `close` 或行动号召 `cta`）；`reference` 是"用来查"的横切资料页，运行手册用它收尾而非 CTA。
> 组件复用：本页**不新增组件 HTML**，直接消费 [`blocks/worksheet.md`](../blocks/worksheet.md) 的既有配方，按 `resources.block_refs:["worksheet"]` 注入。天生皮肤 [`schematic_blueprint`](../styles/light.md)。

## 何时用 reference

- **参考型 deck 的收尾**：运行手册讲完各阶段后，收在横切参考——读者随时跳回来查"谁负责 / 何时升级 / 门槛是什么 / 术语什么意思"。
- **不是 CTA**：说服型 deck 结尾放行动号召（`end` + `cta`）；参考型 deck 结尾放可查制品（`reference`）。二者互斥，由 archetype 决定，见 [`principles/narrative-arc.md` §参考型叙事](../principles/narrative-arc.md)。
- 一页放**一个**制品。多个横切参考（RACI + 质量门 + 术语表）拆成多张连续 `reference` 页，每张一个制品。

## back-matter 角色 → worksheet 配方映射

每种参考制品复用一个既有配方，不写新组件：

| back-matter 角色 | worksheet 配方 | card_type | block_refs |
|------------------|----------------|-----------|------------|
| 责任矩阵（RACI） | `responsibility-matrix`（`worksheet_kind:"responsibility_matrix"`） | `list` | `["worksheet"]` |
| 质量门 / 失败模式 | `status-block`（`worksheet_kind:"status_block"`，gate 绿 / failure 琥珀） | `list` | `["worksheet"]` |
| 升级路径 / 例会节奏 | `escalation-matrix`（`worksheet_kind:"escalation"`） | `list` | `["worksheet"]` |
| 术语表（glossary） | **原生** `card_type:"list"` 定义列表（术语 + 释义两列），**不新增 worksheet 配方** | `list` | —（可选 `["worksheet"]` 借斑马行样式） |

> 术语表走原生 `list` 卡的定义列表形态即可（左术语、右释义）；如需黑表头 / 斑马行观感，可挂 `block_refs:["worksheet"]` 复用表格骨架，但**不要**为 glossary 单独造配方。

## 页面结构

1. **持久页眉** `<header class="slide-header">`——masthead，与正文各页一致（reference 要随时回答"我在哪"）。
2. **参考标题 + 一句 lead**（可选）——这份参考"何时查、怎么读"。
3. **一个操作制品**——按上表选 worksheet 配方，`resources.block_refs:["worksheet"]` 注入其正文；`card_style:"transparent"`（表格自带黑框骨架，外层不再套卡）。
4. **持久页脚** `<footer class="slide-footer">`。

## 规划 JSON 片段（示例：RACI back-matter 页）

```json
{
  "page_type": "reference",
  "narrative_role": "reference",
  "title": "Who owns what",
  "resources": { "block_refs": ["worksheet"], "page_template": "reference" },
  "cards": [
    {
      "card_id": "s12-anchor-1", "role": "anchor",
      "card_type": "list", "card_style": "transparent",
      "worksheet_kind": "responsibility_matrix",
      "headline": "Responsibility matrix",
      "body": ["Kickoff sign-off — A: Client, R: Tech Lead", "Prototype build — A: Tech Lead, R: Engineer"]
    }
  ]
}
```

## 唯一硬约束

- 复用既有 worksheet 配方，**不新增组件 HTML**、**不新增 validator `card_type`**（走 `block_refs` 机制，同 diagram family 文件）。
- 所有颜色通过 CSS 变量引用（`status-block` 的语义信号色是唯一例外，见 `blocks/worksheet.md` 碳out）。
- 持久页眉/页脚必须带 `slide-header` / `slide-footer` 类名——合同校验与视觉 QA 据此确认持久 chrome。
- 管线安全：真实 `<table>` / `<div>`，禁 SVG `<text>`、禁 `mask-image` / `conic-gradient` / `background-image:url()`。
- 一页一个制品；表格行数 4-8 为宜，超过 8 拆页（同 worksheet 约束）。
