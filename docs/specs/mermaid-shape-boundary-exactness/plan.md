# Implementation Plan — Mermaid Shape Boundary Exactness

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_strategies.py` or dedicated shape geometry module (wherever `ShapeGeometry` protocol implementations live); `scripts/mermaid_render/layout/_renderer.py` (double-circle HTML fix, both rendering paths); `tests/test_shape_geometry.py` (new or extended).
2. Done when: `pytest tests/` passes; property-based tests sweep ≥100 angles per shape and find no intersection off the outline; `grep -n "boundary_intersection.*rect" scripts/mermaid_render/` returns zero matches for rounded/stadium/cylinder shapes; HTML and SVG double-circle produce two stroked rings and no filled disc.
3. Not changing: text measurement (see `mermaid-text-measurement-adoption`); route geometry beyond clipping points; the ELK adapter; painter architecture (shapes still go through the centralized ShapeGeometry painters).

**Declined patterns:**
- Tempted to use a general polygon rasterizer for all shapes; declining — analytic solutions exist for all required shapes and are more numerically stable.
- Tempted to add a new abstract base class for shapes; declining — the spec explicitly says "complete the existing ShapeGeometry abstraction without replacing its centralized painters."
- Tempted to use SciPy for intersection math; declining — all required intersections are closed-form; no external math library dependency needed.

---

## Tasks

### Task 1: Extend `ShapeGeometry` protocol
Depends on: none
Verification: TDD

**Tests:**
- `test_shape_geometry_protocol_methods`: assert each of the nine protocol methods exists on `ShapeGeometry` with the correct signature.
- `test_rectangle_implements_protocol`: instantiate a `RectangleGeometry`; assert all nine methods are callable.
- `test_normal_at_unit_length`: for each shape, call `normal_at` at 8 boundary points; assert each returned vector has length 1.0 within 0.01 tolerance.
- `test_normal_at_points_outward`: for a rectangle, call `normal_at` at the top-center boundary point; assert the vector points upward (positive Y component, zero X).

**Approach:**
- Add the following to the `ShapeGeometry` protocol (or ABC): `measure`, `outline_path`, `contains`, `boundary_intersection`, `boundary_anchor`, `normal_at`, `marker_clearance`, `paint_html`, `paint_svg` (nine methods total).
- Each existing shape subclass must implement all nine; add stubs raising `NotImplementedError` as a migration aid.

---

### Task 2: Analytic intersections for curved shapes
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_rounded_rect_intersection_not_on_bounding_box`: sweep 100 angles; for each, assert the intersection point differs from the axis-aligned bounding box intersection.
- `test_stadium_intersection_on_capsule`: sweep 100 angles; assert the intersection lies on the straight side or semicircle, not the rectangle.
- `test_circle_intersection_on_ellipse`: sweep 100 angles; assert the intersection lies on the ellipse within 0.1-pixel tolerance.
- `test_cylinder_intersection_on_silhouette`: sweep angles toward cap and wall; assert intersection lies on the painted silhouette.

**Approach:**
- `RoundedRectGeometry.boundary_intersection`: parametrize by angle; for angles in the straight-edge sectors, use rectangle ray; for corner-arc sectors, solve quarter-ellipse intersection analytically.
- `StadiumGeometry.boundary_intersection`: for center-aligned angles, use capsule-side ray; for end-cap angles, solve semicircle.
- `CircleGeometry.boundary_intersection` and `DoubleCircleGeometry.boundary_intersection`: solve `P + t*D` on the ellipse equation.
- `CylinderGeometry.boundary_intersection`: model the visible silhouette as the union of the top ellipse arc, two vertical lines, and the bottom ellipse arc.

---

### Task 3: Polygon intersections for faceted shapes
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_diamond_intersection_on_segment`: sweep angles; assert intersection lies on a diamond edge segment (not interior or exterior).
- `test_hexagon_intersection_on_segment`: sweep angles; assert intersection lies on a hexagon segment.
- `test_trapezoid_intersection_on_segment`: sweep angles; assert intersection on a trapezoid edge.
- `test_flag_intersection_on_segment`: sweep angles; assert intersection on a flag edge.

**Approach:**
- Add `_ray_polygon_intersection(center, ray_dir, vertices) -> Point` utility.
- Use it for `DiamondGeometry`, `HexagonGeometry`, `TrapezoidGeometry`, `InverseTrapezoidGeometry`, `FlagGeometry`.

---

### Task 4: Content-fit sizing
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_diamond_content_fit_grows_for_wide_label`: construct a diamond with a label wider than the usable interior; assert the returned `Size` has `width > label_width * sqrt(2)`.
- `test_circle_content_fit_grows_for_tall_label`: construct a circle where label height forces radius increase; assert returned radius accommodates the label diagonal.
- `test_content_fit_label_inside`: for each non-rectangular shape, assert that after sizing, placing the padded label rectangle at the center and testing all four corners with `contains(..., inset=0)` returns `True`.

**Approach:**
- Add `content_fit_size(label_rect: Rect, padding: Insets) -> Size` to each shape that requires it.
- Implement: construct padded label rectangle; test corner containment with `contains`; if any corner fails, grow width/height by 1px increments and retry; cap growth at a maximum dimension.
- Use this size in `measure(text_metrics, padding)`.

---

### Task 5: Marker-specific clearance
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_hollow_triangle_clearance_greater_than_arrow`: assert `marker_clearance(HOLLOW_TRIANGLE, ...)` > `marker_clearance(FILLED_ARROW, ...)` for the same shape and tangent.
- `test_filled_diamond_clearance_greater_than_arrow`: assert `marker_clearance(FILLED_DIAMOND, ...)` > `marker_clearance(FILLED_ARROW, ...)`.
- `test_er_glyph_clearance_positive`: assert `marker_clearance(ER_CARDINALITY, ...)` > 0 for every shape.

**Approach:**
- In `ShapeGeometry.marker_clearance`, accept `marker_kind: MarkerKind` as a parameter.
- Return distinct float values per marker kind based on typical marker bounding box dimensions (hollow triangle ~18px, filled diamond ~20px, hollow diamond ~22px, ordinary arrow ~10px, ER glyph ~16px).
- These are per-kind constants, not shape-dependent; the method exists on the protocol to allow shape-specific overrides in future.

---

### Task 6: Double-circle HTML/SVG equivalence
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_double_circle_html_two_rings`: render a double-circle node as HTML; parse the output; assert exactly two elements with a `stroke` and `border-radius: 50%`; assert no `background-color` fill on the inner element.
- `test_double_circle_svg_two_rings`: render as SVG; parse; assert exactly two `<circle>` or `<ellipse>` elements with `stroke` and no unintended `fill` on the inner.
- `test_state_final_distinct_style`: compile a state diagram final state; assert it uses a style distinct from double-circle node style.

**Approach:**
- In `_renderer.py` (both rendering paths), fix the double-circle HTML painter:
  - Outer ring: `border-radius: 50%; border: 2px solid; background: transparent;`.
  - Inner ring: same, positioned absolutely inside outer.
  - Remove any `background-color` or `background` that creates a filled disc.
- In the SVG painter, fix the double-circle SVG painter analogously.
- Add a dedicated CSS class for state-final symbols so their fill (which is intentional: filled outer, filled inner gap) does not inherit double-circle transparent style.

---

### Task 7: Direct boundary parameterization (anchors)
Depends on: Task 2, Task 3
Verification: TDD

**Tests:**
- `test_rounded_rect_anchor_on_outline`: call `boundary_anchor(BOTTOM, 0.5, size)` on a rounded rect; assert the result lies on the outline within 0.5-pixel tolerance.
- `test_stadium_anchor_on_outline`: call `boundary_anchor(LEFT, 0.0, size)` on a stadium; assert result on the semicircle.
- `test_anchor_not_translated_side_center`: construct a shape where the old translated side-center would be clearly off the curve; assert the new `boundary_anchor` differs from that point.

**Approach:**
- Replace `_default_anchor`'s center-side + perpendicular-translation pattern with direct parameterization.
- For each side (TOP, BOTTOM, LEFT, RIGHT): parameterize the outline curve/segment for that side by a `normalized_offset ∈ [0,1]`; return the point at that fraction along the outline.
- Round corners: parameterize the quarter-ellipse arc by angle.
- Straight edges: parameterize by linear interpolation.

---

### Task 8: Remove independent intersection math from flowchart/state renderers
Depends on: Tasks 2, 3, 7
Verification: Goal-based check

**Done when:** `grep -rn "\.intersection\|clip_to_boundary\|rect.*ray\|ray.*rect" scripts/mermaid_render/layout/_strategies.py` returns zero matches for shape-intersection code (layout validation uses different patterns).

**Approach:**
- Search for any `boundary_intersection`, `clip_to_boundary`, or equivalent calls inside `_strategies.py` or the state compiler that compute shape intersection independently.
- Replace each with a call to the corresponding `ShapeGeometry.boundary_intersection`.
- Remove the independent math after verifying tests still pass.
