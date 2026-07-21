# Mermaid P0+P1 Renderer Report

## Environment Baseline

| Item | Value |
|------|-------|
| Starting SHA | `fbf0987e5e0795c8077ea963cf09d0bad4cad5c2` |
| Git dirty | false |
| Python | 3.13.13 |
| Pillow | 12.2.0 |
| mmdc | 11.15.0 |
| Platform | darwin |

## Baseline Test Results

```
python3 -m pytest tests/test_mermaid_layout.py tests/test_routing_astar.py \
  tests/test_render_correctness.py tests/test_syntax_architecture.py \
  tests/test_syntax_c4.py tests/test_fix_architecture.py \
  tests/test_fix_flowchart.py tests/test_fix_state.py tests/test_oracle.py -q

1327 passed, 72 skipped
```

## Stage 0: Baseline Establishment

**Status:** in-progress

### Changes

- `scripts/compare_gallery.py`: Added `--output-dir`, `--metadata-only`, `--width-hint` CLI arguments.
  Each gallery run writes `<output-dir>/metadata.json` with full provenance.
- `tests/test_render_correctness.py`: Removed `gitgraph-basic.mmd`, `journey-basic.mmd`,
  `requirement-basic.mmd` from `_UNSUPPORTED` (all three are now dispatched).
  Moved `gitgraph-basic.mmd` and `journey-basic.mmd` to `_NO_PATHS` (no annotated edge paths).

### Gallery Paths

| Gallery | Path |
|---------|------|
| Before | ppt-output/compare-before/ |
| After | ppt-output/compare-after/all/ |

---

## Stage 1: Geometry IR

**Status:** pending

### Pipeline Design

```
parse semantic models (_Node, _Edge, _Group)
  -> measure text (TextMeasurer / PillowTextMeasurer)
  -> calculate node dimensions
  -> layered/compound placement
  -> calculate group boundaries
  -> create ports
  -> route edges
  -> place edge labels
  -> calculate visible bounds
  -> freeze FinalizedLayout
  -> serialize HTML (_renderer.py)
```

### IR Types (in _geometry.py)

- `Point`, `Size`, `Insets`, `Rect`
- `TextStyle`, `TextRun`, `TextLine`, `TextLayout`
- `PortSide` enum (AUTO/LEFT/RIGHT/TOP/BOTTOM)
- `PortRequest`, `PortLayout`
- `NodeLayout`, `GroupLayout`
- `EdgeLabelLayout`, `RoutedEdge`
- `LayoutDiagnostics`, `FinalizedLayout`

---

## Stage 2: Text Layout

**Status:** pending

### Font Resolution Order

1. Explicit RenderOptions/config font path
2. MERMAID_RENDER_FONT_PATH env var
3. Known Inter font locations
4. Known Arial/Liberation Sans locations
5. Known DejaVu Sans locations
6. Pillow bundled/default font (last resort)

### TextMeasurer Protocol

```python
class TextMeasurer(Protocol):
    def measure_run(self, text: str, style: TextStyle) -> TextRun: ...
    def layout(self, text: str, style: TextStyle, max_width: float | None,
               *, allow_emergency_break: bool = False) -> TextLayout: ...
```

---

## Stage 3: Typed Config

**Status:** pending

---

## Stage 4: Architecture Ports

**Status:** pending

---

## Stage 5: C4 Parsing and Boundaries

**Status:** pending

---

## Stage 6: Compound Graph Layout

**Status:** pending

---

## Stage 7: Port/Label Routing

**Status:** pending

---

## Stage 8: Layered Graph Core

**Status:** pending

### Algorithm Names

| Strategy | Name |
|----------|------|
| Rank | `longest-path`, `network-simplex` |
| Order | `barycenter`, `barycenter-transpose` |
| Position | `simple`, `brandes-koepf` |

---

## Stage 9: Renderer Serialization-Only

**Status:** pending

---

## Stage 10: Content-Tight SVG

**Status:** pending

---

## Before/After Test Counts

| Phase | Passed | Skipped | Failed |
|-------|--------|---------|--------|
| Baseline | 1327 | 72 | 0 |
| Final | TBD | TBD | TBD |

## Known Remaining Gaps

### Parser Gaps
TBD

### Layout Gaps
TBD

### Renderer Gaps
TBD

### Visual-Style Gaps
TBD

## Unsatisfied Acceptance Criteria

TBD — to be filled at completion.
