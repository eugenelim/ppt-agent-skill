"""mermaid_render.svg_serializer — Deterministic native SVG serializer.

Converts an immutable SvgScene to UTF-8 SVG bytes using lxml.etree.

Guarantees:
- Deterministic element and attribute ordering
- Deterministic IDs derived from semantic identity (not object id() / uuid / timestamps)
- Canonical float formatting: ≤3dp, no trailing zeros, no negative zero, rejects NaN/inf
- Proper XML escaping (lxml handles this)
- <text>/<tspan> output based on SceneText.lines
- No <foreignObject>
- No html/head/body elements
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from lxml import etree

from .scene import (
    SvgScene, SceneGroup, SceneRect, SceneRoundedRect, SceneCircle, SceneEllipse,
    SceneLine, ScenePolyline, ScenePolygon, ScenePath, SceneText, SceneTextLine,
    SceneImage, PaintStyle, StrokeStyle, FillStyle,
    MarkerDefinition, LinearGradientDefinition, RadialGradientDefinition,
    ClipPathDefinition, _SceneElement, LAYER_ORDER,
)

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


# ── Float formatting ──────────────────────────────────────────────────────────

def _fmt(v: float, dp: int = 3) -> str:
    """Format a float to at most `dp` decimal places, removing trailing zeros."""
    if not math.isfinite(v):
        raise ValueError(f"Non-finite coordinate: {v}")
    if v == 0.0:
        return "0"
    rounded = round(v, dp)
    if rounded == 0.0:
        return "0"
    s = f"{rounded:.{dp}f}".rstrip("0").rstrip(".")
    if s == "-0":
        return "0"
    return s


def _pts(points: Tuple[Tuple[float, float], ...]) -> str:
    return " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in points)


def _path_d(commands: Tuple[tuple, ...]) -> str:
    parts: List[str] = []
    for cmd in commands:
        letter = cmd[0]
        nums = cmd[1:]
        if letter == "Z":
            parts.append("Z")
        else:
            parts.append(letter + " " + " ".join(_fmt(n) for n in nums))
    return " ".join(parts)


# ── Deterministic ID generation ───────────────────────────────────────────────

def _content_hash(scene_id: str) -> str:
    """Stable 8-char hex derived from the scene's semantic id."""
    return hashlib.sha256(scene_id.encode()).hexdigest()[:8]


def _def_id(scene_id: str, def_type: str, key: str) -> str:
    """Deterministic id for a <defs> item."""
    raw = f"{scene_id}:{def_type}:{key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


# ── Attribute helpers ─────────────────────────────────────────────────────────

def _apply_paint(el: etree._Element, paint: PaintStyle) -> None:
    fill = paint.fill
    if fill.color and fill.color != "none":
        el.set("fill", fill.color)
        if fill.opacity < 1.0:
            el.set("fill-opacity", _fmt(fill.opacity))
        if fill.fill_rule != "nonzero":
            el.set("fill-rule", fill.fill_rule)
    else:
        el.set("fill", "none")

    stroke = paint.stroke
    if stroke is not None:
        el.set("stroke", stroke.color)
        if stroke.width != 1.0:
            el.set("stroke-width", _fmt(stroke.width))
        if stroke.dasharray:
            el.set("stroke-dasharray", stroke.dasharray)
        if stroke.linecap != "butt":
            el.set("stroke-linecap", stroke.linecap)
        if stroke.linejoin != "miter":
            el.set("stroke-linejoin", stroke.linejoin)
        if stroke.opacity < 1.0:
            el.set("stroke-opacity", _fmt(stroke.opacity))

    if paint.opacity < 1.0:
        el.set("opacity", _fmt(paint.opacity))


def _apply_base(el: etree._Element, elem: _SceneElement) -> None:
    if elem.element_id:
        el.set("id", elem.element_id)
    if elem.css_classes:
        el.set("class", " ".join(elem.css_classes))
    if elem.semantic_role:
        el.set("role", elem.semantic_role)
    for name, value in sorted(elem.data_attrs):
        el.set(f"data-{name}", value)
    if elem.transform:
        el.set("transform", elem.transform)
    if elem.clip_ref:
        el.set("clip-path", f"url(#{elem.clip_ref})")
    _apply_paint(el, elem.paint)


# ── Element serializers ───────────────────────────────────────────────────────

def _ser_rect(elem: SceneRect, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "rect")
    el.set("x", _fmt(elem.x))
    el.set("y", _fmt(elem.y))
    el.set("width", _fmt(elem.w))
    el.set("height", _fmt(elem.h))
    _apply_base(el, elem)
    return el


def _ser_rounded_rect(elem: SceneRoundedRect, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "rect")
    el.set("x", _fmt(elem.x))
    el.set("y", _fmt(elem.y))
    el.set("width", _fmt(elem.w))
    el.set("height", _fmt(elem.h))
    if elem.rx:
        el.set("rx", _fmt(elem.rx))
    if elem.ry:
        el.set("ry", _fmt(elem.ry))
    _apply_base(el, elem)
    return el


def _ser_circle(elem: SceneCircle, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "circle")
    el.set("cx", _fmt(elem.cx))
    el.set("cy", _fmt(elem.cy))
    el.set("r", _fmt(elem.r))
    _apply_base(el, elem)
    return el


def _ser_ellipse(elem: SceneEllipse, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "ellipse")
    el.set("cx", _fmt(elem.cx))
    el.set("cy", _fmt(elem.cy))
    el.set("rx", _fmt(elem.rx))
    el.set("ry", _fmt(elem.ry))
    _apply_base(el, elem)
    return el


def _ser_line(elem: SceneLine, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "line")
    el.set("x1", _fmt(elem.x1))
    el.set("y1", _fmt(elem.y1))
    el.set("x2", _fmt(elem.x2))
    el.set("y2", _fmt(elem.y2))
    if elem.marker_start:
        el.set("marker-start", f"url(#{elem.marker_start})")
    if elem.marker_end:
        el.set("marker-end", f"url(#{elem.marker_end})")
    _apply_base(el, elem)
    return el


def _ser_polyline(elem: ScenePolyline, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "polyline")
    el.set("points", _pts(elem.points))
    if elem.marker_start:
        el.set("marker-start", f"url(#{elem.marker_start})")
    if elem.marker_end:
        el.set("marker-end", f"url(#{elem.marker_end})")
    _apply_base(el, elem)
    return el


def _ser_polygon(elem: ScenePolygon, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "polygon")
    el.set("points", _pts(elem.points))
    _apply_base(el, elem)
    return el


def _ser_path(elem: ScenePath, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "path")
    el.set("d", _path_d(elem.commands))
    if elem.marker_start:
        el.set("marker-start", f"url(#{elem.marker_start})")
    if elem.marker_end:
        el.set("marker-end", f"url(#{elem.marker_end})")
    _apply_base(el, elem)
    return el


def _ser_text(elem: SceneText, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "text")
    el.set("text-anchor", elem.text_anchor)
    if elem.dominant_baseline != "auto":
        el.set("dominant-baseline", elem.dominant_baseline)
    _apply_base(el, elem)

    for line in elem.lines:
        tspan = etree.SubElement(el, "tspan")
        tspan.set("x", _fmt(line.x))
        tspan.set("y", _fmt(line.y))
        if line.font_size != 15.0:
            tspan.set("font-size", _fmt(line.font_size))
        if line.font_weight != 400:
            tspan.set("font-weight", str(line.font_weight))
        if line.italic:
            tspan.set("font-style", "italic")
        if line.letter_spacing:
            tspan.set("letter-spacing", _fmt(line.letter_spacing))
        if line.fill_color and line.fill_color != "#000000":
            tspan.set("fill", line.fill_color)
        if line.strikethrough:
            tspan.set("text-decoration", "line-through")
        tspan.text = line.text
    return el


def _ser_image(elem: SceneImage, parent: etree._Element) -> etree._Element:
    el = etree.SubElement(parent, "image")
    el.set("x", _fmt(elem.x))
    el.set("y", _fmt(elem.y))
    el.set("width", _fmt(elem.w))
    el.set("height", _fmt(elem.h))
    el.set("{%s}href" % XLINK_NS, elem.href)
    el.set("href", elem.href)
    _apply_base(el, elem)
    return el


def _ser_group(elem: SceneGroup, parent: etree._Element) -> etree._Element:
    g = etree.SubElement(parent, "g")
    _apply_base(g, elem)
    for child in elem.children:
        _ser_element(child, g)
    return g


def _ser_element(elem: object, parent: etree._Element) -> None:
    if isinstance(elem, SceneGroup):
        _ser_group(elem, parent)
    elif isinstance(elem, SceneRect):
        _ser_rect(elem, parent)
    elif isinstance(elem, SceneRoundedRect):
        _ser_rounded_rect(elem, parent)
    elif isinstance(elem, SceneCircle):
        _ser_circle(elem, parent)
    elif isinstance(elem, SceneEllipse):
        _ser_ellipse(elem, parent)
    elif isinstance(elem, SceneLine):
        _ser_line(elem, parent)
    elif isinstance(elem, ScenePolyline):
        _ser_polyline(elem, parent)
    elif isinstance(elem, ScenePolygon):
        _ser_polygon(elem, parent)
    elif isinstance(elem, ScenePath):
        _ser_path(elem, parent)
    elif isinstance(elem, SceneText):
        _ser_text(elem, parent)
    elif isinstance(elem, SceneImage):
        _ser_image(elem, parent)
    else:
        raise TypeError(f"Unknown scene element type: {type(elem)}")


# ── Definitions serializers ───────────────────────────────────────────────────

def _ser_marker(mdef: MarkerDefinition, defs: etree._Element) -> None:
    marker = etree.SubElement(defs, "marker")
    marker.set("id", mdef.marker_id)
    marker.set("markerWidth", _fmt(mdef.size))
    marker.set("markerHeight", _fmt(mdef.size))
    marker.set("refX", _fmt(mdef.refX))
    marker.set("refY", _fmt(mdef.refY))
    marker.set("orient", "auto")
    marker.set("markerUnits", "strokeWidth")

    mtype = mdef.marker_type
    c = mdef.color
    s = mdef.size

    if mtype == "arrow-end":
        # Filled triangle pointing right
        path = etree.SubElement(marker, "path")
        path.set("d", f"M 0 0 L {_fmt(s)} {_fmt(s/2)} L 0 {_fmt(s)} Z")
        path.set("fill", c)
    elif mtype == "arrow-start":
        # Filled triangle pointing left
        path = etree.SubElement(marker, "path")
        path.set("d", f"M {_fmt(s)} 0 L 0 {_fmt(s/2)} L {_fmt(s)} {_fmt(s)} Z")
        path.set("fill", c)
    elif mtype == "arrow-open":
        # Open chevron
        path = etree.SubElement(marker, "path")
        path.set("d", f"M 1 1 L {_fmt(s-1)} {_fmt(s/2)} L 1 {_fmt(s-1)}")
        path.set("fill", "none")
        path.set("stroke", c)
        path.set("stroke-width", "2")
    elif mtype == "arrow-filled":
        # Same as arrow-end
        path = etree.SubElement(marker, "path")
        path.set("d", f"M 0 0 L {_fmt(s)} {_fmt(s/2)} L 0 {_fmt(s)} Z")
        path.set("fill", c)
    elif mtype == "arrow-bidirectional":
        # Two triangles (both ends — used on a path: set marker-start AND marker-end)
        path = etree.SubElement(marker, "path")
        path.set("d", f"M 0 0 L {_fmt(s)} {_fmt(s/2)} L 0 {_fmt(s)} Z")
        path.set("fill", c)
    elif mtype == "state-transition":
        path = etree.SubElement(marker, "path")
        path.set("d", f"M 0 0 L {_fmt(s)} {_fmt(s/2)} L 0 {_fmt(s)} Z")
        path.set("fill", c)
    elif mtype == "timeline-end":
        path = etree.SubElement(marker, "path")
        path.set("d", f"M 0 0 L {_fmt(s)} {_fmt(s/2)} L 0 {_fmt(s)} Z")
        path.set("fill", c)
    else:
        # Default: filled triangle
        path = etree.SubElement(marker, "path")
        path.set("d", f"M 0 0 L {_fmt(s)} {_fmt(s/2)} L 0 {_fmt(s)} Z")
        path.set("fill", c)


def _ser_linear_gradient(gdef: LinearGradientDefinition, defs: etree._Element) -> None:
    grad = etree.SubElement(defs, "linearGradient")
    grad.set("id", gdef.gradient_id)
    grad.set("x1", _fmt(gdef.x1))
    grad.set("y1", _fmt(gdef.y1))
    grad.set("x2", _fmt(gdef.x2))
    grad.set("y2", _fmt(gdef.y2))
    grad.set("gradientUnits", gdef.gradient_units)
    for offset, color, opacity in gdef.stops:
        stop = etree.SubElement(grad, "stop")
        stop.set("offset", _fmt(offset))
        stop.set("stop-color", color)
        if opacity < 1.0:
            stop.set("stop-opacity", _fmt(opacity))


def _ser_radial_gradient(gdef: RadialGradientDefinition, defs: etree._Element) -> None:
    grad = etree.SubElement(defs, "radialGradient")
    grad.set("id", gdef.gradient_id)
    grad.set("cx", _fmt(gdef.cx))
    grad.set("cy", _fmt(gdef.cy))
    grad.set("r", _fmt(gdef.r))
    grad.set("gradientUnits", gdef.gradient_units)
    for offset, color, opacity in gdef.stops:
        stop = etree.SubElement(grad, "stop")
        stop.set("offset", _fmt(offset))
        stop.set("stop-color", color)
        if opacity < 1.0:
            stop.set("stop-opacity", _fmt(opacity))


def _ser_clip_path(cdef: ClipPathDefinition, defs: etree._Element) -> None:
    cp = etree.SubElement(defs, "clipPath")
    cp.set("id", cdef.clip_id)
    rect = etree.SubElement(cp, "rect")
    rect.set("x", _fmt(cdef.clip_x))
    rect.set("y", _fmt(cdef.clip_y))
    rect.set("width", _fmt(cdef.clip_w))
    rect.set("height", _fmt(cdef.clip_h))
    if cdef.rx:
        rect.set("rx", _fmt(cdef.rx))
    if cdef.ry:
        rect.set("ry", _fmt(cdef.ry))


# ── Validation ────────────────────────────────────────────────────────────────

class SceneValidationError(ValueError):
    pass


def validate_scene(scene: SvgScene) -> None:
    """Raise SceneValidationError if the scene has structural problems.

    Checks:
    - No foreignObject elements
    - No duplicate element ids
    - No unresolved marker/clip references
    - Valid viewBox (positive width/height)
    """
    vb = scene.view_box
    if vb[2] <= 0 or vb[3] <= 0:
        raise SceneValidationError(f"viewBox has non-positive dimensions: {vb}")

    seen_ids: Set[str] = set()
    defined_markers: Set[str] = set()
    defined_clips: Set[str] = set()
    referenced_markers: Set[str] = set()
    referenced_clips: Set[str] = set()

    for defn in scene.definitions:
        if isinstance(defn, MarkerDefinition):
            if defn.marker_id in seen_ids:
                raise SceneValidationError(f"Duplicate id: {defn.marker_id!r}")
            seen_ids.add(defn.marker_id)
            defined_markers.add(defn.marker_id)
        elif isinstance(defn, (LinearGradientDefinition, RadialGradientDefinition)):
            gid = defn.gradient_id
            if gid in seen_ids:
                raise SceneValidationError(f"Duplicate id: {gid!r}")
            seen_ids.add(gid)
        elif isinstance(defn, ClipPathDefinition):
            if defn.clip_id in seen_ids:
                raise SceneValidationError(f"Duplicate id: {defn.clip_id!r}")
            seen_ids.add(defn.clip_id)
            defined_clips.add(defn.clip_id)

    def _collect(elem: object) -> None:
        if isinstance(elem, _SceneElement):
            if elem.element_id:
                if elem.element_id in seen_ids:
                    raise SceneValidationError(f"Duplicate id: {elem.element_id!r}")
                seen_ids.add(elem.element_id)
            if elem.clip_ref:
                referenced_clips.add(elem.clip_ref)
        if isinstance(elem, (SceneLine, ScenePolyline, ScenePath)):
            if elem.marker_start:
                referenced_markers.add(elem.marker_start)
            if elem.marker_end:
                referenced_markers.add(elem.marker_end)
        if isinstance(elem, SceneGroup):
            for child in elem.children:
                _collect(child)

    for _, elements in scene.layers:
        for elem in elements:
            _collect(elem)

    unresolved_markers = referenced_markers - defined_markers
    if unresolved_markers:
        raise SceneValidationError(f"Unresolved marker references: {sorted(unresolved_markers)}")

    unresolved_clips = referenced_clips - defined_clips
    if unresolved_clips:
        raise SceneValidationError(f"Unresolved clip references: {sorted(unresolved_clips)}")


# ── Main serializer ───────────────────────────────────────────────────────────

def scene_to_svg(scene: SvgScene, *, validate: bool = True) -> bytes:
    """Serialize an SvgScene to UTF-8 SVG bytes.

    Deterministic: same scene → byte-identical output.
    """
    if validate:
        validate_scene(scene)

    vb = scene.view_box
    vb_str = f"{_fmt(vb[0])} {_fmt(vb[1])} {_fmt(vb[2])} {_fmt(vb[3])}"

    root = etree.Element(
        f"{{{SVG_NS}}}svg",
        nsmap={None: SVG_NS, "xlink": XLINK_NS},
    )
    root.set("width", _fmt(scene.width))
    root.set("height", _fmt(scene.height))
    root.set("viewBox", vb_str)
    root.set("role", scene.accessibility.role or "graphics-document document")
    if scene.accessibility.aria_label:
        root.set("aria-label", scene.accessibility.aria_label)
    elif scene.accessibility.title:
        root.set("aria-label", scene.accessibility.title)
    root.set("aria-roledescription", scene.diagram_type)
    root.set("data-diagram-type", scene.diagram_type)

    # <title>
    if scene.accessibility.title:
        title_el = etree.SubElement(root, "title")
        title_el.text = scene.accessibility.title

    # <desc>
    if scene.accessibility.description:
        desc_el = etree.SubElement(root, "desc")
        desc_el.text = scene.accessibility.description

    # <defs>
    if scene.definitions:
        defs = etree.SubElement(root, "defs")
        for defn in scene.definitions:
            if isinstance(defn, MarkerDefinition):
                _ser_marker(defn, defs)
            elif isinstance(defn, LinearGradientDefinition):
                _ser_linear_gradient(defn, defs)
            elif isinstance(defn, RadialGradientDefinition):
                _ser_radial_gradient(defn, defs)
            elif isinstance(defn, ClipPathDefinition):
                _ser_clip_path(defn, defs)

    # Paint layers in canonical order
    layers_by_name = {name: elems for name, elems in scene.layers}
    for layer_name in LAYER_ORDER:
        elements = layers_by_name.get(layer_name, ())
        if not elements:
            continue
        layer_g = etree.SubElement(root, "g")
        layer_g.set("id", f"layer-{layer_name}")
        layer_g.set("class", f"layer {layer_name}")
        for elem in elements:
            _ser_element(elem, layer_g)

    return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)


def scene_to_svg_str(scene: SvgScene, *, validate: bool = True) -> str:
    """Serialize to a UTF-8 string."""
    return scene_to_svg(scene, validate=validate).decode("utf-8")
