# Plan: mermaid_layout package split

**Status:** Done
**Spec:** docs/specs/mermaid-layout-package-split/spec.md

## Tasks

### T1 — Create package skeleton
**Depends on:** none
**Verification mode:** goal-based
**Done when:** `scripts/mermaid_layout/` directory exists; placeholder `__init__.py` present

**Approach:**
Create `scripts/mermaid_layout/` with an empty `__init__.py`. At this point the package
exists but imports nothing. Existing tests will fail until T8 populates `__init__.py` —
that's expected.

---

### T2 — Extract `_constants.py`
**Depends on:** T1
**Verification mode:** goal-based
**Done when:** `from mermaid_layout._constants import NODE_CAP, _Node, _node_render_h` works

**Approach:**
Copy from `mermaid_layout.py`:
- Lines ~27–85: icon loader (`_ICON_DIR`, `_icon_cache`, `_load_icon`)
- Lines ~87–161: caps, geometry, directive sets, icon maps (`_ARCH_ICON_MAP`, `_C4_ICON_MAP`), dataclasses (`_Node`, `_Edge`, `_Group`)
- Lines ~812–875: `_WRAP_CHARS` + measurement utilities (`_wrap_label`, `_node_render_h`)

Note: `_WRAP_CHARS` is at line 812 (between routing section end at 798 and `_wrap_label` at
815). `_NODE_CSS` is at line 802 — it belongs in `_renderer.py`, not here.

These three clusters go into `_constants.py` together to break the import cycle:
`_node_render_h` is needed by both `_routing.py` (lines 642/697/699/724/728) and `_layout.py`
(line 538) — placing it in `_renderer.py` would create `_renderer → _routing → _renderer`.

**Critical path fix:** `_ICON_DIR = Path(__file__).parent.parent / "assets" / "icons"` must
become `Path(__file__).parent.parent.parent / "assets" / "icons"` because `__file__` is now
`scripts/mermaid_layout/_constants.py` (one directory deeper than the original
`scripts/mermaid_layout.py`). Without this fix, icon loading silently returns empty strings.

Stdlib imports needed: `from __future__ import annotations`, `dataclasses`, `typing`,
`pathlib`, `re`.

---

### T3 — Extract `_parser.py`
**Depends on:** T2
**Verification mode:** goal-based
**Done when:** `from mermaid_layout._parser import _parse_graph_source` works

**Approach:**
Copy lines ~162–361. Add:
```python
from ._constants import _Node, _Edge, _Group, _GRAPH_DIRECTIVES, _KNOWN_DIRECTIVES
```
Plus stdlib imports (`re`, `from __future__ import annotations`).

---

### T4 — Extract `_layout.py`
**Depends on:** T2
**Verification mode:** goal-based
**Done when:** `from mermaid_layout._layout import _assign_ranks` works

**Approach:**
Copy lines ~362–545. Add:
```python
from ._constants import _Node, _Edge, NODE_CAP, EDGE_CAP, CROSSING_PASSES, _node_render_h, COL_GAP, RANK_GAP, CANVAS_PAD, NODE_W, NODE_H
```
Plus stdlib imports.

---

### T5 — Extract `_routing.py`
**Depends on:** T2
**Verification mode:** goal-based
**Done when:** `from mermaid_layout._routing import _route_edges` works

**Approach:**
Copy lines ~548–798. Add:
```python
from ._constants import _Node, _Edge, NODE_W, SELF_LOOP_DX, MIN_FAN_STEP, CANVAS_PAD, _node_render_h, _arrowhead
```
Wait — `_arrowhead` is *defined* in `_routing.py` (line 550) and called by `_route_edges`.
No import needed for it. Import list:
```python
from ._constants import _Node, _Edge, NODE_W, NODE_H, SELF_LOOP_DX, MIN_FAN_STEP, _node_render_h
```
Plus stdlib imports (`math`).

---

### T6 — Extract `_renderer.py`
**Depends on:** T2, T5
**Verification mode:** goal-based
**Done when:** `from mermaid_layout._renderer import _render_graph_fragment` works

**Approach:**
Copy lines ~800–1233 starting from `_NODE_CSS` (line 802, the shape→CSS map used only by
`_render_graph_fragment`), EXCLUDING `_WRAP_CHARS`, `_wrap_label`, `_node_render_h` which
moved to `_constants.py`. Add:
```python
from ._constants import (
    _Node, _Edge, _Group, NODE_W, NODE_H, RANK_GAP, COL_GAP, CANVAS_PAD,
    GROUP_CAP, GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT,
    _NODE_H_LINE, _NODE_H_ICON, _NODE_H_TECH,
    _load_icon, _wrap_label, _node_render_h,
)
from ._routing import _route_edges
```
Plus stdlib imports (`re`, `from html import escape as _h`).

Also copy `_separate_groups_lr` (lines ~1187–1233); it is called by `_layout_graph_topology`
in `_strategies.py`, but since it uses `_node_render_h` and `GROUP_PAD_*` constants, it
belongs in `_renderer.py`.

---

### T7 — Extract `_strategies.py`
**Depends on:** T2, T3, T4, T5, T6
**Verification mode:** goal-based
**Done when:** `from mermaid_layout._strategies import _dispatch` works

**Approach:**
Copy lines ~1237–2504. Add:
```python
from ._constants import (
    _Node, _Edge, _Group,
    NODE_CAP, EDGE_CAP, GROUP_CAP,
    NODE_W, NODE_H, COL_GAP, CANVAS_PAD,
    GROUP_PAD_X, GROUP_PAD_Y_TOP, GROUP_PAD_Y_BOT,
    _ARCH_ICON_MAP, _C4_ICON_MAP,
    _KNOWN_DIRECTIVES, _GRAPH_DIRECTIVES,
    _node_render_h, _wrap_label,
)
from ._parser import _parse_graph_source, _detect_directive, _strip_frontmatter
from ._layout import _break_cycles, _assign_ranks, _minimize_crossings, _assign_coordinates
from ._routing import _route_edges, _arrowhead
from ._renderer import (
    _render_graph_fragment,
    _extract_diagram_title, _render_metadata_chip, _render_legend, _separate_groups_lr,
)
```
Note: `_directive_content` is *defined* in `_strategies.py` (line 1320) — do NOT import it
from anywhere. `_graph_from_content_nodes` is also defined locally in `_strategies.py`.

Plus stdlib imports (`from __future__ import annotations`, `re`, `math`, `typing`, `from html import escape as _h`).

---

### T8 — Wire `__init__.py` re-exports
**Depends on:** T2, T3, T4, T5, T6, T7
**Verification mode:** goal-based
**Done when:** `from mermaid_layout import _dispatch, _Node, NODE_CAP, _node_render_h, _load_icon, _separate_groups_lr` all work

**Approach:**
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

---

### T9 — Create `__main__.py` CLI
**Depends on:** T8
**Verification mode:** visual / manual QA
**Done when:** `python3 scripts/mermaid_layout/ --source 'flowchart TB\nA-->B'` exits 0 and emits HTML

**Approach:**
Copy `main()` + `if __name__ == "__main__": main()` from lines 2506–2556. Add a `sys.path`
bootstrap before the import (relative imports fail when `__main__.py` is the top-level module):
```python
_pkg_parent = Path(__file__).parent.parent
if str(_pkg_parent) not in sys.path:
    sys.path.insert(0, str(_pkg_parent))
from mermaid_layout._strategies import _dispatch
```
Also import `argparse`, `sys`, `pathlib.Path`, `from __future__ import annotations`.

---

### T10 — Cut-over: delete monolith, fix all path consumers, update CONVENTIONS.md, run full suite
**Depends on:** T9
**Verification mode:** goal-based (full gate run)
**Done when:** `pytest tests/ -x -q` → 255 pass; `python3 scripts/smoke_test.py --phase 2` → 39 pass

**Approach:**
1. Delete `scripts/mermaid_layout.py`
2. Update `scripts/smoke_test.py:498`: `mermaid_layout.py` → `mermaid_layout`
3. Update `scripts/diagram_render_check.py:280`: `mermaid_layout.py` → `mermaid_layout`
4. Update `references/prompts/step4/tpl-page-orchestrator.md:56`: `mermaid_layout.py \` → `mermaid_layout \`
5. Update `docs/CONVENTIONS.md § Python module conventions`: remove `mermaid_layout.py` exception entry, add `_strategies.py` (~1,250 lines) as the new tracked exception
6. Run `pytest tests/ -x -q`
7. Run `python3 scripts/smoke_test.py --phase 2`

---

## Implementation order

T1 → T2 → T3, T4, T5 (independent; do sequentially to keep verifiable) → T6 → T7 → T8 → T9 → T10

## Key notes

- Python resolves `import mermaid_layout` to the package as soon as `scripts/mermaid_layout/__init__.py` exists, even while `scripts/mermaid_layout.py` is still present. Do not populate `__init__.py` until T8 so tests remain on the old file during T2–T7 individual verification steps.
- `_directive_content` (line 1320) is defined in `_strategies.py` — no import needed; do not add one.
- `_separate_groups_lr` goes in `_renderer.py` (not `_layout.py`) to avoid a `_layout → _renderer` dependency.
- After T10, `_strategies.py` will be the only file exceeding the 500-line target; it becomes the sole tracked exception in CONVENTIONS.md.
