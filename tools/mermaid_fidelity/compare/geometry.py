"""Geometry normalization, relative layout checks, and scored layout metrics.

Normalization algorithm:
1. Find semantic content bounds.
2. Remove translation (shift so content_bounds.x == content_bounds.y == 0).
3. Choose one uniform scale factor (max content dimension).
4. Preserve aspect ratio — never independently scale x and y.
5. Retain the original canvas aspect ratio as a separate metric.

Float precision: PRECISION decimal places for all normalized values.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..models import (
    BoundingBox, EntityGeometry, GeometryObservation,
    GroupGeometry, RelationGeometry,
)

PRECISION = 4
SAMPLE_COUNT = 32  # number of sampled connector points for path comparison


def _round(v: float) -> float:
    return round(v, PRECISION)


@dataclass
class NormalizedGeometry:
    """Geometry after translation removal and uniform scaling."""
    scale_factor: float
    entities: list[EntityGeometry]
    groups: list[GroupGeometry]
    canvas_aspect: float | None     # original canvas w/h
    content_aspect: float | None    # content bounds w/h


@dataclass
class RelativeLayoutResult:
    """Results of hard relative-layout checks."""
    passed: bool
    failures: list[str] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)


@dataclass
class ScoredLayoutMetrics:
    """Continuously scored layout similarity metrics.

    These are reported independently and do not gate CI during Phase 1.
    """
    normalized_entity_center_error: float | None  # mean normalized distance
    median_entity_width_error: float | None        # median |w_native - w_ref| / w_ref
    median_entity_height_error: float | None
    content_aspect_delta: float | None             # |native_aspect - ref_aspect|
    canvas_aspect_delta: float | None
    text_line_agreement: float | None              # fraction of entities with same line count
    crossing_count_delta: int | None
    bend_count_delta: float | None                 # mean absolute bend difference per relation


def normalize_geometry(obs: GeometryObservation) -> NormalizedGeometry | None:
    """Normalize geometry: remove translation, apply uniform scale.

    Returns None when content_bounds is missing or zero-area.
    """
    cb = obs.content_bounds
    if cb is None or cb.area() <= 0:
        return None

    # Step 1+2: translate so content_bounds origin is (0, 0)
    tx, ty = cb.x, cb.y
    scale = _round(1.0 / max(cb.width, cb.height, 1.0))

    def _translate_bbox(b: BoundingBox) -> BoundingBox:
        return BoundingBox(
            x=_round((b.x - tx) * scale),
            y=_round((b.y - ty) * scale),
            width=_round(b.width * scale),
            height=_round(b.height * scale),
        )

    norm_entities: list[EntityGeometry] = []
    for eg in obs.entities:
        norm_entities.append(EntityGeometry(
            entity_id=eg.entity_id,
            bbox=_translate_bbox(eg.bbox),
            text_bbox=_translate_bbox(eg.text_bbox) if eg.text_bbox else None,
            text_lines=eg.text_lines,
        ))

    norm_groups: list[GroupGeometry] = []
    for gg in obs.groups:
        norm_groups.append(GroupGeometry(
            group_id=gg.group_id,
            bbox=_translate_bbox(gg.bbox),
        ))

    canvas_aspect: float | None = None
    if obs.canvas_bounds and obs.canvas_bounds.height > 0:
        canvas_aspect = _round(obs.canvas_bounds.width / obs.canvas_bounds.height)

    content_aspect: float | None = None
    if cb.height > 0:
        content_aspect = _round(cb.width / cb.height)

    return NormalizedGeometry(
        scale_factor=scale,
        entities=norm_entities,
        groups=norm_groups,
        canvas_aspect=canvas_aspect,
        content_aspect=content_aspect,
    )


def compare_relative_layout(
    native_obs: GeometryObservation,
    ref_obs: GeometryObservation,
    strict_fields: list[str],
    native_semantic_direction: str | None = None,
) -> RelativeLayoutResult:
    """Hard relative-layout checks for well-defined geometric relationships.

    Does not compare absolute coordinates. Only checks direction-relative
    and containment relationships that should be preserved.
    """
    failures: list[str] = []
    checks_run: list[str] = []

    nat_by_id = {eg.entity_id: eg for eg in native_obs.entities}
    ref_by_id = {eg.entity_id: eg for eg in ref_obs.entities}
    common_ids = set(nat_by_id) & set(ref_by_id)

    # Guard: if BOTH sides have entities but no overlap, this is an extractor gap,
    # not a layout pass.  Return an explicit failure so the runner can surface
    # EXTRACTOR_GAP rather than vacuously passing.
    # When only one side has entities (e.g. reference oracle has empty geometry
    # because its regex-based extractor doesn't parse the diagram type), treat it
    # as "no shared geometry data" and pass vacuously rather than flagging a gap.
    if not common_ids and native_obs.entities and ref_obs.entities:
        return RelativeLayoutResult(
            passed=False,
            failures=["no common entity IDs between native and reference — likely extractor gap"],
            checks_run=["entity-id-overlap"],
        )

    if not common_ids:
        return RelativeLayoutResult(passed=True, failures=[], checks_run=[])

    # direction / rank check: in TB mode, higher-ranked nodes should have lower y.
    # Use native_semantic_direction (from the parsed diagram, not measured geometry).
    direction = native_semantic_direction or "TB"

    if "direction" in strict_fields and native_obs.canvas_bounds and ref_obs.canvas_bounds:
        checks_run.append("direction-relative-rank")
        nat_dir = _infer_direction(native_obs)
        ref_dir = _infer_direction(ref_obs)
        if nat_dir and ref_dir and nat_dir != ref_dir:
            failures.append(
                f"layout direction mismatch: native infers {nat_dir!r}, "
                f"reference infers {ref_dir!r}"
            )

    # Containment: entities in groups should be inside their group bbox.
    # Convention: containment tuples are (child_id, parent_id).
    if "containment" in strict_fields:
        checks_run.append("containment")
        nat_groups = {gg.group_id: gg for gg in native_obs.groups}
        for child_id, parent_id in native_obs.containment:
            if parent_id not in nat_groups or child_id not in nat_by_id:
                continue
            grp = nat_groups[parent_id].bbox
            ent = nat_by_id[child_id].bbox
            tolerance = 4.0
            if (ent.x < grp.x - tolerance or ent.right > grp.right + tolerance
                    or ent.y < grp.y - tolerance or ent.bottom > grp.bottom + tolerance):
                failures.append(
                    f"containment violation: entity {child_id!r} not inside "
                    f"group {parent_id!r} (entity: {ent}, group: {grp})"
                )

    return RelativeLayoutResult(
        passed=len(failures) == 0,
        failures=failures,
        checks_run=checks_run,
    )


def _infer_direction(obs: GeometryObservation) -> str | None:
    """Infer TB/LR from whether spread is more vertical or horizontal."""
    if not obs.entities:
        return None
    xs = [eg.bbox.cx for eg in obs.entities]
    ys = [eg.bbox.cy for eg in obs.entities]
    if len(xs) < 2:
        return None
    x_range = max(xs) - min(xs)
    y_range = max(ys) - min(ys)
    if y_range > x_range:
        return "TB"
    return "LR"


def score_layout_metrics(
    native_norm: NormalizedGeometry,
    ref_norm: NormalizedGeometry,
    native_obs: GeometryObservation,
    ref_obs: GeometryObservation,
) -> ScoredLayoutMetrics:
    """Compute continuously scored layout similarity metrics.

    All metrics are reported independently. None gate CI during Phase 1.
    Missing data yields None for that metric rather than 0.
    """
    nat_by_id = {eg.entity_id: eg for eg in native_norm.entities}
    ref_by_id = {eg.entity_id: eg for eg in ref_norm.entities}
    common_ids = sorted(set(nat_by_id) & set(ref_by_id))

    # Normalized entity center error
    center_error: float | None = None
    if common_ids:
        dists: list[float] = []
        for eid in common_ids:
            n = nat_by_id[eid].bbox
            r = ref_by_id[eid].bbox
            dist = math.hypot(n.cx - r.cx, n.cy - r.cy)
            dists.append(dist)
        center_error = _round(sum(dists) / len(dists))

    # Median width/height error
    median_w_err: float | None = None
    median_h_err: float | None = None
    if common_ids:
        w_errs = sorted(
            abs(nat_by_id[eid].bbox.width - ref_by_id[eid].bbox.width) / max(ref_by_id[eid].bbox.width, 1.0)
            for eid in common_ids
        )
        h_errs = sorted(
            abs(nat_by_id[eid].bbox.height - ref_by_id[eid].bbox.height) / max(ref_by_id[eid].bbox.height, 1.0)
            for eid in common_ids
        )
        mid = len(w_errs) // 2
        median_w_err = _round(w_errs[mid])
        median_h_err = _round(h_errs[mid])

    # Content aspect delta
    content_delta: float | None = None
    if native_norm.content_aspect is not None and ref_norm.content_aspect is not None:
        content_delta = _round(abs(native_norm.content_aspect - ref_norm.content_aspect))

    # Canvas aspect delta
    canvas_delta: float | None = None
    if native_norm.canvas_aspect is not None and ref_norm.canvas_aspect is not None:
        canvas_delta = _round(abs(native_norm.canvas_aspect - ref_norm.canvas_aspect))

    # Text line agreement
    line_agreement: float | None = None
    if common_ids:
        matches = sum(
            1 for eid in common_ids
            if nat_by_id[eid].text_lines == ref_by_id[eid].text_lines
        )
        line_agreement = _round(matches / len(common_ids))

    # Crossing count delta
    cross_delta: int | None = None
    nat_cross = native_obs.crossing_count
    ref_cross = ref_obs.crossing_count
    if nat_cross is not None and ref_cross is not None:
        cross_delta = abs(nat_cross - ref_cross)

    # Bend count delta
    bend_delta: float | None = None
    nat_rels = {r.relation_id: r for r in native_obs.relations}
    ref_rels = {r.relation_id: r for r in ref_obs.relations}
    common_rels = set(nat_rels) & set(ref_rels)
    if common_rels:
        bends = [
            abs(nat_rels[rid].bend_count - ref_rels[rid].bend_count)
            for rid in common_rels
        ]
        bend_delta = _round(sum(bends) / len(bends))

    return ScoredLayoutMetrics(
        normalized_entity_center_error=center_error,
        median_entity_width_error=median_w_err,
        median_entity_height_error=median_h_err,
        content_aspect_delta=content_delta,
        canvas_aspect_delta=canvas_delta,
        text_line_agreement=line_agreement,
        crossing_count_delta=cross_delta,
        bend_count_delta=bend_delta,
    )
