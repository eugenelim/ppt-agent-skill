# Standalone: Mermaid renderer visual QA — follow-up session

## Context

This repo is `ppt-agent-skill` (`scripts/mermaid_layout/`). The renderer converts
Mermaid `.mmd` source to deterministic HTML/CSS which is screenshotted via Puppeteer
(`scripts/html2png.py`). All 33 fixture PNGs live in `tests/snapshots/light/`.

Previous sessions fixed: T3 dark fallback colours, diamond square aspect ratio,
architecture edge port prefix, mindmap L-connectors, timeline multi-period collapse,
kanban `id["label"]` stripping, pie height cap, quadrant-4 label position, gantt bar
fill (white-on-white → visible teal), block-beta missing arrows, packet quoted labels.

**Branch to start from:** `main` (PR #57 merged, plus a second commit fixing gantt/
packet/block).

## Render command

```bash
# Regenerate a single fixture in light mode:
python3 -c "
import sys; sys.path.insert(0,'scripts')
from mermaid_layout import _dispatch, make_page
import pathlib, subprocess
src = pathlib.Path('tests/fixtures/<STEM>.mmd').read_text()
html = make_page(_dispatch(src, None, 800), theme='light')
pathlib.Path('ppt-output/<STEM>-light.html').write_text(html)
" && python3 scripts/html2png.py ppt-output/<STEM>-light.html -o ppt-output/png --fullpage

# Recapture baseline after a fix:
python3 -m pytest tests/test_snapshots.py -k "<STEM>" --snapshot-capture -q
```

## TDD loop

For each bug below:
1. Read the fixture `.mmd` to understand input.
2. Write a **unit test** in `tests/test_strategies.py` or `test_renderer.py` that
   asserts the specific output property (e.g. "HTML contains `<svg` with `<line`").
3. Confirm the test is RED (fails before fix).
4. Fix `scripts/mermaid_layout/_strategies.py` (most changes land here) or
   `_renderer.py` / `_constants.py`.
5. Confirm GREEN, then regenerate the PNG and visually inspect it.
6. Recapture the snapshot baseline.
7. Run `python3 -m pytest tests/ -q --ignore=tests/test_snapshots.py` to confirm
   no regressions.

## Known remaining bugs (priority order)

### P1 — Class diagram node overflow (`class-relationships-all`)

**Fixture:** `tests/fixtures/class-relationships-all.mmd`  
**Bug:** 5 pairs of classes rendered as a grid; in the parent row the 5 nodes
overflow the canvas width — labels are cut off ("Group" → "oup", "Owner" → "wner").  
**Root cause:** `_render_graph_fragment` in `_renderer.py` uses `_assign_coordinates`
which places siblings at fixed `COL_GAP=100` apart; with 5 siblings at `NODE_W=192`
the total width exceeds `width_hint=800`.  
**Fix direction:** In `_assign_coordinates` (or `_compact_group_columns`), when the
total rank width > `width_hint`, scale `COL_GAP` down or spread nodes across two rows.
Alternatively, widen the canvas dynamically: `canvas_w = max(width_hint, CANVAS_PAD*2
+ n_siblings * (NODE_W + COL_GAP))`.

---

### P1 — Timeline period/event separation (`timeline-basic`, `timeline-multiperiod`)

**Fixture:** `tests/fixtures/timeline-basic.mmd`, `timeline-multiperiod.mmd`  
**Bug:** Mermaid syntax `2020 : MVP Launch` means period `"2020"` with one event
`"MVP Launch"`. The renderer combines them as `"2020 : MVP Launch"` in a single box.  
**Root cause:** In `_layout_timeline` (`_strategies.py` ~line 762), the period parser
doesn't split on ` : ` to separate period header from inline event.  
**Fix direction:**
```python
# When a period line has ' : ' split into period + first event:
if ' : ' in line:
    period_name, first_event = line.split(' : ', 1)
    current = {"period": period_name.strip(), "events": [first_event.strip()]}
else:
    current = {"period": line, "events": []}
sections.append(current)
```
Then render each section with a period pill header above an event list below it.

---

### P2 — Hexagon shape doesn't look like a hexagon (`flowchart-shapes-new`)

**Fixture:** `tests/fixtures/flowchart-shapes-new.mmd`  
**Bug:** The hexagon node renders with flat top/bottom and tiny side stubs — looks
like a wide trapezoid rather than a true 6-sided hexagon.  
**Root cause:** The CSS `clip-path` polygon for hexagon in `_renderer.py` is probably
using `polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)` on a square
div (192×192). But the visual stubs suggest the polygon offsets are wrong.  
**Fix direction:** Verify the `clip-path` string in `_renderer.py` for the `hexagon`
shape. It should be `polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)`
on a 192×192 square. If the shape is 192×42 (old non-square), the fix from the
previous session may have only updated height for the default case — check:
```python
# _constants.py _node_render_h:
if n.shape in ("diamond", "hexagon"):
    return NODE_W  # must be NODE_W not NODE_H
```

---

### P2 — Architecture-beta horizontal fan-out (`architecture-complex`)

**Fixture:** `tests/fixtures/architecture-complex.mmd`  
**Bug:** `api --> cache`, `api --> db`, `api --> mq` all land in a single left-aligned
column — no horizontal spread. All 5 nodes in a vertical chain.  
**Root cause:** The architecture-beta strategy (`_layout_architecture` in
`_strategies.py`) places nodes using `_assign_coordinates` which honours rank/column,
but the service nodes in `architecture-complex` may all be assigned rank 2 (children
of `api`) — the column separation of siblings may be broken for architecture.  
**Fix direction:** Inspect how `_layout_architecture` calls `_assign_coordinates`.
Check whether it reuses `_render_graph_fragment` (flowchart path). If the three leaf
services all get `col=0`, they stack vertically. The `_assign_coordinates` function
should spread children of a common parent across different columns.

---

### P2 — Flowchart groups cross-edge routing (`flowchart-groups-complex`)

**Fixture:** `tests/fixtures/flowchart-groups-complex.mmd`  
**Bug:** Cross-subgraph edges (e.g. Web App → REST API across Frontend→Backend group
boundary) route through confused paths creating visual tangles. Groups are scattered
rather than layered.  
**Root cause:** `_assign_coordinates` doesn't account for group membership when placing
nodes — nodes in separate subgraphs can get interleaved column assignments.  
**Fix direction:** When assigning columns, keep subgraph members in contiguous column
ranges. After `_assign_coordinates`, run a pass that computes the column span of each
group and shifts groups to avoid overlap.

---

### P3 — Pie chart jagged polygon arcs (`pie-basic`)

**Bug:** SVG arc segments look like low-resolution polygons (too few vertices).  
**Root cause:** Pie chart in `_layout_pie` builds segments as SVG `<path>` arcs. If
it's using a polygon approximation (multiple `<line>` segments) instead of proper SVG
arc commands, increase the arc resolution or switch to `A` arc commands.  
**Fix direction:** Look for `M ... L ... L ...` arc approximation in `_layout_pie`.
Replace with proper SVG arc path: `M cx cy L x1 y1 A r r 0 large-arc-flag 1 x2 y2 Z`.

---

### P3 — Sequence note text missing (`sequence-note`)

**Fixture:** `tests/fixtures/sequence-note.mmd`  
**Bug:** Note boxes render as empty white rectangles — the note text content is not
displayed inside them.  
**Root cause:** The sequence renderer in `_strategies.py` around the `note` keyword
handling likely creates the box div but doesn't inject the note text into it.  
**Fix direction:** Find the `note` parser in `_layout_sequence`. Check that after
parsing `Note over Alice: text`, the rendered div includes the text content.

---

### P3 — Gantt task labels in row 1 say "Task A" for both tasks (`gantt-basic`)

**Bug:** Phase 1 has Task A and Task B but both appear in row 1 sharing the same
"Task A" label area. Task B label is not shown.  
**Root cause:** The gantt renderer puts the label in the left column and the bars
side-by-side. With 2 tasks, there are 2 bars but only 1 label. Task B's label may be
overlapping Task A's position.  
**Fix direction:** In `_layout_gantt`, each task should have its own row (y coordinate)
with label + bar on the same row. Currently `each_w` divides the bar area into
side-by-side bars — change to one bar per row stacked vertically.

---

### P3 — Mindmap child nodes lack visual containers (`mindmap-basic`, `mindmap-deep`)

**Bug:** Only the root node has a rounded card; branch and leaf nodes are plain text.  
**Fix direction:** In `_layout_mindmap`, add a subtle pill/rounded-rect background
behind branch-level node labels. Use `border-radius:12px; padding:2px 8px; background:
rgba(53,148,103,0.08)` for branch nodes and `rgba(53,148,103,0.05)` for leaves.

---

## Icon mapping audit (informational)

Icons render for registered names. Missing/wrong icons are a fallback issue not a
crash. Known gaps:
- `lambda` → shows generic square (no AWS Lambda icon registered)
- `email`, `mail` → shows generic square
- `worker`, `job` → no icon
These are acceptable polish items — extend the icon registry if exact icons matter.

## Do NOT persist spec/plan docs

Work directly from this prompt. No `docs/specs/` or `plan.md` files needed.
Use the TDD loop inline. Recapture snapshots after each fix.
