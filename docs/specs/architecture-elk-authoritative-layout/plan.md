# Implementation Plan — architecture-elk-authoritative-layout

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/architecture.py`,
   `scripts/mermaid_render/layout/_strategies.py`,
   `scripts/mermaid_render/errors.py`,
   `tests/test_architecture_painter.py`.
2. Done when: `pytest tests/` passes; `architecture-complex` fixture tests green
   under `@requires_elk`; fallback tests green in `MERMAID_LAYOUT_ENGINE=python`;
   `mypy scripts/` exits 0.
3. Not changing: `elk_adapter.py`, `_routing.py`, `_renderer.py`,
   `FinalizedLayout`/`LayoutDiagnostics` dataclasses, `layout_architecture_scene()`
   public signature, or any Python Sugiyama logic.

**Declined patterns:**
- Tempted to fold all ELK-path logic into `arch_to_finalized()`; declining — the
  ELK call and fallback decision must stay in `compile_architecture()` so the caller
  can distinguish layout failure from rendering failure, and so `_layout_architecture()`
  in `_strategies.py` can mirror the same guard without touching `arch_to_finalized`.
- Tempted to patch `LayoutDiagnostics` with a new `backend` field; declining — the
  contract states to use `warnings` for backend provenance to avoid breaking the
  `FinalizedLayout` dataclass interface. Revisit if a dedicated field is added in
  a later spec.
- Tempted to convert `_build_arch_layout_graph` to pass `direction=None` to let ELK
  choose; declining — the product spec says LR is a preference submitted to ELK,
  and the existing `LayoutGraph(direction="LR")` construction is correct.

---

## Tasks

### Task 1: Add `ArchitectureLayoutError` to errors.py
Depends on: none
Verification: TDD

**Tests:**
- `test_architecture_layout_error_is_native_render_error`: instantiate
  `ArchitectureLayoutError("layout", cause=ValueError("x"))`, assert
  `isinstance(e, NativeRenderError)`, `e.diagram_type == "architecture-beta"`,
  `e.phase == "layout"`, and `str(e)` contains `"x"`.

**Approach:**
- Add `ArchitectureLayoutError` to `scripts/mermaid_render/errors.py` as a subclass
  of `NativeRenderError` with a fixed `diagram_type="architecture-beta"` and a
  `phase` parameter. Keep the constructor signature consistent with `NativeRenderError`.

---

### Task 2: Add `_arch_fallback_to_finalized()` helper in architecture.py
Depends on: none
Verification: TDD

**Tests:**
- `test_fallback_returns_finalized_layout`: call `_arch_fallback_to_finalized` with
  the parsed nodes/edges/groups from `architecture-complex`; assert result is a
  `FinalizedLayout`, `node_layouts` contains all expected node IDs, `group_layouts`
  contains `"cloud"`, and `"python-fallback"` appears in
  `result.diagnostics.warnings`.
- `test_fallback_canvas_nonzero`: assert `result.canvas_bounds.w > 0` and
  `result.canvas_bounds.h > 0`.

**Approach:**
- Extract the heuristic + group + route path from the bottom of `compile_architecture()`
  into a new private function `_arch_fallback_to_finalized(nodes, edges, groups, width_hint)`.
- The function calls `_heuristic_arch_placement`, `_compute_group_bboxes`, and
  `_route_edges` in the same order as today.
- Builds a `FinalizedLayout` via `arch_to_finalized()` applied to the resulting
  `ArchitectureDiagramLayout`, then stamps `"python-fallback"` into
  `diagnostics.warnings` by returning a `dataclasses.replace(fl, diagnostics=...)`.
- Does not raise; on internal failure propagates as-is (Task 5 handles the outer guard).

---

### Task 3: Add `_arch_elk_to_finalized()` helper in architecture.py
Depends on: none
Verification: TDD

**Tests:**
- `test_elk_to_finalized_preserves_group_layout`: given a mock `FinalizedLayout`
  (with a `GroupLayout` for `"cloud"`) and the original parsed `nodes`/`groups`,
  assert that `_arch_elk_to_finalized` returns a `FinalizedLayout` where
  `group_layouts["cloud"].label_layout` is not None (label was restored from
  the parsed group, which ELK's `_from_elk_result` loses).
- `test_elk_to_finalized_preserves_icon_svg`: assert that service `NodeLayout`s
  have their `icon_svg` and `accent_color` fields populated from the original
  parsed `nodes` dict (not empty strings as `_from_elk_result` leaves them).
- `test_elk_to_finalized_preserves_port_sides`: given a mock ELK `FinalizedLayout`
  with `src_port.side=PortSide.EAST` on an edge, assert the output edge retains
  `src_port.side == PortSide.EAST`.
- `test_elk_to_finalized_stamps_elk_backend`: assert `"elk-js"` appears in
  `result.diagnostics.warnings`.

**Approach:**
- `_arch_elk_to_finalized(elk_fl, nodes, groups, width_hint)` takes the raw
  `FinalizedLayout` from `layout_with_elk()` and the original parsed dicts.
- Iterates `elk_fl.node_layouts`, merging `icon_svg`, `icon_bounds`, `accent_color`,
  `title_layout`, `side_ports`, and `parent_group_id` from the original `nodes` dict.
- Iterates `elk_fl.group_layouts`, merging `label_layout` and `child_group_ids` from
  the original `groups` dict.
- Leaves `routed_edges`, `canvas_bounds`, `visible_bounds` from `elk_fl` unchanged
  (they are ELK-authoritative).
- Stamps `"elk-js"` into `diagnostics.warnings` via `dataclasses.replace`.
- Computes zoom from `width_hint` and `canvas_bounds.w` (same formula as today).

---

### Task 4: Rewrite `compile_architecture()` ELK path
Depends on: Task 2, Task 3
Verification: TDD

**Tests:**
- `test_compile_architecture_elk_path_no_reroute` (`@requires_elk`): monkeypatch
  `_route_edges` and `_compute_group_bboxes` to raise `AssertionError("should not
  be called on ELK path")`; call `compile_architecture()` on `architecture-complex`
  under real ELK; assert no `AssertionError` raised.
- `test_compile_architecture_elk_unavailable_falls_back`: monkeypatch
  `layout_with_elk` to raise `ElkUnavailable("test")`; call
  `compile_architecture()` on `architecture-complex`; assert result is an
  `ArchitectureDiagramLayout` and `"python-fallback"` is in the returned
  `FinalizedLayout`'s diagnostics warnings (accessed via `arch_to_finalized`).
- `test_compile_architecture_incomplete_elk_raises`: monkeypatch `layout_with_elk`
  to return a `FinalizedLayout` with an empty `node_layouts`; assert `ValueError`
  is raised with a message containing the missing node ID.
- `test_compile_architecture_unexpected_error_raises_typed`: monkeypatch
  `layout_with_elk` to raise `RuntimeError("boom")`; assert
  `ArchitectureLayoutError` is raised and `.__cause__` is the original
  `RuntimeError`.

**Approach:**
- Replace the `try/except Exception: pass` block with:
  ```python
  try:
      _fl = layout_with_elk(_lg)
      missing = _expected_nids - set(_fl.node_layouts.keys())
      if missing:
          raise ValueError(f"ELK returned incomplete layout: missing nodes {missing}")
      return _arch_elk_to_finalized(_fl, nodes, groups, width_hint)
  except ElkUnavailable as exc:
      warnings.warn(str(exc), stacklevel=2)
      # fall through to fallback
  except ValueError:
      raise  # incomplete result — propagate as-is
  except Exception as exc:
      raise ArchitectureLayoutError("layout", cause=exc) from exc
  ```
- After the try/except: call `_arch_fallback_to_finalized(nodes, edges, groups,
  width_hint)` and return its result.
- Remove the old `canvas_w == 0` sentinel check (Task 2's fallback function
  handles the canvas computation internally).

---

### Task 5: Mirror the fix in `_layout_architecture()` in `_strategies.py`
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_layout_architecture_elk_path_no_reroute` (`@requires_elk`): monkeypatch
  `_route_edges` and `_compute_group_bboxes` inside `_strategies.py` to raise
  `AssertionError`; call `_layout_architecture(ARCH_COMPLEX_SRC, "LR", 0)`;
  assert no `AssertionError`.
- `test_layout_architecture_fallback_string_output`: set
  `MERMAID_LAYOUT_ENGINE=python` via `monkeypatch.setenv`; call
  `_layout_architecture(ARCH_COMPLEX_SRC, "LR", 0)`; assert result is a non-empty
  string (existing contract — `_layout_architecture` returns an SVG fragment string).

**Approach:**
- In `_layout_architecture()`, replace the `try/except Exception: pass` block
  (lines ~4225–4243) with the same typed three-branch guard as Task 4.
- Import `ElkUnavailable` from `elk_adapter` at the top of the try block (already
  imported inline in the current code).
- Import `ArchitectureLayoutError` from `..errors`.
- The fallback branch in `_layout_architecture` continues to call
  `_heuristic_arch_placement` then `_render_graph_fragment` as today (this function
  returns an SVG string, not a `FinalizedLayout`, so it cannot use
  `_arch_fallback_to_finalized` directly).

---

### Task 6: Add `@requires_elk` port-side and containment acceptance tests
Depends on: Task 4
Verification: TDD

**Tests (all `@requires_elk`, in `tests/test_architecture_painter.py`):**
- `test_lb_exits_east_api_enters_west`: load `architecture-complex.mmd`, call
  `compile_architecture()`, find the `lb->api` edge in `arch.edges`, assert
  `src_port.side == PortSide.RIGHT` (EAST) and `dst_port.side == PortSide.LEFT`
  (WEST). Note: `PortSide.RIGHT == EAST` per the existing enum.
- `test_api_db_exits_east_enters_west`: same for the `api->db` edge.
- `test_api_cache_exits_south_enters_north`: find `api->cache`, assert
  `src_port.side == PortSide.BOTTOM` and `dst_port.side == PortSide.TOP`.
- `test_api_queue_exits_east_enters_west`: find `api->queue`.
- `test_all_services_contained_in_cloud`: for each service in `arch.services`,
  assert `svc.outer_bounds` is geometrically inside the `cloud` group
  `boundary_bounds` (all four corners within the boundary rect).
- `test_no_edge_crosses_service_or_title`: for each edge waypoint, assert it does
  not fall inside any service `outer_bounds` and does not fall within the top
  `GROUP_PAD_Y_TOP` pixels of the group `boundary_bounds` (the title strip).
- `test_elk_backend_in_provenance`: call `arch_to_finalized(arch)`, assert
  `"elk-js"` appears in `result.diagnostics.warnings`.

**Approach:**
- Load the fixture via `Path("tests/fixtures/architecture-complex.mmd").read_text()`.
- Use the existing `@requires_elk` pytest mark already used in
  `tests/test_elk_adapter.py`.
- For geometry containment helpers, define a small inline `_contains(outer, inner)`
  function (returns `True` if `inner.x >= outer.x`, `inner.y >= outer.y`,
  `inner.x+inner.w <= outer.x+outer.w`, `inner.y+inner.h <= outer.y+outer.h`).

---

### Task 7: Fallback and error-path acceptance tests (no ELK required)
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_fallback_warning_on_elk_unavailable`: monkeypatch `layout_with_elk` to
  raise `ElkUnavailable("test")`; call `compile_architecture()` on
  `architecture-complex`; convert via `arch_to_finalized()`; assert
  `"python-fallback"` in `result.diagnostics.warnings`.
- `test_incomplete_elk_result_raises_value_error`: monkeypatch to return
  `FinalizedLayout` with empty `node_layouts`; assert `ValueError` message contains
  `"missing nodes"`.
- `test_unexpected_elk_exception_raises_architecture_layout_error`: monkeypatch
  to raise `OSError("disk full")`; assert `ArchitectureLayoutError` is raised with
  `.__cause__` being the `OSError`.
- `test_fallback_output_matches_finalized_contract`: set
  `MERMAID_LAYOUT_ENGINE=python`; call `compile_architecture()` + `arch_to_finalized()`;
  assert `canvas_bounds.w > 0`, `len(node_layouts) == 5` (five services),
  `len(group_layouts) == 1` (cloud group), `len(routed_edges) >= 4`.

**Approach:**
- Use `pytest.monkeypatch` to swap `layout_with_elk` in the
  `scripts.mermaid_render.layout.architecture` module namespace.
- No ELK toolchain required — all paths exercised via monkeypatching.
