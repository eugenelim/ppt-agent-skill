# Spec: Compound Layout — ELK First-Class Subgraphs

Mode: full (multi-file structural change to primary layout path; unfamiliar ELK compound-node territory; multi-feature)

**Status:** Shipped
**Constrained by:** `docs/adr/001-elk-layout-engine.md` — ELK is optional; Python Sugiyama is the mandatory fallback. AC1–AC3 verification requires the ELK toolchain (Node.js + elkjs 0.12.0); tests are `@requires_elk` and assert `metadata.algorithm == "ELK-layered"`.

## Objective

Make subgraphs first-class compound layout nodes in the ELK path. Currently the ELK path:
1. Falls back to Python Sugiyama when any subgraph declares a `direction` that differs from the outer direction (`_has_inner_direction` guard).
2. Recomputes group bounding boxes from node positions after ELK via `_compute_group_bboxes`, discarding ELK's own compound-node bounds.
3. Places empty compound nodes at canvas origin (0, 0).

All three of these prevent correct ELK compound layout.

**Targets**: `flowchart-empty-subgraph`, `flowchart-groups-complex`, `flowchart-inner-direction`.

## Acceptance Criteria

- [ ] **AC1 — Empty subgraph non-origin placement** *(requires ELK; `@requires_elk`)*: `flowchart-empty-subgraph` renders both groups with non-zero-area bboxes at distinct, non-overlapping positions (neither at canvas origin). (deferred: backlog-compound-elk-ac1-ac3)
- [ ] **AC2 — Groups-complex containment** *(requires ELK; `@requires_elk`)*: `flowchart-groups-complex` renders three groups each fully containing their declared members. (deferred: backlog-compound-elk-ac1-ac3)
- [ ] **AC3 — Inner-direction LR ordering** *(requires ELK; `@requires_elk`)*: `flowchart-inner-direction` renders ingest.x < transform.x < load.x and source.y < ingest.y < sink.y. (deferred: backlog-compound-elk-ac1-ac3)
- [x] **AC4 — No regressions on basic render**: All three fixtures produce valid HTML with all expected node labels; `pytest tests/` exits 0 (4487 passed, 100 skipped).
- [x] **AC5 — Existing test suite passes**: `pytest tests/test_compound_layout.py tests/test_elk_adapter.py tests/test_flowchart_geometry.py` exits 0 with updated tests.

## Boundaries

**What we're changing:**
- `elk_adapter.py`: `_to_elk_json` — per-group `elk.direction`, empty-group minimum size
- `_strategies.py`: remove `_has_inner_direction` ELK guard; populate `_elk_grp_bboxes` from ELK result; remove post-hoc `_compute_group_bboxes` + containment-expansion on ELK path
- `tests/test_compound_layout.py`: update or relax tests that assumed Python-path positions for inner-direction diagrams

**What we're NOT changing:**
- Python Sugiyama fallback path: `_compute_group_bboxes`, `_separate_groups_*`, `_push_nonmembers_out_of_groups_lr` remain intact for the Python path.
- `_layout.py`: `_apply_inner_direction_positions` stays — it's independently unit-tested.
  <!-- SUPERSEDED by eight-case-parity-ci-and-cleanup AC4/AC10 (ini-003 item 6): this
  function was the unconditional inner-direction / post-global-placement fixup that
  the bottom-up Python compound layout (item 3) replaced. It became dead production
  code and was deleted along with its TestApplyInnerDirection unit tests. This
  frozen bullet no longer reflects the code. -->

- `_routing.py`: no changes.
- `_from_elk_result` in `elk_adapter.py`: no changes (already builds correct group layouts).

## Testing Strategy

Verification mode: **construction tests** (render fixture → assert geometry invariants on `FinalizedLayout`).

Each target fixture is tested via `_compile_flowchart(src, ...)`. Group bounds: `layout.group_layouts[gid].boundary_bounds`. Node positions: `layout.node_layouts[nid].outer_bounds`.

Tests in `tests/test_compound_layout.py`:
1. `test_empty_subgraph_groups_non_overlapping` — **ELK-only** (`@pytest.mark.skipif` when elkjs absent): both groups non-zero area, neither at (0,0), no AABB overlap.
2. `test_groups_complex_member_containment` — **ELK-only**: for each group, all declared member node bboxes inside group bbox (1 px tolerance for int-truncated node coords).
3. `TestInnerDirectionFixture.*` — unchanged (correct LR-ordering and TB-outer invariants; ELK-skipif when unavailable for geometry tests).
4. `TestTBInnerLROuter` — keep `test_tb_inner_members_same_x` (ELK TB-inner places P, Q, R in one column → same x). Keep all three sub-tests.
5. `TestNestedGroupAsUnit.test_inner_members_within_outer_group` (replaces `test_inner_members_at_same_y_as_outer_direct`) — containment: A, B, C, D all within Outer group boundary. Strict same-y preserved as `test_python_path_same_y` (Python-path-only).
6. `TestNestedGroupAsUnit.test_inner_group_within_outer_group` (replaces `test_inner_group_to_left_of_outer_direct`) — Inner group boundary within Outer boundary. Strict left-of preserved as `test_python_path_inner_left_of_outer_direct` (Python-path-only).
7. `TestRecursiveGroupLayoutDeterminism` — keep (ELK is deterministic).

## Task List

1. **[elk_adapter.py] Per-compound-node elk.direction** — In `_to_elk_json`, add `"elk.direction"` to each group's `layoutOptions` based on `g.local_direction or graph.direction`. Depends on: none.

2. **[elk_adapter.py] Empty-group minimum size** — For groups with no children in the ELK child map, set `g_node["width"]` and `g_node["height"]` to `max(label_w + 2*pad_x, 80+2*pad_x) × (pad_top + pad_bot)`. Depends on: none.

3. **[_strategies.py] Remove _has_inner_direction guard** — Delete the `if _has_inner_direction: raise` block. Keep `_has_inner_direction` variable if used in logging, else remove. Depends on: tasks 1 and 2.

4. **[_strategies.py] Populate _elk_grp_bboxes from ELK result** — After ELK succeeds, extract `[x, y, x+w, y+h]` from `_elk_result.group_layouts` into `_elk_grp_bboxes`. Replace the `_compute_group_bboxes` call in the ELK path with `_grp_bboxes = _elk_grp_bboxes or {}`. Recompute canvas from group + node extents. Remove the member-containment expansion loop. Depends on: task 3.

5. **[tests] Strengthen and fix compound layout tests** — Add `test_empty_subgraph_groups_non_overlapping` and `test_groups_complex_member_containment`. Relax `TestTBInnerLROuter.test_tb_inner_members_same_x` (strict equality) and `TestNestedGroupAsUnit.test_inner_members_at_same_y_as_outer_direct` to positional inequalities that ELK satisfies. Depends on: task 4.

## Assumptions

- ELK 0.12.0 positions compound nodes (even empty ones) when given explicit `width`/`height`.
- ELK layered algorithm with `elk.hierarchyHandling=INCLUDE_CHILDREN` routes cross-hierarchy edges (source→ingest, load→sink) correctly, placing source above and sink below the Pipeline group in TB outer layout.
- `_from_elk_result` already returns correct absolute positions for nested nodes (offset accumulation in `_visit`).

**Declined:**
- Adding a `compound-routing` helper for boundary gates: ELK handles this natively with INCLUDE_CHILDREN; no new layer needed.
- Removing `_compute_group_bboxes` entirely: it remains valid for the Python fallback path; removing it would require updating many tests.
- Changing `_from_elk_result`'s group layout building: it already builds correct `GroupLayout` with `boundary_bounds`; we just need to surface those bounds to the downstream `_build_group_layouts_ir` call.
- Implementing port-based cross-boundary routing: ELK's INCLUDE_CHILDREN handles this automatically without explicit port specs.
