"""ELK layout adapter — calls elkjs 0.12.0 via a pinned Node.js subprocess.

Public API:
    layout_with_elk(graph: LayoutGraph) -> FinalizedLayout
    class ElkUnavailable(RuntimeError)

Exempted from tests/test_dependencies.py::TestNoSubprocess via _SUBPROCESS_EXEMPTIONS.
See docs/adr/001-elk-layout-engine.md for the ADR that governs this dependency.
"""
from __future__ import annotations

import json
import math
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
    """Serialize LayoutGraph to an ELK JSON input dict."""
    children = []
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
        children.append(child)

    # Groups become ELK children with their own children
    # (nested hierarchy handled by parent_id on LayoutNode)
    # For now, groups are flattened — ELK receives all nodes at root level
    # when no group hierarchy is set. This is refined in T5 wire-up.

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
    return {
        "id": "root",
        "layoutOptions": {
            "elk.algorithm": "layered",
            "elk.direction": elk_direction,
            "elk.edgeRouting": "ORTHOGONAL",
            "elk.layered.spacing.nodeNodeBetweenLayers": node_layers,
            "elk.spacing.nodeNode": node_node,
        },
        "children": children,
        "edges": edges,
    }


def _from_elk_result(out: dict, graph: LayoutGraph) -> FinalizedLayout:
    """Build FinalizedLayout from the positioned ELK output dict."""
    node_map = {n.id: n for n in graph.nodes}

    node_layouts: dict[str, NodeLayout] = {}
    for child in out.get("children", []):
        nid = child["id"]
        orig = node_map.get(nid)
        if orig is None:
            continue
        x, y = float(child.get("x", 0)), float(child.get("y", 0))
        w, h = float(child.get("width", orig.measured_width)), float(child.get("height", orig.measured_height))
        outer = Rect(x=x, y=y, w=w, h=h)
        label = orig.labels[0] if orig.labels else nid
        node_layouts[nid] = NodeLayout(
            node_id=nid,
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
        visible = Rect.union_all(all_rects).inflate(48)
    else:
        visible = Rect(0.0, 0.0, float(out.get("width", 500)), float(out.get("height", 300)))
    canvas = visible.inflate(48)

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


def layout_with_elk(graph: LayoutGraph) -> FinalizedLayout:
    """Run ELK layout on graph; raise ElkUnavailable when ELK cannot be used.

    Triggers:
    - MERMAID_LAYOUT_ENGINE=python env var → always raises ElkUnavailable
    - Node runtime absent → raises ElkUnavailable
    - elkjs node_modules missing → raises ElkUnavailable
    - Subprocess non-zero exit, malformed JSON, or timeout → raises ElkUnavailable
    """
    if os.environ.get("MERMAID_LAYOUT_ENGINE", "").lower() == "python":
        raise ElkUnavailable("MERMAID_LAYOUT_ENGINE=python: ELK disabled by env var")
    if _find_node() is None:
        raise ElkUnavailable("node runtime not found in PATH")
    if _find_elkjs() is None:
        raise ElkUnavailable(
            "elkjs not installed; run: npm ci --prefix scripts/mermaid_render/layout"
        )
    elk_json = _to_elk_json(graph)
    try:
        out = _run_elk(elk_json)
    except subprocess.TimeoutExpired as exc:
        raise ElkUnavailable(f"elk_runner.js timed out after {_ELK_TIMEOUT}s") from exc
    return _from_elk_result(out, graph)
