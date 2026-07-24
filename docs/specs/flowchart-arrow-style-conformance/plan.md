# Implementation Plan — Flowchart Arrow Style Conformance

**Status:** Approved

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/_parser.py` (edge token
   normalization); `scripts/mermaid_render/layout/_geometry.py` (`EdgeStyle` and stable
   `edge_id` fields); `scripts/mermaid_render/layout/_strategies.py` or
   `_flowchart_compile.py` (ELK serialization/deserialization style preservation);
   `scripts/mermaid_render/native_svg.py` and HTML painter (SVG stroke/dasharray/marker);
   `tests/test_flowchart_arrow_conformance.py` (new).
2. Done when: `flowchart-arrows-defs` passes the canonical runner in all four lanes
   (ELK+HTML, ELK+SVG, fallback+HTML, fallback+SVG) with nonzero style/marker assertions;
   faithful mode produces no legend or semantic color.
3. Not changing: non-flowchart edge types; existing edge routing geometry; the five fixture
   `.mmd` files.

**Declined patterns:**
- Tempted to use `(source_id, destination_id)` as the edge identity; declining — spec
  requires a stable `edge_id` that survives ELK round-trip.
- Tempted to assign semantic colors (e.g., dashed = async) in faithful mode; declining —
  spec explicitly forbids this.
- Tempted to merge style and marker into a single field; declining — spec requires
  marker ownership asserted separately from stroke style.

---

## Tasks

### Task 1: Stable edge ID through the pipeline
Depends on: none
Verification: TDD

**Tests:**
- `test_edge_id_survives_elk_roundtrip`: serialize a `LayoutEdge` to ELK JSON and
  deserialize; assert `edge_id` is unchanged.
- `test_edge_id_survives_fallback_routing`: route a `LayoutEdge` through the Python
  fallback; assert the `RoutedEdge.edge_id` matches the input.
- `test_edge_id_not_source_destination_pair`: assert `edge_id` values are unique even
  when two edges share the same `(source_id, destination_id)` direction.

**Approach:**
- Ensure `_Edge` has an `edge_id: str` field assigned at parse time (UUID or
  deterministic hash from source text position).
- Propagate `edge_id` through `LayoutEdge`, ELK JSON (`id` field), ELK deserialization,
  `RoutedEdge`.
- Assert `edge_id` in the oracle record.

---

### Task 2: Token normalization to EdgeStyle
Depends on: none
Verification: TDD

**Tests:**
- `test_arrow_token_normal`: `-->` normalizes to `EdgeStyle(line=SOLID, thickness=NORMAL,
  end_marker=ARROW)`.
- `test_arrow_token_thick`: `==>` normalizes to `EdgeStyle(line=SOLID,
  thickness=THICK, end_marker=ARROW)`.
- `test_arrow_token_dotted`: `-.->` normalizes to `EdgeStyle(line=DOTTED,
  end_marker=ARROW)`.
- `test_style_independent_from_color`: `EdgeStyle` does not carry an editorial color field.

**Approach:**
- Add `EdgeStyle(line: LineStyle, thickness: Thickness, end_marker: MarkerType)` to
  `_geometry.py` with enums `LineStyle(SOLID, DOTTED)`, `Thickness(NORMAL, THICK)`,
  `MarkerType(ARROW, NONE, ...)`.
- In `_parser.py`, normalize edge tokens to `EdgeStyle` at parse time.
- Attach `edge_style: EdgeStyle` to `_Edge`, `LayoutEdge`, `RoutedEdge`.

---

### Task 3: Style preservation through ELK serialization
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_elk_serializes_style`: assert the ELK JSON for the `==>` edge contains a
  property encoding `thickness=thick` or equivalent.
- `test_elk_deserializes_style`: after a round-trip, the deserialized `LayoutEdge` has
  `edge_style.line == SOLID` and `edge_style.thickness == THICK` for the `==>` edge.

**Approach:**
- In the ELK serializer, add an `edge-style` property to each edge's ELK JSON using the
  `EdgeStyle` fields.
- In the ELK deserializer, parse that property back into `EdgeStyle`.
- Use a stable property key (e.g., `"ppt:edgeStyle"`) to avoid collision with ELK's own
  style properties.

---

### Task 4: HTML and SVG painting of edge styles
Depends on: Task 2
Verification: TDD

**Tests:**
- `test_html_normal_solid_edge`: `A-->B` in `to_html` output has CSS class or inline
  style for normal stroke (e.g., no extra stroke-width, no dasharray).
- `test_html_thick_solid_edge`: `A==>C` has CSS for thick stroke (e.g.,
  `stroke-width: 3px` or similar token).
- `test_html_dotted_edge`: `A-.->D` has CSS dasharray matching the Mermaid dotted pattern.
- `test_svg_stroke_width`: SVG output for `==>` has `stroke-width` > normal.
- `test_svg_dasharray`: SVG output for `-.->` has a non-empty `stroke-dasharray`.
- `test_marker_present_all_edges`: all five edges in both HTML and SVG have a visible
  arrowhead marker (`marker-end` or equivalent).

**Approach:**
- In the HTML painter, read `edge_style` from the `RoutedEdge` and emit CSS classes or
  inline styles accordingly.
- In `native_svg.py`, read `edge_style` and emit appropriate SVG `stroke-width`,
  `stroke-dasharray`, and `marker-end` attributes.
- Map `EdgeStyle` fields to constants defined in `_constants.py`.

---

### Task 5: Faithful mode guard
Depends on: Task 4
Verification: TDD

**Tests:**
- `test_faithful_mode_no_legend`: `to_html(faithful_mermaid=True)` output for
  `flowchart-arrows-defs` contains no element with a legend or semantic label.
- `test_faithful_mode_no_semantic_color`: same output does not contain any CSS class or
  inline color beyond the neutral stroke color.
- `test_editorial_mode_allows_style`: in editorial mode, style enhancements may be
  present (this test just asserts faithful mode is stricter, not that editorial mode
  breaks anything).

**Approach:**
- Audit the HTML and SVG painters for any legend injection or semantic-color logic gated
  on edge `line` type.
- If found, gate these behaviors on `faithful_mermaid=False` only.
- Add assertions in the oracle records that count style and marker checks separately.
