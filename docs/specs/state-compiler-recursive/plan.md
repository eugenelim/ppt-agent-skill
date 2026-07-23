# Plan: state-compiler-recursive

## Task 1 — Fix `compile_state_machine()` recursive children
**Mode:** TDD  
**Depends on:** none  
**Files:** `statediagram.py`

**Tests:**
```python
def test_composite_children_populated():
    lines = ["state Processing {", "[*] --> Validating", "Validating --> Executing", "}"]
    m = compile_state_machine(lines)
    cs = next(s for s in m.states if isinstance(s, CompositeState) and s.id == "Processing")
    assert len(cs.children) > 0

def test_inner_start_in_children():
    lines = ["state Processing {", "[*] --> Validating", "}"]
    m = compile_state_machine(lines)
    cs = next(s for s in m.states if isinstance(s, CompositeState))
    ids = {s.id for s in cs.children if hasattr(s, 'id')}
    assert "Processing_sm_start_" in ids

def test_inner_transitions_in_composite():
    lines = ["state Processing {", "[*] --> Validating", "Validating --> Executing", "}"]
    m = compile_state_machine(lines)
    cs = next(s for s in m.states if isinstance(s, CompositeState))
    assert any(t.src_id == "Validating" for t in cs.transitions)

def test_cross_scope_transition_in_top_level():
    lines = ["state Processing {", "[*] --> X", "}", "Processing --> Done"]
    m = compile_state_machine(lines)
    assert any(t.src_id == "Processing" and t.dst_id == "Done" for t in m.transitions)
```

**Approach:**
- Two-pass: pass 1 identifies composite IDs via `_COMPOSITE_RE`
- Pass 2: per-scope stack `(scope_id, local_states, local_transitions)`, direction tracking
- On `state X {`: push scope frame; if X in _known from transition ref, we don't add placeholder
- On `}`: pop frame, assemble `CompositeState(children=tuple(states), transitions=tuple(transitions)...)`, append to parent frame
- `_ensure(sid)`: if sid in composite_ids and not yet in _known, skip (will be added on `}`)
- Add `local_direction: str = ""` field to `CompositeState` frozen dataclass

**Done when:** 4 new tests pass.

---

## Task 2 — Fix `state_model_to_graph()` cross-scope handling
**Mode:** TDD  
**Depends on:** Task 1  
**Files:** `statediagram.py`, `_constants.py`

**Tests:**
```python
def test_composite_group_has_children_as_members():
    m = compile_state_machine([
        "state Processing {", "[*] --> Validating", "Validating --> Executing", "Executing --> [*]", "}",
    ])
    nodes, edges, groups = state_model_to_graph(m)
    g = next(g for g in groups.values() if g.label == "Processing")
    assert "Processing_sm_start_" in g.members
    assert "Validating" in g.members

def test_cross_scope_exit_edge_has_src_group():
    m = compile_state_machine([
        "state Processing {", "[*] --> X", "X --> [*]", "}",
        "Processing --> Done",
    ])
    nodes, edges, groups = state_model_to_graph(m)
    exit_edge = next(e for e in edges if e.dst == "Done")
    assert exit_edge.src_group is not None

def test_cross_scope_entry_targets_inner_start():
    m = compile_state_machine([
        "Idle --> Processing",
        "state Processing {", "[*] --> X", "}",
    ])
    nodes, edges, groups = state_model_to_graph(m)
    entry_edge = next(e for e in edges if e.src == "Idle")
    assert entry_edge.dst == "Processing_sm_start_"
```

**Approach:**
- In `state_model_to_graph()`: build `_composite_ids = {s.id for s in all_composite_states}`
- Recursively emit children into group (already done in `_emit`)
- For top-level transitions:
  - If `src_id in _composite_ids`: set `edge.src = {cs_id}_sm_end_` (or first available member), `edge.src_group = _g_{cs_id}`
  - If `dst_id in _composite_ids`: set `edge.dst = {cs_id}_sm_start_` (or last available member)
- Add `src_group: Optional[str] = None` to `_Edge` in `_constants.py` (no `dst_group` — no consumer)

**Done when:** 3 new tests pass.

---

## Task 3 — Wire `compile_state_machine()` into `_compile_flowchart()`
**Mode:** goal-based  
**Depends on:** Task 2  
**Files:** `_strategies.py`

**Approach:**
- At top of `_compile_flowchart()`, after extracting `content_lines`:
  ```python
  _state_directives = frozenset({"statediagram-v2", "statediagram"})
  directive, _ = _detect_directive(clean)
  if directive.lower() in _state_directives:
      from .statediagram import compile_state_machine, state_model_to_graph
      nodes, edges, groups = state_model_to_graph(compile_state_machine(content_lines))
      # Assign stable edge IDs
      _id_counts = {}
      for _e in edges:
          _base = f"{_e.src}->{_e.dst}"
          _n = _id_counts.get(_base, 0)
          _id_counts[_base] = _n + 1
          _e.edge_id = _base if _n == 0 else f"{_base}#{_n}"
  else:
      nodes, edges, groups = _parse_graph_source(content_lines)
  ```
- After routing (line ~5382), add waypoint clipping for `src_group` edges:
  ```python
  if _grp_bboxes:
      _src_group_map = {e.edge_id: e.src_group for e in edges if getattr(e, 'src_group', None)}
      if _src_group_map:
          _clip_cross_scope_exit_waypoints(route_batch.routed, _src_group_map, _grp_bboxes)
  ```
- Add helper `_clip_cross_scope_exit_waypoints()` that clips each matching edge's waypoints to the group bbox boundary

**Done when:** `_dispatch(nested_fixture_src, None, 800)` returns valid HTML containing "Processing".

---

## Task 4 — Improve initial/final state rendering in `render_finalized()`
**Mode:** goal-based  
**Depends on:** none (independent of Tasks 1-3)  
**Files:** `_renderer.py`

**Approach:**
- Add special-case for `circle` + `_is_terminal_circle(nl)` in `render_finalized()` node loop:
  - Render as `<div class="node node-circle state-initial"` with CSS `background:{accent}; border-radius:50%;` and NO text label
  - Check terminal circle by: `nl.semantic_shape == "circle"` and label `≤ 2 chars`
- Change `doublecircle` inner div from `border:2px solid {accent}` to `background:{accent}` (filled disc)
- The check: `shape == "doublecircle"` and `nid.endswith("_sm_end_")` → use filled disc

**Done when:** Initial state renders without `●` character; final state has `background` in inner div.

---

## Task 5 — Update tests
**Mode:** goal-based  
**Depends on:** Tasks 1-4  
**Files:** `test_fix_state.py`, `test_state_model.py`, new `test_state_compiler_integration.py`

**Changes:**
- `test_fix_state.py` line 145: `"_g0_sm_start_"` → `"Processing_sm_start_"`
- Add new tests for cross-scope edge `src_group`
- Add new `test_state_compiler_integration.py` with nested fixture acceptance tests
- Verify `test_start_symbol_in_html`: initial state should NOT contain `●` in `node-label` (now CSS disc)
- Update `test_start_node_bullet_label`: still passes (the `_Node.label == "●"` test is in _parser.py path)

**Done when:** All tests pass.
