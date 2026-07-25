"""Within-rank node ordering refinement via cost-minimizing permutation (ini-004 spec 4).

Two public functions:
  evaluate_ordering_cost — pure formula; all penalty counts caller-supplied.
  refine_rank_ordering   — finds the best ordering by evaluating permutations
                           (rank ≤ 6) or adjacent transposition (rank > 6).
"""
from __future__ import annotations

import itertools
from collections import deque
from typing import Callable

from mermaid_render.layout.port_planner import generate_port_candidates
from mermaid_render.layout.route_search import route_edge


# ── Public: formula ───────────────────────────────────────────────────────────

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
) -> float:
    return (
        10000 * node_overlap_count
        + 2000 * edge_node_intersection_count
        + 1000 * label_overlap_count
        + 600 * shared_segment_count
        + 300 * edge_crossing_count
        + 80 * bend_count
        + route_length
        - 180 * straight_edge_count
    )


# ── Public: optimizer ─────────────────────────────────────────────────────────

def refine_rank_ordering(
    rank: list[str],
    node_bounds: dict[str, tuple[float, float, float, float]],
    edges: list[dict],
    declared_order: list[tuple[str, str]] = (),
    cost_fn: Callable | None = None,
) -> list[str]:
    """Return the within-rank ordering that minimises cost_fn.

    Permutation search for rank ≤ 6; adjacent transposition for rank > 6.
    Topological seed satisfies all declared pairs before optimisation begins.
    """
    if not rank:
        return []
    if len(rank) == 1:
        return list(rank)

    if cost_fn is None:
        cost_fn = _cheap_cost

    seed = _topological_seed(rank, declared_order)
    in_rank = set(rank)
    declared_pairs = [(a, b) for a, b in declared_order if a in in_rank and b in in_rank]

    if len(rank) <= 6:
        return _permutation_search(seed, node_bounds, edges, declared_pairs, cost_fn)
    return _transposition_search(seed, node_bounds, edges, declared_pairs, cost_fn)


# ── Internals ─────────────────────────────────────────────────────────────────

def _topological_seed(rank: list[str], declared_order: list[tuple[str, str]]) -> list[str]:
    """Return a topological sort of rank satisfying declared_order pairs.

    Uses Kahn's algorithm with tie-breaking by original rank position.
    Raises ValueError if declared_order contains a cycle among rank nodes.
    """
    in_rank = set(rank)
    position = {n: i for i, n in enumerate(rank)}

    # Filter to in-rank pairs only
    pairs = [(a, b) for a, b in declared_order if a in in_rank and b in in_rank]

    in_degree: dict[str, int] = {n: 0 for n in rank}
    successors: dict[str, list[str]] = {n: [] for n in rank}
    for a, b in pairs:
        successors[a].append(b)
        in_degree[b] += 1

    # Priority queue via sorted list (rank is small — linear scan is fine)
    queue = sorted([n for n in rank if in_degree[n] == 0], key=lambda n: position[n])
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for succ in sorted(successors[node], key=lambda n: position[n]):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                # Insert maintaining sorted order by original position
                inserted = False
                for i, q in enumerate(queue):
                    if position[succ] < position[q]:
                        queue.insert(i, succ)
                        inserted = True
                        break
                if not inserted:
                    queue.append(succ)

    if len(result) != len(rank):
        raise ValueError("contradictory declared_order: cycle detected")
    return result


def _satisfies_declared(ordering: list[str], pairs: list[tuple[str, str]]) -> bool:
    pos = {n: i for i, n in enumerate(ordering)}
    return all(pos[a] < pos[b] for a, b in pairs)


def _permutation_search(
    seed: list[str],
    node_bounds: dict[str, tuple[float, float, float, float]],
    edges: list[dict],
    declared_pairs: list[tuple[str, str]],
    cost_fn: Callable,
) -> list[str]:
    best: list[str] | None = None
    best_cost = float("inf")
    for perm in itertools.permutations(seed):
        ordering = list(perm)
        if declared_pairs and not _satisfies_declared(ordering, declared_pairs):
            continue
        c = cost_fn(ordering, node_bounds, edges)
        if c < best_cost:
            best_cost = c
            best = ordering
    return best if best is not None else seed


def _transposition_search(
    seed: list[str],
    node_bounds: dict[str, tuple[float, float, float, float]],
    edges: list[dict],
    declared_pairs: list[tuple[str, str]],
    cost_fn: Callable,
) -> list[str]:
    ordering = list(seed)
    current_cost = cost_fn(ordering, node_bounds, edges)
    rank_size = len(ordering)
    max_passes = 3 * rank_size

    for _ in range(max_passes):
        improved = False
        for i in range(rank_size - 1):
            candidate = ordering[:]
            candidate[i], candidate[i + 1] = candidate[i + 1], candidate[i]
            if declared_pairs and not _satisfies_declared(candidate, declared_pairs):
                continue
            c = cost_fn(candidate, node_bounds, edges)
            if c < current_cost:
                ordering = candidate
                current_cost = c
                improved = True
        if not improved:
            break

    return ordering


def _cheap_cost(
    ordering: list[str],
    node_bounds: dict[str, tuple[float, float, float, float]],
    edges: list[dict],
) -> float:
    """Route-aware default cost: derives bend_count/route_length from route_edge."""
    slot_xs = sorted(node_bounds[n][0] for n in ordering)

    permuted_bounds: dict[str, tuple[float, float, float, float]] = {}
    for i, node_id in enumerate(ordering):
        _x, y, w, h = node_bounds[node_id]
        permuted_bounds[node_id] = (slot_xs[i], y, w, h)

    total_bend = 0
    total_length = 0.0
    straight_count = 0

    for edge in edges:
        edge_id = edge["edge_id"]
        src_id = edge["source_id"]
        dst_id = edge["target_id"]

        src_bounds = permuted_bounds.get(src_id, node_bounds.get(src_id))
        dst_bounds = permuted_bounds.get(dst_id, node_bounds.get(dst_id))
        if src_bounds is None or dst_bounds is None:
            continue

        src_candidates = generate_port_candidates(src_id, src_bounds, edge_id)
        dst_candidates = generate_port_candidates(dst_id, dst_bounds, edge_id)
        if not src_candidates or not dst_candidates:
            continue

        rc = route_edge(edge_id, src_candidates[0], dst_candidates[0])
        if rc is None:
            continue

        total_bend += rc.bend_count
        total_length += rc.length
        if rc.bend_count == 0:
            straight_count += 1

    return evaluate_ordering_cost(
        bend_count=total_bend,
        route_length=total_length,
        straight_edge_count=straight_count,
    )
