"""Backward-compat shim: _browser → mermaid_render.browser.

Replaces the original implementation; the real code lives in
scripts/mermaid_render/browser.py. Using sys.modules aliasing so
mock.patch("_browser.sync_playwright") and mutation of _browser._PLAYWRIGHT_AVAILABLE
reach the real module globals.
"""
import sys as _sys
import pathlib as _p

_sys.path.insert(0, str(_p.Path(__file__).parent))
from mermaid_render import browser as _real  # noqa: E402
_sys.modules[__name__] = _real
