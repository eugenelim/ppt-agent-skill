# Spec: renderer-stable-ids

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** `mermaid-source-bridge`
- **Brief:** none
- **Discovery:** none
- **Contract:** none
- **Shape:** data

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The mermaid renderer's HTML output carries stable, source-derived identity
attributes on every primary entity and edge element for all covered diagram
types. Any consumer (a rendering oracle, a PPTX exporter, a test harness) can
extract the diagram's topology directly from the rendered HTML using
`data-node-id`, `data-src`, `data-dst`, and `data-edge-label` — without
accessing internal parser structures. The attribute values mirror the ids the
mermaid source already declares; they are deterministic and stable across
repeated renders of the same source.

## Attribute scheme

The canonical reference for what attribute each element carries.

| Diagram type | Element | Attribute(s) | Value |
|---|---|---|---|
| flowchart, stateDiagram-v2, classDiagram, erDiagram, architecture-beta, c4* | node `<div>` | `data-node-id` | mermaid source node id |
| flowchart, stateDiagram-v2, classDiagram, erDiagram, architecture-beta, c4* | edge `<path>` (SVG overlay) | `data-src`, `data-dst` | source / dest node ids |
| flowchart, stateDiagram-v2, classDiagram, erDiagram, architecture-beta, c4* | edge label `<span>` | `data-src`, `data-dst`, `data-edge-label` | source / dest ids, label text |
| sequenceDiagram | participant header `<div>` | `data-node-id` | participant actor id (token before `as`) |
| sequenceDiagram | message `<line>` / `<path>` (SVG) | `data-src`, `data-dst` | source / dest participant actor ids |
| sequenceDiagram | message label `<span>` | `data-src`, `data-dst`, `data-edge-label` | actor ids, label text |
| gantt | task bar `<div>` | `data-task-id` | explicit task id (lowercased as parsed) if declared; otherwise the task name verbatim |
| kanban | column header `<div>` | `data-col` | column name |
| kanban | card `<div>` | `data-card` | card label |
| pie | slice label `<span>` | `data-slice` | slice label |
| quadrantChart | point label `<span>` | `data-point` | point name |
| xychart-beta | bar `<div>` | `data-category` | x-axis category label (or `"1"`, `"2"`, … if no labels); line-series-only charts carry no identity attr (no bar div is rendered) |
| packet-beta | field `<div>` | `data-field` | `"start-end"` (or `"start"` when start == end) |
| mindmap | node `<div>` | `data-node-id` | 0-based position index in the source flat list |
| timeline | period `<div>` | `data-node-id` | period name |
| block-beta | block `<div>` | `data-node-id` | block id from source |
| block-beta | edge `<line>` (SVG) | `data-src`, `data-dst` | source / dest block ids |

Note on multi-rank edges: a multi-rank edge A→D (routed through intermediate
dummy nodes) produces multiple path segments, each carrying `data-src="A"
data-dst="D"` — the original endpoint ids, not the ids of any intermediary
dummy nodes.

## Boundaries

### Always do

- Keep every attribute value HTML-escaped (via `_h()` / `escape()`); integer
  values (packet bit ranges, mindmap positional indices) are exempt as they
  contain no HTML-unsafe characters.
- Use the mermaid source id verbatim for `data-node-id`; use a 0-based
  position index only for types that carry no stable source id (mindmap).
- Keep all changes additive: no layout, geometry, or styling change is
  permitted — existing snapshot PNGs must be pixel-identical after this change.
- Add `data-src`/`data-dst` to SVG edge elements (`<path>`, `<line>`) inside
  the overlay when they are the only carrier for edge identity (unlabeled edges
  emit no label `<span>`, so the SVG element is the sole addressable target).
- For multi-rank (dummy-chained) edges, propagate the original source/dest ids
  (`_Edge.orig_src`, `_Edge.orig_dst`) so every path segment in the chain
  carries the real endpoint ids.

### Ask first

- Any change to `_parser.py` or `_constants.py` data structures beyond the two
  optional fields (`orig_src`, `orig_dst`) added to `_Edge` as part of this
  spec — broader structural changes to the shared data model require explicit
  sign-off.

### Never do

- Change layout, geometry, canvas size, or any pixel-visible property.
- Add a new pip dependency.
- Introduce a new module, class, or abstraction layer for attribute emission —
  inline f-string interpolation in the existing emitters is the right level.
- Migrate from the HTML/CSS `<div>` + SVG overlay architecture to pure SVG.

## Testing Strategy

**TDD** for all covered types: assertions are added to
`tests/test_mermaid_layout.py` before the production code they verify, using
the red-green-refactor cycle. Each assertion checks that calling `_dispatch()`
or the relevant strategy on a minimal mermaid source string produces HTML
containing the expected `data-*` attribute with the correct value.

**TDD (property/invariant test)** for the routing pipe-through (`_routing.py`):
property tests in `tests/test_mermaid_layout.py` assert that every dict
returned by `_route_edges` carries `"src"` and `"dst"`, exercised across
forward, back-edge, and self-loop branches in both TB and LR direction modes.

**Goal-based check** for snapshot regression: `pytest tests/test_snapshots.py`
passes with zero diff against the existing PNG baselines.

## Acceptance Criteria

- [ ] **Graph topology — nodes.** For flowchart, stateDiagram-v2, classDiagram,
  erDiagram, architecture-beta, and c4* diagrams: every non-dummy node `<div>`
  in the rendered HTML carries `data-node-id` equal to the mermaid source id.

- [ ] **Graph topology — edge paths.** For the same types: every edge `<path>`
  element in the SVG overlay carries `data-src` and `data-dst` matching the
  original source and destination node ids. This includes forward edges,
  back-edges, self-loops, and multi-rank (dummy-chained) edges — all 6 routing
  branches in `_routing.py`, exercised in both TB and LR direction modes.

- [ ] **Graph topology — edge labels.** For the same types: every edge label
  `<span>` carries `data-src`, `data-dst`, and `data-edge-label` (label text,
  HTML-escaped).

- [ ] **Sequence — participants.** Each participant header `<div>` carries
  `data-node-id` equal to the participant's actor id (the token before `as` in
  `participant A as Alice`; for a bare `Alice->>Bob` message, the id is
  `Alice`).

- [ ] **Sequence — messages.** Each message arrow element (SVG `<line>` or
  `<path>`) carries `data-src` and `data-dst` equal to the actor ids of the
  sending and receiving participants; each message label `<span>` additionally
  carries `data-edge-label`.

- [ ] **Gantt — tasks.** Each task bar `<div>` carries `data-task-id` equal to
  the explicit task id (lowercased as parsed by the strategy) if one is
  declared in the source, otherwise the task name verbatim.

- [ ] **Kanban — columns and cards.** Each column header element carries
  `data-col` equal to the column name; each card `<div>` carries `data-card`
  equal to the card label.

- [ ] **Pie — slices.** Each slice label `<span>` carries `data-slice` equal
  to the slice label.

- [ ] **Quadrant — points.** Each point label `<span>` carries `data-point`
  equal to the point name.

- [ ] **XYchart — bars.** Each bar `<div>` carries `data-category` equal to
  the x-axis category label (or the 1-based index string when no label list is
  provided). Line-series-only xychart (no `bar` directive) renders no bar divs
  and therefore carries no identity attribute — this is a known gap, out of
  scope for this spec.

- [ ] **Packet — fields.** Each field `<div>` carries `data-field` equal to
  `"start-end"` for multi-bit fields or `"start"` for single-bit fields.

- [ ] **Mindmap — nodes.** Each node `<div>` carries `data-node-id` equal to
  its 0-based position index in the source flat list (stable: same source →
  same index on every render).

- [ ] **Timeline — periods.** Each period `<div>` carries `data-node-id` equal
  to the period name.

- [ ] **Block-beta — blocks and edges.** Each block `<div>` carries
  `data-node-id` equal to its source block id; each SVG `<line>` edge carries
  `data-src` and `data-dst`.

- [ ] **Positional-id stability.** Rendering the same mindmap source twice
  produces identical `data-node-id` values (same positional indices) both
  times. (Graph-topology, sequence, and other source-id-derived types are
  deterministic by construction.)

- [ ] **No pixel change.** `pytest tests/test_snapshots.py` passes with zero
  diff against existing PNG baselines.

- [ ] **All existing tests pass.** `pytest tests/test_mermaid_layout.py` and
  `pytest tests/test_snapshots.py` both green; lint and typecheck clean.

## Assumptions

- **Technical**: `_Node.id`, `_Edge.src`, `_Edge.dst`, `_Edge.label` already
  parsed in `_constants.py` lines 187–210; no parsing change needed
  (source: `scripts/mermaid_layout/_constants.py`)
- **Technical**: `_route_edges` result dict does not currently carry `src`/`dst`
  — confirmed by reading all 6 `result.append()` calls in `_routing.py`
  (source: `scripts/mermaid_layout/_routing.py`)
- **Technical**: block-beta parser extracts `blk["id"]` for each block and
  tracks edges as `(src_id, dst_id)` tuples; stable source ids exist
  (source: `scripts/mermaid_layout/_strategies.py` `_layout_block`)
- **Technical**: `data-*` attrs on SVG `<path>`/`<line>` elements may be
  dropped by dom-to-svg in `html2svg.js`; this is acceptable because the
  downstream oracle reads our HTML pre-SVG (source: task brief)
- **Technical**: `tests/test_svg2pptx.py` does not exist; the test gate is
  `test_mermaid_layout.py` + `test_snapshots.py`
  (source: ls of tests/ directory)
- **Technical**: `tests/test_oracle.py` is on a sibling branch and is not a
  gate for this PR; it is the downstream consumer this change enables
  (source: task brief)
- **Process**: Full mode required — this is a structural change to the HTML
  output contract (source: task brief)
- **Product**: block-beta has stable source ids (`blk["id"]`) and is included
  in scope (source: user confirmation 2026-07-19)
