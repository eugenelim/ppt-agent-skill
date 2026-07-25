# Spec: brand-shell-interview-wiring

**Mode:** full (structural change — prompt template, validator contract, CLI cheatsheet, PageAgent playbook, multi-file with inter-task dependencies)

- **Status:** Shipped <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Depends on:** `brand-shell-extraction` must ship first — produces `brand_mode` in style.json
- **Contract:** `scripts/contract_validator.py` interview anchors

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Wire the brand-shell extraction workflow into the main agent's standard run.
After this spec ships, a user can supply `brand_deck_path: <path>` in the
interview, and the pipeline will:

1. Accept the optional `brand_deck_path` field in both `interview-qa.txt` and
   `requirements-interview.txt` without a validator error.
2. Know (from the CLI cheatsheet) to run `brand_extract.py` after the
   interview gate, before Step 3.5, when `brand_deck_path` is present.
3. Skip the Style subagent (Step 3.5) when `style.json` already exists with
   a `brand_mode` key, treating it as a signal that a brand shell has been
   applied.
4. Set a `data-theme` attribute on diagram card wrapper divs in Step 4 HTML
   based on `brand_mode` from `style.json` — via a note in Phase 7.5 of the
   PageAgent's HTML playbook. The diagram's colors already flow through CSS
   variables; the attribute is a forward hook with no current in-repo consumer
   (Phase 7.5 uses hand-authored CSS Grid/Flex, not a Mermaid runtime).

Files touched: `scripts/contract_validator.py`,
`references/prompts/tpl-interview.md` (Group C + normalization table),
`references/cli-cheatsheet.md` (Step 0, Step 3.5),
`references/playbooks/step4/page-html-playbook.md` (Phase 7.5 diagram note).
No new scripts are added.

## Acceptance Criteria

- [x] AC1 — **`brand_deck_path` accepted without error.** A
  `requirements-interview.txt` that contains `brand_deck_path: /path/to/brand.pptx`
  passes `python3 scripts/contract_validator.py requirements-interview
  <path>` with zero errors and zero brand-deck-path warnings.

- [x] AC2 — **`brand_deck_path` optional — omission still valid.** A
  `requirements-interview.txt` without `brand_deck_path` passes the same
  validator with zero errors. The existing required-anchor contract is
  unchanged.

- [x] AC3 — **`brand_deck_path` must end in `.pptx`.** When present, if
  the value does not end in `.pptx` (case-insensitive), the validator emits
  a warning (not an error). A test asserts the warning fires for
  `brand_deck_path: /path/to/brand.pdf` and does not fire for
  `brand_deck_path: /path/to/brand.pptx`. An empty value is treated as
  absent (no warning).

- [x] AC4 — **Step 0 post-interview command documented.** `references/cli-cheatsheet.md`
  Step 0 contains a "Brand Shell (optional)" subsection explaining:
  when `brand_deck_path` is set in `requirements-interview.txt`, run
  `brand_extract.py` (provisional interface — pin to actual flags once
  `brand-shell-extraction` ships) after the interview gate before Step 3.5.
  The subsection notes the command is provisional pending the upstream spec.
  A test asserts `grep -q "brand_deck_path" references/cli-cheatsheet.md` exits 0.

- [x] AC5 — **Step 3.5 bypass documented.** `references/cli-cheatsheet.md`
  Step 3.5 contains a guard block: if `OUTPUT_DIR/style.json` exists and
  contains a `brand_mode` key, skip the Style subagent and go directly to
  the gate validator. The guard handles missing `style.json` (file-absent
  check before JSON parse) and corrupt JSON (silent non-zero exit, treated
  as no-brand-shell). A test asserts
  `grep -qE "skip Style subagent|brand shell detected" references/cli-cheatsheet.md` exits 0.

- [x] AC6 — **Step 4 diagram theme attribute in PageAgent playbook.** A note
  added to Phase 7.5 of `references/playbooks/step4/page-html-playbook.md`
  instructs the PageAgent: when writing the diagram card's outer wrapper div,
  read `brand_mode` from `style.json` and set `data-theme="dark"` when
  `"dark"`, `data-theme="light"` when `"light"`, omit when absent or
  `"neutral"`. Colors already flow through CSS variables; the attribute is a
  forward hook for any light/dark-aware diagram renderer (no current in-repo
  consumer — diagram cards are hand-authored CSS Grid/Flex HTML). A test asserts
  `grep -q "data-theme" references/playbooks/step4/page-html-playbook.md` exits 0.

- [x] AC7 — **`tpl-interview.md` Group C updated.** The `brand_constraints`
  bullet in Group C includes a sub-note: if the user provides an organization
  `.pptx`, record the path as `brand_deck_path: <absolute_path>`. The
  normalization table gains a row: `brand_deck_path → brand_deck_path（可选，路径原样落盘）`.
  A test asserts `grep -q "brand_deck_path" references/prompts/tpl-interview.md` exits 0.

## Boundaries

### Always do

- Add `brand_deck_path` as a recognized optional field in `contract_validator.py`
  — warn on non-`.pptx` extension; treat empty value as absent; never require
  it; never add to `REQUIRED_INTERVIEW_ANCHORS`; wire into both
  `validate_interview()` and `validate_requirements_interview()`.
- Add `brand_deck_path` to the normalization table in `tpl-interview.md` and
  the Group C sub-note; do not modify Groups A, B, D, E or the required-anchor
  list.
- Document the post-interview extraction command in `cli-cheatsheet.md` Step 0,
  the bypass guard in Step 3.5, and the mermaid theme note in the PageAgent
  HTML playbook.

### Never do

- Add `brand_deck_path` to `REQUIRED_INTERVIEW_ANCHORS`.
- Validate that the PPTX file exists at the given path — path resolution
  happens at runtime, not at interview-gate time.
- Introduce a new `contract_validator.py` subcommand.
- Modify any rendering script, planning schema, or style board.

## Testing Strategy

| AC | Task | Verification mode | Mechanism |
|----|------|-------------------|-----------|
| AC1 | validator accepts `brand_deck_path` | TDD | `test_brand_deck_path_valid_pptx`: `requirements-interview` with `/x.pptx` → 0 errors, 0 warnings |
| AC2 | validator tolerates absence | TDD | `test_brand_deck_path_absent`: no `brand_deck_path` → 0 errors |
| AC3 | non-pptx extension warns | TDD | `test_brand_deck_path_warns_non_pptx`: `/x.pdf` → 1 warning; `/x.pptx` → 0 warnings |
| AC3 | empty value no warning | TDD | `test_brand_deck_path_empty_no_warning`: `brand_deck_path: ` → 0 warnings |
| AC3 | extension-less path warns | TDD | `test_brand_deck_path_no_extension_warns`: `/x/brand` → 1 warning |
| AC3 | PPTX extension case-insensitive | TDD | `test_brand_deck_path_case_insensitive`: `/x.PPTX` → 0 warnings |
| AC1/AC3 | validate_interview also checks | TDD | `test_brand_deck_path_interview_qa_path`: same check via `validate_interview()` |
| AC2 | required anchors unchanged | TDD | `test_required_anchors_unchanged`: `REQUIRED_INTERVIEW_ANCHORS` lacks `brand_deck_path` |
| AC4 | post-interview command documented | Goal-based | `grep -q "brand_deck_path" references/cli-cheatsheet.md` exits 0 |
| AC5 | bypass guard documented | Goal-based | `grep -q "skip Style subagent\|brand shell detected" references/cli-cheatsheet.md` exits 0 |
| AC6 | playbook diagram theme note | Goal-based | `grep -q "data-theme" references/playbooks/step4/page-html-playbook.md` exits 0 |
| AC7 | tpl-interview updated | Goal-based | `grep -q "brand_deck_path" references/prompts/tpl-interview.md` exits 0 |

## Assumptions

1. `brand_extract.py` ships first (produces `brand_mode` in `style.json`);
   the cheatsheet's Site 1 command is marked provisional pending that interface.
2. The PageAgent generates diagram card HTML inline (CSS Grid/Flex, per
   `page-html-playbook.md` Phase 7.5); a `data-theme` attribute on the
   wrapper div is fully under its control. This spec adds a `brand_mode` →
   `data-theme` note to Phase 7.5 as a forward hook. No current in-repo
   consumer reads this attribute; it enables future Mermaid-compatible renderers
   to pick up the signal without a further spec change.
3. `extract_anchor_fields()` in `contract_validator.py` parses any `key: value`
   line from interview text — confirmed; no new parser code is needed.
4. `contract_validator.py` warnings are non-blocking (exit 0); errors are
   blocking (exit 1). The `.pptx` extension check is a warning.
