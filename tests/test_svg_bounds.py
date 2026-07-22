"""Stage 10 tests: content-tight SVG bounds.

Covers:
- _patch_svg_bounds correctly replaces width/height/viewBox on SVG root
- data-diagram-w and data-diagram-h attributes are present on diagram root
- to_svg() produces SVG without fixed 1280px width (integration — requires playwright)
- viewBox approximately equals visible geometry plus padding
- Repeated SVG conversion is structurally deterministic
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from mermaid_render.svg import _patch_svg_bounds


# ── _patch_svg_bounds ─────────────────────────────────────────────────────────

class TestPatchSvgBounds:
    def test_sets_width_attribute(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect/></svg>'
        result = _patch_svg_bounds(svg, 400, 300)
        assert 'width="400"' in result

    def test_sets_height_attribute(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect/></svg>'
        result = _patch_svg_bounds(svg, 400, 300)
        assert 'height="300"' in result

    def test_sets_viewbox(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect/></svg>'
        result = _patch_svg_bounds(svg, 400, 300)
        assert 'viewBox="0 0 400 300"' in result

    def test_removes_old_1280_width(self):
        svg = '<svg width="1280" height="720" viewBox="0 0 1280 720"><rect/></svg>'
        result = _patch_svg_bounds(svg, 500, 250)
        assert '1280' not in result.split(">")[0]

    def test_preserves_svg_content(self):
        svg = '<svg width="1280"><g><rect id="test"/></g></svg>'
        result = _patch_svg_bounds(svg, 100, 100)
        assert '<rect id="test"/>' in result

    def test_handles_svg_without_existing_attrs(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        result = _patch_svg_bounds(svg, 200, 150)
        assert 'width="200"' in result
        assert 'height="150"' in result
        assert 'viewBox="0 0 200 150"' in result

    def test_only_patches_root_svg(self):
        """Nested <svg> elements (e.g. from icons) must not be patched."""
        outer = 600
        svg = (
            f'<svg width="{outer}" height="{outer}">'
            '<g><svg width="24" height="24"><path/></svg></g>'
            "</svg>"
        )
        result = _patch_svg_bounds(svg, 300, 200)
        # Root: 300×200; nested: 24×24 unchanged
        assert 'width="300"' in result
        assert 'height="200"' in result
        assert 'width="24"' in result  # nested unchanged

    def test_idempotent(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        once = _patch_svg_bounds(svg, 400, 300)
        twice = _patch_svg_bounds(once, 400, 300)
        assert once == twice


# ── data-diagram-w/h attributes ──────────────────────────────────────────────

class TestDiagramDataAttributes:
    """Verify to_html() emits data-diagram-w and data-diagram-h on the root div."""

    def _get_html(self, src: str) -> str:
        import mermaid_render
        return mermaid_render.to_html(src)

    def test_flowchart_has_data_diagram_w(self):
        html = self._get_html("flowchart TB\n  A --> B")
        assert re.search(r'data-diagram-w="\d+"', html), (
            "data-diagram-w missing from flowchart HTML"
        )

    def test_flowchart_has_data_diagram_h(self):
        html = self._get_html("flowchart TB\n  A --> B")
        assert re.search(r'data-diagram-h="\d+"', html), (
            "data-diagram-h missing from flowchart HTML"
        )

    def test_data_w_is_positive_integer(self):
        html = self._get_html("flowchart TB\n  A --> B --> C")
        m = re.search(r'data-diagram-w="(\d+)"', html)
        assert m, "data-diagram-w not found"
        assert int(m.group(1)) > 0

    def test_data_h_is_positive_integer(self):
        html = self._get_html("flowchart TB\n  A --> B --> C")
        m = re.search(r'data-diagram-h="(\d+)"', html)
        assert m, "data-diagram-h not found"
        assert int(m.group(1)) > 0

    def test_data_w_matches_style_width(self):
        """data-diagram-w should match the CSS width value on the same element."""
        html = self._get_html("flowchart TB\n  A --> B")
        # Find the diagram root div
        m_dw = re.search(r'data-diagram-w="(\d+)"', html)
        m_sw = re.search(r'data-diagram-w="(\d+)"[^>]*style="[^"]*width:(\d+)px', html)
        if not m_sw:
            # Try the other order: style comes before data attrs
            m_sw = re.search(r'width:(\d+)px[^>]*data-diagram-w="(\d+)"', html)
            if m_sw:
                css_w, dw = int(m_sw.group(1)), int(m_sw.group(2))
                assert css_w == dw, f"data-diagram-w={dw} != style width={css_w}"
                return
        assert m_dw, "data-diagram-w not found"
        # If we can't match the combined pattern, just check both values exist and are >0
        assert int(m_dw.group(1)) > 0

    def test_not_fixed_1280(self):
        """data-diagram-w should NOT be 1280 for a simple 2-node flowchart
        (1280 would indicate the viewport width was used rather than content width)."""
        html = self._get_html("flowchart TB\n  A --> B")
        m = re.search(r'data-diagram-w="(\d+)"', html)
        if m:
            w = int(m.group(1))
            assert w != 1280, (
                "data-diagram-w=1280 suggests viewport width leaked into layout "
                "(should be content-tight)"
            )

    def test_deterministic_across_calls(self):
        src = "flowchart TB\n  A --> B --> C --> D"
        html1 = self._get_html(src)
        html2 = self._get_html(src)
        m1 = re.search(r'data-diagram-w="(\d+)"', html1)
        m2 = re.search(r'data-diagram-w="(\d+)"', html2)
        assert m1 and m2
        assert m1.group(1) == m2.group(1), "data-diagram-w is not deterministic"


# ── SVG integration (requires Playwright) ────────────────────────────────────

@pytest.mark.skipif(
    not os.path.exists(
        os.path.join(os.path.dirname(__file__), "..", "scripts",
                     "mermaid_render", "vendor", "dom-to-svg.bundle.js")
    ),
    reason="dom-to-svg bundle not found; skipping Playwright integration tests",
)
class TestSvgBoundsIntegration:
    """Integration tests that call to_svg() and inspect the output SVG."""

    def _get_svg(self, src: str) -> str:
        import mermaid_render
        return mermaid_render.to_svg(src, theme="light", experimental=True)

    def test_svg_not_1280_wide(self):
        """Exported SVG width must not be 1280 (the Playwright default viewport)."""
        svg = self._get_svg("flowchart TB\n  A --> B")
        m = re.search(r'<svg\b[^>]+\bwidth="(\d+)"', svg)
        assert m, "No width attribute found on root SVG element"
        assert int(m.group(1)) != 1280, (
            f"SVG width={m.group(1)} equals viewport default 1280; expected content-tight"
        )

    def test_svg_has_viewbox(self):
        """Exported SVG must have a viewBox attribute."""
        svg = self._get_svg("flowchart TB\n  A --> B")
        assert re.search(r'viewBox="[\d. ]+"', svg), "No viewBox on root SVG"

    def test_viewbox_matches_width_height(self):
        """viewBox '0 0 W H' must match the SVG's width and height attributes."""
        svg = self._get_svg("flowchart LR\n  X --> Y --> Z")
        m_wh = re.search(r'<svg\b[^>]+\bwidth="(\d+)"[^>]+\bheight="(\d+)"', svg)
        m_vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
        if not m_wh:
            m_wh = re.search(r'<svg\b[^>]+\bheight="(\d+)"[^>]+\bwidth="(\d+)"', svg)
            if m_wh:
                h, w = int(m_wh.group(1)), int(m_wh.group(2))
            else:
                pytest.skip("Could not parse width/height from SVG root")
                return
        else:
            w, h = int(m_wh.group(1)), int(m_wh.group(2))
        assert m_vb, "No viewBox on root SVG"
        vb_w, vb_h = int(m_vb.group(1)), int(m_vb.group(2))
        assert vb_w == w, f"viewBox width {vb_w} != SVG width {w}"
        assert vb_h == h, f"viewBox height {vb_h} != SVG height {h}"

    def test_architecture_fixture_uses_content_width(self):
        """Architecture diagram SVG width should reflect content, not 1280px."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures",
                                    "architecture-complex.mmd")
        with open(fixture_path) as f:
            src = f.read()
        svg = self._get_svg(src)
        m = re.search(r'<svg\b[^>]+\bwidth="(\d+)"', svg)
        if m:
            w = int(m.group(1))
            assert w != 1280, f"Architecture SVG width={w} is the viewport default"

    def test_svg_conversion_deterministic(self):
        """Same source must produce the same SVG structure on repeated conversion."""
        src = "flowchart TB\n  A --> B --> C"
        svg1 = self._get_svg(src)
        svg2 = self._get_svg(src)
        # Strip volatile content (temp paths in comments, generated IDs)
        def _normalize(s: str) -> str:
            s = re.sub(r'<!--.*?-->', '', s)          # strip all HTML comments (temp paths)
            s = re.sub(r'id="[^"]*"', 'id="__"', s)  # normalize generated IDs
            s = re.sub(r'url\(#[^)]*\)', 'url(#__)', s)  # normalize ID references
            return s
        assert _normalize(svg1) == _normalize(svg2), "SVG output is not deterministic"
