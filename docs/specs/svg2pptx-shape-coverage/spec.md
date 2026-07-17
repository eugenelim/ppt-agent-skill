# Spec: svg2pptx SVG basic-shape coverage

Mode: light (no risk trigger fired)

- **Status:** Shipped <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Constrained by:** none

## Objective

`scripts/svg2pptx.py` converts inline SVG to native PPTX shapes for the
PowerPoint export path. It handles `rect`, `circle`, `ellipse`, `line`,
`path`, `text`, `image`, and `g`, but its `_walk` dispatch has **no case for
`<polygon>` or `<polyline>`** — the two remaining SVG basic shapes. Both fall
through the `else` branch, which recurses into children; a leaf shape has none,
so it is **silently dropped** (no `skipped`/`errors` stat, no warning).

Consequence: every arrowhead the renderer emits is a `<polygon>`
(`mermaid_layout/_routing.py:_arrowhead` → `_renderer.py`/`_strategies.py`, and
`html2svg.py`'s CSS-border-arrow preprocessing), so **arrows disappear in the
PPTX**. Confirmed empirically: a probe SVG with `rect`+`path`+`polygon`+`polyline`
converts only the `rect` and `path` (2 shapes), silently dropping the other two.

Make svg2pptx support the **full SVG basic-shapes surface** (guiding principle:
everything in the SVG spec the renderer uses should convert), and make the
*class* of silent-drop bug loud so a future gap surfaces instead of vanishing.

**Amendment (after rebasing onto #55 `mermaid-renderer-uplift`):** #55 replaced
per-edge `<polygon>` arrowheads with `<marker>` + `marker-end`, where the
arrowhead geometry now lives inside `<defs>`. dom-to-svg preserves
`<defs>`/`<marker>`/`marker-end` verbatim (it does not inline markers), and
svg2pptx *skips* `<defs>` and ignores `marker-end` — so **edge arrowheads are
lost in the PPTX** even with the basic-shape fix (which still fixes the legend
arrows and sequence-note dog-ears, which are body polygons). This spec now also
covers resolving `<marker>`/`marker-end` so the edge arrows survive. Both halves
matter: basic-shapes for arbitrary external SVGs, marker resolution for our own
renderer output.

## Acceptance Criteria

- [x] `<polygon>` converts to a native PPTX shape, reusing the existing
      `<path>` → `custGeom` codepath (points → `M … L … Z`), preserving
      `fill`, `stroke`, `stroke-width`, and `opacity`.
- [x] `<polyline>` converts the same way, **open** (no closing `Z`).
- [x] A probe SVG with `rect`+`path`+`polygon`+`polyline` yields **4** converted
      shapes (was 2).
- [x] Arrowheads survive end-to-end: the mermaid renderer's `<polygon>` arrowhead
      output converts through svg2pptx (verified via probe reproducing the
      `_arrowhead` point-string shape, and a real html2svg→svg2pptx run).
- [x] An **unrecognized leaf rendering element** is no longer silently swallowed:
      it increments a visible `unhandled` counter and warns once to stderr
      (non-rendering leaves — `title`/`desc`/`metadata` — and comment/PI nodes
      with falsy tags are exempt; containers still recurse as before).
- [x] `pytest tests/` (356) and `python scripts/smoke_test.py --phase 5` stay
      green; no regression in existing shape conversion.

Marker resolution (amendment):

- [x] A `<path>`/`<line>`/`<polyline>`/`<polygon>` carrying `marker-end` (and
      `marker-start`) draws the referenced `<defs>` `<marker>` geometry as a
      concrete oriented shape at the path vertex — `<defs>` markers are otherwise
      skipped, so this is the only path by which they render.
- [x] Markers defined in `<defs>` but never referenced are **not** drawn
      (no double-draw / no stray shapes).
- [x] Orientation honors `orient="auto"` (tangent at the vertex),
      `auto-start-reverse`, and a fixed numeric angle; placement honors
      `refX`/`refY`, `viewBox`, `markerWidth`/`markerHeight`, and `markerUnits`
      (`userSpaceOnUse` vs `strokeWidth`).
- [x] A `marker-end` referencing a missing id does not crash; the base shape
      still converts.
- [x] End-to-end: the mermaid renderer's marker-based edge arrows survive
      `renderer → html2svg → svg2pptx` (verified on a real flowchart: 42 → 47
      shapes, the 5 edge arrows).

## Boundaries

In scope: `scripts/svg2pptx.py` element dispatch (svg2pptx-side fix per user
direction). Out of scope: the renderer / html2svg (they legitimately emit
`<polygon>`; the fix belongs in the converter). Attribute-completeness beyond
what the reused `<path>` codepath already supports is out of scope — noted below.

## Assumptions

1. dom-to-svg preserves inline `<polygon>` as `<polygon>` into the SVG fed to
   svg2pptx — evidenced by `html2svg.py:309-317` emitting `<polygon>` as its own
   arrow output, and by the confirmed unit-level drop.
2. Reusing `_path` gives polygons/polylines identical fidelity to the `<path>`
   triangles that already convert correctly in production (same `custGeom`).
3. No production SVG relies on polygon/polyline being dropped — they are
   arrowheads that are *supposed* to render.

## Declined patterns

- Tempted to fix `_path`'s `(bx+ox)*scale` vs `_line`'s `coord*scale+ox`
  transform inconsistency — declining; path triangles convert correctly at
  scale=1 in production and touching it risks regressing the working path
  codepath. Noted in `notes/`.
- Tempted to add a full SVG **attribute** completeness pass (dasharray/linecap on
  polygons, `fill-rule`, `<marker>`) — declining; scope is *shape-element*
  coverage. Reusing `_path` inherits exactly the attribute support paths have.
- Tempted to fix it renderer-side (emit `<path>` triangles instead of
  `<polygon>`) — declining; user's explicit direction is the sustainable
  single-point fix in svg2pptx, which also covers `html2svg`'s CSS-arrow polygons
  and any future polygon use. (This also makes `references/pipeline-compat.md:18`'s
  existing "use inline SVG `<polygon>`" recommendation *true*.)

## Testing Strategy

TDD. `tests/test_svg2pptx_shapes.py` (pytest, `sys.path.insert` import pattern):
drive `SvgConverter.convert` on in-memory probe SVGs, assert on the `stats`
counters (the observable conversion result) — `shapes` for polygon/polyline/
path/rect, `unhandled` for an unknown leaf, and that fill/stroke are emitted.
Plus the phase-2 smoke test for no end-to-end regression.
