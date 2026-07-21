"""Regression tests for sequence diagram rendering features added in G3.

Each test validates that a fixture: (1) renders to non-empty HTML, and
(2) passes all 11 geometry invariants via validate().  Some tests also
assert specific rendering tokens that verify the feature under test.

Import pattern follows repo convention: scripts/ on sys.path.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html, validate

FIXTURES = REPO_ROOT / "tests" / "fixtures"

# All sequence-*.mmd fixtures, parametrised for geometry-pass checks
_SEQ_FIXTURES = sorted(FIXTURES.glob("sequence-*.mmd"))


# ── Parametrised: every sequence fixture must pass geometry invariants ─────────

@pytest.mark.parametrize("fixture", _SEQ_FIXTURES, ids=lambda p: p.stem)
def test_sequence_fixture_geometry_pass(fixture: Path) -> None:
    """Every sequence fixture must render and pass all 11 geometry invariants."""
    src = fixture.read_text(encoding="utf-8")
    html = to_html(src)
    assert html, f"{fixture.name}: to_html returned empty"
    vr = validate(src)
    assert vr.render != "fail", f"{fixture.name}: render=fail: {vr.errors}"
    assert vr.geometry == "pass", (
        f"{fixture.name}: geometry={vr.geometry}, violations: {vr.errors}"
    )


# ── Feature-specific regressions ──────────────────────────────────────────────

class TestConstraintLayout:
    """T8a/T8b: per-participant box widths and constraint-based column layout."""

    def test_long_participant_box_is_wider(self) -> None:
        """VeryLongParticipantName box must be wider than Short box."""
        src = (FIXTURES / "sequence-constraint-layout.mmd").read_text(encoding="utf-8")
        html = to_html(src)
        widths = [int(m) for m in re.findall(
            r'class="node node-rect"[^>]+width:(\d+)px', html
        )]
        assert len(widths) >= 2, "Expected at least 2 participant boxes"
        assert widths[0] > widths[1], (
            f"VeryLongParticipantName box ({widths[0]}px) should exceed Short ({widths[1]}px)"
        )

    def test_lifelines_do_not_overlap(self) -> None:
        """All adjacent lifelines must be separated by at least 20 px."""
        src = (FIXTURES / "sequence-constraint-layout.mmd").read_text(encoding="utf-8")
        html = to_html(src)
        lines = re.findall(r'<line x1="(\d+)"[^>]*stroke-dasharray="5 4"', html)
        xs = sorted(int(x) for x in lines)
        for i in range(len(xs) - 1):
            gap = xs[i + 1] - xs[i]
            assert gap >= 20, f"Lifelines overlap: gap={gap}px between index {i} and {i + 1}"


class TestFragmentLabels:
    """T8b: fragment-header label forces column gap wide enough to show label."""

    def test_fragment_keywords_present(self) -> None:
        """loop/alt/else fragments must render their keyword in the HTML."""
        src = (FIXTURES / "sequence-fragment-labels.mmd").read_text(encoding="utf-8")
        html = to_html(src)
        assert "loop" in html.lower()
        assert "alt" in html.lower()

    def test_long_loop_condition_in_html(self) -> None:
        """Long loop condition label text must appear in the rendered HTML."""
        src = (FIXTURES / "sequence-fragment-labels.mmd").read_text(encoding="utf-8")
        html = to_html(src)
        assert "retry until success" in html


class TestRectRgba:
    """T11: RGBA rect fills must not carry a redundant opacity= attribute."""

    def test_no_double_alpha_on_rgba_rect(self) -> None:
        """rect with rgba() fill must not also have opacity= attribute."""
        src = (FIXTURES / "sequence-rect-rgba.mmd").read_text(encoding="utf-8")
        html = to_html(src)
        double_alpha = re.findall(
            r'<rect[^>]+fill="rgba\([^"]*\)"[^>]+opacity="[^"]*"', html
        )
        assert not double_alpha, f"Double-alpha rect found: {double_alpha}"

    def test_rgba_fill_present(self) -> None:
        """A rect rgba() fill must appear in the rendered HTML."""
        src = (FIXTURES / "sequence-rect-rgba.mmd").read_text(encoding="utf-8")
        html = to_html(src)
        assert "rgba(" in html.lower()


class TestActivationCentering:
    """T11: label midpoint uses activation-adjusted endpoints."""

    def test_activation_diagram_renders_all_participants(self) -> None:
        """All declared participants must appear in the HTML."""
        src = (FIXTURES / "sequence-activation-centering.mmd").read_text(encoding="utf-8")
        html = to_html(src)
        for pid in ("Alice", "Bob"):
            assert pid in html, f"Participant '{pid}' missing from HTML"

    def test_activation_labels_use_translatex_centering(self) -> None:
        """Edge labels must use translateX(-50%) centering (label-midpoint fix)."""
        src = (FIXTURES / "sequence-activation-centering.mmd").read_text(encoding="utf-8")
        html = to_html(src)
        edge_styles = re.findall(r'class="edge-label"[^>]+style="([^"]+)"', html)
        assert edge_styles, "No edge-labels found"
        for style in edge_styles:
            assert "translateX(-50%)" in style, (
                f"Edge label missing translateX(-50%) centering: {style}"
            )
