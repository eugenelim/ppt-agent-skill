"""mermaid_render — public API for the mermaid render pipeline.

to_html(src, *, theme=None, width_hint=0) -> str
    Pure-Python HTML backend; no playwright.

to_svg(src, *, theme=None, width_hint=0, fallback=None) -> str
    Pure-Python native SVG backend (default).
    Consumes render_svg_result() internally.
    Set MERMAID_RENDER_SVG_BACKEND=legacy-dom or pass fallback='legacy-dom'
    to use the Playwright DOM path for types without a native renderer.

render_svg_result(src, *, ...) -> RenderResult
    Full pipeline: parse → capability lookup → builder → validator → serialize.
    Returns RenderResult; raises typed errors on hard failures.

dispatch_native_result(src, *, ...) -> RenderResult
    Thin wrapper around render_svg_result(); never raises — returns error RenderResult.

to_png(src, *, theme=None, scale=1.0, width_hint=0) -> bytes
    Requires playwright.

validate(src) -> ValidationResult
    Geometry validation with per-type structural and semantic checks.

get_capability(diagram_type) -> RendererCapability
    Return the native-backend capability record for a diagram type.
    Accepts raw or canonical directives (e.g. "graph" → flowchart entry).
    Raises UnsupportedDiagramType for unknown types.

canonicalize_directive(raw) -> str
    Normalize a raw directive string to its canonical registry key.

RENDERER_REGISTRY : dict[str, RendererCapability]
    The full capability map (canonical keys).

DIRECTIVE_ALIASES : dict[str, str]
    Raw → canonical directive alias map.
"""
from __future__ import annotations

from .themes import Theme  # noqa: F401 — re-exported as part of public API
from .layout._geometry import ValidationResult  # noqa: F401 — re-exported
from .registry import (  # noqa: F401 — re-exported
    RendererCapability,
    RENDERER_REGISTRY,
    RenderResult,
    get_capability,
    canonicalize_directive,
    DIRECTIVE_ALIASES,
)
from .errors import (  # noqa: F401 — re-exported
    NativeRenderError,
    NativeRendererUnavailable,
    UnsupportedDiagramType,
    UnsupportedDiagramFeature,
)
def __getattr__(name: str):
    # Lazy-load native_svg symbols so importing mermaid_render never eagerly
    # pulls in lxml (svg_serializer dep) — required for test_to_html_runs_without_site_packages.
    if name == "render_svg_result":
        from .native_svg import render_svg_result as _rsr
        globals()["render_svg_result"] = _rsr
        return _rsr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    Delegates to render_svg_result() for the actual pipeline.
    """
    from .native_svg import render_svg_result
    from .registry import canonicalize_directive

    # Detect canonical directive upfront to label error RenderResults consistently.
    # render_svg_result() runs its own parse_render_request() internally; both
    # paths must use canonicalize_directive() so they agree on the type string.
    from .layout._parser import _detect_directive, _strip_frontmatter
    clean = _strip_frontmatter(src)
    raw_directive, _ = _detect_directive(clean)
    d = canonicalize_directive(raw_directive)

    try:
        return render_svg_result(
            src,
            theme=theme,
            width_hint=width_hint,
            height_hint=height_hint,
        )
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


def validate(src: str) -> ValidationResult:
    """Validate Mermaid source string and return a ValidationResult.

    Graph directives and sequenceDiagram compile to a scene and run geometry
    checks. Other directives return geometry='unvalidated'.
    renderer_backend is populated from the actual dispatch result so the
    gallery has_failures guard catches any stub-backend regression.
    """
    from dataclasses import replace as _dc_replace
    from .native_svg import parse_render_request
    from .layout._strategies import _dispatch_validate

    request = parse_render_request(src)
    result = _dispatch_validate(request.clean_source)

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
    Consumes render_svg_result() internally so the result contract is enforced.

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

    from .native_svg import _use_native, render_svg_result

    if _use_native():
        try:
            result = render_svg_result(
                src,
                theme=theme,
                faithful=faithful,
                width_hint=width_hint,
            )
            if result.geometry == "failed":
                raise result.to_exception()
            return result.svg  # type: ignore[union-attr]
        except NativeRendererUnavailable as _unavail:
            if fallback == "legacy-dom":
                pass  # Fall through to legacy DOM path below
            else:
                # Preserve legacy contract: callers expect NativeRenderError(phase="not-implemented")
                raise NativeRenderError(
                    _unavail.diagram_type, "not-implemented", cause=_unavail
                ) from _unavail
        except NativeRenderError as _e:
            if fallback == "legacy-dom" and _e.phase in ("not-implemented", "build"):
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
