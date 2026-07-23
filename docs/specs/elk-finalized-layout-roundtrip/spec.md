# ELK Finalized Layout Round-Trip

Mode: full (structural change, unfamiliar territory)

- **Status:** Shipped

## Objective

Make `scripts/mermaid_render/layout/elk_adapter.py` perform a lossless-enough
round trip from `LayoutGraph` → ELK JSON → `FinalizedLayout`.

The ELK adapter currently drops significant information on deserialization.
`_from_elk_result()` hardcodes `PortSide.BOTTOM` for every source port and
`PortSide.TOP` for every destination port, discards `edge_style`, sets every
`RoutedEdge.label_layout` to `None`, leaves all `NodeLayout.ports` empty,
and sets `GroupLayout.label_layout` to `None`.  As a result, a `FinalizedLayout`
produced via the ELK path is materially different from one produced via the
Python Sugiyama path for the same `LayoutGraph`, and the renderer cannot
consistently apply dotted strokes, correct port directions, or edge labels.

The fix is to complete the existing adapter — not replace ELK.  Every field
that can be preserved from the input `LayoutGraph` or recovered from the ELK
output must be recovered; remaining gaps are noted as explicitly accepted
losses.

**Constrained by:** `docs/adr/001-elk-layout-engine.md` — ELK is optional;
Python Sugiyama remains the mandatory fallback.  Tests that exercise actual
ELK subprocess output are `@requires_elk` and skip when Node / elkjs is absent.

## Boundaries

**Files touched:**
- `scripts/mermaid_render/layout/elk_adapter.py` — primary target; all changes to `_from_elk_result()` and `layout_with_elk()`
- `scripts/mermaid_render/layout/_geometry.py` — extend `LayoutMetadata` with `backend`, `backend_version`, `fallback_reason`, `elapsed_ms`, `options_applied`; add optional `junction_points` field to `RoutedEdge`
- `tests/test_elk_adapter.py` — new round-trip test class

**Not changing:**
- The Python Sugiyama fallback path (`_strategies.py`, `_routing.py`, `_layout.py`)
- `_to_elk_json()` — serialization direction already correct
- `errors.py` — `ElkUnavailable` already lives in `elk_adapter.py`; no migration needed
- Renderer HTML generation
- Any other layout adapter or compiler

## Acceptance Criteria

- [ ] **AC1 — Fixed port side survives deserialization**: A `LayoutNode` with a `PortSpec(side="EAST", fixed_side=True)` produces a `NodeLayout.ports` entry with `PortSide.RIGHT` after `_from_elk_result()` runs. Likewise for WEST→LEFT, NORTH→TOP, SOUTH→BOTTOM. No fixed port is mapped to AUTO.

- [ ] **AC2 — Automatic port side resolved from route tangent**: A `LayoutNode` whose port has `fixed_side=False` (i.e., `PortSpec` with `fixed_side=False`) receives a `PortSide` in the resulting `NodeLayout.ports` that matches the face closest to the first/last route segment tangent (not hardcoded BOTTOM/TOP).

- [ ] **AC3 — PortLayout.direction from tangent, not hardcoded**: `RoutedEdge.src_port.direction` and `RoutedEdge.dst_port.direction` reflect the actual first and last segment tangent unit vectors respectively; they are not always `Point(0.0, 1.0)` / `Point(0.0, -1.0)`.

- [ ] **AC4 — Edge style preserved**: A `LayoutEdge` with `line_style="dotted"` produces `RoutedEdge.edge_style="dotted"`. A `LayoutEdge` with `line_style="thick"` produces `RoutedEdge.edge_style="thick"`. The literal `edge_style="solid"` is no longer hardcoded in `_from_elk_result()`.

- [ ] **AC5 — Edge labels survive round trip**: A `LayoutEdge` with a non-empty `label` and ELK-returned label geometry (`labels[0].x/y/width/height`) produces a non-`None` `RoutedEdge.label_layout` with `bounds` derived from ELK label coordinates. If ELK returns no label geometry, `label_layout` remains `None`.

- [ ] **AC6 — Source and target markers preserved**: `RoutedEdge.source_marker` and `RoutedEdge.target_marker` match the corresponding `LayoutEdge.source_marker` / `LayoutEdge.target_marker` for every edge, including `MarkerKind.NONE`, `ARROW`, `DIAMOND`, and `HOLLOW_TRIANGLE`.

- [ ] **AC7 — Group label represented**: A `LayoutGroup` with a non-empty `label` produces a `GroupLayout.label_layout` that is not `None`; the `TextLayout` has `width` and `height` taken from `LayoutGroup.label_width` / `LayoutGroup.label_height`.

- [ ] **AC8 — Node rank reconstructed**: `NodeLayout.rank` is set to a non-zero integer for nodes in a multi-layer graph; the value equals the 1-based layer index reconstructed from ELK's y-positions (TB/BT) or x-positions (LR/RL) via a clustering threshold.

- [ ] **AC9 — Junction points retained**: When ELK returns `junctionPoints` on an edge section, those points are stored in `RoutedEdge.junction_points`; the field exists on `RoutedEdge` (defaulting to an empty tuple for non-ELK edges).

- [ ] **AC10 — Multiple ELK sections joined deterministically**: When an edge has more than one section in the ELK output, all sections are concatenated in order (start → bends → end of section N, then start of section N+1 is de-duped against end of section N) to produce a single `waypoints` tuple with no duplicate consecutive points.

- [ ] **AC11 — Original semantic source/destination IDs preserved**: `RoutedEdge.src_node_id` and `RoutedEdge.dst_node_id` equal the first element of `LayoutEdge.sources` and `LayoutEdge.targets` (the caller's semantic IDs) when `orig_edge` is present, not a port ID or split artifact.

- [ ] **AC12 — LayoutMetadata extended**: `LayoutMetadata` gains fields `backend: str`, `backend_version: str`, `fallback_reason: Optional[str]`, `elapsed_ms: float`, `options_applied: Mapping[str, str]`. `layout_with_elk()` populates them (`backend="elkjs"`, `backend_version="0.12.0"`, `elapsed_ms` from wall-clock, `options_applied` from the `layoutOptions` sent to ELK, `fallback_reason=None` on success). Existing `LayoutMetadata` construction sites that omit the new fields use sensible defaults.

- [ ] **AC13 — No successful ELK result re-routed**: Once `layout_with_elk()` returns a `FinalizedLayout`, no subsequent call to the Python Sugiyama router is made on the same graph unless the caller explicitly requests a typed repair pass. The ELK result is authoritative.

- [ ] **AC14 — Round-trip test suite green**: `pytest tests/test_elk_adapter.py -k roundtrip` passes with the following test coverage: fixed left/right/top/bottom ports; dotted and thick edges; labeled edges; source and target markers; empty and nested compound groups; cross-hierarchy edges.

## Testing Strategy

**Test tier:** Mocked-subprocess (fast, default tier) for all structural round-trip assertions; real-subprocess (`@pytest.mark.isolation`) only for AC3 tangent direction, where actual ELK waypoints are required.

**Construction pattern:** Each round-trip test builds a `LayoutGraph` with the property under test, constructs a synthetic ELK output dict that mirrors what ELK would produce (valid sections, optional labels/junctionPoints), calls `_from_elk_result(out, graph)` directly, and asserts on the resulting `FinalizedLayout` fields.

Tests live in `tests/test_elk_adapter.py` in a new class `TestRoundTrip`.

The six fixture scenarios map directly to AC1/AC2, AC4, AC5, AC6, AC7, AC9, AC14:
1. `test_fixed_port_sides` — NORTH/EAST/SOUTH/WEST → TOP/RIGHT/BOTTOM/LEFT (AC1)
2. `test_dotted_and_thick_edges` — line_style preserved (AC4)
3. `test_labeled_edge` — label_layout non-None when ELK returns label geometry (AC5)
4. `test_source_target_markers` — MarkerKind values round-trip (AC6)
5. `test_empty_and_nested_compounds` — GroupLayout.label_layout non-None; nested group boundary inside outer (AC7)
6. `test_cross_hierarchy_edges` — src_node_id / dst_node_id equal semantic source/target, not port IDs (AC11)
