# Mermaid Fidelity Harness — Phase 1

Benchmarks `scripts/mermaid_render/` (the native from-scratch renderer)
against real Mermaid.js via mmdc/Chromium across four dimensions:

| Dimension | What | Hard gate? |
|---|---|---|
| Exact semantic | Nodes, edges, groups, labels, order | Yes |
| Relative/normalized layout | Containment, rank direction | Yes |
| Native quality | Overflow, zero-area, outside-canvas | Yes |
| Visual similarity | Normalized center error, aspect delta | No (scored) |

## Quick start

```bash
# Validate manifest (no browser needed)
python tests/fidelity/run.py validate

# Run full comparison against captured oracle
python tests/fidelity/run.py run

# Capture oracle reference observations (requires mmdc)
python tests/fidelity/run.py capture-reference

# Check native renderer determinism
python tests/fidelity/run.py determinism
```

## Directory layout

```
tests/fidelity/
  cases.toml                 — 24 benchmark cases with check-list metadata
  run.py                     — repository entry point
  adapters/
    native.py                — wraps scripts/mermaid_render/ via to_html()
    reference.py             — wraps mmdc/Chromium subprocess
  oracle/
    mermaid-11.15.0-neutral/
      environment.json       — reference environment metadata
      cases/                 — captured reference observations (*.json)
  profiles/
    mermaid-neutral.json     — Mermaid render profile (viewport, theme, font)
    native-neutral.css       — CSS injected after to_html() to neutralize palette
  test_manifest.py           — manifest parse/validation tests
  test_models.py             — data model unit tests
  test_core_boundary.py      — harvestability boundary tests
  test_comparators.py        — semantic/geometry/quality comparator unit tests
  test_mutations.py          — 12 mutation tests (11 must trigger, 1 must not)
  test_phase1.py             — end-to-end Phase 1 acceptance tests
```

## Core library

`tools/mermaid_fidelity/` is the reusable core — extractable to PyPI with
no repo-specific imports. Use it from a standalone project:

```python
from mermaid_fidelity import FidelityRunner, parse_manifest, RenderProfile
```

## Oracle reference: mermaid-11.15.0-neutral

- mmdc 11.15.0, mermaid ^11.14.0
- Playwright 1.61.0, Chromium r1228
- Mermaid `base` theme, 1200×900 viewport
- Font: Helvetica Neue, Helvetica, Arial, sans-serif

To recapture: `python tests/fidelity/run.py capture-reference`

## Renderer data attributes

Phase 1 added fidelity annotations to the native renderer HTML output:

| Element | Attribute | Value |
|---|---|---|
| node div | `data-node-id` | stable node ID (existing) |
| node div | `data-kind` | "node" |
| node div | `data-label` | raw label text |
| node div | `data-shape` | "rect", "diamond", "circle", … |
| node div | `data-order` | rank (integer) |
| node div | `data-parent-id` | subgraph ID (when in a group) |
| group div | `data-group-id` | stable subgraph ID |
| group div | `data-group-label` | subgraph label |
| edge path | `data-src` / `data-dst` | endpoint IDs (existing) |
| edge path | `data-relation-id` | `src__dst__edge_index` |
| edge path | `data-arrow` | marker ID or "none" |
| edge label | `data-relation-id` | same as edge path |

## Cases

24 fixtures across 4 diagram types:

| Type | Count | Examples |
|---|---|---|
| flowchart | 11 | diamond-branch, groups-complex, parallel-links |
| sequence | 7 | basic, complex, alt-loop |
| architecture | 2 | basic, groups-complex |
| er | 4 | basic, ecommerce, cardinality-all, identifying |
