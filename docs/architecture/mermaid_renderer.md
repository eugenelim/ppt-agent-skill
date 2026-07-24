# Mermaid Renderer Architecture

This document describes the current structure of the mermaid renderer in
`scripts/mermaid_render/`. It is a living document; update it when the
layout or module split changes.

## Module Map

```
scripts/mermaid_render/
├── layout/
│   ├── _parser.py          # syntax analysis; strips directives, detects type
│   ├── _constants.py       # shared constants (NODE_W, COL_GAP, etc.)
│   ├── _geometry.py        # immutable geometry types (FinalizedLayout, RoutedEdge, …)
│   ├── _pipeline.py        # flowchart compilation: parse → ELK → FinalizedLayout
│   ├── _sequence_compile.py# sequence diagram compilation (split from _strategies, AC6)
│   ├── _diagram_types.py   # non-flowchart diagram types (gantt, pie, mindmap, …)
│   ├── _strategies.py      # dispatch + class/ER helpers; re-exports from split modules
│   ├── _layout.py          # pure graph algorithms (rank, crossing, coordinate assign)
│   ├── _routing.py         # edge routing and waypoint computation
│   ├── _renderer.py        # HTML/SVG serializers (render_finalized is canonical)
│   ├── _text.py            # text measurement (Pillow-backed _MEASURER)
│   ├── architecture.py     # architecture-beta compiler
│   ├── elk_adapter.py      # ELK-JS bridge (subprocess or HTTP)
│   └── shape_geometry.py   # node boundary and shape math
└── mermaid_layout.py       # top-level public entry point
```

## Semantic Pipeline

Every diagram type follows the same four-stage pipeline:

```
Source text
    │
    ▼
1. Parse (._parser)
    Extract directive, strip frontmatter, identify node/edge/group tokens.
    Output: typed AST objects (_Node, _Edge, _Group, etc.)

    │
    ▼
2. Compile / Layout (._pipeline, ._sequence_compile, architecture.py, …)
    Convert AST into geometry. For flowcharts: ELK-JS or Python fallback.
    For sequences: pure-Python _layout_lifeline.
    Output: FinalizedLayout (immutable, pre-routed geometry)

    │
    ▼
3. Render / Serialize (._renderer.render_finalized)
    Convert FinalizedLayout → HTML/SVG string.
    MUST NOT perform any geometry work (AC8).
    Output: HTML string

    │
    ▼
4. Validate (optional, ._sequence_compile.validate_sequence_geometry, …)
    Check geometry invariants; return ValidationResult.
```

## Layout Graph

`FinalizedLayout` is the canonical geometry output. It is immutable
(frozen dataclass) and contains:

- `node_layouts`: `MappingProxyType[str, NodeLayout]` — per-node bounds
- `group_layouts`: `MappingProxyType[str, GroupLayout]` — per-group bounds
- `routed_edges`: `tuple[RoutedEdge, ...]` — pre-computed waypoints
- `visible_bounds`: canvas bounding box (excludes padding)
- `canvas_bounds`: full canvas including padding
- `direction`: layout direction (TB, LR, RL, BT)
- `diagnostics`: `LayoutDiagnostics` — warnings and fallback metadata
- `routing_failures`: edges that could not be routed

Key invariant: `FinalizedLayout` always contains pre-routed edges.
`render_finalized` must consume `routed_edges` directly and MUST NOT
call `_route_edges` again (AC8).

## ELK and Fallback Rules

The flowchart compiler (._pipeline) uses ELK-JS for layout:

1. **ELK success path**: ELK-JS returns a valid layout → edges are
   extracted from `sections` → `FinalizedLayout` is built.
   `diagnostics.backend` = `"elk-js"`.

2. **ELK unavailable** (`ElkUnavailable`): Python fallback runs
   (`_layout.py` algorithms). `diagnostics.backend` = `"python-fallback"`.

3. **ELK invalid result** (`_ElkInvalidResult`): re-raised as
   `ArchitectureLayoutError`; no silent fallback.

**Rule**: `LayoutMetadata.backend` must always be non-empty. A hidden
fallback (backend = `""`) is a CI failure condition (AC5).

The `geometry_verifier.verify_layout()` function checks 8 structural
invariants on every `FinalizedLayout` before rendering:
- Canvas bounds are positive
- All node bounds are within canvas
- Nodes do not overlap
- All routed edge endpoints are on visible node boundaries
- Edges do not enter node interiors
- Group containment (all members are within group bounds)
- Backend metadata is non-empty

## Recursive Compounds

Groups (subgraphs) are supported via recursive compound layout. A group
can contain other groups. The ELK `compound=True` mode handles nesting.

Invariant: every node belongs to at most one group.
Groups may be nested; the `group_layouts` map covers all levels.

## Text Measurement

All text measurement goes through `_text._MEASURER` (a Pillow-backed
singleton). Functions:

- `_MEASURER.layout(text, style, max_width)` → `TextLayout`
  - `.max_content_width`: natural width if unconstrained
  - `.height_px`: total height

**Never** use raw string-length estimates (`len(text) * 8.0`) in new
code. The Pillow measurer handles Unicode, proportional fonts, and
multi-line wrapping correctly.

## Shape Geometry

Node bounds and shapes live in `shape_geometry.py`. The `_node_shape`
function determines the clip/boundary shape for a given node class.
`render_finalized` uses these bounds for:
- Exact endpoint snapping (edge waypoints land on boundary, not interior)
- Overlap checking
- Containment checking

## Oracle Statuses

`OracleStatus` (in `tools/mermaid_fidelity/oracle_contract.py`) has five
values:

| Status | Meaning |
|--------|---------|
| `PASS` | All checks passed; at least one check required (AC9) |
| `FAIL` | One or more checks failed |
| `EXTRACTOR_GAP` | Reference extractor could not extract the needed data |
| `UNSUPPORTED_REFERENCE_FEATURE` | mmdc feature not supported by our renderer |
| `UNVALIDATED` | No geometry checks were run for this fixture |

**AC9 invariant**: `OracleResult(status=PASS, checks=())` raises
`ValueError` in `__post_init__`. A comparator cannot silently return
PASS without recording at least one check.

## Faithful Mode

The renderer supports a `faithful` mode flag. When `faithful=True`:
- The renderer attempts to match mmdc output pixel-for-pixel
- Shape clip paths use exact geometry from `shape_geometry.py`
- Edge waypoints use ELK-computed paths, never straight-line fallback

When `faithful=False` (default): the renderer uses a simplified layout
suitable for slide generation.

## CI Reproduction

Fast parity checks (browser-free, < 60 s):

```bash
make parity-fast
# or
pytest tests/ -m parity_fast --timeout=60
```

Pinned browser/reference suite (sequential, requires Playwright):

```bash
make parity-browser
# or
pytest --run-browser tests/ -m browser -p no:xdist
```

CI jobs are defined in `.github/workflows/tests.yml`:
- `parity-fast`: browser-free geometry and gate checks
- `parity-browser`: mmdc reference capture + oracle comparison

To reproduce a CI failure locally:
1. Ensure the same Python version as CI (3.13)
2. `pip install -r requirements-dev.txt`
3. `make parity-fast` for the fast job
4. `playwright install chromium --with-deps && make parity-browser` for the browser job

## Module Split History

`_strategies.py` was refactored as part of the boston-v1 initiative
(item 13: mermaid-parity-ci-and-maintainability-cleanup). The split:

| Module | Contents |
|--------|---------|
| `_pipeline.py` | Flowchart compilation (ELK path + Python fallback) |
| `_sequence_compile.py` | Sequence diagram compilation + validation |
| `_diagram_types.py` | Non-flowchart diagram types (gantt, pie, mindmap, …) |
| `_strategies.py` | Dispatch + class/ER helpers + re-exports (shim) |

All names previously importable from `_strategies.py` remain importable
(AC10: backward compatible).
