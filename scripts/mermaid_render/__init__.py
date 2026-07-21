"""mermaid_render — public API for the mermaid render pipeline.

to_html(src, *, theme=None, width_hint=0) -> str          pure-Python, no playwright
to_svg(src, *, theme=None, width_hint=0) -> str            requires playwright
to_png(src, *, theme=None, scale=1.0, width_hint=0) -> bytes  requires playwright
validate(src) -> ValidationResult                          geometry validation stub
"""
from __future__ import annotations

from .themes import Theme  # noqa: F401 — re-exported as part of public API
from .layout._geometry import ValidationResult  # noqa: F401 — re-exported


def validate(src: str) -> ValidationResult:
    """Validate Mermaid source string and return a ValidationResult.

    Stub — returns empty (ok) result for all inputs until full geometry
    constraint checking is implemented.
    """
    from .layout._strategies import _dispatch_validate
    return _dispatch_validate(src)


def to_html(src: str, *, theme: Theme = None, width_hint: int = 0, faithful: bool = False) -> str:
    """Render a Mermaid source string to a standalone HTML document.

    Playwright is NOT imported. theme is forwarded to themes.render_page.
    width_hint: if nonzero, scales the output to fit within this pixel width.
    faithful: when True, preserves declared direction, suppresses icon/legend inference,
        and does not auto-flip direction for aspect ratio.
    """
    from .layout._strategies import _dispatch, RenderOptions
    from .themes import render_page

    opts = RenderOptions(faithful_mermaid=faithful) if faithful else None
    fragment = _dispatch(src, None, width_hint, opts=opts)
    return render_page(fragment, theme)


def to_svg(src: str, *, theme: Theme = None, width_hint: int = 0, faithful: bool = False) -> str:
    """Render a Mermaid source string to an SVG string (requires playwright)."""
    resolved = theme if theme is not None else "adaptive-light"
    html = to_html(src, theme=resolved, width_hint=width_hint, faithful=faithful)
    from .svg import _to_svg_from_html_string

    return _to_svg_from_html_string(html)


def to_png(src: str, *, theme: Theme = None, scale: float = 1.0, width_hint: int = 0, faithful: bool = False) -> bytes:
    """Render a Mermaid source string to PNG bytes (requires playwright)."""
    resolved = theme if theme is not None else "adaptive-light"
    html = to_html(src, theme=resolved, width_hint=width_hint, faithful=faithful)
    from .png import _to_png_from_html_string

    return _to_png_from_html_string(html, scale=scale)
