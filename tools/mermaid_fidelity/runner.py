"""Fidelity runner: orchestrates observation collection and comparison.

The runner operates only on the FidelityAdapter protocol and the core models.
It has no repository-specific knowledge.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapters import FidelityAdapter
from .compare.geometry import (
    NormalizedGeometry,
    ScoredLayoutMetrics,
    RelativeLayoutResult,
    normalize_geometry,
    compare_relative_layout,
    score_layout_metrics,
)
from .compare.quality import QualityTolerances, run_quality_checks
from .compare.semantic import SemanticComparisonResult, compare_semantic
from .models import (
    ComparisonStatus,
    FidelityCase,
    FidelityManifest,
    Observation,
    RenderProfile,
    SemanticDiagram,
)
from .serialization import observation_fingerprint, save_json, to_json


@dataclass
class CaseRunResult:
    case_id: str
    native_obs: Observation
    ref_obs: Observation | None         # None when no oracle data exists
    semantic_result: SemanticComparisonResult | None
    layout_result: RelativeLayoutResult | None
    native_norm: NormalizedGeometry | None
    ref_norm: NormalizedGeometry | None
    scored_metrics: ScoredLayoutMetrics | None
    final_status: ComparisonStatus
    reason: str | None
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class RunSummary:
    total: int
    passed: int
    semantic_mismatches: int
    quality_failures: int
    extractor_gaps: int
    parse_mismatches: int
    other_failures: int
    results: list[CaseRunResult] = field(default_factory=list)


class FidelityRunner:
    """Orchestrates observation collection and comparison for a manifest."""

    def __init__(
        self,
        native_adapter: FidelityAdapter,
        oracle_dir: Path,
        tolerances: QualityTolerances | None = None,
    ) -> None:
        self._native = native_adapter
        self._oracle_dir = oracle_dir
        self._tolerances = tolerances or QualityTolerances()

    def run_case(
        self,
        case: FidelityCase,
        profile: RenderProfile,
        ref_id: str,
    ) -> CaseRunResult:
        """Run a single case and compare against oracle."""
        native_obs = self._native.observe(case, profile)

        # Load reference oracle
        oracle_path = self._oracle_dir / ref_id / "cases" / f"{case.id}.json"
        ref_obs: Observation | None = None
        if oracle_path.exists():
            try:
                from .serialization import load_json
                from .serialization import _to_json_value
                raw = load_json(oracle_path)
                ref_obs = _deserialize_observation(raw)
            except Exception as e:
                native_obs.diagnostics.append(f"Oracle load error: {e}")

        return self._compare(case, native_obs, ref_obs)

    def _compare(
        self,
        case: FidelityCase,
        native_obs: Observation,
        ref_obs: Observation | None,
    ) -> CaseRunResult:
        status = native_obs.status
        reason = native_obs.reason
        semantic_result: SemanticComparisonResult | None = None
        layout_result: RelativeLayoutResult | None = None
        native_norm: NormalizedGeometry | None = None
        ref_norm: NormalizedGeometry | None = None
        scored: ScoredLayoutMetrics | None = None
        diagnostics: list[str] = list(native_obs.diagnostics)

        if status not in (ComparisonStatus.PASS,):
            # Native observation already has a failure status
            pass
        elif ref_obs is None:
            status = ComparisonStatus.STALE_ORACLE
            reason = "no oracle reference data; run capture-reference first"
        elif ref_obs.status == ComparisonStatus.REFERENCE_RENDER_FAILURE:
            status = ComparisonStatus.REFERENCE_RENDER_FAILURE
            reason = "reference render failed"
        else:
            # Semantic comparison
            if native_obs.semantic and ref_obs.semantic:
                semantic_result = compare_semantic(
                    ref_obs.semantic,
                    native_obs.semantic,
                    case.strict,
                )
                if not semantic_result.passed:
                    status = ComparisonStatus.SEMANTIC_MISMATCH
                    reason = "; ".join(semantic_result.diff.to_lines()[:5])
                    diagnostics.extend(semantic_result.diff.to_lines())

            # Geometry comparison
            if native_obs.geometry and ref_obs.geometry:
                native_norm = normalize_geometry(native_obs.geometry)
                ref_norm = normalize_geometry(ref_obs.geometry)

                layout_result = compare_relative_layout(
                    native_obs.geometry,
                    ref_obs.geometry,
                    case.strict,
                    native_obs.semantic.direction if native_obs.semantic else None,
                )
                if not layout_result.passed and status == ComparisonStatus.PASS:
                    status = ComparisonStatus.RELATIVE_LAYOUT_MISMATCH
                    reason = "; ".join(layout_result.failures[:3])
                    diagnostics.extend(layout_result.failures)

                if native_norm and ref_norm:
                    scored = score_layout_metrics(
                        native_norm, ref_norm,
                        native_obs.geometry, ref_obs.geometry,
                    )

            # Quality checks
            if native_obs.geometry:
                quality_findings = run_quality_checks(
                    native_obs.geometry, self._tolerances
                )
                if quality_findings and status == ComparisonStatus.PASS:
                    status = ComparisonStatus.QUALITY_FAILURE
                    reason = quality_findings[0].message

        return CaseRunResult(
            case_id=case.id,
            native_obs=native_obs,
            ref_obs=ref_obs,
            semantic_result=semantic_result,
            layout_result=layout_result,
            native_norm=native_norm,
            ref_norm=ref_norm,
            scored_metrics=scored,
            final_status=status,
            reason=reason,
            diagnostics=diagnostics,
        )

    def run_all(
        self,
        manifest: FidelityManifest,
        profile: RenderProfile,
        ref_id: str,
        case_ids: list[str] | None = None,
    ) -> RunSummary:
        cases = manifest.cases
        if case_ids:
            cases = [c for c in cases if c.id in case_ids]

        results: list[CaseRunResult] = []
        for case in cases:
            result = self.run_case(case, profile, ref_id)
            results.append(result)

        return _build_summary(results)

    def run_determinism(
        self,
        cases: list[FidelityCase],
        profile: RenderProfile,
        runs: int = 3,
    ) -> dict[str, Any]:
        """Render each case 'runs' times and check canonical stability."""
        report: dict[str, Any] = {"cases": {}, "stable": True}

        for case in cases:
            obs_list: list[Observation] = []
            for _ in range(runs):
                obs = self._native.observe(case, profile)
                obs_list.append(obs)

            fingerprints = [observation_fingerprint(obs) for obs in obs_list]
            stable = len(set(fingerprints)) == 1

            case_report: dict[str, Any] = {
                "stable": stable,
                "fingerprints": fingerprints,
                "diffs": [],
            }

            if not stable:
                report["stable"] = False
                # Find first differing pair
                for i in range(1, len(obs_list)):
                    if fingerprints[i] != fingerprints[0]:
                        diffs = _find_json_diffs(
                            to_json(obs_list[0], for_fingerprint=True),
                            to_json(obs_list[i], for_fingerprint=True),
                        )
                        case_report["diffs"] = diffs[:20]
                        break

            report["cases"][case.id] = case_report

        return report


def _build_summary(results: list[CaseRunResult]) -> RunSummary:
    passed = sum(1 for r in results if r.final_status == ComparisonStatus.PASS)
    sem = sum(1 for r in results if r.final_status == ComparisonStatus.SEMANTIC_MISMATCH)
    qual = sum(1 for r in results if r.final_status == ComparisonStatus.QUALITY_FAILURE)
    gap = sum(1 for r in results if r.final_status == ComparisonStatus.EXTRACTOR_GAP)
    parse = sum(1 for r in results if r.final_status == ComparisonStatus.PARSE_MISMATCH)
    other = len(results) - passed - sem - qual - gap - parse

    return RunSummary(
        total=len(results),
        passed=passed,
        semantic_mismatches=sem,
        quality_failures=qual,
        extractor_gaps=gap,
        parse_mismatches=parse,
        other_failures=other,
        results=results,
    )


def _find_json_diffs(a: str, b: str) -> list[str]:
    """Return a list of differing JSON paths between two JSON strings."""
    import json

    def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
        out: dict[str, Any] = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                out.update(_flatten(v, f"{prefix}.{k}" if prefix else k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                out.update(_flatten(v, f"{prefix}[{i}]"))
        else:
            out[prefix] = obj
        return out

    flat_a = _flatten(json.loads(a))
    flat_b = _flatten(json.loads(b))
    diffs: list[str] = []
    all_keys = sorted(set(flat_a) | set(flat_b))
    for k in all_keys:
        va = flat_a.get(k, "<missing>")
        vb = flat_b.get(k, "<missing>")
        if va != vb:
            diffs.append(f"{k}: {va!r} → {vb!r}")
    return diffs


def _deserialize_observation(raw: dict) -> Observation:
    """Shallow-reconstruct an Observation from a loaded JSON dict.

    Returns a minimal Observation with status/reason preserved.
    Full geometry/semantic deserialization is done on demand.
    """
    from .models import (
        ComparisonStatus, EnvironmentIdentity, ImplementationIdentity,
        Observation, ParseObservation,
    )

    status_val = raw.get("status", "INTERNAL_ERROR")
    try:
        status = ComparisonStatus(status_val)
    except ValueError:
        status = ComparisonStatus.INTERNAL_ERROR

    impl = raw.get("implementation", {})
    env = raw.get("environment", {})
    parse = raw.get("parse_result", {})

    return Observation(
        schema_version=raw.get("schema_version", 1),
        case_id=raw.get("case_id", ""),
        implementation=ImplementationIdentity(
            name=impl.get("name", ""),
            version=impl.get("version", ""),
            integrity=impl.get("integrity"),
            adapter_version=impl.get("adapter_version", ""),
            profile_id=impl.get("profile_id", ""),
        ),
        environment=EnvironmentIdentity(
            mermaid_version=env.get("mermaid_version", ""),
            mermaid_integrity=env.get("mermaid_integrity"),
            playwright_version=env.get("playwright_version", ""),
            chromium_revision=env.get("chromium_revision", ""),
            viewport_width=env.get("viewport_width", 1200),
            viewport_height=env.get("viewport_height", 900),
            device_scale_factor=env.get("device_scale_factor", 1.0),
            locale=env.get("locale", "en-US"),
            timezone=env.get("timezone", "UTC"),
            reduced_motion=env.get("reduced_motion", True),
            mermaid_config_hash=env.get("mermaid_config_hash", ""),
            css_profile_hash=env.get("css_profile_hash", ""),
            font_info=env.get("font_info", {}),
        ),
        parse_result=ParseObservation(
            accepted=parse.get("accepted", False),
            diagram_type=parse.get("diagram_type"),
            error_category=parse.get("error_category"),
            source_position=parse.get("source_position"),
        ),
        semantic=_deserialize_semantic(raw.get("semantic")),
        geometry=_deserialize_geometry(raw.get("geometry")),
        quality=_deserialize_quality(raw.get("quality")),
        status=status,
        reason=raw.get("reason"),
        artifact_refs=raw.get("artifact_refs", {}),
        diagnostics=raw.get("diagnostics", []),
        capture_timestamp=raw.get("capture_timestamp"),
    )


def _deserialize_semantic(data: dict | None):
    if data is None:
        return None
    from .models import Entity, Group, OrderedEvent, Relation, SemanticDiagram

    def _entity(d: dict) -> Entity:
        return Entity(
            id=d.get("id", ""),
            kind=d.get("kind", "node"),
            label=d.get("label", ""),
            shape=d.get("shape"),
            parent_id=d.get("parent_id"),
            order=d.get("order", 0),
            attributes=d.get("attributes", {}),
        )

    def _relation(d: dict) -> Relation:
        return Relation(
            id=d.get("id", ""),
            kind=d.get("kind", "edge"),
            source=d.get("source", ""),
            target=d.get("target", ""),
            label=d.get("label", ""),
            arrow=d.get("arrow"),
            order=d.get("order", 0),
            attributes=d.get("attributes", {}),
        )

    def _group(d: dict) -> Group:
        return Group(
            id=d.get("id", ""),
            kind=d.get("kind", "subgraph"),
            label=d.get("label", ""),
            parent_id=d.get("parent_id"),
            order=d.get("order", 0),
            members=d.get("members", []),
            attributes=d.get("attributes", {}),
        )

    def _event(d: dict) -> OrderedEvent:
        return OrderedEvent(
            id=d.get("id", ""),
            kind=d.get("kind", "message"),
            source=d.get("source"),
            target=d.get("target"),
            label=d.get("label", ""),
            order=d.get("order", 0),
            attributes=d.get("attributes", {}),
        )

    return SemanticDiagram(
        diagram_type=data.get("diagram_type", ""),
        direction=data.get("direction"),
        entities=[_entity(e) for e in data.get("entities", [])],
        relations=[_relation(r) for r in data.get("relations", [])],
        groups=[_group(g) for g in data.get("groups", [])],
        ordered_events=[_event(e) for e in data.get("ordered_events", [])],
        metadata=data.get("metadata", {}),
    )


def _deserialize_geometry(data: dict | None):
    """Reconstruct GeometryObservation from a loaded JSON dict."""
    if data is None:
        return None
    from .models import (
        BoundingBox, EntityGeometry, GeometryObservation,
        GroupGeometry, RelationGeometry,
    )

    def _bbox(d: dict | None) -> BoundingBox | None:
        if not d:
            return None
        return BoundingBox(
            x=float(d.get("x", 0)),
            y=float(d.get("y", 0)),
            width=float(d.get("width", 0)),
            height=float(d.get("height", 0)),
        )

    def _point(p) -> tuple[float, float] | None:
        if p is None:
            return None
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            return (float(p[0]), float(p[1]))
        return None

    entities = [
        EntityGeometry(
            entity_id=e.get("entity_id", ""),
            bbox=_bbox(e.get("bbox")) or BoundingBox(0, 0, 0, 0),
            text_bbox=_bbox(e.get("text_bbox")),
            text_lines=e.get("text_lines", 1),
        )
        for e in data.get("entities", [])
    ]

    groups = [
        GroupGeometry(
            group_id=g.get("group_id", ""),
            bbox=_bbox(g.get("bbox")) or BoundingBox(0, 0, 0, 0),
        )
        for g in data.get("groups", [])
    ]

    relations = []
    for r in data.get("relations", []):
        src_pt = _point(r.get("source_point"))
        dst_pt = _point(r.get("target_point"))
        sampled_raw = r.get("sampled_points", [])
        sampled = [_point(p) for p in sampled_raw if _point(p) is not None]
        relations.append(RelationGeometry(
            relation_id=r.get("relation_id", ""),
            source_point=src_pt or (0.0, 0.0),
            target_point=dst_pt or (0.0, 0.0),
            source_side=r.get("source_side"),
            target_side=r.get("target_side"),
            sampled_points=sampled,
            bend_count=r.get("bend_count", 0),
            path_length=r.get("path_length"),
        ))

    containment = []
    for item in data.get("containment", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            containment.append((str(item[0]), str(item[1])))

    return GeometryObservation(
        coordinate_convention=data.get("coordinate_convention", "css-top-left"),
        content_bounds=_bbox(data.get("content_bounds")),
        canvas_bounds=_bbox(data.get("canvas_bounds")),
        viewbox=data.get("viewbox"),
        entities=entities,
        groups=groups,
        relations=relations,
        containment=containment,
        crossing_count=data.get("crossing_count"),
    )


def _deserialize_quality(data: dict | None):
    """Reconstruct QualityObservation from a loaded JSON dict."""
    if data is None:
        return None
    from .models import QualityFinding, QualityFindingKind, QualityObservation

    findings = []
    for f in data.get("findings", []):
        kind_val = f.get("kind", "missing_element")
        try:
            kind = QualityFindingKind(kind_val)
        except ValueError:
            kind = QualityFindingKind.MISSING_ELEMENT
        findings.append(QualityFinding(
            kind=kind,
            entity_id=f.get("entity_id"),
            message=f.get("message", ""),
            details=f.get("details", {}),
        ))
    return QualityObservation(findings=findings)
