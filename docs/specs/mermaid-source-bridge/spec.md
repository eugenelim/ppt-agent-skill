# Spec: mermaid-source-bridge

- **Status:** Implementing
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Mode:** full (new script + planning-schema extension + render-path integration)
- **Constrained by:**
  - [`diagram-consistency-system`](../diagram-consistency-system/spec.md) — the
    `diagram-architecture` recipe templates (CSS-variable theming contract,
    connector-topology rules) must exist before `mermaid_layout.py` output can be
    integrated into the HTML render step. The layout engine can be authored and
    unit-tested independently but render-path wiring cannot be exercised until
    the recipe family ships.
- **Contract:** none
- **Shape:** mixed (new script + schema extension + playbook edits)

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

---

## Problem

When a source document (any Markdown file the user provides — an RFC, a design
spec, an API doc, an exported Notion page, a hand-authored system description,
anything) contains one or more Mermaid fences, those diagrams carry
**semantically correct topology** that a human already validated. The topology is
the hard part; the rendering is not.

Today that topology is thrown away. The planner reads the source document for its
prose, routes the relevant slide as a `diagram` card, and at render time the HTML
agent **re-invents the diagram from scratch** — guessing coordinates, edge routes,
and layout — because no Mermaid source has been threaded into the planning JSON.
The re-invented diagram is always worse than the original: the model has to do
geometry from memory with no feedback loop, at a scale (>8 nodes) where its
accuracy is worst.

The same quality gap applies even to diagrams that look "correct" in a Markdown
editor. The Mermaid.js dagre layout engine is the problem: it assigns positions
non-deterministically, produces crossings, and cannot be styled to match the
deck's design system. So the fix is not "render the Mermaid better" — it is
**parse the topology once, lay it out with a deterministic algorithm, and emit
pipeline-safe HTML/CSS that the deck's CSS variables theme automatically**.

---

## Objective

Thread Mermaid diagram topology from any source document into the ppt-agent's
primary planning → proof → render flow, and render it with a **native layout
engine** (`scripts/mermaid_layout.py`) that bypasses dagre entirely and produces
pipeline-safe, deck-themed HTML/CSS output on the first pass.

The three concerns:

- **A — Source extraction (Steps 1–4):** When source documents are present,
  extract Mermaid fences and attach the raw Mermaid source to the relevant
  planning JSON card rather than discarding it. This is a fork at the outline /
  planning stage: the planner either references source material directly or
  embeds the extracted Mermaid text — but the planning JSON becomes the single
  source of truth before the proof gate.
- **B — Proof-gate visibility:** The proof worksheet must display extracted
  Mermaid source as a fenced code block so the reviewer can verify topology
  before committing to an expensive render.
- **C — Native layout engine:** `scripts/mermaid_layout.py` takes a Mermaid
  flowchart/graph source string and outputs a self-contained HTML/CSS fragment
  with deterministically positioned nodes and edge paths, using the
  `blocks/diagram.md` CSS-variable theming contract. No new runtime dependency;
  pure Python.

---

## The fork in detail

The primary flow has two decision points where the fork materialises:

### Fork at Step 3 (Outline)

During outline planning, when the agent reads source documents it encounters
Mermaid fences. At this point it must:

1. **Enumerate every Mermaid fence** in the source document (by `fence_index`,
   0-based) and evaluate each one independently.
2. **For each fence the planner decides to use**, create a corresponding outline
   item that becomes a diagram slide. One fence → one slide candidate. If a
   source document contains four fences and all four are relevant, the planner
   produces four diagram slide entries, each carrying its own `mermaid_source`.
3. **Record** the raw Mermaid source text on each outline item as `mermaid_source`
   — a passthrough field that survives into Step 4.
4. If a fence is incidental prose illustration (e.g., a tiny two-node example
   in a design doc) rather than a primary diagram, the planner may skip it. But
   the decision to skip or include is the planner's, made explicitly — not a
   silent omission.

This is the "extract and include" path. The alternative ("refer to source at
render time") is rejected because it breaks the proof gate: a render agent that
reads the source document directly bypasses the planning JSON as the single
source of truth, makes the proof worksheet silent about diagram topology, and
reintroduces the ad-hoc invention problem at render time.

### Fork at Step 4 (Planning)

When a diagram card's outline item carries `mermaid_source`, the planner writes
it into the card's new `diagram_source` field (see schema extension below). The
card is still routed normally: `card_type: diagram`, correct `diagram_type`,
`block_refs` pointing to the family recipe file. The `diagram_source` field is
additive — it does not replace the routing contract, it provides the topology
that the layout engine will consume.

---

## Planning JSON schema extension

A new **optional** field `diagram_source` is added to cards with
`card_type: diagram`. It is ignored on all other card types.

```json
{
  "card_type": "diagram",
  "diagram_type": "flowchart",
  "headline": "...",
  "diagram_source": {
    "origin": "source_document",
    "mermaid_source": "flowchart TB\n  A[Ingest] --> B[Process]\n  B --> C[Store]\n",
    "source_ref": "path/to/source.md",
    "fence_index": 0
  },
  "resources": {
    "block_refs": ["diagram", "diagram-process-flow"]
  }
}
```

Fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `origin` | `"source_document"` | yes | Fixed string; identifies that topology came from external source, not LLM synthesis |
| `mermaid_source` | string | yes | Mermaid source text with config frontmatter stripped — directive line, nodes, edges, subgraphs only. `title:` frontmatter is promoted to `headline` (if unset) before stripping. |
| `source_ref` | string | no | Relative or absolute path to the source document. Informational only — the pipeline does not re-read it. |
| `fence_index` | integer | yes | 0-based index of this fence within the source document. Required when `origin` is `"source_document"` — it is the key that makes each extracted fence traceable and uniquely identifies which fence this card represents. If a source document has N fences and the planner uses all N, there will be N diagram cards each with a distinct `fence_index`. |

`diagram_source` is **absent** when the diagram is synthesised by the planning
agent from research (the existing path). Its presence signals to the render agent
to call `mermaid_layout.py` instead of hand-generating geometry.

**One fence per card, always.** A card's `diagram_source` holds exactly one
fence. The planner never merges two fences into one card. If multiple fences
from the same source document belong together (e.g., a container diagram and its
sequence flow), they become separate slides and the deck narrative connects them.

### Validator check `DIAG-SRC-01` (WARN)

`planning_validator.py` gains check `DIAG-SRC-01`: fires only when
`card_type == "diagram"` and `diagram_source` is present. Checks:
1. `mermaid_source` is a non-empty string beginning with a recognised Mermaid
   directive (any directive in the strategy table above, case-insensitive first
   token). Note: `mermaid_source` is stored as topology only (frontmatter already
   stripped); leading `---` frontmatter blocks will not appear in valid stored
   source and are not tolerated.
2. `fence_index` is an integer when `origin == "source_document"`.

Emits WARN (not FAIL) on any failure so a malformed fence does not block the
gate; the render agent falls back to the existing ad-hoc path and the WARN
surfaces in the proof worksheet.

---

## Proof-gate display

`scripts/proof_worksheet.py` gains a `mermaid_source` display block: when a
diagram card has `diagram_source.mermaid_source`, the worksheet renders it as a
fenced Markdown code block under the card's title. The reviewer sees the exact
topology that will be laid out — not a rendered image, not a description. This is
the cheapest possible proof that the right diagram will render before the
expensive HTML step runs.

---

## `scripts/mermaid_layout.py` — native layout engine

A new pure-Python script (no new `pip` dependency). Consumes Mermaid flowchart
or graph source; emits a self-contained HTML/CSS fragment. The emitted HTML uses
only CSS variables from the `blocks/diagram.md` theming contract
(`--node-bg-from/to`, `--node-border`, `--node-fg`, `--edge`, `--edge-strong`,
`--node-accent`, `--label-font`, etc.) and no hardcoded colors.

### Scope: all Mermaid diagram types

The layout engine handles **all Mermaid diagram types** present in the Mermaid
v11 spec. Each type maps to one of the following rendering strategies (dispatched
by directive name in the script's `main()` — direct `if/elif`, no registry):

| Mermaid directive | Strategy | Layout algorithm |
|---|---|---|
| `flowchart`, `graph` | Graph topology | Steps 1–6 below (longest-path + barycenter) |
| `sequenceDiagram` | Lifeline layout | Participants as vertical columns; messages as horizontal arrows with activation boxes |
| `stateDiagram-v2`, `stateDiagram` | Graph topology | Same as flowchart (states are nodes, transitions are edges) |
| `erDiagram` | Entity-relation layout | Entities as nodes, relationships as labeled edges; group by entity rank |
| `classDiagram` | Hierarchical layout | Inheritance edges rank-up; association edges horizontal |
| `gantt` | Timeline layout | Tasks as horizontal bars on a time axis; sections as horizontal swim-lanes |
| `timeline` | Chronological layout | Events as horizontally distributed nodes on a single axis |
| `quadrantChart` | Grid layout | 2×2 fixed grid; points plotted by (x, y) value |
| `pie`, `pie showData` | Donut/pie layout | Segments sized by value; labels on arcs |
| `xychart-beta` | Bar/line chart | Axes, bars, and lines drawn from data |
| `mindmap` | Radial tree layout | Root at centre; branches radiate outward by depth |
| `block-beta` | Grid block layout | Blocks positioned in declared rows/columns |
| `packet-beta` | Bit-field layout | Fixed-width cells across a horizontal axis |
| `kanban` | Column layout | Cards stacked in labelled vertical columns |
| `architecture-beta` | Zone-node layout | Nodes grouped in named zones; edges between zones and nodes |
| `C4Context`, `C4Container`, `C4Component` | C4 layered layout | Boundary boxes as containers; nodes inside; relationships as edges |

For directive types not listed above (e.g., `gitGraph`, `journey`,
`requirementDiagram`), the script attempts graph-topology rendering as a
best-effort fallback; on parse failure it exits 1 and the render agent falls
back to the ad-hoc path.

### Algorithm (six steps, no layout library)

Grounded in the grok-build Rust implementation (`xai-org/grok-build mermaid.rs`,
Apache 2.0) and the existing first-pass research in
`docs/specs/render-visual-check-and-diagram-routing/notes/diagram-first-pass-research.md`.
All six steps are pure Python integer arithmetic; no float layout math.

**Step 1 — Parse**

Tokenise the Mermaid source:
- Node declarations: detect label-text and shape from bracket type
  (`[rect]`, `(round)`, `{diamond}`, `[(cylinder)]`, `>flag]`, `(( circle ))`).
- Edge declarations: detect line style (solid `-->`, dotted `-.->`), arrowhead
  direction, and optional label (`-- text -->`).
- Subgraph blocks: push/pop a group stack; assign each node to its innermost
  group.

Output: `nodes: list[Node]`, `edges: list[Edge]`, `groups: list[Group]`.

Cap: 64 nodes, 128 edges, 16 groups (measured after parsing, before dummy-node
insertion). Above the cap, exit non-zero with a message naming the cap and
suggesting the planner split the diagram. See complexity-budget note in
`docs/specs/render-visual-check-and-diagram-routing/notes/diagram-first-pass-research.md`.

**Step 2 — Cycle break**

DFS from source nodes (in-degree 0). Back-edges are marked `reversed=True` and
conceptually flipped for layout; the arrowhead is flipped back at render time.

**Step 3 — Rank assignment**

Longest-path ranking (same as grok-build):

```python
for u in reverse_topological_order(dag):
    for v in dag[u].successors:
        rank[v] = max(rank[v], rank[u] + 1)
```

Insert dummy nodes on edges where `rank[target] - rank[source] > 1` so every
edge spans exactly one rank. Dummy nodes are invisible at render time; they
anchor edge bend-points.

Subgraphs are expanded inline at this step: their internal nodes are ranked as
part of the parent graph, then a bounding-box group container is drawn around
them.

**Step 4 — Crossing minimisation**

Eight passes of barycenter relaxation (same count as grok-build):
- Forward pass (rank 0 → max): for each node in rank R, compute its barycenter
  as the mean column-position of its predecessors in rank R-1. Sort nodes within
  each rank by barycenter ascending. **Rank-0 nodes have no predecessors** — use
  declaration order as the initial ordering, with node ID as a stable tiebreaker
  throughout all passes.
- Backward pass (rank max → 0): same logic, using successors.
- Repeat ×4 (8 passes total).

After all passes, assign each node an integer column index based on its sorted
position. When two nodes tie on barycenter, break ties by node ID (lexicographic)
to guarantee deterministic output across runs.

**Step 5 — Coordinate assignment**

All measurements in CSS custom-property multiples; the HTML fragment declares
`--grid-unit: 120px; --node-w: 160px; --node-h: 56px;` as defaults (overridable
by the deck's `:root`).

```
x[node] = column_index(node) * (--node-w + --h-gap)   # --h-gap: 48px default
y[node] = rank(node)         * (--node-h + --v-gap)   # --v-gap: 64px default
```

Canvas width  = `(max_columns + 1) * (--node-w + --h-gap)`
Canvas height = `(max_rank + 1)    * (--node-h + --v-gap)`

Node labels are wrapped at 20 display chars; multi-line nodes increase
`--node-h` proportionally. Font: `var(--label-font)`.

Subgraph group containers are drawn as `position:absolute` divs whose bounding
box encloses all member nodes plus 16px padding. They use `--node-accent-2` for
their border and a faint fill.

**Step 6 — Edge routing**

Three strategies:

- **Adjacent-rank forward edge**: cubic Bezier from bottom-centre of source node
  to top-centre of target node. SVG `<path d="M ... C ... ">`. Endpoint formula:
  `(x + --node-w/2, y + --node-h)` → `(x' + --node-w/2, y')`. Control points at
  one-third and two-thirds of the vertical span. Arrowhead: inline SVG
  `<polygon>` at the target endpoint (pipeline-safe; matches `diagram.md`
  arrowhead rule).
- **Back-edge / multi-rank jump**: exit from the right side of the source node,
  travel to a reserved right-lane column (max_column + 1.5 grid units), descend
  to target rank, re-enter from the right side of the target. Orthogonal path via
  three SVG `<line>` segments.
- **Self-loop (gap = 0, source = target)**: a loopback arc rendered as a small
  SVG `<path>` that exits the top-right of the node, curves right 24px, and
  re-enters the bottom-right. Arrowhead at the re-entry point. Common in
  `stateDiagram` self-transitions. Same-rank non-self edges (gap = 0, different
  nodes) are treated as back-edges and routed via the right-lane strategy above.

Edge labels (if any) are HTML `<span>` elements overlaid at the midpoint of the
Bezier, positioned absolutely. No SVG `<text>`.

Fan-in / fan-out follows the topology rules in `blocks/diagram.md` §3.1: multiple
edges converging on a single target distribute their endpoint x-offsets across the
node bottom edge (no stacking at center); fan-out from a single source distributes
symmetrically across the node top.

### Output format

The script emits a single `<div class="diagram mermaid-layout">` fragment:

```html
<div class="diagram mermaid-layout" style="position:relative; width:__px; height:__px; --grid-unit:120px; --node-w:160px; --node-h:56px;">
  <!-- node divs, position:absolute, left/top in px -->
  <div class="node" style="left:Xpx; top:Ypx; width:var(--node-w); height:var(--node-h);">
    <span class="node-label">Label text</span>
  </div>
  <!-- SVG overlay for edges -->
  <svg style="position:absolute; inset:0; width:100%; height:100%; overflow:visible; pointer-events:none;">
    <path d="..." stroke="var(--edge)" fill="none" stroke-width="1.5"/>
    <polygon points="..." fill="var(--edge)"/>
  </svg>
</div>
```

All color values are CSS variables; no hardcoded hex. The fragment is
self-contained (no external assets, no JS) and passes `pipeline-compat.md`
rules: no SVG `<text>`, no CSS triangles, no pseudo-elements for visual content,
no `mask-image`.

### CLI interface

```bash
python3 SKILL_DIR/scripts/mermaid_layout.py \
  --source <mermaid_source_string_or_@file> \
  [--direction TB|LR|RL|BT]   # override graph direction; default from source
  [--width-hint 960]           # canvas width hint (px); script scales --node-w to fit
  [--output fragment.html]     # default: stdout
```

Exit 0: HTML fragment written to stdout/file.
Exit 1: parse error (unsupported directive, syntax error, cap exceeded) — the
render agent falls back to the ad-hoc path and logs the error.

---

## Render-path integration

The HTML render agent (Step 5c, per-page orchestrator) gains the following
pre-render step for `card_type: diagram` cards:

1. Check for `diagram_source.mermaid_source` in the card JSON.
2. If present and non-empty:
   a. Write `mermaid_source` to a tempfile (to avoid shell-quoting hazards with
      newlines and special characters), then run
      `python3 SKILL_DIR/scripts/mermaid_layout.py --source @/tmp/diag-src.mmd --output /tmp/diagram-fragment.html`.
   b. On exit 0: embed the fragment as the card's diagram content. The
      surrounding recipe template (whichever family was routed via `block_refs`)
      provides the card shell (title, background, padding); the layout engine
      output occupies the diagram content area.
   c. On exit 1: fall back to the existing ad-hoc geometry path; log the error
      as a comment in the HTML for traceability.
3. If absent: use the existing ad-hoc path (no regression).

---

## Boundaries

### Always do

- The planning JSON remains the single source of truth before the proof gate.
  Never have the render agent re-read source documents to recover Mermaid fences
  that should have been extracted at planning time. Source documents are read once
  (Steps 1–3); their relevant content flows into planning JSON.
- Emit only CSS-variable colors in `mermaid_layout.py` output. No hardcoded hex
  except the documented trend green/red pair.
- Obey `pipeline-compat.md` in the layout engine's HTML output: arrowheads as
  `<polygon>`, connectors as `<div>` or SVG `<line>`/`<path>`, all labels as
  HTML (never SVG `<text>`).
- Treat `mermaid_source` as verbatim source topology, not as a prompt to the
  LLM to "generate a diagram about X". The layout engine is deterministic; the
  LLM does not touch the geometry.
- Keep `mermaid_layout.py` pure Python with no new `pip` dependency. The
  algorithm is O(N²) at worst (pairwise overlap check, N≤64) and must complete
  in under 2 seconds for any input within the cap.

### Ask first

- Raising the node/edge cap above 64/128 — higher caps risk slides that are too
  dense to read; the complexity-budget recommendation is 8–12 nodes per diagram.
- Changing the `diagram_source.origin` enum to support values other than
  `"source_document"` (e.g., a future `"llm_synthesised"` for round-tripping
  through the layout engine on generated diagrams).

### Never do

- Re-read the source document in the render agent. If the fence wasn't extracted
  at planning time, the render agent does not silently go back to the source — it
  falls back to the ad-hoc path and the missing extraction is a planning-stage
  failure to fix on the next run.
- Add `mermaid.js` or any external layout library (`dagre`, `elkjs`) as a
  runtime dependency. The layout engine is the replacement, not a wrapper.
- Change the `planning_validator.py` `DIAG-SRC-01` check to FAIL-gating before
  it has been exercised on real decks. It starts as WARN.

---

## Testing strategy

- **Parser correctness** — unit tests (inline with `smoke_test.py` phases) over
  Mermaid fixture strings covering: TB/LR flowchart, subgraph nesting, cycle
  (back-edge), node shapes (rect/round/diamond/cylinder), edge labels, dotted
  edges. Assert parsed node/edge counts match expected.
- **Layout determinism** — same fixture string produces identical `(x, y)` values
  on two successive calls (no randomness). Assert.
- **Pipeline-safety** — `grep` assertions on script output: no SVG `<text>`, no
  hardcoded hex (excluding `#22c55e` / `#ef4444`), arrowheads are `<polygon>`,
  no `::before`/`::after`.
- **CSS-variable inheritance** — render one output fragment via `html2png.py`
  under three `style.json` variants (dark/light/editorial); confirm node fill
  and edge stroke change with the deck palette and `visual_qa.py` returns non-FAIL.
- **Cap enforcement** — fixture at 65 nodes exits 1; fixture at 64 nodes exits 0.
- **Validator check `DIAG-SRC-01`** — fixture planning JSON with malformed
  `mermaid_source` (`""`, wrong directive, missing field) emits WARN; valid
  `mermaid_source` emits no DIAG-SRC-01 warning.
- **Proof worksheet** — fixture card with `diagram_source` produces a fenced code
  block in the worksheet HTML; fixture card without `diagram_source` produces no
  such block.
- **Performance** — at the cap (64 nodes, 128 edges): `time python3
  scripts/mermaid_layout.py --source @/tmp/cap-fixture.mmd` completes in under
  2 seconds on the development machine. This is a spot-check, not a CI gate.

---

## Acceptance criteria

- [x] **AC1** `scripts/mermaid_layout.py` exists, is pure Python (no new pip
  dependency), and exits 0 with an HTML fragment on valid flowchart input.
- [x] **AC2** The HTML fragment passes pipeline-compat assertions: no SVG
  `<text>`, no CSS triangles, no `::before`/`::after` visual content, no
  `mask-image`; arrowheads are `<polygon>`; all colors are CSS variables.
- [ ] **AC3** The fragment rendered via `html2png.py` under three style variants
  inherits node fill, border, and edge stroke from deck CSS variables;
  `visual_qa.py` returns non-FAIL on each.
  _(deferred: mermaid-source-bridge-ac3-visual-qa)_
- [x] **AC4** `planning_validator.py` check `DIAG-SRC-01` fires WARN (not FAIL)
  on a card with `diagram_source.mermaid_source = ""` or an unrecognised
  directive prefix; passes silently on a valid `mermaid_source`.
- [x] **AC5** `proof_worksheet.py` renders `diagram_source.mermaid_source` as a
  fenced Markdown code block in the card's proof row when present.
- [x] **AC6** The SKILL.md Step 3 playbook and Step 4 planning instructions
  document the extraction fork: when to embed `diagram_source.mermaid_source` in
  the card vs. treating the source document as prose only.
- [x] **AC7** The render-path integration is documented in the per-page
  orchestrator template: `diagram_source` present → call
  `mermaid_layout.py` → embed; exit 1 or absent → existing ad-hoc path.
- [x] **AC8** Layout is deterministic: two calls with the same Mermaid source
  produce byte-identical HTML output (verified in smoke tests).
- [x] **AC9** The spec README table and spec header `Status:` are both updated:
  README row `Draft` → `Implementing`; `spec.md` line 3 `Status: Draft` →
  `Status: Implementing`.

---

## Open questions

1. **Mermaid frontmatter directives.** ~~Should frontmatter be stripped?~~
   **Resolved: strip all frontmatter that does not affect rendering; keep what
   does.** Since the layout engine is our own renderer (not Mermaid.js), all
   `config:` blocks (`layout: elk`, `theme: dark`, `look: neo`, etc.) are
   renderer-specific and irrelevant — strip them. The `mermaid_source` stored in
   planning JSON is topology only: the directive line, nodes, edges, subgraphs.
   Exception: `title:` in frontmatter is promoted to the card's `headline` if no
   headline was already set, then stripped from `mermaid_source`. Everything else
   in frontmatter is discarded silently.

3. **Implementation phasing.** ~~Should the initial implementation phase by type?~~
   **Resolved: no phasing.** All Mermaid diagram types in the strategy table ship
   in a single implementation. The plan.md will sequence the rendering strategies
   by complexity (graph-topology first, then structured layouts, then chart types)
   but the acceptance criteria gate is the full table. Partial delivery is not
   acceptable.

---

## Appendix: Visual Design Contract

Derived from `references/blocks/diagram.md`, `references/blocks/diagram-architecture.md`,
`references/design-runtime/design-specs.md`, `references/design-runtime/css-weapons.md`,
`references/pipeline-compat.md`, and cross-validated against Mermaid neo theme source
and D2 SVG renderer constants. Every value here is either sourced directly from those
files or explicitly calibrated against them.

### A. CSS variables declared on `.diagram` root

```css
.diagram {
  /* Node surfaces — all bound to deck tokens, never hardcoded */
  --node-bg-from:   var(--card-bg-from);
  --node-bg-to:     var(--card-bg-to);
  --node-border:    var(--card-border);
  --node-radius:    var(--card-radius, 8px);   /* fallback 8px; range across styles: 0–20px */
  --node-fg:        var(--text-primary);
  --node-fg-dim:    var(--text-secondary);

  /* Edges */
  --edge:           var(--card-border);
  --edge-strong:    var(--accent-1);           /* critical path / emphasis */

  /* Subgraph containers */
  --group-border:   var(--accent-1);
  --group-radius:   12px;                      /* larger than node radius; fixed */

  /* Accent nodes */
  --node-accent:    var(--accent-1);
  --node-accent-2:  var(--accent-2);

  /* Typography */
  --label-font:     var(--font-primary);
  --label-mono:     var(--font-mono);          /* lineart mode only */

  /* Spacing (all multiples of 8px) */
  --rank-gap:       48px;   /* vertical between node rows */
  --col-gap:        16px;   /* horizontal between same-rank nodes */
  --node-pad-v:     12px;
  --node-pad-h:     16px;
  --canvas-pad:     40px;   /* outer canvas inset */
}
```

**Lineart mode override** (`schematic_blueprint` and any style with
`decorations.diagram_mode: "lineart"`): the layout engine detects this flag and
emits an additional override block on `.diagram`:

```css
.diagram {
  --node-bg-from: transparent;
  --node-bg-to:   transparent;
  --node-radius:  4px;           /* reduced; some styles use 0px */
  --edge:         var(--card-border);
  /* box-shadow: forbidden in lineart — no override */
}
```

### B. Node visual treatment

| Property | Value | Source |
|---|---|---|
| `border-radius` | `var(--node-radius, 8px)` | `diagram.md` contract; range 0–20px across styles |
| `border` | `1px solid var(--node-border)` | `diagram-architecture.md` template |
| `padding` | `12px 16px` | `diagram-architecture.md` node template |
| `min-width` | `120px` | `diagram.md` shared node primitive |
| `min-height` | `56px` | `diagram.md` shared node primitive |
| `box-sizing` | `border-box` | `diagram.md` shared node primitive |
| Background | `linear-gradient(180deg, var(--node-bg-from), var(--node-bg-to))` | `diagram.md` theme contract — even a near-imperceptible gradient reads as premium vs. flat fill |
| `box-shadow` (default) | none | Lineart rule; shadows add weight at slide scale |
| `box-shadow` (focal node, 1–2 per diagram max) | `0 0 0 1px var(--node-accent)` | `diagram-architecture.md` — double-ring halo, not elevation |
| `box-shadow` (elevated context only) | `0 1px 2px rgba(0,0,0,.10), 0 4px 8px rgba(0,0,0,.08), 0 12px 24px rgba(0,0,0,.12)` | `css-weapons.md` W7 three-layer progressive shadow |
| Node title `font-size` | `14px` | `diagram-architecture.md`; Mermaid neo default; D2 legend |
| Node title `font-weight` | `700` | `diagram-architecture.md` |
| Node title `color` | `var(--node-fg)` — **never accent color** | `diagram.md` node title color rule — emphasis is on border+halo, not text |
| Sub-label `font-size` | `12px` | `diagram-architecture.md` |
| Sub-label `color` | `var(--node-fg-dim)` | `diagram.md` |
| Inner flex gap (title → sub-label) | `4px` | `diagram.md` tight-symbiosis spacing |

**Inset top-edge highlight** (premium treatment for dark-background styles only):
```css
box-shadow: inset 0 1px 0 rgba(255,255,255,0.10);
```
Adds a "catch light" on the node top edge. Omit on light-background styles (transparent or near-white `--card-bg-from`).

**Node color discipline** — the most frequently violated rule (documented in `diagram.md`):
- Node background and border **never** carry category information. Category lives on connector/arrowhead color.
- Forbidden: `.node.blue`, `.node.green` overriding background or border for grouping.
- Permitted per-node differentiation: `border-left: 2px solid var(--node-accent)` accent bar on neutral background (legend/category list only, no connectors).
- Focal node emphasis: `border-color: var(--node-accent); box-shadow: 0 0 0 1px var(--node-accent)`. Title stays `--node-fg`.

### C. Edge and connector visual treatment

| Property | Value | Source |
|---|---|---|
| `stroke-width` | `1.5px` | `diagram-architecture.md`; `diagram.md` balance rule: node border 1px → connector ≤ 1.5px |
| Lineart stroke-width | `1px` standard, `1.2px` critical path only | `diagram.md` lineart rules |
| Default curve | **Orthogonal elbow** `M x1 y1 H midX V y2 H x2` — reads "engineered" | Mermaid sharp-edge default; D2 default for architecture |
| Flow diagrams | Cubic Bézier `M x1 y1 C cx1 cy1 cx2 cy2 x2 y2` from node bottom-centre to top-centre | For sequence/flow types only |
| Elbow corner | Sharp 90° (no arc) | Technical diagrams; D2 supports 0–20px rounded elbows — not needed here |
| Key-path / strong edge | `stroke: var(--edge-strong)` — color change only, no width change | `diagram.md` — width change breaks line-weight balance |
| Dotted edge | `stroke-dasharray: 6 4` | Two-value form only (pipeline-safe); `stroke-dashoffset` is forbidden |
| Arrowhead | SVG `<polygon>` only — never CSS border triangles | `pipeline-compat.md`; `diagram.md` arrowhead primitive |
| Arrowhead size | 14px wide × 12px tall (`points="104,2 118,8 104,14"` on viewBox `0 0 120 16`) | `diagram-architecture.md` shared arrowhead SVG |
| Arrowhead fill | Same as edge stroke (`var(--edge)` or `var(--edge-strong)`) | `diagram.md` |
| Edge label font-size | `11px` | Typography hierarchy (see §E) |
| Edge label background | `var(--card-bg-from)` at `0.8` opacity | Ensures legibility over connectors |

**Fan-in / fan-out endpoint distribution** — from `diagram.md` §3.1:
- N edges converging on one target: distribute entry x-positions as `a + (b−a)·i/(N+1)` across the node's padded bounding box. Never route all lines to geometric center.
- Target endpoint clamped to `[y_top + r, y_bottom − r]` (r = node-radius). Never copy source center-y to target.
- Dense many-to-many (>4×4): bus topology — one trunk + short stubs, not N×M diagonals.
- SVG `<marker orient="auto">` is unreliable in downstream renderers — arrowhead polygon points must be calculated explicitly per connector.

### D. Layout spacing (all multiples of 8px)

| Dimension | Value | Source |
|---|---|---|
| Rank gap (vertical between rows) | `48px` | `diagram-architecture.md` layer template: 14px padding above + 24px SVG connector zone + 10px breathing room |
| Column gap (horizontal, same rank) | `16px` | `diagram-architecture.md` node row flex `gap: 16px` |
| Subgraph / group container padding | `28px 20px 20px` | `diagram-architecture.md` group div (top larger to clear floating label) |
| Subgraph border-radius | `12px` | `diagram-architecture.md`; larger than node radius (8px) |
| Canvas outer padding | `40px` | `design-specs.md` content zone inset |
| Minimum gap between any two nodes | `40px` | Cocoon-AI architecture-diagram spec |
| Node inner padding | `12px 16px` | `diagram-architecture.md` |
| Available slide content width | `1200px` | `design-specs.md` (1280 − 2×40) |
| Available slide content height | `580px` | `design-specs.md` (720 − 80 header − 60 footer) |

### E. Typography hierarchy

| Role | `font-size` | `font-weight` | `letter-spacing` | `color` |
|---|---|---|---|---|
| Diagram section / layer heading | `11px` | `700` | `+0.15em` (≈ `1px`) | `var(--accent-1)` |
| Section heading `text-transform` | uppercase | — | — | — |
| Node primary label | `14px` | `700` | `-0.005em` | `var(--node-fg)` |
| Node sub-label | `12px` | `400` | `0` | `var(--node-fg-dim)` |
| Edge label | `11px` | `400` | `+0.05em` | `var(--node-fg-dim)` |
| Subgraph / group title | `11px` | `700` | `+0.15em` | `var(--group-border)` (= `--accent-1`) |
| Subgroup title `text-transform` | uppercase | — | — | — |

Subgraph group title positioning: `position: absolute; top: -10px; left: 16px; padding: 0 8px; background: var(--bg-primary)` — interrupts the dashed border, creating the "badge in the border" effect. Implemented as a real `<span>` (no pseudo-elements).

Font feature settings on all node labels (the absence of these reads as AI-generated):
```css
font-feature-settings: 'kern', 'liga', 'calt';
-webkit-font-smoothing: antialiased;
```

### F. Pipeline-safety hard rules

Properties that **must not appear** in layout engine output (they survive HTML preview but break PPTX export via dom-to-svg):

| Forbidden | PPTX failure | Safe substitute |
|---|---|---|
| SVG `<text>` | Coordinates offset ±3–5px | Absolute-positioned HTML `<span>` over SVG |
| CSS border triangle (`width:0; height:0; border:`) | Shape lost | SVG `<polygon>` |
| `::before` / `::after` for visual content | Content disappears | Real `<span>` or `<div>` |
| `background-clip: text` + `-webkit-text-fill-color` | White text on color block | `color: var(--accent-1)` |
| `mask-image` | Element disappears | `<div>` overlay with `linear-gradient` background |
| `conic-gradient` | Does not render | SVG `<circle>` + two-value `stroke-dasharray` |
| `mix-blend-mode` | Not supported | `opacity` overlay |
| `filter: blur()` | Rasterized and displaced | `opacity` or `box-shadow` |
| `stroke-dashoffset` | Ignored | Omit entirely (use two-value `stroke-dasharray` only) |
| `@keyframes` / `animation` / `transition` | PPTX has no animation | Omit entirely |
| `backdrop-filter` | Not supported | Tinted `rgba()` background |

Safe for use: `clip-path: polygon()`, multi-layer `box-shadow`, `border-radius`, `linear-gradient`, `radial-gradient`, `stroke-dasharray` (two-value form only), `writing-mode`.
