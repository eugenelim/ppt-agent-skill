"""DOM/SVG extractor for browser geometry capture.

Parses rendered SVG text and extracts a ReferenceDiagram.
This module has NO browser dependency — it operates on SVG strings
that can be supplied in unit tests as synthetic input.

Key responsibilities:
- Coordinate normalization: resolve nested transforms, viewBox scaling,
  remove page offsets, preserve subpixel values.
- Node, group, edge, label, marker extraction.
- Class diagram marker resolution.
- ER cardinality normalization.
- State diagram symbol classification.
- Typed ExtractorGap diagnostics for unresolvable fields.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import field
from typing import Any

from tools.mermaid_fidelity.models import (
    BoundingBox,
    CardinalityEnd,
    ComparisonStatus,
    ExtractorGap,
    ReferenceEdge,
    ReferenceGroup,
    ReferenceLabel,
    ReferenceMarker,
    ReferenceDiagram,
    ReferenceNode,
    ReferenceProvenance,
    StateSymbolKind,
)

# SVG namespace
_SVG_NS = "http://www.w3.org/2000/svg"

# Placeholder provenance used when no external provenance is supplied
_NULL_PROVENANCE = ReferenceProvenance(
    mermaid_version="unknown",
    mmdc_version="unknown",
    node_version="unknown",
    playwright_version="unknown",
    chromium_version="unknown",
    platform="unknown",
    font_families=[],
    font_fingerprint="",
    fixture_source_hash="",
    render_config_hash="",
)


# ── transform parsing ──────────────────────────────────────────────────────────

class _Transform:
    """Represents a composed 2D affine transform as a 3x3 matrix."""

    __slots__ = ("a", "b", "c", "d", "e", "f")

    def __init__(
        self, a: float = 1, b: float = 0, c: float = 0,
        d: float = 1, e: float = 0, f: float = 0,
    ) -> None:
        self.a, self.b, self.c, self.d, self.e, self.f = a, b, c, d, e, f

    @classmethod
    def identity(cls) -> "_Transform":
        return cls()

    def then(self, other: "_Transform") -> "_Transform":
        """Compose: apply self first, then other."""
        return _Transform(
            a=other.a * self.a + other.c * self.b,
            b=other.b * self.a + other.d * self.b,
            c=other.a * self.c + other.c * self.d,
            d=other.b * self.c + other.d * self.d,
            e=other.a * self.e + other.c * self.f + other.e,
            f=other.b * self.e + other.d * self.f + other.f,
        )

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def transform_bbox(self, bbox: BoundingBox) -> BoundingBox:
        """Transform a bounding box; handles arbitrary affine transforms."""
        corners = [
            self.apply(bbox.x, bbox.y),
            self.apply(bbox.x + bbox.width, bbox.y),
            self.apply(bbox.x, bbox.y + bbox.height),
            self.apply(bbox.x + bbox.width, bbox.y + bbox.height),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        x0, y0 = min(xs), min(ys)
        return BoundingBox(
            x=x0, y=y0,
            width=max(xs) - x0,
            height=max(ys) - y0,
        )


def _parse_transform_string(transform_str: str) -> _Transform:
    """Parse an SVG transform attribute string into a composed _Transform."""
    result = _Transform.identity()
    if not transform_str:
        return result

    # Match: translate(tx [, ty])  scale(sx [, sy])  matrix(a b c d e f)
    for m in re.finditer(
        r'(translate|scale|matrix|rotate)\s*\(([^)]*)\)',
        transform_str,
    ):
        func = m.group(1)
        args = [float(v) for v in re.split(r'[\s,]+', m.group(2).strip()) if v]
        if func == "translate":
            tx = args[0] if args else 0.0
            ty = args[1] if len(args) > 1 else 0.0
            t = _Transform(e=tx, f=ty)
        elif func == "scale":
            sx = args[0] if args else 1.0
            sy = args[1] if len(args) > 1 else sx
            t = _Transform(a=sx, d=sy)
        elif func == "rotate":
            angle = math.radians(args[0]) if args else 0.0
            cx = args[1] if len(args) > 1 else 0.0
            cy = args[2] if len(args) > 2 else 0.0
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            # Rotate around (cx, cy)
            t = _Transform(
                a=cos_a, b=sin_a, c=-sin_a, d=cos_a,
                e=cx - cos_a * cx + sin_a * cy,
                f=cy - sin_a * cx - cos_a * cy,
            )
        elif func == "matrix":
            if len(args) == 6:
                t = _Transform(*args)
            else:
                continue
        else:
            continue
        result = result.then(t)
    return result


def _collect_transform(element: ET.Element, tree: ET.ElementTree) -> _Transform:
    """Walk ancestors and compose all transform attributes into one."""
    chain: list[_Transform] = []

    # Build path from root to element
    def find_ancestors(root: ET.Element, target: ET.Element) -> list[ET.Element]:
        if root is target:
            return [root]
        for child in root:
            path = find_ancestors(child, target)
            if path:
                return [root] + path
        return []

    root = tree.getroot()
    path = find_ancestors(root, element)
    # Collect transforms from outermost to innermost
    for el in path:
        t_str = el.get("transform", "")
        if t_str:
            chain.append(_parse_transform_string(t_str))

    result = _Transform.identity()
    for t in chain:
        result = result.then(t)
    return result


# ── viewBox normalization ──────────────────────────────────────────────────────

def _parse_viewbox(svg_el: ET.Element) -> tuple[float, float, float, float] | None:
    """Parse the viewBox attribute; returns (vx, vy, vw, vh) or None."""
    vb = svg_el.get("viewBox") or svg_el.get("viewbox")
    if not vb:
        return None
    parts = [float(v) for v in re.split(r'[\s,]+', vb.strip()) if v]
    if len(parts) == 4:
        return tuple(parts)  # type: ignore[return-value]
    return None


def _viewbox_scale(svg_el: ET.Element) -> tuple[float, float]:
    """Return (sx, sy) to convert from viewBox coords to CSS pixel coords."""
    vb = _parse_viewbox(svg_el)
    if not vb:
        return (1.0, 1.0)
    _, _, vw, vh = vb

    def _parse_length(attr: str) -> float | None:
        val = svg_el.get(attr)
        if not val:
            return None
        # strip 'px' or '%'
        val = val.replace("px", "").replace("%", "").strip()
        try:
            return float(val)
        except ValueError:
            return None

    w = _parse_length("width")
    h = _parse_length("height")
    sx = (w / vw) if (w and vw) else 1.0
    sy = (h / vh) if (h and vh) else 1.0
    return sx, sy


# ── bbox extraction helpers ────────────────────────────────────────────────────

def _bbox_from_attrs(el: ET.Element) -> BoundingBox | None:
    """Extract bounding box from x/y/width/height attributes."""
    try:
        x = float(el.get("x", "0"))
        y = float(el.get("y", "0"))
        w = float(el.get("width", "0"))
        h = float(el.get("height", "0"))
        return BoundingBox(x=x, y=y, width=w, height=h)
    except (TypeError, ValueError):
        return None


def _bbox_from_rect(el: ET.Element) -> BoundingBox | None:
    """Extract bounding box from a <rect> element."""
    return _bbox_from_attrs(el)


def _bbox_from_circle(el: ET.Element) -> BoundingBox | None:
    """Extract bounding box from a <circle> element using cx/cy/r."""
    try:
        cx = float(el.get("cx", "0"))
        cy = float(el.get("cy", "0"))
        r = float(el.get("r", "0"))
        return BoundingBox(x=cx - r, y=cy - r, width=2 * r, height=2 * r)
    except (TypeError, ValueError):
        return None


def _bbox_from_ellipse(el: ET.Element) -> BoundingBox | None:
    """Extract bounding box from an <ellipse> element."""
    try:
        cx = float(el.get("cx", "0"))
        cy = float(el.get("cy", "0"))
        rx = float(el.get("rx", "0"))
        ry = float(el.get("ry", "0"))
        return BoundingBox(x=cx - rx, y=cy - ry, width=2 * rx, height=2 * ry)
    except (TypeError, ValueError):
        return None


def _best_bbox(el: ET.Element) -> BoundingBox | None:
    """Find the best bounding box for an element by trying different strategies."""
    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
    if tag == "rect":
        return _bbox_from_rect(el)
    if tag == "circle":
        return _bbox_from_circle(el)
    if tag == "ellipse":
        return _bbox_from_ellipse(el)
    # Fallback: use x/y/width/height attributes
    return _bbox_from_attrs(el)


# ── marker resolution ──────────────────────────────────────────────────────────

# CSS class → marker kind mapping for Mermaid class diagrams
_CLASS_MARKER_MAP: dict[str, str] = {
    "marker-extension": "hollow_triangle",
    "marker-composition": "filled_diamond",
    "marker-aggregation": "hollow_diamond",
    "marker-dependency": "open_arrow",
    "marker-association": "open_arrow",
    "marker-realization": "hollow_triangle",
}

# href/id patterns → marker kind
_MARKER_ID_PATTERNS: list[tuple[str, str]] = [
    (r"extensionStart|extensionEnd|Extension", "hollow_triangle"),
    (r"compositionStart|compositionEnd|Composition|filled.?diamond", "filled_diamond"),
    (r"aggregationStart|aggregationEnd|Aggregation|hollow.?diamond", "hollow_diamond"),
    (r"dependencyStart|dependencyEnd|Dependency|open.?arrow|Arrow", "open_arrow"),
    (r"associationStart|associationEnd|Association", "open_arrow"),
    (r"realizationStart|realizationEnd|Realization", "hollow_triangle"),
    (r"arrow_cross|cross", "none"),
    (r"arrow_point|pointEnd|pointStart", "open_arrow"),
]


def _resolve_marker_kind(marker_ref: str, defs_map: dict[str, ET.Element]) -> str:
    """Resolve a marker href/id reference to a canonical marker kind."""
    # Strip url(#...) wrapper — handles url(#id), url('#id'), url("#id")
    marker_id = marker_ref.strip()
    # Match url(#id), url('#id'), url("#id") forms
    m = re.match(r"""url\(['"]?#([^'")]+)['"]?\)""", marker_id)
    if m:
        marker_id = m.group(1)
    else:
        # Already a bare id or #id
        marker_id = marker_id.lstrip("#")
    marker_id = marker_id.strip("'\"")

    # Look up in defs
    el = defs_map.get(marker_id)
    if el is not None:
        css_class = el.get("class", "")
        for cls, kind in _CLASS_MARKER_MAP.items():
            if cls in css_class:
                return kind

    # Pattern match on the id string
    for pattern, kind in _MARKER_ID_PATTERNS:
        if re.search(pattern, marker_id, re.IGNORECASE):
            return kind

    return "open_arrow"  # conservative default


# ── cardinality parsing ────────────────────────────────────────────────────────

_CARDINALITY_TEXT_MAP: dict[str, CardinalityEnd] = {
    "1": CardinalityEnd(minimum="ONE", maximum="ONE"),
    "0..1": CardinalityEnd(minimum="ZERO", maximum="ONE"),
    "1..*": CardinalityEnd(minimum="ONE", maximum="MANY"),
    "0..*": CardinalityEnd(minimum="ZERO", maximum="MANY"),
    "*": CardinalityEnd(minimum="ZERO", maximum="MANY"),
    "one or more": CardinalityEnd(minimum="ONE", maximum="MANY"),
    "zero or more": CardinalityEnd(minimum="ZERO", maximum="MANY"),
    "one and only one": CardinalityEnd(minimum="ONE", maximum="ONE"),
    "zero or one": CardinalityEnd(minimum="ZERO", maximum="ONE"),
    "only one": CardinalityEnd(minimum="ONE", maximum="ONE"),
}


def _parse_cardinality(text: str) -> CardinalityEnd | None:
    """Parse an ER cardinality text to a CardinalityEnd, or None."""
    text = text.strip()
    result = _CARDINALITY_TEXT_MAP.get(text)
    if result:
        return result
    # Try normalized forms
    normalized = text.lower().replace(" ", "")
    for key, val in _CARDINALITY_TEXT_MAP.items():
        if key.lower().replace(" ", "") == normalized:
            return val
    return None


# ── state symbol classification ────────────────────────────────────────────────

def _classify_state_symbol(el: ET.Element, tree: ET.ElementTree) -> StateSymbolKind | None:
    """Classify a state diagram element into a StateSymbolKind.

    Classification rules (from Mermaid SVG patterns):
    - initial: <circle> with class containing "start" or fill=black
    - final: concentric rings (<circle> inside a <circle>) or class "end"
    - composite: <rect class="cluster-rect"> with child elements
    - composite_boundary: fork/join bar (<rect> with aspect ratio >> 1 and fill)
    - simple: <rect class="node-rect"> or default rounded-rect without children
    """
    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
    css_class = el.get("class", "")

    if tag == "circle":
        # Check for initial (filled black circle)
        fill = el.get("fill", "")
        if "start" in css_class or fill in ("#000", "#000000", "black"):
            return StateSymbolKind.INITIAL
        # Check for final (concentric rings / end class)
        if "end" in css_class:
            return StateSymbolKind.FINAL
        # Check if this circle is inside another circle (concentric rings)
        parent = _find_parent(el, tree)
        if parent is not None:
            p_tag = parent.tag.split("}")[-1] if "}" in parent.tag else parent.tag
            if p_tag == "circle":
                return StateSymbolKind.FINAL
        return None

    if tag == "rect":
        w_str = el.get("width", "0")
        h_str = el.get("height", "0")
        try:
            w, h = float(w_str), float(h_str)
        except ValueError:
            w, h = 0.0, 0.0

        # Fork/join bar: very wide and short (aspect ratio > 5:1)
        if h > 0 and w / h > 5:
            return StateSymbolKind.COMPOSITE_BOUNDARY

        # Composite: cluster rect with children
        if "cluster" in css_class or "composite" in css_class:
            return StateSymbolKind.COMPOSITE

        # Simple node
        return StateSymbolKind.SIMPLE

    return None


def _find_parent(element: ET.Element, tree: ET.ElementTree) -> ET.Element | None:
    """Find the parent of an element in the tree."""
    root = tree.getroot()
    for el in root.iter():
        if element in list(el):
            return el
    return None


# ── path sampling ──────────────────────────────────────────────────────────────

def _sample_path_points(path_d: str, n_samples: int = 16) -> list[tuple[float, float]]:
    """Extract sample points from a path 'd' attribute.

    Extracts coordinate pairs from M, L, C, Q, T commands for a simple
    approximation. Does not fully interpolate Bezier curves but captures
    the control points which bound the path.
    """
    points: list[tuple[float, float]] = []
    # Match coordinate pairs after command letters
    for m in re.finditer(
        r'[MLCQTSAHVZmlcqtsahvz]\s*((?:[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?\s*,?\s*)+)',
        path_d,
    ):
        nums = [float(v) for v in re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', m.group(1))]
        # Pairs
        for i in range(0, len(nums) - 1, 2):
            points.append((nums[i], nums[i + 1]))

    # Downsample if needed
    if len(points) > n_samples:
        step = len(points) / n_samples
        points = [points[int(i * step)] for i in range(n_samples)]
    return points


# ── namespace helpers ──────────────────────────────────────────────────────────

def _tag(local: str) -> str:
    return f"{{{_SVG_NS}}}{local}"


def _iter_ns(root: ET.Element, local: str):
    return root.iter(_tag(local))


def _find_all_ns(root: ET.Element, local: str) -> list[ET.Element]:
    return list(root.iter(_tag(local)))


# ── main extractor ─────────────────────────────────────────────────────────────

def extract_diagram(
    svg_text: str,
    fixture_stem: str = "",
    diagram_type: str = "unknown",
    provenance: ReferenceProvenance | None = None,
) -> ReferenceDiagram:
    """Extract a ReferenceDiagram from rendered SVG text.

    Args:
        svg_text: Raw SVG string from the browser renderer.
        fixture_stem: Identifier for the source fixture (e.g. "flowchart-basic").
        diagram_type: Diagram type hint ("flowchart", "er", "class", "state", …).
        provenance: Pre-recorded toolchain provenance; uses a null provenance
            if not supplied (for unit testing without browser).

    Returns:
        ReferenceDiagram with all extracted fields. Fields that cannot be
        extracted produce an ExtractorGap in ReferenceDiagram.gaps.
    """
    if provenance is None:
        provenance = _NULL_PROVENANCE

    gaps: list[ExtractorGap] = []

    # Parse SVG
    try:
        root = ET.fromstring(svg_text)
        tree = ET.ElementTree(root)
    except ET.ParseError as exc:
        return ReferenceDiagram(
            fixture_stem=fixture_stem,
            diagram_type=diagram_type,
            canvas_bounds=BoundingBox(x=0, y=0, width=0, height=0),
            view_box=None,
            provenance=provenance,
            gaps=[ExtractorGap(field="svg_parse", reason=str(exc))],
        )

    # Strip namespace for convenience
    svg_el = root

    # ── viewBox and canvas bounds ─────────────────────────────────────────────

    view_box_str = svg_el.get("viewBox") or svg_el.get("viewbox")
    sx, sy = _viewbox_scale(svg_el)

    canvas_w_str = svg_el.get("width")
    canvas_h_str = svg_el.get("height")
    try:
        canvas_w = float((canvas_w_str or "0").replace("px", "").replace("%", ""))
        canvas_h = float((canvas_h_str or "0").replace("px", "").replace("%", ""))
    except ValueError:
        canvas_w, canvas_h = 0.0, 0.0

    if canvas_w == 0 or canvas_h == 0:
        vb = _parse_viewbox(svg_el)
        if vb:
            _, _, vw, vh = vb
            canvas_w = canvas_w or vw
            canvas_h = canvas_h or vh

    canvas_bounds = BoundingBox(x=0, y=0, width=canvas_w, height=canvas_h)

    # ── collect defs (markers, etc.) ──────────────────────────────────────────

    defs_map: dict[str, ET.Element] = {}
    for defs_el in root.iter(_tag("defs")):
        for child in defs_el:
            el_id = child.get("id")
            if el_id:
                defs_map[el_id] = child

    # Also collect top-level elements with IDs
    for el in root.iter():
        el_id = el.get("id")
        if el_id and el_id not in defs_map:
            defs_map[el_id] = el

    # ── extract nodes ─────────────────────────────────────────────────────────

    nodes: list[ReferenceNode] = []
    seen_node_ids: set[str] = set()

    for g_el in root.iter(_tag("g")):
        g_class = g_el.get("class", "")
        g_id = g_el.get("id", "")

        # Mermaid renders nodes as <g class="node ...">
        if "node" not in g_class and not g_id:
            continue

        # Find the primary shape within the group
        shape_el = None
        shape_kind = None
        for child in g_el:
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child_tag in ("rect", "circle", "ellipse", "polygon"):
                shape_el = child
                shape_kind = child_tag
                break

        if shape_el is None:
            continue

        bbox = _best_bbox(shape_el)
        if bbox is None:
            continue

        # Apply local transform chain
        transform = _collect_transform(shape_el, tree)
        bbox = transform.transform_bbox(bbox)

        # Scale by viewBox
        bbox = BoundingBox(
            x=bbox.x * sx, y=bbox.y * sy,
            width=bbox.width * sx, height=bbox.height * sy,
        )

        # Extract label
        label = ""
        for text_el in g_el.iter(_tag("text")):
            label = (text_el.text or "").strip()
            if label:
                break

        node_id = g_id or f"node-{len(nodes)}"
        if node_id in seen_node_ids:
            node_id = f"{node_id}-{len(nodes)}"
        seen_node_ids.add(node_id)

        # Determine transform chain strings
        t_chain = []
        for ancestor in root.iter():
            if shape_el in list(ancestor):
                t_str = ancestor.get("transform", "")
                if t_str:
                    t_chain.append(t_str)

        nodes.append(ReferenceNode(
            id=node_id,
            label=label,
            shape=shape_kind,
            kind=None,
            bbox=bbox,
            transform_chain=t_chain,
        ))

    # ── extract groups ────────────────────────────────────────────────────────

    groups: list[ReferenceGroup] = []

    for g_el in root.iter(_tag("g")):
        g_class = g_el.get("class", "")
        if "cluster" not in g_class and "subgraph" not in g_class:
            continue

        g_id = g_el.get("id", f"group-{len(groups)}")
        label = ""
        for text_el in g_el.iter(_tag("text")):
            label = (text_el.text or "").strip()
            if label:
                break

        # Get bbox from cluster rect
        g_bbox = BoundingBox(x=0, y=0, width=0, height=0)
        for rect_el in g_el:
            rect_tag = rect_el.tag.split("}")[-1] if "}" in rect_el.tag else rect_el.tag
            if rect_tag == "rect":
                bb = _bbox_from_rect(rect_el)
                if bb:
                    transform = _collect_transform(rect_el, tree)
                    bb = transform.transform_bbox(bb)
                    g_bbox = BoundingBox(
                        x=bb.x * sx, y=bb.y * sy,
                        width=bb.width * sx, height=bb.height * sy,
                    )
                    break

        groups.append(ReferenceGroup(
            id=g_id,
            label=label,
            bbox=g_bbox,
        ))

    # ── extract edges ─────────────────────────────────────────────────────────

    edges: list[ReferenceEdge] = []
    seen_edge_ids: set[str] = set()

    for path_el in root.iter(_tag("path")):
        path_class = path_el.get("class", "")
        # Mermaid edge paths have class containing "edge" or "flowchart-link"
        if "edge" not in path_class and "link" not in path_class and "relation" not in path_class:
            continue

        path_d = path_el.get("d", "")
        if not path_d:
            continue

        # Edge ID from element id or class
        edge_id = path_el.get("id", "")
        if not edge_id:
            # Try to derive from class: e.g. "edgePaths edge-A-B"
            for cls_part in path_class.split():
                if cls_part.startswith("edge-") or cls_part.startswith("LS-"):
                    edge_id = cls_part
                    break
        if not edge_id:
            edge_id = f"edge-{len(edges)}"

        # Ensure uniqueness for parallel edges
        base_id = edge_id
        suffix = 0
        while edge_id in seen_edge_ids:
            suffix += 1
            edge_id = f"{base_id}-{suffix}"
        seen_edge_ids.add(edge_id)

        # Resolve source/target from data attributes or id patterns
        source = path_el.get("data-from", path_el.get("data-source", ""))
        target = path_el.get("data-to", path_el.get("data-target", ""))

        # Marker references
        marker_start_ref = path_el.get("marker-start", "")
        marker_end_ref = path_el.get("marker-end", "")

        marker_start = None
        if marker_start_ref:
            kind = _resolve_marker_kind(marker_start_ref, defs_map)
            marker_start = ReferenceMarker(
                marker_id=marker_start_ref,
                kind=kind,  # type: ignore[arg-type]
                edge_id=edge_id,
                end="start",
            )

        marker_end = None
        if marker_end_ref:
            kind = _resolve_marker_kind(marker_end_ref, defs_map)
            marker_end = ReferenceMarker(
                marker_id=marker_end_ref,
                kind=kind,  # type: ignore[arg-type]
                edge_id=edge_id,
                end="end",
            )

        # Stroke style
        style = path_el.get("style", "")
        stroke_width = 1.0
        dash_pattern = None
        for part in style.split(";"):
            part = part.strip()
            if part.startswith("stroke-width:"):
                try:
                    stroke_width = float(part.split(":")[1].replace("px", "").strip())
                except ValueError:
                    pass
            elif part.startswith("stroke-dasharray:"):
                dash_pattern = part.split(":")[1].strip() or None

        sampled = _sample_path_points(path_d)

        edges.append(ReferenceEdge(
            id=edge_id,
            source=source,
            target=target,
            path_data=path_d,
            sampled_points=sampled,
            stroke_width=stroke_width,
            dash_pattern=dash_pattern,
            marker_start=marker_start,
            marker_end=marker_end,
        ))

    # ── extract labels ────────────────────────────────────────────────────────

    labels: list[ReferenceLabel] = []

    for label_g in root.iter(_tag("g")):
        label_class = label_g.get("class", "")
        if "edgeLabel" not in label_class and "label" not in label_class:
            continue

        label_id = label_g.get("id", f"label-{len(labels)}")
        text_content = ""
        for text_el in label_g.iter(_tag("text")):
            text_content = (text_el.text or "").strip()
            if text_content:
                break

        if not text_content:
            continue

        # Get bbox from foreignObject or text element
        label_bbox = BoundingBox(x=0, y=0, width=0, height=0)
        for fo in label_g.iter(_tag("foreignObject")):
            bb = _bbox_from_attrs(fo)
            if bb:
                transform = _collect_transform(fo, tree)
                bb = transform.transform_bbox(bb)
                label_bbox = BoundingBox(
                    x=bb.x * sx, y=bb.y * sy,
                    width=bb.width * sx, height=bb.height * sy,
                )
                break

        labels.append(ReferenceLabel(
            id=label_id,
            text=text_content,
            bbox=label_bbox,
        ))

    # ── extract markers (class diagram) ───────────────────────────────────────

    markers: list[ReferenceMarker] = []

    for marker_el in defs_map.values():
        marker_tag = marker_el.tag.split("}")[-1] if "}" in marker_el.tag else marker_el.tag
        if marker_tag != "marker":
            continue
        marker_id = marker_el.get("id", "")
        if not marker_id:
            continue
        kind = _resolve_marker_kind(marker_id, defs_map)
        # Only record non-trivial markers
        if kind != "open_arrow":
            markers.append(ReferenceMarker(
                marker_id=marker_id,
                kind=kind,  # type: ignore[arg-type]
                edge_id="",
                end="end",
            ))

    return ReferenceDiagram(
        fixture_stem=fixture_stem,
        diagram_type=diagram_type,
        canvas_bounds=canvas_bounds,
        view_box=view_box_str,
        provenance=provenance,
        nodes=nodes,
        groups=groups,
        edges=edges,
        labels=labels,
        markers=markers,
        gaps=gaps,
    )


# ── coordinate normalization (standalone, for unit testing) ──────────────────

def normalize_coordinates(
    raw_bbox: BoundingBox,
    transform_str: str,
    viewbox_scale: tuple[float, float] = (1.0, 1.0),
) -> BoundingBox:
    """Normalize a bounding box by applying a transform string and viewBox scale.

    This is the unit-testable entry point for coordinate normalization.
    It applies the transform, then scales by the viewBox scaling factors.

    Args:
        raw_bbox: The raw bounding box in element-local coordinates.
        transform_str: SVG transform attribute string (may be composed).
        viewbox_scale: (sx, sy) scale factors from viewBox → CSS pixels.

    Returns:
        BoundingBox in the top-left coordinate system.
    """
    transform = _parse_transform_string(transform_str)
    bbox = transform.transform_bbox(raw_bbox)
    sx, sy = viewbox_scale
    return BoundingBox(
        x=bbox.x * sx, y=bbox.y * sy,
        width=bbox.width * sx, height=bbox.height * sy,
    )
