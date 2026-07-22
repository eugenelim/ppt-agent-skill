# P0 Layout Geometry Fixes

**Status:** Shipped
**Mode:** full (multi-feature + dependent tasks; _Node dataclass + HTML structure change)

## Objective

Fix the six geometry defects in `scripts/mermaid_render/layout/` that cause text
clipping, oversized column widths, and inaccurate shape sizing — without replacing
the layout engine (P1) or adding new external dependencies.

Source analysis: `.context/attachments/TTRgsS/pasted_text_2026-07-20_17-16-08.txt`

## Boundaries

**In scope:** `scripts/mermaid_render/layout/` — `_constants.py`, `_layout.py`,
`_routing.py`, `_renderer.py`. Tests in `tests/test_mermaid_layout.py`,
`tests/test_syntax_flowchart.py`, `tests/test_render_correctness.py`.

**Out of scope:** P1 (Dagre/ELK integration), P2 (edge-routing engine outputs),
P3 (geometry assertion tests), `mermaid_layout/` shim (reads from `mermaid_render`),
self-loop lane allocation, faithful-mermaid mode separation, trapezoid/flag/cylinder
dynamic sizing.

## Acceptance Criteria

- [x] AC-1 **Font measurement**: `_measure_text_px()` and `_wrap_label()` both use
  15 px / weight 700, matching `var(--node-fs-title,15px)` emitted by `_renderer.py`.
  All nodes (including icon nodes) use 15 px / weight 700 in `_assign_coordinates()`
  width computation; this slight overestimate for icon nodes (which render at 14 px
  via CSS) prevents text clipping. Named constants `_TITLE_FS=15`, `_TITLE_FW=700`,
  `_ICON_FS=14` avoid re-introducing numeric drift; `_ICON_FS` is a CSS-documentation
  constant and is not used in layout width computation.
- [x] AC-2 **NODE_MAX_W cap**: a new `NODE_MAX_W = 220` constant exists; `n.width`
  never exceeds it for text-box shapes (rect, round, stadium, subroutine, cylinder)
  in `_assign_coordinates()`. Circle and hexagon use their own size formula and are
  not capped by NODE_MAX_W.
- [x] AC-3 **`_Node.height` populated**: after `_assign_coordinates()` returns, every
  non-dummy node has `n.height > 0`.
- [x] AC-4 **Dynamic circle and hexagon sizing**: a regular `((circle))` node with a
  label wider than 80 px gets a diameter larger than `_CIRCLE_NODE_SIZE`; short-label
  circles (≥ 3 chars, non-terminal) remain at `_CIRCLE_NODE_SIZE`. Hexagon uses the
  same growth formula as diamond.
- [x] AC-5 **Dynamic diamond sizing**: a `{diamond}` node with a label requiring
  more than 100 px diagonal gets a side larger than `_DIAMOND_SIZE`; short-label
  diamonds remain at `_DIAMOND_SIZE`.
- [x] AC-6 **Polygon separation**: for diamond, hexagon, trapezoid, trapezoid-alt,
  and flag shapes, the `clip-path` CSS is on a background div (not the label
  container). The text container uses `overflow:visible`. `box-shadow` is placed on
  the clipped background div so the drop shadow follows the polygon outline. Verified
  for all five shapes.
- [x] AC-7 **Per-column widths (TB)**: each column's x-pitch uses only the maximum
  width of nodes in that column, not the global diagram maximum. A narrow-column
  node's `x` coordinate reflects the narrow column's pitch, not the widest column's.
- [x] AC-8 **Per-rank widths (LR)**: when a narrow rank precedes a wide rank, the
  wide rank node's `x` equals `CANVAS_PAD + narrow_rank_width + RANK_GAP`, not
  `CANVAS_PAD + global_max_width + RANK_GAP`.
- [x] AC-9 **Router uses `n.width`/`n.height`**: `_node_render_w()` in `_routing.py`
  returns `n.width` for shapes that now have dynamic sizing (circle, diamond, hexagon).
  `_node_render_h()` returns a height consistent with the dynamic `n.width` for those
  shapes (equivalent to what `_node_render_h(n)` computes using `n.width`).
- [x] AC-10 **Tests updated and passing**: circle/diamond size assertions in
  `test_syntax_flowchart.py` updated to match dynamic sizing. No regressions in
  `test_mermaid_layout.py`. `test_render_correctness.py` has no coordinate-baseline
  assertions; per-column/per-rank changes did not require any updates there.

## Testing Strategy

**Verification mode:** TDD for geometry logic; structural HTML check for polygon
separation (visual un-clipping is out of scope per Assumption 4).

Construction tests (written in `plan.md` before EXECUTE):
- `_measure_text_px("Decision")` returns a value consistent with 15px/700 (>13px/500
  result).
- An icon node measures narrower than the same label without an icon (14 vs 15 px).
- A text-box node with a 300-char label gets `n.width ≤ NODE_MAX_W`.
- After `_assign_coordinates()`, a non-dummy node has `n.height > 0`.
- `((Cat))` (short, non-terminal circle) renders at exactly `_CIRCLE_NODE_SIZE`.
- `((A Long Circle Label That Exceeds Default))` renders with `width > _CIRCLE_NODE_SIZE`.
- `{A Very Long Decision Label}` renders with diamond width > `_DIAMOND_SIZE`.
- All five polygon shapes have `clip-path` on a background div, not the outer container.
- TB: narrow column's node x is left of where global-max pitch would place it.
- LR: wide-rank node x equals `CANVAS_PAD + narrow_rank_width + RANK_GAP` (not
  `CANVAS_PAD + global_max_width + RANK_GAP`).

## Assumptions

1. `_measure_text_width()` is accurate enough at 15px/700; browser CanvasRenderingContext2D
   is not invoked (complexity/latency budget for Python-only rendering).
2. Dynamic hexagon sizing uses the same linear content-sum formula as diamond for P0
   (`content_w + content_h + NODE_HPAD`; not a hypot/diagonal). Binary-search approach is P1.
3. Trapezoids, flags, cylinders keep fixed sizing for P0 (label typically fits). With the
   polygon-separation change (AC-6), `overflow:visible` on the text div means a long
   label spills outside the polygon boundary instead of being clipped. This is a
   known trade-off; fixing it requires per-shape overflow policy (P1).
4. The test suite covers the golden path; visual QA of actual rendered output is out of scope
   for this automation pass. Task 5 verifies structural rearrangement of HTML, not pixel-level
   clipping.
5. Terminal-circle `_circ_shift` in `_strategies.py` uses the global max node width, not the
   per-column width. For typical state diagrams (single real-node column in TB layout) the
   result is equivalent to using the column width. Multi-column diagrams with terminal circles
   in a narrower column may show a slight horizontal jog; fixing this is P1.

## Declined patterns

- **ELK/Dagre integration**: out of scope for P0; addressed by P1 spec.
- **Browser-backed measurement via Playwright**: adds async complexity; 15/700 heuristic is
  sufficient for measurable improvement.
- **Dynamic trapezoid/flag sizing**: binary-search over slanted polygon is complex; deferred.
- **`faithful_mermaid` mode flag**: new option with no second caller yet; deferred.
- **NODE_MAX_W cap on circle/diamond**: their growth formula has a natural bound (hypot of
  label text); capping would re-introduce clipping on long labels.
