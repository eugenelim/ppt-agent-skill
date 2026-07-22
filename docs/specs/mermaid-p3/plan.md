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

## Deferred tasks (Stages 6-13 — separate loops)
See docs/backlog.md entries:
- backlog-mermaid-p3-scene-bounds (Stage 5 scene IR hardening)
- backlog-mermaid-p3-type-migrations (Stage 6 twelve placeholder types)
- backlog-mindmap-tidy-tree (Stage 7 mind map tidy-tree)
- backlog-mermaid-p3-timeline (Stage 8 timeline completion)
- backlog-mermaid-p3-architecture (Stage 9 architecture semantics)
- backlog-mermaid-p3-c4 (Stage 10 C4 completion)
- backlog-mermaid-p3-state (Stage 11 state diagrams)
- backlog-mermaid-p3-infra (Stage 12 themes/faithful/sizing/PNG + to_html/validate wiring)
- backlog-mermaid-p3-class-compiler (classDiagram FinalizedLayout compiler)
- backlog-mermaid-p3-semantic-tests (Stage 13 semantic tests + gallery)
