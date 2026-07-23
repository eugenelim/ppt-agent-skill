# Flowchart ELK Finalized Layout Consumption

Mode: full (structural — core layout pipeline; multi-file; touches fallback behavior)

- **Status:** Draft

## Objective

The flowchart and state diagram compiler currently converts successful ELK results back
into mutable `_Node`, group-bbox tuple, and route-dictionary structures before rebuilding
the final geometry. It also applies whole-diagram fallback behavior for terminal circles
and self-loops, and runs additional topology/group passes after the ELK result is
received. This second reconstruction loses the fidelity guarantees of the ELK output —
edge IDs, port sides, junction points, and route sections — and triggers the Python
fallback for the entire diagram when only a single edge type is unsupported.

This spec splits `_compile_flowchart` into focused, composable functions and makes
successful ELK output directly authoritative: the returned `FinalizedLayout` is enriched
with semantic metadata and returned, never reconstructed through mutable legacy geometry.

Depends on: `mermaid-oracle-runtime-unification` (oracle contract must be stable to
validate the new pipeline output).

## Boundaries

**In scope:**
- Split `_compile_flowchart` into: `parse_flowchart_semantics()`,
  `build_flowchart_layout_graph()`, `layout_flowchart_with_elk()`,
  `enrich_flowchart_finalized_layout()`, `layout_flowchart_with_python_fallback()`,
  `validate_flowchart_layout()`.
- On ELK success: accept the returned `FinalizedLayout`; enrich it immutably with
  semantic metadata and presentation roles; return it directly.
- Prohibition on copying successful ELK geometry into `_Node.x/_Node.y`, tuple group
  bboxes, route dictionaries, or a second call to `_route_edges`.
- Preserve through enrichment: edge IDs, node IDs, group IDs, fixed port sides, route
  sections, junction points, edge style, markers, labels, ranks, backend metadata.
- Replace whole-diagram terminal-circle fallback with a targeted approach: represent the
  terminal symbol as a measured ELK node; retain its semantic kind; apply only final
  shape-boundary clipping after layout.
- Replace whole-diagram self-loop fallback with: ELK self-loop output when valid;
  otherwise a typed local self-loop repair operating only on that edge.
- Catch only typed exceptions: `ElkUnavailable`, `ElkInvalidResult`, explicitly
  documented unsupported-feature errors. Unexpected exceptions propagate with context.
- Set `layout.metadata.backend`, `layout.metadata.algorithm`,
  `layout.metadata.fallback_reason` for every result.
- Replace edge metadata lookups keyed by `(src, dst)` with `edge_id`.
- Move post-layout assertions into `validate_flowchart_layout()`.
- HTML and SVG painters receive the same `FinalizedLayout`.

**Out of scope:**
- Sequence, ER, class, architecture, or requirement diagram compilation.
- Compound layout improvements (see `mermaid-recursive-compound-layout`).
- Shape boundary mathematics (see `mermaid-shape-boundary-exactness`).
- The ELK subprocess itself or `elk_adapter.py` internals beyond typed exception handling.

**Never:**
- Call `_route_edges` after a successful ELK result.
- Flatten a successful ELK result into mutable `_Node` geometry.
- Use `(src, dst)` as an edge identity key anywhere in the pipeline.
- Use a bare `except Exception` to silently change layout algorithms.

## Acceptance Criteria

- [ ] AC1: A successful ELK call is not followed by `_route_edges` on the same graph.
- [ ] AC2: A successful ELK call is not flattened into mutable legacy geometry
  (`_Node.x`, `_Node.y`, tuple bboxes, route dictionaries).
- [ ] AC3: Terminal circle symbols do not force the entire diagram onto the Python
  fallback; they are represented as measured ELK nodes with semantic kind preserved.
- [ ] AC4: A self-loop edge does not force unrelated edges onto the Python fallback; the
  repair operates only on the self-loop edge with a typed local fix.
- [ ] AC5: Every fallback has a typed reason recorded in `layout.metadata.fallback_reason`.
- [ ] AC6: Edge style, markers, labels, ports, and junction points survive unchanged
  through the enrichment step.
- [ ] AC7: HTML and SVG painters receive the same `FinalizedLayout` returned by the
  pipeline — no painter-internal geometry reconstruction.
- [ ] AC8: All edge metadata lookups use `edge_id`, not `(src, dst)`.
- [ ] AC9: `layout.metadata.backend` and `layout.metadata.algorithm` are populated for
  every result (ELK and fallback).
- [ ] AC10: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

All tests use mocked ELK output where the ELK subprocess is unavailable. Real-subprocess
tests are gated with `@requires_elk`.

- **Pipeline split:** assert each of the five functions exists and has the correct
  signature; assert `parse_flowchart_semantics` returns a semantic model with no layout
  coordinates.
- **ELK-not-followed-by-route-edges:** mock `layout_flowchart_with_elk` to return a
  `FinalizedLayout`; assert `_route_edges` is not called on the same graph.
- **Immutable enrichment:** assert that enriching a `FinalizedLayout` does not mutate
  its `nodes`, `edges`, or `groups` collections; assert the returned object is a new
  instance (or the same with only metadata added).
- **Terminal-circle targeted handling:** construct a graph with a terminal circle;
  assert the result comes from ELK, not the Python fallback; assert
  `metadata.fallback_reason` is `None`.
- **Self-loop local repair:** construct a graph with exactly one self-loop; assert the
  repair touches only that edge; assert other edges retain their ELK geometry.
- **Typed fallback only:** assert that `ElkUnavailable` is caught and produces a typed
  fallback with reason; assert that an unexpected exception propagates with fixture
  context rather than silently switching backends.
- **Edge-id keying:** construct a graph with two parallel edges between the same nodes;
  assert each is retrievable by its unique `edge_id`, not by `(src, dst)`.
- **Backend metadata:** assert every result has non-empty `metadata.backend` and
  `metadata.algorithm`.
