# Architecture Fixed-Port Integration

Mode: full (ELK integration test; fixed-port semantics; fallback correctness)

- **Status:** Shipped

Dependencies: `docs/specs/eight-case-validation-and-provenance`

Constrained by: `docs/adr/001-elk-layout-engine.md`

## Objective

Validate the existing architecture ELK implementation with the real locked elkjs runtime
and make the Python fallback preserve declared side semantics.

Do not redesign the successful ELK path.

Fixture in scope: `architecture-complex`

```
architecture-beta
  group cloud(cloud)[Cloud Platform]
  service lb(gateway)[Load Balancer] in cloud
  service api(server)[API Server] in cloud
  service db(database)[Database] in cloud
  service cache(server)[Cache] in cloud
  service queue(pipeline)[Message Queue] in cloud
  lb:R --> L:api
  api:R --> L:db
  api:B --> T:cache
  api:R --> L:queue
```

## Boundaries

**In scope:**
- **Real ELK integration test:** runs the actual elkjs subprocess; does not mock
  `layout_with_elk`; installs dependencies from the committed lockfile; requires
  `layout_backend = "elkjs"` and `fallback_reason = null`; fails the integration lane if
  ELK is unavailable; verifies the successful ELK result is returned directly without
  being rerouted through the Python router.
- **Fixed port semantics preserved:** `lb:R-->L:api`, `api:R-->L:db`, `api:B-->T:cache`,
  `api:R-->L:queue`. At each stage retain: `edge_id`, declared source side, declared
  destination side, finalized source port, finalized destination port, first route
  tangent, last route tangent. First and last route segments agree with declared sides.
- **Fallback correctness:** replace `PortSide.AUTO` construction in the Python fallback
  so that declared source/destination sides are copied into finalized `PortLayout`;
  endpoint positions are computed from the declared side of the visible service boundary;
  endpoint directions point outward from source and inward toward destination; routing
  starts and ends at those fixed ports; if the fallback cannot honor a constraint, raise a
  typed architecture layout error (not silent AUTO replacement).
- **Architecture validation assertions:** all five services exist; all services are inside
  Cloud Platform; Cloud Platform title band is clear; no edge crosses a service interior;
  all four source-side declarations match; all four destination-side declarations match; no
  finalized architecture port remains AUTO; each relation has a stable `edge_id`; backend
  provenance derived from `LayoutMetadata`.
- **Faithful mode guard:** `faithful_mermaid=True` must not add a synchronous legend, a
  service-boundary legend, or infer business semantics beyond the architecture source.

**Out of scope:**
- Redesigning the ELK path for architecture diagrams.
- New architecture syntax or diagram types.
- Changes to flowchart or sequence architecture handling.

**Never:**
- Mock `layout_with_elk` in the authoritative integration test.
- Silently replace a declared port side with `PortSide.AUTO` in the fallback.
- Use a preexisting gallery screenshot as the acceptance oracle.

## Acceptance Criteria

- [x] AC1: Integration test runs actual elkjs subprocess; `layout_backend = "elkjs"`;
  `fallback_reason = null`; test fails if ELK is unavailable.
  (`tests/test_architecture_elk_integration.py`, `@pytest.mark.elk_integration`.)
- [x] AC2: ELK result is consumed directly; the Python router is not called after a
  successful ELK layout.
- [x] AC3: All four declared port sides preserved through ELK: `lb:R`, `api:R` (×2),
  `api:B`, with matching destination sides `L:api`, `L:db`, `T:cache`, `L:queue`.
- [x] AC4: First and last route segment tangents agree with the declared source and
  destination sides for all four edges.
- [x] AC5: Python fallback preserves all four declared source/destination sides; no
  finalized port remains `PortSide.AUTO`.
- [x] AC6: Python fallback raises a typed error rather than silently substituting AUTO
  when it cannot honor a port-side constraint.
- [x] AC7: All five services (`lb`, `api`, `db`, `cache`, `queue`) exist in the layout.
- [x] AC8: All five services are inside the Cloud Platform group.
- [ ] AC9 (deferred: arch-elk-edge-interior-crossing): No edge crosses a service
  interior; Cloud Platform title band is clear. Holds on the Python fallback
  (validated clean by the segment-aware validators); the ELK path has a
  pre-existing `api→cache` route that clips `queue`'s interior for this fixture.
  Fixing it requires changing ELK's architecture edge routing, which this spec's
  Never/Out-of-scope constraints forbid ("do not redesign the successful ELK path").
- [x] AC10: Each relation has a stable `edge_id` in both ELK and fallback lanes.
- [x] AC11: `faithful_mermaid=True` output contains no synchronous or service-boundary
  legend.

**Note on `layout_backend` vocabulary:** architecture's native `backend` field uses `"elk-js"`
(not `"elkjs"`) for the ELK path. The `Provenance.layout_backend` normalization maps
`"elk-js"` → `"elkjs"` for consistent cross-compiler provenance.

## Deviations

- **`compile_architecture` return type unified to `ArchitectureDiagramLayout`.**
  The prior `mermaid-architecture-metadata-preservation` spec returned a
  `FinalizedLayout` directly on the ELK success path. That conflicts with the
  ini-003 eight-case AC9 harness (item 1, merged), which reads
  `.services`/`.groups`/`.edges` — so `architecture-complex` failed on `main`
  whenever elkjs was installed. Item 5 unifies the return type: both the ELK and
  fallback paths return the documented `ArchitectureDiagramLayout`; the
  `FinalizedLayout` is obtained via `arch_to_finalized()`. The ELK geometry is
  consumed directly (no re-routing — AC2 preserved). The prior spec's conformance
  tests (`tests/test_architecture_conformance.py`) were updated to assert their
  invariants on `arch_to_finalized(compile_architecture(...))`.
- **AC9 ELK-path interior crossing deferred** (see AC9 above), anchor
  `arch-elk-edge-interior-crossing`. The same anchor covers the pre-existing
  ELK-only architecture geometry test failures (`test_arch_port_acceptance`
  edge-face inset, `test_no_edge_waypoint_inside_service`,
  `test_arch_compiled_model::TestBiRelEdge::test_birel_with_label`): ELK's port
  positions sit ~12px inside the visual node face. These fail only when elkjs is
  installed and are unchanged by this item (proven: zero new FAILED-set drift vs
  a pristine `origin/main` worktree with the same elkjs).

## Testing Strategy

| AC | Verification mode |
|----|-------------------|
| AC1 | Goal-based: real ELK subprocess run; assert `layout_backend == "elkjs"` via Provenance normalization |
| AC2 | Goal-based: instrument Python router; assert it is not called after ELK succeeds |
| AC3–AC4 | TDD: render via ELK; assert declared port sides and tangents for all 4 edges |
| AC5–AC6 | TDD: monkeypatch ELK unavailable; assert declared sides preserved; raise on conflict |
| AC7–AC9 | TDD: inspect layout for service containment, title-band clearance, no edge crossing |
| AC10 | TDD: ELK and fallback; assert stable unique `edge_id` per relation |
| AC11 | TDD: render `to_html(faithful_mermaid=True)`; grep for legend elements |
