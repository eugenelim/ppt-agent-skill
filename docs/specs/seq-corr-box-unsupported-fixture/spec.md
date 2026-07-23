**Mode:** light (no risk trigger fired)

**Status:** Shipped

# seq-corr-box-unsupported-fixture

## Objective

Parse the Mermaid `box` directive in sequence diagrams and render a colored group background behind grouped participants. Currently `box` is caught by `_SEQ_SKIP_RE` and turned into a Diagnostic — the color, label, and participant membership are discarded.

## Acceptance Criteria

- [x] AC-1: `box` is parsed before `_SEQ_SKIP_RE`; color and label are extracted.
- [x] AC-2: Participants declared inside a `box`…`end` block are tracked as members of that box.
- [x] AC-3: Each box with at least one recognized participant renders a full-height positioned `<div data-box-group="true">` behind the participants.
- [x] AC-4: A non-empty box label renders as an absolutely-positioned sibling `<span>` at top-4px, centered over the box width.
- [x] AC-5: Multiple disjoint boxes render independent backgrounds (count == number of boxes with members).
- [x] AC-6: Diagrams with no `box` directive contain no `data-box-group` attribute.
- [x] AC-7: `tests/fixtures/sequence-box-unsupported.mmd` fixture file exists and `_dispatch` renders it without error.
- [x] AC-8: Full test suite (excluding snapshot tests) passes with no regressions.

## Testing Strategy

Eight new unit tests added to `tests/test_fix_sequence.py` under a new `TestBoxGroups` class:

- `test_box_background_rect_rendered` — AC-3 (full-height div, z-order before participants)
- `test_box_label_rendered` — AC-4 (label span at top:4px, centered)
- `test_no_box_in_non_box_diagram` — AC-6
- `test_multiple_boxes_rendered` — AC-5
- `test_title_only_box_uses_label_not_color` — AC-1 (title-only: label not misused as color)
- `test_named_color_appears_in_background` — AC-1 (named CSS color reaches background CSS)
- `test_functional_color_appears_in_background` — AC-1 (rgb() color reaches background CSS)
- `test_box_named_participant_message_renders` — regression (participant named Box not dropped)

The fixture file exercises AC-7 via the glob-parametrized tests in `tests/test_render_correctness.py` (the fixture is added to `_NO_PATHS` since it renders without path-annotated geometry).

## Task List

1. Add lean spec (this file)
2. Modify `scripts/mermaid_render/layout/_strategies.py`:
   - Initialize `_all_box_groups`, `_open_box_stack`, `_block_type_stack` before `_ensure_p`
   - Modify `_ensure_p` to add newly-registered participants to the current open box
   - Add `box` handler before the `_SEQ_SKIP_RE` check in the parsing loop
   - Push `"block"` to `_block_type_stack` in the `_SEQ_BLOCK_RE` handler
   - Pop `_block_type_stack` in the `end` handler; pop `_open_box_stack` when type is `"box"`
   - Render box backgrounds as positioned divs before participant boxes in HTML emission
3. Create `tests/fixtures/sequence-box-unsupported.mmd`
4. Add `TestBoxGroups` class to `tests/test_fix_sequence.py`

## Boundaries

Not changing:
- `SequenceGeometry` dataclass (no new exported geometry fields)
- SVG renderer or any other diagram type

Deliberate changes beyond the obvious:
- `_SEQ_SKIP_RE`: `box` alternation removed (the box handler intercepts `^box(?:\s|$)` first; keeping `box` in the skip regex would silently drop messages from a participant named `Box` since `^box\b` matches `Box->>...`)
