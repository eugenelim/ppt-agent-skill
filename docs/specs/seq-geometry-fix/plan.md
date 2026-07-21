# Plan: sequenceDiagram Geometry Fix

## Task 1 — Write failing geometry-invariant tests (TDD red)
**Depends on:** none
**Mode:** TDD

Tests (materialized as red stubs before EXECUTE):
- `TestGeometryInvariants::test_participant_box_center_matches_lifeline` — renders
  `sequence-notes-all.mmd`, extracts participant box left values and lifeline x1
  values from SVG, asserts each `box_left + col_w//2 == lifeline_x` (±1).
- `TestGeometryInvariants::test_fragment_bounds_align_with_participant_columns` —
  renders inline diagram with left-of note + loop block, checks fragment rect x ≈
  `first_lifeline_x - col_w//2 - 20` (±2).
- `TestGeometryInvariants::test_message_label_uses_transform_centering` — renders
  `sequence-basic.mmd`, asserts `transform:translateX(-50%)` in all edge-label spans.
- `TestGeometryInvariants::test_self_message_no_head_has_no_arrowhead` — renders
  inline `Alice->Alice: think`, asserts `_arrow_polys == 0`.
- `TestGeometryInvariants::test_self_message_with_head_has_arrowhead` — renders
  inline `Alice->>Alice: call`, asserts `_arrow_polys == 1`.
- `TestGeometryInvariants::test_self_message_cross_has_no_arrowhead` — renders
  inline `Alice-xAlice: fail`, asserts `_arrow_polys == 0` AND `_has_cross_marker`.
- `TestGeometryInvariants::test_left_of_note_close_to_lifeline` — renders
  `sequence-notes-all.mmd`, finds left-of note right edge, asserts gap to first
  lifeline ≤ 48px.

Done when: all 7 new tests are red (fail); no existing tests broken.

## Task 2 — Fix BUG-SEQ-A: participant boxes use _cx() [AC-A]
**Depends on:** Task 1
**Mode:** TDD (green for test_participant_box_center_matches_lifeline)

Approach: In `_layout_lifeline`, change the participant box rendering loop.

Old:
```python
for i, pid in enumerate(participants):
    lx = PAD_H + i * col_pitch + (col_pitch - col_w) // 2
```
New:
```python
for pid in participants:
    lx = _cx(pid) - col_w // 2
```

Both top and bottom boxes use this formula.

Done when: `test_participant_box_center_matches_lifeline` green; no regressions.

## Task 3 — Fix BUG-SEQ-B: fragment bounds use _cx() [AC-B]
**Depends on:** Task 2
**Mode:** TDD (green for test_fragment_bounds_align_with_participant_columns)

Approach: Change `_blk_x0/_blk_x1` computation and label left positions.

Old:
```python
_blk_x0 = PAD_H // 2
_blk_x1 = PAD_H + (n_parts - 1) * col_pitch + col_w + PAD_H // 2
```
New:
```python
_blk_x0 = _cx(participants[0]) - col_w // 2 - PAD_H // 2
_blk_x1 = _cx(participants[-1]) + col_w // 2 + PAD_H // 2
```

Change block/else label left from `PAD_H + 4` to `_blk_x0 + 4` in both label
rendering loops.

Done when: `test_fragment_bounds_align_with_participant_columns` green; no regressions.

## Task 4 — Fix BUG-SEQ-C: note placement uses lifeline-center anchor [AC-C]
**Depends on:** Task 3
**Mode:** TDD (green for test_left_of_note_close_to_lifeline)

Approach: Change `_note_geom` and the pre-pass to use `SIDE_NOTE_GAP = 24` anchored
at the lifeline center, not the box edge.

In `_note_geom`:
```python
# Old:
nx = _cx(primary) - col_w // 2 - nw - 8   # left_of
nx = _cx(primary) + col_w // 2 + 8        # right_of
# New:
SIDE_NOTE_GAP = 24
nx = _cx(primary) - nw - SIDE_NOTE_GAP    # left_of
nx = _cx(primary) + SIDE_NOTE_GAP         # right_of
```

In pre-pass (same formula, `_cx_offset[0]` still 0 at that point):
```python
# Old:
_nx = _cx(_nprimary) - col_w // 2 - col_w - 8   # left_of prepass
_nx = _cx(_nprimary) + col_w // 2 + 8            # right_of prepass
# New:
_nx = _cx(_nprimary) - col_w - 24                # left_of prepass
_nx = _cx(_nprimary) + 24                        # right_of prepass
```

Done when: `test_left_of_note_close_to_lifeline` green; no regressions.

## Task 5 — Fix BUG-SEQ-D: message labels use CSS transform [AC-D]
**Depends on:** Task 4
**Mode:** TDD (green for test_message_label_uses_transform_centering)

Approach: Change `left:{mid_x - 30}px` to `left:{mid_x}px;transform:translateX(-50%);`.

Old:
```python
f'left:{mid_x - 30}px;top:{ry - 18}px;'
```
New:
```python
f'left:{mid_x}px;top:{ry - 18}px;transform:translateX(-50%);'
```

The `white-space:nowrap;` already present in the style string is unchanged.

Done when: `test_message_label_uses_transform_centering` green; no regressions.

## Task 6 — Fix BUG-SEQ-E: self-message respects arrow type [AC-E]
**Depends on:** Task 5
**Mode:** TDD (green for all three self-message arrow tests)

Approach: Add `is_cross` and `has_head` checks to the self-message branch.

Old:
```python
if sx == dx2:
    parts.append(...)  # path
    ah = _arrowhead(sx, ry + 8, -1, 0, back=10, half_w=6)
    parts.append(f'<polygon points="{ah}" fill="{_seq_edge}"/>')
```
New:
```python
if sx == dx2:
    parts.append(...)  # path
    if is_cross:
        sz = 6
        parts.append(f'<line x1="{sx - sz}" y1="{ry + 8 - sz}" x2="{sx}" y2="{ry + 8 + sz}" stroke="{_seq_edge}" stroke-width="1.5"/>')
        parts.append(f'<line x1="{sx - sz}" y1="{ry + 8 + sz}" x2="{sx}" y2="{ry + 8 - sz}" stroke="{_seq_edge}" stroke-width="1.5"/>')
    elif has_head:
        ah = _arrowhead(sx, ry + 8, -1, 0, back=10, half_w=6)
        parts.append(f'<polygon points="{ah}" fill="{_seq_edge}"/>')
```

Done when: both self-message arrow tests green; no regressions.

## Declined patterns

- Tempted to refactor `_layout_lifeline` into sub-functions (note renderer, message
  renderer, etc.) — declining; this is a targeted geometry fix, not a refactor.
- Tempted to implement variable-height row packing — declining; architectural change
  beyond scope, deferred per spec.
- Tempted to fix activation y-coordinate tracking — declining; requires activation
  prepass refactor, deferred per spec.
- Tempted to add per-fragment participant-bounds tracking — declining; requires
  parser changes, deferred per spec.
