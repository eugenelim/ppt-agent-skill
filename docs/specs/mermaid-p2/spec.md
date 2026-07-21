# Mermaid P2 — Semantic Renderer and Native SVG Backend

**Mode: full (structural change + multi-feature + unfamiliar territory)**

Status: Implementing

## Objective

Replace the Playwright/dom-to-svg SVG export path with a deterministic pure-Python
native SVG backend driven by an immutable paint scene IR. Simultaneously, implement
Mermaid-faithful semantic rendering for five diagram families whose visual grammar
requires custom treatment.

## Prerequisites (P0/P1 — verified)

- `FinalizedLayout`, `NodeLayout`, `GroupLayout`, `PortLayout`, `RoutedEdge`, `TextLayout`
  all exist in `scripts/mermaid_render/layout/_geometry.py` ✓
- Pillow-backed text measurement (`PillowTextMeasurer`) ✓
- Typed renderer configuration (`FlowchartLayoutConfig`, `C4LayoutConfig`, `RenderConfig`) ✓
- Named layered-layout strategies (LongestPathRanker, BrandesKoepfAssigner, etc.) ✓
- Architecture side-port preservation in `_routing.py` ✓
- Recursive compound-graph layout in `_layout.py` ✓
- Content-tight diagram bounds (`visible_bounds` in `FinalizedLayout`) ✓
- P0/P1 structural tests pass ✓

**Gap from P0/P1:** The HTML renderer (`_render_graph_fragment`) still operates on
mutable `_Node`/`_Edge` objects, not `FinalizedLayout`. The P2 native SVG path will
use the same layout algorithms but bypass HTML serialization.

## Boundaries

**In scope:**
- `scripts/mermaid_render/scene.py` — new SvgScene IR module
- `scripts/mermaid_render/svg_serializer.py` — new lxml-based serializer
- `scripts/mermaid_render/paint.py` — layout→scene converter (generic + semantic)
- `scripts/mermaid_render/__init__.py` — switch to_svg() to native backend
- `scripts/mermaid_render/layout/mindmap.py` — tidy-tree mindmap
- `scripts/mermaid_render/layout/timeline.py` — semantic timeline columns
- `scripts/mermaid_render/layout/architecture.py` — architecture layout
- `scripts/mermaid_render/layout/c4_layout.py` — C4 layout
- `scripts/mermaid_render/layout/state.py` — state hierarchy
- `scripts/mermaid_render/paint/` — per-type painters
- New test files per the spec's REQUIRED TEST FILES section

**Out of scope:**
- P3 repository reorganization
- Modifying `scripts/html2svg.py` or the general slide HTML conversion pipeline
- Redesigning diagram types not in the P2 five (flowchart, class, ER, etc.)
- Adding new production dependencies

## Acceptance Criteria

- [x] P0/P1 prerequisites verified
- [x] Typed immutable `SvgScene` exists with all required primitives
- [x] SVG serializer produces deterministic, valid SVG from `SvgScene`
- [x] `to_svg()` does not import or launch Playwright
- [x] `to_svg()` does not call `documentToSVG`
- [x] Native SVG contains no `<foreignObject>`
- [x] Native SVG contains no `html/head/body` elements
- [x] Native SVG IDs and float formatting are deterministic
- [x] Native SVG text uses `<text>` / `<tspan>` based on `TextLayout`
- [x] Every supported Mermaid diagram type has a native-scene path
- [ ] `layout: tidy-tree` selects tidy-tree Mind Map strategy (deferred: backlog-mindmap-tidy-tree)
- [x] Default radial Mind Map behavior still covered independently
- [ ] Tidy-tree uses variable measured node dimensions (deferred: backlog-mindmap-tidy-tree)
- [ ] Tidy-tree: zero node overlap and zero tree-edge crossings on regression set (deferred: backlog-mindmap-tidy-tree)
- [x] Timeline source order preserved
- [x] Timeline continuation events belong to correct task column
- [x] Timeline uses task/event columns (not alternating above/below)
- [x] Timeline task and event boxes do not overlap
- [x] Architecture services use semantic icon tiles (not generic narrow cards)
- [x] Architecture labels do not shrink service tiles
- [x] Architecture group icons, labels, and boundaries rendered
- [x] Architecture fixed port sides honored
- [ ] Architecture bidirectional relations: one path, two markers (deferred: backlog-arch-bidir)
- [x] No Architecture legend invented by default
- [ ] C4: ordinary, person, database, queue, external painters are distinct (deferred: backlog-c4-shapes)
- [x] C4: technology and description painted separately
- [x] C4: recursive boundaries painted and contain descendants
- [ ] C4: directional hints affect endpoints/routes (deferred: backlog-c4-birel)
- [ ] C4: BiRel uses one path and two markers (deferred: backlog-c4-birel)
- [x] C4: relation labels and technology avoid element interiors
- [ ] State: initial/final pseudo-states use correct shapes (not placeholder text) (deferred: backlog-state-semantics)
- [ ] State: composite states contain their internal machines (deferred: backlog-state-semantics)
- [ ] State: no atomic+composite duplicate for same state (deferred: backlog-state-semantics)
- [ ] State: notes anchored to declared side (deferred: backlog-state-semantics)
- [ ] State: external transitions use composite boundary gates (deferred: backlog-state-semantics)
- [ ] State: self-loops clear owning node (deferred: backlog-state-semantics)
- [x] Every P2 fixture is content-tight
- [x] Marker tips and labels inside viewBox
- [x] Native SVG passes SVG-to-PowerPoint path
- [x] `to_html()` remains pure Python and Playwright-free
- [x] Public API backward-compatible
- [x] P0/P1 structural tests still pass
- [x] Full test suite passes
- [x] `notes/mermaid-p2-report.md` completed

## Testing Strategy

- TDD for SvgScene IR and serializer (frozen dataclasses, pure functions)
- Goal-based for native backend switch (grep: no playwright import in to_svg path)
- TDD for tidy-tree algorithm (overlap assertions, crossing count assertions)
- TDD for timeline column layout (source-order, column membership assertions)
- TDD for architecture, C4, state painters (shape-kind assertions, containment assertions)
- Visual/manual QA for end-to-end SVG output quality (compare galleries)

## Assumptions

1. The existing layout algorithms (Sugiyama, A* routing) produce correct coordinates for
   non-P2-target types — we preserve their geometry in the native SVG path.
2. `lxml` is sufficient for deterministic SVG serialization (already a dependency).
3. The `mmdc --version` oracle is pinned at 11.15.0.
4. Pillow font resolution is stable across runs on the same machine.

## Declined patterns

- Tempted to use a full scene-graph render tree with retained-mode updates — declining;
  the spec requires immutable frozen dataclasses, which precludes retained-mode.
- Tempted to use a Python SVG library (svgwrite, drawsvg) — declining; spec requires
  no new dependencies; lxml already available.
- Tempted to redesign the HTML renderer to use FinalizedLayout — declining; that's P3
  work; the native SVG path uses the same mutable layout objects as intermediate.
- Tempted to share the geometry computation between `to_html()` and `to_svg()` via
  caching — declining; separate calls are separate renders; consistency is guaranteed
  by determinism, not shared state.
