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

def _find_mmdc() -> str:
    local = _REPO / "node_modules" / ".bin" / "mmdc"
    if local.exists():
        return str(local)
    found = shutil.which("mmdc")
    if found:
        return found
    return "/opt/homebrew/bin/mmdc"

_MMDC_PATH = _find_mmdc()
_ADAPTER_VERSION = "2.0.0"

# Version/integrity cached after the first subprocess call so that each case
# does not re-invoke mmdc --version and re-hash the binary.
_UNSET = object()  # sentinel distinguishing "not yet computed" from None/""
_MMDC_VERSION_CACHE: object = _UNSET
_MMDC_INTEGRITY_CACHE: object = _UNSET

# SVG topology extractors matching test_oracle.py
_MM_FLOWCHART_NODE = re.compile(r'flowchart-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_SERVICE_NODE   = re.compile(r'service-([A-Za-z0-9_.\-]+?)"')
_MM_ENTITY_NODE    = re.compile(r'entity-([A-Za-z0-9_.\-]+?)-\d+"')
_MM_LINK_EDGE      = re.compile(r'L_([A-Za-z0-9_.\-]+?)_([A-Za-z0-9_.\-]+?)_\d+"')
_MM_SELF_LOOP      = re.compile(r'id="[^"]*-([A-Za-z0-9_]+)-cyclic-special-\d+"')
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
    global _MMDC_VERSION_CACHE
    if _MMDC_VERSION_CACHE is not _UNSET:
        return _MMDC_VERSION_CACHE  # type: ignore[return-value]
    try:
        result = subprocess.run(
            [_MMDC_PATH, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        v = result.stdout.strip() or result.stderr.strip() or "unknown"
    except Exception:
        v = "unknown"
    _MMDC_VERSION_CACHE = v
    return v


def _mmdc_integrity() -> "str | None":
    global _MMDC_INTEGRITY_CACHE
    if _MMDC_INTEGRITY_CACHE is not _UNSET:
        return _MMDC_INTEGRITY_CACHE  # type: ignore[return-value]
    p = Path(_MMDC_PATH)
    val: "str | None" = hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None
    _MMDC_INTEGRITY_CACHE = val
    return val


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
        node_labels = _parse_flowchart_labels(source)
        entities = [
            Entity(id=n, kind="node", label=node_labels.get(n, n), shape=None, parent_id=None, order=i)
            for i, n in enumerate(dict.fromkeys(raw_nodes))
        ]
        # Use source-based edge extraction for accurate (src, dst, label) in document order.
        # Dedup by (src, dst, label) key to match mmdc's dedup; fall back to SVG topology
        # when source parser produces fewer edges (complex multi-edge or chains).
        source_edges = _parse_flowchart_edges(source)
        # Verify: source-based count should match SVG topology (after dedup + self-loops).
        # If source parser found edges, prefer it (it has correct labels and order).
        # Fall back to SVG topology with empty labels for parse failures.
        svg_nodes_set = {e.id for e in entities}
        # Filter source edges to known SVG nodes only (avoids false positives from
        # comment lines parsed as edges)
        valid_source_edges = [
            (s, d, lbl) for s, d, lbl in source_edges
            if s in svg_nodes_set and d in svg_nodes_set
        ]
        relations = [
            Relation(
                id=f"{s}__{d}__{i}",
                kind="edge",
                source=s,
                target=d,
                label=lbl,
                arrow=None,
                order=i,
            )
            for i, (s, d, lbl) in enumerate(valid_source_edges)
        ]
        # Parse subgraph groups from source
        from adapters.playwright_extractor import _parse_flowchart_subgraphs
        subgraph_data = _parse_flowchart_subgraphs(source)
        groups_sem = [
            Group(id=sg["id"], kind="subgraph", label=sg["label"],
                  parent_id=sg.get("parent"), order=i, members=sg["members"])
            for i, sg in enumerate(subgraph_data)
        ]
        direction = _extract_direction_from_source(source)
        return SemanticDiagram(
            diagram_type="flowchart",
            direction=direction,
            entities=entities,
            relations=relations,
            groups=groups_sem,
        )

    if diagram_type in ("architecture-beta", "architecture"):
        raw_nodes = list(_MM_SERVICE_NODE.findall(svg))
        raw_edges = list(_MM_LINK_EDGE.findall(svg))
        arch_labels = _parse_architecture_labels(source)
        entities = [
            Entity(id=n, kind="service", label=arch_labels.get(n, n), shape=None, parent_id=None, order=i)
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
        # Explicit participant/actor declarations
        explicit = re.findall(
            r'(?:participant|actor)\s+([A-Za-z0-9_][A-Za-z0-9_ ]*?)(?:\s+as\s+|\s*\n)',
            source, re.IGNORECASE,
        )
        # Implicit participants from message endpoints: A ->> B: text, A -> B, etc.
        implicit: list[str] = []
        for m in re.finditer(
            r'([A-Za-z0-9_][A-Za-z0-9_ ]*?)\s*(?:-->>|->|->>|-->|-x|-\))\s*'
            r'([A-Za-z0-9_][A-Za-z0-9_ ]*?)\s*:',
            source,
        ):
            implicit.extend([m.group(1).strip(), m.group(2).strip()])
        # Deduplicate preserving order; explicit declarations take priority.
        seen: dict[str, None] = dict.fromkeys(p.strip() for p in explicit)
        for p in implicit:
            seen.setdefault(p, None)
        entities = [
            Entity(id=p, kind="participant", label=p, shape=None, parent_id=None, order=i)
            for i, p in enumerate(seen)
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


def _find_arrow_outside_brackets(text: str) -> tuple[int, int] | None:
    """Find first Mermaid arrow outside bracket-enclosed content."""
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c in '[({':
            depth += 1
            i += 1
        elif c in '])}':
            depth = max(0, depth - 1)
            i += 1
        elif depth == 0 and c == '-':
            # Directed: -[-.=]*> (handles -->, ---->, -.->, etc.)
            m = re.match(r'-[-.=]*>', text[i:])
            if m:
                return (i, i + len(m.group()))
            # Arrowless solid link: --- or longer (e.g. "A --- B", "A -- text --- B")
            m = re.match(r'---+', text[i:])
            if m:
                return (i, i + len(m.group()))
            i += 1
        elif depth == 0 and c == '=':
            # Directed thick: =[=]+>
            m = re.match(r'=[=]+>', text[i:])
            if m:
                return (i, i + len(m.group()))
            # Arrowless thick: === or longer
            m = re.match(r'===[=]*', text[i:])
            if m:
                return (i, i + len(m.group()))
            i += 1
        else:
            i += 1
    return None


def _extract_node_ids_from_segment(segment: str) -> list[str]:
    """Extract node IDs from a segment, splitting on & only outside brackets."""
    result = []
    parts: list[str] = []
    depth = 0
    start = 0
    for i, c in enumerate(segment):
        if c in '[({':
            depth += 1
        elif c in '])}':
            depth = max(0, depth - 1)
        elif c == '&' and depth == 0:
            parts.append(segment[start:i])
            start = i + 1
    parts.append(segment[start:])
    for part in parts:
        part = part.strip()
        # Mermaid node IDs may contain hyphens (e.g. api-v1, db-main)
        m = re.match(r'([A-Za-z0-9_][A-Za-z0-9_-]*)', part)
        if m:
            result.append(m.group(1))
    return result


def _parse_flowchart_edges(source: str) -> list[tuple[str, str, str]]:
    """Extract (source, target, label) from Mermaid flowchart source.

    Handles: A --> B, A -->|label| B, A -- label --> B,
             A --> B & C & D (multi-target), A & B --> C (multi-source),
             A --> B --> C (chained — produces two edges).
    """
    edges: list[tuple[str, str, str]] = []

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(
            ('%%', '//', 'subgraph', 'end', 'flowchart', 'graph', 'direction')
        ):
            continue
        if not any(a in stripped for a in ['-->', '-.->', '===', '==>', '---']):
            continue

        # Split the line into node-segments and per-arrow labels by iterating
        # arrows. Adjacent segments i and i+1 form one edge with labels[i].
        segments: list[str] = []
        labels: list[str] = []
        remaining = stripped
        while True:
            arrow_span = _find_arrow_outside_brackets(remaining)
            if arrow_span is None:
                segments.append(remaining)
                break
            a_start, a_end = arrow_span
            before = remaining[:a_start]
            after = remaining[a_end:]

            # Check for pipe label immediately after arrow
            label = ""
            after_stripped = after.strip()
            if after_stripped.startswith('|'):
                pipe_end = after_stripped.find('|', 1)
                if pipe_end > 0:
                    label = _strip_html(after_stripped[1:pipe_end]).strip()
                    after = after_stripped[pipe_end + 1:]
            # Dash-text style: A -- text --> B. Strip bracket/quote content first
            # so node labels like A["up -- down"] don't corrupt label extraction.
            elif '--' in before:
                _stripped_before = re.sub(r'"[^"]*"|\[[^\]]*\]|\([^)]*\)|\{[^}]*\}', '', before)
                if '--' in _stripped_before:
                    m_text = re.match(r'(.+?)\s+--\s+(.+?)\s*$', before)
                    if m_text:
                        before = m_text.group(1)
                        label = _strip_html(m_text.group(2)).strip()

            segments.append(before)
            labels.append(label)
            remaining = after

        for i in range(len(segments) - 1):
            sources = _extract_node_ids_from_segment(segments[i])
            targets = _extract_node_ids_from_segment(segments[i + 1])
            lbl = labels[i] if i < len(labels) else ""
            for src in sources:
                for tgt in targets:
                    if src and tgt:
                        edges.append((src, tgt, lbl))

    return edges


def _parse_architecture_labels(source: str) -> dict[str, str]:
    """Return id → label for architecture-beta service/junction declarations.

    Supports: service id(icon)[Label]  and  junction id
    """
    result: dict[str, str] = {}
    pat = re.compile(
        r'(?:service|junction)\s+([A-Za-z0-9_.\-]+)'
        r'(?:\s*\([^)]*\))?'       # optional (icon)
        r'(?:\s*\[([^\]]*)\])?',   # optional [Label]
    )
    for m in pat.finditer(source):
        nid, label = m.group(1), m.group(2)
        if nid not in result:
            result[nid] = (_strip_html(label).strip() if label else nid)
    return result


def _parse_flowchart_labels(source: str) -> dict[str, str]:
    """Return id → label mapping from Mermaid flowchart source lines.

    Handles the common node-definition forms:
        A[rect]  A(round)  A{diamond}  A[[sub]]  A((circle))  A([stadium])
        A(((dcircle)))  A{{hex}}  A[(cyl)]  A>flag]  A[/trap/]  A[\\inv\\]
    Falls back to id == label when no bracket form is found.
    """
    result: dict[str, str] = {}
    # One pass: match ID then the first bracket-enclosed label.
    # The pattern intentionally covers the longest forms first to avoid
    # partial matches (e.g. [[...]] before [...]).
    _pat = re.compile(
        r'\b([A-Za-z0-9_]+)\s*'
        r'(?:'
        r'\(\(\(([^()]*)\)\)\)'        # (((text))) triple-circle
        r'|\[\[([^\[\]]*)\]\]'         # [[text]] subroutine
        r'|\(\(([^()]*)\)\)'           # ((text)) double-circle
        r'|\(\[([^\[\]]*)\]\)'         # ([text]) stadium
        r'|\[\(([^()]*)\)\]'           # [(text)] cylinder
        r'|\{\{([^{}]*)\}\}'           # {{text}} hexagon
        r'|\[\\([^\[\]\\]*)\\\]'       # [\text\] inv-trapezoid
        r'|\[\/([^\[\]\/]*)\\\]'       # [/text\] tilted-right
        r'|\[\\([^\[\]\\]*)\/\]'       # [\text/] tilted-left
        r'|\[\/([^\[\]\/]*)\/'         # [/text/  trapezoid (closing optional)
        r'|\{([^{}]*)\}'               # {text} diamond
        r'|\(([^()]*)\)'               # (text) rounded
        r'|\[([^\[\]]*)\]'             # [text] rectangle
        r'|>([^\[\]]*)\]'              # >text] asymmetric/flag
        r')'
    )
    for m in _pat.finditer(source):
        nid = m.group(1)
        if nid in result:
            continue
        for g in m.groups()[1:]:
            if g is not None:
                # Normalize <br> to space before stripping HTML tags
                normalized = re.sub(r'<br\s*/?>', ' ', g, flags=re.IGNORECASE)
                label = _strip_html(normalized).strip("/\\").strip()
                # Strip surrounding Mermaid quoting (double quotes around whole label)
                if label.startswith('"') and label.endswith('"') and len(label) > 1:
                    label = label[1:-1]
                label = ' '.join(label.split())  # normalize internal whitespace
                if label:
                    result[nid] = label
                break
    return result


def _extract_direction_from_source(source: str) -> str | None:
    m = re.search(r'(?:flowchart|graph)\s+(TB|LR|BT|RL|TD)\b', source, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def _extract_viewbox_geometry(svg: str) -> GeometryObservation | None:
    """Extract canvas bounds from SVG viewBox (for non-flowchart types)."""
    viewbox_m = re.search(r'viewBox="([^"]+)"', svg)
    if not viewbox_m:
        return None
    try:
        parts = [float(v) for v in viewbox_m.group(1).split()]
        vx, vy, vw, vh = parts
    except ValueError:
        return None
    # css-top-left convention: origin is (0,0) at the rendered top-left corner.
    # SVG viewBox origin (vx, vy) is an internal coordinate offset, not a CSS position.
    return GeometryObservation(
        coordinate_convention="css-top-left",
        content_bounds=None,
        canvas_bounds=BoundingBox(x=0.0, y=0.0, width=vw, height=vh),
        viewbox=viewbox_m.group(1),
    )


class ReferenceAdapter:
    """Fidelity adapter for the mmdc/Chromium (real Mermaid.js) reference.

    Reference ID: mermaid-11.15.0-neutral
    """

    def __init__(self) -> None:
        from adapters.playwright_extractor import PlaywrightBrowserManager
        self._browser_manager: "PlaywrightBrowserManager | None" = None

    def _get_browser_manager(self) -> "Any":
        from adapters.playwright_extractor import PlaywrightBrowserManager
        if self._browser_manager is None:
            self._browser_manager = PlaywrightBrowserManager()
        return self._browser_manager

    def close(self) -> None:
        if self._browser_manager is not None:
            self._browser_manager.close()
            self._browser_manager = None

    def __enter__(self) -> "ReferenceAdapter":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

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
                schema_version=1, case_id=case.id,
                implementation=self.identity(), environment=_env_identity(profile, self),
                parse_result=ParseObservation(accepted=False, diagram_type=None,
                    error_category="mmdc_unavailable", source_position=None),
                semantic=None, geometry=None, quality=None,
                status=ComparisonStatus.REFERENCE_RENDER_FAILURE,
                reason="mmdc binary not found",
            )

        config_json: str | None = None
        if profile.mermaid_config:
            config_json = json.dumps(profile.mermaid_config)

        source_sha256 = hashlib.sha256(case.source.encode("utf-8")).hexdigest()
        svg = _mmdc_render(case.source, config_json)
        diagram_type = _infer_diagram_type(case.source)
        impl = self.identity()

        if svg is None:
            # Build env without browser (chromium_revision will be "unknown"; acceptable
            # for error observations where geometry is never captured).
            return Observation(
                schema_version=1, case_id=case.id,
                implementation=impl, environment=_env_identity(profile, self),
                parse_result=ParseObservation(accepted=False, diagram_type=None,
                    error_category="render_error", source_position=None),
                semantic=None, geometry=None, quality=None,
                status=ComparisonStatus.REFERENCE_RENDER_FAILURE,
                reason="mmdc returned non-zero or no SVG",
                capture_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_sha256=source_sha256,
            )

        semantic = _extract_semantic_from_svg(svg, case.source)

        geometry: GeometryObservation | None = None
        status = ComparisonStatus.PASS
        reason: str | None = None
        used_browser = False

        if diagram_type in ("flowchart", "graph"):
            try:
                from adapters.playwright_extractor import extract_flowchart_geometry
                bm = self._get_browser_manager()
                geometry, error_reason = extract_flowchart_geometry(
                    svg=svg,
                    semantic=semantic,
                    browser_manager=bm,
                    source=case.source,
                    viewport_width=profile.viewport_width,
                    viewport_height=profile.viewport_height,
                    device_scale_factor=profile.device_scale_factor,
                    locale=profile.locale,
                    timezone=profile.timezone,
                    reduced_motion=profile.reduced_motion,
                )
                used_browser = True
                if error_reason is not None:
                    status = ComparisonStatus.EXTRACTOR_GAP
                    reason = error_reason
            except Exception as exc:
                reason = f"playwright extraction error: {exc}"
                status = ComparisonStatus.EXTRACTOR_GAP
                geometry = GeometryObservation(
                    coordinate_convention="css-top-left",
                    content_bounds=None, canvas_bounds=None, viewbox=None,
                )
        else:
            # For non-flowchart types: parse viewBox from SVG for canvas bounds
            geometry = _extract_viewbox_geometry(svg)

        parse_obs = ParseObservation(
            accepted=True, diagram_type=diagram_type,
            error_category=None, source_position=None,
        )

        # Build env after geometry extraction; pass used_browser so chromium_revision
        # is only recorded for observations that actually launched the browser.
        env = _env_identity(profile, self, used_browser=used_browser)

        return Observation(
            schema_version=1, case_id=case.id,
            implementation=impl, environment=env,
            parse_result=parse_obs, semantic=semantic,
            geometry=geometry, quality=None,
            status=status, reason=reason,
            capture_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_sha256=source_sha256,
        )


def _profile_font_family(profile: RenderProfile) -> str:
    """Return the font-family configured in the render profile's mermaid config."""
    try:
        if profile.mermaid_config:
            theme_vars = profile.mermaid_config.get("themeVariables", {})
            font = theme_vars.get("fontFamily") or profile.mermaid_config.get("fontFamily")
            if font:
                return font
    except Exception:
        pass
    return "trebuchet ms, verdana, arial, sans-serif"


def _env_identity(
    profile: RenderProfile,
    adapter: "ReferenceAdapter | None" = None,
    used_browser: bool = False,
) -> EnvironmentIdentity:
    cfg_hash = ""
    if profile.mermaid_config:
        cfg_hash = hashlib.sha256(
            json.dumps(profile.mermaid_config, sort_keys=True).encode()
        ).hexdigest()[:16]

    pw_version = "unknown"
    chromium_version = "unknown"
    if adapter is not None:
        try:
            bm = adapter._browser_manager
            if bm is not None:
                pw_version = bm.playwright_version()  # importlib.metadata — no browser launch
                # Only record chromium version when this observation actually used the browser.
                # Checking bm._browser is not None would bleed the browser version into
                # non-flowchart observations that run after a flowchart case opened the browser.
                if used_browser and bm._browser is not None:
                    chromium_version = bm.browser_version()
            else:
                from adapters.playwright_extractor import PlaywrightBrowserManager
                pw_version = PlaywrightBrowserManager().playwright_version()
        except Exception:
            pass

    return EnvironmentIdentity(
        mermaid_version=_mmdc_version(),
        mermaid_integrity=_mmdc_integrity(),
        playwright_version=pw_version,
        chromium_revision=chromium_version,
        viewport_width=profile.viewport_width,
        viewport_height=profile.viewport_height,
        device_scale_factor=profile.device_scale_factor,
        locale=profile.locale,
        timezone=profile.timezone,
        reduced_motion=profile.reduced_motion,
        mermaid_config_hash=cfg_hash,
        css_profile_hash="",
        font_info={"requested": _profile_font_family(profile)},
    )
