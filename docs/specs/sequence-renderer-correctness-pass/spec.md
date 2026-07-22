# Spec: Sequence Renderer Correctness Pass

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

Refactor the `sequenceDiagram` renderer pipeline so that parsing, layout, rendering,
and validation share a single compile result. `_layout_lifeline` is called exactly once
per `compile_sequence()` invocation; both the rendered HTML and the geometry validator
inspect the identical `SequenceGeometry` instance produced by that single call. Width/height
hints uniformly scale the complete natural-size diagram via a CSS `transform:scale()` wrapper
applied to the whole natural-coordinate output, rather than independently compressing
participant column positions. The geometry model carries typed semantic records
(`ParticipantGeometry`, `MessageGeometry`, `ActivationGeometry`, `NoteGeometry`,
`FragmentGeometry`, `BranchGeometry`) populated at the emission site. The comparison
gallery exposes independent status lanes (render, syntax, structural geometry, semantic
geometry, mmdc oracle) and metadata.json records file hashes and per-fixture dimensions.
The `validate()` public-API signature in `__init__.py` is unchanged.

## Boundaries

### Always do

- Retain full backward compatibility for the existing 163 sequence tests.
- Emit `SequenceDiagnostic` for every unsupported or unrecognised construct rather
  than silently discarding source lines.
- Run the full repository test suite before declaring done.
- Write failing tests before each fix (TDD red-green).
- `_layout_lifeline` is called exactly once per `compile_sequence()` call.

### Ask first

- Any change to the public API signature of `to_html`, `to_svg`, `to_png`, or
  `validate` in `scripts/mermaid_render/__init__.py`.
- Removing or renaming existing fields from `SequenceGeometry` in a way that would
  break external callers without a deprecation alias in the same PR.

### Never do

- Add a new top-level Python package dependency.
- Change the Playwright DOM path or the native SVG backend dispatch outside the
  sequence-diagram code path.
- Use pixel-exact comparison to mmdc output; compare semantic relationships only.
- Rewrite the flowchart / erDiagram / classDiagram / gantt / timeline renderers.
- Change `validate(src)` to accept width_hint/height_hint — that is an Ask-first action.
  Multi-width dimension checks are made through `compile_sequence()` only.

## Testing Strategy

All behavior covered by TDD. Tests live in:

- `tests/test_fix_sequence.py` — regression and geometry tests (existing + new)
- `tests/test_syntax_sequence.py` — syntax-coverage smoke tests (existing + new)
- `tests/test_sequence_geometry.py` (new) — typed geometry IR and validation unit tests

Per-AC verification modes:

| AC group | Mode | Rationale |
|---|---|---|
| Compile-once (AC-1) | TDD — spy `_layout_lifeline` call count + geometry hash | Identity across a pure-function call isn't preserved; spy is the reliable signal |
| Uniform scaling (AC-2) | TDD | Regex-parse `sequence-natural-stage` inner coords and outer wrapper |
| Typed geometry IR (AC-3) | TDD | Assert typed record fields populated |
| Structural validation (AC-4 structural) | TDD | Inject bad geometry; assert violations detected |
| Semantic validation (AC-4 semantic) | TDD | Known-correct diagram; assert semantic_geometry == "pass" |
| Self-message (AC-5) | TDD | Assert activation anchoring and bounds |
| Variable heights (AC-6) | TDD | Compare canvas heights across short/long labels |
| Branch parent fix (AC-7) | TDD | Assert parent_fragment_id non-empty and in fragment set |
| Arrow grammar (AC-8) | TDD — parametrize all 10 tokens | |
| Diagnostics (AC-9) | TDD | Existing syntax tests extended |
| Gallery lanes (AC-10) | goal-based — grep generated index.html for lane labels | |
| Gallery provenance (AC-10.2) | goal-based — verify metadata.json keys | |
| mmdc oracle (AC-11) | goal-based — lane renders without crashing | |
| height_hint scaling (AC-2 / P2#8) | TDD — same as uniform scaling | |
| Regression fixtures (AC-R) | TDD — per-fixture expected status table | |

## Acceptance Criteria

### Phase 1 — Compile-once result

- [ ] AC-1.1 `SequenceCompileResult` frozen dataclass exists in `_geometry.py` with fields:
  `html: str`, `geometry: SequenceGeometry`, `diagnostics: tuple[SequenceDiagnostic, ...]`,
  `syntax_coverage: str`, `natural_width: float`, `natural_height: float`,
  `scale: float`, `rendered_width: float`, `rendered_height: float`.
- [ ] AC-1.2 `compile_sequence(source, *, width_hint=0, height_hint=0, theme=None) -> SequenceCompileResult`
  exists in `_strategies.py` and calls `_layout_lifeline` exactly once.
- [ ] AC-1.3 `_dispatch_validate` for sequenceDiagram calls `compile_sequence()` and does
  not call `_layout_lifeline` directly.
- [ ] AC-1.4 A test spies on `_layout_lifeline` (via `unittest.mock.patch`) and asserts it
  is called **exactly once** per `compile_sequence()` call at any width_hint.
- [ ] AC-1.5 At width_hint 0, 320, 480, 800: `compile_sequence()` returns a result whose
  `rendered_width` matches the outer viewport div's `width:` CSS value in `.html`.
  (These checks go through `compile_sequence()`, not through `validate()`.)

### Phase 2 — Uniform scaling

- [ ] AC-2.1 When `scale < 1.0`, the rendered HTML contains a `sequence-viewport` div with
  `width:{rendered_width}px` and an inner `sequence-natural-stage` div with
  `transform:scale({scale})` and `width:{natural_width}px`.
- [ ] AC-2.2 The inner `sequence-natural-stage` coordinates are **identical** to the
  coordinates produced at `width_hint=0` (test: render at width_hint=0, record participant
  box positions; render at width_hint=320, parse inner-stage positions; assert equal ±1px).
- [ ] AC-2.3 When `width_hint >= natural_width` or `width_hint == 0`, scale is 1.0 and no
  `transform:scale()` wrapper is emitted.
- [ ] AC-2.4 The natural bounds union used to compute `natural_width` / `natural_height`
  includes: top+bottom participant boxes, lifelines, message paths, markers, activation bars,
  notes, fragments, branch separators, self-loops. (Tests: diagrams with each element type
  produce natural_width > canvas_w − 2*PAD_H.)
- [ ] AC-2.5 height_hint scales the diagram uniformly: `scale = min(1.0, width_hint/natural_width, height_hint/natural_height)` when both hints are supplied; either hint alone uses its own ratio capped at 1.0.

### Phase 3 — Typed geometry IR

- [ ] AC-3.1 `_geometry.py` defines frozen dataclasses: `Bounds(left,top,right,bottom)`,
  `ParticipantGeometry`, `MessageGeometry`, `ActivationGeometry`, `NoteGeometry`,
  `FragmentGeometry`, `BranchGeometry`.
- [ ] AC-3.2 `SequenceGeometry` contains typed tuples of the records above. The old
  float-tuple fields (`participant_centers`, `message_endpoints`, etc.) remain as
  deprecated aliases pointing at the same data until removed in a follow-up PR.
- [ ] AC-3.3 Every `ParticipantGeometry` is populated with: `participant_id`, `label`,
  `center_x`, `top_box: Bounds`, `bottom_box: Bounds`, `lifeline_top`, `lifeline_bottom`.
- [ ] AC-3.4 Every `MessageGeometry` carries: `event_id`, `source_id`, `destination_id`,
  `baseline_y`, `source_x`, `destination_x`, `label_x: float`, `path_bounds: Bounds`,
  `label_bounds: Bounds | None`, `start_marker: str | None`, `end_marker: str | None`,
  `is_self_message: bool`, `arrow_token: str`.
- [ ] AC-3.5 Every `ActivationGeometry` carries: `activation_id`, `participant_id`,
  `start_y`, `end_y`, `depth: int`, `bounds: Bounds`, `was_implicitly_closed: bool`.
- [ ] AC-3.6 Every `NoteGeometry`, `FragmentGeometry`, `BranchGeometry` carries its
  semantic IDs and a `bounds: Bounds`.
- [ ] AC-3.7 `scale` and `natural_bounds: Bounds` live on `SequenceCompileResult`, not
  duplicated onto `SequenceGeometry`. `SequenceGeometry` remains coordinate-only.

### Phase 4 — Structural and semantic geometry validation

- [ ] AC-4.1 `validate_sequence_geometry(geom: SequenceGeometry) -> SequenceValidationResult`
  exists with lanes: `structural_geometry`, `semantic_geometry`, `diagnostics`, `errors`, `warnings`.
- [ ] AC-4.2 Structural checks: positive dimensions; participant centers strictly ordered;
  adjacent participant boxes do not overlap; message baselines non-decreasing; every primitive
  within rendered bounds ±2px epsilon; activation/fragment/branch bounds non-inverted.
- [ ] AC-4.3 Semantic checks: activation start_y ≤2px from triggering message baseline_y;
  activation end_y ≤2px from closing message baseline_y; `was_implicitly_closed` activations
  extend to `lifeline_bottom`; fragment `participant_ids` equals the set of participants
  touched by descendant events; branch `parent_fragment_id` non-empty and in fragment_id set;
  note participants are registered.
- [ ] AC-4.4 Unmatched deactivate → `SequenceDiagnostic(code="unmatched_deactivate",
  severity="warning")`. Test: `"deactivate A"` with no prior activate → diagnostic in result.
- [ ] AC-4.5 All unknown-participant code sites — the message-emission skip-guards
  (grep: `"row += 1; continue"` near sender lookup) and the `_box_hw`/`_cx` coord helpers
  (grep: `"\.get(pid, 0)"`) — emit `SequenceDiagnostic(code="unknown_participant", severity="error")`
  rather than silently defaulting to index 0 or skipping without trace. Both are defensive
  hardening: all pids are auto-registered through parsing, so these sites are currently
  unreachable by user input. They are verified via direct unit tests on each isolated code path
  (see AC-9.3 for the coord-helper unit test; T9 adds a skip-guard unit test).

### Phase 5 — Self-message geometry

- [ ] AC-5.1 Self-message anchor `source_x` = `activation_bounds_at(pid, y)[1]` when active,
  else lifeline center_x.
- [ ] AC-5.2 Self-message loop width = `max(MIN_LOOP_W, label_width + 2*HPAD)`.
- [ ] AC-5.3 Self-message loop height = `max(MIN_LOOP_H, label_height + 2*VPAD)`. Row height
  grows to accommodate the loop.
- [ ] AC-5.4 Self-message on the rightmost participant expands `natural_width` to contain the
  full loop right edge.
- [ ] AC-5.5 `MessageGeometry.is_self_message == True` and `path_bounds` is populated.
- [ ] AC-5.6 Bidirectional self-message (`<<->>`) renders both start and end markers.

### Phase 6 — Variable event heights for all event types

- [ ] AC-6.1 Message row height = `max(MIN_MESSAGE_H, label_height + LABEL_GAP + BOT_PAD)`.
- [ ] AC-6.2 Fragment-start row height = `max(MIN_FRAGMENT_H, header_text_height + 2*FRAG_PAD_Y)`.
- [ ] AC-6.3 Branch (else/and/option) row height = `max(MIN_BRANCH_H, branch_label_h + 2*BRANCH_PAD_Y)`.
- [ ] AC-6.4 `overflow:hidden` and `text-overflow:ellipsis` are absent from participant
  labels and message-label spans in sequence output (grep confirms).
- [ ] AC-6.5 Multiline message labels, multiline fragment conditions, multiline branch labels,
  and long fragment-header text each produce a taller canvas than the short-label equivalent.

### Phase 7 — Branch parent association fix

- [ ] AC-7.1 A `_branch_parent_id: dict[int, str]` is populated during the block prepass
  (not reconstructed from the stack during emission).
- [ ] AC-7.2 `BranchGeometry.parent_fragment_id != ""` for every branch.
- [ ] AC-7.3 `BranchGeometry.parent_fragment_id` is in the known fragment_id set.
- [ ] AC-7.4 Branch separator `bounds.left` == parent fragment `bounds.left` ± 2px;
  `bounds.right` == parent fragment `bounds.right` ± 2px.

### Phase 8 — Complete arrow grammar

- [ ] AC-8.1 `MarkerKind` enum and `ArrowSpec(token, dashed, start_marker, end_marker)` frozen
  dataclass are defined in `_geometry.py`.
- [ ] AC-8.2 The complete Mermaid 11.15 token set is covered: `->`, `-->`, `->>`, `-->>`,
  `-x`, `--x`, `-)`, `--)`, `<<->>`, `<<-->>`.
- [ ] AC-8.3 A token absent from `ARROW_SPECS` produces `SequenceDiagnostic(code="unsupported_arrow")`
  and falls back to a solid no-marker line (not a crash, not a silent wrong marker).
- [ ] AC-8.4 Parametrised tests cover all 10 tokens asserting `dashed`, `start_marker`,
  `end_marker` fields.

### Phase 9 — No silently discarded syntax

- [ ] AC-9.1 `SequenceDiagnostic` frozen dataclass exists in `_geometry.py` with:
  `severity: Literal["info","warning","error"]`, `code: str`, `feature: str | None`,
  `line_number: int | None`, `source_text: str | None`, `message: str`.
- [ ] AC-9.2 Every non-blank non-comment source line resolves to a supported AST node,
  a documented no-op, a `SequenceDiagnostic`, or a syntax error.
- [ ] AC-9.3 The `_box_hw` and `_cx` coord helpers are hardened as a **defensive invariant**:
  both `.get(pid, 0)` sites (grep: `"\.get(pid, 0)"` in `_strategies.py`) are replaced with
  strict dict lookup + `SequenceDiagnostic(code="unknown_participant")` + fallback return.
  These sites are currently unreachable through parsing (all message/note/activation pids are
  auto-registered before the helpers are called), so this is defensive hardening, not a live
  bug fix. `test_unknown_participant_helper_emits_diagnostic_not_index_zero` exercises the
  helpers directly. See AC-4.5 for the skip-guard diagnostic at the actual live trigger site.
- [ ] AC-9.4 `syntax_coverage == "partial"` whenever any `SequenceDiagnostic` is emitted.
- [ ] AC-9.5 `syntax_coverage == "pass"` when no diagnostics are emitted.

### Phase 10 — Gallery provenance and status lanes

- [ ] AC-10.1 `compare_gallery.py` `_assert_module_provenance` exits non-zero if
  `mermaid_render` is not from the checked-out repo.
- [ ] AC-10.2 `metadata.json` includes: git SHA, git dirty state, SHA256 of `_strategies.py`,
  `_geometry.py`, `_text.py`; natural/rendered dimensions; scale; diagnostics per fixture.
- [ ] AC-10.3 Gallery `index.html` shows five independent status lanes per fixture:
  `render`, `syntax`, `structural_geometry`, `semantic_geometry`, `mmdc_oracle`.
- [ ] AC-10.4 `--strict` flag fails the process when any fixture has render≠pass,
  syntax≠pass, structural_geometry≠pass, or any error-severity diagnostic.
- [ ] AC-10.5 Gallery is generated into a sibling temp directory and **atomically renamed**
  to the output directory only after every artifact is written. A failed run leaves the
  previous output intact. Test: interrupt mid-generation; assert old output unchanged.

### Phase 11 — mmdc semantic comparison (basic)

- [ ] AC-11.1 `mmdc_oracle` lane extracts participant count, message count, activation rects,
  note polygons from mmdc SVG and compares against `SequenceGeometry` counts.
- [ ] AC-11.2 Comparison normalises coordinates (relative order, not absolute pixels) before
  comparing; font/theme/padding differences are not reported as mismatches.
- [ ] AC-11.3 Mismatches are reported individually (e.g. "participant count mismatch: 3 vs 2")
  not as one undifferentiated oracle failure.

### P2 Cleanup

- [ ] AC-P2.1 The inline comment `# Phase 4 will wire per-type validation` at
  `__init__.py:146` is removed and replaced with the actual behavior description.
- [ ] AC-P2.2 `rect` fill with `rgba()` does not also carry an `opacity=` attribute
  (double-alpha bug). Test: `rect rgba(0,200,0,0.3)` → no `opacity=` on that SVG rect.
- [ ] AC-P2.3 Message labels are centered over the activation-adjusted segment midpoint
  `(source_x + destination_x) / 2`, not over bare lifeline centers.

### Regression fixtures

- [ ] AC-R.1 All 163 existing sequence tests pass.
- [ ] AC-R.2 New regression fixture files in `tests/fixtures/`:

  | Fixture | Expected render | Expected syntax | Expected structural_geometry |
  |---|---|---|---|
  | `sequence-width-320.mmd` | pass | pass | pass |
  | `sequence-width-480.mmd` | pass | pass | pass |
  | `sequence-width-800.mmd` | pass | pass | pass |
  | `sequence-long-participants.mmd` | pass | pass | pass |
  | `sequence-multiline-message.mmd` | pass | pass | pass |
  | `sequence-nested-fragments.mmd` | pass | pass | pass |
  | `sequence-nested-activations.mmd` | pass | pass | pass |
  | `sequence-unclosed-activation.mmd` | pass | partial | pass |
  | `sequence-unmatched-deactivate.mmd` | pass | partial | pass |
  | `sequence-active-self-message.mmd` | pass | pass | pass |
  | `sequence-middle-participant-self-message.mmd` | pass | pass | pass |
  | `sequence-bidirectional-self-message.mmd` | pass | pass | pass |
  | `sequence-full-arrow-token-matrix.mmd` | pass | pass | pass |
  | `sequence-unknown-participant.mmd` | pass | pass | pass |
  | `sequence-autonumber-unsupported.mmd` | pass | partial | pass |
  | `sequence-critical-option.mmd` | pass | pass | pass |
  | `sequence-rect.mmd` | pass | pass | pass |
  | `sequence-multiline-note.mmd` | pass | pass | pass |
  | `sequence-multiline-fragment.mmd` | pass | pass | pass |

- [ ] AC-R.3 Each fixture's `structural_geometry` and `syntax_coverage` match the expected
  columns above (both asserted by the T12 parametrised test).

**Explicitly deferred to `docs/backlog.md`:**
- `sequence-box-unsupported.mmd` — box grouping visual fidelity vs mmdc
- `sequence-create-destroy.mmd` — create/destroy markers (complex)
- `sequence-single-participant-fragment-long-header.mmd` — P2 cleanup #5
- `sequence-note-only-implicit-participant.mmd` — covered by existing SEQ-014 test

## Assumptions

- **Technical**: Runtime is Python 3.13.13 (`python3 --version → Python 3.13.13`)
- **Technical**: Baseline is 163 passing sequence tests (run confirmed 2026-07-21)
- **Technical**: `_dispatch_validate` hardcodes `_layout_lifeline(clean, "LR", 900)` — `_strategies.py:4815`
- **Technical**: All unknown-participant sites in `_strategies.py` — both the `.get(pid, 0)`
  coord helpers and the `row += 1; continue` skip-guards — are defensive hardening; they are
  currently unreachable through parsing since all pids are auto-registered. Verified via direct
  unit tests on each site.
- **Technical**: `loop-cohort.py` available at `.claude/skills/work-loop/scripts/loop-cohort.py`
- **Product**: user confirmation 2026-07-21 — spec from `.context/attachments/3G1u18/…`
- **Process**: user confirmation 2026-07-21 — "do this in the work-loop"
- **Process**: `validate()` public signature is Ask-first; multi-width checks go through `compile_sequence()` only
