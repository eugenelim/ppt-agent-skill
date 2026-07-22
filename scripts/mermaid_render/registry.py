"""mermaid_render.registry — capability registry and render-result contract.

Two public surfaces:
  RendererCapability  — what the native backend can do for each diagram type
  RENDERER_REGISTRY   — the full capability map (diagram_type → RendererCapability)
  get_capability()    — look up by type key
  RenderResult        — typed result object from dispatch_native_result()
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional, Tuple


# ── Capability registry ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class RendererCapability:
    """What the native SVG backend can do for one diagram type.

    native_status values:
      "implemented"  — native scene builder exists and is validated
      "experimental" — native scene builder exists but may raise; no guaranteed output
      "legacy-only"  — no native builder; the legacy DOM (Playwright) path handles it
      "unsupported"  — neither native nor legacy; raises UnsupportedDiagramType
    """
    diagram_type: str
    native_status: Literal["implemented", "experimental", "legacy-only", "unsupported"]
    native_builder: Optional[Callable] = None
    validator: Optional[Callable] = None
    semantic_fixture_ids: Tuple[str, ...] = ()


def _make(
    diagram_type: str,
    status: Literal["implemented", "experimental", "legacy-only", "unsupported"],
    *,
    builder: Optional[Callable] = None,
    validator: Optional[Callable] = None,
    fixtures: Tuple[str, ...] = (),
) -> RendererCapability:
    return RendererCapability(
        diagram_type=diagram_type,
        native_status=status,
        native_builder=builder,
        validator=validator,
        semantic_fixture_ids=fixtures,
    )


RENDERER_REGISTRY: dict[str, RendererCapability] = {
    # ── Implemented (graph topology pipeline) ─────────────────────────────────
    "flowchart":         _make("flowchart",         "implemented"),
    "statediagram-v2":   _make("statediagram-v2",   "implemented"),
    "statediagram":      _make("statediagram",       "implemented"),

    # ── Experimental (have real builders; output may vary) ────────────────────
    "classdiagram":      _make("classdiagram",       "experimental"),
    "architecture-beta": _make("architecture-beta",  "experimental"),
    "c4context":         _make("c4context",           "experimental"),
    "c4container":       _make("c4container",         "experimental"),
    "c4component":       _make("c4component",         "experimental"),
    "timeline":          _make("timeline",            "experimental"),
    "mindmap":           _make("mindmap",             "experimental"),

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

    Raises KeyError for unrecognised types.
    """
    return RENDERER_REGISTRY[diagram_type]


# ── RenderResult — typed result from dispatch_native_result() ─────────────────

@dataclass(frozen=True)
class RenderResult:
    """Typed result from a single native SVG render attempt.

    Fields
    ------
    svg               : produced SVG string, or None on failure
    diagram_type      : detected diagram-type key
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
