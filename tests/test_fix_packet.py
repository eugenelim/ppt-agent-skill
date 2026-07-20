#!/usr/bin/env python3
"""Regression tests for the packet-beta renderer fixes.

Covers:
  - Bit ruler row with tick marks (data-pkt-ruler attribute)
  - Row wrapping: packets wider than 32 bits produce multiple rows
  - Relative +N field syntax resolves to absolute bit positions
  - Proportional field widths (wider fields are physically wider)
  - Correct data-field identifiers preserved from original code
  - Error cases (invalid range, zero relative width, no fields)
  - Fixtures: packet-basic, packet-wrap, packet-relative
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _layout_packet


def _render(src: str, width: int = 640) -> str:
    return _layout_packet(src, "LR", width)


# ── Bit ruler ─────────────────────────────────────────────────────────────────

class TestBitRuler:
    """A ruler strip (data-pkt-ruler) appears above every field row."""

    def test_ruler_attribute_present_single_row(self):
        html = _render("packet-beta\n  0-7: A\n  8-15: B")
        assert "data-pkt-ruler" in html

    def test_ruler_index_zero_present(self):
        html = _render("packet-beta\n  0-31: Header")
        assert 'data-pkt-ruler="0"' in html

    def test_ruler_shows_bit_zero(self):
        html = _render("packet-beta\n  0-31: Header")
        assert ">0<" in html

    def test_ruler_shows_bit_8(self):
        html = _render("packet-beta\n  0-31: Header")
        assert ">8<" in html

    def test_ruler_shows_bit_16(self):
        html = _render("packet-beta\n  0-31: Header")
        assert ">16<" in html

    def test_ruler_shows_bit_24(self):
        html = _render("packet-beta\n  0-31: Header")
        assert ">24<" in html

    def test_ruler_shows_bit_31(self):
        # 31 is the last bit in a 32-bit row
        html = _render("packet-beta\n  0-31: Header")
        assert ">31<" in html

    def test_ruler_is_svg_element(self):
        html = _render("packet-beta\n  0-7: A")
        assert "<svg" in html and 'data-pkt-ruler="0"' in html


# ── Row wrapping ───────────────────────────────────────────────────────────────

class TestRowWrapping:
    """Fields exceeding 32 bits produce multiple ruler rows."""

    def test_single_row_for_exactly_32_bits(self):
        html = _render("packet-beta\n  0-15: A\n  16-31: B")
        rulers = re.findall(r'data-pkt-ruler="(\d+)"', html)
        assert len(rulers) == 1

    def test_two_rows_for_64_bits(self):
        html = _render("packet-beta\n  0-31: Row0\n  32-63: Row1")
        rulers = re.findall(r'data-pkt-ruler="(\d+)"', html)
        assert len(rulers) == 2

    def test_two_rows_for_partial_second_row(self):
        # Bits 0-31 fill row 0; bit 32 starts row 1
        src = (
            "packet-beta\n"
            "  0-7: A\n  8-15: B\n  16-23: C\n  24-31: D\n  32-39: E"
        )
        html = _render(src)
        rulers = re.findall(r'data-pkt-ruler="(\d+)"', html)
        assert len(rulers) == 2

    def test_three_rows_for_96_bits(self):
        html = _render("packet-beta\n  0-31: A\n  32-63: B\n  64-95: C")
        rulers = re.findall(r'data-pkt-ruler="(\d+)"', html)
        assert len(rulers) == 3

    def test_second_row_ruler_shows_bit_32(self):
        html = _render("packet-beta\n  0-31: Row0\n  32-63: Row1")
        assert ">32<" in html

    def test_second_row_ruler_shows_bit_40(self):
        html = _render("packet-beta\n  0-31: Row0\n  32-63: Row1")
        assert ">40<" in html

    def test_both_rows_have_fields(self):
        html = _render("packet-beta\n  0-31: Row0\n  32-63: Row1")
        assert 'data-field="0-31"' in html
        assert 'data-field="32-63"' in html

    def test_wrap_fixture_two_rows(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "packet-wrap.mmd").read_text()
        html = _render(src)
        rulers = re.findall(r'data-pkt-ruler="(\d+)"', html)
        assert len(rulers) == 2

    def test_wrap_fixture_all_fields_present(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "packet-wrap.mmd").read_text()
        html = _render(src)
        for fid in ("0-15", "16-31", "32-47", "48-63"):
            assert f'data-field="{fid}"' in html

    def test_field_spanning_boundary_appears_in_both_rows(self):
        # Field 24-39 crosses the 32-bit boundary
        html = _render("packet-beta\n  0-23: Before\n  24-39: Spanning\n  40-63: After")
        # Should appear in row 0 (vis bits 24-31) and row 1 (vis bits 32-39)
        count = html.count('data-field="24-39"')
        assert count == 2


# ── Relative +N syntax ─────────────────────────────────────────────────────────

class TestRelativeSyntax:
    """Relative +N field syntax resolves to absolute bit positions."""

    def test_single_relative_field_from_zero(self):
        html = _render("packet-beta\n  +8: Alpha")
        assert 'data-field="0-7"' in html

    def test_two_consecutive_relative_fields(self):
        html = _render("packet-beta\n  +8: Alpha\n  +8: Beta")
        assert 'data-field="0-7"' in html
        assert 'data-field="8-15"' in html

    def test_relative_after_absolute(self):
        html = _render("packet-beta\n  0-7: A\n  +8: B")
        assert 'data-field="0-7"' in html
        assert 'data-field="8-15"' in html

    def test_relative_16bit_field(self):
        html = _render("packet-beta\n  +16: Payload")
        assert 'data-field="0-15"' in html

    def test_relative_field_label_rendered(self):
        html = _render("packet-beta\n  +16: Payload")
        assert "Payload" in html

    def test_relative_fields_produce_ruler(self):
        html = _render("packet-beta\n  +8: A")
        assert "data-pkt-ruler" in html

    def test_relative_zero_bits_raises(self):
        with pytest.raises(ValueError, match="relative width"):
            _render("packet-beta\n  +0: Bad")

    def test_relative_fixture_correct_fields(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "packet-relative.mmd").read_text()
        html = _render(src)
        assert 'data-field="0-7"' in html    # +8 → 0-7
        assert 'data-field="8-15"' in html   # +8 → 8-15
        assert 'data-field="16-31"' in html  # +16 → 16-31
        assert 'data-field="32-63"' in html  # +32 → 32-63


# ── Proportional field widths ─────────────────────────────────────────────────

class TestProportionalWidths:
    """A wider bit field occupies proportionally more horizontal space."""

    def test_16bit_wider_than_8bit(self):
        html = _render("packet-beta\n  0-7: Narrow\n  8-23: Wide", width=640)
        m_narrow = re.search(r'data-field="0-7"[^>]*?width:(\d+)px', html)
        m_wide = re.search(r'data-field="8-23"[^>]*?width:(\d+)px', html)
        assert m_narrow and m_wide
        assert int(m_wide.group(1)) > int(m_narrow.group(1))

    def test_16bit_is_twice_as_wide_as_8bit(self):
        html = _render("packet-beta\n  0-7: Narrow\n  8-23: Wide", width=640)
        m_narrow = re.search(r'data-field="0-7"[^>]*?width:(\d+)px', html)
        m_wide = re.search(r'data-field="8-23"[^>]*?width:(\d+)px', html)
        assert m_narrow and m_wide
        # Allow 1-pixel rounding tolerance
        assert abs(int(m_wide.group(1)) - 2 * int(m_narrow.group(1))) <= 2

    def test_equal_bit_fields_equal_widths(self):
        html = _render("packet-beta\n  0-7: A\n  8-15: B", width=640)
        m_a = re.search(r'data-field="0-7"[^>]*?width:(\d+)px', html)
        m_b = re.search(r'data-field="8-15"[^>]*?width:(\d+)px', html)
        assert m_a and m_b
        assert m_a.group(1) == m_b.group(1)

    def test_bit_unit_based_on_32_not_total_bits(self):
        # A 24-bit packet and a 32-bit packet should have the same bit scale
        html24 = _render("packet-beta\n  0-7: A\n  8-23: B", width=640)
        html32 = _render("packet-beta\n  0-7: A\n  8-23: B\n  24-31: C", width=640)
        m24 = re.search(r'data-field="0-7"[^>]*?width:(\d+)px', html24)
        m32 = re.search(r'data-field="0-7"[^>]*?width:(\d+)px', html32)
        assert m24 and m32
        # Same bit unit → same pixel width for 0-7 regardless of total packet size
        assert m24.group(1) == m32.group(1)


# ── Field cells ───────────────────────────────────────────────────────────────

class TestFieldCells:
    """Each field renders as a labelled node-rect cell with correct data-field."""

    def test_basic_fixture_all_fields_present(self):
        src = (REPO_ROOT / "tests" / "fixtures" / "packet-basic.mmd").read_text()
        html = _render(src)
        for fid in ("0-3", "4-7", "8-15", "16-23"):
            assert f'data-field="{fid}"' in html

    def test_field_labels_rendered(self):
        html = _render("packet-beta\n  0-7: Version\n  8-15: IHL")
        assert "Version" in html
        assert "IHL" in html

    def test_single_bit_field_data_attribute(self):
        html = _render("packet-beta\n  0: Flag")
        assert 'data-field="0"' in html

    def test_range_field_data_attribute(self):
        html = _render("packet-beta\n  0-7: Header\n  8-15: Payload")
        assert 'data-field="0-7"' in html
        assert 'data-field="8-15"' in html

    def test_field_has_node_rect_class(self):
        html = _render("packet-beta\n  0-7: Header")
        assert 'class="node node-rect"' in html

    def test_no_fields_raises(self):
        with pytest.raises(ValueError, match="No fields"):
            _render("packet-beta\n  %% comment only")

    def test_invalid_range_raises(self):
        with pytest.raises(ValueError, match="invalid bit range"):
            _render("packet-beta\n  8-4: Bad")

    def test_title_line_ignored(self):
        src = "packet-beta\n  title My Packet\n  0-7: Field"
        html = _render(src)
        assert 'data-field="0-7"' in html


# ── Canvas dimensions ─────────────────────────────────────────────────────────

class TestCanvasDimensions:
    """Canvas height grows with additional rows."""

    def test_two_row_canvas_taller_than_one_row(self):
        h1 = _render("packet-beta\n  0-31: OneRow")
        h2 = _render("packet-beta\n  0-31: Row0\n  32-63: Row1")
        m1 = re.search(r'height:(\d+)px', h1)
        m2 = re.search(r'height:(\d+)px', h2)
        assert m1 and m2
        assert int(m2.group(1)) > int(m1.group(1))
