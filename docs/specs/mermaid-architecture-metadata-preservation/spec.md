# Mermaid Architecture ELK Metadata Preservation

Mode: full (structural — removes conversion helper; edge-ID migration; multi-file)

- **Status:** Draft

Dependencies: mermaid-oracle-runtime-unification, mermaid-text-measurement-adoption,
mermaid-recursive-compound-layout

## Objective

The architecture compiler has an enrichment path capable of returning an ELK
`FinalizedLayout` directly, but the main compilation path still converts ELK routed edges
through `_elk_routes_to_specs`. That helper maps labels by `(src, dst)`, converts routed
edges into path-like dictionaries, and then reconstructs architecture edges. This loses
edge identity and risks losing fixed-side port and route metadata.

This spec removes `_elk_routes_to_specs` from the successful path, makes the enriched ELK
`FinalizedLayout` the direct return, and preserves fixed-side port constraints and edge
identity through the full pipeline.

## Boundaries

**In scope:**
- Successful ELK branch returns the enriched ELK `FinalizedLayout` directly; no
  intermediate conversion through `_elk_routes_to_specs`.
- Remove `_elk_routes_to_specs` from the successful path.
- Retain architecture semantic metadata by `edge_id`: service source and target, declared
  source side, declared target side, bidirectionality, label, marker semantics.
- Preserve ELK output: node bounds, compound bounds, fixed-side ports, edge sections,
  junctions, label positions, ranks, backend metadata.
- No reconstruction of successful ELK ports as generic AUTO, TOP, or BOTTOM ports.
- Replace `(src, dst)` label lookup with `edge_id`.
- Use shared `TextMeasurer` for service labels, group labels, group minimum widths, edge
  labels.
- LR treated as preferred direction, not a reason to violate explicit side constraints.
- Heuristic/fallback path retained only for typed `ElkUnavailable`.
- Fallback satisfies the same `FinalizedLayout` contract with `backend=python-fallback`,
  `fallback_reason=elk-unavailable`.
- Tests: duplicate source/destination pairs, all four fixed sides, multiple edges sharing
  one service side, nested groups, incomplete ELK result rejection.

**Out of scope:**
- Flowchart, state, ER, class, requirement compilation.
- Changes to the ELK adapter's JSON serialization.
- New architecture diagram features.

**Never:**
- Replace a successfully returned ELK port side with AUTO after the ELK call completes.
- Use `(src, dst)` as a relation identity key anywhere in the architecture pipeline.
- Re-route a successful ELK result through the Python fallback.

## Acceptance Criteria

For `architecture-complex`:
- [ ] AC1: The four declared fixed-side constraints (`lb:R→L:api`, `api:R→L:db`,
  `api:B→T:cache`, `api:R→L:queue`) remain intact as fixed-side port constraints
  throughout compilation and serialization.
- [ ] AC2: Each relation has a unique `edge_id`.
- [ ] AC3: All services are contained within their declared group bounds.
- [ ] AC4: No successful ELK result is rerouted through the Python fallback.
- [ ] AC5: No successful ELK port side is replaced by AUTO.
- [ ] AC6: Group and edge labels use measured `TextLayout` objects (no character-count
  estimates).
- [ ] AC7: `layout.metadata.backend` and `layout.metadata.fallback_reason` are present
  in every result.
- [ ] AC8: The fallback path (when ELK is unavailable) satisfies the full `FinalizedLayout`
  contract and records `backend=python-fallback`, `fallback_reason=elk-unavailable`.
- [ ] AC9: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

Mocked-ELK tests for structural assertions; real-ELK tests gated with `@requires_elk`.

- **Fixed side preservation:** construct an architecture graph with all four cardinal
  fixed sides; assert the returned `FinalizedLayout` preserves each port side, not AUTO.
- **No _elk_routes_to_specs in success path:** assert that the successful compilation
  path does not call `_elk_routes_to_specs`; mock ELK to return a minimal valid layout.
- **Edge-id keying:** construct a graph with two services connected by two labeled
  edges; assert both edges are retrievable by `edge_id`; assert `(src, dst)` lookup is
  absent from the pipeline.
- **Duplicate service pair:** construct two edges with the same `(src, dst)` but
  different labels; assert both survive with distinct `edge_id` values and distinct
  labels.
- **Multiple edges on one side:** construct a service with three outgoing edges from the
  RIGHT side; assert all three receive distinct port positions on that side.
- **Nested groups:** construct a group containing a group; assert all services are
  contained in their declared groups after layout.
- **Incomplete ELK result rejection:** construct a mock ELK result missing required edge
  sections; assert the pipeline raises `ElkInvalidResult` rather than producing a partial
  layout.
- **Fallback contract:** trigger `ElkUnavailable`; assert the fallback result has
  `metadata.backend="python-fallback"` and `metadata.fallback_reason="elk-unavailable"`.
- **Measured labels:** assert service labels and group labels use `TextLayout`, not
  raw character-count widths.
