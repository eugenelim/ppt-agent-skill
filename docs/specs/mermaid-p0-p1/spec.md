# Spec: Mermaid P0+P1 Renderer Overhaul

**Mode: full (multi-feature, structural change, unfamiliar territory)**

**Status:** Implementing

## Objective

Create one authoritative geometry pipeline for the shared graph renderer,
fixing text sizing, geometry recomputation, architecture port syntax,
C4 layout, compound-graph layout, edge labels, layered ranking, SVG bounds,
and improving test provenance.

Source brief: `.context/attachments/nKOCbI/pasted_text_2026-07-20_22-53-29.txt`

## Boundaries

**In scope:** flowchart, graph, stateDiagram/v2, classDiagram, erDiagram,
requirementDiagram, architecture-beta, C4 diagrams.

**Out of scope:** sequence, Gantt, packet, pie, journey, GitGraph, XY chart
(dedicated renderers), full native SVG serializer.

**Public API preserved:**
```python
mermaid_render.to_html(src, *, theme=None, width_hint=0)
mermaid_render.to_svg(src, *, theme=None, width_hint=0)
mermaid_render.to_png(src, *, theme=None, scale=1.0, width_hint=0)
```
`to_html()` remains Playwright-free.

**No new runtime dependencies** (lxml, Pillow, python-pptx, playwright only).

## Acceptance Criteria

- [ ] Baseline SHA, commands, and gallery path recorded in notes/mermaid-p0-p1-report.md
- [ ] compare_gallery.py supports --output-dir, --metadata-only, --width-hint
- [ ] Gallery runs write metadata.json (git_sha, versions, fixture SHAs, font path, CLI args)
- [ ] FinalizedLayout IR defined; NodeLayout, GroupLayout, RoutedEdge, etc. are frozen dataclasses
- [ ] _renderer.py does not perform geometry work for migrated graph types after pipeline
- [ ] Text measurement uses Pillow FreeType for resolved emitted font
- [ ] Normal Latin words are not split into one-character lines
- [ ] Node dimensions derive from final TextLayout
- [ ] nodeSpacing, rankSpacing, diagramPadding change actual geometry (tested)
- [ ] Architecture side ports captured and honored (A:R --> L:B)
- [ ] Architecture bidirectional relations produce one route with two markers
- [ ] C4 parses and renders ContainerQueue
- [ ] C4 preserves technology and description separately
- [ ] C4 parses UpdateLayoutConfig
- [ ] C4 boundaries recursively packed and visibly rendered
- [ ] Elements after `}` not retained in prior boundary
- [ ] Local subgraph direction implemented recursively, not by rank flattening
- [ ] Group calculations use actual node widths, not NODE_W constant
- [ ] Edge labels use measured bounds
- [ ] Router has no direct obstacle-crossing line fallback
- [ ] Improved layered algorithm available behind named strategies
- [ ] SVG bounds content-tight (not fixed 1280px)
- [ ] Full test suite passes
- [ ] After gallery and metadata generated
- [ ] Any visual mismatches explicitly listed, not hidden by snapshot updates

## Testing Strategy

New test files:
- tests/test_geometry_ir.py
- tests/test_text_layout.py
- tests/test_layout_config.py
- tests/test_architecture_ports.py
- tests/test_c4_boundaries.py
- tests/test_compound_layout.py
- tests/test_edge_label_layout.py
- tests/test_layered_algorithms.py
- tests/test_svg_bounds.py
- tests/test_gallery_provenance.py

Verification mode: TDD (core logic) + goal-based (gallery generation) + manual QA (visual output).
