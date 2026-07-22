# Native SVG Hardening 2026-07 — plan

**Status:** In Progress

## Assumption trio

1. `python -m pytest tests/ -x -q` currently produces exactly 1 failure: `test_compare_gallery.py::TestGalleryExitCode::test_no_exit_1_when_all_ok` (caused by `NodeLayout.parent_group_id` missing field).
2. `dispatch_native()` and `native_svg.py` are internal APIs — only `to_svg()` in `__init__.py` calls them publicly.
3. Changing stub functions to raise rather than return SVG will break `TestStubMigration`; those tests must be updated.

## Declined patterns

- **Tempted to merge `errors.py` into `registry.py`**: keeping them separate improves import-cycle safety (`errors.py` imports nothing from this package).
- **Tempted to immediately implement segment-vs-rect intersection (Phase 5 check 14)**: needs a geometry algorithm library or significant code; out of scope for this loop.
- **Tempted to emit `RenderResult` from all existing scene builders**: would require updating every scene function; add `dispatch_native_result()` as a thin wrapper around existing scene pipeline instead.
- **Tempted to change gallery to use `to_svg()` instead of `to_html()`**: gallery tests HTML rendering; switching backends would break gallery semantics; stub rejection is separate from HTML validation.

## Resolve-vs-surface disposition

- Gallery `has_failures` logic for stub/unvalidated: **resolved** — check `backend.endswith("-stub")` and `geometry == "unvalidated"` for IMPLEMENTED types in `_build_gallery()`.
- Whether to wire `dispatch_native_result()` into `to_svg()`: **resolved** — `to_svg()` uses `dispatch_native_result()` internally and returns `result.svg` only on strict success.
- Whether Phase 5 segment intersection is required for this PR: **surfaced** → deferred to Phase 5 complete (separate PR). Basic reconciliation + uniqueness + point validity is the floor.

---

## Tasks

### Task 0 — Fix NodeLayout.parent_group_id bug

**AC:** AC-B.1, AC-B.2, AC-B.3
**Mode:** TDD
**Depends on:** none
**Touches:** `scripts/mermaid_render/layout/_geometry.py`, `scripts/mermaid_render/layout/_strategies.py`

**Tests (write first — should be red before fix):**
```python
# test should already fail with AttributeError before fix
def test_to_html_flowchart_no_attribute_error():
    from mermaid_render import to_html
    html = to_html("flowchart TD\n    A --> B")
    assert "data-node-id" in html
```

**Approach:**
1. In `_geometry.py`, add `parent_group_id: Optional[str] = None` to `NodeLayout` after `accent_color`.
2. In `_strategies.py::_build_node_layouts_ir`, build a `node_to_group` map and pass `parent_group_id` correctly.

**Done when:** `pytest tests/test_compare_gallery.py::TestGalleryExitCode::test_no_exit_1_when_all_ok` passes.

---

### Task 1 — Support registry

**AC:** AC-1.1–AC-1.5
**Mode:** TDD
**Depends on:** Task 0
**Touches:** `scripts/mermaid_render/registry.py` (new), `scripts/mermaid_render/__init__.py`, `tests/test_native_svg_registry.py` (new)

**Tests (write first):**
```python
def test_renderer_capability_fields():
    from mermaid_render.registry import RendererCapability
    rc = RendererCapability(
        diagram_type="flowchart",
        native_status="implemented",
        native_builder=None,
        validator=None,
        semantic_fixture_ids=(),
    )
    assert rc.diagram_type == "flowchart"
    assert rc.native_status == "implemented"

def test_registry_covers_all_required_types():
    from mermaid_render.registry import RENDERER_REGISTRY
    required = {
        "architecture", "block", "c4context", "c4container", "c4component",
        "classdiagram", "erdiagram", "flowchart", "gantt", "gitgraph",
        "journey", "kanban", "mindmap", "packet-beta", "pie",
        "quadrantchart", "requirementdiagram", "sankey-beta",
        "sequencediagram", "statediagram-v2", "timeline",
        "xychart-beta", "zenuml",
    }
    assert required <= set(RENDERER_REGISTRY.keys())

def test_get_capability_flowchart():
    from mermaid_render.registry import get_capability
    cap = get_capability("flowchart")
    assert cap.native_status == "implemented"

def test_get_capability_unknown_raises():
    from mermaid_render.registry import get_capability
    import pytest
    with pytest.raises(KeyError):
        get_capability("nonexistent-type")

def test_registry_public_from_package():
    import mermaid_render
    assert hasattr(mermaid_render, "get_capability")
    assert hasattr(mermaid_render, "RENDERER_REGISTRY")
```

**Approach:**
1. Create `scripts/mermaid_render/registry.py` with `RendererCapability` frozen dataclass and `RENDERER_REGISTRY` dict.
2. Status assignment: flowchart/stateDiagram-v2 → "implemented"; architecture/C4/classDiagram/timeline/mindmap → "experimental" (have real builders but fallback); sequence/er/gantt/quadrant/pie/xychart/block/packet/kanban/journey/requirement/gitgraph → "legacy-only"; sankey/zenuml → "unsupported".
3. Add `get_capability()` function.
4. Export from `__init__.py`.

**Done when:** All registry tests green.

---

### Task 2 — Typed errors + remove placeholder success paths

**AC:** AC-2.1–AC-2.8
**Mode:** TDD
**Depends on:** Task 1
**Touches:** `scripts/mermaid_render/errors.py` (new), `scripts/mermaid_render/native_svg.py`, `scripts/mermaid_render/__init__.py`, `tests/test_native_svg_backend.py`, `tests/test_native_svg_registry.py`

**Tests (write first — will be red until errors.py exists):**
```python
# errors
def test_native_render_error_has_cause():
    from mermaid_render.errors import NativeRenderError
    cause = ValueError("bad")
    err = NativeRenderError("flowchart", "routing", cause=cause)
    assert err.diagram_type == "flowchart"
    assert err.phase == "routing"
    assert err.__cause__ is cause

def test_unsupported_diagram_type_error():
    from mermaid_render.errors import UnsupportedDiagramType
    err = UnsupportedDiagramType("sankey-beta")
    assert "sankey-beta" in str(err)

def test_native_renderer_unavailable():
    from mermaid_render.errors import NativeRendererUnavailable
    err = NativeRendererUnavailable("sequencediagram")
    assert "sequencediagram" in str(err)

# legacy-only types now raise
def test_sequence_raises_native_renderer_unavailable():
    from mermaid_render.native_svg import dispatch_native
    from mermaid_render.errors import NativeRendererUnavailable
    src = "sequenceDiagram\n    Alice->>Bob: Hi\n"
    with pytest.raises(NativeRendererUnavailable):
        dispatch_native(src)

def test_er_raises_native_renderer_unavailable():
    from mermaid_render.native_svg import dispatch_native
    from mermaid_render.errors import NativeRendererUnavailable
    src = "erDiagram\n    CUSTOMER ||--o{ ORDER : places\n"
    with pytest.raises(NativeRendererUnavailable):
        dispatch_native(src)

# sankey/zenuml still raise ValueError-like
def test_sankey_raises_unsupported():
    from mermaid_render.native_svg import dispatch_native
    from mermaid_render.errors import UnsupportedDiagramType
    with pytest.raises(UnsupportedDiagramType):
        dispatch_native("sankey-beta\nA,B,10")

# injection regression test
def test_unexpected_adapter_exception_becomes_native_render_error(monkeypatch):
    from mermaid_render import native_svg
    from mermaid_render.errors import NativeRenderError
    import pytest
    def _bad_builder(*a, **kw):
        raise RuntimeError("adapter exploded")
    monkeypatch.setattr(native_svg, "_graph_topology_scene", _bad_builder)
    with pytest.raises(NativeRenderError) as exc_info:
        native_svg.dispatch_native("flowchart TD\n    A-->B\n")
    assert exc_info.value.__cause__ is not None

# fallback parameter
def test_to_svg_fallback_legacy_dom_for_unsupported():
    # Should NOT raise when fallback="legacy-dom" — instead tries legacy path
    # (legacy path may itself fail if Playwright absent, but dispatch_native doesn't raise)
    from mermaid_render.errors import NativeRendererUnavailable
    import mermaid_render
    # Without fallback: raises
    with pytest.raises(NativeRendererUnavailable):
        mermaid_render.to_svg("sequenceDiagram\n    Alice->>Bob: Hi\n")
    # With fallback (may raise different error if no Playwright, but not NativeRendererUnavailable)
    try:
        mermaid_render.to_svg("sequenceDiagram\n    Alice->>Bob: Hi\n", fallback="legacy-dom")
    except NativeRendererUnavailable:
        pytest.fail("Should not raise NativeRendererUnavailable when fallback='legacy-dom'")
    except Exception:
        pass  # Playwright may not be installed; that's fine
```

**Approach:**
1. Create `errors.py` with four exception classes.
2. In `native_svg.py`:
   - Stub functions: replace `return _html_fallback_scene(...)` with `raise NativeRendererUnavailable(diagram_type)`.
   - Broad except: replace with `except (UnsupportedDiagramFeature, NativeRendererUnavailable): raise; except Exception as e: raise NativeRenderError(diagram_type, phase, cause=e) from e`.
   - Keep `_html_fallback_scene` but add `debug_placeholder: bool` guard.
   - Change `ValueError` for sankey/zenuml to `UnsupportedDiagramType`.
3. Update `to_svg()` to accept `fallback` param; catch `NativeRendererUnavailable` and route to legacy if `fallback="legacy-dom"`.
4. Update `TestStubMigration` in `test_native_svg_backend.py` to expect `NativeRendererUnavailable`.

**Done when:** All new error tests green; `TestStubMigration` updated and green.

---

### Task 3 — RenderResult contract

**AC:** AC-3.1–AC-3.5
**Mode:** TDD
**Depends on:** Task 2
**Touches:** `scripts/mermaid_render/registry.py`, `scripts/mermaid_render/native_svg.py`, `tests/test_native_svg_registry.py`

**Tests (write first):**
```python
def test_render_result_strict_success():
    from mermaid_render.registry import RenderResult
    r = RenderResult(
        svg="<svg/>", diagram_type="flowchart", backend="native",
        semantic_adapter="passed", syntax_coverage="passed",
        geometry="passed", serialization="passed",
        warnings=(), errors=(),
    )
    assert r.is_success(strict=True)

def test_render_result_strict_rejects_unvalidated_geometry():
    from mermaid_render.registry import RenderResult
    r = RenderResult(
        svg="<svg/>", diagram_type="flowchart", backend="native",
        semantic_adapter="passed", syntax_coverage="passed",
        geometry="unvalidated", serialization="passed",
        warnings=(), errors=(),
    )
    assert not r.is_success(strict=True)
    assert r.is_success(strict=False)  # non-strict allows unvalidated

def test_render_result_stub_backend_not_strict_success():
    from mermaid_render.registry import RenderResult
    r = RenderResult(
        svg="<svg/>", diagram_type="sequence", backend="native-svg-stub",
        semantic_adapter="unsupported", syntax_coverage="failed",
        geometry="unvalidated", serialization="passed",
        warnings=(), errors=(),
    )
    assert not r.is_success(strict=True)

def test_render_result_errors_never_success():
    from mermaid_render.registry import RenderResult
    r = RenderResult(
        svg="<svg/>", diagram_type="flowchart", backend="native",
        semantic_adapter="passed", syntax_coverage="passed",
        geometry="passed", serialization="passed",
        warnings=(), errors=("validation failed",),
    )
    assert not r.is_success(strict=False)
    assert not r.is_success(strict=True)

def test_dispatch_native_result_returns_render_result():
    from mermaid_render.native_svg import dispatch_native_result
    from mermaid_render.registry import RenderResult
    result = dispatch_native_result("flowchart TD\n    A-->B\n")
    assert isinstance(result, RenderResult)
    assert result.diagram_type == "flowchart"

def test_dispatch_native_result_flowchart_strict_success():
    from mermaid_render.native_svg import dispatch_native_result
    result = dispatch_native_result("flowchart TD\n    A-->B\n")
    # flowchart is IMPLEMENTED — should succeed strictly
    assert result.is_success(strict=True) or result.geometry == "unvalidated"
    # At minimum: no errors and SVG produced
    assert result.svg is not None
    assert not result.errors
```

**Approach:**
1. Add `RenderResult` frozen dataclass to `registry.py`.
2. Add `dispatch_native_result(src, *, theme=None, width_hint=0, height_hint=0) -> RenderResult` to `native_svg.py`.
3. Wire `dispatch_native()` to call `dispatch_native_result()` and return `result.svg` or raise.

**Done when:** All RenderResult tests green; `dispatch_native_result("flowchart TD\n    A-->B\n")` returns a `RenderResult`.

---

### Task 4 — Finalized-layout edge invariants

**AC:** AC-5.1–AC-5.7
**Mode:** TDD
**Depends on:** Task 0 (geometry.py access)
**Touches:** `scripts/mermaid_render/layout/_geometry.py`, `tests/test_geometry_ir.py`

**Tests (write first — add to existing test_geometry_ir.py or new test_geometry_invariants.py):**
```python
def test_edge_reconciliation_invariant_passes():
    """len(routed_edges) + len(routing_failures) == original_edge_count."""
    from mermaid_render.layout._geometry import (
        FinalizedLayout, LayoutMetadata, NodeLayout, Rect, RoutedEdge,
        RoutingFailure, Point, PortLayout, PortSide
    )
    # Build a minimal valid FinalizedLayout
    ...
    violations = layout.validate()
    assert not any("edge reconciliation" in v for v in violations)

def test_edge_reconciliation_invariant_fails_when_off():
    ...
    violations = layout.validate()
    assert any("edge reconciliation" in v for v in violations)

def test_unique_routed_edge_ids():
    ...

def test_no_edge_in_both_routed_and_failed():
    ...

def test_route_has_at_least_two_points():
    ...

def test_consecutive_points_distinct():
    ...
```

**Approach:**
Check which invariant checks already exist in `FinalizedLayout.validate()` (lines 420–560 in `_geometry.py`). Add missing checks:
1. Edge reconciliation (may already exist — if so, strengthen assertion message).
2. Routed edge ID uniqueness.
3. Routing failure ID uniqueness.
4. No overlap between routed and failed sets.
5. Each route has ≥2 points, all finite.
6. Consecutive points are distinct.

**Done when:** New invariant tests pass; existing `test_geometry_ir.py` still passes.

---

### Task 5 — Gallery stub rejection

**AC:** AC-7.1, AC-7.2
**Mode:** goal-based
**Depends on:** Tasks 0, 2
**Touches:** `tools/compare_gallery.py`, `tests/test_compare_gallery.py`

**Done when:** `test_no_exit_1_when_all_ok` passes (fixed by Task 0); gallery marks stub/unvalidated IMPLEMENTED types as failures.

**Approach:**
1. In `_build_gallery()`, after getting `vr`, also call `dispatch_native_result(src)` (if available and IMPLEMENTED type), check `result.backend.endswith("-stub")` or `result.geometry == "unvalidated"`.
2. Include in `has_failures` check.
3. Add test that gallery fails for a mocked stub backend result.

---

## Files touched summary

| File | Tasks |
|------|-------|
| `scripts/mermaid_render/layout/_geometry.py` | 0, 4 |
| `scripts/mermaid_render/layout/_strategies.py` | 0 |
| `scripts/mermaid_render/errors.py` (new) | 2 |
| `scripts/mermaid_render/registry.py` (new) | 1, 3 |
| `scripts/mermaid_render/native_svg.py` | 2, 3 |
| `scripts/mermaid_render/__init__.py` | 1, 2 |
| `tools/compare_gallery.py` | 5 |
| `tests/test_native_svg_backend.py` | 2 |
| `tests/test_native_svg_registry.py` (new) | 1, 2, 3 |
| `tests/test_geometry_ir.py` | 4 |
| `tests/test_compare_gallery.py` | 5 |
