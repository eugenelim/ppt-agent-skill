"""SVG basic-shape coverage for scripts/svg2pptx.py.

Import pattern mirrors tests/test_mermaid_layout.py: sys.path.insert so tests/
doesn't need a conftest.py. Drives SvgConverter.convert on in-memory probe SVGs
and asserts on the observable result (the stats counters and emitted shape XML).

Regression guard for the silently-dropped <polygon> arrowheads: the mermaid
renderer emits every arrowhead as a <polygon>, so a drop here loses all arrows
in the PPTX export.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lxml import etree
from pptx import Presentation

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import svg2pptx  # noqa: E402
from svg2pptx import SvgConverter  # noqa: E402

SVG_HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" '
            'viewBox="0 0 400 300">')


def _convert(svg_body: str, tmp_path: Path):
    """Write an SVG, convert it onto a fresh blank slide, return (stats, slide_xml)."""
    f = tmp_path / "probe.svg"
    f.write_text(f"{SVG_HEAD}{svg_body}</svg>")
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    conv = SvgConverter()
    conv.convert(f, slide)
    xml = etree.tostring(slide._element).decode()
    return conv.stats, xml


def test_all_four_basic_shapes_convert(tmp_path):
    """rect + path + polygon + polyline all become native shapes (was 2)."""
    stats, _ = _convert(
        '<rect x="10" y="10" width="80" height="40" fill="#333"/>'
        '<path d="M 200 100 L 192 96 L 192 104 Z" fill="#e00"/>'
        '<polygon points="300,100 292,96 292,104" fill="#0a0"/>'
        '<polyline points="20,200 120,200 120,260" fill="none" stroke="#00f" stroke-width="2"/>',
        tmp_path,
    )
    assert stats["shapes"] == 4, stats
    assert stats["errors"] == 0, stats


def test_polygon_preserves_fill(tmp_path):
    """A filled polygon carries its fill colour through to the shape XML."""
    _, xml = _convert('<polygon points="300,100 292,96 292,104" fill="#00AA00"/>', tmp_path)
    assert "00AA00" in xml.upper()


def test_polygon_is_closed(tmp_path):
    """polygon geometry must close (emits an a:close), unlike polyline."""
    _, xml = _convert('<polygon points="300,100 292,96 292,104" fill="#0a0"/>', tmp_path)
    assert "a:close" in xml


def test_polyline_is_open(tmp_path):
    """polyline must not emit a closing segment (no a:close in its geometry)."""
    _, xml = _convert(
        '<polyline points="20,200 120,200 120,260" fill="none" stroke="#00f" stroke-width="2"/>',
        tmp_path,
    )
    assert "a:close" not in xml


def test_arrowhead_polygon_converts(tmp_path):
    """The renderer's actual _arrowhead point-string converts (the real bug)."""
    from mermaid_layout._routing import _arrowhead
    pts = _arrowhead(300, 100, -1, 0)  # leftward tip, as LR edges emit
    stats, _ = _convert(f'<polygon points="{pts}" fill="#64748b"/>', tmp_path)
    assert stats["shapes"] == 1, stats


def test_unhandled_leaf_is_counted_not_swallowed(tmp_path):
    """An unknown leaf rendering element surfaces via the unhandled counter."""
    stats, _ = _convert('<foobar x="1" y="2"/>', tmp_path)
    assert stats.get("unhandled", 0) >= 1, stats
    assert stats["errors"] == 0, stats


def test_comment_nodes_are_not_counted_unhandled(tmp_path):
    """dom-to-svg emits XML comments (falsy tag) — they must not count as unhandled."""
    stats, _ = _convert(
        '<!-- a comment --><rect x="10" y="10" width="80" height="40" fill="#333"/>',
        tmp_path,
    )
    assert stats.get("unhandled", 0) == 0, stats
    assert stats["shapes"] == 1, stats


def test_metadata_leaves_are_exempt(tmp_path):
    """Non-rendering leaves (title/desc/metadata) do not count as unhandled."""
    stats, _ = _convert(
        '<title>t</title><desc>d</desc><rect x="10" y="10" width="80" height="40" fill="#333"/>',
        tmp_path,
    )
    assert stats.get("unhandled", 0) == 0, stats
    assert stats["shapes"] == 1, stats


# ── <marker> / marker-end resolution (edge arrowheads after renderer #55) ──────

# The renderer's arrow-normal marker, verbatim from mermaid_layout._renderer.
_MARKER = (
    '<defs><marker id="ah" viewBox="0 -4 9 8" refX="9" refY="0" markerWidth="9" '
    'markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">'
    '<polygon points="0,-4 9,0 0,4" fill="#334455"/></marker></defs>'
)


_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _offsets(xml):
    """Every shape's top-left (a:off) in px, back-converted from EMU."""
    from svg2pptx import EMU_PX
    root = etree.fromstring(xml.encode())
    return [(int(o.get("x")) / EMU_PX, int(o.get("y")) / EMU_PX)
            for o in root.iter(f"{_A}off")]


def _boxes(xml):
    """Every shape's (x, y, w, h) in px — pairs each a:off with its sibling a:ext."""
    from svg2pptx import EMU_PX
    root = etree.fromstring(xml.encode())
    out = []
    for xfrm in root.iter(f"{_A}xfrm"):
        off, ext = xfrm.find(f"{_A}off"), xfrm.find(f"{_A}ext")
        if off is not None and ext is not None:
            out.append((int(off.get("x")) / EMU_PX, int(off.get("y")) / EMU_PX,
                        int(ext.get("cx")) / EMU_PX, int(ext.get("cy")) / EMU_PX))
    return out


def _near(offs, x, y, tol=2):
    return any(abs(px - x) <= tol and abs(py - y) <= tol for px, py in offs)


def test_marker_end_adds_arrowhead_shape(tmp_path):
    """A path with marker-end draws the marker geometry as an extra shape."""
    without, _ = _convert(
        '<path d="M 100 100 L 100 300" stroke="#334455" stroke-width="2" fill="none"/>',
        tmp_path,
    )
    with_marker, _ = _convert(
        _MARKER + '<path d="M 100 100 L 100 300" stroke="#334455" stroke-width="2" '
        'fill="none" marker-end="url(#ah)"/>',
        tmp_path,
    )
    assert with_marker["shapes"] == without["shapes"] + 1, (without, with_marker)
    assert with_marker["errors"] == 0


def test_marker_end_oriented_at_endpoint(tmp_path):
    """orient=auto: a downward path puts the arrowhead just above its endpoint (100,300).

    Transform of the arrow-normal triangle rotated to point down gives a bbox of
    roughly x∈[96,104], y∈[291,300] — top-left ≈ (96, 291).
    """
    _, xml = _convert(
        _MARKER + '<path d="M 100 100 L 100 300" stroke="#334455" stroke-width="2" '
        'fill="none" marker-end="url(#ah)"/>',
        tmp_path,
    )
    assert _near(_offsets(xml), 96, 291), _offsets(xml)


def test_marker_orientation_differs_by_direction(tmp_path):
    """A rightward path orients the arrowhead differently from a downward one."""
    _, down = _convert(
        _MARKER + '<path d="M 100 100 L 100 300" fill="none" stroke="#334455" marker-end="url(#ah)"/>',
        tmp_path,
    )
    _, right = _convert(
        _MARKER + '<path d="M 100 100 L 300 100" fill="none" stroke="#334455" marker-end="url(#ah)"/>',
        tmp_path,
    )
    # Downward arrow tip at (100,300), top-left ≈ (96,291); rightward at (300,100) ≈ (291,96).
    assert _near(_offsets(down), 96, 291), _offsets(down)
    assert _near(_offsets(right), 291, 96), _offsets(right)


_START_MARKER = _MARKER.replace('id="ah"', 'id="ah2"').replace(
    'orient="auto"', 'orient="auto-start-reverse"')


def test_marker_start_auto_reverse(tmp_path):
    """auto-start-reverse flips a start marker to point back along the path.

    Downward path start (100,100): plain auto would point down (base above,
    top-left y≈91); reversed points up (base below, top-left ≈ (96,100)).
    """
    _, xml = _convert(
        _START_MARKER + '<path d="M 100 100 L 100 300" fill="none" stroke="#334455" '
        'marker-start="url(#ah2)"/>',
        tmp_path,
    )
    assert _near(_offsets(xml), 96, 100), _offsets(xml)


def test_marker_fixed_numeric_orient(tmp_path):
    """A numeric orient ignores the tangent and rotates by that many degrees."""
    fixed = _MARKER.replace('id="ah"', 'id="ah3"').replace('orient="auto"', 'orient="90"')
    _, xml = _convert(
        fixed + '<path d="M 100 100 L 300 100" fill="none" stroke="#334455" '
        'marker-end="url(#ah3)"/>',
        tmp_path,
    )
    # Rightward path (auto would give top-left ≈ (291,96)); fixed 90° gives ≈ (296,91).
    assert _near(_offsets(xml), 296, 91), _offsets(xml)


def test_marker_stroke_width_units_scale(tmp_path):
    """markerUnits=strokeWidth scales the arrowhead by the host stroke-width."""
    sw = (_MARKER.replace('id="ah"', 'id="ah4"')
          .replace('markerUnits="userSpaceOnUse"', 'markerUnits="strokeWidth"'))
    _, xml = _convert(
        sw + '<path d="M 100 100 L 100 300" fill="none" stroke="#334455" stroke-width="2" '
        'marker-end="url(#ah4)"/>',
        tmp_path,
    )
    # The base marker is 8×9 px; stroke-width 2 doubles it to ~16×18.
    arrow = [b for b in _boxes(xml) if abs(b[2] - 16) <= 2 and abs(b[3] - 18) <= 2]
    assert arrow, _boxes(xml)


def test_marker_path_child_renders(tmp_path):
    """A <path>-child marker (the renderer's arrow-open) exercises _transform_path_d."""
    open_marker = (
        '<defs><marker id="ao" viewBox="0 -4 9 8" refX="9" refY="0" markerWidth="9" '
        'markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">'
        '<path d="M 0,-4 L 9,0 L 0,4" fill="none" stroke="#e8924a" stroke-width="1.5"/>'
        '</marker></defs>'
    )
    stats, xml = _convert(
        open_marker + '<path d="M 100 100 L 100 300" fill="none" stroke="#e8924a" '
        'marker-end="url(#ao)"/>',
        tmp_path,
    )
    assert stats["shapes"] == 2, stats  # edge line + arrowhead
    assert _near(_offsets(xml), 96, 291), _offsets(xml)


def test_marker_on_relative_path_is_skipped(tmp_path):
    """A relative/H/V host path can't be paired safely, so the marker is skipped
    (base shape still converts, no crash)."""
    stats, _ = _convert(
        _MARKER + '<path d="M 100 100 h 50 v 50" fill="none" stroke="#334455" '
        'marker-end="url(#ah)"/>',
        tmp_path,
    )
    assert stats["shapes"] == 1, stats  # only the base path; marker safely skipped
    assert stats["errors"] == 0, stats


def test_orient_radians_units():
    """Unitless orient is degrees; grad is matched before its rad suffix."""
    import math
    f = SvgConverter._orient_radians
    assert f("90") == pytest.approx(math.pi / 2)      # unitless -> degrees
    assert f("90deg") == pytest.approx(math.pi / 2)
    assert f("1rad") == pytest.approx(1.0)
    assert f("200grad") == pytest.approx(math.pi)     # not mis-read as radians
    assert f("0.5turn") == pytest.approx(math.pi)
    assert f("junk") == 0.0


def test_marker_malformed_viewbox_no_crash(tmp_path):
    """A <4-number viewBox degrades gracefully instead of aborting the conversion."""
    bad = _MARKER.replace('viewBox="0 -4 9 8"', 'viewBox="0 -4 9"')
    stats, _ = _convert(
        bad + '<path d="M 100 100 L 100 300" fill="none" stroke="#334455" '
        'marker-end="url(#ah)"/>',
        tmp_path,
    )
    assert stats["errors"] == 0, stats
    assert stats["shapes"] >= 1, stats


def test_unreferenced_defs_marker_not_drawn(tmp_path):
    """A marker defined but never referenced produces no shape (defs is skipped)."""
    stats, _ = _convert(_MARKER, tmp_path)
    assert stats["shapes"] == 0, stats
    assert stats.get("unhandled", 0) == 0, stats


def test_marker_missing_ref_does_not_crash(tmp_path):
    """marker-end to a missing id: base shape still converts, no error."""
    stats, _ = _convert(
        '<path d="M 100 100 L 100 300" stroke="#334455" fill="none" marker-end="url(#nope)"/>',
        tmp_path,
    )
    assert stats["shapes"] == 1, stats
    assert stats["errors"] == 0, stats
