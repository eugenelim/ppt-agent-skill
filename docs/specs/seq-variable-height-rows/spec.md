# sequenceDiagram Variable-Height Row Packing (SEQ-009)

**Status:** Shipped
**Mode:** light (no risk trigger fired; single-file renderer fix with TDD)

## Objective

Replace the fixed `ROW_H = 40` row grid in `_layout_lifeline` with a
two-pass variable-height accumulator so that note rows expand to fit their
text, and all downstream y-positions (messages, activation bars, fragment
rects, canvas height) shift accordingly.

Scope: heuristic text-height estimation via character count + average char
width at 10 px. Pixel-accurate Playwright measurement is deferred
(see `docs/backlog.md → seq-variable-height-rows-playwright`).

## Acceptance Criteria

- [x] AC-1 **Long note row expands**: A note with ≥ 80 chars produces a
  note polygon whose height > `ROW_H − 8` (32 px).
- [x] AC-2 **Subsequent rows shift**: A message after a long note has a
  larger y-coordinate than after a short note (downstream rows shift);
  and message y > note polygon bottom edge.
- [x] AC-3 **Canvas height grows**: A diagram with a long note has a
  taller `canvas_h` than the identical diagram with a short note.
- [x] AC-4 **Fragment height covers tall rows**: A loop block containing a
  long note produces a background rect taller than the same block with a
  short note.
- [x] AC-5 **No regressions**: All 61 sequence tests continue to pass.

## Boundaries

- **Never do**: Playwright or any browser launch in the `_layout_lifeline` hot path.
- **Never do**: introduce a new package dependency for font metrics.

## Testing Strategy

TDD for AC-1–AC-4 (new `TestVariableHeightRows` class in `tests/test_fix_sequence.py`); AC-5 verified by full suite green.

## Tasks

1. Write red tests for AC-1 through AC-4 in `tests/test_fix_sequence.py`
   (class `TestVariableHeightRows`).
2. Add `_row_h_list` / `_row_top_list` accumulator in `_layout_lifeline`,
   replacing `n_rows * ROW_H` in `ll_bot` and `canvas_h`.
3. Update `_note_geom`, the SEQ-006 event-y pass, Pass A (fragment rects),
   Pass B (messages/notes), and Pass C (labels) to use the per-row arrays.

## Declined patterns

- Playwright in hot path: adds a full browser startup per render call;
  heuristic is sufficient for real-world overflow cases.
- Font-metrics library: new dependency for marginal accuracy improvement.
- Variable-height message rows: message labels at `ry − 18` rarely overflow
  in practice; deferred as a follow-up.
