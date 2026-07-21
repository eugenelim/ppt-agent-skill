# Adversarial Review Pass 2 — renderer-hardening-2026-07

Pass 1 Blockers all resolved. New issues found.

## Blockers

**1. Task 7 enumerates only one `_astar_route` caller (singular "Find the caller").** `plan.md`. There are TWO call sites: LR path at `_routing.py:899` (`_pts_lr = _astar_route(...)` + `if len(_pts_lr) >= 2` at line 901) and TB path at `_routing.py:972` (`_pts = _astar_route(...)` + `if len(_pts) >= 2` at line 974). Both also call `_accumulate_occupied(_pts*)` immediately after. When `_astar_route` returns `None`, both crash with `TypeError: object of type 'NoneType' has no len()`. Fix: enumerate both call sites and wrap each with the perimeter-retry / `continue`-on-None pattern.

**2. `test_routing_failure_omits_edge` is vacuous — asserts only `isinstance(result, list)`.** `plan.md`. The test creates two clear-space nodes with no obstacles, so routing succeeds; the assertion can never fail. Fix: use a full-surround obstacle `[(0, 0, 500, 500)]` with source/dest deep inside it so both A* and all perimeter retries fail, then assert the result is `None` from `_route_perimeter`.

**3. AC-P4.3 reverse-edge predicate stated as `src_box.x1 <= dst_box.x` (wrong direction).** `spec.md:48`. The original `_routing.py:739` check `s.x >= d.x + NODE_W` means "source LEFT edge is right of destination's right edge (fixed width)". The correct fix is `node_rect(s).x >= node_rect(d).x1` (not `src_box.x1 <= dst_box.x` which is the opposite). Plan Approach already has the correct formula but the spec, test assertion, and plan test all use the wrong direction. Fix: correct spec, test, and plan to `src_rect.x >= dst_rect.x1`.

## Concerns

**4. All-blocked label fallback silently moves labels to canvas origin.** `spec.md:21`, `plan.md:84-86`. Returning `LabelPlacement(box=None)` and unwrapping to `(0,0)` makes every blocked label appear at top-left, which is worse than the current least-overlap fallback. Since rerouting is deferred, `reroute_required=True` is inert. Fix: return `LabelPlacement(box=<least-overlap position>, reroute_required=True)` when all candidates are blocked; only return `box=None` for the empty-candidates case.

**5. Task 5 orphans the gallery test import after moving the file.** `plan.md`. Task 4 adds `tests/test_compare_gallery.py` importing `compare_gallery`; Task 5 then moves the file to `tools/` without updating the test's `sys.path`. Fix: Task 5 Approach should update the gallery test's sys.path insert to `tools/`.

**6. Spec Boundaries In-scope omits `tests/test_routing_astar.py` and `tests/test_compare_gallery.py`.** `spec.md:64`. Both files are edited/created by the plan. Fix: add both.

## Nit

**7. Task 4 Touches omits `tests/test_compare_gallery.py`.** Fix: add it.
