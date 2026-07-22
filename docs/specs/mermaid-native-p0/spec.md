# Mermaid Native SVG Backend — P0 Registry Hardening

- **Mode:** full (multi-feature brief; structural change; new abstractions)
- **Status:** Shipped

## Objective

Close the six critical semantic gaps in the native SVG backend that allow
invalid outcomes to pass as success. Implementing spec sections 1-7 (P0 items 2-7).

Baseline (HEAD 578b4c2): clean tree, Python 3.13.13.

Pre-existing issues found:
- `_dispatch_scene()` silently routes unknown directives through the flowchart pipeline (lines 392-402).
- `RENDERER_REGISTRY` entries have `native_builder=None` — not executable from the registry.
- `"graph"` is missing from `RENDERER_REGISTRY` (only in `_GRAPH_DIRECTIVES`).
- `dispatch_native_result()` always returns `geometry="unvalidated"` even for IMPLEMENTED types.
- `to_svg()` calls `dispatch_native()` directly, bypassing `RenderResult`.
- `RenderResult.to_exception()` method does not exist.
- `render_svg_result()` does not exist.
- `CompiledFlowchart.validation` is computed but discarded in `_dispatch_scene()`.
- Two competing registries: `RENDERER_REGISTRY` in `registry.py` and `NATIVE_RENDERER_REGISTRY` in `scene.py`.

## Acceptance Criteria

- [x] AC-1: `render_svg_result("unknown_directive TD\n  A-->B\n")` raises `UnsupportedDiagramType`; `dispatch_native_result` returns error RenderResult with errors populated.
- [x] AC-2: `dispatch_native_result("graph TD\n  A-->B\n")` succeeds (canonical alias: graph→flowchart).
- [x] AC-3: `get_capability("graph")` returns the flowchart entry.
- [x] AC-4: Every `RENDERER_REGISTRY["implemented_type"].native_builder is not None`.
- [x] AC-5: Every `RENDERER_REGISTRY["experimental_type"].native_builder is not None`.
- [x] AC-6: Every `RENDERER_REGISTRY["legacy_type"].native_builder is None`.
- [x] AC-7: `render_svg_result("flowchart TD\n  A-->B\n")` returns `RenderResult` with `geometry="passed"` (not "unvalidated").
- [x] AC-8: `render_svg_result(flowchart)` returns `RenderResult.is_success(strict=True) == True`.
- [x] AC-9: `to_svg("flowchart TD\n  A-->B\n")` succeeds via `render_svg_result()`.
- [x] AC-10: `RenderResult(..., geometry="failed", ...).to_exception()` returns a `NativeRenderError`.
- [x] AC-11: `RenderResult(..., errors=("e",), ...).to_exception()` returns a `NativeRenderError`.
- [~] AC-12: ~~dispatch_native_result and _dispatch_scene agree on classification~~ — RETIRED. `_dispatch_scene` has no callers post-refactor; classification contract is verified through `render_svg_result()` and the registry (ACs 1-8).
- [x] AC-13: Unexpected builder exceptions are wrapped as `NativeRenderError` and preserve `__cause__`.
- [x] AC-14: Existing test suite remains green (no regressions).

## Scope

**In scope:**
- `registry.py`: `DIRECTIVE_ALIASES`, `canonicalize_directive()`, populate `native_builder` + add `geometry_validator`, add `RenderResult.to_exception()`
- `native_svg.py`: `render_svg_result()`, remove flowchart fallback in `_dispatch_scene()`, update `parse_render_request()` to canonicalize
- `__init__.py`: make `dispatch_native_result()` use `render_svg_result()`, make `to_svg()` use `render_svg_result()` and raise on `geometry="failed"`
- `layout/_routing.py`: three routing fixes to eliminate spurious geometry validation failures:
  1. Deduplicate consecutive identical waypoints in `_smooth_orthogonal_path()` (collinear same-column edges)
  2. Skip zero-length L command when a short segment's arc-start equals the previous arc-end (`Q` endpoint)
  3. Align `_est_label_w` with `_make_text_layout_ir` (both use 8px/char) so label routing placement is consistent with the stored bounds width (a residual divergence exists for labels >56 chars due to `_est_label_w`'s 450px cap; `_make_text_layout_ir` has no cap — deferred: `backlog-mermaid-p0-label-width-cap`)
- Tests for all ACs above

## Boundaries

- **Entry points changed**: `to_svg()`, `dispatch_native_result()` (both now delegate to `render_svg_result()`)
- **New public surface**: `render_svg_result()` in `native_svg.py`, exported lazily from `mermaid_render.__init__`
- **New abstractions**: `DIRECTIVE_ALIASES`, `canonicalize_directive()`, `get_capability()` (registry.py); `render_svg_result()`, `_build_graph_pipeline()` (native_svg.py)
- **Behavior change**: `to_svg()` now raises `NativeRenderError(phase="geometry")` for diagrams with failed geometry validation (previously returned the SVG silently)
- **`_dispatch_scene()` preserved**: has no callers after the refactor (dead code), but kept per the declined-pattern register as a low-level entry point; removal is deferred to a separate PR once route tests exist

**Deferred (not in this PR):**
- P0 items 8-9: `original_edge_ids`, `EdgeIdentity`, exact route/port/obstacle validation
- P0 items 10-11: Implemented-renderer geometry validation for statediagram compound states; native SVG gallery lane
- P1-P2: Painted bounds, ID namespacing, endpoint labels, compound-boundary endpoints, typed ClassDiagramIR
- Remove `NATIVE_RENDERER_REGISTRY` from `scene.py` (separate decommission PR, test_native_renderer_capabilities.py depends on it)
- Add `NativeBuildArtifact` dataclass (deferred until Phase 9 pipeline is wired)

## Testing strategy

Verification mode: TDD (pure functions, compressible invariants).

Test files to update/create:
- `tests/test_native_svg_registry.py` — add tests for AC-1 through AC-13
- `tests/test_render_pipeline.py` (new) — integration tests for `render_svg_result()` and the `to_svg()` pipeline

## Declined-pattern register

- Tempted to add `NativeBuildArtifact` (spec Phase 2): declining — adds coupling without Phase 9 validation plumbing, can land when the artifact's validators are populated.
- Tempted to merge `_dispatch_scene()` and `dispatch_native()` into one function: declining — too risky without comprehensive route tests, and removes a useful low-level entry point.
- Tempted to remove `NATIVE_RENDERER_REGISTRY` from `scene.py`: declining — needs its own PR; `test_native_renderer_capabilities.py` depends on it.
- Tempted to require `experimental=True` for experimental builders in the public API: declining — breaks existing callers; experimental gating is deferred to the separate experimental-opt-in spec.
