# Mermaid Fidelity Harness — Phase 1

Benchmarks `scripts/mermaid_render/` (the native SVG renderer) against
real Mermaid.js via mmdc/Chromium across four dimensions:

| Dimension | What | Hard gate? |
|---|---|---|
| Exact semantic | Nodes, edges, groups, labels, order | Yes |
| Relative/normalized layout | Containment, rank direction | Yes |
| Native quality | Overflow, zero-area, outside-canvas | Yes |
| Visual similarity | Normalized center error, aspect delta | No (scored) |

## Scope — what Phase 1 covers

Phase 1 covers the 13 **active** cases — diagram families the native
renderer already implements:

| Type | Cases | Status |
|---|---|---|
| flowchart | 11 | Active (natively rendered) |
| architecture | 2 | Active (natively rendered) |
| sequence | 7 | **Planned** — NATIVE_UNSUPPORTED expected |
| er | 4 | **Planned** — NATIVE_UNSUPPORTED expected |

- **Active** cases: all strict checks must pass. Any NATIVE_UNSUPPORTED is
  a CI failure.
- **Planned** cases: NATIVE_UNSUPPORTED is expected and acceptable. Adding
  native support for these families is tracked separately.

## Quick start

```bash
# Validate manifest (no browser needed)
python tests/fidelity/run.py validate

# Run full comparison against captured oracle
python tests/fidelity/run.py run

# Capture oracle reference observations (requires mmdc)
python tests/fidelity/run.py capture-reference

# Check native renderer determinism (active-only cases)
python tests/fidelity/run.py determinism
```

## Directory layout

```
tests/fidelity/
  cases.toml                 — 24 benchmark cases (lifecycle field on each)
  run.py                     — repository entry point
  adapters/
    native_svg.py            — wraps scripts/mermaid_render/ via to_svg()
    reference.py             — wraps mmdc/Chromium subprocess
  oracle/
    mermaid-11.15.0-neutral/
      environment.json       — reference environment metadata
      cases/                 — captured reference observations (*.json)
  profiles/
    mermaid-neutral.json     — Mermaid render profile (viewport, theme, font)
    native-neutral.css       — CSS injected after to_svg() to neutralize palette
  test_manifest.py           — manifest parse/validation tests
  test_models.py             — data model unit tests
  test_core_boundary.py      — harvestability boundary tests + registry checks
  test_comparators.py        — semantic/geometry/quality comparator unit tests
  test_mutations.py          — 12 mutation tests (11 must trigger, 1 must not)
  test_phase1.py             — end-to-end Phase 1 acceptance tests
  test_hardening.py          — hardening suite: false-green elimination, stale
                               oracle, multiset relations, lifecycle validation
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

Oracle JSON files include `source_sha256` (SHA-256 of the `.mmd` file at
capture time). A mismatch between current source and oracle hash is
reported as `STALE_ORACLE` — re-run `capture-reference` to refresh.

## Renderer data attributes

Phase 1 added fidelity annotations to the native renderer SVG output:

| Element | Attribute | Value |
|---|---|---|
| node shape | `data-node-id` | stable node ID |
| node shape | `data-kind` | "node" |
| node shape | `data-label` | raw label text |
| node shape | `data-shape` | "rect", "diamond", "circle", … |
| node shape | `data-order` | rank (integer) |
| node shape | `data-parent-id` | subgraph ID (when in a group) |
| group element | `data-group-id` | stable subgraph ID |
| group element | `data-group-label` | subgraph label |
| edge path | `data-src` / `data-dst` | endpoint IDs |
| edge path | `data-relation-id` | `src__dst__edge_index` |
| edge path | `data-arrow` | marker ID or "none" |

## Check registry

`tools/mermaid_fidelity/registry.py` is the single source of truth for
all check names and their policy kinds (strict / scored / ignored).
The manifest validates check names against the registry at parse time.
New checks must be registered here before they can appear in cases.toml.

## Cases

24 fixtures across 4 diagram types:

| Type | Count | Lifecycle | Examples |
|---|---|---|---|
| flowchart | 11 | active | diamond-branch, groups-complex, parallel-links |
| sequence | 7 | planned | basic, complex, alt-loop |
| architecture | 2 | active | basic, groups-complex |
| er | 4 | planned | basic, ecommerce, cardinality-all, identifying |
