# sequenceDiagram Geometry Fix

**Status:** Shipped
**Mode:** full (multi-bug fix touching rendering geometry, TDD shape, user-specified full mode)

## Objective

Fix five geometry defects in `_layout_lifeline()` in
`scripts/mermaid_render/layout/_strategies.py` that cause participant boxes,
fragment bounds, notes, message labels, and self-message arrowheads to render
incorrectly — without restructuring the renderer or adding new dependencies.

Source analysis: user-provided bug report (2026-07-20) listing five geometry defects in `_layout_lifeline`; findings fully captured in the Acceptance Criteria below.

## Boundaries

**In scope:** `scripts/mermaid_render/layout/_strategies.py` (function
`_layout_lifeline`), `tests/test_fix_sequence.py` (add `TestGeometryInvariants`).

**Bundled baseline re-capture:** 16 sequence snapshot PNGs in
`tests/snapshots/{light,dark}/sequence-*.png` were intentionally re-captured after
the geometry fixes changed pixel output. Visual correctness is attested by the 7
`TestGeometryInvariants` coordinate-invariant tests; the recaptured PNGs guard
against future geometry drift.

**Out of scope:** Variable-height row packing (BUG #4 from report — architectural
change; see [backlog: seq-variable-height-rows](../../backlog.md#seq-variable-height-rows));
activation y-coordinate exact tracking (BUG #1 from report — structural change
requiring activation prepass refactor; see
[backlog: seq-activation-y-tracking](../../backlog.md#seq-activation-y-tracking));
per-fragment participant bounds (BUG #3 from report — follow-up; see
[backlog: seq-per-fragment-bounds](../../backlog.md#seq-per-fragment-bounds));
message-endpoint activation-bar adjustment (BUG #2 from report — follow-up; see
[backlog: seq-message-endpoint-activation](../../backlog.md#seq-message-endpoint-activation));
`scripts/mermaid_layout/_strategies.py` shim (5-line read-through, never edited).

## Acceptance Criteria

- [x] AC-A **Participant box centers align with lifelines**: for every participant,
  `box_left + col_w // 2 == lifeline_x` (±1 for rounding). Verified by rendering
  `sequence-notes-all.mmd` which forces `_cx_offset > 0` via a left-of note.
- [x] AC-B **Fragment bounds track _cx_offset**: fragment rect `x` value equals
  `_cx(participants[0]) - col_w // 2 - PAD_H // 2` (±2). Not hardcoded to
  `PAD_H // 2 = 20`. Block and else labels use `_blk_x0 + 4` not `PAD_H + 4`.
- [x] AC-C **Left-of note uses lifeline-center anchor**: left-of note right edge
  is within `2 × SIDE_NOTE_GAP (48px)` of the first lifeline x. (Old formula
  produced 88px gap; new formula produces 24px gap.)
- [x] AC-D **Message labels use CSS transform centering**: edge-label spans carry
  `transform:translateX(-50%)` and `left:{mid_x}px`, not `left:{mid_x-30}px`.
- [x] AC-E **Self-message respects arrow type**: a `->` (no-head) self-message
  produces 0 arrowhead polygons; a `->>` self-message produces 1. A `-x` self-message
  produces 0 filled polygons and instead renders two cross lines.
- [x] AC-F **All 29 existing tests continue to pass** with no regressions.

## Testing Strategy

**Verification mode:** TDD — write failing tests for each AC, then fix.

Construction tests (written in `plan.md` before EXECUTE):
- `TestGeometryInvariants::test_participant_box_center_matches_lifeline` → AC-A
- `TestGeometryInvariants::test_fragment_bounds_align_with_participant_columns` → AC-B
- `TestGeometryInvariants::test_message_label_uses_transform_centering` → AC-D
- `TestGeometryInvariants::test_self_message_no_head_has_no_arrowhead` → AC-E (no-head)
- `TestGeometryInvariants::test_self_message_with_head_has_arrowhead` → AC-E (has-head)
- `TestGeometryInvariants::test_self_message_cross_has_no_arrowhead` → AC-E (cross: 0 polys + 2 lines)
- `TestGeometryInvariants::test_left_of_note_close_to_lifeline` → AC-C

## Assumptions

1. `_cx_offset[0]` is the only coordinate shift applied; there are no other hidden
   offsets. Verified by reading `_layout_lifeline` source.
2. Lifeline SVG lines are identifiable by `stroke-dasharray="5 4"` and vertical
   direction (`x1 == x2`). Fragment rects use `stroke-dasharray="5 3"`.
3. The `sequence-notes-all.mmd` fixture produces `_cx_offset > 0` because it has
   a `Note left of Alice` that overflows the left margin.
4. Variable-height row packing and exact activation y-coordinates are deferred
   as architectural changes beyond this bug-fix scope.
