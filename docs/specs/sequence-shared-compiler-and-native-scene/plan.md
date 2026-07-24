# Implementation Plan — Sequence Shared Compiler and Native Scene

**Status:** Approved

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_geometry.py` (new `BoxGeometry`,
   extend `FragmentGeometry`, extend `SequenceGeometry`); `scripts/mermaid_render/layout/
   _sequence_compile.py` (populate new fields; refactor into parse/compile/paint);
   `scripts/mermaid_render/native_svg.py` (replace `_sequence_scene` to call shared
   compiler); `scripts/mermaid_render/layout/sequence.py` (delete after no imports);
   `tests/test_sequence_shared_compiler.py` (new).
2. Done when: both sequence fixtures pass in the canonical runner; `layout/sequence.py` is
   deleted and no import references it; `data-box-id` and `data-fragment-id` attributes
   match in HTML and SVG; `layout_backend == "sequence-geometry"` for both.
3. Not changing: HTML sequence painter behavior (only refactoring its entry point);
   existing sequence fixture `.mmd` files; existing passing tests for sequences.

**Declined patterns:**
- Tempted to derive box hierarchy from HTML after painting; declining — spec requires
  populating `BoxGeometry` from the already-parsed `_all_box_groups` in the compiler,
  not from HTML introspection.
- Tempted to keep `layout/sequence.py` as a thin shim; declining — spec requires deletion
  after both fixtures pass.
- Tempted to add a `"native-svg"` fallback for unsupported constructs; declining — spec
  requires a typed diagnostic instead of silent omission.

---

## Tasks

### Task 1: BoxGeometry and FragmentGeometry IR extensions
Depends on: none
Verification: TDD

**Tests:**
- `test_box_geometry_fields`: compile `sequence-box-unsupported`; assert two
  `BoxGeometry` records with matching `box_id`, `label`, `color`, `participant_ids`.
- `test_fragment_geometry_parent_fields`: compile `sequence-nested-fragments`; assert
  inner fragment's `parent_fragment_id` equals outer fragment's `fragment_id`; assert
  `depth` values are consistent (0 for outer, 1 for inner).
- `test_sequence_geometry_boxes_tuple`: `SequenceGeometry.boxes` is a tuple of
  `BoxGeometry` in source order.

**Approach:**
- Add `BoxGeometry(box_id, label, color, participant_ids, bounds, source_order)` as a
  frozen dataclass in `_geometry.py`.
- Extend `FragmentGeometry` with `parent_fragment_id`, `start_event_index`,
  `end_event_index`, `depth`.
- Extend `SequenceGeometry` with `boxes: tuple[BoxGeometry, ...]`.
- Populate from `_all_box_groups` and the existing fragment stack in
  `_sequence_compile.py`.

---

### Task 2: Pipeline refactor — parse / compile / paint separation
Depends on: Task 1
Verification: Goal-based check

**Done when:** `parse_sequence_semantics`, `compile_sequence_geometry`,
`sequence_geometry_to_html`, `sequence_geometry_to_scene` are distinct callable functions;
`to_html` and `to_svg` both call `parse_sequence_semantics` → `compile_sequence_geometry`
before branching into their respective painters.

**Approach:**
- Extract `parse_sequence_semantics(source: str) -> SequenceModel` from the existing
  parser section of `_sequence_compile.py`.
- Extract `compile_sequence_geometry(model, width_hint, render_options) ->
  SequenceGeometry` as the geometry compiler section.
- Rename/wrap the existing HTML painter as `sequence_geometry_to_html`.
- Stub `sequence_geometry_to_scene(model, geometry, render_options) -> SvgScene` for
  wiring in Task 3.
- Update the `to_html` path to call the new pipeline in sequence.
- Keep backward-compatible re-exports in `_strategies.py` so existing callers don't break.

---

### Task 3: Retire legacy native-SVG parser
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_native_svg_sequence_uses_shared_compiler`: render `sequence-nested-fragments` via
  `to_svg`; assert `layout_backend == "sequence-geometry"` (not `"native-svg"`); assert
  fragment records are present in the output.
- `test_layout_sequence_py_deleted`: `importlib.util.find_spec(
  "scripts.mermaid_render.layout.sequence")` returns None (or `import` raises
  `ModuleNotFoundError`).
- `test_no_silent_skips`: render `sequence-box-unsupported` via `to_svg`; assert both
  boxes are present in the SVG output.

**Approach:**
- Replace `native_svg._sequence_scene` to call `parse_sequence_semantics` →
  `compile_sequence_geometry` → `sequence_geometry_to_scene`.
- Remove the delegation to `layout.sequence.layout_sequence_scene`.
- Verify no remaining imports reference `layout/sequence.py`; delete the file.
- For constructs that remain unsupported in `sequence_geometry_to_scene`, emit a
  `SequenceDiagnostic(code="unsupported_construct", ...)` rather than silently omitting.

---

### Task 4: Box painting in HTML and SVG
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_box_painted_before_lifelines`: in HTML output, the box element appears before
  the participant card elements in DOM order.
- `test_box_data_attribute_html`: HTML output for `sequence-box-unsupported` contains
  `data-box-id` for both Group A and Group B.
- `test_box_data_attribute_svg`: SVG output contains the same `data-box-id` values.
- `test_group_a_contains_alice_bob_only`: Group A bounds encompass Alice and Bob columns
  but not Carol or Dave.
- `test_group_b_contains_carol_only`: Group B bounds encompass Carol column only.
- `test_dave_outside_both_boxes`: Dave's column is outside both group bounds.
- `test_box_color_normalized`: Group A has a CSS color resolving to blue; Group B has
  `rgb(200,100,50)` retained.

**Approach:**
- In `sequence_geometry_to_html`, render each `BoxGeometry` as a `<div class="seq-box">`
  before lifeline elements. Use `bounds` directly from `BoxGeometry`.
- In `sequence_geometry_to_scene`, render each `BoxGeometry` as an SVG `<rect>` with
  `data-box-id`.
- Use a CSS color normalizer for the `color` field (accept named colors and rgb()
  expressions).

---

### Task 5: Nested fragment painting
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_outer_fragment_painted_before_inner`: in both HTML and SVG, the outer alt
  element appears before the inner loop element in render order.
- `test_inner_fragment_bounds_inside_outer`: inner loop `bounds` are fully contained by
  outer alt `bounds`.
- `test_fragment_data_attributes`: both HTML and SVG contain `data-fragment-id`,
  `data-parent-fragment-id`, `data-depth` for nested fragments.
- `test_retry_messages_inside_loop_interval`: both retry messages have event indices
  within `[loop.start_event_index, loop.end_event_index]`.
- `test_failure_message_inside_alt_outside_loop`: failure notification event index is
  within the outer alt interval but outside the loop interval.

**Approach:**
- Sort `FragmentGeometry` records by `depth` ascending before rendering (parents before
  children).
- Emit each fragment with the required `data-*` attributes from the `FragmentGeometry`
  fields.
- Place branch separators (else/elif) using `BranchGeometry.parent_fragment_id` to
  group them correctly under their owning fragment.
