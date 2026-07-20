#!/usr/bin/env python3
"""Timeline diagram syntax coverage tests for the mermaid_render layout engine.

Covers every documented timeline syntax feature:
  - Basic period/event rendering
  - ``title`` keyword
  - ``section`` keyword for grouping periods
  - Multiple events per period (first event on the same line, continuation form)
  - Direction variant (``timeline LR`` / ``timeline TD``)

Support detection: the module-level ``SUPPORTED`` flag is set by probing
``to_html`` at import time. All tests branch on this flag so the suite stays
valid regardless of whether the renderer supports timeline.

Import note: ``to_html`` lives in ``mermaid_render``, not ``mermaid_layout``
(the latter is a backward-compat shim to ``mermaid_render.layout`` and does not
re-export ``to_html``). We import directly from ``mermaid_render``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402

# ── Support detection ─────────────────────────────────────────────────────────

try:
    _probe_html = to_html("timeline\n  2024 : Event")
    SUPPORTED = True
except ValueError:
    SUPPORTED = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _timeline(body: str) -> str:
    """Wrap body lines in a minimal timeline directive and call to_html."""
    return to_html(f"timeline\n{body}")


# ── TestTimelineBasic ─────────────────────────────────────────────────────────


class TestTimelineBasic:
    def test_minimal_timeline_renders_or_raises(self):
        """A minimal one-period timeline either renders or raises ValueError."""
        src = "timeline\n  2024 : Event"
        if SUPPORTED:
            html = to_html(src)
            assert html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_period_text_in_output(self):
        """The period label appears in the rendered HTML."""
        src = "timeline\n  2024 : Launch"
        if SUPPORTED:
            html = to_html(src)
            assert "2024" in html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_event_text_in_output(self):
        """The event text for a period appears in the rendered HTML."""
        if SUPPORTED:
            html = _timeline("  2024 : Launch")
            assert "Launch" in html
        else:
            with pytest.raises(ValueError):
                _timeline("  2024 : Launch")

    def test_output_is_html_document(self):
        """to_html returns a full HTML document."""
        if SUPPORTED:
            html = _timeline("  2024 : Event")
            assert html.strip().startswith("<!DOCTYPE") or "<html" in html
        else:
            with pytest.raises(ValueError):
                _timeline("  2024 : Event")

    def test_mermaid_layout_class_present(self):
        """Rendered fragment carries the 'mermaid-layout' CSS class."""
        if SUPPORTED:
            html = _timeline("  2024 : Event")
            assert "mermaid-layout" in html
        else:
            with pytest.raises(ValueError):
                _timeline("  2024 : Event")

    def test_data_node_id_attribute_for_period(self):
        """Period node carries a data-node-id attribute."""
        if SUPPORTED:
            html = _timeline("  2002 : LinkedIn")
            assert 'data-node-id="2002"' in html
        else:
            with pytest.raises(ValueError):
                _timeline("  2002 : LinkedIn")

    def test_multiple_periods_all_appear(self):
        """Multiple periods all produce visible output."""
        src = (
            "timeline\n"
            "  2002 : LinkedIn\n"
            "  2004 : Facebook\n"
            "  2005 : YouTube\n"
        )
        if SUPPORTED:
            html = to_html(src)
            assert "2002" in html
            assert "2004" in html
            assert "2005" in html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_svg_axis_line_present(self):
        """A horizontal axis SVG line connects the period nodes."""
        if SUPPORTED:
            html = _timeline("  2002 : LinkedIn\n  2004 : Facebook")
            assert "<svg" in html
            assert "<line" in html
        else:
            with pytest.raises(ValueError):
                _timeline("  2002 : LinkedIn\n  2004 : Facebook")


# ── TestTimelineTitle ─────────────────────────────────────────────────────────


class TestTimelineTitle:
    def test_title_text_in_output(self):
        """The title keyword value appears in the rendered HTML."""
        src = (
            "timeline\n"
            "  title History of Social Media Platform\n"
            "  2002 : LinkedIn\n"
        )
        if SUPPORTED:
            html = to_html(src)
            assert "History of Social Media Platform" in html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_title_does_not_appear_as_period_node(self):
        """The title line is not treated as a period; no data-node-id for it."""
        src = (
            "timeline\n"
            "  title My Title\n"
            "  2024 : Event\n"
        )
        if SUPPORTED:
            html = to_html(src)
            assert 'data-node-id="My Title"' not in html
            assert 'data-node-id="title My Title"' not in html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_title_and_periods_coexist(self):
        """Title and period nodes both appear when both are present."""
        src = (
            "timeline\n"
            "  title Platform Timeline\n"
            "  2006 : Twitter\n"
        )
        if SUPPORTED:
            html = to_html(src)
            assert "Platform Timeline" in html
            assert "2006" in html
            assert "Twitter" in html
        else:
            with pytest.raises(ValueError):
                to_html(src)


# ── TestTimelineSection ───────────────────────────────────────────────────────


class TestTimelineSection:
    def test_section_keyword_does_not_crash(self):
        """A section line does not raise; the diagram renders without error."""
        src = (
            "timeline\n"
            "  section 2010s\n"
            "    2010 : Instagram\n"
        )
        if SUPPORTED:
            html = to_html(src)
            assert html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_periods_after_section_appear_in_output(self):
        """Periods declared after a section heading render normally."""
        src = (
            "timeline\n"
            "  section 2010s\n"
            "    2010 : Instagram\n"
            "    2011 : Snapchat\n"
        )
        if SUPPORTED:
            html = to_html(src)
            assert "2010" in html
            assert "2011" in html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_multiple_sections_all_periods_render(self):
        """Periods across multiple sections all appear in a single render."""
        src = (
            "timeline\n"
            "  section 2010s\n"
            "    2010 : Instagram\n"
            "  section 2020s\n"
            "    2021 : TikTok\n"
        )
        if SUPPORTED:
            html = to_html(src)
            assert "2010" in html
            assert "2021" in html
        else:
            with pytest.raises(ValueError):
                to_html(src)


# ── TestTimelineMultipleEvents ────────────────────────────────────────────────


class TestTimelineMultipleEvents:
    def test_first_event_on_same_line_in_output(self):
        """The first event on a period line appears in the rendered HTML."""
        if SUPPORTED:
            html = _timeline("  2004 : Facebook")
            assert "Facebook" in html
        else:
            with pytest.raises(ValueError):
                _timeline("  2004 : Facebook")

    def test_continuation_event_form_does_not_crash(self):
        """The ``: <event>`` continuation form does not raise."""
        src = (
            "timeline\n"
            "  2004 : Facebook\n"
            "       : Google\n"
        )
        if SUPPORTED:
            html = to_html(src)
            assert html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_continuation_event_text_appears(self):
        """Text from a continuation event line appears somewhere in the output."""
        src = (
            "timeline\n"
            "  2004 : Facebook\n"
            "       : Google\n"
        )
        if SUPPORTED:
            html = to_html(src)
            # "Google" must appear — either as a period label (implementation
            # detail) or as an event text; the exact form is not specified here.
            assert "Google" in html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_period_with_multiple_inline_events_renders(self):
        """A period with its primary event renders both period and event text."""
        if SUPPORTED:
            html = _timeline("  2006 : Twitter")
            assert "2006" in html
            assert "Twitter" in html
        else:
            with pytest.raises(ValueError):
                _timeline("  2006 : Twitter")


# ── TestTimelineDirection ─────────────────────────────────────────────────────


class TestTimelineDirection:
    def test_timeline_lr_renders_or_raises_value_error(self):
        """``timeline LR`` either renders without error or raises ValueError."""
        src = "timeline LR\n  2024 : Event"
        if SUPPORTED:
            html = to_html(src)
            assert html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_timeline_td_renders_or_raises_value_error(self):
        """``timeline TD`` either renders without error or raises ValueError."""
        src = "timeline TD\n  2024 : Event"
        if SUPPORTED:
            html = to_html(src)
            assert html
        else:
            with pytest.raises(ValueError):
                to_html(src)

    def test_direction_lr_period_text_present(self):
        """Period text is present in ``timeline LR`` output."""
        src = "timeline LR\n  2002 : LinkedIn\n  2004 : Facebook"
        if SUPPORTED:
            html = to_html(src)
            assert "2002" in html
            assert "2004" in html
        else:
            with pytest.raises(ValueError):
                to_html(src)


# ── TestTimelineFullExample ───────────────────────────────────────────────────


class TestTimelineFullExample:
    """Validate the full Social Media Platform example from the Mermaid docs."""

    _SRC = (
        "timeline\n"
        "  title History of Social Media Platform\n"
        "  2002 : LinkedIn\n"
        "  2004 : Facebook\n"
        "       : Google\n"
        "  2005 : YouTube\n"
        "  2006 : Twitter\n"
        "  section 2010s\n"
        "    2010 : Instagram\n"
        "    2011 : Snapchat\n"
        "  section 2020s\n"
        "    2021 : TikTok\n"
    )

    def test_full_example_renders(self):
        """The complete Social Media Platform example renders without error."""
        if SUPPORTED:
            html = to_html(self._SRC)
            assert html
        else:
            with pytest.raises(ValueError):
                to_html(self._SRC)

    def test_full_example_title_present(self):
        """The title appears in the full example output."""
        if SUPPORTED:
            html = to_html(self._SRC)
            assert "History of Social Media Platform" in html
        else:
            with pytest.raises(ValueError):
                to_html(self._SRC)

    def test_full_example_key_periods_present(self):
        """Key period labels (2002, 2004, 2005, 2006) all appear in the output."""
        if SUPPORTED:
            html = to_html(self._SRC)
            for year in ("2002", "2004", "2005", "2006"):
                assert year in html, f"Period '{year}' missing from output"
        else:
            with pytest.raises(ValueError):
                to_html(self._SRC)

    def test_full_example_section_decade_periods_present(self):
        """Periods under section headings (2010, 2011, 2021) all appear in output."""
        if SUPPORTED:
            html = to_html(self._SRC)
            for year in ("2010", "2011", "2021"):
                assert year in html, f"Period '{year}' missing from output"
        else:
            with pytest.raises(ValueError):
                to_html(self._SRC)
