"""mermaid_render — public API for the mermaid render pipeline.

to_html(src, *, theme=None, width_hint=0) -> str
    Pure-Python HTML backend; no playwright.

to_svg(src, *, theme=None, width_hint=0, fallback=None) -> str
    Pure-Python native SVG backend (default).
    Set MERMAID_RENDER_SVG_BACKEND=legacy-dom or pass fallback='legacy-dom'
    to use the Playwright DOM path for types without a native renderer.

to_png(src, *, theme=None, scale=1.0, width_hint=0) -> bytes
    Requires playwright.

validate(src) -> ValidationResult
    Geometry validation; partial — full per-type validation is Phase 4.

get_capability(diagram_type) -> RendererCapability
    Return the native-backend capability record for a diagram type.

RENDERER_REGISTRY : dict[str, RendererCapability]
    The full capability map.
"""
from __future__ import annotations

from .themes import Theme  # noqa: F401 — re-exported as part of public API
from .layout._geometry import ValidationResult  # noqa: F401 — re-exported
from .registry import (  # noqa: F401 — re-exported
    RendererCapability,
    RENDERER_REGISTRY,
    RenderResult,
    get_capability,
)
from .errors import (  # noqa: F401 — re-exported
    NativeRenderError,
    NativeRendererUnavailable,
    UnsupportedDiagramType,
    UnsupportedDiagramFeature,
)


def validate(src: str) -> ValidationResult:
    """Validate Mermaid source string and return a ValidationResult.

    Currently implements full geometry validation for sequenceDiagram;
    returns geometry='unvalidated' for all other types until Phase 4.
    renderer_backend is populated from the actual dispatch result so the
    gallery has_failures guard catches any stub-backend regression.
    """
    from dataclasses import replace as _dc_replace
    from .layout._strategies import _dispatch_validate
    from .native_svg import dispatch_native_result

    result = _dispatch_validate(src)

    # Run native dispatch to capture the actual backend name.
    # Errors (NativeRendererUnavailable, UnsupportedDiagramType, …) are
    # expected for LEGACY_ONLY / UNSUPPORTED types — use the error result's
    # backend field, which is "none" for those cases, never "-stub".
    try:
        nr = dispatch_native_result(src)
        backend = nr.backend
    except Exception:
        backend = ""

    return _dc_replace(result, renderer_backend=backend)


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


def to_svg(
    src: str,
    *,
    theme: Theme = None,
    width_hint: int = 0,
    faithful: bool = False,
    fallback: "str | None" = None,
) -> str:
    """Render a Mermaid source string to an SVG string.

    Uses the native pure-Python SVG backend by default (no Playwright, deterministic).

    Parameters
    ----------
    fallback : str | None
        When 'legacy-dom', routes LEGACY_ONLY types to the Playwright DOM path
        if the native backend raises NativeRendererUnavailable.
        Raises ValueError for unrecognised fallback values.
        Set env var MERMAID_RENDER_SVG_BACKEND=legacy-dom for a process-wide default.
    """
    if fallback is not None and fallback != "legacy-dom":
        raise ValueError(
            f"Unknown fallback value '{fallback}'. "
            "The only supported value is 'legacy-dom'."
        )

    from .native_svg import _use_native, dispatch_native

    if _use_native():
        try:
            return dispatch_native(src, theme=theme, width_hint=width_hint)
        except NativeRendererUnavailable:
            if fallback == "legacy-dom":
                # Fall through to legacy DOM path below
                pass
            else:
                raise

    # Legacy DOM path (Playwright)
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
