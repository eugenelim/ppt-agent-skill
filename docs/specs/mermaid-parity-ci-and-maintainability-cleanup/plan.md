# Implementation Plan — Parity CI and Maintainability Cleanup

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: CI configuration (new/updated workflow YAML or Makefile targets); `scripts/mermaid_render/layout/_strategies.py` → five new focused modules; `tests/test_parity_ci.py` (new: import-boundary and dead-code checks); `docs/architecture/mermaid_renderer.md` (update); `tools/mermaid_fidelity/` (publish artifacts).
2. Done when: `pytest tests/ -m "parity"` runs in under 60s on a standard CI worker; `grep -rn "_compile_er_legacy\|OracleStatus.*=.*Enum" tools/ tests/` returns zero matches; `_strategies.py` has been reduced to a re-export shim or deleted; all public renderer imports succeed.
3. Not changing: public renderer API signatures; fixture `.mmd` files; the oracle contract, text measurer, shape geometry, compound layout, or any upstream dependency from items 1–12.

**Declined patterns:**
- Tempted to merge the fast job and the browser job into one; declining — the spec requires a browser-free fast job and a separate pinned browser job.
- Tempted to split `_strategies.py` before CI gates are green; declining — the spec explicitly requires CI gates to be green first.
- Tempted to remove public API symbols without a deprecation warning; declining — the spec requires backward compatibility for at least one release cycle.

---

## Tasks

### Task 1: Fast per-PR CI job (browser-free)
Depends on: none
Verification: Goal-based check

**Done when:** `make parity-fast` (or `pytest tests/ -m parity_fast`) completes in under 60 seconds; the CI YAML file runs it on every PR.

**Approach:**
- Add a `@pytest.mark.parity_fast` mark to all parity checks that do not require a browser.
- Create a `Makefile` target or CI job step: `pytest tests/ -m parity_fast --timeout=60`.
- Document the command in `AGENTS.md` under a "Parity checks" section.
- The fast job must cover: parser tests, semantic counts, `FinalizedLayout` validation, deterministic compilation, HTML/SVG geometry identity, node overlap, containment, boundary-endpoint, route-obstacle, marker/cardinality, backend metadata.

---

### Task 2: Pinned browser integration job
Depends on: none
Verification: Goal-based check

**Done when:** a CI YAML step exists that runs the pinned browser suite; `pytest tests/ -m browser --workers=1` is the command; `pytest-xdist` is not used in parallel mode for snapshot/browser tests.

**Approach:**
- Add a CI job that installs the pinned Playwright/Chromium, then runs `pytest tests/ -m browser --workers=1`.
- The `--workers=1` flag prevents unsafe parallel worker mode for snapshot/browser tests.
- Published artifacts: structured native geometry, structured reference geometry, oracle JSON, provenance JSON, failing fixture source, normalized SVGs.
- Raster similarity output as a diagnostic artifact, not a gate.

---

### Task 3: CI failure conditions as explicit gates
Depends on: Task 1
Verification: TDD

**Tests:**
- `test_zero_check_pass_blocked`: assert a PASS result with zero checks causes the fast job to fail.
- `test_hidden_fallback_blocked`: compile a diagram; mock `metadata.backend = None`; assert the parity check raises.
- `test_node_overlap_blocked`: introduce an overlap in a `FinalizedLayout`; assert the parity check raises.
- `test_html_svg_geometry_divergence_blocked`: make HTML and SVG receive different `FinalizedLayout` instances; assert the parity check raises.
- `test_nondeterministic_output_blocked`: produce two different normalized geometry records for the same source; assert the parity check raises.

**Approach:**
- Add `tests/test_parity_gates.py` with one test per CI failure condition.
- Each test constructs the pathological scenario and asserts the gate raises or returns a failure status.
- These tests are tagged `@pytest.mark.parity_fast` so they run in the fast job.

---

### Task 4: Differential tests (pre/post rearchitecture)
Depends on: none
Verification: Goal-based check

**Done when:** `pytest tests/ -m differential` produces a comparison report showing which fixtures differ from the pre-rearchitecture golden SVGs and why; any semantic regression (not just visual) causes `FAIL`.

**Approach:**
- Locate or regenerate the pre-rearchitecture golden SVGs from the checked-out SHA (do not use previously generated artifacts).
- Add `tests/test_differential_parity.py` that compiles each in-scope fixture through `to_svg()` and diffs the normalized output against the golden.
- Differences in semantic topology (nodes, edges, labels) → `FAIL`; differences only in pixel coordinates → `diagnostic`.
- Tag with `@pytest.mark.differential`.

---

### Task 5: Import-boundary tests
Depends on: none
Verification: TDD

**Tests:**
- `test_renderer_does_not_import_layout`: parse `_renderer.py` with `ast`; assert no import of `_layout`, `_routing`, or `_strategies` from the layout package.
- `test_layout_does_not_import_renderer`: parse `_layout.py` and `_strategies.py`; assert no import of `_renderer`.
- `test_parser_does_not_choose_colors`: parse the flowchart/state parser modules; assert no import of color or style modules.
- `test_comparator_no_pass_without_checks`: assert that the oracle comparator functions cannot return `OracleStatus.PASS` with `len(checks) == 0`.

**Approach:**
- Add `tests/test_import_boundaries.py`.
- Use `ast.parse` + `ast.walk` to find `Import` and `ImportFrom` nodes in each target module.
- Assert forbidden import targets are absent.
- Tag with `@pytest.mark.parity_fast`.

---

### Task 6: Dead-code deletion
Depends on: all upstream items 1–12 being green
Verification: Goal-based check

**Done when:** `grep -rn "_compile_er_legacy\|_elk_routes_to_specs\|OracleStatus.*Enum" scripts/ tools/ tests/` returns zero matches; `pytest tests/` passes.

**Approach:**
- Delete (in order, verifying tests pass after each deletion):
  1. `_compile_er_legacy` (should already be deleted by item 10).
  2. `_elk_routes_to_specs` (should be removed from success path by item 9).
  3. Post-layout compound shuffling functions (`_group_separation`, `_push_members`, `_recompute_bboxes` in primary path).
  4. Broad `except Exception` fallback handlers (replace with typed `except (ElkUnavailable, ElkInvalidResult)`).
  5. Source/destination tuple identity maps (`{(src, dst): ...}` pattern).
  6. Raw string-length layout estimates (`len(text) * constant` in layout code).
  7. Duplicated `OracleStatus` enum definitions (should already be unified by item 1).
  8. Vacuous comparison branches (branches that return PASS with no checks).

---

### Task 7: `_strategies.py` split
Depends on: Task 6 and CI gates being green
Verification: Goal-based check

**Done when:** `_strategies.py` has been reduced to a re-export shim or deleted; focused modules (see approach) own each compilation system; `pytest tests/` passes.

**Approach:**
- Audit the current post-boston-v1 module layout: `_pipeline.py` and `_diagram_types.py` may already exist from the prior strategies-module-split iteration. Reconcile by extending existing modules rather than recreating them.
- Create or extend as needed: `_flowchart_compile.py`, `_sequence_compile.py`, `_compound_layout.py`, `_layout_fallback.py`, `_layout_validation.py`. Do not overwrite files that already contain related logic.
- Move remaining unrelated compilation systems out of `_strategies.py` to the appropriate module.
- Keep `_strategies.py` as a re-export shim for backward compatibility.
- Add a deprecation warning on import of `_strategies.py` after the split.
- Verify all existing `import` statements still work.

---

### Task 8: Documentation update
Depends on: Tasks 6, 7
Verification: Goal-based check

**Done when:** `docs/architecture/mermaid_renderer.md` exists and covers all nine topics listed in the spec; the file was updated in the same PR as the split.

**Approach:**
- Write or update `docs/architecture/mermaid_renderer.md` covering: semantic pipeline, layout graph, ELK and fallback rules, recursive compounds, text measurement, shape geometry, oracle statuses, faithful mode, CI reproduction.
- One section per topic; each section should be sufficient for a new contributor to understand where to look in the code.
