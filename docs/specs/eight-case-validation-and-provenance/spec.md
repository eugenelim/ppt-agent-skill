# Eight-Case Validation and Provenance

Mode: full (validation infrastructure — canonical runner; canvas/segment/gate/non-vacuous checks)

- **Status:** Shipped

Constrained by: `docs/adr/001-elk-layout-engine.md`

Dependencies: none — gates items 2–6.

## Objective

Make validation and provenance trustworthy for the eight scoped fixtures so that later
items have a reliable acceptance harness.

Fixtures in scope:
- `architecture-complex`
- `flowchart-arrows-defs`
- `flowchart-cross-scope-edge`
- `flowchart-empty-subgraph`
- `flowchart-groups-complex`
- `flowchart-inner-direction`
- `sequence-box-unsupported`
- `sequence-nested-fragments`

## Boundaries

**In scope:**
- **Canonical eight-fixture runner:** one command that renders only the eight scoped
  fixtures across four render variants (to_html/to_svg × faithful_mermaid True/False).
  Architecture and flowchart fixtures also run an ELK-required lane and a Python-fallback
  lane. Sequence fixtures run only the canonical-sequence-geometry lane.
- **Backend provenance fields:** Seven named fields in a `Provenance` dataclass, all
  separate — never derived from each other:
  1. `renderer_api`: `"to_html"` | `"to_svg"` — which public function was called
  2. `output_format`: `"html"` | `"svg"` — the output format
  3. `semantic_compiler`: `"flowchart"` | `"architecture"` | `"sequence"` — which compiler
  4. `layout_backend`: `"elkjs"` | `"python-fallback"` | `"sequence-geometry"` — normalized
     from the compiler's native `backend` value: `"elkjs"`→`"elkjs"`, `"elk-js"`→`"elkjs"`,
     `"python"`→`"python-fallback"`, sequence path → `"sequence-geometry"`
  5. `fallback_reason`: `None` | typed string — from `LayoutMetadata.fallback_reason`
  6. `node_version`: Node.js version string (ELK-required lane only; `None` for others)
  7. `elkjs_version`: elkjs package version string (ELK-required lane only; `None` for others)

  The test runner stamps these fields from the returned `LayoutMetadata` and call-site
  context. `layout_backend` is a NORMALIZED read — never rename `LayoutMetadata.backend`.
  Sequence diagrams carry no `LayoutMetadata`; stamp `semantic_compiler = "sequence"` and
  `layout_backend = "sequence-geometry"` at the call site.
- **Canvas validation:** every edge waypoint and every route segment must lie inside the
  declared canvas with a small numeric tolerance. Canvas bounds are finalized after all of
  nodes, groups, sequence boxes, fragment bounds, routes, markers, edge/message labels,
  and compound gates are known. Negative-coordinate layouts are translated into the
  positive coordinate space (not clipped).
- **Segment-vs-rectangle intersection validation:** replace waypoint-only collision checks
  with segment-versus-rectangle intersection. Test each route segment against unrelated
  node interiors, unrelated group interiors, group title bands, edge-label rectangles, and
  marker-clearance regions. Exclude the first/last segment portions that legitimately meet
  their own endpoint node or group gate.
- **Compound gate validation:** for every cross-scope edge, require explicit entry/exit
  gate records on the corresponding group boundary; require the route to contain the gate
  as an exact waypoint or within tolerance; require exactly one boundary crossing per
  entry/exit; reject routes that bypass their gate, leave/re-enter the same group, or
  cross an unrelated group.
- **Non-vacuous case contracts:** minimum assertion counts per fixture (see Acceptance
  Criteria). A status of PASS when zero assertions executed must fail validation.
- **Regression test:** `flowchart-cross-scope-edge` historical off-canvas state
  (canvas h=264, B→C route y=293) must fail the new canvas validator.

**Out of scope:**
- Any change to diagram rendering logic (layout algorithms, painters, parsers).
- New fixtures beyond the eight scoped ones.
- Visual/raster comparison.
- Mocking ELK availability outside the designated fallback lane.

**Ask first:**
- If a fixture's live lane fails for reasons not in the known-broken list from items 2–6.

**Never:**
- Report a PASS when zero assertions executed.
- Infer `layout_backend` from `output_format`.
- Clip or discard geometry that has negative coordinates.
- Rename `LayoutMetadata.backend`; always derive `layout_backend` from it with the normalization mapping.
- Add a new pip dependency or new top-level directory.

## Acceptance Criteria

- [x] AC1: One command (`make eight-case` or `pytest -m eight_case`) renders all eight
  fixtures across all required lanes and fails loudly on any lane error.
- [x] AC2: ELK-required lane for architecture/flowchart fixtures: skipped cleanly when
  a real ELK/Node runtime is absent (via the `requires_elk` marker); when ELK is
  present, fails if the compiler selects the Python fallback and records Node and
  elkjs versions in provenance.
- [x] AC3: Fallback lane: explicitly disables ELK; requires `layout_backend ==
  "python-fallback"`; requires a typed `fallback_reason`.
- [x] AC4: Sequence fixtures report `semantic_compiler = "sequence"` and `layout_backend
  = "sequence-geometry"` — never `"native-svg"`.
- [x] AC5: `renderer_api`, `output_format`, and `layout_backend` are separate fields in
  all provenance records.
- [x] AC6: The historical `flowchart-cross-scope-edge` off-canvas state (h=264, y=293)
  fails the canvas validator in a regression test.
- [x] AC7: Complete route segments (not only waypoints) participate in obstruction and
  canvas validation.
- [x] AC8: Compound gate validation rejects routes that bypass declared gates or cross
  unrelated groups.
- [x] AC9: Minimum assertion counts per fixture:
  - `architecture-complex`: 5 services, 1 group, 4 relations, 8 endpoint-side assertions
  - `flowchart-arrows-defs`: 4 nodes, 5 edges, 3 distinct edge-style assertions
  - `flowchart-cross-scope-edge`: 5 nodes, 1 group, 4 edges, 2 cross-scope relationships, entry/exit gate assertions
  - `flowchart-empty-subgraph`: 2 groups, 1 empty group, 2 nodes, 1 relation
  - `flowchart-groups-complex`: 3 groups, 7 nodes, 8 relations, containment/route-obstacle assertions
  - `flowchart-inner-direction`: 1 group, 5 nodes, 4 relations, local-direction/gate assertions
  - `sequence-box-unsupported`: 4 participants, 2 boxes, 4 messages, box membership/color assertions
    (box membership/color assertions were deferred to item 2 and landed with the shared sequence
    compiler — `seq-box-membership-assertions` is resolved; the AC9 contract now asserts box count,
    Group A/B membership, and accent colors alongside participant and message counts.)
  - `sequence-nested-fragments`: 2 participants, 2 nested fragments, 1 branch, 3 messages, fragment-parent/event-containment assertions
- [x] AC10: All seven provenance fields (`renderer_api`, `output_format`, `semantic_compiler`,
  `layout_backend`, `fallback_reason`, `node_version`, `elkjs_version`) are populated from
  compiler/layout metadata and call-site context — none are inferred from each other.

## Testing Strategy

| AC | Verification mode |
|----|-------------------|
| AC1 | Goal-based check: `pytest -m eight_case` runs without error |
| AC2 | TDD: ELK-required lane asserts backend == "elkjs", versions present; skipped if ELK absent |
| AC3 | TDD: monkeypatch `layout_with_elk` to raise `ElkUnavailable`; assert fallback fields |
| AC4 | TDD: call `compile_sequence` directly; assert stamped fields |
| AC5 | TDD: assert fields are independent keys in the Provenance record |
| AC6 | TDD: fabricate the historical geometry; assert validator rejects it |
| AC7 | TDD: fabricate a layout where a segment exits canvas between valid waypoints |
| AC8 | TDD: fabricate a layout with a gate bypass; assert validator rejects it |
| AC9 | TDD: one contract test per fixture, each asserting minimum assertion count |
| AC10 | TDD: covered by AC2/AC3/AC4/AC5 together |
