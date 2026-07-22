# Native SVG Hardening 2026-07 — spec

Mode: full (multi-feature, dependent tasks; structural changes across `_geometry.py`, `native_svg.py`, `__init__.py`; new `errors.py` and `registry.py` modules; new public interfaces; P0 of the post-review hardening document)

**Status:** Shipped

## Objective

Make `mermaid_render`'s native SVG backend semantically trustworthy. Every call to `to_svg()` must produce exactly one of: a validated native SVG, an opt-in legacy-backend result, or a typed error. The backend must never silently return a centered placeholder, a diagram-type label, an empty scene, or a generic token graph while reporting success.

The full hardening spec (phases 1–13) was provided as a session attachment and is reproduced in the Not-in-scope list below for each deferred phase. This PR implements P0 (phases 1–7 priority items) and the pre-existing `NodeLayout.parent_group_id` bug fix.

## Baseline

- HEAD: 9033be7 (feat(sequence): sequenceDiagram rendering fix)
- Python 3.13.13
- Baseline failing test: `tests/test_compare_gallery.py::TestGalleryExitCode::test_no_exit_1_when_all_ok`
- Root cause: `NodeLayout` in `_geometry.py` lacks `parent_group_id` field accessed by `_renderer.py:1667`

## Acceptance Criteria

### Bug Fix — NodeLayout.parent_group_id (Task 0)

- [x] **AC-B.1** `NodeLayout` in `_geometry.py` has field `parent_group_id: Optional[str] = None`.
- [x] **AC-B.2** `_build_node_layouts_ir` in `_strategies.py` populates `parent_group_id` from group membership.
- [x] **AC-B.3** `test_compare_gallery.py::TestGalleryExitCode::test_no_exit_1_when_all_ok` passes.

### Phase 1 — Support registry (Task 1)

- [x] **AC-1.1** `scripts/mermaid_render/registry.py` exports `RendererCapability` (frozen dataclass: `diagram_type`, `native_status` in `{"implemented","legacy-only","unsupported","experimental"}`, `native_builder` callable or None, `validator` callable or None, `semantic_fixture_ids` tuple).
- [x] **AC-1.2** `RENDERER_REGISTRY: dict[str, RendererCapability]` covers all 21 types from spec: architecture, block, C4 (c4context/c4container/c4component), class, ER, flowchart, Gantt, GitGraph, journey, kanban, mindmap, packet, pie, quadrant, requirement, sankey, sequence, state, timeline, xychart, ZenUML.
- [x] **AC-1.3** `get_capability(diagram_type: str) -> RendererCapability` is a public function in `registry.py`.
- [x] **AC-1.4** Registry is importable from `mermaid_render.registry` without side effects.
- [x] **AC-1.5** `mermaid_render.__init__` exports `get_capability` and `RENDERER_REGISTRY`.

### Phase 2 — Remove placeholder success paths (Task 2)

- [x] **AC-2.1** `scripts/mermaid_render/errors.py` exports: `NativeRenderError`, `NativeRendererUnavailable`, `UnsupportedDiagramType`, `UnsupportedDiagramFeature` — all subclass `ValueError` for backward compatibility; structured fields: `diagram_type`, `phase` (for `NativeRenderError`).
- [x] **AC-2.2** `dispatch_native()` for `LEGACY_ONLY` types raises `NativeRendererUnavailable` instead of returning `_html_fallback_scene`.
- [x] **AC-2.3** `dispatch_native()` for `UNSUPPORTED` types raises `UnsupportedDiagramType`. The existing `test_unsupported_sankey_raises` still passes (ValueError match preserved).
- [x] **AC-2.4** Broad `except Exception: return _html_fallback_scene(...)` blocks in class/timeline/mindmap/architecture/C4 are replaced with: re-raise typed errors as-is; wrap unexpected exceptions as `NativeRenderError(diagram_type, phase, cause=e)`. No stub fallback.
- [x] **AC-2.5** `_html_fallback_scene` is gated by `debug_placeholder: bool` parameter defaulting False; called only when caller explicitly requests it.
- [x] **AC-2.6** `to_svg()` in `__init__.py` accepts `fallback: str | None = None`; raises `ValueError` for unknown fallback values; when `fallback="legacy-dom"` and native raises `NativeRendererUnavailable`, routes to the legacy DOM path.
- [x] **AC-2.7** Regression test: inject an unexpected adapter exception into `_graph_topology_scene`, assert `dispatch_native()` raises `NativeRenderError` (not a stub).
- [x] **AC-2.8** `TestStubMigration` updated to expect `NativeRendererUnavailable` for legacy-only types. All other existing `dispatch_native` callers (arch painter, C4 painter, state hierarchy, svg2pptx compat) still pass — experimental builders succeed for their test fixtures.

### Phase 3 — RenderResult contract (Task 3)

- [x] **AC-3.1** `scripts/mermaid_render/registry.py` exports `RenderResult` frozen dataclass with fields: `svg: str | None`, `diagram_type: str`, `backend: str`, `semantic_adapter: Literal["passed","unsupported","failed"]`, `syntax_coverage: Literal["passed","partial","failed"]`, `geometry: Literal["passed","unvalidated","failed"]`, `serialization: Literal["passed","failed"]`, `warnings: tuple[str, ...]`, `errors: tuple[str, ...]`.
- [x] **AC-3.2** `RenderResult.is_success(strict=True)` returns False when `errors` non-empty or SVG is None; in strict mode also requires `semantic_adapter=="passed"`, `syntax_coverage=="passed"`, `geometry=="passed"`, `serialization=="passed"`.
- [x] **AC-3.3** Strict success does NOT allow `geometry="unvalidated"`, `syntax_coverage="partial"`, or backend names ending in `"-stub"`. (Flowchart currently returns `geometry="unvalidated"` until Phase 4 wires validation — this is the correct transient state, not a bug.)
- [x] **AC-3.4** `dispatch_native_result(src, ...) -> RenderResult` is a public function in `native_svg.py`.
- [x] **AC-3.5** `dispatch_native(src, ...) -> str` returns the SVG string whenever one is produced (geometry validation status does not block it); raises typed errors on scene-construction failure.

### Phase 5 (basic) — Finalized-layout edge invariants (Task 4)

- [x] **AC-5.1** `FinalizedLayout.validate()` enforces: `len(routed_edges) + len(routing_failures) == metadata.original_edge_count`.
- [x] **AC-5.2** Every original edge ID is unique.
- [x] **AC-5.3** Every routed edge ID is unique.
- [x] **AC-5.4** Every routing failure ID is unique.
- [x] **AC-5.5** No edge ID appears in both `routed_edges` and `routing_failures`.
- [x] **AC-5.6** Every routed edge has at least two finite, distinct consecutive points.
- [x] **AC-5.7** Tests for each invariant check: one valid case (no violation), one invalid case (violation detected).

### Phase 7 (partial) — Gallery test fix (Task 5)

- [x] **AC-7.1** Gallery test `test_no_exit_1_when_all_ok` passes (fixed by Task 0 / NodeLayout bug).
- [x] **AC-7.2** `_build_gallery()` includes `renderer_backend` check in `has_failures` so stub backends cause exit 1.

**Not in scope (explicitly deferred to follow-up PRs):**
- Phase 5 checks 7-19: orthogonality, port position constraints, group-title reservation, compound containment, label/marker in-canvas, finiteness checks (segment-vs-rectangle intersection is complex geometry)
- Phase 4: Per-type public validation (complex per-type adapter work)
- Phase 6: EndpointRef / compound-boundary endpoints
- Phase 7 complete: Full gallery provenance embedding
- P1 phases 8–13: EdgeIdentity, SVG namespacing, painted bounds, NormalizedLayeredGraph
- P2: Complete native adapters for sequence, ER, etc.
- EXPERIMENTAL `experimental=True` gate (Phase 2 for experimental types only removes stub fallback; the opt-in flag is P1 scope)

## Boundaries

**In scope:**
- `scripts/mermaid_render/layout/_geometry.py` — add `parent_group_id` to `NodeLayout`; strengthen `FinalizedLayout` invariants; add `renderer_backend` to `ValidationResult`
- `scripts/mermaid_render/layout/_strategies.py` — populate `parent_group_id` in `_build_node_layouts_ir`
- `scripts/mermaid_render/layout/_renderer.py` — bundled fix: strip `<br>` from `data-label` attribute to prevent `&lt;br&gt;` leaking into HTML output (pre-existing bug unmasked by `parent_group_id` fix; covered by `TestMultilineBrComprehensive`)
- `scripts/mermaid_render/native_svg.py` — remove placeholder paths, add `dispatch_native_result()`
- `scripts/mermaid_render/errors.py` (new) — typed exceptions
- `scripts/mermaid_render/registry.py` (new) — `RendererCapability`, `RENDERER_REGISTRY`, `RenderResult`
- `scripts/mermaid_render/__init__.py` — expose `get_capability`, `RENDERER_REGISTRY`, update `to_svg()`; populate `renderer_backend` in `validate()`
- `tools/compare_gallery.py` — partial Phase 7 (stub rejection)
- `tests/test_native_svg_backend.py` — update `TestStubMigration` tests
- `tests/test_native_svg_registry.py` (new) — registry, RenderResult, typed error tests
- `tests/test_geometry_invariants.py` (new) — edge invariant tests

**Not in scope (deferred):**
- Phase 4: Per-type public validation beyond flowchart skeleton (complex per-type work)
- Phase 5 complete: Segment-vs-rectangle intersection (complex geometry algorithm, separate PR)
- Phase 6: EndpointRef / compound-boundary endpoints (new design, separate PR)
- Phase 7 complete: Full gallery provenance embedding (separate PR)
- P1 phases 8–13: EdgeIdentity, SVG namespacing, painted bounds, NormalizedLayeredGraph (separate PRs)
- P2: Complete native adapters for sequence, ER, etc. (separate PRs)

## Declined patterns

- **Change `dispatch_native()` return type to `RenderResult`**: breaks existing callers; add `dispatch_native_result()` alongside instead.
- **Implement segment-vs-rectangle intersection in Phase 5**: too complex for this loop; basic edge reconciliation + uniqueness + point validity is the achievable floor.
- **Implement EndpointRef now**: requires compound-layout design decisions; deferred to Phase 6 spec.
- **Add full gallery provenance embedding now**: the provenance collection already has most fields; embedding per-diagram pass/fail is the priority; full spec embedding deferred.

## Testing strategy

TDD for all new logic (registry, errors, RenderResult, invariants).
Goal-based check for gallery fix.
Update `TestStubMigration` tests to expect typed errors after Phase 2.
