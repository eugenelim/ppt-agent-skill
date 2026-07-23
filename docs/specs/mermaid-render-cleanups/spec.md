# Spec: mermaid-render-cleanups

- **Status:** Shipped

Mode: full (multi-item brief + cross-cutting internal-model refactor across 6
diagram families with silent-correctness risk).

Three self-contained cleanups in `scripts/mermaid_render/`, each an open
`docs/backlog.md` item:

1. `arrow-semantics-cleanup` — remove the legacy `arrow: bool` / `bidir: bool`
   fields from `_Edge`; derive them from the canonical `source_marker` /
   `target_marker` (`MarkerKind`) representation.
2. `backlog-mermaid-p0-label-width-cap` — apply `_est_label_w`'s 450px width cap
   to the `_make_text_layout_ir` label-layout path so long edge labels no longer
   diverge between routing and stored bounds.
3. `c4-icon-map-orphan` — remove the dead `_C4_ICON_MAP` from `_constants.py`.

## Objective

Close three backlog cleanups without changing rendered output (task 1 & 3 are
behaviour-preserving; task 2 is an intentional, snapshot-visible convergence for
labels >56 chars only). Leave the `_Edge` model with a single source of truth
for arrowhead semantics (the `MarkerSpec` markers).

## Background — the load-bearing finding (grounds the task premise)

The backlog claims `arrow`/`bidir` are "now derived from `source_marker` and
`target_marker`". Investigation shows this is **only partially true**: the
flowchart parser (`_parser.py:552-553`) keeps markers in sync, but several
**writers** set `arrow=`/`bidir=` and leave markers at their `NONE` default —
`statediagram.py:442`, the requirement parser (`_strategies.py:4376`), the two
architecture parsers (`_strategies.py:4043-4058`, `architecture.py:428-438`),
and the edge-copy sites (`_layered.py:193`, `_layout.py:143`). The ELK bridge
(`_strategies.py:5121`) reconciles the target end via a
`(ARROW if e.arrow else NONE)` fallback; the `_routing.py` Sugiyama path reads
`e.arrow` directly with **no** reconciliation.

Therefore removing the fields safely requires **(a) migrating those writers to
populate markers** and only then **(b) deriving the readers**. Reader-only
migration (the literal task wording) would silently drop arrowheads from state,
requirement, and architecture diagrams.

## Derivation contract (the canonical semantics)

`arrow` and `bidir` become read-only `@property` accessors on `_Edge`, backed by
a `_marker_kind()` coercion helper (markers may be `MarkerSpec`, bare
`MarkerKind`, `str`, or `None`):

- `arrow` ≡ `_marker_kind(target_marker) != MarkerKind.NONE`
  (a target-end arrowhead is present).
- `bidir` ≡ `_marker_kind(source_marker) == MarkerKind.ARROW and
  _marker_kind(target_marker) == MarkerKind.ARROW`
  (flowchart/arch `<-->`: arrowheads on **both** ends).

Faithfulness argued per family in `notes/derivation-analysis.md`. The one
reader that is not faithful under a target-only `arrow` is the class-diagram
marker gate (`_routing.py:814,818`), where `arrow` was always `True` (hardcoded
at construction) and served only as a redundant guard; the two `and e.arrow`
clauses are removed (equivalent, since class edges always set `arrow=True`).
The ELK-bridge fallback (`_strategies.py:5121`) collapses to `dst_mk = _tm_kind`
once writers populate `target_marker`.

## Acceptance Criteria

- [x] AC1: `_Edge` no longer defines `arrow` or `bidir` as stored fields; both
  are `@property` accessors deriving from the markers per the contract above.
  `arrow_src` remains absent.
- [x] AC2: No `_Edge(...)` construction — in `scripts/mermaid_render/` **or**
  `tests/` — passes `arrow=` or `bidir=` kwargs; every writer that previously
  encoded arrowhead intent via those kwargs now sets `source_marker` /
  `target_marker` consistently. (The known `tests/` construction sites are
  `test_mermaid_layout.py` — 8 flowchart edges — and `test_class_semantic.py`.)
- [x] AC3: Every reader of `.arrow` / `.bidir` / `getattr(e,"arrow"|"bidir")` /
  `spec.get("bidir")` resolves through the new properties or route-dict values;
  `paint.py` / `svg_serializer.py` continue to key rendering on the route-dict
  `ah` / `marker_id` / `bidir` values and `LayoutEdge` markers (no `_Edge`-field
  dependency). Behavioural tests asserting `e.arrow`/`e.bidir` on parser output
  (`test_syntax_flowchart.py`, `test_fix_flowchart.py`) stay green unmodified.
- [x] AC4: Across `scripts/mermaid_render/` and `tests/` (`--include='*.py'`),
  none of these match a residual field read or removed kwarg: `arrow=`/`bidir=`
  as an `_Edge(...)` kwarg; and every `\.arrow\b`/`\.bidir\b`,
  `getattr(...["']arrow`/`bidir`, `\.get\(["']arrow`/`bidir` hit outside
  `_constants.py` resolves to a property/route-dict access, not a stored field.
- [x] AC5: `_make_text_layout_ir` caps its width at 450px, matching
  `_est_label_w`; `_est_label_w`'s docstring no longer describes an uncapped
  divergence. Note: `_make_text_layout_ir` builds node/group IR too, so the cap
  intentionally bounds node/group label-driven widths (incl. otherwise-uncapped
  circle/diamond/hexagon shapes), not just edge labels — no fixture reaches
  450px, so no rendered output changes today.
- [x] AC6: `_C4_ICON_MAP` is removed from `_constants.py` (grep returns nothing).
- [x] AC7: The default (non-snapshot) `pytest tests/` suite passes (4591 passed,
  289 skipped). Snapshot suite (`--run-snapshots`, 192 items) shows **zero net
  drift** vs the pristine base — the identical 76 fixtures fail pre and post
  (pre-existing environment/baseline drift, not CI-gated per `tests.yml:79`).
  Task 2 needs no recapture: no snapshot fixture carries a label wide enough to
  reach the 450px cap (verified), so the cap changes no rendered output.
- [x] AC8: The three backlog sections are removed from `docs/backlog.md`.

## Testing Strategy

- **TDD/unit** for the derivation contract: a new test asserting `_Edge`
  property values for representative marker combinations (plain arrow, bidir,
  no-arrow, class aggregation source-only, class dependency target-only), added
  to `tests/test_mermaid_layout.py` (or a focused new module).
- **Goal-based** for tasks 2 & 3: label-cap unit test (long label →
  `_make_text_layout_ir(...).width == 450`) added near
  `test_edge_label_layout.py::TestEstLabelWidth`; grep assertion for `_C4_ICON_MAP`
  removal.
- **Regression oracle**: full default `pytest tests/` (browser/snapshot-free) is
  the primary behaviour oracle for the arrow migration; it
  exercises `_route_edges` / layout compilation directly. Snapshot suite is the
  pixel oracle where the environment allows (playwright + chromium confirmed
  available).

## Boundaries

- **In scope**: `_Edge` field removal + property derivation + `_marker_kind`
  helper; writer migration at every `_Edge(...)` site; the two `_routing.py`
  class-gate reader edits; the `_strategies.py:5121` fallback simplification;
  the label-cap one-liner; `_C4_ICON_MAP` removal; backlog edits.
- **Out of scope**: the P3 typed-transform work, class-compiler work, any
  broader marker-model refactor, `_LABEL_ICON_KEYWORDS`, and the pre-existing
  duplication of the two architecture / two class-edge construction paths (fixed
  for consistency but not consolidated).

## Assumptions

- Both architecture parsers and both class-edge builders are edited for
  consistency even if one is legacy/dead; snapshots + the default suite verify
  liveness.
- `MarkerKind` is `(str, Enum)`, so `_marker_kind` must test `isinstance(m,
  MarkerKind)` before `isinstance(m, str)`.
- No **production** `_Edge(...)` site relies on the old `arrow: bool = True`
  default without also setting markers (verified by census); removing the default
  flips such an edge to `arrow=False`. One **test** helper *did* rely on it —
  `tests/test_mermaid_layout.py:_make_simple_graph` (bare `_Edge("A","B")`,
  feeding `test_has_arrowhead_polygon`) — and was migrated to
  `target_marker=_ARROW_TGT`; the full-suite run surfaced it, confirming the
  oracle catches default-reliance.

## Declined temptations

- **A shared marker-model dataclass / registry** unifying `_Edge` and
  `LayoutEdge` markers — out of scope; this is a field-removal, not a model
  merge.
- **Consolidating the duplicate arch/class parser paths** — tempting while in
  the file, but a design call beyond the cleanup; left as-is (noted in
  Boundaries).
- **Making `arrow` "any marker present"** to avoid the two class-gate edits —
  declined; it muddies the ELK-bridge/ELK-route-dict target semantics. Target-
  only `arrow` + dropping the redundant class gate is the honest mapping.
