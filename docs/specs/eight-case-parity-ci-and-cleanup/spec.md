# Eight-Case Parity CI and Cleanup

Mode: full (CI gate — deterministic matrix; hard failure conditions; dead-code deletion)

- **Status:** Approved

Dependencies:
- `docs/specs/sequence-shared-compiler-and-native-scene`
- `docs/specs/flowchart-compound-layout-and-boundary-gates`
- `docs/specs/flowchart-arrow-style-conformance`
- `docs/specs/architecture-fixed-port-integration`

## Objective

Make the eight scoped fixtures a deterministic CI gate and remove the obsolete paths made
unnecessary by items 1–5.

## Boundaries

**In scope:**
- **CI matrix:** for every scoped fixture: output (to_html, to_svg) × presentation
  (faithful, editorial). For architecture and flowchart: additionally backend (ELK required,
  Python fallback). For sequence: compiler (canonical sequence geometry only).
- **Hard CI failures:** hidden backend fallback; missing backend provenance; incorrect
  renderer/layout-backend field usage; route waypoint outside canvas; route segment outside
  canvas; route segment crossing an unrelated node/group/title-band; missing or off-boundary
  compound gate; cross-scope route bypassing its gate; missing empty group; overlapping or
  touching sibling groups; incorrect local group direction; missing sequence box; incorrect
  box membership; missing sequence fragment; incorrect nested-fragment parent; missing
  flowchart edge style; incorrect architecture fixed-side port; HTML/SVG semantic or
  geometry divergence; zero-check comparison pass; nondeterministic normalized output.
- **Structured artifacts per fixture:** fixture source hash, implementation git SHA,
  compiler metadata, layout metadata, normalized nodes/groups/boxes/fragments, normalized
  routes/messages, labels/markers, gates, validation result, assertion count, reference
  extraction result, fresh HTML/SVG comparison artifact.
- **Cleanup — delete obsolete paths:**
  - `layout/sequence.py` and its independent parser (already retired in item 2).
  - `native_svg._sequence_scene` legacy delegation (already retired in item 2).
  - Obsolete sequence skip behavior for boxes and fragments.
  - Unconditional inner-direction Python fallback (already replaced in item 3).
  - Post-global-placement group correction, sibling-group pushing, bbox recomputation
    (already replaced in item 3).
  - Fallback architecture `PortSide.AUTO` construction (already fixed in item 5).
- **Cleanup — replace or delete obsolete tests:**
  - Tests that skip when an expected empty group is absent.
  - Tests that assert implementation-specific post-layout shuffling.
  - Tests that validate only waypoint positions rather than route segments.
  - Tests that call `to_html` but claim to validate the native SVG sequence path.
- **Renderer architecture documentation update:** actual shared and non-shared pipelines;
  sequence canonical geometry; ELK and fallback behavior; recursive compound layout;
  boundary gates; backend provenance; validation invariants.

**Out of scope:**
- New diagram type features.
- Changes to the renderer public API.
- New CI infrastructure providers.

**Never:**
- Use a preexisting generated artifact as the source of truth.
- Run the cleanup before all hard CI failure conditions are green.
- Remove a public renderer API without a migration path.

## Acceptance Criteria

- [ ] AC1: CI matrix runs all eight fixtures across the full output/presentation/backend
  matrix; documented command in `AGENTS.md`.
- [ ] AC2: Every hard failure condition listed above causes a CI failure, each covered by
  at least one test.
- [ ] AC3: `layout/sequence.py` is deleted; no remaining imports reference it.
- [ ] AC4: Unconditional inner-direction fallback code is removed; all four flowchart
  compound fixtures still pass.
- [ ] AC5: Post-global-placement group correction code is removed; all four flowchart
  compound fixtures still pass.
- [ ] AC6: Fallback `PortSide.AUTO` construction code is removed; architecture-complex
  still passes both ELK and fallback lanes.
- [ ] AC7: Structured artifacts are published for each fixture run.
- [ ] AC8: `docs/architecture/mermaid_renderer.md` describes the actual pipeline,
  sequence canonical geometry, ELK/fallback behavior, recursive compound layout, boundary
  gates, backend provenance, and validation invariants.
- [ ] AC9: Repeated clean runs of the full matrix produce identical normalized semantic
  and geometry records.
- [ ] AC10: No test in the test suite skips when an expected empty group is absent,
  asserts post-layout shuffling, or validates only waypoints.

## Testing Strategy

| AC | Verification mode |
|----|-------------------|
| AC1 | Goal-based: CI job exists in GitHub Actions; `make eight-case-ci` documented in AGENTS.md |
| AC2 | TDD: one test per hard-failure condition; each fabricates pathological input and asserts FAIL |
| AC3–AC6 | Goal-based: `grep -rn` for deleted symbols returns zero matches; matrix still passes |
| AC7 | Goal-based: artifacts JSON file exists for each fixture run |
| AC8 | Goal-based: `docs/architecture/mermaid_renderer.md` updated and grep-verified |
| AC9 | Goal-based: two identical runs produce byte-identical artifact JSON |
| AC10 | Goal-based: `grep -rn "pytest.mark.skip"` in tests returns zero obsoletion matches |
