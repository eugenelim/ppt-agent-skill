# architecture-elk-authoritative-layout

Mode: full (structural change, unfamiliar territory)

- **Status:** Draft
- **Depends on:** `elk-finalized-layout-roundtrip` — ELK's `FinalizedLayout` round-trip must be lossless (compound boundaries, port sides, edge sections and bend points fully preserved) before this spec can ship. That spec is a prerequisite; this spec assumes the round-trip contract is in place.

## Objective

Make ELK authoritative for architecture-beta placement, compound group boundaries,
port positions, and edge routes. Today `compile_architecture()` and
`_layout_architecture()` consume only the flat node (x, y) positions from the ELK
result, then recompute group bounding boxes and reroute every edge through the
legacy Python router. This discards ELK's compound geometry and port-respecting
orthogonal routing, producing incorrect port exit sides and edges that cross group
containers. The broad `except Exception: pass` guard silently hides ELK failures.

After this change, a successful ELK run produces the canonical `FinalizedLayout`
directly — no post-layout recomputation of groups or edges. The fallback produces
the same contract and self-identifies as `python-fallback` in diagnostics.

**Target fixture:** `tests/fixtures/architecture-complex.mmd`

## Boundaries

**What we are changing:**

- `scripts/mermaid_render/layout/architecture.py`
  - `compile_architecture()`: replace partial-copy ELK consumption with full
    `FinalizedLayout` pass-through; remove post-ELK calls to `_compute_group_bboxes`
    and `_route_edges` on the ELK path; replace `except Exception: pass` with
    typed exception handling (`ElkUnavailable` → fallback + warning,
    malformed/incomplete result → validation failure, unexpected → typed error).
  - `_build_arch_layout_graph()`: ensure the `LayoutGraph` `direction` field remains
    `"LR"` as a layout preference submitted to ELK, not as a post-layout routing
    assumption; allow mixed fixed-side port constraints to produce multiple rows.
  - New helper: `_arch_elk_to_finalized()` — converts the raw `FinalizedLayout`
    returned by `layout_with_elk()` to a fully annotated `ArchitectureDiagramLayout`,
    restoring service icon/label metadata that `_from_elk_result` does not carry.
  - New helper: `_arch_fallback_to_finalized()` — runs `_heuristic_arch_placement`,
    `_compute_group_bboxes`, and `_route_edges` to produce a `FinalizedLayout`
    self-labeled as `python-fallback` in `LayoutDiagnostics.warnings`.
  - `arch_to_finalized()`: accept an already-finalized `FinalizedLayout` pass-through
    for the ELK path (or delegate to the fallback builder), preserving ELK group
    labels, child group IDs, and local direction.

- `scripts/mermaid_render/layout/_strategies.py`
  - `_layout_architecture()`: mirror the same ELK-first / typed-exception / fallback
    structure; stop post-hoc rerouting on the ELK path.

- `scripts/mermaid_render/errors.py`
  - Add `ArchitectureLayoutError(NativeRenderError)` — typed error for unexpected
    exceptions in the architecture layout phase, carrying `diagram_type="architecture-beta"`.

- `tests/test_architecture_painter.py` — add `@requires_elk` acceptance tests
  for `architecture-complex` port sides, edge directions, containment, and backend
  provenance.

**What we are NOT changing:**

- `elk_adapter.py` (`layout_with_elk`, `_to_elk_json`, `_from_elk_result`) — no changes;
  the ELK adapter is treated as a black box that returns a `FinalizedLayout`.
- `_routing.py` — `_route_edges` remains; it is still used by the fallback path.
- `_renderer.py` — `_compute_group_bboxes` remains; it is still used by the fallback path.
- The `FinalizedLayout` and `LayoutDiagnostics` dataclasses — no structural changes.
- `layout_architecture_scene()` public entry point — signature unchanged.
- Python Sugiyama / heuristic grid placement logic — untouched.

## Acceptance Criteria

- [ ] AC1: For `architecture-complex`, `lb` exits EAST and `api` enters WEST (port side
  on the `lb -> api` edge confirmed in the routed `RoutedEdge`).
- [ ] AC2: For `architecture-complex`, `api -> db` exits EAST and enters WEST.
- [ ] AC3: For `architecture-complex`, `api -> cache` exits SOUTH and enters NORTH.
- [ ] AC4: For `architecture-complex`, `api -> queue` exits EAST and enters WEST.
- [ ] AC5: Every service node (`lb`, `api`, `db`, `cache`, `queue`) is fully contained
  within the `cloud` group boundary (service outer_bounds inside group boundary_bounds).
- [ ] AC6: No edge waypoint falls inside any service outer_bounds or within a group
  title strip (top `GROUP_PAD_Y_TOP` px of any group boundary).
- [ ] AC7: When ELK succeeds, `_compute_group_bboxes` and `_route_edges` are not called
  (confirmed by mock/monkeypatch in unit test).
- [ ] AC8: When ELK is unavailable (`ElkUnavailable`), the fallback produces a valid
  `FinalizedLayout` and records a warning in `LayoutDiagnostics.warnings` containing
  `"python-fallback"`.
- [ ] AC9: When the ELK result is incomplete (missing node IDs), a `ValueError` with
  a descriptive message is raised — not silently swallowed.
- [ ] AC10: When an unexpected exception occurs during the ELK layout phase,
  `ArchitectureLayoutError` is raised, wrapping the original cause.
- [ ] AC11: The selected layout backend (`"elk-js"` or `"python-fallback"`) is
  visible in `LayoutDiagnostics.warnings` of the returned `FinalizedLayout`.
- [ ] AC12: `pytest tests/` passes (zero new failures); existing tests for
  `architecture-beta` remain green on both ELK and non-ELK environments.

## Testing Strategy

Tests live in `tests/test_architecture_painter.py` under a new class
`TestArchitectureElkAuthoritative`.

**ELK-dependent tests** are marked `@requires_elk` (the project decorator that skips
when `MERMAID_LAYOUT_ENGINE=python` or Node/elkjs is absent). They load
`tests/fixtures/architecture-complex.mmd`, call `compile_architecture()`, and assert
the port-side and containment acceptance criteria (AC1–AC7).

**Fallback tests** run in all environments:
- Set `MERMAID_LAYOUT_ENGINE=python` via `monkeypatch.setenv`, call
  `compile_architecture()` on `architecture-complex`, and assert AC8 (warning present,
  valid layout returned).
- Use `monkeypatch` to patch `layout_with_elk` to return a result with missing node IDs,
  and assert AC9 raises `ValueError`.
- Use `monkeypatch` to raise an unexpected `RuntimeError` from `layout_with_elk`, and
  assert AC10 raises `ArchitectureLayoutError`.

**Provenance test** (AC11): inspect `LayoutDiagnostics.warnings` on the result of
`arch_to_finalized()` for either the ELK or fallback path and confirm the backend
string is present.

**No-reroute guard** (AC7): monkeypatch `_route_edges` and `_compute_group_bboxes` to
raise `AssertionError`; call `compile_architecture()` under a mocked successful ELK
run; assert no `AssertionError` is raised.
