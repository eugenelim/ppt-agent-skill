# State-machine compiler: recursive composite states

**Status:** Implementing
**Mode:** full

## Objective

Wire `compile_state_machine()` as the authoritative state diagram compiler, replacing
the flat `_parse_graph_source()` path for `stateDiagram`/`stateDiagram-v2`. Composite
states must carry recursive children so the layout pipeline renders proper hierarchical
nesting, and cross-scope transitions must originate from the composite group boundary
rather than from an internal pseudo-state.

## Boundaries

**In scope:**
- `statediagram.py` — compiler and `state_model_to_graph()`
- `_constants.py` — `_Edge` gets `src_group` (cross-scope exit metadata only; no `dst_group`)
- `_strategies.py` — `_compile_flowchart()` uses new compiler
- `_renderer.py` — initial/final state rendering (filled disc, concentric final ring)
- Tests — update broken IDs, add acceptance-criteria tests

**Out of scope:**
- `_routing.py` internals (cycle routing changes deferred — see `docs/backlog.md#state-diagram-local-cycle-routing`)
- Waypoint clipping for cross-scope exit edges: deferred — see `docs/backlog.md#state-diagram-cross-scope-clip`
- `mermaid_render/native_svg.py` SVG paint path (separate renderer)
- ELK path (state diagrams fall back to Python due to terminal circles)

## Assumptions

- Existing tests remain green after changes.
- State diagrams always fall back to the Python Sugiyama path (terminal circles force that).
- `src_group` on `_Edge` tags cross-scope exit edges for future waypoint clipping; it has no reader today (clipping is deferred). Transitions are still routed via the scoped internal final state node, which is inside the group, giving a visually reasonable result.

## Declined

- `StateGate` as explicit border node in the graph: overhead, unclear positioning.
- `_routing.py` local-cycle routing (req 9): separate concern, deferred.
- Concurrency (`--`) region support: deferred to a follow-up.
- Deep-history semantics beyond label: deferred.
- `dst_group` on `_Edge`: no consumer in this PR; omitted.

## Acceptance Criteria

- [x] `compile_state_machine()` populates `CompositeState.children` recursively for the nested fixture.
- [x] `compile_state_machine()` uses scoped pseudo-state IDs: `Processing_sm_start_` not `_g0_sm_start_`.
- [x] `state_model_to_graph()` produces a `_g_Processing` group whose `members` include `Processing_sm_start_`, `Validating`, `Executing`.
- [x] Top-level `Processing → Done` transition edge has `src_group="_g_Processing"` in its `_Edge`.
- [x] After wiring, `statediagram-nested.mmd` renders without crash.
- [x] After wiring, `statediagram-complex.mmd` renders without crash.
- [x] Group label "Processing" appears in HTML output for nested fixture.
- [ ] Edge labels `start`, `valid`, `success`, `error` all appear in nested fixture HTML. *(deferred: label placement on group-crossing edges)*
- [x] Initial state rendered as CSS filled disc (no `●` character in `node-label` spans).
- [x] Final state inner ring is a filled disc (CSS `background`) not a border ring.
- [x] All pre-existing tests still pass (updated to new scoped IDs where needed).

## Testing Strategy

- Unit tests in `tests/test_state_model.py` — compiler IR (children, transitions, scoped IDs) + cross-scope graph tests
- Integration tests in `tests/test_fix_state.py` — updated scoped ID references, AC9/AC10 rendering assertions
- Verification: `_dispatch("statediagram-nested.mmd content")` returns valid HTML with required content

## Disposition record

| Item | Resolution |
|------|-----------|
| Cross-scope exit clipping | `src_group` on `_Edge` tags the edge; waypoint clipping deferred to `docs/backlog.md#state-diagram-cross-scope-clip` |
| Entry into composite | Route `dst = {composite}_sm_start_` (internal initial state) — semantically correct |
| local_direction | Add to `CompositeState`; applied as `group.direction` in `state_model_to_graph()` |
| Cycle routing req 9 | Deferred to `docs/backlog.md#state-diagram-local-cycle-routing` |
| SVG paint path | Not touched this PR |
| `dst_group` | Dropped — no consumer |
