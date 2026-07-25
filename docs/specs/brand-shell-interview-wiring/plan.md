# Plan: brand-shell-interview-wiring

**Status:** Drafting <!-- Drafting | Approved | Implementing | Done -->

**Spec:** [`spec.md`](spec.md)

---

## Resolve-vs-surface disposition record

| Question | Disposition | Rationale |
|----------|-------------|-----------|
| Does `extract_anchor_fields()` parse arbitrary `key: value` lines? | Resolve — grep confirmed | `contract_validator.py:357`: `anchors = extract_anchor_fields(text)`; helper parses any `key: value` line — no new parser code needed |
| Does `contract_validator.py` distinguish errors vs warnings? | Resolve — code confirmed | `result.error()` → exit 1; `result.warn()` → exit 0 |
| Where in Step 0 to insert the brand shell command? | Resolve — read cheatsheet | After the Gate 校验 block at line ~65, before the `---` separator leading to Step 1 |
| Does the PageAgent read `cli-cheatsheet.md`? | Resolve — confirmed no | The PageAgent reads `references/playbooks/step4/page-html-playbook.md`; the main agent reads `cli-cheatsheet.md`. Diagram theme signal must go in the playbook as a `data-theme` wrapper attribute note. |
| Does Phase 7.5 support a `data-theme` attribute on diagram wrappers? | Resolve — confirmed | Phase 7.5 hand-authors CSS Grid/Flex HTML; wrapper `<div>` attributes are fully under PageAgent control. Attribute has no current consumer; it is a forward hook. |
| Should `brand_deck_path` go in both interview files? | Resolve — drop Ask-first | tpl-interview normalization table writes every anchor to both files; adding Group C sub-note automatically writes it to both; wiring both validator paths is consistent |

---

## Design

### Task 1 — `contract_validator.py` optional field

Add `_check_brand_deck_path(anchors: dict, result: ValidationResult) -> None`:

```python
def _check_brand_deck_path(anchors: dict, result: ValidationResult) -> None:
    val = (anchors.get("brand_deck_path") or "").strip()
    if val and not val.lower().endswith(".pptx"):
        result.warn(
            "brand_deck_path: value does not end in .pptx — "
            "brand shell extraction requires a PPTX file"
        )
```

Call from both `validate_interview()` and `validate_requirements_interview()`
after `matched_anchors = validate_required_anchor_fields(...)`.

### Task 2 — `references/prompts/tpl-interview.md`

**Group C** — add sub-note under the existing `brand_constraints` bullet:

```
- `brand_constraints`（落盘归一化到 `brand`）: 品牌视觉禁忌、主色、字体偏好、Logo 使用边界
  - 若用户提供了组织的 `.pptx` 模板文件，将路径额外记录为 `brand_deck_path: <absolute_path>`（可选维度；不写盘也不报错）
```

**Normalization table** — add one row after the `brand` row:

```
| `brand_deck_path` | `brand_deck_path`（可选，路径原样落盘） |
```

### Task 3 — `references/cli-cheatsheet.md` two-site update

**Site 1 — Step 0, after the Gate 校验 block, before `---`:**

```markdown
**品牌外壳提取（可选）**

检查 `requirements-interview.txt` 是否含 `brand_deck_path` 字段：

```bash
grep -q "brand_deck_path:" OUTPUT_DIR/requirements-interview.txt && \
  python3 SKILL_DIR/scripts/brand_extract.py "<brand_deck_path 的值>" \
    --refs-dir SKILL_DIR/references \
    --output OUTPUT_DIR/style.json && \
  python3 SKILL_DIR/scripts/contract_validator.py style OUTPUT_DIR/style.json
```

> **暂定接口**：上述 `brand_extract.py` 命令行格式以 `brand-shell-extraction` 规格落地时的实际接口为准。
> `brand_mode`（`"dark"` / `"light"` / `"neutral"`）写入 `style.json` 后由 Step 3.5 和 Step 4 消费。
> 未提供 `brand_deck_path` 时跳过此块。
```

**Site 2 — Step 3.5, before "1. 生成阶段 prompt 文件":**

```markdown
**Style 跳过检测（品牌外壳优先）**

先检查 `OUTPUT_DIR/style.json` 是否已存在且含 `brand_mode` 键：

```bash
[ -f OUTPUT_DIR/style.json ] && \
  python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    sys.exit(0 if 'brand_mode' in d else 1)
except Exception:
    sys.exit(1)
" OUTPUT_DIR/style.json && echo "brand shell detected — skip Style subagent, go to Gate 校验"
```

- 输出 `brand shell detected` → **直接跳到第 4 步 Gate 校验**；跳过启动 Style subagent。
- `style.json` 不存在 → 跳过检测，走正常 Style 流程。
- `style.json` 存在但不含 `brand_mode`（包括 JSON 解析失败）→ 跳过检测，走正常 Style 流程。
```

### Task 4 — `references/playbooks/step4/page-html-playbook.md` diagram theme note

Add a note inside Phase 7.5 (「图解卡「结构先行」」), after the CSS Grid/Flex
layout rules and before the static self-check block, referencing the existing
"颜色全走主题变量" principle:

```markdown
> **品牌外壳主题属性**：若 `style.json` 含 `brand_mode`，在 diagram 卡的外层
> wrapper `<div>` 上设置 `data-theme` 属性：`brand_mode="dark"` → `data-theme="dark"`；
> `"light"` → `data-theme="light"`；`"neutral"` 或字段不存在 → 不设置。
> 颜色本身已由 CSS 变量（`bg_primary`、`accent_1` 等）覆盖；此属性为 Mermaid 兼容
> 组件提供显式深浅信号。
```

---

## Tasks

### Task 1 — `contract_validator.py` — `brand_deck_path` optional validation

**Depends on:** none  
**Verification:** TDD  
**Tests:** `tests/test_contract_validator_brand_deck.py`

```python
# Red drivers (fail before implementation): test_brand_deck_path_warns_non_pptx,
#   test_brand_deck_path_no_extension_warns, test_brand_deck_path_interview_qa_path
# Green guards (pass before + after; catch regressions): all others

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contract_validator import (
    validate_interview, validate_requirements_interview, REQUIRED_INTERVIEW_ANCHORS
)

MINIMAL_ANCHORS = (
    "scenario: pitch\naudience: exec\ntarget_action: buy\n"
    "expected_pages: 10\npage_density: moderate\nstyle: minimal\n"
    "brand: none\nmust_include: x\nmust_avoid: y\nlanguage: English\n"
    "imagery: decorate\nmaterial_strategy: research\n"
    "grounding_mode: illustrative\nsubagent_model_strategy: inherit\n"
    "subagent_thinking_effort: medium\nmanual_audit_mode: off\n"
    "manual_audit_scope: none\nmanual_audit_assets: summary_only\n"
)

def _req_text(extra: str = "") -> str:
    return MINIMAL_ANCHORS + extra

def test_brand_deck_path_valid_pptx(tmp_path):  # STUB: AC1
    stub: bool = True
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand.pptx\n"))
    result, _ = validate_requirements_interview(p)
    assert result.errors == [], "expected 0 errors"
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert brand_warns == [], "expected 0 brand_deck_path warnings"

def test_brand_deck_path_absent(tmp_path):  # STUB: AC2
    stub: bool = True
    p = tmp_path / "req.txt"
    p.write_text(_req_text())
    result, _ = validate_requirements_interview(p)
    assert result.errors == []

def test_brand_deck_path_warns_non_pptx(tmp_path):  # STUB: AC3
    stub: bool = True
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand.pdf\n"))
    result, _ = validate_requirements_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert len(brand_warns) == 1

    p2 = tmp_path / "req2.txt"
    p2.write_text(_req_text("brand_deck_path: /path/to/brand.pptx\n"))
    result2, _ = validate_requirements_interview(p2)
    brand_warns2 = [w for w in result2.warnings if "brand_deck_path" in w]
    assert brand_warns2 == []

def test_brand_deck_path_empty_no_warning(tmp_path):  # STUB: AC3
    stub: bool = True
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: \n"))
    result, _ = validate_requirements_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert brand_warns == []

def test_brand_deck_path_no_extension_warns(tmp_path):  # STUB: AC3
    stub: bool = True
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand\n"))
    result, _ = validate_requirements_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert len(brand_warns) == 1

def test_brand_deck_path_case_insensitive(tmp_path):  # STUB: AC3
    stub: bool = True
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand.PPTX\n"))
    result, _ = validate_requirements_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert brand_warns == []

def test_brand_deck_path_interview_qa_path(tmp_path):  # STUB: AC1/AC3
    stub: bool = True
    p = tmp_path / "qa.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand.pdf\n"))
    result, _ = validate_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert len(brand_warns) == 1  # same check fires via validate_interview

def test_required_anchors_unchanged():  # STUB: AC2
    stub: bool = True
    assert "brand_deck_path" not in REQUIRED_INTERVIEW_ANCHORS
```

Approach:
- Add `_check_brand_deck_path(anchors: dict, result: ValidationResult) -> None`
  (pure function, stdlib only).
- Call from both `validate_interview()` and `validate_requirements_interview()`
  after `matched_anchors = validate_required_anchor_fields(...)`.

### Task 2 — `references/prompts/tpl-interview.md`

**Depends on:** none  
**Verification:** Goal-based  
**Done when:** `grep -q "brand_deck_path" references/prompts/tpl-interview.md` exits 0.

Edit Group C to add the sub-note under `brand_constraints`, and add the
normalization table row as described in the Design section. No other lines changed.

### Task 3 — `references/cli-cheatsheet.md` two-site update

**Depends on:** none (docs-only; parallel with Tasks 1 and 2)  
**Verification:** Goal-based  
**Done when:**
1. `grep -q "brand_deck_path" references/cli-cheatsheet.md` exits 0 (AC4)
2. `grep -qE "skip Style subagent|brand shell detected" references/cli-cheatsheet.md` exits 0 (AC5)

Insert the two blocks (Step 0 + Step 3.5) from the Design section. No other lines changed.

### Task 4 — `references/playbooks/step4/page-html-playbook.md`

**Depends on:** none (docs-only; parallel with Tasks 1–3)  
**Verification:** Goal-based  
**Done when:** `grep -q "data-theme" references/playbooks/step4/page-html-playbook.md` exits 0 (AC6)

Add the diagram theme note from the Design section (into Phase 7.5). No other lines changed.

## Test plan

```bash
cd /path/to/repo
python -m pytest tests/test_contract_validator_brand_deck.py -v
# Goal-based checks:
grep -q "brand_deck_path" references/cli-cheatsheet.md && echo "AC4 pass"
grep -qE "skip Style subagent|brand shell detected" references/cli-cheatsheet.md && echo "AC5 pass"
grep -q "data-theme" references/playbooks/step4/page-html-playbook.md && echo "AC6 pass"
grep -q "brand_deck_path" references/prompts/tpl-interview.md && echo "AC7 pass"
```

## Rollout

Additive. No existing validators fail. No prompt files change in a way that
breaks the existing interview flow (the field is optional everywhere). All
existing runs that omit `brand_deck_path` are unaffected.
