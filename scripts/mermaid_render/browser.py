"""Shared Playwright launcher for the PPT-agent render pipeline.

Provides BrowserSession, get_browser(), _setup_page(), _url_allowed(), and
_within_deck_root(). All scripts that spawn headless Chromium import from here.

Security controls:
- _url_allowed: blocks every scheme except file:// and data: (LLM01/ASI05)
- _within_deck_root: symlink-safe path confinement (LLM05/CWE-22)

Browser lifecycle
-----------------
Use BrowserSession as an explicit context manager when rendering multiple inputs
through a single Chromium process:

    with BrowserSession() as session:
        png1 = session.render_to_png(html_path_1)
        png2 = session.render_to_png(html_path_2)

Each render_to_png call gets a fresh BrowserContext + Page, closed deterministically
in finally blocks. The browser and Playwright driver close at session exit.

Use get_browser() for legacy one-shot callers — it is a thin wrapper around
BrowserSession and carries identical error semantics.

Chromium provisioning
---------------------
Neither BrowserSession nor get_browser() installs Chromium automatically.
If the Chromium executable is absent, a RuntimeError is raised immediately
with instructions. Run: playwright install chromium
"""

from __future__ import annotations

import os as _os
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page, Playwright as SyncPlaywright

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False


def _url_allowed(url: str) -> bool:
    """Return True iff the URL is allowed during a local render (file:// or data:)."""
    return url.startswith("file://") or url.startswith("data:")


def _within_deck_root(path: "Path | str", deck_root: "Path | str") -> bool:
    """Return True iff path resolves to deck_root or a descendant (symlink-safe)."""
    resolved = Path(path).resolve()
    root_resolved = Path(deck_root).resolve()
    try:
        resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


_IN_CONTAINER = _os.environ.get("RENDER_IN_CONTAINER", "").strip() == "1"
_LAUNCH_ARGS = (
    ["--disable-gpu", "--font-render-hinting=none"]
    if _IN_CONTAINER
    else ["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"]
)

_FONTS_IMGS_READY = """async () => {
    await document.fonts.ready;
    const imgs = Array.from(document.querySelectorAll('img'));
    await Promise.all(imgs.map(img => {
        if (img.complete) return Promise.resolve();
        return new Promise(r => { img.onload = r; img.onerror = r; });
    }));
}"""


def _install_route(page: "Page") -> None:
    """Install the URL allowlist route handler on a page (LLM01/ASI05)."""
    def _handle_route(route):
        url = route.request.url
        if _url_allowed(url):
            route.continue_()
        else:
            route.abort()
    page.route("**/*", _handle_route)


def _launch_browser(pw):
    """Launch Chromium; raise RuntimeError on any failure (no lazy install)."""
    try:
        return pw.chromium.launch(args=_LAUNCH_ARGS)
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            raise RuntimeError(
                "Chromium not installed — run: playwright install chromium"
            ) from e
        raise RuntimeError(f"Chromium launch failed: {e}") from e


class BrowserSession:
    """Context manager owning one sync_playwright() instance and one Browser.

    Callers can render many inputs through a single Chromium process.
    Each render_to_png call uses a fresh BrowserContext + Page, closed
    deterministically in finally blocks.

    Usage::

        with BrowserSession() as session:
            png_bytes = session.render_to_png(html_path)

    Raises RuntimeError on entry if playwright is not installed or Chromium
    is absent. Never installs Chromium automatically.
    """

    def __init__(self) -> None:
        self._pw: "SyncPlaywright | None" = None
        self._browser: "Browser | None" = None

    def __enter__(self) -> "BrowserSession":
        if not _PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "playwright not installed — run: pip install playwright && playwright install chromium"
            )
        self._pw = sync_playwright().start()
        self._browser = _launch_browser(self._pw)
        return self

    def __exit__(self, *_) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass

    def render_to_png(
        self,
        html_path: Path,
        scale: float = 1.0,
        fullpage: bool = False,
    ) -> bytes:
        """Render one HTML file to PNG bytes using a fresh context and page.

        Matches the rendering contract of html2png.py:
          - viewport 1280×720, device_scale_factor=scale
          - waits for domcontentloaded, then fonts.ready and img loads
          - full-page screenshot when fullpage=True

        Page and context are closed in finally blocks after every render,
        including on exception.
        """
        context = self._browser.new_context(  # type: ignore[union-attr]
            viewport={"width": 1280, "height": 720},
            device_scale_factor=scale,
        )
        page = context.new_page()
        page.emulate_media(media="screen")
        _install_route(page)
        try:
            page.goto("file://" + str(html_path), wait_until="domcontentloaded", timeout=30000)
            page.evaluate(_FONTS_IMGS_READY)
            return page.screenshot(type="png", full_page=fullpage)
        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass


class SnapshotRasterSession:
    """Snapshot raster session: one Browser, fresh BrowserContext+Page per render.

    Uses page.set_content with domcontentloaded instead of page.goto with a blocking
    navigation wait, eliminating the guaranteed ≥500 ms wait per render while preserving
    pixel-stable output (page state doesn't accumulate across renders).

    The URL-allowlist route handler (LLM01/ASI05) is installed on each page.

    Use inside a BrowserSession context — shares its Browser instance:

        with BrowserSession() as bs:
            session = SnapshotRasterSession(bs._browser)
            try:
                png_bytes = session.render_html(html_string)
            finally:
                session.close()
    """

    def __init__(self, browser: "Browser") -> None:
        self._browser = browser

    def render_html(self, html: str) -> bytes:
        """Render an HTML string to PNG bytes.

        Creates a fresh BrowserContext+Page for each render to ensure pixel-stable
        output across the full fixture corpus.
        """
        context = self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1.0,
        )
        page = context.new_page()
        page.emulate_media(media="screen")
        _install_route(page)  # LLM01/ASI05
        try:
            page.set_content(html, wait_until="domcontentloaded")
            page.evaluate(_FONTS_IMGS_READY)
            return page.screenshot(type="png", full_page=True)
        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass

    def close(self) -> None:
        """No-op: context+page are closed after each render_html call."""


@contextmanager
def get_browser() -> "Generator[Browser, None, None]":
    """Yield a Playwright Browser. Thin wrapper around BrowserSession.

    All failures — missing Chromium, broken installation, offline CI — raise
    RuntimeError so callers can catch a single type and degrade gracefully.
    Chromium is NOT installed automatically; run: playwright install chromium
    """
    with BrowserSession() as session:
        yield session._browser  # type: ignore[misc]


def _setup_page(
    page: "Page",
    width: int = 1280,
    height: int = 720,
) -> None:
    """Configure a Playwright page: viewport + URL allowlist route handler.

    Use new_page() instead when a non-1x device_scale_factor is needed —
    Playwright's device scale factor must be set at context creation, not
    on an existing page.
    """
    page.set_viewport_size({"width": width, "height": height})
    page.emulate_media(media="screen")
    _install_route(page)


def new_page(
    browser: "Browser",
    width: int = 1280,
    height: int = 720,
    scale: float = 1.0,
) -> "Page":
    """Create a browser context with the given device_scale_factor and return a
    configured page (viewport + URL allowlist).

    Context is closed automatically when the page is closed — callers only need
    page.close().
    """
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=scale,
    )
    page = context.new_page()
    page.emulate_media(media="screen")
    _install_route(page)
    def _close_context(_):
        try:
            context.close()
        except Exception:
            pass
    page.on("close", _close_context)
    return page
