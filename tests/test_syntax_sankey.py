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
``sankey-beta`` is rendered by the pure-Python HTML backend (AC-3.1) as a
dedicated flow diagram: one ``<rect data-sankey-node>`` bar per node and one
``<path data-sankey-link>`` ribbon per flow, never the generic node-graph
fallback. A leading ``source,target,value`` header row (non-numeric value) is
skipped. These tests verify the renderer accepts every valid sankey-beta input
shape and emits the dedicated Sankey markers.

Import note: ``to_html`` lives in ``mermaid_render``, not the backward-compat
``mermaid_layout`` shim.  Import directly from ``mermaid_render``.
"""
from __future__ import annotations

import sys
from pathlib import Path

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


def _n_links(html: str) -> int:
    return html.count("data-sankey-link")


def _n_nodes(html: str) -> int:
    return html.count("data-sankey-node")


# ---------------------------------------------------------------------------
# TestSankeyBetaSupport — sankey-beta renders as a dedicated flow diagram
# ---------------------------------------------------------------------------

class TestSankeyBetaSupport:
    """sankey-beta renders with dedicated Sankey markers (AC-3.1)."""

    def test_minimal_renders(self):
        """Minimal sankey-beta renders one link and two node bars."""
        html = _sankey("A,B,10\n")
        assert _n_links(html) == 1
        assert _n_nodes(html) == 2

    def test_not_generic_graph(self):
        """Output is the dedicated Sankey layout, not the generic edge fallback."""
        html = _sankey("Electricity,Lighting,28.7\n")
        assert "data-sankey-node" in html
        assert "data-src=" not in html  # no generic annotated edge paths

    def test_header_row_skipped(self):
        """The 'source,target,value' header (non-numeric value) is not a flow."""
        html = _sankey("A,B,10\n")
        assert _n_links(html) == 1  # header dropped, only A→B


# ---------------------------------------------------------------------------
# TestSankeyBetaBasic — basic 3-row CSV
# ---------------------------------------------------------------------------

class TestSankeyBetaBasic:
    """Basic three-row CSV renders one ribbon per row."""

    _SRC = (
        "Electricity,Lighting,28.7\n"
        "Electricity,Heating,42.3\n"
        "Gas,Heating,60.0\n"
    )

    def test_three_rows_three_links(self):
        html = _sankey(self._SRC)
        assert _n_links(html) == 3

    def test_two_rows_two_links(self):
        html = _sankey("Electricity,Lighting,28.7\nElectricity,Heating,42.3\n")
        assert _n_links(html) == 2


# ---------------------------------------------------------------------------
# TestSankeyBetaQuotedValues — quoted sources/targets containing commas
# ---------------------------------------------------------------------------

class TestSankeyBetaQuotedValues:
    """Quoted identifiers with embedded commas parse as a single node."""

    _SRC_QUOTED_SOURCE = '"Fuel, Oil",Heating,10.5\n'
    _SRC_QUOTED_TARGET = 'Nuclear,"Electricity Gen",92.9\n'
    _SRC_BOTH_QUOTED = '"Fuel, Oil","Electricity Gen",0.9\n'
    _SRC_MULTI_QUOTED = (
        '"Fuel, Oil",Heating,10.5\n'
        '"Fuel, Oil","Electricity Gen",0.9\n'
        'Nuclear,"Electricity Gen",92.9\n'
    )

    def test_quoted_source_one_node(self):
        html = _sankey(self._SRC_QUOTED_SOURCE)
        assert "Fuel, Oil" in html
        assert _n_links(html) == 1

    def test_quoted_target_one_node(self):
        html = _sankey(self._SRC_QUOTED_TARGET)
        assert "Electricity Gen" in html
        assert _n_links(html) == 1

    def test_both_quoted(self):
        html = _sankey(self._SRC_BOTH_QUOTED)
        assert "Fuel, Oil" in html
        assert "Electricity Gen" in html

    def test_multiple_quoted_rows(self):
        html = _sankey(self._SRC_MULTI_QUOTED)
        assert _n_links(html) == 3


# ---------------------------------------------------------------------------
# TestSankeyBetaDecimalValues — decimal numeric flow values
# ---------------------------------------------------------------------------

class TestSankeyBetaDecimalValues:
    """Decimal and integer flow values all render."""

    def test_decimal_value(self):
        html = _sankey("Electricity,Lighting,28.7\n")
        assert _n_links(html) == 1

    def test_large_integer_value(self):
        html = _sankey("Coal,Power,10000\n")
        assert _n_links(html) == 1

    def test_decimal_and_integer_mixed(self):
        html = _sankey("A,B,100\nC,D,55.5\nE,F,0.1\n")
        assert _n_links(html) == 3


# ---------------------------------------------------------------------------
# TestSankeyBetaMultiFlow — multi-source / multi-target flows
# ---------------------------------------------------------------------------

class TestSankeyBetaMultiFlow:
    """Multi-source / multi-target flows render every ribbon."""

    _FULL_EXAMPLE = (
        "Electricity,Lighting,28.7\n"
        "Electricity,Heating,42.3\n"
        "Gas,Heating,60.0\n"
        "Nuclear,Electricity,92.9\n"
        '"Fuel, Oil",Heating,10.5\n'
        '"Fuel, Oil","Electricity Gen",0.9\n'
    )

    def test_multi_source_single_target(self):
        src = (
            "Electricity,Heating,42.3\n"
            "Gas,Heating,60.0\n"
            '"Fuel, Oil",Heating,10.5\n'
        )
        html = _sankey(src)
        assert _n_links(html) == 3

    def test_full_example(self):
        """The full mermaid.js docs example (all 6 rows) renders 6 ribbons."""
        html = _sankey(self._FULL_EXAMPLE)
        assert _n_links(html) == 6

    def test_chain_flow(self):
        """A three-step chain A→B→C renders two ribbons across three columns."""
        html = _sankey("A,B,50\nB,C,50\n")
        assert _n_links(html) == 2
        assert _n_nodes(html) == 3
