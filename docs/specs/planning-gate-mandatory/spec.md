# Spec: Planning gate is mandatory and non-bypassable

Mode: full (public-interface / flow-contract change to the Step-4→5 pipeline)

- **Status:** Shipped

## Objective

Ensure a **skeleton planning can never reach slide HTML / PPTX**, by making the
planning content gate (`planning_validator.py`, now skeleton-rejecting via
[planning-content-gate](../planning-content-gate/spec.md)) a **mandatory,
non-bypassable precondition** for HTML generation in the documented flow, and by
**explicitly forbidding the off-pipeline path** that produced the Synchrony
skeleton.

## Background — why this is a doc/flow change, not more code

The gated flow already runs `planning_validator.py` at three points — the
PageAgent self-check (`tpl-page-planning` step 11), the Step-4.4 recovery gate,
and `milestone_check.check_step4`. With the content-gate fix, all three now
reject skeletons. So the **standard pipeline already always runs the gate**.

The recurrence path was going **off-pipeline**: a hand-built deck with a
lightweight single `planning.json` (top-level list, `slide`/`page` keys) plus
custom `build_deck.py` / native-PPTX scripts that invoked **no gate at all** —
and whose schema `planning_validator` can't even parse (`from_payload` handles
neither a top-level list nor the `slide` key). This skill is agent-driven with no
runtime engine, so the only enforcement is a **mandatory instruction that forbids
leaving the gated flow**.

## Change

- **SKILL.md Step 5c** — turn the existing "禁止跳过策划稿直接生成" note into a
  hard gate: **no page's slide HTML may be generated until that page's planning
  has PASSED `planning_validator.py` with zero ERROR** (a `skeleton card` or
  `empty card payload` error blocks HTML).
- **SKILL.md** — add a global rule: **do not hand-roll a deck or use custom build
  scripts that bypass the gated Step-4 flow + `planning_validator.py`**; a
  skeleton planning (cards carrying only a headline) is a **P0 blocker**, not a
  deliverable.
- **references/cli-cheatsheet.md** — reinforce that the Step-4.4 validator run is
  a mandatory blocking gate before HTML, on every path.

## Acceptance Criteria

- [x] SKILL.md Step 5c states HTML generation is **blocked** until the page's
  planning passes `planning_validator.py` (skeleton / empty-payload = block).
- [x] SKILL.md forbids off-pipeline / hand-rolled decks that bypass the gate and
  names a skeleton planning as a P0 blocker.
- [x] `references/cli-cheatsheet.md` marks the planning-gate run as mandatory
  before HTML on every path.
- [x] `git grep` confirms the mandatory-gate and no-bypass wording in SKILL.md.
- [x] `python3 scripts/check_skill.py` exits 0.

## Boundaries

**Out of scope:** teaching `planning_validator.py` to parse the lightweight
off-pipeline schema (top-level list, `slide`/`page` keys). Bridging that schema
is a separate effort; this spec **forbids the path** instead of blessing it.

**Never do:** add a runtime engine/scheduler; change the validator's schema.

## Testing Strategy

Goal-based (no code change; the mechanical gate + its test already exist):
1. `git grep` shows the mandatory-gate + no-bypass wording in SKILL.md and the
   cli-cheatsheet reinforcement.
2. `python3 scripts/check_skill.py` exits 0 (doc↔code contract intact).
