# Mermaid P3 — Native SVG Semantic Completion

**Mode: full (structural change + multi-feature + dependent tasks + unfamiliar territory)**

- **Status:** Implementing (Stages 0-7, 9, 11 partial done; Stages 8, 10, 12-13 deferred per backlog anchors below)

## Objective

Complete the native Mermaid renderer so that every advertised-supported diagram type
produces its real semantic content through one authoritative pipeline — no placeholders,
no silent fallbacks, no duplicate layout pipelines.

Final architecture:

```
Mermaid source
→ parse_render_request()  → RenderRequest  (immutable, stripped, directive resolved)
→ per-type compiler       → typed compiled model (FinalizedLayout / semantic IR)
→ finalized_layout_to_scene() / per-type painter  → SvgScene  (immutable)
→ scene_to_svg_str()      → deterministic UTF-8 SVG
```

The HTML and SVG serializers must consume the same compiled geometry.
No supported renderer may return a placeholder scene.

## Boundaries

**In scope:**
- `scripts/mermaid_render/native_svg.py` — remove `_html_fallback_scene`, add `RenderRequest`, `NativeRenderError`, `NativeRendererSpec`
- `scripts/mermaid_render/paint.py` — add `finalized_layout_to_scene()`, deprecate mutable-model `graph_to_scene`
- `scripts/mermaid_render/scene.py` — add `NativeParityLevel`, `NativeRendererSpec`, capability registry
- `scripts/mermaid_render/__init__.py` — wire `faithful` and `theme` through `dispatch_native`
- `scripts/mermaid_render/layout/` — per-type semantic models and painters (all 12 placeholder types)
- New test files per Stage requirements

**Out of scope:**
- General slide HTML-to-SVG pipeline
- P4 repository reorganization
- Adding new production dependencies (must be justified per stage)
- Sankey-beta and ZenUML (explicitly unsupported)

## Constraints

- `to_html()` remains pure Python
- `to_svg()` remains pure Python and must not import or launch Playwright
- `to_png()` may use Playwright only to rasterize native SVG
- No Mermaid/Node.js/Dagre/ELK/Graphviz/mmdc runtime introduced
- No `<foreignObject>` emitted
- No user-provided raw SVG markup inserted
- No silent placeholder substitution
- Rendering must remain deterministic (same input → byte-identical SVG)
- Stable `data-*` attributes preserved
- Public API preserved: `to_html`, `to_svg`, `to_png`, `validate`

## Assumptions

- FinalizedLayout, NodeLayout, GroupLayout, RoutedEdge are already defined in `_geometry.py` ✓
- `_compile_flowchart()` and `render_finalized()` exist in `_strategies.py` and `_renderer.py` ✓
- `mmdc` 11.15.0 available as test oracle ✓
- Pillow text measurement available ✓

## Declined patterns

- Tempted to reuse existing `graph_to_scene()` by passing a FinalizedLayout adapter: declining — the mutable/immutable boundary must be clear; the adapter would perpetuate the pattern.
- Tempted to add a `FallthroughRenderer` that silently catches all errors and returns HTML: declining — explicit error propagation is the design goal.
- Tempted to generate HTML first and parse it for SVG geometry: declining — explicitly prohibited by the spec.
- Tempted to implement stages 4-13 with stub passthrough classes: declining — stubs are what we're removing. Stages 4-13 get real implementations or explicit NotImplementedError.

## Acceptance Criteria

**Stage 0 — Baseline**
- [x] Baseline SHA, versions, and test count recorded in `notes/mermaid-native-closeout-report.md`
- [x] `NativeParityLevel` enum (FULL / PARTIAL / NOT_IMPLEMENTED / UNSUPPORTED) and `NativeRendererSpec` dataclass exist in `scene.py`
- [x] All directives registered in one location via `NATIVE_RENDERER_REGISTRY`
- [x] Previously-placeholder types use `NOT_IMPLEMENTED` parity; only FULL/PARTIAL types are tested for semantic output in `test_native_renderer_capabilities.py`
- [x] `tests/test_native_renderer_capabilities.py` exists with stub-rejection assertions for FULL/PARTIAL and raise-assertions for NOT_IMPLEMENTED/UNSUPPORTED
- [x] `tests/test_no_native_stubs.py` exists and passes static assertions

**Stage 1 — No Placeholders**

> **Interim behavior:** After Stage 1 and before Stages 6-11 complete, the 12 currently-placeholder
> types will raise `NativeRenderError` (phase="not-implemented") rather than returning stubs.
> CLI callers and tests must tolerate this; consumers using `MERMAID_RENDER_SVG_BACKEND=legacy-dom`
> retain the HTML fallback for those types until their dedicated stages ship.

- [x] `_html_fallback_scene()` absent from production code
- [x] `"native-svg-stub"` absent from production code
- [x] `"mechanical stub"` absent from production accessibility descriptions
- [x] No `except Exception:` in dedicated native builder wrappers
- [x] Unknown directives raise `NativeRenderError` explicitly
- [x] Exception tests for each previously-fallback renderer pass

**Stage 2 — RenderRequest**
- [x] `RenderRequest` frozen dataclass exists with all required fields
- [x] `parse_render_request()` strips frontmatter once
- [x] Frontmatter configuration preserved in `RenderRequest.frontmatter`
- [x] `faithful=True` propagated through native dispatch and `request.faithful` is set in `RenderRequest`
- [x] `theme=` propagated through native dispatch; `to_svg(src, theme=...)` does not raise (deferred: theme tokens wiring to paint layer → backlog-mermaid-p3-infra; byte-different assertion deferred there too)
- [x] `to_svg()` and `dispatch_native()` consume `RenderRequest` (SVG path scoped; `to_html`/`to_png`/`validate` wiring deferred: backlog-mermaid-p3-infra)
- [x] `tests/test_render_request.py` passes

**Stage 3 — FinalizedLayout Authority (flowchart/graph/stateDiagram only)**
- [x] `finalized_layout_to_scene()` exists and accepts `FinalizedLayout`
- [x] Native graph SVG path for `_GRAPH_DIRECTIVES` calls `_compile_flowchart()` → `finalized_layout_to_scene()`
- [x] `graph_to_scene()` no longer called on the `_GRAPH_DIRECTIVES` native path with mutable models
- [x] `_graph_topology_scene()` removed from `native_svg.py` (replaced by compile+scene pipeline)
- [x] `_class_topology_scene()` kept until a dedicated class compiler exists (deferred: backlog-mermaid-p3-class-compiler)
- [x] `architecture.py::graph_to_scene` call scoped out — architecture completed in Stage 9
- [x] Field-coverage parity test uses `dataclasses.fields(NodeLayout)` + `dataclasses.fields(RoutedEdge)` to assert every visible field is consumed (reflective, not manually enumerated)
- [x] `tests/test_finalized_layout_scene.py` passes (serialization-only proof)

**Stages 4-13 — Semantic Type Implementations** (deferred to future loops)
- [x] Recursive compound layout default (Stage 4) — `_recursive_group_layout` replaces rank-flattening + `_apply_inner_direction_positions`; fixes TB inner in LR outer x-unification and child group unit treatment
- [x] SVG Scene bounds hardening (Stage 5) — `element_visible_bounds`, `scene_visible_bounds`, `validate_scene` in `scene_bounds.py`; typed transform parsing; 50 tests
- [x] All 12 placeholder types implemented (Stage 6) — sequenceDiagram, erDiagram, gantt, quadrantChart, pie, xychart-beta, block-beta, packet-beta, kanban, journey, requirementDiagram, gitGraph each have PARTIAL native scene builders; 218 tests pass
- [x] Mind Map tidy-tree (Stage 7) — Buchheim variable-size tidy-tree, two-sided layout, `config: { layout: tidy-tree }` activation; radial path unchanged
- [x] Timeline measurement completion (Stage 8) — per-text measurement for period/event heights, col_w derived from widest period label, canvas_h driven by tallest column, activity-line arrowhead, _TimelineTokens theme token struct
- [x] Architecture semantics (Stage 9) — `ArchitectureDiagramLayout` compiled model; service tiles with measured label, icon_bounds, side ports; junction geometry; group hierarchy; BiRel → one path + two markers; `finalized_layout_to_scene` replaces `graph_to_scene`
- [x] C4 completion (Stage 10)
- [x] State diagrams (Stage 11) — partial: immutable state model (AtomicState, CompositeState, InitialPseudoState, FinalPseudoState, Choice, Fork, Join, History, StateGate, StateTransition, StateNote) in `statediagram.py`; <<fork>>/<<join>>/<<choice>>/<<history>> parser fix; bar shape rendering in HTML and SVG paths; 69 new tests. Deferred: wire statediagram.py as primary compiler replacing _parser.py state path, full composite children compilation. (backlog-mermaid-p3-state)
- [x] Themes/faithful/sizing/PNG (Stage 12) — `_tokens_from_theme` maps CSS-var palette to `_Tokens`; threaded into `finalized_layout_to_scene` via `_build_graph_pipeline`; `_natural_size` extracts view_box dims; `to_html` strips frontmatter before `_dispatch`; `to_png` rasterizes native SVG via `page.set_content`, falls back to HTML path for legacy-only types; `validate` sequence geometry confirmed wired
- [ ] Semantic tests and gallery (Stage 13) (deferred: backlog-mermaid-p3-semantic-tests)

## Testing Strategy

- TDD: `NativeParityLevel`, `NativeRendererSpec`, `RenderRequest`, `parse_render_request()` — frozen dataclasses and pure functions → red-green with example-based contract assertions
- Goal-based: static grep assertions in `test_no_native_stubs.py`
- TDD: `finalized_layout_to_scene()` given a minimal FinalizedLayout → produces SvgScene; field coverage verified by asserting each NodeLayout/RoutedEdge field's *value* appears in the emitted scene elements (not a hand-maintained literal set)
