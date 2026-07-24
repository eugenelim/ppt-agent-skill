"""Eight-Case Validation and Provenance — canonical acceptance harness.

One command (``pytest -m eight_case``) renders the eight scoped fixtures across
the required lanes and enforces:

- Backend provenance: seven independent fields, none inferred from another
  (spec AC5/AC10), stamped from ``LayoutMetadata`` + call-site context.
- Canvas coverage: every waypoint AND every route segment inside the canvas,
  with the historical ``flowchart-cross-scope-edge`` off-canvas geometry as a
  regression (spec AC6/AC7).
- Segment-vs-rectangle obstruction: complete segments, not just waypoints,
  participate in obstruction checks (spec AC7).
- Compound gate validation: cross-scope edges must cross group boundaries only
  through declared gates (spec AC8).
- Non-vacuous case contracts: minimum assertion counts per fixture; a PASS with
  zero assertions fails (spec AC9).

Live-render lanes for fixtures known-broken until later initiative items land
(native SVG for sequence → item 2; architecture ports/ELK → item 5) are marked
``xfail`` so this suite stays green now.

Coordinate convention: css-top-left (origin top-left, y increases downward).
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

pytestmark = pytest.mark.eight_case

# ── import surface: put scripts/ on sys.path (matches sibling test modules) ────
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import mermaid_render as mr  # noqa: E402
from mermaid_render.layout._geometry import (  # noqa: E402
    BoundaryGate,
    BoundaryGateKind,
    EdgeLabelLayout,
    FinalizedLayout,
    GroupLayout,
    LayoutDiagnostics,
    LayoutMetadata,
    NodeLayout,
    Point,
    PortLayout,
    PortSide,
    Rect,
    RoutedEdge,
    TextLayout,
)
from mermaid_render.layout._layout_validation import (  # noqa: E402
    all_violations,
    required_origin_translation,
    segment_intersects_rect,
    translate_layout_to_positive,
    validate_canvas_coverage,
    validate_compound_gates,
    validate_segment_obstruction,
)
from mermaid_render.layout._sequence_compile import compile_sequence  # noqa: E402
from mermaid_render.layout._strategies import (  # noqa: E402
    RenderOptions,
    _compile_flowchart,
)
from mermaid_render.layout.architecture import compile_architecture  # noqa: E402
from mermaid_render.layout.elk_adapter import _find_elkjs, _find_node  # noqa: E402

FIXTURE_DIR = Path(__file__).parent / "fixtures"

FLOWCHART_FIXTURES = (
    "flowchart-arrows-defs",
    "flowchart-cross-scope-edge",
    "flowchart-empty-subgraph",
    "flowchart-groups-complex",
    "flowchart-inner-direction",
)
ARCHITECTURE_FIXTURES = ("architecture-complex",)
SEQUENCE_FIXTURES = ("sequence-box-unsupported", "sequence-nested-fragments")
ALL_FIXTURES = FLOWCHART_FIXTURES + ARCHITECTURE_FIXTURES + SEQUENCE_FIXTURES


def _src(stem: str) -> str:
    return (FIXTURE_DIR / f"{stem}.mmd").read_text()


def _elk_available() -> bool:
    try:
        return _find_elkjs() is not None and _find_node() is not None
    except Exception:  # pragma: no cover - defensive
        return False


# ── Provenance record: seven independent fields ───────────────────────────────

@dataclasses.dataclass(frozen=True)
class Provenance:
    """Backend provenance for one rendered fixture lane.

    Every field is stamped from an explicit source — never derived from
    another field (spec AC5/AC10). ``layout_backend`` is a *normalized* read of
    ``LayoutMetadata.backend`` (never a rename of it) or the sequence-path
    constant; it is emphatically NOT inferred from ``output_format``.
    """

    renderer_api: str            # "to_html" | "to_svg"
    output_format: str           # "html" | "svg"
    semantic_compiler: str       # "flowchart" | "architecture" | "sequence"
    layout_backend: str          # "elkjs" | "python-fallback" | "sequence-geometry"
    fallback_reason: Optional[str]
    node_version: Optional[str]
    elkjs_version: Optional[str]


def _layout_backend_from_metadata(metadata: LayoutMetadata) -> str:
    """Normalize ``LayoutMetadata.backend`` to the provenance vocabulary.

    "elkjs"/"elk-js" → "elkjs"; "python" → "python-fallback"; anything else is
    returned verbatim. Never renames ``LayoutMetadata.backend`` itself.
    """
    mapping = {
        "elkjs": "elkjs",
        "elk-js": "elkjs",
        "python": "python-fallback",
    }
    return mapping.get(metadata.backend, metadata.backend)


def _node_version() -> Optional[str]:
    node = shutil.which("node")
    if node is None:
        return None
    try:
        out = subprocess.run(
            [node, "--version"], capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() or None
    except Exception:  # pragma: no cover - defensive
        return None


def _elkjs_version() -> Optional[str]:
    pkg = (
        Path(mr.__file__).parent
        / "layout"
        / "node_modules"
        / "elkjs"
        / "package.json"
    )
    try:
        return json.loads(pkg.read_text()).get("version")
    except Exception:
        # Fall back to the version pinned in the layout package manifest.
        manifest = Path(mr.__file__).parent / "layout" / "package.json"
        try:
            deps = json.loads(manifest.read_text()).get("dependencies", {})
            v = deps.get("elkjs", "")
            return v.lstrip("^~") or None
        except Exception:  # pragma: no cover - defensive
            return None


def _flowchart_provenance(
    stem: str,
    renderer_api: str,
    output_format: str,
    *,
    monkeypatch: Optional[pytest.MonkeyPatch] = None,
    force_python: bool = False,
) -> Provenance:
    """Compile a flowchart fixture and stamp its provenance from real metadata.

    When ``force_python`` is set, ``MERMAID_LAYOUT_ENGINE=python`` is applied via
    the caller's ``monkeypatch`` fixture (auto-restored, xdist-safe) so the
    Python fallback is selected deterministically in any environment.
    """
    if force_python:
        assert monkeypatch is not None, "force_python requires a monkeypatch fixture"
        monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
    compiled = _compile_flowchart(_src(stem), None, RenderOptions())
    md = compiled.metadata
    is_elk = md.backend == "elkjs"
    return Provenance(
        renderer_api=renderer_api,
        output_format=output_format,
        semantic_compiler="flowchart",
        layout_backend=_layout_backend_from_metadata(md),
        fallback_reason=md.fallback_reason,
        node_version=_node_version() if is_elk else None,
        elkjs_version=_elkjs_version() if is_elk else None,
    )


def _sequence_provenance(stem: str, renderer_api: str, output_format: str) -> Provenance:
    """Compile a sequence fixture and stamp its provenance at the call site.

    Sequence diagrams carry no ``LayoutMetadata`` — provenance is stamped
    directly: ``semantic_compiler="sequence"``, ``layout_backend="sequence-geometry"``.
    """
    compile_sequence(_src(stem))  # exercise the compiler; result unused here
    return Provenance(
        renderer_api=renderer_api,
        output_format=output_format,
        semantic_compiler="sequence",
        layout_backend="sequence-geometry",
        fallback_reason=None,
        node_version=None,
        elkjs_version=None,
    )


# ── Non-vacuous case contracts ─────────────────────────────────────────────────

class NonVacuousViolation(AssertionError):
    """Raised when a fixture reports PASS but executed zero assertions."""


def assert_non_vacuous(status: str, assertion_count: int) -> None:
    if status == "PASS" and assertion_count == 0:
        raise NonVacuousViolation(
            "status PASS with zero executed assertions is a vacuous result"
        )


@dataclasses.dataclass(frozen=True)
class FixtureContract:
    """Minimum counts a fixture must exhibit (spec AC9)."""

    stem: str
    min_nodes: int = 0          # nodes / services / participants
    min_groups: int = 0
    min_relations: int = 0      # edges / relations / messages
    min_gates: int = 0          # boundary gates / cross-scope crossings
    min_fragments: int = 0
    min_branches: int = 0
    min_endpoint_assertions: int = 0
    min_empty_groups: int = 0
    min_boxes: int = 0


CONTRACTS = {
    "architecture-complex": FixtureContract(
        "architecture-complex",
        min_nodes=5,
        min_groups=1,
        min_relations=4,
        min_endpoint_assertions=8,
    ),
    "flowchart-arrows-defs": FixtureContract(
        "flowchart-arrows-defs", min_nodes=4, min_relations=5
    ),
    "flowchart-cross-scope-edge": FixtureContract(
        "flowchart-cross-scope-edge",
        min_nodes=5,
        min_groups=1,
        min_relations=4,
        min_gates=2,
    ),
    "flowchart-empty-subgraph": FixtureContract(
        "flowchart-empty-subgraph",
        min_nodes=2,
        min_groups=2,
        min_relations=1,
        min_empty_groups=1,
    ),
    "flowchart-groups-complex": FixtureContract(
        "flowchart-groups-complex", min_nodes=7, min_groups=3, min_relations=8
    ),
    "flowchart-inner-direction": FixtureContract(
        "flowchart-inner-direction", min_nodes=5, min_groups=1, min_relations=4
    ),
    "sequence-box-unsupported": FixtureContract(
        "sequence-box-unsupported", min_nodes=4, min_relations=4, min_boxes=2
    ),
    "sequence-nested-fragments": FixtureContract(
        "sequence-nested-fragments",
        min_nodes=2,
        min_relations=3,
        min_fragments=2,
        min_branches=1,
    ),
}


# ── Fabrication builders for validator unit tests ──────────────────────────────

def _empty_diag() -> LayoutDiagnostics:
    return LayoutDiagnostics(unsupported_options=(), route_failures=(), warnings=())


def _port(node_id: str, p: Point) -> PortLayout:
    return PortLayout(node_id=node_id, side=PortSide.AUTO, position=p, direction=Point(0.0, 0.0))


def _node(node_id: str, rect: Rect, member_of: str = "") -> NodeLayout:
    return NodeLayout(
        node_id=node_id,
        semantic_shape="rect",
        outer_bounds=rect,
        content_bounds=rect,
        title_layout=None,
        subtitle_layout=None,
        member_layouts=(),
        icon_bounds=None,
        ports=(),
        css_classes=(),
        extra_css="",
        parent_group_id=member_of or None,
    )


def _group(group_id: str, rect: Rect, members: tuple[str, ...] = ()) -> GroupLayout:
    return GroupLayout(
        group_id=group_id,
        parent_group_id=None,
        boundary_bounds=rect,
        label_layout=None,
        member_ids=members,
        child_group_ids=(),
        local_direction="TB",
    )


def _edge(
    edge_id: str,
    src: str,
    dst: str,
    waypoints: tuple[Point, ...],
    *,
    source_scope: str = "",
    target_scope: str = "",
    label: Optional[EdgeLabelLayout] = None,
) -> RoutedEdge:
    return RoutedEdge(
        edge_id=edge_id,
        src_node_id=src,
        dst_node_id=dst,
        src_port=_port(src, waypoints[0]),
        dst_port=_port(dst, waypoints[-1]),
        waypoints=waypoints,
        edge_style="solid",
        has_marker_end=True,
        has_marker_start=False,
        label_layout=label,
        src_label_layout=None,
        dst_label_layout=None,
        source_scope=source_scope,
        target_scope=target_scope,
    )


def _layout(
    *,
    nodes: tuple[NodeLayout, ...] = (),
    groups: tuple[GroupLayout, ...] = (),
    edges: tuple[RoutedEdge, ...] = (),
    canvas: Rect,
    gates: tuple[BoundaryGate, ...] = (),
) -> FinalizedLayout:
    return FinalizedLayout(
        node_layouts={n.node_id: n for n in nodes},
        group_layouts={g.group_id: g for g in groups},
        routed_edges=edges,
        visible_bounds=canvas,
        diagram_padding=8.0,
        canvas_bounds=canvas,
        direction="TB",
        diagnostics=_empty_diag(),
        boundary_gates=gates,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Task 1 — canonical runner: ELK-required, fallback, and sequence lanes
# ═══════════════════════════════════════════════════════════════════════════════

def _render_lane_params():
    params = []
    for stem in ALL_FIXTURES:
        for api in ("to_html", "to_svg"):
            for faithful in (True, False):
                # Item 2 landed the shared sequence compiler + native scene, so
                # sequence to_svg is no longer broken. Architecture native SVG
                # remains pending item 5.
                broken = api == "to_svg" and stem in ARCHITECTURE_FIXTURES
                marks = (
                    [pytest.mark.xfail(
                        reason="architecture native SVG pending item 5",
                        strict=False,
                    )]
                    if broken
                    else []
                )
                params.append(
                    pytest.param(stem, api, faithful, marks=marks, id=f"{stem}-{api}-f{int(faithful)}")
                )
    return params


@pytest.mark.parametrize("stem,api,faithful", _render_lane_params())
def test_render_variant_lane(stem, api, faithful):
    """AC1: every fixture renders across the four variants; loud on any error.

    Sequence has an experimental native SVG builder, so its to_svg lane opts in
    with ``experimental=True``. Architecture stays on the opt-in-required path
    (its native SVG is pending item 5) so its lane remains a genuine xfail.
    """
    if api == "to_html":
        out = mr.to_html(_src(stem), faithful=faithful)
    elif stem in SEQUENCE_FIXTURES:
        out = mr.to_svg(_src(stem), faithful=faithful, experimental=True)
    else:
        out = mr.to_svg(_src(stem), faithful=faithful)
    assert out, "renderer returned empty output"
    root_tag = "<svg" if api == "to_svg" else "<html"
    assert root_tag in out.lower(), f"{api} output missing {root_tag} root tag"


def _elk_lane_params():
    params = []
    for stem in FLOWCHART_FIXTURES:
        # Compound layouts (has_inner_dir) always take the Python path — the
        # ELK-backed compound path is item 3's work, so these xfail on the ELK lane.
        compound = stem in ("flowchart-cross-scope-edge", "flowchart-inner-direction")
        marks = [pytest.mark.xfail(
            reason="compound layout takes the Python path until item 3", strict=False,
        )] if compound else []
        params.append(pytest.param(stem, marks=marks, id=stem))
    # Architecture ELK/port integration is item 5.
    params.append(pytest.param(
        "architecture-complex",
        marks=[pytest.mark.xfail(reason="architecture ELK/port integration pending item 5", strict=False)],
        id="architecture-complex",
    ))
    return params


@pytest.mark.requires_elk
@pytest.mark.parametrize("stem", _elk_lane_params())
def test_elk_lane_requires_elkjs_present(stem):
    """AC2: with ELK available, the ELK-required fixtures use the elkjs backend
    and record Node + elkjs versions. Skipped cleanly when ELK is absent."""
    prov = _flowchart_provenance(stem, "to_html", "html", force_python=False)
    assert prov.layout_backend == "elkjs"
    assert prov.fallback_reason is None
    assert prov.node_version, "node version must be recorded on the ELK lane"
    assert prov.elkjs_version, "elkjs version must be recorded on the ELK lane"


@pytest.mark.parametrize("stem", FLOWCHART_FIXTURES)
def test_fallback_lane_uses_python_fallback(stem, monkeypatch):
    """AC3: forcing ELK off yields python-fallback with a typed fallback_reason."""
    prov = _flowchart_provenance(
        stem, "to_html", "html", monkeypatch=monkeypatch, force_python=True
    )
    assert prov.layout_backend == "python-fallback"
    assert isinstance(prov.fallback_reason, str) and prov.fallback_reason
    assert prov.node_version is None
    assert prov.elkjs_version is None


@pytest.mark.parametrize("stem", SEQUENCE_FIXTURES)
def test_sequence_lane_stamps_correct_fields(stem):
    """AC4: sequence fixtures stamp semantic_compiler=sequence / layout_backend=sequence-geometry."""
    prov = _sequence_provenance(stem, "to_html", "html")
    assert prov.semantic_compiler == "sequence"
    assert prov.layout_backend == "sequence-geometry"
    assert prov.layout_backend != "native-svg"


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2 — backend provenance fields are independent
# ═══════════════════════════════════════════════════════════════════════════════

def test_provenance_fields_separate(monkeypatch):
    """AC5: the seven provenance fields are distinct keys, not derived from each other."""
    prov = _flowchart_provenance(
        "flowchart-groups-complex", "to_html", "html",
        monkeypatch=monkeypatch, force_python=True,
    )
    keys = {f.name for f in dataclasses.fields(prov)}
    assert keys == {
        "renderer_api",
        "output_format",
        "semantic_compiler",
        "layout_backend",
        "fallback_reason",
        "node_version",
        "elkjs_version",
    }
    # renderer_api, output_format, layout_backend carry independent values.
    assert prov.renderer_api == "to_html"
    assert prov.output_format == "html"
    assert prov.layout_backend == "python-fallback"


def test_provenance_not_inferred_from_output_format(monkeypatch):
    """AC10: layout_backend comes from layout metadata, not the output format.

    Provenance is stamped by the test runner, so the two records differ only in
    the caller-supplied output_format; the assertion that carries the AC is that
    layout_backend is identical across both because it is read from the same
    compile metadata, never from output_format.
    """
    html_prov = _flowchart_provenance(
        "flowchart-groups-complex", "to_html", "html",
        monkeypatch=monkeypatch, force_python=True,
    )
    svg_prov = _flowchart_provenance(
        "flowchart-groups-complex", "to_svg", "svg",
        monkeypatch=monkeypatch, force_python=True,
    )
    assert html_prov.layout_backend == svg_prov.layout_backend == "python-fallback"


def test_layout_backend_normalization_mapping():
    """The normalization maps native backend strings without renaming the source field."""
    def md(backend):
        return LayoutMetadata(
            direction="TB", node_count=0, group_count=0, edge_count=0,
            algorithm="x", backend=backend,
        )

    assert _layout_backend_from_metadata(md("elkjs")) == "elkjs"
    assert _layout_backend_from_metadata(md("elk-js")) == "elkjs"
    assert _layout_backend_from_metadata(md("python")) == "python-fallback"
    # source field is untouched
    assert md("python").backend == "python"


# ═══════════════════════════════════════════════════════════════════════════════
# Task 3 — canvas validation with complete segment coverage
# ═══════════════════════════════════════════════════════════════════════════════

def test_canvas_contains_all_waypoints():
    """AC7: a waypoint outside the canvas fails validation."""
    canvas = Rect(0.0, 0.0, 200.0, 200.0)
    edge = _edge("e1", "A", "B", (Point(10.0, 10.0), Point(250.0, 10.0)))
    layout = _layout(edges=(edge,), canvas=canvas)
    errors = validate_canvas_coverage(layout)
    assert errors, "waypoint at x=250 outside a 200-wide canvas must fail"


def test_canvas_contains_all_segments():
    """AC7: an intermediate waypoint/segment outside the canvas fails, even though
    the route's first and last points are inside (endpoints-only check misses it)."""
    canvas = Rect(0.0, 0.0, 200.0, 200.0)
    # first & last inside; middle bulges out above the canvas.
    edge = _edge(
        "e1", "A", "B",
        (Point(20.0, 20.0), Point(100.0, -50.0), Point(180.0, 20.0)),
    )
    layout = _layout(edges=(edge,), canvas=canvas)
    errors = validate_canvas_coverage(layout)
    assert errors, "intermediate excursion above the canvas must fail"
    # sanity: an endpoints-only view would have passed.
    assert canvas.contains_point(edge.waypoints[0], 1.0)
    assert canvas.contains_point(edge.waypoints[-1], 1.0)


def test_cross_scope_edge_regression():
    """AC6: the historical flowchart-cross-scope-edge off-canvas state
    (canvas h=264, B→C route y=293) fails the new canvas validator."""
    canvas = Rect(0.0, 0.0, 400.0, 264.0)
    edge = _edge("B->C", "B", "C", (Point(100.0, 200.0), Point(100.0, 293.0)))
    layout = _layout(edges=(edge,), canvas=canvas)
    errors = validate_canvas_coverage(layout)
    assert any("293" in e or "B->C" in e for e in errors), errors


def test_negative_coordinates_translated():
    """Spec: negative-coordinate layouts are translated into positive space, not clipped."""
    canvas = Rect(-30.0, -20.0, 200.0, 200.0)
    node = _node("A", Rect(-30.0, -20.0, 40.0, 30.0))
    edge = _edge("e1", "A", "B", (Point(-10.0, -5.0), Point(50.0, 50.0)))
    layout = _layout(nodes=(node,), edges=(edge,), canvas=canvas)

    dx, dy = required_origin_translation(layout)
    assert dx == 30.0 and dy == 20.0

    moved = translate_layout_to_positive(layout)
    # No geometry discarded: waypoint count preserved, all coords non-negative.
    assert len(moved.routed_edges[0].waypoints) == len(edge.waypoints)
    for wp in moved.routed_edges[0].waypoints:
        assert wp.x >= 0.0 and wp.y >= 0.0
    assert moved.canvas_bounds.x >= 0.0 and moved.canvas_bounds.y >= 0.0
    assert moved.node_layouts["A"].outer_bounds.x >= 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Task 4 — segment-vs-rectangle obstruction
# ═══════════════════════════════════════════════════════════════════════════════

def test_clean_layout_passes_all_validators():
    """A well-formed layout produces no violations across every validator."""
    canvas = Rect(0.0, 0.0, 300.0, 300.0)
    a = _node("A", Rect(20.0, 140.0, 40.0, 20.0))
    b = _node("B", Rect(240.0, 140.0, 40.0, 20.0))
    edge = _edge("e1", "A", "B", (Point(60.0, 150.0), Point(240.0, 150.0)))
    layout = _layout(nodes=(a, b), edges=(edge,), canvas=canvas)
    assert all_violations(layout) == []


def test_segment_primitive_detects_crossing():
    rect = Rect(40.0, 40.0, 40.0, 40.0)  # interior (40,40)-(80,80)
    assert segment_intersects_rect(Point(0.0, 60.0), Point(120.0, 60.0), rect)
    # a segment that only grazes the boundary is not an interior crossing
    assert not segment_intersects_rect(Point(0.0, 40.0), Point(120.0, 40.0), rect)
    # a segment fully clear of the rect
    assert not segment_intersects_rect(Point(0.0, 0.0), Point(10.0, 0.0), rect)


def test_segment_crosses_node_interior():
    """AC7: a route segment passing through an unrelated node fails validation."""
    canvas = Rect(0.0, 0.0, 300.0, 300.0)
    src = _node("A", Rect(0.0, 140.0, 20.0, 20.0))
    dst = _node("B", Rect(280.0, 140.0, 20.0, 20.0))
    blocker = _node("X", Rect(130.0, 130.0, 40.0, 40.0))
    edge = _edge("e1", "A", "B", (Point(20.0, 150.0), Point(280.0, 150.0)))
    layout = _layout(nodes=(src, dst, blocker), edges=(edge,), canvas=canvas)
    errors = validate_segment_obstruction(layout)
    assert any("'X'" in e for e in errors), errors


def test_segment_endpoint_exclusion():
    """AC7: the first segment legitimately meeting its own source node is not a false positive."""
    canvas = Rect(0.0, 0.0, 300.0, 300.0)
    src = _node("A", Rect(40.0, 140.0, 40.0, 40.0))
    dst = _node("B", Rect(240.0, 140.0, 40.0, 40.0))
    # route starts at the source's right edge and ends at the destination's left edge.
    edge = _edge("e1", "A", "B", (Point(80.0, 160.0), Point(240.0, 160.0)))
    layout = _layout(nodes=(src, dst), edges=(edge,), canvas=canvas)
    errors = validate_segment_obstruction(layout)
    assert errors == [], errors


def test_segment_crosses_group_title_band():
    """AC7: a route segment crossing a group title band fails validation."""
    canvas = Rect(0.0, 0.0, 300.0, 300.0)
    src = _node("A", Rect(0.0, 5.0, 20.0, 20.0))
    dst = _node("B", Rect(280.0, 5.0, 20.0, 20.0))
    grp = _group("G", Rect(100.0, 0.0, 80.0, 200.0), members=())
    edge = _edge("e1", "A", "B", (Point(20.0, 10.0), Point(280.0, 10.0)))
    layout = _layout(nodes=(src, dst), groups=(grp,), edges=(edge,), canvas=canvas)
    errors = validate_segment_obstruction(layout)
    assert any("group-title" in e for e in errors), errors


def test_segment_crosses_label_rect():
    """AC7: a segment crossing another edge's label rectangle fails validation."""
    canvas = Rect(0.0, 0.0, 300.0, 300.0)
    a = _node("A", Rect(0.0, 140.0, 20.0, 20.0))
    b = _node("B", Rect(280.0, 140.0, 20.0, 20.0))
    c = _node("C", Rect(0.0, 40.0, 20.0, 20.0))
    d = _node("D", Rect(280.0, 40.0, 20.0, 20.0))
    label = EdgeLabelLayout(
        text="lbl",
        layout=_stub_textlayout(),
        bounds=Rect(130.0, 140.0, 40.0, 20.0),
        anchor_point=Point(150.0, 150.0),
    )
    other = _edge("e2", "C", "D", (Point(20.0, 50.0), Point(280.0, 50.0)), label=label)
    edge = _edge("e1", "A", "B", (Point(20.0, 150.0), Point(280.0, 150.0)))
    layout = _layout(nodes=(a, b, c, d), edges=(edge, other), canvas=canvas)
    errors = validate_segment_obstruction(layout)
    assert any("edge-label" in e and "'e2'" in e for e in errors), errors


def test_segment_crosses_group_interior():
    """AC7: a route segment threading an unrelated group's interior fails validation."""
    canvas = Rect(0.0, 0.0, 300.0, 300.0)
    src = _node("A", Rect(0.0, 140.0, 20.0, 20.0))
    dst = _node("B", Rect(280.0, 140.0, 20.0, 20.0))
    # G contains only Z; neither endpoint is a member, so G is an obstacle.
    grp = _group("G", Rect(120.0, 130.0, 60.0, 60.0), members=("Z",))
    edge = _edge("e1", "A", "B", (Point(20.0, 160.0), Point(280.0, 160.0)))
    layout = _layout(nodes=(src, dst), groups=(grp,), edges=(edge,), canvas=canvas)
    errors = validate_segment_obstruction(layout)
    assert any("group-interior" in e and "'G'" in e for e in errors), errors


def _stub_textlayout() -> TextLayout:
    return TextLayout(
        lines=(), width=40.0, height=20.0, line_height=20.0,
        min_content_width=40.0, max_content_width=40.0,
        resolved_font_path=None, resolved_font_family="sans",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Task 5 — compound gate validation
# ═══════════════════════════════════════════════════════════════════════════════

def _cross_scope_layout(*, gates, waypoints, group_rect=Rect(100.0, 100.0, 100.0, 100.0)):
    canvas = Rect(0.0, 0.0, 400.0, 400.0)
    src = _node("A", Rect(20.0, 140.0, 20.0, 20.0))
    dst = _node("B", Rect(140.0, 140.0, 20.0, 20.0), member_of="G")
    grp = _group("G", group_rect, members=("B",))
    edge = _edge(
        "e1", "A", "B", waypoints, source_scope="", target_scope="G"
    )
    return _layout(nodes=(src, dst), groups=(grp,), edges=(edge,), canvas=canvas, gates=gates)


def test_gate_required_for_cross_scope_edge():
    """AC8: a cross-scope edge without any gate record fails validation."""
    layout = _cross_scope_layout(
        gates=(), waypoints=(Point(40.0, 150.0), Point(150.0, 150.0))
    )
    errors = validate_compound_gates(layout)
    assert any("no boundary gate" in e for e in errors), errors


def test_gate_on_group_boundary():
    """AC8: a gate that does not lie on the group boundary fails validation."""
    off_gate = BoundaryGate(
        gate_id="g1", group_id="G", side=PortSide.LEFT,
        point=Point(150.0, 150.0),  # interior of the group, not on the boundary
        semantic_node_id="B", edge_id="e1", kind=BoundaryGateKind.ENTRY,
    )
    exit_gate = BoundaryGate(
        gate_id="g0", group_id="G", side=PortSide.LEFT,
        point=Point(100.0, 150.0), semantic_node_id="A",
        edge_id="e1", kind=BoundaryGateKind.EXIT,
    )
    layout = _cross_scope_layout(
        gates=(exit_gate, off_gate),
        waypoints=(Point(40.0, 150.0), Point(100.0, 150.0), Point(150.0, 150.0)),
    )
    errors = validate_compound_gates(layout)
    assert any("not on group" in e and "g1" in e for e in errors), errors


def test_route_contains_gate_waypoint():
    """AC8: a route that bypasses its declared gate fails validation."""
    entry = BoundaryGate(
        gate_id="g1", group_id="G", side=PortSide.LEFT,
        point=Point(100.0, 150.0), semantic_node_id="B",
        edge_id="e1", kind=BoundaryGateKind.ENTRY,
    )
    exit_gate = BoundaryGate(
        gate_id="g0", group_id="G", side=PortSide.TOP,
        point=Point(150.0, 100.0), semantic_node_id="A",
        edge_id="e1", kind=BoundaryGateKind.EXIT,
    )
    # route jumps straight into the group interior, nowhere near the gate points.
    layout = _cross_scope_layout(
        gates=(entry, exit_gate),
        waypoints=(Point(40.0, 150.0), Point(150.0, 150.0)),
    )
    errors = validate_compound_gates(layout)
    assert any("bypasses gate" in e for e in errors), errors


def test_single_boundary_crossing():
    """AC8: a route that leaves and re-enters the same group fails validation."""
    # One ENTRY gate on target group G: the route should cross G's boundary once.
    entry = BoundaryGate(
        gate_id="g1", group_id="G", side=PortSide.LEFT,
        point=Point(100.0, 150.0), semantic_node_id="B",
        edge_id="e1", kind=BoundaryGateKind.ENTRY,
    )
    # in (150) → out (40) → in (150): crosses the group boundary 2 times.
    layout = _cross_scope_layout(
        gates=(entry,),
        waypoints=(
            Point(100.0, 150.0),
            Point(150.0, 150.0),
            Point(40.0, 150.0),
            Point(150.0, 150.0),
        ),
    )
    errors = validate_compound_gates(layout)
    assert any("re-enters" in e for e in errors), errors


def test_gate_route_crosses_unrelated_group():
    """AC8: a cross-scope route that threads an unrelated (ungated) group fails."""
    canvas = Rect(0.0, 0.0, 400.0, 400.0)
    src = _node("A", Rect(20.0, 140.0, 20.0, 20.0))
    dst = _node("B", Rect(250.0, 140.0, 20.0, 20.0), member_of="G")
    grp_g = _group("G", Rect(200.0, 100.0, 100.0, 100.0), members=("B",))
    grp_h = _group("H", Rect(100.0, 100.0, 60.0, 60.0), members=("Z",))  # unrelated, no gate
    entry = BoundaryGate(
        gate_id="g1", group_id="G", side=PortSide.LEFT,
        point=Point(200.0, 150.0), semantic_node_id="B",
        edge_id="e1", kind=BoundaryGateKind.ENTRY,
    )
    edge = _edge(
        "e1", "A", "B",
        (Point(40.0, 150.0), Point(130.0, 150.0), Point(200.0, 150.0), Point(250.0, 150.0)),
        source_scope="", target_scope="G",
    )
    layout = _layout(
        nodes=(src, dst), groups=(grp_g, grp_h), edges=(edge,), canvas=canvas, gates=(entry,)
    )
    errors = validate_compound_gates(layout)
    assert any("unrelated" in e and "'H'" in e for e in errors), errors


# ═══════════════════════════════════════════════════════════════════════════════
# Live validator lane — validators run against the real compiled FinalizedLayout
# ═══════════════════════════════════════════════════════════════════════════════

# Flowchart fixtures whose real compiled geometry is currently clean; the
# remaining two carry geometry defects owned by items 3-4 and therefore xfail.
_LIVE_BROKEN = {
    "flowchart-cross-scope-edge": "off-canvas compound routing (B→C y=293 > canvas h=264) — item 3",
    "flowchart-groups-complex": "edge-label route obstruction — item 3/4",
}


def _live_lane_params():
    params = []
    for stem in FLOWCHART_FIXTURES:
        marks = (
            [pytest.mark.xfail(reason=_LIVE_BROKEN[stem], strict=False)]
            if stem in _LIVE_BROKEN
            else []
        )
        params.append(pytest.param(stem, marks=marks, id=stem))
    return params


@pytest.mark.parametrize("stem", _live_lane_params())
def test_live_flowchart_geometry_clean(stem, monkeypatch):
    """AC6/AC7/AC8: run the segment-aware validators against each fixture's real
    compiled FinalizedLayout — the gate that actually bites on the eight cases.

    Currently-clean fixtures must pass; fixtures whose geometry is fixed by
    items 3-4 xfail (this is exactly how the harness gates those items). The
    xfail on flowchart-cross-scope-edge confirms the historical off-canvas
    state on the real fixture, complementing the fabricated AC6 regression.
    """
    monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")  # deterministic backend
    compiled = _compile_flowchart(_src(stem), None, RenderOptions())
    layout = translate_layout_to_positive(compiled.layout)
    violations = all_violations(layout)
    assert violations == [], f"{stem}: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# Task 6 — non-vacuous case contracts
# ═══════════════════════════════════════════════════════════════════════════════

def test_zero_assertion_count_fails():
    """AC9: a PASS result with zero executed assertions is a NonVacuousViolation."""
    with pytest.raises(NonVacuousViolation):
        assert_non_vacuous("PASS", 0)
    # a genuine PASS with assertions, and any non-PASS, are fine.
    assert_non_vacuous("PASS", 3)
    assert_non_vacuous("FAIL", 0)


def _flowchart_counts(stem):
    compiled = _compile_flowchart(_src(stem), None, RenderOptions())
    layout = compiled.layout
    real_nodes = [n for n in layout.node_layouts.values() if not getattr(n, "is_dummy", False)]
    empty_groups = [
        g for g in layout.group_layouts.values() if len(g.member_ids) == 0
    ]
    node_ids = set(layout.node_layouts.keys())
    # Containment: every group member id resolves to a laid-out node.
    containment_ok = all(
        all(m in node_ids for m in g.member_ids)
        for g in layout.group_layouts.values()
    )
    return {
        "nodes": len(real_nodes),
        "groups": len(layout.group_layouts),
        "relations": len(layout.routed_edges) + len(layout.routing_failures),
        "gates": len(layout.boundary_gates),
        "empty_groups": len(empty_groups),
        "containment_ok": containment_ok,
    }


@pytest.mark.parametrize("stem", ALL_FIXTURES)
def test_fixture_non_vacuous_contract(stem):
    """AC9: each fixture meets its minimum assertion counts and is non-vacuous."""
    contract = CONTRACTS[stem]
    checks: list[tuple[str, bool]] = []

    if stem in FLOWCHART_FIXTURES:
        c = _flowchart_counts(stem)
        checks.append(("nodes", c["nodes"] >= contract.min_nodes))
        checks.append(("groups", c["groups"] >= contract.min_groups))
        checks.append(("relations", c["relations"] >= contract.min_relations))
        if contract.min_gates:
            checks.append(("gates", c["gates"] >= contract.min_gates))
        if contract.min_empty_groups:
            checks.append(("empty_groups", c["empty_groups"] >= contract.min_empty_groups))
        if c["groups"]:
            # containment assertion (spec AC9: groups-complex / inner-direction)
            checks.append(("containment", c["containment_ok"]))
    elif stem in ARCHITECTURE_FIXTURES:
        arch = compile_architecture(_src(stem))
        checks.append(("services", len(arch.services) >= contract.min_nodes))
        checks.append(("groups", len(arch.groups) >= contract.min_groups))
        checks.append(("relations", len(arch.edges) >= contract.min_relations))
        # endpoint-side assertions: each edge's source and target resolve to a service.
        service_ids = {s.node_id for s in arch.services}
        endpoint_checks = 0
        for e in arch.edges:
            for end in _arch_edge_endpoints(e):
                checks.append((f"endpoint:{end}", end in service_ids))
                endpoint_checks += 1
        checks.append(("endpoint_count", endpoint_checks >= contract.min_endpoint_assertions))
    else:  # sequence
        geom = compile_sequence(_src(stem)).geometry
        checks.append(("participants", len(geom.participants) >= contract.min_nodes))
        checks.append(("messages", len(geom.messages) >= contract.min_relations))
        if contract.min_boxes:
            # Item 2 landed the shared sequence compiler, which surfaces `box`
            # geometry — the assertions item 1 deferred under the
            # `seq-box-membership-assertions` anchor. sequence-box-unsupported:
            # Group A = {Alice, Bob} (blue), Group B = {Carol} (rgb(200,100,50)),
            # Dave in neither box.
            checks.append(("boxes", len(geom.boxes) >= contract.min_boxes))
            by_label = {b.label: b for b in geom.boxes}
            checks.append(("box-labels", {"Group A", "Group B"} <= set(by_label)))
            if "Group A" in by_label:
                ga = by_label["Group A"]
                checks.append(("group-a-members", set(ga.participant_ids) == {"Alice", "Bob"}))
                checks.append(("group-a-color", ga.color.lower() == "blue"))
            if "Group B" in by_label:
                gb = by_label["Group B"]
                checks.append(("group-b-members", set(gb.participant_ids) == {"Carol"}))
                checks.append(("group-b-color", gb.color.replace(" ", "") == "rgb(200,100,50)"))
            # Dave belongs to no box.
            boxed = {pid for b in geom.boxes for pid in b.participant_ids}
            checks.append(("dave-unboxed", "Dave" not in boxed))
        if contract.min_fragments:
            checks.append(("fragments", len(geom.fragments) >= contract.min_fragments))
            # event-containment: every fragment names ≥1 participant it spans.
            checks.append((
                "fragment-participants",
                all(len(f.participant_ids) >= 1 for f in geom.fragments),
            ))
        if contract.min_branches:
            checks.append(("branches", len(geom.branches) >= contract.min_branches))
            # fragment-parent: each branch's parent resolves to a real fragment.
            frag_ids = {f.fragment_id for f in geom.fragments}
            checks.append((
                "branch-parent",
                all(b.parent_fragment_id in frag_ids for b in geom.branches),
            ))

    # Every declared check must hold, and the case must be non-vacuous.
    assert_non_vacuous("PASS", len(checks))
    failed = [name for name, ok in checks if not ok]
    assert not failed, f"{stem} contract failures: {failed} (counts below minimum)"
    assert len(checks) >= 2, f"{stem} executed too few assertions: {len(checks)}"


def _arch_edge_endpoints(edge) -> tuple[str, str]:
    """Resolve an architecture edge's source/target service ids across field-name variants."""
    for src_name, dst_name in (
        ("src_id", "dst_id"),
        ("source_id", "target_id"),
        ("source", "target"),
        ("from_id", "to_id"),
    ):
        if hasattr(edge, src_name) and hasattr(edge, dst_name):
            return getattr(edge, src_name), getattr(edge, dst_name)
    raise AssertionError(f"cannot resolve endpoints on architecture edge: {edge!r}")
