# Plan: Per-deck output layout convention

Single goal-based task — a documentation-only change (no `scripts/` logic), so
the plan is thin. Verification mode: **goal-based** (grep + `check_skill.py`
regression guard), per the spec's Testing Strategy. No TDD stubs (mode).

## Task 1 — Document the per-deck layout across the five doc files

Depends on: none

Approach: introduce `OUTPUT_ROOT` (shared parent `ppt-output/`) and relocate
`OUTPUT_DIR` to `OUTPUT_ROOT/<deck-slug>/` in the SKILL.md path-convention table
and output-structure block; add the slug rule (kebab normalization, resolve-once
timing, new-vs-resume dedup with the `<slug>*` scan); mirror the convention into
`references/cli-cheatsheet.md` (intro only — commands are `OUTPUT_DIR`-relative
and unchanged), `docs/architecture/overview.md` (tree line + runtime prose), and
`README.md` / `README_EN.md` (output-location lines + tree comments).

Done when (goal-based checks, from the spec's Testing Strategy):
- `git grep 'OUTPUT_ROOT'` and `git grep '<deck-slug>'` in `SKILL.md` non-empty;
  resume/dedup rule text present.
- `git grep` for the per-deck folder non-empty in `README.md`, `README_EN.md`,
  `docs/architecture/overview.md`.
- `git grep '在 Step 1 完成后立即确定' SKILL.md` empty (contradicting line gone).
- `python3 scripts/check_skill.py` exits 0.
- `git diff --name-only` touches no `scripts/`.

## Changelog

- Landed as documentation-only; no code path changed (safety confirmed by the
  smoke test's existing `OUTPUT_DIR=ppt-output/e2e-test/` precedent). Two
  script-docstring nits and the SKILL.md-vs-cli-cheatsheet filename drift
  deferred per the spec's Boundaries.
