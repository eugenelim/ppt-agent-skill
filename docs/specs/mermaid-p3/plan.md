# Mermaid P3 — Implementation Plan

- **Status:** Done (Tasks 0-11 complete; Task 10 = Stage 4 recursive compound layout; Task 11 = Stage 5 scene bounds)

## Task 0: Record Baseline
Verification: goal-based
Tests: none (record-only step)
Depends on: none
Done when: `notes/mermaid-native-closeout-report.md` exists with HEAD SHA, Python version, dependency versions, mmdc version, test counts

## Task 1a: Add NativeParityLevel, NativeRendererSpec, capability registry to scene.py
Verification: TDD
stub: true
Tests:
  - `NativeRendererSpec(directive="flowchart", ...)` is frozen (frozen=True enforced by dataclass)
  - Registry contains every currently-handled directive from `_KNOWN_DIRECTIVES`
  - `NATIVE_RENDERER_REGISTRY["flowchart"].parity == NativeParityLevel.PARTIAL`
  - `NATIVE_RENDERER_REGISTRY["sankey-beta"].parity == NativeParityLevel.UNSUPPORTED`
  - `NATIVE_RENDERER_REGISTRY["sequencediagram"].parity == NativeParityLevel.NOT_IMPLEMENTED` (raises, will implement in Stage 6)
  - `NativeParityLevel` has members: FULL, PARTIAL, NOT_IMPLEMENTED, UNSUPPORTED
Depends on: none

## Task 1b: Create tests/test_native_renderer_capabilities.py
Verification: TDD (stub-then-fill)
stub: true
Tests:
  - Iterates all `NativeParityLevel.FULL` or `PARTIAL` directives and asserts:
    - `renderer_backend != "native-svg-stub"`
    - accessibility description does not contain "mechanical stub"
    - output contains more than just background + type label
    - source labels present in SVG for non-empty source
  - `NativeParityLevel.NOT_IMPLEMENTED` directives raise `NativeRenderError` on `to_svg()` call
  - `NativeParityLevel.UNSUPPORTED` directives raise on `to_svg()` call
  - (Note: stub test initially fails for FULL/PARTIAL types — becomes green after Task 3+6+7)
Depends on: Task 1a

## Task 2: Add NativeRenderError typed exception
Verification: TDD
Tests:
  - `NativeRenderError` carries `diagram_type`, `phase`, `semantic_id`, `cause`
  - Is a subclass of ValueError (for backward compat with existing callers)
  - str(error) includes diagram_type and phase
Depends on: none

## Task 3: Remove _html_fallback_scene and fix silent exception fallbacks
Verification: TDD + goal-based
Tests (test_no_native_stubs.py):
  - Static: `_html_fallback_scene` absent from `native_svg.py` source text
  - Static: `native-svg-stub` absent from `native_svg.py` source text
  - Static: `mechanical stub` absent from `native_svg.py` source text
  - Static: no `except Exception:` in native builder wrappers
  - Monkeypatching each diagram builder (timeline, mindmap, architecture, C4) to raise ValueError
    → exception propagates, contains diagram_type, no placeholder returned
  - `to_svg("sequenceDiagram\nA->>B: hello")` raises NativeRenderError (not-implemented phase)
  - `to_svg` with MERMAID_RENDER_SVG_BACKEND=native-svg-stub raises (no such backend)
Depends on: Task 2
Approach: Delete `_html_fallback_scene`. Replace each wrapper:
  - Wrappers with `_html_fallback_scene(src, "TYPE", width_hint)` → `raise NativeRenderError(diagram_type="TYPE", phase="not-implemented")`
  - Remove `except Exception` from classDiagram (re-raise), timeline, mindmap, architecture, C4 wrappers
  - Unknown directives in dispatch_native → `raise NativeRenderError(diagram_type=directive, phase="dispatch", cause=..., semantic_id="unknown")`

## Task 4: Add RenderRequest frozen dataclass and parse_render_request()
Verification: TDD
Tests (tests/test_render_request.py):
  - `parse_render_request(src)` detects directive correctly from various sources
  - frontmatter block in `src` → `request.frontmatter` contains parsed values
  - `request.clean_source` contains no frontmatter block
  - `parse_render_request(src, theme="dark")` → `request.theme == "dark"`
  - `parse_render_request(src, faithful=True)` → `request.faithful is True`
  - same input + options → same request (determinism/byte stability)
Depends on: none (parallel with Task 3)
Approach: add `RenderRequest` dataclass to `native_svg.py`; implement `parse_render_request`.

## Task 5: Wire RenderRequest through dispatch_native and to_svg
Verification: goal-based + test assertion
Tests:
  - `to_svg(src, theme="dark")` does not raise (call path verified; byte-different assertion deferred: backlog-mermaid-p3-infra)
  - `to_svg(src, faithful=True)` request has `faithful=True` in the RenderRequest passed to builder
  - Existing flowchart fixture tests still pass
Depends on: Task 4
Approach: update `dispatch_native()` signature to accept `faithful` + `theme`; call `parse_render_request()`.
         Update `__init__.py::to_svg()` to pass them through.

## Task 6: Implement finalized_layout_to_scene()
Verification: TDD
stub: true
Tests (tests/test_finalized_layout_scene.py):
  - Given minimal FinalizedLayout (1 node, 1 edge) → SvgScene with correct layers populated
  - `NodeLayout.outer_bounds` → SceneRect at matching x,y,w,h in nodes layer
  - `RoutedEdge.waypoints` → ScenePath in edges layer
  - Title text → SceneText in labels layer
  - `NodeLayout.title_layout` → text appears in SVG output
  - `RoutedEdge.has_marker_end=True` → marker definition in scene.definitions
  - `GroupLayout.boundary_bounds` → group boundary rect in boundaries layer
  - Field-coverage value-presence test: for each field of NodeLayout + RoutedEdge, assert its
    *value from the test fixture* is observable in the emitted SvgScene (e.g. outer_bounds.x appears
    as a SceneRect.x, title_layout text appears in SceneTextLine.text, marker fields produce
    MarkerDefinition entries, accent_color appears as fill color). No hand-maintained set — each
    field is individually verified to survive serialization.
  - Monkeypatching layout/routing functions after `_compile_flowchart()` call → serialization still succeeds (proves painting is serialization-only)
  - Deterministic: same input → same bytes
Depends on: Task 3
Approach: add `finalized_layout_to_scene(layout, *, diagram_type, title, tokens, metadata) -> SvgScene`
         to `paint.py`. Consume every FinalizedLayout field; emit scene elements.
         This replaces `graph_to_scene()` on the native path.

## Task 7: Wire finalized_layout_to_scene into native _GRAPH_DIRECTIVES path
Verification: goal-based + existing tests
Tests:
  - Existing flowchart + stateDiagram fixture tests render without error
  - `grep -c "graph_to_scene" scripts/mermaid_render/native_svg.py` → 0
  - `grep -c "_graph_topology_scene" scripts/mermaid_render/native_svg.py` → 0 (function removed)
  - classDiagram still goes through `_class_topology_scene` (not wired through finalized path yet)
Depends on: Task 6
Approach: In `dispatch_native()`, replace the `d in _GRAPH_DIRECTIVES` branch:
  ```python
  compiled = _compile_flowchart(clean, ...)
  scene = finalized_layout_to_scene(compiled.layout, ...)
  ```
  Delete `_graph_topology_scene()` function. Keep `_class_topology_scene()`.
  Note: classDiagram cutover deferred (backlog-mermaid-p3-class-compiler).
  Note: Task 3 already removed the unknown-directive fallback to `_graph_topology_scene`
  at dispatch_native:539, so the grep=0 check is achievable without touching that line.

## Task 8: Static completion checks (finalize test_no_native_stubs.py)
Verification: goal-based
Tests: all static assertions in test_no_native_stubs.py pass including:
  - Playwright import isolation: monkeypatch playwright to raise → `to_svg()` all supported fixtures succeed
Done when: full `test_no_native_stubs.py` green
Depends on: Tasks 3, 5, 7

## Task 9: Fix parent_group_id test coverage in test_finalized_layout_scene.py
Verification: goal-based
Tests: test_node_layout_field_coverage_reflective passes
Depends on: none
Done when: `parent_group_id` added to `_DECLARED_NON_CONSUMED`
Approach: Document as layout hierarchy metadata, not a visual element.

## Task 10: Stage 4 — Recursive compound layout
Verification: TDD + goal-based
Tests (tests/test_compound_layout.py):
  - test_descendants_inside_ancestors: nodes in a group are within its bbox
  - test_sibling_groups_no_overlap: two sibling groups have non-overlapping bboxes
  - test_inner_dir_lr_in_tb_outer: LR group in TB outer places members horizontally
  - test_nested_group_unit_treatment: child group treated as unit in parent's layout
  - test_deterministic_compound_output: same input → same canvas dimensions
  - test_no_rank_flattening: LR group members have DIFFERENT y positions (not flattened)
Depends on: Task 9
Approach:
  - Add `_recursive_group_layout()` to `_strategies.py`
  - Remove rank-flattening hack from `_compile_flowchart`
  - Replace `_apply_inner_direction_positions` call in `_compile_flowchart` with `_recursive_group_layout`
    (`_group_coherent_cols` and `_compact_group_columns` remain as prerequisite col-assignment passes)
  - Update imports in `_strategies.py`

## Task 11: Stage 5 — Scene bounds hardening
Verification: TDD
Tests (tests/test_scene_bounds.py):
  - element_visible_bounds for all 10 element types
  - _parse_translate: comma/space/single-arg/empty/unrecognised
  - scene_visible_bounds: single element, multi-element union, empty → None, multi-layer
  - validate_scene: clean scene, duplicate element_id, nested duplicate, blank ids OK,
    negative width/height, negative radius, nested negative geometry
Done when: 50 tests pass
Approach:
  - New module `scripts/mermaid_render/scene_bounds.py`
  - Imports Rect/Point from layout/_geometry; imports scene types from scene.py (no circular deps)
  - element_visible_bounds: dispatches on element type, parses translate() from transform str
  - arc command endpoint: (cmd[6], cmd[7]) per ScenePath docstring ("A", rx,ry,xr,lf,sf,x,y)
  - text bounds: per-line width estimate from len*font_size*0.6, respects text_anchor
  - group bounds: recursive children union + translate parent transform on top
  - scene_visible_bounds: union across all layers
  - validate_scene: duplicate element_ids + negative geometry on rects/circles/ellipses

## Stage 6 — Twelve placeholder types → real scene builders

### Task 12: Wave A — pie, packet-beta, kanban, journey
Verification: TDD
Tests (tests/test_type_migrations.py — Wave A section):
  - `layout_pie_scene("pie\n  \"A\": 60\n  \"B\": 40")` returns SvgScene with diagram_type="pie"
  - Arc paths present in scene for each slice; slice count matches entry count
  - Labels "A" and "B" appear in the scene's label elements
  - `pie showData` flag present in rendered SVG (accessibility description or data-attr)
  - `layout_packet_scene` parses `0-N: "label"` and `+N: "label"` forms; each field produces a rect
  - All field labels appear in scene text elements
  - Field widths are proportional to their bit span
  - `layout_kanban_scene` produces one column element per column, one card per task
  - Column headers appear in text elements; task labels appear in text elements
  - `layout_journey_scene` produces one bar per task; task labels appear in text
  - Score colour coding: score 1-2 → red-ish, 4-5 → green-ish (different fill colours)
  - All four types: deterministic (same input → same scene bytes), no NativeRenderError raised
Depends on: Task 11
Approach:
  - `layout/pie.py` — parse `"label": value` + optional `showData`/`title`; compute angles;
    draw arcs with ScenePath ("A" command); legend text labels in LAYER_LABELS
  - `layout/packet.py` — parse `start-end: "label"` + `+N: "label"`; draw SceneRect per field
    proportional to bit span; field labels centered in LAYER_LABELS
  - `layout/kanban.py` — parse indented columns + task nodes; draw column header SceneRoundedRect
    + per-card SceneRoundedRect stack in LAYER_NODES; labels in LAYER_LABELS
  - `layout/journey.py` — parse title + sections + `task: score: actor, ...`; draw section bands
    in LAYER_BACKGROUND; task rows as colored SceneRect bars in LAYER_NODES; score dot overlay

### Task 13: Wave B — gantt, quadrantChart, xychart-beta, gitGraph
Verification: TDD
Tests (tests/test_type_migrations.py — Wave B section):
  - `layout_gantt_scene` parses sections+tasks; each task produces a horizontal bar in scene
  - Task labels appear in text elements; section headers appear in text elements
  - All bars fit within canvas width; relative dates (`after <id>`) resolved to pixel offsets
  - `layout_quadrant_scene` parses x-axis/y-axis labels + `Name: [x, y]` data points
  - Data point labels appear in scene; grid lines present (4 quadrant dividers)
  - `layout_xychart_scene` parses x-axis categories + y-axis range + bar data
  - Bars present in nodes layer; category labels appear; bar heights scale to y range
  - `layout_gitgraph_scene` parses commits + branches + merges
  - Each commit produces a circle element; each branch produces a lane line; merge lines present
  - Branch names appear in text elements; commit ids (first 6 chars) appear in text elements
  - All four types: deterministic, no NativeRenderError raised
Depends on: Task 11
Approach:
  - `layout/gantt.py` — parse dateFormat + section + task lines; resolve dates to float days;
    draw task bars in LAYER_NODES, section bands in LAYER_BACKGROUND, axis in LAYER_EDGES
  - `layout/quadrant.py` — parse axes + quadrant labels + `Name: [x,y]` points;
    draw 4-quadrant grid in LAYER_EDGES; scatter circles in LAYER_NODES; labels in LAYER_LABELS
  - `layout/xychart.py` — parse x-axis + y-axis + bar/line series; draw bar rects in LAYER_NODES;
    line path in LAYER_EDGES; axis lines + labels in LAYER_OVERLAYS
  - `layout/gitgraph.py` — parse commit/branch/checkout/merge operations; assign lane per branch;
    draw horizontal lane lines in LAYER_EDGES; commit circles in LAYER_NODES; labels in LAYER_LABELS

### Task 14: Wave C — sequenceDiagram, erDiagram, block-beta, requirementDiagram
Verification: TDD
Tests (tests/test_type_migrations.py — Wave C section):
  - `layout_sequence_scene` parses participants + messages; lifeline count = participant count
  - Actor names appear in text elements; message labels appear in text elements
  - Messages are SceneLine or ScenePath elements in LAYER_EDGES connecting correct lifeline columns
  - `layout_er_scene` parses entities + attributes + relationships
  - Entity names appear as text elements; entity boxes as SceneRect in LAYER_NODES
  - Relationship labels appear in text elements; edges connect entity boxes (SceneLine in LAYER_EDGES)
  - `layout_block_scene` parses `columns N` + block rows; each block produces a SceneRect
  - Block labels appear in text elements; `A --> B` produces an edge in LAYER_EDGES
  - `layout_requirement_scene` parses requirement/element nodes + relation edges
  - Node labels appear in text elements; relation edges present in LAYER_EDGES
  - All four types: deterministic, no NativeRenderError raised
Depends on: Task 11
Approach:
  - `layout/sequence.py` — parse `participant`, `->>`, `-->>` + `Note over`; assign participant x positions;
    draw actor boxes in LAYER_NODES, lifeline dashed lines in LAYER_EDGES, message arrows in LAYER_OVERLAYS
  - `layout/er.py` — parse entity blocks + relationship lines; arrange entities in rows;
    draw entity header + attribute list in LAYER_NODES; edges in LAYER_EDGES with cardinality markers
  - `layout/block.py` — parse `columns N` + block grid rows; compute cell positions;
    draw block rects in LAYER_NODES; arrow edges in LAYER_EDGES
  - `layout/requirement.py` — parse requirement/functionalRequirement/element blocks + relation lines;
    assign grid positions; draw requirement boxes in LAYER_NODES; relation edges in LAYER_EDGES

### Task 15: Wire all builders into native_svg.py + update scene registry
Verification: goal-based
Tests:
  - `dispatch_native(src)` succeeds (no exception) for all 12 type fixtures
  - `NATIVE_RENDERER_REGISTRY[d].parity == NativeParityLevel.PARTIAL` for all 12 types
  - `_NOT_IMPLEMENTED_DIRECTIVES` frozenset is empty (or removed)
Done when:
  - Each `_X_scene()` function calls the corresponding `layout_X_scene()` instead of raising
  - `_NOT_IMPLEMENTED_DIRECTIVES` frozenset made empty (all 12 removed)
  - `dispatch_native`'s `elif d in _NOT_IMPLEMENTED_DIRECTIVES: raise` removed; the `else:` clause
    now routes through `_dispatch_scene(clean, d, direction, width_hint, height_hint)` so all 12
    new types reach their builders via the existing `_dispatch_scene` routing table
  - Dead docstring lines about "phase=not-implemented" updated/removed
  - Registry entries updated from NOT_IMPLEMENTED → PARTIAL with feature lists
  - Waves run serially (A→B→C); tasks 12/13/14 all write to the same test file
Depends on: Tasks 12, 13, 14
Note: `_dispatch_scene` already routes all 12 types to their `_X_scene()` wrappers.
      `dispatch_native` bypasses `_dispatch_scene` for the 6 already-implemented types
      (graph, class, timeline, mindmap, architecture, c4) to thread `faithful`/`opts` through.
      The clean fix is: `else: scene = _dispatch_scene(clean, d, direction, width_hint, height_hint)`
      instead of raising, so the 12 new types route through the existing table.

### Task 16: Update all test files asserting NOT_IMPLEMENTED for new PARTIAL types
Verification: goal-based
Tests: full pytest suite passes with no regressions on the 4 affected test files
Done when:
  - `test_native_renderer_capabilities.py`: `test_registry_contains_not_implemented_directives`
    updated to expect empty set; `test_not_implemented_directives_raise_native_render_error`
    removed/repurposed; new parametrized tests for 12 PARTIAL types added
  - `test_no_native_stubs.py`: `test_not_implemented_directive_raises_native_render_error`
    parametrize list emptied (all 12 types removed)
  - `test_native_svg_backend.py`: `TestLegacyOnlyTypes` updated to remove the 12 types
    from its not-implemented expectations
  - `test_native_svg_registry.py`: `test_no_fallback_legacy_raises_native_render_error` and
    `test_fallback_legacy_dom_catches_not_implemented` updated for new PARTIAL types
  - `test_type_migrations.py` is green for all 12 fixture files
Depends on: Task 15

### Task 17: Update spec.md status + backlog anchor for Stage 6 completion
Verification: goal-based (lint-spec-status.py passes)
Done when:
  - spec.md line 115 flipped from `- [ ]` to `- [x]`, `(deferred: ...)` marker removed
  - spec.md Status updated to include Stages 0-6 done
  - docs/backlog.md `backlog-mermaid-p3-type-migrations` entry marked complete
Depends on: Task 16

## Deferred tasks (Stages 7-12 — implemented in separate loops)
Previously deferred, now complete:
- backlog-mermaid-p3-type-migrations (Stage 6 twelve placeholder types) ✓
- backlog-mindmap-tidy-tree (Stage 7 mind map tidy-tree) ✓
- backlog-mermaid-p3-timeline (Stage 8 timeline completion) ✓
- backlog-mermaid-p3-architecture (Stage 9 architecture semantics) ✓
- backlog-mermaid-p3-c4 (Stage 10 C4 completion) ✓
- backlog-mermaid-p3-state (Stage 11 state diagrams) ✓
- backlog-mermaid-p3-infra (Stage 12 themes/faithful/sizing/PNG + to_html/validate wiring) ✓

Still deferred (outside Stage 13 scope):
- backlog-mermaid-p3-class-compiler (classDiagram FinalizedLayout compiler)

## Task 13: Semantic tests and gallery (Stage 13)
Verification: TDD + goal-based
Depends on: all previous tasks complete
Tests:
  - Task A: _REGISTRY_SEMANTIC_PARAMS in test_native_renderer_capabilities.py — parameterized
    over every PARTIAL/FULL registry entry; source_label_present, node_count, shape_role
  - Task B: _FIXTURE_MATRIX — 22 gallery fixtures across 19 diagram types
  - Task C: test_svg_pptx_compat.py — SVG embed path via SvgConverter; no crash, zero errors
  - Task D: fixture_results in compare_gallery.py metadata.json; test_compare_gallery.py asserts
  - Task E: oracle cases carry source_sha256 after capture-reference recapture
Done when:
  - pytest tests/ -x -q passes
  - spec.md Stage 13 marked [x]
  - spec Status updated to "Done (Stages 0-13)"
