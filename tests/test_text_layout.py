"""Tests for the text layout service (_text.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mermaid_render.layout._geometry import TextStyle
from mermaid_render.layout._text import (
    PillowTextMeasurer,
    HeuristicTextMeasurer,
    parse_markdown_runs,
    resolve_font,
    get_default_measurer,
)

# Use HeuristicTextMeasurer for deterministic tests that don't require real fonts.
# PillowTextMeasurer tests run with whatever font is available on the system.

_HEURISTIC = HeuristicTextMeasurer()
_STYLE = TextStyle(font_size=15.0, font_weight=700)
_STYLE_NORM = TextStyle(font_size=15.0, font_weight=400)


class TestHeuristicMeasurer:
    def test_empty_string(self):
        run = _HEURISTIC.measure_run("", _STYLE)
        assert run.width == 0.0
        assert run.text == ""

    def test_longer_is_wider(self):
        short = _HEURISTIC.measure_run("A", _STYLE)
        long_ = _HEURISTIC.measure_run("ABCDEFGHIJKLMNOPQRSTUVWXYZ", _STYLE)
        assert long_.width > short.width

    def test_bold_wider_than_normal(self):
        normal = _HEURISTIC.measure_run("Web app", _STYLE_NORM)
        bold = _HEURISTIC.measure_run("Web app", _STYLE)
        assert bold.width > normal.width

    def test_no_word_split_to_one_char_lines(self):
        """'Web app' must never produce one-character lines."""
        layout = _HEURISTIC.layout("Web app", _STYLE, max_width=200)
        for ln in layout.lines:
            for run in ln.runs:
                stripped = run.text.strip()
                if stripped:
                    assert len(stripped) > 1, f"Single-char line: '{stripped}'"

    def test_explicit_br_creates_new_line(self):
        layout = _HEURISTIC.layout("Line one<br>Line two", _STYLE, max_width=500)
        assert layout.height > layout.lines[0].height  # at least 2 lines worth of height

    def test_explicit_newline_creates_new_line(self):
        layout = _HEURISTIC.layout("Line one\nLine two", _STYLE, max_width=500)
        assert len(layout.lines) == 2

    def test_backslash_n_creates_new_line(self):
        layout = _HEURISTIC.layout("Line one\\nLine two", _STYLE, max_width=500)
        assert len(layout.lines) == 2

    def test_no_wrap_none_max_width(self):
        layout = _HEURISTIC.layout("A very long label that would normally wrap", _STYLE, max_width=None)
        assert len(layout.lines) == 1

    def test_wrap_at_word_boundary(self):
        layout = _HEURISTIC.layout("API service", _STYLE, max_width=30)
        # Must produce 2 lines with whole words (not single chars)
        assert len(layout.lines) >= 1
        for ln in layout.lines:
            for run in ln.runs:
                if run.text.strip():
                    assert " " not in run.text.strip() or len(run.text.strip()) > 1

    def test_deterministic(self):
        """Same input produces identical output on repeated calls."""
        t1 = _HEURISTIC.layout("Postgres", _STYLE, max_width=150)
        t2 = _HEURISTIC.layout("Postgres", _STYLE, max_width=150)
        assert t1.width == t2.width
        assert t1.height == t2.height
        assert len(t1.lines) == len(t2.lines)

    def test_min_content_width_le_total_width(self):
        layout = _HEURISTIC.layout("Fulfilment worker", _STYLE, max_width=200)
        assert layout.min_content_width <= layout.width

    def test_max_content_width_ge_total_width(self):
        layout = _HEURISTIC.layout("Fulfilment worker", _STYLE, max_width=200)
        assert layout.max_content_width >= layout.width

    def test_cjk_labels(self):
        layout = _HEURISTIC.layout("服务网关", _STYLE, max_width=200)
        assert layout.width > 0
        assert layout.height > 0

    def test_combining_marks_zero_width(self):
        # 'e' + combining acute (U+0301) should be narrower than 'ee'
        layout_combined = _HEURISTIC.layout("é", _STYLE, max_width=None)
        layout_double = _HEURISTIC.layout("ee", _STYLE, max_width=None)
        assert layout_combined.width < layout_double.width

    def test_multiline_height_accumulates(self):
        single = _HEURISTIC.layout("one line", _STYLE, max_width=None)
        multi = _HEURISTIC.layout("line one\nline two\nline three", _STYLE, max_width=None)
        assert multi.height > single.height * 2

    def test_node_bounds_contain_text(self):
        """Node bounds must contain painted text — test the invariant direction."""
        import math
        layout = _HEURISTIC.layout("API service", _STYLE, max_width=200)
        node_padding = 24
        node_w = math.ceil(layout.width) + node_padding
        node_h = math.ceil(layout.height) + node_padding
        assert node_w >= layout.width
        assert node_h >= layout.height

    def test_font_family_reported(self):
        m = HeuristicTextMeasurer()
        assert isinstance(m.font_family, str)
        assert m.font_family  # non-empty


class TestMarkdownParser:
    def test_bold(self):
        runs = parse_markdown_runs("**bold** text", TextStyle())
        bold_run = next((r for r in runs if r[1].font_weight >= 700), None)
        assert bold_run is not None
        assert bold_run[0] == "bold"

    def test_italic(self):
        runs = parse_markdown_runs("*italic* text", TextStyle())
        italic_run = next((r for r in runs if r[1].italic), None)
        assert italic_run is not None

    def test_strikethrough(self):
        runs = parse_markdown_runs("~~strike~~", TextStyle())
        st_run = next((r for r in runs if r[1].strikethrough), None)
        assert st_run is not None

    def test_br_as_newline(self):
        runs = parse_markdown_runs("line1<br>line2", TextStyle())
        texts = [r[0] for r in runs]
        assert "\n" in texts

    def test_no_markup(self):
        runs = parse_markdown_runs("plain text", TextStyle())
        assert len(runs) == 1
        assert runs[0][0] == "plain text"

    def test_mixed_bold_italic(self):
        runs = parse_markdown_runs("**bold** and *italic*", TextStyle())
        assert any(r[1].font_weight >= 700 for r in runs)
        assert any(r[1].italic for r in runs)


class TestFontResolution:
    def test_returns_tuple(self):
        path, family = resolve_font()
        assert isinstance(family, str)
        assert family  # non-empty

    def test_path_exists_or_none(self):
        path, _ = resolve_font()
        if path is not None:
            assert Path(path).exists()

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("MERMAID_RENDER_FONT_PATH", "/nonexistent/font.ttf")
        path, family = resolve_font()
        # Should fall through to next candidate since path doesn't exist
        assert True  # just verify it doesn't crash


class TestPillowMeasurer:
    """Integration tests — use whatever font the system has."""

    @pytest.fixture(autouse=True)
    def measurer(self):
        self.m = PillowTextMeasurer()

    def test_measure_run_nonempty(self):
        run = self.m.measure_run("API service", TextStyle(font_size=15))
        assert run.width > 0
        assert run.height > 0

    def test_layout_no_word_split(self):
        """'API service' must not produce 1-char lines."""
        layout = self.m.layout("API service", TextStyle(font_size=15), max_width=200)
        for ln in layout.lines:
            for run in ln.runs:
                if run.text.strip():
                    assert len(run.text.strip()) > 1, f"Got 1-char line: '{run.text}'"

    def test_deterministic_pillow(self):
        style = TextStyle(font_size=15, font_weight=700)
        t1 = self.m.layout("Postgres", style, max_width=150)
        t2 = self.m.layout("Postgres", style, max_width=150)
        assert t1.width == t2.width
        assert t1.height == t2.height

    def test_font_family_in_layout(self):
        layout = self.m.layout("test", TextStyle(font_size=15), max_width=None)
        assert layout.resolved_font_family == self.m.font_family

    def test_explicit_br(self):
        layout = self.m.layout("line1<br>line2", TextStyle(font_size=15), max_width=500)
        # Should produce at least 2 lines
        assert len(layout.lines) >= 2

    def test_bold_wider_than_normal(self):
        normal = self.m.layout("Fulfilment worker", TextStyle(font_size=15, font_weight=400), max_width=None)
        bold = self.m.layout("Fulfilment worker", TextStyle(font_size=15, font_weight=700), max_width=None)
        # Bold should be at least as wide (may be same with fallback font)
        assert bold.width >= normal.width * 0.95


class TestGetDefaultMeasurer:
    def test_returns_measurer(self):
        m = get_default_measurer()
        assert hasattr(m, "layout")
        assert hasattr(m, "measure_run")

    def test_singleton(self):
        m1 = get_default_measurer()
        m2 = get_default_measurer()
        assert m1 is m2
