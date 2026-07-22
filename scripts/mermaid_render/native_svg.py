"""mermaid_render.native_svg — Native SVG dispatch (no Playwright, no DOM-to-SVG).

Default SVG backend after P2. Activated by to_svg() when
MERMAID_RENDER_SVG_BACKEND != 'legacy-dom'.

Pipeline:
    Mermaid source
    -> detect diagram type
    -> per-type layout + scene construction
    -> SvgScene
    -> svg_serializer.scene_to_svg()
    -> UTF-8 SVG string
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from .errors import (
    NativeRenderError,
    NativeRendererUnavailable,
    UnsupportedDiagramType,
    UnsupportedDiagramFeature,  # noqa: F401 — re-exported for caller convenience
)
from .layout._parser import _detect_directive, _strip_frontmatter
from .layout._strategies import _GRAPH_DIRECTIVES
from .scene import SvgScene
from .svg_serializer import scene_to_svg_str


# ── Render request (immutable, parsed once) ──────────────────────────────────

@dataclass(frozen=True)
class RenderRequest:
    """Immutable parsed render request.

    Constructed by parse_render_request(). All renderers receive this
    rather than re-parsing the source independently.
    """
    original_source: str          # verbatim input from the caller
    clean_source: str             # source with frontmatter block removed
    directive: str                # lower-case diagram directive, e.g. "flowchart"
    direction: str                # "TB" | "LR" | "RL" | "BT"
    frontmatter: MappingProxyType  # MappingProxyType[str, object] parsed from ---…--- block
    diagram_config: MappingProxyType  # MappingProxyType[str, object] from %%{init:…}%% block
    theme: "str | None"           # caller-supplied theme; None means use diagram default
    faithful: bool                # suppress non-Mermaid embellishments
    width_hint: int               # maximum output width in pixels (0 = unconstrained)
    height_hint: int              # maximum output height in pixels (0 = unconstrained)


_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_INIT_RE = re.compile(r"%%\s*\{init:\s*(\{.*?\})\s*\}\s*%%", re.DOTALL)


def _parse_frontmatter(src: str) -> tuple[str, dict]:
    """Strip leading YAML-like frontmatter; return (clean_src, frontmatter_dict)."""
    m = _FRONTMATTER_RE.match(src)
    if not m:
        return src, {}
    body = m.group(1)
    remaining = src[m.end():]
    fm: dict = {}
    for line in body.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return remaining, fm


def _parse_diagram_config(src: str) -> dict:
    """Extract %%{init: {...}}%% config from source."""
    m = _INIT_RE.search(src)
    if not m:
        return {}
    import json
    try:
        return json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return {}


def parse_render_request(
    src: str,
    *,
    theme: "str | None" = None,
    faithful: bool = False,
    width_hint: int = 0,
    height_hint: int = 0,
) -> RenderRequest:
    """Parse a Mermaid source string into an immutable RenderRequest.

    Strips frontmatter once. Detects directive and direction. Preserves
    frontmatter and diagram config for downstream renderers.
    The directive is canonicalized via DIRECTIVE_ALIASES (e.g. "graph" → "flowchart").
    """
    from .registry import canonicalize_directive

    clean_after_fm, frontmatter = _parse_frontmatter(src)
    diagram_config = _parse_diagram_config(clean_after_fm)

    # Use the existing _strip_frontmatter for the canonical clean source
    # (handles both YAML frontmatter and %%{init}%% blocks)
    clean_source = _strip_frontmatter(src)
    directive, auto_direction = _detect_directive(clean_source)

    return RenderRequest(
        original_source=src,
        clean_source=clean_source,
        directive=canonicalize_directive(directive),
        direction=auto_direction.upper(),
        frontmatter=MappingProxyType(frontmatter),
        diagram_config=MappingProxyType(diagram_config),
        theme=theme,
        faithful=faithful,
        width_hint=width_hint,
        height_hint=height_hint,
    )


# ── Environment flag ──────────────────────────────────────────────────────────

BACKEND_ENV = "MERMAID_RENDER_SVG_BACKEND"
BACKEND_NATIVE = "native"
BACKEND_LEGACY = "legacy-dom"


def _use_native() -> bool:
    """Return True when the native SVG backend should be used (the default)."""
    backend = os.environ.get(BACKEND_ENV, BACKEND_NATIVE).lower()
    return backend != BACKEND_LEGACY


# ── Per-type native scene builders ────────────────────────────────────────────

def _class_topology_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    """Build SvgScene for classDiagram using graph topology pipeline."""
    import re
    from .layout._constants import (
        _Node, _Edge, NODE_CAP, NODE_W, CANVAS_PAD,
        _node_render_h, _TERMINAL_NODE_SIZE, _is_terminal_circle,
    )
    from .layout._strategies import _CLASS_REL_RE, _class_rel_style, _directive_content
    from .layout._layout import (
        _break_cycles, _assign_ranks, _minimize_crossings,
        _assign_coordinates,
    )
    from .layout._routing import _route_edges
    from .layout._renderer import _extract_diagram_title, _compute_group_bboxes
    from .paint import graph_to_scene

    content_lines = _directive_content(src)
    nodes: dict = {}
    edges: list = []
    current_class = None
    class_members: dict = {}

    for raw in content_lines:
        line = raw.strip()
        if not line or line.startswith(("%%", "//")):
            continue
        if line == "}":
            current_class = None
            continue
        m = re.match(r'^class\s+(\w+)', line)
        if m:
            cid = m.group(1)
            nodes.setdefault(cid, _Node(id=cid, label=cid, shape="rect"))
            class_members.setdefault(cid, [])
            current_class = cid if "{" in line else None
            continue
        if current_class:
            if line not in ("+", "-", "#", "~"):
                class_members.setdefault(current_class, []).append(line)
            continue
        m = _CLASS_REL_RE.match(line)
        if m:
            c1, mul_src, op, mul_dst, c2, lbl = (
                m.group(1), m.group(2) or "", m.group(3),
                m.group(4) or "", m.group(5), m.group(6) or "",
            )
            for cid in (c1, c2):
                nodes.setdefault(cid, _Node(id=cid, label=cid, shape="rect"))
                class_members.setdefault(cid, [])
            arrow_src = op.startswith(("<|", "*", "o"))
            edges.append(_Edge(
                src=c1, dst=c2, label=lbl.strip(),
                style=_class_rel_style(op), arrow=True,
                arrow_src=arrow_src,
                src_label=mul_src, dst_label=mul_dst,
            ))
            continue
        m2 = re.match(r'^(\w+)\s*:', line)
        if m2:
            nodes.setdefault(m2.group(1), _Node(id=m2.group(1), label=m2.group(1), shape="rect"))
            class_members.setdefault(m2.group(1), [])

    if not nodes:
        raise ValueError("No classes found in classDiagram.")

    for cid, members in class_members.items():
        if cid in nodes and members:
            attrs = [mm for mm in members if "(" not in mm]
            methods = [mm for mm in members if "(" in mm]
            rows = attrs
            if attrs and methods:
                rows = attrs + ["---"] + methods
            elif methods:
                rows = methods
            nodes[cid].label = f"{cid}|" + "\n".join(rows)

    groups: dict = {}

    if len(nodes) > NODE_CAP:
        raise ValueError(f"Cap exceeded: {len(nodes)} nodes (cap {NODE_CAP}).")

    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)

    canvas_w, canvas_h = _assign_coordinates(nodes, direction)

    real_nodes = [n for n in nodes.values() if not n.is_dummy]
    if real_nodes:
        canvas_h = max(n.y + _node_render_h(n) for n in real_nodes) + CANVAS_PAD
        canvas_w = max(n.x + (n.width or NODE_W) for n in real_nodes) + CANVAS_PAD

    zoom = 1.0
    if width_hint and canvas_w > 0:
        zoom = min(width_hint / canvas_w, 1.0)

    routes = _route_edges(nodes, edges, canvas_w, direction, {})
    title = _extract_diagram_title(src)

    return graph_to_scene(
        nodes=nodes,
        edges=edges,
        groups=groups,
        routes=routes,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        diagram_type="classdiagram",
        direction=direction,
        group_bboxes=None,
        title=title,
        zoom=zoom,
    )


def _sequence_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("sequencediagram", "not-implemented")


def _er_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("erdiagram", "not-implemented")


def _class_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    return _class_topology_scene(src, direction, width_hint)


def _gantt_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("gantt", "not-implemented")


def _timeline_scene(
    src: str,
    direction: str,
    width_hint: int,
    diagram_config: Optional[dict] = None,
) -> SvgScene:
    """Native semantic scene for timeline — delegates to dedicated module."""
    from .layout.timeline import layout_timeline_scene
    return layout_timeline_scene(src, width_hint=width_hint, diagram_config=diagram_config)


def _quadrant_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("quadrantchart", "not-implemented")


def _pie_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("pie", "not-implemented")


def _xychart_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("xychart-beta", "not-implemented")


def _get_mindmap_layout(request: RenderRequest) -> str:
    """Extract the mindmap layout algorithm from frontmatter or diagram_config."""
    if request.frontmatter.get("layout") == "tidy-tree":
        return "tidy-tree"
    # _parse_frontmatter stores values as raw strings; substring check handles
    # `config: { layout: tidy-tree }` → "{ layout: tidy-tree }"
    if "tidy-tree" in str(request.frontmatter.get("config", "")):
        return "tidy-tree"
    dc = request.diagram_config
    if dc.get("layout") == "tidy-tree":
        return "tidy-tree"
    cfg = dc.get("config", {})
    if isinstance(cfg, dict) and cfg.get("layout") == "tidy-tree":
        return "tidy-tree"
    return "radial"


def _mindmap_scene(
    src: str, direction: str, width_hint: int, layout: str = "radial"
) -> SvgScene:
    """Native semantic scene for mindmap — delegates to dedicated module."""
    from .layout.mindmap import layout_mindmap_scene
    return layout_mindmap_scene(src, width_hint=width_hint, layout=layout)


def _block_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("block-beta", "not-implemented")


def _packet_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("packet-beta", "not-implemented")


def _kanban_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("kanban", "not-implemented")


def _architecture_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    """Native scene for architecture-beta — delegates to dedicated module."""
    from .layout.architecture import layout_architecture_scene
    return layout_architecture_scene(src, width_hint=width_hint)


def _c4_scene(src: str, direction: str, width_hint: int, directive: str) -> SvgScene:
    """Native scene for C4 — delegates to dedicated module."""
    from .layout.c4_layout import layout_c4_scene
    return layout_c4_scene(src, c4_type=directive.lower(), width_hint=width_hint)


def _journey_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("journey", "not-implemented")


def _requirement_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("requirementdiagram", "not-implemented")


def _gitgraph_scene(src: str, direction: str, width_hint: int) -> SvgScene:
    raise NativeRenderError("gitgraph", "not-implemented")


# ── Main dispatch ─────────────────────────────────────────────────────────────

_NOT_IMPLEMENTED_DIRECTIVES = frozenset({
    "sequencediagram", "erdiagram", "gantt", "quadrantchart", "pie",
    "xychart-beta", "block-beta", "packet-beta", "kanban", "journey",
    "requirementdiagram", "gitgraph",
})


def _dispatch_scene(
    clean: str,
    directive: str,
    direction: str,
    width_hint: int,
    height_hint: int,
) -> SvgScene:
    """Route a cleaned Mermaid source to the appropriate scene builder."""
    d = directive.lower()
    if d in _GRAPH_DIRECTIVES:
        from .layout._strategies import _compile_flowchart, RenderOptions
        from .layout._renderer import _extract_diagram_title
        from .paint import finalized_layout_to_scene
        compiled = _compile_flowchart(
            clean, width_hint, RenderOptions(),
            direction_override=direction,
            height_hint=height_hint,
        )
        title = _extract_diagram_title(clean)
        return finalized_layout_to_scene(compiled.layout, diagram_type=d, title=title)
    elif d == "sequencediagram":
        return _sequence_scene(clean, direction, width_hint)
    elif d == "erdiagram":
        return _er_scene(clean, direction, width_hint)
    elif d == "classdiagram":
        return _class_scene(clean, direction, width_hint)
    elif d == "gantt":
        return _gantt_scene(clean, direction, width_hint)
    elif d == "timeline":
        return _timeline_scene(clean, direction, width_hint)
    elif d == "quadrantchart":
        return _quadrant_scene(clean, direction, width_hint)
    elif d == "pie" or d.startswith("pie "):
        return _pie_scene(clean, direction, width_hint)
    elif d == "xychart-beta":
        return _xychart_scene(clean, direction, width_hint)
    elif d == "mindmap":
        return _mindmap_scene(clean, direction, width_hint)
    elif d == "block-beta":
        return _block_scene(clean, direction, width_hint)
    elif d == "packet-beta":
        return _packet_scene(clean, direction, width_hint)
    elif d == "kanban":
        return _kanban_scene(clean, direction, width_hint)
    elif d == "architecture-beta":
        return _architecture_scene(clean, direction, width_hint)
    elif d in ("c4context", "c4container", "c4component"):
        return _c4_scene(clean, direction, width_hint, d)
    elif d == "journey":
        return _journey_scene(clean, direction, width_hint)
    elif d == "requirementdiagram":
        return _requirement_scene(clean, direction, width_hint)
    elif d == "gitgraph":
        return _gitgraph_scene(clean, direction, width_hint)
    elif d in ("sankey-beta", "zenuml"):
        raise UnsupportedDiagramType(d)
    else:
        raise UnsupportedDiagramType(d)


def dispatch_native(
    src: str,
    *,
    theme: "str | None" = None,
    faithful: bool = False,
    width_hint: int = 0,
    height_hint: int = 0,
) -> str:
    """Dispatch Mermaid source to a native SVG string.

    Raises typed errors on failure:
      - NativeRenderError(phase="not-implemented") for LEGACY_ONLY types
      - UnsupportedDiagramType for UNSUPPORTED types (sankey-beta, zenuml)
      - NativeRenderError for other builder failures
      - ValueError for diagram-level errors (empty graph, etc.)

    Never silently falls back to a placeholder.
    """
    request = parse_render_request(
        src,
        theme=theme,
        faithful=faithful,
        width_hint=width_hint,
        height_hint=height_hint,
    )
    d = request.directive
    direction = request.direction

    # Normalize "pie title ..." → "pie"
    if d.startswith("pie "):
        d = "pie"

    clean = request.clean_source

    if d in _GRAPH_DIRECTIVES:
        from .layout._strategies import _compile_flowchart, RenderOptions
        from .layout._renderer import _extract_diagram_title
        from .paint import finalized_layout_to_scene
        _opts = RenderOptions(faithful_mermaid=request.faithful)
        compiled = _compile_flowchart(
            clean, width_hint, _opts,
            direction_override=direction,
            height_hint=height_hint,
        )
        title = _extract_diagram_title(clean)
        scene = finalized_layout_to_scene(compiled.layout, diagram_type=d, title=title)
    elif d == "classdiagram":
        scene = _class_scene(clean, direction, width_hint)
    elif d == "timeline":
        scene = _timeline_scene(clean, direction, width_hint, diagram_config=dict(request.diagram_config))
    elif d == "mindmap":
        scene = _mindmap_scene(clean, direction, width_hint, _get_mindmap_layout(request))
    elif d == "architecture-beta":
        scene = _architecture_scene(clean, direction, width_hint)
    elif d in ("c4context", "c4container", "c4component"):
        scene = _c4_scene(clean, direction, width_hint, d)
    elif d in _NOT_IMPLEMENTED_DIRECTIVES:
        raise NativeRenderError(d, "not-implemented")
    elif d in ("sankey-beta", "zenuml"):
        raise UnsupportedDiagramType(d)
    else:
        raise NativeRenderError(d, "dispatch")

    return scene_to_svg_str(scene)


# ── Registry-backed pipeline ──────────────────────────────────────────────────

def _build_graph_pipeline(request: RenderRequest, diagram_type: str) -> "tuple[SvgScene, object]":
    """Build (SvgScene, ValidationResult) for graph-topology types (flowchart, statediagram*).

    Called by the registry lazy builders (_build_flowchart, etc.) to avoid
    duplicating the compile/layout/paint pipeline.
    """
    from .layout._strategies import _compile_flowchart, RenderOptions
    from .layout._renderer import _extract_diagram_title
    from .paint import finalized_layout_to_scene

    _opts = RenderOptions(faithful_mermaid=request.faithful)
    compiled = _compile_flowchart(
        request.clean_source,
        request.width_hint,
        _opts,
        direction_override=request.direction,
        height_hint=request.height_hint,
    )
    title = _extract_diagram_title(request.clean_source)
    scene = finalized_layout_to_scene(compiled.layout, diagram_type=diagram_type, title=title)
    return scene, compiled.validation


def render_svg_result(
    src: str,
    *,
    theme: "str | None" = None,
    width_hint: int = 0,
    height_hint: int = 0,
    faithful: bool = False,
    fallback: "str | None" = None,
) -> "object":  # -> RenderResult, imported lazily to avoid circular import
    """Render Mermaid source to a typed RenderResult via the registry pipeline.

    This is the authoritative dispatch path.  to_svg() and dispatch_native_result()
    both delegate here.

    Raises typed errors (not RenderResult) on hard failures:
      - UnsupportedDiagramType  — diagram type is "unsupported" in the registry or unknown
      - NativeRendererUnavailable — diagram type is "legacy-only" and no fallback was requested
      - NativeRenderError       — builder/serializer raised an unexpected exception

    On success: returns RenderResult with is_success(strict=True) == True for IMPLEMENTED
    types whose geometry validation passed.
    """
    from .registry import RENDERER_REGISTRY, canonicalize_directive, RenderResult
    from .errors import (
        NativeRenderError, NativeRendererUnavailable, UnsupportedDiagramType,
        UnsupportedDiagramFeature,
    )

    request = parse_render_request(
        src,
        theme=theme,
        faithful=faithful,
        width_hint=width_hint,
        height_hint=height_hint,
    )
    canonical = request.directive  # already canonicalized by parse_render_request()

    cap = RENDERER_REGISTRY.get(canonical)
    if cap is None:
        raise UnsupportedDiagramType(canonical)

    if cap.native_status == "unsupported":
        raise UnsupportedDiagramType(canonical)

    if cap.native_status == "legacy-only":
        raise NativeRendererUnavailable(canonical)

    if cap.native_builder is None:
        raise NativeRenderError(
            canonical, "dispatch",
            cause=NotImplementedError(f"No native_builder registered for {canonical!r}"),
        )

    # Call the builder
    try:
        result = cap.native_builder(request)
        if isinstance(result, tuple) and len(result) == 2:
            scene, validation = result
        else:
            scene, validation = result, None
    except NativeRenderError:
        raise  # already typed, preserve exactly
    except Exception as e:
        raise NativeRenderError(canonical, "build", cause=e) from e

    # Determine geometry status from validation result
    geometry_errors: "tuple[str, ...]" = ()
    if validation is not None and cap.native_status == "implemented":
        errors_list = getattr(validation, "errors", None)
        if errors_list is not None:
            if errors_list:
                geometry: str = "failed"
                geometry_errors = tuple(str(e) for e in errors_list)
            else:
                geometry = "passed"
        else:
            geometry = "unvalidated"
    else:
        geometry = "unvalidated"

    # Determine semantic lanes based on status.
    # Experimental types also force geometry="unvalidated" regardless of what the
    # builder returned — but because the implemented-guard above only fires for
    # cap.native_status=="implemented", experimental builders never populate
    # geometry_errors, so errors stays () on the experimental path.
    if cap.native_status == "experimental":
        sem_adapter: str = "unsupported"
        syntax_cov: str = "partial"
        geometry = "unvalidated"
    else:
        sem_adapter = "passed"
        syntax_cov = "passed"

    # Serialize
    try:
        svg_str = scene_to_svg_str(scene)
    except Exception as e:
        raise NativeRenderError(canonical, "serialize", cause=e) from e

    backend = getattr(scene, "renderer_backend", "native")

    return RenderResult(
        svg=svg_str,
        diagram_type=canonical,
        backend=backend,
        semantic_adapter=sem_adapter,
        syntax_coverage=syntax_cov,
        geometry=geometry,
        serialization="passed",
        warnings=(),
        errors=geometry_errors,
    )


