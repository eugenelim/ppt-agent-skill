"""test_deliverable_gate.py — check_deliverable_gate blocks export unless
planning/*.json passes planning_validator AND runtime/proof/gate.json is present.

Covers:
  - skip when no planning/ dir (non-deck context, deck_required=False)
  - fail when no planning/ dir and deck_required=True (html_packager / svg2pptx)
  - block when planning/ exists but has no JSON files
  - block when planning fails validation
  - block when planning passes but gate.json is absent
  - pass when planning is valid and gate.json records a decision
  - milestone_check.check_preview / check_step5 also enforce gate_status
  - html_packager.py and svg2pptx.py CLI: exit 1 when gate not satisfied
  - html2svg.py (mermaid_render/svg.py) CLI: exit 1 when gate not satisfied,
    skip when no planning/ dir
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from proof_gate import check_deliverable_gate, record_decision  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal valid planning page that passes planning_validator with --refs.
# Derived from test_planning_schema_compliance.py's base_content_page().
# ---------------------------------------------------------------------------
_VALID_PAGE = {
    "page": {
        "slide_number": 3,
        "page_type": "content",
        "narrative_role": "evidence",
        "narrative_archetype": "persuasive",
        "title": "Test",
        "page_goal": "test",
        "audience_takeaway": "x",
        "visual_weight": 5,
        "density_label": "medium",
        "density_reason": "test",
        "density_contract": {
            "deck_bias": "balanced",
            "page_lower_bound": "mid_low",
            "page_upper_bound": "high",
            "max_cards": 4,
            "max_charts": 2,
            "min_body_font_px": 18,
            "max_lines_per_card": 5,
            "image_policy": "support_only",
            "decoration_budget": "medium",
            "overflow_strategy": "tighten_budget",
        },
        "layout_hint": "mixed-grid",
        "director_command": {"mood": "m"},
        "decoration_hints": {"background": {}},
        "source_guidance": {"strictness": "s"},
        "resources": {
            "page_template": None,
            "layout_refs": ["mixed-grid"],
            "block_refs": [],
            "chart_refs": [],
            "principle_refs": [],
        },
        "cards": [
            {
                "card_id": "s3-anchor-1",
                "role": "anchor",
                "card_type": "text",
                "card_style": "elevated",
                "argument_role": "evidence",
                "headline": "H",
                "body": ["a body sentence"],
                "data_points": [],
                "chart": None,
                "content_budget": {"body_max_lines": 3},
                "image": {
                    "needed": False,
                    "usage": None,
                    "placement": None,
                    "content_description": None,
                    "source_hint": None,
                },
            }
        ],
        "workflow_metadata": {"stage": "planning"},
    }
}

_INVALID_PAGE = {"page": {"slide_number": 1, "page_type": "INVALID_TYPE"}}


def _write_planning(planning_dir: Path, payload: dict) -> None:
    planning_dir.mkdir(parents=True, exist_ok=True)
    (planning_dir / "planning1.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _record_gate(deck_dir: Path, decision: str = "render-direct") -> None:
    record_decision(deck_dir, decision)


# ---------------------------------------------------------------------------
# check_deliverable_gate unit tests
# ---------------------------------------------------------------------------

class TestCheckDeliverableGate:
    def test_skip_no_planning_dir(self, tmp_path):
        ok, msg = check_deliverable_gate(tmp_path)
        assert ok
        assert "non-deck context" in msg

    def test_fail_no_planning_dir_when_deck_required(self, tmp_path):
        ok, msg = check_deliverable_gate(tmp_path, deck_required=True)
        assert not ok
        assert "no planning/" in msg

    def test_fail_planning_dir_exists_but_empty(self, tmp_path):
        (tmp_path / "planning").mkdir()
        ok, msg = check_deliverable_gate(tmp_path)
        assert not ok
        assert "no planning JSON" in msg

    def test_fail_invalid_planning_json(self, tmp_path):
        _write_planning(tmp_path / "planning", _INVALID_PAGE)
        ok, msg = check_deliverable_gate(tmp_path)
        assert not ok
        assert "planning validation failed" in msg

    def test_fail_valid_planning_but_no_gate(self, tmp_path):
        _write_planning(tmp_path / "planning", _VALID_PAGE)
        ok, msg = check_deliverable_gate(tmp_path)
        assert not ok
        # gate_status message names Step 4.5 or proof_gate.py
        assert "Step 4.5" in msg or "proof_gate.py" in msg

    def test_pass_valid_planning_and_gate(self, tmp_path):
        _write_planning(tmp_path / "planning", _VALID_PAGE)
        _record_gate(tmp_path)
        ok, msg = check_deliverable_gate(tmp_path)
        assert ok


# ---------------------------------------------------------------------------
# milestone_check gate_status wiring
# ---------------------------------------------------------------------------

class TestMilestoneCheckGateWiring:
    """gate_status is checked in check_preview and check_step5."""

    def _make_checker(self, tmp_path):
        import milestone_check as M
        return M.Checker(skill_dir=REPO_ROOT, output_dir=tmp_path, target="preview")

    def test_check_preview_fails_without_gate(self, tmp_path):
        # Create the minimum artifacts for check_preview to reach the gate check.
        (tmp_path / "deck-preview.html").touch()
        checker = self._make_checker(tmp_path)
        with pytest.raises(RuntimeError, match="proof gate not recorded"):
            checker.check_preview()

    def test_check_preview_passes_with_gate(self, tmp_path):
        (tmp_path / "deck-preview.html").touch()
        _record_gate(tmp_path)
        checker = self._make_checker(tmp_path)
        checker.check_preview()  # must not raise


# ---------------------------------------------------------------------------
# CLI subprocess tests — html_packager.py and svg2pptx.py must exit 1 when gate
# not satisfied (even if their other preconditions are met).
# ---------------------------------------------------------------------------

class TestCliGateEnforcement:
    """Run the export scripts as subprocesses and assert gate exit behaviour."""

    def _setup_deck(self, tmp_path: Path, *, valid_planning: bool, record_gate: bool) -> Path:
        """Create a minimal deck tree. Returns slides_dir."""
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "slide-1.html").write_text("<html><body>slide</body></html>")
        if valid_planning:
            _write_planning(tmp_path / "planning", _VALID_PAGE)
        if record_gate:
            _record_gate(tmp_path)
        return slides_dir

    def test_html_packager_blocked_no_planning(self, tmp_path):
        slides_dir = self._setup_deck(tmp_path, valid_planning=False, record_gate=False)
        # planning/ dir exists but is empty → gate blocks
        (tmp_path / "planning").mkdir()
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "html_packager.py"), str(slides_dir)],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
        assert "gate" in r.stderr.lower()

    def test_html_packager_blocked_no_gate(self, tmp_path):
        slides_dir = self._setup_deck(tmp_path, valid_planning=True, record_gate=False)
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "html_packager.py"), str(slides_dir)],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
        assert "gate" in r.stderr.lower()

    def test_html_packager_passes_with_valid_gate(self, tmp_path):
        slides_dir = self._setup_deck(tmp_path, valid_planning=True, record_gate=True)
        out = tmp_path / "preview.html"
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "html_packager.py"), str(slides_dir),
             "-o", str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        assert out.exists()

    def test_html_packager_blocked_when_no_planning_dir(self, tmp_path):
        """html_packager is deck-only (deck_required=True): absent planning/ is a failure."""
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "slide-1.html").write_text("<html><body>slide</body></html>")
        # No planning/ dir at all — should block, not skip.
        out = tmp_path / "preview.html"
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "html_packager.py"), str(slides_dir),
             "-o", str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
        assert "gate" in r.stderr.lower()

    def test_svg2pptx_blocked_no_gate(self, tmp_path):
        svg_dir = tmp_path / "svg"
        svg_dir.mkdir()
        (svg_dir / "slide-1.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
        )
        _write_planning(tmp_path / "planning", _VALID_PAGE)
        # No gate.json → blocked.
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "svg2pptx.py"), str(svg_dir),
             "-o", str(tmp_path / "out.pptx")],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
        assert "gate" in r.stderr.lower()

    def test_svg2pptx_blocked_when_no_planning_dir(self, tmp_path):
        """svg2pptx is deck-only (deck_required=True): absent planning/ is a failure."""
        svg_dir = tmp_path / "svg"
        svg_dir.mkdir()
        (svg_dir / "slide-1.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
        )
        # No planning/ dir — should block, not skip.
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "svg2pptx.py"), str(svg_dir),
             "-o", str(tmp_path / "out.pptx")],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
        assert "gate" in r.stderr.lower()


# ---------------------------------------------------------------------------
# milestone_check.check_step5 gate wiring
# ---------------------------------------------------------------------------

class TestMilestoneCheckStep5GateWiring:
    """gate_status is checked in check_step5."""

    def _make_checker(self, tmp_path):
        import milestone_check as M
        return M.Checker(skill_dir=REPO_ROOT, output_dir=tmp_path, target="5")

    def _populate_step5_artifacts(self, tmp_path: Path, pages: int = 1) -> None:
        """Create minimal Step-5 artifacts so check_step5 reaches the gate check.

        _VALID_PAGE has slide_number=3 but counts as 1 page (one JSON file).
        Artifact names follow the contract_validator delivery-manifest schema:
          artifacts.preview_html / artifacts.presentation_png_pptx / artifacts.presentation_svg_pptx
        """
        import json as _json
        _write_planning(tmp_path / "planning", _VALID_PAGE)
        preview = tmp_path / f"{tmp_path.name}-preview.html"
        preview.touch()
        png_dir = tmp_path / "png"
        png_dir.mkdir(exist_ok=True)
        svg_dir = tmp_path / "svg"
        svg_dir.mkdir(exist_ok=True)
        for i in range(1, pages + 1):
            (png_dir / f"slide-{i}.png").touch()
            (svg_dir / f"slide-{i}.svg").touch()
        png_pptx = tmp_path / f"{tmp_path.name}-png.pptx"
        svg_pptx = tmp_path / f"{tmp_path.name}-svg.pptx"
        png_pptx.touch()
        svg_pptx.touch()
        manifest = {
            "run_id": "test-run",
            "generated_at": "2026-07-22T00:00:00Z",
            "artifacts": {
                "preview_html": str(preview),
                "presentation_png_pptx": str(png_pptx),
                "presentation_svg_pptx": str(svg_pptx),
            },
        }
        (tmp_path / "delivery-manifest.json").write_text(
            _json.dumps(manifest), encoding="utf-8"
        )

    def test_check_step5_fails_without_gate(self, tmp_path):
        self._populate_step5_artifacts(tmp_path)
        checker = self._make_checker(tmp_path)
        with pytest.raises(RuntimeError, match="proof gate not recorded"):
            checker.check_step5()

    def test_check_step5_passes_with_gate(self, tmp_path):
        self._populate_step5_artifacts(tmp_path)
        _record_gate(tmp_path)
        checker = self._make_checker(tmp_path)
        checker.check_step5()  # must not raise


# ---------------------------------------------------------------------------
# CLI subprocess tests — html2svg.py (mermaid_render/svg.py) gate enforcement
# ---------------------------------------------------------------------------

class TestHtml2SvgGateEnforcement:
    """html2svg gate runs via subprocess — verify exit behaviour."""

    HTML2SVG = SCRIPTS / "html2svg.py"  # backward-compat shim that calls mermaid_render.svg.main()

    def _setup_deck(self, tmp_path: Path, *, valid_planning: bool, record_gate: bool) -> Path:
        """Create a minimal deck tree. Returns slides_dir (html dir)."""
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "slide-1.html").write_text(
            "<html><body><div class='mermaid'>graph LR; A-->B</div></body></html>"
        )
        if valid_planning:
            _write_planning(tmp_path / "planning", _VALID_PAGE)
        if record_gate:
            _record_gate(tmp_path)
        return slides_dir

    def test_html2svg_blocked_no_planning(self, tmp_path):
        slides_dir = self._setup_deck(tmp_path, valid_planning=False, record_gate=False)
        (tmp_path / "planning").mkdir()  # present but empty
        r = subprocess.run(
            [sys.executable, str(self.HTML2SVG), str(slides_dir),
             "-o", str(tmp_path / "svg")],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
        assert "gate" in r.stderr.lower()

    def test_html2svg_blocked_no_gate(self, tmp_path):
        slides_dir = self._setup_deck(tmp_path, valid_planning=True, record_gate=False)
        r = subprocess.run(
            [sys.executable, str(self.HTML2SVG), str(slides_dir),
             "-o", str(tmp_path / "svg")],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
        # proof_gate.py --check emits to stderr
        assert "gate" in r.stderr.lower() or "step 4.5" in r.stderr.lower()

    def test_html2svg_non_deck_skip(self, tmp_path):
        """html2svg allows non-deck use (no planning/ dir → gate skips)."""
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "diagram.html").write_text(
            "<html><body><div class='mermaid'>graph LR; A-->B</div></body></html>"
        )
        # No planning/ dir — gate should skip, not block.
        r = subprocess.run(
            [sys.executable, str(self.HTML2SVG), str(slides_dir),
             "-o", str(tmp_path / "svg")],
            capture_output=True, text=True,
        )
        # Exit code may be non-zero due to Chromium not being installed in test env,
        # but it must NOT fail due to the gate (no "gate" in stderr).
        assert "gate" not in r.stderr.lower(), f"gate should not block: {r.stderr}"
