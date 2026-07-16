# Diagram Polish — plan

Status: Shipped (committed d644718)

## Task list

### T0 — Fix `_parse_spec` quote-stripping (AC-1)
**Verification:** TDD
**Depends on:** none
**Touches:** `scripts/mermaid_layout.py`

Tests:
- `_parse_spec('A["My Service"]')` → label == `"My Service"` (no surrounding quotes).
- `_parse_spec("A['single']")` → label == `"single"`.

Approach: After capturing the label from the named group, strip leading/trailing `"` and `'` characters before returning. The regex already captures the content inside brackets; the fix is in the post-capture clean-up step.

**Status: done** — `_parse_spec` strips surrounding quotes from all captured labels (verified by `test_mermaid_polish` AC-1 checks).

---

### T1 — Fix `_wrap_label` literal `\n` handling (AC-2b)
**Verification:** TDD
**Depends on:** none
**Touches:** `scripts/mermaid_layout.py`

Tests:
- `_wrap_label("Line 1\\nLine 2")` → `["Line 1", "Line 2"]` (literal backslash-n treated as line break).
- `_wrap_label("Line 1\nLine 2")` → `["Line 1", "Line 2"]` (real newline also splits).

Approach: In `_wrap_label`, normalise `\\n` (the literal two-character sequence) to `\n` before splitting, so both forms produce line breaks.

**Status: done** — verified by `test_mermaid_polish` `_wrap_label` checks and the `\n in label renders as <br>` check.

---

### T2 — Subgraph `ID["Label"]` extraction (AC-2)
**Verification:** TDD
**Depends on:** none
**Touches:** `scripts/mermaid_layout.py`

Tests:
- `_parse_graph_source(['subgraph db["Database Layer"]', 'N[x]', 'end'])` → `groups["db"].label == "Database Layer"`.

Approach: In the subgraph-parsing branch of `_parse_graph_source`, apply the same bracket-extraction pattern used for nodes (`id["label"]` or `id[label]`) to extract the human-readable label from the subgraph directive line.

**Status: done** — verified by `test_mermaid_polish` subgraph label check.

---

### T3 — `COL_GAP` 16→32px + named `GROUP_PAD_*` constants (AC-3)
**Verification:** Goal-based
**Depends on:** none
**Touches:** `scripts/mermaid_layout.py`

Done when: `COL_GAP == 32`, `GROUP_PAD_X == 16`, `GROUP_PAD_Y_TOP == 28`, `GROUP_PAD_Y_BOT == 16` are module-level constants; group container rendering references these constants (no magic numbers).

Approach: Change `COL_GAP = 16` → `COL_GAP = 32`; introduce `GROUP_PAD_X`, `GROUP_PAD_Y_TOP`, `GROUP_PAD_Y_BOT` constants; replace inline numeric literals in group-box `gx/gy/gw/gh` calculation.

**Status: done** — constants verified by `test_mermaid_polish` constant-value checks.

---

### T4 — `:::external` class rendering (AC-4)
**Verification:** TDD
**Depends on:** none
**Touches:** `scripts/mermaid_layout.py`

Tests:
- `_parse_spec_and_class("A[Service]:::external")` → `css_class == "external"`.
- Node parsed from `'A["API"]:::external --> B["DB"]'` → `nodes["A"].css_class == "external"`.
- `_dispatch("flowchart TD\nA[Ext]:::external --> B[Int]", None, 400)` → output contains `"node-external"`.
- The `node-external` div style attribute uses `--node-fg-dim` for border colour.

Approach: Add `_parse_spec_and_class` that strips `:::class` suffix before passing to `_parse_spec`, then stores `css_class` on the `_Node`. In `_render_graph_fragment`, if `n.css_class == "external"`, use `--node-fg-dim` for both border and text variables, and add `node-external` to the div's class list.

**Status: done** — all four test checks pass.

---

### T5 — `label|tech` sub-label rendering (AC-5)
**Verification:** TDD
**Depends on:** none
**Touches:** `scripts/mermaid_layout.py`

Tests:
- `_dispatch('flowchart TD\nA["Svc|Spring Boot"] --> B[DB]', None, 400)` → output contains `"node-tech"` span and text `"Spring Boot"` and `"Svc"`.
- Whitespace around `|` stripped: `"Svc | Spring Boot"` → tech label `"Spring Boot"`.

Approach: In node label rendering, split on `|` once; render the main label as the primary `<span>` and the tech portion as a `<span class="node-tech">` at 11px with `--node-fg-dim` colour, separated by a `<br>`.

**Status: done** — all tech-label checks pass.

---

### T6 — Auto-legend for multi-style diagrams (AC-6)
**Verification:** TDD
**Depends on:** none
**Touches:** `scripts/mermaid_layout.py`

Tests:
- Solid+dashed diagram → `"diagram-legend"` in output, `"Async"` present.
- Solid-only diagram → `"diagram-legend"` absent.
- Solid+thick diagram → `"diagram-legend"` in output, `"Critical path"` present.
- Dashed-only diagram → legend present.

Approach: Implement `_render_legend(edges, groups) -> str`. Count unique non-solid semantic types (dashed, thick) and whether any groups exist. If only one type is present and it is solid, return `""`. Otherwise render a `<div class="diagram-legend">` row with labelled samples for each edge type present.

**Status: done** — all four legend checks pass.

---

### T7 — Diagram metadata chip (AC-7)
**Verification:** TDD
**Depends on:** none
**Touches:** `scripts/mermaid_layout.py`

Tests:
- `_extract_diagram_title("%% title: My Arch\nflowchart TD\nA-->B")` → `"My Arch"`.
- `_extract_diagram_title("%% define nodes\nflowchart TD\nA-->B")` → `""` (plain comment ignored).
- `_render_metadata_chip("flowchart", "My Arch")` contains `"Flowchart"` and `"My Arch"`.
- `_render_metadata_chip("flowchart", "")` → `""` (no chip for untitled diagram).
- Titled diagram dispatch → output contains `"diagram-meta"` and title text.
- Untitled diagram dispatch → no `"diagram-meta"`.

Approach: Implement `_extract_diagram_title(src) -> str` scanning for `%% title:` prefix; implement `_render_metadata_chip(directive, title) -> str` that returns `""` when title is absent, otherwise a `<div class="diagram-meta">` chip with normalised directive label + title. Call both from `_layout_graph_topology` and wrap with `diagram-wrapper` div only when chip or legend is non-empty.

**Status: done** — all six metadata checks pass.

---

### T8 — `diagram.md` documentation (AC-9)
**Verification:** Goal-based
**Depends on:** T4, T5, T6, T7 (documents what those tasks implement)
**Touches:** `references/blocks/diagram.md`

Done when: `:::external`, `|` separator, `%% title:`, and legend conventions are documented in `references/blocks/diagram.md` under a "Mermaid 渲染器语义标注" section.

Approach: Append a new H2 section with subsections for each convention, including usage examples and the CSS variables each maps to.

**Status: done** — all four conventions documented; recipe-example updates deferred to backlog (anchor: `recipe-example-updates`).

---

### T9 — New tests: `test_mermaid_polish()` (AC-8)
**Verification:** TDD
**Depends on:** T0–T8 (covers all ACs)
**Touches:** `scripts/test_diagram_qa.py`

Done when: `test_mermaid_polish()` passes with ≥30 checks covering ACs 1–7 + 9; `test_diagram_qa.py` exits 0.

**Status: done** — `test_mermaid_polish()` contains 34 checks; `test_diagram_qa.py` suite (98 checks) passes; `lint_diagram_recipes.py` 0 violations.

---

## Declined patterns (plan)

- Tempted to post-process `_parse_spec` output to extract the css class: declining — the `:::class` suffix must be stripped *before* delegating to `_parse_spec` (pre-processing), not derived from its return value, so `_parse_spec_and_class` strips the suffix and then calls `_parse_spec` on the cleaned spec string.
- Tempted to add `diagram-meta` chip to untitled diagrams (showing type only): declining — the chip adds visual noise when there is no title; type-only chips were deemed low value.
- Tempted to use `background-clip:text` for the metadata chip gradient text: declining — not pipeline-safe.
