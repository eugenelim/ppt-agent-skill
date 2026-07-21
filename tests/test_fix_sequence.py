"""Regression tests for sequenceDiagram renderer fixes.

Covers:
- Bottom participant boxes (FIX-SEQ-01)
- Block rects spanning full content height (FIX-SEQ-02)
- +/- activation shorthand parsed correctly (FIX-SEQ-03)
- Note left-of / right-of / spanning-over positioning (FIX-SEQ-04)
- Arrow head styles: no-head for ->, cross for --x (FIX-SEQ-05)
- Canvas height accommodates bottom boxes without overflow (FIX-SEQ-06)
- diagram-lifeline class present (FIX-SEQ-07)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _dispatch

FIXTURES = REPO_ROOT / "tests" / "fixtures"


# ── helpers ──────────────────────────────────────────────────────────────────

def _render(fname: str, width: int = 800) -> str:
    src = (FIXTURES / fname).read_text()
    return _dispatch(src, None, width)


def _node_divs(html: str) -> int:
    return len(re.findall(r'<div class="node', html))


def _note_polys(html: str) -> list[tuple[float, float]]:
    """Return list of (x_min, x_max) for each note polygon."""
    result = []
    for pts in re.findall(r'<polygon points="([^"]+)"[^>]+fill="var\(--node-bg', html):
        xs = [float(p.split(",")[0]) for p in pts.strip().split()]
        result.append((min(xs), max(xs)))
    return result


def _arrow_polys(html: str) -> int:
    """Count filled arrowhead polygons (not note polygons)."""
    return len(re.findall(r'<polygon points="[^"]+"\s+fill="var\(--edge', html))


def _block_heights(html: str) -> list[int]:
    """Return sorted heights of block background rects (stroke-dasharray marks them)."""
    rects = re.findall(r'<rect[^>]+stroke-dasharray="5 3"[^>]*/>', html)
    return sorted(
        int(re.search(r'height="(\d+)"', r).group(1))
        for r in rects
        if re.search(r'height="(\d+)"', r)
    )


def _canvas_height(html: str) -> int:
    m = re.search(r'<div[^>]+mermaid-layout[^>]+height:(\d+)px', html)
    return int(m.group(1)) if m else 0


def _activation_boxes(html: str) -> int:
    return len(re.findall(r'opacity="0\.35"', html))


def _has_cross_marker(html: str) -> bool:
    """Return True iff HTML contains two cross lines with mirrored y-values (X geometry)."""
    segs = re.findall(
        r'<line x1="(\d+)" y1="(\d+)" x2="(\d+)" y2="(\d+)"[^>]*stroke-width="1\.5"',
        html,
    )
    for i, (ax1, ay1, ax2, ay2) in enumerate(segs):
        for bx1, by1, bx2, by2 in segs[i + 1:]:
            if ax1 == bx1 and ax2 == bx2 and ay1 == by2 and ay2 == by1:
                return True
    return False


# ── FIX-SEQ-01: Bottom participant boxes ─────────────────────────────────────

class TestBottomParticipantBoxes:
    def test_basic_has_4_node_divs(self):
        """2 participants → 2 top boxes + 2 bottom boxes = 4 node divs."""
        html = _render("sequence-basic.mmd")
        assert _node_divs(html) == 4

    def test_activation_has_6_node_divs(self):
        """3 participants → 6 node divs."""
        html = _render("sequence-activation.mmd")
        assert _node_divs(html) == 6

    def test_bottom_box_class_present(self):
        """Bottom boxes have the node-lifeline-bottom class."""
        html = _render("sequence-basic.mmd")
        assert "node-lifeline-bottom" in html

    def test_bottom_box_at_ll_bot(self):
        """Bottom box top position matches lifeline bottom (ll_bot)."""
        html = _render("sequence-basic.mmd")
        # Both top boxes are at top:24px, bottom boxes at a larger top value
        top_values = sorted(
            int(m) for m in re.findall(r'class="node node-rect[^"]*"[^>]+top:(\d+)px', html)
        )
        # Should have 2 small values (top boxes) and 2 large values (bottom boxes)
        assert len(top_values) == 4
        assert top_values[0] == top_values[1]  # same top for top boxes
        assert top_values[2] == top_values[3]  # same top for bottom boxes
        assert top_values[2] > top_values[1]   # bottom boxes lower than top boxes


# ── FIX-SEQ-02: Block rects spanning full content ────────────────────────────

class TestBlockSpanning:
    def test_loop_block_height(self):
        """loop block spans its 2 inner messages + header = 3 × ROW_H."""
        html = _render("sequence-blocks.mmd")
        heights = _block_heights(html)
        assert 120 in heights, f"Expected 120 (3×40) in block heights {heights}"

    def test_alt_block_height(self):
        """alt+else block spans 4 rows (alt header + OK + else + 500) = 4 × ROW_H."""
        html = _render("sequence-blocks.mmd")
        heights = _block_heights(html)
        assert 160 in heights, f"Expected 160 (4×40) in block heights {heights}"

    def test_complex_block_height(self):
        """alt block in complex fixture spans 4 rows."""
        html = _render("sequence-complex.mmd")
        heights = _block_heights(html)
        assert 160 in heights, f"Expected 160 in complex block heights {heights}"

    def test_block_single_row_fallback(self):
        """No block returns height < ROW_H (min 1 row = 40px)."""
        html = _render("sequence-blocks.mmd")
        for h in _block_heights(html):
            assert h >= 40, f"Block height {h} < ROW_H 40"


# ── FIX-SEQ-03: Activation shorthand ─────────────────────────────────────────

class TestActivationShorthand:
    def test_explicit_activate_deactivate(self):
        """Explicit activate/deactivate creates activation boxes."""
        html = _render("sequence-activation.mmd")
        assert _activation_boxes(html) == 2

    def test_plus_minus_shorthand_activates(self):
        """Alice->>+Bob creates an activation box for Bob."""
        html = _render("sequence-all-arrowtypes.mmd")
        assert _activation_boxes(html) >= 1

    def test_plus_dst_not_in_participant_name(self):
        """+Bob is parsed as participant Bob, not +Bob."""
        html = _render("sequence-all-arrowtypes.mmd")
        # Should not have node with id '+Bob'
        assert 'data-node-id="+Bob"' not in html
        assert 'data-node-id="Bob"' in html


# ── FIX-SEQ-04: Note positioning ─────────────────────────────────────────────

class TestNotePositioning:
    def test_left_of_note_is_left_of_participant(self):
        """Note left of Alice is positioned to the left of Alice's column.

        After the canvas-expansion fix, the canvas widens to accommodate left-of
        notes. All notes must stay within [0, canvas_w] and the left-of note must
        be in the leftmost third of the canvas (it's left of the first participant).
        """
        html = _render("sequence-notes-all.mmd")
        cw = int(re.search(r'width:(\d+)px', html).group(1))
        polys = _note_polys(html)
        # Left-of note is in the left third of the (now-expanded) canvas
        left_notes = [p for p in polys if p[1] <= cw // 3]
        assert len(left_notes) >= 1, f"No left-of note found. Canvas={cw} polys={polys}"
        # All note polygons must be within canvas bounds
        for x_min, x_max in polys:
            assert x_min >= 0, f"Note polygon starts at negative x={x_min}"
            assert x_max <= cw, f"Note polygon ends at x={x_max} beyond canvas_w={cw}"

    def test_right_of_note_is_right_of_participant(self):
        """Note right of Carol is positioned to the right of Carol's column.

        After the canvas-expansion fix, the canvas widens to accommodate right-of
        notes. The right-of note is in the rightmost third of the canvas.
        """
        html = _render("sequence-notes-all.mmd")
        cw = int(re.search(r'width:(\d+)px', html).group(1))
        polys = _note_polys(html)
        # Right-of note is in the right third of the (now-expanded) canvas
        right_notes = [p for p in polys if p[0] >= cw * 2 // 3]
        assert len(right_notes) >= 1, f"No right-of note found. Canvas={cw} polys={polys}"

    def test_spanning_note_over_multiple_participants(self):
        """Note over Alice,Carol is wider than a single column."""
        html = _render("sequence-notes-all.mmd")
        col_w = 160
        polys = _note_polys(html)
        wide_notes = [p for p in polys if (p[1] - p[0]) > col_w * 2]
        assert len(wide_notes) >= 1, f"No spanning note found. polys={polys}"

    def test_single_over_note_is_single_column_width(self):
        """Note over Alice (single) is approximately one column wide."""
        html = _render("sequence-note.mmd")
        polys = _note_polys(html)
        assert len(polys) == 2, f"Expected 2 note polys, got {len(polys)}"
        for x_min, x_max in polys:
            assert (x_max - x_min) <= 170, f"Note too wide: {x_max - x_min}px"


# ── FIX-SEQ-05: Arrow head styles ────────────────────────────────────────────

class TestArrowHeadStyles:
    def test_open_arrow_has_no_head(self):
        """-> (open arrow) does not get a filled polygon arrowhead."""
        html = _render("sequence-all-arrowtypes.mmd")
        # 8 messages, minus 1 for -> (no head), minus 1 for --x (cross, not polygon) = 6
        assert _arrow_polys(html) == 6

    def test_solid_filled_arrows_have_heads(self):
        """All ->> messages in basic fixture have arrowheads."""
        html = _render("sequence-basic.mmd")
        assert _arrow_polys(html) == 4

    def test_self_loop_has_arrowhead(self):
        """Self-message always gets a filled arrowhead."""
        html = _render("sequence-self-message.mmd")
        assert _arrow_polys(html) >= 1


# ── FIX-SEQ-06: Canvas height accommodates bottom boxes ──────────────────────

class TestCanvasHeight:
    def test_canvas_fits_bottom_boxes(self):
        """Canvas height must be >= ll_bot + BOX_H, not overflow."""
        for fname in [
            "sequence-basic.mmd",
            "sequence-blocks.mmd",
            "sequence-complex.mmd",
        ]:
            html = _render(fname)
            canvas_h = _canvas_height(html)
            # Find bottom boxes' top positions
            bottom_top_vals = [
                int(m) for m in re.findall(
                    r'node-lifeline-bottom[^>]+top:(\d+)px', html
                )
            ]
            if bottom_top_vals:
                box_bottom = max(bottom_top_vals) + 40  # BOX_H = 40
                assert box_bottom <= canvas_h, (
                    f"{fname}: bottom box extends to {box_bottom} but canvas is only {canvas_h}"
                )

    def test_canvas_height_increases_with_rows(self):
        """More messages → taller canvas."""
        h_basic = _canvas_height(_render("sequence-basic.mmd"))
        h_complex = _canvas_height(_render("sequence-complex.mmd"))
        assert h_complex > h_basic


# ── FIX-SEQ-07: diagram-lifeline class ───────────────────────────────────────

class TestDiagramClass:
    def test_lifeline_class_on_container(self):
        """Container div has diagram-lifeline class for CSS targeting."""
        for fname in [
            "sequence-basic.mmd",
            "sequence-blocks.mmd",
            "sequence-complex.mmd",
        ]:
            html = _render(fname)
            assert "diagram-lifeline" in html, f"{fname}: missing diagram-lifeline class"


# ── Smoke: all fixtures render without error ─────────────────────────────────

@pytest.mark.parametrize("fname", [
    "sequence-basic.mmd",
    "sequence-activation.mmd",
    "sequence-all-arrowtypes.mmd",
    "sequence-blocks.mmd",
    "sequence-complex.mmd",
    "sequence-note.mmd",
    "sequence-notes-all.mmd",
    "sequence-self-message.mmd",
])
def test_fixture_renders_without_error(fname):
    """Every sequence fixture should render without raising an exception."""
    html = _render(fname)
    assert len(html) > 100
    assert "diagram-lifeline" in html


# ── FIX-SEQ-08: Geometry invariants ──────────────────────────────────────────

class TestGeometryInvariants:
    """BUG-SEQ-A through BUG-SEQ-E: coordinate-system correctness.

    These tests assert spatial invariants the existing tests did not check
    (they only verified rendering without error). Each test corresponds to
    one geometry defect described in the seq-geometry-fix spec.
    """

    def test_participant_box_center_matches_lifeline(self):
        """BUG-SEQ-A: Each participant box center must equal its lifeline x.

        When a left-of note forces _cx_offset > 0, participant boxes must
        shift by the same amount. Uses sequence-notes-all.mmd which has a
        left-of note that triggers the offset.
        """
        html = _render("sequence-notes-all.mmd")
        col_w = int(re.search(r'class="node node-rect"[^>]+width:(\d+)px', html).group(1))
        # Top participant boxes: class="node node-rect" (exact — not node-lifeline-bottom)
        box_lefts = sorted(
            int(m) for m in re.findall(
                r'<div class="node node-rect"[^>]+left:(\d+)px', html
            )
        )
        # Vertical lifeline SVG lines: x1 == x2, stroke-dasharray="5 4"
        line_matches = re.findall(
            r'<line x1="(\d+)" y1="(\d+)" x2="(\d+)" y2="(\d+)"[^>]*stroke-dasharray="5 4"',
            html,
        )
        lifeline_xs = sorted(int(x1) for x1, _y1, x2, _y2 in line_matches if x1 == x2)
        assert box_lefts, "No top participant boxes found"
        assert lifeline_xs, "No lifelines found"
        assert len(box_lefts) == len(lifeline_xs), (
            f"Participant count mismatch: {len(box_lefts)} boxes, {len(lifeline_xs)} lifelines"
        )
        for box_left, lifeline_x in zip(box_lefts, lifeline_xs):
            box_center = box_left + col_w // 2
            assert abs(box_center - lifeline_x) <= 1, (
                f"Box center {box_center} ≠ lifeline x {lifeline_x} "
                f"(offset={lifeline_x - box_center}). BUG-SEQ-A not fixed."
            )

    def test_fragment_bounds_align_with_participant_columns(self):
        """BUG-SEQ-B: Fragment rect x must track _cx(), not the hardcoded PAD_H//2=20.

        Uses an inline diagram with a left-of note (forces _cx_offset > 0) AND a
        loop block so both the no-offset and offset paths are exercised.
        """
        src = (
            "sequenceDiagram\n"
            "    participant Alice\n"
            "    participant Bob\n"
            "    Note left of Alice: side note\n"
            "    loop Retry\n"
            "        Alice->>Bob: request\n"
            "        Bob-->>Alice: response\n"
            "    end\n"
        )
        html = _dispatch(src, None, 800)
        col_w = int(re.search(r'class="node node-rect"[^>]+width:(\d+)px', html).group(1))
        # Fragment background rects use stroke-dasharray="5 3"
        frag_xs = [
            float(m) for m in re.findall(
                r'<rect x="([^"]+)"[^>]*stroke-dasharray="5 3"', html
            )
        ]
        line_matches = re.findall(
            r'<line x1="(\d+)" y1="(\d+)" x2="(\d+)" y2="(\d+)"[^>]*stroke-dasharray="5 4"',
            html,
        )
        lifeline_xs = sorted(int(x1) for x1, _y1, x2, _y2 in line_matches if x1 == x2)
        assert frag_xs, "No fragment rects found"
        assert lifeline_xs, "No lifelines found"
        first_lifeline_x = min(lifeline_xs)
        PAD_H = 40  # mirrors PAD_H in _strategies.py; update both if the constant changes
        expected_frag_x0 = first_lifeline_x - col_w // 2 - PAD_H // 2
        for fx in frag_xs:
            assert fx >= 0, f"Fragment rect at negative x={fx}"
            assert abs(fx - expected_frag_x0) <= 2, (
                f"Fragment x={fx:.0f} ≠ expected {expected_frag_x0} "
                f"(first_lifeline={first_lifeline_x}, col_w={col_w}, _cx_offset>0). "
                "BUG-SEQ-B not fixed."
            )

    def test_message_label_uses_transform_centering(self):
        """BUG-SEQ-D: Message label spans must use left:{mid_x}px + translateX(-50%)."""
        html = _render("sequence-basic.mmd")
        edge_label_styles = re.findall(
            r'<span class="edge-label"[^>]+style="([^"]+)"', html
        )
        assert edge_label_styles, "No edge-label spans found in sequence-basic.mmd"
        # Compute expected mid_x from lifeline positions
        line_matches = re.findall(
            r'<line x1="(\d+)" y1="(\d+)" x2="(\d+)" y2="(\d+)"[^>]*stroke-dasharray="5 4"',
            html,
        )
        lifeline_xs = sorted(int(x1) for x1, _y1, x2, _y2 in line_matches if x1 == x2)
        assert len(lifeline_xs) >= 2, "Expected at least two lifelines"
        mid_x = (lifeline_xs[0] + lifeline_xs[-1]) // 2
        for style in edge_label_styles:
            assert "translateX(-50%)" in style, (
                f"Edge label missing transform:translateX(-50%): …{style[:100]}… "
                "BUG-SEQ-D not fixed."
            )
            assert f"left:{mid_x}px" in style, (
                f"Edge label left={style[:60]}… expected left:{mid_x}px. "
                "Old -30px offset regression or wrong mid_x."
            )

    def test_self_message_no_head_has_no_arrowhead(self):
        """BUG-SEQ-E: Self-message with -> (no-head) must not get a filled arrowhead."""
        src = "sequenceDiagram\n  Alice->Alice: think"
        html = _dispatch(src, None, 800)
        count = _arrow_polys(html)
        assert count == 0, (
            f"Self-message with -> should have 0 arrowhead polygons, got {count}. "
            "BUG-SEQ-E not fixed."
        )

    def test_self_message_with_head_has_arrowhead(self):
        """BUG-SEQ-E: Self-message with ->> must still get one filled arrowhead."""
        src = "sequenceDiagram\n  Alice->>Alice: call"
        html = _dispatch(src, None, 800)
        count = _arrow_polys(html)
        assert count == 1, (
            f"Self-message with ->> should have 1 arrowhead polygon, got {count}."
        )

    def test_self_message_cross_has_no_arrowhead(self):
        """BUG-SEQ-E: Self-message with -x must produce 0 filled polygons + 2 cross lines."""
        src = "sequenceDiagram\n  Alice-xAlice: fail"
        html = _dispatch(src, None, 800)
        poly_count = _arrow_polys(html)
        assert poly_count == 0, (
            f"Self-message with -x should have 0 arrowhead polygons, got {poly_count}."
        )
        assert _has_cross_marker(html), (
            "Self-message with -x should render two cross <line> elements."
        )

    def test_left_of_note_close_to_lifeline(self):
        """BUG-SEQ-C: Left-of note right edge must be near the first lifeline center.

        Old formula: anchor at box edge → gap ≈ 88px.
        Fixed formula: anchor at lifeline center with SIDE_NOTE_GAP=24 → gap = 24px.
        """
        html = _render("sequence-notes-all.mmd")
        line_matches = re.findall(
            r'<line x1="(\d+)" y1="(\d+)" x2="(\d+)" y2="(\d+)"[^>]*stroke-dasharray="5 4"',
            html,
        )
        lifeline_xs = sorted(int(x1) for x1, _y1, x2, _y2 in line_matches if x1 == x2)
        assert lifeline_xs, "No lifelines found"
        first_lifeline_x = min(lifeline_xs)
        polys = _note_polys(html)
        # Left-of note has its right edge strictly left of Alice's lifeline
        left_notes = [p for p in polys if p[1] < first_lifeline_x]
        assert len(left_notes) >= 1, (
            f"No left-of note found left of first lifeline x={first_lifeline_x}. polys={polys}"
        )
        SIDE_NOTE_GAP = 24
        for x_min, x_max in left_notes:
            gap = first_lifeline_x - x_max
            assert gap == SIDE_NOTE_GAP, (
                f"Left-of note gap={gap}px ≠ SIDE_NOTE_GAP={SIDE_NOTE_GAP}px "
                f"(note_right={x_max}, lifeline={first_lifeline_x}). BUG-SEQ-C not fixed."
            )
