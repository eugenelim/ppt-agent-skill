Mode: full (structural change — new lifecycle geometry for sequence participants; unfamiliar territory)

# seq-corr-create-destroy-fixture

**Status:** Active

## Objective

Implement `create participant` and `destroy` lifecycle rendering for sequence diagrams.
Currently both directives are parsed but emit `Diagnostic` entries and render as if
the participant always exists (full lifeline, symmetric top/bottom boxes).

## Background

Mermaid supports dynamic participant lifecycle:

```
sequenceDiagram
    participant Alice
    Alice->>Bob: Hello
    create participant Carol
    Alice->>Carol: Welcome
    destroy Bob
    Bob-->>Alice: Goodbye
```

**Expected mmdc-compatible behavior:**
- `create participant Carol`: Carol's top box does not appear at diagram top; Carol's lifeline
  starts at the row where `create` occurs (mid-diagram). Carol gets a top box at the creation
  point.
- `destroy Bob`: Bob's lifeline ends at the row of `destroy`. Bob's bottom box is replaced
  by an "X" marker (crosshead) at the destruction point. Bob's body box may still appear
  at the bottom.

**Current state:**
- Both directives produce `Diagnostic` entries (feature keys `create_participant`, `destroy`).
- The participant is registered and rendered as always-present (no lifecycle geometry).
- `SequenceGeometry` does not expose `created_at` or `destroyed_at` info per participant.

## Acceptance Criteria

- [ ] AC-1: `create participant NAME` causes `ParticipantGeometry.created_at_row` (or
  equivalent field) to be set to the row index of the creation event; `top_box` is absent
  (or placed at the creation row, not y=0).
- [ ] AC-2: The created participant's lifeline starts at the creation row, not at the top
  of the diagram.
- [ ] AC-3: `destroy NAME` causes `ParticipantGeometry.destroyed_at_row` (or equivalent)
  to be set to the destroy row index; the lifeline ends at that row.
- [ ] AC-4: An X/crosshead marker is rendered at the destruction point (center of participant
  lifeline at the destroy row y-coordinate).
- [ ] AC-5: The `Diagnostic` entries for `create_participant` and `destroy` are removed
  (replaced by real geometry).
- [ ] AC-6: `tests/fixtures/sequence-create-destroy.mmd` fixture created with:
  - 1 `create participant` mid-diagram
  - 1 `destroy` mid-diagram
  - Messages to/from both lifecycle participants
- [ ] AC-7: `structural_geometry` for the fixture reports `render`.
- [ ] AC-8: Existing tests (no create/destroy) continue to pass.

## Assumptions

- **`ParticipantGeometry`**: New fields needed: `created_at_row: Optional[int] = None`,
  `destroyed_at_row: Optional[int] = None`. These are additive; existing code ignoring them
  is safe.
- **Lifeline clipping**: Lifeline `y1` = `ll_top + _row_top_list[created_at_row]` when set;
  otherwise `ll_top` (current behavior).
- **Top box for created participants**: Placed at creation row y (centered on row), not y=0.
- **Bottom box for destroyed participants**: Not rendered; X marker placed instead.
- **Destroy X marker**: Two crossed lines, ~16px each arm, at the lifeline center x,
  at the destroy row's midpoint y.

## Testing strategy

- Unit tests in `test_sequence_geometry.py`: assert `created_at_row` and `destroyed_at_row`
  fields on `ParticipantGeometry` when the directives are present.
- Unit tests in `test_fix_sequence.py`: assert X marker appears in HTML for destroyed
  participants; assert lifeline starts late for created participants.
- New fixture for integration check.

## Deferred

- `create actor NAME` (non-participant creation) — defer to follow-up.
- Self-destruction (`destroy self` in self-message context) — defer.
- Multiple create/destroy for the same participant — defer.
