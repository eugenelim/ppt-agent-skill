# Mermaid Trustworthiness Pass — Strict API + Single Registry

**Mode: full (multi-feature + dependent tasks + structural change + public interface change)**

- **Status:** Shipped

## Objective

Make the public native SVG API truthful. Every call to `to_svg()` must produce exactly one of:
a validated strict native SVG (for IMPLEMENTED types), an explicit experimental opt-in SVG, an explicit legacy fallback, or a typed error. Experimental renderers must never surface as ordinary production success.

Simultaneously, eliminate the independent second capability table (`scene.NATIVE_RENDERER_REGISTRY`) so that there is exactly one authoritative source of truth for which diagram types are supported and at what status.

Baseline HEAD: d1c38622b4f671a2e9209eac96620c6c4b9f1e50
Reviewed baseline from attachment: 87c56e8dd36be0f3fed072cd167a42771fc967ae

## Boundaries

**In scope:**
- `scripts/mermaid_render/errors.py` — add `ExperimentalOptInRequired`
- `scripts/mermaid_render/registry.py` — update `RenderResult.semantic_adapter` Literal; update `to_exception()`
- `scripts/mermaid_render/native_svg.py` — set `semantic_adapter="partial"` for experimental in `render_svg_result()`
- `scripts/mermaid_render/__init__.py` — add `strict`/`experimental` params to `to_svg()` and `to_png()`
- `scripts/mermaid_render/__main__.py` — pass `experimental=True` in CLI (developer tool)
- `scripts/mermaid_render/scene.py` — make `NATIVE_RENDERER_REGISTRY` a derived view of `RENDERER_REGISTRY`
- `tests/test_native_renderer_capabilities.py` — update callers of experimental types
- `tests/test_native_svg_registry.py` — update callers of experimental types
- `tests/test_render_pipeline.py` — update callers of experimental types
- `tests/fidelity/adapters/native_svg.py` — use `experimental=True`
- `tests/test_mermaid_trustworthiness.py` (new) — regression tests for Phase 1 and 2

**Out of scope (explicitly deferred):**
- Changing builder signatures to return `NativeBuildArtifact` (own session, touches all builders)
- Adding `semantic_validator`/`supported_features`/`unsupported_features` to `RendererCapability` (per-type work)
- Renaming `native_status` → `status` or `native_builder` → `builder` (breaks too many tests)
- `NativeBuildArtifact` dataclass (will be defined but not wired)
- Phases 3–14 from the attachment spec (separate sessions)
- Changing `dispatch_native()` behavior — it returns SVG for any buildable type regardless of strictness
- Changing `dispatch_native_result()` behavior — already returns `RenderResult` with all lanes

## Baseline (pre-change)

- 1 failing test: `test_fixture_capability_matrix[architecture-beta/architecture-basic.mmd]`
  - Root cause: test expects label `"api"` but SVG renders label `"API Gateway"` (case-sensitive mismatch)
- `to_svg()` returns SVG for experimental types (geometry="unvalidated") — silent partial success
- `NATIVE_RENDERER_REGISTRY` in `scene.py` is an independent hand-maintained table duplicating `RENDERER_REGISTRY`
- `RenderResult.semantic_adapter` uses `"unsupported"` for experimental types — misleading (they ARE partially supported)

## Constraints

- Preserve backward compatibility for IMPLEMENTED types: `to_svg(flowchart_src)` must still work unchanged
- `strict: bool = True` default makes the new behavior opt-in only for callers that add `experimental=True`
- `dispatch_native()` and `dispatch_native_result()` are unchanged (they have always returned partial output; strict policy applies only to `to_svg()`)
- No circular imports introduced
- `scene.py` does not import from `registry.py` at module level (use lazy import at bottom of file to avoid cycles)

## Assumptions

1. Python loads `registry.py` fully before any `native_svg.py` builder runs (lazy builders), so `scene.py` can import `RENDERER_REGISTRY` at module-bottom without circularity.
2. All tests that call `to_svg()` on experimental types will be updated to add `experimental=True`.
3. `to_svg(strict=False)` is not required for the scope of this PR — the use case for non-strict library is `dispatch_native()`.

## Declined patterns

- Tempted to add `NativeBuildArtifact` and wire it through all builders: declining — touching all 20+ builders in one PR creates a massive diff; define the type, defer wiring.
- Tempted to rename `native_status` → `status` across codebase: declining — 40+ test assertions reference `native_status`; rename needs its own PR.
- Tempted to add `strict=False` path for library callers who want partial: declining — `dispatch_native()` already covers this case; don't add API surface without a second caller needing it.
- Tempted to make `fallback="legacy-dom"` bypass experimental strictness: declining — fallback is for legacy-only types; experimental types have a native builder and should use `experimental=True` explicitly.

## Resolve-vs-surface disposition

- Whether `scene.py`→`registry.py` import creates a cycle: **resolved** — `registry.py` uses only stdlib at module level; lazy builders avoid circular init.
- Whether to also update `dispatch_native_result()` strict logic: **resolved** — `dispatch_native_result()` already returns `RenderResult` with all fields; callers check `is_success()` themselves; no change needed.
- Whether to add `strict=False` path to `to_svg()`: **resolved** — declining per declined patterns above.
- Migration of fidelity adapter: **resolved** — add `experimental=True` to its `to_svg()` call.

## Acceptance Criteria

### Bug fix — architecture-basic.mmd label

- [x] **AC-BUG.1** `test_fixture_capability_matrix[architecture-beta/architecture-basic.mmd]` passes. Expected label updated from `["api"]` to `["API Gateway"]` to match rendered service label.

### Phase 1 — Strict public API enforcement

- [x] **AC-1.1** `ExperimentalOptInRequired(diagram_type: str)` exception class exists in `errors.py`; subclasses `ValueError`; has `.diagram_type` attribute.
- [x] **AC-1.2** `RenderResult.semantic_adapter` Literal includes `"partial"`: `Literal["passed", "partial", "unsupported", "failed"]`.
- [x] **AC-1.3** `render_svg_result()` sets `semantic_adapter="partial"` (not `"unsupported"`) for `native_status=="experimental"` types.
- [x] **AC-1.4** `RenderResult.to_exception()` returns `ExperimentalOptInRequired` when `semantic_adapter=="partial"`.
- [x] **AC-1.5** `RenderResult.to_exception()` returns `UnsupportedDiagramType` when `semantic_adapter=="unsupported"`.
- [x] **AC-1.6** `to_svg()` accepts new keyword params: `strict: bool = True`, `experimental: bool = False`.
- [x] **AC-1.7** `to_svg(experimental_src)` (strict=True, experimental=False) raises `ExperimentalOptInRequired`.
- [x] **AC-1.8** `to_svg(experimental_src, experimental=True)` returns a non-empty SVG string.
- [x] **AC-1.9** `to_svg(implemented_src)` returns SVG unchanged (IMPLEMENTED types unaffected).
- [x] **AC-1.10** `to_svg(unsupported_src)` raises `UnsupportedDiagramType` (unchanged behavior).
- [x] **AC-1.11** `to_png()` accepts `strict: bool = True`, `experimental: bool = False`; applies same policy by delegating to `to_svg()`.
- [x] **AC-1.12** `to_png(experimental_src)` raises `ExperimentalOptInRequired` without `experimental=True`.
- [x] **AC-1.13** All existing tests that call `to_svg()` or `to_png()` on experimental types are updated to pass `experimental=True`.
- [x] **AC-1.14** `__main__.py` CLI `svg` and `png` commands pass `experimental=True` (developer tool; backward compat).

### Phase 2 — Single registry

- [x] **AC-2.1** `scene.NATIVE_RENDERER_REGISTRY` is reconciled from `RENDERER_REGISTRY` at module load time; it cannot drift in type coverage.
- [x] **AC-2.2** `set(NATIVE_RENDERER_REGISTRY.keys()) == set(RENDERER_REGISTRY.keys()) | set(DIRECTIVE_ALIASES.keys())` is true at runtime (canonical keys + alias keys like `"graph"`).
- [x] **AC-2.3** The `_reg()` calls in `scene.py` retain per-type feature data but are supplemented by a `_reconcile_with_renderer_registry()` call at module end that adds missing canonical + alias keys and removes stale keys not in `RENDERER_REGISTRY` or `DIRECTIVE_ALIASES`.
- [x] **AC-2.4** A type added to `RENDERER_REGISTRY` automatically appears in `NATIVE_RENDERER_REGISTRY` via the reconciliation step (key equality test is the proxy).
- [x] **AC-2.5** Registry consistency test: every IMPLEMENTED entry has a `native_builder`.
- [x] **AC-2.6** Registry consistency test: every UNSUPPORTED entry has no `native_builder`.
- [x] **AC-2.7** Registry consistency test: every directive in `_KNOWN_DIRECTIVES` resolves to a registry entry (existing test still passes).

### Regression gate

- [x] **AC-REG.1** `pytest tests/ -q --tb=short` passes with 0 failures.
- [x] **AC-REG.2** `test_partial_directive_produces_svg_not_stub` still tests that PARTIAL types produce SVG (IMPLEMENTED types via `to_svg()`, classdiagram via `to_svg(experimental=True)`).

## Testing Strategy

All new behavior: TDD (write failing test → implement → observe green).
Existing test updates: update test call site to add `experimental=True`, confirm green.

New tests go in `tests/test_mermaid_trustworthiness.py`:
- `test_normal_to_svg_rejects_experimental` — `to_svg(architecture_src)` raises `ExperimentalOptInRequired`
- `test_experimental_true_permits_partial` — `to_svg(architecture_src, experimental=True)` returns SVG with `<svg`
- `test_implemented_strict_always_succeeds` — `to_svg(flowchart_src)` (strict=True) succeeds
- `test_to_png_obeys_strict_policy` — `to_png(architecture_src)` raises `ExperimentalOptInRequired`
- `test_legacy_fallback_still_requires_explicit` — `to_svg(architecture_src, fallback="legacy-dom")` raises (fallback is for legacy-only, not experimental)
- `test_unexpected_builder_exception_is_typed` — inject exception into builder, assert `NativeRenderError` from `to_svg()`
- `test_render_result_partial_not_unsupported` — `dispatch_native_result(architecture_src)` has `semantic_adapter=="partial"`, not `"unsupported"`
- `test_to_exception_partial_returns_experimental_opt_in` — `RenderResult(semantic_adapter="partial", ...).to_exception()` is `ExperimentalOptInRequired`
- `test_native_registry_derived_from_renderer_registry` — keys match
- `test_no_type_in_native_not_in_renderer` — no extra keys in NATIVE_RENDERER_REGISTRY
- `test_implemented_entries_have_builder` — all implemented caps have native_builder
- `test_unsupported_entries_have_no_builder` — all unsupported caps have no native_builder
