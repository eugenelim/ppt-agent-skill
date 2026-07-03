# Plan: proof-gate-enforcement

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing

> **Plan contract:** this is the implementation strategy. When it changes
> substantially, note why in the changelog at the bottom.

## Approach

Add one self-contained stdlib script — `scripts/proof_gate.py` — that owns the
Step-4.5 gate *state*: `--decision review|render-direct` writes
`OUTPUT_DIR/runtime/proof/gate.json`; `--check` exits non-zero (with an actionable
message) when the marker is absent or invalid. `SKILL.md` Step 4.5 records the
decision after the user chooses; Step 5c runs `proof_gate.py --check` before
writing any slide HTML and treats non-zero as a hard STOP. `cli-cheatsheet.md` and
`scripts/README.md` are updated; the test is registered in `smoke_test.py`.

`proof_gate.py` sits beside `proof_worksheet.py` (same `runtime/proof/` write-jail,
same determinism/no-clock discipline). No changes to `milestone_check.py` (see
Declined patterns) or `workflow_versions.py`.

## Declined patterns

- **`PreToolUse` hook blocking `Write` to `slides/`** — the only truly
  unskippable option, but it lives in the *user's* `settings.json`, not the
  portable skill; it would not ship with the skill. Declined (recorded as the
  Known limit in the spec).
- **A cumulative `"4.5"` stage in `milestone_check.py`** — the original design.
  Dropped after pre-EXECUTE review: `milestone_check` stages are *post-render
  acceptance* checks (its Step-4 check requires `slides/`+`png/`), so a cumulative
  `4.5` run pre-render fails on missing slides rather than the marker (the
  reviewer's load-bearing Blocker); and `milestone_check` isn't wired into the
  SKILL flow, so a post-hoc backstop there is dead weight. The user's ask is a
  *pre-render refuse* → `proof_gate.py --check`, which needs no milestone stage.
- **Folding the gate into `proof_worksheet.py`** — that script is a pure,
  byte-deterministic *renderer* with a "writes ONLY the worksheet" contract; adding
  stateful gate mutation muddies its single responsibility. Declined.
- **A timestamp / audit trail in `gate.json`** — breaks determinism (AC4) and
  isn't needed. Declined.
- **`schema_version` sourced from `workflow_versions.py`** — would couple the
  marker to the workflow version bus and touch a boundary the spec forbids; a local
  literal keeps AC4 byte-identity and the boundary. Declined.

## Constraints

- `AGENTS.md` — minimal diff; stdlib only (no new dependency); touch only what the
  feature requires.
- `workflow_versions.py`, `milestone_check.py`, the gallery/style surface, and the
  planning schema are all untouched.

## Tasks

### Task 1 — `scripts/proof_gate.py` (writer + checker)  [TDD]

**Tests:** `scripts/test_proof_gate.py` (no-pytest house style, mirrors
`test_proof_worksheet.py`; `check(name, cond)` helper, `tempfile`, subprocess):
- AC1: `--decision render-direct` on an empty deck dir → `runtime/proof/gate.json`
  exists, parses to `decision == "render-direct"`, exit 0.
- AC2a: `--decision review` with no worksheet for this deck → exit != 0, stderr
  names the missing worksheet.
- AC2b: `--decision review` with the deck's `runtime/proof/<deck>-intent.html`
  present → marker written with `decision == "review"`, exit 0.
- AC3a: `--check` with no marker → exit != 0, stderr asserts the literal substrings
  `proof_gate.py`, `--decision`, and `Step 4.5` all present (pins the "exact
  remediation command" AC, not a loose match).
- AC3b: `--check` after a decision recorded → exit 0.
- AC3c: `--check` with a malformed `gate.json` (bad JSON / missing/invalid
  `decision`) → exit != 0.
- AC4: two `--decision render-direct` runs → byte-identical `gate.json`;
  `schema_version` present; and a `render-direct` → `review` re-decision overwrites
  (last wins), leaving `decision == "review"`.

**Approach:** argparse — positional `output_dir`, mutually-exclusive required
group `--decision {review,render-direct}` / `--check`. Module constants
`SCHEMA_VERSION = "1"` (local literal) and
`GATE_REL = Path("runtime") / "proof" / "gate.json"`.
`record_decision(output_dir, decision)`: for `review`, require the deck's
slug-scoped worksheet `output_dir / "runtime" / "proof" / f"{output_dir.name}-intent.html"`
to exist else raise `ProofGateError`; `mkdir -p` the proof dir; unconditionally
overwrite (idempotent, last-decision-wins) via
`json.dumps({"schema_version": SCHEMA_VERSION, "decision": decision},
ensure_ascii=False, indent=2, sort_keys=True) + "\n"`.
`gate_status(output_dir) -> tuple[bool, str]`: read the marker, parse JSON,
validate `decision in {"review", "render-direct"}`; on any failure return
`(False, <message naming Step 4.5 + the --decision command>)`, else `(True, ok)`.
`--check` prints the message to stderr on failure and returns exit 0/1 from
`gate_status`.

### Task 2 — SKILL.md + cli-cheatsheet + README wiring  [goal-based]

**Done when:** `python3 scripts/check_skill.py` exit 0; `grep` confirms Step 4.5
records the decision via `proof_gate.py --decision` and Step 5c runs
`proof_gate.py --check` as a hard STOP; cheatsheet §629 block + `scripts/README.md`
mention `proof_gate.py`; `test_proof_gate.py` is in `smoke_test.py` phase-1 list.

**Approach:**
- `SKILL.md` Step 4.5 (§178–200): after the Review/Render choice, record it via
  `proof_gate.py OUTPUT_DIR --decision review|render-direct`. Step 5c (§242–246):
  prepend a mechanical precondition — run `proof_gate.py OUTPUT_DIR --check` before
  writing any slide HTML; non-zero exit = hard STOP (you skipped Step 4.5).
- `references/cli-cheatsheet.md` §629 block: add the two `proof_gate.py` commands
  and the Step-5c pre-render check.
- `scripts/README.md` table: add `proof_gate.py` (bundled fix: also add the
  pre-existing-missing `proof_worksheet.py` row while editing the same table).
- Register `test_proof_gate.py` in `scripts/smoke_test.py` phase-1 list.

## Construction tests

Covered per-task above. Integration floor: `smoke_test.py --phase 1` green
(runs `test_proof_gate.py` + `test_proof_worksheet.py` + `check_skill.py`).

## Changelog

- Initial plan.
- Post pre-EXECUTE review: dropped the `milestone_check.py` `"4.5"` stage
  (Blocker: its stages are post-render acceptance, cumulative run fails pre-render
  on missing slides; and it isn't wired into the flow). Pre-render enforcement is
  now solely `proof_gate.py --check` at Step 5c. Fixed status vocabulary, pinned
  `schema_version` as a local literal, and documented `render-direct` as a
  zero-evidence self-attested bypass in the spec's Known limit.
