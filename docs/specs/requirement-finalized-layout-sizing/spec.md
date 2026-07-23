# requirement-finalized-layout-sizing

Mode: full (structural change, dependent tasks)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** `mermaid-single-finalized-layout-pipeline` (must ship first — it provides the shared FinalizedLayout → HTML and FinalizedLayout → SVG rendering paths that this feature wires into)
- **Contract:** none
- **Shape:** refactor + test expansion

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Consolidate `requirementDiagram` HTML and SVG rendering around a single shared
`compile_requirement()` function that returns `FinalizedLayout`.

Today there are two divergent code paths:

- **Native SVG path** — `scripts/mermaid_render/layout/requirement.py`
  (`layout_requirement_scene`) builds its own card geometry, topological rank
  assignment, and band-clamped routing, then emits an `SvgScene` directly.
- **HTML path** — `scripts/mermaid_render/layout/_strategies.py`
  (`_layout_requirement`) duplicates parsing and a simpler layout, then calls
  `_graph_from_content_nodes` for the generic HTML renderer.

Both paths drift independently. Card sizing, routing, and semantic metadata are
not shared. `width_hint` / `height_hint` are honored only partially.

After this feature both paths call `compile_requirement()`, which produces a
single `FinalizedLayout` carrying fully measured card geometry, orthogonal
routes, and semantic metadata. HTML and SVG painters receive identical
coordinates; there is no second layout pass.

## Boundaries

### Always do

- Reuse the Mermaid 11.15-compatible strict parser (already in `requirement.py`
  `_parse_requirement_source`, `_parse_attr_value`) as the single canonical parser.
  `_layout_requirement` must not keep its own duplicate; it calls
  `compile_requirement()`.
- Honor `width_hint` and `height_hint` for all nonempty diagrams; never silently
  ignore them (repack ranks when useful, otherwise uniform output scaling).
- Preserve requirement `subtype` (e.g. `functionalRequirement`,
  `performanceRequirement`, `designConstraint`) and element type as semantic
  metadata on `NodeLayout`.
- Attach each relation label to a `RoutedEdge.label_layout` (finalized route
  segment), not assembled ad-hoc by the painter.
- Measure card height from every attribute key+value pair (wrapped via
  `_wrap_text`) — not just `text` and `docref`.
- Measure card width from the longest rendered line among: node identifier,
  subtype label, and all wrapped attribute lines.

### Never

- **Never reopen the mmdc grammar/docref issue.** The strict quoted-path
  validation (`_parse_attr_value`) is already resolved. Do not alter, relax,
  or bypass that logic.
- Never introduce a third rendering path. After this feature there are exactly
  two consumers of `compile_requirement()`: the HTML painter and the SVG
  painter.
- Never add a new production dependency.

### Ask first

- Changing `FinalizedLayout`, `NodeLayout`, or `RoutedEdge` field signatures
  in `_geometry.py` — those are shared IR types; changes require cross-cutting
  review.
- Moving `compile_requirement()` outside of `requirement.py` — the function
  lives there alongside the parser and layout helpers.

## Acceptance Criteria

- [x] AC1: `requirement-basic` fixture parses successfully in both native SVG
  mode (`layout_requirement_scene`) and mmdc/HTML mode (`_layout_requirement`),
  producing non-empty output with no error.
- [x] AC2: All four cards (`test_req`, `func_req`, `perf_req`, `test_entity`)
  appear in both HTML and SVG output of `requirement-basic`.
- [x] AC3: All three relations (`satisfies`, `verifies`, `derives`) appear in
  both HTML and SVG output of `requirement-basic`.
- [x] AC4: No text is clipped — every attribute line (including wrapped lines)
  fits within its card's content bounds; card height is strictly >= the sum of
  header height + all wrapped-line heights + vertical padding.
- [x] AC5: No relation route passes through any card — every waypoint segment
  in `RoutedEdge.waypoints` lies outside the `outer_bounds` of all
  `NodeLayout` entries.
- [x] AC6: A nonempty diagram with a nonzero `width_hint` produces a canvas
  whose width is exactly `width_hint` (repacked or uniformly scaled), never
  the raw unconstrained width.
- [x] AC7: A nonempty diagram with a nonzero `height_hint` produces a canvas
  whose height is exactly `height_hint` (repacked or uniformly scaled), never
  the raw unconstrained height.
- [x] AC8: `NodeLayout.css_classes` contains the requirement subtype string
  (e.g. `"req-functionalRequirement"`) for requirement nodes and the element
  type for element nodes; this metadata is present in both HTML and SVG output.
- [x] AC9: Each `RoutedEdge` in the `FinalizedLayout` produced by
  `compile_requirement()` carries a non-None `label_layout` with `text` equal
  to the relation type string.
- [x] AC10: HTML coordinates (`NodeLayout.outer_bounds`, `RoutedEdge.waypoints`)
  and SVG coordinates (scene rects / polyline points) are identical — both
  consumers read the same `FinalizedLayout` from `compile_requirement()`,
  no second geometry pass.

## Testing Strategy

- **TDD for `compile_requirement()`** — write tests before the function
  exists; each test asserts a specific geometry or metadata invariant on the
  returned `FinalizedLayout`.  Cover: four-card/three-edge fixture, quoted
  paths, long text wrapping, multiple outgoing relations from one node, and
  same-rank relations.
- **Regression for existing tests** — all tests in `tests/test_syntax_requirement.py`
  and `TestNativeSceneGeometry` must remain green without modification.
- **AC coverage** — each AC above maps to at least one named test case in
  `tests/test_requirement_layout.py` (new file).
- **Coordinate identity check (AC10)** — one test calls both the HTML path and
  the SVG path on the same source and asserts that card top-left coordinates
  and edge waypoints are numerically identical.

## Assumptions

1. `mermaid-single-finalized-layout-pipeline` ships first and provides working
   FinalizedLayout → HTML and FinalizedLayout → SVG rendering paths. This
   feature does not implement those renderers; it implements the geometry
   producer (`compile_requirement()`) and wires the two paths to it.
2. `_parse_requirement_source` and `_parse_attr_value` in `requirement.py` are
   the canonical parser; `_layout_requirement` in `_strategies.py` drops its
   local duplicate parser on adoption.
3. `_wrap_text`, `_compute_ranks`, `_order_nodes_in_ranks`, `_clamp_mid_y`,
   and `_route_edge` in `requirement.py` remain valid layout helpers and are
   called by `compile_requirement()`; they are not rewritten.
4. `FinalizedLayout`, `NodeLayout`, and `RoutedEdge` fields are stable for the
   duration of this feature.

## Declined patterns

- Tempted to unify `requirement.py` and `_strategies.py` into a single file —
  declining; the split (native scene vs shared geometry compiler) is the right
  long-term shape.
- Tempted to fix the width-of-card computation by patching `_NODE_W` constant
  directly — declining; the `_NODE_W` constant becomes a minimum, and measured
  width from text lengths replaces the fixed value.
