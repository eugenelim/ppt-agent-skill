# Plan: Sequence Renderer Correctness Pass

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially,
> note why in the changelog at the bottom.

## Approach

Implement in order: T1 → T3a → T3b → T2 → T5 → T6 → T7 → T4 → T8 → T9 → T10 → T11 → T12.
T2 depends on T3b (not T3a); T4 depends on T3b and T7 (branch invariants need T7 first).

Primary files: `_geometry.py` (new dataclasses), `_strategies.py` (compile_sequence + full
`_layout_lifeline` refactor), `__init__.py` (thin wrappers unchanged), `compare_gallery.py`
(status lanes, provenance), `tests/test_sequence_geometry.py` (new), `tests/test_fix_sequence.py`
(extended).

**Highest-risk item — T2 (CSS-transform wrapper)**: Before implementing T2, grep all 163
sequence tests for render widths below natural size. Specifically:
- `test_fix_sequence.py` renders at `width=800` (default in `_render()`); natural widths of
  most fixtures are under 800 → **no compression today at width=800**, so existing tests
  assert natural-coordinate positions.
- Any fixture wider than 800px natural would be compressed today. Mitigation: at width_hint=800,
  all current fixtures render without scaling. T2 only adds the CSS wrapper when
  `width_hint < natural_width`; at width_hint=800 with a narrower natural diagram, scale=1.0
  and no wrapper is emitted.
- Risk remains for T2 tests that explicitly render at small widths (320, 480). Those tests
  are new and will be written to parse inner-stage coordinates, not outer wrapper dimensions.

## Constraints

- No new Python package dependencies.
- Existing 163 sequence tests stay green after every task.
- `to_html`, `to_svg`, `to_png`, `validate` signatures in `__init__.py` unchanged.
- `_layout_lifeline` is called exactly once per `compile_sequence()` invocation.

## Construction tests

Cross-cutting: after all tasks, `python -m pytest tests/ -q --tb=short` must exit 0.

---

## Tasks

### T1 — SequenceCompileResult + SequenceDiagnostic + compile_sequence()

**Implements:** AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-1.5, AC-9.1
**Depends on:** none
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_geometry.py`, `scripts/mermaid_render/layout/_strategies.py`

**Tests:**
```python
# tests/test_sequence_geometry.py

from unittest.mock import patch

def test_compile_sequence_returns_compile_result():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: hi")
    assert isinstance(r, SequenceCompileResult)
    assert r.html and r.geometry
    assert r.natural_width > 0 and r.natural_height > 0

def test_layout_lifeline_called_exactly_once_per_compile():
    with patch("mermaid_render.layout._strategies._layout_lifeline",
               wraps=_layout_lifeline) as spy:
        compile_sequence("sequenceDiagram\n  A->>B: hi", width_hint=480)
        assert spy.call_count == 1

def test_rendered_width_matches_html_width_hint():
    for wh in (0, 320, 480, 800):
        r = compile_sequence("sequenceDiagram\n  A->>B: hi", width_hint=wh)
        if wh > 0:
            assert r.rendered_width == wh
        else:
            assert r.rendered_width == r.natural_width

def test_dispatch_validate_uses_compile_sequence_not_layout_lifeline():
    """_dispatch_validate must not call _layout_lifeline directly."""
    with patch("mermaid_render.layout._strategies._layout_lifeline",
               wraps=_layout_lifeline) as spy:
        _dispatch_validate("sequenceDiagram\n  A->>B: hi")
        # The call must come via compile_sequence, but only once
        assert spy.call_count == 1

def test_sequence_diagnostic_fields():
    r = compile_sequence("sequenceDiagram\n  autonumber\n  A->>B: hi")
    d = r.diagnostics[0]
    assert hasattr(d, "severity") and d.severity in ("info","warning","error")
    assert hasattr(d, "code") and d.code
    assert hasattr(d, "message")
```

**Approach:**
1. Add `SequenceDiagnostic` frozen dataclass to `_geometry.py`:
   `severity, code, feature, line_number, source_text, message`.
2. Add `SequenceCompileResult` frozen dataclass to `_geometry.py`.
3. In `_strategies.py`, add `compile_sequence(source, *, width_hint=0, height_hint=0, theme=None)`:
   - Calls `_layout_lifeline(clean, direction, width_hint)` exactly once.
   - Packages `(html, geom)` into `SequenceCompileResult`.
   - Sets `natural_width`, `natural_height` from `geom.canvas` (pre-scaling coords).
   - Sets `scale=1.0`, `rendered_width=natural_width` initially (T2 will fill scale).
4. Rewrite `_dispatch` for sequenceDiagram to call `compile_sequence().html`.
5. Rewrite `_dispatch_validate` for sequenceDiagram to call `compile_sequence()`.

**Done when:** all 5 tests pass + 163 existing sequence tests pass.

---

### T3a — New typed geometry dataclasses (additive)

**Implements:** AC-3.1, AC-3.7
**Depends on:** T1
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_geometry.py`

**Tests:**
```python
def test_bounds_dataclass_exists():
    b = Bounds(left=0, top=0, right=100, bottom=50)
    assert b.right - b.left == 100

def test_participant_geometry_fields():
    pg = ParticipantGeometry(
        participant_id="Alice", label="Alice", center_x=100.0,
        top_box=Bounds(50,20,150,60), bottom_box=Bounds(50,400,150,440),
        lifeline_top=60.0, lifeline_bottom=400.0,
    )
    assert pg.participant_id == "Alice"
```

**Approach:**
1. Add to `_geometry.py`: `Bounds`, `ParticipantGeometry`, `MessageGeometry`,
   `ActivationGeometry`, `NoteGeometry`, `FragmentGeometry`, `BranchGeometry`.
2. Do **not** yet change `SequenceGeometry` — that is T3b.
3. No changes to `_strategies.py` in this task.

---

### T3b — Populate typed geometry records in _layout_lifeline

**Implements:** AC-3.2, AC-3.3, AC-3.4, AC-3.5, AC-3.6
*(Note: `label_x` field added to `MessageGeometry` per AC-3.4; populated in T6 with activation-adjusted midpoint.)*
**Depends on:** T3a
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `scripts/mermaid_render/layout/_geometry.py`

**Tests:**
```python
def test_participant_geometry_populated():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: hi")
    assert len(r.geometry.participants) == 2
    alice = r.geometry.participants[0]
    assert alice.participant_id == "Alice"
    assert alice.center_x > 0
    assert alice.top_box.left < alice.center_x < alice.top_box.right

def test_message_geometry_populated():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: hi")
    assert len(r.geometry.messages) == 1
    msg = r.geometry.messages[0]
    assert msg.source_id == "Alice" and msg.destination_id == "Bob"
    assert msg.baseline_y > 0 and msg.arrow_token == "->>"

def test_activation_geometry_was_implicitly_closed():
    r = compile_sequence("sequenceDiagram\n  activate Alice\n  A->>B: hi")
    acts = [a for a in r.geometry.activations if a.participant_id == "Alice"]
    assert len(acts) == 1 and acts[0].was_implicitly_closed

def test_fragment_geometry_populated():
    r = compile_sequence("sequenceDiagram\n  loop retry\n    A->>B: x\n  end")
    assert len(r.geometry.fragments) == 1
    assert r.geometry.fragments[0].kind == "loop"

def test_note_geometry_populated():
    r = compile_sequence("sequenceDiagram\n  A->>B: x\n  Note over A: hello")
    assert len(r.geometry.notes) == 1
    assert r.geometry.notes[0].bounds.right > r.geometry.notes[0].bounds.left
```

**Approach:**
1. Update `SequenceGeometry` in `_geometry.py` to include typed tuple fields:
   `participants: tuple[ParticipantGeometry, ...] = ()`, `messages: tuple[MessageGeometry, ...] = ()`,
   `activations: tuple[ActivationGeometry, ...] = ()`, `notes: tuple[NoteGeometry, ...] = ()`,
   `fragments: tuple[FragmentGeometry, ...] = ()`, `branches: tuple[BranchGeometry, ...] = ()`.
   All default to `()` so tests can construct `SequenceGeometry(activations=(bad_act,))` without
   specifying every field. Keep old float-tuple fields as deprecated aliases.
2. In `_layout_lifeline`, populate each typed record at its emission site.
3. `SequenceCompileResult.scale` and `SequenceCompileResult.natural_bounds` own the
   transform metadata; `SequenceGeometry` remains coordinate-only.

---

### T2 — Uniform scaling via CSS transform viewport

**Implements:** AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-2.5
**Depends on:** T3b
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_strategies.py`

**Tests:**
```python
def test_width_hint_320_produces_transform_wrapper():
    r = compile_sequence("sequenceDiagram\n  participant Alice\n  participant Bob\n  Alice->>Bob: hi",
                         width_hint=320)
    assert "sequence-viewport" in r.html
    assert "sequence-natural-stage" in r.html
    assert "transform:scale(" in r.html

def test_inner_stage_coordinates_match_natural():
    """Inner stage coords at width_hint=320 == natural coords at width_hint=0."""
    src = "sequenceDiagram\n  participant Alice\n  participant Bob\n  Alice->>Bob: hi"
    natural = compile_sequence(src, width_hint=0)
    scaled = compile_sequence(src, width_hint=320)
    # Extract lifeline x from both; assert equal
    import re
    def _lifelines(html):
        return sorted(int(x) for x, *_ in re.findall(
            r'<line x1="(\d+)"[^>]*stroke-dasharray="5 4"', html))
    assert _lifelines(natural.html) == _lifelines(scaled.html)

def test_no_transform_when_wider_than_natural():
    r = compile_sequence("sequenceDiagram\n  A->>B: hi", width_hint=2000)
    assert r.scale == 1.0
    assert "transform:scale(" not in r.html

def test_participant_boxes_no_overlap_at_320():
    r = compile_sequence("sequenceDiagram\n  A->>B: hi\n  B->>C: hi", width_hint=320)
    assert r.scale < 1.0
    assert r.rendered_width == 320

def test_height_hint_uniform_scale():
    r = compile_sequence("sequenceDiagram\n  A->>B: hi", width_hint=400, height_hint=200)
    assert r.scale == min(1.0, 400/r.natural_width, 200/r.natural_height)

@pytest.mark.parametrize("with_element,without_element", [
    # note wider than label — note bounds expand canvas
    ("sequenceDiagram\n  A->>B: x\n  Note over A,B: " + "n" * 50,
     "sequenceDiagram\n  A->>B: x"),
    # fragment header wider than body — fragment bounds expand canvas
    ("sequenceDiagram\n  loop " + "f" * 60 + "\n    A->>B: x\n  end",
     "sequenceDiagram\n  A->>B: x"),
    # extra participant widens canvas
    ("sequenceDiagram\n  A->>B: x\n  B->>C: y",
     "sequenceDiagram\n  A->>B: x"),
])
def test_ac2_4_natural_width_includes_element_type(with_element, without_element):
    r_with = compile_sequence(with_element)
    r_without = compile_sequence(without_element)
    assert r_with.natural_width > r_without.natural_width

# Self-loop canvas expansion (AC-5.4) is tested in T5; not repeated here.
```

**Approach:**
1. In `_layout_lifeline`, remove the old `_wh_scale` column-position-only scaling
   (lines ~418-419 in `_strategies.py`). Always produce natural coordinates.
2. After building HTML string, compute `scale`:
   - `w_scale = width_hint / natural_width if width_hint else 1.0`
   - `h_scale = height_hint / natural_height if height_hint else 1.0`
   - `scale = min(1.0, w_scale, h_scale)`
3. If `scale < 1.0`, wrap the HTML in:
   ```html
   <div class="sequence-viewport" style="...width:{rendered_width}px;height:{rendered_height}px;overflow:hidden;">
     <div class="sequence-natural-stage" style="...width:{natural_width}px;height:{natural_height}px;transform:scale({scale});transform-origin:top left;">
       {inner_html}
     </div>
   </div>
   ```
4. Update `SequenceCompileResult.scale`, `.rendered_width`, `.rendered_height`.
5. **Pre-T2 grep**: verify all existing test renders use `width=800`; confirm no
   natural fixture exceeds 800px wide (if one does, T2 must keep backward compat
   for that test's expected positions).

---

### T4 — Structural and semantic geometry validation

**Implements:** AC-4.1, AC-4.2, AC-4.3
**Depends on:** T3b, T7
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `tests/test_sequence_geometry.py`

**Tests:**
```python
def test_structural_validation_valid_diagram():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: hi")
    svr = validate_sequence_geometry(r.geometry)
    assert svr.structural_geometry == "pass"

def test_structural_validation_detects_inverted_activation():
    # inject ActivationGeometry with end_y < start_y (start=100, end=50 → inverted)
    bad_act = ActivationGeometry(
        activation_id="a0", participant_id="Alice",
        start_y=100.0, end_y=50.0,
        depth=0, bounds=Bounds(95,50,105,100), was_implicitly_closed=False,
    )
    bad_geom = SequenceGeometry(activations=(bad_act,))
    svr = validate_sequence_geometry(bad_geom)
    assert svr.structural_geometry != "pass"

def test_semantic_activation_baseline_alignment():
    src = ("sequenceDiagram\n  Alice->>Bob: request\n  "
           "activate Bob\n  Bob-->>Alice: response\n  deactivate Bob")
    r = compile_sequence(src)
    svr = validate_sequence_geometry(r.geometry)
    assert svr.semantic_geometry == "pass"

def test_branch_semantic_validation_after_t7():
    src = "sequenceDiagram\n  alt A\n    A->>B: x\n  else B\n    A->>B: y\n  end"
    r = compile_sequence(src)
    svr = validate_sequence_geometry(r.geometry)
    assert svr.semantic_geometry == "pass"
```

**Approach:**
1. Write `validate_sequence_geometry(geom) -> SequenceValidationResult` in `_strategies.py`.
2. Structural checks use typed geometry records from T3b.
3. Semantic checks use `ActivationGeometry.start_y` vs `MessageGeometry.baseline_y`;
   `FragmentGeometry.participant_ids`; `BranchGeometry.parent_fragment_id`.
4. T4 runs after T7 so branch invariants and parent IDs are fully populated.

---

### T5 — Self-message geometry fixes

**Implements:** AC-5.1, AC-5.2, AC-5.3, AC-5.4, AC-5.5, AC-5.6
**Depends on:** T3b
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_strategies.py`

**Tests:**
```python
def test_active_self_message_anchors_at_activation_right():
    src = ("sequenceDiagram\n  activate Alice\n  Alice->>Alice: think\n  deactivate Alice")
    r = compile_sequence(src)
    act = r.geometry.activations[0]
    msg = r.geometry.messages[0]  # the self-message (skip first if needed)
    assert abs(msg.source_x - act.bounds.right) <= 2

def test_self_message_loop_width_from_label():
    long_src = "sequenceDiagram\n  Alice->>Alice: " + "x" * 60
    short_src = "sequenceDiagram\n  Alice->>Alice: x"
    r_long = compile_sequence(long_src)
    r_short = compile_sequence(short_src)
    long_msg = r_long.geometry.messages[0]
    short_msg = r_short.geometry.messages[0]
    long_w = long_msg.path_bounds.right - long_msg.path_bounds.left
    short_w = short_msg.path_bounds.right - short_msg.path_bounds.left
    assert long_w > short_w

def test_self_message_rightmost_within_canvas():
    src = "sequenceDiagram\n  A->>B: x\n  B->>B: self with a very long label"
    r = compile_sequence(src)
    msg = next(m for m in r.geometry.messages if m.is_self_message)
    assert msg.path_bounds.right <= r.natural_width + 2

def test_bidirectional_self_message_two_markers():
    src = "sequenceDiagram\n  Alice<<->>Alice: bidir"
    html = compile_sequence(src).html
    polys = re.findall(r'<polygon[^>]+fill="var\(--edge', html)
    assert len(polys) == 2
```

**Approach:**
1. Refactor the self-message branch in `_layout_lifeline`.
2. `source_x` = `activation_bounds_at(pid, y)[1]` when active, else `cx`.
3. Measure label: `loop_w = max(MIN_LOOP_W, label_width + 2*HPAD)`.
4. Row height: `max(ROW_H, label_height + loop_height + SELF_PAD)`.
5. Expand `canvas_w` if `source_x + loop_w + PAD_H > canvas_w`.
6. Populate `MessageGeometry(is_self_message=True, path_bounds=Bounds(...))`.

---

### T6 — Variable event heights for messages, fragments, branches

**Implements:** AC-6.1, AC-6.2, AC-6.3, AC-6.4, AC-6.5, AC-P2.2, AC-P2.3
**Depends on:** T3b
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `scripts/mermaid_render/layout/_geometry.py`

**Tests:**
```python
def test_multiline_message_expands_row():
    src_multi = "sequenceDiagram\n  A->>B: line1\nline2\nline3"
    src_short = "sequenceDiagram\n  A->>B: x"
    assert _canvas_height(_dispatch(src_multi, None, 800)) > _canvas_height(_dispatch(src_short, None, 800))

def test_long_fragment_header_expands_row():
    src_long = "sequenceDiagram\n  loop " + "x" * 80 + "\n    A->>B: hi\n  end"
    src_short = "sequenceDiagram\n  loop x\n    A->>B: hi\n  end"
    assert _canvas_height(_dispatch(src_long, None, 800)) > _canvas_height(_dispatch(src_short, None, 800))

def test_no_overflow_hidden_in_sequence_labels():
    html = _dispatch("sequenceDiagram\n  Alice->>Bob: hi", None, 0)
    # participant label spans must not have overflow:hidden
    label_styles = re.findall(r'class="node-label"[^>]+style="([^"]+)"', html)
    for style in label_styles:
        assert "overflow:hidden" not in style

def test_p2_2_no_double_alpha_on_rgba_rect():
    """A rect with rgba() fill must not also carry opacity= (double-alpha bug)."""
    r = compile_sequence("sequenceDiagram\n  loop retry\n    A->>B: x\n  end")
    import re
    rects = re.findall(r'<rect[^>]+>', r.html)
    for rect in rects:
        if "rgba(" in rect:
            assert "opacity=" not in rect, f"double-alpha on rect: {rect}"

def test_p2_3_message_label_centered_over_activation_adjusted_segment():
    """Label x must be midpoint between source_x and dest_x, not bare lifeline centers."""
    src = ("sequenceDiagram\n  activate Alice\n  Alice->>Bob: request\n  deactivate Alice")
    r = compile_sequence(src)
    msg = r.geometry.messages[0]
    expected_mid = (msg.source_x + msg.destination_x) / 2
    # label_x must equal (source_x + destination_x) / 2 within 2px
    assert abs(msg.label_x - expected_mid) <= 2
```

**Approach:**
1. Add `_calculate_event_height(item, metrics, measurer)` returning height per event type.
2. Call it for all item types, not just notes, when building `_row_h_list`.
3. Remove `overflow:hidden` and `text-overflow:ellipsis` from participant-label and
   message-label span CSS in `_layout_lifeline`.
4. (AC-P2.2) When emitting fragment/note rects with rgba fill, omit the `opacity=`
   attribute — opacity is already encoded in the alpha channel.
5. (AC-P2.3) Compute `label_x = (source_x + destination_x) / 2` at emission, where
   `source_x` and `destination_x` are the activation-adjusted endpoints (not bare
   `_cx[src_pid]`). Populate `MessageGeometry.label_x`.

---

### T7 — Branch parent association fix

**Implements:** AC-7.1, AC-7.2, AC-7.3, AC-7.4
**Depends on:** T3b
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_strategies.py`

**Tests:**
```python
def test_branch_parent_fragment_id_populated():
    src = "sequenceDiagram\n  alt A\n    A->>B: x\n  else B\n    A->>B: y\n  end"
    r = compile_sequence(src)
    frag_ids = {f.fragment_id for f in r.geometry.fragments}
    for branch in r.geometry.branches:
        assert branch.parent_fragment_id != ""
        assert branch.parent_fragment_id in frag_ids

def test_branch_bounds_match_parent_bounds():
    src = "sequenceDiagram\n  alt A\n    A->>B: x\n  else B\n    A->>B: y\n  end"
    r = compile_sequence(src)
    for branch in r.geometry.branches:
        frag = next(f for f in r.geometry.fragments if f.fragment_id == branch.parent_fragment_id)
        assert abs(branch.bounds.left - frag.bounds.left) <= 2
        assert abs(branch.bounds.right - frag.bounds.right) <= 2

def test_nested_fragment_branch_correct_parent():
    src = ("sequenceDiagram\n"
           "  loop outer\n"
           "    alt inner\n"
           "      A->>B: x\n"
           "    else other\n"
           "      A->>B: y\n"
           "    end\n"
           "  end\n")
    r = compile_sequence(src)
    branches = r.geometry.branches
    inner_frag = next(f for f in r.geometry.fragments if f.kind == "alt")
    for b in branches:
        assert b.parent_fragment_id == inner_frag.fragment_id
```

**Approach:**
1. During the block prepass (`_bstack` loop), add:
   ```python
   _branch_parent_id: dict[int, str] = {}
   ```
   When encountering `else/and/option` at `_bi` with `_bstack` non-empty:
   `_branch_parent_id[_bi] = _frag_id[_bstack[-1]]`
2. During emission (Pass B), use `_branch_parent_id.get(_bi, "")` for branch parent.
3. Remove reliance on `_bstk_else` for parent lookup.
4. Populate `BranchGeometry(branch_id, parent_fragment_id, ...)` at emission.

---

### T8 — MarkerKind + ArrowSpec + complete arrow grammar

**Implements:** AC-8.1, AC-8.2, AC-8.3, AC-8.4
**Depends on:** T1
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_geometry.py`, `scripts/mermaid_render/layout/_strategies.py`

**Tests:**
```python
@pytest.mark.parametrize("token,dashed,start_m,end_m", [
    ("->",    False, None,        None),
    ("-->",   True,  None,        None),
    ("->>",   False, None,        "triangle"),
    ("-->>",  True,  None,        "triangle"),
    ("-x",    False, None,        "cross"),
    ("--x",   True,  None,        "cross"),
    ("-)  ",  False, None,        "filled_head"),
    ("--)  ", True,  None,        "filled_head"),
    ("<<->>", False, "triangle",  "triangle"),
    ("<<-->>",True,  "triangle",  "triangle"),
])
def test_arrow_spec_table(token, dashed, start_m, end_m):
    from mermaid_render.layout._geometry import MarkerKind, ARROW_SPECS
    spec = ARROW_SPECS[token.strip()]
    assert spec.dashed == dashed
    assert spec.start_marker == (MarkerKind(start_m) if start_m else None)
    assert spec.end_marker == (MarkerKind(end_m) if end_m else None)

def test_unsupported_arrow_produces_diagnostic():
    """Feed a token through the arrow-spec lookup with a fabricated token not in ARROW_SPECS."""
    from mermaid_render.layout._geometry import ARROW_SPECS, ArrowSpec, MarkerKind
    from mermaid_render.layout._strategies import _emit_arrow_or_diagnostic

    diagnostics: list = []
    # "--->" is syntactically plausible but not in ARROW_SPECS
    result = _emit_arrow_or_diagnostic("--->", diagnostics)
    assert any(d.code == "unsupported_arrow" for d in diagnostics)
    # fallback must be a solid no-marker spec, not None
    assert result is not None
    assert result.dashed is False
    assert result.start_marker is None and result.end_marker is None
```

**Approach:**
1. Add `MarkerKind(enum.Enum)` and `ArrowSpec` frozen dataclass to `_geometry.py`.
2. Move `_ARROW_SPECS` from `_strategies.py` to a module-level `ARROW_SPECS` dict using
   `ArrowSpec` instances.
3. Export `ARROW_SPECS`, `MarkerKind`, `ArrowSpec` from `_geometry.py`.
4. Extract arrow lookup into `_emit_arrow_or_diagnostic(token: str, diagnostics: list) -> ArrowSpec`:
   if token not in `ARROW_SPECS`, appends `SequenceDiagnostic(code="unsupported_arrow", ...)`
   and returns the solid no-marker fallback `ArrowSpec(dashed=False, start_marker=None, end_marker=None)`.
   Call this helper from `_layout_lifeline` so it is independently testable.

---

### T9 — SequenceDiagnostic integration + no silent discards

**Implements:** AC-9.2, AC-9.3, AC-9.4, AC-9.5, AC-4.4, AC-4.5, AC-P2.1
*(AC-4.5 = diagnostic at skip-guards; AC-9.3 = defensive hardening on helpers)*
**Depends on:** T1
**Mode:** TDD
**Touches:** `scripts/mermaid_render/layout/_strategies.py`, `scripts/mermaid_render/__init__.py`

**Tests:**
```python
def test_autonumber_diagnostic_has_severity():
    r = compile_sequence("sequenceDiagram\n  autonumber\n  A->>B: hi")
    d = r.diagnostics[0]
    assert d.severity in ("info","warning","error")
    assert d.code == "autonumber"
    assert d.line_number == 1

def test_unknown_participant_helper_emits_diagnostic_not_index_zero():
    """Call _cx_or_diagnostic directly — exercises the defensive invariant on the helper.
    All parsing paths auto-register pids, so this tests the helper in isolation."""
    from mermaid_render.layout._strategies import _cx_or_diagnostic
    col_centers = [100.0, 300.0]  # Alice=0, Bob=1
    p_index = {"Alice": 0, "Bob": 1}
    diags: list = []
    fallback = _cx_or_diagnostic("Ghost", p_index, col_centers=col_centers, diags=diags)
    assert any(d.code == "unknown_participant" and d.severity == "error" for d in diags)
    # fallback must not be index-0's coordinate (100.0)
    assert fallback != col_centers[0]

def test_skip_guard_emits_diagnostic():
    """Call _emit_message_or_skip directly with unregistered sender pid — exercises
    the skip-guard diagnostic site. Separate from the coord-helper site."""
    from mermaid_render.layout._strategies import _emit_message_or_skip
    diags: list = []
    p_index = {"Alice": 0, "Bob": 1}
    skipped = _emit_message_or_skip(
        src_pid="Ghost", dst_pid="Alice",
        p_index=p_index, col_centers=[100.0, 300.0],
        diags=diags, row_tops=[0.0, 50.0], event_idx=0,
    )
    assert skipped is True
    assert any(d.code == "unknown_participant" for d in diags)

def test_p2_1_stale_phase4_comment_removed():
    """The stale '# Phase 4 will wire per-type validation' comment at __init__.py:146 is gone."""
    import pathlib, mermaid_render
    init_src = pathlib.Path(mermaid_render.__file__).read_text()
    assert "Phase 4 will wire per-type validation" not in init_src

def test_unmatched_deactivate_produces_diagnostic():
    r = compile_sequence("sequenceDiagram\n  A->>B: hi\n  deactivate B")
    assert any(
        d.code == "unmatched_deactivate" and d.severity == "warning"
        for d in r.diagnostics
    )
```

**Approach:**
1. Replace bare `Diagnostic` with `SequenceDiagnostic` throughout `_layout_lifeline`.
2. Add `severity`, `code`, `message` fields to each diagnostic emission.
3. **Skip-guard hardening** (AC-4.5): grep for `"row += 1; continue"` near the message-sender
   lookup in `_layout_lifeline`. Extract each into `_emit_message_or_skip(src_pid, dst_pid, ...)`
   that emits `SequenceDiagnostic(code="unknown_participant", severity="error")` before skipping.
   This is defensive: all pids are auto-registered through parsing, so no user input reaches it.
   Verified by `test_skip_guard_emits_diagnostic` calling the helper directly.
4. **Coord helper hardening** (AC-9.3): replace both `.get(pid, 0)` sites
   (grep: `"\.get(pid, 0)"` in `_strategies.py`) with:
   - `_box_hw_or_diagnostic(pid, p_index, diags) -> float`: if `pid` absent, emit diagnostic,
     return `BOX_MIN_W / 2.0`.
   - `_cx_or_diagnostic(pid, p_index, col_centers, diags) -> float`: if `pid` absent, emit
     diagnostic, return `float(PAD_H)`.
   Also defensive / unreachable through parsing.
5. Remove and replace the inline `# Phase 4 will wire per-type validation` comment at
   `__init__.py:146` with a description of the actual behavior (geometry is now validated
   per-type via `compile_sequence()`).

---

### T10 — Gallery provenance + status lanes + atomic replacement

**Implements:** AC-10.1, AC-10.2, AC-10.3, AC-10.4, AC-10.5
**Depends on:** T1, T4
**Mode:** goal-based check
**Touches:** `tools/compare_gallery.py`

**Done when:**
```bash
# --strict flag exists
python3 tools/compare_gallery.py --help | grep -q "\-\-strict"
# provenance check exits non-zero when a foreign module SHA256 is injected
python3 -c "
import subprocess, sys, json, pathlib, hashlib
meta = pathlib.Path('gallery/metadata.json')
orig = json.loads(meta.read_text())
orig['modules']['_geometry.py']['sha256'] = 'deadbeef'
meta.write_text(json.dumps(orig))
rc = subprocess.run(['python3', 'tools/compare_gallery.py', '--metadata-only'], capture_output=True).returncode
meta.write_text(json.dumps(json.loads(pathlib.Path('gallery/metadata.json.bak').read_text())))
sys.exit(0 if rc != 0 else 1)
"
# 5 lane labels in index.html
grep -qE 'render.*syntax.*structural_geometry.*semantic_geometry.*mmdc_oracle' gallery/index.html
# AC-10.5: atomic replace — simulate failure mid-write and verify old output unchanged
python3 -c "
import tools.compare_gallery as cg, tempfile, os, shutil, pathlib
out = pathlib.Path('gallery')
bak = shutil.copytree(out, out.parent / '_bak_test')
try:
    # patch write to raise mid-way; out must be unchanged
    orig = out / 'test_artifact.html'
    orig.write_text('<old/>')
    try:
        cg._atomic_write_gallery(out, raise_mid_write=True)
    except Exception:
        pass
    assert orig.read_text() == '<old/>', 'atomic replace violated: old output overwritten'
finally:
    shutil.rmtree(out)
    shutil.copytree(bak, out)
    shutil.rmtree(bak)
"
```

**Approach:**
1. `_assert_module_provenance` already present — verify it covers `_geometry.py` and
   `_text.py` SHA256 in metadata.
2. Add 5-lane status rendering to `index.html` template: `render`, `syntax`,
   `structural_geometry`, `semantic_geometry`, `mmdc_oracle`.
3. Add `--strict` flag: iterate metadata.json, fail on any fixture where render≠pass
   or structural_geometry≠pass or any error-severity diagnostic.
4. Atomic replacement: write to `tempfile.mkdtemp(dir=OUT_DIR.parent)`, then
   `shutil.rmtree(OUT_DIR)` + `os.rename(tmp, OUT_DIR)` once all artifacts are written.
   Wrap in `try/finally` to clean up tmp on failure. Expose `_atomic_write_gallery(out_dir, *, raise_mid_write=False)`
   as a testable helper (the `raise_mid_write` flag is test-only; defaults to False in production).

---

### T11 — mmdc semantic comparison (basic)

**Implements:** AC-11.1, AC-11.2, AC-11.3
**Depends on:** T10
**Mode:** goal-based check
**Touches:** `tools/compare_gallery.py`

**Done when:** gallery renders with `mmdc_oracle` showing "pass", "warning", or "unvalidated"
for all fixtures without crashing.

**Approach:**
1. Parse mmdc SVG for: `<g data-et="participant">` count, `<g data-et="message">` count,
   presence of `<rect data-et="activation">`, `<polygon data-et="note">`.
2. Compare counts against `SequenceGeometry.participants` and `.messages` lengths.
3. Report per-category mismatches.

---

### T12 — New regression fixtures + tests

**Implements:** AC-R.1, AC-R.2, AC-R.3
**Depends on:** T1, T2, T3b, T4, T5, T6, T7, T8, T9
**Mode:** TDD
**Touches:** `tests/fixtures/`, `tests/test_fix_sequence.py`, `tests/test_sequence_geometry.py`

**Approach:**
1. Create each fixture .mmd file per AC-R.2.
2. Add parametrised test asserting both `structural_geometry` **and** `syntax_coverage` for
   each fixture match the expected-status table in spec AC-R.2 (`render`, `syntax`,
   `structural_geometry` columns).
3. Verify full test suite passes.

---

## Deferred to docs/backlog.md

Items anchored in `docs/backlog.md ## sequence-renderer-correctness-pass`:

- `sequence-box-unsupported.mmd` → [seq-corr-box-unsupported-fixture]
- `sequence-create-destroy.mmd` → [seq-corr-create-destroy-fixture]
- `sequence-single-participant-fragment-long-header.mmd` → [seq-corr-single-participant-fragment-long-header]
- `sequence-note-only-implicit-participant.mmd` → [seq-corr-note-only-implicit-participant-fixture]
- height_hint in gallery per-fixture metadata → [seq-corr-height-hint-gallery-metadata]
- mmdc `data-et` attribute selectors → [seq-corr-mmdc-data-et-selectors]

## Risks

- **T2 scale wrapper and existing coordinate-parsing tests**: Existing tests parse
  absolute pixel positions from rendered HTML. At `width=800` (all existing tests),
  natural widths of current fixtures are under 800px → no compression today → T2
  produces `scale=1.0` for those cases → no wrapper div, no coordinate shift.
  New T2 tests that exercise width_hint=320/480 will parse inner-stage coordinates,
  not outer wrapper dimensions.

- **T3b SequenceGeometry field migration**: 82+ accesses in `test_fix_sequence.py`
  read geometry via old tuple fields. Keeping deprecated aliases in T3b means those
  tests stay green. Aliases are removed in a follow-up PR once new tests cover same ground.

- **T4/T7 ordering**: Branch semantic validation in T4 depends on T7's parent-ID fix.
  T4 is split: structural-only tests written first, branch-semantic assertion written
  after T7 lands.

## Changelog

- 2026-07-22 (pass 1): Split T3 → T3a/T3b. Changed T2 `Depends on: T3b`. Added T7 dep for T4. Named both `.get(pid,0)` sites in T9. AC-1.4 spy approach. height_hint AC-2.5. Scale on SequenceCompileResult. Backlog anchors. Deferred fixtures.
- 2026-07-22 (pass 2): AC-P2.2/AC-P2.3 added to T6. AC-4.4/4.5 sole-owned by T9. T10 Done-when has provenance + lane + AC-10.5 atomic assertions. AC-P2.1 repointed to __init__.py:146 comment. T8 arrow test calls helper directly. T4 inverted-activation test fixed. Approach ordering corrected. AC-2.4 test discriminating.
- 2026-07-22 (pass 3): AC-4.4 test added to T9. label_x added to AC-3.4 / T6 Touches. AC-2.4 self-loop case moved to T5. T9 step 4 points at comment. T3b step 1 documents () defaults.
- 2026-07-22 (pass 4): AC-4.5 reworded to "fallback render, not skip". Unknown-participant test now calls `_cx_or_diagnostic` helper directly. AC-2.4 self-loop case replaced with extra-participant case. AC-9.3 cross-references AC-4.5. Discovery field set to none. Absolute line-number anchors replaced with grep instructions.
