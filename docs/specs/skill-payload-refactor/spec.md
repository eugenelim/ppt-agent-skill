# Spec: Skill Payload Refactor

**Status:** Done
**Branch:** `eugene/skill-payload-refactor`

---

## Objective

Move non-adopter files out of the three official skill folders (`scripts/`, `assets/`, `references/`) so each official folder contains **only adopter-facing artifacts**. This enforces the agentskills.io payload boundary — the bundled payload is exactly `SKILL.md` + `scripts/` + `assets/` + `references/` — and is a prerequisite for a clean Playwright migration.

No behavior changes. Pure structural move + reference update + sys.path/path fixes.

---

## Classification Method

A file **stays** in an official folder **iff** it is adopter-facing at skill runtime.

**Reachability roots** (for `scripts/`):
1. `SKILL.md` (main skill entry point)
2. `references/cli-cheatsheet.md` (the script invocation reference loaded by every agent run)
3. Any `.md` file under `references/` or `.claude/skills/*/` that directly invokes `scripts/<name>` at runtime

**Resolution algorithm:**
1. Grep all roots for `scripts/<name>.py` or `scripts/<name>` patterns → **directly reachable set**.
2. For each directly reachable `.py`, parse its Python `import` statements → add those scripts to the set (one level, since scripts import stdlib + sibling scripts only) → **transitively reachable set**.
3. Union = reachable. Everything else moves.

For `assets/`: referenced by `SKILL.md`, any `references/*.md`, or an adopter-facing script at runtime → stays. Gallery/branding images referenced only by README move.

For `references/`: all content is adopter-facing (audit confirmed no non-adopter content).

---

## Acceptance Criteria

- [ ] No `test_*.py` under any official folder.
- [ ] Every remaining `scripts/*.py` is adopter-facing per the method above (one-line rationale per moved file in PR).
- [ ] `assets/` contains only adopter-runtime resources (`icons/`, `proof/`) — hero gallery + branding live under `docs/assets/`.
- [ ] `references/` audited — no non-adopter content (no moves needed).
- [ ] All references updated; repo-wide grep for old paths is clean.
- [ ] Gates green: `pytest tests/ -x -q` passes (existing tests + moved tests with pytest-safe guards); lint passes.
- [ ] `tests/test_payload_boundary.py` exists and passes: (a) `glob('scripts/**/test_*.py')` is empty, (b) all `scripts/*.py` (non-package, non-`__init__`) are in the reachable set derived from the roots above.
- [ ] `docs/CONVENTIONS.md` updated to reflect new test locations and new `tools/` maintainer-script location.

---

## Testing Strategy

**Goal-based** + existing suite green from new locations.

- **Boundary guard** (`tests/test_payload_boundary.py`): implements the reachability check above as a pytest test; built in task 0 before any moves, expected to fail red until moves complete.
- **pytest** (`pytest tests/ -x -q`): all existing tests pass; moved script-style tests are importable (module-level sys.exit calls guarded; see "Sys.exit guards" below).
- **Grep verification**: after each batch of moves, `grep -r "scripts/<old-name>" .` (excluding .git and new location) yields zero.

---

## Sys.exit guards (required minimal change)

Script-style tests call `sys.exit(1)` at module scope. When pytest collects them, this aborts the whole run. The minimal fix is wrapping the test body in `if __name__ == "__main__":`. This is not a behavior change — when run directly (`python3 tests/test_foo.py`) they work identically; pytest simply finds no `test_*` functions and moves on.

Files confirmed to need the guard (conditional or unconditional module-level exit):
`test_arch_canvas_mock.py`, `test_build_pdf.py`, `test_check_skill_refs.py`, `test_deck_probe.py`,
`test_diagram_qa.py`, `test_gallery_toggle.py`, `test_html2png_cwd.py`, `test_html2svg_tmp_isolation.py`,
`test_html_packager.py`, `test_icon_search.py`, `test_planning_content_gate.py`,
`test_planning_diag_route.py`, `test_proof_gate.py`, `test_proof_worksheet.py`,
`test_reference_page_types.py`, `test_render_gate.py`, `test_resolve_output_dir.py`,
`test_slide_montage.py`, `test_visual_qa_contrast.py`.

Pattern: all module-level code below the imports and constant definitions wraps in `if __name__ == "__main__":`.

---

## Moves

### `scripts/` → `tests/` (all 19 `test_*.py`)

All 19 `scripts/test_*.py` files move to `tests/`. Additional path fixes per file:
- 6 files import tools-bound modules: add `sys.path.insert(0, str(ROOT / "tools"))` after existing `sys.path.insert(0, str(ROOT / "scripts"))`.
  - `test_arch_canvas_mock.py` (imports `smoke_test`)
  - `test_check_skill_refs.py` (imports `check_skill`)
  - `test_diagram_qa.py` (imports `lint_diagram_recipes`)
  - `test_planning_content_gate.py` (imports `smoke_skill`)
  - `test_planning_diag_route.py` (imports `smoke_skill`)
  - `test_proof_worksheet.py` (imports `smoke_skill`)

### `scripts/` → `tools/` (maintainer-only)

| File | Rationale |
|------|-----------|
| `smoke_test.py` | `skill 作者/维护者` per scripts/README.md; not in SKILL.md/cli-cheatsheet workflow |
| `smoke_skill.py` | `skill 作者/维护者` per scripts/README.md |
| `check_skill.py` | `skill 作者/维护者` per scripts/README.md; `维护与校验` section of SKILL.md (not runtime) |
| `diagram_render_check.py` | Only called by `smoke_test.py` (itself a maintainer tool) |
| `lint_diagram_recipes.py` | Maintainer linter; not invoked at runtime in SKILL.md/cli-cheatsheet |
| `build_hero.py` | Generates repo hero images; maintainer tool |
| `diagram_gallery.py` | QA visualization gallery; not referenced at runtime |

Path fixes for tools/ scripts:
- `smoke_test.py`: update subprocess path strings for `lint_diagram_recipes.py` and `diagram_render_check.py` and `check_skill.py` (scripts/ → tools/); update all `scripts/test_*.py` strings → `tests/test_*.py`.
- `smoke_skill.py`: add `sys.path.insert(0, str(SCRIPTS_DIR))` before bare sibling imports.
- `build_hero.py`: update `ASSETS = ROOT / "assets"` → `ASSETS = ROOT / "docs" / "assets"`.
- `check_skill.py`: already has `sys.path.insert(0, str(SCRIPTS_DIR))` — no change needed.
- `diagram_render_check.py`: `ROOT / "scripts" / "mermaid_layout"` reference stays valid (mermaid_layout stays).
- `lint_diagram_recipes.py`, `diagram_gallery.py`: no internal path changes needed.

### `assets/` → `docs/assets/` (internal gallery + branding)

`hero-all.png`, `hero-cultural-oriental.png`, `hero-dark-professional.png`,
`hero-light-premium.png`, `hero-natural-retro.png`, `hero-vibrant.png`,
`banner.svg`, `logo.svg`, `architecture.png`, `architecture.svg`.

### `assets/` — STAY

| Path | Rationale |
|------|-----------|
| `assets/icons/` | Referenced at runtime by SKILL.md, `references/icons.md`, `scripts/icon_search.py` |
| `assets/proof/` | Referenced at runtime by SKILL.md, `scripts/proof_worksheet.py` |

### `scripts/` — STAY (adopter-facing at runtime)

| File | Reachability |
|------|-------------|
| `assemble_planning.py` | Direct: `references/prompts/step4/tpl-page-planning.md` |
| `build_pdf.py` | Direct: `references/playbooks/print-combiner-playbook.md` |
| `contract_validator.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `deck_probe.py` | Direct: `.claude/skills/assimilate-slides/SKILL.md` (a runtime root per Classification Method) |
| `gallery.py` | Direct: SKILL.md Step 5a |
| `html2png.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `html2svg.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `html_packager.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `icon_search.py` | Direct: `references/icons.md` |
| `mermaid_layout/` | Direct: `references/prompts/step4/tpl-page-orchestrator.md` invokes it |
| `milestone_check.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `planning_validator.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `png2pptx.py` | Direct: cli-cheatsheet.md Step 5 |
| `proof_gate.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `proof_worksheet.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `prompt_harness.py` | Direct: cli-cheatsheet.md |
| `resolve_output_dir.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `resource_loader.py` | Direct: cli-cheatsheet.md |
| `slide_montage.py` | Direct: SKILL.md |
| `subagent_logger.py` | Direct: scripts/README.md (subagent role); cli-cheatsheet.md Step 4 references it |
| `svg2pptx.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `visual_qa.py` | Direct: SKILL.md, cli-cheatsheet.md |
| `workflow_versions.py` | Transitive: `contract_validator.py` → `planning_validator.py` → `workflow_versions.py` |

---

## Known reference update sites

All sites where moved paths appear and must be updated:

**scripts/ → tools/ references:**
- `AGENTS.md` lines ~141–143, ~208
- `SKILL.md` `维护与校验` section
- `references/README.md`
- `references/styles/index.md`
- `references/principles/failure-modes.md`
- `references/blocks/README.md`
- `references/design-runtime/design-specs.md`
- `.claude/skills/assimilate-slides/references/build-and-ship.md`
- `.claude/skills/assimilate-slides/references/extract-primitives.md`
- `.claude/skills/assimilate-slides/references/extract-style.md`
- `docs/CONVENTIONS.md`
- `docs/architecture/reference.md`
- `docs/backlog.md`
- `README.md`
- `scripts/README.md` (row for moved maintainer scripts)

**scripts/ → tests/ references:**
- `docs/CONVENTIONS.md` (test location descriptions + pytest run command)
- `scripts/README.md` (remove test_*.py rows, or note they moved)
- `tools/smoke_test.py` (all `scripts/test_*.py` subprocess paths)

**assets/ → docs/assets/ references:**
- `README.md` (logo.svg, hero-*.png, architecture.png, banner.svg)
- `README_EN.md` (same)
- `README.md` directory tree listing

---

## Boundaries

- No Playwright migration; Node stays exactly as-is.
- No behavior changes — moves + sys.path/path fixes + sys.exit guards only.
- No `package.json` / `requirements.txt` changes.
- No CI (`tests.yml`) changes — CI gate expansion is out of scope; noted as a follow-up.
- `references/` audited: no non-adopter content found; no moves.
