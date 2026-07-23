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
            _, has_failures, _ = gallery._build_gallery([mmd], tmp_path / "out", allow_dirty=True)

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
            _, has_failures, _ = gallery._build_gallery([mmd], tmp_path / "out", allow_dirty=True)

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
        monkeypatch.setattr(_sys, "argv", ["compare_gallery", "--allow-dirty"])

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
            _, _, fixture_results = gallery._build_gallery(mmds, tmp_path / "out", allow_dirty=True)

        assert len(fixture_results) == 2
        for r in fixture_results:
            assert "render" in r
            assert "diagram_type" in r
            assert "renderer_backend" in r
            assert "geometry" in r
            assert "timestamp_utc" in r


class TestBaselineProvenance:
    """Task 9: tests covering ACs 1–13 of mermaid-current-head-comparison-baseline."""

    def _make_gallery(self, tmp_path, monkeypatch):
        """Helper: build a single-fixture gallery with mocked mmdc and git."""
        gallery = _import_gallery()
        mmd = tmp_path / "flowchart-basic.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")
        out = tmp_path / "out"
        with patch.object(gallery, "_run_mmdc", return_value=(False, "mmdc not installed")):
            _, _, fixture_results = gallery._build_gallery([mmd], out, allow_dirty=True)
        return gallery, out, fixture_results

    # ── AC1: HTML header must contain full 40-char git SHA ────────────────────

    def test_ac1_html_header_contains_full_sha(self, tmp_path):
        """AC1: gallery HTML header shows full 40-char git SHA."""
        gallery = _import_gallery()
        mmd = tmp_path / "flowchart-basic.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")
        out = tmp_path / "out"
        with patch.object(gallery, "_run_mmdc", return_value=(False, "no mmdc")):
            gallery._build_gallery([mmd], out, allow_dirty=True)

        html = (out / "index.html").read_text(encoding="utf-8")
        import re
        # header should contain a full 40-hex-char SHA somewhere
        assert re.search(r"sha:\s*[0-9a-f]{40}", html), "40-char SHA not found in HTML header"

    # ── AC2: dirty tree guard exits nonzero without --allow-dirty ─────────────

    def test_ac2_dirty_tree_returns_has_failures(self, tmp_path, monkeypatch):
        """AC2: build from dirty tree returns has_failures=True when allow_dirty=False."""
        gallery = _import_gallery()
        mmd = tmp_path / "flowchart-basic.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")

        # Monkeypatch subprocess.run so git status --short returns dirty output.
        import subprocess as _sp
        original_run = _sp.run

        def _fake_run(cmd, **kw):
            if isinstance(cmd, list) and "status" in cmd and "--short" in cmd:
                from unittest.mock import MagicMock
                r = MagicMock()
                r.stdout = " M tools/compare_gallery.py\n"
                r.returncode = 0
                return r
            return original_run(cmd, **kw)

        monkeypatch.setattr(gallery.subprocess, "run", _fake_run)
        _, has_failures, results = gallery._build_gallery([mmd], tmp_path / "out")
        assert has_failures is True
        assert any(r.get("error") == "dirty-tree" for r in results)

    def test_ac2_dirty_tree_allowed_with_flag(self, tmp_path):
        """AC2: dirty tree is allowed when allow_dirty=True; no dirty-tree error record."""
        gallery = _import_gallery()
        mmd = tmp_path / "flowchart-basic.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")
        with patch.object(gallery, "_run_mmdc", return_value=(False, "")):
            _, _, results = gallery._build_gallery([mmd], tmp_path / "out", allow_dirty=True)
        assert not any(r.get("error") == "dirty-tree" for r in results), \
            "dirty-tree error record present even though allow_dirty=True"

    # ── AC3: per-fixture provenance keys ─────────────────────────────────────

    def test_ac3_provenance_all_keys_present(self, tmp_path):
        """AC3: per-fixture provenance dict contains all required keys."""
        gallery, out, fixture_results = self._make_gallery(tmp_path, None)
        required_keys = [
            "actual_layout_backend", "fallback_reason", "faithful", "theme",
            "width_hint", "height_hint", "output_width", "output_height",
            "output_viewbox", "renderer_api", "fixture_sha256", "name", "path",
        ]
        assert len(fixture_results) >= 1
        prov = fixture_results[0]
        missing = [k for k in required_keys if k not in prov]
        assert not missing, f"provenance missing keys: {missing}"

    # ── AC5: fidelity lane renders with faithful=True ──────────────────────────

    def test_ac5_fidelity_render_uses_faithful_true(self, tmp_path):
        """AC5: _render_fidelity calls to_html with faithful=True."""
        gallery = _import_gallery()
        calls: list = []

        def _capture_to_html(src, **kw):
            calls.append(kw)
            return "<html><body><div class='diagram'></div></body></html>"

        original = gallery.mermaid_render.to_html
        gallery.mermaid_render.to_html = _capture_to_html
        try:
            gallery._render_fidelity("flowchart TD\n  A-->B")
        finally:
            gallery.mermaid_render.to_html = original

        assert calls, "to_html was not called"
        assert calls[0].get("faithful") is True, f"faithful not True in call kwargs: {calls[0]}"

    def test_ac5_fidelity_render_uses_neutral_theme(self, tmp_path):
        """AC5: _render_fidelity passes theme='neutral'."""
        gallery = _import_gallery()
        calls: list = []

        def _capture_to_html(src, **kw):
            calls.append(kw)
            return "<html><body></body></html>"

        original = gallery.mermaid_render.to_html
        gallery.mermaid_render.to_html = _capture_to_html
        try:
            gallery._render_fidelity("flowchart TD\n  A-->B")
        finally:
            gallery.mermaid_render.to_html = original

        assert calls[0].get("theme") == "neutral"

    # ── AC10: missing backend field is hard fail ───────────────────────────────

    def test_ac10_missing_backend_field_is_hard_fail(self, tmp_path):
        """AC10: fixture with empty actual_layout_backend triggers has_failures."""
        gallery = _import_gallery()
        bad_rec = {
            "name": "flowchart-test",
            "actual_layout_backend": "",
            "fallback_reason": None,
            "mmdc_ok": False,
        }
        failures = gallery._validate_outputs([bad_rec], tmp_path, target_names=["flowchart-test"])
        assert failures, "expected at least one failure for empty backend"
        assert any("actual_layout_backend" in f for f in failures)

    # ── AC7: ELK fallback without reason is hard fail ─────────────────────────

    def test_ac7_elk_fallback_without_reason_is_hard_fail(self, tmp_path):
        """AC7: python-fallback with no fallback_reason triggers has_failures."""
        gallery = _import_gallery()
        bad_rec = {
            "name": "flowchart-test",
            "actual_layout_backend": "python-fallback",
            "fallback_reason": None,
            "mmdc_ok": False,
        }
        failures = gallery._validate_outputs([bad_rec], tmp_path, target_names=["flowchart-test"])
        assert failures, "expected failure for python-fallback without reason"
        assert any("python-fallback" in f for f in failures)

    # ── AC8: missing mmdc asset is hard fail ──────────────────────────────────

    def test_ac8_missing_mmdc_asset_is_hard_fail(self, tmp_path):
        """AC8: mmdc_ok=True but SVG absent → hard fail."""
        gallery = _import_gallery()
        (tmp_path / "mmdc").mkdir()
        rec = {
            "name": "flowchart-test",
            "actual_layout_backend": "python-fallback",
            "fallback_reason": "no node",
            "mmdc_ok": True,  # mmdc was expected to produce SVG
        }
        failures = gallery._validate_outputs([rec], tmp_path, target_names=["flowchart-test"])
        assert failures, "expected failure for missing mmdc SVG"
        assert any("mmdc SVG missing" in f for f in failures)

    # ── AC12: provenance details block present per fixture ────────────────────

    def test_ac12_provenance_block_present_per_fixture(self, tmp_path):
        """AC12: every fixture section in index.html has a <details> provenance block."""
        gallery, out, _ = self._make_gallery(tmp_path, None)
        html = (out / "index.html").read_text(encoding="utf-8")
        import re
        # Find <details> blocks that contain provenance JSON (have actual_layout_backend)
        details_count = len(re.findall(r"<details>.*?actual_layout_backend.*?</details>", html, re.DOTALL))
        assert details_count >= 1, "No provenance details blocks found in index.html"

    def test_ac12_provenance_json_includes_backend_field(self, tmp_path):
        """AC12: provenance JSON in <details> contains actual_layout_backend key."""
        gallery, out, _ = self._make_gallery(tmp_path, None)
        html = (out / "index.html").read_text(encoding="utf-8")
        import re
        # Extract JSON from the provenance details block
        m = re.search(r'<details><summary>provenance</summary><pre>(.*?)</pre></details>', html, re.DOTALL)
        assert m, "no provenance details block found"
        import html as _html_mod
        prov_json = _html_mod.unescape(m.group(1))
        prov = json.loads(prov_json)
        assert "actual_layout_backend" in prov

    # ── AC2 via main(): --allow-dirty flag wired through to argparse ──────────

    def test_ac2_main_allow_dirty_flag_parsed(self, tmp_path, monkeypatch):
        """AC2: --allow-dirty flag prevents dirty-tree failure in main()."""
        gallery = _import_gallery()
        mmd = tmp_path / "flowchart-basic.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")
        out = tmp_path / "out"

        monkeypatch.setattr(gallery, "_run_mmdc", lambda *a, **kw: (False, ""))
        monkeypatch.setattr(gallery, "_collect_metadata", lambda *a, **kw: {})
        monkeypatch.setattr(gallery, "_assert_module_provenance", lambda *a, **kw: None)
        monkeypatch.setattr(gallery, "FIXTURES_DIR", tmp_path)
        monkeypatch.setattr(gallery, "OUT_DIR", out)
        out.mkdir(parents=True, exist_ok=True)

        import sys as _sys
        monkeypatch.setattr(_sys, "argv", ["compare_gallery", "--allow-dirty"])
        gallery.main()  # should not raise SystemExit

    # ── collect_metadata node/elkjs version fields ────────────────────────────

    def test_collect_metadata_includes_node_version_key(self, tmp_path):
        """Task 2: _collect_metadata result has node_version key (may be None)."""
        gallery = _import_gallery()
        meta = gallery._collect_metadata([], tmp_path, 0, [])
        assert "node_version" in meta

    def test_collect_metadata_includes_elkjs_version_key(self, tmp_path):
        """Task 2: _collect_metadata result has elkjs_version key (may be None)."""
        gallery = _import_gallery()
        meta = gallery._collect_metadata([], tmp_path, 0, [])
        assert "elkjs_version" in meta

    # ── AC11: mmdc SVG inlined in HTML (not external iframe) ─────────────────

    def test_ac11_mmdc_svg_inlined_when_mmdc_ok(self, tmp_path):
        """AC11: when mmdc succeeds, SVG content is inlined in HTML, not an iframe with src."""
        gallery = _import_gallery()
        mmd = tmp_path / "flowchart-basic.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")

        def _fake_mmdc(src, out_svg, **kw):
            out_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><rect/></svg>')
            return True, ""

        with patch.object(gallery, "_run_mmdc", side_effect=_fake_mmdc):
            gallery._build_gallery([mmd], tmp_path / "out", allow_dirty=True)

        html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
        # Should have inline SVG class, not an iframe src pointing to mmdc/
        assert 'mmdc-inline-svg' in html, "mmdc-inline-svg class missing from HTML"
        assert '<iframe class="mmdc-frame"' not in html, "old iframe mmdc-frame still present"

    # ── AC4: all target fixtures present in artifact ─────────────────────────

    def test_ac4_all_15_fixtures_in_artifact(self, tmp_path):
        """AC4: all 15 target fixtures produce entries in fixture_results."""
        gallery = _import_gallery()
        # Create all 15 target fixture files.
        target_names = [
            "architecture-complex", "class-relationships-all", "er-cardinality-all",
            "er-ecommerce", "flowchart-all-shapes", "flowchart-arrows-defs",
            "flowchart-diamond-branch", "flowchart-diamond-clipping",
            "flowchart-empty-subgraph", "flowchart-groups-complex",
            "flowchart-inner-direction", "flowchart-parallel-links",
            "requirement-basic", "statediagram-complex", "statediagram-nested",
        ]
        mmd_files = []
        for name in target_names:
            p = tmp_path / f"{name}.mmd"
            p.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")
            mmd_files.append(p)

        with patch.object(gallery, "_run_mmdc", return_value=(False, "no mmdc")):
            _, _, fixture_results = gallery._build_gallery(mmd_files, tmp_path / "out", allow_dirty=True)

        result_names = {r.get("name") for r in fixture_results}
        missing = [n for n in target_names if n not in result_names]
        assert not missing, f"Missing fixture results: {missing}"
        assert len(fixture_results) == 15

    # ── AC13: npm ci called before rendering in generate_baseline ─────────────

    def test_ac13_npm_ci_called_before_render(self, tmp_path, monkeypatch):
        """AC13: generate_baseline.py calls _run_npm_ci before _build_gallery."""
        import importlib.util
        import sys
        baseline_path = ROOT / "tools" / "generate_baseline.py"
        if not baseline_path.exists():
            import pytest
            pytest.skip("generate_baseline.py not found")

        spec = importlib.util.spec_from_file_location("generate_baseline", baseline_path)
        baseline_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(baseline_mod)  # type: ignore[union-attr]

        call_order: list[str] = []

        def _mock_npm_ci():
            call_order.append("npm_ci")

        def _mock_build_gallery(*a, **kw):
            call_order.append("build_gallery")
            return (tmp_path / "index.html"), False, []

        def _mock_collect_metadata(*a, **kw):
            return {}

        # Patch high-level functions so we don't need real fixtures or root.
        monkeypatch.setattr(baseline_mod, "_run_npm_ci", _mock_npm_ci)

        # Provide real fixture files.
        fixtures_dir = ROOT / "tests" / "fixtures"
        monkeypatch.setattr(baseline_mod, "_TARGET_FIXTURES", ["flowchart-diamond-branch"])
        monkeypatch.setattr(baseline_mod, "ROOT", ROOT)

        import importlib as _il
        import importlib.util as _ilu
        gallery_spec = _ilu.spec_from_file_location("compare_gallery", ROOT / "tools" / "compare_gallery.py")
        gallery_mod = _ilu.module_from_spec(gallery_spec)  # type: ignore[arg-type]
        gallery_spec.loader.exec_module(gallery_mod)  # type: ignore[union-attr]
        monkeypatch.setattr(gallery_mod, "_build_gallery", _mock_build_gallery)

        # Patch importlib.util.module_from_spec to return our pre-patched gallery_mod.
        original_mfs = _ilu.module_from_spec

        def _patched_mfs(s):
            if getattr(s, "name", "") == "compare_gallery":
                return gallery_mod
            return original_mfs(s)

        import importlib.util as _ilu2
        monkeypatch.setattr(_ilu2, "module_from_spec", _patched_mfs)

        monkeypatch.setattr(sys, "argv", ["generate_baseline", "--allow-dirty"])
        try:
            baseline_mod.main()
        except SystemExit:
            pass

        npm_idx = next((i for i, v in enumerate(call_order) if v == "npm_ci"), None)
        build_idx = next((i for i, v in enumerate(call_order) if v == "build_gallery"), None)
        assert npm_idx is not None, f"_run_npm_ci was never called; order: {call_order}"
        if build_idx is not None:
            assert npm_idx < build_idx, f"npm_ci must precede build_gallery; order: {call_order}"


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
