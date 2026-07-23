# Implementation Plan — Mermaid Single Finalized Layout Pipeline

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/er.py`, `scripts/mermaid_render/layout/requirement.py`, `scripts/mermaid_render/layout/architecture.py`, `scripts/mermaid_render/layout/_strategies.py`, `tests/test_single_layout_pipeline.py`
2. Done when: `pytest tests/` passes; `mypy scripts/mermaid_render/` reports zero new errors; `_layout_er`, `_layout_requirement`, `_layout_architecture` no longer exist in `_strategies.py`; `test_er_geometry_roundtrip`, `test_requirement_geometry_roundtrip`, `test_architecture_geometry_roundtrip` all green
3. Not changing: `native_svg.py` dispatch (already calls correct SVG path per type), `finalized_layout_to_scene()` in `paint.py`, `render_finalized()` in `_renderer.py`, `scene_to_svg_str()`, `FinalizedLayout` dataclass, public API signatures for `layout_er_scene`, `layout_requirement_scene`, `layout_architecture_scene`, `compile_architecture`

**Dependency note:** The `elk-finalized-layout-roundtrip` spec should ideally
land before this work begins. That spec hardens `FinalizedLayout` as a stable
serialisation contract (round-trip data attributes, field naming, ELK
coordinate mapping). `compile_er` and `compile_requirement` produce
`FinalizedLayout` directly; if the contract changes under them the roundtrip
tests here will break at integration. If `elk-finalized-layout-roundtrip` is
still open, accept the risk and track it as a known dependency.

**Declined patterns:**
- Tempted to merge `layout_er_scene` and `compile_er` into a single function; declining — keeping them separate preserves the public API and makes the compiler testable in isolation without a full `SvgScene` render
- Tempted to introduce a new abstract base class or protocol for `Compiler`; declining — three concrete compilers with consistent signatures are simpler and already covered by the geometry roundtrip tests
- Tempted to migrate all diagram types (gantt, timeline, etc.) to the shared pipeline in the same PR; declining — scope is ER, requirement, architecture only; other types are a separate effort

## Tasks

### Task 1: `compile_er` — extract parse + layout into a shared compiler
Depends on: none
Verification: goal-based check

**Tests:**
- `test_compile_er_returns_finalized_layout`: call `compile_er` on a minimal two-entity ER fixture; assert return type is `FinalizedLayout`, `node_layouts` contains both entities, `canvas_bounds.w > 0`, `routing_failures == ()`
- `test_compile_er_attribute_rows_preserved_in_metadata`: assert that entity attribute lists survive in `FinalizedLayout` node metadata (semantic data not lost)
- `test_compile_er_non_identifying_edge_style`: assert that a `..` relation produces a `RoutedEdge` with `style == "dashed"` in the finalized edges

**Approach:**
- In `er.py`, extract the parse-and-layout body of `layout_er_scene()` into a new `compile_er(src: str, *, width_hint: int = 0) -> FinalizedLayout` function
- `layout_er_scene()` becomes: `compile_er(src, width_hint=width_hint)` → `finalized_layout_to_scene(...)`; no geometry work left in the painter
- Entity attribute data (the `entity_attrs` dict) must be stored in `FinalizedLayout.node_layouts[eid].semantic_data` so painters can render attribute rows without re-parsing
- `FinalizedLayout.diagnostics` carries crow's-foot cardinality metadata per edge if needed by the SVG painter


### Task 2: `compile_requirement` — extract parse + layout into a shared compiler
Depends on: none
Verification: goal-based check

**Tests:**
- `test_compile_requirement_returns_finalized_layout`: call `compile_requirement` on a minimal fixture with one requirement and one element; assert `FinalizedLayout` returned, both nodes present, `canvas_bounds` non-empty
- `test_compile_requirement_relation_type_preserved`: assert that a `satisfies` relation produces a `RoutedEdge` with `label == "satisfies"`
- `test_compile_requirement_element_shape_in_metadata`: assert that `element` nodes carry `shape == "cylinder"` in their `NodeLayout.semantic_data`

**Approach:**
- In `requirement.py`, extract the parse-and-layout body of `layout_requirement_scene()` into `compile_requirement(src: str, *, width_hint: int = 0) -> FinalizedLayout`
- `layout_requirement_scene()` becomes: `compile_requirement(...)` → `finalized_layout_to_scene(...)`
- Node type (`requirement` vs `element`) and block attributes stored in `NodeLayout.semantic_data` for the SVG painter's header/body rendering
- Orthogonal edge routing must be preserved; verify the `RoutedEdge.waypoints` have at least two points for any node pair not in the same rank


### Task 3: Wire `architecture-beta` HTML path through existing `compile_architecture`
Depends on: none
Verification: goal-based check

**Tests:**
- `test_architecture_html_uses_compile_architecture`: call `to_html()` on an architecture fixture; mock `compile_architecture` to record call count; assert it is called exactly once
- `test_architecture_html_output_non_empty`: smoke-test that `to_html()` still returns a non-empty HTML fragment containing the service label

**Approach:**
- In `_strategies.py`, replace the `_layout_architecture` call at line ~5910 with:
  `from .architecture import compile_architecture, arch_to_finalized` then `compile_architecture(clean, width_hint=width_hint)` → `arch_to_finalized(...)` → `render_finalized(...)`
- Apply the same zoom-wrapper logic currently in `_layout_architecture` using `arch.zoom`
- Do not delete `_layout_architecture` yet — leave it in place as dead code until Task 6 (deletion gate)


### Task 4: Wire ER and requirement HTML paths through new compilers
Depends on: Task 1, Task 2
Verification: goal-based check

**Tests:**
- `test_er_html_uses_compile_er`: call `to_html()` on an ER fixture; assert `compile_er` is invoked (call-count mock or import-path assertion)
- `test_requirement_html_uses_compile_requirement`: same pattern for requirement

**Approach:**
- In `_strategies.py`, replace the `_layout_er(...)` call at line ~5874 with: `from .er import compile_er; fl = compile_er(clean, width_hint=width_hint); return render_finalized(fl)`
- Replace the `_layout_requirement(...)` call at line ~5916 analogously using `compile_requirement`
- Do not delete `_layout_er` or `_layout_requirement` yet


### Task 5: Geometry roundtrip test helper and full coverage
Depends on: Task 1, Task 2, Task 3, Task 4
Verification: TDD

**Tests:**
- `test_er_geometry_roundtrip`: compile a fixture via `compile_er`; render to HTML with `render_finalized`; render to SVG via `layout_er_scene` (which now calls `compile_er` internally); parse `data-node-id`/`data-x`/`data-y`/`data-w`/`data-h` from both; assert all values match within 0.5 px tolerance
- `test_requirement_geometry_roundtrip`: same pattern using `compile_requirement` / `layout_requirement_scene`
- `test_architecture_geometry_roundtrip`: same using `compile_architecture` + `arch_to_finalized` / `layout_architecture_scene`
- `test_er_fix_propagates_to_both_outputs`: mutate a node-width constant in `er.py`, confirm both HTML and SVG reflect the change without touching either painter

**Approach:**
- Create `tests/test_single_layout_pipeline.py`
- Implement `_extract_geometry_attrs(html_or_svg: str) -> dict[str, dict]` helper that parses `data-node-id`, `data-x`, `data-y`, `data-w`, `data-h` from either format using `re` (no BeautifulSoup dependency)
- Each roundtrip test calls the helper on HTML output and SVG output of the same fixture and asserts coordinate equality


### Task 6: Delete legacy HTML-path functions and validate snapshots
Depends on: Task 5
Verification: goal-based check

**Tests:**
- All existing tests in `tests/` pass unchanged (no new test written here — this task is a deletion + gate)
- `grep -r "_layout_er\|_layout_requirement\|_layout_architecture" scripts/` returns empty (functions gone)

**Approach:**
- Delete `_layout_er`, `_layout_requirement`, and `_layout_architecture` from `_strategies.py`
- Run `pytest tests/` and `mypy scripts/mermaid_render/` and confirm clean
- If any snapshot drifts, investigate whether the geometry delta is within floating-point tolerance; update snapshot hashes only if the new output is geometrically correct and the old output was diverged from the shared model
