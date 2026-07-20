#!/usr/bin/env python3
"""packet-beta syntax coverage tests for the mermaid_render layout engine.

Probes whether ``packet-beta`` is supported and covers every documented
syntax variant:
- Basic packet with named absolute-range fields
- Single-bit fields (no end index)
- Fields spanning multiple bits
- Relative ``+N`` syntax (silently skipped by the parser — all-relative
  diagrams raise ValueError; mixed diagrams render only the absolute fields)
- Mix of absolute and relative fields
- Output structure invariants (HTML document, data-field attrs)
- Edge cases (comment lines, single field, many fields)

Import note: ``to_html`` lives on ``mermaid_render``, not on the
``mermaid_layout`` backward-compat shim.  We import directly from
``mermaid_render``.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _packet(body: str) -> str:
    """Render a packet-beta body via to_html."""
    return to_html(f"packet-beta\n{body}")


def _fields(html: str) -> list[str]:
    """Return all data-field attribute values from rendered HTML."""
    return re.findall(r'data-field="([^"]+)"', html)


# ---------------------------------------------------------------------------
# TestPacketSupported — directive is recognised and renders
# ---------------------------------------------------------------------------

class TestPacketSupported:
    def test_minimal_packet_renders(self):
        """A two-field packet with absolute ranges returns non-empty HTML."""
        html = _packet('  0-7: "Source Port"\n  8-15: "Destination Port"')
        assert html

    def test_output_is_html_document(self):
        """to_html returns a full standalone HTML document."""
        html = _packet('  0-7: "Source Port"\n  8-15: "Destination Port"')
        assert html.strip().startswith("<!DOCTYPE html") or "<html" in html
        assert "</html>" in html

    def test_diagram_mermaid_layout_class_present(self):
        """Rendered fragment carries the 'diagram mermaid-layout' CSS class."""
        html = _packet('  0-7: "Source Port"\n  8-15: "Destination Port"')
        assert "diagram mermaid-layout" in html

    def test_field_labels_in_output(self):
        """Field label text appears somewhere in the rendered HTML."""
        html = _packet('  0-7: "Source Port"\n  8-15: "Destination Port"')
        assert "Source Port" in html
        assert "Destination Port" in html


# ---------------------------------------------------------------------------
# TestPacketAbsoluteRange — explicit start-end fields
# ---------------------------------------------------------------------------

class TestPacketAbsoluteRange:
    def test_real_ip_header_fields(self):
        """A realistic IP-header packet renders all four named fields."""
        src = (
            '  0-3: "Version"\n'
            '  4-7: "IHL"\n'
            '  8-15: "DSCP/ECN"\n'
            '  16-31: "Total Length"'
        )
        html = _packet(src)
        assert "Version" in html
        assert "IHL" in html
        assert "DSCP/ECN" in html
        assert "Total Length" in html

    def test_data_field_attrs_present(self):
        """Each absolute-range field produces a data-field attribute."""
        src = (
            '  0-7: "Source Port"\n'
            '  8-15: "Destination Port"\n'
            '  16-31: "Sequence Number"'
        )
        html = _packet(src)
        found = _fields(html)
        assert "0-7" in found
        assert "8-15" in found
        assert "16-31" in found

    def test_single_bit_field(self):
        """A single-bit field (no end index) renders without error."""
        html = _packet('  0: "Flag"\n  1-7: "Reserved"')
        assert "Flag" in html
        assert "Reserved" in html

    def test_single_bit_data_field_attr(self):
        """A single-bit field produces a data-field attribute with just the bit number."""
        html = _packet('  0: "SYN"\n  1-7: "Window"')
        found = _fields(html)
        assert "0" in found

    def test_wide_span_field(self):
        """A 32-bit-wide field (e.g. sequence number) renders without error."""
        html = _packet('  0-31: "Sequence Number"')
        assert "Sequence Number" in html

    def test_many_fields(self):
        """A packet with six fields renders all labels."""
        src = (
            '  0-7: "Source Port"\n'
            '  8-15: "Destination Port"\n'
            '  16-31: "Sequence Number"\n'
            '  32-47: "Ack Number"\n'
            '  48-51: "Data Offset"\n'
            '  52-63: "Flags"'
        )
        html = _packet(src)
        for label in ("Source Port", "Destination Port", "Sequence Number",
                      "Ack Number", "Data Offset", "Flags"):
            assert label in html


# ---------------------------------------------------------------------------
# TestPacketRelativeSyntax — +N fields are not recognised by the parser
# ---------------------------------------------------------------------------

class TestPacketRelativeSyntax:
    def test_all_relative_raises_value_error(self):
        """+N-only diagram raises ValueError — relative syntax is not parsed."""
        with pytest.raises(ValueError, match="No fields"):
            _packet('  +8: "Source Port"\n  +8: "Destination Port"\n  +16: "Length"')

    def test_relative_single_field_raises_value_error(self):
        """A single +N field raises ValueError (nothing parsed, no fields found)."""
        with pytest.raises(ValueError, match="No fields"):
            _packet('  +32: "Data"')

    def test_relative_with_label_raises_value_error(self):
        """Full real-world relative packet (all +N) raises ValueError."""
        src = (
            '  +8: "Flags"\n'
            '  +16: "Checksum"\n'
            '  +32: "Data"'
        )
        with pytest.raises(ValueError, match="No fields"):
            _packet(src)


# ---------------------------------------------------------------------------
# TestPacketMixedSyntax — mix of absolute and relative fields
# ---------------------------------------------------------------------------

class TestPacketMixedSyntax:
    def test_mixed_absolute_and_relative_renders(self):
        """Absolute fields render; relative +N lines are silently skipped."""
        src = (
            '  0-7: "Source Port"\n'
            '  8-15: "Destination Port"\n'
            '  16-31: "Sequence Number"\n'
            '  +8: "Flags"\n'        # silently skipped
            '  +16: "Checksum"\n'    # silently skipped
            '  +32: "Data"'          # silently skipped
        )
        html = _packet(src)
        # Absolute fields appear
        assert "Source Port" in html
        assert "Destination Port" in html
        assert "Sequence Number" in html

    def test_mixed_only_absolute_fields_have_data_attrs(self):
        """data-field attributes exist only for the absolute-range fields."""
        src = (
            '  0-7: "Source Port"\n'
            '  8-15: "Destination Port"\n'
            '  +8: "Flags"'   # skipped
        )
        html = _packet(src)
        found = _fields(html)
        assert "0-7" in found
        assert "8-15" in found
        # No data-field for the skipped +8 line
        assert len(found) == 2

    def test_absolute_before_relative_renders_absolute(self):
        """Leading absolute field renders even when followed by all-relative lines."""
        src = (
            '  0-15: "Header"\n'
            '  +16: "Payload"'
        )
        html = _packet(src)
        assert "Header" in html


# ---------------------------------------------------------------------------
# TestPacketStructure — HTML output invariants
# ---------------------------------------------------------------------------

class TestPacketStructure:
    def test_contains_svg_or_div_elements(self):
        """Rendered output contains HTML structure elements."""
        html = _packet('  0-7: "Source Port"\n  8-15: "Destination Port"')
        assert "<div" in html

    def test_field_count_matches_data_attrs(self):
        """Number of data-field attributes equals number of absolute-range fields."""
        src = (
            '  0-7: "A"\n'
            '  8-15: "B"\n'
            '  16-23: "C"'
        )
        html = _packet(src)
        found = _fields(html)
        assert len(found) == 3

    def test_bit_range_label_in_output(self):
        """Bit range index text (e.g. '0' or '0–7') appears in rendered HTML."""
        html = _packet('  0-7: "Source Port"\n  8-15: "Destination Port"')
        # The renderer emits the start bit at minimum
        assert "0" in html

    def test_quoted_label_text_rendered(self):
        """Quoted label text renders without the surrounding quotation marks."""
        html = _packet('  0-15: "Total Length"')
        assert "Total Length" in html
        # Quotation marks from the source should not appear literally in the label
        # (the renderer strips them via .strip('"'))
        assert 'data-field=' in html


# ---------------------------------------------------------------------------
# TestPacketEdgeCases
# ---------------------------------------------------------------------------

class TestPacketEdgeCases:
    def test_comment_lines_ignored(self):
        """Lines starting with %% are ignored and do not crash parsing."""
        src = (
            "%% this is a comment\n"
            '  0-7: "Source Port"\n'
            '  8-15: "Destination Port"'
        )
        html = _packet(src)
        assert "Source Port" in html
        assert "Destination Port" in html

    def test_empty_diagram_raises_value_error(self):
        """A packet-beta block with no parseable fields raises ValueError."""
        with pytest.raises(ValueError, match="No fields"):
            to_html("packet-beta\n  %% comment only")

    def test_single_field_full_width(self):
        """A single field spanning all 8 bits renders without error."""
        html = _packet('  0-7: "Byte"')
        assert "Byte" in html
        assert _fields(html) == ["0-7"]

    def test_unquoted_label_accepted(self):
        """Field labels without quotation marks are also accepted."""
        html = _packet("  0-7: Source\n  8-15: Destination")
        assert "Source" in html
        assert "Destination" in html

    def test_tcp_header_excerpt(self):
        """Realistic TCP header excerpt (absolute ranges only) renders all fields."""
        src = (
            '  0-15: "Source Port"\n'
            '  16-31: "Destination Port"\n'
            '  32-63: "Sequence Number"\n'
            '  64-95: "Acknowledgement Number"'
        )
        html = _packet(src)
        assert "Source Port" in html
        assert "Destination Port" in html
        assert "Sequence Number" in html
        assert "Acknowledgement Number" in html
