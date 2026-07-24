# Plan: Architecture + Renderer Maintainability Cleanup

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Three sequential changes across two files. Task 1 is independent; Tasks 2
and 3 are sequenced (T3 extends the dataclass fields added in T2's extraction
and must update the same construction call-site). All changes are structural
only — no functional behaviour changes.

**Task 1 (`_renderer.py`):** Extract a module-level `_edge_stroke_attrs`
resolver. The dash derivation uses the superset form
(`style.endswith("-dotted")` in addition to exact `"dotted"`) to preserve
classDiagram `cls-dotted` dashed edges that the fragment painter produces.
Add a `faithful: bool = False` keyword argument to `_render_graph_fragment`.
Replace the inlined three-branch stroke/dash logic in both painters with a
single call. Remove the NOTE cross-reference comments.

**Task 2 (`architecture.py`):** Extract `_build_arch_layout`. The ~80-line
service-tile / junction / group-boundary / edge construction body (including
`_heuristic_arch_placement` and zoom computation) currently duplicated in
`_arch_fallback_to_finalized` (lines 489–611) and `compile_architecture`'s
fallback branch (lines 1026–1201) is moved into one module-private function.
Both callers shrink to a single `_build_arch_layout(...)` call. This
incidentally reduces the `seen_pairs` counter from two occurrences to one,
fixing the desync risk. Zoom is computed inside the function (it owns `canvas_w`)
— no zoom parameter is added.

**Task 3 (`architecture.py`):** Add `content_bounds: Optional[object] = None`
to `ArchServiceTile` and `diagnostics: Optional[object] = None` to
`ArchitectureDiagramLayout`. Update `_finalized_to_arch` to carry both fields
from the `FinalizedLayout`. Update `arch_to_finalized` to prefer the carried
values and use fixed-offset / empty-diagnostics fallbacks only when `None`.

Riskiest part: `arch_to_finalized`'s backend-tag deduplication guard (AC10) —
if `arch.diagnostics.warnings` already contains the tag from the ELK enrichment
step in `_arch_elk_to_finalized`, a naive `warnings + (arch.backend,)` would
double-add it.

## Constraints

- `docs/specs/eight-case-parity-ci-and-cleanup`: eight-case CI gate must stay
  green; no redesign of the ELK path.
- `docs/specs/architecture-fixed-port-integration`: `compile_architecture`
  public signature and return type (`ArchitectureDiagramLayout`) are frozen.
- All new helpers are module-private (leading underscore).

## Construction tests

**Integration tests:** `make eight-case-ci` (covers all three changed code
paths via the eight fixture matrix). Run after all three tasks.

**Manual verification:** none — all invariants are machine-checkable.

## Design (LLD)

### Design decisions

- **Return type of `_edge_stroke_attrs`:** `tuple[str, str, str]`
  (`stroke_color, stroke_w, dash`) — matches the local variables both painters
  already use, minimises the diff. Traces to: AC1–AC3.
- **`_build_arch_layout` return type:** `ArchitectureDiagramLayout` — allows
  `compile_architecture` to return it directly (no extra `arch_to_finalized`
  call on the fallback path). `_arch_fallback_to_finalized` applies
  `arch_to_finalized` on top, preserving its return type. Traces to: AC4–AC7.
- **Sentinel value `None` for new fields:** avoids importing `_empty_diagnostics`
  at module level (the lazy-import pattern in `architecture.py` is intentional).
  `arch_to_finalized` checks `is not None` before using the carried value.
  Traces to: AC8–AC10.
- **Backend-tag deduplication in `arch_to_finalized`:** check
  `arch.backend not in (arch.diagnostics.warnings or ())` before appending —
  prevents double-stamping on the ELK round-trip. Traces to: AC10.

### Data & schema

New fields appended at the END of frozen dataclasses (positional ordering
preserved for existing construction sites):

- `ArchServiceTile.content_bounds: Optional[object] = None`
- `ArchitectureDiagramLayout.diagnostics: Optional[object] = None`

`_build_arch_layout` leaves both as `None` (Python-fallback path). `arch_to_finalized`
applies the fixed-offset derivation when `content_bounds` is `None`, and
`_empty_diagnostics()` when `diagnostics` is `None`, then appends the backend tag.

## Tasks

### T1: Extract `_edge_stroke_attrs` resolver in `_renderer.py`

**Depends on:** none
**Touches:** `scripts/mermaid_render/layout/_renderer.py`, `tests/test_flowchart_arrow_conformance.py`

**Tests:**
- New unit test `test_edge_stroke_attrs_branches` covering 7 cases: style
  `"thick"` × `faithful=False/True`; style `"dotted"` × `faithful=False/True`;
  style `"solid"` × `faithful=False/True`; style `"cls-dotted"` × `faithful=False`
  (asserts `dash` is non-empty, exercising the superset `-dotted` branch).
  Asserts exact `(stroke_color, stroke_w, dash)` tuple per case. (AC1)
- New direct test of `_render_graph_fragment` with a `cls-dotted`-style edge;
  assert rendered SVG contains `stroke-dasharray="6 4"`. Locks raw-style
  behavior across the extraction (`_render_graph_fragment` is not on the live
  classDiagram render path; this is a behavioral lock, not production coverage).
  (AC12)
- Existing `tests/test_flowchart_arrow_conformance.py` passes unchanged. (AC1, AC2)
- `grep -n "renderer-two-paths" scripts/mermaid_render/layout/_renderer.py`
  returns zero matches. (AC3)

**Approach:**
- Define `_edge_stroke_attrs(edge_style: str, faithful: bool = False) -> tuple[str, str, str]`
  above `_render_graph_fragment` in `_renderer.py`.
  - `stroke_color`, `stroke_w`: three-branch `thick / dotted / else` with
    the `faithful` guard on color (from `render_finalized` lines 1767–1778).
  - `dash`: `' stroke-dasharray="6 4"' if edge_style == "dotted" or edge_style.endswith("-dotted") else ""`
    (superset; preserves `cls-dotted` dash that only the fragment painter produces).
- Add `*, faithful: bool = False` to `_render_graph_fragment`'s signature.
  Replace lines 597–610 with `stroke_color, stroke_w, dash = _edge_stroke_attrs(style, faithful)`.
- In `render_finalized`, replace lines 1767–1779 with
  `stroke_color, stroke_w, dash = _edge_stroke_attrs(re_obj.edge_style, faithful)`.
- Remove both NOTE cross-reference comments (lines ~589–596 in fragment,
  lines ~1762–1766 in `render_finalized`).

**Done when:** all unit tests pass; `make test` green; grep returns zero NOTE matches;
`cls-dotted` fragment test asserts `stroke-dasharray` present.

---

### T2: Extract `_build_arch_layout` in `architecture.py`

**Depends on:** none (independent of T1)
**Touches:** `scripts/mermaid_render/layout/architecture.py`, `tests/test_architecture_elk_authoritative.py`

**Tests:**
- Existing five tests calling `_arch_fallback_to_finalized` pass unchanged
  (lines 168, 173, 179, 184, 189 in `test_architecture_elk_authoritative.py`). (AC5)
- Existing `test_architecture_elk_authoritative.py` tests that monkeypatch
  `layout_with_elk` to raise `ElkUnavailable` and assert on
  `compile_architecture(COMPLEX_SRC, ...)` exercise the Python-fallback branch
  after the reduction and verify it still returns a valid `ArchitectureDiagramLayout`. (AC6)
- New unit test `test_build_arch_layout_duplicate_pair_edge_ids` creates nodes
  `A`, `B`, `C` with two `A->B` edges; asserts `_build_arch_layout` returns at
  least one `ArchEdge` with id `"A->B"` (second may be skipped if zero-length). (AC4, AC7)
- `grep -n "seen_pairs" scripts/mermaid_render/layout/architecture.py` returns
  exactly one match. (AC7)

**Approach:**
- Define `_build_arch_layout(nodes, edges, groups, *, width_hint=0, backend="python-fallback") -> "ArchitectureDiagramLayout":`
  between `_arch_fallback_to_finalized` and `_arch_elk_to_finalized` in `architecture.py`.
- Move the ENTIRE shared body from `_arch_fallback_to_finalized` (lines 489–610,
  minus the final `arch_to_finalized` call and return) into `_build_arch_layout`,
  including the `_heuristic_arch_placement` call and the zoom computation. The
  function owns `canvas_w` and computes `zoom` internally from `width_hint` —
  no zoom parameter is needed or safe (the caller never has `canvas_w`).
  Parameterise `backend` via the keyword argument.
- Reduce `_arch_fallback_to_finalized` to two lines: call
  `arch = _build_arch_layout(nodes, edges, groups, width_hint=width_hint, backend="python-fallback")`
  then `return arch_to_finalized(arch)`.
- Reduce `compile_architecture`'s Python-fallback branch (lines ~1025–1201) to:
  `return _build_arch_layout(nodes, edges, groups, width_hint=width_hint, backend=_backend)`.

**Done when:** all existing tests pass; grep returns exactly one `seen_pairs` match;
`_arch_fallback_to_finalized` body ≤ 5 lines; fallback branch in `compile_architecture`
≤ 5 lines after the reduction.

---

### T3: Carry `content_bounds` + `diagnostics` through `ArchitectureDiagramLayout`

**Depends on:** T2
**Touches:** `scripts/mermaid_render/layout/architecture.py`, `tests/test_architecture_elk_authoritative.py`

**Tests:**
- New round-trip unit test `test_arch_roundtrip_carries_content_bounds_and_diagnostics`:
  build a minimal synthetic `FinalizedLayout` with one node whose `content_bounds`
  differs from the fixed-offset derivation, and a `LayoutDiagnostics` with a
  non-empty `route_failures` tuple; pass through `_finalized_to_arch` then
  `arch_to_finalized`; assert the node's `content_bounds` matches the synthetic
  value and `diagnostics.route_failures` matches. (AC11)
- Additional dedup case in the same test (or a sibling): build a
  `FinalizedLayout` with `diagnostics.warnings = ("elk-js",)` and `backend="elk-js"`;
  assert that after `_finalized_to_arch` + `arch_to_finalized` the tag `"elk-js"`
  appears exactly once in `diagnostics.warnings`. (AC10)
- `grep -c "content_bounds" scripts/mermaid_render/layout/architecture.py` increases
  (verifies new field usage). (AC8, AC9)
- All existing architecture tests pass unchanged. (AC13)

**Approach:**
- Append `content_bounds: Optional[object] = None` to `ArchServiceTile` (after
  `accent_color`).
- Append `diagnostics: Optional[object] = None` to `ArchitectureDiagramLayout`
  (after `backend`).
- In `_finalized_to_arch`: update the `ArchServiceTile(...)` construction call to
  pass `content_bounds=nl.content_bounds`. Update the `ArchitectureDiagramLayout(...)`
  construction call to pass `diagnostics=fl.diagnostics`.
- In `arch_to_finalized`: for service nodes, replace the hardcoded
  `content_bounds=Rect(x=b.x+8, ...)` with:
  ```python
  content_bounds=(svc.content_bounds if svc.content_bounds is not None
                  else Rect(x=b.x+8.0, y=b.y+4.0,
                            w=float(max(b.w-16.0, 20.0)),
                            h=float(max(b.h-8.0, 10.0))))
  ```
  For diagnostics, replace `_empty_diagnostics()` base with:
  ```python
  diag = arch.diagnostics if arch.diagnostics is not None else _empty_diagnostics()
  if arch.backend and arch.backend not in (diag.warnings or ()):
      diag = LayoutDiagnostics(unsupported_options=diag.unsupported_options,
                               route_failures=diag.route_failures,
                               warnings=diag.warnings + (arch.backend,))
  ```
- Update `_build_arch_layout` (from T2) to accept `diagnostics=None` as a
  keyword argument and pass it through to `ArchitectureDiagramLayout`.
  Python-fallback callers leave it as `None`.

**Done when:** round-trip test passes; `make test` green; `make eight-case-ci` passes
with elkjs installed in same worktree. (AC13)

## Rollout

Pure in-process refactor; no infrastructure changes, no deployment sequencing,
no flags. Rollback is a revert — no data migrations or published contracts changed.

## Risks

- **Double backend-tag in diagnostics.warnings:** guarded by the `not in` check
  in `arch_to_finalized` (T3 Approach). Covered by the dedup assertion in the
  round-trip test (T3 Tests: synthetic `warnings=("elk-js",)` + `backend="elk-js"`
  → asserts exactly one occurrence after round-trip).
- **Zoom must survive the extraction:** `_build_arch_layout` computes zoom
  from `canvas_w` and `width_hint` internally and stores it in
  `ArchitectureDiagramLayout.zoom`. The field is consumed by downstream painters
  (`arch_to_finalized` passes it to `FinalizedLayout`). Verify by running the
  architecture fixture tests on both ELK and fallback lanes — zoom-related
  geometry must be unchanged.

## Changelog

- 2026-07-24: initial plan
