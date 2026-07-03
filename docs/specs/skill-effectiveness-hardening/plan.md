# Plan: Skill effectiveness hardening

- **Status:** Done

## Pre-mortem trio

- **Files touched:** `SKILL.md`, `scripts/check_skill.py`,
  `scripts/resolve_output_dir.py` (new), `references/image-generation.md` (new),
  `references/cli-cheatsheet.md`, `scripts/test_check_skill_refs.py` (new),
  `scripts/test_resolve_output_dir.py` (new).
- **"Done" is demonstrated by:** `check_skill.py` 0/0;
  `python3 scripts/test_check_skill_refs.py && python3 scripts/test_resolve_output_dir.py`
  both exit 0; existing `test_*.py` still exit 0; grep assertions for F1/F3/F4/F5/F7 hold.
- **Not changing:** `resource_loader.py`, gate logic, prompt content, styles.

**Declined temptations.** Tempted to add a check_skill assertion enforcing F4's
clarity note — declining; there is no drift to catch (the two prompt paths are
intentionally distinct), so an enforcement check would be ceremony with near-zero
value. Tempted to make F8's script also translate CJK→English — declining; that
step needs the LLM, so the script takes an already-English slug and the agent owns
translation. Tempted to expand F2 into a general "all links in all reference files"
checker — declining; scope is SKILL.md's referenced paths per the brief.

## Domain-grounding

No ungrounded load-bearing domain claim — all facts (chart-file inventory, style
count, prompt-path distinction, `os.mkdir` atomicity, planning-gate-is-mandatory)
verified against the repo during PLAN.

## Tasks

### T1 — F1: fix stale chart routing in SKILL.md
- Depends on: none
- Verification: goal-based
- Tests: none (goal). `Done when:` `grep -n 'charts/radar.md\|13 个' SKILL.md`
  returns nothing and `check_skill.py` stays 0/0.
- Approach: correct the routing-table example (drop radar.md) and the reference-
  index row (charts specs live in `{basic,advanced,complex}.md` via `index.md`).

### T2 — F2: reference-existence guard in check_skill.py
- Depends on: T1 (so the real tree is clean when the guard runs)
- Verification: TDD
- Tests (`scripts/test_check_skill_refs.py`): (a) a dead literal ref is reported;
  (b) a `{a,b,c}.md` brace form is expanded and a missing member reported;
  (c) `<placeholder>` and `*` forms are skipped (not reported); (d) the real
  SKILL.md passes clean; (e) **a dead concrete path co-located with a
  `<placeholder>` path on the same line/table-row is still reported** (the F1-hiding
  shape — pins per-span tokenization).
- Approach: add `check_referenced_files_exist(result)` — a `references/…​.md`
  regex whose char class **excludes whitespace/backtick/pipe** so each backtick-span
  is a separate token (not a greedy line match); skip any token containing
  `< > *`, brace-expand `{…}`, assert each concrete path exists under repo root;
  wire into `run_all_checks`.

### T3 — F3: 28 → 29 style count
- Depends on: none
- Verification: goal-based
- Tests: none. `Done when:` `grep -c '28 风格' SKILL.md` == 0 and check_skill 0/0.
- Approach: one-token edit on the output-structure comment.

### T4 — F4: clarify two prompt paths in SKILL.md reference index
- Depends on: none
- Verification: goal-based
- Tests: none. `Done when:` the index rows for `prompts.md` and `prompts/*.md`
  each name their execution path (inline flow vs subagent pipeline).
- Approach: edit the two reference-index rows to state the relationship.

### T5 — F5: extract image tables to references/image-generation.md
- Depends on: none
- Verification: goal-based + byte-preservation check
- Blocks moved (exact headings): `##### generate_image 提示词构造公式` (table),
  `##### 风格与配图关键词对应` (table), `##### 按页面类型调整` (table),
  `##### 禁止事项` (list). **Stays in SKILL.md 5b:** the `> 在需求调研…如果用户选择
  "不需要配图"则跳过` skip trigger **and the `##### 配图时机` flow rule** (generate
  before each page HTML, ≥1/page, save to `images/`) — this is flow control, not
  prompt-construction detail.
- Tests: none. `Done when:` each moved block's heading + a sentinel row is found via
  `grep -F` in `references/image-generation.md` and **absent** from SKILL.md 5b;
  SKILL.md 5b keeps the skip trigger + 配图时机 + a pointer; the reference index lists
  the new file; check_skill 0/0 (the new pointer path resolves under the F2 guard).
- Approach: create `references/image-generation.md` with the four extracted blocks
  verbatim; replace the SKILL.md 5b detail with trigger + 配图时机 + pointer; add index row.

### T6 — F7: compress Step 2 grounding restatement
- Depends on: none
- Verification: goal-based
- Tests: none. `Done when:` the Step 2 gate keeps its intro line, line 141's
  point-of-action STOP rule (never backfill from topic memory; G3 needs explicit
  consent + watermark), and a pointer to 来源接地契约, but no longer restates the
  G1/G2 definitions; the G1/G2/G3 contract table itself is untouched.
- Approach: collapse **only the two verbatim G1/G2 definition bullets (lines
  139–140)** into one back-pointer; **keep line 141's action-rule** intact.

### T7 — F8: resolve_output_dir.py + SKILL.md prose + cheatsheet
- Depends on: none (independent of T1–T6; shares SKILL.md so sequenced after them)
- Verification: TDD
- Tests (`scripts/test_resolve_output_dir.py`): normalize
  ("Dify Enterprise Intro!" → "dify-enterprise-intro"; length ≤40; empty→exit
  non-zero), claim on fresh root creates `<slug>`, collision (pre-created `<slug>`)
  returns `<slug>-2`. **No resume test — the script has no resume path.**
- Approach: new stdlib-only script `--root --slug` (claim only, **no `--resume`**);
  `os.mkdir` atomic claim, suffix 2..99, exhaustion → stderr + exit 1, prints
  absolute path on success. Rewrite SKILL.md §output-dir prose to prefer the script
  for the claim, keep the manual mkdir protocol as the no-Python fallback, and keep
  resume-dir selection an agent/prose judgment (the script never guesses it); add a
  cli-cheatsheet entry (with the manual fallback + resume protocol there).

## Disposition record (closed at DECIDE)

All items resolved-with-referent — nothing surfaced:
- F1/F2/F3/F5/F7/F8: resolved against repo verification (file inventory, style-ID
  count, gate behavior) and the two adversarial + one quality review rounds.
- **F4 re-scoped** (resolved-with-referent): the "drift guard / legacy marker"
  framing rested on a false duplication premise; file contents proved prompts.md
  (inline flow) and prompts/ (subagent pipeline) are distinct paths, so the fix
  became a clarity note. Referent: the two files' divergent structure + handoff tokens.
- **F6 dropped** (value decision by the user: keep the description Chinese-first).
- **NEW-2/F8 included** (value decision by the user: "fix the new findings too"); my
  original robustness veto was withdrawn after confirming Python is already a hard
  mid-flow dependency (the mandatory planning gate), and the manual fallback keeps the
  no-Python degradation path intact.

## Execution order

Sequential (single writer on SKILL.md and check_skill.py): T1 → T2 → T3 → T4 →
T5 → T6 → T7. No parallel dispatch (file overlap).
