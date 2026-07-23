"""Core data models for Mermaid fidelity benchmarking.

Versioned, serializable dataclasses. Schema version 1.
Coordinate convention: css-top-left (origin at top-left, y increases downward).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal


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
    RELATIVE_LAYOUT_MISMATCH = "RELATIVE_LAYOUT_MISMATCH"
    QUALITY_FAILURE = "QUALITY_FAILURE"
    EXTRACTOR_GAP = "EXTRACTOR_GAP"
    REFERENCE_RENDER_FAILURE = "REFERENCE_RENDER_FAILURE"
    NATIVE_UNSUPPORTED = "NATIVE_UNSUPPORTED"
    NONDETERMINISTIC = "NONDETERMINISTIC"
    STALE_ORACLE = "STALE_ORACLE"
    INVALID_MANIFEST = "INVALID_MANIFEST"
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
    source_sha256: str | None = None      # SHA-256 of the .mmd source bytes


# ── runner inputs ─────────────────────────────────────────────────────────────

@dataclass
class FidelityCase:
    """A single benchmark case from the manifest."""
    id: str
    source_path: Path
    source: str         # loaded .mmd content
    diagram: str        # "flowchart"|"sequence"|"architecture"|"er"|…
    lifecycle: str = "active"   # "active" | "planned"
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


# ── reference diagram types (browser geometry capture) ────────────────────────

@dataclass
class CardinalityEnd:
    """ER diagram cardinality end representation."""
    minimum: Literal["ZERO", "ONE"]
    maximum: Literal["ONE", "MANY"]


@dataclass
class ExtractorGap:
    """Typed diagnostic for a field that could not be captured."""
    field: str
    reason: str


@dataclass
class ReferenceNode:
    """A node extracted from a rendered SVG."""
    id: str
    label: str
    shape: str | None           # "rect"|"diamond"|"circle"|"roundedrect"|...
    kind: str | None            # entity kind from diagram type
    bbox: BoundingBox
    transform_chain: list[str] = field(default_factory=list)
    parent_group_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferenceGroup:
    """A group/subgraph extracted from a rendered SVG."""
    id: str
    label: str
    bbox: BoundingBox
    parent_group_id: str | None = None
    node_ids: list[str] = field(default_factory=list)
    group_ids: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferenceLabel:
    """A label attached to an edge or standalone element."""
    id: str
    text: str
    bbox: BoundingBox
    edge_id: str | None = None


@dataclass
class ReferenceMarker:
    """A resolved SVG marker (arrowhead/decorator) on an edge endpoint."""
    marker_id: str
    kind: Literal[
        "hollow_triangle",
        "filled_diamond",
        "hollow_diamond",
        "open_arrow",
        "none",
    ]
    edge_id: str
    end: Literal["start", "end"]


@dataclass
class ReferenceEdge:
    """An edge extracted from a rendered SVG."""
    id: str
    source: str                 # normalized node/entity id
    target: str                 # normalized node/entity id
    path_data: str              # raw SVG path d= attribute
    sampled_points: list[tuple[float, float]] = field(default_factory=list)
    stroke_width: float = 1.0
    dash_pattern: str | None = None
    marker_start: ReferenceMarker | None = None
    marker_end: ReferenceMarker | None = None
    label_bbox: BoundingBox | None = None
    cardinality_start: CardinalityEnd | None = None
    cardinality_end: CardinalityEnd | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


class StateSymbolKind(str, Enum):
    INITIAL = "initial"
    FINAL = "final"
    SIMPLE = "simple"
    COMPOSITE = "composite"
    COMPOSITE_BOUNDARY = "composite_boundary"


@dataclass
class ReferenceProvenance:
    """Version and environment fingerprint recorded at capture time."""
    mermaid_version: str
    mmdc_version: str
    node_version: str
    playwright_version: str
    chromium_version: str
    platform: str
    font_families: list[str]
    font_fingerprint: str       # sha256 hex of font files
    fixture_source_hash: str    # sha256 hex of the .mmd source bytes
    render_config_hash: str     # sha256 hex of the render configuration
    captured_at: str | None = None  # ISO 8601 timestamp; not used in cache key


@dataclass
class ReferenceDiagram:
    """Structured geometry record extracted from a browser-rendered Mermaid diagram.

    Only structured JSON records are used as oracle input — screenshots are never the input.
    Status is EXTRACTOR_GAP when any field has a typed ExtractorGap diagnostic.
    """
    fixture_stem: str
    diagram_type: str
    canvas_bounds: BoundingBox
    view_box: str | None
    provenance: ReferenceProvenance
    nodes: list[ReferenceNode] = field(default_factory=list)
    groups: list[ReferenceGroup] = field(default_factory=list)
    edges: list[ReferenceEdge] = field(default_factory=list)
    labels: list[ReferenceLabel] = field(default_factory=list)
    markers: list[ReferenceMarker] = field(default_factory=list)
    gaps: list[ExtractorGap] = field(default_factory=list)
    status: ComparisonStatus = ComparisonStatus.PASS

    def __post_init__(self) -> None:
        if self.gaps and self.status == ComparisonStatus.PASS:
            object.__setattr__(self, "status", ComparisonStatus.EXTRACTOR_GAP)
