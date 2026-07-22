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


def dispatch_native_result(
    src: str,
    *,
    theme: "str | None" = None,
    width_hint: int = 0,
    height_hint: int = 0,
) -> "RenderResult":
    """Dispatch Mermaid source to a typed RenderResult.

    Returns a RenderResult with svg=None and errors populated on failure.
    Never silently falls back to a placeholder or legacy renderer.
    """
    from .native_svg import _dispatch_scene
    from .layout._parser import _detect_directive, _strip_frontmatter
    from .svg_serializer import scene_to_svg_str

    clean = _strip_frontmatter(src)
    directive, auto_direction = _detect_directive(clean)
    d = directive.lower()

    try:
        scene = _dispatch_scene(clean, directive, auto_direction.upper(), width_hint, height_hint)
    except (NativeRendererUnavailable, UnsupportedDiagramType) as e:
        return RenderResult(
            svg=None,
            diagram_type=d,
            backend="none",
            semantic_adapter="unsupported",
            syntax_coverage="failed",
            geometry="unvalidated",
            serialization="failed",
            warnings=(),
            errors=(str(e),),
        )
    except NativeRenderError as e:
        return RenderResult(
            svg=None,
            diagram_type=d,
            backend="native",
            semantic_adapter="failed",
            syntax_coverage="failed",
            geometry="unvalidated",
            serialization="failed",
            warnings=(),
            errors=(str(e),),
        )
    except ValueError as e:
        return RenderResult(
            svg=None,
            diagram_type=d,
            backend="native",
            semantic_adapter="failed",
            syntax_coverage="failed",
            geometry="unvalidated",
            serialization="failed",
            warnings=(),
            errors=(str(e),),
        )
    except Exception as e:
        wrapped = NativeRenderError(d, "dispatch", cause=e)
        return RenderResult(
            svg=None,
            diagram_type=d,
            backend="native",
            semantic_adapter="failed",
            syntax_coverage="failed",
            geometry="unvalidated",
            serialization="failed",
            warnings=(),
            errors=(str(wrapped),),
        )

    # Serialise
    try:
        svg_str = scene_to_svg_str(scene)
    except Exception as e:
        return RenderResult(
            svg=None,
            diagram_type=d,
            backend=getattr(scene, "renderer_backend", "native"),
            semantic_adapter="passed",
            syntax_coverage="passed",
            geometry="unvalidated",
            serialization="failed",
            warnings=(),
            errors=(f"Serialization failed: {e}",),
        )

    backend = getattr(scene, "renderer_backend", "native")

    # For experimental types, validation lanes are not yet wired — downgrade from "passed"
    cap = RENDERER_REGISTRY.get(d)
    if cap is not None and cap.native_status == "experimental":
        sem_adapter: str = "unsupported"
        syntax_cov: str = "partial"
    else:
        sem_adapter = "passed"
        syntax_cov = "passed"

    return RenderResult(
        svg=svg_str,
        diagram_type=d,
        backend=backend,
        semantic_adapter=sem_adapter,
        syntax_coverage=syntax_cov,
        geometry="unvalidated",   # Phase 4 will wire per-type validation
        serialization="passed",
        warnings=(),
        errors=(),
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

    result = _dispatch_validate(src)

    # Run native dispatch to capture the actual backend name.
    # Errors (NativeRenderError, UnsupportedDiagramType, …) are
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
            return dispatch_native(src, theme=theme, faithful=faithful, width_hint=width_hint)
        except NativeRendererUnavailable:
            if fallback == "legacy-dom":
                pass  # Fall through to legacy DOM path below
            else:
                raise
        except NativeRenderError as _e:
            if fallback == "legacy-dom" and _e.phase == "not-implemented":
                pass  # Fall through to legacy DOM path below
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
