# Implementation Plan — Mermaid Text Measurement Adoption

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_text.py` (add `TextStyle` constants); `scripts/mermaid_render/layout/_strategies.py` (flowchart group sizing); `scripts/mermaid_render/layout/architecture.py` (service/group labels); `scripts/mermaid_render/layout/er.py` (entity card sizing); `scripts/mermaid_render/layout/_renderer.py` (requirement wrapping, both rendering paths per the two-paths memory); `tests/` (new measurement tests).
2. Done when: `pytest tests/` passes; `grep -rn "len(.*) \* [0-9]" scripts/mermaid_render/layout/` returns zero matches for layout-width computations; every visible label in each in-scope diagram has a non-stub `TextLayout`.
3. Not changing: the `TextMeasurer` implementation itself; font files; sequence diagram layout; route geometry.

**Declined patterns:**
- Tempted to add a fallback to character-count when `TextMeasurer` is unavailable; declining — the measurer is already a required dependency; adding a fallback re-introduces the problem this spec solves.
- Tempted to replace all text calls in one pass; declining — each category has distinct style constants and must be migrated independently to keep diffs reviewable.
- Tempted to abstract a new `TextService` wrapper class; declining — the existing `_MEASURER` singleton is sufficient; no new abstraction layer.

---

## Tasks

### Task 1: Define `TextStyle` constants
Depends on: none
Verification: TDD

**Tests:**
- `test_text_style_constants_exist`: assert each of the nine named styles exists in `_text.py` as a `TextStyle` instance.
- `test_text_style_non_zero_font_size`: assert every `TextStyle` has `font_size > 0`.

**Approach:**
- Add to `scripts/mermaid_render/layout/_text.py` nine `TextStyle` constants:
  `NODE_LABEL`, `GROUP_LABEL`, `EDGE_LABEL`, `ARCH_SERVICE_LABEL`, `CLASS_NAME`,
  `ER_ENTITY_HEADER`, `ER_CELL`, `REQUIREMENT_FIELD`, `STATE_LABEL`.
- Use existing `TextStyle` dataclass fields; derive values from current hard-coded
  constants where they exist.

---

### Task 2: Flowchart group title measurement
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_group_width_not_len_coefficient`: compile two flowchart groups with labels of different lengths using the real `TextMeasurer`; assert the wider label produces a wider group.
- `test_group_label_has_real_text_layout`: compile a flowchart with a group; assert the group's label `TextLayout` has positive `width` and `height` (not a stub zero-area layout).

**Approach:**
- In `_strategies.py` or the flowchart compiler, locate `len(g.label) * 8` (or equivalent) used to size group label width.
- Replace with `_MEASURER.layout(g.label, GROUP_LABEL, max_width=MAX_GROUP_WIDTH)`.
- Store the resulting `TextLayout` on the `LayoutGroup` or pass it into the group construction call.

---

### Task 3: Architecture service and group label measurement
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_arch_service_label_has_real_text_layout`: compile an architecture diagram; for each service node, assert the label `TextLayout` has positive `width` and `height`.
- `test_arch_group_min_width_from_measurement`: compile two architecture groups with different label lengths using the real `TextMeasurer`; assert the wider-label group has a greater minimum width.

**Approach:**
- In `architecture.py`, locate `_arch_text_layout` and any group-width estimate using character counts.
- Replace with `_MEASURER.layout(label, ARCH_SERVICE_LABEL, ...)` for service labels and `_MEASURER.layout(label, GROUP_LABEL, ...)` for group labels.
- Use the resulting `TextLayout.width` as the group minimum width.

---

### Task 4: ER entity card measurement
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_er_card_width_from_attribute_name`: compile an ER entity with a 3-character attribute name and one with a 30-character attribute name; assert the wider name produces a wider card.
- `test_er_header_measured`: compile an ER entity; assert the entity header has a non-stub `TextLayout` with positive width and height.

**Approach:**
- In `er.py`, locate entity width calculation using character-count approximation.
- For each entity, measure: header text, each attribute's key badge, type string, and name string using `_MEASURER.layout(..., ER_ENTITY_HEADER or ER_CELL)`.
- Set entity card width to `max(measured_header_width, max(measured_column_widths) + padding)`.
- Set row heights from measured line heights.

---

### Task 5: Requirement field measurement and pixel wrapping
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_requirement_pixel_wrap`: compile a requirement with a text field exceeding 200 pixels; assert the resulting `TextLayout.lines` has more than one line without using a character count.
- `test_requirement_all_fields_measured`: compile `requirement-basic`; for each of the ten field types (requirement name, subtype, ID, text, risk, verification method, element name, element type, document reference, relation label), assert `TextLayout.width > 0 and TextLayout.height > 0`.
- `test_text_wrap_chars_deleted`: `grep -n "_TEXT_WRAP_CHARS" scripts/mermaid_render/layout/` returns zero matches.

**Approach:**
- In `_renderer.py` (both rendering paths — main and render_finalized, per the renderer-two-paths convention), locate `_TEXT_WRAP_CHARS` and all fixed character-count wrapping calls.
- Replace with `_MEASURER.layout(field_value, REQUIREMENT_FIELD, max_width=card_max_width, wrap=True)`.
- Delete `_TEXT_WRAP_CHARS` constant.
- Create real `TextLayout` from the measured result for each field.

---

### Task 6: Cache and scaling coherence
Depends on: Tasks 2, 3, 4, 5
Verification: TDD

**Tests:**
- `test_measurement_cache_determinism`: call `_MEASURER.layout` twice with identical arguments; assert equal results.
- `test_scaling_transforms_text_layout`: apply a 2× scale to a `FinalizedLayout`; assert `TextLayout.line_height`, `TextLayout.width`, and `TextLayout.bounds` are all doubled.
- `test_font_identity_in_metadata`: compile any fixture; assert the resulting layout metadata contains a font identity field (family name + file fingerprint); assert the field is non-empty (AC7).

**Approach:**
- Verify the existing `TextMeasurer` cache uses the complete key (text, family, fingerprint, size, weight, style, letter_spacing, max_width, wrap_mode).
- Ensure that when scaling is applied post-compilation, all `TextLayout` fields are included in the scale transform (not only bounds).
- Add a `scale_text_layout(tl: TextLayout, factor: float) -> TextLayout` helper if one doesn't exist.

---

### Task 7: HTML/SVG identity assertion tests
Depends on: Tasks 2, 3, 4, 5
Verification: TDD

**Tests:**
- `test_flowchart_html_svg_same_label_bounds`: compile a flowchart; for each node label, assert the HTML painter and SVG painter receive a `TextLayout` with the same `bounds`.
- `test_er_html_svg_same_card_geometry`: compile an ER diagram; assert HTML and SVG receive the same entity card `FinalizedLayout`.
- `test_requirement_html_svg_same_field_layouts`: compile `requirement-basic`; assert HTML and SVG receive the same field `TextLayout` objects.

**Approach:**
- Add a thin test fixture that captures `TextLayout` objects passed to HTML and SVG painters.
- For each diagram type, compile the diagram and assert the captured layouts are equal.
