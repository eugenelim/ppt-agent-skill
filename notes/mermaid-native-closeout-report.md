# Mermaid Native SVG Closeout Report

## Stage 0 — Baseline

### Environment

| Item | Value |
|------|-------|
| Starting SHA | `6964824ecf4996e7f936d290563ea3474040b7fc` |
| Dirty state (at baseline) | `M docs/backlog.md`, `?? docs/specs/mermaid-p3/` (spec scaffolding only) |
| Python version | 3.13.13 |
| Pillow version | 12.2.0 |
| lxml version | 6.1.1 |
| mmdc version | 11.15.0 |
| Mermaid version | 11.15.0 (pinned oracle) |
| Ancestry check | `123c9527680786c0d82761ea3e983ec17daa4aaa` is ancestor of HEAD: YES |

### Baseline Test Counts (before P3 changes)

| Result | Count |
|--------|-------|
| Passed | 2608 |
| Failed | 604 |
| Skipped | 46 |
| Total (excl. snapshots) | 3258 |

Top failing modules:
- `test_mermaid_layout.py`: 316
- `test_render_correctness.py`: 62
- `test_oracle.py`: 47
- `test_syntax_flowchart.py`: 36
- `test_syntax_state.py`: 25

### Native Renderer State at Baseline

| Diagram Type | Current State | Parity Level |
|---|---|---|
| flowchart / graph | `_graph_topology_scene` → `graph_to_scene` (mutable) | PARTIAL |
| stateDiagram / stateDiagram-v2 | `_graph_topology_scene` → `graph_to_scene` (mutable) | PARTIAL |
| classDiagram | `_class_topology_scene` → `graph_to_scene` (mutable) | PARTIAL |
| timeline | `layout_timeline_scene` (dedicated) or fallback | PARTIAL |
| mindmap | `layout_mindmap_scene` (radial only) or fallback | PARTIAL |
| architecture-beta | `layout_architecture_scene` or fallback | PARTIAL |
| c4context/c4container/c4component | `layout_c4_scene` or fallback | PARTIAL |
| sequenceDiagram | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| erDiagram | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| gantt | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| quadrantChart | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| pie | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| xychart-beta | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| block-beta | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| packet-beta | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| kanban | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| journey | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| requirementDiagram | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| gitGraph | `_html_fallback_scene` stub | NOT_IMPLEMENTED |
| sankey-beta | explicit ValueError | UNSUPPORTED |
| zenuml | explicit ValueError | UNSUPPORTED |

### Source Defects Confirmed Present

1. `_html_fallback_scene()` exists and emits only background + `[diagram_type]` label ✓
2. 12 renderers unconditionally use that placeholder ✓
3. classDiagram, timeline, mindmap, architecture, C4 have `except Exception` → placeholder ✓
4. `_graph_topology_scene()` duplicates parser, ranking, coordinates, routing ✓
5. `_class_topology_scene()` duplicates mutable layout pipeline ✓
6. `graph_to_scene()` consumes mutable `_Node`/`_Edge`/`_Group` dicts ✓
7. `paint.py` recalculates approximate node heights ✓
8. `dispatch_native()` strips frontmatter before dedicated renderers ✓
9. `to_svg(..., faithful=True)` does not propagate `faithful` ✓
10. `theme=` accepted but not propagated ✓
11. Mind Map implements only radial layout ✓
12. Architecture painted through generic graph painter (via fallback) ✓
13. Architecture `<-->` represented as two logical edges ✓
14. C4 uses rounded rectangles for every element type ✓
15. State diagrams use generic flowchart path ✓
16. `to_png()` renders HTML representation ✓
17. P2 report has no completed visual gallery ✓

---

## Stage 0-3 Implementation Results

### Changes Shipped

| Task | Status | Key Files |
|------|--------|-----------|
| 0: Baseline | ✓ | `notes/mermaid-native-closeout-report.md` |
| 1a: NativeParityLevel/NativeRendererSpec/registry | ✓ | `scene.py` |
| 1b: test_native_renderer_capabilities.py | ✓ | `tests/test_native_renderer_capabilities.py` |
| 2: NativeRenderError | ✓ | `native_svg.py` |
| 3: Remove _html_fallback_scene, all except Exception | ✓ | `native_svg.py` |
| 4: RenderRequest + parse_render_request() | ✓ | `native_svg.py` |
| 5: Wire RenderRequest through dispatch | ✓ | `native_svg.py`, `__init__.py` |
| 6: finalized_layout_to_scene() | ✓ | `paint.py` |
| 7: Wire finalized_layout_to_scene into _GRAPH_DIRECTIVES | ✓ | `native_svg.py` |
| 8: test_no_native_stubs.py | ✓ | `tests/test_no_native_stubs.py` |

### Post-P3 Test Counts

| Result | Count | Delta vs Baseline |
|--------|-------|-------------------|
| Passed | 2696 | +88 |
| Failed | 604 | ±0 (zero regressions) |
| Skipped | 46 | ±0 |
| Total (excl. snapshots) | 3346 | +88 |

### Architecture After P3

| Diagram Type | Pipeline | Parity Level |
|---|---|---|
| flowchart / graph / stateDiagram | `_compile_flowchart` → `finalized_layout_to_scene` (immutable) | PARTIAL |
| classDiagram | `_class_topology_scene` → `graph_to_scene` (mutable; deferred) | PARTIAL |
| timeline | `layout_timeline_scene` | PARTIAL |
| mindmap | `layout_mindmap_scene` (radial only) | PARTIAL |
| architecture-beta | `layout_architecture_scene` | PARTIAL |
| c4context/c4container/c4component | `layout_c4_scene` | PARTIAL |
| 12 placeholder types | raises `NativeRenderError(phase="not-implemented")` | NOT_IMPLEMENTED |
| sankey-beta, zenuml | raises `NativeRenderError(phase="dispatch")` | UNSUPPORTED |

### Defects Resolved

1. ✓ `_html_fallback_scene()` removed — 12 stub renderers now raise `NativeRenderError`
2. ✓ `except Exception` silent fallbacks removed from timeline, mindmap, architecture, C4
3. ✓ `_graph_topology_scene()` removed — replaced by `_compile_flowchart` + `finalized_layout_to_scene`
4. ✓ `graph_to_scene()` no longer called on the native `_GRAPH_DIRECTIVES` path
5. ✓ `faithful=True` propagated through `RenderRequest` into `_compile_flowchart`
6. ✓ Theme accepted without raising on native path (wiring to paint tokens deferred)
7. ✓ Reflective field-coverage test: all NodeLayout + RoutedEdge fields accounted for

### Remaining Known Gaps (deferred)

- theme tokens not wired to paint → `backlog-mermaid-p3-infra`
- classDiagram still uses mutable path → `backlog-mermaid-p3-class-compiler`
- 12 NOT_IMPLEMENTED types still raise → `backlog-mermaid-p3-type-migrations`
- src_label_layout / dst_label_layout not consumed → `backlog-mermaid-p3-type-migrations`
- `content_bounds`, `ports`, `extra_css`, `icon_bounds`, `icon_svg` not consumed → design decisions documented in reflective test
