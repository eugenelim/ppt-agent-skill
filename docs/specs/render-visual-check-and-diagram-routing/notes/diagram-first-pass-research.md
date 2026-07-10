# Research — first-pass diagram quality (author-time, no visual feedback)

Synthesis from an evidence-retriever pass (2026-07-10). Question: what author-time
techniques make LLM-generated HTML/CSS/SVG diagrams render correctly on the **first
pass**, before any review loop? Applies to item E of this spec.

## Why LLMs fail first-pass diagram geometry

1. **Numerical tokenization mismatch** — coordinates are treated as character
   sequences, not magnitudes; ~half of SVG-generation errors are coordinate math.
2. **Local vs. global integration gap** — >80% on local primitive recognition
   ("which way does this arrow point") but <50% on composing multiple spatial
   constraints at once; errors often preserve one axis and lose the other.
3. **Scaling collapse** — accuracy degrades nonmonotonically with graph size (avg
   −42.7%, up to −84% on large inputs); multi-step place→route→check loses prior
   spatial state.

Consequence: asking an LLM to **decide topology and hand-place coordinates in one
pass** is its worst case.

## Highest-leverage author-time interventions (ranked, low-install)

1. **Separate structure from coordinates.** Emit `{nodes, edges}` as data first, then
   place deterministically (DiagrammerGPT). Cheap static-HTML form: topological sort →
   CSS-grid **row per layer**, distribute nodes across columns, anchors at
   `(col·cellW + nodeW/2, row·cellH)`, polylines with one elbow. O(N), no float math
   by the LLM. **We adopt the approximation, not a layout engine — no dependency.**
2. **Layered (Sugiyama) discipline** — cycle-break → layer-assign → crossing-min →
   place. dagre/ELK implement it; we approximate phases 2+4 with CSS grid.
3. **Complexity budget** — hard cap ≈ **8–12 nodes, 10–15 edges** per diagram; above
   it, split into sub-diagrams; dense many-to-many → **bus topology** (already in
   `blocks/diagram.md` §3.1 ④). This is a **planning-stage** lever.
4. **Reason-before-code** — emit a discarded `<layout-plan>` (node list w/ row/col
   hints + edge list w/ direction) before the HTML/SVG, forcing spatial conflicts to
   resolve first.
5. **Geometry invariants as CSS variables** — `--grid-unit`, `--node-w`, `--node-h`;
   connector math is algebraic (`--node-w/2`) not drifting literals. Reinforces the
   existing theme-contract in `blocks/diagram.md`.
6. **Pre-render self-check assertions** (on the data/plan, before finalize): bounding-
   box containment in canvas; **endpoint clamped inside target node bbox**; text-
   overflow estimate `len(label)·char_w ≤ node_w − pad`; pairwise node overlap (O(N²),
   cheap for N≤12). Maps to `page-html-playbook.md` Phase 8 diagram self-check.

## Caveat

Auto-layout can fight **human-intended grouping** (e.g. "storage on the right").
Mitigation: let planning assign nodes to named **zones**; place within zones. We keep
zones as author intent, approximate layout within them — we do **not** adopt a layout
engine (honors the no-dependency boundary).

## Citations

- Stuck in the Matrix: Probing Spatial Reasoning in LLMs — arXiv 2510.20198
- DiagrammerGPT (COLM 2024) — arXiv 2310.12128
- GeoSVG-RL — arXiv 2605.25447
- Reason-SVG — arXiv 2505.24499
- ELK Layered — eclipse.dev/elk ; Dagre — g6.antv.antgroup.com
- Token-efficiency analysis — dev.to/akari_iku ; Sugiyama overview — yworks.com
