# Spec: mermaid_layout package split

**Mode:** Full (structural change — new module boundary; multiple sub-modules created)
**Status:** Shipped
**Owner:** Eu Gene Lim
**Plan:** docs/specs/mermaid-layout-package-split/plan.md
**Constrained by:** docs/CONVENTIONS.md § Python module conventions
**Contract:** none (stdlib only, no new pip dependencies)

## Objective

Split `scripts/mermaid_layout.py` (2,556 lines) into a proper Python package at
`scripts/mermaid_layout/` with six focused sub-modules. The driver is the
CONVENTIONS.md module-size limit (500 lines target; 800+ line tracked exception). The
test suite from the previous session (`tests/test_mermaid_layout.py`, 120 tests + 135
other tests = 255 total) acts as the safety net for this purely structural change.

**What changes:** file organisation only. No behaviour change, no symbol renames, no
API change.

## Problem statement

`scripts/mermaid_layout.py` is 2,556 lines — 5× the CONVENTIONS.md target. It mixes
seven logical concerns: constants/types, icon loading/measurement, parsing, layout
algorithms, edge routing, HTML rendering, and strategy dispatch. The test suite provides
the safety net to make this split safe.

## Acceptance criteria

- [x] `scripts/mermaid_layout/` package directory exists with `__init__.py`,
      `__main__.py`, and six sub-modules: `_constants.py`, `_parser.py`, `_layout.py`,
      `_routing.py`, `_renderer.py`, `_strategies.py` (AC-STRUCTURE)
- [x] Each sub-module is ≤ 800 lines, except `_strategies.py` (~1,250 lines, tracked
      exception documented in CONVENTIONS.md) (AC-SIZE)
- [x] `from mermaid_layout import _dispatch, _Node, NODE_CAP, ...` — all symbols currently
      importable from `mermaid_layout` remain importable via `__init__.py` re-exports
      (AC-COMPAT)
- [x] `pytest tests/ -x -q` → 255 tests pass (all tests, including the 120 mermaid layout
      unit tests) (AC-UNIT)
- [x] `python3 scripts/smoke_test.py --phase 2` → 39/39 pass (AC-SMOKE; also exercises
      `scripts/test_diagram_qa.py` imports)
- [x] `python3 scripts/mermaid_layout/ --source 'flowchart TB\nA-->B'` exits 0 and
      emits HTML (AC-CLI)
- [x] `scripts/mermaid_layout.py` is deleted (AC-CLEANUP)
- [x] All path-string consumers updated (smoke_test.py, diagram_render_check.py,
      tpl-page-orchestrator.md) from `mermaid_layout.py` → `mermaid_layout` (AC-CONSUMERS)
- [x] No circular imports between sub-modules (AC-NOCIRC)
- [x] `docs/CONVENTIONS.md § Python module conventions` updated: remove `mermaid_layout.py`
      exception, add `_strategies.py` as the new tracked exception (AC-CONVENTIONS)

## Boundaries

**Always do:**
- Create `scripts/mermaid_layout/` package with the six sub-modules + `__init__.py` +
  `__main__.py`
- Delete `scripts/mermaid_layout.py`
- Update path-string consumers:
  - `scripts/smoke_test.py`: `mermaid_layout.py` → `mermaid_layout`
  - `scripts/diagram_render_check.py`: `mermaid_layout.py` → `mermaid_layout`
  - `references/prompts/step4/tpl-page-orchestrator.md`: `mermaid_layout.py` → `mermaid_layout`
- Update `docs/CONVENTIONS.md` exception tracking

**Never do:**
- Rename any symbol (no `_` prefix removal, no rename for clarity)
- Change any function signature, constant value, or behaviour
- Move `tests/test_mermaid_layout.py` (stays in `tests/`)
- Add any new pip dependency

**Ask first:**
- Any edit beyond file reorganisation (logic changes, bug fixes, style passes)

## Module assignment and import DAG

The import DAG is acyclic. Each module only imports from modules earlier in this list.

**Key design constraint:** `_node_render_h` (which calls `_load_icon`) is needed by both
`_routing.py` (endpoint Y-coordinate calculation, lines 642/697/699/724/728) and
`_layout.py` (column height calculation, line 538). Placing it in `_renderer.py` would
create a cycle (`_renderer → _routing → _renderer`). Solution: move the shared
measurement cluster (`_load_icon`, `_wrap_label`, `_node_render_h`, `_ICON_DIR`,
`_icon_cache`) into `_constants.py`, which has no sibling dependencies.

```
_constants.py   ← no siblings (includes icon loader + measurement utils)
_parser.py      ← _constants
_layout.py      ← _constants
_routing.py     ← _constants
_renderer.py    ← _constants, _routing
_strategies.py  ← _constants, _parser, _layout, _routing, _renderer
```

### `_constants.py` (~190 lines)

- Caps: `NODE_CAP`, `EDGE_CAP`, `GROUP_CAP`, `CROSSING_PASSES`
- Geometry: `NODE_W`, `NODE_H`, `RANK_GAP`, `COL_GAP`, `CANVAS_PAD`, `GROUP_PAD_X`,
  `GROUP_PAD_Y_TOP`, `GROUP_PAD_Y_BOT`, `_NODE_H_LINE`, `_NODE_H_ICON`, `_NODE_H_TECH`,
  `SELF_LOOP_DX`, `MIN_FAN_STEP`
- Directive sets: `_GRAPH_DIRECTIVES`, `_KNOWN_DIRECTIVES`
- Icon maps: `_ARCH_ICON_MAP`, `_C4_ICON_MAP`
- Data types: `_Node`, `_Edge`, `_Group` (dataclasses)
- Icon loader: `_ICON_DIR`, `_icon_cache`, `_load_icon` (shared by routing + renderer)
- Measurement: `_WRAP_CHARS`, `_wrap_label`, `_node_render_h` (shared by layout + routing + renderer)

**Path fix required:** `_ICON_DIR` must change from `Path(__file__).parent.parent / "assets" / "icons"`
to `Path(__file__).parent.parent.parent / "assets" / "icons"` because `_constants.py` sits one
directory deeper than the original monolith. This is the single non-pure-copy change in the split
(structural necessity, not a logic change).

### `_parser.py` (~200 lines, from ~162–361)

- `_strip_frontmatter`, `_detect_directive`
- `_parse_spec`, `_parse_spec_and_class`, regex `_SPEC_RE`, `_SPEC_SHAPE_MAP`, `_CSS_CLASS_RE`
- `_parse_graph_source`, `_parse_line`, `_EDGE_RE`

### `_layout.py` (~185 lines, from ~362–545)

- `_break_cycles`, `_assign_ranks`, `_minimize_crossings`, `_assign_coordinates`

### `_routing.py` (~250 lines, from ~548–798)

- `_arrowhead`, `_smooth_orthogonal_path`, `_fan_offset`, `_route_edges`

### `_renderer.py` (~400 lines, from ~800–1233)

- `_NODE_CSS` (line 802 — shape → CSS border-radius map, used only by `_render_graph_fragment`)
- `_render_graph_fragment`
- `_DIRECTIVE_LABELS` (line 1049 — display names for diagram types, used by `_render_metadata_chip`)
- `_extract_diagram_title`, `_render_metadata_chip`, `_render_legend`
- `_separate_groups_lr`

(Icon loader, `_WRAP_CHARS`, and measurement utilities moved to `_constants.py` to break
the import cycle.)

### `_strategies.py` (~1,250 lines, from ~1235–2504)

**Tracked exception:** ~1,250 lines. One focused concern (diagram-type dispatch). Documented
in CONVENTIONS.md.

- `_directive_content` (shared helper, defined here, not imported from `_parser`)
- `_layout_graph_topology`
- `_layout_lifeline`, `_layout_er`, `_layout_class` (T2)
- `_graph_from_content_nodes` (shared helper)
- All T3 strategies: `_layout_gantt`, `_layout_timeline`, `_layout_quadrant`, `_layout_pie`,
  `_layout_xychart`, `_layout_mindmap`, `_layout_block`, `_layout_packet`, `_layout_kanban`,
  `_layout_architecture`, `_layout_c4`
- `_dispatch`

### `__init__.py`

Re-exports every symbol currently importable from `mermaid_layout`:

```python
from ._constants import (
    NODE_CAP, EDGE_CAP, NODE_W, NODE_H, COL_GAP,
    GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT,
    _Node, _Edge, _Group,
    _load_icon, _wrap_label, _node_render_h,
)
from ._parser import (
    _strip_frontmatter, _detect_directive, _parse_spec,
    _parse_spec_and_class, _parse_graph_source,
)
from ._layout import (
    _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates,
)
from ._routing import _arrowhead, _smooth_orthogonal_path, _fan_offset, _route_edges
from ._renderer import (
    _render_graph_fragment,
    _extract_diagram_title, _render_metadata_chip, _render_legend,
    _separate_groups_lr,
)
from ._strategies import _dispatch
```

### `__main__.py`

Contains `main()` and `if __name__ == "__main__": main()` — verbatim copy of the CLI
section from the monolith (lines 2506–2556), with two changes:

1. A `sys.path` bootstrap before the import:
   ```python
   _pkg_parent = Path(__file__).parent.parent
   if str(_pkg_parent) not in sys.path:
       sys.path.insert(0, str(_pkg_parent))
   ```
   Required because relative imports (`from . import _dispatch`) raise "attempted relative
   import with no known parent package" when `__main__.py` is the top-level module under
   `python3 scripts/mermaid_layout/`.

2. Absolute import after bootstrap: `from mermaid_layout._strategies import _dispatch`

## Path-string consumers

Three files hardcode the `.py` path and need updating when the monolith is deleted:

| File | Current path | Updated path |
|---|---|---|
| `scripts/smoke_test.py:498` | `ROOT / "scripts" / "mermaid_layout.py"` | `ROOT / "scripts" / "mermaid_layout"` |
| `scripts/diagram_render_check.py:280` | `ROOT / "scripts" / "mermaid_layout.py"` | `ROOT / "scripts" / "mermaid_layout"` |
| `references/prompts/step4/tpl-page-orchestrator.md:56` | `scripts/mermaid_layout.py \` | `scripts/mermaid_layout \` |

Import consumers (`scripts/test_diagram_qa.py`) require no changes — `from mermaid_layout
import ...` resolves to the package automatically.

## Testing strategy

All tests already exist. This is a pure safety-net run:

- **Verification mode:** goal-based — run `pytest tests/ -x -q` and
  `python3 scripts/smoke_test.py --phase 2` after the cut-over.
- No new test file needed.
- Existing `tests/test_mermaid_layout.py` uses `sys.path.insert(0, str(REPO_ROOT / "scripts"))`
  then `from mermaid_layout import ...` — this automatically resolves to the package once
  `scripts/mermaid_layout/` exists (Python prefers packages over same-named `.py` modules).

## Assumptions and risks

**Assumption trio:**
- The 255 pytest + 39 smoke tests cover enough of the API that a cut-paste split with only
  the `_ICON_DIR` path correction will pass without additional test authoring.
- Python's package-over-module resolution means the existing test `sys.path.insert` pattern
  works without changes once `__init__.py` is populated.
- All three path-string consumers (`smoke_test.py`, `diagram_render_check.py`,
  `tpl-page-orchestrator.md`) are the only places that invoke `mermaid_layout.py` as a
  filesystem path.

**Standalone-skill deployment:** the `_ICON_DIR` path fix (`parent.parent.parent`) also keeps
the icon loader correct when the skill is deployed as a standalone agent skill (where
`scripts/mermaid_layout/_constants.py` sits three levels above the skill root, not two).

**What we are not changing:** no function signatures, no constant values, no test file location.

**Declined-pattern register:**
- _Tempted to rename symbols (drop `_` prefix, rename for clarity) — declining; this is
  a pure structural move, API stays identical._
- _Tempted to introduce a `__all__` allowlist in `__init__.py` — declining; explicit
  re-imports of every symbol are safer, no accidental gaps._
- _Tempted to add a `_measure.py` or `_utils.py` module — declining; the six-module split
  from the backlog is the contract; the import cycle is resolved by moving measurement
  utilities into `_constants.py` instead._
- _Tempted to move topology-strategy logic into `_layout.py` — declining; coordinate-
  assignment (type-agnostic) stays in `_layout.py`; diagram-type dispatch stays in
  `_strategies.py`._
- _Tempted to fix COL_GAP or other diagram polish while touching the file — declining;
  separate concern, separate PR._

## Resolve-vs-surface disposition record

| Item | Resolution |
|---|---|
| Import cycle `_renderer ⇄ _routing` via `_node_render_h` | Resolved — move measurement cluster to `_constants.py`; DAG is acyclic |
| `tpl-page-orchestrator.md` path consumer | Resolved — added to AC-CONSUMERS and boundary list |
| `diagram_render_check.py` path consumer | Resolved — added to AC-CONSUMERS and boundary list |
| `test_diagram_qa.py` import consumer | Resolved — auto-resolves to package; covered by AC-SMOKE |
| AC-SIZE / `_strategies.py` ~1,250 lines | Resolved — AC-SIZE reworded to acknowledge tracked exception |
| CONVENTIONS.md stale exception entry | Resolved — AC-CONVENTIONS added; T10 extended |
| Status values | Resolved — spec: `Approved`, plan: `Drafting` |
