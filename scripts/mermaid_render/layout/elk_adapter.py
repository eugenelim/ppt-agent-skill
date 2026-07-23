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


class ElkUnavailable(RuntimeError):
    """Raised when ELK layout cannot run (Node absent, elkjs missing, env opt-out, or subprocess failure)."""


def _find_node() -> Optional[str]:
    return shutil.which("node")


def _find_elkjs() -> Optional[str]:
    candidate = Path(__file__).parent / "node_modules" / "elkjs" / "lib" / "elk.bundled.js"
    return str(candidate) if candidate.exists() else None


def _to_elk_json(graph: LayoutGraph, spacing: "dict | None" = None) -> dict:
    """Serialize LayoutGraph to an ELK JSON input dict.

    When graph.groups is non-empty, emits ELK container nodes for each group
    and sets elk.hierarchyHandling=INCLUDE_CHILDREN so ELK enforces group
    separation natively (Item 2).
    """
    group_ids = {g.id for g in graph.groups}

    # ── Organise nodes by parent group ──────────────────────────────────────
    group_direct_nodes: dict[str, list] = {g.id: [] for g in graph.groups}
    root_nodes: list = []

    for node in graph.nodes:
        child: dict = {
            "id": node.id,
            "width": node.measured_width,
            "height": node.measured_height,
        }
        if node.ports:
            child["ports"] = [
                {
                    "id": p.id,
                    "properties": {
                        "port.side": p.side,
                        "port.index": p.index,
                    },
                }
                for p in node.ports
            ]
        if node.parent_id and node.parent_id in group_ids:
            group_direct_nodes[node.parent_id].append(child)
        else:
            root_nodes.append(child)

    # ── Organise child groups by parent group ────────────────────────────────
    group_child_groups: dict[str, list] = {}
    for g in graph.groups:
        if g.parent_id and g.parent_id in group_ids:
            group_child_groups.setdefault(g.parent_id, []).append(g.id)

    # ── Build nested ELK container nodes recursively ────────────────────────
    def _build_group_container(gid: str) -> dict:
        children: list = list(group_direct_nodes.get(gid, []))
        for child_gid in group_child_groups.get(gid, []):
            children.append(_build_group_container(child_gid))
        container: dict = {"id": gid}
        if children:
            container["children"] = children
        return container

    # Root-level items: plain nodes + root group containers
    root_group_ids = {g.id for g in graph.groups if not g.parent_id}
    children: list = list(root_nodes)
    for g in graph.groups:
        if g.id in root_group_ids:
            children.append(_build_group_container(g.id))

    edges = []
    for edge in graph.edges:
        elk_edge: dict = {
            "id": edge.id,
            "sources": list(edge.sources),
            "targets": list(edge.targets),
        }
        if edge.source_port:
            elk_edge["sources"] = [f"{edge.sources[0]}:{edge.source_port}"]
        if edge.target_port:
            elk_edge["targets"] = [f"{edge.targets[0]}:{edge.target_port}"]
        edges.append(elk_edge)

    elk_direction = {
        "TB": "DOWN", "BT": "UP", "LR": "RIGHT", "RL": "LEFT",
    }.get(graph.direction, "DOWN")

    _sp = spacing or {}
    node_node = str(_sp.get("col_gap", 40))
    node_layers = str(_sp.get("rank_gap", 60))

    layout_options: dict = {
        "elk.algorithm": "layered",
        "elk.direction": elk_direction,
        "elk.edgeRouting": "ORTHOGONAL",
        # Item 3(a): improved obstacle-avoidance routing
        "elk.layered.unnecessaryBendpoints": "false",
        "elk.layered.nodePlacementStrategy": "BRANDES_KOEPF",
        "elk.layered.spacing.nodeNodeBetweenLayers": node_layers,
        "elk.spacing.nodeNode": node_node,
    }
    # Item 2: enable hierarchy handling when groups are present so ELK enforces
    # group-member locality natively.
    if graph.groups:
        layout_options["elk.hierarchyHandling"] = "INCLUDE_CHILDREN"

    return {
        "id": "root",
        "layoutOptions": layout_options,
        "children": children,
        "edges": edges,
    }


def _collect_positioned_nodes(
    children: list,
    offset_x: float,
    offset_y: float,
    node_map: dict,
    node_layouts: dict,
) -> None:
    """Recursively collect absolute-coordinate node positions from ELK output.

    ELK returns child positions relative to their parent container; this
    accumulates offsets so all NodeLayout objects use canvas-absolute coords.
    """
    for child in children:
        cid = child["id"]
        cx = offset_x + float(child.get("x", 0))
        cy = offset_y + float(child.get("y", 0))
        cw = float(child.get("width", 0))
        ch = float(child.get("height", 0))

        if cid in node_map:
            orig = node_map[cid]
            w = cw if cw > 0 else orig.measured_width
            h = ch if ch > 0 else orig.measured_height
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

        # Recurse into group containers and nested groups (with accumulated offset).
        if "children" in child:
            _collect_positioned_nodes(
                child["children"], cx, cy, node_map, node_layouts
            )


def _from_elk_result(out: dict, graph: LayoutGraph) -> FinalizedLayout:
    """Build FinalizedLayout from the positioned ELK output dict."""
    node_map = {n.id: n for n in graph.nodes}

    node_layouts: dict[str, NodeLayout] = {}
    _collect_positioned_nodes(
        out.get("children", []),
        offset_x=0.0,
        offset_y=0.0,
        node_map=node_map,
        node_layouts=node_layouts,
    )

    edge_map = {e.id: e for e in graph.edges}
    routed_edges: list[RoutedEdge] = []
    for elk_edge in out.get("edges", []):
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
        src_id = src_ids[0].split(":")[0] if src_ids else ""
        dst_id = dst_ids[0].split(":")[0] if dst_ids else ""

        src_pos = waypoints[0] if waypoints else Point(0.0, 0.0)
        dst_pos = waypoints[-1] if waypoints else Point(0.0, 0.0)

        src_port = PortLayout(
            node_id=src_id, side=PortSide.BOTTOM,
            position=src_pos, direction=Point(0.0, 1.0),
        )
        dst_port = PortLayout(
            node_id=dst_id, side=PortSide.TOP,
            position=dst_pos, direction=Point(0.0, -1.0),
        )

        src_mk = MarkerKind.NONE
        dst_mk = MarkerKind.ARROW
        if orig_edge is not None:
            src_mk = orig_edge.source_marker
            dst_mk = orig_edge.target_marker

        routed_edges.append(RoutedEdge(
            edge_id=eid,
            src_node_id=src_id,
            dst_node_id=dst_id,
            src_port=src_port,
            dst_port=dst_port,
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

    if node_layouts:
        all_rects = [nl.outer_bounds for nl in node_layouts.values()]
        node_union = Rect.union_all(all_rects)
        visible = node_union.inflate(48)
    else:
        node_union = Rect(0.0, 0.0, float(out.get("width", 500)), float(out.get("height", 300)))
        visible = node_union.inflate(48)
    canvas = node_union.inflate(96)

    return FinalizedLayout(
        node_layouts=node_layouts,
        group_layouts={},
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
