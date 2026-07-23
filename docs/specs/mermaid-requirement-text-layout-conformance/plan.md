# Implementation Plan — Requirement Text Layout Conformance

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_renderer.py` (both rendering paths — main and render_finalized, per the renderer-two-paths convention); `tests/test_requirement_conformance.py` (new or extended).
2. Done when: `pytest tests/` passes; `_TEXT_WRAP_CHARS` (or equivalent) is deleted; all requirement field `TextLayout` objects have positive width and height; scaling transforms all nested text fields coherently.
3. Not changing: the `compile_requirement` public entry point signature; flowchart, state, ER, class, architecture compilers; font files.

**Declined patterns:**
- Tempted to create a second `compile_requirement_html` path; declining — the spec prohibits HTML-specific or SVG-specific layout variants.
- Tempted to use character count as a "fast path" for short strings; declining — even short strings must use the measurer to guarantee determinism and HTML/SVG identity.

---

## Tasks

### Task 1: Pixel-width wrapping for all requirement fields
Depends on: none
Verification: TDD

**Tests:**
- `test_requirement_pixel_wrap_text`: compile a requirement with a long `text` field; assert `TextLayout.lines` wraps at the pixel limit (not a character count); assert no line exceeds `max_width` pixels.
- `test_text_wrap_chars_deleted`: `grep -rn "_TEXT_WRAP_CHARS" scripts/mermaid_render/` returns zero matches.
- `test_long_unbroken_document_reference`: compile a requirement with a URL in `docRef`; assert card width expands rather than truncating the URL.

**Approach:**
- In `_renderer.py` (main rendering path), locate `_TEXT_WRAP_CHARS` and all fixed-character-count wrapping calls.
- Replace with `_MEASURER.layout(value, REQUIREMENT_FIELD, max_width=card_max_width, wrap=True)`.
- Delete `_TEXT_WRAP_CHARS` constant.
- For long unbroken tokens: set `wrap=True` with `allow_break_anywhere=True` as fallback if `max_width` is exceeded and no natural break point exists.
- Also apply the same fix in the `render_finalized` path (the second rendering path).

---

### Task 2: Real `TextLayout` for every field
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_all_ten_fields_measured`: compile `requirement-basic`; for each of the ten field types (requirement name, subtype, ID, text, risk, verification method, element name, element type, document reference, relation label), assert `TextLayout.width > 0 and TextLayout.height > 0`.
- `test_no_stub_text_layouts`: compile `requirement-basic`; assert no field's `TextLayout` has `lines == []` or `width == 0`.

**Approach:**
- For each of the ten requirement field types, create a real `TextLayout` using `_MEASURER.layout(field_value, REQUIREMENT_FIELD)`.
- Store the `TextLayout` on the field's layout record and pass it to both HTML and SVG painters.
- Fix both rendering paths to use the real `TextLayout` for text placement (not an independently computed coordinate).

---

### Task 3: Card sizing from measured fields
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_card_width_from_longest_field`: compile two requirements where one has a much longer name; assert the longer-name card is wider.
- `test_card_height_from_field_count`: compile requirements with different numbers of attributes; assert taller cards for more attributes.
- `test_width_hint_affects_card_positions`: compile the same diagram with `width_hint=400` and `width_hint=800`; assert card positions differ.

**Approach:**
- In `compile_requirement`, compute card width as `max(field_widths) + left_margin + right_margin`.
- Compute card height as `sum(field_heights) + top_margin + bottom_margin`.
- Respect `width_hint` and `height_hint` as layout constraints affecting the overall canvas, not just the bounds.

---

### Task 4: Scaling coherence
Depends on: Tasks 2, 3
Verification: TDD

**Tests:**
- `test_scaling_transforms_text_layout`: apply 2× scale post-compilation; assert `TextLayout.font_size`, `TextLayout.line_height`, `TextLayout.width`, `TextLayout.bounds` are all doubled.
- `test_scaling_transforms_member_rows`: assert member row bounds are scaled by the same factor.
- `test_partial_scaling_detected`: construct a `FinalizedLayout` where text bounds are at scale 1.0 but node bounds are at scale 2.0; assert the validator raises.

**Approach:**
- Prefer compiling at the target scale. If post-compilation scaling is still necessary, implement `scale_requirement_layout(layout, factor) -> FinalizedLayout` that scales all fields listed in the spec.
- Add `validate_requirement_scaling_coherence(layout) -> list[ScalingViolation]` that checks all text and node bounds are at the same effective scale (ratio test within tolerance).

---

### Task 5: Route non-penetration
Depends on: Tasks 3, 4
Verification: TDD

**Tests:**
- `test_relation_routes_do_not_enter_cards`: compile `requirement-basic`; for each relation route, assert all waypoints are outside all requirement card interiors.
- `test_relation_source_and_target_correct`: compile `requirement-basic`; assert each of the three relations has the correct source and target card IDs.

**Approach:**
- Add a route-obstacle check to the requirement layout (or reuse the geometry verifier from `mermaid-flowchart-conformance`).
- Assert no waypoint falls inside any requirement card's bounding rectangle.

---

### Task 6: HTML/SVG identity, oracle comparison, and grammar strictness
Depends on: Tasks 1–5
Verification: TDD

**Tests:**
- `test_html_svg_same_geometry`: compile `requirement-basic`; assert HTML and SVG painters receive identical `FinalizedLayout` instances.
- `test_oracle_nonzero_checks`: run `OracleCheck` comparison on `requirement-basic`; assert `len(result.checks) > 0` and `result.status != OracleStatus.UNVALIDATED`.
- `test_invalid_syntax_raises`: supply invalid requirement syntax; assert `ParseError` or equivalent is raised, not a silently repaired diagram.

**Approach:**
- Ensure `compile_requirement` returns a single `FinalizedLayout` consumed by both painters.
- Invoke the oracle comparator from `oracle_contract.py` on `requirement-basic`; verify it produces at least one check (AC7).
- In the requirement parser, add grammar validation that raises on unrecognized tokens rather than silently producing a partial diagram.
