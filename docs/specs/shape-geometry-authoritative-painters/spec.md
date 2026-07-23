# shape-geometry-authoritative-painters

Mode: full (structural change, multi-feature)

- **Status:** Shipped

## Objective

Finish the `ShapeGeometry` abstraction so each shape has one authoritative implementation
for measurement, boundary intersection, HTML painting, and SVG painting.

Today `paint_html()` and `paint_svg()` on every geometry class return `None`. The actual
rendering lives in three separate places:

1. `layout/_renderer.py` — `_render_graph_fragment()` main path (per-shape branches, ~250 lines)
2. `layout/_renderer.py` — `render_finalized()` ELK path (same branches duplicated, ~150 lines)
3. `paint.py` — `_node_scene_elements()` (per-shape scene-element branches, ~120 lines)

This triplication causes geometry drift between the HTML and SVG renderers — polygon vertex
arithmetic is expressed three times with three independent percentage constants. The feature
consolidates all shape-specific painting into `SHAPE_REGISTRY[shape].paint_html()` and
`SHAPE_REGISTRY[shape].paint_svg()`, making `outline_path()` the single source of truth
for the visible outline, fill clipping, connector intersection, and marker clearance.

**Targets:** `flowchart-all-shapes`, `flowchart-diamond-clipping`

**Shapes:** rect, round, stadium, diamond, circle, doublecircle, cylinder, hexagon,
trapezoid, trapezoid-alt, subroutine, flag, bar (13 total)

## Boundaries

- **Always:** fix both `_renderer.py` rendering paths (`_render_graph_fragment` + `render_finalized`)
  in lockstep — any shape fix that lands in one must land in both.
- **Always:** derive polygon `<polygon points="...">` and `clip-path` percentages from
  `outline_path(w, h)`, never from inline arithmetic that diverges from the geometry class.
- **Ask:** before adding new shapes to `SHAPE_REGISTRY` or changing `outline_path()` vertex counts.
- **Never:** change `_constants.py` size functions or `_layout.py` size assignment.
- **Never:** change the `ShapeGeometry` protocol method signatures.
- **Out of scope:** curved-shape routing clipping (circle/stadium ellipse boundary in `_routing.py`).

## Acceptance Criteria

- [ ] AC-1: `paint_svg()` returns a non-`None` SVG string for all 13 registered shapes.
- [ ] AC-2: `paint_html()` returns a non-`None` HTML string for all 13 registered shapes.
- [ ] AC-3: All 13 fixture shapes are visually distinct and proportionate in both HTML and
      SVG output; `flowchart-all-shapes` renders without error.
- [ ] AC-4: No polygonal node has a rectangular backing border — diamond, hexagon,
      trapezoid, trapezoid-alt, and flag all use SVG polygon strokes, not `border:` CSS.
- [ ] AC-5: Every connector terminates on the painted outline; the connector tip coordinate
      returned by `boundary_intersection()` lies on the `outline_path()` boundary within 2 px.
- [ ] AC-6: `flowchart-diamond-clipping` has no rectangular artifacts and no penetrating edges.
- [ ] AC-7: HTML and SVG painters derive polygon vertices from the same `outline_path()` call;
      painter parity tests confirm normalized vertex sets match within 1 px tolerance.
- [ ] AC-8: `_render_graph_fragment()` in `_renderer.py` no longer contains per-shape painting
      branches; all shapes route through `SHAPE_REGISTRY[shape].paint_html()`.
- [ ] AC-9: `render_finalized()` in `_renderer.py` no longer contains per-shape painting
      branches; all shapes route through `SHAPE_REGISTRY[shape].paint_html()`.
- [ ] AC-10: `_node_scene_elements()` in `paint.py` no longer contains per-shape scene-element
      branches; all shapes route through `SHAPE_REGISTRY[shape].paint_svg()`.
- [ ] AC-11: `flag` uses its 5-vertex asymmetric polygon in native SVG output (not a rectangle
      or a rounded rect).
- [ ] AC-12: `subroutine` `paint_svg()` output includes two inner vertical `<line>` elements
      inset 8 px from each side.
- [ ] AC-13: `doublecircle` renders as two stroked concentric rings; the inner ring carries
      `fill="none"` — no filled disc except the UML final-state semantic already handled by
      `_is_terminal_doublecircle`.
- [ ] AC-14: `CylinderGeometry.outline_path(w, h)` returns a bounding silhouette that spans
      the full height `h`, including the space consumed by both elliptical caps.
- [ ] AC-15: All `data-node-*` and accessibility attributes produced by the caller are preserved
      on the outermost group/container element in both painter outputs.
- [ ] AC-16: 8-angle (0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°) ray-intersection tests pass
      for all polygon shapes; intersection lies on `outline_path()` boundary within 2 px.

## Testing Strategy

All tests via `pytest tests/` (no browser required).

**Extend `tests/test_shape_geometry_rays.py`:**

- `test_paint_svg_not_none` — parametrized over all 13 SHAPE_REGISTRY keys; `paint_svg(0, 0, 100, 60)` returns a non-`None` string.
- `test_paint_html_not_none` — same parametrization; `paint_html(0, 0, 100, 60, inner_html="")` returns a non-`None` string.
- `test_painter_vertex_parity` — for each polygon shape (diamond, hexagon, trapezoid, trapezoid-alt, flag), parse the `polygon points="..."` string from `paint_svg()` output and compare to `outline_path()` vertices scaled to the same `(w, h)`; all points within 1 px.
- `test_doublecircle_ring_semantics` — `paint_html(...)` contains no `background:` disc div inside the outer ring; `paint_svg(...)` contains two `<circle>` elements and the inner one has `fill="none"`.
- `test_flag_svg_polygon_5_vertices` — `paint_svg(0, 0, 120, 50)` for `flag` contains a `<polygon>` with exactly 5 coordinate pairs.
- `test_subroutine_svg_vertical_rules` — `paint_svg(0, 0, 140, 50)` for `subroutine` contains exactly two `<line>` elements.
- `test_cylinder_outline_full_height` — `CylinderGeometry().outline_path(80, 60)` spans `y=0` to `y=60`.

**Regression guard:**
Existing 177 tests in `test_shape_geometry_rays.py` (ray, outline_path, measure, structural) pass unchanged.
