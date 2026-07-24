# Flowchart Arrow Style Conformance

Mode: full (style preservation — edge token normalization; style through pipeline; faithful mode)

- **Status:** Approved

Dependencies: `docs/specs/eight-case-validation-and-provenance`

Constrained by: `docs/adr/001-elk-layout-engine.md`

## Objective

Prove that Mermaid flowchart edge tokens retain their exact style and marker semantics
through parsing, ELK, fallback routing, HTML painting, and SVG painting.

Fixture in scope: `flowchart-arrows-defs`

```
flowchart TB
    A-->B
    A==>C
    A-.->D
    B-->C
    C-->D
```

## Boundaries

**In scope:**
- **Stable edge ID:** every relation has a stable, unique `edge_id` (not derived from
  source/destination pair alone) that survives ELK round-trip and fallback routing.
- **Token normalization:** `-->` → normal solid line + normal target arrow; `==>` → thick
  solid line + normal target arrow; `-.->` → Mermaid dotted/dashed line pattern + normal
  target arrow. Style is independent from editorial color.
- **Style preservation through pipeline:** `_Edge` → `LayoutEdge` → ELK serialization →
  ELK deserialization → Python fallback `RoutedEdge` → HTML attributes/CSS → SVG
  stroke-width/dasharray/marker → structured oracle records.
- **Test coverage:** both ELK-required and Python-fallback lanes; both `to_html` and
  `to_svg` outputs.
- **Faithful mode guard:** `faithful_mermaid=True` must not add a legend, label edges as
  synchronous/asynchronous/optional/critical, or assign semantic colors based on line
  style.
- **Marker ownership:** assert marker ownership (target-arrow presence) separately from
  stroke style.

**Out of scope:**
- New arrow token types beyond the three in the fixture.
- Changes to non-flowchart edge types.
- Visual/raster comparison.

**Never:**
- Identify an edge only by `(source_id, destination_id)`.
- Assign semantic business meaning to edge line styles in faithful mode.
- Use a preexisting screenshot or gallery artifact as the acceptance oracle.

## Acceptance Criteria

- [ ] AC1: A→B is normal solid line with target arrow marker.
- [ ] AC2: A→C is thick solid line with target arrow marker.
- [ ] AC3: A→D is dotted/dashed line (per the pinned Mermaid token reference) with target
  arrow marker.
- [ ] AC4: B→C and C→D are normal solid line with target arrow markers.
- [ ] AC5: All five edges retain their target arrow marker independently confirmed from
  stroke style.
- [ ] AC6: Style and marker assertions execute with nonzero count in the structured
  oracle records.
- [ ] AC7: ELK-required and Python-fallback lane results agree on style and marker for
  all five edges.
- [ ] AC8: `to_html` and `to_svg` results agree on style and marker for all five edges.
- [ ] AC9: `faithful_mermaid=True` outputs contain no legend, no semantic edge labels, and
  no semantically derived colors beyond the Mermaid source declaration.
- [ ] AC10: Each edge has a stable `edge_id` that persists through ELK serialization and
  deserialization.

## Testing Strategy

| AC | Verification mode |
|----|-------------------|
| AC1–AC4 | TDD: parse `flowchart-arrows-defs`; assert `EdgeStyle` fields per edge |
| AC5 | TDD: assert marker presence separately from stroke-width/dasharray |
| AC6 | TDD: oracle record has nonzero `assertion_count` for style checks |
| AC7 | TDD: ELK and fallback results agree on style/marker; parametrized test |
| AC8 | TDD: `to_html` and `to_svg` results agree on style/marker |
| AC9 | TDD: render `to_html(faithful_mermaid=True)`; grep for legend/semantic-color |
| AC10 | TDD: ELK serialization round-trip; assert `edge_id` unchanged |
