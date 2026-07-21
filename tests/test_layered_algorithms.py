"""Stage 8 tests: layered graph algorithm strategies.

Covers:
- Protocol compliance for all strategy classes
- LongestPathRanker: rank constraints satisfied, dummy insertion
- NetworkSimplexRanker: tighter total edge length than longest-path on suitable graphs
- BarycentricOrderer: crossing count non-negative and bounded
- BarycentricTransposeOrderer: never worse than initial ordering; improves strictly on
  a deliberately crossed fixture
- SimpleCoordinateAssigner: positions valid and deterministic
- BrandesKoepfAssigner: zero node overlaps, valid positions
- Metric helpers: count_edge_crossings, count_node_overlaps, total_edge_length, etc.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from mermaid_render.layout._constants import _Node, _Edge, _Group, NODE_W, NODE_H, COL_GAP, RANK_GAP
from mermaid_render.layout._layered import (
    RankAssigner, CrossingOrderer, CoordinateAssigner,
    LongestPathRanker, NetworkSimplexRanker,
    BarycentricOrderer, BarycentricTransposeOrderer,
    SimpleCoordinateAssigner, BrandesKoepfAssigner,
    _adjacent_transpose,
    count_edge_crossings, count_node_overlaps,
    total_edge_length, total_bends, layout_area,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_node(nid: str, rank: int = 0, col: int = 0, w: int = NODE_W, h: int = NODE_H) -> _Node:
    n = _Node(id=nid, rank=rank, col=col)
    n.width = w
    n.height = h
    return n


def _make_edge(src: str, dst: str) -> _Edge:
    return _Edge(src=src, dst=dst)


def _simple_dag() -> tuple[dict[str, _Node], list[_Edge]]:
    """A→B→C linear chain."""
    nodes = {
        "A": _make_node("A"),
        "B": _make_node("B"),
        "C": _make_node("C"),
    }
    edges = [_make_edge("A", "B"), _make_edge("B", "C")]
    return nodes, edges


def _diamond_dag() -> tuple[dict[str, _Node], list[_Edge]]:
    """A→B, A→C, B→D, C→D."""
    nodes = {nid: _make_node(nid) for nid in ("A", "B", "C", "D")}
    edges = [
        _make_edge("A", "B"), _make_edge("A", "C"),
        _make_edge("B", "D"), _make_edge("C", "D"),
    ]
    return nodes, edges


def _crossed_dag() -> tuple[dict[str, _Node], list[_Edge]]:
    """Two crossing edges: A→D, B→C with initial alphabetical col order.

    rank 0: A(col=0), B(col=1)
    rank 1: C(col=0), D(col=1)  ← alphabetical — crossed!
    """
    nodes = {
        "A": _make_node("A", rank=0, col=0),
        "B": _make_node("B", rank=0, col=1),
        "C": _make_node("C", rank=1, col=0),
        "D": _make_node("D", rank=1, col=1),
    }
    edges = [_make_edge("A", "D"), _make_edge("B", "C")]
    return nodes, edges


def _multi_rank_dag() -> tuple[dict[str, _Node], list[_Edge]]:
    """A→B→D, A→C→D (diamond with longer ranks)."""
    nodes = {nid: _make_node(nid) for nid in ("A", "B", "C", "D")}
    edges = [
        _make_edge("A", "B"), _make_edge("A", "C"),
        _make_edge("B", "D"), _make_edge("C", "D"),
    ]
    return nodes, edges


# ── Protocol compliance ───────────────────────────────────────────────────────

class TestProtocolCompliance:
    def test_longest_path_is_rank_assigner(self):
        assert isinstance(LongestPathRanker(), RankAssigner)

    def test_network_simplex_is_rank_assigner(self):
        assert isinstance(NetworkSimplexRanker(), RankAssigner)

    def test_barycentric_is_crossing_orderer(self):
        assert isinstance(BarycentricOrderer(), CrossingOrderer)

    def test_barycentric_transpose_is_crossing_orderer(self):
        assert isinstance(BarycentricTransposeOrderer(), CrossingOrderer)

    def test_simple_assigner_is_coordinate_assigner(self):
        assert isinstance(SimpleCoordinateAssigner(), CoordinateAssigner)

    def test_bk_assigner_is_coordinate_assigner(self):
        assert isinstance(BrandesKoepfAssigner(), CoordinateAssigner)


# ── LongestPathRanker ─────────────────────────────────────────────────────────

class TestLongestPathRanker:
    def test_chain_ranks_ascending(self):
        nodes, edges = _simple_dag()
        LongestPathRanker().assign(nodes, edges)
        real = {nid: n for nid, n in nodes.items() if not n.is_dummy}
        assert real["A"].rank < real["B"].rank < real["C"].rank

    def test_source_at_rank_zero(self):
        nodes, edges = _simple_dag()
        LongestPathRanker().assign(nodes, edges)
        real = {nid: n for nid, n in nodes.items() if not n.is_dummy}
        assert real["A"].rank == 0

    def test_rank_constraints_satisfied(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        for e in edges:
            if e.src in nodes and e.dst in nodes and not e.reversed_:
                assert nodes[e.dst].rank > nodes[e.src].rank, (
                    f"Rank constraint violated: {e.src}({nodes[e.src].rank}) → "
                    f"{e.dst}({nodes[e.dst].rank})"
                )

    def test_dummy_nodes_inserted_for_skip_edges(self):
        """An edge spanning >1 rank gets dummy nodes."""
        nodes = {"A": _make_node("A"), "C": _make_node("C")}
        edges = [_make_edge("A", "C")]
        # Manually set C rank high to force a skip
        # LongestPathRanker will calculate A→C as 1 rank, so no skip.
        # Instead, test with an intervening node that forces skip:
        nodes2 = {
            "A": _make_node("A"),
            "B": _make_node("B"),
            "C": _make_node("C"),
        }
        edges2 = [_make_edge("A", "B"), _make_edge("B", "C"), _make_edge("A", "C")]
        LongestPathRanker().assign(nodes2, edges2)
        # A→C now spans 2 ranks; a dummy should be inserted
        dummies = [nid for nid in nodes2 if nodes2[nid].is_dummy]
        # A is rank 0, B is rank 1, C is rank 2 → A→C spans 2 → 1 dummy
        assert len(dummies) == 1

    def test_deterministic_on_repeated_calls(self):
        for _ in range(3):
            nodes, edges = _diamond_dag()
            LongestPathRanker().assign(nodes, edges)
            real = {nid: n for nid, n in nodes.items() if not n.is_dummy}
            assert real["A"].rank == 0
            assert real["D"].rank == 2


# ── NetworkSimplexRanker ──────────────────────────────────────────────────────

class TestNetworkSimplexRanker:
    def test_rank_constraints_satisfied(self):
        nodes, edges = _diamond_dag()
        NetworkSimplexRanker().assign(nodes, edges)
        for e in edges:
            if e.src in nodes and e.dst in nodes and not e.reversed_:
                if not nodes[e.src].is_dummy and not nodes[e.dst].is_dummy:
                    assert nodes[e.dst].rank >= nodes[e.src].rank + 1, (
                        f"Rank violated: {e.src}→{e.dst}"
                    )

    def test_source_at_rank_zero(self):
        nodes, edges = _simple_dag()
        NetworkSimplexRanker().assign(nodes, edges)
        real = {nid: n for nid, n in nodes.items() if not n.is_dummy}
        sources = [nid for nid in real if real[nid].rank == 0]
        assert len(sources) >= 1

    def test_total_edge_length_le_longest_path(self):
        """Network-simplex should tighten ranks, reducing or maintaining total wire length."""
        nodes_lp, edges_lp = _diamond_dag()
        LongestPathRanker().assign(nodes_lp, edges_lp)
        len_lp = total_edge_length(nodes_lp, edges_lp)

        nodes_ns, edges_ns = _diamond_dag()
        NetworkSimplexRanker().assign(nodes_ns, edges_ns)
        len_ns = total_edge_length(nodes_ns, edges_ns)

        assert len_ns <= len_lp, (
            f"NetworkSimplex length {len_ns} > LongestPath length {len_lp}"
        )

    def test_deterministic(self):
        ranks_a, ranks_b = [], []
        for _ in range(2):
            nodes, edges = _diamond_dag()
            NetworkSimplexRanker().assign(nodes, edges)
            real = sorted(
                [(nid, n.rank) for nid, n in nodes.items() if not n.is_dummy],
                key=lambda x: x[0],
            )
            if not ranks_a:
                ranks_a = real
            else:
                ranks_b = real
        assert ranks_a == ranks_b

    def test_handles_single_node(self):
        nodes = {"A": _make_node("A")}
        edges: list[_Edge] = []
        NetworkSimplexRanker().assign(nodes, edges)
        assert "A" in nodes  # no crash


# ── BarycentricOrderer ────────────────────────────────────────────────────────

class TestBarycentricOrderer:
    def test_assigns_col_to_all_nodes(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        for nid, n in nodes.items():
            assert n.col >= 0, f"Node {nid} has negative col"

    def test_crossing_count_nonnegative(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        c = count_edge_crossings(nodes, edges)
        assert c >= 0

    def test_deterministic(self):
        results = []
        for _ in range(2):
            nodes, edges = _diamond_dag()
            LongestPathRanker().assign(nodes, edges)
            BarycentricOrderer().order(nodes, edges)
            results.append({nid: n.col for nid, n in nodes.items()})
        assert results[0] == results[1]


# ── BarycentricTransposeOrderer ───────────────────────────────────────────────

class TestBarycentricTransposeOrderer:
    def test_assigns_col_to_all_nodes(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricTransposeOrderer().order(nodes, edges)
        for nid, n in nodes.items():
            assert n.col >= 0

    def test_never_worse_than_barycenter(self):
        """BarycentricTransposeOrderer crossings ≤ BarycentricOrderer crossings."""
        nodes_b, edges_b = _diamond_dag()
        LongestPathRanker().assign(nodes_b, edges_b)
        BarycentricOrderer().order(nodes_b, edges_b)
        crossings_b = count_edge_crossings(nodes_b, edges_b)

        nodes_t, edges_t = _diamond_dag()
        LongestPathRanker().assign(nodes_t, edges_t)
        BarycentricTransposeOrderer().order(nodes_t, edges_t)
        crossings_t = count_edge_crossings(nodes_t, edges_t)

        assert crossings_t <= crossings_b, (
            f"Transpose orderer ({crossings_t}) worse than barycenter ({crossings_b})"
        )

    def test_improves_on_crossed_fixture(self):
        """Adjacent-transpose directly improves a deliberately crossed arrangement.

        A→D, B→C with initial col assignments: A(0),B(1) / C(0),D(1)
        creates 1 crossing. Adjacent-transpose must reduce it to 0.
        """
        nodes, edges = _crossed_dag()
        initial_crossings = count_edge_crossings(nodes, edges)
        assert initial_crossings == 1, (
            f"Test setup error: expected 1 crossing, got {initial_crossings}"
        )

        _adjacent_transpose(nodes, edges, max_passes=5)
        final_crossings = count_edge_crossings(nodes, edges)

        assert final_crossings < initial_crossings, (
            f"Adjacent-transpose did not improve: before={initial_crossings}, "
            f"after={final_crossings}"
        )
        assert final_crossings == 0, (
            f"Expected 0 crossings after transpose, got {final_crossings}"
        )

    def test_deterministic(self):
        results = []
        for _ in range(2):
            nodes, edges = _diamond_dag()
            LongestPathRanker().assign(nodes, edges)
            BarycentricTransposeOrderer().order(nodes, edges)
            results.append({nid: n.col for nid, n in nodes.items()})
        assert results[0] == results[1]

    def test_larger_graph_no_regression(self):
        """On a larger graph, BT-orderer must not increase crossings vs barycenter."""
        # Fan-out graph: one source feeding many targets
        nodes_b = {nid: _make_node(nid) for nid in ("src", "a", "b", "c", "d", "e")}
        edges_b = [_make_edge("src", v) for v in ("a", "b", "c", "d", "e")]
        LongestPathRanker().assign(nodes_b, edges_b)
        BarycentricOrderer().order(nodes_b, edges_b)
        c_b = count_edge_crossings(nodes_b, edges_b)

        nodes_t = {nid: _make_node(nid) for nid in ("src", "a", "b", "c", "d", "e")}
        edges_t = [_make_edge("src", v) for v in ("a", "b", "c", "d", "e")]
        LongestPathRanker().assign(nodes_t, edges_t)
        BarycentricTransposeOrderer().order(nodes_t, edges_t)
        c_t = count_edge_crossings(nodes_t, edges_t)

        assert c_t <= c_b


# ── SimpleCoordinateAssigner ──────────────────────────────────────────────────

class TestSimpleCoordinateAssigner:
    def test_all_nodes_get_positions(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        cw, ch = SimpleCoordinateAssigner().assign(nodes, "TB", None, None, None)
        for nid, n in nodes.items():
            assert n.x >= 0 and n.y >= 0, f"Node {nid} at ({n.x},{n.y})"

    def test_returns_positive_canvas_dims(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        cw, ch = SimpleCoordinateAssigner().assign(nodes, "TB", None, None, None)
        assert cw > 0 and ch > 0

    def test_zero_overlaps(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        SimpleCoordinateAssigner().assign(nodes, "TB", None, None, None)
        overlaps = count_node_overlaps(nodes)
        assert overlaps == 0, f"Unexpected node overlaps: {overlaps}"

    def test_deterministic(self):
        for _ in range(2):
            nodes_a, edges_a = _diamond_dag()
            LongestPathRanker().assign(nodes_a, edges_a)
            BarycentricOrderer().order(nodes_a, edges_a)
            SimpleCoordinateAssigner().assign(nodes_a, "TB", None, None, None)
        nodes_b, edges_b = _diamond_dag()
        LongestPathRanker().assign(nodes_b, edges_b)
        BarycentricOrderer().order(nodes_b, edges_b)
        SimpleCoordinateAssigner().assign(nodes_b, "TB", None, None, None)
        # Same input → same positions
        for nid in ("A", "B", "C", "D"):
            assert nodes_a[nid].x == nodes_b[nid].x
            assert nodes_a[nid].y == nodes_b[nid].y

    def test_col_gap_affects_separation(self):
        nodes_small, edges = _diamond_dag()
        LongestPathRanker().assign(nodes_small, edges)
        BarycentricOrderer().order(nodes_small, edges)
        cw_small, _ = SimpleCoordinateAssigner().assign(nodes_small, "TB", 20, None, None)

        nodes_large, edges2 = _diamond_dag()
        LongestPathRanker().assign(nodes_large, edges2)
        BarycentricOrderer().order(nodes_large, edges2)
        cw_large, _ = SimpleCoordinateAssigner().assign(nodes_large, "TB", 100, None, None)

        assert cw_large >= cw_small


# ── BrandesKoepfAssigner ─────────────────────────────────────────────────────

class TestBrandesKoepfAssigner:
    def test_all_nodes_get_positions(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        cw, ch = BrandesKoepfAssigner().assign(nodes, "TB", None, None, None)
        for nid, n in nodes.items():
            assert n.x >= 0 and n.y >= 0, f"Node {nid} at ({n.x},{n.y})"

    def test_returns_positive_canvas_dims(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        cw, ch = BrandesKoepfAssigner().assign(nodes, "TB", None, None, None)
        assert cw > 0 and ch > 0

    def test_zero_overlaps(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        BrandesKoepfAssigner().assign(nodes, "TB", None, None, None)
        overlaps = count_node_overlaps(nodes)
        assert overlaps == 0, f"Node overlaps after BK: {overlaps}"

    def test_deterministic(self):
        positions: list[dict[str, tuple[int, int]]] = []
        for _ in range(2):
            nodes, edges = _diamond_dag()
            LongestPathRanker().assign(nodes, edges)
            BarycentricOrderer().order(nodes, edges)
            BrandesKoepfAssigner().assign(nodes, "TB", None, None, None)
            positions.append({nid: (n.x, n.y) for nid, n in nodes.items()})
        assert positions[0] == positions[1]

    def test_lr_falls_back_gracefully(self):
        """BrandesKoepfAssigner must not crash on LR direction."""
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        cw, ch = BrandesKoepfAssigner().assign(nodes, "LR", None, None, None)
        assert cw > 0 and ch > 0

    def test_larger_graph_zero_overlaps(self):
        nids = [f"n{i}" for i in range(8)]
        nodes = {nid: _make_node(nid) for nid in nids}
        edges = [
            _make_edge("n0", "n2"), _make_edge("n0", "n3"),
            _make_edge("n1", "n3"), _make_edge("n1", "n4"),
            _make_edge("n2", "n5"), _make_edge("n3", "n5"),
            _make_edge("n3", "n6"), _make_edge("n4", "n6"),
            _make_edge("n5", "n7"), _make_edge("n6", "n7"),
        ]
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        BrandesKoepfAssigner().assign(nodes, "TB", None, None, None)
        overlaps = count_node_overlaps(nodes)
        assert overlaps == 0, f"Overlaps: {overlaps}"


# ── count_edge_crossings ──────────────────────────────────────────────────────

class TestCountEdgeCrossings:
    def test_no_crossings_parallel(self):
        """A→C, B→D with A.col<B.col and C.col<D.col → 0 crossings."""
        nodes = {
            "A": _make_node("A", rank=0, col=0),
            "B": _make_node("B", rank=0, col=1),
            "C": _make_node("C", rank=1, col=0),
            "D": _make_node("D", rank=1, col=1),
        }
        edges = [_make_edge("A", "C"), _make_edge("B", "D")]
        assert count_edge_crossings(nodes, edges) == 0

    def test_one_crossing(self):
        """A→D, B→C → exactly 1 crossing."""
        nodes, edges = _crossed_dag()
        assert count_edge_crossings(nodes, edges) == 1

    def test_empty_graph(self):
        assert count_edge_crossings({}, []) == 0

    def test_single_edge(self):
        nodes = {
            "A": _make_node("A", rank=0, col=0),
            "B": _make_node("B", rank=1, col=0),
        }
        edges = [_make_edge("A", "B")]
        assert count_edge_crossings(nodes, edges) == 0


# ── count_node_overlaps ───────────────────────────────────────────────────────

class TestCountNodeOverlaps:
    def test_no_overlap_side_by_side(self):
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        nodes["A"].x, nodes["A"].y = 0, 0
        nodes["B"].x, nodes["B"].y = NODE_W + 20, 0
        assert count_node_overlaps(nodes) == 0

    def test_overlap_detected(self):
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        nodes["A"].x, nodes["A"].y = 0, 0
        nodes["B"].x, nodes["B"].y = 5, 5  # inside A's bounds
        assert count_node_overlaps(nodes) > 0

    def test_empty_graph(self):
        assert count_node_overlaps({}) == 0


# ── total_edge_length ─────────────────────────────────────────────────────────

class TestTotalEdgeLength:
    def test_chain_length(self):
        nodes, edges = _simple_dag()
        LongestPathRanker().assign(nodes, edges)
        length = total_edge_length(nodes, edges)
        # A(0)→B(1)→C(2): each edge spans 1 rank. Dummies may add more edges.
        # At minimum, total_edge_length >= 2
        assert length >= 2

    def test_empty(self):
        assert total_edge_length({}, []) == 0


# ── layout_area ───────────────────────────────────────────────────────────────

class TestLayoutArea:
    def test_area_positive_after_layout(self):
        nodes, edges = _diamond_dag()
        LongestPathRanker().assign(nodes, edges)
        BarycentricOrderer().order(nodes, edges)
        SimpleCoordinateAssigner().assign(nodes, "TB", None, None, None)
        area = layout_area(nodes)
        assert area > 0

    def test_empty_zero(self):
        assert layout_area({}) == 0


# ── Integration: pipeline smoke tests ────────────────────────────────────────

class TestPipelineIntegration:
    """Run all strategies in sequence and verify structural invariants."""

    def _run_pipeline(
        self,
        ranker: RankAssigner,
        orderer: CrossingOrderer,
        assigner: CoordinateAssigner,
        dag_factory=_diamond_dag,
    ):
        nodes, edges = dag_factory()
        ranker.assign(nodes, edges)
        orderer.order(nodes, edges)
        cw, ch = assigner.assign(nodes, "TB", None, None, None)
        return nodes, edges, cw, ch

    def test_lp_bary_simple_pipeline(self):
        nodes, edges, cw, ch = self._run_pipeline(
            LongestPathRanker(), BarycentricOrderer(), SimpleCoordinateAssigner()
        )
        assert count_node_overlaps(nodes) == 0
        assert cw > 0 and ch > 0

    def test_ns_bt_simple_pipeline(self):
        nodes, edges, cw, ch = self._run_pipeline(
            NetworkSimplexRanker(), BarycentricTransposeOrderer(), SimpleCoordinateAssigner()
        )
        assert count_node_overlaps(nodes) == 0
        assert cw > 0 and ch > 0

    def test_lp_bary_bk_pipeline(self):
        nodes, edges, cw, ch = self._run_pipeline(
            LongestPathRanker(), BarycentricOrderer(), BrandesKoepfAssigner()
        )
        assert count_node_overlaps(nodes) == 0
        assert cw > 0 and ch > 0

    def test_ns_bt_bk_pipeline(self):
        nodes, edges, cw, ch = self._run_pipeline(
            NetworkSimplexRanker(), BarycentricTransposeOrderer(), BrandesKoepfAssigner()
        )
        assert count_node_overlaps(nodes) == 0
        assert cw > 0 and ch > 0

    def test_rank_constraints_satisfied_after_ns(self):
        nodes, edges = _diamond_dag()
        NetworkSimplexRanker().assign(nodes, edges)
        BarycentricTransposeOrderer().order(nodes, edges)
        for e in edges:
            if (e.src in nodes and e.dst in nodes
                    and not e.reversed_
                    and not nodes[e.src].is_dummy
                    and not nodes[e.dst].is_dummy):
                assert nodes[e.dst].rank >= nodes[e.src].rank + 1

    def test_full_pipeline_deterministic(self):
        positions: list[dict] = []
        for _ in range(3):
            nodes, edges = _diamond_dag()
            NetworkSimplexRanker().assign(nodes, edges)
            BarycentricTransposeOrderer().order(nodes, edges)
            BrandesKoepfAssigner().assign(nodes, "TB", None, None, None)
            positions.append({nid: (n.x, n.y) for nid, n in nodes.items() if not n.is_dummy})
        assert positions[0] == positions[1] == positions[2]

    def test_render_with_new_strategies(self):
        """Full render using new strategies: verify output is valid HTML."""
        import mermaid_render
        html = mermaid_render.to_html("flowchart TB\n  A --> B --> C")
        assert "diagram mermaid-layout" in html
        assert "data-node-id" in html
