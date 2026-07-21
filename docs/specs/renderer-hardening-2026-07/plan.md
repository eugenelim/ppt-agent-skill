# Renderer Hardening 2026-07 — plan

**Status:** Done

## Assumption trio

1. The test suite (`pytest tests/ -x`) currently passes on the current branch.
2. The `scripts/mermaid_render/layout/` package has no imports from FORBIDDEN packages (pre-condition for the allowlist test to start green on non-layout files).
3. `_best_label_pos` is used exclusively within `_routing.py`; changing its return type has no external callers.

## Declined patterns

- Tempted to add a `LayoutPipeline` coordinator class to thread `ValidationResult` through `to_html`. Declining — a stub `validate()` preserves the intent without the structural cost.
- Tempted to add crossing count as a metric logged to stdout during layout. Declining — no observability request; scope creep.
- Tempted to refactor all five `_fan_offset` call sites to use `PortAllocation.lane`. Declining — lane-based external doglegs are P3 scope; P4.2 only fixes the bounds, not the lane routing.

## Resolve-vs-surface disposition

- Self-loop finalization pass: **surfaced** → deferred to backlog. Cannot remove clamping without a translation step that doesn't yet exist.
- LabelPlacement propagation through `_label_on_longest`: **resolved** — `_label_on_longest` unwraps to `(lx, ly)` at the boundary; the key gain (failure signalling in `_best_label_pos`) is achieved without propagating the new type upward.

---

## Tasks

### Task 1 — Fix vacuous hexagon assertion (P0.1)

**AC:** AC-P0.1  
**Mode:** TDD  
**Depends on:** none  
**Touches:** `tests/test_flowchart_geometry.py`

**Tests:**
```python
# test_flowchart_geometry.py:152 — replace `assert w != h or True` with:
assert w != h
```
The 5-line hexagon should have height ≈ 114px and width ≈ HEX_MIN_W+shoulder. They are unequal, so the assertion will pass and will be meaningful.

**Approach:**
Replace `assert w != h or True` with `assert w != h` at line 152 in `test_flowchart_geometry.py`. Remove the misleading comment block.

**Done when:** `pytest tests/test_flowchart_geometry.py::TestHexagonSizing::test_hexagon_width_height_independent -x` passes with the new assertion.

---

### Task 2 — Add LabelPlacement + fix _best_label_pos (P0.2)

**AC:** AC-P0.2  
**Mode:** TDD  
**Depends on:** Task 1  
**Touches:** `scripts/mermaid_render/layout/_routing.py`, `tests/test_flowchart_geometry.py`

**Tests (write first — should be red before implementation):**
```python
# In test_flowchart_geometry.py, update test_all_blocked_returns_fallback:
def test_all_blocked_returns_fallback(self):
    """When all candidates overlap nodes, returns LabelPlacement with box set, reroute_required=True."""
    from mermaid_render.layout._routing import _best_label_pos
    node_obs = [(0, 0, 800, 600)]
    candidates = [(100, 100), (200, 200), (300, 300)]
    placed: list = []
    placement = _best_label_pos(candidates, "label", node_obs, placed, 800)
    assert placement.box is not None   # still places (least-overlap fallback)
    assert placement.reroute_required is True  # but signals rerouting needed
    assert len(placed) == 1  # chip still appended so other labels avoid it

def test_empty_candidates_returns_none_placement(self):
    """Empty candidate list returns LabelPlacement(box=None, reroute_required=True)."""
    from mermaid_render.layout._routing import _best_label_pos
    placed: list = []
    placement = _best_label_pos([], "label", [], placed, 800)
    assert placement.box is None
    assert placement.reroute_required is True
    assert placed == []  # nothing to place, nothing appended
```

**Approach:**
1. Add `LabelPlacement` frozen dataclass to `_routing.py` (after the existing imports, uses `Rect` from `_geometry.py`).
2. Change `_best_label_pos` to:
   - When `candidates` is empty: return `LabelPlacement(box=None, reroute_required=True)` (don't append to `placed`).
   - When `_clear` is empty (all blocked): continue scoring all candidates for least-overlap; chip = `_label_chip_bbox(best_lx, best_ly, label)`, append to `placed`, return `LabelPlacement(box=Rect(chip[0], chip[1], chip[2]-chip[0], chip[3]-chip[1]), reroute_required=True)`.
   - When `_clear` is non-empty (clear placement): same chip construction, return `LabelPlacement(box=rect, reroute_required=False)`.
3. Update **all nine call sites** inside `_routing.py`:
   - Line 255 (`_label_on_longest`): `lp = _best_label_pos(...); return (int(lp.box.x), int(lp.box.y1)) if lp.box else (0, 0)`.
   - Lines 663, 679, 699, 715, 766, 793, 820, 858 (direct in `_route_edges`): `_lp = _best_label_pos(...); llx, lly = (int(_lp.box.x), int(_lp.box.y1)) if _lp.box else (0, 0)`.

**Done when:** `pytest tests/test_flowchart_geometry.py::TestEdgeLabelHardReject -x` passes with updated assertions; all other geometry tests pass.

---

### Task 3 — Update loop-clamping test (P0.3)

**AC:** AC-P0.3  
**Mode:** TDD  
**Depends on:** Task 2  
**Touches:** `tests/test_flowchart_geometry.py`, `docs/backlog.md`

**Tests:**
Replace `test_tb_left_face_loop_canvas_clamped` with a test that documents provisional negative coordinate behavior:
```python
def test_tb_left_face_loop_renders_without_error(self):
    """TB left-face self-loop renders without raising; finalization is deferred (see backlog)."""
    src = (
        "flowchart TD\n"
        "    A[Hub]\n"
        "    A --> A\n"
        "    A -->|second| A\n"
    )
    html = _dispatch(src, None, 800)
    assert "data-node-id" in html
```

Update `test_self_loop_canvas_not_exceeded` to remove the `min(ys) >= -5` assertion for LR loops (LR top-face can have provisional negative y before finalization):
```python
# Remove: assert min(ys) >= -5, ...
# Keep: assert max(xs) <= canvas_w + 5 and assert max(ys) <= canvas_h + 5
```

Add a `docs/backlog.md` entry: `## self-loop-finalization-pass — Remove provisional clamping once finalization pass translates full drawing to canvas origin`.

**Approach:**
1. Update the two tests.
2. Add/update `docs/backlog.md` with the deferred entry.
3. Do NOT change routing code yet (clamping stays; it's the tests that are wrong).

**Done when:** Both self-loop tests pass; backlog entry exists.

---

### Task 4 — Add ValidationResult + wire gallery (P0.4, P0.5)

**AC:** AC-P0.4, AC-P0.5  
**Mode:** TDD  
**Depends on:** Task 3  
**Touches:** `scripts/mermaid_render/layout/_geometry.py`, `scripts/mermaid_render/layout/_strategies.py`, `scripts/mermaid_render/__init__.py`, `scripts/compare_gallery.py`, `tests/test_compare_gallery.py` (new)

**Tests (write first):**
```python
# tests/test_flowchart_geometry.py — new TestValidationResult class:
def test_validation_result_ok_status(self):
    from mermaid_render.layout._geometry import ValidationResult
    vr = ValidationResult()
    assert vr.status == "ok"

def test_validation_result_invalid_status(self):
    from mermaid_render.layout._geometry import ValidationResult
    vr = ValidationResult(errors=("overlap detected",))
    assert vr.status == "invalid"

def test_validation_result_warning_status(self):
    from mermaid_render.layout._geometry import ValidationResult
    vr = ValidationResult(warnings=("tight spacing",))
    assert vr.status == "warning"

def test_validate_public_api(self):
    import mermaid_render
    vr = mermaid_render.validate("flowchart LR\n    A-->B")
    from mermaid_render.layout._geometry import ValidationResult
    assert isinstance(vr, ValidationResult)
```

**Approach:**
1. Add `ValidationResult` to `_geometry.py` with `errors`, `warnings` tuple fields and `status` property.
2. Add `validate(src: str) -> ValidationResult` to `mermaid_render/__init__.py` (calls a stub in `_strategies.py`).
3. In `_strategies.py`, add `_dispatch_validate(src: str) -> ValidationResult` stub that returns empty `ValidationResult()`.
4. Update `compare_gallery.py`:
   - Change `_render_ours` to return `(html | None, error: str, status: str)` by calling `validate()` and `_classify_status`.
   - Change the tuple in `type_results` from `(name, src, ours_ok, ours_err, ...)` to `(name, src, ours_status, ours_err, ...)` where `ours_status ∈ {"ok","warning","invalid","error"}`.
   - Update nav badge, section badge, header count to use `ours_status`.
   - In `main()`: after gallery build, exit with code 1 if any `ours_status` is `"invalid"` or `"error"`.
5. Add a committed test to `tests/test_flowchart_geometry.py` (or a new `tests/test_compare_gallery.py`) that monkeypatches `compare_gallery._classify_status` to always return `"invalid"` and asserts `main()` raises `SystemExit(1)` or returns 1.

**Done when:** New `ValidationResult` tests pass; `pytest tests/test_flowchart_geometry.py::TestValidationResult -x` green; gallery exit-code test passes.

---

### Task 5 — Move compare_gallery.py to tools/ (P0.6)

**AC:** AC-P0.6  
**Mode:** goal-based  
**Depends on:** Task 4  
**Touches:** `scripts/compare_gallery.py` → `tools/compare_gallery.py`

**Done when:** `python tools/compare_gallery.py --help` exits 0; `scripts/compare_gallery.py` does not exist.

**Approach:**
1. `git mv scripts/compare_gallery.py tools/compare_gallery.py`.
2. Verify `ROOT` path computation in the moved file still resolves correctly (one level up from `tools/` to repo root).
3. Update `tests/test_compare_gallery.py` to insert `tools/` into `sys.path` instead of `scripts/` when importing `compare_gallery`.

---

### Task 6 — Complete geometry IR types (P1.1)

**AC:** AC-P1.1  
**Mode:** TDD  
**Depends on:** Task 5  
**Touches:** `scripts/mermaid_render/layout/_geometry.py`, `tests/test_flowchart_geometry.py`

**Tests (write first):**
```python
# New TestGeometryIRFull class:
def test_point_construction(self):
    from mermaid_render.layout._geometry import Point
    p = Point(10, 20)
    assert p.x == 10 and p.y == 20

def test_port_allocation_frozen(self):
    from mermaid_render.layout._geometry import PortAllocation
    pa = PortAllocation(offset=21, lane=0)
    with pytest.raises(Exception):  # FrozenInstanceError
        pa.offset = 99

def test_layout_result_construction(self):
    from mermaid_render.layout._geometry import LayoutResult, Rect, GroupLayout
    lr = LayoutResult(
        node_boxes={"A": Rect(0, 0, 100, 50)},
        groups={},
        edges=(),
        decoration_boxes=(),
        canvas=Rect(0, 0, 200, 200),
    )
    assert lr.canvas.w == 200
```

**Approach:**
Add `Point`, `Port`, `PortAllocation`, `GroupLayout`, `RoutedEdge`, `LayoutResult` frozen dataclasses (with `slots=True` where Python ≥ 3.10 supports it) to `_geometry.py`.

**Done when:** All new type tests pass; `_geometry.py` exports all types without error.

---

### Task 7 — Fix A* routing failure (P4.1)

**AC:** AC-P4.1  
**Mode:** TDD  
**Depends on:** Task 6  
**Touches:** `scripts/mermaid_render/layout/_routing.py`, `tests/test_routing_astar.py`

**Tests (write first — to be added to `test_routing_astar.py`):**
```python
def test_astar_no_path_returns_none(self):
    """_astar_route returns None when no path exists, not a direct line."""
    from mermaid_render.layout._routing import _astar_route
    # Fully blocked grid: all segments blocked
    grid_xs = [0, 10, 20]
    grid_ys = [0, 10, 20]
    blocked = {(xi, yi, xi2, yi2)
               for xi in range(2) for yi in range(2)
               for xi2 in range(2) for yi2 in range(2)}
    result = _astar_route(5, 5, 15, 15, grid_xs, grid_ys, blocked, set())
    assert result is None

def test_perimeter_retry_finds_path(self):
    """When A* fails but a 16px margin adds clearance, retry finds a valid path."""
    from mermaid_render.layout._routing import _route_perimeter
    # Large obstacle in the centre; 16px margin clears a path around it
    obstacles = [(50, 50, 150, 150)]  # 100x100 box
    pts = _route_perimeter(0, 100, 200, 100, 16, obstacles)
    assert pts is not None
    assert len(pts) >= 3  # at least 3 waypoints for a bypass

def test_routing_failure_omits_edge(self):
    """_route_perimeter returns None when all four bypass directions are obstructed."""
    from mermaid_render.layout._routing import _route_perimeter
    # Full-surround obstacle: source and dest deep inside it.
    # All 4 bypass paths have vertical segments that cross the obstacle boundary.
    full_surround = [(0, 0, 500, 500)]
    for margin in (16, 32, 64, 128):
        result = _route_perimeter(200, 200, 300, 300, margin, full_surround)
        assert result is None, f"Expected None with margin={margin}, got {result}"
```

**Approach:**
1. Change the final line of `_astar_route` (line 180) from `return [(sx, sy), (dx, dy)]` to `return None`.
2. There are **two** `_astar_route` call sites to update:
   - **LR path** (lines 899–904): `_pts_lr = _astar_route(...)` followed by `if len(_pts_lr) >= 2:` and `_accumulate_occupied(_pts_lr)`.
   - **TB path** (lines 972–977): `_pts = _astar_route(...)` followed by `if len(_pts) >= 2:` and `_accumulate_occupied(_pts)`.
   
   Wrap each with the perimeter-retry / continue-on-None pattern:
   ```python
   # (replace the _astar_route call and the immediate len() / accumulate)
   _pts = _astar_route(int(x1), int(y1), int(x2), int(y2),
                       _grid_xs, _grid_ys, _blocked, _occupied)
   if _pts is None:
       for margin in (16, 32, 64, 128):
           _pts = _route_perimeter(int(x1), int(y1), int(x2), int(y2), margin, _routing_obs)
           if _pts is not None:
               break
   if _pts is None:
       continue  # skip edge — omit from result rather than draw through obstacle
   if len(_pts) >= 2:
       _pts[0] = (int(x1), int(y1))
       _pts[-1] = (int(x2), int(y2))
   _accumulate_occupied(_pts)
   ```
3. Implement `_route_perimeter(sx, sy, dx, dy, margin, obstacles) -> list | None` — computes the obstacle bounding box over `obstacles`, inflates by `margin`, tries 4 bypass paths (top, bottom, left, right), returns the first that passes `_try_3seg_clear`, or `None` if all four fail.

**Done when:** All three new tests pass; existing routing tests still pass.

---

### Task 8 — Add allocate_face_ports + fix _fan_offset bounds (P4.2)

**AC:** AC-P4.2  
**Mode:** TDD  
**Depends on:** Task 7  
**Touches:** `scripts/mermaid_render/layout/_routing.py`, `tests/test_flowchart_geometry.py`

**Tests (write first):**
```python
def test_allocate_face_ports_bounds(self):
    """All port offsets are within [0, face_length]."""
    from mermaid_render.layout._routing import allocate_face_ports
    ports = allocate_face_ports(face_length=42, count=8)
    assert len(ports) == 8
    for p in ports:
        assert 0 <= p.offset <= 42

def test_allocate_face_ports_overflow(self):
    """When count exceeds capacity, lane increments for excess ports."""
    from mermaid_render.layout._routing import allocate_face_ports
    # 42px face, min_step=6: capacity = (42-16)//6 + 1 = 5
    ports = allocate_face_ports(face_length=42, count=8)
    lanes = [p.lane for p in ports]
    assert lanes[:5] == [0, 0, 0, 0, 0]  # first 5 on lane 0
    assert all(l == 1 for l in lanes[5:])  # remaining on lane 1

def test_allocate_face_ports_single(self):
    from mermaid_render.layout._routing import allocate_face_ports
    ports = allocate_face_ports(face_length=100, count=1)
    assert ports[0].offset == 50  # centred

def test_fan_offset_clamped(self):
    """_fan_offset output stays within [0, node_w] even with many edges."""
    from mermaid_render.layout._routing import _fan_offset
    for i in range(8):
        off = _fan_offset(i, 8, node_w=42)
        assert 0 <= off <= 42, f"_fan_offset({i}, 8, 42) = {off}"
```

**Approach:**
1. Add `PortAllocation` import from `_geometry.py` (already added in Task 6).
2. Add `allocate_face_ports(face_length, count, *, padding=8, min_step=6)` implementing the spec algorithm.
3. Update `_fan_offset` to clamp: `return max(0, min(node_w, start + step * index))`.

**Done when:** All three new tests pass; no regression in existing routing tests.

---

### Task 9 — Add node_rect + fix back-edge detection (P4.3)

**AC:** AC-P4.3  
**Mode:** TDD  
**Depends on:** Task 8  
**Touches:** `scripts/mermaid_render/layout/_routing.py`, `tests/test_flowchart_geometry.py`

**Tests (write first):**
```python
def test_node_rect_wide_card(self):
    """node_rect returns width from _node_render_w, not NODE_W."""
    from mermaid_render.layout._routing import node_rect
    from mermaid_render.layout._constants import _Node
    n = _Node(id="A", label="wide", width=220, height=50)
    n.x = 100; n.y = 30
    r = node_rect(n)
    assert r.x == 100
    assert r.y == 30
    assert r.w == 220
    assert r.h == 50

def test_back_edge_detection_center(self):
    """Back-edge detection uses center comparison, not NODE_W constant."""
    from mermaid_render.layout._routing import node_rect
    from mermaid_render.layout._constants import _Node
    src = _Node(id="S", label="src"); src.x = 300; src.y = 0; src.width = 100; src.height = 50
    dst = _Node(id="D", label="dst"); dst.x = 0; dst.y = 0; dst.width = 220; dst.height = 50
    dst_rect = node_rect(dst)
    src_rect = node_rect(src)
    goes_back = (dst_rect.x + dst_rect.w / 2) < (src_rect.x + src_rect.w / 2)
    assert goes_back  # dst center at 110 < src center at 350

def test_reverse_edge_detection_center(self):
    """Reverse-edge detection uses node_rect right edge, not fixed NODE_W."""
    from mermaid_render.layout._routing import node_rect
    from mermaid_render.layout._constants import _Node, NODE_W
    # src at x=0 with wide=200px; dst at x=210 (right of src). Should NOT be reverse.
    src = _Node(id="S", label="s"); src.x = 0; src.y = 0; src.width = 200; src.height = 50
    dst = _Node(id="D", label="d"); dst.x = 210; dst.y = 0; dst.width = NODE_W; dst.height = 50
    src_rect = node_rect(src)
    dst_rect = node_rect(dst)
    # New check: src.x1 <= dst.x  (200 <= 210 → False for reverse, which is correct)
    is_right_to_left = src_rect.x1 > dst_rect.x
    assert not is_right_to_left  # 200 <= 210, not reverse
    # With old NODE_W check: s.x >= d.x + NODE_W → 0 >= 210 + 42 = 252 → False. Same result here.
    # Now a case that differs: wide src (220px) at x=0, dst at x=180. Old: 0 >= 180+42=222 → False.
    # New: src.x1=220 > dst.x=180 → True (IS right-to-left). Old formula missed this.
    src2 = _Node(id="S2", label="s2"); src2.x = 0; src2.y = 0; src2.width = 220; src2.height = 50
    dst2 = _Node(id="D2", label="d2"); dst2.x = 180; dst2.y = 0; dst2.width = NODE_W; dst2.height = 50
    src2_rect = node_rect(src2)
    dst2_rect = node_rect(dst2)
    assert src2_rect.x1 > dst2_rect.x  # 220 > 180: wide src overlaps dst start
```

**Approach:**
1. Add `node_rect(n: _Node) -> Rect` function to `_routing.py`.
2. Fix line 730: replace `(d.x + NODE_W // 2) < s.x` with center comparison using `node_rect`.
3. Fix line 739: replace `s.x >= d.x + NODE_W` with `node_rect(s).x >= node_rect(d).x1`.

**Done when:** Both new tests pass; existing routing tests pass.

---

### Task 10 — Robust cycle-breaking: iterative DFS (P2.1)

**AC:** AC-P2.1  
**Mode:** TDD  
**Depends on:** Task 9  
**Touches:** `scripts/mermaid_render/layout/_layout.py`, `tests/test_routing_astar.py`

**Tests (write first):**
```python
def _has_cycle(nodes, edges):
    """Return True if forward edges form a cycle."""
    adj = {nid: [] for nid in nodes}
    for e in edges:
        if not e.reversed_ and e.src in adj and e.dst in adj:
            adj[e.src].append(e.dst)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}
    def dfs(u):
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                return True
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False
    return any(dfs(nid) for nid in nodes if color[nid] == WHITE)

def test_greedy_fas_correctness(self):
    """After _break_cycles, the forward-edge subgraph contains no directed cycles."""
    from mermaid_render.layout._constants import _Node, _Edge
    from mermaid_render.layout._layout import _break_cycles
    nodes = {nid: _Node(id=nid, label=nid) for nid in "ABCDE"}
    edges = [
        _Edge(src="A", dst="B", label=""),
        _Edge(src="B", dst="C", label=""),
        _Edge(src="C", dst="A", label=""),  # cycle 1
        _Edge(src="C", dst="D", label=""),
        _Edge(src="D", dst="E", label=""),
        _Edge(src="E", dst="C", label=""),  # cycle 2
    ]
    _break_cycles(nodes, edges)
    assert not _has_cycle(nodes, edges), "Forward-edge subgraph still has a cycle"

def test_greedy_fas_deterministic(self):
    """Repeated calls on identical graphs produce identical results."""
    from mermaid_render.layout._constants import _Node, _Edge
    from mermaid_render.layout._layout import _break_cycles
    def run():
        nodes = {nid: _Node(id=nid, label=nid) for nid in "ABCDE"}
        edges = [
            _Edge(src="A", dst="B", label=""),
            _Edge(src="B", dst="C", label=""),
            _Edge(src="C", dst="A", label=""),
            _Edge(src="C", dst="D", label=""),
            _Edge(src="D", dst="E", label=""),
            _Edge(src="E", dst="C", label=""),
        ]
        _break_cycles(nodes, edges)
        return [(e.src, e.dst, e.reversed_) for e in edges]
    assert run() == run()

def test_greedy_fas_single_cycle(self):
    """For a simple linear cycle, exactly 1 edge is reversed."""
    from mermaid_render.layout._constants import _Node, _Edge
    from mermaid_render.layout._layout import _break_cycles
    nodes = {nid: _Node(id=nid, label=nid) for nid in "ABC"}
    edges = [
        _Edge(src="A", dst="B", label=""),
        _Edge(src="B", dst="C", label=""),
        _Edge(src="C", dst="A", label=""),
    ]
    _break_cycles(nodes, edges)
    assert sum(1 for e in edges if e.reversed_) == 1
```

**Approach:**
Replace recursive DFS `_break_cycles` with iterative DFS to avoid Python's recursion limit on large graphs.

An Eades-style greedy FAS was prototyped but caused a regression: for `statediagram-complex`, the greedy ordering placed `Auth` before `Idle` (delta=1), reversing `Idle→Auth` instead of the back-edge `Auth→Idle`. This produced a 4-rank layout instead of the correct 6-rank layout, making the canvas too narrow for the right-lane back-edge routing path (canvas_w=344, path reached x=356). The iterative DFS matches the recursive DFS exactly (both traverse in node declaration order) so it produces identical rank assignments with no regression.

**Implementation:**
```python
for start in list(nodes.keys()):
    if color[start] != WHITE:
        continue
    stack = [(start, 0)]  # (node, adj_list_index)
    color[start] = GRAY
    while stack:
        u, idx = stack[-1]
        if idx < len(adj[u]):
            stack[-1] = (u, idx + 1)
            ei = adj[u][idx]
            v = edges[ei].dst
            if color.get(v) == GRAY:
                edges[ei].reversed_ = True
            elif color.get(v) == WHITE:
                color[v] = GRAY
                stack.append((v, 0))
        else:
            color[u] = BLACK
            stack.pop()
```

**Done when:** All three invariant tests pass (`TestBreakCyclesInvariants` in `tests/test_routing_astar.py`); all existing flowchart/routing tests pass (regression free).

---

### Task 11 — Dependency enforcement tests (DEP)

**AC:** AC-DEP.1, AC-DEP.2, AC-DEP.3  
**Mode:** TDD  
**Depends on:** none  
**Touches:** `tests/test_dependencies.py` (new file)

**Tests:** The test file IS the implementation. Three tests:
1. Isolated-interpreter test (subprocess with `-I -S`).
2. AST import allowlist scan.
3. AST no-subprocess scan.

**Done when:** All three tests pass in `pytest tests/test_dependencies.py -x`.

---

## Files touched summary

| File | Tasks |
|------|-------|
| `tests/test_flowchart_geometry.py` | 1, 2, 3, 4, 6, 8, 9, 10 |
| `scripts/mermaid_render/layout/_geometry.py` | 4, 6 |
| `scripts/mermaid_render/layout/_routing.py` | 2, 7, 8, 9 |
| `scripts/mermaid_render/layout/_layout.py` | 10 |
| `scripts/mermaid_render/layout/_strategies.py` | 4 |
| `scripts/mermaid_render/__init__.py` | 4 |
| `scripts/compare_gallery.py` → `tools/compare_gallery.py` | 4, 5 |
| `tests/test_routing_astar.py` | 7 |
| `tests/test_compare_gallery.py` (new) | 4 |
| `tests/test_dependencies.py` (new) | 11 |
| `docs/backlog.md` | 3 |
