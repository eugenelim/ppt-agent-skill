# Flowchart Compound Layout and Boundary Gates

Mode: full (layout algorithm — bottom-up compound; boundary gates; empty-group packing)

- **Status:** Shipped

Dependencies: `docs/specs/eight-case-validation-and-provenance`

Constrained by: `docs/adr/001-elk-layout-engine.md`

## Objective

Replace the current post-global-placement compound correction with a true bottom-up
compound layout, and make boundary gates actual route waypoint constraints.

Fixtures in scope: `flowchart-cross-scope-edge`, `flowchart-empty-subgraph`,
`flowchart-groups-complex`, `flowchart-inner-direction`.

## Boundaries

**In scope:**
- **Remove unconditional inner-direction fallback:** the current code routes any diagram
  with a group `local_direction` different from the outer direction to the Python fallback.
  Change this: build the full compound `LayoutGraph` with each group's `local_direction`
  and attempt ELK first for all four scoped flowchart fixtures. Consume a successful ELK
  `FinalizedLayout` directly without invoking the Python router.
- **True Python compound fallback:** replace the current sequence (global layout → move
  members → separate groups → recompute boxes) with bottom-up: build the complete group
  tree; partition edges by scope (internal/entry/exit/sibling/multi-level); process groups
  bottom-up; for each group measure title, lay out direct nodes and child-group proxies
  using `local_direction`, reserve title-band and padding, route internal edges, compute
  finalized group size, expose as a measured proxy; lay out the parent from measured
  proxies; expand child proxies by translating already-finalized internal geometry.
- **First-class empty groups:** an empty group is a real measured compound proxy. Its size
  derives from measured title width/height, title padding, content padding, deterministic
  minimum content w/h. It is positioned through the same parent packing as nonempty
  proxies. It must not sit at x=0,y=0 by default; must not overlap a sibling group.
- **Boundary gates as route waypoints:** for every cross-scope relationship, select
  deterministic entry/exit sides based on source/destination positions, group
  `local_direction`, route length, crossing minimization, and title-band avoidance. Create
  explicit `BoundaryGate` records. Insert each gate into the actual route as a waypoint.
  Preserve semantic source/destination, routing source/destination, source/destination
  scope, entry/exit gate IDs. Route the internal portion within the group and the external
  portion outside unrelated groups.
- **Group-aware routing obstacles:** treat unrelated node interiors, unrelated group
  interiors, group title bands, allocated label rectangles, allocated compound gates, and
  marker-clearance zones as routing obstacles. Use local channels between relevant groups.

**Out of scope:**
- Changes to non-flowchart compound types (architecture, sequence, state).
- Adding a new graph-layout engine.
- Replacing ELK Layered as the primary engine.
- Fixture-specific coordinates or route patches.

**Never:**
- Use a prior global placement's coordinates as the starting position for local group
  layout.
- Add an invisible gate node and reconstruct route points without verifying the boundary
  crossing.
- Select a remote canvas edge as the default route lane when a local channel exists.

## Acceptance Criteria

- [x] AC1: `flowchart-empty-subgraph` — both groups exist; Empty Group has nonzero
  measured bounds; Empty Group does not overlap or touch Group With Node; Group With Node
  contains A; B is outside both groups; A→B route does not cross Empty Group; test fails
  (not skips) when empty group is absent.
- [x] AC2: `flowchart-cross-scope-edge` — every route point and segment is inside the
  finalized canvas; B→C enters Inner TB exactly once at a declared gate on the Inner TB
  boundary; C→D remains inside Inner TB; D→E exits Inner TB exactly once at a declared
  gate; neither cross-scope route crosses the group title band or leaves/re-enters the
  group; canvas is finalized after route construction.
- [x] AC3: `flowchart-groups-complex` — Frontend contains UI and Cache; Backend Services
  contains API, Auth, Worker; Data Layer contains DB and Queue; sibling group bounds do
  not overlap; no relationship segment crosses an unrelated group interior or title band;
  Worker→Queue uses a local cross-group route; API→DB and Cache→DB do not route around
  the full canvas perimeter; routes to the same target use deterministic distinct channels
  or a modeled junction.
- [x] AC4: `flowchart-inner-direction` — Pipeline uses local LR layout; Ingest, Transform,
  Load have monotonically increasing x coordinates; Source→Ingest enters through a
  Pipeline boundary gate; Load→Sink exits through a Pipeline boundary gate; neither
  external route uses x=0 or a global canvas-edge lane unless it is the shortest valid
  local channel; ELK is attempted first; `layout_backend` and `fallback_reason` accurately
  identify the selected path; no post-finalization coordinate shuffle.
- [ ] AC5: All four fixtures attempt ELK first and consume a successful ELK result
  directly without calling the Python router.
- [x] AC6: The Python compound fallback processes groups bottom-up with measured proxies;
  it does not use prior global placement coordinates.
- [x] AC7: `BoundaryGate` records exist for every cross-scope edge; each gate lies on the
  corresponding group boundary within tolerance.

## Deviations (as shipped)

- **AC5, and AC4's "ELK is attempted first" clause, are met for the two
  non-compound grouped fixtures only; the two inner-direction compound fixtures
  ship on the bottom-up Python compound path (deferred, not infeasible).**
  `BoundaryGate` records (AC7) are currently emitted only by the Python compound
  path, and the item-1 harness's `_flowchart_counts` asserts
  `flowchart-cross-scope-edge` carries ≥2 gates via a *non-forced* compile — so
  consuming ELK's native compound result directly (AC5) would today leave
  cross-scope edges gate-less. This is **not** an inherent AC5↔AC7 impossibility:
  `_cbe_boundary_crossings` derives gates from finished route geometry and is
  engine-agnostic, so a post-ELK gate-derivation pass over ELK-produced routes
  would satisfy AC5 and AC7 jointly. That pass is **deferred** because `elkjs` is
  unavailable in this environment to verify it (backlog:
  `flowchart-compound-elk-gate-derivation`). **Resolution as shipped:** the two
  non-compound grouped fixtures (`flowchart-empty-subgraph`,
  `flowchart-groups-complex`) attempt ELK first and consume it directly on
  success; the two compound fixtures (`flowchart-cross-scope-edge`,
  `flowchart-inner-direction`) route through the gate-emitting Python compound
  path, satisfying AC1–AC3 geometry, AC4 (minus the ELK-first clause), AC6, AC7.
- **AC3 obstruction/local-route invariants are verified on the Python fallback
  path.** The live-lane tests force `MERMAID_LAYOUT_ENGINE=python` for
  determinism, so `flowchart-groups-complex`'s AC3 cleanliness is asserted on the
  fallback engine. When `elkjs` is installed this fixture ships on ELK; verifying
  AC3 on the ELK lane is folded into the deferred backlog item above.

## Testing Strategy

| AC | Verification mode |
|----|-------------------|
| AC1 | TDD: render `flowchart-empty-subgraph`; assert both groups, sizes, positions |
| AC2 | TDD: render `flowchart-cross-scope-edge` via `_compile_flowchart`; assert gate and route invariants |
| AC3 | TDD: render `flowchart-groups-complex`; assert containment, no-overlap, no-obstacle-crossing |
| AC4 | TDD: render `flowchart-inner-direction`; assert LR, monotonic x, boundary gates, ELK first |
| AC5 | Goal-based: instrument `_compile_flowchart`; assert ELK call occurs and result used directly |
| AC6 | TDD: in fallback mode, instrument group processing; assert leaf-first order and proxy sizes |
| AC7 | TDD: inspect `layout.boundary_gates`; assert gate points lie on group boundary ± 1px |
