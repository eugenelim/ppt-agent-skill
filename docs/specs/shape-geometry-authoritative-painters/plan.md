# Implementation Plan — shape-geometry-authoritative-painters

## Pre-mortem

**Assumption trio:**
1. Files I'll touch:
   - `scripts/mermaid_render/layout/shape_geometry.py` — implement `paint_html()` + `paint_svg()` on all 13 geometry classes
   - `scripts/mermaid_render/layout/_renderer.py` — replace per-shape branches in `_render_graph_fragment()` and `render_finalized()` with `SHAPE_REGISTRY[shape].paint_html()` calls
   - `scripts/mermaid_render/paint.py` — replace per-shape branches in `_node_scene_elements()` with `SHAPE_REGISTRY[shape].paint_svg()` calls
   - `tests/test_shape_geometry_rays.py` — add parity tests, ring-semantics tests, flag/subroutine/cylinder painter tests
2. Done when: `pytest tests/` passes; `flowchart-all-shapes` and `flowchart-diamond-clipping` render without visual regression; `_render_graph_fragment`, `render_finalized`, and `_node_scene_elements` no longer contain per-shape painting branches.
3. Not changing: `_constants.py` size functions, `_layout.py` size assignment, `_routing.py`, `ShapeGeometry` protocol method signatures, ELK adapter, non-flowchart diagram renderers.

**Declined patterns:**
- Tempted to unify `_node_size_*` helper functions into `ShapeGeometry.measure()` — that touches `_layout.py` and is out of scope.
- Tempted to change `paint_svg()` to return typed scene objects instead of an SVG string — the existing protocol signature returns `Optional[str]`; changing it would break the Protocol and all existing callers. Raw SVG fragment + a `SceneRaw` wrapper (or direct string embed in paint.py) is preferred.
- Tempted to use kwargs-as-CSS-vars inside the geometry classes (e.g. `kw["accent"]` defaults to `var(--accent-1)`); instead, callers pass resolved color strings so the geometry class has no CSS-variable dependency.
- Tempted to change `CylinderGeometry.outline_path()` to an actual silo silhouette path — keeping it as a rect bounding box is correct (connectors attach to the outer rect); the cap fix is in `measure()` / painter, not `outline_path()`.

---

## Tasks

### Task 1: Implement paint_html() for rect-family shapes
Depends on: none
Verification: TDD

**Shapes:** `rect`, `round`, `stadium`

**Tests (write first):**
- `test_paint_html_not_none[rect]`, `[round]`, `[stadium]`
- Assert returned string contains `class="node node-{shape}"`
- Assert returned string contains the `inner_html` kwarg value

**Approach:**
- In `shape_geometry.py`, implement `RectGeometry.paint_html()`, `RoundGeometry.paint_html()`,
  and `StadiumGeometry.paint_html()`.
- Each method builds the same outer div that `_render_graph_fragment()` currently builds for that
  shape. Consume kwargs: `x`, `y`, `w`, `h`, `inner_html`, `border_css`, `shape_css`, `bg_css`,
  `box_shadow`, `data_attrs_html` (pre-rendered `data-node-id="..." ...` string), `extra_cls`.
- Border CSS: rect/round/stadium all use `border:1.5px solid {border_var}; border-top:3px solid {accent};`.
  Stadium adds full-perimeter accent border instead of top-only. Callers pass the resolved string.
- The returned HTML is the complete outer `<div>...</div>` including `{inner_html}`.
- `paint_svg()` on these three shapes: return a `<rect rx="{rx}" .../>` SVG fragment; rect rx=8,
  round rx=14, stadium rx=50.

---

### Task 2: Implement paint_html() for polygon shapes
Depends on: none
Verification: TDD

**Shapes:** `diamond`, `hexagon`, `trapezoid`, `trapezoid-alt`, `flag`

**Tests (write first):**
- `test_paint_html_not_none[diamond]` etc.
- `test_no_rect_border_on_polygon_nodes` (existing test) passes for all 5 shapes — no regression.
- For flag: assert HTML contains a `<polygon>` with exactly 5 coordinate pairs (not a rect).
- `test_painter_vertex_parity` — parse `polygon points="..."` from `paint_html()` SVG overlay;
  compare to `outline_path(w, h)` scaled vertices; all points within 1 px.

**Approach:**
- In `shape_geometry.py`, implement `paint_html()` on `DiamondGeometry`, `HexagonGeometry`,
  `TrapezoidGeometry`, `TrapezoidAltGeometry`, `FlagGeometry`.
- All five use the clip-path background div + SVG polygon border pattern currently in
  `_renderer.py`. The critical change: derive polygon vertex strings from `outline_path(w, h)`
  rather than inline percentage arithmetic. Helpers:
  ```python
  def _verts_to_points(verts, x_off=0, y_off=0):
      return " ".join(f"{x + x_off:.1f},{y + y_off:.1f}" for x, y in verts)

  def _verts_to_clip_path(verts, w, h):
      return "polygon(" + ",".join(f"{100*x/w:.1f}% {100*y/h:.1f}%" for x, y in verts) + ")"
  ```
  Add these as module-level helpers in `shape_geometry.py`.
- Outer container: `position:absolute; left:{x}px; top:{y}px; width:{w}px; min-height:{h}px;
  box-sizing:border-box; overflow:visible; {border_css} {shape_css}` (no `border:` on outer for
  polygon shapes — callers pass `border_css=""` for these shapes).
- Background div (clip-path fill): `clip-path:{clip}; position:absolute; inset:0; {bg_css}; box-shadow:{box_shadow}`.
- SVG polygon overlay: `<svg ...><polygon points="{pts}" fill="none" stroke="{accent}" stroke-width="2"/></svg>`.
- Text div (unclipped): `position:absolute; inset:0; padding:...; display:flex; ...`.
- `paint_svg()` on these shapes: `<polygon points="{pts_with_x_y_offset}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>`.

---

### Task 3: Implement paint_html() for specialty shapes
Depends on: none
Verification: TDD

**Shapes:** `circle`, `doublecircle`, `cylinder`, `subroutine`, `bar`

**Tests (write first):**
- `test_paint_html_not_none[circle]` etc.
- `test_doublecircle_ring_semantics` — HTML output contains outer ring div + inner ring div
  with `border-radius:50%; border:2px solid ...`; no `background:` disc div.
- `test_subroutine_svg_vertical_rules` — HTML contains `<line x1="8"` and `<line x1="{nw-8}"`.

**Approach:**
- `CircleGeometry.paint_html()`: outer div `border-radius:50%`; single border-color accent ring.
- `DoubleCircleGeometry.paint_html()`: outer div `border-radius:50%; border:2px solid {accent}`;
  inner div `position:absolute; inset:5px; border-radius:50%; border:2px solid {accent};
  pointer-events:none` — no `background:` fill on inner div. This replaces the filled-disc
  rendering (which is now reserved for `_is_terminal_doublecircle` in the caller). Passes
  `inner_html` label into the outer div.
- `CylinderGeometry.paint_html()`: outer div `border:none`; inline SVG overlay with two side
  `<line>` elements, filled top ellipse (covers rect edge), outlined bottom ellipse. Padding
  accounts for cap height via `(12 + cap_ry)px 12px 12px 12px`.
- `SubroutineGeometry.paint_html()`: outer div `{border_css} {shape_css}`; inner SVG with two
  `<line>` elements at x=8 and x=nw-8, spanning y=2 to y=nh-2.
- `BarGeometry.paint_html()`: outer wrapper div; inner solid rect `background:var(--node-fg,...);
  border-radius:2px`; label span below bar.
- For all five: `paint_svg()` is covered in Task 4.

---

### Task 4: Implement paint_svg() for all 13 shapes
Depends on: none (parallel with Tasks 1–3)
Verification: TDD

**Tests (write first):**
- `test_paint_svg_not_none` parametrized over all 13 shapes.
- `test_flag_svg_polygon_5_vertices` — paint_svg() for flag contains one `<polygon>` with 5 pairs.
- `test_subroutine_svg_vertical_rules` — paint_svg() for subroutine contains two `<line>` elements.
- `test_doublecircle_ring_semantics` (SVG side) — two `<circle>` elements; inner `fill="none"`.
- `test_painter_vertex_parity` — polygon points in `paint_svg()` match `outline_path()` scaled verts.

**Approach:**
- `paint_svg()` returns a raw SVG fragment string (not scene objects). The caller in `paint.py`
  will embed it. kwargs consumed: `x`, `y`, `w`, `h`, `fill`, `stroke`, `stroke_w`,
  `data_attrs_svg` (pre-rendered `data-node-id="..."` string for the group element).
- Rect-family (`rect`, `round`, `stadium`): `<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" .../>`.
- Polygon shapes (`diamond`, `hexagon`, `trapezoid`, `trapezoid-alt`):
  Derive `pts` from `outline_path(w, h)`, offset by `(x, y)` with `_verts_to_points()`.
  Return `<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>`.
- `flag`: same pattern — 5-vertex polygon from `FlagGeometry.outline_path(w, h)`.
  **Bug fix:** current `paint.py` treats flag as a `SceneRoundedRect` (rectangle); replace with
  the correct polygon.
- `circle`: `<circle cx="{cx}" cy="{cy}" r="{r}" .../>`.
- `doublecircle`: outer `<circle r="{r_outer}" .../>` + inner `<circle r="{r_inner}" fill="none" .../>`.
  **Bug fix:** no filled inner disc in normal rendering.
- `cylinder`: `<rect>` body + bottom `<ellipse fill="none">` + top `<ellipse>` filled. Use existing
  scene logic from `paint.py` as reference; ensure cap height `cap_ry = max(8.0, h * 0.12)`.
  **Note on bounds:** `outline_path()` remains the rectangular bounding silhouette (correct for
  connectors); the rendered cylinder paints caps within that bounding box.
- `subroutine`: outer `<rect rx="4" .../>` + two `<line>` elements at x=x+8 and x=x+w-8.
  **Bug fix:** `paint.py` currently emits only a `SceneRoundedRect` (no inner lines) for subroutine.
- `bar`: single `<rect>` with no stroke and `fill="{text_fill}"`.

---

### Task 5: Wire _render_graph_fragment() to SHAPE_REGISTRY
Depends on: Tasks 1, 2, 3
Verification: run existing `pytest tests/`; no regressions

**Approach:**
- In `_renderer.py`, import `SHAPE_REGISTRY` from `.shape_geometry`.
- Build the context kwargs dict once per node before the shape dispatch:
  ```python
  _paint_kw = dict(
      inner_html=inner,
      border_css=_border_css,
      shape_css=shape_css,
      bg_css=_bg_css,
      box_shadow=_shadow,
      data_attrs_html=f'{_node_data_attrs(nid, n)} class="node node-{_h(n.shape)}{extra_cls}"',
      accent=accent_color,
      depth_wash=_depth_wash,
      nw=_nw,
      node_h=node_h,
  )
  ```
- Replace the large `if n.shape == "diamond": ... elif n.shape == "hexagon": ... else:` block with:
  ```python
  _geom = SHAPE_REGISTRY.get(n.shape)
  if _geom is not None:
      _html = _geom.paint_html(n.x, n.y, _nw, node_h, **_paint_kw)
  if _html is not None:
      parts.append(_html)
  else:
      # fallback: plain card (should not be reached after full implementation)
      parts.append(_render_plain_card(n, _paint_kw))
  ```
- Keep the `_is_terminal_doublecircle` / `_is_terminal_circle` guards above this block; those are
  semantic overrides, not shape painters, and remain as is.
- Remove `_NODE_CSS`, `_CLIP_PATH_CSS` from the module if no longer referenced by callers
  (keep if any other call site imports them — check with grep).

---

### Task 6: Wire render_finalized() to SHAPE_REGISTRY
Depends on: Tasks 1, 2, 3
Verification: run existing `pytest tests/`; no regressions

**Approach:**
- Same pattern as Task 5, applied to `render_finalized()` starting at line ~1717
  (`shape_overlay = ""` block through the closing `parts.append(...)`).
- Build `_paint_kw` from `nl.*` fields (FinalizedLayout node layout) rather than `n.*` (_Node).
- Replace the `if shape == "diamond":` / `elif shape == "hexagon":` / `elif shape in (...):`
  shape-overlay block and the special-case render blocks with a single
  `SHAPE_REGISTRY.get(shape).paint_html(...)` call.
- The `nid.endswith("_sm_start_") and shape == "circle"` UML-initial-state guard remains above
  the SHAPE_REGISTRY call.

---

### Task 7: Wire paint.py to SHAPE_REGISTRY
Depends on: Task 4
Verification: run existing `pytest tests/`; no regressions

**Approach:**
- In `paint.py`, import `SHAPE_REGISTRY` from `.layout.shape_geometry`.
- In `_node_scene_elements()`, replace the `if shape in ("rect", "round", ...) ... elif shape == "cylinder": ...`
  block (lines ~199–327) with:
  ```python
  _geom = SHAPE_REGISTRY.get(shape)
  svg_frag = _geom.paint_svg(x, y, nw, nh,
      fill=paint.fill.color,
      stroke=paint.stroke.color,
      stroke_w=paint.stroke.width,
      data_attrs_svg=...,
  ) if _geom is not None else None
  if svg_frag is not None:
      elements.append(SceneRaw(
          element_id=eid,
          svg=svg_frag,
          css_classes=("node", f"node-{shape}"),
          data_attrs=_node_data,
      ))
  ```
- If `SceneRaw` does not exist in `scene.py`, add it as a thin `@dataclass` with `element_id`,
  `svg`, `css_classes`, `data_attrs` fields and a `to_svg()` method that returns `self.svg`.
  The serializer in `scene.py` must be updated to call `to_svg()` for `SceneRaw` instances.
- Keep the label text block (lines ~329–353) unchanged — it always appends after shape elements.

---

### Task 8: Add painter parity and regression tests
Depends on: Tasks 5, 6, 7
Verification: `pytest tests/test_shape_geometry_rays.py -v` — all pass

**Tests to add in `tests/test_shape_geometry_rays.py`:**

```python
# AC-1 / AC-2: painter completeness
@pytest.mark.parametrize("shape", list(SHAPE_REGISTRY.keys()))
def test_paint_svg_not_none(shape): ...

@pytest.mark.parametrize("shape", list(SHAPE_REGISTRY.keys()))
def test_paint_html_not_none(shape): ...

# AC-7: vertex parity between HTML and SVG painters
@pytest.mark.parametrize("shape", ["diamond","hexagon","trapezoid","trapezoid-alt","flag"])
def test_painter_vertex_parity(shape): ...
# parse <polygon points="..."> from paint_svg(); compare to outline_path() verts offset by (0,0)

# AC-11: flag is a 5-vertex polygon in SVG
def test_flag_svg_polygon_5_vertices(): ...

# AC-12: subroutine SVG has two inner vertical rules
def test_subroutine_svg_vertical_rules(): ...

# AC-13: doublecircle is two stroked rings
def test_doublecircle_ring_semantics_svg(): ...
def test_doublecircle_ring_semantics_html(): ...

# AC-16: 8-angle ray tests — already in file; confirm they still pass (no new tests needed)
```

**Approach:**
- All new tests call `SHAPE_REGISTRY[shape].paint_svg(0, 0, 100, 60, fill="#eee", stroke="#333", stroke_w=1.5)`
  and `paint_html(0, 0, 100, 60, inner_html="", border_css="", shape_css="", bg_css="",
  box_shadow="", data_attrs_html='data-node-id="n1"', accent="#60a5fa", depth_wash="rgba(0,0,0,0)",
  nw=100, node_h=60)`.
- Vertex parity test: extract first `polygon points="..."` from SVG output with regex; split into
  `(float, float)` pairs; compare against `outline_path(100, 60)` with x/y offset applied; all
  distances < 1 px.
- No screenshot or browser required.
