# C4 Layout Engine

- **Status:** Shipped

## Objective

Replace the C4 diagram renderer — which currently routes C4 through the generic
DAG rank-assign pipeline — with a dedicated C4 shelf/row packer that preserves
Mermaid declaration order, matching Mermaid 11.15's `Bounds.insert()` algorithm.

Root cause: `_layout_c4` calls `_graph_from_content_nodes()`, which runs
`_assign_ranks()` on relationship edges. For `user → webapp → email`, this
creates three vertical ranks instead of the required two-plus-one shelf layout.

## Boundaries

**Touches:** `_strategies.py`, new `_c4.py` (new module), tests.

**Does not touch:** `_constants.py` (`_Node` model unchanged), `_renderer.py`
(no shared C4 special cases), `_layout.py` (no DAG changes).

**Always do:**
- `_c4.py` must retain the Mermaid MIT license notice for the ported
  `Bounds.insert()` algorithm (Mermaid is MIT-licensed).
- C4 rendering must be fully self-contained in `_c4.py`; no C4 special-cases
  in the shared `_renderer.py`.

**Ask first:**
- Adding a `height` field to `_Node` in `_constants.py` (currently declined).
- Touching `_renderer.py` for C4-specific rendering.

## Acceptance Criteria

- [x] AC-1: `C4Bounds.insert()` pixel-exact packing — given `start_x=100,
  start_y=66, width_limit=832`, three boxes (first 216×134, rest 216×86) produce
  `(150,166)`, `(466,166)`, `(150,400)` (verified by unit test against the packer
  directly, not via HTML).
- [x] AC-2: Layout width is independent of `width_hint` — dispatching the c4-basic
  fixture at `width_hint=200` still places two boxes on row 1, not one per row.
- [x] AC-3: Person shape is rect — `data-node-id="user"` div has no `node-circle`
  class; width 216px and height 134px appear in its style.
- [x] AC-4: System shape is rect — system nodes are 216×86px.
- [x] AC-5: External element uses solid fill, not dashed border —
  `border:1.5px dashed` does not appear for `System_Ext` nodes.
- [x] AC-6: Relationships do not affect node placement — dispatching c4-basic with
  all `Rel(...)` lines removed produces the same node positions.
- [x] AC-7: Title parsed — `"System Context"` text appears in the rendered HTML.
- [x] AC-8: Internal element renders with standard card border (`border:1.5px solid`).
- [x] AC-9: All existing C4 smoke tests pass with updated expectations.

## Testing Strategy

**TDD** for AC-1 (`C4Bounds` packer — pure function).
**Goal-based** for AC-2 through AC-9 (HTML output assertions).
