# Mermaid ER Compiler Consolidation and Routing

Mode: full (structural — deletes legacy compiler; ELK routing integration; multi-file)

- **Status:** Draft

Dependencies: mermaid-oracle-runtime-unification, mermaid-text-measurement-adoption

## Objective

`compile_er` is already an alias for `compile_er_layout`, but the codebase retains a
large legacy compiler for reference. The active compiler has the structured `CardinalityEnd`
model and dynamic-width intent, but still uses approximate text sizing, simplified label
bounds, and mostly direct relationship segments. Relationships are not routed through
structured `FinalizedLayout` paths.

This spec makes `compile_er_layout` the sole active ER implementation, deletes
`_compile_er_legacy` after tests migrate, routes relationships through ELK orthogonal
routing where available, measures entity cards with the shared measurer, and ensures
every relationship has a unique `edge_id` and explicit cardinality on both ends.

## Boundaries

**In scope:**
- `compile_er_layout(...)` as the authoritative implementation; `compile_er(...)` kept
  only as a compatibility alias.
- Delete `_compile_er_legacy` after all tests migrate and no imports reference it.
- Measure entity cards with the shared `TextMeasurer`: entity header, constraint badges,
  type column, attribute-name column, row heights.
- Real `TextLayout` objects for headers, attributes, and relationship labels.
- Convert measured ER topology into `LayoutGraph`.
- ELK orthogonal routing as primary relationship router where ELK is available.
- Current deterministic topology layout as typed fallback.
- Every relationship: unique `edge_id`, explicit source port, explicit target port,
  source `CardinalityEnd`, target `CardinalityEnd`, identifying/non-identifying style,
  label layout.
- Distinct ordered ports for adjacent relationships on one entity.
- Endpoint distance reserved for cardinality glyphs before drawing visible route.
- Cardinality rendered from finalized endpoint tangent and normal.
- Relation label placed on the longest clear route segment.
- Cardinality and label bounds included in collision validation.
- Semantic tests for `||--||`, `||--o{`, `}|--||`, `|o--|{`.
- Routing tests proving unrelated entity interiors are not crossed.

**Out of scope:**
- Flowchart, state, architecture, class, requirement compilation.
- New ER diagram features beyond the current Mermaid grammar.

**Never:**
- Keep `_compile_er_legacy` alive after all tests have migrated.
- Base any card width on a raw character-count coefficient.
- Use `(src, dst)` as relationship identity.
- Route a relationship through an unrelated entity's interior.

## Acceptance Criteria

- [ ] AC1: One active ER compiler remains; `_compile_er_legacy` is deleted.
- [ ] AC2: No entity card width is based on a raw character-count coefficient; all widths
  derive from `TextMeasurer` measurements.
- [ ] AC3: All visible ER text has real measured `TextLayout` objects (no stub or
  zero-area layouts).
- [ ] AC4: Every relationship has a stable `edge_id` unique within the diagram.
- [ ] AC5: Both cardinality ends of each relationship match the parsed source semantics
  for all four test patterns (`||--||`, `||--o{`, `}|--||`, `|o--|{`).
- [ ] AC6: Cardinality glyphs rotate with their route tangent; the glyph orientation
  matches the endpoint direction.
- [ ] AC7: Relationship labels do not overlap cardinality endpoint glyphs.
- [ ] AC8: Relationships do not enter unrelated entity card interiors.
- [ ] AC9: HTML and SVG consume identical finalized geometry from `compile_er_layout`.
- [ ] AC10: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

All tests compile from ER source strings; no hardcoded coordinates.

- **Legacy deletion:** assert `_compile_er_legacy` is not importable after the migration.
- **Measured card width:** construct an ER entity with a long attribute name; assert the
  card width exceeds that of an entity with a short attribute name; assert no
  character-count coefficient is used in the computation.
- **Real TextLayout for attributes:** compile an ER diagram; for each attribute, assert
  its `TextLayout.width > 0` and `TextLayout.height > 0`.
- **Cardinality semantics (four patterns):** compile each of the four test patterns;
  assert `source_end.minimum`, `source_end.maximum`, `target_end.minimum`,
  `target_end.maximum` match the expected values.
- **Unique edge IDs:** compile a multi-relationship ER diagram; assert all `edge_id`
  values are distinct.
- **Cardinality glyph orientation:** compile a diagram with a known horizontal
  relationship; assert the cardinality glyph angle matches the route tangent angle
  within 5 degrees.
- **Label not overlapping glyph:** compile a labeled relationship; assert label bounds
  and cardinality glyph bounds do not intersect.
- **Route non-penetration:** compile an ER diagram with at least three entities; assert
  no route waypoints lie inside an unrelated entity's bounding rectangle.
- **HTML/SVG identity:** for each entity and relationship, assert HTML and SVG receive
  the same `FinalizedLayout` bounds.
