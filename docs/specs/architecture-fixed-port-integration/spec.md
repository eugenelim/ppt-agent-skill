# Architecture Fixed-Port Integration

Mode: full (ELK integration test; fixed-port semantics; fallback correctness)

- **Status:** Approved

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

- [ ] AC1: Integration test runs actual elkjs subprocess; `layout_backend = "elkjs"`;
  `fallback_reason = null`; test fails if ELK is unavailable.
- [ ] AC2: ELK result is consumed directly; the Python router is not called after a
  successful ELK layout.
- [ ] AC3: All four declared port sides preserved through ELK: `lb:R`, `api:R` (×2),
  `api:B`, with matching destination sides `L:api`, `L:db`, `T:cache`, `L:queue`.
- [ ] AC4: First and last route segment tangents agree with the declared source and
  destination sides for all four edges.
- [ ] AC5: Python fallback preserves all four declared source/destination sides; no
  finalized port remains `PortSide.AUTO`.
- [ ] AC6: Python fallback raises a typed error rather than silently substituting AUTO
  when it cannot honor a port-side constraint.
- [ ] AC7: All five services (`lb`, `api`, `db`, `cache`, `queue`) exist in the layout.
- [ ] AC8: All five services are inside the Cloud Platform group.
- [ ] AC9: No edge crosses a service interior; Cloud Platform title band is clear.
- [ ] AC10: Each relation has a stable `edge_id` in both ELK and fallback lanes.
- [ ] AC11: `faithful_mermaid=True` output contains no synchronous or service-boundary
  legend.

**Note on `layout_backend` vocabulary:** architecture's native `backend` field uses `"elk-js"`
(not `"elkjs"`) for the ELK path. The `Provenance.layout_backend` normalization maps
`"elk-js"` → `"elkjs"` for consistent cross-compiler provenance.

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
