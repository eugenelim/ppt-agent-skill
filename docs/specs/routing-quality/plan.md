# Plan: routing-quality

## Tasks

### T1: Raise A* CROSS penalty
**File:** `scripts/mermaid_render/layout/_routing.py` line 276
**Approach:** `CROSS = 60` → `CROSS = 300`; also `BEND = 100` → `BEND = 30`
and `SEG_COST = 25` → `SEG_COST = 10` so distance is cheap and occupied
channels are strongly discouraging.
**Verification:** goal-based — `grep "CROSS = 300" _routing.py`
**Depends on:** none

### T2: Raise Z-route shared-segment cost
**File:** `scripts/mermaid_render/layout/route_search.py` line 45
**Approach:** `+ 12.0 * rc.shared_segment_length` → `+ 80.0 * rc.shared_segment_length`
**Verification:** goal-based — `grep "80.0 \* rc.shared_segment_length" route_search.py`
**Depends on:** none

### T3: Add `_assign_lanes` to `_pipeline.py`
**File:** `scripts/mermaid_render/layout/_pipeline.py`
**Approach:**
  - Add module-level `_assign_lanes(assignments, obstacles, lane_gap=12.0)` function
    before `_flowchart_route_new_path`. It iterates all (i, j) route pairs, finds
    shared segments > 8 px using inline `_axis_overlap` logic, and shifts the
    later route's overlapping waypoints by ±lane_gap, skipping if the shifted
    vertical/horizontal segment enters any `NODE_INTERIOR` or `node` obstacle.
  - At line 2044 (after main routing loop, before conversion loop): add call
    `assignments = _assign_lanes(assignments, obs_tuple)`
**Verification:** goal-based — grep for `_assign_lanes` at call site
**Depends on:** T1, T2 (logically, but can be implemented in parallel)

### T4: Visual QA
**Approach:** Render both fixtures via `mermaid_render render` + `html2png.py`,
capture screenshots, verify no tramlines.
**Verification:** visual / manual QA
**Depends on:** T1, T2, T3
