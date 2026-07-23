"""TDD tests for finalized_layout_to_scene().

Tests are written first (red), then paint.py is updated to make them green.
"""
from __future__ import annotations
from types import MappingProxyType

import pytest

from scripts.mermaid_render.layout._geometry import (
    Point, Rect, FinalizedLayout, NodeLayout, GroupLayout,
    RoutedEdge, EdgeLabelLayout, TextLayout, TextLine, TextRun, TextStyle,
    LayoutDiagnostics, PortLayout, PortSide,
)
from scripts.mermaid_render.scene import (
    SvgScene, ScenePath, SceneRect, SceneRoundedRect, SceneCircle, ScenePolygon,
    SceneText, SceneTextLine, SceneGroup, MarkerDefinition,
    LAYER_NODES, LAYER_EDGES, LAYER_LABELS, LAYER_BOUNDARIES, LAYER_BACKGROUND,
    LAYER_ORDER,
)


# ── Fixture helpers ────────────────────────────────────────────────────────────

def _ts(font_size: float = 13.0, font_weight: int = 600) -> TextStyle:
    return TextStyle(font_size=font_size, font_weight=font_weight)


def _run(text: str, size: float = 13.0) -> TextRun:
    return TextRun(
        text=text,
        style=_ts(font_size=size),
        width=float(len(text) * 7),
        height=size * 1.2,
    )


def _text_layout(text: str, size: float = 13.0) -> TextLayout:
    r = _run(text, size)
    line = TextLine(runs=(r,), width=r.width, height=r.height, baseline=r.height * 0.8)
    return TextLayout(
        lines=(line,),
        width=r.width,
        height=r.height * 1.2,
        line_height=r.height,
        min_content_width=r.width,
        max_content_width=r.width,
        resolved_font_path=None,
        resolved_font_family="sans-serif",
    )


def _port(node_id: str, side: PortSide = PortSide.BOTTOM, x: float = 0.0, y: float = 0.0) -> PortLayout:
    return PortLayout(
        node_id=node_id,
        side=side,
        position=Point(x, y),
        direction=Point(0.0, 1.0),
    )


def _node(
    node_id: str,
    x: float = 10.0, y: float = 20.0, w: float = 120.0, h: float = 50.0,
    shape: str = "rect",
    title: str = "Node Label",
    accent: str = "#4a90d9",
    rank: int = 0,
    is_dummy: bool = False,
    member_texts: tuple[str, ...] = (),
) -> NodeLayout:
    members = tuple(_text_layout(m) for m in member_texts)
    return NodeLayout(
        node_id=node_id,
        semantic_shape=shape,
        outer_bounds=Rect(x, y, w, h),
        content_bounds=Rect(x + 4, y + 4, w - 8, h - 8),
        title_layout=_text_layout(title) if title else None,
        subtitle_layout=None,
        member_layouts=members,
        icon_bounds=None,
        ports=(_port(node_id, PortSide.BOTTOM, x + w / 2, y + h),),
        css_classes=(),
        extra_css="",
        is_dummy=is_dummy,
        rank=rank,
        is_external=False,
        icon_svg="",
        accent_color=accent,
    )


def _edge(
    src: str, dst: str,
    waypoints: tuple = None,
    has_marker_end: bool = True,
    has_marker_start: bool = False,
    edge_style: str = "solid",
    label: str = "",
) -> RoutedEdge:
    from scripts.mermaid_render.layout._geometry import MarkerKind
    if waypoints is None:
        waypoints = (Point(10.0, 70.0), Point(10.0, 100.0), Point(130.0, 100.0))
    label_layout = None
    if label:
        label_layout = EdgeLabelLayout(
            text=label,
            layout=_text_layout(label),
            bounds=Rect(50.0, 95.0, 40.0, 14.0),
            anchor_point=Point(70.0, 100.0),
        )
    return RoutedEdge(
        edge_id=f"{src}-{dst}",
        src_node_id=src, dst_node_id=dst,
        src_port=_port(src, PortSide.BOTTOM),
        dst_port=_port(dst, PortSide.TOP),
        waypoints=waypoints,
        edge_style=edge_style,
        has_marker_end=has_marker_end,
        has_marker_start=has_marker_start,
        label_layout=label_layout,
        src_label_layout=None,
        dst_label_layout=None,
        source_marker=MarkerKind.ARROW if has_marker_start else MarkerKind.NONE,
        target_marker=MarkerKind.ARROW if has_marker_end else MarkerKind.NONE,
    )


def _group(
    group_id: str,
    x: float = 0.0, y: float = 0.0, w: float = 300.0, h: float = 200.0,
    label: str = "Group A",
) -> GroupLayout:
    return GroupLayout(
        group_id=group_id,
        parent_group_id=None,
        boundary_bounds=Rect(x, y, w, h),
        label_layout=_text_layout(label) if label else None,
        member_ids=(),
        child_group_ids=(),
        local_direction="TB",
    )


def _layout(
    nodes: dict = None,
    groups: dict = None,
    edges: tuple = (),
    canvas_w: float = 800.0,
    canvas_h: float = 400.0,
) -> FinalizedLayout:
    return FinalizedLayout(
        node_layouts=MappingProxyType(nodes or {"A": _node("A")}),
        group_layouts=MappingProxyType(groups or {}),
        routed_edges=edges,
        visible_bounds=Rect(0.0, 0.0, canvas_w, canvas_h),
        diagram_padding=20.0,
        canvas_bounds=Rect(0.0, 0.0, canvas_w, canvas_h),
        direction="TB",
        diagnostics=LayoutDiagnostics(
            unsupported_options=(), route_failures=(), warnings=(),
        ),
    )


# Target under test (imported after fixture defs so import error appears clearly)
from scripts.mermaid_render.paint import finalized_layout_to_scene


# ── Basic structure ───────────────────────────────────────────────────────────

def test_returns_svg_scene():
    scene = finalized_layout_to_scene(_layout(), diagram_type="flowchart")
    assert isinstance(scene, SvgScene)


def test_canvas_bounds_map_to_dimensions():
    scene = finalized_layout_to_scene(_layout(canvas_w=600.0, canvas_h=300.0), diagram_type="flowchart")
    assert scene.width == 600.0
    assert scene.height == 300.0


def test_scene_has_all_layer_names():
    scene = finalized_layout_to_scene(_layout(), diagram_type="flowchart")
    names = {name for name, _ in scene.layers}
    for name in LAYER_ORDER:
        assert name in names, f"Layer {name!r} missing from scene"


# ── Node → nodes layer ────────────────────────────────────────────────────────

def test_node_outer_bounds_map_to_element_position():
    """NodeLayout.outer_bounds x,y,w,h appear on a scene element in nodes layer."""
    nl = _node("A", x=42.0, y=17.0, w=150.0, h=60.0)
    scene = finalized_layout_to_scene(_layout(nodes={"A": nl}), diagram_type="flowchart")

    found = any(
        getattr(el, "x", None) == 42.0
        and getattr(el, "y", None) == 17.0
        and getattr(el, "w", None) == 150.0
        and getattr(el, "h", None) == 60.0
        for el in scene.get_layer(LAYER_NODES)
    )
    assert found, "outer_bounds (42,17,150,60) not found in nodes layer"


def test_node_outer_bounds_x_observable():
    nl = _node("A", x=77.5)
    scene = finalized_layout_to_scene(_layout(nodes={"A": nl}), diagram_type="flowchart")
    xs = [getattr(el, "x", None) for el in scene.get_layer(LAYER_NODES)]
    assert 77.5 in xs


def test_node_accent_color_in_stroke():
    """NodeLayout.accent_color reflects as stroke color on scene element."""
    nl = _node("A", accent="#ff0000")
    scene = finalized_layout_to_scene(_layout(nodes={"A": nl}), diagram_type="flowchart")
    stroke_colors = [
        getattr(getattr(getattr(el, "paint", None), "stroke", None), "color", None)
        for el in scene.get_layer(LAYER_NODES)
    ]
    assert "#ff0000" in stroke_colors, f"accent_color not in stroke colors: {stroke_colors}"


def test_dummy_nodes_excluded():
    real = _node("A", title="Real")
    dummy = _node("D", title="Dummy", is_dummy=True)
    scene = finalized_layout_to_scene(_layout(nodes={"A": real, "D": dummy}), diagram_type="flowchart")
    dummy_ids = [
        el for el in scene.get_layer(LAYER_NODES)
        if any(k == "node-id" and v == "D" for k, v in getattr(el, "data_attrs", ()))
    ]
    assert not dummy_ids, "Dummy node leaked into nodes layer"


# ── Title layout → labels layer ───────────────────────────────────────────────

def test_node_title_text_appears_in_labels():
    nl = _node("A", title="Hello World")
    scene = finalized_layout_to_scene(_layout(nodes={"A": nl}), diagram_type="flowchart")
    texts = [
        line.text
        for el in scene.get_layer(LAYER_LABELS) if isinstance(el, SceneText)
        for line in el.lines
    ]
    assert any("Hello World" in t for t in texts), f"Title missing from labels. Got: {texts}"


def test_title_parameter_appears_in_background():
    scene = finalized_layout_to_scene(_layout(), diagram_type="flowchart", title="My Diagram")
    texts = [
        line.text
        for el in scene.get_layer(LAYER_BACKGROUND) if isinstance(el, SceneText)
        for line in el.lines
    ]
    assert any("My Diagram" in t for t in texts), f"Title not in background: {texts}"


# ── RoutedEdge → edges layer ──────────────────────────────────────────────────

def test_routed_edge_waypoints_produce_scene_path():
    e = _edge("A", "B", waypoints=(Point(10.0, 70.0), Point(90.0, 120.0)))
    scene = finalized_layout_to_scene(
        _layout(nodes={"A": _node("A"), "B": _node("B", y=130.0)}, edges=(e,)),
        diagram_type="flowchart",
    )
    paths = [el for el in scene.get_layer(LAYER_EDGES) if isinstance(el, ScenePath)]
    assert paths, "No ScenePath in edges layer"
    assert paths[0].commands[0] == ("M", 10.0, 70.0)
    assert paths[0].commands[1] == ("L", 90.0, 120.0)


def test_edge_src_dst_in_data_attrs():
    e = _edge("src-node", "dst-node")
    scene = finalized_layout_to_scene(
        _layout(
            nodes={"src-node": _node("src-node"), "dst-node": _node("dst-node", y=130.0)},
            edges=(e,),
        ),
        diagram_type="flowchart",
    )
    paths = [el for el in scene.get_layer(LAYER_EDGES) if isinstance(el, ScenePath)]
    assert paths
    data = dict(paths[0].data_attrs)
    assert data.get("src") == "src-node"
    assert data.get("dst") == "dst-node"


def test_edge_label_appears_in_labels_layer():
    e = _edge("A", "B", label="my label")
    scene = finalized_layout_to_scene(
        _layout(nodes={"A": _node("A"), "B": _node("B", y=130.0)}, edges=(e,)),
        diagram_type="flowchart",
    )
    texts = [
        line.text
        for el in scene.get_layer(LAYER_LABELS) if isinstance(el, SceneText)
        for line in el.lines
    ]
    assert any("my label" in t for t in texts), f"Edge label missing. Got: {texts}"


# ── Markers ───────────────────────────────────────────────────────────────────

def test_has_marker_end_produces_marker_def():
    e = _edge("A", "B", has_marker_end=True)
    scene = finalized_layout_to_scene(
        _layout(nodes={"A": _node("A"), "B": _node("B", y=130.0)}, edges=(e,)),
        diagram_type="flowchart",
    )
    marker_defs = [d for d in scene.definitions if isinstance(d, MarkerDefinition)]
    assert marker_defs, "No MarkerDefinition when has_marker_end=True"
    paths = [el for el in scene.get_layer(LAYER_EDGES) if isinstance(el, ScenePath)]
    assert paths[0].marker_end
    assert paths[0].marker_end in {m.marker_id for m in marker_defs}


def test_no_marker_end_no_end_marker_def():
    e = _edge("A", "B", has_marker_end=False)
    scene = finalized_layout_to_scene(
        _layout(nodes={"A": _node("A"), "B": _node("B", y=130.0)}, edges=(e,)),
        diagram_type="flowchart",
    )
    end_markers = [
        d for d in scene.definitions
        if isinstance(d, MarkerDefinition) and d.marker_type == "arrow-end"
    ]
    assert not end_markers
    paths = [el for el in scene.get_layer(LAYER_EDGES) if isinstance(el, ScenePath)]
    assert not paths[0].marker_end


def test_has_marker_start_produces_bidir_marker():
    e = _edge("A", "B", has_marker_start=True, has_marker_end=True)
    scene = finalized_layout_to_scene(
        _layout(nodes={"A": _node("A"), "B": _node("B", y=130.0)}, edges=(e,)),
        diagram_type="flowchart",
    )
    types = {d.marker_type for d in scene.definitions if isinstance(d, MarkerDefinition)}
    assert "arrow-start" in types
    paths = [el for el in scene.get_layer(LAYER_EDGES) if isinstance(el, ScenePath)]
    assert paths[0].marker_start


def test_no_edges_no_marker_defs():
    scene = finalized_layout_to_scene(_layout(edges=()), diagram_type="flowchart")
    assert not [d for d in scene.definitions if isinstance(d, MarkerDefinition)]


# ── Groups → boundaries layer ─────────────────────────────────────────────────

def test_group_boundary_bounds_in_boundaries_layer():
    g = _group("G1", x=5.0, y=5.0, w=300.0, h=200.0)
    scene = finalized_layout_to_scene(
        _layout(nodes={"A": _node("A")}, groups={"G1": g}),
        diagram_type="flowchart",
    )
    bounds_layer = scene.get_layer(LAYER_BOUNDARIES)
    assert bounds_layer, "Boundaries layer empty"

    def _has_group_rect(el):
        if isinstance(el, SceneGroup):
            return any(
                getattr(child, "x", None) == 5.0
                and getattr(child, "y", None) == 5.0
                and getattr(child, "w", None) == 300.0
                and getattr(child, "h", None) == 200.0
                for child in el.children
            )
        return False

    assert any(_has_group_rect(el) for el in bounds_layer), (
        "Group rect (5,5,300,200) not found in boundaries layer"
    )


def test_group_label_in_boundary_group():
    g = _group("G1", label="My Group Label")
    scene = finalized_layout_to_scene(
        _layout(nodes={"A": _node("A")}, groups={"G1": g}),
        diagram_type="flowchart",
    )
    bounds_layer = scene.get_layer(LAYER_BOUNDARIES)
    all_texts = []
    for el in bounds_layer:
        if isinstance(el, SceneGroup):
            for child in el.children:
                if isinstance(child, SceneText):
                    all_texts.extend(line.text for line in child.lines)
    assert any("My Group Label" in t for t in all_texts), (
        f"Group label missing. Got: {all_texts}"
    )


# ── Determinism ───────────────────────────────────────────────────────────────

def test_deterministic_same_input_same_bytes():
    from scripts.mermaid_render.svg_serializer import scene_to_svg

    e = _edge("A", "B")

    def _make_layout():
        return _layout(
            nodes={"A": _node("A", title="Alpha"), "B": _node("B", title="Beta", y=150.0)},
            edges=(e,),
        )

    svg1 = scene_to_svg(finalized_layout_to_scene(_make_layout(), diagram_type="flowchart", title="T"))
    svg2 = scene_to_svg(finalized_layout_to_scene(_make_layout(), diagram_type="flowchart", title="T"))
    assert svg1 == svg2


# ── Newly consumed fields ─────────────────────────────────────────────────────

def test_is_external_produces_dashed_border():
    """NodeLayout.is_external=True → dashed stroke on node paint."""
    from scripts.mermaid_render.layout._geometry import NodeLayout
    import dataclasses
    nl_ext = dataclasses.replace(
        _node("A"),
        is_external=True,
    )
    scene = finalized_layout_to_scene(_layout(nodes={"A": nl_ext}), diagram_type="flowchart")
    nodes_layer = scene.get_layer(LAYER_NODES)
    stroke_dashes = [
        getattr(getattr(getattr(el, "paint", None), "stroke", None), "dasharray", None)
        for el in nodes_layer
    ]
    assert any(d for d in stroke_dashes if d), (
        f"is_external=True should produce dashed stroke; got dasharray values: {stroke_dashes}"
    )


def test_subtitle_layout_text_appears_in_labels():
    """NodeLayout.subtitle_layout text appears in the labels layer."""
    import dataclasses
    nl_sub = dataclasses.replace(
        _node("A", title="Main Title"),
        subtitle_layout=_text_layout("Sub Description"),
    )
    scene = finalized_layout_to_scene(_layout(nodes={"A": nl_sub}), diagram_type="flowchart")
    texts = [
        line.text
        for el in scene.get_layer(LAYER_LABELS) if isinstance(el, SceneText)
        for line in el.lines
    ]
    assert any("Sub Description" in t for t in texts), (
        f"subtitle_layout text 'Sub Description' missing from labels. Got: {texts}"
    )


# ── Reflective field-coverage parity test ─────────────────────────────────────

def test_node_layout_field_coverage_reflective():
    """Every NodeLayout field is either consumed (observable in scene) or explicitly declared.

    This test uses dataclasses.fields(NodeLayout) so no new field can be added without
    either being consumed by finalized_layout_to_scene() or added to the declared set below.
    """
    import dataclasses
    from scripts.mermaid_render.layout._geometry import NodeLayout

    # Fields whose values are not mapped to SVG scene elements, with documented reasons:
    # - content_bounds: inner text area; outer_bounds is used for positioning; text uses title_layout
    # - icon_bounds: HTML icon placement rect; no native SVG icon rendering yet
    # - ports: pre-computed routing ports; routing is encoded in RoutedEdge.waypoints
    # - extra_css: HTML-only CSS override; inserting raw CSS violates the no-foreignObject constraint
    # - rank: layout rank (topological order); non-visual metadata
    # - icon_svg: HTML inline SVG icon; inserting user SVG violates no-user-SVG constraint
    # - parent_group_id: layout hierarchy metadata for compound layout (Stage 4);
    #   group membership is rendered via GroupLayout boundaries, not per-node
    _DECLARED_NON_CONSUMED: set[str] = {
        "content_bounds",
        "icon_bounds",
        "ports",
        "extra_css",
        "rank",
        "icon_svg",
        "parent_group_id",  # subgraph membership metadata; grouping is encoded in FinalizedLayout.groups
    }

    # Build a comprehensive fixture with non-None/non-default values for all consumable fields
    nl = NodeLayout(
        node_id="test-node",
        semantic_shape="rect",
        outer_bounds=Rect(50.0, 60.0, 140.0, 55.0),
        content_bounds=Rect(54.0, 64.0, 132.0, 47.0),
        title_layout=_text_layout("Reflective Title"),
        subtitle_layout=_text_layout("Reflective Subtitle"),
        member_layouts=(_text_layout("member: str"),),
        icon_bounds=Rect(56.0, 66.0, 24.0, 24.0),
        ports=(_port("test-node", PortSide.BOTTOM, 120.0, 115.0),),
        css_classes=("node-custom",),
        extra_css="border-radius:4px;",
        is_dummy=False,
        rank=3,
        is_external=True,
        icon_svg="<svg/>",
        accent_color="#abcdef",
    )
    scene = finalized_layout_to_scene(_layout(nodes={"test-node": nl}), diagram_type="flowchart")

    all_field_names = {f.name for f in dataclasses.fields(NodeLayout)}
    consumed_fields = all_field_names - _DECLARED_NON_CONSUMED

    def _scene_texts(scene):
        texts = []
        for layer_name in ("nodes", "labels", "boundaries", "background"):
            for el in scene.get_layer(layer_name):
                if isinstance(el, SceneText):
                    texts.extend(line.text for line in el.lines)
        return texts

    # Verify each consumed field leaves an observable trace
    field_checks = {
        "node_id": lambda: any(
            v == "test-node"
            for el in scene.get_layer(LAYER_NODES)
            for k, v in getattr(el, "data_attrs", ())
        ),
        "semantic_shape": lambda: bool(scene.get_layer(LAYER_NODES)),
        "outer_bounds": lambda: any(
            getattr(el, "x", None) == 50.0 and getattr(el, "y", None) == 60.0
            for el in scene.get_layer(LAYER_NODES)
        ),
        "title_layout": lambda: any("Reflective Title" in t for t in _scene_texts(scene)),
        "subtitle_layout": lambda: any("Reflective Subtitle" in t for t in _scene_texts(scene)),
        "member_layouts": lambda: any("member" in t for t in _scene_texts(scene)),
        "css_classes": lambda: any(
            "node-custom" in getattr(el, "css_classes", ())
            for el in scene.get_layer(LAYER_NODES)
        ),
        "is_dummy": lambda: bool(scene.get_layer(LAYER_NODES)),  # False → node IS in scene
        "is_external": lambda: any(
            getattr(getattr(getattr(el, "paint", None), "stroke", None), "dasharray", None)
            for el in scene.get_layer(LAYER_NODES)
        ),
        "accent_color": lambda: any(
            getattr(getattr(getattr(el, "paint", None), "stroke", None), "color", None) == "#abcdef"
            for el in scene.get_layer(LAYER_NODES)
        ),
    }

    # Assert every consumed field that has a check passes
    for field_name, check in field_checks.items():
        assert field_name in consumed_fields, f"{field_name} listed in checks but not in consumed_fields"
        assert check(), f"Consumed NodeLayout field {field_name!r} not observable in SvgScene"

    # Assert the union covers all fields (no unchecked field is silently present)
    checked_fields = set(field_checks.keys())
    unchecked_consumed = consumed_fields - checked_fields
    assert not unchecked_consumed, (
        f"Consumed fields missing from reflective checks: {unchecked_consumed}. "
        "Either add them to field_checks or move them to _DECLARED_NON_CONSUMED."
    )


def test_routed_edge_field_coverage_reflective():
    """Every RoutedEdge field is either consumed (observable in scene) or explicitly declared."""
    import dataclasses
    from scripts.mermaid_render.layout._geometry import RoutedEdge

    # Fields not mapped to SVG scene elements, with documented reasons:
    # - src_port: port allocation metadata; routing already encoded in waypoints
    # - dst_port: port allocation metadata; routing already encoded in waypoints
    # - src_label_layout: edge source multiplicity (e.g. "0..*"); deferred (backlog-mermaid-p3-type-migrations)
    # - dst_label_layout: edge target multiplicity; deferred (backlog-mermaid-p3-type-migrations)
    # - is_reversed: back-edge flag; currently rendered identically to forward edges
    # - route_diagnostics: diagnostic string ("ok"/"fallback"/...); non-visual metadata
    # - has_marker_end: legacy bool derived from target_marker; paint.py now uses target_marker directly
    # - has_marker_start: legacy bool derived from source_marker; paint.py now uses source_marker directly
    _DECLARED_NON_CONSUMED: set[str] = {
        "src_port",
        "dst_port",
        "src_label_layout",
        "dst_label_layout",
        "is_reversed",
        "route_diagnostics",
        "has_marker_end",
        "has_marker_start",
    }

    from scripts.mermaid_render.layout._geometry import MarkerKind as _MarkerKindT
    edge = RoutedEdge(
        edge_id="test-edge",
        src_node_id="src-node",
        dst_node_id="dst-node",
        src_port=_port("src-node", PortSide.BOTTOM, 10.0, 70.0),
        dst_port=_port("dst-node", PortSide.TOP, 10.0, 120.0),
        waypoints=(Point(10.0, 70.0), Point(10.0, 95.0), Point(130.0, 95.0)),
        edge_style="dotted",
        has_marker_end=True,
        has_marker_start=True,
        label_layout=EdgeLabelLayout(
            text="edge label text",
            layout=_text_layout("edge label text"),
            bounds=Rect(50.0, 90.0, 60.0, 14.0),
            anchor_point=Point(80.0, 95.0),
        ),
        src_label_layout=None,
        dst_label_layout=None,
        is_reversed=False,
        route_diagnostics="ok",
        source_marker=_MarkerKindT.ARROW,
        target_marker=_MarkerKindT.ARROW,
    )
    layout = _layout(
        nodes={
            "src-node": _node("src-node"),
            "dst-node": _node("dst-node", y=130.0),
        },
        edges=(edge,),
    )
    scene = finalized_layout_to_scene(layout, diagram_type="flowchart")

    all_field_names = {f.name for f in dataclasses.fields(RoutedEdge)}
    consumed_fields = all_field_names - _DECLARED_NON_CONSUMED

    paths = [el for el in scene.get_layer(LAYER_EDGES) if isinstance(el, ScenePath)]
    labels = [
        line.text
        for el in scene.get_layer(LAYER_LABELS) if isinstance(el, SceneText)
        for line in el.lines
    ]
    marker_types = {d.marker_type for d in scene.definitions if isinstance(d, MarkerDefinition)}

    field_checks = {
        "edge_id": lambda: bool(paths) and "test-edge" in paths[0].element_id or "src-node" in paths[0].element_id,
        "src_node_id": lambda: bool(paths) and dict(paths[0].data_attrs).get("src") == "src-node",
        "dst_node_id": lambda: bool(paths) and dict(paths[0].data_attrs).get("dst") == "dst-node",
        "waypoints": lambda: bool(paths) and paths[0].commands[0] == ("M", 10.0, 70.0),
        "edge_style": lambda: bool(paths) and bool(
            getattr(getattr(getattr(paths[0], "paint", None), "stroke", None), "dasharray", None)
        ),
        "source_marker": lambda: bool(paths) and bool(paths[0].marker_start),
        "target_marker": lambda: bool(paths) and bool(paths[0].marker_end),
        "label_layout": lambda: any("edge label text" in t for t in labels),
    }

    for field_name, check in field_checks.items():
        assert field_name in consumed_fields, f"{field_name} in checks but not consumed"
        assert check(), f"Consumed RoutedEdge field {field_name!r} not observable in SvgScene"

    unchecked_consumed = consumed_fields - set(field_checks.keys())
    assert not unchecked_consumed, (
        f"Consumed RoutedEdge fields missing from checks: {unchecked_consumed}"
    )
