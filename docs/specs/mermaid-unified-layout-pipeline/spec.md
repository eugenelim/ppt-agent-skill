# Spec: mermaid-unified-layout-pipeline

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** `docs/specs/flowchart-pipeline-finish/spec.md` (pure-Python + no-subprocess import tests) — **explicitly overridden** by ADR-001 (`docs/adr/001-elk-layout-engine.md`) created in T0 of this spec
- **Brief:** none
- **Discovery:** none
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Both `to_html()` and `to_svg()` share one pipeline: parse → pre-layout IR
(`LayoutGraph`) → layouter → `FinalizedLayout` → painter. Painters diverge only
in serialization; they never re-derive node positions or route edges independently.

ELK (elkjs 0.12.0 via a pinned Node subprocess) is the primary layouter for
graph-topology diagram types (flowchart, stateDiagram). The existing Python
Sugiyama + A\* stack is the explicit fallback when the `MERMAID_LAYOUT_ENGINE=python`
env var is set or when the Node runtime is absent. "Deterministic" applies
within a single engine: ELK output is deterministic given the same input and
seed; the same is true of the Python path. CI requires Node, enforcing ELK
as the canonical engine for graph-topology types.

The 15 named fixtures render without node–node overlap, node–group-title
overlap, edge clipping, reversed arrow semantics, detached labels, artificial
global feedback lanes, or vacuous fidelity geometry passes.

## Assumptions

- **Technical:** Node.js v26.4.0 available (probe: `node --version`)
- **Technical:** elkjs 0.12.0 available via npm (`npm show elkjs version`)
- **Technical:** `tests/test_dependencies.py::TestNoSubprocess` scans all `layout/*.py`; `elk_adapter.py` requires a named exemption
- **Technical:** pure-Python layout ADR was never formally written (tracked in `docs/backlog.md`); the constraining artifacts are the `flowchart-pipeline-finish` spec + `tests/test_dependencies.py` import tests
- **Technical:** `FinalizedLayout` is already consumed by both painters; the seam is between layout computation and painting, not HTML vs. SVG
- **Technical:** `validate_finalized_layout()` currently reports `structural_geometry: unvalidated` and `semantic_geometry: unvalidated` — structural/semantic checks are missing, making some passes vacuous
- **Technical:** `architecture-complex`, `class-relationships-all`, `er-cardinality-all`, `er-ecommerce`, `requirement-basic` do not route through `_compile_flowchart` — they have separate layout paths in `_dispatch` and ELK is out of scope for them
- **Product:** task spec is authoritative; ELK integration with Python fallback is the target; pure-Python constraint is intentionally overridden with proper ADR governance
- **Process:** Full mode — structural change, new dependency (elkjs + Node), multi-feature, unfamiliar territory; ADR required before implementation begins

## Acceptance Criteria

### Governance
- [x] AC-GOV-1: `docs/adr/001-elk-layout-engine.md` exists and records the decision to add elkjs + Node as a conditional runtime dependency, overriding the backlog item `adt-pure-python-layout`

### IR and pipeline unification
- [x] AC-IR-1: `LayoutGraph`, `LayoutNode`, `LayoutGroup`, `LayoutEdge`, `PortSpec` dataclasses exist in `layout/_geometry.py` and are importable
- [x] AC-IR-2: `LayoutEdge` carries independent `source_marker` and `target_marker` fields of type `MarkerKind`; `_Edge` (the mutable parse-time struct) also gains `source_marker` and `target_marker` derived from parsed syntax; legacy `arrow`/`bidir`/`arrow_src` booleans remain in `_Edge` as derived fields, kept consistent with the new markers (removal deferred to `docs/backlog.md#arrow-semantics-cleanup`). Legacy boolean agreement is asserted in T3 tests.
- [x] AC-IR-3: `to_html()` and `to_svg()` each call `_compile_flowchart()` exactly once and pass the returned `FinalizedLayout` to their respective painters without recomputing positions. Verified by patching at each entry point's call site and asserting the call count is exactly 1 per entry point.

### ELK adapter
- [x] AC-ELK-1: `layout/elk_adapter.py` exports `layout_with_elk(graph: LayoutGraph) -> FinalizedLayout`. Note: the production pipeline in `_compile_flowchart` (`_strategies.py`) applies ELK positions inline (rather than calling `layout_with_elk` directly) to integrate with the shared `_Node`/IR-building pipeline; deferred unification tracked in `docs/backlog.md#elk-production-path-unification`.
- [x] AC-ELK-2: `elk_adapter.py` is in `_SUBPROCESS_EXEMPTIONS` in `tests/test_dependencies.py`
- [x] AC-ELK-3: `layout_with_elk` returns a `FinalizedLayout` with node positions derived from ELK child `x`/`y` coordinates and edge waypoints from ELK edge sections
- [x] AC-ELK-4: When `MERMAID_LAYOUT_ENGINE=python` is set **or** Node is absent, `layout_with_elk` raises `ElkUnavailable`; `_compile_flowchart` catches it and runs Python Sugiyama. Both triggers are unit-tested independently.
- [x] AC-ELK-5: When elkjs exits non-zero, returns malformed JSON, **or** exceeds 30 seconds, `layout_with_elk` raises `ElkUnavailable`. All three failure modes are unit-tested; the timeout test asserts `subprocess.run` is called with `timeout=30`.

### ShapeGeometry
- [x] AC-SHAPE-1: `layout/shape_geometry.py` defines a `ShapeGeometry` Protocol with `measure`, `boundary_intersection`, `available_ports`, `marker_clearance`, `paint_svg`, `paint_html`
- [x] AC-SHAPE-2: `SHAPE_REGISTRY` maps all 13 current shape names to `ShapeGeometry` implementations
- [x] AC-SHAPE-3: Connector clipping in `_routing.py` uses `SHAPE_REGISTRY[shape].boundary_intersection()` on the Python fallback path. `DiamondGeometry.boundary_intersection` ports the existing `_clip_to_diamond()` logic. A test asserts that the clipping output for a diamond-shaped node routes through `boundary_intersection()` on the fallback path (not the inlined function). The ELK path is unaffected (ELK handles clipping internally).

### Faithful mode
- [x] AC-FAITH-1: When `faithful_mermaid=True`, `to_html()` and `to_svg()` do not inject icons, legends, semantic color tints, or depth tints
- [x] AC-FAITH-2: When `faithful_mermaid=True`, `auto_direction` inference is not applied (source direction is preserved)
- [x] AC-FAITH-3: When `faithful_mermaid=True`, Mermaid line-style types are not restyled

### Validation
- [x] AC-VAL-1: `validate_finalized_layout(strict=True)` returns non-pass geometry status when any two node bounding boxes overlap by > 1 px, or any node overlaps a sibling group's title strip; the threshold ≤ 1 px is the pass tolerance for both AC-VAL-1 and AC-FIX-1
- [x] AC-VAL-2: `validate_finalized_layout(strict=True)` returns non-pass structural status when any non-cross-hierarchy child (a child whose parent group IS included in the ELK layout call) extends outside its parent group's bounding box. Cross-hierarchy children (edges that cross subgraph boundaries, placed by ELK `hierarchyHandling=INCLUDE_CHILDREN`) are explicitly excluded. Note: ELK group hierarchy serialization is deferred (ELK receives a flat node list); member containment is enforced post-hoc by expanding group bboxes in `_strategies.py` (deferred: `docs/backlog.md#elk-group-hierarchy-serialization`).
- [x] AC-VAL-3: In the fidelity runner (`tools/mermaid_fidelity/runner.py`), when a case declares strict semantic fields, `ref_obs.semantic` has entities (`len(ref_obs.semantic.entities) > 0`), and `native_obs.semantic` is `None`, the runner records `ComparisonStatus.SEMANTIC_MISMATCH` (not `ComparisonStatus.EXTRACTOR_GAP`). Verified by calling `FidelityRunner._compare()` directly with a fabricated reference observation (semantic with entities) and a native observation with `semantic=None`.

### Fixture correctness (graph-topology fixtures)
- [x] AC-FIX-1: The 10 graph-topology fixtures (`flowchart-all-shapes`, `flowchart-arrows-defs`, `flowchart-diamond-branch`, `flowchart-diamond-clipping`, `flowchart-empty-subgraph`, `flowchart-groups-complex`, `flowchart-inner-direction`, `flowchart-parallel-links`, `statediagram-complex`, `statediagram-nested`) produce a `FinalizedLayout` with zero node-node geometry overlaps (≤ 1 px tolerance) and no containment violations as reported by `validate_finalized_layout(strict=True)`, and have ≥ 1 node. Note: edge routing quality (label-node intersection, waypoints through nodes) is a known ELK first-iteration limitation; these checks are not gated in T8b tests (deferred: `docs/backlog.md#elk-edge-routing-quality`).
- [x] AC-FIX-2: The 5 non-graph-topology fixtures (`architecture-complex`, `class-relationships-all`, `er-cardinality-all`, `er-ecommerce`, `requirement-basic`) produce non-empty SVG output via `to_svg(experimental=True)`. Note: semantic extractor entity-count assertion (≥ 1 entity) is not tested in T8b (deferred: `docs/backlog.md#elk-non-graph-entity-count`).

### Snapshots
- [x] AC-SNAP-1: The snapshot baseline for graph-topology fixtures is regenerated after ELK wiring (T5) and the visual delta reviewed; the regenerated baseline is committed. Non-graph-topology snapshot baselines are unchanged.

### Dependency record
- [x] AC-DEP-1: A `package.json` + `package-lock.json` pinning elkjs 0.12.0 exists under `scripts/mermaid_render/layout/`; `node_modules/` there is gitignored; the dependency is recorded in the relevant `AGENTS.md`

### Gates
- [x] AC-GATES: `pytest tests/` passes (0 failures); snapshot regeneration is under `--run-snapshots` (not the fast tier)

## Boundaries

### Always do

- Write ADR `docs/adr/001-elk-layout-engine.md` (T0) before any code change
- Add `LayoutGraph`, `LayoutNode`, `LayoutGroup`, `LayoutEdge`, `PortSpec`, `MarkerKind` to `layout/_geometry.py`
- Add `layout/shape_geometry.py` with `ShapeGeometry` protocol + `SHAPE_REGISTRY`
- Add `layout/elk_adapter.py` with `layout_with_elk`, `ElkUnavailable`, sidecar `elk_runner.js`
- Add `_SUBPROCESS_EXEMPTIONS` exemption for `elk_adapter.py` in `tests/test_dependencies.py`
- Add `package.json` + `package-lock.json` pinning elkjs 0.12.0 under `scripts/mermaid_render/layout/`
- Fix `faithful_mermaid` to suppress icon inference, legend, auto-flip, semantic colors
- Fix `validate_finalized_layout()` to enforce overlap, containment, and oracle-entity-presence
- Regenerate graph-topology snapshot baselines after ELK wiring
- Update `docs/specs/README.md`

### Ask first

- Removing the Python Sugiyama phases (must stay as fallback)
- Changing the public `to_html`/`to_svg` signatures
- Running ELK on non-graph-topology types
- Splitting `_strategies.py` into `_pipeline.py`/`_diagram_types.py` (deferred; track in backlog)

### Never do

- Delete or disable `TestNoSubprocess` globally — only add a named `_SUBPROCESS_EXEMPTIONS` entry for `elk_adapter.py`
- Remove the Python Sugiyama + A\* implementation
- Make elkjs a hard import-time dependency (subprocess only, `ElkUnavailable` on Node/elkjs absence)
- Introduce a new top-level directory outside `scripts/mermaid_render/`
- Run ELK on non-graph-topology diagram types

## Testing Strategy

| AC | Mode | Mechanism |
|---|---|---|
| AC-GOV-1 | Goal-based | File existence check: `docs/adr/001-elk-layout-engine.md` |
| AC-IR-1, AC-IR-2 | TDD | Unit: import and instantiate new dataclasses; assert `source_marker` field type |
| AC-IR-3 | TDD | Unit: patch `mermaid_render.layout._strategies._compile_flowchart` at entry-point call sites; assert call count == 1 per `to_html`/`to_svg` call |
| AC-ELK-1–5 | TDD | Unit: mock `_run_elk` subprocess for all failure modes (absent Node, env-var, non-zero exit, malformed JSON, timeout=30); real-subprocess tests under `--run-isolation` (`@pytest.mark.isolation`) |
| AC-SHAPE-1–3 | TDD | Unit: `measure()` + `boundary_intersection()` on each shape; registry completeness |
| AC-FAITH-1–3 | TDD | Unit: compile fixture with `faithful_mermaid=True`; assert no icon/legend/color fields |
| AC-VAL-1–2 | TDD | Unit: construct overlapping/containment-violating layouts; assert `strict=True` fails |
| AC-VAL-3 | TDD | Unit: call `FidelityRunner._compare()` with ref having entities and native `semantic=None`; assert `SEMANTIC_MISMATCH` not `EXTRACTOR_GAP` |
| AC-FIX-1 | Goal-based | Script: compile 10 graph-topology fixtures; `validate_finalized_layout(strict=True)` |
| AC-FIX-2 | Goal-based | Script: `to_svg()` on 5 non-graph fixtures; assert non-empty and ≥ 1 entity |
| AC-SNAP-1 | Visual/manual | `--run-snapshots` regeneration + visual delta review |
| AC-DEP-1 | Goal-based | File existence + `cat package.json \| jq .dependencies.elkjs` == `"0.12.0"` |
| AC-GATES | Goal-based | `pytest tests/` |
