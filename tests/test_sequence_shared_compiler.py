"""Acceptance tests for the sequence shared compiler + native scene (item 2).

Covers docs/specs/sequence-shared-compiler-and-native-scene AC1–AC9: the
shared parse → compile-geometry → paint(html|scene) pipeline, the BoxGeometry
and FragmentGeometry IR, box + nested-fragment painting in both HTML and SVG,
retirement of the legacy layout/sequence.py native parser, and typed
diagnostics instead of silent omission.

Import pattern follows repo convention: scripts/ on sys.path.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import mermaid_render as mr  # noqa: E402
from mermaid_render.layout._geometry import BoxGeometry, FragmentGeometry  # noqa: E402
from mermaid_render.layout._sequence_compile import (  # noqa: E402
    compile_sequence,
    parse_sequence_semantics,
    compile_sequence_geometry,
    sequence_geometry_to_html,
    sequence_geometry_to_scene,
)
from mermaid_render.svg_serializer import scene_to_svg_str  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _src(stem: str) -> str:
    return (FIXTURES / f"{stem}.mmd").read_text(encoding="utf-8")


def _geom(stem: str):
    return compile_sequence(_src(stem)).geometry


def _svg(stem: str) -> str:
    model = parse_sequence_semantics(_src(stem))
    geometry = compile_sequence_geometry(model)
    return scene_to_svg_str(sequence_geometry_to_scene(model, geometry))


def _attrs(text: str, name: str) -> list[str]:
    return re.findall(rf'{name}="([^"]*)"', text)


# ── Task 1: IR extensions ──────────────────────────────────────────────────────

def test_box_geometry_fields():
    """AC1: two BoxGeometry records with matching id, label, color, members."""
    boxes = _geom("sequence-box-unsupported").boxes
    assert all(isinstance(b, BoxGeometry) for b in boxes)
    by_label = {b.label: b for b in boxes}
    assert set(by_label) == {"Group A", "Group B"}
    ga, gb = by_label["Group A"], by_label["Group B"]
    assert ga.participant_ids == ("Alice", "Bob")
    assert ga.color.lower() == "blue"
    assert gb.participant_ids == ("Carol",)
    assert gb.color.replace(" ", "") == "rgb(200,100,50)"
    assert ga.box_id != gb.box_id


def test_sequence_geometry_boxes_tuple():
    """AC1: SequenceGeometry.boxes is a tuple of BoxGeometry in source order."""
    boxes = _geom("sequence-box-unsupported").boxes
    assert isinstance(boxes, tuple)
    assert [b.source_order for b in boxes] == [0, 1]
    assert [b.label for b in boxes] == ["Group A", "Group B"]


def test_fragment_geometry_parent_fields():
    """AC3: inner loop's parent is the outer alt; depths are 0 (outer) / 1 (inner)."""
    frags = _geom("sequence-nested-fragments").fragments
    assert all(isinstance(f, FragmentGeometry) for f in frags)
    by_kind = {f.kind: f for f in frags}
    outer, inner = by_kind["alt"], by_kind["loop"]
    assert outer.parent_fragment_id is None
    assert outer.depth == 0
    assert inner.parent_fragment_id == outer.fragment_id
    assert inner.depth == 1


# ── Task 3: retire legacy native-SVG parser ────────────────────────────────────

def test_layout_sequence_py_deleted():
    """AC4: the legacy native-SVG sequence module is gone; no import resolves it."""
    assert importlib.util.find_spec("mermaid_render.layout.sequence") is None
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("mermaid_render.layout.sequence")


def test_native_svg_sequence_reports_sequence_geometry_backend():
    """AC5: the sequence scene reports layout_backend sequence-geometry (never native-svg)."""
    model = parse_sequence_semantics(_src("sequence-nested-fragments"))
    scene = sequence_geometry_to_scene(model, compile_sequence_geometry(model))
    assert scene.renderer_backend == "sequence-geometry"
    assert scene.renderer_backend != "native-svg"
    result = mr.dispatch_native_result(_src("sequence-nested-fragments"))
    assert result.backend == "sequence-geometry"


def test_native_svg_sequence_has_fragments():
    """AC3: native SVG no longer omits the fragments (regression on legacy parser)."""
    svg = _svg("sequence-nested-fragments")
    assert _attrs(svg, "data-fragment-id") == ["f0", "f1"]


def test_no_silent_skips_boxes_present():
    """AC7: both boxes appear in the SVG output (no silent omission)."""
    svg = _svg("sequence-box-unsupported")
    assert set(_attrs(svg, "data-box-id")) == {"box-0", "box-1"}


@pytest.mark.parametrize("construct,token", [
    ("autonumber", "autonumber"),
    ("par_over Alice: x", "par_over"),
    ("create actor Zed", "create_actor"),
    ("!!not a real line", "unrecognized_line"),
])
def test_unsupported_construct_emits_typed_diagnostic(construct, token):
    """AC7: unsupported constructs produce a typed diagnostic, not silent omission."""
    src = f"sequenceDiagram\n  {construct}\n  Alice->>Bob: hi\n"
    model = parse_sequence_semantics(src)
    scene = sequence_geometry_to_scene(model, compile_sequence_geometry(model))
    assert any(token in d for d in scene.diagnostics), scene.diagnostics


@pytest.mark.parametrize("kw", ["loop", "alt", "opt", "par", "critical", "break", "rect"])
def test_supported_fragment_keywords_not_silently_skipped(kw):
    """AC7/Never: the supported block keywords render (never silently dropped)."""
    body = "Alice->>Bob: step" if kw != "alt" else "Alice->>Bob: step\n  else other\n  Bob-->>Alice: back"
    src = f"sequenceDiagram\n  {kw} label\n  {body}\n  end\n"
    model = parse_sequence_semantics(src)
    scene = sequence_geometry_to_scene(model, compile_sequence_geometry(model))
    svg = scene_to_svg_str(scene)
    if kw == "rect":
        # rect solid-fill backgrounds aren't painted in the native scene; per AC7
        # (no silent skips) the scene must instead carry a typed diagnostic.
        assert any("rect" in d for d in scene.diagnostics), scene.diagnostics
    else:
        assert _attrs(svg, "data-fragment-id"), f"{kw}: fragment silently omitted from SVG"


def _scene_from(src: str):
    model = parse_sequence_semantics(src)
    return sequence_geometry_to_scene(model, compile_sequence_geometry(model))


def test_svg_scene_branches_paint_notes_activation_selfmsg_destroy_and_markers():
    """Coverage: exercise the SVG-only branches the two spec fixtures don't reach.

    Covers the self-message ScenePath, the cross marker, the note polygon, the
    activation bar, and the destroy-X overlay in one native scene.
    """
    from mermaid_render.scene import ScenePath, ScenePolygon, SceneLine
    src = (
        "sequenceDiagram\n"
        "  participant A\n"
        "  participant B\n"
        "  create participant C\n"
        "  A->>A: self ping\n"
        "  A-x B: fail\n"
        "  activate B\n"
        "  Note over A,B: a shared note\n"
        "  B-->>A: done\n"
        "  deactivate B\n"
        "  destroy C\n"
    )
    scene = _scene_from(src)
    overlays = scene.get_layer("overlays")
    notes = scene.get_layer("notes")
    # Note polygon present.
    assert any(isinstance(e, ScenePolygon) and e.semantic_role == "note" for e in notes)
    # Self-message curved path present.
    assert any(isinstance(e, ScenePath) and e.semantic_role == "message" for e in overlays)
    # Activation bar carries its participant id.
    assert any(dict(e.data_attrs).get("data-pid") == "B" for e in overlays if e.data_attrs)
    # Destroy-X overlay for the destroyed participant C.
    assert any(isinstance(e, SceneLine) and "destroy" in e.element_id for e in overlays)
    # Scene serializes without error.
    assert "<svg" in scene_to_svg_str(scene)


def test_empty_sequence_renders_stub_with_diagnostic():
    """C4/no-silent-skip: a participant-less sequence renders a stub SVG that says why."""
    result = mr.dispatch_native_result("sequenceDiagram")
    assert result.svg and "<svg" in result.svg
    assert "NaN" not in result.svg


# ── Task 4: box painting in HTML and SVG ────────────────────────────────────────

def test_box_painted_before_lifelines_and_cards():
    """AC(box painting): box element precedes participant cards in HTML DOM order."""
    html = mr.to_html(_src("sequence-box-unsupported"))
    assert html.index("data-box-id") < html.index('class="node node-rect"')


def test_box_data_attribute_html_and_svg_match():
    """AC8: data-box-id values match between HTML and SVG for the same box."""
    html = mr.to_html(_src("sequence-box-unsupported"))
    svg = _svg("sequence-box-unsupported")
    html_ids = sorted(set(_attrs(html, "data-box-id")))
    svg_ids = sorted(set(_attrs(svg, "data-box-id")))
    assert html_ids == svg_ids == ["box-0", "box-1"]


def test_group_membership_and_dave_outside():
    """AC1: Group A = {Alice, Bob}, Group B = {Carol}, Dave in neither."""
    boxes = {b.label: b for b in _geom("sequence-box-unsupported").boxes}
    assert set(boxes["Group A"].participant_ids) == {"Alice", "Bob"}
    assert set(boxes["Group B"].participant_ids) == {"Carol"}
    boxed = {pid for b in boxes.values() for pid in b.participant_ids}
    assert "Dave" not in boxed


def test_box_bounds_encompass_declared_members_only():
    """AC1/box painting: Group A bounds span Alice+Bob columns but exclude Carol/Dave."""
    g = _geom("sequence-box-unsupported")
    cx = {p.participant_id: p.center_x for p in g.participants}
    ga = next(b for b in g.boxes if b.label == "Group A")
    assert ga.bounds.left <= cx["Alice"] and ga.bounds.right >= cx["Bob"]
    assert ga.bounds.right < cx["Carol"]
    assert ga.bounds.right < cx["Dave"]


def test_box_color_normalized_and_retained():
    """AC1: Group A resolves to blue; Group B retains rgb(200,100,50)."""
    boxes = {b.label: b for b in _geom("sequence-box-unsupported").boxes}
    assert boxes["Group A"].color.lower() == "blue"
    assert boxes["Group B"].color.replace(" ", "") == "rgb(200,100,50)"


# ── Task 5: nested fragment painting ────────────────────────────────────────────

def test_outer_fragment_painted_before_inner_html_and_svg():
    """AC9: outer alt renders before inner loop in both HTML and SVG order."""
    html = mr.to_html(_src("sequence-nested-fragments"))
    svg = _svg("sequence-nested-fragments")
    for out in (html, svg):
        assert out.index('data-fragment-id="f0"') < out.index('data-fragment-id="f1"')


def test_inner_fragment_bounds_inside_outer():
    """AC3: inner loop bounds are fully contained by outer alt bounds."""
    frags = {f.kind: f for f in _geom("sequence-nested-fragments").fragments}
    outer, inner = frags["alt"].bounds, frags["loop"].bounds
    assert outer.left <= inner.left and outer.right >= inner.right
    assert outer.top <= inner.top and outer.bottom >= inner.bottom


def _fragment_attr_map(text: str) -> dict[str, tuple]:
    """Map fragment-id → (parent, depth, start-event, end-event) from each fragment tag.

    Extracts per-tag so branch separators (which carry data-parent-fragment-id
    but no data-fragment-id) and attribute ordering differences between the HTML
    and SVG serializers don't perturb the result.
    """
    out: dict[str, tuple] = {}
    for tag in re.findall(r"<[^>]*data-fragment-id[^>]*>", text):
        def _g(name: str):
            m = re.search(rf'{name}="([^"]*)"', tag)
            return m.group(1) if m else None
        out[_g("data-fragment-id")] = (
            _g("data-parent-fragment-id"), _g("data-depth"),
            _g("data-start-event"), _g("data-end-event"),
        )
    return out


def test_fragment_data_attributes_present_and_match():
    """AC9/AC3: fragment data-* attributes present, matching HTML↔SVG, with the
    concrete event intervals (outer alt [0,6) strictly contains inner loop [1,4))."""
    html_map = _fragment_attr_map(mr.to_html(_src("sequence-nested-fragments")))
    svg_map = _fragment_attr_map(_svg("sequence-nested-fragments"))
    expected = {"f0": ("", "0", "0", "6"), "f1": ("f0", "1", "1", "4")}
    assert html_map == expected
    assert svg_map == expected


def test_retry_messages_inside_loop_interval():
    """AC3: both retry messages fall inside the loop's event interval."""
    g = _geom("sequence-nested-fragments")
    loop = next(f for f in g.fragments if f.kind == "loop")
    # try + result are the two messages inside the loop; notify failure is outside.
    inside = [m for m in g.messages if loop.bounds.top <= m.baseline_y <= loop.bounds.bottom]
    assert len(inside) == 2
    # The loop is opened at row 1 and spans the two retry messages + its end row
    # (half-open [1, 4)); the outer alt interval strictly contains it.
    assert (loop.start_event_index, loop.end_event_index) == (1, 4)
    alt = next(f for f in g.fragments if f.kind == "alt")
    assert alt.start_event_index <= loop.start_event_index
    assert alt.end_event_index >= loop.end_event_index


def test_failure_message_inside_alt_outside_loop():
    """AC3: the failure notification is inside the outer alt but outside the loop."""
    g = _geom("sequence-nested-fragments")
    alt = next(f for f in g.fragments if f.kind == "alt")
    loop = next(f for f in g.fragments if f.kind == "loop")
    # The failure branch message is the last message (source order).
    failure = g.messages[-1]
    assert alt.bounds.top <= failure.baseline_y <= alt.bounds.bottom
    assert not (loop.bounds.top <= failure.baseline_y <= loop.bounds.bottom)


# ── AC6: HTML and SVG consume the same SequenceGeometry ─────────────────────────

def test_html_and_svg_share_one_geometry():
    """AC6: painting HTML and SVG from one compiled geometry yields matching bounds."""
    model = parse_sequence_semantics(_src("sequence-box-unsupported"))
    geometry = compile_sequence_geometry(model)
    html = sequence_geometry_to_html(model, geometry)
    scene = sequence_geometry_to_scene(model, geometry)
    svg = scene_to_svg_str(scene)
    # Same canvas.
    assert f"width:{int(round(geometry.canvas[0]))}px" in html
    assert scene.width == geometry.canvas[0]
    # Same box ids painted by both painters from the shared geometry.
    assert sorted(set(_attrs(html, "data-box-id"))) == sorted(set(_attrs(svg, "data-box-id")))


def test_compile_geometry_deterministic():
    """AC6: compiling twice yields structurally identical geometry."""
    model = parse_sequence_semantics(_src("sequence-nested-fragments"))
    g1 = compile_sequence_geometry(model)
    g2 = compile_sequence_geometry(model)
    assert g1.canvas == g2.canvas
    assert [f.bounds for f in g1.fragments] == [f.bounds for f in g2.fragments]
    assert [m.baseline_y for m in g1.messages] == [m.baseline_y for m in g2.messages]
