# Plan: sequence-rendering-fix

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn.

## Approach

Work proceeds in dependency order across three generations. **Generation 1** (T1–T3) consists of three independent tasks that can be done in any order: gallery provenance, the ValidationResult four-status extension, and the arrow parity fix. **Generation 2** (T4–T6) depends on G1 results and adds diagnostics, Fragment typed objects, and PillowTextMeasurer wiring. **Generation 3** (T7–T11): T7 adds self-message geometry and refactors `_layout_lifeline` to return `(html, SequenceGeometry)`; T8a/T8b implement the constraint solver in two phases; T11 (P2 cleanup) must complete before T9 (semantic validation), because T9's canvas-bounds invariant depends on T11's marker-in-viewBox fix; T10 (fixtures) runs last.

Execution order within G3: T6 → T7 → T8a → T11 → T8b → T9 → T10.

The riskiest parts are T7 (changes the return type of `_layout_lifeline`, which must be unpacked within `_dispatch` only — all callers of `_dispatch` remain unchanged) and T8a (replaces the core column computation, causing geometry shifts across all tests). Introduce both behind the eight-fixture regression suite before proceeding to T8b/T9.

## Constraints

None from ADRs or RFCs. The spec's Boundaries (no layout-constant tuning, no partial-diagram green status) govern all tasks.

## Construction tests

**Integration:** regenerate all eight original fixtures after T8b completes and assert all semantic invariants pass — this is the integration smoke test that the geometry pipeline is end-to-end correct.

**Manual verification:** open the regenerated gallery in a browser after T8b and visually confirm self-loop arrows, column spacing, participant box widths, and activation bar alignment. Record the observation in the task's Done-when note.

## Design (LLD)

### Design decisions

- **Four-status model in `ValidationResult`**: add four fields (`render`, `syntax_coverage`, `geometry`, `mmdc_oracle`) with defaults, keeping the existing `errors`/`warnings`/`.status` interface for callers that have not yet migrated. No new type created.
- **`Diagnostic` dataclass**: frozen dataclass in `_geometry.py` alongside `ValidationResult`; referenced by both `_strategies.py` (emit site) and `compare_gallery.py` (display site). Keeps the geometry IR the single home for validation types.
- **`Fragment` / `FragmentBranch` dataclasses**: frozen, defined at module level in `_strategies.py` (near the top of `_layout_lifeline`). Replace the loose `dict` + `_frag_parts` set pattern.
- **`SequenceGeometry` and `_layout_lifeline` return type change**: `_layout_lifeline` currently returns `str` (HTML). In T7 it is refactored to return `(html: str, geometry: SequenceGeometry)`. `SequenceGeometry` is a frozen dataclass carrying: `participant_centers: dict[str, float]`, `lifeline_x: dict[str, float]`, `activation_bars: dict[str, list[tuple[float,float]]]` (list of (top_y, bottom_y) per pid), `message_ys: list[float]`, `message_endpoints: list[tuple[float,float,float,float]]` (src_x, src_y, dst_x, dst_y per message), `fragment_bounds: dict[str, tuple[float,float,float,float]]` (x, y, w, h per fragment id), `branch_separator_bounds: dict[str, list[tuple[float,float,float,float]]]` (rects per fragment id), `note_bounds: list[tuple[float,float,float,float]]`, `self_loop_bounds: list[tuple[float,float,float,float]]` (x, y, w, h per self-message event), `label_bounds: list[tuple[float,float,float,float]]` (per message), `marker_bounds: list[tuple[float,float,float,float]]` (per drawn marker), `canvas: tuple[float,float]`. `_dispatch_validate` calls `_layout_lifeline` directly to obtain `(html, geometry)`, then validates the geometry object — it never parses the emitted HTML. `_dispatch`'s sequence branch (`_strategies.py:3992`) unpacks the tuple and returns only `html`; all callers of `_dispatch` receive `str`, preserving the public API in `__init__.py`, `__main__.py`, and all tests.
- **`activation_bounds_at(pid, y)`**: a helper function inside `_layout_lifeline`, given the participant id and a y coordinate, returns `(left_x, right_x)` of the outermost active activation bar at that y, or `(cx, cx)` if no bar is active. Used by both straight-message endpoint clamping and self-message loop anchoring.
- **Constraint solver**: a simple left-to-right longest-path over an ordered list of `(i, j, min_gap)` constraints. No external library; implemented as a one-pass `O(n)` scan over sorted constraints. Width of diagram = `max_center + rightmost_half_width + PAD_H`.
- **Participant box width**: the participant box `width` attribute is set to `max(measured_label_width + BOX_HPAD, BOX_MIN_W)` rather than the fixed `col_w`. The label span removes `overflow:hidden` and `text-overflow:ellipsis`; the constraint solver is given a correspondingly wider `half_width` for that participant column.
- **`mmdc_oracle` deferred**: the oracle comparison status defaults to `"unvalidated"`; computing it is tracked in `docs/backlog.md#seq-mmdc-oracle-comparison`. No computing code ships in this spec.

### Data & schema

`ValidationResult` extension (in `_geometry.py`):
```python
@dataclass(frozen=True, slots=True)
class Diagnostic:
    feature: str
    line_number: int
    source_text: str

@dataclass(frozen=True, slots=True)
class ValidationResult:
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    diagnostics: Tuple[Diagnostic, ...] = ()
    render: str = "pass"           # "pass" | "fail"
    syntax_coverage: str = "pass"  # "pass" | "partial" | "fail"
    geometry: str = "unvalidated"  # "pass" | "fail" | "unvalidated"
    mmdc_oracle: str = "unvalidated"  # "pass" | "warning" | "fail" | "unvalidated"
```

`Fragment` / `FragmentBranch` (in `_strategies.py`):
```python
@dataclass(frozen=True)
class FragmentBranch:
    condition: str
    start_event: int
    end_event: int

@dataclass(frozen=True)
class Fragment:
    id: str
    kind: str
    condition: str
    parent_id: Optional[str]
    start_event: int
    end_event: int
    participant_ids: frozenset[str]
    branches: tuple[FragmentBranch, ...]
```

### Component / module decomposition

| Symbol | File | Role |
|---|---|---|
| `Diagnostic` | `_geometry.py` | Typed structured diagnostic; emitted for unsupported/unknown constructs |
| `SequenceGeometry` | `_geometry.py` | Frozen dataclass carrying all computed sequence geometry (participant centers, activation bars, message endpoints, fragment/note/label/marker bounds, canvas); returned alongside HTML by `_layout_lifeline` |
| `Fragment`, `FragmentBranch` | `_strategies.py` | Typed fragment model replacing loose dicts |
| `activation_bounds_at(pid, y)` | `_strategies.py` (inside `_layout_lifeline`) | Returns active bar x-bounds at a given y |
| `_solve_col_centers(constraints)` | `_strategies.py` | Longest-path column constraint solver |
| `_draw_marker("filled_head", ...)` | `_strategies.py` | New half-arrowhead marker renderer |
| `_assert_module_provenance()` | `compare_gallery.py` | Pre-render module-path assertion |
| Four-badge status row | `compare_gallery.py` | Renders render/syntax/geometry/oracle badges |

### Failure, edge cases & resilience

- If `mermaid_render.__file__` is not inside the repo: gallery exits non-zero before generating any HTML.
- If an unknown participant name appears in a message: emit `Diagnostic(feature="unknown_participant", ...)`, default to nearest known participant for rendering (not index 0).
- If a `deactivate` has no matching `activate`: emit `Diagnostic(feature="unmatched_deactivate", ...)`, skip the bar.
- If the constraint solver produces a layout narrower than `width_hint`: apply uniform scale to reach `width_hint`.

## Tasks

### T1: Gallery provenance and atomic replace

**Depends on:** none
**Touches:** `tools/compare_gallery.py`

**Tests:**
- `assert_module_provenance()` raises `SystemExit` when called with a `__file__` outside the repo root.
- After gallery generation, `metadata.json` contains all required keys: `git_sha`, `git_dirty`, `python_executable`, `mermaid_render_module_path`, `strategies_sha256`, `text_sha256`, `mmdc_version`, `fixture_sha256`, `renderer_schema_version`.
- Gallery `<header>` HTML contains the short SHA, last-two-path-components of module path, and first-12-hex of `strategies_sha256`.
- After generation, no temporary directory remains; the output directory was replaced atomically.

**Approach:**
1. Add `_assert_module_provenance(repo_root: Path)` at the top of `compare_gallery.py`; call it before `_build_gallery`.
2. Extend `_collect_metadata` to add `strategies_sha256`, `text_sha256`, `renderer_schema_version` (hardcoded `"2026-07-21"` for now), `mermaid_render_module_path`.
3. Update the gallery `<header>` template string to show SHA, module path, and source hash.
4. Wrap `_build_gallery` call in `main()`: write to `tempfile.mkdtemp()`, then `shutil.move(tmp_dir, dest_dir)`.

**Done when:** `python3 -m pytest tests/test_compare_gallery.py -k provenance` green (or new test file if one doesn't exist); running the gallery tool produces a directory with `metadata.json` containing all nine new fields.

---

### T2: ValidationResult four-status model

**Depends on:** none
**Touches:** `scripts/mermaid_render/layout/_geometry.py`, `scripts/mermaid_render/__init__.py`, `tools/compare_gallery.py`

**Tests:**
- `ValidationResult()` default has `geometry="unvalidated"`, `render="pass"`, `syntax_coverage="pass"`, `mmdc_oracle="unvalidated"`.
- `_dispatch_validate("sequenceDiagram\nA->>B: hi")` returns a `ValidationResult` with `geometry="unvalidated"`.
- Gallery renders four separate CSS-classed badge elements per diagram: `.badge-render`, `.badge-syntax`, `.badge-geometry`, `.badge-oracle`.
- A diagram with `geometry="unvalidated"` shows a grey/yellow badge, not green.
- Existing callers that read only `.status` / `.errors` / `.warnings` continue to work (backward compatibility).

**Approach:**
1. Add `Diagnostic` frozen dataclass to `_geometry.py`.
2. Extend `ValidationResult` with `diagnostics`, `render`, `syntax_coverage`, `geometry`, `mmdc_oracle` fields (all with defaults preserving old interface).
3. Update `_dispatch_validate` to return `ValidationResult(geometry="unvalidated")` explicitly.
4. Update `compare_gallery.py` `_classify_status` to read four fields and render four badges.

**Done when:** `python3 -m pytest tests/test_fix_sequence.py tests/test_syntax_sequence.py` still green; new tests for four-status defaults pass.

---

### T3: Arrow parity — filled_head marker

**Depends on:** none
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `tests/test_fix_sequence.py`

**Tests:**
- `_draw_marker("filled_head", x, y, direction)` emits an SVG `<polygon>` with non-zero fill (not a circle, not a hollow path).
- `_ARROW_SPECS["-)"]["end_m"] == "filled_head"` and `_ARROW_SPECS["--)"]["end_m"] == "filled_head"`.
- Parameterised test over all ten `_ARROW_SPECS` tokens: for each token, render `A{token}B: label` and assert the correct number/type of marker elements.
- Self-message form of each token also renders the correct marker.
- `TestArrowSpecTable` passes with no `pytest.skip()`.

**Approach:**
1. Add `"filled_head"` branch to `_draw_marker` inside `_layout_lifeline`; render it as a filled polygon scaled to the renderer's marker coordinate system (reference: mmdc path `M 18,7 L9,13 L14,7 L9,1 Z` — half-chevron pointing right; mirror for direction=-1).
2. Update `_ARROW_SPECS` for `"-)"`/`"--)` to `"filled_head"`.
3. Update `TestArrowSpecTable` — the `-)` test currently asserts `"<circle"` (`test_fix_sequence.py:766`) and the `--)` test asserts `arrow_polys == 0` (`test_fix_sequence.py:777`); both must be updated to assert a filled-head polygon instead.
4. Add parameterised test across all ten tokens.

**Done when:** `python3 -m pytest tests/test_fix_sequence.py -k arrow` green; `-)` and `--)` render polygon markers in the gallery.

---

### T4: Unsupported syntax diagnostics

**Depends on:** T2 (needs `Diagnostic` and `syntax_coverage` field)
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `tests/test_fix_sequence.py`, `tests/test_syntax_sequence.py`

**Tests:**
- Rendering `"sequenceDiagram\nautonumber\nA->>B: hi"` returns `ValidationResult` with `diagnostics` containing one `Diagnostic(feature="autonumber", line_number=2, source_text="autonumber")` and `syntax_coverage="partial"`.
- Same for `create participant`, `create actor`, `destroy`, `box … end`, `par_over`.
- A completely unrecognised line (e.g. `"gobbledygook XYZ"`) emits `Diagnostic(feature="unrecognized_line", ...)`.
- No source line matching a recognised pattern is absent from both the SVG output and the diagnostics tuple.
- `syntax_coverage="fail"` when the renderer raises.

**Approach:**
1. Replace the `_SEQ_SKIP_RE` silent-skip with a diagnostic emit: for each matched line, append `Diagnostic(feature=<keyword>, line_number=<lineno>, source_text=<raw_line>)` to a local `_diagnostics` list.
2. Add a final `else` branch in the per-line parser loop (after all known regexes) that emits `Diagnostic(feature="unrecognized_line", ...)` for any non-blank, non-comment line.
3. Pass `_diagnostics` into the returned `ValidationResult` when `_dispatch_validate` (or the render path) calls back with results.
4. Compute `syntax_coverage`: `"partial"` if `_diagnostics` non-empty, `"fail"` if render raises, `"pass"` otherwise.
5. Update `test_fix_sequence.py::TestParserGaps` and `test_syntax_sequence.py::TestSequenceSequencing` to assert diagnostics instead of just "doesn't crash".

**Done when:** `python3 -m pytest tests/test_fix_sequence.py tests/test_syntax_sequence.py -k "autonumber or parser or syntax"` green; no source line silently discarded.

---

### T5: Fragment model — typed dataclasses and data-* attributes

**Depends on:** none
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `tests/test_fix_sequence.py`

**Tests:**
- Rendered `alt` block `<rect>` carries `data-fragment-id`, `data-fragment-kind="alt"`, `data-participants="A B"`, `data-start-event="2"`, `data-end-event="5"` (or similar counts).
- `TestFragmentParticipantBounds` locates fragments via `[data-fragment-kind]` selector; no `pytest.skip()` branches remain.
- Nested fragments: inner fragment's `data-participants` is a subset of outer's.
- `FragmentBranch` conditions propagate to `data-branch-condition` on `else`/`and` separator rects.

**Approach:**
1. Define `FragmentBranch` and `Fragment` frozen dataclasses at module level (above `_layout_lifeline`).
2. Replace the loose `_frag_parts: dict[int, set]` accumulation with a `_fragments: dict[int, Fragment]` builder pattern; finalize each `Fragment` when `block_end` is encountered.
3. In the SVG render pass, emit `data-fragment-id`, `data-fragment-kind`, `data-participants` (space-joined sorted pid list), `data-start-event`, `data-end-event` on each fragment rect.
4. Emit `data-branch-condition` on else/and separator rects.
5. Update `TestFragmentParticipantBounds` to use attribute selectors.

**Done when:** `python3 -m pytest tests/test_fix_sequence.py -k fragment` green with no `pytest.skip()`.

---

### T6: Wire PillowTextMeasurer into sequence renderer

**Depends on:** none
**Touches:** `scripts/mermaid_render/layout/_strategies.py`

**Tests:**
- `_note_row_h` (or its replacement) uses measurer output, not `_CHAR_W_10PX`.
- `TestVariableHeightRows` still passes.
- Rendering a note with a CJK character produces a taller row than the same ASCII note (because CJK chars measure as 2× width).
- `_CHAR_W_10PX` and `_LINE_H_10PX` do not appear anywhere in `_strategies.py`.

**Approach:**
1. At the top of `_layout_lifeline`, call `_MEASURER = get_default_measurer()` (module-level singleton, imported from `._text`).
2. Replace `_note_row_h(it)` char-count heuristic with `_MEASURER.layout(text, style, max_width=usable_w).height + VPAD`.
3. Replace message-label width estimates (`len(label) * _CHAR_W_10PX`) with `_MEASURER.layout(label, style, max_width=inf).max_content_width`.
4. Remove `_CHAR_W_10PX` and `_LINE_H_10PX` constants.
5. Run full test suite; fix any rows whose height changed enough to break a geometry assertion.

**Done when:** `python3 -m pytest tests/test_fix_sequence.py` green; `grep -n "_CHAR_W_10PX\|_LINE_H_10PX" scripts/mermaid_render/layout/_strategies.py` returns nothing.

---

### T7: Self-message geometry — activation-aware anchor, text-measured loop, and SequenceGeometry return

**Depends on:** T5, T6
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `scripts/mermaid_render/layout/_geometry.py`, `tests/test_fix_sequence.py`

**Tests:**
- Inactive self call: loop anchors at lifeline center x, extends right by `loop_w`.
- Active self call: loop anchors at activation bar's right edge, extends right by `loop_w`.
- Nested active self call: anchor is outermost bar's right edge.
- Self call on rightmost participant: loop still fully within canvas (canvas width expands).
- Long self label: `loop_w` is wider than short-label case.
- Multiline self label: `loop_h` is taller.
- `cross` and `filled_head` self-arrow markers render at the correct loop endpoint.
- Bidirectional self arrow: start marker at loop top, end marker at loop bottom.
- Loop geometry included in global `viewBox` (no clipping on right edge).
- `_layout_lifeline` returns a 2-tuple `(html, geometry)` where `geometry` is a `SequenceGeometry` instance.
- `geometry.participant_centers["A"]` equals the x-coordinate of participant A's lifeline.

**Approach:**
1. Add `SequenceGeometry` frozen dataclass to `_geometry.py` with fields: `participant_centers: dict[str, float]`, `lifeline_x: dict[str, float]`, `activation_bars: dict[str, list[tuple[float, float]]]`, `message_ys: list[float]`, `fragment_bounds: dict[str, tuple[float, float, float, float]]`, `note_bounds: list[tuple[float, float, float, float]]`, `canvas: tuple[float, float]`.
2. Add `activation_bounds_at(pid, y, act_stack)` — given current activation stack dict `{pid: [(top_y, bottom_y, depth), ...]}`, return `(cx - w/2, cx + w/2)` where `w` is the total width of nested bars for `pid` at `y`.
3. Replace the hardcoded Bezier self-message path with:
   - `loop_w = max(_MEASURER.layout(label).max_content_width + LOOP_LABEL_PAD, LOOP_MIN_W)`
   - `loop_h = max(_MEASURER.layout(label).height + MARKER_CLEARANCE, LOOP_MIN_H)`
4. Anchor at `activation_bounds_at(pid, row_y)` right edge; if no active bar, anchor at `cx`.
5. Draw label centered over the loop midpoint (not at `cx`).
6. Update marker draw calls to use the same `_draw_marker` dispatcher as straight messages.
7. Expand `_global_bbox` to include `(anchor_x + loop_w, row_y ± loop_h/2)`.
8. At the end of `_layout_lifeline`, collect geometry into a `SequenceGeometry` instance and return `(html, geometry)`. Update only `_dispatch`'s sequenceDiagram branch (`_strategies.py:~3992`) to unpack the tuple and continue returning `html`; all callers of `_dispatch` (public API, tests) are unchanged.

**Done when:** new self-message tests pass; `python3 -m pytest tests/test_fix_sequence.py -k self` green; `_layout_lifeline` returns `(str, SequenceGeometry)`.

---

### T8a: Natural horizontal layout — solver and participant/message constraints

**Depends on:** T6, T7
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `tests/test_fix_sequence.py`

**Tests:**
- Two participants with a long message label: column gap is at least `label_width + LABEL_PAD`, not just `COL_W`.
- Participant with long name: column center accounts for `name_width / 2`.
- Participant box width equals measured name width (no overflow:hidden).
- All eight original fixtures still pass geometry invariants.

**Approach:**
1. Add `_solve_col_centers(n_participants, constraints)` — longest-path over `(i, j, min_gap)` list.
2. Collect adjacent-participant and message-label constraints in a pre-pass.
3. Replace `_cx(p) = PAD_H + p_idx * col_pitch` with `_cx(p) = col_centers[p_idx]`.
4. Set participant box `width` = measured label width + `BOX_HPAD`; remove `overflow:hidden` / `text-overflow:ellipsis` from label spans.
5. After solving, compute global bbox; apply single translation to `(PAD_H, PAD_V)`.

**Done when:** `python3 -m pytest tests/test_fix_sequence.py` green with all eight original fixtures; participant box width changes visible in gallery.

---

### T8b: Natural horizontal layout — note, fragment, self-loop constraints and width_hint scaling

**Depends on:** T8a
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `tests/test_fix_sequence.py`

**Tests:**
- Spanning note: column gap between note endpoints is at least `note_width + NOTE_PAD`.
- Fragment header: column span covers at least `header_text_width`.
- Self-loop column: right edge of loop is within canvas.
- `width_hint=320`: diagram scales down uniformly (no distorted aspect ratios).
- `width_hint=800`: diagram scales up uniformly.
- All eight original fixtures still pass.

**Approach:**
1. Extend the constraint pre-pass with: spanning-note, fragment-header, and self-loop-clearance constraints.
2. After natural-size layout, apply uniform scale for `width_hint`: `scale = width_hint / natural_width`; apply to all coords and font sizes uniformly.

**Done when:** `python3 -m pytest tests/test_fix_sequence.py` green; long-label and fragment-header fixtures in gallery show correct spacing visually.

---

### T9: Semantic validation implementation

**Depends on:** T2, T4, T5, T7, T8b, T11
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `tools/compare_gallery.py`

**Tests:**
- A correct diagram returns `geometry="pass"`.
- A diagram where activation bar top ≠ trigger message y returns `geometry="fail"` with a descriptive error.
- A diagram where fragment bounds don't match participant set returns `geometry="fail"`.
- A diagram with text outside canvas bounds returns `geometry="fail"`.
- `_dispatch_validate` stub path is removed; real validation runs for sequenceDiagram.

**Approach:**
1. `_dispatch_validate` calls `_layout_lifeline` to get `(html, geometry: SequenceGeometry)`.
2. For each of the eleven invariants in the spec, check `geometry` fields and append to `errors: list[str]` if violated.
3. Return `ValidationResult(geometry="pass" if not errors else "fail", errors=tuple(errors), ...)`.
4. Wire into `_dispatch_validate` for the `sequenceDiagram` directive.

**Done when:** `python3 -m pytest tests/test_fix_sequence.py -k geometry` green; gallery shows green geometry badge for correct fixtures, red for injected-error fixture.

---

### T10: Regression fixtures — new fixture files

**Depends on:** T3, T4, T5, T7, T8b, T9, T11
**Touches:** `tests/fixtures/sequence/` (new `.mmd` files), `tests/test_fix_sequence.py` or new `tests/test_sequence_fixtures.py`

**Tests:** (the fixtures themselves are the tests — each is loaded and rendered; semantic invariants are asserted)

For each of the following, a `.mmd` fixture file is added and a corresponding test asserts no semantic-validation errors:
- `seq-nested-activations.mmd`
- `seq-unclosed-activation.mmd`
- `seq-unmatched-deactivation.mmd`
- `seq-active-self-message.mmd`
- `seq-nested-active-self-message.mmd`
- `seq-bidir-and-filled-head-arrows.mmd`
- `seq-long-participant-aliases.mmd`
- `seq-long-adjacent-labels.mmd`
- `seq-multiline-notes.mmd`
- `seq-multiline-fragment-conditions.mmd`
- `seq-nested-fragments.mmd`
- `seq-note-only-implicit-participants.mmd`
- `seq-unknown-participant-typo.mmd`
- `seq-empty-fragment.mmd`
- `seq-fragment-notes-only.mmd`
- `seq-width-hint-320.mmd`, `seq-width-hint-480.mmd`, `seq-width-hint-800.mmd`
- `seq-unsupported-create-destroy.mmd`, `seq-unsupported-box.mmd`, `seq-unsupported-autonumber.mmd`

**Done when:** `python3 -m pytest tests/test_sequence_fixtures.py` green; all twenty+ fixtures render without error; the six "unsupported" fixtures emit diagnostics and have `syntax_coverage="partial"`.

---

### T11: P2 cleanup

**Depends on:** T8a
**Touches:** `scripts/mermaid_render/layout/_strategies.py`

**Tests:**
- An unknown participant name in a message emits a `Diagnostic` (not index-0 default).
- An unmatched `deactivate` emits a `Diagnostic`.
- A rect with an embedded RGBA fill `rgba(r,g,b,a)` does not also have an SVG `opacity` attribute (no double-alpha).
- Straight message label `x` coordinate equals midpoint of the activation-adjusted segment, not the lifeline midpoint.
- After adding a tall note that extends the canvas right, the `viewBox` width includes marker bounding boxes.
- `height_hint=400` renders the diagram scaled uniformly to fit 400px tall.

**Approach:**
1. Strict participant lookup: change `_pid(name)` to return `None` for unknown names; emit `Diagnostic` and skip the event.
2. Unmatched deactivate: check that a matching open bar exists before popping; emit `Diagnostic` if not found.
3. RGBA alpha: strip any existing `opacity` attribute when the fill already encodes alpha.
4. Label centering: use activation-adjusted endpoint `x` values to compute `mid_x = (src_x + dst_x) / 2`.
5. Bounds: include half-marker-size padding in the `_global_bbox` accumulation for each drawn marker.
6. `height_hint`: after natural-size layout, compute `h_scale = height_hint / natural_height`; apply uniform scale if `h_scale < 1`.

**Done when:** `python3 -m pytest tests/test_fix_sequence.py` green; P2 test cases in T11 pass; no double-opacity in rendered HTML.

## Rollout

All changes are internal to the rendering pipeline. No flag needed — the renderer is invoked only by tests and the gallery tool. Rollback is a git revert.

## Risks

- **T7 return-type change**: changing `_layout_lifeline` from `-> str` to `-> tuple[str, SequenceGeometry]` propagates to `_dispatch` and every caller. Mitigation: change `_dispatch` to unpack the tuple immediately and continue returning `str` to external callers; `_dispatch_validate` gets the geometry separately via a shared internal function.
- **T8a regression surface**: the constraint solver replaces the core column computation; any off-by-one shifts all downstream geometry and fails many tests at once. Mitigation: implement with the eight original fixtures as a live regression suite; don't proceed to T8b until all eight pass.
- **T6 row-height changes**: switching to PillowTextMeasurer will change row heights for some notes, breaking exact-pixel assertions in `TestVariableHeightRows`. Mitigation: update those assertions to use measurer output as the expected value, not hardcoded constants.
- **T7 self-message coordinate shift**: activation-aware anchoring changes the x-position of self-loop SVG elements; `TestGeometryInvariants` assertions on self-message cross positions will need updating. Mitigation: treat the new coordinates as authoritative and update assertions to match.

## Changelog

- 2026-07-21: initial plan
- 2026-07-21: adversarial review pass — added SequenceGeometry return type to T7, split T8 into T8a/T8b, fixed T9/T10 Depends-on, added catch-all unrecognized-line diagnostic to T4, fixed T3 test references, deferred mmdc_oracle to backlog
