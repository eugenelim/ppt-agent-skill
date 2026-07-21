# Plan: Flowchart Pipeline Finish

Note on atomicity: steps 1-12 land in one PR. The DEFINITION OF DONE requires the
compile-validate-render triad to be consistent; splitting would ship a half-migrated
pipeline. Each task is self-contained within the PR.

---

## Task 0: Write all failing tests (red phase)
**Depends on: none**
**Verification: TDD (red stubs)**

Tests in `tests/test_pipeline_contract.py` (all 10 must fail today):
- `test_validate_detects_node_overlap`
- `test_validate_detects_missing_route`
- `test_validate_detects_group_outside_canvas`
- `test_validate_detects_blocked_label`
- `test_to_html_does_not_call_render_graph_fragment` (monkeypatch raises)
- `test_to_html_calls_render_finalized` (monkeypatch verifies call)
- `test_gallery_invalid_fixture_exits_nonzero`
- `test_all_parsed_edges_appear_as_routed_or_failed`
- `test_finalized_layout_collections_cannot_be_mutated`
- `test_no_forbidden_runtime_dependency`

Approach:
- Write the test bodies; do NOT implement fixes
- Each test should FAIL (AssertionError or NotImplementedError), not ERROR

Done when: `pytest tests/test_pipeline_contract.py` shows all 10 FAILED (not ERROR).

---

## Task 1: Add new geometry IR types
**Depends on: Task 0**
**Verification: TDD**

Tests:
- `test_routing_failure_is_frozen`: `RoutingFailure` frozen dataclass with `edge_id`, `reason`, `src_node_id`, `dst_node_id`
- `test_layout_metadata_is_frozen`: `LayoutMetadata` frozen with `direction`, `node_count`, `group_count`, `edge_count`, `algorithm`
- `test_compiled_flowchart_is_frozen`: `CompiledFlowchart(layout, validation, metadata)` frozen

Approach:
- Add `RoutingFailure`, `LayoutMetadata`, `CompiledFlowchart` to `_geometry.py`
- Add `routing_failures: tuple[RoutingFailure, ...]` field to `FinalizedLayout`
- Remove `LayoutResult` (stub duplicate); update/remove any test files that import or construct `LayoutResult` directly
- Update `layout/__init__.py` exports

Done when: 3 tests above pass.

---

## Task 2: Freeze FinalizedLayout collections
**Depends on: Task 1**
**Verification: TDD**

Tests:
- `test_finalized_layout_node_layouts_immutable`: `layout.node_layouts[k] = x` raises `TypeError`
- `test_finalized_layout_group_layouts_immutable`: same for `group_layouts`
- `test_finalized_layout_collections_cannot_be_mutated` (from Task 0): now passes

Approach:
- Change `FinalizedLayout.node_layouts` type to `MappingProxyType[str, NodeLayout]`
- Change `FinalizedLayout.group_layouts` type to `MappingProxyType[str, GroupLayout]`
- All construction sites wrap plain dicts with `types.MappingProxyType(d)` before assignment
- Update any existing tests that build FinalizedLayout directly

Done when: 3 tests pass.

---

## Task 3: Add faithful=False to public API
**Depends on: Task 0**
**Verification: TDD + goal-based**

Tests:
- `test_faithful_true_preserves_direction`: `to_html(LR source, faithful=True)` produces LR, not auto-switched
- `test_faithful_true_suppresses_icons`: `to_html(node with icon keyword, faithful=True)` has no injected icon
- `test_faithful_true_suppresses_legend`: `to_html(src, faithful=True)` has no legend strip
- `test_faithful_false_default`: existing behavior unchanged

Approach:
- Add `faithful: bool = False` to `to_html()`, `to_svg()`, `to_png()` in `mermaid_render/__init__.py`
- Forward `faithful` as `RenderOptions(faithful_mermaid=faithful)`; `_dispatch()` already accepts `opts`
- Wire gallery script to call `faithful=True`

Done when: 3 tests pass; existing faithful_mermaid tests unchanged.

---

## Task 4: Rename algorithm classes, add IsotonicCoordinateAssigner
**Depends on: Task 0**
**Verification: TDD**

Tests:
- `test_slack_tightening_ranker_exists_and_implements_protocol`
- `test_network_simplex_ranker_removed_from_public_exports`
- `test_isotonic_coordinate_assigner_implements_protocol`
- `test_pav_monotone_projection`: given target values `[3, 1, 2]` with uniform weights, result is non-decreasing and minimizes sum-of-squares
- `test_isotonic_assigner_no_overlap_after_assign`: nodes in same rank with 0 col_gap still separated

Approach:
- Rename `NetworkSimplexRanker` → `SlackTighteningRanker` in `_layered.py`; remove from `__init__.py` exports
- Add `IsotonicCoordinateAssigner`:
  - Build preferred center for each rank-column pair from median of connected-neighbor centers
  - PAV isotonic projection: left-to-right sweep; merge blocks that violate separation; block average
  - Downward sweep then upward sweep; take average
  - Round only after final compaction
- Add `_pav_project(targets, min_separations) -> list[float]` helper (pure function, testable)
- Do NOT yet wire as production default (wait until Task 5 owns the production-default switch after compound layout is ready)
- Remove `BrandesKoepfAssigner` from `_layered.py` and update all in-repo callers (same treatment as `NetworkSimplexRanker`)
- Update `__init__.py` exports to remove both `NetworkSimplexRanker` and `BrandesKoepfAssigner`

Done when: 5 tests pass.

---

## Task 5: Implement _compile_flowchart() and wire to_html/validate
**Depends on: Tasks 1, 2, 3, 4**
**Verification: TDD**

Tests:
- `test_compile_flowchart_returns_compiled_flowchart`
- `test_compile_flowchart_metadata_has_node_count`
- `test_to_html_calls_compile_flowchart_not_dispatch` (verify via attribute, not monkeypatch)
- `test_validate_calls_compile_flowchart` (validate() reuses same pipeline, not independent layout)
- `test_coordinate_assigner_switch`: switch production default to `IsotonicCoordinateAssigner` here

Approach:
- Implement `_compile_flowchart(src, width_hint, options) -> CompiledFlowchart` in `_strategies.py`
  - Calls full pipeline: parse → normalize → measure → cycle-break → rank (LongestPathRanker)
    → dummy insert → crossing-minimization (BarycentricTransposeOrderer) → coordinate assignment
    (IsotonicCoordinateAssigner) → inner-direction fixup → route → label placement
    → final canvas operation (see Task 10) → freeze FinalizedLayout → validate → CompiledFlowchart
  - **Algorithm values will change** vs legacy path; snapshot tests may need re-baselining
- Wire `_dispatch` for the 6 in-scope types to call `_compile_flowchart` → `render_finalized`
- Update `to_html()` and `validate()` in `mermaid_render/__init__.py` to call `_compile_flowchart`
- Other diagram types (sequence, Gantt, pie, etc.) remain unchanged

Done when: 5 tests pass; `test_fix_flowchart.py`, `test_fix_state.py`, `test_fix_er.py`, `test_fix_architecture.py` still pass (re-baselined if coordinate values changed).

---

## Task 6: Cut to_html() to render_finalized() only
**Depends on: Task 5**
**Verification: TDD + monkeypatch**

Tests:
- `test_to_html_does_not_call_render_graph_fragment` (from Task 0): now passes
- `test_to_html_calls_render_finalized` (from Task 0): now passes
- `test_flowchart_renders_html`: basic render produces `<div` with node ids
- `test_state_diagram_renders_html`: stateDiagram-v2 still renders correctly

Approach:
- Confirm `_compile_flowchart` (Task 5) never calls `_render_graph_fragment`
- Verify `render_finalized(layout.layout)` is in the path
- Non-flowchart types unchanged

Done when: all 4 tests pass.

---

## Task 7: Implement validate_finalized_layout()
**Depends on: Task 5**
**Verification: TDD**

Tests (from Task 0 + new in `tests/test_validation.py`):
- `test_validate_detects_node_overlap` (from Task 0)
- `test_validate_detects_missing_route` (from Task 0): a parsed edge absent from both `routed_edges` and `routing_failures` → error (edge-count reconciliation check)
- `test_validate_detects_group_outside_canvas` (from Task 0)
- `test_validate_detects_blocked_label` (from Task 0)
- `test_validate_detects_routing_failure`
- `test_validate_nonpositive_canvas`
- `test_validate_child_outside_parent`
- `test_validate_zero_length_segment`
- `test_validate_port_not_on_boundary`
- `test_validate_route_through_unrelated_node`
- `test_validate_label_intersects_unrelated_node`
- `test_validate_label_intersects_other_label`
- `test_validate_intersecting_group_title_boxes`
- `test_validate_marker_outside_canvas`
- `test_validate_ok_simple`: simple 2-node flowchart → no errors

Approach: Implement `validate_finalized_layout(layout: FinalizedLayout) -> ValidationResult` in `_geometry.py`.

All error checks:
1. Canvas positive (w > 0, h > 0)
2. routing_failures entries → one error per failure
2b. Edge-count reconciliation: `metadata.edge_count` must equal `len(routed_edges) + len(routing_failures)`; any shortfall → "missing route for edge X" error
3. Every node outer_bounds inside canvas_bounds
4. Every group boundary_bounds inside canvas_bounds
5. Every label_layout bounds inside canvas_bounds
6. Every marker/decoration outside canvas → error
7. No two ordinary non-dummy node outer_bounds overlap (pairwise)
8. Each child node/group inside parent group boundary_bounds
9. Intersecting group-title boxes (group label bounds overlap adjacent group labels)
10. Port not on declared boundary (port position outside node outer_bounds)
11. Route through unrelated node interior (any waypoint segment crosses unrelated node outer_bounds)
12. Label intersecting unrelated node, title, or another label (bounds overlap)
13. Route has ≥ 2 waypoints; no zero-length consecutive-waypoint segment
Warnings:
14. Clearance below threshold (< 4px between nearest node bounds) → warning

Done when: all 15 tests pass.

---

## Task 8: Recursive compound layout
**Depends on: Task 6**
**Verification: TDD**

Tests in `tests/test_regression_fixtures.py`:
- `test_nested_group_containment`
- `test_sibling_groups_no_overlap`
- `test_empty_nested_group`
- `test_cross_group_edge_routing` (routing test: ports on crossed group boundaries)
- `test_five_nested_groups`
- `test_compound_item_return_type`: compound_item has (bounds, member_rects, child_compounds, title_strip_h)

Approach:
- Define `_CompoundItem(bounds: Rect, member_rects: dict[str, Rect], child_compounds: dict[str, '_CompoundItem'], title_strip_h: float)` — consistent field names used in all tests and code
- Implement `_layout_compound(nodes, edges, groups, direction, ...) -> dict[str, _CompoundItem]`
  - Sort groups by depth (deepest first: depth = count of ancestor groups)
  - For each group scope: extract member nodes and immediate child groups (already laid out → treated as fixed-size items)
  - Run full rank/order/position pipeline over items in this scope
  - Translate child-compound positions into this scope's coordinate space
  - Reserve title strip at top of group box
  - Compute group box from items + title strip
  - Return the completed `_CompoundItem` for this group
- **Cross-group edge LCA routing**: detect when src and dst are in different groups; compute LCA scope; allocate legal entry/exit ports on each crossed group boundary; route each segment within its permitted region
- Remove `_separate_groups_lr()`, `_separate_groups_tb()`, `_push_nonmembers_out_of_groups_lr()` from `_renderer.py` and `_strategies.py`
- Remove them from `layout/__init__.py` exports (they are currently re-exported)
- Update `_compile_flowchart` to call `_layout_compound` for the coordinate/group phase

Done when: all 6 tests pass; no existing group-related tests regress.

---

## Task 9: Routing integration
**Depends on: Task 8**
**Verification: TDD**

Tests:
- `test_routing_uses_face_ports`: edge endpoints on legal node faces
- `test_parallel_links_use_lanes`: 8 parallel links have distinct port offsets
- `test_routing_failure_on_impossible_route`: truly impossible route → `RoutingFailure`
- `test_no_edge_silently_disappears` (from Task 0): now passes
- `test_label_shelf_on_blocked_label`
- `test_cross_group_boundary_ports`: cross-group edge ports land on group boundaries at crossing

Approach:
- Modify `_route_edges()` to call `allocate_face_ports()` for each edge endpoint
- Change return type to `tuple[list[RoutedEdge], list[RoutingFailure]]`
- Label placement: generate collision-free candidates; reject bad ones; label shelf fallback; retry ≤ 2; then RoutingFailure
- Update `_compile_flowchart` to collect both lists into `FinalizedLayout`
- No edge may silently disappear: every original edge → routed_edges OR routing_failures

Done when: all 6 tests pass.

---

## Task 10: One final canvas operation
**Depends on: Task 9**
**Verification: TDD**

Tests:
- `test_single_canvas_translation`: all drawables inside canvas_bounds
- `test_no_negative_coordinates_in_finalized`: all bounds have x,y ≥ 0 after finalization
- `test_canvas_includes_all_drawables`: canvas_bounds == union(all drawable bounds) + padding
- `test_gallery_invalid_fixture_exits_nonzero` (from Task 0): now passes after validate is wired

Approach:
- After all layout + routing + label placement:
  - Collect all drawable bounds (node outer_bounds, group boundary_bounds, label bounds, route waypoint envelopes)
  - Compute `min_x = min(b.x for b in all_bounds)`, `min_y = min(b.y for b in all_bounds)`
  - `dx = CANVAS_PAD - min_x`, `dy = CANVAS_PAD - min_y`
  - Translate every drawable by `(dx, dy)` using `.translate(dx, dy)` on each frozen IR object
  - Set `canvas_bounds = Rect(0, 0, max_x + CANVAS_PAD, max_y + CANVAS_PAD)`
  - Remove node-only canvas recomputation in `_layout_graph_topology`
  - Remove terminal-circle-only x-shift (center it during position assignment instead)

Done when: 4 tests pass.

---

## Task 11: Regression fixtures
**Depends on: Tasks 6, 7, 8, 9, 10**
**Verification: TDD**

Tests in `tests/test_regression_fixtures.py` (extend from Task 8):
- `test_five_nested_groups_long_titles`
- `test_parent_with_direct_nodes_and_child_groups`
- `test_sibling_groups_unequal_dimensions`
- `test_cross_group_edges`
- `test_eight_parallel_links`
- `test_six_self_loops`
- `test_impossible_exceptional_route`
- `test_label_requiring_shelf`
- `test_mixed_node_sizes_64_220px`
- `test_terminal_circle_beside_wide_node`
- `test_multiline_shapes_cylinder_trapezoid_flag_diamond`
- `test_cjk_labels`
- `test_emoji_wide_narrow_glyphs`
- `test_determinism_fixed_seed` (random.Random(42))
- `test_no_overlap_random_seed` (random.Random(seed), 10 seeds)

Verify for each: no overlap, group containment, legal ports, no missing edge, collision-free labels, all inside canvas.

Done when: all 15 tests pass.

---

## Task 12: Import boundary enforcement
**Depends on: none**
**Verification: TDD**

Tests in `tests/test_import_boundary.py`:
- `test_no_networkx_import`
- `test_no_numpy_in_layout`
- `test_no_scipy_import`
- `test_no_shapely_import`
- `test_no_graphviz_import`
- `test_no_pygraphviz_import`
- `test_no_pydot_import`
- `test_no_subprocess_in_layout`
- `test_no_playwright_in_to_html_path` (complement to subprocess test in test_mermaid_render_guards.py)

Approach:
- Walk AST of all `scripts/mermaid_render/layout/*.py` files
- Use `ast.walk(ast.parse(source))` to find `Import` and `ImportFrom` nodes
- Check module names against forbidden list

Done when: all 9 tests pass.

---

## backlog.md entries to add after this PR

- `adt-pure-python-layout` heading already added to `docs/backlog.md` (Blocker 1 fix)
- `strategies-module-split` heading already added to `docs/backlog.md`
- Multiline shape fixtures beyond cylinder/diamond (trapezoid, flag, hexagon variants)
