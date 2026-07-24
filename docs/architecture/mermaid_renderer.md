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

## Shared vs. non-shared pipelines

Not every diagram type shares the same compiler. The eight-case parity
initiative (davao-v1) settled three distinct compile paths:

| Diagram family | Compiler module | Backend | Shared? |
|----------------|-----------------|---------|---------|
| flowchart (incl. compound subgraphs) | `_pipeline._compile_flowchart` | ELK-JS → Python fallback | shared `FinalizedLayout` painter (`_renderer.render_finalized`) |
| architecture-beta | `architecture.compile_architecture` → `arch_to_finalized` | ELK-JS → Python fallback | reuses the `FinalizedLayout` painter via `arch_to_finalized` |
| sequence | `_sequence_compile` (single parser + single geometry compiler) | pure-Python canonical geometry | own native scene painter (`native_svg._sequence_scene`) |
| class / ER | `_strategies` + `_renderer._render_graph_fragment` | Python | separate HTML fragment painter |

Flowchart and architecture converge on the immutable `FinalizedLayout` and the
canonical `render_finalized` painter. Sequence does **not** go through
`FinalizedLayout`; it produces `SequenceGeometry` and paints a native SVG
scene. Class/ER still use the older `_render_graph_fragment` HTML path.

**Sequence canonical geometry.** There is exactly **one** sequence parser
(`_sequence_compile.parse_sequence_semantics`) and **one** geometry compiler
(`compile_sequence_geometry`). The legacy independent parser `layout/sequence.py`
and the `native_svg._sequence_scene` delegation to it were retired in item 2;
`layout/sequence.py` no longer exists and cannot be imported. `box` and
fragment geometry are first-class outputs of the shared compiler — the old
"skip boxes/fragments" behavior is gone.

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
can contain other groups.

- **ELK path:** ELK `compound=True` mode handles nesting; each group carries
  its `local_direction` and ELK lays out the full compound graph in one pass.
- **Python fallback (item 3, bottom-up measured proxies):** the fallback builds
  the complete group tree and processes groups **bottom-up (leaf groups first)**.
  Each group measures its title, lays out direct nodes and child-group *proxies*
  using its `local_direction`, reserves the title band and padding, routes
  internal edges, computes its finalized size, and exposes itself to its parent
  as a **measured proxy**. The parent packs from those proxies; child proxies are
  then expanded by translating already-finalized internal geometry. This
  replaced the old "global layout → move members → separate groups → recompute
  boxes" post-global-placement correction (the unconditional inner-direction
  fixup `_apply_inner_direction_positions`), which was deleted in the eight-case
  parity cleanup (spec AC4/AC5).
- **Empty groups are first-class:** an empty subgraph is a real measured proxy
  sized from its title metrics + deterministic minimum content box. It is never
  parked at the origin and never overlaps or touches a sibling group.

Invariant: every node belongs to at most one group.
Groups may be nested; the `group_layouts` map covers all levels.

## Boundary Gates

Cross-scope edges (an edge whose endpoints live in different group scopes) must
cross group boundaries only through **declared gates**. For each cross-scope
relationship the compound layout:

1. **Creation** — selects deterministic entry/exit sides from source/destination
   positions, the group's `local_direction`, route length, crossing
   minimization, and title-band avoidance, then records an explicit
   `BoundaryGate` (`_geometry.BoundaryGate`, kind `ENTRY`/`EXIT`).
2. **Waypoint insertion** — inserts each gate point into the actual route as a
   waypoint, so the gate is a real constraint on the drawn path, not metadata.
3. **Gate validation** — `_layout_validation.validate_compound_gates` requires:
   a gate record exists; each gate lies on its group boundary; the route touches
   each gate point; the route crosses each gated group exactly once per gate
   (no leave/re-enter); and the route never threads an unrelated group interior.

## Backend Provenance

Every rendered fixture lane stamps a seven-field provenance record (see
`tests/test_eight_case_validation.py::Provenance`). Each field has an explicit
source and is **never inferred from another field** — in particular
`layout_backend` is read from `LayoutMetadata.backend` (or the sequence-path
constant), never derived from `output_format`:

| Field | Source |
|-------|--------|
| `renderer_api` | call site (`to_html` / `to_svg`) |
| `output_format` | call site (`html` / `svg`) |
| `semantic_compiler` | compiler identity (`flowchart` / `architecture` / `sequence`) |
| `layout_backend` | normalized `LayoutMetadata.backend`: `elkjs` / `python-fallback` / `sequence-geometry` |
| `fallback_reason` | typed reason when the Python fallback ran; `None` on ELK |
| `node_version` | Node `--version`, only on the ELK lane |
| `elkjs_version` | pinned elkjs version, only on the ELK lane |

A hidden fallback (empty `LayoutMetadata.backend`) or a `layout_backend` carrying
an output-format token is a hard CI failure (`validate_backend_declared`,
`validate_provenance`).

## Validation Invariants

The eight-case acceptance harness lives in
`scripts/mermaid_render/layout/_layout_validation.py` — kept **separate** from
the in-pipeline `_geometry.validate_finalized_layout` so tightening the
acceptance bar does not perturb the production render path. It is *segment-aware*
(complete route segments, not only waypoints, participate). Gates:

- `validate_canvas_coverage` — every waypoint **and** every segment inside the
  canvas; nodes/groups within canvas. Negative-coordinate layouts are
  *translated* into positive space (`translate_layout_to_positive`), never
  clipped.
- `validate_segment_obstruction` — no segment crosses an unrelated node
  interior, unrelated group interior, group title band, or another edge's label
  rectangle.
- `validate_compound_gates` — the boundary-gate contract above.
- CI hard-failure gates (`validate_backend_declared`, `validate_provenance`,
  `validate_no_auto_ports`, `validate_sibling_groups_disjoint`,
  `validate_local_directions`, `validate_edge_styles`, `validate_min_counts`,
  `validate_membership`, `validate_parent_refs`, `semantic_divergence`) — one per
  spec-listed hard-failure condition; exercised by
  `tests/test_eight_case_ci_gates.py`.

**Known deferred defect.** On the ELK path the `architecture-complex`
`api→cache` route clips `queue`'s interior (backlog anchor
`arch-elk-edge-interior-crossing`). Item 5 forbids redesigning the successful
ELK path, so the architecture ELK geometry gate is a narrowly-scoped `xfail`
tied to that anchor; the architecture Python-fallback lane and all flowchart
fixtures stay hard gates.

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
