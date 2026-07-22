# Mermaid Trustworthiness Pass — plan

**Status:** Done

## Assumption trio

1. `registry.py` is fully initialized before any `native_svg.py` builder runs (builders are lazy imports); adding `from .registry import RENDERER_REGISTRY` at the bottom of `scene.py` will not create a circular import.
2. All tests calling `to_svg()` on experimental types are in the test files identified in the spec boundaries; there are no other undiscovered callers in the production code path that would silently start failing.
3. IMPLEMENTED types (flowchart, statediagram-v2, statediagram) currently return `geometry="passed"` via their validators; making `to_svg()` call `is_success(strict=True)` will NOT break them.

## Declined patterns

- Tempted to change all builder signatures to `NativeBuildArtifact` simultaneously: this touches 20+ functions and deserves its own loop.
- Tempted to add `parity: Literal["full", "partial", "none"]` field to `RendererCapability`: existing `native_status` already encodes this; `NativeParityLevel` in `scene.py` is already derived from it; adding yet another representation is premature without a consumer.
- Tempted to wire `ExperimentalOptInRequired` into `dispatch_native_result()`: it already returns `RenderResult`; callers reading `semantic_adapter` already can distinguish partial.

## Tasks

---

### Task 0 — Fix failing test (architecture-basic.mmd label)

**AC:** AC-BUG.1
**Mode:** Goal-based check
**Depends on:** none
**Touches:** `tests/test_native_renderer_capabilities.py`

**Done when:** `pytest tests/test_native_renderer_capabilities.py::test_fixture_capability_matrix -k "architecture-basic" -q` passes.

**Approach:**
In `_FIXTURE_MATRIX`, change the architecture-beta fixture row from `["api"]` to `["API Gateway"]`.
The fixture `architecture-basic.mmd` has `service api(internet)[API Gateway]`; the rendered SVG shows the user-visible label "API Gateway", not the service ID "api".

---

### Task 1 — ExperimentalOptInRequired + RenderResult.semantic_adapter "partial"

**AC:** AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-1.5
**Mode:** TDD
**Depends on:** Task 0
**Touches:** `scripts/mermaid_render/errors.py`, `scripts/mermaid_render/registry.py`, `scripts/mermaid_render/native_svg.py`, `tests/test_mermaid_trustworthiness.py` (new)

**Tests (write first — should be red before fix):**
```python
# tests/test_mermaid_trustworthiness.py

def test_render_result_partial_not_unsupported():
    """render_svg_result() must set semantic_adapter='partial' for experimental types."""
    from scripts.mermaid_render import dispatch_native_result
    result = dispatch_native_result("architecture-beta\n  service s(internet)[S]")
    assert result.semantic_adapter == "partial", (
        f"Expected 'partial' for experimental type, got {result.semantic_adapter!r}"
    )
    assert result.semantic_adapter != "unsupported"

def test_to_exception_partial_returns_experimental_opt_in():
    """RenderResult with semantic_adapter='partial' raises ExperimentalOptInRequired."""
    from scripts.mermaid_render.registry import RenderResult
    from scripts.mermaid_render.errors import ExperimentalOptInRequired
    r = RenderResult(
        svg="<svg/>",
        diagram_type="architecture-beta",
        backend="native",
        semantic_adapter="partial",
        syntax_coverage="partial",
        geometry="unvalidated",
        serialization="passed",
        warnings=(),
        errors=(),
    )
    exc = r.to_exception()
    assert isinstance(exc, ExperimentalOptInRequired)
    assert exc.diagram_type == "architecture-beta"

def test_to_exception_unsupported_returns_unsupported_diagram_type():
    """RenderResult with semantic_adapter='unsupported' raises UnsupportedDiagramType."""
    from scripts.mermaid_render.registry import RenderResult
    from scripts.mermaid_render.errors import UnsupportedDiagramType
    r = RenderResult(
        svg=None,
        diagram_type="sankey-beta",
        backend="none",
        semantic_adapter="unsupported",
        syntax_coverage="failed",
        geometry="unvalidated",
        serialization="failed",
        warnings=(),
        errors=("unsupported",),
    )
    exc = r.to_exception()
    assert isinstance(exc, UnsupportedDiagramType)
```

**Approach:**
1. In `errors.py`: add `ExperimentalOptInRequired(diagram_type)` that subclasses `ValueError`.
2. In `registry.py`: add `"partial"` to `RenderResult.semantic_adapter` Literal.
3. In `registry.py` `RenderResult.to_exception()`: check `semantic_adapter=="partial"` → `ExperimentalOptInRequired`; check `semantic_adapter=="unsupported"` → `UnsupportedDiagramType`. These two checks must be placed **before** the existing `geometry=="failed"` and `if self.errors` branches so the correct exception is returned when semantic_adapter is set.
4. In `native_svg.py` `render_svg_result()`: change `sem_adapter = "unsupported"` to `sem_adapter = "partial"` for the `native_status=="experimental"` branch.
5. Export `ExperimentalOptInRequired` from `__init__.py`.

---

### Task 2 — Strict to_svg() and to_png() enforcement

**AC:** AC-1.6, AC-1.7, AC-1.8, AC-1.9, AC-1.10, AC-1.11, AC-1.12, AC-1.13, AC-1.14
**Mode:** TDD
**Depends on:** Task 1
**Touches:** `scripts/mermaid_render/__init__.py`, `scripts/mermaid_render/__main__.py`, `tests/test_mermaid_trustworthiness.py`

**Tests (write first):**
```python
def test_normal_to_svg_rejects_experimental():
    """to_svg() with defaults raises ExperimentalOptInRequired for experimental types."""
    import os
    from unittest.mock import patch
    from scripts.mermaid_render import to_svg
    from scripts.mermaid_render.errors import ExperimentalOptInRequired
    from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE
    with patch.dict(os.environ, {BACKEND_ENV: BACKEND_NATIVE}):
        with pytest.raises(ExperimentalOptInRequired) as exc_info:
            to_svg("architecture-beta\n  service s(internet)[S]")
    assert exc_info.value.diagram_type == "architecture-beta"

def test_experimental_true_permits_partial():
    """to_svg(experimental=True) returns SVG for experimental types."""
    import os
    from unittest.mock import patch
    from scripts.mermaid_render import to_svg
    from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE
    with patch.dict(os.environ, {BACKEND_ENV: BACKEND_NATIVE}):
        result = to_svg("architecture-beta\n  service s(internet)[S]", experimental=True)
    assert result and "<svg" in result

def test_implemented_strict_always_succeeds():
    """to_svg() on IMPLEMENTED types still works with default strict=True."""
    import os
    from unittest.mock import patch
    from scripts.mermaid_render import to_svg
    from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE
    with patch.dict(os.environ, {BACKEND_ENV: BACKEND_NATIVE}):
        result = to_svg("flowchart LR\n  A --> B")
    assert result and "<svg" in result

def test_to_png_obeys_strict_policy():
    """to_png() raises ExperimentalOptInRequired for experimental types."""
    import os
    from unittest.mock import patch
    from scripts.mermaid_render import to_png
    from scripts.mermaid_render.errors import ExperimentalOptInRequired
    from scripts.mermaid_render.native_svg import BACKEND_ENV, BACKEND_NATIVE
    with patch.dict(os.environ, {BACKEND_ENV: BACKEND_NATIVE}):
        with pytest.raises(ExperimentalOptInRequired):
            to_png("architecture-beta\n  service s(internet)[S]")
```

**Approach:**
1. In `to_svg()`: add `strict: bool = True` and `experimental: bool = False` kwargs.
2. After calling `render_svg_result()`, if `strict=True`:
   - If `result.semantic_adapter == "partial"` and `not experimental`: `raise result.to_exception()`
   - Else if `not result.is_success(strict=True)` and not (`experimental` and `result.svg is not None`): `raise result.to_exception()`
   - Else return `result.svg`
3. In `to_png()`: add same kwargs; propagate to `to_svg()`.
4. In `__main__.py` `_cmd_svg()` AND `_cmd_png()`: pass `experimental=True` (CLI is a dev tool; backward compat).
5. The strict check is INSERTED into the existing `to_svg()` try/except block, not replacing it. The existing `try/except NativeRendererUnavailable/NativeRenderError → legacy-dom fallback` logic is preserved. The strict block activates on the normal-return path inside the try block, after `render_svg_result()` succeeds.
6. Update all failing test callsites:
   - `test_partial_directive_produces_svg_not_stub` for `classdiagram`: add `experimental=True`
   - `test_native_sequence_produces_svg` in registry tests: add `experimental=True`
   - `test_fallback_legacy_dom_does_not_raise_for_sequence`: add `experimental=True`
   - `test_sequence_native_produces_svg` in render_pipeline: add `experimental=True`
   - `tests/fidelity/adapters/native_svg.py` line ~458: add `experimental=True`

**Done when:** `pytest tests/ -q --tb=short` passes with 0 failures.

---

### Task 3 — NATIVE_RENDERER_REGISTRY derived from RENDERER_REGISTRY

**AC:** AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-2.5, AC-2.6, AC-2.7
**Mode:** TDD
**Depends on:** Task 0
**Touches:** `scripts/mermaid_render/scene.py`, `tests/test_mermaid_trustworthiness.py`

**Tests (write first):**
```python
def test_native_registry_derived_from_renderer_registry():
    """NATIVE_RENDERER_REGISTRY keys must exactly equal RENDERER_REGISTRY keys."""
    from scripts.mermaid_render.scene import NATIVE_RENDERER_REGISTRY
    from scripts.mermaid_render.registry import RENDERER_REGISTRY
    assert set(NATIVE_RENDERER_REGISTRY.keys()) == set(RENDERER_REGISTRY.keys()), (
        f"Key mismatch — native only: {set(NATIVE_RENDERER_REGISTRY.keys()) - set(RENDERER_REGISTRY.keys())}, "
        f"renderer only: {set(RENDERER_REGISTRY.keys()) - set(NATIVE_RENDERER_REGISTRY.keys())}"
    )

def test_no_type_in_native_not_in_renderer():
    """No extra type in NATIVE_RENDERER_REGISTRY that is not in RENDERER_REGISTRY."""
    from scripts.mermaid_render.scene import NATIVE_RENDERER_REGISTRY
    from scripts.mermaid_render.registry import RENDERER_REGISTRY
    extra = set(NATIVE_RENDERER_REGISTRY.keys()) - set(RENDERER_REGISTRY.keys())
    assert not extra, f"Types in NATIVE but not RENDERER: {extra}"

def test_implemented_entries_have_builder():
    """Every IMPLEMENTED capability in RENDERER_REGISTRY has a native_builder."""
    from scripts.mermaid_render.registry import RENDERER_REGISTRY
    for dtype, cap in RENDERER_REGISTRY.items():
        if cap.native_status == "implemented":
            assert cap.native_builder is not None, (
                f"{dtype} is implemented but has no native_builder"
            )

def test_unsupported_entries_have_no_builder():
    """Every UNSUPPORTED capability has no native_builder."""
    from scripts.mermaid_render.registry import RENDERER_REGISTRY
    for dtype, cap in RENDERER_REGISTRY.items():
        if cap.native_status == "unsupported":
            assert cap.native_builder is None, (
                f"{dtype} is unsupported but has a native_builder"
            )
```

**Approach:**
1. Keep all existing `_reg(...)` calls in `scene.py` — they preserve per-type feature data (`supported_features`, `unsupported_features`).
2. Keep the `del _reg` line — `_reg` is a private helper.
3. After `del _reg`, add a `_reconcile_with_renderer_registry()` function that:
   - Imports `RENDERER_REGISTRY` and `DIRECTIVE_ALIASES` lazily
   - Adds any canonical key in `RENDERER_REGISTRY` that is NOT in `NATIVE_RENDERER_REGISTRY` (new type auto-appears)
   - Adds any alias key in `DIRECTIVE_ALIASES` that is NOT in `NATIVE_RENDERER_REGISTRY` (keeps `"graph"`)
   - Removes any key in `NATIVE_RENDERER_REGISTRY` that is not in `RENDERER_REGISTRY` or `DIRECTIVE_ALIASES` (prunes stale types)
4. Call `_reconcile_with_renderer_registry()` immediately after its definition.
5. The `"graph"` key survives because it's already in `_reg("graph", ...)` AND would be added via DIRECTIVE_ALIASES if missing.

**Note on feature data loss:** `_reconcile_with_renderer_registry()` adds new types with empty feature lists. Existing types retain their hand-maintained feature data. This is acknowledged: the per-type feature lists belong in `RendererCapability` (out of scope for this PR).

**Done when:** `pytest tests/ -q --tb=short` passes with 0 failures and `test_native_registry_derived_from_renderer_registry` is green.

---

## End-of-loop checklist

- [ ] All ACs are green
- [ ] `pytest tests/ -q` passes with 0 failures
- [ ] `python .claude/skills/work-loop/scripts/lint-spec-status.py` clean
- [ ] No uncommitted or untracked files (except gitignored scratch)
- [ ] Conventional commit format used
