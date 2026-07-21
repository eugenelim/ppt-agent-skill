# Spec: Flowchart Pipeline Finish

**Mode: full (multi-feature, structural change, public interface change)**

- **Status:** Implementing
- **Constrained by:** pure-Python layout rule (no Dagre/ELK/NetworkX/Graphviz/subprocess); enforced in `docs/adr/` once ADR is written — see `docs/backlog.md#adt-pure-python-layout`

## Objective

Finish the migration to one authoritative pure-Python flowchart pipeline so
that `to_html()`, `to_svg()`, `to_png()`, and `validate()` all share one
`_compile_flowchart()` entry point, geometry is deeply immutable after
finalization, the renderer is serialization-only, and `validate()` reports real
geometry errors against a typed IR.

Source brief: `.context/attachments/r6R9nj/pasted_text_2026-07-21_11-08-07.txt`

## Boundaries

**Always do:**
- Use only the existing runtime deps: lxml, Pillow, python-pptx, playwright.
- Keep all 3162 existing tests green throughout the migration.
- Use pure-Python algorithms for all layout (no subprocess calls to layout engines).
- Return `RoutingFailure` objects for any failed route; never silently drop an edge.

**Ask first:**
- Any change to the public `to_html/to_svg/to_png` signatures beyond adding `faithful=False`.
- Any change to sequence / Gantt / pie / packet / journey / XY chart renderers.
- Splitting this into multiple PRs vs landing as one atomic PR.

**Never do:**
- Import networkx, numpy, scipy, shapely, graphviz, pygraphviz, pydot in any `mermaid_render/layout/*.py` file.
- Import subprocess in any layout module.
- Import playwright on the `to_html()` path.
- Add new runtime dependencies.
- Implement full Gansner network-simplex unless the pivot step is complete and tested.

**In scope (diagram types that cut over to `_compile_flowchart()` / `render_finalized()`):**
flowchart, graph, stateDiagram-v2, classDiagram, erDiagram, architecture-beta — all rendered through `_layout_graph_topology`. All six switch to `_compile_flowchart` → `render_finalized()` in this PR.

**Remaining on `_render_graph_fragment()`:** sequence, Gantt, pie, packet, journey, XY chart, C4 — these use their own dedicated renderers and are not changed.

## Acceptance Criteria

- [ ] `to_html()` for flowchart and related diagram types calls `render_finalized()`, not `_render_graph_fragment()`
- [ ] `validate()` performs real geometry checks and reports errors for overlapping nodes, missing routes, groups outside canvas, blocked labels, and all other categories from brief step 5
- [ ] Gallery command exits nonzero when any fixture produces `status == "invalid"`
- [ ] All drawables (nodes, groups, labels, route waypoints, markers) in `FinalizedLayout` are within `canvas_bounds`
- [ ] No parsed edge silently disappears: every edge appears in `routed_edges` or `routing_failures`
- [ ] Blocked labels cause rerouting (label shelf) or produce a `RoutingFailure`
- [ ] Groups are laid out recursively (deepest first); post-hoc separation functions removed
- [ ] `FinalizedLayout.node_layouts` and `.group_layouts` cannot be mutated after construction (`MappingProxyType`)
- [ ] One canvas union and one `dx/dy` translation applied to all drawables; no later geometry mutations
- [ ] `to_html()`, `to_svg()`, `to_png()` accept `faithful=False`; `faithful=True` preserves declared direction and suppresses icon/legend inference
- [ ] Comparison gallery calls `faithful=True`
- [ ] No forbidden runtime import in any `layout/*.py` file
- [ ] All 3162 existing tests pass; all new tests pass

## Testing Strategy

TDD for all new logic:
- `tests/test_pipeline_contract.py` — 10 failing-first tests from Step 1 of brief
- Extend `tests/test_geometry_ir.py` — RoutingFailure, MappingProxyType immutability
- Extend `tests/test_layered_algorithms.py` — IsotonicCoordinateAssigner, SlackTighteningRanker
- `tests/test_validation.py` — validate_finalized_layout with all error categories
- `tests/test_regression_fixtures.py` — 21 geometry fixtures for complex layouts (6 in Task 8 + 15 in Task 11)
- `tests/test_import_boundary.py` — AST import guard for 9 forbidden modules

Goal-based: gallery command exits nonzero on invalid fixture.
Manual QA: `to_html()` renders all 6 in-scope diagram types correctly after pipeline migration.

## Assumptions

1. `render_finalized()` already correctly serializes a `FinalizedLayout` to HTML for the geometry it receives.
2. `_layout_graph_topology()` produces correctly-positioned relative coordinates, but **values will change** when `IsotonicCoordinateAssigner` replaces the legacy coordinate function and post-hoc group separation is removed. Snapshot tests and visual-correctness tests must be re-baselined after the coordinate-assigner switch, not assumed stable.
3. `allocate_face_ports()` can be integrated into `_route_edges()` without changing the routing output for simple (non-parallel, non-overflow) edges.
4. Pool-adjacent-violators (PAV) isotonic projection is ~50 lines of pure Python and produces a valid assignment for the separation constraints in the common case.
5. Existing callers that don't pass `faithful=` continue to work unchanged (default `False`).
6. Cross-group edge routing (LCA-scope boundary port allocation) is in scope for Task 9 routing integration.

## Declined patterns

- Full Gansner network-simplex (true pivot step) — spec says skip unless complete; `SlackTighteningRanker` is the honest rename.
- `LayoutEngine` strategy registry — only one engine exists; no abstraction needed.
- Per-validation-rule configuration flags — one threshold constant is sufficient.
- Splitting into multiple PRs — the DEFINITION OF DONE requires all pieces together; atomicity is justified by the compile-validate-render triad needing to be consistent.
- ADR written inline — deferred to `docs/backlog.md#adt-pure-python-layout` per backlog guidance.
