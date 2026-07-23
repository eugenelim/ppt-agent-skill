# er-measured-topology-layout

Mode: full (risk triggers: structural change to common layout IR, multi-subsystem)

**Status:** Shipped

## Objective

Replace the fixed-grid ER renderer in `layout/er.py` with measured topology layout and a
structured `CardinalityEnd` model. Update the HTML painter in `_strategies.py` to use the
same model.

## Acceptance Criteria

- [x] `er.py`: `_COLS=3` placement policy removed; Sugiyama layered layout used instead
- [x] Entity card dimensions measured from header height + n_attrs × row_h + padding
- [x] `Minimum` / `Maximum` / `CardinalityEnd` dataclasses in `_constants.py`
- [x] `parse_er_cardinality(card_str)` in `er.py` returns `(CardinalityEnd, CardinalityEnd)`
- [x] `_CARD_MAP` with duplicate `"||"` keys removed; replaced by `_parse_cardinality_token()`
- [x] Glyphs rendered in tangent/normal frame: crow's feet have feet near entity, convergence on line
- [x] Main relationship line trimmed by `_er_glyph_reserve()` at each endpoint
- [x] Lines routed from card boundaries (not entity centres)
- [x] Relationship label placed at midpoint of trimmed segment
- [x] HTML painter (`_strategies.py`) updated to use `CardinalityEnd` + corrected glyph geometry
- [x] Tests: `test_er_cardinality.py` decodes each acceptance-criterion token and asserts structured ends
- [x] Acceptance `er-cardinality-all`: all 8 cards non-overlapping, each endpoint glyph type correct
- [x] Acceptance `er-ecommerce`: 5 measured cards non-overlapping, labels correct

## Testing Strategy

- Unit: `test_er_cardinality.py` — parametrized over all 4 acceptance-criterion pairs, asserts `CardinalityEnd` equality
- Integration (existing): `test_fix_er.py` + `test_syntax_er.py` — must stay green
- Integration: `test_fix_er.py::TestFixtures::test_er_cardinality_all` and `test_er_ecommerce` for acceptance
- Geometric: `test_fix_er.py::TestCardNonOverlap` — non-overlap check at widths [800, 600, 400] for HTML path + native `layout_er_scene` path at width=600

## Tasks

1. Add `Minimum`, `Maximum`, `CardinalityEnd` to `_constants.py` — done-when: `from mermaid_render.layout._constants import CardinalityEnd` works
2. Rewrite `er.py` — remove grid, add measured layout, `parse_er_cardinality`, glyph rendering
3. Update `_strategies.py` — use `CardinalityEnd`, rewrite `_render_crow_foot`, add `_er_glyph_reserve`
4. Write `tests/test_er_cardinality.py`
5. Run gates (pytest)

## What I'm not changing

- Sugiyama pipeline core (`_layout.py`, `_layered.py`)
- Any other diagram type's rendering
- `_Edge.cardinality_src/dst` field type (stays `Optional[str]` for backward compat in `_Node/_Edge` IR)

## Declined patterns

- Tempted to create `_er_model.py`; declining — `CardinalityEnd` fits in `_constants.py` (the "common layout IR") and parsing helpers fit in `er.py`
- Tempted to add orthogonal routing for ER edges; declining — straight lines with boundary clipping satisfy the acceptance criteria
- Tempted to update `_Edge.cardinality_src/dst` to `CardinalityEnd`; declining — would require updating all callers and is not required by the task
