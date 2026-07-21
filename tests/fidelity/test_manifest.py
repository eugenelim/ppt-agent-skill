"""Tests for the cases.toml manifest parsing and validation."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FIDELITY = Path(__file__).resolve().parent
_REPO = _FIDELITY.parents[1]
sys.path.insert(0, str(_REPO / "tools"))

from mermaid_fidelity.manifest import parse_manifest, ManifestValidationError
from mermaid_fidelity.models import FidelityManifest, FidelityCase

_MANIFEST = _FIDELITY / "cases.toml"
_FIXTURES = _REPO / "tests" / "fixtures"


def test_manifest_parses():
    manifest = parse_manifest(_MANIFEST, load_sources=False)
    assert isinstance(manifest, FidelityManifest)


def test_manifest_has_24_cases():
    manifest = parse_manifest(_MANIFEST, load_sources=False)
    assert len(manifest.cases) == 24, (
        f"Expected 24 cases, got {len(manifest.cases)}: "
        f"{[c.id for c in manifest.cases]}"
    )


def test_manifest_case_types():
    manifest = parse_manifest(_MANIFEST, load_sources=False)
    type_counts: dict[str, int] = {}
    for c in manifest.cases:
        type_counts[c.diagram] = type_counts.get(c.diagram, 0) + 1
    assert type_counts.get("flowchart", 0) == 11, f"Expected 11 flowchart, got {type_counts}"
    assert type_counts.get("sequence", 0) == 7, f"Expected 7 sequence, got {type_counts}"
    assert type_counts.get("architecture", 0) == 2, f"Expected 2 architecture, got {type_counts}"
    assert type_counts.get("er", 0) == 4, f"Expected 4 er, got {type_counts}"


def test_manifest_case_ids_unique():
    manifest = parse_manifest(_MANIFEST, load_sources=False)
    ids = [c.id for c in manifest.cases]
    assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"


def test_manifest_case_ids_stable():
    """IDs must not contain timestamps or auto-generated components."""
    manifest = parse_manifest(_MANIFEST, load_sources=False)
    for c in manifest.cases:
        assert "/" not in c.id, f"Case ID contains slash: {c.id}"
        assert c.id == c.id.strip(), f"Case ID has leading/trailing whitespace: {c.id!r}"
        assert c.id, "Case ID is empty"


def test_manifest_sources_load():
    """With load_sources=True, each case has a non-empty source string."""
    manifest = parse_manifest(_MANIFEST, load_sources=True)
    for c in manifest.cases:
        assert c.source, f"Case {c.id} has empty source"
        assert c.source_path.exists(), f"Case {c.id} source_path does not exist: {c.source_path}"


def test_manifest_fixture_files_exist():
    """Every case's source_path must resolve to an existing .mmd file."""
    manifest = parse_manifest(_MANIFEST, load_sources=False)
    missing = []
    for c in manifest.cases:
        if not c.source_path.exists():
            missing.append(str(c.source_path))
    assert not missing, f"Missing fixture files: {missing}"


def test_manifest_schema_version():
    manifest = parse_manifest(_MANIFEST, load_sources=False)
    assert manifest.schema_version == 1


def test_case_check_fields_are_known_strings():
    """strict/scored/ignored must be lists of non-empty strings."""
    manifest = parse_manifest(_MANIFEST, load_sources=False)
    for c in manifest.cases:
        for lst_name in ("strict", "scored", "ignored"):
            lst = getattr(c, lst_name, [])
            for item in lst:
                assert isinstance(item, str) and item, (
                    f"Case {c.id}.{lst_name} has blank/non-string entry: {item!r}"
                )
