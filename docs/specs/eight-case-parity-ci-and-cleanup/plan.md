# Implementation Plan — Eight-Case Parity CI and Cleanup

**Status:** Approved

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `.github/workflows/` or `Makefile` (CI matrix job); `AGENTS.md`
   (documented command); `scripts/mermaid_render/layout/sequence.py` (delete);
   `scripts/mermaid_render/native_svg.py` (remove legacy delegation); `_strategies.py` or
   split modules (remove obsolete code paths); `tests/` (replace or delete stale tests);
   `docs/architecture/mermaid_renderer.md` (update).
2. Done when: the CI matrix job runs all eight fixtures across the full
   output/presentation/backend matrix; every hard failure condition listed in the spec
   causes a CI failure; all obsolete code paths are deleted; documentation is updated;
   repeated runs are deterministic.
3. Not changing: public renderer API; fixture `.mmd` files; any shipped behavior from
   items 1–5.

**Declined patterns:**
- Tempted to run cleanup before all hard CI conditions are green; declining — spec
  requires cleanup only after the CI matrix passes.
- Tempted to delete `layout/sequence.py` in this item; declining — it is already deleted
  in item 2; this item just verifies it.
- Tempted to add a raster-similarity hard gate; declining — spec explicitly says raster
  similarity is diagnostic only.

---

## Tasks

### Task 1: CI matrix job
Depends on: none
Verification: Goal-based check

**Done when:** a CI job (GitHub Actions step or Makefile target `eight-case-ci`) runs the
full matrix and is documented in `AGENTS.md`; the job fails on any lane error.

**Approach:**
- Add a GitHub Actions job `eight-case-parity` that installs dependencies (including
  elkjs via `npm ci`) and runs `pytest -m eight_case --timeout=120`.
- The job matrix includes: all 8 fixtures, `to_html`/`to_svg`, `faithful`/`editorial`,
  ELK-required/fallback (for arch/flowchart), canonical-sequence (for sequence).
- Publish structured artifacts via `actions/upload-artifact` after the run.
- Document `make eight-case-ci` (or `pytest -m eight_case`) in `AGENTS.md`.

---

### Task 2: Hard failure condition tests
Depends on: none
Verification: TDD

**Tests (one per condition listed in spec):**
- `test_ci_fails_on_hidden_backend_fallback`
- `test_ci_fails_on_missing_backend_provenance`
- `test_ci_fails_on_route_waypoint_outside_canvas`
- `test_ci_fails_on_route_segment_outside_canvas`
- `test_ci_fails_on_segment_crossing_unrelated_node`
- `test_ci_fails_on_segment_crossing_unrelated_group`
- `test_ci_fails_on_segment_crossing_title_band`
- `test_ci_fails_on_missing_compound_gate`
- `test_ci_fails_on_cross_scope_route_bypassing_gate`
- `test_ci_fails_on_missing_empty_group`
- `test_ci_fails_on_overlapping_sibling_groups`
- `test_ci_fails_on_incorrect_local_direction`
- `test_ci_fails_on_missing_sequence_box`
- `test_ci_fails_on_incorrect_box_membership`
- `test_ci_fails_on_missing_sequence_fragment`
- `test_ci_fails_on_incorrect_nested_fragment_parent`
- `test_ci_fails_on_missing_edge_style`
- `test_ci_fails_on_incorrect_architecture_port`
- `test_ci_fails_on_html_svg_geometry_divergence`
- `test_ci_fails_on_zero_check_pass`
- `test_ci_fails_on_nondeterministic_output`

**Approach:**
- Add `tests/test_eight_case_ci_gates.py` with one test per condition.
- Each test fabricates the minimal pathological scenario and asserts the canonical runner
  raises or returns FAIL.
- Tag all with `@pytest.mark.eight_case`.

---

### Task 3: Structured artifacts publisher
Depends on: Task 1
Verification: Goal-based check

**Done when:** after each fixture run, a JSON artifact is written to
`test-artifacts/<fixture>/<lane>.json` containing the fields listed in the spec.

**Approach:**
- Add `tools/mermaid_fidelity/eight_case_artifacts.py` with a `publish_fixture_artifact`
  function.
- Call it from the canonical runner after each fixture lane completes.
- Fields: fixture source hash, implementation git SHA, compiler metadata, layout metadata,
  normalized nodes/groups/boxes/fragments, normalized routes/messages, labels/markers,
  gates, validation result, assertion count, reference extraction result, HTML/SVG
  comparison artifact path.

---

### Task 4: Cleanup — delete obsolete code paths
Depends on: Task 1, Task 2
Verification: Goal-based check

**Done when:** `grep -rn` for the deleted symbols returns zero matches; all eight fixtures
still pass.

**Approach:**
- Delete `layout/sequence.py` (already done in item 2; verify and confirm deletion).
- Remove `native_svg._sequence_scene` legacy delegation (already done in item 2; verify).
- Remove obsolete sequence skip behavior for boxes and fragments.
- Remove the unconditional inner-direction Python fallback (already done in item 3; verify).
- Remove post-global-placement group correction, sibling-group pushing, bbox recomputation
  (already done in item 3; verify).
- Remove fallback architecture `PortSide.AUTO` construction (already done in item 5; verify).
- For each deletion, run the CI matrix to confirm no regressions.

---

### Task 5: Replace stale tests
Depends on: Task 4
Verification: Goal-based check

**Done when:** `grep -rn "pytest.mark.skip\|skipIf" tests/` returns zero matches related
to the obsolete conditions; no test asserts only waypoints or claims to validate the
native SVG sequence path.

**Approach:**
- Identify tests that skip when an expected empty group is absent → replace skip with
  `assert False, "empty group must exist"`.
- Identify tests that assert post-layout shuffling behavior → delete (behavior is removed).
- Identify tests that validate only waypoints → update to validate segments.
- Identify tests that call `to_html` but assert native SVG path → delete or redirect to
  the shared compiler.

---

### Task 6: Architecture documentation update
Depends on: Task 4
Verification: Goal-based check

**Done when:** `docs/architecture/mermaid_renderer.md` describes all required topics and
a reviewer can understand the pipeline without reading source code.

**Approach:**
- Update `docs/architecture/mermaid_renderer.md` to cover:
  - Actual shared and non-shared pipelines (which compilers are shared, which are not).
  - Sequence canonical geometry (single parser, single geometry compiler).
  - ELK and fallback behavior and typed fallback conditions.
  - Recursive compound layout (bottom-up, measured proxies).
  - Boundary gates (creation, waypoint insertion, gate validation).
  - Backend provenance (five fields and how they are populated).
  - Validation invariants (canvas bounds, segment intersection, compound gate checks).
