# Spec: Architecture + Renderer Maintainability Cleanup

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** `docs/specs/eight-case-parity-ci-and-cleanup`, `docs/specs/architecture-fixed-port-integration`
- **Brief:** none
- **Discovery:** none
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Three backlog anchors from the Eight-Case Mermaid parity initiative
(`renderer-two-paths-faithful-resolver`, `arch-fallback-duplicate-body`,
`arch-elk-roundtrip-lossy`) are resolved by three targeted refactors — all
within two files — that eliminate duplicated logic and carry previously-dropped
data through an intermediate model. T3 intentionally changes observable ELK-path
output: `content_bounds` and `diagnostics` now flow through `_finalized_to_arch`
→ `arch_to_finalized` rather than being re-derived from fixed offsets / empty.
The eight-case CI gate stays green and all existing tests pass. The
`arch-dual-edge-id-desync` anchor (ELK-path edge_id reconstruction) is out of
scope for this PR and remains open.

## Boundaries

### Always do

- Keep `_render_graph_fragment`'s existing call sites unmodified: the new
  `faithful` keyword argument defaults to `False`.
- Keep `_arch_fallback_to_finalized`'s public signature and return type
  (`FinalizedLayout`) unchanged — five tests call it directly.
- Add at least one new test per extracted function / newly-carried field.
- Prove zero CI regression with `make eight-case-ci` in the same worktree
  that has elkjs installed (not a fresh /tmp worktree).

### Ask first

- Any change to the `ArchitectureDiagramLayout` frozen-dataclass field order
  or removal of an existing field.
- Any change to `arch_to_finalized`'s `isinstance(arch, FinalizedLayout)`
  pass-through guard.

### Never do

- Redesign or replace the ELK layout path (frozen by
  `docs/specs/architecture-fixed-port-integration`).
- Add new top-level imports of `._geometry` to `architecture.py` at module
  load time — the lazy-import pattern is intentional.
- Introduce a new public module-level export (all extracted helpers are
  module-private, leading underscore).
- Change `compile_architecture`'s public signature or return type.

## Testing Strategy

All three refactors are pure structural changes; the definitive invariant is
identical observable output before and after:

- **Goal-based check (CI gate):** `make eight-case-ci` passes with elkjs
  installed in the same worktree. Covers the architecture ELK path and
  flowchart/sequence render paths (which go through `render_finalized`), but
  does NOT cover `_render_graph_fragment` (the classDiagram HTML path, which
  has no eight-case fixture).
- **TDD for extracted functions:** `_edge_stroke_attrs` needs 7 cases:
  3 styles (`thick`, `dotted`, `solid`) × 2 faithful states (6), plus one
  `cls-dotted` × `faithful=False` case asserting the superset dash branch
  fires. `_build_arch_layout` is exercised through the existing five
  fallback-path tests; a new test asserts edge-id uniqueness for a duplicate
  `(src, dst)` pair.
- **TDD for the raw-style fragment painter:** a new test drives `_layout_class`
  (which delegates to `_render_graph_fragment` internally) with a classDiagram
  that contains a dependency (`..>`) relation, whose raw style is `cls-dotted`,
  and asserts `stroke-dasharray` is present in the output. See Deviations for
  the deviation from the AC12 literal wording. This test locks the function's
  raw-style behavior across the shared-resolver extraction.
- **TDD for newly-carried fields:** a round-trip test (`_finalized_to_arch`
  → `arch_to_finalized`) asserts that `content_bounds` and
  `diagnostics.route_failures` survive unchanged for a synthetic
  `FinalizedLayout` whose node bounds differ from the fixed-offset derivation.
- **TDD for Python-fallback path:** covered by the five direct unit tests
  calling `_arch_fallback_to_finalized` (AC5), not by the CI gate (which
  routes `architecture-complex` through ELK when elkjs is installed).
- **Goal-based check (grep):** `grep -n "seen_pairs" architecture.py` returns
  all matches inside exactly one function (`_build_arch_layout`) after Task 2.

## Acceptance Criteria

- [x] AC1: `_edge_stroke_attrs(edge_style: str, faithful: bool = False) ->
  tuple[str, str, str]` exists as a module-level function in
  `scripts/mermaid_render/layout/_renderer.py`. Both `_render_graph_fragment`
  and `render_finalized` call it; neither inlines the three-branch resolver.
  The function derives `dash` from `style == "dotted" or style.endswith("-dotted")`
  (superset, preserving classDiagram `cls-dotted` dashed edges), and derives
  `stroke_color` and `stroke_w` from the three-branch `thick / dotted / else`
  logic with the `faithful` guard on color only.

- [x] AC2: `_render_graph_fragment` accepts `faithful: bool = False` as a
  keyword-only argument and passes it through to `_edge_stroke_attrs`. All
  existing callers work unchanged (default applies).

- [x] AC3: The NOTE comments referencing `renderer-two-paths-faithful-resolver`
  are removed from both painters. `grep -n "renderer-two-paths"
  scripts/mermaid_render/layout/_renderer.py` returns zero matches.

- [x] AC4: `_build_arch_layout(nodes, edges, groups, *, width_hint=0,
  backend="python-fallback") -> ArchitectureDiagramLayout` exists as a
  module-private function in `scripts/mermaid_render/layout/architecture.py`.
  It contains the single authoritative service-tile / junction /
  group-boundary / edge construction body.

- [x] AC5: `_arch_fallback_to_finalized` calls `_build_arch_layout` then
  `arch_to_finalized`. Its signature `(nodes, edges, groups, *, width_hint=0)`
  and return type `FinalizedLayout` are unchanged. All five tests that call
  it directly pass.

- [x] AC6: `compile_architecture`'s Python-fallback branch calls
  `_build_arch_layout` and returns its result directly, with no inlined
  service-tile / junction / group-boundary / edge construction body.

- [x] AC7: All occurrences of `seen_pairs` in
  `scripts/mermaid_render/layout/architecture.py` are inside exactly one
  function (`_build_arch_layout`) — the counter is no longer duplicated.

- [x] AC8: `ArchServiceTile` gains `content_bounds: Optional[object] = None`
  appended as the last field. `ArchitectureDiagramLayout` gains
  `diagnostics: Optional[object] = None` appended as the last field.

- [x] AC9: `_finalized_to_arch` carries `nl.content_bounds` into
  `ArchServiceTile.content_bounds` and `fl.diagnostics` into
  `ArchitectureDiagramLayout.diagnostics`.

- [x] AC10: `arch_to_finalized` uses `svc.content_bounds` when not `None`,
  else derives from fixed offsets `Rect(x=b.x+8.0, y=b.y+4.0,
  w=float(max(b.w-16.0, 20.0)), h=float(max(b.h-8.0, 10.0)))`. It uses
  `arch.diagnostics` when not `None`, else `_empty_diagnostics()`, then
  appends the backend tag only if not already present in
  `diagnostics.warnings`.

- [x] AC11: A round-trip unit test asserts that `content_bounds` and
  `diagnostics.route_failures` from a synthetic `FinalizedLayout` survive
  `_finalized_to_arch` → `arch_to_finalized` unchanged.

- [x] AC12: A unit test exercises `_render_graph_fragment` directly with a
  `cls-dotted`-style edge and asserts the rendered path element contains
  `stroke-dasharray="6 4"`. This locks the function's raw-style behavior
  across the shared-resolver extraction. (`_render_graph_fragment` is
  currently reachable only via the uncalled `_layout_class` chain and direct
  tests — it is not on the live classDiagram render path, which goes through
  `render_finalized` after style normalization.)

- [x] AC13: `make eight-case-ci` passes with elkjs installed (same worktree,
  same backend). Zero regressions vs. `origin/main`.

## Deviations

- **AC12:** The locking test calls `_layout_class` (which routes through
  `_render_graph_fragment` internally) rather than `_render_graph_fragment`
  directly. The path is preserved; the only risk is if `_layout_class` stops
  delegating to the fragment painter, which would require a structural refactor
  of the class diagram strategy.

## Assumptions

- Technical: runtime is Python 3.13.x (probe: `python3 --version → Python 3.13.13`).
- Technical: `_render_graph_fragment` (line 132, `_renderer.py`) has no
  `faithful` parameter; three-branch stroke resolver at lines 597–626 duplicates
  `render_finalized` lines 1767–1779. (source: `scripts/mermaid_render/layout/_renderer.py`)
- Technical: `ArchitectureDiagramLayout` (lines 92–102) has no `diagnostics`
  or per-service `content_bounds` field; `arch_to_finalized` re-derives both
  at lines 1228–1232 and 1302–1309. (source: `scripts/mermaid_render/layout/architecture.py`)
- Technical: `_arch_fallback_to_finalized` (line 474) returns `FinalizedLayout`;
  `compile_architecture` must return `ArchitectureDiagramLayout` — type mismatch
  drives the ~80-line body duplication. (source: `scripts/mermaid_render/layout/architecture.py`)
- Technical: five tests call `_arch_fallback_to_finalized` directly (lines
  168, 173, 179, 184, 189). (source: `tests/test_architecture_elk_authoritative.py`)
- Process: eight-case CI gate must stay green; elkjs-installed same-worktree
  diff is the required verification. (source: `AGENTS.md` line 21; user confirmation 2026-07-24)
