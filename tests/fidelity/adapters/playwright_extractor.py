"""Playwright browser DOM geometry extractor for Mermaid flowchart SVGs.

Loads mmdc-rendered SVG into a Chromium page and measures element geometry
via getBBox() + getCTM(), producing GeometryObservation in css-top-left coords.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "tools"))

from mermaid_fidelity.models import (
    BoundingBox,
    ComparisonStatus,
    EntityGeometry,
    GeometryObservation,
    GroupGeometry,
    RelationGeometry,
    SemanticDiagram,
)

# ── RDP bend-count ─────────────────────────────────────────────────────────────

def _point_line_dist(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _rdp(points: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker polyline simplification."""
    if len(points) < 3:
        return list(points)
    max_d, idx = 0.0, 0
    for i in range(1, len(points) - 1):
        d = _point_line_dist(points[i], points[0], points[-1])
        if d > max_d:
            max_d, idx = d, i
    if max_d > eps:
        left = _rdp(points[: idx + 1], eps)
        right = _rdp(points[idx:], eps)
        return left[:-1] + right
    return [points[0], points[-1]]


def _compute_bend_count(dense: list[tuple[float, float]], eps: float = 1.0) -> int:
    if not dense:
        return 0
    simplified = _rdp(dense, eps)
    return max(0, len(simplified) - 2)


# ── crossing count ─────────────────────────────────────────────────────────────

def _cross(o: tuple, a: tuple, b: tuple) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_intersect(
    p1: tuple, p2: tuple, p3: tuple, p4: tuple, tol: float = 1e-9
) -> bool:
    """True if segment p1-p2 properly intersects p3-p4 (shared endpoints excluded)."""
    d1 = _cross(p3, p4, p1)
    d2 = _cross(p3, p4, p2)
    d3 = _cross(p1, p2, p3)
    d4 = _cross(p1, p2, p4)
    if ((d1 > tol and d2 < -tol) or (d1 < -tol and d2 > tol)) and \
       ((d3 > tol and d4 < -tol) or (d3 < -tol and d4 > tol)):
        return True
    return False


def _compute_crossing_count(
    relations: list[RelationGeometry], endpoint_tol: float = 3.0
) -> int:
    """Count proper crossings between distinct relations.

    Relations that share an attachment point (endpoint within endpoint_tol of
    the other relation's endpoint) are excluded — they meet at a node rather
    than crossing.
    """
    crossing = 0
    n = len(relations)
    for i in range(n):
        pts_i = relations[i].sampled_points
        if len(pts_i) < 2:
            continue
        segs_i = list(zip(pts_i[:-1], pts_i[1:]))
        for j in range(i + 1, n):
            pts_j = relations[j].sampled_points
            if len(pts_j) < 2:
                continue
            segs_j = list(zip(pts_j[:-1], pts_j[1:]))
            # Count every proper segment-segment intersection between the two
            # polylines. _segments_intersect already excludes endpoint-only
            # contact, so no need for a pair-level endpoint skip (which would
            # suppress valid non-endpoint crossings between connected edges).
            for s1 in segs_i:
                for s2 in segs_j:
                    if _segments_intersect(*s1, *s2):
                        crossing += 1
    return crossing


# ── endpoint side inference ────────────────────────────────────────────────────

def _infer_side(point: tuple[float, float], bbox: BoundingBox) -> str:
    x, y = point
    d_l = abs(x - bbox.x)
    d_r = abs(x - bbox.right)
    d_t = abs(y - bbox.y)
    d_b = abs(y - bbox.bottom)
    m = min(d_l, d_r, d_t, d_b)
    if m == d_l:
        return "L"
    if m == d_r:
        return "R"
    if m == d_t:
        return "T"
    return "B"


# ── source parsing helpers ─────────────────────────────────────────────────────

def _parse_flowchart_subgraphs(source: str) -> list[dict]:
    """Extract subgraph/cluster declarations and their member node IDs.

    Returns [{"id": group_id, "label": label, "members": [node_ids...]}].
    Handles nested subgraphs and both explicit IDs and implicit-title subgraphs.

    Mermaid subgraph ID resolution:
      subgraph id [label]  → DOM cluster id = id
      subgraph id          → DOM cluster id = id  (single word)
      subgraph Multi Word  → DOM cluster id = subGraphN (auto-generated, 0-indexed)
    """
    subgraphs: list[dict] = []
    stack: list[dict] = []
    auto_idx = 0  # increments when each group CLOSES (matches mmdc's subGraphN order)

    _node_id_pat = re.compile(r'^([A-Za-z0-9_][A-Za-z0-9_-]*)')
    # Include arrowless links (---, ===) so members on both sides are collected.
    _arrow_pat = re.compile(r'-+[-.=]*>|=[=]+>|---+|===[=]*')

    def _close_entry(entry: dict) -> None:
        """Assign a deferred ID and increment the counter; backfill waiting children."""
        nonlocal auto_idx
        if entry["id"] is None:
            entry["id"] = f"subGraph{auto_idx}"
        auto_idx += 1
        # Backfill any already-closed children whose parent was implicit at their
        # close time (i.e. it hadn't been assigned an ID yet).
        entry_id = entry["id"]
        for sg in subgraphs:
            if sg.get("_deferred_parent") is entry:
                sg["parent"] = entry_id
                del sg["_deferred_parent"]

    for line in source.splitlines():
        stripped = line.strip()

        if stripped == 'subgraph' or stripped.startswith('subgraph '):
            rest = stripped[len('subgraph'):].strip()
            # Single-token id (with optional [label]) anchored to end → explicit ID.
            # Anything else is a multi-word implicit title; ID deferred to close.
            _id_then_end = re.match(
                r'([A-Za-z0-9_.\-]+)(?:\s*\[\s*"?([^"\]]*)"?\s*\])?\s*$', rest
            )
            if _id_then_end:
                sg_id: str | None = _id_then_end.group(1)
                sg_label = (_id_then_end.group(2) or sg_id).strip()
            elif rest:
                sg_id = None  # implicit title; assigned in _close_entry
                sg_label = rest
            else:
                sg_id = None
                sg_label = ''

            sg_entry: dict = {"id": sg_id, "label": sg_label, "members": [], "parent": None}
            stack.append(sg_entry)
            continue

        if stripped == 'end' and stack:
            finished = stack.pop()
            _close_entry(finished)

            # Resolve parent: if parent is on the stack with a known ID, record it now.
            # If parent is still implicit (id=None), defer by storing a dict reference.
            if stack:
                parent_entry = stack[-1]
                if parent_entry["id"] is not None:
                    finished["parent"] = parent_entry["id"]
                else:
                    finished["_deferred_parent"] = parent_entry

            subgraphs.append(finished)
            continue

        if stack and stripped and not stripped.startswith(('%%', '//', 'flowchart', 'graph', 'direction')):
            # Collect all node IDs referenced on this line (node defs and edge endpoints).
            if _arrow_pat.search(stripped):
                clean = re.sub(r'\|[^|]*\|', '', stripped)
                parts = re.split(r'-+[-.=]*>|=[=]+>|---+|===[=]*|&', clean)
                for part in parts:
                    m2 = _node_id_pat.match(part.strip())
                    if m2:
                        nid = m2.group(1)
                        if nid not in stack[-1]["members"]:
                            stack[-1]["members"].append(nid)
            else:
                m2 = _node_id_pat.match(stripped)
                if m2:
                    nid = m2.group(1)
                    if nid not in stack[-1]["members"]:
                        stack[-1]["members"].append(nid)

    # Drain unclosed subgraphs (malformed source)
    while stack:
        entry = stack.pop()
        _close_entry(entry)
        subgraphs.append(entry)

    # Clean up any remaining deferred refs (shouldn't occur in valid Mermaid)
    for sg in subgraphs:
        sg.pop("_deferred_parent", None)

    return subgraphs


# ── JavaScript extraction payload ──────────────────────────────────────────────

_JS_EXTRACT = """
(args) => {
  const {entity_ids, relations, group_ids, svg_id_hint} = args;

  const svg = document.querySelector('svg');
  if (!svg) return {error: 'no svg element found'};

  const svgId = svg.id || svg_id_hint || '';

  // Fix SVG viewport to match viewBox so getCTM() returns viewBox coords (not CSS px).
  const vbStr = svg.getAttribute('viewBox') || svg.getAttribute('viewbox') || '';
  const vbParts = vbStr.trim().split(/[\\s,]+/).map(Number).filter(n => !isNaN(n));
  let canvasBounds = {x: 0, y: 0, width: 0, height: 0};
  if (vbParts.length === 4) {
    const [vx, vy, vw, vh] = vbParts;
    svg.setAttribute('width', vw);
    svg.setAttribute('height', vh);
    canvasBounds = {x: vx, y: vy, width: vw, height: vh};
  } else {
    const w = parseFloat(svg.getAttribute('width') || '0');
    const h = parseFloat(svg.getAttribute('height') || '0');
    canvasBounds = {x: 0, y: 0, width: w, height: h};
  }

  // Helpers ---------------------------------------------------------------

  function applyCtm(x, y, ctm) {
    const pt = svg.createSVGPoint();
    pt.x = x; pt.y = y;
    const tp = pt.matrixTransform(ctm);
    return [tp.x, tp.y];
  }

  // Get bbox of el in root SVG userspace via getBBox + getCTM.
  function svgBBox(el) {
    if (!el) return null;
    try {
      const bbox = el.getBBox();
      if (bbox.width === 0 && bbox.height === 0) return null;
      const ctm = el.getCTM();
      if (!ctm) return null;
      const corners = [
        applyCtm(bbox.x, bbox.y, ctm),
        applyCtm(bbox.x + bbox.width, bbox.y, ctm),
        applyCtm(bbox.x, bbox.y + bbox.height, ctm),
        applyCtm(bbox.x + bbox.width, bbox.y + bbox.height, ctm),
      ];
      const xs = corners.map(p => p[0]);
      const ys = corners.map(p => p[1]);
      const x0 = Math.min(...xs), y0 = Math.min(...ys);
      const x1 = Math.max(...xs), y1 = Math.max(...ys);
      if (!isFinite(x0) || !isFinite(y0)) return null;
      return {x: x0, y: y0, width: x1 - x0, height: y1 - y0};
    } catch(e) { return null; }
  }

  // Get foreignObject bbox via getScreenCTM inversion (for HTML labels).
  function foBBox(fo) {
    if (!fo) return null;
    try {
      const cr = fo.getBoundingClientRect();
      if (cr.width === 0 && cr.height === 0) return null;
      const rootCTM = svg.getScreenCTM();
      if (!rootCTM) return null;
      const inv = rootCTM.inverse();
      const corners = [
        applyCtm(cr.left, cr.top, inv),
        applyCtm(cr.right, cr.top, inv),
        applyCtm(cr.left, cr.bottom, inv),
        applyCtm(cr.right, cr.bottom, inv),
      ];
      const xs = corners.map(p => p[0]);
      const ys = corners.map(p => p[1]);
      const x0 = Math.min(...xs), y0 = Math.min(...ys);
      const x1 = Math.max(...xs), y1 = Math.max(...ys);
      if (!isFinite(x0) || !isFinite(y0)) return null;
      return {x: x0, y: y0, width: x1 - x0, height: y1 - y0};
    } catch(e) { return null; }
  }

  function samplePath(pathEl, n, ctm) {
    const pts = [];
    let localLen = 0;
    try { localLen = pathEl.getTotalLength(); } catch(e) {}
    if (localLen <= 0) return {points: [], length: 0};
    for (let i = 0; i < n; i++) {
      const t = n === 1 ? 0 : (i / (n - 1)) * localLen;
      const p = pathEl.getPointAtLength(t);
      pts.push(ctm ? applyCtm(p.x, p.y, ctm) : [p.x, p.y]);
    }
    // Compute arc length from root-coordinate points so the result is consistent
    // with the CTM-transformed sample positions (getTotalLength() is in local space).
    let rootLen = 0;
    for (let i = 1; i < pts.length; i++) {
      const dx = pts[i][0] - pts[i-1][0], dy = pts[i][1] - pts[i-1][1];
      rootLen += Math.sqrt(dx * dx + dy * dy);
    }
    return {points: pts, length: rootLen > 0 ? rootLen : localLen};
  }

  // Entity extraction -----------------------------------------------------
  const flowchartPrefix = svgId ? svgId + '-flowchart-' : 'flowchart-';
  const sortedEntityIds = [...entity_ids].sort((a, b) => b.length - a.length);

  const entities = [];
  const entityErrors = [];

  for (const g of svg.querySelectorAll('g.node[id]')) {
    const domId = g.getAttribute('id') || '';
    if (!domId.startsWith(flowchartPrefix)) continue;
    const remainder = domId.slice(flowchartPrefix.length);

    let matchedId = null;
    for (const eid of sortedEntityIds) {
      if (remainder === eid) { matchedId = eid; break; }
      const rest = remainder.slice(eid.length);
      if (remainder.startsWith(eid) && rest.startsWith('-') && /^\\d+$/.test(rest.slice(1))) {
        matchedId = eid; break;
      }
    }
    if (!matchedId) continue;

    // Primary shape: look for the visual container element.
    // Priority: element with class 'label-container' or 'outer-path',
    // then first visible SVG shape child.
    let shapeEl = null;
    const shapeSelectors = [
      ':scope > .label-container',
      ':scope > .outer-path',
      ':scope > g.label-container',
      ':scope > g.outer-path',
    ];
    for (const sel of shapeSelectors) {
      const el = g.querySelector(sel);
      if (el) { shapeEl = el; break; }
    }
    if (!shapeEl) {
      for (const child of g.children) {
        const tag = child.tagName.toLowerCase();
        if (['rect', 'circle', 'ellipse', 'polygon', 'path'].includes(tag)) {
          try {
            const bb = child.getBBox();
            if (bb.width > 0 || bb.height > 0) { shapeEl = child; break; }
          } catch(e) {}
        }
      }
    }

    const outerBBox = svgBBox(shapeEl || g);
    if (!outerBBox || outerBBox.width <= 0 || outerBBox.height <= 0) {
      entityErrors.push({id: matchedId, reason: 'zero-area bbox'});
      continue;
    }

    // Text bbox and line count.
    let textBBox = null;
    const fo = g.querySelector('foreignObject');
    if (fo) {
      const fw = parseFloat(fo.getAttribute('width') || '0');
      const fh = parseFloat(fo.getAttribute('height') || '0');
      if (fw > 0 && fh > 0) {
        textBBox = foBBox(fo) || svgBBox(fo);
        if (textBBox && textBBox.width <= 0) textBBox = null;
      }
    }
    if (!textBBox) {
      const textEl = g.querySelector('text');
      if (textEl) {
        textBBox = svgBBox(textEl);
      }
    }
    // text_lines is always 1 here to match the native SVG adapter; multi-line
    // scoring is deferred until native extraction implements line counting.
    const textLines = 1;

    entities.push({entity_id: matchedId, bbox: outerBBox, text_bbox: textBBox, text_lines: textLines});
  }

  // Group extraction ------------------------------------------------------
  const clusterPrefix = svgId ? svgId + '-' : '';
  const groups = [];
  const groupErrors = [];

  for (const g of svg.querySelectorAll('g.cluster[id]')) {
    const domId = g.getAttribute('id') || '';
    const groupId = clusterPrefix && domId.startsWith(clusterPrefix)
      ? domId.slice(clusterPrefix.length)
      : domId;

    if (group_ids.length > 0 && !group_ids.includes(groupId)) continue;

    const bbox = svgBBox(g);
    if (!bbox || bbox.width <= 0 || bbox.height <= 0) {
      groupErrors.push({id: groupId, reason: 'zero-area bbox'});
      continue;
    }
    groups.push({group_id: groupId, bbox});
  }

  // Edge extraction -------------------------------------------------------
  const extractedRelations = [];
  const relationErrors = [];

  // Map "src|tgt" -> [path elements] in document order.
  const pairPaths = {};
  for (const path of svg.querySelectorAll('path[data-id]')) {
    const dataId = path.getAttribute('data-id') || '';
    const withoutL = dataId.startsWith('L_') ? dataId.slice(2) : null;
    if (!withoutL) continue;
    for (const rel of relations) {
      const infix = rel.source + '_' + rel.target + '_';
      if (withoutL.startsWith(infix) && /^\\d+$/.test(withoutL.slice(infix.length))) {
        const key = rel.source + '|' + rel.target;
        if (!pairPaths[key]) pairPaths[key] = [];
        pairPaths[key].push(path);
        break;
      }
    }
  }

  // Self-loop paths: {node}-cyclic-special-{1,mid,2}
  const cyclicPaths = {};
  for (const path of svg.querySelectorAll('path[data-id]')) {
    const dataId = path.getAttribute('data-id') || '';
    const m = dataId.match(/^([A-Za-z0-9_][A-Za-z0-9_-]*)-cyclic-special-(\\d+|mid)$/);
    if (m) {
      const nid = m[1];
      if (!cyclicPaths[nid]) cyclicPaths[nid] = [];
      cyclicPaths[nid].push({path, suffix: m[2], dataId});
    }
  }

  const pairOccurrence = {};
  const usedPaths = new Set();
  const SUFFIX_ORDER = {'1': 0, 'mid': 1, '2': 2};

  const sortedRelations = [...relations].sort((a, b) => (a.order || 0) - (b.order || 0));

  for (const rel of sortedRelations) {
    const isSelfLoop = rel.source === rel.target;
    const key = rel.source + '|' + rel.target;
    if (!pairOccurrence[key]) pairOccurrence[key] = 0;
    const occ = pairOccurrence[key]++;

    if (isSelfLoop) {
      // Consume up to 3 cyclic-special segments per self-loop relation (1 set of arcs).
      // Filter first to preserve DOM occurrence order, then take the first 3 (one set)
      // before sorting by suffix for arc traversal. Sorting all before slicing would
      // interleave segments from different loops (1, 1, mid, mid, 2, 2 → wrong trio).
      const unusedCyclic = (cyclicPaths[rel.source] || [])
        .filter(e => !usedPaths.has(e.path))
        .slice(0, 3)
        .sort((a, b) => (SUFFIX_ORDER[a.suffix] ?? 99) - (SUFFIX_ORDER[b.suffix] ?? 99));
      if (unusedCyclic.length === 0) {
        relationErrors.push({id: rel.id, reason: 'no cyclic-special paths'});
        continue;
      }
      unusedCyclic.forEach(e => usedPaths.add(e.path));

      // Calculate total length of all segments.
      const segLengths = unusedCyclic.map(e => {
        try { return e.path.getTotalLength(); } catch(_) { return 0; }
      });
      const totalLen = segLengths.reduce((a, b) => a + b, 0);

      // Sample 32 and 128 points proportionally across segments.
      function sampleCombined(n) {
        const pts = [];
        if (totalLen <= 0) return pts;
        for (let i = 0; i < n; i++) {
          let t = n === 1 ? 0 : (i / (n - 1)) * totalLen;
          let segIdx = 0, cumLen = 0;
          while (segIdx < unusedCyclic.length - 1 && cumLen + segLengths[segIdx] < t) {
            cumLen += segLengths[segIdx++];
          }
          const localT = Math.min(t - cumLen, segLengths[segIdx] || 0);
          const pathEl = unusedCyclic[segIdx].path;
          const ctm = pathEl.getCTM();
          try {
            const p = pathEl.getPointAtLength(localT);
            pts.push(ctm ? applyCtm(p.x, p.y, ctm) : [p.x, p.y]);
          } catch(_) {}
        }
        return pts;
      }

      const sampled32 = sampleCombined(32);
      const dense128 = sampleCombined(128);
      if (sampled32.length === 0) {
        relationErrors.push({id: rel.id, reason: 'failed to sample self-loop'}); continue;
      }
      extractedRelations.push({
        relation_id: rel.id, source: rel.source, target: rel.target,
        source_point: sampled32[0], target_point: sampled32[sampled32.length - 1],
        sampled_points: sampled32, dense_points: dense128, path_length: totalLen,
      });
      continue;
    }

    // Regular edge: always take first unused path to preserve document order.
    const available = (pairPaths[key] || []).filter(p => !usedPaths.has(p));
    if (available.length === 0) {
      relationErrors.push({id: rel.id, reason: 'no path for ' + key}); continue;
    }
    const pathEl = available[0];
    usedPaths.add(pathEl);

    const ctm = pathEl.getCTM();
    const {points: sampled32, length: totalLen} = samplePath(pathEl, 32, ctm);
    const {points: dense128} = samplePath(pathEl, 128, ctm);

    if (sampled32.length === 0) {
      relationErrors.push({id: rel.id, reason: 'failed to sample path'}); continue;
    }

    extractedRelations.push({
      relation_id: rel.id, source: rel.source, target: rel.target,
      source_point: sampled32[0], target_point: sampled32[sampled32.length - 1],
      sampled_points: sampled32, dense_points: dense128, path_length: totalLen,
    });
  }

  return {
    canvas_bounds: canvasBounds, viewbox: vbStr,
    entities, groups, relations: extractedRelations,
    errors: {entities: entityErrors, groups: groupErrors, relations: relationErrors},
  };
}
"""


# ── browser manager ────────────────────────────────────────────────────────────

class PlaywrightBrowserManager:
    """Manages one Playwright Chromium browser across multiple SVG extractions."""

    def __init__(self) -> None:
        self._pw: Any = None
        self._pw_context: Any = None
        self._browser: Any = None

    def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        from playwright.sync_api import sync_playwright
        pw_context = sync_playwright()
        pw = pw_context.__enter__()
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception:
            try:
                pw_context.__exit__(None, None, None)
            except Exception:
                pass
            raise
        # Only assign after successful launch so close() is safe on partial init.
        self._pw_context = pw_context
        self._pw = pw
        self._browser = browser

    def browser_version(self) -> str:
        self._ensure_browser()
        return self._browser.version

    def playwright_version(self) -> str:
        try:
            import importlib.metadata
            return importlib.metadata.version("playwright")
        except Exception:
            return "unknown"

    def new_page(self, viewport_width: int = 1200, viewport_height: int = 900,
                 device_scale_factor: float = 1.0, locale: str = "en-US",
                 timezone: str = "UTC", reduced_motion: bool = True) -> Any:
        self._ensure_browser()
        context = self._browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height},
            locale=locale,
            timezone_id=timezone,
            device_scale_factor=device_scale_factor,
            reduced_motion="reduce" if reduced_motion else "no-preference",
        )
        page = context.new_page()
        # Block network requests — SVG is embedded directly
        page.route("**/*", lambda route: route.abort())
        return page

    def close(self) -> None:
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._pw is not None:
            self._pw = None
        # Call __exit__ on the context manager so it stops Playwright and
        # cleans up the event loop it owns (SyncPlaywright.stop() alone does not).
        ctx = getattr(self, "_pw_context", None)
        if ctx is not None:
            try:
                ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._pw_context = None

    def __enter__(self) -> "PlaywrightBrowserManager":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ── main extraction function ───────────────────────────────────────────────────

def _load_svg_page(page: Any, svg: str) -> None:
    """Load an SVG into a Playwright page with animations disabled."""
    html = (
        "<!DOCTYPE html><html>"
        "<head><style>*{animation:none!important;transition:none!important;"
        "animation-play-state:paused!important;caret-color:transparent!important;}"
        "body{margin:0;padding:0;background:white;}</style></head>"
        f"<body>{svg}</body></html>"
    )
    page.set_content(html, wait_until="domcontentloaded")
    page.evaluate("() => document.fonts.ready")
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )


def extract_flowchart_geometry(
    svg: str,
    semantic: SemanticDiagram,
    browser_manager: PlaywrightBrowserManager,
    source: str = "",
    viewport_width: int = 1200,
    viewport_height: int = 900,
    device_scale_factor: float = 1.0,
    locale: str = "en-US",
    timezone: str = "UTC",
    reduced_motion: bool = True,
) -> tuple[GeometryObservation, str | None]:
    """Extract flowchart geometry via Playwright DOM measurement.

    Returns (observation, error_reason).
    error_reason is None on success; on failure the observation has EXTRACTOR_GAP.
    """
    entity_ids = [e.id for e in semantic.entities]
    relations_data = [
        {"id": r.id, "source": r.source, "target": r.target, "order": r.order}
        for r in semantic.relations
    ]
    subgraphs = _parse_flowchart_subgraphs(source)
    group_ids = [sg["id"] for sg in subgraphs]

    page = browser_manager.new_page(
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        device_scale_factor=device_scale_factor,
        locale=locale,
        timezone=timezone,
        reduced_motion=reduced_motion,
    )
    try:
        _load_svg_page(page, svg)
        raw = page.evaluate(
            _JS_EXTRACT,
            {
                "entity_ids": entity_ids,
                "relations": relations_data,
                "group_ids": group_ids,
                "svg_id_hint": "",
            },
        )
    finally:
        try:
            page.context.close()
        except Exception:
            pass

    if isinstance(raw, dict) and "error" in raw:
        reason = f"JS extraction failed: {raw['error']}"
        return _gap_observation(reason), reason

    return _build_observation(raw, semantic, subgraphs)


def _gap_observation(reason: str) -> GeometryObservation:
    return GeometryObservation(
        coordinate_convention="css-top-left",
        content_bounds=None,
        canvas_bounds=None,
        viewbox=None,
        entities=[],
        groups=[],
        relations=[],
        containment=[],
        crossing_count=None,
    )


def _to_bbox(d: dict) -> BoundingBox:
    return BoundingBox(x=d["x"], y=d["y"], width=d["width"], height=d["height"])


def _build_observation(
    raw: dict,
    semantic: SemanticDiagram,
    subgraphs: list[dict],
) -> tuple[GeometryObservation, str | None]:
    """Convert raw JS result to GeometryObservation; validate completeness."""
    canvas_bounds = _to_bbox(raw["canvas_bounds"]) if raw.get("canvas_bounds") else None
    viewbox = raw.get("viewbox")

    # Entities
    entities: list[EntityGeometry] = []
    for e in raw.get("entities", []):
        bbox = _to_bbox(e["bbox"])
        text_bbox = _to_bbox(e["text_bbox"]) if e.get("text_bbox") else None
        entities.append(EntityGeometry(
            entity_id=e["entity_id"],
            bbox=bbox,
            text_bbox=text_bbox,
            text_lines=e.get("text_lines", 1),
        ))
    # Stable ordering
    entities.sort(key=lambda e: e.entity_id)

    # Groups
    groups: list[GroupGeometry] = []
    for g in raw.get("groups", []):
        groups.append(GroupGeometry(group_id=g["group_id"], bbox=_to_bbox(g["bbox"])))
    groups.sort(key=lambda g: g.group_id)

    # Entity bbox lookup for side inference
    entity_bbox_map: dict[str, BoundingBox] = {e.entity_id: e.bbox for e in entities}

    # Relations
    relations: list[RelationGeometry] = []
    for r in raw.get("relations", []):
        sp = tuple(r["source_point"]) if r.get("source_point") else None
        tp = tuple(r["target_point"]) if r.get("target_point") else None
        sampled = [tuple(p) for p in r.get("sampled_points", [])]
        dense = [tuple(p) for p in r.get("dense_points", [])]

        source_side = _infer_side(sp, entity_bbox_map[r["source"]]) if (sp and r["source"] in entity_bbox_map) else None
        target_side = _infer_side(tp, entity_bbox_map[r["target"]]) if (tp and r["target"] in entity_bbox_map) else None

        bend = _compute_bend_count(dense)

        relations.append(RelationGeometry(
            relation_id=r["relation_id"],
            source_point=sp,
            target_point=tp,
            source_side=source_side,
            target_side=target_side,
            sampled_points=sampled,
            bend_count=bend,
            path_length=r.get("path_length"),
        ))
    # Order by semantic relation order
    rel_order = {r["relation_id"]: r.get("order", 0) for r in raw.get("relations", [])}
    relations.sort(key=lambda r: rel_order.get(r.relation_id, 0))

    # Containment from source parsing
    containment: list[tuple[str, str]] = []
    entity_id_set = {e.entity_id for e in entities}
    group_id_set = {g.group_id for g in groups}
    for sg in subgraphs:
        for member in sg["members"]:
            if member in entity_id_set and sg["id"] in group_id_set:
                containment.append((member, sg["id"]))
    containment.sort()

    # Content bounds: union of entity boxes + group boxes + relation samples
    all_xs: list[float] = []
    all_ys: list[float] = []
    for e in entities:
        all_xs += [e.bbox.x, e.bbox.right]
        all_ys += [e.bbox.y, e.bbox.bottom]
    for g in groups:
        all_xs += [g.bbox.x, g.bbox.right]
        all_ys += [g.bbox.y, g.bbox.bottom]
    # Exclude relation sampled points: native adapter derives bounds from entities+groups
    # only, so including edge waypoints here would create asymmetric normalization.

    content_bounds: BoundingBox | None = None
    if all_xs:
        cx0, cx1 = min(all_xs), max(all_xs)
        cy0, cy1 = min(all_ys), max(all_ys)
        content_bounds = BoundingBox(x=cx0, y=cy0, width=cx1 - cx0, height=cy1 - cy0)

    # Crossing count
    crossing_count = _compute_crossing_count(relations)

    obs = GeometryObservation(
        coordinate_convention="css-top-left",
        content_bounds=content_bounds,
        canvas_bounds=canvas_bounds,
        viewbox=viewbox,
        entities=entities,
        groups=groups,
        relations=relations,
        containment=containment,
        crossing_count=crossing_count,
    )

    # Completeness validation
    error_reason = _validate_completeness(obs, semantic)
    return obs, error_reason


def _validate_completeness(obs: GeometryObservation, semantic: SemanticDiagram) -> str | None:
    """Validate that geometry matches semantic. Returns error reason string or None."""
    diags: list[str] = []

    sem_entity_ids = {e.id for e in semantic.entities}
    obs_entity_ids = {e.entity_id for e in obs.entities}
    missing_entities = sem_entity_ids - obs_entity_ids
    extra_entities = obs_entity_ids - sem_entity_ids
    if missing_entities:
        diags.append(f"missing entity geometry: {sorted(missing_entities)}")
    if extra_entities:
        diags.append(f"extra entity geometry: {sorted(extra_entities)}")

    sem_group_ids = {g.id for g in semantic.groups}
    obs_group_ids = {g.group_id for g in obs.groups}
    missing_groups = sem_group_ids - obs_group_ids
    if missing_groups:
        diags.append(f"missing group geometry: {sorted(missing_groups)}")
    for g in obs.groups:
        if g.bbox.width <= 0 or g.bbox.height <= 0:
            diags.append(f"zero-area bbox for group {g.group_id!r}")

    sem_rel_ids = {r.id for r in semantic.relations}
    obs_rel_ids = {r.relation_id for r in obs.relations}
    missing_rels = sem_rel_ids - obs_rel_ids
    extra_rels = obs_rel_ids - sem_rel_ids
    if missing_rels:
        diags.append(f"missing relation geometry: {sorted(missing_rels)}")
    if extra_rels:
        diags.append(f"extra relation geometry: {sorted(extra_rels)}")

    for e in obs.entities:
        if e.bbox.width <= 0 or e.bbox.height <= 0:
            diags.append(f"zero-area bbox for entity {e.entity_id!r}")
        if not (math.isfinite(e.bbox.x) and math.isfinite(e.bbox.y)):
            diags.append(f"non-finite bbox for entity {e.entity_id!r}")

    for r in obs.relations:
        if len(r.sampled_points) != 32:
            diags.append(f"relation {r.relation_id!r} has {len(r.sampled_points)} samples (expected 32)")
        if r.path_length is not None and r.path_length <= 0:
            diags.append(f"relation {r.relation_id!r} has non-positive path length")
        if r.source_point and not all(math.isfinite(v) for v in r.source_point):
            diags.append(f"relation {r.relation_id!r} has non-finite source_point")
        if r.target_point and not all(math.isfinite(v) for v in r.target_point):
            diags.append(f"relation {r.relation_id!r} has non-finite target_point")

    if obs.content_bounds is None and (sem_entity_ids or sem_rel_ids):
        diags.append("content_bounds is null with semantic content present")

    if diags:
        return "; ".join(diags)
    return None
