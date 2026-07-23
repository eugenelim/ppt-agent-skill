# Implementation Plan — ELK Finalized Layout Round-Trip

## Pre-mortem

**Assumption trio:**
1. Files I'll touch: `scripts/mermaid_render/layout/elk_adapter.py`, `scripts/mermaid_render/layout/_geometry.py`, `tests/test_elk_adapter.py`
2. Done when: `pytest tests/` passes; `pytest tests/test_elk_adapter.py -k roundtrip` is green; mypy reports 0 errors on touched files; no existing test regressions.
3. Not changing: `_strategies.py`, `_routing.py`, `_layout.py`, `errors.py`, the Python Sugiyama path, `_to_elk_json()`, renderer HTML generation.

**Declined patterns:**
- Tempted to move `ElkUnavailable` to `errors.py` alongside `NativeRenderError`; declining — `ElkUnavailable` is documented in the module docstring of `elk_adapter.py` and referenced in `ADR-001`; moving it would break the ADR contract and all call-sites without benefit.
- Tempted to add a `JunctionPoint` dataclass; declining — `Point` already exists; `junction_points: tuple[Point, ...]` on `RoutedEdge` is sufficient and keeps the type surface minimal.
- Tempted to infer rank by calling a separate topological sort; declining — ELK's y-positions (TB) or x-positions (LR) already encode layer order; clustering by coordinate gap is deterministic and zero-dependency.
- Tempted to extend `FinalizedLayout` to carry full ELK metadata; declining — `LayoutMetadata` already accompanies `FinalizedLayout` in `CompiledFlowchart`; adding fields there is the right seam.

---

## Tasks

### Task 1: Extend `RoutedEdge` with `junction_points` field
Depends on: none
Verification: TDD

**Tests:**
- `test_junction_points_default_empty`: construct a `RoutedEdge` without `junction_points`; assert `re.junction_points == ()`.
- `test_junction_points_preserved`: pass a synthetic ELK output with `"junctionPoints": [{"x": 50, "y": 80}]` on a section; call `_from_elk_result`; assert `routed_edges[0].junction_points == (Point(50.0, 80.0),)`.

**Approach:**
- In `_geometry.py`, add `junction_points: tuple[Point, ...] = ()` as the last field of `RoutedEdge` (after `target_marker`) so existing construction sites that don't pass it get the default.
- `RoutedEdge` is a frozen dataclass without `slots=True`, so adding a defaulted field at the end is backwards-compatible.
- In `_from_elk_result()` (elk_adapter.py line ~232 section loop): collect `section.get("junctionPoints", [])` into a `list[Point]`, deduplicate, and pass as `junction_points=tuple(jpts)` to the `RoutedEdge` constructor.

---

### Task 2: Fix `edge_style` — stop hardcoding `"solid"`
Depends on: none
Verification: TDD

**Tests (in `TestRoundTrip`):**
- `test_dotted_edge_style`: build a `LayoutGraph` with a `LayoutEdge(line_style="dotted")`; pass a synthetic ELK output; call `_from_elk_result`; assert `routed_edges[0].edge_style == "dotted"`.
- `test_thick_edge_style`: same for `"thick"`.
- `test_solid_edge_style_default`: `orig_edge` absent (unknown ELK edge id) → `edge_style` falls back to `"solid"`.

**Approach:**
- In `_from_elk_result()` at line 269, replace the literal `edge_style="solid"` with:
  ```python
  edge_style=orig_edge.line_style if orig_edge else "solid",
  ```
- No other files touched.

---

### Task 3: Fix `src_node_id` / `dst_node_id` — use semantic IDs from `orig_edge`
Depends on: none
Verification: TDD

**Tests (in `TestRoundTrip`):**
- `test_cross_hierarchy_semantic_ids`: build a graph where `LayoutEdge.sources=["A"]`, `LayoutEdge.targets=["B"]`, and a `source_port` value that differs from `"A"`; assert `routed_edges[0].src_node_id == "A"` and `dst_node_id == "B"`.

**Approach:**
- In `_from_elk_result()` lines 248–253, after `orig_edge` is retrieved, replace the multi-step fallback resolution with:
  ```python
  if orig_edge is not None:
      src_id = orig_edge.sources[0] if orig_edge.sources else src_ref
      dst_id = orig_edge.targets[0] if orig_edge.targets else dst_ref
  else:
      src_id = port_to_node.get(src_ref) or (src_ref.split(":")[0] if ":" in src_ref else src_ref)
      dst_id = port_to_node.get(dst_ref) or (dst_ref.split(":")[0] if ":" in dst_ref else dst_ref)
  ```
- Preserves the fallback for ELK-generated edges whose IDs don't match `edge_map`.

---

### Task 4: Populate `NodeLayout.ports` from ELK port output + `PortSpec`
Depends on: none
Verification: TDD

**Tests (in `TestRoundTrip`):**
- `test_fixed_port_sides`: build a `LayoutNode` with four `PortSpec` objects (NORTH/EAST/SOUTH/WEST, all `fixed_side=True`); include ELK-positioned port dicts on the node child; assert the resulting `NodeLayout.ports` has four entries with `PortSide.TOP`, `PortSide.RIGHT`, `PortSide.BOTTOM`, `PortSide.LEFT` respectively and `position` matching the ELK x/y (absolute-offsetted).
- `test_ports_empty_when_no_portspec`: `LayoutNode` with no ports → `NodeLayout.ports == ()`.

**Approach:**
- Add a module-level mapping in `elk_adapter.py`:
  ```python
  _ELK_SIDE_TO_PORT_SIDE: dict[str, PortSide] = {
      "NORTH": PortSide.TOP,
      "SOUTH": PortSide.BOTTOM,
      "EAST": PortSide.RIGHT,
      "WEST": PortSide.LEFT,
  }
  ```
- Build a `port_spec_map: dict[str, PortSpec] = {p.id: p for n in graph.nodes for p in n.ports}` before `_visit`.
- In `_visit`, when processing a node child, extract `child.get("ports", [])` from the ELK output. For each ELK port dict `ep`:
  - Look up `ps = port_spec_map.get(ep["id"])`.
  - If `ps` and `ps.fixed_side`: `side = _ELK_SIDE_TO_PORT_SIDE.get(ps.side, PortSide.AUTO)`.
  - Else: defer to Task 5 (tangent-based resolution); for now emit `PortSide.AUTO` as a placeholder.
  - Position: `Point(cx + float(ep.get("x", 0)), cy + float(ep.get("y", 0)))` (apply parent offset).
  - Direction: derive from side (RIGHT → `Point(1,0)`, LEFT → `Point(-1,0)`, TOP → `Point(0,-1)`, BOTTOM → `Point(0,1)`).
  - Construct `PortLayout(node_id=cid, side=side, position=pos, direction=dir)`.
- Assign `ports=tuple(port_layouts)` in `NodeLayout` constructor at line 197.

---

### Task 5: Resolve `PortLayout` direction and `src_port`/`dst_port` from route tangent
Depends on: Task 3 (semantic src/dst IDs needed to look up node positions)
Verification: TDD (mocked; isolation tier for real ELK tangents)

**Tests (in `TestRoundTrip`):**
- `test_src_port_direction_right_going_edge`: synthetic ELK output with `startPoint: {x:192, y:21}`, `bendPoints: [{x:250, y:21}]`; assert `src_port.direction.x > 0` and `src_port.side == PortSide.RIGHT`.
- `test_dst_port_direction_into_top`: synthetic ELK output ending with `endPoint` that approaches from above; assert `dst_port.side == PortSide.TOP` and `dst_port.direction.y < 0`.

**Approach:**
- Add helper `_tangent_to_side(dx: float, dy: float) -> PortSide` that maps the dominant axis and sign to a `PortSide`:
  ```python
  def _tangent_to_side(dx: float, dy: float) -> PortSide:
      if abs(dx) >= abs(dy):
          return PortSide.RIGHT if dx >= 0 else PortSide.LEFT
      return PortSide.BOTTOM if dy >= 0 else PortSide.TOP
  ```
- Add helper `_side_to_direction(side: PortSide) -> Point`:
  ```python
  _SIDE_DIR = {PortSide.RIGHT: Point(1,0), PortSide.LEFT: Point(-1,0),
               PortSide.BOTTOM: Point(0,1), PortSide.TOP: Point(0,-1)}
  ```
- In `_from_elk_result()`, after waypoints are built, compute:
  - `src_tangent`: direction from `waypoints[0]` to `waypoints[1]` (if len >= 2).
  - `dst_tangent`: direction from `waypoints[-2]` to `waypoints[-1]` (if len >= 2).
  - Use these to build `src_port` and `dst_port` with `_tangent_to_side` + `_side_to_direction`.
- For `NodeLayout.ports` with `PortSide.AUTO` from Task 4: after edge processing, back-fill AUTO ports whose PortSpec has `fixed_side=False` using the tangent of the edge that references that port ID. (First-pass: leave as AUTO; a follow-up post-process loop over `routed_edges` can back-fill `NodeLayout.ports` if needed — this is acceptable because `validate_finalized_layout` already raises an error on `PortSide.AUTO` in `RoutedEdge.src_port`/`dst_port`, not in `NodeLayout.ports`.)

---

### Task 6: Preserve `edge_style`, markers, and source/dest labels on `RoutedEdge`
Depends on: Task 2 (edge_style), Task 3 (orig_edge lookup), none for markers (already partially done)
Verification: TDD

**Tests (in `TestRoundTrip`):**
- `test_source_target_markers`: build a `LayoutEdge` with `source_marker=MarkerKind.DIAMOND`, `target_marker=MarkerKind.HOLLOW_TRIANGLE`; assert `routed_edges[0].source_marker == MarkerKind.DIAMOND` and `target_marker == MarkerKind.HOLLOW_TRIANGLE`. (Markers already flow through lines 257–258; test confirms no regression.)
- `test_src_dst_label_layout_none_when_no_elk_label`: `LayoutEdge` with empty `label`; ELK output has no `labels` array; assert `label_layout is None`, `src_label_layout is None`, `dst_label_layout is None`.

**Approach:**
- `source_marker` and `target_marker` already read from `orig_edge` (lines 257–258). Confirm no change needed; test documents the invariant.
- `src_label_layout` and `dst_label_layout`: ELK does not return source/destination sub-labels for flowchart edges; leave as `None` (accept this as an explicit gap — noted in spec).

---

### Task 7: Build `EdgeLabelLayout` from ELK edge label geometry
Depends on: Task 3
Verification: TDD

**Tests (in `TestRoundTrip`):**
- `test_labeled_edge_label_layout`: build a `LayoutEdge(label="deploys")` with ELK output including `"labels": [{"x": 110, "y": 90, "width": 60, "height": 14, "text": "deploys"}]`; assert `routed_edges[0].label_layout` is not `None`, `label_layout.text == "deploys"`, `label_layout.bounds.w == 60`, `label_layout.bounds.h == 14`.
- `test_labeled_edge_no_elk_label`: `LayoutEdge(label="deploys")` but ELK returns no `"labels"` array; assert `label_layout is None`.

**Approach:**
- In `_from_elk_result()` edge loop, after building `waypoints`, extract ELK label:
  ```python
  label_layout: Optional[EdgeLabelLayout] = None
  elk_labels = elk_edge.get("labels", [])
  if elk_labels and orig_edge and orig_edge.label:
      lbl = elk_labels[0]
      lx, ly, lw, lh = float(lbl.get("x", 0)), float(lbl.get("y", 0)), \
                        float(lbl.get("width", 0)), float(lbl.get("height", 0))
      midpoint = waypoints[len(waypoints) // 2] if waypoints else Point(lx, ly)
      label_layout = EdgeLabelLayout(
          text=orig_edge.label,
          layout=TextLayout(lines=(), width=lw, height=lh, line_height=14.0,
                            min_content_width=0.0, max_content_width=lw,
                            resolved_font_path=None, resolved_font_family="sans-serif"),
          bounds=Rect(x=lx, y=ly, w=lw, h=lh),
          anchor_point=midpoint,
      )
  ```
- Pass `label_layout=label_layout` to `RoutedEdge` constructor.

---

### Task 8: Build `GroupLayout.label_layout` from `LayoutGroup` label fields
Depends on: none
Verification: TDD

**Tests (in `TestRoundTrip`):**
- `test_group_label_layout_non_none`: build a `LayoutGraph` with a `LayoutGroup(label="Pipeline", label_width=72.0, label_height=18.0)`; assert `group_layouts["g"].label_layout is not None` and `label_layout.width == 72.0`, `label_layout.height == 18.0`.
- `test_empty_group_label_stays_none`: `LayoutGroup(label="")` → `label_layout is None`.

**Approach:**
- In `_visit()`, when processing a group child (line ~209), replace `label_layout=None` with:
  ```python
  group_label = None
  if g_orig.label:
      lw, lh = g_orig.label_width or 80.0, g_orig.label_height or 16.0
      group_label = TextLayout(
          lines=(), width=lw, height=lh, line_height=lh,
          min_content_width=0.0, max_content_width=lw,
          resolved_font_path=None, resolved_font_family="sans-serif",
      )
  ```
- Pass `label_layout=group_label` to `GroupLayout` constructor.

---

### Task 9: Reconstruct `NodeLayout.rank` from ELK layer coordinates
Depends on: none
Verification: TDD

**Tests (in `TestRoundTrip`):**
- `test_node_rank_tb_two_layers`: build a TB graph with two nodes at y=10 and y=200; assert `node_layouts["A"].rank == 1` and `node_layouts["B"].rank == 2`.
- `test_node_rank_lr_three_layers`: LR graph with three nodes at x=10, x=150, x=300; assert ranks 1, 2, 3.

**Approach:**
- After `_visit` completes, compute ranks:
  ```python
  if graph.direction in ("TB", "BT"):
      coord_key = lambda nl: nl.outer_bounds.y
  else:
      coord_key = lambda nl: nl.outer_bounds.x
  sorted_coords = sorted({coord_key(nl) for nl in node_layouts.values()})
  coord_to_rank = {c: i + 1 for i, c in enumerate(sorted_coords)}
  # Re-build node_layouts with rank set
  node_layouts = {
      nid: NodeLayout(**{**vars(nl), "rank": coord_to_rank[coord_key(nl)]})
      for nid, nl in node_layouts.items()
  }
  ```
  Note: `NodeLayout` is a frozen dataclass; use `dataclasses.replace(nl, rank=...)` instead of `**vars()`.

---

### Task 10: Extend `LayoutMetadata` with ELK provenance fields
Depends on: none
Verification: TDD

**Tests:**
- `test_layout_metadata_elk_fields`: call `layout_with_elk(graph)` with a mocked `_run_elk`; assert the returned `LayoutMetadata` has `backend="elkjs"`, `backend_version="0.12.0"`, `fallback_reason is None`, `elapsed_ms >= 0.0`, and `options_applied` contains `"elk.algorithm"`.
- `test_layout_metadata_defaults_compat`: construct `LayoutMetadata(direction="TB", node_count=1, group_count=0, edge_count=1, algorithm="ELK-layered")` without the new fields; assert construction succeeds (backwards compat via defaults).

**Approach:**
- In `_geometry.py`, add five fields to `LayoutMetadata` with defaults (placed after `algorithm` to preserve existing construction sites):
  ```python
  backend: str = ""
  backend_version: str = ""
  fallback_reason: Optional[str] = None
  elapsed_ms: float = 0.0
  options_applied: Mapping[str, str] = field(default_factory=dict)
  ```
  `LayoutMetadata` has `slots=True`; slots and `field(default_factory=...)` require `dataclasses.field`. Import `field` from `dataclasses` if not already present. Because `slots=True` is set, all fields with defaults must come after all fields without defaults — check ordering.
- In `layout_with_elk()` in `elk_adapter.py`: wrap the `_run_elk` call with `time.perf_counter()` to measure `elapsed_ms`. Build a `LayoutMetadata` and return it alongside `FinalizedLayout` — but `layout_with_elk` currently returns only `FinalizedLayout`. Options:
  - Change return type to `tuple[FinalizedLayout, LayoutMetadata]` — breaks callers.
  - Attach metadata to `FinalizedLayout` via a field — `FinalizedLayout` doesn't carry metadata.
  - Return `FinalizedLayout` unchanged; surface metadata via `CompiledFlowchart` at the `_compile_flowchart()` call site in `_strategies.py` — the right seam.
  - **Preferred**: add an optional `_elk_metadata: Optional[LayoutMetadata] = None` out-parameter pattern is not Pythonic. Instead, have `layout_with_elk` return a `tuple[FinalizedLayout, LayoutMetadata]` and update the single call site in `_strategies.py`. That call site already builds a `LayoutMetadata` from the ELK result; unifying is cleaner.
- Update `_strategies.py` call site to unpack the tuple and use the returned `LayoutMetadata` to populate `CompiledFlowchart.metadata`.

---

### Task 11: Round-trip test suite (`TestRoundTrip` in `tests/test_elk_adapter.py`)
Depends on: Tasks 1–9
Verification: `pytest tests/test_elk_adapter.py -k roundtrip` green

**Tests:**
- `test_fixed_port_sides` — AC1: four `PortSpec` (NORTH/EAST/SOUTH/WEST fixed) → four `PortLayout` (TOP/RIGHT/BOTTOM/LEFT).
- `test_dotted_and_thick_edges` — AC4: `line_style="dotted"` and `line_style="thick"` survive.
- `test_labeled_edge` — AC5: ELK label geometry → non-None `label_layout` with correct bounds.
- `test_source_target_markers` — AC6: `MarkerKind.DIAMOND` / `MarkerKind.HOLLOW_TRIANGLE` survive.
- `test_empty_and_nested_compounds` — AC7: empty group and nested group both get non-None `label_layout`; nested group boundary inside outer boundary.
- `test_cross_hierarchy_edges` — AC11: `src_node_id` / `dst_node_id` equal `LayoutEdge.sources[0]` / `LayoutEdge.targets[0]`, not a port ID.

**Approach:**
- Each test is self-contained: build `LayoutGraph`, build synthetic ELK output dict, call `_from_elk_result(out, graph)`, assert on the result.
- Use `@pytest.mark.isolation` only for the one test that requires actual ELK waypoints (AC3 direction tangent with real Node subprocess).
- No new fixtures needed; `_simple_graph()` helper already exists and can be extended.
