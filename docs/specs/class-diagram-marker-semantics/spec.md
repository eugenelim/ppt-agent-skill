# Spec: class-diagram-marker-semantics

- **Status:** Shipped

Mode: full (structural change; multi-task; public interface)
Constrained by: docs/adr/001-elk-layout-engine.md (LayoutEdge.source_marker stays MarkerKind)

## Objective

Replace the class-diagram relationship representation with independent
source-end and destination-end semantics via a new `MarkerSpec` type.
The current `arrow_src: bool` encodes which end carries the UML marker
as a single boolean, which cannot represent the full marker vocabulary
(kind, fill, stroke, clearance) needed for correct UML rendering.

Target fixture: `tests/fixtures/class-relationships-all.mmd`

## Acceptance Criteria

- [x] `MarkerSpec` dataclass exists in `layout/_geometry.py` with fields:
      `kind`, `end`, `size`, `line_join`, `fill`, `stroke`, `clearance`.
- [x] `MarkerKind` enum includes `HOLLOW_TRIANGLE` and `HOLLOW_DIAMOND`.
- [x] `_Edge.arrow_src` field removed; `source_marker` and `target_marker`
      typed as `MarkerSpec` (not `MarkerKind`).
- [x] Mermaid class-diagram operators map to `MarkerSpec` exactly:
      - `A <|-- B`  → `source_marker=MarkerSpec(HOLLOW_TRIANGLE, SOURCE)`, solid
      - `A *-- B`   → `source_marker=MarkerSpec(FILLED_DIAMOND,  SOURCE)`, solid
      - `A o-- B`   → `source_marker=MarkerSpec(HOLLOW_DIAMOND,  SOURCE)`, solid
      - `A --> B`   → `target_marker=MarkerSpec(OPEN_ARROW,      TARGET)`, solid
      - `A ..> B`   → `target_marker=MarkerSpec(OPEN_ARROW,      TARGET)`, dotted
      - `A ..|> B`  → `target_marker=MarkerSpec(HOLLOW_TRIANGLE, TARGET)`, dotted
- [x] Routing derives marker placement from which of `source_marker`/`target_marker`
      is non-NONE, never from a boolean `arrow_src` field. (`MarkerSpec.end` is
      informational metadata; it does not drive routing decisions.)
- [ ] Route paths for class edges shortened by `MarkerSpec.clearance` at the marker end so the marker sits at the card face, not inside it. (deferred: class-diagram-marker-clearance)
- [ ] Route entry/exit points clipped to actual class-card bounding rect. (deferred: class-diagram-route-clip)
- [ ] Edge labels placed on longest stable segment (≥40 px). (deferred: class-diagram-label-segment)
- [x] Multiplicity (`src_label`/`dst_label`) threaded through for both ends.
- [x] Declared relation direction preserved independently of graph rank order.
- [x] Semantic tests pass for every relation in `class-relationships-all.mmd`:
      marker kind, marker end, dash pattern, src node, dst node, label.
- [x] All existing class-diagram tests still pass (no regression).

## Boundaries

**Changing:**
- `layout/_geometry.py` — add `HOLLOW_TRIANGLE`, `HOLLOW_DIAMOND` to `MarkerKind`; add `MarkerSpec`
- `layout/_constants.py` — remove `arrow_src`; retype `source_marker`/`target_marker` as `MarkerSpec`
- `layout/_parser.py` — wrap flowchart marker kinds in `MarkerSpec`
- `layout/_strategies.py` — add `_class_rel_markers()`; update `_layout_class()`; update `_compile_flowchart_to_layout_graph()` to extract `.kind` from `MarkerSpec`
- `native_svg.py` — update class topology parser
- `layout/_routing.py` — replace `arrow_src` check with `source_marker.kind`
- `tests/test_mermaid_layout.py` — update `TestArrowSemantics` assertions (`.kind`)
- `tests/test_class_semantic.py` — new semantic test file

**Not changing:**
- `LayoutEdge.source_marker`/`target_marker` type (stays `MarkerKind` for ELK pipeline)
- HTML marker defs in `_renderer.py` (marker IDs unchanged: `cls-inherit`, `cls-composition`, etc.)
- `svg_serializer.py` / `paint.py` marker painting for flowchart/statediagram

## Testing Strategy

Verification mode: TDD for the semantic model (MarkerSpec creation + routing
marker selection), goal-based for rendering (HTML output contains correct
marker IDs and dash attrs).

**Unit tests (`tests/test_class_semantic.py`):**
- For each of the 6 operator lines in `class-relationships-all.mmd`, parse
  edges and assert `source_marker.kind`, `target_marker.kind`,
  `source_marker.end` or `target_marker.end`, line style, src/dst nodes,
  label text.
- Clearance: assert route endpoint shortened for edges with non-NONE marker.

**Regression tests (existing):**
- `TestClassRelationshipParse`, `TestClassMarkerDefs`, `TestClassDashedLine`,
  `TestClassInheritanceTriangle`, `TestClassCompositionDiamond`,
  `TestClassParser`, `TestArrowSemantics` — all must stay green.

## Assumptions

- `_class_rel_style()` kept as compatibility shim; caller (`_layout_class`,
  `native_svg.py`) migrates to `_class_rel_markers()`.
- `LayoutEdge.source_marker`/`target_marker` stays `MarkerKind` — no ELK
  pipeline change.
- Clearance default = 12.0 for triangle/diamond markers, 9.0 for open arrow.

## Declined

- Changing `LayoutEdge.source_marker`/`target_marker` to `MarkerSpec`
  (would cascade into ELK pipeline, architecture-beta, RoutedEdge — out of scope).
- New abstract `MarkerPainter` class (unnecessary indirection for 4 cases).
- Configurability flags or env vars (single well-specified default set).
