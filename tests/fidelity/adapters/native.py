"""Native adapter: observes scripts/mermaid_render/ output.

Uses the public to_html() API, then extracts semantics and geometry
from the actual emitted HTML via Playwright.
"""
from __future__ import annotations

import datetime
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

# Repository path setup — kept in this adapter, outside the reusable core.
_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "scripts"))

from mermaid_render import to_html

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
    QualityFinding,
    QualityFindingKind,
    QualityObservation,
    Relation,
    RelationGeometry,
    RenderProfile,
    SemanticDiagram,
)

_ADAPTER_VERSION = "1.0.0"

# Regex patterns matching the stable data-* attributes emitted by the renderer
_RE_NODE_ID = re.compile(r'data-node-id="([^"]*)"')
_RE_NODE_KIND = re.compile(r'data-kind="([^"]*)"')
_RE_NODE_LABEL = re.compile(r'data-label="([^"]*)"')
_RE_NODE_SHAPE = re.compile(r'data-shape="([^"]*)"')
_RE_NODE_PARENT = re.compile(r'data-parent-id="([^"]*)"')
_RE_NODE_ORDER = re.compile(r'data-order="([^"]*)"')

_RE_EDGE_SRC = re.compile(r'data-src="([^"]*)"')
_RE_EDGE_DST = re.compile(r'data-dst="([^"]*)"')
_RE_EDGE_LABEL = re.compile(r'data-edge-label="([^"]*)"')
_RE_EDGE_RELID = re.compile(r'data-relation-id="([^"]*)"')
_RE_EDGE_ARROW = re.compile(r'data-arrow="([^"]*)"')

_RE_DIAGRAM_W = re.compile(r'data-diagram-w="(\d+)"')
_RE_DIAGRAM_H = re.compile(r'data-diagram-h="(\d+)"')

_RE_GROUP_ID = re.compile(r'data-group-id="([^"]*)"')


def _impl_version() -> str:
    """Return a stable version string for the native renderer."""
    try:
        import mermaid_render
        return getattr(mermaid_render, "__version__", "unknown")
    except Exception:
        return "unknown"


def _impl_integrity() -> str | None:
    """SHA256 of key renderer files for change detection."""
    try:
        key_files = [
            _REPO / "scripts" / "mermaid_render" / "layout" / "_renderer.py",
            _REPO / "scripts" / "mermaid_render" / "layout" / "_strategies.py",
        ]
        h = hashlib.sha256()
        for p in key_files:
            if p.exists():
                h.update(p.read_bytes())
        return h.hexdigest()[:16]
    except Exception:
        return None


def _env_identity(profile: RenderProfile) -> EnvironmentIdentity:
    try:
        import playwright
        pw_version = getattr(playwright, "__version__", "unknown")
    except Exception:
        pw_version = "unavailable"

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
        playwright_version=pw_version,
        chromium_revision="1228",
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


class NativeAdapter:
    """Fidelity adapter for the native scripts/mermaid_render/ renderer.

    Extracts semantics from data-* annotations on the emitted HTML
    and geometry from the live DOM via Playwright.
    """

    def identity(self) -> ImplementationIdentity:
        return ImplementationIdentity(
            name="mermaid_render",
            version=_impl_version(),
            integrity=_impl_integrity(),
            adapter_version=_ADAPTER_VERSION,
            profile_id="native-production",
        )

    def observe(self, case: FidelityCase, profile: RenderProfile) -> Observation:
        impl = ImplementationIdentity(
            name="mermaid_render",
            version=_impl_version(),
            integrity=_impl_integrity(),
            adapter_version=_ADAPTER_VERSION,
            profile_id=profile.id,
        )
        env = _env_identity(profile)

        try:
            html_fragment = to_html(case.source)
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

        # Extract semantics from HTML annotations
        semantic = _extract_semantic_from_html(html_fragment, case.diagram)
        parse_obs = ParseObservation(
            accepted=True,
            diagram_type=case.diagram,
            error_category=None,
            source_position=None,
        )

        # Extract geometry via Playwright (when available)
        geometry: GeometryObservation | None = None
        quality_obs: QualityObservation | None = None

        try:
            geometry, quality_obs = _extract_geometry_and_quality(
                html_fragment, profile
            )
        except ImportError:
            pass  # Playwright not available — geometry skipped
        except Exception as e:
            pass  # Browser error — continue without geometry

        return Observation(
            schema_version=1,
            case_id=case.id,
            implementation=impl,
            environment=env,
            parse_result=parse_obs,
            semantic=semantic,
            geometry=geometry,
            quality=quality_obs,
            status=ComparisonStatus.PASS,
            reason=None,
            capture_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )


def _classify_error(msg: str) -> str:
    msg_lower = msg.lower()
    if "unsupported" in msg_lower:
        return "unsupported_diagram_type"
    if "parse" in msg_lower or "syntax" in msg_lower:
        return "parse_error"
    return "render_error"


def _extract_semantic_from_html(html: str, diagram_type: str) -> SemanticDiagram:
    """Extract semantic information from data-* attributes in rendered HTML."""
    import html as _html_lib

    entities: list[Entity] = []
    relations: list[Relation] = []
    groups_list: list[Group] = []

    # Extract nodes — scan line by line for data-node-id occurrences
    # Each occurrence may also have data-kind, data-label, data-shape, etc.
    node_pattern = re.compile(
        r'data-node-id="([^"]*)"'
        r'(?:[^>]*?data-kind="([^"]*)")?'
        r'(?:[^>]*?data-label="([^"]*)")?'
        r'(?:[^>]*?data-shape="([^"]*)")?'
        r'(?:[^>]*?data-order="([^"]*)")?'
        r'(?:[^>]*?data-parent-id="([^"]*)")?',
        re.DOTALL,
    )
    seen_node_ids: set[str] = set()
    for m in node_pattern.finditer(html):
        nid = _html_lib.unescape(m.group(1))
        if not nid or nid in seen_node_ids:
            continue
        seen_node_ids.add(nid)
        kind = m.group(2) or "node"
        label = _html_lib.unescape(m.group(3) or nid)
        shape = m.group(4) or "rect"
        try:
            order = int(m.group(5) or 0)
        except (ValueError, TypeError):
            order = 0
        parent_id = _html_lib.unescape(m.group(6)) if m.group(6) else None
        entities.append(Entity(
            id=nid,
            kind=kind,
            label=label,
            shape=shape,
            parent_id=parent_id,
            order=order,
        ))

    # Fall back to simple data-node-id scan if pattern missed anything
    for nid_raw in _RE_NODE_ID.findall(html):
        nid = _html_lib.unescape(nid_raw)
        if nid and nid not in seen_node_ids:
            seen_node_ids.add(nid)
            entities.append(Entity(id=nid, kind="node", label=nid, shape=None, parent_id=None, order=0))

    # Extract edges
    edge_pattern = re.compile(
        r'data-src="([^"]*)"[^>]*?data-dst="([^"]*)"'
        r'(?:[^>]*?data-edge-label="([^"]*)")?'
        r'(?:[^>]*?data-relation-id="([^"]*)")?'
        r'(?:[^>]*?data-arrow="([^"]*)")?',
        re.DOTALL,
    )
    seen_rel_ids: set[str] = set()
    rel_order = 0
    for m in edge_pattern.finditer(html):
        src = _html_lib.unescape(m.group(1))
        dst = _html_lib.unescape(m.group(2))
        if not src or not dst:
            continue
        label = _html_lib.unescape(m.group(3) or "")
        rel_id = _html_lib.unescape(m.group(4) or f"{src}__{dst}__{rel_order}")
        if rel_id in seen_rel_ids:
            continue
        seen_rel_ids.add(rel_id)
        arrow = m.group(5) or None
        relations.append(Relation(
            id=rel_id,
            kind="edge",
            source=src,
            target=dst,
            label=label,
            arrow=arrow,
            order=rel_order,
        ))
        rel_order += 1

    # Extract groups (data-group-id on group containers)
    group_pattern = re.compile(
        r'data-group-id="([^"]*)"[^>]*?'
        r'(?:data-group-label="([^"]*)")?',
        re.DOTALL,
    )
    seen_group_ids: set[str] = set()
    for m in group_pattern.finditer(html):
        gid = _html_lib.unescape(m.group(1))
        if not gid or gid in seen_group_ids:
            continue
        seen_group_ids.add(gid)
        glabel = _html_lib.unescape(m.group(2) or gid)
        # Collect members: entities with parent_id == gid
        members = [e.id for e in entities if e.parent_id == gid]
        groups_list.append(Group(
            id=gid,
            kind="subgraph",
            label=glabel,
            parent_id=None,
            order=len(groups_list),
            members=members,
        ))

    # Also reconstruct groups from entity parent_ids if no data-group-id found
    if not groups_list:
        parent_map: dict[str, list[str]] = {}
        for e in entities:
            if e.parent_id:
                parent_map.setdefault(e.parent_id, []).append(e.id)
        for gid, members in parent_map.items():
            if gid not in seen_group_ids:
                groups_list.append(Group(
                    id=gid,
                    kind="subgraph",
                    label=gid,
                    parent_id=None,
                    order=len(groups_list),
                    members=members,
                ))

    # Infer direction from data-diagram-* or HTML structure
    direction = _infer_direction_from_source_or_html(html)

    return SemanticDiagram(
        diagram_type=diagram_type,
        direction=direction,
        entities=entities,
        relations=relations,
        groups=groups_list,
    )


def _infer_direction_from_source_or_html(html: str) -> str | None:
    """Infer flowchart direction from the rendered HTML."""
    # data-direction if present (added in newer renderer versions)
    m = re.search(r'data-direction="([^"]*)"', html)
    if m:
        return m.group(1).upper()
    # Heuristic: look for direction in diagram header (first 200 chars of fragment)
    m = re.search(r'flowchart\s+(TB|LR|BT|RL|TD)\b', html[:500], re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def _extract_geometry_and_quality(
    html_fragment: str,
    profile: RenderProfile,
) -> tuple[GeometryObservation, QualityObservation]:
    """Extract geometry and quality from the live DOM via Playwright."""
    from playwright.sync_api import sync_playwright
    import tempfile
    import json as _json
    from pathlib import Path
    sys.path.insert(0, str(_REPO / "scripts"))
    from _browser import _setup_page, get_browser

    # Load native-neutral CSS if profile has one
    css_inject = ""
    if profile.css_path and profile.css_path.exists():
        css_inject = f"<style>{profile.css_path.read_text()}</style>"

    page_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body{{margin:0;padding:16px;background:white;}}
.slide-area{{width:{profile.viewport_width - 32}px;}}</style>
{css_inject}
</head><body><div class="slide-area">{html_fragment}</div></body></html>"""

    _DOM_GEO_JS = """() => {
        const canvas = document.querySelector('.diagram.mermaid-layout, .diagram-lifeline');
        if (!canvas) return {error: 'no canvas'};
        const cr = canvas.getBoundingClientRect();

        const nodes = {};
        document.querySelectorAll('[data-node-id]').forEach(el => {
            const id = el.getAttribute('data-node-id');
            if (!id) return;
            const r = el.getBoundingClientRect();
            nodes[id] = {x: r.left - cr.left, y: r.top - cr.top, w: r.width, h: r.height,
                         scrollW: el.scrollWidth, scrollH: el.scrollHeight};
        });

        const groups = {};
        document.querySelectorAll('[data-group-id], .diagram-group').forEach(el => {
            const id = el.getAttribute('data-group-id') || el.dataset.groupId;
            if (!id) return;
            const r = el.getBoundingClientRect();
            groups[id] = {x: r.left - cr.left, y: r.top - cr.top, w: r.width, h: r.height};
        });

        const edges = [];
        document.querySelectorAll('path[data-src][data-dst], line[data-src][data-dst]').forEach(el => {
            edges.push({
                src: el.getAttribute('data-src'),
                dst: el.getAttribute('data-dst'),
                rel_id: el.getAttribute('data-relation-id') || '',
                arrow: el.getAttribute('data-arrow') || '',
            });
        });

        return {
            canvas: {x: cr.left, y: cr.top, w: cr.width, h: cr.height},
            diagramW: parseInt(canvas.getAttribute('data-diagram-w') || canvas.offsetWidth),
            diagramH: parseInt(canvas.getAttribute('data-diagram-h') || canvas.offsetHeight),
            nodes: nodes,
            groups: groups,
            edges: edges,
        };
    }"""

    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "diagram.html"
        html_path.write_text(page_html, encoding="utf-8")
        with get_browser() as browser:
            page = browser.new_page()
            _setup_page(page, width=profile.viewport_width, height=profile.viewport_height)
            page.goto(f"file://{html_path}", wait_until="networkidle", timeout=30000)
            page.evaluate("async () => { await document.fonts.ready; }")
            dom = page.evaluate(_DOM_GEO_JS)
            page.close()

    if "error" in dom:
        raise RuntimeError(f"DOM extraction error: {dom['error']}")

    canvas_r = dom["canvas"]
    canvas_bounds = BoundingBox(
        x=0.0, y=0.0,
        width=float(dom.get("diagramW", canvas_r["w"])),
        height=float(dom.get("diagramH", canvas_r["h"])),
    )

    entities_geo: list[EntityGeometry] = []
    for eid, r in dom["nodes"].items():
        bbox = BoundingBox(x=float(r["x"]), y=float(r["y"]), width=float(r["w"]), height=float(r["h"]))
        entities_geo.append(EntityGeometry(
            entity_id=eid,
            bbox=bbox,
            text_bbox=None,
            text_lines=1,
        ))

    groups_geo: list[GroupGeometry] = []
    for gid, r in dom["groups"].items():
        groups_geo.append(GroupGeometry(
            group_id=gid,
            bbox=BoundingBox(x=float(r["x"]), y=float(r["y"]), width=float(r["w"]), height=float(r["h"])),
        ))

    # Containment from group membership (inferred from positions)
    containment: list[tuple[str, str]] = []
    grp_bboxes = {gg.group_id: gg.bbox for gg in groups_geo}
    for eg in entities_geo:
        for gid, gbbox in grp_bboxes.items():
            if _bbox_contains(gbbox, eg.bbox, tolerance=8.0):
                containment.append((eg.entity_id, gid))
                break

    # Content bounds
    if entities_geo:
        all_bboxes = [eg.bbox for eg in entities_geo] + [gg.bbox for gg in groups_geo]
        min_x = min(b.x for b in all_bboxes)
        min_y = min(b.y for b in all_bboxes)
        max_x = max(b.right for b in all_bboxes)
        max_y = max(b.bottom for b in all_bboxes)
        content_bounds = BoundingBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)
    else:
        content_bounds = None

    geo = GeometryObservation(
        coordinate_convention="css-top-left",
        content_bounds=content_bounds,
        canvas_bounds=canvas_bounds,
        viewbox=None,
        entities=entities_geo,
        groups=groups_geo,
        relations=[],
        containment=containment,
    )

    # Quality checks
    from mermaid_fidelity.compare.quality import run_quality_checks, QualityTolerances
    findings = run_quality_checks(geo)
    quality = QualityObservation(findings=findings)

    return geo, quality


def _bbox_contains(container: BoundingBox, item: BoundingBox, tolerance: float = 8.0) -> bool:
    return (
        item.x >= container.x - tolerance
        and item.right <= container.right + tolerance
        and item.y >= container.y - tolerance
        and item.bottom <= container.bottom + tolerance
    )
