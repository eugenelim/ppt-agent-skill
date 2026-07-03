# Spec: proof-gate-enforcement

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** [`../slide-intent-review/spec.md`](../slide-intent-review/spec.md)
- **Contract:** none
- **Shape:** service

Mode: full (structural + public-interface change — new script `proof_gate.py`
documented in `SKILL.md` / `references/cli-cheatsheet.md`)

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The Step 4.5 Review/Render gate ([`slide-intent-review`](../slide-intent-review/spec.md))
is **prose only**. A model that had the hardened `[STOP -- 必须先问 Review/Render，禁止跳过]`
instruction in-context still slid Step 4 → Step 5 without asking: in the
`OSS Client Onboarding` run (session `c7c27a2a`), `proof_worksheet.py` never ran,
no Review/Render choice was presented, and the loop went straight from writing
planning files to writing slide HTML.

This spec adds a **pre-render check the model must run before writing any slide
HTML**: a new `scripts/proof_gate.py` that (a) records the user's Review/Render
decision to `OUTPUT_DIR/runtime/proof/gate.json` (`--decision`), and (b) exits
non-zero if that marker is absent (`--check`). `SKILL.md` Step 5c gains a hard
precondition — run `proof_gate.py --check` first; a non-zero exit is a hard STOP
meaning Step 4.5 was skipped. This converts the soft behavioral instruction
("remember to ask the user") into a concrete, verifiable command with a binary,
self-correcting failure.

**Known limit (surfaced, not resolved).** This is still *prose-invoked* — the
model runs `proof_gate.py --check` because Step 5c says to; a model that skips the
whole gate could skip the check too. And the marker only proves *a decision was
recorded*, not that a review happened: `--decision render-direct` is a
**zero-evidence, self-attested bypass** (option B legitimately renders without a
worksheet). The gain over the status quo is real but bounded — a concrete
tool-invocation with a loud binary failure is followed far more reliably than a
soft "ask first" instruction, and recording a decision forces a deliberate act
rather than silent drift. A truly *un*skippable gate needs a harness `PreToolUse`
hook, which lives in user `settings.json`, not in the portable skill — out of
scope here (see Plan's declined patterns).

## Acceptance Criteria

- [x] **AC1** `proof_gate.py OUTPUT_DIR --decision render-direct` creates
  `OUTPUT_DIR/runtime/proof/gate.json` recording `decision: "render-direct"` and
  exits 0 (creating `runtime/proof/` if absent). `--decision` is
  **idempotent-overwrite**: a later `--decision` (same or different value) replaces
  the marker — last decision wins, no error (a user may change their mind).
- [x] **AC2** `proof_gate.py OUTPUT_DIR --decision review` exits non-zero with an
  actionable message when the deck's worksheet (`<OUTPUT_DIR-name>-intent.html`
  under `runtime/proof/`) does not exist; with it present it writes the marker
  (`decision: "review"`) and exits 0. The check is slug-scoped (matches the current
  deck's worksheet, not any stale `*-intent.html`), and confirms *a* worksheet was
  rendered — not that its content matches the current planning (see Known limit).
- [x] **AC3** `proof_gate.py OUTPUT_DIR --check` exits 0 iff `gate.json` exists and
  parses to a valid `decision`; otherwise exits non-zero and its message names the
  skipped Step 4.5 gate and the exact `--decision` command to record it. A
  malformed/absent/invalid marker all fail.
- [x] **AC4** `gate.json` is deterministic — no system-clock or network read; its
  on-disk shape is the two keys `schema_version` and `decision` (sorted);
  `schema_version` is a local literal in `proof_gate.py` (not sourced from
  `workflow_versions.py`); two successive `--decision render-direct` runs produce
  byte-identical files.
- [x] **AC5** `SKILL.md` Step 4.5 instructs recording the decision via
  `proof_gate.py --decision` after the user chooses; Step 5c instructs running
  `proof_gate.py --check` before writing any slide HTML and treats a non-zero exit
  as a hard STOP (Step 4.5 was skipped).
- [x] **AC6** `references/cli-cheatsheet.md` documents `proof_gate.py --decision`
  / `--check` and the Step-5c pre-render check.
- [x] **AC7** `scripts/test_proof_gate.py` covers AC1–AC4, is registered in
  `scripts/smoke_test.py` phase-1 test list, and `scripts/README.md` lists
  `proof_gate.py`.
- [x] **AC8** `python3 scripts/check_skill.py` and
  `python3 scripts/smoke_test.py --phase 1` stay green (no new
  `check_skill.py` rule is tripped by the SKILL.md / cheatsheet edits).

### Folded-in behavior changes (same PR, user-directed)

Rendering is expensive per slide — not the (already-batched, ~1s/slide) export
scripts, but the **LLM turns generating each bespoke slide's HTML in Step 5c**
(~40–60s/slide; the OSS run took ~7 min for 8 slides). So the render must be
opt-in, and the skill must activate on English prompts.

- [x] **AC9 (plan-first default)** `SKILL.md` Step 4.5 defaults to **A (先评审)**
  and, after worksheet review, **stops at the plan and hands control back** — it
  does not auto-advance to Step 5 render; render happens only on an explicit user
  request. Option B (直接出图) remains for an explicit immediate render.
- [x] **AC10 (render/export opt-in)** `SKILL.md` Step 6 is no longer
  `[必做]`/`禁止跳过`; it produces preview/SVG/PPTX only when the user has asked to
  render, never eagerly up front. `README.md` quick-start flow reflects the
  plan-first pause.
- [x] **AC11 (English activation triggers)** the `description:` frontmatter leads
  with English trigger phrases ("make slides on X", "turn this doc into a
  presentation", …) so the skill activates on English prompts, retaining the
  Chinese triggers.

## Boundaries

### Always do

- Write the marker only under `OUTPUT_DIR/runtime/proof/`; produce deterministic
  content (no clock, no network).

### Ask first

- Any change to the planning schema, `planning_validator.py`, or the Step-0
  interview-anchor contract (none needed here).
- Adding any runtime dependency (none needed — stdlib only).

### Never do

- Read the system clock or network when writing/reading the marker.
- Require a worksheet for the `render-direct` decision (option B legitimately
  skips the worksheet).
- Block `--check` on anything other than marker presence/validity.
- Touch `workflow_versions.py` version constants, `milestone_check.py`, or the
  gallery/style surface.

## Testing Strategy

- **TDD** — `proof_gate.py` (deterministic, compressible invariants): AC1–AC4 via
  `scripts/test_proof_gate.py`, no-pytest house style (subprocess + exit-code
  assertions + byte-identity), mirroring `test_proof_worksheet.py`.
- **Visual / manual QA** — `proof_gate.py` is a CLI the model invokes: run both
  `--decision` values and `--check` (pass and fail) on a temp fixture end-to-end
  and record observed exit codes / stderr.
- **Doc wiring** — `check_skill.py` green; grep confirms SKILL.md Step 4.5/5c and
  cli-cheatsheet mention the new commands.

## Assumptions

- **Verified:** `proof_worksheet.py` writes `runtime/proof/<deck-slug>-intent.html`
  (deck-slug = `OUTPUT_DIR` dir name), so `--decision review` detects the deck's
  worksheet by the slug-scoped name `<OUTPUT_DIR-name>-intent.html`.
- **Milestone backstop declined** — a cumulative `"4.5"` stage in
  `milestone_check.py` was dropped after review (it is post-render acceptance and
  unwired from the flow); rationale in [`plan.md`](plan.md) Declined patterns. A
  future formal-acceptance wiring can add a marker check to
  `check_preview`/`check_step5` (follow-up in `docs/backlog.md`).
