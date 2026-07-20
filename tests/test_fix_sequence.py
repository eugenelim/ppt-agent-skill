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
    """Check if any X cross marker is present (two lines for --x arrow)."""
    # Cross is rendered as two SVG <line> elements adjacent to each other
    return bool(re.search(r'<line x1="[^"]*" y1="[^"]*-\d+" x2="[^"]*" y2="[^"]*\+\d+"', html)
                or len(re.findall(r'stroke="var\(--edge[^"]*"\s+stroke-width="1\.5"', html)) >= 2)


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
        """Note left of Alice is positioned to the left of Alice's column."""
        html = _render("sequence-notes-all.mmd")
        polys = _note_polys(html)
        # Alice is roughly at cx=160, col_w=160, so her left edge ≈ 80
        # Note left of Alice should have x_max <= 80 (left of Alice's left edge)
        left_notes = [p for p in polys if p[1] <= 90]
        assert len(left_notes) >= 1, f"No left-of note found. All note polys: {polys}"

    def test_right_of_note_is_right_of_participant(self):
        """Note right of Carol is positioned to the right of Carol's column."""
        html = _render("sequence-notes-all.mmd")
        cw = int(re.search(r'width:(\d+)px', html).group(1))
        polys = _note_polys(html)
        # Canvas width=800, Carol is ~3rd of 3 participants
        # Note right of Carol should have x_min >= ~700
        right_notes = [p for p in polys if p[0] >= cw * 0.85]
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
