# mermaid_render — Agent Context

Scoped context for agents working inside `scripts/mermaid_render/` and
`scripts/mermaid_render/layout/`. Read the root `AGENTS.md` first; this
file adds the visual-verification loop specific to renderer work.

## Key files

| File | Role |
|---|---|
| `layout/_routing.py` | Edge routing — polyline paths, port selection, fan-out |
| `layout/route_search.py` | A* / obstacle-aware route search |
| `layout/endpoint_geometry.py` | Where a line attaches to a shape boundary |
| `layout/shape_geometry.py` | Polygon outlines for all shape types |
| `layout/_layered.py` | Layered (Sugiyama) layout: rank assignment, crossing minimisation, coordinate assignment |
| `layout/_layout.py` | Top-level layout pipeline; subgraph padding, group placement |
| `layout/_renderer.py` | Two paths: main (Python layout) and `render_finalized` (ELK). Shape fixes go in **both**. |
| `layout/_constants.py` | NODE_W/H, GROUP_PAD_*, spacing constants — change here, not inline |
| `layout/native_svg.py` | Class/ER/requirement native-SVG render path |
| `layout/port_planner.py` | Port-side allocation for parallel edges |
| `layout/node_ordering.py` | Node order refinement within ranks |
| `layout/elk_adapter.py` | ELK layout adapter (requires Node + elkjs) |

## Visual-verification loop — mandatory for renderer work

Every iteration of a renderer fix **must** run the compare gallery and
visually inspect the output before declaring done. The gallery renders
our implementation alongside mmdc side-by-side for exact comparison.

### Step-by-step

```bash
# 1. Render the specific fixture(s) you changed, open in browser
python tools/compare_gallery.py --open tests/fixtures/<name>.mmd

# 2. Screenshot for inspection (pass the output dir, not individual files)
python scripts/html2png.py ppt-output/compare/ours/ -o ppt-output/compare/screenshots/

# 3. Read the screenshot with your image tool and compare against mmdc SVG
#    ppt-output/compare/screenshots/<name>.png  ← ours
#    ppt-output/compare/mmdc/<name>.svg          ← mmdc reference

# 4. Iterate until the visual output matches mmdc structurally:
#    - All nodes present and correctly placed
#    - Connector lines attach cleanly to shape edges (not interiors)
#    - Lines are straight where the graph allows it
#    - No overlapping lines at the same start/end point
#    - Subgraph containers have adequate padding (not nodes touching edges)
#    - No shape label truncation or overlap
```

### What "fixed" means

Compare against the mmdc SVG (the ground truth). The fix is done when:
1. The screenshot for **this** fixture looks structurally equivalent to mmdc.
2. `pytest tests/` still passes (fast tier, no browser required).
3. No visual regression on other fixtures you didn't intend to change
   (run gallery for a broader set and spot-check).

### Algorithmic approach — not patches

Prefer root-cause algorithm changes:
- If lines bend where they shouldn't → fix the port-side selection or
  routing heuristic in `_routing.py` / `route_search.py`.
- If endpoints land inside shapes → fix `endpoint_geometry.py` and
  `shape_geometry.py` clip logic.
- If subgraph padding is wrong → fix `_constants.py` GROUP_PAD_* or
  the coordinate-assignment phase in `_layered.py`.
- If nodes overlap or are misplaced → fix rank assignment or crossing
  minimisation in `_layered.py`.
- If parallel edges overlap → fix `port_planner.py` fan-out allocation.

Avoid: hard-coding offsets for a single fixture, special-casing by
fixture name, adding `if diagram_name == "..."` guards.

## Diagram-type entry points

| Diagram type | Primary files |
|---|---|
| `flowchart` | `_layout.py` → `_layered.py` → `_routing.py` → `_renderer.py` |
| `classDiagram` | `native_svg.py` (connector geometry uses `endpoint_geometry.py`) |
| `requirementDiagram` | `requirement.py` (layout) + `native_svg.py` (render) |
| `architecture-beta` | `architecture.py` |

## Fast test gate

```bash
# Zero-browser, zero-mmdc — run this after every change
pytest tests/
```

If geometry invariants fail, the specific assertion tells you which
edge or node violated a routing/placement rule. Fix the algorithm,
not the assertion.
