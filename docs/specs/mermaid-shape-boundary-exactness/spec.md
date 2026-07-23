# Mermaid Shape Boundary Exactness

Mode: full (structural — extends ShapeGeometry protocol; mathematical precision; multi-file)

- **Status:** Draft

## Objective

Several shape types in the renderer use rectangular boundary intersection even when their
visible outline is curved or slanted (rounded rectangles, stadiums, cylinder silhouette).
`_default_anchor` obtains a center-side intersection and then translates it perpendicular
to the side, which can place an anchor off a curved or slanted boundary. Marker clearance
defaults broadly to one constant regardless of marker kind. The double-circle HTML painter
and SVG painter are not fully equivalent — one produces an unintended filled inner disc.

This spec completes the existing `ShapeGeometry` abstraction by adding analytic (or
stable numerical) implementations of each required operation for every supported shape,
removing the rectangular approximation from curved and slanted shapes, and making marker
clearance marker-specific. All painting, intersection, anchoring, content fit, and
clearance for a given shape live in one place.

Depends on: `mermaid-text-measurement-adoption` (content-fit sizing uses real measured
text; shape geometry must know the measured label rectangle before growing).

## Boundaries

**In scope:**
- Explicit protocol methods on `ShapeGeometry`:
  `measure(text_metrics, padding) -> Size`,
  `outline_path(size) -> ShapePath`,
  `contains(point, size, inset=0) -> bool`,
  `boundary_intersection(center, ray, size) -> Point`,
  `boundary_anchor(side, normalized_offset, size) -> Point`,
  `normal_at(point, size) -> Vector`,
  `marker_clearance(marker_kind, tangent, point) -> float`,
  `paint_html(...)`,
  `paint_svg(...)`.
- Analytic or stable intersections: rectangle (ray/box), rounded rectangle (straight
  edges + quarter ellipses), stadium (capsule sides + semicircles), circle/double-circle
  (ellipse ray), diamond/hexagon/flag/trapezoids (ray/polygon segment), cylinder (visible
  ellipse-and-wall silhouette).
- Direct boundary parameterization: replace translated side-center anchors.
- Content-fit sizing: construct padded label rectangle; test corners against usable
  interior; grow width/height deterministically until fit; apply to diamond, circle,
  double-circle, hexagon, cylinder, flag, trapezoid, inverse trapezoid.
- Bounded proportional slant/notch values (replace fixed constants).
- Logical silhouette of cylinder matches its painted caps and walls.
- Marker-specific clearance: ordinary filled/open arrows, hollow triangle, filled diamond,
  hollow diamond, ER cardinality glyph reserve.
- Double-circle equivalence: two stroked rings, no unintended filled inner disc, label
  above both rings, separate dedicated style for state-final symbol.
- Property-based tests over ray angles and dimensions.
- Flowchart and state renderers removed of independent shape-intersection math.

**Out of scope:**
- Adding new shape types beyond those currently supported.
- SVG-filter or CSS-shadow effects.
- Sequence diagram shapes.
- Text measurement (see `mermaid-text-measurement-adoption`).

**Note on `outline_path`:** `outline_path(size) -> ShapePath` is verified transitively
by every `boundary_intersection` and `contains` test (AC1–AC3, AC8) since all intersection
and containment computations consume the outline path produced by this method. A dedicated
AC is not added; any implementation error in `outline_path` will surface through the
property-based sweep in AC8.

**Never:**
- Use rectangular boundary intersection for a non-rectangular shape's visible outline.
- Translate a center-side anchor perpendicular to the side for curved/slanted shapes.
- Apply the same marker clearance constant regardless of marker kind.
- Leave the flowchart or state renderer with independent intersection math.

## Acceptance Criteria

- [ ] AC1: Rounded-rectangle and stadium nodes produce boundary intersections on their
  actual curved outline; rectangular approximation is no longer used for these shapes.
- [ ] AC2: Cylinder route endpoints lie on the visible ellipse-and-wall silhouette, not
  on a rectangle bounding the cylinder.
- [ ] AC3: Anchors on curved and slanted outlines (rounded rectangle, stadium, diamond,
  hexagon, cylinder) lie on the actual outline within a 0.5-pixel tolerance.
- [ ] AC4: Content-fit sizing for diamond, circle, double-circle, hexagon, cylinder,
  flag, trapezoid, and inverse trapezoid ensures the padded label rectangle fits within
  the usable interior.
- [ ] AC5: Double-circle HTML and SVG output are semantically equivalent: two stroked
  rings, no filled inner disc, label positioned above both rings.
- [ ] AC6: Marker clearance returns distinct non-zero values for ordinary arrow, hollow
  triangle, filled diamond, hollow diamond, and ER cardinality glyph.
- [ ] AC7: Flowchart and state renderers contain no independent shape-intersection or
  shape-anchor math; all such calls go through `ShapeGeometry`.
- [ ] AC8: Property-based tests assert over ≥100 random ray angles per shape: the
  intersection point lies on the outline; a point immediately inside passes `contains`;
  a point immediately outside fails `contains`.
- [ ] AC9: `normal_at(point, size)` returns a unit-length vector pointing outward from
  the shape at the given boundary point; verified for each implemented shape at ≥8
  distinct boundary points.
- [ ] AC10: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

Mix of analytic unit tests and property-based tests (using `hypothesis` if available,
or parametrized angle sweeps otherwise).

- **Rectangle intersection:** test cardinal and diagonal rays; assert result is on the
  box edge.
- **Rounded-rectangle intersection:** sweep ray angles; assert result lies on straight
  segment or quarter-ellipse arc, not on the rectangular bounding box.
- **Stadium intersection:** sweep ray angles; assert result lies on capsule side or
  semicircle.
- **Circle/double-circle intersection:** sweep ray angles; assert result lies on the
  ellipse.
- **Diamond intersection:** test rays toward each vertex and each mid-segment; assert
  result lies on a diamond segment.
- **Cylinder silhouette:** test rays toward cap and wall; assert result lies on painted
  outline.
- **Content-fit — diamond:** assert a label wider than the usable diagonal causes width
  growth; assert the padded label fits after growth.
- **Content-fit — circle:** assert label height causes radius growth.
- **Double-circle equivalence:** render double-circle in HTML and in SVG; parse output;
  assert two stroked ring elements and no filled inner disc.
- **Marker clearance:** assert `hollow_triangle` clearance > `filled_arrow` clearance;
  assert `filled_diamond` > `filled_arrow`; all values > 0.
- **State renderer no-independent-math:** grep for shape-intersection patterns in
  `_strategies.py` and state-specific compiler; assert zero matches after this spec ships.
