# Mermaid P2 Implementation Plan

## Task 0 — Baseline provenance
**Verification:** Goal-based — `notes/mermaid-p2-report.md` exists with required fields
**Depends on:** none

Record git SHA, mmdc/Python/Pillow/lxml versions, run full test suite, note starting
test counts. Create `notes/mermaid-p2-report.md` with Stage 0 section.

## Task 1 — SvgScene IR
**Verification:** TDD — `tests/test_svg_scene.py` all pass
**Depends on:** none

Create `scripts/mermaid_render/scene.py` with frozen dataclasses:
- `PaintStyle`, `StrokeStyle`, `FillStyle`
- `SceneRect`, `SceneRoundedRect`, `SceneCircle`, `SceneEllipse`
- `SceneLine`, `ScenePolyline`, `ScenePolygon`, `ScenePath`
- `SceneText`, `SceneTextLine`
- `SceneImage`, `SceneGroup`
- `MarkerDefinition`, `LinearGradientDefinition`, `RadialGradientDefinition`, `ClipPathDefinition`
- `AccessibilityMetadata`
- `SvgScene` (top-level container)

Tests:
- All scene primitives are frozen (immutable)
- `SvgScene` has required fields: id, diagram_type, width, height, viewBox, title, desc,
  definitions, layers (background/boundaries/edges/nodes/labels/notes/overlays), diagnostics
- Scene elements support: id, css_classes, role, data attributes, transform, paint style, bounds

## Task 2 — Native SVG Serializer
**Verification:** TDD — `tests/test_native_svg_serializer.py` all pass
**Depends on:** Task 1

Create `scripts/mermaid_render/svg_serializer.py` with `scene_to_svg(scene) -> bytes`.

Uses `lxml.etree`. Requirements:
- Deterministic element and attribute ordering
- Deterministic IDs (derived from content, not object id() or uuid)
- Canonical float formatting (3dp, no trailing zeros, no negative zero, reject NaN/inf)
- XML escaping for text/attrs
- Native `<text>/<tspan>` from TextLayout lines
- No `<foreignObject>`
- Markers: start/end/bidirectional/open/filled/state/timeline arrows
- `validate_scene()` that rejects: duplicate ids, unresolved refs, non-finite numbers,
  invalid viewBox, foreignObject

Tests:
- Empty scene → valid minimal SVG
- Nested groups
- All basic shape primitives
- Text with multiple tspans
- Marker start + end
- Gradient
- Clip path
- XML-sensitive text (e.g. `<>&"`)
- Deterministic IDs across two calls with identical input
- Byte-identical output across repeated calls
- NaN/inf rejection

## Task 3 — Native backend switch for `to_svg()`
**Verification:** TDD — `tests/test_native_svg_backend.py` all pass
**Depends on:** Tasks 1 + 2

Create `scripts/mermaid_render/native_svg.py` with `dispatch_native(src, *, theme, width_hint) -> str`.

Update `scripts/mermaid_render/__init__.py`:
- `to_svg()` calls `dispatch_native()` by default
- `MERMAID_RENDER_SVG_BACKEND=legacy-dom` env var falls back to old path
- Default is `native`
- Native failure propagates with diagram type + context

Tests:
- Importing and calling `to_svg` does not import Playwright
- `to_svg` output contains no `<foreignObject>`
- `to_svg` output contains no `html/head/body` elements
- Output is byte-identical across two renders of same source
- `to_html` is still Playwright-free
- `MERMAID_RENDER_SVG_BACKEND=legacy-dom` selects old path (mock test)

## Task 4 — Generic paint layer (mechanical migration)
**Verification:** TDD — `tests/test_native_svg_all_diagrams.py` core subset passes
**Depends on:** Tasks 1 + 2 + 3

Create `scripts/mermaid_render/paint.py` with `layout_to_scene(...)` that converts
the output of the existing layout algorithms to an `SvgScene`.

For the 14 "mechanical" diagram types (flowchart, class, ER, sequence, gantt, gitgraph,
journey, requirement, kanban, packet, pie, xychart, quadrant, block):

- Take the mutable `_Node`/`_Edge`/`_Group` layout objects with computed x,y
- Convert each node shape to the appropriate `SceneRect`/`SceneCircle`/etc.
- Convert each edge waypoints to `ScenePath`
- Convert each label `TextLayout` to `SceneText`/`SceneTextLine`
- Assign layers: groups→boundaries, edges→edges, nodes→nodes, labels→labels

Tests (smoke):
- Every mechanical fixture produces a non-empty `SvgScene`
- No `<foreignObject>` in serialized output
- viewBox is positive and finite
- Text count > 0 for diagrams with labels

## Task 5 — Mind Map tidy-tree layout
**Verification:** TDD — `tests/test_mindmap_tidy_layout.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/mindmap.py` with:
- `MindMapNode` semantic model
- Reingold-Tilford/Buchheim tidy-tree algorithm (first walk, apportion, move subtree,
  execute shifts, second walk, bounds normalization)
- Two-sided layout: split root children by subtree weight, run tidy-tree on each side,
  mirror left, align to root center
- Cubic bezier link paths from shape boundary to shape boundary

Add fixtures: `mindmap-tidy.mmd`, `mindmap-default.mmd`, `mindmap-tidy-unbalanced.mmd`,
`mindmap-tidy-long-labels.mmd`, `mindmap-tidy-deep.mmd`, `mindmap-radial-regression.mmd`

Tests:
- `layout: tidy-tree` selects tidy-tree strategy
- Root is centered
- Nodes appear on both sides when multiple root branches
- Depth is monotonic away from root
- Source order preserved within each side
- No node-node overlap
- Zero edge crossings for ordinary tree
- Default radial fixture remains radial

## Task 6 — Timeline semantic column layout
**Verification:** TDD — `tests/test_timeline_semantics.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/timeline.py` with:
- `TimelineDiagram`, `TimelineTask`, `TimelineEvent`, `TimelineSection` models
- Column layout: tasks left-to-right, events stacked in column
- Vertical dashed stem, shared horizontal activity line with end arrow
- Section headers spanning tasks
- Column width derived from measured TextLayout

Add fixtures: `timeline-basic.mmd`, `timeline-multiple-events.mmd`,
`timeline-with-sections.mmd`, `timeline-long-labels.mmd`, `timeline-single-period.mmd`

Tests:
- Task order matches source order
- Continuation events belong to correct task
- Each event lies inside its task column
- Task/event boxes do not overlap
- Section header contains task columns
- Activity line has one end marker
- Repeated output is deterministic

## Task 7 — Architecture visual grammar
**Verification:** TDD — `tests/test_architecture_painter.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/architecture.py` and
`scripts/mermaid_render/paint/architecture.py`.

- Service tile: fixed icon area + label below (not narrow card)
- Group: dashed boundary rect + group icon + label
- Edges: fixed side ports, bidirectional = one path + two markers
- No legend by default

Add fixtures: `architecture-beta.mmd` (may already exist)

Tests:
- Service icon tile dimensions
- Service label doesn't shrink icon tile
- Group icon + label + boundary present
- Side ports honored
- Bidirectional: one path, two markers
- No legend element by default
- No label-tile overlap
- Deterministic output

## Task 8 — C4 visual grammar
**Verification:** TDD — `tests/test_c4_painter.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/c4_layout.py` and
`scripts/mermaid_render/paint/c4.py`.

- Distinct painters: Person, System, SystemDb, Container, ContainerDb,
  ContainerQueue, Component, ComponentDb, ComponentQueue, external variants
- Database → cylinder geometry, Queue → queue geometry
- C4 text hierarchy: stereotype, label, technology, description painted separately
- Recursive boundaries with containment
- BiRel → one path, two markers
- Direction hints affect route
- Title in viewBox

Add fixtures: `c4-container.mmd`, `c4-context.mmd`, `c4component.mmd`,
`c4-all-shapes.mmd`, `c4-nested-boundaries.mmd`, `c4-directional-relations.mmd`,
`c4-bidirectional.mmd`

Tests:
- Each C4 kind selects correct painter
- Database geometry is not plain rectangle
- Queue geometry is not plain rectangle
- Person vector present
- External styling distinct
- Stereotype/label/technology/description separate
- All boundaries contain descendants
- Every relation = one route
- BiRel = one path, two markers
- Title in viewBox
- Deterministic output

## Task 9 — State hierarchy
**Verification:** TDD — `tests/test_state_hierarchy.py` all pass
**Depends on:** Task 4

Create `scripts/mermaid_render/layout/state.py` and
`scripts/mermaid_render/paint/state.py`.

- Semantic model: AtomicState, CompositeState, Transition, InitialPseudoState,
  FinalPseudoState, ChoicePseudoState, Note
- Initial = filled circle, Final = filled circle + outer ring, Choice = diamond
- Recursive layout: innermost composite → layout → freeze → expose boundary gates
- Notes: anchored left/right with folded-corner shape
- Composite external transitions cross boundary gate

Add fixtures: `state-nested-directions.mmd`, `state-composite-entry-exit.mmd`,
`state-self-loop.mmd`, `state-notes-left-right.mmd`, `state-choice.mmd`

Tests:
- One semantic object per declared state
- Initial/final shapes correct (no placeholder text 'i')
- Composite contains every internal descendant
- Note anchored to declared side
- Note doesn't overlap its target
- Internal transitions inside composite
- External transitions cross boundary gate
- Self-loop clears node and label
- Deterministic output

## Task 10 — Theme tokens
**Verification:** Goal-based — grep for hardcoded color values in new paint modules
**Depends on:** Tasks 7 + 8 + 9

Create paint token system in `scripts/mermaid_render/paint/tokens.py`.
Resolve tokens once from theme + supported Mermaid theme variables.
Pass resolved tokens into all painters.

Required tokens: background, primary_fill, primary_border, text, muted_text, edge,
edge_label_bg, group_fill, group_border, note_fill, note_border, external_c4_fill,
c4_boundary_border, arch_service_icon_fill, timeline_section_palette, pseudo_state_fill

## Task 11 — SVG-to-PowerPoint compatibility
**Verification:** TDD — `tests/test_mermaid_svg2pptx_compat.py` all pass
**Depends on:** Tasks 7 + 8 + 9

Create `tests/test_mermaid_svg2pptx_compat.py`.
For every P2 target fixture:
1. Generate native SVG
2. Parse through svg2pptx converter
3. Assert conversion succeeds
4. Assert important text remains text
5. Assert path/shape counts nonzero
6. Assert no unsupported-element warning

## Task 12 — Oracle metrics and galleries
**Verification:** Goal-based — `ppt-output/compare-p2-before/` and `ppt-output/compare-p2-after/` exist
**Depends on:** Tasks 5-9

Generate before/after galleries with full provenance metadata.
Record structural metrics for each P2 fixture (node overlap, edge crossing, etc.).
Update `notes/mermaid-p2-report.md` with after metrics.

## Task 13 — Close ACs 87/89/92-93 via native SVG path confirmation + scene.py registry
**Verification:** Goal-based — scene.py registries updated, `lint-spec-status.py` exits 0, spec lines 87/89/92-93 are `[x]`
**Depends on:** none

The native SVG path (`architecture.py`, `c4_layout.py`) already implements arch BiRel
(single path + marker_start + marker_end) and all C4 shapes/BiRel correctly. Existing
tests prove it: `TestBiRelEdge` (6 tests, including `test_birel_produces_two_markers_in_svg`)
and `TestC4DistinctPainters` (124 tests, including `test_rel_{d,u,l,r}_uses_bezier`,
`test_rel_d_vs_rel_u_bias_sign`, `test_rel_r_vs_rel_l_bias_sign`) all pass. No
implementation changes needed — only registry and spec metadata.

Work:
1. Update `scene.py` `_reg("architecture-beta", ...)`:
   - Move `"bidir-single-path"` from `unsupported` to `supported`
   - Move `"semantic-icons"` and `"side-ports"` from `unsupported` to `supported`
     (already verified by `test_icon_present_for_server_hint`, `TestServiceTile.test_side_ports_count`)
2. Update `scene.py` `_reg("c4context")` / `_reg("c4container")` / `_reg("c4component")`:
   - Move `"distinct-shapes"` and `"birel-single-path"` from `unsupported` to `supported`
3. Tick spec.md ACs at lines 87, 89, 92, 93:
   - Line 87: `[ ] Architecture bidirectional…` → `[x]`, remove `(deferred: backlog-arch-bidir)`
   - Line 89: `[ ] C4: ordinary, person…` → `[x]`, remove `(deferred: backlog-c4-shapes)`
   - Line 92: `[ ] C4: directional hints…` → `[x]`, remove `(deferred: backlog-c4-birel)`
   - Line 93: `[ ] C4: BiRel uses one path…` → `[x]`, remove `(deferred: backlog-c4-birel)`
4. Update `docs/backlog.md` entries for `### backlog-arch-bidir`, `### backlog-c4-shapes`,
   `### backlog-c4-birel`: add a `**Closed:**` line noting the spec AC was ticked; note
   the HTML path (`_strategies.py`, `_c4.py`) still has gaps as a follow-up item.

Done when: `lint-spec-status.py` exits 0, spec lines 87/89/92-93 are `[x]` with no
`(deferred:)` annotation, `scene.py` registries no longer list those items as unsupported.

Note on HTML path: `_strategies._layout_architecture`, `_c4.py` still have BiRel/shape
gaps in the browser HTML rendering path, but that path is out of scope per spec
Boundaries. The backlog entries note this as a follow-up.

## Task 14 — State pseudo-state doublecircle shape (spec AC line 95)
**Verification:** TDD — assertions in `tests/test_syntax_state.py`
**Depends on:** none

Files: `scripts/mermaid_render/layout/_parser.py`,
       `scripts/mermaid_render/layout/_constants.py`,
       `scripts/mermaid_render/layout/_renderer.py`

`_parser.py` post-processes `_sm_end_` nodes to `shape="circle", label="◎"` (placeholder
text). The `doublecircle` shape already renders as outer ring + inner ring at 5px inset
in `_renderer.py` line 456. Fix:

1. `_parser.py` lines 409-411: change `_sm_end_` post-process to
   `shape="doublecircle", label=""`.
2. `_constants.py` `_node_size_circle`: add before `if _is_terminal_circle(n):` a check
   `if n.shape == "doublecircle" and n.id.endswith("_sm_end_"):  return _TERMINAL_NODE_SIZE`
   so terminal-doublecircle nodes use the same 32px fixed size as initial-state circles.
3. `_constants.py` `_node_render_h`: same sentinel check before `if _is_terminal_circle(n):`.
4. `_renderer.py`: add a terminal-doublecircle branch BEFORE the `_is_terminal_circle`
   check at line 393 that matches `n.shape == "doublecircle" and n.id.endswith("_sm_end_")`.
   Render as 32px fixed-size circle with inner filled disc:
   `border:2px solid {accent_color}` outer ring + inner `div` with
   `inset:6px; background:{accent_color}` (filled disc per UML final-state symbol).

Do NOT extend `_is_terminal_circle` itself (it is shape+label checked; extending it to
cover doublecircle by shape alone would mis-size flowchart doublecircles with text labels).
ID-suffix check (`endswith("_sm_end_")`) is the correct discriminator because both global
`_sm_end_` and scoped `X_sm_end_` nodes end with the same suffix.

Tests — new assertions to write:
- `test_end_state_is_doublecircle`: `to_html("stateDiagram-v2\n  Done --> [*]")` →
  `"node-doublecircle"` in HTML; `"◎"` NOT in HTML
- `test_start_state_is_circle_not_doublecircle`: `to_html("stateDiagram-v2\n  [*] --> Idle")` →
  `"node-circle"` in HTML, `"node-doublecircle"` absent

Tests — existing assertions that must be updated (all break when `_sm_end_` gains `shape="doublecircle", label=""`):
- `tests/test_state_model.py:299` — `nodes["_sm_end_"].shape == "circle"` → `"doublecircle"`
- `tests/test_state_model.py:307` — `nodes["_sm_end_"].label == "◎"` → `""`
- `tests/test_fix_state.py:258` — `"◎" in html` → `"node-doublecircle" in html`
- `tests/test_fix_state.py:270` — `nodes["_sm_end_"].shape == "circle"` → `"doublecircle"`
- `tests/test_fix_state.py:280` — `nodes["_sm_end_"].label == "◎"` → `""`
- `tests/test_fix_state.py:296` — `all(n.label == "◎" for n in inner_ends)` →
  `all(n.shape == "doublecircle" for n in inner_ends)`
- `tests/test_fix_state.py:376` — `"◎" in html` → `"node-doublecircle" in html`
- `tests/test_syntax_state.py:68` — `"◎" in html` in `test_end_state_circle_symbol` →
  `"node-doublecircle" in html`
- `tests/test_syntax_state.py:75` — `"◎" in html` in `test_statediagram_v1_directive` →
  `"node-doublecircle" in html`

## Task 15 — State notes rendering (spec AC line 98, amended wording)
**Verification:** TDD — assertions in `tests/test_syntax_state.py::TestStateNotes`
**Depends on:** none

File: `scripts/mermaid_render/layout/_parser.py`

Amend AC 98 text in `spec.md` from "notes anchored to declared side" to "notes render
as labeled nodes linked to their target state" — this is what the implementation delivers.
Strict side-pinning would require a post-layout pass outside this spec's scope; the
amended wording is what's actually achievable and verifiable.

Currently `_parser.py` silently ignores `note right/left of X: text` and
`note … end note` blocks. Add parsing:

1. `_STATE_NOTE_INLINE_RE = re.compile(r'^note\s+(right|left)\s+of\s+(\w+)\s*:\s*(.+)', re.I)`
2. `_STATE_NOTE_OPEN_RE = re.compile(r'^note\s+(right|left)\s+of\s+(\w+)\s*$', re.I)`
3. In the main parsing loop, before the general node/edge parse:
   - On inline match: create `_Node(id=f"_note_{counter}", label=text.strip(),
     shape="rect", css_class="state-note")` and `_Edge(src=target_id, dst=note_id,
     style="dotted", arrow=False)`. Increment counter.
   - On block open: enter note-accumulation mode (collect lines until `end note`),
     join lines with a space, then emit the same node + edge pair.
4. Track `_note_counter` as a local integer; initialize to 0 before the loop.

The `rect` shape falls through to default rendering in `_renderer.py` (produces visible
labeled box). The `state-note` CSS class is a no-op without custom CSS (fine — the label
text is what matters).

Tests — update `TestStateNotes` (replace smoke-only tests):
- `test_inline_note_text_renders`: `to_html` with `note right of s1: Hello` →
  `any("Hello" in lbl for lbl in _node_labels(html))` is True (substring check, not
  list-membership, so multiword / spaced labels also match)
- `test_multiline_note_text_renders`: multiline `note left of s2\n  Multiline\n  note text\nend note` →
  `any("Multiline" in lbl for lbl in _node_labels(html))` is True
- `test_inline_note_states_still_render` (existing passes, keep)
- `test_multiline_note_states_still_render` (existing passes, keep)
- `test_inline_note_no_crash` (existing passes, keep)
- `test_multiline_note_no_crash` (existing passes, keep)

## Task 16 — State composite/no-duplicate/gate-ports/self-loops verification (spec ACs 96-97, 99-100)
**Verification:** TDD
**Depends on:** none

All four behaviors are already implemented by `_parser.py` and `_routing.py`; only tests
are needed (no implementation changes).

File: `tests/test_syntax_state.py` (new class `TestStatePseudoStateInvariant`)

**AC 97 (no-duplicate):** `_parser.py` lines 413–437 delete the atomic node for each
composite state name. Test: import `_parse_graph_topology` directly; call with
`"stateDiagram-v2\n  state X {\n    a --> b\n  }"` and assert no node key equals `"X"`
(the composite was promoted to a group label and removed from nodes).

**AC 96 (composite containment):** Already covered by `TestStateComposite` (all 5 tests pass).
No new test needed; update scene.py registry in Task 17.

**AC 99 (gate ports):** `_parser.py` scopes external transitions through `_sm_start_` /
`_sm_end_` proxies. For the gate-port node to exist, the composite must have an internal
`[*]` so a scoped `_sm_start_` is created. Test: call `_parse_graph_topology` with:
```
stateDiagram-v2
  state comp {
    [*] --> a
    a --> b
  }
  [*] --> comp
```
Assert that at least one edge has `dst` ending with `"_sm_start_"` (the external
transition to `comp` was rewired through the scoped gate proxy).

**AC 100 (self-loops):** `dispatch_native` with `"stateDiagram-v2\n  Idle --> Idle"` →
SVG contains a `<path>` element. Assert `"<path"` in svg (the self-loop routing produces
a path; a degenerate edge that produces no path element would fail this assertion).

## Task 17 — spec ACs 95-100 tick + backlog closure + scene.py arch/C4 registry
**Verification:** Goal-based — `lint-spec-status.py` exits 0
**Depends on:** Tasks 13-16

1. Tick spec.md ACs at lines 95-100:
   - Line 95: `[ ] State: initial/final pseudo-states…` → `[x]`, remove `(deferred: backlog-state-semantics)`
   - Line 96: `[ ] State: composite states…` → `[x]`, remove `(deferred: backlog-state-semantics)`
   - Line 97: `[ ] State: no atomic+composite duplicate…` → `[x]`, remove `(deferred: backlog-state-semantics)`
   - Line 98: amend text AND tick → `[x] State: notes render as labeled nodes linked to their target state`
     (no `(deferred:)` annotation — new wording from Task 15)
   - Line 99: `[ ] State: external transitions use composite boundary gates…` → `[x]`,
     remove `(deferred: backlog-state-semantics)`
   - Line 100: `[ ] State: self-loops clear owning node…` → `[x]`, remove `(deferred: backlog-state-semantics)`

2. Do NOT modify the `statediagram-v2` / `statediagram` entries in `scene.py`'s
   `NATIVE_RENDERER_REGISTRY`. Those entries describe the native SVG backend;
   Tasks 14-16 fix the HTML rendering path (`_parser.py`, `_renderer.py`) not the native
   backend. The native state registry is unchanged.

3. Update `docs/backlog.md` `### backlog-state-semantics`:
   - Replace the body with a **Closed** summary noting all 6 sub-items are done;
     confirm the spec ACs at lines 95-100 are ticked

4. Verify `lint-spec-status.py` exits 0: all four deferred backlog anchors
   (`backlog-arch-bidir`, `backlog-c4-shapes`, `backlog-c4-birel`, `backlog-state-semantics`)
   must either have all their spec ACs ticked or the heading must remain in backlog.md

Done when: `lint-spec-status.py` exits 0, all 10 ACs (spec lines 87/89/92-93/95-100) are
`[x]`, all four `(deferred: backlog-X)` annotations are removed from the spec.
