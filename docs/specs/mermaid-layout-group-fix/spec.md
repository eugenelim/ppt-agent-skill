# Spec: mermaid-layout-group-fix

**Mode:** full (multi-feature: layout correctness + renderer fix; structural: new exported function `_separate_groups_tb`)
**Status:** Implementing
**Owner:** eugenelim
**Plan:** [`plan.md`](plan.md)
**Constrained by:** `docs/CONVENTIONS.md`, `docs/specs/mermaid-layout-package-split/spec.md` (no symbol renames, no new deps)
**Reference:** xai-org/grok-build mermaid-to-svg (Rust+dagre) — key insight: dagre is cluster-aware at every layout stage; our barycenter isn't. We adopt its key behaviours (group column separation, canvas sizing from actual node heights) without porting the full algorithm.

## Objective

Fix four confirmed layout correctness bugs in `scripts/mermaid_layout/`:

1. **Group X/Y overlap (TB mode)**: After coordinate assignment, groups with overlapping column ranges (different subgraphs, same columns) get group borders that overlap — sometimes one group's box visually contains nodes from another group. Happens because the barycenter assigns columns globally without respecting subgraph membership.

2. **Non-member node intrusion**: Standalone nodes (not in any subgraph) get positioned within a group's padded bounding box, making them appear to be members of that group.

3. **Canvas height underestimation (TB mode)**: `_assign_coordinates` computes `canvas_h` using fixed `NODE_H` but nodes can be taller (icon + multi-line label + tech sub-label = up to ~140px vs NODE_H=56). The last-rank group border overflows the canvas by up to 88px on tall decks.

4. **Group bbox non-member intrusion in renderer**: `_render_graph_fragment` draws group bounding boxes from padded node positions without checking for adjacent non-member nodes, so overlapping groups and intruding standalone nodes render incorrectly.

Reference comparison:
- dagre `SUBGRAPH_PADDING = 8px` (ours: 24/32px — intentionally larger for PPT card labels)
- dagre `NODE_SEP = 50px`, `RANK_SEP = 50px` (ours: COL_GAP=48, RANK_GAP=72 — larger for PPT cards)
- dagre cluster-aware layout (ours: global barycenter, cluster-unaware)

## Acceptance Criteria

- **AC-1 (TDD)** `_separate_groups_tb(nodes, groups)` exists and is exported from `mermaid_layout`. For a TB diagram with two groups whose barycenter-assigned column ranges overlap AND whose Y ranges also overlap, calling `_separate_groups_tb` shifts the right-er group's node X positions so the groups' padded bboxes no longer overlap in X. Canvas_w is updated to fit.
- **AC-2 (TDD)** `_assign_coordinates(nodes, "TB")` returns a `canvas_h` such that for every node n: `n.y + _node_render_h(n) + CANVAS_PAD <= canvas_h`. Currently fails for nodes with icon + tech sub-label at the max rank.
- **AC-3 (TDD)** `_compute_group_bboxes(nodes, groups, canvas_w, canvas_h)` (new, exported) resolves overlap: for any pair of groups whose initial padded bboxes overlap in both axes, the returned bboxes do not overlap. Also clips each bbox to `[0, canvas_w] × [0, canvas_h]`.
- **AC-4 (TDD)** `_compute_group_bboxes` non-member exclusion: for a standalone node (not in any group) whose position falls within a group's initial padded bbox, the returned bbox for that group shrinks to exclude the standalone node (gap ≥ 4px between group edge and non-member node edge).
- **AC-5 (goal-based)** `_render_graph_fragment` uses `_compute_group_bboxes` for all group divs (verified by diff).
- **AC-6 (unit)** All 120 existing `tests/test_mermaid_layout.py` tests still pass. No test regressions.
- **AC-7 (unit)** All new TDD tests pass (written RED first, then GREEN).
- **AC-8 (smoke)** `python3 scripts/smoke_test.py --phase 2` → 39/39 pass.

## Boundaries

**Always do:**
- Write RED tests before implementing each fix (strict TDD)
- Export `_compute_group_bboxes` and `_separate_groups_tb` from `__init__.py`
- Keep all symbol names unchanged (no renames)
- No new pip dependencies

**Never do:**
- Change any public function signature (add optional params only, never remove)
- Move `tests/test_mermaid_layout.py`
- Introduce behaviour changes outside TB mode group layout and canvas sizing

**Ask first:**
- Changing `CANVAS_PAD`, `COL_GAP`, `RANK_GAP`, `GROUP_PAD_*` constants (layout geometry — separate tuning decision)
- Any change to LR mode layout (existing `_separate_groups_lr` coverage; risk of regression)

## Declined patterns

- _Tempted to port the full dagre Sugiyama algorithm — declining; 3,000-line Rust port for 4 targeted bugs is gross overkill. We adopt dagre's group-separation principle via post-coordinate passes, not its full internals._
- _Tempted to make node sizes text-measured (variable WIDTH) — declining; the fixed-width card design (NODE_W=160) is intentional and tested by 120 tests. HEIGHT should vary (already does via `_node_render_h`); WIDTH stays fixed._
- _Tempted to reduce CANVAS_PAD, COL_GAP, GROUP_PAD constants during this fix — declining; those are separate tuning decisions; this spec is correctness-only._
- _Tempted to add visual LLM review loop to this PR — declining; separate spec, separate concern._

## Testing Strategy

TDD (write failing test, implement, make it pass):

- **T1**: `test_tb_canvas_height_accommodates_tall_last_rank_node` — `_assign_coordinates` with a two-rank graph where rank-1 node has icon + tech sub-label; assert `ch >= node_bottom + CANVAS_PAD`. **RED before AC-2 fix.**
- **T2**: `test_compute_group_bboxes_no_overlap` — two groups whose raw padded bboxes overlap in both X and Y; assert returned bboxes don't overlap. **RED before AC-3 fix.**
- **T3**: `test_compute_group_bboxes_clips_to_canvas` — a group whose padded bbox extends below canvas_h=200; assert returned y1 ≤ 200. **RED before AC-3 fix (clipping part).**
- **T4**: `test_compute_group_bboxes_excludes_nonmember` — a standalone node at position inside a group's padded bbox; assert returned group bbox right edge ≤ nonmember_left - 4. **RED before AC-4 fix.**
- **T5**: `test_separate_groups_tb_resolves_x_overlap` — two groups at same rank (Y-overlapping) with manually forced overlapping X positions; assert after `_separate_groups_tb`, groups' padded X bboxes don't overlap. **RED before AC-1 fix.**
- **T6**: `test_separate_groups_tb_noop_for_nonoverlapping` — two groups at different Y levels (one at rank 0, one at rank 2, with 144px Y gap); assert `_separate_groups_tb` does not shift any node. **Verifies no spurious separations.**

## Resolve-vs-surface disposition

| Item | Resolution |
|------|-----------|
| Full dagre port | Resolved: post-coordinate separation passes achieve the same visual result for our fixed-width cards |
| LR mode regressions | Resolved: AC-8 smoke + AC-6 unit cover existing LR tests; boundary rule excludes LR changes |
| CANVAS_PAD adjustment | Surfaced: separate tuning decision, not in this spec |
| Visual LLM review | Surfaced: separate spec |
