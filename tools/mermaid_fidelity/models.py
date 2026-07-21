"""Core data models for Mermaid fidelity benchmarking.

Versioned, serializable dataclasses. Schema version 1.
Coordinate convention: css-top-left (origin at top-left, y increases downward).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ── implementation / environment identity ─────────────────────────────────────

@dataclass
class ImplementationIdentity:
    name: str
    version: str
    integrity: str | None       # SHA256 of key implementation files
    adapter_version: str
    profile_id: str


@dataclass
class EnvironmentIdentity:
    """Significant capture variables for a reference render environment.

    capture_timestamp is stored on Observation, not here, so it does not
    contribute to deterministic fingerprints.
    """
    mermaid_version: str
    mermaid_integrity: str | None   # lockfile hash or npm integrity string
    playwright_version: str
    chromium_revision: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float
    locale: str
    timezone: str
    reduced_motion: bool
    mermaid_config_hash: str        # SHA256 of the Mermaid config JSON
    css_profile_hash: str           # SHA256 of the CSS profile file; "" for default
    font_info: dict[str, Any]       # resolved/requested font information


# ── parse observation ─────────────────────────────────────────────────────────

@dataclass
class ParseObservation:
    accepted: bool
    diagram_type: str | None
    error_category: str | None      # normalized category, not a raw upstream string
    source_position: str | None     # "line:col" when reliably available


# ── semantic model ────────────────────────────────────────────────────────────

@dataclass
class Entity:
    id: str
    kind: str           # "node"|"actor"|"service"|"entity"|"class"|…
    label: str
    shape: str | None   # "rect"|"diamond"|"circle"|…
    parent_id: str | None
    order: int
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relation:
    id: str
    kind: str           # "edge"|"message"|"link"|"relationship"|…
    source: str         # entity id
    target: str         # entity id
    label: str
    arrow: str | None   # arrow type / style
    order: int
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Group:
    id: str
    kind: str           # "subgraph"|"boundary"|"block"|…
    label: str
    parent_id: str | None
    order: int
    members: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderedEvent:
    """Sequence diagram message or time-ordered event."""
    id: str
    kind: str           # "message"|"activation"|"note"|…
    source: str | None
    target: str | None
    label: str
    order: int
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticDiagram:
    diagram_type: str
    direction: str | None
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    ordered_events: list[OrderedEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ── geometry observation ──────────────────────────────────────────────────────

@dataclass
class BoundingBox:
    """Axis-aligned bounding box. Coordinate convention: css-top-left."""
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2

    def area(self) -> float:
        return self.width * self.height


@dataclass
class EntityGeometry:
    entity_id: str
    bbox: BoundingBox
    text_bbox: BoundingBox | None   # tightest text-content box when measurable
    text_lines: int


@dataclass
class RelationGeometry:
    relation_id: str
    source_point: tuple[float, float]
    target_point: tuple[float, float]
    source_side: str | None         # "L"|"R"|"T"|"B"
    target_side: str | None
    sampled_points: list[tuple[float, float]]  # 32 sampled points along path
    bend_count: int
    path_length: float | None


@dataclass
class GroupGeometry:
    group_id: str
    bbox: BoundingBox


COORDINATE_CONVENTION = "css-top-left"


@dataclass
class GeometryObservation:
    """Actual measured output geometry.

    Coordinate convention: css-top-left (origin at top-left of canvas,
    y increases downward, units are CSS pixels at device_scale_factor=1).
    """
    coordinate_convention: str          # always "css-top-left"
    content_bounds: BoundingBox | None  # tightest bbox around all semantic content
    canvas_bounds: BoundingBox | None   # declared canvas element bounds
    viewbox: str | None                 # raw SVG viewBox string when present
    entities: list[EntityGeometry] = field(default_factory=list)
    groups: list[GroupGeometry] = field(default_factory=list)
    relations: list[RelationGeometry] = field(default_factory=list)
    containment: list[tuple[str, str]] = field(default_factory=list)  # (child_id, parent_id)
    crossing_count: int | None = None


# ── quality observation ───────────────────────────────────────────────────────

class QualityFindingKind(str, Enum):
    CLIPPED_LABEL = "clipped_label"
    CONTENT_OVERFLOW = "content_overflow"
    OUTSIDE_CANVAS = "outside_canvas"
    ZERO_AREA = "zero_area"
    UNRELATED_OVERLAP = "unrelated_overlap"
    DETACHED_ENDPOINT = "detached_endpoint"
    GROUP_CONTAINMENT_VIOLATION = "group_containment_violation"
    UNREADABLY_SMALL = "unreadably_small"
    MISSING_ELEMENT = "missing_element"


@dataclass
class QualityFinding:
    kind: QualityFindingKind
    entity_id: str | None
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityObservation:
    findings: list[QualityFinding] = field(default_factory=list)


# ── comparison status ─────────────────────────────────────────────────────────

class ComparisonStatus(str, Enum):
    PASS = "PASS"
    PARSE_MISMATCH = "PARSE_MISMATCH"
    SEMANTIC_MISMATCH = "SEMANTIC_MISMATCH"
    QUALITY_FAILURE = "QUALITY_FAILURE"
    EXTRACTOR_GAP = "EXTRACTOR_GAP"
    REFERENCE_RENDER_FAILURE = "REFERENCE_RENDER_FAILURE"
    NATIVE_UNSUPPORTED = "NATIVE_UNSUPPORTED"
    NONDETERMINISTIC = "NONDETERMINISTIC"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ── top-level observation ─────────────────────────────────────────────────────

@dataclass
class Observation:
    schema_version: int         # 1
    case_id: str
    implementation: ImplementationIdentity
    environment: EnvironmentIdentity
    parse_result: ParseObservation
    semantic: SemanticDiagram | None
    geometry: GeometryObservation | None
    quality: QualityObservation | None
    status: ComparisonStatus
    reason: str | None          # machine-readable reason for non-PASS status
    artifact_refs: dict[str, str] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)
    capture_timestamp: str | None = None  # excluded from deterministic fingerprints


# ── runner inputs ─────────────────────────────────────────────────────────────

@dataclass
class FidelityCase:
    """A single benchmark case from the manifest."""
    id: str
    source_path: Path
    source: str         # loaded .mmd content
    diagram: str        # "flowchart"|"sequence"|"architecture"|"er"|…
    tags: list[str] = field(default_factory=list)
    strict: list[str] = field(default_factory=list)
    scored: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class RenderProfile:
    """Configuration for a single render environment."""
    id: str
    viewport_width: int = 1200
    viewport_height: int = 900
    device_scale_factor: float = 1.0
    locale: str = "en-US"
    timezone: str = "UTC"
    reduced_motion: bool = True
    css_path: Path | None = None        # injected stylesheet (neutral profile)
    mermaid_config: dict | None = None  # Mermaid init config object


@dataclass
class FidelityManifest:
    schema_version: int
    cases: list[FidelityCase]
