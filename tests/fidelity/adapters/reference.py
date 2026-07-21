"""Reference adapter: observes mmdc/Chromium (real Mermaid.js) output.

Wraps the same mmdc subprocess pattern as tests/test_oracle.py and
extracts semantics from the SVG via Playwright DOM inspection.

This adapter should NOT launch its own browser independently — it reuses
the mmdc/Chromium stack exactly as the oracle tests do.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
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
    OrderedEvent,
    ParseObservation,
    QualityFindingKind,
    QualityObservation,
    Relation,
    RenderProfile,
    SemanticDiagram,
)

_MMDC_PATH = shutil.which("mmdc") or "/opt/homebrew/bin/mmdc"
_ADAPTER_VERSION = "1.0.0"

# SVG topology extractors matching test_oracle.py
_MM_FLOWCHART_NODE = re.compile(r'flowchart-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_SERVICE_NODE   = re.compile(r'service-([A-Za-z0-9_.\-]+?)"')
_MM_ENTITY_NODE    = re.compile(r'entity-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_LINK_EDGE      = re.compile(r'L_([A-Za-z0-9_.\-]+?)_([A-Za-z0-9_.\-]+?)_\d+"')
_MM_EDGE_LABEL     = re.compile(
    r'<span class="edgeLabel"><p[^>]*>(.*?)</p></span>', re.DOTALL
)
_MM_SEQ_ACTOR      = re.compile(r'actor\s+([A-Za-z0-9_.\- ]+?)(?:\s*\n|$)', re.MULTILINE)
_MM_SEQ_MSG        = re.compile(r'sequenceMessage-\d+"')
_MM_GROUP_LABEL    = re.compile(r'<g[^>]+class="[^"]*label[^"]*"[^>]*>\s*<text[^>]*>([^<]+)</text>')

_STRIP_TAGS = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    import html as _html_lib
    return _html_lib.unescape(_STRIP_TAGS.sub("", s)).strip()


def _mmdc_version() -> str:
    try:
        result = subprocess.run(
            [_MMDC_PATH, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() or result.stderr.strip() or "unknown"
    except Exception:
        return "unknown"


def _mmdc_integrity() -> str | None:
    p = Path(_MMDC_PATH)
    if p.exists():
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return None


def _mmdc_render(source: str, config_json: str | None = None) -> str | None:
    """Run mmdc and return the SVG string, or None on failure."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mmd_path = tmp_path / "d.mmd"
        svg_path = tmp_path / "d.svg"
        mmd_path.write_text(source, encoding="utf-8")

        cmd = [_MMDC_PATH, "-i", str(mmd_path), "-o", str(svg_path), "--quiet"]
        if config_json:
            cfg_path = tmp_path / "config.json"
            cfg_path.write_text(config_json)
            cmd += ["-c", str(cfg_path)]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=90)
        except subprocess.TimeoutExpired:
            return None
        if result.returncode != 0 or not svg_path.exists():
            return None
        return svg_path.read_text(encoding="utf-8")


def _infer_diagram_type(source: str) -> str:
    first_line = source.strip().split("\n")[0].strip().lower()
    for prefix in ("flowchart", "graph", "sequencediagram", "erdiagram",
                   "architecture-beta", "classDiagram", "stateDiagram"):
        if first_line.startswith(prefix.lower()):
            return prefix.lower().replace(" ", "").replace("-beta", "")
    return "unknown"


def _extract_semantic_from_svg(svg: str, source: str) -> SemanticDiagram:
    """Extract semantic topology from the mmdc-rendered SVG."""
    diagram_type = _infer_diagram_type(source)

    if diagram_type in ("flowchart", "graph"):
        raw_nodes = list(_MM_FLOWCHART_NODE.findall(svg))
        raw_edges = list(_MM_LINK_EDGE.findall(svg))
        raw_labels = [
            _strip_html(lbl) for lbl in _MM_EDGE_LABEL.findall(svg)
            if _strip_html(lbl)
        ]
        entities = [
            Entity(id=n, kind="node", label=n, shape=None, parent_id=None, order=i)
            for i, n in enumerate(dict.fromkeys(raw_nodes))
        ]
        label_iter = iter(raw_labels)
        relations = [
            Relation(
                id=f"{s}__{d}__{i}",
                kind="edge",
                source=s,
                target=d,
                label=next(label_iter, ""),
                arrow=None,
                order=i,
            )
            for i, (s, d) in enumerate(raw_edges)
        ]
        direction = _extract_direction_from_source(source)
        return SemanticDiagram(
            diagram_type="flowchart",
            direction=direction,
            entities=entities,
            relations=relations,
        )

    if diagram_type == "architecture-beta":
        raw_nodes = list(_MM_SERVICE_NODE.findall(svg))
        raw_edges = list(_MM_LINK_EDGE.findall(svg))
        entities = [
            Entity(id=n, kind="service", label=n, shape=None, parent_id=None, order=i)
            for i, n in enumerate(dict.fromkeys(raw_nodes))
        ]
        relations = [
            Relation(id=f"{s}__{d}__{i}", kind="edge", source=s, target=d, label="", arrow=None, order=i)
            for i, (s, d) in enumerate(raw_edges)
        ]
        return SemanticDiagram(diagram_type="architecture", direction=None, entities=entities, relations=relations)

    if diagram_type == "erdiagram":
        raw_nodes = list(_MM_ENTITY_NODE.findall(svg))
        entities = [
            Entity(id=n, kind="entity", label=n, shape=None, parent_id=None, order=i)
            for i, n in enumerate(dict.fromkeys(raw_nodes))
        ]
        return SemanticDiagram(diagram_type="er", direction=None, entities=entities)

    if "sequencediagram" in diagram_type:
        # Extract participants from source as fallback
        participants = re.findall(
            r'(?:participant|actor)\s+([A-Za-z0-9_][A-Za-z0-9_ ]*?)(?:\s+as\s+|\s*\n)',
            source, re.IGNORECASE,
        )
        entities = [
            Entity(id=p.strip(), kind="participant", label=p.strip(), shape=None, parent_id=None, order=i)
            for i, p in enumerate(dict.fromkeys(participants))
        ]
        # Messages from SVG message elements
        ordered_events: list[OrderedEvent] = []
        msg_matches = re.findall(
            r'data-seq-(?:msg|message)[^>]*?>([^<]*)<',
            svg,
        )
        for i, text in enumerate(msg_matches):
            ordered_events.append(OrderedEvent(
                id=f"msg-{i}",
                kind="message",
                source=None,
                target=None,
                label=_strip_html(text),
                order=i,
            ))
        return SemanticDiagram(
            diagram_type="sequence",
            direction=None,
            entities=entities,
            ordered_events=ordered_events,
        )

    # Generic fallback
    return SemanticDiagram(diagram_type=diagram_type, direction=None)


def _extract_direction_from_source(source: str) -> str | None:
    m = re.search(r'(?:flowchart|graph)\s+(TB|LR|BT|RL|TD)\b', source, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def _extract_geometry_from_svg(svg: str) -> GeometryObservation | None:
    """Extract bounding boxes from the SVG viewBox and element coordinates."""
    viewbox_m = re.search(r'viewBox="([^"]+)"', svg)
    if not viewbox_m:
        return None

    try:
        parts = [float(v) for v in viewbox_m.group(1).split()]
        vx, vy, vw, vh = parts
    except ValueError:
        return None

    canvas_bounds = BoundingBox(x=vx, y=vy, width=vw, height=vh)

    # Extract entity bboxes from SVG rect elements inside node groups
    # Mermaid SVG: <g id="flowchart-NodeId-N" ...><rect ... x=".." y=".." width=".." height=".."/></g>
    node_bbox_pattern = re.compile(
        r'<g[^>]+id="flowchart-([A-Za-z0-9_.\-]+)-\d+"[^>]*>.*?'
        r'<rect[^>]+x="([^"]+)"[^>]+y="([^"]+)"[^>]+(?:width="([^"]+)"[^>]+height="([^"]+)"|'
        r'height="([^"]+)"[^>]+width="([^"]+)")',
        re.DOTALL,
    )
    entities_geo: list[EntityGeometry] = []
    seen: set[str] = set()
    for m in node_bbox_pattern.finditer(svg):
        node_id = m.group(1)
        if node_id in seen:
            continue
        seen.add(node_id)
        try:
            x = float(m.group(2))
            y = float(m.group(3))
            w = float(m.group(4) or m.group(7))
            h = float(m.group(5) or m.group(6))
            entities_geo.append(EntityGeometry(
                entity_id=node_id,
                bbox=BoundingBox(x=x, y=y, width=w, height=h),
                text_bbox=None,
                text_lines=1,
            ))
        except (ValueError, TypeError):
            continue

    content_bounds = None
    if entities_geo:
        min_x = min(eg.bbox.x for eg in entities_geo)
        min_y = min(eg.bbox.y for eg in entities_geo)
        max_x = max(eg.bbox.right for eg in entities_geo)
        max_y = max(eg.bbox.bottom for eg in entities_geo)
        content_bounds = BoundingBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)

    return GeometryObservation(
        coordinate_convention="svg-top-left",
        content_bounds=content_bounds,
        canvas_bounds=canvas_bounds,
        viewbox=viewbox_m.group(1),
        entities=entities_geo,
        groups=[],
        relations=[],
        containment=[],
    )


class ReferenceAdapter:
    """Fidelity adapter for the mmdc/Chromium (real Mermaid.js) reference.

    Reference ID: mermaid-11.15.0-neutral
    """

    def identity(self) -> ImplementationIdentity:
        return ImplementationIdentity(
            name="mermaid-cli",
            version=_mmdc_version(),
            integrity=_mmdc_integrity(),
            adapter_version=_ADAPTER_VERSION,
            profile_id="mermaid-neutral",
        )

    def observe(self, case: FidelityCase, profile: RenderProfile) -> Observation:
        if not shutil.which("mmdc") and not Path(_MMDC_PATH).exists():
            return Observation(
                schema_version=1,
                case_id=case.id,
                implementation=self.identity(),
                environment=_env_identity(profile),
                parse_result=ParseObservation(
                    accepted=False,
                    diagram_type=None,
                    error_category="mmdc_unavailable",
                    source_position=None,
                ),
                semantic=None,
                geometry=None,
                quality=None,
                status=ComparisonStatus.REFERENCE_RENDER_FAILURE,
                reason="mmdc binary not found",
            )

        config_json: str | None = None
        if profile.mermaid_config:
            config_json = json.dumps(profile.mermaid_config)

        svg = _mmdc_render(case.source, config_json)
        impl = self.identity()
        env = _env_identity(profile)

        if svg is None:
            return Observation(
                schema_version=1,
                case_id=case.id,
                implementation=impl,
                environment=env,
                parse_result=ParseObservation(
                    accepted=False,
                    diagram_type=None,
                    error_category="render_error",
                    source_position=None,
                ),
                semantic=None,
                geometry=None,
                quality=None,
                status=ComparisonStatus.REFERENCE_RENDER_FAILURE,
                reason="mmdc returned non-zero or no SVG",
                capture_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )

        semantic = _extract_semantic_from_svg(svg, case.source)
        geometry = _extract_geometry_from_svg(svg)

        parse_obs = ParseObservation(
            accepted=True,
            diagram_type=_infer_diagram_type(case.source),
            error_category=None,
            source_position=None,
        )

        return Observation(
            schema_version=1,
            case_id=case.id,
            implementation=impl,
            environment=env,
            parse_result=parse_obs,
            semantic=semantic,
            geometry=geometry,
            quality=None,
            status=ComparisonStatus.PASS,
            reason=None,
            capture_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )


def _env_identity(profile: RenderProfile) -> EnvironmentIdentity:
    cfg_hash = ""
    if profile.mermaid_config:
        cfg_hash = hashlib.sha256(
            json.dumps(profile.mermaid_config, sort_keys=True).encode()
        ).hexdigest()[:16]

    return EnvironmentIdentity(
        mermaid_version=_mmdc_version(),
        mermaid_integrity=_mmdc_integrity(),
        playwright_version="bundled-in-mmdc",
        chromium_revision="1228",
        viewport_width=profile.viewport_width,
        viewport_height=profile.viewport_height,
        device_scale_factor=profile.device_scale_factor,
        locale=profile.locale,
        timezone=profile.timezone,
        reduced_motion=profile.reduced_motion,
        mermaid_config_hash=cfg_hash,
        css_profile_hash=None,
        font_info={"requested": "Helvetica Neue, Helvetica, Arial, sans-serif"},
    )
