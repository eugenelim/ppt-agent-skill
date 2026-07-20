# Spec: Mermaid Renderer Correctness

- **Status:** Shipped <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Mode:** full (risk triggers: multi-feature; structural change to layout pipeline; behavioral change to edge-routing contract)
- **Constrained by:** [`mermaid-renderer-uplift`](../mermaid-renderer-uplift/spec.md) — boundary: HTML/CSS div + SVG overlay architecture is permanent; no new pip deps without sign-off; `_dispatch` signature is stable
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The renderer's 68/71 success rate substantially overstates correctness: several "green" renders have lost most source semantics or contain broken geometry (paths outside canvas, disconnected segments, wrong markers). This spec tracks the correctness repairs — from the immediate dummy-chain routing bug fix through the full set of semantic, geometric, and diagram-type gaps identified in a systematic inspection pass documented in `.context/attachments/TJTeD1/pasted_text_2026-07-20_03-58-23.txt` (hereafter "the inspection report").

Work is split into four phases:
- **Phase 0 (DONE):** Dummy-chain routing bug — long edges were emitting multiple disconnected SVG paths, some off-canvas.
- **Phase 1:** Geometric correctness — canvas bounds, shape boundary intersections, self-loop routing, ER marker parsing.
- **Phase 2:** Semantic correctness — class diagram marker endpoints, text measurement, compound/nested layout.
- **Phase 3:** Typed adapters — Sankey, C4, ZenUML, Journey, GitGraph, Requirement (eliminate false-positive green renders).

## Boundaries

### Always do
- Keep the HTML/CSS `<div>` + absolutely-positioned SVG overlay architecture — no format migration.
- Write the failing test first for every new AC (red → green → refactor).
- Preserve `_Node`, `_Edge`, `_Group` dataclass field names (public contract).
- Preserve `_dispatch(src, direction_override, width_hint, height_hint, style_overrides)` signature.
- Place new fixtures in `tests/fixtures/<name>.mmd`; no inline fixture strings in test files.

### Ask first
- Adding a pip dependency (even a small pure-Python one).
- Changing the `_dispatch` return type or public re-exports from `mermaid_render/__init__.py`.
- Introducing a new top-level module outside `scripts/mermaid_render/`.

### Never do
- Return a "green" (non-error) result for a diagram type that is semantically unrenderable — return explicit unsupported instead.
- Add attribution or external-source references in code comments, docstrings, or commit messages.
- Emit duplicate `<marker>` IDs within a single SVG.

## Snapshot failures: diagnosis (pre-existing at start of this spec)

63 snapshot tests fail in `test_snapshots.py` as of branch `eugene/mermaid-render-bug-fixes`. These are **all pre-existing** (none caused by the Phase 0 dummy-chain fix). They fall into two buckets:

**Bucket A — stale baselines (no semantic defect, just a baseline drift after renderer improvements):**
Most failures are in diagram types where the renderer changed after baselines were captured. Recapturing baselines on the reference machine resolves these mechanically. Affected fixtures (full list, both light + dark variants):

- `architecture-basic`, `architecture-complex`
- `c4-basic`
- `er-basic`, `er-cardinality-all`, `er-ecommerce`, `er-identifying`
- `flowchart-all-shapes`, `flowchart-deep-nesting`, `flowchart-diamond-branch`, `flowchart-diamond-clipping`, `flowchart-empty-subgraph`, `flowchart-groups-complex`, `flowchart-shapes-new`
- `gantt-basic`
- `packet-basic`, `pie-basic`, `quadrant-basic`
- `sequence-activation`, `sequence-all-arrowtypes`, `sequence-basic`, `sequence-blocks`, `sequence-complex`, `sequence-note`, `sequence-notes-all`, `sequence-self-message`
- `statediagram-basic` (dark only)
- `timeline-basic`, `timeline-multiperiod`
- `xychart-mixed`

Note: flowchart fixtures drifted because Phase 0 routing changes shifted edge path coordinates (new paths vs. A*-routed paths).

**Bucket B — visual defects in the rendering (not just stale baselines):**
Some failures reflect real rendering bugs identified in the inspection report. These must be *fixed* before baselines are recaptured, otherwise the baseline would encode broken geometry:
- `sequence-notes-all`: notes extend to x ≈ −116 and x ≈ 748 while canvas is ≈ 608 (canvas bounds pass, Phase 1 AC-1.3).
- `statediagram-complex`: `Processing` state appears as both compound boundary and a separate atomic node (nested state compound layout, Phase 2 AC-2.4).
- `statediagram-nested`: external transitions attach to duplicate atomic node rather than compound boundary.

**Resolution plan:** Fix Bucket B defects in Phase 1/Phase 2 first, then recapture all 63 baselines in one batch. Do **not** recapture before the defects are fixed.

## Testing Strategy

**TDD — HTML/SVG property assertions (primary):** Every AC has a failing test before any implementation. Tests live in `tests/test_syntax_flowchart.py`, `tests/test_fix_state.py`, `tests/test_fix_sequence.py`, `tests/test_fix_er.py`, `tests/test_fix_class.py`, or a new file `tests/test_render_correctness.py` for Phase 1–3 items that don't fit existing files.

**Snapshot regression guard (secondary):** After all Phase 1 fixes are complete and Phase 2 is in progress, recapture the 63 stale baselines. Subsequent work uses snapshot diffs to catch regressions.

**Geometric invariants (continuous):** After Phase 0 is done, add a parametric invariant test: for every fixture in `tests/fixtures/`, every rendered edge must produce exactly 1 SVG path and that path must stay within canvas bounds (± 5px tolerance).

## Acceptance Criteria

### Phase 0 — DONE

- [x] **AC-0.1** `_assign_ranks` inserts dummy nodes for multi-rank edges; the edge label travels on the **last** segment (dummy → real dst), not the first. Verified: `test_fix_state.py::TestTransitionLabels::test_complex_fixture_labels` passes.
- [x] **AC-0.2** `_route_edges` skips intermediate dummy-chain segments as independent paths; the last-segment route uses `orig_src` as the physical start point, producing exactly one continuous SVG path per logical edge. Verified: `TestDummyChainRouting` (4 tests) passes.
- [x] **AC-0.3** Fan-in/fan-out port spreading uses real (`orig_src`/`orig_dst`) endpoints for deduplication, not dummy-chain node IDs.
- [x] **AC-0.4** Skip-rank forward edges in TB layout (rank_gap > 1) are routed via a right-side lane (`right_lane_x + 8 * lane_index`) instead of A*, preventing visual boundary-touching on intermediate-rank nodes. Verified: `TestDummyChainRouting::test_long_edge_path_stays_within_canvas` passes.

### Phase 1 — Geometric correctness

- [x] **AC-1.1** `TestGeometricInvariants::test_no_duplicate_src_dst_pairs` — no `(src, dst)` pair appears more than twice across all fixture-rendered annotated paths (catches dummy-chain regression). Also fixed: back-edge lane step reduced 32→12px so `statediagram-complex` stays within canvas.
- [x] **AC-1.2** `TestGeometricInvariants::test_paths_within_canvas` — parametric canvas bounds check across all edge-producing fixtures. 64 parametric tests added to `tests/test_render_correctness.py`.
- [x] **AC-1.3** Sequence diagram note canvas bounds: a pre-pass in `_strategies.py` computes min/max x across all note polygons, shifts all participant x positions right if any note extends to negative x, and expands `canvas_w` if any note extends past the right edge. All note polygons in `sequence-notes-all` now within `[0, canvas_w]`. Updated `TestNotePositioning` thresholds to use relative (canvas-fraction) bounds.
- [x] **AC-1.4** ER diagrams: the relationship label parser strips surrounding quotes. `"places"` in source text emits `places` (no quote chars) in the rendered label. Verified: `TestERLabelQuotes` (2 tests in `test_render_correctness.py`). Fix: `_strategies.py` line 755 `lbl = m.group("lbl").strip().strip('"')`.
- [x] **AC-1.5** Self-loop edges (`A --> A`) route via a rectangular orthogonal loop (4-waypoint `_smooth_orthogonal_path`) exiting/returning the right face at distinct y offsets. Replaced cubic-bezier self-loop. Loop stays within canvas. Verified: `TestSelfLoopRouting` (4 tests).

### Phase 2 — Semantic correctness

- [x] **AC-2.1** Class diagram relation parser: `A <|-- B` places the hollow-triangle marker at `A` (the superclass), not at `B`. Verified by `TestClassMarkerEndpoints`.
- [x] **AC-2.2** Class diagram multiplicities: `A "1" -- "0..*" B` stores `sourceMultiplicity` and `targetMultiplicity` as separate fields and positions each label near its respective endpoint. Verified: `TestClassMultiplicities`.
- [x] **AC-2.3** ER cardinality markers are composed from primitives: bar, circle, crowfoot. `||..||` → two-bar at both ends; `o{..}|` → circle+crowfoot at source, bar+crowfoot at target. Verified: `TestERCardinalityMarkers`.
- [x] **AC-2.4** Nested state diagrams (`stateDiagram-v2` with `state Processing { ... }`): the composite state renders as a compound bounding box only (no duplicate atomic node). External transitions attach to the compound boundary, not a separate node. Verified: `TestNestedStateCompound`.
- [x] **AC-2.5** Node dimensions are computed from text content rather than a fixed 192px width. A node labeled `A` is narrower than one labeled `ABCDEFGHIJKLMNOPQRSTUVWXYZ`. Both remain at least `NODE_MIN_W` wide. Verified: `TestNodeTextSizing`.

### Phase 3 — Typed adapters (eliminate false-positive green renders)

- [x] **AC-3.1** `sankey-basic` fixture returns an explicit unsupported result OR renders Sankey ribbons with proportional widths and source-to-target conservation. It does **not** render generic boxes. Verified: `TestSankeyRenderer`.
- [x] **AC-3.2** `c4-*` fixtures preserve `elementType` (`person`, `system`, `external_system`), `description`, and render `person` elements with a person-silhouette shape (not a flattened ellipse). Verified: `TestC4SemanticFields`.
- [x] **AC-3.3** `zenuml-basic` fixture returns an explicit unsupported result rather than rendering arbitrary tokens as unrelated boxes. Verified: `TestZenUMLUnsupported`.
- [x] **AC-3.4** `journey-basic` returns an explicit unsupported result (or renders a timeline with task cards). Currently the renderer already returns unsupported for journey; this AC ensures that is by design and not a parser crash.
- [x] **AC-3.5** `gitgraph-basic` fixture: the lowercase `gitgraph` detector is fixed to recognise the fixture header. Currently both sides fail due to a case-sensitivity bug.

## Assumptions

- Python 3.13 runtime (`python3 -c "import sys; print(sys.version)"` → `3.13.x`).
- Test runner: `pytest` from `requirements.txt`, no new test dependencies needed.
- Snapshot baselines are machine-authoritative (committed by eugenelim on his Mac); CI skips snapshot tests when `SNAPSHOT_BASELINE_PLATFORM` does not match.
- Sankey AC-3.1: implementing a full Sankey renderer is Phase 3 work; returning `unsupported` is an acceptable interim for AC-3.1 if the ribbon renderer is not yet implemented.
