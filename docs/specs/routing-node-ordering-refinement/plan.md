# Plan: Routing Node Ordering Refinement

- **Spec:** [`spec.md`](spec.md)
- **Status:** Shipped

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially,
> note why in the changelog at the bottom.

## Approach

Introduce `scripts/mermaid_render/layout/node_ordering.py` with two public
functions: `evaluate_ordering_cost` (the pure formula) and `refine_rank_ordering`
(the optimizer). The riskiest part is (a) making the cost actually vary with
ordering via slot-position reassignment, (b) declared-order preservation under
both strategies, and (c) the topological seed before optimization begins. All
tests use red-green-refactor.

## Constraints

- `evaluate_ordering_cost` must use exact coefficients (AC2).
- Permutation strategy only for rank_size ≤ 6 (AC3/AC4).
- Adjacent transposition capped at `3 * rank_size` passes (Assumption 9).
- No new pip dependencies (only `itertools` from stdlib).
- Declared-order constraint enforced by topological seed + per-swap check (AC5a/b).
- `_cheap_cost` must use `route_edge`; passing zeros is not acceptable (Spec Assumption 3).

## Construction tests

**Integration tests:** T3's `test_refine_declared_order_preserved` exercises
both permutation and transposition with declared-order constraints.

## Design (LLD)

### Slot-position reassignment

The optimizer cannot compare orderings unless node positions depend on the
ordering. Before scoring any candidate ordering `perm`:

1. Compute `slot_xs = sorted(node_bounds[n][0] for n in rank)`.
   These are the canonical x-positions of the rank slots in left-to-right order.
2. For each index `i`, node `perm[i]` is assigned x = `slot_xs[i]`.
   Its y, w, h come unchanged from `node_bounds[perm[i]]`.
3. The resulting `permuted_bounds` dict is what the cost function scores.

### Topological initialization (declared-order seed)

Before the permutation or transposition loop begins, sort the rank into a
valid declared-order seed:

1. Filter declared pairs to those where both nodes are in the rank.
2. Build a dependency graph: `(a, b)` means a must come before b.
3. Run Kahn's algorithm (stable topological sort): nodes with no in-edges go
   first; break ties using the current position in the input rank.
4. If Kahn detects a cycle (queue empties before all nodes are placed), raise
   `ValueError("contradictory declared_order: cycle detected")`.
5. The result is the seed ordering for both strategies.

### `_cheap_cost(ordering, node_bounds, edges) -> float`

This is the default `cost_fn`. It derives actual route metrics so different
orderings score differently:

1. Build `permuted_bounds` as above.
2. For each edge `{"edge_id", "source_id", "target_id"}`:
   a. Call `generate_port_candidates(src_id, permuted_bounds.get(src_id, node_bounds[src_id]), edge_id)`.
      Take the first candidate (`PortCandidate`); if none, skip edge.
   b. Do the same for `dst_id`.
   c. Call `route_edge(edge_id, src_candidate, dst_candidate)`.
      (Pass `PortCandidate` objects directly — `route_edge` takes `PortCandidate`, not `PortReservation`.)
      If result is None, skip.
   d. Accumulate: `total_bend += rc.bend_count`, `total_length += rc.length`,
      `straight_count += (1 if rc.bend_count == 0 else 0)`.
3. Return `evaluate_ordering_cost(
   bend_count=total_bend, route_length=total_length, straight_edge_count=straight_count)`.
   All other penalty counts default to 0 (geometric penalties are caller's
   responsibility when using the full cost function).

### Interfaces & contracts

```python
def evaluate_ordering_cost(
    *,
    node_overlap_count: int = 0,
    edge_node_intersection_count: int = 0,
    label_overlap_count: int = 0,
    shared_segment_count: int = 0,
    edge_crossing_count: int = 0,
    bend_count: int = 0,
    route_length: float = 0.0,
    straight_edge_count: int = 0,
) -> float
# Pure formula — keyword-only args only; caller supplies all penalty counts.
# No positional params: no geometry is computed inside this function.

def refine_rank_ordering(
    rank: list[str],                   # node IDs, initial ordering
    node_bounds: dict[str, tuple[float, float, float, float]],
    edges: list[dict],
    declared_order: list[tuple[str, str]] = (),  # [(a, b), ...] a must precede b
    cost_fn: Callable | None = None,   # defaults to _cheap_cost
) -> list[str]
# Returns the best ordering found.
# cost_fn signature: (ordering: list[str], node_bounds: dict, edges: list) -> float.
```

### Behavior & rules

- `evaluate_ordering_cost`: pure formula; keyword-only args only; no positional params.
- `refine_rank_ordering`: returns `[]` for empty rank; `[rank[0]]` for single node.
- Topological initialization runs unconditionally (declared pairs filter to in-rank
  pairs; if no in-rank declared pairs, stable topological sort = original order).
- Permutation (rank_size ≤ 6): generate all n! orderings from the seed (all permutations
  of the seeded list); filter to orderings satisfying all declared pairs; score each with
  cost_fn; return the minimum-cost ordering (tie-break: first encountered).
- Adjacent transposition (rank_size > 6): score seed with cost_fn (1 invocation);
  for each pass (max `3 * rank_size` passes), scan all adjacent pairs `(i, i+1)`;
  for each pair, compute cost of the swapped ordering (1 invocation); accept swap if
  cost decreases AND the swap doesn't violate any declared pair; after a full pass with
  no swaps, stop early. Do NOT re-score accepted swaps mid-pass; carry the current
  ordering and its last scored cost forward.
- Declared-pair check: for pair `(a, b)`, the ordering is valid iff
  `ordering.index(a) < ordering.index(b)`.
- Declared pairs referencing absent nodes are silently ignored (Assumption 7).

## Tasks

### T1: Importable module + cost formula (AC1, AC2) — stub: true

**Depends on:** none

**Tests:**
- `test_import_smoke` (AC1): both `evaluate_ordering_cost` and `refine_rank_ordering` importable.
- `test_evaluate_ordering_cost_simple` (AC2): `route_length=10.0, straight_edge_count=1`,
  all other counts zero → `evaluate_ordering_cost(route_length=10.0, straight_edge_count=1) == -170.0`.
- `test_evaluate_ordering_cost_all_penalties` (AC2): each coefficient independently verified
  (8 separate terms); all kwargs, no positional args.

**Approach:**
- Create `node_ordering.py`; implement `evaluate_ordering_cost` with exact formula.
- Stub `refine_rank_ordering` as `raise NotImplementedError`.

**Done when:** import + two cost tests pass.

### T2: Topological seed + permutation strategy (AC3, AC5a/b, AC6, AC7) — stub: true

**Depends on:** T1

**Tests:**
- `test_refine_empty_rank` (AC7): `rank=[]` → `[]`.
- `test_refine_single_node` (AC7): `rank=["A"]` → `["A"]`.
- `test_refine_permutation_selects_minimum` (AC3): 3-node rank with a cost_fn
  that prefers a specific ordering; verify that ordering is returned.
- `test_refine_permutation_invocation_count` (AC3): 3-node rank, no declared
  constraints; inject counting cost_fn; expect exactly 6 (3!) invocations.
- `test_refine_declared_order_permutation` (AC5a): with declared pair `(A, B)`,
  returned ordering has A before B.
- `test_refine_cycle_raises` (AC5b): declared pairs form a cycle →
  `ValueError` raised.
- `test_refine_deterministic_permutation` (AC6): two calls same input → same output.

**Approach:**
- Implement `_topological_seed(rank, declared_pairs) -> list[str]` using Kahn's algorithm.
- Implement `refine_rank_ordering` for rank_size ≤ 6: apply seed, enumerate all
  permutations, filter infeasible, score, return min.

**Done when:** seven permutation/seed tests pass.

### T3: Adjacent transposition strategy (AC4, AC5a, AC6) — stub: true

**Depends on:** T1, T2

**Tests:**
- `test_refine_uses_transposition_for_large_rank` (AC4): 7-node rank (size > 6);
  inject counting cost_fn; total invocations ≤ `3 * 7 * 6 + 1 = 127`.
- `test_refine_transposition_improves_cost` (AC4): 7-node rank with a cost_fn
  that penalizes a specific pair being adjacent; verify result avoids that adjacency.
- `test_refine_declared_order_transposition` (AC5a): 7-node rank; declared pair
  preserved under transposition (no swap violates the pair).
- `test_refine_deterministic_transposition` (AC6): two calls same input → same output.

**Approach:**
- Extend `refine_rank_ordering` for rank_size > 6: after topological seed, run
  adjacent transposition passes up to `3 * rank_size`; accept swap only if
  cost decreases AND declared pairs are satisfied.

**Done when:** four transposition tests pass.

### T4: Default cost function (_cheap_cost) and AC9 (AC9) — stub: true

**Depends on:** T1 (evaluate_ordering_cost), external (port_planner, route_search)

**Tests:**
- `test_cheap_cost_varies_with_ordering` (AC9): a 2-node rank `[A, B]` where A
  and B occupy *distinct* x-positions (e.g. A at x=50, B at x=150, both same y/w/h),
  with two edges each going to a *distinct* external node at different x-positions
  (edge 1: A→ExtLeft at x=0, edge 2: B→ExtRight at x=200). `_cheap_cost([A, B], ...)`
  must return a different value from `_cheap_cost([B, A], ...)`, confirming slot
  positions vary with ordering and route_edge is actually called.
- `test_refine_route_aware_default` (AC9): `refine_rank_ordering` with the same fixture
  and no `cost_fn` returns the ordering with shorter total route length.

**Approach:**
- Implement `_cheap_cost` as described in Design: sort slot_xs, build permuted_bounds,
  call generate_port_candidates + route_edge per edge, accumulate metrics, call
  evaluate_ordering_cost.

**Done when:** `test_cheap_cost_varies_with_ordering` passes.

### T5: Regression pass (AC8)

**Depends on:** T1-T4

**Tests:**
- `pytest tests/ -x -q` → full suite green.

**Done when:** 0 failures.

## Rollout

No infra or external-system changes. Pure Python, no new dependencies
(only stdlib `itertools`).

## Risks

- Permutation strategy is O(n!) for n ≤ 6 — 720 evaluations max; acceptable.
- Adjacent transposition may not reach the global optimum for non-convex cost
  functions; acceptable per spec.
- `_cheap_cost` calls `route_edge` per edge per candidate ordering; for n=6 that is
  720 × |edges| route evaluations — acceptable for typical rank sizes.

## Changelog

- 2026-07-24: initial plan
- 2026-07-24: rewrite (post-adversarial-review): added slot-position reassignment,
  topological seed, and _cheap_cost via route_edge to fix three blockers
- 2026-07-24: second adversarial-review pass: dropped positional params from
  evaluate_ordering_cost (keyword-only), added AC9 for route-aware default,
  unified AC1 into TDD, fixed step lettering, specified T4 fixture edge topology
