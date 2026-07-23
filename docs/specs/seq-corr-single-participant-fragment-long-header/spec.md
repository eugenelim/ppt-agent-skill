Mode: light (no risk trigger fired)

# seq-corr-single-participant-fragment-long-header

**Status:** Shipped

## Objective

Fix single-participant fragment header text overflow: when a loop/alt/opt fragment header
label is wider than the participant box, the row height must accommodate text wrapping and
the rendered HTML span must have `max-width`/`overflow-wrap` to prevent visual overflow.

## Acceptance Criteria

- AC-1: `_block_row_h` uses actual fragment x bounds width (not `canvas_w`) for
  single-participant fragments, so the row height is computed at the correct wrap width.
- AC-2: The fragment header `<span>` has `max-width:{frag_width - 8}px;overflow-wrap:break-word`
  so text wraps visually within the fragment box.
- AC-3: `test_single_participant_fragment_long_header_row_height` passes: long-header fragment
  is taller than short-header equivalent.
- AC-4: `test_single_participant_fragment_header_has_max_width` passes.
- AC-5: `tests/fixtures/sequence-single-participant-fragment-long-header.mmd` exists.
- AC-6: Full test suite (excl. snapshots) passes with no new failures.

## Task list

- [x] T1: Fix `_block_row_h` single-participant branch in `_strategies.py`
- [x] T2: Fix fragment header span max-width in HTML rendering in `_strategies.py`
- [x] T3: Create fixture `.mmd` file
- [x] T4: Add tests to `test_fix_sequence.py`
