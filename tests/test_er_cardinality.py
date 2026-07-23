#!/usr/bin/env python3
"""Tests for structured ER cardinality parsing.

Verifies that ``parse_er_cardinality`` decodes each source token pair from the
acceptance-criterion fixtures into the correct ``CardinalityEnd`` values:

    A ||--|| B   →  (ONE..ONE,   ONE..ONE)
    C ||--o{ D   →  (ONE..ONE,   ZERO..MANY)
    E }|--|| F   →  (ONE..MANY,  ONE..ONE)
    G |o--|{ H   →  (ZERO..ONE,  ONE..MANY)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout.er import parse_er_cardinality  # noqa: E402
from mermaid_render.layout._constants import (  # noqa: E402
    CardinalityEnd,
    Maximum,
    Minimum,
)

_ONE_ONE = CardinalityEnd(Minimum.ONE, Maximum.ONE)
_ZERO_MANY = CardinalityEnd(Minimum.ZERO, Maximum.MANY)
_ONE_MANY = CardinalityEnd(Minimum.ONE, Maximum.MANY)
_ZERO_ONE = CardinalityEnd(Minimum.ZERO, Maximum.ONE)


# ── Acceptance-criterion pairs ────────────────────────────────────────────────

class TestParseErCardinality:
    @pytest.mark.parametrize("card_str,expected_src,expected_dst", [
        # A ||--|| B: both ends ONE..ONE
        ("||--||", _ONE_ONE, _ONE_ONE),
        # C ||--o{ D: src ONE..ONE, dst ZERO..MANY
        ("||--o{", _ONE_ONE, _ZERO_MANY),
        # E }|--|| F: src ONE..MANY, dst ONE..ONE
        ("}|--||", _ONE_MANY, _ONE_ONE),
        # G |o--|{ H: src ZERO..ONE, dst ONE..MANY
        ("|o--|{", _ZERO_ONE, _ONE_MANY),
    ])
    def test_acceptance_criterion_pairs(self, card_str, expected_src, expected_dst):
        src_end, dst_end = parse_er_cardinality(card_str)
        assert src_end == expected_src, f"{card_str}: src expected {expected_src}, got {src_end}"
        assert dst_end == expected_dst, f"{card_str}: dst expected {expected_dst}, got {dst_end}"

    @pytest.mark.parametrize("card_str,expected_src,expected_dst", [
        # Additional combinations from the ecommerce fixture
        ("||--o{", _ONE_ONE, _ZERO_MANY),   # CUSTOMER ||--o{ ORDER
        ("||--|{", _ONE_ONE, _ONE_MANY),    # ORDER ||--|{ LINE_ITEM
        ("}|--||", _ONE_MANY, _ONE_ONE),   # LINE_ITEM }|--|| PRODUCT
    ])
    def test_ecommerce_fixture_pairs(self, card_str, expected_src, expected_dst):
        src_end, dst_end = parse_er_cardinality(card_str)
        assert src_end == expected_src
        assert dst_end == expected_dst

    @pytest.mark.parametrize("card_str,expected_src,expected_dst", [
        # All SRC token variants
        ("||--||", _ONE_ONE,   _ONE_ONE),
        ("|o--||", _ZERO_ONE,  _ONE_ONE),
        ("}|--||", _ONE_MANY,  _ONE_ONE),
        ("}o--||", _ZERO_MANY, _ONE_ONE),
        # All DST token variants
        ("||--||", _ONE_ONE,  _ONE_ONE),
        ("||--|o", _ONE_ONE,  _ZERO_ONE),
        ("||--|{", _ONE_ONE,  _ONE_MANY),
        ("||--o{", _ONE_ONE,  _ZERO_MANY),
        # Right-side o| token (zero or one, mirrored)
        ("||--o|", _ONE_ONE,  _ZERO_ONE),
    ])
    def test_all_documented_token_variants(self, card_str, expected_src, expected_dst):
        src_end, dst_end = parse_er_cardinality(card_str)
        assert src_end == expected_src
        assert dst_end == expected_dst

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_er_cardinality("??--??")

    def test_dotted_line_separator_accepted(self):
        """Non-identifying relationships use '..' as the line separator."""
        src_end, dst_end = parse_er_cardinality("}o..o{")
        assert src_end == _ZERO_MANY
        assert dst_end == _ZERO_MANY


# ── Structured end properties ─────────────────────────────────────────────────

class TestCardinalityEndProperties:
    def test_one_one_is_frozen(self):
        e = CardinalityEnd(Minimum.ONE, Maximum.ONE)
        with pytest.raises((AttributeError, TypeError)):
            e.minimum = Minimum.ZERO  # type: ignore[misc]

    def test_equality_by_value(self):
        a = CardinalityEnd(Minimum.ZERO, Maximum.MANY)
        b = CardinalityEnd(Minimum.ZERO, Maximum.MANY)
        assert a == b

    def test_hashable(self):
        s = {CardinalityEnd(Minimum.ONE, Maximum.ONE), CardinalityEnd(Minimum.ZERO, Maximum.MANY)}
        assert len(s) == 2

    def test_minimum_zero_many_fields(self):
        e = _ZERO_MANY
        assert e.minimum is Minimum.ZERO
        assert e.maximum is Maximum.MANY


# ── Integration: glyph types match token ──────────────────────────────────────

class TestGlyphTypesMatchToken:
    """Verify that the HTML renderer emits the right SVG elements per token."""

    def _render(self, card_src: str, card_dst: str) -> str:
        from mermaid_render.layout._strategies import _layout_er
        src = f"erDiagram\n    A {card_src}--{card_dst} B : rel\n"
        return _layout_er(src, "TB", 800)

    def test_one_one_produces_double_bar(self):
        html = self._render("||", "||")
        # ONE..ONE at each end: 2 bars each side = at least 4 SVG line elements
        assert html.count("<line ") >= 4
        assert "<circle " not in html

    def test_zero_many_produces_circle(self):
        html = self._render("||", "o{")
        assert "<circle " in html

    def test_one_many_no_circle(self):
        html = self._render("}|", "||")
        # ONE..MANY: crow's foot + bar, no circle
        assert "<circle " not in html
        assert "<line " in html

    def test_zero_one_produces_circle(self):
        html = self._render("|o", "||")
        assert "<circle " in html

    @pytest.mark.parametrize("card_src,card_dst", [
        ("||", "||"),
        ("|o", "o{"),
        ("}|", "||"),
        ("|o", "|{"),
    ])
    def test_acceptance_criterion_combos_render(self, card_src, card_dst):
        html = self._render(card_src, card_dst)
        assert "A" in html
        assert "B" in html
        assert "<line " in html
