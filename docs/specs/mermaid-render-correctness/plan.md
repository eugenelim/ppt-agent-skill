# Plan: Mermaid Renderer Correctness

- **Spec:** [`spec.md`](spec.md)
- **Status:** Phase 0-3 complete (all ACs done). **Remaining: Task 1.5 — snapshot baseline recapture.** Run `python -m pytest tests/test_snapshots.py --snapshot-capture` on the reference machine, then commit updated PNGs.

## Phase 0 — Dummy-chain routing bug fix (DONE)

All tasks complete as of 2026-07-20 on branch `eugene/mermaid-render-bug-fixes`.

### Task 0.1: Label on last dummy-chain segment (DONE)
- **Files:** `scripts/mermaid_render/layout/_layout.py`
- **Tests:** `test_fix_state.py::TestTransitionLabels::test_complex_fixture_labels`
- **Done when:** `logout` label renders on the `Active → _sm_end_` transition.
- **Approach:** `_assign_ranks` moved the label from the first segment to the last segment of each dummy chain (`label=e.label` on the final append instead of the intermediate ones).

### Task 0.2: Single path per logical edge (DONE)
- **Files:** `scripts/mermaid_render/layout/_routing.py`
- **Tests:** `tests/test_syntax_flowchart.py::TestDummyChainRouting` (4 tests)
- **Done when:** 5 logical edges in `flowchart-arrows-defs` → 5 SVG paths, no off-canvas coordinates.
- **Approach:** `_route_edges` skips edges where `dst.is_dummy` (intermediate segments); for the last segment where `src.is_dummy`, substitutes `orig_src` as the routing start point. Fan-in/fan-out and `parallel_edge_idx` both use real `orig_src`/`orig_dst` endpoints.

### Task 0.3: Skip-rank forward edges via right lane (DONE)
- **Files:** `scripts/mermaid_render/layout/_routing.py`
- **Tests:** `TestDummyChainRouting::test_long_edge_path_stays_within_canvas`
- **Done when:** `A ==> C` and `A -.-> D` (rank_gap > 1) route via right-side lane, not A*; paths stay within `canvas_w + 5`.
- **Approach:** Pre-loop builds `_skip_lane: dict[int, int]`; main loop dispatches rank_gap > 1 forward edges to `right_lane_x + 8 * skip_i` orthogonal route before reaching the LR/TB branching logic.

---

## Phase 1 — Geometric correctness

### Task 1.1: Parametric geometric invariant tests
- **Files:** `tests/test_render_correctness.py` (new file)
- **Tests:** `TestGeometricInvariants::test_one_path_per_logical_edge`, `TestGeometricInvariants::test_paths_within_canvas`
- **Done when:** Both tests pass for every fixture in `tests/fixtures/`; red stubs exist before implementation.
- **Depends on:** none (pure test addition)
- **Approach:** Parametrize over `glob('tests/fixtures/*.mmd')`. For the path-count test, collect `data-src`/`data-dst` attribute pairs from `<path>` elements and assert each pair appears exactly once. For the canvas test, extract all `M x` and `L x` coordinates from path `d` attributes using regex `r'[ML]\s+([\d.]+)'` and assert max ≤ parsed `canvas_w + 5`. Skip fixtures for diagram types that don't produce `<path>` elements (pie, gantt, xychart, etc.).

### Task 1.2: Sequence diagram canvas bounds (notes outside viewbox)
- **Files:** `scripts/mermaid_render/layout/_strategies.py` or sequence renderer
- **Tests:** `test_fix_sequence.py::TestNotePositioning::test_left_of_note_is_left_of_participant` (tighten assertion: no negative x)
- **Done when:** `sequence-notes-all` renders with all note polygons at x ≥ 0 and x ≤ canvas_w.
- **Depends on:** none
- **Approach:** Sequence renderer currently calculates canvas_w from participant count before note offsets are known. Perform a post-placement bounds expansion: after all note positions are computed, extend canvas_w if any note's x_min < 0 or x_max > canvas_w, then translate all elements by `tx = max(0, -min_x) + CANVAS_PAD`.

### Task 1.3: ER label quote stripping
- **Files:** `scripts/mermaid_render/parsers/` (ER parser)
- **Tests:** `tests/test_render_correctness.py::TestERLabelQuotes`
- **Done when:** `"places"` in `er-cardinality-all.mmd` renders as `places` without surrounding quotes.
- **Depends on:** none
- **Approach:** In the ER parser's relationship label extraction, strip surrounding `"` characters from label tokens using `label.strip('"')`.

### Task 1.4: Self-loop routing (rectangular loop)
- **Files:** `scripts/mermaid_render/layout/_routing.py`
- **Tests:** `tests/test_render_correctness.py::TestSelfLoopRouting`
- **Done when:** `A --> A` in a flowchart renders as a 4-waypoint rectangular path exiting the right face, staying within canvas bounds.
- **Depends on:** none
- **Approach:** In `_route_edges`, the existing self-loop path detection (`e.src == e.dst`) routes a small rectangular loop: exit right face at `(node.x + NODE_W, node.y + NODE_H*0.35)`, right turn to `(node.x + NODE_W + 20, same_y)`, down to `(same_x, node.y + NODE_H*0.65)`, return left to `(node.x + NODE_W, node.y + NODE_H*0.65)`. Label goes to the right of the loop midpoint.

### Task 1.5: Snapshot baseline recapture — **NEXT (unblocked)**
- **Files:** `tests/snapshots/` (committed PNGs)
- **Tests:** All snapshot tests in `tests/test_snapshots.py`
- **Done when:** All snapshot tests pass after recapture.
- **Depends on:** All Phase 1-3 fixes (now done). All Bucket B defects are fixed.
- **Approach:** Run `python -m pytest tests/test_snapshots.py --snapshot-capture` on the reference machine (macOS, eugenelim). Review the diff of changed PNGs (should be ~63 stale baselines + the Bucket B defect fixtures). Commit updated PNGs. Verify `python -m pytest tests/test_snapshots.py` passes 100%.
- **Note:** At start of this spec there were 63 failing snapshot tests (all pre-existing). After Phase 1-3 fixes, the rendering changed (improved), so baselines need recapture. The `--snapshot-capture` flag regenerates PNGs in place.

---

## Phase 2 — Semantic correctness

### Task 2.1: Class diagram marker endpoint semantics
- **Files:** `scripts/mermaid_render/parsers/` (class parser), `scripts/mermaid_render/layout/_routing.py`
- **Tests:** `tests/test_render_correctness.py::TestClassMarkerEndpoints`
- **Done when:** `A <|-- B` places hollow-triangle at `A`; `A *-- B` places filled-diamond at `A`.
- **Depends on:** none
- **Approach:** The parser must store `startMarker` and `endMarker` independently on the `_Edge`. The routing layer must apply `marker_start_id` at the source endpoint and `marker_end_id` at the destination, regardless of path direction. Current code always applies the marker at the `dst` end.

### Task 2.2: Class diagram multiplicities (DONE)
- **Files:** `_constants.py` (_Edge.src_label/dst_label), `_strategies.py` (_CLASS_REL_RE group capture + parser), `_routing.py` (thread through result dict), `_renderer.py` (emit mult-label spans)
- **Tests:** `tests/test_render_correctness.py::TestClassMultiplicities` (3 tests, all green)
- **Done when:** `A "1" -- "0..*" B` shows `1` near A and `0..*` near B.
- **Depends on:** Task 2.1 (same parser)
- **Approach:** Added `src_label`/`dst_label` fields to `_Edge`. Updated `_CLASS_REL_RE` to capture multiplicity groups (now groups 2/4, op is group 3). Parser passes them to `_Edge`. Routing threads them through all 7 `result.append` calls. Renderer emits `<span class="mult-label">` near path first/last M/L coordinates extracted via `_path_endpoint(d)` helper.

### Task 2.3: ER cardinality marker primitives (DONE)
- **Files:** `scripts/mermaid_render/layout/_strategies.py`
- **Tests:** `tests/test_render_correctness.py::TestERCardinalityMarkers` (4 tests, all green)
- **Done when:** Each cardinality combination (`||`, `|o`, `}|`, `o{`) renders as the correct SVG primitive composition.
- **Depends on:** none
- **Approach:** Root cause was `_ER_CARD_SRC_MAP` having `"o|"` for zero-one but Mermaid's actual left-side zero-or-one notation is `"|o"` (matches the `er-cardinality-all.mmd` fixture). Fixed by changing the map key. The `_render_crow_foot` function already composed the correct primitives (bar/circle/crowfoot); no refactor needed.

### Task 2.4: Nested state compound layout (no duplicate atomic node) (DONE)
- **Files:** `scripts/mermaid_render/layout/_parser.py`
- **Tests:** `tests/test_render_correctness.py::TestNestedStateCompound` (4 tests, all green)
- **Done when:** `statediagram-nested` renders `Processing` as a compound boundary only; no duplicate atomic node; external transitions render.
- **Depends on:** none
- **Approach:** Added `_composite_gids` set in `_parse_graph_source`; removed the `_ensure()` call in the composite state handler (it would create an atomic node); added a post-processing loop that (1) deletes atomic nodes re-created by transition parsing for each composite state name, and (2) rewires edges to/from composite state names to the group's scoped `_sm_start_`/`_sm_end_` anchor nodes. Updated `_node_labels` in `test_syntax_state.py` to capture both `node-label` and `group-label` (composite state names now appear as group labels).

### Task 2.5: Node width from text content (replace fixed 192px) — DONE
- **Files:** `scripts/mermaid_render/layout/_constants.py`, `_layout.py`, `_routing.py`, `_renderer.py`, `_strategies.py`
- **Tests:** `tests/test_render_correctness.py::TestNodeTextSizing`
- **Done when:** A node labeled `A` is narrower than one labeled `ABCDEFGHIJKLMNOPQRSTUVWXYZ`; both are ≥ `NODE_MIN_W` (64px); `canvas_w` for the wide-node diagram is proportionally larger.
- **Approach:** Added `_measure_text_px`, `NODE_MIN_W=64`, `NODE_HPAD=24` to `_constants.py`; `_Node.width` field (0 = use default); per-node widths computed in `_assign_coordinates` with `_layout_nw = max(widths)` for uniform column spacing. Nodes narrower than `_layout_nw` are centered within their column slot via `_slot_off = (_layout_nw - n.width) // 2`. Terminal circles get `_circ_shift` applied in `_strategies.py` so their visual centre aligns with rect nodes in the same column.

---

## Phase 3 — Typed adapters

### Task 3.1: Sankey — unsupported (DONE)
- **Tests:** `tests/test_render_correctness.py::TestSankeyRenderer`; `tests/test_syntax_sankey.py` updated
- **Approach:** Added `"sankey-beta"` to the unsupported `raise ValueError` block in `_dispatch`. Updated `test_syntax_sankey.py` to assert `ValueError` (was: asserts successful render). Moved `sankey-basic.mmd` from `_NO_PATHS` to `_UNSUPPORTED` in invariant tests.

### Task 3.2: C4 semantic fields (DONE)
- **Tests:** `tests/test_render_correctness.py::TestC4SemanticFields`
- **Approach:** Extended `_C4_ELEM_RE` to capture optional description (group 4). Added `_C4_TYPE_DISPLAY` map. Label format changed to `"{name}|[{type_tag}]\n{desc}"` using `|` for the tech-label slot in the renderer (shows type row + description row). `person` shape remains `"circle"` (node-circle CSS class).

### Task 3.3: ZenUML — mark as unsupported (DONE)
- **Tests:** `tests/test_render_correctness.py::TestZenUMLUnsupported`; `tests/test_syntax_zenuml.py` updated
- **Approach:** Added `"zenuml"` to the unsupported `raise ValueError` block. Updated `test_syntax_zenuml.py` to assert `ValueError`. Moved `zenuml-basic.mmd` from `_NO_PATHS` to `_UNSUPPORTED`.

### Task 3.4: GitGraph — lowercase detector (DONE)
- **Tests:** `tests/test_render_correctness.py::TestGitGraphDetector`
- **Approach:** `_detect_directive` already lowercases the directive. The `gitgraph` check in `_dispatch` already uses lowercase comparison. Test confirms the existing behavior is correct and by design.

---

## Declined items (not in scope)

- **Full ELK compound layout engine:** implementing the full ELK Layered pipeline (hierarchical nodes, port constraints, compound boundary dummies). The approach in Task 2.4 is a targeted fix for the specific stateDiagram bug; a full ELK-style engine is a future spec.
- **Browser font measurement (canvas.measureText):** Task 2.5 uses a character-width approximation. True browser-quality text measurement requires a headless browser or a font-metrics library — a new dependency.
- **Libavoid orthogonal router:** the inspection report recommends libavoid for grouped-flowchart edge collisions. This is a future spec; current A* router is retained.
- **Journey, Requirement, ZenUML full implementations:** these are return-unsupported for now (AC-3.3, AC-3.4); full implementation is deferred.
