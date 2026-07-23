"""Shared oracle contract types for mermaid fidelity comparison.

Single canonical location for OracleStatus, OracleCheck, OracleResult,
ManifestError, and FixtureMinimums. Every consumer imports from here;
never redeclare these types in test files or compare modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OracleStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    EXTRACTOR_GAP = "extractor_gap"
    UNSUPPORTED_REFERENCE_FEATURE = "unsupported_reference_feature"
    UNVALIDATED = "unvalidated"


@dataclass(frozen=True)
class OracleCheck:
    name: str
    passed: bool
    expected: Any = None
    actual: Any = None
    diagnostic: str = ""


@dataclass(frozen=True)
class OracleResult:
    status: OracleStatus
    checks: tuple = ()
    diagnostics: tuple = ()
    fixture_stem: str = ""

    def __post_init__(self) -> None:
        if self.status == OracleStatus.PASS and not self.checks:
            raise ValueError(
                "OracleResult(status=PASS, checks=()) is not allowed; "
                "PASS requires at least one check"
            )


class ManifestError(ValueError):
    pass


@dataclass
class FixtureMinimums:
    min_entities: int = 0
    min_groups: int = 0
    min_relations: int = 0
    min_labels: int = 0
    min_markers: int = 0


# Shared fixture minimums registry — consumers populate or extend this.
FIXTURE_MINIMUMS: dict[str, FixtureMinimums] = {}
