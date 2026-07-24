# Implementation Plan — Architecture Fixed-Port Integration

**Status:** Approved

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `tests/test_architecture_elk_integration.py` (new/extended — real ELK
   subprocess); `scripts/mermaid_render/layout/_strategies.py` or `_compound_layout.py`
   (architecture fallback: replace `PortSide.AUTO` with declared sides); `_geometry.py`
   (`PortLayout` declared-side fields); `tests/test_architecture_conformance.py` (extend
   with gate assertions).
2. Done when: `architecture-complex` passes the real ELK integration lane (no mocks) with
   all four declared port sides verified; passes the explicit fallback lane with no
   `PortSide.AUTO` remaining; `faithful_mermaid=True` produces no legend.
3. Not changing: the ELK path for architecture diagrams (no redesign); public renderer
   API; other diagram types.

**Declined patterns:**
- Tempted to mock `layout_with_elk` in the authoritative integration test to make it
  fast; declining — spec explicitly requires the real subprocess to run.
- Tempted to silently substitute `PortSide.AUTO` when the fallback can't honor a
  declared side; declining — spec requires a typed error.
- Tempted to verify port sides only at the final HTML/SVG output; declining — spec
  requires preserving the declared side at every stage of the pipeline.

---

## Tasks

### Task 1: Real ELK integration test
Depends on: none
Verification: Goal-based check

**Done when:** `pytest tests/test_architecture_elk_integration.py -m elk_integration`
passes with the real elkjs subprocess; the test fails if `node` is unavailable; `npm ci`
is run from the committed lockfile before the test suite.

**Approach:**
- Add `tests/test_architecture_elk_integration.py` tagged `@pytest.mark.elk_integration`.
- Do not patch `layout_with_elk`; call the renderer end-to-end.
- Assert `provenance.layout_backend == "elkjs"` and `provenance.fallback_reason is None`.
- Assert the result is returned directly (not rerouted through the Python router): check
  that the Python router is not called by instrumenting it once to verify no-op.
- Record `node --version` and `elkjs` package version in provenance.

---

### Task 2: Declared port side preservation — ELK path
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_elk_lb_right_to_api_left`: render `architecture-complex` via ELK; assert the
  `lb→api` edge's source port is on the RIGHT side of `lb` and destination port is on
  the LEFT side of `api`.
- `test_elk_api_bottom_to_cache_top`: assert `api→cache` source is BOTTOM of `api`,
  destination is TOP of `cache`.
- `test_elk_source_tangent_agrees_with_declared_side`: for each of the four edges, assert
  the first route segment direction agrees with the declared source side (e.g., RIGHT →
  the x component of the first tangent is positive).
- `test_elk_destination_tangent_agrees_with_declared_side`: last route segment direction
  agrees with declared destination side.

**Approach:**
- Verify the existing ELK serializer sends declared port-side constraints to ELK (e.g.,
  as port `side` properties). If not, add them.
- After ELK deserialization, assert the `PortLayout` contains the declared sides (add
  `declared_source_side` and `declared_destination_side` fields if not already present).
- Compute tangents from the first/last route segment and compare with the declared side.

---

### Task 3: Architecture fallback — replace PortSide.AUTO
Depends on: none
Verification: TDD

**Tests:**
- `test_fallback_no_auto_ports`: render `architecture-complex` with ELK disabled; assert
  no `PortLayout` in the result has `side == PortSide.AUTO`.
- `test_fallback_preserves_declared_lb_right`: in the fallback result, `lb→api` source
  endpoint is on the RIGHT side of `lb`.
- `test_fallback_preserves_declared_api_bottom`: `api→cache` source endpoint is on the
  BOTTOM side of `api`.
- `test_fallback_typed_error_on_unhonorable_constraint`: mock a scenario where the
  declared side cannot be honored (e.g., conflicting port placement); assert a typed
  `ArchitectureLayoutError` is raised rather than silent AUTO substitution.

**Approach:**
- Locate the Python fallback architecture router in `_strategies.py` or
  `_compound_layout.py`.
- Replace `PortSide.AUTO` construction with: copy declared source/destination sides from
  the `_Edge`; compute endpoint positions from the declared side of the visible service
  boundary; set endpoint directions to point outward from source and inward toward
  destination.
- Add `ArchitectureLayoutError(edge_id, declared_side, reason)` to `_geometry.py`.
- Raise it when the fallback cannot honor a constraint rather than substituting AUTO.

---

### Task 4: Architecture validation assertions
Depends on: Task 1, Task 3
Verification: TDD

**Tests:**
- `test_all_five_services_exist`: services `lb`, `api`, `db`, `cache`, `queue` present.
- `test_all_services_inside_cloud_platform`: all five service bounds are contained by the
  Cloud Platform group bounds.
- `test_cloud_platform_title_band_clear`: no edge segment crosses the Cloud Platform title
  band.
- `test_no_edge_crosses_service_interior`: no route segment crosses any service interior.
- `test_stable_edge_ids`: all four edge IDs are non-empty strings unique across relations.
- `test_provenance_from_layout_metadata`: `provenance.layout_backend` and
  `provenance.fallback_reason` are derived from `LayoutMetadata`, not from output format.

**Approach:**
- Add these assertions to `tests/test_architecture_conformance.py` (or the new
  integration test file) using the existing geometry validation helpers.
- Reuse `_segment_intersects_rect` from Task 4 of item 1 for title-band and service-
  interior checks.

---

### Task 5: Faithful mode guard
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_faithful_no_synchronous_legend`: `to_html(faithful_mermaid=True)` for
  `architecture-complex` contains no "synchronous" legend element.
- `test_faithful_no_service_boundary_legend`: same output contains no service-boundary
  legend element.
- `test_faithful_no_inferred_semantics`: output does not annotate edges with business
  semantics beyond what the architecture source declares.

**Approach:**
- Audit the architecture HTML/SVG painter for any legend injection.
- Gate legend rendering on `faithful_mermaid=False` only.
- Add assertions to the canonical runner for both faithful and editorial variants.
