# Spec: Skill effectiveness hardening

Mode: full (multi-feature brief with a dependent task — the check_skill guard
must be robust enough to guard the doc fixes; also touches the contract-
enforcement mechanism and adds a runtime script that affects every deck run)

- **Status:** Shipped

## Objective

Improve the `ppt-agent` skill along the audited effectiveness dimensions —
consistency, progressive disclosure, terseness, deterministic scripting, and
drift-resistance — **without weakening any quality/rigor guarantee** (the
grounding contract, the planning/taste/pipeline gates, and cross-page discipline
stay fully intact).

## Background — what the audit found

- **Stale chart routing (F1).** The reference index (SKILL.md) claims
  "sunbigfly 风格的单文件图表（13 个）" and the routing table gives
  `references/charts/radar.md` as an example, but the per-chart spec files were
  consolidated into `charts/basic.md` / `advanced.md` / `complex.md` (routed via
  `charts/index.md`; a `README.md` also sits in the dir, but no per-chart
  `radar.md`-style file remains). `resource_loader.py` silently skips a missing file, so the
  dead path is invisible at runtime and misleads a maintainer reading the index.
- **No existence guard (F2).** `check_skill.py` validates route *patterns* and
  phase contracts but never asserts referenced files exist, so F1 (and the F3
  count typo) passed green. This is the highest-leverage fix: a guard that fails
  on this drift class.
- **Style count typo (F3).** SKILL.md says "28 风格预览" in one place; everywhere
  else and `gallery.py` say 29 (verified: 29 distinct IDs; boards 8+10+4+3+4).
- **Prompt-path clarity (F4, re-scoped).** `references/prompts.md` (monolith,
  Prompt #1–#5) drives the **inline single-agent flow** (SKILL.md Steps 1–5 cite
  it directly); `references/prompts/` (tpl-*, phase-split with `STAGE COMPLETE`
  handoff tokens) drives the **subagent orchestration pipeline**. They are **not
  duplicates** — verified: the monolith contains none of the modular handoff
  tokens. The original "drift guard / legacy marker" framing was based on a false
  duplication premise; a "legacy" marker would be actively wrong. The real fix is
  a clarity note so no maintainer mistakes one path for a stale copy of the other.
- **Always-loaded image tables (F5).** The Step 5b image-generation subsection
  (four prompt-construction tables) is only relevant when image-gen exists and the
  user wants figures, yet it sits in the always-loaded SKILL.md. It belongs in a
  reference loaded on demand.
- **Grounding contract restated verbatim (F7).** SKILL.md states the G1/G2/G3
  contract in full, then the Step 2 gate re-explains G1/G2 line-by-line. The
  point-of-action STOP should stay; the verbatim re-explanation is redundant.
- **Slug/output-dir resolution is intricate prose (F8).** The kebab-normalize +
  atomic-`mkdir`-without-`-p` + suffix-retry + resume-scan protocol is executed by
  the agent by hand. The mechanical part is deterministic and error-prone by hand
  — a script should own it, with the agent still doing the CJK→English step and
  the prose retained as a no-Python fallback.

## Out of scope / dropped

- **English trigger phrases in the description (F6) — dropped** at the user's
  direction ("leave F6 for chinese users"); the description stays Chinese-first.
- Rewriting prompt *content* in either prompt path.
- Changing `resource_loader.py`'s chart-field routing behavior (its silent-skip is
  correct; F1 is a doc fix, F2 makes the drift visible).

## Acceptance Criteria

- [x] **F1** SKILL.md contains no reference to `references/charts/radar.md` or to
  "单一图表精细规格 / 13 个" per-chart files; chart specs are documented as living
  in `charts/{basic,advanced,complex}.md` routed via `charts/index.md`.
- [x] **F2** `check_skill.py` gains a check that (a) every literal
  `references/…​.md` path in SKILL.md resolves on disk, (b) brace-form paths
  (`{a,b,c}.md`) are expanded and each resolves, and (c) placeholder/glob forms
  (`<…>`, `*`) are skipped. A deliberately-injected dead reference makes the check
  exit non-zero; the real tree exits 0.
- [x] **F3** SKILL.md says "29 风格预览" (no remaining "28 风格").
- [x] **F4** SKILL.md's reference index states the two-path relationship
  (prompts.md = inline flow; prompts/ = subagent pipeline) so neither reads as a
  stale copy.
- [x] **F5** The four Step-5b image prompt-construction blocks — three tables
  (`generate_image 提示词构造公式`, `风格与配图关键词对应`, `按页面类型调整`) plus the
  `禁止事项` list — live in `references/image-generation.md`; SKILL.md keeps the
  when-to-run/skip trigger **and the 配图时机 flow rule** (generate before each page,
  ≥1/page, save to `images/`) plus a pointer, and the reference index lists the new
  file. No image-generation content is lost.
- [x] **F7** SKILL.md's Step 2 source gate keeps its hard STOP action-rule but no
  longer re-explains G1/G2 in full; it points back to the 来源接地契约 section.
- [x] **F8** `scripts/resolve_output_dir.py` exists and, given an English slug and
  root, deterministically kebab-normalizes and **atomically claims** `<slug>` (or the
  first free `<slug>-N`, N≤99), printing the resolved absolute path. The script owns
  **new-claim only** — resume-dir selection (scan `<slug>*`, reuse the dir whose
  artifacts match this run) stays an agent/prose judgment, not a script guess.
  SKILL.md prefers the script for the claim and retains the manual protocol as an
  explicit no-Python fallback; the prose stays authoritative for both the
  CJK→English step and resume selection. `cli-cheatsheet.md` documents it.
- [x] **Gates** `check_skill.py` reports 0 errors / 0 warnings; `contract_validator.py`
  and `planning_validator.py` still import and run; the two new tests pass —
  `python3 scripts/test_check_skill_refs.py && python3 scripts/test_resolve_output_dir.py`
  (both exit 0); existing `scripts/test_*.py` still pass.
- [x] No quality guarantee weakened: grounding contract (G1/G2/G3 STOP semantics),
  planning gate, taste gate, pipeline-compat, cross-page narrative all still present
  and enforced.

## Boundaries

Touches: `SKILL.md`, `scripts/check_skill.py`, `scripts/resolve_output_dir.py`
(new), `references/image-generation.md` (new), `references/cli-cheatsheet.md`,
`scripts/README.md` (bundled: register the new script), new
`scripts/test_check_skill_refs.py` and `scripts/test_resolve_output_dir.py`.
No change to `resource_loader.py`, `planning_validator.py`, the prompt content,
the styles, or any gate logic.

## Testing Strategy

- F2: dedicated test injects a dead reference into a temp SKILL-like text and
  asserts the checker reports it; asserts brace expansion and placeholder skip;
  **and asserts a dead concrete path is still reported when a `<placeholder>` path
  sits on the same line/row** (the exact shape that hid F1 — forces per-span, not
  per-line, tokenization).
- F8: dedicated test covers normalize (punctuation/case/length≤40), atomic claim
  on a fresh root, and collision → `-2`. No resume test — the script is claim-only.
- F1/F3/F4/F5/F7: goal-based — `check_skill.py` clean + targeted `grep` assertions;
  F5 additionally verified by confirming the moved tables are byte-preserved.

## Assumptions

- Python is already a hard mid-flow dependency (the mandatory `planning_validator.py`
  gate runs before HTML), so F8 preferring a Python helper does **not** introduce a
  new dependency class; the manual fallback preserves the documented no-script
  degradation path regardless.
- `os.mkdir` is atomic on the target POSIX filesystem, preserving the concurrency
  (anti-collision) guarantee the prose protocol provides. This guarantee applies to
  the **claim** path only; **resume** stays a single-writer, agent-selected path per
  the prose (a resume race on one deck is explicitly out of the protocol's scope),
  so the script implements no resume-guessing.

## Risks

- F2 false positives on pattern rows if brace/placeholder handling is wrong →
  mitigated by the dedicated test and by running the checker against the real tree.
- F5 content loss during the move → mitigated by byte-preservation verification.
- F8 behavior drift from the documented protocol → mitigated by the test covering
  claim/collision and by keeping the prose fallback authoritative for the
  CJK→English step.
