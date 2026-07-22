"""Tests for tools/compare_gallery.py — gallery exit code and status wiring."""
from __future__ import annotations

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
            _, has_failures = gallery._build_gallery([mmd], tmp_path / "out")

        assert has_failures is True

    def test_no_exit_1_when_all_ok(self, tmp_path, monkeypatch):
        """has_failures is False when the diagram renders successfully."""
        gallery = _import_gallery()

        mmd = tmp_path / "flowchart-basic.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")

        with patch.object(gallery, "_run_mmdc", return_value=(False, "mmdc not installed")):
            _, has_failures = gallery._build_gallery([mmd], tmp_path / "out")

        assert has_failures is False

    def test_exits_1_when_stub_backend(self, tmp_path, monkeypatch):
        """AC-7.2: has_failures is True when dispatch_native_result returns a stub backend."""
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        gallery = _import_gallery()

        mmd = tmp_path / "flowchart-stub.mmd"
        mmd.write_text("flowchart TD\n    A --> B\n", encoding="utf-8")

        # Inject a stub backend at the dispatch_native_result level.
        # validate() in __init__.py does `from .native_svg import dispatch_native_result`
        # each call, resolving via the mermaid_render.native_svg module object.
        import mermaid_render.native_svg as _nsv  # same module via scripts/ sys.path
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
        monkeypatch.setattr(_nsv, "dispatch_native_result", lambda *a, **kw: stub_result)

        with patch.object(gallery, "_run_mmdc", return_value=(False, "mmdc not installed")):
            _, has_failures = gallery._build_gallery([mmd], tmp_path / "out")

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

        with patch.object(gallery, "_build_gallery", return_value=(out / "index.html", True)):
            with pytest.raises(SystemExit) as exc:
                gallery.main()
        assert exc.value.code == 1
