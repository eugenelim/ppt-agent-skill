#!/usr/bin/env python3
"""Sankey diagram (sankey-beta) syntax coverage tests.

Mermaid sankey-beta syntax reference
-------------------------------------
::

    sankey-beta
    source,target,value
    Electricity,Lighting,28.7
    Electricity,Heating,42.3
    Gas,Heating,60.0
    Nuclear,Electricity,92.9
    "Fuel, Oil",Heating,10.5
    "Fuel, Oil","Electricity Gen",0.9

Key syntax features:
- Keyword is ``sankey-beta`` (not ``sankey``).
- CSV format: three columns — ``source,target,value``.
- Values are numeric (integers or decimals).
- Sources/targets that contain commas must be double-quoted: ``"Fuel, Oil"``.
- Double-quote literal inside a quoted string uses ``""`` escaping.
- Optional ``%%{init: {...}}%%`` frontmatter configures ``linkColor``,
  ``nodeAlignment``, ``nodeWidth``, and ``nodePadding``.

Support status
--------------
``sankey-beta`` is **not supported** by the pure-Python renderer (AC-3.1).
``to_html`` raises ``ValueError`` with a "not supported" message.  Use mmdc
(mermaid-js CLI) for actual Sankey flow-band rendering.  These tests verify
that the unsupported path raises consistently across all valid sankey-beta
input shapes.

Import note: ``to_html`` lives in ``mermaid_render``, not the backward-compat
``mermaid_layout`` shim.  Import directly from ``mermaid_render``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_HEADER = "sankey-beta\nsource,target,value\n"


def _sankey(body: str) -> str:
    """Render a sankey-beta diagram with a CSV body via to_html."""
    return to_html(_HEADER + body)


# ---------------------------------------------------------------------------
# TestSankeyBetaSupport — sankey-beta is supported (no ValueError)
# ---------------------------------------------------------------------------

class TestSankeyBetaSupport:
    """sankey-beta raises ValueError (unsupported, AC-3.1)."""

    def test_raises_unsupported(self):
        """Minimal sankey-beta raises ValueError."""
        with pytest.raises(ValueError, match="not supported"):
            _sankey("A,B,10\n")

    def test_raises_for_basic_source(self):
        """sankey-beta with basic rows raises ValueError."""
        with pytest.raises(ValueError, match="not supported"):
            _sankey("Electricity,Lighting,28.7\n")

    def test_error_message_contains_directive(self):
        """ValueError message references the directive name."""
        with pytest.raises(ValueError) as exc_info:
            _sankey("A,B,10\n")
        assert "sankey" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# TestSankeyBetaBasic — basic 3-row CSV
# ---------------------------------------------------------------------------

class TestSankeyBetaBasic:
    """Basic three-row CSV — all raise ValueError (unsupported)."""

    _SRC = (
        "Electricity,Lighting,28.7\n"
        "Electricity,Heating,42.3\n"
        "Gas,Heating,60.0\n"
    )

    def test_raises_unsupported(self):
        """Three data rows raise ValueError (sankey-beta unsupported)."""
        with pytest.raises(ValueError, match="not supported"):
            _sankey(self._SRC)

    def test_two_rows_also_raise(self):
        """Two data rows also raise ValueError."""
        with pytest.raises(ValueError):
            _sankey("Electricity,Lighting,28.7\nElectricity,Heating,42.3\n")


# ---------------------------------------------------------------------------
# TestSankeyBetaQuotedValues — quoted sources/targets containing commas
# ---------------------------------------------------------------------------

class TestSankeyBetaQuotedValues:
    """Quoted identifiers with embedded commas — all raise ValueError (unsupported)."""

    _SRC_QUOTED_SOURCE = '"Fuel, Oil",Heating,10.5\n'
    _SRC_QUOTED_TARGET = 'Nuclear,"Electricity Gen",92.9\n'
    _SRC_BOTH_QUOTED = '"Fuel, Oil","Electricity Gen",0.9\n'
    _SRC_MULTI_QUOTED = (
        '"Fuel, Oil",Heating,10.5\n'
        '"Fuel, Oil","Electricity Gen",0.9\n'
        'Nuclear,"Electricity Gen",92.9\n'
    )

    def test_quoted_source_raises(self):
        """A row with a quoted source raises ValueError."""
        with pytest.raises(ValueError):
            _sankey(self._SRC_QUOTED_SOURCE)

    def test_quoted_target_raises(self):
        """A row with a quoted target raises ValueError."""
        with pytest.raises(ValueError):
            _sankey(self._SRC_QUOTED_TARGET)

    def test_both_quoted_raises(self):
        """A row with both source and target quoted raises ValueError."""
        with pytest.raises(ValueError):
            _sankey(self._SRC_BOTH_QUOTED)

    def test_multiple_quoted_rows_raise(self):
        """Multiple rows mixing quoted and unquoted identifiers raise ValueError."""
        with pytest.raises(ValueError):
            _sankey(self._SRC_MULTI_QUOTED)


# ---------------------------------------------------------------------------
# TestSankeyBetaDecimalValues — decimal numeric flow values
# ---------------------------------------------------------------------------

class TestSankeyBetaDecimalValues:
    """Decimal and integer flow values — all raise ValueError (unsupported)."""

    def test_decimal_value_raises(self):
        """A row with a decimal value raises ValueError."""
        with pytest.raises(ValueError):
            _sankey("Electricity,Lighting,28.7\n")

    def test_large_integer_value_raises(self):
        """A large integer flow value raises ValueError."""
        with pytest.raises(ValueError):
            _sankey("Coal,Power,10000\n")

    def test_decimal_and_integer_mixed_raises(self):
        """Rows mixing decimal and integer values raise ValueError."""
        with pytest.raises(ValueError):
            _sankey("A,B,100\nC,D,55.5\nE,F,0.1\n")


# ---------------------------------------------------------------------------
# TestSankeyBetaMultiFlow — multi-source / multi-target flows
# ---------------------------------------------------------------------------

class TestSankeyBetaMultiFlow:
    """Multi-source / multi-target flows — all raise ValueError (unsupported)."""

    _FULL_EXAMPLE = (
        "Electricity,Lighting,28.7\n"
        "Electricity,Heating,42.3\n"
        "Gas,Heating,60.0\n"
        "Nuclear,Electricity,92.9\n"
        '"Fuel, Oil",Heating,10.5\n'
        '"Fuel, Oil","Electricity Gen",0.9\n'
    )

    def test_multi_source_single_target_raises(self):
        """Multiple sources flowing into the same target raises ValueError."""
        src = (
            "Electricity,Heating,42.3\n"
            "Gas,Heating,60.0\n"
            '"Fuel, Oil",Heating,10.5\n'
        )
        with pytest.raises(ValueError):
            _sankey(src)

    def test_full_example_raises(self):
        """The full mermaid.js docs example (all 6 rows) raises ValueError."""
        with pytest.raises(ValueError):
            _sankey(self._FULL_EXAMPLE)

    def test_chain_flow_raises(self):
        """A three-step chain A→B→C raises ValueError."""
        with pytest.raises(ValueError):
            _sankey("A,B,50\nB,C,50\n")
