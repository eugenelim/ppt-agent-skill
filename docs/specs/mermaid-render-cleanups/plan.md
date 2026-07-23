# Plan: mermaid-render-cleanups

- **Status:** Done

Work-breakdown for the three cleanups. Tasks are ordered; T1 is the large one.
Each is committed separately (T3 and T1 both touch `_constants.py`; T2 touches
`_strategies.py` which T1 also edits — sequential, no parallel fan-out).

Files touched: `layout/_constants.py`, `layout/_routing.py`,
`layout/_strategies.py`, `layout/_parser.py`, `layout/_layered.py`,
`layout/_layout.py`, `layout/statediagram.py`, `layout/er.py`,
`layout/architecture.py`, `native_svg.py`, plus tests and `docs/backlog.md`.

Verification mode: **TDD** for the derivation contract (T1) and the label cap
(T2); **goal-based** (grep) for T3. Test runner (`pytest`) already wired.

---

## T1 — arrow-semantics-cleanup

Depends on: none

### Tests (write first, red)
- `tests/test_edge_marker_derivation.py` (new): construct `_Edge` instances and
  assert the property values —
  - plain arrow (`target=ARROW`, `source=NONE`) → `arrow True, bidir False`
  - bidir (`target=ARROW`, `source=ARROW`) → `arrow True, bidir True`
  - no-arrow (both `NONE`) → `arrow False, bidir False`
  - class aggregation (`source=AGGREGATION` spec, `target=NONE`) →
    `arrow False, bidir False`
  - class dependency (`target=TRIANGLE/dep` spec, `source=NONE`) →
    `arrow True, bidir False`
  - marker as bare `MarkerKind` and as `str` both coerce — helper robustness,
    mirroring the existing defensive `isinstance(m, str)` coercion at
    `_strategies.py:5119`/`4797` (markers are polymorphic across the pipeline).
- End-to-end regression: `pytest tests/` default suite green (behaviour oracle).
- **Test-site migration (in scope — else `pytest tests/` TypeErrors):** the
  `_Edge(arrow=/bidir=)` construction sites in `tests/test_mermaid_layout.py`
  (lines 1379, 1423-1424, 1759-1760, 2023, 2061-2062 — explicit `arrow=True`
  flowchart edges → set `target_marker=MarkerSpec(kind=MarkerKind.ARROW,
  end="TARGET")`; **plus** `_make_simple_graph` ~line 439, a bare `_Edge("A","B")`
  that relied on the old `arrow=True` default and now needs an explicit
  `target_marker`) and `tests/test_class_semantic.py` (363-364, 395-396 — class
  edges that already set markers → drop `arrow=True`). Parser-output assertion
  tests (`test_syntax_flowchart.py:116/137`, `test_fix_flowchart.py:79/83`) are
  verified to still pass unmodified (they read the new properties).

### Approach
1. Add `_marker_kind(m) -> MarkerKind` helper in `_constants.py` (MarkerKind →
   MarkerSpec.kind → str → NONE, MarkerKind-before-str ordering).
2. On `_Edge`: delete `arrow`/`bidir` fields; add `@property arrow`/`bidir` per
   the derivation contract.
3. Migrate writers (per `notes/derivation-analysis.md` table): drop `arrow=`/
   `bidir=` kwargs; add `source_marker`/`target_marker` where the kwarg carried
   intent; copy markers at the two edge-copy sites.
4. Migrate the two non-transparent readers: drop `and e.arrow` at
   `_routing.py:814,818`; simplify `_strategies.py:5121` to `dst_mk = _tm_kind`.
5. Add marker imports where writers need them (statediagram, the arch writer
   function in architecture.py).

### Done when
- AC1–AC4 hold; `pytest tests/` green; grep for `arrow=`/`bidir=` kwargs and
  `.arrow`/`.bidir` field reads is clean.

---

## T2 — backlog-mermaid-p0-label-width-cap

Depends on: none (independent; sequenced after T1 to avoid `_strategies.py`
churn overlap)

### Tests (write first, red)
- In `tests/test_edge_label_layout.py`: a long-label (>56 char) case asserting
  `_make_text_layout_ir(long).width == 450.0` and that it matches
  `_est_label_w(long)` (both capped).

### Approach
- In `_make_text_layout_ir` (`_strategies.py:4603`): cap
  `w = min(450.0, _estimate_text_width(text))`.
- Update `_est_label_w`'s docstring (`_routing.py:536-543`) to drop the
  "minor divergence … no cap" note.

### Done when
- AC5 holds; the new test passes; snapshot drift (if any) is limited to
  long-label node/edge widths and recaptured with justification.

---

## T3 — c4-icon-map-orphan

Depends on: none

### Tests
- Goal-based: `grep -rn '_C4_ICON_MAP' scripts/ tests/ --include='*.py'` returns
  nothing (`--include` avoids matching stale `__pycache__/*.pyc`); default suite
  still imports/loads `_constants.py` fine.

### Approach
- Delete the `_C4_ICON_MAP` dict block from `_constants.py` (lines ~59-70) and
  its lead comment.

### Done when
- AC6 holds; `pytest tests/` green.

---

## Finish
- Remove the three backlog sections (`arrow-semantics-cleanup`,
  `backlog-mermaid-p0-label-width-cap`, `c4-icon-map-orphan`) from
  `docs/backlog.md`; flip spec ACs to `[x]`, set status `Shipped`.
- `lint-spec-status.py`; adversarial + quality reviews; PR against `main`; merge
  on green CI.
