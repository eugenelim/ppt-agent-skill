"""Fidelity comparators: semantic, geometry, and quality."""
from .semantic import (
    SemanticDiff,
    SemanticComparisonResult,
    compare_semantic,
)
from .geometry import (
    NormalizedGeometry,
    ScoredLayoutMetrics,
    normalize_geometry,
    compare_relative_layout,
    score_layout_metrics,
    RelativeLayoutResult,
)
from .quality import (
    check_overflow,
    check_outside_canvas,
    check_canvas_size,
    check_zero_area,
    check_overlap,
    check_group_containment,
    QualityTolerances,
)

__all__ = [
    "SemanticDiff",
    "SemanticComparisonResult",
    "compare_semantic",
    "NormalizedGeometry",
    "ScoredLayoutMetrics",
    "normalize_geometry",
    "compare_relative_layout",
    "score_layout_metrics",
    "RelativeLayoutResult",
    "check_overflow",
    "check_outside_canvas",
    "check_canvas_size",
    "check_zero_area",
    "check_overlap",
    "check_group_containment",
    "QualityTolerances",
]
