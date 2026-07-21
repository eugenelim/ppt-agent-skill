"""Typed layout configuration models replacing the untyped dict from _parse_init_config.

Parse priority:
  %%{init: {"flowchart": {"nodeSpacing": N, ...}}}%%  — standard Mermaid init block
  UpdateLayoutConfig($c4ShapeInRow="3", ...)           — C4 layout config calls

Unknown keys are preserved in `unsupported_keys` for diagnostics.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from ._constants import COL_GAP, RANK_GAP, CANVAS_PAD

# ── Config dataclasses ────────────────────────────────────────────────────────

@dataclass
class FlowchartLayoutConfig:
    """Per-diagram layout settings for flowchart / graph directives."""
    node_spacing: int = COL_GAP       # gap perpendicular to flow direction (COL_GAP)
    rank_spacing: int = RANK_GAP      # gap in flow direction (RANK_GAP)
    diagram_padding: int = CANVAS_PAD
    wrapping_width: Optional[int] = None
    curve: str = "basis"              # "basis" | "linear" | "step" (visual only)
    ranker: str = "longest-path"      # "longest-path" | "network-simplex"
    orderer: str = "barycenter"       # "barycenter" | "barycenter-transpose"
    positioner: str = "simple"        # "simple" | "brandes-koepf"
    unsupported_keys: list[str] = field(default_factory=list)


@dataclass
class GraphLayoutConfig(FlowchartLayoutConfig):
    """Same as FlowchartLayoutConfig — 'graph' directive shares all settings."""
    pass


@dataclass
class C4LayoutConfig:
    """Layout settings for C4 diagram directives."""
    shapes_per_row: int = 4       # max leaf shapes per row inside a boundary
    boundaries_per_row: int = 2   # max sibling boundaries per row
    shape_width: int = 216        # width of each C4 shape card (px)
    shape_margin: int = 20        # horizontal margin between shapes (px)
    boundary_margin: int = 24     # margin around boundary boxes (px)
    layout_width: int = 1000      # total diagram width hint (px)
    diagram_padding: int = CANVAS_PAD
    unsupported_keys: list[str] = field(default_factory=list)


@dataclass
class RenderConfig:
    """Top-level render configuration, aggregating per-diagram configs."""
    flowchart: FlowchartLayoutConfig = field(default_factory=FlowchartLayoutConfig)
    graph: GraphLayoutConfig = field(default_factory=GraphLayoutConfig)
    c4: C4LayoutConfig = field(default_factory=C4LayoutConfig)
    theme: Optional[str] = None


# ── Parsers ───────────────────────────────────────────────────────────────────

_INIT_RE = re.compile(r'%%\s*\{(.+?)\}\s*%%', re.DOTALL)

# C4 UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
_C4_UPDATE_RE = re.compile(
    r'UpdateLayoutConfig\s*\(([^)]+)\)',
    re.IGNORECASE,
)
_C4_PARAM_RE = re.compile(r'\$(\w+)\s*=\s*["\']?(\d+)["\']?')


def _parse_init_block(raw: str) -> dict:
    """Parse the content of a %%{...}%% block into a dict.

    Handles:
      - Standard JSON: {"init": {"flowchart": {...}}}
      - Mermaid's semi-JSON: init: {"flowchart": {...}}  (unquoted key)
      - Single-quoted variants: init: {'flowchart': {...}}
    """
    raw = raw.strip()
    # Replace single quotes with double quotes for JSON parsing
    raw_dq = re.sub(r"'([^']*)'", r'"\1"', raw)

    # 1. Try standard JSON (entire block is valid JSON)
    try:
        obj = json.loads(raw_dq)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Mermaid format: "init: {...}" — strip the "init:" prefix and parse the value
    init_m = re.match(r'^init\s*:\s*(\{.+\})\s*$', raw_dq, re.DOTALL)
    if init_m:
        try:
            inner = json.loads(init_m.group(1))
            if isinstance(inner, dict):
                return {"init": inner}
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. Try wrapping with {} (original approach for single-level: flowchart: {...})
    try:
        obj = json.loads("{" + raw_dq + "}")
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    return {}


def parse_flowchart_config(src: str) -> FlowchartLayoutConfig:
    """Parse %%{init:{flowchart:{...}}}%% blocks into FlowchartLayoutConfig."""
    cfg = FlowchartLayoutConfig()
    for m in _INIT_RE.finditer(src):
        obj = _parse_init_block(m.group(1))
        if not obj:
            continue
        fc = (
            obj.get("flowchart")
            or obj.get("init", {}).get("flowchart", {})
        )
        if not isinstance(fc, dict):
            continue
        known = {
            "nodeSpacing", "rankSpacing", "diagramPadding", "wrappingWidth",
            "curve", "ranker",
        }
        for key, val in fc.items():
            if key == "nodeSpacing":
                try:
                    cfg.node_spacing = int(val)
                except (TypeError, ValueError):
                    pass
            elif key == "rankSpacing":
                try:
                    cfg.rank_spacing = int(val)
                except (TypeError, ValueError):
                    pass
            elif key == "diagramPadding":
                try:
                    cfg.diagram_padding = int(val)
                except (TypeError, ValueError):
                    pass
            elif key == "wrappingWidth":
                try:
                    cfg.wrapping_width = int(val)
                except (TypeError, ValueError):
                    pass
            elif key == "curve":
                cfg.curve = str(val)
            elif key == "ranker":
                cfg.ranker = str(val)
            elif key not in known:
                cfg.unsupported_keys.append(key)
    return cfg


def parse_c4_config(src: str) -> C4LayoutConfig:
    """Parse UpdateLayoutConfig(...) calls and %%{init:{c4:{...}}}%% blocks."""
    cfg = C4LayoutConfig()

    # UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
    for m in _C4_UPDATE_RE.finditer(src):
        body = m.group(1)
        for pm in _C4_PARAM_RE.finditer(body):
            key = pm.group(1)
            val = int(pm.group(2))
            if key == "c4ShapeInRow":
                cfg.shapes_per_row = val
            elif key == "c4BoundaryInRow":
                cfg.boundaries_per_row = val
            else:
                cfg.unsupported_keys.append(f"${key}")

    # Also check %%{init:{c4:{...}}}%%
    for m in _INIT_RE.finditer(src):
        obj = _parse_init_block(m.group(1))
        if not obj:
            continue
        c4_cfg = obj.get("c4") or obj.get("init", {}).get("c4", {})
        if not isinstance(c4_cfg, dict):
            continue
        for key, val in c4_cfg.items():
            if key == "diagramPadding":
                try:
                    cfg.diagram_padding = int(val)
                except (TypeError, ValueError):
                    pass
            else:
                cfg.unsupported_keys.append(key)

    return cfg


def parse_render_config(src: str) -> RenderConfig:
    """Parse all init config from diagram source into a RenderConfig."""
    return RenderConfig(
        flowchart=parse_flowchart_config(src),
        graph=parse_flowchart_config(src),   # graph uses same config schema
        c4=parse_c4_config(src),
    )


# ── Backward-compat shim for _parse_init_config callers ──────────────────────

def legacy_parse_init_config(src: str) -> dict[str, int]:
    """Drop-in replacement for _parser._parse_init_config.

    Returns {"col_gap": int, "rank_gap": int, "diagram_padding": int} where set.
    """
    cfg = parse_flowchart_config(src)
    result: dict[str, int] = {}
    if cfg.node_spacing != COL_GAP:
        result["col_gap"] = cfg.node_spacing
    if cfg.rank_spacing != RANK_GAP:
        result["rank_gap"] = cfg.rank_spacing
    if cfg.diagram_padding != CANVAS_PAD:
        result["diagram_padding"] = cfg.diagram_padding
    return result
