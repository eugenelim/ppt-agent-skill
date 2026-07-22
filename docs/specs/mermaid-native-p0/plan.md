# Plan: Mermaid Native SVG Backend — P0 Registry Hardening

Status: Done

## Tasks

### Task 1: Directive aliasing + canonical normalization
Depends on: none
Touches: scripts/mermaid_render/registry.py, scripts/mermaid_render/native_svg.py

Add `DIRECTIVE_ALIASES` and `canonicalize_directive()` to `registry.py`.
Update `parse_render_request()` in `native_svg.py` to call `canonicalize_directive()`.
Update `get_capability()` to use canonical form (raise `UnsupportedDiagramType` for unknown).
Add "graph" → "flowchart" to the alias map; add "graph" as an entry in `RENDERER_REGISTRY`.

Tests:
- `test_canonicalize_directive_graph_maps_to_flowchart`
- `test_canonicalize_directive_unknown_returns_same`
- `test_get_capability_graph_returns_flowchart_entry`
- `test_get_capability_unknown_raises_unsupported_diagram_type`
- `test_parse_render_request_graph_canonical_is_flowchart`

Done when: `get_capability("graph")` returns flowchart entry; `get_capability("xyz123")` raises `UnsupportedDiagramType`.

### Task 2: Remove unknown-directive flowchart fallback
Depends on: Task 1
Touches: scripts/mermaid_render/native_svg.py

Remove lines 392-402 in `_dispatch_scene()` (the `else:` flowchart fallback).
Replace with `raise UnsupportedDiagramType(d)`.

Tests:
- `test_dispatch_scene_unknown_raises_unsupported` — NOT WRITTEN. `_dispatch_scene()` has no callers after the refactor; the functional coverage (unknown directive → UnsupportedDiagramType) is provided by `test_render_svg_result_unknown_raises_unsupported` in `test_render_pipeline.py` via `render_svg_result()`.

Done when: `_dispatch_scene("unknown_directive TD\n  A-->B\n", "unknown_directive", "TB", 0, 0)` raises `UnsupportedDiagramType`.

### Task 3: Populate native_builder in RENDERER_REGISTRY
Depends on: Task 1
Touches: scripts/mermaid_render/registry.py

Add `geometry_validator: Optional[Callable] = None` field to `RendererCapability`.
Populate `native_builder` and `geometry_validator` for IMPLEMENTED types (flowchart, statediagram-v2, statediagram).
Populate `native_builder` (no geometry_validator) for EXPERIMENTAL types.
LEGACY_ONLY and UNSUPPORTED entries keep `native_builder=None`.

Note: builders use lazy imports to avoid circular imports. Signature: `Callable[[RenderRequest], tuple[SvgScene, ValidationResult | None]]`.

Tests:
- `test_implemented_entries_have_native_builder`
- `test_implemented_entries_have_geometry_validator`
- `test_experimental_entries_have_native_builder`
- `test_legacy_entries_have_no_native_builder`
- `test_unsupported_entries_have_no_native_builder`

Done when: all registry assertions pass.

### Task 4: Add RenderResult.to_exception()
Depends on: none
Touches: scripts/mermaid_render/registry.py

Add `to_exception()` method to `RenderResult` that returns a typed error:
- `errors` non-empty → `NativeRenderError(diagram_type, "pipeline", cause=...)`
- `geometry="failed"` → `NativeRenderError(diagram_type, "geometry")`
- `svg is None` → `NativeRenderError(diagram_type, "build")`
- Otherwise (unexpected) → `NativeRenderError(diagram_type, "unknown")`

Tests:
- `test_to_exception_errors_field`
- `test_to_exception_geometry_failed`
- `test_to_exception_svg_none`

Done when: all to_exception assertions pass.

### Task 5: Add render_svg_result() and wire geometry validation
Depends on: Tasks 1, 2, 3, 4
Touches: scripts/mermaid_render/native_svg.py

Add `render_svg_result(src, *, theme, width_hint, height_hint, faithful, fallback, experimental) -> RenderResult`.

Pipeline:
1. `parse_render_request(src, ...)`
2. `canonicalize_directive(request.directive)` → look up capability
3. Route by capability.native_status:
   - "unsupported" → raise `UnsupportedDiagramType`
   - "legacy-only" → raise `NativeRendererUnavailable`
   - "implemented"/"experimental" → call `cap.native_builder(request)` → `(scene, validation)`
4. Derive geometry: `"passed"` if validation is not None and no errors; else `"failed"` if errors; else `"unvalidated"`
5. IMPLEMENTED: `semantic_adapter="passed"`, `syntax_coverage="passed"`
   EXPERIMENTAL: `semantic_adapter="unsupported"`, `syntax_coverage="partial"`, geometry forced `"unvalidated"`
6. Serialize scene → svg_str
7. Wrap unexpected exceptions as `NativeRenderError(..., cause=e)`

Tests:
- `test_render_svg_result_flowchart_strict_success`
- `test_render_svg_result_flowchart_geometry_passed`
- `test_render_svg_result_unknown_raises_unsupported`
- `test_render_svg_result_legacy_raises_unavailable`
- `test_render_svg_result_experimental_has_partial_syntax`
- `test_render_svg_result_builder_exception_wraps_cause`

Done when: `render_svg_result("flowchart TD\n  A-->B\n").is_success(strict=True) == True`.

### Task 6: Make to_svg() and dispatch_native_result() consume render_svg_result()
Depends on: Task 5
Touches: scripts/mermaid_render/__init__.py

Update `dispatch_native_result()` to call `render_svg_result()` internally, catching exceptions and returning error RenderResult.

Update `to_svg()` to call `render_svg_result()` and either return the SVG or raise:
- Preserve `NativeRenderError(phase="not-implemented")` exception type for legacy-only types (backward compat).
- Geometry-failed gate: `if result.geometry == "failed": raise result.to_exception()`. Experimental/unvalidated results return SVG without raising (they never claim passed geometry).

Tests:
- `test_to_svg_uses_render_svg_result_pipeline` (to_svg returns SVG via geometry-passed path)
- `test_to_svg_geometry_failed_raises` (headline behavior: to_svg raises NativeRenderError(phase="geometry") on validation failure)
- `test_dispatch_native_result_flowchart_geometry_passed`
- `test_dispatch_native_result_graph_alias_succeeds` (AC-2: graph alias → flowchart strict success)
- `test_dispatch_native_result_unknown_directive_returns_error_result`
- Regression: `test_no_fallback_legacy_raises_native_render_error` still passes

Done when: all existing + new tests pass.
