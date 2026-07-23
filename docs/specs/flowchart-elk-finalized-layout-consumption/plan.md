# Implementation Plan — Flowchart ELK Finalized Layout Consumption

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_strategies.py` (split `_compile_flowchart`); `scripts/mermaid_render/layout/elk_adapter.py` (typed exception handling); `scripts/mermaid_render/layout/_geometry.py` (verify/extend `LayoutMetadata` fields); `tests/test_flowchart_compile.py` (new or extended); `tests/test_elk_adapter.py` (typed exception tests).
2. Done when: `pytest tests/` passes; `grep -n "_route_edges" scripts/mermaid_render/layout/_strategies.py` shows only the fallback path; no successful ELK call is followed by `_route_edges`; all `edge_id` lookups in the flowchart pipeline use `edge_id`, not `(src, dst)`.
3. Not changing: the ELK subprocess itself; `elk_adapter.py` serialization direction (`_to_elk_json`); renderer HTML/SVG painter logic (painters receive unchanged `FinalizedLayout`); sequence, ER, class, architecture, or requirement compilers.

**Declined patterns:**
- Tempted to combine parse and build into one function for brevity; declining — the spec requires five separate functions to make each stage independently testable.
- Tempted to add a retry mechanism when ELK fails; declining — typed exceptions and a fallback are sufficient; retries introduce non-determinism.
- Tempted to use `(src, dst)` as a local lookup cache for performance; declining — the spec prohibits this; use `edge_id` even if it requires a dict rebuild.

---

## Tasks

### Task 1: Split `_compile_flowchart` into five functions
Depends on: none
Verification: TDD

**Tests:**
- `test_parse_flowchart_semantics_returns_semantic_model`: call `parse_flowchart_semantics(source)` and assert the result has no layout coordinates.
- `test_build_flowchart_layout_graph_has_edge_ids`: call `build_flowchart_layout_graph(semantic)` and assert all edges have a non-empty `edge_id`.
- `test_five_functions_exist`: assert each of the five function names is importable from the strategies module.

**Approach:**
- Extract `parse_flowchart_semantics(source: str) -> FlowchartSemantics` — parser call only.
- Extract `build_flowchart_layout_graph(semantics: FlowchartSemantics) -> LayoutGraph` — semantic → graph.
- Extract `layout_flowchart_with_elk(graph: LayoutGraph, opts) -> FinalizedLayout` — ELK call.
- Extract `enrich_flowchart_finalized_layout(layout: FinalizedLayout, semantics) -> FinalizedLayout` — immutable enrichment.
- Extract `layout_flowchart_with_python_fallback(graph, opts) -> FinalizedLayout` — existing fallback.
- Extract `validate_flowchart_layout(layout: FinalizedLayout)` — post-layout assertion.
- Keep the outer `_compile_flowchart` as an orchestrator calling the five functions.

---

### Task 2: Direct FinalizedLayout return on ELK success
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_elk_success_not_followed_by_route_edges`: mock ELK to return a valid `FinalizedLayout`; compile a flowchart; assert `_route_edges` is not called.
- `test_elk_success_not_flattened`: mock ELK; compile; assert no `_Node.x` or `_Node.y` assignment after ELK returns.
- `test_html_svg_painters_receive_same_finalized_layout`: compile a flowchart; capture the `FinalizedLayout` instance passed to the HTML painter and the SVG painter; assert `html_layout is svg_layout` (AC7).

**Approach:**
- In `layout_flowchart_with_elk`, after receiving the ELK result, call `enrich_flowchart_finalized_layout` and return.
- Remove any post-ELK conversion into `_Node.x/_Node.y`, tuple group bboxes, or route dicts.
- Remove the `_route_edges` call that currently follows successful ELK output.

---

### Task 3: Replace terminal-circle whole-diagram fallback
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_terminal_circle_uses_elk`: compile a flowchart with a terminal circle; assert `layout.metadata.backend == "elkjs"`; assert `metadata.fallback_reason is None`.
- `test_terminal_circle_semantic_kind_preserved`: compile a flowchart with a terminal circle; assert the resulting node has the correct semantic kind annotation.

**Approach:**
- Locate the condition in the current code that triggers whole-diagram fallback for terminal circles.
- Replace with: represent the terminal symbol as a measured ELK node with `shape=TerminalCircle`; pass it to ELK; apply shape-boundary clipping only after ELK layout is complete.
- Do not call the Python fallback for the whole diagram.

---

### Task 4: Replace self-loop whole-diagram fallback
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_self_loop_local_repair_only`: compile a flowchart with one self-loop and two normal edges; assert the two normal edges have `waypoints` from ELK; assert the self-loop has a repaired local geometry.
- `test_self_loop_does_not_trigger_global_fallback`: compile; assert `metadata.fallback_reason is None` (no global fallback).

**Approach:**
- Locate the self-loop detection that currently triggers the whole-diagram fallback.
- Replace with: after ELK layout, detect any edge whose `src_node_id == dst_node_id` and whose ELK-returned waypoints are invalid (zero-length or single point); apply a local self-loop geometry repair to that edge only.
- Other edges retain their ELK geometry unchanged.

---

### Task 5: Typed exception handling and metadata
Depends on: Tasks 2, 3, 4
Verification: TDD

**Tests:**
- `test_elk_unavailable_produces_typed_fallback`: raise `ElkUnavailable` from the ELK call; assert `metadata.fallback_reason == "elk-unavailable"`.
- `test_unexpected_exception_propagates`: raise `RuntimeError` from the ELK call; assert it propagates with fixture context in the message, not a silent fallback.
- `test_metadata_populated_on_elk_success`: compile a flowchart; assert `metadata.backend`, `metadata.algorithm` are non-empty.
- `test_metadata_populated_on_fallback`: trigger fallback; assert `metadata.backend`, `metadata.fallback_reason` are non-empty.

**Approach:**
- Catch only `ElkUnavailable` and `ElkInvalidResult` in the ELK call site; all other exceptions propagate.
- On `ElkUnavailable`: call `layout_flowchart_with_python_fallback`; set `metadata.fallback_reason = "elk-unavailable"`.
- On success: set `metadata.backend = "elkjs"`, `metadata.algorithm = "layered"`.
- For unexpected exceptions: wrap in a `FlowchartLayoutError(fixture=..., source=...) from exc` and re-raise.

---

### Task 6: Edge-ID–based metadata migration
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_edge_metadata_by_edge_id`: construct a flowchart with parallel edges; assert each is retrievable by `edge_id` from the enrichment dict; assert `(src, dst)` lookup is absent.
- `test_no_src_dst_tuple_keys`: `grep -n "src_id, dst_id" scripts/mermaid_render/layout/_strategies.py` returns zero matches for lookup dict keys.

**Approach:**
- In `enrich_flowchart_finalized_layout`, build enrichment dicts keyed by `edge_id`.
- Replace any `{(src, dst): metadata}` lookup with `{edge_id: metadata}`.
- In `build_flowchart_layout_graph`, assign `edge_id` to every `LayoutEdge` before ELK processing.
