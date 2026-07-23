# Plan: class-diagram-marker-semantics

## Tasks

### Task 1: MarkerSpec model (TDD)
Depends on: none

Add `HOLLOW_TRIANGLE` and `HOLLOW_DIAMOND` to `MarkerKind` in
`layout/_geometry.py`.  Add the `MarkerSpec` dataclass with:
`kind: MarkerKind`, `end: str` ("SOURCE"|"TARGET"),
`size: float`, `line_join: str`, `fill: str`, `stroke: str`, `clearance: float`.

Tests:
- `MarkerSpec(kind=MarkerKind.HOLLOW_TRIANGLE, end="SOURCE")` round-trips via
  `dataclasses.asdict()`.
- Default `size=10.0`, `clearance=12.0` for triangle/diamond kinds.
- `end` accepts "SOURCE" or "TARGET"; rejects other strings at construction.

Approach:
- Edit `_geometry.py`: add two enum values after `FILLED_DIAMOND`.
- Add frozen `MarkerSpec` dataclass with field defaults; validate `end` in
  `__post_init__` (raises `ValueError` on invalid value).
- Export `MarkerSpec` via `_geometry.__all__` alongside `MarkerKind`.

Done when: `from mermaid_render.layout._geometry import MarkerSpec, MarkerKind`
succeeds and basic attribute access works.

---

### Task 2: _Edge migration (goal-based)
Depends on: Task 1

Remove `arrow_src: bool = False` from `_Edge` in `_constants.py`.
Change `source_marker: MarkerKind = MarkerKind.NONE` →
`source_marker: MarkerSpec = field(default_factory=_none_marker_spec)`.
Same for `target_marker`.

Update `_parser.py`:
- `_src_mk = MarkerSpec(kind=MarkerKind.ARROW, end="SOURCE")` if bidir else NONE spec
- `_dst_mk = MarkerSpec(kind=MarkerKind.ARROW, end="TARGET")` if has_arrow else NONE spec

Update `_strategies.py` at `_compile_flowchart_to_layout_graph` (~line 4958):
- Extract `e.source_marker.kind` when assigning to `LayoutEdge.source_marker`
- `dst_mk = e.target_marker.kind if e.target_marker.kind != MarkerKind.NONE else (MarkerKind.ARROW if e.arrow else MarkerKind.NONE)`

Update existing tests `TestArrowSemantics` in `test_mermaid_layout.py`:
- `edge.target_marker == MarkerKind.ARROW` → `edge.target_marker.kind == MarkerKind.ARROW`
- Same for source_marker assertions.

Done when: existing test suite runs green (full suite, not just class tests).

---

### Task 3: Class relation parser (TDD)
Depends on: Task 2

Add `_class_rel_markers(op: str) -> tuple[MarkerSpec, MarkerSpec, str]` to
`layout/_strategies.py`.  Return `(source_spec, target_spec, line_style)` where
`line_style` is `"cls-solid"` or `"cls-dotted"`.

Mapping:
```
op           source_spec.kind   target_spec.kind   line_style
<|--         HOLLOW_TRIANGLE    NONE               cls-solid
<|..         HOLLOW_TRIANGLE    NONE               cls-dotted
*--          FILLED_DIAMOND     NONE               cls-solid
--*          NONE               FILLED_DIAMOND     cls-solid (rare right-to-left)
o--          HOLLOW_DIAMOND     NONE               cls-solid
--o          NONE               HOLLOW_DIAMOND     cls-solid
-->          NONE               OPEN_ARROW         cls-solid
..>          NONE               OPEN_ARROW         cls-dotted
..|>         NONE               HOLLOW_TRIANGLE    cls-dotted
..>|         HOLLOW_TRIANGLE    NONE               cls-dotted  (reversed notation)
```

Update `_layout_class` to use `_class_rel_markers` instead of
`_class_rel_style` + `arrow_src`.  Update `native_svg.py` similarly.

Tests (in `test_class_semantic.py`):
- Each operator above: assert `source_spec.kind`, `target_spec.kind`, `line_style`.
- `_class_rel_markers("<|--") == (MarkerSpec(HOLLOW_TRIANGLE,SOURCE), MarkerSpec(NONE,TARGET), "cls-solid")`
- ... for all 6 fixture operators

Done when: all 6 operators map correctly.

---

### Task 4: Routing update (goal-based)
Depends on: Task 3

In `layout/_routing.py`, replace the `arrow_src` check with `MarkerSpec`-based
marker selection.

Old code (~line 794-806):
```python
elif e.style.startswith("cls-"):
    _mid = e.style.replace("-dotted", "")
...
if e.arrow and getattr(e, "arrow_src", False):
    marker_id = _mid + "-rev"
```

New code:
- When `e.style.startswith("cls")` (handles `"cls-solid"` and `"cls-dotted"`):
  - Check `e.source_marker.kind != MarkerKind.NONE` → `marker_id = _kind_to_mid(src_kind) + "-rev"`
  - Else check `e.target_marker.kind != MarkerKind.NONE` → `marker_id = _kind_to_mid(tgt_kind)`
  - Add `_kind_to_mid` helper mapping kinds to `cls-inherit`/`cls-composition`/`cls-aggregation`/`cls-dep`
- Keep dash detection: `e.style.endswith("-dotted")` still works for `"cls-dotted"`

Also shorten route endpoints by `MarkerSpec.clearance` along the path tangent
(requirement 3): after computing waypoints, adjust the endpoint `clearance` px
back from the node face in the direction of the incoming route tangent.

Done when: rendered HTML for `A <|-- B` has `marker-start="url(#cls-inherit-rev)"`
and for `A ..|> B` has `marker-end="url(#cls-inherit)"`.

---

### Task 5: Semantic tests (TDD)
Depends on: Task 3

Create `tests/test_class_semantic.py` with `TestClassRelationSemantics`.

For each of the 7 relations in `class-relationships-all.mmd`:
- Parse with `_CLASS_REL_RE`
- Call `_class_rel_markers(op)` 
- Assert `source_marker.kind`, `target_marker.kind`, both `.end` values,
  `line_style` (cls-solid vs cls-dotted), src/dst node names, label text.

Also test rendered HTML output:
- Correct `marker-start` vs `marker-end` attribute used.
- Presence of `stroke-dasharray` for dotted relations.
- No label overlap (bounding box check).

Done when: all 7 relations are covered and tests pass.
