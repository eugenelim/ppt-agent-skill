# Renderer Hardening 2026-07 — spec

Mode: full (multi-feature, dependent tasks; structural changes across `_geometry.py`, `_layout.py`, `_routing.py`, `_strategies.py`, `compare_gallery.py`; new module structure; new test file; P0–P2 of the post-review hardening document)

**Status:** Implementing

## Objective

Implement the P0, P1, and partial P2/P4 items from the renderer hardening review (July 2026). The review identified: a vacuous test assertion that can never fail, a label-placement fallback that knowingly accepts overlap, tests that entrench incorrect clamping behavior, a gallery that ignores the classifier it already defines, geometry types that exist only as TODOs, A* routing that silently produces straight-through lines on routing failure, parallel-port allocation that can put endpoints outside the node face, back-edge detection that uses a fixed NODE_W constant, and a cycle-breaker that reverses more edges than necessary.

## Background

The review document is committed at `.context/attachments/2O5dZK/pasted_text_2026-07-20_22-43-38.txt`. The prioritized fixes are P0 (observability and test correctness), P1 (complete geometry IR), P4 partial (routing safety and port bounds), and P2 partial (greedy feedback-arc). P2 compound layout, P3 channel routing, and the full LayoutResult pipeline are deferred to follow-up sessions.

## Acceptance Criteria

### P0 — Observability and test correctness

- [ ] **AC-P0.1 (vacuous hexagon assertion)** `test_hexagon_width_height_independent` uses `assert w != h` not `assert w != h or True`. The assertion is actually capable of failing.

- [ ] **AC-P0.2 (LabelPlacement dataclass)** `_routing.py` exports `LabelPlacement(box: Rect | None, reroute_required: bool)` frozen dataclass. `_best_label_pos` returns `LabelPlacement`. When `candidates` is empty, returns `LabelPlacement(box=None, reroute_required=True)` and does NOT append to `placed`. When all candidates are blocked by node obstacles (no clear candidate), returns `LabelPlacement(box=<least-overlap chip rect>, reroute_required=True)` and appends to `placed` (preserving visual placement while signalling rerouting is needed). When placement succeeds without overlap, returns `LabelPlacement(box=<chip rect>, reroute_required=False)` and appends to `placed`. All nine call sites in `_routing.py` (lines 255, 663, 679, 699, 715, 766, 793, 820, 858) are updated to unwrap the result. Tests: `test_all_blocked_returns_fallback` asserts `placement.box is not None` and `placement.reroute_required is True`; `test_empty_candidates_returns_none_placement` asserts `box is None` and `reroute_required is True` for empty candidate list.

- [ ] **AC-P0.3 (loop-clamping test removed)** `test_tb_left_face_loop_canvas_clamped` is updated to no longer assert that negative x coordinates are prevented. The test documents the known provisional-coordinate behavior and defers finalization-pass validation to the backlog. The existing `test_self_loop_canvas_not_exceeded` is updated to only check positive paths (not left-face self-loops which can be provisional negative). Backlog entry added for the finalization pass.

- [ ] **AC-P0.4 (ValidationResult + validate stub)** `_geometry.py` exports `ValidationResult(errors: tuple[str, ...] = (), warnings: tuple[str, ...] = ())` frozen dataclass with `.status` property returning `"ok"` / `"warning"` / `"invalid"`. `mermaid_render` package exposes `validate(src: str) -> ValidationResult` (stub returning empty for now). Tests: `ValidationResult` status property, public import of `validate`.

- [ ] **AC-P0.5 (gallery uses _classify_status)** `_build_gallery()` calls `mermaid_render.validate(src)` after a successful render and passes `geometry_errors` / `geometry_warnings` to `_classify_status`. The stored status (not just `ours_ok: bool`) is threaded through the result tuple and used for nav badges, header counts, and section badges. A committed test monkeypatches `_classify_status` to return `"invalid"` and asserts `main()` exits with code 1.

- [ ] **AC-P0.6 (compare_gallery moved)** `scripts/compare_gallery.py` is moved to `tools/compare_gallery.py`. The gallery still runs correctly from the new path. `scripts/` no longer contains a tool that invokes `mmdc`. Tests: `tools/compare_gallery.py --help` succeeds; `scripts/compare_gallery.py` does not exist.

### P1 — Complete geometry IR

- [ ] **AC-P1.1 (geometry frozen dataclasses)** `_geometry.py` exports the full set of frozen, slotted geometry types:
  - `Point(x: int, y: int)`
  - `Port(point: Point, side: str, slot: int, lane: int)`
  - `PortAllocation(offset: int, lane: int)` — for face-port allocation
  - `GroupLayout(box: Rect, title_box: Rect)`
  - `RoutedEdge(edge_id: int, src: str, dst: str, points: tuple[Point, ...], src_port: Port, dst_port: Port, label_box: Rect | None, marker_boxes: tuple[Rect, ...])`
  - `LayoutResult(node_boxes: Mapping[str, Rect], groups: Mapping[str, GroupLayout], edges: tuple[RoutedEdge, ...], decoration_boxes: tuple[Rect, ...], canvas: Rect)`
  Tests: all types construct without error; frozen mutation raises `FrozenInstanceError`; `LayoutResult` and `RoutedEdge` round-trip through construction.

### P4 partial — Routing safety and port bounds

- [ ] **AC-P4.1 (A* routing failure returns None)** `_astar_route` returns `None` when no path is found instead of `[(sx, sy), (dx, dy)]`. The caller in `_route_edges` retries with perimeter margins 16, 32, 64, 128 px before accepting failure. When all retries fail, the edge is omitted from `result` (not drawn as a direct line through obstacles). Tests: (a) `test_astar_no_path_returns_none` — heavily blocked grid returns `None`; (b) `test_perimeter_retry_finds_path` — blocked obstacle with 16 px margin clearance, retry finds a valid 3-segment path; (c) `test_routing_failure_omits_edge` — `_route_edges` called with two nodes completely surrounded by obstacles produces no result entry for that edge.

- [ ] **AC-P4.2 (allocate_face_ports)** `_routing.py` exports `allocate_face_ports(face_length: int, count: int, *, padding: int = 8, min_step: int = 6) -> tuple[PortAllocation, ...]`. All returned offsets satisfy `0 <= offset <= face_length`. When `count > capacity`, excess edges cycle slot indices and increment `lane`. `_fan_offset` is updated to clamp its output to `[0, node_w]`. Tests: `test_allocate_face_ports_bounds`, `test_allocate_face_ports_overflow` (8 ports on 42 px face: first 5 have lane=0, next 3 have lane=1), `test_fan_offset_clamped`.

- [ ] **AC-P4.3 (node_rect accessor)** `_routing.py` exports `node_rect(n: _Node) -> Rect`. Back-edge detection (line 730) uses `node_rect` center comparison: `dst_box.x + dst_box.w / 2 < src_box.x` (not `d.x + NODE_W // 2 < s.x`). Reverse-edge routing shortcut (line 739) uses `node_rect(s).x >= node_rect(d).x1` (source left edge ≥ destination right edge) instead of `s.x >= d.x + NODE_W`. Tests: `test_node_rect_wide_card`, `test_back_edge_detection_center`, `test_reverse_edge_detection_center`.

### P2 partial — Greedy feedback-arc ordering

- [ ] **AC-P2.1 (greedy feedback-arc)** `_break_cycles` in `_layout.py` is replaced with an Eades-style greedy FAS: source/sink stripping, then greedily removing the vertex maximizing `out_degree - in_degree`. Declaration order is the deterministic tie-breaker. Tests: (a) `test_greedy_fas_correctness` — after `_break_cycles`, the forward-edge subgraph (non-reversed edges) contains no directed cycles; (b) `test_greedy_fas_deterministic` — calling `_break_cycles` twice on the same graph produces identical results; (c) `test_greedy_fas_single_cycle` — for a linear cycle `A→B→C→A`, exactly 1 edge is reversed.

### Dependency enforcement tests

- [ ] **AC-DEP.1 (isolated interpreter)** `test_to_html_runs_without_site_packages` runs `to_html` in a subprocess with `-I -S` flags (no user site-packages) and asserts exit code 0 and `data-node-id` in output.

- [ ] **AC-DEP.2 (import allowlist)** `test_layout_import_allowlist` AST-scans all `.py` files under `scripts/mermaid_render/layout/` and asserts no import from a forbidden set: `networkx`, `numpy`, `scipy`, `shapely`, `graphviz`, `pygraphviz`, `pydot`, `PIL`, `playwright`.

- [ ] **AC-DEP.3 (no subprocess)** `test_no_subprocess_in_runtime_renderer` AST-scans all `.py` files under `scripts/mermaid_render/layout/` and asserts `subprocess` is not imported.

## Boundaries

**In scope:**
- `scripts/mermaid_render/layout/_geometry.py` — geometry IR types, ValidationResult
- `scripts/mermaid_render/layout/_routing.py` — LabelPlacement, A* fallback, allocate_face_ports, node_rect, back-edge fix
- `scripts/mermaid_render/layout/_layout.py` — greedy FAS replacing DFS cycle breaker
- `scripts/mermaid_render/layout/_strategies.py` — `_dispatch_validate` stub
- `scripts/mermaid_render/__init__.py` — expose `validate()`
- `scripts/compare_gallery.py` → move to `tools/compare_gallery.py`
- `tests/test_flowchart_geometry.py` — fix P0.1–P0.3 test assertions
- `tests/test_routing_astar.py` — A* failure and perimeter retry tests
- `tests/test_compare_gallery.py` (new) — gallery exit-code test
- `tests/test_dependencies.py` (new) — dependency enforcement tests

**Not in scope (explicitly deferred):**
- Recursive compound layout (P2 main) — requires fundamental restructuring
- PAVA coordinate assignment (P2) — complex, needs dedicated sprint
- Rank-gap channel routing replacing A* (P3) — requires LayoutResult pipeline
- Full renderer serialization-only restructuring (P3) — blocked by pipeline split
- `to_html(faithful=...)` public parameter — deferred with pipeline
- Compound boundary ports (P3)
- Label shelves for rerouting (P4 deferred)
- Score-based self-loop side selection (P4 deferred)
- Full NODE_W leakage cleanup in `_assign_coordinates` (P4 deferred)
- Median sweeps + Fenwick crossing counter (P2 deferred, needs dedicated sprint)
- Remove self-loop clamping (P4 deferred — requires finalization pass first)

## Declined patterns

- **Split `to_html()` into layout + render phases now**: requires the full LayoutResult pipeline to be complete first. The `validate()` stub preserves the architecture without the restructure.
- **Immediately remove self-loop clamping**: would produce negative coordinates without a finalization pass. Deferred.
- **AST-based import scanner as a standalone tool**: implemented as tests only; no need for a separate script.
- **Change `_label_on_longest` return type to `LabelPlacement`**: too many callers to update in one change; `_label_on_longest` stays as `(lx, ly)` unwrapper.

## Testing strategy

All new logic: TDD (write test first, observe red, implement green).
Existing test fixes: modify tests to correctly express desired invariants, then confirm they pass (or document failure in backlog).
Dependency tests: new test file `tests/test_dependencies.py` using subprocess and ast.
Move of `compare_gallery.py`: goal-based check (`python tools/compare_gallery.py --help`).

Spec: docs/specs/renderer-hardening-2026-07/spec.md
