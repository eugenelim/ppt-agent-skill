# Spec: Mermaid Renderer Correctness

- **Status:** Implementing <!-- Draft | Approved | Implementing | Shipped | Archived -->
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

Work is split into four phases (0-3 complete) plus a Phase 4 upstream-sync + regression pass:

- **Phase 0 (DONE):** Dummy-chain routing bug — long edges were emitting multiple disconnected SVG paths, some off-canvas.
- **Phase 1 (DONE):** Geometric correctness — canvas bounds, shape boundary intersections, self-loop routing, ER marker parsing.
- **Phase 2 (DONE):** Semantic correctness — class diagram marker endpoints, text measurement, compound/nested layout.
- **Phase 3 (DONE):** Typed adapters — Sankey, C4, ZenUML, Journey, GitGraph, Requirement (eliminate false-positive green renders).
- **Phase 4:** Upstream-sync patches and text-fit regressions found via ours-vs-official comparison gallery (compare_gallery.py). Two universal issues identified in the gallery: (1) hard-coded 1280px canvas regardless of diagram content; (2) labels measured after coordinates are fixed, allowing browser wrapping to mutate node geometry post-layout.

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

### Phase 4 — Upstream-sync + text-fit regressions

These items were identified after Phase 0-3 landed, via a downstream-vendor fidelity spike and the ours-vs-official comparison gallery.

- [x] **AC-4.1** Browser teardown guard: `new_page()` in `scripts/mermaid_render/browser.py` wraps the `page.on("close", ...)` context-close callback in a try/except so Playwright async protocol errors during teardown are swallowed rather than raising noisy "Failed to find context" errors. Verified: goal-based (existing browser tests pass; no exception on `page.close()` after context is disposed).

- [x] **AC-4.2** English-only source: the 9 Chinese-language source comments across `scripts/mermaid_render/png.py` and `scripts/mermaid_render/svg.py` are translated to English. The downstream package ships English-only. Verified: `grep -r '[^\x00-\x7F]' scripts/mermaid_render/` returns no matches in `.py` files.

- [x] **AC-4.3** Vendor NOTICE: `scripts/mermaid_render/vendor/NOTICE` is added, attributing `dom-to-svg.bundle.js` to Felix Becker (MIT). Required by MIT redistribution terms. Verified: file exists and names project, copyright, and license URL.

- [ ] **AC-4.4** Node height for wrapped labels: `_node_render_h` in `_constants.py` uses the per-node width (`n.width if n.width > 0 else NODE_W`) rather than the global `NODE_W` when computing the `_wrap_label` budget. `_renderer.py`'s `_wbudget` is updated to match. Effect: nodes narrower than 192px (produced by Task 2.5 per-node width) now predict label wrapping accurately — node height no longer underestimates when the browser wraps. Verified: `TestNodeWrappedHeight` in `tests/test_render_correctness.py`; snapshot recapture.

- [ ] **AC-4.5** Edge label placement avoids destination node: fixing AC-4.4 corrects the node-obstacle heights used by `_best_label_pos`, which removes the dominant cause of edge labels overlapping the downstream node card. Verified: no `<text class="edge-label">` element whose bounding box overlaps its corresponding destination node's bbox in the `flowchart-tb-text-metrics` fixture. Verified: `TestEdgeLabelNoOverlap`.

- [ ] **AC-4.6** Dynamic canvas width: the rendered HTML viewport is set from the diagram's computed `canvas_w` (the value returned by `_dispatch`) rather than the hard-coded 1280px in `_strategies.py`'s `make_page()`. Narrow diagrams no longer have blank right margins; wide diagrams no longer clip. `make_page(fragment, theme, width)` accepts an optional `width` argument (default: current behaviour for backward compat). Verified: `TestDynamicCanvas` asserts that a 3-node linear chain's HTML `<html>` width attribute matches the expected narrow canvas width.

- [ ] **AC-4.7** Two-pass layout — height before y-assignment: `_assign_coordinates` performs node-height measurement (calling `_node_render_h`) AFTER per-node widths are set but BEFORE y-coordinate assignment, so rank-gap arithmetic uses the correct node heights. Current bug: y positions are set using `_node_render_h` called at rank_h computation (line 281 of `_layout.py`), but `n.width` is set at line 242 — the height call and the width set are already in the right order, so the latent bug is that `_node_render_h` used `NODE_W` instead of `n.width` (fixed by AC-4.4). AC-4.7 adds a regression-prevention test: a TB diagram with a multi-word narrow-node label has a RANK_GAP of at least `NODE_H + RANK_GAP` between the narrow node's bottom and the next rank. Verified: `TestTwoPassRankGap`.

### Phase 5 — Fixture-level regressions (from comparison gallery audit)

Findings from comparing all 71 fixtures against official mermaid.js via `compare_gallery.py`.
Ordered P0 first (blocks correctness of other diagrams), then by area type.

**P0 — Geometry contract (cross-cutting)**
- [x] **AC-5.1** Dynamic canvas width (same as AC-4.6 — listed here for cross-reference). All rendered HTML viewports use content-derived width, not hard-coded 1280px.
- [x] **AC-5.2** Two-pass node sizing (same as AC-4.4 / AC-4.7 — cross-reference). No browser CSS reflow after final layout; labels measured before coordinates are fixed.

**Shape rendering (flowchart-shapes-new)**
- [x] **AC-5.3** Stadium shape has a closed full-border outline on all four sides. Currently only the side segments are stroked; the left/right caps are missing the connecting border lines. Verified: `TestStadiumShape` asserts that the stadium SVG path/clip encloses all four sides.
- [x] **AC-5.4** Hexagon, trapezoid, and trapalt shapes have a visible closed-polygon border outline. Currently these shapes lack a visible stroke border. Verified: `TestPolygonShapeBorders`.
- [x] **AC-5.5** Double-circle node is not oversized. Currently computed as `max(NODE_W, NODE_H) + 8 = 200px`, which is much larger than the reference. Reduce to approximately `NODE_H + 24` or match the diameter of the inner ring plus border gap. Verified: `TestDoubleCircleSize` asserts height ≤ 80px.

**Gantt**
- [x] **AC-5.6** `gantt-after-multi` renders all months in the date axis with no gaps. Currently months 2024-01-08, 2024-01-09, 2024-01-10 (the window after both dependencies) are missing from the tick labels. Fix: ensure the date-axis tick generator covers the full span `[min_start, max_end]` inclusive. Verified: `TestGanttAfterMultiTicks` asserts tick labels cover all months in the fixture's date range.

**Kanban**
- [x] **AC-5.7** Kanban card IDs (`t1`, `t2`, etc.) are stripped from displayed label text. Currently `t1["Write unit tests"]` renders as `t1` or the raw id rather than just `Write unit tests`. Fix: the kanban parser must extract the bracketed label and discard the id prefix. Verified: `TestKanbanLabelExtraction`.
- [x] **AC-5.8** `kanban-metadata.mmd` (`@{ticket:..., priority:..., assigned:...}` syntax): document that current mmdc (installed version) does not support the `@{...}` metadata block syntax — this is an mmdc version issue, not a renderer bug. Our renderer should parse metadata gracefully and render cards without it rather than crashing. Verified: fixture renders without exception; metadata fields are stripped silently.

**Mind map**
- [x] **AC-5.9** Mind-map edge paths start and end at the boundary of the source/destination node shape, not at the center point. Currently branch lines connect through the center, causing lines to visually enter nodes rather than touching their edges. Fix: compute the intersection of the line with the node's bounding ellipse/rectangle before emitting the `<path>`. Verified: `TestMindmapEdgeEndpoints` asserts that no edge path endpoint coordinate equals a node's center `(n.x + w/2, n.y + h/2)`.

**Sankey**
- [ ] **AC-5.10** `sankey-beta` renders a proportional ribbon diagram. Nodes are bars on left/right sides; ribbons connect them with width proportional to flow value; source ribbon widths sum to node total. (AC-3.1 currently returns unsupported — this upgrades it to a real renderer.) Verified: `TestSankeyRibbons` asserts ribbon SVG elements exist and that ribbon widths are proportional to flow values.

**Pie**
- [x] **AC-5.11** Pie charts render as solid pie (inner radius = 0), not as donuts. Currently the renderer produces a ring/donut shape. Fix: set inner radius to 0 in the arc computation. Verified: `TestPieSolid` asserts no donut hole (inner radius = 0).

**ER**
- [x] **AC-5.12** ER entity record nodes are sized to fit all attribute rows. Currently entity tables are too small and attributes overflow. Fix: `_node_render_h` for ER nodes must count attribute rows and multiply by `_MEMBER_LINE_H`. Verified: `TestEREntityHeight` asserts entity height ≥ `NODE_H + num_attributes * _MEMBER_LINE_H`.

**Class**
- [x] **AC-5.13** Class diagram boxes are wide enough for the longest attribute/method name. Currently they are too narrow and text clips. Fix: `_measure_text_px` should scan all members, not just the class name, for width computation. Verified: `TestClassBoxWidth` asserts box width ≥ longest member text width + `NODE_HPAD`.

**Packet**
- [x] **AC-5.14** Packet diagram viewport is tightened to content bounds with no excessive vertical padding. Currently rows have large vertical gaps and the diagram occupies a fraction of the 1280px canvas. Fix: compute `canvas_h` from actual row heights. Verified: `TestPacketViewport` asserts content fills ≥ 60% of canvas area.

**XY chart**
- [x] **AC-5.15** XY chart canvas is sized to content (not padded to 1280px). Plot area occupies ≥ 60% of the rendered canvas. Verified: `TestXYChartViewport`.

**Config propagation**
- [x] **AC-5.16** Flowchart `%%{init: {"flowchart": {"nodeSpacing": N, "rankSpacing": M}}}%%` directives are parsed and propagate to `COL_GAP` / `RANK_GAP` in the layout algorithm. Verified: `TestFlowchartConfigSpacing` renders two fixtures with different spacing configs and asserts the resulting node coordinates differ proportionally.

**Subgraph local direction**
- [x] **AC-5.17** An inner `direction LR` declaration inside a subgraph block is honored: children of that subgraph are laid out left-to-right while the outer graph remains TB. Verified: `TestSubgraphLocalDirection` asserts that nodes inside a `direction LR` subgraph have the same `y` but different `x` values.

**GitGraph (implement)**
- [x] **AC-5.18** `gitgraph-basic` renders a basic git branch diagram: commits appear as circles on horizontal lanes, branch labels shown, merge connectors drawn. Currently returns unsupported via lowercase `gitgraph` detection (AC-3.5 fixed detection — this AC requires the actual renderer). Verified: `TestGitGraphBasic`.

**Journey (implement)**
- [x] **AC-5.19** `journey-basic` renders with section bands and task score cards. Currently returns unsupported. Verified: `TestJourneyBasic` asserts section labels and task entries are present in output.

**Requirement (implement)**
- [x] **AC-5.20** `requirement-basic` renders requirement and element record nodes with typed relation labels. Currently returns unsupported. Verified: `TestRequirementBasic`.

## Assumptions

- Python 3.13 runtime (`python3 -c "import sys; print(sys.version)"` → `3.13.x`).
- Test runner: `pytest` from `requirements.txt`, no new test dependencies needed.
- Snapshot baselines are machine-authoritative (committed by eugenelim on his Mac); CI skips snapshot tests when `SNAPSHOT_BASELINE_PLATFORM` does not match.
- Sankey AC-3.1: implementing a full Sankey renderer is Phase 3 work; returning `unsupported` is an acceptable interim for AC-3.1 if the ribbon renderer is not yet implemented.
