# Plan: renderer-stable-ids

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn.

## Approach

Seven files change: `_constants.py` (add `orig_src`/`orig_dst` to `_Edge`),
`_layout.py` (thread them through dummy splitting), `_routing.py` (pipe
src/dst through result dicts), `_renderer.py` (add attrs to graph-topology
node divs and edge paths/labels), `_strategies.py` (add attrs to 11 strategy
emitters including block-beta), `tests/test_mermaid_layout.py` (new
assertions per type), and `docs/specs/README.md` (active spec list).

All changes are additive — `data-*` attributes are inert to layout, CSS, and
the existing SVG pipeline. The riskiest part is the routing pipe-through: T1
must add `src`/`dst` to all 6 `result.append` sites in `_routing.py` —
missing even one leaves unlabeled-edge paths without attrs (since there's no
label span as a fallback carrier). T1's verification uses a runtime assertion
over `_route_edges` output covering all three routing branches.

Work order: T0 (TDD — _Edge fields) → T1 (TDD property/invariant — routing)
→ T2 (TDD — graph topology) → T3 (TDD — sequence) → T4 (TDD — gantt) →
T5 (TDD — remaining specialty types) → T6 (goal-based — gates + README).
T3–T5 are independent of each other.

## Constraints

- HTML/CSS div + SVG-overlay architecture is a permanent contract
  (`mermaid-source-bridge` spec) — no migration to pure SVG.
- No new pip dependency.
- Snapshot PNGs must be pixel-identical (`data-*` attrs are invisible).
- No change to `_parser.py` or `_constants.py` data structures beyond the two
  optional `_Edge` fields `orig_src`/`orig_dst` added by T0.

## Construction tests

**Integration tests:** none beyond per-task tests — each task's test is
self-contained in `tests/test_mermaid_layout.py`.

**Manual verification:** none — all ACs are machine-checkable via pytest.

## Design (LLD)

### Design decisions

- **Routing pipe-through over re-parsing**: add `src`/`dst` to the existing
  routed spec dict rather than re-deriving from the edge list in the renderer.
  The SVG `<path>` is the only src/dst carrier for unlabeled edges (no label
  span is emitted), so the routing dict must carry identity.
  Traces to: graph-topology edge ACs.
- **Inline f-string, no helper**: attribute emission is a one-field addition
  per site; no `_emit_node_attr()` abstraction. Traces to: Boundaries.
- **SVG path/line attrs for graph topology + sequence + block-beta edges**:
  `<path>` and `<line>` elements inside SVG overlays carry `data-src`/`data-dst`.
  If dom-to-svg drops them that is acceptable (oracle reads HTML). Traces to:
  graph-topology edge ACs, sequence message ACs, block-beta ACs.
- **Mindmap positional id**: mindmap nodes have no stable source id; 0-based
  position index is deterministic for a given source. Traces to: mindmap AC.
- **Block-beta included**: blocks have source ids (`blk["id"]`) and edges are
  tracked as `(src_id, dst_id)` tuples — natural identity exists.
  Traces to: block-beta AC.
- **`_Edge.orig_src`/`orig_dst` for dummy-chain threading**: multi-rank edges
  are split into dummy-node chains in `_layout.py`; without threading the
  original endpoint ids, routed paths would carry dummy ids (e.g.,
  `_dummy_A_D_1`) which the oracle cannot match to source nodes. Adding two
  optional fields to `_Edge` is the minimal change. Traces to: graph-topology
  edge paths AC.
- **Packet integer values exempt from `_h()`**: bit-range ints contain no
  HTML-unsafe chars; emitting them without `_h()` is intentional. Traces to:
  Always-do Boundary note.

### Data & schema

No persistent schema change. The change is purely to the in-memory HTML string
produced by each emitter function.

## Tasks

### T0: Add orig_src/orig_dst to _Edge and thread through _layout.py dummy splitting

**Depends on:** none

**Touches:** `scripts/mermaid_layout/_constants.py`, `scripts/mermaid_layout/_layout.py`

**Tests:**
- `test_assign_ranks_multi_rank_edge_orig_src_dst_threaded`: build a backbone
  `A→B→C→D` (forces D to rank 3) plus a long-jump edge `A→D`; call
  `_assign_ranks`. Assert that (1) the result contains at least one `_Edge`
  with a dummy src or dst (confirming dummies were actually inserted), and (2)
  every such dummy-segment edge carries `orig_src="A"` and `orig_dst="D"`.

**Approach:**
- In `scripts/mermaid_layout/_constants.py`, add two optional fields to `_Edge`:
  ```python
  orig_src: Optional[str] = None
  orig_dst: Optional[str] = None
  ```
- In `scripts/mermaid_layout/_layout.py` (`_assign_ranks`, dummy insertion
  loop ~lines 113–123), set `orig_src=e.src, orig_dst=e.dst` on every split
  `_Edge` created in the dummy chain (both the intermediate and the final
  segment).

**Done when:** `test_assign_ranks_multi_rank_edge_orig_src_dst_threaded` passes.

---

### T1: Pipe src/dst through _routing.py result dicts

**Depends on:** T0

**Touches:** `scripts/mermaid_layout/_routing.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `test_route_edges_tb_all_dicts_carry_src_dst`: build a TB node set with a
  forward edge (A→B), a self-loop (A→A), and a back-edge (B→A, marked
  `reversed_=True`); call `_route_edges(..., direction="TB")` and assert every
  dict carries `"src"` and `"dst"` matching the edge's orig_src-or-src /
  orig_dst-or-dst. This covers self-loop (line ~300), TB back-edge sub-cases
  (lines ~350/375/400), and TB forward (line ~599).
- `test_route_edges_lr_all_dicts_carry_src_dst`: same node set, call with
  `direction="LR"` — asserts src/dst on all dicts, covering LR back-edge
  sub-cases (lines ~350/375/400) and LR forward (line ~513).

**Approach:**
- In `scripts/mermaid_layout/_routing.py`, add
  `"src": e.orig_src or e.src, "dst": e.orig_dst or e.dst` to every
  `result.append({...})` call. There are 6 such calls (lines 300, 350, 375,
  400, 513, 599 as of current HEAD).

**Done when:** both routing tests pass green.

---

### T2: Add data-node-id to graph topology node divs + data-src/data-dst/data-edge-label to edge paths and labels

**Depends on:** T1

**Touches:** `scripts/mermaid_layout/_renderer.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `test_graph_topology_node_div_carries_data_node_id`: dispatch
  `flowchart TB\n  A[Alpha] --> B[Beta]` — HTML contains `data-node-id="A"`
  and `data-node-id="B"`.
- `test_graph_topology_dummy_node_no_data_attr`: a graph with a multi-rank
  edge (inserts dummy nodes) — dummy node divs do not carry `data-node-id`.
- `test_graph_topology_edge_path_carries_data_src_dst`: same flowchart source
  — `data-src="A" data-dst="B"` appears on the `<path>` element.
- `test_graph_topology_edge_path_self_loop`: dispatch `flowchart TB\n  A-->A`
  — self-loop `<path>` carries `data-src="A" data-dst="A"`.
- `test_graph_topology_edge_path_back_edge`: dispatch a cyclic flowchart
  (A→B→A) — both resulting paths carry `data-src` and `data-dst`.
- `test_graph_topology_edge_path_multi_rank`: dispatch a flowchart where
  A→C skips rank (e.g., `flowchart TB\n  A-->B\n  B-->C\n  A-->C`) — the
  multi-rank A→C path carries `data-src="A" data-dst="C"` (not dummy ids).
- `test_graph_topology_edge_label_carries_all_attrs`: dispatch
  `flowchart TB\n  A -->|hello| B` — edge label `<span>` carries
  `data-src="A"`, `data-dst="B"`, `data-edge-label="hello"`.
- `test_er_diagram_entity_carries_data_node_id`: erDiagram dispatch.
- `test_class_diagram_class_carries_data_node_id`: classDiagram dispatch.
- `test_state_diagram_state_carries_data_node_id`: stateDiagram-v2 dispatch.
- `test_architecture_beta_service_carries_data_node_id`: architecture-beta.
- `test_c4_element_carries_data_node_id`: C4Context dispatch.

**Approach:**
- In `_render_graph_fragment` (`_renderer.py`):
  1. Non-dummy node divs: add `data-node-id="{_h(nid)}"` to the opening
     `<div>` tag in all four shape branches (circle/doublecircle, subroutine,
     default); skip the dummy branch.
  2. Edge `<path>` elements: add `data-src="{_h(spec['src'])}"
     data-dst="{_h(spec['dst'])}"` to the `<path>` in the routed-edge loop.
  3. Edge label `<span>` elements: add `data-src`, `data-dst`,
     `data-edge-label` to the edge-label span.
- Add a comment at the top of `_render_graph_fragment` pointing to the
  attribute scheme table in `docs/specs/renderer-stable-ids/spec.md`.

**Done when:** all TDD tests above pass; `pytest tests/test_mermaid_layout.py
-k "data_node_id or data_src or data_dst or data_edge_label"` green.

---

### T3: Add data-node-id to sequence participants + data-src/data-dst to messages

**Depends on:** none

**Touches:** `scripts/mermaid_layout/_strategies.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `test_sequence_participant_carries_data_node_id`: dispatch
  `sequenceDiagram\n  Alice->>Bob: hello` — participant header divs carry
  `data-node-id="Alice"` and `data-node-id="Bob"`.
- `test_sequence_participant_as_form_uses_actor_id`: dispatch
  `sequenceDiagram\n  participant A as Alice\n  A->>B: hi` — header div
  carries `data-node-id="A"`, not `"Alice"`.
- `test_sequence_message_line_carries_data_src_dst`: same source — SVG
  `<line>` element carries `data-src="Alice" data-dst="Bob"`.
- `test_sequence_message_label_carries_all_attrs`: same source — label
  `<span>` carries `data-src="Alice"`, `data-dst="Bob"`,
  `data-edge-label="hello"`.
- `test_sequence_self_message_path_carries_data_src_dst`: dispatch
  `sequenceDiagram\n  Alice->>Alice: self` — self-loop `<path>` carries
  `data-src="Alice" data-dst="Alice"`.

**Approach:**
- In `_layout_lifeline` (`_strategies.py`):
  1. Participant header `<div>`: add `data-node-id="{_h(pid)}"`.
  2. Message SVG loop (rows emitting `<line>` and `<path>` for self-loops):
     add `data-src="{_h(it['src'])}" data-dst="{_h(it['dst'])}"` to both the
     `<line>` and the `<path>` element.
  3. Message label `<span>`: add `data-src`, `data-dst`, `data-edge-label`.

**Done when:** all TDD tests above pass.

---

### T4: Add data-task-id to gantt task bars

**Depends on:** none

**Touches:** `scripts/mermaid_layout/_strategies.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `test_gantt_task_bar_carries_explicit_id`: dispatch a gantt with an explicit
  task id (e.g., `task1 : desc, taskId, 2024-01-01, 1d`) — bar div carries
  `data-task-id="taskid"` (lowercased as parsed).
- `test_gantt_task_bar_falls_back_to_name`: dispatch a gantt without an
  explicit task id (e.g., `desc : 2024-01-01, 1d`) — bar div carries
  `data-task-id="desc"`.

**Approach:**
- In `_layout_gantt` (`_strategies.py`), task bar `<div>` (label column):
  add `data-task-id="{_h(task['id'] if task['id'] else task['name'])}"`.

**Done when:** TDD tests above pass.

---

### T5: Add type-specific attrs to kanban, pie, quadrant, xychart, packet, mindmap, timeline, block-beta

**Depends on:** none

**Touches:** `scripts/mermaid_layout/_strategies.py`, `tests/test_mermaid_layout.py`

**Tests:**

*Kanban:*
- `test_kanban_column_header_carries_data_col`: column header div carries
  `data-col="<column name>"`.
- `test_kanban_card_carries_data_card`: card div carries
  `data-card="<card label>"`.

*Pie:*
- `test_pie_slice_label_carries_data_slice`: each slice label `<span>` carries
  `data-slice="<label>"`.

*Quadrant:*
- `test_quadrant_point_label_carries_data_point`: each point label `<span>`
  carries `data-point="<name>"`.

*XYchart:*
- `test_xychart_bar_carries_data_category_with_x_cats`: xychart with an
  x-axis label list — each bar div carries `data-category="<label>"`.
- `test_xychart_bar_carries_data_category_fallback`: no x-axis labels —
  bars carry `data-category="1"`, `"2"`, etc.

*Packet:*
- `test_packet_field_carries_data_field_range`: multi-bit field (e.g.,
  `0-7 : Source`) — field div carries `data-field="0-7"`.
- `test_packet_field_carries_data_field_single`: single-bit field (e.g.,
  `0 : Flag`) — field div carries `data-field="0"`.

*Mindmap:*
- `test_mindmap_node_carries_positional_data_node_id`: first node div carries
  `data-node-id="0"`, second `"1"`, etc.
- `test_mindmap_stable_across_renders`: render same source twice; both outputs
  identical (positional-id stability).

*Timeline:*
- `test_timeline_period_carries_data_node_id`: each period div carries
  `data-node-id="<period name>"`.

*Block-beta:*
- `test_block_beta_block_div_carries_data_node_id`: dispatch a minimal
  `block-beta\n  columns 2\n  A["Label A"] B["Label B"]` — block divs carry
  `data-node-id="A"` and `data-node-id="B"`.
- `test_block_beta_edge_line_carries_data_src_dst`: dispatch with an edge
  (`A --> B`) — SVG `<line>` carries `data-src="A" data-dst="B"`.

**Approach:**
- `_layout_kanban`: column header `<div>` — add `data-col="{_h(col['name'])}"`;
  card `<div>` — add `data-card="{_h(card)}"`.
- `_layout_pie`: slice label `<span>` — add `data-slice="{_h(sl['label'])}"`.
- `_layout_quadrant`: point label `<span>` — add `data-point="{_h(pt['name'])}"`.
- `_layout_xychart`: bar `<div>` — add `data-category="{_h(cat)}"` where `cat`
  is `x_cats[i]` if in range else `str(i + 1)`.
- `_layout_packet`: field `<div>` — add `data-field="{fld['start']}-{fld['end']}"` 
  if `fld['start'] != fld['end']` else `str(fld['start'])`.
- `_layout_mindmap`: node `<div>` — add `data-node-id="{i}"` using `enumerate`
  over the flat list.
- `_layout_timeline`: period `<div>` — add `data-node-id="{_h(sec['period'])}"`.
- `_layout_block`: block `<div>` — add `data-node-id="{_h(blk['id'])}"`;
  SVG `<line>` edges — add `data-src="{_h(src_id)}" data-dst="{_h(dst_id)}"`.

**Done when:** all TDD tests above pass.

---

### T6: Gates and README update

**Depends on:** T0, T1, T2, T3, T4, T5

**Touches:** `docs/specs/README.md`

**Tests:**
- `pytest tests/test_mermaid_layout.py` — all green.
- `pytest tests/test_snapshots.py` — zero diff.
- Lint and typecheck clean.
- `python .claude/skills/work-loop/scripts/lint-spec-status.py` clean.

**Approach:**
- Update `docs/specs/README.md` to add `renderer-stable-ids` to the active
  spec list.
- Run the full gate suite and confirm all green.

**Done when:** all gates pass; `docs/specs/README.md` updated.

---

## Rollout

Pure-logic change with no infrastructure, no flags, no external-system
dependencies, and no data migration. Delivery: direct merge to main after
gates pass. Reversible: removing the `data-*` attr additions is a clean
revert with no side effects.

## Risks

- **Routing pipe-through completeness**: all 6 `result.append` sites must be
  updated in `_routing.py`. T1's runtime assertion covers all three branch
  types (forward, self-loop, back-edge) to catch any missed site.
- **Snapshot regression**: `data-*` attributes are invisible to the renderer,
  so no visual diff is expected. If any snapshot fails, investigate the
  Puppeteer pipeline before assuming the attr caused it.
- **SVG overlay attr survival**: `data-src`/`data-dst` on SVG elements may be
  dropped by dom-to-svg. This does not affect the test gate (oracle reads HTML)
  but should be noted if the attribute scheme is later extended to the exported
  SVG/PPTX.

## Changelog

- 2026-07-19: initial plan
- 2026-07-19: added block-beta (user confirmed stable source ids exist);
  fixed T1 to runtime assertion; added self-loop/back-edge tests to T2;
  moved comment addition from T6 to T2; fixed gantt casing note; fixed
  sequence AC to use actor id
- 2026-07-19: added T0 (_Edge.orig_src/orig_dst + _layout.py threading) to
  fix multi-rank edge identity; expanded T1 to cover LR routing branches;
  added multi-rank edge test to T2; noted packet int-value _h() exemption
