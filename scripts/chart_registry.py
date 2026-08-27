"""Canonical chart identifiers and grouped recipe routing."""

from __future__ import annotations


CHART_TYPE_TO_FILE: dict[str, str] = {
    # basic.md
    "progress_bar": "basic",
    "comparison_bar": "basic",
    "ring": "basic",
    "sparkline": "basic",
    "waffle": "basic",
    "kpi": "basic",
    "metric_row": "basic",
    "rating": "basic",
    # advanced.md
    "radar": "advanced",
    "timeline": "advanced",
    "funnel": "advanced",
    "gauge": "advanced",
    "grouped_bar": "advanced",
    "stacked_bar": "advanced",
    "simple_map": "advanced",
    # complex.md
    "world_choropleth": "complex",
    "network_graph": "complex",
    "sankey_flow": "complex",
    "heatmap_calendar": "complex",
    "treemap": "complex",
}

VALID_CHART_TYPES = frozenset(CHART_TYPE_TO_FILE)


def normalize_chart_type(value: str) -> str:
    """Normalize a chart reference while preserving the public snake-case form."""
    return value.strip().lower().replace("-", "_")


def chart_recipe_file(value: str) -> str | None:
    """Return the grouped recipe file stem for a chart reference."""
    return CHART_TYPE_TO_FILE.get(normalize_chart_type(value))
