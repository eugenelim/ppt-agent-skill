"""Pure geometry predicates for native output quality checks.

These functions are reusable, browser-independent predicates extracted
from the original diagram_render_check.py for use across contexts.
All tolerances are explicit named constants, never magic numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models import BoundingBox, GeometryObservation, QualityFinding, QualityFindingKind


@dataclass
class QualityTolerances:
    """Named tolerances for quality predicates.

    All values are in CSS pixels at device_scale_factor=1.
    """
    overflow_tolerance: float = 4.0         # scrollWidth > clientWidth + overflow_tolerance
    outside_canvas_tolerance: float = 8.0   # node edge outside canvas by more than this
    min_canvas_width: float = 50.0          # canvas narrower than this is flagged
    min_canvas_height: float = 20.0         # canvas shorter than this is flagged
    overlap_fraction_threshold: float = 0.5 # overlap area / min(area_a, area_b) > this
    endpoint_detach_threshold: float = 16.0 # endpoint farther than this from node edge
    unreadable_width_threshold: float = 20.0


DEFAULT_TOLERANCES = QualityTolerances()


# ── pure geometry predicates ──────────────────────────────────────────────────

def check_overflow(
    node_rect: BoundingBox,
    scroll_rect: BoundingBox,
    tolerances: QualityTolerances = DEFAULT_TOLERANCES,
) -> bool:
    """Return True when content overflows node bounds (text clipping risk).

    node_rect: outer node element bounds (clientWidth/clientHeight equivalent).
    scroll_rect: scrollable content bounds (scrollWidth/scrollHeight equivalent).
    """
    return (
        scroll_rect.width > node_rect.width + tolerances.overflow_tolerance
        or scroll_rect.height > node_rect.height + tolerances.overflow_tolerance
    )


def check_outside_canvas(
    node_rect: BoundingBox,
    canvas_rect: BoundingBox,
    tolerances: QualityTolerances = DEFAULT_TOLERANCES,
) -> bool:
    """Return True when any node edge extends outside the canvas."""
    t = tolerances.outside_canvas_tolerance
    return (
        node_rect.right > canvas_rect.right + t
        or node_rect.bottom > canvas_rect.bottom + t
        or node_rect.x < canvas_rect.x - t
        or node_rect.y < canvas_rect.y - t
    )


def check_canvas_size(
    canvas: BoundingBox,
    tolerances: QualityTolerances = DEFAULT_TOLERANCES,
) -> bool:
    """Return True when canvas has non-zero meaningful size."""
    return (
        canvas.width >= tolerances.min_canvas_width
        and canvas.height >= tolerances.min_canvas_height
    )


def check_zero_area(
    bbox: BoundingBox,
) -> bool:
    """Return True when entity has a meaningful non-zero area."""
    return bbox.width > 0 and bbox.height > 0


def _overlap_area(a: BoundingBox, b: BoundingBox) -> float:
    """Return the area of intersection of two bounding boxes."""
    ix1 = max(a.x, b.x)
    iy1 = max(a.y, b.y)
    ix2 = min(a.right, b.right)
    iy2 = min(a.bottom, b.bottom)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    return (ix2 - ix1) * (iy2 - iy1)


def check_overlap(
    a: BoundingBox,
    b: BoundingBox,
    tolerances: QualityTolerances = DEFAULT_TOLERANCES,
) -> bool:
    """Return True when two unrelated node bounding boxes substantially overlap."""
    ov = _overlap_area(a, b)
    if ov <= 0:
        return False
    min_area = min(a.area(), b.area())
    if min_area <= 0:
        return False
    return (ov / min_area) >= tolerances.overlap_fraction_threshold


def check_group_containment(
    entity_bbox: BoundingBox,
    group_bbox: BoundingBox,
    tolerances: QualityTolerances = DEFAULT_TOLERANCES,
) -> bool:
    """Return True when entity is (approximately) contained within its group."""
    t = tolerances.outside_canvas_tolerance
    return (
        entity_bbox.x >= group_bbox.x - t
        and entity_bbox.right <= group_bbox.right + t
        and entity_bbox.y >= group_bbox.y - t
        and entity_bbox.bottom <= group_bbox.bottom + t
    )


# ── observation-level quality checker ────────────────────────────────────────

def run_quality_checks(
    geo: GeometryObservation,
    tolerances: QualityTolerances = DEFAULT_TOLERANCES,
) -> list[QualityFinding]:
    """Run all quality checks on a GeometryObservation.

    Returns a list of findings (empty = all checks passed).
    """
    findings: list[QualityFinding] = []

    if geo.canvas_bounds is not None:
        if not check_canvas_size(geo.canvas_bounds, tolerances):
            findings.append(QualityFinding(
                kind=QualityFindingKind.ZERO_AREA,
                entity_id=None,
                message=f"canvas has near-zero size: {geo.canvas_bounds.width:.0f}×{geo.canvas_bounds.height:.0f}px",
                details={"canvas_w": geo.canvas_bounds.width, "canvas_h": geo.canvas_bounds.height},
            ))

    # Outside-canvas check
    if geo.canvas_bounds is not None:
        for eg in geo.entities:
            if check_outside_canvas(eg.bbox, geo.canvas_bounds, tolerances):
                findings.append(QualityFinding(
                    kind=QualityFindingKind.OUTSIDE_CANVAS,
                    entity_id=eg.entity_id,
                    message=f"entity {eg.entity_id!r} extends outside canvas",
                    details={"bbox": _bbox_dict(eg.bbox), "canvas": _bbox_dict(geo.canvas_bounds)},
                ))

    # Zero-area entities
    for eg in geo.entities:
        if not check_zero_area(eg.bbox):
            findings.append(QualityFinding(
                kind=QualityFindingKind.ZERO_AREA,
                entity_id=eg.entity_id,
                message=f"entity {eg.entity_id!r} has zero area",
                details={"bbox": _bbox_dict(eg.bbox)},
            ))

    # Group containment violations
    grp_by_id = {gg.group_id: gg.bbox for gg in geo.groups}
    for child_id, parent_id in geo.containment:
        if parent_id in grp_by_id and child_id in {eg.entity_id for eg in geo.entities}:
            child_bbox = next(eg.bbox for eg in geo.entities if eg.entity_id == child_id)
            if not check_group_containment(child_bbox, grp_by_id[parent_id], tolerances):
                findings.append(QualityFinding(
                    kind=QualityFindingKind.GROUP_CONTAINMENT_VIOLATION,
                    entity_id=child_id,
                    message=f"entity {child_id!r} outside group {parent_id!r}",
                    details={
                        "entity_bbox": _bbox_dict(child_bbox),
                        "group_bbox": _bbox_dict(grp_by_id[parent_id]),
                    },
                ))

    # Unrelated-node overlap (quadratic — only for reasonably-sized diagrams)
    if len(geo.entities) <= 64:
        ents = geo.entities
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                # Skip entities that are in parent-child relationships
                related = {
                    (c, p) for c, p in geo.containment
                    if c in (ents[i].entity_id, ents[j].entity_id)
                    or p in (ents[i].entity_id, ents[j].entity_id)
                }
                if not related and check_overlap(ents[i].bbox, ents[j].bbox, tolerances):
                    findings.append(QualityFinding(
                        kind=QualityFindingKind.UNRELATED_OVERLAP,
                        entity_id=ents[i].entity_id,
                        message=(
                            f"entities {ents[i].entity_id!r} and {ents[j].entity_id!r} "
                            f"substantially overlap"
                        ),
                        details={
                            "entity_a": ents[i].entity_id,
                            "entity_b": ents[j].entity_id,
                        },
                    ))

    return findings


def _bbox_dict(b: BoundingBox) -> dict:
    return {"x": b.x, "y": b.y, "width": b.width, "height": b.height}
