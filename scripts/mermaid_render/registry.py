"""mermaid_render.registry — capability registry and render-result contract.

Public surfaces:
  DIRECTIVE_ALIASES     — raw directive → canonical key map
  canonicalize_directive() — normalize a raw directive string
  RendererCapability    — what the native backend can do for each diagram type
  RENDERER_REGISTRY     — the full capability map (canonical_type → RendererCapability)
  get_capability()      — look up by type key (raises UnsupportedDiagramType for unknowns)
  RenderResult          — typed result object from dispatch_native_result()
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional, Tuple


# ── Directive aliasing ────────────────────────────────────────────────────────
#
# Maps raw (lowercased) directive strings to the canonical key used throughout
# the registry and dispatch pipeline.  _detect_directive() already lowercases
# the first token, so camelCase variants are not needed here — but they are
# listed in comments for documentation.
#
# "graph" is the primary Mermaid alias for "flowchart".  All other registry
# keys are their own canonical forms.

DIRECTIVE_ALIASES: dict[str, str] = {
    # graph LR / graph TD → flowchart
    "graph": "flowchart",
}


def canonicalize_directive(raw: str) -> str:
    """Return the canonical registry key for a raw directive string.

    Lowercases *raw* and resolves any alias.  Does not validate that the
    result exists in the registry — callers that need the capability entry
    should call get_capability(), which raises UnsupportedDiagramType for
    unknown keys.
    """
    return DIRECTIVE_ALIASES.get(raw.lower(), raw.lower())


# ── Capability registry ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class RendererCapability:
    """What the native SVG backend can do for one diagram type.

    native_status values:
      "implemented"  — native scene builder exists and is validated
      "experimental" — native scene builder exists but may raise; no guaranteed output
      "legacy-only"  — no native builder; the legacy DOM (Playwright) path handles it
      "unsupported"  — neither native nor legacy; raises UnsupportedDiagramType

    native_builder : Callable[[RenderRequest], tuple[SvgScene, ValidationResult | None]]
        Returns (scene, validation) where validation is None for types without
        a geometry validator yet.  None for legacy-only and unsupported types.

    geometry_validator : Callable[[RenderRequest], ValidationResult] | None
        Standalone geometry validator (optional).  IMPLEMENTED types must have one.
        For types where the builder already returns a ValidationResult in its
        tuple, this may be omitted (the builder-provided result is used).
    """
    diagram_type: str
    native_status: Literal["implemented", "experimental", "legacy-only", "unsupported"]
    native_builder: Optional[Callable] = None
    geometry_validator: Optional[Callable] = None
    # Legacy field name preserved for tests that reference it directly.
    # Points to the same callable as geometry_validator for now.
    validator: Optional[Callable] = None
    semantic_fixture_ids: Tuple[str, ...] = ()


# ── Lazy-import native builders ───────────────────────────────────────────────
#
# Builders are defined as module-level callables that import lazily to avoid
# circular imports.  Each returns (SvgScene, ValidationResult | None).


def _build_flowchart(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _build_graph_pipeline
    return _build_graph_pipeline(request, "flowchart")


def _build_statediagram_v2(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _build_graph_pipeline
    return _build_graph_pipeline(request, "statediagram-v2")


def _build_statediagram(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _build_graph_pipeline
    return _build_graph_pipeline(request, "statediagram")


def _build_classdiagram(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _class_scene
    scene = _class_scene(
        request.clean_source,  # type: ignore[attr-defined]
        request.direction,     # type: ignore[attr-defined]
        request.width_hint,    # type: ignore[attr-defined]
    )
    return scene, None


def _build_architecture(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _architecture_scene
    scene = _architecture_scene(
        request.clean_source,  # type: ignore[attr-defined]
        request.direction,     # type: ignore[attr-defined]
        request.width_hint,    # type: ignore[attr-defined]
    )
    return scene, None


def _build_c4context(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _c4_scene
    scene = _c4_scene(
        request.clean_source,  # type: ignore[attr-defined]
        request.direction,     # type: ignore[attr-defined]
        request.width_hint,    # type: ignore[attr-defined]
        "c4context",
    )
    return scene, None


def _build_c4container(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _c4_scene
    scene = _c4_scene(
        request.clean_source,  # type: ignore[attr-defined]
        request.direction,     # type: ignore[attr-defined]
        request.width_hint,    # type: ignore[attr-defined]
        "c4container",
    )
    return scene, None


def _build_c4component(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _c4_scene
    scene = _c4_scene(
        request.clean_source,  # type: ignore[attr-defined]
        request.direction,     # type: ignore[attr-defined]
        request.width_hint,    # type: ignore[attr-defined]
        "c4component",
    )
    return scene, None


def _build_timeline(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _timeline_scene
    scene = _timeline_scene(
        request.clean_source,  # type: ignore[attr-defined]
        request.direction,     # type: ignore[attr-defined]
        request.width_hint,    # type: ignore[attr-defined]
    )
    return scene, None


def _build_mindmap(request: object) -> tuple:  # type: ignore[type-arg]
    from .native_svg import _mindmap_scene
    scene = _mindmap_scene(
        request.clean_source,  # type: ignore[attr-defined]
        request.direction,     # type: ignore[attr-defined]
        request.width_hint,    # type: ignore[attr-defined]
    )
    return scene, None


def _make(
    diagram_type: str,
    status: Literal["implemented", "experimental", "legacy-only", "unsupported"],
    *,
    builder: Optional[Callable] = None,
    geometry_validator: Optional[Callable] = None,
    fixtures: Tuple[str, ...] = (),
) -> RendererCapability:
    return RendererCapability(
        diagram_type=diagram_type,
        native_status=status,
        native_builder=builder,
        geometry_validator=geometry_validator,
        validator=geometry_validator,  # legacy alias
        semantic_fixture_ids=fixtures,
    )


RENDERER_REGISTRY: dict[str, RendererCapability] = {
    # ── Implemented (graph topology pipeline) ─────────────────────────────────
    "flowchart":         _make("flowchart",         "implemented",  builder=_build_flowchart),
    "statediagram-v2":   _make("statediagram-v2",   "implemented",  builder=_build_statediagram_v2),
    "statediagram":      _make("statediagram",       "implemented",  builder=_build_statediagram),

    # ── Experimental (have real builders; output may vary) ────────────────────
    "classdiagram":      _make("classdiagram",       "experimental", builder=_build_classdiagram),
    "architecture-beta": _make("architecture-beta",  "experimental", builder=_build_architecture),
    "c4context":         _make("c4context",           "experimental", builder=_build_c4context),
    "c4container":       _make("c4container",         "experimental", builder=_build_c4container),
    "c4component":       _make("c4component",         "experimental", builder=_build_c4component),
    "timeline":          _make("timeline",            "experimental", builder=_build_timeline),
    "mindmap":           _make("mindmap",             "experimental", builder=_build_mindmap),

    # ── Legacy-only (HTML/Playwright renderer handles these) ──────────────────
    "sequencediagram":   _make("sequencediagram",    "legacy-only"),
    "erdiagram":         _make("erdiagram",           "legacy-only"),
    "gantt":             _make("gantt",               "legacy-only"),
    "quadrantchart":     _make("quadrantchart",       "legacy-only"),
    "pie":               _make("pie",                 "legacy-only"),
    "xychart-beta":      _make("xychart-beta",        "legacy-only"),
    "block-beta":        _make("block-beta",          "legacy-only"),
    "packet-beta":       _make("packet-beta",         "legacy-only"),
    "kanban":            _make("kanban",              "legacy-only"),
    "journey":           _make("journey",             "legacy-only"),
    "requirementdiagram": _make("requirementdiagram", "legacy-only"),
    "gitgraph":          _make("gitgraph",            "legacy-only"),

    # ── Unsupported (no DOM fallback either; requires dedicated engine) ───────
    "sankey-beta":       _make("sankey-beta",         "unsupported"),
    "zenuml":            _make("zenuml",              "unsupported"),
}


def get_capability(diagram_type: str) -> RendererCapability:
    """Return the RendererCapability for *diagram_type*.

    Accepts both raw and canonical directive strings (e.g. "graph" → flowchart entry).
    Raises UnsupportedDiagramType for unrecognised types.
    """
    from .errors import UnsupportedDiagramType
    canonical = canonicalize_directive(diagram_type)
    if canonical not in RENDERER_REGISTRY:
        raise UnsupportedDiagramType(canonical)
    return RENDERER_REGISTRY[canonical]


# ── RenderResult — typed result from dispatch_native_result() ─────────────────

@dataclass(frozen=True)
class RenderResult:
    """Typed result from a single native SVG render attempt.

    Fields
    ------
    svg               : produced SVG string, or None on failure
    diagram_type      : detected diagram-type key (canonical)
    backend           : name of the backend used (e.g. "native", "legacy-dom", "none")
    semantic_adapter  : "passed" | "unsupported" | "failed"
    syntax_coverage   : "passed" | "partial" | "failed"
    geometry          : "passed" | "unvalidated" | "failed"
    serialization     : "passed" | "failed"
    warnings          : non-blocking diagnostic messages
    errors            : blocking errors (non-empty → is_success() == False)
    """
    svg: Optional[str]
    diagram_type: str
    backend: str
    semantic_adapter: Literal["passed", "unsupported", "failed"]
    syntax_coverage: Literal["passed", "partial", "failed"]
    geometry: Literal["passed", "unvalidated", "failed"]
    serialization: Literal["passed", "failed"]
    warnings: Tuple[str, ...]
    errors: Tuple[str, ...]

    def is_success(self, *, strict: bool = True) -> bool:
        """Return True when this result represents a trustworthy native SVG.

        Non-strict (strict=False): svg is not None and errors is empty.
        Strict (strict=True, default): additionally requires all validation
        lanes to be "passed" and the backend to not end in "-stub".
        """
        if self.errors:
            return False
        if self.svg is None:
            return False
        if not strict:
            return True
        return (
            self.semantic_adapter == "passed"
            and self.syntax_coverage == "passed"
            and self.geometry == "passed"
            and self.serialization == "passed"
            and not self.backend.endswith("-stub")
        )

    def to_exception(self) -> "Exception":
        """Return a typed exception for this failed result.

        Callers should raise the returned exception; they should not call this
        on a successful result.
        """
        from .errors import NativeRenderError
        if self.geometry == "failed":
            # geometry failure takes priority; errors carry the validator messages
            cause = RuntimeError("; ".join(self.errors)) if self.errors else None
            return NativeRenderError(self.diagram_type, "geometry", cause=cause)
        if self.errors:
            return NativeRenderError(
                self.diagram_type,
                "pipeline",
                cause=RuntimeError("; ".join(self.errors)),
            )
        if self.svg is None:
            return NativeRenderError(self.diagram_type, "build")
        return NativeRenderError(self.diagram_type, "unknown")
