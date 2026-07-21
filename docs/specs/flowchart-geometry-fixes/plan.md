# Flowchart Geometry Fixes — plan

## Task 1: Text measurement bug fix
Mode: TDD
Depends on: none

**Tests:**
```python
def test_long_token_wrap_uses_title_font_constants():
    # Line at _constants.py:351 used hard-coded 13/500; should use _TITLE_FS/_TITLE_FW
    ...
def test_long_token_each_line_fits_budget():
    ...
```

**Approach:** Replace `_measure_text_width(w[:split_i+1], 13, 500)` with `_measure_text_width(w[:split_i+1], _TITLE_FS, _TITLE_FW)` at `_constants.py:351`.

**Done when:** test_long_token_wrap_uses_title_font_constants passes; existing wrap tests green.

---

## Task 2: Shape sizing — diamond separate formula
Mode: TDD
Depends on: Task 1

**Tests:**
```python
def test_diamond_size_single_line():
    ...
def test_diamond_size_three_lines_grows():
    ...
def test_diamond_size_cjk_wider():
    ...
```

**Approach:** Add `_node_size_diamond(n)` to `_constants.py` using `ceil(content_w + content_h + NODE_HPAD + _NODE_PAD_V//2)`. Update `_layout.py:261` to call `_node_size_diamond(n)`.

**Done when:** diamond node width from `_node_size_diamond` differs from hexagon width for same label.

---

## Task 3: Shape sizing — hexagon independent w/h
Mode: TDD
Depends on: Task 2

**Tests:**
```python
def test_hexagon_width_height_independent():
    ...
def test_hexagon_tall_label_increases_height_not_width():
    ...
def test_node_render_h_hexagon_returns_height():
    ...
```

**Approach:** Add `_node_size_hexagon(n) -> tuple[int, int]` returning `(width, height)`. In `_layout.py:263-264`, set both `n.width` and `n.height`. Update `_node_render_h` to return `n.height` for hexagon (already reads `n.width`; change to `n.height`).

**Done when:** hexagon with multi-line label has `n.height != n.width`.

---

## Task 4: Shape sizing — circle multiline
Mode: TDD
Depends on: Task 3

**Tests:**
```python
def test_circle_multiline_larger_than_single():
    ...
def test_doublecircle_adds_ring_clearance():
    ...
```

**Approach:** Update `_node_size_circle(n)` to measure `max(measure(line) for line in lines)` and `content_h = len(lines) * _TITLE_LINE_H`. For doublecircle, add ring clearance (8px on each side).

**Done when:** circle with 3-line label has wider diameter than same node with 1 line.

---

## Task 5: Geometry IR
Mode: TDD
Depends on: none

**Tests:**
```python
def test_rect_contains():
    ...
def test_rect_overlaps():
    ...
def test_rect_union():
    ...
def test_rect_translate():
    ...
def test_finalized_layout_construction():
    ...
```

**Approach:** Create `scripts/mermaid_render/layout/_geometry.py` with frozen `Rect`, `GroupLayout`, `RoutedEdge`, `FinalizedLayout`.

**Done when:** all Rect helper tests pass.

---

## Task 6: Nested group y-shift
Mode: TDD
Depends on: none (reads existing `_compute_group_bboxes`)

**Tests:**
```python
def test_deep_nesting_group_titles_no_overlap():
    ...
def test_deep_nesting_all_groups_above_zero():
    ...
def test_deep_nesting_canvas_contains_groups():
    ...
```

**Approach:** In `_renderer.py::_compute_group_bboxes`, after the existing x-shift pass (lines 1279-1290), add an analogous y-shift pass: if `min(b[1] for b in bboxes.values()) < 0`, shift nodes and bboxes down. Then expand canvas_h to include `max(b[3] for b in bboxes.values()) + CANVAS_PAD`.

**Done when:** `_render_graph_fragment` on deep-nesting fixture produces bboxes with `y >= 0`.

---

## Task 7: Canvas bounds include groups
Mode: TDD
Depends on: Task 6

**Tests:**
```python
def test_canvas_width_includes_group_right_edge():
    ...
def test_canvas_height_includes_group_bottom_edge():
    ...
```

**Approach:** In `_render_graph_fragment` (or its caller in `_strategies.py`), after computing group bboxes, expand `canvas_w` and `canvas_h` to include `max(b[2])` and `max(b[3])` plus `CANVAS_PAD`. Also update `_separate_groups_tb` to account for actual node widths (not global `NODE_W`).

**Done when:** canvas width/height >= all group bbox extents.

---

## Task 8: Direction-aware self-loops
Mode: TDD
Depends on: none

**Tests:**
```python
def test_self_loop_tb_exits_right_side():
    ...
def test_self_loop_lr_exits_top_or_bottom():
    ...
def test_four_self_loops_tb_alternate_sides():
    ...
def test_self_loop_label_extent_grows_with_label():
    ...
```

**Approach:** In `_routing.py`, replace the fixed self-loop code (lines 614-638) with direction-aware routing:
- Track `loop_counts: dict[str, int]` per node.
- For TB/TD: `side_order = ("right", "left")`.
- For LR/RL: `side_order = ("top", "bottom")`.
- `side = side_order[loop_index % 2]`, `lane = loop_index // 2`.
- `extent = max(BASE_LOOP_EXTENT, label_width + 2*LABEL_PAD, 0.35 * max(nw, nh)) + lane * LOOP_LANE_GAP`.

**Done when:** LR diagram with a self-loop produces path that exits top or bottom, not right.

---

## Task 9: A* group title obstacles for routing
Mode: TDD
Depends on: none

**Tests:**
```python
def test_astar_avoids_group_title_strip():
    ...
```

**Approach:** In `_routing.py::_route_edges`, pass group title strip bboxes to `_blocked_segs` (in addition to node bodies) when building `_blocked`. Currently `_routing_obs` (line 486-487) only includes nodes.

**Done when:** route between two nodes with a group title strip in the direct path avoids the strip.

---

## Task 10: Edge label collision filtering
Mode: TDD
Depends on: none

**Tests:**
```python
def test_label_placement_avoids_unrelated_node():
    ...
def test_label_placement_uses_best_clear_candidate():
    ...
```

**Approach:** `_best_label_pos` already scores against obstacles, which include node bboxes. The issue is the candidate generation in `_label_on_longest` is limited (5 candidates). Expand to 9 candidates (3 x positions × 3 y offsets). Assert that when a direct-midpoint position overlaps a node, an alternate is chosen.

**Done when:** placing a label whose midpoint would land on a node body produces a chip with zero overlap area vs that node.

---

## Task 11: RenderOptions dataclass
Mode: TDD
Depends on: none

**Tests:**
```python
def test_render_options_defaults():
    ...
def test_faithful_mermaid_preserves_direction():
    ...
def test_faithful_mermaid_no_icons():
    ...
def test_faithful_mermaid_no_legend():
    ...
```

**Approach:** Add `@dataclass(frozen=True) class RenderOptions` to `_strategies.py` with fields `faithful_mermaid=False, infer_icons=True, auto_direction=True, inferred_legend=True`. Thread through `_layout_graph_topology` and `_dispatch`. Guard icon inference, direction auto-select, and legend injection with the flags.

**Done when:** `_dispatch(src, None, 400, opts=RenderOptions(faithful_mermaid=True))` produces no inferred icons/legend; declared direction preserved.

---

## Task 12: CSS box-model fixes
Mode: TDD
Depends on: none

**Tests:**
```python
def test_subroutine_svg_uses_node_width():
    ...
def test_cylinder_svg_uses_node_width():
    ...
def test_shape_background_border_radius_inherit():
    ...
```

**Approach:** In `_renderer.py`:
- SVG overlays for subroutine and cylinder: use `n.width`/`node_h` rather than hard-coded values.
- Add `border-radius:inherit;` to the `.node-shape-background` layer where it's inline-styled.

**Done when:** rendered HTML for a cylinder node has `width="{n.width}"` in its SVG overlay, not `width="42"` or other fixed value.

---

## Task 13: Gallery three-state badges
Mode: TDD
Depends on: none

**Tests:**
```python
def test_classify_status_error():
    ...
def test_classify_status_invalid():
    ...
def test_classify_status_warning():
    ...
def test_classify_status_ok():
    ...
```

**Approach:** In `scripts/compare_gallery.py`, add `_classify_status(render_exception, geometry_errors, geometry_warnings) -> str` function returning `"error"|"invalid"|"warning"|"ok"`. Add `tests/validate_compare_gallery.py` with geometry check helpers.

**Done when:** `_classify_status(None, True, False)` returns `"invalid"`, `_classify_status(None, False, True)` returns `"warning"`, etc.
