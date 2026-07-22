"""mermaid_render.errors — typed exceptions for the native SVG pipeline."""
from __future__ import annotations


class NativeRenderError(ValueError):
    """Unexpected exception during native SVG rendering.

    Wraps an unexpected builder or serializer failure so callers can catch it
    as a typed signal rather than a bare Exception.
    """

    def __init__(self, diagram_type: str, phase: str, *, cause: BaseException | None = None) -> None:
        self.diagram_type = diagram_type
        self.phase = phase
        msg = f"Native SVG render failed for '{diagram_type}' during {phase}"
        if cause is not None:
            msg += f": {cause}"
        super().__init__(msg)
        if cause is not None:
            self.__cause__ = cause


class NativeRendererUnavailable(ValueError):
    """Diagram type has no native SVG renderer; a legacy DOM backend may handle it.

    Raised when the caller did not opt into the legacy fallback via
    ``fallback="legacy-dom"`` and the diagram type is LEGACY_ONLY.
    """

    def __init__(self, diagram_type: str) -> None:
        self.diagram_type = diagram_type
        super().__init__(
            f"No native SVG renderer for diagram type '{diagram_type}'. "
            "Pass fallback='legacy-dom' to use the Playwright DOM path, "
            "or wait for a native adapter to be implemented."
        )


class UnsupportedDiagramType(ValueError):
    """Diagram type is explicitly unsupported by the native renderer.

    Unlike LEGACY_ONLY types, there is no DOM fallback path for these types.
    """

    def __init__(self, diagram_type: str) -> None:
        self.diagram_type = diagram_type
        super().__init__(
            f"Mermaid diagram type '{diagram_type}' is not supported by the "
            "pure-Python native renderer and has no legacy DOM fallback. "
            "Use mmdc for this diagram type."
        )


class UnsupportedDiagramFeature(ValueError):
    """A specific feature within a supported diagram type cannot be rendered natively."""

    def __init__(self, diagram_type: str, feature: str) -> None:
        self.diagram_type = diagram_type
        self.feature = feature
        super().__init__(
            f"Diagram feature '{feature}' in type '{diagram_type}' is not supported "
            "by the native SVG renderer."
        )
