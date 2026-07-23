# Adversarial Review — Round 2 (post-EXECUTE)

**Reviewer:** adversarial-reviewer  
**Phase:** post-EXECUTE (implementation + tests complete)  
**Date:** 2026-07-22

## Findings

### Blocker 1 — AC1–AC3 tests didn't assert ELK path was exercised
`test_empty_subgraph_groups_non_overlapping` and `test_groups_complex_member_containment` were marked `@requires_elk` (skipped when ELK absent) but didn't assert `metadata.algorithm == "ELK-layered"`. The tests would silently pass if ELK fell back to Python, masking the fix.

**Fix applied:** Added `assert compiled.metadata.algorithm == "ELK-layered"` to both tests.

### Blocker 2 — Python-path strict tests silently dropped
`TestNestedGroupAsUnit` previously had `test_inner_members_at_same_y_as_outer_direct` and `test_inner_group_to_left_of_outer_direct` with strict coordinate equality. These were replaced with looser containment checks without preserving the strict variant under a Python-only skip guard, meaning Python-path coverage was silently dropped.

**Fix applied:** Added `test_python_path_same_y` and `test_python_path_inner_left_of_outer_direct` with `@pytest.mark.skipif(_elk_available(), reason="ELK alters positions")` to preserve Python-path strict coverage.

### Blocker 3 — `test_lr_inner_nodes_share_top` too strict for ELK
The test asserted `abs(top_ingest - top_transform) == 0` (integer equality). ELK places nodes at floating-point coordinates that may differ by 1–2 px due to box centering vs strict grid. This would fail when ELK is available.

**Fix applied:** Relaxed to `<= 2` pixel tolerance: `abs(top_ingest - top_transform) <= tol and abs(top_transform - top_load) <= tol`.

### Minor — Spec Testing Strategy had old method names
The spec referenced `test_inner_members_at_same_y_as_outer_direct` and `test_inner_group_to_left_of_outer_direct` which were replaced.

**Fix applied:** Updated spec to use new method names (`test_inner_members_within_outer_group`, `test_inner_group_within_outer_group`, `test_python_path_same_y`, `test_python_path_inner_left_of_outer_direct`).

## Outcome

All four findings fixed. Gates: 90 passed, 7 skipped. Clean — ready to commit.
