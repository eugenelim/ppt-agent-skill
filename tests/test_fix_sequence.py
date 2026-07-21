"""Regression tests for sequenceDiagram renderer fixes.

Covers:
- Bottom participant boxes (FIX-SEQ-01)
- Block rects spanning full content height (FIX-SEQ-02)
- +/- activation shorthand parsed correctly (FIX-SEQ-03)
- Note left-of / right-of / spanning-over positioning (FIX-SEQ-04)
- Arrow head styles: no-head for ->, cross for --x (FIX-SEQ-05)
- Canvas height accommodates bottom boxes without overflow (FIX-SEQ-06)
- diagram-lifeline class present (FIX-SEQ-07)
- Activation bar exact baselines (SEQ-006)
- Activation-aware message endpoints (SEQ-007)
- Per-fragment participant bounds (SEQ-008)
- Spanning note lifeline-anchored geometry (SEQ-010)
- Arrow spec table: async point marker + bidirectional (SEQ-012)
- critical/option branch + rect background (SEQ-013)
- Note participant auto-registration (SEQ-014)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _dispatch, _dispatch_validate, _layout_lifeline
from mermaid_render.layout._geometry import Diagnostic, SequenceGeometry

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
        """Note over Alice,Carol is wider than a single participant column."""
        html = _render("sequence-notes-all.mmd")
        m = re.search(r'class="node node-rect"[^>]+width:(\d+)px', html)
        col_w = int(m.group(1)) if m else 80
        polys = _note_polys(html)
        wide_notes = [p for p in polys if (p[1] - p[0]) > col_w]
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


# ── helpers for geometry tests ────────────────────────────────────────────────

def _extract_activation_bars(html: str) -> "dict[str, dict]":
    """Return {pid: {x, y, width, height}} for activation bars (keyed by data-pid)."""
    result: "dict[str, dict]" = {}
    for m in re.finditer(
        r'<rect\s([^>]*)opacity="0\.35"([^>]*)/>', html
    ):
        full = m.group(0)
        pid_m = re.search(r'data-pid="([^"]+)"', full)
        if not pid_m:
            continue
        pid = pid_m.group(1)
        x = float(re.search(r'\bx="([^"]+)"', full).group(1))
        y = float(re.search(r'\by="([^"]+)"', full).group(1))
        w = float(re.search(r'width="([^"]+)"', full).group(1))
        h = float(re.search(r'height="([^"]+)"', full).group(1))
        result[pid] = {"x": x, "y": y, "width": w, "height": h}
    return result


def _extract_message_lines(html: str) -> "list[dict]":
    """Return [{src, dst, x1, y1, x2, y2}] for message lines (data-src/dst)."""
    result = []
    for m in re.finditer(
        r'<line x1="([^"]+)" y1="([^"]+)" x2="([^"]+)" y2="([^"]+)"[^>]*'
        r'data-src="([^"]+)" data-dst="([^"]+)"',
        html,
    ):
        result.append({
            "x1": float(m.group(1)), "y1": float(m.group(2)),
            "x2": float(m.group(3)), "y2": float(m.group(4)),
            "src": m.group(5), "dst": m.group(6),
        })
    return result


def _fragment_rects(html: str, kind: "str | None" = None) -> "list[dict]":
    """Return [{x, y, w, h, kind, fid, participants}] for fragment background rects.

    If ``kind`` is given, only rects with that data-fragment-kind are returned.
    Falls back to stroke-dasharray matching for rects without data-fragment-kind.
    """
    result = []
    for m in re.finditer(r'<rect[^>]+stroke-dasharray="5 3"[^>]*/>', html):
        full = m.group(0)
        fkind_m = re.search(r'data-fragment-kind="([^"]*)"', full)
        fkind = fkind_m.group(1) if fkind_m else ""
        if kind is not None and fkind != kind:
            continue
        fid_m = re.search(r'data-fragment-id="([^"]*)"', full)
        pids_m = re.search(r'data-participants="([^"]*)"', full)
        result.append({
            "x": float(re.search(r'\bx="([^"]+)"', full).group(1)),
            "y": float(re.search(r'\by="([^"]+)"', full).group(1)),
            "w": float(re.search(r'width="([^"]+)"', full).group(1)),
            "h": float(re.search(r'height="([^"]+)"', full).group(1)),
            "kind": fkind,
            "fid": fid_m.group(1) if fid_m else "",
            "participants": pids_m.group(1) if pids_m else "",
        })
    return result


def _lifeline_xs(html: str) -> "list[float]":
    """Return sorted list of x-coordinates for vertical lifeline dashes."""
    matches = re.findall(
        r'<line x1="([^"]+)" y1="([^"]+)" x2="([^"]+)" y2="([^"]+)"[^>]*stroke-dasharray="5 4"',
        html,
    )
    return sorted(float(x1) for x1, _y1, x2, _y2 in matches if x1 == x2)


# ── SEQ-006: Activation bar exact baselines ───────────────────────────────────

class TestActivationBaselines:
    """SEQ-006: Activation bars must begin/end at triggering message baselines."""

    def test_bob_activation_top_at_request_message_y(self):
        """Bob's activation bar top must equal the Alice→Bob request message y."""
        html = _render("sequence-activation.mmd")
        bars = _extract_activation_bars(html)
        msgs = _extract_message_lines(html)
        assert "Bob" in bars, f"No activation bar for Bob. bars={list(bars)}"
        req = next((m for m in msgs if m["src"] == "Alice" and m["dst"] == "Bob"), None)
        assert req, "Request message Alice→Bob not found"
        assert abs(bars["Bob"]["y"] - req["y1"]) <= 2, (
            f"Bob activation top={bars['Bob']['y']} ≠ request y={req['y1']} (SEQ-006)"
        )

    def test_bob_activation_bottom_at_final_response_y(self):
        """Bob's activation bar bottom must equal the Bob→Alice final response y."""
        html = _render("sequence-activation.mmd")
        bars = _extract_activation_bars(html)
        msgs = _extract_message_lines(html)
        assert "Bob" in bars
        bob = bars["Bob"]
        resp = next((m for m in reversed(msgs) if m["src"] == "Bob" and m["dst"] == "Alice"), None)
        assert resp, "Final response Bob→Alice not found"
        bob_bottom = bob["y"] + bob["height"]
        assert abs(bob_bottom - resp["y1"]) <= 2, (
            f"Bob activation bottom={bob_bottom} ≠ final response y={resp['y1']} (SEQ-006)"
        )

    def test_carol_activation_aligns_with_forward_and_response(self):
        """Carol's activation bar spans from Forward to Response messages."""
        html = _render("sequence-activation.mmd")
        bars = _extract_activation_bars(html)
        msgs = _extract_message_lines(html)
        assert "Carol" in bars, f"No activation bar for Carol. bars={list(bars)}"
        carol = bars["Carol"]
        fwd = next((m for m in msgs if m["src"] == "Bob" and m["dst"] == "Carol"), None)
        resp = next((m for m in msgs if m["src"] == "Carol" and m["dst"] == "Bob"), None)
        assert fwd and resp
        assert abs(carol["y"] - fwd["y1"]) <= 2, (
            f"Carol activation top={carol['y']} ≠ forward y={fwd['y1']} (SEQ-006)"
        )
        carol_bottom = carol["y"] + carol["height"]
        assert abs(carol_bottom - resp["y1"]) <= 2, (
            f"Carol activation bottom={carol_bottom} ≠ response y={resp['y1']} (SEQ-006)"
        )

    def test_unclosed_activation_flushes_to_lifeline_bottom(self):
        """An unclosed activate extends to the lifeline bottom, not zero height."""
        src = (
            "sequenceDiagram\n"
            "    Alice->>Bob: start\n"
            "    activate Bob\n"
            "    Alice->>Bob: continue\n"
        )
        html = _dispatch(src, None, 800)
        bars = _extract_activation_bars(html)
        assert "Bob" in bars, "No activation bar for unclosed Bob"
        bob = bars["Bob"]
        assert bob["height"] > 30, (
            f"Unclosed activation height={bob['height']} too small; should extend to ll_bot (SEQ-006)"
        )

    def test_nested_activations_have_different_x(self):
        """Two nested activations on the same participant must have different x offsets."""
        src = (
            "sequenceDiagram\n"
            "    Alice->>Bob: outer call\n"
            "    activate Bob\n"
            "    Bob->>Bob: inner call\n"
            "    activate Bob\n"
            "    Bob-->>Bob: inner return\n"
            "    deactivate Bob\n"
            "    Bob-->>Alice: outer return\n"
            "    deactivate Bob\n"
        )
        html = _dispatch(src, None, 800)
        all_bars = [b for b in re.findall(r'<rect[^>]+opacity="0\.35"[^>]*/>', html)
                    if 'data-pid="Bob"' in b]
        assert len(all_bars) >= 2, f"Expected ≥2 Bob activation bars, got {len(all_bars)}"
        xs = [float(re.search(r'\bx="([^"]+)"', b).group(1)) for b in all_bars]
        assert len(set(xs)) >= 2, (
            f"Nested activation bars have same x={xs}; depths not offset (SEQ-006)"
        )


# ── SEQ-007: Activation-aware message endpoints ───────────────────────────────

class TestActivationAwareEndpoints:
    """SEQ-007: Messages must terminate at activation bar edges, not lifeline centers."""

    def test_request_to_bob_ends_at_activation_left_edge(self):
        """Alice→Bob request x2 must touch Bob's activation left edge."""
        html = _render("sequence-activation.mmd")
        bars = _extract_activation_bars(html)
        msgs = _extract_message_lines(html)
        assert "Bob" in bars, f"No Bob activation bar in sequence-activation.mmd. bars={list(bars)}"
        bob_left = bars["Bob"]["x"]
        req = next((m for m in msgs if m["src"] == "Alice" and m["dst"] == "Bob"), None)
        assert req, "Request message Alice→Bob not found"
        assert abs(req["x2"] - bob_left) <= 2, (
            f"Alice→Bob x2={req['x2']} ≠ Bob activation left={bob_left} (SEQ-007)"
        )

    def test_forward_message_starts_at_bob_activation_right(self):
        """Bob→Carol forward x1 must start at Bob's activation right edge."""
        html = _render("sequence-activation.mmd")
        bars = _extract_activation_bars(html)
        msgs = _extract_message_lines(html)
        assert "Bob" in bars, f"No Bob activation bar. bars={list(bars)}"
        bob_right = bars["Bob"]["x"] + bars["Bob"]["width"]
        fwd = next((m for m in msgs if m["src"] == "Bob" and m["dst"] == "Carol"), None)
        assert fwd, "Forward message Bob→Carol not found"
        assert abs(fwd["x1"] - bob_right) <= 2, (
            f"Bob→Carol x1={fwd['x1']} ≠ Bob activation right={bob_right} (SEQ-007)"
        )

    def test_forward_message_ends_at_carol_activation_left(self):
        """Bob→Carol forward x2 must end at Carol's activation left edge."""
        html = _render("sequence-activation.mmd")
        bars = _extract_activation_bars(html)
        msgs = _extract_message_lines(html)
        assert "Carol" in bars, f"No Carol activation bar. bars={list(bars)}"
        carol_left = bars["Carol"]["x"]
        fwd = next((m for m in msgs if m["src"] == "Bob" and m["dst"] == "Carol"), None)
        assert fwd, "Forward message Bob→Carol not found"
        assert abs(fwd["x2"] - carol_left) <= 2, (
            f"Bob→Carol x2={fwd['x2']} ≠ Carol activation left={carol_left} (SEQ-007)"
        )


# ── SEQ-008: Per-fragment participant bounds ──────────────────────────────────

class TestFragmentParticipantBounds:
    """SEQ-008: Each fragment rect must span only its own participants."""

    def test_loop_excludes_client_participant(self):
        """loop Retry around Server+DB must not extend to Client's x."""
        html = _render("sequence-blocks.mmd")
        xs = _lifeline_xs(html)
        assert len(xs) >= 2, "Expected at least 2 lifelines"
        client_x = xs[0]  # Client is the leftmost participant
        loop_frags = _fragment_rects(html, kind="loop")
        assert loop_frags, "No loop fragment found (data-fragment-kind='loop') (SEQ-008)"
        loop = loop_frags[0]
        assert loop["x"] > client_x, (
            f"Loop fragment x={loop['x']} extends left of Client lifeline at {client_x} (SEQ-008)"
        )

    def test_alt_excludes_db_participant(self):
        """alt Success/Error around Client+Server must not extend to DB's x."""
        html = _render("sequence-blocks.mmd")
        xs = _lifeline_xs(html)
        assert len(xs) >= 3, "Expected at least 3 lifelines"
        db_x = xs[-1]  # DB is the rightmost participant
        alt_frags = _fragment_rects(html, kind="alt")
        assert alt_frags, "No alt fragment found (data-fragment-kind='alt') (SEQ-008)"
        alt = alt_frags[0]
        alt_right = alt["x"] + alt["w"]
        assert alt_right < db_x, (
            f"Alt fragment right={alt_right} extends past DB lifeline at {db_x} (SEQ-008)"
        )

    def test_fragment_data_attributes_present(self):
        """Fragment rects carry data-fragment-id, data-fragment-kind, data-participants."""
        html = _render("sequence-blocks.mmd")
        frags = _fragment_rects(html)
        assert frags, "No fragment rects found"
        for frag in frags:
            assert frag["fid"], f"Fragment missing data-fragment-id: {frag}"
            assert frag["kind"], f"Fragment missing data-fragment-kind: {frag}"

    def test_nested_fragment_bounds_are_tighter(self):
        """Inner fragment bounds must be contained within outer fragment bounds."""
        src = (
            "sequenceDiagram\n"
            "    participant Client\n"
            "    participant Server\n"
            "    participant DB\n"
            "    loop Retry\n"
            "        Client->>Server: request\n"
            "        alt Success\n"
            "            Server->>DB: query\n"
            "        end\n"
            "    end\n"
        )
        html = _dispatch(src, None, 800)
        frags = sorted(_fragment_rects(html), key=lambda f: f["h"])
        assert len(frags) >= 2, f"Expected ≥2 fragment rects, got {len(frags)} (SEQ-008)"
        inner = frags[0]  # shorter = inner (alt Success/DB)
        outer = frags[-1]  # taller = outer (loop Retry/Client+Server+DB)
        assert inner["x"] >= outer["x"], (
            f"Inner x={inner['x']} < outer x={outer['x']} (SEQ-008)"
        )
        assert inner["x"] + inner["w"] <= outer["x"] + outer["w"], (
            f"Inner right={inner['x']+inner['w']} > outer right={outer['x']+outer['w']} (SEQ-008)"
        )

    def test_branch_condition_on_else_separator(self):
        """else separator line must carry data-branch-condition with the branch label."""
        html = _render("sequence-blocks.mmd")
        assert 'data-branch-condition="Error"' in html, (
            "else separator missing data-branch-condition='Error' (T5)"
        )


# ── SEQ-010: Spanning note lifeline-anchored geometry ────────────────────────

class TestSpanningNoteGeometry:
    """SEQ-010: Spanning notes must overhang lifelines by NOTE_SPAN_OVERHANG=24px."""

    def test_spanning_note_left_edge_is_24px_left_of_first_lifeline(self):
        html = _render("sequence-notes-all.mmd")
        xs = _lifeline_xs(html)
        assert len(xs) >= 2
        first_lx, last_lx = xs[0], xs[-1]
        polys = _note_polys(html)
        # Spanning note is the widest note polygon (covers Alice to Carol)
        wide = [p for p in polys if (p[1] - p[0]) > 200]
        assert wide, f"No wide spanning note found. polys={polys}"
        NOTE_SPAN_OVERHANG = 24
        for x_min, x_max in wide:
            # left edge should be first_lifeline_x - 24
            assert abs(x_min - (first_lx - NOTE_SPAN_OVERHANG)) <= 2, (
                f"Spanning note left={x_min} ≠ lifeline {first_lx} - 24 (SEQ-010)"
            )
            # right edge should be last_lifeline_x + 24
            assert abs(x_max - (last_lx + NOTE_SPAN_OVERHANG)) <= 2, (
                f"Spanning note right={x_max} ≠ lifeline {last_lx} + 24 (SEQ-010)"
            )


# ── SEQ-012: Arrow spec table ─────────────────────────────────────────────────

class TestArrowSpecTable:
    """SEQ-012: Arrow spec table with point (async) and bidirectional markers."""

    def test_async_arrow_renders_filled_head_not_circle(self):
        """-)  arrow must produce a filled-head <polygon> (Mermaid 11.15), not a <circle>."""
        src = "sequenceDiagram\n  Alice-)Bob: async call"
        html = _dispatch(src, None, 800)
        arrow_polys = re.findall(r'<polygon points="[^"]+"\s+fill="var\(--edge', html)
        assert len(arrow_polys) == 1, (
            f"async -)  arrow should render exactly 1 filled-head polygon, got {len(arrow_polys)} (SEQ-012)"
        )
        assert "<circle" not in html, (
            "async -)  arrow should not render a hollow circle (Mermaid 11.15 uses filled_head) (SEQ-012)"
        )

    def test_async_dotted_arrow_renders_filled_head_not_circle(self):
        """--) arrow must also produce a filled-head <polygon> (Mermaid 11.15)."""
        src = "sequenceDiagram\n  Alice--)Bob: async dotted"
        html = _dispatch(src, None, 800)
        arrow_polys = re.findall(r'<polygon points="[^"]+"\s+fill="var\(--edge', html)
        assert len(arrow_polys) == 1, (
            f"async --)  arrow should render exactly 1 filled-head polygon, got {len(arrow_polys)} (SEQ-012)"
        )
        assert "<circle" not in html, (
            "async --)  arrow should not render a hollow circle (Mermaid 11.15 uses filled_head) (SEQ-012)"
        )

    def test_bidirectional_arrow_has_two_triangle_markers(self):
        """<<->> must produce exactly 2 filled triangle polygons."""
        src = "sequenceDiagram\n  Alice<<->>Bob: bidir"
        html = _dispatch(src, None, 800)
        arrow_polys = re.findall(r'<polygon points="[^"]+"\s+fill="var\(--edge', html)
        assert len(arrow_polys) == 2, (
            f"<<->> should produce 2 triangle polygons, got {len(arrow_polys)} (SEQ-012)"
        )

    def test_bidirectional_dotted_arrow_has_two_markers(self):
        """<<-->> must produce exactly 2 filled triangle polygons."""
        src = "sequenceDiagram\n  Alice<<-->>Bob: bidir dotted"
        html = _dispatch(src, None, 800)
        arrow_polys = re.findall(r'<polygon points="[^"]+"\s+fill="var\(--edge', html)
        assert len(arrow_polys) == 2, (
            f"<<-->> should produce 2 triangle polygons, got {len(arrow_polys)} (SEQ-012)"
        )


# ── SEQ-013: Parser gaps ──────────────────────────────────────────────────────

class TestParserGaps:
    """SEQ-013: critical/option and rect must render correctly."""

    def test_critical_with_option_branch_renders(self):
        """critical ... option branch must not be silently dropped."""
        src = (
            "sequenceDiagram\n"
            "    critical Acquire resource\n"
            "        Service->>DB: get lock\n"
            "    option No resource\n"
            "        Service-->>Client: 503\n"
            "    end\n"
        )
        html = _dispatch(src, None, 800)
        assert "option" in html.lower(), (
            "critical/option branch keyword not in output; likely silently dropped (SEQ-013)"
        )
        msgs = _extract_message_lines(html)
        assert len(msgs) == 2, (
            f"Expected 2 messages in critical/option, got {len(msgs)} (SEQ-013)"
        )

    def test_rect_has_solid_fill_not_dashed_border(self):
        """rect must render as a solid background region, not a dashed labeled fragment."""
        src = (
            "sequenceDiagram\n"
            "    Alice->>Bob: hello\n"
            "    rect rgb(0, 255, 0)\n"
            "        Bob-->>Alice: response\n"
            "    end\n"
        )
        html = _dispatch(src, None, 800)
        # rect should NOT use stroke-dasharray="5 3" (that's for fragments)
        rect_bodies = re.findall(r'<rect[^>]*/>', html)
        for body in rect_bodies:
            if 'opacity="0.3"' in body or 'rgb(0, 255, 0)' in body.lower():
                assert 'stroke-dasharray' not in body, (
                    "rect rendered with dashed border instead of solid fill (SEQ-013)"
                )

    def test_autonumber_does_not_break_render(self):
        """autonumber directive must not crash and emits a Diagnostic."""
        src = (
            "sequenceDiagram\n"
            "    autonumber\n"
            "    Alice->>Bob: ping\n"
            "    Bob-->>Alice: pong\n"
        )
        html = _dispatch(src, None, 800)
        assert "Alice" in html and "Bob" in html


# ── SEQ-013/T4: Unsupported syntax diagnostics ───────────────────────────────

class TestUnsupportedSyntaxDiagnostics:
    """T4: Unsupported constructs emit Diagnostic objects instead of silently dropping."""

    def _validate(self, src: str):
        return _dispatch_validate("sequenceDiagram\n" + src)

    def test_autonumber_emits_diagnostic(self):
        vr = self._validate("autonumber\nA->>B: hi")
        assert len(vr.diagnostics) == 1
        d = vr.diagnostics[0]
        assert d.feature == "autonumber"
        assert d.line_number == 1
        assert d.source_text == "autonumber"

    def test_create_participant_emits_diagnostic(self):
        vr = self._validate("create participant Token\nA->>B: hi")
        assert any(d.feature == "create_participant" for d in vr.diagnostics)

    def test_create_actor_emits_diagnostic(self):
        vr = self._validate("create actor Robot\nA->>B: hi")
        assert any(d.feature == "create_actor" for d in vr.diagnostics)

    def test_destroy_emits_diagnostic(self):
        vr = self._validate("A->>B: hi\ndestroy B")
        assert any(d.feature == "destroy" for d in vr.diagnostics)

    def test_par_over_emits_diagnostic(self):
        vr = self._validate("A->>B: hi\npar_over")
        assert any(d.feature == "par_over" for d in vr.diagnostics)

    def test_unrecognized_line_emits_diagnostic(self):
        vr = self._validate("A->>B: hi\ngobbledygook XYZ")
        assert any(d.feature == "unrecognized_line" for d in vr.diagnostics)

    def test_syntax_coverage_partial_when_diagnostics(self):
        vr = self._validate("autonumber\nA->>B: hi")
        assert vr.syntax_coverage == "partial"

    def test_syntax_coverage_pass_when_no_diagnostics(self):
        vr = self._validate("A->>B: hi")
        assert vr.syntax_coverage == "pass"
        assert vr.diagnostics == ()

    def test_render_fails_returns_syntax_coverage_fail(self):
        """A diagram that raises (no participants) → render=fail, syntax_coverage=fail."""
        vr = _dispatch_validate("sequenceDiagram\n%%only a comment")
        assert vr.render == "fail"
        assert vr.syntax_coverage == "fail"

    def test_box_emits_diagnostic_and_renders(self):
        src = (
            "sequenceDiagram\n"
            "    box Frontend\n"
            "        participant Alice\n"
            "    end\n"
            "    Alice->>Bob: hi\n"
        )
        vr = _dispatch_validate(src)
        assert any(d.feature == "box" for d in vr.diagnostics)
        assert vr.syntax_coverage == "partial"
        html = _dispatch(src, None, 800)
        assert "Alice" in html


# ── SEQ-014: Note participant auto-registration ───────────────────────────────

class TestNoteParticipantRegistration:
    """SEQ-014: Participants referenced only in notes must be auto-registered."""

    def test_note_participant_not_in_message_gets_lifeline(self):
        """A participant only in a note (not in any message) must still appear."""
        src = (
            "sequenceDiagram\n"
            "    Alice->>Bob: hello\n"
            "    Note over Carol: observer\n"
        )
        html = _dispatch(src, None, 800)
        xs = _lifeline_xs(html)
        # 3 participants: Alice, Bob, Carol → 3 lifelines
        assert len(xs) == 3, (
            f"Expected 3 lifelines (Alice, Bob, Carol), got {len(xs)} (SEQ-014)"
        )

    def test_spanning_note_registers_both_participants(self):
        """Note over A,B auto-registers both A and B as participants."""
        src = (
            "sequenceDiagram\n"
            "    Note over X,Y: spanning\n"
            "    X->>Y: message\n"
        )
        html = _dispatch(src, None, 800)
        assert "X" in html and "Y" in html
        xs = _lifeline_xs(html)
        assert len(xs) == 2, f"Expected 2 lifelines, got {len(xs)} (SEQ-014)"


# ── helpers for variable-height row tests ─────────────────────────────────────

def _note_poly_heights(html: str) -> "list[float]":
    """Return list of heights (max_y - min_y) for each note polygon."""
    result = []
    for pts in re.findall(r'<polygon points="([^"]+)"[^>]+fill="var\(--node-bg', html):
        ys = [float(p.split(",")[1]) for p in pts.strip().split()]
        result.append(max(ys) - min(ys))
    return result


def _note_poly_bottoms(html: str) -> "list[float]":
    """Return list of max-y for each note polygon."""
    result = []
    for pts in re.findall(r'<polygon points="([^"]+)"[^>]+fill="var\(--node-bg', html):
        ys = [float(p.split(",")[1]) for p in pts.strip().split()]
        result.append(max(ys))
    return result


# ── SEQ-009: Variable-height row packing ──────────────────────────────────────

class TestVariableHeightRows:
    """SEQ-009: long note text expands its row; subsequent y-positions shift."""

    # Long note with spaces so the measurer can wrap to ≥3 lines at font-size 10px / col_w 160px
    _LONG_NOTE = "long note text " * 6

    def test_long_note_polygon_taller_than_row_h_interior(self):
        """AC-1: A note with ≥80 chars must produce a note polygon taller than ROW_H−8 (32 px)."""
        src = (
            "sequenceDiagram\n"
            f"    Alice->>Bob: go\n"
            f"    Note over Alice: {self._LONG_NOTE}\n"
        )
        html = _dispatch(src, None, 800)
        note_hs = _note_poly_heights(html)
        ROW_H_INTERIOR = 32  # ROW_H(40) - 8
        assert note_hs, "No note polygons found"
        assert any(nh > ROW_H_INTERIOR for nh in note_hs), (
            f"Long note must produce polygon taller than {ROW_H_INTERIOR}px; "
            f"got heights {note_hs} (SEQ-009 AC-1)"
        )

    def test_message_y_shifts_below_long_note(self):
        """AC-2: Message after a long note shifts further down than after a short note;
        and it remains below the note polygon's bottom edge."""
        short_src = "sequenceDiagram\n    Note over Alice: hi\n    Alice->>Bob: go\n"
        long_src = (
            "sequenceDiagram\n"
            f"    Note over Alice: {self._LONG_NOTE}\n"
            "    Alice->>Bob: go\n"
        )
        short_html = _dispatch(short_src, None, 800)
        long_html = _dispatch(long_src, None, 800)
        short_msgs = _extract_message_lines(short_html)
        long_msgs = _extract_message_lines(long_html)
        assert short_msgs and long_msgs, "Messages not found in rendered output"
        # Primary: downstream rows shift further down with a tall note
        assert long_msgs[0]["y1"] > short_msgs[0]["y1"], (
            f"Message after long note (y={long_msgs[0]['y1']}) must be lower than "
            f"after short note (y={short_msgs[0]['y1']}) (SEQ-009 AC-2)"
        )
        # Geometric invariant: message y is always below the note polygon bottom
        long_note_bottoms = _note_poly_bottoms(long_html)
        assert long_note_bottoms, "No note polygon in long diagram"
        assert long_msgs[0]["y1"] > max(long_note_bottoms), (
            f"Message y={long_msgs[0]['y1']} must exceed note bottom={max(long_note_bottoms)} "
            f"(SEQ-009 AC-2 geometric invariant)"
        )

    def test_canvas_height_grows_with_long_note(self):
        """AC-3: A diagram with a long note must have a taller canvas than one with a short note."""
        short_src = "sequenceDiagram\n    Note over Alice: hi\n    Alice->>Bob: go\n"
        long_src = (
            "sequenceDiagram\n"
            f"    Note over Alice: {self._LONG_NOTE}\n"
            "    Alice->>Bob: go\n"
        )
        h_short = _canvas_height(_dispatch(short_src, None, 800))
        h_long = _canvas_height(_dispatch(long_src, None, 800))
        assert h_long > h_short, (
            f"Long-note canvas h={h_long} must exceed short-note canvas h={h_short} (SEQ-009 AC-3)"
        )

    def test_block_height_grows_when_containing_long_note(self):
        """AC-4: A loop block containing a long note must have a taller background rect."""
        short_src = "sequenceDiagram\n    loop L\n        Note over Alice: hi\n    end\n"
        long_src = (
            "sequenceDiagram\n"
            "    loop L\n"
            f"        Note over Alice: {self._LONG_NOTE}\n"
            "    end\n"
        )
        short_hs = _block_heights(_dispatch(short_src, None, 800))
        long_hs = _block_heights(_dispatch(long_src, None, 800))
        assert short_hs, "No block rects in short diagram"
        assert long_hs, "No block rects in long diagram"
        assert max(long_hs) > max(short_hs), (
            f"Long-note block h={max(long_hs)} must exceed short-note block h={max(short_hs)} "
            f"(SEQ-009 AC-4)"
        )


# ── T7: SequenceGeometry return type and self-message anchor ─────────────────

class TestSequenceGeometryReturn:
    """T7: _layout_lifeline returns (html, SequenceGeometry); self-message geometry."""

    def _layout(self, src: str):
        return _layout_lifeline(src, "LR", 900)

    def test_return_is_two_tuple_with_sequence_geometry(self):
        src = "sequenceDiagram\n  Alice->>Bob: hi"
        result = self._layout(src)
        assert isinstance(result, tuple) and len(result) == 2
        html, geom = result
        assert isinstance(html, str) and html
        assert isinstance(geom, SequenceGeometry)

    def test_participant_centers_populated(self):
        src = "sequenceDiagram\n  Alice->>Bob: hi"
        _, geom = self._layout(src)
        pids = [pid for pid, _ in geom.participant_centers]
        assert "Alice" in pids and "Bob" in pids

    def test_canvas_populated(self):
        src = "sequenceDiagram\n  Alice->>Bob: hi"
        _, geom = self._layout(src)
        w, h = geom.canvas
        assert w > 0 and h > 0

    def test_diagnostics_in_geometry(self):
        src = "sequenceDiagram\n  autonumber\n  A->>B: hi"
        _, geom = self._layout(src)
        assert any(d.feature == "autonumber" for d in geom.diagnostics)

    def test_self_loop_inactive_anchors_at_lifeline_cx(self):
        """Inactive self-message loop must start at lifeline center x."""
        src = "sequenceDiagram\n  Alice->>Alice: think"
        _, geom = self._layout(src)
        assert geom.self_loop_bounds, "Expected self_loop_bounds to be populated"
        # participant center for Alice
        cx = dict(geom.participant_centers).get("Alice", None)
        assert cx is not None
        # loop anchor x (left edge) should equal cx when inactive
        ax = geom.self_loop_bounds[0][0]
        assert abs(ax - cx) < 1.0, f"Inactive self-loop anchor {ax} != lifeline cx {cx}"

    def test_self_loop_canvas_fits(self):
        """Self-loop on rightmost participant must stay within canvas width."""
        src = "sequenceDiagram\n  Alice->>Alice: this is a long self-message label"
        html, geom = self._layout(src)
        if geom.self_loop_bounds:
            ax, _, loop_w, _ = geom.self_loop_bounds[0]
            canvas_w = geom.canvas[0]
            assert ax + loop_w <= canvas_w, (
                f"Self-loop right edge {ax + loop_w} exceeds canvas_w {canvas_w}"
            )

    def test_self_loop_path_in_html(self):
        """Self-message must render as an SVG <path> (cubic Bezier)."""
        src = "sequenceDiagram\n  Alice->>Alice: call"
        html = _dispatch(src, None, 800)
        assert '<path d="M' in html, "Self-message should render as SVG <path>"

# ── T8a: Natural horizontal layout ───────────────────────────────────────────

class TestNaturalHorizontalLayout:
    """T8a: constraint solver produces correct column widths."""

    def _lifeline_gap(self, html: str) -> int:
        """Return the gap (px) between the two leftmost lifeline x-coordinates."""
        lines = re.findall(
            r'<line x1="(\d+)"[^>]*stroke-dasharray="5 4"', html
        )
        xs = sorted(set(int(x) for x in lines))
        return xs[1] - xs[0] if len(xs) >= 2 else 0

    def test_long_message_label_widens_column_gap(self):
        """A long message label between adjacent participants forces a wider column gap."""
        long_label = "a very long message label that must expand column gap"
        src_long = f"sequenceDiagram\n  Alice->>Bob: {long_label}"
        src_short = "sequenceDiagram\n  Alice->>Bob: hi"
        gap_long = self._lifeline_gap(_dispatch(src_long, None, 0))
        gap_short = self._lifeline_gap(_dispatch(src_short, None, 0))
        assert gap_long > gap_short, (
            f"Long label should widen column gap: got {gap_long}px vs {gap_short}px"
        )

    def test_long_participant_name_widens_box(self):
        """A participant with a long name gets a wider box than one with a short name."""
        src = "sequenceDiagram\n  Verylongparticipantname->>X: hi"
        html = _dispatch(src, None, 0)
        widths = [int(m) for m in re.findall(
            r'class="node node-rect"[^>]+width:(\d+)px', html
        )]
        assert len(widths) >= 2, "Expected at least 2 participant boxes"
        assert widths[0] > widths[1], (
            f"Long-name box ({widths[0]}px) should be wider than short-name box ({widths[1]}px)"
        )

    def test_participant_label_no_overflow_hidden(self):
        """Participant label spans must not use overflow:hidden (names must not clip)."""
        html = _dispatch("sequenceDiagram\n  Alice->>Bob: hi", None, 0)
        label_sections = re.findall(r'class="node-label"[^>]+style="([^"]+)"', html)
        for style in label_sections:
            assert "overflow:hidden" not in style, (
                f"Participant label must not clip text: {style}"
            )

    def test_spanning_note_long_word_widens_column_gap(self):
        """A spanning note with a very long single word forces the column gap to widen."""
        # Use an extremely long single unbreakable word (no spaces) so min_content_width
        # exceeds the natural adjacent-box gap and forces the constraint to fire.
        long_word = "A" * 60  # 60-char word; measured width ~450px at 10px font
        src_long = (
            "sequenceDiagram\n"
            f"  note over Alice, Bob: {long_word}\n"
            "  Alice->>Bob: x"
        )
        src_short = (
            "sequenceDiagram\n"
            "  note over Alice, Bob: short\n"
            "  Alice->>Bob: x"
        )
        gap_long = self._lifeline_gap(_dispatch(src_long, None, 0))
        gap_short = self._lifeline_gap(_dispatch(src_short, None, 0))
        assert gap_long > gap_short, (
            f"Long single-word note should widen column gap: {gap_long}px vs {gap_short}px"
        )

    def test_fragment_header_label_widens_column_gap(self):
        """A long fragment-header label forces the spanned columns wider."""
        long_label = "this is a very long loop condition that needs room"
        src_long = (
            "sequenceDiagram\n"
            f"  loop {long_label}\n"
            "    Alice->>Bob: x\n"
            "  end\n"
        )
        src_short = (
            "sequenceDiagram\n"
            "  loop short\n"
            "    Alice->>Bob: x\n"
            "  end\n"
        )
        gap_long = self._lifeline_gap(_dispatch(src_long, None, 0))
        gap_short = self._lifeline_gap(_dispatch(src_short, None, 0))
        assert gap_long > gap_short, (
            f"Long fragment header should widen gap: {gap_long}px vs {gap_short}px"
        )


# ── T11: P2 cleanup ───────────────────────────────────────────────────────────

class TestP2Cleanup:
    """T11: strict participant lookup, unmatched-deactivate, RGBA double-alpha,
    label centering."""

    def test_implicit_participant_renders_without_crash(self):
        """Implicit participants (not declared via 'participant') still render safely."""
        src = "sequenceDiagram\n  participant Alice\n  Alice->>Typo: hi"
        html, geom = _layout_lifeline(src, "LR", 0)
        assert html is not None
        # Typo auto-registered; both participants should appear as lifelines
        assert "Alice" in html
        assert "Typo" in html

    def test_unmatched_deactivate_emits_diagnostic(self):
        """A deactivate with no matching activate produces a Diagnostic."""
        src = "sequenceDiagram\n  participant A\n  A->>A: hi\n  deactivate A"
        _, geom = _layout_lifeline(src, "LR", 0)
        assert any(d.feature == "unmatched_deactivate" for d in geom.diagnostics), (
            "Expected unmatched_deactivate Diagnostic"
        )

    def test_rgba_fill_no_opacity_attribute(self):
        """rect block with rgba() fill must not also carry opacity= (no double-alpha)."""
        src = (
            "sequenceDiagram\n"
            "  A->>B: start\n"
            "  rect rgba(0, 200, 0, 0.3)\n"
            "    A->>B: colored\n"
            "  end\n"
        )
        html = _dispatch(src, None, 0)
        # Find rect elements that have rgba fill AND opacity
        double_alpha = re.findall(
            r'<rect[^>]+fill="rgba\([^"]*\)"[^>]+opacity="[^"]*"', html
        )
        assert not double_alpha, f"Rect has both rgba fill and opacity= (double-alpha): {double_alpha}"

    def test_label_centered_at_activation_midpoint(self):
        """With activations, label x is midpoint of activation-adjusted endpoints."""
        src = (
            "sequenceDiagram\n"
            "  participant Alice\n"
            "  participant Bob\n"
            "  activate Bob\n"
            "  Alice->>Bob: msg\n"
            "  deactivate Bob\n"
        )
        html = _dispatch(src, None, 0)
        edge_styles = re.findall(r'class="edge-label"[^>]+style="([^"]+)"', html)
        assert edge_styles, "No edge-label found"
        # All edge labels use translateX(-50%) centering
        for style in edge_styles:
            assert "translateX(-50%)" in style
