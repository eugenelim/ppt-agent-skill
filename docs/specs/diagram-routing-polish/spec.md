# Diagram Routing Polish — spec

Mode: full (multi-feature, dependent tasks; structural changes to `_route_edges`, `_assign_coordinates`, `_render_graph_fragment`)
- **Status:** Shipped

## Objective

Fix eight rendering bugs discovered during architecture diagram review sessions, plus three polish improvements requested by design review. Goal: `flowchart LR` works correctly, multi-line nodes don't clip or overflow group boxes, labels don't cross lines, arrowheads are proportional, and semantic colour roles are documented.

## Background: bugs found during architecture diagram sessions

The following bugs required in-session workarounds and are **not yet fixed**:

- **Bug 4** — `_SPEC_RE` rejects `[` inside quoted labels: `NODE["name\n[inner]"]` falls back to bare ID because the `rect` capture `[^\[\]]*` bars bracket characters even inside a quoted string. Fix: add `rect_q` / `cylinder_q` / `round_q` variants using `"[^"]+"` (quote-delimited) that take priority.
- **Bug 5** — Group bounding box uses fixed `NODE_H`: multi-line / icon / tech-label nodes are taller than `NODE_H=56`, so they visually overflow their subgraph border box.
- **Bug 6** — Canvas height uses fixed `NODE_H`: same root cause; nodes are clipped at the canvas bottom.
- **Bug 7** — `flowchart LR` ignores direction: `_assign_coordinates` always maps `rank→Y, col→X` regardless of direction, so all LR diagrams render as TB stacks.
- **Bug 8** — LR layout uses fixed pitch for col→Y: multi-line nodes are taller than `NODE_H`, so the fixed row pitch in LR mode causes node overlap.

Bugs 1a, 1b, 2, 3 were fixed in the previous session.

## Acceptance Criteria

- [x] **AC-1 (Bug 4)** `_SPEC_RE` matches bracket-containing quoted labels: `_parse_spec('NODE["name\\n[inner]"]')` returns label `name\n[inner]`, not the node ID. Add `rect_q`/`round_q`/`cylinder_q` variants before the unquoted variants in `_SPEC_RE`.
- [x] **AC-2 (Bug 5)** `_node_render_h(node)` helper mirrors `_render_graph_fragment`'s per-node height calculation. Group bounding box `gy`, `gh` use `_node_render_h` for all member nodes.
- [x] **AC-3 (Bug 6)** Canvas height after `_assign_coordinates` is overridden in `_layout_graph_topology` using `max(n.y + _node_render_h(n) for n in real_nodes) + CANVAS_PAD`.
- [x] **AC-4 (Bug 7)** `flowchart LR` / `graph LR` diagrams render left-to-right: `rank→X, col→Y` for LR; `_route_edges` uses horizontal Bézier (control points at 1/3 and 2/3 of horizontal span) for LR forward edges; back-edges use a bottom-lane bypass.
- [x] **AC-5 (Bug 8)** LR layout uses variable row pitch: `_assign_coordinates` accumulates `_node_render_h` to compute Y for each column position so multi-line nodes don't overlap.
- [x] **AC-6** `right_lane_x` is computed as `max(n.x + NODE_W for non-dummy nodes) + 32` (32 > GROUP_PAD_X=16 so it clears group container borders).
- [x] **AC-7** `_arrowhead` gains keyword params `back=8, half_w=4` (was hardcoded 10/6); `_route_edges` passes `back=10, half_w=5` for thick edges, defaults for normal; `_layout_lifeline` call sites pass explicit `back=10, half_w=6` to preserve existing sequence-diagram arrowhead size. No `thick=` boolean parameter (that cannot reproduce `half_w=6` lifeline size).
- [x] **AC-8** Edge labels for near-vertical edges carry `rot=90`; label position uses perpendicular offset (14px from midpoint); label HTML uses `transform:translate(-50%,-50%) rotate(Ndeg)`.
- [x] **AC-9** Node divs include `box-shadow:var(--node-shadow,none)`. `references/blocks/diagram.md` adds `--node-shadow` to the `.diagram{}` CSS contract block (bound to `var(--card-shadow,none)`) and adds a "节点颜色角色 / Semantic colour-role guidance" section.
- [x] **AC-11** All existing tests pass; `lint_diagram_recipes.py` 0 violations. `test_mermaid_routing_polish()` adds ≥10 checks covering ACs 1–9.

## Boundaries

**In scope:**
- `scripts/mermaid_layout.py` — `_SPEC_RE`, `_node_render_h` (new), `_assign_coordinates` (direction-aware, variable pitch), `_route_edges` (LR forward/back-edge, right_lane_x, arrowhead args, label rotation), `_render_graph_fragment` (group box, canvas height, node shadow, label transform)
- `references/blocks/diagram.md` — `--node-shadow` in CSS contract + colour-role section
- `scripts/test_diagram_qa.py` — `test_mermaid_routing_polish()`

**Not in scope:**
- `--o` circle-headed edge operator (Bug 9, separate minor item)
- Fragment-to-slide assembler (`gen_slides.py` reusable script) — separate spec
- Auto label collision detection (needs font metrics)
- Glass/backdrop-filter card style (not pipeline-safe)
- Non-graph layouts (sequence, ER, class)

## Declined patterns

- Tempted to fix rank_gap==0 same-rank routing: declining — this branch can never fire (rank assignment guarantees dst.rank ≥ src.rank+1 for all non-reversed edges). The adversarial reviewer confirmed this. The actual visible crossing is from LR-mode variable-height overlap (Bug 8), which AC-5 fixes.
- Tempted to change `_arrowhead` defaults globally: declining — sequence diagrams share this function; only graph-topology call sites get the new proportions. `_layout_lifeline` call sites get explicit `back=10, half_w=6` args to stay unchanged.
- Tempted to add label-collision resolution: declining — perpendicular offset + rotation is sufficient; font-metrics-based resolution requires a browser runtime.
- Tempted to add `backdrop-filter:blur` glass effect: declining — not pipeline-safe per `pipeline-compat.md`.

## Testing Strategy

TDD for all parser and layout functions. Goal-based for documentation ACs.

- **AC-1**: `_parse_spec('NODE["name\\n[inner]"]')` → label == `"name\n[inner]"` (not the ID).
- **AC-2**: Build nodes with multi-line labels; `_node_render_h` returns > `NODE_H`; group bounding box `gh` ≥ `max(node.y + _node_render_h(n)) - gy + GROUP_PAD_Y_BOT`.
- **AC-3**: After `_layout_graph_topology` with multi-line node, canvas_h > `CANVAS_PAD * 2 + (max_rank+1) * (NODE_H+RANK_GAP)`.
- **AC-4**: `_dispatch("flowchart LR\nA-->B-->C", None, 600)` produces HTML where node A's `left` < node B's `left` (LR means rank→x increases).
- **AC-5**: LR diagram with a multi-line node — node B's `top` > node A's `top` + `_node_render_h(A)` (no y-overlap).
- **AC-6**: Build scenario with post-scale nodes at max x=460; assert `right_lane_x ≥ 460+32=492`. Group at max x=460+NODE_W=620; `right_lane_x ≥ 652`.
- **AC-7**: Parse `_arrowhead(100,100,0,1)` points string → half-width == 4, back == 8. Parse `_arrowhead(100,100,0,1,thick=True)` → half-width == 5, back == 10.
- **AC-8**: Vertical forward edge (x1==x2) → `spec["rot"] == 90` and `spec["lx"] != mid_x`.
- **AC-9**: `_render_graph_fragment` output contains `--node-shadow` in a node div style attr. `grep -c "\-\-node-shadow" references/blocks/diagram.md` > 0.

## Assumptions

1. `_node_render_h` must be a pure function of node fields (not require rendering) — it can replicate the `extra_h` calculation from `_render_graph_fragment` directly.
2. For LR layout, `fan_offset` distributes across the node's vertical range (height) rather than horizontal width — the function already works generically on `node_w` param; pass `NODE_H` for LR.
3. `_SPEC_RE` quoted variants (`rect_q` etc.) use `"[^"]+"` — single-quoted labels are not handled (acceptable, single-quote labels are rare).
4. The `direction` string must be threaded: `_layout_graph_topology` → `_assign_coordinates(nodes, direction)`, `_render_graph_fragment(nodes, edges, groups, canvas_w, canvas_h, direction="TB")`, and inside `_render_graph_fragment` → `_route_edges(nodes, edges, canvas_w, direction)`. `_render_graph_fragment` currently has no `direction` param — adding it with `direction="TB"` default keeps non-graph callers (ER, class) working. `_route_edges` similarly gets `direction="TB"` default.

## Resolve-vs-surface disposition record

All open items resolved:
- "rank_gap==0 dead code" → resolved: drop it, confirmed by adversarial review (rank assignment invariant).
- "Variable node height" → resolved: introduce `_node_render_h(n)` helper shared by group box, canvas height, and LR pitch.
- "Arrowhead affects sequence diagrams" → resolved: pass explicit `back/half_w` to lifeline call sites.
- "right_lane_x inside group border at +16" → resolved: use +32 (double GROUP_PAD_X).
- "gen_slides.py" → resolved: out of scope for this spec; add to backlog as separate spec.
