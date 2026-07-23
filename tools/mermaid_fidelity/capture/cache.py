"""Cache layer for browser geometry capture.

Cache key: sha256(source_hash + mermaid_version + browser_version
                  + font_fingerprint + render_config_hash).

Entries are stored as JSON under .cache/mermaid_reference/ (gitignored).
Serialization uses dataclasses.asdict + json; deserialization reconstructs
the dataclasses from the nested dict structure.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from tools.mermaid_fidelity.models import (
    BoundingBox,
    CardinalityEnd,
    ComparisonStatus,
    ExtractorGap,
    ReferenceEdge,
    ReferenceGroup,
    ReferenceLabel,
    ReferenceMarker,
    ReferenceDiagram,
    ReferenceNode,
    ReferenceProvenance,
)


# Default cache directory relative to the repo root
_DEFAULT_CACHE_DIR = Path(".cache") / "mermaid_reference"


def _cache_key(
    source_hash: str,
    mermaid_version: str,
    browser_version: str,
    font_fingerprint: str,
    render_config_hash: str,
) -> str:
    """Compute the cache key as a SHA-256 hex digest."""
    components = "|".join([
        source_hash,
        mermaid_version,
        browser_version,
        font_fingerprint,
        render_config_hash,
    ])
    return hashlib.sha256(components.encode()).hexdigest()


def _bbox_from_dict(d: dict[str, Any]) -> BoundingBox:
    return BoundingBox(x=d["x"], y=d["y"], width=d["width"], height=d["height"])


def _marker_from_dict(d: dict[str, Any] | None) -> Optional[ReferenceMarker]:
    if d is None:
        return None
    return ReferenceMarker(
        marker_id=d["marker_id"],
        kind=d["kind"],  # type: ignore[arg-type]
        edge_id=d["edge_id"],
        end=d["end"],  # type: ignore[arg-type]
    )


def _cardinality_from_dict(d: dict[str, Any] | None) -> Optional[CardinalityEnd]:
    if d is None:
        return None
    return CardinalityEnd(minimum=d["minimum"], maximum=d["maximum"])  # type: ignore[arg-type]


def _diagram_from_dict(d: dict[str, Any]) -> ReferenceDiagram:
    """Reconstruct a ReferenceDiagram from a plain dict (deserialization)."""
    prov_d = d["provenance"]
    provenance = ReferenceProvenance(
        mermaid_version=prov_d["mermaid_version"],
        mmdc_version=prov_d["mmdc_version"],
        node_version=prov_d["node_version"],
        playwright_version=prov_d["playwright_version"],
        chromium_version=prov_d["chromium_version"],
        platform=prov_d["platform"],
        font_families=prov_d["font_families"],
        font_fingerprint=prov_d["font_fingerprint"],
        fixture_source_hash=prov_d["fixture_source_hash"],
        render_config_hash=prov_d["render_config_hash"],
        captured_at=prov_d.get("captured_at"),
    )

    nodes = [
        ReferenceNode(
            id=n["id"],
            label=n["label"],
            shape=n.get("shape"),
            kind=n.get("kind"),
            bbox=_bbox_from_dict(n["bbox"]),
            transform_chain=n.get("transform_chain", []),
            parent_group_id=n.get("parent_group_id"),
            attributes=n.get("attributes", {}),
        )
        for n in d.get("nodes", [])
    ]

    groups = [
        ReferenceGroup(
            id=g["id"],
            label=g["label"],
            bbox=_bbox_from_dict(g["bbox"]),
            parent_group_id=g.get("parent_group_id"),
            node_ids=g.get("node_ids", []),
            group_ids=g.get("group_ids", []),
            attributes=g.get("attributes", {}),
        )
        for g in d.get("groups", [])
    ]

    edges = [
        ReferenceEdge(
            id=e["id"],
            source=e["source"],
            target=e["target"],
            path_data=e["path_data"],
            sampled_points=[tuple(p) for p in e.get("sampled_points", [])],  # type: ignore[misc]
            stroke_width=e.get("stroke_width", 1.0),
            dash_pattern=e.get("dash_pattern"),
            marker_start=_marker_from_dict(e.get("marker_start")),
            marker_end=_marker_from_dict(e.get("marker_end")),
            label_bbox=_bbox_from_dict(e["label_bbox"]) if e.get("label_bbox") else None,
            cardinality_start=_cardinality_from_dict(e.get("cardinality_start")),
            cardinality_end=_cardinality_from_dict(e.get("cardinality_end")),
            attributes=e.get("attributes", {}),
        )
        for e in d.get("edges", [])
    ]

    labels = [
        ReferenceLabel(
            id=lbl["id"],
            text=lbl["text"],
            bbox=_bbox_from_dict(lbl["bbox"]),
            edge_id=lbl.get("edge_id"),
        )
        for lbl in d.get("labels", [])
    ]

    markers = [
        ReferenceMarker(
            marker_id=m["marker_id"],
            kind=m["kind"],  # type: ignore[arg-type]
            edge_id=m["edge_id"],
            end=m["end"],  # type: ignore[arg-type]
        )
        for m in d.get("markers", [])
    ]

    gaps = [
        ExtractorGap(field=g["field"], reason=g["reason"])
        for g in d.get("gaps", [])
    ]

    return ReferenceDiagram(
        fixture_stem=d["fixture_stem"],
        diagram_type=d["diagram_type"],
        canvas_bounds=_bbox_from_dict(d["canvas_bounds"]),
        view_box=d.get("view_box"),
        provenance=provenance,
        nodes=nodes,
        groups=groups,
        edges=edges,
        labels=labels,
        markers=markers,
        gaps=gaps,
        status=ComparisonStatus(d.get("status", "PASS")),
    )


class DiagramCache:
    """File-based cache for ReferenceDiagram records.

    Cache is keyed by (source_hash, mermaid_version, browser_version,
    font_fingerprint, render_config_hash). Entries are stored as JSON.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._dir = cache_dir or _DEFAULT_CACHE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(
        self,
        source_hash: str,
        mermaid_version: str,
        browser_version: str,
        font_fingerprint: str,
        render_config_hash: str = "",
    ) -> Optional[ReferenceDiagram]:
        """Return the cached diagram, or None on a cache miss."""
        key = _cache_key(
            source_hash, mermaid_version, browser_version,
            font_fingerprint, render_config_hash,
        )
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return _diagram_from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def put(
        self,
        diagram: ReferenceDiagram,
        source_hash: str,
        mermaid_version: str,
        browser_version: str,
        font_fingerprint: str,
        render_config_hash: str = "",
    ) -> None:
        """Store a diagram in the cache."""
        key = _cache_key(
            source_hash, mermaid_version, browser_version,
            font_fingerprint, render_config_hash,
        )
        path = self._path(key)
        data = dataclasses.asdict(diagram)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def invalidate(
        self,
        source_hash: str,
        mermaid_version: str,
        browser_version: str,
        font_fingerprint: str,
        render_config_hash: str = "",
    ) -> bool:
        """Remove a specific cache entry. Returns True if entry was present."""
        key = _cache_key(
            source_hash, mermaid_version, browser_version,
            font_fingerprint, render_config_hash,
        )
        path = self._path(key)
        if path.exists():
            path.unlink()
            return True
        return False
