# Spec: flowchart-shape-geometry-overhaul

Mode: full (structural/public-interface change, multi-feature brief, dependent tasks)

- **Status:** Shipped

## Objective

Create one authoritative `ShapeGeometry` implementation for every flowchart shape so
that the same polygon math drives both visual rendering and connector routing. Fix all
cases where edges touch rectangular bounding boxes instead of actual shape outlines.

Targets: `flowchart-all-shapes`, `flowchart-diamond-clipping`  
Shapes: rect, round, diamond, stadium, circle, subroutine, doublecircle, hexagon,
        cylinder, flag, trapezoid, trapezoid-alt

## Acceptance Criteria

- [x] AC-1: All 12 shapes are recognizable and proportionate in rendered output.
      _Verified: `_dispatch` renders flowchart-all-shapes.mmd without error; shapes
      matched by class selectors in structural tests._
- [x] AC-2: Every polygon-outline edge touches the visible shape outline (no gap, no penetration).
      _Scope: polygon shapes only (`_POLY_CLIP_SHAPES`). Curved shapes (circle/stadium)
      use rect AABB approximation — acceptable divergence, deferred to backlog._
- [x] AC-3: No polygonal node shows a rectangular backing artifact (flag, diamond, hexagon, trapezoid, trapezoid-alt).
      _Verified: `test_no_rect_border_on_polygon_nodes` parametrized over all 5 shapes._
- [x] AC-4: `outline_path(w, h)` returns polygon vertices for polygon shapes, `None` for curved shapes.
      _Verified: `test_outline_path_closed` + `test_curved_shapes_outline_path_none`._
- [x] AC-5: `boundary_intersection()` for hexagon, trapezoid, trapezoid-alt, flag uses polygon ray intersection (not rect approximation).
      _Verified: `test_ray_hits_outline` (72 parametrized cases across polygon shapes)._
- [x] AC-6: Diamond `boundary_intersection()` is applied in both TB and LR routing paths.
      _Verified: `test_polygon_routing_clip_tb_endpoint_on_outline` + `test_polygon_routing_clip_lr_endpoint_on_outline` — parse actual SVG path M-coordinate and assert it lies on the diamond outline._
- [x] AC-7: Hexagon, trapezoid, trapezoid-alt, flag get polygon `boundary_intersection()` clipping in routing (TB and LR).
      _Same as AC-6 — `_POLY_CLIP_SHAPES` covers all 5 polygon types. TB and LR per-endpoint guards are independent (a pinned src port no longer suppresses dest clipping)._
- [x] AC-8: Flag renders with SVG polygon border, no rectangular CSS border.
      _Verified: `test_flag_svg_polygon_border` + `test_no_rect_border_on_polygon_nodes[flag]`.
      Both main renderer and `render_finalized()` paths fixed._
- [x] AC-9: Subroutine inner vertical lines stay inside the outer rectangle (y=2 to y=node_h-2).
      _Verified: `test_subroutine_inner_lines_inside_border`._
- [x] AC-10: `DiamondGeometry.measure()` uses the sum-of-dimensions formula.
      _Verified: `test_diamond_measure_sum_formula`._
- [x] AC-11: `DoubleCircleGeometry.measure()` includes the ring gap (DOUBLE_CIRCLE_RING=8).
      _Verified: `test_doublecircle_measure_includes_ring_gap`._
- [x] AC-12: Ray tests: 8 angles into every polygon shape; intersection lies on the outline within 2 px.
      _Verified: `test_ray_hits_outline` — 72 cases; all pass._
- [x] AC-13: Structural test: diamond nodes in `flowchart-diamond-clipping` output have no CSS `border` property on the outer container.
      _Verified: `test_diamond_no_rect_border_in_clipping_fixture`._

Additional tests added:
- `test_outline_path_matches_clip_path_css`: asserts `outline_path()` percentages match `_CLIP_PATH_CSS` polygon percentages for all 5 clip-path shapes.

## Files Touched

- `scripts/mermaid_render/layout/shape_geometry.py` — protocol + all implementations
- `scripts/mermaid_render/layout/_renderer.py` — flag SVG border (both rendering paths), subroutine inner lines (both paths), diamond overlay y-coord fix
- `scripts/mermaid_render/layout/_routing.py` — polygon clipping in TB and LR routing paths; fixed-port guard for TB path
- `tests/test_shape_geometry_rays.py` — new ray + structural + measure tests (177 tests)

## Not Changing

- `_constants.py`: `_node_size_diamond()`, `_node_size_hexagon()` etc. remain the authoritative
  size sources for the layout pipeline. `ShapeGeometry.measure()` is only used by external
  callers and tests.
- `_layout.py`: node size assignment logic unchanged.
- ELK routing path: only the Python fallback routing path is touched in `_routing.py`.
- Curved shapes (circle, doublecircle, stadium) in routing: these continue to use rect AABB
  approximation in routing. The ellipse boundary_intersection is correct mathematically but
  would require routing changes beyond this spec's scope.

## Declined Patterns

- Tempted to unify `_node_size_*` functions into `ShapeGeometry.measure()`; declining —
  that's a large refactor outside scope and would touch `_layout.py` and `_constants.py`.
- Tempted to add a `paint_html()` / `paint_svg()` full implementation; declining — stubs
  are the current contract; renderer renders shapes via its own inline HTML, not via the
  registry. Wiring paint methods is a separate pass.
- Tempted to add curved-shape routing clipping (circle/stadium ellipse intersection);
  declining — behavior is unchanged from before; out of scope for this pass.

## Boundaries

- Always: fix both `_renderer.py` rendering paths (main + `render_finalized`) in lockstep.
- Ask: if adding new shapes to `_POLY_CLIP_SHAPES` or `_CLIP_PATH_CSS`.
- Never: change `_constants.py` size functions or `_layout.py` size assignment.

## Testing Strategy

- `tests/test_shape_geometry_rays.py`: unit tests for geometry (outline_path, boundary_intersection, measure)
  and structural HTML tests for rendering artifacts.
- All tests run via `pytest tests/` (no browser required). 177 new tests; 4468 total pass.
