# Sequence Shared Compiler and Native Scene

Mode: full (sequence pipeline refactor — shared IR; retire legacy native-SVG parser)

- **Status:** Shipped

Dependencies: `docs/specs/eight-case-validation-and-provenance`

Constrained by: `docs/adr/001-elk-layout-engine.md`

## Objective

Make `_sequence_compile.py` the single sequenceDiagram parser and geometry compiler for
both HTML and SVG. Retire the independent native-SVG parser in `layout/sequence.py`.

The existing HTML compiler already supports boxes, fragments, nested fragments, branches,
participants, messages, notes, and activations. Retain that implementation and remove the
independent native-SVG parser.

## Boundaries

**In scope:**
- **BoxGeometry IR:** new frozen dataclass `BoxGeometry(box_id, label, color,
  participant_ids, bounds, source_order)` added to `_geometry.py`. Populated from
  `_all_box_groups` in `_sequence_compile.py`. Added to `SequenceGeometry.boxes`.
- **FragmentGeometry extensions:** `parent_fragment_id: str | None`, `start_event_index:
  int`, `end_event_index: int`, `depth: int` added to the existing `FragmentGeometry`
  dataclass. `BranchGeometry.parent_fragment_id` is retained; event-position fields added
  as needed.
- **Pipeline refactor:** `parse_sequence_semantics(source) -> SequenceModel`,
  `compile_sequence_geometry(SequenceModel, width_hint, render_options) ->
  SequenceGeometry`, `sequence_geometry_to_html(SequenceModel, SequenceGeometry,
  render_options) -> str`, `sequence_geometry_to_scene(SequenceModel, SequenceGeometry,
  render_options) -> SvgScene`. Both `to_html` and `to_svg` invoke the same parser and
  compiler.
- **Retire legacy native-SVG parser:** replace `native_svg._sequence_scene` to call the
  canonical compiler and `sequence_geometry_to_scene`. Remove the delegation to
  `layout.sequence.layout_sequence_scene`. Delete `layout/sequence.py` after no imports
  reference it and both sequence fixtures pass.
- **Box painting:** render `BoxGeometry` before lifelines and participant cards. Bounds
  encompass exactly the declared participants. Label retained. CSS color normalized and
  retained. Nested/adjacent boxes have deterministic z-order. `data-box-id` exposed in
  both HTML and SVG.
- **Nested fragment painting:** paint parent fragment background before child fragments.
  Child bounds contained by parent. Branch separators inside their parent. Expose
  `data-fragment-id`, `data-parent-fragment-id`, `data-start-event`, `data-end-event`,
  `data-depth`.
- **No silent skips:** any construct that remains unsupported must produce a typed
  diagnostic and unsupported status rather than disappearing from SVG output.

**Out of scope:**
- Changes to the HTML sequence painter beyond the shared-compiler refactor.
- New sequence diagram syntax support beyond what the HTML compiler already handles.
- ELK or fallback layout for sequence diagrams.

**Never:**
- Derive box or fragment hierarchy from HTML after the fact.
- Use `"native-svg"` as `layout_backend` for sequence diagrams.
- Silently skip `box`, `alt`, `else`, `loop`, `opt`, `par`, `critical`, `break`, `rect`, `end`.

## Acceptance Criteria

- [x] AC1: `sequence-box-unsupported` — 4 participants (Alice, Bob, Carol, Dave). Group A
  has label "Group A", color Blue, contains Alice and Bob only. Group B has label "Group
  B", color rgb(200,100,50), contains Carol only. Dave is outside both boxes. Exactly 4
  messages present and ordered. HTML and SVG consume matching participant, box, and message
  coordinates.
- [x] AC2: The historical `sequence-box-unsupported` fixture filename is preserved; any
  test expectation that box syntax is unsupported is removed.
- [x] AC3: `sequence-nested-fragments` — outer alt (label "success", `parent_fragment_id
  = None`) contains inner loop (label "retry", `parent_fragment_id` = outer alt ID). The
  failure branch belongs to the outer alt. Loop bounds are contained by alt bounds. Two
  retry messages occur inside the loop event interval. Failure notification occurs inside
  the outer alt but outside the loop interval. Native SVG no longer omits the fragments.
- [x] AC4: `layout/sequence.py` is deleted; no remaining imports reference it.
- [x] AC5: Both sequence fixtures report `semantic_compiler = "sequence"` and
  `layout_backend = "sequence-geometry"`.
- [x] AC6: HTML and SVG consume the same `SequenceGeometry` instance (same canvas, same
  participant positions, same box and fragment bounds).
- [x] AC7: All unsupported sequence constructs produce typed diagnostics rather than
  silent omission.
- [x] AC8: `data-box-id` attributes match between HTML and SVG for the same box.
- [x] AC9: `data-fragment-id`, `data-parent-fragment-id`, `data-depth` attributes present
  in both HTML and SVG for nested fragments.

## Testing Strategy

| AC | Verification mode |
|----|-------------------|
| AC1 | TDD: assert `SequenceGeometry.boxes` tuple length and field values |
| AC2 | Goal-based: run canonical runner; verify fixture file still at original path |
| AC3 | TDD: assert fragment hierarchy fields and inner bounds ⊂ outer bounds |
| AC4 | Goal-based: `importlib.util.find_spec("layout.sequence")` returns None |
| AC5 | TDD: render via `compile_sequence`; assert provenance fields |
| AC6 | TDD: call `compile_sequence` twice; assert identical `SequenceGeometry` |
| AC7 | TDD: render `sequence-box-unsupported` via `to_svg`; grep for unsupported construct diagnostic |
| AC8 | TDD: render via `to_html` and `to_svg`; assert `data-box-id` values match |
| AC9 | TDD: render via `to_html` and `to_svg`; assert `data-fragment-id` values match |
