"""Tests for brand_deck_path optional validation in contract_validator.py."""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contract_validator import (
    validate_interview,
    validate_requirements_interview,
    REQUIRED_INTERVIEW_ANCHORS,
)

# Minimal text satisfying all 18 required anchors + dimensions
MINIMAL_ANCHORS = (
    "scenario: pitch\naudience: exec\ntarget_action: buy\n"
    "expected_pages: 10\npage_density: moderate\nstyle: minimal\n"
    "brand: none\nmust_include: x\nmust_avoid: y\nlanguage: English\n"
    "imagery: decorate\nmaterial_strategy: research\n"
    "grounding_mode: illustrative\nsubagent_model_strategy: inherit\n"
    "subagent_thinking_effort: medium\nmanual_audit_mode: off\n"
    "manual_audit_scope: none\nmanual_audit_assets: summary_only\n"
)


def _req_text(extra: str = "") -> str:
    return MINIMAL_ANCHORS + extra


# Red drivers (fail before implementation):
#   test_brand_deck_path_warns_non_pptx, test_brand_deck_path_no_extension_warns,
#   test_brand_deck_path_interview_qa_path
# Green guards (pass before + after; catch regressions): all others


def test_brand_deck_path_valid_pptx(tmp_path):  # STUB: AC1
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand.pptx\n"))
    result, _ = validate_requirements_interview(p)
    assert result.errors == [], "expected 0 errors"
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert brand_warns == [], "expected 0 brand_deck_path warnings"


def test_brand_deck_path_absent(tmp_path):  # STUB: AC2
    p = tmp_path / "req.txt"
    p.write_text(_req_text())
    result, _ = validate_requirements_interview(p)
    assert result.errors == []


def test_brand_deck_path_warns_non_pptx(tmp_path):  # STUB: AC3 — red driver
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand.pdf\n"))
    result, _ = validate_requirements_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert len(brand_warns) == 1

    p2 = tmp_path / "req2.txt"
    p2.write_text(_req_text("brand_deck_path: /path/to/brand.pptx\n"))
    result2, _ = validate_requirements_interview(p2)
    brand_warns2 = [w for w in result2.warnings if "brand_deck_path" in w]
    assert brand_warns2 == []


def test_brand_deck_path_empty_no_warning(tmp_path):  # STUB: AC3
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: \n"))
    result, _ = validate_requirements_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert brand_warns == []


def test_brand_deck_path_no_extension_warns(tmp_path):  # STUB: AC3 — red driver
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand\n"))
    result, _ = validate_requirements_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert len(brand_warns) == 1


def test_brand_deck_path_case_insensitive(tmp_path):  # STUB: AC3
    p = tmp_path / "req.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand.PPTX\n"))
    result, _ = validate_requirements_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert brand_warns == []


def test_brand_deck_path_interview_qa_path(tmp_path):  # STUB: AC1/AC3 — red driver
    p = tmp_path / "qa.txt"
    p.write_text(_req_text("brand_deck_path: /path/to/brand.pdf\n"))
    result, _ = validate_interview(p)
    brand_warns = [w for w in result.warnings if "brand_deck_path" in w]
    assert len(brand_warns) == 1


def test_required_anchors_unchanged():  # STUB: AC2
    assert "brand_deck_path" not in REQUIRED_INTERVIEW_ANCHORS
