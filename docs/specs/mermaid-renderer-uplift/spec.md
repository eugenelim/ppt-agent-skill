# Spec: Mermaid Renderer Quality Uplift

- **Status:** Draft
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Brief:** none
- **Discovery:** none
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The custom Mermaid layout renderer (`scripts/mermaid_layout/`) produces HTML/CSS diagrams with pixel-accurate text wrapping, a wider node shape vocabulary, inline label formatting, and a shared SVG marker vocabulary defined once in `<defs>`. Sequence, ER, and class diagrams carry diagram-type-appropriate notation: activation boxes and dog-ear notes for sequence; crow's foot cardinality symbols for ER; UML relationship markers for class. Every rendered diagram is verifiable through two complementary test layers: HTML-property assertions (red-green-refactor TDD, primary) and screenshot-baseline comparisons against a committed fixture corpus in `tests/fixtures/` and `tests/snapshots/` (visual regression guard, secondary).

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines.
*Always do* applies without asking; *Ask first* requires human sign-off
before proceeding; *Never do* is a hard rule, even under time pressure.

### Always do

- Keep output as HTML/CSS `<div>` nodes with an absolutely-positioned SVG overlay for edges and arrows — no format migration.
- Write the failing test first before any implementation code for every AC (red → green → refactor).
- Place every new diagram fixture in `tests/fixtures/<name>.mmd`; no inline fixture strings inside `tests/test_snapshots.py`.
- Define all SVG arrow and relationship markers once per `<defs>` block in the edge-routing SVG overlay; reference by stable `id` from edges.
- Preserve the existing CSS custom property names — `THEME_DARK`, `THEME_LIGHT`, `STYLE_COMPACT`, `STYLE_LARGE` variable sets are unchanged.
- Add all new HTML-property TDD test classes to `tests/test_mermaid_layout.py` (not a new test file).
- Pillow (`PIL`) is a hard prerequisite for pixel comparison in `tests/test_snapshots.py`; it is already pinned in `requirements.txt` and must remain there.

### Ask first

- Changing the public `_dispatch(src, direction_override, width_hint, height_hint, style_overrides)` signature or its return type.
- Altering any `_Node`, `_Edge`, or `_Group` dataclass field names re-exported from `scripts/mermaid_layout/__init__.py`.
- Adding a new CI step that requires external services or network access.
- Introducing any new pip dependency beyond those already in `requirements.txt`.

### Never do

- Migrate diagram output to pure SVG — the HTML/CSS div + SVG overlay architecture is the permanent contract.
- Add attribution or external-source references in code comments, docstrings, commit messages, or spec text.
- Introduce a new top-level module outside `scripts/mermaid_layout/` without an RFC.
- Change the string values in `_KNOWN_DIRECTIVES` (breaks caller parsing contracts).
- Emit duplicate `<marker>` IDs within a single SVG — suffix with a stable style-variant token, never an edge index.

## Testing Strategy

**TDD — HTML-property assertions (primary):** covers all logic improvements (AC-1 through AC-13) and the overflow guard (AC-16). For each improvement area, new test classes are added to `tests/test_mermaid_layout.py`. Tests assert on rendered HTML string output: CSS class or inline-style presence, SVG path `d` attribute coordinate values, `<marker>` count in `<defs>`, `<strong>`/`<em>`/`<s>` tag presence in label output, and numeric overflow bounds. Each test class is written before the implementing code; the test must fail first.

**Screenshot baseline — visual regression guard (secondary):** covers AC-14 and AC-15. After all HTML-property TDD passes for a wave, `tests/test_snapshots.py` renders each `.mmd` fixture via `_dispatch`, produces a PNG via `scripts/html2png.py`, and either captures a baseline (`--snapshot-capture` mode) or diffs against the committed PNG (default mode, threshold ≤ 0.5% changed pixels). Baseline PNGs live in `tests/snapshots/` and are committed. Baselines are single-machine-authoritative: captured with a pinned puppeteer version (`25.3.0`) and device-scale-factor `1`; CI is expected to have `node` available or the snapshot suite is skipped (not failed).

**Goal-based check:** AC-17. `pytest tests/test_mermaid_layout.py` passes with zero failures before and after every implementation wave.

## Acceptance Criteria

- [ ] **AC-1** `_measure_text_width(text: str, font_size: int, font_weight: int) -> float` exists in `scripts/mermaid_layout/_constants.py`. A `TestMeasureTextWidth` test class defines a reference set of 10 strings (spanning ASCII narrow chars, wide Latin, CJK, and mixed punctuation) whose expected pixel widths were measured via browser `canvas.measureText` at the specified `font_size`/`font_weight` and are hardcoded in the test as the oracle. The function returns widths within ±15% of those hardcoded oracle values.
- [ ] **AC-2** `_wrap_label` accepts a `width_budget: int` pixel parameter (default `NODE_W − 40`) and wraps on a pixel-width threshold computed via `_measure_text_width` at `font_size=13, font_weight=500`. The prior `max_chars` int parameter is removed from the signature. `ICON_COL_WIDTH: int = 34` (icon 24px + margin 10px) is defined as a named constant in `_constants.py`; icon-card callers pass `NODE_W − 40 − ICON_COL_WIDTH` explicitly. Both the height-computation path and the render path pass the identical `width_budget` for icon cards so computed heights match rendered line counts. A render-level test verifies that a label that fits on one line without an icon wraps to two lines when an icon is present. No caller passes `max_chars` — any such call raises `TypeError`.
- [ ] **AC-3** `_route_edges` in `_routing.py` clips path endpoints for `shape='diamond'` nodes to the actual diamond outline via ray-polygon intersection (`_clip_to_diamond`). A `TestDiamondEdgePath` test provides a known TB flowchart with one diamond→rect edge, parses the first `M x,y` of the generated `<path>` `d` attribute, and asserts the source endpoint satisfies the diamond-edge equation `|dx/w| + |dy/h| ≈ 0.5` (lies on the diamond face, not inside or on the bounding box).
- [ ] **AC-4** `_parse_spec` in `_parser.py` recognises and returns the correct canonical shape for: `([label])` → `stadium` (distinct from `round`), `{{label}}` → `hexagon`, `[[label]]` → `subroutine`, `[/label/]` → `trapezoid`, `[\label\]` → `trapezoid-alt`, `(((label)))` → `doublecircle`. All existing shapes (`rect`, `round`, `diamond`, `circle`, `cylinder`, `flag`) are unaffected.
- [ ] **AC-5** Each new/updated shape produces a visually distinct CSS or SVG representation: `stadium` uses a pill `border-radius` (≥ 50% on the short axis) distinct from `round`; `hexagon` uses `clip-path: polygon(...)` with six points; `subroutine` emits two inner vertical `<line>` SVG elements at ≈ 8px inset from each side; `trapezoid` and `trapezoid-alt` use opposing four-point `clip-path` polygons; `doublecircle` renders two concentric circular elements with the inner ≈ 5px smaller radius than the outer.
- [ ] **AC-6** Node labels containing `**text**` render with `font-weight:700` or `<strong>`; `*text*` with `font-style:italic` or `<em>`; `~~text~~` with `text-decoration:line-through` or `<s>`. Mixed formatting (`**bold** and *italic*`) renders both markers correctly. Mismatched delimiters (e.g. `**no close`) are treated as literal text — no partial HTML tags emitted. A label where a bold span straddles a `_wrap_label`-inserted line break renders the break and the bold marker both correctly.
- [ ] **AC-7** The edge-routing SVG overlay for every graph-topology diagram contains exactly one `<defs>` block with one `<marker>` element per arrow style variant in use (normal, thick, open/dotted). No `<polygon>` arrowhead elements appear as direct SVG children of the overlay `<svg>` outside `<defs>`. Legend inline SVGs (emitted by `_render_legend`) are excluded from this constraint. A 10-edge same-style diagram has exactly 1 matching `<marker>` in `<defs>` and 10 `marker-end=` references on `<path>` elements.
- [ ] **AC-8** Sequence diagrams with `activate`/`deactivate` lines render a filled `<rect>` element on the lifeline SVG for the duration of each activation, centered on the participant's lifeline x-coordinate.
- [ ] **AC-9** Sequence self-messages (`A ->> A`) render as a cubic-bezier `<path>` loop to the right of the lifeline (the `d` attribute contains a `C` command), not as a zero-length horizontal line.
- [ ] **AC-10** `Note over` statements in sequence diagrams render as a five-point polygon `<polygon>` SVG element with a folded top-right corner. The note text is positioned within the polygon bounds.
- [ ] **AC-11** `loop`, `alt`, and `opt` blocks in sequence diagrams render as a containing `<rect>` with a header text label. `alt` additionally renders a horizontal `<line>` divider between branches.
- [ ] **AC-12** ER diagrams render crow's foot cardinality markers at both endpoints of each relationship `<path>`: `||` → two parallel bars (one), `o|` → circle + bar (zero-or-one), `}|` / `|{` → three-line fan (many), `o{` / `}o` → circle + three-line fan (zero-or-many). Marker SVG elements appear within 16px of the edge endpoint.
- [ ] **AC-13** Class diagrams define relationship markers in `<defs>`: `<|--` → hollow-triangle `#cls-inherit`, `*--` → filled-diamond `#cls-composition`, `o--` → hollow-diamond `#cls-aggregation`, `-->` → open-chevron `#cls-dep`. Dashed lines (`..`) use `stroke-dasharray`. Each marker ID is present in `<defs>` when at least one relationship of that type is rendered.
- [ ] **AC-14** `tests/fixtures/` contains ≥ 27 `.mmd` files covering all dispatched diagram types — explicitly: flowchart/graph, stateDiagram-v2, sequenceDiagram, erDiagram, classDiagram, gantt, timeline, quadrantChart, pie, xychart-beta, mindmap, block-beta, packet-beta, kanban, architecture-beta, and c4Context — plus dedicated fixtures for each improvement area (AC-1 through AC-13).
- [ ] **AC-15** `tests/test_snapshots.py` renders each fixture via `_dispatch`, converts to PNG via `scripts/html2png.py` at device-scale-factor 1 with puppeteer `25.3.0`, and in default (regression) mode asserts ≤ 0.5% changed pixels against the committed baseline in `tests/snapshots/`. Running with `--snapshot-capture` (registered in `conftest.py`) creates or overwrites the baseline without asserting. The suite skips (does not fail) when `node` is not on PATH or when an env-var guard `SNAPSHOT_BASELINE_PLATFORM` does not match the current `sys.platform` — preventing false-failures on CI platforms that differ from the baseline machine.
- [ ] **AC-16** For every fixture in `tests/fixtures/`, no node's bottom edge (`top + computed_height` parsed from the rendered HTML) exceeds the **pre-legend canvas height** + `CANVAS_PAD`. The pre-legend canvas height is extracted from the overlay SVG's inline `style` attribute — `re.search(r'<svg\b[^>]*style="[^"]*\bheight:(\d+)px', html)` — which carries `canvas_h` before the legend strip is added (`_renderer.py:294`). The outer wrapper `<div>`'s `height` (which includes `_LEGEND_H`) and legend swatch `<svg height="10">` attributes must not be used. Verified by `TestFixtureCorpus.test_no_overflow` in `tests/test_mermaid_layout.py` (HTML-property TDD).
- [ ] **AC-17** All tests in `tests/test_mermaid_layout.py` (≥ 200 at spec-authoring time) pass without modification after every implementation wave.

## Assumptions

- Technical: Runtime is Python 3.13 (probe: `python3 -c "import sys; print(sys.version)"` → `3.13.13`)
- Technical: Renderer is pure Python stdlib only — zero pip dependencies in `scripts/mermaid_layout/` itself (probe: imports in `_constants.py`: `re`, `dataclasses`, `pathlib`, `typing` only)
- Technical: Output is HTML/CSS `<div>` with SVG overlay; `_renderer.py` emits `<div class="diagram mermaid-layout">` (probe: `_renderer.py` file inspection)
- Technical: Test runner is `pytest`; primary test file is `tests/test_mermaid_layout.py` (probe: file imports `pytest`, uses `class Test*` structure)
- Technical: Test corpus is 100% inline strings — no `.mmd` fixture files exist today (probe: `grep -rn "\.mmd" tests/ scripts/` → zero matches)
- Technical: Zero visual snapshot tests exist today — all verification is HTML string assertions and numeric geometry checks (probe: `grep "screenshot|snapshot|pixel" tests/test_mermaid_layout.py` → zero matches)
- Technical: Package split is complete — 8 sub-modules in `scripts/mermaid_layout/`, no monolith refactor needed first (probe: `ls scripts/mermaid_layout/`)
- Technical: `puppeteer@25.3.0` is a devDependency in `package.json`; `scripts/html2png.py` exists and uses it (probe: `package.json`, `ls scripts/html2png.py`)
- Technical: `Pillow` is already pinned in `requirements.txt` (`Pillow==12.3.0`) — no new dep sign-off needed (probe: adversarial reviewer confirmed `requirements.txt`)
- Technical: `stadium` (`([label])`) is already parsed but currently aliased to `round` shape with identical rendering — needs a distinct pill CSS (probe: `_parser.py` `_SPEC_SHAPE_MAP`: `"stadium": "round"`)
- Technical: `hexagon`, `subroutine`, `trapezoid`, `trapezoid-alt`, `doublecircle` are not yet parsed — `{{…}}`, `[[…]]`, `[/…/]`, `[\…\]`, `((…))` fall through to the no-match case in `_parse_spec` (probe: `_parser.py` `_SPEC_RE` regex inspection)
- Technical: `_wrap_label` currently returns `list[str]` (not a string with `<br>`) — the `<br>` join happens in `_renderer.py` (probe: adversarial reviewer confirmed `_constants.py:223`)
- Product: All 9 improvement areas are in scope for this spec (user confirmation 2026-07-17)
- Product: Visual verification uses HTML-property TDD plus screenshot baseline (user confirmation 2026-07-17)
- Product: Output architecture stays HTML/CSS div + SVG overlay, no migration to pure SVG (user confirmation 2026-07-17)
