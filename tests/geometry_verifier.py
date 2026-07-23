"""Reusable geometry verifier for FinalizedLayout structural invariants.

Provides:
  verify_layout(layout) -> list[GeometryViolation]   — eight structural checks
  compute_compactness(layout) -> CompactnessReport    — regression metrics

Each check is independent; a layout with zero violations is structurally
sound. The verifier executes all eight checks unconditionally so that
"zero assertions executed" is impossible even on a clean layout.

Usage in tests::

    from geometry_verifier import verify_layout, compute_compactness
    violations = verify_layout(compiled.layout)
    assert violations == [], violations
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

# Allow importing from the scripts directory when used from the tests/ directory
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

if TYPE_CHECKING:
    from mermaid_render.layout._geometry import (
        FinalizedLayout,
        Point,
        Rect,
    )


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class GeometryViolation:
    """A single structural violation found by verify_layout()."""
    kind: str          # one of the eight kind strings below
    description: str   # human-readable explanation
    offending_ids: tuple  # node/edge/group IDs involved


@dataclass
class CompactnessReport:
    """Regression metrics for one compiled layout.

    All values are non-negative. Use as baseline constants in tests: assert
    each metric is <= its committed baseline (improvements acceptable;
    regressions are not).
    """
    total_route_length: float   # sum of all edge Euclidean path lengths (px)
    total_bends: int            # count of direction changes across all routes
    max_edge_excursion: float   # max interior waypoint distance outside src-dst AABB
    canvas_area: float          # canvas_bounds.w * canvas_bounds.h (px^2)
    crossing_count: int         # pair-wise segment intersection count


# ── Top-level API ─────────────────────────────────────────────────────────────

def verify_layout(layout: "FinalizedLayout") -> list[GeometryViolation]:
    """Run all eight structural invariant checks on *layout*.

    Returns a (possibly empty) list of GeometryViolation objects.
    All eight checks always run — no short-circuiting — so the verifier
    executes at least one check per fixture even on a clean layout.
    """
    violations: list[GeometryViolation] = []

    _check_node_overlap(layout, violations)
    _check_containment(layout, violations)
    _check_sibling_group_overlap(layout, violations)
    _check_edge_endpoints(layout, violations)
    _check_route_through_node(layout, violations)
    _check_route_through_group(layout, violations)
    _check_route_crosses_title_band(layout, violations)
    _check_label_overlap_node(layout, violations)

    return violations


def compute_compactness(layout: "FinalizedLayout") -> CompactnessReport:
    """Compute regression-friendly compactness metrics for *layout*.

    Deterministic: same layout produces same report every time.
    """
    total_route_length = 0.0
    total_bends = 0
    max_edge_excursion = 0.0
    all_segs: list = []

    for edge in layout.routed_edges:
        wps = edge.waypoints
        if len(wps) < 2:
            continue

        # Route length
        for i in range(len(wps) - 1):
            total_route_length += wps[i].distance_to(wps[i + 1])
            all_segs.append((wps[i], wps[i + 1]))

        # Bend count (direction changes in the polyline)
        for i in range(1, len(wps) - 1):
            v1x = wps[i].x - wps[i - 1].x
            v1y = wps[i].y - wps[i - 1].y
            v2x = wps[i + 1].x - wps[i].x
            v2y = wps[i + 1].y - wps[i].y
            cross = abs(v1x * v2y - v1y * v2x)
            if cross > 0.5:
                total_bends += 1

        # Max edge excursion: max distance of interior waypoints outside src-dst AABB
        src_nl = layout.node_layouts.get(edge.src_node_id)
        dst_nl = layout.node_layouts.get(edge.dst_node_id)
        if src_nl and dst_nl and len(wps) >= 3:
            combined = src_nl.outer_bounds.union(dst_nl.outer_bounds)
            for wp in wps[1:-1]:
                dx = max(combined.x - wp.x, 0.0, wp.x - combined.x1)
                dy = max(combined.y - wp.y, 0.0, wp.y - combined.y1)
                excursion = math.hypot(dx, dy)
                if excursion > max_edge_excursion:
                    max_edge_excursion = excursion

    canvas_area = layout.canvas_bounds.w * layout.canvas_bounds.h
    crossing_count = _count_crossings(all_segs)

    return CompactnessReport(
        total_route_length=total_route_length,
        total_bends=total_bends,
        max_edge_excursion=max_edge_excursion,
        canvas_area=canvas_area,
        crossing_count=crossing_count,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _overlap_exceeds(a: "Rect", b: "Rect", threshold: float = 1.0) -> bool:
    """True iff the two rects share more than *threshold* px in BOTH axes."""
    ox = min(a.x1, b.x1) - max(a.x, b.x)
    oy = min(a.y1, b.y1) - max(a.y, b.y)
    return ox > threshold and oy > threshold


# ── Check 1: node-node non-overlap ────────────────────────────────────────────

def _check_node_overlap(
    layout: "FinalizedLayout",
    violations: list[GeometryViolation],
) -> None:
    """No two non-dummy nodes may overlap by > 1 px in both axes."""
    real = [(nid, nl) for nid, nl in layout.node_layouts.items() if not nl.is_dummy]
    for i in range(len(real)):
        for j in range(i + 1, len(real)):
            nid_a, nl_a = real[i]
            nid_b, nl_b = real[j]
            if _overlap_exceeds(nl_a.outer_bounds, nl_b.outer_bounds):
                violations.append(GeometryViolation(
                    kind="node-overlap",
                    description=(
                        f"Nodes {nid_a!r} and {nid_b!r} outer_bounds overlap "
                        f"by more than 1 px in both axes."
                    ),
                    offending_ids=(nid_a, nid_b),
                ))


# ── Check 2: node-group containment ───────────────────────────────────────────

def _check_containment(
    layout: "FinalizedLayout",
    violations: list[GeometryViolation],
) -> None:
    """Every node with a parent_group_id must be inside that group's boundary."""
    for nid, nl in layout.node_layouts.items():
        if nl.is_dummy:
            continue
        pgid = nl.parent_group_id
        if pgid is None or pgid not in layout.group_layouts:
            continue
        gl = layout.group_layouts[pgid]
        inflated = gl.boundary_bounds.inflate(1.0)
        if not inflated.contains(nl.outer_bounds):
            violations.append(GeometryViolation(
                kind="containment",
                description=(
                    f"Node {nid!r} outer_bounds {nl.outer_bounds} is not "
                    f"inside group {pgid!r} boundary {gl.boundary_bounds}."
                ),
                offending_ids=(nid, pgid),
            ))


# ── Check 3: sibling-group non-overlap ────────────────────────────────────────

def _check_sibling_group_overlap(
    layout: "FinalizedLayout",
    violations: list[GeometryViolation],
) -> None:
    """Groups with the same parent must not overlap each other."""
    by_parent: dict = defaultdict(list)
    for gid, gl in layout.group_layouts.items():
        by_parent[gl.parent_group_id].append(gid)

    for siblings in by_parent.values():
        for i in range(len(siblings)):
            for j in range(i + 1, len(siblings)):
                gid_a = siblings[i]
                gid_b = siblings[j]
                gl_a = layout.group_layouts[gid_a]
                gl_b = layout.group_layouts[gid_b]
                if _overlap_exceeds(gl_a.boundary_bounds, gl_b.boundary_bounds):
                    violations.append(GeometryViolation(
                        kind="group-overlap",
                        description=(
                            f"Sibling groups {gid_a!r} and {gid_b!r} "
                            f"boundary_bounds overlap by > 1 px in both axes."
                        ),
                        offending_ids=(gid_a, gid_b),
                    ))


# ── Check 4: edge endpoints on visible boundaries ────────────────────────────

def _check_edge_endpoints(
    layout: "FinalizedLayout",
    violations: list[GeometryViolation],
) -> None:
    """Edge endpoints (first/last waypoints) must lie on or near the node boundary."""
    TOLERANCE = 8.0
    for edge in layout.routed_edges:
        wps = edge.waypoints
        if len(wps) < 2:
            continue
        for which, wp, nid in (
            ("source", wps[0], edge.src_node_id),
            ("target", wps[-1], edge.dst_node_id),
        ):
            nl = layout.node_layouts.get(nid)
            if nl is None or nl.is_dummy:
                continue
            inflated = nl.outer_bounds.inflate(TOLERANCE)
            if not inflated.contains_point(wp):
                violations.append(GeometryViolation(
                    kind="endpoint-outside-boundary",
                    description=(
                        f"Edge {edge.edge_id!r} {which} endpoint {wp} "
                        f"is outside node {nid!r} boundary (inflated by {TOLERANCE} px)."
                    ),
                    offending_ids=(edge.edge_id, nid),
                ))


# ── Check 5: no route passes through unrelated node ──────────────────────────

def _check_route_through_node(
    layout: "FinalizedLayout",
    violations: list[GeometryViolation],
) -> None:
    """Interior waypoints of an edge must not lie inside an unrelated node."""
    MARGIN = 2.0
    real_nodes = {nid: nl for nid, nl in layout.node_layouts.items() if not nl.is_dummy}

    for edge in layout.routed_edges:
        wps = edge.waypoints
        if len(wps) < 3:
            continue
        incident = {edge.src_node_id, edge.dst_node_id}
        for wp in wps[1:-1]:
            for nid, nl in real_nodes.items():
                if nid in incident:
                    continue
                inner = nl.outer_bounds.inflate(-MARGIN)
                if inner.w > 0 and inner.h > 0 and inner.contains_point(wp):
                    violations.append(GeometryViolation(
                        kind="route-through-node",
                        description=(
                            f"Edge {edge.edge_id!r} interior waypoint {wp} "
                            f"lies inside unrelated node {nid!r}."
                        ),
                        offending_ids=(edge.edge_id, nid),
                    ))
                    break


# ── Check 6: no route enters unrelated group interior ────────────────────────

def _check_route_through_group(
    layout: "FinalizedLayout",
    violations: list[GeometryViolation],
) -> None:
    """Interior waypoints must not enter group interiors the edge is not connecting."""
    if not layout.group_layouts:
        return
    MARGIN = 4.0

    for edge in layout.routed_edges:
        wps = edge.waypoints
        if len(wps) < 3:
            continue
        src_nl = layout.node_layouts.get(edge.src_node_id)
        dst_nl = layout.node_layouts.get(edge.dst_node_id)
        connected_groups: set = set()
        if src_nl and src_nl.parent_group_id:
            connected_groups.add(src_nl.parent_group_id)
        if dst_nl and dst_nl.parent_group_id:
            connected_groups.add(dst_nl.parent_group_id)

        for wp in wps[1:-1]:
            for gid, gl in layout.group_layouts.items():
                if gid in connected_groups:
                    continue
                interior = gl.boundary_bounds.inflate(-MARGIN)
                if interior.w > 0 and interior.h > 0 and interior.contains_point(wp):
                    violations.append(GeometryViolation(
                        kind="route-through-group",
                        description=(
                            f"Edge {edge.edge_id!r} interior waypoint {wp} "
                            f"enters unrelated group {gid!r} interior."
                        ),
                        offending_ids=(edge.edge_id, gid),
                    ))
                    break


# ── Check 7: no route crosses group title band ────────────────────────────────

def _check_route_crosses_title_band(
    layout: "FinalizedLayout",
    violations: list[GeometryViolation],
) -> None:
    """Interior waypoints must not cross a group title band the edge is not incident to."""
    if not layout.group_layouts:
        return
    GROUP_TITLE_H = 36.0  # GROUP_PAD_Y_TOP

    from mermaid_render.layout._geometry import Rect  # noqa: PLC0415

    for edge in layout.routed_edges:
        wps = edge.waypoints
        if len(wps) < 3:
            continue
        src_nl = layout.node_layouts.get(edge.src_node_id)
        dst_nl = layout.node_layouts.get(edge.dst_node_id)
        connected_groups: set = set()
        if src_nl and src_nl.parent_group_id:
            connected_groups.add(src_nl.parent_group_id)
        if dst_nl and dst_nl.parent_group_id:
            connected_groups.add(dst_nl.parent_group_id)

        for wp in wps[1:-1]:
            for gid, gl in layout.group_layouts.items():
                if gid in connected_groups:
                    continue
                title_band = Rect(
                    x=gl.boundary_bounds.x,
                    y=gl.boundary_bounds.y,
                    w=gl.boundary_bounds.w,
                    h=GROUP_TITLE_H,
                )
                if title_band.contains_point(wp, tolerance=2.0):
                    violations.append(GeometryViolation(
                        kind="route-crosses-title-band",
                        description=(
                            f"Edge {edge.edge_id!r} interior waypoint {wp} "
                            f"crosses title band of group {gid!r}."
                        ),
                        offending_ids=(edge.edge_id, gid),
                    ))
                    break


# ── Check 8: label bounds do not overlap nodes ────────────────────────────────

def _check_label_overlap_node(
    layout: "FinalizedLayout",
    violations: list[GeometryViolation],
) -> None:
    """Edge label bounds must not overlap node outer_bounds by > 1 px."""
    real_nodes = [(nid, nl) for nid, nl in layout.node_layouts.items() if not nl.is_dummy]

    for edge in layout.routed_edges:
        for lbl in (edge.label_layout, edge.src_label_layout, edge.dst_label_layout):
            if lbl is None:
                continue
            for nid, nl in real_nodes:
                if _overlap_exceeds(lbl.bounds, nl.outer_bounds, threshold=1.0):
                    violations.append(GeometryViolation(
                        kind="label-overlap-node",
                        description=(
                            f"Edge {edge.edge_id!r} label {lbl.text!r} bounds "
                            f"{lbl.bounds} overlaps node {nid!r} outer_bounds {nl.outer_bounds}."
                        ),
                        offending_ids=(edge.edge_id, nid),
                    ))


# ── Crossing count helper ─────────────────────────────────────────────────────

def _count_crossings(segs: list) -> int:
    """Count pair-wise proper intersections among segments. O(n^2)."""
    count = 0
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if _proper_intersect(segs[i][0], segs[i][1], segs[j][0], segs[j][1]):
                count += 1
    return count


def _cross2d(o: "Point", a: "Point", b: "Point") -> float:
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)


def _proper_intersect(a1: "Point", a2: "Point", b1: "Point", b2: "Point") -> bool:
    """Return True iff segments a1-a2 and b1-b2 properly (interior-to-interior) intersect."""
    d1 = _cross2d(b1, b2, a1)
    d2 = _cross2d(b1, b2, a2)
    d3 = _cross2d(a1, a2, b1)
    d4 = _cross2d(a1, a2, b2)
    if (
        ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0))
        and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0))
    ):
        return True
    return False
