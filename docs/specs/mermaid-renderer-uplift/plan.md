# Plan: Mermaid Renderer Quality Uplift

- **Spec:** [`spec.md`](spec.md)
- **Status:** Drafting

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Nine improvements across three waves. **Wave 1** (T1–T5, T9a) delivers the foundational changes — text metrics, diamond clipping, new node shapes, inline label formatting, and SVG marker vocabulary — plus the fixture corpus scaffolding. These tasks share `tests/test_mermaid_layout.py`, `_constants.py`, and `_renderer.py`, so they run sequentially within the wave despite having no logical dependency on each other; the order listed below is the safe implementation order. **Wave 2** (T6, T7, T8) applies the SVG marker infrastructure from T5 to sequence, ER, and class notation in `_strategies.py`; T6→T7→T8 run sequentially because they all edit `_strategies.py`. **Wave 3** (T10) captures screenshot baselines, validates the full regression suite, and closes out.

The riskiest change is T1 (text metrics): replacing the `max_chars` character-count wrap heuristic with pixel-width measurement touches every diagram type. Its test suite runs first and serves as the early-warning canary for the rest of wave 1.

## Constraints

No ADRs or RFCs constrain this implementation. The output format (HTML/CSS div + SVG overlay) and the public `_dispatch` signature are preserved by the spec's Boundaries.

## Construction tests

**Integration tests:** `pytest tests/` passes clean across all waves. `pytest tests/test_snapshots.py --snapshot-capture` re-captures baselines after Wave 2 passes; `pytest tests/test_snapshots.py` (regression mode) passes in Wave 3.

**Manual verification:** after Wave 2, open each fixture HTML in a browser by running `python3 -m scripts.mermaid_layout --source @tests/fixtures/<name>.mmd > /tmp/diag.html && open /tmp/diag.html` and visually inspect before committing baselines.

## Design (LLD)

### Design decisions

- Text metrics and updated `_wrap_label` live in `_constants.py` alongside the existing label utilities — no new module (traces to: AC-1, AC-2).
- `_wrap_label` changes its wrap parameter from `max_chars: int` to `width_budget: int` (default `NODE_W − 40`); icon-card callers pass `NODE_W − 40 − ICON_COL_WIDTH` explicitly. The return type stays `list[str]` — the `<br>` join continues to happen in `_renderer.py` (traces to: AC-2).
- Diamond clipping is a pure function `_clip_to_diamond` in `_routing.py`; called in `_route_edges` only when `n.shape == 'diamond'` (traces to: AC-3).
- New shape CSS entries extend `_NODE_CSS` in `_renderer.py`; new shape regex branches extend `_SPEC_RE` and `_SPEC_SHAPE_MAP` in `_parser.py`; no new dataclass fields on `_Node` (traces to: AC-4, AC-5).
- Inline formatting is a `_render_label_html(label: str) -> str` helper in `_renderer.py`; applied at the single `"<br>".join(...)` site so it receives the already-wrapped `list[str]` and transforms the joined string (traces to: AC-6).
- SVG `<defs>` markers use stable IDs: `arrow-normal`, `arrow-thick`, `arrow-open` (flowchart/state); `cls-inherit`, `cls-composition`, `cls-aggregation`, `cls-dep` (class); `er-one`, `er-zero-one`, `er-many`, `er-zero-many` (ER). Legend inline SVGs remain unchanged (traces to: AC-7, AC-12, AC-13).
- Sequence, ER, and class notation enhancements live inside their existing strategy functions in `_strategies.py` (traces to: AC-8 through AC-13).
- Snapshot harness uses `scripts/html2png.py` (puppeteer `25.3.0`, already in `package.json`) for HTML→PNG; pixel comparison uses Pillow (already in `requirements.txt`) (traces to: AC-15).

### Data & schema

- `_Node.shape` type literal in `_constants.py` expands to include: `stadium`, `hexagon`, `subroutine`, `trapezoid`, `trapezoid-alt`, `doublecircle` (traces to: AC-4).
- `_Edge` gains two optional fields: `cardinality_src: Optional[str] = None` and `cardinality_dst: Optional[str] = None`, used by ER rendering only (traces to: AC-12).
- No persistence changes — all in-memory dataclasses.

### Interfaces & contracts

- `_dispatch(src, direction_override, width_hint, height_hint, style_overrides) -> str` — signature and return type unchanged (traces to: AC-17).

### Component / module decomposition

| Module | Task(s) | Changes |
|---|---|---|
| `_constants.py` | T1, T7 | Add `_measure_text_width`; update `_wrap_label` to `width_budget` pixel parameter; add `cardinality_src/dst` to `_Edge` |
| `_parser.py` | T3, T7 | Add 5 new shape regex branches; add ER cardinality token capture |
| `_routing.py` | T2, T5 | Add `_clip_to_diamond`; remove per-edge polygon arrowheads; return `marker_id` per edge |
| `_renderer.py` | T3, T4, T5 | Extend `_NODE_CSS`; add `_render_label_html`; emit `<defs>` + `<marker>` block in overlay SVG |
| `_strategies.py` | T6, T7, T8 | Sequence: activation boxes, self-loops, dog-ear notes, block headers; ER: crow's foot; Class: UML markers |
| `tests/test_mermaid_layout.py` | T1–T8, T9a | New test classes per improvement area |
| `tests/fixtures/*.mmd` | T9a | ≥ 27 new fixture files (new directory) |
| `tests/test_snapshots.py` | T9a | New file — screenshot baseline harness |
| `tests/conftest.py` | T9a | New file — registers `--snapshot-capture` pytest option |
| `tests/snapshots/*.png` | T10 | Committed baselines |

### Behavior & rules

**Text metrics — character-class bucketing:**

Width = `sum(char_ratio(c) for c in text) × font_size × base_ratio + font_size × 0.15` where:
- `base_ratio`: 0.60 (weight ≥ 600), 0.57 (≥ 500), 0.54 (lighter)
- `char_ratio(c)`: 0.0 (combining marks U+0300–U+036F), 0.3 (space), 0.4 (narrow: `iltfjI1!|.,:;'`), 0.5 (semi-narrow punct: `()[]{}/\-"\``), 0.8 (`r`), 1.2 (uppercase A–Z), 1.5 (`WMwm@%`), 2.0 (CJK/emoji U+4E00+), 1.0 (all other)

`_wrap_label` wraps when a new word would push the cumulative line width past `width_budget` (default `NODE_W − 40`). Return type stays `list[str]`.

**Diamond clipping:**
Diamond vertices: top `(cx, cy−h/2)`, right `(cx+w/2, cy)`, bottom `(cx, cy+h/2)`, left `(cx−w/2, cy)`. Parametric ray from just outside the endpoint along `(−dx, −dy)` intersects 4 diamond edges (`t ∈ (0, 1]`); first intersection is the clipped point. Falls back to the nearest vertex if no intersection found.

**SVG marker geometry (unchanged from current arrowhead):**
Normal: `back=9, half_w=4`; thick: `back=11, half_w=5`; open (dotted): open-chevron `<path>`, no fill. Crow's foot geometry: see Behavior rules in Design (LLD) below.

**Crow's foot marker geometry:**
- One (`||`): two parallel lines 6px apart, perpendicular to edge, 8px from endpoint.
- Zero-or-one (`o|`): circle r=4px at 16px from endpoint, bar line at 8px.
- Many (`}|` / `|{`): three lines fanning ±12° from centre, 8px long, base at 8px from endpoint.
- Zero-or-many (`o{` / `}o`): circle r=4px at 20px, fan base at 8px.

**Inline formatting — interaction with `_wrap_label`:**
`_render_label_html` operates on the already-joined string (after `"<br>".join(...)`). Delimiters (`**`, `*`, `~~`) that straddle a `<br>` boundary are treated as two separate spans, one per line segment. No delimiter is split across a `<br>` — the state machine resets at each `<br>`.

### Failure, edge cases & resilience

- `_measure_text_width("")` returns 0 — no divide-by-zero.
- `_clip_to_diamond` with perfectly vertical or horizontal approach falls back to the nearest vertex rather than erroring.
- `_render_label_html` with mismatched delimiters emits no partial HTML tags — returns the raw segment as literal text.
- `hexagon` `clip-path` requires the node `<div>` to have `overflow: visible`; verify no parent container clips it.
- `tests/test_snapshots.py` skips the entire module (not fails) when `shutil.which("node") is None`, mirroring `diagram_render_check.py`'s pattern.
- Sequence diagrams without `activate`/`deactivate` produce zero activation `<rect>` elements — no regression for existing sequence tests.

## Tasks

### T1: Pixel-accurate text width measurement

**Depends on:** none

**Touches:** `scripts/mermaid_layout/_constants.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `TestMeasureTextWidth.test_narrow_lt_wide`: `_measure_text_width("i", 13, 400)` < `_measure_text_width("W", 13, 400)`.
- `test_empty_string`: `_measure_text_width("", 13, 400)` == 0.
- `test_cjk_wider_than_ascii`: `_measure_text_width("你好", 13, 400)` ≥ `_measure_text_width("ab", 13, 400)`.
- `test_heavier_weight_wider`: `_measure_text_width("test", 13, 600)` > `_measure_text_width("test", 13, 400)`.
- `test_reference_set_within_15pct`: for each of 10 `(text, font_size, font_weight, oracle_px)` tuples hardcoded from browser `canvas.measureText` measurements (document the measurement method and font in the test), assert `abs(result − oracle_px) / oracle_px ≤ 0.15`.
- `TestWrapLabelBudget.test_long_label_wraps`: `_wrap_label("A very long service label that will exceed the pixel threshold at thirteen pixels")` returns a list with `len > 1`.
- `test_short_label_unchanged`: `_wrap_label("Auth")` == `["Auth"]`.
- `test_hyphen_boundary`: `_wrap_label("event-driven-architecture-platform")` splits at a hyphen boundary; result is a list of ≥ 2 strings.
- `test_max_chars_removed`: calling `_wrap_label("x", max_chars=20)` raises `TypeError` (verifies AC-2 removal of old parameter).
- `test_icon_narrow_budget`: `_wrap_label("long icon label text here", width_budget=NODE_W - 40 - ICON_COL_WIDTH)` returns a list with more items than `_wrap_label("long icon label text here")` (verifies narrower budget wraps sooner).
- `test_icon_card_wraps_with_icon`: render a flowchart node with an icon (`:::server` class or equivalent) where the label is wide enough to fit on one line without an icon but wraps to two lines with the icon column; assert the rendered node HTML contains a `<br>` (render-level caller test).

**Approach:**
1. Add `_CHAR_CLASS_RATIOS` constant and `_measure_text_width(text, font_size, font_weight) -> float` to `_constants.py` after the existing label utilities. Use `ord()` range checks and string membership — no regex, no external lib.
2. Add `ICON_COL_WIDTH: int = 34` (icon 24px + margin 10px) to `_constants.py` alongside the other layout constants.
3. Change `_wrap_label`'s signature from `max_chars: int = 20` to `width_budget: int = NODE_W - 40`. Accumulate pixel width per word; wrap when adding the next word would exceed `width_budget`. Return type stays `list[str]`.
4. Update all internal callers: icon-card callers pass `width_budget=NODE_W - 40 - ICON_COL_WIDTH`. **Both** the height-computation path (`_constants.py`) and the render path (`_renderer.py`) must pass the identical `width_budget` for icon cards — verify both sites before marking done.

**Done when:** `TestMeasureTextWidth` and `TestWrapLabelBudget` pass; `pytest tests/test_mermaid_layout.py` fully green.

---

### T2: Diamond edge-endpoint clipping

**Depends on:** T1

**Touches:** `scripts/mermaid_layout/_routing.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `TestClipToDiamond.test_approach_from_below`: `_clip_to_diamond(cx, cy+100, cx, cy, w=60, h=40, dx=0, dy=-1)` returns a point on the bottom face — verify `abs((y − cy) / (h/2)) + abs((x − cx) / (w/2)) ≈ 1.0` (on diamond outline).
- `test_approach_from_right`: returned x < `cx + w/2`.
- `test_approach_from_above`: returned y < `cy`.
- `test_horizontal_approach`: `dy=0`, `dx=-1` → falls back to right vertex `(cx+w/2, cy)`.
- `test_result_on_diamond_edge`: for a known non-axis approach, verify `|dx_norm| + |dy_norm| ≈ 1.0` (Manhattan distance from centre = half-size, confirming point lies on diamond outline).
- `TestDiamondEdgePath.test_endpoint_satisfies_outline_equation`: render `flowchart TB\nA{Diamond} --> B[Rect]`; parse first `M x,y` from the overlay SVG `<path>` `d` attribute; compute `|x − cx| / (w/2) + |y − cy| / (h/2)`; assert the value is ≤ 1.05 (on face, not outside) and ≥ 0.90 (not at centre).

**Approach:**
1. Add `_clip_to_diamond(tip_x, tip_y, cx, cy, w, h, dx, dy) -> tuple[float, float]` to `_routing.py`. Parametric intersection against 4 diamond edges; return first `t ∈ (0, 1]` solution; fall back to nearest vertex.
2. In `_route_edges`: if `src.shape == 'diamond'`, call `_clip_to_diamond` for the source endpoint using the first segment direction; if `dst.shape == 'diamond'`, call it for the destination endpoint using the last segment direction reversed.

**Done when:** `TestClipToDiamond` and `TestDiamondEdgePath` pass; `pytest tests/test_mermaid_layout.py` green.

---

### T3: Six new/updated node shapes

**Depends on:** T2

**Touches:** `scripts/mermaid_layout/_parser.py`, `scripts/mermaid_layout/_renderer.py`, `scripts/mermaid_layout/_constants.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `TestParseNewShapes.test_stadium`: `_parse_spec("A([stadium label])")` → `('A', 'stadium label', 'stadium')`.
- `test_hexagon`: `_parse_spec("A{{hex}}")` → shape `'hexagon'`.
- `test_subroutine`: `_parse_spec("A[[sub]]")` → shape `'subroutine'`.
- `test_trapezoid`: `_parse_spec("A[/trap/]")` → shape `'trapezoid'`.
- `test_trapezoid_alt`: `_parse_spec("A[\\alt\\]")` → shape `'trapezoid-alt'`.
- `test_doublecircle`: `_parse_spec("A(((dc)))")` → shape `'doublecircle'`.
- `test_existing_diamond_unaffected`: `_parse_spec("A{diamond}")` → shape `'diamond'` (single-brace still diamond).
- `test_existing_circle_unaffected`: `_parse_spec("A((circle))")` → shape `'circle'`.
- `TestNewShapeCSS.test_stadium_pill`: render `flowchart TB\nA([My Service])`; assert node HTML contains a `border-radius` value distinct from the `round` shape value (≥ 50% on short axis).
- `test_hexagon_clippath`: render a hexagon node; assert `clip-path:polygon(` appears with exactly 6 coordinate pairs.
- `test_subroutine_inner_lines`: render a subroutine node; assert two `<line` elements inside the SVG overlay with x-coordinates ≈ 8px from node left and node right edges.
- `test_trapezoid_vs_trapezoid_alt`: render both; assert their `clip-path` polygon strings differ (opposing slant direction).
- `test_doublecircle_concentric`: render a doublecircle node; assert two elements with `border-radius:50%` at different sizes.

**Approach:**
1. In `_parser.py` `_SPEC_RE`, add regex branches in priority order (before any branch that could partially match): `\(\(\((?P<doublecircle>[^)]*)\)\)\)`, `\{\{(?P<hexagon>[^}]*)\}\}`, `\[\[(?P<subroutine>[^\]]*)\]\]`, `\[/(?P<trapezoid>[^/]*)/\]`, `\[\\(?P<trapezoid_alt>[^\\]*)\\\]`. Update `_SPEC_SHAPE_MAP`: change `"stadium": "round"` to `"stadium": "stadium"` and add the 5 new entries.
2. In `_renderer.py` `_NODE_CSS`, add CSS entries for `stadium`, `hexagon`, `trapezoid`, `trapezoid-alt`. Add special-case render branches for `subroutine` (two inner SVG `<line>` elements) and `doublecircle` (outer div + inner concentric div, both `border-radius:50%`, inner inset 5px on all sides via `position:absolute`).
3. In `_constants.py` `_node_render_h`, add case for `doublecircle`: minimum height = `max(NODE_W, NODE_H) + 8`.

**Done when:** `TestParseNewShapes` and `TestNewShapeCSS` pass; `pytest tests/test_mermaid_layout.py` green.

---

### T4: Inline label formatting

**Depends on:** T3

**Touches:** `scripts/mermaid_layout/_renderer.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `TestInlineLabelFormatting.test_bold`: `_render_label_html("**bold**")` contains `font-weight:700` or `<strong>`.
- `test_italic`: `_render_label_html("*italic*")` contains `font-style:italic` or `<em>`.
- `test_strike`: `_render_label_html("~~strike~~")` contains `text-decoration:line-through` or `<s>`.
- `test_mixed`: `_render_label_html("**bold** and *italic*")` contains both weight and italic markers.
- `test_plain_unchanged`: `_render_label_html("plain text")` == `"plain text"`.
- `test_mismatched_bold`: `_render_label_html("**no close")` == `"**no close"` — no partial tags.
- `test_br_preserved`: `_render_label_html("line one<br>line two")` contains `<br>` unchanged.
- `test_bold_straddles_br`: `_render_label_html("**start<br>end**")` — state machine resets at `<br>`; assert the result has no cross-`<br>` open HTML tag (i.e. a `</strong>` or closing span does not appear before its matching open span on the same side of the break).
- `test_integration_in_render`: render `flowchart TB\nA["**Service Name**"]`; assert rendered HTML for that node contains a bold marker.

**Approach:**
1. Add `_render_label_html(label: str) -> str` to `_renderer.py`. Single-pass state machine over the joined label string (after `"<br>".join`). Handles `**`, `*`, `~~` tokens; resets state at `<br>` boundary. On balanced pair, emits `<span style="font-weight:700">…</span>`, etc.; on mismatch, emits delimiter as literal.
2. Apply `_render_label_html` at the `"<br>".join(wrapped_lines)` site in `_render_graph_fragment` — after joining, not inside `_wrap_label`.

**Done when:** `TestInlineLabelFormatting` passes; integration render test passes; `pytest tests/test_mermaid_layout.py` green.

---

### T5: SVG `<marker>` definitions in `<defs>`

**Depends on:** T4

**Touches:** `scripts/mermaid_layout/_renderer.py`, `scripts/mermaid_layout/_routing.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `TestSVGMarkerDefs.test_defs_present_in_overlay`: render any flowchart with ≥ 1 edge; extract the overlay `<svg>…</svg>` substring; assert `<defs>` appears exactly once within it.
- `test_arrow_normal_defined_once`: `overlay_svg.count('<marker id="arrow-normal"')` == 1.
- `test_thick_marker_for_thick_edge`: render a diagram with a `==>` edge; assert `<marker id="arrow-thick"` appears in the overlay SVG.
- `test_no_polygon_in_overlay_outside_defs`: extract overlay SVG; strip the `<defs>…</defs>` substring; assert `<polygon` does not appear in the remainder. (Legend HTML is outside the overlay SVG and is not checked here.)
- `test_marker_end_count`: for a 10-edge same-style diagram, `overlay_svg.count('marker-end=')` == 10.
- `TestArrowMarkerReferencing.test_path_has_marker_end`: `marker-end="url(#arrow-normal)"` present on a normal-edge `<path>`.
- `test_dotted_edge_uses_open_marker`: render a `-.-` edge; assert `<marker id="arrow-open"` present and `stroke-dasharray` on the `<path>`.

**Approach:**
1. In `_routing.py`, replace per-edge arrowhead polygon output with `marker_id: str` (`"arrow-normal"`, `"arrow-thick"`, `"arrow-open"`) in each routed edge's return value.
2. In `_renderer.py` `_render_graph_fragment`, scan the routed edge list to collect the set of marker IDs in use; emit a `<defs>` block immediately after the `<svg>` opening tag. Each `<marker>` holds a `<polygon>` or `<path>` using the same geometry as the current per-edge arrowhead. Remove the per-edge `<polygon>` arrowhead emit. Add `marker-end="url(#{marker_id})"` to each `<path>`.

**Done when:** `TestSVGMarkerDefs` and `TestArrowMarkerReferencing` pass; visual output unchanged; `pytest tests/test_mermaid_layout.py` green.

---

### T6: Sequence diagram enhancements

**Depends on:** T5

**Touches:** `scripts/mermaid_layout/_strategies.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `TestSequenceActivation.test_activation_rect`: render `sequenceDiagram\nA->>B: req\nactivate B\nB->>A: res\ndeactivate B`; assert a `<rect` element in the SVG with a fill color and width ≈ 8px appears on the lifeline.
- `TestSequenceSelfMessage.test_self_loop_path`: render `sequenceDiagram\nA->>A: self`; assert SVG `<path` `d` attribute contains `C` (cubic bezier).
- `TestSequenceDogEarNote.test_polygon_5pts`: render `sequenceDiagram\nNote over A: note text`; assert a `<polygon` with exactly 5 `x,y` point pairs appears.
- `TestSequenceBlock.test_loop_rect`: render `sequenceDiagram\nloop retry\nA->>B: msg\nend`; assert a containing `<rect` and the text `retry` appear in output HTML.
- `TestSequenceAltBlock.test_divider_line`: render `sequenceDiagram\nalt success\nA->>B: ok\nelse fail\nA->>B: err\nend`; assert a `<line` divider element appears.

**Approach:**
1. In `_layout_lifeline` in `_strategies.py`, add a pre-pass to scan for `activate`/`deactivate`, `Note over`, `loop`/`alt`/`opt`/`end` lines; build activation-stack per participant, note list, and block list.
2. Emit activation `<rect>` (width=8, centered on lifeline x) spanning activate-y to deactivate-y.
3. For self-messages (`src == dst`): route as cubic bezier with control points offset rightward by `SELF_LOOP_DX=28`.
4. For notes: compute 5-point polygon with 10px dog-ear fold at top-right.
5. For blocks: `<rect>` container spanning messages + `GROUP_PAD`; header `<rect>` with block type label; `alt` adds a `<line>` at the `else` boundary.

**Done when:** all five `TestSequence*` test classes pass; `pytest tests/test_mermaid_layout.py` green.

---

### T7: ER diagram crow's foot notation

**Depends on:** T5, T6

**Touches:** `scripts/mermaid_layout/_parser.py`, `scripts/mermaid_layout/_constants.py`, `scripts/mermaid_layout/_strategies.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `TestERCardinality.test_one_to_zero_many`: parse `Customer ||--o{ Order : places`; assert `_Edge` has `cardinality_src='one'`, `cardinality_dst='zero-many'`.
- `test_many_to_one`: parse `Order }|--|| Line : contains`; assert `cardinality_src='many'`, `cardinality_dst='one'`.
- `test_zero_one_to_many`: parse `A o|--|{ B : rel`; assert `cardinality_src='zero-one'`, `cardinality_dst='many'`.
- `TestERCrowsFoot.test_one_marker`: render ER with `||--||`; assert two parallel `<line` elements appear near each endpoint.
- `test_zero_many_marker`: render `||--o{`; assert `<circle` + fan `<line>` elements near the `o{` endpoint.
- `test_markers_within_16px`: for rendered crow's foot elements, verify their SVG coordinates are within 16px of the corresponding edge endpoint (parsed from the `<path>` `d` attribute).

**Approach:**
1. Add `cardinality_src: Optional[str] = None` and `cardinality_dst: Optional[str] = None` to `_Edge` in `_constants.py`.
2. In `_parser.py`, update the ER edge regex to capture cardinality tokens at each end; map to `'one'`, `'zero-one'`, `'many'`, `'zero-many'`.
3. In `_layout_er` in `_strategies.py`, after routing edges, call `_render_crow_foot(x, y, dx, dy, kind)` for each endpoint with a non-None cardinality; emit the appropriate SVG `<line>`/`<circle>` elements and append to the overlay SVG string.

**Done when:** `TestERCardinality` and `TestERCrowsFoot` pass; `pytest tests/test_mermaid_layout.py` green.

---

### T8: Class diagram UML relationship markers

**Depends on:** T5, T6, T7

**Touches:** `scripts/mermaid_layout/_strategies.py`, `scripts/mermaid_layout/_renderer.py`, `tests/test_mermaid_layout.py`

**Tests:**
- `TestClassRelationshipParse.test_inherit`: parsing `<|--` returns `('inherit', False)` (marker type, is_dashed).
- `test_composition`: `*--` → `('composition', False)`.
- `test_aggregation`: `o--` → `('aggregation', False)`.
- `test_dependency_dashed`: `..|>` → `('inherit', True)`.
- `TestClassMarkerDefs.test_all_four_present`: render a class diagram with one relationship of each type; assert `<marker id="cls-inherit"`, `id="cls-composition"`, `id="cls-aggregation"`, `id="cls-dep"` each appear exactly once in `<defs>`.
- `TestClassDashedLine.test_dashed_on_realization`: render a `..|>` relationship; assert `stroke-dasharray` on the `<path>`.
- `TestClassInheritanceTriangle.test_hollow`: `<marker id="cls-inherit"` body contains `fill="none"` or `fill="var(--bg)"`.
- `TestClassCompositionDiamond.test_filled`: `<marker id="cls-composition"` body does not contain `fill="none"`.

**Approach:**
1. In `_layout_class` in `_strategies.py`, add a relationship-type parser mapping operator tokens to `(marker_type, is_dashed)`.
2. Re-use the T5 `<defs>` infrastructure to emit `cls-*` markers when a class diagram is rendered. Hollow triangle for `cls-inherit`; filled diamond for `cls-composition`; hollow diamond for `cls-aggregation`; open-chevron `<path>` for `cls-dep`.
3. On each relationship `<path>`: set `marker-end="url(#cls-{type})"` and `stroke-dasharray` if `is_dashed`.

**Done when:** all `TestClass*` test classes pass; `pytest tests/test_mermaid_layout.py` green.

---

### T9a: Fixture corpus and snapshot harness scaffolding

**Depends on:** T5

**Touches:** `tests/fixtures/` (new directory), `tests/test_snapshots.py` (new file), `tests/conftest.py` (new file), `tests/test_mermaid_layout.py`

**Tests:**
- `TestFixtureCorpus.test_all_fixtures_dispatch` (in `tests/test_mermaid_layout.py`): for each `.mmd` file in `tests/fixtures/`, `_dispatch(src)` must not raise and returned HTML must contain `diagram mermaid-layout`.
- `TestFixtureCorpus.test_no_overflow` (in `tests/test_mermaid_layout.py`): for each fixture, extract the pre-legend canvas height from the overlay SVG's inline style via `re.search(r'<svg\b[^>]*style="[^"]*\bheight:(\d+)px', html)` (matches `_renderer.py:294`; excludes the outer wrapper div's `effective_h` and legend swatch `<svg height="10">` attributes); parse all node `top` + computed heights; assert none exceed `canvas_height + CANVAS_PAD`. (Satisfies AC-16.)
- `TestSnapshotHarness.test_skip_when_no_node`: when `shutil.which("node") is None`, `test_snapshots.py` tests are skipped, not failed.

**Fixture table — ≥ 27 `.mmd` files in `tests/fixtures/`:**

| File | Covers |
|---|---|
| `flowchart-tb-text-metrics.mmd` | AC-1, AC-2 (long labels with CJK + narrow chars) |
| `flowchart-lr-text-metrics.mmd` | AC-1, AC-2 (LR orientation) |
| `flowchart-diamond-clipping.mmd` | AC-3 |
| `flowchart-shapes-new.mmd` | AC-4, AC-5 (all 6 new shapes) |
| `flowchart-label-formatting.mmd` | AC-6 (bold, italic, strike) |
| `flowchart-arrows-defs.mmd` | AC-7 (normal, thick, dotted edges) |
| `sequence-basic.mmd` | baseline sequence |
| `sequence-activation.mmd` | AC-8 |
| `sequence-self-message.mmd` | AC-9 |
| `sequence-note.mmd` | AC-10 |
| `sequence-blocks.mmd` | AC-11 (loop + alt) |
| `er-basic.mmd` | baseline ER |
| `er-cardinality-all.mmd` | AC-12 (all 4 cardinality types) |
| `class-basic.mmd` | baseline class |
| `class-relationships-all.mmd` | AC-13 (all 4 relationship types) |
| `statediagram-basic.mmd` | stateDiagram-v2 type coverage |
| `gantt-basic.mmd` | gantt type coverage |
| `timeline-basic.mmd` | timeline type coverage |
| `quadrant-basic.mmd` | quadrantChart type coverage |
| `pie-basic.mmd` | pie type coverage |
| `xychart-basic.mmd` | xychart-beta type coverage |
| `mindmap-basic.mmd` | mindmap type coverage |
| `block-basic.mmd` | block-beta type coverage |
| `packet-basic.mmd` | packet-beta type coverage |
| `kanban-basic.mmd` | kanban type coverage |
| `architecture-basic.mmd` | architecture-beta type coverage |
| `c4-basic.mmd` | c4Context type coverage |

**`tests/test_snapshots.py` structure:**
- Register `--snapshot-capture` via `pytest_addoption` in `tests/conftest.py` (new file — pytest ignores `pytest_addoption` in test modules). Skip the entire suite if `shutil.which("node") is None` or if env var `SNAPSHOT_BASELINE_PLATFORM` is set and does not match `sys.platform` (prevents false-failures on CI platforms that differ from the baseline machine).
- Per-fixture parametrised test: render via `_dispatch`; write to a temp HTML file; call `scripts/html2png.py` via `subprocess` with `--scale 1`; in `--snapshot-capture` mode write PNG to `tests/snapshots/<name>.png`; in regression mode open baseline with Pillow `Image.open`, compute `PIL.ImageChops.difference`, count non-zero pixels, assert ≤ 0.5% of total pixels.

**Done when:** `tests/fixtures/` has ≥ 27 files; `TestFixtureCorpus.test_all_fixtures_dispatch` and `TestFixtureCorpus.test_no_overflow` pass in `tests/test_mermaid_layout.py`; `tests/test_snapshots.py` runs without error in capture mode (baselines deferred to T10).

---

### T10: Baseline capture, full regression pass, and spec close-out

**Depends on:** T1, T2, T3, T4, T5, T6, T7, T8, T9a

**Touches:** `tests/snapshots/*.png` (committed), `tests/test_mermaid_layout.py` (any fixups), `docs/specs/README.md`, `docs/specs/mermaid-renderer-uplift/spec.md`, `docs/specs/mermaid-renderer-uplift/plan.md`

**Tests:**
- `pytest tests/test_mermaid_layout.py` — all ≥ 200 tests pass (AC-17).
- `pytest tests/test_snapshots.py --snapshot-capture` — all baseline PNGs created without error.
- `pytest tests/test_snapshots.py` — all fixtures within 0.5% pixel diff (AC-15).

**Approach:**
1. Run `pytest tests/test_mermaid_layout.py`; fix any failures introduced by Waves 1–2.
2. Manually inspect each fixture HTML in browser for visual correctness before capturing.
3. Run `pytest tests/test_snapshots.py --snapshot-capture`; commit PNG files in `tests/snapshots/`.
4. Run `pytest tests/test_snapshots.py` in regression mode to confirm ≤ 0.5% diff.
5. Set `spec.md` `Status:` → `Shipped` (or `Implementing` if landing in separate PRs).
6. Set `plan.md` `Status:` → `Done`.
7. Update `docs/specs/README.md`: mark `mermaid-renderer-uplift` Status accordingly.

**Done when:** `pytest tests/` passes with zero failures; ≥ 27 baseline PNGs committed; AC-14 through AC-17 all checked.

## Rollout

Pure Python package change — no infrastructure, no feature flags. Ships when `pytest tests/` is fully green and baselines are committed. The downstream consumer picks up changes on the next `_dispatch` call. Rollback is a git revert; no data migration required.

## Risks

- **T1 wrap-threshold change causes layout shifts across all types.** `_wrap_label` is called for every diagram type. Mitigate: run `pytest tests/test_mermaid_layout.py` immediately after T1 and fix all failures before starting T2.
- **`_strategies.py` approaches unmanageable size.** T6–T8 add substantial sequence/ER/class detail to an already 1,250-line file (CONVENTIONS tracked exception). If the file exceeds 1,600 lines after Wave 2, open a follow-on spec to split it.
- **`doublecircle` concentric-ring z-index.** The inner ring must not clip or cover the outer ring. Mitigate: use `position:absolute; inset:5px` on the inner div; ensure the outer div has `position:relative; overflow:visible`.
- **Screenshot baseline cross-machine drift.** Baselines are single-machine-authoritative (pinned puppeteer `25.3.0`, device-scale-factor 1). CI on a different OS or Chrome version will drift past 0.5%. Mitigate: document the baseline machine in `tests/snapshots/README.md` and skip the snapshot suite on machines without `node`.

## Changelog

- 2026-07-17: initial plan
- 2026-07-17: fixed four adversarial-reviewer blockers — `_wrap_label` list return type, icon-budget parameter, AC-7 legend exclusion, AC-14 full type coverage; added concerns — Pillow prerequisite, task serialization, reference-value oracle, AC-16 classification, cross-`<br>` formatting test
- 2026-07-17: second pass — fixed `--capture` flag collision (renamed to `--snapshot-capture`, moved to `conftest.py`); defined `ICON_COL_WIDTH` constant; added render-level icon-budget test; updated T9a `Depends on: T5`; added platform skip guard; clarified pre-legend canvas height in AC-16; added T10 steps to update spec/plan Status fields
- 2026-07-17: third pass — purged all remaining stale `--capture` occurrences; added `tests/conftest.py` to T9a Touches and decomposition table; fixed AC-16 canvas-height source to SVG overlay attribute (not outer wrapper div); updated T10 Touches to include spec.md and plan.md
- 2026-07-17: fourth pass — fixed AC-16 and T9a regex to match actual renderer output (`style="...height:Npx..."` in SVG inline style at `_renderer.py:294`, not a bare `height="N"` attribute which only appears on legend swatch SVGs)
