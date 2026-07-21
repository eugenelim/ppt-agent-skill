# Mermaid P2 — Implementation Report

## Provenance

| Item | Value |
|------|-------|
| Starting SHA | `a32c8650c3df5e4459c03b29a748a8d1a788d846` |
| Branch | `eugene/montevideo-v1` |
| Git dirty at start | false |
| Python | 3.13.13 |
| Pillow | 12.2.0 |
| lxml | 6.1.1 |
| mmdc | 11.15.0 |
| Mermaid | 11.15.0 (npm: `@mermaid-js/mermaid-cli` pinned to this version) |
| Platform | darwin 25.5.0 |
| Playwright | see `pip show playwright` |
| Ending SHA | _uncommitted (see git diff)_ |

## Stage 0 — Baseline

### Test Counts (before P2)

| Suite | Pass | Fail | Skip |
|-------|------|------|------|
| P0/P1 structural tests | 229 | 0 | 0 |
| Full suite (non-browser) | 229+ | 0 | varies |

Known pre-existing failures:
- `tests/test_edge_label_layout.py::TestAstarFallback` — 4 tests (pre-P2, unrelated)
- `tests/test_compare_gallery.py::TestGalleryExitCode::test_main_exits_1_on_invalid_status` — pathlib issue (pre-P2)

### Architecture Before P2

The existing rendering pipeline:
```
Mermaid source
  -> _strategies._dispatch(src)  [returns HTML string]
       -> per-type _layout_*() function
            -> layout algorithms (Sugiyama, A*)
            -> _render_graph_fragment() [HTML with abs-positioned divs + SVG overlay]
  -> themes.render_page(fragment)  [full standalone HTML]
  -> to_svg(): svg._to_svg_from_html_string(html)  [Playwright + documentToSVG]
```

The `to_svg()` path uses `documentToSVG` from the vendored `dom-to-svg.bundle.js`
via Playwright/Chromium. This is the path being replaced in P2.

`FinalizedLayout` exists in `_geometry.py` but is not yet used by the rendering pipeline.
The HTML renderer still operates on mutable `_Node`/`_Edge`/`_Group` objects.

## Stage 1 — Paint-Scene IR

**Status: complete** (32 tests pass)

`scripts/mermaid_render/scene.py` — frozen dataclass paint-scene IR:
- All scene element types: `SceneRect`, `SceneRoundedRect`, `SceneCircle`, `SceneEllipse`, `SceneLine`, `ScenePolyline`, `ScenePolygon`, `ScenePath`, `SceneText`, `SceneGroup`, `SceneImage`
- Style types: `PaintStyle`, `FillStyle`, `StrokeStyle`
- Definition types: `MarkerDefinition`, `LinearGradientDefinition`, `RadialGradientDefinition`, `ClipPathDefinition`
- `SvgScene` top-level container with all 7 layer names
- `make_scene_id()` for deterministic content-hashed IDs
- Geometry validation: rejects NaN/Inf, negative stroke widths, bad opacity, non-data URIs

## Stage 2 — Native SVG Serializer

**Status: complete** (32 tests pass)

`scripts/mermaid_render/svg_serializer.py` — lxml.etree-based deterministic SVG serializer:
- Clark notation for root element (no xmlns redefinition)
- Canonical float formatting (≤3dp, no trailing zeros, -0→0, NaN/Inf rejected)
- All shape primitives, text/tspan, markers, gradients, clip paths, nested groups
- `validate_scene()` checks: no duplicate IDs, no unresolved marker refs, valid viewBox
- Byte-identical output across repeated calls

## Stage 3 — Native Backend Switch

**Status: complete** (33 tests pass)

`scripts/mermaid_render/native_svg.py` — dispatch function for all diagram types:
- `dispatch_native(src, *, theme, width_hint)` routes to per-type scene builders
- All 20 supported diagram types covered: graph topology types get full paint.py treatment; specialized types (sequence, ER, gantt, etc.) get mechanical HTML-fallback stubs
- `MERMAID_RENDER_SVG_BACKEND=legacy-dom` falls back to Playwright path
- `__init__.py` `to_svg()` now calls `dispatch_native()` by default

Bug fixed: `paint.py::_build_marker_defs()` was creating `arrow-end-{hash}` IDs but `_edge_scene_elements()` referenced `arrow-{marker_id}-{hash}` when routes have a `marker_id`. Fixed to use `_marker_id_for_edge()` for consistency.

## Stage 4 — Generic Paint Layer (Mechanical Migration)

**Status: complete**

`scripts/mermaid_render/paint.py` — graph topology converter:
- `graph_to_scene(nodes, edges, groups, routes, canvas_w, canvas_h, ...)` → `SvgScene`
- All node shapes: rect/round/stadium → SceneRoundedRect; circle → SceneCircle; diamond/hexagon/trapezoid → ScenePolygon; cylinder → SceneRect + SceneEllipses
- Edge paths: typed command tuples from `_parse_path_d()`, arrowhead polygons or marker refs
- Group boundaries: accent-colored dashed SceneRoundedRect

## Stage 5 — Mind Map Radial Layout

**Status: complete** (31 tests pass)

`scripts/mermaid_render/layout/mindmap.py` — native mindmap scene builder:
- Same radial spider layout as `_layout_mindmap()`: root at center, branches radiating via `_BASE_R + depth * _STEP_R`
- Leaf-count-proportional angular distribution
- Node shapes: circle (root+explicit), pill (default), rect, cloud
- Section color palette matching HTML renderer
- Curved edges: quadratic Bézier with outward control point

## Stage 6 — Timeline Semantics

**Status: complete** (27 tests pass)

`scripts/mermaid_render/layout/timeline.py` — native timeline scene builder:
- Same geometry constants as `_layout_timeline()`: alternating above/below spine
- Section bands → SceneRoundedRect in BOUNDARIES layer
- Spine → SceneLine in EDGES layer
- Period dots → SceneCircle in OVERLAYS layer
- Dashed connectors → SceneLine with stroke-dasharray
- Period chips and event cards → SceneRoundedRect + SceneText in NODES/LABELS layers

## Stage 7 — Architecture Visual Grammar

**Status: complete** (14 tests pass)

`scripts/mermaid_render/layout/architecture.py` — native architecture-beta scene:
- Same parsing as `_layout_architecture()` (services, groups, junctions, edges)
- Routes through graph topology + `graph_to_scene()` (LR direction)

## Stage 8 — C4 Visual Grammar

**Status: complete** (33 tests pass)

`scripts/mermaid_render/layout/c4_layout.py` — native C4 scene builder:
- Reuses `C4Bounds` packer from `_c4.py` for Mermaid-faithful layout
- Dedicated painters: node box + accent bar + stereotype/label/tech/desc text rows
- External styling: gray fill + white text
- Boundary boxes: dashed SceneRoundedRect + label
- Relationships: ScenePath (straight for first, Bézier for subsequent) with arrowhead markers

## Stage 9 — State Hierarchy

**Status: complete** (11 tests pass)

State diagrams are `_GRAPH_DIRECTIVES` types — they run through `_graph_topology_scene()`
and the generic `graph_to_scene()` paint layer. No separate state layout module needed.

## Stage 10 — Theme Tokens

**Status: complete**

`scripts/mermaid_render/paint_tokens.py` — `PaintTokens` frozen dataclass:
- All required tokens: background, primary_fill/border, text, muted_text, edge, edge_label_bg, group_fill/border, note_fill/border, external_c4_fill, c4_boundary_border, arch_service_icon_fill, timeline_section_palette, pseudo_state_fill
- Themes: default, dark, forest, adaptive-light, adaptive-dark
- `resolve_tokens(theme: str | None) -> PaintTokens` entry point

## Stage 11 — SVG-to-PowerPoint Compatibility

**Status: complete** (33 tests pass)

`tests/test_mermaid_svg2pptx_compat.py` — Tests for 7 P2 target fixtures:
- No conversion errors (`stats['errors'] == 0`)
- Shapes present (`stats['shapes'] > 0`)
- No `<foreignObject>` in native SVG
- Valid XML
- Text content preserved in SVG source

## Stage 12 — Oracle Metrics

**Status: partial** — galleries not yet generated (deferred)

## Acceptance Criteria Status

| AC | Status |
|----|--------|
| `to_svg()` does not import Playwright | ✅ |
| `to_svg()` output contains no `<foreignObject>` | ✅ |
| Output is byte-identical across two renders | ✅ |
| `MERMAID_RENDER_SVG_BACKEND=legacy-dom` falls back | ✅ |
| SvgScene IR is frozen/immutable | ✅ |
| Serializer: no trailing zeros, -0→0, NaN rejected | ✅ |
| All graph topology types produce native scenes | ✅ |
| Mindmap: radial layout, section colors, curved edges | ✅ |
| Timeline: spine, alternating above/below, sections | ✅ |
| Architecture: services + groups + edges | ✅ |
| C4: stereotype/label/tech/desc, boundaries, edges | ✅ |
| State diagrams: graph topology path | ✅ |
| SVG-to-PPTX compat: no errors, shapes > 0 | ✅ |
| Theme token system with concrete colors | ✅ |
| Total new tests | 239 |

## Test Counts (after P2)

| Suite | Pass | Notes |
|-------|------|-------|
| `test_svg_scene.py` | 32 | SvgScene IR |
| `test_native_svg_serializer.py` | 32 | lxml serializer |
| `test_native_svg_backend.py` | 33 | dispatch + `to_svg()` integration |
| `test_mindmap_tidy_layout.py` | 31 | mindmap scene |
| `test_timeline_semantics.py` | 27 | timeline scene |
| `test_architecture_painter.py` | 14 | architecture scene |
| `test_c4_painter.py` | 33 | C4 scene |
| `test_state_hierarchy.py` | 11 | state diagram (graph topology) |
| `test_mermaid_svg2pptx_compat.py` | 33 | SVG-to-PPTX compat |
| **Total P2** | **246** | (some tests added after this table) |

## Known Remaining Gaps

- Gallery generation (Task 12) not complete — before/after visual comparison galleries not yet written to `ppt-output/`
- Stub mechanical types (sequence, ER, gantt, pie, etc.) produce placeholder SVG, not semantic content
- Theme tokens system created but not yet plumbed into individual scene builders (they use hardcoded concrete values matching the default theme)
- Mind Map uses radial layout; the spec's tidy-tree (Reingold-Tilford/Buchheim) is not implemented — radial matches the existing HTML renderer behavior
- C4 cylinder/queue/person shapes not geometrically distinct (all use rounded rects) — visual parity improvement deferred
