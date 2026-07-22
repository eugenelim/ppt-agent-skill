"""TDD tests for _browser.py security helpers (no browser/Chromium required)."""
import os
import sys
import unittest.mock as mock
from pathlib import Path

import pytest

# Insert scripts/ onto path so bare `from _browser import` works (mirrors payload boundary)
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import _browser
from _browser import _url_allowed, _within_deck_root


class TestUrlAllowed:
    def test_file_url_allowed(self):
        assert _url_allowed("file:///path/to/file.html") is True

    def test_file_url_short(self):
        assert _url_allowed("file://localhost/foo.html") is True

    def test_data_url_allowed(self):
        assert _url_allowed("data:text/plain;base64,abc") is True

    def test_data_url_image(self):
        assert _url_allowed("data:image/png;base64,iVBORw0KGgo=") is True

    def test_https_blocked(self):
        assert _url_allowed("https://evil.com") is False

    def test_http_blocked(self):
        assert _url_allowed("http://localhost") is False

    def test_filex_blocked(self):
        # Catches a naive url.startswith("file") without the "://" suffix
        assert _url_allowed("filex://not-file") is False

    def test_empty_blocked(self):
        assert _url_allowed("") is False

    def test_ftp_blocked(self):
        assert _url_allowed("ftp://files.example.com/x") is False


class TestWithinDeckRoot:
    def test_child_within_root(self, tmp_path):
        assert _within_deck_root(tmp_path / "slides" / "s1.html", tmp_path) is True

    def test_deeply_nested_within_root(self, tmp_path):
        assert _within_deck_root(tmp_path / "a" / "b" / "c.png", tmp_path) is True

    def test_exact_root_is_within(self, tmp_path):
        assert _within_deck_root(tmp_path, tmp_path) is True

    def test_lexical_parent_traversal_blocked(self, tmp_path):
        # tmp_path / "../outside.html" collapses lexically but resolve() still puts it outside
        outside = tmp_path / ".." / "outside.html"
        assert _within_deck_root(outside, tmp_path) is False

    def test_sibling_dir_blocked(self, tmp_path):
        sibling = tmp_path.parent / "sibling" / "file.html"
        assert _within_deck_root(sibling, tmp_path) is False

    def test_symlink_escape_blocked(self, tmp_path):
        # Symlink inside the deck root pointing to a file outside — must be blocked.
        # This case requires Path.resolve() (not just abspath/normpath) to catch.
        outside_dir = tmp_path.parent / "outside_dir"
        outside_dir.mkdir(parents=True, exist_ok=True)
        outside_file = outside_dir / "secret.txt"
        outside_file.write_text("secret")

        deck_root = tmp_path / "deck"
        deck_root.mkdir()
        link = deck_root / "link_to_outside.txt"
        link.symlink_to(outside_file)

        assert _within_deck_root(link, deck_root) is False

    def test_symlink_within_root_allowed(self, tmp_path):
        # Symlink inside the deck root pointing to another file inside — must be allowed.
        deck_root = tmp_path / "deck"
        deck_root.mkdir()
        real_file = deck_root / "real.txt"
        real_file.write_text("ok")
        link = deck_root / "link.txt"
        link.symlink_to(real_file)

        assert _within_deck_root(link, deck_root) is True


class TestGetBrowserErrorWrapping:
    """All launch failures must surface as RuntimeError so callers can degrade cleanly."""

    def test_playwright_unavailable_raises_runtime_error(self):
        original = _browser._PLAYWRIGHT_AVAILABLE
        try:
            _browser._PLAYWRIGHT_AVAILABLE = False
            with pytest.raises(RuntimeError, match="playwright not installed"):
                with _browser.get_browser():
                    pass
        finally:
            _browser._PLAYWRIGHT_AVAILABLE = original

    def test_unexpected_launch_error_wrapped_as_runtime_error(self):
        """Non-'Executable doesn't exist' Playwright errors are converted to RuntimeError."""
        if not _browser._PLAYWRIGHT_AVAILABLE:
            pytest.skip("playwright not importable")
        fake_chromium = mock.MagicMock()
        fake_chromium.launch.side_effect = Exception("some unexpected crash")
        fake_pw = mock.MagicMock()
        fake_pw.chromium = fake_chromium

        with mock.patch("_browser.sync_playwright") as mock_sp:
            mock_sp.return_value.start.return_value = fake_pw
            with pytest.raises(RuntimeError, match="Chromium launch failed"):
                with _browser.get_browser():
                    pass

    def test_fail_fast_on_missing_executable(self):
        """'Executable doesn't exist' raises RuntimeError immediately — no install attempt."""
        if not _browser._PLAYWRIGHT_AVAILABLE:
            pytest.skip("playwright not importable")
        fake_chromium = mock.MagicMock()
        fake_chromium.launch.side_effect = Exception("Executable doesn't exist")
        fake_pw = mock.MagicMock()
        fake_pw.chromium = fake_chromium

        with mock.patch("_browser.sync_playwright") as mock_sp:
            mock_sp.return_value.start.return_value = fake_pw
            with pytest.raises(RuntimeError, match="playwright install chromium"):
                with _browser.get_browser():
                    pass


class TestBrowserSession:
    """BrowserSession owns one browser for multi-render use."""

    def test_browser_session_lifecycle(self):
        """BrowserSession calls launch once and close once."""
        if not _browser._PLAYWRIGHT_AVAILABLE:
            pytest.skip("playwright not importable")
        fake_browser = mock.MagicMock()
        fake_chromium = mock.MagicMock()
        fake_chromium.launch.return_value = fake_browser
        fake_pw = mock.MagicMock()
        fake_pw.chromium = fake_chromium

        with mock.patch("_browser.sync_playwright") as mock_sp:
            mock_sp.return_value.start.return_value = fake_pw
            with _browser.BrowserSession() as session:
                assert session._browser is fake_browser
            fake_chromium.launch.assert_called_once()
            fake_browser.close.assert_called_once()
            fake_pw.stop.assert_called_once()

    def test_browser_session_reuses_browser_across_renders(self, tmp_path):
        """Two render_to_png calls use new_context twice but chromium.launch once."""
        if not _browser._PLAYWRIGHT_AVAILABLE:
            pytest.skip("playwright not importable")
        html = tmp_path / "t.html"
        html.write_text("<html><body>hi</body></html>")

        fake_page = mock.MagicMock()
        fake_page.screenshot.return_value = b"\x89PNG\r\n"
        fake_context = mock.MagicMock()
        fake_context.new_page.return_value = fake_page
        fake_browser = mock.MagicMock()
        fake_browser.new_context.return_value = fake_context
        fake_chromium = mock.MagicMock()
        fake_chromium.launch.return_value = fake_browser
        fake_pw = mock.MagicMock()
        fake_pw.chromium = fake_chromium

        with mock.patch("_browser.sync_playwright") as mock_sp:
            mock_sp.return_value.start.return_value = fake_pw
            with _browser.BrowserSession() as session:
                session.render_to_png(html)
                session.render_to_png(html)

        fake_chromium.launch.assert_called_once()
        assert fake_browser.new_context.call_count == 2

    def test_browser_session_page_closes_after_render_failure(self, tmp_path):
        """page.close and context.close are called even when goto raises."""
        if not _browser._PLAYWRIGHT_AVAILABLE:
            pytest.skip("playwright not importable")
        html = tmp_path / "t.html"
        html.write_text("<html><body>hi</body></html>")

        fake_page = mock.MagicMock()
        fake_page.goto.side_effect = RuntimeError("network error")
        fake_context = mock.MagicMock()
        fake_context.new_page.return_value = fake_page
        fake_browser = mock.MagicMock()
        fake_browser.new_context.return_value = fake_context
        fake_chromium = mock.MagicMock()
        fake_chromium.launch.return_value = fake_browser
        fake_pw = mock.MagicMock()
        fake_pw.chromium = fake_chromium

        with mock.patch("_browser.sync_playwright") as mock_sp:
            mock_sp.return_value.start.return_value = fake_pw
            with _browser.BrowserSession() as session:
                with pytest.raises(RuntimeError):
                    session.render_to_png(html)

        fake_page.close.assert_called_once()
        fake_context.close.assert_called_once()


class TestDegradationGuard:
    """Each shipped script returns False/non-zero when playwright is unavailable."""

    def _make_html(self, tmp_path):
        html = tmp_path / "slides" / "slide-1.html"
        html.parent.mkdir(parents=True)
        html.write_text("<html><body>test</body></html>")
        return html

    def test_html2svg_returns_false_when_unavailable(self, tmp_path):
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import html2svg
        html_file = self._make_html(tmp_path)
        original = _browser._PLAYWRIGHT_AVAILABLE
        try:
            _browser._PLAYWRIGHT_AVAILABLE = False
            result = html2svg.convert(html_file.parent, tmp_path / "svg")
            assert result is False
        finally:
            _browser._PLAYWRIGHT_AVAILABLE = original

    def test_html2png_returns_false_when_unavailable(self, tmp_path):
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import html2png
        html_file = self._make_html(tmp_path)
        original = _browser._PLAYWRIGHT_AVAILABLE
        try:
            _browser._PLAYWRIGHT_AVAILABLE = False
            result = html2png.convert(html_file.parent, tmp_path / "png")
            assert result is False
        finally:
            _browser._PLAYWRIGHT_AVAILABLE = original

    def test_build_pdf_returns_nonzero_when_unavailable(self, tmp_path):
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import build_pdf
        html_file = self._make_html(tmp_path)
        docs = build_pdf.resolve_documents([str(html_file)], None, None)
        original = _browser._PLAYWRIGHT_AVAILABLE
        try:
            _browser._PLAYWRIGHT_AVAILABLE = False
            result = build_pdf.render(docs, width=1280, height=720, scale=1)
            assert result != 0
        finally:
            _browser._PLAYWRIGHT_AVAILABLE = original

    def test_gallery_returns_false_when_unavailable(self, tmp_path):
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import gallery
        original = _browser._PLAYWRIGHT_AVAILABLE
        try:
            _browser._PLAYWRIGHT_AVAILABLE = False
            # empty styles → empty file list; get_browser() raises RuntimeError before the loop
            result = gallery.take_screenshots([])
            assert result is False
        finally:
            _browser._PLAYWRIGHT_AVAILABLE = original
