"""mermaid_render.scene — Immutable paint-scene IR for native SVG output.

The pipeline is:
    layout IR (FinalizedLayout / per-type semantic model)
    -> layout_to_scene(...)  [in paint.py]
    -> SvgScene             [immutable, deterministic]
    -> scene_to_svg(...)    [in svg_serializer.py]
    -> bytes

No object in this module may hold mutable state after construction.
No object in this module may perform layout or geometry computation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple


# ── Paint styles ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrokeStyle:
    color: str = "#000000"
    width: float = 1.0
    dasharray: str = ""          # SVG stroke-dasharray value, "" = solid
    linecap: str = "butt"        # "butt" | "round" | "square"
    linejoin: str = "miter"      # "miter" | "round" | "bevel"
    opacity: float = 1.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.width) or self.width < 0:
            raise ValueError(f"StrokeStyle.width must be finite non-negative; got {self.width}")
        if not (0.0 <= self.opacity <= 1.0):
            raise ValueError(f"StrokeStyle.opacity must be 0–1; got {self.opacity}")


@dataclass(frozen=True)
class FillStyle:
    color: str = "none"          # CSS color or "none"
    opacity: float = 1.0
    fill_rule: str = "nonzero"   # "nonzero" | "evenodd"

    def __post_init__(self) -> None:
        if not (0.0 <= self.opacity <= 1.0):
            raise ValueError(f"FillStyle.opacity must be 0–1; got {self.opacity}")


@dataclass(frozen=True)
class PaintStyle:
    fill: FillStyle = field(default_factory=FillStyle)
    stroke: Optional[StrokeStyle] = None
    filter: str = ""             # SVG filter reference, "" = none
    opacity: float = 1.0         # element-level opacity

    def __post_init__(self) -> None:
        if not (0.0 <= self.opacity <= 1.0):
            raise ValueError(f"PaintStyle.opacity must be 0–1; got {self.opacity}")


# ── Definitions (referenced by elements) ─────────────────────────────────────

@dataclass(frozen=True)
class MarkerDefinition:
    """An SVG <marker> arrowhead definition."""
    marker_id: str
    marker_type: str             # "arrow-end" | "arrow-start" | "arrow-open" | "arrow-filled"
                                 # | "arrow-bidirectional" | "state-transition" | "timeline-end"
    color: str = "#000000"
    size: float = 6.0
    refX: float = 6.0
    refY: float = 3.0


@dataclass(frozen=True)
class LinearGradientDefinition:
    gradient_id: str
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 1.0
    y2: float = 0.0
    stops: Tuple[Tuple[float, str, float], ...] = ()   # (offset, color, opacity)
    gradient_units: str = "objectBoundingBox"


@dataclass(frozen=True)
class RadialGradientDefinition:
    gradient_id: str
    cx: float = 0.5
    cy: float = 0.5
    r: float = 0.5
    stops: Tuple[Tuple[float, str, float], ...] = ()
    gradient_units: str = "objectBoundingBox"


@dataclass(frozen=True)
class ClipPathDefinition:
    clip_id: str
    clip_x: float
    clip_y: float
    clip_w: float
    clip_h: float
    rx: float = 0.0
    ry: float = 0.0


# ── Accessibility ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AccessibilityMetadata:
    title: str = ""
    description: str = ""
    role: str = "graphics-document document"
    aria_label: str = ""


# ── Scene element base (shared fields) ───────────────────────────────────────

@dataclass(frozen=True)
class _SceneElement:
    element_id: str = ""
    css_classes: Tuple[str, ...] = ()
    semantic_role: str = ""
    data_attrs: Tuple[Tuple[str, str], ...] = ()   # (name, value) pairs
    transform: str = ""                             # SVG transform string
    clip_ref: str = ""                              # clipPath id reference
    paint: PaintStyle = field(default_factory=PaintStyle)


# ── Shape primitives ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SceneRect(_SceneElement):
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    def __post_init__(self) -> None:
        _check_finite(self.x, "SceneRect.x")
        _check_finite(self.y, "SceneRect.y")
        _check_finite(self.w, "SceneRect.w")
        _check_finite(self.h, "SceneRect.h")


@dataclass(frozen=True)
class SceneRoundedRect(_SceneElement):
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    rx: float = 0.0
    ry: float = 0.0

    def __post_init__(self) -> None:
        _check_finite(self.x, "SceneRoundedRect.x")
        _check_finite(self.y, "SceneRoundedRect.y")
        _check_finite(self.w, "SceneRoundedRect.w")
        _check_finite(self.h, "SceneRoundedRect.h")


@dataclass(frozen=True)
class SceneCircle(_SceneElement):
    cx: float = 0.0
    cy: float = 0.0
    r: float = 0.0

    def __post_init__(self) -> None:
        _check_finite(self.cx, "SceneCircle.cx")
        _check_finite(self.cy, "SceneCircle.cy")
        _check_finite(self.r, "SceneCircle.r")


@dataclass(frozen=True)
class SceneEllipse(_SceneElement):
    cx: float = 0.0
    cy: float = 0.0
    rx: float = 0.0
    ry: float = 0.0

    def __post_init__(self) -> None:
        _check_finite(self.cx, "SceneEllipse.cx")
        _check_finite(self.cy, "SceneEllipse.cy")
        _check_finite(self.rx, "SceneEllipse.rx")
        _check_finite(self.ry, "SceneEllipse.ry")


@dataclass(frozen=True)
class SceneLine(_SceneElement):
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    marker_start: str = ""   # marker id reference
    marker_end: str = ""

    def __post_init__(self) -> None:
        _check_finite(self.x1, "SceneLine.x1")
        _check_finite(self.y1, "SceneLine.y1")
        _check_finite(self.x2, "SceneLine.x2")
        _check_finite(self.y2, "SceneLine.y2")


@dataclass(frozen=True)
class ScenePolyline(_SceneElement):
    points: Tuple[Tuple[float, float], ...] = ()
    marker_start: str = ""
    marker_end: str = ""

    def __post_init__(self) -> None:
        for i, (x, y) in enumerate(self.points):
            _check_finite(x, f"ScenePolyline.points[{i}].x")
            _check_finite(y, f"ScenePolyline.points[{i}].y")


@dataclass(frozen=True)
class ScenePolygon(_SceneElement):
    points: Tuple[Tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        for i, (x, y) in enumerate(self.points):
            _check_finite(x, f"ScenePolygon.points[{i}].x")
            _check_finite(y, f"ScenePolygon.points[{i}].y")


@dataclass(frozen=True)
class ScenePath(_SceneElement):
    """Typed SVG path. `commands` is a sequence of typed command tuples.

    Each command is a tuple whose first element is the command letter:
        ("M", x, y)         — moveto absolute
        ("L", x, y)         — lineto absolute
        ("C", x1,y1,x2,y2,x,y) — cubic bezier absolute
        ("Q", x1,y1,x,y)    — quadratic bezier absolute
        ("A", rx,ry,xr,lf,sf,x,y) — arc absolute
        ("Z",)              — closepath
    No raw SVG path strings. No user-provided data.
    """
    commands: Tuple[tuple, ...] = ()
    marker_start: str = ""
    marker_end: str = ""

    def __post_init__(self) -> None:
        for i, cmd in enumerate(self.commands):
            letter = cmd[0]
            nums = cmd[1:]
            if letter not in ("M", "L", "C", "Q", "A", "Z"):
                raise ValueError(f"ScenePath command[{i}]: unsupported letter {letter!r}")
            for j, v in enumerate(nums):
                if not math.isfinite(v):
                    raise ValueError(f"ScenePath command[{i}] arg[{j}] is non-finite: {v}")


# ── Text ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SceneTextLine:
    """One rendered text line with pre-computed position."""
    text: str
    x: float
    y: float              # baseline y coordinate
    font_size: float = 15.0
    font_weight: int = 400
    italic: bool = False
    letter_spacing: float = 0.0
    fill_color: str = "#000000"
    strikethrough: bool = False

    def __post_init__(self) -> None:
        _check_finite(self.x, "SceneTextLine.x")
        _check_finite(self.y, "SceneTextLine.y")


@dataclass(frozen=True)
class SceneText(_SceneElement):
    """A text block composed of pre-measured lines."""
    lines: Tuple[SceneTextLine, ...] = ()
    text_anchor: str = "middle"    # "start" | "middle" | "end"
    dominant_baseline: str = "auto"


# ── Image ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SceneImage(_SceneElement):
    """An embedded image (must be a data: URI or trusted internal path)."""
    href: str = ""          # data: URI — no external URLs
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    def __post_init__(self) -> None:
        if self.href and not self.href.startswith("data:"):
            raise ValueError("SceneImage.href must be a data: URI")


# ── Groups and layers ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SceneGroup(_SceneElement):
    """A logical group of scene elements (maps to SVG <g>)."""
    children: Tuple[object, ...] = ()   # SceneElement union


# Union type of all paintable elements (declared after SceneGroup so the type is resolved)
SceneElement = (
    SceneRect
    | SceneRoundedRect
    | SceneCircle
    | SceneEllipse
    | SceneLine
    | ScenePolyline
    | ScenePolygon
    | ScenePath
    | SceneText
    | SceneImage
    | SceneGroup
)


# ── Named paint layers ────────────────────────────────────────────────────────

LAYER_BACKGROUND = "background"
LAYER_BOUNDARIES = "boundaries"
LAYER_EDGES = "edges"
LAYER_NODES = "nodes"
LAYER_LABELS = "labels"
LAYER_NOTES = "notes"
LAYER_OVERLAYS = "overlays"

LAYER_ORDER = (
    LAYER_BACKGROUND,
    LAYER_BOUNDARIES,
    LAYER_EDGES,
    LAYER_NODES,
    LAYER_LABELS,
    LAYER_NOTES,
    LAYER_OVERLAYS,
)


@dataclass(frozen=True)
class SvgScene:
    """Top-level immutable paint scene.  Serialize with svg_serializer.scene_to_svg()."""
    scene_id: str
    diagram_type: str
    width: float
    height: float
    view_box: Tuple[float, float, float, float]    # (x, y, w, h)
    accessibility: AccessibilityMetadata = field(default_factory=AccessibilityMetadata)
    definitions: Tuple[object, ...] = ()   # MarkerDefinition | Gradient | ClipPath
    layers: Tuple[Tuple[str, Tuple[object, ...]], ...] = ()
    # Each entry: (layer_name, tuple_of_scene_elements)
    diagnostics: Tuple[str, ...] = ()
    theme_id: str = "default"
    renderer_backend: str = "native-svg"
    direction: str = ""

    def __post_init__(self) -> None:
        vb = self.view_box
        if len(vb) != 4:
            raise ValueError("view_box must be a 4-tuple (x, y, w, h)")
        if not math.isfinite(vb[2]) or vb[2] <= 0:
            raise ValueError(f"view_box width must be positive finite; got {vb[2]}")
        if not math.isfinite(vb[3]) or vb[3] <= 0:
            raise ValueError(f"view_box height must be positive finite; got {vb[3]}")
        _check_finite(self.width, "SvgScene.width")
        _check_finite(self.height, "SvgScene.height")

    def get_layer(self, name: str) -> Tuple[object, ...]:
        for lname, elements in self.layers:
            if lname == name:
                return elements
        return ()

    @classmethod
    def make_empty(
        cls,
        scene_id: str,
        diagram_type: str,
        width: float,
        height: float,
    ) -> "SvgScene":
        """Create an empty scene with standard layer skeleton."""
        layers = tuple((name, ()) for name in LAYER_ORDER)
        return cls(
            scene_id=scene_id,
            diagram_type=diagram_type,
            width=width,
            height=height,
            view_box=(0.0, 0.0, width, height),
            layers=layers,
        )


# ── Native renderer capability registry ──────────────────────────────────────

import enum


class NativeParityLevel(enum.Enum):
    FULL = "full"                   # Full semantic parity with mmdc oracle
    PARTIAL = "partial"             # Renders real content; some features missing
    NOT_IMPLEMENTED = "not-implemented"  # Will be implemented; currently raises NativeRenderError
    UNSUPPORTED = "unsupported"     # Explicitly unsupported (Sankey, ZenUML)


@dataclass(frozen=True)
class NativeRendererSpec:
    directive: str
    parity: NativeParityLevel
    supported_features: Tuple[str, ...] = ()
    unsupported_features: Tuple[str, ...] = ()


NATIVE_RENDERER_REGISTRY: dict = {}  # populated below


def _reg(
    directive: str,
    parity: NativeParityLevel,
    supported: Tuple[str, ...] = (),
    unsupported: Tuple[str, ...] = (),
) -> None:
    NATIVE_RENDERER_REGISTRY[directive] = NativeRendererSpec(
        directive=directive,
        parity=parity,
        supported_features=supported,
        unsupported_features=unsupported,
    )


# Partially-implemented types (render real content, some features missing)
_reg("flowchart", NativeParityLevel.PARTIAL,
     supported=("nodes", "edges", "groups", "labels", "basic-shapes"),
     unsupported=("compound-layout-recursive",))
# "graph" is a DIRECTIVE_ALIASES alias → wired by _reconcile_with_renderer_registry()
_reg("statediagram-v2", NativeParityLevel.PARTIAL,
     supported=("states", "transitions"),
     unsupported=("pseudo-states", "composite-states", "notes"))
_reg("statediagram", NativeParityLevel.PARTIAL,
     supported=("states", "transitions"),
     unsupported=("pseudo-states", "composite-states", "notes"))
_reg("classdiagram", NativeParityLevel.PARTIAL,
     supported=("classes", "relationships"),
     unsupported=("finalized-layout", "member-layouts"))
_reg("timeline", NativeParityLevel.PARTIAL,
     supported=("periods", "events", "sections"),
     unsupported=("measured-text", "activity-line-marker", "theme-tokens"))
_reg("mindmap", NativeParityLevel.PARTIAL,
     supported=("radial-layout",),
     unsupported=("tidy-tree-layout",))
_reg("architecture-beta", NativeParityLevel.PARTIAL,
     supported=("services", "groups", "edges", "semantic-icons", "side-ports", "bidir-single-path"),
     unsupported=())
_reg("c4context", NativeParityLevel.PARTIAL,
     supported=("elements", "boundaries", "relations", "distinct-shapes", "birel-single-path"),
     unsupported=())
_reg("c4container", NativeParityLevel.PARTIAL,
     supported=("elements", "boundaries", "relations", "distinct-shapes", "birel-single-path"),
     unsupported=())
_reg("c4component", NativeParityLevel.PARTIAL,
     supported=("elements", "boundaries", "relations", "distinct-shapes", "birel-single-path"),
     unsupported=())

# Newly-implemented types (Stage 6) — PARTIAL parity
_reg("sequencediagram", NativeParityLevel.PARTIAL,
     supported=("participants", "messages", "notes", "lifelines"),
     unsupported=("activations", "loops", "fragments", "measured-text"))
_reg("erdiagram", NativeParityLevel.PARTIAL,
     supported=("entities", "attributes", "relations", "cardinality"),
     unsupported=("measured-text", "cardinality-markers", "identifying-lines"))
_reg("gantt", NativeParityLevel.PARTIAL,
     supported=("sections", "tasks", "status-colours", "relative-dates"),
     unsupported=("measured-text", "weekend-exclusions", "theme-tokens"))
_reg("quadrantchart", NativeParityLevel.PARTIAL,
     supported=("axes", "quadrant-labels", "data-points"),
     unsupported=("measured-text", "theme-tokens"))
_reg("pie", NativeParityLevel.PARTIAL,
     supported=("slices", "legend", "percentages", "showdata"),
     unsupported=("measured-text", "theme-tokens"))
_reg("xychart-beta", NativeParityLevel.PARTIAL,
     supported=("bar-series", "line-series", "axes", "grid"),
     unsupported=("measured-text", "theme-tokens"))
_reg("block-beta", NativeParityLevel.PARTIAL,
     supported=("blocks", "grid-layout", "edges"),
     unsupported=("nested-blocks", "measured-text"))
_reg("packet-beta", NativeParityLevel.PARTIAL,
     supported=("fields", "bit-ranges", "relative-widths", "row-wrap"),
     unsupported=("measured-text", "theme-tokens"))
_reg("kanban", NativeParityLevel.PARTIAL,
     supported=("columns", "cards", "metadata"),
     unsupported=("measured-text", "theme-tokens"))
_reg("journey", NativeParityLevel.PARTIAL,
     supported=("sections", "tasks", "score-colours", "actors"),
     unsupported=("measured-text", "theme-tokens"))
_reg("requirementdiagram", NativeParityLevel.PARTIAL,
     supported=("requirements", "elements", "relations"),
     unsupported=("measured-text", "requirement-types", "theme-tokens"))
_reg("gitgraph", NativeParityLevel.PARTIAL,
     supported=("commits", "branches", "merges", "tags", "cherry-pick"),
     unsupported=("measured-text", "theme-tokens"))

# Explicitly unsupported
_reg("sankey-beta", NativeParityLevel.UNSUPPORTED)
_reg("zenuml", NativeParityLevel.UNSUPPORTED)

del _reg


def _reconcile_with_renderer_registry() -> None:
    """Ensure NATIVE_RENDERER_REGISTRY stays in sync with RENDERER_REGISTRY.

    - Adds any canonical type missing from NATIVE_RENDERER_REGISTRY (default: UNSUPPORTED).
    - Propagates DIRECTIVE_ALIASES so alias keys resolve to the canonical entry.
    - Removes stale keys not present in RENDERER_REGISTRY or its aliases.

    Called once at module load after the _reg() block; idempotent.
    """
    from .registry import DIRECTIVE_ALIASES, RENDERER_REGISTRY  # noqa: PLC0415

    # Add missing canonical types with a safe default parity.
    for dtype in RENDERER_REGISTRY:
        if dtype not in NATIVE_RENDERER_REGISTRY:
            NATIVE_RENDERER_REGISTRY[dtype] = NativeRendererSpec(
                directive=dtype,
                parity=NativeParityLevel.UNSUPPORTED,
            )

    # Wire aliases to their canonical NativeRendererSpec.
    for alias, canonical in DIRECTIVE_ALIASES.items():
        if canonical in NATIVE_RENDERER_REGISTRY:
            NATIVE_RENDERER_REGISTRY[alias] = NATIVE_RENDERER_REGISTRY[canonical]

    # Remove stale keys no longer present in either registry.
    valid = set(RENDERER_REGISTRY.keys()) | set(DIRECTIVE_ALIASES.keys())
    for stale in list(NATIVE_RENDERER_REGISTRY.keys()):
        if stale not in valid:
            del NATIVE_RENDERER_REGISTRY[stale]


_reconcile_with_renderer_registry()
del _reconcile_with_renderer_registry


# ── Legacy capability dataclass (kept for backward compat) ────────────────────

@dataclass(frozen=True)
class RendererCapability:
    diagram_type: str
    native_scene: bool
    semantic_parity_level: str   # "full" | "mechanical" | "stub"
    unsupported_features: Tuple[str, ...] = ()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_finite(v: float, name: str) -> None:
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite; got {v}")


def make_scene_id(diagram_type: str, content_hash: int) -> str:
    """Generate a stable, deterministic scene ID from diagram type and content hash."""
    return f"mermaid-{diagram_type}-{content_hash & 0xFFFFFFFF:08x}"
