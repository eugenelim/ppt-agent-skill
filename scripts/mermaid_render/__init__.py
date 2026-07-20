"""mermaid_render — public API for the mermaid render pipeline.

to_html(src, *, theme=None) -> str       pure-Python, no playwright
to_svg(src, *, theme=None) -> str        requires playwright
to_png(src, *, theme=None, scale=1.0) -> bytes  requires playwright
"""
from __future__ import annotations

from .themes import Theme  # noqa: F401 — re-exported as part of public API


def to_html(src: str, *, theme: Theme = None) -> str:
    """Render a Mermaid source string to a standalone HTML document.

    Playwright is NOT imported. theme is forwarded to themes.render_page.
    """
    from .layout._strategies import _dispatch
    from .themes import render_page

    fragment = _dispatch(src, None, 0)
    return render_page(fragment, theme)


def to_svg(src: str, *, theme: Theme = None) -> str:
    """Render a Mermaid source string to an SVG string (requires playwright)."""
    resolved = theme if theme is not None else "adaptive-light"
    html = to_html(src, theme=resolved)
    from .svg import _to_svg_from_html_string

    return _to_svg_from_html_string(html)


def to_png(src: str, *, theme: Theme = None, scale: float = 1.0) -> bytes:
    """Render a Mermaid source string to PNG bytes (requires playwright)."""
    resolved = theme if theme is not None else "adaptive-light"
    html = to_html(src, theme=resolved)
    from .png import _to_png_from_html_string

    return _to_png_from_html_string(html, scale=scale)
