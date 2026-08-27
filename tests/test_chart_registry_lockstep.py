"""Keep chart validation, loading, and grouped recipes on one contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CHARTS = ROOT / "references" / "charts"
CHART_INDEX = CHARTS / "index.md"
sys.path.insert(0, str(SCRIPTS))

import chart_registry as registry  # noqa: E402
import planning_validator as validator  # noqa: E402
import resource_loader as loader  # noqa: E402


EXPECTED_CHARTS = {
    "progress_bar": "basic",
    "comparison_bar": "basic",
    "ring": "basic",
    "sparkline": "basic",
    "waffle": "basic",
    "kpi": "basic",
    "metric_row": "basic",
    "rating": "basic",
    "radar": "advanced",
    "timeline": "advanced",
    "funnel": "advanced",
    "gauge": "advanced",
    "grouped_bar": "advanced",
    "stacked_bar": "advanced",
    "simple_map": "advanced",
    "world_choropleth": "complex",
    "network_graph": "complex",
    "sankey_flow": "complex",
    "heatmap_calendar": "complex",
    "treemap": "complex",
}


def _recipe_ids(path: Path) -> list[str]:
    """Return chart identifiers from numbered recipe headings in order."""
    pattern = re.compile(r"^## \d+\..*\((?:`)?([a-z][a-z0-9_]*)(?:`)?\)\s*$", re.MULTILINE)
    return pattern.findall(path.read_text(encoding="utf-8"))


def _table_ids(path: Path) -> list[str]:
    """Return identifiers from the family file's leading chart index table."""
    text = path.read_text(encoding="utf-8")
    first_recipe = re.search(r"^## \d+\.", text, re.MULTILINE)
    assert first_recipe is not None
    return re.findall(
        r"^\| \d+ \|.*\| `([a-z][a-z0-9_]*)` \|",
        text[:first_recipe.start()],
        re.MULTILINE,
    )


def test_registry_is_the_confirmed_twenty_type_contract() -> None:
    assert registry.CHART_TYPE_TO_FILE == EXPECTED_CHARTS
    assert registry.VALID_CHART_TYPES == frozenset(EXPECTED_CHARTS)


def test_validator_and_loader_consume_the_canonical_registry() -> None:
    assert validator.VALID_CHART_TYPES == registry.VALID_CHART_TYPES
    assert loader.CHART_TYPE_TO_FILE is registry.CHART_TYPE_TO_FILE


def test_hyphen_and_underscore_refs_resolve_to_the_same_recipe() -> None:
    for chart_type, family in EXPECTED_CHARTS.items():
        assert registry.chart_recipe_file(chart_type) == family
        assert registry.chart_recipe_file(chart_type.replace("_", "-")) == family
        assert validator.resource_exists(CHARTS.parent, "chart_refs", chart_type)


@pytest.mark.parametrize(("chart_type", "family"), EXPECTED_CHARTS.items())
@pytest.mark.parametrize("separator", ("_", "-"))
def test_resource_loader_loads_the_declared_grouped_recipe(
    chart_type: str,
    family: str,
    separator: str,
) -> None:
    chart_ref = chart_type.replace("_", separator)
    page = {
        "slide_number": 1,
        "cards": [{"card_type": "text", "chart": {"chart_type": chart_ref}}],
    }
    with patch.object(loader, "load_planning_pages", return_value=[page]):
        output = loader.resolve_resources(CHARTS.parent, Path("unused.json"))

    family_titles = {
        name: (CHARTS / f"{name}.md").read_text(encoding="utf-8").splitlines()[0]
        for name in ("basic", "advanced", "complex")
    }
    assert family_titles[family] in output
    for other_family in {"basic", "advanced", "complex"} - {family}:
        assert family_titles[other_family] not in output


def test_grouped_recipe_headings_match_the_registry() -> None:
    indexed: dict[str, str] = {}
    all_table_ids: list[str] = []
    all_heading_ids: list[str] = []
    for family in ("basic", "advanced", "complex"):
        path = CHARTS / f"{family}.md"
        table_ids = _table_ids(path)
        heading_ids = _recipe_ids(path)
        assert len(table_ids) == len(set(table_ids))
        assert len(heading_ids) == len(set(heading_ids))
        assert heading_ids == table_ids
        all_table_ids.extend(table_ids)
        all_heading_ids.extend(heading_ids)
        indexed.update({chart_type: family for chart_type in table_ids})
    assert len(all_table_ids) == len(set(all_table_ids)) == len(EXPECTED_CHARTS)
    assert len(all_heading_ids) == len(set(all_heading_ids)) == len(EXPECTED_CHARTS)
    assert indexed == EXPECTED_CHARTS


def test_published_chart_index_matches_the_registry() -> None:
    """The human-facing selector must publish the runtime IDs and families."""
    rows = re.findall(
        r"^\| \d+ \| `([a-z][a-z0-9_]*)` \|.*\| \[(basic|advanced|complex)\.md\]",
        CHART_INDEX.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert len(rows) == len(EXPECTED_CHARTS)
    assert len({chart_type for chart_type, _ in rows}) == len(EXPECTED_CHARTS)
    assert dict(rows) == EXPECTED_CHARTS
