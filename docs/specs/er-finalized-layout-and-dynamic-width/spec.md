# er-finalized-layout-and-dynamic-width

Mode: full (structural change, multi-feature, dependent tasks)

- **Status:** Shipped
- **Depends on:** `elk-finalized-layout-roundtrip`, `mermaid-single-finalized-layout-pipeline`

## Objective

Move ER HTML and SVG rendering onto one measured `FinalizedLayout` pipeline.

Today `er.py::layout_er_scene()` (SVG) and `_strategies.py::_layout_er()` (HTML)
each own separate layout passes using the raw Sugiyama helpers (`_break_cycles`,
`_assign_ranks`, `_minimize_crossings`, `_assign_coordinates`). Both fix entity card
width at a compile-time constant (`_CARD_W = 200` in `er.py`; `NODE_W` in
`_strategies.py`), so wide entity names and long type strings are silently clipped,
and the two outputs can drift because they run independent coordinate assignments.

This spec replaces both paths with a single pipeline:

1. Measure each entity card width from its actual content columns.
2. Compile entities and relationships into a `LayoutGraph`.
3. Run ELK Layered orthogonal routing (falling back to measured Sugiyama when ELK
   is unavailable).
4. Receive a `FinalizedLayout` — one authoritative set of node positions and routed
   edge waypoints.
5. Render cardinality marks from the finalized endpoint port tangent.
6. Drive both HTML and SVG output from the same `FinalizedLayout` coordinates.

The existing `CardinalityEnd` model and tangent/normal cardinality painter are
preserved; only their input changes from ad-hoc boundary math to the port tangent
supplied by the layout engine.

Target fixtures: `er-cardinality-all`, `er-ecommerce`.

## Boundaries

**In scope**

- `scripts/mermaid_render/layout/er.py` — card width measurement, `LayoutGraph`
  compilation, ELK/Sugiyama dispatch, `FinalizedLayout` return, cardinality mark
  rendering from port tangent, label placement on longest clear segment.
- `scripts/mermaid_render/layout/_strategies.py` `_layout_er()` — replace
  independent coordinate pass with `FinalizedLayout`-driven HTML rendering.
- Port allocation for parallel and adjacent ER relationships (separate ports per
  parallel edge pair).
- `width_hint` applied as a uniform viewBox rescale of the completed `FinalizedLayout`
  (repack, not compress-only node positions).
- New test file `tests/test_er_finalized_layout.py`.

**Out of scope**

- `_layout.py`, `_layered.py`, `elk_adapter.py` — Sugiyama and ELK internals.
- Any other diagram type.
- The `_Edge.cardinality_src/dst` field type on the legacy `_Node/_Edge` IR.
- Visual theme / color tokens (`_BG_FILL`, `_ENTITY_HEADER_FILL`, etc.).

## Acceptance Criteria

- [x] AC1: No entity cards overlap — verified on both `er-cardinality-all` (8 cards)
  and `er-ecommerce` (5 cards) via `FinalizedLayout.node_layouts` outer-bounds
  overlap check, not HTML parsing.
- [x] AC2: No attribute text is clipped — for every entity, the measured card width
  covers badge column (22 px) + type column + name column + row padding (16 px);
  the rendered `NodeLayout.outer_bounds.w` equals the measured width, clamped
  between `_ER_MIN_CARD_W` and `_ER_MAX_CARD_W`.
- [x] AC3: All four cardinality combinations in `er-cardinality-all` render correct
  glyphs — each of the eight relationship endpoints produces the expected
  `CardinalityEnd` (one of `ONE·ONE`, `ONE·MANY`, `ZERO·ONE`, `ZERO·MANY`) and the
  glyph elements match the prior `_er_glyph_elements()` contract.
- [x] AC4: `er-ecommerce` relationships avoid unrelated cards — no routed edge
  waypoint intersects the bounding box of an entity it is not incident to
  (checked via `RoutedEdge.waypoints` vs `NodeLayout.outer_bounds`).
- [x] AC5: HTML and SVG have identical entity top-left coordinates and edge waypoints
  — for every node id, `html_left == svg_x` and `html_top == svg_y` within 1 px;
  for every relationship, the SVG line endpoints match the HTML SVG overlay within
  1 px.
- [x] AC6: `width_hint` scales or repacks the completed layout without compressing
  only node positions — at `width_hint=600` on `er-ecommerce` (natural width ~1200),
  the zoom factor applied to the viewBox equals `600 / natural_width`, and the
  HTML container `width` attribute reports the scaled value.
- [x] AC7: Parallel or adjacent ER relationships receive separate ports — for any
  two relationships sharing the same source–destination entity pair, their
  `RoutedEdge.src_port.position` values differ by at least 1 px.
- [x] AC8: Identifying (solid) and non-identifying (dotted) line styles are retained
  in `RoutedEdge.edge_style` and rendered as `stroke-dasharray="6 4"` for dotted
  edges only.
- [x] AC9: Relationship labels appear on the longest clear route segment — the label
  anchor point lies on the longest `RoutedEdge.waypoints` segment; label bounds do
  not overlap any entity card bounding box.
- [x] AC10: Cardinality marks are drawn from the port tangent supplied by the layout
  engine, not from recomputed centre-to-centre vectors — `_er_glyph_elements` is
  called with `(dx, dy)` derived from `PortLayout.direction`, not from
  `dst_centre - src_centre`.
- [x] AC11: `pytest tests/` passes with zero new failures — existing `test_fix_er.py`,
  `test_er_cardinality.py`, `test_syntax_er.py` all green.

## Testing Strategy

**Unit (no fixtures, isolated functions)**

- `test_er_finalized_layout.py::TestCardWidthMeasurement` — parametrized over
  representative attribute lists; asserts clamping to `_ER_MIN_CARD_W` /
  `_ER_MAX_CARD_W`; verifies badge column present only when constraint set.
- `test_er_finalized_layout.py::TestLayoutGraphCompilation` — small inline ER
  source (two entities, one relationship); asserts `LayoutGraph` node count,
  `LayoutEdge.source_marker` / `target_marker` match expected `MarkerKind`
  crow-foot variants; asserts edge `line_style` for dotted separator.

**Integration (fixtures, full pipeline)**

- `test_er_finalized_layout.py::TestFinalizedLayoutACs` — drives `layout_er_scene()`
  or the new `compile_er_layout()` entry point; checks AC1 (non-overlap via
  `outer_bounds`), AC5 (HTML/SVG parity), AC6 (`width_hint` viewBox), AC7 (port
  separation), AC9 (label bounds vs entity bounds).
- Existing `test_fix_er.py::TestCardNonOverlap` — must remain green against both
  HTML and native-SVG paths; overlap check now also queries `FinalizedLayout`
  directly (not only HTML regex).
- Existing `test_er_cardinality.py` — must remain green; cardinality parsing is
  unchanged.
- Existing `test_syntax_er.py` — must remain green.
