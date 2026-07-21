"""mermaid_fidelity — reusable Mermaid rendering fidelity benchmarking library.

Public API for the harvestable core. No imports of scripts/, tests/,
mermaid_render, or repository-specific adapters.

Future extraction mapping:
  tools/mermaid_fidelity/ → src/mermaid_fidelity/ (standalone PyPI package)
"""
from .models import (
    ImplementationIdentity,
    EnvironmentIdentity,
    ParseObservation,
    Entity,
    Relation,
    Group,
    OrderedEvent,
    SemanticDiagram,
    BoundingBox,
    EntityGeometry,
    RelationGeometry,
    GroupGeometry,
    GeometryObservation,
    QualityFindingKind,
    QualityFinding,
    QualityObservation,
    ComparisonStatus,
    Observation,
    FidelityCase,
    RenderProfile,
    FidelityManifest,
    COORDINATE_CONVENTION,
)
from .adapters import FidelityAdapter
from .serialization import to_json, save_json, load_json, observation_fingerprint
from .canonical import canonical_label, canonical_semantic, stable_relation_id
from .manifest import parse_manifest, ManifestValidationError
from .runner import FidelityRunner, CaseRunResult, RunSummary
from .report import generate_json_report, generate_md_report, generate_html_report
from .projection import generate_projection, generate_overlay

__version__ = "0.1.0"
__all__ = [
    # models
    "ImplementationIdentity",
    "EnvironmentIdentity",
    "ParseObservation",
    "Entity",
    "Relation",
    "Group",
    "OrderedEvent",
    "SemanticDiagram",
    "BoundingBox",
    "EntityGeometry",
    "RelationGeometry",
    "GroupGeometry",
    "GeometryObservation",
    "QualityFindingKind",
    "QualityFinding",
    "QualityObservation",
    "ComparisonStatus",
    "Observation",
    "FidelityCase",
    "RenderProfile",
    "FidelityManifest",
    "COORDINATE_CONVENTION",
    # adapters
    "FidelityAdapter",
    # serialization
    "to_json",
    "save_json",
    "load_json",
    "observation_fingerprint",
    # canonical
    "canonical_label",
    "canonical_semantic",
    "stable_relation_id",
    # manifest
    "parse_manifest",
    "ManifestValidationError",
    # runner
    "FidelityRunner",
    "CaseRunResult",
    "RunSummary",
    # report
    "generate_json_report",
    "generate_md_report",
    "generate_html_report",
    # projection
    "generate_projection",
    "generate_overlay",
]
