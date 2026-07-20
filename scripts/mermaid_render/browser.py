"""Shared Playwright launcher for the PPT-agent render pipeline.

Provides get_browser(), _setup_page(), _url_allowed(), and _within_deck_root().
All scripts that spawn headless Chromium import from this module.

Security controls:
- _url_allowed: blocks every scheme except file:// and data: (LLM01/ASI05)
- _within_deck_root: symlink-safe path confinement (LLM05/CWE-22)
"""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

try:
    from playwright.sync_api import Browser, Page, sync_playwright
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


_LAUNCH_ARGS = ["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"]


def _install_route(page: "Page") -> None:
    """Install the URL allowlist route handler on a page (LLM01/ASI05)."""
    def _handle_route(route):
        url = route.request.url
        if _url_allowed(url):
            route.continue_()
        else:
            route.abort()
    page.route("**/*", _handle_route)


@contextmanager
def get_browser() -> "Generator[Browser, None, None]":
    """Yield a Playwright Browser; provision Chromium lazily on first run.

    All failures — bad install, broken Chromium, offline CI — raise RuntimeError
    so callers can catch a single type and degrade gracefully.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "playwright not installed — run: pip install playwright && playwright install chromium"
        )

    def _try_launch(pw):
        return pw.chromium.launch(args=_LAUNCH_ARGS)

    with sync_playwright() as pw:
        try:
            browser = _try_launch(pw)
        except Exception as e:
            if "Executable doesn't exist" not in str(e):
                raise RuntimeError(f"Chromium launch failed: {e}") from e
            try:
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    check=True,
                )
            except Exception as install_err:
                raise RuntimeError(
                    f"playwright install chromium failed: {install_err}"
                ) from install_err
            try:
                browser = _try_launch(pw)
            except Exception as launch_err:
                raise RuntimeError(
                    f"Chromium launch failed after install: {launch_err}"
                ) from launch_err
        try:
            yield browser
        finally:
            browser.close()


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
