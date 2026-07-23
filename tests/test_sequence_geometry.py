"""Construction tests for the sequence renderer correctness pass.

Each test group is labelled with the task it verifies (T1, T3a, T3b, T2, ...).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import (
    _layout_lifeline,
    compile_sequence,
    _dispatch_validate,
    validate_sequence_geometry,
    _cx_or_diagnostic,
    _emit_message_or_skip,
)
from mermaid_render.layout._geometry import (
    Bounds,
    ParticipantGeometry,
    MessageGeometry,
    ActivationGeometry,
    NoteGeometry,
    FragmentGeometry,
    BranchGeometry,
    SequenceCompileResult,
    SequenceDiagnostic,
    SequenceGeometry,
    SequenceValidationResult,
    SequenceMarkerKind,
    ArrowSpec,
    ARROW_SPECS,
)

MarkerKind = SequenceMarkerKind  # local alias: the sequence-diagram marker kind


# ── T1: SequenceCompileResult + SequenceDiagnostic + compile_sequence() ───────

def test_compile_sequence_returns_compile_result():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: hi")
    assert isinstance(r, SequenceCompileResult)
    assert r.html and r.geometry
    assert r.natural_width > 0 and r.natural_height > 0


def test_compile_sequence_html_nonempty():
    r = compile_sequence("sequenceDiagram\n  A->>B: hello")
    assert "<svg" in r.html or "<div" in r.html


def test_layout_lifeline_called_exactly_once_per_compile():
    import mermaid_render.layout._strategies as strats
    with patch.object(strats, "_layout_lifeline", wraps=strats._layout_lifeline) as spy:
        compile_sequence("sequenceDiagram\n  A->>B: hi", width_hint=480)
        assert spy.call_count == 1


def test_compile_sequence_natural_width_populated():
    r = compile_sequence("sequenceDiagram\n  A->>B: hi", width_hint=0)
    assert r.natural_width > 0
    assert r.rendered_width == r.natural_width


def test_dispatch_validate_calls_layout_lifeline_exactly_once():
    import mermaid_render.layout._strategies as strats
    with patch.object(strats, "_layout_lifeline", wraps=strats._layout_lifeline) as spy:
        _dispatch_validate("sequenceDiagram\n  A->>B: hi")
        assert spy.call_count == 1


def test_sequence_diagnostic_has_required_fields():
    d = SequenceDiagnostic(severity="warning", code="test_code", message="test msg")
    assert d.severity == "warning"
    assert d.code == "test_code"
    assert d.message == "test msg"
    assert d.feature is None
    assert d.line_number is None
    assert d.source_text is None


def test_sequence_diagnostic_severity_values():
    for sev in ("info", "warning", "error"):
        d = SequenceDiagnostic(severity=sev, code="x", message="y")
        assert d.severity == sev


def test_compile_sequence_diagnostics_are_sequence_diagnostics():
    # autonumber is an unsupported construct → produces a legacy Diagnostic
    # compile_sequence lifts it to SequenceDiagnostic
    r = compile_sequence("sequenceDiagram\n  autonumber\n  A->>B: hi")
    for d in r.diagnostics:
        assert isinstance(d, SequenceDiagnostic)
        assert d.severity in ("info", "warning", "error")
        assert d.code


# ── T3a: New typed geometry dataclasses (additive) ────────────────────────────

def test_bounds_dataclass_exists():
    b = Bounds(left=0, top=0, right=100, bottom=50)
    assert b.right - b.left == 100
    assert b.width == 100
    assert b.height == 50
    assert b.cx == 50
    assert b.cy == 25


def test_participant_geometry_fields():
    pg = ParticipantGeometry(
        participant_id="Alice", label="Alice", center_x=100.0,
        top_box=Bounds(50, 20, 150, 60), bottom_box=Bounds(50, 400, 150, 440),
        lifeline_top=60.0, lifeline_bottom=400.0,
    )
    assert pg.participant_id == "Alice"
    assert pg.center_x == 100.0
    assert pg.top_box.width == 100


def test_message_geometry_fields():
    mg = MessageGeometry(
        event_id="msg0", source_id="Alice", destination_id="Bob",
        baseline_y=100.0, source_x=100.0, destination_x=300.0,
        label_x=200.0, arrow_token="->>",
    )
    assert mg.is_self_message is False
    assert mg.label_x == 200.0


def test_activation_geometry_fields():
    ag = ActivationGeometry(
        activation_id="act0", participant_id="Alice",
        start_y=100.0, end_y=200.0, depth=0,
        bounds=Bounds(95, 100, 105, 200), was_implicitly_closed=False,
    )
    assert ag.start_y < ag.end_y


def test_note_geometry_fields():
    ng = NoteGeometry(
        note_id="note0", participant_ids=("Alice",),
        placement="over", bounds=Bounds(50, 100, 200, 130),
    )
    assert ng.bounds.width == 150


def test_fragment_geometry_fields():
    fg = FragmentGeometry(
        fragment_id="frag0", kind="loop",
        participant_ids=("Alice", "Bob"),
        bounds=Bounds(10, 80, 400, 300), header_text="retry",
    )
    assert fg.kind == "loop"
    assert "Alice" in fg.participant_ids


def test_branch_geometry_fields():
    bg = BranchGeometry(
        branch_id="branch0", parent_fragment_id="frag0",
        label="else", bounds=Bounds(10, 150, 400, 155),
    )
    assert bg.parent_fragment_id == "frag0"


def test_sequence_geometry_typed_fields_default_empty():
    geom = SequenceGeometry()
    assert geom.participants == ()
    assert geom.messages == ()
    assert geom.activations == ()
    assert geom.notes == ()
    assert geom.fragments == ()
    assert geom.branches == ()


def test_sequence_geometry_partial_construction():
    bad_act = ActivationGeometry(
        activation_id="a0", participant_id="Alice",
        start_y=100.0, end_y=50.0,  # inverted — end_y < start_y
        depth=0, bounds=Bounds(95, 50, 105, 100), was_implicitly_closed=False,
    )
    geom = SequenceGeometry(activations=(bad_act,))
    assert len(geom.activations) == 1
    assert geom.activations[0].end_y < geom.activations[0].start_y


# ── T3b: Typed geometry populated in _layout_lifeline ────────────────────────

def test_typed_participants_count_matches_diagram():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: hi\n  Carol->>Alice: ok")
    assert len(r.geometry.participants) == 3


def test_typed_participant_fields_populated():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: hi")
    pids = {p.participant_id for p in r.geometry.participants}
    assert "Alice" in pids and "Bob" in pids
    alice = next(p for p in r.geometry.participants if p.participant_id == "Alice")
    assert alice.label == "Alice"
    assert alice.center_x > 0
    assert isinstance(alice.top_box, Bounds)
    assert alice.top_box.width > 0
    assert alice.top_box.height > 0
    assert isinstance(alice.bottom_box, Bounds)
    assert alice.lifeline_top < alice.lifeline_bottom


def test_typed_messages_count_matches_diagram():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: one\n  Bob-->>Alice: two")
    assert len(r.geometry.messages) == 2


def test_typed_message_fields_populated():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: hello")
    assert len(r.geometry.messages) == 1
    m = r.geometry.messages[0]
    assert m.source_id == "Alice"
    assert m.destination_id == "Bob"
    assert m.arrow_token == "->>"
    assert m.is_self_message is False
    assert m.baseline_y > 0
    # label_x should lie between the two endpoints
    lo, hi = min(m.source_x, m.destination_x), max(m.source_x, m.destination_x)
    assert lo <= m.label_x <= hi


def test_typed_self_message_flag():
    r = compile_sequence("sequenceDiagram\n  Alice->>Alice: think")
    msgs = r.geometry.messages
    assert len(msgs) == 1
    assert msgs[0].is_self_message is True
    assert msgs[0].source_id == "Alice"
    assert msgs[0].destination_id == "Alice"
    assert msgs[0].path_bounds is not None


def test_typed_activations_populated():
    src = "sequenceDiagram\n  Alice->>Bob: req\n  activate Bob\n  Bob-->>Alice: resp\n  deactivate Bob"
    r = compile_sequence(src)
    bob_acts = [a for a in r.geometry.activations if a.participant_id == "Bob"]
    assert len(bob_acts) >= 1
    act = bob_acts[0]
    assert act.start_y < act.end_y
    assert isinstance(act.bounds, Bounds)
    assert act.was_implicitly_closed is False


def test_typed_activation_implicitly_closed():
    # No deactivate → flushed to lifeline bottom → was_implicitly_closed=True
    src = "sequenceDiagram\n  Alice->>Bob: req\n  activate Bob\n  Bob-->>Alice: resp"
    r = compile_sequence(src)
    bob_acts = [a for a in r.geometry.activations if a.participant_id == "Bob"]
    assert len(bob_acts) >= 1
    assert any(a.was_implicitly_closed for a in bob_acts)


def test_typed_notes_populated():
    src = "sequenceDiagram\n  Alice->>Bob: hi\n  Note over Alice: thinking"
    r = compile_sequence(src)
    assert len(r.geometry.notes) >= 1
    note = r.geometry.notes[0]
    assert isinstance(note.bounds, Bounds)
    assert note.bounds.width > 0 and note.bounds.height > 0
    assert "Alice" in note.participant_ids


def test_typed_fragments_populated():
    src = "sequenceDiagram\n  loop retry\n    Alice->>Bob: ping\n  end"
    r = compile_sequence(src)
    frags = [f for f in r.geometry.fragments if f.kind == "loop"]
    assert len(frags) >= 1
    frag = frags[0]
    assert isinstance(frag.bounds, Bounds)
    assert "retry" in frag.header_text


def test_typed_branches_populated():
    src = (
        "sequenceDiagram\n"
        "  alt success\n"
        "    Alice->>Bob: ok\n"
        "  else failure\n"
        "    Alice->>Bob: err\n"
        "  end"
    )
    r = compile_sequence(src)
    assert len(r.geometry.branches) >= 1
    branch = r.geometry.branches[0]
    assert isinstance(branch.bounds, Bounds)
    assert branch.label == "failure"


# ── T2: Uniform CSS-transform scaling viewport ────────────────────────────────

_WIDE_SRC = "sequenceDiagram\n  A->>B: hi\n  B->>C: hi"  # natural ~368px


def test_width_hint_320_produces_transform_wrapper():
    # _WIDE_SRC natural width ~368 > 320 → scale < 1.0 → wrapper emitted
    r = compile_sequence(_WIDE_SRC, width_hint=320)
    assert "sequence-viewport" in r.html
    assert "sequence-natural-stage" in r.html
    assert "transform:scale(" in r.html


def test_inner_stage_coordinates_match_natural():
    # Lifeline x coords inside the scaled stage must equal the natural coords
    natural = compile_sequence(_WIDE_SRC, width_hint=0)
    scaled = compile_sequence(_WIDE_SRC, width_hint=320)

    def _lifelines(html):
        return sorted(int(x) for x, *_ in re.findall(
            r'<line x1="(\d+)"[^>]*stroke-dasharray="5 4"', html))

    assert _lifelines(natural.html) == _lifelines(scaled.html)


def test_no_transform_when_wider_than_natural():
    r = compile_sequence("sequenceDiagram\n  A->>B: hi", width_hint=2000)
    assert r.scale == 1.0
    assert "transform:scale(" not in r.html


def test_participant_boxes_no_overlap_at_320():
    # _WIDE_SRC natural width ~368 > 320 → scale < 1.0, rendered_width = 320
    r = compile_sequence(_WIDE_SRC, width_hint=320)
    assert r.scale < 1.0
    assert r.rendered_width == 320


def test_height_hint_uniform_scale():
    r = compile_sequence("sequenceDiagram\n  A->>B: hi", width_hint=400, height_hint=200)
    assert r.scale == min(1.0, 400 / r.natural_width, 200 / r.natural_height)


@pytest.mark.parametrize("with_element,without_element", [
    (
        "sequenceDiagram\n  A->>B: x\n  Note over A,B: " + "n" * 50,
        "sequenceDiagram\n  A->>B: x",
    ),
    (
        "sequenceDiagram\n  loop " + "f" * 60 + "\n    A->>B: x\n  end",
        "sequenceDiagram\n  A->>B: x",
    ),
    (
        "sequenceDiagram\n  A->>B: x\n  B->>C: y",
        "sequenceDiagram\n  A->>B: x",
    ),
])
def test_ac2_4_natural_width_includes_element_type(with_element, without_element):
    r_with = compile_sequence(with_element)
    r_without = compile_sequence(without_element)
    assert r_with.natural_width > r_without.natural_width


# ── T5: Self-message geometry fixes ──────────────────────────────────────────

def test_active_self_message_anchors_at_activation_right():
    src = "sequenceDiagram\n  activate Alice\n  Alice->>Alice: think\n  deactivate Alice"
    r = compile_sequence(src)
    act = r.geometry.activations[0]
    msg = r.geometry.messages[0]
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


# ── T6: Variable event heights ────────────────────────────────────────────────

def _canvas_height(html: str) -> int:
    m = re.search(r"height:(\d+)px", html)
    return int(m.group(1)) if m else 0


def test_multiline_message_expands_row():
    # <br> forces 3 lines in the label → row height > ROW_H
    src_multi = "sequenceDiagram\n  A->>B: line1<br>line2<br>line3"
    src_short = "sequenceDiagram\n  A->>B: x"
    from mermaid_render.layout._strategies import _dispatch
    assert _canvas_height(_dispatch(src_multi, None, 800)) > _canvas_height(_dispatch(src_short, None, 800))


def test_long_fragment_header_expands_row():
    # <br> forces 3 lines in the fragment header → block row height > ROW_H
    src_long = "sequenceDiagram\n  loop x<br>y<br>z\n    A->>B: hi\n  end"
    src_short = "sequenceDiagram\n  loop x\n    A->>B: hi\n  end"
    from mermaid_render.layout._strategies import _dispatch
    assert _canvas_height(_dispatch(src_long, None, 800)) > _canvas_height(_dispatch(src_short, None, 800))


def test_no_overflow_hidden_in_sequence_labels():
    from mermaid_render.layout._strategies import _dispatch
    html = _dispatch("sequenceDiagram\n  Alice->>Bob: hi", None, 0)
    label_styles = re.findall(r'class="node-label"[^>]+style="([^"]+)"', html)
    for style in label_styles:
        assert "overflow:hidden" not in style


def test_p2_2_no_double_alpha_on_rgba_rect():
    r = compile_sequence("sequenceDiagram\n  loop retry\n    A->>B: x\n  end")
    rects = re.findall(r'<rect[^>]+>', r.html)
    for rect in rects:
        fill_m = re.search(r'\bfill="([^"]+)"', rect)
        fill_val = fill_m.group(1) if fill_m else ""
        if "rgba(" in fill_val:
            assert "opacity=" not in rect, f"double-alpha on rect: {rect}"


def test_p2_3_message_label_centered_over_activation_adjusted_segment():
    src = "sequenceDiagram\n  activate Alice\n  Alice->>Bob: request\n  deactivate Alice"
    r = compile_sequence(src)
    msg = r.geometry.messages[0]
    expected_mid = (msg.source_x + msg.destination_x) / 2
    assert abs(msg.label_x - expected_mid) <= 2


# ── T7: Branch parent association fix ────────────────────────────────────────

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
    src = (
        "sequenceDiagram\n"
        "  loop outer\n"
        "    alt inner\n"
        "      A->>B: x\n"
        "    else other\n"
        "      A->>B: y\n"
        "    end\n"
        "  end\n"
    )
    r = compile_sequence(src)
    branches = r.geometry.branches
    inner_frag = next(f for f in r.geometry.fragments if f.kind == "alt")
    for b in branches:
        assert b.parent_fragment_id == inner_frag.fragment_id


# ── T4: Structural and semantic geometry validation ───────────────────────────

def test_structural_validation_valid_diagram():
    r = compile_sequence("sequenceDiagram\n  Alice->>Bob: hi")
    svr = validate_sequence_geometry(r.geometry)
    assert isinstance(svr, SequenceValidationResult)
    assert svr.structural_geometry == "pass"


def test_structural_validation_detects_inverted_activation():
    bad_act = ActivationGeometry(
        activation_id="a0", participant_id="Alice",
        start_y=100.0, end_y=50.0,
        depth=0, bounds=Bounds(95, 50, 105, 100), was_implicitly_closed=False,
    )
    bad_geom = SequenceGeometry(activations=(bad_act,))
    svr = validate_sequence_geometry(bad_geom)
    assert svr.structural_geometry != "pass"


def test_semantic_activation_baseline_alignment():
    src = (
        "sequenceDiagram\n  Alice->>Bob: request\n  "
        "activate Bob\n  Bob-->>Alice: response\n  deactivate Bob"
    )
    r = compile_sequence(src)
    svr = validate_sequence_geometry(r.geometry)
    assert svr.semantic_geometry == "pass"


def test_branch_semantic_validation_after_t7():
    src = "sequenceDiagram\n  alt A\n    A->>B: x\n  else B\n    A->>B: y\n  end"
    r = compile_sequence(src)
    svr = validate_sequence_geometry(r.geometry)
    assert svr.semantic_geometry == "pass"


# ── T8: MarkerKind + ArrowSpec + complete arrow grammar ───────────────────────

@pytest.mark.parametrize("token,dashed,start_m,end_m", [
    ("->",     False, None,        None),
    ("-->",    True,  None,        None),
    ("->>",    False, None,        "triangle"),
    ("-->>",   True,  None,        "triangle"),
    ("-x",     False, None,        "cross"),
    ("--x",    True,  None,        "cross"),
    ("-)",     False, None,        "filled_head"),
    ("--)",    True,  None,        "filled_head"),
    ("<<->>",  False, "triangle",  "triangle"),
    ("<<-->>", True,  "triangle",  "triangle"),
])
def test_arrow_spec_table(token, dashed, start_m, end_m):
    spec = ARROW_SPECS[token.strip()]
    assert spec.dashed == dashed
    assert spec.start_marker == (MarkerKind(start_m) if start_m else None)
    assert spec.end_marker == (MarkerKind(end_m) if end_m else None)


def test_unsupported_arrow_produces_diagnostic():
    from mermaid_render.layout._strategies import _emit_arrow_or_diagnostic
    diagnostics: list = []
    result = _emit_arrow_or_diagnostic("--->", diagnostics)
    assert any(d.code == "unsupported_arrow" for d in diagnostics)
    assert result is not None
    assert result.dashed is False
    assert result.start_marker is None and result.end_marker is None


# ── T9: SequenceDiagnostic integration ───────────────────────────────────────

def test_autonumber_diagnostic_has_severity():
    r = compile_sequence("sequenceDiagram\n  autonumber\n  A->>B: hi")
    d = r.diagnostics[0]
    assert d.severity in ("info", "warning", "error")
    assert d.code == "autonumber"
    assert d.line_number == 1


def test_unknown_participant_helper_emits_diagnostic_not_index_zero():
    col_centers = [100.0, 300.0]
    p_index = {"Alice": 0, "Bob": 1}
    diags: list = []
    fallback = _cx_or_diagnostic("Ghost", p_index, col_centers=col_centers, diags=diags)
    assert any(d.code == "unknown_participant" and d.severity == "error" for d in diags)
    assert fallback != col_centers[0]


def test_skip_guard_emits_diagnostic():
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
    import pathlib
    import mermaid_render
    init_src = pathlib.Path(mermaid_render.__file__).read_text()
    assert "Phase 4 will wire per-type validation" not in init_src


def test_unmatched_deactivate_produces_diagnostic():
    r = compile_sequence("sequenceDiagram\n  A->>B: hi\n  deactivate B")
    assert any(
        d.code == "unmatched_deactivate" and d.severity == "warning"
        for d in r.diagnostics
    )


# ── T10: Gallery provenance + status lanes + atomic replacement ───────────────

def test_t10_validation_result_has_structural_semantic_lanes():
    from mermaid_render.layout._geometry import ValidationResult
    vr = ValidationResult()
    assert hasattr(vr, "structural_geometry")
    assert hasattr(vr, "semantic_geometry")
    assert vr.structural_geometry == "unvalidated"
    assert vr.semantic_geometry == "unvalidated"


def test_t10_dispatch_validate_sequence_populates_lanes():
    vr = _dispatch_validate("sequenceDiagram\n  Alice->>Bob: hi")
    assert vr.structural_geometry in ("pass", "fail", "unvalidated")
    assert vr.semantic_geometry in ("pass", "fail", "unvalidated")
    # clean simple diagram should pass both lanes
    assert vr.structural_geometry == "pass"
    assert vr.semantic_geometry == "pass"


def test_t10_dispatch_validate_geometry_field_matches_structural():
    """geometry field (backward compat) should equal structural_geometry."""
    vr = _dispatch_validate("sequenceDiagram\n  A->>B: hi")
    assert vr.geometry == vr.structural_geometry


def test_t10_atomic_write_gallery_preserves_on_failure():
    """_atomic_write_gallery with raise_mid_write=True must leave out_dir untouched."""
    import shutil
    import tempfile
    from pathlib import Path
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from compare_gallery import _atomic_write_gallery  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gallery"
        out.mkdir()
        sentinel = out / "test_artifact.html"
        sentinel.write_text("<old/>")
        try:
            _atomic_write_gallery(out, raise_mid_write=True)
        except Exception:
            pass
        assert sentinel.read_text() == "<old/>", "atomic replace violated: old output overwritten"


def test_t10_strict_flag_in_compare_gallery_help():
    """--strict flag must appear in compare_gallery.py --help output."""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "compare_gallery.py"), "--help"],
        capture_output=True, text=True,
    )
    assert "--strict" in result.stdout, "--strict not found in --help output"


def test_t10_modules_dict_in_metadata():
    """_collect_metadata must return a 'modules' dict covering _geometry.py."""
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT / "tools"))
    from compare_gallery import _collect_metadata  # noqa: PLC0415
    from pathlib import Path as _Path

    meta = _collect_metadata([], _Path("/tmp"), 0, [])
    assert "modules" in meta
    assert "_geometry.py" in meta["modules"]
    assert "_strategies.py" in meta["modules"]
    assert "_text.py" in meta["modules"]
    assert meta["modules"]["_geometry.py"].get("sha256") is not None


# ── T12: New regression fixtures ──────────────────────────────────────────────

_T12_FIXTURES = [
    ("sequence-width-320.mmd",                      "pass", "pass",    "pass"),
    ("sequence-width-480.mmd",                      "pass", "pass",    "pass"),
    ("sequence-width-800.mmd",                      "pass", "pass",    "pass"),
    ("sequence-long-participants.mmd",               "pass", "pass",    "pass"),
    ("sequence-multiline-message.mmd",               "pass", "pass",    "pass"),
    ("sequence-nested-fragments.mmd",                "pass", "pass",    "pass"),
    ("sequence-nested-activations.mmd",              "pass", "pass",    "pass"),
    ("sequence-unclosed-activation.mmd",             "pass", "partial", "pass"),
    ("sequence-unmatched-deactivate.mmd",            "pass", "partial", "pass"),
    ("sequence-active-self-message.mmd",             "pass", "pass",    "pass"),
    ("sequence-middle-participant-self-message.mmd", "pass", "pass",    "pass"),
    ("sequence-bidirectional-self-message.mmd",      "pass", "pass",    "pass"),
    ("sequence-full-arrow-token-matrix.mmd",         "pass", "pass",    "pass"),
    ("sequence-unknown-participant.mmd",             "pass", "pass",    "pass"),
    ("sequence-autonumber-unsupported.mmd",          "pass", "partial", "pass"),
    ("sequence-critical-option.mmd",                 "pass", "pass",    "pass"),
    ("sequence-rect.mmd",                            "pass", "pass",    "pass"),
    ("sequence-multiline-note.mmd",                  "pass", "pass",    "pass"),
    ("sequence-multiline-fragment.mmd",              "pass", "pass",    "pass"),
    ("sequence-create-destroy.mmd",                  "pass", "pass",    "pass"),
]


@pytest.mark.parametrize("fixture,exp_render,exp_syntax,exp_struct", _T12_FIXTURES)
def test_t12_fixture_status(fixture, exp_render, exp_syntax, exp_struct):
    """AC-R.2/AC-R.3: each T12 fixture matches its expected status table entry."""
    fixture_path = REPO_ROOT / "tests" / "fixtures" / fixture
    assert fixture_path.exists(), f"Fixture file missing: {fixture_path}"
    src = fixture_path.read_text(encoding="utf-8").strip()
    vr = _dispatch_validate(src)
    assert vr.render == exp_render, f"{fixture}: render={vr.render!r} != {exp_render!r}"
    assert vr.syntax_coverage == exp_syntax, (
        f"{fixture}: syntax_coverage={vr.syntax_coverage!r} != {exp_syntax!r}"
    )
    assert vr.structural_geometry == exp_struct, (
        f"{fixture}: structural_geometry={vr.structural_geometry!r} != {exp_struct!r}"
    )


# ── Participant lifecycle (create/destroy) ────────────────────────────────────

def _seq_lifecycle(src: str):
    """Return (html, geom) for a sequenceDiagram source string."""
    return _layout_lifeline("sequenceDiagram\n" + src, "LR", 0)


def test_created_at_row_set_for_created_participant():
    """AC-1: created_at_row is set on the participant geometry."""
    _, geom = _seq_lifecycle("Alice->>Bob: Hi\ncreate participant Carol\nAlice->>Carol: Hello")
    carol = next(p for p in geom.participants if p.participant_id == "Carol")
    assert carol.created_at_row is not None
    assert carol.created_at_row >= 1  # appears after at least one message


def test_created_participant_lifeline_starts_late():
    """AC-2: created participant lifeline_top is below diagram ll_top."""
    _, geom = _seq_lifecycle("Alice->>Bob: Hi\ncreate participant Carol\nAlice->>Carol: Hello")
    alice = next(p for p in geom.participants if p.participant_id == "Alice")
    carol = next(p for p in geom.participants if p.participant_id == "Carol")
    assert carol.lifeline_top > alice.lifeline_top


def test_destroyed_at_row_set_for_destroyed_participant():
    """AC-3: destroyed_at_row is set on the participant geometry."""
    _, geom = _seq_lifecycle("Alice->>Bob: Hi\ndestroy Bob\nBob-->>Alice: Bye")
    bob = next(p for p in geom.participants if p.participant_id == "Bob")
    assert bob.destroyed_at_row is not None
    assert bob.destroyed_at_row >= 1


def test_destroyed_participant_lifeline_ends_early():
    """AC-3: destroyed participant lifeline_bottom is above ll_bot."""
    _, geom = _seq_lifecycle("Alice->>Bob: Hi\ndestroy Bob\nBob-->>Alice: Bye\nAlice->>Alice: more")
    alice = next(p for p in geom.participants if p.participant_id == "Alice")
    bob = next(p for p in geom.participants if p.participant_id == "Bob")
    assert bob.lifeline_bottom < alice.lifeline_bottom


def test_destroy_x_marker_in_html():
    """AC-4: X marker lines appear in HTML for destroyed participant."""
    html, _ = _seq_lifecycle("Alice->>Bob: Hi\ndestroy Bob\nBob-->>Alice: Bye")
    # Two crossing SVG lines with no stroke-dasharray (solid, not lifeline)
    x_lines = re.findall(r'<line[^>]+stroke-width="2"[^/]*/>', html)
    assert len(x_lines) == 2, f"Expected 2 X marker lines, got {len(x_lines)}: {x_lines}"


def test_no_lifecycle_diagnostics():
    """AC-5: no Diagnostic for create_participant or destroy."""
    _, geom = _seq_lifecycle(
        "Alice->>Bob: Hi\ncreate participant Carol\nAlice->>Carol: Hello\n"
        "destroy Bob\nBob-->>Alice: Bye"
    )
    features = {d.feature for d in geom.diagnostics}
    assert "create_participant" not in features
    assert "destroy" not in features


def test_normal_participants_unaffected_by_lifecycle():
    """AC-8: participants without lifecycle directives keep full lifeline."""
    _, geom = _seq_lifecycle(
        "Alice->>Bob: Hi\ncreate participant Carol\nAlice->>Carol: Hello\n"
        "destroy Bob\nBob-->>Alice: Bye"
    )
    alice = next(p for p in geom.participants if p.participant_id == "Alice")
    assert alice.created_at_row is None
    assert alice.destroyed_at_row is None
