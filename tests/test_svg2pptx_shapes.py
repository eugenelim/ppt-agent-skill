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
