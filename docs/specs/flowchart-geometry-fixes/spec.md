# Flowchart Geometry Fixes — spec

Mode: full (multi-feature, dependent tasks; structural changes to `_constants.py`, `_layout.py`, `_routing.py`, `_renderer.py`, `_strategies.py`; new module `_geometry.py`)
- **Status:** Shipped

## Objective

Fix 11 geometry bugs and 6 box-model warnings identified in the adversarial review of the flowchart renderer. The bugs cause: canvas overflow, groups outside the canvas, overlapping group titles, edge labels covering unrelated nodes, self-loops competing with forward edges in LR mode, and incorrect polygon/circle sizing for multi-line content.

## Background

Adversarial review (commit 16737b8 baseline) identified that `ours_ok=True` in the gallery is a crash-only gate that hides intrinsic geometry errors. The gallery's iframe+zoom hides overflow by scaling broken geometry to fit. The seven structural errors and six box-model warnings survive because the test suite checks CSS classes and path existence, not pixel containment.

## Acceptance Criteria

- [x] **AC-1 (text-measurement bug)** Long-token wrap loop uses `_TITLE_FS`/`_TITLE_FW` font constants, not hard-coded `13, 500`. Test: `_wrap_label` on a 200-char token produces lines measurable at `_TITLE_FS`/`_TITLE_FW` that each fit within the budget.
- [x] **AC-2 (diamond sizing)** Diamond size uses `ceil(content_w + content_h + h_padding + v_padding/2)`, not the shared diamond/hexagon formula. Test: diamond node with 3-line label has `n.width >= content_w + content_h`.
- [x] **AC-3 (hexagon sizing)** Hexagon width and height are independent: `height = max(HEX_MIN_H, ceil(content_h + v_padding))`, `width = max(HEX_MIN_W, ceil(content_w + h_padding + 2*shoulder))`. `_node_render_h(hexagon_node)` returns `n.height`. Tests: hexagon with tall content has `n.height > n.width` when content is tall; hexagon `n.width != n.height` for non-square content.
- [x] **AC-4 (circle multiline)** Circle/doublecircle diameter is computed as `hypot(max_line_w + h_pad, n_lines * line_h + v_pad)` over all lines. Doublecircle adds ring clearance (`DOUBLE_CIRCLE_RING = 8`). Test: circle with 3-line label has larger diameter than same node with 1 line; doublecircle diameter > circle diameter for same label.
- [x] **AC-5 (geometry IR)** `_geometry.py` exports `Rect` frozen dataclass with `contains(other: Rect) -> bool`, `overlaps(other: Rect) -> bool`, `union(other: Rect) -> Rect`, `translate(dx, dy) -> Rect` helpers. `GroupLayout`, `RoutedEdge`, `FinalizedLayout` are deferred to the full IR sprint. Tests: all four `Rect` helpers verified with numeric assertions.
- [x] **AC-6 (nested group y-shift)** `_compute_group_bboxes` applies a y-shift when `min(b[1] for b in bboxes.values()) < 0`, translating both bboxes and member nodes downward — analogous to the existing x-shift for negative x. Canvas height after the function includes `max(b[3]) + CANVAS_PAD`. Tests: deep-nesting fixture group bboxes all have `y1 >= 0`; canvas_h >= max group bottom.
- [x] **AC-7 (canvas width includes groups)** `_render_graph_fragment` expands `canvas_w` to include `max(b[2])` for all group bboxes (the x-shift in `_compute_group_bboxes` may widen groups beyond current node-only canvas). Test: rendered `width:` in HTML >= max group right edge.
- [x] **AC-8 (direction-aware self-loops)** `_routing.py` constants `BASE_LOOP_EXTENT = 32`, `LOOP_LANE_GAP = 20`, `LABEL_PAD = 6` added to `_constants.py`. Self-loops in TB/TD: `side_order = ("right", "left")`; in LR/RL: `side_order = ("top", "bottom")`. Each loop index uses `side = side_order[idx % 2]`, `lane = idx // 2`; extent = `max(BASE_LOOP_EXTENT, label_w + 2*LABEL_PAD, 0.35*max(nw,nh)) + lane*LOOP_LANE_GAP`. Canvas expanded if loop extends past current edges. Tests: LR self-loop path uses top/bottom face (y-coord outside node, x-coord within node bounds); TB self-loop path uses right/left face; 4 loops on one node produce 4 non-overlapping paths.
- [x] **AC-9 (A* group title obstacles)** Group title bboxes `(x0, y0, x1, y0+GROUP_PAD_Y_TOP)` added to `_routing_obs` list so `_blocked_segs` blocks routing paths through title strips. Tests: `_blocked_segs` with a group-title obstacle blocks the segment passing through it; clear segment is not blocked.
- [x] **AC-10 (edge label hard-reject on node overlap)** `_best_label_pos` applies a hard skip (score = infinity) when a candidate chip bbox has nonzero intersection area with any node obstacle (not just soft penalty). Falls back to the original midpoint if all candidates are blocked. Tests: when all candidates overlap a node, best position is the fallback; when one candidate is clear, that candidate is chosen.
- [x] **AC-11 (RenderOptions)** `@dataclass(frozen=True) class RenderOptions` in `_strategies.py` with fields `faithful_mermaid=False, infer_icons=True, auto_direction=True, inferred_legend=True`. `_dispatch` accepts `opts: RenderOptions | None = None`; defaults to `RenderOptions()`. When `faithful_mermaid=True`: icon inference skipped, direction auto-select skipped, legend not injected. Tests: `_dispatch` with `faithful_mermaid=True` on LR flowchart: (a) declared direction preserved when width/height hints would otherwise auto-switch; (b) `n.icon` not set for nodes whose labels match icon keywords; (c) legend strip absent from output.
- [x] **AC-12 (gallery three-state)** `scripts/compare_gallery.py` gains `_classify_status(render_exception, geometry_errors, geometry_warnings) -> Literal["error", "invalid", "warning", "ok"]`. Tests: returns `"error"` when `render_exception` is set; `"invalid"` when `geometry_errors=True, geometry_warnings=False`; `"warning"` when `geometry_errors=False, geometry_warnings=True`; `"ok"` when both False and no exception.
- [x] **AC-13 (CSS box-model)** Overlay SVGs for subroutine and cylinder use `width` and `height` attributes equal to the node's actual pixel dimensions (not `42`). Test: a subroutine node rendered to HTML has `width="{n.width}"` in its overlay SVG; likewise for cylinder. Node width used is the one computed by `_node_size_*` / `_assign_coordinates`.
- [x] **AC-14 (all existing tests pass)** `python -m pytest tests/ -x` green throughout.

## Boundaries

**In scope:**
- `scripts/mermaid_render/layout/_constants.py` — text measurement bug, shape sizing
- `scripts/mermaid_render/layout/_layout.py` — call sites for new shape sizing functions
- New `scripts/mermaid_render/layout/_geometry.py` — Rect IR
- `scripts/mermaid_render/layout/_routing.py` — direction-aware self-loops, group title obstacles, label collision
- `scripts/mermaid_render/layout/_renderer.py` — nested group y-shift, canvas bounds, CSS fixes
- `scripts/mermaid_render/layout/_strategies.py` — RenderOptions
- `scripts/compare_gallery.py` — three-state status
- New `tests/test_flowchart_geometry.py` — all new TDD tests
- New `tests/validate_compare_gallery.py` — geometry validator helper

**Not in scope:**
- Full immutable LayoutResult refactor (deferred to a future architectural sprint)
- Renderer serialization-only (requires full LayoutResult; deferred)
- Bottom-up compound group layout as a pipeline stage (deferred)
- Playwright browser geometry tests (deferred)
- Dagre/ELK integration (deferred)
- Cylinder cap clearance formula (complex shape with fixed SVG overlay; deferred)
- Trapezoid/flag independent shoulder width (minor, deferred)

## Declined patterns

- **Full LayoutResult IR threaded through pipeline**: the full frozen `FinalizedLayout` IR would require changes to every test that calls `_render_graph_fragment`. Deferring to a dedicated architectural sprint.
- **`_node_size_cylinder` formula**: cylinder uses a fixed SVG overlay that's harder to change without visual regression; left as a separate item.
- **New `quality-engineer` agent pass**: scope is clear; adversarial pass is sufficient for this fix sprint.

## Testing strategy

All new behavior covered by `tests/test_flowchart_geometry.py`. Red stubs first, then implementation. Existing tests must stay green throughout.

## Assumptions

- `mermaid_layout` is a shim; only `mermaid_render/layout/` needs changes.
- `_node_render_h` is the single source of truth for height; it will return `n.height` for hexagon after AC-3 is implemented.
- `RenderOptions` is backward-compatible (default instance matches current behavior).
