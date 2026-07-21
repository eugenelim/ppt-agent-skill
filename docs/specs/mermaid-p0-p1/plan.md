# Plan: Mermaid P0+P1 Renderer Overhaul

## Declined patterns
- Tempted to replace _strategies.py with a full visitor pattern hierarchy; declining — too large a refactor, patch in place.
- Tempted to pull in NetworkX or similar for graph algorithms; declining — no new runtime deps.
- Tempted to build a live preview dev server; declining — out of scope.

## Resolve-vs-surface disposition

All open items will be resolved via referent (spec + task brief). No value-origination
or irreversible-risk items identified beyond accurate reporting of any remaining gaps.

---

## Task S0: Stage 0 — Establish baseline
Depends on: none
Verification: goal-based

Done when:
- Baseline environment recorded
- Tests run and saved (1327 pass, 72 skip baseline)
- compare_gallery.py has --output-dir, --metadata-only, --width-hint
- Each gallery run writes metadata.json
- notes/mermaid-p0-p1-report.md skeleton created with baseline SHA
- test_render_correctness.py stale _UNSUPPORTED fixed
- assert condition or True patterns removed

Tests: (goal-based — no test file needed; verified by python3 scripts/compare_gallery.py --help)

---

## Task S1: Stage 1 — Complete geometry IR
Depends on: S0
Verification: TDD

Done when:
- _geometry.py expanded with all IR types
- finalize_graph_layout() orchestrator created
- Existing layout still works (gates green)

Tests: tests/test_geometry_ir.py
- Rect.union_all / inflate / center / intersection_area / from_points
- FinalizedLayout construction
- PortSide enum values

---

## Task S2: Stage 2 — Text layout service
Depends on: S1
Verification: TDD

Done when:
- scripts/mermaid_render/layout/_text.py created
- PillowTextMeasurer implements TextMeasurer protocol
- Deterministic font resolution chain implemented
- No normal Latin word split character-by-character
- Node dimensions use TextLayout

Tests: tests/test_text_layout.py

---

## Task S3: Stage 3 — Typed config propagation
Depends on: S1
Verification: TDD

Done when:
- FlowchartLayoutConfig, GraphLayoutConfig, C4LayoutConfig, RenderConfig dataclasses
- _parse_init_config() returns typed config
- nodeSpacing / rankSpacing / diagramPadding change actual coordinates
- Unknown keys go to diagnostics

Tests: tests/test_layout_config.py

---

## Task S4: Stage 4 — Architecture port parsing
Depends on: S1, S3
Verification: TDD

Done when:
- A:R --> L:B parsed correctly with named captures
- Source/destination port requests on _Edge
- Router honors fixed ports
- Bidirectional uses single route with two markers

Tests: tests/test_architecture_ports.py

---

## Task S5: Stage 5 — C4 parsing and boundaries
Depends on: S1, S3
Verification: TDD

Done when:
- ContainerQueue, ContainerDb, ComponentQueue, Person_Ext etc. parsed
- Technology and description separate fields
- Boundary stack pops on `}` not only `)`
- Recursive boundary packing
- tests/fixtures/c4-container-config.mmd fixture added

Tests: tests/test_c4_boundaries.py

---

## Task S6: Stage 6 — Recursive compound-graph layout
Depends on: S1, S2
Verification: TDD

Done when:
- Group tree built and bottom-up layout
- Local direction implemented recursively
- Descendant containment invariant holds

Tests: tests/test_compound_layout.py

---

## Task S7: Stage 7 — Port/label-aware routing
Depends on: S1, S2, S4
Verification: TDD

Done when:
- No direct source-to-destination fallback
- Label boxes measured via TextLayout
- Fixed ports honored
- Diagnostics on failure

Tests: tests/test_edge_label_layout.py

---

## Task S8: Stage 8 — Layered graph core upgrade
Depends on: S1
Verification: TDD

Done when:
- network-simplex rank assignment behind named strategy
- barycenter-transpose orderer
- Brandes-Koepf-style coordinate assignment (or accurate name if approximation)
- Metric helpers: count_edge_crossings, count_node_overlaps, etc.

Tests: tests/test_layered_algorithms.py

---

## Task S9: Stage 9 — Renderer serialization-only
Depends on: S1, S2, S6, S7
Verification: TDD + goal-based

Done when:
- _renderer.py does not call routing, recompute sizes, or wrap text for migrated types
- Monkeypatch test proves no geometry work post-finalization

---

## Task S10: Stage 10 — Content-tight SVG
Depends on: S9
Verification: TDD + goal-based

Done when:
- Exported SVG width != 1280 for content
- viewBox ~= visible geometry + padding
- All markers and labels inside viewBox

Tests: tests/test_svg_bounds.py
