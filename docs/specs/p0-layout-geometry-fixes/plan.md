# Plan: P0 Layout Geometry Fixes

## Files touched

- `scripts/mermaid_render/layout/_constants.py` — font size constants, NODE_MAX_W,
  _Node.height, dynamic size helpers, _TITLE_FS/_TITLE_FW/_ICON_FS
- `scripts/mermaid_render/layout/_layout.py` — per-column/per-rank width assignment,
  n.height population, icon-aware font measurement in _assign_coordinates
- `scripts/mermaid_render/layout/_routing.py` — _node_render_w/h use n.width/n.height
- `scripts/mermaid_render/layout/_renderer.py` — polygon separation HTML structure
- `tests/test_mermaid_layout.py` — updated circle/diamond size assertions
- `tests/test_syntax_flowchart.py` — updated circle/diamond size assertions
- `tests/test_render_correctness.py` — coordinate-baseline updates for per-column/per-rank

## Not changing

Shim at `scripts/mermaid_layout/` (reads from `mermaid_render`; no change needed).
`_strategies.py` (layout orchestration; P1 concern). Parser, C4, sequence, ER, gantt renderers.

## Declined temptations

- New module for shape-geometry functions (single-use; stays in `_constants.py`).
- `faithful_mermaid` toggle parameter (no second caller yet).
- NODE_MAX_W cap on circle/diamond (their growth formula has natural bound; capping re-introduces clipping).
- Porting the Brandes-Köpf full coordinate-assignment (P1 scope).

---

## Task 1 — Add font constants and fix `_measure_text_px` / `_wrap_label` / icon-aware width

**Verification mode:** TDD
**Depends on:** none

**Tests (red stubs first):**
```python
def test_title_fs_constants_exist():
    from mermaid_render.layout._constants import _TITLE_FS, _TITLE_FW, _ICON_FS
    assert _TITLE_FS == 15
    assert _TITLE_FW == 700
    assert _ICON_FS == 14

def test_measure_text_px_uses_render_font():
    from mermaid_render.layout._constants import _measure_text_px, _measure_text_width
    assert _measure_text_px("Decision") == _measure_text_width("Decision", 15, 700)

def test_wrap_label_uses_render_font():
    from mermaid_render.layout._constants import _wrap_label, _measure_text_width
    label = "Long Label Text That Wraps"
    measured_15_700 = _measure_text_width(label, 15, 700)
    measured_13_500 = _measure_text_width(label, 13, 500)
    # Budget between the two measurements: fits at 13/500 but overflows at 15/700
    budget = int((measured_13_500 + measured_15_700) / 2)
    lines_new = _wrap_label(label, width_budget=budget)
    assert len(lines_new) >= 2, (
        f"label must wrap at 15/700 with budget={budget} "
        f"(13/500={measured_13_500}, 15/700={measured_15_700})"
    )

def test_icon_node_measures_narrower():
    from mermaid_render.layout._constants import _measure_text_width, _ICON_FS, _TITLE_FS
    label = "DatabaseNode"
    w_icon = _measure_text_width(label, _ICON_FS, 700)
    w_normal = _measure_text_width(label, _TITLE_FS, 700)
    assert w_icon < w_normal, "icon font (14px) must measure narrower than normal font (15px)"
```

**Approach:**

In `_constants.py`, add:
```python
_TITLE_FS: int = 15
_TITLE_FW: int = 700
_ICON_FS: int = 14
```

Change `_measure_text_px(text)` body to:
```python
return _measure_text_width(text, _TITLE_FS, _TITLE_FW)
```

Change all `_measure_text_width(..., 13, 500)` in `_wrap_label()` to
`_measure_text_width(..., _TITLE_FS, _TITLE_FW)`.

In `_layout.py` `_assign_coordinates()` (around line 255–268), in the per-node width loop,
add icon-awareness to the measurement call:
```python
_has_icon = bool(
    (n.icon and _load_icon(n.icon)) or (n.css_class and _load_icon(n.css_class))
)
_icon_extra = ICON_COL_WIDTH if _has_icon else 0
_fs = _ICON_FS if _has_icon else _TITLE_FS
# First-line title width (same stripping _measure_text_px does internally):
_title_line = n.label.split("|")[0].split("\n")[0].strip()
_label_w = _measure_text_width(_title_line, _fs, _TITLE_FW)
if "|" in n.label:
    _members = n.label.split("|", 1)[1].replace("---", "").split("\n")
    for _ml in _members:
        _ml = _ml.strip()
        if _ml:
            _label_w = max(_label_w, _measure_text_width(_ml, _fs, _TITLE_FW))
n.width = max(NODE_MIN_W, _label_w + NODE_HPAD + _icon_extra)
```

(Also import `_ICON_FS`, `_TITLE_FS`, `_TITLE_FW` from `_constants` in `_layout.py`'s import block.)

**Done when:** `_measure_text_px("Decision") == _measure_text_width("Decision", 15, 700)`.

---

## Task 2 — Add NODE_MAX_W and clamp text-box node width

**Verification mode:** TDD
**Depends on:** Task 1

**Tests:**
```python
def test_node_max_w_constant_exists():
    from mermaid_render.layout._constants import NODE_MAX_W
    assert NODE_MAX_W == 220

def test_long_label_capped_at_node_max_w():
    from mermaid_render.layout._constants import _Node, NODE_MAX_W
    from mermaid_render.layout._layout import _assign_coordinates
    nodes = {"A": _Node(id="A", label="A" * 100, shape="rect")}
    _assign_coordinates(nodes)
    assert nodes["A"].width <= NODE_MAX_W
```

**Approach:**
- Add `NODE_MAX_W = 220` after `NODE_MIN_W` in `_constants.py`.
- In `_assign_coordinates()`, after computing width for text-box shapes, apply the cap:
  ```python
  n.width = min(max(NODE_MIN_W, _label_w + NODE_HPAD + _icon_extra), NODE_MAX_W)
  ```
  The guard `n.shape not in _fixed_shapes` already skips circle/diamond/hexagon
  (see `_fixed_shapes = {"circle", "diamond", "hexagon"}` at `_layout.py:253`).

**Done when:** `_Node(label="A"*100, shape="rect")` → `n.width ≤ 220`.

---

## Task 3 — Add `height` to `_Node` and populate after layout

**Verification mode:** TDD
**Depends on:** Tasks 1, 2

**Tests:**
```python
def test_node_height_field_exists():
    from mermaid_render.layout._constants import _Node
    n = _Node(id="X", label="X")
    assert hasattr(n, "height") and n.height == 0

def test_assign_coordinates_populates_height():
    from mermaid_render.layout._constants import _Node
    from mermaid_render.layout._layout import _assign_coordinates
    nodes = {"A": _Node(id="A", label="Hello"), "B": _Node(id="B", label="World")}
    _assign_coordinates(nodes)
    assert nodes["A"].height > 0
    assert nodes["B"].height > 0

def test_dummy_node_height_stays_zero():
    from mermaid_render.layout._constants import _Node
    from mermaid_render.layout._layout import _assign_coordinates
    nodes = {"D": _Node(id="D", label="", is_dummy=True)}
    _assign_coordinates(nodes)
    assert nodes["D"].height == 0
```

**Approach:**
- Add `height: int = 0` field to `_Node` dataclass in `_constants.py` (after `width`).
- In `_assign_coordinates()`, after the full width-computation loop (after line 268),
  add a height pass:
  ```python
  for n in nodes.values():
      if not n.is_dummy:
          n.height = _node_render_h(n)
  ```
  This runs AFTER widths are set.

**Done when:** Non-dummy nodes have `n.height > 0` after `_assign_coordinates()`.

---

## Task 4 — Dynamic circle, diamond, and hexagon sizing

**Verification mode:** TDD
**Depends on:** Task 3

**Tests:**
```python
def test_circle_short_label_stays_min_size():
    """Non-terminal circle with 3-char label renders at exactly _CIRCLE_NODE_SIZE."""
    from mermaid_render.layout._constants import _CIRCLE_NODE_SIZE
    from mermaid_render.layout._strategies import _dispatch
    import re
    html = _dispatch("flowchart TB\n  A((Cat))", None, 400)
    m = re.search(r'class="node node-circle[^"]*"[^>]*style="([^"]*)"', html)
    assert m, "node-circle div not found"
    style = m.group(1)
    w_m = re.search(r'width:(\d+)px', style)
    assert w_m, "width not found in node-circle style"
    assert int(w_m.group(1)) == _CIRCLE_NODE_SIZE

def test_circle_long_label_grows():
    from mermaid_render.layout._constants import _CIRCLE_NODE_SIZE
    from mermaid_render.layout._strategies import _dispatch
    import re
    html = _dispatch("flowchart TB\n  A((A Very Long Circle Label That Needs Space))", None, 600)
    m = re.search(r'class="node node-circle[^"]*"[^>]*style="([^"]*)"', html)
    assert m, "node-circle div not found"
    style = m.group(1)
    w_m = re.search(r'width:(\d+)px', style)
    assert w_m, "width not found in node-circle style"
    w = int(w_m.group(1))
    assert w > _CIRCLE_NODE_SIZE, f"long-label circle must grow beyond {_CIRCLE_NODE_SIZE}px, got {w}"

def test_circle_not_capped_by_node_max_w():
    """Circle with very long label exceeds NODE_MAX_W — the cap does not apply."""
    from mermaid_render.layout._constants import _Node, NODE_MAX_W
    from mermaid_render.layout._layout import _assign_coordinates
    nodes = {"C": _Node(id="C", label="A Very Long Circle Label That Definitely Grows", shape="circle")}
    _assign_coordinates(nodes)
    # hypot(~420, ~42) ≈ 422px — well above NODE_MAX_W=220
    assert nodes["C"].width > NODE_MAX_W, (
        f"circle must not be capped at NODE_MAX_W={NODE_MAX_W}; got {nodes['C'].width}"
    )

def test_hexagon_not_capped_by_node_max_w():
    """Hexagon with very long label exceeds NODE_MAX_W — the cap does not apply."""
    from mermaid_render.layout._constants import _Node, NODE_MAX_W
    from mermaid_render.layout._layout import _assign_coordinates
    nodes = {"H": _Node(id="H", label="A Very Long Hexagon Label That Definitely Grows Beyond Two Twenty", shape="hexagon")}
    _assign_coordinates(nodes)
    assert nodes["H"].width > NODE_MAX_W, (
        f"hexagon must not be capped at NODE_MAX_W={NODE_MAX_W}; got {nodes['H'].width}"
    )

def test_diamond_short_label_at_floor():
    """Short-label diamond is exactly _DIAMOND_SIZE (the floor)."""
    from mermaid_render.layout._constants import _DIAMOND_SIZE
    from mermaid_render.layout._strategies import _dispatch
    import re
    html = _dispatch("flowchart TB\n  A{Go}", None, 400)
    m = re.search(r'class="node node-diamond[^"]*"[^>]*style="([^"]*)"', html)
    assert m, "node-diamond div not found"
    style = m.group(1)
    w_m = re.search(r'width:(\d+)px', style)
    assert w_m, "width not in diamond style"
    assert int(w_m.group(1)) == _DIAMOND_SIZE, (
        "short-label diamond must be exactly _DIAMOND_SIZE (max formula floors to base_size)"
    )

def test_diamond_long_label_grows():
    from mermaid_render.layout._constants import _DIAMOND_SIZE
    from mermaid_render.layout._strategies import _dispatch
    import re
    html = _dispatch("flowchart TB\n  A{A Very Long Decision Label That Cannot Fit In Hundred Pixels}", None, 700)
    m = re.search(r'class="node node-diamond[^"]*"[^>]*style="([^"]*)"', html)
    assert m, "node-diamond div not found"
    style = m.group(1)
    w_m = re.search(r'width:(\d+)px', style)
    assert w_m, "width not in diamond style"
    assert int(w_m.group(1)) > _DIAMOND_SIZE, f"long-label diamond must grow beyond {_DIAMOND_SIZE}px"

def test_hexagon_long_label_grows():
    from mermaid_render.layout._constants import _HEXAGON_SIZE
    from mermaid_render.layout._strategies import _dispatch
    import re
    html = _dispatch("flowchart TB\n  A{{A Very Long Hexagon Label That Needs More Space}}", None, 700)
    m = re.search(r'class="node node-hexagon[^"]*"[^>]*style="([^"]*)"', html)
    assert m, "node-hexagon div not found"
    style = m.group(1)
    w_m = re.search(r'width:(\d+)px', style)
    assert w_m, "width not in hexagon style"
    assert int(w_m.group(1)) > _HEXAGON_SIZE, f"long-label hexagon must grow beyond {_HEXAGON_SIZE}px"
```

**Existing `test_syntax_flowchart.py` test updates (enumerate and fix these four):**
- Line ~424: `width:80px; height:80px` for "My Circle Node" → regex-extract int, assert `w == h` and `w >= _CIRCLE_NODE_SIZE`
- Line ~433: `width:80px` for circle check → `w >= _CIRCLE_NODE_SIZE`
- Line ~459: `width:100px` for "Decision" diamond → regex-extract, assert `w >= _DIAMOND_SIZE`
- Line ~466: SVG `width="100"` for diamond border → regex-extract int, assert `>= _DIAMOND_SIZE`

**Approach (in `_constants.py`):**

Add `import math` if not already present. Add helpers:
```python
def _node_size_circle(n: "_Node") -> int:
    if _is_terminal_circle(n):
        return _TERMINAL_NODE_SIZE
    label = n.label.split("|")[0].split("\n")[0].strip()
    content_w = _measure_text_width(label, _TITLE_FS, _TITLE_FW)
    content_h = _TITLE_LINE_H
    return max(_CIRCLE_NODE_SIZE, math.ceil(math.hypot(content_w + NODE_HPAD, content_h + NODE_HPAD)))

def _node_size_diamond_hex(n: "_Node", base_size: int) -> int:
    """Linear content-sum formula (not hypot) for diamond/hexagon growth."""
    label = n.label.split("|")[0].split("\n")[0].strip()
    content_w = _measure_text_width(label, _TITLE_FS, _TITLE_FW)
    content_h = _TITLE_LINE_H
    return max(base_size, math.ceil(content_w + content_h + NODE_HPAD))
```

In `_assign_coordinates()`, handle fixed shapes before the text-box width loop:
```python
_fixed_shapes = {"circle", "diamond", "hexagon"}
for n in nodes.values():
    if n.width == 0 and not n.is_dummy:
        if n.shape in ("circle", "doublecircle"):
            n.width = _node_size_circle(n)
        elif n.shape == "diamond":
            n.width = _node_size_diamond_hex(n, _DIAMOND_SIZE)
        elif n.shape == "hexagon":
            n.width = _node_size_diamond_hex(n, _HEXAGON_SIZE)
        else:
            # text-box shapes: existing formula
            ...
```

In `_node_render_h()`:
```python
if n.shape in ("circle", "doublecircle"):
    return n.width if n.width > 0 else _CIRCLE_NODE_SIZE
if n.shape in ("diamond", "hexagon"):
    return n.width if n.width > 0 else _DIAMOND_SIZE
```

In `_routing.py` `_node_render_w()`:
```python
if n.shape in ("circle", "doublecircle"):
    return n.width if n.width > 0 else _CIRCLE_NODE_SIZE
if n.shape in ("diamond", "hexagon"):
    return n.width if n.width > 0 else _DIAMOND_SIZE
```

In `_renderer.py`, update rendering to use `n.width` with constant fallback:
- Circle: `width:{n.width or _CIRCLE_NODE_SIZE}px; height:{n.width or _CIRCLE_NODE_SIZE}px`
- Diamond: `width:{n.width or _DIAMOND_SIZE}px`
- Diamond/Hexagon SVG border: `n.width or _DIAMOND_SIZE` / `n.width or _HEXAGON_SIZE`

**Done when:** Short "Go" diamond == 100, long diamond > 100, long circle > 80, long hexagon > 100.

---

## Task 5 — Polygon clip-path separation (all five polygon shapes)

**Verification mode:** Structural HTML check (visual un-clipping out of scope per spec Assumption 4)
**Depends on:** Task 4

**Tests:**
```python
import pytest

@pytest.mark.parametrize("shape_mermaid,css_class", [
    ("A{Decision}", "node-diamond"),
    ("A{{Hex Node}}", "node-hexagon"),
    ("A[/Trapezoid/]", "node-trapezoid"),
    ("A[\\\\Trapezoid Alt\\\\]", "node-trapezoid-alt"),
    ("A>Flag Node]", "node-flag"),
])
def test_polygon_clip_path_on_background_not_outer(shape_mermaid, css_class):
    from mermaid_render.layout._strategies import _dispatch
    import re
    html = _dispatch(f"flowchart TB\n  {shape_mermaid}", None, 400)
    assert "clip-path:polygon" in html, f"clip-path must exist in HTML for {css_class}"
    pattern = rf'class="node {re.escape(css_class)}[^"]*"[^>]*style="([^"]*)"'
    m = re.search(pattern, html)
    assert m, f"outer container div for {css_class} not found in HTML"
    outer_style = m.group(1)
    assert "clip-path" not in outer_style, (
        f"clip-path must not be on outer container for {css_class}; "
        f"found in: {outer_style!r}"
    )
    assert "overflow:hidden" not in outer_style, (
        f"overflow:hidden must not be on outer container for {css_class}"
    )

def test_polygon_clip_path_present_in_html():
    from mermaid_render.layout._strategies import _dispatch
    html = _dispatch("flowchart TB\n  A{{Hex}}", None, 400)
    assert "clip-path:polygon" in html
```

**Approach (in `_renderer.py`):**

For shapes in the `_uses_clip` set (diamond, hexagon, trapezoid, trapezoid-alt, flag):

Before (simplified):
```html
<div class="node node-{shape}" style="...clip-path:polygon(...); overflow:hidden; ...">
  {inner_html}  {_shape_border_svg}
</div>
```

After:
```html
<div class="node node-{shape}" style="position:absolute; left:X; top:Y; width:W; height:H; overflow:visible;">
  <div style="position:absolute; inset:0; clip-path:polygon(...); {background_css};"></div>
  <div style="position:absolute; inset:0; padding:{pad}; display:flex; flex-direction:column;
              align-items:{align}; justify-content:center; overflow:visible;">
    {inner_html}
  </div>
  {_shape_border_svg}
</div>
```

The `clip-path` and background gradient move to the background div.
The text container uses `overflow:visible`. Non-clip shapes (rect, round, stadium,
subroutine, cylinder, circle, doublecircle) unchanged.

**Done when:** All five parametrized `test_polygon_clip_path_on_background_not_outer` cases pass.

---

## Task 6 — Per-column (TB) and per-rank (LR) width assignment

**Verification mode:** TDD
**Depends on:** Tasks 1, 2, 3

**Tests:**
```python
def test_tb_per_column_narrow_node_x():
    """Narrow column node's x uses its own column width, not the global max."""
    from mermaid_render.layout._constants import _Node, _Edge, CANVAS_PAD, COL_GAP
    from mermaid_render.layout._layout import (
        _assign_coordinates, _assign_ranks, _minimize_crossings, _break_cycles
    )
    nodes = {
        "Wide": _Node(id="Wide", label="W" * 25, shape="rect"),
        "Narrow": _Node(id="Narrow", label="N", shape="rect"),
        "Sink": _Node(id="Sink", label="S", shape="rect"),
    }
    edges = [_Edge(src="Wide", dst="Sink"), _Edge(src="Narrow", dst="Sink")]
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _minimize_crossings(nodes, edges)
    _assign_coordinates(nodes, direction="TB")

    w_wide = nodes["Wide"].width
    w_narrow = nodes["Narrow"].width
    assert w_wide > w_narrow, "precondition: Wide must be wider"

    n_wide = nodes["Wide"]
    n_narrow = nodes["Narrow"]
    assert n_wide.col != n_narrow.col, (
        "precondition: Wide and Narrow must be in different columns"
    )

    # Determine which node is in the left column (col with smaller index)
    if n_wide.col < n_narrow.col:
        left_w, right_w = w_wide, w_narrow
        right_node = n_narrow
    else:
        left_w, right_w = w_narrow, w_wide
        right_node = n_wide

    # Per-column: right_node.x = CANVAS_PAD + left_w + COL_GAP
    # (right node is centered in its own slot width, which equals right_w, so offset=0)
    # Global-max: right_node.x = CANVAS_PAD + (max(left_w,right_w) + COL_GAP) + (max - right_w)//2
    expected_per_col = CANVAS_PAD + left_w + COL_GAP
    assert right_node.x == expected_per_col, (
        f"right node x={right_node.x} expected {expected_per_col} (per-column); "
        f"global-max would give {CANVAS_PAD + max(left_w,right_w) + COL_GAP + (max(left_w,right_w)-right_w)//2}"
    )

def test_lr_per_rank_wide_node_x():
    """LR: narrow rank 0 -> wide rank 1; wide node x uses narrow rank's width."""
    from mermaid_render.layout._constants import _Node, _Edge, CANVAS_PAD, RANK_GAP
    from mermaid_render.layout._layout import _assign_coordinates, _assign_ranks, _break_cycles
    nodes = {
        "A": _Node(id="A", label="N"),           # narrow, rank 0
        "B": _Node(id="B", label="W" * 20),      # wide, rank 1
    }
    edges = [_Edge(src="A", dst="B")]
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)
    _assign_coordinates(nodes, direction="LR")

    w_a = nodes["A"].width
    w_b = nodes["B"].width
    assert w_b > w_a, "precondition: B must be wider than A"

    # Per-rank: B.x = CANVAS_PAD + w_a + RANK_GAP  (rank 0 slot = w_a)
    # Global-max: B.x = CANVAS_PAD + max(w_a, w_b) + RANK_GAP = CANVAS_PAD + w_b + RANK_GAP
    expected_per_rank = CANVAS_PAD + w_a + RANK_GAP
    assert nodes["B"].x == expected_per_rank, (
        f"B.x={nodes['B'].x} expected {expected_per_rank} (per-rank); "
        f"global-max would give {CANVAS_PAD + w_b + RANK_GAP}"
    )

def test_dummy_node_x_in_per_column_layout():
    """Dummy node x is >= CANVAS_PAD (within canvas) after per-column assignment."""
    from mermaid_render.layout._constants import _Node, _Edge, CANVAS_PAD
    from mermaid_render.layout._layout import (
        _assign_coordinates, _assign_ranks, _minimize_crossings, _break_cycles
    )
    # A->B->C chain plus skip edge A->C forces a rank-spanning dummy (A rank 0, C rank 2)
    nodes = {
        "A": _Node(id="A", label="A" * 15, shape="rect"),
        "B": _Node(id="B", label="B", shape="rect"),
        "C": _Node(id="C", label="C", shape="rect"),
    }
    edges = [_Edge(src="A", dst="B"), _Edge(src="B", dst="C"), _Edge(src="A", dst="C")]
    _break_cycles(nodes, edges)
    _assign_ranks(nodes, edges)  # inserts dummy nodes for A->C span (rank 0->2)
    _minimize_crossings(nodes, edges)
    _assign_coordinates(nodes, direction="TB")

    dummy_nodes = [n for n in nodes.values() if n.is_dummy]
    assert len(dummy_nodes) > 0, (
        "A->C spanning ranks 0->2 must produce at least one dummy node"
    )
    for dummy in dummy_nodes:
        assert dummy.x >= CANVAS_PAD, f"dummy.x={dummy.x} is left of CANVAS_PAD"
```

**Approach (in `_layout.py`):**

TB layout — replace global `_layout_nw` / `col_pitch` (lines 269–285):
```python
all_cols = sorted({n.col for n in nodes.values()})
col_width: dict[int, int] = {
    c: max(
        (n.width for n in nodes.values() if n.col == c and not n.is_dummy and n.width > 0),
        default=NODE_W,
    )
    for c in all_cols
}
col_left: dict[int, int] = {}
cursor = CANVAS_PAD
for c in all_cols:
    col_left[c] = cursor
    cursor += col_width[c] + _col_gap

for n in nodes.values():
    cw = col_width.get(n.col, NODE_W)
    nw = n.width or cw  # dummy: width=0 -> nw=cw -> centering_offset=0 -> x=col_left[n.col]
    n.x = col_left[n.col] + (cw - nw) // 2

canvas_w = cursor - _col_gap + CANVAS_PAD
```

The existing "pull dummy nodes tightly" block (lines 286–298) also references `_layout_nw`
and `col_pitch` — replace those references with `col_left`/`col_width` lookups.

LR layout — replace `rank_pitch`:
```python
all_ranks = sorted({n.rank for n in nodes.values()})
rank_width: dict[int, int] = {
    r: max(
        (n.width for n in nodes.values() if n.rank == r and not n.is_dummy and n.width > 0),
        default=NODE_W,
    )
    for r in all_ranks
}
rank_left: dict[int, int] = {}
cursor = CANVAS_PAD
for r in all_ranks:
    rank_left[r] = cursor
    cursor += rank_width[r] + _rank_gap

for n in nodes.values():
    n.x = rank_left.get(n.rank, CANVAS_PAD)

canvas_w = cursor - _rank_gap + CANVAS_PAD
```

Update `test_render_correctness.py` coordinate baselines for diagrams where
column/rank x-positions shift due to per-column sizing. These are snapshot-style
assertions; update them to match the new correct geometry.

**Done when:** Both width-discriminating tests pass; dummy x stays inside canvas.

---

## Rollout

No deployment; local Python renderer only.
Gate sequence: `python -m pytest tests/test_mermaid_layout.py tests/test_syntax_flowchart.py tests/test_render_correctness.py -x -q`
