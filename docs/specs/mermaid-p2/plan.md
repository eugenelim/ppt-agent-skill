# Mermaid P2 Implementation Plan

## Task 0 — Baseline provenance
**Verification:** Goal-based — `notes/mermaid-p2-report.md` exists with required fields
**Depends on:** none

Record git SHA, mmdc/Python/Pillow/lxml versions, run full test suite, note starting
test counts. Create `notes/mermaid-p2-report.md` with Stage 0 section.

## Task 1 — SvgScene IR
**Verification:** TDD — `tests/test_svg_scene.py` all pass
**Depends on:** none

Create `scripts/mermaid_render/scene.py` with frozen dataclasses:
- `PaintStyle`, `StrokeStyle`, `FillStyle`
- `SceneRect`, `SceneRoundedRect`, `SceneCircle`, `SceneEllipse`
- `SceneLine`, `ScenePolyline`, `ScenePolygon`, `ScenePath`
- `SceneText`, `SceneTextLine`
- `SceneImage`, `SceneGroup`
- `MarkerDefinition`, `LinearGradientDefinition`, `RadialGradientDefinition`, `ClipPathDefinition`
- `AccessibilityMetadata`
- `SvgScene` (top-level container)

Tests:
- All scene primitives are frozen (immutable)
- `SvgScene` has required fields: id, diagram_type, width, height, viewBox, title, desc,
  definitions, layers (background/boundaries/edges/nodes/labels/notes/overlays), diagnostics
- Scene elements support: id, css_classes, role, data attributes, transform, paint style, bounds

## Task 2 — Native SVG Serializer
**Verification:** TDD — `tests/test_native_svg_serializer.py` all pass
**Depends on:** Task 1

Create `scripts/mermaid_render/svg_serializer.py` with `scene_to_svg(scene) -> bytes`.

Uses `lxml.etree`. Requirements:
- Deterministic element and attribute ordering
- Deterministic IDs (derived from content, not object id() or uuid)
- Canonical float formatting (3dp, no trailing zeros, no negative zero, reject NaN/inf)
- XML escaping for text/attrs
- Native `<text>/<tspan>` from TextLayout lines
- No `<foreignObject>`
- Markers: start/end/bidirectional/open/filled/state/timeline arrows
- `validate_scene()` that rejects: duplicate ids, unresolved refs, non-finite numbers,
  invalid viewBox, foreignObject

Tests:
- Empty scene → valid minimal SVG
- Nested groups
- All basic shape primitives
- Text with multiple tspans
- Marker start + end
- Gradient
- Clip path
- XML-sensitive text (e.g. `<>&"`)
- Deterministic IDs across two calls with identical input
- Byte-identical output across repeated calls
- NaN/inf rejection

## Task 3 — Native backend switch for `to_svg()`
**Verification:** TDD — `tests/test_native_svg_backend.py` all pass
**Depends on:** Tasks 1 + 2

Create `scripts/mermaid_render/native_svg.py` with `dispatch_native(src, *, theme, width_hint) -> str`.

Update `scripts/mermaid_render/__init__.py`:
- `to_svg()` calls `dispatch_native()` by default
- `MERMAID_RENDER_SVG_BACKEND=legacy-dom` env var falls back to old path
- Default is `native`
- Native failure propagates with diagram type + context

Tests:
- Importing and calling `to_svg` does not import Playwright
- `to_svg` output contains no `<foreignObject>`
- `to_svg` output contains no `html/head/body` elements
- Output is byte-identical across two renders of same source
- `to_html` is still Playwright-free
- `MERMAID_RENDER_SVG_BACKEND=legacy-dom` selects old path (mock test)

## Task 4 — Generic paint layer (mechanical migration)
**Verification:** TDD — `tests/test_native_svg_all_diagrams.py` core subset passes
**Depends on:** Tasks 1 + 2 + 3

Create `scripts/mermaid_render/paint.py` with `layout_to_scene(...)` that converts
the output of the existing layout algorithms to an `SvgScene`.

For the 14 "mechanical" diagram types (flowchart, class, ER, sequence, gantt, gitgraph,
journey, requirement, kanban, packet, pie, xychart, quadrant, block):

- Take the mutable `_Node`/`_Edge`/`_Group` layout objects with computed x,y
- Convert each node shape to the appropriate `SceneRect`/`SceneCircle`/etc.
- Convert each edge waypoints to `ScenePath`
- Convert each label `TextLayout` to `SceneText`/`SceneTextLine`
- Assign layers: groups→boundaries, edges→edges, nodes→nodes, labels→labels

Tests (smoke):
- Every mechanical fixture produces a non-empty `SvgScene`
- No `<foreignObject>` in serialized output
- viewBox is positive and finite
- Text count > 0 for diagrams with labels

## Task 5 — Mind Map tidy-tree layout
**Verification:** TDD — `tests/test_mindmap_tidy_layout.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/mindmap.py` with:
- `MindMapNode` semantic model
- Reingold-Tilford/Buchheim tidy-tree algorithm (first walk, apportion, move subtree,
  execute shifts, second walk, bounds normalization)
- Two-sided layout: split root children by subtree weight, run tidy-tree on each side,
  mirror left, align to root center
- Cubic bezier link paths from shape boundary to shape boundary

Add fixtures: `mindmap-tidy.mmd`, `mindmap-default.mmd`, `mindmap-tidy-unbalanced.mmd`,
`mindmap-tidy-long-labels.mmd`, `mindmap-tidy-deep.mmd`, `mindmap-radial-regression.mmd`

Tests:
- `layout: tidy-tree` selects tidy-tree strategy
- Root is centered
- Nodes appear on both sides when multiple root branches
- Depth is monotonic away from root
- Source order preserved within each side
- No node-node overlap
- Zero edge crossings for ordinary tree
- Default radial fixture remains radial

## Task 6 — Timeline semantic column layout
**Verification:** TDD — `tests/test_timeline_semantics.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/timeline.py` with:
- `TimelineDiagram`, `TimelineTask`, `TimelineEvent`, `TimelineSection` models
- Column layout: tasks left-to-right, events stacked in column
- Vertical dashed stem, shared horizontal activity line with end arrow
- Section headers spanning tasks
- Column width derived from measured TextLayout

Add fixtures: `timeline-basic.mmd`, `timeline-multiple-events.mmd`,
`timeline-with-sections.mmd`, `timeline-long-labels.mmd`, `timeline-single-period.mmd`

Tests:
- Task order matches source order
- Continuation events belong to correct task
- Each event lies inside its task column
- Task/event boxes do not overlap
- Section header contains task columns
- Activity line has one end marker
- Repeated output is deterministic

## Task 7 — Architecture visual grammar
**Verification:** TDD — `tests/test_architecture_painter.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/architecture.py` and
`scripts/mermaid_render/paint/architecture.py`.

- Service tile: fixed icon area + label below (not narrow card)
- Group: dashed boundary rect + group icon + label
- Edges: fixed side ports, bidirectional = one path + two markers
- No legend by default

Add fixtures: `architecture-beta.mmd` (may already exist)

Tests:
- Service icon tile dimensions
- Service label doesn't shrink icon tile
- Group icon + label + boundary present
- Side ports honored
- Bidirectional: one path, two markers
- No legend element by default
- No label-tile overlap
- Deterministic output

## Task 8 — C4 visual grammar
**Verification:** TDD — `tests/test_c4_painter.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/c4_layout.py` and
`scripts/mermaid_render/paint/c4.py`.

- Distinct painters: Person, System, SystemDb, Container, ContainerDb,
  ContainerQueue, Component, ComponentDb, ComponentQueue, external variants
- Database → cylinder geometry, Queue → queue geometry
- C4 text hierarchy: stereotype, label, technology, description painted separately
- Recursive boundaries with containment
- BiRel → one path, two markers
- Direction hints affect route
- Title in viewBox

Add fixtures: `c4-container.mmd`, `c4-context.mmd`, `c4component.mmd`,
`c4-all-shapes.mmd`, `c4-nested-boundaries.mmd`, `c4-directional-relations.mmd`,
`c4-bidirectional.mmd`

Tests:
- Each C4 kind selects correct painter
- Database geometry is not plain rectangle
- Queue geometry is not plain rectangle
- Person vector present
- External styling distinct
- Stereotype/label/technology/description separate
- All boundaries contain descendants
- Every relation = one route
- BiRel = one path, two markers
- Title in viewBox
- Deterministic output

## Task 9 — State hierarchy
**Verification:** TDD — `tests/test_state_hierarchy.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/state.py` and
`scripts/mermaid_render/paint/state.py`.

- Semantic model: AtomicState, CompositeState, Transition, InitialPseudoState,
  FinalPseudoState, ChoicePseudoState, Note
- Initial = filled circle, Final = filled circle + outer ring, Choice = diamond
- Recursive layout: innermost composite → layout → freeze → expose boundary gates
- Notes: anchored left/right with folded-corner shape
- Composite external transitions cross boundary gate

Add fixtures: `state-nested-directions.mmd`, `state-composite-entry-exit.mmd`,
`state-self-loop.mmd`, `state-notes-left-right.mmd`, `state-choice.mmd`

Tests:
- One semantic object per declared state
- Initial/final shapes correct (no placeholder text 'i')
- Composite contains every internal descendant
- Note anchored to declared side
- Note doesn't overlap its target
- Internal transitions inside composite
- External transitions cross boundary gate
- Self-loop clears node and label
- Deterministic output

## Task 10 — Theme tokens
**Verification:** Goal-based — grep for hardcoded color values in new paint modules
**Depends on:** Tasks 7 + 8 + 9

Create paint token system in `scripts/mermaid_render/paint/tokens.py`.
Resolve tokens once from theme + supported Mermaid theme variables.
Pass resolved tokens into all painters.

Required tokens: background, primary_fill, primary_border, text, muted_text, edge,
edge_label_bg, group_fill, group_border, note_fill, note_border, external_c4_fill,
c4_boundary_border, arch_service_icon_fill, timeline_section_palette, pseudo_state_fill

## Task 11 — SVG-to-PowerPoint compatibility
**Verification:** TDD — `tests/test_mermaid_svg2pptx_compat.py` all pass
**Depends on:** Tasks 7 + 8 + 9

Create `tests/test_mermaid_svg2pptx_compat.py`.
For every P2 target fixture:
1. Generate native SVG
2. Parse through svg2pptx converter
3. Assert conversion succeeds
4. Assert important text remains text
5. Assert path/shape counts nonzero
6. Assert no unsupported-element warning

## Task 12 — Oracle metrics and galleries
**Verification:** Goal-based — `ppt-output/compare-p2-before/` and `ppt-output/compare-p2-after/` exist
**Depends on:** Tasks 5-9

Generate before/after galleries with full provenance metadata.
Record structural metrics for each P2 fixture (node overlap, edge crossing, etc.).
Update `notes/mermaid-p2-report.md` with after metrics.
