# Spec: Routing Node Ordering Refinement

Mode: full (structural — new module `node_ordering.py`; multi-feature initiative item)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** ini-004 Shared Orthogonal Routing Foundation (maputo-v1); no ADR/RFC governs this spec
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Introduce `node_ordering.py` — a geometric ordering refinement module that
takes a ranked node layout and finds the within-rank ordering that minimizes
a cost objective derived from cheap route estimates. When nodes are permuted,
their slot positions (x-coordinates in a horizontal rank) are reassigned
correspondingly, so reordering changes which positions routes traverse and the
cost varies. For ranks with ≤ 6 nodes, all feasible permutations are evaluated; for
larger ranks, deterministic adjacent transposition is used. The module is
standalone — it imports from `port_planner.py` and `route_search.py` only.

No changes to `_pipeline.py` or any diagram-type file in this spec.

## Boundaries

### Always do

- Import from `port_planner.py` and `route_search.py` only.
- Keep all new code in `node_ordering.py`.
- Use the exact cost formula coefficients from the initiative spec.
- Implement the permutation strategy for rank_size ≤ 6 and the adjacent
  transposition strategy for rank_size > 6.
- Derive slot positions from the initial `node_bounds`: sort current x values
  to get the canonical slot centers; assign slot i to the node at position i
  in the candidate ordering (with original w, h).
- Produce deterministic output: identical inputs → identical output.
- Pre-seed orderings to satisfy all declared-order constraints before running
  the cost-minimization loop (topological initialization).

### Ask first

- Any integration into `_pipeline.py` or any diagram-type file.
- Any change to `port_planner.py` or `route_search.py`.

### Never do

- Add a new pip dependency (only stdlib `itertools` and `math`).
- Touch `_routing.py`, `_pipeline.py`, `_geometry.py`, or any diagram-type file.
- Evaluate all permutations for ranks > 6.
- Use non-deterministic ordering (random shuffles, etc.).
- Return a declared-order-violating result when a valid ordering exists.

## Testing Strategy

- **TDD** — all ACs including the import smoke (AC1), cost formula, strategy selection,
  permutation optimality, transposition convergence, declared-order preservation,
  route-aware default cost, and determinism all use red-green-refactor.

## Declined patterns

- Tempted to integrate with `_pipeline.py` — declining: wiring requires full
  FinalizedLayout context; deferred to follow-on work.
- Tempted to accept slot-width as a caller parameter — declining: slot positions
  are derived from current `node_bounds` (the x-values already encode spacing);
  an extra parameter would require caller coordination not justified at this spec level.
- Tempted to add random-restart for large ranks — declining: non-deterministic;
  adjacent transposition is sufficient per spec.

## Assumptions

1. A "rank" is a list of node IDs at the same depth in the layout DAG.
   The current position of each node is given by `node_bounds[node_id] = (x,y,w,h)`.
2. Slot positions: sort current x values of all nodes in the rank to obtain
   `slot_xs`. Candidate ordering `perm[i]` receives bounds
   `(slot_xs[i], original_y, original_w, original_h)`. Cost depends on these
   permuted bounds — so different orderings yield different costs.
3. `route_search.route_edge` is used for cheap per-edge port-and-route estimates
   inside the cost function (builds PortCandidates from permuted bounds, calls
   `route_edge`, reads `bend_count` and `length` from the result).
4. `straight_edge_count` in the formula: the number of edges whose `route_edge`
   result has `bend_count == 0`.
5. The cost formula's coefficients (`straight_edge_count` -180 reward,
   `edge_crossing_count` 300, etc.) come from the initiative brief's
   ROUTE-AWARE NODE ORDERING section and differ from `compute_route_cost`'s
   per-edge objective — they are a ranking-level objective, not a per-edge cost.
6. Declared-order initialization: before running the optimization loop, apply a
   stable topological sort over the declared pairs to produce a valid seed.
   If declared pairs form a cycle (infeasible), raise `ValueError`.
7. Declared-order absent-node pairs (node ID not in rank) are silently ignored.
8. Empty rank returns `[]`. Single-node rank returns `[node_id]` unchanged.
9. Adjacent transposition passes: at most `3 * rank_size` passes, each scanning
   all adjacent pairs. A swap is accepted only if it reduces cost AND doesn't
   violate any declared pair. Cache current ordering cost across pairs.
10. Python 3.13 runtime.

## Resolve-vs-surface disposition record

Opened at PLAN. Closed at DECIDE.

| Question | Resolution |
|---|---|
| How do node positions vary with ordering? | Slot-derived: sort current x values; assign by index. |
| Should _cheap_cost use route_edge or zero costs? | route_edge — otherwise the optimizer has no signal. |
| Infeasible declared pairs: crash or silent? | Raise ValueError (explicit error, AC5b). |
| Threshold configurable? | Hardcoded 6; per the initiative brief. |
| Should adjacent-transposition be seeded with valid declared-order? | Yes — topological initialization before the loop (Assumption 6). |

## Acceptance Criteria

- [x] AC1: `evaluate_ordering_cost` and `refine_rank_ordering` are importable
  from `scripts.mermaid_render.layout.node_ordering` (verified by a pytest import test).
- [x] AC2: The ordering cost formula is:

  ```
  cost = 10000 * node_overlap_count
       + 2000  * edge_node_intersection_count
       + 1000  * label_overlap_count
       + 600   * shared_segment_count
       + 300   * edge_crossing_count
       + 80    * bend_count
       + route_length
       - 180   * straight_edge_count
  ```

  `evaluate_ordering_cost` accepts only keyword arguments (no positional params);
  it is a pure formula — caller supplies all counts.
  Verification: all penalty counts zero, `route_length=10.0`,
  `straight_edge_count=1` → `10.0 - 180.0 = -170.0`.

- [x] AC3: `refine_rank_ordering` with `rank_size ≤ 6` evaluates all feasible
  permutations (verified by passing a `cost_fn` that counts calls; expected call
  count equals the number of feasible orderings — `rank_size!` when no declared
  pair constrains the rank).
- [x] AC4: `refine_rank_ordering` with `rank_size > 6` uses adjacent
  transposition; the total number of `cost_fn` invocations is at most
  `3 * rank_size * (rank_size - 1) + 1` (the `+1` is the initial cost of the
  seed ordering, cached once). Verified by injecting a counting `cost_fn`.
- [x] AC5a: `refine_rank_ordering` with declared-order pairs returns an ordering
  where every declared pair `(a, b)` satisfies `a` before `b`.
- [x] AC5b: `refine_rank_ordering` with contradictory declared pairs (a cycle)
  raises `ValueError`.
- [x] AC6: `refine_rank_ordering` called twice with identical inputs returns the
  same ordering (determinism).
- [x] AC7: `refine_rank_ordering` for a rank of one node returns `[that_node]`.
  For an empty rank, returns `[]`.
- [x] AC8: All existing `pytest tests/ -x -q` tests pass (no regressions).
- [x] AC9: `refine_rank_ordering` with no `cost_fn` uses a route-aware default.
  Verification: a 2-node rank `[A, B]` where A and B occupy distinct x-positions
  (e.g. A at x=50, B at x=150), with two edges — `A→ExtLeft` (external node at x≈0)
  and `B→ExtRight` (external node at x≈200) — where the two orderings produce routes
  of different total length; `refine_rank_ordering([A, B], ...)` returns the ordering
  with the shorter total route length (not a constant).
