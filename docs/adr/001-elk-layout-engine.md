# ADR-001: ELK as Primary Layout Engine for Graph-Topology Diagrams

- **Status:** Accepted
- **Date:** 2026-07-22
- **Spec:** [`docs/specs/mermaid-unified-layout-pipeline/spec.md`](../specs/mermaid-unified-layout-pipeline/spec.md)

## Context

`scripts/mermaid_render/layout/` implements a from-scratch Sugiyama-style graph layout
pipeline (cycle-breaking → longest-path ranking → barycentric crossing minimisation →
PAV coordinate assignment → A\* orthogonal edge routing). This pipeline is documented
as "pure Python, no subprocess, no external layout engine" in
`docs/backlog.md#adt-pure-python-layout`, with the rationale of portability,
determinism, and zero Node.js runtime dependency.

After completing the `flowchart-pipeline-finish` and `mermaid-fidelity-hardening`
specs, analysis of the 15 named fixture cases reveals persistent issues with:
- Node-node and node-group-title overlap in complex subgraph layouts
- Incorrect edge clipping for non-rectangular shapes
- Post-layout group-separation heuristics that conflict with inner-direction subgraphs
- Feedback-lane routing that produces non-intuitive global lanes

ELK (Eclipse Layout Kernel, via `elkjs`) is a production-grade graph layout library
that handles hierarchical layout, port constraints, edge routing, and inner-direction
subgraphs natively. It eliminates the post-layout fixup passes that are the source of
the overlap and clipping issues.

## Decision

Use `elkjs` 0.12.0 as the **primary layouter** for graph-topology diagram types
(flowchart, stateDiagram-v2, stateDiagram). Invoke it via a pinned Node.js subprocess
(`layout/elk_runner.js`) from `layout/elk_adapter.py`.

The existing Python Sugiyama + A\* implementation remains as an explicit fallback,
activated by:
- `MERMAID_LAYOUT_ENGINE=python` environment variable (user opt-out)
- Node.js runtime absent at invocation time (`shutil.which("node")` returns `None`)
- `ElkUnavailable` exception from the subprocess (non-zero exit, timeout, malformed JSON)

Non-graph-topology diagram types (sequence, ER, class, architecture-beta, etc.) are
**not** affected — they have their own layout implementations and are out of scope.

## Consequences

**Positive:**
- Eliminates overlap, clipping, and post-layout fixup hacks for the 15 named fixtures
- Hierarchical and inner-direction subgraph layout handled natively by ELK
- Both HTML and SVG painters consume the same `FinalizedLayout` (unified pipeline)

**Negative / mitigations:**
- **Node.js runtime required in CI and production.** CI must have Node installed.
  Python-only environments (e.g. restricted serverless) use the Python fallback.
- **New external dependency.** `elkjs@0.12.0` pinned in
  `scripts/mermaid_render/layout/package.json`. `node_modules/` is gitignored;
  install via `npm ci --prefix scripts/mermaid_render/layout` in CI.
- **Non-determinism across engines.** ELK and Python Sugiyama produce different
  coordinates for the same source. "Deterministic" means within a single engine.
  CI enforces Node presence so ELK is the canonical engine for snapshot baselines.
- **`tests/test_dependencies.py::TestNoSubprocess` exemption.** `elk_adapter.py`
  is added to `_SUBPROCESS_EXEMPTIONS`; all other layout modules remain subprocess-free.

## Supersedes

The `adt-pure-python-layout` backlog item (`docs/backlog.md#adt-pure-python-layout`)
tracked creating a formal ADR for the pure-Python constraint; this ADR supersedes
the intent of that item by recording the reversal decision instead. The backlog item
should be marked closed.

## Alternatives considered

1. **Fix the Python Sugiyama pipeline** — would require implementing full network-simplex
   ranking, proper hierarchical compaction, and constrained port assignment. Estimated
   scope: 4–6 weeks; ELK already solves these correctly.
2. **Graphviz/DOT** — mature but subprocess-based and non-deterministic across versions.
   No hierarchical-handling API for cross-subgraph edges.
3. **dagre-d3** — JavaScript, similar API to ELK but less actively maintained; no port
   constraints or hierarchical handling.
