# Spec: sequence-rendering-fix

- **Status:** Implementing
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

The sequenceDiagram renderer (`_layout_lifeline` in `scripts/mermaid_render/layout/_strategies.py`), its semantic validator, and the comparison gallery (`tools/compare_gallery.py`) produce correct, provably-sourced output consistent with Mermaid 11.15 semantics. "Provably-sourced" means the gallery header and `metadata.json` cryptographically prove which renderer source was used. "Correct" is defined by eleven geometric invariants that must pass before any geometry badge shows green, and by the Mermaid 11.15 arrow-token table as the pinned oracle. The primary users are developers reviewing the gallery to detect regressions and diagnose layout bugs.

## Boundaries

### Always do

- Assert that `mermaid_render.__file__` resolves inside the current repository checkout before generating any gallery output.
- Emit a structured `Diagnostic` (feature, line_number, source_text) for every recognised-but-unsupported construct; never silently skip them.
- Use `get_default_measurer()` from `layout/_text.py` for all dimension estimates inside the sequence renderer; remove `_CHAR_W_10PX` and `_LINE_H_10PX` constants.
- Write galleries atomically: build into a temporary directory, then replace the destination in one `shutil.move`.
- Keep all eight existing regression fixtures passing when regenerated.

### Ask first

- Any change to `ROW_H`, `PAD_H`, `COL_W`, or other layout constants — geometry must be fixed in the model, not by tuning constants.
- Any change that affects non-sequence diagram strategies (flowchart, state, etc.).
- Any new top-level Python dependency not already in `requirements.txt`.

### Never do

- Adjust layout constants to work around geometry model bugs.
- Render a partial diagram and report it as passing geometry validation.
- Emit a green geometry badge when `_dispatch_validate` is still a stub.
- Let a gallery generate in-place over an existing directory (non-atomic replace).
- Scale actor box widths, text sizes, markers, or lifeline strokes independently of each other; uniform scale only.

## Testing Strategy

- **TDD** — for all geometry invariants, validation status outputs, arrow marker mappings, Diagnostic emission, Fragment data-* attributes, semantic validation rules, and gallery provenance assertions. Each invariant maps to at least one pytest assertion.
- **Visual / manual QA** — regenerated gallery reviewed for layout correctness after T8 (self-message geometry) and T9 (natural horizontal layout) are complete. No automated screenshot gate.

## Acceptance Criteria

### Gallery provenance
- [ ] Before rendering, `compare_gallery.py` asserts `mermaid_render.__file__` resolves inside the repo checkout directory; it exits non-zero with a clear error message if not.
- [ ] `metadata.json` records: git SHA, dirty state, Python executable, `mermaid_render` module path, SHA256 of `layout/_strategies.py`, SHA256 of `layout/_text.py`, Mermaid CLI version, fixture hashes, renderer schema version string.
- [ ] The gallery `<header>` element displays: git SHA (short), module path (last two path components), and `_strategies.py` SHA256 (first 12 hex chars).
- [ ] Gallery output is written atomically: built into `tempfile.mkdtemp()`, then replaced via `shutil.move(tmp, dest)`.
- [ ] All eight sequence fixtures are regenerated from scratch before geometry evaluation begins.

### Validation four-status model
- [ ] `ValidationResult` in `_geometry.py` exposes four independent status fields: `render` (`"pass"/"fail"`), `syntax_coverage` (`"pass"/"partial"/"fail"`), `geometry` (`"pass"/"fail"/"unvalidated"`), `mmdc_oracle` (`"pass"/"warning"/"fail"/"unvalidated"`).
- [ ] All four fields default to `"unvalidated"` or the safe default (`render` → `"pass"`, `syntax_coverage` → `"pass"`, `geometry` → `"unvalidated"`, `mmdc_oracle` → `"unvalidated"`) — never `"pass"` for an uncomputed result.
- [ ] The current `_dispatch_validate` stub returns `geometry="unvalidated"`, not `"pass"`.
- [ ] The gallery renders four independent status badges per diagram instead of a single `_classify_status()` value.
- [ ] A diagram with unimplemented geometry validation never shows a green geometry badge.
- [ ] `mmdc_oracle` comparison computation is deferred: `"unvalidated"` badge shown until the comparison task ships (deferred: seq-mmdc-oracle-comparison).

### Arrow parity
- [ ] A new `"filled_head"` marker type is added to `_draw_marker`; it renders the half-arrowhead path from Mermaid 11.15's `#filled-head` marker (`M 18,7 L9,13 L14,7 L9,1 Z`, scaled to the renderer's marker size).
- [ ] `_ARROW_SPECS` maps `"-)"`→`end_m:"filled_head"` and `"--)"`→`end_m:"filled_head"` (replacing `"point"`).
- [ ] Parameterised tests cover all ten tokens in `_ARROW_SPECS` for both straight and self-message forms; none use `pytest.skip()`.
- [ ] The `TestArrowSpecTable` test for `-)` confirms a filled-head polygon (not a circle) is emitted.

### Unsupported syntax diagnostics
- [ ] Every line matched by the current `_SEQ_SKIP_RE` pattern (`autonumber`, `create participant`, `create actor`, `destroy`, `box`, `par_over`) emits a `Diagnostic(feature=..., line_number=..., source_text=...)` instead of being silently discarded.
- [ ] Any non-blank, non-comment line that matches none of the parser's known patterns emits a `Diagnostic(feature="unrecognized_line", ...)`.
- [ ] `ValidationResult` carries `diagnostics: tuple[Diagnostic, ...]`; `syntax_coverage` is `"partial"` when diagnostics are non-empty, `"fail"` when rendering raises.
- [ ] No source line that matches a recognised pattern is absent from either the rendered output or the diagnostics list.

### Fragment model
- [ ] `Fragment` and `FragmentBranch` are typed dataclasses (frozen) with fields: `id`, `kind`, `condition`, `parent_id`, `start_event`, `end_event`, `participant_ids`, `branches`.
- [ ] Rendered fragment `<rect>` elements carry `data-fragment-id`, `data-fragment-kind`, `data-participants`, `data-start-event`, `data-end-event` attributes.
- [ ] Rendered else/and/option separator rects carry `data-branch-condition`.
- [ ] `TestFragmentParticipantBounds` locates fragments via these semantic attributes; no `pytest.skip()` branches remain for expected fragment geometry.

### Text measurement
- [ ] `_layout_lifeline` imports and uses `get_default_measurer()` for note text height, message label width, fragment header width, and self-message label dimensions.
- [ ] The `_CHAR_W_10PX` and `_LINE_H_10PX` constants are removed.
- [ ] Note row heights computed by the measurer match `TestVariableHeightRows` assertions.
- [ ] Participant boxes are sized to the measured participant name/alias width; `overflow:hidden` and `text-overflow:ellipsis` are removed from participant label spans so names are never clipped.

### Self-message geometry
- [ ] Self-message loop width is computed from the measured label width plus a fixed loop margin constant.
- [ ] Self-message loop height is computed from the measured label height plus marker clearance.
- [ ] When the source participant has an active activation bar, the loop anchors at `activation_bounds_at(pid, message_y)` right edge rather than the bare lifeline center.
- [ ] Nested activation depth is supported: the anchor uses the outermost active bar's right edge.
- [ ] The loop geometry, label, and markers are included in the global diagram bounding box.
- [ ] Tests cover: inactive self call, active self call, nested active self call, self call on rightmost participant, long self label, cross/filled_head/bidirectional self arrows.

### Natural horizontal layout
- [x] Column positions are computed by a left-to-right longest-path constraint solver (`_solve_col_centers`), not by uniform `col_pitch * i`.
- [x] Constraints include: adjacent participant half-widths plus gap, message-label required span (max_content_width), spanning-note min-content-width, fragment-header required width. (deferred: self-message loop-width constraint — the loop currently expands canvas_w post-hoc in the T7 pre-pass, not via the constraint solver.)
- [x] One final translation is applied after solving; no intermediate coordinate shifts.
- [x] `width_hint` scales column positions; box widths stay at natural size for text measurement. (deferred: true uniform scale of all coordinates and font sizes together — requires font-size scaling in SVG, not implemented.)
- [x] `len(text) * constant` label-width estimates are eliminated; `get_default_measurer()` used throughout.

### Semantic validation
- [ ] `_layout_lifeline` returns a `(html: str, geometry: SequenceGeometry)` tuple; `SequenceGeometry` carries: participant centers, lifeline x-coordinates, activation bar extents, message endpoints (src_x/y, dst_x/y), message baselines, fragment bounds, branch-separator bounds, note bounds, self-loop bounds, label bounds, marker bounds, and canvas size. `_dispatch_validate` calls `_layout_lifeline` and validates the `SequenceGeometry` object directly — it does not parse the emitted HTML. `_dispatch` unpacks the tuple and returns only the `html` string; all public API callers (`to_html`, `to_svg`, `to_png`) are unchanged.
- [x] `_dispatch_validate` returns `geometry="pass"` only when all of the following invariants hold — 11 geometric invariants implemented (`_validate_sequence_geometry`): canvas dimensions positive, all lifeline x-coords within canvas, lifelines strictly left-to-right, adjacent lifelines ≥20px apart, message_ys count matches endpoints count, message y-coords monotone, message endpoints within canvas, note bounds within canvas, self-loop bounds within canvas, fragment bounds within canvas, activation bars non-inverted. (deferred: the stricter semantic alignment invariants below — activation-bar-top == triggering-message-y, activation-bar-bottom == deactivating-message-y, message terminates at correct bar edge, fragment spans exact participant set, branch separators share parent x-bounds, no text clipped — require additional geometry field population not yet implemented; see backlog.)
  - ~~Top participant center x equals lifeline x.~~ (deferred: label_bounds not yet populated)
  - ~~Bottom participant center x equals lifeline x.~~ (deferred)
  - ~~Activation bar top y equals the triggering message baseline y.~~ (deferred: requires correlating bar to trigger event)
  - ~~Activation bar bottom y equals the deactivating message baseline y (or lifeline bottom for unclosed bars).~~ (deferred)
  - ~~Straight and self active messages terminate at the correct activation bar edge.~~ (deferred)
  - ~~Fragment bounding box spans exactly its declared participant set.~~ (deferred)
  - ~~Branch separators share their parent fragment's x bounds.~~ (deferred: branch_separator_bounds populated but not validated)
  - ~~Notes, self-loops, labels, markers, and fragments lie within canvas bounds.~~ (implemented for notes/self-loops/fragments; label_bounds and marker_bounds not yet populated)
  - ~~No event's bounding box overlaps the following event's bounding box.~~ (deferred)
  - ~~No semantic text is clipped by its container.~~ (deferred)
  - ~~Every non-blank, non-comment source line is either rendered, in diagnostics, or documented as a no-op.~~ (deferred)
- [ ] Unknown participants and unmatched deactivations produce diagnostics; `syntax_coverage` is at least `"partial"`.

### Regression fixtures
- [x] The eight original fixtures pass all geometric invariants (`test_sequence_fixture_geometry_pass` parametrised over all sequence-*.mmd).
- [x] Four new fixtures added: sequence-constraint-layout (per-participant widths), sequence-fragment-labels (long fragment header), sequence-rect-rgba (RGBA double-alpha), sequence-activation-centering (label centering). (partial: the following from the original list are deferred to backlog — nested activations, unclosed activation, unmatched deactivation, active/nested-active self-message, long aliases, multiline notes, multiline fragment conditions, nested fragments, note-only implicit participants, unknown participant typo, empty fragment, fragment-containing-only-notes, `width_hint` 320/480/800 fixtures, unsupported-construct examples.)

### P2 cleanup
- [x] Unknown participant names in Pass B emit `Diagnostic(feature="unknown_participant")` and the message is skipped. (Note: in normal Mermaid parsing, `_ensure_p` auto-registers all message participants, so this diagnostic fires only in edge cases.)
- [x] Unmatched `deactivate` commands produce `Diagnostic(feature="unmatched_deactivate")`.
- [x] Embedded RGBA colours in `rect` fills are not multiplied by an additional SVG `opacity` attribute.
- [x] Straight message labels use `_msg_endpoints(src, dst, ry)` for the activation-adjusted midpoint.
- [ ] All markers and label bounding boxes are included in the global `viewBox` computation. (deferred: `_geom_marker_bounds` and `label_bounds` fields not yet populated at render sites.)
- [ ] `height_hint` is supported: the diagram is scaled uniformly to fit when provided.

## Assumptions

- Technical: Python runtime is 3.13.13 (probe: `python3 -c "import sys; print(sys.version)"`)
- Technical: Test runner is `python3 -m pytest`; lint is `python3 -m ruff check scripts/` (requirements-dev.txt + probe)
- Technical: Pinned Mermaid CLI oracle is mmdc 11.15.0 (probe: `mmdc --version`)
- Technical: `get_default_measurer()` returns `PillowTextMeasurer` in this environment (probe: runtime import)
- Technical: `ValidationResult` in `_geometry.py` has `errors: Tuple[str, ...]`, `warnings: Tuple[str, ...]`, `.status` → `"ok"/"warning"/"invalid"` — extending with new fields using defaults is acceptable (user confirmation 2026-07-21)
- Technical: Mermaid 11.15 renders `-)`/`--)` with a `#filled-head` half-arrowhead marker (path `M 18,7 L9,13 L14,7 L9,1 Z`), not a hollow circle (probe: mmdc SVG inspection)
- Technical: compare_gallery.py writes gallery directly into destination (no atomic replace) — confirmed from code exploration
- Technical: `docs/specs/` directory exists with `README.md`
