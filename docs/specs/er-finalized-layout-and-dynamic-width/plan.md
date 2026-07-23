# Implementation Plan — er-finalized-layout-and-dynamic-width

## Pre-mortem

**Assumption trio:**

1. Files I'll touch:
   - `scripts/mermaid_render/layout/er.py` — width measurement, `LayoutGraph`
     compilation, ELK/Sugiyama dispatch, `FinalizedLayout` consumption, cardinality
     mark rendering from port tangent, label placement on longest segment.
   - `scripts/mermaid_render/layout/_strategies.py` — `_layout_er()` HTML renderer
     replaced with `FinalizedLayout`-driven pass; old coordinate loop removed.
   - `tests/test_er_finalized_layout.py` — new test file (Tasks 1, 2, 5, 6 each
     add their own test class).
   - `tests/test_fix_er.py` — `TestCardNonOverlap.test_er_native_scene_non_overlapping`
     may need updating if the `SceneRect` tagging contract changes.

2. Done when: `pytest tests/` passes with zero failures; `er-cardinality-all` and
   `er-ecommerce` HTML and SVG outputs are coordinate-identical within 1 px;
   `validate_finalized_layout()` reports no errors on both fixtures.

3. Not changing: `_layout.py`, `_layered.py`, `elk_adapter.py`, `_geometry.py`
   (read-only consumers only), all other diagram type renderers, color token
   constants, `CardinalityEnd` / `Minimum` / `Maximum` model, `parse_er_cardinality`.

**Declined patterns:**

- Tempted to wire ER through `_compile_flowchart()` directly — declining; that
  function owns flowchart/state/class parsing and its parse path is not ER-aware.
  ER gets its own `compile_er_layout()` that reuses the same ELK adapter and
  Sugiyama helpers.
- Tempted to merge `er.py` into `_strategies.py` — declining; the two files have
  different abstraction levels (scene IR vs HTML string) and merging would bloat
  `_strategies.py` further.
- Tempted to make `FinalizedLayout` carry a `cardinality_ends` side-channel dict —
  declining; encode cardinality as `MarkerKind` on `LayoutEdge.source_marker` /
  `target_marker` so the layout engine owns the full edge semantic.
- Tempted to add an orthogonal connector HTML path separate from the SVG overlay —
  declining; both HTML and SVG use the single `FinalizedLayout.routed_edges`
  waypoints, rendered as an inline `<svg>` overlay on the HTML side.

---

## Tasks

### Task 1: Dynamic card width measurement
Depends on: none
Verification: TDD

**Tests** (`tests/test_er_finalized_layout.py::TestCardWidthMeasurement`):
- `test_min_width_no_attrs` — entity with zero attributes returns at least
  `_ER_MIN_CARD_W`.
- `test_max_width_clamp` — entity with very long name and many long-typed attributes
  never exceeds `_ER_MAX_CARD_W`.
- `test_badge_column_included` — entity with a PK attribute produces a wider card
  than the same entity with no constraint (badge column = 22 px).
- `test_no_badge_no_extra_column` — entity with no constraint attributes does not
  allocate the badge column.
- `test_measured_width_covers_type_and_name` — for a known attribute `("varchar",
  "email_address")`, the returned width is >= badge_col + type_px + name_px + padding.

**Approach:**
- Add `_ER_MIN_CARD_W: int = 160` and `_ER_MAX_CARD_W: int = 320` constants to `er.py`.
- Add `_measure_card_width(entity_name: str, attrs: list[dict]) -> float` in `er.py`.
  - Compute `header_w` = approximate text width of entity name at 13 px bold (use
    `len(entity_name) * 7.8 + 16` as a char-width estimate; exact measurement
    deferred to the font-metrics subsystem once available).
  - Compute `has_badge = any(a["constraint"] in ("PK", "FK", "UK") for a in attrs)`.
  - Compute `badge_col = 22` if `has_badge` else `0`.
  - Compute `type_col = max((len(a["type"]) * 6.5 for a in attrs), default=0) + 4`.
  - Compute `name_col = max((len(a["name"]) * 7.0 for a in attrs), default=0) + 4`.
  - `row_padding = 16` (8 px each side).
  - Return `max(_ER_MIN_CARD_W, min(_ER_MAX_CARD_W, max(header_w, badge_col + type_col + name_col + row_padding)))`.
- Replace `_CARD_W = 200` usages in `er.py` with per-entity measured width stored
  in a `widths: dict[str, float]` keyed by entity id.

---

### Task 2: LayoutGraph compilation for ER
Depends on: Task 1
Verification: TDD

**Tests** (`tests/test_er_finalized_layout.py::TestLayoutGraphCompilation`):
- `test_node_count_matches_entities` — two-entity diagram produces a `LayoutGraph`
  with exactly two `LayoutNode`s, each with `measured_width` equal to the Task 1
  measurement result.
- `test_edge_source_marker_one_many` — `||--|{` produces `source_marker=CROW_ONE`,
  `target_marker=CROW_MANY`.
- `test_edge_source_marker_zero_one` — `|o--||` produces `source_marker=CROW_ZERO_ONE`,
  `target_marker=CROW_ONE`.
- `test_dotted_relationship_line_style` — `..` separator produces
  `LayoutEdge.line_style == "dotted"`.
- `test_parallel_edges_get_distinct_ports` — two relationships between the same
  pair of entities produce `LayoutEdge`s with distinct `source_port` ids.

**Approach:**
- Add `_cardinality_to_marker(end: CardinalityEnd) -> MarkerKind` in `er.py`:
  - `(ONE, ONE)` → `CROW_ONE`; `(ZERO, ONE)` → `CROW_ZERO_ONE`;
  - `(ONE, MANY)` → `CROW_MANY`; `(ZERO, MANY)` → `CROW_ZERO_MANY`.
- Add `_compile_er_layout_graph(entities, relationships, widths, heights) -> LayoutGraph`
  in `er.py`:
  - Create one `LayoutNode` per entity with `measured_width=widths[eid]`,
    `measured_height=heights[eid]`, `shape_id="er_entity"`.
  - For parallel edges (same `from`/`to` pair), allocate a named `PortSpec` per
    edge on each face; use `port_id = f"{from}_{to}_{idx}"`.
  - Create one `LayoutEdge` per relationship: `source_marker` and `target_marker`
    from `_cardinality_to_marker`, `line_style` from dotted flag,
    `label=rel["label"]`.
  - Return `LayoutGraph(nodes=..., groups=(), edges=..., direction="TB")`.

---

### Task 3: ELK / Sugiyama dispatch to FinalizedLayout
Depends on: Task 2
Verification: TDD (integration level — runs ELK when available, Sugiyama otherwise)

**Tests** (`tests/test_er_finalized_layout.py::TestFinalizedLayoutPipeline`):
- `test_returns_finalized_layout` — `compile_er_layout(src)` returns a
  `FinalizedLayout` instance.
- `test_node_count_correct` — `len(result.node_layouts)` equals entity count.
- `test_no_routing_failures` — `result.routing_failures == ()` for both fixtures.
- `test_validate_passes` — `result.validate()` returns `ValidationResult` with
  `errors == ()`.
- `test_non_overlap_cardinality_all` — all pairs of `outer_bounds` in
  `result.node_layouts` have zero intersection area (AC1).
- `test_non_overlap_ecommerce` — same check on `er-ecommerce`.

**Approach:**
- Add `compile_er_layout(src: str, *, width_hint: int = 0) -> FinalizedLayout`
  in `er.py`:
  1. Parse entities and relationships via `_parse_er_source`.
  2. Measure widths (`_measure_card_width`) and heights (`_card_height`) per entity.
  3. Build `LayoutGraph` via `_compile_er_layout_graph`.
  4. Try ELK: `from .elk_adapter import layout_with_elk; result = layout_with_elk(lg)`.
     On `ElkUnavailable` or any exception, fall through.
  5. Fallback: run `_break_cycles`, `_assign_ranks`, `_minimize_crossings`,
     `_assign_coordinates` on a temporary `_Node`/`_Edge` dict built from
     `LayoutGraph`; construct `FinalizedLayout` from the resulting positions using
     straight-line routing (boundary-clipped, same as current `er.py`).
  6. Apply `width_hint` as a uniform scale: if `canvas_bounds.w > width_hint > 0`,
     compute `zoom = width_hint / canvas_bounds.w`; scale `visible_bounds`,
     `canvas_bounds`, all `NodeLayout.outer_bounds`, all `RoutedEdge.waypoints`,
     and all `PortLayout.position` by `zoom` (direction vectors are unchanged).
  7. Return `FinalizedLayout`.
- Export `compile_er_layout` from `er.py`'s public API.

---

### Task 4: Cardinality mark rendering from FinalizedLayout port tangent
Depends on: Task 3
Verification: TDD

**Tests** (`tests/test_er_finalized_layout.py::TestCardinalityMarkRendering`):
- `test_glyph_tangent_from_port_direction` — for a known `PortLayout` with
  `direction=Point(1.0, 0.0)`, `_er_glyph_elements` called with `(dx=1, dy=0)`
  emits horizontal bar/foot elements (x-coordinates differ, y-coordinates equal).
- `test_glyph_reserve_consistent` — `_glyph_reserve(end)` for all four `CardinalityEnd`
  values matches the values returned by the same function before this task (no
  regression in reserve distances).
- `test_cardinality_all_all_glyphs_present` — rendering `er-cardinality-all` via
  `compile_er_layout()` produces eight `CardinalityEnd` entries (one per entity side)
  each with correct `minimum`/`maximum` values read from `RoutedEdge`
  `source_marker`/`target_marker`.

**Approach:**
- Add `_marker_to_cardinality(mk: MarkerKind) -> CardinalityEnd` inverse of
  `_cardinality_to_marker` (needed to drive `_er_glyph_elements`).
- In the SVG rendering pass (both `layout_er_scene` updated path and the SVG overlay
  in `_layout_er`):
  - For each `RoutedEdge`, take `src_port.direction` and `dst_port.direction`.
  - Call `_er_glyph_elements(src_port.position.x, src_port.position.y, dx, dy, end, ...)`
    with `(dx, dy) = (src_port.direction.x, src_port.direction.y)`.
  - Do not recompute centre-to-centre direction vectors.

---

### Task 5: Label placement on longest clear route segment
Depends on: Task 3
Verification: TDD

**Tests** (`tests/test_er_finalized_layout.py::TestLabelPlacement`):
- `test_label_on_longest_segment` — for a three-waypoint route
  `[(0,0), (0,100), (200,100)]`, the longest segment is `(0,100)-(200,100)` (len 200);
  label anchor is its midpoint `(100, 100)`.
- `test_label_not_inside_entity_card` — after rendering `er-ecommerce`, every
  relationship label `EdgeLabelLayout.bounds` has zero intersection area with every
  `NodeLayout.outer_bounds`.
- `test_label_omitted_when_empty` — relationship with empty label string produces
  `label_layout=None` on the `RoutedEdge`.

**Approach:**
- Add `_longest_segment_midpoint(waypoints: Sequence[Point]) -> Point`:
  - Iterate adjacent pairs; return midpoint of the pair with maximum Euclidean
    distance. Falls back to midpoint of first and last point for < 2 waypoints.
- In the label rendering pass, call `_longest_segment_midpoint` on
  `RoutedEdge.waypoints` to get the anchor point.
- Treat cardinality glyph bounds (inflated `PortLayout.position` ± `_glyph_reserve`)
  and adjacent entity bounding boxes as obstacles; if the anchor point falls inside
  an obstacle, walk the remaining segments in descending order of length until a
  clear midpoint is found.
- This replaces the current `(lx1 + lx2) / 2.0` midpoint used in both `er.py` and
  `_strategies.py`.

---

### Task 6: FinalizedLayout-driven HTML renderer in _strategies.py
Depends on: Task 3, Task 4, Task 5
Verification: TDD

**Tests** (`tests/test_er_finalized_layout.py::TestHtmlSvgCoordinateParity`):
- `test_entity_positions_match` — for both target fixtures, parse left/top from
  HTML entity divs and compare to `FinalizedLayout.node_layouts[eid].outer_bounds`
  within 1 px.
- `test_edge_waypoints_match` — for each relationship, the SVG `<line>` endpoint
  pair in the HTML output matches `RoutedEdge.waypoints[0]` and `waypoints[-1]`
  within 1 px.
- `test_width_hint_zoom_applied` — at `width_hint=600` on `er-ecommerce`, the
  outer div's `width` CSS value equals the scaled `canvas_bounds.w` (within 1 px).
- `test_identifying_solid_line` — solid relationship (`er-identifying.mmd`) has no
  `stroke-dasharray` on data-edge `<line>` elements.
- `test_non_identifying_dashed_line` — `..` separator produces
  `stroke-dasharray="6 4"` on edge `<line>` elements.

**Approach:**
- In `_strategies.py::_layout_er()`:
  1. Call `from .er import compile_er_layout; fl = compile_er_layout(src, width_hint=width_hint)`.
  2. Build entity card HTML from `fl.node_layouts`:
     - `left = int(nl.outer_bounds.x)`, `top = int(nl.outer_bounds.y)`,
       `width = int(nl.outer_bounds.w)`, `height = int(nl.outer_bounds.h)`.
     - Attribute rows, badges, comments unchanged from existing HTML template.
  3. Build SVG overlay from `fl.routed_edges`:
     - Emit `<line>` segments connecting consecutive `RoutedEdge.waypoints`.
     - Drive `stroke-dasharray` from `RoutedEdge.edge_style == "dotted"`.
     - Drive cardinality glyphs from `src_port` / `dst_port` via Task 4 helpers.
     - Drive labels from `RoutedEdge.label_layout.anchor_point` (Task 5).
  4. Set outer div `width = int(fl.canvas_bounds.w)`, `height = int(fl.canvas_bounds.h)`.
  5. Remove the old independent Sugiyama coordinate loop from `_layout_er`.
- Update `layout_er_scene()` in `er.py` to also consume `compile_er_layout()` and
  map `FinalizedLayout` → `SvgScene` (replacing the existing direct `SvgScene`
  construction). Entity header rects remain tagged `semantic_role="entity"` for
  existing `test_fix_er.py::TestCardNonOverlap.test_er_native_scene_non_overlapping`.

---

### Task 7: Gates and fixture validation
Depends on: Task 6
Verification: run-gates

**Tests:**
- Run `pytest tests/test_fix_er.py tests/test_er_cardinality.py tests/test_syntax_er.py tests/test_er_finalized_layout.py -x`.
- Run `mypy scripts/mermaid_render/layout/er.py scripts/mermaid_render/layout/_strategies.py --ignore-missing-imports`.
- For both `er-cardinality-all` and `er-ecommerce`: call `compile_er_layout(src).validate()` and assert `errors == ()`.

**Approach:**
- Fix any type errors surfaced by mypy (expected: return type of
  `compile_er_layout`, `MarkerKind` import in `er.py`).
- If `test_fix_er.py::TestCardNonOverlap.test_er_native_scene_non_overlapping` fails
  because `layout_er_scene` no longer emits `SceneRect` with `semantic_role="entity"`,
  update that test to query `FinalizedLayout.node_layouts` outer bounds instead of
  scanning `LAYER_NODES`.
- All other existing tests must pass without modification.
