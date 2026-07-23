# Mermaid Single Finalized Layout Pipeline

Mode: full (structural change, multi-feature, dependent tasks)

- **Status:** Shipped

## Objective

Eliminate the independent HTML and SVG layout implementations for `erDiagram`,
`requirementDiagram`, and `architecture-beta` diagrams.

Currently each of these three diagram types maintains two separate
parse-and-layout paths: one inside `_strategies.py` that emits an HTML
fragment for `to_html()`, and one inside `er.py` / `requirement.py` /
`architecture.py` that emits an `SvgScene` for `to_svg()`. A geometry fix
in one path does not propagate to the other.

The target design is one pipeline per type:

```
source
  → compile_*(source, **opts)   → typed compiled model (FinalizedLayout)
  → render_finalized()          → HTML fragment
  → finalized_layout_to_scene() → SvgScene
```

Both painters consume the same compiled model; neither may recalculate node
bounds, group bounds, edge waypoints, port assignments, or label positions.

## Boundaries

**In scope:**
- `scripts/mermaid_render/layout/er.py` — add `compile_er()`
- `scripts/mermaid_render/layout/requirement.py` — add `compile_requirement()`
- `scripts/mermaid_render/layout/architecture.py` — `compile_architecture()` already exists; add `arch_to_html()` bridge
- `scripts/mermaid_render/layout/_strategies.py` — replace `_layout_er`, `_layout_requirement`, `_layout_architecture` with compiler calls; delete dead code after tests pass
- `scripts/mermaid_render/native_svg.py` — no structural change needed; `_er_scene`, `_requirement_scene`, `_architecture_scene` already call the correct SVG path
- `tests/test_single_layout_pipeline.py` — new test file with geometry roundtrip helper
- Semantic metadata preserved on `FinalizedLayout` nodes and edges

**Out of scope:**
- Other diagram types (flowchart, classdiagram, sequence already share a compiled model)
- P4 repository reorganisation
- ELK integration for ER or requirement layout (these use Sugiyama / BFS rank assignment)
- Changes to `to_png()`, `validate()`, or `parse_render_request()`
- New production dependencies

## Acceptance Criteria

- [ ] AC1: `compile_er(src, *, width_hint: int = 0) -> FinalizedLayout` exists in `er.py`; `to_html()` for `erDiagram` calls it and passes the result to `render_finalized()`; `layout_er_scene()` calls it and passes the result to `finalized_layout_to_scene()`
- [ ] AC2: `compile_requirement(src, *, width_hint: int = 0) -> FinalizedLayout` exists in `requirement.py`; `to_html()` for `requirementDiagram` and `layout_requirement_scene()` both call it
- [ ] AC3: `to_html()` for `architecture-beta` is wired through `compile_architecture()` → `arch_to_finalized()` → `render_finalized()`; the standalone `_layout_architecture()` function is removed from `_strategies.py`
- [ ] AC4: `_layout_er()` and `_layout_requirement()` are deleted from `_strategies.py` after the HTML path is re-wired
- [ ] AC5: HTML and SVG outputs for all three diagram types expose identical node bounds, group bounds, edge waypoints, port positions, and label bounds — verified by `test_single_layout_pipeline.py` extracting `data-*` geometry attributes from both serializations
- [ ] AC6: A geometry fix applied to `compile_er`, `compile_requirement`, or `compile_architecture` appears in both `to_html()` and `to_svg()` output without touching either painter
- [ ] AC7: Public APIs preserved and backward compatible: `layout_er_scene(src, *, width_hint)`, `layout_requirement_scene(src, *, width_hint)`, `layout_architecture_scene(src, *, width_hint)`, `compile_architecture(src, *, width_hint)` — all still importable and return the same types as today
- [ ] AC8: Semantic category data (entity attributes for ER, requirement/element type for requirement, service/junction/group metadata for architecture) is preserved as immutable metadata attached to finalized nodes and edges rather than recomputed by the painters
- [ ] AC9: `mypy` reports zero new errors versus the pre-change baseline
- [ ] AC10: All existing snapshot and semantic tests pass unchanged after the refactor

## Testing Strategy

**Geometry roundtrip tests** (`tests/test_single_layout_pipeline.py`):
Each test compiles a fixture once via `compile_*()`, renders to HTML via
`render_finalized()`, renders to SVG via `finalized_layout_to_scene()` +
`scene_to_svg_str()`, extracts the `data-node-id` / `data-x` / `data-y` /
`data-w` / `data-h` attributes from the HTML fragment, and the corresponding
`data-*` attributes from the SVG, and asserts they are numerically identical.
This proves the single-layout invariant mechanically.

**Unit tests** for each new compiler (`compile_er`, `compile_requirement`)
assert:
- Returns a `FinalizedLayout` instance
- `node_layouts` contains an entry for every entity/requirement/service in the fixture
- `canvas_bounds` is non-empty
- No `routing_failures`

**Backward-compatibility smoke tests** confirm that after re-wiring,
`to_html()` and `to_svg()` return non-empty strings for a minimal fixture of
each type — no regressions in the public surface.

**Deletion gate**: the dead-code deletion task (removing `_layout_er`,
`_layout_requirement`, `_layout_architecture`) runs last; all gates must pass
before deletion is committed.
