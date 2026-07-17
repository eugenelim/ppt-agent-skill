# Plan: mermaid_layout.py — Test Suite, Icon Fix, Architecture

**Status:** Done

## Constraints

- Touch: `tests/test_mermaid_layout.py` (new), `scripts/mermaid_layout.py` (3 edits), `AGENTS.md`
- Don't touch: `scripts/smoke_test.py`, `scripts/test_diagram_qa.py`, any spec/strategy logic
- Gates: `pytest tests/ scripts/test_diagram_qa.py -x -q` exits 0; `python scripts/smoke_test.py` exits 0

## Declined patterns

- Package split — too high blast radius for this session; backlogged
- `_node_icon_name` helper — two call sites, no third coming; inline is clearer
- Modifying `_parse_graph_source` to backfill `n.icon` — conflates semantics

---

## Task 1 — Write RED icon-bug tests (TDD step 1)

**Verification mode:** TDD
**Depends on:** none

**Tests (stub — will be RED before Task 2):**
```python
# Note: _dispatch takes (src, direction_override, width_hint) — 3 positional args
def test_flowchart_database_class_injects_icon():
    html = _dispatch("flowchart LR\n  A[Server]:::database", None, 400)
    assert "node-icon" in html

def test_flowchart_api_class_injects_icon():
    html = _dispatch("flowchart LR\n  A[Gateway]:::api", None, 400)
    assert "node-icon" in html

def test_flowchart_plain_node_no_icon():
    html = _dispatch("flowchart LR\n  A[Server]", None, 400)
    assert "node-icon" not in html

def test_flowchart_external_class_no_icon():
    html = _dispatch("flowchart LR\n  A[Server]:::external", None, 400)
    assert "node-icon" not in html

def test_flowchart_nonexistent_icon_class_no_icon():
    html = _dispatch("flowchart LR\n  A[Thing]:::someMadeUpClass", None, 400)
    assert "node-icon" not in html

def test_node_render_h_database_icon_class():
    n_icon = _Node(id="A", label="Server", css_class="database")
    n_plain = _Node(id="B", label="Server")
    assert _node_render_h(n_icon) > _node_render_h(n_plain)

def test_plain_node_flex_direction_column():
    html = _dispatch("flowchart LR\n  A[Server]", None, 400)
    assert "flex-direction:row" not in html
```

**Approach:** Write the tests in `tests/test_mermaid_layout.py`. Confirm they are RED with `pytest tests/test_mermaid_layout.py -k icon -x -q`. Do NOT fix production code yet.

---

## Task 2 — Fix the icon bug (TDD step 2: GREEN)

**Verification mode:** TDD
**Depends on:** Task 1

**Approach:** Three targeted edits to `scripts/mermaid_layout.py`:

**Edit A — `_node_render_h` (around line 840-845):**
```python
# Docstring line 840: update "Uses n.icon (field) rather than _load_icon" →
#   "Uses n.icon and n.css_class (via _load_icon) to determine effective icon."

# Before:
if n.icon:
    extra_h = max(extra_h, 20)

# After:
effective_icon = n.icon or (n.css_class if (n.css_class and _load_icon(n.css_class)) else "")
if effective_icon:
    extra_h = max(extra_h, 20)
```

**Edit B — `_render_graph_fragment` icon loading (line 917):**
```python
# Before:
icon_svg = _load_icon(n.icon) if n.icon else ""

# After:
icon_svg = _load_icon(n.icon) if n.icon else (_load_icon(n.css_class) if n.css_class else "")
```

**Edit C — `_render_graph_fragment` flex_dir (line 958):**
```python
# Before:
flex_dir = "column" if tech_label else "row"

# After:
flex_dir = "column"
```

Confirm icon tests are GREEN: `pytest tests/test_mermaid_layout.py -k icon -x -q`

---

## Task 3 — Build the full test suite

**Verification mode:** Goal-based (≥ 60 tests pass)
**Depends on:** Task 2

**Test classes to write (in `tests/test_mermaid_layout.py`):**

```
TestStripFrontmatter        — 3 tests: no-frontmatter, with-frontmatter, unterminated
TestDetectDirective         — 4 tests: flowchart TB, LR, graph TD, unknown
TestParseSpec               — 8 tests: plain id, [rect], ["quoted"], (round), {diamond}, [(cyl)], ((circle)), >flag]
TestParseSpecAndClass       — 4 tests: no class, :::external, :::database, chained label+class
TestParseGraphSource        — 6 tests: basic nodes, edges, subgraph, cycle, chained edges, css_class propagation
TestBreakCycles             — 3 tests: DAG (no reversal), single cycle, self-loop
TestAssignRanks             — 4 tests: linear chain, diamond, multiple sources, dummy node insertion
TestMinimizeCrossings       — 2 tests: col indices set, no crash on empty graph
TestAssignCoordinates       — 3 tests: TB coordinates, LR coordinates, canvas size
TestWrapLabel               — 5 tests: short label, long label, explicit \n, real newline, pipe label
TestNodeRenderH             — 4 tests: single-line, multi-line, icon, tech-label
TestRenderGraphFragment     — 5 tests: has node divs, has SVG overlay, has group div, arrowhead present, external node styling
TestMetadataAndLegend       — 4 tests: extract title, chip with title, chip no title, legend mixed edges
TestDispatch                — 6 tests: flowchart, sequenceDiagram, erDiagram, gantt, pie, unknown (falls back)
TestFlowchartIconInjection  — 7 tests (from Task 1)
TestCapEnforcement          — 3 tests: 64 nodes ok, 65 nodes raises, edge cap raises
TestDirectiveStrategies     — 10 tests: sequenceDiagram, erDiagram, classDiagram, gantt, timeline, quadrantChart, pie, xychart-beta, architecture-beta, C4Context
TestErrorPaths              — 3 tests: zero-total pie, reversed packet range, empty source
```

Target: ≥ 60 tests total. Confirm: `pytest tests/test_mermaid_layout.py -q`

---

## Task 4 — Update AGENTS.md

**Verification mode:** Goal-based
**Depends on:** none (parallel-safe with Tasks 1-3)

Add `## Python module conventions` section to `AGENTS.md` (before the `## Skill authoring` section):

```markdown
## Python module conventions

### Module size
Scripts in `scripts/` should stay under ~500 lines. Above 800 lines, open a backlog item
to split into sub-modules. `mermaid_layout.py` is a tracked exception (backlog: `mermaid-layout-package-split`).

### Private symbols
All internal functions and constants use a `_` prefix. Only `main()` (CLI entry points) and
dataclass-level type names (`_Node`, `_Edge`, `_Group`) are intentionally importable by tests.

### Where tests live
- `tests/` — pytest unit tests; imported directly (not subprocess)
- `scripts/test_*.py` — integration or cross-module tests that need the full scripts/ context
- `scripts/smoke_test.py` — end-to-end subprocess tests

### Importing internals in tests
```python
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from mermaid_layout import _dispatch, _parse_spec, _Node, ...
```
No conftest.py needed — the `sys.path.insert` pattern is self-contained per file.
Run tests with: `pytest tests/ scripts/test_diagram_qa.py -x -q`

### No new pip dependencies
Adding a new `import` from outside stdlib or the project's `requirements.txt` requires an RFC.
```

Confirm: `grep -n "Python module conventions" AGENTS.md`
