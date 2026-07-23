# Mermaid Text Measurement Adoption

Mode: full (multi-file; touches multiple layout categories; structural)

- **Status:** Shipped

## Objective

Multiple layout categories in the renderer still compute node, group, and card sizes from
raw string length multiplied by a per-character coefficient, a fixed average character
width, a fixed wrap-character count, or a category-specific approximation. Requirement
layout creates partially synthetic `TextLayout` values and wraps by a fixed character
count. These estimates are not deterministic across fonts and produce coordinates that
differ from what HTML and SVG painters subsequently place.

This spec makes the existing Pillow/FreeType-backed `TextMeasurer` in `_text.py` the
authoritative source for every in-scope layout-time text decision. The measurer and its
font resolver already exist; the work is to route all sizing through them and eliminate
the character-count shortcuts.

Depends on: `mermaid-oracle-runtime-unification` (the oracle contract must be stable so
measured-coordinate changes produce meaningful comparison signals).

## Boundaries

**In scope:**
- Define `TextStyle` constants for: ordinary node labels, group labels, edge labels,
  architecture service labels, class names, ER entity headers, ER key/type/name cells,
  requirement headers and all requirement fields, state labels and transition labels.
- Replace every layout calculation that uses `len(text) * constant`, fixed average
  character width, fixed wrap-character count, or category-specific approximation with
  `_MEASURER.layout(text, style, max_width=..., wrap=...)`.
- Construct real `TextLayout` values from measured line strings, line widths, line
  height, content width, total height, bounding rectangle, and resolved font metadata.
- Use measured `TextLayout` for both node/group sizing and HTML/SVG text placement.
- Flowchart group title sizing: measure before building `LayoutGroup`; remove
  `len(g.label) * 8` coefficient.
- Architecture `_arch_text_layout` and group-width estimates: replace with shared
  measurer.
- ER entity width: derive from measured header and column text (key badges, type column,
  attribute-name column).
- Requirement wrapping: replace `_TEXT_WRAP_CHARS` with pixel-width wrapping; measure
  every requirement field.
- Scaling coherence: either compile at the target scale, or transform all of: node
  bounds, ports, routes, TextLayout fields together.
- Cache keyed by: text, font family, font file fingerprint, font size, weight, style,
  letter spacing, max width, wrap mode.
- Tests for: long labels, multiline labels, long unbroken tokens, non-ASCII labels,
  identical repeated measurements, identical HTML and SVG text bounds.

**Out of scope:**
- Replacing the `TextMeasurer` implementation itself.
- Changing font files or the font resolver algorithm.
- Sequence diagram text layout (separate track).
- Non-text geometry (shape boundaries, route paths).

**Never:**
- Build another runtime text-measurement abstraction.
- Use raw `len(text)` as a layout width input for any in-scope label.
- Produce a `TextLayout` with a stub or zero-area bounding rectangle for a visible label.

## Acceptance Criteria

- [ ] AC1: No in-scope layout width for a visible label is derived directly from
  `len(text)` or a character-count coefficient.
- [ ] AC2: Every visible layout label has a non-stub `TextLayout` with non-zero `width`
  and `height`.
- [ ] AC3: HTML and SVG painters consume the same line breaks and text bounds for every
  label — identical `TextLayout` objects, not independently computed values.
- [ ] AC4: Requirement card wrapping is pixel-based; the character-count constant
  `_TEXT_WRAP_CHARS` (or equivalent) is deleted.
- [ ] AC5: ER entity width responds to actual column contents; a wider attribute name
  produces a wider card.
- [ ] AC6: Repeated clean runs with identical source, options, and fonts produce identical
  layout coordinates — measurement is deterministic and cache-consistent.
- [ ] AC7: Font identity (family and file fingerprint) is included in layout metadata or
  render provenance.
- [ ] AC8: `pytest tests/` continues to pass with zero regressions.

## Testing Strategy

All tests are unit/integration tests with the real `TextMeasurer` (no mocking of
font metrics).

- **Style constants completeness:** assert each named `TextStyle` constant exists and has
  non-zero `font_size`.
- **Long label measurement:** assert measured width for a 50-character label is strictly
  greater than for a 5-character label in the same style.
- **Multiline wrapping:** assert a label that exceeds `max_width` produces multiple lines
  in `TextLayout.lines`; total height > single-line height.
- **Long unbroken token:** assert a token with no break opportunities does not produce a
  zero-width or negative-width line.
- **Non-ASCII labels:** assert a label containing CJK or accented characters produces a
  non-zero measured width.
- **Cache determinism:** call `_MEASURER.layout` twice with identical arguments; assert
  the result is the same object or equal by value.
- **HTML/SVG identity:** for each in-scope label category, assert HTML painter and SVG
  painter receive the same `TextLayout` instance.
- **ER width response:** construct two ER entities differing only in attribute name
  length; assert the wider-name entity produces a wider card.
- **Requirement pixel wrap:** assert requirement card wrapping uses pixel bounds, not a
  character count; a long unbroken word forces width expansion rather than truncation.
