# Spec: mermaid_layout.py — Test Suite, Icon Fix, and Architecture

**Mode:** Full (structural change — new test module; multi-file; public interface touched)
**Status:** Shipped
**Owner:** Eu Gene Lim
**Plan:** docs/specs/mermaid-layout-refactor/plan.md
**Constrained by:** none
**Contract:** none

## Objective

`scripts/mermaid_layout.py` has grown to 2,476 lines with no dedicated unit-test file. Tests are
either subprocess-only (`smoke_test.py`) or scattered in `scripts/test_diagram_qa.py`. This spec
covers three coordinated deliverables:

1. **Robust pytest unit-test suite** (`tests/test_mermaid_layout.py`) imported directly from the
   module — fast, isolated, no subprocess overhead.
2. **Flowchart icon bug fix** — when a flowchart node carries a `:::css_class` annotation whose
   name resolves to an icon asset, inject the icon SVG. Currently `flex-direction:row` is set on
   plain nodes (no icon, no tech label) but no icon is ever injected for generic flowchart syntax.
3. **AGENTS.md Python module conventions** — document the size-limit, private-symbol convention,
   test-location contract, and import pattern for internals so future contributors don't repeat
   the anti-patterns that created this situation.

## Problem statement

### Icon bug

`_render_graph_fragment` sets `icon_svg = _load_icon(n.icon) if n.icon else ""` (line 917).
For flowchart/graph/stateDiagram nodes, `n.icon` is **never set** — only architecture-beta and C4
parsers populate it. So `:::database`, `:::api`, `:::model`, etc. on a flowchart node produce zero
icon output, even though 94 SVG assets exist in `assets/icons/`.

Additionally, `_node_render_h` uses `n.icon` (field) to compute node height. It gives the wrong
height for flowchart nodes whose `css_class` resolves to an icon — the height is underestimated,
causing the group bounding box and LR pitch to be too small.

`flex_dir = "column" if tech_label else "row"` (line 958) gives plain nodes `flex-direction:row`.
This is semantically confusing even though it causes no visual regression.

### Test coverage gap

Zero unit tests cover: `_strip_frontmatter`, `_detect_directive`, `_parse_spec`,
`_parse_spec_and_class`, `_parse_graph_source`, `_break_cycles`, `_assign_ranks`,
`_minimize_crossings`, `_assign_coordinates`, `_arrowhead`, `_smooth_orthogonal_path`,
`_fan_offset`, `_route_edges`, and all T2/T3 strategy functions individually.

## Acceptance criteria

- [x] `tests/test_mermaid_layout.py` exists with ≥ 60 pytest tests (AC-TEST — 104 tests)
- [x] Tests cover: all parsing functions, rank assignment, crossing minimisation, coordinate
      assignment, edge routing, `_wrap_label`, `_node_render_h`, `_render_graph_fragment`,
      metadata/legend helpers, `_dispatch`, cap enforcement, error paths, and at least 10 of the
      17 directive strategies (AC-TEST-COVERAGE)
- [x] A flowchart node `A[Label]:::database` produces output containing `node-icon` span (AC-ICON-1)
- [x] A flowchart node `A[Label]:::api` produces output containing `node-icon` span (AC-ICON-2)
- [x] A flowchart node `A[Label]:::external` does NOT produce `node-icon` (AC-ICON-3)
- [x] A plain flowchart node `A[Label]` does NOT produce `node-icon` (AC-ICON-4)
- [x] `_node_render_h` returns a value > `NODE_H` for a node with `css_class="database"` and
      single-line label (AC-ICON-HEIGHT)
- [x] `flex_dir` for plain nodes (no icon, no tech_label) uses `column` not `row` (AC-FLEX)
- [x] All pre-existing tests continue to pass (AC-REGRESSION — 250 total)
- [x] Icon injection is intentional for ALL `css_class` values that resolve to an asset (AC-ICON-INTENT)
- [x] `python scripts/smoke_test.py --phase 2` exits 0 — 39/39 (AC-SMOKE; Phase 1 pre-existing
      failure is unrelated to mermaid_layout)
- [x] `docs/CONVENTIONS.md` contains `## Python module conventions`; `AGENTS.md` carries a
      one-line pointer (AC-AGENTS)

## Boundaries

**Always do:**
- `tests/test_mermaid_layout.py` (new file)
- `scripts/mermaid_layout.py` — the three targeted edits described in plan Task 2 only
- `docs/CONVENTIONS.md` — new Python module conventions section
- `AGENTS.md` — pointer to CONVENTIONS.md section (one line)

**Ask first:**
- Any edit to existing spec/strategy logic beyond the three icon edits
- Adding a new icon-resolution hook or mapping structure

**Never do:**
- Package split into `scripts/mermaid_layout/` — deferred (backlog: mermaid-layout-package-split)
- Edits to `scripts/smoke_test.py` or `scripts/test_diagram_qa.py`
- Adding a new pip dependency
- architecture-beta group layout changes

## Testing strategy

Mode: **TDD** for the icon fix (tests written red before any production change).
Mode: **Goal-based** for AGENTS.md (lint check: grep for the section heading).
Mode: **Goal-based** for the test suite itself (pytest count ≥ 60).

Import pattern (consistent with `tests/test_assemble_planning.py`):
```python
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from mermaid_layout import ...
```

## Assumptions

1. `assets/icons/database.svg` and `assets/icons/api.svg` exist and load non-empty SVG — verified
   by directory listing (94 icons present).
2. `css_class` values like "external" that have no icon asset correctly return `""` from
   `_load_icon`, making them safe to use as the lookup key.
3. The `sys.path.insert` pattern works without a conftest — confirmed by `test_assemble_planning.py`
   using the identical pattern.

## Declined

- **`_node_icon_name` helper function**: Tempted to extract a private `_node_icon_name(n)` helper
  shared by `_node_render_h` and `_render_graph_fragment`. Declining — the duplication is two
  identical one-liner expressions; a helper adds a non-obvious indirection for no compressibility
  gain given both call sites. If a third call site appears, add it then.
- **Backfilling `n.icon` at parse time**: Setting `n.icon = css_class` in `_ensure()` when
  `_load_icon(css_class)` resolves. Declining — it conflates icon rendering with CSS class semantics
  and breaks the invariant that `n.icon` is always an *explicit* icon declaration, not an inference.
