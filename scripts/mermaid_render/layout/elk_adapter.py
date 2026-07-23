"""ELK layout adapter — calls elkjs 0.12.0 via a pinned Node.js subprocess.

Public API:
    layout_with_elk(graph: LayoutGraph, spacing=None) -> FinalizedLayout
    class ElkUnavailable(RuntimeError)

Exempted from tests/test_dependencies.py::TestNoSubprocess via _SUBPROCESS_EXEMPTIONS.
See docs/adr/001-elk-layout-engine.md for the ADR that governs this dependency.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ._geometry import (
    FinalizedLayout, LayoutGraph, LayoutNode, LayoutGroup, LayoutEdge,
    NodeLayout, GroupLayout, RoutedEdge, PortLayout, PortSide, Point, Rect,
    EdgeLabelLayout, MarkerKind, TextLayout, _empty_diagnostics,
)

_ELK_RUNNER = Path(__file__).parent / "elk_runner.js"
_ELK_TIMEOUT = 30  # seconds

# Group padding constants (mirrors _constants.py — kept here to avoid a circular import)
_GROUP_PAD_Y_TOP = 36   # title strip reserved height (px)
_GROUP_PAD_X = 28       # horizontal inner padding (px)
_GROUP_PAD_Y_BOT = 28   # bottom inner padding (px)

# Mermaid direction → ELK direction string
_ELK_DIR = {"TB": "DOWN", "TD": "DOWN", "BT": "UP", "LR": "RIGHT", "RL": "LEFT"}


class ElkUnavailable(RuntimeError):
    """Raised when ELK layout cannot run (Node absent, elkjs missing, env opt-out, or subprocess failure)."""


def _find_node() -> Optional[str]:
    return shutil.which("node")


def _find_elkjs() -> Optional[str]:
    candidate = Path(__file__).parent / "node_modules" / "elkjs" / "lib" / "elk.bundled.js"
    return str(candidate) if candidate.exists() else None


def _to_elk_json(graph: LayoutGraph, spacing: "dict | None" = None) -> dict:
    """Serialize LayoutGraph to an ELK JSON input dict.

    When graph.groups is non-empty and nodes carry parent_id, groups become ELK
    compound parent nodes with their child nodes nested inside. Port constraints
    (FIXED_SIDE) are added when PortSpec objects are present. All edges are
    placed at root level so ELK handles cross-compound routing.
    """
    elk_direction = _ELK_DIR.get(graph.direction.upper(), "DOWN")
    _sp = spacing or {}
    node_node = str(_sp.get("col_gap", 40))
    node_layers = str(_sp.get("rank_gap", 60))
    shared_layout_opts: dict = {
        "elk.algorithm": "layered",
        "elk.direction": elk_direction,
        "elk.edgeRouting": "ORTHOGONAL",
        "elk.layered.unnecessaryBendpoints": "false",
        "elk.layered.nodePlacementStrategy": "BRANDES_KOEPF",
        "elk.layered.spacing.nodeNodeBetweenLayers": node_layers,
        "elk.spacing.nodeNode": node_node,
    }

    # Bucket nodes by parent_id: "" → root level
    children_by_parent: dict[str, list] = {}
    for node in graph.nodes:
        elk_node: dict = {
            "id": node.id,
            "width": node.measured_width,
            "height": node.measured_height,
        }
        if node.ports:
            elk_node["ports"] = [
                {
                    "id": p.id,
                    "properties": {
                        "port.side": p.side,
                        "port.index": p.index,
                    },
                }
                for p in node.ports
            ]
            elk_node["properties"] = {"portConstraints": "FIXED_SIDE"}
        children_by_parent.setdefault(node.parent_id or "", []).append(elk_node)

    # Build compound group ELK nodes
    for g in graph.groups:
        pad_top = _GROUP_PAD_Y_TOP
        if g.label_height > 0:
            pad_top = max(pad_top, int(g.label_height) + 8)

        # Per-group direction so `direction LR` inside a subgraph is honoured by ELK.
        elk_group_dir = _ELK_DIR.get((g.local_direction or graph.direction).upper(), "DOWN")

        group_children = children_by_parent.setdefault(g.id, [])
        g_node: dict = {
            "id": g.id,
            "children": group_children,
            "layoutOptions": dict(shared_layout_opts, **{
                "elk.direction": elk_group_dir,
                "elk.padding": (
                    f"[top={pad_top},right={_GROUP_PAD_X},"
                    f"bottom={_GROUP_PAD_Y_BOT},left={_GROUP_PAD_X}]"
                ),
            }),
        }
        if not group_children:
            # Empty compound node: give it a deterministic minimum size so ELK
            # positions it as a visible labeled box rather than collapsing to zero.
            min_w = max(float(_GROUP_PAD_X * 2 + 80), g.label_width + float(_GROUP_PAD_X * 2))
            min_h = float(pad_top + _GROUP_PAD_Y_BOT)
            g_node["width"] = min_w
            g_node["height"] = min_h
        else:
            if g.minimum_width > 0:
                g_node["width"] = g.minimum_width
            if g.minimum_height > 0:
                g_node["height"] = g.minimum_height
        children_by_parent.setdefault(g.parent_id or "", []).append(g_node)

    # Edges at root level; port IDs are referenced directly (globally unique)
    edges = []
    for edge in graph.edges:
        elk_edge: dict = {
            "id": edge.id,
            "sources": [edge.source_port] if edge.source_port else list(edge.sources),
            "targets": [edge.target_port] if edge.target_port else list(edge.targets),
        }
        edges.append(elk_edge)

    root_layout_opts = dict(shared_layout_opts)
    if graph.groups:
        root_layout_opts["elk.hierarchyHandling"] = "INCLUDE_CHILDREN"

    return {
        "id": "root",
        "layoutOptions": root_layout_opts,
        "children": children_by_parent.get("", []),
        "edges": edges,
    }


def _from_elk_result(out: dict, graph: LayoutGraph) -> FinalizedLayout:
    """Build FinalizedLayout from the positioned ELK output dict.

    Handles both flat and compound graph layouts. For compound layouts, group
    nodes appear as children and their service children are nested inside them.
    Positions are accumulated from parent offsets to produce absolute coordinates.
    """
    node_map = {n.id: n for n in graph.nodes}
    group_map = {g.id: g for g in graph.groups}
    # Port ID → node ID mapping for edge source/target decoding
    port_to_node = {p.id: n.id for n in graph.nodes for p in n.ports}

    node_layouts: dict[str, NodeLayout] = {}
    group_layouts: dict[str, GroupLayout] = {}

    def _visit(children: list, offset_x: float, offset_y: float) -> None:
        for child in children:
            cid = child["id"]
            cx = float(child.get("x", 0)) + offset_x
            cy = float(child.get("y", 0)) + offset_y
            cw = float(child.get("width", 0))
            ch = float(child.get("height", 0))

            orig = node_map.get(cid)
            if orig is not None:
                w = cw or orig.measured_width
                h = ch or orig.measured_height
                outer = Rect(x=cx, y=cy, w=w, h=h)
                node_layouts[cid] = NodeLayout(
                    node_id=cid,
                    semantic_shape=orig.shape_id,
                    outer_bounds=outer,
                    content_bounds=outer,
                    title_layout=TextLayout(
                        lines=(), width=w, height=h,
                        line_height=14.0, min_content_width=0.0, max_content_width=w,
                        resolved_font_path=None, resolved_font_family="sans-serif",
                    ),
                    subtitle_layout=None,
                    member_layouts=(),
                    icon_bounds=None,
                    ports=(),
                    css_classes=(),
                    extra_css="",
                    is_dummy=False,
                    rank=0,
                    is_external=False,
                    icon_svg="",
                    accent_color="",
                    parent_group_id=orig.parent_id,
                )

            g_orig = group_map.get(cid)
            if g_orig is not None:
                boundary = Rect(x=cx, y=cy, w=cw, h=ch)
                member_ids = tuple(n.id for n in graph.nodes if n.parent_id == cid)
                child_group_ids = tuple(g.id for g in graph.groups if g.parent_id == cid)
                group_layouts[cid] = GroupLayout(
                    group_id=cid,
                    parent_group_id=g_orig.parent_id,
                    boundary_bounds=boundary,
                    label_layout=None,
                    member_ids=member_ids,
                    child_group_ids=child_group_ids,
                    local_direction=g_orig.local_direction or graph.direction,
                )
                nested = child.get("children", [])
                if nested:
                    _visit(nested, cx, cy)

    _visit(out.get("children", []), 0.0, 0.0)

    def _collect_edges(node_dict: dict) -> list:
        result = list(node_dict.get("edges", []))
        for child in node_dict.get("children", []):
            result.extend(_collect_edges(child))
        return result

    edge_map = {e.id: e for e in graph.edges}
    routed_edges: list[RoutedEdge] = []
    for elk_edge in _collect_edges(out):
        eid = elk_edge.get("id", "")
        orig_edge = edge_map.get(eid)

        waypoints: list[Point] = []
        for section in elk_edge.get("sections", []):
            sp = section.get("startPoint", {})
            if sp:
                waypoints.append(Point(float(sp["x"]), float(sp["y"])))
            for bp in section.get("bendPoints", []):
                waypoints.append(Point(float(bp["x"]), float(bp["y"])))
            ep = section.get("endPoint", {})
            if ep:
                waypoints.append(Point(float(ep["x"]), float(ep["y"])))

        src_ids = list(elk_edge.get("sources", []))
        dst_ids = list(elk_edge.get("targets", []))
        src_ref = src_ids[0] if src_ids else ""
        dst_ref = dst_ids[0] if dst_ids else ""
        # Resolve: port ID → node ID, then "nodeId:portId" split, then as-is
        src_id = port_to_node.get(src_ref) or (src_ref.split(":")[0] if ":" in src_ref else src_ref)
        dst_id = port_to_node.get(dst_ref) or (dst_ref.split(":")[0] if ":" in dst_ref else dst_ref)

        src_pos = waypoints[0] if waypoints else Point(0.0, 0.0)
        dst_pos = waypoints[-1] if waypoints else Point(0.0, 0.0)
        src_mk = orig_edge.source_marker if orig_edge else MarkerKind.NONE
        dst_mk = orig_edge.target_marker if orig_edge else MarkerKind.ARROW

        routed_edges.append(RoutedEdge(
            edge_id=eid,
            src_node_id=src_id,
            dst_node_id=dst_id,
            src_port=PortLayout(node_id=src_id, side=PortSide.BOTTOM,
                                position=src_pos, direction=Point(0.0, 1.0)),
            dst_port=PortLayout(node_id=dst_id, side=PortSide.TOP,
                                position=dst_pos, direction=Point(0.0, -1.0)),
            waypoints=tuple(waypoints),
            edge_style="solid",
            has_marker_end=(dst_mk != MarkerKind.NONE),
            has_marker_start=(src_mk != MarkerKind.NONE),
            label_layout=None,
            src_label_layout=None,
            dst_label_layout=None,
            source_marker=src_mk,
            target_marker=dst_mk,
        ))

    all_rects = ([nl.outer_bounds for nl in node_layouts.values()]
                 + [gl.boundary_bounds for gl in group_layouts.values()])
    if all_rects:
        visible = Rect.union_all(all_rects).inflate(48)
        canvas = visible.inflate(48)
    else:
        fallback = Rect(0.0, 0.0, float(out.get("width", 500)), float(out.get("height", 300)))
        visible = fallback.inflate(48)
        canvas = fallback.inflate(96)

    return FinalizedLayout(
        node_layouts=node_layouts,
        group_layouts=group_layouts,
        routed_edges=tuple(routed_edges),
        visible_bounds=visible,
        diagram_padding=48.0,
        canvas_bounds=canvas,
        direction=graph.direction,
        diagnostics=_empty_diagnostics(),
    )


def _run_elk(elk_json: dict) -> dict:
    """Invoke elk_runner.js via subprocess and return the parsed result dict."""
    node = _find_node()
    if node is None:
        raise ElkUnavailable("node runtime not found")
    runner = str(_ELK_RUNNER)
    result = subprocess.run(
        [node, runner],
        input=json.dumps(elk_json),
        capture_output=True,
        text=True,
        timeout=_ELK_TIMEOUT,
    )
    if result.returncode != 0:
        raise ElkUnavailable(
            f"elk_runner.js exited {result.returncode}: {result.stderr.strip()[:200]}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ElkUnavailable(f"elk_runner.js returned malformed JSON: {exc}") from exc


def layout_with_elk(graph: LayoutGraph, spacing: "dict | None" = None) -> FinalizedLayout:
    """Run ELK layout on graph; raise ElkUnavailable when ELK cannot be used.

    Triggers:
    - MERMAID_LAYOUT_ENGINE=python env var → always raises ElkUnavailable
    - Node runtime absent → raises ElkUnavailable
    - elkjs node_modules missing → raises ElkUnavailable
    - Subprocess non-zero exit, malformed JSON, or timeout → raises ElkUnavailable

    spacing: optional dict with col_gap / rank_gap / diagram_padding to pass to
    _to_elk_json.  _compile_flowchart passes _init_cfg here so both code paths
    use identical spacing — the unification point for Item 1.
    """
    if os.environ.get("MERMAID_LAYOUT_ENGINE", "").lower() == "python":
        raise ElkUnavailable("MERMAID_LAYOUT_ENGINE=python: ELK disabled by env var")
    if _find_node() is None:
        raise ElkUnavailable("node runtime not found in PATH")
    if _find_elkjs() is None:
        raise ElkUnavailable(
            "elkjs not installed; run: npm ci --prefix scripts/mermaid_render/layout"
        )
    elk_json = _to_elk_json(graph, spacing=spacing)
    try:
        out = _run_elk(elk_json)
    except subprocess.TimeoutExpired as exc:
        raise ElkUnavailable(f"elk_runner.js timed out after {_ELK_TIMEOUT}s") from exc
    return _from_elk_result(out, graph)
