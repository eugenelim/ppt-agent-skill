"""Eight-case parity CI — hard-failure-condition gate suite.

One test per hard-failure condition listed in
``docs/specs/eight-case-parity-ci-and-cleanup/spec.md`` (AC2). Each test
fabricates the minimal pathological scenario and asserts the corresponding
gate *bites* (returns violations / raises). Where a real fixture is cheap to
compile, a positive control confirms the gate does not false-positive.

Architecture ELK interior-crossing reconciliation
-------------------------------------------------
The spec's hard list includes "route segment crossing an unrelated node
interior". Item 5 DEFERRED exactly this on the architecture ELK path for
``architecture-complex`` (the ``api→cache`` route clips ``queue``'s interior),
tracked by backlog anchor ``arch-elk-edge-interior-crossing``; item 5 forbids
redesigning the successful ELK path. To keep the ELK-required lane from
spuriously failing the hard gate WITHOUT weakening it for flowchart fixtures,
the live architecture ELK lane below is a narrowly-scoped ``xfail`` tied to
that anchor, while the architecture Python-fallback lane asserts clean and the
fabricated node-interior gate (``test_ci_fails_on_segment_crossing_unrelated_node``)
stays a hard assertion.

Coordinate convention: css-top-left (origin top-left, y increases downward).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.eight_case

# ── import surface ─────────────────────────────────────────────────────────
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import mermaid_render as mr  # noqa: E402
from mermaid_render.layout._geometry import (  # noqa: E402
    BoundaryGate,
    BoundaryGateKind,
    FinalizedLayout,
    GroupLayout,
    LayoutDiagnostics,
    NodeLayout,
    Point,
    PortLayout,
    PortSide,
    Rect,
    RoutedEdge,
)
from mermaid_render.layout._layout_validation import (  # noqa: E402
    all_violations,
    semantic_divergence,
    translate_layout_to_positive,
    validate_backend_declared,
    validate_canvas_coverage,
    validate_compound_gates,
    validate_edge_styles,
    validate_local_directions,
    validate_membership,
    validate_min_counts,
    validate_no_auto_ports,
    validate_parent_refs,
    validate_provenance,
    validate_segment_obstruction,
    validate_sibling_groups_disjoint,
)
from mermaid_render.layout._strategies import RenderOptions, _compile_flowchart  # noqa: E402
from mermaid_render.layout.architecture import (  # noqa: E402
    arch_to_finalized,
    compile_architecture,
)

from eight_case_artifacts import (  # noqa: E402
    ALL_FIXTURES,
    FLOWCHART_FIXTURES,
    publish_fixture_artifact,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _src(stem: str) -> str:
    return (_FIXTURE_DIR / f"{stem}.mmd").read_text()


# ── minimal fabrication builders ─────────────────────────────────────────────

def _diag() -> LayoutDiagnostics:
    return LayoutDiagnostics(unsupported_options=(), route_failures=(), warnings=())


def _port(nid: str, p: Point, side: PortSide = PortSide.AUTO) -> PortLayout:
    return PortLayout(node_id=nid, side=side, position=p, direction=Point(0.0, 0.0))


def _node(nid: str, rect: Rect, member_of: str = "") -> NodeLayout:
    return NodeLayout(
        node_id=nid, semantic_shape="rect", outer_bounds=rect, content_bounds=rect,
        title_layout=None, subtitle_layout=None, member_layouts=(), icon_bounds=None,
        ports=(), css_classes=(), extra_css="", parent_group_id=member_of or None,
    )


def _group(gid: str, rect: Rect, members=(), *, parent=None, direction="TB") -> GroupLayout:
    return GroupLayout(
        group_id=gid, parent_group_id=parent, boundary_bounds=rect,
        label_layout=None, member_ids=tuple(members), child_group_ids=(),
        local_direction=direction,
    )


def _edge(eid, src, dst, waypoints, *, style="solid", src_side=PortSide.RIGHT,
          dst_side=PortSide.LEFT, source_scope="", target_scope="") -> RoutedEdge:
    return RoutedEdge(
        edge_id=eid, src_node_id=src, dst_node_id=dst,
        src_port=_port(src, waypoints[0], src_side),
        dst_port=_port(dst, waypoints[-1], dst_side),
        waypoints=tuple(waypoints), edge_style=style, has_marker_end=True,
        has_marker_start=False, label_layout=None, src_label_layout=None,
        dst_label_layout=None, source_scope=source_scope, target_scope=target_scope,
    )


def _layout(*, nodes=(), groups=(), edges=(), canvas, gates=()) -> FinalizedLayout:
    return FinalizedLayout(
        node_layouts={n.node_id: n for n in nodes},
        group_layouts={g.group_id: g for g in groups},
        routed_edges=tuple(edges), visible_bounds=canvas, diagram_padding=8.0,
        canvas_bounds=canvas, direction="TB", diagnostics=_diag(),
        boundary_gates=tuple(gates),
    )


_CANVAS = Rect(0.0, 0.0, 300.0, 300.0)


# ═══════════════════════════════════════════════════════════════════════════
# Provenance / backend conditions
# ═══════════════════════════════════════════════════════════════════════════

def test_ci_fails_on_hidden_backend_fallback():
    assert validate_backend_declared("")        # empty → violation
    assert validate_backend_declared(None)
    assert validate_backend_declared("   ")
    assert validate_backend_declared("elkjs") == []          # positive control


def test_ci_fails_on_missing_backend_provenance():
    bad = {"renderer_api": "to_html", "output_format": "html",
           "semantic_compiler": "flowchart", "layout_backend": ""}
    assert any("layout_backend" in e for e in validate_provenance(bad))
    good = {**bad, "layout_backend": "elkjs"}
    assert validate_provenance(good) == []


def test_ci_fails_on_incorrect_layout_backend_field_usage():
    # layout_backend must never carry an output-format token.
    bad = {"renderer_api": "to_svg", "output_format": "svg",
           "semantic_compiler": "flowchart", "layout_backend": "svg"}
    assert any("output_format" in e for e in validate_provenance(bad))


# ═══════════════════════════════════════════════════════════════════════════
# Canvas coverage conditions
# ═══════════════════════════════════════════════════════════════════════════

def test_ci_fails_on_route_waypoint_outside_canvas():
    edge = _edge("e1", "A", "B", (Point(10.0, 10.0), Point(400.0, 10.0)))
    assert validate_canvas_coverage(_layout(edges=(edge,), canvas=_CANVAS))


def test_ci_fails_on_route_segment_outside_canvas():
    # endpoints inside, middle bulges above the canvas.
    edge = _edge("e1", "A", "B",
                 (Point(20.0, 20.0), Point(150.0, -80.0), Point(280.0, 20.0)))
    assert validate_canvas_coverage(_layout(edges=(edge,), canvas=_CANVAS))


# ═══════════════════════════════════════════════════════════════════════════
# Segment obstruction conditions
# ═══════════════════════════════════════════════════════════════════════════

def test_ci_fails_on_segment_crossing_unrelated_node():
    src = _node("A", Rect(0.0, 140.0, 20.0, 20.0))
    dst = _node("B", Rect(280.0, 140.0, 20.0, 20.0))
    blocker = _node("X", Rect(130.0, 130.0, 40.0, 40.0))
    edge = _edge("e1", "A", "B", (Point(20.0, 150.0), Point(280.0, 150.0)))
    errs = validate_segment_obstruction(_layout(nodes=(src, dst, blocker), edges=(edge,), canvas=_CANVAS))
    assert any("'X'" in e for e in errs), errs


def test_ci_fails_on_segment_crossing_unrelated_group():
    src = _node("A", Rect(0.0, 140.0, 20.0, 20.0))
    dst = _node("B", Rect(280.0, 140.0, 20.0, 20.0))
    grp = _group("G", Rect(120.0, 130.0, 60.0, 60.0), members=("Z",))
    edge = _edge("e1", "A", "B", (Point(20.0, 160.0), Point(280.0, 160.0)))
    errs = validate_segment_obstruction(_layout(nodes=(src, dst), groups=(grp,), edges=(edge,), canvas=_CANVAS))
    assert any("group-interior" in e and "'G'" in e for e in errs), errs


def test_ci_fails_on_segment_crossing_title_band():
    src = _node("A", Rect(0.0, 5.0, 20.0, 20.0))
    dst = _node("B", Rect(280.0, 5.0, 20.0, 20.0))
    grp = _group("G", Rect(100.0, 0.0, 80.0, 200.0))
    edge = _edge("e1", "A", "B", (Point(20.0, 10.0), Point(280.0, 10.0)))
    errs = validate_segment_obstruction(_layout(nodes=(src, dst), groups=(grp,), edges=(edge,), canvas=_CANVAS))
    assert any("group-title" in e for e in errs), errs


# ═══════════════════════════════════════════════════════════════════════════
# Compound gate conditions
# ═══════════════════════════════════════════════════════════════════════════

def _cross_scope(gates, waypoints):
    src = _node("A", Rect(20.0, 140.0, 20.0, 20.0))
    dst = _node("B", Rect(140.0, 140.0, 20.0, 20.0), member_of="G")
    grp = _group("G", Rect(100.0, 100.0, 100.0, 100.0), members=("B",))
    edge = _edge("e1", "A", "B", waypoints, source_scope="", target_scope="G")
    return _layout(nodes=(src, dst), groups=(grp,), edges=(edge,),
                   canvas=Rect(0.0, 0.0, 400.0, 400.0), gates=gates)


def test_ci_fails_on_missing_compound_gate():
    layout = _cross_scope((), (Point(40.0, 150.0), Point(150.0, 150.0)))
    assert any("no boundary gate" in e for e in validate_compound_gates(layout))


def test_ci_fails_on_cross_scope_route_bypassing_gate():
    entry = BoundaryGate(gate_id="g1", group_id="G", side=PortSide.LEFT,
                         point=Point(100.0, 150.0), semantic_node_id="B",
                         edge_id="e1", kind=BoundaryGateKind.ENTRY)
    exit_g = BoundaryGate(gate_id="g0", group_id="G", side=PortSide.TOP,
                          point=Point(150.0, 100.0), semantic_node_id="A",
                          edge_id="e1", kind=BoundaryGateKind.EXIT)
    layout = _cross_scope((entry, exit_g), (Point(40.0, 150.0), Point(150.0, 150.0)))
    assert any("bypasses gate" in e for e in validate_compound_gates(layout))


# ═══════════════════════════════════════════════════════════════════════════
# Group structure conditions
# ═══════════════════════════════════════════════════════════════════════════

def test_ci_fails_on_missing_empty_group():
    # flowchart-empty-subgraph declares an empty subgraph → contract wants ≥1.
    assert validate_min_counts({"empty_groups": 0}, {"empty_groups": 1})
    assert validate_min_counts({"empty_groups": 1}, {"empty_groups": 1}) == []


def test_ci_fails_on_overlapping_sibling_groups():
    a = _group("G1", Rect(0.0, 0.0, 100.0, 100.0), parent="root")
    b = _group("G2", Rect(80.0, 0.0, 100.0, 100.0), parent="root")  # overlap
    assert validate_sibling_groups_disjoint(_layout(groups=(a, b), canvas=Rect(0, 0, 300, 300)))
    # touching (shared edge at x=100) is also a violation
    c = _group("G3", Rect(100.0, 0.0, 50.0, 100.0), parent="root")
    assert validate_sibling_groups_disjoint(_layout(groups=(a, c), canvas=Rect(0, 0, 300, 300)))
    # clearly separated → clean
    d = _group("G4", Rect(150.0, 0.0, 50.0, 100.0), parent="root")
    assert validate_sibling_groups_disjoint(_layout(groups=(a, d), canvas=Rect(0, 0, 300, 300))) == []


def test_ci_fails_on_incorrect_local_direction():
    grp = _group("G", Rect(0.0, 0.0, 100.0, 100.0), direction="TB")
    assert validate_local_directions(_layout(groups=(grp,), canvas=_CANVAS), {"G": "LR"})
    assert validate_local_directions(_layout(groups=(grp,), canvas=_CANVAS), {"G": "TB"}) == []


# ═══════════════════════════════════════════════════════════════════════════
# Sequence conditions
# ═══════════════════════════════════════════════════════════════════════════

def test_ci_fails_on_missing_sequence_box():
    assert validate_min_counts({"boxes": 0}, {"boxes": 2})
    assert validate_min_counts({"boxes": 2}, {"boxes": 2}) == []


def test_ci_fails_on_incorrect_box_membership():
    actual = {"Group A": ("Alice",)}                       # wrong: Bob missing
    expected = {"Group A": ("Alice", "Bob")}
    assert validate_membership(actual, expected)
    assert validate_membership({"Group A": ("Bob", "Alice")}, expected) == []


def test_ci_fails_on_missing_sequence_fragment():
    assert validate_min_counts({"fragments": 1}, {"fragments": 2})
    assert validate_min_counts({"fragments": 2}, {"fragments": 2}) == []


def test_ci_fails_on_incorrect_nested_fragment_parent():
    # a branch whose parent_fragment_id does not resolve to a real fragment.
    assert validate_parent_refs({"br1": "frag-ghost"}, {"frag-1", "frag-2"})
    assert validate_parent_refs({"br1": "frag-1"}, {"frag-1", "frag-2"}) == []


# ═══════════════════════════════════════════════════════════════════════════
# Edge style / architecture port conditions
# ═══════════════════════════════════════════════════════════════════════════

def test_ci_fails_on_missing_edge_style():
    e_solid = _edge("e1", "A", "B", (Point(0.0, 0.0), Point(10.0, 0.0)), style="solid")
    layout = _layout(edges=(e_solid,), canvas=_CANVAS)
    assert validate_edge_styles(layout, {"solid", "thick", "dotted"})   # thick+dotted missing
    assert validate_edge_styles(layout, {"solid"}) == []


def test_ci_fails_on_incorrect_architecture_port():
    # an unresolved PortSide.AUTO on a finalized edge is a fixed-side-port failure.
    edge = _edge("e1", "A", "B", (Point(0.0, 0.0), Point(10.0, 0.0)),
                 src_side=PortSide.AUTO, dst_side=PortSide.LEFT)
    assert validate_no_auto_ports(_layout(edges=(edge,), canvas=_CANVAS))
    ok = _edge("e2", "A", "B", (Point(0.0, 0.0), Point(10.0, 0.0)),
               src_side=PortSide.RIGHT, dst_side=PortSide.LEFT)
    assert validate_no_auto_ports(_layout(edges=(ok,), canvas=_CANVAS)) == []


# ═══════════════════════════════════════════════════════════════════════════
# HTML/SVG divergence, zero-check, determinism
# ═══════════════════════════════════════════════════════════════════════════

def test_ci_fails_on_html_svg_geometry_divergence():
    html_rec = {"nodes": 4, "edges": 5}
    svg_rec = {"nodes": 4, "edges": 4}          # diverges on edge count
    assert semantic_divergence(html_rec, svg_rec)
    assert semantic_divergence(html_rec, dict(html_rec)) == []


def test_ci_fails_on_zero_check_pass():
    # a comparison that "passed" with zero recorded checks is vacuous.
    assert validate_min_counts({"checks": 0}, {"checks": 1})
    assert validate_min_counts({"checks": 4}, {"checks": 1}) == []


def test_ci_fails_on_nondeterministic_output():
    run_a = {"canvas": [0, 0, 200, 200], "nodes": 3}
    run_b = {"canvas": [0, 0, 201, 200], "nodes": 3}   # 1px drift == nondeterministic
    assert semantic_divergence(run_a, run_b)
    assert semantic_divergence(run_a, dict(run_a)) == []


# ═══════════════════════════════════════════════════════════════════════════
# Architecture ELK interior-crossing reconciliation (see module docstring)
# ═══════════════════════════════════════════════════════════════════════════

def test_architecture_fallback_geometry_gate_clean(monkeypatch):
    """The architecture Python-fallback lane must pass every segment-aware
    validator — the hard gate bites there with no exception."""
    monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
    arch = compile_architecture(_src("architecture-complex"))
    assert arch.backend == "python-fallback"
    layout = translate_layout_to_positive(arch_to_finalized(arch))
    assert all_violations(layout) == [], "arch fallback must be geometry-clean"


@pytest.mark.requires_elk
@pytest.mark.xfail(
    reason="arch-elk-edge-interior-crossing (backlog): on the ELK path the "
    "api->cache route clips queue's interior for architecture-complex. Item 5 "
    "forbids redesigning the successful ELK path; deferred to a follow-on "
    "ELK-architecture-geometry spec. Narrowly scoped so the ELK-required lane "
    "does not spuriously fail the hard gate; the flowchart node-interior gate "
    "(test_ci_fails_on_segment_crossing_unrelated_node) stays hard. strict=True "
    "so an XPASS ALARMS when the defect is fixed, prompting promotion to a hard gate.",
    strict=True,
)
def test_architecture_elk_geometry_gate_known_deferred():
    """AC2 reconciliation: the segment-obstruction gate over the REAL
    architecture-complex ELK geometry currently reports the known deferred
    interior crossing.

    The ELK precondition is asserted via ``skip`` (NOT part of the xfail
    expectation), so only the interior-crossing assertion below is expected to
    fail — a wrong backend or an ELK error skips rather than masquerading as the
    expected failure.
    """
    arch = compile_architecture(_src("architecture-complex"))
    if arch.backend != "elk-js":
        pytest.skip("real ELK backend not engaged (precondition, not the deferred defect)")
    layout = translate_layout_to_positive(arch_to_finalized(arch))
    # Expected-to-fail (strict): the known api->cache interior crossing.
    assert validate_segment_obstruction(layout) == []


# ═══════════════════════════════════════════════════════════════════════════
# Real-fixture teeth — the detectors above run against actual compiled fixtures
# so a real regression (not only a fabricated one) turns this gate red.
# ═══════════════════════════════════════════════════════════════════════════

def _compile_py(stem, monkeypatch):
    monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
    return _compile_flowchart(_src(stem), None, RenderOptions()).layout


def test_real_flowchart_edge_styles_present(monkeypatch):
    """The edge-style gate bites on a real fixture: flowchart-arrows-defs must
    expose solid, thick, and dotted styles."""
    layout = _compile_py("flowchart-arrows-defs", monkeypatch)
    assert validate_edge_styles(layout, {"solid", "thick", "dotted"}) == []


def test_real_inner_direction_local_direction(monkeypatch):
    """The local-direction gate bites on a real fixture: flowchart-inner-direction's
    inner group carries the declared LR local direction."""
    layout = _compile_py("flowchart-inner-direction", monkeypatch)
    lr_groups = {gid for gid, gl in layout.group_layouts.items() if gl.local_direction == "LR"}
    assert lr_groups, "expected an LR inner group in flowchart-inner-direction"
    expected = {gid: "LR" for gid in lr_groups}
    assert validate_local_directions(layout, expected) == []


def test_real_architecture_no_auto_ports(monkeypatch):
    """The fixed-side-port gate bites on real architecture output: no PortSide.AUTO
    survives on the architecture-complex fallback lane."""
    monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
    arch = compile_architecture(_src("architecture-complex"))
    layout = translate_layout_to_positive(arch_to_finalized(arch))
    assert validate_no_auto_ports(layout) == []


def test_real_html_svg_semantic_agreement():
    """The HTML/SVG-divergence gate bites on real output: the to_html and to_svg
    lanes of flowchart-arrows-defs must agree on the set of edge relation-ids."""
    import re
    src = _src("flowchart-arrows-defs")
    rel_re = re.compile(r'data-relation-id="([^"]+)"')
    html_ids = sorted(set(rel_re.findall(mr.to_html(src))))
    svg_ids = sorted(set(rel_re.findall(mr.to_svg(src))))
    assert html_ids, "no relation-ids extracted from HTML"
    assert svg_ids, "no relation-ids extracted from SVG"
    assert semantic_divergence({"rel_ids": html_ids}, {"rel_ids": svg_ids}) == []


# ═══════════════════════════════════════════════════════════════════════════
# Task 3 — structured artifacts publisher (AC7) + determinism (AC9)
# ═══════════════════════════════════════════════════════════════════════════

def test_artifacts_published_for_each_fixture(tmp_path):
    """AC7: a structured JSON artifact is written for every fixture run and
    carries every spec-required field."""
    import json
    for stem in ALL_FIXTURES:
        force_python = stem in FLOWCHART_FIXTURES
        record = publish_fixture_artifact(
            stem, tmp_path, faithful=True, force_python=force_python, impl_sha="TEST",
        )
        lane = record["lane"]
        path = tmp_path / stem / f"{lane}.json"
        assert path.exists(), f"missing artifact for {stem}"
        data = json.loads(path.read_text())
        norm = data["normalized"]
        # spec-required field presence
        for key in ("source_hash", "semantic_compiler", "layout_metadata",
                    "nodes", "groups", "boxes", "fragments", "routes",
                    "messages", "gates", "validation", "assertion_count"):
            assert key in norm, f"{stem}: normalized artifact missing {key!r}"
        assert data["provenance"]["impl_git_sha"] == "TEST"
        assert data["reference_extraction"]["status"] == "not-run"
        assert data["comparison"]["comparable"] is True
        # non-vacuous: a published fixture executed at least one assertion.
        assert norm["assertion_count"] >= 1, f"{stem}: vacuous artifact"


def test_artifacts_normalized_deterministic(tmp_path):
    """AC9: two clean runs of the same lane produce byte-identical normalized
    records (volatile provenance is excluded from the contract)."""
    import json
    for stem in ALL_FIXTURES:
        force_python = stem in FLOWCHART_FIXTURES
        r1 = publish_fixture_artifact(stem, tmp_path / "a", faithful=True,
                                      force_python=force_python, impl_sha="X")
        r2 = publish_fixture_artifact(stem, tmp_path / "b", faithful=True,
                                      force_python=force_python, impl_sha="Y")
        d1 = json.dumps(r1["normalized"], sort_keys=True)
        d2 = json.dumps(r2["normalized"], sort_keys=True)
        assert d1 == d2, f"{stem}: normalized records diverge across runs"
        # the gate that proves nondeterminism would be caught:
        assert semantic_divergence(r1["normalized"], r2["normalized"]) == []


def test_artifacts_deterministic_across_processes(tmp_path):
    """AC9 (cross-process): the "two identical runs" contract must hold across
    SEPARATE processes with different PYTHONHASHSEED — the case a single-process
    comparison cannot catch (set/dict iteration ordering). Publishes one lane in
    two fresh interpreters seeded differently and diffs the normalized subtree.
    """
    import json
    import os
    import subprocess

    stem = "flowchart-groups-complex"  # richest flowchart lane
    tools_dir = str(Path(__file__).resolve().parent.parent / "tools")
    snippet = (
        "import json,sys;"
        "sys.path.insert(0, %r);"
        "from eight_case_artifacts import publish_fixture_artifact;"
        "r=publish_fixture_artifact(%r, sys.argv[1], faithful=True, force_python=True, impl_sha='S');"
        "print(json.dumps(r['normalized'], sort_keys=True))"
    ) % (tools_dir, stem)

    def _run(seed: str, out: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": seed}
        proc = subprocess.run(
            [sys.executable, "-c", snippet, out],
            capture_output=True, text=True, env=env, timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        return proc.stdout.strip()

    a = _run("0", str(tmp_path / "p0"))
    b = _run("12345", str(tmp_path / "p1"))
    assert a == b, f"{stem}: normalized record differs across processes (hash-seed ordering leak)"
    # sanity: the subprocess actually produced a normalized record.
    assert json.loads(a)["semantic_compiler"] == "flowchart"
