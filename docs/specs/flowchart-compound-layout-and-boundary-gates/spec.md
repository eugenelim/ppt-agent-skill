# Flowchart Compound Layout and Boundary Gates

Mode: full (layout algorithm — bottom-up compound; boundary gates; empty-group packing)

- **Status:** Approved

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

- [ ] AC1: `flowchart-empty-subgraph` — both groups exist; Empty Group has nonzero
  measured bounds; Empty Group does not overlap or touch Group With Node; Group With Node
  contains A; B is outside both groups; A→B route does not cross Empty Group; test fails
  (not skips) when empty group is absent.
- [ ] AC2: `flowchart-cross-scope-edge` — every route point and segment is inside the
  finalized canvas; B→C enters Inner TB exactly once at a declared gate on the Inner TB
  boundary; C→D remains inside Inner TB; D→E exits Inner TB exactly once at a declared
  gate; neither cross-scope route crosses the group title band or leaves/re-enters the
  group; canvas is finalized after route construction.
- [ ] AC3: `flowchart-groups-complex` — Frontend contains UI and Cache; Backend Services
  contains API, Auth, Worker; Data Layer contains DB and Queue; sibling group bounds do
  not overlap; no relationship segment crosses an unrelated group interior or title band;
  Worker→Queue uses a local cross-group route; API→DB and Cache→DB do not route around
  the full canvas perimeter; routes to the same target use deterministic distinct channels
  or a modeled junction.
- [ ] AC4: `flowchart-inner-direction` — Pipeline uses local LR layout; Ingest, Transform,
  Load have monotonically increasing x coordinates; Source→Ingest enters through a
  Pipeline boundary gate; Load→Sink exits through a Pipeline boundary gate; neither
  external route uses x=0 or a global canvas-edge lane unless it is the shortest valid
  local channel; ELK is attempted first; `layout_backend` and `fallback_reason` accurately
  identify the selected path; no post-finalization coordinate shuffle.
- [ ] AC5: All four fixtures attempt ELK first and consume a successful ELK result
  directly without calling the Python router.
- [ ] AC6: The Python compound fallback processes groups bottom-up with measured proxies;
  it does not use prior global placement coordinates.
- [ ] AC7: `BoundaryGate` records exist for every cross-scope edge; each gate lies on the
  corresponding group boundary within tolerance.

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
