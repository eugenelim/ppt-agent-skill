# Implementation Plan — requirement-finalized-layout-sizing

- **Spec:** [`spec.md`](spec.md)
- **Status:** Drafting <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn.

## Pre-mortem

**Assumption trio:**

1. **Files I'll touch:**
   - `scripts/mermaid_render/layout/requirement.py` — add `compile_requirement()`, update `layout_requirement_scene` to consume it
   - `scripts/mermaid_render/layout/_strategies.py` — replace `_layout_requirement` body with a call to `compile_requirement()`
   - `tests/test_requirement_layout.py` — new test file (TDD, written before Task 1)
   - `tests/test_syntax_requirement.py` — must stay green (no changes expected, but verify)

2. **Done when:** `pytest tests/` passes; `requirement-basic` fixture passes in both
   HTML and SVG modes; AC10 coordinate-identity test is green; `mypy` reports zero
   new errors on the touched files.

3. **Not changing:**
   - `scripts/mermaid_render/layout/_geometry.py` — `FinalizedLayout`, `NodeLayout`,
     `RoutedEdge` field signatures are frozen for this feature
   - `scripts/mermaid_render/layout/_strategies.py` routing helpers, `_parse_attr_value`,
     and any other diagram-type strategy functions
   - `tests/test_syntax_requirement.py` — existing tests must stay green without edits
   - Any other diagram type's rendering path

**Declined patterns:**

- Inlining the full layout computation inside `_strategies._layout_requirement` — keeps
  the duplication; `compile_requirement()` is the single source of truth.
- Making `compile_requirement()` accept `SvgScene` as an output mode parameter — the
  function returns `FinalizedLayout` only; the scene builder stays as a thin wrapper.
- Adding a caching layer between `compile_requirement()` and the two painters — separate
  calls are separate renders; determinism guarantees identical coordinates without shared
  state.
- Patching `_NODE_W` constant to widen cards — the constant becomes a minimum; measured
  width replaces it.

## Prerequisite

`mermaid-single-finalized-layout-pipeline` must be implemented and merged first.
It provides the FinalizedLayout → HTML and FinalizedLayout → SVG rendering
infrastructure that Tasks 4 and 5 wire into. Do not start Task 4 or Task 5 until
that pipeline is confirmed green.

## Tasks

### Task 1: Test stubs for `compile_requirement()` (TDD scaffolding)
Depends on: none
Verification: TDD — tests written first, all initially xfail or ImportError

**Tests:**
- `tests/test_requirement_layout.py::test_basic_returns_finalized_layout` — calling
  `compile_requirement(src)` on the `requirement-basic` fixture returns a
  `FinalizedLayout` instance.
- `tests/test_requirement_layout.py::test_basic_four_nodes` — `FinalizedLayout`
  has exactly four entries in `node_layouts`.
- `tests/test_requirement_layout.py::test_basic_three_edges` — `FinalizedLayout`
  has exactly three entries in `routed_edges`.
- `tests/test_requirement_layout.py::test_relation_labels_attached` — each
  `RoutedEdge` has a non-None `label_layout`; labels are `{"satisfies", "verifies",
  "derives"}`.
- `tests/test_requirement_layout.py::test_no_edge_through_card` — no segment of
  any `RoutedEdge.waypoints` passes through any `NodeLayout.outer_bounds`.
- `tests/test_requirement_layout.py::test_quoted_path_docref` — a source with
  `docref: "/refs/spec.docx"` parses without `ValueError`; the `docref` attribute
  appears in the corresponding `NodeLayout`.
- `tests/test_requirement_layout.py::test_long_text_card_height` — a source with
  a `text` value exceeding `_TEXT_WRAP_CHARS` produces a `NodeLayout` whose
  `outer_bounds.h` is taller than a node with a one-line text.
- `tests/test_requirement_layout.py::test_multiple_outgoing_relations` — a node
  with three outgoing relations produces three `RoutedEdge` entries, each exiting
  at a different horizontal fraction of the source face.
- `tests/test_requirement_layout.py::test_same_rank_relations` — two nodes at the
  same rank connected by a relation produce a `RoutedEdge` whose waypoints use
  left/right faces (not top/bottom), i.e. all waypoints share neither the source
  top-y nor the source bottom-y.
- `tests/test_requirement_layout.py::test_semantic_subtype_in_css_classes` — each
  `NodeLayout.css_classes` contains the requirement subtype string (e.g.
  `"req-functionalRequirement"`).
- `tests/test_requirement_layout.py::test_width_hint_applied` — passing
  `width_hint=800` to a source that would otherwise produce a narrower canvas
  results in `FinalizedLayout.canvas_bounds.w == 800`.
- `tests/test_requirement_layout.py::test_height_hint_applied` — passing
  `height_hint=600` to a source that would otherwise produce a shorter canvas
  results in `FinalizedLayout.canvas_bounds.h == 600`.

**Approach:**
- Create `tests/test_requirement_layout.py` with the above tests importing
  `compile_requirement` from `mermaid_render.layout.requirement`.  All tests
  fail at import-time (function does not yet exist).  Mark with `pytest.importorskip`
  or let them fail with `ImportError` — do not skip with xfail; the failures
  drive Task 2.

---

### Task 2: `compile_requirement()` — core geometry compiler
Depends on: Task 1
Verification: TDD — Task 1 tests turn green one by one

**Tests:** (Task 1 tests)

**Approach:**

Add `compile_requirement(src: str, *, width_hint: int = 0, height_hint: int = 0) -> FinalizedLayout`
to `scripts/mermaid_render/layout/requirement.py`.

Implementation steps inside the function:

1. **Parse** — call `_parse_requirement_source(src)`; raise `ValueError` on empty
   result (no nodes).

2. **Measure card sizes** — for each node, compute:
   - `card_w`: max of `_NODE_W` (minimum) and the widest rendered line among
     node identifier, subtype display label, and every wrapped `key: value` line
     (use `len(line) * _FONT_ATTR * 0.6` as a pixel estimate, or proportionally
     from the char width used by `_wrap_text`).
   - `card_h`: `_node_height(node)` (already correct — header + wrapped attr rows
     + padding).

3. **Topological rank + ordering** — call `_compute_ranks` and
   `_order_nodes_in_ranks` (unchanged from existing `layout_requirement_scene`
   logic).

4. **Position nodes** — assign `(x, y)` per node using the existing centering
   logic from `layout_requirement_scene`; use per-node `card_w` instead of
   the fixed `_NODE_W` for row-width and offset calculations.

5. **Band-clamped routing** — compute `row_bands` and call `_route_edge` for
   each relation, using the spread `exit_fraction` logic from
   `layout_requirement_scene`.

6. **Assemble `FinalizedLayout`**:
   - For each node: construct a `NodeLayout` with `node_id`, `semantic_shape`
     (`"rect"` for requirements, `"cylinder"` for elements),
     `outer_bounds=Rect(x, y, card_w, card_h)`, `content_bounds` (inset by
     `_ATTR_PAD`), and `css_classes=(f"req-{node['subtype']}",)`.  Populate
     `member_layouts` with one `TextLayout` per wrapped attribute line (to
     carry the text for the painter).
   - For each relation: construct a `RoutedEdge` with waypoints from
     `_route_edge`, `label_layout` set to an `EdgeLabelLayout` with
     `text=rel_type` anchored at the midpoint of the longest waypoint segment
     (reuse `_label_point` logic), `target_marker=MarkerKind.ARROW`.
   - `visible_bounds` = union of all `outer_bounds`.
   - `canvas_bounds` = `visible_bounds` padded by `_PAD_H` / `_PAD_V`.
   - Apply `width_hint` / `height_hint`: if nonzero, scale `canvas_bounds`
     uniformly so that the hinted dimension matches exactly; if repacking would
     produce a better fit (fewer ranks vs more columns) do so, otherwise scale.
   - `direction = "TB"`, `diagram_padding = float(_PAD_H)`.
   - `diagnostics = LayoutDiagnostics((), (), ())`.

---

### Task 3: `layout_requirement_scene` consumes `compile_requirement()`
Depends on: Task 2
Verification: TDD — `TestNativeSceneGeometry` tests in `test_syntax_requirement.py` stay green

**Tests:**
- All existing `TestNativeSceneGeometry` tests in `tests/test_syntax_requirement.py`
  must remain green without modification.
- `tests/test_requirement_layout.py::test_no_edge_through_card` must pass (reuses
  the compiled geometry, not a second pass).

**Approach:**

Replace the internal layout computation in `layout_requirement_scene` with a call
to `compile_requirement(src, width_hint=width_hint)`.  Keep the scene assembly
loop (card rects, attribute text, polylines, labels) but source all coordinates
from `FinalizedLayout`:

- Card rects: `NodeLayout.outer_bounds` for header rect, body rect derived from
  `outer_bounds` minus `_HEADER_H`.
- Attribute text lines: `NodeLayout.member_layouts` (the `TextLayout` tuple
  populated in Task 2).
- Edge polylines: `RoutedEdge.waypoints` (already `tuple[Point, ...]`; convert to
  `tuple[tuple[float, float], ...]` for `ScenePolyline`).
- Edge labels: `RoutedEdge.label_layout.anchor_point` (replaces `_label_point`
  call).

Do not call `_compute_ranks`, `_order_nodes_in_ranks`, or `_route_edge` directly
in `layout_requirement_scene` after this task — all geometry comes from
`compile_requirement()`.

---

### Task 4: `_layout_requirement` in `_strategies.py` calls `compile_requirement()`
Depends on: Task 2, `mermaid-single-finalized-layout-pipeline`
Verification: TDD — existing HTML-path tests in `test_syntax_requirement.py` stay green

**Tests:**
- All `TestRequirementDiagram` tests in `tests/test_syntax_requirement.py` must
  remain green without modification.
- `tests/test_requirement_layout.py::test_quoted_path_docref` — parsed via
  the HTML path; must not raise `ValueError`.

**Approach:**

Replace the body of `_layout_requirement` in `_strategies.py` with:

```python
from .requirement import compile_requirement
layout = compile_requirement(src, width_hint=width_hint)
# delegate to the shared FinalizedLayout → HTML painter
return _render_finalized_layout(layout, direction=direction)
```

Where `_render_finalized_layout` is the FinalizedLayout → HTML function provided
by `mermaid-single-finalized-layout-pipeline`. Remove the local duplicate
`cur_block` / `attr_lines` parser and the `_graph_from_content_nodes` call.

Preserve the `_REQ_REL_RE` import at the top of `_strategies.py` only if other
strategy functions use it; otherwise delete it.

---

### Task 5: AC10 coordinate-identity test
Depends on: Task 3, Task 4
Verification: TDD — new test in `tests/test_requirement_layout.py`

**Tests:**
- `tests/test_requirement_layout.py::test_html_svg_coordinates_identical` —
  calls `compile_requirement(src)` once; asserts that:
  - `NodeLayout.outer_bounds.x` and `.y` for all four nodes match the `x`/`y`
    of the corresponding `SceneRect` elements in the `SvgScene` produced by
    `layout_requirement_scene(src)` (to within 0.5 px floating-point tolerance).
  - `RoutedEdge.waypoints` for all three edges match the `ScenePolyline.points`
    in the `SvgScene` (same tolerance).

**Approach:**

Call `compile_requirement(src)` to get the `FinalizedLayout`, then call
`layout_requirement_scene(src)` to get the `SvgScene`.  Extract coordinates
from both outputs and assert equality.  If `layout_requirement_scene` already
calls `compile_requirement()` (Task 3), the equality is guaranteed by
construction — this test documents and guards that invariant.

---

### Task 6: Gates
Depends on: Tasks 1–5
Verification: Full suite green

**Tests:** (all existing + new)

**Approach:**

Run:
```
pytest tests/ -x -q
mypy scripts/mermaid_render/layout/requirement.py scripts/mermaid_render/layout/_strategies.py
```

Fix any type errors introduced by the new `FinalizedLayout` construction sites
(e.g. `PortLayout` default for nodes that have no ports, `TextLayout` construction
for `member_layouts`).  Do not suppress errors with `# type: ignore` without a
comment explaining why.

Done when both commands exit 0 and `requirement-basic` fixture passes in both
rendering modes.
