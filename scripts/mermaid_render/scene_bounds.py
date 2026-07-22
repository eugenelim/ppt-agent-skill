"""mermaid_render.scene_bounds — Visible-bounds computation and validation for SvgScene.

Keeps geometry computation out of scene.py per that module's contract.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .scene import (
    SceneCircle,
    SceneEllipse,
    SceneGroup,
    SceneImage,
    SceneLine,
    ScenePath,
    ScenePolygon,
    ScenePolyline,
    SceneRect,
    SceneRoundedRect,
    SceneText,
    SvgScene,
)
from .layout._geometry import Point, Rect


# ── Transform parsing ─────────────────────────────────────────────────────────

_TRANSLATE_RE = re.compile(
    r"^\s*translate\(\s*([+-]?\d*\.?\d+)\s*[, ]\s*([+-]?\d*\.?\d+)\s*\)\s*$"
)
_TRANSLATE_1_RE = re.compile(r"^\s*translate\(\s*([+-]?\d*\.?\d+)\s*\)\s*$")


def _parse_translate(transform_str: str) -> Tuple[float, float]:
    """Extract (dx, dy) from a 'translate(dx, dy)' transform string.

    Returns (0.0, 0.0) for empty strings and unrecognised transforms.
    Only translate() is parsed; rotate/scale/matrix are treated as identity.
    """
    if not transform_str:
        return (0.0, 0.0)
    m = _TRANSLATE_RE.match(transform_str)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    m2 = _TRANSLATE_1_RE.match(transform_str)
    if m2:
        return (float(m2.group(1)), 0.0)
    return (0.0, 0.0)


# ── Bounds per element type ───────────────────────────────────────────────────

def element_visible_bounds(
    element: object,
    definitions: tuple = (),
) -> Optional[Rect]:
    """Return an axis-aligned bounding rect for a single scene element.

    Returns None for elements with no visible geometry (empty text, zero-radius
    circles, paths with no commands, etc.).

    Conservative for curves: bezier control points are included in the hull, so
    the returned rect may be slightly larger than the rendered ink.

    Transform handling: only translate(dx, dy) is parsed; other transform types
    are treated as identity (bounds are reported in the element's untransformed
    coordinate space for non-translate transforms).
    """
    dx, dy = _parse_translate(getattr(element, "transform", ""))

    if isinstance(element, (SceneRect, SceneRoundedRect)):
        return Rect(element.x + dx, element.y + dy, element.w, element.h)

    if isinstance(element, SceneImage):
        if not element.href:
            return None
        return Rect(element.x + dx, element.y + dy, element.w, element.h)

    if isinstance(element, SceneCircle):
        if element.r <= 0:
            return None
        return Rect(element.cx - element.r + dx, element.cy - element.r + dy,
                    2 * element.r, 2 * element.r)

    if isinstance(element, SceneEllipse):
        if element.rx <= 0 or element.ry <= 0:
            return None
        return Rect(element.cx - element.rx + dx, element.cy - element.ry + dy,
                    2 * element.rx, 2 * element.ry)

    if isinstance(element, SceneLine):
        pts = [Point(element.x1 + dx, element.y1 + dy),
               Point(element.x2 + dx, element.y2 + dy)]
        return Rect.from_points(pts)

    if isinstance(element, (ScenePolyline, ScenePolygon)):
        if not element.points:
            return None
        pts = [Point(x + dx, y + dy) for x, y in element.points]
        return Rect.from_points(pts)

    if isinstance(element, ScenePath):
        coords = _path_control_points(element)
        if not coords:
            return None
        pts = [Point(x + dx, y + dy) for x, y in coords]
        return Rect.from_points(pts)

    if isinstance(element, SceneText):
        return _text_bounds(element, dx, dy)

    if isinstance(element, SceneGroup):
        child_rects: List[Rect] = []
        for child in element.children:
            b = element_visible_bounds(child, definitions)
            if b is not None:
                child_rects.append(b)
        if not child_rects:
            return None
        union = Rect.union_all(child_rects)
        return union.translate(dx, dy) if (dx or dy) else union

    return None


def _path_control_points(path: ScenePath) -> List[Tuple[float, float]]:
    """Collect all coordinates from a ScenePath (including bezier control points)."""
    coords: List[Tuple[float, float]] = []
    for cmd in path.commands:
        letter = cmd[0]
        if letter in ("M", "L"):
            coords.append((cmd[1], cmd[2]))
        elif letter == "C":
            coords.extend([(cmd[1], cmd[2]), (cmd[3], cmd[4]), (cmd[5], cmd[6])])
        elif letter == "Q":
            coords.extend([(cmd[1], cmd[2]), (cmd[3], cmd[4])])
        elif letter == "A":
            coords.append((cmd[6], cmd[7]))
        # "Z" has no coordinates
    return coords


def _text_bounds(text: SceneText, dx: float, dy: float) -> Optional[Rect]:
    """Estimate bounding rect for a SceneText block."""
    rects: List[Rect] = []
    anchor = text.text_anchor
    for line in text.lines:
        if not line.text:
            continue
        w = len(line.text) * line.font_size * 0.6
        h = line.font_size
        if anchor == "start":
            x_left = line.x
        elif anchor == "end":
            x_left = line.x - w
        else:
            x_left = line.x - w / 2
        rects.append(Rect(x_left + dx, line.y - h + dy, w, h * 1.2))
    if not rects:
        return None
    return Rect.union_all(rects)


# ── Scene-level bounds ────────────────────────────────────────────────────────

def scene_visible_bounds(scene: SvgScene) -> Optional[Rect]:
    """Return bounding rect enclosing all visible elements across all layers."""
    all_bounds: List[Rect] = []
    for _layer_name, elements in scene.layers:
        for elem in elements:
            b = element_visible_bounds(elem, scene.definitions)
            if b is not None:
                all_bounds.append(b)
    if not all_bounds:
        return None
    return Rect.union_all(all_bounds)


# ── Validation ────────────────────────────────────────────────────────────────

def validate_scene(scene: SvgScene) -> List[str]:
    """Return a list of structural error strings (empty list = valid).

    Checks:
    - Duplicate element_ids across all elements (empty id = unnamed, not checked)
    - Negative width/height on rect-like elements
    - Negative radius on circles/ellipses
    """
    errors: List[str] = []
    seen_ids: set = set()
    for _layer_name, elements in scene.layers:
        for elem in elements:
            _walk_ids(elem, seen_ids, errors)
            _check_negative_geometry(elem, errors)
    return errors


def _walk_ids(elem: object, seen: set, errors: List[str]) -> None:
    eid = getattr(elem, "element_id", "")
    if eid:
        if eid in seen:
            errors.append(f"Duplicate element_id: {eid!r}")
        else:
            seen.add(eid)
    if isinstance(elem, SceneGroup):
        for child in elem.children:
            _walk_ids(child, seen, errors)


def _check_negative_geometry(elem: object, errors: List[str]) -> None:
    if isinstance(elem, (SceneRect, SceneRoundedRect, SceneImage)):
        if elem.w < 0:
            errors.append(f"Negative width on {type(elem).__name__}: w={elem.w}")
        if elem.h < 0:
            errors.append(f"Negative height on {type(elem).__name__}: h={elem.h}")
    elif isinstance(elem, SceneCircle):
        if elem.r < 0:
            errors.append(f"Negative radius on SceneCircle: r={elem.r}")
    elif isinstance(elem, SceneEllipse):
        if elem.rx < 0:
            errors.append(f"Negative rx on SceneEllipse: rx={elem.rx}")
        if elem.ry < 0:
            errors.append(f"Negative ry on SceneEllipse: ry={elem.ry}")
    if isinstance(elem, SceneGroup):
        for child in elem.children:
            _check_negative_geometry(child, errors)
