# Mermaid Requirement Text Layout Conformance

Mode: full (multi-file; scaling coherence; pixel-width wrapping)

- **Status:** Shipped

Dependencies: mermaid-oracle-runtime-unification, mermaid-text-measurement-adoption

## Objective

Requirement layout still contains fixed character-count wrapping and approximate width
formulas. Its scaling path transforms bounds and route points but does not consistently
reconstruct every nested text and member layout field at the same scale. This means
`width_hint` and `height_hint` do not reliably control the full layout, and HTML/SVG
geometry can diverge when scaling is applied.

This spec retains the current shared `compile_requirement` entry point, replaces
character-count wrapping with measured pixel wrapping for every requirement field,
creates real `TextLayout` objects for all fields, and makes scaling coherent — either
compiling at the target scale or transforming all nested fields consistently.

## Boundaries

**In scope:**
- Keep `compile_requirement` as the sole entry point; no HTML-specific or SVG-specific
  layout variant.
- Replace fixed character wrapping with pixel-width wrapping for: requirement name,
  subtype, ID, text, risk, verification method, element name, element type, document
  reference, relation labels.
- Real `TextLayout` objects for every field listed above.
- Card width and height derived from measured fields and configured limits.
- Long unbroken paths and document references: safe break opportunities, width expansion
  up to a maximum, then deterministic wrapping.
- `width_hint` and `height_hint` coherent for non-empty diagrams.
- Scaling: prefer compiling at the target scale; when post-compilation scaling remains
  necessary, transform all of: node bounds, member row bounds, text bounds, text font
  size/line height, ports, route points, label bounds, canvas bounds.
- Validator that detects partially scaled layouts.
- Preserve strict Mermaid grammar behavior: invalid input produces a diagnostic, not
  silent repair.

**Out of scope:**
- Adding new requirement diagram field types.
- Flowchart, state, ER, class, architecture compilation.
- Font file changes.

**Never:**
- Create a second HTML-specific or SVG-specific requirement layout.
- Leave any visible requirement field with a stub or zero-area `TextLayout`.
- Apply post-compilation scaling that skips text font size or member row bounds.

## Acceptance Criteria

For `requirement-basic`:
- [x] AC1: Four semantic cards are present with all fields preserved.
- [x] AC2: Three relations have correct source, target, and label.
- [x] AC3: No field has a stub text layout; every field's `TextLayout` has positive
  width and height.
- [x] AC4: No relation route crosses any card interior.
- [x] AC5: Output size hints (`width_hint`, `height_hint`) affect the complete layout
  coherently; changing a hint changes card positions, not just canvas bounds.
- [x] AC6: HTML and SVG geometry is identical; the same `FinalizedLayout` is consumed
  by both painters.
- [x] AC7: mmdc/reference comparison executes nonzero checks on `requirement-basic`.
- [x] AC8: Requirement card wrapping is pixel-based; `_TEXT_WRAP_CHARS` (or equivalent)
  is deleted.
- [x] AC9: The scaling validator raises when a layout's text bounds are at a different
  scale than its node bounds.
- [x] AC10: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

All tests compile from requirement source strings; no hardcoded coordinates.

- **Pixel-based wrapping:** compile a requirement with a very long text field; assert
  the resulting `TextLayout.lines` wraps at the pixel limit, not at a character count;
  assert no line exceeds `max_width` pixels (by measuring it with the same measurer).
- **All fields measured:** compile `requirement-basic`; for each of the ten field types
  (requirement name, subtype, ID, text, risk, verification method, element name, element
  type, document reference, relation label), assert the `TextLayout` has positive width
  and height.
- **Long unbroken document reference:** compile a requirement with a URL in the document
  reference field; assert the width expands to fit rather than truncating.
- **Width hint response:** compile the same diagram with two different `width_hint`
  values; assert card positions differ in both cases.
- **Scaling coherence:** apply post-compilation scaling to a layout; assert text font
  size, member row heights, and text bounds are all scaled by the same factor.
- **Partial scaling detection:** construct a `FinalizedLayout` where text bounds are at
  scale 1.0 and node bounds are at scale 2.0; assert the validator raises.
- **Route non-penetration:** compile `requirement-basic`; for each relation route, assert
  all waypoints are outside all card interiors.
- **HTML/SVG identity:** compile `requirement-basic`; assert HTML and SVG painters
  receive identical `FinalizedLayout` instances.
- **Grammar strictness:** supply invalid requirement syntax; assert a `ParseError` or
  diagnostic is raised, not a silently repaired diagram.
