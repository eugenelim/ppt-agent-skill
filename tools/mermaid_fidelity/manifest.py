"""Manifest parsing and validation for cases.toml.

Path policy (which source paths are allowed) belongs in the repository
adapter layer, not here. This module validates structure and check names only.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from .models import FidelityCase, FidelityManifest
from .registry import get_capability, strict_check_names, scored_check_names, ignored_check_names


_KNOWN_LIFECYCLES: frozenset[str] = frozenset({"active", "planned"})

_KNOWN_DIAGRAMS: frozenset[str] = frozenset({
    "flowchart", "sequence", "architecture", "er",
    "class", "state", "gantt", "timeline", "mindmap",
    "c4", "block", "packet", "kanban", "pie", "xychart",
    "gitgraph", "journey", "requirement", "sankey", "quadrant", "zenuml",
})


class ManifestValidationError(ValueError):
    pass


def parse_manifest(
    manifest_path: Path,
    *,
    load_sources: bool = True,
    path_validator: "PathValidator | None" = None,
) -> FidelityManifest:
    """Parse cases.toml and return a validated FidelityManifest.

    manifest_path: path to cases.toml
    load_sources: if True, read each .mmd source file
    path_validator: optional callable(resolved_path, case_id) → None that
        raises ManifestValidationError for disallowed paths. Repository
        adapters inject this to enforce fixture-area confinement.
    """
    raw = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    schema_version = raw.get("schema_version", 1)
    if schema_version != 1:
        raise ManifestValidationError(f"Unsupported schema_version: {schema_version!r}")

    cases_raw = raw.get("case", [])
    if not cases_raw:
        raise ManifestValidationError("Manifest contains no [[case]] entries")

    manifest_dir = manifest_path.parent
    seen_ids: set[str] = set()
    cases: list[FidelityCase] = []

    for i, cr in enumerate(cases_raw):
        case_id = cr.get("id", "")
        if not case_id:
            raise ManifestValidationError(f"Case at index {i} has no 'id' field")
        if case_id in seen_ids:
            raise ManifestValidationError(f"Duplicate case id: {case_id!r}")
        seen_ids.add(case_id)

        source_rel = cr.get("source", "")
        if not source_rel:
            raise ManifestValidationError(f"Case {case_id!r} has no 'source' field")

        source_path = (manifest_dir / source_rel).resolve()

        if not source_path.suffix == ".mmd":
            raise ManifestValidationError(
                f"Case {case_id!r}: source must be a .mmd file, got {source_path.suffix!r}"
            )

        if path_validator is not None:
            path_validator(source_path, case_id)

        if not source_path.exists():
            raise ManifestValidationError(
                f"Case {case_id!r}: source path does not exist: {source_path}"
            )

        diagram = cr.get("diagram", "")
        if diagram not in _KNOWN_DIAGRAMS:
            raise ManifestValidationError(
                f"Case {case_id!r}: unrecognized diagram family {diagram!r}. "
                f"Known: {sorted(_KNOWN_DIAGRAMS)}"
            )

        lifecycle = cr.get("lifecycle", "active")
        if lifecycle not in _KNOWN_LIFECYCLES:
            raise ManifestValidationError(
                f"Case {case_id!r}: unknown lifecycle {lifecycle!r}. "
                f"Known: {sorted(_KNOWN_LIFECYCLES)}"
            )

        strict: list[str] = cr.get("strict", [])
        scored: list[str] = cr.get("scored", [])
        ignored: list[str] = cr.get("ignored", [])

        _strict_names = strict_check_names()
        _scored_names = scored_check_names()
        _ignored_names = ignored_check_names()

        for chk in strict:
            if chk not in _strict_names:
                raise ManifestValidationError(
                    f"Case {case_id!r}: unknown strict check {chk!r}. "
                    f"Known strict checks: {sorted(_strict_names)}"
                )
        for chk in scored:
            if chk not in _scored_names:
                raise ManifestValidationError(
                    f"Case {case_id!r}: unknown scored check {chk!r}. "
                    f"Known scored checks: {sorted(_scored_names)}"
                )
        for chk in ignored:
            if chk not in _ignored_names:
                raise ManifestValidationError(
                    f"Case {case_id!r}: unknown ignored check {chk!r}. "
                    f"Known ignored: {sorted(_ignored_names)}"
                )

        all_checks = strict + scored + ignored
        seen_checks: dict[str, int] = {}
        for chk in all_checks:
            seen_checks[chk] = seen_checks.get(chk, 0) + 1
        duplicates = [chk for chk, cnt in seen_checks.items() if cnt > 1]
        if duplicates:
            raise ManifestValidationError(
                f"Case {case_id!r}: checks appear in multiple policy lists: {duplicates}"
            )

        source_text = source_path.read_text(encoding="utf-8") if load_sources else ""
        cases.append(FidelityCase(
            id=case_id,
            source_path=source_path,
            source=source_text,
            diagram=diagram,
            lifecycle=lifecycle,
            tags=list(cr.get("tags", [])),
            strict=strict,
            scored=scored,
            ignored=ignored,
            notes=cr.get("notes", ""),
        ))

    return FidelityManifest(schema_version=schema_version, cases=cases)


PathValidator = "callable[[Path, str], None]"
