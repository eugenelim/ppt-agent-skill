# Plan: render-visual-check-and-diagram-routing

- **Spec:** [`spec.md`](spec.md)
- **Mode:** full

## Design (LLD)

Five concerns (A–E in the spec) land as edits to existing scripts/playbooks plus **one**
new script. No new dependency; no `resource_loader.py` routing change; `visual_qa.py`
reused as the mechanical batch gate (not re-implemented).

### Assumption trio

- **Files touched:** `scripts/slide_montage.py` (new) + its test; `scripts/html2png.py`
  + test; `scripts/planning_validator.py` + test; the render-completeness gate
  **extends `scripts/milestone_check.py`** (its `check_step4`/`check_step5` already
  enforce `len(pngs)==pages`; add `visual_qa` batch + PNG-freshness) + test;
  `scripts/smoke_test.py` (phase wiring);
  `scripts/check_skill.py` (diagram-map lockstep assertion); `SKILL.md`;
  `references/prompts/step4/tpl-page-html.md` (the real per-page render template,
  assembled into `runtime/prompt-page-html-N.md`);
  `references/playbooks/step4/page-html-playbook.md`;
  `references/playbooks/step4/page-review-playbook.md`;
  `references/playbooks/step4/page-planning-playbook.md`; `references/cli-cheatsheet.md`.
  **Not touched:** `tpl-page-review.md` / `tpl-page-orchestrator.md` (Stage-3 gate is
  reused as-is, not modified); `scripts/deck_probe.py` (assimilate-slides external-deck
  probe — wrong subsystem); `resource_loader.py`; the export pipeline.
- **"Done" is demonstrated by:** `scripts/smoke_test.py` green with new phases; the
  new TDD self-tests green; grep assertions for the doc/playbook contracts; a manual
  end-to-end render of the fixture deck showing the gate runs, blocks on a seeded
  overflow, and degrades-with-announcement when `node` is forced absent.
- **Not changing:** the `visual_qa.py` check algorithms, the diagram recipe bodies
  (`blocks/diagram*.md`), `resource_loader.py` routing, the export pipeline
  (`html2svg`/`svg2pptx`/`build_pdf`), the proof gate.

### Declined temptations

- Tempted to add **dagre/ELK** (or any layout engine) for deterministic diagram
  layout; **declining** — the spec forbids a new dependency; we ship the O(N)
  CSS-grid-by-layer approximation the research endorses as guidance instead.
- Tempted to write a **new `render_gate.py`** pipeline stage; **declining** —
  `visual_qa.py` batch already is the mechanical terminal check; a second gate script
  is Ask-first and unnecessary.
- Tempted to make `DIAG-ROUTE-01` an **ERROR** (it feels load-bearing); **declining** —
  new checks start WARN (false-positive risk on the diagram-shape heuristic).
- Tempted to auto-run the visual gate whenever slides exist; **declining** — it fires
  only inside an invoked render, preserving "no forced preview".

### Domain-grounding

The one load-bearing external claim — *why LLMs miss first-pass diagram geometry and
what prevents it* — is grounded in [`notes/diagram-first-pass-research.md`]
(citation-backed). No further grounding needed; the rest is repo-internal contract.

## Tasks

Ordering by `Depends on`. T1–T5 are independent; T6 integrates; T7 wires the gate;
T8 is the final regression sweep.

---

### T1 — `planning_validator.py`: `DIAG-ROUTE-01` diagram-routing WARN
**Depends on:** none · **Verification:** TDD

Add a WARN-level check (stable id `DIAG-ROUTE-01`) that fires when:
(a) a card with `card_type == "diagram"` has no `diagram_type`, or its `diagram_type`'s
family file (per the `blocks/diagram.md` selector map) is not in
`resources.block_refs`; or
(b) a card typed `list`/`text`/`process` whose `headline`+`body` matches a
diagram-shape lexicon (pipeline, flow, workflow, architecture, topology, lifecycle,
data flow, sequence, state machine, swimlane, org/hierarchy, roadmap/gantt, network,
map, funnel, matrix/quadrant, cycle) **and** no diagram family file is present in
`block_refs`.
WARN only; ERROR count and exit semantics unchanged; the `diagram_type → family` map
is a module constant mirroring `blocks/diagram.md`. Add a **lockstep guard** (in
`check_skill.py`, run in smoke) asserting the validator's map matches the selector
table in `blocks/diagram.md` so the two can't drift silently.

**Tests:** (`scripts/test_planning_diag_route.py`, wired into smoke)
- diagram card, no `diagram_type` → one `DIAG-ROUTE-01` WARN.
- diagram card, `diagram_type` set but family file absent from `block_refs` → WARN.
- diagram card correctly tagged + family in `block_refs` → no `DIAG-ROUTE-01`.
- `list` card headline "Interview-to-retrieval pipeline", no diagram family → WARN.
- plain `text` card ("Key recommendations") → no finding (no false positive).
- Regression: a known-good fixture planning set → ERROR count unchanged.
- Lockstep: validator map keys/values equal the `blocks/diagram.md` selector entries.

**Done when:** `python3 scripts/test_planning_diag_route.py` passes,
`planning_validator.py` on the existing fixtures reports the same ERROR count as before,
and the lockstep guard passes.

---

### T2 — `scripts/slide_montage.py`: contact-sheet montage (Pillow-only)
**Depends on:** none · **Verification:** TDD

New script: read a deck `png/` dir, natural-sort `slide-*.png` (reuse the
`html2png.py` natural-key), tile into a grid (default cols configurable, thumbnails via
the `build_hero.py:make_thumbnail` pattern), write `<deck-slug>-contact-sheet.png`.
Empty/missing dir → clear message + non-zero exit. Pillow-only, stdlib argparse.

**Tests:** (`scripts/test_slide_montage.py`)
- N fixture PNGs → one output PNG whose dimensions match the expected grid
  (cols × ceil(N/cols)) at the chosen thumb size + gaps.
- natural order: `slide-2` tiles before `slide-10`.
- empty dir → non-zero exit, no output file.

**Done when:** `python3 scripts/test_slide_montage.py` passes; output opens as a valid
PNG; Pillow-only (no new import beyond PIL + stdlib).

---

### T3 — `html2png.py`: launch robustness (module resolution, not getcwd)
**Depends on:** none · **Verification:** TDD

`html2png.py` already passes an explicit `cwd` to `subprocess.run` (so it was *not* the
session's `getcwd` casualty — that was the login-shell Preview server). T3 is a
defensive hardening of **module resolution + temp-script placement**: set `NODE_PATH`
to `<dep_dir>/node_modules` (and/or run node with `cwd = dep_dir`) so puppeteer resolves
regardless of where `work_dir` sits (e.g. a single-file render whose `parent.parent`
is not under `ppt-output`), validate the chosen dir and fall back to a stdlib
`tempfile` dir if inaccessible, and write the temp `.js` there. Preserve `get_dep_dir`
/ `ppt-output` install behavior and the `file://` egress block.

**Tests:** (`scripts/test_html2png_cwd.py` — mirrors `test_html2svg_tmp_isolation.py`)
- The node-launch config resolves `NODE_PATH`/cwd/temp-script to the chosen validated
  dir, independent of `os.getcwd()`.
- (If puppeteer present) a smoke conversion of a fixture HTML located outside
  `ppt-output` succeeds.

**Done when:** `python3 scripts/test_html2png_cwd.py` passes; a real fixture render via
`html2png.py` still produces a PNG.

---

### T4 — Guidance: canonical visual-read path + server/Preview-MCP prohibition (A)
**Depends on:** none · **Verification:** goal-based

Edit `SKILL.md` (env/degradation area), `page-review-playbook.md`, and
`cli-cheatsheet.md`: the agent's own visual read = `html2png.py` (`file://`, headless
puppeteer); **forbid** `python3 -m http.server` and `mcp__Claude_Preview` for that
purpose with the one-line reason (ports/shells/`getcwd`+pyenv under CloudStorage);
scope `open <file>` to a human hand-off. Authoring per `AGENTS.md` format.

**Done when:** greps find the canonical-path statement, the prohibition + rationale,
and the `open`=hand-off scoping in all three files; `check_skill.py` clean.

---

### T5 — Author-time diagram guidance (E): planning strengthen + HTML-stage structure-before-coordinates + first-pass self-check
**Depends on:** none · **Verification:** goal-based

- `page-planning-playbook.md`: replace the "leave `block_refs: []` when unsure"
  instruction with the strengthened recognition→tag→route rule; add the **complexity
  budget** as authoring guidance (8–12 nodes / 10–15 edges → split; dense many-to-many
  → bus, `blocks/diagram.md` §3.1 ④).
- `references/prompts/step4/tpl-page-html.md` **and** `page-html-playbook.md`: add the
  **structure-before-coordinates** step for diagram cards (declare nodes+edges+zones and
  a layer/grid assignment, then CSS-grid-by-layer + algebraic CSS-variable geometry) and
  a **diagram first-pass self-check** in Phase 8 (static, fires only for diagram pages):
  connector endpoints clamped inside target node box, fan-in distributed, no node
  overflow/label clip, no overlap — citing `blocks/diagram.md` §3.1 +
  `notes/diagram-first-pass-research.md`. **Do not** add screenshotting to Stage 2
  (preserve its "只写 HTML，不截图" boundary).

**Done when:** greps confirm each added contract; `check_skill.py` clean.

---

### T6 — Render fan-out contract + render-completeness gate + montage + degradation (A-dispatch, B, C)
**Depends on:** T2 · **Verification:** TDD (gate) + goal-based + manual QA

- **Dispatch contract (SKILL.md Step 5c/6):** render fan-out **must** run the full
  per-page orchestration incl. Stage 3 Review (`tpl-page-orchestrator.md`); an
  HTML-only batch that skips Stage 3 is **forbidden**. Surface the contact sheet
  (`slide_montage.py`) for the human review turn instead of a preview server. Preserve
  "不主动/提前" (no forced preview); the gate is render-scoped.
- **Mechanical render-completeness gate — extend `milestone_check.py`** (`check_step4`
  already enforces `len(pngs)==pages`): add (a) a `visual_qa.py` **batch** run over the
  deck requiring exit ≠ 1, and (b) **PNG-freshness** — each `png/slide-*.png` mtime ≥
  its matching `slides/slide-*.html` (a stale PNG from a prior render must not pass).
  `node`/puppeteer absent → **announced-skip** branch (message names the missing
  capability), never hard-fail, never silent. To keep existing callers byte-stable, add
  the `visual_qa`+freshness behavior behind an opt-in flag (e.g. `--with-visual-qa`)
  that the render-done step passes.
- **Invocation point (closes the residual gap):** SKILL.md Step 5c/6 render-done step
  clears/regenerates `png/` at render start and **runs** `milestone_check.py <stage>
  --output-dir <deck> --with-visual-qa` — nothing ran the existing PNG-count check in
  the session, so naming the invocation is the actual fix.

**Tests:** (`scripts/test_render_gate.py`, wired into smoke)
- fixture deck: slide HTML present, PNG missing → gate = not-done.
- fixture deck: all PNGs present + `visual_qa` clean → gate = done.
- fixture deck: PNG older than its slide HTML (stale) → gate = not-done (freshness).
- node-absent shim → gate = announced-skip (documented exit/marker), not hard-fail.
- regression: existing `milestone_check.py` invocations (without `--with-visual-qa`)
  behave byte-identically.

**Manual QA (record observed output):** render the smoke fixture deck end-to-end →
confirm the gate runs and the contact sheet is written; delete/stale one slide's PNG →
confirm not-done; force `node` absent (PATH shim) → confirm the announced-skip branch.

**Done when:** `python3 scripts/test_render_gate.py` passes; greps confirm the dispatch
contract + montage + degradation wording; manual QA observations recorded.

---

### T7 — Wire smoke_test.py phases
**Depends on:** T1, T2, T3, T6 · **Verification:** goal-based

Add `scripts/smoke_test.py` phases: (i) run `test_planning_diag_route.py`,
`test_slide_montage.py`, `test_html2png_cwd.py`, `test_render_gate.py`; (ii) run the
`check_skill.py` diagram-map lockstep guard; (iii) assert the montage script runs on a
fixture png dir. (T5 is doc-only — covered by the T8 `check_skill.py` grep sweep, not a
smoke phase.)

**Done when:** `python3 scripts/smoke_test.py` passes with the new phases present and
green.

---

### T8 — Regression sweep + contract-drift gates
**Depends on:** T1–T7 · **Verification:** goal-based (final gate)

Run `visual_qa.py` over the pre-existing fixture set → byte-identical verdicts/exit
codes for inputs that trip no new check. Run `check_skill.py`, `planning_validator.py`,
`contract_validator.py`, and the full `smoke_test.py`. Confirm `requirements.txt` /
`package.json` unchanged.

**Done when:** all gates green; no dependency added; spec ACs all `[x]` or
`(deferred: …)`.

## Constraints

- Pillow-only / runtime-free; `visual_qa.py` `0/1/2` exit preserved.
- No `resource_loader.py` routing change; no new pipeline stage/gate script beyond the
  montage.
- New checks WARN-first; degradations announced; no forced preview.

## Risks

- **Diagram-shape lexicon false positives** (T1b) — mitigated by WARN-only + a
  no-false-positive fixture case; heuristic tuned conservative.
- **Review cost** — the fix reuses the *existing* Stage-3 gate (min-2-round loop);
  cost is unchanged from the intended design. B adds no per-slide cost beyond what the
  orchestrator already prescribes — it only stops the fan-out from *skipping* it.
- **Enforcement is behavioral, not textual** — the render-completeness gate checks
  PNG-per-slide existence + `visual_qa` batch (PNGs prove Stage 3 ran), so it can't be
  satisfied by prose alone (the failure mode the pre-EXECUTE review flagged).
- **Gate-script home decided** — extend `milestone_check.py` (its step-4 check already
  does `len(pngs)==pages`); `deck_probe.py` rejected (external-deck probe, wrong
  subsystem). No new standalone gate script.
- **Stale-PNG freshness** — the existing/new PNG count-check can be fooled by leftover
  PNGs on re-render; mitigated by clearing `png/` at render start + an mtime ≥ check.
- **Diagram-shape lexicon** — WARN-only + a no-false-positive fixture case keeps a
  conservative heuristic from blocking a good deck.

## Rollout

Docs/scripts only; no migration. Ships behind the existing opt-in render flow. Reverting
is a straight revert of the PR.

## Changelog

- 2026-07-10 — plan drafted from spec; research folded into E.
- 2026-07-10 — pre-EXECUTE adversarial review: reframed B (reuse existing Stage-3 gate
  + mechanical render-completeness gate, not a duplicate; behavioral not grep), fixed
  template path (`tpl-page-html.md`), reframed D (module resolution), committed gate to
  `milestone_check.py`, added PNG-freshness (stale-PNG defeat), softened E overclaims.
- 2026-07-10 — implemented T1–T8; gates green (`check_skill` 0/0, `smoke_test` 101/0).
- 2026-07-10 — post-implementation adversarial review: broadened diagram-shape cues,
  WARN on unknown `diagram_type`, html2png temp-write fallback, added gate exit-mapping
  test; ACs ticked; two deferrals to `docs/backlog.md`.
