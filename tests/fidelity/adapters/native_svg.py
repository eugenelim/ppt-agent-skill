"""Native SVG adapter: exercises the public mermaid_render.to_svg() path.

Primary authoritative adapter for the Phase 1 fidelity harness.
Extracts semantics and geometry directly from the native SVG output via
XML parsing — no browser required for the semantic lane.
"""
from __future__ import annotations

import datetime
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "scripts"))

from mermaid_render import to_svg

sys.path.insert(0, str(_REPO / "tools"))

from mermaid_fidelity.models import (
    BoundingBox,
    ComparisonStatus,
    Entity,
    EntityGeometry,
    EnvironmentIdentity,
    FidelityCase,
    GeometryObservation,
    Group,
    GroupGeometry,
    ImplementationIdentity,
    Observation,
    ParseObservation,
    QualityObservation,
    Relation,
    RelationGeometry,
    RenderProfile,
    SemanticDiagram,
)

_ADAPTER_VERSION = "1.0.0"
_SVG_NS = "http://www.w3.org/2000/svg"
_NS = {"svg": _SVG_NS}

# Register default namespace to avoid ns0: prefixes in output
ET.register_namespace("", _SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def _impl_version() -> str:
    try:
        import mermaid_render
        return getattr(mermaid_render, "__version__", "unknown")
    except Exception:
        return "unknown"


def _impl_integrity() -> str | None:
    try:
        key_files = [
            _REPO / "scripts" / "mermaid_render" / "native_svg.py",
            _REPO / "scripts" / "mermaid_render" / "svg_serializer.py",
            _REPO / "scripts" / "mermaid_render" / "layout" / "_renderer.py",
        ]
        h = hashlib.sha256()
        for p in key_files:
            if p.exists():
                h.update(p.read_bytes())
        return h.hexdigest()[:16]
    except Exception:
        return None


def _env_identity(profile: RenderProfile) -> EnvironmentIdentity:
    css_hash = ""
    if profile.css_path and profile.css_path.exists():
        css_hash = hashlib.sha256(profile.css_path.read_bytes()).hexdigest()[:16]

    cfg_hash = ""
    if profile.mermaid_config:
        import json
        cfg_hash = hashlib.sha256(
            json.dumps(profile.mermaid_config, sort_keys=True).encode()
        ).hexdigest()[:16]

    return EnvironmentIdentity(
        mermaid_version="n/a (native renderer — no mermaid.js)",
        mermaid_integrity=None,
        playwright_version="n/a",
        chromium_revision="n/a",
        viewport_width=profile.viewport_width,
        viewport_height=profile.viewport_height,
        device_scale_factor=profile.device_scale_factor,
        locale=profile.locale,
        timezone=profile.timezone,
        reduced_motion=profile.reduced_motion,
        mermaid_config_hash=cfg_hash,
        css_profile_hash=css_hash,
        font_info={"requested": "Helvetica Neue, Helvetica, Arial, sans-serif"},
    )


def _classify_error(msg: str) -> str:
    msg_lower = msg.lower()
    if "unsupported" in msg_lower:
        return "unsupported_diagram_type"
    if "parse" in msg_lower or "syntax" in msg_lower:
        return "parse_error"
    return "render_error"


def _attr(el: ET.Element, name: str) -> str | None:
    """Get an attribute value without namespace prefix."""
    return el.get(name)


def _text_content(el: ET.Element) -> str:
    """Get concatenated text content of tspan children or element text."""
    parts = []
    if el.text:
        parts.append(el.text.strip())
    for child in el:
        if child.text:
            parts.append(child.text.strip())
        if child.tail:
            t = child.tail.strip()
            if t:
                parts.append(t)
    return " ".join(p for p in parts if p)


def _extract_semantic_from_svg(svg_text: str, diagram_type: str) -> SemanticDiagram:
    """Extract SemanticDiagram from the native SVG output via XML parsing."""
    import html as _html_lib

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return SemanticDiagram(diagram_type=diagram_type, direction=None,
                               entities=[], relations=[], groups=[])

    # Use manifest diagram_type as canonical (case.diagram is the authority);
    # SVG's data-diagram-type may use internal names like "sequencediagram"/"erdiagram"
    actual_type = diagram_type
    direction = root.get("data-direction")

    # Collect all elements with data-* attributes
    entities: list[Entity] = []
    relations: list[Relation] = []
    groups_list: list[Group] = []

    seen_node_ids: set[str] = set()
    seen_rel_ids: set[str] = set()
    seen_group_ids: set[str] = set()

    # Build label map: data-node-id → label text (from label layer text elements)
    label_map: dict[str, str] = {}
    for el in root.iter():
        nid = el.get("data-node-id")
        if nid and el.tag.endswith("}text") or el.tag == "text":
            t = _text_content(el)
            if t and nid:
                # Prefer first occurrence (may be overwritten by closer text)
                label_map.setdefault(_html_lib.unescape(nid), t)

    # Build group-member map from containment relationships
    group_member_map: dict[str, list[str]] = {}

    # Walk all elements extracting semantic annotations
    order = 0
    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag

        # Nodes: any shape element with data-node-id
        nid_raw = el.get("data-node-id")
        if nid_raw and tag not in ("text", "tspan"):
            nid = _html_lib.unescape(nid_raw)
            if nid and nid not in seen_node_ids:
                seen_node_ids.add(nid)
                label = label_map.get(nid, nid)
                # Shape from data-semantic-id / data-shape (T4) or CSS class
                shape = el.get("data-shape")
                if not shape:
                    css = el.get("class", "")
                    for css_part in css.split():
                        if css_part.startswith("node-") and css_part != "node":
                            shape = css_part[5:]
                            break
                    if not shape:
                        shape = _infer_shape_from_tag(tag)
                kind = el.get("data-kind") or "node"
                parent_id = el.get("data-parent-id")
                try:
                    node_order = int(el.get("data-order") or order)
                except (ValueError, TypeError):
                    node_order = order
                semantic_id = el.get("data-semantic-id") or nid
                entities.append(Entity(
                    id=semantic_id,
                    kind=kind,
                    label=_html_lib.unescape(el.get("data-label") or label),
                    shape=shape,
                    parent_id=_html_lib.unescape(parent_id) if parent_id else None,
                    order=node_order,
                ))
                order += 1
                if parent_id:
                    gid = _html_lib.unescape(parent_id)
                    group_member_map.setdefault(gid, []).append(semantic_id)

        # Edges: path/line elements with data-src and data-dst
        src_raw = el.get("data-src")
        dst_raw = el.get("data-dst")
        if src_raw and dst_raw and tag in ("path", "line", "polyline"):
            src = _html_lib.unescape(src_raw)
            dst = _html_lib.unescape(dst_raw)
            rel_id_raw = el.get("data-relation-id") or f"{src}__{dst}__{len(relations)}"
            rel_id = _html_lib.unescape(rel_id_raw)
            if rel_id not in seen_rel_ids:
                seen_rel_ids.add(rel_id)
                arrow = el.get("data-arrow")
                rel_kind = el.get("data-relation-kind") or "edge"
                label_raw = el.get("data-label") or ""
                relations.append(Relation(
                    id=rel_id,
                    kind=rel_kind,
                    source=src,
                    target=dst,
                    label=_html_lib.unescape(label_raw),
                    arrow=arrow,
                    order=len(relations),
                ))

        # Groups: elements with data-group-id
        gid_raw = el.get("data-group-id")
        if gid_raw and tag != "text":
            gid = _html_lib.unescape(gid_raw)
            if gid not in seen_group_ids:
                seen_group_ids.add(gid)
                glabel_raw = el.get("data-group-label") or gid
                parent_gid = el.get("data-parent-id")
                members = group_member_map.get(gid, [])
                groups_list.append(Group(
                    id=gid,
                    kind="subgraph",
                    label=_html_lib.unescape(glabel_raw),
                    parent_id=_html_lib.unescape(parent_gid) if parent_gid else None,
                    order=len(groups_list),
                    members=members,
                ))

    # Back-fill group members from entity parent_ids if group membership not found
    for entity in entities:
        if entity.parent_id:
            gid = entity.parent_id
            if gid in seen_group_ids:
                # Find the group and add this entity to its members if not already there
                for g in groups_list:
                    if g.id == gid and entity.id not in g.members:
                        g.members.append(entity.id)

    return SemanticDiagram(
        diagram_type=actual_type,
        direction=direction,
        entities=entities,
        relations=relations,
        groups=groups_list,
    )


def _infer_shape_from_tag(tag: str) -> str:
    return {
        "rect": "rect",
        "circle": "circle",
        "ellipse": "ellipse",
        "polygon": "diamond",
        "path": "rect",
    }.get(tag, "rect")


def _extract_geometry_from_svg(svg_text: str) -> GeometryObservation | None:
    """Extract basic geometry from the SVG using XML coordinate parsing."""
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return None

    width = float(root.get("width") or 0)
    height = float(root.get("height") or 0)
    viewbox_str = root.get("viewBox")

    canvas_bounds = BoundingBox(x=0, y=0, width=width, height=height) if width and height else None

    entities_geo: list[EntityGeometry] = []
    groups_geo: list[GroupGeometry] = []
    seen_node_ids: set[str] = set()
    seen_group_ids: set[str] = set()

    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag

        nid = el.get("data-node-id")
        if nid and tag not in ("text", "tspan", "g"):
            if nid not in seen_node_ids:
                seen_node_ids.add(nid)
                bbox = _element_bbox(el, tag)
                if bbox:
                    entities_geo.append(EntityGeometry(
                        entity_id=nid,
                        bbox=bbox,
                        text_bbox=None,
                        text_lines=1,
                    ))

        gid = el.get("data-group-id")
        if gid and tag in ("rect", "g"):
            if gid not in seen_group_ids:
                seen_group_ids.add(gid)
                bbox = _element_bbox(el, tag)
                if bbox:
                    groups_geo.append(GroupGeometry(group_id=gid, bbox=bbox))

    # Content bounds: union of all entity + group bboxes
    all_bboxes = [eg.bbox for eg in entities_geo] + [gg.bbox for gg in groups_geo]
    if all_bboxes:
        min_x = min(b.x for b in all_bboxes)
        min_y = min(b.y for b in all_bboxes)
        max_x = max(b.x + b.width for b in all_bboxes)
        max_y = max(b.y + b.height for b in all_bboxes)
        content_bounds = BoundingBox(x=min_x, y=min_y,
                                     width=max_x - min_x, height=max_y - min_y)
    else:
        content_bounds = None

    return GeometryObservation(
        coordinate_convention="css-top-left",
        content_bounds=content_bounds,
        canvas_bounds=canvas_bounds,
        viewbox=viewbox_str,
        entities=entities_geo,
        groups=groups_geo,
        relations=[],
        containment=[],
    )


def _element_bbox(el: ET.Element, tag: str) -> BoundingBox | None:
    """Extract bounding box from common SVG shape elements."""
    try:
        if tag == "rect":
            x = float(el.get("x") or 0)
            y = float(el.get("y") or 0)
            w = float(el.get("width") or 0)
            h = float(el.get("height") or 0)
            if w > 0 and h > 0:
                return BoundingBox(x=x, y=y, width=w, height=h)
        elif tag == "circle":
            cx = float(el.get("cx") or 0)
            cy = float(el.get("cy") or 0)
            r = float(el.get("r") or 0)
            if r > 0:
                return BoundingBox(x=cx - r, y=cy - r, width=2 * r, height=2 * r)
        elif tag == "ellipse":
            cx = float(el.get("cx") or 0)
            cy = float(el.get("cy") or 0)
            rx = float(el.get("rx") or 0)
            ry = float(el.get("ry") or 0)
            if rx > 0 and ry > 0:
                return BoundingBox(x=cx - rx, y=cy - ry, width=2 * rx, height=2 * ry)
        elif tag == "polygon":
            pts_str = el.get("points") or ""
            pts = []
            for pair in pts_str.split():
                xy = pair.split(",")
                if len(xy) == 2:
                    pts.append((float(xy[0]), float(xy[1])))
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                x, y = min(xs), min(ys)
                w, h = max(xs) - x, max(ys) - y
                if w > 0 and h > 0:
                    return BoundingBox(x=x, y=y, width=w, height=h)
    except (ValueError, TypeError):
        pass
    return None


class NativeSvgAdapter:
    """Fidelity adapter for the native scripts/mermaid_render/ renderer.

    Primary authoritative target: calls to_svg() and extracts semantics
    from data-* annotations on the emitted SVG via pure XML parsing.
    No browser required for the semantic observation lane.
    """

    def identity(self) -> ImplementationIdentity:
        return ImplementationIdentity(
            name="mermaid_render_svg",
            version=_impl_version(),
            integrity=_impl_integrity(),
            adapter_version=_ADAPTER_VERSION,
            profile_id="native-production",
        )

    def observe(self, case: FidelityCase, profile: RenderProfile) -> Observation:
        impl = ImplementationIdentity(
            name="mermaid_render_svg",
            version=_impl_version(),
            integrity=_impl_integrity(),
            adapter_version=_ADAPTER_VERSION,
            profile_id=profile.id,
        )
        env = _env_identity(profile)

        try:
            svg_text = to_svg(case.source)
        except ValueError as e:
            return Observation(
                schema_version=1,
                case_id=case.id,
                implementation=impl,
                environment=env,
                parse_result=ParseObservation(
                    accepted=False,
                    diagram_type=None,
                    error_category=_classify_error(str(e)),
                    source_position=None,
                ),
                semantic=None,
                geometry=None,
                quality=None,
                status=ComparisonStatus.NATIVE_UNSUPPORTED,
                reason=f"ValueError: {str(e)[:120]}",
            )
        except Exception as e:
            return Observation(
                schema_version=1,
                case_id=case.id,
                implementation=impl,
                environment=env,
                parse_result=ParseObservation(
                    accepted=False,
                    diagram_type=None,
                    error_category="internal_error",
                    source_position=None,
                ),
                semantic=None,
                geometry=None,
                quality=None,
                status=ComparisonStatus.INTERNAL_ERROR,
                reason=f"{type(e).__name__}: {str(e)[:120]}",
            )

        # Detect mechanical stub — native renderer doesn't support this type yet
        if "mechanical stub" in svg_text:
            return Observation(
                schema_version=1,
                case_id=case.id,
                implementation=impl,
                environment=env,
                parse_result=ParseObservation(
                    accepted=False,
                    diagram_type=case.diagram,
                    error_category="unsupported_diagram_type",
                    source_position=None,
                ),
                semantic=None,
                geometry=None,
                quality=None,
                status=ComparisonStatus.NATIVE_UNSUPPORTED,
                reason=f"diagram type '{case.diagram}' not yet implemented in native renderer",
                capture_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )

        semantic = _extract_semantic_from_svg(svg_text, case.diagram)
        parse_obs = ParseObservation(
            accepted=True,
            diagram_type=case.diagram,
            error_category=None,
            source_position=None,
        )

        geometry = _extract_geometry_from_svg(svg_text)

        return Observation(
            schema_version=1,
            case_id=case.id,
            implementation=impl,
            environment=env,
            parse_result=parse_obs,
            semantic=semantic,
            geometry=geometry,
            quality=QualityObservation(findings=[]),
            status=ComparisonStatus.PASS,
            reason=None,
            artifact_refs={"svg": f"native_{case.id}.svg"},
            capture_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
