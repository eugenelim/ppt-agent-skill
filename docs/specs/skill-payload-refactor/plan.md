# Plan: Skill Payload Refactor

## Task 0: Boundary guard (red stub)
**Verification:** TDD — test must exist and fail red before any moves.
**Depends on:** none

**Tests:**
```python
# tests/test_payload_boundary.py
def test_no_test_files_in_scripts(): ...  # fails until moves done
def test_all_scripts_reachable(): ...     # fails until moves done
```

**Approach:** Create `tests/test_payload_boundary.py` that asserts:
(a) `glob("scripts/**/test_*.py", recursive=True)` is empty
(b) All `scripts/*.py` (non-`__init__`) are in the reachable set (grep SKILL.md + cli-cheatsheet + references/ + .claude/skills/ for `scripts/<name>` patterns, plus one level of import parsing)

**Done when:** `pytest tests/test_payload_boundary.py` exits with 2 failures (red).

---

## Task 1: Move 19 test_*.py → tests/ + sys.exit guards
**Verification:** Goal-based — `pytest tests/ -x -q` collects them without collection errors.
**Depends on:** Task 0

**Approach:**
1. `git mv scripts/test_*.py tests/` (all 19 files)
2. Wrap module-level test body in `if __name__ == "__main__":` for all 19 files
3. For 6 files importing tools-bound modules: add `sys.path.insert(0, str(ROOT / "tools"))` (these still fail at import until Task 2; that's OK — the test files exist)
4. Update `tools/smoke_test.py` subprocess paths: `scripts/test_*.py` → `tests/test_*.py`

**Done when:** `pytest tests/ -x -q` runs without collection errors on the script-style tests (they show "no tests collected" for those modules, not errors).

---

## Task 2: Move 7 maintainer scripts → tools/ + internal path fixes
**Verification:** Goal-based — moved scripts run from new location without import errors.
**Depends on:** Task 1 (smoke_test.py path updates already done in Task 1)

**Approach:**
1. `git mv` each file:
   - `scripts/smoke_test.py` → `tools/`
   - `scripts/smoke_skill.py` → `tools/`
   - `scripts/check_skill.py` → `tools/`
   - `scripts/diagram_render_check.py` → `tools/`
   - `scripts/lint_diagram_recipes.py` → `tools/`
   - `scripts/build_hero.py` → `tools/`
   - `scripts/diagram_gallery.py` → `tools/`
2. Fix internal paths in moved scripts:
   - `smoke_test.py`: `lint_diagram_recipes`, `diagram_render_check`, `check_skill` paths: `scripts/` → `tools/`
   - `smoke_skill.py`: add `sys.path.insert(0, str(SCRIPTS_DIR))` before bare imports
   - `build_hero.py`: `ASSETS = ROOT / "assets"` → `ASSETS = ROOT / "docs" / "assets"`
3. Now the 6 test files (Task 1) that add `tools/` to sys.path will import correctly

**Done when:** `python3 tools/smoke_skill.py --dry-run` (or equivalent) runs without import errors; `pytest tests/ -x -q` green on the import step.

---

## Task 3: Move assets/ branding → docs/assets/
**Verification:** Goal-based — `ls docs/assets/` shows the 10 files; `ls assets/` shows only icons/ and proof/.
**Depends on:** none (independent of Tasks 1-2)

**Approach:**
1. `mkdir -p docs/assets`
2. `git mv assets/hero-*.png docs/assets/`
3. `git mv assets/banner.svg docs/assets/`
4. `git mv assets/logo.svg docs/assets/`
5. `git mv assets/architecture.png docs/assets/`
6. `git mv assets/architecture.svg docs/assets/`

**Done when:** `ls assets/` shows only `icons/` and `proof/`.

---

## Task 4: Update all reference files
**Verification:** Goal-based — `grep -r "scripts/smoke_test\|scripts/smoke_skill\|scripts/check_skill\|scripts/lint_diagram\|scripts/build_hero\|scripts/diagram_gallery\|scripts/diagram_render\|assets/hero\|assets/banner\|assets/logo\|assets/architecture" . --include="*.md" --include="*.py" | grep -v ".git\|tools/\|tests/"` yields zero results.
**Depends on:** Tasks 2, 3

**Files to update:**
- `AGENTS.md`
- `SKILL.md`
- `references/README.md`
- `references/styles/index.md`
- `references/principles/failure-modes.md`
- `references/blocks/README.md`
- `references/design-runtime/design-specs.md`
- `.claude/skills/assimilate-slides/references/build-and-ship.md`
- `.claude/skills/assimilate-slides/references/extract-primitives.md`
- `.claude/skills/assimilate-slides/references/extract-style.md`
- `docs/CONVENTIONS.md` (test locations, pytest command, maintainer script locations)
- `docs/architecture/reference.md`
- `docs/backlog.md`
- `README.md` (hero/logo/architecture image paths + directory tree + smoke_test path)
- `README_EN.md` (hero/logo/architecture image paths)
- `scripts/README.md` (remove moved scripts rows)

---

## Task 5: Make boundary guard green + final gates
**Verification:** TDD — both assertions pass.
**Depends on:** Tasks 1-4

**Done when:**
- `pytest tests/test_payload_boundary.py` exits 0 (both tests green)
- `pytest tests/ -x -q` exits 0
- `grep` for all old paths shows zero results
