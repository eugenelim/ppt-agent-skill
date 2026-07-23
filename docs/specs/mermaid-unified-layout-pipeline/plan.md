# Plan: mermaid-unified-layout-pipeline

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

The pipeline has three distinct seams today:
1. Parse → mutable `_Node/_Edge/_Group` (layout engine input)
2. `_compile_flowchart()` → `FinalizedLayout` (layout engine output, shared)
3. `FinalizedLayout` → HTML fragment OR SvgScene (painter, already separated)

The refactor adds a seam between 1 and 2: a **pre-layout IR** (`LayoutGraph`)
that captures measured node sizes, group hierarchies, edge semantics, and port
specs. This IR passes to ELK (elkjs 0.12.0 via a pinned Node subprocess); ELK
returns positioned coordinates that populate `FinalizedLayout`. The existing
Python Sugiyama + A\* stays as the explicit fallback.

Task order respects hard dependencies:
- T0 (ADR) → must land before any code change
- T1 (IR types) → foundation for T3 and T4
- T2 (ShapeGeometry) → depends on T1; feeds T5 (connector clipping on fallback path)
- T3 (arrow semantics) → depends on T1; feeds T5
- T4 (ELK adapter) → depends on T1; feeds T5
- T5 (pipeline wire-up) → depends on T2 + T3 + T4
- T6 (faithful mode) → depends on T5
- T7 (validation) → depends on T5
- T8a (snapshot regen) → depends on T5
- T8b (integration verification) → depends on T6 + T7

The riskiest task is T5: touching `_compile_flowchart` in the 5,430-line
`_strategies.py`. The mitigation is that T5 only adds a new early-exit path
(ELK success) before the existing Python pipeline; the Python path is
untouched, so fallback mode is bit-for-bit identical to today.

**Note on `_strategies.py` size:** `docs/backlog.md#strategies-module-split`
tracks splitting this into `_pipeline.py`/`_diagram_types.py`. T5-T6 touch it
but do not perform the split — deferred to avoid extra scope. The stale
CONVENTIONS path (`mermaid_layout/` → now `mermaid_render/`) should be fixed
in the split task.

## Constraints

- **ADR-001** (`docs/adr/001-elk-layout-engine.md`): governs the elkjs + Node dependency decision
- **Override target:** `flowchart-pipeline-finish` spec pure-Python clause + `tests/test_dependencies.py::TestNoSubprocess`
- **Preserve:** Python Sugiyama + A\* as runnable fallback
- **Never:** ELK for non-graph-topology types

## Construction tests

**Cross-cutting integration test (T8b):** compile all 15 named fixtures end-to-end;
`validate_finalized_layout(strict=True)` must pass for the 10 graph-topology
fixtures; non-graph fixtures must produce non-empty SVG.

**Cross-path geometry comparison (T8b):** compile ≥ 1 graph-topology fixture
through both `to_html()` and `to_svg()`; assert node x/y/w/h within 0.5 px.

**Gate check after each task:** `pytest tests/ -x -q` must stay green before
the next task.

## Design (LLD)

### Pre-layout IR (LayoutGraph)

```
LayoutGraph
  nodes: list[LayoutNode]
  groups: list[LayoutGroup]
  edges: list[LayoutEdge]
  direction: str  # "TB" | "LR" | "BT" | "RL"

LayoutNode(id, measured_width, measured_height, shape_id, parent_id,
           ports: list[PortSpec], labels: list[str], semantic_data: dict)

LayoutGroup(id, parent_id, label, label_width, label_height, padding,
            local_direction, minimum_width, minimum_height)

PortSpec(id, node_id, side: str, index: int, fixed_side: bool, fixed_order: bool)

LayoutEdge(id, sources: list[str], targets: list[str],
           source_port, target_port,
           source_marker: MarkerKind, target_marker: MarkerKind,
           line_style: str, label: str, semantic_data: dict)
```

`MarkerKind` enum: `NONE | ARROW | OPEN_ARROW | DIAMOND | FILLED_DIAMOND | CIRCLE | CROSS | CROW_ONE | CROW_MANY | CROW_ZERO_ONE | CROW_ZERO_MANY`

### ELK serialisation

`LayoutGraph` → ELK JSON with:
- `elk.algorithm: layered`, `elk.edgeRouting: ORTHOGONAL`
- `elk.direction` from `LayoutGraph.direction`
- `elk.hierarchyHandling: INCLUDE_CHILDREN` when cross-hierarchy edges exist
- Explicit `width`, `height` per node
- Port `side`, `index` per PortSpec

ELK result → `FinalizedLayout`:
- Child `x`, `y`, `width`, `height` → `NodeLayout`/`GroupLayout`
- Edge sections (bend points) → `RoutedEdge.waypoints`
- Label positions → `RoutedEdge.label_layout`

### Fallback path

`MERMAID_LAYOUT_ENGINE=python` or Node absent → `ElkUnavailable` → Python
Sugiyama + A\* pipeline (bit-identical to today).

### Subprocess contract

`elk_runner.js` reads ELK JSON from stdin, runs `elk.layout()`, writes result
JSON to stdout. Bounded by 30-second timeout in `elk_adapter.py`. Non-zero exit
or malformed JSON → `ElkUnavailable`.

## Tasks

### T0 — ADR: ELK layout engine decision

**Depends on:** none

**Tests:** Goal-based: `assert Path("docs/adr/001-elk-layout-engine.md").exists()`

**Approach:**
- Create `docs/adr/` directory
- Write `docs/adr/001-elk-layout-engine.md` recording: decision to use elkjs + Node as
  a conditional runtime dependency for graph-topology layout; context (pure-Python
  constraint and its backlog entry); consequences (Node required in CI; Python fallback
  for Node-absent environments; `elk_adapter.py` exempt from `TestNoSubprocess`)
- Record elkjs + Node in `scripts/mermaid_render/AGENTS.md` or root `AGENTS.md`

**Done when:** `docs/adr/001-elk-layout-engine.md` exists; `pytest tests/ -x -q` green

---

### T1 — Pre-layout IR types in `_geometry.py`

**Depends on:** T0

**Tests:**
```python
from mermaid_render.layout._geometry import (
    LayoutGraph, LayoutNode, LayoutGroup, LayoutEdge, PortSpec, MarkerKind
)

def test_layout_graph_construction():
    node = LayoutNode(id="A", measured_width=192, measured_height=42,
                      shape_id="rect", parent_id=None, ports=[], labels=["A"], semantic_data={})
    graph = LayoutGraph(nodes=[node], groups=[], edges=[], direction="TB")
    assert graph.nodes[0].id == "A"

def test_layout_edge_independent_markers():
    edge = LayoutEdge(id="e0", sources=["A"], targets=["B"],
                      source_port=None, target_port=None,
                      source_marker=MarkerKind.NONE, target_marker=MarkerKind.ARROW,
                      line_style="solid", label="", semantic_data={})
    assert edge.source_marker == MarkerKind.NONE
    assert edge.target_marker == MarkerKind.ARROW

def test_marker_kind_has_crow_variants():
    assert MarkerKind.CROW_ONE in MarkerKind
    assert MarkerKind.CROW_ZERO_MANY in MarkerKind
```

**Approach:**
- Append to `scripts/mermaid_render/layout/_geometry.py`:
  - `MarkerKind` enum (frozen string enum for JSON-safe serialisation)
  - `PortSpec` dataclass
  - `LayoutNode` dataclass
  - `LayoutGroup` dataclass
  - `LayoutEdge` dataclass
  - `LayoutGraph` dataclass
- All are frozen dataclasses with `__slots__ = ()` for performance
- Add tests to `tests/test_geometry_ir.py` (existing file for geometry tests)

**Done when:** `pytest tests/ -x -q` green; six new names importable from `mermaid_render.layout._geometry`

---

### T2 — ShapeGeometry protocol + registry

**Depends on:** T1

**Tests:**
```python
from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY

def test_registry_covers_all_shapes():
    expected = {"rect", "round", "stadium", "diamond", "circle", "doublecircle",
                "cylinder", "hexagon", "trapezoid", "trapezoid-alt", "subroutine", "flag", "bar"}
    assert expected <= set(SHAPE_REGISTRY.keys())

def test_rect_boundary_right():
    sg = SHAPE_REGISTRY["rect"]
    # center at (96, 21), direction right (+1, 0), 192x42 node
    x, y = sg.boundary_intersection(96, 21, 192, 42, 1.0, 0.0)
    import pytest
    assert x == pytest.approx(192.0)  # right edge
    assert y == pytest.approx(21.0)

def test_diamond_boundary_right():
    sg = SHAPE_REGISTRY["diamond"]
    x, y = sg.boundary_intersection(0, 0, 80, 40, 1.0, 0.0)
    assert x > 0 and abs(y) < 0.1
```

**Approach:**
- New file: `scripts/mermaid_render/layout/shape_geometry.py`
- `ShapeGeometry` as `runtime_checkable Protocol` with all six methods
- One implementation class per shape; all are zero-argument dataclasses/namedtuples
- `boundary_intersection(cx, cy, w, h, dx, dy)` where `(cx,cy)` is the node center,
  `(dx,dy)` is the outward direction vector, returns `(intersection_x, intersection_y)`
- `DiamondGeometry.boundary_intersection` ports the existing `_clip_to_diamond()` logic
- `paint_svg` and `paint_html` are stubs returning `None` for this task (wired fully in a future pass)
- `SHAPE_REGISTRY: dict[str, ShapeGeometry]` at module level
- Add tests to `tests/test_geometry_ir.py`

**Done when:** `pytest tests/ -x -q` green; registry has all 13 shapes; `boundary_intersection` tested for rect + diamond

---

### T2b — Wire ShapeGeometry into `_routing.py` connector clipping

**Depends on:** T2

**Tests:**
```python
from mermaid_render.layout.shape_geometry import SHAPE_REGISTRY
from unittest.mock import patch, call

def test_diamond_clipping_uses_registry(monkeypatch):
    """AC-SHAPE-3: _routing.py calls SHAPE_REGISTRY['diamond'].boundary_intersection.
    Patches the registry entry (not the instance) so it works regardless of frozen/slots."""
    from mermaid_render.layout import shape_geometry as sg_mod
    original_sg = sg_mod.SHAPE_REGISTRY["diamond"]
    calls = []
    class TrackingDiamond:
        def boundary_intersection(self, *args, **kwargs):
            calls.append(args)
            return original_sg.boundary_intersection(*args, **kwargs)
        def __getattr__(self, name):
            return getattr(original_sg, name)
    monkeypatch.setitem(sg_mod.SHAPE_REGISTRY, "diamond", TrackingDiamond())
    # Compile a diagram with a diamond node and force the Python fallback path
    import os
    os.environ["MERMAID_LAYOUT_ENGINE"] = "python"
    try:
        from mermaid_render.layout._strategies import _compile_flowchart, RenderOptions
        _compile_flowchart("flowchart TD\n  A{Decision} --> B", None, RenderOptions())
    finally:
        del os.environ["MERMAID_LAYOUT_ENGINE"]
    assert len(calls) > 0, "SHAPE_REGISTRY['diamond'].boundary_intersection was never called"
```

**Approach:**
- In `layout/_routing.py`, in `_route_edges()` where connector endpoints are clipped to node boundaries:
  - Replace the direct `_clip_to_diamond(cx, cy, w, h, dx, dy)` call with `SHAPE_REGISTRY[node.shape].boundary_intersection(cx, cy, w, h, dx, dy)` for all shapes
  - The `DiamondGeometry.boundary_intersection()` implementation in `shape_geometry.py` is a direct port of `_clip_to_diamond()` — output is identical
  - Keep `_clip_to_diamond()` as a private helper called by `DiamondGeometry.boundary_intersection()` to minimise diff noise
- Add `from .shape_geometry import SHAPE_REGISTRY` import to `_routing.py`
- This is the only change to `_routing.py` in this task; edge routing logic is unchanged

**Note on T5 "bit-for-bit identical":** The Python fallback path has one change — clip calls are routed through the registry. Output is identical because `DiamondGeometry.boundary_intersection` delegates to `_clip_to_diamond` unchanged. Non-diamond shapes use the default `RectGeometry.boundary_intersection` which replicates the existing rect-edge intersection logic.

**Done when:** `pytest tests/ -x -q` green; diamond clipping tracking test passes on `MERMAID_LAYOUT_ENGINE=python`

---

### T3 — Arrow semantics: `_Edge.source_marker` + `_Edge.target_marker`

**Depends on:** T1

**Tests:**
```python
from mermaid_render.layout._strategies import _compile_flowchart, RenderOptions
from mermaid_render.layout._geometry import MarkerKind

def test_arrow_edge_target_only():
    compiled = _compile_flowchart("flowchart LR\n  A --> B", None, RenderOptions())
    edge = compiled.layout.routed_edges[0]
    assert edge.target_marker == MarkerKind.ARROW
    assert edge.source_marker == MarkerKind.NONE

def test_bidir_edge_both_markers():
    compiled = _compile_flowchart("flowchart LR\n  A <--> B", None, RenderOptions())
    edge = compiled.layout.routed_edges[0]
    assert edge.source_marker == MarkerKind.ARROW
    assert edge.target_marker == MarkerKind.ARROW

def test_plain_edge_no_markers():
    compiled = _compile_flowchart("flowchart LR\n  A --- B", None, RenderOptions())
    edge = compiled.layout.routed_edges[0]
    assert edge.source_marker == MarkerKind.NONE
    assert edge.target_marker == MarkerKind.NONE

def test_legacy_arrow_bool_consistent_with_target_marker():
    """AC-IR-2: parser sets legacy .arrow consistent with target_marker on the same _Edge."""
    from mermaid_render.layout._parser import _parse_graph_source
    _nodes, edges, _groups = _parse_graph_source(
        ["A --> B", "A --- C"]
    )
    arrow_edge = next(e for e in edges if e.dst == "B")
    plain_edge = next(e for e in edges if e.dst == "C")
    # After T3: parser sets both legacy bool and marker consistently
    assert arrow_edge.target_marker == MarkerKind.ARROW
    assert arrow_edge.arrow == True
    assert plain_edge.target_marker == MarkerKind.NONE
    assert plain_edge.arrow == False

def test_legacy_bidir_bool_consistent_with_source_marker():
    """AC-IR-2: parser sets legacy .bidir consistent with source_marker on the same _Edge."""
    from mermaid_render.layout._parser import _parse_graph_source
    _nodes, edges, _groups = _parse_graph_source(["A <--> B"])
    edge = edges[0]
    assert edge.source_marker == MarkerKind.ARROW
    assert edge.target_marker == MarkerKind.ARROW
    assert edge.bidir == True
```

**Approach:**
- Add `source_marker: MarkerKind = MarkerKind.NONE` and `target_marker: MarkerKind = MarkerKind.NONE` to `_Edge` in `layout/_constants.py`
- Update `_parse_graph_source()` in `_parser.py` to set these from arrow syntax:
  - `-->` / `->` → `target=ARROW`
  - `<-->` / `<->` → `source=ARROW, target=ARROW`
  - `---` → both `NONE`
  - `-.->` → `target=ARROW` (dotted style, same marker logic)
  - ER `|o--||` → `source=CROW_ZERO_ONE, target=CROW_ONE` etc. (crow-foot mapping)
- Add `source_marker: MarkerKind` and `target_marker: MarkerKind` to `RoutedEdge` in `_geometry.py`
- Update `_route_edges()` in `_routing.py` to propagate to `RoutedEdge`
- Update `paint.py` `finalized_layout_to_scene()` to use `source_marker`/`target_marker` for `marker-start`/`marker-end`
- Keep `_Edge.arrow`, `_Edge.bidir`, `_Edge.arrow_src` as derived from parsed markers (no removal this PR); add `# deferred: backlog#arrow-semantics-cleanup` comment
- Add tests to `tests/test_mermaid_layout.py`

**Done when:** `pytest tests/ -x -q` green; three marker tests pass

---

### T4 — ELK adapter + dependency

**Depends on:** T1

**Tests:**
```python
# Default tier (mocked subprocess):
from unittest.mock import patch, MagicMock
from mermaid_render.layout.elk_adapter import layout_with_elk, ElkUnavailable
from mermaid_render.layout._geometry import LayoutGraph, LayoutNode, LayoutEdge, MarkerKind

def _simple_graph():
    return LayoutGraph(
        nodes=[LayoutNode("A", 192, 42, "rect", None, [], ["A"], {}),
               LayoutNode("B", 192, 42, "rect", None, [], ["B"], {})],
        groups=[],
        edges=[LayoutEdge("e0", ["A"], ["B"], None, None,
                          MarkerKind.NONE, MarkerKind.ARROW, "solid", "", {})],
        direction="TB",
    )

def test_elk_unavailable_when_node_absent(monkeypatch):
    import mermaid_render.layout.elk_adapter as mod
    monkeypatch.setattr(mod, "_find_node", lambda: None)
    with pytest.raises(ElkUnavailable):
        layout_with_elk(_simple_graph())

def test_elk_returns_finalized_layout_from_mock():
    elk_output = {
        "id": "root", "x": 0, "y": 0, "width": 500, "height": 300,
        "children": [
            {"id": "A", "x": 10, "y": 10, "width": 192, "height": 42},
            {"id": "B", "x": 10, "y": 132, "width": 192, "height": 42},
        ],
        # ElkEdgeSection schema: startPoint, endPoint (singular), optional bendPoints
        "edges": [{"id": "e0", "sections": [{"startPoint": {"x":106,"y":52},
            "endPoint": {"x":106,"y":132}, "bendPoints": []}]}]
    }
    with patch("mermaid_render.layout.elk_adapter._run_elk", return_value=elk_output):
        result = layout_with_elk(_simple_graph())
    assert "A" in result.node_layouts
    assert result.node_layouts["B"].rect.y > result.node_layouts["A"].rect.y

def test_elk_nonzero_exit_raises_unavailable():
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        with pytest.raises(ElkUnavailable):
            layout_with_elk(_simple_graph())

def test_elk_malformed_json_raises_unavailable():
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        with pytest.raises(ElkUnavailable):
            layout_with_elk(_simple_graph())

def test_elk_timeout_raises_unavailable():
    import subprocess
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("node", 30)):
        with pytest.raises(ElkUnavailable):
            layout_with_elk(_simple_graph())

def test_elk_subprocess_called_with_timeout():
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout=json.dumps(_minimal_elk_output()), stderr="")
        layout_with_elk(_simple_graph())
    _, kwargs = mock.call_args
    assert kwargs.get("timeout") == 30

def test_env_var_forces_python_path(monkeypatch):
    monkeypatch.setenv("MERMAID_LAYOUT_ENGINE", "python")
    with pytest.raises(ElkUnavailable):
        layout_with_elk(_simple_graph())

# Isolation tier (real Node subprocess):
@pytest.mark.isolation
def test_elk_places_nodes_real():
    result = layout_with_elk(_simple_graph())
    assert result.node_layouts["B"].rect.y > result.node_layouts["A"].rect.y
```

**Approach:**
- Write `scripts/mermaid_render/layout/elk_runner.js` (reads stdin, calls `elk.layout()`, writes stdout)
- Install: `npm install elkjs@0.12.0 --prefix scripts/mermaid_render/layout` → creates `package.json` + `package-lock.json` under that dir; `node_modules/` added to root `.gitignore`
- Write `scripts/mermaid_render/layout/elk_adapter.py`:
  - `class ElkUnavailable(RuntimeError): pass`
  - `_find_node() -> str | None` — shutil.which("node")
  - `_find_elkjs() -> str | None` — looks for `node_modules/elkjs/lib/elk.bundled.js` relative to this file
  - `_to_elk_json(graph: LayoutGraph) -> dict`
  - `_from_elk_result(out: dict, graph: LayoutGraph) -> FinalizedLayout`
  - `_run_elk(elk_json: dict) -> dict` — `subprocess.run(["node", runner, "--stdin"], input=json, timeout=30)`
  - `layout_with_elk(graph: LayoutGraph) -> FinalizedLayout`
  - Check `MERMAID_LAYOUT_ENGINE=python` env var first; if set, raise `ElkUnavailable`
- Update `tests/test_dependencies.py`:
  - Add `_SUBPROCESS_EXEMPTIONS: set[str] = {"elk_adapter.py"}`
  - In `TestNoSubprocess.test_no_subprocess_in_runtime_renderer`: skip files in exemptions

**Done when:** `pytest tests/ -x -q` green (mocked tests pass); `pytest --run-isolation tests/test_elk_adapter.py` passes with real Node

---

### T5 — Wire ELK into `_compile_flowchart`

**Depends on:** T2b, T3, T4

**Tests:**
```python
def test_elk_path_active_by_default():
    with patch("mermaid_render.layout.elk_adapter._run_elk") as mock_elk:
        mock_elk.return_value = _minimal_elk_output()
        compiled = _compile_flowchart("flowchart TD\n  A --> B", None, RenderOptions())
    mock_elk.assert_called_once()

def test_python_path_when_elk_unavailable(monkeypatch):
    import mermaid_render.layout.elk_adapter as mod
    monkeypatch.setattr(mod, "_find_node", lambda: None)
    compiled = _compile_flowchart("flowchart TD\n  A --> B", None, RenderOptions())
    assert len(compiled.layout.node_layouts) == 2

def test_no_group_separation_on_elk_path():
    # _separate_groups_lr/_tb must not be called when ELK succeeds
    with patch("mermaid_render.layout._strategies._separate_groups_lr") as mock:
        with patch("mermaid_render.layout.elk_adapter._run_elk", return_value=_elk_output_with_groups()):
            _compile_flowchart("flowchart TD\n  subgraph G\n    A\n  end", None, RenderOptions())
    mock.assert_not_called()
```

**Approach:**
- In `_compile_flowchart()` in `layout/_strategies.py`, after parsing produces `_Node/_Edge/_Group`:
  1. Build `LayoutGraph` from parsed structures (sizes from `_node_render_h()`)
  2. Try `layout_with_elk(graph)` → if it returns `FinalizedLayout`, return it (skip Python phases entirely)
  3. On `ElkUnavailable`: run existing Python pipeline unchanged (ranks → crossings → coords → routing → `FinalizedLayout`)
  4. On ELK path: **do not** call `_separate_groups_*`, `_apply_inner_direction_positions`, `_compact_group_columns`
- The ELK → `FinalizedLayout` conversion (`_from_elk_result`) produces the same `FinalizedLayout` type used by the Python path
- The Python path has two changes from T2b (registry-routed clipping) and T3 (marker fields) but is otherwise unchanged; output is semantically identical (same positions, same clip points via the registry delegate)

**Done when:** `pytest tests/ -x -q` green; ELK path active by default; Python fallback works when ELK unavailable

---

### T6 — Fix faithful mode

**Depends on:** T5

**Tests:**
```python
def test_faithful_no_icon_inference():
    html = to_html("flowchart LR\n  A[Database]:::database --> B", faithful=True)
    assert "node-icon" not in html

def test_faithful_no_legend():
    html = to_html("classDiagram\n  Animal <|-- Dog", faithful=True)
    assert "legend" not in html.lower()

def test_faithful_no_auto_direction_flip():
    # Long chain that might trigger auto-flip to LR
    src = "flowchart TB\n" + "\n".join(f"  N{i} --> N{i+1}" for i in range(8))
    compiled = _compile_flowchart(src, None, RenderOptions(faithful_mermaid=True))
    # TB direction: node y-coordinates should increase (not LR where x increases)
    nodes = compiled.layout.node_layouts
    sorted_nodes = sorted(nodes.values(), key=lambda n: n.rect.y)
    assert sorted_nodes[0].rect.y < sorted_nodes[-1].rect.y
```

**Approach:**
- In `_compile_flowchart()`: when `options.faithful_mermaid`:
  - Skip `_infer_label_icons(nodes)` call
  - Skip `auto_direction` check / flip
- In `_renderer.render_finalized()`: when faithful: skip semantic color tints, depth tints in `_render_node()`
- In `_dispatch()` (non-graph types): when faithful: skip legend rendering
- Audit for remaining un-faithful paths via grep for `inferred_legend`, `infer_icons`, `auto_direction`

**Done when:** `pytest tests/ -x -q` green; three faithful tests pass

---

### T7 — Fix validation (strict mode + oracle entity check)

**Depends on:** T5

**Tests:**
```python
from mermaid_render.layout._geometry import validate_finalized_layout, NodeLayout, FinalizedLayout, Rect

def _overlapping_layout():
    nodes = {
        "A": NodeLayout(rect=Rect(x=0, y=0, width=192, height=42), ...),
        "B": NodeLayout(rect=Rect(x=10, y=0, width=192, height=42), ...),  # overlaps A
    }
    return FinalizedLayout(node_layouts=nodes, ...)

def _make_overlapping_layout():
    """Two nodes overlapping by 182 px horizontally."""
    from mermaid_render.layout._geometry import NodeLayout, RouteBatch, Rect, FinalizedLayout
    nl_a = NodeLayout(rect=Rect(x=0, y=0, width=192, height=42),
                      label="A", shape="rect", icon=None, css_class=None, extra_css=None)
    nl_b = NodeLayout(rect=Rect(x=10, y=0, width=192, height=42),
                      label="B", shape="rect", icon=None, css_class=None, extra_css=None)
    return FinalizedLayout(
        node_layouts={"A": nl_a, "B": nl_b},
        group_layouts={},
        routed_edges=[],
        routing_failures=[],
        direction="TB",
        canvas_bounds=Rect(0, 0, 300, 100),
        diagram_padding=0,
        visible_bounds=Rect(0, 0, 300, 100),
        diagnostics=None,
    )

def _make_containment_violation():
    """Child node rect outside parent group rect."""
    from mermaid_render.layout._geometry import (
        NodeLayout, GroupLayout, RouteBatch, Rect, FinalizedLayout, Insets
    )
    child = NodeLayout(rect=Rect(x=500, y=500, width=192, height=42),
                       label="C", shape="rect", icon=None, css_class=None, extra_css=None)
    group = GroupLayout(rect=Rect(x=0, y=0, width=300, height=200),
                        label="G", label_height=20, padding=Insets(8, 8, 8, 8),
                        children={"C"}, direction=None)
    return FinalizedLayout(
        node_layouts={"C": child},
        group_layouts={"G": group},
        routed_edges=[], routing_failures=[], direction="TB",
        canvas_bounds=Rect(0, 0, 600, 600), diagram_padding=0,
        visible_bounds=Rect(0, 0, 600, 600), diagnostics=None,
    )

def test_strict_overlap_fails():
    result = validate_finalized_layout(_make_overlapping_layout(), strict=True)
    assert result.geometry != "pass"
    assert "fail" in result.geometry.lower()

def test_non_strict_overlap_does_not_fail():
    result = validate_finalized_layout(_make_overlapping_layout(), strict=False)
    # backward compat: non-strict may return "pass" or "unvalidated", never "fail"
    assert "fail" not in (result.geometry or "")

def test_containment_violation_fails():
    result = validate_finalized_layout(_make_containment_violation(), strict=True)
    assert result.structural_geometry not in ("pass", "unvalidated")
    assert "fail" in result.structural_geometry.lower()

def test_oracle_entity_zero_fails():
    """AC-VAL-3: runner records SEMANTIC_MISMATCH (not EXTRACTOR_GAP) when ref has entities
    and native semantic is None — after T7 fixes runner.py:171."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
    from mermaid_fidelity.runner import FidelityRunner
    from mermaid_fidelity.models import (
        ComparisonStatus, Entity, FidelityCase, Observation, SemanticDiagram,
        ImplementationIdentity, EnvironmentIdentity, ParseObservation,
    )
    from unittest.mock import MagicMock

    def _entity(eid): return Entity(id=eid, kind="node", label=eid, shape="rect",
                                    parent_id=None, order=0)
    ref_sem = SemanticDiagram(diagram_type="flowchart", direction="LR",
                              entities=[_entity("A"), _entity("B")], relations=[], groups=[])
    ref_obs = Observation(
        schema_version=1, case_id="test", status=ComparisonStatus.PASS, reason=None,
        implementation=MagicMock(), environment=MagicMock(),
        parse_result=MagicMock(), semantic=ref_sem, geometry=None, quality=None,
    )
    native_obs = Observation(
        schema_version=1, case_id="test", status=ComparisonStatus.PASS, reason=None,
        implementation=MagicMock(), environment=MagicMock(),
        parse_result=MagicMock(), semantic=None, geometry=None, quality=None,
    )
    case = FidelityCase(id="test", source_path=Path("."), source="", diagram="flowchart",
                        strict=["entities"])
    runner = FidelityRunner(native_adapter=MagicMock(), oracle_dir=Path("."))
    result = runner._compare(case, native_obs, ref_obs)
    # After T7 fix: native semantic=None + ref has entities → SEMANTIC_MISMATCH, not EXTRACTOR_GAP
    assert result.final_status == ComparisonStatus.SEMANTIC_MISMATCH, (
        f"Expected SEMANTIC_MISMATCH, got {result.final_status}"
    )
```

**Approach:**
- Add `strict: bool = False` parameter to `validate_finalized_layout()` in `_geometry.py`
- When `strict=True`:
  - Compute pairwise overlap for all `node_layouts` (use `Rect.overlaps()`)
  - Check each child node/group is contained by parent group (use `Rect.contains()`)
  - Return descriptive `geometry="fail: N overlapping pairs"` instead of `"pass"`
  - Return descriptive `structural_geometry="fail: N containment violations"` instead of `"unvalidated"`
- In `tools/mermaid_fidelity/runner.py`, in `FidelityRunner._compare()` at the `elif semantic_strict:` branch (currently line ~168):
  - Current: when `not native_obs.semantic` and ref has semantic data → `EXTRACTOR_GAP`
  - Fix: when `not native_obs.semantic` AND `ref_obs.semantic and ref_obs.semantic.entities` → `SEMANTIC_MISMATCH` (treat absent native extraction as a missing-entity failure, not an excused gap)
  - Preserve `EXTRACTOR_GAP` for the case where `not ref_obs.semantic` (oracle also has no data)

**Done when:** `pytest tests/ -x -q` green; overlap/containment tests pass; oracle entity test passes

---

### T8a — Snapshot baseline regeneration

**Depends on:** T5

**Tests:** Visual/manual QA — `pytest --run-snapshots tests/test_snapshots.py` regenerates graph-topology baselines; visual delta reviewed.

**Approach:**
- Run: `pytest --run-snapshots tests/test_snapshots.py -k "flowchart or statediagram"`
- Review visual diffs (if any snapshot runner produces diff images)
- Commit updated baselines

**Done when:** Snapshot runner exits 0 for graph-topology types with ELK-generated output

---

### T8b — Integration verification: all 15 fixtures + cross-path check

**Depends on:** T6, T7, T8a

**Tests:**
```python
@pytest.mark.parametrize("fixture_name", [
    # graph-topology: must pass strict validation
    "flowchart-all-shapes", "flowchart-arrows-defs", "flowchart-diamond-branch",
    "flowchart-diamond-clipping", "flowchart-empty-subgraph", "flowchart-groups-complex",
    "flowchart-inner-direction", "flowchart-parallel-links",
    "statediagram-complex", "statediagram-nested",
])
def test_graph_fixture_no_overlap(fixture_name):
    src = Path(f"tests/fixtures/{fixture_name}.mmd").read_text()
    compiled = _compile_flowchart(src, None, RenderOptions(faithful_mermaid=True))
    result = validate_finalized_layout(compiled.layout, strict=True)
    assert result.geometry == "pass", f"{fixture_name}: {result.geometry}"
    assert len(compiled.layout.node_layouts) > 0

@pytest.mark.parametrize("fixture_name", [
    "architecture-complex", "class-relationships-all",
    "er-cardinality-all", "er-ecommerce", "requirement-basic",
])
def test_non_graph_fixture_produces_output(fixture_name):
    src = Path(f"tests/fixtures/{fixture_name}.mmd").read_text()
    svg = to_svg(src, faithful=True)
    assert svg and len(svg) > 100

def test_each_entry_point_calls_compile_once(monkeypatch):
    """AC-IR-3: each entry point calls _compile_flowchart exactly once, no hidden recompute."""
    import mermaid_render.layout._strategies as strats
    real_compile = strats._compile_flowchart
    def counting_compile(src, width_hint, options, **kw):
        return real_compile(src, width_hint, options, **kw)

    # Pin the native SVG backend so to_svg uses _compile_flowchart (not legacy-dom path)
    monkeypatch.delenv("MERMAID_RENDER_SVG_BACKEND", raising=False)

    with patch("mermaid_render.layout._strategies._compile_flowchart",
               side_effect=counting_compile) as mock:
        src = "flowchart TD\n  A --> B --> C"
        to_html(src)
        html_count = mock.call_count
        mock.reset_mock()
        to_svg(src)
        svg_count = mock.call_count
    assert html_count == 1, f"to_html called _compile_flowchart {html_count} times"
    assert svg_count == 1, f"to_svg called _compile_flowchart {svg_count} times"
```

**Approach:**
- Add `tests/test_unified_pipeline.py` with the above tests
- Run full suite: `pytest tests/ -x -q`

**Done when:** All 15 fixture tests pass; cross-path comparison shows ≤ 0.5 px divergence; full suite green

---

## Changelog

- 2026-07-22: Initial plan authored (full mode, 8 tasks + T0 ADR)
- 2026-07-22: Revised after adversarial review — fixed 7 Blockers: ADR added as T0, AC-IR-2 softened (legacy booleans deferred), AC-FIX-1/2 scoped to graph-topology vs non-graph, AC-IR-3 implementing task added (T8b), ELK real-subprocess tests moved to `--run-isolation` (`@pytest.mark.isolation`) marker, governance ADR made T0 prerequisite, determinism claim scoped to within-engine, snapshot task added (T8a)
