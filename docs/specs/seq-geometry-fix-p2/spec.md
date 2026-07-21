# sequenceDiagram Geometry Fix — P2

**Status:** Shipped
**Mode:** light (no risk trigger fired; single-file renderer fix with TDD)

## Objective

Implement the seven deferred sequenceDiagram geometry bugs from
`docs/backlog.md` (SEQ-006/007/008/010/012/013/014) that were explicitly
out-of-scope in the `seq-geometry-fix` spec. Source: user-provided bug report
attached at `.context/attachments/SufzQD/pasted_text_2026-07-20_21-28-09.txt`.

Explicitly deferred from this PR: SEQ-009 (variable-height rows — architectural;
requires browser text measurement), SEQ-011 (horizontal constraint solver —
requires full layout refactor), SEQ-015/016 (gallery semantic gate — P2).

## Acceptance Criteria

- [x] AC-1 **Activation bar baselines (SEQ-006)**: Bob's activation bar `y` ≤ 2px
  from the Alice→Bob request message y; bar bottom ≤ 2px from final response y.
  Carol's activation similarly. Unclosed activations extend to `ll_bot`. Nested
  activations have different x offsets.
- [x] AC-2 **Activation-aware message endpoints (SEQ-007)**: LTR request x2 at Bob
  activation left edge; Bob→Carol x1 at Bob right edge; Bob→Carol x2 at Carol left
  edge. All within 2px tolerance.
- [x] AC-3 **Per-fragment participant bounds (SEQ-008)**: `loop Retry` around
  Server+DB does not extend to Client x; `alt Success/Error` does not extend to DB
  x. Nested inner bounds ⊆ outer bounds.
- [x] AC-4 **Spanning note lifeline-anchored geometry (SEQ-010)**: Spanning note
  left = first lifeline x − 24px; right = last lifeline x + 24px (±2).
- [x] AC-5 **Arrow spec table (SEQ-012)**: `-)` / `--)` render `<circle>` endpoint,
  not triangle. `<<->>` / `<<-->>` produce exactly 2 triangle polygons.
- [x] AC-6 **Parser gaps (SEQ-013)**: `critical ... option` branch renders both
  messages; `rect` renders solid fill (no dashed border, no keyword label);
  `autonumber` is silently accepted.
- [x] AC-7 **Note participant registration (SEQ-014)**: A participant only in a
  `Note over X` gets a lifeline. `activate X` also registers X as a participant.
  `box ... end` blocks don't mis-close enclosing fragments.
- [x] AC-8 **No regressions**: All 29 prior sequence tests continue to pass.

## Testing Strategy

TDD — write red tests for each AC, then implement. All tests in
`tests/test_fix_sequence.py` (`TestActivationBaselines`, `TestActivationAwareEndpoints`,
`TestFragmentParticipantBounds`, `TestSpanningNoteGeometry`, `TestArrowSpecTable`,
`TestParserGaps`, `TestNoteParticipantRegistration`).
