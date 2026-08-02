# Plan: Routing Port-Planner Foundation

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing

## Approach

Create `scripts/mermaid_render/layout/port_planner.py` as a pure-function module
with four NamedTuple data structures and four planning functions. No existing file
is modified; existing tests provide the regression baseline. Write `tests/test_port_planner.py`
in TDD order (red stub → green → refactor) before implementing each function.

Riskiest part: `generate_port_candidates` with `shape_geometry` — must correctly
convert node-local `boundary_anchor` output to canvas coordinates.

## Constraints

- CONVENTIONS.md: module under ~500 lines; `_` prefix for private helpers;
  no new pip dependencies without RFC.
- ini-004 spec: do NOT modify `_routing.py`, `_pipeline.py`, or any existing
  layout file.
- `boundary_anchor(side, offset, w, h)` returns node-local coords (confirmed
  from shape_geometry.py:97–109); caller adds `(node_x, node_y)` offset.

## Construction tests

**Integration tests:** none beyond per-task tests (module is self-contained).
**Manual verification:** `python -c "from scripts.mermaid_render.layout.port_planner import PortCandidate, PortReservation, RouteCandidate, RoutingObstacle, build_edge_lists, generate_port_candidates, plan_straight_corridor, fan_slots; print('OK')"` exits 0.

## Design (LLD)

### Data & schema

```
PortCandidate(NamedTuple):
    edge_id, node_id, side, normalized_offset, point, outward_normal, fixed_side, preference_penalty

PortReservation(NamedTuple):
    edge_id, node_id, port_candidate, terminal_clearance, escape_point

RouteCandidate(NamedTuple):
    edge_id, source_port, target_port, points, bend_count, length,
    crossing_count, shared_segment_length, cost,
    escape_indices(frozenset, default=frozenset())

RoutingObstacle(NamedTuple):
    obstacle_id, kind, bounds, scope_id, title_bounds, permitted_gate_ids(frozenset)
```

Private helper `_aabb_anchor_point(side, offset, node_x, node_y, w, h)` computes
canvas-coord anchor via AABB interpolation for the fallback path.

### Interfaces & contracts

```python
build_edge_lists(edges: list[dict]) -> dict[str, list[str]]
generate_port_candidates(
    node_id: str,
    node_bounds: tuple[float, float, float, float],  # (x, y, w, h)
    edges: list[dict],  # each has edge_id, source_id, target_id
    edge_id: str,
    fixed_side: str | None = None,
    shape_geometry: ShapeGeometry | None = None,
) -> list[PortCandidate]
plan_straight_corridor(
    src_bounds: tuple[float, float, float, float],
    dst_bounds: tuple[float, float, float, float],
) -> tuple[str, float] | None
fan_slots(
    edge_ids: list[str],
    side: str,
) -> list[tuple[str, float]]
```

## Tasks

### Task 1: Data structures

Verification mode: TDD
stub: true

**Tests:**
```python
# test_port_planner.py — Task 1 stubs (AC2, AC3)

# AC2: PortCandidate immutable
def test_port_candidate_is_immutable():  # STUB: AC2
    pc = PortCandidate(edge_id="e1", node_id="A", side="top",
                       normalized_offset=0.5, point=(10.0, 20.0),
                       outward_normal=(0.0, -1.0), fixed_side=False,
                       preference_penalty=0.0)
    with pytest.raises(AttributeError):
        pc.side = "bottom"

# AC3: edge_id field present on PortCandidate
def test_port_candidate_edge_id_field():  # STUB: AC3
    pc = PortCandidate(edge_id="e1", node_id="A", side="top",
                       normalized_offset=0.5, point=(10.0, 20.0),
                       outward_normal=(0.0, -1.0), fixed_side=False,
                       preference_penalty=0.0)
    assert pc.edge_id == "e1"

# AC2: PortReservation immutable
def test_port_reservation_is_immutable():  # STUB: AC2
    pc = PortCandidate(edge_id="e1", node_id="A", side="top",
                       normalized_offset=0.5, point=(10.0, 20.0),
                       outward_normal=(0.0, -1.0), fixed_side=False,
                       preference_penalty=0.0)
    pr = PortReservation(edge_id="e1", node_id="A", port_candidate=pc,
                         terminal_clearance=10.0, escape_point=(10.0, 15.0))
    with pytest.raises(AttributeError):
        pr.terminal_clearance = 999.0

# AC3: edge_id field present on PortReservation
def test_port_reservation_edge_id_field():  # STUB: AC3
    pc = PortCandidate(edge_id="e1", node_id="A", side="top",
                       normalized_offset=0.5, point=(10.0, 20.0),
                       outward_normal=(0.0, -1.0), fixed_side=False,
                       preference_penalty=0.0)
    pr = PortReservation(edge_id="e1", node_id="A", port_candidate=pc,
                         terminal_clearance=10.0, escape_point=(10.0, 15.0))
    assert pr.edge_id == "e1"

# AC2: RouteCandidate immutable
def test_route_candidate_is_immutable():  # STUB: AC2
    pc = PortCandidate(edge_id="e1", node_id="A", side="top",
                       normalized_offset=0.5, point=(10.0, 20.0),
                       outward_normal=(0.0, -1.0), fixed_side=False,
                       preference_penalty=0.0)
    rc = RouteCandidate(edge_id="e1", source_port=pc, target_port=pc,
                        points=((10.0, 20.0),), bend_count=0, length=0.0,
                        crossing_count=0, shared_segment_length=0.0, cost=0.0)
    with pytest.raises(AttributeError):
        rc.cost = 999.0

# AC3: edge_id field present on RouteCandidate
def test_route_candidate_edge_id_field():  # STUB: AC3
    pc = PortCandidate(edge_id="e1", node_id="A", side="top",
                       normalized_offset=0.5, point=(10.0, 20.0),
                       outward_normal=(0.0, -1.0), fixed_side=False,
                       preference_penalty=0.0)
    rc = RouteCandidate(edge_id="e1", source_port=pc, target_port=pc,
                        points=((10.0, 20.0),), bend_count=0, length=0.0,
                        crossing_count=0, shared_segment_length=0.0, cost=0.0)
    assert rc.edge_id == "e1"

# AC2: RoutingObstacle immutable; AC3: keyed by obstacle_id not edge_id
def test_routing_obstacle_immutable_and_keyed_by_obstacle_id():  # STUB: AC2, AC3
    ob = RoutingObstacle(obstacle_id="n1", kind="node",
                         bounds=(0.0, 0.0, 100.0, 60.0),
                         scope_id=None, title_bounds=None,
                         permitted_gate_ids=frozenset(["g1"]))
    assert isinstance(ob.permitted_gate_ids, frozenset)
    assert ob.obstacle_id == "n1"
    assert not hasattr(ob, "edge_id")  # not an edge-derived structure
    with pytest.raises(AttributeError):
        ob.kind = "group"
```

**Approach:** Define `PortCandidate`, `PortReservation`, `RouteCandidate`,
`RoutingObstacle` as `NamedTuple` subclasses. `RoutingObstacle.permitted_gate_ids`
uses `frozenset` (set membership, hashable, unordered). `RoutingObstacle` has
no `edge_id` field — it is keyed by `obstacle_id`.

Done when: all seven stubs pass.
Depends on: none.

---

### Task 2: `build_edge_lists`

Verification mode: TDD
stub: true

**Tests:**
```python
def test_build_edge_lists_single_edge():  # STUB: AC12
    edges = [{"edge_id": "e1", "source_id": "A", "target_id": "B"}]
    el = build_edge_lists(edges)
    assert "e1" in el["A"]
    assert "e1" in el["B"]

def test_build_edge_lists_multi_edge_same_node():  # STUB: AC12
    edges = [
        {"edge_id": "e1", "source_id": "A", "target_id": "B"},
        {"edge_id": "e2", "source_id": "A", "target_id": "C"},
    ]
    el = build_edge_lists(edges)
    assert sorted(el["A"]) == ["e1", "e2"]

def test_build_edge_lists_no_duplicate_ids():  # STUB: AC12
    edges = [{"edge_id": "e1", "source_id": "A", "target_id": "A"}]
    el = build_edge_lists(edges)
    # A self-loop: A appears once, e1 appears once
    assert el["A"].count("e1") == 1
```

**Approach:** Iterate edges; for each, add `edge_id` to both `source_id` and
`target_id` lists (skipping None/missing keys); deduplicate per-node.

Done when: all three tests pass.
Depends on: Task 1.

---

### Task 3: `generate_port_candidates`

Verification mode: TDD
stub: true

**Tests:**
```python
def test_generate_fixed_side_returns_only_that_side():  # STUB: AC4
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(0.0, 0.0, 120.0, 60.0),
        edges=[], edge_id="e1", fixed_side="top"
    )
    assert all(c.side == "top" for c in candidates)
    assert all(c.fixed_side is True for c in candidates)
    assert all(c.preference_penalty == 0.0 for c in candidates)
    assert len(candidates) >= 1

def test_generate_all_sides_when_no_fixed():  # STUB: AC5
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(0.0, 0.0, 120.0, 60.0),
        edges=[], edge_id="e1"
    )
    sides_present = {c.side for c in candidates}
    assert {"top", "right", "bottom", "left", "center"}.issubset(sides_present)

def test_generate_center_has_highest_penalty():  # STUB: AC5
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(0.0, 0.0, 120.0, 60.0),
        edges=[], edge_id="e1"
    )
    center_candidates = [c for c in candidates if c.side == "center"]
    non_center = [c for c in candidates if c.side != "center"]
    assert center_candidates, "center candidate must be present"
    assert all(c.preference_penalty > nc.preference_penalty
               for c in center_candidates for nc in non_center
               if nc.preference_penalty == 0.0)

def test_generate_with_shape_geometry_rect_point_on_boundary():  # STUB: AC6
    from scripts.mermaid_render.layout.shape_geometry import RectGeometry
    geom = RectGeometry()
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(10.0, 20.0, 120.0, 60.0),
        edges=[], edge_id="e1", fixed_side="top",
        shape_geometry=geom
    )
    assert len(candidates) == 1
    px, py = candidates[0].point
    # Top side: y should equal node_y (=20.0) ± 0.5
    assert abs(py - 20.0) < 0.5
    # x should be within [10, 130]
    assert 10.0 - 0.5 <= px <= 130.0 + 0.5

def test_generate_center_candidate_point_is_node_center():  # STUB: AC6
    candidates = generate_port_candidates(
        node_id="A", node_bounds=(10.0, 20.0, 120.0, 60.0),
        edges=[], edge_id="e1"
    )
    center = [c for c in candidates if c.side == "center"]
    assert len(center) == 1
    assert center[0].point == (10.0 + 120.0 / 2, 20.0 + 60.0 / 2)
```

**Approach:** When `fixed_side` is set, generate one candidate via
`_make_candidate(fixed_side, 0.5, 0.0, True)`. When not set, generate
preferred sides (bottom, right) with penalty=0.0; other sides (top, left)
with penalty=25.0; center with penalty=50.0. `_make_candidate` calls
`shape_geometry.boundary_anchor(side, offset, w, h)` → adds `(node_x, node_y)`
for canvas coords. Center candidate always uses `(node_x + w/2, node_y + h/2)`
regardless of shape_geometry.

Done when: all five tests pass (four side-selection + one center-point).
Depends on: Task 1.

---

### Task 4: `plan_straight_corridor`

Verification mode: TDD
stub: true

**Tests:**
```python
def test_plan_straight_corridor_vertical():  # STUB: AC7
    src = (40.0, 0.0, 80.0, 60.0)   # x=40, y=0, w=80, h=60 → bottom at y=60
    dst = (50.0, 100.0, 80.0, 60.0) # x=50, y=100 → top at y=100
    result = plan_straight_corridor(src, dst)
    assert result is not None
    kind, val = result
    assert kind == "vertical"
    # X overlap: [40,120] ∩ [50,130] = [50,120]; center = 85
    assert abs(val - 85.0) < 1.0

def test_plan_straight_corridor_horizontal():  # STUB: AC8
    src = (0.0, 30.0, 80.0, 60.0)   # right at x=80
    dst = (120.0, 40.0, 80.0, 60.0) # left at x=120
    result = plan_straight_corridor(src, dst)
    assert result is not None
    kind, val = result
    assert kind == "horizontal"
    # Y overlap: [30,90] ∩ [40,100] = [40,90]; center = 65
    assert abs(val - 65.0) < 1.0

def test_plan_straight_corridor_no_overlap():  # STUB: AC9
    src = (0.0, 0.0, 60.0, 40.0)
    dst = (200.0, 200.0, 60.0, 40.0)
    assert plan_straight_corridor(src, dst) is None

def test_plan_straight_corridor_touching_nodes_not_strict():  # STUB: AC7
    # src bottom == dst top (touching, not strictly above → sy+sh == dy)
    src = (0.0, 0.0, 60.0, 40.0)
    dst = (0.0, 40.0, 60.0, 40.0)
    # Strictly-above requires sy+sh < dy; touching fails the strict check
    result = plan_straight_corridor(src, dst)
    assert result is None

def test_plan_straight_corridor_vertical_takes_priority():  # STUB: AC13
    # Construct a case where both vertical and horizontal conditions could fire
    # (overlapping in both x and y axes, with src above and to the left of dst)
    src = (0.0, 0.0, 200.0, 60.0)   # wide node
    dst = (0.0, 100.0, 200.0, 60.0)  # directly below, same width → vertical fires first
    result = plan_straight_corridor(src, dst)
    assert result is not None
    kind, _ = result
    assert kind == "vertical"  # vertical check runs first
```

**Approach:** Check vertical corridor (src strictly above dst, x-overlap
nonempty) → return `("vertical", midpoint_x)`. Check horizontal (src strictly
left of dst, y-overlap nonempty) → return `("horizontal", midpoint_y)`. Return
None otherwise. Vertical is always checked first (AC13).

Done when: all five tests pass (vertical, horizontal, no-overlap, touching, priority).
Depends on: Task 1.

---

### Task 5: `fan_slots`

Verification mode: TDD
stub: true

Signature: `fan_slots(edge_ids: list[str], side: str) -> list[tuple[str, float]]`

Note: `node_id` and `node_bounds` are dropped — the `(i+1)/(n+1)` formula
does not read them. `side` is retained because per-side distribution is
expected to diverge in follow-on specs.

**Tests:**
```python
def test_fan_slots_even_distribution():  # STUB: AC10
    slots = fan_slots(["e1", "e2", "e3"], "bottom")
    assert len(slots) == 3
    offsets = [o for _, o in slots]
    assert sorted(offsets) == offsets  # monotonically increasing
    # For 3 edges: 1/4, 2/4, 3/4
    assert abs(offsets[0] - 0.25) < 1e-9
    assert abs(offsets[1] - 0.50) < 1e-9
    assert abs(offsets[2] - 0.75) < 1e-9

def test_fan_slots_no_duplicate_offsets():  # STUB: AC10
    slots = fan_slots(["e1", "e2", "e3", "e4"], "top")
    offsets = [o for _, o in slots]
    assert len(set(offsets)) == len(offsets)

def test_fan_slots_all_in_open_unit_interval():  # STUB: AC10
    slots = fan_slots(["e1", "e2"], "right")
    offsets = [o for _, o in slots]
    assert all(0.0 < o < 1.0 for o in offsets)

def test_fan_slots_empty():  # STUB: AC10
    slots = fan_slots([], "left")
    assert slots == []

def test_fan_slots_preserves_edge_id_order():  # STUB: AC10
    eids = ["e3", "e1", "e2"]
    slots = fan_slots(eids, "bottom")
    returned_eids = [eid for eid, _ in slots]
    assert returned_eids == eids
```

**Approach:** For `n` edges, slot `i` (0-indexed) gets offset `(i+1)/(n+1)`.
This guarantees all offsets in `(0.0, 1.0)` exclusive and no duplicates.
Return `[(edge_id, offset), ...]` preserving input order.

Done when: all five tests pass.
Depends on: Task 1.

---

### Task 6: Regression pass

Verification mode: Goal-based check

Done when: `pytest tests/ -x -q` exits 0 (no regressions from new module).
Depends on: Tasks 1–5.

## Changelog

- 2026-07-24: Initial draft.
