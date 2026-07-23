"""tests/test_assemble_diagram_slide.py — unit tests for assemble_diagram_slide."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Make scripts/ importable
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import assemble_diagram_slide as _mod

# Synthetic fragment with a known viewBox
_FRAGMENT_800x600 = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" width="800" height="600">'
    '<rect x="10" y="10" width="100" height="50" />'
    "</svg>"
)
_FRAGMENT_NO_VIEWBOX = "<svg><rect /></svg>"


class TestParseViewbox(unittest.TestCase):
    def test_parses_width_height(self):
        w, h = _mod._parse_viewbox(_FRAGMENT_800x600)
        self.assertEqual(w, 800)
        self.assertEqual(h, 600)

    def test_returns_zero_when_missing(self):
        w, h = _mod._parse_viewbox(_FRAGMENT_NO_VIEWBOX)
        self.assertEqual((w, h), (0, 0))

    def test_returns_zero_on_empty(self):
        w, h = _mod._parse_viewbox("")
        self.assertEqual((w, h), (0, 0))

    def test_float_viewbox_values(self):
        frag = '<svg viewBox="0 0 1200.5 900.7"></svg>'
        w, h = _mod._parse_viewbox(frag)
        self.assertEqual(w, 1200)
        self.assertEqual(h, 900)


class TestAssembleSlide(unittest.TestCase):
    """Tests for assemble_slide() — no CLI, no file I/O."""

    def test_fragment_appears_in_output(self):
        result = _mod.assemble_slide(_FRAGMENT_800x600)
        self.assertIn(_FRAGMENT_800x600, result)

    def test_no_style_produces_adaptive_theme(self):
        """Without --style, render_page is called with theme=None (adaptive CSS vars)."""
        result = _mod.assemble_slide(_FRAGMENT_800x600)
        # Adaptive page uses prefers-color-scheme media query
        self.assertIn("prefers-color-scheme", result)

    def test_style_path_bakes_css_variables(self):
        """With a style.json, css_variables dict is baked into the HTML."""
        css_vars = {"--bg-primary": "#FF0000", "--text-primary": "#00FF00"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"css_variables": css_vars}, f)
            style_path = f.name
        try:
            result = _mod.assemble_slide(_FRAGMENT_800x600, style_path=style_path)
            self.assertIn("--bg-primary: #FF0000", result)
            self.assertIn("--text-primary: #00FF00", result)
            # Baked page has no prefers-color-scheme
            self.assertNotIn("prefers-color-scheme", result)
        finally:
            Path(style_path).unlink()

    def test_title_appears_in_output(self):
        result = _mod.assemble_slide(_FRAGMENT_800x600, title="My Title")
        self.assertIn('<h1 class="slide-title">My Title</h1>', result)

    def test_annotation_appears_in_output(self):
        result = _mod.assemble_slide(_FRAGMENT_800x600, annotation="Caption text")
        self.assertIn('<p class="slide-annotation">Caption text</p>', result)

    def test_title_and_annotation_inject_css(self):
        result = _mod.assemble_slide(_FRAGMENT_800x600, title="T", annotation="A")
        self.assertIn("slide-title", result)
        self.assertIn("slide-annotation", result)
        # CSS block should appear
        self.assertIn("<style>", result)

    def test_no_title_no_annotation_no_extra_css(self):
        result = _mod.assemble_slide(_FRAGMENT_800x600)
        self.assertNotIn("slide-title", result)
        self.assertNotIn("slide-annotation", result)

    def test_title_is_html_escaped(self):
        result = _mod.assemble_slide(_FRAGMENT_800x600, title="<script>alert(1)</script>")
        self.assertNotIn("<script>alert(1)</script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_annotation_is_html_escaped(self):
        result = _mod.assemble_slide(_FRAGMENT_800x600, annotation='<b onclick="bad()">x</b>')
        self.assertNotIn('<b onclick=', result)


class TestMainCLI(unittest.TestCase):
    """Integration tests for main() with mocked _dispatch."""

    def _run(self, argv: list[str]) -> str:
        """Run main() with given argv, capture stdout."""
        import io
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            _mod.main(argv)
        finally:
            sys.stdout = old_stdout
        return buf.getvalue()

    def test_fragment_input_dims_comment(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(_FRAGMENT_800x600)
            frag_path = f.name
        try:
            result = self._run(["--fragment", frag_path])
            self.assertTrue(result.startswith("<!-- dims: 800x600 -->"))
        finally:
            Path(frag_path).unlink()

    def test_fragment_input_no_viewbox_dims(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(_FRAGMENT_NO_VIEWBOX)
            frag_path = f.name
        try:
            result = self._run(["--fragment", frag_path])
            self.assertTrue(result.startswith("<!-- dims: 0x0 -->"))
        finally:
            Path(frag_path).unlink()

    def test_source_input_renders_via_dispatch(self):
        """--source calls _dispatch, result is assembled into HTML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
            f.write("flowchart LR\n  A --> B\n")
            src_path = f.name
        fake_fragment = _FRAGMENT_800x600
        with patch.object(_mod, "_dispatch", return_value=fake_fragment) as mock_dispatch:
            result = self._run(["--source", src_path])
            mock_dispatch.assert_called_once()
            call_args = mock_dispatch.call_args
            # First arg is the source text, third arg is width hint
            self.assertIn("flowchart LR", call_args[0][0])
            self.assertEqual(call_args[0][2], 1200)  # default width
        self.assertTrue(result.startswith("<!-- dims: 800x600 -->"))
        Path(src_path).unlink()

    def test_source_respects_width_hint(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
            f.write("graph TD\n  A --> B\n")
            src_path = f.name
        with patch.object(_mod, "_dispatch", return_value=_FRAGMENT_800x600) as mock_dispatch:
            self._run(["--source", src_path, "--width", "800"])
            self.assertEqual(mock_dispatch.call_args[0][2], 800)
        Path(src_path).unlink()

    def test_title_appears_in_output(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(_FRAGMENT_800x600)
            frag_path = f.name
        try:
            result = self._run(["--fragment", frag_path, "--title", "My Slide"])
            self.assertIn('<h1 class="slide-title">My Slide</h1>', result)
        finally:
            Path(frag_path).unlink()

    def test_annotation_appears_in_output(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(_FRAGMENT_800x600)
            frag_path = f.name
        try:
            result = self._run(["--fragment", frag_path, "--annotation", "Fig 1"])
            self.assertIn('<p class="slide-annotation">Fig 1</p>', result)
        finally:
            Path(frag_path).unlink()

    def test_output_writes_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(_FRAGMENT_800x600)
            frag_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as out_f:
            out_path = out_f.name
        try:
            self._run(["--fragment", frag_path, "--output", out_path])
            written = Path(out_path).read_text(encoding="utf-8")
            self.assertTrue(written.startswith("<!-- dims: 800x600 -->"))
        finally:
            Path(frag_path).unlink()
            Path(out_path).unlink()

    def test_output_to_stdout_when_no_output_flag(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(_FRAGMENT_800x600)
            frag_path = f.name
        try:
            result = self._run(["--fragment", frag_path])
            self.assertIn("<!DOCTYPE html>", result)
        finally:
            Path(frag_path).unlink()

    def test_error_both_fragment_and_source(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(_FRAGMENT_800x600)
            frag_path = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
            f.write("graph TD\n  A\n")
            src_path = f.name
        try:
            with self.assertRaises(SystemExit) as ctx:
                _mod.main(["--fragment", frag_path, "--source", src_path])
            self.assertNotEqual(ctx.exception.code, 0)
        finally:
            Path(frag_path).unlink()
            Path(src_path).unlink()

    def test_error_neither_fragment_nor_source(self):
        with self.assertRaises(SystemExit) as ctx:
            _mod.main([])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_style_json_bakes_css_vars(self):
        css_vars = {"--bg-primary": "#123456"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"css_variables": css_vars}, f)
            style_path = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(_FRAGMENT_800x600)
            frag_path = f.name
        try:
            result = self._run(["--fragment", frag_path, "--style", style_path])
            self.assertIn("--bg-primary: #123456", result)
        finally:
            Path(style_path).unlink()
            Path(frag_path).unlink()


if __name__ == "__main__":
    unittest.main()
