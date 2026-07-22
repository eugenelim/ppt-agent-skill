"""Tests for tools/compare_gallery.py — gallery exit code and status wiring."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))


def _import_gallery():
    import importlib
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "compare_gallery", ROOT / "tools" / "compare_gallery.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGalleryExitCode:
    """AC-P0.5: gallery exits 1 when any diagram has invalid/error status."""

    def test_exits_1_when_render_fails(self, tmp_path, monkeypatch):
        """has_failures is True when _render_ours returns None (render failure)."""
        gallery = _import_gallery()

        mmd = tmp_path / "flowchart-test.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")

        monkeypatch.setattr(gallery, "_render_ours", lambda *a, **kw: (None, "forced failure"))

        with patch.object(gallery, "_run_mmdc", return_value=(False, "mmdc not installed")):
            _, has_failures, _ = gallery._build_gallery([mmd], tmp_path / "out")

        assert has_failures is True

    def test_no_exit_1_when_all_ok(self, tmp_path, monkeypatch):
        """has_failures is False when the diagram renders successfully."""
        gallery = _import_gallery()

        mmd = tmp_path / "flowchart-basic.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")

        with patch.object(gallery, "_run_mmdc", return_value=(False, "mmdc not installed")):
            _, has_failures, _ = gallery._build_gallery([mmd], tmp_path / "out")

        assert has_failures is False

    def test_exits_1_when_stub_backend(self, tmp_path, monkeypatch):
        """AC-7.2: has_failures is True when dispatch_native_result returns a stub backend."""
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        gallery = _import_gallery()

        mmd = tmp_path / "flowchart-stub.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")

        # Inject a stub backend at the dispatch_native_result level.
        # validate() calls dispatch_native_result() from mermaid_render.__init__,
        # so patch the mermaid_render module attribute directly.
        import mermaid_render as _mr  # same module via scripts/ sys.path
        from mermaid_render.registry import RenderResult
        stub_result = RenderResult(
            svg="<svg/>",
            diagram_type="flowchart",
            backend="native-svg-stub",
            semantic_adapter="passed",
            syntax_coverage="passed",
            geometry="unvalidated",
            serialization="passed",
            warnings=(),
            errors=(),
        )
        monkeypatch.setattr(_mr, "dispatch_native_result", lambda *a, **kw: stub_result)

        with patch.object(gallery, "_run_mmdc", return_value=(False, "mmdc not installed")):
            _, has_failures, _ = gallery._build_gallery([mmd], tmp_path / "out")

        assert has_failures is True

    def test_main_exits_1_on_invalid_status(self, tmp_path, monkeypatch):
        """main() calls sys.exit(1) when has_failures is True."""
        import pytest
        gallery = _import_gallery()

        mmd = tmp_path / "flowchart-test.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")
        out = tmp_path / "out"

        monkeypatch.setattr(gallery, "_run_mmdc", lambda *a, **kw: (False, ""))
        monkeypatch.setattr(gallery, "_collect_metadata", lambda *a, **kw: {})
        monkeypatch.setattr(gallery, "FIXTURES_DIR", tmp_path)
        monkeypatch.setattr(gallery, "OUT_DIR", out)

        import sys as _sys
        monkeypatch.setattr(_sys, "argv", ["compare_gallery"])

        with patch.object(gallery, "_build_gallery", return_value=(out / "index.html", True, [])):
            with pytest.raises(SystemExit) as exc:
                gallery.main()
        assert exc.value.code == 1


class TestGalleryFixtureProvenance:
    """Stage 13 Task D: per-fixture provenance block in gallery metadata.json."""

    def test_fixture_results_written_to_metadata(self, tmp_path, monkeypatch):
        """Gallery run must write fixture_results provenance to metadata.json."""
        gallery = _import_gallery()

        mmd = tmp_path / "flowchart-basic.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()

        monkeypatch.setattr(gallery, "_run_mmdc", lambda *a, **kw: (False, "mmdc not installed"))
        monkeypatch.setattr(gallery, "_collect_metadata", lambda *a, **kw: {})
        monkeypatch.setattr(gallery, "_assert_module_provenance", lambda *a, **kw: None)
        monkeypatch.setattr(gallery, "FIXTURES_DIR", tmp_path)
        monkeypatch.setattr(gallery, "OUT_DIR", out)

        import sys as _sys
        monkeypatch.setattr(_sys, "argv", ["compare_gallery"])

        gallery.main()

        meta_path = out / "metadata.json"
        assert meta_path.exists(), "metadata.json not written"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert "fixture_results" in meta, "fixture_results key missing from metadata.json"

        results = meta["fixture_results"]
        assert len(results) == 1, f"expected 1 fixture result, got {len(results)}"
        r = results[0]
        for field in ("diagram_type", "renderer_backend", "geometry", "render", "timestamp_utc"):
            assert field in r, f"fixture result missing field {field!r}"

    def test_fixture_results_one_per_rendered_fixture(self, tmp_path, monkeypatch):
        """fixture_results has exactly one entry per fixture that renders."""
        gallery = _import_gallery()

        mmds = []
        for name in ("flowchart-a.mmd", "flowchart-b.mmd"):
            p = tmp_path / name
            p.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")
            mmds.append(p)

        with patch.object(gallery, "_run_mmdc", return_value=(False, "no mmdc")):
            _, _, fixture_results = gallery._build_gallery(mmds, tmp_path / "out")

        assert len(fixture_results) == 2
        for r in fixture_results:
            assert "render" in r
            assert "diagram_type" in r
            assert "renderer_backend" in r
            assert "geometry" in r
            assert "timestamp_utc" in r


class TestGalleryOracleSourceSha256:
    """Stage 13 Task E: oracle cases must carry source_sha256 fields after recapture."""

    def test_oracle_cases_have_source_sha256(self):
        """Every oracle case JSON must include a source_sha256 field.

        Requires prior `capture-reference` run with mmdc available.
        If the field is absent the backlog item mmdc-oracle-recapture is still pending.
        """
        oracle_dir = ROOT / "tests" / "fidelity" / "oracle"
        if not oracle_dir.exists():
            import pytest
            pytest.skip("oracle directory not found")

        cases_dirs = list(oracle_dir.glob("*/cases"))
        if not cases_dirs:
            import pytest
            pytest.skip("no oracle cases found — run capture-reference first")

        missing = []
        for cases_dir in cases_dirs:
            for case_file in sorted(cases_dir.glob("*.json")):
                data = json.loads(case_file.read_text(encoding="utf-8"))
                if "source_sha256" not in data:
                    missing.append(str(case_file.relative_to(ROOT)))

        assert not missing, (
            f"{len(missing)} oracle case(s) missing source_sha256 "
            f"(see docs/backlog.md mmdc-oracle-recapture): {missing[:5]}"
        )
