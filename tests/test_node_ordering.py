"""Tests for node_ordering.py (ini-004 spec 4).

Coverage: AC1-AC9 per docs/specs/routing-node-ordering-refinement/spec.md.
"""
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.node_ordering import (
    evaluate_ordering_cost,
    refine_rank_ordering,
    _cheap_cost,
)


# ── T1: AC1 import smoke ──────────────────────────────────────────────────────

def test_import_smoke():
    # Both names importable (AC1)
    assert callable(evaluate_ordering_cost)
    assert callable(refine_rank_ordering)


# ── T1: AC2 cost formula ──────────────────────────────────────────────────────

def test_evaluate_ordering_cost_simple():
    # route_length=10, straight_edge_count=1, all others zero → -170.0
    result = evaluate_ordering_cost(route_length=10.0, straight_edge_count=1)
    assert result == pytest.approx(-170.0)


def test_evaluate_ordering_cost_zero():
    assert evaluate_ordering_cost() == pytest.approx(0.0)


def test_evaluate_ordering_cost_all_penalties():
    # Each coefficient independently correct
    assert evaluate_ordering_cost(node_overlap_count=1) == pytest.approx(10000.0)
    assert evaluate_ordering_cost(edge_node_intersection_count=1) == pytest.approx(2000.0)
    assert evaluate_ordering_cost(label_overlap_count=1) == pytest.approx(1000.0)
    assert evaluate_ordering_cost(shared_segment_count=1) == pytest.approx(600.0)
    assert evaluate_ordering_cost(edge_crossing_count=1) == pytest.approx(300.0)
    assert evaluate_ordering_cost(bend_count=1) == pytest.approx(80.0)
    assert evaluate_ordering_cost(route_length=1.0) == pytest.approx(1.0)
    assert evaluate_ordering_cost(straight_edge_count=1) == pytest.approx(-180.0)


def test_evaluate_ordering_cost_keyword_only():
    # Must not accept positional arguments (AC2)
    with pytest.raises(TypeError):
        evaluate_ordering_cost(0)  # type: ignore[call-arg]


# ── T2: AC7 edge cases ────────────────────────────────────────────────────────

def test_refine_empty_rank():
    assert refine_rank_ordering([], {}, []) == []


def test_refine_single_node():
    assert refine_rank_ordering(["A"], {"A": (0, 0, 50, 30)}, []) == ["A"]


# ── T2: AC3 permutation exhaustiveness ───────────────────────────────────────

def test_refine_permutation_invocation_count():
    # 3-node rank, no declared constraints → exactly 3! = 6 cost_fn calls
    rank = ["A", "B", "C"]
    bounds = {"A": (0, 0, 50, 30), "B": (60, 0, 50, 30), "C": (120, 0, 50, 30)}
    call_count = [0]

    def counting_fn(ordering, nb, edges):
        call_count[0] += 1
        return 0.0

    refine_rank_ordering(rank, bounds, [], cost_fn=counting_fn)
    assert call_count[0] == 6  # 3! = 6


def test_refine_permutation_selects_minimum():
    # cost_fn prefers ordering [C, A, B] — that should be returned
    rank = ["A", "B", "C"]
    bounds = {"A": (0, 0, 50, 30), "B": (60, 0, 50, 30), "C": (120, 0, 50, 30)}
    preferred = ("C", "A", "B")

    def biased_fn(ordering, nb, edges):
        return 0.0 if tuple(ordering) == preferred else 1.0

    result = refine_rank_ordering(rank, bounds, [], cost_fn=biased_fn)
    assert result == list(preferred)


# ── T2: AC5a/b declared order ────────────────────────────────────────────────

def test_refine_declared_order_permutation():
    # With (A, B) declared, result must have A before B
    rank = ["B", "A", "C"]
    bounds = {n: (i * 60, 0, 50, 30) for i, n in enumerate(rank)}
    result = refine_rank_ordering(rank, bounds, [], declared_order=[("A", "B")])
    assert result.index("A") < result.index("B")


def test_refine_cycle_raises():
    rank = ["A", "B"]
    bounds = {n: (i * 60, 0, 50, 30) for i, n in enumerate(rank)}
    with pytest.raises(ValueError, match="cycle"):
        refine_rank_ordering(rank, bounds, [], declared_order=[("A", "B"), ("B", "A")])


# ── T2: AC6 determinism (permutation) ────────────────────────────────────────

def test_refine_deterministic_permutation():
    rank = ["A", "B", "C"]
    bounds = {"A": (0, 0, 50, 30), "B": (60, 0, 50, 30), "C": (120, 0, 50, 30)}
    r1 = refine_rank_ordering(rank, bounds, [])
    r2 = refine_rank_ordering(rank, bounds, [])
    assert r1 == r2


# ── T3: AC4 transposition invocation bound ───────────────────────────────────

def test_refine_uses_transposition_for_large_rank():
    # 7-node rank → adjacent transposition; cost_fn calls ≤ 3*7*(7-1)+1 = 127
    rank = [f"N{i}" for i in range(7)]
    bounds = {n: (i * 60, 0, 50, 30) for i, n in enumerate(rank)}
    call_count = [0]

    def counting_fn(ordering, nb, edges):
        call_count[0] += 1
        return float(sum(int(n[1:]) for n in ordering))  # varies; forces passes

    refine_rank_ordering(rank, bounds, [], cost_fn=counting_fn)
    assert call_count[0] <= 3 * 7 * 6 + 1  # 127


def test_refine_transposition_improves_cost():
    # 7-node rank; cost_fn penalises N0 at position 0; function should move it
    rank = [f"N{i}" for i in range(7)]
    bounds = {n: (i * 60, 0, 50, 30) for i, n in enumerate(rank)}

    def penalty_fn(ordering, nb, edges):
        # Very expensive if N0 is at position 0
        return 10000.0 if ordering[0] == "N0" else float(ordering.index("N0"))

    result = refine_rank_ordering(rank, bounds, [], cost_fn=penalty_fn)
    assert result[0] != "N0"


# ── T3: AC5a declared order under transposition ───────────────────────────────

def test_refine_declared_order_transposition():
    rank = [f"N{i}" for i in range(7)]
    bounds = {n: (i * 60, 0, 50, 30) for i, n in enumerate(rank)}
    # Declare N6 before N0 to force a non-trivial constraint
    result = refine_rank_ordering(rank, bounds, [], declared_order=[("N6", "N0")])
    assert result.index("N6") < result.index("N0")


# ── T3: AC6 determinism (transposition) ──────────────────────────────────────

def test_refine_deterministic_transposition():
    rank = [f"N{i}" for i in range(7)]
    bounds = {n: (i * 60, 0, 50, 30) for i, n in enumerate(rank)}
    r1 = refine_rank_ordering(rank, bounds, [])
    r2 = refine_rank_ordering(rank, bounds, [])
    assert r1 == r2


# ── T4: AC9 route-aware default cost ─────────────────────────────────────────

def _two_node_fixture():
    """A, B at distinct x; edges A→ExtLeft, B→ExtRight at different x."""
    bounds = {
        "A": (50.0, 100.0, 40.0, 30.0),
        "B": (150.0, 100.0, 40.0, 30.0),
        "ExtLeft": (0.0, 0.0, 10.0, 10.0),
        "ExtRight": (200.0, 0.0, 10.0, 10.0),
    }
    edges = [
        {"edge_id": "e1", "source_id": "A", "target_id": "ExtLeft"},
        {"edge_id": "e2", "source_id": "B", "target_id": "ExtRight"},
    ]
    return bounds, edges


def test_cheap_cost_varies_with_ordering():
    # Two orderings of [A, B] must produce different cheap costs (AC9)
    bounds, edges = _two_node_fixture()
    rank_ab = ["A", "B"]
    rank_ba = ["B", "A"]
    cost_ab = _cheap_cost(rank_ab, bounds, edges)
    cost_ba = _cheap_cost(rank_ba, bounds, edges)
    assert cost_ab != cost_ba


def test_refine_route_aware_default():
    # refine_rank_ordering with no cost_fn should return the better ordering
    bounds, edges = _two_node_fixture()
    rank = ["A", "B"]
    # [A,B]: A at slot x=50 → edge to ExtLeft@x=0 is short; B at x=150 → edge to ExtRight@x=200 short
    # [B,A]: B at slot x=50 → edge to ExtRight@x=200 is long; A at x=150 → edge to ExtLeft@x=0 long
    # [A,B] should have lower total length → refine should return it
    cost_ab = _cheap_cost(["A", "B"], bounds, edges)
    cost_ba = _cheap_cost(["B", "A"], bounds, edges)
    expected_best = ["A", "B"] if cost_ab < cost_ba else ["B", "A"]
    result = refine_rank_ordering(rank, bounds, edges)
    assert result == expected_best


# ── T5: regression check is run via pytest tests/ -x -q (no extra tests here)
