# C4 Layout Engine — Plan

## Task 1: Create `_c4.py` module
**Mode: TDD (C4Bounds) + goal-based (rendering)**
**Depends on: none**

Tests (construction):
- `C4Bounds` pixel-exact coordinates: start_x=100, start_y=66, width_limit=832,
  three boxes → (150,166), (466,166), (150,400).
- Row wrapping independence: 5 boxes at shapes_per_row=4 → first 4 on row 1,
  fifth on row 2.

Approach:
- Data models: `C4Item` (alias, kind, label, description, is_external, boundary)
  and `C4Box` (alias, width, height, x, y).
- Constants: `C4_NODE_W=216`, `C4_PERSON_H=134`, `C4_SYSTEM_H=86` (Mermaid 11.15
  defaults — hardcoded, not measured at runtime).
- `C4Bounds` class — direct port of Mermaid 11.15 `Bounds.insert()` with MIT notice.
- Layout origin: `start_x = 2 * C4_SHAPE_MARGIN = 100`, `start_y = C4_TITLE_H = 66`
  when title is present (matches the reference fixture geometry), `start_y = 0`
  when no title. `layout_width = 832` always (Mermaid default, independent of
  `width_hint`).
- `_render_c4_fragment(title, items, relationships, width_hint)`:
  1. Build `C4Box` per item with appropriate height.
  2. Run `C4Bounds.insert()` for each box.
  3. `canvas_w = max_right + C4_SHAPE_MARGIN`, `canvas_h = max_bottom + C4_SHAPE_MARGIN`.
  4. `zoom = min(1.0, width_hint / canvas_w)` — scale for display, not for packing.
  5. Render outer div with zoom + nodes + SVG edge overlay.
- Node HTML: `<div class="node c4-node c4-{kind}" data-node-id="{alias}" style="
  position:absolute; left:{x}px; top:{y}px; width:{w}px; height:{h}px; ...">`.
  Internal: standard card border `border:1.5px solid var(--node-border,...);
  border-top:3px solid {accent}`. External (`is_external=True`): solid gray fill
  `background:#999; border:1px solid #8a8a8a; color:#fff`.
- Stereotype rendered as `[Person]` / `[Software System]` etc. (house style,
  preserves `test_type_tag_rendered`).
- Edge rendering: first relationship → straight line; subsequent → quadratic Bézier.
  Rectangle-boundary intersection uses center-ray geometry.
- `C4Boundary` and `C4Relationship` dataclasses in same file.
- Title div at `position:absolute; left:0; top:0; width:100%` with C4_TITLE_H space.

Done when: `C4Bounds` assertion from spec passes (unit test); `_render_c4_fragment`
produces valid HTML with correct data-node-id positions.

---

## Task 2: Modify `_layout_c4` in `_strategies.py`
**Mode: Goal-based**
**Depends on: Task 1**

Approach:
- Add `title` parsing at top of parse loop (`line.lower().startswith("title ")`).
- Build `items: list[C4Item]` in declaration order (not dict-only).
- Remove `shape="circle"` for persons; all C4 items are rect (C4Item.is_external).
- Remove `css_class="external"` assignment; C4Item carries `is_external`.
- Replace `return _graph_from_content_nodes(...)` with
  `return _render_c4_fragment(title, items, relationships, groups, width_hint)`.
- Import `_render_c4_fragment`, `C4Item`, `C4Relationship` from `._c4`.

Done when: `_dispatch(c4_basic_src, None, 800)` returns HTML with
`data-node-id="user"` at `left:150px; top:166px`.

---

## Task 3: Update tests
**Mode: Goal-based**
**Depends on: Task 2**

Tests to update:
- `test_render_correctness.py:450-457` `test_person_has_circle_shape` → rename to
  `test_person_shape_is_rect`, assert `node-circle` NOT present and `node-c4-person`
  IS present.
- `test_mermaid_layout.py:668-681` `test_c4_ext_elements_get_external_class` →
  change assertion from `border:1.5px dashed` to `background:#999` (external fill).
  Assert `border:1.5px solid` still present (internal elements).
- `test_mermaid_layout.py:2168-2180` `test_c4_bigbank_external_border` → same.

New tests:
- `TestC4LayoutCoordinates` in `test_mermaid_layout.py`:
  - `test_c4_basic_packing_coordinates` — dispatch c4-basic at width_hint=800,
    parse HTML for user/webapp/email positions.
  - `test_c4_narrow_width_no_per_row_wrap` — dispatch at width_hint=200,
    assert user and webapp still on same row (user.y == webapp.y).
  - `test_c4_title_rendered` — assert "System Context" in HTML.
  - `test_c4_external_solid_fill` — assert `background:#999` in HTML for email.
  - `test_c4_relationships_do_not_move_nodes` — dispatch with and without Rel lines,
    assert user/webapp/email positions unchanged.

Done when: `pytest tests/ -x -q` passes.

---

## Declined patterns

- Adding `height: int` field to `_Node` — C4Box handles height independently; no
  shared model coupling needed.
- Routing C4 rendering through `_renderer.py` — `_c4.py` is fully self-contained.
- Nested C4 boundary visual boxes — acceptance criteria only test flat diagrams;
  boundaries are parsed (for member tracking) but not rendered as visual containers.
- Making `C4_LAYOUT_WIDTH`, `C4_SHAPE_MARGIN` configurable — Mermaid 11.15 has
  fixed defaults; no second caller needs to differ.
- Changing stereotype format from `[Person]` to `<<person>>` — house style;
  preserves `test_type_tag_rendered`.
