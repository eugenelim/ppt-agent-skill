# Mermaid State Diagram Conformance

Mode: full (multi-fixture; recursive index; semantic/routing endpoint separation)

- **Status:** Draft

Dependencies: mermaid-oracle-runtime-unification, mermaid-text-measurement-adoption,
flowchart-elk-finalized-layout-consumption, mermaid-recursive-compound-layout,
mermaid-shape-boundary-exactness, mermaid-flowchart-conformance (shared
`tests/geometry_verifier.py` is created by that item and reused here)

## Objective

Complete recursive state indexing, scoped pseudo-state handling, semantic/routing endpoint
preservation, explicit boundary gates, and local cycle routing for the two in-scope state
diagram fixtures.

The state compiler already models composite states, gates, and scoped pseudo-states, but
some composite-ID and transition lookup logic traverses only top-level model states while
child emission is recursive. This can fail for deeper nesting. Flowchart integration also
needs edge-ID-based metadata and targeted handling of terminal and self-loop geometry.

## Boundaries

**In scope:**
- `StateIndex` dataclass: `by_id`, `parent_by_id`, `scope_by_id`, `composite_ids`,
  `initial_by_scope`, `final_by_scope` — replacing top-level-only scans with recursive
  traversal.
- Assign every transition a unique `edge_id` before any endpoint rewriting.
- Preserve per-transition: `semantic_source_id`, `semantic_target_id`,
  `routing_source_id`, `routing_target_id`, `source_scope`, `target_scope`,
  `entry_gate_id`, `exit_gate_id`.
- Key all transition metadata by `edge_id`.
- Scoped internal initial and final states: pseudo-state nodes with collision-free IDs.
- Dedicated state-symbol geometry: filled circle (initial), concentric-ring state-final
  (final).
- Composite-to-external: retain composite as semantic endpoint; route through explicit
  exit gate; begin visible external route on composite boundary.
- External-to-composite: terminate on entry gate; retain declared semantic target.
- Internal transitions inside composite unless semantics cross scope.
- Local cycle routing: route around the smallest relevant state subset, not a global
  canvas lane.
- Self-loop handling: local geometry repair, no whole-diagram fallback.
- Validation: scoped containment, pseudo-state scope, transition scope, gate ownership,
  semantic/routing endpoint consistency.
- Fixtures: `statediagram-complex`, `statediagram-nested`.

**Out of scope:**
- Flowchart, ER, class, architecture, requirement diagrams.
- New pseudo-state types beyond initial and final.
- Changes to the ELK adapter beyond how state graph hierarchy is passed.

**Never:**
- Use top-level-only state scan when the model has composite states.
- Use `(src, dst)` as transition identity.
- Force a whole-diagram backend fallback for a single self-loop.

## Acceptance Criteria

- [ ] AC1 (statediagram-complex): Every state and transition has a unique identifier;
  local cycles are confined to their relevant states; labels are associated by edge ID.
- [ ] AC2 (statediagram-nested): The `Processing` composite contains all internal states
  and pseudo-states; internal routes remain inside `Processing`; external transitions
  begin or end on explicit `Processing` gates; `Processing` remains the semantic endpoint
  where declared; global and internal final states remain distinct; nested lookup works
  beyond one composite depth.
- [ ] AC3: `StateIndex` provides `by_id`, `parent_by_id`, `scope_by_id`,
  `composite_ids`, `initial_by_scope`, and `final_by_scope` populated by recursive
  traversal (not top-level-only scan).
- [ ] AC4: Every transition has a unique `edge_id` assigned before endpoint rewriting;
  all metadata keyed by `edge_id`, not `(src, dst)`.
- [ ] AC5: Composite-to-external transitions route through an explicit exit gate; the
  visible external route begins on the composite boundary.
- [ ] AC6: A self-loop is handled without triggering a whole-diagram fallback; only
  the self-loop edge is affected by the local repair.
- [ ] AC7: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

All tests compile from source. ELK-dependent tests are gated with `@requires_elk`.

- **StateIndex recursion:** construct a three-level hierarchy; assert `by_id` contains
  all states at all levels; assert `parent_by_id` correctly maps inner states.
- **Unique edge IDs:** compile `statediagram-complex`; assert all `edge_id` values are
  unique across all transitions.
- **Endpoint preservation:** for a known composite-to-external transition, assert
  `semantic_source_id` equals the composite ID (not the gate proxy ID).
- **Entry gate:** for a known external-to-composite transition, assert the route
  terminates at a gate node whose `group_id` matches the composite.
- **Self-loop local repair:** compile `statediagram-complex` which contains at least one
  self-loop; assert the result's `metadata.fallback_reason` is None (ELK used, not
  whole-diagram fallback).
- **Internal route confinement:** compile `statediagram-nested`; for all edges whose
  source and target are both in `Processing`, assert all waypoints are within
  `Processing`'s group bounds.
- **Final state distinctness:** compile `statediagram-nested`; assert the global final
  state and the `Processing`-internal final state have distinct IDs.
- **Geometry verifier:** run the reusable geometry verifier (from
  `mermaid-flowchart-conformance`) on both state fixtures; assert zero violations.
